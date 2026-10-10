# Larger ledger task: development calibration

The larger workload still does not establish frontier difficulty. Astra-low with
supplied tests passed all 43 cases at its initial handoff in both Ruby and Rust.
It should remain a calibration candidate, not a basis for general language claims.

| Measurement | Ruby | Rust |
|---|---:|---:|
| Working starter source lines | 319 | 576 |
| Initial generated source lines | 382 | 668 |
| Initial added / removed lines | 72 / 9 | 104 / 12 |
| Source files initially | 6 | 6 |
| Initial private cases passed | 43 / 43 | 43 / 43 |
| Initial active seconds | 79.96 | 79.73 |
| Initial tool calls, including rejected calls | 5 | 6 |
| Initial provider-reported tokens, including cached input | 96,617 | 127,853 |
| Final source lines after two nudges | 382 | 821 |

Rust's final growth includes inline unit tests. Ruby's source hash was unchanged
through both continuations; Rust added tests in its first continuation. Both
remained 43/43 at every checkpoint. Nudges did not rescue either solution.
The observed repair work included timeout-argument correction and Rust formatting;
neither valid initial attempt required a compiler-error repair. Some tool commands
also tried `git diff` in a workspace without Git metadata; those command exits
must not be mislabeled as application failures.

A preceding Ruby attempt was interrupted after 27.30 seconds because the agent
requested a 200-second tool timeout, exceeding the allowed 120 seconds. The old
adapter treated that ordinary argument mistake as a fatal protocol violation.
Its receipt is preserved and excluded from language-correctness conclusions.
The corrected adapter rejects the call without executing it, returns actionable
feedback, and permits a corrected request within the same turn. Identity and
capability violations still stop execution. Both fresh valid attempts encountered
one rejected timeout request and recovered normally. This is tool feedback within
an agent turn, distinct from a generic handoff nudge or a failure-informed repair
campaign.

The valid runs used the same semantic seed, a 900-second initial allowance and
two 180-second continuations. They ran sequentially, with other benchmark builds
and tests paused. There is one valid attempt per language, one semantic instance,
one model/effort configuration and supplied tests only. Provider totals include
cached input and are not billing or normalized compute. No statistical language
ranking follows from these numbers; the nearly identical initial wall time is
also only a single observation per language.

The test is semantically broader than the original migration smoke: conflict
validation interacts with snapshots, tombstones, unique alias swaps, capacity,
durable delta recovery, checkpoint publication, legacy schema adoption and retry
identity. But its required patch remains compact, and both frontier-model trials
passed. This is evidence against promoting it simply because its source is larger.
The default difficulty gate remains closed. Future confirmatory collection needs
independent, calibrated task instances; the real queue track separately tests
concurrency, overload and failures that the JSONL ledger cannot exercise.

[Machine-readable measurements](ledger-calibration-results.json) preserve source
inventories, checkpoint metrics and the failed-attempt accounting without raw
account or session details. See [the source-size audit](difficulty-audit.md) for
count definitions and [the queue experiment](scalability-benchmark.md) for the
separate ecosystem hypothesis.
