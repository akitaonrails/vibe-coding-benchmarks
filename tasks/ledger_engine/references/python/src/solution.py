"""Wire authorization and transaction lifecycle."""
from copy import deepcopy
from device import Device
from domain import record, project
from table import Table
from transaction import Transaction

class Engine:
    def __init__(self):
        self.reset(64)

    def reset(self, capacity):
        self.capacity = capacity
        self.device = Device()
        self.table = Table()
        self.receipts = {}
        self.revision = 0
        self.transactions = {}

    def recover(self):
        self.table, self.receipts, self.revision = self.device.recover()
        self.transactions.clear()

    def handle(self, request):
        op = request['op']
        if op == 'init':
            self.reset(request['capacity'])
            return {'ok': True}
        if op == 'stats':
            return {'revision': self.revision, 'journal_frames': len(self.device.journal),
                    'capacity': self.capacity, 'transactions': len(self.transactions)}
        if op == 'crash':
            self.recover()
            return {'recovered': self.revision}
        if op == 'checkpoint':
            self.device.publish(self.table, self.receipts, self.revision, request.get('fault'))
            if 'fault' in request:
                self.recover()
                return {'error': 'interrupted'}
            return {'checkpoint': self.revision}
        version = request.get('v', 1)
        tenant = 'legacy' if version == 1 else request['tenant']
        if version == 2 and tenant != request['actor']:
            return {'error': 'forbidden'}
        if op == 'inspect':
            return self.device.inspect(tenant)
        if op == 'load':
            if self.revision or self.transactions or self.device.loaded or self.device.journal or self.device.image['entries'] or self.device.image['receipts']:
                return {'error': 'not_empty'}
            self.device.image = deepcopy(request['image'])
            self.device.owner = tenant
            self.device.loaded = True
            self.recover()
            return {'loaded': self.revision}
        if op == 'begin':
            if request['tx'] in self.transactions:
                return {'error': 'transaction_exists'}
            self.transactions[request['tx']] = Transaction(tenant, self.table)
            return {'snapshot': self.revision}
        if op == 'commit' and (tenant, request['request']) in self.receipts:
            return {'committed': self.receipts[(tenant, request['request'])]}
        tx = self.transactions.get(request.get('tx'))
        if tx is None:
            return {'error': 'transaction_missing'}
        if tx.tenant != tenant:
            return {'error': 'transaction_owner'}
        if op == 'commit':
            if not tx.valid(self.table):
                return {'error': 'conflict'}
            if not self.table.overlay(tx.writes).unique():
                return {'error': 'unique'}
            if len(self.device.journal) + len(tx.writes) + 2 > self.capacity:
                return {'error': 'capacity'}
            revision = self.revision + 1
            frames = [{'kind': 'BEGIN', 'tenant': tenant, 'request': request['request'],
                       'revision': revision, 'count': len(tx.writes)}]
            frames += [{'kind': 'EDIT', 'id': key[1], 'row': deepcopy(row)} for key, row in sorted(tx.writes.items())]
            frames.append({'kind': 'SEAL', 'revision': revision})
            self.device.append(frames, request.get('fault'))
            if 'fault' in request:
                self.recover()
                return {'error': 'interrupted'}
            self.table.apply(tx.writes, revision)
            self.revision = revision
            self.receipts[(tenant, request['request'])] = revision
            del self.transactions[request['tx']]
            return {'committed': revision}
        if op == 'abort':
            del self.transactions[request['tx']]
        elif op == 'put':
            tx.writes[(tenant, request['id'])] = record(tenant, request)
        elif op == 'delete':
            tx.writes[(tenant, request['id'])] = None
        elif op == 'read':
            key = (tenant, request['id'])
            tx.points.add(key)
            return {'record': project(tx.view().row(key), version)}
        elif op in ('scan', 'lookup'):
            view = tx.view()
            if op == 'scan':
                lo, hi = request['lo'], request['hi']
                if lo < hi:
                    tx.ranges.append((lo, hi))
                keys = view.interval(tenant, lo, hi)
            else:
                tx.alias_reads.append(request['alias'])
                keys = view.aliases(tenant, request['alias'])
            return {'records': [project(view.row(key), version) for key in sorted(keys) if view.row(key) is not None]}
        return {'ok': True}
