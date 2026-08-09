# AD-04 — Separation of Concerns

| Field | Value |
|---|---|
| **ID** | AD-04 |
| **Title** | Separation of Concerns |
| **Status** | `RECONSTRUCTED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | Unknown — predates PKP v1 |
| **Source** | PKP v1 §8 (title only); PKP v2 §8.6 (substance) |
| **Supersedes** | — |
| **Superseded by** | — |

> **Provenance warning.** v1 recorded this decision as the bare title "Separation of concerns". **Decision**, **What It Binds**, **Consequences** and **Known Tensions** are *established* from PKP v2 §8.6. **Context** and **Alternatives Considered** are *reconstructed* and are not a historical record.

---

## Decision (established)

Each engine and component has one responsibility and does not encroach on others.

One engine owns each pipeline stage transition. Knowledge, control and processing are distinct: shared components store and relate but never interpret; Orchestration sequences but never judges; engines transform but never coordinate.

## Context (reconstructed)

The pipeline is a chain of transformations in which each stage is more interpretive than the last. The characteristic failure of such a chain is **responsibility creep** — a stage that begins to do its successor's work.

The concrete hazards are specific and severe:

- If Fact Extraction judges significance, the evidence layer becomes editorialised and AD-01's grounding guarantee is compromised at its foundation.
- If Problem Intelligence proposes solutions, it pre-determines the Opportunity and Solution stages and collapses three engines into one.
- If Validation improves the solutions it tests, it loses the independence that makes validation meaningful.
- If a shared component infers relationships, those relationships enter the lineage record with no engine attributable to them, silently breaching Principle 3.

Each of these is individually plausible and locally reasonable — which is why the boundary must be architectural rather than a matter of judgement. AD-04 establishes that every failure is attributable to exactly one component.

## Alternatives Considered (reconstructed)

**Option A — Strict one-responsibility separation (selected).** Each engine owns one stage transition; boundaries stated negatively and enforced.

**Option B — Consolidated engines.** Merge related stages (Problem and Pattern; Solution and Validation) into fewer, larger engines.
*Rejected:* fewer coordination points, but it eliminates precisely the boundaries that prevent the hazards above. A merged Solution/Validation engine cannot validate independently, since it would be testing its own proposals. Note that the roadmap *does* pair Solution and Validation in phase P7 — that is a scheduling convenience, not an engine merge, and OQ-17 records the distinction.

**Option C — Capability-based decomposition.** Organise around shared capabilities (extraction, scoring, explanation) rather than pipeline stages.
*Rejected:* cross-cutting capability owners would be invoked by every stage, recreating the N-to-N coupling AD-02 exists to prevent. It also breaks the one-engine-per-stage property that makes failures attributable.

**Option D — Strict separation with an explicit coordinator owning cross-cutting decisions** (gating, promotion, prioritisation).
*Rejected at v1, and this rejection has proven costly.* It would have prevented the responsibility voids now recorded as MISSING-26, MISSING-28 and MISSING-31, where decision points fall between engines and are owned by none. It was presumably rejected because a coordinator making quality judgements is a tenth engine in all but name — but the gap is real and is now being closed piecemeal by `T06.4.1` and `T07.3.7`.

## Rationale (reconstructed)

Option A makes every failure attributable to exactly one component, which is the property that makes a nine-engine pipeline debuggable at all. It also makes AD-02 enforceable: if responsibilities overlap, the object contract between them cannot be sharply defined.

The trade is accepted knowingly — more components, more sequencing, and the standing risk that a necessary concern belongs to no one. Option D's rejection is the origin of the platform's responsibility voids, and it is worth recording that the alternative was available and declined.

## What It Binds (established)

- The nine engines.
- The three shared components.
- The Boundary Doctrine — boundaries are stated negatively (what an engine must *not* do) and name the owner of each excluded concern.

Underpins Principle 4 and makes AD-02 enforceable.

## Consequences Accepted (established)

- **More components, more sequencing overhead, higher orchestration complexity.**
- **Cross-cutting concerns have no natural home.** Confidence, scoring and explanation quality risk being implemented inconsistently in each engine.

## Known Tensions (established)

**CONTRADICTION-06.** Knowledge Store and Knowledge Graph responsibilities are not separated, violating this decision at the component level. *Resolution pending as N-6 (`T00.4.1`)* — objects authoritative, graph derived and rebuildable.

**CONTRADICTION-01.** Scoring is a cross-cutting concern with no assigned owner — the characteristic failure mode of this decision. *Resolution pending at `T06.2.5`* — internal to Opportunity Intelligence, no tenth engine.

**MISSING-26, MISSING-28, MISSING-31.** Decision points — post-validation promotion, solution selection — fall between engines and are owned by none. PKP v2 §8.6 states the general principle: *strict separation without an explicit decision-owner creates responsibility voids.* This is the direct consequence of rejecting Option D.

**CONTRADICTION-02.** The Execution stage has no owning engine — the most severe instance of a responsibility void, and the one that breaks the learning loop.

**Pattern.** Every tension against AD-04 is of the same kind: a necessary concern with no owner. Strict separation guarantees that anything unassigned is *unowned* rather than *implicitly shared*. That is the decision working as intended — the voids are visible rather than silently absorbed — but each void must be closed explicitly.

## Revisit Conditions

Reconsider only if:

- Coordination overhead demonstrably exceeds the value of attributable failure isolation, **or**
- The count of responsibility voids proves unmanageable, indicating Option D should have been selected.

Individual voids are **not** grounds for revisiting; they are grounds for assigning an owner via a recorded decision, which is how MISSING-26, MISSING-28, MISSING-31 and CONTRADICTION-02 are being closed.
