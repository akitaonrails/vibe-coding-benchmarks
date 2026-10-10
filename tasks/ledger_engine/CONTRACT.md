# Transactional ledger maintenance task, version 2

Implement this complete contract in the supplied native language. Keep ledger
business logic in that language; do not delegate it to another interpreter or
external program. Standard libraries and the supplied dependencies are allowed.
The supplied v1
baseline is functioning, but lacks scoped identities, serializable validation,
unique-index validation, fault-safe journal recovery and durable retry tracking.
Only `src/**` is submitted. The JSONL adapter reads one object and emits one object
per line; requests within one test share a process, and each case starts fresh.
Object-key order is ignored. There are no threads, clocks or external services.

## Values, identity and errors

IDs, tenants, aliases, transaction handles and commit request IDs are nonempty
ASCII strings of 1..24 characters from `[A-Za-z0-9_:-]`. Ordering is ASCII byte
lexicographic; scoped keys are tuples `(tenant,id)`, never concatenated strings.
All integers are exact signed integers within ±1,000,000,000, with revisions and
frame counts nonnegative. Tests remain within these bounds. `value` is required
on a put and is an integer. `alias` is optional and may be a string or null;
only strings enter the unique secondary index. `note` is optional and may be any
JSON value (integers obey the bound). Preserve absent versus explicit null in
both optional fields. Returned records are `{"tenant":T,"id":I,"value":N}`
plus alias/note iff present. V1 records omit tenant. Never expose internal versions.

Every ordinary operation has optional `v` (1 or 2; default 1). V1 implicitly
addresses tenant `legacy` and ignores tenant/actor fields. V2 requires `tenant`
and `actor`; authorization requires exact equality, before any handle/key lookup.
A mismatched actor returns `{"error":"forbidden"}`. Transactions have one owner
tenant. Using an existing handle from another authorized tenant returns
`{"error":"transaction_owner"}`; no other handle information is returned.
`init`, `crash`, `checkpoint`, `stats` are administrative operations without v or
actor. All other errors are exactly `{"error":CODE}`. Malformed requests and
out-of-bound inputs are outside grading. Inputs satisfy all documented shapes.

State starts empty, revision 0, journal capacity 64 frames. `init` with `capacity`
(4..512) resets all volatile and durable state and returns `{"ok":true}`; it is
used only as the first request. There are at most 1000 distinct keys, 64 live
transactions, and 1000 successful commit IDs per case. No expiry or eviction.

## Transactions and reads

- `begin` with `tx`: duplicate live handle => `transaction_exists`. Otherwise
  capture a full logical snapshot at current revision, create empty tracking sets,
  and return `{"snapshot":R}`. A handle can be reused after commit/abort/crash.
- `read` with `tx,id`: returns `{"record":RECORD_OR_NULL}` from staged writes
  overlaid on the begin snapshot. Track the key's *snapshot version*, even when
  reading a staged value or an absent row. Never implicitly read current state.
- `scan` with `tx,lo,hi`: closed-open ID interval `[lo,hi)` within owner tenant,
  including staged writes/deletes. Return `{"records":[...]}` sorted by ID.
  Track the snapshot's complete key-version map for that interval, including
  tombstones; a later insertion, deletion or rewrite anywhere in it conflicts.
  Empty/inverted intervals (`lo >= hi`) read nothing and track no range.
- `lookup` with `tx,alias`: returns `{"records":[...]}` sorted by ID from the
  overlaid snapshot whose string alias equals the supplied alias. Staged duplicate
  aliases are visible as multiple records before commit. Track the snapshot map
  of *live matching* IDs to versions; later changes to this matching set or its
  row versions conflict. Changes to unrelated aliases do not conflict.
- `put` with `tx,id,value` and optional alias/note replaces the entire row in the
  transaction overlay, dropping absent optional fields. Return `{"ok":true}`.
- `delete` with `tx,id` stages absence, even if already absent; return ok.
- `abort` with `tx`: discard transaction and return ok.

