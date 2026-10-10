# Native Python and TypeScript ledger ports

Date: 2026-10-10. Development reference qualification, not model-attempt evidence.
The source inventory is in [the companion receipt](ledger-python-typescript-validation.json).
No dependencies were downloaded and no model coding calls were made for these ports.

Both languages have separate six-module native v1 starters and v2 references:
JSONL transport, domain values, versioned table/index predicates, transaction
snapshot/dependencies, stable device/journal, and wire/lifecycle coordinator.
The starter supports all four common baseline histories while rejecting v2 and
fault requests without mutation. It lacks conflict validation, unique validation,
retry deduplication and fault publication. There is no reference-mode toggle or
cross-language implementation delegation.

References recover from checkpoint images and actual BEGIN/EDIT/SEAL journal
frames. They retain no durable shadow table or per-commit whole-state snapshot.
Tuple identities are Python tuples and losslessly encoded JSON tuples in
TypeScript; explicit tuple sorting handles ASCII order. Optional JSON fields are
preserved and copied across ownership boundaries. Transactions validate snapshot
versions, including tombstones, while writes apply atomically before secondary
index validation is accepted.

Protected launchers/configuration sit outside editable `src/**`. Python uses
stdlib JSON and dataclasses without a mandatory static checker. Its build checks
syntax with bytecode output under `target/pycache`; execution disables source-tree
bytecode writes. TypeScript uses `strict`, `noUncheckedIndexedAccess` and
`noEmitOnError`, with ES2022/CommonJS output in `target/`. Its domain includes
recursive JSON types and a discriminated journal-frame union. A protected minimal
`runtime.d.ts` describes only the supplied Node transport APIs; no npm dependency
or blanket `any` is used. The JSONL boundary assumes the contract's valid input
shapes, as do the existing native ports.

Validation:

```sh
python3 -m unittest tests.test_ledger_python tests.test_ledger_typescript -q
PATH=/usr/bin:/bin /usr/bin/python3 -m unittest tests.test_ledger_python -q
```

The combined run passed 12 tests in 10.943 seconds on Python 3.12.12, Node
26.10.0 and TypeScript 6.0.3. The Python-only run also passed six tests in 5.393
seconds on the intended worker interpreter, `/usr/bin/python3` 3.14.7. Each
reference passed 27 public histories and all 43 private-suite histories (including
public cases) for seeds 0, 29 and 271. Each starter passed four baseline histories
and explicit unsupported-version/fault state-preservation checks. A hand-derived
anchor checks torn SEAL rollback, lost transaction handles, successful retry and
post-crash receipt lookup with an explicit null note.

Six real native mutations per language were built and executed: omitted conflict
validation, omitted uniqueness, omitted receipt reuse, checkpoint publication
after its first write, ignored torn-frame marker, and tombstone version loss.
Each was rejected by a targeted public history. These mutations test observable
semantic failures; they are not simulated changes to controller verdicts.

Setup friction was limited to selecting the worker Python separately from the
host PATH interpreter and supplying the TypeScript standard transport declarations.
No install or package acquisition time is candidate effort. Both ports also passed isolated offline Docker qualification on image
`sha256:62379d1caa1fe6d335b8a74a85b1dea2673dae39303df407edd296db1993db69`: each
reference passed 27 public cases plus all 43 cases at seeds 0, 29 and 271, and
each starter passed four baseline histories. Resource/image evidence appears in
the companion receipt. Per-task support and installed-wheel source/config
completeness remain shared integration checks. These ports extend one existing
ledger task and do not establish frontier difficulty or language superiority.

Independent runtime check: both references also passed all 43 private-suite
histories at seed 20261010 inside the pinned seven-language image
`sha256:62379d1caa1fe6d335b8a74a85b1dea2673dae39303df407edd296db1993db69`.
Both starters passed all four baseline histories in that image. The worker
verified 4 GiB memory, two CPUs, 64 PIDs, offline networking, bounded temporary
filesystems, and absence of controller/task packages. Local raw receipts are
`results/native-seven-python-reference.json`,
`results/native-seven-typescript-reference.json`, and
`results/native-seven-python-typescript-starters.json`. These are reference and
harness qualification costs, not candidate coding effort.
