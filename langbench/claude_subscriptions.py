"""Exact Claude subscription adapter. No live qualification occurs during a coding run."""
from contextlib import ExitStack
import hashlib
import http.server
import json
import os
import re
from pathlib import Path
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid

from .assistance import collect, persist, POLICY, STATUS_INSTRUCTION, terminal_status
from .core import prepare
from .grading import grade
from .mcp_bridge import Bridge
from .provider_cli import bounded_process, write_private, SYSTEM
from .provider_transport import NoRedirect, MAX_BODY
from .provider_usage import summarize_invocations
from .subscriptions import (capture_invocation, source_digest, runtime_binding,
                            validate_qualification, sha, export_workspace)
from .worker import DockerWorker

MODEL = 'claude-opus-5-5'
EFFORT = 'medium'
VERSION = '2.1.290'
BINARY_SHA = 'ea38ee1a1f946eea9bc6e97fb912dbe71fc379b25cc605d91b308afa1ca08be7'
BINARY = Path.home()/'.local/share/mise/installs/claude'/VERSION/'claude'
TOOL = 'mcp__langbench__sandbox_shell'
ENDPOINT = 'https://api.anthropic.com/v1/messages?beta=true'
# Pinned 2.1.290 lCe registry; qee reads name@builtin from enabledPlugins.
BUILTIN_PLUGINS = ('sec-default','agents-md','telemetry','plugin-authoring','mods-guide',
                   'tips','mermaid','responsive-mode','diff','you-should-know','claude-test')
DISABLED_PLUGINS = {'cc-plugin-'+name+'@builtin':False for name in BUILTIN_PLUGINS}
REJECTION_REASONS = frozenset(('invalid request shape','streaming request required','wire model mismatch',
    'wire effort mismatch','wire capability mismatch','subscription OAuth required','path rejected',
    'framing rejected','incomplete request','response bound','allowance unavailable','allowance bound',
    'extra usage must be disabled','allowance unknown','pending_request_bound','request_admission_timeout',
    'invalid_transport_data','invalid_response_event','invalid_response_message','response_model_mismatch',
    'response_capability_mismatch','concurrent_request_rejected','auxiliary_request_bound'))
AUXILIARY_PATHS={'/v1/messages/count_tokens':'count_tokens',
    '/v1/messages/count_tokens?beta=true':'count_tokens','/v1/messages/cache_touch':'cache_touch'}

def endpoint_category(path):
    return AUXILIARY_PATHS.get(path,'messages' if path in ('/v1/messages','/v1/messages?beta=true') else 'unknown')




def exact(model, effort, retention='seal-v1'):
    if (model, effort, retention) != (MODEL, EFFORT, 'seal-v1'):
        raise ValueError('exact Opus 5.5 medium with seal-v1 required')


def inspect_request(body, headers):
    if not isinstance(body,dict) or not isinstance(body.get('output_config'),dict) or not isinstance(body.get('tools'),list) or any(not isinstance(t,dict) for t in body['tools']):
        raise ValueError('invalid request shape')
    if body.get('stream') is not True: raise ValueError('streaming request required')
    if body.get('model') != MODEL: raise ValueError('wire model mismatch')
    if body.get('output_config', {}).get('effort') != EFFORT: raise ValueError('wire effort mismatch')
    names = [tool.get('name') for tool in body.get('tools', [])]
    if names != [TOOL] or any(t.get('type', 'custom') != 'custom' for t in body['tools']):
        raise ValueError('wire capability mismatch')
    lower = {key.lower(): value for key, value in headers.items()}
    authorization = lower.get('authorization', '')
    if lower.get('x-api-key') or not authorization.startswith('Bearer sk-ant-oat'):
        raise ValueError('subscription OAuth required')
    return {'model': MODEL, 'effort': EFFORT, 'tool_names': names, 'auth_mode': 'oauth_bearer',
            'stream': body.get('stream')}


