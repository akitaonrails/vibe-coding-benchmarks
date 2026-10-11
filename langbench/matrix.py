"""Frozen, resumable subscription matrix; never retries a consumed attempt."""
from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path
import random
import time

from .core import LANGUAGES, digest_tree, scaffold, task_path

PROVIDERS = {'kimi': ('kimi-code/k3', 'high'), 'opencode': ('zai/glm-5.3', 'high')}
POLICY = 'terminal-status-v1'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_plan(seed=20261010):
    if type(seed) is not int or seed < 0:
        raise ValueError('invalid seed')
    cells = []
    for replicate, language, condition, provider in itertools.product(
            (1, 2), LANGUAGES, ('T0', 'T1'), PROVIDERS):
        model, effort = PROVIDERS[provider]
        cells.append(dict(task='ledger_engine', language=language, tests=condition,
                          provider=provider, model=model, effort=effort, replicate=replicate,
                          semantic_seed=20261010 + replicate - 1,
                          block_id=f'ledger-subscriptions:{replicate}', base_seconds=900,
                          continuation_seconds=180, max_nudges=2))
    random.Random(seed).shuffle(cells)
    for index, cell in enumerate(cells):
        cell['id'] = f'{index + 1:04d}-{cell["provider"]}-{cell["language"]}-{cell["tests"]}-r{cell["replicate"]}'
    return dict(schema_version=2, purpose='exploratory_language_effort', policy=POLICY,
                seed=seed, scored_execution_qualified=False, cells=cells)


def validate_plan(plan):
    # Exact generation prevents omitted hard cells, duplicate attempts or changed budgets.
    if not isinstance(plan, dict) or plan != make_plan(plan.get('seed')):
        raise ValueError('plan differs from the complete frozen 56-cell design')
    return plan['cells']


