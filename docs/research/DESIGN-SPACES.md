# Design Spaces and Rejected Alternatives

Every design space explored in this project, with all alternatives considered
and the exact constraint each rejected option violated.

Preserved because **"a decision without rejected alternatives is a
preference"** (`DECISION-TEMPLATE.md`), and because M-50 — v1 recording four
decisions as bare titles — is the project's founding defect.

---

## 1. M-16 — Source Taxonomy (→ N-20)

**Question.** What is the closed member set for `source_type`?

| Option | Description | Verdict |
|---|---|---|
| **A** | Taxonomy by **subject domain** (`retail`, `finance`, …) | ❌ Fails S-2 P3 — two sources in one domain may be wholly independent channels, so domain-counting does not measure sampling artefact. Domains are open-ended, breaching C17 closure |
| **B** | Taxonomy by **acquisition channel** | ✅ **SELECTED** — directly serves P3; sampling artefact is a *channel* phenomenon. Small, stable, orthogonal to independence and licensing |
| **C** | Taxonomy by **legal/licensing regime** | ❌ **Architecturally illegal.** Violates C10 (N-15 makes storage licence-driven and *separate* from type). Collapses M-16 into M-18, which crosswalk #4 forbids |
| **D** | Free text with a registry of observed values | ❌ Not a *closed* taxonomy (AC1); fails C17. A typo registers as new diversity — the exact failure P3 exists to prevent |

**Selection rationale.** Option B supplies exactly what C5, C7, C8 and C9
already presuppose, so **no ratified record needs amendment**. A and D would
require revisiting S-2's purpose; C would require superseding N-15.

> **AS-0:** the eight members themselves are **selected, not derived**. The
> corpus enumerates zero source types.

---

## 2. M-16 — Trust Model (→ N-20 §5.3)

**Question.** How is source trust represented, and does it score?

| Option | Verdict |
|---|---|
| Trust as an input to `evidential_support` | ❌ **Contradicted by S-2**: five inputs, *"No other input."* Would require superseding S-2 |
| Trust recorded, non-scoring, versioned registry | ✅ **SELECTED** — changes no scoring, so S-2 is untouched |
| Trust with a neutral default for unrated sources | ❌ IOM calls equal weighting *"a strong unstated assumption"* — a described **flaw**, not a policy. Materialising it would encode the defect |
| Trust omitted entirely | ❌ OQ-28 is subsumed into M-16; omitting leaves the marker unclosed |

**Consequence accepted.** Trust becomes *visible* but not *operative*. Weak and
strong sources remain equal to the scoring function. M-16's core complaint is
mitigated, not eliminated.

---

## 3. M-18 — Acquisition Rights (→ N-21)

**Question.** Who decides admissibility, and where is it enforced?

| Option | Verdict |
|---|---|
| **A** Conservative allow-list — only explicitly licensed sources | ❌ Maximum safety, severe coverage loss. B-34: *"worsening coverage (M-17) and sampling bias risk"* |
| **B** Per-source assessment recorded, **not** enforced | ❌ **Fails K4** — N-15 states enforcement *determines mode at acquisition*. Leaves ineligible material in an immutable store (K11), unremovable (I4) |
| **C** Per-source assessment **with enforcement before acquisition** | ✅ **SELECTED** — satisfies K1–K5, respects N-08's mechanism/policy split, produces failure records under N-10 |
| **D** Enforcement at the Store's acceptance gate | ❌ **Fails K6 twice**: licence admissibility is not *structural*, and embedding it makes the Store "a policy owner", which N-08 explicitly rejects. Also too late — acquisition already occurred |

**Selection rationale.** Option C supplies exactly what N-15 declares it
consumes. B would eventually force superseding N-15; D would force superseding
N-08.

---

## 4. M-17 — Coverage Model (→ N-22)

**Question.** What does "coverage" mean, and what does "complete" mean?

| Option | Verdict |
|---|---|
| **A** No coverage measure; rely on volume | ❌ **Fails J1** — N-3 already ratified "source-type coverage" as a stage-1 measure. Fails J10: gaps unrecorded |
| **B** Source-type coverage only | ❌ **Fails J10/J11** — an inaccessible source produces a silent hole; nothing declares it |
| **C** Population coverage against a market frame | ❌ **Fails J9** — AD-01 concedes the platform *"is blind to what it has not collected"*. A population frame asserts knowledge of the unseen universe. Also requires an owner role that F8 forbids creating |
| **D** Source-type coverage **plus explicit gap declaration** | ✅ **SELECTED** — satisfies J1, J6, J7, J10, J11, J12 without touching S-4 or the engine set |

**Consequence accepted.** B-35, verbatim: *"Declared gaps do not fix bias; they
only make it visible. That is nonetheless the difference between a known
limitation and a silent falsehood."*

---

