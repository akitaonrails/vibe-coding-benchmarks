# Follow-up matrix results and combined interpretation

Both 28-attempt follow-up cohorts are closed. The committed reports preserve all 56 identities, including three Opus infrastructure incidents. The closed [Kimi/GLM cohort](subscription-matrix-results.md) remains unchanged and independently reportable.

The follow-ups add exact Sol medium and Opus 5.5 medium, each with 28 planned attempts: seven languages × T0/T1 × two repetitions. Plans preserve the earlier Kimi arm's order, semantic seeds, task and budgets. Availability, qualifications and collection are distinct events; qualification success does not guarantee enough remaining subscription allowance to finish a cohort.

## Closed outcomes

| Cohort | Planned | Normally completed and correct | Correct deadline snapshot | Failed saved artifact | Final correctness unknown | Status |
|---|---:|---:|---:|---:|---:|---|
| Kimi K3 high | 28 | 17 | 7 | 2 | 2 | Closed; original instrumentation |
| OpenCode GLM 5.3 high | 28 | 7 | 9 | 7 | 5 | Closed; original instrumentation |
| Codex Sol medium | 28 | 28 | 0 | 0 | 0 | Closed; all outcomes valid |
| Claude Opus 5.5 medium | 28 | 25 | 0 | 3 (infrastructure artifacts) | 0 raw-grade unknown | Closed; three infrastructure-attributed outcomes |

The first-cohort failure column describes graded artifacts, including unchanged starters after model output limits. It is not an infrastructure-attributed language-failure count. The Opus cohort has 25 eligible semantic outcomes, all correct, and three infrastructure-attributed outcomes; its three failed raw artifacts are not counted as language semantic failures. Across the four cohorts, all 112 planned identities have terminal records: 93 correct artifacts comprise 77 normal correct completions and 16 correct deadline snapshots. Twelve saved artifacts failed, including the three infrastructure-attributed Opus artifacts; seven final grades are unavailable. These bookkeeping totals do not turn infrastructure interruptions into language failures or make the cohorts causally interchangeable.

The [language × condition effort tables](followup-language-effort.md) cover all 28 Opus and 28 Sol attempts, with known denominators, source sizes, tool/source-changing calls, token components and operational delay. Primary wall medians require valid-development status and confirmed coding start, irrespective of grade. Raw infrastructure effort remains in the generated per-attempt reports. No follow-up attempt received a nudge, so initial and final checkpoints coincide; there is no measured nudge-rescue effect in these cohorts.

Sol has complete native usage for 28/28 attempts, totaling 4,842,146 inclusive tokens, with 289 completed response identities and 266 tools. Opus has complete usage for 25/28, totaling 3,504,507 disjoint native tokens within that coverage subset, with 205 native-request observations and 192 tools across all attempts. These totals are not pooled: tokenizer, caching, reasoning and request scopes differ. Both configurations reached a correctness ceiling: Sol 28/28 and Opus 25/25 eligible outcomes. The three Opus infrastructure incidents remain outside that semantic denominator.

Reports are `results/sol-medium-matrix-final/` and `results/opus-medium-matrix-final/`, generated with plan, receipt, source and recursive instrumentation-lineage validation. The original 56-attempt report remains unchanged. A mechanically counted source-changing call is not a repair iteration; unclassified checks and missing usage remain unknown rather than zero debugging or zero cost.

## Qualification and setup costs

| Qualification receipt | Outcome | Native tokens | Role |
|---|---|---:|---|
| `results/sol-medium-qualification-1/qualification.json` | Passed | 36,103 | Exact Code Mode isolation, host canary, same-session resume and native usage reconciliation |
| `results/opus-medium-qualification-1/qualification.json` | Failed effective-configuration check | 3,135 | Exact medium/OAuth tool requests succeeded, but CLI initialization still listed built-in plugins |
| `results/opus-medium-qualification-2/qualification.json` | Passed | 4,983 | All pinned built-in plugins disabled; exact route, tools, resume and native accounting verified |
| `results/opus-medium-qualification-3/qualification.json` | Passed | 5,005 | Qualified the serialized-admission successor |
| `results/opus-medium-qualification-4/qualification.json` | Failed | Partial 5,042 | Failed qualification retained; incomplete usage is not a total |
| `results/opus-medium-qualification-5/qualification.json` | Failed | Partial 3,139 | Failed qualification retained; incomplete usage is not a total |
| `results/opus-medium-qualification-6/qualification.json` | Passed | 5,008 | Three native requests; 17 operational records include 14 proven-unsent preflight HTTP 429 checks |

These are setup/model-probe costs, excluded from candidate coding totals. All failed Opus qualifications are preserved rather than replaced. Sol's total and Opus's disjoint token totals have different native definitions, so they are shown separately, not summed into a common compute measure. Non-inference availability checks and AI-operated debugging are further setup work; their unmeasured token/time costs remain unknown. See [the qualification ledger and collection protocol](later-model-matrix.md).

## Known instrumentation differences

The later cohorts use `seal-v1`: after a bounded command timeout, writers stop and submitted source may be sealed before the worker is removed. The original cohort could lose that source and therefore the final grade. Retention receipts record cutoff, writer-stop and sealing evidence. This improves evidence availability but changes instrumentation; a later reduction in unknown artifacts must not be attributed solely to the model or language.

