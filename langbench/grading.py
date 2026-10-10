from pathlib import Path
from contextlib import ExitStack
import json
import os
import shutil
import tempfile
from .core import cases, scaffold, task_path, validate_source, digest_tree, copy_workspace
from .process import execute
from .public_driver import same_json
from .worker import DockerWorker

def sandbox_command(command, workspace):
    if not shutil.which('bwrap'):
        raise RuntimeError('bubblewrap unavailable; refusing unisolated candidate execution')
    argv = ['bwrap', '--die-with-parent', '--unshare-all', '--new-session', '--cap-drop', 'ALL', '--clearenv',
            '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/tmp', '--setenv', 'LANG', 'C.UTF-8',
            '--ro-bind', '/usr', '/usr', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    for path in ('/bin', '/lib', '/lib64'):
        if Path(path).exists():
            argv += ['--ro-bind', path, path]
    # Runtime installations are read-only, never mount the entire home.
    path_parts = ['/usr/bin', '/bin']
    for program in ('ruby', 'rustc'):
        binary = shutil.which(program)
        if not binary:
            continue
        resolved = Path(binary).resolve()
        if str(resolved).startswith('/usr/'):
            continue
        if program == 'ruby':
            install = resolved.parent.parent
            argv += ['--ro-bind', str(install), str(install)]
            path_parts.insert(0, str(install / 'bin'))
        else:
            result = execute([binary, '--print', 'sysroot'])
            if result['returncode'] != 0:
                raise RuntimeError('cannot resolve Rust toolchain')
            install = Path(result['stdout'].strip()).resolve()
            argv += ['--ro-bind', str(install), str(install)]
            path_parts.insert(0, str(install / 'bin'))
    registry = Path.home() / '.cargo' / 'registry'
    if registry.is_dir():
        argv += ['--dir', '/cargo', '--ro-bind', str(registry), '/cargo/registry', '--setenv', 'CARGO_HOME', '/cargo', '--setenv', 'CARGO_NET_OFFLINE', 'true']
    argv += ['--setenv', 'PATH', ':'.join(path_parts), '--bind', str(workspace), '/workspace', '--chdir', '/workspace', '--']
    return argv + command

def grade(task, language, source, suite='private', seed=0, backend='docker'):
    if backend not in ('docker', 'sandbox', 'trusted-reference'):
        raise ValueError('unknown grading backend')
    src = validate_source(source)
    if backend == 'trusted-reference' and Path(source).resolve() != scaffold(task, language, 'reference').resolve():
        raise ValueError('local execution is restricted to the repository reference')
    selected = cases(task, suite, seed)
    metadata = json.loads((task_path(task) / 'task.json').read_text())
    with tempfile.TemporaryDirectory(prefix='langbench-grade-') as temp, ExitStack() as stack:
        workspace = Path(temp) / 'workspace'
        copy_workspace(scaffold(task, language), workspace)
        shutil.rmtree(workspace / 'src')
        shutil.copytree(src, workspace / 'src')
        worker=stack.enter_context(DockerWorker(workspace)) if backend == 'docker' else None
        def run(command, stdin='', timeout=10):
            if worker is not None:
                return worker.execute(command,stdin=stdin,timeout=timeout)
            argv = sandbox_command(command, workspace) if backend == 'sandbox' else command
            return execute(argv, cwd=workspace, stdin=stdin, timeout=timeout)
        build = run(['sh', 'build.sh'], timeout=metadata.get('build_timeout_seconds',120))
        outcomes = []
        if build['returncode'] == 0 and build['termination'] is None:
            for case in selected:
                result = run(['sh', 'run.sh'], ''.join(json.dumps(r)+'\n' for r in case['requests']), timeout=metadata.get('case_timeout_seconds',5))
                try:
                    actual = [json.loads(line) for line in result['stdout'].splitlines()]
                    passed = result['returncode'] == 0 and result['termination'] is None and same_json(actual, case['expected'])
                except (ValueError, TypeError):
                    passed = False
                outcomes.append({'id':case['id'], 'group':case['group'], 'passed':passed,
                                 'returncode':result['returncode'], 'termination':result['termination']})
                if worker is not None and not worker.alive:
                    break
        groups = {group: all(o['passed'] for o in outcomes if o['group']==group) and any(o['group']==group for o in outcomes)
                  for group in {case['group'] for case in selected}}
        return {'schema_version':1, 'task':task, 'language':language, 'suite':suite, 'seed':seed,
                'source_sha256':digest_tree(src), 'backend':backend,
                'validity':('valid' if backend=='docker' else 'unqualified_local_reference' if backend=='trusted-reference' else 'unqualified_development_sandbox'),
                'environment':worker.qualification if worker else {'resource_isolation_qualified':False},
                'success':bool(outcomes) and len(outcomes)==len(selected) and all(o['passed'] for o in outcomes),
                'critical_failures':[g for g in metadata['critical_groups'] if g in groups and not groups[g]],
                'groups':groups, 'cases':outcomes, 'build':build}
