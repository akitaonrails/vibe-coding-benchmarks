# Later exact-model cohorts

The original 56 Kimi/GLM attempts closed before any Claude/Codex availability check. Their results are preserved in [the first-cohort report](subscription-matrix-results.md). Follow-up cohorts use separately frozen plans and qualification receipts; they do not replace or get silently pooled with those observations.

Each available target receives 28 cells: seven languages × T0/T1 × two repetitions. Exact targets are `gpt-6-sol` medium through the existing ChatGPT subscription and `claude-opus-5-5` medium through the existing Claude subscription. No fallback model, API-key route, purchased allowance or quota reset is part of this protocol.

`langbench.later_matrix` retains the original Kimi arm's cell order, task, semantic seeds, repetitions, block labels and budgets. Only the provider/model/effort and cell identifier change. Initial work is capped at 900 seconds; the same visible-terminal policy permits at most two eligible 180-second nudges. Private grades never trigger a continuation. The separate `seal-v1` source-retention correction is bound into future qualifications; it makes this an explicitly different instrumentation cohort.

The runner shares the original durable scheduling implementation. Plans must exactly match the generated 28-cell design. Resume validates plan, qualification, harness/input commitments and saved result hashes; started attempts are never retried. A quota result is preserved and remaining cells for that target are marked unrun. An unknown infrastructure incident stops dispatch for diagnosis before pending cells resume. Provider cohorts run separately, so one provider's allowance does not block the other.

The ten original/follow-up matrix tests cover paired-design parity, altered plans, no-repeat resume, interruption and quota preservation, and changed bindings. This is scheduling evidence, not live adapter qualification.

On October 11, 2026, after the first cohort closed, a non-inference Codex app-server check confirmed ChatGPT authentication, the exact Sol model with medium support, and ordinary usage allowed; the reported weekly window was 15% used. Claude's canonical OAuth usage endpoint reported Max authentication, 0% five-hour and 97% weekly usage, with extra usage disabled. The installed CLI supports the exact public Opus identifier; account-specific entitlement still requires a harmless live qualification. Neither percentage guarantees enough allowance for all 28 cells. Sanitized local receipts are under `results/later-model-availability/`.

Claude's ambient configuration selected API-key authentication during the check. The benchmark adapter must explicitly exclude that route while preserving canonical subscription OAuth state. Public model configuration is documented by [Claude Code](https://code.claude.com/docs/en/model-config); public availability is not account entitlement evidence.

Generate a new immutable plan with `python -m langbench.later_matrix plan codex PATH` (or `claude`). Run only after the corresponding exact adapter qualification and integration review: `python -m langbench.later_matrix run PLAN OUTPUT --qualification RECEIPT`. Add `--resume` only after diagnosing an incident or a controller interruption. This document does not assert that either follow-up coding cohort has run yet.
