"""Conservative, auditable effort summaries; unknown work is never zero work."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shlex
import statistics

# Only simple commands qualify. A compound shell status cannot reliably be
# attributed to its embedded build/test, and quoted text is not execution.
def recognized_check(command):
    if not isinstance(command, str) or any(c in command for c in '\n;|&<>`'):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if not words:
        return False
    executable = Path(words[0]).name
    args = words[1:]
    if any(arg in ('--help', '-h', '--version', '-V', '-version', '-help', '--showConfig', '--print', '--listFilesOnly', '--init', '--all', '-v', '--clean', '--dry') for arg in args):
        return False
    return (executable == 'build.sh'
            or executable in ('sh', 'bash') and args == ['build.sh']
            or executable.startswith('python') and args == ['test_public.py']
            or executable == 'cargo' and bool(args) and args[0] in ('check', 'test', 'build')
            or executable == 'dotnet' and bool(args) and args[0] in ('build', 'test')
            or executable == 'ruby' and bool(args) and args[0] == '-c'
            or executable == 'tsc' and bool(args)
            or executable in ('ghc', 'kotlinc') and any(arg.endswith(('.hs', '.kt')) for arg in args))


def tool_effort(invocations):
    counts = Counter()
    pending_revision = False
    checked_before = False
    last_check_failed = None
    cycles = []
    for invocation in invocations:
        records = invocation.get('tool_records')
        if records is None:
            counts['invocations_missing_tool_records'] += 1
            continue
        for tool in records:
            counts['tool_calls'] += 1
            if tool.get('rejected'):
                counts['rejected_tool_calls'] += 1
                continue
            before, after = tool.get('source_before'), tool.get('source_after')
            changed = before is not None and after is not None and before != after
            if before is None or after is None:
                counts['calls_missing_source_evidence'] += 1
            if changed:
                counts['source_changing_calls'] += 1
                pending_revision = True
            command = (tool.get('arguments') or {}).get('command', '')
            recognized = recognized_check(command)
            result = tool.get('result') or {}
            if result.get('termination'):
                counts['terminated_tool_calls'] += 1
            if result.get('returncode') not in (None, 0):
                counts['nonzero_exit_calls'] += 1
            if not recognized:
                counts['unclassified_command_calls'] += 1
                continue
            counts['recognized_check_calls'] += 1
            failed = result.get('returncode') != 0 or result.get('termination') is not None
            if result.get('returncode') is None:
                failed = None
            if checked_before and pending_revision:
                cycles.append(dict(invocation=invocation.get('index'), call_id=tool.get('call_id'),
                                   preceding_check_failed=last_check_failed, check_failed=failed))
            checked_before = True
            pending_revision = False
            last_check_failed = failed
    available = bool(invocations) and counts['invocations_missing_tool_records'] == 0
    return dict(rule_version='observable-check-revision-check-v1', counts=dict(counts),
                trace_available=available,
                observed_revision_check_cycles=len(cycles) if available else None,
                observed_repair_cycles=sum(c['preceding_check_failed'] is True for c in cycles) if available else None,
                cycle_evidence=cycles,
                limitation='Lower-bound trace observations; mixed shell commands and unrecognized checks remain ambiguous.')


def attempt_row(cell, state, result=None):
    result = result or {}
    collection = result.get('collection') or result.get('partial_collection') or {}
    invocations = collection.get('invocations', [])
    grades = {g['index']: g for g in result.get('grades', []) if 'index' in g}
    initial = grades.get(0)
    checkpoints = collection.get('checkpoints', [])
    final_index = max((c['index'] for c in checkpoints), default=None)
    final = grades.get(final_index)
    last_graded = grades.get(max(grades)) if grades else None
    interventions = collection.get('interventions', [])
    usage = collection.get('usage_summary') or {}
    uncertain_nudge = any(i.get('category') == 'reactivation' and i.get('delivery_status') != 'invocation_returned' for i in interventions)
    from .provider_usage import summarize_invocations as summarize_usage
    initial_usage = summarize_usage(invocations[:1]) if invocations else {}
    return dict(cell=cell, state=state, validity=result.get('validity'),
                initial_success=initial.get('success') if initial else None,
                final_success=final.get('success') if final else None,
                final_checkpoint_index=final_index,
                last_graded_index=max(grades) if grades else None,
                last_graded_success=last_graded.get('success') if last_graded else None,
                initial_critical_failures=initial.get('critical_failures') if initial else None,
                final_critical_failures=final.get('critical_failures') if final else None,
                actual_nudges=None if uncertain_nudge else sum(i.get('category') == 'reactivation' and i.get('delivery_status') == 'invocation_returned' for i in interventions),
                planned_nudges=sum(i.get('category') == 'reactivation' for i in interventions),
                nudge_delivery_uncertain=uncertain_nudge,
                interventions=interventions, intervention_types=dict(Counter(i.get('category', 'unknown') for i in interventions)),
                observed_human_repair_seconds=None,
                initial_seconds=invocations[0].get('seconds') if invocations else None,
                active_seconds=collection.get('active_seconds'), usage=usage, initial_usage=initial_usage,
                provider_reported_tokens=usage.get('provider_reported_total'),
                initial_provider_reported_tokens=initial_usage.get('provider_reported_total'),
                cli_normalized_tokens=usage.get('cli_normalized_total'),
                initial_cli_normalized_tokens=initial_usage.get('cli_normalized_total'),
                stop_reason=collection.get('stop_reason'), harness_timing=result.get('timing', {}),
                effort=tool_effort(invocations),
                handoffs=[dict(index=i.get('index'), status=i.get('status'), seconds=i.get('seconds'),
                               usage_records=i.get('usage_records')) for i in invocations])


def report_matrix(directory):
    directory = Path(directory)
    plan = json.loads((directory / 'plan.json').read_text())
    progress = json.loads((directory / 'matrix.json').read_text())
    if hashlib.sha256((directory / 'plan.json').read_bytes()).hexdigest() != progress.get('plan_sha256'):
        raise ValueError('frozen plan hash mismatch')
    if len(plan['cells']) != len(progress['cells']):
        raise ValueError('progress does not cover every planned cell')
    rows = []
    for cell, state in zip(plan['cells'], progress['cells']):
        if cell['id'] != state['id']:
            raise ValueError('matrix identity mismatch')
        path = directory / cell['id'] / 'result.json'
        if state.get('result_sha256'):
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != state['result_sha256']:
                raise ValueError('preserved result hash mismatch')
        result = json.loads(path.read_text()) if path.exists() else None
        rows.append(attempt_row(cell, state['state'], result))
    grouped = defaultdict(list)
    for row in rows:
        cell = row['cell']
        grouped[(cell['language'], cell['provider'], cell['model'], cell['tests'])].append(row)
    summaries = []
    for (language, provider, model, condition), group in sorted(grouped.items()):
        times = [r['active_seconds'] for r in group if r['active_seconds'] is not None]
        tokens = [r['provider_reported_tokens'] for r in group if r['provider_reported_tokens'] is not None]
        summaries.append(dict(language=language, provider=provider, model=model, tests=condition,
                              planned_attempts=len(group), states=dict(Counter(r['state'] for r in group)),
                              graded_initial_attempts=sum(r['initial_success'] is not None for r in group),
                              first_handoff_successes=sum(r['initial_success'] is True for r in group),
                              final_successes=sum(r['final_success'] is True for r in group),
                              nudge_counts=[r['actual_nudges'] for r in group],
                              harness_timing=[r['harness_timing'] for r in group],
                              active_seconds=times, provider_reported_tokens=tokens,
                              attempts_with_token_totals=len(tokens),
                              median_provider_reported_tokens=statistics.median(tokens) if tokens else None,
                              observed_repair_cycles=[r['effort']['observed_repair_cycles'] for r in group],
                              median_active_seconds=statistics.median(times) if times else None,
                              operator_interventions=dict(sum((Counter(r['intervention_types']) for r in group), Counter()))))
    return dict(schema_version=1, kind='language_effort_analysis', attempts=rows, summary=summaries,
                limitations=['One ledger task, two repetitions; exploratory, not a general language ranking.',
                             'Unrun and invalid cells remain visible; unknown usage and human time remain unknown.',
                             'Token comparisons are within provider/model; CLI-normalized scopes remain labeled.',
                             'Check/revision cycles are observable lower bounds, not all reasoning iterations.',
                             'Queue reference authoring is separate and supplies no controlled AI effort comparison.'])
