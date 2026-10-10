"""Real RabbitMQ development trials. No benchmark resources enter worker mounts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import ipaddress
import json
import math
import random
import secrets
import socket
from pathlib import Path
import subprocess
import time
import uuid
from langbench.process import execute as bounded_execute
from types import SimpleNamespace

BROKER_IMAGE='rabbitmq:4.1.4-management'
INFRA_IMAGE='langbench-queue-infra:dev'
SCENARIOS=('clean','slow','lost_response','kill_poison','broker_restart','shutdown','handler_crash')
ROOT=Path(__file__).resolve().parent
SECRETS=set()

# The first SELECT establishes the WAL read snapshot. All tables share that view.
SNAPSHOT_SCRIPT = """import sqlite3,json,sys,time
started=time.time()
c=sqlite3.connect(sys.argv[1]);c.row_factory=sqlite3.Row
try:
 c.execute('BEGIN')
 effects=[json.loads(r[0]) for r in c.execute('SELECT body FROM effects')]
 out={'effects':effects,'effect_times':[dict(r) for r in c.execute('SELECT tenant,id,committed FROM effects')],'attempts':[dict(r) for r in c.execute('SELECT tenant,id,started,finished,status,dropped,fault_header FROM attempts')],'peak_inflight':c.execute("SELECT COALESCE(MAX(value),0) FROM metrics WHERE name='peak_inflight'").fetchone()[0]}
 out['snapshot']={'read_started_at':started,'read_finished_at':time.time(),'consistency':'One SQLite read transaction; view fixed by first SELECT. Broker observations are separate.'}
finally:
 c.close()
