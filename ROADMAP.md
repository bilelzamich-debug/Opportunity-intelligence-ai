# Roadmap

Ten phases (P0–P9). Each ends with an exit gate that must pass before the next
begins. Phase boundaries come from PKP v1 §9; blocking markers from PKP v2 §14.

---

## Overview

| Phase | Name | Tasks | Status | Blocking markers |
|---|---|---|---|---|
| **P0** | Specification | 37 decisions | ✅ **CLOSED** | — |
| **P1** | Foundation | 44 | ✅ **CLOSED** 2026-08-04 | — |
| **P2** | Research Engine | 10 | 🟡 **IN PROGRESS** | role-supplied assessments (N-24 ratified 2026-08-19; D-1 resolved) |
| **P3** | Fact Extraction | ~15 | ⬜ | M-19, M-11, M-20 |
| **P4** | Problem Intelligence | ~12 | ⬜ | M-12, M-21, M-22, M-06 |
| **P5** | Pattern Intelligence | ~14 | ⬜ | M-23, M-24, M-25, M-13 |
| **P6** | Opportunity Intelligence | ~18 | ⬜ | C-01, M-14, M-26, M-27 |
| **P7** | Solution & Validation | ~25 | ⬜ | C-05, M-30, M-32, M-33, M-28, M-31, M-53 |
| **P8** | Feedback | 20 | ⬜ | **C-02**, M-47, M-02, M-43, M-70, M-04 |
| **P9** | Hardening | ~10 | ⬜ | M-55, M-56, M-57 |

PKP v2 §14 recorded every phase as **Blocked** at the outset. P0 and P1 have
since cleared their blockers; P2's are partially cleared.

---

## P0 — Specification ✅ CLOSED

**Delivered.** 37 ratified decisions, the decision register, the canonical
marker crosswalk, the six-field decision template, the ratification annotation
layer.

**Key outcomes.** AD-01/AD-03 were found in **direct conflict** — the learning
loop undermined the evidence-first guarantee. Resolved by **R-8** (behavioural
closure) and **AD-05** (Ground Truth Protection, four exhaustive permitted
forms).

**Lesson that shaped everything after.** The crosswalk exposed **ten** marker
collisions, not the eight previously catalogued. Found only by exhaustive
extraction. *Validate by extraction, not by recollection.*

---

## P1 — Foundation ✅ CLOSED 2026-08-04

**Goal.** Build the least changeable layer: Knowledge Store, Knowledge Graph,
object acceptance path, baseline Orchestration.

**Delivered.** 44/44 tasks · 134/134 acceptance criteria · 18/18
Definition-of-Done criteria · 3,142 unit + 116 stress tests · 99.02% coverage ·
405 architecture checks.

| Wave | Focus |
|---|---|
| W1 | Identity, universal attributes |
| W2 | Relationship taxonomy, lineage, atomic write |
| W3 | Versioning, config store, failure store |
| W4 | Acceptance path, V1–V12, semantic hook |
| W5 | Lifecycle, graph index, confidence |
| W6 | Baseline Orchestration |
| W7 | Nine object types |
| W8 | Exit gate |

**Twenty-one production defects** found and fixed. The exit gate ran **three
times** — the first two halted on defects that all prior validation missed.

---

## P2 — Research Engine 🟡 IN PROGRESS (acquisition gated on role-supplied assessments)

**Goal.** Acquire external source material as Evidence with complete
provenance. The platform's only external-world acquisition boundary.

**Ratified 2026-08-04:** N-20 (source model) · N-21 (acquisition rights) ·
N-22 (coverage) · N-23 (research trigger).
**2026-08-19:** D-1 resolved (N-23 §5.5(i)) · `T02.1.3` closed · N-24 ratified.

| Task | Status |
|---|---|
| `T02.1.1` Source model | 🟡 AC1 ✅ (populated from N-20 §5.1, 2026-08-19) AC2 ✅ **AC3 ❌** (M-02/M-43) |
| `T02.1.2` Licensing enforcement | ✅ **CLOSED 2026-08-19** (oip/rights.py; 27/27; 14/14) — operational when assessments arrive |
| `T02.1.3` Independence grouping | ✅ **CLOSED 2026-08-19** (explicit-input model) |
| `T02.1.4` Coverage model | ✅ **CLOSED 2026-08-19** (oip/coverage.py; 33/33; 14/14) |
| `T02.2.1` Acquisition | ✅ **CLOSED 2026-08-19** (oip/acquisition.py; 25/25; 15/15) |
| `T02.2.2` Duplicate detection | ✅ **CLOSED 2026-08-19** (oip/duplicates.py; 25/25; 12/12) |
| `T02.2.3` Drift detection | ✅ **CLOSED 2026-08-20** (oip/drift.py; 26/26; 13/13) |
| `T02.2.4` Directive intake | ✅ **CLOSED 2026-08-20** (oip/directives.py; 30/30; 14/14) |
| `T02.2.5` Failure recording | ✅ **CLOSED 2026-08-20** (N-10 projection + attempted; 23/23; 12/12) |
| `T02.3.1` P2 exit gate | 🟢 **Executable** (all F02.1/F02.2 tasks CLOSED) |

