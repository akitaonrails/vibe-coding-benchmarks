# Effort analysis follow-ups after collection

Prepared 2026-10-10 during the frozen subscription matrix. This is one bounded,
read-only review of `langbench/effort_report.py`, the
[matrix effort protocol](matrix-effort-protocol.md), and the first two completed
receipts. Only this analysis-preparation document was written. No frozen code,
fixtures, configuration or receipts changed; no tests, builds, probes or model
calls were run. These are proposed post-collection reporting changes, not a
reopened provider qualification gate or instructions to the active agents.

## Two receipts already show why separate dimensions matter

| Attempt | Collection outcome | Saved artifact | Recorded work |
|---|---|---|---|
| `0001-opencode-ruby-T1-r1` | Timeout after 900.043 seconds; no normal completed handoff, no nudge | Private grading passed; last observed source-changing call's hash equals graded source hash | 36 tool calls; three source-changing calls; 31 provider requests; 1,740,768 inclusive provider tokens |
| `0002-opencode-haskell-T0-r1` | Raw infrastructure-invalid label; independently diagnosed clean CLI exit with model output-length stop after 460.796 seconds; no completed handoff or nudge | Unchanged starter artifact failed grading; valid observed effort and artifact evidence | Five tool calls; five provider requests; 49,846 inclusive provider tokens |

Receipt commitments at inspection:

- Ruby: `c230804b83af13379c13edfcebc6d0025ad9cd67297cb6c6eb8b345fca4cd745`.
- Haskell: `73c9ec28c00ec4e2182aa473f47ba57885090c671a292f64b1b11fe4f190c838`.

Paths are under ignored `results/subscription-matrix/<attempt>/result.json`.
The [operational audit](subscription-matrix-operational-audit.md) independently
establishes Haskell's clean exit and complete `step_finish` event with reason
`length`. Its final request reported 32,000 output tokens, including 31,997
reasoning tokens. The frozen parser misclassified that legitimate terminal event
as infrastructure-invalid. Preserve that raw label alongside the SHA-bound
`model_output_limit` analysis override in `outcome-overrides.jsonl`. The attempt
provides valid known effort and an unchanged, failing artifact; it is not missing
language evidence or an established infrastructure interruption. The precise
configuration origin of the output cap remains inferred, as the audit explains.
Ruby produced a correct saved artifact at timeout without finishing normally.
Neither outcome should be renamed to suit a success/failure headline. These two
cells differ in language and test treatment and alone support no language comparison.

## 1. Separate stopping behavior from artifact correctness

Current per-attempt rows retain invocation status in `handoffs`, but summary
`first_handoff_successes` counts a true initial grade even when the checkpoint was
created at timeout or infrastructure failure. The first Ruby receipt therefore
looks like a successful first handoff in the summary although there was no such
handoff. Final checkpoint correctness is likewise distinct from normal completion.

Post-collection, publish independent columns:

- Raw and analysis `collection_terminal_status`: normal handoff, timeout, model
  output limit, quota, infrastructure error or interrupted/unknown; alongside
  validity, override provenance and actual elapsed work. A clean process exit
  with a length stop is distinct from a completed coding handoff.
- `declared_status`: the exact COMPLETE/INCOMPLETE/BLOCKED interpretation, including
  unknown; declaration is not correctness.
- `initial_artifact_correct` and `final_artifact_correct`, plus grade validity and
  checkpoint index. Keep a missing final grade unknown.
- `completed_normally_and_correct`, `correct_at_timeout`, `incorrect_at_timeout`,
  `model_output_limit_with_artifact`, and
  `infrastructure_interrupted_with_artifact` as derived categories. Output-limit
  artifacts retain their actual correctness and known effort; the raw parser
  label does not by itself exclude them from valid analysis.

