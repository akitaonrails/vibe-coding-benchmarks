# Ruby/Rust development implementation

Status: development implementation, 2026-10-10. Ruby and Rust are the first
executable ports, following the user's requested starting point. The selected
seven-language roster remains Rust, Haskell, C#, Kotlin, TypeScript, Python and
Ruby; Idris is not part of it. The earlier research documents describe the broader
proposed experiment. This document records what is implemented and verified now.

## Implemented task slice

Two compact task instances implement the shared persistent JSONL interface.
They have precise public contracts, native references and starters, deterministic
public/private cases, hand-derived oracle anchors and targeted semantic mutants.
They have **not been calibrated for frontier-model difficulty**.

| Task | Native baseline and requested work | Main interactions |
|---|---|---|
| `crash_store` (F1) | Extend a supplied store into the documented crash-consistent protocol | Durable publication, snapshots, capacity pressure and interrupted reclamation |
| `protocol_migration` (F4) | Migrate a functioning modular v1 service while retaining compatibility | Scoped identity, authorization, absent/null payloads, schema evolution, cached reads and stale completion after cancellation/retry |

The remaining task families in [the catalog](task-catalog.md) are proposals.
The F4 starter has matching domain, repository/cache, worker and request-routing
boundaries in Ruby and Rust; migration crosses those interfaces. Dynamic ports
include prose data contracts, while Rust also provides native record types.
Neither starter is an empty TODO scaffold.

The controller is Python standard library code in `langbench/`. Task assets live
in `tasks/`; native and harness regression tests live in `tests/`. Task metadata
marks the instances `stage: development` and limits submitted changes to
`src/**`. Trusted build and per-case timeouts come from controller-side metadata.

## Running the development tools

From the repository root:

```sh
python3 -m langbench list
python3 -m langbench plan
python3 -m unittest discover -s tests -v
```

`list` reports implemented ports and the planned language roster. `plan` emits a
seeded randomized manifest; it does not launch model work. The current pilot
configuration contains **48 cells**: 2 replicates × 2 tasks × 2 languages × 2 test
conditions × 3 model/effort configurations. The requested configurations are
Astra low, Sol medium and Luna high. The manifest explicitly sets
`scored_execution_qualified: false`. No 48-cell pilot has been launched.

Prepare a new candidate directory:

```sh
python3 -m langbench prepare protocol_migration ruby .work/ruby-t1 --tests T1
python3 -m langbench prepare protocol_migration rust .work/rust-t0 --tests T0
```

T0 supplies the starter, adapter and complete behavioral contract without supplied
behavioral tests. T1 adds the public cases and their executable driver. Agents may
write their own tests in either condition. T0 therefore means **no supplied
suite**, not “no permission to test.” Private cases and reference implementations
stay outside the candidate bundle.

Grade a candidate source directory or validate all native references:

```sh
python3 -m langbench grade protocol_migration ruby .work/ruby-t1
python3 -m langbench selftest
```

`grade` accepts the bundle root as its source argument. It copies submitted
`src/` into a fresh trusted scaffold, builds it, and starts a fresh persistent
process for each case. Candidate changes to launchers or build configuration do
not replace the trusted scaffold. Public grading can be selected explicitly with
`--suite public`; the default is private. `selftest` checks references for both
tasks and languages. Unmodified starters intentionally fail the full requested
contract. `report` consumes result JSON files for descriptive summaries.

## Executing a bounded development-plan prefix

The batch runner consumes the existing plan format and runs selected cells
sequentially:

```sh
mkdir -p .work
mkdir -p .work
python3 -m langbench plan > .work/pilot-plan.json
python3 -m langbench batch .work/pilot-plan.json results/pilot --limit 2
```

This example selects the first two randomized cells, **not necessarily a paired
comparison**. `--limit` is a prefix bound, not a balance guarantee. Omitting it
selects the full plan; no full pilot or batch has been launched during this
implementation. `--binary` is also supported.

Before inference, the runner validates all selected cells and rejects plans
marked as qualified for scored collection. It freezes the raw plan, its hash and
selected count, then passes through the exact seed, block, replicate, model,
effort and budgets. Indexed attempt directories avoid collisions. An fsynced
append-only progress ledger and atomically replaced `batch.json` preserve
completed work. Infrastructure/quota incidents stop the batch without retries;
interruptions retain its execution history. This is development automation, not
a waiver of preregistration or scored-run qualification gates.

## Execution boundary and environment

