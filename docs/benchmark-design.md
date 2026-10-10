# Experimental design

Status: proposed protocol, 2026-10-10. Freeze after development pilots and before scored runs. See [research](research-findings.md) for evidence and [analysis](measurement-and-analysis.md) for decision rules.

## Questions and falsifiable hypotheses

The unit of comparison is a **language configuration × model/effort configuration × test-support condition × task instance × independent attempt**, under a fixed Codex harness and assistance policy.

| Hypothesis | Observable prediction | Evidence against it |
|---|---|---|
| H1: static feedback improves efficiency | Within-language checker feedback increases verified success at equal budgets, or reduces effort at comparable success. | No meaningful benefit with sufficiently narrow uncertainty, or a consistent net cost after correctness is held accountable. |
| H2: stronger checking has diminishing returns | In explicitly ordered checking configurations, the first increment helps more than a later increment on the prespecified workload. | Later increments yield equal/larger practical benefits, particularly with tests present. |
| H3: good tests can substitute for much static checking | Dynamic/no-checker + supplied tests is noninferior to checked + supplied tests in verified correctness, without materially worse effort or critical failures. | Checked + tests has a practically meaningful advantage, or dynamic code has more critical violations. |
| H4: types and tests are complementary | The checker benefit is larger with supplied tests, or the combination dominates either alone. | Benefit shrinks with tests or combination imposes cost without a practical gain. |
| H5: some failures are cheap to reactivate | Generic nudges recover a measurable share of initial failures with little additional work. | Recovery is rare or needs large continuation budgets; technical hints are necessary. |

These hypotheses need not have one global answer. Type-sensitive API evolution and crash-recovery semantics may behave differently. Report contradictory findings instead of forcing a unified ranking.

## Track A: practical language comparison

Select seven languages. The descriptions are strata for coverage, not an ordinal score.

| Language | Proposed configuration | Contribution and confounds |
|---|---|---|
| Rust | Stable pinned toolchain, safe Rust submission, ordinary ownership/borrow checking; lint policy fixed | Ownership and rich data modeling; compile and borrow-repair burden. Native execution differs from managed languages. |
| Haskell | Pinned GHC, documented language edition/extensions; fixed warning profile, no deferred type errors | Inference, algebraic types and purity; laziness, package familiarity and runtime behavior also change. |
| C# | Pinned .NET/C# versions, nullable reference analysis enabled and enforced | Mainstream nominal static typing, managed runtime, strong tooling. |
| Kotlin | Pinned JVM/Kotlin versions, fixed compiler warning policy | Nullability, sealed models and mainstream static checking; JVM build/startup costs. |
| TypeScript | Pinned Node/TypeScript, `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`; trusted final checker | Structural/gradual typing, erased types; safety escapes and JavaScript semantics. |
| Python | Pinned CPython; no external type checker in the dynamic baseline | Dynamic implementation with short feedback cycles; optional typing studied separately. |
| Ruby | Pinned CRuby; no RBS/Steep/Sorbet in baseline | Second dynamic language reduces dependence on Python-specific model familiarity. |

Start the pilot with Rust, Haskell, TypeScript and Python. Expansion must include Ruby, C# and Kotlin before making a claim about these wider strata. Toolchain versions are resolved and frozen during implementation, not guessed now.

Use idiomatic code and comparable modular boundaries, not line-for-line translations. Provide equally working build/launch scaffolds, pinned dependencies and the same behavioral contract. No model gets a prewritten domain solution. Independent port review should confirm that one language's starter types do not reveal algorithms that others must invent.

Record actual usage of `any`, casts, unchecked assertions, null assertions, partial functions, panics, reflection and runtime validation. Do not ban every escape in the practical track: that would measure an artificial style. Prohibit disabled required checks, changed protected configuration, alternate-language implementations and outsourcing the core algorithm to a ready-made solver. Rust `unsafe` is excluded from this initial safe-code workload, explicitly limiting generalization.

The main result answers “which configured language works best here?” It cannot attribute Rust–Python differences solely to types or infer how all languages behave.

## Track B: identify mechanisms within one runtime

Use two distinct ablations; do not mix their estimates.

**B1: annotation information versus checker feedback.** For TypeScript, compare the following modes on paired starts:

| Mode | Domain annotations available | Checker feedback during work | Execution |
|---|---|---|---|
| B1-0 | No; equivalent constraints in prose | No | JavaScript on the same Node runtime |
| B1-1 | Yes | No | TypeScript erased by a pinned transpiler |
| B1-2 | Identical initial annotations to B1-1 | Yes | Same transpiler/runtime as B1-1 |

B1-1 versus B1-2 is the strongest direct test of feedback, conditional on the same starter representation. B1-0 versus B1-1 measures an annotation/representation package, not a perfect isolated information effect. Prompt lengths are recorded, not artificially padded. Keep runtime defaults and emitted semantics matched, including class-field behavior. Exclude or precompile constructs whose runtime semantics differ across transpilers.

Repeat in Python: unannotated/no checker, annotated/no checker, annotated/pinned checker. No-checker arms cannot invoke a checker through an alternate tool. Annotation syntax is allowed in the primary dynamic practical track, but controlled B1-0 explicitly removes it. The typed Python annotations/checker settings must be identical in B1-1/B1-2 at the start.

For **feedback causality**, hidden runtime correctness is the common endpoint, with final type-check status a separate outcome in every arm. Do not require type-check success only for B1-2 and then call a lower success rate evidence that feedback hurts. A second deployability endpoint may require both runtime and static conformity for all applicable annotated arms.

