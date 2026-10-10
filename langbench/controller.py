"""Fixed handoff policy. The executor is supplied by a qualified isolation adapter.

No grader or hidden outcome is accepted by the collection controller.
"""
import hashlib
import json
from pathlib import Path
import shutil
from .core import digest_tree, copy_workspace
from .metrics import normalize_usage, reconcile_provider_usage

NUDGES = (
    'Continue working on the original task. Review the requirements and complete any unfinished work using the tools available in this run.',
    'Check the current implementation against the original requirements, investigate problems you find, and complete the task before concluding.',
)

def collect(workspace, output, prompt, invoke, *, base_seconds=7200, continuation_seconds=1800):
    """invoke(prompt, session_id, seconds) -> terminal result plus JSON events.

Result keys: status (handoff/timeout/infrastructure_error/quota), session_id,
seconds, events. Adapter must return only after all candidate processes stop.
"""
    if base_seconds <= 0 or continuation_seconds <= 0:
        raise ValueError('budgets must be positive')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    invocations = []
    session = None
    for index, message in enumerate((prompt, *NUDGES)):
        result = invoke(message, session, base_seconds if index == 0 else continuation_seconds)
        if result.get('status') not in ('handoff', 'timeout', 'infrastructure_error', 'quota'):
            raise ValueError('invalid executor terminal status')
        if not isinstance(result.get('events'), list) or type(result.get('seconds')) not in (int, float) or result['seconds'] < 0:
            raise ValueError('invalid executor telemetry')
        new_session = result.get('session_id')
        if session is not None and new_session != session:
            result['status'] = 'infrastructure_error'
            result['error'] = 'resume_session_changed'
        if result['status'] == 'handoff' and (not isinstance(new_session, str) or not new_session):
            result['status'] = 'infrastructure_error'
            result['error'] = 'missing_resume_session'
        session = new_session
        snapshot = output / f'snapshot-{index}'
        artifact_hash = digest_tree(workspace, ignore_root_artifacts=True)
        copy_workspace(workspace, snapshot)
        if digest_tree(snapshot, ignore_root_artifacts=True) != artifact_hash or digest_tree(workspace, ignore_root_artifacts=True) != artifact_hash:
            raise RuntimeError('workspace changed during quiescent snapshot')
        record = {**result, 'index':index, 'artifact_sha256':artifact_hash,
                  'prompt_sha256':hashlib.sha256(message.encode()).hexdigest()}
        invocations.append(record)
        with (output / 'events.jsonl').open('a') as handle:
            for event in result['events']:
                handle.write(json.dumps({'invocation':index, 'event':event})+'\n')
        (output / 'collection.json').write_text(json.dumps({'invocations':invocations}, indent=2)+'\n')
        if result['status'] != 'handoff' or not isinstance(session, str) or not session:
            break
    return {'invocations':invocations, 'nudges':len(invocations)-1,
            'active_seconds':sum(item['seconds'] for item in invocations),
            'usage':normalize_usage([event for item in invocations for event in item['events']]),
            'provider_usage':reconcile_provider_usage(invocations)}