def input_binding():
    """Bind semantic assets and implementation, excluding generated build files."""
    task = task_path('ledger_engine')
    assets = {name: sha256(task / name) for name in ('CONTRACT.md', 'cases.py', 'task.json')}
    for language in LANGUAGES:
        for kind in ('starter', 'reference'):
            assets[f'{kind}/{language}'] = digest_tree(scaffold('ledger_engine', language, kind),
                                                      ignore_root_artifacts=True)
    assets['harness'] = {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    return assets


def _atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def run_matrix(plan_file, destination, *, qualifications, resume=False, runner=None, binding=None):
    return _run_matrix(plan_file, destination, qualifications=qualifications,
                       resume=resume, runner=runner, binding=binding,
                       plan_validator=validate_plan, providers=PROVIDERS,
                       kind='subscription_matrix')


def _run_matrix(plan_file, destination, *, qualifications, resume=False, runner=None,
                binding=None, plan_validator, providers, kind):
    """Run remaining cells once. Resume never reopens started/finished attempts.

    Qualifications are provider -> receipt path. Provider validates its own live
    binding before inference. No automatic qualification or external repair loop.
    """
    source = Path(plan_file)
    if source.stat().st_size > 1024 * 1024:
        raise ValueError('plan too large')
    raw = source.read_bytes()
    plan = json.loads(raw)
    cells = plan_validator(plan)
    if set(qualifications) != set(providers):
        raise ValueError('exact design provider qualification receipts required')
    qualification_data = {}
    qualification_hashes = {}
    for provider, path in qualifications.items():
        data = json.loads(Path(path).read_text())
        if data.get('passed') is not True:
            raise ValueError(f'{provider} qualification has not passed')
        qualification_data[provider] = data
        qualification_hashes[provider] = sha256(path)
    frozen_inputs = input_binding() if binding is None else binding
    output = Path(destination).absolute()
    plan_hash = hashlib.sha256(raw).hexdigest()
    if resume:
        state = json.loads((output / 'matrix.json').read_text())
        if (state.get('kind') != kind or state['plan_sha256'] != plan_hash or sha256(output / 'plan.json') != plan_hash
                or state['qualification_sha256'] != qualification_hashes
                or state['input_binding'] != frozen_inputs):
            raise ValueError('frozen plan or qualification changed')
        if [item['id'] for item in state['cells']] != [item['id'] for item in cells]:
            raise ValueError('progress cell identities changed')
        for item in state['cells']:
            if item.get('result_sha256') and sha256(output / item['id'] / 'result.json') != item['result_sha256']:
                raise ValueError('preserved result changed')
            if item['state'] == 'running':
                item['state'] = 'interrupted_unknown'
                item['reason'] = 'Previous controller stopped; no automatic retry or replacement.'
    else:
        output.mkdir(parents=True, exist_ok=False)
        (output / 'plan.json').write_bytes(raw)
        state = dict(schema_version=2, kind=kind, plan_sha256=plan_hash,
                     qualification_sha256=qualification_hashes, input_binding=frozen_inputs, state='running',
                     execution='sequential', blocked_providers=[],
                     cells=[dict(id=c['id'], state='pending') for c in cells])
        for provider, data in qualification_data.items():
            _atomic_json(output / f'qualification-{provider}.json', data)

    def persist(event):
        with (output / 'progress.jsonl').open('a') as handle:
            handle.write(json.dumps(dict(time=time.time(), **event), sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        _atomic_json(output / 'matrix.json', state)

    persist(dict(event='resumed' if resume else 'frozen'))
    if runner is None:
        from .subscriptions import run_subscription
        runner = run_subscription
    state['state'] = 'running'
    for cell, item in zip(cells, state['cells']):
        if item['state'] != 'pending':
            continue
        provider = cell['provider']
        if provider in state['blocked_providers']:
            item.update(state='not_run_quota', reason='Provider exhausted allowance in earlier frozen cell.')
            persist(dict(event='not_run_quota', id=cell['id']))
            continue
        attempt = output / cell['id']
        if attempt.exists():
            raise ValueError('pending attempt directory exists; reconcile without rerunning inference')
        item['state'] = 'running'
        persist(dict(event='started', id=cell['id']))
        kwargs = {key: cell[key] for key in ('provider', 'model', 'effort', 'tests', 'replicate',
                                             'block_id', 'base_seconds', 'continuation_seconds')}
        kwargs.update(seed=cell['semantic_seed'], qualification=qualification_data[provider])
        try:
            result = runner(cell['task'], cell['language'], attempt, **kwargs)
            if not isinstance(result, dict):
                raise ValueError('invalid runner receipt')
        except KeyboardInterrupt:
            item.update(state='interrupted_unknown', reason='Interrupted; retained without automatic retry.')
            state['state'] = 'interrupted'
            persist(dict(event='interrupted', id=cell['id']))
            return state
        except Exception as exc:
            # Avoid exception strings: transports may embed credentials in errors.
            result = dict(validity='infrastructure_invalid', error_type=type(exc).__name__)
        attempt.mkdir(exist_ok=True)
        result_path = attempt / 'result.json'
        if not result_path.exists():
            _atomic_json(result_path, result)
        else:
            # Persisted adapter receipt is the authoritative result.
            result = json.loads(result_path.read_text())
        collection = result.get('collection') or result.get('partial_collection') or {}
        quota = any(i.get('status') == 'quota' for i in collection.get('invocations', []))
        quota = quota or result.get('validity') == 'quota'
        item.update(state='quota' if quota else 'collected', validity=result.get('validity', 'unknown'),
                    result_sha256=sha256(result_path))
        if quota:
            state['blocked_providers'].append(provider)
        elif item['validity'] != 'valid_development':
            item['state'] = 'infrastructure_invalid'
            state['state'] = 'stopped_on_incident'
            persist(dict(event='incident', id=cell['id']))
            return state
        persist(dict(event='collected', id=cell['id'], state=item['state']))
    state['state'] = 'complete' if all(i['state'] == 'collected' for i in state['cells']) else 'closed_with_missing_cells'
    persist(dict(event='closed', state=state['state']))
    return state