Keep planned-cell denominators, observed valid-attempt denominators and graded
artifact denominators explicit. Report all attempts first, then any clearly
labeled conditional comparison. Do not turn invalid cells into successful samples
or silently delete their consumed effort. Existing `last_graded_*` fields remain
useful when later grading is unavailable.

## 2. Distinguish source stability, visible verification and completion

Ruby's source-changing calls were 19, 20 and 21. Call 21's `source_after` equals
the private grade's `source_sha256`; subsequent recorded calls did not change that
hash. Call 21 also emitted `Public cases passed`. Later work created and repaired
self-authored Python checks under `/tmp/t/`. At timeout the model was still
checking a fuzz harness; call 37 reported no mismatches. This demonstrates
additional verification work after the final observed submitted-source change.
It does not establish that the agent knew private correctness earlier.

Useful post-collection fields are last observed submitted-source change,
first visible supplied-test pass for that source, last visible check, and normal
handoff/deadline. Derive a **retrospectively final source** milestone only when its
hash matches the immutable graded source and no later source evidence is missing.
Label it retrospective, not time-to-proven-correctness. Do not subtract remaining
verification or model reasoning time from total measured effort.

Timing limits matter: tool `started_at` is wall time; command `seconds` is
monotonic execution duration and excludes some surrounding source-hash/export
work. The first provider request is not an exact invocation start timestamp.
Use bounded intervals or clearly named offsets from the first recorded request,
not fabricated precise edit-completion times. Temporary helper files are not in
submitted-source hashes and may not survive worker teardown. Their commands and
bounded outputs, rather than complete final files, may be the only evidence.

Preserve existing preparation, collection/cleanup, private-grading and total
attempt timing separately. Compilation/check runtime inside an agent tool call is
candidate effort; offline private grading and benchmark setup are controller cost.
No per-request token cost should be assigned to an exact code-edit milestone
without unambiguous timing and request-coverage evidence.

## 3. Split implementation repairs from testing and tool friction

The present conservative classifier recognized zero checks in both receipts.
Ruby has 36 unclassified commands because they are compound shell commands,
here-documents or custom checks. Its zero observed repair cycles is consequently
an instrumentation lower bound, not evidence of zero debugging or effortless
implementation. A raw nonzero exit is also not automatically a program failure:
`ruby -v; which ruby` ended nonzero although later Ruby builds/checks succeeded.

Add a reviewed, versioned classification layer after collection, preserving raw
call IDs, command/output evidence and confidence:

| Category | Evidence required | What must not be inferred |
|---|---|---|
| Submitted implementation revision | Before/after source digest change; source path/body evidence when available | Every edit was a defect repair |
| Implementation compile/type repair | Identifiable compiler failure, relevant source change, subsequent identifiable check | A compound shell's final zero means its earlier build passed |
| Implementation semantic repair | Credible supplied/self-authored failing assertion, implementation change and subsequent check | Every self-authored expected value is correct |
| Self-authored test/helper repair | Commands modify helper/model/expected data while submitted-source hash remains stable | Time spent fixing a Python test helper is Ruby production-code debugging |
| Tool/environment navigation | Shell/path/argument evidence, such as an absent convenience command | The language compiler/runtime was unavailable |
| Verification without implementation edits | Checks or helper changes after unchanged production-source hash | Those checks are redundant, or private correctness was already known |
| Unknown/mixed | Insufficient output, combined steps, missing source hashes | Confident allocation of all time/tokens to one category |

Ruby's later transcript explicitly describes correcting its own test expectations
and a missing `init` in its fuzz driver, with stable submitted source. Treat those
as candidate-authored verification work where supported by command/output evidence,
not operator repairs. An independent analyst may reject an agent's claim about
what went wrong; narrative self-report alone is weaker evidence than executed
commands and hash continuity.

Avoid loosening the current check classifier into a substring detector. Retain
its conservative counts, publish classification coverage, and provide reviewed
annotations separately. A manual annotation audit is benchmark-analysis work,
not manual work needed to fix the candidate application.

