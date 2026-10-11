# Later Opus/Sol matrix integration plan

Prepared 2026-10-11 from local repository code and installed CLI help only. This is preparation during the frozen Kimi/GLM collection, not an implementation or qualification. No quota check, model catalog request, provider inference, package update, test or build was performed. Exact Opus 5.5 medium and Sol medium availability remains unknown. No model substitution or paid API fallback is authorized.

## Preserve the experiment

After the current 56-cell cohort closes, add a separate immutable plan for each available requested model: `ledger_engine` × seven languages × T0/T1 × two fresh repetitions = 28 cells/model. Preserve the existing starter, contract, public/private cases and offline `seven` runtime commitments. Use semantic seeds 20261010 and 20261011 for repetitions 1 and 2, the same 900-second initial maximum and at most two eligible 180-second continuations. Freeze deterministic cell order and record cohort/date; later collection is not contemporaneous with Kimi/GLM.

Reuse the visible-terminal assistance policy described in [matrix-effort-protocol.md](matrix-effort-protocol.md): COMPLETE closes collection; eligible INCOMPLETE/BLOCKED can receive the fixed generic nudge; missing markers, deadlines, quota and fatal adapter failures do not authorize continuations. No private grading until agent/tool activity has settled and collection has closed. Do not force equal nudge counts. Preserve every started attempt, including output limits and interruptions; no silent retries.

`matrix.py` currently validates exactly its generated 56-cell Kimi/GLM plan and requires both qualifications. It cannot accept these additions merely by passing different model names. Implement a separately versioned extension plan/runner after collection, preserving validation of complete 28-cell designs, per-provider quota stops, all-attempt journaling, input hashes and no-retry resume. Do not mutate the original plan or accepted results.

## Local Codex integration evidence

Inspected `langbench/appserver.py`, `live.py`, `assistance.py`, `matrix.py`, `subscriptions.py` and `metrics.py`.

- The existing app-server transport defaults to the direct Codex 0.156.0 binary and requires its Code Mode companion. It creates a temporary controller home, links the existing login file, excludes user configuration, checks ChatGPT authentication and matches the exact model/effort against the server catalog. These checks have **not** been executed for Sol in this phase.
- Its dynamic sandbox shell executes only through the Docker worker; native command/file/network/delegation capabilities are rejected. Code Mode isolation has a specific source/structured-output qualification probe. Retain and rerun that probe for the eventual pinned executable pair; past Astra qualification is not Sol qualification.
- `live.run` is a historical development-smoke entry point: it qualifies within each run, uses the historical collector and default runtime, and does not provide the new adaptive-assistance receipt contract. Do not send the later matrix through it unchanged.
- The adapter records turn notifications and provider token updates but does not supply the new terminal-text and per-call source-hash interface. Its interrupt/export boundary needs explicit settlement evidence before reuse with the new collector; an interrupt request alone is not proof that candidate execution stopped.

Build a small Codex adapter around the existing transport, keeping historical behavior and receipts intact. Use `DockerWorker(runtime='seven')`, return exact terminal text/session identity, instrument source digests before/after tool calls, close tool admission and settle activity before export, and feed the existing adaptive collector. Bind the qualification to adapter source, binary and companion hashes, exact resolved model/medium effort, runtime image/toolchain and effective tool configuration. Model names are unresolved in this plan: verify which exact returned identifier corresponds to the user's Sol request later; do not infer identity from a familiar alias.

`metrics.reconcile_provider_usage` already handles explicit provider response counts reconciled with cumulative thread counters. It is a candidate for reuse after fixture/live verification, not authority to equate every raw notification with a new request. Preserve missing coverage and unqualified semantics rather than manufacturing a complete token total.

## Local Claude integration evidence

The user-facing `~/.local/bin/claude` wrapper runs `mise use -g claude` before execution. Do not use it for qualification or collection. A direct installed executable exists at `~/.local/share/mise/installs/claude/2.1.290/claude`; only its local `--help` was executed. Directory version and help are not evidence of entitlement, quota, resolved model identity or wire behavior.

The inspected help advertises `--print`, `--output-format stream-json`, `--include-partial-messages`, exact `--model`, `--effort medium`, explicit `--session-id`/`--resume`, `--tools ""`, `--strict-mcp-config`, `--mcp-config`, `--setting-sources`, `--settings`, `--disable-slash-commands`, and `--no-chrome`. These are proposed building blocks, not a qualified command line. It also explicitly says:

- `--bare` skips OAuth/keychain and restricts Anthropic authentication to API-key/helper routes. Do **not** use it as the subscription isolation shortcut.
- `--restricted` still permits managed/explicit settings and confines rather than removes file tools. It is not sufficient alone.
- `--safe-mode` disables customizations including MCP while retaining built-in tools/plugins; determine whether explicit MCP configuration is compatible before choosing it.
- `--no-session-persistence` prevents resume. Avoid it when qualifying resumable continuations; use a private temporary session store instead.
- `--fallback-model` enables substitutions. Never pass it, and verify no implicit fallback or auxiliary inference escapes exact-model binding.

