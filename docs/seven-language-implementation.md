# Native expansion implementation evidence

Status: implementation and qualification in progress, 2026-10-10. No candidate
coding attempt or model-generated performance conclusion is reported here.

The new runtime is a self-contained image selected explicitly with `runtime='seven'`
for both candidate execution and private grading. All seven languages use the same
image and limits. The historical runtime default is preserved. Per-task language
availability admits seven ledger ports while crash_store/protocol_migration remain
Ruby/Rust. Wheel packaging includes protected compiler configurations and nested
native sources; preparation still exposes only the starter and public contract,
plus common public cases/driver in T1. Private cases remain controller-only.

The complete runtime closure and reproduction limits are documented in
[the toolchain directory](../toolchains/seven/README.md). Native versions differ
from some host installations: image Ruby3.4.10, Python3.14.8, Node26.11.1,
TypeScript6.0.3, GHC9.6.7/Aeson2.2.4.0, Kotlin2.4.21/Java27,
.NET SDK10.0.112 and Rust1.99.0. The installed package closure records exact builds.
Comparisons must use this frozen image for every language, not mix host runtimes
with isolated workers or retroactively compare against old runtime conditions.

## Domain typing review

An initial implementation used typed tables/transactions but JSON objects for rows
and journal frames. Review rejected that as insufficient treatment fidelity:
JSON bags conceal precisely the compiler guarantees being investigated. Haskell,
C# and Kotlin ports now require native Row types, explicit optional-field presence,
nullable/Maybe tombstones, and algebraic/sealed journal frame variants. JSON stays
at wire/checkpoint serialization boundaries and inside arbitrary note values.
Starter and reference share that architecture. Starters remove target conflict,
uniqueness, fault-publication and retry-deduplication behavior rather than hide a
complete solution behind a flag. This does not require identical source lengths
or identical representations in dynamic languages.

## Setup and intervention ledger

All entries below are coordinating-agent development/setup work, outside measured
candidate effort. No human repair hours were measured; no model coding trial was
run by the native-port author. Tool commands and failures were retained in local
`/tmp/langbench-*` logs; these local logs are not a portable committed receipt.

| Incident | Resolution | Attribution |
|---|---|---|
| Haskell compiler absent; Kotlin CLI absent on host | Built a shared runtime with complete compiler/library closure | One-time toolchain setup |
| Arch package `java-gson` unavailable | Copied existing Gson2.11.0 artifact and pinned its SHA | One-time dependency acquisition |
| .NET offline build requested missing ASP.NET targeting pack | Added the SDK's optional targeting pack before freezing image | Environment preflight, not candidate compile failure |
| Haskell Aeson exports a conflicting `Key` name | Explicitly hid that import | Reference-author coding correction |
| Haskell lazy ByteString has no `getLine` | Read a line then pack for JSON parser | Reference-author coding correction |
| JSON-domain representation weakened static guarantees | Replaced native rows/journal with typed domains before qualification | Independent review-driven reference revision |

No global runtime configuration was changed. Container image builds used network;
actual candidate/compiler execution uses the qualified network-disabled worker.
No host private assets or credential directories are mounted by the seven runtime.

## Evidence inventory

- `tests/test_seven_runtime.py`: immutable runtime, tool availability, cgroups,
  network/private-path boundary, export and per-task availability.
- `tests/test_packaging.py`: built/installed wheel, all native source/config assets,
  isolated CLI preparation, no build products or supplied reference/oracle leakage.
- Haskell: `tests/test_ledger_haskell.py` passed3methods in62.330s, including
  27public +43private histories each at seeds29/271,4starter histories and6
  actually compiled semantic mutants. Source/environment evidence is in
  [ledger-haskell-runtime-validation.json](ledger-haskell-runtime-validation.json).
- Native tests: common public cases, 43 private histories per frozen seed,
  four functioning starter histories, baseline guards and actual native mutants.
  Language-specific test ownership and final results are recorded as each lane
  completes; abstract Python-oracle mutants alone are not native-port evidence.
- Ruby/Rust were requalified on the new image: each reference passed27public +
  43private(seed29) histories, each starter passed4baseline histories. Worker
  boundary3tests and installed-wheel1test passed before typed-port finalization.

- Independent Python/TypeScript Docker grades each passed43private histories at
  seed20261010 (`results/native-seven-{python,typescript}-reference.json`), and
  each starter passed4baseline histories
  (`results/native-seven-python-typescript-starters.json`).

This work qualifies implementations and measurement boundaries. It does not
qualify ledger difficulty for frontier models or provide evidence that one
language reduces coding effort. Independent native-domain review remains required.
