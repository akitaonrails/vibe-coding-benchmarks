import json
import tempfile
import unittest
from pathlib import Path
from langbench.provider_cli import parse_events,bounded_process
from langbench.subscriptions import validate_qualification,sha

class ProviderTests(unittest.TestCase):
    def test_kimi_terminal_and_forbidden_capability(self):
        events=[{'role':'assistant','content':'BENCHMARK_STATUS: COMPLETE'},
                {'role':'meta','type':'session.resume_hint','session_id':'abc'}]
        parsed,session,text,finished=parse_events('kimi','\n'.join(map(json.dumps,events)))
        self.assertEqual(session,'abc');self.assertTrue(finished)
        events.insert(0,{'role':'assistant','tool_calls':[{'function':{'name':'Bash'}}]})
        with self.assertRaises(ValueError):parse_events('kimi','\n'.join(map(json.dumps,events)))

    def test_opencode_request_scope_and_session(self):
        events=[{'type':'text','sessionID':'a','part':{'text':'done'}},{'type':'step_finish','sessionID':'a','part':{'reason':'stop'}}]
        self.assertTrue(parse_events('opencode','\n'.join(map(json.dumps,events)))[3])
        events[-1]['sessionID']='b'
        with self.assertRaises(ValueError):parse_events('opencode','\n'.join(map(json.dumps,events)))

    def test_bounded_stream_and_timeout(self):
        import sys,os
        with tempfile.TemporaryDirectory() as directory:
            for source,reason in [('import time;time.sleep(5)','timeout'),('print("x"*100000)','output_limit')]:
                result=bounded_process([sys.executable,'-c',source],cwd=directory,env={'PATH':'/usr/bin:/bin'},timeout=.1,limit=1000)
                self.assertEqual(result['termination'],reason)

    def test_qualification_hash_binding(self):
        identity={'model':'exact','tool':'only'}
        validate_qualification({'passed':True,'binding':identity,'binding_sha256':sha(identity)},identity)
        with self.assertRaises(ValueError):validate_qualification({'passed':True,'binding':identity,'binding_sha256':sha(identity)},{'model':'other'})

    def test_fake_oauth_store_preserves_atomic_rotation_and_lock_identity(self):
        from unittest.mock import patch
        from langbench.provider_cli import ProviderCLI
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);canonical=root/'.kimi-code';canonical.mkdir()
            (canonical/'credentials').mkdir();(canonical/'oauth').mkdir()
            (canonical/'credentials/kimi-code.json').write_text('{"fake":1}')
            (canonical/'config.toml').write_text('''[providers."managed:kimi-code"]
type="kimi"
base_url="https://api.kimi.com/coding/v1"
oauth={storage="file",key="fake"}
[models."kimi-code/k3"]
provider="managed:kimi-code"
model="k3"
''')
            adapter=ProviderCLI.__new__(ProviderCLI)
            adapter.home=root/'isolated';adapter.home.mkdir()
            adapter.transport=type('Transport',(),{'base_url':'http://127.0.0.1:1234'})()
            adapter.secrets=[]
            adapter.env={};adapter.model='kimi-code/k3';adapter.effort='high';adapter.mcp_command=['fake']
            with patch('langbench.provider_cli.Path.home',return_value=root):adapter.configure_kimi()
            isolated=adapter.home/'kimi'
            self.assertEqual((isolated/'oauth').resolve(),(canonical/'oauth').resolve())
            rotated=canonical/'credentials/new.json';rotated.write_text('{"fake":2}')
            rotated.replace(canonical/'credentials/kimi-code.json')
            self.assertEqual((isolated/'credentials/kimi-code.json').read_text(),'{"fake":2}')
            import tomllib
            config=tomllib.loads((isolated/'config.toml').read_text())
            self.assertEqual(config['tools']['enabled'],['mcp__langbench__sandbox_shell'])
            self.assertEqual(config['background']['print_background_mode'],'exit')

    def test_timeout_preserves_valid_event_prefix(self):
        prefix=json.dumps({'role':'meta','type':'session.resume_hint','session_id':'s'})+'\n{"role":'
        parsed,session,_,_=parse_events('kimi',prefix,allow_truncated=True)
        self.assertEqual(session,'s');self.assertEqual(len(parsed),1)
        with self.assertRaises(ValueError):parse_events('kimi',prefix)

    def test_invoke_preserves_timeout_when_drain_fails_and_wire_is_partial(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from langbench.provider_cli import ProviderCLI
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'trace').mkdir();(root/'kimi/session').mkdir(parents=True)
            wire=root/'kimi/session/wire.jsonl'
            wire.write_text(json.dumps({'type':'context.append_loop_event','event':{'type':'step.end','usage':{'inputOther':3,'output':2,'inputCacheRead':0,'inputCacheCreation':0}}})+'\n{"type":')
            adapter=ProviderCLI.__new__(ProviderCLI)
            adapter.index=0;adapter.provider='kimi';adapter.model='kimi-code/k3';adapter.binary=Path('/fake');adapter.skills=root;adapter.profile=root/'profile';adapter.cwd=root;adapter.env={};adapter.secrets=[];adapter.output=root/'trace';adapter.home=root;adapter.seen_usage=set()
            def fail_drain():raise RuntimeError('still active')
            adapter.bridge=SimpleNamespace(records=[{'old':True}],deadline=0,fatal=None,settle=fail_drain)
            adapter.transport=SimpleNamespace(records=[],rejections=[],fatal=None,rate_latched=False,accepting=True,settle=lambda:None)
            process={'stdout':'{"role":"assistant"','stderr':'','returncode':-9,'termination':'timeout','seconds':.1}
            with patch('langbench.provider_cli.bounded_process',return_value=process):result=adapter.invoke('prompt','same',1)
            self.assertEqual(result['status'],'timeout')
            self.assertFalse(result['quiescent'])
            self.assertEqual(result['cleanup_unsettled'][0]['component'],'bridge')
            self.assertEqual(len(result['cli_usage_records']),1)
            self.assertTrue((root/'trace/invocation-0.json').is_file())
