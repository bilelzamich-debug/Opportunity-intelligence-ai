# S-5 — Extraction Fidelity Verification

| Field | Value |
|---|---|
| **ID** | S-5 |
| **Title** | Extraction Fidelity Verification |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | M-67 (partially) |
| **Backlog task** | `T00.5.5` |
| **Depends on** | [N-8](N-08-acceptance-authority.md), [S-3](S-03-claim-equivalence.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Three layers.** Detection is not claimed to be complete; the residual error rate is **measured and published**.

### Layer 1 — Anchor verification (100% of Facts, at acceptance)

Every Fact's claim must be **locatable at its stated positional anchor** in the referenced Evidence.

| Check | Rejects |
|---|---|
| Anchor resolves to a real span in the Evidence | Fabricated anchors |
| Claim's **subject** and **predicate** (S-3) are present at that span | Claims attributed to spans that do not contain them |
| Claim's **value**, where present, appears at that span | Fabricated quantities |

Runs on every Fact via the acceptance-path hook (`T01.4.6`, N-8). Failure blocks acceptance.

**Explicit limit:** anchor verification catches fabricated *location*. It does **not** catch paraphrase drift — a claim genuinely derived from the span but subtly altered in meaning.

### Layer 2 — Sampled deep audit

A configurable sample of accepted Facts is audited for **semantic fidelity**: does the claim, including its qualifier, faithfully represent what the source says?

| Property | Value |
|---|---|
| Initial sample rate | 5% of accepted Facts, stratified by source type and extraction confidence |
| Audit judgement | `FAITHFUL` · `DRIFTED` · `UNSUPPORTED` |
| Adjustment | Sample rate rises for source types or confidence bands showing elevated drift |

### Layer 3 — Published hallucination rate

Audit results produce two **published platform quality metrics**:

| Metric | Definition |
|---|---|
| **Hallucination rate** | Proportion of audited Facts judged `UNSUPPORTED` |
| **Drift rate** | Proportion judged `DRIFTED` |

Both feed N-3's stage-2 proxy measures, are tracked as trends, and are **reported alongside platform output** so consumers can weigh it appropriately.

**A rising hallucination rate is a platform-level defect**, not a per-Fact issue.

## Context

Rule F-V6 requires that a Fact's claim be present in its Evidence. **No mechanism verified it.**

This is the platform's integrity floor and the highest-severity gap in the object model (M-67). A hallucinated Fact satisfies **every structural rule** — it has a reference, an anchor, an explanation, a confidence value — while being false. N-8 recorded explicitly that structural enforcement cannot catch it.

The consequence is uniquely severe: a fabricated claim at depth 1 corrupts the grounding layer, and every downstream conclusion inherits a falsehood that appears fully evidenced. By depth 6 it is effectively unrecoverable.

## Alternatives Considered

**Option A — Anchor verification only.**
*Rejected as sufficient:* mechanical and cheap, catches fabricated anchors, but misses paraphrase drift entirely. Adopted as Layer 1.

**Option B — Independent re-extraction and comparison.**
*Rejected:* catches more, but doubles extraction cost on the platform's highest-volume stage, and correlated model errors mean two extractions may agree on the same fabrication.

**Option C — Sampled human audit.**
*Rejected as sole mechanism:* catches semantic drift and provides a measured rate, but does not scale to 100% coverage. Adopted as Layer 2.

**Option D — Layered: anchor verification on all, sampled deep audit, published rate (selected).**

**Option E — Accept the risk; rely on downstream validation.**
*Rejected:* validation operates six stages later on solution assumptions, not on fact fidelity. By then the falsehood is embedded in Problems, Patterns and Opportunities.

## Rationale

**Detection cannot be perfect, so measurement is the objective.**

This is the decision's central position. No mechanism can guarantee that a model-extracted claim faithfully represents its source — the failure is semantic, and semantic judgement is exactly what is being checked. Attempting completeness would produce false assurance.

What *is* achievable: mechanical elimination of fabricated anchors (Layer 1, 100% coverage), statistical measurement of semantic drift (Layer 2), and honest publication of the residual rate (Layer 3).

**Publishing the rate is what converts an unknown risk into a known one.** An unmeasured hallucination rate means consumers cannot weigh platform output appropriately, and the platform cannot tell whether extraction is improving or degrading. Article X requires the platform to state what it does not know; this is that requirement applied to its own integrity floor.

Layer 1 leans on S-3: structured claims make anchor verification checkable component-by-component rather than as fuzzy string matching.

## What It Binds

- **`T03.2.1`** anchor verification on 100% of Facts.
- **`T03.2.2`** sampled deep audit protocol.
- **`T03.2.3`** hallucination rate as a published quality metric.
- **`T01.4.6`** semantic verification hook (N-8) is where Layer 1 attaches.
- **F-V6** becomes partially enforceable — mechanically for location, statistically for meaning.
- **N-3** stage-2 proxy measures.

## Consequences Accepted

- **M-67 is only partially closed.** Sampling means some hallucinations reach production. This is stated plainly rather than obscured.
- **5% is an initial value with no empirical basis** and must be tuned once drift distribution is observed.
- **Layer 2 requires human audit capacity** — an ongoing operational cost, not a one-off build.
- **Published rates may undermine confidence in platform output.** Accepted: an unpublished rate does not make output more reliable, only less honestly described.
- Anchor verification adds cost on the highest-volume acceptance path.

## Known Tensions

**With M-67.** This decision measures rather than eliminates. The marker should remain **open** with severity reduced, not be closed.

**With N-4 non-determinism.** Re-extraction produces different claims, so audit compares against the *source*, never against a re-run.

**With the vision's AI-native commitment.** Model-driven extraction is chosen deliberately; hallucination is its characteristic failure. The platform accepts the capability and measures the cost.

## Revisit Conditions

**Revisit the sample rate continuously** as drift distribution is observed. **Revisit the mechanism** if measured hallucination rates exceed the level at which the grounding layer can be trusted — at which point Option B (independent re-extraction) becomes justified despite its cost.
