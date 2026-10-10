"""Controller-only abstract history oracle; native engines replay actual journal frames.

This model stores accepted logical commit states and renders inspect frames from
commit events. It never reconstructs rows by interpreting BEGIN/EDIT/SEAL bytes.
"""
from copy import deepcopy
import random


class Model:
    def __init__(self, mutation=None):
        self.mutation = mutation
        self.reset(64)

    def reset(self, capacity):
        self.capacity = capacity
        self.revision = 0
        self.rows = {}  # (tenant,id) -> (version, row or None)
        self.receipts = {}
        self.transactions = {}
        self.checkpoint_image = dict(schema=2, revision=0, entries=[], receipts=[])
        self.legacy_owner = None
        self.loaded = False
        self.events = []  # accepted deltas, not device frames

    def identity(self, tenant, identifier):
        return ('global', identifier) if self.mutation == 'unscoped_keys' else (tenant, identifier)

    @staticmethod
    def version(rows, key):
        return rows.get(key, (0, None))[0]

    def record(self, tenant, identifier, request):
        return dict(tenant=tenant, id=identifier, **{k: deepcopy(request[k]) for k in ('value', 'alias', 'note') if k in request})

    def overlay(self, tx):
        rows = deepcopy(tx['snapshot'])
        for key, row in tx['writes'].items():
            rows[key] = (self.version(rows, key), deepcopy(row))
        return rows

    @staticmethod
    def interval(rows, tenant, lo, hi):
        return {key: version for key, (version, _) in rows.items() if key[0] == tenant and lo <= key[1] < hi}

    @staticmethod
    def aliases(rows, tenant, alias):
        return {key: version for key, (version, row) in rows.items() if key[0] == tenant and row is not None and row.get('alias') == alias}

    def frames(self):
        frames = []
        for event in self.events:
            frames.append(dict(kind='BEGIN', tenant=event['tenant'], request=event['request'], revision=event['revision'], count=len(event['writes'])))
            frames.extend(dict(kind='EDIT', id=key[1], row=deepcopy(row)) for key, row in sorted(event['writes'].items()))
            frames.append(dict(kind='SEAL', revision=event['revision']))
        return frames

    def image(self):
        return dict(schema=2, revision=self.revision,
                    entries=[dict(tenant=key[0], id=key[1], version=version, row=deepcopy(row)) for key, (version, row) in sorted(self.rows.items())],
                    receipts=[dict(tenant=key[0], request=key[1], revision=rev) for key, rev in sorted(self.receipts.items())])

    def call(self, q):
        op = q['op']
        if op == 'init':
            self.reset(q['capacity'])
            return {'ok': True}
        if op == 'stats':
            return dict(revision=self.revision, journal_frames=len(self.frames()), capacity=self.capacity, transactions=len(self.transactions))
        if op == 'crash':
            self.transactions.clear()
            return {'recovered': self.revision}
        if op == 'checkpoint':
            f = q.get('fault')
            publish = f is None or (f['keep'] == 2 and not f['tear'])
            if self.mutation == 'early_checkpoint' and f is not None and f['keep'] >= 1:
                publish = True
            if publish:
                self.checkpoint_image = self.image()
                self.legacy_owner = None
                self.events.clear()
                if self.mutation == 'checkpoint_loses_receipts':
                    self.receipts.clear()
                    self.checkpoint_image['receipts'] = []
            if f is not None:
                self.transactions.clear()
                return {'error': 'interrupted'}
            return {'checkpoint': self.revision}
        v = q.get('v', 1)
        tenant = 'legacy' if v == 1 else q['tenant']
        if v == 2 and q['actor'] != tenant and self.mutation != 'skip_authorization':
            return {'error': 'forbidden'}
        def wire(row):
            if row is None:
                return None
            result = deepcopy(row)
            if v == 1:
                result.pop('tenant', None)
            return result
        if op == 'inspect':
            image = deepcopy(self.checkpoint_image)
            if image['schema'] == 1:
                if tenant != self.legacy_owner:
                    image['entries'] = []
                    image['receipts'] = []
            else:
                image['entries'] = [e for e in image['entries'] if e['tenant'] == tenant]
                image['receipts'] = [r for r in image['receipts'] if r['tenant'] == tenant]
            journal = []
            for event in self.events:
                if event['tenant'] == tenant:
                    journal += [dict(kind='BEGIN', tenant=tenant, request=event['request'], revision=event['revision'], count=len(event['writes']))]
                    journal += [dict(kind='EDIT', id=key[1], row=deepcopy(row)) for key, row in sorted(event['writes'].items())]
                    journal += [dict(kind='SEAL', revision=event['revision'])]
            return dict(checkpoint=image, journal=journal)
        if op == 'load':
            if self.loaded or self.revision or self.rows or self.receipts or self.events or self.transactions:
                return {'error': 'not_empty'}
            image = deepcopy(q['image'])
            self.loaded = True
            self.checkpoint_image = image
            self.legacy_owner = tenant
            self.revision = image['revision']
            self.rows = {self.identity(tenant, e['id']): (e['version'], None if e['row'] is None else dict(deepcopy(e['row']), tenant=tenant)) for e in image['entries']}
            self.receipts = {(tenant, r['request']): r['revision'] for r in image['receipts']}
            return {'loaded': self.revision}
        receipt_key = (tenant, q.get('request'))
        if op == 'commit' and receipt_key in self.receipts and self.mutation != 'skip_dedup':
            return {'committed': self.receipts[receipt_key]}
        handle = q.get('tx')
        if op == 'begin':
            if handle in self.transactions:
                return {'error': 'transaction_exists'}
            self.transactions[handle] = dict(tenant=tenant, snapshot=deepcopy(self.rows), reads=set(), ranges=[], aliases=[], writes={})
            return {'snapshot': self.revision}
        tx = self.transactions.get(handle)
        if tx is None:
            return {'error': 'transaction_missing'}
        if tx['tenant'] != tenant:
            return {'error': 'transaction_owner'}
        key = self.identity(tenant, q.get('id'))
        if op == 'abort':
            del self.transactions[handle]
            return {'ok': True}
        if op == 'read':
            tx['reads'].add(key)
            rows = self.overlay(tx)
            return {'record': wire(rows.get(key, (0, None))[1])}
        if op == 'scan':
            lo, hi = q['lo'], q['hi']
            if lo < hi:
                tx['ranges'].append((lo, hi))
            return {'records': [wire(row) for k, (_, row) in sorted(self.overlay(tx).items()) if k[0] == tenant and lo <= k[1] < hi and row is not None]}
        if op == 'lookup':
            alias = q['alias']
            tx['aliases'].append(alias)
            return {'records': [wire(row) for k, (_, row) in sorted(self.overlay(tx).items()) if k[0] == tenant and row is not None and row.get('alias') == alias]}
        if op in ('put', 'delete'):
            row = self.record(tenant, q['id'], q) if op == 'put' else None
            if self.mutation == 'drop_null' and row is not None:
                row = {k: value for k, value in row.items() if value is not None}
            tx['writes'][key] = row
            return {'ok': True}
        assert op == 'commit', op
        points = set(tx['writes']) | tx['reads']
        if self.mutation == 'skip_read_conflicts':
            points = set(tx['writes'])
        if self.mutation == 'skip_write_conflicts':
            points = set(tx['reads'])
        if any(self.version(tx['snapshot'], k) != self.version(self.rows, k) for k in points):
            return {'error': 'conflict'}
        if self.mutation != 'skip_range_conflicts' and any(self.interval(tx['snapshot'], tenant, lo, hi) != self.interval(self.rows, tenant, lo, hi) for lo, hi in tx['ranges']):
            return {'error': 'conflict'}
        if self.mutation != 'skip_alias_conflicts' and any(self.aliases(tx['snapshot'], tenant, alias) != self.aliases(self.rows, tenant, alias) for alias in tx['aliases']):
            return {'error': 'conflict'}
        proposed = deepcopy(self.rows)
        next_revision = self.revision + 1
        for k, row in tx['writes'].items():
            proposed[k] = (next_revision, deepcopy(row))
        if self.mutation == 'drop_tombstones':
            proposed = {k: pair for k, pair in proposed.items() if pair[1] is not None}
        if self.mutation != 'skip_uniqueness':
            aliases = set()
            for k, (_, row) in proposed.items():
                if row is not None and isinstance(row.get('alias'), str):
                    alias_key = (k[0], row['alias'])
                    if alias_key in aliases:
                        return {'error': 'unique'}
                    aliases.add(alias_key)
        required = len(tx['writes']) + 2
        if len(self.frames()) + required > self.capacity and self.mutation != 'skip_capacity':
            return {'error': 'capacity'}
        fault = q.get('fault')
        accepted = fault is None or (fault['keep'] == required and not fault['tear'])
        if self.mutation == 'accept_unsealed' and fault is not None and fault['keep'] >= required - 1:
            accepted = True
        if accepted:
            self.rows = proposed
            self.revision = next_revision
            self.receipts[receipt_key] = next_revision
            self.events.append(dict(tenant=tenant, request=q['request'], revision=next_revision, writes=deepcopy(tx['writes'])))
            del self.transactions[handle]
        if fault is not None:
            self.transactions.clear()
            return {'error': 'interrupted'}
        return {'committed': self.revision}


