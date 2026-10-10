import json
from pathlib import Path
import sys
import tempfile
import unittest
from langbench.controller import collect, NUDGES
from langbench.core import digest_tree, validate_source, task_path
from langbench.metrics import UsageSemantics, normalize_usage
from langbench.process import execute
from langbench.report import summarize

class MetricsTests(unittest.TestCase):
    def event(self, ident='a', **usage):
        return {'type':'turn.completed','turn_id':ident,'usage':{'input_tokens':10,'cached_input_tokens':4,'output_tokens':5,**usage}}
    def test_unknown_semantics_never_invents_total(self):
        self.assertIsNone(normalize_usage([self.event()])['total_tokens'])
    def test_subset_not_added(self):
        result=normalize_usage([self.event()],UsageSemantics('per_turn','included',True,True))
        self.assertEqual(result['total_tokens'],15)
        self.assertEqual(result['uncached_input_tokens'],6)
    def test_duplicate_not_counted(self):
        event=self.event()
        self.assertEqual(normalize_usage([event,event],UsageSemantics('per_turn','included',True,True))['total_tokens'],15)
    def test_conflicting_duplicate_invalidates(self):
        result=normalize_usage([self.event(),self.event(input_tokens=20)],UsageSemantics('per_turn','included',True,True))
        self.assertIsNone(result['total_tokens'])
    def test_disjoint_reasoning_missing_is_not_zero(self):
        self.assertIsNone(normalize_usage([self.event()],UsageSemantics('per_turn','disjoint',True,True))['total_tokens'])
    def test_cumulative_is_differenced(self):
        result=normalize_usage([self.event(),self.event('b',input_tokens=30,output_tokens=12,cached_input_tokens=8)],UsageSemantics('cumulative_thread','included',True,True))
        self.assertEqual(result['total_tokens'],42)
    def test_missing_id_is_uncertain(self):
        event=self.event();del event['turn_id']
        self.assertIsNone(normalize_usage([event],UsageSemantics('per_turn','included',True,True))['total_tokens'])
    def test_zero_is_observed_not_missing(self):
        result=normalize_usage([self.event(input_tokens=0,output_tokens=0,cached_input_tokens=0)],UsageSemantics('per_turn','included',True,True))
        self.assertEqual(result['total_tokens'],0)

