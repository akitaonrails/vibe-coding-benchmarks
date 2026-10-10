"""Haskell ledger parity, working v1 baseline and compiled semantic mutants."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from langbench.core import ROOT, copy_workspace
from langbench.worker import DockerWorker
from langbench.grading import same_json

SPEC=importlib.util.spec_from_file_location('ledger_new_cases',ROOT/'tasks/ledger_engine/cases.py')
CASES=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(CASES)

class HaskellLedgerTests(unittest.TestCase):
    languages=('haskell',)
    def check_cases(self, worker, cases):
        failures=[]
        for case in cases:
            result=worker.execute(['sh','run.sh'],stdin=''.join(json.dumps(r)+'\n' for r in case['requests']),timeout=10)
            try: actual=[json.loads(line) for line in result['stdout'].splitlines()]
            except ValueError: actual=None
            if result['returncode'] or result['termination'] or not same_json(actual,case['expected']):failures.append((case['id'],result['stderr'],actual))
        return failures
    def build(self,worker):
        result=worker.execute(['sh','build.sh'],timeout=120)
        self.assertEqual(result['returncode'],0,result['stdout']+result['stderr']);self.assertIsNone(result['termination'])
    def test_references_native_parity(self):
        for language in self.languages:
            with self.subTest(language=language), DockerWorker(ROOT/'tasks/ledger_engine/references'/language,runtime='seven') as worker:
                self.build(worker)
                for seed in (29,271):self.assertEqual(self.check_cases(worker,CASES.cases('private',seed)),[])
                self.assertEqual(self.check_cases(worker,CASES.cases('public')),[])
    def test_starters_working_baseline(self):
        for language in self.languages:
            with self.subTest(language=language), DockerWorker(ROOT/'tasks/ledger_engine/starters'/language,runtime='seven') as worker:
                self.build(worker);self.assertEqual(self.check_cases(worker,CASES.baseline_cases()),[])
                requests=[{'op':'begin','tx':'t'},{'op':'commit','tx':'t','request':'q','fault':{'keep':0,'tear':False}},{'op':'read','v':2,'tenant':'a','actor':'a','tx':'t','id':'x'}]
                result=worker.execute(['sh','run.sh'],stdin=''.join(json.dumps(x)+'\n' for x in requests))
                self.assertEqual([json.loads(x) for x in result['stdout'].splitlines()],[{'snapshot':0},{'error':'unsupported_fault'},{'error':'unsupported_version'}])
    def test_native_semantic_mutants(self):
        mutations={
            'haskell': [('src/Engine.hs','not (valid (table e) tx)','False && not (valid (table e) tx)'),('src/Engine.hs','not (unique proposed)','False && not (unique proposed)'),('src/Engine.hs','Just previous <- M.lookup identity (receipts e)','Just previous <- M.lookup identity (receipts e), False'),('src/Device.hs','number "keep" f/=2','number "keep" f/=1'),('src/Device.hs','init prefix++[TornFrame]','prefix'),('src/Table.hs','maybe 0 entryVersion','maybe 0 (\\e -> if entryRow e==Nothing then 0 else entryVersion e)')],
        }
        for language in self.languages:
            for index,(filename,old,new) in enumerate(mutations[language]):
                with self.subTest(language=language,mutant=index),tempfile.TemporaryDirectory() as temp:
                    source=Path(temp)/'workspace';copy_workspace(ROOT/'tasks/ledger_engine/references'/language,source)
                    path=source/filename;text=path.read_text();self.assertIn(old,text);path.write_text(text.replace(old,new,1))
                    with DockerWorker(source,runtime='seven') as worker:
                        self.build(worker)
                        self.assertTrue(self.check_cases(worker,CASES.cases('private',29)),f'undetected native mutant {language}/{index}')
