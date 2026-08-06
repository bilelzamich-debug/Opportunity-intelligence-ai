# R-03 — Two-Component Confidence with Monotonic Ceiling

| Field | Value |
|---|---|
| **ID** | R-03 |
| **Title** | Ratify D-03: Two-Component Confidence with Monotonic Ceiling |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-03 |
| **Closes** | M-15 |
| **Backlog task** | `T00.2.3` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Confidence has **two orthogonal components**, both required on every object:

| Component | Meaning | Determined by |
|---|---|---|
| `evidential_support` | Strength, breadth and independence of underlying evidence | Computed from lineage |
| `assertion_confidence` | The producing engine's certainty in its own inferential step | Asserted by the engine |

**Ceiling rule:** `effective_confidence ≤ min(effective_confidence of all upstream objects)`.

Confidence is monotonically non-increasing along the pipeline. Both components use a 0.00–1.00 scale with five mandatory band labels: `NEGLIGIBLE`, `WEAK`, `MODERATE`, `STRONG`, `VERY_STRONG`.

## Context

v1 defines no confidence model (M-15), yet the vision requires scoring and comparison, and Principle 1 requires distinguishing supported from unsupported claims.

Certainty necessarily degrades along the pipeline: each interpretive step adds inferential risk. Without a propagation rule, four confident inferential steps over moderate evidence compound into apparent near-certainty. PKP v2 identifies confidence inflation at the Opportunity stage as **the most consequential failure in the platform**, because that is the output driving resource commitment.

## Alternatives Considered

**Option A — Two components with a min() ceiling (selected).**

**Option B — Single scalar confidence.**
*Rejected:* cannot distinguish evidential weakness from inferential weakness. PKP v2 §2.1 requires that an object may be well-evidenced and low-confidence, or poorly-evidenced and high-confidence — and the second case is precisely the one that must be detectable. One number cannot express it.

**Option C — Categorical bands only, no numeric value.**
*Rejected:* prevents the ceiling rule from being computable.

**Option D — Two components with a weighted aggregate ceiling.**
*Rejected for now, recorded as OQ-20.* A weighted function could better reflect genuine corroboration across many independent moderate sources. Rejected because `min()` cannot inflate confidence, whereas a weighted function can. Revisitable once outcome data exists.

**Option E — No confidence model.**
*Rejected:* the vision requires scoring and comparison.

## Rationale

Two components are required because the platform must distinguish *"we have little evidence"* from *"we are unsure what the evidence means"*. These are different problems with different remedies — the first is solved by more research, the second by better reasoning.

The ceiling rule is the platform's **structural defence against confidence inflation**. The worked example in IOM §4.4 demonstrates it: Evidence at 0.62 yields an Opportunity at 0.58 (`MODERATE`) rather than the 0.85 its own assertion would suggest. Without the ceiling, the same chain manufactures near-certainty from moderate evidence.

`min()` was chosen over any weighted alternative on a single criterion: it cannot inflate. A conservative rule that occasionally understates is safer than a permissive one that occasionally overstates, given which failure is more consequential.

## What It Binds

- **Confidence attribute model** (`T01.5.1`): both components stored independently on every object.
- **Ceiling enforcement** (`T01.5.2`): computed from actual lineage; violation rejected at acceptance.
- **Validation rule V5**; **integrity constraint I7**.
- **O-V5**: Opportunity confidence bounded by originating Pattern.
- All nine object types.

## Consequences Accepted

- Two values must be justified rather than one, on every object.
- Bands invite treating the midpoint as meaningful.
- `min()` may understate confidence where many independent moderate sources genuinely converge — the case for OQ-20.
- Ceiling recomputation is required whenever upstream confidence changes (I7).

## Known Tensions

**With M-59 (support function, open).** `evidential_support` has no defined computation until S-2.

**With M-60 (calibration, open).** Nothing establishes that one engine's 0.7 means what another's does, making the ceiling arithmetically valid but semantically unsound across engines. This is the deepest unresolved issue in the confidence model, addressed by S-1.

**With OQ-20.** The `min()` versus weighted question is deliberately deferred until outcome data exists.

## Revisit Conditions

Reconsider the ceiling function (not the two-component structure) once P8 outcome data permits empirical evaluation of whether `min()` systematically understates. Recorded as OQ-20.