Qualified candidate grading requires Linux and Docker. The worker expects an
already-local `alpine:3.22` image, resolves it to an immutable image ID, and records
that identity. It does not automatically pull an image. This is a container
boundary around mounted host Ruby/Rust toolchains, not a fully self-contained
portable toolchain image; toolchain identities must also be frozen for collection.
Dependency fetching happens during environment setup. Candidate tools run
offline, with a read-only root filesystem and read-only toolchain/dependency
mounts. The repository, references and hidden oracle are not mounted wholesale.
The worker refuses controller/private task packages located under shared runtime
mounts or discoverable through its isolated Python imports. Keep the controller
in a source checkout or virtual environment outside `/usr` and other mounted
runtime trees; unsafe global installations are refused.

The worker verifies its cgroup limits: 4 GiB memory with no swap, 2 CPUs, 64 PIDs,
512 MiB workspace, 64 MiB temporary filesystem and 128 MiB Cargo filesystem.
Command timeouts terminate work; cleanup checks prevent candidate descendants
from continuing to modify artifacts between invocations or snapshots. Export is
bounded and rejects unsupported filesystem objects and invalid paths. These are
implemented isolation checks, not a claim that every hostile-program scenario has
been proven safe.

The optional `trusted-reference` backend only accepts repository reference
sources and labels its result unqualified for candidate isolation. The optional
`sandbox` backend is also labeled unqualified. Neither substitutes for Docker
candidate qualification.

## Evidence collected so far

The final integrated suite passed **78 test methods in 20.233 seconds**, covering
Docker boundaries, native oracle/mutation checks, isolated packaging, 12 provider
usage checks, 15 live-adapter checks and seven batch-runner checks. Phase 1 previously passed 39 methods.
Docker selftest passed all four native reference combinations:

| Task | Ruby | Rust |
|---|---:|---:|
| Crash store | 49/49 cases | 49/49 cases |
| Protocol migration | 44/44 cases | 44/44 cases |

The private grading suites include public regressions: F1 has 9 public plus 40
additional seeded cases; F4 has 20 public plus 24 withheld seeded cases. Thus
44/44 does not mean 44 previously unseen cases. F4 T1 supplies those 20 public
cases, while T0 supplies none.

The suites reject **13 targeted semantic mutants**: six for crash storage and
seven for migration. Native task tests also compare references against additional
seeded cases and hand-derived anchors. This demonstrates useful oracle and
instrumentation checks, not exhaustive correctness or independently authored
human oracles. These implementations still need independent review and workload
calibration.

**Reference passes are not model results.** They show that native ports and the
grading path can satisfy the documented development contracts. They establish
nothing yet about language efficiency, diminishing returns from typing, or the
relative value of supplied tests.

## Collection and measurement

The collection controller preserves the unattended artifact, then sends up to two
fixed generic continuations after ordinary agent handoffs. Nudge timing does not
inspect hidden grades. Timeout, quota and infrastructure failures terminate the
sequence instead of being treated as ordinary handoffs. Every continuation gets
its own artifact snapshot, events, elapsed time and prompt/artifact hashes. The
pilot plan budgets 45 minutes initially and 15 minutes per continuation; these
remain development defaults.

Private grading must occur outside the collection loop and must not feed results
back into the agent or decide whether it receives a nudge. This keeps a generic
reactivation distinct from a grader-guided repair loop. Unattended and assisted
outcomes must remain separately reportable.

Usage parsing retains raw reported token components and detects missing,
duplicated, conflicting and incomplete events. A total remains unknown until
usage scope and reasoning-token overlap are qualified. Cached-input subtraction
also requires known subset semantics. Missing counters are not zero, and a
short continuation prompt does not mean its resulting agent work was cheap.

## Live subscription adapter and qualification

The live adapter is implemented against Codex app-server **0.156.0**, with the
Codex binary and its sibling `codex-code-mode-host` companion both hashed in the
environment receipt. A custom installation can be selected with `--binary`; the
matching companion must be beside it. Experimental protocol events and capability
controls are version-sensitive and require requalification after upgrades.

The controller verifies existing ChatGPT subscription authentication, exact model
availability and supported effort, and refuses model fallback. It starts from a
clean temporary configuration, disables host skill discovery and builtin shells,
and sets `environments: []`. JavaScript Code Mode composition remains enabled so
models can call the sole supplied tool, `sandbox_shell`, which dispatches into the
offline Docker worker. Account identity and allowance responses are excluded from
the archived event ledger.

Qualification requires both a hidden host-file canary check and an exact-source
JavaScript probe with paired structured tool output. Agent prose is insufficient.
The Codex process performs subscription network requests; candidate shell tools
have no network access. This behavioral qualification does not prove every
property of provider internals.

