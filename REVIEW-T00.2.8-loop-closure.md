# Architecture Decision Review 2
## T00.2.8 — Behavioural Loop Closure

| Field | Value |
|---|---|
| **Review of** | Proposed decision R-8 (IOM decision D-08 + C-04 closure) |
| **Escalation** | 🔺 Reinterprets v1's pipeline notation `Feedback -> Evidence` |
| **Closes if accepted** | C-04 (and constrains C-06) |
| **Status** | **REVIEW ONLY — not ratified, architecture unchanged** |
| **Decision required from** | Platform Architecture / project owner |

---

## 1. Current Problem

v1's pipeline (§3) is written as a closed loop:

```
Evidence -> Facts -> Problems -> Patterns -> Opportunities ->
Solutions -> Validation -> Execution -> Feedback -> Evidence
```

The final arrow, `Feedback -> Evidence`, states that feedback re-enters the loop **as Evidence**.

But Evidence is defined by a property that feedback cannot have. From the IOM (§3.1) and PKP v2 (§3.3): Evidence is *"the platform's contact with reality… the only stage where information enters from outside the platform"*. It is the **only object type with no upstream lineage**, and that property is definitional — it is what makes every lineage trace terminate at an external observation.

Feedback originates **inside** the platform. It is derived from Execution Records, which derive from Solutions, which derive ultimately from Evidence.

So `Feedback -> Evidence` asserts that platform-internal, fully-derived content becomes platform-grounding, underived content. This is C-04, which PKP v2 §8.7 identifies as **the single decision-level conflict in the architecture**: the loop implementing AD-03 (Feedback Loop) undermines AD-01 (Evidence-First).

PKP v2 §3.3 frames the choice precisely:

> Either **(a)** internally-generated Evidence is a legitimate subtype, in which case Principle 1's grounding guarantee weakens and circular self-reinforcement becomes structurally possible, or **(b)** feedback enters the loop by causing new external research rather than by becoming Evidence directly. **v1's notation states (a); the evidence-first philosophy implies (b).**

## 2. Why the Existing Architecture Is Insufficient

The architecture as written cannot be implemented, because two of its own rules are in direct opposition.

**2.1 The two readings are mutually exclusive and both are load-bearing.**
Reading (a) is what the pipeline notation literally says. Reading (b) is what AD-01, Principle 1, and the definition of Evidence require. An implementer must choose; there is no construction satisfying both.

**2.2 Reading (a) makes the lineage graph cyclic.**
If a Feedback Record becomes Evidence, and that Evidence produces Facts → Problems → … → Execution Records → Feedback Records, the lineage graph contains a cycle. This breaks:
- **V10** (no lineage cycle may be introduced) — an acceptance rule.
- **Backward traversal termination** — Principle 3 requires every object to reach Evidence in bounded effort; a cycle makes traversal non-terminating for every object in it.
- **Cascade invalidation** (I6, `T01.2.3`) — forward traversal over a cyclic graph cannot terminate.

**2.3 Reading (a) enables structural self-reinforcement.**
This is the substantive risk, not merely a formal one. If platform output re-enters as Evidence, the platform can:
- treat its own prior conclusions as independent external corroboration,
- inflate `independent_source_count` with self-generated content,
- and therefore raise `evidential_support` on the basis of its own beliefs.

PKP v2 §4.8 names this **loop instability**: *"learning amplifying its own bias across successive cycles… structurally enabled by CONTRADICTION-04"*. The failure is progressive and hard to detect: the platform becomes more confident while becoming less grounded.

**2.4 The gap is not closable by implementation discipline.**
An implementer cannot "be careful" here. Either Evidence may have upstream lineage or it may not — that is a schema-level property enforced at write time (E-V1, E-I2). It must be decided before P1 builds the acceptance path.

## 3. Possible Alternatives

### Alternative A — Behavioural loop closure (reading (b))
Feedback informs engine behaviour via `INFORMS` and may raise a **research directive**. The Research Engine then acquires **new external Evidence**. The loop closes through platform behaviour, not through lineage. Enforced by E-I2 (Evidence never derives from platform-internal objects) and FR-I2 (Feedback Record never becomes Evidence).

