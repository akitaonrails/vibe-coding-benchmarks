# First eight subscription attempts: representative trace audit

Interim, 2026-10-11. This is a bounded read-only inspection of the first eight consumed cells, not an exhaustive annotation or language ranking. No candidate was rerun, repaired or graded during this audit. The eight result hashes match `matrix.json`; the six available snapshot hashes and their graded source hashes also match. Source-changing call counts require both before/after digests: a missing after-digest is unknown, not a change.

All evidence below is under `results/subscription-matrix/`. For each named cell, tool call IDs refer to `result.json → collection.invocations[0].tool_records`; terminal/process evidence is in `trace/invocation-0.json`. Saved sources, where available, are in `collection/snapshot-0/src`. None of these eight attempts received a reactivation nudge. Token totals and full timing tables belong in the analyzer; this note identifies kinds of work that aggregate totals obscure.

## Outcomes and observable source changes

| Cell | Model / language / condition | Terminal interpretation | Final private evidence | Source-changing call IDs | Saved src bytes / lines |
|---|---|---|---|---|---:|
| 0001 | GLM / Ruby / T1 r1 | Deadline, no normal completed handoff | Correct saved artifact | 19, 20, 21 | 14,869 / 444 |
| 0002 | GLM / Haskell / T0 r1 | Model output limit; raw parser label infrastructure-invalid retained | Unchanged starter failed | None | 14,239 / 239 |
| 0003 | Kimi / TypeScript / T0 r2 | Normal handoff with COMPLETE | Correct saved artifact | 9, 10 | 15,273 / 308 |
| 0004 | GLM / Haskell / T1 r2 | Deadline, no normal completed handoff | Correct saved artifact | 17–21 | 17,456 / 313 |
| 0005 | GLM / Haskell / T1 r1 | Normal handoff with COMPLETE | Correct saved artifact | 20–23, 42 | 17,869 / 341 |
| 0006 | Kimi / Haskell / T0 r1 | Deadline with transport settlement failure | No final artifact or grade | 7 | Unknown |
| 0007 | GLM / TypeScript / T0 r1 | Model output limit; raw parser label infrastructure-invalid retained | Unchanged starter failed | None | 12,738 / 247 |
| 0008 | GLM / Kotlin / T1 r1 | Deadline during tool execution; worker retired | No final artifact or grade | 18–21; call 35 lacks after-digest | Unknown |

The full cell names are the directory names listed in the evidence inventory below. Lines count saved `src` files using byte-line splitting, including blanks/comments; these are descriptive artifact sizes, not effort, quality or production-only LOC. For each available artifact the last known tool source digest matches the graded source. That establishes continuity to the saved artifact, not the time the agent knew it was correct. Missing final artifacts are not replaced with an earlier controller workspace.

## Representative mechanisms

### Implementation work and supplied-test feedback

Ruby cell 0001 first ran the supplied tests at call 10: output contains `AssertionError: tenant_auth_retry_scope`. The compound pipeline returned zero despite that assertion. Calls 19–21 wrote implementation modules; call 21 reports `Public cases passed`. This supports a baseline failure → implementation → public pass sequence. It does not support counting each source-writing command as a distinct defect repair.

Haskell cell 0004 likewise showed the baseline `tenant_auth_retry_scope` failure at call 16. Calls 18–20 exposed real compiler feedback: a hidden `Table.version` qualified name, argument-type mismatches around device functions, then unavailable `B.getLine` after rewriting Main. Calls 19–21 changed submitted sources to address these; call 21 linked and passed public cases. This is observable compiler-guided implementation repair. Whether those diagnostics reduced total reasoning or prevented later semantic mistakes is not identified by this trace alone.

Haskell cell 0005 call 22 lacked imported Aeson `Object`/`String` constructors; call 23 changed `Value` to `Value(..)` and linked successfully. Call 24 passed the supplied tests. Its later call 42 changed the implementation again, removing a redundant `ident` binding and using `identity` directly. That is an observed source cleanup, not evidence of another repaired semantic failure. The printed `build rc=1` is the status of `grep` filtering warnings/errors in a pipeline; subsequent public and custom checks passed. It must not be counted as a compiler failure without inspecting the command.

Kotlin cell 0008 call 20 failed compilation because `Pair<BeginFrame,List<Frame>>` did not match `Pair<BeginFrame,List<EditFrame>>`. Call 21 changed the edit list mapping to explicit `EditFrame` casts and reported BUILD_OK; call 22 passed supplied public tests. Record the type error and chosen cast repair faithfully. A language label alone does not establish that the implementation exercised its strongest available static guarantees.

T1 supplies executable examples and expected results. These agents also read selected public histories before editing. That is legitimate treatment feedback, not private-grader leakage. A passing public check alone is weaker evidence than the independent final private grade.

### Self-authored helpers can account for substantial further debugging

Ruby cell 0001 calls 22–37 left submitted-source hashes unchanged while creating and modifying `/tmp/t/extra_cases.py`, `extra2.py` and `fuzz.py`. Call 22 exposed Python syntax errors; calls 25–33 adjusted helper code and expected histories; call 33 reported 26/26 extra cases. Calls 34–35 moved another helper from 5/8 to 8/8. Calls 36–37 repaired the fuzz driver's missing initial `init` request and moved its report from three mismatches to none. These are model-authored verification/helper repairs, not further Ruby implementation edits or human assistance. Passing the agent's own checker is not independent proof that its expectations are valid.

