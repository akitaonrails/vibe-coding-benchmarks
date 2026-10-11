import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from langbench.worker import DockerWorker
from langbench.subscriptions import capture_invocation
from langbench.core import digest_tree

class RetentionTests(unittest.TestCase):
    def source(self,root):
        source=root/'workspace';(source/'src').mkdir(parents=True)
        (source/'src/main.txt').write_text('starter')
        (source/'TASK.md').write_text('trusted task')
        return source

    def test_real_timeout_seals_before_tmpfs_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(Path(directory))
            with DockerWorker(source,runtime='seven',retention='seal-v1') as worker:
                result=worker.execute("printf final > src/main.txt; (while :; do printf x >> src/background.txt; sleep .01; done) & sleep 20",timeout=.3)
                self.assertEqual(result['termination'],'timeout')
                self.assertFalse(worker.alive)
                self.assertEqual((worker.retained_source/'src/main.txt').read_text(),'final')
                before=digest_tree(worker.retained_source/'src')
                with self.assertRaises(RuntimeError):worker.execute('true')
                self.assertEqual(digest_tree(worker.retained_source/'src'),before)
                receipt=result['artifact_retention']
                self.assertLessEqual(receipt['cutoff_monotonic'],receipt['writers_stopped_monotonic'])
                self.assertLessEqual(receipt['writers_stopped_monotonic'],receipt['sealed_monotonic'])
                invocation={'status':'timeout','quiescent':True,'cleanup_unsettled':[]}
                capture_invocation(worker,source,invocation)
                self.assertTrue(invocation['artifact_available'])
                self.assertEqual((source/'src/main.txt').read_text(),'final')
                self.assertEqual((source/'TASK.md').read_text(),'trusted task')

    def test_real_transport_drain_does_not_discard_quiescent_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(Path(directory))
            with DockerWorker(source,runtime='seven',retention='seal-v1') as worker:
                worker.execute('printf implemented > src/main.txt')
                invocation={'status':'timeout','quiescent':False,'cleanup_unsettled':[{'component':'transport','error_type':'RuntimeError'}],'usage_coverage_verified':False}
                capture_invocation(worker,source,invocation)
                self.assertTrue(invocation['artifact_available'])
                self.assertFalse(invocation['quiescent'])
                self.assertFalse(invocation['usage_coverage_verified'])
                self.assertEqual((source/'src/main.txt').read_text(),'implemented')
                self.assertFalse(worker.alive)

    def test_real_invalid_source_never_becomes_sealed_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(Path(directory))
            with DockerWorker(source,runtime='seven',retention='seal-v1') as worker:
                result=worker.execute('ln -s /etc/passwd src/link; sleep 20',timeout=.3)
                self.assertEqual(result['termination'],'timeout')
                self.assertFalse(result['artifact_retention']['artifact_available'])
                self.assertIsNone(worker.retained_source)
                self.assertFalse(worker.alive)

    def test_real_hardlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(Path(directory))
            with DockerWorker(source,runtime='seven',retention='seal-v1') as worker:
                result=worker.execute('ln src/main.txt src/alias; sleep 20',timeout=.3)
                self.assertFalse(result['artifact_retention']['artifact_available'])
                self.assertIsNone(worker.retained_source)

    def test_bridge_unsettled_never_exports_stale_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source=self.source(Path(directory));worker=Mock()
            worker.retention='seal-v1';worker.alive=True;worker.retained_source=None;worker.retention_receipt=None
            invocation={'status':'timeout','quiescent':False,'cleanup_unsettled':[{'component':'bridge','error_type':'RuntimeError'}]}
            capture_invocation(worker,source,invocation)
            worker.seal_quiescent.assert_not_called();worker.close.assert_called_once()
            self.assertFalse(invocation['artifact_available'])

    def test_cleanup_failure_does_not_attempt_export(self):
        worker=DockerWorker.__new__(DockerWorker)
        worker.admission_closed=False;worker.retention='seal-v1';worker.alive=True;worker.supervisor_pid=2
        worker.raw=Mock(side_effect=[{'returncode':-9,'termination':'timeout'},{'returncode':1,'termination':None}])
        worker.close=Mock(side_effect=lambda:setattr(worker,'alive',False));worker._seal_source=Mock()
        result=worker.execute('test',timeout=.1)
        worker._seal_source.assert_not_called()
        self.assertEqual(result['termination'],'timeout')
        self.assertFalse(result['artifact_retention']['artifact_available'])

    def test_removal_failure_cannot_claim_worker_closed(self):
        from unittest.mock import patch
        worker=DockerWorker.__new__(DockerWorker)
        worker.retention='seal-v1';worker.alive=True;worker.name='fake'
        with patch('langbench.worker.execute',return_value={'returncode':1,'termination':None}):
            with self.assertRaises(RuntimeError):worker.close()
        self.assertTrue(worker.alive)
