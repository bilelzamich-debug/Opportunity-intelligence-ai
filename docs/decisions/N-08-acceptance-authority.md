# N-08 — Acceptance Authority: Store Enforces, Object Model Specifies

| Field | Value |
|---|---|
| **ID** | N-08 |
| **Title** | Acceptance Authority: Store Enforces, Object Model Specifies |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-64 |
| **Backlog task** | `T00.4.3` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

The **Knowledge Store enforces** acceptance at the `PROPOSED → ACTIVE` transition. The **rule set is specified in the Intelligence Object Model**, not embedded in the Store.

Mechanism and policy are separated: the Store evaluates rules; it does not define them.

**Scope limit, stated explicitly.** The Store enforces **structural** rules only (V1–V12, I1–I8). Rules requiring semantic judgement — notably **F-V6**, that a Fact's claim is actually present in its Evidence — **cannot be enforced structurally**. These are handled by the semantic verification hook (`T01.4.6`), and their residual error rate is measured, not eliminated.

**Failed acceptance produces a failure record** (N-10), never a silent rejection.

## Context

Validation rules V1–V12 must be enforced somewhere. No component was assigned (M-64).

Engines cannot self-certify — an engine asserting its own output is valid is not a check. Shared components are specified as non-interpretive, which appears to exclude them.

Without an owner, every integrity guarantee in the object model is aspirational. Since P1 builds the write path, invalid objects would enter from the first write and the store's contents could never again be trusted without full retrospective audit.

## Alternatives Considered

**Option A — Knowledge Store enforces, rules embedded in the Store.**
*Rejected:* natural chokepoint, but embedding rules in the Store makes it a policy owner. Over time it would drift toward interpretation, violating its non-interpretive boundary.

**Option B — Orchestration Engine enforces.**
*Rejected:* has cross-engine visibility, but v1 forbids Orchestration from making quality judgements. Acceptance is a judgement about object validity.

**Option C — Each producing engine self-certifies.**
*Rejected:* no independent check. An engine with a defect certifies its own defective output.

**Option D — Store enforces; rules specified in the object model (selected).**

## Rationale

Option D keeps the Store's role **mechanical**: it evaluates a rule set it does not own. This stays within the grant PKP v2 §5.2 already gives it — structural-validity rejection at write — without making it a policy authority.

The write path is the only point every object necessarily passes through, so it is the only place enforcement can be complete.

**The scope limit is the honest part of this decision.** Structural enforcement cannot catch a hallucinated Fact: a fabricated claim with a well-formed anchor, a resolvable reference and a plausible explanation satisfies every structural rule while being false. Recording that limit here — rather than implying the acceptance path is a complete guarantee — is what makes S-5's measured error rate necessary rather than optional.

## What It Binds

- **`T01.4.1`** acceptance enforcement point at the Store.
- **`T01.4.2`–`T01.4.4`** rules V1–V12 evaluated at acceptance.
- **`T01.4.5`** integrity constraints I1–I8 as continuous invariants.
- **`T01.4.6`** semantic verification hook for rules structure cannot enforce.
- **N-10** failed acceptance produces a failure record.
- **S-5** extraction fidelity verification plugs into the hook.

## Consequences Accepted

- **Rules must be expressible structurally** to be enforced this way. Semantic rules are not, and are explicitly out of scope for the Store.
- **F-V6 is stated but not structurally enforceable.** The platform's integrity floor depends on a hook whose coverage is partial and whose residual error is measured rather than prevented.
- Rule evaluation on every write is a throughput cost on the platform's hottest path.

## Known Tensions

**With M-67 (open).** Hallucination detection remains the highest-severity unresolved gap. This decision does not close it; it provides the hook and states the limit.

**With AD-04.** A Store that evaluates rules is close to interpreting. The mechanism/policy split is what keeps it on the correct side, and must be maintained deliberately.

## Revisit Conditions

Reconsider if structural enforcement at write proves prohibitive at throughput, or if a component better placed to own acceptance emerges. Note that moving enforcement away from the write path forfeits completeness.
