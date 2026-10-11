import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import urllib.request

from langbench import claude_subscriptions as c
from langbench.assistance import collect


def request(index=0):
    return {'index':index,'model':c.MODEL,'effort':c.EFFORT,'tool_names':[c.TOOL],'auth_mode':'oauth_bearer','usage':{'input_tokens':10,'cache_read_input_tokens':20,'cache_creation_input_tokens':30,'output_tokens':40},
            'response_ids':['msg-'+str(index)],'http_status':200,'message_stopped':True,'response_complete':True}


def body(**updates):
    return {'model':c.MODEL,'output_config':{'effort':'medium'},'stream':True,'tools':[{'name':c.TOOL}],**updates}


def stream(session='session'):
    return '\n'.join(json.dumps(e) for e in [
        {'type':'system','subtype':'init','model':c.MODEL,'tools':[c.TOOL],'session_id':session,'apiKeySource':'none'},
        {'type':'assistant','session_id':session,'message':{'model':c.MODEL,'content':[{'type':'text','text':'BENCHMARK_STATUS: COMPLETE'}]}},
        {'type':'result','subtype':'success','session_id':session,'is_error':False}])


class ClaudeTests(unittest.TestCase):
    def test_request_boundary(self):
        headers={'Authorization':'Bearer sk-ant-oat-test'}
        self.assertEqual(c.inspect_request(body(),headers)['model'],c.MODEL)
        for altered in [body(model='sonnet'),body(output_config={'effort':'high'}),body(tools=[{'name':'Bash'}]),body(tools=[]),body(stream=False)]:
            with self.assertRaises(ValueError):c.inspect_request(altered,headers)
        for altered in ({'x-api-key':'fake'},dict(headers,**{'x-api-key':'fake'}),{'Authorization':'Bearer api-key'}):
            with self.assertRaises(ValueError):c.inspect_request(body(),altered)

    def test_disjoint_cache_and_unknown_coverage(self):
        item=c.native_usage(request());self.assertEqual(item['provider_reported_total'],100)
        self.assertIsNone(item['components']['reasoning'])
        inv={'request_records':[request()],'usage_coverage_verified':True}
        self.assertEqual(c.reconcile_claude_usage([inv])['total'],100)
        result=c.reconcile_claude_usage([inv,{'request_records':[],'usage_coverage_verified':False}])
        self.assertIsNone(result['total']);self.assertEqual(result['known_subtotal'],100)
        bad=request();del bad['usage']['cache_read_input_tokens']
        self.assertIsNone(c.native_usage(bad)['provider_reported_total'])
        bad=request();bad['usage']['input_tokens']=True
        self.assertFalse(c.native_usage(bad)['valid'])
        duplicate=c.reconcile_claude_usage([inv,inv])
        self.assertEqual(duplicate['total'],100);self.assertEqual(duplicate['known_subtotal'],100)

    def test_stream_cumulative_output_not_added(self):
        transport=c.ClaudeTransport.__new__(c.ClaudeTransport);transport.fatal=None
        row={'usage':{},'response_ids':[]}
        for event in [
            {'type':'message_start','message':{'model':c.MODEL,'id':'msg','usage':{'input_tokens':10,'cache_read_input_tokens':20,'cache_creation_input_tokens':30,'output_tokens':1}}},
            {'type':'message_delta','usage':{'output_tokens':40},'delta':{'stop_reason':'end_turn'}},
            {'type':'message_stop'}]:
            transport.observe(row,b'data: '+json.dumps(event).encode())
        self.assertEqual(row['usage']['output_tokens'],40)
        self.assertTrue(row['message_stopped'])
        transport.observe(row,b'data: '+json.dumps({'type':'content_block_start','content_block':{'type':'tool_use','name':'Bash'}}).encode())
        self.assertEqual(transport.fatal,'response_capability_mismatch')

    def test_live_init_builtin_plugins_are_rejected(self):
        init={'type':'system','subtype':'init','model':c.MODEL,'tools':[c.TOOL],
              'session_id':'session','apiKeySource':'none','skills':[],'slash_commands':[],
              'agents':['claude','general-purpose','statusline-setup'],
              'plugins':[{'name':'cc-plugin-agents-md','path':'builtin','source':'cc-plugin-agents-md@builtin'},
                         {'name':'cc-plugin-plugin-authoring','path':'builtin','source':'cc-plugin-plugin-authoring@builtin'}]}
        with self.assertRaisesRegex(ValueError,'injected customization'):
            c.parse_events(json.dumps(init),'session')
        init['plugins']=[]
        self.assertTrue(c.parse_events(json.dumps(init),'session')[3])
        self.assertEqual(len(c.DISABLED_PLUGINS),11)
        self.assertTrue(all(value is False for value in c.DISABLED_PLUGINS.values()))

    def test_event_identity_and_native_tools(self):
        self.assertTrue(c.parse_events(stream(),'session')[3])
        for invalid in (stream('other'),stream().replace(c.MODEL,'claude-sonnet'),stream().replace(c.TOOL,'Bash')):
            with self.assertRaises(ValueError):c.parse_events(invalid,'session')
        self.assertTrue(c.parse_events(stream()+'\n{"type":','session',truncated=True)[3])
        with self.assertRaises(ValueError):c.parse_events(stream()+'\n{"type":','session')

    def test_pre_upstream_rejection_and_quota_latch(self):
        class Response(io.BytesIO):
            status=200;headers={'Content-Type':'application/json'}
        class Opener:
            def __init__(self):self.urls=[]
            def open(self,req,timeout):
                self.urls.append(req.full_url)
                return Response(json.dumps({'extra_usage':{'is_enabled':False},'five_hour':{'utilization':100},'seven_day':{'utilization':97}}).encode())
        opener=Opener();transport=c.ClaudeTransport(opener)
        try:
            def send(payload):
                req=urllib.request.Request(transport.base_url+'/v1/messages?beta=true',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer sk-ant-oat-fake','Content-Type':'application/json'})
                try:urllib.request.urlopen(req,timeout=3).read()
                except urllib.error.HTTPError as error:return error.code
            self.assertEqual(send(body(model='wrong')),502);self.assertFalse(opener.urls)
            transport.fatal=None
            self.assertEqual(send(body()),429)
            self.assertEqual(opener.urls,['https://api.anthropic.com/api/oauth/usage'])
            self.assertEqual(send(body()),429);self.assertEqual(len(opener.urls),1)
            self.assertTrue(transport.records[-1]['quota_retry_blocked'])
        finally:transport.close()

    def test_allowance_extra_usage_denied(self):
        class Response(io.BytesIO):status=200
        t=c.ClaudeTransport.__new__(c.ClaudeTransport)
        t.opener=SimpleNamespace(open=lambda *a,**k:Response(b'{"extra_usage":{"is_enabled":true}}'))
        with self.assertRaises(ValueError):t.check_allowance('fake')

    def fake_adapter(self,directory,settle_error=False):
        adapter=c.ClaudeCLI.__new__(c.ClaudeCLI)
        adapter.binary=Path('/fake/claude');adapter.output=Path(directory);adapter.cwd=Path(directory)
        adapter.env={};adapter.settings=Path(directory)/'settings';adapter.mcp=Path(directory)/'mcp';adapter.index=0;adapter.session='session'
        def settle():
            if settle_error:raise RuntimeError('unsettled')
        adapter.bridge=SimpleNamespace(records=[],fatal=None,deadline=0,settle=lambda:None)
        adapter.transport=SimpleNamespace(records=[request()],base_url='http://127.0.0.1:1',fatal=None,rate_latched=False,settle=settle,allowance={'extra_usage_enabled':False})
        return adapter

    def test_timeout_truncated_stream_preserves_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=self.fake_adapter(d,settle_error=True)
            replies=[{'stdout':json.dumps({'authMethod':'claude.ai','apiProvider':'firstParty','subscriptionType':'max'}),'returncode':0},
                     {'stdout':stream()+'\n{"type":','stderr':'','returncode':-9,'termination':'timeout','seconds':.01}]
            with patch.object(c,'bounded_process',side_effect=replies):result=adapter.invoke('task','session',2)
            self.assertEqual(result['status'],'timeout');self.assertFalse(result['quiescent'])
            self.assertEqual(result['cleanup_unsettled'][0]['component'],'transport')
            self.assertTrue(Path(result['raw_path']).exists());self.assertTrue(result['events'])
            self.assertFalse(result['usage_coverage_verified'])

    def test_no_api_auth_fallback_and_session_resume(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=self.fake_adapter(d)
            with patch.object(c,'bounded_process',return_value={'returncode':0,'stdout':json.dumps({'authMethod':'api_key'})}) as process:
                with self.assertRaises(ValueError):adapter.invoke('task','session',2)
                self.assertEqual(process.call_count,1)
            with self.assertRaises(ValueError):adapter.invoke('task','other-session',2)
            argv=adapter.argv('task','session')
            self.assertIn('--resume',argv);self.assertEqual(argv[argv.index('--tools')+1],'')
            self.assertNotIn('--bare',argv);self.assertNotIn('--fallback-model',argv)

    def test_constructor_isolates_keys_and_preserves_oauth_namespace(self):
        import hashlib
        import os
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'claude';binary.write_bytes(b'fixture executable')
            with patch.object(c,'BINARY_SHA',hashlib.sha256(binary.read_bytes()).hexdigest()), patch.dict(os.environ,{'ANTHROPIC_API_KEY':'must-not-inherit','CLAUDE_CONFIG_DIR':'must-not-inherit'}):
                adapter=c.ClaudeCLI(Path(d)/'trace',lambda *a:None,lambda:'hash',binary=binary)
                try:
                    self.assertNotIn('ANTHROPIC_API_KEY',adapter.env)
                    self.assertNotIn('CLAUDE_CONFIG_DIR',adapter.env)
                    self.assertEqual(adapter.env['CLAUDE_CODE_DISABLE_CLAUDE_MDS'],'1')
                    self.assertEqual(adapter.env['HOME'],str(Path.home()))
                    self.assertTrue(adapter.identity['settings']['disableAllHooks'])
                    self.assertEqual(adapter.identity['settings']['enabledPlugins'],c.DISABLED_PLUGINS)
                    self.assertIs(adapter.identity['settings']['enabledPlugins']['cc-plugin-agents-md@builtin'],False)
                    self.assertIs(adapter.identity['settings']['enabledPlugins']['cc-plugin-plugin-authoring@builtin'],False)
                    self.assertEqual(list(json.loads(adapter.mcp.read_text())['mcpServers']),['langbench'])
                finally:adapter.close()

    def test_handoff_usage_and_late_request_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=self.fake_adapter(d);adapter.transport.records=[]
            def process(*args,**kwargs):
                if 'auth' in args[0]:
                    return {'stdout':json.dumps({'authMethod':'claude.ai','apiProvider':'firstParty','subscriptionType':'max'}),'returncode':0}
                adapter.transport.records.append(request())
                return {'stdout':stream(),'stderr':'','returncode':0,'termination':None,'seconds':.01}
            with patch.object(c,'bounded_process',side_effect=process):result=adapter.invoke('task','session',2)
            self.assertEqual(result['status'],'handoff')
            self.assertTrue(result['usage_coverage_verified'])
            self.assertEqual(c.reconcile_claude_usage([result])['total'],100)

    def test_wire_length_overrides_cli_success(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=self.fake_adapter(d);adapter.transport.records=[]
            def process(*args,**kwargs):
                if 'auth' in args[0]:
                    return {'stdout':json.dumps({'authMethod':'claude.ai','apiProvider':'firstParty','subscriptionType':'max'}),'returncode':0}
                adapter.transport.records.append({**request(),'stop_reason':'max_tokens'})
                return {'stdout':stream(),'stderr':'','returncode':0,'termination':None,'seconds':.01}
            with patch.object(c,'bounded_process',side_effect=process):result=adapter.invoke('task','session',2)
            self.assertEqual(result['status'],'model_output_limit')

    def test_conflicts_missing_ids_and_partial_component_bounds(self):
        original=request();changed=request();changed['usage']['output_tokens']=41
        result=c.reconcile_claude_usage([{'request_records':[original,changed],'usage_coverage_verified':True}])
        self.assertFalse(result['complete']);self.assertIsNone(result['known_subtotal'])
        self.assertIsNone(result['known_token_lower_bound']);self.assertTrue(result['identity_conflicts'])
        missing=request();missing['response_ids']=[]
        result=c.reconcile_claude_usage([{'request_records':[missing],'usage_coverage_verified':True}])
        self.assertIsNone(result['known_subtotal']);self.assertEqual(len(result['unidentified_usage_observations']),1)
        partial=request();partial['message_stopped']=False;partial['response_complete']=False
        del partial['usage']['output_tokens']
        result=c.reconcile_claude_usage([{'request_records':[partial],'usage_coverage_verified':False}])
        self.assertFalse(result['complete']);self.assertIsNone(result['total'])
        self.assertEqual(result['known_token_lower_bound'],60)
        self.assertEqual(result['observed_component_lower_bounds']['cache_read'],20)
        self.assertIsNone(result['observed_component_lower_bounds']['output_including_reasoning'])

    def test_active_time_excludes_auth_and_cleanup(self):
        with tempfile.TemporaryDirectory() as d:
            adapter=self.fake_adapter(d);clock=[100.0]
            def process(*args,**kwargs):
                if 'auth' in args[0]:
                    clock[0]+=5
                    return {'stdout':json.dumps({'authMethod':'claude.ai','apiProvider':'firstParty','subscriptionType':'max'}),'returncode':0}
                self.assertEqual(kwargs['timeout'],900)
                self.assertEqual(adapter.bridge.deadline,100+5+900)
                clock[0]+=3
                return {'stdout':stream(),'stderr':'','returncode':0,'termination':None,'seconds':3}
            def settle():clock[0]+=11
            adapter.transport.settle=settle
            with patch.object(c,'bounded_process',side_effect=process),patch.object(c.time,'monotonic',side_effect=lambda:clock[0]):
                result=adapter.invoke('task','session',900)
            self.assertEqual(result['seconds'],3)
            self.assertEqual(result['auth_preflight_seconds'],5)
            self.assertEqual(result['cleanup_seconds'],11)

    def test_qualification_teardown_failure_never_passes(self):
        from langbench import subscriptions as shared
        for module in (c,shared):
            for failure in (None,'adapter','worker'):
                with self.subTest(module=module.__name__,failure=failure),tempfile.TemporaryDirectory() as d:
                    class Worker:
                        qualification={}
                        def __init__(self,*args,**kwargs):pass
                        def __enter__(self):return self
                        def __exit__(self,*args):
                            if failure=='worker':raise RuntimeError('cleanup failed')
                        def execute(self,*args,**kwargs):return {'returncode':0,'termination':None}
                    class Adapter:
                        identity={'tool':c.TOOL}
                        transport=SimpleNamespace(fatal=None)
                        marker=None
                        def __init__(self,*args,**kwargs):self.count=0
                        def invoke(self,prompt,session,seconds):
                            self.count+=1;command=None
                            if self.count==1:
                                command=prompt.split('sandbox_shell: ',1)[1].split('\n')[0]
                                Adapter.marker=command.split('printf %s ',1)[1].split(' > ',1)[0]
                            return {'status':'handoff','session_id':'s','terminal_text':'BENCHMARK_STATUS: COMPLETE',
                                'seconds':1,'effective_configuration_verified':True,'subscription_auth_verified':True,
                                'allowance':{'extra_usage_enabled':False},'usage_coverage_verified':True,
                                'usage_records':[c.native_usage(request(self.count))],
                                'request_records':[{**request(self.count),'tool_names':[c.TOOL]}],
                                'tool_records':[{'arguments':{'command':command},'result':{'returncode':0,'termination':None}}] if command else []}
                        def close(self):
                            if failure=='adapter':raise RuntimeError('cleanup failed')
                    def export(worker,workspace):(workspace/'src/QUALIFIED').write_text(Adapter.marker)
                    adapter_name='ClaudeCLI' if module is c else 'ProviderCLI'
                    binding_name='binding' if module is c else 'bound_identity'
                    with patch.object(module,'DockerWorker',Worker),patch.object(module,adapter_name,Adapter),patch.object(module,binding_name,return_value={}),patch.object(module,'export_workspace',side_effect=export):
                        if module is c:result=module.qualify_claude(Path(d)/'q')
                        else:result=module.qualify_provider('kimi',Path(d)/'q',model='kimi-code/k3',effort='high')
                    if failure:
                        self.assertFalse(result['passed']);self.assertIn('error',result)
                    else:self.assertTrue(result['passed'],result.get('error'))

    def test_output_limit_is_consumed_without_nudge(self):
        with tempfile.TemporaryDirectory() as d:
            workspace=Path(d)/'w';(workspace/'src').mkdir(parents=True);(workspace/'src/main.rb').write_text('x')
            calls=[]
            def invoke(*args):
                calls.append(args)
                return {'status':'model_output_limit','session_id':'session','terminal_text':'BENCHMARK_STATUS: INCOMPLETE','seconds':1,'artifact_available':True}
            result=collect(workspace,Path(d)/'out','task',invoke)
            self.assertEqual(len(calls),1);self.assertEqual(result['stop_reason'],'transport_model_output_limit')


if __name__=='__main__':unittest.main()
