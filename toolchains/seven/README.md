# Offline seven-language runtime

The qualified runtime is the immutable image ID in
`configs/toolchain-seven.json`. `DockerWorker(..., runtime='seven')` uses it for
all seven languages, mounts no host runtime or dependency directories, and checks
its package inventory hash before candidate execution. Historical workers remain
available through `runtime='historical'`; historical receipts are unchanged.

The common profile remains two CPUs, 4 GiB memory with no swap, 64 PIDs, a 512 MiB
workspace and 64 MiB `/tmp`, network disabled, read-only image, and process cleanup
after each command. Java is capped to two processors, serial GC and a 768 MiB heap;
.NET sees two processors. Compiler dependencies live in the immutable image.
Cargo uses vendored locked dependencies, NuGet package sources are cleared in the
C# scaffold, and Kotlin uses the supplied Gson JAR without Gradle/network lookup.

`packages.lock` is the complete installed OS package closure, not merely the
requested top-level packages. The Gson 2.11.0 artifact hash is separately recorded
in the config. Rust dependency versions/checksums are in the existing ledger
Cargo.lock; `cargo vendor --locked --offline` produced `/opt/cargo-vendor`.
The base image is pinned by registry digest. The resulting image ID, not the
mutable development tag, is authoritative for this matrix.

To recreate the build context before qualification:

1. Run `cargo vendor --locked --offline --manifest-path tasks/ledger_engine/references/rust/Cargo.toml .runtime-build/cargo-vendor`.
2. Put the Gson 2.11.0 JAR at `.runtime-build/gson.jar`; verify its SHA-256 against
   the config before building. The original came from the existing local Gradle
   cache, never from a candidate workspace.
3. Copy this Dockerfile into `.runtime-build/` and run
   `docker build -t langbench-seven:dev .runtime-build`.
4. Extract `/opt/toolchain-packages.lock` and compare every package with the
   committed lock; compare the Gson hash and Cargo closure. This online acquisition
   recipe uses Arch mirrors and may resolve newer packages later. A changed
   closure/image is a new runtime requiring qualification, never a silent update
   to an in-progress matrix. Preserve/export the qualified image for exact reuse.
5. Record the immutable image ID and package SHA in a new qualification receipt,
   then run worker-boundary, installed-wheel and all-language native parity checks
   before freezing the matrix. Do not change the current config during collection.

Only third-party runtimes/libraries and package metadata enter the image. Task
starters, references, oracle cases, controller source and credentials are excluded
from its build context. Candidate source is staged separately into bounded tmpfs.