**B2: checking intensity.** In TypeScript, compare identical annotated starters under (a) checking without strict null checks, (b) `strict`, (c) `strict` plus unchecked-index and exact-optional checks. Confirm the flag ladder is genuinely nested on the pinned version. Unlike B1, all three get checker feedback. This supports a local diminishing-returns test; there is no defensible extrapolation from this ladder to “Haskell is stronger than Rust.” An optional representation study contrasts primitive IDs with validated domain wrappers/typestate in one language, but labels its additional starter design information and migration burden explicitly.

Cross each selected mechanism contrast with test support. Stage B1/B2 separately to avoid an unmanageable full factorial. These experiments require separate implementations and validation; they are not implicit extra runs in Track A.

## Test-support conditions

| Condition | Agent-visible support | What the contrast means |
|---|---|---|
| T0: no supplied behavioral suite | Public prose specification, identical I/O examples, working launcher and transport smoke check; no domain assertion suite | Ability to implement and choose its own verification from the contract |
| T1: supplied unit suite | Everything in T0 plus a useful immutable suite covering specified behavior; agent can add tests | Benefit of external executable behavioral support |

Both allow the agent to compile, execute, debug and write its own tests. Hidden evaluators exist in both, never exposed during coding. T0 is **not** “no tests exist” or “no verification.” Record self-authored tests and time spent creating them as outcomes/mediators; do not adjust them away in the primary causal analysis.

Use the same language-neutral test driver and fixture semantics across languages, over the provided component protocol. Tests target small semantic units and short state transitions, not only end-to-end applications. A secondary realistic track may use native test frameworks; report its additional ecosystem effects separately.

The primary T0/T1 effect is the value of an already available suite. Record human/model effort to author, review and maintain that suite separately, and publish a lifecycle sensitivity analysis amortizing it over 1, 10 and 100 task uses. Charge comparable preparation costs for rich starter types and domain wrappers. Otherwise “tests are nearly as good” could hide substantial up-front work. Agent-authored tests are always charged to the current run.

Every T1 test maps to a requirement already written in T0. T1 inevitably supplies extra executable examples—that is part of the intervention, not something to hide. To isolate oracle execution from reading examples, a small optional three-arm study can give the same test text with execution disabled. It is not necessary for the main practical question.

A “proper suite” is validated before use: one known-bad implementation for every critical public invariant must fail; positive cases reject reject-everything implementations; domain-specific semantic mutants assess breadth. Freeze mutation targets and suite runtime, report surviving non-equivalent mutants and avoid equating line coverage with adequacy. Public tests cover every requirement class, while hidden tests combine boundaries, longer histories and independent seeds. Do not construct a deliberately weak suite to manufacture a type advantage.

Optional **T2** adds a public property/state-machine testing framework with independent generators; optional **T−** disallows candidate execution and behavioral testing until submission while retaining necessary compilation. T− needs an audited restricted tool interface, is artificial and is not a fair “zero feedback” condition for static versus dynamic languages. Keep it out of the headline results.

## Models and effort

Primary configurations, subject to account qualification:

| Label | Requested identifier | Effort |
|---|---|---|
| Strong configuration | `gpt-6-astra` | low |
| Middle configuration | `gpt-6-sol` | medium |
| Light configuration | `gpt-6-luna` | high |

Official model pages describe these model IDs and their supported API efforts: [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra), [Sol](https://developers.openai.com/api/docs/models/gpt-6-sol), [Luna](https://developers.openai.com/api/docs/models/gpt-6-luna). API documentation does not confirm this subscription's access. Local qualification must verify actual resolved model and effort; do not silently substitute `gpt-6.1-sol` for Sol.

These labels describe proposed deployment configurations, not measured ordering. On a prespecified subset, add Astra medium and Luna medium, reusing Sol medium cells for a common-effort comparison. A common setting does not imply equal inference compute. An optional Astra high calibration subset distinguishes hard tasks from an unusually low effort ceiling. Fable motivates task difficulty, but is not required in the primary Codex-only model matrix.

Disable model delegation, cross-run memory, external skills, plugins and automatic specialist reviewers in the scored agent environment. Keep the Codex version, agent instructions, tool inventory, context settings, output truncation and allowed local documentation fixed. Record unavoidable model-specific built-in behavior. Diagnose whether the shared harness disadvantages a model rather than assuming perfect neutrality.

## Fairness and generalization

- Use common numeric, encoding, ordering, time and error semantics; specify them rather than inherit language defaults. Transport large integers as decimal strings and bytes as encoded byte sequences. Define null versus missing, map ordering and Unicode handling.
- Simulate crash and concurrent event schedules for the core comparison, so thread libraries and operating-system timing do not determine correctness. Real threads/native I/O belong in a separately reported ecological extension.
- Permit algorithmically equivalent idioms and standard data structures; prohibit external implementations of the tested algorithm. Publish exact allowed dependencies and local documentation for each language.
- Isolate compilation and execution resource costs, but include both in end-to-end agent time. Separately measure runtime performance relative to a correct same-language baseline; never award correctness credit for raw native-language speed.
- Use clean per-run workspaces, identical starting cache policy and deterministic evaluator seeds. Pair conditions on task variants, randomize order within day blocks and record server/CLI changes.
- Language familiarity/training exposure cannot be measured reliably from popularity. Hold tasks constant, report per-language results and use within-language ablations; do not claim a statistical control removed hidden pretraining differences.
- Include implementation, repair and migration workloads. A build-only test could miss maintenance benefits; only compiler-friendly refactors could overstate them.
- All hidden assertions must follow public requirements. Hidden cases may be surprising; hidden obligations are invalid.
