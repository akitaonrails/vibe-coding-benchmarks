# Rails/Bunny arm

The pinned Rails gem is installed. The entrypoint boots a real Rails::Application
with Active Model, Active Job and Action Controller railties; each delivery runs
inside Rails.application.executor.wrap. This is a background worker application,
not a web server. It does not route deliveries through Active Job, which would
introduce another queue and acknowledgement boundary. The paired plain Ruby arm
uses the identical worker algorithm without application boot or executor wrapping.
This control makes the framework distinction explicit; it does not represent every
possible Rails queue architecture.

Build: `docker build -t langbench-queue-rails:dev scalability/workers/rails/reference`.
Runtime is UID65534, self-contained and compatible with a read-only root plus
/tmp. Logs go to stderr; Rails temporary/log paths target /tmp. Dependencies are
pinned in Gemfile.lock and the Ruby base image is pinned by digest.

The reference passed all seven real 96-event broker/sink development scenarios; the starter passed clean96. See `docs/queue-ruby-rails-validation.json`. Clean/slow receipts use corrected sink processing counters. No throughput,
reliability or language superiority is claimed from source inspection or boot.

The clean-path starter lives under `starter/` and omits application retry and confirmed DLQ handling while retaining Bunny connection recovery.
The supplied handler-crash hook has a frozen source hash in `fault-hook.json`;
independent review was bound to each reference image before the fault trial.