## 5. M-01 — Research Trigger (→ N-23)

**Question.** What initiates acquisition, and with what scope?

| Option | Verdict |
|---|---|
| **A** Continuous autonomous discovery | ❌ Violates G6 (Research *"does NOT decide what to research"*) and G1/G3 (N-17 ratifies bounded scheduled cycles) |
| **B** Event-driven — acquisition reacts to platform state | ❌ **Fails G1/G2 explicitly** — N-17: *"Directive, not reactive… does not watch for objects appearing"* |
| **C** Externally specified work sets, no directive artefact | ❌ Fails G8/G9 — v2 §10 names "Research directive" as a required artefact; AD-05 gives it a home. Leaves feedback's Research Trigger form with no destination, breaching G10 exhaustiveness |
| **D** Research directive as a **first-class recorded artefact** | ✅ **SELECTED** — supplies the origin v2 names as missing; AD-05 already assigns its home |

---

## 6. Gate Ordering (→ N-20 §5.2.1) — **selected, not derived**

**Question.** In what order are the three pre-acquisition gates evaluated?

The corpus fixes **no** order. Three gates admit **3! = 6** permutations, each
combinable with `{halt-first, collect-all}` → **≥12 legal models**.

| Option | Verdict |
|---|---|
| Halt-at-first, order Scope → Typability → Rights | ✅ **SELECTED** (AS-1, AS-2) |
| Halt-at-first, any of 5 other permutations | ⚠️ Equally legal |
| **Evaluate all gates, record a set of reasons** | ⚠️ **Matches the ratified N-08/N-10 precedent exactly** and needs no ordering at all |

**Honest note.** The selected option **inverts** the platform's one existing
multi-check convention: the acceptance path evaluates every rule and records
all failures (`FailureRecord.failed_rules` is a tuple). Recorded as **AS-2**.

---

## 7. Cascade Repair (→ T01.8.1 fix)

**Question.** How to make partial-retraction eligibility order-independent?

| Option | Verdict |
|---|---|
| **(a)** Topological ordering over the induced subgraph | ❌ Would change `plan()`'s breadth-first order — a **documented, tested public contract** (`test_plan_is_breadth_first_then_lexicographic`). Would force weakening a test |
| **(b)** Iterate eligibility to a **fixpoint** | ✅ **SELECTED** — leaves `_collect()`/`plan()` byte-identical; makes correctness independent of traversal order entirely |

**Termination proof.** Every pass but the last adds ≥1 object to `doomed`;
`doomed` is bounded by the finite dependent set.

---

## 8. M-16 Decomposition (ARB)

| Option | Verdict |
|---|---|
| Keep M-16 atomic | ❌ Two halves have **different evidentiary status** — taxonomy underdetermined, trust representation determinable |
| Split into M-16a / M-16b | ✅ Recommended — correctness improvement |

**Honest finding.** Tested counterfactually: splitting frees **only 2 of 94
blocked tasks**. *"The split is a correctness improvement, not a throughput
one, and should not be sold as unblocking Phase 2."*

---

## 9. M-18 Decomposition (→ M-18 / M-18b)

| Concern | Variable | In N-21? |
|---|---|---|
| Legality · licensing · terms of use · retention rights | **Rights** — may this be taken and kept? | ✅ Yes |
| Robots · rate limits | **Conduct** — how may the system be accessed? | ❌ No — **M-18b** |

**Evidence for the boundary.** N-15 pairs licensing with retention (*"some
sources permit acquisition but not retention"*); **no** ratified text ever
pairs robots or rate limits with retention. The rights half blocks **91 tasks**;
the conduct half blocks **zero**.

---

## 10. Rejected Across the Corpus

| Rejected | Where | Why |
|---|---|---|
| Mutable objects in place | IOM D-01 | Destroys the historical record Principle 3 requires |
| Binary valid/invalid status | IOM D-02 | Cannot distinguish rejection from invalidation from retraction |
| Per-object-type support functions | S-2 Option B | Destroys comparability, which the ceiling rule requires |
| Engine-asserted support | S-2 Option C | Abandons comparability; collapses R-3's two components |
| Orchestration owns cascade | N-9 Option A | Implies Orchestration judges validity |
| Graph performs cascade | N-9 Option B | Under N-6 the graph cannot author status changes |
| Each engine invalidates its own outputs | N-9 Option C | Requires engine-to-engine coupling Article V forbids |
| Store defines its own rules | N-8 Option | Makes the Store a policy owner; it would drift toward interpretation |
| Full content always | N-15 Option A | May breach source licensing; largest storage cost |
| Reference only | N-15 Option B | Grounding depends on external systems remaining available |
| Feedback as Evidence | IOM D-07 | This is C-04 — grants internally-generated content grounding status |
| No feedback object | IOM D-07 | Leaves Principle 3 violated by design |