def native_usage(request):
    raw = request.get('usage', {})
    fields = ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')
    valid = all(type(raw.get(name)) is int and raw[name] >= 0 for name in fields)
    identity_valid = request.get('model')==MODEL and request.get('effort')==EFFORT and request.get('tool_names')==[TOOL] and request.get('auth_mode')=='oauth_bearer'
    complete = valid and identity_valid and request.get('message_stopped') is True and request.get('response_complete') is True and request.get('http_status') == 200
    return {'parser_version':'claude-messages-v1', 'provider':'claude',
            'request_id':'transport-'+str(request['index']), 'raw':raw, 'scope':'request',
            'components':{'input':raw.get(fields[0]), 'cache_read':raw.get(fields[1]),
                          'cache_write':raw.get(fields[2]), 'output_including_reasoning':raw.get(fields[3]), 'reasoning':None},
            'cli_normalized_total':None, 'provider_reported_total':sum(raw[n] for n in fields) if complete else None,
            'native_fields_verified':complete, 'request_coverage_verified':complete, 'valid':valid,
            'native_response_observed':identity_valid and request.get('http_status')==200,
            'mapping':'Native disjoint uncached input, cache read, cache creation, output. Thinking is included in output; no separate inference.'}


class ClaudeTransport:
    """Local fixed Messages destination, enforcing subscription and request capabilities."""
    def __init__(self, opener=None):
        self.records=[]; self.rejections=[]; self.denied_auxiliary_requests=[]; self.fatal=None; self.rate_latched=False
        self.condition=threading.Condition(); self.active=0; self.pending=0; self.accepting=True; self.responses=[]
        self.deadline=float('inf')
        self.allowance_checked=False; self.allowance=None
        self.opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version='HTTP/1.0'
            def log_message(self, *args): pass
            def do_POST(self):
                if self.path in AUXILIARY_PATHS:
                    with owner.condition:
                        if not owner.accepting:self.send_error(503);return
                        if len(owner.denied_auxiliary_requests)>=128:
                            owner.reject('auxiliary_request_bound',False,endpoint_category(self.path))
                            self.send_error(503);return
                        owner.denied_auxiliary_requests.append({'endpoint_category':endpoint_category(self.path),
                            'reason':'blocked_noninference_endpoint','upstream_sent':False,'http_status':404,'observed_at':time.time()})
                    self.send_error(404,'Auxiliary endpoint unavailable');return
                with owner.condition:
                    if not owner.accepting: self.send_error(503); return
                    admission_started=time.monotonic()
                    if owner.active:
                        if owner.pending:
                            owner.reject('pending_request_bound', False); self.send_error(503); return
                        owner.pending+=1
                        try:
                            ready=owner.condition.wait_for(lambda:not owner.accepting or owner.active==0,
                                max(0,min(15,owner.deadline-time.monotonic())))
                        finally:
                            owner.pending-=1;owner.condition.notify_all()
                        if not owner.accepting:self.send_error(503);return
                        if not ready:
                            owner.reject('request_admission_timeout', False);self.send_error(503);return
                    if time.monotonic()>=owner.deadline:
                        self.send_error(503);return
                    admission_wait=time.monotonic()-admission_started
                    owner.active += 1
                evidence=None
                try:
                    self.connection.settimeout(130)
                    if self.path not in ('/v1/messages', '/v1/messages?beta=true'): raise ValueError('path rejected')
                    length=int(self.headers.get('Content-Length', '-1'))
                    if not 0 < length <= MAX_BODY or self.headers.get('Transfer-Encoding'): raise ValueError('framing rejected')
                    data=self.rfile.read(length)
                    if len(data)!=length: raise ValueError('incomplete request')
                    body=json.loads(data); evidence=inspect_request(body, dict(self.headers))
                    evidence.update(index=len(owner.records), started_at=time.time(), usage={}, response_ids=[],
                                    admission_wait_seconds=admission_wait)
                    owner.records.append(evidence)
                    if owner.rate_latched:
                        evidence.update(http_status=429, upstream_sent=False, quota_retry_blocked=True)
                        self.send_error(429); return
                    if not owner.allowance_checked:
                        owner.check_allowance(self.headers['Authorization'])
                    if owner.rate_latched:
                        evidence.update(http_status=429, upstream_sent=False, quota_preflight_stop=True)
                        self.send_error(429); return
                    headers={k:v for k,v in self.headers.items() if k.lower() in
                             ('authorization','anthropic-version','anthropic-beta','content-type','user-agent','x-app')}
                    request=urllib.request.Request(ENDPOINT, data=data, headers=headers, method='POST')
                    evidence['upstream_sent']=True
                    try: response=owner.opener.open(request, timeout=125)
                    except urllib.error.HTTPError as error: response=error
                    owner.responses.append(response)
                    with response:
                        evidence['http_status']=response.status
                        if response.status==429: owner.rate_latched=True
                        self.send_response(response.status)
                        self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                        self.end_headers(); pending=b''; count=0
                        while True:
                            chunk=response.read1(65536) if hasattr(response,'read1') else response.read(65536)
                            if not chunk: break
                            count+=len(chunk)
                            if count>MAX_BODY: raise ValueError('response bound')
                            # Observe before client delivery: a killed CLI must not erase known usage.
                            pending+=chunk
                            while b'\n' in pending:
                                line,pending=pending.split(b'\n',1); owner.observe(evidence,line)
                            self.wfile.write(chunk); self.wfile.flush()
                        if pending: owner.observe(evidence,pending)
                        evidence['response_complete']=True
                except Exception as error:
                    if isinstance(error,ValueError):
                        owner.reject(str(error), bool(evidence and evidence.get('upstream_sent')),endpoint_category(self.path),
                                     hashlib.sha256(self.path.split('?',1)[0].encode()).hexdigest() if str(error)=='path rejected' else None)
                    elif evidence is not None: evidence['transport_error']=type(error).__name__
                    try: self.send_error(502)
                    except OSError: pass
                finally:
                    with owner.condition: owner.active-=1; owner.condition.notify_all()
            def do_GET(self): self.send_error(405)
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.base_url='http://127.0.0.1:'+str(self.server.server_port)

    def reject(self, reason, upstream_sent, category='response', path_sha256=None):
        safe=reason if reason in REJECTION_REASONS else 'invalid_transport_data'
        self.fatal=safe
        self.rejections.append({'reason':safe,'upstream_sent':upstream_sent,'observed_at':time.time(),
                                'endpoint_category':category if category in ('messages','count_tokens','cache_touch','unknown','response') else 'unknown'})
        if isinstance(path_sha256,str) and re.fullmatch('[0-9a-f]{64}',path_sha256):
            self.rejections[-1]['path_sha256']=path_sha256

    def check_allowance(self, authorization):
        request=urllib.request.Request('https://api.anthropic.com/api/oauth/usage',
            headers={'Authorization':authorization,'anthropic-beta':'oauth-2025-04-20'})
        with self.opener.open(request,timeout=15) as response:
            if response.status!=200: raise ValueError('allowance unavailable')
            data=response.read(65537)
            if len(data)>65536: raise ValueError('allowance bound')
            value=json.loads(data)
        if (value.get('extra_usage') or {}).get('is_enabled') is not False:
            raise ValueError('extra usage must be disabled')
        limits={key:(value.get(key) or {}).get('utilization') for key in ('five_hour','seven_day')}
        if any(type(v) not in (int,float) or not 0<=v<=100 for v in limits.values()):
            raise ValueError('allowance unknown')
        self.allowance={'extra_usage_enabled':False,'utilization':limits,'checked_at':time.time()}
        self.allowance_checked=True
        if any(v>=100 for v in limits.values()): self.rate_latched=True

    def observe(self, record, line):
        if not line.strip().startswith(b'data:'): return
        try: value=json.loads(line.strip()[5:])
        except ValueError: return
        if not isinstance(value,dict): self.reject('invalid_response_event',True); return
        kind=value.get('type')
        if kind=='message_start':
            message=value.get('message',{})
            if not isinstance(message,dict): self.reject('invalid_response_message',True); return
            if message.get('model')!=MODEL: self.reject('response_model_mismatch',True)
            record['response_ids'].append(message.get('id'))
            record['usage'].update(message.get('usage',{}))
        elif kind=='message_delta':
            record['usage'].update(value.get('usage',{}));record['stop_reason']=value.get('delta',{}).get('stop_reason')
        elif kind=='message_stop': record['message_stopped']=True
        elif kind=='content_block_start':
            block=value.get('content_block',{})
            if block.get('type')=='tool_use' and block.get('name')!=TOOL: self.reject('response_capability_mismatch',True)

    def settle(self, timeout=15):
        with self.condition:
            self.accepting=False;self.condition.notify_all()
            if not self.condition.wait_for(lambda:self.active==0 and self.pending==0,timeout): raise RuntimeError('provider request did not settle')

    def close(self):
        import socket
        for response in self.responses:
            try:
                sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                if sock: sock.shutdown(socket.SHUT_RDWR)
                response.close()
            except OSError: pass
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2);self.settle()


