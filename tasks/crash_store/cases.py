"""Trusted history oracle. No candidate code or native reference is imported."""
import random

critical_groups = ["atomicity", "snapshots", "reclamation", "capacity", "recovery"]

class History:
    def __init__(self):
        self.versions = [({}, set())]
        self.current = 0
        self.handles = {}
        self.allocated = set()
        self.next_page = self.next_handle = 1
        self.capacity = 0

    def call(self, r):
        op = r['op']
        if op == 'init':
            self.__init__()
            self.capacity = r['capacity']
            return {'ok': True}
        live = set(self.versions[self.current][1])
        for v in self.handles.values():
            live.update(self.versions[v][1])
        if op == 'status':
            return dict(used=len(self.allocated), live=len(live), snapshots=len(self.handles))
        if op == 'snapshot':
            h = self.next_handle
            self.next_handle += 1
            self.handles[h] = self.current
            return {'snapshot': h}
        if op in ('read', 'drop'):
            h = r.get('snapshot')
            if h is not None and h not in self.handles:
                return {'error': 'snapshot'}
            if op == 'drop':
                del self.handles[h]
                return {'ok': True}
            v = self.current if h is None else self.handles[h]
            return {'data': dict(self.versions[v][0])}
        if op == 'crash':
            return {'ok': True}
        if op == 'reclaim':
            dead = sorted(self.allocated - live)
            removed = dead[:r.get('cut', len(dead))]
            self.allocated.difference_update(removed)
            return {'crashed': True} if 'cut' in r else {'reclaimed': len(removed)}
        data = dict(self.versions[self.current][0])
        for k, v in r['changes']:
            if v is None:
                data.pop(k, None)
            else:
                data[k] = v
        n = max(1, len(data))
        if len(self.allocated) + n > self.capacity:
            return {'error': 'full'}
        written = min(n, r.get('cut', n + 1))
        pages = set(range(self.next_page, self.next_page + written))
        self.next_page += written
        self.allocated.update(pages)
        if r.get('cut', n + 1) > n:
            self.versions.append((data, pages))
            self.current = len(self.versions) - 1
        return {'crashed': True} if 'cut' in r else {'ok': True}

def _case(name, group, requests):
    model = History()
    return dict(id=name, group=group, requests=requests,
                expected=[model.call(r) for r in requests])

def cases(suite: str, seed: int = 0) -> list[dict]:
    if suite not in ('public', 'private'):
        raise ValueError('suite must be public or private')
    out = []
    for cut in range(5):
        rs = [{'op':'init','capacity':12}, {'op':'commit','changes':[['a','old']]},
              {'op':'snapshot'}, {'op':'commit','changes':[['a','new'],['b','B']], 'cut':cut},
              {'op':'crash'}, {'op':'read'}, {'op':'read','snapshot':1},
              {'op':'status'}, {'op':'reclaim'}, {'op':'status'}]
        out.append(_case(f'publication-{cut}', 'atomicity', rs))
    base = [{'op':'init','capacity':3}, {'op':'snapshot'},
            {'op':'commit','changes':[['x','1']]}, {'op':'snapshot'},
            {'op':'commit','changes':[['x','2']]}, {'op':'snapshot'},
            {'op':'commit','changes':[['x','3']]}, {'op':'reclaim'},
            {'op':'commit','changes':[]}, {'op':'drop','snapshot':2},
            {'op':'reclaim','cut':0}, {'op':'status'}, {'op':'reclaim','cut':1},
            {'op':'crash'}, {'op':'commit','changes':[['x',None]]},
            {'op':'read','snapshot':2}, {'op':'read','snapshot':3},
            {'op':'read','snapshot':1}, {'op':'status'}, {'op':'snapshot'}]
    for group in critical_groups[1:]:
        out.append(_case('lifetime-'+group, group, base))
    if suite == 'private':
        rng = random.Random(seed)
        for i in range(40):
            rs = [{'op':'init','capacity':rng.randrange(2,16)}]
            handles = 0
            for _ in range(100):
                op = rng.choice(['commit']*4 + ['snapshot','drop','read','reclaim','crash'])
                r = {'op':op}
                if op == 'commit':
                    r['changes'] = [[rng.choice(['a','b','c','δ','🌳']), rng.choice([None,'','x','λ'])] for _ in range(rng.randrange(5))]
                if op == 'snapshot': handles += 1
                if op == 'drop' or (op == 'read' and rng.random()<.5):
                    r['snapshot'] = rng.randrange(1,handles+3)
                if op in ('commit','reclaim') and rng.random()<.6:
                    r['cut'] = rng.randrange(7)
                rs.extend([r, {'op':'status'}, {'op':'read'}])
            out.append(_case(f'seed-{seed}-{i}',critical_groups[i%5],rs))
    return out