Every operation above except begin requires a live handle: missing =>
`transaction_missing`. After ownership checks, no other errors occur for
read/scan/lookup/put/delete/abort. Each committed write, including same-value put
or deleting an absent key, gets the new commit revision as its version. Keep
version tombstones for absent keys; a never-written key has version 0. Writes
always validate against the version in their begin snapshot, even if not read.
Read-only transactions may commit and still advance revision (see below).

## Commit, conflicts, uniqueness and retry identity

`commit` has `request` (commit ID), optional `tx`, optional `fault` as defined
below. Commit IDs are scoped by owner tenant. Error/check precedence is:

1. Authorization, as for every ordinary operation.
2. Durable successful commit ID lookup. If present, return the exact prior
   `{"committed":R}` without requiring a handle, inspecting fault or changing
   any state. Even if tx names an unrelated live handle, leave it untouched.
3. Missing handle, then ownership, as above. An absent tx is a missing handle
   unless an existing receipt already resolved the request.
4. Validate point reads and every staged write against current key versions.
   Validate tracked scan maps and lookup maps against current state. Any mismatch
   => `conflict`. Validation uses the begin snapshot, not a later read time.
5. Overlay *all* staged writes atomically on current rows. String aliases must be
   unique within each tenant in this proposed final state, or return `unique`.
   Thus two-row alias swaps succeed and conflicts take precedence over uniqueness.
6. Required journal frames = number of distinct staged IDs + 2. If current
   complete journal frames + required frames > capacity, return `capacity`.
7. Journal the delta, publish it, advance global revision by exactly one, record
   the scoped commit ID, remove the transaction, and return `{"committed":R}`.

A normal successful commit is durable. `conflict`, `unique`, `capacity` and all
lookup/authorization errors leave transaction, rows, revisions, journal and retry
tracking unchanged; the caller may edit and retry the same transaction/ID.
A failed commit does not reserve its request ID. Transaction handles are global
strings, but durable request IDs are tenant-scoped. The same request in two
tenants may commit independently. Revision is global across tenants.

## Logical stable device, journal and crash cuts

The task supplies a logical device API in its native modules. Candidates may
change implementation modules but must preserve these externally checked rules.
This is not a real filesystem benchmark. Persistent journal entries are delta
frames, and a commit consumes exactly `K+2` frames for K staged IDs:

1. One BEGIN frame containing owner tenant, request ID, proposed revision and K.
2. K EDIT frames in ID order, one per staged ID, storing the complete replacement
   row or a deletion marker. This is the only commit row storage.
3. One SEAL frame committing that BEGIN and all its EDIT frames together.

Implement recovery by scanning complete BEGIN/EDIT/SEAL groups after the current
checkpoint. No whole-database snapshot per commit or hidden durable shadow rows:
only the published checkpoint plus journal frames survive a crash. The v2 logical
device serialization must obey the schema below and is exposed by `inspect`.
A valid SEAL makes the entire group, its revision and retry identity durable.
An incomplete or torn group makes none of its edits durable. Recovery discards
the incomplete suffix, releases its journal space, and clears all transactions.

`commit.fault` is `{"keep":N,"tear":BOOL}`, where N is 0..K+2 and tear may be
true only when N>0. It persists only the first N proposed frames. If tear is true,
the final retained frame is replaced by `{"kind":"TORN"}`. Then it immediately
crashes and recovers and returns `{"error":"interrupted"}`. This occurs even
when all frames survived and seal was valid: commit may be durable despite a lost
acknowledgement. The caller can resolve that through commit-ID retry. Failed
validation/uniqueness/capacity checks happen before faults and do not crash.
`crash` discards all volatile state and recovers durable state; returns
`{"recovered":R}`. Repeated recovery is idempotent. Reuse of a cleared handle
returns transaction_missing unless a commit-ID retry already resolves it.

## Checkpoints, migration and inspect

`checkpoint` creates an image of current committed state and durable retry IDs.
A checkpoint requires exactly two logical publication writes: image then publish.
Default success publishes schema2 image, clears the journal, returns
`{"checkpoint":R}`, and does not invalidate active transactions or snapshots.
Optional `fault:{keep:N,tear:BOOL}` uses N in 0..2 and tear only when N>0:
only N=2 with tear=false publishes the new image and clears the journal; otherwise
the previous checkpoint/journal remain authoritative. Every fault crashes,
clears transactions and returns interrupted. Crash never publishes a staged image.
Checkpoint works even when the journal is full and also at revision 0.

