# Subscription matrix operational audit: first two cells

Recorded 2026-10-10. This is an additive incident record. Frozen code, qualification bindings, prompts, budgets, fixtures and original receipts remain unchanged. No consumed cell was retried, and no extra candidate nudge or source repair was supplied. The matrix resumed with pending cells after a read-only diagnosis.

## Observed attempts

Both cells used OpenCode GLM5.3 high and the same initial maximum window of 900 seconds. They differ in language **and testing condition**, so this pair cannot establish a language effect.

| Evidence | Ruby, T1, repetition 1 | Haskell, T0, repetition 1 |
|---|---:|---:|
| Invocation elapsed seconds | 900.043 | 460.796 |
| Terminal outcome | Controller deadline | Normal CLI exit; model output-length stop |
| Native model requests | 31 | 5 |
| Provider-reported total tokens | 1,740,768 | 49,846 |
| Recorded sandbox tool calls | 36 | 5 |
| Calls changing editable-source digest | 3 | 0 |
| Private cases | 43/43 passed | Overall failed; 14 critical groups failed |
| Additional reactivation nudges | 0 | 0 |
| Preparation/adapter seconds | 0.811 | 0.935 |
| Collection/cleanup wall seconds | 908.089 | 461.753 |
| Private grading seconds | 7.042 | 7.100 |
| Whole-attempt wall seconds | 915.942 | 469.788 |

Token totals have complete observed native request coverage in these receipts. Cached input is included in input totals; reasoning is included in output totals. They are provider-reported counts, not subscription marginal billing. A tool call or source-changing call is not automatically a repair iteration.

Ruby's agent implemented source and continued extensive self-authored tests until the deadline. Its visible commentary discussed correcting expectations in those tests and attempting differential checking. These statements are the agent's own account; the reliable correctness evidence is the independent private grade, run after collection. The snapshot passed all 43 private cases, but the agent did **not** make a normal completed handoff. Report this as a correct deadline snapshot with a censored completion time, not autonomous completion within the window or a completed first handoff.

Haskell's five tool calls only inspected material; editable-source hashes did not change. The starter snapshot failed grading. The agent exited before the wall deadline because its final model response reached an output limit. No COMPLETE/INCOMPLETE/BLOCKED marker appeared. Under the frozen missing-marker policy, that did not authorize an automatic continuation.

## Output-limit classification incident

The raw Haskell process receipt records exit code 0, no process termination reason and empty stderr. The complete final JSON event is `step_finish` with `part.reason="length"`. The final upstream request completed with HTTP 200 and these native counters:

- Input: 7,948 tokens.
- Output: 32,000 tokens, including 31,997 reasoning tokens.
- Total: 39,948 tokens for that request; 49,846 across the five observed requests.

The adapter's `parse_events` function marks an OpenCode invocation finished only when `step_finish.reason == "stop"`. It therefore treated the legitimate `length` terminal event as a missing terminal event, emitted `CLI failed or missing terminal event`, and classified the result as infrastructure-invalid. The artifact was available and quiescent; there was no observed authentication, network, container, compiler-installation or tool-isolation failure.

Pinned OpenCode 1.18.34 source at commit `aec0b9a6d8898f68f923aaf08b7306d931fd9d76` defines `OUTPUT_TOKEN_MAX = 32_000` in `packages/opencode/src/provider/transform.ts`; `maxOutputTokens` uses that default. This matches the observed 32,000 output tokens. **The origin of this particular request's cap is inferred from source and the matching observation:** the recorder retained model/effort/tool inventory and response usage, but did not retain the request's `max_tokens` field. The receipt alone does not prove which configuration layer selected that cap. No output cap or reasoning effort was changed during the matrix.

## Operator action and labor interpretation

The root AI operator requested a read-only investigation by the harness agent. That investigation inspected the two receipts, process events and pinned upstream source. The root then appended a SHA-bound classification override to `results/subscription-matrix/outcome-overrides.jsonl` at `2026-10-10T16:26:42.758115+00:00` and resumed pending cells using the unchanged runner. The override names the analysis classification `model_output_limit`, while retaining the raw classification `infrastructure_invalid` and original result-file hash `73c9ec28c00ec4e2182aa473f47ba57885090c671a292f64b1b11fe4f190c838`.

This was additional AI/operator measurement work, not candidate coding help. There were zero candidate repairs or extra nudges from this intervention. The diagnosis and resume must remain visible as operational friction; they do not consume or alter the candidate's recorded token budget. Operator investigation token use and human labor duration were not measured here. Human labor seconds remain unknown, not zero or estimated from the failed grade.

The frozen parser can encounter this classification issue again. Any further exception should preserve its original receipt and use an explicit, evidence-bound operational record. It must not silently retry a consumed cell, change the task treatment, or relabel an incorrect artifact as successful.

## Evidence paths

- `results/subscription-matrix/0001-opencode-ruby-T1-r1/result.json`: Ruby timing, invocation, token totals, tool records and private grade.
- `results/subscription-matrix/0001-opencode-ruby-T1-r1/trace/invocation-0.json`: original bounded process output.
- `results/subscription-matrix/0002-opencode-haskell-T0-r1/result.json`: original Haskell classification, native requests, unchanged source and private grade.
- `results/subscription-matrix/0002-opencode-haskell-T0-r1/trace/invocation-0.json`: normal exit and final `length` event.
- `results/subscription-matrix/outcome-overrides.jsonl`: additive operator decision tied to the original result SHA-256.
- `langbench/provider_cli.py`, function `parse_events`: frozen terminal-event classification.
- [Pinned OpenCode output-token default](https://github.com/anomalyco/opencode/blob/aec0b9a6d8898f68f923aaf08b7306d931fd9d76/packages/opencode/src/provider/transform.ts): source evidence for the cap-origin inference.

The broader matrix is still being collected. These two cells support incident diagnosis and per-attempt observations, not a completed comparison of languages, testing conditions or type-system strength.
