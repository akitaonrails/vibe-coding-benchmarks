# Opus language effort audit: Ruby, Rust and Haskell

The closed Opus cohort reached a correctness ceiling: **all 25 valid attempts completed normally and passed all 43 private cases at their first handoff, with zero nudges**. Three consumed attempts remain infrastructure-invalid. Within the ten valid Ruby/Rust/Haskell attempts reviewed here, compiler errors did not produce an observable repair loop; visible extra work included a Haskell warning cleanup, Ruby performance revisions, and a Ruby test-output capture failure. This task therefore cannot distinguish these languages by successful completion rate for this model configuration.

This is a read-only audit of the closed Opus cohort. No candidate was executed, changed, or retried. No active Sol results were inspected. The authoritative inputs are [final analysis JSON](../results/opus-medium-matrix-final/analysis.json), [analysis table](../results/opus-medium-matrix-final/analysis.md), and the closed receipts under [matrix-v3](../results/opus-medium-matrix-v3). The analysis JSON SHA-256 at audit time was `ef6b9b02058519dd3f7584ea55d75d90ccfc4968e95c3d1f2265953c0b808b43`; each of the ten receipt hashes matched its analysis entry. Paths inside inherited receipts may point to earlier preserved instrumentation epochs.

## What was measured

T0 supplies the contract and working starter without public tests; T1 also supplies public cases and their driver. The agent may create its own checks in either condition. “Commands” below means sandbox tool calls, each of which can contain several shell commands, edits and checks. “Source-changing calls” counts calls whose recorded `src` content hashes differ before and after. Neither number is an iteration count. A single call can implement several features and run tests; a `touch` can change timestamps without changing source content.

The seconds column is the recorded candidate CLI interval, excluding its separate authentication preflight and passive cleanup. It still includes allowance endpoint retries and CLI backoff within that interval. The adjacent pre-inference span is the observed interval between the first local request record and the first request subsequently forwarded for inference. Where 429 retries occurred, that span is setup delay, not evidence of difficult coding. It is not a model-compute estimate; no attempt is made to derive pure reasoning time by subtracting every known overhead.

Tokens are reconciled native Messages totals: disjoint uncached input, cache reads, cache creation and output, with complete coverage for these ten attempts. Cache and repeated context can dominate totals. These counts are neither billing amounts nor a common unit of compute. File size is all submitted `src` bytes and physical lines, including comments, blank lines and adapters. Each artifact contains six native source files. Temporary test scripts and captured outputs under `/tmp` are outside this size measure; line counts are not a cross-language quality or difficulty ranking.

| Cell | Condition | CLI seconds | Preflight 429s / pre-inference span | Tokens | Commands / source-changing calls | Final src bytes / lines |
|---|---|---:|---:|---:|---:|---:|
| 0002 Haskell | T0 r1 | 86.38 | legacy field unavailable / 0.00 s recorded span | 144,694 | 8 / 2 | 16,036 / 266 |
| 0006 Haskell | T1 r1 | 139.19 | 7 / 69.00 s | 96,469 | 7 / 2 | 16,000 / 280 |
| 0017 Haskell | T0 r2 | 141.36 | 7 / 66.98 s | 92,380 | 6 / 1 | 15,884 / 265 |
| 0012 Ruby | T0 r1 | 75.17 | 0 / 0.00 s | 102,023 | 7 / 2 | 13,518 / 416 |
| 0011 Ruby | T0 r2 | 173.60 | 6 / 34.76 s | 265,378 | 12 / 4 | 14,208 / 426 |
| 0008 Ruby | T1 r2 | 139.73 | 6 / 36.13 s | 205,141 | 10 / 5 | 13,876 / 416 |
| 0019 Rust | T0 r1 | 151.79 | 6 / 36.60 s | 119,770 | 7 / 2 | 22,885 / 702 |
| 0014 Rust | T0 r2 | 131.98 | 6 / 38.17 s | 168,278 | 9 / 3 | 22,670 / 697 |
| 0025 Rust | T1 r1 | 77.18 | 0 / 0.00 s | 174,796 | 8 / 2 | 23,656 / 713 |
| 0007 Rust | T1 r2 | 96.54 | 5 / 18.30 s | 141,916 | 8 / 3 | 23,546 / 716 |

Zero recorded span means the first recorded request was the forwarded request; it does not mean authentication or allowance checking took zero time. The actual allowance HTTP calls generally consumed fractions of a second in total; the much larger spans above include retry spacing. For example, Haskell T1 r1 records 0.524 seconds of allowance calls inside a 69.00-second pre-inference span. Treating its whole 139.19 seconds as language-dependent work would be misleading.

## Representative mechanisms in the traces

### Haskell: warning cleanup, rather than a type-error repair sequence

In [Haskell T0 r1](../results/opus-medium-matrix-v3/0002-claude-haskell-T0-r1/result.json), tool call 3 implemented the missing behavior and built it. GHC reported `-Woverlapping-patterns`. Call 4 removed the redundant `transaction_missing` fallback, rebuilt, and ran custom JSONL examples; calls 5–7 checked further migration, fault and conflict scenarios. This is one visible warning-driven revision. It is not evidence of a compiler catching a semantic ledger defect.

In [Haskell T0 r2](../results/opus-medium-matrix-v3/0017-claude-haskell-T0-r2/result.json), the only source-changing call ended with exit code 1 because the build output was piped into a search for warnings/errors and there were no matches. Subsequent calls found the executable and ran it. Counting that nonzero shell result as a compilation failure would fabricate a repair. No subsequent source revision occurred.

