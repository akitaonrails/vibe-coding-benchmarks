# Languages benchmark: research, protocol and implementation

Research date: 2026-10-10. Status: a Ruby/Rust development slice is implemented for two task families, with native references, behavioral suites and isolated grading. The subscription adapter has passed its capability probe; all four bounded Ruby/Rust × T0/T1 smoke cells passed their initial and nudged checkpoints. These compact development results require difficulty calibration. No comparative model conclusions or scored pilot are available. Numerical budgets, sample sizes and decision margins remain development defaults, to be calibrated and frozen before confirmatory collection.

The question is whether stronger static guarantees improve **verified correctness per unit of agent effort**, and whether their marginal benefit shrinks when useful tests are available. We should permit the evidence to support typing, tests, their combination, or neither under the selected workload.

Start with [the implementation and validation status](implementation.md) for what runs now. [The experimental design](benchmark-design.md) and [the difficult task catalog](task-catalog.md) describe the broader research proposal. Supporting documents:

- [Research findings and sources](research-findings.md): what existing evidence establishes, and where this experiment adds something.
- [Measurement and analysis](measurement-and-analysis.md): tokens, time, errors, nudges, uncertainty and decision rules.
- [Codex harness plan](codex-harness-plan.md): subscription execution, isolation, telemetry and lessons from the reference project.
- [Rollout plan](rollout-plan.md): a small qualification phase, staged pilot, expansion arithmetic and acceptance gates.

Recommended roster: Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby. The initial implementation and testing now start with Ruby and Rust, as requested, then expand; this supersedes the earlier four-language starting proposal. Avoid presenting these as an ordered “type strength” ladder. Run the same behavioral contracts across languages and use TypeScript/Python ablations to isolate the effects of annotations and checker feedback.

Primary model configurations follow the requested Astra low / Sol medium / Luna high proposal. They are **model-plus-effort configurations**, not a clean comparison of model size. Qualify exact subscription-accessible IDs before running; a smaller same-effort crossover separates that confound.

The implemented development plan has 48 cells across two tasks, Ruby/Rust, two test conditions, three model/effort configurations and two replicates; it has not been launched. These compact tasks have not yet been calibrated to frontier difficulty.

The main comparison is tests supplied versus no tests supplied. Both use an independent hidden evaluator. Measure unattended completion and completion after at most two fixed generic nudges separately. Count continuation tokens and elapsed time, not just the prompt length.

The reference project at `~/Projects/llm-coding-benchmark` was inspected read-only. Its existing task results inform difficulty selection, not the findings of this new experiment. No personal Ruby/Rust stack preference was applied: choosing a preferred implementation language would bias this project.
