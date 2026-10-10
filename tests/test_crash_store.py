import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'tasks/crash_store'
spec = importlib.util.spec_from_file_location('crash_cases', TASK / 'cases.py')
CASES = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CASES)


def execute(path, case):
    result = subprocess.run([str(path / 'run.sh')], input=''.join(json.dumps(r)+'\n' for r in case['requests']),
                            text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]


class CrashStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = CASES.cases('public') + CASES.cases('private', 271828)
        for language in ('ruby', 'rust'):
            subprocess.run([str(TASK / 'references' / language / 'build.sh')], check=True,
                           capture_output=True, timeout=120)

    def test_references_match_history_oracle(self):
        for language in ('ruby', 'rust'):
            for case in self.cases:
                with self.subTest(language=language, case=case['id']):
                    self.assertEqual(case['expected'], execute(TASK/'references'/language, case))

    def test_hand_derived_publication_boundary(self):
        m = CASES.History()
        self.assertEqual({'ok':True},m.call({'op':'init','capacity':4}))
        self.assertEqual({'crashed':True},m.call({'op':'commit','changes':[['x','v']], 'cut':1}))
        self.assertEqual({'data':{}},m.call({'op':'read'}))
        self.assertEqual({'used':1,'live':0,'snapshots':0},m.call({'op':'status'}))
        self.assertEqual({'reclaimed':1},m.call({'op':'reclaim'}))
        m.call({'op':'commit','changes':[['x','v']], 'cut':2})
        self.assertEqual({'data':{'x':'v'}},m.call({'op':'read'}))

    def test_semantic_mutants_rejected(self):
        source = (TASK/'references/ruby/src/solution.rb').read_text()
        mutations = {
            'publish_before_final_step': ('if steps > n', 'if steps >= n'),
            'lose_acknowledged_data': ("when 'crash'\n      {'ok'=>true}", "when 'crash'\n      @data = {}; {'ok'=>true}"),
            'reclaim_snapshot_live_pages': ('Set.new(@pages + @snapshots.values.flat_map { |s| s[1] })', 'Set.new(@pages)'),
            'never_reclaim': ('@allocated.delete(p)', 'nil'),
            'accept_stale_snapshot': ("s ? {'data'=>s[0].dup} : {'error'=>'snapshot'}", "s ? {'data'=>s[0].dup} : {'data'=>@data.dup}"),
            'ignore_full_capacity': ('@allocated.size+n > @capacity', 'false'),
        }
        for name, (old,new) in mutations.items():
            with self.subTest(mutant=name), tempfile.TemporaryDirectory() as temp:
                self.assertIn(old,source)
                path=Path(temp)/'ruby'
                shutil.copytree(TASK/'references/ruby',path)
                (path/'src/solution.rb').write_text(source.replace(old,new))
                self.assertTrue(any(execute(path,c)!=c['expected'] for c in self.cases), name)

    def test_suite_reproducibility_and_groups(self):
        self.assertEqual(CASES.cases('private',3),CASES.cases('private',3))
        self.assertNotEqual(CASES.cases('private',3),CASES.cases('private',4))
        self.assertEqual(set(CASES.critical_groups),{c['group'] for c in CASES.cases('public')})
        with self.assertRaises(ValueError): CASES.cases('typo')

if __name__ == '__main__':
    unittest.main()
