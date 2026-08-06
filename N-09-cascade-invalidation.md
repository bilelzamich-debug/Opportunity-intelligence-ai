# N-09 — Cascade Invalidation: Mechanical Operation Invoked by Orchestration

| Field | Value |
|---|---|
| **ID** | N-09 |
| **Title** | Cascade Invalidation: Mechanical Operation Invoked by Orchestration |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-58, M-09 |
| **Backlog task** | `T00.4.4` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md), [N-8](N-08-acceptance-authority.md), [R-2](R-02-object-lifecycle.md), [AD-04](AD-04-separation-of-concerns.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Cascade invalidation is a **mechanical integrity operation** over the lineage graph, **invoked by Orchestration**, performing **no interpretation**.

When an object transitions to `RETRACTED` or `INVALIDATED`, the operation performs forward lineage traversal and transitions all dependents to `INVALIDATED` with `status_reason` naming the originating object.

The operation **propagates a status already determined at the source**. It makes no judgement about whether a dependent is still valid — that determination was made when the upstream object was withdrawn.

**Properties:** idempotent, terminating (guaranteed by the acyclic lineage graph under R-8), and altering status only, never content.

## Context

Integrity constraint I6 requires that retracting Evidence invalidates all downstream dependents. No engine owns this (M-58), and retraction semantics were undefined (M-09).

Retraction is routine, not exceptional — sources withdraw content regularly. Without cascade, conclusions built on withdrawn evidence remain `ACTIVE` and indistinguishable from sound ones. This is a silent-corruption path directly through the grounding layer.

It must exist in P1 because the lineage structures that make cascade possible are built in P1.

## Alternatives Considered

**Option A — Orchestration owns cascade as an engine responsibility.**
*Rejected as framed:* Orchestration is forbidden from making knowledge judgements. Framing cascade as an Orchestration *responsibility* implies it judges validity.

**Option B — Knowledge Graph performs cascade as a structural operation.**
*Rejected:* the graph owns traversal, but v1 states the graph does not infer. More decisively, under N-6 the graph is a derived index — it cannot author status changes to authoritative objects.

**Option C — Each engine invalidates its own outputs on notification.**
*Rejected:* respects ownership but requires an engine notification mechanism that does not exist, and creates engine-to-engine coupling that Article V and Principle 4 forbid.

**Option D — A mechanical operation with no engine owner, invoked by Orchestration (selected).**

## Rationale

The key distinction is between **propagating a decision** and **making one**.

The judgement — that this Evidence is withdrawn — happens at the source. Cascade merely follows the consequences through the graph. That is mechanical, not interpretive, so it can be invoked by Orchestration without Orchestration becoming a knowledge authority: it **triggers**, it does not **judge**.

Option D also avoids inventing a tenth engine for what is fundamentally a maintenance operation over existing structure.

Termination is guaranteed rather than hoped for: R-8 and Article IV keep the lineage graph acyclic, so forward traversal cannot loop.

## What It Binds

- **`T01.2.3`** cascade invalidation operation.
- **`T01.3.5`** forward traversal from Evidence to dependents.
- **I6** becomes enforceable.
- **M-09** retraction semantics resolved: retraction at source, cascade to dependents, status only.
- **`T01.2.4`** partial retraction: an object retaining at least one valid upstream reference is re-versioned, not invalidated.

## Consequences Accepted

- **Introduces an operation that is not an engine** — a mild structural novelty, accepted as smaller than the alternatives.
- **Cascade cost scales with fan-out.** Retracting a widely-used Evidence object may invalidate a large subgraph.
- **Invalidation is coarse.** A dependent supported by ten Facts, one of which is invalidated, is handled by the partial-retraction rule rather than by cascade — the boundary between the two must be maintained carefully.

## Known Tensions

**With AD-04.** An operation with no engine owner sits outside the engine taxonomy. Justified because assigning it to an engine would either expand Orchestration's remit into judgement or create engine-to-engine coupling.

**With M-65 (open).** Re-derivation policy on supersession is distinct from invalidation on retraction and remains unresolved until `T05.2.2`.

## Revisit Conditions

Reconsider if cascade proves too coarse in practice — for example, if partial invalidation semantics are needed at scale — or if an engine emerges as the natural owner.
