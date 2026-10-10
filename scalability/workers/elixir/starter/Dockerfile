FROM elixir:1.18.4-otp-27-slim@sha256:1dda2077640e381b35cf005bc6567c41e7ee26243c7b0c9e4b602fcccf68675f AS build
ENV MIX_ENV=prod ERL_FLAGS="+S 2:2"
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
RUN mix local.hex --force && mix local.rebar --force
COPY mix.exs mix.lock ./
RUN mix deps.get && mix deps.compile
COPY lib ./lib
RUN mix compile --warnings-as-errors && mix release
FROM elixir:1.18.4-otp-27-slim@sha256:1dda2077640e381b35cf005bc6567c41e7ee26243c7b0c9e4b602fcccf68675f
COPY --from=build /etc/ssl/certs /etc/ssl/certs
ENV ERL_FLAGS="+S 2:2 +SDcpu 1 +SDio 1 +A 4" RELEASE_TMP=/tmp
WORKDIR /app
COPY --from=build --chown=65534:65534 /app/_build/prod/rel/queue_worker ./
USER 65534:65534
ENTRYPOINT ["/app/bin/queue_worker", "start"]
