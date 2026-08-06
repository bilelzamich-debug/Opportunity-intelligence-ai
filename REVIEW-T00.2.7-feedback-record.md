# Architecture Decision Review 1
## T00.2.7 — Feedback Record as a Ninth Object Type

| Field | Value |
|---|---|
| **Review of** | Proposed decision R-7 (IOM decision D-07) |
| **Escalation** | 🔺 Extends v1's eight Intelligence Objects to nine |
| **Closes if accepted** | C-03 |
| **Status** | **REVIEW ONLY — not ratified, architecture unchanged** |
| **Decision required from** | Platform Architecture / project owner |

---

## 1. Current Problem

v1 defines a **Feedback stage** (§3, position 9 in the pipeline) and a **Feedback Engine** (§4). It defines eight Intelligence Objects (§6), none of which is a feedback artefact.

Every other stage-engine pair in the platform produces exactly one persisted object:

| Stage | Engine | Object |
|---|---|---|
| Evidence | Research | Evidence |
| Facts | Fact Extraction | Fact |
| Problems | Problem Intelligence | Problem |
| Patterns | Pattern Intelligence | Pattern |
| Opportunities | Opportunity Intelligence | Opportunity |
| Solutions | Solution Intelligence | Solution |
| Validation | Validation | Validation |
| Execution | *(none — C-02)* | Execution Record |
| **Feedback** | **Feedback** | **none — C-03** |

The Feedback Engine therefore performs work — deriving lessons from outcomes and changing platform behaviour — that leaves **no persistent record**.

This is C-03, recorded in PKP v2 §3.9 and reaffirmed at five separate points in the master reference (lines 277, 534, 893, 1233, 1369).

## 2. Why the Existing Architecture Is Insufficient

Three of v1's own commitments are violated by the absence, not by any proposed addition.

**2.1 Principle 3 (Traceable Lineage) is breached by design.**
Principle 3 requires that for any change in the platform, the derivation is reconstructable. Learning updates change engine behaviour globally — scoring calibration, source trust, extraction criteria. With no persisted artefact, it is impossible to answer: *what changed, on the basis of which outcomes, and when?* PKP v2 §4.8 names this the **untraceable drift** failure mode: accumulated small changes with no aggregate record, making regression undiagnosable.

**2.2 Principle 5 (Continuous Learning) cannot meet its own stated requirements.**
PKP v2 §2.5 states that learning changes "must themselves be traceable and reversible". Reversibility requires knowing what was applied. Without a record, a learning update cannot be reliably undone — only approximated. A learning system that cannot roll back a bad lesson is one bad lesson away from unrecoverable degradation.

**2.3 Architecture Decision AD-02 (Intelligence Contracts) has no channel for this information.**
AD-02 establishes that engines communicate *exclusively* through Intelligence Objects. The Feedback Engine must communicate its output to other engines. With no object, either the communication is impossible or it occurs through an undocumented side channel — which AD-02 explicitly forbids (Option D, rejected).

**The structural point:** this is not a missing feature. It is a hole in a pattern that v1 itself established eight times over. The insufficiency is internal to v1, and no amount of implementation discipline closes it.

## 3. Possible Alternatives

Five options, including the status quo.

### Alternative A — Specify the Feedback Record as a ninth Intelligence Object
The Feedback Engine produces a persisted `Feedback Record` carrying: motivating Execution Records, lesson statement, change target, change description, reversal procedure, and `INFORMS` references to affected engines. Derivation restricted to Execution Records only (FR-V6).

### Alternative B — No feedback object (status quo)
Accept that the Feedback stage produces no persisted artefact. Learning happens; the record does not.

### Alternative C — Feedback recorded as configuration history, not an Intelligence Object
Learning changes are captured in the configuration store (N-7, `T00.4.2`) as versioned config records, outside the object model.

### Alternative D — Feedback as Evidence
Feedback re-enters the pipeline as an Evidence object, matching v1's literal `Feedback -> Evidence` notation.

### Alternative E — Extend the Execution Record to carry the lesson
No new object; the Execution Record gains attributes for the derived lesson and applied change.

## 4. Pros and Cons

### Alternative A — Ninth Intelligence Object

**Pros**
- Closes C-03 completely; Principle 3 satisfied for learning changes.
- Restores the stage-engine-object symmetry v1 established for all eight other stages.
- Reversibility becomes structural: `reversal_procedure` is a required attribute.
- Learning is auditable — every change traces to the Execution Records that motivated it.
- Fits AD-02 exactly: the Feedback Engine communicates through an object like every other engine.
- `FR-V6` (derivation from Execution Records only) structurally prevents learning from platform inferences.
- Cumulative drift becomes determinable (`FR-I4`), mitigating the §4.8 failure mode.

