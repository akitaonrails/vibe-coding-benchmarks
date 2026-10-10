import copy
from pathlib import Path
import tempfile
import unittest
from langbench.size import inventory
from langbench.difficulty import calibrate

def evidence():
    results=[];metadata={}
    for instance in range(3):
        task='instance'+str(instance)
        metadata[task]={'difficulty':{'role':'calibration_candidate','independent_instance_id':task,'independence_reviewed':True}}
        for replicate in (1,2):
            for language in ('ruby','rust'):
                results.append({'manifest':{'attempt_id':f'{task}-{replicate}-{language}','task':task,'replicate':replicate,
                    'language':language,'model':'gpt-6-astra','effort':'low','base_seconds':900,'tests':'T1'},
                    'scored_benchmark_qualified':False,
                    'collection':{'invocations':[{'index':0,'status':'handoff','artifact_available':True}]},
                    'grades':[{'index':0,'validity':'valid','success':language=='ruby'}]})
    return results,metadata

class DifficultyTests(unittest.TestCase):
    def test_does_not_select_for_equal_language_success_rates(self):
        results,metadata=evidence();result=calibrate(results,metadata)
        self.assertTrue(result['difficulty_gate_passed'])
        self.assertFalse(result['comparison_eligible'])
        self.assertFalse(result['policy']['equal_language_success_rates_required'])
    def test_ceiling_controls_cannot_be_promoted_by_size(self):
        results,metadata=evidence();results=results[:4]
        for row in results:row['grades'][0]['success']=True;row['source_lines']=100000
        for meta in metadata.values():meta['difficulty']['role']='smoke_control'
        result=calibrate(results,metadata)
        self.assertTrue(result['first_handoff_ceiling_observed']);self.assertFalse(result['frontier_eligible'])
    def test_infrastructure_and_timeouts_excluded_and_cannot_qualify(self):
        results,metadata=evidence();results[0]['collection']['invocations'][0]['status']='timeout'
        results[1]['collection']['invocations'][0]['status']='infrastructure_error'
        result=calibrate(results,metadata)
        self.assertEqual(result['valid_initial_outcomes'],10)
        self.assertEqual(sum(result['excluded'].values()),2)
        self.assertFalse(result['difficulty_gate_passed'])
    def test_seed_changes_are_not_independent_instances(self):
        results,metadata=evidence()
        for meta in metadata.values():meta['difficulty']['independent_instance_id']='same-task'
        for seed,row in enumerate(results):row['manifest']['semantic_seed']=seed
        result=calibrate(results,metadata)
        self.assertEqual(result['reviewed_independent_instances'],1)
        self.assertFalse(result['frontier_eligible'])
    def test_duplicate_attempts_do_not_inflate_calibration(self):
        results,metadata=evidence();result=calibrate(results+[copy.deepcopy(results[0])],metadata)
        self.assertEqual(result['valid_initial_outcomes'],12)
        self.assertFalse(result['difficulty_gate_passed'])

class SourceInventoryTests(unittest.TestCase):
    def test_paths_comments_blanks_and_actual_diff(self):
        with tempfile.TemporaryDirectory() as temp:
            before=Path(temp)/'before';after=Path(temp)/'after';before.mkdir();after.mkdir()
            (before/'main.rb').write_text('# note\n\nputs 1\n')
            (after/'main.rb').write_text('# note\n\nputs 2\n')
            (after/'tests').mkdir();(after/'tests/test_main.rb').write_text('assert true\n')
            result=inventory(after,before)
            self.assertEqual(result['groups']['production']['physical_lines'],3)
            self.assertEqual(result['groups']['production']['nonblank_lines'],2)
            self.assertEqual(result['groups']['production']['comment_only_lines_heuristic'],1)
            self.assertEqual(result['groups']['tests']['physical_lines'],1)
            self.assertEqual(result['changed_lines_vs_starter'],{'added':2,'removed':1,'total':3})
    def test_nested_target_is_counted_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'target').mkdir();(root/'target/helper.rs').write_text('fn f() {}\n')
            self.assertEqual(inventory(root)['groups']['production']['physical_lines'],1)
            (root/'escape').symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):inventory(root)

class InlineTestClassificationTests(unittest.TestCase):
    def test_rust_inline_test_file_is_marked_mixed_not_all_production(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'main.rs').write_text('fn main() {}\n#[cfg(test)]\nmod tests { #[test] fn works() {} }\n')
            result=inventory(temp)
            self.assertEqual(result['groups']['production']['physical_lines'],0)
            self.assertEqual(result['groups']['mixed_production_and_tests']['physical_lines'],3)

class DiffBoundsTests(unittest.TestCase):
    def test_repetitive_large_diff_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as temp:
            before=Path(temp)/'before';after=Path(temp)/'after';before.mkdir();after.mkdir()
            (before/'main.rb').write_text('same\n'*2000)
            (after/'main.rb').write_text('same\n'*1999+'changed\n')
            result=inventory(after,before)['changed_lines_vs_starter']
            self.assertFalse(result['available'])
            self.assertIsNone(result['total'])
            self.assertEqual(result['files'],['main.rb'])
