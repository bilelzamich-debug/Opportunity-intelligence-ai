# R-05 — Facts as Canonical Claims with Multiple Evidence Attachments

| Field | Value |
|---|---|
| **ID** | R-05 |
| **Title** | Ratify D-05: Facts as Canonical Claims with Multiple Evidence Attachments |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-05 |
| **Closes** | M-11 |
| **Backlog task** | `T00.2.5` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

A **Fact represents a canonical claim, not an extraction event.**

When extraction yields a claim semantically equivalent to an existing Fact, a new `evidence_attachment` is added to that Fact rather than a new Fact being created.

Each attachment records its own `evidence_ref`, `positional_anchor`, `extracted_at`, `extraction_confidence`, and `independence_assessment`.

## Context

v1 does not define fact identity or deduplication (M-11).

The consequence is severe and easy to miss: if ten sources state the same thing and produce ten Facts, the platform sees ten independent corroborations of one claim. Every downstream frequency judgement — pattern strength, problem weight, evidential support — is then computed on inflated counts.

## Alternatives Considered

**Option A — Canonical claims with multiple attachments (selected).**

**Option B — One Fact per extraction event.**
*Rejected:* makes corroboration uncountable. Ten sources stating the same thing appear as ten independent facts, structurally guaranteeing the frequency-inflation failure mode identified in PKP v2 §4.2 and §4.4.

**Option C — Deduplication as a downstream concern.**
*Rejected:* pushes the problem to Pattern Intelligence, which operates four stages away and lacks the evidence-level detail — positional anchors, source identity, independence — needed to resolve it.

**Option D — Canonical claims with aggressive automatic merging.**
*Rejected:* over-merging hides genuine source disagreement and is **irreversible**, since merged claims cannot be separated once identity is assigned. Conservative merging with explicit `DUPLICATES` links for uncertain cases is preferred: deliberate under-merging is recoverable.

## Rationale

Corroboration is only measurable if the same claim from different sources resolves to one Fact with multiple attachments. This is the single mechanism that makes `independent_source_count` meaningful, and that count feeds `evidential_support`, which feeds the confidence ceiling.

The asymmetry between error directions drove the conservative posture: **under-merging inflates apparent corroboration but is visible and correctable; over-merging destroys information irreversibly.** Where equivalence is uncertain, the rule is do not merge — record `DUPLICATES` instead.

## What It Binds

- **Fact object type** (`T01.7.2`): `evidence_attachments` structure, minimum one attachment.
- **Merge mechanism** (`T03.1.4`).
- **F-V1, F-V2, F-V5**: attachment present, anchors resolvable, `independent_source_count ≤ attachment count`.
- **F-I2**: attachments only added, never removed.
- **Partial retraction** (`T01.2.4`): a Fact retaining at least one valid attachment is re-versioned, not invalidated.

## Consequences Accepted

- Fact Extraction must perform semantic equivalence judgement, fallible in both directions.
- Adding an attachment modifies a Fact, requiring a new version under D-01 — so frequently-attested Facts develop long supersession chains.
- Merge errors are permanent, since object identity is permanent under I2.

## Known Tensions

**With M-62 (semantic equivalence criterion, open).** What makes two claims "the same claim" is undefined until S-3. This is blocking for P3 and is the decision on which R-5's correctness depends.

**With D-01.** Version churn on corroboration is an accepted cost of combining immutability with canonical claims.

## Revisit Conditions

Reconsider only if semantic equivalence proves undeterminable to an acceptable error rate, such that canonical claims cannot be maintained reliably. In that case the fallback is Option D's conservative variant: never merge, always link with `DUPLICATES`, and compute corroboration across linked sets.