**Cons**
- **Extends v1's object count from eight to nine.** This is a real change to a frozen document, not a clarification.
- Adds an object type to implement, validate and maintain (backlog `T01.7.9`).
- The object's `change_target` attribute cannot be populated until M-02 resolves (`T08.2.1`), so it is specifiable now but not fully usable until P8.
- Storage growth, though minimal — feedback volume is the lowest in the pipeline.

### Alternative B — No feedback object (status quo)

**Pros**
- v1 remains untouched; eight objects, exactly as written.
- Zero implementation cost.
- No escalation required.

**Cons**
- **Principle 3 remains breached by design** — not deferred, but permanently violated for the entire learning subsystem.
- Learning is irreversible in practice; PKP v2 §2.5's reversibility requirement cannot be met.
- Untraceable drift is unmitigated. Over time, platform behaviour diverges from baseline with no record of how.
- The Feedback Engine has no AD-02-compliant output channel, forcing either a side channel or no communication.
- Regression becomes undiagnosable — the platform gets worse and nobody can say why.
- **Does not actually avoid the decision.** It decides to violate a principle, which is itself an architecture decision requiring a record.

### Alternative C — Configuration history only

**Pros**
- No change to v1's object count.
- Configuration store already required by N-7, so the mechanism exists.
- Captures *what changed* with version history and rollback.

**Cons**
- Captures the change but **not the reasoning or the evidence**. Configuration history says "weight moved from 0.4 to 0.35"; it does not say which Execution Records motivated it or why.
- Learning would not be evidence-linked, so Principle 1 does not reach the learning subsystem.
- Config records are not Intelligence Objects, so they carry no lineage, no confidence, no explanation — the three things Principle 2 and 3 require.
- Creates a **second class of platform knowledge** outside the object model, which AD-04 (separation of concerns) would classify as a responsibility void.
- The `INFORMS` relationship has no home, so which engines were affected is unrecorded.

*Assessment: solves the mechanical problem, not the traceability problem. It records the edit, not the decision.*

### Alternative D — Feedback as Evidence

**Pros**
- Matches v1's literal pipeline notation `Feedback -> Evidence` with no reinterpretation.
- No new object type.
- Loop closes through lineage, visibly and simply.

**Cons**
- **This is C-04**, and it is the architecture's single decision-level conflict (PKP v2 §8.7).
- Grants platform-generated content the grounding status Evidence exists to guarantee, weakening AD-01 at its foundation.
- Creates lineage cycles, breaking V10 and making backward traversal non-terminating.
- Enables self-reinforcement: the platform learns from its own output as though it were external observation.
- Violates E-I2 (Evidence never derives from platform-internal objects).

*Assessment: solves C-03 by causing C-04. Strictly worse than doing nothing.*

### Alternative E — Extend the Execution Record

**Pros**
- No new object type; object count stays at eight.
- Lesson stays adjacent to the outcome that produced it.

**Cons**
- **Cardinality mismatch.** A lesson derives from *multiple* Execution Records (FR-V4 requires evidence of a pattern across outcomes, precisely to prevent overfitting). One-lesson-per-record structurally forces overfitting to single outcomes.
- Execution Records have no create authority (C-02 unresolved), so the lesson would inherit an undefined producer.
- Conflates two responsibilities in one object — ground truth observation and derived learning — which AD-04 forbids.
- The Execution Record is produced at Stage 8, the Feedback Record at Stage 9. Merging them collapses a stage boundary.

*Assessment: violates AD-04 and structurally guarantees the overfitting failure mode.*

## 5. Impact on PKP

| Document | Impact if Alternative A accepted |
|---|---|
| **PKP v1** | Object count 8 → 9. This is the material change and the reason for escalation. |
| **PKP v2 §6** | C-03 moves from open to closed. §6.4.1 stage-object alignment table gains a row; the Feedback row changes from "none" to "Feedback Record". One structural break remains (Execution, C-02). |
| **PKP v2 §3.9** | Feedback stage gains a defined exit artefact. |
| **PKP v2 §11** | Contradiction register: C-03 closed. Remaining: 4 (C-01, C-02, C-04, C-06 — of which C-04 is Review 2). |
| **IOM** | §3.9 already specifies the object in full. Ratification makes it binding rather than proposed. |
| **Blocker Resolution** | R-7 moves from DRAFT to RATIFIED. |
| **Backlog** | No task changes. `T01.7.9` (realise Feedback Record) already exists and is currently blocked on this decision. |

**No pipeline stage, engine, shared component or principle is altered.** The change is confined to the object model.

## 6. Impact on Existing Objects and Engines

### Objects

