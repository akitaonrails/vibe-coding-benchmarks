# Plain Ruby/Bunny control

This optional framework control shares its reference delivery algorithm verbatim
with the Rails/Bunny arm. It boots Bundler and the worker directly, without Rails.
Bunny manages a single bounded consumer work pool, broker recovery, QoS restoration
and stale delivery tags. Every HTTP request has one overall timeout; Ruby Net::HTTP
internal retries are disabled. DLQ publication uses a separate serialized confirm
channel. SIGTERM exits immediately, closing TCP and returning unacknowledged work
to RabbitMQ. No local durable state or early acknowledgement is used.

Build from the reference directory: `docker build -t langbench-queue-ruby:dev scalability/workers/ruby/reference`.
The runtime image is self-contained and runs as UID65534 with a read-only root.
All seven real 96-event development scenarios passed; see `docs/queue-ruby-rails-validation.json`. The clean/slow verdicts use corrected sink processing counters.
This is a reference prototype, not model-produced code or capacity evidence.

The clean-path starter lives under `starter/` and omits application retry and confirmed DLQ handling while retaining Bunny connection recovery.
The supplied handler-crash hook has a frozen source hash in `fault-hook.json`;
independent review was bound to each reference image before the fault trial.
