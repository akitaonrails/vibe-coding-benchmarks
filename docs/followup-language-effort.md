# Follow-up language and testing-condition effort

Both follow-up cohorts are closed. The Opus figures below include all 28 planned cells and preserve three infrastructure incidents. Each condition has two planned repetitions. Correct means a normal completed handoff with all 43 private histories passing; no Opus artifact was classified correct only at a deadline. Infra is attribution, not a language semantic failure.

Primary wall medians include only valid-development attempts with confirmed coding start and show known n. This rule includes every valid outcome, including failures and timeouts, irrespective of its grade; it is not a success-only selection. Token medians retain their complete-usage coverage selection. They are not pure model-thinking or CPU time. Tools/edits and saved-source ranges include infrastructure artifacts where available, so they describe the recorded cohort rather than only successful solutions. Source-changing calls are not repair iterations.

## Opus 5.5 medium

| Language | Tests | Normal correct / planned | Semantic failure | Infra | Median valid-attempt wall seconds (n) | Median native tokens (n) | Tools total / source-changing calls | Final src bytes range | Final src lines range |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| csharp | T0 | 2/2 | 0 | 0 | 76.5 (2) | 92,004.5 (2) | 12 / 2 | 14,866–15,080 | 263–267 |
| csharp | T1 | 1/2 | 0 | 1 | 81.4 (1) | 360,988 (1) | 13 / 2 | 13,321–15,107 | 234–268 |
| haskell | T0 | 2/2 | 0 | 0 | 113.9 (2) | 118,537 (2) | 14 / 3 | 15,884–16,036 | 265–266 |
| haskell | T1 | 1/2 | 0 | 1 | 139.2 (1) | 96,469 (1) | 10 / 2 | 14,239–16,000 | 239–280 |
| kotlin | T0 | 2/2 | 0 | 0 | 72.6 (2) | 86,408.5 (2) | 12 / 2 | 13,481–13,515 | 208–210 |
| kotlin | T1 | 2/2 | 0 | 0 | 77.8 (2) | 128,615 (2) | 12 / 3 | 13,352–13,827 | 205–216 |
| python | T0 | 2/2 | 0 | 0 | 98.0 (2) | 100,228.5 (2) | 12 / 6 | 13,074–13,571 | 344–351 |
| python | T1 | 2/2 | 0 | 0 | 85.0 (2) | 153,097 (2) | 14 / 4 | 12,467–12,522 | 315–320 |
| ruby | T0 | 2/2 | 0 | 0 | 124.4 (2) | 183,700.5 (2) | 19 / 6 | 13,518–14,208 | 416–426 |
| ruby | T1 | 1/2 | 0 | 1 | 139.7 (1) | 205,141 (1) | 14 / 5 | 10,195–13,876 | 319–416 |
| rust | T0 | 2/2 | 0 | 0 | 141.9 (2) | 144,024 (2) | 16 / 5 | 22,670–22,885 | 697–702 |
| rust | T1 | 2/2 | 0 | 0 | 86.9 (2) | 158,356 (2) | 16 / 5 | 23,546–23,656 | 713–716 |
| typescript | T0 | 2/2 | 0 | 0 | 85.8 (2) | 116,560.5 (2) | 12 / 3 | 15,046–16,201 | 300–318 |
| typescript | T1 | 2/2 | 0 | 0 | 107.3 (2) | 139,423 (2) | 16 / 5 | 14,869–15,134 | 302–305 |

The three infrastructure-aborted attempts are excluded from the primary wall column, leaving n=1 for C#, Haskell and Ruby T1. Their raw effort remains preserved: the generated JSON retains all-started operational wall medians and each attempt’s timing; the cohort operational totals below also retain these incidents. This avoids presenting short provider/harness aborts as inexpensive language solutions.

All 28 Opus attempts used zero reactivation nudges. Source-size ranges count all saved src files, including comments and any submitted tests; all 28 artifacts were available. Three failed raw artifacts belong to infrastructure incidents and are not eligible semantic failures. The 25 eligible coding outcomes all passed, including all 14 T0 cells and 11 of 14 T1 planned cells; the other three T1 cells are infrastructure incidents. A T0/T1 superiority claim cannot be drawn from this ceiling with unequal usable samples.

Native counts across the cohort are 205 model-request observations versus 271 operational request records; 66 operational records are proven unsent. The cohort records 192 tool calls and 53 known source-changing calls. These describe trace activity, not independent reasoning cycles or defects. Provider-native identity conflicts and missing records remain visible in the source analysis; complete token coverage exists for 25/28 attempts.

Complete-usage attempts contribute 3,504,507 native tokens: 378 uncached input, 2,639,302 cache-read input, 658,634 cache-creation input and 206,193 output including thinking. These are disjoint addends in Claude’s schema; separate reasoning tokens are unknown. The 25-row coverage subset happens to coincide with successful outcomes here, so these token figures must not be advertised as full-cohort totals or a success-neutral complete measurement of failed incidents.

