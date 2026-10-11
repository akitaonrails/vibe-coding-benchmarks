#!/usr/bin/env python3
"""Read-only, versioned analysis of frozen subscription receipts; never runs candidates."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langbench.core import digest_tree
from langbench.effort_report import tool_effort
from langbench.matrix import validate_plan

VERSION = 'subscription-analysis-v1'
COMPONENTS = ('input_including_cache', 'output_including_reasoning', 'cache_read', 'cache_write', 'reasoning')
CLOSED = {'collected', 'infrastructure_invalid', 'quota', 'not_run_quota', 'interrupted_unknown'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def usage(invocations):
    """Native inclusive components only. CLI disjoint components remain separate."""
    records = {}
    conflicts = []
    conflicted_keys = set()
    for position, invocation in enumerate(invocations):
        for record in invocation.get('usage_records', []):
            key = (position, record.get('provider'), record.get('request_id'))
            if key in records and records[key] != record:
                conflicts.append(list(key))
                conflicted_keys.add(key)
            records[key] = record
    native = list(records.values())
    coverage_issues = []
    for position, invocation in enumerate(invocations):
        requests = invocation.get('request_records')
        if not isinstance(requests, list):
            coverage_issues.append({'invocation': position, 'reason': 'missing_request_trace'})
            continue
        indices = [r.get('index') for r in requests]
        if any(type(index) is not int or index < 0 for index in indices) or len(set(indices)) != len(indices):
            coverage_issues.append({'invocation': position, 'reason': 'invalid_or_duplicate_request_identity'})
            continue
        expected = {'transport-'+str(index) for index in indices}
        observed = [key[2] for key in records if key[0] == position]
        if len(observed) != len(expected) or set(observed) != expected:
            coverage_issues.append({'invocation': position, 'reason': 'request_usage_identity_mismatch'})
        if any(r.get('response_complete') is not True or r.get('http_status') != 200 for r in requests):
            coverage_issues.append({'invocation': position, 'reason': 'incomplete_request_response'})
    covered = (bool(invocations) and not coverage_issues
               and all(i.get('usage_coverage_verified') is True for i in invocations))
    verified = [r for key, r in records.items() if key not in conflicted_keys
                and r.get('native_fields_verified') is True and r.get('valid') is True]
    def number(value):
        return type(value) is int and value >= 0
    totals = [r['provider_reported_total'] for r in verified if number(r.get('provider_reported_total'))]
    complete = covered and bool(native) and len(totals) == len(native) and not conflicts
    components = {}
    for name in COMPONENTS:
        values = [(r.get('components') or {}).get(name) for r in verified]
        known = [v for v in values if number(v)]
        components[name] = {'total': sum(known) if complete and len(known) == len(native) else None,
                            'known_subtotal': sum(known) if known else None,
                            'records_with_component': len(known)}
    request_traces = all(isinstance(i.get('request_records'), list) for i in invocations) and bool(invocations)
    return {'provider_total': sum(totals) if complete else None,
            'provider_known_subtotal': sum(totals) if totals else None,
            'native_coverage_complete': complete, 'components': components,
            'observed_request_count': sum(len(i['request_records']) for i in invocations) if request_traces else None,
            'native_usage_record_count': len(native), 'conflicts': conflicts, 'coverage_issues': coverage_issues,
            'parser_versions': sorted({r['parser_version'] for r in native if r.get('parser_version')}),
            'mapping': 'Input/output inclusive; cache/reasoning subsets are not added. Missing components remain unknown.',
            'cli_records': [r for i in invocations for r in i.get('cli_usage_records', [])]}


def overrides_for(directory, receipts):
    rows = jsonl(directory / 'outcome-overrides.jsonl')
    selected = {}
    for row in rows:
        cell = row.get('cell')
        if row.get('schema_version') != 1 or cell not in receipts:
            raise ValueError('unknown override schema or cell')
        if not receipts[cell] or row.get('raw_result_sha256') != receipts[cell]:
            raise ValueError('override result SHA mismatch')
        classification = row.get('analysis_classification')
        if classification not in ('model_output_limit', 'infrastructure_invalid', 'quota', 'timeout'):
            raise ValueError('unsupported override classification')
        if not row.get('actor') or not row.get('time') or not row.get('action'):
            raise ValueError('override provenance missing')
        if not (isinstance(row.get('evidence'), dict) or
                (row.get('signature') and row.get('raw_process_sha256') and isinstance(row.get('cleanup_evidence'), dict))):
            raise ValueError('override evidence missing')
        if row.get('raw_process_sha256'):
            process = directory / cell / 'trace' / 'invocation-0.json'
            if not process.is_file() or sha(process.read_bytes()) != row['raw_process_sha256']:
                raise ValueError('override process SHA mismatch')
        if cell in selected and selected[cell]['analysis_classification'] != classification:
            raise ValueError('conflicting overrides')
        selected[cell] = row
    return selected, rows


def validate_result(cell, result, attempt):
    requested = result.get('requested')
    if requested is not None:
        for key in ('task', 'language', 'tests', 'provider', 'model', 'effort'):
            if requested.get(key) != cell[key]:
                raise ValueError('requested treatment mismatch: '+key)
    manifest = result.get('manifest')
    if manifest:
        data = json.dumps(manifest, sort_keys=True).encode()
        if sha(data) != result.get('manifest_sha256'):
            raise ValueError('manifest commitment mismatch')
        if (attempt / 'attempt.json').exists() and (attempt / 'attempt.json').read_bytes() != data:
            raise ValueError('manifest file mismatch')
        for key in ('task', 'language', 'tests', 'provider', 'model', 'effort', 'replicate', 'semantic_seed',
                    'block_id', 'base_seconds', 'continuation_seconds', 'max_nudges'):
            if manifest.get(key) != cell[key]:
                raise ValueError('manifest treatment mismatch: '+key)
    elif result.get('collection'):
        raise ValueError('collected result lacks identity manifest')
    for grade in result.get('grades', []):
        for key, expected in (('task', cell['task']), ('language', cell['language']), ('seed', cell['semantic_seed'])):
            if grade.get(key) != expected:
                raise ValueError('grade identity mismatch')


def checkpoint_row(checkpoint, grade, invocation, attempt):
    index = checkpoint['index']
    if grade and checkpoint.get('artifact_available') is not True:
        raise ValueError('grade contradicts unavailable artifact')
    if grade and invocation.get('artifact_available') is False:
        raise ValueError('grade contradicts invocation artifact unavailability')
    source = None
    artifact_verified = None
    # Resolve only the conventional trusted snapshot path, never a receipt's arbitrary path.
    path = attempt / 'collection' / ('snapshot-'+str(index))
    if path.is_dir():
        if digest_tree(path, ignore_root_artifacts=True) != checkpoint.get('artifact_sha256'):
            raise ValueError('snapshot artifact hash mismatch')
        artifact_verified = True
        src = path / 'src'
        if src.is_dir():
            source_hash = digest_tree(src)
            if grade and source_hash != grade.get('source_sha256'):
                raise ValueError('graded source hash mismatch')
            files = [p for p in src.rglob('*') if p.is_file()]
            source = {'sha256': source_hash, 'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
                      'lines': sum(len(p.read_bytes().splitlines()) for p in files),
                      'line_basis': 'All submitted src files, including self-authored tests; not production-only LOC.'}
    valid_grade = grade if grade and grade.get('validity') == 'valid' else None
    status = invocation.get('status')
    return {'index': index, 'artifact_available': checkpoint.get('artifact_available'),
            'artifact_sha256': checkpoint.get('artifact_sha256'), 'artifact_verified_on_disk': artifact_verified,
            'source_size': source, 'raw_terminal_status': status, 'declared_status': checkpoint.get('declared_status'),
            'seconds': invocation.get('seconds'), 'grade_validity': grade.get('validity') if grade else None,
            'correct': valid_grade.get('success') if valid_grade else None,
            'groups': valid_grade.get('groups') if valid_grade else None,
            'critical_failures': valid_grade.get('critical_failures') if valid_grade else None,
            'cases_passed': sum(c.get('passed') is True for c in valid_grade.get('cases', [])) if valid_grade else None,
            'cases_total': len(valid_grade.get('cases', [])) if valid_grade else None,
            'usage': usage([invocation]) if invocation else usage([])}


def attempt_row(cell, state, result, directory, override, receipt_sha):
    collection = result.get('collection') or result.get('partial_collection') or {}
    invocations = collection.get('invocations', [])
    indexed = {i['index']: i for i in invocations}
    grades = {g['index']: g for g in result.get('grades', [])}
    checkpoints = collection.get('checkpoints', [])
    if len(indexed) != len(invocations) or len(grades) != len(result.get('grades', [])):
        raise ValueError('duplicate invocation/grade index')
    indices = [c['index'] for c in checkpoints]
    if len(set(indices)) != len(indices) or any(type(i) is not int or i < 0 for i in indices):
        raise ValueError('invalid checkpoint indices')
    points = [checkpoint_row(c, grades.get(c['index']), indexed.get(c['index'], {}), directory / cell['id']) for c in checkpoints]
    initial = next((p for p in points if p['index'] == 0), None)
    final = max(points, key=lambda p:p['index']) if points else None
    raw = invocations[-1].get('status') if invocations else state['state']
    if override and override.get('raw_classification') not in (None, result.get('validity')):
        raise ValueError('override raw classification mismatch')
    analysis = override['analysis_classification'] if override else raw
    for point in points:
        terminal = analysis if final is point else point['raw_terminal_status']
        point['analysis_terminal_status'] = terminal
        point['normal_completed_and_correct'] = (terminal == 'handoff' and point['declared_status'] == 'COMPLETE' and point['correct'] is True)
        point['correct_at_deadline'] = terminal == 'timeout' and point['correct'] is True
    correct = final['correct'] if final else None
    completed = analysis == 'handoff' and bool(final) and final['declared_status'] == 'COMPLETE'
    interventions = collection.get('interventions', [])
    nudges = [i for i in interventions if i.get('category') == 'reactivation']
    effort = tool_effort(invocations)
    return {'cell': cell, 'state': state['state'], 'result_sha256': receipt_sha,
            'raw_validity': result.get('validity'), 'raw_terminal_status': raw, 'analysis_terminal_status': analysis,
            'override': override, 'initial': initial, 'final': final, 'checkpoints': points,
            'normal_completed_and_correct': completed and correct is True,
            'correct_at_deadline': analysis == 'timeout' and correct is True,
            'output_limit': analysis == 'model_output_limit', 'active_seconds': collection.get('active_seconds'),
            'timing': result.get('timing', {}), 'usage': usage(invocations), 'recorded_usage_summary': collection.get('usage_summary'),
            'tool_effort': effort, 'tool_calls': effort['counts'].get('tool_calls', 0) if effort['trace_available'] else None,
            'source_changing_calls': effort['counts'].get('source_changing_calls', 0) if effort['trace_available'] else None,
            'nudge_count': sum(i.get('delivery_status') == 'invocation_returned' for i in nudges)
                if collection and all(i.get('delivery_status') == 'invocation_returned' for i in nudges) else None,
            'planned_nudges': len(nudges), 'interventions': interventions,
            'observed_human_repair_seconds': None}


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        c = row['cell'];groups[(c['language'], c['provider'], c['model'], c['tests'])].append(row)
    summaries = []
    for keys, members in sorted(groups.items()):
        summary = dict(zip(('language', 'provider', 'model', 'tests'), keys))
        summary.update(planned_attempts=len(members), states=dict(Counter(r['state'] for r in members)),
                       terminal_states=dict(Counter(r['analysis_terminal_status'] for r in members)))
        for field in ('normal_completed_and_correct', 'correct_at_deadline', 'output_limit'):
            summary[field] = sum(r[field] is True for r in members)
        for stage in ('initial', 'final'):
            summary[stage+'_graded'] = sum(r[stage] is not None and r[stage]['correct'] is not None for r in members)
            summary[stage+'_correct'] = sum(r[stage] is not None and r[stage]['correct'] is True for r in members)
        summary['final_behavior_groups'] = {}
        names = {name for row in members for name in ((row['final'] or {}).get('groups') or {})}
        for name in sorted(names):
            outcomes = [((row['final'] or {}).get('groups') or {}).get(name) for row in members]
            summary['final_behavior_groups'][name] = {'passed': sum(v is True for v in outcomes),
                                                      'failed': sum(v is False for v in outcomes),
                                                      'unknown': sum(v is None for v in outcomes)}
        for field, getter in (('active_seconds', lambda r:r['active_seconds']),
                              ('provider_tokens', lambda r:r['usage']['provider_total']),
                              ('tools', lambda r:r['tool_calls']), ('nudges', lambda r:r['nudge_count'])):
            values = [getter(r) for r in members if getter(r) is not None]
            summary[field] = {'known_n': len(values), 'values': values, 'median': statistics.median(values) if values else None}
        summaries.append(summary)
    return summaries


def analyze(directory):
    directory = Path(directory)
    plan_bytes = (directory / 'plan.json').read_bytes()
    progress_bytes = (directory / 'matrix.json').read_bytes()
    plan, progress = json.loads(plan_bytes), json.loads(progress_bytes)
    cells = validate_plan(plan)
    if sha(plan_bytes) != progress.get('plan_sha256'):
        raise ValueError('plan SHA mismatch')
    if [c['id'] for c in cells] != [s['id'] for s in progress.get('cells', [])]:
        raise ValueError('progress must cover all planned identities in order')
    receipts, results = {}, {}
    for cell, state in zip(cells, progress['cells']):
        committed = state.get('result_sha256')
        path = directory / cell['id'] / 'result.json'
        if committed:
            data = path.read_bytes()
            if sha(data) != committed:
                raise ValueError('result SHA mismatch')
            results[cell['id']] = json.loads(data)
            validate_result(cell, results[cell['id']], path.parent)
        else:
            # Active/uncommitted files can mutate: do not inspect or analyze them.
            results[cell['id']] = {}
        receipts[cell['id']] = committed
    overrides, override_rows = overrides_for(directory, receipts)
    rows = [attempt_row(c, s, results[c['id']], directory, overrides.get(c['id']), receipts[c['id']])
            for c, s in zip(cells, progress['cells'])]
    operations = jsonl(directory / 'operations.jsonl')
    supervisor = jsonl(directory / 'supervisor-audit.jsonl')
    for op in operations + supervisor:
        if op.get('raw_result_sha256') and receipts.get(op.get('cell')) != op['raw_result_sha256']:
            raise ValueError('operation receipt SHA mismatch')
    if (directory / 'plan.json').read_bytes() != plan_bytes:
        raise ValueError('plan changed during analysis')
    if (directory / 'matrix.json').read_bytes() != progress_bytes:
        raise ValueError('matrix changed during analysis; rerun for a coherent view')
    closed = all(s['state'] in CLOSED for s in progress['cells']) and progress.get('state') in ('complete', 'closed_with_missing_cells')
    return {'schema_version': 1, 'analysis_version': VERSION, 'status': 'closed_cohort' if closed else 'INTERIM',
            'plan_sha256': sha(plan_bytes), 'progress_sha256': sha(progress_bytes),
            'attempts': rows, 'summary': summarize(rows), 'validated_overrides': override_rows,
            'operator_work': {'records': operations, 'record_count': len(operations), 'override_count': len(override_rows),
                              'actor_counts': dict(Counter(o.get('actor', 'unknown') for o in operations)),
                              'supervisor_records': supervisor,
                              'supervisor_event_counts': dict(Counter(o.get('event', 'unknown') for o in supervisor)),
                              'human_hours': None, 'operator_tokens': None,
                              'note': 'Operations and classification overrides are measurement work, not candidate repairs.'},
            'limitations': ['One ledger and two repetitions per condition; no general typing hierarchy or precise ranking.',
                            'Medians use only known values, with denominators; unsuccessful attempts are retained.',
                            'Observable repair cycles are lower bounds; zero does not establish absence of debugging.',
                            'Helper repairs versus production repairs require reviewed annotations; no inferred allocation.',
                            'Source size includes test helpers under src; source stability is not time-to-correctness.',
                            'Provider tokens are not billing or a common cross-provider compute unit.']}


def markdown(report):
    lines = ['# Subscription matrix effort analysis', '', '**'+report['status']+'** — '+report['analysis_version'], '',
             'All planned cells are retained. Unknown values are shown as `?`. '+report['limitations'][0], '',
             '| Attempt | State / analysis stop | Initial correct | Final correct | Normal + correct | Deadline correct | Seconds | Tokens | Tools | Nudges |',
             '|---|---|---|---|---|---|---:|---:|---:|---:|']
    def show(v):return '?' if v is None else str(v)
    for r in report['attempts']:
        values = [r['cell']['id'], r['state']+' / '+str(r['analysis_terminal_status']),
                  (r['initial'] or {}).get('correct'), (r['final'] or {}).get('correct'),
                  r['normal_completed_and_correct'], r['correct_at_deadline'], r['active_seconds'],
                  r['usage']['provider_total'], r['tool_calls'], r['nudge_count']]
        lines.append('| '+' | '.join(show(v) for v in values)+' |')
    lines += ['', '## Language/model/test-condition summaries', '',
              'Medians include known observations only; each metric shows its own denominator. No success-only filtering.', '',
              '| Language | Model | Tests | Planned | Initial correct/graded | Final correct/graded | Normal + correct | Deadline correct | Median seconds (n) | Median tokens (n) |',
              '|---|---|---|---:|---|---|---:|---:|---|---|']
    for s in report['summary']:
        values = [s['language'], s['model'], s['tests'], s['planned_attempts'],
                  f"{s['initial_correct']}/{s['initial_graded']}", f"{s['final_correct']}/{s['final_graded']}",
                  s['normal_completed_and_correct'], s['correct_at_deadline'],
                  f"{show(s['active_seconds']['median'])} ({s['active_seconds']['known_n']})",
                  f"{show(s['provider_tokens']['median'])} ({s['provider_tokens']['known_n']})"]
        lines.append('| '+' | '.join(map(str, values))+' |')
    lines += ['', '## Operator work and limitations', '',
              f"Operational records: {report['operator_work']['record_count']}; validated classification records: {report['operator_work']['override_count']}. Human repair hours and operator tokens are unknown. Detailed interventions, grades, components and provenance are in the companion JSON.", '']
    lines.extend('- '+item for item in report['limitations'])
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('matrix', type=Path)
    parser.add_argument('output', type=Path, help='New output directory; never overwrites existing reports')
    parser.add_argument('--allow-interim', action='store_true')
    args = parser.parse_args()
    report = analyze(args.matrix)
    if report['status'] == 'INTERIM' and not args.allow_interim:
        parser.error('collection is not closed; use --allow-interim for an explicitly labeled interim report')
    if args.output.resolve().is_relative_to(args.matrix.resolve()):
        parser.error('output must be outside the preserved matrix directory')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'analysis.json').write_text(json.dumps(report, indent=2)+'\n')
    (args.output / 'analysis.md').write_text(markdown(report))


if __name__ == '__main__':
    main()
