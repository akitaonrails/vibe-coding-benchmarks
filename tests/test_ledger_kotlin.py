"""Isolated native kotlin ledger: typed domain parity and compiled mutants."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from langbench.core import ROOT, copy_workspace
from langbench.worker import DockerWorker
from langbench.public_driver import same_json

SPEC=importlib.util.spec_from_file_location('kotlin_cases',ROOT/'tasks/ledger_engine/cases.py')
CASES=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CASES)
# This transport gets request histories only; expected results remain controller-side.
DRIVER="""import json,subprocess,sys
for requests in json.load(sys.stdin):
 p=subprocess.run(['sh','run.sh'],input=''.join(json.dumps(q)+'\\n' for q in requests),text=True,capture_output=True,timeout=10)
 print(json.dumps({'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}),flush=True)
"""

class LedgerKotlinTests(unittest.TestCase):
    def build(self,worker):
        result=worker.execute(['sh','build.sh'],timeout=120)
        self.assertEqual(result['returncode'],0,result['stdout']+result['stderr'])
        self.assertIsNone(result['termination'])

    def run_cases(self,worker,cases):
        run=worker.execute(['/usr/bin/python3','-I','-c',DRIVER],stdin=json.dumps([case['requests'] for case in cases]),timeout=120)
        self.assertEqual(run['returncode'],0,run['stderr']);self.assertIsNone(run['termination'])
        records=[json.loads(line) for line in run['stdout'].splitlines()]
        self.assertEqual(len(records),len(cases))
        failures=[]
        for case,record in zip(cases,records):
            self.assertEqual(record['returncode'],0,record['stderr'])
            actual=[json.loads(line) for line in record['stdout'].splitlines()]
            if not same_json(actual,case['expected']):failures.append(case['id'])
        return failures

    def test_reference_public_private_seeds(self):
        with DockerWorker(ROOT/'tasks/ledger_engine/references/kotlin',runtime='seven') as worker:
            self.build(worker)
            self.assertEqual(self.run_cases(worker,CASES.cases('public')),[])
            for seed in (0,29,271):
                with self.subTest(seed=seed):self.assertEqual(self.run_cases(worker,CASES.cases('private',seed)),[])

    def test_starter_baseline_and_guards(self):
        guards={'id':'guards','requests':[{'op':'begin','tx':'t'},{'op':'commit','tx':'t','request':'q','fault':{'keep':0,'tear':False}}, {'op':'checkpoint','fault':{'keep':2,'tear':False}},{'op':'stats'},{'op':'read','v':2,'tenant':'a','actor':'a','tx':'t','id':'x'}],
            'expected':[{'snapshot':0},{'error':'unsupported_fault'},{'error':'unsupported_fault'},{'revision':0,'journal_frames':0,'capacity':64,'transactions':1},{'error':'unsupported_version'}]}
        with DockerWorker(ROOT/'tasks/ledger_engine/starters/kotlin',runtime='seven') as worker:
            self.build(worker);self.assertEqual(self.run_cases(worker,CASES.baseline_cases()+[guards]),[])

    def test_compiled_native_mutants(self):
        cases={c['id']:c for c in CASES.cases('public')}
        for filename,old,new,case_id in [('Engine.kt', 'if(!tx.valid(table))', 'if(false && !tx.valid(table))', 'read_conflict_after_checkpoint'), ('Engine.kt', 'if(!proposed.unique())', 'if(false && !proposed.unique())', 'unique_swap_rollback_and_retry'), ('Engine.kt', 'receipts[identity]?.let { return obj("committed" to it) }', 'receipts[identity]?.let { if(false) return obj("committed" to it) }', 'dedup_lost_ack_checkpoint'), ('Device.kt', 'fault.number("keep")!=2', 'fault.number("keep")!=1', 'checkpoint_migration_cut_1_False'), ('Device.kt', 'kept[kept.lastIndex]=TornFrame', 'kept[kept.lastIndex]=kept.last()', 'journal_cut_4_True'), ('Table.kt', 'entries[Key(tenant,id)]?.version ?: 0', 'entries[Key(tenant,id)]?.takeIf { it.row!=null }?.version ?: 0', 'blind_write_aba_tombstone')]:
            with self.subTest(mutation=old),tempfile.TemporaryDirectory() as temporary:
                source=Path(temporary)/'source';copy_workspace(ROOT/'tasks/ledger_engine/references/kotlin',source)
                path=source/'src'/filename;body=path.read_text();self.assertEqual(body.count(old),1)
                path.write_text(body.replace(old,new))
                with DockerWorker(source,runtime='seven') as worker:
                    self.build(worker);self.assertEqual(self.run_cases(worker,[cases[case_id]]),[case_id])
