# Development validation and limitations

The Python history oracle retains an append-only version history with snapshot
handles pointing to version indices. Native references instead keep current
maps plus copied snapshot maps and page lists. Neither imports or executes the
other implementation. Exact JSON output is compared after every request.

Public tests expose every operation and each publication boundary; private
seeded traces combine duplicate updates, deletion, Unicode, empty writes,
capacity pressure, snapshots, stale handles, partial reclaim, crashes and
publication cuts. A small hand-derived test independently checks the crucial
page-write/publication boundary. Both Rust and Ruby run the same full traces.

`tests/test_crash_store.py` executes six native Ruby semantic mutants: premature
publication, acknowledged data loss, reclaiming snapshot-live pages, never
reclaiming, stale-handle aliasing, and ignoring capacity. Each must be rejected.
These are genuine algorithm mutations, not deliberate output corruption.

Group labels identify the trace's emphasis; this compact development suite has
overlapping coverage and some shared public lifetime traces. It is not evidence
of independent group-level statistical power. References, private seeds and
this mutation source must never be mounted inside candidate environments.

This task intentionally starts below the proposed full F1 difficulty: logical
atomic page writes, deterministic cuts, no byte-level checksum format, no host
fsync, no migrations, and no real process restart of persisted bytes. It tests
modeled crash semantics, not OS durability. Calibrate separately before adding
scored frontier claims or interpreting language/model differences.
