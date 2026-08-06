# S-4 — Evidence Sufficiency Thresholds

| Field | Value |
|---|---|
| **ID** | S-4 |
| **Title** | Evidence Sufficiency Thresholds |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | M-06 |
| **Backlog task** | `T00.5.4` |
| **Depends on** | [S-2](S-02-evidential-support-function.md), [R-3](R-03-confidence-model.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Sufficiency is expressed in **independent sources**, never raw counts.

| Object | Minimum | Rationale |
|---|---|---|
| **Fact** | 1 independent source | A Fact asserts what a source says; one source suffices to establish that it was said |
| **Problem** | **2 independent sources** across its supporting Facts | An inference of deficiency from a single source is that source's opinion |
| **Pattern** | **3 independent sources** across constituent Problems, spanning **≥2 constituents** | Structure claimed from fewer cannot be distinguished from coincidence |
| **Opportunity** | Inherits its Pattern's sufficiency | Adds no evidence of its own |
| **Solution** | Inherits its Opportunity's sufficiency | Adds no evidence of its own |
| **Validation** | 1 independent source for the test result | The result is itself an observation |
| **Execution Record** | 1 verified outcome report | Ground truth, subject to M-47 verification |
| **Feedback Record** | **2 Execution Records** minimum | FR-V4 requires a pattern across outcomes, not a single result |

**Independent** means after independence grouping (`T02.1.3`): syndicated or commonly-owned sources count once.

**Enforcement.** Sufficiency is checked at acceptance. An object below threshold is **rejected**, not accepted with low confidence — this is a floor, distinct from the confidence gradient above it.

## Context

M-06 recorded no minimum evidence sufficiency per object type. Validation rules P-V1 and PT-V1 were written as "non-empty", a placeholder rather than a standard.

Without thresholds, Principle 1 is satisfiable by a single weak source: a Problem could be inferred from one complaint and a Pattern asserted over two Problems from the same source.

## Alternatives Considered

**Option A — Fixed minimum raw counts.**
*Rejected:* simple and enforceable, but counts raw occurrences. Ten syndicated copies of one article would satisfy any threshold while representing one observation.

**Option B — Confidence floor via `evidential_support`.**
*Rejected as sole mechanism:* principled and continuous, but circular at P1 — S-2's function is itself parameterised, so a support floor would be a threshold expressed indirectly and less legibly.

**Option C — Independence-based minimum source counts (selected).**

**Option D — No thresholds; record support and let downstream engines judge.**
*Rejected:* pushes the judgement to engines that lack evidence-level detail, and permits unsupported objects to become `ACTIVE` — precisely what Principle 1 forbids.

## Rationale

**Independence is the property that matters.** Raw counts are reliably wrong in the presence of syndication; independence assessment is occasionally wrong. That asymmetry decides it.

Thresholds are deliberately **low but non-trivial**. Two independent sources for a Problem and three for a Pattern are not high bars — they are the minimum at which a claim is distinguishable from a single voice or a coincidence. Setting them higher would suppress genuine early signal, which conflicts with the vision's discovery commitment.

**Rejection rather than low confidence** is the important choice. A floor and a gradient answer different questions: the gradient says *how strongly* to believe something, the floor says *whether it qualifies as a claim at all*. Conflating them would let unsupported objects circulate carrying a low number nobody acts on but everybody counts.

## What It Binds

- **P-V1** Problem supporting-facts threshold — enforceable.
- **PT-V1** Pattern constituent threshold — enforceable, with an independent-source requirement added.
- **FR-V4** Feedback Record overfitting guard.
- **`T01.4.2`** acceptance-path enforcement.
- **`T02.1.3`** independence grouping supplies the count.

## Consequences Accepted

- **Genuine single-source discoveries are rejected.** A real problem reported by exactly one source cannot become a Problem until corroborated — a deliberate cost of Principle 1.
- **Independence assessment is fallible**, and a false independence judgement inflates the effective count.
- **Thresholds are judgement values.** 2 and 3 are defensible, not derived; they should be revisited against O4/O5 (coverage and precision) from P8.
- Early-stage operation with a thin evidence base will reject much of what it finds.

## Known Tensions

**With the vision's discovery commitment.** Thresholds suppress weak early signal, which is where novel opportunities often first appear. The 2/3 values are set low deliberately to limit this.

**With S-2.** Thresholds and the support function are two mechanisms over the same inputs; they must not drift apart. The threshold is the floor, the function is the gradient.

## Revisit Conditions

**Revisit from P8** against N-3 measures O4 (coverage) and O5 (precision). If coverage is poor and precision high, thresholds are too strict; if the reverse, too permissive.
