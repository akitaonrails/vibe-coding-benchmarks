"""Disposable cgroup-limited offline worker; never bind a writable host directory."""
import base64
import json
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import uuid
from .core import copy_workspace, digest_tree, task_path, TASKS
from .process import execute

def reject_mounted_controller_assets(mounted_roots):
    private_roots=[Path(__file__).resolve().parent, *(task_path(task).resolve() for task in TASKS)]
    for private in private_roots:
        if any(private.is_relative_to(Path(mount).resolve()) for mount in mounted_roots):
            raise RuntimeError('controller or private task assets would be exposed through a runtime mount')

class DockerWorker:
    def __init__(self, source, *, image='alpine:3.22'):
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
        except Exception:
            self.close()
            raise

    def raw(self, argv, *, stdin='', timeout=30, output_limit=4*1024*1024):
        if not self.alive:
            raise RuntimeError('worker retired')
        result=execute(['docker','exec','-i',self.name,*argv],stdin=stdin,timeout=timeout,output_limit=output_limit)
        if result['termination']:
            self.close()
        return result

    def execute(self, command, *, stdin='', timeout=30, output_limit=4*1024*1024):
        argv=['/usr/bin/sh','-c',command] if isinstance(command,str) else command
        result=self.raw(argv,stdin=stdin,timeout=timeout,output_limit=output_limit)
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
            if cleanup['returncode']:
                self.close()
                result['termination']='cleanup_failed'
        return result

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
        info.update({'image':self.image,'workspace_bytes':536870912,'tmp_bytes':67108864,'cargo_bytes':134217728})
        return info

    def export(self, destination):
        """Export only bounded regular files; validate serialized paths before writes."""
        script='''import os,json,base64,stat
root='/workspace';out=[];size=0;count=0
for directory,dirs,files in os.walk(root,followlinks=False):
 if directory==root:dirs[:]=[d for d in dirs if d not in ('target','.git','__pycache__')];files=[f for f in files if f not in ('target','.git','__pycache__')]
 for name in dirs+files:
  p=os.path.join(directory,name);s=os.lstat(p);count+=1
  if count>10000 or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise ValueError('invalid export')
  size+=s.st_size if stat.S_ISREG(s.st_mode) else 0
  if size>10485760:raise ValueError('export exceeds size bound')
  out.append({'path':os.path.relpath(p,root),'mode':stat.S_IMODE(s.st_mode),'directory':stat.S_ISDIR(s.st_mode),'data':base64.b64encode(open(p,'rb').read()).decode() if stat.S_ISREG(s.st_mode) else None})
print(json.dumps(out))'''
        result=self.raw(['/usr/bin/python3','-I','-c',script],output_limit=16*1024*1024)
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
            self.alive=False
            execute(['docker','rm','--force',self.name],timeout=15)

    def __enter__(self):return self
    def __exit__(self,*args):self.close()
