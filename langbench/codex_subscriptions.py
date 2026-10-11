"""Adaptive Sol subscription adapter; historical smoke runner remains unchanged."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import time
import uuid

from .appserver import AppServer, DEFAULT_BINARY, ProtocolViolation
from .assistance import collect, persist, POLICY, terminal_status
from .core import prepare
from .grading import grade
from .live import Adapter as HistoricalAdapter, environment, verify_js_probe
from .metrics import reconcile_provider_usage
from .subscriptions import capture_invocation, source_digest, runtime_binding, validate_qualification, sha
from .worker import DockerWorker

MODEL = 'gpt-6-sol'
EFFORT = 'medium'


def exact(model, effort):
    if (model, effort) != (MODEL, EFFORT):
        raise ValueError('only exact gpt-6-sol medium is authorized; no fallback')


class SubscriptionServer:
    """Drop account payloads; convert explicit allowance revocation to quota stop."""
    def __init__(self, server):
        self.server = server
        self.thread = None
        self.turn = None
        self.allowance_revoked = False

    @property
    def cwd(self):
        return self.server.cwd

    def call(self, method, params, **kwargs):
        result = self.server.call(method, params, **kwargs)
        if method == 'thread/start': self.thread = result.get('thread', {}).get('id')
        if method == 'turn/start': self.turn = result.get('turn', {}).get('id')
        return result

    def send(self, *args, **kwargs):
        return self.server.send(*args, **kwargs)

    def close(self):
        return self.server.close()

    def next(self, deadline):
        while True:
            message = self.server.next(deadline)
            if message.get('method', '').startswith('account/'):
                if (message.get('params') or {}).get('ordinaryUsageAllowed') is False:
                    self.allowance_revoked = True
                    return {'method':'turn/completed', 'params':{'threadId':self.thread,
                            'turn':{'id':self.turn, 'status':'failed', 'items':[],
                                    'error':{'codexErrorInfo':'usageLimitExceeded'}}}}
                continue
            return message


class RecordingWorker:
    """Synchronous command boundary; hashing uses the real worker, not this proxy."""
    def __init__(self, worker):
        self.worker = worker
        self.records = []

    @property
    def alive(self):
        return self.worker.alive

    def execute(self, command, **kwargs):
        started = time.time()
        before = source_digest(self.worker)
        outcome = self.worker.execute(command, **kwargs)
        after = source_digest(self.worker)
        self.records.append({'arguments': {'command': command}, 'started_at': started,
                             'source_before': before, 'source_after': after, 'result': outcome})
        return outcome


def terminal_text(events):
    messages = {}
    for event in events:
        if event.get('method') not in ('item/completed', 'turn/completed'):
            continue
        params = event.get('params', {})
        items = [params.get('item', {})] if event['method'] == 'item/completed' else params.get('turn', {}).get('items', [])
        for item in items:
            if item.get('type') == 'agentMessage' and isinstance(item.get('text'), str):
                messages[item.get('id', item['text'])] = item['text']
    return '\n'.join(messages.values())


def output_limited(events):
    """Only explicit native reasons count; never infer a limit from token count."""
    for event in events:
        params = event.get('params', {})
        if event.get('method') == 'rawResponse/completed':
            if params.get('finishReason') in ('length', 'max_output_tokens'):
                return True
            response = params.get('response') or {}
            if response.get('status') == 'incomplete' and (response.get('incomplete_details') or {}).get('reason') == 'max_output_tokens':
                return True
    return False


class CodexAdapter(HistoricalAdapter):
    """Reuse validated capability checks, but defer export until settlement."""
    def __init__(self, server, worker, workspace, *, model=MODEL, effort=EFFORT, trace=None):
        exact(model, effort)
        self.real_worker = worker
        self.recording = RecordingWorker(worker)
        super().__init__(SubscriptionServer(server), self.recording, workspace, model, effort)
        self.trace = Path(trace) if trace else None
        if self.trace:
            self.trace.mkdir(parents=True, exist_ok=True)
        self.closed = False
        self.invocations = []

    def export(self):
        # Historical invoke calls this before returning. Never export there:
        # interruption acknowledgement is not a settlement proof.
        return None

    def close(self):
        if not self.closed:
            self.server.close()
            self.closed = True

    def invoke(self, prompt, session, seconds):
        if self.closed:
            raise RuntimeError('closed Codex session cannot continue')
        if type(seconds) is not int or seconds <= 0:
            raise ValueError('positive integer deadline required')
        if session is not None and session != self.thread:
            raise ProtocolViolation('explicit thread continuity mismatch')
        self.recording.records = []
        preflight_started = time.monotonic()
        try:
            allowed = self.server.call('account/rateLimits/read', {}, timeout=min(10, seconds)).get('ordinaryUsageAllowed')
        except Exception:
            allowed = None
        preflight_seconds = time.monotonic()-preflight_started
        if allowed is not True:
            self.close()
            result = {'status':'quota' if allowed is False else 'infrastructure_error',
                      'session_id':self.thread, 'turn_id':None, 'seconds':0,
                      'events':[], 'tool_calls':[], 'error':'ordinary_subscription_allowance_unavailable',
                      'ordinary_usage_allowed':allowed, 'inference_started':False}
        else:
            result = super().invoke(prompt, session, seconds)
            result.update(ordinary_usage_allowed=True, inference_started=True)
        result['allowance_preflight_seconds'] = preflight_seconds
        result['ordinary_allowance_revoked'] = self.server.allowance_revoked
        result['artifact_available'] = False  # only capture_invocation may assert availability
        result['terminal_text'] = terminal_text(result['events'])
        result['completion_kind'] = 'model_output_limit' if output_limited(result['events']) else result['status']
        if result['completion_kind'] == 'model_output_limit':
            result['status'] = 'model_output_limit'
            result['terminal_text'] = ''  # a length stop never authorizes an adaptive nudge
        records = iter(self.recording.records)
        tool_records = []
        for call in result['tool_calls']:
            if call.get('rejected'):
                tool_records.append({'call_id': call.get('call_id'), 'arguments': {'command': call.get('command')},
                                     'rejected': True, 'result': call, 'source_before': None, 'source_after': None})
            else:
                recorded = next(records)
                tool_records.append({**recorded, 'call_id': call.get('call_id')})
        result['tool_records'] = tool_records
        result['cleanup_unsettled'] = []
        # Only this synchronous controller can dispatch dynamic tools. On a
        # nonterminal/failed turn, kill the complete controller process group
        # before accepting any source snapshot; queued calls cannot execute.
        if result['status'] != 'handoff' or result['completion_kind'] == 'model_output_limit':
            try:
                self.close()
            except Exception as exc:
                result['cleanup_unsettled'].append({'component': 'transport', 'error_type': type(exc).__name__})
        result['quiescent'] = not result['cleanup_unsettled']
        if not self.real_worker.alive and self.real_worker.retained_source is not None:
            result['status'] = 'timeout'
        # Keep only the known protocol error category, never server exception text.
        if result.get('status') == 'infrastructure_error' and isinstance(result.get('error'), str):
            result['error'] = 'codex_protocol_or_transport_failure'
        result['index'] = len(self.invocations)
        self.invocations.append(result)
        result['native_usage_reconciliation'] = reconcile_provider_usage(self.invocations)
        if self.trace:
            persist(self.trace / f'invocation-{result["index"]}.json', result)
        return result


def binding(worker, binary):
    source_files = ('codex_subscriptions.py', 'appserver.py', 'live.py', 'metrics.py', 'assistance.py',
                    'subscriptions.py', 'worker.py')
    return {'schema_version': 1, 'provider': 'codex', 'model': MODEL, 'effort': EFFORT,
            'auth_mode': 'chatgpt', 'runtime': runtime_binding(), 'assistance_policy': POLICY,
            'environment': environment(worker, binary),
            'source_sha256': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in source_files}}


def qualify_codex(output, *, model=MODEL, effort=EFFORT, binary=DEFAULT_BINARY, seconds=120):
    exact(model, effort)
    output = Path(output).absolute(); output.mkdir(parents=True, exist_ok=False)
    receipt = {'schema_version': 1, 'kind': 'codex_subscription_qualification', 'passed': False,
               'provider': 'codex', 'model': model, 'effort': effort, 'invocations': []}
    persist(output / 'qualification.json', receipt)
    try:
        with tempfile.TemporaryDirectory(prefix='langbench-sol-probe-') as temporary, ExitStack() as stack:
            root = Path(temporary); workspace = root / 'workspace'; (workspace / 'src').mkdir(parents=True)
            canary = root / 'HOST_CANARY'; secret = uuid.uuid4().hex; canary.write_text(secret)
            worker = stack.enter_context(DockerWorker(workspace, runtime='seven', retention='seal-v1'))
            frozen = binding(worker, binary)
            server = AppServer(binary)
            adapter = CodexAdapter(server, worker, workspace, trace=output / 'trace')
            stack.callback(adapter.close)
            auth = server.initialize(model, effort); adapter.start()
            marker = uuid.uuid4().hex
            command = f'test ! -e {canary} && printf %s {marker} > /workspace/src/QUALIFIED'
            independent = worker.execute(['test', '!', '-e', str(canary)])
            js_marker = 'LANGBENCH_JS_GLOBALS_'+uuid.uuid4().hex
            program = (f'const result = {{marker:{json.dumps(js_marker)},process:typeof process,require:typeof require,Deno:typeof Deno,fetch:typeof fetch}};\n'
                       'text(JSON.stringify(result));\n'
                       'if ([result.process,result.require,result.Deno,result.fetch].some(v => v !== "undefined")) throw new Error("Unexpected JavaScript global available; stopping.");\n'
                       f'text(await tools.sandbox_shell({{command:{json.dumps(command)}}}));')
            first = adapter.invoke('Harmless qualification: execute this exact JavaScript with Code Mode, unchanged, then report completion.\n```javascript\n'+program+'\n```', None, seconds)
            first = capture_invocation(worker, workspace, first)
            receipt['invocations'].append(first)
            first_ok = (first['status'] == 'handoff' and first['artifact_available'] and
                        verify_js_probe(first['events'], js_marker, program) and independent['returncode'] == 0 and
                        independent['termination'] is None and (workspace/'src/QUALIFIED').read_text() == marker and
                        any(t['arguments']['command'] == command and t['result']['returncode'] == 0 for t in first['tool_records']))
            if not first_ok:
                raise RuntimeError('initial isolation probe failed')
            second = adapter.invoke('Use sandbox_shell to execute exactly: cat /workspace/src/QUALIFIED. Then finish with BENCHMARK_STATUS: COMPLETE.', first['session_id'], seconds)
            second = capture_invocation(worker, workspace, second)
            receipt['invocations'].append(second)
            resumed = (second['status'] == 'handoff' and terminal_status(second['terminal_text']) == 'COMPLETE' and second['session_id'] == first['session_id'] and
                       any(t['arguments']['command'].strip() == 'cat /workspace/src/QUALIFIED' and marker in t['result'].get('stdout', '') for t in second['tool_records']))
            native = reconcile_provider_usage(receipt['invocations'])
            receipt.update(binding=frozen, binding_sha256=sha(frozen), auth=auth, usage=native,
                           checks={'exact_js_and_host_canary': first_ok, 'same_session_resume': resumed,
                                   'native_usage_complete': native['complete']},
                           passed=bool(resumed and native['complete'] and canary.read_text() == secret and secret not in json.dumps(receipt)))
    except Exception as exc:
        receipt['passed'] = False
        receipt['error_type'] = type(exc).__name__
    persist(output / 'qualification.json', receipt)
    return receipt


def collection_validity(invocations):
    return 'valid_development' if invocations and all(
        i['status'] in ('handoff', 'timeout', 'model_output_limit') and not i.get('cleanup_unsettled')
        for i in invocations) else 'infrastructure_invalid'


def run_codex(task, language, output, *, provider='codex', model=MODEL, effort=EFFORT, tests='T1', seed=0,
              replicate=1, block_id=None, base_seconds=900, continuation_seconds=180, qualification=None,
              binary=DEFAULT_BINARY):
    exact(model, effort)
    if provider != 'codex':
        raise ValueError('provider must be codex')
    if not qualification or qualification.get('passed') is not True:
        raise ValueError('external qualified Codex adapter required')
    if any(type(v) is not int or v <= 0 for v in (replicate, base_seconds, continuation_seconds)) or type(seed) is not int or seed < 0:
        raise ValueError('invalid attempt budgets/identity')
    output = Path(output).absolute(); output.mkdir(parents=True, exist_ok=False)
    result = {'schema_version': 1, 'kind': 'subscription_attempt', 'phase': 'preparation', 'grades': [],
              'scored_benchmark_qualified': False, 'timing': {},
              'requested': dict(task=task, language=language, provider=provider, model=model, effort=effort, tests=tests)}
    persist(output/'result.json', result)
    started = time.monotonic(); phase = started
    try:
        workspace = output/'workspace'; preparation = prepare(task, language, tests, workspace)
        with ExitStack() as stack:
            worker = stack.enter_context(DockerWorker(workspace, runtime='seven', retention='seal-v1'))
            frozen = binding(worker, binary); validate_qualification(qualification, frozen)
            server = AppServer(binary); adapter = CodexAdapter(server, worker, workspace, trace=output/'trace')
            stack.callback(adapter.close)
            server.initialize(model, effort); adapter.start()
            manifest = {'schema_version':1, 'kind':'subscription_attempt_manifest', 'attempt_id':uuid.uuid4().hex,
                        **result['requested'], 'semantic_seed':seed, 'replicate':replicate, 'block_id':block_id,
                        'base_seconds':base_seconds, 'continuation_seconds':continuation_seconds, 'max_nudges':2,
                        'assistance_policy':POLICY, 'initial_artifact_sha256':preparation['initial_artifact_sha256'],
                        'binding':frozen, 'qualification_sha256':sha(qualification)}
            data = json.dumps(manifest, sort_keys=True).encode(); (output/'attempt.json').write_bytes(data)
            result.update(manifest=manifest, manifest_sha256=hashlib.sha256(data).hexdigest(), phase='collection')
            result['timing']['preparation_and_adapter_seconds'] = time.monotonic()-phase
            persist(output/'result.json', result); phase = time.monotonic()
            def invoke(prompt, session, seconds):
                return capture_invocation(worker, workspace, adapter.invoke(prompt, session, seconds))
            collection = collect(workspace, output/'collection',
                f'Implement /workspace/TASK.md in {language}. Read it using sandbox_shell. Edit src/ only, preserving scaffold files. Complete and verify the requirements with the supplied offline toolchain.',
                invoke, base_seconds=base_seconds, continuation_seconds=continuation_seconds)
            collection['native_usage_reconciliation'] = reconcile_provider_usage(collection['invocations'])
            persist(output/'collection/collection.json', collection)
            result['collection'] = collection
        result['timing']['collection_and_cleanup_seconds'] = time.monotonic()-phase
        result['phase'] = 'grading'; persist(output/'result.json', result); phase = time.monotonic()
        for checkpoint in collection['checkpoints']:
            if checkpoint['artifact_available']:
                result['grades'].append({'index':checkpoint['index'], **grade(task, language, checkpoint['artifact_path'], seed=seed, runtime='seven')})
                persist(output/'result.json', result)
        result['timing']['private_grading_seconds'] = time.monotonic()-phase
        result.update(phase='complete', validity=collection_validity(collection['invocations']))
    except Exception as exc:
        result.update(validity='infrastructure_invalid', error_type=type(exc).__name__)
        partial = output/'collection/collection.json'
        if partial.exists() and 'collection' not in result:
            result['partial_collection'] = json.loads(partial.read_text())
    result['timing']['whole_attempt_seconds'] = time.monotonic()-started
    persist(output/'result.json', result)
    return result
