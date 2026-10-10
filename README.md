# Languages benchmark

A controlled experiment on how programming-language checks and supplied tests affect AI coding correctness and effort. The planned roster is Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby. **The first executable slice is Ruby and Rust**, as requested.

Read [the research and protocol](docs/README.md) for the hypotheses, experimental controls and analysis limits. Initial executable tasks are development instances of crash-store recovery and multi-module protocol migration; neither has yet been calibrated as a frontier-level benchmark.

## Local development

The controller uses Python 3.11+ and its standard library. Native validation needs Ruby and Rust/Cargo. Candidate grading additionally requires Docker on Linux. Dependency fetching belongs to environment setup; candidate execution is offline.

```sh
python3 -m langbench list
python3 -m langbench plan
python3 -m unittest discover -s tests -v
```

Prepare an isolated task bundle with or without supplied behavioral tests:

```sh
python3 -m langbench prepare protocol_migration ruby .work/ruby-t1 --tests T1
python3 -m langbench prepare protocol_migration rust .work/rust-t0 --tests T0
```

Each destination must be new. T0 receives the same public contract and working transport as T1, but no supplied behavioral cases. Agents may create their own tests in both conditions. Preparation does not run an LLM.

Grade a submission using trusted build scaffolding and private cases:

```sh
python3 -m langbench grade protocol_migration ruby .work/ruby-t1
python3 -m langbench selftest
```

A starter intentionally does not implement all requested behavior, so its grade should fail. `selftest` grades the known-good references; it measures the grader/environment, not model capability. Real candidate execution must use the isolated backend. Results directories and scratch work are ignored by Git.

## Contents

- `langbench/`: bundle preparation, process supervision, grading, manifests, event accounting, fixed-nudge collection and descriptive reports.
- `tasks/crash_store/`: logical page publication, durable snapshots, capacity pressure and interrupted reclamation.
- `tasks/protocol_migration/`: working v1 service to migrate across wire/domain/repository/worker boundaries; scoped IDs, authorization, absent/null values, cancellation and retry generations.
- `tests/`: oracle anchors, Ruby/Rust parity, semantic mutants and instrumentation/boundary tests.
- `configs/`: pilot roster and execution budgets. A generated plan is not an instruction to launch the full matrix.
- `docs/`: research, protocol, task designs, rollout and implementation evidence.

References and private cases are controller-side assets. Never mount this repository wholesale into a candidate environment. Candidate bundles contain only the selected starter, contract and condition-appropriate public support. Submitted `src/` is overlaid onto a trusted scaffold for grading; submitted launcher/config changes cannot replace the grader's build policy.

## Interpretation

Compilation success is not behavioral success. Token totals remain unknown when event scope or reasoning-token overlap has not been qualified. An unattended result is preserved before fixed generic nudges; every continuation contributes to reported effort. Private outcomes must never determine when a nudge is sent.

Reference results, synthetic event tests and small live smoke tests serve different purposes. None alone establishes that one language is better or that a supplied suite substitutes for static checking. Full scored collection remains subject to the preregistration and qualification gates in the research plan.
