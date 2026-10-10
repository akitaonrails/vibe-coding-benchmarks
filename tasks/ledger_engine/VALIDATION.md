# Ledger-engine development validation

This integrated maintenance workload replaces neither frozen smoke task. Its
additional difficulty comes from documented interactions between transaction
snapshots, point/range/index predicates, atomic index swaps, scoped identities,
legacy durable schemas, bounded delta journals, torn publication and retry
identity. Code length is not an acceptance criterion and no frontier-difficulty
claim follows from adding features. Independent live calibration is still needed.

The controller oracle is an abstract accepted-history model. It stores logical
committed states and accepted deltas; it decides a fault's acceptance directly
from the documented cut boundary, without replaying serialized journal frames.
It renders inspect output from accepted history. Native references must instead
reconstruct state by replaying their device frames. This separates their central
recovery algorithms, although all authors share the same public specification.

`python -m unittest discover -s tests -p test_ledger_oracle.py -v` verifies:

- Independent, hand-derived outcomes for torn seal versus lost acknowledgement,
  an atomic alias swap with failed intermediate commit, exact durable frame/image
  representations, absent-key tombstone range conflict, and interrupted legacy
  checkpoint publication with durable retry identity.
- Fourteen abstract semantic mutants killed by the public inventory: unscoped
  identity, absent authorization, null removal, missing retry deduplication,
  missing point/write/range/alias conflict checks, lost tombstones, absent unique
  validation, ignored capacity, accepted unsealed journal, early checkpoint
  publication and checkpoint receipt loss.
- Reproducible private histories and a separate working-v1 conformance inventory.

These abstract mutants test semantic inventory adequacy, not native code mutation
coverage. Native authors separately validate their implementations and mutation
checks; do not merge those two evidence categories into one mutation score.

The public inventory contains explicit interacting histories, not merely a long
random test: read conflict across checkpoint; blind-write ABA after delete;
range conflict from deleting an absent key; alias predicate phantom versus an
unrelated write; uniqueness failure followed by an atomic swap; capacity failure
followed by checkpoint and commit using the retained snapshot; null/absence across
replacement and recovery; lost acknowledgement followed by checkpoint and retry;
complete and torn multi-edit journal cuts; legacy migration publication cuts with
old and new retry receipts; conflict precedence over uniqueness and injected
fault; tenant collision and authorization of a known retry ID. Private cases
include these regressions and additional independently seeded combinations.
The private total is therefore not a count of entirely unseen cases.

`baseline_cases()` exports four v1 histories suitable for both starters: ordinary
wire/read/index/journal/recovery behavior; capacity retry after checkpoint;
legacy-image adoption and normal migration; and snapshot-overlay replacement,
delete, abort and read-only commit. Baseline inputs deliberately avoid the
stronger v2 guarantees the task asks the agent to implement.

Native validation on 2026-10-10: both references pass all 43 private cases in the
isolated Docker grader. Ruby also passes all public cases, private seeds 0 and 7,
and all four baseline histories. Rust passes public cases, private seeds 29 and
271, baseline histories, and six compiled executable mutations: missing conflict
validation, missing uniqueness, retry reexecution, premature checkpoint publish,
ignored torn frame and forgotten tombstone versions. These six are distinct from
the fourteen abstract model mutations. Independent cross-review found no material
contract discrepancy; references are evaluator validation, not model outcomes.
