from collections import deque
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from langbench.appserver import AppServer, ProtocolViolation
from langbench.live import Adapter

class FakeWorker:
    alive=True
    def __init__(self):self.commands=[]
    def execute(self,command,**kwargs):
        self.commands.append(command)
        return {'returncode':0,'termination':None,'stdout':'ok','stderr':'','seconds':.01}
    def export(self,path):
        (path/'src').mkdir(parents=True);(path/'src/solution.rb').write_text('puts 1')

class FakeServer:
    cwd='/empty-controller'
    def __init__(self,notifications):self.notifications=deque(notifications);self.calls=[];self.sent=[];self.turns=0
    def call(self,method,params,timeout=30):
        self.calls.append((method,params))
        if method=='thread/start':return {'model':'gpt-6-luna','thread':{'id':'thread-1'}}
        if method=='turn/start':
            self.turns+=1;return {'turn':{'id':f'turn-{self.turns}','items':[]}}
        return {}
    def send(self,message,**kwargs):self.sent.append(message)
    def next(self,deadline):
        if not self.notifications:raise TimeoutError('synthetic timeout')
        return self.notifications.popleft()

def terminal(turn='turn-1'):
    return {'method':'turn/completed','params':{'threadId':'thread-1','turn':{'id':turn,'status':'completed','items':[]}}}
def tool(name='sandbox_shell',turn='turn-1'):
    return {'id':10,'method':'item/tool/call','params':{'threadId':'thread-1','turnId':turn,'callId':'call-1','tool':name,'arguments':{'command':'sh build.sh'}}}

