# Protocol migration (development instance F4)

Implement v2 across the repository, wire, cache and worker modules in `src/`.
The starter is a working v1 service. Only `src/**` is editable. The adapter reads
one JSON object per line and writes one JSON object per line. Each test case
starts a fresh process; requests in a case share memory. No external I/O needed.

## Inputs and authorization
Every request has `op`, `id` (nonempty Unicode string), optional `v` (1 or 2,
default 1). V1 always addresses tenant `legacy`. V2 requires a nonempty `tenant`
string and `actor` string. Before any lookup or mutation, actor must equal tenant;
otherwise return `{"error":"forbidden"}`. V1 does not inspect actor/tenant.
IDs and tenants are case-sensitive opaque strings; tuple scope, never delimiter
concatenation, determines identity. Inputs satisfy these shapes; malformed input
handling is outside grading. Integer generations are in 1..1000000.

## Records and views
V2 view: `{"tenant":T,"id":I,"state":S,"generation":G}` plus `payload` only
when present. Payload is any JSON value, including null. States are `pending`,
`ready`, `failed`, `cancelled`. Failed records additionally have string `reason`.
V1 view: `{"id":I,"status":S}` plus `value` iff payload present. V1 maps pending
to `pending`, ready to `ok`, failed/cancelled to `error`; it omits generation and
reason. `get` returns `{"record":VIEW}`, or `{"error":"not_found"}`.

## Operations (all versions unless specified)
- `submit`: create pending record at generation 1; optional `payload` is stored
  preserving absence. Existing key returns `conflict` without change.
- `complete`: missing key => not_found. V2 requires `generation`; unequal current
  generation => stale, checked before state. V1 uses current generation. A pending
  record becomes ready with supplied payload (absence removes any old payload),
  unless `reason` is supplied, in which case it becomes failed, stores reason and
  removes payload. Any non-pending state returns conflict, including duplicate
  completion. Successful mutations return `{"record":VIEW}`.
- `cancel`: missing => not_found; pending becomes cancelled and loses payload.
  Already cancelled is an exact no-op, preserving every field (including payload
  in an imported cancelled record); ready/failed => conflict. Generation unchanged.
- `retry`: only failed/cancelled become pending, generation increases by one,
  payload and reason removed. Other states => conflict; missing => not_found.
- `export`: missing => not_found; return `{"stored":STORED}`. V2 STORED is v2
  view plus `schema:2`. V1 STORED is v1 view plus `schema:1` (lossy projection).
- `import`: request contains `stored`. Upsert a validated stored object;
  `stored.id` must equal request id or return `identity`. Schema 2's tenant must
  equal addressed tenant or return identity. Identity failure leaves old data
  unchanged. Schema 1 has `id,status` and optional `value`: migrate pending/ok/error
  to pending/ready/failed, generation 1, preserve value presence, failed reason
  `legacy_error`. Schema 2 has exactly the v2 fields plus schema and preserves
  them. Return record view. Import may overwrite any state and must invalidate
  cached reads. Reimport is idempotent. A schema1 record is adopted into the
  addressed tenant, never a global tenant. Stored inputs satisfy the documented
  schema; schema1 status is pending/ok/error. Failed schema1 may include value.

All mutations immediately affect reads and exports, including reads previously
cached as missing. Errors are always objects with only `error` and the exact
string above. JSON object key ordering is ignored; arrays preserve order.
No response may expose records from other tenants, including errors. All v1
operations above are the compatibility baseline. The v1 starter imports/exports
schema1 only; v2 and schema2 are the migration requirements. Baseline v1 keeps
internal generation for retry but does not expose it.