def parse_events(stdout, session, *, truncated=False):
    events=[];terminal='';result=None;initialized=False
    lines=stdout.splitlines()
    for index,line in enumerate(lines):
        if not line.strip(): continue
        try: event=json.loads(line)
        except ValueError:
            if truncated and index==len(lines)-1: break
            raise
        if not isinstance(event,dict): raise ValueError('invalid event')
        if event.get('session_id') and event['session_id']!=session: raise ValueError('session mismatch')
        if event.get('type')=='system' and event.get('subtype')=='init':
            if event.get('model')!=MODEL or event.get('tools')!=[TOOL]: raise ValueError('effective configuration mismatch')
            if event.get('apiKeySource') not in ('none',None): raise ValueError('API key route forbidden')
            if any(event.get(key) for key in ('skills','plugins','slash_commands')):
                raise ValueError('unexpected injected customization')
            initialized=True
        if event.get('type')=='assistant':
            message=event.get('message',{})
            if message.get('model')!=MODEL: raise ValueError('assistant model mismatch')
            texts=[]
            for block in message.get('content',[]):
                if block.get('type')=='tool_use' and block.get('name')!=TOOL: raise ValueError('native tool forbidden')
                if block.get('type')=='text': texts.append(block.get('text',''))
            if texts: terminal='\n'.join(texts)
        if event.get('type')=='result': result=event
        events.append(event)
    return events,terminal,result,initialized


