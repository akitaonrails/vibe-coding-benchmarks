"""Separate, exact 28-cell follow-up designs; original receipts stay immutable."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .matrix import _run_matrix, make_plan as original_plan

TARGETS = {'codex': ('gpt-6-sol', 'medium'), 'claude': ('claude-opus-5-5', 'medium')}
RETENTION = 'seal-v1'


def make_plan(provider, seed=20261010):
    if provider not in TARGETS:
        raise ValueError('unsupported exact follow-up target')
    model, effort = TARGETS[provider]
    # Retain the original Kimi arm's order, semantic seeds and paired budgets.
    cells = []
    for source in original_plan(seed)['cells']:
        if source['provider'] != 'kimi':
            continue
        cell = {**source, 'provider': provider, 'model': model, 'effort': effort}
        cell['id'] = f'{len(cells)+1:04d}-{provider}-{cell["language"]}-{cell["tests"]}-r{cell["replicate"]}'
        cells.append(cell)
    return dict(schema_version=3, purpose='exploratory_language_effort_followup',
                policy='terminal-status-v1', seed=seed, provider=provider,
                retention=RETENTION, scored_execution_qualified=False,
                order_basis='original_kimi_arm', cells=cells)


def validate_plan(plan):
    if not isinstance(plan, dict) or plan != make_plan(plan.get('provider'), plan.get('seed')):
        raise ValueError('plan differs from the complete exact 28-cell follow-up design')
    return plan['cells']


def run_matrix(plan_file, destination, *, qualification, resume=False, runner=None, binding=None):
    source = Path(plan_file)
    if source.stat().st_size > 1024 * 1024:
        raise ValueError('plan too large')
    plan = json.loads(source.read_text())
    validate_plan(plan)
    provider = plan['provider']
    if runner is None:
        if provider == 'codex':
            from .codex_subscriptions import run_codex
            runner = run_codex
        elif provider == 'claude':
            from .claude_subscriptions import run_claude
            runner = run_claude
        else:
            raise ValueError('no qualified adapter for target')
    return _run_matrix(source, destination, qualifications={provider: qualification},
                       resume=resume, runner=runner, binding=binding,
                       plan_validator=validate_plan, providers={provider: TARGETS[provider]},
                       kind='later_subscription_matrix')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('provider', choices=TARGETS)
    plan.add_argument('output', type=Path)
    plan.add_argument('--seed', type=int, default=20261010)
    run = commands.add_parser('run')
    run.add_argument('plan', type=Path)
    run.add_argument('output', type=Path)
    run.add_argument('--qualification', type=Path, required=True)
    run.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if args.command == 'plan':
        with args.output.open('x') as handle:
            json.dump(make_plan(args.provider, args.seed), handle, indent=2)
            handle.write('\n')
    else:
        state = run_matrix(args.plan, args.output, qualification=args.qualification, resume=args.resume)
        print(json.dumps({'state': state['state']}))
        return 1 if state['state'] == 'stopped_on_incident' else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
