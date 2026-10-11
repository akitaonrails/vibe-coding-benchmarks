# Kimi language/condition effort: bounded trace audit

Interim, 2026-10-11. Read-only inspection of ten closed Kimi attempts: all four Haskell cells, all four Ruby cells, and Rust repetition 2 in both testing conditions. No candidate was executed, patched, tested or contacted. Private results used here were collected after candidate shutdown and have never been fed back to candidates. This is a representative classification of retained commands and output, not an exhaustive reconstruction of reasoning or independent repair episodes.

## Recorded effort and outcomes

All rows use Kimi K3 high. Tokens are provider-inclusive totals with cached input and reasoning already included, not billing or comparable compute units across providers. `Partial` means the complete invocation total is unknown; its observed subtotal must not be ranked as a smaller total. Calls are recorded sandbox tool calls; requests are recorded native model requests, including incomplete responses. Source edits count calls with distinct known before/after source digests, not edited files, defects or iterations.

| Cell | Language / condition | Native requests | Tool calls | Source-changing calls | Inclusive tokens | Active seconds | Outcome |
|---|---|---:|---:|---:|---:|---:|---|
| 6 | Haskell T0 r1 | 11 | 15 | 1 | Partial 280,355 | 900.02 | Transport unsettled; no final artifact |
| 10 | Haskell T1 r2 | 18 | 17 | 1 | 530,096 | 603.02 | Normal handoff; 43/43 |
| 12 | Haskell T1 r1 | 17 | 20 | 2 | 586,490 | 558.70 | Normal handoff; 43/43 |
| 37 | Haskell T0 r2 | 16 | 16 | 2 | 363,326 | 676.98 | Normal handoff; 28/43 |
| 11 | Ruby T1 r1 | 16 | 15 | 3 | 486,291 | 614.28 | Normal handoff; 43/43 |
| 17 | Ruby T1 r2 | 21 | 25 | 2 | 809,346 | 831.09 | Normal handoff; 43/43 |
| 26 | Ruby T0 r2 | 20 | 20 | 3 | Partial 518,764 | 900.02 | Correct deadline snapshot; 43/43 |
| 27 | Ruby T0 r1 | 9 | 10 | 3 known; last call unknown | 168,308 | 638.02 | Tool timeout retires worker; no final artifact |
| 13 | Rust T1 r2 | 19 | 19 | 5 | 714,500 | 801.90 | Normal handoff; 43/43 |
| 34 | Rust T0 r2 | 17 | 20 | 3 | Partial 414,904 | 900.02 | Correct deadline snapshot; 43/43 |

Each cell has one collected invocation and no reactivation nudge. For missing-artifact cells, earlier successful commands do not establish final correctness. Cell 27 stopped before its 900-second maximum because a command's own timeout retired the worker; 638 seconds is not normal completion time. The complete observed model-token count for that attempt does not make its artifact available.

## Haskell: supplied checks versus self-authored checks

The two T1 attempts compiled their implementation on the first recorded build after editing, then passed supplied tests: cell 10 call 13 builds, call 14 passes; cell 12 call 14 builds, call 15 passes. Subsequent calls ran extra scenarios and repeated supplied verification without further submitted-source changes. The inspected outputs show no compiler-error repair sequence in these two attempts. Cell 10 call 12 returned 127 because `which` was missing after GHC had already printed its version; this was shell navigation friction, not a missing compiler.

In T0 cell 6, call 7 changed multiple modules in one command and linked successfully. Call 9's hand-written JSONL contained malformed `"op":"v":2`; the program rejected that input, and call 10 corrected the input file without changing submitted source. This is a fixture-authoring failure, not a compiler failure or evidence of an implementation regression. Later hand-written scenarios ran, but transport settlement failed at the deadline and no final artifact was exported.

T0 cell 37 also compiled on the first build after source changes (calls 8–9). Calls 10–13 fixed the self-authored `/tmp/t/drv.py` expected results: wrong revision/snapshot expectations and a failed-conflict transaction expected to be missing. The helper printed four failures, then one, then PASS. Other helper suites subsequently printed PASS. All these corrections left submitted source unchanged. The independent private result still failed 15 histories. Source inspection in [the semantic failure audit](subscription-semantic-failure-audit.md) identifies the full-publication checkpoint fault path as a likely common mechanism: the helper pass was not proof of contract completeness.