| Object | Impact |
|---|---|
| Execution Record | Becomes the sole permitted upstream of Feedback Record (FR-V6). No change to its own definition. |
| Evidence | **No change**, and specifically *not* a target — FR-I2 forbids Feedback Records becoming Evidence. |
| All other seven | **No change.** No attribute, rule or constraint is modified. |

The Feedback Record sits at lineage depth 9, deriving only from Execution Records at depth 7–8. It is a **leaf in the lineage graph** — nothing derives from it. This is why its addition is structurally contained: it extends the graph outward without altering any existing path.

### Engines

| Engine | Impact |
|---|---|
| **Feedback** | Gains a defined output object and create authority. Currently the only pipeline engine with no output type. |
| All eight others | Gain **read** access to Feedback Records (subject to OQ-24, whether engines read directly or configuration is updated externally). No change to their create or modify authority. |
| Orchestration | No change — creates no objects, reads metadata only. |

### Authority matrix

One row added: `Feedback Record | Create: Feedback | Modify: Feedback | Read: All engines`. The invariant "exactly one engine holds create authority per object type" is preserved.

## 7. Risks if Rejected

| # | Risk | Severity | Notes |
|---|---|---|---|
| 1 | **Principle 3 permanently breached for the learning subsystem** | **Critical** | Not a deferral. Rejection is a decision to operate a system whose behavioural changes are untraceable. |
| 2 | **Learning becomes irreversible in practice** | **Critical** | PKP v2 §2.5 requires reversibility. Without a record of what was applied, rollback is approximation. One bad lesson could be unrecoverable. |
| 3 | **Untraceable drift** | **High** | PKP v2 §4.8. Behaviour diverges from baseline over time with no aggregate record. Regression undiagnosable. |
| 4 | **AD-02 violated or a side channel created** | **High** | The Feedback Engine must communicate. With no object, it either cannot, or it does so through a channel AD-02 forbids. |
| 5 | **P8 becomes unimplementable as specified** | **High** | Backlog `T01.7.9`, `T08.2.2`, `T08.2.5`, `T08.2.6` all assume the object. Rejection requires re-planning nine backlog tasks. |
| 6 | **Overfitting guard lost** | **Medium** | `evidence_of_pattern` (FR-V4) lives on the object. Without it, nothing structurally requires a lesson to be supported by more than one outcome. |
| 7 | **C-03 remains open indefinitely** | **Medium** | With no alternative resolution proposed, it becomes a permanent known defect. |

**Rejection is not a neutral option.** It requires either accepting risks 1–4 explicitly, or commissioning an alternative resolution to C-03 that this review has not identified.

## 8. Recommendation

**Accept Alternative A — specify the Feedback Record as a ninth Intelligence Object.**

Reasoning, in order of weight:

1. **The addition is required by v1's own principles, not by new requirements.** Principles 3 and 5 and Decision AD-02 each independently demand a persisted, evidence-linked, reversible record of learning. v1 mandated all three and then omitted the artefact that satisfies them. Alternative A completes v1's own logic.

2. **Every alternative is worse on v1's own terms.** B breaches Principle 3 permanently. C records the edit but not the reasoning, leaving Principle 1 and 2 unmet for learning. D causes C-04, the architecture's deepest conflict. E violates AD-04 and structurally forces overfitting.

3. **The blast radius is minimal.** The Feedback Record is a lineage leaf: nothing derives from it, no existing object attribute changes, no engine loses authority, no pipeline stage moves. Of all possible ninth objects, this is the most structurally contained.

4. **The symmetry argument is strong evidence of intent.** Eight of nine stage-engine pairs produce an object. The most probable reading is that the ninth was omitted in error, not designed as an exception — v1 gives no rationale for an exception, and PKP v2 §6.4.1 records the gap as a break in an otherwise consistent pattern.

**Caveats the approver should weigh:**

- This **does** change v1's object count. Anyone treating "eight Intelligence Objects" as a fixed invariant will see this as a breach of the freeze, and that objection is legitimate on its face. The counter-argument is that v1 is internally inconsistent here, and the freeze cannot preserve an inconsistency without also preserving its consequences.
- The object is **not fully usable until M-02 resolves** (`T08.2.1`, learning target vocabulary). Ratifying now unblocks `T01.7.9` in P1 and is not wasted, but the object reaches full utility only at P8.
- This decision is **independent of Review 2**. Accepting the Feedback Record does not require accepting behavioural loop closure — though rejecting Review 2 in favour of Alternative D there would make this object's FR-I2 constraint unenforceable. The interaction is noted in Review 2 §9.

**If rejected**, the approver should direct which of the following applies: (i) accept risks 1–4 with a recorded decision that Principle 3 does not extend to learning changes, or (ii) commission an alternative resolution to C-03.
