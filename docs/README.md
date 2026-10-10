# Languages benchmark: research and proposed protocol

Research date: 2026-10-10. Status: design proposal; no benchmark runs or task implementations yet. Numerical budgets, sample sizes and decision margins are development defaults, to be calibrated and frozen before confirmatory collection.

The question is whether stronger static guarantees improve **verified correctness per unit of agent effort**, and whether their marginal benefit shrinks when useful tests are available. We should permit the evidence to support typing, tests, their combination, or neither under the selected workload.

Start with [the experimental design](benchmark-design.md), then [the difficult task catalog](task-catalog.md). Supporting documents:

- [Research findings and sources](research-findings.md): what existing evidence establishes, and where this experiment adds something.
- [Measurement and analysis](measurement-and-analysis.md): tokens, time, errors, nudges, uncertainty and decision rules.
- [Codex harness plan](codex-harness-plan.md): subscription execution, isolation, telemetry and lessons from the reference project.
- [Rollout plan](rollout-plan.md): a small qualification phase, staged pilot, expansion arithmetic and acceptance gates.

Recommended roster: Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby. Start with four representatives, then expand. Avoid presenting these as an ordered “type strength” ladder. Run the same behavioral contracts across languages and use TypeScript/Python ablations to isolate the effects of annotations and checker feedback.

Primary model configurations follow the requested Astra low / Sol medium / Luna high proposal. They are **model-plus-effort configurations**, not a clean comparison of model size. Qualify exact subscription-accessible IDs before running; a smaller same-effort crossover separates that confound.

The main comparison is tests supplied versus no tests supplied. Both use an independent hidden evaluator. Measure unattended completion and completion after at most two fixed generic nudges separately. Count continuation tokens and elapsed time, not just the prompt length.

The reference project at `~/Projects/llm-coding-benchmark` was inspected read-only. Its existing task results inform difficulty selection, not the findings of this new experiment. No personal Ruby/Rust stack preference was applied: choosing a preferred implementation language would bias this project.
