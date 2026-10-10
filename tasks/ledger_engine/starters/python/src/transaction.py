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

