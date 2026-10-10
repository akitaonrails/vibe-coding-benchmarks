"""Native Ruby ledger contract parity and functioning-starter checks."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from langbench.public_driver import same_json

ROOT=Path(__file__).resolve().parents[1]
TASK=ROOT/'tasks/ledger_engine'
spec=importlib.util.spec_from_file_location('ledger_ruby_cases',TASK/'cases.py')
fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)

@unittest.skipUnless(shutil.which('ruby'),'Ruby runtime unavailable')
class LedgerRubyTests(unittest.TestCase):
    def execute_case(self,kind,case):
        process=subprocess.run(['ruby','src/main.rb'],cwd=TASK/kind/'ruby',text=True,
            input=''.join(json.dumps(q)+'\n' for q in case['requests']),capture_output=True,timeout=10)
        self.assertEqual(process.returncode,0,process.stderr)
        outputs=[json.loads(line) for line in process.stdout.splitlines()]
        self.assertTrue(same_json(outputs,case['expected']),case['id'])
    def test_working_v1_starter(self):
        for case in fixtures.baseline_cases():
            with self.subTest(case=case['id']):self.execute_case('starters',case)
    def test_reference_public_contract(self):
        for case in fixtures.cases('public'):
            with self.subTest(case=case['id']):self.execute_case('references',case)
    def test_reference_private_interactions_and_seeded_cuts(self):
        for seed in (0,7):
            for case in fixtures.cases('private',seed):
                with self.subTest(seed=seed,case=case['id']):self.execute_case('references',case)
    def test_starter_rejects_v2_and_fault_without_mutation(self):
        requests=[{'op':'begin','tx':'t'},{'op':'put','tx':'t','id':'a','value':1},
                  {'op':'commit','tx':'t','request':'r','fault':{'keep':0,'tear':False}},
                  {'op':'stats'},{'op':'begin','v':2,'tenant':'a','actor':'a','tx':'x'}]
        expected=[{'snapshot':0},{'ok':True},{'error':'unsupported_fault'},
                  {'revision':0,'journal_frames':0,'capacity':64,'transactions':1},{'error':'unsupported_version'}]
        self.execute_case('starters',{'id':'baseline-scope','requests':requests,'expected':expected})
