# N-06 — Store/Graph Boundary: Objects Authoritative, Graph Derived

| Field | Value |
|---|---|
| **ID** | N-06 |
| **Title** | Store/Graph Boundary: Objects Authoritative, Graph Derived |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | C-06, M-39 |
| **Backlog task** | `T00.4.1` |
| **Depends on** | [R-1](R-01-immutable-versioned-objects.md), [R-8](R-08-behavioural-loop-closure.md), [R-6](R-06-relationship-taxonomy.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Objects are authoritative for their own lineage and relationships. The Knowledge Graph is a derived, rebuildable traversal index.**

| Component | Holds | Authority |
|---|---|---|
| **Knowledge Store** | Intelligence Objects, including their lineage and relationship references | **Authoritative** |
| **Knowledge Graph** | Traversal index over relationships the objects already assert | **Derived** |

**Consistency model (M-39).** The object write is **atomic**. Graph index update is **asynchronous and idempotent**. The graph may lag the store; it may never contradict it.

**Divergence is a performance concern, not a correctness one.** The graph can be discarded and rebuilt from the objects at any time. A divergent graph makes the platform *slow*, never *wrong*.

**Reconciliation.** Graph rebuild is a supported, repeatable operation over the full object set.

## Context

v1 lists Knowledge Store and Knowledge Graph as separate shared components without stating what distinguishes them (C-06), and defines no consistency model between them (M-39).

Both plausibly hold objects and relationships. Without a stated division they either duplicate state — creating a dual source of truth — or the boundary is decided implicitly by whoever implements first.

This is the **critical-path decision for P1**: it blocks N-7, N-8, N-9, N-11, N-12 and N-14, and it determines the structure of the platform's least changeable layer.

## Alternatives Considered

**Option A — Single component; graph as an internal index.**
*Rejected:* atomicity becomes trivial, but v1 names three shared components and this collapses two into one. A larger deviation than the boundary question requires.

**Option B — Two components, atomic dual write.**
*Rejected as the sole mechanism:* preserves v1's structure but couples the components transactionally, so a graph failure blocks an object write. It also makes the graph load-bearing for correctness, which is exactly what makes divergence dangerous.

**Option C — Two components, eventual consistency with reconciliation, both authoritative.**
*Rejected:* resilient, but with both authoritative there are windows where lineage is unresolvable, transiently breaching V3 and V4. Worse, when they disagree there is no rule for which is right.

**Option D — Objects authoritative, graph derived and rebuildable (selected).**

**Option E — Graph authoritative for relationships, objects for content.**
*Rejected:* an object would be uninterpretable in isolation, violating Article V — objects must be self-describing. It also means a graph failure makes every object's lineage unreadable.

## Rationale

Option D is chosen because it makes divergence **recoverable by construction**.

Under Article V an object must carry its own lineage: it has to be interpretable without consulting anything else. That alone rules out E and constrains C. Once objects carry authoritative lineage, the graph's role is necessarily derived — it is an access-path optimisation over information the objects already hold.

The decisive property: **the graph can never be the reason the platform is wrong.** It can only be the reason it is slow. Given that Principle 3 depends on lineage being correct, and traversal performance is merely desirable, this is the right asymmetry to design in.

Atomic object write with asynchronous index update follows directly. The object write is the correctness boundary; the index catches up. Idempotent index updates mean a failed or repeated update is harmless.

## What It Binds

- **`T01.1.4`** Knowledge Store write path: atomic object write.
- **`T01.3.2`** lineage carried on the object, version-specific (D-01a).
- **`T01.3.3`** Knowledge Graph as derived, rebuildable index.
- **`T01.3.4` / `T01.3.5`** traversal reads the index; correctness verifiable against objects.
- **N-7, N-8, N-9, N-11, N-12, N-14** — all depend on this boundary.
- Article V (objects self-describing) is enforceable.

## Consequences Accepted

- **Graph rebuild is expensive at scale.** Accepted in exchange for the correctness guarantee.
- **The graph may lag.** A newly written object may not be immediately traversable, so read-after-write on the index is not guaranteed.
- **Relationship data exists in two places.** Objects hold it authoritatively; the index holds a copy. This is deliberate duplication with a stated authority, not a dual source of truth.
- Reconciliation must be built and periodically exercised, or rebuild capability will silently rot.

## Known Tensions

**With OQ-14 (graph scope, open).** Global versus partitioned graph is unresolved. This decision does not constrain it.

**With N-11 (concurrency).** Asynchronous index update interacts with concurrent writes; N-11 must not assume immediate index consistency.

**With Principle 3.** Lineage traversal via a lagging index could transiently fail to find a valid path. Mitigated because correctness is verifiable against objects directly.

## Revisit Conditions

Reconsider only if graph rebuild proves impractical at production volume **and** an alternative preserving object self-description is identified. Rebuild cost alone is not grounds — it is the price of the correctness guarantee.
