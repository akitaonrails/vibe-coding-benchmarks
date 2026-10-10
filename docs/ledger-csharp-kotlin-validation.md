# Typed C# and Kotlin ledger qualification

Date: 2026-10-10. These are native implementation checks, not model coding trials.
[The evidence receipt](ledger-csharp-kotlin-validation.json) records source hashes,
immutable toolchain identity, resource bounds, suites and mutations.

Both the working v1 starter and v2 reference use six native modules. C# has
immutable record rows and a closed set of concrete journal frame records; Kotlin
uses data-class rows and sealed journal-frame variants. Both represent absent
optional fields with `Presence<T>`, explicit null alias/note separately, and
missing rows with nullable typed rows. Arbitrary note values remain JSON values
and are copied at ownership boundaries. Tuple identities, table entries,
transaction writes and journal groups are typed. Generic JSON objects remain at
the request/response and checkpoint-image boundaries; the wire serializer's
heterogeneous fields do not turn stored rows or frames into string-keyed maps.

This completes the partially converted C# reference and migrates the Kotlin
implementation and both starters from generic JSON rows/frames. The reference
semantics and public contract are unchanged. Starters retain functioning v1
snapshot overlays, normal journal recovery, load/checkpoint migration and capacity
limits, while lacking conflict/uniqueness validation, retry deduplication and fault
publication. They reject v2/fault requests before changing state. There is no
reference-mode switch or cross-language solution delegation.

Validation command:

```sh
python3 -m unittest tests.test_ledger_csharp tests.test_ledger_kotlin -q
```

Six tests passed in 77.277 seconds. Every build and execution used the offline
`DockerWorker(runtime='seven')` with image
`sha256:62379d1caa1fe6d335b8a74a85b1dea2673dae39303df407edd296db1993db69`,
two CPUs, 4 GiB memory, 64 PIDs and the same bounded temporary/workspace storage
as the other language ports. Each reference passed 27 public histories and the
43-case private grading suite for seeds 0, 29 and 271. Each starter passed the
four common baseline histories and an additional state-preserving unsupported
version/fault history.

Each language also built and executed six native defects, all detected: omitted
conflict checks, omitted unique-index validation, omitted receipt reuse,
checkpoint publication after its first write, ignored torn-frame marker, and
loss of tombstone versions. The transport driver passes only request histories
into each fresh native service; expected results remain in the controller.

Setup and effort remain separate. This lane installed no dependencies and made
no model calls. The shared runtime supplies the pinned .NET SDK and Kotlin/JVM
compiler; Kotlin uses the runtime's pinned Gson 2.11.0. C# uses System.Text.Json
from the SDK without a third-party package. Build/intermediate outputs remain
under protected `target/`; launchers and compiler configuration are outside
editable `src/**`. A nonfatal .NET workload-verification notice appeared during
initial compile; no workload is needed or installed for this SDK console project.

Independent review and installed-wheel completeness remain separate integration
gates. Typed domain use makes the configured comparison more meaningful; it does
not prove that the strongest possible type guarantees are exercised, establish
frontier task difficulty, or imply a language ranking.
