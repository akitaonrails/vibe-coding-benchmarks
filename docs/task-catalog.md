# Difficult task catalog

These are task designs to implement and calibrate, not existing benchmark fixtures. The reference project's ordinary Raft/storage/language tasks saturated; see [research findings](research-findings.md). Aim for difficulty from interacting requirements, with a clear oracle and a bounded implementation surface.

Build two independently authored instances per family initially, rather than twelve cosmetic renamings. Develop smaller sibling tasks for qualification, using different semantics/seeds from scored instances. A full test includes a contract, correct reference, portable starter, public suite, private oracle, semantic mutants and grading resource limits.

## Portable task interface

Provide a persistent JSONL process and language-specific adapter. A request identifies a component operation, not an arbitrary function invocation. Transport is supplied and prevalidated, so agents spend effort on the domain. Stateful tasks may return explicit effects (`persist`, `send`, `schedule`), which a trusted simulator interprets. Simulators expose documented public operations for agent experiments but not hidden seed inventories or reference answers.

The submission must implement the core in the assigned language. Reference implementations and grader source remain outside its environment. Define integer overflow, Unicode, deterministic order, errors, cancellation and persistence precisely. A JSON boundary loses some native API/IDE advantages: therefore include internal multi-module APIs in the migration task and report this portability tradeoff.

## F1. Crash-consistent transactional page store

**Starting point:** a working block-device adapter and simple validated record format. The implementation task adds atomic multi-key batches, snapshots and reclamation. A separate repair instance starts from a realistic store with a coherent recovery flaw.

**Contract:** once commit acknowledgement is emitted, its batch survives every permitted crash. An interrupted unacknowledged transaction may be entirely present or absent as specified, never partially visible. Older snapshots survive reclamation; stale handles cannot expose reused pages. Define flush durability, write ordering, torn-write granularity, checksum semantics, full-device errors and recovery behavior. For bounded fault schedules, the simulator decides which writes persist.

**Hard interaction:** power failure during checkpoint publication, followed by page reuse and recovery of a live snapshot. Add format migration and a later failure during rollback in the harder sibling. Ordinary put/get functionality alone cannot satisfy this.

**Concrete adversary:** commit A; open snapshot S; update A in transaction B; checkpoint; begin reclaiming old pages; crash after a permitted write prefix; restart; read current state and S. A system that restores current values but invalidates S fails a separate invariant.

**Oracle:** small abstract transaction history plus independently implemented permitted durable-state enumeration. Exhaust all cut points on small traces; generate longer traces with independent seeds. Record acknowledged-data loss, atomicity, snapshot and recovery-progress results separately. Require capacity progress so “never reclaim” cannot pass.

**Public suite:** basic transactions plus at least one case in each fault category. **Hidden suite:** combinations of faults, varying device sizes, long reuse cycles and boundary histories. **Mutants:** acknowledge before durability, reclaim snapshot-live page, accept torn record, replay partial batch, silently format on recovery error.

