import { Row } from './domain';
import { Table } from './table';
export class Transaction {
  readonly snapshot: Table;
  readonly writes = new Map<string, Row | null>();
  readonly points = new Set<string>();
  readonly ranges: [string, string][] = [];
  readonly aliasReads: string[] = [];
  constructor(readonly tenant: string, table: Table) { this.snapshot = new Table(table.entries); }
  view(): Table { return this.snapshot.overlay(this.writes); }
}
