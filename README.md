# Vibe Coding Benchmarks

An exploratory benchmark of AI coding correctness and effort across Rust, Haskell, C#, Kotlin, TypeScript, Python and Ruby, with and without supplied tests. A separate queue track compares Elixir, Rust, Rails and plain Ruby.

**Start here:** [setup and tutorial](docs/setup.md) · [results at a glance](docs/results-summary.md) · [documentation index](docs/README.md)

## Completed ledger experiment

112 attempts: seven languages × four model/agent configurations × two test conditions × two repetitions of one ledger task. Correct means passing all 43 private grading histories.

| Configuration | Normal correct | Correct at deadline | Failed artifact | No final grade |
|---|---:|---:|---:|---:|
| Kimi K3 high | 17 | 7 | 2 | 2 |
| OpenCode / GLM 5.3 high | 7 | 9 | 7 | 5 |
| Claude / Opus 5.5 medium | 25 | 0 | 3 infrastructure-interrupted | 0 |
| Codex / Sol medium | 28 | 0 | 0 | 0 |

**No general language ranking is established.** Opus and Sol passed every eligible attempt, so this task was insufficiently difficult to distinguish their correctness. Supplied tests accompanied more correct artifacts for Kimi/GLM. Tokens, missing data, provider delays and harness changes limit comparisons.

- [Full analysis](docs/followup-matrix-results.md), [language/test-condition effort tables](docs/followup-language-effort.md), and [Kimi/GLM results](docs/subscription-matrix-results.md)
- [Published per-attempt measurements](docs/data/matrix-results.json) and [evidence/reproduction limits](docs/data/README.md)
- [Experimental design](docs/benchmark-design.md), [difficulty audit](docs/difficulty-audit.md), and [task catalog](docs/task-catalog.md)

## Queue experiment

Eight 10,000-message reference trials created real backlog, but shared infrastructure and timeout effects prevented a sustainable-capacity ranking. Controlled AI coding effort for Elixir versus Rust/Rails has **not** been measured. The stronger pressure protocol is proposed, not executed.

Read [queue results](docs/scalability-load-validation.md), [pressure research](docs/queue-pressure-research.md), and [queue setup](docs/setup.md#queue-runtime-trials).

## Try it without a model account

From a checkout with Python 3.11+:

```sh
python3 -m langbench list
python3 -m langbench prepare ledger_engine ruby .work/ruby-t1 --tests T1
python3 scripts/export_public_results.py --summary docs/data/matrix-results.json
```

Preparation does not run a model. Grading needs the qualified Docker runtime; live collection additionally needs pinned CLIs and your own subscriptions. Follow the [tutorial](docs/setup.md) before launching a matrix. Raw local traces, credentials and Docker images are not included in this repository.