The observed Haskell T1/T0 contrast is informative about these specific attempts: supplied tests were used successfully, whereas self-authored validation both consumed effort and missed a lifecycle rule. It does not isolate a causal test-support effect with two repetitions, and the unavailable T0 artifact prevents treating both T0 attempts as known semantic failures.

## Ruby: validation work does not disappear with dynamic typing

Ruby T1 cell 11 changed source in calls 10–12, with Syntax OK outputs and a supplied-test pass in call 12. Cell 17 changed source in calls 16–17 and passed supplied tests in call 17. Subsequent hand-written scenarios and final checks left source unchanged. No Ruby syntax/interpreter repair sequence was observed in these two T1 traces. Both completed normally and passed private grading, but their elapsed work and request totals differed substantially even within this same language/model/condition.

Ruby T0 cell 26 passed syntax/build checks in calls 7–9, then spent calls 10–21 on Ruby helpers under `/tmp/t`. Calls 10–13 exposed and adjusted misaligned expected responses in `harness.rb`. Calls 15–20 revised a lookup-conflict scenario whose attempted alias insertion violated uniqueness; changing the helper to update the existing matching row made the intended conflict check pass. These are visible helper/input/expectation repairs, with unchanged production source, not observed interpreter errors. Call 21 reported additional passing cases. The deadline snapshot passed all private histories, but there was no normal completed handoff and usage coverage is incomplete.

Ruby T0 cell 27 passed syntax/build checks in calls 7–9 and wrote an interactive Ruby helper in call 10. Call 11 ran its basic scenario and timed out after about 30 seconds with no output, return code -9 and no after-source digest. The worker was retired. This is observed validation-command liveness failure, not a proven application semantic defect; this audit does not diagnose whether buffering, helper I/O or another cause produced the hang. No stale workspace is graded and no additional source edit is inferred from the absent digest.

## Rust: one compiler repair, then helper repairs in the T0 attempt

Rust T1 cell 13 wrote modules in calls 11–14. Call 14's build failed because `Frame` was private while methods exposing it were called from another module. Call 15 changed `enum Frame` to `pub enum Frame`, built and passed supplied tests. This is one directly observed compiler-guided repair sequence, not three independent defects because the compiler emitted three related errors. Later scenarios and a clean rebuild passed without additional source changes.

Rust T0 cell 34 wrote source in calls 9–11 and reported a successful build in call 11. Its later failures arose in Python helpers under `/tmp/t`: calls 14–16 corrected response indices and expected revisions; calls 18–21 corrected another response-index TypeError and journal-frame expectations. Helper output eventually reported ALL PASS for three parts. Submitted-source hashes stayed unchanged throughout those checks. The deadline snapshot passed private grading, while complete invocation usage remains unknown.

This matched repetition-2 pair does not show that supplied tests reduced total tokens: the T0 total is incomplete. It shows an actual visibility/compiler repair in T1, substantial helper repair work in T0, and different terminal outcomes despite both available artifacts passing. One pair cannot establish an average language effect.

## What can and cannot be allocated

The source-changing call IDs are Haskell 6:7; 10:13; 12:13–14; 37:8–9; Ruby 11:10–12; 17:16–17; 26:7–9; 27:7–9; Rust 13:11–15; 34:9–11. Multiple files can be written within one call. Zero further source changes does not mean zero work: building expectations, diagnosing a helper and verifying the artifact are all candidate effort.

This audit separates demonstrated compiler errors from malformed inputs, helper assertion failures, and environment navigation. It does not assign every second or token to these categories. Compound commands mix writing, compilation and tests; pipeline exit codes can mask earlier failure. Supplied-test passes are visible milestones, but neither they nor the last edit establish a measured time-to-private-correctness. Human repair hours and exhaustive repair-cycle counts remain unknown. No human or operator repaired these candidates during this audit.

All ten receipts reside at `results/subscription-matrix/NNNN-kimi-LANGUAGE-CONDITION-rN/result.json`; the complete directory names follow the table's cell number/language/condition/repetition. Call evidence is in `collection.invocations[0].tool_records`, native request/usage records in that same invocation, and process events at sibling `trace/invocation-0.json`. Available snapshots are under `collection/snapshot-0/src`. The earlier [first-eight audit](subscription-first-eight-trace-audit.md) and [semantic audit](subscription-semantic-failure-audit.md) provide committed hash evidence for cells 6 and 37. All findings here remain local analysis, outside candidate context.
