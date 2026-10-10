# Languages benchmark: research, protocol and implementation

Research date: 2026-10-10. Status: a Ruby/Rust development slice is implemented with two compact smoke controls and a larger ledger-engine calibration candidate, with native references, behavioral suites and isolated grading. The subscription adapter has passed its capability probe; all four bounded Ruby/Rust × T0/T1 smoke cells passed their initial and nudged checkpoints. These compact development results require difficulty calibration. No comparative model conclusions or scored pilot are available. Numerical budgets, sample sizes and decision margins remain development defaults, to be calibrated and frozen before confirmatory collection.

The question is whether stronger static guarantees improve **verified correctness per unit of agent effort**, and whether their marginal benefit shrinks when useful tests are available. We should permit the evidence to support typing, tests, their combination, or neither under the selected workload.

Start with [the implementation and validation status](implementation.md) for what runs now. [The experimental design](benchmark-design.md) and [the difficult task catalog](task-catalog.md) describe the broader research proposal. Supporting documents:

- [Research findings and sources](research-findings.md): what existing evidence establishes, and where this experiment adds something.
- [Measurement and analysis](measurement-and-analysis.md): tokens, time, errors, nudges, uncertainty and decision rules.
- [Codex harness plan](codex-harness-plan.md): subscription execution, isolation, telemetry and lessons from the reference project.
- [Rollout plan](rollout-plan.md): a small qualification phase, staged pilot, expansion arithmetic and acceptance gates.

Recommended roster: Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby. The initial implementation and testing now start with Ruby and Rust, as requested, then expand; this supersedes the earlier four-language starting proposal. Avoid presenting these as an ordered “type strength” ladder. Run the same behavioral contracts across languages and use TypeScript/Python ablations to isolate the effects of annotations and checker feedback.

Primary model configurations follow the requested Astra low / Sol medium / Luna high proposal. They are **model-plus-effort configurations**, not a clean comparison of model size. Qualify exact subscription-accessible IDs before running; a smaller same-effort crossover separates that confound.

The default plan has six ledger-engine calibration cells (Ruby/Rust, supplied tests, Astra low, three replicates). The legacy 48-cell control matrix remains available with `plan --purpose smoke`. Neither plan has been launched. [The source-size and difficulty audit](difficulty-audit.md) records the observed 4/4 initial smoke ceiling and the independent-instance evidence required before difficulty promotion.

The main comparison is tests supplied versus no tests supplied. Both use an independent hidden evaluator. Measure unattended completion and completion after at most two fixed generic nudges separately. Count continuation tokens and elapsed time, not just the prompt length.

The reference project at `~/Projects/llm-coding-benchmark` was inspected read-only. Its existing task results inform difficulty selection, not the findings of this new experiment. No personal Ruby/Rust stack preference was applied: choosing a preferred implementation language would bias this project.

A separate [queue scalability and reliability track](scalability-benchmark.md) tests Elixir/OTP/Broadway, Rust with libraries and Rails/Bunny. It measures agent effort alongside correctness-qualified capacity under backpressure and failure. This compares ecosystems and does not extend the typing experiment into a claim about Elixir's type system.
