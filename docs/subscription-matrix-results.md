# Subscription matrix results: one ledger, seven languages

Closed first cohort, 2026-10-11. All 56 planned attempts are retained: Kimi K3 high and OpenCode GLM 5.3 high, seven languages, supplied tests absent/present (T0/T1), two repetitions. There were **24 normally completed correct attempts, 16 correct deadline snapshots, nine failed saved artifacts and seven attempts without a final grade**. Correctness means passing the 43-case private grading suite, which includes the 27 public-defined histories and 16 withheld seeded combination histories. T1 agents received the public histories; T0 agents did not.

This cohort does not establish a monotonic advantage from stronger typing. Dynamic-language implementations often succeeded, typed implementations also succeeded, and failures included model output limits, tool/transport lifecycle losses and specific missed state-transition rules. The observations are useful for this configured task and agent; they do not rank language families in general.

## Outcomes by language and testing condition

Every row below has two planned attempts. N = normal completed handoff with a correct artifact; D = correct artifact at the deadline; F = available artifact that failed grading; U = no final correctness evidence. A failed artifact may be an unchanged starter after an output limit. U is not counted as a semantic failure. Seconds and tokens are medians over all known observations, including unsuccessful attempts; token n explicitly shows incomplete coverage.

| Agent/model | Language | Tests | N / D / F / U | Median active seconds | Median inclusive tokens (known n/2) | Median tools |
|---|---|---|---|---:|---:|---:|
| Kimi K3 | csharp | T0 | 1 / 1 / 0 / 0 | 895.0 | 545,378 (1/2) | 14.5 |
| Kimi K3 | csharp | T1 | 2 / 0 / 0 / 0 | 644.0 | 675,232 (2/2) | 20.5 |
| OpenCode GLM5.3 | csharp | T0 | 0 / 1 / 1 / 0 | 900.1 | unknown (0/2) | 31.5 |
| OpenCode GLM5.3 | csharp | T1 | 0 / 2 / 0 / 0 | 900.1 | unknown (0/2) | 33.5 |
| Kimi K3 | haskell | T0 | 0 / 0 / 1 / 1 | 788.5 | 363,326 (1/2) | 15.5 |
| Kimi K3 | haskell | T1 | 2 / 0 / 0 / 0 | 580.9 | 558,293 (2/2) | 18.5 |
| OpenCode GLM5.3 | haskell | T0 | 0 / 0 / 1 / 1 | 680.4 | 693,631 (2/2) | 18.5 |
| OpenCode GLM5.3 | haskell | T1 | 1 / 1 / 0 / 0 | 898.5 | 2,276,891 (1/2) | 38 |
| Kimi K3 | kotlin | T0 | 2 / 0 / 0 / 0 | 532.3 | 276,082 (2/2) | 13 |
| Kimi K3 | kotlin | T1 | 1 / 1 / 0 / 0 | 845.7 | 530,417 (1/2) | 16 |
| OpenCode GLM5.3 | kotlin | T0 | 1 / 1 / 0 / 0 | 851.5 | 1,128,066 (1/2) | 28 |
| OpenCode GLM5.3 | kotlin | T1 | 0 / 0 / 0 / 2 | 900.1 | 1,450,846 (2/2) | 32 |
| Kimi K3 | python | T0 | 0 / 1 / 1 / 0 | 898.2 | 442,673 (1/2) | 14 |
| Kimi K3 | python | T1 | 2 / 0 / 0 / 0 | 603.5 | 557,268 (2/2) | 17 |
| OpenCode GLM5.3 | python | T0 | 0 / 0 / 1 / 1 | 900.0 | 1,324,010 (1/2) | 25 |
| OpenCode GLM5.3 | python | T1 | 2 / 0 / 0 / 0 | 631.4 | 1,051,110 (2/2) | 27.5 |
| Kimi K3 | ruby | T0 | 0 / 1 / 0 / 1 | 769.0 | 168,308 (1/2) | 15 |
| Kimi K3 | ruby | T1 | 2 / 0 / 0 / 0 | 722.7 | 647,818 (2/2) | 20 |
| OpenCode GLM5.3 | ruby | T0 | 1 / 1 / 0 / 0 | 876.1 | 912,250 (1/2) | 24.5 |
| OpenCode GLM5.3 | ruby | T1 | 1 / 1 / 0 / 0 | 813.3 | 1,663,385 (2/2) | 34 |
| Kimi K3 | rust | T0 | 0 / 2 / 0 / 0 | 900.0 | unknown (0/2) | 16 |
| Kimi K3 | rust | T1 | 2 / 0 / 0 / 0 | 848.7 | 734,494 (2/2) | 21.5 |
| OpenCode GLM5.3 | rust | T0 | 0 / 1 / 1 / 0 | 668.0 | 53,838 (1/2) | 20.5 |
| OpenCode GLM5.3 | rust | T1 | 1 / 0 / 0 / 1 | 832.3 | 1,164,321 (1/2) | 35 |
| Kimi K3 | typescript | T0 | 2 / 0 / 0 / 0 | 674.9 | 251,598 (2/2) | 11.5 |
| Kimi K3 | typescript | T1 | 1 / 1 / 0 / 0 | 796.5 | 705,900 (1/2) | 18 |
| OpenCode GLM5.3 | typescript | T0 | 0 / 0 / 2 / 0 | 443.5 | 50,048 (2/2) | 5 |
| OpenCode GLM5.3 | typescript | T1 | 0 / 1 / 1 / 0 | 900.0 | unknown (0/2) | 37 |

