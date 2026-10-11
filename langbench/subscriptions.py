"""Subscription matrix entrypoints. Qualification never occurs inside a coding attempt."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import time
import uuid
from .assistance import collect, persist, POLICY, STATUS_INSTRUCTION, terminal_status
from .core import prepare,digest_tree,ROOT,copy_workspace
from .grading import grade
from .worker import DockerWorker
from .provider_cli import ProviderCLI,ROUTES
from .provider_usage import summarize_invocations


def sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def runtime_binding():
    path=ROOT/'configs/toolchain-seven.json'
    if not path.is_file():
        from importlib.resources import files
        path=files('langbench_config').joinpath('toolchain-seven.json')
    return {'runtime':'seven','toolchain_config_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def source_digest(worker):
    if not worker.alive:
        retained=getattr(worker,'retained_source',None)
        return digest_tree(retained/'src') if retained else None
    with tempfile.TemporaryDirectory(prefix='langbench-source-') as temporary:
        target=Path(temporary)/'export';worker.export(target)
        return digest_tree(target/'src')


def export_workspace(worker,workspace):
    temporary=workspace.with_name(workspace.name+'-export')
    worker.export(temporary)
    if workspace.exists():shutil.rmtree(workspace)
    temporary.rename(workspace)


def capture_invocation(worker,workspace,invocation):
    """Recover only a sealed terminal source; transport usage remains independent."""
    if getattr(worker,'retention','legacy')=='seal-v1':
        errors=invocation.get('cleanup_unsettled',[])
        candidate_quiescent=not any(error.get('component')=='bridge' for error in errors)
        if worker.alive and candidate_quiescent and (errors or invocation.get('status')=='timeout'):
            worker.seal_quiescent()
            worker.close()
        if worker.retained_source is not None:
            retained=worker.retained_source
            expected=worker.retention_receipt['source_sha256']
            if digest_tree(retained/'src')!=expected:raise RuntimeError('sealed source changed')
            staged=workspace.with_name(workspace.name+'-sealed')
            copy_workspace(workspace,staged)
            shutil.rmtree(staged/'src')
            shutil.copytree(retained/'src',staged/'src')
            if digest_tree(staged/'src')!=expected:raise RuntimeError('sealed source copy mismatch')
            shutil.rmtree(workspace);staged.rename(workspace)
            invocation.update(artifact_available=True,artifact_retention=dict(worker.retention_receipt),
                              artifact_kind='terminal_sealed')
            return invocation
        if worker.retention_receipt is not None:
            invocation['artifact_retention']=dict(worker.retention_receipt)
    if not invocation.get('quiescent',False):
        worker.close();invocation['artifact_available']=False
    elif worker.alive:
        export_workspace(worker,workspace);invocation['artifact_available']=True
    else:
        invocation.update(status='timeout',artifact_available=False,error='candidate_worker_retired; final source unavailable')
    return invocation


def bound_identity(adapter,worker):
    return {'adapter':adapter.identity,'runtime':runtime_binding(),'worker':worker.qualification,
            'assistance_policy':POLICY,'schema_version':1,
            'adapter_source_sha256':sha({name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('subscriptions.py','provider_cli.py','provider_transport.py','mcp_bridge.py','assistance.py','provider_usage.py','worker.py')})}


def validate_qualification(qualification,identity):
    if not isinstance(qualification,dict) or qualification.get('passed') is not True:
        raise ValueError('passed external qualification required')
    if qualification.get('binding')!=identity or qualification.get('binding_sha256')!=sha(identity):
        raise ValueError('qualification binding mismatch')


def qualify_provider(provider,output,*,model,effort,binary=None,seconds=120,retention='legacy'):
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
            adapter=ProviderCLI(provider,output/'trace',lambda c,t:worker.execute(c,timeout=t,output_limit=256*1024),lambda:source_digest(worker),model=model,effort=effort,binary=binary)
            stack.callback(adapter.close)
            receipt['binding']=bound_identity(adapter,worker);receipt['binding_sha256']=sha(receipt['binding'])
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
                'wire_usage_complete':bool(requests) and all(r.get('response_complete') and r.get('usage') for r in requests),
                'wire_model_effort_enforced':bool(requests) and not adapter.transport.fatal}
            receipt['passed']=bool(all(receipt['checks'].values()) and executed and receipt['independent_host_canary_absent'] and second['status']=='handoff' and second['session_id']==first['session_id'] and (workspace/'src/QUALIFIED').read_text()==marker and canary.read_text()==secret and secret not in json.dumps(receipt))
            receipt['usage_summary']=summarize_invocations(receipt['invocations'])
    except Exception as error:
        receipt['passed']=False
        receipt['error']=type(error).__name__+' (details suppressed to protect provider credentials)'
    persist(output/'qualification.json',receipt)
    return receipt


def run_subscription(task,language,output,*,provider,model,effort,tests='T1',seed=0,replicate=1,block_id=None,
                     base_seconds=900,continuation_seconds=180,qualification=None,binary=None,retention='legacy'):
    if tests not in ('T0','T1') or type(seed) is not int or seed<0:raise ValueError('invalid treatment')
    if provider not in ROUTES or model!=ROUTES[provider]['model']:raise ValueError('invalid provider model')
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
            adapter=ProviderCLI(provider,output/'trace',lambda c,t:worker.execute(c,timeout=t,output_limit=256*1024),lambda:source_digest(worker),model=model,effort=effort,binary=binary)
            stack.callback(adapter.close)
            binding=bound_identity(adapter,worker);validate_qualification(qualification,binding)
            manifest={'schema_version':1,'kind':'subscription_attempt_manifest','attempt_id':uuid.uuid4().hex,
                'task':task,'language':language,'tests':tests,'provider':provider,'model':model,'effort':effort,
                'semantic_seed':seed,'replicate':replicate,'block_id':block_id,'base_seconds':base_seconds,
                'continuation_seconds':continuation_seconds,'max_nudges':2,'assistance_policy':POLICY,
                'initial_artifact_sha256':preparation['initial_artifact_sha256'],'binding':binding,
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
            collection['usage_summary']=summarize_invocations(collection['invocations'])
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
