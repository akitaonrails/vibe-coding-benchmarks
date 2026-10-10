import copy
import json
from pathlib import Path
import tempfile
import unittest
from langbench.batch import batch

def plan():
    cells=[]
    for language in ('ruby','rust'):
        for tests in ('T1','T0'):
            cells.append({'task':'protocol_migration','language':language,'tests':tests,'model':'gpt-6-astra','effort':'low',
                'replicate':1,'block_id':'paired-1','semantic_seed':7,'base_seconds':180,'continuation_seconds':60,
                'max_nudges':2,'auth_mode':'chatgpt'})
    return {'schema_version':1,'seed':3,'scored_execution_qualified':False,'cells':cells}

class BatchTests(unittest.TestCase):
    def save(self,temp,value=None):
        path=Path(temp)/'input.json';path.write_text(json.dumps(value or plan()));return path
    def test_frozen_prefix_executes_sequentially_and_preserves_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            source=self.save(temp);calls=[];output=Path(temp)/'batch'
            def run(task,language,path,**kwargs):
                self.assertEqual((output/'plan.json').read_bytes(),source.read_bytes())
                self.assertEqual(len(json.loads((output/'batch.json').read_text())['attempts']),len(calls))
                calls.append((task,language,path,kwargs))
                return {'kind':'development_smoke','validity':'valid_smoke','collection':{'invocations':[]}}
            result=batch(source,output,limit=3,runner=run)
            self.assertEqual([(c[1],c[3]['tests']) for c in calls],[('ruby','T1'),('ruby','T0'),('rust','T1')])
            self.assertEqual(calls[0][3]['seed'],7);self.assertEqual(calls[0][3]['base_seconds'],180)
            self.assertEqual(result['selected_count'],3);self.assertEqual(result['state'],'complete')
            self.assertEqual(len({c[2] for c in calls}),3)
            self.assertEqual(len(result['attempts']),3)
            self.assertEqual(json.loads((output/'batch.json').read_text()),result)
    def test_invalid_later_selected_cell_rejected_before_any_call(self):
        for field,value in [('base_seconds',True),('model','unknown'),('language','haskell'),('max_nudges',3),
                            ('semantic_seed',-1),('auth_mode','api_key'),('effort','invalid'),('block_id','bad\nblock')]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temp:
                data=plan();data['cells'][1][field]=value;source=self.save(temp,data);calls=[]
                with self.assertRaises(ValueError):batch(source,Path(temp)/'out',runner=lambda *a,**k:calls.append(a))
                self.assertEqual(calls,[]);self.assertFalse((Path(temp)/'out').exists())
    def test_scored_plan_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            data=plan();data['scored_execution_qualified']=True
            with self.assertRaises(ValueError):batch(self.save(temp,data),Path(temp)/'out',runner=lambda *a,**k:self.fail('inference'))
    def test_incident_stops_and_keeps_failed_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            def run(*args,**kwargs):
                calls.append(args)
                return {'validity':'valid_smoke' if len(calls)==1 else 'infrastructure_invalid'}
            output=Path(temp)/'out';result=batch(self.save(temp),output,runner=run)
            self.assertEqual(len(calls),2);self.assertEqual(result['state'],'stopped_on_incident')
            self.assertTrue((output/result['attempts'][1]['result_path']).exists())
            events=[json.loads(line) for line in (output/'progress.jsonl').read_text().splitlines()]
            self.assertEqual(events[-1]['validity'],'infrastructure_invalid')
    def test_quota_stops_even_if_result_is_mislabeled_valid(self):
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            def run(*args,**kwargs):
                calls.append(args);return {'validity':'valid_smoke','collection':{'invocations':[{'status':'quota'}]}}
            result=batch(self.save(temp),Path(temp)/'out',runner=run)
            self.assertEqual(len(calls),1);self.assertTrue(result['attempts'][0]['quota'])
    def test_interruption_preserves_prior_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            calls=[]
            def run(*args,**kwargs):
                calls.append(args)
                if len(calls)==2:raise KeyboardInterrupt
                return {'validity':'valid_smoke'}
            output=Path(temp)/'out';result=batch(self.save(temp),output,runner=run)
            self.assertEqual(result['state'],'interrupted');self.assertEqual(len(result['attempts']),2)
            self.assertEqual(json.loads((output/'batch.json').read_text())['state'],'interrupted')
    def test_existing_destination_never_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FileExistsError):batch(self.save(temp),temp,runner=lambda *a,**k:self.fail('inference'))

if __name__=='__main__':unittest.main()
