# R-7 — Feedback Record as the Ninth Intelligence Object

| Field | Value |
|---|---|
| **ID** | R-7 |
| **Title** | Ratify D-07: Feedback Record as the ninth Intelligence Object |
| **Status** | `RATIFIED` 🔺 |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-07; Architecture Decision Review 1 |
| **Closes** | C-03 |
| **Backlog task** | `T00.2.7` |
| **Supersedes** | — |
| **Superseded by** | — |

> 🔺 **Escalation.** This decision extends v1's object model from eight Intelligence Objects to nine. Approved by the project owner following Architecture Decision Review 1.

---

## Decision

The **Feedback Record** is ratified as the ninth Intelligence Object, as specified in IOM §3.9.

It is produced by the Feedback Engine at pipeline Stage 9, derives exclusively from Execution Records (FR-V6), and carries: motivating records, lesson statement, change target, change description, reversal procedure, `INFORMS` references, applied timestamp, and evidence of pattern.

Under AD-05, the Feedback Record is the **Learning Signal** form — the first of four permitted feedback destinations.

## Context

v1 defines a Feedback stage (§3) and a Feedback Engine (§4) but no corresponding Intelligence Object (§6). Eight of nine stage-engine pairs produce exactly one persisted object; Feedback alone produces none.

The consequence is that the Feedback Engine changes platform behaviour — scoring calibration, source trust, extraction criteria — with no persistent record of what changed, on what basis, or how to reverse it.

This is C-03, recorded at five separate points in PKP v2.

## Alternatives Considered

Five alternatives were examined in full in Architecture Decision Review 1.

**Option A — Ninth Intelligence Object (selected).** The Feedback Engine produces a persisted, evidence-linked, reversible Feedback Record.

**Option B — No feedback object (status quo).**
*Rejected:* leaves Principle 3 breached by design, not deferred. Learning becomes irreversible in practice, untraceable drift is unmitigated, and the Feedback Engine has no AD-02-compliant output channel. Rejection would itself have been an architecture decision requiring a record — a decision to violate a principle.

**Option C — Configuration history only.**
*Rejected:* captures the change but not the reasoning or the evidence. Configuration history records "weight moved from 0.4 to 0.35"; it does not record which Execution Records motivated it. Learning would not be evidence-linked, so Principle 1 would not reach the learning subsystem, and Principles 2 and 3 would have no artefact to attach to.

**Option D — Feedback as Evidence.**
*Rejected:* this is C-04, and it resolves C-03 by causing a worse contradiction. Now additionally prohibited by AD-05.

**Option E — Extend the Execution Record to carry the lesson.**
*Rejected:* cardinality mismatch. A lesson must derive from multiple Execution Records (FR-V4 requires evidence of a pattern across outcomes, precisely to prevent overfitting). One-lesson-per-record structurally forces the overfitting failure mode. Also conflates ground-truth observation with derived learning in one object, violating AD-04.

## Rationale

The addition is **required by v1's own principles**, not by new requirements:

- **Principle 3** requires that changes be traceable. Learning changes platform behaviour globally; with no artefact, they are not.
- **Principle 5**, as expanded in PKP v2 §2.5, requires learning to be traceable *and reversible*. Reversibility requires knowing what was applied.
- **AD-02** establishes that engines communicate exclusively through Intelligence Objects. The Feedback Engine must communicate; with no object it either cannot, or it uses a channel AD-02 forbids.

v1 mandated all three and omitted the artefact that satisfies them. This ratification completes v1's own logic rather than adding a feature.

The **blast radius is minimal**. The Feedback Record sits at lineage depth 9 and is a **leaf**: nothing derives from it. No existing object attribute changes, no engine loses authority, no pipeline stage moves. Of all possible ninth objects, this is the most structurally contained.

The **symmetry argument** is strong evidence of intent: eight of nine stage-engine pairs produce an object, and v1 gives no rationale for an exception at the ninth.

## What It Binds

- **Object model:** nine Intelligence Objects. Evidence, Fact, Problem, Pattern, Opportunity, Solution, Validation, Execution Record, **Feedback Record**.
- **Feedback Engine:** gains create and modify authority over the Feedback Record; gains a defined output.
- **All eight other engines:** gain read access, subject to OQ-24 (whether engines read directly or configuration is updated externally).
- **Authority matrix:** one row added. The invariant "exactly one engine holds create authority per type" is preserved.
- **Validation rules FR-V1…FR-V6 and integrity constraints FR-I1…FR-I4** become binding.
- **Backlog `T01.7.9`** (realise the Feedback Record type) is unblocked.

## Consequences Accepted

- **v1's object count changes from eight to nine.** This is a material change to a frozen document, recorded as an escalation rather than a clarification.
- One additional object type to implement, validate and maintain.
- `change_target` cannot be populated until M-02 resolves (`T08.2.1`). The object is specifiable and buildable now, but reaches full utility only at P8.
- Minor storage growth — feedback is the lowest-volume stage in the pipeline.

## Known Tensions

**With the architecture freeze.** Anyone treating "eight Intelligence Objects" as a fixed invariant will read this as a breach. The counter-position, accepted by the approver: v1 is internally inconsistent at this point, and a freeze cannot preserve an inconsistency without also preserving its consequences.

**With C-02 (unresolved).** The Feedback Record's sole permitted upstream is the Execution Record, which currently has no producing engine. R-7 is therefore ratified with a known upstream gap, scheduled for resolution at `T08.1.1`.

**With M-02 (unresolved).** `change_target` has no vocabulary until `T08.2.1`.

## Revisit Conditions

Reconsider only if:

- An alternative resolution to C-03 is identified that satisfies Principles 3 and 5 and AD-02 without a persisted object, **or**
- C-02 resolves in a way that eliminates Execution Records, removing the Feedback Record's only permitted upstream.

Implementation cost is not grounds. The object is a lineage leaf and among the least invasive additions available.
