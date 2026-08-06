# Architecture Decision Timeline

**Status:** Governance artefact. Chronological narrative of how the architecture reached its current state.
**Established by:** F00.4 (directed)
**Scope:** Every major decision — what triggered it, what was decided, what changed afterwards.

---

## How To Read This

The decision register says *what* was decided. The dependency map says *how decisions relate*. This document says **why each decision appeared when it did, and what became possible afterwards.**

It exists because architectural reasoning decays fastest. A future contributor reading a decision in isolation sees a conclusion; reading it in sequence, they see the pressure that produced it. When a decision looks arbitrary, the trigger usually explains it.

Each entry records: **Trigger → Decision → What Changed**.

---

## Era 0 — Inheritance (pre-project)

The platform began as PKP v1: a foundation document defining a vision, five principles, a ten-stage pipeline, nine engines, three shared components, eight Intelligence Objects, and a nine-phase roadmap.

**It recorded four architecture decisions as bare titles.** No context, no alternatives, no rationale, no consequences. That omission — later marked M-50 — is where this timeline effectively begins, because it meant nobody could tell which constraints were deliberate.

### AD-01 · AD-02 · AD-03 · AD-04 — the inherited four
`RECONSTRUCTED` · documented 2026-08-02

| | |
|---|---|
| **Trigger** | v1 named four decisions with no supporting record. Future contributors could not distinguish a considered constraint from an unexamined default. |
| **Decision** | Reconstruct all four — Evidence-First, Intelligence Contracts, Feedback Loop, Separation of Concerns — with substance traceable to PKP v2 §8 and rationale explicitly labelled as inferred. |
| **What changed** | The architecture acquired stated reasons. AD-01 became recognisable as the platform's strongest constraint; AD-03 as its least supported. Critically, **AD-01 and AD-03 were found to be in direct conflict** — the loop implementing continuous learning undermined the evidence-first guarantee. That conflict drove everything in Era 3. |

> **Honest note.** The alternatives in these four records are *reconstructed*, not recovered. They are labelled as such and must never be cited as evidence of what was historically debated.

---

## Era 1 — Diagnosis

Before anything could be built, the architecture had to be understood. Three analytical passes produced 82 open items across contradictions, missing definitions and open questions.

**Key finding:** v1 was **structurally sound and radically under-specified**. Across all analysis, no finding indicated the pipeline, engine decomposition, or object model was *wrong*. Every gap was an omission, not an error — a far better position than the reverse.

**The most consequential diagnosis:** the object model was named as the platform's contract surface (AD-02) but had no defined contents. A contract surface with no contract. This became the single highest-priority item.

---

## Era 2 — Governance First

### T00.1.1–T00.1.3 — the register, the crosswalk, the template
2026-08-02

| | |
|---|---|
| **Trigger** | M-50: no decision records existed. Any ratification would have been unauditable, and the standing rule "markers are closed only by recorded decision" had no mechanism behind it. |
| **Decision** | Establish the decision register, a mandatory six-field record template, and a canonical marker crosswalk. |
| **What changed** | Decisions became recordable. The crosswalk exposed something unexpected: **ten marker-identifier collisions, not the eight previously catalogued.** Two — configuration home and opportunity selection — would have caused ratifications to close entirely the wrong gaps. |

> **Lesson that shaped later work.** The two extra collisions were found only by exhaustively extracting every marker reference rather than trusting a prior summary. That method — validate by extraction, not by recollection — was applied to every subsequent feature and repeatedly caught real defects.

---

## Era 3 — Resolving the Founding Conflict

The pivotal era. AD-01 versus AD-03 had to be settled before anything could be built on either.

### R-1 … R-6 — the object model becomes real
`RATIFIED` · closes M-08, M-45, M-15, M-46, M-11, M-40

| | |
|---|---|
| **Trigger** | The object model had no attributes, no lifecycle, no versioning, no confidence semantics, no identity rules, no relationship vocabulary. Six foundational gaps, each blocking P1. |
| **Decision** | Objects immutable and versioned (R-1); seven-state lifecycle (R-2); two-component confidence with a monotonic ceiling (R-3); explicit temporal validity without automatic decay (R-4); Facts as canonical claims with multiple attachments (R-5); a closed ten-type relationship taxonomy (R-6). |
| **What changed** | AD-02 moved from **aspirational to realised** — the contract surface acquired contents. Two decisions proved load-bearing beyond their apparent scope: R-3's ceiling rule became the platform's structural defence against confidence inflation, and R-5's canonical claims became the only mechanism making corroboration countable. |

