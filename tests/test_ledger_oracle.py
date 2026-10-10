"""Hand-derived history anchors and abstract semantic mutation adequacy."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'tasks' / 'ledger_engine'
spec = importlib.util.spec_from_file_location('ledger_cases', ROOT / 'cases.py')
catalog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog)
q = catalog.request


class LedgerOracleTests(unittest.TestCase):
    def test_hand_derived_torn_seal_vs_lost_ack(self):
        common = [q('begin', tx='t'), q('put', tx='t', id='a', value=1, note=None)]
        self.assertEqual(catalog.oracle(common + [q('commit', tx='t', request='r', fault=dict(keep=3, tear=True)),dict(op='stats'),q('commit',request='r')]),[
            {'snapshot':0},{'ok':True},{'error':'interrupted'},
            {'revision':0,'journal_frames':0,'capacity':64,'transactions':0},{'error':'transaction_missing'}])
        self.assertEqual(catalog.oracle(common + [q('commit', tx='t', request='r', fault=dict(keep=3, tear=False)),dict(op='stats'),q('commit',request='r')]),[
            {'snapshot':0},{'ok':True},{'error':'interrupted'},
            {'revision':1,'journal_frames':3,'capacity':64,'transactions':0},{'committed':1}])

    def test_hand_derived_atomic_unique_swap(self):
        requests=[q('begin',tx='seed'),q('put',tx='seed',id='a',value=1,alias='one'),q('put',tx='seed',id='b',value=2,alias='two'),q('commit',tx='seed',request='seed'),q('begin',tx='swap'),q('put',tx='swap',id='a',value=3,alias='two'),q('commit',tx='swap',request='swap'),q('put',tx='swap',id='b',value=4,alias='one'),q('commit',tx='swap',request='swap'),dict(op='stats')]
        self.assertEqual(catalog.oracle(requests),[{'snapshot':0},{'ok':True},{'ok':True},{'committed':1},{'snapshot':1},{'ok':True},{'error':'unique'},{'ok':True},{'committed':2},{'revision':2,'journal_frames':8,'capacity':64,'transactions':0}])

    def test_hand_derived_durable_representation(self):
        row=dict(tenant='alpha',id='a',value=7,alias=None)
        requests=[q('begin',tx='t'),q('put',tx='t',id='a',value=7,alias=None),q('commit',tx='t',request='r'),q('inspect'),dict(op='checkpoint'),q('inspect')]
        result=catalog.oracle(requests)
        self.assertEqual(result[3],dict(checkpoint=dict(schema=2,revision=0,entries=[],receipts=[]),journal=[dict(kind='BEGIN',tenant='alpha',request='r',revision=1,count=1),dict(kind='EDIT',id='a',row=row),dict(kind='SEAL',revision=1)]))
        self.assertEqual(result[5],dict(checkpoint=dict(schema=2,revision=1,entries=[dict(tenant='alpha',id='a',version=1,row=row)],receipts=[dict(tenant='alpha',request='r',revision=1)]),journal=[]))

    def test_hand_derived_tombstone_and_range_phantom(self):
        requests=[q('begin',tx='r'),q('scan',tx='r',lo='a',hi='z'),q('begin',tx='d'),q('delete',tx='d',id='missing'),q('commit',tx='d',request='delete'),q('commit',tx='r',request='scan'),dict(op='checkpoint'),q('inspect')]
        results=catalog.oracle(requests)
        self.assertEqual(results[:6],[{'snapshot':0},{'records':[]},{'snapshot':0},{'ok':True},{'committed':1},{'error':'conflict'}])
        self.assertEqual(results[-1]['checkpoint']['entries'],[dict(tenant='alpha',id='missing',version=1,row=None)])

    def test_hand_derived_legacy_publication_and_retry(self):
        legacy=dict(schema=1,revision=8,entries=[dict(id='a',version=8,row=dict(id='a',value=1,note=None))],receipts=[dict(request='old',revision=8)])
        requests=[q('load',image=legacy),dict(op='checkpoint',fault=dict(keep=1,tear=False)),q('inspect'),q('commit',request='old'),dict(op='checkpoint'),q('inspect',tenant='beta')]
        self.assertEqual(catalog.oracle(requests),[{'loaded':8},{'error':'interrupted'},{'checkpoint':legacy,'journal':[]},{'committed':8},{'checkpoint':8},{'checkpoint':dict(schema=2,revision=8,entries=[],receipts=[]),'journal':[]}])

    def test_abstract_semantic_mutants_killed_by_public_cases(self):
        # Model mutants establish semantic coverage; native mutation gates are separate.
        mutants=['unscoped_keys','skip_authorization','drop_null','skip_dedup',
                 'skip_read_conflicts','skip_write_conflicts','skip_range_conflicts',
                 'skip_alias_conflicts','drop_tombstones','skip_uniqueness','skip_capacity',
                 'accept_unsealed','early_checkpoint','checkpoint_loses_receipts']
        public=catalog.cases('public')
        for mutation in mutants:
            with self.subTest(mutation=mutation):
                killed=[case['id'] for case in public if catalog.oracle(case['requests'],mutation)!=case['expected']]
                self.assertTrue(killed, f'surviving abstract semantic mutant: {mutation}')

    def test_seeded_inventory_determinism(self):
        self.assertEqual(catalog.cases('private',123),catalog.cases('private',123))
        self.assertNotEqual(catalog.cases('private',123),catalog.cases('private',124))
        ids=[c['id'] for c in catalog.cases('private',123)]
        self.assertEqual(len(ids),len(set(ids)))

    def test_baseline_inventory_is_v1(self):
        for case in catalog.baseline_cases():
            for request in case['requests']:
                self.assertEqual(request.get('v',1),1)
                self.assertNotIn('fault',request)


if __name__ == '__main__':
    unittest.main()