`inspect` is an ordinary authorized operation without tx. Return
`{"checkpoint":IMAGE,"journal":[FRAMES...]}` containing only the addressed
 tenant's rows/tombstones/receipts and journal groups, while preserving global
revision values. IMAGE uses schema2 after any successful checkpoint and schema1
only after legacy loading. Initially it is schema2 revision0 with empty lists.
This operation exposes the exact logical durable representation, making journal
shape, tombstones, delta storage and checkpoint publication testable.

Schema2 IMAGE:
`{"schema":2,"revision":R,"entries":[{"tenant":T,"id":I,"version":V,"row":ROW_OR_NULL}],"receipts":[{"tenant":T,"request":Q,"revision":V}]}`.
Entries sorted by (tenant,id), receipts by (tenant,request). ROW is the full v2
record, including tenant/id. Entries include tombstones. Each v2 BEGIN is
`{"kind":"BEGIN","tenant":T,"request":Q,"revision":V,"count":K}`;
EDIT is `{"kind":"EDIT","id":I,"row":ROW_OR_NULL}`; SEAL is
`{"kind":"SEAL","revision":V}`. Inspect filters complete groups by BEGIN
owner. All exposed journals are complete because faults immediately recover.
V1 inspect still returns the durable schema as stored, not a lossy v1 projection.

`load` is ordinary, authorized, with `image` containing a schema1 image. It is
permitted only in globally pristine state: revision0, no live transactions, empty
checkpoint entries/receipts and empty journal. Otherwise return `not_empty`.
Schema1 IMAGE is `{"schema":1,"revision":R,"entries":[{"id":I,"version":V,"row":ROW_OR_NULL}],"receipts":[{"request":Q,"revision":V}]}`.
Legacy ROW is id/value plus optional alias/note. Images are valid: sorted unique
IDs/requests, 0<V<=R, unique live string aliases; R may be zero only for empty
lists. Load adopts all IDs and receipts into the addressed tenant, persists the
unchanged schema1 image plus its owner in the device, and returns `{"loaded":R}`.
The owner is device metadata, not part of the inspect image. Other tenants see
schema1 image with same revision but empty entries/receipts. Recovery transparently
interprets legacy entries/receipts under that owner without modifying the image.
New commits append schema2 delta groups. The first successful checkpoint performs
schema1->2 migration; interrupted publication must preserve the old authoritative
image, journal and adopted retry identity. Loading an already loaded empty
schema1 image counts as non-pristine (not_empty), even if R=0.

`stats` returns `{"revision":R,"journal_frames":N,"capacity":C,"transactions":H}`.
Reads never consume frames. There is no automatic checkpoint/reclamation or
implicit retry-ID eviction. Journal capacity covers frames only; checkpoint
images have no capacity cost. All persistence/fault behavior is fully observable
through recovery, retry, inspect and stats, not through host disk access.

## Functioning v1 baseline and migration surface

The starter supports v1 with default tenant legacy: init, begin, read, scan,
lookup, put, delete, abort, commit, crash, checkpoint, stats, inspect, load.
It implements snapshot overlays, absent/null fields, revision/tombstone tracking,
normal journal/checkpoint schemas and legacy-image adoption. Normal v1 commits
apply deltas and respect capacity, but do not validate conflicts or uniqueness;
request IDs are recorded but retries are not deduplicated. Fault parameters return
`unsupported_fault` after handle/ownership checks, without mutation. V2 requests
return `unsupported_version` before any work. This intentional subset is tested
only with legal unique/no-conflict histories without faults or repeated commits.
Baseline normal crash replays complete groups and clears handles; load/checkpoint
normal migration already works. The requested migration adds guarantees across
wire authorization, identity, transactions, secondary indexes, device publication,
recovery and retry receipts; it must preserve the functioning v1 subset while
applying the complete target guarantees to v1 as well as v2.
