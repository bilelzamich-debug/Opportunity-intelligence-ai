# R-06 — Closed Ten-Type Relationship Taxonomy

| Field | Value |
|---|---|
| **ID** | R-06 |
| **Title** | Ratify D-06: Closed Ten-Type Relationship Taxonomy |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-06 |
| **Closes** | M-40 |
| **Backlog task** | `T00.2.6` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Exactly **ten relationship types** exist. The set is **closed**; engines may not invent relationships. Every relationship records the asserting engine and timestamp.

`DERIVES_FROM` · `SUPPORTS` · `CONSTITUENT_OF` · `ADDRESSES` · `TESTS` · `OUTCOME_OF` · `SUPERSEDES` · `DUPLICATES` · `CONTRADICTS` · `INFORMS`

`DERIVES_FROM` and `SUPPORTS` are deliberately distinct: an object *derives from* the inputs its engine read, and is *supported by* the subset that evidences it. These sets are not always identical.

## Context

v1 defines no relationship taxonomy (M-40), yet Principle 3 requires lineage as a first-class queryable structure and the Knowledge Graph's entire purpose is representing relationships.

Without a defined set, each engine would assert relationships of its own conception and the graph would become semantically incoherent — the failure PKP v2 §5.3 identifies.

## Alternatives Considered

**Option A — Closed ten-type taxonomy (selected).**

**Option B — Open or extensible taxonomy.**
*Rejected:* engines would assert relationships of private conception. A graph where `RELATES_TO` means something different depending on which engine wrote it cannot be traversed reliably, and violates AD-02's requirement that objects be self-describing.

**Option C — Lineage relationships only (`DERIVES_FROM` and `SUPERSEDES`).**
*Rejected:* cannot express contradiction (OQ-03), duplication (M-11), or aggregation (`CONSTITUENT_OF`). Each of these is required by a specific object type's validation rules.

**Option D — Ten types with a permitted extension mechanism.**
*Rejected:* an extension mechanism is an open taxonomy with extra steps. Extension should require amending this record, which forces the decision to be recorded.

## Rationale

A closed set is what makes the graph semantically coherent. Every traversal can rely on relationship meaning being uniform regardless of which engine asserted it.

The rigidity is **intentional**. Relationships not expressible in these ten cannot be represented without amending this record — and that constraint is the point. It forces new relationship semantics through a recorded decision rather than allowing them to accumulate silently.

The `DERIVES_FROM` / `SUPPORTS` distinction was retained despite the overlap because conflating them would overstate evidential support: an engine may read fifty Facts and be evidenced by three.

## What It Binds

- **Relationship model** (`T01.3.1`): exactly ten types; undefined types rejected at write.
- **Validation rule V12**: all relationships drawn from the closed taxonomy.
- Every relationship records asserting engine and timestamp.
- **Knowledge Graph** (`T01.3.3`): traversal semantics defined per type.
- `INFORMS` is the only relationship targeting something other than an object (engine behaviour) and is deliberately outside the lineage graph.

## Consequences Accepted

- Relationships outside the ten cannot be represented without amending this record.
- Ten types impose per-type traversal semantics on the Knowledge Graph.
- The `DERIVES_FROM` / `SUPPORTS` distinction requires engines to determine which inputs actually evidenced the output — a judgement, not a mechanical record.

## Known Tensions

**With M-23 (source diversity propagation, open).** Pattern Intelligence needs evidence-level diversity information that no relationship type carries directly. Under AD-02 this must be resolved by extending the object model (`T00.6.1`), not by adding a relationship or opening a side channel.

## Revisit Conditions

Reconsider only when a genuine cross-engine need cannot be expressed by any of the ten. Amendment adds a type by superseding this record — never by informal extension.
