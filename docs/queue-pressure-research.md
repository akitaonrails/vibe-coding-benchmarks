# Queue pressure: research and proposed next experiment

Research date: 2026-10-10. This document proposes the next implementation; it does
not report new load trials. Sources are primary project documentation. Live
`latest` documentation can describe newer versions than our pinned images:
implementation must verify APIs against the frozen dependency locks. Model work begins with the Kimi K3 / OpenCode GLM 5.3 subscription matrix,
then repeats that exact matrix with Opus 5.5 medium and Sol medium if quota
permits. Exact provider identifiers must be qualified before collection. No model
calls are part of this research.

## What the existing evidence permits

The [eight historical load trials](scalability-load-validation.md) offered 200
messages/sec with 4 KiB payloads and nominal 50 ms sink delay. All four
concurrency-eight arms produced about 93–95 effects/sec during publication and
then drained. All concurrency-64 arms left work pending, with over 1,100 recorded
sink intervals exceeding their one-second request timeout. These observations
show system overload, not a worker-language capacity ranking.

Inspection of `scalability/infra/sink.py` reveals one shared Python lock and
SQLite connection, with separate FULL-synchronous commits for admission metrics,
effects, and attempt completion. HTTP/1.0 closes connections. The publisher
confirms one message at a time. Sampling repeatedly reads the full effect and
attempt history and starts broker CLI processes. Each is a plausible shared
ceiling or measurement cost; the existing data does not isolate their individual
contributions. The transactional-snapshot and timeout-qualification corrections
improve interpretation without removing these ceilings.

The present business operation is small: parse JSON, multiply an integer, hash a
short payload, make one HTTP request. More messages exercise runtime duration;
they do not make the coding task much harder. To distinguish implementations,
measure a common useful service objective under bounded saturation and failures,
then measure agent effort to reach that objective. A tie is a valid result.

## What the primary sources change in the design