print(json.dumps(out))"""


def concurrency_measurement(sink, required, timeout_seconds=1.0):
    attempts=sink['attempts']
    unfinished=sum(a.get('finished') is None for a in attempts)
    exceeded=sum(a.get('finished') is not None and a['finished']-a['started']>=timeout_seconds for a in attempts)
    qualified=required and not unfinished and not exceeded
    return {'required':required,'qualified':qualified,'unfinished_attempts':unfinished,
            'timeout_exceeding_spans':exceeded,'request_timeout_seconds':timeout_seconds,
            'cause':'unattributed' if required and not qualified else None,
            'basis':'Observed sink processing intervals, excluding final commit completion and network/admission time; not proof of client concurrency.'}


def sanitize(value):
    for secret in SECRETS:value=value.replace(secret,'[REDACTED]')
    return value

class CandidateFailure(ValueError):
    pass


def docker(*args,input=None,timeout=60,check=True):
    result=subprocess.run(['docker',*map(str,args)],input=input,text=True,capture_output=True,timeout=timeout)
    if check and result.returncode:
        # Do not include command argv: Docker environment arguments carry broker credentials.
        raise RuntimeError('Docker operation failed: '+sanitize(result.stderr[-500:]))
    return result


def image_id(image):
    result=docker('image','inspect',image,'--format','{{.Id}}')
    value=result.stdout.strip()
    if not value.startswith('sha256:') or len(value)!=71:raise ValueError('unresolved image')
    return value


def events(count,poison=False,payload_bytes=64,seed=0):
    if not 16<=payload_bytes<=65536:raise ValueError('payload_bytes must be16..65536')
    rng=random.Random(seed)
    alphabet='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-'
    return [dict(tenant=f't{i%3}',id=f'e{i//3:06d}',value=rng.randint(-1000000,1000000),payload=''.join(rng.choices(alphabet,k=payload_bytes)),poison=bool(poison and i%17==0)) for i in range(count)]


def expected(event):
    return dict(tenant=event['tenant'],id=event['id'],result=event['value']*3+7,digest=hashlib.sha256(event['payload'].encode()).hexdigest())


def evaluate(manifest,accepted,sink,dead,*,limit=8,drained=False,enforce_concurrency=True):
    if not isinstance(accepted,list) or any(not isinstance(key,list) or len(key)!=2 or any(type(part) is not str for part in key) for key in accepted):raise ValueError('malformed publisher identity ledger')
    accepted_keys={tuple(key) for key in accepted}
    if len(accepted_keys)!=len(accepted):raise ValueError('duplicate confirmed source identities')
    source={(e['tenant'],e['id']):e for e in manifest if (e['tenant'],e['id']) in accepted_keys}
    publication_missing=[list((e['tenant'],e['id'])) for e in manifest if (e['tenant'],e['id']) not in accepted_keys]
    actual={};bad=[]
    for e in sink['effects']:
        key=(e['tenant'],e['id']);actual[key]=e
        if key not in source or source[key]['poison'] or e!=expected(source[key]) or type(e.get('result')) is not int or any(type(e.get(field)) is not str for field in ('tenant','id','digest')):bad.append(list(key))
    dead_keys=set();bad_dead=[]
    for e in dead:
        if not isinstance(e,dict) or any(type(e.get(field)) is not str for field in ('tenant','id','payload')) or type(e.get('value')) is not int or type(e.get('poison')) is not bool:
            bad_dead.append({'malformed':repr(e)[:200]});continue
        key=(e['tenant'],e['id'])
        if key not in source or not source[key]['poison'] or e!=source[key]:bad_dead.append(list(key))
        else:dead_keys.add(key)
    missing_effects=[list(k) for k,e in source.items() if not e['poison'] and k not in actual]
    missing_poison=[list(k) for k,e in source.items() if e['poison'] and k not in dead_keys]
    wrong_attempts=sum(a.get('status')==409 for a in sink['attempts'])
    measurement=concurrency_measurement(sink,enforce_concurrency)
    concurrency_ok=(sink['peak_inflight']<=limit) if measurement['qualified'] else None
    correctness=not(publication_missing or missing_effects or missing_poison or bad or bad_dead or wrong_attempts) and drained
    success=correctness and (not enforce_concurrency or concurrency_ok is True)
    return dict(success=success,correctness_and_drain_passed=correctness,concurrency_measurement=measurement,observed_sink_processing_bound_passed=concurrency_ok,publication_missing=publication_missing,accepted=len(source),correct_effects=sum(k in actual and actual[k]==expected(e) for k,e in source.items() if not e['poison']),missing_effects=missing_effects,missing_poison=missing_poison,incorrect_effects=bad,incorrect_deadletters=bad_dead,wrong_attempts=wrong_attempts,peak_observed_sink_handlers=sink['peak_inflight'],http_concurrency_verified=None,drained=drained,http_attempts=len(sink['attempts']),deadletter_copies=len(dead),retry_policy_verification='Per-delivery retry caps/backoff are not fully observable from sink requests alone; not claimed verified.')



def resource_sample(container):
    """Read only the cgroup and processes of the controller-owned worker."""
    try:
        pid=int(docker('inspect',container,'--format','{{.State.Pid}}').stdout.strip())
        if pid<=0:return {'available':False}
        entry=next(line for line in Path(f'/proc/{pid}/cgroup').read_text().splitlines() if line.startswith('0::'))
        root=Path('/sys/fs/cgroup').resolve();group=(root/entry[3:].lstrip('/')).resolve()
        if not group.is_relative_to(root):raise ValueError('invalid cgroup path')
        cpu=dict(line.split() for line in (group/'cpu.stat').read_text().splitlines())
        rss=0
        for child in (group/'cgroup.procs').read_text().split():
            try:
                status=Path(f'/proc/{int(child)}/status').read_text()
                rss+=sum(int(line.split()[1])*1024 for line in status.splitlines() if line.startswith('VmRSS:'))
            except (FileNotFoundError,ProcessLookupError):pass
        return {'available':True,'cpu_usage_usec':int(cpu['usage_usec']),'memory_current_bytes':int((group/'memory.current').read_text()),'memory_peak_bytes':int((group/'memory.peak').read_text()),'summed_process_rss_bytes':rss,'rss_definition':'Sum VmRSS over worker cgroup processes; shared pages may be counted more than once.'}
    except (OSError,ValueError,StopIteration) as exc:
        return {'available':False,'reason':type(exc).__name__}


def load_metrics(samples,publish_seconds,publish_start_seconds=0):
    during=[s for s in samples if publish_start_seconds<=s['seconds']<=publish_start_seconds+publish_seconds and 'queues' in s]
    pairs=[]
    for sample in during:
        work=next((q for q in sample['queues'] if q['name']=='work'),{})
        pairs.append((sample['seconds'],work.get('messages_ready',0)+work.get('messages_unacknowledged',0)))
    slope=None;throughput=None
    if len(pairs)>=2:
        average_t=sum(t for t,_ in pairs)/len(pairs);average_q=sum(q for _,q in pairs)/len(pairs)
        variance=sum((t-average_t)**2 for t,_ in pairs)
        if variance:slope=sum((t-average_t)*(q-average_q) for t,q in pairs)/variance
        elapsed=during[-1]['seconds']-during[0]['seconds']
        if elapsed>0:throughput=(during[-1]['effects']-during[0]['effects'])/elapsed
    resources=[s.get('resources',{}) for s in samples if s.get('resources',{}).get('available')]
    return {'publication_window_sample_count':len(during),'observed_completion_rate_per_second':throughput,'backlog_slope_per_second':slope,'peak_cgroup_memory_bytes':max((r['memory_peak_bytes'] for r in resources),default=None),'peak_summed_process_rss_bytes':max((r['summed_process_rss_bytes'] for r in resources),default=None),'last_observed_cgroup_cpu_usec':resources[-1]['cpu_usage_usec'] if resources else None,'measurement_limit':'Throughput is change in durable effects across observed publication-window samples, excluding final drain; sparse samples and generator lag can invalidate capacity inference.'}


def create_network(name):
    """Use a small private subnet without changing host Docker defaults."""
    ids=docker('network','ls','-q').stdout.split()
    networks=json.loads(docker('network','inspect',*ids).stdout) if ids else []
    occupied=[]
    for network in networks:
        for config in network.get('IPAM',{}).get('Config',[]) or []:
            if config.get('Subnet'):
                subnet=ipaddress.ip_network(config['Subnet'],strict=False)
                if subnet.version==4:occupied.append(subnet)
    routes=subprocess.run(['ip','-j','route','show'],text=True,capture_output=True,check=True)
    for route in json.loads(routes.stdout):
        destination=route.get('dst','default')
        if destination!='default':
            subnet=ipaddress.ip_network(destination,strict=False)
            if subnet.version==4:occupied.append(subnet)
    pool=ipaddress.ip_network('10.0.0.0/8')
    start=secrets.randbelow(1<<20)
    for offset in range(4096):
        subnet=ipaddress.ip_network((int(pool.network_address)+((start+offset)%(1<<20))*16,28))
        if any(subnet.overlaps(other) for other in occupied):continue
        result=docker('network','create','--internal','--opt','com.docker.network.bridge.gateway_mode_ipv4=isolated','--subnet',str(subnet),name,check=False)
        if result.returncode==0:
            info=json.loads(docker('network','inspect',name).stdout)[0]
            if info.get('Internal') is not True or info.get('Options',{}).get('com.docker.network.bridge.gateway_mode_ipv4')!='isolated':
                docker('network','rm',name,check=False)
                raise RuntimeError('isolated gateway boundary unavailable; no fallback')
            return str(subnet)
        if 'overlap' not in result.stderr.lower():raise RuntimeError('private network creation failed: '+sanitize(result.stderr[-300:]))
    raise RuntimeError('no non-overlapping private development subnet available')

class Trial:
    def __init__(self,worker_image,command=(),*,broker_image=BROKER_IMAGE,infra_image=INFRA_IMAGE,cpus=2,memory_mb=1024,pids=128,max_inflight=8,prefetch=32,sink_memory_mb=512,mutant=''):
        self.prefix='langbench-queue-'+uuid.uuid4().hex[:12]
        self.network=self.prefix+'-net';self.broker=self.prefix+'-broker';self.sink=self.prefix+'-sink';self.controller=self.prefix+'-control';self.worker=self.prefix+'-worker'
        self.containers=[];self.volumes=[];self.network_created=False
        try:worker_id=image_id(worker_image)
        except (RuntimeError,ValueError) as exc:raise CandidateFailure('candidate image unavailable or invalid') from exc
        image_configuration=json.loads(docker('image','inspect',worker_id).stdout)[0].get('Config',{})
        if image_configuration.get('Volumes'):raise CandidateFailure('candidate image declares writable VOLUME paths; rebuild without VOLUME')
        self.images={'worker':worker_id,'broker':image_id(broker_image),'infra':image_id(infra_image)}
        self.command=list(command);self.cpus=cpus;self.memory_mb=memory_mb;self.pids=pids;self.max_inflight=max_inflight;self.prefetch=prefetch;self.sink_memory_mb=sink_memory_mb;self.sink_pids=max(128,max_inflight*4+64);self.mutant=mutant
        self.admin_password=uuid.uuid4().hex;self.worker_password=uuid.uuid4().hex
        SECRETS.update((self.admin_password,self.worker_password))
        self.admin_url=f'amqp://admin:{self.admin_password}@broker:5672/%2F'
        self.worker_url=f'amqp://worker:{self.worker_password}@broker:5672/%2F'

    def container(self,name,image,*args,command=()):
        self.containers.append(name)
        docker('run','-d','--name',name,'--network',self.network,'--log-driver','json-file','--log-opt','max-size=1m','--log-opt','max-file=2',*args,image,*command)

    def write(self,container,path,value):
        code='import pathlib,sys;p=pathlib.Path(sys.argv[1]);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(sys.stdin.read())'
        docker('exec','-i',container,'python','-I','-c',code,path,input=json.dumps(value))

    def control(self,mode='normal',delay_ms=0):
        self.write(self.sink,'/state/control.next',dict(mode=mode,delay_ms=delay_ms))
        docker('exec',self.sink,'python','-I','-c',"import os;os.replace('/state/control.next','/state/control.json')")

    def start(self,manifest,mode,delay):
        self.subnet=create_network(self.network);self.network_created=True
        for suffix in ('broker','sink'):
            name=self.prefix+'-'+suffix+'-data';docker('volume','create',name);self.volumes.append(name)
        self.container(self.broker,self.images['broker'],'--network-alias','broker','--memory','1g','--cpus','2','--pids-limit','256','-e','RABBITMQ_DEFAULT_USER=admin','-e','RABBITMQ_DEFAULT_PASS='+self.admin_password,'-e','RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=+S 2:2 +SDcpu 1 +SDio 1 +A 4 -rabbit max_message_size 131072','-e','RABBITMQ_CTL_ERL_ARGS=+S 1:1 +SDcpu 1 +SDio 1 +A 1','--mount','type=volume,src='+self.volumes[0]+',dst=/var/lib/rabbitmq')
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            ready=docker('exec','--user','rabbitmq',self.broker,'rabbitmq-diagnostics','-q','check_running',timeout=10,check=False)
            if ready.returncode==0:break
            if docker('inspect',self.broker,'--format','{{.State.Running}}').stdout.strip()!='true':raise RuntimeError('broker exited during startup')
            time.sleep(.5)
        else:raise RuntimeError('broker readiness deadline')
        docker('exec','--user','rabbitmq',self.broker,'rabbitmqctl','add_user','worker',self.worker_password)
        docker('exec','--user','rabbitmq',self.broker,'rabbitmqctl','set_permissions','-p','/','worker','^$','^amq.default$','^work$')
        self.container(self.controller,self.images['infra'],'--memory','512m','--cpus','2','--pids-limit','128','-e','AMQP_ADMIN_URL='+self.admin_url,command=('-c','import time;time.sleep(3600)'))
        self.container(self.sink,self.images['infra'],'--network-alias','sink','--memory',str(self.sink_memory_mb)+'m','--cpus','2','--pids-limit',str(self.sink_pids),'--mount','type=volume,src='+self.volumes[1]+',dst=/state',command=('-c','import time;time.sleep(3600)'))
        self.write(self.sink,'/state/manifest.json',manifest);self.write(self.sink,'/state/control.json',dict(mode=mode,delay_ms=delay,fault_key=[manifest[0]['tenant'],manifest[0]['id']]))
        docker('exec','-d',self.sink,'python','/infra/sink.py')
        for _ in range(100):
            ready=docker('exec',self.sink,'python','-I','-c',"import socket;s=socket.create_connection(('127.0.0.1',8080),.1);s.close()",check=False)
            if ready.returncode==0:break
            time.sleep(.05)
        else:raise RuntimeError('sink readiness deadline')
        self.producer('setup')

    def qualify_network(self):
        interfaces=json.loads(subprocess.run(['ip','-j','-4','address','show'],text=True,capture_output=True,check=True).stdout)
        addresses={a['local'] for interface in interfaces for a in interface.get('addr_info',[]) if a.get('family')=='inet'}
        addresses.add(str(ipaddress.ip_network(self.subnet).network_address+1))
        script="""import json,socket,sys
