# Results at a glance

This is a completed **exploratory** campaign, not a language leaderboard. There is one ledger maintenance task, seven languages, four model/agent configurations, two test conditions and two repetitions: 112 attempts. T0 has no supplied behavioral tests; T1 supplies 27 histories and a driver. Agents may write tests in either condition. All artifacts are graded against the same 43 private histories after collection.

## Correctness and observed effort

| Metric | Kimi K3 high | GLM 5.3 high | Opus 5.5 medium | Sol medium |
|---|---:|---:|---:|---:|
| Planned attempts | 28 | 28 | 28 | 28 |
| Normal correct completion | 17 | 7 | 25 | 28 |
| Correct artifact at deadline | 7 | 9 | 0 | 0 |
| Failed saved artifact | 2 | 7 | 3 infrastructure-interrupted | 0 |
| No final grade | 2 | 5 | 0 | 0 |
| Correct T0 / planned | 10/14 | 6/14 | 14/14 | 14/14 |
| Correct T1 / planned | 14/14 | 10/14 | 11/14 | 14/14 |
| Complete token accounting | 20/28 | 16/28 | 25/28 | 28/28 |
| Median native tokens, complete records only | 530,257 | 1,171,137 | 119,770 | 176,002 |
| Recorded tool calls | 462 | 780 | 192 | 266 |
| Known source-changing calls | 68 | 98 | 53 | 50 |
| Reactivation nudges | 0 | 0 | 0 | 0 |

All three Opus infrastructure incidents were T1 attempts. Thus Opus passed 25/25 eligible outcomes; its 11/14 planned T1 count is not evidence that tests harmed correctness. Overall, 93 artifacts passed: 77 normal completions plus 16 deadline snapshots. Twelve artifacts failed, including the three interrupted Opus attempts, and seven grades are unavailable. Missing grades are not semantic failures.

Native token definitions and tokenizers differ. Repeated context/cache reads are included, complete-usage coverage differs, and the Opus complete subset coincides with successful attempts. Do not interpret these medians as equivalent compute, money, or a model-efficiency ranking. Source-changing calls include formatting and warning cleanup, and are not repair iterations. The first cohort's automatic repair-cycle classifier lacked coverage; its zero counts are not zero debugging.

## Language comparisons

Each language has four planned attempts per model (T0/T1 × two repetitions). Correct counts include deadline snapshots. A shortfall from four may be a failed artifact or missing/infrastructure evidence, not necessarily a language error; consult the detailed condition tables.

| Language | Kimi correct | GLM correct | Opus correct | Sol correct | Sol median seconds | Sol median native tokens |
|---|---:|---:|---:|---:|---:|---:|
| Haskell | 2/4 | 2/4 | 3/4 | 4/4 | 75.0 | 184,744 |
| Rust | 4/4 | 2/4 | 4/4 | 4/4 | 79.8 | 188,123 |
| C# | 4/4 | 3/4 | 3/4 | 4/4 | 60.7 | 171,554 |
| Kotlin | 4/4 | 2/4 | 4/4 | 4/4 | 64.9 | 170,611 |
| TypeScript | 4/4 | 1/4 | 4/4 | 4/4 | 53.2 | 147,501 |
| Python | 3/4 | 2/4 | 4/4 | 4/4 | 77.1 | 138,248 |
| Ruby | 3/4 | 4/4 | 3/4 | 4/4 | 81.5 | 185,555 |

Sol effort medians pool its four attempts per language; they are not averages of T0/T1 medians. All four have valid outcomes and complete usage. Time includes agent orchestration and validation. Language order is categorical, not ranked. Opus's missing successes for Haskell, C# and Ruby are the three infrastructure incidents.

On this task, Sol's Rust and Ruby effort was similar; TypeScript had the lowest median time and Python the lowest median tokens. Four observations per language and one task cannot establish a general ranking. Stronger typing did not yield a monotonic pattern, but absence of that pattern does not establish diminishing returns or equivalence.

## Conclusions and limits

- Supplied tests accompanied 24 correct Kimi/GLM artifacts versus 16 without them. This descriptive contrast includes deadline snapshots and unequal missing evidence.
- Opus/Sol reached a correctness ceiling (53/53 eligible attempts). The task was too easy for these configurations to discriminate correctness; frontier-level difficulty remains unqualified.
- Harness work is separate from coding difficulty. Opus required instrumentation corrections and six qualification attempts; consumed candidates were never repaired or retried. Operator tokens and human repair hours were not measured.
- All 112 attempts used zero reactivation nudges. The experiment therefore does not measure whether nudges rescue stalled agents.

## Backpressure is a separate, incomplete comparison

Eight reference trials offered 200 messages/sec with 10,000 messages each. At eight handlers, all four stacks delivered about 93–95 effects/sec during publication and ultimately drained. At 64 handlers, rates were about 85–89/sec with unfinished work and timeout overlap. Shared sink/broker/publisher headroom was not established; the high-concurrency measurements cannot rank stack capacity. These are reference runtime trials, **not controlled AI coding attempts**. No Elixir engineering-effort advantage has been established. The stronger load staircase and real worker-death protocol remain proposed.

## Evidence

[Published 112-row measurements](data/matrix-results.json) · [public evidence limits and reproduction](data/README.md) · [full combined analysis](followup-matrix-results.md) · [Kimi/GLM condition tables](subscription-matrix-results.md) · [Opus/Sol condition tables](followup-language-effort.md) · [queue measurements](scalability-load-validation.md) · [pressure proposal](queue-pressure-research.md).
