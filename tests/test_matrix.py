import copy
import json
from pathlib import Path
import tempfile
import unittest

from langbench.matrix import make_plan, run_matrix, validate_plan


class MatrixTests(unittest.TestCase):
    def setup_files(self, root):
        root = Path(root)
        plan = root / 'plan.json'
        plan.write_text(json.dumps(make_plan()))
        qualifications = {}
        for provider in ('kimi', 'opencode'):
            path = root / f'{provider}.json'
            path.write_text(json.dumps({'passed': True, 'provider': provider}))
            qualifications[provider] = path
        return plan, root / 'output', qualifications

    def test_design_contains_every_paired_cell_once(self):
        cells = validate_plan(make_plan())
        self.assertEqual(len(cells), 56)
        identities = {(c['language'], c['provider'], c['tests'], c['replicate']) for c in cells}
        self.assertEqual(len(identities), 56)
        for field, value in [('base_seconds', 1), ('max_nudges', 3), ('language', 'elixir')]:
            changed = copy.deepcopy(make_plan())
            changed['cells'][-1][field] = value
            with self.assertRaises(ValueError):
                validate_plan(changed)

    def test_preserves_failures_and_never_equalizes_work(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, quals = self.setup_files(root)
            calls = []
            def runner(task, language, path, **kwargs):
                calls.append(kwargs)
                return {'validity': 'valid_development', 'grades': [{'success': False}]}
            state = run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, runner=runner)
            self.assertEqual(state['state'], 'complete')
            self.assertEqual(len(calls), 56)
            self.assertEqual(calls[0]['base_seconds'], 900)
            self.assertIn(calls[0]['tests'], ('T0', 'T1'))
            run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, resume=True,
                       runner=lambda *a, **kw: self.fail('repeated attempt'))

    def test_quota_blocks_only_affected_provider(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, quals = self.setup_files(root)
            calls = []
            def runner(*args, **kwargs):
                calls.append(kwargs['provider'])
                return {'validity': 'valid_development', 'collection': {'invocations': [
                    {'status': 'quota' if kwargs['provider'] == 'kimi' else 'handoff'}]}}
            state = run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, runner=runner)
            self.assertEqual(calls.count('kimi'), 1)
            self.assertEqual(calls.count('opencode'), 28)
            self.assertEqual(sum(i['state'] == 'not_run_quota' for i in state['cells']), 27)
            self.assertEqual(state['state'], 'closed_with_missing_cells')

    def test_resume_does_not_retry_incident_and_detects_mutation(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, quals = self.setup_files(root)
            state = run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"},
                               runner=lambda *a, **kw: {'validity': 'infrastructure_invalid'})
            self.assertEqual(state['state'], 'stopped_on_incident')
            calls = []
            state = run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, resume=True,
                               runner=lambda *a, **kw: calls.append(a) or {'validity': 'valid_development'})
            self.assertEqual(len(calls), 55)
            self.assertEqual(state['cells'][0]['state'], 'infrastructure_invalid')
            path = output / state['cells'][1]['id'] / 'result.json'
            path.write_text('{}')
            with self.assertRaises(ValueError):
                run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, resume=True)

    def test_interruption_is_retained_without_replacement(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, quals = self.setup_files(root)
            def runner(*a, **kw):
                raise KeyboardInterrupt
            state = run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, runner=runner)
            self.assertEqual(state['cells'][0]['state'], 'interrupted_unknown')
            calls = []
            state = run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"}, resume=True,
                               runner=lambda *a, **kw: calls.append(a) or {'validity': 'valid_development'})
            self.assertEqual(len(calls), 55)
            self.assertEqual(state['state'], 'closed_with_missing_cells')

    def test_unqualified_provider_and_changed_plan_refused_before_inference(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, quals = self.setup_files(root)
            quals['kimi'].write_text('{"passed": false}')
            with self.assertRaises(ValueError):
                run_matrix(plan, output, qualifications=quals, binding={"test": "fixture"},
                           runner=lambda *a, **kw: self.fail('inference'))
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
