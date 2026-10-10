import { compareKeys, copy, Frame, key, makeRow, parts, project, Request, required } from './domain';
import { Device } from './device';
import { Table } from './table';
import { Transaction } from './transaction';
export class Engine {
  private capacity = 64;
  private device = new Device();
  private table = new Table();
  private receipts = new Map<string, number>();
  private revision = 0;
  private transactions = new Map<string, Transaction>();
  private reset(capacity: number): void {
    this.capacity = capacity; this.device = new Device(); this.table = new Table();
    this.receipts.clear(); this.revision = 0; this.transactions.clear();
  }
  private recover(): void {
    const recovered = this.device.recover();
    this.table = recovered.table; this.receipts = recovered.receipts; this.revision = recovered.revision;
    this.transactions.clear();
  }
  handle(q: Request): unknown {
    const op = q.op;
    if (op === 'init') { this.reset(required(q.capacity)); return { ok: true }; }
    if (op === 'stats') return { revision: this.revision, journal_frames: this.device.journal.length,
      capacity: this.capacity, transactions: this.transactions.size };
    if (op === 'crash') { this.recover(); return { recovered: this.revision }; }
    if (op === 'checkpoint') {
      this.device.publish(this.table, this.receipts, this.revision, q.fault);
      if (q.fault) { this.recover(); return { error: 'interrupted' }; }
      return { checkpoint: this.revision };
    }
    const version = q.v ?? 1;
    const tenant = version === 1 ? 'legacy' : required(q.tenant);
    if (version === 2 && tenant !== q.actor) return { error: 'forbidden' };
    if (op === 'inspect') return this.device.inspect(tenant);
    if (op === 'load') {
      if (this.revision || this.transactions.size || this.device.loaded || this.device.journal.length || this.device.image.entries.length || this.device.image.receipts.length) return { error: 'not_empty' };
      this.device.image = copy(required(q.image)); this.device.owner = tenant; this.device.loaded = true;
      this.recover(); return { loaded: this.revision };
    }
    if (op === 'begin') {
      if (this.transactions.has(required(q.tx))) return { error: 'transaction_exists' };
      this.transactions.set(required(q.tx), new Transaction(tenant, this.table));
      return { snapshot: this.revision };
    }
    if (op === 'commit' && this.receipts.has(key(tenant, required(q.request)))) {
      return { committed: this.receipts.get(key(tenant, required(q.request))) };
    }
    const tx = q.tx === undefined ? undefined : this.transactions.get(q.tx);
    if (!tx) return { error: 'transaction_missing' };
    if (tx.tenant !== tenant) return { error: 'transaction_owner' };
    if (op === 'commit') {
      if (!tx.valid(this.table)) return { error: 'conflict' };
      if (!this.table.overlay(tx.writes).unique()) return { error: 'unique' };
      if (this.device.journal.length + tx.writes.size + 2 > this.capacity) return { error: 'capacity' };
      const revision = this.revision + 1;
      const frames: Frame[] = [{ kind: 'BEGIN', tenant, request: required(q.request), revision, count: tx.writes.size }];
      for (const [k, row] of [...tx.writes].sort(([a], [b]) => compareKeys(a, b))) {
        frames.push({ kind: 'EDIT', id: parts(k)[1], row: copy(row) });
      }
      frames.push({ kind: 'SEAL', revision }); this.device.append(frames, q.fault);
      if (q.fault) { this.recover(); return { error: 'interrupted' }; }
      this.table.apply(tx.writes, revision); this.revision = revision;
      this.receipts.set(key(tenant, required(q.request)), revision); this.transactions.delete(required(q.tx));
      return { committed: revision };
    }
    if (op === 'abort') this.transactions.delete(required(q.tx));
    else if (op === 'put') tx.writes.set(key(tenant, required(q.id)), makeRow(tenant, q));
    else if (op === 'delete') tx.writes.set(key(tenant, required(q.id)), null);
    else if (op === 'read') {
      const k = key(tenant, required(q.id)); tx.points.add(k);
      return { record: project(tx.view().row(k), version) };
    } else if (op === 'scan' || op === 'lookup') {
      const view = tx.view(); let keys: Map<string, number>;
      if (op === 'scan') {
        const lo = required(q.lo), hi = required(q.hi);
        if (lo < hi) tx.ranges.push([lo, hi]);
        keys = view.interval(tenant, lo, hi);
      } else {
        const alias = required(q.alias);
        if (alias === null) throw new Error('lookup requires string alias');
        tx.aliasReads.push(alias); keys = view.aliases(tenant, alias);
      }
      return { records: [...keys.keys()].sort(compareKeys).filter(k => view.row(k) !== null).map(k => project(view.row(k), version)) };
    }
    return { ok: true };
  }
}
