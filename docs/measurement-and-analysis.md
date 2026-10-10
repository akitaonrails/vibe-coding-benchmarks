# Measurement and analysis plan

Status: proposed. Thresholds below are explicit starting choices, not validated statistical power or results. Freeze before confirmatory data. Raw evidence must support every normalized metric.

## Primary outcomes

1. **Verified final success:** the submission builds/launches, conforms to the assigned language rules and passes every required functional/critical contract group within declared evaluator limits. For tasks with a required optimization target, publish both functional success and complete-task success.
2. **Success by resource budget:** probability of producing a verified artifact by each prespecified elapsed-time or token threshold. Publish final deployed success alongside best-so-far success; an agent can break previously working code.
3. **Total effort per launched attempt:** all available token categories and elapsed agent time, including failed work and continuations. Pair this with success; low spend from immediate abandonment is not efficiency.
4. **Critical failure rate:** acknowledged-data loss, unsafe acceptance, tenant isolation violation, invalid optimization, resource misuse, or another task-specific critical invariant. Publish each category and its denominator.

The main tables separate unattended first-handoff artifacts from final artifacts after at most two generic nudges. Neither a compiler exit code nor the agent's completion claim determines success. A green public test suite is also insufficient.

## Token accounting

Preserve each raw event and a versioned parser. Record fields as missing when absent, not zero. Keep provider definitions attached to the record.

| Quantity | Meaning |
|---|---|
| Input tokens, total | Reported input consumed across unique turns/requests, including context rereads and cached portions when the provider defines it that way |
| Cached input | Subset or separate category according to verified event semantics; never add a subset twice |
| Uncached input | `input_total − cached_input` only when both fields and their subset relation are verified |
| Output tokens | Provider-reported generation count; verify whether reasoning is included |
| Reasoning tokens | Separate measured field if available; a breakdown when already included, additive only if proven disjoint |
| Unique prompt/source size | Auxiliary lexical/tokenized size for payload and code, not a substitute for actual consumed tokens |
| Tool-output bytes/tokens | Bytes observed and bytes delivered to the model after truncation; exact token counts only when tokenizer/serialization are known |

If output already contains reasoning, `T = input_total + output_total`. If output is explicitly non-reasoning and reasoning is separate, `T = input_total + output_nonreasoning + reasoning`. Otherwise retain components and mark total semantics unresolved. Never infer unreported reasoning from wall time or count readable reasoning summaries as hidden reasoning tokens.

Validate whether `turn.completed.usage` is per-turn, per-invocation or cumulative over a resumed thread. Reconcile with persisted rollout/app-server counters on a disposable two-turn session; deduplicate replayed history by stable identifiers. Subtract cumulative baselines only when monotonic scope is established. The reference runner sums completion events and adds a reasoning field; that is a useful audit target, not proof of the installed CLI's accounting semantics.

Tokens are a consumption metric, not literal units of thought or identical compute across model families. More concise source can reduce token usage independently of better reasoning. Record prompt/source sizes and compactions to explain that mechanism without “correcting away” a real practical advantage.

If timeouts/failures lack final usage, retain partial observations and completeness flags. Do not substitute zero or rank token efficiency from success-only telemetry. Report missingness by condition and use time as the reliable primary budget until telemetry passes qualification.

## Clocks and iterations

Use monotonic timestamps for elapsed durations and UTC for provenance. Start the agent clock after the environment is ready and immediately before the initial invocation. Include model latency, compilation, test execution, tool waits and active continuation work. Exclude prebuilt image preparation and private grading; report their real operational cost separately. Queue delays and quota downtime belong in calendar/availability statistics.

Track wall-clock intervals without double-counting overlapping tools. Tool CPU totals can exceed wall time and are labeled accordingly. Break down builds, tests, other commands, provider wait when observable, and unattributed elapsed time. No-output intervals can be model reasoning or compilation; they are not automatically stalls.

An **edit/check cycle** is at least one changed-source snapshot followed by a check, ending at the next source change. Also report raw build/check invocations and commands. Many commands in one shell call are not one conceptual iteration; use process instrumentation and retain ambiguity rather than invent precision.

A **repair episode** begins with an observed failure and ends when that particular failure disappears or the run ends. Cluster repeated diagnostics by normalized location/rule, but label compiler diagnostic counts separately from distinct runtime defect mechanisms. Ten compiler messages can arise from one bug; ten thousand failing generated cases are not ten thousand bugs.

## Nudges, stalls and assistance

Main policy is fixed and **independent of hidden grading**:

