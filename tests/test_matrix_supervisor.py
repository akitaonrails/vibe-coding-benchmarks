import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from scripts.supervise_subscription_matrix import classify,matrix_argv,supervise


def fixture(kind='length'):
    invocation={'status':'infrastructure_error','error':'CLI failed or missing terminal event','quiescent':True,
                'artifact_available':True,'boundary_error':{'bridge':None,'transport':None},'tool_records':[]}
    invocation['events']=[{'type':'step_finish','part':{'reason':'length'}}]
    raw={'returncode':0,'termination':None,'stderr':'','stdout':json.dumps({'type':'step_finish','part':{'reason':'length'}})}
    if kind=='drain':
        invocation.update(status='timeout',error=None,quiescent=False,artifact_available=False,
            cleanup_unsettled=[{'component':'transport','error_type':'RuntimeError'}],tool_records=[{'state':'finished'}])
        raw.update(returncode=-9,termination='timeout')
    return {'validity':'infrastructure_invalid','phase':'complete','requested':{'provider':'opencode'},'collection':{'invocations':[invocation]}},raw

class SupervisorTests(unittest.TestCase):
    def test_exact_known_incidents_and_unknown_rejection(self):
        result,raw=fixture();self.assertEqual(classify(result,raw),'model_output_limit')
        raw['returncode']=1;self.assertIsNone(classify(result,raw))
        result,raw=fixture('drain');self.assertEqual(classify(result,raw),'timeout_transport_drain_preserved_invalid')
        result['collection']['invocations'][0]['tool_records'][0]['state']='started'
        self.assertIsNone(classify(result,raw))
        result,raw=fixture('drain');result['error']='cleanup error';self.assertIsNone(classify(result,raw))

    def test_process_matching_uses_tokens_not_own_script_or_shell_text(self):
        self.assertTrue(matrix_argv(['python','-m','langbench','matrix-run','plan','results/x','--resume'],'/tmp','/tmp/results/x'))
        self.assertFalse(matrix_argv(['zsh','-c','python -m langbench matrix-run plan results/x'],'/tmp','/tmp/results/x'))
        self.assertFalse(matrix_argv(['python','scripts/supervise_subscription_matrix.py','results/x'],'/tmp','/tmp/results/x'))
        self.assertFalse(matrix_argv(['python','-m','langbench','matrix-run','plan','elsewhere'],'/tmp','/tmp/results/x'))

    def test_attach_wait_resume_once_preserve_original_and_audit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cell=root/'0001';(cell/'trace').mkdir(parents=True)
            result,raw=fixture();(cell/'result.json').write_text(json.dumps(result));(cell/'trace/invocation-0.json').write_text(json.dumps(raw))
            original=(cell/'result.json').read_bytes();commit=hashlib.sha256(original).hexdigest()
            state={'state':'stopped_on_incident','cells':[{'id':'0001','state':'infrastructure_invalid','result_sha256':commit},{'id':'0002','state':'pending'}]}
            (root/'matrix.json').write_text(json.dumps(state))
            scans=iter([([42],[]),([42],[]),([],[]),([],[])])
            sleeps=[];calls=[]
            def run(command,**kwargs):
                calls.append(command)
                state['state']='closed_with_missing_cells';state['cells'][1]['state']='collected'
                (root/'matrix.json').write_text(json.dumps(state));return SimpleNamespace(returncode=1)
            end=supervise(root,'plan',{'kimi':'k','opencode':'o'},process_scan=lambda p:next(scans),orphan_check=lambda p:(True,{'clean':True}),run=run,sleep=sleeps.append)
            self.assertEqual(end,'closed_with_missing_cells');self.assertEqual(len(calls),1)
            self.assertIn('--resume',calls[0]);self.assertEqual(len(sleeps),1)
            self.assertEqual((cell/'result.json').read_bytes(),original)
            audit=[json.loads(line) for line in (root/'supervisor-audit.jsonl').read_text().splitlines()]
            self.assertEqual(audit[1]['raw_result_sha256'],commit)
            self.assertTrue((root/'outcome-overrides.jsonl').exists())

    def test_orphan_prevents_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cell=root/'0001';(cell/'trace').mkdir(parents=True)
            result,raw=fixture('drain');(cell/'result.json').write_text(json.dumps(result));(cell/'trace/invocation-0.json').write_text(json.dumps(raw))
            (root/'matrix.json').write_text(json.dumps({'state':'stopped_on_incident','cells':[{'id':'0001','state':'infrastructure_invalid','result_sha256':hashlib.sha256((cell/'result.json').read_bytes()).hexdigest()}]}))
            with self.assertRaises(RuntimeError):supervise(root,'plan',{'kimi':'k','opencode':'o'},process_scan=lambda p:([],[]),orphan_check=lambda p:(False,{}),run=lambda *a,**k:self.fail('must not launch'))

    def test_tampered_trace_disagrees_with_committed_events(self):
        result,raw=fixture()
        result['collection']['invocations'][0]['events'][-1]['part']['reason']='tool-calls'
        self.assertIsNone(classify(result,raw))

    def test_second_supervisor_cannot_repeat_no_progress_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);cell=root/'0001';(cell/'trace').mkdir(parents=True)
            result,raw=fixture();(cell/'result.json').write_text(json.dumps(result));(cell/'trace/invocation-0.json').write_text(json.dumps(raw))
            state={'state':'stopped_on_incident','cells':[{'id':'0001','state':'infrastructure_invalid','result_sha256':hashlib.sha256((cell/'result.json').read_bytes()).hexdigest()},{'id':'0002','state':'pending'}]}
            (root/'matrix.json').write_text(json.dumps(state));calls=[]
            def run(*args,**kwargs):calls.append(args);return SimpleNamespace(returncode=1)
            kwargs=dict(process_scan=lambda p:([],[]),orphan_check=lambda p:(True,{}),run=run)
            with self.assertRaisesRegex(RuntimeError,'no progress'):supervise(root,'plan',{'kimi':'k','opencode':'o'},**kwargs)
            self.assertEqual(len(calls),1)
            with self.assertRaisesRegex(RuntimeError,'no progress'):supervise(root,'plan',{'kimi':'k','opencode':'o'},**kwargs)
            self.assertEqual(len(calls),1)

    def test_second_controller_appearing_during_attach_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            scans=iter([([1],[]),([1,2],[])])
            with self.assertRaisesRegex(RuntimeError,'multiple matrix'):
                supervise(Path(temporary),'plan',{'kimi':'k','opencode':'o'},process_scan=lambda p:next(scans),sleep=lambda _:None,run=lambda *a,**k:self.fail('must not resume'))
