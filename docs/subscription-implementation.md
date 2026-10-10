# Subscription adapter implementation and qualification evidence

Status: 2026-10-10, independent provider gate3 passed; final bound capability checks passed. Both installed subscription routes have completed harmless live capability checks. No ledger coding attempt has been launched through these adapters. Source changed during qualification work, so the successful development receipts below are evidence of observed behavior, not reusable final bindings. Refresh qualification after the code gate and before freezing the matrix.

## Entry points and collection

`langbench.subscriptions.qualify_provider(provider, output, model=..., effort=..., seconds=...)` creates a separate empty candidate workspace and performs two bounded, harmless turns. `run_subscription(task, language, output, provider=..., model=..., effort=..., tests='T0'|'T1', qualification=..., ...)` requires an already passed qualification with matching adapter-source, executable, runtime and treatment bindings. It never inserts a qualification conversation into the coding session. Root matrix integration calls this function sequentially.

The coding manifest freezes seed, replicate, block, initial artifact, model/effort, provider identity, environment and assistance policy before inference. The collector stores immutable first-handoff and actual continuation checkpoints. It follows `terminal-status-v1`: a unique final COMPLETE marker closes collection; INCOMPLETE/BLOCKED may receive up to two fixed neutral reactivations; an absent or malformed marker closes with unknown status. Timeout, quota and fatal infrastructure stops do not cause reactivation. No private grade enters the collection process. Grading begins only after the provider and worker have closed.

`collection.json` retains invocation terminal text/status, tool records, usage records, checkpoint hashes and assistance decisions. `interventions.jsonl` is an append-only ledger with separate planned, dispatch-requested and invocation-returned events. An interrupted dispatch is not silently counted as delivered assistance. Actor/category/action/timestamp/source evidence remain distinct from coding revisions. Historical Codex fixed-nudge behavior remains separate.

## Actual routes and capability enforcement

The direct Kimi2.1.1 executable uses `kimi-code/k3` with wire model `k3` through `https://api.kimi.com/coding/v1/chat/completions`. The installed canonical managed OAuth store and lock directories are shared by directory identity, preserving atomic token replacement and refresh coordination. The provider's canonical base URL stays unchanged; only the model-level transport URL points to the local recorder. This matters because Kimi derives its OAuth slot from the provider URL. No refresh-token copy or independent refresh chain is created.

The direct OpenCode1.18.34 executable uses `zai/glm-5.3`, the existing environment credential, and `https://api.z.ai/api/coding/paas/v4/chat/completions`. Main and auxiliary model configuration select the same exact model and high effort. Auxiliary requests are retained in usage, rather than discarded as invisible overhead. Global plugins/configuration are excluded through a temporary home/XDG environment and explicit isolated configuration.

A controller-owned stdio MCP server exposes only `sandbox_shell`. Kimi's global and profile tool allowlists and OpenCode's deny-by-default permissions restrict execution. A narrow local recorder independently examines the actual upstream request and refuses an unexpected model, effort or tool inventory before forwarding. Kimi serializes effort as `thinking: {type: enabled, effort: high}`; OpenCode/Z.ai uses `reasoning_effort: high`. The recorder has fixed upstream paths, rejects redirects, logs no authentication headers and sends no arbitrary destination requests.

The qualification requires a prescribed command to execute through the bridge, absence of a host-only canary in the candidate container, the exact marker artifact, terminal status extraction, same-session continuation, actual wire tool/model/effort evidence, and complete observed native request usage. Agent claims about inaccessible tools are not the evidence: the request inventory and controller dispatch boundary establish which capability was available. Candidate execution uses the pinned seven-language image with no network, host home, repository, grading oracle or Docker socket. This is a pinned configuration qualification, not a proof about every possible future CLI version.

## Lifecycle and censored artifacts

Each invocation has bounded streams and a monotonic deadline. Completion closes tool admission and waits for active bridge dispatch and HTTP handlers before reading late records or exporting source. A failure to settle cannot produce a supposedly immutable checkpoint. Normal protocol cancellation notifications do not expose another tool. Incomplete trailing JSON at a timeout preserves the bounded complete-event prefix and timeout outcome.

A candidate command timeout can retire its worker. If the final artifact cannot be safely recovered, the checkpoint explicitly has `artifact_available: false`, remains a censored timeout, and receives no grade. An earlier source snapshot is never silently relabeled as final. Capability violations and failed qualification remain infrastructure-invalid. The recorder latches HTTP429 and blocks subsequent SDK retries upstream; the receipt says quota-or-rate stop unless more precise evidence exists. No provider/model fallback or coding retry is inserted.

