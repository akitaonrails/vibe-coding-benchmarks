# Queue worker: real-process development contract

This separate ecosystem track compares Elixir/OTP/BroadwayRabbitMQ,
Rust/Tokio/Lapin, and Rails/Bunny. A standalone Ruby/Bunny worker is an explicitly
separate optional control. No ordering is required. Passing this development
suite does not establish scalable capacity or comparative superiority.

## Deployment interface

Supply a prebuilt local Docker image and an optional command argv. The evaluator
runs that image on a new internal Docker network, as a long-running worker,
without host bind mounts, Docker socket, host networking, internet access or
private evaluator data. All child processes share the candidate container's
2-CPU/1-GiB/128-PID resource limits. Root filesystem is read-only; /tmp is a
128-MiB tmpfs. An image must be self-contained and must write runtime files under
/tmp. Multiple processes and threads are permitted within these limits. Dependencies
are installed while building the image, never fetched during the trial.

Environment variables (all limits aggregate across the whole worker container):

- `AMQP_URL=amqp://worker:PASSWORD@broker:5672/%2F`
- `INPUT_QUEUE=work`, `DLQ_QUEUE=dead`
- `SINK_URL=http://sink:8080/effects`
- `PREFETCH=32`: no more than 32 total unacknowledged input deliveries.
- `MAX_INFLIGHT=8`: no more than 8 simultaneous downstream HTTP requests.
- `REQUEST_TIMEOUT_MS=1000`: every HTTP attempt has this deadline.
- `MAX_ATTEMPTS=3`: at most 3 HTTP attempts for a single delivery before requeue.
- `RETRY_DELAY_MS=100`: at least 100ms before retrying a transient HTTP failure
  and before requeue after exhausting those attempts. No busy retry loop.
- `SHUTDOWN_MS=5000`: SIGTERM must stop admission and exit within five seconds.

Queues are predeclared durable classic queues. Consumer credentials permit read
on work and publishing through the default exchange, and do not permit
configure/delete or broker management. Publishing is contractually restricted to
dead. Queue purge is forbidden by the contract and detected through manifest
loss; RabbitMQ read permission alone cannot forbid that method. Do not declare queues. A separate publisher/controller owns topology
and publisher confirms. Source messages use delivery_mode=2. Worker DLQ copies
must also be persistent and use publisher confirms before acknowledging input.
The worker may reconnect indefinitely with bounded backoff after broker failure.

## Input and output

Each input body is a UTF-8 JSON object:
`{"tenant":"t0","id":"e000001","value":12,"payload":"ASCII text","poison":false}`.
Tenant/id are nonempty ASCII identifiers. Identity is the tuple (tenant,id).
Values are integers -1,000,000..1,000,000; payload is ASCII text <=64 KiB.
Inputs are well-formed; poison is a boolean. Duplicate deliveries are possible.

POST the following JSON object to SINK_URL:
`{"tenant":T,"id":I,"result":3*VALUE+7,"digest":SHA256_HEX(PAYLOAD_UTF8)}`.
Digest is lowercase 64-character hex. No other fields. The sink owns a durable
unique tuple identity. An identical repeated effect returns 200 and is idempotent;
a first durable effect returns 201. An incorrect/conflicting/unrecognized effect
returns 409, which is a correctness failure and must not be acknowledged as
success. Valid poison input is rejected by the sink with 422 regardless of effect
content; on 422 publish the ORIGINAL EVENT to dead with persistence and confirm,
then acknowledge input. Poison must produce no effect. Duplicate DLQ copies are
allowed and counted; every copy must match its original manifest event.

Only HTTP 200/201 mean a durable effect completed. Acknowledge an ordinary input
only after one of these responses. 503, transport errors and timeouts are
transient; retry with the common bounded per-delivery policy, then requeue
without acknowledging success. Do not classify healthy messages as poison after
retry exhaustion. A dropped response may occur after the effect committed;
redeliver/retry with the same identity and content. Other non-2xx statuses must
remain unacknowledged and must not cause a hot loop.

SIGKILL can happen at any point. After replacement/reconnection every confirmed
healthy source identity must eventually have exactly its expected effect; poison
identities must be accounted for by the durable dead queue. SIGTERM may drain
unfinished work within the deadline or safely requeue it by closing the channel.
The evaluator may restart a stopped worker to finish draining. Never hide work
in a non-durable local queue after acknowledging its input.