## 4. Report token components and their scope

The first two receipts have complete native request coverage and provider totals,
while CLI-normalized totals are unknown. Those are separate facts, not a parser
failure that should erase available native evidence.

| Attempt | Input including cached | Cache-read subset | Output including reasoning | Reasoning subset | Provider total |
|---|---:|---:|---:|---:|---:|
| Ruby T1 | 1,682,080 | 1,578,816 | 58,688 | 28,911 | 1,740,768 |
| Haskell T0 | 17,616 | 9,536 | 32,230 | 32,077 | 49,846 |

Cache-write values are unknown in both. Cache reads are already inside input;
reasoning is already inside output. Never add either subset again. Cache reuse
and large repeated context can inflate inclusive tokens without corresponding to
equivalent newly generated work or subscription billing. No dollar-cost claim
follows from these totals.

The report currently preserves nested usage records but its summary mainly shows
provider totals. Add per-attempt component totals with completeness/coverage,
request count, known partial subtotal and exact mapping provenance. Include
initial, each actual continuation, and cumulative totals. Do not convert missing
components to zero or distribute a request's reasoning tokens among tool actions
by guesswork. Compare token patterns primarily within the same provider/model;
retain actual wall time, correctness and tool work alongside them.

## 5. Operator help is not inferred human labor

Both inspected receipts record no reactivation nudge. That says nothing about
how much hypothetical human work their applications would require. Haskell
exhausted a model output budget without editing source; its failed private groups
cannot be translated into engineer-hours. Diagnosing the parser misclassification
and recording the override were operator measurement work, with no candidate
repair or extra nudge. Ruby's self-authored helper repairs were model work, not
human intervention.

Keep three ledgers conceptually separate: candidate autonomous/continued work,
controller/operator interventions, and post-collection analyst effort. Count
actual technical hints, direct source edits, environment repairs and reactivation
prompts with actor and before/after checkpoint evidence. A controller's decision
to continue the matrix after an incident belongs to experiment operations; it is
not a repair of that preserved candidate. Coordinating-assistant work is
AI/operator effort unless a human actually performs and times a repair. Preserve
`observed_human_repair_seconds: null` when no measured repair exists.

For the user's language-by-situation view, publish behavior-group failures from
`grades[].groups` and `critical_failures`, plus compile/runtime/assertion/transport
categories supported by evidence. Behavior groups are parts of one attempt, not
independent tasks. Do not repeat the attempt's entire token total as a cost for
every failed group. Keep an explicit outstanding-work list when a solution is
incorrect; a future measured repair study would be a separately authorized
assisted treatment, never a hidden repair loop in this matrix.

## Bounded post-collection work order

1. Verify frozen plan and completed receipt commitments; retain every planned cell
   and unresolved status. Freeze a separate analysis version and input inventory.
   Consume additive outcome overrides only after validating their schema, cell
   identity and exact original-result SHA-256. Retain raw and derived statuses,
   evidence, actor and timestamp; reject mismatches or unresolved conflicting
   overrides rather than silently replacing evidence. Include the validated
   Haskell output-limit attempt in known-effort/artifact analysis without
   relabeling it as normal completion or rewriting its receipt.
2. Add the orthogonal outcome/timing/component columns above without rewriting
   source receipts or changing collection/nudge behavior.
3. Annotate only ambiguous high-impact traces, including the Ruby helper-work
   example; show coverage and uncertainty. Validate classifications against
   call IDs, source hashes and actual outputs.
4. Produce language × model × T0/T1 attempt tables, state/coverage denominators and
   behavior-group breakdowns. With two replicates and one ledger, use individual
   attempts and restrained summaries; do not claim a general typing hierarchy.
5. Report actual assistance and unresolved work separately from model difficulty.
   Any later human repair experiment or new instrumentation belongs to a future
   protocol version, not this frozen cohort.
