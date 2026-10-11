"""Fake protocol/lifecycle tests; these never launch Codex or Docker."""
from collections import deque
from pathlib import Path
import tempfile
import re
import json
import unittest
from unittest.mock import patch

from langbench.codex_subscriptions import CodexAdapter, MODEL, exact, collection_validity, qualify_codex
from langbench.appserver import ProtocolViolation
from langbench.assistance import decision
from tests.test_metrics_live import response, total


class Server:
    cwd = '/empty'
    def __init__(self, events):
        self.events = deque(events); self.calls = []; self.sent = []; self.closed = False; self.turn = 0
    def call(self, method, params, **kwargs):
        self.calls.append((method, params))
        if method == 'account/rateLimits/read': return {'ordinaryUsageAllowed':True,'accountId':'NEVER_ARCHIVE'}
        if method == 'thread/start': return {'model':MODEL,'thread':{'id':'thread'}}
        if method == 'turn/start':
            self.turn += 1
            return {'turn':{'id':str(self.turn),'items':[]}}
        return {}
    def send(self, message, **kwargs): self.sent.append(message)
    def next(self, deadline):
        if not self.events: raise TimeoutError()
        return self.events.popleft()
    def close(self): self.closed = True


class Worker:
    alive = True
    retained_source = None
    def __init__(self): self.commands = []; self.exported = False
    def execute(self, command, **kwargs):
        self.commands.append(command)
        return {'returncode':0,'termination':None,'stdout':'okay','stderr':'','seconds':.01}
    def export(self, path):
        self.exported = True
        raise AssertionError('Historical export must never run')


def completed(turn='1', text='BENCHMARK_STATUS: COMPLETE', status='completed', code=None):
    return {'method':'turn/completed','params':{'threadId':'thread','turn':{'id':turn,'status':status,
            'items':[{'type':'agentMessage','id':'message-'+turn,'text':text}], 'error':{'codexErrorInfo':code}}}}


def tool(name='sandbox_shell', args=None):
    return {'id':20,'method':'item/tool/call','params':{'threadId':'thread','turnId':'1','callId':'call-1',
            'tool':name,'arguments':args if args is not None else {'command':'sh build.sh'}}}


