"""Visible-handoff assistance only; deliberately has no grading dependency."""
import hashlib
import json
import time
from pathlib import Path
from .core import copy_workspace, digest_tree

POLICY = 'terminal-status-v1'
NUDGE = ('Continue the existing task using the available sandbox tool. No additional '
         'permission is needed for edits within the permitted workspace. Finish with '
         'the requested status marker.')
STATUS_INSTRUCTION = ('End your final response with exactly one standalone line: '
                      'BENCHMARK_STATUS: COMPLETE, BENCHMARK_STATUS: INCOMPLETE, or '
                      'BENCHMARK_STATUS: BLOCKED. Choose the status matching your work.')


def terminal_status(text):
    if not isinstance(text, str):
        return None
    lines = text.strip().splitlines()
    markers = [line for line in lines if 'BENCHMARK_STATUS:' in line]
    if len(markers) != 1 or not lines or markers[0] != lines[-1]:
        return None
    return {'BENCHMARK_STATUS: '+s:s for s in ('COMPLETE','INCOMPLETE','BLOCKED')}.get(markers[0])


def decision(result, used):
    status = terminal_status(result.get('terminal_text'))
    if result.get('status') != 'handoff':
        return False, 'transport_'+str(result.get('status')), status
    if status is None:
        return False, 'handoff_status_unknown', None
    if status == 'COMPLETE':
        return False, 'declared_complete', status
    if used >= 2:
        return False, 'assistance_limit', status
    return True, 'visible_'+status.lower(), status


def persist(path, value):
    """Atomic replacement plus fsync; the enclosing attempt directory is unique."""
    import os
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def collect(workspace, output, prompt, invoke, *, base_seconds=900, continuation_seconds=180):
    for seconds in (base_seconds, continuation_seconds):
        if type(seconds) is not int or seconds <= 0:
            raise ValueError('positive integer work windows required')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    receipt = {'schema_version':1,'policy_version':POLICY,'invocations':[],
               'checkpoints':[],'interventions':[],'active_seconds':0,'stop_reason':None}
    session = None
    message = prompt+'\n\n'+STATUS_INSTRUCTION
    def ledger(event):
        import os
        with (output/'interventions.jsonl').open('a') as handle:
            handle.write(json.dumps(event)+'\n');handle.flush();os.fsync(handle.fileno())
    for index in range(3):
        if index:
            ledger({'event':'dispatch_requested','intervention_index':index-1,'timestamp':time.time()})
        result = invoke(message, session, base_seconds if index == 0 else continuation_seconds)
        if index:
            ledger({'event':'invocation_returned','intervention_index':index-1,'timestamp':time.time(),'status':result.get('status')})
            receipt['interventions'][index-1]['delivery_status']='invocation_returned'
        if result.get('status') not in ('handoff','timeout','quota','infrastructure_error'):
            raise ValueError('invalid adapter status')
        if session is not None and result.get('session_id') != session:
            result = {**result,'status':'infrastructure_error','error':'resume_session_changed'}
        session = result.get('session_id')
        if result['status']=='handoff' and (not isinstance(session,str) or not session):
            result = {**result,'status':'infrastructure_error','error':'missing_session'}
        eligible, reason, declared = decision(result,index)
        available=result.get('artifact_available',True)
        digest=None;snapshot=None
        if available:
            digest = digest_tree(workspace,ignore_root_artifacts=True)
            snapshot = output/f'snapshot-{index}'
            copy_workspace(workspace,snapshot)
            if digest_tree(snapshot,ignore_root_artifacts=True)!=digest or digest_tree(workspace,ignore_root_artifacts=True)!=digest:
                raise RuntimeError('non-quiescent snapshot')
        record = {**result,'index':index,'prompt':message,
                  'prompt_sha256':hashlib.sha256(message.encode()).hexdigest()}
        receipt['invocations'].append(record)
        receipt['checkpoints'].append({'index':index,'label':'first_handoff' if index==0 else f'reactivation_{index}',
            'artifact_path':str(snapshot) if snapshot else None,'artifact_available':available,'artifact_sha256':digest,'transport_status':result['status'],
            'declared_status':declared,'nudge_eligible':eligible,'decision_reason':reason})
        receipt['active_seconds'] += result['seconds']
        receipt['stop_reason'] = None if eligible else reason
        persist(output/'collection.json',receipt)
        if not eligible:
            break
        message = NUDGE
        intervention = {'actor':'controller','category':'reactivation','scope':'candidate_attempt',
            'timestamp':time.time(),'reason':reason,'prompt':message,
            'prompt_sha256':hashlib.sha256(message.encode()).hexdigest(),'source_before':digest,
            'preceding_checkpoint':index,'delivery_status':'planned'}
        ledger({'event':'planned',**intervention})
        receipt['interventions'].append(intervention)
        persist(output/'collection.json',receipt)
    return receipt
