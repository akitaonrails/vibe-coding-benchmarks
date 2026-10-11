import json
from pathlib import Path
import tempfile
import unittest
from scripts.export_public_results import export, summary


class PublicResultsTests(unittest.TestCase):
    def test_export_drops_raw_and_nested_private_fields_preserving_unknowns(self):
        secret = 'PRIVATE_SENTINEL'
        row = {'cell': {'id': 'sample', 'provider': 'claude', 'prompt': secret},
               'operator_work': secret, 'result_sha256': 'a' * 64,
               'normal_completed_and_correct': False, 'correct_at_deadline': False,
               'tool_calls': 2, 'source_changing_calls': 1, 'nudge_count': 0,
               'final': {'correct': None, 'source_size': {'bytes': 123, 'path': secret}},
               'usage': {'provider_total': None, 'provider_known_subtotal': 42,
                         'native_coverage_complete': False, 'native_proof': secret,
                         'components': {'cache_read': {'total': None, 'known_subtotal': 12, 'raw': secret}}}}
        report = {'status': 'closed_cohort', 'plan_sha256': 'b' * 64,
                  'analysis_version': 'test', 'attempts': [row], 'local_path': secret}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report.json'
            path.write_text(json.dumps(report))
            data = export([path])
            self.assertNotIn(secret, json.dumps(data))
            self.assertIsNone(data['attempts'][0]['final']['correct'])
            self.assertEqual(data['attempts'][0]['usage']['provider_known_subtotal'], 42)
            self.assertIn('| claude | 1 | 0 | 0 | 0 | 1 | 0/1 | unknown |', summary(data))
            with self.assertRaises(ValueError):
                export([path, path])
            report['status'] = 'INTERIM'
            path.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                export([path])

    def test_published_campaign_counts_and_no_private_paths(self):
        data = json.loads((Path(__file__).resolve().parents[1] / 'docs/data/matrix-results.json').read_text())
        rows = data['attempts']
        self.assertEqual(len(rows), 112)
        self.assertEqual(len({r['cell']['id'] for r in rows}), 112)
        self.assertEqual(sum(r['normal_completed_and_correct'] for r in rows), 77)
        self.assertEqual(sum(r['correct_at_deadline'] for r in rows), 16)
        self.assertEqual(sum(r['final']['correct'] is False for r in rows), 12)
        self.assertEqual(sum(r['final']['correct'] is None for r in rows), 7)
        self.assertEqual(sum(r['nudge_count'] for r in rows), 0)
        for marker in ('/home/', '/mnt/', 'access_token', 'refresh_token', 'raw_path'):
            self.assertNotIn(marker, json.dumps(data))
