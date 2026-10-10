# Seven-language ledger expansion readiness

Inspected 2026-10-10. This is a readiness plan, not qualification evidence. No new
port was implemented, package installed, container built or model called for this
inspection. The reference project at `~/Projects/llm-coding-benchmark` was read only.

The proposed matrix is the existing `ledger_engine` instance × seven languages
(Rust, Haskell, C#, Kotlin, TypeScript, Python, Ruby) × two subscription-backed
model/agent configurations × T0/T1 × two independent replicates: 56 attempts.
Kimi K3 and OpenCode GLM 5.3 are requested configurations, not yet verified resolved
provider identifiers here. Provider qualification is a separate gate. Do not route
them through Codex or Claude. Keep the language set; do not interpret it as an
ordered numerical scale of typing strength. This one-instance matrix remains a
pilot, particularly since the previous Ruby/Rust calibration was solved quickly.

## Locally observed tools and caches

These are local command observations, not recommendations of latest releases or
proof that the current isolated worker can execute them.

| Language | Observed host tools | Dependency readiness |
|---|---|---|
| Rust | rustc 1.99.0; rustup under `~/.cargo` | Existing pinned Cargo ledger scaffold and qualified native port; retain its lockfile. |
| Ruby | Ruby 4.0.7 under mise | Existing standard-library JSON port and qualified native scaffold. |
| Haskell | No `ghc`, `cabal`, or `stack` on PATH | No `~/.cabal/packages` or `~/.stack`; compiler and complete offline JSON dependency closure must be acquired and pinned. |
| C# | dotnet SDK 10.0.401 under `~/.local/share/mise/dotnet-root` | SDK present; NuGet cache contains framework packages and Newtonsoft.Json 13.0.3. Prefer SDK-provided System.Text.Json if qualified; no third-party package is necessary for this domain. |
| Kotlin | Java 27 under mise; no `kotlinc` or `gradle` on PATH | Gradle caches exist, including compiler-embeddable 2.2.20 and 2.0.21, stdlib artifacts, Gson 2.11.0, and kotlinx-serialization-json-jvm 1.4.0. This mixed cache is not a proven compatible build closure. |
| TypeScript | Node 26.10.0 under mise; `/usr/bin/tsc` 6.0.3 resolves to `/usr/lib/node_modules/typescript/bin/tsc`; npm 11.19.1 | Compiler present. Freeze compiler, Node, strict configuration, and Node declarations; arbitrary npm cache contents are not a lockfile. |
| Python | PATH Python 3.12.12 under mise; `/usr/bin/python3` is 3.14.7 | Standard-library JSON sufficient. Explicitly choose and record worker interpreter rather than assuming PATH and controller helper are identical. |

Java, dotnet and Node are outside the current `/usr` runtime mount. Haskell is a
clear acquisition gap; Kotlin is a toolchain assembly/qualification gap. Cache
presence alone establishes neither successful compilation nor offline operation.
Do not mount full home directories or authentication/config caches into workers.
Provision dependencies before timed attempts, then disable network for all builds.

## Harness changes required before a matrix

`langbench/core.py` lists all seven languages but `IMPLEMENTED` admits only Ruby
and Rust. `tasks/ledger_engine/task.json` likewise lists only those two. Avoid
making every task appear to support all languages merely by extending the global
constant: check support per task and add only ledger ports initially. Manifest,
CLI and batch validation must reject unsupported task/language combinations early.

`DockerWorker` presently mounts host `/usr`, Ruby/Rust toolchains and the Cargo
registry, requires both Ruby and Rust even for an unrelated task, and records
fixed resource mounts. Replace implicit runtime discovery with a frozen per-language
runtime specification or qualified immutable toolchain images. Preserve offline
execution, read-only trusted mounts, no writable host bind, cgroups, supervisor
cleanup, isolated Python controller helpers and private-package visibility guards.
A language runtime must not expose controller modules, `cases.py`, reference source,
or another project's files. Exercise those guards against newly packaged images.

The existing 4 GiB/2 CPU/64 PID, 512 MiB workspace and 64 MiB temporary limits need
preflight with each compiler and managed runtime. JVM/.NET thread defaults and
compiler disk output may exceed them. Select a common, documented sufficient
profile before attempts; never selectively raise limits after a language fails.
Pin JVM processor/heap settings and disable compiler daemons/background build
servers where needed. Capture compiler versions, runtime versions, immutable
image/toolchain identities, build commands, flags and dependency locks in receipts.
The legacy bubblewrap backend is not a substitute for qualified Docker grading.

The grader already reconstructs a trusted starter and replaces only `src/`, then
runs `build.sh` and `run.sh`. Keep that boundary. Place all candidate domain modules
inside `src/`; compiler settings, dependency declarations and launchers remain
immutable. Build outputs should go to the existing root `target/` convention,
including managed-language intermediates, rather than broadening ignore rules to
arbitrary directory names. Preserve all nested source paths in hashes/snapshots.

Wheel package-data currently includes Cargo manifests, shell launchers and a single
`src/*` glob, but not csproj, cabal, tsconfig, Kotlin dependency manifests or reliably
nested modules. Add explicit complete source/scaffold packaging and install-wheel
verification for each language. Keep build products and dependency stores out.
`langbench/live.py` currently captures only Ruby/Rust toolchain versions and is
Codex-specific; provider adapters must consume the same qualified worker boundary
without inheriting those assumptions. Existing difficulty gates also mention only
Ruby/Rust and must not silently confer comparison eligibility on the new matrix.

## Native port design and semantic equivalence

Each language needs a functioning v1 starter and a separate correct v2 reference,
not a broken program, TODO-only shell, reference hidden behind a flag, or wrapper
around Python/Ruby/Rust. Maintain the same maintenance surface: identities and
wire authorization, transactions/snapshot validation, unique index, logical device,
journal recovery, checkpoints and retry receipts. Let module layout be idiomatic;
do not impose equal line counts or require Haskell-like abstractions elsewhere.

Suggested native building blocks, to freeze only after isolated qualification:

- Haskell: algebraic domain types, Map/Set state and a native JSON library such as
  Aeson. Native pure transition functions can drive a minimal JSONL IO loop.
- C#: record/enum domain types, dictionaries and System.Text.Json; explicit clone
  or ownership boundaries for JSON values prevent disposed-document references.
- Kotlin: data/sealed classes, explicit maps and a pinned native JVM JSON library.
  A small pinned CLI build avoids Gradle daemon overhead, but must provide the same
  useful compiler diagnostics as the qualified toolchain.
- TypeScript: strict compiler checks, discriminated unions and Map/Set. Do not use
  blanket `any` or disable strictness to manufacture a dynamic arm. Standard JSON
  parsing plus native typed conversion suffices; declarations belong in scaffold.
- Python: normal native modules, dictionaries/dataclasses as useful, stdlib JSON.
  Freeze whether optional static checking is provided; do not silently add a
  mandatory checker only to the dynamic arm or prohibit sensible annotations.

Across all ports, preserve missing versus null alias/note and arbitrary nested
JSON values. A Boolean is not an integer. Never collapse scoped tuple keys into
ambiguous concatenations. Sort ASCII identifiers consistently, including durable
frames/receipts. Avoid iteration-order dependence, shallow-copy snapshot aliasing,
mutable JSON sharing, and accidental floating-point coercion. The specified
integer bounds fit JavaScript exact integers, so do not change the contract to
create an artificial numeric disadvantage.

Match error precedence, tombstones for absent deletes, snapshot versions even on
staged reads, range and alias-map conflicts, atomic alias swaps, empty read-only
commits, capacity failures retaining handles, scoped idempotency before handle
lookup, fault prefix/torn-frame semantics, two-write checkpoint publication, and
schema1 owner adoption. Preserve v1 projection and its documented baseline subset.
Typing policy is a measured ecosystem configuration, not an imposed ranking:
Haskell and Rust differ in guarantees; C#/Kotlin are statically typed; TypeScript
checks are erased. Record actual flags and idioms instead of calling these a
single strong-to-weak ladder.

## Verification and release gates

1. Freeze common contract, starter capability checklist, public cases and private
   seeds before translating. Keep the Python controller oracle outside all agent
   workspaces; native references are development assets, never supplied solutions.
2. Qualify each isolated offline toolchain with its smallest native JSONL program;
   check errors, bounded execution and cleanup. Record cold/warm dependency state.
3. Implement v1/v2 pairs in coherent language lanes. Independently review each
   reference against the contract and hand-derived anchors, not only another port.
4. Require all existing baseline histories on each starter and identical complete
   public/private case sets on each reference, including multiple frozen seeds.
   Run actual compiled/interpreted native semantic mutants for each new port;
   abstract oracle mutations alone do not show native defects are detected.
5. Verify installed-wheel scaffolds, nested source inventories, immutable build
   configuration, private-case exclusion, and T0/T1 parity. T0 has no supplied test
   support but may write its own tests; T1 receives exactly the common public JSON
   tests/driver. The Python public driver is transport/assertion infrastructure,
   not permission for Python delegation in another language's submitted solution.
6. Gate the subscription adapters separately: exact model identity, tool execution
   isolation, wall-clock deadlines, ordinary argument repair, explicit fixed-nudge
   checkpoints, raw usage with unknown counts retained, quota stop and no silent
   retry/model substitution. Run a small qualification before the 56-cell batch.
7. Freeze blocks/order/seeds and both model budgets. Two replicates are independent
   fresh attempts, not resumed successes. Report model+agent configuration effects;
   different CLI tooling is a confound. Do not treat token counts across tokenizers
   or different reasoning visibility as a common cost unit without qualification.

The read-only reference project's `scripts/frontier_opencode.py` separates tool
installation networking from agent execution and probes hidden tests/solution
absence; `scripts/frontier_native.py` preserves sessions. Those are useful patterns,
not evidence that its provider credentials, network policies or Harbor adapters
fit this benchmark. No credentials or private configuration were read or copied.

Deliverable before model collection: seven independently reviewed native v1/v2
pairs, per-task support manifests, packaged offline toolchains, parity/mutant
receipts, and a provider-qualified immutable matrix. Passing that gate establishes
benchmark readiness; a single small ledger instance still cannot establish broad
language superiority or diminishing returns from stronger type systems.
