"""Pure scorer tests; real-process evidence is separate and never simulated here."""
import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
from scalability.runner import evaluate,events,expected,load_metrics


class QueueScorerTests(unittest.TestCase):
    def fixture(self):
        source=events(20,poison=True)
        accepted=[[e['tenant'],e['id']] for e in source]
        sink=dict(effects=[expected(e) for e in source if not e['poison']],attempts=[],peak_inflight=1)
        dead=[e for e in source if e['poison']]
        return source,accepted,sink,dead
    def test_correct_manifest_and_deduplicated_effects(self):
        data=self.fixture();result=evaluate(*data,drained=True)
        self.assertTrue(result['success']);self.assertEqual(result['accepted'],20)
    def test_missing_effect_is_failure_even_if_queue_drained(self):
        source,accepted,sink,dead=self.fixture();sink['effects'].pop()
        self.assertFalse(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_wrong_tenant_content_is_failure(self):
        source,accepted,sink,dead=self.fixture();sink['effects'][0]['tenant']='foreign'
        self.assertFalse(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_poison_requires_correct_durable_deadletter(self):
        source,accepted,sink,dead=self.fixture();dead[0]=dict(dead[0],value=999)
        self.assertFalse(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_duplicate_deadletters_are_counted_not_extra_effects(self):
        source,accepted,sink,dead=self.fixture();dead.append(dead[0])
        self.assertTrue(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_concurrency_over_limit_fails(self):
        source,accepted,sink,dead=self.fixture();sink['peak_inflight']=9
        self.assertFalse(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_incomplete_drain_does_not_qualify(self):
        self.assertFalse(evaluate(*self.fixture(),drained=False)['success'])
    def test_rejected_wrong_attempt_is_still_failure(self):
        source,accepted,sink,dead=self.fixture();sink['attempts']=[dict(status=409)]
        self.assertFalse(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_event_ids_intentionally_collide_across_tenants(self):
        source=events(3)
        self.assertEqual(len({e['id'] for e in source}),1)
        self.assertEqual(len({(e['tenant'],e['id']) for e in source}),3)

    def test_boolean_result_cannot_equal_integer_one(self):
        event=dict(tenant='t',id='e',value=-2,payload='x',poison=False)
        effect=expected(event);effect['result']=True
        verdict=evaluate([event],[['t','e']],dict(effects=[effect],attempts=[],peak_inflight=1),[],drained=True)
        self.assertFalse(verdict['success'])
    def test_unconfirmed_manifest_entries_cannot_silently_disappear(self):
        source,accepted,sink,dead=self.fixture();accepted.pop()
        self.assertFalse(evaluate(source,accepted,sink,dead,drained=True)['success'])
    def test_fault_orphan_handlers_do_not_claim_client_concurrency(self):
        source,accepted,sink,dead=self.fixture();sink['peak_inflight']=24
        verdict=evaluate(source,accepted,sink,dead,drained=True,enforce_concurrency=False)
        self.assertTrue(verdict['success'])
        self.assertIsNone(verdict['http_concurrency_verified'])

    def test_load_rate_excludes_final_drain(self):
        samples=[dict(seconds=t,effects=n,queues=[dict(name='work',messages_ready=q,messages_unacknowledged=0)]) for t,n,q in [(1,10,10),(2,20,20),(3,30,30),(10,100,0)]]
        measured=load_metrics(samples,3)
        self.assertEqual(measured['observed_completion_rate_per_second'],10)
        self.assertEqual(measured['backlog_slope_per_second'],10)
        self.assertEqual(measured['publication_window_sample_count'],3)

    def test_malformed_deadletters_are_candidate_failures(self):
        for malformed in [None,False,1,[],['x'],{'tenant':[],'id':{}},{'tenant':'t','id':'e','value':True,'poison':True,'payload':'x'}]:
            with self.subTest(malformed=malformed):
                source,accepted,sink,dead=self.fixture();dead.append(malformed)
                verdict=evaluate(source,accepted,sink,dead,drained=True)
                self.assertFalse(verdict['success'])
                self.assertTrue(verdict['incorrect_deadletters'])
    def test_malformed_duplicate_publication_ledger_rejected(self):
        source,accepted,sink,dead=self.fixture()
        for ledger in [accepted+[accepted[0]],accepted+[[[],'x']],accepted+[['x']]]:
            with self.assertRaises(ValueError):evaluate(source,ledger,sink,dead,drained=True)


class QueueWorkerBoundaryTests(unittest.TestCase):
    def test_image_volumes_rejected_before_runtime(self):
        from scalability.runner import Trial,CandidateFailure
        with patch('scalability.runner.image_id',return_value='sha256:'+'a'*64),patch('scalability.runner.docker',return_value=SimpleNamespace(stdout=json.dumps([{'Config':{'Volumes':{'/escape':{}}}}]))):
            with self.assertRaises(CandidateFailure):Trial('bad-image')
    def test_failed_container_start_is_registered_for_cleanup(self):
        from scalability.runner import Trial
        trial=object.__new__(Trial);trial.network='owned-network';trial.containers=[]
        with patch('scalability.runner.docker',side_effect=RuntimeError('bad entrypoint')):
            with self.assertRaises(RuntimeError):trial.container('owned-container','image')
        self.assertEqual(trial.containers,['owned-container'])
    def test_runtime_log_policy_is_explicit(self):
        from scalability.runner import Trial
        trial=object.__new__(Trial);trial.network='owned-network';trial.containers=[]
        with patch('scalability.runner.docker') as command:trial.container('owned-container','image')
        argv=command.call_args.args
        self.assertIn('max-size=1m',argv);self.assertIn('max-file=2',argv)
    def test_seed_controls_values_and_payloads(self):
        self.assertEqual(events(10,seed=4),events(10,seed=4))
        self.assertNotEqual(events(10,seed=4),events(10,seed=5))

    def test_absent_owned_container_is_successful_cleanup(self):
        from scalability.runner import Trial
        trial=object.__new__(Trial);trial.containers=['owned'];trial.volumes=[];trial.network_created=False
        with patch('scalability.runner.docker',return_value=SimpleNamespace(returncode=1,stderr='No such container: owned')):
            self.assertEqual(trial.close(),[])
    def test_oversized_duration_rejected_before_any_runtime(self):
        from scalability.runner import run
        with patch('scalability.runner.Trial') as constructor:
            with self.assertRaisesRegex(ValueError,'duration exceeds'):
                run('image','unused',rate=1000,duration=101)
            constructor.assert_not_called()

class QueueMeasurementTests(unittest.TestCase):
    def test_timeout_overlap_is_unqualified_without_erasing_loss(self):
        source=events(2);accepted=[[e['tenant'],e['id']] for e in source]
        sink=dict(effects=[expected(source[0])],attempts=[dict(started=0,finished=1.2,status=201)],peak_inflight=100)
        result=evaluate(source,accepted,sink,[],drained=False)
        self.assertFalse(result['success'])
        self.assertFalse(result['correctness_and_drain_passed'])
        self.assertEqual(len(result['missing_effects']),1)
        self.assertIsNone(result['observed_sink_processing_bound_passed'])
        self.assertEqual(result['concurrency_measurement']['cause'],'unattributed')
    def test_unknown_bound_cannot_pass_even_with_complete_effects(self):
        source=events(1);accepted=[[e['tenant'],e['id']] for e in source]
        for finished in (None,1.0):
            sink=dict(effects=[expected(source[0])],attempts=[dict(started=0,finished=finished,status=201)],peak_inflight=1)
            result=evaluate(source,accepted,sink,[],drained=True)
            self.assertTrue(result['correctness_and_drain_passed'])
            self.assertFalse(result['success'])
            self.assertIsNone(result['http_concurrency_verified'])
    def test_short_intervals_only_qualify_observed_processing_bound(self):
        source=events(1);sink=dict(effects=[expected(source[0])],attempts=[dict(started=0,finished=.2,status=201)],peak_inflight=2)
        result=evaluate(source,[[source[0]['tenant'],source[0]['id']]],sink,[],drained=True)
        self.assertTrue(result['observed_sink_processing_bound_passed'])
        self.assertIsNone(result['http_concurrency_verified'])

    def test_snapshot_is_one_view_while_wal_writer_commits_between_reads(self):
        import contextlib,io,sqlite3,tempfile,threading
        from pathlib import Path
        from scalability.runner import SNAPSHOT_SCRIPT
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'sink.sqlite')
            connect=sqlite3.connect
            db=connect(path);db.execute('PRAGMA journal_mode=WAL')
            db.executescript('CREATE TABLE effects(tenant,id,body,committed); CREATE TABLE attempts(tenant,id,started,finished,status,dropped,fault_header); CREATE TABLE metrics(name,value);')
            db.execute('INSERT INTO effects VALUES(?,?,?,?)',('t','a',json.dumps({'tenant':'t','id':'a'}),1));db.commit();db.close()
            read_done=threading.Event();written=threading.Event();errors=[]
            def writer():
                try:
                    if not read_done.wait(5):raise AssertionError('reader barrier missing')
                    c=connect(path);c.execute('INSERT INTO effects VALUES(?,?,?,?)',('t','b',json.dumps({'tenant':'t','id':'b'}),2));c.commit();c.close()
                except BaseException as exc:errors.append(exc)
                finally:written.set()
            def reader_connect(*args,**kwargs):
                c=connect(*args,**kwargs)
                def trace(sql):
                    if sql=='SELECT tenant,id,committed FROM effects':
                        read_done.set()
                        if not written.wait(5):errors.append(AssertionError('writer barrier missing'))
                c.set_trace_callback(trace);return c
            thread=threading.Thread(target=writer);thread.start()
            output=io.StringIO()
            with patch('sqlite3.connect',side_effect=reader_connect),patch('sys.argv',['snapshot',path]),contextlib.redirect_stdout(output):
                exec(SNAPSHOT_SCRIPT,{})
            thread.join(5);self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            snapshot=json.loads(output.getvalue())
            self.assertEqual([e['id'] for e in snapshot['effects']],['a'])
            self.assertEqual([e['id'] for e in snapshot['effect_times']],['a'])
            c=connect(path);self.assertEqual(c.execute('SELECT COUNT(*) FROM effects').fetchone()[0],2);c.close()