class ClaudeCLI:
    def __init__(self, output, execute, source_hash, *, model=MODEL, effort=EFFORT, binary=None):
        exact(model,effort)
        self.binary=Path(binary or BINARY).resolve()
        if hashlib.sha256(self.binary.read_bytes()).hexdigest()!=BINARY_SHA: raise ValueError('unqualified binary')
        self.output=Path(output);self.output.mkdir(parents=True,exist_ok=False)
        self.temporary=tempfile.TemporaryDirectory(prefix='langbench-claude-');self.home=Path(self.temporary.name)
        self.cwd=self.home/'cwd';self.cwd.mkdir();self.index=0;self.session=None
        # Keep the canonical home and OAuth lock/store namespace; inherit no auth/provider variables.
        self.env={'HOME':str(Path.home()),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TERM':'dumb','NO_COLOR':'1',
            'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1','DISABLE_AUTOUPDATER':'1',
            'CLAUDE_CODE_DISABLE_AUTO_MEMORY':'1','CLAUDE_CODE_DISABLE_BACKGROUND_TASKS':'1',
            'CLAUDE_CODE_DISABLE_CLAUDE_MDS':'1','CLAUDE_CODE_DISABLE_BUNDLED_SKILLS':'1',
            'CLAUDE_CODE_DISABLE_CLAUDE_API_SKILL':'1','CLAUDE_CODE_DISABLE_CLAUDE_CODE_SKILL':'1',
            'CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS':'1','CLAUDE_CODE_DISABLE_EXPLORE_PLAN_AGENTS':'1',
            'CLAUDE_CODE_NO_MODEL_FALLBACK':'1','ANTHROPIC_SMALL_FAST_MODEL':MODEL,
            'CLAUDE_CODE_SUBAGENT_MODEL':MODEL,'ENABLE_TOOL_SEARCH':'false','DISABLE_AUTO_COMPACT':'1'}
        self.bridge=Bridge(self.home,execute,source_hash);self.transport=ClaudeTransport()
        token=self.home/'bridge-token';write_private(token,self.bridge.token)
        command=[sys.executable,'-I',str(Path(__file__).with_name('mcp_bridge.py').resolve()),'--socket',str(self.bridge.path),'--token-file',str(token)]
        self.mcp=self.home/'mcp.json';write_private(self.mcp,json.dumps({'mcpServers':{'langbench':{'command':command[0],'args':command[1:]}}}))
        self.settings=self.home/'settings.json';write_private(self.settings,json.dumps({'disableAllHooks':True,'autoMemoryEnabled':False,'enabledPlugins':DISABLED_PLUGINS,'effortLevel':EFFORT,'permissions':{'allow':[TOOL],'defaultMode':'dontAsk'}}))
        self.identity={'provider':'claude','model':MODEL,'effort':EFFORT,'version':VERSION,'binary_sha256':BINARY_SHA,
            'auth_mode':'canonical_subscription_oauth','endpoint':ENDPOINT,'tool':TOOL,'policy_version':'claude-mcp-only-v1','transport_policy':'serial-admission-v3',
            'settings':json.loads(self.settings.read_text()),'environment':{k:v for k,v in self.env.items() if k!='HOME'}}

    def argv(self,prompt,session):
        return [str(self.binary),'--print','--verbose','--output-format','stream-json','--include-partial-messages',
            '--model',MODEL,'--effort',EFFORT,'--tools','','--allowedTools',TOOL,'--permission-mode','dontAsk',
            '--permission-prompts','none','--strict-mcp-config','--mcp-config',str(self.mcp),
            '--setting-sources','','--settings',str(self.settings),'--disable-slash-commands','--no-chrome',
            '--prompt-suggestions','false','--system-prompt',SYSTEM,
            '--resume' if session else '--session-id',session or self.session,'--',prompt]

    def invoke(self,prompt,session,seconds):
        if session and session!=self.session: raise ValueError('session continuity mismatch')
        if not self.session: self.session=str(uuid.uuid4())
        start=time.monotonic();tool_start=len(self.bridge.records);request_start=len(self.transport.records)
        rejection_start=len(self.transport.rejections);auxiliary_start=len(self.transport.denied_auxiliary_requests)
        self.bridge.deadline=0;self.transport.accepting=True;self.transport.allowance_checked=False
        self.index+=1;directory=self.output/str(self.index);directory.mkdir()
        # Reject managed policy injection before inference. No global file is modified.
        for path in (Path('/etc/claude-code/managed-settings.json'),Path('/etc/claude-code/managed-mcp.json'),Path('/etc/claude-code/managed-settings.d')):
            if path.is_file() or path.is_dir() and any(path.iterdir()): raise ValueError('managed configuration requires independent qualification')
        auth=bounded_process([str(self.binary),'--setting-sources','','--settings',str(self.settings),'auth','status','--json'],cwd=self.cwd,env=self.env,timeout=min(15,seconds),limit=65536)
        try: account=json.loads(auth['stdout'])
        except ValueError: account={}
        if auth['returncode'] or account.get('authMethod')!='claude.ai' or account.get('apiProvider')!='firstParty' or account.get('subscriptionType') not in ('max','pro'):
            raise ValueError('subscription-only authentication unavailable')
        env={**self.env,'ANTHROPIC_BASE_URL':self.transport.base_url}
        def stop():
            if self.bridge.fatal or self.transport.fatal: return 'boundary_rejected'
            if self.transport.rate_latched: return 'quota'
            if any(r.get('result',{}).get('termination')=='timeout' for r in self.bridge.records[tool_start:]): return 'candidate_timeout'
        active_start=time.monotonic();auth_seconds=active_start-start
        self.bridge.deadline=active_start+seconds;self.transport.deadline=active_start+seconds
        raw=bounded_process(self.argv(prompt,session),cwd=self.cwd,env=env,timeout=seconds,stop=stop)
        active_seconds=time.monotonic()-active_start;cleanup_start=time.monotonic()
        for name in ('stdout','stderr'):
            raw[name]=re.sub(r'sk-ant-[A-Za-z0-9_-]+','[REDACTED]',raw[name])
        persist(directory/'raw.json',raw);self.bridge.deadline=0
        errors=[]
        for component,owner in (('bridge',self.bridge),('transport',self.transport)):
            try: owner.settle()
            except Exception as error: errors.append({'component':component,'error_type':type(error).__name__})
        invocation={'status':'infrastructure_error','session_id':self.session,'terminal_text':'','seconds':active_seconds,'auth_preflight_seconds':auth_seconds,
            'cleanup_seconds':time.monotonic()-cleanup_start,
            'raw_path':str(directory/'raw.json'),'events':[],'tool_records':self.bridge.records[tool_start:],
            'request_records':self.transport.records[request_start:],'cleanup_unsettled':errors,'quiescent':not errors,
            'artifact_available':False,'usage_records':[],'usage_coverage_verified':False,'subscription_auth_verified':True,
            'allowance':self.transport.allowance,
            'transport_diagnostics':{'fatal':self.transport.fatal if self.transport.fatal in REJECTION_REASONS else ('invalid_transport_data' if self.transport.fatal else None),
                                     'rejections':list(self.transport.rejections[rejection_start:]),
                                     'denied_auxiliary_requests':list(self.transport.denied_auxiliary_requests[auxiliary_start:])},
            'bridge_boundary_rejected':bool(self.bridge.fatal)}
        try:
            events,text,result,initialized=parse_events(raw['stdout'],self.session,truncated=raw['termination'] in ('timeout','candidate_timeout'))
            invocation.update(events=events,terminal_text=text,effective_configuration_verified=initialized)
            if raw['termination'] in ('timeout','candidate_timeout'): invocation['status']='timeout'
            elif raw['termination']=='quota' or self.transport.rate_latched: invocation['status']='quota'
            elif raw['termination'] or self.bridge.fatal or self.transport.fatal: pass
            elif invocation['request_records'] and invocation['request_records'][-1].get('stop_reason')=='max_tokens': invocation['status']='model_output_limit'
            elif result and result.get('subtype')=='success' and not result.get('is_error') and raw['returncode']==0 and initialized: invocation['status']='handoff'
            invocation['cli_result_usage']=result.get('usage') if result else None
        except Exception as error:
            invocation['parse_error']=type(error).__name__
            invocation['deadline_reached']=raw['termination'] in ('timeout','candidate_timeout')
        if errors and invocation['status'] not in ('timeout','quota'): invocation['status']='infrastructure_error'
        invocation['usage_records']=[native_usage(r) for r in invocation['request_records']]
        invocation['usage_coverage_verified']=bool(invocation['usage_records']) and not self.transport.fatal and all(r['request_coverage_verified'] for r in invocation['usage_records'])
        persist(directory/'invocation.json',invocation)
        return invocation

    def close(self):
        errors=[]
        for owner in (self.transport,self.bridge):
            try: owner.close()
            except Exception as error: errors.append(type(error).__name__)
        self.temporary.cleanup()
        if errors: raise RuntimeError('Claude adapter cleanup unsettled')


