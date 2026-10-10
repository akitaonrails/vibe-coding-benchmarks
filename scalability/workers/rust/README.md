# Rust queue worker

Both variants use Tokio 1.53.2, Lapin 4.12.1 and reqwest 0.13.5, pinned with a
Cargo lockfile. The runtime uses two Tokio worker threads under the shared CPU
budget. Base images are pinned by digest. Runtime requires no package download.

Build from each isolated variant directory:

```sh
docker build -t langbench-queue-rust:reference scalability/workers/rust/reference
docker build -t langbench-queue-rust:starter scalability/workers/rust/starter
```

`starter` is a functioning sequential happy-path consumer. It deliberately lacks
bounded retries/backoff, durable poison routing, reconnection and explicit graceful
shutdown. `reference` uses bounded concurrent futures, manual acknowledgements,
confirmed persistent poison copies and reconnect/backoff. SIGTERM cancels active
requests and exits; broker redelivery preserves unacknowledged work. The common
sink provides idempotency; this worker does not claim exactly-once delivery.

Dependency APIs checked against https://docs.rs/lapin/4.12.1/lapin/ and
https://docs.rs/reqwest/0.13.5/reqwest/. Do not include `reference` sources in a
candidate workspace or image context.

The immutable `src/fault.rs` hook panics on the explicit handler-crash response.
Each reference delivery runs as a bounded Tokio task. Its join failure closes the
AMQP session, aborts sibling handlers, and enters the existing reconnect loop;
the process remains alive and unacknowledged messages are redelivered. Source
hashes and invocation descriptions are in each variant's `fault-hook.json`.

All seven 96-event reference qualification scenarios passed; the starter passed
the clean scenario. See [validation.json](validation.json) for exact receipt and
image identities. These are native reference checks, not model coding trials or
sustainable-capacity measurements. The handler hook is a recoverable work-item
exception; it does not prove uncatchable thread/child replacement.