### Alternative B — Literal loop closure (reading (a))
Feedback Records become Evidence objects directly, exactly as v1's notation states.

### Alternative C — Internal Evidence as a distinct subtype
Introduce a marked subtype — internally-originated Evidence — permitted upstream lineage, excluded from independence counting and from `evidential_support` computation.

### Alternative D — Open the loop
Remove `Feedback -> Evidence`. The pipeline becomes a chain terminating at Feedback. Learning still changes behaviour but the pipeline is not described as a cycle.

### Alternative E — Defer
Leave C-04 open; build P1 without deciding, and resolve before P8.

## 4. Pros and Cons

### Alternative A — Behavioural loop closure

**Pros**
- **Preserves AD-01 completely.** Every lineage trace still terminates at external observation.
- **Lineage graph stays acyclic.** V10 holds, traversal terminates, cascade invalidation works.
- **Self-reinforcement through lineage becomes structurally impossible** — not merely discouraged.
- The loop still closes: learning genuinely influences what the platform researches next.
- Consistent with how the loop must work in practice — a lesson about the world is acted on by *looking at the world again*, not by treating the lesson as an observation.
- Already enforced by constraints specified in the IOM (E-I2, FR-I2); no new mechanism needed.

**Cons**
- **Reinterprets v1's explicit notation.** `Feedback -> Evidence` is read as "feedback causes new Evidence to be acquired" rather than "feedback becomes Evidence". This is the escalation.
- The loop is no longer visible in the lineage graph — closure is behavioural and therefore less obviously verifiable. An auditor cannot see the cycle by traversing objects.
- Requires the Research Engine to accept directives from feedback (`T02.2.4`, `T08.3.4`), a coupling that must be mediated through Orchestration to respect AD-04.
- **Does not eliminate self-reinforcement entirely.** Behavioural amplification remains possible: learning narrows what is researched, which narrows what is found. This is M-70, mitigated separately by `T08.3.1`–`T08.3.3` (magnitude bounds, diversity floors, held-out evaluation).

### Alternative B — Literal loop closure

**Pros**
- **Faithful to v1 as written.** No reinterpretation, no escalation.
- Loop closure is visible and verifiable in the lineage graph.
- Conceptually simple: one uniform Evidence type.

**Cons**
- **Destroys the property that defines Evidence.** If Evidence may have upstream lineage, it is no longer a grounding layer, and AD-01's guarantee becomes conditional.
- **Creates lineage cycles**, breaking V10, backward traversal termination, and cascade invalidation. These are not edge cases — they are core P1 mechanisms.
- **Enables self-reinforcement structurally.** The platform can corroborate itself with itself.
- Violates E-I2 and FR-I2 as specified in the IOM.
- Makes `evidential_support` unsound: independent source counts could include platform-generated content.
- **Resolves C-04 by sacrificing AD-01**, which PKP v2 identifies as the strongest constraint in the platform.

### Alternative C — Internal Evidence subtype

**Pros**
- Honours the literal notation — feedback does become a form of Evidence.
- Marking permits exclusion from independence counting, containing the corroboration risk.
- Loop closure remains visible in the graph.

**Cons**
- **Still creates lineage cycles.** Marking the subtype does not make traversal terminate.
- Two classes of Evidence with different rules is a **significant object model change** — larger than the ninth object in Review 1, because it modifies the definition of an existing, foundational type.
- Every rule referencing Evidence must now specify which subtype it means: E-V1, E-I2, V2, V4, the support function, independence assessment. This is a wide blast radius.
- The subtype is excluded from support computation and independence counting — so it carries none of the properties that make Evidence useful. It is Evidence in name only, which suggests the classification is wrong.
- Adds complexity to the platform's most foundational type to preserve a notation.

### Alternative D — Open the loop

**Pros**
- No contradiction: if there is no `Feedback -> Evidence` arrow, C-04 disappears.
- Lineage stays acyclic.
- Simplest possible resolution.