TypeScript cell 0003 had no supplied tests (T0). It changed source in calls 9–10 and reported BUILD_OK. Its JavaScript helper in `/tmp/t/test.js` initially compared JSON through string serialization; call 12 changed the comparison to normalize object keys and reported 221 checks with zero failures. Calls 13–14 created and corrected a second helper, which reported 158 checks with zero failures. Calls 15–16 rebuilt and verified without source changes, then the agent handed off COMPLETE. Both compiler use and self-authored helper repair are visible; T0 means no supplied test suite, not a prohibition on testing.

Haskell cell 0004 calls 22–33 largely changed `/tmp/lt/mytest*.py` while submitted sources stayed stable. Failures included omitted tenant/actor fields, transaction ownership expectations, missing expected snapshot responses and v1/v2 projection assumptions. The fixes occurred in the helpers, followed by reported passes; this distinction is supported by command paths and unchanged source hashes, not just the agent's commentary.

Haskell cell 0005 calls 33–39 exposed helper syntax errors, response-index errors, a comparison including deliberately different active-transaction counts, and incorrectly nested expected commit results. Call 36's assertion even printed identical observed/previous commit dictionaries while constructing a different expected shape. Call 37 reported 40 stress workloads passing after helper edits. These errors would be badly misattributed if every failed Python command were counted as a Haskell production-code failure.

Kotlin cell 0008 calls 23–34 developed a Python oracle and fuzz/edge helpers under `/tmp/fuzz`. Calls 24–29 repaired an unterminated string in the oracle. Call 32's edge expectation omitted the tenant from a stored journal EDIT row; call 33 corrected the helper expectation, then reported all edge tests passing. Public inspection semantics distinguish stored durable rows from v1 wire projection. The submitted source remained unchanged through these completed helper calls.

### Output limits and missing artifacts are different mechanisms

Cells 0002 and 0007 only read files and did not change submitted source before model output-length stops. Their SHA-bound records in `outcome-overrides.jsonl` preserve the raw parser errors while classifying `model_output_limit`. The saved starters failed grading. This is known consumed model effort and known unchanged-artifact evidence; it is not proof that the languages were unimplementable, nor a missing infrastructure sample. See [the operational audit](subscription-matrix-operational-audit.md).

Cell 0006 did implement and compile Haskell in call 7, then ran hand-written JSONL scenarios. Call 9 contained malformed JSON (`"op":"v":2`); call 10 corrected the input without changing source. The deadline ended with an unsettled transport; the receipt explicitly marks `artifact_available:false` and contains no grades. Visible output supports implementation/checking activity, but cannot establish final correctness or final size. Do not grade the stale host workspace to fill that gap.

Cell 0008 used roughly 1.4 million inclusive provider tokens, but still has no final grade. Its last call 35 launched more self-authored fuzzing and ended with return code -9, `termination:timeout`, after about 19.47 seconds. It printed one profile's 150 passing cases before termination, and lacks a post-call source digest. The invocation reports `candidate_worker_retired; final source unavailable`. Its raw `valid_development` label must not be presented as successful completion or available correctness evidence. Earlier public/fuzz passes and the last known source hash are retained observations, not a replacement final snapshot. The contrast with correct deadline snapshots in cells 0001/0004 is a collection-boundary distinction, not evidence that Kotlin's submitted implementation was wrong.

## Reporting implications

Use separate categories for implementation changes, compiler repairs, supplied-test checks, helper repairs, verification, and tool/environment navigation. `which` was unavailable in some calls despite working compilers discovered with `command -v`; this is shell-tool friction, not missing language support. Compound commands can hide earlier failure or print a filter's status as a build status. Counts from the conservative analyzer are lower bounds and need the trace examples above for interpretation.

These eight cells contain two normal correct completions, two correct deadline snapshots, two output-limit unchanged failures, and two unavailable final artifacts. They are neither a balanced completed factorial comparison nor eight independent language problems. No causal ranking of languages, typing strength or test support follows. Self-authored helper debugging is candidate effort; no measured human repair took place, and required human hours remain unknown.

## Committed evidence inventory

All paths below have the prefix `results/subscription-matrix/` and suffix `/result.json`. Each also has `trace/invocation-0.json`; available artifacts have the snapshot path given above.

| Cell directory | Result SHA-256 |
|---|---|
| `0001-opencode-ruby-T1-r1` | `c230804b83af13379c13edfcebc6d0025ad9cd67297cb6c6eb8b345fca4cd745` |
| `0002-opencode-haskell-T0-r1` | `73c9ec28c00ec4e2182aa473f47ba57885090c671a292f64b1b11fe4f190c838` |
| `0003-kimi-typescript-T0-r2` | `008c64a8d8c7292e0c9863f8d05d3c1b6a925e90b97fecd60c2c87461c1069c5` |
| `0004-opencode-haskell-T1-r2` | `9393c888f86f7d59d3ef9d714e8b52ec2164b68711a16bbc201a56b71e6a5a62` |
| `0005-opencode-haskell-T1-r1` | `9952b633bae375fb09a6f2485c844d2679f70262f3a9b4c0f5dce308ecb1c6fb` |
| `0006-kimi-haskell-T0-r1` | `ac1c5ad734cee88086b7c63168167200cfea3fb2a5751439f8999431ac258b04` |
| `0007-opencode-typescript-T0-r1` | `b33a4a64eb45f355255ecacb9c36d219bad9d500129de3ca569bceb6a9f6874e` |
| `0008-opencode-kotlin-T1-r1` | `d12b54930650b1eb807f856f0b7b31dcff73b883a345a80f5b2043c1b0aaffe5` |
