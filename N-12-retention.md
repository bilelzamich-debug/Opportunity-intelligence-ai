# N-12 — Retention: Lineage Skeleton Permanent, Content Tiered by Reachability

| Field | Value |
|---|---|
| **ID** | N-12 |
| **Title** | Retention: Lineage Skeleton Permanent, Content Tiered by Reachability |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-38 |
| **Backlog task** | `T00.4.7` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md), [R-1](R-01-immutable-versioned-objects.md), [R-2](R-02-object-lifecycle.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**The lineage skeleton is retained permanently. Heavyweight content is tiered by reachability.**

| Retained permanently | Tiered when unreachable |
|---|---|
| Object identity, type, version, `lineage_id` | Evidence raw content |
| Lineage references and relationships | Large object payloads |
| `content_fingerprint`, provenance | — |
| Status, `status_reason`, attribution | — |

**Reachability rule.** An object is tiered only when it is **not reachable from any `ACTIVE` object** by lineage traversal. Anything supporting current knowledge stays.

**Tiering sets `ARCHIVED`** (R-2) and is invoked as a maintenance operation. **Lineage traversal never breaks** — the skeleton always resolves, so what was archived remains identifiable even when the content is not immediately available.

## Context

No retention policy existed (M-38). The `ARCHIVED` state was defined by R-2 with no trigger or owner.

Growth is monotonic and unbounded by construction: R-1 makes objects immutable, R-2 retains `REJECTED` candidates, R-5 versions Facts on every corroboration, and the platform loops continuously.

Principle 3 requires lineage to remain reconstructable indefinitely, which is in direct tension with deleting anything.

## Alternatives Considered

**Option A — Retain everything indefinitely.**
*Rejected:* maximal traceability, unbounded cost. Evidence raw content dominates storage and grows without limit.

**Option B — Archive by age.**
*Rejected:* simple, but age is uncorrelated with relevance. A two-year-old Evidence object may support a currently `ACTIVE` Opportunity; archiving it breaks live lineage.

**Option C — Archive by lineage reachability.**
Correct principle, but archiving whole objects — including their lineage references — would break traversal through them.

**Option D — Tiered: lineage skeleton permanent, content tiered by reachability (selected).** Option C's rule applied to content only.

**Option E — Delete unreachable objects entirely.**
*Rejected:* violates Principle 3 and integrity constraint I4 (referenced objects never hard-deleted). Also destroys the record that something was once believed and later withdrawn.

## Rationale

The insight is that **lineage structure and lineage content have very different costs and very different value over time.**

The skeleton — identities, references, fingerprints, provenance — is small and is what Principle 3 actually requires: the ability to reconstruct *what derived from what*. Raw Evidence content is large and is needed only for re-verification, which applies to knowledge still in use.

Tiering content while retaining the skeleton preserves Principle 3 structurally while bounding the dominant cost. Traversal never breaks; a query reaching an archived object finds a complete record of what it was, with its content retrievable through a slower path.

Retaining `content_fingerprint` permanently is what makes this safe: archived content remains **identifiable and verifiable** even when not immediately available.

## What It Binds

- **`T01.2.5`** ARCHIVED tiering by reachability.
- **I4** referenced objects never hard-deleted — satisfied.
- **Principle 3** lineage traversal never breaks after archival.
- **R-2** `ARCHIVED` gains a trigger and an owner.
- **OQ-12** Evidence storage mode materially changes the cost profile and must align.

## Consequences Accepted

- **Archived content may be needed for re-verification.** Retrieval is slower; `content_fingerprint` guarantees identifiability but not immediate availability.
- **Reachability computation is expensive** at scale — it requires traversal over the full object set.
- **Failure records and configuration are not covered** by this policy and need separate treatment.
- Storage still grows: the skeleton is permanent and unbounded, merely far smaller.

## Known Tensions

**With OQ-12 (open).** Whether Evidence is stored in full or by reference changes what tiering achieves.

**With N-10.** Failure record retention is unaddressed.

**With R-2.** `REJECTED` objects are retained for learning value; they are subject to tiering like any other unreachable object, which may remove content the Feedback Engine would have wanted.

## Revisit Conditions

Reconsider if skeleton growth alone becomes unviable, or if re-verification of archived content proves frequent enough that tiering is counterproductive.
