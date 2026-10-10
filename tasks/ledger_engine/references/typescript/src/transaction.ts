import { Row } from './domain';
import { Table } from './table';
function equalVersions(left: Map<string, number>, right: Map<string, number>): boolean {
  return left.size === right.size && [...left].every(([k, version]) => right.get(k) === version);
}
export class Transaction {
  readonly snapshot: Table;
  readonly writes = new Map<string, Row | null>();
  readonly points = new Set<string>();
  readonly ranges: [string, string][] = [];
  readonly aliasReads: string[] = [];
  constructor(readonly tenant: string, table: Table) { this.snapshot = new Table(table.entries); }
  view(): Table { return this.snapshot.overlay(this.writes); }
  valid(current: Table): boolean {
    for (const k of new Set([...this.points, ...this.writes.keys()])) {
      if (this.snapshot.version(k) !== current.version(k)) return false;
    }
    for (const [lo, hi] of this.ranges) {
      if (!equalVersions(this.snapshot.interval(this.tenant, lo, hi), current.interval(this.tenant, lo, hi))) return false;
    }
    for (const alias of this.aliasReads) {
      if (!equalVersions(this.snapshot.aliases(this.tenant, alias), current.aliases(this.tenant, alias))) return false;
    }
    return true;
  }
}