### R-7 — the ninth object
`RATIFIED` 🔺 · closes C-03

| | |
|---|---|
| **Trigger** | Eight of nine stage-engine pairs produced a persisted object. Feedback produced none, so learning changed platform behaviour with no record — breaching Principle 3 by design. |
| **Decision** | Specify the Feedback Record as a ninth Intelligence Object, extending v1's eight. |
| **What changed** | Learning became traceable and reversible. **This was the first change to v1's structure**, escalated rather than absorbed. The argument that carried it: the addition was required by v1's *own* principles, not by new requirements — v1 mandated traceable reversible learning and omitted the artefact that provides it. |

### R-8 + AD-05 — ground truth protected
`RATIFIED` 🔺 · closes C-04

| | |
|---|---|
| **Trigger** | v1's pipeline arrow `Feedback -> Evidence` asserted that platform-derived content becomes platform-grounding content. Evidence is *defined* by having no upstream lineage. Both could not hold — the architecture's single decision-level conflict. |
| **Decision** | **R-8:** the loop closes *behaviourally* — feedback informs engine behaviour and may trigger new research; it never becomes Evidence. **AD-05:** generalise this into a standing principle prohibiting *any* platform-generated artifact from becoming Evidence, with four exhaustive permitted forms. |
| **What changed** | The lineage graph became provably acyclic, making cascade invalidation and traversal termination possible. AD-01's grounding guarantee became unconditional. **The founding conflict was resolved in favour of the stronger constraint.** |

> **Why AD-05 was added beyond R-8.** R-8 closed the one path v1 drew. AD-05 closed the *class* — a Pattern re-ingested as a source, a Validation finding written back as an observation. A rule naming one instance invites the others.

> **What neither decision solved.** Both close the *lineage* path to self-reinforcement. The *behavioural* path — learning narrows research, which narrows findings — remains open (M-70). Recorded in both records so neither is misread as having solved loop instability.

---

## Era 4 — Drawing the Boundary

### N-1 … N-5 — what the platform is not
`RATIFIED` · closes M-03, M-05, M-04, OQ-01, OQ-02, OQ-05

| | |
|---|---|
| **Trigger** | v1 had no non-goals statement and did not identify who consumes output or where it exits. Scope was unbounded by construction, and C-02 (the Execution stage with no engine) could not be located. |
| **Decision** | The platform is **advisory**, output exits at Stage 7 (N-1). Human judgement at exactly three gates (N-2). Success measures defined now, outcome measures **frozen** (N-3). Reproducible inputs, non-deterministic outputs (N-4). Tenancy discriminator reserved with a named trigger (N-5). |
| **What changed** | C-02 was located: execution happens **outside** the platform, so no Execution Engine is needed. Nine exclusions (X1–X9) were registered, each with the scope-creep pressure to expect — converting future expansion attempts from feature requests into recognisable scope changes. |

> **The subtlest choice here was N-3's freeze.** Outcome measures were defined before any outcome exists, specifically so they cannot later be shaped to match whatever the platform happens to produce. A platform that defines success after seeing its results cannot fail.

---

## Era 5 — The Foundation Layer

### N-6 — the critical path
`RATIFIED` · closes C-06, M-39

| | |
|---|---|
| **Trigger** | Knowledge Store and Knowledge Graph both plausibly held objects and relationships, with no stated division (C-06) and no consistency model (M-39). This blocked five further decisions and determined the platform's least changeable layer. |
| **Decision** | Objects are authoritative for their own lineage; the graph is a derived, rebuildable index. Object write atomic, index update asynchronous and idempotent. |
| **What changed** | Divergence became a **performance** problem rather than a **correctness** one — the graph can never be the reason the platform is wrong, only the reason it is slow. Article V (objects self-describing) became enforceable. Five downstream decisions unblocked. |

### N-8 · N-9 · N-10 — integrity machinery
`RATIFIED` · closes M-64, M-58, M-09, M-36

| | |
|---|---|
| **Trigger** | Validation rules had no enforcer (M-64), cascade invalidation had no owner (M-58), and engine failure had no representation (M-36) — meaning an empty result was indistinguishable from a failed one. |
| **Decision** | The Store enforces acceptance, with rules specified in the object model (N-8). Cascade is a mechanical operation invoked by Orchestration, propagating a decision made at the source (N-9). Failures are recorded outside the object model (N-10). |
| **What changed** | Integrity guarantees became enforceable rather than aspirational. **N-8 also recorded an honest limit:** structural enforcement cannot catch a hallucinated Fact — one satisfies every structural rule while being false. That limit is what makes measured error rates necessary rather than optional. |

