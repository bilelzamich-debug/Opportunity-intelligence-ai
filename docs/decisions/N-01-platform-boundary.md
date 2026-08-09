# N-1 — Platform Boundary: Advisory with Structured Handoff

| Field | Value |
|---|---|
| **ID** | N-1 |
| **Title** | Platform boundary: advisory with structured handoff and mandatory outcome reporting |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution B-18; PKP v2 M-03, M-05 |
| **Closes** | M-03, M-05 |
| **Backlog task** | `T00.3.1` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

The platform is **advisory**. It produces scored, validated opportunities and solution candidates. **It does not execute.**

**Output exit point.** Platform output leaves at **Stage 7 (Validation)** — a validated Solution with its Opportunity, its lineage, its assumptions and their validation results.

**Output consumers.** Decision-makers responsible for resource allocation, who receive output through a structured handoff.

**Structured handoff.** Every handoff carries: the Opportunity with score and `score_model_version`; candidate Solutions with explicit assumptions; Validation results including negative ones; the confidence position; and traversable lineage to Evidence.

**Mandatory outcome reporting.** Outcome reporting is a **condition of the handoff**, not an optional courtesy. A recipient acting on platform output undertakes to report what happened. Outcomes re-enter as Execution Records (Stage 8).

**Consequence for C-02.** Execution occurs **outside** the platform. This confirms reading (a) of C-02: no Execution Engine is required. What remains to be assigned is *outcome intake*, resolved separately at `T08.1.1`.

## Context

v1 defines no non-goals (M-03) and does not identify who consumes output or where it exits (M-05).

The gap is load-bearing. It determines the location of C-02 — the platform's one structural break — and the difference between an analysis system and an operational one. PKP v2 records that the roadmap has no execution phase and §4 has no Execution Engine, which is consistent with execution being external, but v1 never states it.

Without this decision, P7 and P8 cannot be planned and the platform's scope is unbounded by construction.

## Alternatives Considered

**Option A — Advisory: output is scored, validated opportunities; humans decide and act.**
Clean boundary, C-02 resolves as external execution. But without an outcome path the learning loop stays open, breaching Principle 5.

**Option B — Operational: the platform initiates action.**
*Rejected:* requires an Execution Engine, which v1 does not define, and an execution phase, which the roadmap does not contain. Adding both would be a redesign. It also expands the platform from market analysis into market operation — a fundamentally different system with different risk, liability and capability requirements.

**Option C — Advisory with structured handoff and mandatory outcome reporting (selected).**
Option A's clean boundary plus a defined return path for outcomes.

**Option D — Undecided; build to the Validation boundary only.**
*Rejected:* defers the decision past the point where P7 and P8 need it, and leaves C-02 open indefinitely. Deferral is itself a scope decision, taken silently.

## Rationale

Option C matches v1's structure exactly — no Execution Engine, no execution phase — while closing the loop Principle 5 requires. It is the reading that makes v1 internally consistent.

The decisive addition over Option A is **mandatory outcome reporting**. Option A leaves the platform unable to learn: it advises, action is taken, and nothing returns. PKP v2 identifies the reporting gap and survivorship bias as dominant risks precisely because the platform does not control execution. Making reporting a *condition of the handoff* rather than a hope is the only available mitigation that does not require operational control.

Option B was rejected on scope, not capability. Executing would require the platform to hold budget, authority and liability — none of which v1 contemplates.

## Why Is This Capability Intentionally Outside the Platform?

Five capabilities are placed outside deliberately. Each is recorded with the reason, so that future proposals to absorb them are recognised as scope changes requiring a superseding decision.

### 1. Execution — acting on a recommendation

**Why outside.** Execution requires budget authority, operational control, and accountability for consequences. The platform has none of these and v1 assigns none. An advisory system that begins executing acquires liability for outcomes it cannot fully control, and the boundary between "recommended" and "did" becomes unrecoverable in the record.

**Structural evidence.** v1 defines no Execution Engine (§4) and no execution phase (§9), while defining an Execution *Record* object — the platform records what happened; it does not make it happen.

