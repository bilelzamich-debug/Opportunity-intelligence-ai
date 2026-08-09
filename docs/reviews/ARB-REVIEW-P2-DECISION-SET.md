# ARB Review — P2 Decision Set N-20 … N-23

**Scope:** the four drafts treated as one architectural system.
**Method:** drafting-time reasoning treated as untrusted; every claim re-tested
against draft text and the ratified corpus.
**Date:** 2026-08-04
**Authority:** review only. Nothing ratified (Playbook **F6**).

---

## VERDICT

> ### CONDITIONALLY COHERENT — the set can coexist, but **must not be ratified
> as drafted.** Two HIGH-severity seam defects (C-4, C-5) and one blocking
> external contradiction (D-1) require amendment first.

The four drafts are **acyclic, non-duplicating, and contradict no ratified
decision** (0 supersessions required). The defects are all at the **seams
between drafts** — invisible while drafting each in isolation, which is
precisely what this review existed to find.

---

## PART 1 — Dependency Reconstruction

### 1.1 Decision dependency graph

```
        N-20 (taxonomy) ──frame──────────────▶ N-22 (coverage)
             │                                      ▲
             └──typability gate──▶ N-21 (rights) ────┘ REFUSED_BY_RIGHTS
                                                      ▲
        N-23 (directive) ──scope──────────────────────┘ OUT_OF_SCOPE
```

**Acyclic — verified.** N-22 is a pure sink: no draft depends on it.
Topological order: **N-20 → {N-21, N-23} → N-22**.

### 1.2 Information flow

| Artefact | Producer | Consumer |
|---|---|---|
| `source_type` | N-20 | N-22 (frame), S-02 input 2, S-05 |
| `access_conditions` rights values | N-21 | N-15 (storage mode) |
| Directive scope | N-23 | Research, N-22 (`OUT_OF_SCOPE`) |
| Coverage report | N-22 | `T05.1.4` PT-V5 |
| **Trust rating** | **N-20** | **NOTHING** — non-scoring by S-02 |