reachable=[]
for host in json.loads(sys.argv[1]):
 s=socket.socket();s.settimeout(.1)
 try:
  s.connect((host,int(sys.argv[2])));reachable.append(host)
 except OSError:pass
 finally:s.close()
print(json.dumps({'reachable_host_addresses':reachable}))"""
        with socket.socket() as canary:
            canary.bind(('0.0.0.0',0));canary.listen(128)
            report=json.loads(docker('exec',self.controller,'python','-I','-c',script,json.dumps(sorted(addresses)),str(canary.getsockname()[1]),timeout=30).stdout)
        if report['reachable_host_addresses']:raise RuntimeError('worker network can reach host canary; execution refused')
        return {'internal':True,'gateway_mode_ipv4':'isolated','host_canary_blocked':True,'host_addresses_probed':len(addresses),'subnet':self.subnet,'scope':'Trusted controller probe on same network before candidate startup; no host service route fallback.'}

    def start_worker(self):
        env=dict(AMQP_URL=self.worker_url,INPUT_QUEUE='work',DLQ_QUEUE='dead',SINK_URL='http://sink:8080/effects',PREFETCH=str(self.prefetch),MAX_INFLIGHT=str(self.max_inflight),REQUEST_TIMEOUT_MS='1000',MAX_ATTEMPTS='3',RETRY_DELAY_MS='100',SHUTDOWN_MS='5000',MUTANT=self.mutant)
        args=['--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory',str(self.memory_mb)+'m','--memory-swap',str(self.memory_mb)+'m','--cpus',str(self.cpus),'--pids-limit',str(self.pids),'--tmpfs','/tmp:rw,nosuid,nodev,size=134217728']
        for k,v in env.items():args+=['-e',k+'='+v]
        try:self.container(self.worker,self.images['worker'],*args,command=self.command)
        except RuntimeError as exc:raise CandidateFailure('candidate image could not start') from exc

    def producer(self,op,events=None,rate=0):
        result=docker('exec','-i',self.controller,'python','/infra/producer.py',op,str(rate),input=json.dumps(events) if events is not None else None,timeout=180)
        return json.loads(result.stdout)

    def snapshot(self):
        return json.loads(docker('exec',self.sink,'python','-I','-c',SNAPSHOT_SCRIPT,'/state/sink.sqlite').stdout)

    def queues(self):
        output=docker('exec','--user','rabbitmq',self.broker,'rabbitmqctl','-q','list_queues','name','messages_ready','messages_unacknowledged','--formatter=json',timeout=15).stdout
        return json.loads(output)

    def wait_attempt(self,deadline):
        while time.monotonic()<deadline:
            snap=self.snapshot()
            if snap['attempts']:return snap
            running=docker('inspect',self.worker,'--format','{{.State.Running}}').stdout.strip()
            if running!='true':raise CandidateFailure('candidate worker exited before processing')
            time.sleep(.1)
        raise CandidateFailure('candidate worker made no downstream attempt')

    def close(self):
        errors=[]
        commands=[('rm','-f','-v',name) for name in reversed(self.containers)]
        commands += [('volume','rm',name) for name in self.volumes]
        if self.network_created:commands.append(('network','rm',self.network))
        for command in commands:
            try:
                outcome=docker(*command,check=False)
                if outcome.returncode and 'No such container' not in outcome.stderr:errors.append(' '.join(command)+': '+sanitize(outcome.stderr[-200:]))
            except Exception as exc:errors.append(type(exc).__name__+': '+str(exc)[:200])
        return errors


def run(worker_image,destination,*,command=(),scenario='clean',count=96,rate=0,duration=None,payload_bytes=64,deadline=60,drain_seconds=30,cpus=2,memory_mb=1024,pids=128,max_inflight=8,prefetch=32,sink_memory_mb=512,mutant='',hook_review=None,seed=None):
    if scenario not in SCENARIOS or type(count) is not int or count<1 or count>100000 or any(not math.isfinite(v) for v in (rate,deadline,drain_seconds,cpus,memory_mb)) or rate<0 or deadline<=0 or drain_seconds<0 or cpus<=0 or memory_mb<128:raise ValueError('invalid trial parameters')
    if any(type(v) is not int for v in (pids,max_inflight,prefetch,sink_memory_mb)) or not 32<=pids<=8192 or not 1<=max_inflight<=512 or not 1<=prefetch<=4096 or not 128<=sink_memory_mb<=32768:raise ValueError('invalid process/concurrency/infrastructure limits')
    if duration is not None:
        if not math.isfinite(duration) or duration<=0 or rate<=0:raise ValueError('duration requires positive offered rate')
        requested=rate*duration
        if not math.isfinite(requested) or requested>100000:raise ValueError('requested duration exceeds 100000-event development bound')
        count=max(1,int(requested))
    if not 16<=payload_bytes<=65536 or count*(payload_bytes+200)>64*1024*1024:raise ValueError('manifest exceeds bounded development payload budget')
    if seed is None:seed=secrets.randbits(63)
    if type(seed) is not int or seed<0:raise ValueError('invalid seed')
    output=Path(destination);output.mkdir(parents=True,exist_ok=False)
    result={'runner_source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'kind':'queue_development_trial','scalable_capacity_qualified':False,'scenario':scenario,'requested_events':count,'seed':seed,'offered_rate':rate,'duration_seconds':duration,'payload_bytes':payload_bytes,'command':list(command),'resource_limits':dict(cpus=cpus,memory_mb=memory_mb,pids=pids,max_inflight=max_inflight,prefetch=prefetch),'infrastructure_limits':dict(sink_memory_mb=sink_memory_mb,sink_pids=max(128,max_inflight*4+64),sink_cpus=2,broker_cpus=2,broker_memory_mb=1024),'validity':'infrastructure_invalid','fault_triggered':scenario in ('clean','slow','lost_response'),'telemetry':[]}
    trial=None;phase='infrastructure_setup'
    try:
        trial=Trial(worker_image,command,cpus=cpus,memory_mb=memory_mb,pids=pids,max_inflight=max_inflight,prefetch=prefetch,sink_memory_mb=sink_memory_mb,mutant=mutant)
        approved_hook=None
        if hook_review is not None:
            approved_hook=json.loads(Path(hook_review).read_text())
            if approved_hook.get('command')!=list(command) or approved_hook.get('approved') is not True or approved_hook.get('worker_image_sha256')!=trial.images['worker'] or not isinstance(approved_hook.get('trace_marker'),str) or not approved_hook.get('trace_marker') or len(approved_hook.get('source_sha256',''))!=64 or not approved_hook.get('reviewed_invocation'):
                raise ValueError('hook review must be approved and bound to exact worker image/source')
            result['hook_review']=approved_hook
        manifest=events(count,poison=scenario=='kill_poison',payload_bytes=payload_bytes,seed=seed)
        result['manifest_sha256']=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        mode='blocked' if scenario in ('kill_poison','broker_restart') else 'drop_response' if scenario=='lost_response' else 'handler_crash' if scenario=='handler_crash' else 'normal'
        delay=50 if scenario in ('slow','shutdown') else 0
        trial.start(manifest,mode,delay);result['images']=trial.images;result['network_subnet']=trial.subnet
        result['network_qualification']=trial.qualify_network()
        phase='candidate_startup';trial.start_worker();phase='publication'
        initial_container=json.loads(docker('inspect',trial.worker).stdout)[0]
        initial_identity={'pid':initial_container['State']['Pid'],'started_at':initial_container['State']['StartedAt'],'restart_count':initial_container['RestartCount']}
        started=time.monotonic();started_wall=time.time()
        def sample():
            snapshot=trial.snapshot();queues=trial.queues()
            result['telemetry'].append({'seconds':time.monotonic()-started,'effects':len(snapshot['effects']),'queues':queues,'resources':resource_sample(trial.worker)})
            return snapshot,queues
        # Publication runs independently of monitoring; a synchronous publisher
        # confirm window may still bottleneck, which scheduling lag exposes.
        with ThreadPoolExecutor(max_workers=1) as pool:
            publishing=pool.submit(trial.producer,'publish',manifest,rate)
            while not publishing.done():
                sample();time.sleep(.25)
            publication=publishing.result()
        result['publication']=publication
        result['publication_observed_seconds']=time.monotonic()-started
        phase='candidate_execution';accepted=publication['accepted']
        if scenario in ('kill_poison','broker_restart','shutdown'):
            proof=trial.wait_attempt(time.monotonic()+min(20,deadline));queues=trial.queues()
            result['fault_proof']={'observed_attempts':len(proof['attempts']),'queues_before':queues}
            if scenario=='kill_poison':
                docker('kill','--signal','KILL',trial.worker);trial.control();docker('start',trial.worker);result['fault_triggered']=True
            elif scenario=='broker_restart':
                # Sink was blocked before publication; require observed outstanding work.
                docker('restart','--time','1',trial.broker,timeout=60)
                result['fault_triggered']=any(row.get('messages_unacknowledged',0)>0 or row.get('messages_ready',0)>0 for row in queues)
                for _ in range(60):
                    if docker('exec','--user','rabbitmq',trial.broker,'rabbitmq-diagnostics','-q','check_running',check=False).returncode==0:break
                    time.sleep(.2)
                else:raise RuntimeError('broker did not recover')
                trial.control()
            else:
                signalled=time.monotonic();docker('kill','--signal','TERM',trial.worker)
                until=signalled+5
                while time.monotonic()<until and docker('inspect',trial.worker,'--format','{{.State.Running}}').stdout.strip()=='true':time.sleep(.05)
                stopped=docker('inspect',trial.worker,'--format','{{.State.Running}}').stdout.strip()=='false'
                result['shutdown']={'within_deadline':stopped,'seconds':time.monotonic()-signalled}
                if not stopped:docker('kill','--signal','KILL',trial.worker)
                docker('start',trial.worker);result['fault_triggered']=any(row.get('messages_unacknowledged',0)>0 or row.get('messages_ready',0)>0 for row in queues)
        until=time.monotonic()+deadline+drain_seconds;drained=False
        while time.monotonic()<until:
            if docker('inspect',trial.worker,'--format','{{.State.Running}}').stdout.strip()!='true':
                raise CandidateFailure('candidate worker exited before drain')
            snapshot,queues=sample()
            healthy=sum(not e['poison'] for e in manifest)
            work=next((row for row in queues if row['name']=='work'),{})
            if len(snapshot['effects'])>=healthy and work.get('messages_ready',1)==0 and work.get('messages_unacknowledged',1)==0:
                drained=True;break
            time.sleep(.2)
        result['elapsed_seconds']=time.monotonic()-started
        result['load_metrics']=load_metrics(result['telemetry'],publication['publish_seconds'],publication['started_at']-started_wall)
        result['load_metrics']['generator_max_schedule_lag_seconds']=max(publication['schedule_lag_seconds'],default=0)
        snapshot=trial.snapshot();dead=trial.producer('dead')
        (output/'sink-observations.json').write_text(json.dumps(snapshot,indent=2)+'\n')
        (output/'deadletters.json').write_text(json.dumps(dead,indent=2)+'\n')
        bounded_logs=bounded_execute(['docker','logs','--tail','500',trial.worker],timeout=10,output_limit=262144)
        result['worker_log_capture']={'byte_limit':262144,'termination':bounded_logs['termination']}
        worker_logs=SimpleNamespace(stdout=bounded_logs['stdout'],stderr=bounded_logs['stderr'])
        (output/'worker.log').write_text(sanitize(worker_logs.stdout+worker_logs.stderr)[-262144:])
        if scenario=='handler_crash':
            faults=[a for a in snapshot['attempts'] if a.get('fault_header')=='handler-crash']
            final_container=json.loads(docker('inspect',trial.worker).stdout)[0]
            final_identity={'pid':final_container['State']['Pid'],'started_at':final_container['State']['StartedAt'],'restart_count':final_container['RestartCount']}
            fault_time=faults[0]['started'] if faults else None
            progress=sum(e['committed']>fault_time and e['tenant']!=faults[0]['tenant'] for e in snapshot['effect_times']) if faults else 0
            result['handler_fault']={'hook_review_pending':approved_hook is None,'hook_execution_proven':False,'hook_execution_supported_by_review_and_trace':bool(approved_hook and approved_hook['trace_marker'] in worker_logs.stdout+worker_logs.stderr and faults),'fault_headers_observed':len(faults),'initial_container':initial_identity,'final_container':final_identity,'container_unchanged':initial_identity==final_identity,'healthy_other_tenant_effects_after_fault':progress,'exception_log_path':'worker.log'}
            result['fault_triggered']=bool(faults)
        verdict=evaluate(manifest,accepted,snapshot,dead,drained=drained,limit=max_inflight,enforce_concurrency=scenario in ('clean','slow'))
        scheduled={(e['tenant'],e['id']):e['scheduled'] for e in publication['scheduled_publications']}
        latencies=sorted(e['committed']-scheduled[(e['tenant'],e['id'])] for e in snapshot['effect_times'] if (e['tenant'],e['id']) in scheduled)
        result['latency_seconds']={'p50':latencies[int((len(latencies)-1)*.50)] if latencies else None,'p95':latencies[int((len(latencies)-1)*.95)] if latencies else None,'p99':latencies[int((len(latencies)-1)*.99)] if latencies else None,'completed_effects':len(latencies),'unresolved_healthy':len(verdict['missing_effects']),'basis':'Scheduled publisher wall time to pre-commit transaction timestamp of a subsequently committed effect; excludes commit completion time. Successes only, unresolved count retained.'}
        cpu=result['load_metrics']['last_observed_cgroup_cpu_usec']
        result['load_metrics']['cpu_usec_per_correct_effect_including_startup']=cpu/verdict['correct_effects'] if scenario in ('clean','slow') and cpu is not None and verdict['correct_effects'] else None
        if result.get('shutdown',{}).get('within_deadline') is False:verdict['success']=False
        if scenario=='handler_crash' and (not result['handler_fault']['container_unchanged'] or not result['handler_fault']['healthy_other_tenant_effects_after_fault']):verdict['success']=False
        if scenario=='lost_response':result['fault_triggered']=any(a['dropped'] for a in snapshot['attempts'])
        if scenario=='slow':result['fault_triggered']=any(a['finished'] is not None and a['finished']-a['started']>=.05 for a in snapshot['attempts'])
        result.update(verdict=verdict,validity='valid_development' if result['fault_triggered'] else 'infrastructure_invalid')
        if scenario in ('clean','slow') and not verdict['concurrency_measurement']['qualified']:
            result['validity']='measurement_unqualified'
        if scenario=='handler_crash':
            if approved_hook is None:result['validity']='hook_review_required'
            elif not result['handler_fault']['hook_execution_supported_by_review_and_trace']:verdict['success']=False
        result['limitations']=['Not a sustainable capacity measurement.','Per-delivery retry caps and local buffered work are not fully externally verified.','Broker prefetch/unacked sampling is observational, not a continuous proof.','Sink processing intervals do not prove client concurrency; clean/slow timeout-overlap measurements are unqualified, with cause unattributed.','Publisher uses a one-message confirm window; scheduling lag must qualify offered rate before any capacity inference.','No stack comparison from a single development run.']
    except Exception as exc:
        result['validity']='candidate_failure' if isinstance(exc,CandidateFailure) else 'infrastructure_invalid'
        result['error']=type(exc).__name__+': '+sanitize(str(exc))[:400];result['phase']=phase
    finally:
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if trial is not None:
            result['cleanup_errors']=trial.close()
            if result['cleanup_errors']:result['validity']='infrastructure_invalid'
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='op',required=True)
    sub.add_parser('setup')
    r=sub.add_parser('run');r.add_argument('image');r.add_argument('destination');r.add_argument('--scenario',choices=SCENARIOS,default='clean');r.add_argument('--count',type=int,default=96);r.add_argument('--rate',type=float,default=0);r.add_argument('--duration',type=float);r.add_argument('--payload-bytes',type=int,default=64);r.add_argument('--deadline',type=float,default=60);r.add_argument('--drain-seconds',type=float,default=30);r.add_argument('--cpus',type=float,default=2);r.add_argument('--memory-mb',type=int,default=1024);r.add_argument('--pids',type=int,default=128);r.add_argument('--max-inflight',type=int,default=8);r.add_argument('--prefetch',type=int,default=32);r.add_argument('--sink-memory-mb',type=int,default=512);r.add_argument('--mutant',default='');r.add_argument('--seed',type=int);r.add_argument('--hook-review',type=Path);r.add_argument('--command',nargs=argparse.REMAINDER,default=[])
    args=p.parse_args()
    if args.op=='setup':
        docker('pull',BROKER_IMAGE,timeout=180)
        docker('build','-t',INFRA_IMAGE,str(ROOT/'infra'),timeout=300)
        print(json.dumps({'broker':image_id(BROKER_IMAGE),'infra':image_id(INFRA_IMAGE)}));return 0
    result=run(args.image,args.destination,command=args.command,scenario=args.scenario,count=args.count,rate=args.rate,duration=args.duration,payload_bytes=args.payload_bytes,deadline=args.deadline,drain_seconds=args.drain_seconds,cpus=args.cpus,memory_mb=args.memory_mb,pids=args.pids,max_inflight=args.max_inflight,prefetch=args.prefetch,sink_memory_mb=args.sink_memory_mb,mutant=args.mutant,hook_review=args.hook_review,seed=args.seed)
    print(json.dumps(result,indent=2));return 0 if result.get('verdict',{}).get('success') and result.get('validity')=='valid_development' else 1

if __name__=='__main__':raise SystemExit(main())
