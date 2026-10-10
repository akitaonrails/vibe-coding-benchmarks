# Languages benchmark

A controlled experiment on how programming-language checks and supplied tests affect AI coding correctness and effort. The planned roster is Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby. **The first executable slice is Ruby and Rust**, as requested.

Read [the research and protocol](docs/README.md) for the hypotheses, experimental controls and analysis limits. Crash-store recovery and protocol migration are compact smoke controls. The larger ledger-engine task is a calibration candidate; none is established as a frontier benchmark. See [the size and difficulty audit](docs/difficulty-audit.md).

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

## Live subscription smoke tests

The implemented adapter pins Codex app-server 0.156.0 and records hashes of both
its binary and Code Mode companion. It requires an existing ChatGPT subscription
sign-in, exact requested model/effort availability, and a passing capability probe.
Candidate shell commands run offline in Docker; private grading follows model and
worker shutdown. See [implementation evidence and limitations](docs/implementation.md).

```sh
python3 -m langbench qualify results/qualification --model gpt-6-astra --effort low
python3 -m langbench run protocol_migration ruby results/ruby-t1 --tests T1 --model gpt-6-astra --effort low --base-seconds 180 --continuation-seconds 60
python3 -m langbench report results/ruby-t1/result.json
```

`qualify` and `run` accept `--binary /path/to/codex`; its matching
`codex-code-mode-host` must be alongside it. These commands consume subscription
inference. All four bounded Ruby/Rust × T0/T1 smoke cells passed the 44-case F4 grading
suite at their initial checkpoint and after both nudges; the suite includes 20
public and 24 withheld cases. This is development qualification, not evidence for
a language ranking. The default six-cell ledger calibration and legacy 48-cell smoke plan have not been launched. The observed three-minute initial budget was a toolchain smoke budget. Two fixed generic nudges get
separate snapshots. Request-level provider counts reconcile for these pinned traces (cached input
included; not billing or invisible compute). Generic token accounting remains
unqualified, and a worker timeout that
loses its artifact is infrastructure-invalid rather than a measured task failure.

Execute a bounded prefix of a generated development plan:

```sh
mkdir -p .work
python3 -m langbench plan > .work/calibration-plan.json
python3 -m langbench batch .work/calibration-plan.json results/calibration --limit 2
```

`plan` defaults to ledger-engine calibration. Use `plan --purpose smoke` for the legacy 48-cell control matrix. A single ledger instance cannot establish frontier difficulty.

The prefix follows randomized plan order and need not contain paired cells. The
runner validates and freezes the selected plan, records durable progress, and
stops on infrastructure/quota incidents without retries. No batch or full pilot
has been launched. See the implementation document before selecting larger runs.

## Contents

- `langbench/`: bundle preparation, process supervision, grading, manifests, event accounting, fixed-nudge collection and descriptive reports.
- `tasks/crash_store/`: logical page publication, durable snapshots, capacity pressure and interrupted reclamation.
- `tasks/protocol_migration/`: working v1 service to migrate across wire/domain/repository/worker boundaries; scoped IDs, authorization, absent/null values, cancellation and retry generations.
- `tasks/ledger_engine/`: snapshot transactions, conflict validation, durable journal replay and checkpoint migration; a difficulty calibration candidate.
- `tests/`: oracle anchors, Ruby/Rust parity, semantic mutants and instrumentation/boundary tests.
- `configs/`: pilot roster and execution budgets. A generated plan is not an instruction to launch the full matrix.
- `docs/`: research, protocol, task designs, rollout and implementation evidence.

References and private cases are controller-side assets. Never mount this repository wholesale into a candidate environment. Candidate bundles contain only the selected starter, contract and condition-appropriate public support. Submitted `src/` is overlaid onto a trusted scaffold for grading; submitted launcher/config changes cannot replace the grader's build policy.

## Interpretation

Compilation success is not behavioral success. Token totals remain unknown when event scope or reasoning-token overlap has not been qualified. An unattended result is preserved before fixed generic nudges; every continuation contributes to reported effort. Private outcomes must never determine when a nudge is sent.

Reference results, synthetic event tests and small live smoke tests serve different purposes. None alone establishes that one language is better or that a supplied suite substitutes for static checking. Full scored collection remains subject to the preregistration and qualification gates in the research plan.