**Cons**
- **Contradicts AD-03 (Feedback Loop) and Principle 5.** v1 explicitly commits to a closed loop; removing it is a larger architectural change than either A or B.
- Learning would still occur (via `INFORMS`), so the loop closes behaviourally anyway — meaning this is Alternative A with the pipeline diagram edited to hide it.
- Loses the architectural statement that the platform has no terminal state.

*Assessment: functionally equivalent to A, but achieves it by deleting a v1 commitment rather than interpreting one. Strictly more invasive.*

### Alternative E — Defer

**Pros**
- No decision now; more information available later.
- Avoids the escalation in the near term.

**Cons**
- **Blocks P1.** `T00.4.1` (Store/Graph boundary, the critical-path item) depends on `T00.2.8`. Deferring stops the foundation.
- Evidence's schema-level property — whether upstream lineage is permitted — must be decided before the acceptance path is built (`T01.4.1`, `T01.7.1`).
- Cycle prevention (`T01.3.6`) cannot be implemented without knowing whether cycles are legal.
- **Deferring past P1 means retrofitting the answer into the least changeable layer**, which is exactly what Phase 0 exists to prevent.

*Assessment: not viable. C-04 is a P1 blocker, not a P8 one.*

## 5. Impact on PKP

| Document | Impact if Alternative A accepted |
|---|---|
| **PKP v1 §3** | Pipeline notation `Feedback -> Evidence` is **reinterpreted**, not rewritten: read as "feedback causes new external Evidence to be acquired". The arrow remains; its meaning is fixed. This is the escalation. |
| **PKP v2 §3.3** | C-04 resolved toward reading (b), the reading v2 itself identifies as implied by the evidence-first philosophy. |
| **PKP v2 §8.3 / §8.5 / §8.7** | The AD-01 vs AD-03 conflict — the architecture's only decision-level conflict — is resolved in favour of AD-01. AD-03 is preserved, closing behaviourally. |
| **PKP v2 §11** | C-04 closed. Remaining: C-01, C-02, C-06 (assuming C-03 closed by Review 1). |
| **IOM §3.1, §3.9, §4.2** | E-I2 and FR-I2 become binding. §4.2 loop diagram becomes normative. |
| **Backlog** | Unblocks `T00.4.1` (critical path). No task changes; `T08.3.4` already implements behavioural closure. |

**No engine, object, shared component or principle is altered.** One notation is given a fixed interpretation.

## 6. Impact on Existing Objects and Engines

### Objects

| Object | Impact |
|---|---|
| **Evidence** | Its defining property is **confirmed and enforced**, not changed. E-V1 (`derives_from` empty) and E-I2 (never derives from platform-internal objects) become binding acceptance rules. No attribute added or removed. |
| **Feedback Record** | FR-I2 becomes binding: never becomes Evidence. Its `INFORMS` relationship targets engine behaviour, explicitly outside the lineage graph. |
| All other seven | **No change.** |

The key point: Alternative A **changes no object definition**. It confirms the definitions already specified and makes two integrity constraints enforceable. Alternative B, by contrast, would require relaxing E-V1 — a change to the platform's foundational type.

### Engines

| Engine | Impact |
|---|---|
| **Research** | Accepts research directives originating from feedback (`T02.2.4`). Acquisition remains external-only; the directive influences *what* is acquired, never *what counts as* Evidence. |
| **Feedback** | Output is `INFORMS` to engine behaviour plus optional research directives — never an Evidence write. Holds no create authority over Evidence. |
| Orchestration | Mediates the directive path, preserving AD-04 (no direct engine-to-engine coupling). |
| All others | **No change.** |

### Knowledge components

| Component | Impact |
|---|---|
| Knowledge Graph | Guaranteed acyclic. Backward and forward traversal terminate. Cycle guard (`T01.3.6`) is implementable. |
| Knowledge Store | E-V1 and E-I2 enforceable at write time. |

## 7. Risks if Rejected

Rejection means selecting B, C, D or E instead.

