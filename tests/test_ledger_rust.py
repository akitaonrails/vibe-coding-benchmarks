"""Native Rust ledger parity and executable fault mutants."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'tasks' / 'ledger_engine'
spec = importlib.util.spec_from_file_location('ledger_rust_cases', ROOT / 'cases.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)


def execute(root, requests):
    result = subprocess.run(['sh', str(root / 'run.sh')],
                            input=''.join(json.dumps(request) + '\n' for request in requests),
                            text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise AssertionError(result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]


def build(root):
    subprocess.run(['sh', str(root / 'build.sh')], check=True, capture_output=True, timeout=120)


class LedgerRustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = ROOT / 'references/rust'
        cls.starter = ROOT / 'starters/rust'
        build(cls.reference)
        build(cls.starter)

    def test_reference_public_and_seeded_private(self):
        for suite, seed in [('public', 0), ('private', 29), ('private', 271)]:
            for case in catalog.cases(suite, seed):
                with self.subTest(suite=suite, seed=seed, case=case['id']):
                    self.assertEqual(execute(self.reference, case['requests']), case['expected'])

    def test_working_v1_baseline(self):
        for case in catalog.baseline_cases():
            with self.subTest(case=case['id']):
                actual = execute(self.starter, case['requests'])
                self.assertEqual(actual, case['expected'])
                self.assertEqual(actual, execute(self.reference, case['requests']))

    def test_starter_explicit_unimplemented_guarantees(self):
        requests = [
            {'op': 'begin', 'v': 2, 'tenant': 'a', 'actor': 'a', 'tx': 't'},
            {'op': 'begin', 'tx': 't'},
            {'op': 'commit', 'tx': 't', 'request': 'r', 'fault': {'keep': 0, 'tear': False}},
            {'op': 'stats'},
        ]
        self.assertEqual(execute(self.starter, requests), [
            {'error': 'unsupported_version'}, {'snapshot': 0},
            {'error': 'unsupported_fault'},
            {'revision': 0, 'journal_frames': 0, 'capacity': 64, 'transactions': 1},
        ])

    def test_compiled_semantic_mutants_are_rejected(self):
        mutations = [
            ('skip_conflict', 'solution.rs',
             'if !transaction.validates(&self.state)', 'if false'),
            ('skip_uniqueness', 'solution.rs',
             'if !transaction.proposed_unique(&self.state)', 'if false'),
            ('duplicate_receipt_reexecutes', 'solution.rs',
             'if let Some(revision) = self.state.receipts.get(&Key::new(owner, commit_id))',
             'if let Some(revision) = None::<&u64>'),
            ('checkpoint_publishes_after_one_write', 'device.rs',
             'fault.keep == 2 && !fault.tear', 'fault.keep >= 1 && !fault.tear'),
            ('torn_seal_commits', 'device.rs',
             '*proposed.last_mut().unwrap() = Frame::Torn;',
             'let _ignored_tear = &proposed;'),
            ('forget_tombstone_versions', 'domain.rs',
             'map_or(0, |entry| entry.version)',
             'map_or(0, |entry| if entry.row.is_some() { entry.version } else { 0 })'),
        ]
        cases = catalog.cases('public') + catalog.cases('private', 29)
        for name, file, old, new in mutations:
            with self.subTest(mutant=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp) / 'rust'
                shutil.copytree(self.reference, root, ignore=shutil.ignore_patterns('target'))
                source = root / 'src' / file
                text = source.read_text()
                self.assertIn(old, text)
                source.write_text(text.replace(old, new, 1))
                build(root)
                self.assertTrue(any(execute(root, case['requests']) != case['expected'] for case in cases), name)


if __name__ == '__main__':
    unittest.main()
