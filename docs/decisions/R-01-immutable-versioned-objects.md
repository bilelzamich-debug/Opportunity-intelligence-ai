# R-01 — Immutable Versioned Objects

| Field | Value |
|---|---|
| **ID** | R-01 |
| **Title** | Ratify D-01 / D-01a: Immutable Versioned Objects |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-01 / D-01a |
| **Closes** | M-08 |
| **Backlog task** | `T00.2.1` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Intelligence Objects are **immutable** once created. Any change to content produces a **new version** with a new `object_id`, linked to its predecessor by `SUPERSEDES` and sharing a stable `lineage_id`.

**D-01a — Reference binding.** Lineage references bind to a **specific version**, never to a floating "current" version.

Status transitions are the sole permitted non-versioning mutation (see R-2).

## Context

v1 does not state whether objects are mutable. The gap is M-08.

The question is foundational because it determines what the Knowledge Store guarantees, whether historical predictions survive, and whether lineage means anything. It must be settled before P1 builds the write path — objects persisted under an undecided mutability model cannot be retrofitted.

## Alternatives Considered

**Option A — Immutable, versioned (selected).**

**Option B — Mutable in place.**
*Rejected:* destroys the historical record Principle 3 requires. It also makes prediction-versus-outcome comparison impossible, which Principle 5 depends on — the Feedback Engine must be able to retrieve what the platform believed at the time it believed it, not what it believes now.

**Option C — Mutable with a change log.**
*Rejected:* reconstructing prior state from a log is derivation, not record. Lineage would reference objects whose content at reference time is no longer directly recoverable, so Principle 3 would hold only as far as the log's fidelity.

**Option D — Immutable with floating references.**
*Rejected:* if a Problem's lineage repointed to the newest Fact version automatically, the Problem's justification would change without the Problem changing. An object must remain a derivation of what it was actually derived from.

## Rationale

Immutability is the only model under which Principle 3 is structurally true rather than best-effort. Every other option makes lineage a claim about the past that the past no longer supports.

D-01a matters as much as D-01. Version-specific binding means an object's justification is stable: superseding a Fact does not silently alter every Problem built on it. Whether a dependent *should* be revised is a separate judgement, recorded via `status`, not applied by reference drift.

## What It Binds

- **Knowledge Store write path** (`T01.1.4`): content immutable after acceptance; hard delete unsupported.
- **Versioning mechanism** (`T01.1.5`): linear supersession chains, no branching, exactly one `ACTIVE` version per `lineage_id` (I5).
- **Validation rule V11**: version increments by exactly 1; `lineage_id` unchanged.
- **Integrity constraints I1, I2, I3**: content immutable, identifiers never reused, references never repoint.
- All nine object types.

## Consequences Accepted

- **Storage grows monotonically.** Compounds M-38 (retention), addressed by N-12.
- Every reference must be version-specific, adding indirection.
- Supersession chains require traversal to find the current version.
- Corroboration produces version churn: under D-05, each new evidence attachment creates a new Fact version. Pattern constituent addition has the same property, mitigated by batching (`T05.1.7`).

## Known Tensions

**With storage cost.** Unbounded growth is real and is why N-12 (retention: lineage skeleton permanent, content tiered) exists. The two decisions must be read together.

**With OQ-13 (concurrency).** Non-branching supersession assumes serialised versioning per object type. Guaranteed only because a single engine holds create authority per type and interpretation is serialised under N-11.

## Revisit Conditions

Reconsider only if storage cost proves unviable **after** N-12 tiering is implemented and measured, or if a legitimate use case requires branching version history.

Convenience of in-place edit is not grounds.
