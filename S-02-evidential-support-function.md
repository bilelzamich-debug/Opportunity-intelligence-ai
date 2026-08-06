# S-2 — Evidential Support Function

| Field | Value |
|---|---|
| **ID** | S-2 |
| **Title** | Evidential Support Function |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | M-59 |
| **Backlog task** | `T00.5.2` |
| **Depends on** | [S-1](S-01-calibration-rubric.md), [R-3](R-03-confidence-model.md), [R-5](R-05-canonical-claims.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

`evidential_support` is computed by a **single platform-wide function** over lineage. It is **deterministic given lineage** and comparable across all object types.

### Inputs — exhaustive

| # | Input | Source |
|---|---|---|
| 1 | **Independent source count** | Distinct Evidence sources beneath the object, after independence grouping |
| 2 | **Source diversity** | Number of distinct source *types* represented |
| 3 | **Corroboration depth** | For Facts, attachments per canonical claim (R-5) |
| 4 | **Contradiction presence** | Whether `CONTRADICTS` relationships exist in the supporting set |
| 5 | **Upstream support** | The `evidential_support` of contributing objects |

**No other input.** Confidence asserted by engines (`assertion_confidence`) is explicitly **not** an input — the two components must remain orthogonal per R-3.

### Behaviour — normative properties, not a formula

| # | Property | Rationale |
|---|---|---|
| P1 | **Monotonic in independent sources** — more independent sources never decrease support | Corroboration is evidence |
| P2 | **Saturating** — the tenth independent source adds less than the second | Diminishing returns; prevents volume dominating quality |
| P3 | **Diversity-weighted** — *n* sources of one type yield less than *n* across types | Counters sampling artefact, the platform's most dangerous systemic failure |
| P4 | **Independence-gated** — non-independent sources count once | Prevents syndication inflation |
| P5 | **Contradiction-penalised** — unresolved contradictions reduce support | Disagreement is genuine uncertainty |
| P6 | **Bounded by upstream** — never exceeds the support of contributing objects | Consistent with R-3's ceiling |
| P7 | **Deterministic** — identical lineage yields identical support | Required for comparability |

The precise curve is an implementation parameter; **these seven properties are the contract.**

### Comparability across object types

The function reads only lineage, which every object type carries in the same form. An Opportunity at depth 4 and a Fact at depth 1 are scored by the same measure — *how much independent external observation stands behind this* — so values are directly comparable regardless of stage.

## Context

R-3 made `evidential_support` mandatory on every object. M-59 recorded that no function computes it.

Without one, the attribute is either unpopulated — blocking objects from reaching `ACTIVE` — or populated arbitrarily per engine, making values incomparable and R-3's ceiling arithmetic over meaningless numbers.

## Alternatives Considered

**Option A — Single platform-wide function (selected).**

**Option B — Per-object-type functions.**
*Rejected:* better fit for type-specific nuance, but destroys comparability across types — which the ceiling rule requires, since it compares support across a lineage chain spanning every type.

**Option C — Engine-asserted with recorded justification.**
*Rejected:* maximally flexible, abandons comparability entirely, and collapses the R-3 distinction between evidential and inferential confidence.

**Option D — Central base value with bounded per-type adjustment.**
*Rejected for now.* Reasonable, but adds a tuning surface before any evidence exists that a single function is inadequate. Available later if type-specific bias is observed.

## Rationale

Comparability matters more than nuance at this stage, and **the ceiling rule's validity depends on it.**

Specifying **properties rather than a formula** was deliberate. A formula fixed now would encode guesses about relative weights with no empirical basis — precisely what Principle 1 forbids. The seven properties are what the architecture actually requires; the curve satisfying them is tunable without a contract change.

P3 (diversity weighting) and P4 (independence gating) carry the most weight. Together they counter frequency inflation, which PKP v2 identifies as corrupting every downstream aggregation. Ten syndicated copies of one claim must not outweigh two genuinely independent observations.

## What It Binds

- **`T01.5.3`** support computation.
- **`T01.5.4`** independent-source-count summary attribute is input 1.
- **`T02.1.3`** source independence grouping determines input 1.
- **R-3** ceiling operates on comparable values.
- **S-4** sufficiency thresholds expressed against this measure.

## Consequences Accepted

- **A single function will misjudge specific cases.** Accepted: an incomparable measure silently corrupts every ranking, which is worse and harder to detect.
- **Properties without a formula leave a tuning surface** that must be governed to avoid drift between environments.
- **Recomputation on upstream change** (I7) makes support a derived value requiring maintenance.
- P5's contradiction penalty may over-penalise healthy disagreement in genuinely contested markets.

## Known Tensions

**With M-23 (source diversity propagation).** Input 2 requires diversity information reaching downstream engines; the summary attribute (`T01.5.4`) provides it, deep traversal provides detail.

**With N-4 determinism.** P7 holds because the function reads only stored lineage, not model output — one of the few genuinely deterministic computations in the platform.

## Revisit Conditions

Reconsider toward Option D if measured type-specific bias emerges — for example, if Patterns systematically score lower than their evidence warrants because of fan-in effects.
