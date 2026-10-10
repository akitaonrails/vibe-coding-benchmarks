"""Stable checkpoint and delta frames are the only recovery inputs."""
from copy import deepcopy
from domain import Entry
from table import Table

class Device:
    def __init__(self):
        self.image = {'schema': 2, 'revision': 0, 'entries': [], 'receipts': []}
        self.owner = None
        self.loaded = False
        self.journal = []

    def append(self, frames, fault=None):
        kept = deepcopy(frames if fault is None else frames[:fault['keep']])
        if fault is not None and fault['tear']:
            kept[-1] = {'kind': 'TORN'}
        self.journal.extend(kept)

    def publish(self, table, receipts, revision, fault=None):
        image = {'schema': 2, 'revision': revision,
                 'entries': [{'tenant': t, 'id': i, 'version': e.version, 'row': deepcopy(e.row)}
                             for (t, i), e in sorted(table.entries.items())],
                 'receipts': [{'tenant': t, 'request': q, 'revision': r}
                              for (t, q), r in sorted(receipts.items())]}
        if fault is None or (fault['keep'] == 2 and not fault['tear']):
            self.image = image
            self.owner = None
            self.journal.clear()

    def recover(self):
        table = Table()
        receipts = {}
        revision = self.image['revision']
        for item in self.image['entries']:
            tenant = self.owner if self.image['schema'] == 1 else item['tenant']
            row = deepcopy(item['row'])
            if row is not None:
                row['tenant'] = tenant
            table.entries[(tenant, item['id'])] = Entry(item['version'], row)
        for item in self.image['receipts']:
            tenant = self.owner if self.image['schema'] == 1 else item['tenant']
            receipts[(tenant, item['request'])] = item['revision']
        cursor = 0
        while cursor < len(self.journal):
            begin = self.journal[cursor]
            if begin['kind'] != 'BEGIN':
                break
            end = cursor + begin['count'] + 1
            if end >= len(self.journal):
                break
            edits = self.journal[cursor + 1:end]
            seal = self.journal[end]
            if seal['kind'] != 'SEAL' or any(e['kind'] != 'EDIT' for e in edits):
                break
            if seal['revision'] != begin['revision']:
                break
            table.apply({(begin['tenant'], e['id']): e['row'] for e in edits}, begin['revision'])
            revision = begin['revision']
            receipts[(begin['tenant'], begin['request'])] = revision
            cursor = end + 1
        self.journal = self.journal[:cursor]
        return table, receipts, revision

    def inspect(self, tenant):
        image = deepcopy(self.image)
        if image['schema'] == 1:
            if tenant != self.owner:
                image['entries'] = []
                image['receipts'] = []
        else:
            image['entries'] = [e for e in image['entries'] if e['tenant'] == tenant]
            image['receipts'] = [e for e in image['receipts'] if e['tenant'] == tenant]
        journal = []
        cursor = 0
        while cursor < len(self.journal):
            begin = self.journal[cursor]
            end = cursor + begin['count'] + 2
            if begin['tenant'] == tenant:
                journal.extend(deepcopy(self.journal[cursor:end]))
            cursor = end
        return {'checkpoint': image, 'journal': journal}
