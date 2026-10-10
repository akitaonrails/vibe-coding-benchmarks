# Queue reliability, backpressure and engineering effort

Status: design and implementation track, added 2026-10-10. No Elixir/Rust/Rails comparative results exist. This is separate from the language typing experiment. The treatment is a language/runtime/framework ecosystem, including its documentation and defaults; results cannot isolate static typing.

## Questions and falsifiable hypotheses

Does an agent need less work to deliver a reliable bounded queue consumer using Elixir/OTP/Broadway than Rust with supported libraries or Rails/Bunny? At equivalent reliability and resource limits, what useful throughput does each generated system sustain? Does Ruby reach a resource or latency limit earlier for this workload? These are independent questions: a cheap-to-build system can have lower capacity, and a high-capacity system can be expensive to build.

Do not require other stacks to imitate OTP. Record supervision, ownership, cancellation, admission control, bounded buffering, recovery and restart policy as descriptive architecture features after grading. Similar solutions are not proof that all architectures converge, nor is a supervisor tree proof of reliable application semantics.

Primary-source motivation:

- OTP supervisors start, stop, monitor and restart child processes, with restart strategies and intensity limits. This supports a hypothesis about implementation effort, not automatic message durability. [Erlang supervisor principles](https://www.erlang.org/doc/system/sup_princ.html).
- Broadway combines backpressure, acknowledgement, batching, failure handling and graceful shutdown; its pipeline has a supervision tree. [Introduction](https://broadway.hexdocs.pm/introduction.html), [architecture](https://broadway.hexdocs.pm/architecture.html), [RabbitMQ producer](https://broadway-rabbitmq.hexdocs.pm/BroadwayRabbitMQ.Producer.html).
- Tokio documents bounded channels and cooperative shutdown. These are useful Rust primitives, not evidence that its completed applications need more work. [Channels](https://tokio.rs/tokio/tutorial/channels), [shutdown](https://tokio.rs/tokio/topics/shutdown), [Lapin AMQP client](https://docs.rs/lapin/latest/lapin/).
- Bunny supports manual acknowledgement, prefetch and connection recovery. Rails/Bunny must be allowed to use these facilities and multiple worker processes. [Bunny](https://github.com/ruby-amqp/bunny), [connection recovery](https://github.com/ruby-amqp/bunny/blob/main/docs/guides/connecting.md).
- RabbitMQ distinguishes publisher confirms from consumer acknowledgements; reconnect/retransmit can produce duplicates. Prefetch bounds outstanding deliveries, not every buffer in the application. [Reliability](https://www.rabbitmq.com/docs/reliability), [acknowledgements and confirms](https://www.rabbitmq.com/docs/confirms).

## Treatments and controls

Main stack arms: Elixir + OTP + BroadwayRabbitMQ; Rust + Tokio + Lapin (additional idiomatic supervision/retry libraries allowed); Rails + Bunny in a dedicated worker entrypoint. Ruby+Bunny without Rails is an additional control to distinguish framework overhead from Ruby itself. It must not silently replace the requested Rails arm. Freeze supported versions, dependency lockfiles, docs snapshots and container digests before attempts. Give equivalent working broker connections and happy-path consumer starters; do not supply a finished reliability solution to one arm only.

Use one independently configured RabbitMQ deployment per trial and an identical external sink/verifier. RabbitMQ itself uses Erlang, so any shared broker benefit belongs to all arms. First qualify the broker, sink and load generator above the offered load; otherwise label the capacity measurement infrastructure-limited. Do not compare Elixir's in-memory mailbox with Rust/Ruby durable delivery.

All application processes/threads and sidecars count against a common cgroup CPU and memory budget. Allow multiple Ruby processes and idiomatic BEAM schedulers/Rust tasks. Record idle framework footprint separately without subtracting it from runtime cost. Broker, verifier and generator have separate fixed budgets and telemetry. Dedicated local networks expose only benchmark services, with no internet or host service access during candidate execution. Never give candidate code the Docker socket or private evaluator files.

## Workload contract

Build a multi-tenant event processing worker. Events have immutable unique IDs, tenant IDs, payloads and a deterministic transformation. Producers publish persistent messages using confirms. The worker transforms each event and submits the effect to an HTTP sink, then acknowledges completion. The sink persists effect IDs transactionally; repeated submissions with identical content are idempotent, while a conflicting duplicate is an error. This is at-least-once delivery with externally deduplicated effects, not an unsupported end-to-end exactly-once claim. Count duplicate attempts even when the effect is deduplicated.

The evaluator owns the source event manifest and sink state. A successful accepted event must end as exactly one correct durable effect, or in the designated durable dead-letter path if the contract declares it poison. Every accepted ID must be accounted for after the drain deadline. IDs not accepted by the broker are producer failures, not lost consumer messages. Ambiguous publish confirms are retried with the same ID and tracked explicitly. Reject unrecognized effects, cross-tenant content, wrong transformations, silent drops and acknowledgements before durable completion.

Bound broker prefetch, active downstream requests, local queued work, retry work and total resident memory. Parameters are common externally supplied limits, not architecture prescriptions. Admission control may defer work to the broker but cannot hide an indefinitely growing broker backlog as sustainable throughput. Durable retries need a finite attempt/backoff policy and poison handling. A permanently failing message must not create a hot retry/restart loop or starve healthy tenants. SIGTERM stops new admission, drains or safely requeues unfinished work, and exits within the common deadline. SIGKILL tests crash recovery separately.

The sink can return retryable errors, hold a bounded number of connections, delay responses, commit an effect and drop its response, or reject poison payloads. Test-specific sink state and event manifests remain outside candidate visibility. Public requirements describe these failure classes; hidden trials vary timing and composition, not undocumented semantics.

## Hard scenarios

| Scenario | Interaction under test | Independent evidence |
|---|---|---|
| Steady state and staircase load | Useful throughput versus backlog and latency | Confirmed IDs, sink commits, queue depth and latency |
| Burst above capacity | End-to-end backpressure and bounded buffers | RSS, in-flight requests, broker unacked/ready, drain time |
| Slow or unavailable sink | Retry bounds, cancellation and recovery | Request concurrency, attempt rates, post-recovery backlog |
| Effect committed, response lost | Idempotency across ambiguous completion | One durable effect per ID, repeated request counts |
| Crash during processing | Redelivery, unacked work and worker replacement | Process death, subsequent completions, no missing IDs |
| Worker crash storm plus poison | Isolation and bounded restart/retry amplification | Healthy-tenant progress, restart/attempt rates |
| Broker disconnect/restart | Connection/channel restoration and delivery semantics | Broker event log, outstanding confirms, recovered IDs |
| SIGTERM while overloaded | Safe shutdown with pending effects | Exit deadline and eventual full accounting after restart |
| Multiple competing consumers | Work sharing and duplicate races | Duplicate attempts/effects and per-tenant progress |
| Long soak then recovery | Resource leakage, queue growth and tail latency | Time series, drain and repeat-run reproducibility |

A logical simulator is useful for unit testing the scorer; it cannot establish scalability, fault recovery or runtime superiority. These scenarios must run against real broker/worker processes and real network failures. Start with a single broker restart; replicated-broker availability and multi-host partitions are a separately qualified extension, never implied by single-host results.

Do not make global/per-key ordered delivery a hidden requirement. If ordering is added, make it a separate explicit task instance with identical partition and ordering rules in all arms.

## Measurement

Engineering outcomes: first-handoff complete correctness, correctness after each of the two fixed generic nudges, agent wall time, tool calls, build/test/repair cycles, input/cached/output/reasoning tokens with provider accounting, changed production/test lines and dependency additions. Keep tiny-prompt nudges separate from the full continuation cost. A later failure-informed optimization loop is a separate treatment with equal feedback and budget; it must not be mixed with unattended results.

Runtime outcomes: correctness-qualified useful events/sec, end-to-end p50/p95/p99 from scheduled producer arrival, oldest-event age, queue backlog slope, peak and steady RSS, CPU time per correct effect, downstream concurrency, duplicate attempts, missing/incorrect effects, poison handling, recovery time and healthy-tenant progress. Include unresolved events as deadline failures; latency percentiles of successes alone conceal losses. Use an open-loop arrival schedule and record generator scheduling lag to avoid hiding overload through coordinated omission.

Report absolute common offered-load curves first. Also characterize each artifact near its own measured saturation point, clearly labelled diagnostic. Sustainable capacity requires the declared latency target, bounded backlog/resources and all reliability gates over the full interval. A service that ACKs and drops work has zero qualifying capacity. Correctness failures remain in the engineering denominator even when no capacity number is valid.

Use at least two resource tiers and several message/downstream profiles: I/O-heavy baseline, mixed payload work, and a CPU-heavy control. Freeze numerical SLOs after infrastructure calibration, before scored model attempts. Do not tune the workload after observing which language wins. Runtime repeats use the same frozen generated artifact and measure scheduling noise; they are not independent AI coding samples.

## Experimental sequence and inference

1. Build the real broker/sink/generator/fault runner and native reference workers; validate against deliberately broken consumers (early ACK, duplicate effects, unbounded fan-out, poison hot-loop, lost recovery, unsafe shutdown).
2. Demonstrate that every scenario detects its intended defect, and that the generator/sink/broker are not the limiting resource in the chosen operating range.
3. Qualify stack dependency images and equally useful starters. Save immutable manifests and all infrastructure identities.
4. Run a small paired Astra-low calibration, initially with supplied tests. If all stacks trivially pass, strengthen a preregistered second development instance and recalibrate. Keep calibration separate from confirmatory data.
5. Freeze independent task instances, load/fault schedules, budgets and analysis. Expand to Astra-low / Sol-medium / Luna-high and supplied-tests/no-supplied-tests only after difficulty and cost are established.
6. Randomize stack order within model/instance/replicate blocks. Run runtime trials without concurrent compilation or other benchmark work. Report host contention and infrastructure-invalid runs with explicit reasons.

Present effort versus reliable capacity as a Pareto comparison rather than one arbitrary weighted score. Compare tokens/time to a common passing target, with failures censored at their budget, alongside probability of success. Also report performance among successful artifacts, labelled conditional to avoid survivor bias. A result supporting the hypothesis would be less agent effort for Elixir at comparable reliability/capacity; Rust winning peak capacity would not contradict that. Rails matching all targets would contradict the proposed smaller-scale limitation within the tested range. Report uncertainty across independent coding attempts and task instances, not across individual messages.

## Implementation boundary

The current JSONL ledger grader is deliberately unsuitable for measuring real concurrency. This track requires its own network-enabled, isolated multi-service runner and runtime evidence format, while reusing agent token/nudge accounting where the capability boundary is qualified. The seven-language typing roster is unchanged; Elixir is added to this separate ecosystem track. Until real execution, defect detection and infrastructure calibration pass, results remain development evidence and no stack superiority may be claimed.

### Development contract decisions

The first runnable slice uses finite per-delivery HTTP attempts and backoff, followed by requeue for healthy events whose transient outage persists; exhausting a local retry budget must not silently classify a healthy event as poison. The sink's explicit poison response is the sole poison classification. Publish poison events durably to the dead-letter queue with confirmation before acknowledging their input delivery. Concurrency limits apply across all worker processes. Fault validation records durable sink attempts/completions and broker state; final deduplicated effects alone cannot prove correct acknowledgement timing. Initial small runs qualify instrumentation only; load/duration controls are required before reporting capacity or soak results.

### Installation boundary

The Python wheel includes the `scalability` runner, public contract and trusted
broker/sink support assets. `queuebench --help` and
`python -m scalability.runner --help` expose the same CLI. Installed trials consume
prebuilt worker images. Building native worker images requires this source
checkout; those language-specific build trees are deliberately excluded from the
wheel. Worker images contain their own application and pinned dependencies, never
the private controller assets.

The first protected failure hook raises a work-item exception (a Rust task panic,
an Elixir callback exception, or a Ruby delivery exception). An outer failure
boundary may recover it. This measures handler-failure recovery; it does not
prove replacement of an arbitrarily killed BEAM process or Ruby thread. Those
stronger child-death faults, restart storms, replicated-broker partitions and
multi-host scaling remain separate extensions. A callback rescue can satisfy
this first contract without reproducing an OTP supervision tree; record that
outcome rather than redefining it as architectural convergence.
