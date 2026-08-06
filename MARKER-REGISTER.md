# Marker Register

Complete register of every marker — missing definitions, open questions and
contradictions — with current state, closing decision and remaining portion.

**A marker is closed only by a ratified decision record.** Closing a marker by
implementation choice is prohibited (Playbook **F3**).

Canonical authority: **PKP v2 §11** (contradictions), **§12** (open questions),
**§13** (missing definitions). Identifier resolution:
[`marker-crosswalk.md`](marker-crosswalk.md).

---

## 1. Summary

| Category | Total | Closed | Partially closed | Open |
|---|---|---|---|---|
| Missing definitions (`M-nn`) | 70 | 22 | 4 | 44 |
| Open questions (`OQ-nn`) | 24 | 8 | 0 | 16 |
| Contradictions (`C-nn`) | 8 | 4 | 1 | 3 |

---

## 2. Closed Markers

### Closed in Phase 0

| Marker | Gap | Closed by |
|---|---|---|
| M-03, M-05 | Non-goals; who consumes output | **N-1** |
| M-04 | Success criteria and measures | **N-3** |
| M-06 | Evidence sufficiency thresholds | **S-4** |
| M-07 | Explanation format | **N-13** |
| M-08 | Object mutability / versioning | **R-1** |
| M-09 | Retraction semantics | **N-9** |
| M-11 | Fact identity and deduplication | **R-5** |
| M-15 | Confidence model | **R-3** |
| M-23 | Source diversity and independence accounting | **N-16** |
| M-35, M-37 | Orchestration control model; loop termination | **N-17** |
| M-38 | Retention policy | **N-12** |
| M-39 | *(store/graph)* | **N-6** |
| M-40 | Relationship taxonomy | **R-6** |
| M-45 | Lifecycle and status states | **R-2** |
| M-46 | Temporal validity | **R-4** |
| M-53 | Experiment Registry phase assignment | **N-19** |
| M-58 | Cascade invalidation owner | **N-9** |
| M-59 | Evidential support computation | **S-2** |
| M-60 | Cross-engine confidence calibration | **S-1** |
| M-62 | Semantic equivalence for Fact merging | **S-3** |
| M-63 | Engine configuration home | **N-7** |
| M-64 | Acceptance authority | **N-8** |
| M-68 | Object model has no attributes | IOM §3 |
| **C-03** | Feedback is a stage and engine but not an object | **R-7** |
| **C-04** | Feedback → Evidence | **R-8** + **AD-05** |
| **C-06** | Store / Graph boundary | **N-6** |
| **C-08** | Orchestration has no roadmap phase | **N-18** |
| OQ-01 | Determinism | **N-4** |
| OQ-02, OQ-05 | Human involvement; learning update approval | **N-2** |
| OQ-04 | Rejected candidates persisted | **R-2** |
| OQ-12 | Evidence full vs reference | **N-15** |
| OQ-13 | Concurrency | **N-11** |
| OQ-15 | *(orchestration)* | **N-17** |
| OQ-18 | Cross-stage read access | **N-14** |

### Closed in Phase 2 (2026-08-04)

| Marker | Gap | Closed by |
|---|---|---|
| **OQ-28** | Source trust attribute | **N-20 §5.3** — fully closed |

---

## 3. Partially Closed Markers

Partial closure follows established precedent: S-5 `Closes | M-67 (partially)`;
R-8 `Closes | C-04 (jointly with AD-05)`.

| Marker | Closed portion | Remaining open portion | By |
|---|---|---|---|
| **M-16** | Source-type taxonomy (§5.1), per-type eligibility (§5.2), trust representation (§5.3) | **Trust scoring** — requires superseding S-2; **learnability** — M-02/M-43 | **N-20** |
| **M-17** | Coverage and completeness concepts (§5.1–§5.4, §5.6–§5.7) | **Stopping** — "when has it researched enough" → M-01 | **N-22** |
| **M-18** | Rights half: legality, licensing, terms of use, retention rights (§5.1–§5.7) | **M-18b** conduct half (robots, rate limits); v2 §14 "compliance" scope | **N-21** |
| **M-01** | Initiation, originators, trigger lifecycle, scoping, cancellation (§5.1–§5.8) | **Self-direction** (D-2); **target approval** (D-1) | **N-23** |
| **M-36** | Failure *representation* | **Policy** — retry / skip / halt / compensate | **N-10** |
| **M-67** | Sampled fidelity verification | Unsampled hallucinations still reach production | **S-5** |
| **C-04** | Lineage path to self-reinforcement | **Behavioural** path → M-70 | **R-8** + **AD-05** |

### Reserved identifier

**M-18b** — acquisition *conduct* (robots, rate limits). Split from M-18 on
ratification of N-21. **Zero backlog acceptance criteria depend on it.**

---

## 4. Open Markers

### P2 — Research

| Marker | Gap | Status |
|---|---|---|
| M-16 (scoring) | Whether trust weights `evidential_support` | Needs S-2 superseded |
| M-17 (stopping) | When research is enough | Follows M-01 |
| M-18b | Robots, rate limits | Unscheduled |
| M-01 (self-direction) | May Research propose its own targets | **No canonical ID** (D-2) |

### P3–P5 — Fact, Problem, Pattern

