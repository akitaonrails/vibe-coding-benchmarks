# Languages benchmark: research, protocol and implementation

Research began on 2026-10-10. The seven-language ledger campaign now has terminal records for all 112 planned attempts across Kimi K3 high, OpenCode/GLM 5.3 high, Opus 5.5 medium and Sol medium. There are 93 correct artifacts: 77 normal correct completions and 16 correct deadline snapshots. Twelve saved artifacts failed (including three Opus infrastructure incidents), and seven final grades are unavailable. These are exploratory results from one task instance with two repetitions per language/model/test condition, not a confirmed typing hierarchy or a frontier-difficulty qualification.

Start with [the four-cohort results and limitations](followup-matrix-results.md), [follow-up language/condition effort tables](followup-language-effort.md), and [the original 56-attempt results](subscription-matrix-results.md). Native token totals, source sizes, tool activity, missing evidence and operational incidents remain separately visible.

The question is whether stronger static guarantees improve **verified correctness per unit of agent effort**, and whether their marginal benefit shrinks when useful tests are available. We should permit the evidence to support typing, tests, their combination, or neither under the selected workload.

For the initial Ruby/Rust development slice, see [its implementation and validation history](implementation.md). [The experimental design](benchmark-design.md) and [the difficult task catalog](task-catalog.md) describe the broader research proposal. Supporting documents:

- [Research findings and sources](research-findings.md): what existing evidence establishes, and where this experiment adds something.
- [Larger ledger calibration results](ledger-calibration.md): both initial solutions passed; difficulty remains unqualified.
- [Measurement and analysis](measurement-and-analysis.md): tokens, time, errors, nudges, uncertainty and decision rules.
- [Codex harness plan](codex-harness-plan.md): subscription execution, isolation, telemetry and lessons from the reference project.
- [Original rollout proposal](rollout-plan.md): historical qualification, pilot and expansion plans, not current collection status.

The implemented roster is Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby. Ruby/Rust came first, followed by native ports and shared isolated runtime qualification. These are not an ordered “type strength” ladder. All use the same ledger behavioral contract; proposed annotation/checker ablations remain future work.

Astra low / Sol medium / Luna high was the original model proposal. Later user instructions selected Kimi/GLM first, then the exact available Opus/Sol configurations; all four 28-cell cohorts are now closed. The old six-cell Astra ledger calibration and 48-cell compact smoke plans remain historical development commands, not the current campaign or evidence of additional completed comparison cells. [The difficulty audit](difficulty-audit.md) records earlier calibration limitations.

The comparison is supplied tests (T1) versus no supplied tests (T0), with independent private grading after candidate shutdown. The current assistance policy permits at most two bounded adaptive nudges for visible unfinished work or tool quirks; it does not force continuations or reveal private grades. Earlier smoke experiments used fixed nudges and remain separate.

The reference project at `~/Projects/llm-coding-benchmark` was inspected read-only. Its existing task results inform difficulty selection, not the findings of this new experiment. No personal Ruby/Rust stack preference was applied: choosing a preferred implementation language would bias this project.

A separate [queue scalability and reliability track](scalability-benchmark.md) tests Elixir/OTP/Broadway, Rust with libraries and Rails/Bunny. Its implemented runtime runner exercises backpressure and failure using real RabbitMQ, native workers and an independent durable sink. Agent-effort integration and capacity qualification remain separate gates; see [implementation and validation](scalability-implementation.md) and [larger workload evidence](scalability-load-validation.md). This compares ecosystems and does not extend the typing experiment into a claim about Elixir's type system.

## Completed subscription campaign

- [Complete 56-attempt results](subscription-matrix-results.md), including source sizes and measurement limits
- [Matched language effort traces](subscription-language-effort-audit.md) and [semantic failure audit](subscription-semantic-failure-audit.md)
- [Closed Opus/Sol results](followup-matrix-results.md), [language effort tables](followup-language-effort.md), [collection protocol](later-model-matrix.md) and [source-retention correction](artifact-retention-validation.md)
- [Opus trace audit](opus-language-effort-audit.md) and [Sol trace audit](sol-language-effort-audit.md): compiler repairs, verification helpers and build workflow costs
- [Coding effort and intervention protocol](matrix-effort-protocol.md)
- [Subscription adapter design](subscription-adapters.md) and [implementation evidence](subscription-implementation.md)
- [Seven-language expansion](seven-language-expansion.md) and [runtime validation](seven-language-implementation.md)
- [Further queue pressure research](queue-pressure-research.md)

The later subscription instructions superseded the initial model roster for this
campaign: Kimi K3 high and OpenCode/GLM 5.3 high ran first, followed, after subscription qualification,
by exact Opus 5.5 medium and Sol medium. Historical Astra smoke results remain
separate. The current assistance policy uses eligible visible incomplete handoffs;
it does not force two nudges on every attempt.