Operational timing coverage is separate. Initial preflight retry intervals sum to a 398.34-second observed lower bound over 27/28 attempts; the remaining interval is unknown. Reported allowance HTTP calls total 8.37 seconds over only 23/28 attempts. Auth preflight and cleanup fields cover 28/28 attempts (2.60 seconds and 0.14 seconds respectively). These timers have different scopes and must not be subtracted to invent a clean coding duration. For example, cell 6 has seven proven-unsent checks, 0.52 seconds of recorded HTTP calls and a 69.00-second initial retry interval within roughly 139 seconds of invocation wall time.

Instrumentation epochs are original (four consumed cells), serial-admission-v2 (one consumed cell), and serial-admission-v3 (23 remaining cells). Original cells 3/4 and v2 cell 5 are infrastructure incidents; their preserved raw failing grades do not imply a semantic defect produced by a valid coding attempt. No consumed attempt was repeated after the instrumentation changes. The complete lineage is retained in the generated report.

Sol uses the same language/condition layout below, while retaining Codex’s different native response-count and inclusive cache/reasoning conventions. Cross-provider token columns will not be summed or interpreted as a common compute unit. See [the main follow-up report](followup-matrix-results.md) for qualifications, caveats and the unchanged first-cohort comparison.

Evidence: `results/opus-medium-matrix-final/analysis.json` SHA-256 `ef6b9b02058519dd3f7584ea55d75d90ccfc4968e95c3d1f2265953c0b808b43`; its immutable source lineage is `results/opus-medium-matrix-v3`. Only closed committed reports were used.

## Sol medium

All 28 attempts completed normally and passed all 43 histories at the initial checkpoint. All were valid-development attempts with confirmed coding start, complete native usage and available source. There were no deadline-only passes, semantic failures, infrastructure interruptions, quota stops or nudges. Each table row has two planned and two normal correct attempts; every wall/token median has n=2.

| Language | Tests | Normal correct / planned | Median valid-attempt wall seconds (n) | Median native tokens (n) | Tools total / source-changing calls | Final src bytes range | Final src lines range |
|---|---|---:|---:|---:|---:|---:|---:|
| csharp | T0 | 2/2 | 64.8 (2) | 171,554.0 (2) | 19 / 4 | 14,897–15,015 | 264–271 |
| csharp | T1 | 2/2 | 54.2 (2) | 166,230.5 (2) | 17 / 2 | 14,584–14,943 | 249–262 |
| haskell | T0 | 2/2 | 81.5 (2) | 196,279.5 (2) | 20 / 5 | 15,913–15,995 | 268–268 |
| haskell | T1 | 2/2 | 65.5 (2) | 184,743.5 (2) | 20 / 5 | 15,787–15,833 | 263–266 |
| kotlin | T0 | 2/2 | 67.1 (2) | 177,734.5 (2) | 20 / 2 | 13,302–13,330 | 210–213 |
| kotlin | T1 | 2/2 | 58.8 (2) | 160,835.5 (2) | 24 / 2 | 13,179–13,263 | 204–209 |
| python | T0 | 2/2 | 83.7 (2) | 178,628.5 (2) | 19 / 3 | 11,894–11,965 | 310–312 |
| python | T1 | 2/2 | 60.0 (2) | 126,033.5 (2) | 15 / 3 | 11,664–11,810 | 293–306 |
| ruby | T0 | 2/2 | 111.8 (2) | 213,356.0 (2) | 22 / 4 | 12,740–12,834 | 381–381 |
| ruby | T1 | 2/2 | 68.7 (2) | 155,668.0 (2) | 17 / 4 | 12,741–12,777 | 383–383 |
| rust | T0 | 2/2 | 81.6 (2) | 188,123.0 (2) | 19 / 5 | 21,110–22,694 | 597–695 |
| rust | T1 | 2/2 | 76.5 (2) | 208,358.0 (2) | 21 / 7 | 22,077–22,199 | 675–676 |
| typescript | T0 | 2/2 | 68.2 (2) | 146,027.5 (2) | 16 / 2 | 14,285–14,332 | 282–283 |
| typescript | T1 | 2/2 | 53.2 (2) | 147,501.0 (2) | 17 / 2 | 14,279–14,325 | 281–284 |

Sol records 289 completed native response identities, 266 tool calls and 50 known source-changing calls. Response identities are not wire-request starts. Complete usage across 28/28 attempts totals 4,842,146 tokens: 4,725,576 inclusive input plus 116,570 inclusive output. Input contains 4,131,968 cache-read tokens; output contains 20,184 reasoning tokens. Reported cache-write tokens are zero. These subsets must not be added again. No operational incidents or manual interventions appear in the Sol report ledger; unmeasured operator setup effort remains separate.

Both configurations reached the correctness ceiling on eligible outcomes. Differences in these tiny-sample effort columns are descriptive and cannot establish a language ranking. Wall times include agent orchestration and validation, and Opus additionally has measured provider-preflight delays. Source sizes count all submitted source, including helpers/tests, not production-only code.

Evidence: `results/sol-medium-matrix-final/analysis.json` SHA-256 `4957300c9678b426579498976d695e157c6a6176073258ba73d90d596cad4978`.