class LiveAdapterTests(unittest.TestCase):
    def adapter(self,temp,notifications):
        work=Path(temp)/'workspace';work.mkdir();server=FakeServer(notifications);worker=FakeWorker()
        adapter=Adapter(server,worker,work,'gpt-6-luna','high');adapter.start()
        return adapter,server,worker
    def test_single_tool_and_explicit_thread_continuity(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter,server,worker=self.adapter(temp,[tool(),terminal(),terminal('turn-2')])
            first=adapter.invoke('task',None,10);second=adapter.invoke('continue','thread-1',10)
            self.assertEqual(first['status'],'handoff');self.assertEqual(second['status'],'handoff')
            self.assertEqual(first['tool_call_count'],1);self.assertEqual(worker.commands,['sh build.sh'])
            self.assertEqual(first['tool_seconds'],.01)
            self.assertIsNone(first['usage_semantics']['normalized_total'])
            for method,params in server.calls:
                if method in ('thread/start','turn/start'):self.assertEqual(params['environments'],[])
                if method=='turn/start':self.assertEqual(params['threadId'],'thread-1');self.assertEqual(params['effort'],'high')
            with self.assertRaises(ProtocolViolation):adapter.invoke('wrong','different-thread',10)
    def test_unexpected_builtin_item_rejected(self):
        notification={'method':'item/started','params':{'threadId':'thread-1','turnId':'turn-1','item':{'type':'commandExecution'}}}
        with tempfile.TemporaryDirectory() as temp:
            adapter,server,worker=self.adapter(temp,[notification])
            result=adapter.invoke('task',None,10)
            self.assertEqual(result['status'],'infrastructure_error');self.assertEqual(worker.commands,[])
            self.assertTrue(any(method=='turn/interrupt' for method,_ in server.calls))
    def test_unknown_tool_request_never_executes(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter,_,worker=self.adapter(temp,[tool('host_shell')])
            self.assertEqual(adapter.invoke('task',None,10)['status'],'infrastructure_error')
            self.assertEqual(worker.commands,[])
    def test_usage_total_last_preserved_without_summing(self):
        usage={'total':{'inputTokens':12,'outputTokens':8,'reasoningOutputTokens':6,'totalTokens':20},'last':{'inputTokens':4,'totalTokens':7}}
        event={'method':'thread/tokenUsage/updated','params':{'threadId':'thread-1','turnId':'turn-1','tokenUsage':usage}}
        with tempfile.TemporaryDirectory() as temp:
            adapter,_,_=self.adapter(temp,[event,terminal()]);result=adapter.invoke('task',None,10)
            stored=next(e for e in result['events'] if e.get('method')=='thread/tokenUsage/updated')
            self.assertEqual(stored['params']['tokenUsage'],usage)
            self.assertIsNone(result['usage_semantics']['normalized_total'])
    def test_timeout_interrupts_and_no_tool_work(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter,server,worker=self.adapter(temp,[]);result=adapter.invoke('task',None,10)
            self.assertEqual(result['status'],'timeout');self.assertEqual(worker.commands,[])
            self.assertTrue(any(method=='turn/interrupt' for method,_ in server.calls))
    def test_unavailable_artifact_not_claimed(self):
        with tempfile.TemporaryDirectory() as temp:
            adapter,_,worker=self.adapter(temp,[terminal()]);worker.alive=False
            self.assertFalse(adapter.invoke('task',None,10)['artifact_available'])

class AuthCatalogTests(unittest.TestCase):
    def server(self,account,models):
        server=object.__new__(AppServer);calls=[]
        def call(method,params,timeout=30):
            calls.append((method,params))
            if method=='account/read':return {'account':account}
            if method=='model/list':return {'data':models,'nextCursor':None}
            return {}
        server.call=call;server.send=lambda *a,**k:None
        return server,calls
    def test_signed_out_and_api_key_rejected(self):
        for account in (None,{'type':'apiKey'}):
            server,_=self.server(account,[])
            with self.assertRaisesRegex(RuntimeError,'subscription'):server.initialize('gpt-6-luna','high')
    def test_exact_model_and_effort_required(self):
        server,calls=self.server({'type':'chatgpt','email':'never-logged'},[{'model':'gpt-6-luna','supportedReasoningEfforts':[{'reasoningEffort':'high'}]}])
        result=server.initialize('gpt-6-luna','high')
        self.assertNotIn('email',json.dumps(result))
        self.assertTrue(next(params for method,params in calls if method=='model/list')['includeHidden'])
        with self.assertRaises(RuntimeError):server.initialize('gpt-6-luna','low')
        with self.assertRaises(RuntimeError):server.initialize('different','high')

class LiveReceiptTests(unittest.TestCase):
    def test_grade_failure_preserves_manifest_collection_and_earlier_grade(self):
        from unittest.mock import MagicMock
        from langbench.live import run
        with tempfile.TemporaryDirectory() as temp:
            adapter=MagicMock();adapter.resolved_model='gpt-6-luna'
            collection={'invocations':[{'index':i,'artifact_available':True,'status':'handoff'} for i in range(3)]}
            with patch('langbench.live.qualify',return_value={'passed':True,'environment':{}}), \
                 patch('langbench.live.environment',return_value={}), \
                 patch('langbench.live.DockerWorker'), patch('langbench.live.AppServer'), \
                 patch('langbench.live.Adapter',return_value=adapter), \
                 patch('langbench.live.collect',return_value=collection), \
                 patch('langbench.live.grade',side_effect=[{'success':True,'validity':'valid'},RuntimeError('synthetic grader failure')]):
                result=run('crash_store','ruby',Path(temp)/'run',seed=17)
            self.assertEqual(result['validity'],'infrastructure_invalid')
            self.assertEqual(result['phase'],'grading')
            self.assertEqual(result['manifest']['semantic_seed'],17)
            self.assertEqual(result['collection'],collection)
            self.assertEqual(len(result['grades']),1)
            self.assertEqual(json.loads((Path(temp)/'run/result.json').read_text()),result)
    def test_smoke_report_checkpoints_and_missingness(self):
        from langbench.report import summarize
        row={'kind':'development_smoke','validity':'valid_smoke','manifest':{'task':'crash_store','language':'ruby','model':'gpt-6-luna','effort':'high','tests':'T1'},
             'collection':{'invocations':[{'index':0,'seconds':5,'tool_call_count':2,'status':'handoff','artifact_available':True},{'index':1,'seconds':3,'tool_call_count':1,'status':'handoff','artifact_available':True}]},
             'grades':[{'index':0,'validity':'valid','success':False},{'index':1,'validity':'valid','success':True}]}
        report=summarize([row]);cell=report['cells'][0]
        self.assertEqual(cell['checkpoints'][0]['successes'],0)
        self.assertEqual(cell['checkpoints'][1]['successes'],1)
        self.assertEqual(cell['checkpoints'][2]['reached'],0)
        self.assertIsNone(cell['checkpoints'][2]['success_rate_among_graded'])
        self.assertEqual(cell['observed_active_seconds'],8)
        self.assertIsNone(cell['normalized_tokens'])
        with self.assertRaises(ValueError):summarize([row,{'validity':'valid','success':True}])

class TransportTests(unittest.TestCase):
    def test_duplex_stderr_and_large_partial_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);binary=root/'codex';companion=root/'codex-code-mode-host';companion.write_text('placeholder')
            binary.write_text('#!/usr/bin/python3\nimport sys,json\nsys.stderr.write("e"*100000);sys.stderr.flush()\nfor line in sys.stdin:\n obj=json.loads(line);print(json.dumps({"id":obj["id"],"result":{"size":len(obj["params"]["payload"])}}),flush=True)\n')
            binary.chmod(0o755);auth=root/'auth.json';auth.write_text('{}')
            with AppServer(binary,auth=auth) as server:
                response=server.call('echo',{'payload':'x'*150000},timeout=3)
                self.assertEqual(response['size'],150000)
                self.assertEqual(len(server.stderr),100000)

class ProbeEvidenceTests(unittest.TestCase):
    def test_agent_prose_and_unpaired_outputs_do_not_qualify(self):
        from langbench.live import verify_js_probe
        output=json.dumps({'marker':'marker','process':'undefined','require':'undefined','Deno':'undefined','fetch':'undefined'})
        self.assertFalse(verify_js_probe([{'params':{'item':{'type':'agentMessage','text':output}}}],'marker','exact program'))
        self.assertFalse(verify_js_probe([{'params':{'item':{'type':'function_call_output','call_id':'x','output':output}}}],'marker','exact program'))
        events=[{'params':{'item':{'type':'function_call','name':'exec','call_id':'x','input':'exact program'}}},
                {'params':{'item':{'type':'function_call_output','call_id':'x','output':output}}}]
        self.assertTrue(verify_js_probe(events,'marker','exact program'))

class InvalidCheckpointReportTests(unittest.TestCase):
    def test_later_invalid_checkpoint_does_not_contaminate_earlier_success(self):
        from langbench.report import summarize
        row={'kind':'development_smoke','validity':'infrastructure_invalid',
             'collection':{'invocations':[{'index':0,'status':'handoff','artifact_available':True,'seconds':3},
                                         {'index':1,'status':'infrastructure_error','artifact_available':True,'seconds':2}]},
             'grades':[{'index':0,'validity':'valid','success':True},{'index':1,'validity':'valid','success':True}]}
        checkpoints=summarize([row])['cells'][0]['checkpoints']
        self.assertEqual(checkpoints[0]['successes'],1)
        self.assertEqual(checkpoints[1]['successes'],0)
        self.assertEqual(checkpoints[1]['infrastructure_invalid_grades'],1)
        self.assertEqual(checkpoints[1]['incremental_active_seconds'],2)

class ProbeFieldRegressionTests(unittest.TestCase):
    def events(self,report,**flags):
        return [{'params':{'item':{'type':'function_call','name':'exec','call_id':'x','input':'exact program'}}},
                {'params':{'item':{'type':'function_call_output','call_id':'x','output':json.dumps(report),**flags}}}]
    def test_unrelated_undefined_and_failed_outputs_never_pass(self):
        from langbench.live import verify_js_probe
        report={'marker':'m','process':'object','require':'undefined','Deno':'undefined','fetch':'undefined','extra':'undefined'}
        self.assertFalse(verify_js_probe(self.events(report),'m','exact program'))
        report['process']='undefined'
        self.assertTrue(verify_js_probe(self.events(report),'m','exact program'))
        self.assertFalse(verify_js_probe(self.events(report,status='failed'),'m','exact program'))
        self.assertFalse(verify_js_probe(self.events(report,isError=True),'m','exact program'))
        self.assertFalse(verify_js_probe(self.events(report),'wrong-marker','exact program'))

class EffectiveSettingsTests(unittest.TestCase):
    def test_mismatched_effective_model_or_effort_stops_turn(self):
        for settings in ({'model':'other','effort':'high'},{'model':'gpt-6-luna','effort':'low'},
                         {'collaborationMode':{'settings':{'model':'other'}}}):
            with tempfile.TemporaryDirectory() as temp:
                work=Path(temp)/'work';work.mkdir()
                server=FakeServer([{'method':'thread/settings/updated','params':{'threadId':'thread-1','threadSettings':settings}},terminal()])
                worker=FakeWorker();adapter=Adapter(server,worker,work,'gpt-6-luna','high');adapter.start()
                result=adapter.invoke('task',None,10)
                self.assertEqual(result['status'],'infrastructure_error')
                self.assertEqual(worker.commands,[])
