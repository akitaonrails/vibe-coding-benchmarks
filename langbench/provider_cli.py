"""Pinned subscription CLIs with isolated configuration and a single MCP capability."""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import sys
import tempfile
import time
import tomllib
from .mcp_bridge import Bridge
from .provider_usage import record,native_record
from .provider_transport import Transport

ROUTES={'kimi':{'model':'kimi-code/k3','endpoint':'https://api.kimi.com/coding/v1','version':'2.1.1',
                'binary':Path.home()/'.kimi-code/bin/kimi','tool':'mcp__langbench__sandbox_shell'},
        'opencode':{'model':'zai/glm-5.3','endpoint':'https://api.z.ai/api/coding/paas/v4','version':'1.18.34',
                    'binary':Path.home()/'.local/share/mise/installs/opencode/1.18.34/opencode','tool':'langbench_sandbox_shell'}}
SYSTEM='You are implementing a benchmark task. Your only execution capability is sandbox_shell in the offline candidate /workspace. Host files and native tools are unavailable. Edit permitted source, run checks, and report your final status honestly.'


def bounded_process(argv,*,cwd,env,timeout,limit=16*1024*1024,stop=None):
    started=time.monotonic()
    process=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    selector=selectors.DefaultSelector();buffers={'stdout':bytearray(),'stderr':bytearray()};termination=None
    for name in buffers:
        stream=getattr(process,name);os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
    try:
        while selector.get_map():
            if stop and stop():termination=stop();break
            if time.monotonic()-started>=timeout:termination='timeout';break
            for key,_ in selector.select(min(.1,max(.001,timeout-(time.monotonic()-started)))):
                data=os.read(key.fd,65536)
                if not data:selector.unregister(key.fileobj);continue
                buffers[key.data].extend(data)
                if sum(map(len,buffers.values()))>limit:termination='output_limit';break
            if termination:break
        if termination is None:
            try:process.wait(timeout=max(.001,timeout-(time.monotonic()-started)))
            except subprocess.TimeoutExpired:termination='timeout'
    finally:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait();selector.close();process.stdout.close();process.stderr.close()
    return {'returncode':process.returncode,'termination':termination,'seconds':time.monotonic()-started,
            **{name:bytes(data[:limit]).decode('utf-8',errors='replace') for name,data in buffers.items()}}


def parse_events(provider,stdout,*,allow_truncated=False):
    events=[];session=None;terminal=[];finished=False
    for line in stdout.splitlines():
        if not line.strip():continue
        try:event=json.loads(line)
        except ValueError:
            if allow_truncated and line==stdout.splitlines()[-1]:break
            raise
        if not isinstance(event,dict):raise ValueError('non-object provider event')
        events.append(event)
        if provider=='kimi':
            if event.get('role')=='assistant':
                for call in event.get('tool_calls') or []:
                    if call.get('function',{}).get('name')!=ROUTES[provider]['tool']:raise ValueError('forbidden native tool event')
                if isinstance(event.get('content'),str) and not event.get('tool_calls'):terminal.append(event['content'])
            if event.get('role')=='meta' and event.get('type')=='session.resume_hint':session=event.get('session_id');finished=True
        else:
            candidate=event.get('sessionID')
            if candidate:
                if session and session!=candidate:raise ValueError('multiple session identities')
                session=candidate
            part=event.get('part',{})
            if event.get('type')=='tool_use' and part.get('tool')!=ROUTES[provider]['tool']:raise ValueError('forbidden native tool event')
            if event.get('type')=='text' and isinstance(part.get('text'),str):terminal.append(part['text'])
            if event.get('type')=='step_finish' and part.get('reason')=='stop':finished=True
    return events,session,'\n'.join(terminal),finished


def write_private(path,text):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as handle:handle.write(text)
    path.chmod(0o600)


