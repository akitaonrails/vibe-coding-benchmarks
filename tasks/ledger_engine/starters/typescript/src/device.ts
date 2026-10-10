import { compareKeys, copy, Fault, Frame, Image, key, parts, required, Row } from './domain';
import { Table } from './table';
/** Only image, adoption metadata and journal survive recovery. */
export class Device {
  image: Image = { schema: 2, revision: 0, entries: [], receipts: [] };
  owner: string | undefined;
  loaded = false;
  journal: Frame[] = [];
  append(frames: Frame[], fault?: Fault): void {
    this.journal.push(...copy(frames));
  }
  publish(table: Table, receipts: Map<string, number>, revision: number, fault?: Fault): void {
    const image: Image = { schema: 2, revision,
      entries: [...table.entries].sort(([a], [b]) => compareKeys(a, b)).map(([k, e]) => {
        const [tenant, id] = parts(k); return { tenant, id, version: e.version, row: copy(e.row) };
      }),
      receipts: [...receipts].sort(([a], [b]) => compareKeys(a, b)).map(([k, r]) => {
        const [tenant, request] = parts(k); return { tenant, request, revision: r };
      }) };
    this.image = image; this.owner = undefined; this.journal = [];
  }
  recover(): { table: Table; receipts: Map<string, number>; revision: number } {
    const table = new Table(), receipts = new Map<string, number>();
    let revision = this.image.revision;
    for (const entry of this.image.entries) {
      const tenant = required(this.image.schema === 1 ? this.owner : entry.tenant);
      const row: Row | null = entry.row === null ? null : { ...copy(entry.row), tenant };
      table.entries.set(key(tenant, entry.id), { version: entry.version, row });
    }
    for (const receipt of this.image.receipts) {
      const tenant = required(this.image.schema === 1 ? this.owner : receipt.tenant);
      receipts.set(key(tenant, receipt.request), receipt.revision);
    }
    let cursor = 0;
    while (cursor < this.journal.length) {
      const begin = required(this.journal[cursor]);
      if (begin.kind !== 'BEGIN') break;
      const end = cursor + begin.count + 1;
      if (end >= this.journal.length) break;
      const seal = required(this.journal[end]), edits = this.journal.slice(cursor + 1, end);
      if (seal.kind !== 'SEAL' || seal.revision !== begin.revision || edits.some(e => e.kind !== 'EDIT')) break;
      const writes = new Map<string, Row | null>();
      for (const edit of edits) {
        if (edit.kind === 'EDIT') writes.set(key(begin.tenant, edit.id), edit.row);
      }
      table.apply(writes, begin.revision); revision = begin.revision;
      receipts.set(key(begin.tenant, begin.request), revision);
      cursor = end + 1;
    }
    this.journal = this.journal.slice(0, cursor);
    return { table, receipts, revision };
  }
  inspect(tenant: string): { checkpoint: Image; journal: Frame[] } {
    const image = copy(this.image);
    if (image.schema === 1) {
      if (tenant !== this.owner) { image.entries = []; image.receipts = []; }
    } else {
      image.entries = image.entries.filter(e => e.tenant === tenant);
      image.receipts = image.receipts.filter(e => e.tenant === tenant);
    }
    const journal: Frame[] = [];
    let cursor = 0;
    while (cursor < this.journal.length) {
      const begin = required(this.journal[cursor]);
      if (begin.kind !== 'BEGIN') throw new Error('unrecovered journal');
      const end = cursor + begin.count + 2;
      if (begin.tenant === tenant) journal.push(...copy(this.journal.slice(cursor, end)));
      cursor = end;
    }
    return { checkpoint: image, journal };
  }
}