1. Run to the first genuine terminal handoff or the base time cap. Freeze the artifact and observed usage. A textual progress message while tools are still running is not a handoff.
2. If the run ends normally before the cap, send nudge 1 irrespective of whether the artifact secretly passes. Use the same session and workspace. No hidden failure count or success bit is delivered.
3. After its next normal handoff, send nudge 2 irrespective of hidden score, if continuation budget remains. At most two messages; no restart-until-success loop.
4. A base-cap timeout, still-active run or infrastructure failure does not qualify as premature stopping. In the main protocol, do not send a nudge to interrupt active work. Analyze extra-budget runs separately.
5. Grade snapshots privately after collection. Report regressions introduced by nudging initial successes as well as rescues of initial failures.

Frozen suggested texts:

- N1: `Continue working on the original task. Review the requirements and complete any unfinished work using the tools available in this run.`
- N2: `Check the current implementation against the original requirements, investigate problems you find, and complete the task before concluding.`

These work with both T0 and T1. Asking a question whose answer is already in the contract gets the same generic policy, not a tailored explanation. A genuine missing requirement makes the task ambiguous: amend it for all conditions before restarting a new benchmark version.

Classify interventions:

| Class | Example | Treatment |
|---|---|---|
| Automatic internal action | Codex retries a transient tool call | Log as part of the fixed harness |
| Generic reactivation | Fixed N1/N2 | Included in assisted endpoint and all effort totals |
| Technical hint | “The old quorum is wrong in snapshot.go” | Excluded from standardized assisted endpoint; separate diagnostic run |
| Environment repair | Fixing a broken launcher/auth failure | Infrastructure incident with explicit invalidation/replacement rule |
| Human implementation | Editing candidate code | Separate human-assisted result, never autonomous success |

“Cheap nudge” describes **the subsequent work**, not message length. Publish incremental tokens/time, changed code and check cycles for every rescue. Proposed descriptive bucket: success within 5 active minutes and 50,000 additional total tokens from the first nudge, at most one nudge and zero technical hints. If token data is incomplete, cheapness is unknown. Also report continuous distributions and sensitivity at 2/10 minutes and 25k/100k tokens; the thresholds are not scientific constants.

For a diagnostic control, compare N1/N2 with two identical minimal `Continue.` messages under matched continuation caps. Fork identical terminal session/workspace snapshots if the CLI passes a fork-fidelity test; otherwise randomize independent runs from the start. Apply both policies to all terminal runs in that subset, avoiding hidden-score-triggered eligibility. Full policy costs include the shared initial effort once per policy estimate; physical experiment spend counts actually duplicated continuations. Forks are paired descendants, not independent initial trials.

Minimal continuation versus no reactivation measures reactivation plus extra opportunity. Reminder versus minimal continuation estimates the incremental reminder benefit under equal ceilings. Neither isolates “more time with no message,” since a terminated agent needs a trigger to resume. A separate fresh-start budget ladder tests larger allowed budgets for all runs, including those that hit the cap.

## Success, efficiency and censoring

Report `P(success by b)` on prespecified budgets. For time curves, save quiescent workspace snapshots after completed mutation/check events and at terminal points; grade later with no feedback. An asynchronous filesystem copy during a write is not a valid checkpoint. If only terminal snapshots are available, report terminal outcomes, not fabricated exact time-to-correctness.

Let `B` be the resource cap. For success-attainment analysis, assign each failed run a capped attainment value `B`, even if it voluntarily stopped much earlier. Successful runs use first observed verified attainment; it is interval-observed between snapshots. Report mean capped attainment alongside success and actual spend. This avoids rewarding instant failures or showing only fast winners. Do not casually apply Kaplan–Meier assumptions to voluntary stopping: stopping can be informative.

Publish:

- Arithmetic mean and distribution of actual attempt effort, including failures.
- Success rate and critical failure rate at matching budgets.
- Descriptive aggregate effort per success: sum of all attempts' effort divided by number of successful attempts, infinite/undefined when none succeed. This is not a promise about an optimal independent retry policy.
- Conditional successful-run time/tokens, explicitly secondary and subject to selection effects.
- Paired correctness/effort differences and a Pareto plot. Faster wrong code is not on a useful correctness frontier.

For token-budget curves, coarse completion-only usage cannot enforce a hard real-time token cap. Until live usage is qualified, label curves as retrospective observed checkpoints with overshoot. A time-limited run that ends before reaching a requested token threshold provides no outcome at that larger threshold. Do not extrapolate its future success.

Subscription runs have no defensible per-run dollar price unless actual allowance consumption is exposed and measured. Report tokens, wall time and quota interruptions. Optional API-price equivalents are hypothetical and versioned separately; they are not subscription invoices. Generic nudges have a count, not an invented human-minutes cost.

## Statistical unit and design

