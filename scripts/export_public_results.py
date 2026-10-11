#!/usr/bin/env python3
"""Export allowlisted measurements, without prompts, credentials or local paths."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import statistics

CELL_FIELDS = ('id', 'task', 'language', 'tests', 'provider', 'model', 'effort',
               'replicate', 'semantic_seed', 'base_seconds', 'continuation_seconds', 'max_nudges')
ROW_FIELDS = ('state', 'result_sha256', 'raw_validity', 'analysis_terminal_status',
              'normal_completed_and_correct', 'correct_at_deadline', 'active_seconds',
              'tool_calls', 'source_changing_calls', 'nudge_count')
COMPONENTS = ('input_including_cache', 'input_uncached', 'output_including_reasoning',
              'cache_read', 'cache_write', 'reasoning')


def select(source, keys):
    return {key: source.get(key) for key in keys}


def export(paths):
    result = {'schema_version': 1, 'scope': 'Exploratory ledger campaign; one task, not a language ranking.',
              'evidence_limit': 'Sanitized measurements and commitments only. Raw traces and candidate artifacts are not distributed.',
              'reports': [], 'attempts': []}
    seen = set()
    for path in paths:
        raw = Path(path).read_bytes()
        report = json.loads(raw)
        if report['status'] != 'closed_cohort':
            raise ValueError('only closed reports may be published')
        report_hash = hashlib.sha256(raw).hexdigest()
        result['reports'].append({'sha256': report_hash, 'plan_sha256': report['plan_sha256'],
                                  'analysis_version': report['analysis_version'], 'attempts': len(report['attempts'])})
        for row in report['attempts']:
            identity = row['cell']['id']
            if identity in seen:
                raise ValueError('duplicate attempt identity')
            seen.add(identity)
            final = row.get('final') or {}
            usage = row['usage']
            entry = {'report_sha256': report_hash, 'cell': select(row['cell'], CELL_FIELDS),
                     **select(row, ROW_FIELDS),
                     'final': select(final, ('artifact_available', 'artifact_sha256', 'grade_validity',
                                             'correct', 'cases_passed', 'cases_total')),
                     'usage': select(usage, ('provider_total', 'provider_known_subtotal',
                                             'native_coverage_complete', 'observed_request_count'))}
            entry['final']['source_size'] = select(final.get('source_size') or {}, ('sha256', 'files', 'bytes', 'lines'))
            entry['usage']['components'] = {name: select(usage['components'][name], ('total', 'known_subtotal'))
                                            for name in COMPONENTS if name in usage['components']}
            result['attempts'].append(entry)
    return result


def summary(data):
    groups = defaultdict(list)
    for row in data['attempts']:
        groups[row['cell']['provider']].append(row)
    lines = ['| Provider | Planned | Normal correct | Deadline correct | Failed artifact | Unknown grade | Complete usage | Median tokens (complete only) | Tools | Source changes | Nudges |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for provider in ('kimi', 'opencode', 'claude', 'codex'):
        rows = groups.get(provider)
        if not rows:
            continue
        tokens = [r['usage']['provider_total'] for r in rows if r['usage']['provider_total'] is not None]
        values = [provider, len(rows), sum(r['normal_completed_and_correct'] is True for r in rows),
                  sum(r['correct_at_deadline'] is True for r in rows),
                  sum(r['final']['correct'] is False for r in rows),
                  sum(r['final']['correct'] is None for r in rows),
                  f'{len(tokens)}/{len(rows)}', f'{statistics.median(tokens):,.1f}' if tokens else 'unknown']
        values += [sum(r[key] for r in rows) for key in ('tool_calls', 'source_changing_calls', 'nudge_count')]
        lines.append('| ' + ' | '.join(map(str, values)) + ' |')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports', type=Path, nargs='*')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--summary', type=Path)
    args = parser.parse_args()
    if args.summary:
        if args.reports or args.output or args.check:
            parser.error('--summary is a separate read-only mode')
        print(summary(json.loads(args.summary.read_text())), end='')
        return
    if not args.reports or not args.output:
        parser.error('report paths and --output are required')
    if args.output.resolve() in [p.resolve() for p in args.reports]:
        parser.error('output cannot overwrite an input report')
    encoded = (json.dumps(export(args.reports), indent=2) + '\n').encode()
    if args.check:
        if args.output.read_bytes() != encoded:
            raise SystemExit('public export differs from the source reports')
        print('Public export matches source reports.')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(encoded)


if __name__ == '__main__':
    main()
