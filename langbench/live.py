"""Subscription smoke collection; private grading follows all model turns."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import uuid
from .appserver import AppServer, DEFAULT_BINARY, DISABLED_FEATURES, ProtocolViolation, RpcError
from .controller import collect
from .core import prepare, digest_tree
from .grading import grade
from .manifest import freeze
from .process import execute
from .worker import DockerWorker

TOOL = {'type':'function','name':'sandbox_shell','description':'Run a shell command in the isolated offline /workspace. Only src/ is submitted. Use this tool to inspect/edit source and run builds/tests. Each call waits; background jobs are stopped at return.',
        'inputSchema':{'type':'object','properties':{'command':{'type':'string'},'timeout_seconds':{'type':'integer','minimum':1,'maximum':120}},'required':['command'],'additionalProperties':False}}
ALLOWED_ITEMS={'userMessage','agentMessage','functionCallOutput','plan','reasoning','dynamicToolCall','contextCompaction'}

def check_item(item):
    kind=item.get('type')
    if kind not in ALLOWED_ITEMS:raise ProtocolViolation('unexpected item capability: '+str(kind))
    if kind=='dynamicToolCall' and (item.get('tool')!='sandbox_shell' or item.get('namespace') not in (None,'')):
        raise ProtocolViolation('unexpected dynamic tool capability')

def _probe_report(value, marker):
    """Read structured tool JSON; textual occurrence counts are never evidence."""
    if isinstance(value,dict):
        if value.get('isError') is True or value.get('success') is False or value.get('status') in ('failed','error'):
            return False
        if value.get('marker')==marker:
            return all(value.get(name)=='undefined' for name in ('process','require','Deno','fetch'))
        return any(_probe_report(child,marker) for child in value.values())
    if isinstance(value,list):
        return any(_probe_report(child,marker) for child in value)
    if isinstance(value,str):
        try:decoded=json.loads(value)
        except (ValueError,TypeError):return False
        return _probe_report(decoded,marker) if decoded!=value else False
    return False

def verify_js_probe(events, marker, expected_program):
    items=[event.get('params',{}).get('item',{}) for event in events]
    calls={item.get('call_id') for item in items
           if item.get('type') in ('function_call','custom_tool_call')
           and item.get('name') in ('exec','functions.exec')
           and isinstance(item.get('input'),str) and item['input'].strip()==expected_program.strip()
           and item.get('status') not in ('failed','error')}
    for item in items:
        if item.get('status') in ('failed','error') or item.get('isError') is True or item.get('success') is False:
            continue
        if item.get('type') in ('function_call_output','custom_tool_call_output') and item.get('call_id') in calls:
            output=item.get('output')
        else:
            continue
        if _probe_report(output,marker):return True
    return False


def environment(worker,binary):
    runtimes={}
    for name in ('ruby','rustc','cargo'):
        result=worker.execute([name,'--version'])
        if result['returncode'] or result['termination']:raise RuntimeError('runtime qualification failed: '+name)
        runtimes[name]=result['stdout'].strip()
    version=execute([str(binary),'--version'])
    if version['returncode']:raise RuntimeError('Codex version unavailable')
    companion=Path(binary).resolve().parent/'codex-code-mode-host'
    if not companion.is_file():raise RuntimeError('pinned Code Mode companion unavailable')
    return {'worker':worker.qualification,'runtime_versions':runtimes,'codex_version':version['stdout'].strip(),
            'codex_binary_sha256':hashlib.sha256(Path(binary).read_bytes()).hexdigest(),
            'code_mode_host':{'enabled':True,'path':str(companion),'sha256':hashlib.sha256(companion.read_bytes()).hexdigest(),
                              'version':'bundled with '+version['stdout'].strip(),'role':'JavaScript tool composition only; no builtin shell/environment capabilities'},
            'disabled_features':list(DISABLED_FEATURES),'host_skill_discovery':False,
            'builtin_environments':[], 'experimental_raw_events':True, 'dynamic_tools':[TOOL], 'web_search':'disabled',
            'toolchain_identity_limit':'Runtime versions and binary hash recorded; host toolchain trees are not immutable images.'}

class Adapter:
    def __init__(self, server, worker, workspace, model, effort):
        self.server=server;self.worker=worker;self.workspace=Path(workspace);self.model=model;self.effort=effort
        self.thread=None;self.resolved_model=None;self.tool_calls=[];self.turn_ids=set()

    def start(self):
        result=self.server.call('thread/start',{'model':self.model,'allowProviderModelFallback':False,
            'approvalPolicy':'never','sandbox':'read-only','ephemeral':True,'environments':[], 'experimentalRawEvents':True,
            'selectedCapabilityRoots':[],'dynamicTools':[TOOL],
            'cwd':str(self.server.cwd),
            'developerInstructions':'Use only sandbox_shell. The host session is read-only, but sandbox_shell executes in a separate writable Docker worker. The working tree is /workspace inside that tool. You may read all workspace files and write src/; builds may create target/. Only src/ is editable source; preserve launchers and compiler settings. No host execution, external browsing, plugins, or other agents are available.'})
        if result.get('model')!=self.model:raise ProtocolViolation('resolved model differs from requested model')
        self.thread=result.get('thread',{}).get('id')
        if not isinstance(self.thread,str) or not self.thread:raise ProtocolViolation('missing thread ID')
        self.resolved_model=result['model']
        return self.thread

    def export(self):
        with tempfile.TemporaryDirectory(prefix='langbench-export-') as temp:
            exported=Path(temp)/'workspace';self.worker.export(exported)
            # Destination is controller-created and never passed to the candidate.
            shutil.rmtree(self.workspace)
            shutil.copytree(exported,self.workspace)

    def invoke(self,prompt,session,seconds):
        if self.thread is None:raise RuntimeError('start thread before freezing attempt')
        if session is not None and session!=self.thread:raise ProtocolViolation('explicit thread continuity mismatch')
        started=time.monotonic();deadline=started+seconds;events=[];calls=[];turn_id=None;status='infrastructure_error';error=None
        try:
            result=self.server.call('turn/start',{'threadId':self.thread,'model':self.model,'effort':self.effort,
                'approvalPolicy':'never','environments':[],
                'input':[{'type':'text','text':prompt}]},timeout=max(.01,deadline-time.monotonic()))
            turn=result.get('turn',{});turn_id=turn.get('id')
            if not isinstance(turn_id,str) or not turn_id:raise ProtocolViolation('missing turn ID')
            self.turn_ids.add(turn_id)
            for item in turn.get('items',[]):check_item(item)
            events.append({'type':'turn.started','turn_id':turn_id,'monotonic_seconds':0})
            while True:
                message=self.server.next(deadline)
                method=message.get('method');params=message.get('params',{})
                if not method:raise ProtocolViolation('unexpected RPC reply during turn')
                if method.startswith('account/'):
                    # Never archive account identity or allowance payloads.
                    continue
                if params.get('threadId') not in (None,self.thread):raise ProtocolViolation('cross-thread event')
                if params.get('turnId') not in (None,turn_id):
                    if method!='thread/tokenUsage/updated' or params.get('turnId') not in self.turn_ids:
                        raise ProtocolViolation('cross-turn event')
                if method=='thread/settings/updated':
                    settings=params.get('threadSettings') or {}
                    if settings.get('model') not in (None,self.model) or settings.get('effort') not in (None,self.effort):
                        raise ProtocolViolation('effective model or effort differs from request')
                    nested=(settings.get('collaborationMode') or {}).get('settings') or {}
                    if nested.get('model') not in (None,self.model) or nested.get('reasoning_effort') not in (None,self.effort):
                        raise ProtocolViolation('effective collaboration model or effort differs from request')
                if method in ('item/started','item/completed'):check_item(params.get('item',{}))
                if any(method.startswith('item/'+name) for name in ('commandExecution','fileChange','mcpToolCall','collabAgent','webSearch','imageGeneration')):
                    raise ProtocolViolation('unexpected builtin notification')
                events.append({'type':'appserver_notification','method':method,'params':params,
                               'monotonic_seconds':time.monotonic()-started})
                if 'id' in message:
                    if method!='item/tool/call':
                        self.server.send({'id':message['id'],'error':{'code':-32601,'message':'Capability not authorized'}})
                        raise ProtocolViolation('unexpected server tool request: '+method)
                    if params.get('threadId')!=self.thread or params.get('turnId')!=turn_id:
                        raise ProtocolViolation('missing or mismatched tool-call identity')
                    if params.get('tool')!='sandbox_shell' or params.get('namespace') not in (None,''):
                        raise ProtocolViolation('unexpected dynamic tool request')
                    args=params.get('arguments')
                    if not isinstance(args,dict) or set(args)-{'command','timeout_seconds'} or not isinstance(args.get('command'),str) or len(args['command'])>131072:
                        raise ProtocolViolation('invalid sandbox shell arguments')
                    requested=args.get('timeout_seconds',60)
                    if type(requested) is not int or not 1<=requested<=120:raise ProtocolViolation('invalid tool timeout')
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('turn budget exhausted')
                    outcome=self.worker.execute(args['command'],timeout=min(requested,remaining),output_limit=256*1024)
                    record={'command':args['command'],'call_id':params.get('callId'),'turn_id':turn_id,**outcome}
                    calls.append(record);self.tool_calls.append(record)
                    self.server.send({'id':message['id'],'result':{'contentItems':[{'type':'inputText','text':json.dumps(outcome)}],
                        'success':outcome['returncode']==0 and outcome['termination'] is None}})
                    if not self.worker.alive:
                        status='timeout' if time.monotonic()>=deadline else 'infrastructure_error'
                        error='worker_retired_after_tool_limit';break
                elif method=='turn/completed':
                    terminal=params.get('turn',{})
                    if terminal.get('id')!=turn_id:raise ProtocolViolation('terminal turn ID mismatch')
                    for item in terminal.get('items',[]):check_item(item)
                    state=terminal.get('status')
                    status='handoff' if state=='completed' else 'infrastructure_error'
                    if state!='completed':
                        detail=terminal.get('error') or {};code=detail.get('codexErrorInfo')
                        if code in ('usageLimitExceeded','rateLimitExceeded'):status='quota'
                        error={'terminal_status':state,'code':code}
                    events.append({'type':'turn.completed' if status=='handoff' else 'turn.failed','turn_id':turn_id})
                    break
        except TimeoutError:
            status='timeout';error='turn_deadline'
        except (ProtocolViolation,RpcError,RuntimeError,OSError,ValueError) as exc:
            status='infrastructure_error';error=type(exc).__name__+': '+str(exc)[:300]
        active_seconds=time.monotonic()-started
        if status!='handoff' and turn_id:
            try:self.server.call('turn/interrupt',{'threadId':self.thread,'turnId':turn_id},timeout=2)
            except Exception:pass
        artifact_available=False
        if self.worker.alive:
            try:
                self.export();artifact_available=True
            except (RuntimeError,ValueError,OSError):error='artifact_export_failed';status='infrastructure_error'
        return {'status':status,'session_id':self.thread,'turn_id':turn_id,'seconds':active_seconds,'events':events,
                'tool_calls':calls,'tool_call_count':len(calls),'tool_seconds':sum(call['seconds'] for call in calls),
                'artifact_available':artifact_available,'error':error,
                'raw_usage_updates':[event for event in events if event.get('method')=='thread/tokenUsage/updated'],
                'raw_thread_cumulative':next((event['params'].get('tokenUsage',{}).get('total') for event in reversed(events) if event.get('method')=='thread/tokenUsage/updated'),None),
                'usage_semantics':{'scope':'unqualified','reasoning_overlap':'unqualified','normalized_total':None}}


def qualify(destination,model='gpt-6-luna',effort='high',seconds=90,binary=DEFAULT_BINARY):
    if type(seconds) is not int or seconds <= 0:raise ValueError('qualification seconds must be positive')
    output=Path(destination);output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='langbench-canary-') as temp, ExitStack() as stack:
        home=Path(temp);canary=home/'HOST_CANARY';secret=uuid.uuid4().hex;canary.write_text(secret)
        source=home/'workspace';(source/'src').mkdir(parents=True)
        marker=uuid.uuid4().hex
        probe_command=f'test ! -e {canary} && printf %s {marker} > /workspace/src/QUALIFIED'
        worker=stack.enter_context(DockerWorker(source))
        independent_probe=worker.execute(['test','!','-e',str(canary)])
        independent_probe_passed=independent_probe['returncode']==0 and independent_probe['termination'] is None
        env=environment(worker,binary)
        server=stack.enter_context(AppServer(binary))
        auth=server.initialize(model,effort)
        adapter=Adapter(server,worker,source,model,effort);adapter.start()
        js_marker='LANGBENCH_JS_GLOBALS_'+uuid.uuid4().hex
        program=(f'const result = {{marker:{json.dumps(js_marker)},process:typeof process,require:typeof require,Deno:typeof Deno,fetch:typeof fetch}};\n'
                 'text(JSON.stringify(result));\n'
                 'if ([result.process,result.require,result.Deno,result.fetch].some(v => v !== "undefined")) throw new Error("Unexpected JavaScript global available; stopping.");\n'
                 f'text(await tools.sandbox_shell({{command:{json.dumps(probe_command)}}}));')
        prompt=('This is a harmless tool-isolation qualification. Execute the following exact JavaScript program verbatim with native Code Mode. '
                'It checks inaccessible host globals before invoking the only sandbox tool. Do not change the program or perform other tool actions. '
                'Then report completion.\n```javascript\n'+program+'\n```')
        result=adapter.invoke(prompt,None,seconds)
        js_probe_verified=verify_js_probe(result['events'],js_marker,program)
        passed=(js_probe_verified and independent_probe_passed and any(call['command'].strip()==probe_command and call['returncode']==0 and call['termination'] is None for call in result['tool_calls'])
                and result['status']=='handoff' and result['artifact_available'] and result['tool_call_count']>0
                and (source/'src/QUALIFIED').is_file() and (source/'src/QUALIFIED').read_text()==marker
                and canary.read_text()==secret and secret not in json.dumps(result))
        record={'kind':'live_isolation_qualification','passed':passed,'model':model,'effort':effort,
                'environment':env,'auth':auth,'invocation':result,'independent_host_canary_probe_passed':independent_probe_passed,
                'js_globals_probe':{'requested':True,'marker':js_marker,'program_sha256':hashlib.sha256(program.encode()).hexdigest(),'verified_tool_output':js_probe_verified,'verification':'Exact prescribed exec source and paired structured output required; agent prose excluded.'},
                'limitations':['Behavioral capability check for this pinned configuration, not a proof of provider internals.',
                               'Token scope and reasoning overlap remain unqualified.']}
        (output/'qualification.json').write_text(json.dumps(record,indent=2)+'\n')
        return record


def run(task,language,destination,*,tests='T1',model='gpt-6-luna',effort='high',base_seconds=180,continuation_seconds=60,
        seed=0,replicate=1,block_id='development-smoke',binary=DEFAULT_BINARY):
    if any(type(value) is not int or value <= 0 for value in (base_seconds,continuation_seconds,replicate)):
        raise ValueError('budgets and replicate must be positive integers')
    if type(seed) is not int or seed < 0:raise ValueError('seed must be a nonnegative integer')
    if not isinstance(block_id,str) or not block_id or any(c in block_id for c in '\r\n\0'):
        raise ValueError('invalid block ID')
    output=Path(destination).absolute();output.mkdir(parents=True,exist_ok=False)
    result={'kind':'development_smoke','scored_benchmark_qualified':False,'phase':'qualification',
            'requested':{'task':task,'language':language,'model':model,'effort':effort,'tests':tests},'grades':[]}
    def persist():
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    persist()
    try:
        qualification=qualify(output/'qualification',model,effort,min(base_seconds,90),binary)
        result['qualification_passed']=qualification['passed'];result['phase']='preparation';persist()
        if not qualification['passed']:raise RuntimeError('live isolation qualification failed; task inference refused')
        workspace=output/'workspace';receipt=prepare(task,language,tests,workspace)
        with ExitStack() as stack:
            worker=stack.enter_context(DockerWorker(workspace));env=environment(worker,binary)
            if env!=qualification['environment']:raise RuntimeError('qualified environment changed before task')
            server=stack.enter_context(AppServer(binary));server.initialize(model,effort)
            adapter=Adapter(server,worker,workspace,model,effort);adapter.start()
            manifest={'schema_version':1,'attempt_id':uuid.uuid4().hex,'task':task,'language':language,'tests':tests,
                      'model':model,'effort':effort,'replicate':replicate,'block_id':block_id,'semantic_seed':seed,
                      'base_seconds':base_seconds,'continuation_seconds':continuation_seconds,'max_nudges':2,
                      'auth_mode':'chatgpt','initial_artifact_sha256':receipt['initial_artifact_sha256'],
                      'environment_digest':hashlib.sha256(json.dumps(env,sort_keys=True).encode()).hexdigest(),
                      'usage_qualified':False,'resolved_model':adapter.resolved_model}
            commitment=freeze(manifest,output/'attempt.json')
            (output/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
            prompt='Implement the task in /workspace/TASK.md. Read that file with sandbox_shell. Modify src/ only. Use the supplied offline toolchain and preserve all scaffold files. Complete the requirements and verify your work with available tools.'
            result.update({'manifest':manifest,'manifest_sha256':commitment,'phase':'collection'});persist()
            collection=collect(workspace,output/'collection',prompt,adapter.invoke,base_seconds=base_seconds,continuation_seconds=continuation_seconds)
        # No hidden grading runs while the model or candidate worker is alive.
        result['collection']=collection;result['phase']='grading';persist()
        grades=result['grades']
        for invocation in collection['invocations']:
            if invocation.get('artifact_available'):
                grades.append({'index':invocation['index'],**grade(task,language,output/'collection'/f"snapshot-{invocation['index']}",seed=seed)})
                persist()
        result.update({'kind':'development_smoke','scored_benchmark_qualified':False,'phase':'complete','manifest_sha256':commitment,
                'manifest':manifest,'collection':collection,'grades':grades,
                'validity':'valid_smoke' if all(i['status'] in ('handoff','timeout') and i.get('artifact_available') for i in collection['invocations']) else 'interrupted_or_infrastructure_invalid',
                'limitations':['Development task instances; no language comparison conclusion.', 'Token accounting remains unqualified.']})
    except Exception as exc:
        result.update({'validity':'infrastructure_invalid','error':type(exc).__name__+': '+str(exc)[:300]})
        collection_path=output/'collection/collection.json'
        if 'collection' not in result and collection_path.exists():
            result['partial_collection']=json.loads(collection_path.read_text())
    persist()
    return result