Block on task instance and pair languages/test conditions on the same semantic variant and evaluator seed manifest. Use independent session/workspace starts for repetitions; repeated identical prompts are stochastic replications, not independent tasks. Randomize within blocks and distribute conditions across days. Record model/server revisions when available; a changed endpoint defines a new block/cohort.

Primary language contrasts: each language against prespecified TypeScript and Python baselines, within model configuration and test condition. Avoid all-pairs fishing. Use paired differences, task-instance intervals and family summaries. When pooling, give each family equal weight and each independent instance within it equal weight; do not let the largest generated suite dominate.

For confirmatory inference, use a prespecified hierarchical model or paired cluster bootstrap that retains complete treatment blocks and nests replicates within task instances. Six families are too few for confident broad population inference: report suite-conditional estimates and leave-one-family-out sensitivity. More seeds of the same task reduce stochastic uncertainty, not workload-selection uncertainty. Broad claims require more genuinely independent tasks/families.

A possible mixed logistic model includes language/configuration, supplied tests, model/effort and prespecified interactions, with task-instance and day effects. Prefer direct paired estimates when the sample is too small or model fits separate/fail. Do not control for downstream mediators such as number of tests written, chosen representation or compiler cycles in the primary treatment estimate.

Within-language tests:

- Checker effect: success(B1-2) − success(B1-1), paired on tests/model/task.
- Test interaction: checker effect under T1 minus checker effect under T0. Negative suggests substitution on this scale; positive suggests complementarity.
- Diminishing return: for the verified B2 ladder, compare adjacent gains `(P2−P1)` and `(P1−P0)`, and their effort costs at comparable quality. Interpret on a prespecified probability scale; ceiling saturation alone is not proof of a universal law.
- Test-substitution noninferiority: prespecify `delta = P(dynamic+T1) − P(checked+T1)`. A lower one-sided 95% bound above −5 percentage points supports the proposed correctness margin on this suite. Report critical failures separately and require an effort-ratio upper bound below 1.20 for “nearly as efficient.” For the effort ratio, prespecify paired mean capped attainment under a common budget rather than comparing only successful attempts; show actual spend alongside it. These margins need user/workload justification before registration.

A nonsignificant difference or overlapping confidence intervals does not establish equivalence. For an actual two-sided equivalence claim, use a prespecified equivalence procedure and both bounds. Zero observed critical violations does not imply zero risk; publish an upper bound and note clustering. Passing finite behavioral tests is not equivalent to a static safety theorem. Conclusions concern observed task outcomes and effort, with guaranteed properties of the selected language configurations described separately.

Prioritize the checker/test interaction, test-substitution contrast and B2 marginal contrast. Apply a declared multiplicity rule (e.g. Holm within the primary contrast family); label remaining language/model explorations as exploratory. Do not change margins after looking at outcomes.

## Sample size and missingness

The pilot estimates variance, task discordance, resource distributions, missing telemetry and invalidity. Simulate the planned paired/hierarchical analysis with those quantities before choosing confirmatory size. As a rough warning, an unpaired binomial proportion near 50% needs about 385 independent observations for a ±5-point 95% interval; a difference generally needs more, pairing may help, and clustering may hurt. This is not the power calculation for our experiment.

Distinguish:

- Valid candidate failure: incomplete work, runtime bug, malformed model tool call with a working adapter, candidate resource exhaustion, loop, premature stop.
- Infrastructure invalid: proven provider/auth failure, broken supplied environment, harness corruption, evaluator defect.
- Protocol deviation: reading forbidden material, disabling checks, technical help or an unapproved language implementation.
- Unknown: insufficient evidence for attribution.

Publish all launched attempts and category counts. Treat candidate-caused protocol deviations as unsuccessful in operational/intention-to-run results; a separately labeled compliant-only view must not erase how often a configuration escapes its assigned constraints. Show intention-to-run operational yield, valid-attempt capability yield, invalid fractions and pessimistic/optimistic missing-outcome bounds. One replacement maximum for a proven infrastructure-invalid attempt, selected by rule before outcome review; retain both IDs, never choose the better valid result. Stop a block during a systematic incident. Missing token metrics do not invalidate a correct artifact, but do limit token conclusions.

## Minimum report

Every result row includes task/model/language/configuration hashes, test condition, repetition, run block, unattended/assisted outcome, critical groups, total and incremental effort, usage completeness, intervention counts, static-check result, public-check result, validity category and artifact hash.

Publish success-versus-budget curves; paired checker/test interaction plots; language-specific correctness–effort plots; nudge recovery cost distributions; and a failure-category table. Clearly distinguish factual observations from causal explanations of why an agent stopped. Do not summarize this experiment as one universal language leaderboard.