## Token evidence and repair effort

Every observed upstream model request has a native record, including auxiliary requests and placeholders for missing usage. Native Chat Completions input includes cached input; output includes reasoning where the provider reports that subset. Native totals use the explicit input/output/total relationship and never add cache or reasoning twice. Cache-write data remains unknown when absent.

`provider_reported_total` is available only with verified per-request evidence and coverage of every invocation. `provider_reported_known_subtotal` preserves known request costs when another request/turn is incomplete; it is not a full total. These are observed provider counters, not marginal subscription billing or a common compute unit across providers. CLI-normalized counters remain separately available in `cli_usage_records`; their zero-filling and normalization are not treated as native evidence.

Tool telemetry retains command/arguments, result, exit/termination, duration, rejection status and editable-source hashes before/after. Full checkpoint hashes are separate. These records support observable check→revision→check analysis; tool calls do not automatically equal iterations. Provider-agent bookkeeping and reactivation effort count as part of the configured treatment. Adapter authoring, compiler preparation and qualification work are separate setup friction. Each attempt also records monotonic `timing` fields for preparation/adapter setup, collection plus snapshot/cleanup, private grading and total wall time. Failures retain elapsed time in the incomplete phase. These walls are separate from model-invocation active seconds and token totals.

## Preserved qualification history

The table reports observed invocation elapsed time and known native request totals from saved receipts. A dash means unavailable, not zero. Some failed attempts stopped before any forwarded model request was recorded. No human repair hours were measured or estimated.

| Receipt directory under `results/` | Result | Invocation seconds | Observed request count | Known native token subtotal | Finding |
|---|---|---|---:|---:|---|
| `subscription-qualification-kimi-v1` | Failed before invocation | — | 0 | — | Incorrect credential-file lookup; no coding/model request recorded |
| `subscription-qualification-kimi-v2` | Failed | 1.537 | 0 | — | Local provider URL selected an unpopulated OAuth slot |
| `subscription-qualification-kimi-v3` | Failed | 90.020 | 0 | — | Recorder rejected Kimi's different native effort shape; historical receipt retains original classification |
| `subscription-qualification-kimi-v4` | Passed, binding superseded by subsequent fixes | 15.203 + 4.100 | 3 | 2,800 | Canonical OAuth route, enforced native effort/tools, nonce and same-session continuation |
| `subscription-qualification-opencode-v1` | Failed | 21.143 | 3 | 2,963 | Nonce worked; MCP cancellation handling and auxiliary effort needed correction |
| `subscription-qualification-opencode-v2` | Failed | 14.510 | 2 | 1,807 | Auxiliary request without required effort blocked before upstream |
| `subscription-qualification-opencode-v3` | Passed, binding superseded by subsequent fixes | 21.133 + 7.318 | 5 | 5,574 | Main/auxiliary request accounting, tool boundary and explicit continuation verified |

All rows are setup/qualification evidence, excluded from candidate coding totals. Failed receipts are retained. The final source-bound qualifications appear below; none of the earlier development attempts authorizes bypassing the binding check.

## Final source-bound qualification after review

Independent provider gate3 passed, including21 focused fake tests. Both final harmless qualifications subsequently passed, and their binding hashes, inspected executables, adapter source hashes and runtime configuration were rechecked against current files. No production code changed during this refresh.

| Final receipt | Invocation seconds | Native requests | Native reported total | Binding SHA-256 |
|---|---|---:|---:|---|
| `results/subscription-qualification-kimi-final/qualification.json` | 13.828 + 3.977 | 3 | 3,002 | `6fd8bca3cced66cfb6520c1321fcf26131b1788e4d7f98a149fa6a7b1c49f6a5` |
| `results/subscription-qualification-opencode-final/qualification.json` | 23.202 + 7.951 | 5 | 5,545 | `929651ec2aaebba4de2958744ca57cdb18c1d20d18c1f5e0a581522d21502129` |

Final qualification-file SHA-256 values are respectively `1494b1a256fcbe4903b9316d767cdf310d2f61e40ec6f3c8d73b05c7f0aafb5b` and `96219279700ada861dd1dba7ba4b4067f1a87158d951b55da4ddd9d113900e95`. Each has `native_request_coverage_complete: true` and `all_invocations_covered: true`. The legacy CLI-normalization `completeness` field remains separate and unknown; it does not negate the explicitly qualified native-request total. Billing and human labor remain unmeasured.

These receipts qualify the specified adapter configuration, not ledger correctness or frontier task difficulty. They authorize no model substitutions or private-feedback repair loop. Full-suite/native parity and the frozen matrix gate remain separate prerequisites to coding collection.
