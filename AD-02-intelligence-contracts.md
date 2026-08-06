# AD-02 — Intelligence Contracts

| Field | Value |
|---|---|
| **ID** | AD-02 |
| **Title** | Intelligence Contracts |
| **Status** | `RECONSTRUCTED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | Unknown — predates PKP v1 |
| **Source** | PKP v1 §8 (title only); PKP v2 §8.4 (substance) |
| **Supersedes** | — |
| **Superseded by** | — |

> **Provenance warning.** v1 recorded this decision as the bare title "Intelligence contracts". **Decision**, **What It Binds** and **Consequences** are *established* from PKP v2 §8.4. **Context** and **Alternatives Considered** are *reconstructed* from the architecture's internal logic and are not a historical record.

---

## Decision (established)

Engines communicate exclusively through defined Intelligence Objects.

The object definitions constitute the complete inter-engine interface surface. No other channel exists: engines do not call each other, inspect each other's state, or exchange anything the object model does not represent.

## Context (reconstructed)

The platform comprises nine engines, eight of which are model-driven. Model-driven components are replaced frequently — as capability improves, as costs change, as approaches are superseded. An architecture in which replacing one engine requires understanding or modifying the others would ossify within a small number of replacement cycles.

The platform also intends to run continuously and learn. That means engine behaviour is non-stationary: an engine's output distribution changes over time. Any coupling to another engine's *behaviour*, as opposed to its *output contract*, becomes a coupling to a moving target.

A single, explicit interface surface is therefore required — one that is stable, inspectable, and independent of how any engine happens to be implemented at a given moment.

## Alternatives Considered (reconstructed)

**Option A — Intelligence Objects as the sole contract (selected).** Engines produce and consume persisted objects; no other interaction is permitted.

**Option B — Direct engine-to-engine invocation.** Engines call one another as needed.
*Rejected:* creates an N-to-N coupling graph across nine engines. Replacing any engine requires changes to every caller, so replacement cost rises with the square of engine count. It also destroys traceability — a conclusion produced through a chain of direct calls has no persisted intermediate record, breaching Principle 3.

**Option C — Shared mutable working state.** Engines read and write a common scratch space alongside persisted objects.
*Rejected:* the shared state becomes an undeclared interface that no document describes and no validation enforces. It would carry exactly the information too awkward to model as objects — which is the information most in need of scrutiny. Concurrency and lineage both become unmanageable.

**Option D — Objects as the primary contract, with permitted side channels for cross-cutting concerns** (confidence, diversity metadata, quality signals).
*Rejected, though genuinely attractive.* It would have resolved MISSING-23 (source diversity reaching Pattern Intelligence) cleanly. Rejected because a permitted side channel is a second interface surface that is undocumented, unversioned, and unenforced — and it would grow. The discipline of forcing every cross-engine need through the object model is what keeps the contract surface honest, even when that discipline is inconvenient.

## Rationale (reconstructed)

Option A makes the interface surface **finite, enumerable and inspectable**. Nine engines share exactly one contract mechanism, so the cost of replacing an engine is bounded by the object definitions it touches, not by the number of engines in the platform.

The choice has a sharp implication accepted deliberately: anything two engines need to exchange **must** be expressible as an object attribute. Where that proves awkward, the correct response is to extend the object model through a recorded decision — not to open a side channel.

## What It Binds (established)

- All nine engines.
- The nine object definitions, which are the complete inter-engine interface surface.
- Boundary Doctrine rules 2, 3 and 5.

Enables Principle 4 (Modular engines).

## Consequences Accepted (established)

- **Object definitions become the highest-stakes artefacts in the platform.** A weak object definition weakens every engine on both sides of it.
- **Object schema changes are breaking changes** affecting multiple engines simultaneously.
- **Engines cannot exchange anything the object model does not represent.** This is why unmodelled concepts are severe rather than merely inconvenient.

## Known Tensions (established)

**Decision 2 was aspirational at v1.** PKP v2 §8.4 records that the object definitions were not specified to contract standard — the decision named a contract surface that had no defined contents. This was escalated as **CONTRADICTION-08 / MISSING-68**: *a contract surface with no defined contents is not a contract.*

**Resolution.** The Intelligence Object Model specifies all nine object types across eighteen dimensions, including the universal attribute set, validation rules, integrity constraints, and the engine authority matrix. AD-02 moves from aspirational to realised on ratification of R-1 through R-8.

**Residual tension.** MISSING-23 (source diversity propagation) remains a case where an engine needs information that the object model does not naturally carry. Under AD-02 this must be resolved by extending the object model — decision pending at `T00.6.1` — and explicitly **not** by a side channel.

## Revisit Conditions

Reconsider only if:

- A demonstrated cross-engine need cannot be expressed as an object attribute without distorting the object model beyond usefulness, **or**
- The cost of object-mediated communication is shown to be prohibitive at required throughput.

Inconvenience is not grounds. The discipline is the point.
