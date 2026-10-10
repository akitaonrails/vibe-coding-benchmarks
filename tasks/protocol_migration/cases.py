"""Controller-only executable oracle and seeded development inventories."""
import copy
import random


def oracle(requests):
    # Abstract state: immutable snapshots per scoped identity, no implementation cache.
    history = {}
    answers = []
    for q in requests:
        v = q.get('v', 1)
        tenant = 'legacy' if v == 1 else q['tenant']
        key = (tenant, q['id'])
        before = copy.deepcopy(history.get(key))
        error = None
        op = q['op']
        after = before
        if v == 2 and q['actor'] != tenant:
            error = 'forbidden'
        elif op == 'import':
            s = q['stored']
            if s['id'] != key[1] or (s['schema'] == 2 and s['tenant'] != tenant):
                error = 'identity'
            elif s['schema'] == 2:
                after = {k: copy.deepcopy(value) for k, value in s.items() if k != 'schema'}
            else:
                after = dict(tenant=tenant, id=key[1], generation=1,
                             state={'pending': 'pending', 'ok': 'ready', 'error': 'failed'}[s['status']])
                if 'value' in s:
                    after['payload'] = copy.deepcopy(s['value'])
                if after['state'] == 'failed':
                    after['reason'] = 'legacy_error'
        elif op == 'submit':
            if before is not None:
                error = 'conflict'
            else:
                after = dict(tenant=tenant, id=key[1], generation=1, state='pending')
                if 'payload' in q:
                    after['payload'] = copy.deepcopy(q['payload'])
        elif before is None:
            error = 'not_found'
        elif op == 'complete' and v == 2 and q['generation'] != before['generation']:
            error = 'stale'
        elif op == 'cancel' and before['state'] == 'cancelled':
            pass  # Repeated cancellation preserves an imported record exactly.
        elif op in ('complete', 'cancel', 'retry'):
            permitted = {'complete': {'pending'}, 'cancel': {'pending', 'cancelled'},
                         'retry': {'failed', 'cancelled'}}
            if before['state'] not in permitted[op]:
                error = 'conflict'
            else:
                after.pop('payload', None)
                if op == 'retry':
                    after.update(state='pending', generation=before['generation'] + 1)
                    after.pop('reason', None)
                elif op == 'cancel':
                    after['state'] = 'cancelled'
                elif 'reason' in q:
                    after.update(state='failed', reason=q['reason'])
                else:
                    after['state'] = 'ready'
                    if 'payload' in q:
                        after['payload'] = copy.deepcopy(q['payload'])
        if error:
            answers.append({'error': error})
            continue
        history[key] = copy.deepcopy(after)
        if v == 2:
            view = copy.deepcopy(after)
        else:
            view = {'id': key[1], 'status': {'pending': 'pending', 'ready': 'ok',
                                           'failed': 'error', 'cancelled': 'error'}[after['state']]}
            if 'payload' in after:
                view['value'] = copy.deepcopy(after['payload'])
        if op == 'export':
            view['schema'] = v
        answers.append({'stored' if op == 'export' else 'record': view})
    return answers


