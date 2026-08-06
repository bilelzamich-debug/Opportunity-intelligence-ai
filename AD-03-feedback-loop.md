# AD-03 — Feedback Loop

| Field | Value |
|---|---|
| **ID** | AD-03 |
| **Title** | Feedback Loop |
| **Status** | `RECONSTRUCTED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | Unknown — predates PKP v1 |
| **Source** | PKP v1 §8 (title only); PKP v2 §8.5 (substance) |
| **Supersedes** | — |
| **Superseded by** | — |

> **Provenance warning.** v1 recorded this decision as the bare title "Feedback loop". **Decision**, **What It Binds**, **Consequences** and **Known Tensions** are *established* from PKP v2 §8.5. **Context** and **Alternatives Considered** are *reconstructed* and are not a historical record.
>
> **Implementability warning.** PKP v2 §8.5 states plainly: *"Decision 3 is the least implementable of the four as currently specified."* Three contradictions and one missing definition bear directly on it. This record documents the decision as made; it does not claim the decision is currently executable.

---

## Decision (established)

The pipeline closes on itself; outcomes feed back into platform behaviour.

The platform has no terminal state. Execution outcomes are captured, compared against the platform's prior predictions, and used to change future behaviour.

## Context (reconstructed)

The platform reasons about markets, and markets change. A static analysis system degrades from the day it is built: its scoring reflects conditions that no longer hold, its patterns describe structure that has dissolved, and nothing detects the drift.

More fundamentally, the platform makes **predictions** — it asserts that an opportunity carries value. Predictions are testable. A system that makes testable predictions and never checks them is discarding the only signal that could tell it whether it works at all.

Principle 5 (Continuous learning) requires improvement over time. AD-03 is the structural expression of that principle: it makes the pipeline a cycle rather than a chain, so that outcomes have a defined path back into behaviour.

## Alternatives Considered (reconstructed)

**Option A — Closed loop with outcome-driven learning (selected).** Outcomes are captured as Execution Records and drive changes to platform behaviour.

**Option B — Open pipeline; no feedback.** The platform produces validated opportunities and stops.
*Rejected:* the platform could never determine whether its output was any good, and would degrade silently as markets moved. It also abandons Principle 5 entirely, which would require removing a principle rather than merely deferring a capability.

**Option C — Feedback as reporting only.** Outcomes are captured and reported to humans, who may adjust the platform manually.
*Rejected:* PKP v2 §2.5 identifies "feedback that only produces reports" as an anti-pattern under Principle 5. It also relocates the learning loop outside the platform, where it is untraceable — the adjustment has no recorded link to the outcomes that motivated it, breaching Principle 3.

**Option D — Closed loop with unsupervised continuous adaptation.** The platform adjusts itself freely and continuously from every outcome.
*Rejected:* a closed learning loop with no bounds can amplify its own bias, converging on self-generated belief. With no stability guard (MISSING-70), no reversibility mechanism (MISSING-34), and no success measure (MISSING-04), unsupervised adaptation would make regression undiagnosable. The loop is retained; the freedom is not.

## Rationale (reconstructed)

Option A is the only alternative that satisfies Principle 5 while keeping learning **inside** the platform where it can be traced. Option C's failure is subtle but decisive: relocating learning to humans does not eliminate it, it merely makes it invisible.

Option D was rejected on risk, not on principle — the difference between A and D is bounds, reversibility and traceability, all of which are additive safeguards rather than architectural changes. This is why the Feedback Record (D-07) requires `reversal_procedure` and `evidence_of_pattern`.

## What It Binds (established)

- Pipeline topology — the pipeline is a cycle, not a chain.
- The Feedback Engine.
- The Execution Record object.
- Orchestration's control model — the platform has no terminal state.

Implements Principle 5.

## Consequences Accepted (established)

- **Platform behaviour is time-dependent and non-stationary.** Identical inputs at different times may legitimately produce different outputs.
- **Regression is possible.** Learning can make the platform worse.
- **The system has no terminal state**, so resource consumption is bounded only by explicit control.
- **Debugging becomes historical.** Current behaviour is a function of the entire outcome history.

## Known Tensions (established)

**CONTRADICTION-02.** The loop is structurally incomplete: no engine produces Execution Records, so there is a gap between Validation and Feedback. *Resolution pending at `T08.1.1`* — proposed assignment of outcome intake to the Research Engine (🔺 escalation).

**CONTRADICTION-03.** Feedback produces no persisted object, so learning changes are untraceable, breaching Principle 3. *Resolution pending as R-7 (`T00.2.7`)* — the Feedback Record as a ninth object type (🔺 escalation).

**CONTRADICTION-04.** `Feedback -> Evidence` conflicts with AD-01. PKP v2 §8.7 identifies this as the architecture's single decision-level conflict. *Resolution pending as R-8 (`T00.2.8`)* — behavioural loop closure.

**MISSING-02.** The loop has no defined target of change, so it cannot be closed even once the above are resolved. *Resolution pending at `T08.2.1`.*

**Assessment.** AD-03 is the decision least supported by the rest of v1. The loop it mandates is broken at Execution (no engine, no intake) and at Feedback (no object). Four separate resolutions are required before it is implementable — which is why the entire Phase 8 backlog is contingent on them.

## Revisit Conditions

Reconsider only if:

- Outcome data proves unobtainable at sufficient volume or reliability, rendering the loop functionally open regardless of structure, **or**
- Loop instability proves unmanageable despite the safeguards specified in `T08.3.1`–`T08.3.3`, **or**
- R-7 or R-8 is rejected without an alternative that restores traceable, non-self-reinforcing learning.

Note that **deferring** P8 is not a revisit of AD-03. The decision stands; its implementation is scheduled last by design.
