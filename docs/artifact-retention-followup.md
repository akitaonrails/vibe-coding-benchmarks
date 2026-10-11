# Artifact retention after timeouts: versioned follow-up

Status: design only, 2026-10-11. The frozen 56-cell collection continues unchanged. This review read source, existing receipts and Docker documentation; it ran no containers, tests, builds or model calls. Any implementation, qualification or follow-up collection requires a separate version after the frozen campaign closes.

## Why source disappears

`langbench/worker.py` mounts `/workspace` as a 512MiB Docker tmpfs. `DockerWorker.raw()` runs `docker exec` through the bounded host process wrapper. Any termination reason immediately calls `close()`, which force-removes the container. Consequently `execute()` cannot run its normal candidate-process cleanup, and `export()` cannot retrieve source. The subscriptions adapter correctly records unavailable source and supplies no grade, but the source was destroyed by the measurement lifecycle rather than proven incorrect.

The observed cases include:

- `0008-opencode-kotlin-T1-r1`: 900.057-second invocation; final tool timed out; source-before hash existed, source-after was unavailable; no grade.
- `0019-opencode-haskell-T0-r2`: same worker-retirement/artifact-unavailable path at the final tool deadline; no grade.
- `0023-opencode-kotlin-T1-r2`: 900.057-second invocation; final command edited `src/Engine.kt` before building/running tests, then timed out. The pre-command source hash therefore cannot establish the final source; no grade.

Receipts are under `results/subscription-matrix/<cell>/result.json`. These are missing correctness observations, not failed private tests. The first two listed commands included substantial candidate-authored checking; that does not prove their source passed the private contract. Reconstructing source from commands would also be a new, uncertain derivation, not an original immutable checkpoint.

`source_digest()` currently exports into a temporary directory and retains only the hash. There is no persistent last-known candidate snapshot after each tool. The host `workspace/` is refreshed at handoff; when the initial invocation loses its worker, it can still contain the starter. Never label that directory as the timed-out candidate's final implementation.

## Docker constraints on proposed alternatives

