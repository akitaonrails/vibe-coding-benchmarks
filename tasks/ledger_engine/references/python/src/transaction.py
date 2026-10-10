"""A begin-time snapshot with independent point, range and alias dependencies."""
from table import Table

class Transaction:
    def __init__(self, tenant, table):
        self.tenant = tenant
        self.snapshot = Table(table.entries)
        self.writes = {}
        self.points = set()
        self.ranges = []
        self.alias_reads = []

    def view(self):
        return self.snapshot.overlay(self.writes)

    def valid(self, current):
        for key in self.points | self.writes.keys():
            if self.snapshot.version(key) != current.version(key):
                return False
        for lo, hi in self.ranges:
            if self.snapshot.interval(self.tenant, lo, hi) != current.interval(self.tenant, lo, hi):
                return False
        for alias in self.alias_reads:
            if self.snapshot.aliases(self.tenant, alias) != current.aliases(self.tenant, alias):
                return False
        return True
