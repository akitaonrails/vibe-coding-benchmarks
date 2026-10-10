FROM rust:1-bookworm@sha256:9a73a5088750b4c95158ab26629c854c3d6fc4b173cb7bc8079ad252d8ed7bfa AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
ENV CARGO_BUILD_JOBS=2
RUN cargo build --release --locked
FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
COPY --from=build /app/target/release/queue_worker /usr/local/bin/queue-worker
USER 65534:65534
ENTRYPOINT ["/usr/local/bin/queue-worker"]