| Marker | Gap |
|---|---|
| M-19 | What qualifies as a fact; extraction granularity |
| M-20 | Extraction fidelity verification |
| M-12 | Problem attributes — severity, frequency, population scales |
| M-21 | Problem taxonomy |
| M-22 | Problem identity and deduplication |
| M-13 | Pattern temporal validity |
| M-24 | Pattern thresholds |
| M-25 | Pattern type taxonomy |
| M-66 | Lineage summarisation — deep sets may exceed human inspection |

### P6–P7 — Opportunity, Solution, Validation

| Marker | Gap |
|---|---|
| **C-01** | Contradiction in opportunity definition |
| **C-05** | Validation / Experiment Registry boundary |
| M-14 | Scoring dimensions and weights |
| M-26 | Definition of "opportunity" |
| M-27 | *(scoring-adjacent)* |
| M-28 | Owner of solution selection |
| M-29 | Solution granularity |
| M-30 | *(solution formulation)* |
| M-31 | Owner of post-validation promote/reject |
| M-32 | **Validation methodology — no method vocabulary** |
| M-33 | Validation outcome states |
| M-42 | Experiment lifecycle |
| M-69 | Constraint model |
| OQ-19 | Score point-in-time vs recomputed |
| OQ-21 | Pattern constituent versioning |
| OQ-34 | *(open)* |

### P8 — Feedback

| Marker | Gap |
|---|---|
| **C-02** | **Execution is a pipeline stage with an object but no engine** |
| M-02 | What the platform learns — the target of change |
| M-43 | Feedback Engine write target |
| M-47 | How outcomes are obtained, verified, attributed |
| M-10 | Learning cadence and trigger |
| M-34 | Learning update reversion mechanism |
| **M-70** | **Feedback loop instability guard** |
| OQ-24 | Feedback application mechanism |

### P9 / Cross-cutting

| Marker | Gap |
|---|---|
| M-55 | Security, access control, tenancy |
| M-56 | Cost model |
| M-57 | Observability requirements |
| M-61 | Staleness owner |
| M-65 | Re-derivation on supersession |
| OQ-10 | May pipeline stages be skipped? |
| OQ-11 | Is backflow permitted? |
| OQ-06 | Precedence rule when principles conflict |
| OQ-07 | May Pattern Intelligence read Facts directly? |

---

## 5. Twelve Forbidden Closures

Verified during Phase 1 as **NOT invented** — each remains open and is surfaced
in production code that fails closed:

| # | Gap | Marker |
|---|---|---|
| 1 | Severity / frequency scales | M-12 |
| 2 | Scoring dimensions | M-14 |
| 3 | Per-type pattern thresholds | M-24 / M-25 |
| 4 | Validation method vocabulary | M-32 |
| 5 | Verification standard | M-47 |
| 6 | Learning-target vocabulary | M-02 |
| 7 | Constraint model | M-69 |
| 8 | Gate ownership | M-31 |
| 9 | Problem deduplication | M-22 |
| 10 | Feedback application | OQ-24 |
| 11 | Instability guard | M-70 |
| 12 | Success measure | M-04 *(since closed by N-3)* |

---

## 6. Discovered Discrepancies

Not markers in the original registers — found during Phase 1 and 2 work.

| ID | Discrepancy | Status |
|---|---|---|
| **D-1** | `T02.2.4` AC2 requires "approval per human-gate decision"; N-2 fixes **exactly three gates**, none covering research targets. Under Article XI, N-2 governs and the AC is unsatisfiable as written | **BLOCKING** — awaiting Project Owner |
| **D-2** | B-59 attributes the self-direction question to OQ-07, but canonical OQ-07 is "May Pattern Intelligence read Facts directly?" The crosswalk records no collision — the question appears to have **no canonical identifier** | Open |
| **D-3** | IOM §3.1 annotates `access_conditions` with "OPEN QUESTION-13", but canonical OQ-13 is *concurrency*, closed by N-11. IOM cites concurrency separately as "OPEN QUESTION-23". A licensing-terms marker appears **mis-merged and falsely reported closed** | Recorded in annotations §10 |
| **D-4** | IOM §3.4 defines `source_diversity` as a count of *sources*; S-2 input 2 defines it as *types*. Under Article XI, S-2 governs its own input, but the Pattern attribute is unstated | Blocks clean PT-V4 |
| — | v2 §14 (X14) names the M-18 gap "Legal **and compliance**"; §13 omits compliance | Unresolved scope question |

---

## 7. Markers Surfaced in Production Code

Every open marker that affects behaviour is cited in the code that fails closed
because of it:

M-01 · M-02 · M-04 · M-12 · M-13 · M-14 · M-16 · M-17 · M-18 · M-21 · M-22 ·
M-23 · M-24 · M-25 · M-26 · M-27 · M-29 · M-31 · M-32 · M-36 · M-42 · M-43 ·
M-47 · M-55 · M-56 · M-57 · M-61 · M-65 · M-66 · M-67 · M-69 · M-70 · C-01 ·
C-02 · C-04 · C-05 · OQ-05 · OQ-10 · OQ-11 · OQ-19 · OQ-21 · OQ-24 · OQ-34

Verified mechanically by `closure_t01_8_1.py` section E.