def binding(adapter,worker):
    names=('claude_subscriptions.py','subscriptions.py','worker.py','mcp_bridge.py','provider_cli.py','provider_transport.py','provider_usage.py','assistance.py')
    return {'adapter':adapter.identity,'runtime':runtime_binding(),'worker':worker.qualification,'assistance_policy':POLICY,
            'schema_version':1,'adapter_source_sha256':sha({name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in names})}


def qualify_claude(output,*,model=MODEL,effort=EFFORT,binary=None,seconds=120,retention='seal-v1'):
    exact(model,effort,retention)
    provider='claude'
    """Two harmless subscription turns; separate from every coding attempt."""
    output=Path(output).absolute();output.mkdir(parents=True,exist_ok=False)
    receipt={'schema_version':1,'kind':'subscription_qualification','passed':False,'provider':provider,'model':model,'effort':effort,'invocations':[]}
    persist(output/'qualification.json',receipt)
    try:
        workspace=output/'workspace';(workspace/'src').mkdir(parents=True)
        marker=uuid.uuid4().hex;canary=output/'host-canary';secret=uuid.uuid4().hex;canary.write_text(secret)
        command=f'test ! -e {str(canary)} && test ! -e /workspace/tasks && printf %s {marker} > /workspace/src/QUALIFIED'
        with ExitStack() as stack:
            worker=stack.enter_context(DockerWorker(workspace,runtime='seven',retention=retention))
            adapter=ClaudeCLI(output/'trace',lambda c,t:worker.execute(c,timeout=t,output_limit=256*1024),lambda:source_digest(worker),model=model,effort=effort,binary=binary)
            stack.callback(adapter.close)
            receipt['binding']=binding(adapter,worker);receipt['binding_sha256']=sha(receipt['binding'])
            independent=worker.execute(['test','!','-e',str(canary)])
            receipt['independent_host_canary_absent']=independent['returncode']==0 and not independent['termination']
            prompt=('Harmless capability qualification. Only the registered sandbox_shell MCP tool is permitted. '
                'Native host shell, file access and delegation must be unavailable. Execute exactly this command once using sandbox_shell: '+command+
                '\nThen report completion.\n'+STATUS_INSTRUCTION)
            first=adapter.invoke(prompt,None,seconds);receipt['invocations'].append(first);persist(output/'qualification.json',receipt)
            if first['status']!='handoff':raise RuntimeError('initial qualification did not hand off')
            second=adapter.invoke('Session continuity check only: do not call tools. Reply with BENCHMARK_STATUS: COMPLETE as your final line.',first['session_id'],seconds)
            receipt['invocations'].append(second)
            export_workspace(worker,workspace)
            executed=any(item.get('arguments',{}).get('command')==command and item.get('result',{}).get('returncode')==0 and not item.get('result',{}).get('termination') for item in first['tool_records'])
            requests=[request for invocation in receipt['invocations'] for request in invocation['request_records']]
            receipt['checks']={'terminal_markers':all(terminal_status(i['terminal_text'])=='COMPLETE' for i in receipt['invocations']),
                'wire_tool_inventory':any(r['tool_names']==[adapter.identity['tool']] for r in requests),
                'wire_usage_complete':reconcile_claude_usage(receipt['invocations'])['complete'],
                'wire_model_effort_enforced':bool(requests) and not adapter.transport.fatal,
                'effective_tool_inventory':all(i.get('effective_configuration_verified') for i in receipt['invocations']),
                'subscription_route':all(i.get('subscription_auth_verified') and (i.get('allowance') or {}).get('extra_usage_enabled') is False for i in receipt['invocations'])}
            receipt['passed']=bool(all(receipt['checks'].values()) and executed and receipt['independent_host_canary_absent'] and second['status']=='handoff' and second['session_id']==first['session_id'] and (workspace/'src/QUALIFIED').read_text()==marker and canary.read_text()==secret and secret not in json.dumps(receipt))
            receipt['usage_summary']=summarize_claude_invocations(receipt['invocations'])
    except Exception as error:
        receipt['passed']=False
        receipt['error']=type(error).__name__+' (details suppressed to protect provider credentials)'
    persist(output/'qualification.json',receipt)
    return receipt