def oracle(requests, mutation=None):
    model = Model(mutation)
    return [deepcopy(model.call(q)) for q in requests]


def request(op, tenant='alpha', **fields):
    return dict(v=2, tenant=tenant, actor=tenant, op=op, **fields)


def cases(suite: str, seed: int = 0) -> list[dict]:
    if suite not in ('public', 'private'):
        raise ValueError('invalid suite')
    result = []
    def add(name, group, requests):
        result.append(dict(id=name, group=group, requests=requests, expected=oracle(requests)))
    def q(op, **fields):
        return request(op, **fields)
    def transaction(handle, rid, writes, tenant='alpha', fault=None):
        ops = [q('begin', tx=handle, tenant=tenant)]
        ops += [q('put', tx=handle, tenant=tenant, **row) for row in writes]
        commit = q('commit', tx=handle, request=rid, tenant=tenant)
        if fault is not None:
            commit['fault'] = fault
        return ops + [commit]
    def readback(tenant='alpha'):
        return [q('begin',tx='verify',tenant=tenant),q('scan',tx='verify',lo='0',hi='zzzz',tenant=tenant),q('abort',tx='verify',tenant=tenant)]
    add('working_v1','compatibility',[
        dict(op='init',capacity=12),dict(op='begin',tx='v1'),dict(op='put',tx='v1',id='a',value=5,alias=None,note=None),dict(op='put',tx='v1',id='b',value=8,alias='unique'),dict(op='read',tx='v1',id='a'),dict(op='lookup',tx='v1',alias='unique'),dict(op='scan',tx='v1',lo='a',hi='z'),dict(op='commit',tx='v1',request='first'),dict(op='crash'),dict(op='begin',tx='r'),dict(op='read',tx='r',id='a'),dict(op='abort',tx='r'),dict(op='inspect'),dict(op='checkpoint'),dict(op='inspect'),dict(op='stats')])
    add('tenant_auth_retry_scope','authorization',transaction('a','same',[dict(id='x',value=1,alias='shared')])+transaction('b','same',[dict(id='x',value=2,alias='shared')],tenant='beta')+[q('begin',tx='owned'),q('read',tx='owned',id='x',tenant='beta'),dict(q('commit',request='same'),actor='beta'),q('inspect',tenant='beta'),q('commit',request='same',tenant='beta')]+readback())
    add('delimiter_identities','identity',transaction('a','r',[dict(id='b:c',value=1)],tenant='a')+transaction('b','r',[dict(id='c',value=2)],tenant='a:b')+readback('a')+readback('a:b')+[q('inspect',tenant='a:b')])
    add('snapshot_read_your_writes_presence','snapshots',transaction('seed','seed',[dict(id='a',value=1,alias=None,note=None)])+[q('begin',tx='old')]+transaction('new','new',[dict(id='a',value=2,alias='new')])+[q('read',tx='old',id='a'),q('put',tx='old',id='b',value=3,note=None),q('scan',tx='old',lo='a',hi='z'),q('delete',tx='old',id='a'),q('read',tx='old',id='a'),q('commit',tx='old',request='conflict'),q('abort',tx='old')])
    add('read_conflict_after_checkpoint','read_conflicts',transaction('seed','seed',[dict(id='a',value=1)])+[q('begin',tx='old'),q('read',tx='old',id='a')]+transaction('new','new',[dict(id='a',value=2)])+[dict(op='checkpoint'),q('put',tx='old',id='b',value=9),q('commit',tx='old',request='r'),q('read',tx='old',id='b'),q('abort',tx='old'),q('inspect')])
    add('blind_write_aba_tombstone','write_conflicts',[q('begin',tx='old'),q('put',tx='old',id='missing',value=8)]+transaction('new','new',[dict(id='missing',value=1)])+[q('begin',tx='del'),q('delete',tx='del',id='missing'),q('commit',tx='del',request='deleted'),dict(op='checkpoint'),q('commit',tx='old',request='old'),q('inspect')])
    add('range_phantom_tombstone','range_conflicts',[q('begin',tx='scan'),q('scan',tx='scan',lo='a',hi='m'),q('begin',tx='delete'),q('delete',tx='delete',id='b'),q('commit',tx='delete',request='tombstone'),q('commit',tx='scan',request='readonly'),q('inspect')])
    add('range_boundary_nonconflict','range_conflicts',[q('begin',tx='scan'),q('scan',tx='scan',lo='a',hi='m'),q('scan',tx='scan',lo='z',hi='a')]+transaction('new','outside',[dict(id='m',value=1)])+[q('commit',tx='scan',request='readonly'),dict(op='stats'),q('inspect')])
    add('lookup_phantom_and_unrelated','index_conflicts',[q('begin',tx='look'),q('lookup',tx='look',alias='needle')]+transaction('new','new',[dict(id='a',value=1,alias='other')])+[q('commit',tx='look',request='unrelated'),q('begin',tx='look2'),q('lookup',tx='look2',alias='needle')]+transaction('new2','new2',[dict(id='b',value=2,alias='needle')])+[q('commit',tx='look2',request='phantom')])
    add('unique_swap_rollback_and_retry','uniqueness',transaction('seed','seed',[dict(id='a',value=1,alias='left'),dict(id='b',value=2,alias='right')])+[q('begin',tx='swap'),q('put',tx='swap',id='a',value=3,alias='right'),q('lookup',tx='swap',alias='right'),q('commit',tx='swap',request='swap'),q('put',tx='swap',id='b',value=4,alias='left'),q('commit',tx='swap',request='swap'),q('inspect')]+readback())
    add('capacity_rollback_live_snapshot','capacity',[dict(op='init',capacity=4)]+transaction('seed','seed',[dict(id='a',value=1)])+[q('begin',tx='waiting'),q('put',tx='waiting',id='b',value=2),q('commit',tx='waiting',request='wait'),dict(op='stats'),dict(op='checkpoint'),q('read',tx='waiting',id='a'),q('commit',tx='waiting',request='wait'),q('inspect')])
    add('absent_null_delete_recovery','presence',transaction('seed','seed',[dict(id='a',value=1,note=None,alias=None),dict(id='b',value=2)])+[dict(op='crash')]+readback()+[q('begin',tx='replace'),q('put',tx='replace',id='a',value=3),q('delete',tx='replace',id='b'),q('commit',tx='replace',request='replace'),dict(op='checkpoint'),dict(op='crash'),q('inspect')]+readback())
    add('dedup_lost_ack_checkpoint','retry',transaction('lost','same',[dict(id='a',value=1)],fault=dict(keep=3,tear=False))+[q('commit',request='same'),q('begin',tx='live'),q('put',tx='live',id='b',value=2),q('commit',tx='live',request='same'),dict(op='stats'),dict(op='checkpoint'),dict(op='crash'),q('commit',request='same'),q('inspect')]+readback())
    for keep,tear in [(0,False),(1,False),(2,False),(3,False),(4,False),(4,True),(3,True)]:
        add(f'journal_cut_{keep}_{tear}','durability',transaction('seed','seed',[dict(id='old',value=1)])+transaction('fault','lost',[dict(id='a',value=2),dict(id='b',value=3)],fault=dict(keep=keep,tear=tear))+[dict(op='stats'),q('commit',request='lost'),q('inspect'),dict(op='crash')]+readback()+transaction('after','after',[dict(id='c',value=4)])+[q('inspect')])
    legacy=dict(schema=1,revision=7,entries=[dict(id='a',version=5,row=dict(id='a',value=10,alias='old',note=None)),dict(id='gone',version=7,row=None)],receipts=[dict(request='legacy_commit',revision=7)])
    for keep,tear in [(0,False),(1,False),(1,True),(2,True),(2,False)]:
        add(f'checkpoint_migration_cut_{keep}_{tear}','migration',[q('load',image=legacy),q('inspect'),q('commit',request='legacy_commit')]+transaction('append','appended',[dict(id='b',value=2,alias='new')])+[dict(op='checkpoint',fault=dict(keep=keep,tear=tear)),q('inspect'),q('commit',request='legacy_commit'),q('commit',request='appended'),dict(op='crash')]+readback()+[dict(op='checkpoint'),q('inspect'),q('inspect',tenant='beta')])
    add('conflict_before_unique_fault','priority',transaction('seed','seed',[dict(id='a',value=1,alias='taken')])+[q('begin',tx='old'),q('read',tx='old',id='a')]+transaction('new','new',[dict(id='a',value=2,alias='taken')])+[q('put',tx='old',id='b',value=3,alias='taken'),q('commit',tx='old',request='priority',fault=dict(keep=0,tear=False)),dict(op='stats'),q('read',tx='old',id='b')])
    add('empty_load_pristine_once','migration',[q('load',image=dict(schema=1,revision=0,entries=[],receipts=[])),q('load',image=dict(schema=1,revision=0,entries=[],receipts=[])),dict(op='checkpoint'),q('load',image=dict(schema=1,revision=0,entries=[],receipts=[]))])
    if suite == 'private':
        rng=random.Random(seed)
        for sample in range(16):
            ops=[dict(op='init',capacity=rng.choice([12,16,24]))]
            for turn in range(12):
                tenant=rng.choice(['alpha','beta','a:b']);handle=f't{turn}';rid=f'r{turn}'
                ops.append(q('begin',tx=handle,tenant=tenant))
                ops.append(q('scan',tx=handle,tenant=tenant,lo='a',hi='z'))
                row=dict(id=rng.choice(['a','b','c']),value=rng.randint(-100,100))
                if rng.randrange(2):row['note']=rng.choice([None,False,[],{'n':turn}])
                if rng.randrange(2):row['alias']=rng.choice(['left','right',None])
                ops.append(q('put',tx=handle,tenant=tenant,**row))
                if rng.randrange(3)==0:
                    ops+=transaction(f'other{turn}',f'other{turn}',[dict(id=row['id'],value=turn)],tenant=tenant)
                commit=q('commit',tx=handle,request=rid,tenant=tenant)
                if rng.randrange(3)==0:
                    keep=rng.randrange(4);commit['fault']=dict(keep=keep,tear=bool(keep and rng.randrange(2)))
                ops.append(commit)
                ops.append(q('commit',request=rid,tenant=tenant))
                if rng.randrange(2):ops.append(dict(op='checkpoint',fault=dict(keep=rng.randrange(3),tear=False)))
                else:ops.append(dict(op='checkpoint'))
                ops.append(q('inspect',tenant=tenant))
            add(f'seed_{seed}_{sample}','combinations',ops)
    return result


