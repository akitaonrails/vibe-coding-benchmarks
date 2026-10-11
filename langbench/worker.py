"""Disposable cgroup-limited offline worker; never bind a writable host directory."""
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
import time
from .core import copy_workspace, digest_tree, task_path, TASKS
from .process import execute

def reject_mounted_controller_assets(mounted_roots):
    private_roots=[Path(__file__).resolve().parent, *(task_path(task).resolve() for task in TASKS)]
    for private in private_roots:
        if any(private.is_relative_to(Path(mount).resolve()) for mount in mounted_roots):
            raise RuntimeError('controller or private task assets would be exposed through a runtime mount')

class DockerWorker:
    def __init__(self, source, *, image='alpine:3.22', runtime='historical', retention='legacy'):
        if retention not in ('legacy','seal-v1'):raise ValueError('unknown retention policy')
        self.retention=retention;self.admission_closed=False;self.retained_source=None;self.retention_receipt=None;self._retained_temp=None
        if runtime not in ('historical','seven'):
            raise ValueError('unknown worker runtime')
        self.runtime=runtime
        if runtime=='seven':
            from .core import ROOT
            config=ROOT/'configs/toolchain-seven.json'
            if not config.is_file():
                from importlib.resources import files
                config=files('langbench_config').joinpath('toolchain-seven.json')
            self.runtime_config=json.loads(config.read_text())
            image=self.runtime_config['image']
            if not image.startswith('sha256:') or len(image)!=71:
                raise RuntimeError('seven-language runtime requires immutable image ID')
        self.name = 'langbench-' + uuid.uuid4().hex
        self.alive = False
        self.image = None
        self.path = ['/usr/bin', '/bin']
        self.source = Path(source)
        if not shutil.which('docker'):
            raise RuntimeError('Docker unavailable; isolated execution refused')
        result=execute(['docker','image','inspect',image,'--format','{{.Id}}'])
        image_id=result['stdout'].strip()
        if result['returncode'] or not image_id.startswith('sha256:') or len(image_id)!=71:
            raise RuntimeError('required local worker image unavailable; no automatic network pull')
        self.image=image_id
        args=['docker','run','--detach','--init','--name',self.name,'--read-only','--network','none',
              '--cap-drop','ALL','--security-opt','no-new-privileges','--memory','4g','--memory-swap','4g',
              '--pids-limit','64','--cpus','2', '--tmpfs','/workspace:rw,exec,nosuid,nodev,size=536870912',
              '--tmpfs','/tmp:rw,exec,nosuid,nodev,size=67108864', '--tmpfs','/cargo:rw,nosuid,nodev,size=134217728',
              '--workdir','/workspace','--env','HOME=/tmp','--env','CARGO_HOME=/cargo','--env','CARGO_NET_OFFLINE=true',
              '--env','LANG=C.UTF-8']
        mounted_roots=[]
        if runtime=='historical':
            for host, guest in [('/usr','/usr'),('/usr/bin','/bin'),('/usr/lib','/lib'),('/usr/lib','/lib64')]:
                mounted_roots.append(Path(host).resolve())
                args += ['--mount',f'type=bind,src={host},dst={guest},readonly']
            for program in ('ruby','rustc'):
                binary=shutil.which(program)
                if not binary:
                    raise RuntimeError(f'required runtime unavailable: {program}')
                resolved=Path(binary).resolve()
                if program=='rustc':
                    query=execute([binary,'--print','sysroot'])
                    if query['returncode']:
                        raise RuntimeError('cannot resolve Rust sysroot')
                    install=Path(query['stdout'].strip()).resolve()
                else:
                    install=resolved.parent.parent
                if not str(install).startswith('/usr'):
                    mounted_roots.append(install)
                    args += ['--mount',f'type=bind,src={install},dst={install},readonly']
                    self.path.insert(0,str(install/'bin'))
            registry=Path.home()/'.cargo/registry'
            if registry.is_dir():
                mounted_roots.append(registry.resolve())
                args += ['--mount',f'type=bind,src={registry},dst=/cargo/registry,readonly']
        reject_mounted_controller_assets(mounted_roots)
        if runtime=='seven':
            args += ['--env','CARGO_HOME=/opt/cargo','--env','DOTNET_CLI_HOME=/tmp','--env','NUGET_PACKAGES=/tmp/nuget']
        args += ['--env','PATH='+':'.join(self.path),'--entrypoint','/usr/bin/sleep',self.image,'infinity']
        started=execute(args,timeout=30)
        if started['returncode']:
            execute(['docker','rm','--force',self.name])
            raise RuntimeError('worker startup failed: '+started['stderr'][:500])
        self.alive=True
        try:
            supervisor=self.raw(['/usr/bin/python3','-I','-c',
                "import pathlib; children=pathlib.Path('/proc/1/task/1/children').read_text().split(); "
                "assert len(children)==1; pid=int(children[0]); "
                "assert pathlib.Path('/proc/'+str(pid)+'/exe').resolve()==pathlib.Path('/usr/bin/sleep'); print(pid)"])
            if supervisor['returncode']:
                raise RuntimeError('cannot identify trusted worker supervisor')
            self.supervisor_pid=int(supervisor['stdout'].strip())
            digest_tree(source,ignore_root_artifacts=True)
            with tempfile.TemporaryDirectory(prefix='langbench-stage-') as temp:
                staged=Path(temp)/'workspace';copy_workspace(source,staged)
                entries=[]
                for file in staged.rglob('*'):
                    entries.append({'path':file.relative_to(staged).as_posix(), 'mode':file.stat().st_mode & 0o777,
                                    'directory':file.is_dir(), 'data':base64.b64encode(file.read_bytes()).decode() if file.is_file() else None})
                stage_script = """import json,sys,pathlib,base64
for entry in json.load(sys.stdin):
 p=pathlib.Path('/workspace')/entry['path']
 if entry['directory']:p.mkdir(parents=True,exist_ok=True)
 else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(base64.b64decode(entry['data']))
 p.chmod(entry['mode'])
"""
                copied=self.raw(['/usr/bin/python3','-I','-c',stage_script],stdin=json.dumps(entries),timeout=30)
                if copied['returncode']:
                    raise RuntimeError('worker staging failed: '+copied['stderr'][:500])
            self.qualification=self.qualify()
            if self.retention!='legacy':self.qualification['artifact_retention_policy']=self.retention
        except Exception:
            self.close()
            raise

    def raw(self, argv, *, stdin='', timeout=30, output_limit=4*1024*1024, retain_timeout=False):
        if not self.alive:
            raise RuntimeError('worker retired')
        result=execute(['docker','exec','-i',self.name,*argv],stdin=stdin,timeout=timeout,output_limit=output_limit)
        if result['termination'] and not (retain_timeout and result['termination']=='timeout'):
            self.close()
        return result

    def execute(self, command, *, stdin='', timeout=30, output_limit=4*1024*1024):
        if self.admission_closed:raise RuntimeError('candidate admission closed')
        argv=['/usr/bin/sh','-c',command] if isinstance(command,str) else command
        command_started=time.monotonic()
        result=self.raw(argv,stdin=stdin,timeout=timeout,output_limit=output_limit,retain_timeout=self.retention=='seal-v1')
        timed_out=result['termination']=='timeout' and self.retention=='seal-v1'
        if timed_out:
            self.admission_closed=True
            self.retention_receipt={'policy':'seal-v1','cutoff_monotonic':command_started+timeout,'timeout_observed_monotonic':time.monotonic(),'artifact_available':False}
        if self.alive:
            # No candidate process may survive the command or drift a snapshot.
            cleanup=self.raw(['/usr/bin/python3','-I','-c',
                '''import os,signal,time,sys
me=os.getpid()
supervisor=int(sys.argv[1])
for attempt in range(3):
 for p in os.listdir('/proc'):
  if p.isdigit() and int(p) not in (1,me,supervisor):
   try:os.kill(int(p),signal.SIGKILL)
   except ProcessLookupError:pass
 time.sleep(.01)
for p in os.listdir('/proc'):
 if p.isdigit() and int(p) not in (1,me,supervisor):
  try:
   state=open('/proc/'+p+'/stat').read().split(') ')[1].split()[0]
   if state!='Z':raise RuntimeError('candidate process survived cleanup')
  except FileNotFoundError:pass
''',str(self.supervisor_pid)],timeout=5)
            if cleanup['returncode'] or cleanup.get('termination'):
                self.close()
                result['cleanup_error']='candidate_cleanup_failed'
                if not timed_out:result['termination']='cleanup_failed'
            elif timed_out:
                self.retention_receipt['writers_stopped_monotonic']=time.monotonic()
                self._seal_source()
        if timed_out:
            result['artifact_retention']=self.retention_receipt
            self.close()
        return result

    def _seal_source(self):
        # Only called after candidate writers are stopped or proven already quiescent.
        self.admission_closed=True
        if self.retention_receipt is None:
            now=time.monotonic()
            self.retention_receipt={'policy':'seal-v1','cutoff_monotonic':now,'writers_stopped_monotonic':now,'artifact_available':False}
        try:
            self._retained_temp=tempfile.TemporaryDirectory(prefix='langbench-sealed-')
            target=Path(self._retained_temp.name)/'source'
            self.export(target,source_only=True)
            if not (target/'src').is_dir():raise ValueError('missing submitted source')
            self.retained_source=target
            sealed=time.monotonic()
            self.retention_receipt.update(artifact_available=True,source_sha256=digest_tree(target/'src'),
                sealed_monotonic=sealed,seal_lag_seconds=sealed-self.retention_receipt['cutoff_monotonic'])
        except Exception as error:
            self.retained_source=None
            self.retention_receipt['error_type']=type(error).__name__
        return self.retention_receipt

    def seal_quiescent(self):
        if self.retention!='seal-v1':raise RuntimeError('sealing is not enabled')
        if self.retained_source is not None:return self.retention_receipt
        if not self.alive:return self.retention_receipt
        return self._seal_source()

    def qualify(self):
        script='''import json,pathlib,socket,importlib.util
p=pathlib.Path('/sys/fs/cgroup')
r={k:(p/k).read_text().strip() for k in ('memory.max','memory.swap.max','pids.max','cpu.max')}
r['mounts']=pathlib.Path('/proc/mounts').read_text()
r['controller_assets_visible']=any(importlib.util.find_spec(name) is not None for name in ('langbench','langbench_tasks'))
s=socket.socket();s.settimeout(.1)
try:s.connect(('1.1.1.1',53));r['network_blocked']=False
except OSError:r['network_blocked']=True
finally:s.close()
print(json.dumps(r))'''
        result=self.raw(['/usr/bin/python3','-I','-c',script])
        if result['returncode']:
            raise RuntimeError('cannot inspect worker resource boundary')
        info=json.loads(result['stdout'])
        if info.get('controller_assets_visible') is not False:
            raise RuntimeError('controller or private task package is visible in the worker runtime')
        if info['memory.max']!='4294967296' or info['memory.swap.max']!='0' or info['pids.max']!='64' or info['cpu.max']!='200000 100000' or not info['network_blocked']:
            raise RuntimeError('worker resource/network limits did not match requested policy')
        mounts=info.pop('mounts')
        for name, size in (('/workspace','size=524288k'),('/tmp','size=65536k'),('/cargo','size=131072k')):
            if not any(line.split()[1:3]==[name,'tmpfs'] and size in line for line in mounts.splitlines()):
                raise RuntimeError('worker temporary filesystem limits not verified')
        info.update({'runtime':self.runtime,'image':self.image,'workspace_bytes':536870912,'tmp_bytes':67108864,'cargo_bytes':134217728})
        if self.runtime=='seven':
            check=self.raw(['/usr/bin/sha256sum','/opt/toolchain-packages.lock'])
            if check['returncode'] or check['stdout'].split()[0]!=self.runtime_config['packages_sha256']:
                raise RuntimeError('toolchain package inventory mismatch')
            info['packages_sha256']=self.runtime_config['packages_sha256']
        return info

    def export(self, destination, *, source_only=False):
        """Export only bounded regular files; validate serialized paths before writes."""
        script='''import os,json,base64,stat,sys
source_only=sys.argv[1]=='1'
root='/workspace';out=[];size=0;count=0
for directory,dirs,files in os.walk(root,followlinks=False):
 if directory==root:
  if source_only:dirs[:]=[d for d in dirs if d=='src'];files=[]
  else:dirs[:]=[d for d in dirs if d not in ('target','.git','__pycache__')];files=[f for f in files if f not in ('target','.git','__pycache__')]
 for name in dirs+files:
  p=os.path.join(directory,name);s=os.lstat(p);count+=1
  if count>10000 or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise ValueError('invalid export')
  if source_only and stat.S_ISREG(s.st_mode) and s.st_nlink!=1:raise ValueError('source hardlink rejected')
  size+=s.st_size if stat.S_ISREG(s.st_mode) else 0
  if size>10485760:raise ValueError('export exceeds size bound')
  out.append({'path':os.path.relpath(p,root),'mode':stat.S_IMODE(s.st_mode),'directory':stat.S_ISDIR(s.st_mode),'data':base64.b64encode(open(p,'rb').read()).decode() if stat.S_ISREG(s.st_mode) else None})
print(json.dumps(out))'''
        result=self.raw(['/usr/bin/python3','-I','-c',script,'1' if source_only else '0'],output_limit=16*1024*1024)
        if result['returncode'] or result['termination']:
            raise ValueError('worker export rejected invalid or oversized artifact')
        entries=json.loads(result['stdout'])
        target=Path(destination)
        target.mkdir(parents=True,exist_ok=False)
        for entry in entries:
            path=PurePosixPath(entry['path'])
            if path.is_absolute() or '..' in path.parts or not path.parts:
                raise ValueError('invalid export path')
            file=target.joinpath(*path.parts)
            if entry['directory']:
                file.mkdir(parents=True,exist_ok=True)
            else:
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_bytes(base64.b64decode(entry['data'],validate=True))
            file.chmod(entry['mode'] & 0o777)
        return digest_tree(target,ignore_root_artifacts=True)

    def close(self):
        if self.alive:
            if self.retention=='seal-v1':
                removed=execute(['docker','rm','--force',self.name],timeout=15)
                if removed['returncode'] or removed.get('termination'):
                    raise RuntimeError('terminal worker removal unverified')
                self.alive=False
            else:
                self.alive=False
                execute(['docker','rm','--force',self.name],timeout=15)

    def __enter__(self):return self
    def __exit__(self,*args):
        self.close()
        if self._retained_temp is not None:self._retained_temp.cleanup()
