import copy
import json
from pathlib import Path
import tempfile
import unittest

from langbench.later_matrix import make_plan, run_matrix, validate_plan
from langbench.matrix import make_plan as original_plan


class LaterMatrixTests(unittest.TestCase):
    def files(self, root):
        root = Path(root)
        plan = root / 'plan.json'
        plan.write_text(json.dumps(make_plan('codex')))
        qualification = root / 'qualification.json'
        qualification.write_text(json.dumps({'passed': True, 'provider': 'codex'}))
        return plan, root / 'output', qualification

    def test_exact_paired_design_preserves_original_conditions(self):
        plan = make_plan('codex')
        cells = validate_plan(plan)
        self.assertEqual(len(cells), 28)
        original = [c for c in original_plan()['cells'] if c['provider'] == 'kimi']
        for left, right in zip(cells, original):
            for field in ('task', 'language', 'tests', 'replicate', 'semantic_seed',
                          'base_seconds', 'continuation_seconds', 'max_nudges', 'block_id'):
                self.assertEqual(left[field], right[field])
            self.assertEqual((left['model'], left['effort']), ('gpt-6-sol', 'medium'))
        for field, value in [('model', 'gpt-6-astra'), ('base_seconds', 901), ('replicate', 3)]:
            changed = copy.deepcopy(plan)
            changed['cells'][0][field] = value
            with self.assertRaises(ValueError):
                validate_plan(changed)
        changed = copy.deepcopy(plan)
        changed['retention'] = 'legacy'
        with self.assertRaises(ValueError):
            validate_plan(changed)
        with self.assertRaises(ValueError):
            validate_plan(original_plan())
        opus = validate_plan(make_plan('claude'))
        self.assertEqual(len(opus), 28)
        self.assertTrue(all((c['model'], c['effort']) == ('claude-opus-5-5', 'medium') for c in opus))
        self.assertEqual([(c['language'], c['tests'], c['replicate']) for c in cells],
                         [(c['language'], c['tests'], c['replicate']) for c in opus])

    def test_consumed_incident_never_retried(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, qualification = self.files(root)
            state = run_matrix(plan, output, qualification=qualification, binding={'fixture': 1},
                               runner=lambda *a, **kw: {'validity': 'infrastructure_invalid'})
            self.assertEqual(state['state'], 'stopped_on_incident')
            calls = []
            state = run_matrix(plan, output, qualification=qualification, binding={'fixture': 1},
                               resume=True, runner=lambda *a, **kw: calls.append(kw) or
                               {'validity': 'valid_development'})
            self.assertEqual(len(calls), 27)
            self.assertEqual(state['kind'], 'later_subscription_matrix')
            self.assertEqual(state['state'], 'closed_with_missing_cells')
            self.assertEqual(state['cells'][0]['state'], 'infrastructure_invalid')
            run_matrix(plan, output, qualification=qualification, binding={'fixture': 1},
                       resume=True, runner=lambda *a, **kw: self.fail('repeated inference'))

    def test_quota_preserves_started_attempt_and_closes_remaining(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, qualification = self.files(root)
            calls = []
            def runner(*a, **kw):
                calls.append(kw)
                return {'validity': 'quota', 'collection': {'invocations': [{'status': 'quota'}]}}
            state = run_matrix(plan, output, qualification=qualification, binding={}, runner=runner)
            self.assertEqual(len(calls), 1)
            self.assertEqual(state['cells'][0]['state'], 'quota')
            self.assertEqual(sum(c['state'] == 'not_run_quota' for c in state['cells']), 27)
            self.assertEqual(state['state'], 'closed_with_missing_cells')

    def test_changed_binding_or_receipt_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as root:
            plan, output, qualification = self.files(root)
            run_matrix(plan, output, qualification=qualification, binding={'version': 1},
                       runner=lambda *a, **kw: {'validity': 'infrastructure_invalid'})
            with self.assertRaises(ValueError):
                run_matrix(plan, output, qualification=qualification, binding={'version': 2},
                           resume=True, runner=lambda *a, **kw: self.fail('inference'))
            qualification.write_text('{"passed":true,"changed":true}')
            with self.assertRaises(ValueError):
                run_matrix(plan, output, qualification=qualification, binding={'version': 1},
                           resume=True, runner=lambda *a, **kw: self.fail('inference'))


if __name__ == '__main__':
    unittest.main()