class ProviderCLI:
    def __init__(self,provider,output,execute,source_hash,*,model,effort,binary=None):
        if provider not in ROUTES or model!=ROUTES[provider]['model'] or effort not in ('low','high','max'):
            raise ValueError('unsupported exact provider/model/effort')
        self.provider=provider;self.model=model;self.effort=effort
        self.binary=Path(binary or ROUTES[provider]['binary']).resolve()
        if not self.binary.is_file() or self.binary.read_bytes()[:4]!=b'\x7fELF':raise ValueError('direct ELF CLI required')
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        self.temporary=tempfile.TemporaryDirectory(prefix='langbench-provider-');self.home=Path(self.temporary.name)
        self.cwd=self.home/'cwd';self.cwd.mkdir();self.skills=self.home/'empty-skills';self.skills.mkdir()
        self.env={'PATH':'/usr/bin:/bin','HOME':str(self.home),'LANG':'C.UTF-8','TERM':'dumb','NO_COLOR':'1'}
        for name in ('CONFIG','DATA','CACHE','STATE'):
            self.env['XDG_'+name+'_HOME']=str(self.home/name.lower())
        self.bridge=Bridge(self.home,execute,source_hash)
        token=self.home/'bridge-token';write_private(token,self.bridge.token)
        bridge_file=Path(__file__).with_name('mcp_bridge.py').resolve()
        self.mcp_command=[sys.executable,'-I',str(bridge_file),'--socket',str(self.bridge.path),'--token-file',str(token)]
        self.index=0;self.seen_usage=set();self.secrets=[]
        try:
            self.transport=Transport(provider,effort,ROUTES[provider]['tool'])
            self.configure()
            version=bounded_process([str(self.binary),'--version'],cwd=self.cwd,env=self.env,timeout=20,limit=65536)
            if version['returncode'] or ROUTES[provider]['version'] not in version['stdout']+version['stderr']:raise ValueError('unqualified CLI version')
            self.identity={'provider':provider,'model':model,'effort':effort,'endpoint':ROUTES[provider]['endpoint'],
                'binary_sha256':hashlib.sha256(self.binary.read_bytes()).hexdigest(),'version':ROUTES[provider]['version'],
                'auth_mode':'existing_subscription','transport':'fixed_local_forwarder_v1','tool':ROUTES[provider]['tool'],'policy_version':'mcp-only-v1'}
        except BaseException:self.close();raise

    def configure(self):
        if self.provider=='kimi':self.configure_kimi()
        else:self.configure_opencode()

    def configure_kimi(self):
        canonical=Path.home()/'.kimi-code'
        original=tomllib.loads((canonical/'config.toml').read_text())
        provider=original['providers']['managed:kimi-code'];model=original['models'][self.model]
        if provider.get('base_url')!=ROUTES['kimi']['endpoint'] or provider.get('type')!='kimi' or not provider.get('oauth'):
            raise ValueError('Kimi managed subscription route required')
        if model.get('provider')!='managed:kimi-code' or model.get('model')!='k3':raise ValueError('Kimi model route mismatch')
        home=self.home/'kimi';home.mkdir();self.env['KIMI_CODE_HOME']=str(home)
        # Directory links retain atomic-renamed credential files and the same lock directory.
        for name in ('credentials','oauth'):
            target=canonical/name
            if not target.is_dir():raise ValueError('canonical OAuth store/lock directory absent')
            (home/name).symlink_to(target.resolve(),target_is_directory=True)
            if (home/name).resolve()!=target.resolve():raise ValueError('OAuth directory identity mismatch')
        q=json.dumps
        oauth=provider['oauth']
        credential=canonical/'credentials/kimi-code.json'
        values=json.loads(credential.read_text())
        self.secrets.extend(v for k,v in values.items() if k in ('access_token','refresh_token') and isinstance(v,str) and v)
        if set(oauth)-{'storage','key'}:raise ValueError('unexpected OAuth configuration')
        oauth_line='{'+', '.join(key+' = '+q(value) for key,value in oauth.items())+'}'
        config=f'''default_model = {q(self.model)}
default_permission_mode = "yolo"
merge_all_available_skills = false
telemetry = false
[providers."managed:kimi-code"]
type = "kimi"
api_key = ""
base_url = {q(ROUTES['kimi']['endpoint'])}
oauth = {oauth_line}
[models."kimi-code/k3"]
provider = "managed:kimi-code"
model = "k3"
base_url = {q(self.transport.base_url)}
max_context_size = 1048576
capabilities = ["thinking", "always_thinking", "tool_use"]
support_efforts = ["low", "high", "max"]
[thinking]
enabled = true
effort = {q(self.effort)}
[tools]
enabled = ["mcp__langbench__sandbox_shell"]
[background]
print_background_mode = "exit"
keep_alive_on_exit = false
bash_auto_background_on_timeout = false
'''
        write_private(home/'config.toml',config)
        write_private(home/'mcp.json',json.dumps({'mcpServers':{'langbench':{'command':self.mcp_command[0],'args':self.mcp_command[1:],'toolTimeoutMs':135000}}}))
        self.profile=self.home/'benchmark.md'
        write_private(self.profile,'---\nname: benchmark\ndescription: Isolated benchmark worker\ntools:\n  - mcp__langbench__sandbox_shell\nsubagents: []\n---\n'+SYSTEM)

    def configure_opencode(self):
        managed=Path('/etc/opencode')
        if managed.exists() and any(managed.iterdir()):raise ValueError('unreviewed managed OpenCode configuration')
        original=json.loads((Path.home()/'.config/opencode/opencode.json').read_text())
        source=original['provider']['zai'];options=source.get('options',{})
        if options.get('baseURL')!=ROUTES['opencode']['endpoint'] or source.get('npm')!='@ai-sdk/openai-compatible':raise ValueError('Z.ai coding route required')
        reference=options.get('apiKey','');match=re.fullmatch(r'\{env:([A-Za-z_][A-Za-z0-9_]*)\}',reference)
        if not match or not os.environ.get(match[1]):raise ValueError('existing Z.ai environment credential unavailable')
        self.env[match[1]]=os.environ[match[1]]
        self.secrets.append(os.environ[match[1]])
        permission={'*':'deny','langbench_sandbox_shell':'allow'}
        config={'model':self.model,'small_model':self.model,'enabled_providers':['zai'],'plugin':[],'autoupdate':False,'share':'disabled',
                'snapshot':False,'lsp':False,'formatter':False,'permission':permission,
                'provider':{'zai':{'npm':source['npm'],'options':{'baseURL':self.transport.base_url,'apiKey':reference},
                    'models':{'glm-5.3':{'name':'GLM5.3 coding subscription','options':{'reasoningEffort':self.effort,'reasoning_effort':self.effort},
                    'variants':{self.effort:{'reasoningEffort':self.effort,'reasoning_effort':self.effort}}}}}},
                'agent':{'benchmark':{'mode':'primary','prompt':SYSTEM,'permission':permission}},
                'mcp':{'langbench':{'type':'local','command':self.mcp_command,'enabled':True,'timeout':135000}}}
        path=Path(self.env['XDG_CONFIG_HOME'])/'opencode/opencode.json';write_private(path,json.dumps(config))
        self.env.update(OPENCODE_DISABLE_AUTOUPDATE='1',OPENCODE_DISABLE_PROJECT_CONFIG='1',OPENCODE_DISABLE_MODELS_FETCH='1')

    def invoke(self,prompt,session_id,seconds):
        index=self.index;self.index+=1;start_records=len(self.bridge.records);start_requests=len(self.transport.records)
        self.bridge.deadline=time.monotonic()+seconds
        self.transport.accepting=True
        if self.provider=='kimi':
            argv=[str(self.binary),'-p',prompt,'--output-format','stream-json','-m',self.model,'--skills-dir',str(self.skills)]
            argv+=['-S',session_id] if session_id else ['--agent-file',str(self.profile)]
        else:
            argv=[str(self.binary),'run','--pure','--format','json','--model',self.model,'--agent','benchmark','--variant',self.effort]
            if session_id:argv+=['--session',session_id]
            argv += [prompt]
        result=bounded_process(argv,cwd=self.cwd,env=self.env,timeout=seconds,stop=lambda:'quota' if self.transport.rate_latched else ('boundary' if self.bridge.fatal or self.transport.fatal else ('candidate_timeout' if any(r.get('result',{}).get('termination')=='timeout' for r in self.bridge.records[start_records:]) else None)))
        self.bridge.deadline=0
        for field in ('stdout','stderr'):
            for secret in self.secrets:result[field]=result[field].replace(secret,'[REDACTED_CREDENTIAL]')
        raw=self.output/f'invocation-{index}.json';write_private(raw,json.dumps(result))
        drain_errors=[]
        for name,settle in (('bridge',self.bridge.settle),('transport',self.transport.settle)):
            try:settle()
            except Exception as failure:drain_errors.append({'component':name,'error_type':type(failure).__name__})
        status='handoff';error=None;events=[];resolved=session_id;terminal=''
        try:
            events,resolved,terminal,finished=parse_events(self.provider,result['stdout'],allow_truncated=result['termination'] in ('timeout','candidate_timeout'))
            if self.bridge.fatal or self.transport.fatal:raise ValueError('capability or transport boundary failed')
            if result['termination'] in ('timeout','candidate_timeout'):status='timeout'
            elif result['termination'] or result['returncode'] or not finished:
                status='infrastructure_error';error='CLI failed or missing terminal event'
        except (ValueError,TypeError) as failure:status='infrastructure_error';error=type(failure).__name__+' while validating provider protocol'
        request_records=self.transport.records[start_requests:]
        if any(request.get('http_status')==429 for request in request_records):
            status='quota';error='provider_rate_or_quota_limit'
        usage_error=None
        try:usages=self.usage(events,resolved,index)
        except (ValueError,OSError) as failure:
            usages=[];usage_error=type(failure).__name__
        if drain_errors and status not in ('timeout','quota'):
            status='infrastructure_error';error='cleanup_unsettled'
        coverage=bool(request_records) and len(usages)==len(request_records) and all(r.get('response_complete') and r.get('usage') and r.get('http_status')==200 for r in request_records)
        for usage,request in zip(usages,request_records):
            native=request['usage'][-1] if request.get('usage') else {}
            usage['native_usage']=native
            usage['transport_request_index']=request['index']
            prompt_tokens=native.get('prompt_tokens');completion_tokens=native.get('completion_tokens')
            usage['request_coverage_verified']=coverage and type(prompt_tokens) is int and type(completion_tokens) is int and usage['cli_normalized_total']==prompt_tokens+completion_tokens
        return {'quiescent':not drain_errors,'cleanup_unsettled':drain_errors,'cli_usage_error':usage_error,
                'status':status,'error':error,'session_id':resolved,'terminal_text':terminal,
                'seconds':result['seconds'],'raw_events_path':str(raw),'events':events,
                'tool_records':self.bridge.records[start_records:],'cli_usage_records':usages,
                'usage_records':[native_record(self.provider,r) for r in request_records],
                'request_records':self.transport.records[start_requests:],
                'usage_coverage_verified':bool(request_records) and all(native_record(self.provider,r)['native_fields_verified'] for r in request_records),
                'transport_rejections':self.transport.rejections,
                'boundary_error':{'bridge':self.bridge.fatal,'transport':self.transport.fatal},
                'mcp_protocol':(self.home/'mcp-protocol.jsonl').read_text() if (self.home/'mcp-protocol.jsonl').exists() else ''}

    def usage(self,events,session,index):
        records=[]
        if self.provider=='opencode':
            for event in events:
                part=event.get('part',{})
                if event.get('type')=='step_finish' and isinstance(part.get('tokens'),dict):
                    identity=part.get('id')
                    if identity:records.append(record('opencode',identity,part['tokens']))
        else:
            for path in (self.home/'kimi').rglob('wire.jsonl'):
                if path.stat().st_size>32*1024*1024:raise ValueError('usage log exceeds bound')
                lines=path.read_text().splitlines()
                for number,line in enumerate(lines):
                    try:value=json.loads(line)
                    except ValueError:
                        if number==len(lines)-1:break
                        raise
                    step=value.get('event',{})
                    if value.get('type')=='context.append_loop_event' and step.get('type')=='step.end' and isinstance(step.get('usage'),dict):
                        identity=str(path.relative_to(self.home/'kimi'))+':'+str(number)
                        if identity not in self.seen_usage:
                            self.seen_usage.add(identity);records.append(record('kimi',identity,step['usage']))
        return records

    def close(self):
        errors=[]
        for resource in ('transport','bridge'):
            if hasattr(self,resource):
                try:getattr(self,resource).close()
                except Exception as error:errors.append(type(error).__name__)
        if hasattr(self,'temporary'):self.temporary.cleanup()
        if errors:raise RuntimeError('provider cleanup_unsettled: '+','.join(errors))