| Mechanism | Source finding | Consequence for this benchmark |
|---|---|---|
| Broker baseline | RabbitMQ PerfTest supports persistent messages, confirms, QoS, predeclared topology, rate control and confirm-latency metrics. Explicitly naming a queue shares work; unnamed queue setups can instead replicate messages. | Qualify the exact topology and durability mode. A fast auto-ACK/nonpersistent run cannot establish headroom for our manual-ACK persistent workload. [PerfTest](https://perftest.rabbitmq.com/) |
| Queue topology | A queue replica's hot path is limited to one CPU core. | Adding broker CPUs alone may not remove a single-queue ceiling. Keep one queue initially; test four identically configured partitions only if broker qualification shows that need, and change every arm together. [RabbitMQ queues](https://www.rabbitmq.com/docs/queues) |
| Prefetch | RabbitMQ applies a non-global QoS limit independently to consumers; combined channel/global limits have different semantics. | Freeze an aggregate outstanding-delivery budget. Four consumers with prefetch 256 are not equivalent to one with 256. Record consumers, channels and per-consumer limits. [Consumer prefetch](https://www.rabbitmq.com/docs/consumer-prefetch) |
| Broadway demand | Processor concurrency, demand, producer concurrency and batchers are distinct controls; telemetry exposes processor/message and batch spans. | Record the actual topology, callback time and message exceptions. Our current one producer, `max_demand: 1`, no-batcher configuration does not exercise every Broadway capability. Permit documented tuning within shared aggregate limits. [Broadway API](https://broadway.hexdocs.pm/Broadway.html) |
| Broadway recovery | Callback errors are normally contained without crashing processes. Producer failures have a different restart/resubscription path. | Separate callback exceptions from actual process termination. Do not infer supervisor effectiveness from a logged callback exception. [Broadway architecture](https://broadway.hexdocs.pm/architecture.html) |
| Tokio CPU work | Long blocking/CPU work in an async future can prevent other futures progressing. The blocking pool has a large default limit; bounded CPU parallelism needs an explicit control. Started blocking tasks cannot simply be aborted. | Include mixed CPU/I/O work after I/O qualification. Allow bounded blocking pools or other native strategies; observe queueing, healthy-message latency and shutdown, rather than requiring a particular executor. [Tokio spawn_blocking](https://docs.rs/tokio/latest/tokio/task/fn.spawn_blocking.html) |
| Ruby execution | CRuby threads in a ractor share a GVL; different ractors can execute in parallel. Blocking operations can run without the GVL. | Threads can be useful for I/O. Do not extrapolate CPU scaling from an I/O trial, or prohibit subprocesses/native libraries while allowing competing stacks to use multiple cores. Ractor/library compatibility remains a practical implementation choice. [Ruby ractors](https://docs.ruby-lang.org/en/3.4/ractor_md.html), [Ruby blocking operations](https://docs.ruby-lang.org/en/master/Thread.html) |
| Rails integration | Application code invoked by custom threads should use the Rails executor. | Retain real Rails boot/executor behavior; plain Ruby is a diagnostic framework-overhead control, not a replacement for Rails. [Rails threading guide](https://guides.rubyonrails.org/threading_and_code_execution.html) |
| Durable sink | WAL allows readers alongside a writer but still has one writer. Grouping changes in one transaction amortizes transaction cost. | Use a bounded group-commit sink; adding HTTP threads cannot make the SQLite writer parallel. Preserve ACK-after-commit semantics. SQLite's old disk-throughput examples are not forecasts for this host. [SQLite WAL](https://www.sqlite.org/wal.html), [SQLite transaction FAQ](https://www.sqlite.org/faq.html#q19) |
| Arrival measurement | A constant-throughput load generator should account for when a request was scheduled, avoiding omission of waiting time when a system stalls. | Drive an independent arrival schedule, retain late/unissued arrivals, and measure end-to-end latency from scheduled arrival. Do not make the producer wait for each effect. [wrk2 design](https://github.com/giltene/wrk2) |
| Restart limits | OTP supervisors enforce restart intensity; excessive failures can terminate a subtree. Monitors report actual process termination. | A crash storm can defeat default supervision. Record death, replacement and escalation instead of assuming OTP always recovers. [Supervisor principles](https://www.erlang.org/doc/system/sup_princ.html), [Erlang process monitors](https://www.erlang.org/doc/system/ref_man_processes.html) |

These sources explain mechanisms. They do not predict which current reference
or model-generated implementation will win.

## Small coherent implementation slice

Build a versioned pressure harness around the existing effect/deduplication
contract. Keep current qualification cases and receipts frozen. Implement only
three prerequisites before generating another comparative load table:

1. A durable sink with bounded group commit and measured headroom.
2. A bounded asynchronous publisher and constant-cost telemetry.
3. One common pressure schedule plus a source-reviewed child-death hook.

### Sink and generator qualification

Use HTTP keep-alive with a bounded asynchronous admission layer and one SQLite
writer. The writer gathers at most 64 effects or waits at most 2 ms, commits their
deduplicated effects atomically, then releases successful responses. Duplicate
requests waiting for the same identity join the same pending result; mismatched
content still fails. Neither admission nor batched enqueue constitutes durable
success. Keep SQLite WAL/FULL; group commit changes transaction granularity, not
the requested durability semantics. Bound pending admission at 4,096 requests;
reject excess with explicit 503 and count it. Avoid a second FULL commit for each
telemetry field: effect durability is authoritative, diagnostic spans use a
bounded separate buffer whose drops are explicit.

Record monotonic admission, writer-queue entry, commit-return and response-ready
times. Persist effect identity/content in the committed transaction; a
post-commit observation is telemetry, not an atomic durability proof across
power failure. A sink kill after commit but before response must still produce
one durable effect on retry. Test rollback, duplicate simultaneous submissions,
writer exceptions, final drain and recovery. Qualify the real durable path, not a
no-op sink. An optional no-op endpoint is diagnostic only.

Replace one-outstanding-confirm publication with a bounded window of 256
persistent messages and explicit confirms/nacks/returns. Preserve intended
arrival timestamps independently of confirmations. Once the window is full,
record delayed offered work; never silently lower the requested rate or drop
scheduled arrivals. Report offered, sent, confirmed, ambiguous and rejected
counts separately. Limit the bounded workload to 100,000 events and 64 MiB of
manifest data; split larger soaks into explicitly indexed bounded segments only
if their common arrival timeline and accounting are preserved.

Poll broker metrics at one-second intervals via an already-running management
client, and read incremental sink counters rather than exporting complete
history on every sample. Full manifest reconciliation and transactional snapshots
remain at trial end. Capture broker, sink, generator and worker CPU, memory,
throttling and I/O, not only worker resources.

Before candidate trials, require two independent controls:

- Broker-only PerfTest with our persistent/manual-ACK topology and payload size;
  sweep confirm/QoS windows with fixed resources. Save image ID, full arguments
  and metrics. This separates broker capability from HTTP sink behavior.
- Direct-to-sink trusted driver at twice the highest candidate offered rate,
  using the actual transformed HTTP effect body sizes, duplicate mix and
  downstream-delay configuration of that profile (the broker payload size is
  not the HTTP body size); require no rejection, complete
  reconciliation, p99 response-ready latency under 100 ms, and p99 generator
  scheduling lag under 5 ms. Confirm equivalent broker headroom at that rate.

The 2× margin and numeric thresholds are proposed local qualification criteria,
not published universal constants. Freeze them after infrastructure-only pilots,
before inspecting treatment comparisons. If a control fails, reduce the common
workload ceiling or improve that infrastructure and repeat all affected arms;
do not award a win to the stack that happens to load the sink less aggressively.

### A common staircase with saturation and recovery

Start with 1 KiB payloads and three tenants equally weighted. Use aggregate worker
limits of two CPUs, 1 GiB and 2,048 PIDs; allow any native thread/process/task
strategy within those limits. Main profiles: 8 and 64 active requests, aggregate
prefetch 4× that limit. Run 256 only after its own infrastructure qualification.
One work queue remains the default; no ordering guarantee is added. Before
every staircase, overload or fault scenario, serialize the entire actual
manifest and reject any scenario exceeding either 100,000 events or 64 MiB.
For example, 800/sec over 70 seconds at approximately 1,224 bytes/event already
exceeds 64 MiB before precise serialization; the proposed highest rung is not
automatically admissible. Compute a common admissible rate ceiling from actual
serialized manifests across all paired seeds, or first qualify indexed
segmentation. Overload schedules require the same check (their nominal total
is 80 times the base rate). Never truncate arrivals silently.

Initial rate ladder: 50, 100, 200, 400 and 800 events/sec, capped by demonstrated
infrastructure headroom. Each independent rung has 10 seconds warmup, 60 seconds
measured arrivals and 30 seconds bounded drain, on fresh broker/sink state.
Warmup events retain full accounting but are excluded from the measured latency
cohort. Stop after two failing adjacent rungs. Refine at most once between the
highest passing and lowest failing rate. Every arm receives the same frozen
ladder; no stack-specific rate tuning is used for the headline capacity curve.
Use three seed-paired repetitions in randomized blocked arm order. This is a
local capacity estimate, not a long-term availability claim.

Proposed passing rung: all published healthy IDs reconcile with no wrong effects,
no healthy DLQ, no unconfirmed publication ambiguity; at least 99% of scheduled
measured arrivals complete within 500 ms and 99.9% within 2 s; end-of-rung backlog
is at most one second of offered arrivals; backlog slope over the final 30 s is
at most 1% of offered rate; final drain completes within 30 s. Unresolved arrivals
remain SLO failures, not missing latency samples. Report all percentiles and
counts, not just pass/fail. A threshold failure is useful evidence even if all
arms fail. Candidate correctness failure, SLO failure and measurement-unqualified
must remain separate statuses.

After finding the common safe region, a bounded overload/recovery episode uses
30 s at the common passing rate, 10 s at twice that rate (still within validated
infrastructure headroom), then 30 s back at the initial rate plus 30 s drain.
Measure backlog growth, time to regain latency SLO, RSS recovery, retry
amplification and healthy-tenant progress. If no overload is induced, report it;
do not change pressure separately until one chosen stack loses.

### Actual child death, then a bounded crash storm

Keep three failure classes separate: callback exception (existing case), native
execution-unit death, and whole-container SIGKILL. A frozen adapter registers the
actual execution unit handling a selected delivery. Once that unit reaches a
pre-effect barrier, the fault controller triggers its termination and independently
observes exit/cancellation and a new execution generation. No success ACK is
allowed at the barrier. Maintain other-tenant arrivals throughout recovery.

For BEAM this can use monitored `Process.exit(pid, :kill)` against an actual
processor/child; for Rust an externally held task abort handle with awaited
cancellation of that specific task; for Ruby an actual delivery thread's kill
and join, or a child process SIGKILL if the solution chooses processes. These
are equivalent lost-work-unit stimuli, **not identical fault-containment models**:
BEAM kill, Rust task cancellation and Ruby thread termination differ in cleanup
and shared-state effects. Record which native boundary was killed, its ownership
of broker delivery, lifecycle evidence and collateral cancellation. Do not force
Ruby/Rust to mimic an OTP tree. Keep a separate all-arms OS-child isolation test
only if every arm explicitly implements that architecture.

Run one death first, then three deaths five seconds apart, then a ten-death
storm at 200 ms intervals as a separate resilience limit. Source/image/command
bound hook review remains mandatory. Record every scheduled termination time,
actual issued time, observed unit death and replacement generation separately.
When no registered live unit exists at the scheduled instant, count the fault
as unissued; do not claim a completed storm or silently shift its schedule.
Preserve crash generation and cause, child
replacement latency, connection churn, other-tenant longest completion gap,
redeliveries and unresolved work. The parent container must stay up for the
native-unit trial; controller restart cannot rescue it. Graceful escalation or
restart-intensity exhaustion is reported, not silently retried. Compare this
against baseline at both a common absolute load and separately at 70% of each
arm's independently qualified capacity; do not combine those two comparisons.

## CPU work, batching and framework tuning

The first slice remains I/O pressure to avoid changing every dimension at once.
Its next orthogonal extension is a fully specified fixed-work transform (bounded
integer-array parsing, validation and rolling checksum with exact 32-bit wrap),
with a fixed fraction of larger jobs mixed among small ones. Freeze identical
inputs and operation semantics, not equal milliseconds of work per language.
Do not busy-wait or sleep to simulate CPU. Measure small-job tails under heavy
jobs and scaling from one to two allocated CPUs. Permit native libraries and
process pools; record them because these are ecosystem results, not isolated
compiler speed. Optional tightly constrained language-only compute would be a
separate experiment.

Current Broadway does not batch HTTP effects. Do not add a batch API only to
Broadway. If application batching is studied, expose the same batch endpoint,
maximum 32 effects and 5 ms flush budget to every arm, and score per-effect
scheduled latency. Server-side group commit above is shared infrastructure and
requires no candidate batching. Preserve Bunny's built-in recovery and Rails'
executor. Document allowed tuning choices and give every agent the same tuning
budget; freeze chosen settings before private evaluation.

## Host limits, effort and gates

Only one capacity/fault trial may run on this host at a time. No concurrent image
builds, integration tests or coding-agent workloads during runtime collection.
Use disjoint CPU sets for worker and trusted infrastructure when available;
reserve at least two worker CPUs, two broker CPUs, four sink CPUs and two
publisher/controller CPUs, plus host margin. CPU quotas alone do not isolate
cache, disk or scheduler interference. Record hardware, CPU sets, throttling,
pressure-stall metrics and background load. If the host cannot reserve this
budget, reduce the single-trial allocation and requalify; do not parallelize
comparative trials to save time. Model generation may be parallel only outside
runtime measurement windows and within the provider/host limits.

Agent effort is elapsed active work, tool calls, nudges, successful test/build
checks and provider-reported usage when available. Missing provider usage is
unknown, not zero. Keep automatic retries and bounded adaptive nudges separate. Allow at most
two generic nudges, only for visibly unfinished work or a visible tool quirk;
do not force equal nudge counts after completed work. Record the visible trigger
and additional cost. No private-grading feedback or external repair loop may
steer collection.
The task asks agents to reach the public functional/resource contract, with
withheld seeds and fault schedules used only after collection. Reference runtimes
do not establish agent difficulty. Run the existing frozen T0/T1 comparison
separately from tuning-budget experiments; do not give public performance
telemetry only to one language. Root owns exact provider authentication, model identifiers and budget matching.
After the Kimi K3 / OpenCode GLM 5.3 matrix, repeat the exact matrix with
Opus 5.5 medium and Sol medium only if subscription quota permits; disclose
missing or incomplete cells rather than substituting models silently.

Phase1 decision requested: accept this research protocol for later queue work.
The immediate next implementation priority is the remaining language/model coding
matrix; this proposal does not authorize or schedule a new queue load campaign.
Before future pressure-harness coding, freeze the sink/publication protocol,
measurement schema and initial SLOs. An optional bounded diagnostic could compare
one direct-to-sink durable run with a broker-only control; it is not required
before the coding matrix and would not establish stack capacity.
Minimum verification owners: infrastructure author proves commit/confirm and
arrival accounting with adversarial fixtures; independent reviewer verifies
snapshot/cutoff and failure attribution; native authors prove real lifecycle
hooks; controller owner proves randomized plan/resource receipts. Real negative
controls must detect early ACK, unbounded admission, lost child work and
measurement-window truncation. Only after all four boundaries pass should queue-specific agent collection
and comparative capacity collection begin. The existing ledger coding matrix
can proceed independently. No finding requires Elixir to win.
