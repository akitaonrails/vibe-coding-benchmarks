import tempfile
import unittest
from pathlib import Path
from langbench.assistance import collect, terminal_status, decision

class AssistanceTests(unittest.TestCase):
    def test_marker_is_exact_unique_final_line(self):
        self.assertEqual(terminal_status('done\nBENCHMARK_STATUS: COMPLETE'),'COMPLETE')
        for text in ('done','BENCHMARK_STATUS: COMPLETE\nmore','BENCHMARK_STATUS: COMPLETE\nBENCHMARK_STATUS: BLOCKED','`BENCHMARK_STATUS: COMPLETE`'):
            self.assertIsNone(terminal_status(text))
        self.assertFalse(decision({'status':'timeout','terminal_text':'BENCHMARK_STATUS: BLOCKED'},0)[0])

    def test_conditional_resume_and_immutable_first_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); workspace=root/'workspace'; (workspace/'src').mkdir(parents=True)
            (workspace/'src'/'main.rb').write_text('first')
            calls=[]
            def invoke(prompt,session,seconds):
                calls.append((session,seconds))
                if len(calls)==2:(workspace/'src'/'main.rb').write_text('second')
                return {'status':'handoff','session_id':'same','seconds':1,
                        'terminal_text':'BENCHMARK_STATUS: '+('INCOMPLETE' if len(calls)==1 else 'COMPLETE')}
            result=collect(workspace,root/'collection','task',invoke)
            self.assertEqual(calls,[(None,900),('same',180)])
            self.assertEqual(len(result['interventions']),1)
            self.assertEqual(result['stop_reason'],'declared_complete')
            self.assertEqual((root/'collection/snapshot-0/src/main.rb').read_text(),'first')

    def test_missing_marker_does_not_nudge(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'src').mkdir()
            result=collect(root,root.parent/(root.name+'-receipt'),'task',lambda *a:{'status':'handoff','session_id':'s','seconds':0,'terminal_text':'Done'})
            self.assertEqual(len(result['invocations']),1)
            self.assertEqual(result['stop_reason'],'handoff_status_unknown')
            import shutil
            shutil.rmtree(root.parent/(root.name+'-receipt'))

    def test_retired_worker_is_censored_without_stale_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);workspace=root/'workspace';(workspace/'src').mkdir(parents=True)
            (workspace/'src/stale.rb').write_text('old')
            result=collect(workspace,root/'collection','task',lambda *args:{'status':'timeout','session_id':'s','seconds':1,'terminal_text':'','artifact_available':False})
            checkpoint=result['checkpoints'][0]
            self.assertFalse(checkpoint['artifact_available'])
            self.assertIsNone(checkpoint['artifact_path'])
            self.assertFalse((root/'collection/snapshot-0').exists())