Three failed preflights are preserved: two had Code Mode disabled, and the third
hid the required structured output behind a wrapper. The fourth passed with
raw-event proof of the prescribed probe. These are **harness qualification
failures**, not task failures or language observations.

```sh
python3 -m langbench qualify results/qualification --model gpt-6-astra --effort low --seconds 90
python3 -m langbench run protocol_migration ruby results/ruby-t1 --tests T1 --model gpt-6-astra --effort low --base-seconds 180 --continuation-seconds 60
python3 -m langbench report results/ruby-t1/result.json
```

`run` first qualifies its own configuration, freezes the attempt and environment,
then collects the initial turn and up to two fixed generic nudges. It records each
snapshot before any private grading. Model and candidate-worker shutdown precede
private evaluation. Raw events, tool calls, timings and artifact hashes survive
in the result directory; interrupted processing retains completed phase data.

The bounded smoke scope is four F4 cells: Ruby/Rust × T0/T1, Astra low, one attempt
per cell, with **3 minutes initially and 1 minute per nudge**. All four task receipts completed successfully and are summarized below. These short qualification runs are not comparable to the proposed
45-minute initial / 15-minute continuation pilot and cannot establish language
rankings. Development smoke timing was not controlled: concurrent harness
validation overlapped part of Rust T1, so no language-efficiency analysis is
attempted. The 48-cell pilot remains unlaunched.

| Smoke cell | Initial / nudge 1 / nudge 2 | Active seconds | Shell calls |
|---|---|---|---|
| Ruby T1 | 44/44 · 44/44 · 44/44 | 42.35 · 25.56 · 41.56 | 4 · 2 · 4 |
| Rust T1 | 44/44 · 44/44 · 44/44 | 46.24 · 23.88 · 33.29 | 4 · 2 · 2 |
| Ruby T0 | 44/44 · 44/44 · 44/44 | 56.93 · 26.66 · 32.66 | 4 · 2 · 2 |
| Rust T0 | 44/44 · 44/44 · 44/44 | 65.91 · 37.71 · 38.60 | 5 · 2 · 2 |

All four cells passed at their initial checkpoints. Eight fixed nudges added
work without improving any score, and no hidden outcome was available to trigger
or guide them. Their effort remains part of the assisted result. The quick
initial success reinforces that this compact task needs difficulty calibration;
it establishes neither frontier-level difficulty nor a typing hypothesis result.

Inspection of Rust T1’s initial artifact found typed record fields,
`Option<Value>` payload presence and tuple identity, but lifecycle state remained
`String`, without an enum or typestate encoding. A language label does not show
that its strongest available guarantees were exercised. Future calibration must
review idioms and escape hatches and freeze comparable scaffolds; this smoke
cannot test diminishing returns from progressively stronger type guarantees.

Request-level provider token counters reconcile for all four receipts:

| Smoke cell | Initial | Nudge 1 | Nudge 2 | Total |
|---|---:|---:|---:|---:|
| Ruby T1 | 58,804 | 47,144 | 99,357 | 205,305 |
| Rust T1 | 61,148 | 53,201 | 66,719 | 181,068 |
| Ruby T0 | 59,270 | 51,498 | 63,726 | 174,494 |
| Rust T0 | 80,803 | 60,372 | 74,639 | 215,814 |

Cached input is included. These provider-reported workload counters are not
billing or uncached-compute estimates; qualification inference is separate. This
pinned request-level reconciliation neither qualifies older aggregate counters
nor establishes equal compute per token across configurations.

[The sanitized machine-readable summary](smoke-results.json) records all four
receipts, exact counters, manifest commitments, artifact/source hashes and local
raw-ledger paths. It excludes account, thread and server identifiers and raw
messages. The three Ruby T1/Rust T1/Ruby T0 artifacts were identical at all
checkpoints: nudges added verification work without edits. Rust T0 added
`src/tests.rs` and its test-module declaration during nudge 1, with no observed
behavior change; nudge 2 left that artifact unchanged. All four initially passed,
so these observations cannot estimate nudge rescue probability.

A remaining limitation: a worker command timeout retires the container and its
tmpfs. If the current artifact cannot be exported, it is marked unavailable and
the run is infrastructure-invalid; it must not be counted as a behavioral task
failure. Artifact recovery at this boundary needs improvement before scored
collection. Generic normalized token totals remain unqualified. The narrower pinned
request-level reconciliation above supplies explicit provider workload counters
for these four traces; it is not a claim about billing or invisible compute.
Live tool isolation evidence alone does not qualify the full benchmark.
