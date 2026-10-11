"""Synthetic post-hoc receipts only; no candidate/provider execution."""
import json
from pathlib import Path
import tempfile
import unittest
from scripts import analyze_later_matrix as a
from scripts import analyze_subscription_matrix as base
from langbench.later_matrix import make_plan
from langbench.claude_subscriptions import MODEL, TOOL
from tests.test_metrics_live import trace


def claude_request(identity='one', **changes):
    return {'index':0,'response_ids':[identity], 'model':MODEL,'effort':'medium','tool_names':[TOOL],
            'auth_mode':'oauth_bearer','http_status':200,'message_stopped':True,'response_complete':True,
            'usage':{'input_tokens':10,'cache_read_input_tokens':20,'cache_creation_input_tokens':30,'output_tokens':40},**changes}


class LaterAnalysisTests(unittest.TestCase):
    def test_operational_retry_interval_and_http_are_distinct(self):
        unsent={'upstream_sent':False,'response_ids':[],'usage':{},'http_status':429,'started_at':100}
        invocation={'index':0,'allowance_preflight_seconds':0.52,'auth_preflight_seconds':0.2,
                    'cleanup_seconds':0.1,'request_records':[unsent,{**unsent,'started_at':110},
                                                              {'upstream_sent':True,'started_at':130}]}
        result=a.operational_effort('claude',[invocation])
        row=result['invocations'][0]
        self.assertEqual(row['proven_unsent_request_count'],2)
        self.assertEqual(row['operational_request_count'],3)
        self.assertEqual(row['initial_preflight_retry_interval_seconds'],30)
        self.assertEqual(row['reported_allowance_http_seconds'],0.52)
        self.assertTrue(result['aggregate']['cleanup_seconds']['complete'])
        invocation['request_records'][1]['response_ids']=['ambiguous']
        result=a.operational_effort('claude',[invocation])
        self.assertIsNone(result['invocations'][0]['initial_preflight_retry_interval_seconds'])

    def test_operational_empty_missing_and_partial_coverage(self):
        for requests in ([],[{'upstream_sent':False}], [{'upstream_sent':True}]):
            result=a.operational_effort('claude',[{'request_records':requests}])
            self.assertIsNone(result['invocations'][0]['initial_preflight_retry_interval_seconds'])
            self.assertIsNone(result['aggregate']['reported_allowance_http_seconds']['total'])
        result=a.operational_effort('claude',[{'allowance_preflight_seconds':0.4,'request_records':[]},{}])
        aggregate=result['aggregate']['reported_allowance_http_seconds']
        self.assertIsNone(aggregate['total']);self.assertEqual(aggregate['known_subtotal'],0.4)
        self.assertEqual(aggregate['known_invocations'],1)
        self.assertIsNone(a.operational_effort('codex',[{}])['aggregate']['operational_request_count']['total'])

    def test_codex_cumulative_continuation_and_subsets(self):
        runs=trace()
        self.assertEqual(a.native_usage('codex',runs[:1])['provider_total'],30)
        result=a.native_usage('codex',runs)
        self.assertEqual(result['provider_total'],60)
        self.assertEqual(result['components']['cache_read']['total'],12)
        self.assertEqual(result['observed_request_count'],4)
        self.assertIn('not wire',result['request_count_scope'])

    def test_codex_partial_and_duplicate(self):
        runs=trace();runs[0]['events'].insert(1,runs[0]['events'][0])
        self.assertEqual(a.native_usage('codex',runs)['provider_total'],60)
        runs[-1]['status']='timeout';result=a.native_usage('codex',runs)
        self.assertIsNone(result['provider_total']);self.assertEqual(result['provider_known_subtotal'],60)
        self.assertIsNone(a.native_usage('codex',[])['provider_known_subtotal'])

    def test_codex_missing_component_is_not_zero(self):
        runs=trace()
        for invocation in runs:
            for event in invocation['events']:
                if event['method']=='rawResponse/completed':
                    event['params']['usage'].pop('cacheWriteInputTokens',None)
        result=a.native_usage('codex',runs)
        self.assertIsNone(result['components']['cache_write']['known_subtotal'])
        self.assertIsNone(result['provider_total'])

    def test_claude_disjoint_duplicate_and_partial(self):
        req=claude_request();runs=[{'usage_coverage_verified':True,'request_records':[req,req]}]
        result=a.native_usage('claude',runs)
        self.assertEqual(result['provider_total'],100)
        self.assertEqual(result['native_proof']['deduplicated_records'],1)
        self.assertIsNone(result['components']['reasoning']['total'])
        runs.append({'usage_coverage_verified':False,'request_records':[claude_request('two',usage={'input_tokens':5})]})
        result=a.native_usage('claude',runs)
        self.assertIsNone(result['provider_total']);self.assertEqual(result['provider_known_subtotal'],100)
        self.assertEqual(result['known_token_lower_bound'],105)

    def test_claude_conflicts_missing_identity(self):
        req=claude_request();other=claude_request(usage={'input_tokens':12})
        result=a.native_usage('claude',[{'usage_coverage_verified':True,'request_records':[req,other]}])
        self.assertIsNone(result['provider_total']);self.assertTrue(result['native_proof']['identity_conflicts'])
        result=a.native_usage('claude',[{'usage_coverage_verified':True,'request_records':[claude_request(response_ids=[])]}])
        self.assertIsNone(result['provider_total']);self.assertIsNone(result['provider_known_subtotal'])

    def test_both_full_plans_preserve_28_quota_and_unknown_cells(self):
        for provider in ('codex','claude'):
            with self.subTest(provider=provider),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);plan=make_plan(provider)
                data=json.dumps(plan).encode();(root/'plan.json').write_bytes(data)
                progress={'plan_sha256':base.sha(data),'state':'closed_with_missing_cells',
                          'cells':[{'id':c['id'],'state':'not_run_quota'} for c in plan['cells']]}
                (root/'matrix.json').write_text(json.dumps(progress))
                report=a.analyze(root)
                self.assertEqual(len(report['attempts']),28);self.assertEqual(report['status'],'closed_cohort')
                self.assertEqual(sum(s['planned_attempts'] for s in report['summary']),28)
                self.assertTrue(all(row['final'] is None for row in report['attempts']))
                self.assertTrue(all(row['usage']['provider_total'] is None for row in report['attempts']))

    def test_preinference_quota_keeps_grade_without_semantic_failure(self):
        cell=make_plan('codex')['cells'][0]
        result={'validity':'infrastructure_invalid','collection':{'active_seconds':0,
            'invocations':[{'index':0,'status':'quota','seconds':0,'inference_started':False}],
            'checkpoints':[{'index':0,'artifact_available':True}], 'interventions':[]},
            'grades':[{'index':0,'validity':'valid','success':False,'groups':{'migration':False}}]}
        with tempfile.TemporaryDirectory() as temp:
            row=a.later_row(cell,{'state':'quota'},result,Path(temp),None,None)
        self.assertIs(row['final']['correct'],False)
        self.assertIs(row['coding_attempt_started'],False)
        self.assertEqual(row['outcome_category'],'quota_before_coding')
        self.assertIsNone(row['semantic_failure']);self.assertIsNone(row['coding_active_seconds'])
        self.assertFalse(row['normal_completed_and_correct'])

    def test_claude_unsent_preflight_summary_excluded(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);plan=make_plan('claude');cell=plan['cells'][0]
            data=json.dumps(plan).encode();(root/'plan.json').write_bytes(data)
            manifest={key:value for key,value in cell.items() if key!='id'}
            result={'manifest':manifest,'manifest_sha256':base.sha(json.dumps(manifest,sort_keys=True).encode()),
                    'collection':{'active_seconds':0.2,'invocations':[{'index':0,'status':'quota',
                        'request_records':[claude_request(upstream_sent=False,quota_preflight_stop=True)],
                        'usage_coverage_verified':False}], 'checkpoints':[], 'interventions':[]}}
            attempt=root/cell['id'];attempt.mkdir();raw=json.dumps(result).encode();(attempt/'result.json').write_bytes(raw)
            states=[{'id':c['id'],'state':'not_run_quota'} for c in plan['cells']]
            states[0].update(state='quota',result_sha256=base.sha(raw))
            (root/'matrix.json').write_text(json.dumps({'plan_sha256':base.sha(data),'state':'closed_with_missing_cells','cells':states}))
            report=a.analyze(root);row=report['attempts'][0]
            self.assertIs(row['coding_attempt_started'],False)
            self.assertEqual(row['outcome_category'],'quota_before_coding')
            summary=next(s for s in report['summary'] if s['language']==cell['language'] and s['tests']==cell['tests'])
            self.assertEqual(summary['active_seconds']['known_n'],0)
            self.assertEqual(summary['provider_tokens']['known_n'],0)

    def test_started_ungraded_is_not_semantic_success(self):
        cell=make_plan('claude')['cells'][0]
        result={'collection':{'invocations':[{'index':0,'status':'timeout',
                    'request_records':[claude_request(upstream_sent=True)]}],
                'checkpoints':[{'index':0,'artifact_available':False}], 'interventions':[]}}
        with tempfile.TemporaryDirectory() as temp:
            row=a.later_row(cell,{'state':'collected'},result,Path(temp),None,None)
            self.assertIs(row['coding_attempt_started'],True)
            self.assertIsNone(row['semantic_failure']);self.assertFalse(row['semantic_outcome_eligible'])
            result['collection']['invocations'][0]['request_records'][0].pop('upstream_sent')
            uncertain=a.later_row(cell,{'state':'collected'},result,Path(temp),None,None)
            self.assertIsNone(uncertain['coding_attempt_started'])

    def test_length_is_not_normal_or_nudge_and_checkpoint_prefixes(self):
        cell=make_plan('codex')['cells'][0]
        invocations=trace()[:2]
        invocations[1]['status']='model_output_limit'
        result={'collection':{'invocations':invocations,'checkpoints':[
            {'index':0,'artifact_available':False},{'index':1,'artifact_available':False}], 'interventions':[]}}
        with tempfile.TemporaryDirectory() as temp:
            row=a.later_row(cell,{'state':'collected'},result,Path(temp),None,None)
        self.assertTrue(row['output_limit']);self.assertFalse(row['normal_completed_and_correct'])
        self.assertEqual(row['nudge_count'],0)
        self.assertEqual(row['initial']['usage']['provider_total'],30)
        self.assertIsNone(row['final']['usage']['provider_total'])
        self.assertEqual(row['final']['usage']['provider_known_subtotal'],45)


if __name__=='__main__':unittest.main()
