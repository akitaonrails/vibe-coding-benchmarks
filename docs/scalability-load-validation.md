# Sustained queue workload: development evidence

Date: 2026-10-10. This validates a real load experiment and identifies measurement
limits. It is not a language ranking, maximum-capacity result or controlled AI
coding trial. The four reference implementations were developed with coding-agent
assistance while building the benchmark.

## Frozen workload

The [development plan](../configs/queue-load-development.json) uses 10,000 messages
per trial, 4,096-byte payloads, seed 20261010 and a scheduled 200 messages/second.
The shared durable sink adds a nominal 50 ms delay. Every worker receives two
CPUs, 1 GiB memory and 2,048 PIDs. Two profiles allow 8/64 active downstream
requests and 32/256 unacknowledged deliveries. The sink gets two CPUs and 1 GiB;
RabbitMQ gets two CPUs and 1 GiB. The sink PID allowance grows with concurrency
and is identical across stacks within each profile.

Trials run sequentially in Elixir, Rust, Rails, Ruby order at concurrency eight,
then the same order at 64. Benchmark builds/tests are paused during collection.
This is a shared host, not demonstrated contention-free hardware. There is one
trial per cell; order is fixed, not randomized. All cells use the same manifest.
The workload and sequence were fixed before the first result; the plan file was
serialized during collection from that command.

Repeat a workload cell with the current runner after building its pinned worker image and running infrastructure
setup. Historical collection used commit `7a510e3`; the current runner includes
the measurement corrections below, so this is not an exact historical replay:

```sh
python3 -m scalability.runner run langbench-queue-elixir:reference results/new-elixir-c8 \
  --scenario slow --count 10000 --rate 200 --payload-bytes 4096 --seed 20261010 \
  --max-inflight 8 --prefetch 32 --pids 2048 --cpus 2 --memory-mb 1024 \
  --sink-memory-mb 1024 --deadline 90 --drain-seconds 30
```

Use `--max-inflight 64 --prefetch 256` for the second profile. Destinations must be
new. Tags resolve to immutable image IDs in each receipt. The 90+30 second
completion allowance follows publication; the total trial is not a 90-second
soak.

## Results

All eight trials accepted 10,000 source messages. All four eight-handler runs
finished with 10,000 correct effects, no wrong effects, no duplicate HTTP attempts
and an empty work queue. All four 64-handler runs reached the deadline with work
still pending; those high-concurrency measurements are **unqualified** for stack
capacity or client-concurrency conclusions.

| Stack | Handlers | Correct effects / 10,000 | Effects/sec during publication | Backlog growth/sec | Total observed seconds | Peak worker MiB | Drained |
|---|---:|---:|---:|---:|---:|---:|---|
| elixir | 8 | 10,000 | 94.8 | 100.2 | 151.3 | 135.3 | Yes |
| rust | 8 | 10,000 | 94.6 | 97.8 | 151.4 | 16.0 | Yes |
| rails | 8 | 10,000 | 92.7 | 99.7 | 154.9 | 79.2 | Yes |
| ruby | 8 | 10,000 | 92.5 | 100.1 | 154.7 | 38.2 | Yes |
| elixir | 64 | 7,915 | 84.8 | 106.6 | 171.1 | 160.7 | No |
| rust | 64 | 8,151 | 88.2 | 100.5 | 170.8 | 22.6 | No |
| rails | 64 | 8,108 | 88.5 | 101.3 | 171.2 | 87.0 | No |
| ruby | 64 | 8,081 | 88.0 | 100.8 | 170.9 | 60.0 | No |

“Total observed seconds” begins just before publication and ends at the final
drain/deadline observation. It includes the approximately 50-second publication
window; it is not the duration of drain alone. At eight handlers, post-publication
drain took approximately another 100–104 seconds. Throughput is the change in
durable effect rows over publication-window observations, not total effects
divided by the 50-second offered-load window. Memory is the worker cgroup peak,
including its processes and accounted memory; it is not a language-wide footprint
estimate.

All cells accumulated backlog while 200 events/sec were offered. The generator published all 10,000 messages in approximately 50 seconds per
trial. Maximum recorded scheduling lag ranged from 0.23 to 200.76 ms across the
eight runs, with no ambiguous confirms. These are observed scheduling bounds,
not proof of additional generator, sink or broker headroom. Similar completion
rates across the stacks suggest investigating a shared bottleneck, without
identifying its cause from these measurements alone.

At eight handlers, success-only p99 scheduled-arrival-to-pre-commit timestamps
were roughly 99–103 seconds. At 64 handlers, each run had 1,106–1,198 observed sink
spans of at least one second, duplicate attempts, and 1,849–2,085 unresolved
messages. Reporting latency only for successes would conceal those unresolved
messages. Raising concurrency did not improve this particular system under test;
that is not a maximum-capacity finding about any language or framework.

