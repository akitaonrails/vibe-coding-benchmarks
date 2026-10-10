"""Native reference parity, hand-derived oracle anchors, and semantic mutation gates."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'tasks' / 'protocol_migration'
spec = importlib.util.spec_from_file_location('migration_cases', ROOT / 'cases.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def execute(root, requests):
    proc = subprocess.run(['sh', str(root / 'run.sh')], input=''.join(json.dumps(r)+'\n' for r in requests), text=True, capture_output=True, timeout=10)
    if proc.returncode:
        raise AssertionError(proc.stderr)
    return [json.loads(line) for line in proc.stdout.splitlines()]


class ProtocolMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for variant in ('references', 'starters'):
            for language in ('ruby', 'rust'):
                subprocess.run(['sh', str(ROOT / variant / language / 'build.sh')], check=True, capture_output=True, timeout=120)

    def test_hand_derived_oracle(self):
        requests = [dict(v=2,tenant='a',actor='a',id='x',op=op,**extra) for op,extra in [
            ('submit',{'payload':None}),('cancel',{}),('retry',{}),('complete',{'generation':1}),('get',{})]]
        base = dict(tenant='a',id='x')
        self.assertEqual(catalog.oracle(requests),[
            {'record':dict(base,state='pending',generation=1,payload=None)},
            {'record':dict(base,state='cancelled',generation=1)},
            {'record':dict(base,state='pending',generation=2)},
            {'error':'stale'},
            {'record':dict(base,state='pending',generation=2)}])
        self.assertEqual(catalog.oracle([dict(op='import',id='x',stored=dict(schema=1,id='x',status='error',value=None)),dict(v=2,op='get',id='x',tenant='legacy',actor='legacy')]),[
            {'record':{'id':'x','status':'error','value':None}},
            {'record':dict(tenant='legacy',id='x',state='failed',generation=1,payload=None,reason='legacy_error')}])

    def test_imported_cancelled_record_preserves_payload(self):
        requests = [dict(v=2,tenant='alpha',actor='alpha',id='job',op=op,**extra)
                    for op,extra in [('import',{'stored':dict(schema=2,tenant='alpha',id='job',state='cancelled',generation=7,payload=None)}),('cancel',{}),('export',{})]]
        record = dict(tenant='alpha',id='job',state='cancelled',generation=7,payload=None)
        expected = [{'record':record}, {'record':record}, {'stored':dict(record,schema=2)}]
        self.assertEqual(catalog.oracle(requests), expected)
        for language in ('ruby','rust'):
            with self.subTest(language=language):
                self.assertEqual(execute(ROOT/'references'/language,requests),expected)

    def test_native_references_public_and_private(self):
        for language in ('ruby','rust'):
            for suite,seed in [('public',0),('private',17),('private',932)]:
                for case in catalog.cases(suite,seed):
                    with self.subTest(language=language,suite=suite,seed=seed,case=case['id']):
                        self.assertEqual(execute(ROOT/'references'/language,case['requests']),case['expected'])

    def test_starters_are_equivalent_working_v1(self):
        for case in catalog.cases('public'):
            if any(q.get('v',1)!=1 for q in case['requests']):
                continue
            for language in ('ruby','rust'):
                with self.subTest(language=language,case=case['id']):
                    self.assertEqual(execute(ROOT/'starters'/language,case['requests']),case['expected'])
        r=[dict(v=2,op='get',id='x',tenant='a',actor='a')]
        for language in ('ruby','rust'):
            self.assertEqual(execute(ROOT/'starters'/language,r),[{'error':'unsupported_version'}])

    def test_critical_semantic_mutants_are_killed(self):
        mutants = [
            ('compatibility','domain.rb',"'ready'=>'ok'","'ready'=>'pending'"),
            ('authorization','solution.rb',"version == 2 && q['actor'] != tenant","false"),
            ('identity','domain.rb','[tenant, id]','id'),
            ('presence','solution.rb',"if q.key?('payload')","if q['payload']"),
            ('lifecycle','worker.rb',"request['generation'] != record['generation']","false"),
            ('cache','repository.rb','@cache.delete(key)','# stale cache'),
            ('migration','domain.rb',"out['reason'] = 'legacy_error'","out['reason'] = 'wrong_reason'"),
        ]
        public=catalog.cases('public')
        for group,file,old,new in mutants:
            with self.subTest(group=group),tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/'ruby'
                shutil.copytree(ROOT/'references'/'ruby',root)
                path=root/'src'/file
                source=path.read_text()
                self.assertIn(old,source)
                path.write_text(source.replace(old,new))
                relevant=[c for c in public if c['group']==group]
                self.assertTrue(any(execute(root,c['requests'])!=c['expected'] for c in relevant),f'survived: {group}')

    def test_seed_reproducibility_and_inventory(self):
        self.assertEqual(catalog.cases('private',13),catalog.cases('private',13))
        self.assertNotEqual(catalog.cases('private',13),catalog.cases('private',14))
        metadata=json.loads((ROOT/'task.json').read_text())
        self.assertEqual(set(metadata['critical_groups']),{c['group'] for c in catalog.cases('public')})


if __name__ == '__main__':
    unittest.main()
