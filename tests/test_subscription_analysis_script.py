"""Fake receipts only: no inference, Docker, toolchain or candidate execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('analysis_script', Path(__file__).resolve().parents[1]/'scripts/analyze_subscription_matrix.py')
a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(a)
from langbench.matrix import make_plan


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = make_plan()
        self.write('plan.json', self.plan)
        self.progress = {'state': 'running', 'plan_sha256': a.sha((self.root/'plan.json').read_bytes()),
                         'cells': [{'id': c['id'], 'state': 'pending'} for c in self.plan['cells']]}
        self.write('matrix.json', self.progress)

    def write(self, name, data):
        p = self.root/name;p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
        return p

    def add(self, status='timeout', success=True, records=None, available=True):
        cell = self.plan['cells'][0]
        manifest = {k:v for k,v in cell.items() if k != 'id'}
        invocation = {'index': 0, 'status': status, 'seconds': 900, 'tool_records': [],
                      'usage_records': records or [], 'request_records': [{'index':0,'response_complete':True,'http_status':200}] if records else [],
                      'usage_coverage_verified': bool(records)}
        checkpoint = {'index': 0, 'artifact_available': available, 'artifact_sha256': 'saved',
                      'declared_status': 'COMPLETE' if status == 'handoff' else None}
        result = {'validity': 'valid_development', 'manifest': manifest,
                  'manifest_sha256': a.sha(json.dumps(manifest, sort_keys=True).encode()),
                  'requested': {k:cell[k] for k in ('task','language','tests','provider','model','effort')},
                  'collection': {'invocations': [invocation], 'checkpoints': [checkpoint],
                                 'active_seconds': 900, 'interventions': []},
                  'grades': [{'index': 0, 'task':cell['task'], 'language':cell['language'],
                              'seed':cell['semantic_seed'], 'validity':'valid', 'success':success,
                              'groups':{'durability':success}, 'cases':[]}] if available else []}
        self.save_result(result)
        return result

    def save_result(self, result):
        cell = self.plan['cells'][0]
        p = self.write(cell['id']+'/result.json', result)
        self.progress['cells'][0].update(state='collected', result_sha256=a.sha(p.read_bytes()))
        self.write('matrix.json', self.progress)

    def override(self, **extras):
        row = {'schema_version':1, 'cell':self.plan['cells'][0]['id'],
               'raw_result_sha256':self.progress['cells'][0]['result_sha256'],
               'analysis_classification':'model_output_limit', 'actor':'test operator',
               'time':'now', 'action':'preserve', 'evidence':{'reason':'length'}, **extras}
        (self.root/'outcome-overrides.jsonl').write_text(json.dumps(row)+'\n')
        return row

    def test_all_cells_and_timeout_not_completion(self):
        self.add()
        report = a.analyze(self.root)
        self.assertEqual(len(report['attempts']),56)
        self.assertEqual(report['status'],'INTERIM')
        first = report['attempts'][0]
        self.assertTrue(first['correct_at_deadline'])
        self.assertFalse(first['normal_completed_and_correct'])
        self.assertIsNone(report['attempts'][1]['nudge_count'])
        self.assertEqual(sum(s['planned_attempts'] for s in report['summary']),56)
        self.assertIn('INTERIM',a.markdown(report))

    def test_normal_completion(self):
        self.add(status='handoff')
        self.assertTrue(a.analyze(self.root)['attempts'][0]['normal_completed_and_correct'])

    def test_override_and_sha_tamper(self):
        self.add(status='infrastructure_error',success=False)
        self.override()
        row = a.analyze(self.root)['attempts'][0]
        self.assertEqual(row['raw_terminal_status'],'infrastructure_error')
        self.assertEqual(row['analysis_terminal_status'],'model_output_limit')
        self.assertFalse(row['final']['correct'])
        self.override(raw_result_sha256='wrong')
        with self.assertRaisesRegex(ValueError,'override result SHA'):
            a.analyze(self.root)

    def test_supervisor_override_process_binding(self):
        self.add(status='infrastructure_error')
        p = self.write(self.plan['cells'][0]['id']+'/trace/invocation-0.json',{'returncode':0})
        self.override(evidence=None,signature='model_output_limit',raw_process_sha256=a.sha(p.read_bytes()),cleanup_evidence={})
        self.assertTrue(a.analyze(self.root)['attempts'][0]['output_limit'])
        p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'process SHA'):
            a.analyze(self.root)

    def test_missing_usage_artifact_unknown(self):
        self.add(available=False)
        row = a.analyze(self.root)['attempts'][0]
        self.assertIsNone(row['final']['correct'])
        self.assertIsNone(row['final']['source_size'])
        self.assertIsNone(row['usage']['provider_total'])
        self.assertIsNone(row['usage']['components']['cache_write']['total'])

    def test_inclusive_components_not_double_counted(self):
        record = {'provider':'opencode','request_id':'transport-0','valid':True,'native_fields_verified':True,
                  'provider_reported_total':130,'components':{'input_including_cache':100,
                  'output_including_reasoning':30,'cache_read':80,'reasoning':20,'cache_write':None}}
        self.add(records=[record,record])
        u = a.analyze(self.root)['attempts'][0]['usage']
        self.assertEqual(u['provider_total'],130)
        self.assertEqual(u['components']['reasoning']['total'],20)
        self.assertEqual(u['native_usage_record_count'],1)
        self.assertIsNone(u['components']['cache_write']['total'])
        r = a.read_json(self.root/self.plan['cells'][0]['id']/'result.json')
        r['collection']['invocations'][0]['usage_coverage_verified']=False
        self.save_result(r)
        u = a.analyze(self.root)['attempts'][0]['usage']
        self.assertIsNone(u['provider_total'])
        self.assertEqual(u['provider_known_subtotal'],130)
        self.assertEqual(u['components']['cache_read']['known_subtotal'],80)

    def test_identity_and_result_hash(self):
        r = self.add()
        r['requested']['language']='wrong';self.save_result(r)
        with self.assertRaisesRegex(ValueError,'treatment mismatch'):
            a.analyze(self.root)
        self.add()
        p = self.root/self.plan['cells'][0]['id']/'result.json';p.write_text('{}')
        with self.assertRaisesRegex(ValueError,'result SHA'):
            a.analyze(self.root)

    def test_final_checkpoint_missing_grade_remains_unknown(self):
        r=self.add()
        r['collection']['checkpoints'].append({'index':1,'artifact_available':False})
        r['collection']['invocations'].append({'index':1,'status':'timeout','seconds':180})
        self.save_result(r)
        row=a.analyze(self.root)['attempts'][0]
        self.assertTrue(row['initial']['correct'])
        self.assertIsNone(row['final']['correct'])
        self.assertIsNone(row['tool_effort']['observed_repair_cycles'])

    def test_conflicting_usage_not_a_known_subtotal(self):
        record = {'provider':'opencode','request_id':'transport-0','valid':True,'native_fields_verified':True,
                  'provider_reported_total':130,'components':{}}
        self.add(records=[record,{**record,'provider_reported_total':140}])
        usage=a.analyze(self.root)['attempts'][0]['usage']
        self.assertIsNone(usage['provider_total'])
        self.assertIsNone(usage['provider_known_subtotal'])
        self.assertTrue(usage['conflicts'])

    def test_usage_flag_cannot_replace_request_reconciliation(self):
        record = {'provider':'opencode','request_id':'transport-0','valid':True,
                  'native_fields_verified':True,'provider_reported_total':130,'components':{}}
        result = self.add(records=[record])
        requests = result['collection']['invocations'][0]['request_records']
        requests.append({'index':1,'response_complete':True,'http_status':200})
        self.save_result(result)
        observed=a.analyze(self.root)['attempts'][0]['usage']
        self.assertIsNone(observed['provider_total'])
        self.assertEqual(observed['provider_known_subtotal'],130)
        self.assertFalse(observed['native_coverage_complete'])
        requests.pop()
        requests[0]['index']=9
        self.save_result(result)
        self.assertFalse(a.analyze(self.root)['attempts'][0]['usage']['native_coverage_complete'])

    def test_success_grade_with_unavailable_artifact_rejected(self):
        result=self.add()
        result['collection']['checkpoints'][0]['artifact_available']=False
        self.save_result(result)
        with self.assertRaisesRegex(ValueError,'unavailable artifact'):
            a.analyze(self.root)

    def test_plan_tamper_rejected(self):
        self.plan['cells'][0]['base_seconds']=901;self.write('plan.json',self.plan)
        with self.assertRaises(ValueError):a.analyze(self.root)

    def test_progress_omission_rejected(self):
        self.progress['cells'].pop();self.write('matrix.json',self.progress)
        with self.assertRaisesRegex(ValueError,'all planned'):
            a.analyze(self.root)

    def test_active_uncommitted_receipt_not_read(self):
        self.progress['cells'][0]['state']='running';self.write('matrix.json',self.progress)
        p=self.root/self.plan['cells'][0]['id']/'result.json';p.parent.mkdir();p.write_text('incomplete JSON')
        self.assertIsNone(a.analyze(self.root)['attempts'][0]['result_sha256'])


if __name__ == '__main__':unittest.main()
