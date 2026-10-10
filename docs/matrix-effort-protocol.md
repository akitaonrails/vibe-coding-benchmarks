# Coding difficulty and intervention protocol

Status: preparation for a frozen development matrix, 2026-10-10. This incorporates
the user's latest instruction: small reactivation nudges are allowed; iteration
counts must not be forced equal; repeated evaluator-driven repair loops are not
allowed. It supersedes the earlier unconditional two-nudge policy **for this new
matrix only**. Historical Codex receipts remain unchanged and separate.

## Matrix and interpretation

Initial scope: `ledger_engine` × Rust, Haskell, C#, Kotlin, TypeScript, Python and
Ruby × Kimi K3 / OpenCode GLM 5.3 × T0/T1 × two fresh repetitions = 56 attempts.
Exact subscription routes, model identifiers, native effort settings and toolchain
identities must pass qualification before the plan is frozen. After this stage,
check Claude/Codex quotas and model availability; if available, collect Opus 5.5
medium and Sol medium on the same 28 language/condition/repetition cells per
model. No model substitution or separate paid API fallback is authorized.

Both providers are available through the user's subscriptions. Authentication
transport can still use API-shaped requests; the qualification must establish the
subscription endpoint and existing login/credential route, not infer billing from
whether the CLI uses HTTP. Do not expose credentials in receipts.

The experimental unit is one fresh coding attempt. Cases and behavior groups
inside one ledger instance are not independent coding tasks. This is exploratory:
the ledger remains difficulty-unqualified, and two repetitions cannot establish a
universal language ranking or causal effect of stronger typing. Report differences
within each model/test condition and retain contradictory or ceiling outcomes.
The two CLI agents are also different treatments; model-only claims are unsupported.

## Primary evidence, preserved for every attempt

| Dimension | Required record | Interpretation |
|---|---|---|
| Autonomous correctness | Immutable first-handoff source, private result after collection | Whether the agent completed the contract without operator reactivation |
| Assisted correctness | Separate source/result after each eligible nudge | Recovery with additional assistance, never relabeled autonomous |
| Model effort | Request-scoped raw usage, active elapsed time, terminal status | Include unsuccessful attempts, interruptions and continuations |
| Tool activity | Ordered commands, outputs, exit/termination, duration and source-change evidence | A tool call is not automatically one repair iteration |
| Repair activity | Observable edit → build/test/check → follow-up edit/check sequences | Count observed cycles with the rule/version and uncertainty retained |
| Failure category | Compile/check, runtime, assertion/behavior, tool argument, environment, quota, unknown | Avoid attributing an unavailable compiler or adapter defect to language correctness |
| Operator intervention | Actor, category, reason, timestamp, exact prompt/action, source hashes when changed | Distinguish neutral nudges, environment repair, technical hints and direct code repair |
| Remaining work | Private failures and unresolved behavior groups at collection close | Failure remains an outcome, not a missing successful sample |

Save input, cache-read, cache-write, output and reasoning components only where
the provider actually supplies and defines them. Preserve raw fields and whether
usage is request-scoped or cumulative. Do not double-count cached input or reasoning
already included in output. Unknown counts remain unknown; a partial total is
labeled partial. Cross-provider token totals are not a common compute/cost unit.
Within-model language comparisons are the primary token contrast.

Record cumulative totals at first handoff, each actual nudge and final collection.
A tiny nudge prompt can cause a large continuation: report both prompt size and
all continuation work. No optional nudge is inserted merely to match another
language's iteration count. No completed attempt is repeatedly reopened to spend
its remaining budget.

## Bounded assistance and collection boundary

Freeze equal maximum work windows before collection: proposed 900 seconds initial
and at most two 180-second continuations. Actual iteration counts, tool calls,
wall time and nudge counts may differ. Ordinary edit/build/debug work inside the
agent invocation is permitted and measured; the prohibited loop is an external
controller repeatedly grading and feeding corrective advice back to the agent.

A nudge is eligible only after a visible incomplete/stalled terminal handoff,
such as an explicit unfinished status, unnecessary permission request, or tool
misunderstanding. Capture the terminal message and eligibility reason before
sending it. Prefer a simple common final-status marker to an additional LLM judge
or ambiguous keyword matching; its exact format and missing-marker handling must
be qualified and frozen with the adapters. A marker is the agent's self-report,
not proof that its implementation works.

Use a short, fixed reactivation message that refers to the existing task and
available tools. It may clarify the public execution boundary but must not supply
an algorithm, a private failing case, or language-specific repair instructions.
An explicit completed handoff closes collection without a nudge. Quota failures,
fatal adapter failures and expired work windows are handled as those outcomes,
not as permission to loop. Missing markers must not be silently interpreted as
correctness or an entitlement to repeated continuations.

No private grader runs until the candidate agent and worker have stopped and all
snapshots are immutable. Only then grade the saved checkpoints. Private outcomes
cannot determine nudge eligibility, prompt content or extra budget. Every external
intervention appears in a separate ledger. If an operator provides a technical
hint or changes candidate code, preserve the preceding result and label subsequent
work as an additional assisted treatment, outside the primary matrix.

## Harness friction versus coding difficulty

Record one-time setup issues separately: compiler/dependency installation,
protected build-scaffold changes, offline cache preparation, adapter failures and
qualification retries. Preserve relevant command receipts, durations and issue
categories. These are useful practical costs but depend on this host and prior
cache state. Do not add benchmark-authoring tokens or setup wall time to a
candidate's coding totals, or compare warmed Ruby setup with a new Haskell install
as if they were matched per-attempt work.

During collection, environment repairs invalidate or explicitly deviate the
frozen setup; they are not silent help. Preserve the affected attempt and record
which cells need replacement under the same rule for all languages. A candidate
compilation error in a qualified working environment remains candidate evidence.
A bounded nudge that helps the agent navigate a tool is intervention evidence,
not an erased infrastructure incident.

“Manual work required” must be observed, not invented. If no human performs a
repair, report outstanding defects and actual operator interventions; do not
estimate human hours from failed tests or reference patches. Work performed by
this coordinating assistant is AI/operator assistance, not measured human labor.
Zero recorded human edits means none were provided, not that a failed solution
would require no work.

## Analysis deliverable

The main table is language × model × T0/T1, with independent-attempt counts,
first-handoff success, success after actual nudges, work-window exhaustion,
observed repair cycles, tokens/time, intervention counts/types and unresolved
failures. Include every frozen cell and show missing/quota/invalid cells explicitly.
Use per-attempt data alongside summaries; with two repeats, avoid false precision.

Provide a separate behavior-group failure table for authorization, identity,
transaction conflicts, durability/recovery and migration. Do not allocate an
attempt's entire token total to each group or pretend these groups are separate
coding runs. A success-only effort table may supplement the main table, but must
be labeled conditional and cannot replace the all-attempt comparison.

Maintain two separate conclusions: which configured languages performed better
on this task, and what extra operator assistance was actually necessary. Neither
requires equal iteration counts or an assumed ranking of type-system strength.
