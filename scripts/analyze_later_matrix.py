#!/usr/bin/env python3
"""Post-hoc native-usage analysis of exact 28-cell follow-up cohorts."""
import argparse
from collections import Counter
import statistics
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import analyze_subscription_matrix as base
from langbench.later_matrix import validate_plan
from scripts.fork_later_matrix import validate_lineage, epoch_for_cell
from langbench.metrics import reconcile_provider_usage
from langbench.claude_subscriptions import reconcile_claude_usage, proven_unsent

VERSION = 'later-subscription-analysis-v1'


def native_usage(provider, invocations):
    if provider == 'codex':
        proof = reconcile_provider_usage(invocations)
        mapping = {'input_including_cache':'inputTokens', 'output_including_reasoning':'outputTokens',
                   'cache_read':'cachedInputTokens', 'cache_write':'cacheWriteInputTokens', 'reasoning':'reasoningOutputTokens'}
        observed = proof['observed_components']
        observed_fields = {key for invocation in invocations for event in invocation.get('events', [])
                           if event.get('method') == 'rawResponse/completed'
                           for key,value in ((event.get('params') or {}).get('usage') or {}).items()
                           if type(value) is int and value >= 0}
        # The reconciler's zero accumulators are not observations when no responses exist.
        components = {name: {'total': observed[key] if proof['complete'] else None,
                             'known_subtotal': proof['known_subtotals'][key] if proof['response_count'] and key in observed_fields else None}
                      for name,key in mapping.items()}
        return {'provider_total':proof['provider_reported_total_tokens'],
                'provider_known_subtotal':proof['known_subtotals']['totalTokens'] if proof['response_count'] and 'totalTokens' in observed_fields else None,
                'native_coverage_complete':proof['complete'], 'components':components,
                'observed_request_count':proof['response_count'],
                'request_count_scope':'Observed completed native response identities, not wire request starts.',
                'mapping':'Inclusive input/output; cache/reasoning subsets are not added.',
                'native_proof':proof, 'billing_total':None}
    if provider == 'claude':
        proof = reconcile_claude_usage(invocations)
        mapping = {'input_uncached':'input', 'cache_read':'cache_read', 'cache_write':'cache_write',
                   'output_including_reasoning':'output_including_reasoning', 'reasoning':'reasoning'}
        components = {name:{'total':proof['components'].get(key),
                            'known_subtotal':proof['observed_component_lower_bounds'].get(key)}
                      for name,key in mapping.items()}
        return {'provider_total':proof['total'], 'provider_known_subtotal':proof['known_subtotal'],
                'known_token_lower_bound':proof['known_token_lower_bound'],
                'native_coverage_complete':proof['complete'], 'components':components,
                'observed_request_count':proof['request_count'],
                'request_count_scope':'Native Messages identities plus unidentified observations; conflicts remain explicit.',
                'mapping':'Disjoint uncached input/cache read/cache creation/output; reasoning subset is unknown.',
                'native_proof':proof, 'billing_total':None}
    raise ValueError('unsupported later provider')


