# seal-v1 implementation and evidence

Date: 2026-10-11. This opt-in correction applies to future cohorts. It does not alter the original 56 receipts, candidate sources, task fixtures or outcomes. No model inference or provider-account action was used for this validation.

## Verification plan and ownership

The harness lane owns three claims: retain actual terminal source after a command timeout; keep candidate-source availability separate from provider-usage drain; fail closed when writers or submitted paths cannot be trusted. The evidence path uses deterministic lifecycle fakes plus bounded container checks on the already pinned seven-language image. Historical worker tests and subscription tests cover the surrounding unchanged interfaces. Independent review is a separate gate.

## Implemented boundary

`DockerWorker(..., retention='seal-v1')` is explicit; the default is `legacy`. `qualify_provider` and `run_subscription` accept the same option, and the selected policy appears in worker qualification bindings. Adapter source binding now includes `worker.py`. A new qualification is required for future model runs.

On a candidate command timeout, `raw()` retains the running container only for the opt-in terminal cleanup path. `execute()` closes candidate admission, records the deadline and observation timestamps, and invokes the existing bounded trusted process cleanup. Once candidate writers are stopped, an isolated exporter reads bounded editable source while the tmpfs is still mounted. It rejects symlinks, hardlinks and special files. Only afterward is the container removed. A cleanup or export failure retains the timeout and reports unavailable source.

`retained_source` points to a controller-owned temporary artifact, never a candidate-visible mount. `retention_receipt` records policy, source digest, cutoff, timeout observation, writer-stop time, seal time and seal lag. The worker context releases this temporary artifact after its caller has copied the source. Candidate execution cannot resume after terminal admission closes.

`subscriptions.capture_invocation(worker, workspace, invocation)` copies only this sealed source onto the trusted host preparation and marks `artifact_kind='terminal_sealed'`. It never calls the model or grader. If only the HTTP transport drain failed but candidate dispatch settled, it can seal source independently; cleanup invalidity and incomplete token usage remain explicit. If bridge dispatch did not settle, it refuses to create a new seal and records unavailable source. No stale host starter receives a final grade.

The artifact describes state when writers stopped, not an instantaneous snapshot at the nominal deadline. The recorded lag makes that limitation measurable. The actual command can leave partially written source; the collector does not repair it. This change does not implement a persistent last-known cache for arbitrary container/OOM disappearance; those losses remain unknown unless a terminal seal was obtained. It does not use pause/docker-cp, writable host mounts or privileged candidate execution.

## Decisive checks

`tests/test_artifact_retention.py` covers:

- Actual Docker command timeout with known source plus a background writer: writers are stopped, source survives tmpfs removal, subsequent candidate calls are rejected and the copied source matches the sealed digest.
- Actual Docker source capture with a simulated transport-only drain failure: source is retained while `quiescent=false` and incomplete usage evidence remain unchanged.
- Actual source symlink and hardlink submissions: no artifact is accepted.
- Fake unsettled bridge: no exporter runs and no stale artifact is claimed.
- Fake trusted-cleanup failure: no export is attempted; the candidate timeout remains recorded.

The transport-drain test controls the failing transport state; it is not a claim that a live provider timed out during this test. The source/runtime half is a real bounded container execution. Existing transport lifecycle tests separately cover handler drain and cancellation.

Observed checks during implementation: nine existing worker tests passed; 35 subscription-focused tests passed; the final retention-focused run passed seven tests in 3.179 seconds, including failed-removal verification (the worker remains marked alive and raises). No benchmark-named containers remained after the preceding bounded checks. Broader repetition is unnecessary unless review changes source or exposes a new failure mode.

Private grading still occurs only after provider and worker teardown. Later cohort eligibility and statistical treatment remain governed by [the artifact-retention follow-up](artifact-retention-followup.md); this instrumentation change does not retrospectively replace missing observations in the original campaign.
