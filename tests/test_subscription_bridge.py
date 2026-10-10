import tempfile
import time
import unittest
from langbench.mcp_bridge import Bridge,validate_arguments

class BridgeTests(unittest.TestCase):
    def test_rejected_arguments_then_valid_call(self):
        calls=[]
        with tempfile.TemporaryDirectory() as directory:
            bridge=Bridge(directory,lambda command,seconds:calls.append(command) or {'returncode':0},lambda:'hash')
            try:
                bridge.deadline=time.monotonic()+5
                bad=bridge.dispatch({'name':'sandbox_shell','arguments':{'command':'true','timeout_seconds':200}})
                self.assertTrue(bad['isError']);self.assertEqual(calls,[])
                good=bridge.dispatch({'name':'sandbox_shell','arguments':{'command':'true'}})
                self.assertFalse(good['isError']);self.assertEqual(calls,['true'])
                self.assertEqual(len(bridge.records),2)
                with self.assertRaises(ValueError):bridge.dispatch({'name':'host_shell','arguments':{}})
                bridge.deadline=0
                with self.assertRaises(TimeoutError):bridge.dispatch({'name':'sandbox_shell','arguments':{}})
            finally:bridge.close()

    def test_schema_boundaries(self):
        for args in ({'command':'x','timeout_seconds':True},{'command':'\ud800'},{'command':'x','root':'/'},{'command':'x'*131073}):
            self.assertIsNotNone(validate_arguments(args))

    def test_settle_waits_for_inflight_command_and_late_record(self):
        import threading
        entered=threading.Event();release=threading.Event()
        def execute(*args):entered.set();release.wait(2);return {'returncode':0}
        with tempfile.TemporaryDirectory() as directory:
            bridge=Bridge(directory,execute,lambda:'hash');bridge.deadline=time.monotonic()+5
            thread=threading.Thread(target=lambda:bridge.dispatch({'name':'sandbox_shell','arguments':{'command':'true'}}));thread.start()
            try:
                self.assertTrue(entered.wait(1))
                with self.assertRaises(RuntimeError):bridge.settle(.01)
                release.set();bridge.settle(1)
                self.assertEqual(len(bridge.records),1)
            finally:release.set();thread.join();bridge.close()
