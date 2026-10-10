"""Versioned table and secondary-index predicates, including absent-row tombstones."""
from copy import deepcopy
from domain import Entry

class Table:
    def __init__(self, entries=None):
        self.entries = deepcopy(entries) if entries is not None else {}

    def version(self, key):
        item = self.entries.get(key)
        return item.version if item else 0

    def row(self, key):
        item = self.entries.get(key)
        return deepcopy(item.row) if item else None

    def overlay(self, writes):
        result = Table(self.entries)
        for key, row in writes.items():
            result.entries[key] = Entry(self.version(key), deepcopy(row))
        return result

    def interval(self, tenant, lo, hi):
        return {key: entry.version for key, entry in self.entries.items()
                if key[0] == tenant and lo <= key[1] < hi}

    def aliases(self, tenant, alias):
        return {key: entry.version for key, entry in self.entries.items()
                if key[0] == tenant and entry.row is not None
                and entry.row.get('alias') == alias}

    def apply(self, writes, revision):
        for key, row in writes.items():
            self.entries[key] = Entry(revision, deepcopy(row))
