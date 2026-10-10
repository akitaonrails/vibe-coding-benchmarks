from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
LANGUAGES = ('rust', 'haskell', 'csharp', 'kotlin', 'typescript', 'python', 'ruby')
IMPLEMENTED = LANGUAGES
TASKS = ('crash_store', 'protocol_migration', 'ledger_engine')

def task_path(task):
    if task not in TASKS:
        raise ValueError('unknown task')
    checkout = ROOT / 'tasks' / task
    if checkout.is_dir():
        return checkout
    from importlib.resources import files
    return Path(str(files('langbench_tasks').joinpath(task)))

BUILD_ARTIFACTS = frozenset(('target', '__pycache__', '.git'))

def copy_workspace(source, destination):
    """Omit only workspace-root build artifacts; src is always preserved."""
    root = Path(source).absolute()
    def ignore(directory, names):
        return BUILD_ARTIFACTS.intersection(names) if Path(directory).absolute() == root else set()
    return shutil.copytree(source, destination, ignore=ignore)

def digest_tree(path, *, ignore_root_artifacts=False):
    path = Path(path)
    result = {}
    total_bytes = 0
    entries = 0
    for directory, dirs, files in os.walk(path, followlinks=False):
        directory = Path(directory)
        if ignore_root_artifacts and directory == path:
            dirs[:] = [name for name in dirs if name not in BUILD_ARTIFACTS]
            files = [name for name in files if name not in BUILD_ARTIFACTS]
        for name in sorted(dirs + files):
            file = directory / name
            entries += 1
            if entries > 10000:
                raise ValueError('too many submission entries')
            if file.is_symlink():
                raise ValueError(f'symlinks forbidden: {file}')
            if file.is_file():
                total_bytes += file.stat().st_size
                if total_bytes > 10 * 1024 * 1024:
                    raise ValueError('artifact exceeds 10 MiB limit')
                result[file.relative_to(path).as_posix()] = {'type':'file', 'mode':file.stat().st_mode & 0o777, 'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
            elif file.is_dir():
                result[file.relative_to(path).as_posix()] = {'type':'directory', 'mode':file.stat().st_mode & 0o777}
            else:
                raise ValueError('special files forbidden')
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()

def cases(task, suite, seed=0):
    if suite not in ('public', 'private') or type(seed) is not int or seed < 0:
        raise ValueError('invalid case selector')
    spec = importlib.util.spec_from_file_location(f'langbench_cases_{task}', task_path(task) / 'cases.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cases(suite, seed=seed)

def supported_languages(task):
    return tuple(json.loads((task_path(task)/'task.json').read_text())['languages'])

def scaffold(task, language, kind='starter'):
    if language not in supported_languages(task) or kind not in ('starter', 'reference'):
        raise ValueError('unsupported language or scaffold')
    return task_path(task) / {'starter':'starters','reference':'references'}[kind] / language

def prepare(task, language, condition, destination):
    if condition not in ('T0', 'T1'):
        raise ValueError('tests must be T0 or T1')
    target = Path(destination).absolute()
    if target.exists():
        raise ValueError('attempt destination already exists; use a clean directory')
    source = scaffold(task, language)
    digest_tree(source, ignore_root_artifacts=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    copy_workspace(source, target)
    shutil.copyfile(task_path(task) / 'CONTRACT.md', target / 'TASK.md')
    if condition == 'T1':
        (target / 'public_cases.json').write_text(json.dumps(cases(task, 'public'), indent=2) + '\n')
        shutil.copyfile(ROOT / 'langbench' / 'public_driver.py', target / 'test_public.py')
    manifest = {'kind': 'preparation_receipt', 'schema_version': 1, 'task': task, 'language': language, 'tests': condition,
                'initial_artifact_sha256': digest_tree(target, ignore_root_artifacts=True),
                'contract_sha256': hashlib.sha256((target / 'TASK.md').read_bytes()).hexdigest(),
                'allowed_submission_paths': ['src/'], 'model_resolved': None}
    manifest_path = target.with_name(target.name + '.manifest.json')
    try:
        with manifest_path.open('x') as handle:
            json.dump(manifest, handle, indent=2)
            handle.write('\n')
    except Exception:
        shutil.rmtree(target)
        raise
    return manifest

def validate_source(source):
    source = Path(source)
    if source.is_symlink() or not source.is_dir():
        raise ValueError('submission must be a real directory')
    # Validate the entire submitted tree, including unused scaffold paths.
    digest_tree(source, ignore_root_artifacts=True)
    src = source / 'src'
    if not src.is_dir():
        raise ValueError('submission requires src/')
    for entry in src.rglob('*'):
        if entry.is_symlink() or not (entry.is_dir() or entry.is_file()):
            raise ValueError('source symlinks and special files forbidden')
    if sum(p.stat().st_size for p in src.rglob('*') if p.is_file()) > 5 * 1024 * 1024:
        raise ValueError('source exceeds 5 MiB limit')
    return src
