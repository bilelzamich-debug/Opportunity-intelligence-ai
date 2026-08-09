# R-8 — Behavioural Loop Closure

| Field | Value |
|---|---|
| **ID** | R-8 |
| **Title** | Ratify D-08 + C-04 closure: objects authoritative; loop closes behaviourally |
| **Status** | `RATIFIED` 🔺 |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decisions D-08 and §4.2; Architecture Decision Review 2 |
| **Closes** | C-04 (jointly with AD-05); partially constrains C-06 |
| **Backlog task** | `T00.2.8` |
| **Supersedes** | — |
| **Superseded by** | — |

> 🔺 **Escalation.** This decision reinterprets v1's pipeline notation `Feedback -> Evidence`. Approved by the project owner following Architecture Decision Review 2.

---

## Decision

**Two parts.**

**Part 1 — Loop closure (C-04).** v1's pipeline arrow `Feedback -> Evidence` is interpreted as *"feedback causes new external Evidence to be acquired"*, **not** *"feedback becomes Evidence"*.

The loop closes **behaviourally**: a Feedback Record informs engine behaviour, which may raise a research directive, which causes the Research Engine to acquire new Evidence from external reality. The lineage graph remains acyclic.

**Part 2 — Lineage authority (D-08).** Objects carry their own lineage and are authoritative for it. The Knowledge Graph is a **derived traversal index**, rebuildable from objects at any time, and is never the authority on a relationship.

## Context

Evidence is defined by a property no platform-derived artifact can have: it originates outside the platform and has no upstream lineage. That property is what makes every lineage trace terminate at an external observation.

v1's notation asserts that feedback — which is fully derived from Execution Records, Solutions, and ultimately Evidence — becomes Evidence. PKP v2 §8.7 identifies this as **the architecture's single decision-level conflict**: the loop implementing AD-03 undermines AD-01.

PKP v2 §3.3 framed the choice: *"v1's notation states (a); the evidence-first philosophy implies (b)."* This decision selects (b).

Part 2 is included because a contract surface must be self-contained. If lineage lived only in the Graph, an object would be uninterpretable in isolation, and Store/Graph divergence would become a correctness problem rather than a performance one.

## Alternatives Considered

Five alternatives were examined in full in Architecture Decision Review 2.

**Option A — Behavioural loop closure (selected).** Feedback informs behaviour and may trigger research; Evidence remains external-only.

**Option B — Literal loop closure.** Feedback Records become Evidence, as v1's notation states.
*Rejected:* destroys the property that defines Evidence; creates lineage cycles breaking V10, backward traversal termination and cascade invalidation; enables structural self-reinforcement; makes `evidential_support` unsound. Resolves C-04 by sacrificing AD-01, the platform's strongest constraint.

**Option C — Internal Evidence as a marked subtype.**
*Rejected:* marking does not prevent lineage cycles. Creates two classes of Evidence with different rules, requiring every Evidence rule to be subtype-qualified — a wider blast radius than the reinterpretation being escalated. The subtype would be excluded from support computation and independence counting, making it Evidence in name only.

**Option D — Open the loop.** Remove the arrow; pipeline terminates at Feedback.
*Rejected:* contradicts AD-03 and Principle 5, both explicit v1 commitments. Functionally equivalent to Option A, since learning still closes the loop behaviourally — but achieves it by deleting a commitment rather than interpreting one. Strictly more invasive.

**Option E — Defer.**
*Rejected as non-viable:* `T00.4.1` (Store/Graph boundary, the critical-path P1 item) depends on this decision. Whether Evidence may have upstream lineage is a schema-level property enforced at write time and must be settled before the acceptance path is built.

## Rationale

**PKP v2 already identified (b) as the reading the architecture implies.** This ratification makes binding the interpretation the master reference records as consistent with the platform's principles.

**It resolves the conflict in favour of the stronger constraint.** PKP v2 §8.7 names AD-01 the strongest constraint in the platform. Option A preserves AD-01 fully while keeping AD-03 functional. Options B and C sacrifice AD-01 to preserve a notation.