Proposed architecture: a dedicated Claude CLI adapter uses the existing controller-owned MCP bridge for the sole `sandbox_shell` capability. Use an empty controller working directory and isolated configuration/session directories; deny all built-in tools and permit only the exact registered bridge tool. Disable skills, hooks, plugins, background activity, browser integration and delegation through verified effective configuration. Inspect managed configuration without modifying it; fail closed if isolation cannot be established. Help flags alone do not establish resolved capabilities.

Before live qualification, determine the subscription OAuth storage/refresh locking behavior from local implementation or official evidence. Preserve the canonical refresh/lock namespace rather than creating an independent rotating credential copy. Never print credentials or expose them to the candidate container. Removing user configuration must not silently replace subscription OAuth with an environment API key. Do not use `setup-token`, login, upgrade or global configuration mutation as automatic setup steps.

Pin the eventual direct binary hash and exact Opus 5.5 identifier; verify medium is applied to actual requests/session configuration. Prove subscription route, no fallback, MCP-only tool inventory and continuation identity. If request-level recording requires a transport shim, develop and qualify it separately; do not assume the current Kimi/OpenCode shim understands Claude authentication, streaming or usage. If native telemetry cannot establish complete coverage, report unknown/partial usage explicitly rather than claiming comparable totals.

## Required receipt semantics

Use the same all-attempt reporting vocabulary across adapters while retaining native events:

| Evidence | Required semantics |
|---|---|
| Identity | Requested and resolved model, effort, CLI/companion hashes, subscription mode, adapter/config/runtime commitments; no account IDs or credentials in published summaries |
| Terminal state | Separate normal process exit, completed model handoff, output-limit stop, deadline, quota, malformed/truncated stream and infrastructure failure; retain provider stop reason and raw classification |
| Artifact | Immutable initial and actual continuation checkpoints; source and artifact hashes; settled export boundary; private grades only after shutdown |
| Work | Monotonic invocation/tool duration, preparation/cleanup/grading separately, ordered commands/results and source changes; source stability is not proven time-to-correctness |
| Usage | Native input/cache-read/cache-write/output/reasoning fields with provider-specific definitions, scope, completeness and request reconciliation; unknown is not zero |
| Assistance | Exact generic prompt, visible eligibility reason, session continuity and delivery status; no private feedback or automatic output-limit continuation |
| Operations | Separate setup/qualification/incident effort from candidate effort; measured human labor remains unknown unless actually observed |

Do not assume Claude cache tokens are subsets of input merely because that is true of a previously inspected provider. Verify each native field definition and aggregation scope. Do not add reasoning twice or count cumulative and request totals together. CLI aggregate and request-native totals stay distinct unless reconciled. A successful correctness grade at timeout is a correct deadline snapshot, not normal completion.

The Haskell length-stop incident documented in [subscription-matrix-operational-audit.md](subscription-matrix-operational-audit.md) is a required terminal-classification fixture. Output budget exhaustion is valid effort/artifact evidence where established; do not discard it as infrastructure failure because final text is absent. Any later interpretation override must validate original result SHA/cell identity and remain additive.

## Implementation and verification sequence after current collection

1. Close and preserve the Kimi/GLM cohort. Perform the user-authorized quota/availability checks only then. Record unavailable targets without substituting another model; a catalog listing alone does not prove usable allowance.
2. Implement separate adapters and extension-plan dispatch without changing frozen assets. Keep transport/CLI lifecycle below orchestration, assistance independent of grading, and private cases controller-only.
3. Use fake transport/CLI tests for exact model/effort rejection, fallback/auxiliary requests, MCP capability denial, session mismatch, process-group death, in-flight tool settlement, failed export and immutable snapshots. Exercise cancellation while a tool is active, not just an idle CLI.
4. Add parser/accounting fixtures for normal completion, length stop, quota, clean exit without a recognized terminal event, timeout with complete JSON prefix plus truncated final frame, duplicate/cumulative usage, missing request coverage and cache/reasoning semantics. Verify unavailable usage remains null and partial observations remain visible.
5. Test assistance and matrix integration: zero/one/two eligible nudges; COMPLETE/missing marker/deadline/output-limit do not trigger unapproved continuation; quota stops only that provider; resume never repeats a consumed cell; altered qualification/plan/runtime fails before inference. Verify full 28-cell coverage and exact seed/condition mapping.
6. Run harmless live qualification for each available exact model/medium setting, including host-canary denial, sole sandbox-tool invocation, session resume and usage evidence. Keep all failures and setup effort separately. No coding cell begins until bindings are frozen and reviewed.
7. Collect sequentially under the established host controls. Preserve raw receipts, then grade and report per-language/test-condition correctness, effort and outstanding work. Compare providers as configured model-plus-agent treatments; later cohorts, different agents and token vocabularies prevent a clean model-only causal comparison.

No ready-to-run inference command is provided because model identifiers, authentication isolation, live capability enforcement and allowance have not yet been verified. This document is the implementation checklist for that later gate, not a claim that either adapter is ready.
