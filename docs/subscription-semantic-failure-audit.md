# Submitted semantic failures: cells 21, 25 and 37

Interim read-only audit, 2026-10-11. No candidate execution, build, test, patch or model call was performed. The analysis below has never been fed back to candidates. It uses committed private-grading receipts, saved submitted source, the frozen contract and case definitions. Receipt hashes, snapshot commitments and graded source digests were verified by file hashing only.

The receipts retain case pass/fail and process status, not full actual/expected response transcripts. Consequently, the specific response differences below are deductions from source and contract, not newly reproduced failures. A cluster of failed histories is not a count of independent defects.

## Shared lost-history condition in C# and Python

Cell `0021-opencode-csharp-T0-r2` reached its 900.08-second deadline with a saved artifact. Cell `0025-kimi-python-T0-r2` handed off normally after 896.38 seconds. Each passed 42/43 private histories; each failed only `empty_load_pristine_once`, with process exit zero and no termination. Both reported the critical group `migration` failed.

The contract's load rule at `tasks/ledger_engine/CONTRACT.md:162–176` explicitly makes loading an empty revision-zero schema1 image a non-pristine event. The public-defined history `empty_load_pristine_once` in `tasks/ledger_engine/cases.py:255` performs:

1. Load an empty revision-zero schema1 image: expect `loaded:0`.
2. Load it again: expect `not_empty`.
3. Perform an ordinary checkpoint: expect `checkpoint:0`.
4. Attempt the load again: expect `not_empty`.

This history tests historical eligibility after an empty migration, not the presence of user rows or a positive revision. These T0 agents did not receive the supplied public histories during collection.

In the C# submitted `src/Engine.cs:66–72`, the load guard checks revision, transactions, journal, checkpoint schema and checkpoint entries/receipts. `src/Device.cs:17` publishes the checkpoint as schema2 and clears the legacy owner and journal. After the first empty load, the schema1 check blocks the immediate retry; after checkpointing the empty state, all the guard's inspected properties again look pristine. There is no retained historical load marker in that guard. Direct source evaluation therefore predicts that the fourth request is incorrectly accepted.

The Python submission contains an explicit `loaded` marker. `src/solution.py:50–57` uses it to reject another load, and `src/device.py:50–53` sets it when loading. However, successful publication at `src/device.py:42–46` clears `self.loaded` as well as the legacy owner and journal. For an empty revision-zero checkpoint, the remaining load guards also become false. The same fourth request is therefore predicted to be incorrectly accepted.

These are two implementations of the same semantic omission: migration erases the evidence needed to enforce the once-only load eligibility rule. The Python boolean makes the state distinction explicit but is reset at the wrong lifecycle transition; the C# guard derives eligibility from current image shape. Static typing versus dynamic typing is not isolated by this pair: they use different models, both are T0, and the relevant invariant is about history across operations.

A plausible repair would preserve a historical loaded/non-pristine fact across checkpoint publication and recovery, resetting it only with a fresh initialization. That describes a localized repair hypothesis, not an applied patch, measured repair time, verified line count or proof that one-line editing would be sufficient. Recovery/init interactions would still need validation in a separately authorized repair study.

## Haskell full-publication fault is treated as ordinary success

Cell `0037-kimi-haskell-T0-r2` handed off normally after 676.98 seconds, with a saved artifact and 28/43 private histories passing. Failures were `checkpoint_migration_cut_2_False` plus 14 seeded combination histories. All failing processes exited zero without termination. The critical failed group was `migration`; the seeded cases are labeled `combinations`.

The checkpoint contract at `CONTRACT.md:134–141` distinguishes persistence from the response/lifecycle outcome. With `fault:{keep:2,tear:false}`, both logical publication writes survive, so the new schema2 image becomes authoritative and the journal is cleared. **Every injected checkpoint fault still crashes, clears transactions and returns `interrupted`.** Durable success does not imply an ordinary successful response.

The submitted `src/Engine.hs:28–31` handles faults only when `keep<2 || tear`. That branch returns interrupted and calls recovery. The remaining wildcard branch publishes the checkpoint and returns `checkpoint:revision`. Thus `Just (2,False)` takes the same branch as no fault: the durable image is published, but the response is wrong and active transactions are retained rather than cleared by recovery.

This directly explains a mismatch in `checkpoint_migration_cut_2_False`. The seeded generator at `tasks/ledger_engine/cases.py:256–278` also injects checkpoint faults with keep selected from 0, 1 and 2 and tear false. The same omitted full-publication-fault branch is therefore a strong shared explanation for the 14 seeded history failures. The receipt alone cannot prove it is the only defect in those histories: it records aggregate case failure, and no per-response differential rerun was performed. Do not describe this as 15 independently discovered defects or multiply hypothetical repair effort by 15.

The seeded failures are sample indices 0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13, 14 and 15 for seed 20261011. Indices 4 and 11 passed. This note does not reconstruct or execute those traces to prove which request first diverged.

A plausible repair would give all fault-bearing checkpoint requests a distinct control path: conditionally publish the complete durable image, then recover/clear transient state and return interrupted. The normal no-fault path must preserve active snapshots. This appears localized to checkpoint control flow, but its verification spans response semantics, transaction invalidation, durable retry receipts and migration. No repair was implemented, and no human-hours estimate follows.

## Link to the collected source

Evidence paths below are relative to `results/subscription-matrix/`. All cited source paths are beneath each cell's `collection/snapshot-0/`. Tool call IDs are from `result.json → collection.invocations[0].tool_records`; native process events are at `trace/invocation-0.json`.

| Cell | Submitted source-changing calls | Last change matching graded source | Graded source SHA-256 |
|---|---|---|---|
| `0021-opencode-csharp-T0-r2` | 10, 11, 12 | 12; subsequent last recorded source digest still matches | `81ea9cbb8c45135f4a5c9460d7147cd85dfe3a35d973bfff87f57e464734a561` |
| `0025-kimi-python-T0-r2` | 8, 9 | 9; subsequent last recorded source digest still matches | `fc0c924037e49f79fc55df8f7d74c823ce15386681c42c68a973b8733bef751c` |
| `0037-kimi-haskell-T0-r2` | 8, 9 | 9; subsequent last recorded source digest still matches | `f04d26b1077b49dc2a2c13cc639f38a7234876a604ef277c152dc8833ddfcb07` |

Committed `result.json` hashes, respectively:

- Cell 21: `8b2e0adf9fd74c2062a2e7c32b7040f89eadfc26a5c48427806f2b966e35c3a7`.
- Cell 25: `d9b559ec6935b33817a90efec800e277d4072eb2f1b0e7e00d41e99ef85f9878`.
- Cell 37: `1fdc1fbf77c990c2fb2c03ebd429a00099259ffe85f7e45ef9a4f203668a35d6`.

These mechanisms are missed cross-operation invariants in otherwise substantially working implementations. They do not establish which language needs less manual work. Candidate autonomous effort remains measured in the original receipts; this audit is additional AI/operator analysis. No human repair occurred here, required human labor is unknown, and private failure information remains outside every candidate session.