| # | Risk | Severity | Applies to |
|---|---|---|---|
| 1 | **Lineage cycles become legal** — V10 void, backward traversal non-terminating, Principle 3 unenforceable for any object in a cycle | **Critical** | B, C |
| 2 | **Cascade invalidation cannot terminate** — I6 unenforceable, retracted Evidence may not fully propagate | **Critical** | B, C |
| 3 | **Structural self-reinforcement** — platform corroborates itself with its own output; confidence rises while grounding falls | **Critical** | B (C partially mitigated by marking) |
| 4 | **AD-01 downgraded from guarantee to convention** — the platform's strongest constraint becomes conditional | **Critical** | B, C |
| 5 | **`evidential_support` becomes unsound** — independent source counts may include platform-generated content | **High** | B |
| 6 | **P1 blocked** — `T00.4.1` cannot proceed; foundation stalls | **Critical** | E |
| 7 | **Answer retrofitted into the least changeable layer** | **High** | E |
| 8 | **AD-03 and Principle 5 contradicted** — closed loop is a v1 commitment | **High** | D |
| 9 | **Wide object model blast radius** — every Evidence rule must be subtype-qualified | **High** | C |

**The asymmetry is decisive.** Rejecting Alternative A in favour of B or C accepts four Critical risks to preserve a notation. Accepting A costs one reinterpretation and leaves one residual risk (behavioural amplification, M-70) that is already scheduled for mitigation.

## 8. Recommendation

**Accept Alternative A — behavioural loop closure.**

Reasoning, in order of weight:

1. **v2 already identifies (b) as the reading the architecture implies.** PKP v2 §3.3 states plainly: *"v1's notation states (a); the evidence-first philosophy implies (b)."* This is not a new interpretation — it is the one the master reference records as consistent with the platform's principles. The escalation is to make it binding.

2. **It resolves the conflict in favour of the stronger constraint.** PKP v2 §8.7 identifies AD-01 vs AD-03 as the architecture's only decision-level conflict and AD-01 as *"the strongest constraint in the platform"*. Alternative A preserves AD-01 fully while keeping AD-03 functional. B and C sacrifice AD-01 to preserve a notation.

3. **It changes no object definition.** Alternative A confirms Evidence as already specified and makes two existing constraints enforceable. Alternatives B and C both require relaxing or subtyping the platform's foundational object — a materially larger change than the reinterpretation being escalated.

4. **The loop still closes, genuinely.** This is not the loop being abandoned. Learning changes what the platform researches; new research produces new Evidence; the cycle continues. What changes is that the cycle runs through **behaviour and the external world**, not through the lineage graph — which is how a grounded learning system must work.

**Caveats the approver should weigh:**

- **The escalation is real.** v1's arrow says one thing; this reads it as another. The honest framing is: v1's notation is incompatible with v1's own definition of Evidence, and one of them must give. This recommends the notation gives, because the definition is load-bearing for AD-01, Principle 1, Principle 3, and the entire acceptance path.
- **Loop closure becomes less visible.** An auditor cannot verify the cycle by traversing objects, because the closure is behavioural. Mitigated by the Feedback Record's `INFORMS` references and research-directive provenance (`T08.3.4`), but it is a genuine loss of verifiability.
- **Self-reinforcement is not fully eliminated.** Alternative A closes the *lineage* path. The *behavioural* path — learning narrows research, which narrows findings — remains open. This is M-70 and depends on `T08.3.1`–`T08.3.3` being implemented properly. **Accepting A should not be read as having solved loop instability.**

**Interaction with Review 1.** The two decisions are separable but not independent:
- Accepting both is coherent — FR-I2 (Feedback Record never becomes Evidence) enforces this decision.
- Accepting Review 1 and rejecting this one in favour of **B** would put the Feedback Record's FR-I2 constraint in direct conflict with the ratified loop model; FR-I2 would have to be struck.
- Rejecting Review 1 and accepting this one is coherent: the loop closes behaviourally regardless of whether a Feedback Record exists, though learning would remain untraceable (Review 1 risks 1–4).

**If rejected**, the approver should specify which alternative replaces it and accept the corresponding Critical risks in a recorded decision — noting that Alternative E (defer) is not viable, as C-04 blocks `T00.4.1` and therefore all of P1.
