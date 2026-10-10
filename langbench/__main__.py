import argparse
import json
from pathlib import Path
from .core import TASKS, LANGUAGES, IMPLEMENTED, prepare, scaffold
from .grading import grade
from .report import summarize
from .appserver import DEFAULT_BINARY

def main():
    parser = argparse.ArgumentParser(description='Language benchmark qualification harness')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    p = sub.add_parser('plan')
    p.add_argument('--seed', type=int, default=20261010)
    p.add_argument('--purpose', choices=('calibration','smoke'))
    p.add_argument('--config', type=Path)
    p = sub.add_parser('prepare')
    p.add_argument('task', choices=TASKS)
    p.add_argument('language', choices=IMPLEMENTED)
    p.add_argument('destination', type=Path)
    p.add_argument('--tests', choices=('T0','T1'), default='T0')
    p = sub.add_parser('grade')
    p.add_argument('task', choices=TASKS)
    p.add_argument('language', choices=IMPLEMENTED)
    p.add_argument('source', type=Path)
    p.add_argument('--suite', choices=('public','private'), default='private')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--backend', choices=('docker','sandbox','trusted-reference'), default='docker')
    p = sub.add_parser('selftest')
    p.add_argument('--backend', choices=('docker','sandbox','trusted-reference'), default='docker')
    p = sub.add_parser('report')
    p.add_argument('results', type=Path, nargs='+')
    p = sub.add_parser('qualify')
    p.add_argument('destination', type=Path)
    p.add_argument('--model', default='gpt-6-luna')
    p.add_argument('--effort', choices=('low','medium','high'), default='high')
    p.add_argument('--seconds', type=int, default=90)
    p.add_argument('--binary', type=Path, default=DEFAULT_BINARY)
    p = sub.add_parser('run')
    p.add_argument('task', choices=TASKS)
    p.add_argument('language', choices=IMPLEMENTED)
    p.add_argument('destination', type=Path)
    p.add_argument('--tests', choices=('T0','T1'), default='T1')
    p.add_argument('--model', default='gpt-6-luna')
    p.add_argument('--effort', choices=('low','medium','high'), default='high')
    p.add_argument('--base-seconds', type=int, default=180)
    p.add_argument('--continuation-seconds', type=int, default=60)
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--replicate', type=int, default=1)
    p.add_argument('--block-id', default='development-smoke')
    p.add_argument('--binary', type=Path, default=DEFAULT_BINARY)
    p = sub.add_parser('batch')
    p.add_argument('plan', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('--limit', type=int)
    p.add_argument('--binary', type=Path, default=DEFAULT_BINARY)
    p = sub.add_parser('size')
    p.add_argument('task', choices=TASKS)
    p.add_argument('language', choices=IMPLEMENTED)
    p.add_argument('--result', type=Path)
    p = sub.add_parser('calibration-report')
    p.add_argument('results', type=Path, nargs='+')
    args = parser.parse_args()
    if args.command == 'list':
        result = {'languages':LANGUAGES, 'implemented_languages':IMPLEMENTED, 'tasks':TASKS}
    elif args.command == 'plan':
        import random
        from importlib.resources import files
        purpose=args.purpose or 'calibration'
        filename='ruby-rust-pilot.json' if purpose=='smoke' else 'ledger-engine-calibration.json'
        config_path=args.config or Path(__file__).resolve().parent.parent / 'configs' / filename
        if args.config is None and not config_path.is_file():
            config_path = files('langbench_config').joinpath(filename)
        config = json.loads(config_path.read_text())
        purpose=config.get('purpose','smoke') if args.config is not None and args.purpose is None else purpose
        if config.get('purpose',purpose)!=purpose:raise ValueError('config purpose differs from requested purpose')
        cells = []
        for replicate in range(1, config['replicates'] + 1):
            for task in config['tasks']:
                for tests in config['test_conditions']:
                    block = f"{config['block_prefix']}:{task}:{replicate}"
                    for lang in config['languages']:
                        for model in config['models']:
                            cells.append({'task': task, 'language': lang, 'tests': tests,
                                          'model': model['requested'], 'effort': model['effort'],
                                          'replicate': replicate, 'block_id': block,
                                          'semantic_seed': config['semantic_seed_base'] + replicate - 1,
                                          'base_seconds': config['base_seconds'],
                                          'continuation_seconds': config['continuation_seconds_each'],
                                          'max_nudges': config['max_nudges'], 'auth_mode': config['auth_mode']})
        random.Random(args.seed).shuffle(cells)
        result = {'schema_version': 1, 'seed': args.seed, 'purpose':purpose,
                  'scored_execution_qualified': config['scored_execution_qualified'], 'cells': cells}
    elif args.command == 'prepare':
        result = prepare(args.task,args.language,args.tests,args.destination)
    elif args.command == 'grade':
        result = grade(args.task,args.language,args.source,args.suite,args.seed,args.backend)
    elif args.command == 'selftest':
        result = [grade(task,lang,scaffold(task,lang,'reference'),backend=args.backend)
                  for task in TASKS for lang in IMPLEMENTED]
    elif args.command == 'qualify':
        from .live import qualify
        result = qualify(args.destination,args.model,args.effort,args.seconds,args.binary)
    elif args.command == 'run':
        from .live import run
        result = run(args.task,args.language,args.destination,tests=args.tests,model=args.model,effort=args.effort,
                     base_seconds=args.base_seconds,continuation_seconds=args.continuation_seconds,
                     seed=args.seed,replicate=args.replicate,block_id=args.block_id,binary=args.binary)
    elif args.command == 'batch':
        from .batch import batch
        result = batch(args.plan,args.destination,limit=args.limit,binary=args.binary)
    elif args.command == 'size':
        from .size import measure
        result = measure(args.task,args.language,args.result)
    elif args.command == 'calibration-report':
        from .difficulty import calibrate
        result = calibrate([json.loads(path.read_text()) for path in args.results])
    else:
        result = summarize([json.loads(path.read_text()) for path in args.results])
    print(json.dumps(result, indent=2))
    if args.command == 'grade' and not result['success']:
        return 1
    if args.command == 'selftest' and not all(row['success'] for row in result):
        return 1
    if args.command == 'qualify' and not result['passed']:
        return 1
    if args.command == 'run' and result['validity'] != 'valid_smoke':
        return 1
    if args.command == 'batch' and result['state'] != 'complete':
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