def run_claude(task,language,output,*,provider='claude',model=MODEL,effort=EFFORT,tests='T1',seed=0,replicate=1,block_id=None,
                     base_seconds=900,continuation_seconds=180,qualification=None,binary=None,retention='seal-v1'):
    if tests not in ('T0','T1') or type(seed) is not int or seed<0:raise ValueError('invalid treatment')
    exact(model,effort,retention)
    if provider!='claude':raise ValueError('invalid provider')
    if not isinstance(qualification,dict) or qualification.get('passed') is not True:raise ValueError('external passed qualification is required')
    for value in (replicate,base_seconds,continuation_seconds):
        if type(value) is not int or value<=0:raise ValueError('positive integer budgets and replicate required')
    output=Path(output).absolute();output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic();phase_started=started
    result={'timing':{},'schema_version':1,'kind':'subscription_attempt','phase':'preparation','validity':'infrastructure_invalid',
            'scored_benchmark_qualified':False,'grades':[],'requested':{'task':task,'language':language,'provider':provider,'model':model,'effort':effort,'tests':tests}}
    persist(output/'result.json',result)
    try:
        workspace=output/'workspace';preparation=prepare(task,language,tests,workspace)
        with ExitStack() as stack:
            worker=stack.enter_context(DockerWorker(workspace,runtime='seven',retention=retention))
            adapter=ClaudeCLI(output/'trace',lambda c,t:worker.execute(c,timeout=t,output_limit=256*1024),lambda:source_digest(worker),model=model,effort=effort,binary=binary)
            stack.callback(adapter.close)
            identity=binding(adapter,worker);validate_qualification(qualification,identity)
            manifest={'schema_version':1,'kind':'subscription_attempt_manifest','attempt_id':uuid.uuid4().hex,
                'task':task,'language':language,'tests':tests,'provider':provider,'model':model,'effort':effort,
                'semantic_seed':seed,'replicate':replicate,'block_id':block_id,'base_seconds':base_seconds,
                'continuation_seconds':continuation_seconds,'max_nudges':2,'assistance_policy':POLICY,
                'initial_artifact_sha256':preparation['initial_artifact_sha256'],'binding':identity,
                'qualification_sha256':sha(qualification)}
            data=json.dumps(manifest,sort_keys=True).encode()
            with (output/'attempt.json').open('xb') as handle:handle.write(data)
            result['timing']['preparation_and_adapter_seconds']=time.monotonic()-phase_started
            phase_started=time.monotonic()
            result.update(manifest=manifest,manifest_sha256=hashlib.sha256(data).hexdigest(),phase='collection')
            persist(output/'result.json',result)
            def invoke(prompt,session,seconds):
                invocation=adapter.invoke(prompt,session,seconds)
                return capture_invocation(worker,workspace,invocation)
            collection=collect(workspace,output/'collection',f'Implement /workspace/TASK.md in {language}. Read it using sandbox_shell. Edit src/ only, preserving scaffold files. Complete and verify the requirements with the supplied offline toolchain.',invoke,
                               base_seconds=base_seconds,continuation_seconds=continuation_seconds)
            collection['usage_summary']=summarize_claude_invocations(collection['invocations'])
            persist(output/'collection/collection.json',collection)
            result['collection']=collection
        result['timing']['collection_and_cleanup_seconds']=time.monotonic()-phase_started
        phase_started=time.monotonic()
        result['phase']='grading';persist(output/'result.json',result)
        for checkpoint in collection['checkpoints']:
            if not checkpoint.get('artifact_available',True):continue
            result['grades'].append({'index':checkpoint['index'],**grade(task,language,checkpoint['artifact_path'],seed=seed,runtime='seven')})
            persist(output/'result.json',result)
        result['timing']['private_grading_seconds']=time.monotonic()-phase_started
        result['phase']='complete'
        result['validity']='infrastructure_invalid' if any(i['status']=='infrastructure_error' or i.get('cleanup_unsettled') for i in collection['invocations']) else 'valid_development'
    except Exception as error:
        result['timing']['incomplete_phase']=result['phase']
        result['timing']['incomplete_phase_seconds']=time.monotonic()-phase_started
        result['error']=type(error).__name__+' (details suppressed to protect provider credentials)'
        partial=output/'collection/collection.json'
        if partial.exists():result['collection']=json.loads(partial.read_text())
    result['timing']['whole_attempt_seconds']=time.monotonic()-started
    persist(output/'result.json',result)
    return result