### N-11 · N-12 · N-15 — operating properties
`RATIFIED` · closes OQ-13, M-38, OQ-12

| | |
|---|---|
| **Trigger** | Concurrency was undefined (OQ-13), growth was monotonic and unbounded (M-38), and Evidence storage mode was undecided (OQ-12). |
| **Decision** | Parallel acquisition, serialised interpretation (N-11). Lineage skeleton permanent, content tiered by reachability (N-12). Evidence stored in full where licensing permits, by reference otherwise (N-15). |
| **What changed** | Pattern Intelligence gained a stable population per batch. Principle 3 was preserved structurally while bounding the dominant storage cost. Reference-only Evidence carries a **recorded** source-drift exposure rather than a hidden one. |

### N-7 + CI-1 — configuration finds a home
`RATIFIED` 🔺 · closes M-63

| | |
|---|---|
| **Trigger** | Every object carries `engine_configuration_ref`, mandated by Principle 3 and made load-bearing by N-4. Nothing existed for it to reference (M-63). |
| **Decision** | A configuration store as a **scoped extension** of the Knowledge Store — the smaller of two deviations, the alternative being a fourth shared component. Approved subject to **invariant CI-1**. |
| **What changed** | Provenance became reconstructable. CI-1 established that **configuration is infrastructure state, not intelligence**: logically isolated, never participating in reasoning, scoring, pattern detection, or lineage. The approval condition became a binding invariant, elevated into Article V of the Constitution. |

> **Why CI-1 matters more than it appears.** Colocating configuration with knowledge is an operational convenience that creates a real hazard: settings drifting into reasoning. CI-1 makes the boundary explicit and enforceable at the access layer rather than by convention.

---

## Era 6 — Constitutional Consolidation

### Platform Constitution
2026-08-02 (directed)

| | |
|---|---|
| **Trigger** | Twenty-one ratified decisions had accumulated across specification documents. The invariant principles — those expected to hold for the platform's lifetime — were entangled with implementation detail that will change repeatedly. |
| **Decision** | Extract eleven articles into a supreme constitutional document containing no schemas, no engines, no phases. Amendment requires a recorded decision naming the article changed. |
| **What changed** | The platform gained a stable reference point. Specifications became explicitly subordinate and revisable without touching the Constitution. Article XI fixed precedence: Constitution → decision records → IOM → PKP → Backlog. |

---

## Patterns Across the Timeline

Five things recur, and each is worth carrying forward.

**1. Every structural change was forced by v1's own principles.** The ninth object, behavioural loop closure, ground truth protection — none originated from new requirements. Each resolved an internal inconsistency where v1 mandated an outcome and omitted the mechanism.

**2. Escalations were never self-approved.** Four decisions extended v1's frozen architecture (R-7, R-8, N-7, and the pending C-02 resolution). Each was prepared with alternatives and held for explicit sign-off.

**3. Validation by extraction repeatedly beat validation by recollection.** The marker crosswalk found two collisions beyond a prior summary; the dependency map found 19 asymmetries in hand-authored edges; the backlog graph found a forward dependency that would have deadlocked P1. Every one surfaced only through mechanical checking.

**4. Honest limits were recorded rather than smoothed over.** N-8 states that structural enforcement cannot catch hallucinated Facts. R-8 and AD-05 state that they do not solve behavioural self-reinforcement. N-15 states that reference-only Evidence may become unverifiable. Each is a known weakness rather than a discovered one.

**5. The smaller deviation was preferred consistently.** A ninth object rather than relaxing Evidence's definition; a scoped Store extension rather than a fourth component; outcome intake assigned to an existing engine rather than a tenth. In each case the alternative was recorded so the choice remains reviewable.

---

## Current Position

**Resolved:** the founding AD-01/AD-03 conflict; the object model contract surface; the platform's scope boundary; the knowledge foundation layer.

**Outstanding, highest severity first:**

| Marker | Gap | Scheduled |
|---|---|---|
| **M-67** | Hallucinated Facts pass every structural rule | S-5 (F00.5) |
| **M-70** | Behavioural loop instability unguarded | P8 |
| **M-60** | Cross-engine confidence calibration — R-3's ceiling is arithmetically valid but semantically unsound without it | S-1 (F00.5) |
| **M-62** | Semantic equivalence for Fact merging — R-5's correctness depends on it | S-3 (F00.5) |
| **C-02** | Execution Record has no producing engine | `T08.1.1` 🔺 |
| **C-01** | Scoring has no owning engine | `T06.2.5` |

The next feature (F00.5) addresses three of the six.
