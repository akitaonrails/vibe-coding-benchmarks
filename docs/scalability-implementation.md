# Real queue development runner

Status: implemented and qualified against seven real RabbitMQ scenarios and five
injected worker defects. This is a
separate ecosystem experiment, not an addition to the seven-language typing
roster. The worker contract is [scalability/CONTRACT.md](../scalability/CONTRACT.md).
No relative scalability or implementation-effort result is established.

The runner creates a private internal Docker network, fresh durable RabbitMQ and
sink volumes, a trusted publisher/controller, and one candidate worker container.
It publishes real persistent AMQP messages with publisher confirms and evaluates
real HTTP effects against a controller-owned manifest. The sink commits effects
into SQLite with a unique tenant/ID key before returning success. It exposes only
`/effects`; private control changes happen through controller-owned Docker exec,
not network-visible control endpoints or candidate environment secrets.

Dependencies are prepared before trials:

```sh
python3 -m scalability.runner setup
```

Setup pulls RabbitMQ 4.1.4-management and builds the trusted Python 3.12.11 image
with pika 1.3.2. Trials resolve local tags to immutable image IDs and never pull
images. Native worker images must be built separately from their pinned arm
contexts under `scalability/workers/`. The worker has no source bind mount, Docker
socket or private evaluator volume, and its offline runtime uses read-only root
storage with a bounded `/tmp`. Child processes share its CPU/memory/PID limits.
RabbitMQ workers cannot configure topology or use management APIs. Purging work
is forbidden by the contract and detected as loss; read permission cannot itself
prevent RabbitMQ's purge method.

Run an existing native image, or the trusted Python infrastructure reference:

```sh
python3 -m scalability.runner run langbench-queue-rust:reference results/queue-rust-clean --scenario clean
python3 -m scalability.runner run langbench-queue-infra:dev results/queue-infra-kill --scenario kill_poison --command /infra/trusted_worker.py
```

The infrastructure reference is **not a language treatment**. Its purpose
is to validate orchestration and defect detection. Native Elixir/Broadway,
Rust/Tokio/Lapin and Rails/Bunny workers are the requested treatment arms. Plain Ruby/Bunny is a fourth arm controlling for Rails framework overhead. References were authored with coding-agent assistance during benchmark development; they are not blinded, budget-matched coding attempts, and their development effort cannot establish the engineering hypothesis.

Scenarios are `clean`, `slow`, `lost_response`, `kill_poison`, `broker_restart`,
`shutdown` and `handler_crash`. Default qualification uses 96 events, a 60-second completion
window and 30-second final drain. Fault scenarios first observe a real sink
attempt and broker outstanding work where applicable; a requested but untriggered
fault is infrastructure-invalid. Candidate images that cannot start or workers
that exit before processing are candidate failures, while broker/sink setup
failures are infrastructure-invalid. No external broker or database is touched.

The development runner records publication confirmations and ambiguous-confirm
retries, scheduled/confirmed arrival timestamps, pre-commit effect transaction timestamps,
completed-effect latency percentiles plus unresolved counts, HTTP attempts,
poison deadletters, broker-ready/unacked samples and Docker resource samples.
It compares full content and identity, reports missing and incorrect outputs,
and rejects uncompleted drain. Provider/model inference is not part of this
runtime runner; later integration must preserve the existing fixed-nudge and
token-accounting controls.

HTTP concurrency has a deliberate measurement limit: the sink can retain a
handler after its client timed out or died. The observed processing-bound check applies only to clean/slow trials whose
recorded attempts all finish below the request timeout. Any unfinished or
timeout-exceeding span makes the trial `measurement_unqualified`, with cause
unattributed: the consumer may itself overload the sink. Raw correctness and
drain outcomes remain in the receipt; an unknown bound cannot yield a qualified
pass. Even below the timeout, sink intervals exclude admission/network time and
final commit completion, so they do not verify actual client concurrency. Fault-mode server-handler peaks
are reported, not treated as proof of excessive client concurrency. Per-delivery
retry caps, local buffer bounds and precise backoff cannot be fully inferred from
sink requests; the receipt explicitly does not claim those are verified.

