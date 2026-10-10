import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from langbench.effort_report import attempt_row, tool_effort, report_matrix, recognized_check


def call(command, before='a', after='a', code=0):
    return dict(arguments={'command': command}, source_before=before, source_after=after,
                result={'returncode': code, 'termination': None}, call_id=command)


class EffortTests(unittest.TestCase):
    def test_counts_observed_repairs_not_tool_calls(self):
        result = tool_effort([{'index': 0, 'tool_records': [
            call('cat src/main.rb'), call('sh build.sh', code=1),
            call('edit src/main.rb', after='b'), call('sh build.sh', before='b', after='b'),
            call('cat TASK.md'), call('sh build.sh', before='b', after='b')]}])
        self.assertEqual(result['counts']['tool_calls'], 6)
        self.assertEqual(result['observed_repair_cycles'], 1)
        self.assertEqual(result['observed_revision_check_cycles'], 1)
        self.assertEqual(result['counts']['source_changing_calls'], 1)

    def test_missing_evidence_and_rejected_calls_do_not_become_repairs(self):
        result = tool_effort([{}, {'tool_records': [{'rejected': True},
            {'arguments': {'command': 'sh build.sh'}, 'result': {}}]}])
        self.assertIsNone(result['observed_repair_cycles'])
        self.assertEqual(result['counts']['invocations_missing_tool_records'], 1)
        self.assertEqual(result['counts']['calls_missing_source_evidence'], 1)

    def test_assisted_success_and_unknown_human_time_remain_distinct(self):
        result = {'collection': {'invocations': [], 'checkpoints': [{'index': 0}, {'index': 1}], 'interventions': [{'category': 'reactivation', 'delivery_status': 'invocation_returned'}]},
                  'grades': [{'index': 0, 'success': False}, {'index': 1, 'success': True}]}
        row = attempt_row({}, 'collected', result)
        self.assertFalse(row['initial_success'])
        self.assertTrue(row['final_success'])
        self.assertEqual(row['actual_nudges'], 1)
        self.assertIsNone(row['observed_human_repair_seconds'])
        self.assertIsNone(row['active_seconds'])
        self.assertIsNone(attempt_row({}, 'not_run_quota')['initial_success'])

    def test_provider_totals_keep_initial_and_continuation_effort_separate(self):
        native = {'provider': 'kimi', 'request_id': 'transport-0',
                  'provider_reported_total': 125, 'native_fields_verified': True,
                  'cli_normalized_total': None, 'request_coverage_verified': True}
        first = {'index': 0, 'usage_coverage_verified': True, 'usage_records': [native]}
        row = attempt_row({}, 'collected', {'collection': {
            'invocations': [first], 'usage_summary': {'provider_reported_total': 300,
                                                     'cli_normalized_total': None}}})
        self.assertEqual(row['initial_provider_reported_tokens'], 125)
        self.assertEqual(row['provider_reported_tokens'], 300)
        self.assertIsNone(row['cli_normalized_tokens'])
        first['usage_coverage_verified'] = False
        row = attempt_row({}, 'collected', {'collection': {'invocations': [first]}})
        self.assertIsNone(row['initial_provider_reported_tokens'])

    def test_interrupted_nudge_is_not_counted_as_known_delivery(self):
        row = attempt_row({}, 'interrupted_unknown', {
            'collection': {'interventions': [{'category': 'reactivation', 'delivery_status': 'planned'}]}})
        self.assertIsNone(row['actual_nudges'])
        self.assertTrue(row['nudge_delivery_uncertain'])
        self.assertEqual(row['planned_nudges'], 1)

    def test_information_commands_and_quoted_examples_are_not_checks(self):
        for command in ('tsc --version', 'tsc -v', 'tsc --init', 'tsc -b --clean', 'tsc -b --dry',
                        'cargo build --help', 'ghc --numeric-version',
                        'echo "sh build.sh"', 'cat TASK.md && sh build.sh'):
            self.assertFalse(recognized_check(command), command)

    def test_ungraded_final_checkpoint_cannot_inherit_earlier_success(self):
        row = attempt_row({}, 'infrastructure_invalid', {
            'collection': {'checkpoints': [{'index': 0}, {'index': 1}]},
            'grades': [{'index': 0, 'success': True}]})
        self.assertIsNone(row['final_success'])
        self.assertTrue(row['last_graded_success'])
        self.assertEqual(row['final_checkpoint_index'], 1)

    def test_report_rejects_truncated_progress_or_changed_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan = {'cells': [{'id': 'a'}, {'id': 'b'}]}
            path = root / 'plan.json'
            path.write_text(json.dumps(plan))
            progress = {'plan_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                        'cells': [{'id': 'a', 'state': 'pending'}]}
            (root / 'matrix.json').write_text(json.dumps(progress))
            with self.assertRaisesRegex(ValueError, 'every planned cell'):
                report_matrix(root)
            progress['cells'].append({'id': 'b', 'state': 'pending'})
            progress['cells'][0]['result_sha256'] = 'wrong'
            (root / 'matrix.json').write_text(json.dumps(progress))
            with self.assertRaisesRegex(ValueError, 'result hash mismatch'):
                report_matrix(root)
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'plan hash mismatch'):
                report_matrix(root)


if __name__ == '__main__':
    unittest.main()
