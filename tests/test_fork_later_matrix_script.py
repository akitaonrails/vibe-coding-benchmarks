"""Offline preservation and no-retry successor fixtures."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from scripts import fork_later_matrix as f
from scripts.analyze_later_matrix import analyze
from langbench.later_matrix import make_plan, run_matrix


class ForkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.old=self.root/'old';self.old.mkdir();self.new=self.root/'new'
        self.before={'asset':'unchanged','harness':{name:'a'*64 for name in f.ADAPTER_SOURCES}}
        self.after=copy.deepcopy(self.before);self.after['harness']['claude_subscriptions.py']='b'*64
        self.plan=make_plan('claude');self.write(self.old/'plan.json',self.plan)
        self.oldq=self.makeq(self.before);self.newq=self.makeq(self.after)
        self.write(self.old/'qualification-claude.json',self.oldq)
        self.qpath=self.root/'new-qualification.json';self.write(self.qpath,self.newq)
        states=[]
        for i,cell in enumerate(self.plan['cells']):
            state={'id':cell['id'],'state':'pending'}
            if i<4:
                path=self.old/cell['id'];path.mkdir();self.write(path/'result.json',{'validity':'infrastructure_invalid' if i==3 else 'valid_development'})
                state.update(state='infrastructure_invalid' if i==3 else 'collected',result_sha256=f.digest(path/'result.json'))
            states.append(state)
        self.state={'kind':'later_subscription_matrix','schema_version':2,'state':'stopped_on_incident',
                    'plan_sha256':f.digest(self.old/'plan.json'),'qualification_sha256':{'claude':f.digest(self.old/'qualification-claude.json')},
                    'input_binding':self.before,'blocked_providers':[],'cells':states}
        self.write(self.old/'matrix.json',self.state)
    def write(self,path,value):path.write_text(json.dumps(value,indent=2)+'\n')
    def makeq(self,binding):
        b={'adapter':{'provider':'claude','model':'claude-opus-5-5','effort':'medium'},
           'adapter_source_sha256':f.sha({n:binding['harness'][n] for n in f.ADAPTER_SOURCES})}
        return {'passed':True,'provider':'claude','model':'claude-opus-5-5','effort':'medium','binding':b,'binding_sha256':f.sha(b)}
    def fork(self):return f.fork(self.old,self.new,self.qpath,reason='diagnosed serialization race',current_binding=self.after)

    def test_preserve_then_resume_only_pending(self):
        inventory=f.inventory(self.old);epoch=self.fork()
        self.assertEqual(f.inventory(self.old),inventory);self.assertEqual(len(epoch['consumed_ids']),4)
        called=[]
        def runner(task,language,dest,**kwargs):
            called.append(Path(dest).name);return {'validity':'valid_development'}
        state=run_matrix(self.new/'plan.json',self.new,qualification=self.qpath,resume=True,runner=runner,binding=self.after)
        self.assertEqual(called,epoch['pending_ids']);self.assertEqual(state['cells'][:4],self.state['cells'][:4])
        self.assertEqual(f.inventory(self.old),inventory)
        report=analyze(self.new)
        self.assertEqual([r['instrumentation_epoch'] for r in report['attempts'][:4]],['predecessor']*4)
        self.assertEqual(len(report['instrumentation_lineage']['pending_ids']),24)

    def test_exact_transport_policy_transition(self):
        self.newq['binding']['adapter']['transport_policy']='serial-admission-v2'
        self.newq['binding_sha256']=f.sha(self.newq['binding']);self.write(self.qpath,self.newq)
        epoch=self.fork();self.assertEqual(len(epoch['consumed_ids']),4)

    def test_arbitrary_transport_policy_rejected(self):
        self.newq['binding']['adapter']['transport_policy']='anything-else'
        self.newq['binding_sha256']=f.sha(self.newq['binding']);self.write(self.qpath,self.newq)
        with self.assertRaisesRegex(ValueError,'beyond allowed'):self.fork()

    def test_result_tamper_rejected_without_destination(self):
        (self.old/self.plan['cells'][1]['id']/'result.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'result commitment'):self.fork()
        self.assertFalse(self.new.exists())

    def test_pending_directory_and_running_rejected(self):
        (self.old/self.plan['cells'][4]['id']).mkdir()
        with self.assertRaisesRegex(ValueError,'pending attempt'):self.fork()
        (self.old/self.plan['cells'][4]['id']).rmdir()
        self.state['cells'][4]['state']='running';self.write(self.old/'matrix.json',self.state)
        with self.assertRaisesRegex(ValueError,'no running'):self.fork()

    def test_other_binding_changes_rejected(self):
        self.after['asset']='changed'
        with self.assertRaisesRegex(ValueError,'only a changed'):self.fork()

    def test_qualification_not_passed_or_wrong_exact_model(self):
        self.newq['passed']=False;self.write(self.qpath,self.newq)
        with self.assertRaisesRegex(ValueError,'exact passed'):self.fork()
        self.newq['passed']=True;self.newq['model']='other';self.write(self.qpath,self.newq)
        with self.assertRaisesRegex(ValueError,'exact passed'):self.fork()

    def test_duplicate_identity_and_postfork_consumed_change(self):
        original=self.state['cells'][1]['id'];self.state['cells'][1]['id']=self.state['cells'][0]['id'];self.write(self.old/'matrix.json',self.state)
        with self.assertRaisesRegex(ValueError,'identity'):self.fork()
        self.state['cells'][1]['id']=original;self.write(self.old/'matrix.json',self.state);self.fork()
        state=json.loads((self.new/'matrix.json').read_text());state['cells'][0]['state']='pending';self.write(self.new/'matrix.json',state)
        with self.assertRaisesRegex(ValueError,'changed or retried'):f.validate_lineage(self.new)

    def test_only_claude_design(self):
        self.plan=make_plan('codex');self.write(self.old/'plan.json',self.plan)
        with self.assertRaisesRegex(ValueError,'Claude follow-up'):self.fork()


if __name__=='__main__':unittest.main()
