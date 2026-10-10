FROM archlinux@sha256:b4df475619469581537637ceaace6075f4912ea1cd6db6b99d463e3a72969d04
RUN pacman -Syu --noconfirm && pacman -S --noconfirm ghc haskell-aeson dotnet-sdk aspnet-targeting-pack kotlin jdk-openjdk typescript rust ruby ruby-json python gcc && pacman -Q > /opt/toolchain-packages.lock && pacman -Scc --noconfirm
COPY gson.jar /usr/share/java/gson.jar
COPY cargo-vendor /opt/cargo-vendor
RUN mkdir -p /opt/cargo && printf '[source.crates-io]\nreplace-with = "vendored-sources"\n[source.vendored-sources]\ndirectory = "/opt/cargo-vendor"\n' > /opt/cargo/config.toml
ENV CARGO_HOME=/opt/cargo CARGO_NET_OFFLINE=true DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 DOTNET_GENERATE_ASPNET_CERTIFICATE=false DOTNET_NOLOGO=true DOTNET_PROCESSOR_COUNT=2 JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount=2 -XX:+UseSerialGC -Xmx768m" PYTHONDONTWRITEBYTECODE=1
