# Difficulty correction and source-size audit

The first workload was too small to support the intended frontier-coding comparison. All four `protocol_migration` smoke runs passed all 44 private cases at the first handoff. Nudges did not rescue an initially failing implementation. This is an observed ceiling in four development runs, not evidence that types and tests are equivalent.

The repeatable inventory is [size-audit.json](size-audit.json). Counts cover `src/`, including adapters and any agent-written tests, rather than attributing the entire repository to the agent.

| Language / supplied tests | Starter physical lines | First handoff | Final handoff | First-handoff additions / deletions versus starter |
|---|---:|---:|---:|---:|
| Ruby / T0 | 93 | 111 | 111 | 37 / 19 |
| Ruby / T1 | 93 | 106 | 106 | 27 / 14 |
| Rust / T0 | 64 | 206 | 348 | 191 / 49 |
| Rust / T1 | 64 | 147 | 147 | 114 / 31 |

Each first-handoff implementation has five source files. Rust T0's final growth includes inline unit tests; it must not be interpreted as production-code growth. The inventory marks files containing Rust test attributes as mixed production/tests. It does not pretend to determine exact inline test LOC. Test-path heuristics identify separate test files. Supplied T1 `test_public.py` and `public_cases.json` are outside `src/` and excluded from these source counts.

Physical lines use `splitlines()`; nonblank lines remove whitespace-only lines. Comment-only counts recognize common full-line prefixes and are explicitly heuristic, including possible multiline-string misclassification. Byte counts and source hashes are also recorded. Added and removed lines come from `difflib.SequenceMatcher` against the same-language starter, with unchanged scaffold excluded from the change count. These measures describe the size of the task and edits; they are not cross-language measures of quality or reasoning effort.

## Why the smoke task is insufficient

The migration task exercises several useful properties—tenant authorization, old/new payload compatibility, idempotency, caching and worker behavior—but its implementation fits into a small in-memory service. Forty-four case histories are not forty-four independent tasks. The observed models solved the initial version rapidly, and the supplied Rust baseline itself contains only 64 physical source lines. The crash-store control is similarly compact and has not been established as a frontier task. Both tasks now carry `difficulty.role = smoke_control`, calibration-required metadata and explicit comparison ineligibility.

The replacement `ledger_engine` is a calibration candidate, not a promoted hard benchmark. Its intended difficulty comes from maintaining a working multi-module baseline while coordinating transaction conflict validation, uniqueness/index updates, durable recovery and schema changes. Larger source size alone will not establish that those interactions are difficult for the tested agents. Native references, independent contract anchors and semantic mutants must establish the evaluator before live calibration.

## Evidence gate

`calibration-report` uses first-handoff artifacts and excludes infrastructure-invalid, ungraded and time-censored observations from its complete-outcome count while reporting their exclusions. Such exclusions also block promotion pending explicit analysis. It detects the actual four-of-four initial ceiling in the smoke receipts and returns `frontier_eligible: false` and `comparison_eligible: false`.

The provisional development gate requires at least three reviewed, independently designed semantic instances, two replicates in each language per instance, and at least twelve pooled strong-model observations with both successes and failures at the prespecified initial budget of at least 900 seconds. Different seeds of one workload do not count as independently designed instances. Model, effort, budget and supplied-test cohorts must be analyzed separately. These are minimum screening conditions, not a statistical power calculation or sufficient evidence for a general claim.

The gate deliberately does **not** require Ruby and Rust to have similar success rates: selecting tasks to enforce that would bias the language comparison. Difficulty is assessed on pooled outcomes. LOC is not an eligibility input. Even a passed difficulty screen does not override the separate `scored_benchmark_qualified` requirement; current development results remain ineligible for a scored comparison.

## Reproduction and planning

```sh
python -m langbench size protocol_migration ruby --result results/smoke-ruby-t1/result.json
python -m langbench calibration-report results/smoke-{ruby,rust}-{t0,t1}/result.json
python -m langbench plan > calibration-plan.json
python -m langbench plan --purpose smoke > legacy-smoke-plan.json
```

The default plan targets `ledger_engine` calibration with Astra low, Ruby/Rust, T1 and 900/180-second initial/continuation budgets. Its three repetitions still describe one semantic instance and cannot alone satisfy the independence gate. The previous 48-cell control matrix remains available explicitly through `--purpose smoke` or `--config configs/ruby-rust-pilot.json`. No inference was performed for this audit.
