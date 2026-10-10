import { copy, Entry, key, parts, Row } from './domain';
export class Table {
  readonly entries: Map<string, Entry>;
  constructor(entries: Map<string, Entry> = new Map()) { this.entries = copy(entries); }
  version(k: string): number { return this.entries.get(k)?.version ?? 0; }
  row(k: string): Row | null { return copy(this.entries.get(k)?.row ?? null); }
  overlay(writes: Map<string, Row | null>): Table {
    const result = new Table(this.entries);
    for (const [k, row] of writes) result.entries.set(k, { version: this.version(k), row: copy(row) });
    return result;
  }
  interval(tenant: string, lo: string, hi: string): Map<string, number> {
    const result = new Map<string, number>();
    for (const [k, entry] of this.entries) {
      const [t, id] = parts(k);
      if (t === tenant && lo <= id && id < hi) result.set(k, entry.version);
    }
    return result;
  }
  aliases(tenant: string, alias: string): Map<string, number> {
    const result = new Map<string, number>();
    for (const [k, entry] of this.entries) {
      if (parts(k)[0] === tenant && entry.row?.alias === alias) result.set(k, entry.version);
    }
    return result;
  }
  unique(): boolean {
    const seen = new Set<string>();
    for (const [k, entry] of this.entries) {
      if (typeof entry.row?.alias === 'string') {
        const indexKey = key(parts(k)[0], entry.row.alias);
        if (seen.has(indexKey)) return false;
        seen.add(indexKey);
      }
    }
    return true;
  }
  apply(writes: Map<string, Row | null>, revision: number): void {
    for (const [k, row] of writes) this.entries.set(k, { version: revision, row: copy(row) });
  }
}