Both later adapters recognize explicit model output limits without treating them as normal completion or allowing a nudge. The original GLM parser misclassified four clean length stops; additive SHA-bound overrides preserve its raw receipts while correcting analysis classification. Allowance is checked through the existing subscription route; no paid fallback, quota reset or model substitution is part of collection.

Opus required explicit instrumentation successors. The v3 cohort at `results/opus-medium-matrix-v3` inherits five consumed cells and assigns only the remaining 23 cells to the latest binding. Original consumed cells retain their originating qualification and epoch: four under the original instrumentation, then one under serialized admission v2. No consumed cell was retried. Recursive lineage archives preserve the predecessors and every source/qualification commitment.

Three consumed Opus cells were infrastructure incidents: cells 3 and 4 under the original binding, and cell 5 under v2. The original boundary failures' causes remain unknown. A concurrency problem was reproduced locally, but that does not prove it caused those historical failures. Cell 5 recorded a path rejection before upstream forwarding; the actual rejected path is unknown. The later handling of the pinned CLI's known auxiliary count-token path is based on inspected CLI source, not proof that this was cell 5's request. The report preserves these distinctions.

The sixth qualification separates 14 proven-unsent quota-preflight checks from three native model requests. This demonstrates provider allowance pressure and harness interaction even in a successful qualification. Invocation wall time can include CLI backoff, repeated preflight waiting and transport delays. It must not be called pure coding CPU time or model thinking time. Recorded HTTP preflight duration excludes retry backoff; subtracting it does not recover a clean model-only time metric. Unknown timing components remain unknown.

Native accounting also differs:

- Codex exposes completed response IDs and fresh-thread cumulative counters. Reconciliation deduplicates responses and checks cumulative totals across continuation prefixes. Counts are observed completed responses, not independently observed wire request starts. Input includes cached input; output includes reasoning. These subsets are not added twice.
- Claude records native Messages requests and response identities. Uncached input, cache reads, cache creation and output are disjoint addends. Reasoning is included in output but has no separately measured token count. Duplicate/conflicting/missing identities and incomplete streams prevent complete totals; partial component lower bounds remain labeled.
- Kimi/GLM used their qualified native Chat Completions records. Their first report already distinguishes inclusive totals from cache/reasoning subsets and incomplete coverage.

Different tokenizers, cache policies, repeated context and CLI orchestration make cross-model token totals unsuitable as a common compute or price scale. Within-model language/condition contrasts are the primary token comparison. An unsent Claude preflight record is not evidence that coding started. A quota-stop snapshot of a starter can retain a raw failed grade without becoming a language semantic failure or a fast low-token attempt. Started-but-ungraded attempts also remain unknown, not successful.

## Interpretation

The first 56 attempts produced 40 correct artifacts, but only 24 normal correct completions. Sixteen were correct deadline snapshots. That distinction matters: last source change, passing public tests and a later correct private grade do not establish an earlier measured time-to-correctness. Validation and helper repair after an implementation edit still consume model effort.

The [language/condition effort audit](subscription-language-effort-audit.md) documents compiler repairs alongside self-authored helper failures in static and dynamic languages. The [semantic-failure audit](subscription-semantic-failure-audit.md) documents missed cross-operation invariants: the same failed history can occur across languages, and many failed seeded histories can reflect one shared mechanism. Neither audit was fed back into candidate sessions.

The [Opus trace audit](opus-language-effort-audit.md) and [Sol trace audit](sol-language-effort-audit.md) distinguish compiler/import repairs, verification-helper corrections, formatting and build-artifact mistakes in Ruby, Rust and Haskell. They explain measured activity without treating every command or source change as a failed implementation.

This remains one ledger maintenance instance with two repetitions per cell. Frontier-level difficulty is unqualified, language labels are not a single ordered typing scale, and implementations do not necessarily exercise their strongest available guarantees. Supplied-test effects are descriptive; these data cannot establish universal test equivalence or monotonic typing benefits. Follow-up cohorts also run later with different native agents and retention behavior. Report those limits alongside any observed differences rather than merging them into a causal language ranking.

No manual candidate source edits were supplied by operators in these cohorts. The follow-up reports record no reactivation nudges; Opus operational intervention preserved incidents and changed instrumentation for pending cells, without repairing or retrying consumed candidates. AI/operator qualification, incident diagnosis and analysis are separate work. Human repair hours remain unknown, even where no human edit was observed. Historic Astra smoke and queue reference/runtime experiments are outside these coding-cohort totals.

## What this experiment establishes

In the first 56 attempts, supplied tests accompanied 24 correct artifacts versus 16 without supplied tests. This is descriptive evidence for those Kimi/GLM configurations on this instance, including deadline snapshots and unequal missing-outcome counts. In the follow-ups, both tested and untested eligible attempts passed, leaving no correctness separation to measure. That ceiling cannot establish test equivalence, a monotonic typing advantage, or saturation of increasingly strong type guarantees.

The requested difficult-task ambition remains unqualified: the ledger exercises interacting invariants, but these two follow-up configurations solved every eligible attempt. More independent instances and calibrated difficulty would be needed for broader claims. The present evidence is useful for observed language/condition effort and failure mechanisms, while preserving the distinction between semantic failure, interrupted instrumentation and provider overhead. Human repair hours and total AI-operated setup/diagnostic effort remain unknown. No hidden evaluator feedback or post-hoc candidate repair was used.