`--count`, `--rate`, `--duration`, `--payload-bytes`, `--cpus`, `--memory-mb`, `--max-inflight`, `--prefetch` and
`--pids` enable exploratory
workload/resource variations. Monitoring runs concurrently with publication and reports observed completion
rate during that window, backlog slope, cgroup CPU/memory and summed process RSS.
The publisher uses one outstanding confirm: measured scheduling lag must show
that it can sustain the requested rate. These controls are **not by themselves
a qualified staircase/soak scalability harness**. Every receipt sets
`scalable_capacity_qualified: false`; do not divide drained events by an offered
load window and call the result sustainable throughput. Continuous telemetry,
infrastructure headroom, repeated trials and preregistered SLOs remain necessary.

The 25 focused regressions in `tests/test_scalability.py` pass. The trusted
infrastructure worker passed all seven real-process scenarios. Actual defective
workers were detected for early ACK, incorrect effects, poison retry loops,
missing reconnection and unbounded fanout; the last produced 31 simultaneous
sink operations against the limit of eight. These are evaluator qualification
results, not language rankings. Native reference qualification is recorded
separately. Eight [10,000-message exploratory trials](scalability-load-validation.md)
now exercise two concurrency profiles. The lower profile drained correctly; the
higher profile exposed timeout overlap and inconsistent historical snapshots.
The measurement defects are corrected below, but sustainable capacity remains
unqualified.

Initial readiness, Docker address-pool and sink-counter failures are preserved
in local receipts. The counter originally included handlers after exposing their
completed response, falsely penalizing bounded native workers. It now ends the
processing interval before exposing the response; clean/slow qualifications were
repeated. Fault-mode orphan-handler overlap remains a separate measurement.


The handler-crash addendum tests a native work-item exception without controller
replacement of the whole container. Source-reviewed hooks and their hashes are
required to interpret this as a supervision test. Until approved, the runner
records header delivery, logs, unchanged container identity and healthy progress
but marks hook review pending. Container kill/restart alone does not test OTP's
internal supervision advantage.


A controller-owned `--hook-review FILE` may record approval after source review.
Its JSON must contain `approved: true`, the exact `worker_image_sha256`, hook
`source_sha256`, `trace_marker`, the exact `command` array and a
`reviewed_invocation` description. An image or command mismatch is refused. This documents reviewed-source plus runtime-trace support;
it is not black-box proof against an adversarial replacement image.


The default concurrency8/prefetch32/PID128 profile is only qualification. Larger
common profiles can use concurrency64/256 and PID2048 to let each ecosystem
choose its process/thread/task strategy. The sink receives a separate larger PID
budget and configurable `--sink-memory-mb`; receipts retain both application and
infrastructure limits. A resource-ceiling comparison requires equal frozen
profiles and demonstrated broker/sink/generator headroom.


Network creation requires Docker's isolated IPv4 gateway mode and fails closed
if unavailable. A real host canary probe verifies that the trial network cannot
reach host service addresses before candidate execution; the qualification
receipt recorded 31 blocked host addresses. No host firewall or foreign Docker
resource is changed. Images declaring Docker volumes are rejected. Container
names are registered before startup, so failed entrypoints are still cleaned up;
absence during owned-resource cleanup is harmless. Container log rotation and
controller log capture have explicit byte limits. Work/dead queues reject
publication above their configured 64 MiB retained-message limit, and the broker
caps individual messages at 128 KiB. These controls are not a host disk quota.

Inputs use a recorded random seed unless `--seed` is supplied. Manifest values
and payloads vary with the seed while deliberate cross-tenant ID collisions
remain. Oversized duration/rate products and payload budgets are rejected, never
silently shortened. The installed `queuebench` entry point also supports these
commands and includes trusted infrastructure assets; native image build contexts
remain in the source checkout.


Every sink snapshot now reads effects, timestamp rows, attempts and peak metrics
inside one explicit SQLite read transaction. Its view is fixed at the first
SELECT; acquisition start/end timestamps bracket that cutoff. The final snapshot
can include work completed after the preceding drain poll. Broker and deadletter
observations happen separately and are not a cross-service atomic snapshot.
A deterministic WAL writer regression commits between the reader's queries and
verifies that effect counts and timestamp rows still represent one view.

Latency uses the timestamp recorded before the effect transaction's commit,
for effects subsequently visible as committed. It excludes commit completion
latency and must not be labeled exact durability completion. Attempt end times
also precede the final attempt-record commit and response transmission. Receipts
record the runner source SHA-256 so changes to these measurement rules can be
identified independently of unchanged container image IDs.
