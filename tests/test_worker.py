import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from langbench.worker import DockerWorker

class WorkerFailureTests(unittest.TestCase):
    def test_missing_docker_fails_closed(self):
        with patch('langbench.worker.shutil.which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Docker unavailable'):
                DockerWorker('/does/not/matter')

@unittest.skipUnless(shutil.which('docker'),'Docker boundary tests require Docker')
class DockerBoundaryTests(unittest.TestCase):
    def workspace(self,path):
        source=Path(path)/'input';(source/'src/target').mkdir(parents=True)
        (source/'src/target/helper.rb').write_text('puts 1')
        return source
    def test_limits_hidden_paths_background_cleanup_and_export(self):
        with tempfile.TemporaryDirectory() as temp:
            source=self.workspace(temp)
            with DockerWorker(source) as worker:
                self.assertEqual(worker.qualification['pids.max'],'64')
                result=worker.execute("test ! -e /mnt/data/Projects/languages-benchmark && test ! -e /root/.codex && test ! -e /var/run/docker.sock && test ! -e /home/akitaonrails/.codex")
                self.assertEqual(result['returncode'],0)
                result=worker.execute("sh -c 'sleep 1; echo drift > /workspace/src/drift' >/dev/null 2>&1 &")
                self.assertEqual(result['returncode'],0)
                self.assertIsNone(result['termination'])
                worker.execute('sleep 1.1')
                target=Path(temp)/'exported';worker.export(target)
                self.assertEqual((target/'src/target/helper.rb').read_text(),'puts 1')
                self.assertFalse((target/'src/drift').exists())
    def test_source_symlink_export_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with DockerWorker(self.workspace(temp)) as worker:
                worker.execute('ln -s /etc/passwd src/escape')
                with self.assertRaises(ValueError):worker.export(Path(temp)/'exported')
    def test_timeout_retires_worker(self):
        with tempfile.TemporaryDirectory() as temp:
            with DockerWorker(self.workspace(temp)) as worker:
                result=worker.execute('sleep 10',timeout=.1)
                self.assertEqual(result['termination'],'timeout')
                self.assertFalse(worker.alive)
                with self.assertRaises(RuntimeError):worker.execute('true')

@unittest.skipUnless(shutil.which('docker'),'Docker boundary tests require Docker')
class PythonHelperIsolationTests(unittest.TestCase):
    def test_candidate_modules_cannot_shadow_trusted_helpers(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';(source/'src').mkdir(parents=True)
            (source/'src/solution.rb').write_text('puts "genuine"')
            for name in ('json','signal','pathlib'):
                (source/(name+'.py')).write_text("open('/workspace/SHADOW_EXECUTED','w').write('bad')\nraise RuntimeError('candidate helper shadow executed')\n")
            with DockerWorker(source) as worker:
                self.assertEqual(worker.qualification['pids.max'],'64')
                result=worker.execute('true')
                self.assertEqual(result['returncode'],0)
                self.assertIsNone(result['termination'])
                exported=Path(temp)/'exported';worker.export(exported)
                self.assertEqual((exported/'src/solution.rb').read_text(),'puts "genuine"')
                self.assertFalse((exported/'SHADOW_EXECUTED').exists())
                for name in ('json','signal','pathlib'):
                    self.assertEqual((exported/(name+'.py')).read_bytes(),(source/(name+'.py')).read_bytes())

@unittest.skipUnless(shutil.which('docker'),'Docker boundary tests require Docker')
class WorkerReapingTests(unittest.TestCase):
    def test_repeated_orphans_do_not_exhaust_pid_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';(source/'src').mkdir(parents=True)
            with DockerWorker(source) as worker:
                for _ in range(70):
                    result=worker.execute('sleep 10 >/dev/null 2>&1 &')
                    self.assertEqual(result['returncode'],0)
                    self.assertIsNone(result['termination'])
                result=worker.execute('true')
                self.assertEqual(result['returncode'],0)
                self.assertIsNone(result['termination'])
