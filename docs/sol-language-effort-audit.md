# Sol medium: language effort in the closed ledger cohort

Raw receipts referenced below are local historical evidence, not shipped in this repository. See [published measurements and evidence limits](data/README.md).

The closed Sol cohort passed all 43 private cases in all 28 cells at first handoff, with complete native usage accounting and no infrastructure-invalid attempts. No reactivation nudges were needed. This is a task ceiling for this model and setting, not evidence that the languages are equally difficult or that this task discriminates frontier capability.

This audit reads the 12 Ruby, Rust and Haskell T0/T1 receipts, without executing candidates. T0 withheld supplied public tests; candidates could still write their own checks. T1 supplied public examples and a driver. The six representative rows below expose concrete mechanisms rather than rank languages. Authoritative totals are in the reconciled analysis (local receipt: `results/sol-medium-matrix-final/analysis.json`), SHA-256 `4957300c9678b426579498976d695e157c6a6176073258ba73d90d596cad4978`. All 12 inspected result hashes match that analysis.

| Cell | Native tokens | Active seconds | Shell calls / source-changing calls | Submitted bytes / physical lines |
| --- | ---: | ---: | ---: | ---: |
| Haskell T0 r1 (`0002-codex-haskell-T0-r1`) | 219,456 | 86.14 | 11 / 3 | 15,995 / 268 |
| Haskell T1 r2 (`0004-codex-haskell-T1-r2`) | 179,872 | 58.01 | 10 / 3 | 15,833 / 266 |
| Ruby T0 r1 (`0012-codex-ruby-T0-r1`) | 239,545 | 93.96 | 12 / 2 | 12,834 / 381 |
| Ruby T1 r2 (`0008-codex-ruby-T1-r2`) | 127,393 | 68.29 | 7 / 2 | 12,777 / 383 |
| Rust T0 r1 (`0019-codex-rust-T0-r1`) | 176,671 | 96.29 | 9 / 2 | 21,110 / 597 |
| Rust T1 r1 (`0025-codex-rust-T1-r1`) | 241,383 | 92.83 | 12 / 4 | 22,077 / 675 |

Each artifact has six source files. Sizes cover submitted `src`, including any helper content there; physical lines are not production-only complexity. Source-changing calls compare editable-tree hashes before and after a command. They include formatting and warning cleanup. Shell calls, changes and tokens are not iteration counts. Native provider totals are observed token usage, not equivalent compute, billed cost or human labor.

## What actually needed repair

**Haskell:** T1 r2's first build failed because `Table.version` was unavailable through an import that hid `version`. The next source-changing command repaired the import and built successfully; the public driver then passed. A later change removed a name-shadowing warning. This is a concrete compiler-guided name-resolution repair, not evidence that the compiler caught a ledger semantics defect. T0 r1 similarly spent changes removing unused imports and shadowing warnings after implementation. Its hand-authored assertions checked alias changes, retries, checkpoint cuts, migration, conflicts and capacity. Three changing calls therefore do not mean three failed semantic implementations.

**Ruby:** T0 r1 changed production source twice, then repaired its own checks without further source changes. One helper expected 11 journal frames; its replacement expected 12 and passed. Another changed a frame expectation from 9 to 11 and corrected which engine instance was crashed in a migration check. A capacity/alias-swap helper was subsequently revised to expect a four-frame commit to fit capacity four. These are visible test-authoring corrections, not candidate fixes. Some failed assertions were followed by `./build.sh`, leaving the overall shell return code zero: counting only nonzero commands misses this work. In T1 r2, supplied public tests passed before an additional helper expected 11 rather than the observed 13 journal frames. A later focused helper passed without source changes. Passing private grading supports final correctness but does not retroactively validate every discarded helper.

**Rust:** T1 r1 ran `cargo test --offline`, which compiled a test executable and reported **zero tests**. The public driver then failed `working_v1`. Reading the scripts and running `./build.sh` produced the normal binary and made the driver pass without a source change. The evidence supports a build-artifact workflow correction, not a ledger algorithm repair. Later `cargo fmt --check` failed; formatting accounts for another source-changing call. T0 r1 also ran a zero-test Cargo suite alongside manual protocol checks. No Rust compiler-error repair was observed in the four inspected Rust attempts; that observation is limited to this sample.

## Verification and interpretation limits

Several attempts tried unavailable `rg` or `git`; `find` or separate checks followed. An `&&` chain stopped by missing Git can skip the intended test. These are environment/tool-use mistakes, separate from language errors. The inspected event text contained no observed JavaScript parse-error mechanism. Unlike the Opus audit, no Claude OAuth preflight-429 delays belong to these Codex receipts; timing mechanisms must not be transferred between providers.

The traces show compiler assistance, helper repair and verification choices consuming different kinds of effort. They do not isolate typing strength causally. Two replicates, one successful task and the complete correctness ceiling leave little power to distinguish language effects. More discriminating independent tasks are needed before interpreting token or elapsed-time differences as diminishing returns from stronger typing.
