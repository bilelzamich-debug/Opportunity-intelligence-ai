# N-19 — Experiment Registry: Reserved in P1, Built in P7

| Field | Value |
|---|---|
| **ID** | N-19 |
| **Title** | Experiment Registry: Reserved in P1, Built in P7 |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-53 |
| **Backlog task** | `T00.6.4` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Placement reserved in P1. Capability built in P7.**

| Phase | Deliverable |
|---|---|
| **P1** | Component placement reserved; boundary with the Knowledge Store fixed; no capability built |
| **P7** | Full capability — experiment state, lifecycle, negative-result retention (`T07.1.3`, `T07.1.4`) |

### Boundary — fixed now

| Holds | Component |
|---|---|
| **Mutable, in-flight experiment state** — scheduled, running, abandoned | Experiment Registry |
| **Immutable concluded results** | Validation objects, in the Knowledge Store |

A Validation object is created **only when an experiment concludes**. Until then the experiment exists solely in the Registry.

This is the C-05 boundary, provisionally settled here and formally confirmed at `T07.1.1`.

### Why reserve rather than defer entirely

The Registry holds **mutable operational state** — a fundamentally different character from the Knowledge Store's immutable objects (R-1). Discovering that difference in P7 would mean retrofitting a second persistence model into a foundation built exclusively for immutability.

## Context

M-53: the Experiment Registry has no roadmap phase, yet P7 requires it. v1 names it as one of three shared components but never schedules its construction.

C-05 also remains open: the relationship between Validation objects and Registry entries is undefined, risking dual sources of truth.

## Alternatives Considered

**Option A — Build in P1 with the other shared components.**
*Rejected:* consistent with treating all three shared components together, but builds capability five phases before it is used, against requirements (M-32 validation methodology) that are not yet defined.

**Option B — Build entirely in P7 where it is needed.**
*Rejected:* avoids premature work, but risks discovering in P7 that the foundation cannot accommodate mutable state — the Knowledge Store is built exclusively for immutable objects under R-1.

**Option C — Split: placement reserved in P1, capability in P7 (selected).**

**Option D — Fold the Registry into the Knowledge Store.**
*Rejected:* eliminates a component, but mixes mutable operational state with immutable knowledge in one component — the same concern CI-1 addresses for configuration, and here without CI-1's isolation guarantee.

## Rationale

The split follows the same reasoning as N-5's tenancy reservation: **reserve the expensive-to-retrofit part now, build the rest when requirements exist.**

What is expensive to retrofit is the *accommodation of a second persistence model* — mutable operational state alongside immutable knowledge. That is a foundation property. What is cheap to defer is the *capability* — experiment lifecycle, state transitions, result recording — which depends on M-32 (validation methodology), unresolved until `T07.1.2`.

Fixing the boundary now also **eliminates the dual-truth risk in C-05** before any implementation can embed it: mutable state in the Registry, immutable results in Validation objects, with a single handoff at conclusion.

## What It Binds

- **P1** Registry placement reserved; boundary fixed.
- **`T07.1.3`** Registry capability build.
- **`T07.1.4`** experiment lifecycle.
- **C-05** provisionally resolved; confirmed at `T07.1.1`.
- **V-I1** negative results never suppressed — the Registry must retain abandoned and failed experiments.

## Consequences Accepted

- **A reserved placement is not a component.** It provides nothing in P1–P6 and must not be mistaken for existing capability.
- **The P1 portion risks under-specification** — reserving space for requirements not yet known.
- **Two persistence models** in the platform, with a boundary maintained by discipline.

## Known Tensions

**With C-05 (open until `T07.1.1`).** The boundary is fixed provisionally; formal confirmation awaits validation methodology.

**With R-1.** The Registry deliberately holds mutable state, an exception to platform-wide immutability, justified because operational state is not knowledge.

**With N-12 retention.** Registry records are not Intelligence Objects and need separate retention treatment.

## Revisit Conditions

Reconsider if P7 reveals the Registry needs foundation properties not reserved in P1, or if C-05 resolves toward a different boundary at `T07.1.1`.
