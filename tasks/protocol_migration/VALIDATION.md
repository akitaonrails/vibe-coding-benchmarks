# Development validation

This is a compact F4 development instance, not a calibrated frontier-difficulty
benchmark. Difficulty and discriminative power remain unmeasured until independent
pilot runs. Do not infer comparative language performance from references.

`python -m unittest discover -s tests -p test_protocol_migration.py -v` builds all
four native programs and checks:

- Hand-derived null/cancellation/generation and schema1-failure migration anchors.
- Ruby and Rust references against all public cases and private seeds 17 and 932.
- Both starters against every wholly-v1 public case, and consistent v2 rejection.
- Seven executable Ruby reference mutants, each killed by its critical public
  group: incorrect legacy status; missing authorization; tenant-blind identity;
  lost null payload; accepted stale worker generation; stale cache; wrong legacy
  failure migration. These are targeted semantic checks, not a mutation score for
  all possible defects.
- Seed reproducibility and public coverage of metadata critical groups.

The Python oracle is a direct snapshot history model without the native
repository/cache architecture. Cross-language agreement is checked against this
model, with hand-derived anchors. These three implementations are not independent
human authorship; shared misunderstanding remains a limitation. Private inventory
is not agent-visible. Public cases include every requirement class.

Native module boundaries are matched: domain serialization/migration, repository
and cache, worker state changes, service request routing, supplied JSONL adapter.
The v1 starters use unscoped string keys and lack scoped tenant storage and v2
serialization. Domain/view signatures, repository keys, worker completion checks,
and request authorization all require migration. Rust has a concrete Record;
Ruby methods carry equivalent data and documented behavior. The v1 code is
functioning baseline, not TODO-only stubs.
