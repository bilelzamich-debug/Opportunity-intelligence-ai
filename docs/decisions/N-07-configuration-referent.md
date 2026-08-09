# N-07 — Configuration Referent: Scoped Knowledge Store Extension

| Field | Value |
|---|---|
| **ID** | N-07 |
| **Title** | Configuration Referent: Scoped Knowledge Store Extension |
| **Status** | `RATIFIED` 🔺 |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-63 |
| **Backlog task** | `T00.4.2` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md), [N-4](N-04-determinism.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

> 🔺 **ESCALATION — RATIFIED 2026-08-02 (Option E).** Approved by project owner. Option A (fourth shared component) was considered and declined in favour of the smaller deviation, subject to the isolation invariant below.

## Decision

Engine configuration is held in a **configuration store**, implemented as a **scoped extension of the Knowledge Store** rather than a fourth shared component.

Configuration records are **immutable and versioned**, following R-1. Every Intelligence Object's `engine_configuration_ref` resolves to a specific configuration version.

**Configuration records are not Intelligence Objects.** They carry no lineage, no confidence, no explanation, and never enter the lineage graph. They are platform state, not platform knowledge.

### Invariant CI-1 — Configuration Isolation

> **Configuration data is infrastructure state, not intelligence.**
>
> It may be stored inside the Knowledge Store for operational reasons, but it must remain **logically isolated** from Intelligence Objects and must **never participate in reasoning, scoring, pattern detection, or lineage.**

This invariant is the condition on which Option E was approved. It is binding and non-negotiable.

**What CI-1 prohibits, specifically:**

| Prohibited | Why |
|---|---|
| Configuration appearing in any `derives_from` chain | Would place infrastructure state in the lineage graph, breaching Principle 3's meaning and Article V |
| Any engine reasoning **from** configuration values as evidence | Configuration is not an observation of the world; treating it as one approaches the Article IV boundary |
| Configuration contributing to confidence, scoring, or support computation | Would make platform settings a determinant of how strongly a market claim is believed |
| Pattern detection over configuration records | Patterns are structures in market problems, not in platform settings |
| Configuration records being returned by Intelligence Object queries | Logical isolation must hold at the access boundary, not only by convention |

**What CI-1 permits:**

- Storage colocation within the Knowledge Store, for operational reasons only.
- `engine_configuration_ref` as an **opaque provenance pointer** on Intelligence Objects — a record of *what settings were in force*, never an input to reasoning.
- Reading configuration to **configure an engine**, which is its sole legitimate use.
- Reading configuration history for **audit and reversal** (learning rollback).

**The distinction that matters.** An object records which configuration produced it, so provenance is complete. That reference is **descriptive, never inferential**: it says how the object came to exist; it contributes nothing to what the object claims or how strongly it is believed.

## Context

Every Intelligence Object carries `engine_configuration_ref`, required by Principle 3 and made load-bearing by N-4 (reproducible inputs). No component was defined to hold engine configuration or its history (M-63).

The attribute is mandatory but has no referent. Objects persisted without a resolvable reference have permanently unreconstructable provenance — configuration state at creation time cannot be recovered afterwards.

PKP v2 records this as one of four categories of required information with no home (M-34/M-63).

## Alternatives Considered

**Option A — A fourth shared component.**
*Rejected:* cleanest conceptually, but v1 names exactly three shared components. Adding a fourth is a larger architectural change than scoping an existing one, and would require justifying why configuration is peer to the Knowledge Store rather than part of it.

**Option B — Configuration as Intelligence Objects in the Knowledge Store.**
*Rejected:* configuration is not knowledge. Making it an object would give it lineage, confidence and explanation it cannot meaningfully carry, and would place platform state inside the lineage graph — dangerously close to the Article IV boundary.

**Option C — Configuration snapshot embedded in every object.**
*Rejected:* self-contained and requires no new storage, but duplicates full configuration on every object. Under R-1 immutability this is permanent, unbounded duplication.

**Option D — Configuration held per-engine, referenced by identifier.**
*Rejected:* modular, but provides no single audit surface. Reconstructing what the platform was configured to do at a past moment would require querying nine engines, each with its own retention.

**Option E — Configuration store as a scoped Knowledge Store extension (selected).**

## Rationale

Option E is the **smallest available deviation** that gives the reference a real target.

It preserves v1's three shared components while acknowledging that the Knowledge Store's remit — "holds Intelligence Objects" — must stretch to cover platform state that objects reference. That stretch is recorded here as an escalation rather than assumed.

Keeping configuration records **outside the object model** is the essential constraint. They are immutable and versioned like objects, because reproducibility demands it, but they are not knowledge: no lineage, no confidence, no entry into the lineage graph. This preserves Article V (Intelligence Objects are the platform's only currency for *knowledge*) while giving state a home.

Option A remains the honest alternative and would be preferred if the approver considers stretching the Store's remit worse than adding a component.

## What It Binds

- **CI-1 (Configuration Isolation)** — binding invariant; enforced at the access boundary, not by convention.

- **`T01.1.6`** configuration store: immutable, versioned, resolvable at any historical point.
- **Universal attribute** `engine_configuration_ref` on every object.
- **N-4** determinism: captured configuration is what makes divergence investigable.
- **N-10** failure records: co-located with configuration as platform state.
- **`T08.2.5`** learning reversal via versioned configuration rollback.

## Consequences Accepted

- **Stretches the Knowledge Store's stated remit.** Recorded as an escalation.
- Configuration storage grows monotonically under immutability.
- Two classes of persisted data in one component — knowledge and state — with a boundary that must be enforced by discipline and documentation.

## Known Tensions

**With v1's three-component structure.** The Store now holds more than Intelligence Objects. The alternative was a fourth component; the approver should confirm which deviation is preferred.

**With AD-04 (separation of concerns).** A component holding two kinds of data is in mild tension with one-responsibility. Mitigated by the strict rule that configuration never enters the lineage graph.

## Revisit Conditions

Reconsider if the configuration store's requirements diverge materially from the Knowledge Store's — for example, if it needs different retention, access or consistency properties — in which case Option A (fourth component) becomes correct.
