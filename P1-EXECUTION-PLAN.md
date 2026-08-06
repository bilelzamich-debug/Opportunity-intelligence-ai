# P1 Execution Plan — Foundation

**Phase:** P1 · **Tasks:** 44 · **Status:** Authorised
**Mode:** Code first, documentation second.

---

## 1. Objectives

Build the platform's least changeable layer: the Knowledge Store, the Knowledge Graph, the object acceptance path, and baseline Orchestration.

P1 succeeds when **all nine Intelligence Object types can be persisted, validated, versioned, traversed and invalidated** according to the 37 ratified decisions — with tests proving each contract holds.

**Primary outputs are working code, passing tests, and verified contracts.** Documentation is produced only where implementation requires it.

**Non-objectives.** No engine logic (P2+). No extraction, inference or scoring. P1 builds the substrate those engines will write to.

---

## 2. Wave Plan

Dependency-ordered, per the Phase 0 Final Report. Each wave ends with tests passing.

| Wave | Tasks | Focus | Why here |
|---|---|---|---|
| **W1** | `T01.1.1`–`T01.1.3` | Identity · universal attributes | Everything references these |
| **W2** | `T01.3.1`–`T01.3.2`, `T01.1.4` | Relationship taxonomy · lineage · atomic write | **Lineage before write path** — objects are authoritative for lineage (N-6) |
| **W3** | `T01.1.5`–`T01.1.7`, `T01.5.1`, `T01.5.4` | Versioning · config store · failure store · confidence attributes | All referenced by acceptance |
| **W4** | `T01.4.1`–`T01.4.6` | Acceptance path · V1–V12 · semantic hook | **Hook built here**, S-5 Layer 1 depends on it |
| **W5** | `T01.2.1`–`T01.2.5`, `T01.3.3`–`T01.3.6`, `T01.5.2`–`T01.5.3` | Lifecycle · graph index · confidence computation | Graph rebuild **exercised**, not just built |
| **W6** | `T01.6.1`–`T01.6.5` | Baseline Orchestration | N-18 |
| **W7** | `T01.7.1`–`T01.7.9` | Nine object types, pipeline order | Each inherits prior type's rules |
| **W8** | `T01.8.1` | Exit gate | — |

---

## 3. Deliverables

| # | Deliverable | Wave |
|---|---|---|
| D1 | Identity allocator — uniqueness, retirement, version monotonicity | W1 |
| D2 | Universal object contract — 17 required + 6 optional attributes | W1 |
| D3 | Closed ten-type relationship model | W2 |
| D4 | Knowledge Store — immutable, atomic write | W2 |
| D5 | Versioning — linear supersession, one ACTIVE per lineage | W3 |
| D6 | Configuration store with CI-1 isolation | W3 |
| D7 | Failure record store, outside object model | W3 |
| D8 | Acceptance path — V1–V12, I1–I8, semantic hook | W4 |
| D9 | Seven-state lifecycle + cascade invalidation | W5 |
| D10 | Knowledge Graph — derived, rebuildable, bidirectional traversal | W5 |
| D11 | Confidence — two components, ceiling rule, support function | W5 |
| D12 | Baseline Orchestration — batch, state tracking, failure surfacing | W6 |
| D13 | Nine object types with per-type rules | W7 |
| D14 | Test suite — property-based (N-4: never equality) | All |

---

## 4. Milestones

| M | Gate | Proves |
|---|---|---|
| **M1** | End W2 | An object persists with lineage; nothing writes without references |
| **M2** | End W4 | Invalid objects are rejected at acceptance, not filtered later |
| **M3** | End W5 | **Graph rebuild demonstrated**; cascade invalidation terminates |
| **M4** | End W6 | Engines invocable in order; failures surfaced, never masked |
| **M5** | End W7 | All nine types persistable with per-type rules enforced |
| **M6** | `T01.8.1` | P1 exit criteria met |

---

## 5. Risks

| # | Risk | Response |
|---|---|---|
| R1 | **P1 oversized** (N-18 folded Orchestration in) | Wave gates; report slip at wave boundaries, do not absorb silently |
| R2 | **Graph rebuild untested** → capability rots | Exercise in W5 as a milestone, not at exit |
| R3 | **XL tasks** (`T01.3.3`, `T01.7.2`) under-decomposed | Split at execution once context is concrete |
| R4 | **Confidence ceiling correctness** subtle | Reproduce IOM §4.4 worked example (0.62→0.58) as a test |
| R5 | **Semantic hook (S-5 L1) mis-scoped** | Interface only in W4; extraction logic is P3 |
| R6 | **Immutability + retention untested at volume** | Property tests now; volume testing deferred to P2 |
| R7 | **Equality assertions creep into tests** (violates N-4) | Property-based assertions only; review each suite |

---

## 6. Definition of Done

P1 is complete when **all** hold:

**Functional**
1. All nine object types persist with the 17 universal required attributes
2. No object accepted without resolvable lineage to Evidence (V2, V3, V4)
3. Lineage traversable both directions; termination guaranteed
4. Graph rebuild from objects **demonstrated**
5. Seven-state lifecycle with per-type reachability enforced
6. Cascade invalidation terminates and is idempotent
7. Confidence ceiling enforced at acceptance; IOM §4.4 example reproduced
8. Engines invocable in pipeline order; sequencing violations rejected
9. Failures distinguishable from empty results

**Contract**
10. V1–V12 enforced at acceptance
11. I1–I8 hold continuously
12. Exactly one engine holds create authority per type
13. CI-1 verified — configuration cannot enter lineage, scoring or reasoning
14. Article IV verified — no platform artifact can become Evidence

**Quality**
15. Every acceptance criterion in all 44 tasks demonstrably met
16. Tests are property-based, never equality-based (N-4)
17. All tests pass
18. No architectural decision made in code

---

*Next: `T01.1.1` — identity allocation.*