**Exit requires the platform to have actually acquired something** — currently
impossible until the N-24 role is staffed and supplies assessments
(ratification alone admits nothing).

---

## P3 — Fact Extraction ⬜

**Goal.** Convert Evidence into canonical, individually verifiable claims. The
platform's integrity floor.

**Gated behind `T02.3.1`.** Entry task `T03.1.1`.

| Marker | Gap |
|---|---|
| M-19 | What qualifies as a fact; extraction granularity |
| M-11 | Fact identity and deduplication *(closed by R-5)* |
| M-20 / M-67 | Extraction fidelity — hallucination detection *(partially closed by S-5)* |

> **M-67 is the highest-severity gap in the object model:** a hallucinated fact
> satisfies every structural rule while being false. S-5 closes it only
> partially — sampling means some hallucinations reach production.

---

## P4 — Problem Intelligence ⬜

**Goal.** Infer unmet needs from Facts, solution-independently.

| Marker | Gap |
|---|---|
| M-12 | Severity / frequency scales |
| M-21 | Problem taxonomy |
| M-22 | Problem identity and deduplication |
| M-06 | Evidence sufficiency *(closed by S-4)* |

---

## P5 — Pattern Intelligence ⬜

**Goal.** Detect structure across Problems without manufacturing it.

| Marker | Gap |
|---|---|
| M-23 | Source diversity accounting *(closed by N-16)* |
| M-24 / M-25 | Per-type pattern thresholds; pattern type taxonomy |
| M-13 | Pattern temporal validity |

**Sampling artefact is this stage's defining risk** — PKP v2 calls it the
platform's most dangerous systemic failure: confident, well-evidenced, entirely
false views of the market. `PT-V4` (`source_diversity`) and `PT-V5`
(`artefact_assessment`) are mandatory for this reason.

> **Known blocker:** IOM §3.4 defines `source_diversity` as a count of
> *sources*; S-2 input 2 defines it as *types*. Unresolved — blocks a clean
> PT-V4 implementation.

---

## P6 — Opportunity Intelligence ⬜

**Goal.** Formulate and score opportunities.

| Marker | Gap |
|---|---|
| **C-01** | Contradiction in opportunity definition |
| M-14 | Scoring dimensions and weights |
| M-26 | Definition of "opportunity" |
| M-27 | *(scoring-adjacent)* |

**Human gate G1** sits at stage 5 → 6.

---

## P7 — Solution & Validation ⬜

**Goal.** Formulate solutions with explicit assumptions, then test them.

| Marker | Gap |
|---|---|
| **C-05** | Validation / Experiment Registry boundary |
| M-30 | *(solution formulation)* |
| M-32 | **Validation methodology — no method vocabulary exists** |
| M-33 | Validation outcome states |
| M-28 / M-31 | Solution selection owner; post-validation promote/reject owner |
| M-53 | Experiment Registry phase assignment *(closed by N-19)* |

**Human gate G2** sits at stage 7 → handoff. Platform output **exits here**
(N-1).

---

## P8 — Feedback ⬜ — the most constrained phase

**Goal.** Close the learning loop behaviourally.

| Marker | Gap |
|---|---|
| **C-02** | **Execution Record has no producing engine** |
| M-47 | How outcomes are obtained, verified, attributed |
| **M-02 / M-43** | Learning target vocabulary; Feedback write target |
| **M-70** | Feedback loop instability guard |
| M-04 | Success criteria *(closed by N-3)* |
| M-10 / M-34 | Learning cadence; update reversion |

**Human gate G3** sits at stage 9.

> PKP v2 §14: *"P8 Feedback — Blocked — most constrained phase."*
> Principle 5 and AD-03 remain the least-realised parts of the platform.

---

## P9 — Hardening ⬜

| Marker | Gap |
|---|---|
| M-55 | Security, access control, tenancy |
| M-56 | Cost model |
| M-57 | Observability requirements |

**N-5 reserved the tenancy discriminator** with a named trigger: the first of a
second tenant, licensing-driven visibility restrictions (**M-18** — now
partially closed by N-21), or output exposure beyond the commissioning
organisation. On any trigger, `T09.2.2` activates.

---

## Critical Path

```
D-1 resolution ──▶ T02.2.4 ──▶ T07.3.8, T08.3.4  (22 downstream tasks)

Rights authority ──▶ T02.1.2 ──▶ T02.2.1 ──▶ T02.2.2 ──▶ T02.2.3 ──┐
                                          └─▶ T02.2.5 ─────────────┤
                     T02.1.3 ──▶ T02.1.4 ─────────────────────────┤
                                                                   ▼
                                                              T02.3.1
                                                                   │
                                                                   ▼
                                                              T03.1.1 ──▶ P3…P9
```

**The longest blocking chain is D-1.** Everything downstream of the P2 exit
gate — all of P3 through P9 — waits on Phase 2 completing, which waits on the
rights authority being named.

---

## Estimating Honestly

No dates are given, deliberately. Phase 2 has consumed substantial effort and
produced four ratified decisions but **zero acquired Evidence**, because the
work was blocked on decisions rather than on implementation.

The pattern is likely to repeat: each engine phase carries 3–6 open markers,
and each must be closed by ratified decision before implementation may begin.
**Specification throughput, not coding throughput, is the constraint.**