**Observation:** trust is a producer with no consumer. Not a defect (it is the
deliberate consequence of S-02's closed input list), but it means N-20 §5.3
delivers a write-only artefact until S-02 is superseded.

### 1.3 Authority flow

| Action | Authority | Basis |
|---|---|---|
| Assign `source_type` | Research | IOM §2.5 (existing) |
| Own rights **policy** | Human authority **outside** platform | N-01 / Art. VI |
| Enforce rights | Research, pre-acquisition | v2 §4.4 (existing) |
| Measure coverage, declare gaps | Research | N-22 §3 Option D |
| Raise directives | 3 originators | N-23 §5.3 |
| Populate work set | Orchestration | N-17 (existing) |

**No new engine, object or stage** (F8 safe). Research accumulates four roles
but each traces to an existing grant.

### 1.4 Lifecycle flow

| Entity | States |
|---|---|
| Evidence | R-2's seven (RATIFIED) |
| **Directive** | **N-23's five** — `PROPOSED`, `ACTIVE`, `FULFILLED`, `CANCELLED`, `EXPIRED` |
| Trust rating | none — versioned, append-only |
| Rights assessment | none — 3 acquisition + 4 retention values |

---

## PART 2 — Pairwise Consistency (falsification attempted)

| Pair | Result |
|---|---|
| **N20 ↔ N21** | **C-4** — both claim "Both gates must pass"; neither states evaluation **order** |
| **N20 ↔ N22** | **C-3** (dangling dependency), **C-5** (untypable sources unreportable) |
| **N20 ↔ N23** | Clean — directives scope *subject matter*, taxonomy types *channels*; orthogonal |
| **N21 ↔ N22** | Clean — `REFUSED_BY_RIGHTS` defined by N-22, produced by N-21 |
| **N21 ↔ N23** | **C-4** — third gate added; no ordering |
| **N22 ↔ N23** | **C-1** — `OUT_OF_SCOPE` ownership unassigned; each defers to the other |

**No circular dependency. No conflicting ownership. No duplicated
responsibility** (except C-1's unowned token). **No supersession required
between drafts.**

---

## PART 3 — Ratified Compatibility

| Decision | Verdict | Evidence |
|---|---|---|
| **N-02** | **REQUIRES ANNOTATION** | D-1: `T02.2.4` AC2 needs a 4th gate N-02 forbids. N-23 correctly declines to create one → the **backlog AC** must be amended (Art. XI), not N-02 superseded |
| N-03 | Compatible | N-22 refines source-type coverage via N-03's own Revisit clause |
| N-08 | Compatible | N-21 enforces pre-acquisition; Store stays structural-only |
| N-10 | Compatible | All refusals/gaps route to failure records |
| N-12 | Compatible | N-21 §5.6 separates retention rights from retention policy |
| N-15 | Compatible | N-21 §5.7 **supplies** what N-15 declares it consumes |
| N-16 | Compatible | Type stays Tier 2; no universal attribute added |
| N-17 | Compatible | N-23 supplies the missing work-set input |
| S-02 | Compatible | Trust and coverage both excluded from inputs |
| S-04 | Compatible | Sufficiency stays per-object; coverage descriptive |
| S-05 | Compatible | Stratification becomes possible |
| R-01 | Compatible | Append-only trust and rights records |
| **R-02** | **REQUIRES ANNOTATION** | **C-2**: N-23 reuses `PROPOSED`/`ACTIVE` for directive states |
| R-03 | Compatible | Trust excluded from ceiling arithmetic |
| R-06 | Compatible | No relationship type touched |

**Compatible 13 · Requires annotation 2 · Requires supersession 0 ·
Contradicts 0.**

---

## PART 4 — Hidden Conflicts (the substance of this review)

### C-4 — Three pre-acquisition gates, no defined order · **HIGH**
*Class: ambiguous execution / non-determinism.*

N-20 §5.2 (typability), N-21 §5.4 (rights), N-23 §5.2 (scope) each refuse
acquisition. Both N-20 and N-21 assert *"Both gates must pass"* — written as
if only two existed. **No draft states evaluation order** (verified: search
for order/precedence/sequence returns nothing).

**Consequence:** a source that is untypable **and** prohibited **and**
out-of-scope produces an *indeterminate* gap reason in N-22 §5.4. Two
implementations could record different reasons for identical input —
violating the determinism S-02 P7 and N-04 rely on elsewhere.

### C-5 — Untypable sources are invisible to coverage · **HIGH**
*Class: dead reporting path / hidden coupling.*

N-20 §5.2 refuses sources mapping to no member. N-22 §5.1 defines the frame as
**taxonomy members**, and a gap as *a member with no ACTIVE Evidence*.

**An untypable source is therefore not a member, so it can never be a gap.**
The platform can refuse an entire class of material and still report **100 %
coverage**.

Verified: N-22 §5.4's five reasons contain **no** reason for untypable, and
the words *untypable / unclassifiable / does not map* appear nowhere in N-22.

This reintroduces, at the N-20↔N-22 seam, exactly the sampling-bias blind spot
M-17 exists to prevent — and contradicts Article X (*"states what it does not
know"*), which N-22 itself cites as J10.

### C-3 — N-22 depends on an open marker, not on a decision · **MEDIUM**
*Class: dangling dependency.*

N-22's header reads `Depends on | **M-16 (OPEN …)**`. Every ratified record
depends on *decisions*. As drafted, ratifying N-20 does not satisfy N-22's
declared dependency, because it points at the gap rather than its closure.

### C-2 — `PROPOSED`/`ACTIVE` overloaded · **MEDIUM**
*Class: two meanings for one token.*

R-2 fixes both for Intelligence Objects; N-23 §5.6 reuses both for directive
states, and N-22 uses `ACTIVE` in the R-2 sense. N-23 disclaims the overlap,
but one architecture now has `ACTIVE` meaning two things.

### C-1 — `OUT_OF_SCOPE` ownership unassigned · **LOW**
*Class: duplicated responsibility.*

N-22 §6.6 says it *"references directives without defining them"*; N-23 §6 says
N-22 *"consumes `OUT_OF_SCOPE`… this record does not define coverage"*. Each
defers to the other. Meanings agree, so no divergence — but no owner.

### Checked and NOT found
Cyclic authority · impossible lifecycle · unreachable state · multiple sources
of truth for one attribute · configuration/policy confusion (N-20's registry
and N-23's directives are both non-scoring infrastructure state; N-21's rights
sit on the Evidence object, so CI-1 is not engaged).

---

## PART 5 — Completeness

**No marker is fully closed. Four partial closures.**

| Marker | Closed | Still open |
|---|---|---|
| M-01 | initiation, originators, lifecycle, cancellation | self-direction (D-2, no canonical ID); target approval (D-1) |
| M-16 | taxonomy, eligibility, trust representation | trust **scoring** (needs S-02 supersession); learnability (M-02/M-43) |
| M-17 | coverage + completeness concepts | stopping (→ M-01); **untypable reporting (C-5)** |
| M-18 | rights half | conduct half (M-18b); v2 §14 "compliance" scope |

### Acceptance criteria still blocked after all four ratified

| AC | Blocker |
|---|---|
| `T02.1.1` AC3 — learnable P8 target | M-02 / M-43 |
| `T02.1.4` AC1 — coverage measurable | needs N-20 **and** C-5 fixed |
| `T02.2.4` AC2 — approval per human gate | **D-1** |
| `T02.3.1` AC1 — every defined source type | N-20 + operational acquisition |
| `T02.1.2` (all) | satisfiable, but **inert** — N-21 §5.1 names no rights authority |

### Downstream still blocked
- **D-1** (`T02.2.4` AC2): **22 tasks**, all of P7–P8 feedback intake.
- **T02.1.1 AC3**: 94 tasks transitively.

---

## PART 6 — Minimal Ratification Plan

| Order | Draft | Recommendation | Justification |
|---|---|---|---|
| 1 | **N-21** | **CAN BE RATIFIED IMMEDIATELY** | Self-contained; supplies what N-15 already consumes; depends on no other draft; 0 supersessions. Note it is *inert* until a rights authority is named |
| 2 | **N-20** | **MUST BE AMENDED FIRST** — then ratify | Add a gate-ordering clause (C-4) and an untypable-source reporting obligation (C-5). It is the frame for N-22, so it must precede it |
| 3 | **N-23** | **SHOULD WAIT** | Ratifiable in itself, but D-1 leaves `T02.2.4` incompletable. Ratify only alongside a decision to amend AC2 (or a separate 4th-gate record superseding N-02) |
| 4 | **N-22** | **MUST WAIT** + **MUST BE AMENDED** | Explicitly inert until M-16 closes; must re-point its dependency from `M-16` to `N-20` (C-3); must gain an untypable gap reason (C-5) |

**Minimum safe sequence:** amend N-20 → ratify N-21 → ratify N-20 → resolve
D-1 → ratify N-23 → amend N-22 → ratify N-22.

**Do not ratify all four together.** C-4 and C-5 only become live defects when
N-20 and N-22 coexist.

---

## PART 7 — Failure Analysis

**Attempt to prove the set cannot work.**

| Attack | Outcome |
|---|---|
| Counterexample: source untypable + prohibited + out-of-scope | **SUCCEEDS** → C-4 (indeterminate reason) and C-5 (unreportable) |
| Counterexample: whole channel refused as untypable | **SUCCEEDS** → C-5: 100 % coverage reported while blind |
| Circular dependency | Fails — graph is acyclic (§1.1) |
| Two authorities for one action | Fails — each action has exactly one authority (§1.3) |
| Impossible/unreachable lifecycle state | Fails — all five directive states reachable and exitable |
| Governance violation (F2/F3/F6/F8) | Fails — no new engine/object/stage; all drafts `DRAFT`; markers closed only by record |
| Multiple legal interpretations | **SUCCEEDS** → C-4 permits ≥2 conforming implementations |
| Non-determinism | **SUCCEEDS** → same input, different recorded gap reason |

**The set cannot be proven unworkable — but it can be proven ambiguous.** The
architecture is sound; the seams are underspecified. Both HIGH findings are
repairable by amendment without touching any ratified decision.

---

## PART 8 — Deliverables

### Conflict matrix

| | N-20 | N-21 | N-22 | N-23 |
|---|---|---|---|---|
| **N-20** | — | C-4 | C-3, C-5 | — |
| **N-21** | C-4 | — | — | C-4 |
| **N-22** | C-3, C-5 | — | — | C-1 |
| **N-23** | — | C-4 | C-1 | — |

### Authority matrix

| Action | Research | Orchestration | External human | Store |
|---|---|---|---|---|
| Assign `source_type` | **✔** | | | |
| Own rights policy | | | **✔** | |
| Enforce rights | **✔** | | | |
| Measure coverage / declare gaps | **✔** | | | |
| Raise directive | | | ✔ (commission) | |
| Populate work set | | **✔** | | |
| Acceptance (structural) | | | | **✔** |

No cell has two authorities. No action is unowned.

### Lifecycle matrix

| Entity | States | Governing record | Conflict |
|---|---|---|---|
| Evidence | 7 | R-2 | — |
| Directive | 5 | N-23 §5.6 | **C-2** token overload |
| Trust rating | versioned, stateless | N-20 §5.3 | — |
| Rights assessment | valued, stateless | N-21 §5.5 | — |

### Required annotations
1. **R-02** — record that `PROPOSED`/`ACTIVE` are also directive-state names (C-2).
2. **N-02** — record that `T02.2.4` AC2 is unsatisfiable as written; N-02 unchanged (D-1).
3. **marker-crosswalk** — four partial closures.

### Required supersessions
**NONE.** (A future trust-scoring decision would supersede S-02; not now.)

### Remaining open questions
1. Gate evaluation order (C-4) — **must be decided before N-20 + N-22 coexist**.
2. How untypable sources are reported (C-5).
3. Owner of `OUT_OF_SCOPE` (C-1).
4. D-1 — amend AC2, or 4th gate superseding N-02?
5. D-2 — canonical ID for self-direction.
6. Rights authority identity (N-21 §5.1).
7. Whether "compliance" (v2 §14) is inside M-18.

---

## Honest Limitations

- **C-4 and C-5 are defects I introduced while drafting**, and neither was
  visible in the single-decision reviews. That is evidence the per-decision
  process is insufficient on its own, not that these two drafts are unusually
  weak.
- I did **not** re-verify the internal correctness of each draft's constraint
  extraction — this review assumes each draft's own citations are sound and
  examines only their interaction.
- The severity ratings are my judgement. C-5 could be argued LOW if untypable
  sources are expected to be rare; I rated it HIGH because it silently
  inflates a bias metric, which is the failure v2 §9 calls most dangerous.
- Fixing C-4/C-5 requires adding clauses to N-20 and N-22. I have **not**
  drafted them — that would be new architecture, outside this mandate.

---

**Status: review only. Nothing ratified, no draft modified.**
