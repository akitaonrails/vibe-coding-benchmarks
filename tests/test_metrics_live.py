import copy
import unittest
from langbench.metrics import reconcile_provider_usage, PROVIDER_FIELDS

def usage(inp=10,out=5,cache=3,reason=2):
    return dict(zip(PROVIDER_FIELDS,(inp+out,inp,cache,0,out,reason)))
def response(ident,turn,values=None):
    values=values or usage()
    return {'method':'rawResponse/completed','params':{'threadId':'thread','turnId':turn,'responseId':ident,'usage':values,
            'usageMetadata':{'metadata':{'output_tokens_details':{'reasoning_tokens':values.get('reasoningOutputTokens')}}}}}
def total(turn,multiplier):
    return {'method':'thread/tokenUsage/updated','params':{'threadId':'thread','turnId':turn,'tokenUsage':{
        'total':{key:value*multiplier for key,value in usage().items()},'last':usage()}}}
def trace():
    return [{'index':0,'turn_id':'a','status':'handoff','events':[response('r1','a'),response('r2','a'),total('a',2)]},
            {'index':1,'turn_id':'b','status':'handoff','events':[response('r3','b'),total('b',3)]},
            {'index':2,'turn_id':'c','status':'handoff','events':[response('r4','c'),total('c',4)]}]

class ProviderUsageTests(unittest.TestCase):
    def test_multiple_requests_per_turn_and_three_nudge_checkpoints(self):
        result=reconcile_provider_usage(trace())
        self.assertTrue(result['complete']);self.assertEqual(result['provider_reported_total_tokens'],60)
        self.assertEqual([turn['provider_reported_total_tokens'] for turn in result['per_turn']],[30,15,15])
        self.assertEqual(result['observed_components']['reasoningOutputTokens'],8)
        self.assertEqual(result['observed_components']['cachedInputTokens'],12)
    def test_duplicate_response_deduplicated(self):
        runs=trace();runs[0]['events'].insert(1,response('r1','a'))
        self.assertEqual(reconcile_provider_usage(runs)['provider_reported_total_tokens'],60)
    def test_conflicting_duplicate_rejected(self):
        runs=trace();runs[0]['events'].insert(1,response('r1','a',usage(inp=11)))
        result=reconcile_provider_usage(runs)
        self.assertIsNone(result['provider_reported_total_tokens'])
        self.assertIn('conflicting_duplicate_response',result['warnings'])
    def test_missing_field_not_zero(self):
        runs=trace();del runs[0]['events'][0]['params']['usage']['cachedInputTokens']
        result=reconcile_provider_usage(runs)
        self.assertIsNone(result['observed_components']['cachedInputTokens'])
        self.assertIsNone(result['provider_reported_total_tokens'])
    def test_bool_tokens_rejected(self):
        runs=trace();runs[0]['events'][0]['params']['usage']['totalTokens']=True
        self.assertFalse(reconcile_provider_usage(runs)['complete'])
    def test_late_response_and_update_keep_original_turn_identity(self):
        runs=trace();late=runs[0]['events'].pop();runs[2]['events'].append(late)
        result=reconcile_provider_usage(runs)
        self.assertEqual(result['provider_reported_total_tokens'],60)
        self.assertEqual(result['per_turn'][0]['provider_reported_total_tokens'],30)
    def test_timeout_keeps_partial_observations(self):
        runs=trace();runs[-1]['status']='timeout'
        result=reconcile_provider_usage(runs)
        self.assertIsNone(result['provider_reported_total_tokens'])
        self.assertEqual(result['known_subtotals']['totalTokens'],60)
        self.assertEqual(result['per_turn'][0]['provider_reported_total_tokens'],30)
    def test_cumulative_mismatch_rejected(self):
        runs=trace();runs[-1]['events'][-1]['params']['tokenUsage']['total']['totalTokens']=999
        self.assertFalse(reconcile_provider_usage(runs)['complete'])
    def test_metadata_reasoning_mismatch_rejected(self):
        runs=trace();runs[0]['events'][0]['params']['usageMetadata']['metadata']['output_tokens_details']['reasoning_tokens']=3
        self.assertFalse(reconcile_provider_usage(runs)['complete'])
    def test_reasoning_and_cache_cannot_exceed_parent(self):
        for field in ('reasoningOutputTokens','cachedInputTokens'):
            runs=trace();runs[0]['events'][0]['params']['usage'][field]=999
            self.assertFalse(reconcile_provider_usage(runs)['complete'])
    def test_missing_response_id_and_final_usage_rejected(self):
        runs=trace();del runs[0]['events'][0]['params']['responseId'];runs[-1]['events'].pop()
        result=reconcile_provider_usage(runs)
        self.assertFalse(result['complete']);self.assertIsNone(result['provider_reported_total_tokens'])

if __name__=='__main__':unittest.main()

class DuplicateMetadataTests(unittest.TestCase):
    def test_duplicate_with_conflicting_native_reasoning_is_rejected(self):
        runs=trace();duplicate=copy.deepcopy(runs[0]['events'][0])
        duplicate['params']['usageMetadata']['metadata']['output_tokens_details']['reasoning_tokens']=999
        runs[0]['events'].insert(1,duplicate)
        result=reconcile_provider_usage(runs)
        self.assertFalse(result['complete'])
        self.assertIn('conflicting_duplicate_response',result['warnings'])