def baseline_cases():
    """Working-v1 conformance inventory shared by independently authored ports."""
    result = [deepcopy(c) for c in cases('public') if c['id'] == 'working_v1']
    histories = {
        'baseline_tombstone_capacity_checkpoint': [
            dict(op='init', capacity=4), dict(op='begin', tx='a'),
            dict(op='delete', tx='a', id='absent'), dict(op='commit', tx='a', request='r1'),
            dict(op='begin', tx='b'), dict(op='put', tx='b', id='present', value=2),
            dict(op='commit', tx='b', request='r2'), dict(op='checkpoint'),
            dict(op='commit', tx='b', request='r2'), dict(op='crash'), dict(op='inspect')],
        'baseline_schema1_load': [
            dict(op='load', image=dict(schema=1, revision=2,
                 entries=[dict(id='a', version=2, row=dict(id='a', value=9, note=None))],
                 receipts=[dict(request='old', revision=2)])),
            dict(op='crash'), dict(op='begin', tx='a'), dict(op='read', tx='a', id='a'),
            dict(op='put', tx='a', id='b', value=8, alias='b'), dict(op='commit', tx='a', request='new'),
            dict(op='inspect'), dict(op='checkpoint'), dict(op='inspect')],
        'baseline_snapshot_without_conflict': [
            dict(op='begin', tx='a'), dict(op='put', tx='a', id='a', value=1),
            dict(op='read', tx='a', id='a'), dict(op='delete', tx='a', id='a'),
            dict(op='read', tx='a', id='a'), dict(op='abort', tx='a'),
            dict(op='begin', tx='a'), dict(op='scan', tx='a', lo='z', hi='a'),
            dict(op='commit', tx='a', request='empty'), dict(op='stats'), dict(op='crash')]
    }
    for name, requests in histories.items():
        result.append(dict(id=name, group='compatibility', requests=requests, expected=oracle(requests)))
    return result