def cases(suite: str, seed: int = 0) -> list[dict]:
    if suite not in ('public', 'private'):
        raise ValueError('suite must be public or private')
    result = []
    def q(op, id='job', tenant='alpha', **kw):
        return dict(v=2, op=op, id=id, tenant=tenant, actor=tenant, **kw)
    def add(name, group, requests):
        result.append(dict(id=name, group=group, requests=requests, expected=oracle(requests)))
    add('legacy_lifecycle', 'compatibility', [dict(op=op, id='x', **extra) for op, extra in [
        ('get', {}), ('submit', {'payload': None}), ('get', {}), ('cancel', {}),
        ('retry', {}), ('complete', {'reason': 'disk'}), ('get', {}), ('retry', {}),
        ('complete', {'payload': [1, 'x']}), ('export', {}), ('cancel', {})]])
    add('legacy_import', 'compatibility', [dict(op='import', id='x', stored=dict(schema=1,id='x',status='ok',value=None)), dict(op='get',id='x'), dict(op='export',id='x')])
    requests = [q('submit', payload='secret')]
    for op in ('get','export','submit','complete','cancel','retry','import'):
        r=q(op);r['actor']='beta';r.update(generation=1, stored=dict(schema=1,id='job',status='ok'))
        requests.append(r)
    requests.extend([q('get'),q('get',tenant='beta')])
    add('authorization_before_lookup','authorization',requests)
    add('scoped_identifiers','identity',[q('submit',payload=1),q('submit',tenant='beta',payload=2),q('get'),q('get',tenant='beta'),q('submit',id='c',tenant='a:b',payload=3),q('submit',id='b:c',tenant='a',payload=4),q('get',id='c',tenant='a:b'),q('get',id='b:c',tenant='a')])
    add('absent_null','presence',[q('submit'),q('export'),q('complete',generation=1,payload=None),q('get'),q('export'),q('submit',id='other',payload=None),q('complete',id='other',generation=1),q('get',id='other')])
    add('cancel_retry_stale','lifecycle',[q('submit',payload='old'),q('cancel'),q('cancel'),q('complete',generation=1,payload='late'),q('retry'),q('complete',generation=1),q('get'),q('complete',generation=2,reason='failed'),q('retry'),q('complete',generation=3,payload={'ok':True}),q('complete',generation=3),q('retry'),q('get')])
    add('cached_miss_and_overwrite','cache',[q('get'),q('submit'),q('get'),q('complete',generation=1,payload=10),q('get'),q('import',stored=dict(schema=1,id='job',status='ok',value=20)),q('get'),q('export')])
    for status in ('pending','ok','error'):
        for present in (False,True):
            s=dict(schema=1,id='job',status=status)
            if present:s['value']=None
            add(f'migrate_{status}_{present}','migration',[q('import',stored=s),q('get'),q('export'),q('import',stored=s),q('get')])
    for state in ('pending','ready','failed','cancelled'):
        s=dict(schema=2,id='job',tenant='alpha',state=state,generation=7)
        if state=='failed':s['reason']='failure'
        else:s['payload']={'unicode':'日本語','nested':[None,False,0]}
        add(f'roundtrip_{state}','migration',[q('import',stored=s),q('export'),q('import',stored=s),q('get')])
    add('cancel_imported_idempotent','lifecycle',[q('import',stored=dict(schema=2,id='job',tenant='alpha',state='cancelled',generation=7,payload=None)),q('cancel'),q('export')])
    add('import_identity_atomic','identity',[q('submit',payload=1),q('import',stored=dict(schema=1,id='other',status='ok')),q('get'),q('import',stored=dict(schema=2,id='job',tenant='beta',state='ready',generation=8,payload='foreign')),q('get')])
    add('wire_interop','compatibility',[dict(op='submit',id='job',payload=None),q('get',tenant='legacy'),q('complete',tenant='legacy',generation=1,payload=42),dict(op='get',id='job'),dict(op='export',id='job')])
    if suite=='private':
        rng=random.Random(seed)
        for i in range(24):
            requests=[]
            for _ in range(90):
                tenant=rng.choice(['alpha','beta','a:b','legacy','日本語'])
                id=rng.choice(['job','b:c','Ω','0'])
                op=rng.choice(['get','export','submit','complete','cancel','retry','import'])
                r=q(op,id=id,tenant=tenant)
                if rng.randrange(8)==0:r['actor']='unauthorized'
                if op=='complete':
                    r['generation']=rng.randint(1,6)
                    if rng.randrange(3)==0:r['reason']='worker_failure'
                if op in ('complete','submit') and rng.randrange(2):r['payload']=rng.choice([None,0,False,[],{'x':'雪'}])
                if op=='import':
                    r['stored']=dict(schema=1,id=id,status=rng.choice(['pending','ok','error']))
                    if rng.randrange(2):r['stored']['value']=rng.choice([None,False,{'n':i}])
                requests.append(r)
            add(f'seed_{seed}_{i}','migration',requests)
    return copy.deepcopy(result)
