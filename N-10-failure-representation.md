# N-10 — Failure Representation Outside the Object Model

| Field | Value |
|---|---|
| **ID** | N-10 |
| **Title** | Failure Representation Outside the Object Model |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-36 |
| **Backlog task** | `T00.4.5` |
| **Depends on** | [N-7](N-07-configuration-referent.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Engine failures are recorded as **failure records**, held **outside the Intelligence Object model**, co-located with the configuration store (N-7).

**Failure records never enter the lineage graph.** They are operational facts, not knowledge.

Every failure record identifies: the engine, the invocation, the inputs attempted, the configuration in force, the time, and the nature of the failure.

**A stage that produced nothing because it failed is distinguishable from a stage that produced nothing because it found nothing.** This distinction is mandatory at every stage.

## Context

v1 provides no object, state, or mechanism for an engine to signal that processing failed (M-36).

Without it, an empty result is indistinguishable from a failed one. The distinction is critical everywhere and decisive at two points: empty extraction versus failed extraction, and no validation result versus a negative one.

Orchestration cannot handle failures it cannot detect, and cannot support idempotence without knowing what actually completed.

## Alternatives Considered

**Option A — Failure as an Intelligence Object.**
*Rejected:* consistent with the object model, but failures are not knowledge. Placing them in the lineage graph would mean the platform could derive conclusions from its own malfunctions — a path Article IV exists to prevent in spirit.

**Option B — Failure as an object status.**
*Rejected:* reuses R-2's lifecycle, but conflates "this object is invalid" with "production of an object failed". In the failure case there is no object to carry the status.

**Option C — Failure records outside the object model, co-located with configuration (selected).**

**Option D — Failures in engine logs only.**
*Rejected:* logs are not queryable platform state. Orchestration needs to reason about what failed to make scheduling and idempotence decisions.

## Rationale

Failures are **operational facts about the platform**, not **knowledge about the world**. The object model is for the latter; conflating them pollutes the lineage graph with the platform's own malfunctions.

Co-locating with configuration is deliberate: both are platform state rather than platform knowledge, both are immutable, and both must be resolvable at a historical point. One state surface with a clear boundary is preferable to two.

The empty-versus-failed distinction is the operative requirement. Silent failure produces coverage holes with no error signal — and a coverage hole in the evidence layer is indistinguishable, downstream, from a market where nothing was found.

## What It Binds

- **`T01.1.7`** failure record store.
- **`T01.6.3`** failure surfacing: failures visible, never masked as completion.
- **N-8** failed acceptance produces a failure record.
- **`T02.2.5`** acquisition failures: not-found distinguishable from not-attempted.
- **Orchestration** reads failure records for scheduling and idempotence.

## Consequences Accepted

- **A second persistence surface** distinct from Intelligence Objects. The separation is correct but must be explicit and maintained.
- Failure records grow with operational volume and need their own retention treatment under N-12.
- Failures are invisible in lineage traversal — deliberately, but it means a coverage gap must be investigated through failure records rather than through the graph.

## Known Tensions

**With N-12 (retention).** Failure record retention is not addressed by object retention policy and must be specified separately.

**With Principle 3.** Failures are traceable, but through a separate surface. Full reconstruction of what the platform attempted requires consulting both objects and failure records.

## Revisit Conditions

Reconsider if the separation between operational state and knowledge proves unworkable in practice — for example, if failure patterns need to participate in reasoning, which would require a recorded decision about how without breaching Article IV.