class BoundaryTests(unittest.TestCase):
    def test_task_traversal(self):
        with self.assertRaises(ValueError):task_path('../secrets')
    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'src';src.mkdir();(src/'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):validate_source(tmp)
    def test_hash_tracks_path_and_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'one';p.write_text('x');a=digest_tree(tmp)
            p.rename(Path(tmp)/'two');self.assertNotEqual(a,digest_tree(tmp))

class ControllerTests(unittest.TestCase):
    def test_exact_nudges_explicit_session_and_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace=Path(tmp)/'work';workspace.mkdir();(workspace/'file').write_text('0')
            calls=[]
            def invoke(prompt,session,budget):
                calls.append((prompt,session,budget));(workspace/'file').write_text(str(len(calls)))
                return {'status':'handoff','session_id':'one','seconds':1,'events':[]}
            result=collect(workspace,Path(tmp)/'result','task',invoke,base_seconds=7,continuation_seconds=3)
            self.assertEqual(calls,[('task',None,7),(NUDGES[0],'one',3),(NUDGES[1],'one',3)])
            self.assertEqual(result['nudges'],2)
            self.assertEqual((Path(tmp)/'result/snapshot-0/file').read_text(),'1')
    def test_timeout_gets_no_nudge(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)/'work';work.mkdir()
            result=collect(work,Path(tmp)/'result','task',lambda *a:{'status':'timeout','session_id':'x','seconds':1,'events':[]})
            self.assertEqual(result['nudges'],0)
    def test_changed_session_stops(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)/'work';work.mkdir()
            result=collect(work,Path(tmp)/'result','task',lambda p,s,b:{'status':'handoff','session_id':'a' if s is None else 'b','seconds':1,'events':[]})
            self.assertEqual(len(result['invocations']),2)
            self.assertEqual(result['invocations'][-1]['status'],'infrastructure_error')

class ProcessTests(unittest.TestCase):
    def test_both_streams_drain(self):
        result=execute([sys.executable,'-c',"import sys;sys.stdout.write('x'*100000);sys.stderr.write('y'*100000)"])
        self.assertEqual(len(result['stdout']),100000)
        self.assertEqual(len(result['stderr']),100000)
        self.assertEqual(result['returncode'],0)
    def test_timeout(self):
        result=execute([sys.executable,'-c','import time;time.sleep(10)'],timeout=.15)
        self.assertEqual(result['termination'],'timeout')
        self.assertLess(result['seconds'],2)
    def test_output_limit(self):
        result=execute([sys.executable,'-c',"print('x'*100000)"],output_limit=1000)
        self.assertEqual(result['termination'],'output_limit')

class ReportTests(unittest.TestCase):
    def test_invalid_not_silently_dropped(self):
        result=summarize([{'validity':'valid','success':True},{'validity':'infrastructure_invalid'}])
        self.assertEqual(result['operational_success_rate'],.5)
        self.assertEqual(result['missing_outcome_bounds'],[.5,1])

if __name__=='__main__':unittest.main()

class ManifestTests(unittest.TestCase):
    def manifest(self):
        return {'schema_version':1,'attempt_id':'attempt-1','task':'crash_store','language':'ruby','tests':'T0',
                'model':'gpt-6-astra','effort':'low','replicate':1,'block_id':'block-1','base_seconds':60,
                'continuation_seconds':30,'max_nudges':2,'auth_mode':'chatgpt','initial_artifact_sha256':'a'*64,
                'environment_digest':'unqualified','usage_qualified':False,'resolved_model':None}
    def test_freeze_and_detect_tamper(self):
        from langbench.manifest import freeze, load
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'manifest.json';digest=freeze(self.manifest(),path)
            self.assertEqual(load(path,digest),self.manifest())
            with self.assertRaises(FileExistsError):freeze(self.manifest(),path)
            path.write_text('{}')
            with self.assertRaises(ValueError):load(path,digest)
    def test_unknown_field_and_boolean_budget_rejected(self):
        from langbench.manifest import validate
        manifest=self.manifest();manifest['extra']='x'
        with self.assertRaises(ValueError):validate(manifest)
        manifest=self.manifest();manifest['base_seconds']=True
        with self.assertRaises(ValueError):validate(manifest)

class JsonContractTests(unittest.TestCase):
    def test_bool_is_not_number_even_nested(self):
        from langbench.public_driver import same_json
        self.assertFalse(same_json([{'version':True}],[{'version':1}]))
        self.assertFalse(same_json(False,0))
        self.assertTrue(same_json({'b':2,'a':[1]}, {'a':[1],'b':2}))
    def test_oversized_source_refused_before_hashing(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'src';src.mkdir()
            with (src/'huge').open('wb') as handle:handle.truncate(11*1024*1024)
            with patch.object(Path,'read_bytes',side_effect=AssertionError('must not read giant file')):
                with self.assertRaises(ValueError):validate_source(tmp)

class IncompleteUsageTests(unittest.TestCase):
    def test_failed_later_turn_keeps_partial_usage_uncertain(self):
        result=normalize_usage([
            {'type':'turn.completed','turn_id':'one','usage':{'input_tokens':3,'output_tokens':2}},
            {'type':'turn.started'}, {'type':'turn.failed'}],UsageSemantics('per_turn','included',False,True))
        self.assertIsNone(result['total_tokens'])
        self.assertEqual(result['raw_components']['input_tokens'],3)

class SnapshotProvenanceTests(unittest.TestCase):
    def test_nested_build_names_remain_source(self):
        from langbench.core import copy_workspace
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)/'workspace';nested=work/'src/target';nested.mkdir(parents=True)
            helper=nested/'helper.rb';helper.write_text('puts 1')
            (work/'target').mkdir();(work/'target/binary').write_text('omitted')
            initial=digest_tree(work,ignore_root_artifacts=True)
            helper.write_text('puts 2')
            self.assertNotEqual(initial,digest_tree(work,ignore_root_artifacts=True))
            src_initial=digest_tree(work/'src');helper.write_text('puts 3')
            self.assertNotEqual(src_initial,digest_tree(work/'src'))
            snapshot=Path(tmp)/'snapshot';copy_workspace(work,snapshot)
            self.assertEqual((snapshot/'src/target/helper.rb').read_text(),'puts 3')
            self.assertFalse((snapshot/'target').exists())
            self.assertEqual(digest_tree(work,ignore_root_artifacts=True),digest_tree(snapshot,ignore_root_artifacts=True))
