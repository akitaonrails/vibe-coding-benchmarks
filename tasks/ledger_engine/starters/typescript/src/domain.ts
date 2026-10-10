/** Native domain values. JSON is copied at ownership boundaries. */
export type Json = null | boolean | number | string | Json[] | { [key: string]: Json };
export interface Row { tenant: string; id: string; value: number; alias?: string | null; note?: Json }
export type LegacyRow = Omit<Row, 'tenant'>;
export interface Entry { version: number; row: Row | null }
export interface Fault { keep: number; tear: boolean }
export interface ImageEntry { tenant?: string; id: string; version: number; row: Row | LegacyRow | null }
export interface Receipt { tenant?: string; request: string; revision: number }
export interface Image { schema: 1 | 2; revision: number; entries: ImageEntry[]; receipts: Receipt[] }
export type Frame = { kind: 'BEGIN'; tenant: string; request: string; revision: number; count: number }
  | { kind: 'EDIT'; id: string; row: Row | null } | { kind: 'SEAL'; revision: number } | { kind: 'TORN' };
export interface Request {
  op: 'init' | 'stats' | 'crash' | 'checkpoint' | 'inspect' | 'load' | 'begin' | 'commit' | 'abort' | 'read' | 'scan' | 'lookup' | 'put' | 'delete';
  v?: 1 | 2; tenant?: string; actor?: string; tx?: string; id?: string; request?: string;
  value?: number; alias?: string | null; note?: Json; lo?: string; hi?: string;
  capacity?: number; image?: Image; fault?: Fault;
}
export function required<T>(value: T | undefined): T {
  if (value === undefined) throw new Error('missing required contract field');
  return value;
}
export function copy<T>(value: T): T { return structuredClone(value); }
export function key(tenant: string, id: string): string { return JSON.stringify([tenant, id]); }
export function parts(encoded: string): [string, string] { return JSON.parse(encoded) as [string, string]; }
export function compare(a: string, b: string): number { return a < b ? -1 : a > b ? 1 : 0; }
export function compareKeys(a: string, b: string): number {
  const [at, ai] = parts(a), [bt, bi] = parts(b);
  return compare(at, bt) || compare(ai, bi);
}
export function makeRow(tenant: string, q: Request): Row {
  const row: Row = { tenant, id: required(q.id), value: required(q.value) };
  if (Object.hasOwn(q, 'alias')) row.alias = q.alias;
  if (Object.hasOwn(q, 'note')) row.note = copy(q.note);
  return row;
}
export function project(row: Row | null, version: number): Row | LegacyRow | null {
  if (row === null) return null;
  if (version === 2) return copy(row);
  const { tenant: _tenant, ...legacy } = copy(row);
  return legacy;
}