**It changes no object definition.** Option A confirms Evidence exactly as specified and makes two existing constraints (E-I2, FR-I2) enforceable. Options B and C would require relaxing or subtyping the platform's foundational type — a materially larger change than the reinterpretation escalated here.

**The loop still closes, genuinely.** Learning changes what the platform researches; new research produces new Evidence; the cycle continues. What changes is that the cycle runs through behaviour and the external world rather than through the lineage graph — which is how a grounded learning system must work.

**Asymmetry of risk.** Rejecting Option A in favour of B or C would have accepted four Critical risks (lineage cycles, cascade failure, structural self-reinforcement, AD-01 downgraded) to preserve a diagram convention.

## What It Binds

**Part 1 — Loop closure**
- **Evidence:** E-V1 (`derives_from` empty) and E-I2 (never derives from platform-internal objects) become binding acceptance rules.
- **Feedback Record:** FR-I2 (never becomes Evidence) becomes binding.
- **Research Engine:** accepts research directives originating from feedback (`T02.2.4`, `T08.3.4`); acquisition remains external-only.
- **Orchestration:** mediates the directive path, preserving AD-04.
- **Knowledge Graph:** guaranteed acyclic; V10 and cycle guard (`T01.3.6`) implementable.

**Part 2 — Lineage authority**
- Objects carry authoritative lineage; the Graph is a derived index.
- Graph divergence is recoverable by rebuild — a performance concern, not a correctness one.
- Constrains but does not fully resolve C-06; the Store/Graph boundary is settled at `T00.4.1` (N-6).

## Consequences Accepted

- **v1's pipeline notation is reinterpreted.** The arrow remains; its meaning is fixed. This is the escalation.
- **Loop closure is no longer visible in the lineage graph.** An auditor cannot verify the cycle by traversing objects, because there deliberately is no cycle. Verification relies on `INFORMS` references and research-directive provenance. This is a genuine loss of verifiability, accepted.
- **Graph rebuild is expensive at scale.** Accepted in exchange for the guarantee that the Graph can never be the reason the platform is wrong — only the reason it is slow.
- **Self-reinforcement is not fully eliminated.** This decision closes the *lineage* path. The *behavioural* path — learning narrows research, which narrows findings — remains open. That is M-70, mitigated separately by `T08.3.1`–`T08.3.3`. **R-8 must not be read as having solved loop instability.**

## Known Tensions

**With v1's literal notation.** Unavoidable and the reason for escalation. v1's arrow is incompatible with v1's own definition of Evidence; one had to give. The notation gave, because the definition is load-bearing for AD-01, Principles 1 and 3, and the entire acceptance path.

**With C-06 (partially open).** Part 2 constrains the Store/Graph boundary but does not settle traversal responsibilities or query surface. Full resolution at `T00.4.1`.

**With M-70 (open).** Behavioural amplification is unmitigated until P8.

## Relationship to AD-05

R-8 and AD-05 jointly close C-04, at different scopes:

| | R-8 | AD-05 |
|---|---|---|
| **Scope** | The specific arrow `Feedback -> Evidence` | Any platform-generated artifact |
| **Nature** | Interpretation of v1 notation | Standing general principle |
| **Effect** | The loop closes behaviourally | No re-entry path may ever be opened |

R-8 resolves the path v1 drew. AD-05 closes the class, so that paths v1 did not draw — a Pattern re-ingested as a source, a Validation finding written back as an observation — are prohibited by default rather than permitted until noticed.

## Revisit Conditions

Reconsider only if:

- Behavioural loop closure proves insufficient to satisfy Principle 5, such that the platform demonstrably cannot learn, **or**
- The loss of graph-visible loop closure proves to obstruct a required audit obligation that `INFORMS` provenance cannot satisfy.

Preference for notational fidelity to v1 is not grounds. The notation and the Evidence definition were in conflict; this decision records which one governs.
