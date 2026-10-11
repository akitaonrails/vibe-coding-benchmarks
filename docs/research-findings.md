# Research findings

References to `~/Projects/llm-coding-benchmark` identify a separate read-only local checkout, not files distributed with this repository.

As of 2026-10-10. This is a targeted research review, not a systematic literature review or a claim that no other relevant studies exist. Separate published findings, local observations and proposed experimental choices.

## What the existing evidence supports

| Evidence | Finding supported by the source | Limit for our question |
|---|---|---|
| [Berger et al., On the Impact of Programming Languages on Code Quality (2019)](https://arxiv.org/abs/1901.10220) | Reanalysis of an influential GitHub study identified methodological problems; only four language associations remained statistically significant, with very small effects. | Observational human-authored repositories cannot identify the causal effect of static typing on modern AI coding. This also does not prove types have no benefit. |
| [Mayer et al., usability of undocumented software (2012)](https://pleiad.cl/papers/2012/mayerAl-oopsla2012.pdf) | In a study of 27 people across five tasks, static typing helped development time on three tasks and dynamic typing on two. | Human subjects, particular APIs and tasks; useful motivation for task interactions, not an AI effect estimate. |
| [Mündler et al., Type-Constrained Code Generation with Language Models (PLDI 2025)](https://arxiv.org/abs/2504.09246) | Their type-constrained decoding method, extended to TypeScript, reduced compilation errors by more than half and improved functional correctness on HumanEval/MBPP synthesis, translation and repair evaluations. | This changes decoding, not just language or normal compiler feedback. Short benchmark tasks and different models cannot settle long-running Codex token efficiency. Treat it as evidence for a plausible mechanism, not proof of the broad claim. |
| [MultiPL-E (2022)](https://arxiv.org/abs/2208.08227) | Provides a framework translating code-generation benchmarks into many languages and studies language frequency/features. | Useful precedent for comparable contracts, but short translated tasks and language familiarity confound claims about type systems. We need harder, multi-file changes and semantic equivalence review. |
| [SWE-PolyBench (2025)](https://arxiv.org/abs/2504.08703) | Supplies multilingual repository-level tasks and execution-based evaluation of coding agents. | Different repositories and issues per language measure ecosystem performance, not the same problem under different typing conditions. |
| [METR, Measuring AI Ability to Complete Long Software Tasks (2025)](https://arxiv.org/abs/2503.14499) | Uses human task duration to describe the difficulty of tasks agents can complete at a specified reliability. | Human task duration is different from agent elapsed time. We should collect difficulty anchors, without fitting sweeping time-horizon claims from a tiny suite. |

[Flint et al.’s type-annotation replication package](https://zenodo.org/records/15036757) is a relevant additional lead. Its landing page and fetched README establish a reproducibility package using Python/TypeScript and LeetCode/HumanEval-X analyses, but do not establish a result direction. No numerical claim from that study is used here; inspect its paper and full methodology before using it as evidence.

**Current conclusion:** there are credible reasons for static checks to help, and credible reasons for their net benefit to vary. The reviewed evidence does not establish the requested monotonic relationship between richer type systems and fewer tokens in long agentic coding. The diminishing-returns hypothesis remains open.

## Correct the categories before measuring them

“Strong,” “weak,” “static,” “dynamic,” “sound,” and “expressive” are different properties. Python and Ruby belong in the dynamic group; that does not mean their runtime type discipline is weak. C# and Kotlin should not be labeled weakly typed merely to place them between Haskell and Python.

- [C# documentation](https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/types/) describes a strongly typed language. Our C# condition is a mainstream static configuration with explicitly recorded nullable checking and warning policy.
- [Kotlin null safety](https://kotlinlang.org/docs/null-safety.html) prevents some null errors statically while documenting escape paths, including `!!` and interoperability. Record the configuration and actual escapes used.
- [TypeScript compatibility documentation](https://www.typescriptlang.org/docs/handbook/type-compatibility.html) explicitly discusses intentional unsoundness. `strict` improves checking but does not make TypeScript a sound proof system.
- [Python typing documentation](https://docs.python.org/3/library/typing.html) states that annotations are not enforced by the runtime. Annotation availability and static-checker feedback can therefore be varied separately.
- [Haskell 2010 declarations and bindings](https://www.haskell.org/onlinereport/haskell2010/haskellch4.html) specifies its type/declaration system; GHC configuration and extensions must still be pinned in the actual experiment.
- [Rust ownership documentation](https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html) explains compile-time ownership checking without a garbage collector. Comparing Rust and Python changes ownership, runtime, syntax and ecosystem as well as static typing.

These are reasons to publish language-specific contrasts and feature descriptions. A regression against an invented integer “type strength” would provide false precision.

## Mechanisms worth distinguishing

1. **Information:** signatures and algebraic data types communicate constraints before a tool runs.
2. **Detection:** a checker rejects violations before behavioral tests exercise them.
3. **Repair guidance:** diagnostics localize a problem and suggest a next action.
4. **Representation:** encoding states/types can prevent whole classes of invalid programs, while also increasing implementation and migration work.
5. **Verification complementarity:** tests expose behavior not captured in types; types cover cases not exercised by finite tests.
6. **Workflow friction:** build latency, long diagnostics, unfamiliar syntax and repeated checker repairs can consume tokens or cause premature stopping.

The first four could improve efficiency; the last can offset it. Compiler failures alone are not an outcome measure: a language detecting more defects might report more errors while shipping fewer.

## Difficulty evidence from the reference project

Read-only sources inspected:

- v4.1 overview (reference checkout: `~/Projects/llm-coding-benchmark/benchmark-v4.1/README.md`).
- Frontier comparison (reference checkout: `~/Projects/llm-coding-benchmark/docs/success_report.v4_1.frontier_comparison.md`) and gap analysis (reference checkout: `~/Projects/llm-coding-benchmark/benchmark-v4.1/frontier/gap_analysis.md`).
- v5 design (reference checkout: `~/Projects/llm-coding-benchmark/benchmark-v5/DESIGN.md`).
- Codex integration notes (reference checkout: `~/Projects/llm-coding-benchmark/docs/codex-integration.md`), runner implementation (reference checkout: `~/Projects/llm-coding-benchmark/scripts/benchmark/runner.py`), and native subscription adapter (reference checkout: `~/Projects/llm-coding-benchmark/scripts/frontier_native.py`).

The v4.1 overview reports that Genesys, Astra and Fable all scored 100 on its original replicated store, transactional engine and typed-language tasks. Its harder extension reports filesystem scores around 41/27/99, Lean checker scores 0/98/98, and optimization scores 0/0/26 respectively. These are heterogeneous, single-attempt scores with different native harnesses, not language-treatment evidence. This review inspected summaries and adapter code; it did not regrade the underlying submissions.

The practical lesson is substantial: merely asking for “Raft,” “a database,” or “a compiler” does not guarantee useful frontier discrimination. Difficulty must come from verified combinations of failure recovery, semantic obligations and performance constraints. A zero optimization reward can mean insufficient improvement, not incorrect code; a proof-checker zero can mean a serious soundness violation. Preserve those distinctions.

The v5 proposal already separates generic continuation from stronger reminders, requires protected evaluators, and warns against counting thousands of correlated checks as independent samples. We reuse those design ideas, with a stricter rule that hidden grading never determines when the main nudge policy sends a message.

## Sources for proposed hard tasks

- [littlefs](https://github.com/littlefs-project/littlefs) provides a concrete example of power-loss resilience, bounded storage operations and flash constraints. Our portable storage task borrows the fault-model idea, not an assertion of littlefs compatibility.
- [Raft paper](https://raft.github.io/raft.pdf) provides public safety and membership-change semantics. A task must state its precise supported subset and network assumptions.
- [Alive2](https://github.com/AliveToolkit/alive2) illustrates checking compiler transformations against semantics. Our proposed optimizer operates on a small specified IR, with independently checked bounded cases; it is not a replacement for LLVM or a claim of full formal verification.

These projects establish useful task and oracle patterns. They do not establish that our proposed tasks are already calibrated to Astra/Fable difficulty.
