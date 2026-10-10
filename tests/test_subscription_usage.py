import unittest
from langbench.provider_usage import record,summarize

class UsageTests(unittest.TestCase):
    def test_no_missing_zero_and_disjoint_reasoning(self):
        self.assertIsNone(record('kimi','1',{'output':3})['cli_normalized_total'])
        item=record('opencode','1',{'input':10,'output':4,'reasoning':2,'cache':{'read':5,'write':0}})
        self.assertEqual(item['cli_normalized_total'],21)
        self.assertEqual(summarize([item,item])['request_count'],1)
        conflict={**item,'raw':{'changed':True}}
        self.assertIsNone(summarize([item,conflict])['cli_normalized_total'])

    def test_missing_request_prevents_complete_total(self):
        item=record('kimi','one',{'inputOther':10,'inputCacheRead':0,'inputCacheCreation':0,'output':2})
        summary=summarize([item])
        self.assertIsNone(summary['cli_normalized_total'])
        self.assertEqual(summary['observed_records_subtotal'],12)
        item['request_coverage_verified']=True
        self.assertEqual(summarize([item])['cli_normalized_total'],12)

    def test_native_totals_cover_requests_including_missing_usage(self):
        from langbench.provider_usage import native_record
        request={'index':0,'http_status':200,'response_complete':True,'usage':[{'prompt_tokens':10,'completion_tokens':5,'total_tokens':15,'completion_tokens_details':{'reasoning_tokens':3}}]}
        item=native_record('opencode',request)
        self.assertEqual(summarize([item])['provider_reported_total'],15)
        missing=native_record('opencode',{**request,'index':1,'usage':[]})
        self.assertIsNone(summarize([item,missing])['provider_reported_total'])

    def test_entire_missing_turn_prevents_collection_total(self):
        from langbench.provider_usage import native_record,summarize_invocations
        item=native_record('kimi',{'index':0,'http_status':200,'response_complete':True,'usage':[{'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}]})
        result=summarize_invocations([{'usage_records':[item],'usage_coverage_verified':True},{'usage_records':[],'usage_coverage_verified':False}])
        self.assertIsNone(result['provider_reported_total'])
        self.assertEqual(result['provider_reported_partial_subtotal'],5)
