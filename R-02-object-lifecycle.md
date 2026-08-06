# R-02 — Seven-State Object Lifecycle

| Field | Value |
|---|---|
| **ID** | R-02 |
| **Title** | Ratify D-02: Seven-State Object Lifecycle |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-02 |
| **Closes** | M-45, OQ-04 |
| **Backlog task** | `T00.2.2` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

All object types share one lifecycle vocabulary of seven states:

| State | Meaning | Terminal |
|---|---|---|
| `PROPOSED` | Created by an engine; not yet accepted | No |
| `ACTIVE` | Structurally valid; part of current knowledge | No |
| `SUPERSEDED` | Replaced by a newer version | Yes |
| `REJECTED` | Declined by an engine or gate; retained | Yes |
| `RETRACTED` | Withdrawn at source | Yes |
| `INVALIDATED` | An upstream dependency was retracted or invalidated | Yes |
| `ARCHIVED` | Removed from the active working set; lineage preserved | Yes |

Not every state is reachable for every type; per-type reachability is specified in IOM §3. Status transition is the sole permitted non-versioning mutation.

## Context

v1 defines no lifecycle or status model (M-45). Without one, retraction (M-09), rejection (OQ-04) and validation outcomes have no representation, and the acceptance path has no target state to transition into.

## Alternatives Considered

**Option A — Seven-state canonical vocabulary (selected).**

**Option B — Binary valid/invalid.**
*Rejected:* cannot distinguish rejection (a decision, and a learning signal under Principle 5) from invalidation (a consequence of upstream change) from retraction (an external event). These have materially different meanings for the Feedback Engine, and collapsing them destroys information the platform needs.

**Option C — Per-object-type state models.**
*Rejected:* nine vocabularies would make cross-object status reasoning impossible and violate the uniformity a contract surface requires under AD-02.

**Option D — Seven states, but discard `REJECTED` objects.**
*Rejected:* Principle 2 requires rejections to be explainable and Principle 5 requires negative outcomes as learning signal. Discarding rejected candidates means the platform cannot learn from what it declined — and declined opportunities that later prove valuable are among the most informative signals available.

## Rationale

A single shared vocabulary is required by AD-02: a contract surface with nine different status models is nine contracts.

The seven states are not arbitrary — each corresponds to a distinct cause that the platform must be able to distinguish: not yet accepted, current, replaced, declined, withdrawn externally, invalidated by upstream, and aged out. Merging any two loses a distinction the Feedback Engine or the audit path depends on.

Retaining `REJECTED` objects resolves OQ-04 toward retention, accepting the storage cost for the learning signal.

## What It Binds

- **Lifecycle state machine** (`T01.2.1`): all seven states, per-type reachability, terminal states cannot transition.
- **Status transition path** (`T01.2.2`): the sole non-versioning mutation.
- **Validation rule V9**: `status_reason` required when status is not `ACTIVE`.
- **Integrity constraints I5, I6, I8**.
- Evidence cannot reach `INVALIDATED` — having no upstream, nothing can invalidate it from above.
- **Validation objects**: a negative result is `ACTIVE`, never `REJECTED`. `REJECTED` denotes an unusable record, not an unfavourable finding.

## Consequences Accepted

- `REJECTED` objects persist, adding storage growth on top of D-01's monotonic accumulation.
- Status transition as a permitted mutation is a deliberate, narrow exception to immutability and must be tightly controlled.
- Seven states impose per-type reachability documentation on all nine object types.

## Known Tensions

**With M-31 (gate ownership, open).** `PROPOSED → REJECTED` requires a decider. For engine-internal rejection the producing engine decides; for gate rejection the owner is undefined until `T06.4.1` and `T07.3.7`.

**With M-38 (retention).** `ARCHIVED` has no trigger or owner until N-12.

**With M-58 (cascade owner).** `ACTIVE → INVALIDATED` requires cascade, unowned until N-9.

## Revisit Conditions

Reconsider only if a legitimate object state is found that none of the seven can express, or if `REJECTED` retention proves unviable at scale after N-12 tiering.
