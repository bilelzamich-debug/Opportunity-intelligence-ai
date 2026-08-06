# N-5 — Tenancy Discriminator Reserved

| Field | Value |
|---|---|
| **ID** | N-5 |
| **Title** | Tenancy Discriminator Reserved |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | — |
| **Backlog task** | `T00.3.5` |
| **Depends on** | `T00.3.1` (N-1) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

A **tenancy discriminator is reserved on every Intelligence Object** as part of the universal attribute set.

It is populated with a single default value and **carries no behaviour** in the current single-tenant scope. No access control, partitioning or filtering is implemented.

**Full access-control model is deferred**, with a **named trigger**: the first of —

1. A second tenant or organisational boundary is introduced, **or**
2. Evidence licensing requires restricting which derived conclusions may be seen by whom (M-18, `T02.1.2`), **or**
3. Platform output is exposed to consumers outside the commissioning organisation (N-1 handoff recipients beyond the immediate boundary).

On any trigger, the deferred work is `T09.2.2`.

## Context

v1 contains no security model, access control, or tenancy concept (M-55).

Whether the platform is single- or multi-tenant is genuinely unknown, because M-03 (non-goals) and M-05 (output consumers) were open until N-1. N-1 establishes advisory output to decision-makers but does not settle whether those recipients span organisational boundaries.

The structural problem: access control cannot be retrofitted onto a knowledge store without redesigning its access paths and re-partitioning existing data. Under R-1 objects are immutable, so retrofitting a discriminator means creating a new version of every object.

## Alternatives Considered

**Option A — Single-tenant, no internal access control.**
*Rejected:* simplest, but forecloses multi-tenancy without full rework. Given R-1 immutability, retrofitting would require re-versioning the entire store.

**Option B — Single-tenant with role-based access from the outset.**
*Rejected:* builds a control model against requirements that do not yet exist. Roles defined now would encode guesses about an organisational structure N-1 does not specify.

**Option C — Multi-tenant with partitioning from the outset.**
*Rejected:* highest cost, and partitioning would immediately conflict with OQ-14 (global versus partitioned Knowledge Graph). Cross-domain pattern recognition — arguably a core capability — depends on a global graph. Partitioning before it is required would forfeit that for a requirement that may never arrive.

**Option D — Defer entirely, reserve a discriminator on every object (selected).**

## Rationale

Option D is the cheapest action that preserves the expensive option.

The discriminator costs one attribute per object today. Without it, adding tenancy later means re-versioning every object under R-1 — the difference between a trivial cost now and a full-store migration later.

Crucially, reserving **does not** commit the platform to multi-tenancy. It commits only to not foreclosing it. Options B and C both build machinery against unknown requirements; Option A forecloses; Option D neither builds nor forecloses.

The **named trigger** is the essential part. A deferral without a trigger is an omission that resurfaces as an emergency. Three specific conditions are enumerated, each observable, so the deferral has a defined end.

## Why Is This Capability Intentionally Outside the Platform?

### Access control and multi-tenancy — restricting who may see what

**Why outside the platform *for now*.** This is a **deferral, not an exclusion** — the only item in F00.3 so classified, and the distinction matters.

The capability is not architecturally inappropriate; it is premature. Building it now would encode guesses about organisational structure that N-1 does not specify, and Option C's partitioning would forfeit cross-domain pattern recognition to satisfy a requirement that may never arrive.

**Why this is not scope creep when it arrives.** Because the trigger is named. When any of the three conditions occurs, `T09.2.2` is planned work with a recorded rationale — not an unbudgeted expansion. The reservation is what keeps that work proportionate.

**Scope-creep pressure to expect, in both directions.** "Add permissions now, just in case" — premature, rejected as Option B. "We'll deal with it if it happens" — that is Option A, which forecloses. The discriminator is the middle path and should be defended as such.

## What It Binds

- **Universal attribute set** (`T01.1.2`): discriminator present on all nine object types.
- **`T09.2.1`**: tenancy reservation implemented.
- **`T09.2.2`**: full access control, triggered by any of the three conditions.
- **OQ-14** (graph scope): unconstrained for now; a global graph remains available.
- **M-18** (licensing, `T02.1.2`): may activate trigger 2.

## Consequences Accepted

- **An unused attribute on every object.** Mild overhead, permanent under immutability.
- **A reserved discriminator is not access control.** It provides no protection today and must not be mistaken for it.
- **Trigger monitoring is manual.** Nothing automatically detects that a trigger condition has occurred.
- If multi-tenancy arrives, `T09.2.2` remains substantial work — the reservation reduces migration cost, not implementation cost.

## Known Tensions

**With M-55 (open).** The security model remains undefined. This decision defers it deliberately with a trigger; it does not resolve it.

**With OQ-14 (open).** If trigger 1 fires, global-graph cross-domain pattern recognition and tenant partitioning come into direct conflict, and OQ-14 must be resolved against a constraint that does not exist today.

**With N-1.** N-1 identifies output consumers but not whether they cross organisational boundaries — which is exactly trigger 3.

## Revisit Conditions

**This decision expires on its own trigger.** On any of the three named conditions, `T09.2.2` is initiated and this record is superseded by a full access-control decision.

Absent a trigger, reconsider only if the reserved discriminator proves to impose material cost — which is not anticipated, being one attribute.