**Why types might matter:** distinguish committed/uncommitted handles and page identities. **Why tests might matter:** type-correct ordering can still lose acknowledged data. Inspired by [littlefs's fault model](https://github.com/littlefs-project/littlefs); not a requirement to implement its disk format.

## F2. Replicated log repair with snapshots and membership change

**Starting point:** a readable event-driven replicated state machine with one family of deliberately introduced but realistic bugs. Repair scope spans persistence, term transitions and snapshot handling. Another instance implements a specified missing membership transition from a correct baseline.

**Contract:** public safety rules, exactly defined request deduplication, state-machine ordering and reads. If based on [Raft](https://raft.github.io/raft.pdf), state the selected algorithm and joint-consensus rule precisely. Liveness is required only after a stated stable-majority period with bounded delivery and ticks; do not demand progress under arbitrary permanent partitions.

**Hard interaction:** a node restarts with a compacted log while a delayed response from an old term arrives during membership change. Client retries race with leader replacement. Local type correctness cannot establish global linearizability.

**Concrete adversary:** isolate old leader; commit under a new leader; compact; restart a follower; deliver an earlier append response and replay a client request. Verify no stale read, duplicate applied effect or unsafe quorum commitment.

**Oracle:** deterministic scheduler, persisted-state simulator, bounded linearizability/history checker and progress obligations. A history checker that times out produces evaluator-indeterminate, not candidate failure; simplify/minimize the trace before adjudication. Validate against known safety mutants and hand-derived histories.

**Public suite:** normal leadership, retry, restart and basic snapshot/membership cases. **Hidden suite:** reordering/duplication, cross-term snapshots and configuration boundaries. **Mutants:** stale-term acknowledgement counted, old quorum used, deduplication lost on snapshot, read served without requisite authority.

**Balance:** primarily algorithmic invariants; naturally dynamic implementations remain competitive. Use a bounded simulator so Python/Ruby do not lose solely to thread scheduling or raw throughput.

## F3. Verified-behavior optimizer for a small SSA-like IR

**Starting point:** a working parser, interpreter and unoptimized execution engine supplied in every language. Implement or repair optimization passes without changing observable behavior. Internal pass interfaces are real modules, not one giant function.

**Contract:** explicit fixed-width arithmetic, wrap behavior, division traps, branch conditions, phi semantics, memory aliasing and externally observable effects. Begin with integers to avoid underspecified floating-point behavior. Optimizations must preserve results and traps on the defined input domain.

**Hard interaction:** dominance-based facts become invalid across a join, an aliasing write invalidates load elimination, and arithmetic rewrites alter trapping behavior. Optimization order and budget constraints interact.

**Concrete adversary:** a division occurs only on one branch; a simplification hoists it ahead of a guard and introduces division by zero on the previously safe branch. Another case invalidates a cached load through an alias.

**Oracle:** differential execution against a small independently validated interpreter; exhaustive small-width cases, bounded symbolic checks where feasible, seeded program generation and hand-authored adversarial programs. These checks establish bounded evidence, not universal equivalence. [Alive2](https://github.com/AliveToolkit/alive2) supplies a methodological example, not a dependency the candidate may invoke to solve the task wholesale.

**Success has two axes:** semantic correctness and useful optimization. A no-op implementation can pass correctness but fails the stated optimization target. Define improvement as reduced IR execution work on a held-out workload, not faster host-language execution. Initial proposed target: at least 10% geometric-mean work reduction, no workload worse than the frozen regression allowance, with a bounded optimization-work budget. Calibrate before freezing.

**Public suite:** each instruction's semantics, sample traps and simple optimization cases. **Hidden suite:** interactions, skewed workloads and adversarial control flow. **Mutants:** unsafe hoist, overflow-invalid rewrite, wrong phi predecessor, missed alias kill.

**Typing relevance:** rich AST/IR types may prevent malformed rewrites; semantics still require behavioral evidence. Avoid requiring a complete production compiler in seven languages.

## F4. Multi-module protocol migration with compatibility and authorization

**Starting point:** an equivalent functioning service/library in each language. Version 1 uses string identifiers and a single success/error representation across persistence, request handling, cache and background processing. Implement a version 2 contract while retaining explicitly defined version 1 wire behavior.

**Contract:** tagged identifiers with tenant scope; separate absent/pending/failed states; documented schema evolution and deterministic serialization. Old stored records must migrate and new records round-trip. Public specification defines authorization checks and exact error classes. Starter interfaces communicate equivalent information across languages, with prose contracts supplied in dynamic ports.

**Hard interaction:** the typed internal API changes across many modules while legacy records, cancellation and cache keys still encode the old assumptions. A cross-tenant ID collision must never retrieve another tenant's value. A field absent in old data must not silently become an explicit null in the new protocol.

**Concrete adversary:** identical local IDs in two tenants, old cached record, interrupted migration and retry through the background worker. Exercise serialization and authorization together, not only individual DTO constructors.

**Oracle:** old/new wire conformance, schema round trips, small state-machine histories, negative authorization cases and compatibility regression suite. Mutation inventory includes a swap of same-shaped IDs that ordinary structural checking may miss.

**Public suite:** useful existing baseline tests plus v2 examples in T1; T0 receives the same documented behavior without that suite. **Hidden suite:** old/new producer-consumer pairs, collision/cancellation histories and repeated migrations.

**Why include it:** this should give static typing a fair chance to excel at propagation of API changes. If a suite comprised only distributed algorithms showed little type benefit, the result would generalize poorly to ordinary maintenance.

## F5. Incremental dependency engine with retraction and recursive strata

**Starting point:** a working batch evaluator of a small specified rule language. Add incremental updates and retractions with indexed joins, stratified negation, duplicates and deterministic results. A repair sibling begins with a flawed incremental implementation.

**Contract:** set or multiset semantics explicitly chosen, fixed-point semantics, supported recursion, cycle rejection where required, negation strata and precise update boundaries. Results after every update equal the batch semantics. Publish algorithmic operation budgets as part of the task.

**Hard interaction:** a deletion invalidates multiple derivations of the same fact; recursive support must disappear only when no valid derivation remains. Cached negative queries must update when new positives arrive. Add skewed key distributions so full recomputation cannot satisfy the efficiency contract.

**Concrete adversary:** two independent paths derive a fact; delete one path, then introduce a negating fact and remove it again. Verify reference counts, recursive closure and restored output after each step.

**Oracle:** independent slow fixed-point evaluator on small domains, generated incremental histories and a separately validated operation counter for large workloads. Counter instrumentation must cover submitted work so the candidate cannot move costs into uncounted helpers. If that cannot be secured, use same-language runtime normalization and treat performance as secondary.

**Public suite:** recursion, retraction and negation individually. **Hidden suite:** their combinations, high fanout, repeated churn and duplicate sources. **Mutants:** decrement-once assumption, stale negation cache, cycle leak, duplicate inflation.

**Balance:** rich data modeling helps organize the implementation, but the central challenge is preserving semantic invariants and selecting an algorithm.

## F6. Streaming resource protocol under cancellation and backpressure

**Starting point:** an unfamiliar but fully documented local transport API and simple frame codec. Implement a multiplexed session state machine with fragmented frames, bounded queues, cancellation and resumption. A second instance changes resource-lifetime rules in a correct existing implementation.

**Contract:** deterministic event API for reads, writes, cancel, timeout and close; every acquired buffer/lease released exactly once; no send after close; per-stream ordering; bounded queued bytes; specified duplicate delivery and retry behavior. Define whether accepted messages must be delivered or may be cancelled. Use trusted logical resources, not the host garbage collector, for leak accounting.

**Hard interaction:** cancellation occurs after reservation but before completion, while close races with a fragmented control frame and queue pressure. Error handling must preserve other streams and avoid deadlock.

**Concrete adversary:** reserve credit, partially transmit a frame, cancel its stream, receive a duplicate completion, then close the connection. Check no double release, negative credit, lost unrelated message or permanent backpressure.

**Oracle:** event-state reference model, logical lease inventory, bounded exhaustive schedules and long generated traces. Liveness is judged only under explicit fair delivery assumptions. Real asynchronous implementations can be added later as an ecological extension; the initial deterministic state-machine version cannot establish native data-race performance.

**Public suite:** each event and basic fragmentation/cancellation. **Hidden suite:** interleavings and resource exhaustion. **Mutants:** release twice, forget cancellation release, accept frame after close, block all streams behind one cancelled stream.

**Why types might matter:** ownership/state representations can encode valid transitions and resource use. **Why tests might matter:** the compiler generally does not know the custom transport's fairness and message-delivery obligations.

## Calibration and anti-bias rules

Use a difficulty ladder within each family: a compact semantic problem, interacting constraints, and an integrated long task. Retain easier controls to detect a floor in Luna performance; preserve hard tasks to avoid an Astra ceiling. Proposed development acceptance targets are a mixture of pass/fail outcomes across the strongest configuration and nonzero diagnostic progress from lighter configurations, not a prescribed model ranking.

If everything passes, add an independently justified constraint or use a harder sibling. If everything fails, first verify specification clarity, port equivalence, resources and oracle correctness. Do not tune scored instances after observing scored outcomes. Difficulty calibration uses distinct development instances and documents selection decisions.

Record an experienced non-author human's task time on a subset. Author implementation time is a cost estimate, not a human baseline. Human and model pilots need the same public contract, available tools and test-support condition.

For an optional evolution track, apply three planned changes to the candidate's own prior artifact. Grade every checkpoint and retention of earlier contracts. Separately run independent later checkpoints from a correct common baseline; never repair a failed foundation invisibly and present it as an uninterrupted success.
