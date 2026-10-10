# Elixir queue worker

Both variants use Elixir 1.18.4 / OTP 27 and exact locked Broadway 1.3.0,
BroadwayRabbitMQ 0.8.2, AMQP 4.3.0 and Jason 1.4.5. Base images are pinned by
digest. Runtime dependency downloads are unnecessary. BEAM uses two schedulers,
one dirty CPU and one dirty I/O scheduler, and four async threads, within the
common container budget.

```sh
docker build -t langbench-queue-elixir:reference scalability/workers/elixir/reference
docker build -t langbench-queue-elixir:starter scalability/workers/elixir/starter
```

`starter` is a working one-processor happy-path pipeline. It lacks bounded
retries/backoff and durable poison routing. Broadway already supplies supervision
and broker reconnection; those ecosystem defaults are intentionally retained.
`reference` adds finite HTTP retries, fixed backoff and a serialized confirmed
publisher. Its publisher has at most one request per bounded Broadway processor
waiting; callers do not time out and leave growing abandoned publish requests.
The shared sink owns durable deduplication.

Producer configuration deliberately omits `declare` and `bindings`, because the
worker has no topology permission. API sources:
https://hexdocs.pm/broadway_rabbitmq/BroadwayRabbitMQ.Producer.html and
https://hexdocs.pm/amqp/AMQP.Confirm.html. Keep reference sources out of candidate
workspaces and starter image contexts.

The immutable `lib/fault.ex` hook raises on the explicit handler-crash response,
before status classification and outside retry handling. Broadway catches the
callback exception and routes it through failed-message acknowledgement/requeue;
the container stays alive. Each variant's `fault-hook.json` identifies the source
and invocation. The runtime carries the builder's CA bundle because OTP's HTTP
client initializes TLS defaults even when the configured sink uses plain HTTP.

All seven 96-event reference qualification scenarios passed; the starter passed
the clean scenario. See [validation.json](validation.json) for exact receipt and
image identities. These are native reference checks, not model coding trials or
sustainable-capacity measurements. The handler hook is a recoverable work-item
exception; it does not prove uncatchable thread/child replacement.