The [sanitized evidence](queue-load-validation.json) records original receipt
hashes, image IDs, common manifest commitment, full metric summaries, source
inventories and explicit interpretation corrections. Raw receipts stay in the
ignored `results/queue-load-*` directories. They were collected with the runner
source in commit `7a510e3`, before the measurement corrections below. Original
`valid_development` and concurrency fields are retained as historical values;
the summary separately marks all four 64-handler cells `measurement_unqualified`.


## Measurement defects exposed by the larger profile

The initial runner read effects, timestamps and attempts with separate SQLite
queries outside a read transaction. A busy final snapshot could therefore contain
one more effect timestamp than effect row. The recorded pre-correction receipts
are preserved; their internally mismatched counters must not be silently repaired
or treated as one exact observation.

The 64-handler profile also produced sink processing spans longer than the
one-second client timeout. Timed-out requests can remain in the server while the
client starts a replacement. Server-handler overlap then cannot determine whether
the client violated its concurrency bound. A slow response may also result from
candidate-induced overload, so this finding does not attribute cause solely to
infrastructure. Missing/drained outcomes remain separate evidence; an unknown
concurrency measurement cannot become a qualified pass.

The sink's `committed` timestamp is taken immediately **before** `DB.commit()`.
Historical latency values therefore measure scheduled arrival to a pre-commit
transaction timestamp, underestimating durability completion by an
unmeasured amount. Attempt finish timestamps also exclude their final recording
commit and response overhead. They can expose timeout headroom problems, but
short recorded spans do not prove the whole client round trip stayed below its
timeout.

The corrected runner now uses one explicit SQLite read transaction for all
snapshot queries, records the snapshot acquisition interval and runner source
hash, and labels the latency basis accurately. Timeout-overlapping or unfinished
observations produce `measurement_unqualified`, with cause unattributed and no
qualified pass. `http_concurrency_verified` is never asserted; the separate
observed sink-processing-bound field describes the narrower evidence.

Validation: 25 focused tests passed, including a deterministic concurrent WAL
writer committing between snapshot queries. A fresh real clean run passed 96/96
with 96 matching timestamps and no cleanup errors. Rescoring preserved historical
overlap observations retains the incomplete-drain and missing-effect evidence
while retiring unsupported client-limit attribution. Independent review and the full 133-test project regression suite passed.
The eight historical load trials were not silently replaced with corrected runs;
the [evidence file](queue-load-validation.json) separately records correction
validation.

## What this does and does not establish

This is substantially more runtime work than the 96-message qualification: each
cell carries about 39 MiB of payload and tens of seconds of scheduled arrivals.
That validates real backpressure and resource measurement; it does not by itself
establish a difficult coding task. Reference application source is small because
libraries provide much of the machinery:

| Stack | Starter source lines | Reference source lines |
|---|---:|---:|
| Elixir | 56 | 162 |
| Rust | 93 | 203 |
| Ruby | 56 | 128 |
| Rails | 74 | 146 |

These are physical lines in `.ex`, `.exs`, `.rs` and `.rb` files, including comments,
blank lines and native project/application configuration, excluding dependencies,
lockfiles and generated build trees. They are not tokens, implementation effort,
or a measure of semantic difficulty.

The small reference qualification covers seven scenarios: clean, delayed sink,
commit with response loss, worker kill with poison messages, broker restart,
shutdown under backlog, and a source-reviewed handler exception. Five real
broken consumers establish that the evaluator detects early acknowledgement,
wrong effects, poison loops, missing reconnection and unbounded fanout. A handler
exception is not an arbitrary uncatchable child-process death or a crash storm.

The trusted sink currently uses Python’s threaded HTTP server and serialized
SQLite transactions with full durability. Its HTTP/1.0 responses close connections.
These choices can impose a shared service ceiling or connection overhead; similar
worker rates do not prove which component is limiting. Full sink/producer/broker
headroom remains unqualified.

Before comparing sustainable capacity, qualify broker/sink/generator headroom,
add repeated randomized load staircases and longer soaks, and freeze latency and
recovery SLOs. CPU-heavy and mixed-work profiles are needed alongside this
I/O-heavy case. Before comparing agent effort, connect the queue workspace and
public test controls to the qualified subscription adapter, preserve unattended
and fixed-nudge checkpoints, and collect independent budget-matched attempts.
The current queue runner does not perform that model collection. Built-in
Broadway/Bunny recovery stays available; do not manufacture extra work by removing
one ecosystem's defaults or require every solution to imitate OTP.

A valid Elixir advantage would be less measured coding effort at a common passing
reliability/capacity target. Merely using a supervisor tree, having fewer reference
lines, or eventually draining a backlog is insufficient evidence.
