import json
from pathlib import Path
import tempfile
import unittest
from langbench.core import ROOT, supported_languages, scaffold
from langbench.worker import DockerWorker

class SevenRuntimeTests(unittest.TestCase):
    def test_per_task_availability(self):
        self.assertEqual(set(supported_languages('ledger_engine')),{'rust','haskell','csharp','kotlin','typescript','python','ruby'})
        self.assertEqual(set(supported_languages('crash_store')),{'ruby','rust'})
        with self.assertRaises(ValueError):scaffold('crash_store','haskell')
    def test_immutable_runtime_resource_and_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';(source/'src').mkdir(parents=True)
            with DockerWorker(source,runtime='seven') as worker:
                q=worker.qualification
                self.assertEqual(q['runtime'],'seven');self.assertEqual(q['pids.max'],'64')
                self.assertFalse(q['controller_assets_visible']);self.assertTrue(q['network_blocked'])
                for tool in ('ghc','dotnet','kotlinc','node','tsc','python3','ruby','rustc'):
                    self.assertEqual(worker.execute(['sh','-c',f'command -v {tool}'])['returncode'],0,tool)
                result=worker.execute('test ! -e /home/akitaonrails && test ! -e /mnt/data/Projects && test ! -e /var/run/docker.sock')
                self.assertEqual(result['returncode'],0)
                exported=Path(temp)/'exported';worker.export(exported)
                self.assertTrue((exported/'src').is_dir())
    def test_unknown_runtime_rejected(self):
        with self.assertRaises(ValueError):DockerWorker('.',runtime='unqualified')