class CodexAdaptiveTests(unittest.TestCase):
    def make(self, events):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        server = Server(events); worker = Worker()
        adapter = CodexAdapter(server, worker, Path(temporary.name)/'workspace')
        adapter.start()
        return adapter, server, worker

    def test_qualification_teardown_failure_revokes_pass(self):
        # All qualification checks succeed first; only teardown is made to fail.
        for failing in ('adapter', 'worker'):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as temp:
                flags = {'resumed':False, 'reconciled':False}
                class QualifiedWorker:
                    def __init__(self, workspace, **kwargs):self.workspace=workspace
                    def __enter__(self):return self
                    def __exit__(self, *args):
                        if failing=='worker':
                            assert flags['resumed'] and flags['reconciled']
                            raise RuntimeError('worker teardown failed')
                    def execute(self, *args, **kwargs):return {'returncode':0,'termination':None}
                class QualifiedServer:
                    def __init__(self,*args):pass
                    def initialize(self,*args):return {'auth_mode':'chatgpt'}
                class QualifiedAdapter:
                    def __init__(self, server, worker, workspace, **kwargs):self.workspace=workspace
                    def start(self):pass
                    def close(self):
                        if failing=='adapter':
                            assert flags['resumed'] and flags['reconciled']
                            raise RuntimeError('adapter teardown failed')
                    def invoke(self,prompt,session,seconds):
                        if session is None:
                            command=re.search(r'test ! -e [^"\n]+ > /workspace/src/QUALIFIED',prompt).group()
                            marker=re.search(r'printf %s ([a-f0-9]+)',command).group(1)
                            (self.workspace/'src/QUALIFIED').write_text(marker)
                            records=[{'arguments':{'command':command},'result':{'returncode':0}}]
                        else:
                            flags['resumed']=True
                            records=[{'arguments':{'command':'cat /workspace/src/QUALIFIED'},
                                      'result':{'stdout':(self.workspace/'src/QUALIFIED').read_text()}}]
                        return {'status':'handoff','artifact_available':True,'session_id':'same',
                                'terminal_text':'BENCHMARK_STATUS: COMPLETE','events':[], 'tool_records':records}
                def reconcile(invocations):
                    flags['reconciled']=True
                    return {'complete':True}
                module='langbench.codex_subscriptions.'
                with patch(module+'DockerWorker',QualifiedWorker), patch(module+'AppServer',QualifiedServer), \
                     patch(module+'CodexAdapter',QualifiedAdapter), patch(module+'binding',return_value={}), \
                     patch(module+'verify_js_probe',return_value=True), patch(module+'reconcile_provider_usage',side_effect=reconcile), \
                     patch(module+'capture_invocation',side_effect=lambda worker,workspace,invocation:invocation):
                    output=Path(temp)/'qualification'
                    receipt=qualify_codex(output)
                self.assertTrue(flags['resumed']);self.assertTrue(flags['reconciled'])
                self.assertTrue(all(receipt['checks'].values()))
                self.assertFalse(receipt['passed'])
                self.assertEqual(receipt['error_type'],'RuntimeError')
                self.assertFalse(json.loads((output/'qualification.json').read_text())['passed'])

    def test_available_sealed_artifact_does_not_erase_cleanup_failure(self):
        invocation={'status':'timeout','artifact_available':True,
                    'cleanup_unsettled':[{'component':'transport','error_type':'RuntimeError'}]}
        self.assertEqual(collection_validity([invocation]),'infrastructure_invalid')
        invocation['cleanup_unsettled']=[]
        self.assertEqual(collection_validity([invocation]),'valid_development')

    def test_exact_model_effort_no_fallback(self):
        for model, effort in [('gpt-6-astra','medium'),(MODEL,'high')]:
            with self.assertRaises(ValueError):exact(model,effort)
        adapter, server, _ = self.make([completed()])
        self.assertFalse(server.calls[0][1]['allowProviderModelFallback'])
        self.assertEqual(server.calls[0][1]['environments'],[])

    def test_source_hashes_terminal_text_and_deferred_export(self):
        adapter, server, worker = self.make([tool(),completed()])
        with patch('langbench.codex_subscriptions.source_digest',side_effect=['before','after']):
            result = adapter.invoke('task',None,10)
        self.assertEqual(result['terminal_text'],'BENCHMARK_STATUS: COMPLETE')
        self.assertEqual(result['tool_records'][0]['source_after'],'after')
        self.assertEqual(worker.commands,['sh build.sh'])
        self.assertFalse(worker.exported)
        self.assertFalse(result['artifact_available'])
        self.assertTrue(result['quiescent'])
        self.assertFalse(server.closed)

    def test_timeout_closes_before_any_capture_and_cannot_resume(self):
        adapter, server, worker = self.make([])
        result = adapter.invoke('task',None,10)
        self.assertEqual(result['status'],'timeout');self.assertTrue(server.closed)
        self.assertFalse(result['artifact_available']);self.assertFalse(worker.exported)
        with self.assertRaises(RuntimeError):adapter.invoke('continue','thread',10)

    def test_explicit_resume_and_adaptive_marker(self):
        adapter, server, _ = self.make([completed(text='BENCHMARK_STATUS: INCOMPLETE'),completed('2')])
        first=adapter.invoke('task',None,10)
        self.assertTrue(decision(first,0)[0])
        second=adapter.invoke('continue',first['session_id'],10)
        self.assertFalse(decision(second,1)[0])
        self.assertEqual(second['session_id'],first['session_id'])
        with self.assertRaises(ProtocolViolation):adapter.invoke('bad','wrong',10)

    def test_forbidden_capability_stops_without_execution(self):
        adapter, server, worker=self.make([tool('host_shell')])
        result=adapter.invoke('task',None,10)
        self.assertEqual(result['status'],'infrastructure_error')
        self.assertTrue(server.closed);self.assertEqual(worker.commands,[])

    def test_ordinary_argument_error_recoverable(self):
        adapter, _, worker=self.make([tool(args={'command':7}),completed()])
        result=adapter.invoke('task',None,10)
        self.assertEqual(result['status'],'handoff')
        self.assertTrue(result['tool_records'][0]['rejected']);self.assertEqual(worker.commands,[])

    def test_quota_is_not_nudge_eligible(self):
        adapter, server, _=self.make([completed(status='failed',code='usageLimitExceeded')])
        result=adapter.invoke('task',None,10)
        self.assertEqual(result['status'],'quota');self.assertFalse(decision(result,0)[0]);self.assertTrue(server.closed)

    def test_explicit_length_reason_prevents_nudge(self):
        event=response('r','1');event['params']['finishReason']='length'
        adapter,server,_=self.make([event,completed(text='BENCHMARK_STATUS: INCOMPLETE')])
        result=adapter.invoke('task',None,10)
        self.assertEqual(result['completion_kind'],'model_output_limit')
        self.assertEqual(result['status'],'model_output_limit')
        self.assertEqual(collection_validity([result]),'valid_development')
        self.assertEqual(result['terminal_text'],'');self.assertFalse(decision(result,0)[0]);self.assertTrue(server.closed)

    def test_usage_reconciles_multiple_requests_and_resume_without_double_count(self):
        adapter,_,_=self.make([response('r1','1'),response('r2','1'),total('1',2),completed(),
                              response('r3','2'),total('2',3),completed('2')])
        first=adapter.invoke('task',None,10);second=adapter.invoke('followup','thread',10)
        self.assertEqual(first['native_usage_reconciliation']['provider_reported_total_tokens'],30)
        summary=second['native_usage_reconciliation']
        self.assertTrue(summary['complete']);self.assertEqual(summary['provider_reported_total_tokens'],45)
        self.assertEqual(summary['response_count'],3)

    def test_timeout_retains_only_usage_subtotal(self):
        adapter,_,_=self.make([response('r1','1'),total('1',1)])
        result=adapter.invoke('task',None,10);summary=result['native_usage_reconciliation']
        self.assertFalse(summary['complete']);self.assertIsNone(summary['provider_reported_total_tokens'])
        self.assertEqual(summary['known_subtotals']['totalTokens'],15)

    def test_allowance_denial_does_not_start_turn(self):
        adapter,server,_=self.make([])
        original=server.call
        def call(method,params,**kwargs):
            if method=='account/rateLimits/read':return {'ordinaryUsageAllowed':False,'accountId':'SECRET'}
            return original(method,params,**kwargs)
        server.call=call
        result=adapter.invoke('task',None,10)
        self.assertEqual(result['status'],'quota');self.assertFalse(result['inference_started'])
        self.assertEqual(result['seconds'],0)
        self.assertGreaterEqual(result['allowance_preflight_seconds'],0)
        self.assertEqual(server.turn,0);self.assertNotIn('SECRET',str(result))

    def test_allowance_revocation_stops_before_queued_tool(self):
        event={'method':'account/rateLimits/updated','params':{'ordinaryUsageAllowed':False,'accountId':'SECRET'}}
        adapter,server,worker=self.make([event,tool(),completed()])
        result=adapter.invoke('task',None,10)
        self.assertEqual(result['status'],'quota');self.assertEqual(worker.commands,[])
        self.assertTrue(result['ordinary_allowance_revoked']);self.assertNotIn('SECRET',str(result))

    def test_account_notifications_never_archived(self):
        adapter,_,_=self.make([{'method':'account/updated','params':{'secret':'SENSITIVE'}},completed()])
        result=adapter.invoke('task',None,10)
        self.assertNotIn('SENSITIVE',str(result))

    def test_cross_turn_and_model_change_fail_closed(self):
        for event in [tool(),{'method':'thread/settings/updated','params':{'threadId':'thread','threadSettings':{'model':'other'}}}]:
            if event['method']=='item/tool/call':event['params']['turnId']='wrong'
            adapter,server,worker=self.make([event])
            result=adapter.invoke('task',None,10)
            self.assertEqual(result['status'],'infrastructure_error');self.assertTrue(server.closed)
            self.assertEqual(worker.commands,[])


if __name__ == '__main__':unittest.main()
