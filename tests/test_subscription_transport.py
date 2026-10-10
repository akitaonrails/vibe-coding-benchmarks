import io
import json
import unittest
import urllib.request
from langbench.provider_transport import Transport,inspect_request,ENDPOINTS

class TransportTests(unittest.TestCase):
    def test_blocks_model_effort_and_tools(self):
        good={'model':'k3','thinking':{'type':'enabled','effort':'high'},'tools':[{'type':'function','function':{'name':'only'}}]}
        self.assertEqual(inspect_request('kimi',good,'high','only')['tool_names'],['only'])
        for patch in ({'model':'other'},{'thinking':{'type':'enabled','effort':'max'}},{'tools':[{'type':'function','function':{'name':'Bash'}}]}):
            with self.assertRaises(ValueError):inspect_request('kimi',{**good,**patch},'high','only')

    def test_fixed_destination_and_redacted_usage(self):
        calls=[]
        class Response(io.BytesIO):
            status=200;headers={'Content-Type':'text/event-stream'}
        class Opener:
            def open(self,request,timeout):
                calls.append(request)
                return Response(b'data: {"id":"r1","choices":[{"delta":{"content":"private text"}}]}\n\ndata: {"id":"r1","usage":{"prompt_tokens":10,"completion_tokens":2}}\n\ndata: [DONE]\n\n')
        transport=Transport('kimi','high','only',opener=Opener())
        try:
            request=urllib.request.Request(transport.base_url+'/chat/completions',data=json.dumps({'model':'k3','thinking':{'type':'enabled','effort':'high'},'tools':[]}).encode(),headers={'Authorization':'secret'})
            with urllib.request.urlopen(request) as response:response.read()
            self.assertEqual(calls[0].full_url,ENDPOINTS['kimi'])
            self.assertNotIn('secret',json.dumps(transport.records))
            self.assertNotIn('private text',json.dumps(transport.records))
            self.assertEqual(transport.records[0]['usage'][0]['prompt_tokens'],10)
            bad=urllib.request.Request(transport.base_url+'/arbitrary',data=b'{}')
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(bad)
            self.assertEqual(len(calls),1)
        finally:transport.close()

    def test_quota_latch_blocks_sdk_retry_upstream(self):
        calls=[]
        class Response(io.BytesIO):
            status=429;headers={'Content-Type':'application/json'}
        class Opener:
            def open(self,request,timeout):calls.append(request);return Response(b'{"error":{"code":"rate_limit"}}')
        transport=Transport('opencode','high','only',opener=Opener())
        try:
            for _ in range(2):
                request=urllib.request.Request(transport.base_url+'/chat/completions',data=json.dumps({'model':'glm-5.3','reasoning_effort':'high','tools':[]}).encode())
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(request)
            self.assertEqual(len(calls),1)
            self.assertTrue(transport.records[-1]['quota_retry_blocked'])
        finally:transport.close()