Kimi produced 24 correct artifacts out of 28 planned cells (17 normal, seven deadline), two failed artifacts and two unknowns. OpenCode produced 16 correct artifacts (seven normal, nine deadline), seven failed artifacts and five unknowns. These are model-plus-agent configurations, not an isolated model comparison.

Across agents, T1 produced 24 correct artifacts, one failed artifact and three unknowns; T0 produced 16 correct artifacts, eight failed artifacts and four unknowns. This descriptive contrast is consistent with supplied tests helping on this ledger. It is not a causal effect estimate: two repetitions, heterogeneous stopping mechanisms and unknown artifacts leave substantial uncertainty. Within Kimi, all 14 T1 artifacts passed, while T0 had ten passes, two failures and two unknowns.

## Token composition and measurement coverage

Complete native usage is available for 36/56 attempts: 20 Kimi and 16 OpenCode. The remaining attempts retain known partial subtotals in the companion analysis, not complete totals. Missing values are not zero and cannot be used to claim less effort. This table aggregates only complete-usage attempts, regardless of correctness; it is a measurement-coverage subset, not a success-only sample.

| Agent/model | Complete usage attempts | Inclusive input | Cache-read subset of input | Inclusive output | Reasoning subset of output | Inclusive total |
|---|---:|---:|---:|---:|---:|---:|
| Kimi K3 | 20 | 9,655,431 | unknown | 502,141 | unknown | 10,157,572 |
| OpenCode GLM5.3 | 16 | 15,895,421 | 14,862,144 | 781,994 | 526,417 | 16,677,415 |

Cache reads are already included in input and reasoning is already included in output: neither is added again. Cache-write components remain unknown. Repeated cached context can dominate inclusive totals; these totals are not newly generated work, marginal subscription billing or a common cross-provider compute measure. A small visible nudge would also not imply a small continuation cost, but all 56 attempts here used zero nudges.

## Source size and observed work

Saved source size includes all files under src, comments and any submitted helper/test code. The ranges below cover every available final artifact, including unchanged failed starters. Deltas compare physical line counts with the corresponding frozen starter. No missing artifact is replaced with a stale workspace; code length is not quality or implementation difficulty.

| Language | Frozen starter bytes / lines | Available finals / 8 | Final src byte range | Final line range | Line delta range |
|---|---:|---:|---:|---:|---:|
| rust | 18,416 / 576 | 7/8 | 18,416–29,974 | 576–840 | +0–+264 |
| haskell | 14,239 / 239 | 6/8 | 14,239–17,869 | 239–341 | +0–+102 |
| csharp | 13,321 / 234 | 8/8 | 15,142–19,144 | 267–436 | +33–+202 |
| kotlin | 11,920 / 181 | 6/8 | 13,517–16,128 | 204–280 | +23–+99 |
| typescript | 12,738 / 247 | 8/8 | 12,738–17,584 | 247–357 | +0–+110 |
| python | 10,375 / 268 | 7/8 | 12,651–16,299 | 318–419 | +50–+151 |
| ruby | 10,195 / 319 | 7/8 | 14,075–16,726 | 412–463 | +93–+144 |

The full per-attempt JSON retains native request counts, tool counts, source-changing call counts, timing and source hashes. The 56 attempts contain 1,242 recorded tool calls. The conservative simple-command classifier recognized **zero** checks and reported zero repair cycles throughout: this is a coverage failure of that narrow classifier, not evidence of no debugging. Compound shell commands, heredocs and custom test drivers dominate these traces. Do not compare these zero cycle counts as meaningful iteration measurements.