Stopping the container is too late for this workspace: Docker documents that tmpfs contents are removed when the container stops. Persistent volumes/bind mounts have different lifetime semantics. [Docker tmpfs documentation](https://docs.docker.com/engine/storage/tmpfs/).

Do not assume “pause, then docker cp” solves the current implementation. Docker documents `docker cp` limitations for tmpfs and certain other mounts, recommending an in-container transfer for those cases. Its ability to copy stopped containers does not restore vanished tmpfs data. Copying a tar stream directly into a host directory would also need strict validation of untrusted entries and resource bounds. [Docker copy documentation](https://docs.docker.com/reference/cli/docker/container/cp/).

Pausing suspends all container processes, including a trusted exporter started inside that container. A pause-based design therefore needs a separately qualified way to read the still-mounted namespace without unfreezing candidate writers. Docker's pause behavior alone does not establish that a proposed exporter can read this tmpfs safely. [Docker pause documentation](https://docs.docker.com/reference/cli/docker/container/pause/).

A writable host bind is a larger change: it would alter the current “no writable host mount” boundary and tmpfs resource accounting. Persistence alone does not create an atomic snapshot or prevent symlink/hardlink traversal and concurrent writes. Do not introduce one as an unreviewed fallback. A future dedicated bounded volume or host-owned snapshot facility would require its own containment and resource qualification.

## Recommended smallest correction

Keep the existing image, network policy, tmpfs limits, trusted scaffold and permitted source paths. Introduce a terminal worker state transition, rather than unconditional destruction inside every `raw()` timeout:

1. Close candidate-tool admission. Record command timeout versus whole-invocation deadline, last active command and monotonic cutoff. Preserve current policy that a retired-worker timeout ends the attempt; do not grant extra coding time or silently resume the model.
2. Keep the container alive briefly for controller-only cleanup. Run the existing isolated trusted cleanup helper with a separate, strictly bounded cleanup deadline. Kill candidate processes, preserving only the verified init/supervisor and cleanup process; require evidence that no candidate writer remains. Cleanup must not invoke submitted scripts or import from candidate paths.
3. If cleanup succeeds, use a trusted isolated exporter while the tmpfs is still mounted. Export only editable source into a new controller-owned snapshot, validate before writing, reconstruct the protected scaffold from the frozen preparation, and commit hashes atomically. Remove the container afterward. Candidate-authored tests outside permitted source are telemetry, not submission material.
4. If cleanup, export, validation or container liveness fails, retain an explicit unavailable-final-artifact result and destroy the worker. Never relax bounds, follow links, execute candidate code to recover files, or award correctness from a stale snapshot.

This requires separating the trusted cleanup/export transport from `raw()`'s automatic retirement behavior, with a single owner for terminal cleanup. Every failure branch still needs bounded removal and confirmation of no leftover processes/containers. Do not let recursive cleanup timeouts repeatedly invoke cleanup or keep a broken worker available for subsequent tools.

The retained final artifact is the state when candidate writers were confirmed stopped, not necessarily a byte-perfect state at the nominal deadline instant. Record cutoff, cleanup start, writers-stopped and snapshot timestamps, plus cleanup lag. A partially written source file is valid evidence of an interrupted attempt; do not repair it. If strict deadline-instant snapshots become necessary, a separately validated freeze/export design is required.

Add an immutable last-known source snapshot after each already-quiescent tool call. Reuse the existing source-export/hash operation rather than add another full copy solely for hashing. Write outside candidate visibility and retain timestamps, source hash and originating call ID. This reduces evidence loss if a later command destroys the container, while remaining clearly distinct from final source. Bound retained bytes/count and record any retention eviction; a hash alone cannot recover an artifact.

Provider HTTP drain and candidate-source quiescence should be recorded independently. A late or missing usage response need not destroy an already sealed source snapshot. The model/tool channel must be closed and all provider resources settled before private grading. Keep incomplete usage and cleanup incidents explicit even when source is available; source availability does not prove token completeness or a valid completed handoff.

## Artifact and outcome semantics

| Evidence available | Permitted claim |
|---|---|
| Sealed source after writers stopped | Correctness of the terminal timeout snapshot, with cutoff/cleanup lag and censored completion time |
| Last-known snapshot before interrupted command | Correctness of that earlier checkpoint only; final correctness unknown |
| Hash without bytes | Source identity evidence only; no executable reconstruction or grade |
| Starter left in host preparation directory | Baseline behavior only; never the lost candidate result |
| No safe source | Final artifact unavailable; no correctness assertion |

A passing last-known artifact does not prove the later final state remained correct. A failing earlier artifact does not prove the candidate failed at the deadline. Preserve timeout, compile/test observations, source availability, cleanup validity and provider-usage completeness as separate fields. Do not conflate a source-retention defect with evidence against Kotlin, Haskell, testing support or typing strength.

## Required verification before adoption

Use deterministic fake lifecycle tests first, then bounded non-model container qualification on the pinned runtime:

- A command writes a known source file and times out: cleanup finishes, the source is exported before removal, and no writer survives.
- A command performs a partial write while background descendants attempt further writes: establish the writer-stop boundary and demonstrate a stable exported hash. Test process churn within existing PID limits, not an unbounded fork bomb.
- Whole-invocation deadline intersects a tool call; no next command is admitted, late records are retained, and there is exactly one terminal exporter/remover.
- Cleanup/export timeout, container exit, OOM/retirement and removal failure preserve known evidence without falsely claiming a final snapshot or silently continuing a campaign with leftovers.
- Source symlinks, hardlinks, special files, traversal names, excessive files/bytes and candidate modules shadowing trusted imports cannot escape the export boundary or hang the controller. Do not follow links into runtime or host paths.
- Demonstrate the actual tmpfs lifetime on this Docker version and image. Any proposed pause/copy variant must independently prove readable source, absent concurrent writes and bounded cleanup; documentation is not a successful local test.
- Successful handoffs retain equivalent source and grades; artifact-unavailable checkpoints never acquire a stale final grade. Last-known and final identities cannot be confused in reporting.
- Record instrumentation wall time separately and confirm no private oracle, expected values, provider credentials or host workspace are exposed to the candidate.

Freeze a new protocol/version, rerun capability qualification and review this boundary before inference. The current qualification cannot authorize changed worker lifecycle code.

## Scientific treatment and follow-up recommendation

For the original 56 cells, preserve missing final correctness as unknown and retain every observed token/time/tool/intervention record. Report artifact loss by language/model/test condition, including possible missingness related to long checking or compilation near deadlines. Do not drop these cells from denominators or turn them into automatic failures/successes. Give explicit bounds if summarizing correctness with unknown outcomes.

A focused new cohort for the missing-artifact conditions is scientifically useful **as a labeled operational follow-up**, not as replacement observations silently inserted into the original matrix. Choose the eligibility rule before running it: every original cell with unavailable final source caused by the identified retention path, regardless of apparent performance, language or testing condition. Use fresh sessions, the same public task/treatment and matched declared budgets; preserve original consumed effort separately and in combined cost accounting. No original private failures, reference fixes or candidate solution may enter the new prompts. Distinguish duplicate treatment labels from genuinely independent task instances.

Because the improved lifecycle changes measurement and the cohort is selected on missingness, do not pool its success rate with the original campaign as though no protocol changed. If the objective is a corrected cross-language comparison, prefer a fresh balanced cohort across all seven languages, both test conditions and both models under the new version, or at least prespecified matched controls. That is a separate budget/integration decision after the frozen campaign closes. Until such a cohort is qualified and run, the correct report is unknown final correctness, with the limitation visible—not an invented repaired result or estimated human labor.
