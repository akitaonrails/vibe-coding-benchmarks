"""Native python ledger parity, working baseline, and actual semantic mutants."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from langbench.public_driver import same_json

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'tasks/ledger_engine'
spec = importlib.util.spec_from_file_location('python_ledger_cases', TASK / 'cases.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


@unittest.skipUnless(shutil.which('python3'), 'python toolchain unavailable')
class LedgerPythonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scratch = tempfile.TemporaryDirectory()
        cls.roots = {}
        for kind in ('starters', 'references'):
            dest = Path(cls.scratch.name) / kind
            shutil.copytree(TASK / kind / 'python', dest, ignore=shutil.ignore_patterns('target', '__pycache__'))
            built = subprocess.run(['./build.sh'], cwd=dest, text=True, capture_output=True, timeout=30)
            if built.returncode:
                raise AssertionError(built.stderr)
            cls.roots[kind] = dest

    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()

    def outputs(self, root, requests):
        result = subprocess.run(['./run.sh'], cwd=root, text=True,
            input=''.join(json.dumps(q) + '\n' for q in requests), capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines()]

    def check_case(self, kind, case):
        got = self.outputs(self.roots[kind], case['requests'])
        self.assertTrue(same_json(got, case['expected']), case['id'])

    def test_working_v1_starter(self):
        for case in fixtures.baseline_cases():
            with self.subTest(case=case['id']): self.check_case('starters', case)

    def test_reference_public(self):
        for case in fixtures.cases('public'):
            with self.subTest(case=case['id']): self.check_case('references', case)

    def test_reference_private_seeds(self):
        for seed in (0, 29, 271):
            for case in fixtures.cases('private', seed):
                with self.subTest(seed=seed, case=case['id']): self.check_case('references', case)

    def test_starter_scope_guards_preserve_state(self):
        requests = [{'op':'begin','tx':'t'}, {'op':'put','tx':'t','id':'a','value':1},
            {'op':'commit','tx':'t','request':'r','fault':{'keep':0,'tear':False}},
            {'op':'checkpoint','fault':{'keep':2,'tear':False}}, {'op':'stats'},
            {'op':'begin','v':2,'tenant':'a','actor':'a','tx':'x'}]
        expected = [{'snapshot':0},{'ok':True},{'error':'unsupported_fault'},
            {'error':'unsupported_fault'}, {'revision':0,'journal_frames':0,'capacity':64,'transactions':1},
            {'error':'unsupported_version'}]
        self.assertTrue(same_json(self.outputs(self.roots['starters'], requests), expected))

    def test_hand_derived_torn_seal_and_successful_retry(self):
        requests = [{'op':'begin','tx':'t'}, {'op':'put','tx':'t','id':'a','value':7,'note':None},
            {'op':'commit','tx':'t','request':'r','fault':{'keep':3,'tear':True}},
            {'op':'stats'}, {'op':'commit','request':'r'}, {'op':'begin','tx':'t'},
            {'op':'put','tx':'t','id':'a','value':7,'note':None}, {'op':'commit','tx':'t','request':'r'},
            {'op':'crash'}, {'op':'commit','request':'r'}, {'op':'begin','tx':'read'}, {'op':'read','tx':'read','id':'a'}]
        expected = [{'snapshot':0},{'ok':True},{'error':'interrupted'},
            {'revision':0,'journal_frames':0,'capacity':64,'transactions':0},
            {'error':'transaction_missing'}, {'snapshot':0},{'ok':True},{'committed':1},
            {'recovered':1},{'committed':1},{'snapshot':1},{'record':{'id':'a','value':7,'note':None}}]
        self.assertTrue(same_json(self.outputs(self.roots['references'], requests), expected))

    def test_actual_native_semantic_mutants(self):
        mutations = [('skip_conflict', 'solution.py', 'if not tx.valid(self.table):', 'if False:', 'read_conflict_after_checkpoint'), ('skip_unique', 'solution.py', 'if not self.table.overlay(tx.writes).unique():', 'if False:', 'unique_swap_rollback_and_retry'), ('skip_receipt', 'solution.py', "if op == 'commit' and (tenant, request['request']) in self.receipts:", 'if False:', 'dedup_lost_ack_checkpoint'), ('early_checkpoint', 'device.py', "fault['keep'] == 2 and not fault['tear']", "fault['keep'] >= 1 and not fault['tear']", 'checkpoint_migration_cut_1_False'), ('ignore_torn', 'device.py', "if fault is not None and fault['tear']:", 'if False:', 'journal_cut_4_True'), ('drop_tombstone_version', 'table.py', 'return item.version if item else 0', 'return item.version if item and item.row is not None else 0', 'blind_write_aba_tombstone')]
        public = {case['id']: case for case in fixtures.cases('public')}
        for name, filename, original, replacement, case_id in mutations:
            with self.subTest(mutation=name), tempfile.TemporaryDirectory() as folder:
                dest = Path(folder) / 'native'
                shutil.copytree(self.roots['references'], dest, ignore=shutil.ignore_patterns('target', '__pycache__'))
                path = dest / 'src' / filename
                source = path.read_text()
                self.assertEqual(source.count(original), 1, name)
                path.write_text(source.replace(original, replacement))
                built = subprocess.run(['./build.sh'], cwd=dest, text=True, capture_output=True, timeout=30)
                self.assertEqual(built.returncode, 0, built.stderr)
                case = public[case_id]
                self.assertFalse(same_json(self.outputs(dest, case['requests']), case['expected']), name)