| Agent/model | Native requests total / median per attempt | Tool calls total / median | Known source-changing calls total / median |
|---|---:|---:|---:|
| kimi | 458 / 17 | 462 / 16.5 | 68 / 2 |
| opencode | 722 / 27 | 780 / 29 | 98 / 4 |

These edit counts exclude calls without both source digests and remain lower bounds where a timed-out call lost its after-digest.

For concrete classifications, see [the matched Kimi language/condition audit](subscription-language-effort-audit.md) and [the first-eight trace audit](subscription-first-eight-trace-audit.md). They show actual Rust visibility and Haskell/Kotlin compiler repairs alongside lengthy Python/JavaScript/Ruby helper repairs that did not change submitted production source. One tool call can replace several files or combine compilation and tests; a failed helper expectation is not automatically a production defect. The last source edit or first supplied-test pass is not measured time-to-private-correctness. Verification and reasoning after that point remain real candidate effort.

## Failure mechanisms and unknown outcomes

Four SHA-bound overrides classify GLM clean length stops as model output limits rather than the frozen parser’s raw infrastructure errors. These attempts retain known effort and unchanged failing artifacts. They are not silently dropped or retried. The remaining failed artifacts include an additional unchanged TypeScript T1 starter and three near-complete 42/43 results, plus Haskell’s 28/43 result.

The [semantic-failure audit](subscription-semantic-failure-audit.md) links C# cell 21 and Python cell 25 to losing historical load eligibility after an empty migration/checkpoint; both fail `empty_load_pristine_once`. GLM Python cell 45 also fails that history, but its root cause has not been separately audited. Kimi Haskell cell 37 mishandles the fully persisted checkpoint-fault response/lifecycle path; it fails one targeted history and 14 seeded combinations. Fifteen failed histories do not establish 15 independent defects. These source-based diagnoses were not supplied to candidates and no corrective run was performed.

The seven unavailable final artifacts are cells 6, 8, 19, 23, 27, 28 and 49. Their command outputs and consumed effort remain visible. Tool retirement and transport settlement failures can remove final correctness evidence even after successful visible checks. For example Kotlin cell 8 passed public checks before later fuzzing timed out and retired the worker. Neither a raw valid-development label nor a stale host source copy supplies the missing final grade.

## Operational work and scope

Collection used the frozen 900-second initial maximum and at most two eligible 180-second continuations; actual continuations were zero. Thus this cohort provides no estimate of nudge rescue probability, and equal observed nudge counts were not forced. Private grading happened after collection; no private failure drove an extra prompt or repair loop.

The analysis retains 1 explicit operation record, 4 classification overrides and 3 supervisor incident-resume authorizations. These ledgers overlap in describing events and should not be summed as unique interventions. Resumes continued pending cells; consumed attempts were preserved. Setup, provider-parser diagnosis, cleanup incidents and report authoring are harness/AI-operator work, separate from candidate effort. Operator token cost and human repair hours were not measured; both remain unknown.

This is one multi-module maintenance task with two repetitions per cell. Its frontier-level difficulty remains unqualified; correctness ceilings in several cells and large self-authored validation effort are both relevant calibration findings. Seven language labels are not a one-dimensional typing scale, and the submitted code may not exercise each language’s strongest guarantees. No general law of diminishing returns, typing superiority or test equivalence is established here.

The historical Astra smoke and separate queue reference/runtime experiments are not pooled into these statistics. A later non-inference check found the exact Sol medium route available, but this cohort contains no Sol attempts. The later exact Opus 5.5 medium and Sol medium cohorts still require their own qualified adapters and usable subscription allowance; the wider project is not complete.

## Reproducible evidence

The authoritative generated report is `results/subscription-matrix-final/analysis.json`, with the per-attempt Markdown companion `analysis.md`. It reports `closed_cohort`, validates every planned identity and committed receipt, and retains raw/analysis terminal states, overrides, grade groups, token coverage, exact interventions and source commitments. Raw local traces remain in ignored `results/subscription-matrix/`; no secrets or provider messages are reproduced here.

Frozen plan SHA-256: `15bdee06a342a84c18bd9866ecfa1642d4fa38dfc3bc28de3ad9673cc56af8b3`. Generated analysis SHA-256: `a0a565fe6e9fcdc8ab37aad63f3061939c235635493c26b3293484264bec3b64`. All calculations above include all planned cells or explicitly label their available-data subset.