def reconcile_claude_usage(invocations):
    """Deduplicate native response identities and preserve incomplete observations."""
    grouped={};issues=[];unidentified=[];observed_count=0
    covered=bool(invocations)
    for invocation in invocations:
        requests=invocation.get('request_records',[])
        if not requests or invocation.get('usage_coverage_verified') is not True: covered=False
        for request in requests:
            observed_count+=1
            ids=request.get('response_ids',[])
            if len(ids)!=1 or not isinstance(ids[0],str) or not ids[0]:
                covered=False;issues.append({'kind':'missing_or_invalid_response_identity','index':request.get('index')})
                unidentified.append(native_usage(request));continue
            grouped.setdefault(ids[0],[]).append(request)
    unique=[];duplicates=0
    for identity,requests in grouped.items():
        fingerprints={json.dumps({key:r.get(key) for key in ('usage','http_status','message_stopped','response_complete','stop_reason')},sort_keys=True) for r in requests}
        if len(fingerprints)!=1:
            covered=False;issues.append({'kind':'conflicting_response_identity','response_id':identity});continue
        duplicates+=len(requests)-1
        item=native_usage(requests[0]);unique.append(item)
        if not item['request_coverage_verified']: covered=False
    complete=covered and bool(unique)
    known=[r['provider_reported_total'] for r in unique if r['provider_reported_total'] is not None]
    keys=('input','cache_read','cache_write','output_including_reasoning')
    observed_components={}
    for key in keys:
        values=[r['components'][key] for r in unique if r['native_response_observed'] and type(r['components'][key]) is int and r['components'][key]>=0]
        observed_components[key]=sum(values) if values else None
    lower_values=[v for v in observed_components.values() if v is not None]
    components={key:observed_components[key] if complete else None for key in keys}
    components['reasoning']=None
    return {'parser_version':'claude-messages-v2','total':sum(known) if complete else None,
            'known_subtotal':sum(known) if known else None,'complete':complete,
            'request_count':len(grouped)+len(unidentified),'observed_record_count':observed_count,
            'deduplicated_records':duplicates,'components':components,'issues':issues,
            'identity_conflicts':[i for i in issues if i['kind']=='conflicting_response_identity'],
            'observed_component_lower_bounds':observed_components,
            'known_token_lower_bound':sum(lower_values) if lower_values else None,
            'unidentified_usage_observations':unidentified,
            'billing_total':None,'scope':'Unique native Messages identities; partial component lower bounds are not complete totals. Unidentified/conflicting identities excluded from aggregate amounts.'}


def summarize_claude_invocations(invocations):
    summary=summarize_invocations(invocations)
    native=reconcile_claude_usage(invocations)
    summary.update(provider_reported_total=native['total'],provider_reported_known_subtotal=native['known_subtotal'],
                   native_request_coverage_complete=native['complete'],native_reconciliation=native)
    return summary