def operational_effort(provider, invocations):
    """Observed overhead, never subtracted from candidate wall time."""
    def numeric(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    rows = []
    for invocation in invocations:
        requests = invocation.get('request_records')
        available = provider == 'claude' and isinstance(requests, list)
        interval = None
        if available:
            first_sent = next((n for n, request in enumerate(requests) if request.get('upstream_sent') is True), None)
            if first_sent is not None:
                prefix = requests[:first_sent+1]
                times = [request.get('started_at') for request in prefix]
                if (all(proven_unsent(request) for request in prefix[:-1]) and all(numeric(t) for t in times)
                        and times == sorted(times)):
                    interval = times[-1] - times[0]
        def reported(key):
            value = invocation.get(key)
            return value if numeric(value) else None
        rows.append({'index':invocation.get('index'),
                     'operational_request_count':len(requests) if available else None,
                     'proven_unsent_request_count':sum(proven_unsent(r) for r in requests) if available else None,
                     'reported_allowance_http_seconds':reported('allowance_preflight_seconds') if provider == 'claude' else None,
                     'allowance_preflight_seconds':reported('allowance_preflight_seconds'),
                     'auth_preflight_seconds':reported('auth_preflight_seconds'),
                     'cleanup_seconds':reported('cleanup_seconds'),
                     'initial_preflight_retry_interval_seconds':interval})
    aggregate = {}
    fields = ('operational_request_count','proven_unsent_request_count','reported_allowance_http_seconds',
              'allowance_preflight_seconds','auth_preflight_seconds','cleanup_seconds','initial_preflight_retry_interval_seconds')
    for field in fields:
        values = [row[field] for row in rows if row[field] is not None]
        complete = bool(rows) and len(values) == len(rows)
        aggregate[field] = {'total':sum(values) if complete else None,
                            'known_subtotal':sum(values) if values else None,
                            'known_invocations':len(values),'invocations':len(rows),'complete':complete}
    return {'invocations':rows,'aggregate':aggregate,
            'retry_interval_scope':'Lower bound from first observed proven-unsent request start to first sent request start; no sent request or unknown prefix yields unknown.',
            'timing_limit':'Wall-clock timestamps may be affected by clock adjustment. HTTP call durations exclude retry backoff. No subtraction yields pure coding or thinking time.'}


def later_row(cell, state, result, directory, override, receipt_sha):
    row = base.attempt_row(cell, state, result, directory, override, receipt_sha)
    collection = result.get('collection') or result.get('partial_collection') or {}
    invocations = collection.get('invocations', [])
    row['usage'] = native_usage(cell['provider'], invocations)
    for point in row['checkpoints']:
        prefix = [i for i in invocations if i['index'] <= point['index']]
        point['usage'] = native_usage(cell['provider'], prefix)
        point['usage']['scope'] = 'Cumulative candidate work through this checkpoint, including prior invocations.'
    row['initial_usage'] = native_usage(cell['provider'], invocations[:1])
    row['operational_effort'] = operational_effort(cell['provider'], invocations)
    explicit = [i.get('inference_started') for i in invocations]
    requests = [request for invocation in invocations for request in invocation.get('request_records', [])]
    native_responses = any(event.get('method') == 'rawResponse/completed'
                           for invocation in invocations for event in invocation.get('events', []))
    sent = any(request.get('upstream_sent') is True for request in requests)
    all_unsent = bool(requests) and all(request.get('upstream_sent') is False for request in requests)
    started = (True if sent or native_responses else
               False if state['state'] == 'not_run_quota' or all_unsent else
               None if requests else
               True if any(value is True for value in explicit) else
               False if explicit and all(value is False for value in explicit) else None)
    row['coding_attempt_started'] = started
    stop = row['analysis_terminal_status']
    operational = stop in ('quota', 'not_run_quota', 'infrastructure_error', 'infrastructure_invalid', 'interrupted_unknown') or row['raw_validity'] == 'infrastructure_invalid'
    row['outcome_category'] = ('quota_before_coding' if started is False and stop in ('quota', 'not_run_quota') else
                               'quota_interrupted' if stop == 'quota' else
                               'infrastructure_unknown' if operational else
                               'coding_observed' if started is True else 'coding_start_unknown')
    correctness = (row['final'] or {}).get('correct')
    row['semantic_outcome_eligible'] = started is True and not operational and type(correctness) is bool
    row['semantic_failure'] = (correctness is False) if row['semantic_outcome_eligible'] else None
    row['coding_active_seconds'] = row['active_seconds'] if started is True else None
    return row


def analyze(directory):
    report = base.analyze(directory, plan_validator=validate_plan, row_builder=later_row)
    # Base summaries retain raw artifact grades. Separate attribution counters
    # prevent pre-inference quota snapshots from becoming language failures.
    for summary in report['summary']:
        members = [r for r in report['attempts'] if all(r['cell'][k] == summary[k]
                   for k in ('language', 'provider', 'model', 'tests'))]
        summary['raw_artifact_initial_correct'] = summary['initial_correct']
        summary['raw_artifact_final_correct'] = summary['final_correct']
        summary['semantic_failures'] = sum(r['semantic_failure'] is True for r in members)
        summary['semantic_outcome_eligible'] = sum(r['semantic_outcome_eligible'] for r in members)
        summary['outcome_categories'] = dict(Counter(r['outcome_category'] for r in members))
        for field, value in (('active_seconds', lambda r:r['coding_active_seconds']),
                             ('provider_tokens', lambda r:r['usage']['provider_total'] if r['coding_attempt_started'] is True else None)):
            values = [value(r) for r in members if value(r) is not None]
            summary[field] = {'known_n':len(values), 'values':values,
                              'median':statistics.median(values) if values else None,
                              'scope':'Observed coding attempts only; raw per-attempt operational effort retained.'}
    lineage = validate_lineage(directory)
    if lineage:
        report['instrumentation_lineage'] = lineage
        report['instrumentation_lineage_sha256'] = base.sha((Path(directory)/'instrumentation-epoch.json').read_bytes())
        for row in report['attempts']:
            row['instrumentation_epoch'] = epoch_for_cell(directory, row['cell']['id'])
        for summary in report['summary']:
            summary['instrumentation_epochs'] = dict(Counter(row['instrumentation_epoch'] for row in report['attempts']
                if all(row['cell'][key] == summary[key] for key in ('language','provider','model','tests'))))
    report['analysis_version'] = VERSION
    report['limitations'].append('Native provider schemas differ; Codex response counts are not wire-start counts. Checkpoint usage is cumulative. Raw artifact grades do not attribute quota/infra failures to language semantics; explicit semantic_failure and outcome_categories carry attribution.')
    return report


def markdown(report):
    text = base.markdown(report)
    text += '\n## Attribution of operational outcomes\n\n'
    text += 'Initial/final correct columns above describe raw saved artifacts, not language-failure attribution. Coding time/token medians exclude attempts without evidence of inference. Operational effort remains in JSON.\n\n'
    text += '| Cell | Coding started | Outcome category | Semantic failure |\n|---|---|---|---|\n'
    for row in report['attempts']:
        text += f"| {row['cell']['id']} | {row['coding_attempt_started']} | {row['outcome_category']} | {row['semantic_failure']} |\n"
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('matrix',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--allow-interim',action='store_true')
    args=parser.parse_args();report=analyze(args.matrix)
    if report['status']=='INTERIM' and not args.allow_interim:
        parser.error('collection is not closed; explicitly request --allow-interim')
    if args.output.resolve().is_relative_to(args.matrix.resolve()):
        parser.error('output must be outside preserved matrix')
    args.output.mkdir(parents=True,exist_ok=False)
    (args.output/'analysis.json').write_text(json.dumps(report,indent=2)+'\n')
    (args.output/'analysis.md').write_text(markdown(report))


if __name__=='__main__':main()