**Scope-creep pressure to expect.** "The platform already knows what to do — why not let it do it?" This is a request to change the platform's category, not to add a feature.

### 2. Decision authority — choosing which opportunity to pursue

**Why outside.** The platform scores and ranks; it does not decide. Prioritisation depends on strategy, capacity, appetite and timing that exist outside the evidence base. A score computed from market evidence cannot encode organisational context, and presenting it as a decision would overstate what the evidence supports — a Principle 1 violation at the point of highest consequence.

**Structural evidence.** PKP v2 identifies confidence inflation at the Opportunity stage as the platform's most consequential failure. Elevating a score to a decision is that failure institutionalised.

**Scope-creep pressure to expect.** "Just auto-approve anything above threshold." Handled by N-2's gate model, not by absorbing the authority.

### 3. Implementation design — how a solution is built

**Why outside.** Solution granularity stops at *concrete offering description* (M-29, `T07.2.1`). Detailed design is assigned to no engine in v1, and inventing that scope would extend the platform into product development.

**Structural evidence.** IOM §3.6 constrains the Solution object to what makes assumptions testable — no more.

**Scope-creep pressure to expect.** "The solution is too vague to act on." The correct response is validating assumptions, not deepening the design.

### 4. Market operation — running the opportunity

**Why outside.** Follows from (1). The platform observes markets; it does not participate in them. A participant cannot be a neutral observer of the same market: its own actions become part of the evidence base, and AD-05 exists precisely to prevent platform-generated content acquiring the status of external observation.

**Scope-creep pressure to expect.** "We could test the opportunity ourselves." That is execution, and its outcomes must enter as externally-acquired Evidence with full provenance.

### 5. Outcome determination — deciding whether an execution succeeded

**Why outside.** The platform records outcomes; it does not adjudicate them. Success depends on objectives held by the executing party. If the platform both predicted and judged the outcome, the learning loop would be marking its own work — the most direct route to self-reinforcement, prohibited in spirit by AD-05.

**Structural evidence.** The Execution Record's `outcome_valence` and `attribution_assessment` are *recorded*, and `outcome_verification` is required (M-47) precisely because the platform is not the arbiter.

**Scope-creep pressure to expect.** "The platform should decide if it was right." It should *measure* whether it was right against reported outcomes — a different thing.

## What It Binds

- **Pipeline:** output exits at Stage 7. Stage 8 (Execution) is external; Stage 9 (Feedback) consumes what returns.
- **C-02:** confirmed as external execution. Outcome intake assignment remains open (`T08.1.1`).
- **Validation Engine:** its output is the platform's deliverable, raising the bar on V-V5 (`scope_limitations`).
- **Execution Record:** populated from external reports, not internal observation.
- **N-2, N-3, N-5:** all depend on this boundary.

## Consequences Accepted

- **The platform depends on external parties for its only ground truth.** Reporting gap and survivorship bias are live risks, mitigated only by making reporting a handoff condition.
- **Learning is rate-limited by external reporting**, not by platform capability.
- **Outcome latency is uncontrolled.** Outcomes may arrive long after prediction, against a platform state that has since changed.
- **The platform cannot verify its own value directly** — only through reported outcomes.

## Known Tensions

**With Principle 5.** Continuous learning depends on outcomes the platform cannot compel. Mandatory reporting is contractual, not architectural; it can fail in practice.

**With M-47 (open).** Outcome verification standard undefined until `T08.1.3`.

**With C-02 (open).** This decision fixes *where* execution happens, not *which component* receives outcome reports.

## Revisit Conditions

Reconsider only if:

- Outcome reporting proves unobtainable at sufficient volume despite being a handoff condition, such that Principle 5 cannot be satisfied at all, **or**
- The organisation deliberately changes the platform's category from advisory to operational — which would require an Execution Engine, an execution phase, and re-planning P7 and P8.

**Pressure to "just act on it" is not grounds.** The five exclusions above are the platform's scope boundary; absorbing any of them requires superseding this record.
