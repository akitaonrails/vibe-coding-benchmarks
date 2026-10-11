# Staged rollout and decision gates

Status: original research proposal, retained for future confirmatory work. The completed exploratory subscription campaign is documented in [the combined results](followup-matrix-results.md); its model roster and scope supersede this proposal for that campaign. Costs below are maximum agent-hours at draft time ceilings, not predicted runtime, token use or subscription allowance. Human task-authoring, porting, oracle verification and infrastructure work are additional substantial costs.

## Stage 0: implement instruments and task qualification

Build the manifest/event schema, isolated Codex adapter, immutable snapshots, private grader, two-nudge state machine and analysis outputs. Implement one compact development task in the four pilot languages. Validate model access and usage semantics with short jobs before committing to longer tasks.

Develop F1 (crash recovery) and F4 (protocol migration) first: one stresses behavioral invariants, the other API/type propagation. Build reference solutions and semantic mutants before polishing prompts. Have another reviewer, or an independently performed review pass, check contract/oracle consistency and port equivalence. A model that authored an oracle should not be its sole judge.

Gate: all qualification checks in [the harness plan](codex-harness-plan.md) pass; references pass and mutants fail; no persistent credential/config changes are needed in the reference project. If usage accounting is incomplete, time/correctness research may proceed only with token conclusions explicitly deferred.

## Stage 1: bounded pilot, then decide scope using evidence

Recommended pilot: four languages (Rust, Haskell, TypeScript, Python) × three configurations × two test conditions × two development tasks × two repetitions = **96 initial attempts**.

Begin with a 12-attempt sentinel subset: four languages × three models, first F4 development task, T1, first repetition. This is part of the 96, not an additional matrix. Its purpose is detecting broken environments, model-access problems and obviously mismatched task difficulty. Do not drop languages because they look bad in the sentinel.

Draft pilot budget: 45 minutes initial work and up to 15 minutes after each of two terminal nudges, total at most 75 active minutes per attempt. Thus 96 attempts imply at most **120 agent-hours**, up to **192 continuation invocations**, and at most 288 invocation segments. The 12 sentinels have a 15-hour upper bound. Actual use should be measured before continuing; a subscription is rate-limited capacity, not unlimited free compute.

The two development tasks are not enough to estimate general language superiority. This stage estimates:

- Telemetry loss, isolation failures, quota interruptions and environment overhead.
- Runtime/token distribution by model/language/condition, including failed work.
- Frequency and cost of terminal stopping and nudge recovery.
- Public-suite adequacy and private-oracle errors.
- Ceiling/floor effects, translation imbalance and variance across repetitions.

Archive all pilot results as development data. Revise instruments and task budgets transparently, then freeze fresh scored instances. Do not reuse a pilot prompt/solution exposure as an independent held-out task.

## Stage 2: choose the confirmatory question before expanding

There are two useful expansion directions. Do not automatically run all of them.

**Mechanism-first, recommended if the central goal is the typing assumption.** Run B1 TypeScript annotation/checker ablation on four fresh instances representing at least four families: three modes × three model configurations × two test conditions × four tasks × three repetitions = **216 attempts**. Include Python B1 as an independent replication when capacity permits: another 216. Run the TypeScript B2 checking ladder separately for a further 216 if estimating a diminishing-return curve is the priority. Any shared cells must match every manifest dimension before reusing observations; otherwise they are distinct attempts. The raw sum is **648**, not a required launch plan.

This staged order first asks whether checker feedback helps, then whether the result replicates in a dynamic language, then whether increments in checking have shrinking benefit. Four tasks remain limited evidence for a five-point noninferiority margin. Use the pilot to power the precise contrasts and increase independent task diversity rather than simply rerunning the same few tasks.

**Language-first, useful for practical selection.** Expand to all seven languages and all six task families with two independently authored instances per family. Three model configurations × two test conditions × three repetitions gives:

`7 × 3 × 2 × 12 × 3 = 1,512 initial attempts`.

At a draft scored budget of 120 minutes initial plus up to two 30-minute continuations, the ceiling is **4,536 agent-hours** (189 days if serial, before grading and quota delays). Maximum additional continuation invocations: **3,024**. This arithmetic is why we should pilot and prioritize rather than commit blindly to a giant matrix.

At the same three-hour maximum, each 216-attempt mechanism block has a 648-hour ceiling. These are research campaigns, not a weekend batch. Tune actual task caps based on pilots and correct references; do not silently shorten slow compiled-language budgets or grant selected models more time.

Confirmatory sample size is determined by task-level variance and desired precision, not the fact that 1,512 looks large. Repetitions and test cases do not turn twelve tasks into thousands of independent workloads. If a feasible sample cannot resolve the prespecified margin, report an exploratory estimate and “insufficient precision.”

## Stage 3: targeted controls

Choose subsets and ordering before viewing their scored outcomes:

- Same-effort crossover: all three models at medium on selected tasks. Existing Sol medium cells are reusable only with identical manifests; add Astra/Luna medium. Compare requested deployment configurations and common-effort configurations separately.
- Minimal-continuation versus reminder policy: fork qualified terminal histories in a fixed subset, same continuation budgets and no grading-triggered messages.
- Fresh-start budget ladder: base versus doubled allowance in all selected cells, including timeouts, to distinguish compute limits from early stopping.
- Diagnostic-output mechanism: within one checker, compare full native diagnostics against a fixed pass/fail signal in a restricted runner that prevents alternate diagnostic access. Same type rejection rules, same source, same tests. This artificial ablation estimates informational value; native-tooling track remains the practical result.
- Tooling extension: fixed pinned language servers in every ecosystem where available, or compiler/checker-only baseline. Do not claim the CLI-only result tests all IDE/tooling benefits. LSP tools must actually be connected and used, not merely installed.
- Native asynchronous/I/O extension and accumulating maintenance: evaluate ecological limits of the portable simulator tasks.

Every control consumes extra quota and adds hypotheses. Prioritize according to the unresolved mechanism, not which extension could improve a preferred language's ranking.

## Freeze and registration package

Before confirmatory collection, version and hash:

1. Hypotheses, primary contrasts, effect margins, multiplicity rule and analysis code.
2. Public contracts, language ports, starter schemas, toolchain images and dependency manifests.
3. Public suites, mutation inventory, private oracle and hidden manifest commitment.
4. Model IDs/efforts, Codex build, effective instructions, tools, context settings and authentication mode.
5. Resource ceilings, randomization schedule, assistance text/eligibility, snapshot schedule and missing-data policy.
6. Replacement/invalidation rules, allowed submission surfaces and protocol-deviation handling.

Keep hidden seeds/solutions inaccessible until the round closes. Release grader/task materials afterward where licensing permits; use new instances for subsequent rounds. Public availability and randomized names do not eliminate training contamination. Disclose previous exposure and any model use in authoring tasks.

## Completion criteria for the research campaign

Deliver reproducible per-attempt artifacts, normalized metrics, independent correctness results and the prespecified analysis. The report should be able to say, for example:

- “Checker feedback helped on migration tasks, but showed no resolved benefit on recovery tasks at these budgets.”
- “With supplied tests, the dynamic condition met the chosen noninferiority margin, at comparable measured effort.”
- “The point estimate favors the dynamic condition, but uncertainty is too wide to establish noninferiority.”
- “Nudges recovered initial failures, but recovery consumed a substantial additional agentic loop.”
- “The strictest local checking increment reduced defects enough to justify its cost, contradicting diminishing returns on this workload.”

These are examples of permitted conclusions, not expected results. None should become “types are useless,” “strong typing always wins,” or “the model reasoned less” without the corresponding evidence and scope.