## Public failure classes and development gates

The real sink supports slow responses, temporary503, blocked attempts which
ultimately503 without committing, and commit-then-drop-response. Broker/worker
processes can stop and restart. The test schedule/control secret is private to
the controller; the candidate sees only ordinary responses. Effects, HTTP attempt
counts, current/peak request concurrency and durable dead-letter contents are
independently observed. Retry traffic and duplicate attempts are reported.

Default qualification scenarios publish96 messages (poison every17th where
specified), with a 60-second completion window plus a 30-second final drain:

1. Clean baseline, including the same local ID in two tenants.
2. Burst with50ms sink delay: bounded HTTP concurrency and eventual full drain.
3. Commit/drop-response on the first healthy attempt for each identity: replay
   must not corrupt or lose effects.
4. Sink blocks attempts without committing; after observing a real HTTP attempt,
   SIGKILL worker, release sink, restart worker; includes poison. This exposes
   early acknowledgements through manifest reconciliation, not self-report.
5. Broker restart while messages are outstanding, then consumer recovery.
6. SIGTERM with slow sink/backlog, check exit deadline, restart and drain.

Public requirements do not reveal a private event manifest or exact fault timing.
Every trial starts a fresh broker, sink, queues and worker. Only source events
with confirmed publication count as accepted; ambiguous confirms retain their
identity for explicit retry/accounting. Missing or incorrect effects, wrong DLQ
copies, excess HTTP concurrency and failure to drain are failed requirements.
The hard observed-concurrency gate uses only clean/slow responses shorter than
the request deadline. During cancellation/crash faults, surviving server handlers
may overlap new client requests; report that peak separately and do not mistake
it for proven client-side concurrency violation.
Generator/broker/sink startup failures are infrastructure-invalid, never worker
correctness failures. Scenarios whose intended fault was not triggered are
infrastructure-invalid, not a passing fault test.

Runner parameters may increase event count, offered arrival rate and duration
for exploratory offered-load studies. Record scheduling lag and unresolved
events. Monitoring runs concurrently with publication, but the initial
publisher uses one outstanding confirm, so scheduling lag must establish it can
actually sustain the requested rate. These controls alone do not qualify a
staircase/soak capacity measurement. Default96-message runs are qualification only:
no sustainable-capacity label is permitted without a separate calibrated
load/SLO/resource protocol and repeated controlled runtime trials.

## Version 1.1 addendum: logical-handler supervision

A seventh scenario, `handler_crash`, distinguishes internal handler recovery from
whole-container replacement. Once, for one designated healthy identity, the sink
returns HTTP503 with `X-Langbench-Fault: handler-crash` before committing any
effect. A supplied native test hook must raise/panic/exit the current logical
handler outside its ordinary HTTP-retry rescue path. The enclosing application
may supervise or catch/restart that handler idiomatically, but the controller
never restarts its container in this scenario. Rust uses an unwinding processing
task panic; Elixir raises inside the Broadway handler; Ruby/Rails raises outside
the inner delivery retry loop. Requeue/redelivery and healthy-tenant progress must
continue until full accounting, without a duplicate effect or lost input.

Hook source, its invocation path and source hashes require independent review.
The runner records the emitted fault header, available exception logs, unchanged
container process identity and post-fault healthy progress. Black-box success
alone cannot prove a native exception happened. Until an approved hook manifest
is supplied, receipts retain `hook_review_pending: true` and make no verified
internal-supervision claim. Whole-container SIGKILL/restart remains a separate
crash/replay test, never a proxy for this handler-supervision scenario.


## Explicit exploratory resource profiles

The numbers above are development defaults, not mandatory scalability ceilings.
Runner options may change `MAX_INFLIGHT`, `PREFETCH`, the candidate PID limit,
CPU and memory together under a frozen common profile. Every arm receives the
same selected limits. For example, concurrency sweeps of8/64/256 should use a
sufficient common PID budget (such as2048) so Ruby process/thread strategies are
not excluded by an accidental128-PID smoke ceiling. The runner scales the sink's
separate PID budget above candidate concurrency and records its independent
memory/CPU budget; infrastructure headroom still needs measurement, not assumption.