[Haskell T1 r1](../results/opus-medium-matrix-v3/0006-claude-haskell-T1-r1/result.json) first ran the public driver against the incomplete starter, observing `tenant_auth_retry_scope`. It then made two implementation calls and used a custom public-case comparison helper that reported `bad 0`. This is useful feedback from supplied tests, but the observed failed check was before implementation; it should not be reported as a defect introduced by the model and then repaired. Its large CLI duration also includes the 69-second pre-inference delay above.

### Ruby: optional performance work and a verification-helper failure

[Ruby T1 r2](../results/opus-medium-matrix-v3/0008-claude-ruby-T1-r2/result.json) used a custom helper to enumerate public failures in the starter (1/27 passing), implemented the missing features in three source-changing calls, and reached 27/27 public cases. It then voluntarily created a larger workload. Its reported shell timings went from 5.539 seconds to 3.199 and 2.447 after two further source changes: reducing copied/filtered transaction rows and deduplicating tracked scans/lookups. Public cases continued to pass. Those calls add work after initial public correctness; they are performance revisions, not evidence that dynamic typing required more correctness repairs. These ad hoc timings are not controlled scalability measurements.

[Ruby T0 r2](../results/opus-medium-matrix-v3/0011-claude-ruby-T0-r2/result.json) likewise added custom functional and larger workload checks. A later revision changed snapshot copying and row selection. The attempted comparison of two large output files then hit the worker's 64 MiB `/tmp` limit: Ruby reported `Errno::ENOSPC` while writing stdout, and the shell also reported `cmp: command not found`. The next call deleted the captures and streamed output through `md5sum`; the streamed digest matched the saved baseline digest. No additional source change was needed for that helper repair. The failed 1.117-second run is not a valid speedup observation; the later completed streaming check reported 3.810 seconds. This is concrete runtime/tooling friction caused by how the agent verified its code, not a demonstrated ledger correctness defect.

[Ruby T0 r1](../results/opus-medium-matrix-v3/0012-claude-ruby-T0-r1/result.json) used only two source-changing calls and seven total calls, then handed off correctly. The contrast within Ruby itself—75.17 versus 173.60 seconds, with different self-selected verification and preflight delays—is larger than a simple “dynamic language debugging tax” explanation can support.

### Rust: direct implementation, compilation and public feedback

Both Rust T1 traces finished with successful public checks and additional hand-written examples. [T1 r2](../results/opus-medium-matrix-v3/0007-claude-rust-T1-r2/result.json) observed the starter's authorization-case failure, changed transaction/device/solution code across three calls, and obtained `Public cases passed` on the first visible post-change build-and-test call. [T1 r1](../results/opus-medium-matrix-v3/0025-claude-rust-T1-r1/result.json) read the public cases, made two source-changing calls, and also obtained `Public cases passed` before additional examples.

The two [T0 r1](../results/opus-medium-matrix-v3/0019-claude-rust-T0-r1/result.json) and [T0 r2](../results/opus-medium-matrix-v3/0014-claude-rust-T0-r2/result.json) attempts built their implementations and exercised self-authored JSONL scenarios without supplied public expected outputs. No compiler-error-driven revision was visible in these four Rust traces. A nonzero read/listing call in T0 r2 came from checking absent paths, not from compilation. Successful compilation may still have constrained generation or supplied confidence; absence of a repair loop cannot establish that types had no benefit.

## Verification limits and interpretation

- No visible compiler type-error repair sequence was found in these ten valid traces. JSON responses such as `error: conflict`, `capacity`, `interrupted` or `forbidden` are often the intended results of negative scenarios; they were not counted as runtime failures merely because they contain “error.”
- T0 checks frequently printed results for inspection instead of asserting every expected value. Shell pipelines sometimes masked a failed public driver or produced a nonzero status from a diagnostic filter. The independent private grader supplies stronger final correctness evidence than those shell exit codes. It ran after collection; its answers were not available to the agent.
- Native source hash changes expose revisions at tool boundaries, not every internal edit. Helpers under `/tmp` can be created or repaired without a source hash change. Conversely, multiple feature edits before the next check are not several demonstrated repair cycles. The narratives above classify observable sequences; they do not manufacture a universal iteration count.
- All ten valid focal attempts passed 43/43 private cases, and all 25 valid cohort attempts did likewise. This is a ceiling for this ledger/model/agent configuration, not proof that the implementations are correct for every input or that a frontier difficulty gate has been met. One task and at most two valid repetitions per condition cannot establish a typing hierarchy or prove that unit tests substitute for types.
- The preserved C# T1 r2, Haskell T1 r2 and Ruby T1 r1 infrastructure incidents are not semantic language failures. They consumed real operator/model effort and reduced usable coverage; they were not retried. Transport fixes, qualification probes and preflight delays belong in the operational ledger, separately from candidate repairs. Measured human labor is unknown. Zero automatic nudges does not mean zero operator work on the harness.

A defensible mechanism-level inference is that this strong model usually produced a compilable implementation directly, while verification choices and provider setup friction materially affected observed effort. The traces do not establish that Ruby inherently needs more work, that Rust saves tokens, or that Haskell's additional static guarantees have diminishing returns. The successful T0 attempts are compatible with the user's hypothesis, but the correctness ceiling prevents this cohort from testing it sharply.
