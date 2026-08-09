# Reports

Completion reports, closure certificates, defect analyses and architectural
investigations.

---

## Files

| File | Type | Verdict |
|---|---|---|
| [`PHASE-1-CLOSURE-REPORT.md`](PHASE-1-CLOSURE-REPORT.md) | Phase gate | ✅ **PHASE 1 CLOSED** |
| [`T01.8.1-DEFECT-cascade-bfs-ordering.md`](T01.8.1-DEFECT-cascade-bfs-ordering.md) | Defect analysis | **RESOLVED** — fixpoint iteration |
| [`T02.1.1-ARCHITECTURE-CHALLENGE.md`](T02.1.1-ARCHITECTURE-CHALLENGE.md) | Adversarial review | **Blocked confirmed** — M-16 genuinely open |
| [`T02.1.1-DERIVABILITY-INVESTIGATION.md`](T02.1.1-DERIVABILITY-INVESTIGATION.md) | Formal proof | **Underdetermined** — ≥3 valid taxonomies |

Per-task validation logs and specifications live in
[`../../platform/validation/`](../../platform/validation/).

---

## Phase 1 Closure

**44/44 tasks · 134/134 acceptance criteria · 18/18 Definition-of-Done.**

| Gate | Result |
|---|---|
| Full suite | 3,142 passed, 0 failed |
| Stress | 116 passed |
| Closure verifier | 60/60 |
| Exit gate | 94/94 |
| Task gate | 26/26 |
| Architecture verifiers | 405/405 |
| Coverage | 99.02%, no module below 95% |
| Mutation | 19/20 killed, survivor proven equivalent |
| Performance | 0 regressions (best-of-3, idle host) |

---

## The Cascade Defect — Why It Matters

The most instructive artefact in this repository.

**Found by the third run of the Phase 1 exit gate**, after two prior gates and
3,136 passing tests had missed it.

**The bug.** `_collect()` ordered dependents breadth-first — by *shortest
path*. In a DAG that is **not** a topological order. A node with upstreams at
distance 1 and 5 was evaluated at distance 2, before its deep upstream was
condemned. That upstream still read as "attesting", so the node was spared.

**The impact.** An object could remain `ACTIVE` after **every** upstream
reference was withdrawn — the exact silent corruption I6 exists to prevent.

**Why the tests missed it.** All five partial-retraction tests used
uniform-depth lineage, where BFS coincides with topological order. No test
anywhere constructed a stage-spanning lineage edge. Both gate verifiers passed
because they asserted the rule's *presence and shape*, never its *behaviour*
under a non-uniform graph.

**Why it was reachable.** Six of eight derived types enforce a single upstream
type. `Validation` correctly does not — IOM §3.7 says it "DERIVES_FROM the
object containing the tested claim", and IOM types `DERIVES_FROM` as
`any → any`. A Validation accepted through `store.write_validation()`, passing
V1–V12, I1–I8 and V-V1…V-V6, reproduced the defect.

**The fix.** Fixpoint iteration, not topological ordering — because `plan()`'s
breadth-first order is a *documented, tested public contract*, and re-ordering
would have required weakening a test. Eligibility now resolves to a fixpoint,
making the outcome independent of traversal order.

**Lessons that changed the method:**

1. Structural checks ("the rule exists") are not behavioural checks ("the rule
   works on hostile input").
2. Uniform test fixtures hide order-dependent bugs. Vary the shape.
3. Adversarial probing must precede test-writing, not follow it.
4. A gate that has passed twice can still be wrong.

---

## The T02.1.1 Investigations

Two documents recording why Phase 2 stalled — and how the conclusion was
tested rather than assumed.

**`T02.1.1-ARCHITECTURE-CHALLENGE.md`** — an explicit attempt to *disprove* the
blocker. Seven attacks mounted (hidden decision, indirect derivation,
implementation artefact, precedent, crosswalk, frozen IOM wording, backlog
wording). All seven failed. It also found three ratified statements that make
the blocker *stronger*, and corrected two errors in the author's own earlier
reports.

**`T02.1.1-DERIVABILITY-INVESTIGATION.md`** — the formal proof. Every ratified
constraint mentioning source types uses them only to *count* or *partition*, so
any `(M, c)` with `|M| ≥ 1` satisfies all of them. Three pairwise
non-isomorphic witnesses exhibited; no ratified statement discriminates among
them. **Therefore the architecture does not determine the taxonomy.**

The proof is why N-20's eight members are recorded as **AS-0: a selected
choice, not a derivation.**

---

## The Standard Report Formats

**Task completion (11 sections):** Completed Task · Acceptance Criteria ·
Tests · Coverage · Performance · Defects Found and Fixed · Architecture
Impact · Remaining Blockers · Honest Limitations · Next Critical-Path Task ·
Stop.

**Phase exit gate (11 sections):** Phase Completion Status · Verification of
Every Completed Task · Validation Results · Coverage · Performance · Mutation
Testing · Architectural Consistency · Specification Blockers · Technical Debt
Review · Defects Found During the Gate · Closure Decision.

Both formats require an **Honest Limitations** section naming the weakest point
in the work. That is not politeness — it is Constitution Article X applied to
the project's own reporting.
