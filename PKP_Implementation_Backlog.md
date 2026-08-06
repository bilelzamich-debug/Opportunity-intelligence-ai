# Opportunity Intelligence Platform
## Implementation Backlog — Master Execution Plan

**Document type:** Implementation backlog / execution roadmap  
**Role:** Technical Program Manager  
**Derived from:** PKP v2 Master Reference · Intelligence Object Model · Pre-P1 Blocker Resolution  
**Status:** Ready for execution. Phase 0 gates all build work.

---

## 0. How To Execute This Backlog

### 0.1 Scope

**10 epics · 42 features · 182 tasks** across ten phases.

Every task is written so an AI coding agent can execute it without architectural judgement. Where a task would require a decision, that decision has been pulled forward into Phase 0 and the task depends on it. **No task in Phases 1–8 requires designing anything.**

### 0.2 Execution Rules

1. **Never start a task whose dependencies are incomplete.** The dependency graph is validated acyclic; violating it means building against an undefined contract.
2. **Never redesign.** If a task appears to need an architectural decision, stop and escalate. The decision was either missed in Phase 0 or the task is misread.
3. **Acceptance criteria are binding.** A task is done when every criterion is demonstrably met, not when the deliverable exists.
4. **Phase exit tasks are gates.** They are marked non-independent and must be the last task in their phase.
5. **Escalations require sign-off.** Four tasks extend v1's architecture and are marked ESCALATION. They must not be self-approved.

### 0.3 Field Definitions

| Field | Meaning |
|---|---|
| **ID** | Stable identifier `Tphase.feature.seq` |
| **Depends on** | Tasks that must be complete first. Validated acyclic. |
| **Complexity** | XS (trivial) · S (small) · M (moderate) · L (large) · XL (substantial, consider splitting on execution) |
| **Deliverable** | The artefact produced |
| **Acceptance criteria** | Binding conditions for completion |
| **Blocks** | Tasks that cannot start until this completes |
| **Independent** | Yes = can be picked up standalone once dependencies are met. No = a gate or coupled task. |

### 0.4 Validation Performed

The dependency graph was machine-checked. Results:

| Check | Result |
|---|---|
| Duplicate task IDs | None |
| Dangling dependencies | None |
| Dependency cycles | None |
| Forward phase dependencies | None |
| Tasks missing acceptance criteria | None |
| Tasks missing deliverable | None |
| Critical path length | 76 tasks |

One defect was found and corrected during validation: `T01.2.4` originally depended on `T03.1.4` (a Phase 3 task), which would have deadlocked Phase 1. The task was rewritten as a type-agnostic object-layer rule with the Fact-specific behaviour following from it.

---

## 1. Backlog Summary

### 1.1 Distribution by Phase

| Phase | Epic | Tasks | XS | S | M | L | XL |
|---|---|---:|---:|---:|---:|---:|---:|
| Phase 0 — Decision Closure | E00 | 36 | 2 | 7 | 15 | 7 | 5 |
| Phase 1 — Foundation | E01 | 44 | 0 | 1 | 17 | 24 | 2 |
| Phase 2 — Research Engine | E02 | 10 | 0 | 1 | 5 | 4 | 0 |
| Phase 3 — Fact Extraction | E03 | 10 | 0 | 0 | 4 | 5 | 1 |
| Phase 4 — Problem Intelligence | E04 | 7 | 0 | 0 | 3 | 4 | 0 |
| Phase 5 — Pattern Intelligence | E05 | 10 | 0 | 0 | 2 | 6 | 2 |
| Phase 6 — Opportunity Intelligence | E06 | 17 | 0 | 3 | 7 | 6 | 1 |
| Phase 7 — Solution & Validation | E07 | 20 | 0 | 0 | 10 | 7 | 3 |
| Phase 8 — Feedback | E08 | 20 | 0 | 0 | 4 | 13 | 3 |
| Cross-Cutting | E09 | 8 | 0 | 1 | 3 | 4 | 0 |
| **Total** | | **182** | **2** | **13** | **70** | **80** | **17** |

### 1.2 Critical Path

The longest dependency chain is **76 tasks**, running from decision-register setup to the Phase 8 exit gate. Every task on it is marked ⚠ in the detail sections. Delay on any of them delays the platform.

```
  T00.1.1 → T00.1.3 → T00.2.1 → T00.4.1 → T00.4.2 → T00.4.5
  T00.6.2 → T00.6.3 → T00.7.1 → T01.1.1 → T01.1.2 → T01.3.1
  T01.3.2 → T01.3.3 → T01.3.4 → T01.4.2 → T01.4.3 → T01.4.4
  T01.4.5 → T01.7.1 → T01.7.2 → T01.7.3 → T01.7.4 → T01.7.5
  T01.7.6 → T01.7.7 → T01.7.8 → T01.7.9 → T01.8.1 → T02.1.1
  T02.1.2 → T02.2.1 → T02.2.2 → T02.2.3 → T02.3.1 → T03.1.1
  T03.1.3 → T03.2.1 → T03.2.2 → T03.2.3 → T03.3.1 → T04.1.1
  T04.1.4 → T04.1.5 → T04.2.1 → T05.1.1 → T05.1.4 → T05.1.5
  T05.3.1 → T06.1.1 → T06.1.2 → T06.2.1 → T06.2.3 → T06.3.1
  T06.3.2 → T06.4.1 → T06.4.3 → T06.5.1 → T07.1.1 → T07.1.2
  T07.1.5 → T07.3.1 → T07.3.3 → T07.3.7 → T07.4.1 → T08.1.1
  T08.1.2 → T08.1.5 → T08.2.1 → T08.2.2 → T08.2.4 → T08.3.1
  T08.3.2 → T08.3.3 → T08.3.5 → T08.4.1
```

### 1.3 Parallelisation

**173 of 182 tasks (95%) are independently executable** once their dependencies are met. The 9 non-independent tasks are phase exit gates.

Highest-fanout tasks — completing these unblocks the most downstream work:

| Task | Unblocks | Description |
|---|---:|---|
| `T00.1.3` | 11 | Define the decision-record template: context, alternatives considered, decision, rationa… |
| `T00.4.1` | 10 | Decide Store/Graph boundary and consistency: objects authoritative and atomically writte… |
| `T01.1.2` | 7 | Implement the universal required attribute set (17 attributes from IOM §1.1) as the base… |
| `T00.3.1` | 5 | Decide platform boundary: advisory with structured handoff and mandatory outcome reporti… |
| `T01.3.4` | 5 | Implement backward traversal (object to Evidence) with guaranteed termination.… |
| `T01.6.1` | 5 | Implement scheduled batch invocation per N-11 and the M-35 control model.… |
| `T05.1.1` | 5 | Implement cross-problem comparison over the accumulated Problem population.… |
| `T07.3.1` | 5 | Implement claim-level validation targeting individual assumptions (V-V1).… |

### 1.4 Escalations

Four tasks extend v1's architecture and require explicit sign-off before execution:

| Task | Extension | Alternative rejected |
|---|---|---|
| `T00.2.7` | Feedback Record as a ninth object type | Leaving Principle 3 breached by design |
| `T00.2.8` | Behavioural loop closure reinterprets v1's pipeline notation | Lineage cycles and compromised grounding |
| `T00.4.2` | Configuration store as a scoped Knowledge Store extension | A fourth shared component |
| `T08.1.1` | Outcome intake assigned to the Research Engine | A tenth engine |

---

## 2. Detailed Backlog

# Phase 0 — Decision Closure

## Epic E00 — Governance & Decision Closure

**Goal.** Close the 22 minimum decisions and establish the decision-record mechanism. No build work may start until this epic completes.

### Feature F00.1 — Decision Infrastructure

#### `T00.1.1` ⚠

Establish the architecture decision register: one row per decision with ID, status, owner, date, linked full record. Seed with v1's four original decisions (Evidence-first, Intelligence contracts, Feedback loop, Separation of concerns) reconstructed retrospectively.

| | |
|---|---|
| **Depends on** | — (no prerequisites) |
| **Complexity** | S |
| **Deliverable** | Decision register document + 4 seeded retrospective records |
| **Blocks** | `T00.1.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Register exists with defined columns
- v1's four decisions each have context, alternatives, rationale, consequences
- Register is referenced as the single source of decision truth

#### `T00.1.2`

Publish the marker identifier crosswalk from Blocker Resolution §0.2 as the canonical mapping. Renumber all IOM marker references to canonical v2 IDs.

| | |
|---|---|
| **Depends on** | — (no prerequisites) |
| **Complexity** | S |
| **Deliverable** | Canonical crosswalk table + corrected IOM reference list |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- All 8 identified collisions mapped
- Every IOM marker reference resolves to a canonical ID
- No marker ID refers to two different gaps

#### `T00.1.3` ⚠

Define the decision-record template: context, alternatives considered, decision, rationale, consequences accepted, revisit conditions.

| | |
|---|---|
| **Depends on** | `T00.1.1` |
| **Complexity** | XS |
| **Deliverable** | Decision record template |
| **Blocks** | `T00.2.1`, `T00.2.2`, `T00.2.3`, `T00.2.4`, `T00.2.5`, `T00.2.6`, `T00.2.7`, `T00.2.8`, `T00.3.1`, `T00.3.4`, `T00.5.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Template covers all six fields
- Applied to at least one worked example

### Feature F00.2 — Ratify IOM Decisions D-01…D-08 (R-1…R-8)

#### `T00.2.1` ⚠

Ratify D-01/D-01a: objects immutable, versioned; lineage references bind to specific versions.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | S |
| **Deliverable** | Decision record R-1 |
| **Blocks** | `T00.4.1`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Immutability confirmed or amended
- Version-specific binding confirmed
- Consequences for storage growth acknowledged

#### `T00.2.2`

Ratify D-02: seven-state lifecycle (PROPOSED/ACTIVE/SUPERSEDED/REJECTED/RETRACTED/INVALIDATED/ARCHIVED).

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | S |
| **Deliverable** | Decision record R-2 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- All seven states confirmed
- Per-type reachability confirmed
- Rejected-retention consequence accepted

#### `T00.2.3`

Ratify D-03: two-component confidence with monotonic ceiling rule.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | M |
| **Deliverable** | Decision record R-3 |
| **Blocks** | `T00.5.1`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Both components confirmed
- Ceiling rule confirmed as min()
- Band definitions confirmed

#### `T00.2.4`

Ratify D-04: explicit temporal validity, no automatic decay.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | XS |
| **Deliverable** | Decision record R-4 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- asserted_at/observed_at/valid_until confirmed
- No-decay position confirmed

#### `T00.2.5`

Ratify D-05: Facts are canonical claims with multiple evidence attachments.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | M |
| **Deliverable** | Decision record R-5 |
| **Blocks** | `T00.5.3`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Canonical-claim model confirmed
- Attachment structure confirmed
- Version-churn consequence accepted

#### `T00.2.6`

Ratify D-06: closed ten-type relationship taxonomy.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | S |
| **Deliverable** | Decision record R-6 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- All ten types confirmed
- Closed-set rule confirmed
- DERIVES_FROM vs SUPPORTS distinction confirmed

#### `T00.2.7` 🔺 **ESCALATION**

Ratify D-07: Feedback Record as ninth object type. ESCALATION: extends v1's eight object types.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | M |
| **Deliverable** | Decision record R-7 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Ninth type accepted or rejected
- If rejected, alternative mechanism for traceable learning specified
- Principle 3 compliance demonstrated either way

#### `T00.2.8` 🔺 **ESCALATION**

Ratify D-08 + C-04 closure: objects authoritative for lineage; feedback closes the loop behaviourally, never becoming Evidence. ESCALATION: reinterprets v1's pipeline notation.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | L |
| **Deliverable** | Decision record R-8 |
| **Blocks** | `T00.4.1`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Behavioural loop closure accepted or rejected
- Lineage acyclicity guarantee confirmed
- E-I2 (no internal content as Evidence) confirmed

### Feature F00.3 — Scope & Boundary Decisions (N-1…N-5)

#### `T00.3.1`

Decide platform boundary: advisory with structured handoff and mandatory outcome reporting. Resolves M-03 non-goals and M-05 output consumers; determines C-02.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | L |
| **Deliverable** | Decision record N-1 + non-goals statement |
| **Blocks** | `T00.3.2`, `T00.3.3`, `T00.3.5`, `T00.7.1`, `T08.1.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Advisory vs operational settled
- Non-goals enumerated
- Output consumers identified
- Exit stage of platform output stated

#### `T00.3.2`

Decide human role: gates at exactly three transitions (opportunity selection, post-validation promotion, learning application).

| | |
|---|---|
| **Depends on** | `T00.3.1` |
| **Complexity** | M |
| **Deliverable** | Decision record N-2 |
| **Blocks** | `T00.7.1`, `T06.4.1`, `T07.3.7`, `T08.2.8` |
| **Independent** | Yes |

**Acceptance criteria**

- Gate count and locations fixed
- Whether gates require new object states determined
- Unbounded-wait behaviour specified

#### `T00.3.3`

Define success criteria: stage-level proxy measures now, outcome measures fixed now for later use.

| | |
|---|---|
| **Depends on** | `T00.3.1` |
| **Complexity** | L |
| **Deliverable** | Decision record N-3 + measures catalogue |
| **Blocks** | `T00.7.1`, `T03.2.3`, `T09.1.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Proxy measure defined per pipeline stage
- Outcome measures defined and frozen
- Measures traceable to vision commitments

#### `T00.3.4`

Decide determinism posture: reproducible inputs, non-deterministic outputs.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | M |
| **Deliverable** | Decision record N-4 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Capture requirements enumerated (model version, config, input snapshot)
- Replay expectations stated
- Regression-testing implications accepted

#### `T00.3.5`

Decide tenancy: reserve a tenancy discriminator on every object pending scope resolution.

| | |
|---|---|
| **Depends on** | `T00.3.1` |
| **Complexity** | S |
| **Deliverable** | Decision record N-5 |
| **Blocks** | `T00.7.1`, `T09.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Discriminator reserved on universal attribute set
- Full access-control model deferred with a named trigger

### Feature F00.4 — Knowledge Foundation Decisions (N-6…N-12)

#### `T00.4.1` ⚠

Decide Store/Graph boundary and consistency: objects authoritative and atomically written; graph derived, rebuildable. CRITICAL PATH — blocks all P1 build work.

| | |
|---|---|
| **Depends on** | `T00.2.1`, `T00.2.8` |
| **Complexity** | XL |
| **Deliverable** | Decision record N-6 |
| **Blocks** | `T00.4.2`, `T00.4.3`, `T00.4.4`, `T00.4.6`, `T00.4.7`, `T00.4.8`, `T00.5.7`, `T00.6.1`, `T00.6.4`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Authority settled
- Atomicity of object write settled
- Graph rebuild guarantee stated
- Divergence classified as performance not correctness

#### `T00.4.2` ⚠ 🔺 **ESCALATION**

Decide configuration referent: configuration store as scoped Knowledge Store extension. ESCALATION: stretches Store remit.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | M |
| **Deliverable** | Decision record N-7 |
| **Blocks** | `T00.4.5`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Home for engine_configuration_ref defined
- Immutability and versioning of config records confirmed
- Deviation from v1's three components recorded

#### `T00.4.3`

Decide acceptance authority: Knowledge Store enforces at write; rule set specified in the object model, not the Store.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | L |
| **Deliverable** | Decision record N-8 |
| **Blocks** | `T00.4.4`, `T00.5.5`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Enforcement point named
- Mechanism/policy separation confirmed
- Limits acknowledged: semantic rules (F-V6) not structurally enforceable

#### `T00.4.4`

Decide cascade invalidation: mechanical integrity operation over lineage, invoked by Orchestration, performing no interpretation.

| | |
|---|---|
| **Depends on** | `T00.4.1`, `T00.4.3` |
| **Complexity** | M |
| **Deliverable** | Decision record N-9 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Owner named
- Non-interpretive boundary preserved
- I6 becomes enforceable

#### `T00.4.5` ⚠

Decide failure representation: failure records outside the object model, co-located with configuration store.

| | |
|---|---|
| **Depends on** | `T00.4.2` |
| **Complexity** | M |
| **Deliverable** | Decision record N-10 |
| **Blocks** | `T00.6.2`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Failure records excluded from lineage graph
- Home defined
- Empty-vs-failed distinction guaranteed

#### `T00.4.6`

Decide concurrency: concurrent acquisition and extraction; serialised interpretation from Problem onward.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | L |
| **Deliverable** | Decision record N-11 |
| **Blocks** | `T00.6.2`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Concurrency boundary named
- Graph global vs partitioned determined
- Pattern population stability guaranteed

#### `T00.4.7`

Decide retention: lineage skeleton permanent, content tiered by reachability from ACTIVE objects.

| | |
|---|---|
| **Depends on** | `T00.4.1`, `T00.4.8` |
| **Complexity** | M |
| **Deliverable** | Decision record N-12 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- ARCHIVED trigger and owner defined
- Principle 3 preservation demonstrated
- content_fingerprint retained permanently

#### `T00.4.8`

Decide Evidence storage: full content vs reference vs hybrid, constrained by licensing.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | M |
| **Deliverable** | Decision record (OQ-12) |
| **Blocks** | `T00.4.7`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Storage mode per source class decided
- Source-drift exposure of reference-only mode accepted
- Cost profile documented

### Feature F00.5 — Object Semantics Decisions (N-13, N-14, S-1…S-5)

#### `T00.5.1`

Define confidence calibration rubric with worked anchors per band per engine.

| | |
|---|---|
| **Depends on** | `T00.2.3` |
| **Complexity** | XL |
| **Deliverable** | Decision record S-1 + calibration rubric |
| **Blocks** | `T00.5.2`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Each of five bands defined by observable criteria
- At least two worked anchors per band
- Cross-engine comparability argued

#### `T00.5.2`

Define evidential_support computation: single conservative platform-wide function over independent source count and diversity.

| | |
|---|---|
| **Depends on** | `T00.5.1`, `T00.6.1` |
| **Complexity** | XL |
| **Deliverable** | Decision record S-2 + function specification |
| **Blocks** | `T00.5.4`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Inputs enumerated
- Function is deterministic given lineage
- Comparability across object types demonstrated

#### `T00.5.3`

Define structured claim decomposition and Fact equivalence: conservative merge, DUPLICATES for uncertain cases. Co-decided with fact definition and granularity.

| | |
|---|---|
| **Depends on** | `T00.2.5` |
| **Complexity** | XL |
| **Deliverable** | Decision record S-3 + claim structure spec |
| **Blocks** | `T00.5.5`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Claim structure defined
- Equivalence test is checkable, not opinion
- Under-merge preferred over over-merge, stated explicitly

#### `T00.5.4`

Define evidence sufficiency thresholds, independence-based, per object type.

| | |
|---|---|
| **Depends on** | `T00.5.2` |
| **Complexity** | L |
| **Deliverable** | Decision record S-4 |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Threshold per object type
- Expressed in independent sources, not raw counts
- P-V1 and PT-V1 become enforceable

#### `T00.5.5`

Define extraction fidelity verification: anchor verification on all Facts, sampled deeper audit, published hallucination rate. HIGHEST SEVERITY.

| | |
|---|---|
| **Depends on** | `T00.4.3`, `T00.5.3` |
| **Complexity** | XL |
| **Deliverable** | Decision record S-5 + verification protocol |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Anchor verification specified as acceptance-path hook
- Sample rate and audit protocol defined
- Hallucination rate defined as a published quality metric

#### `T00.5.6`

Define explanation skeleton: objects referenced, criteria applied, reasoning free-text, alternatives rejected where applicable.

| | |
|---|---|
| **Depends on** | `T00.1.3` |
| **Complexity** | M |
| **Deliverable** | Decision record N-13 + explanation standard |
| **Blocks** | `T00.7.1`, `T09.1.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Skeleton fields fixed
- V6 becomes structurally checkable
- Applies uniformly to all nine engines

#### `T00.5.7`

Decide cross-stage read access: lineage-restricted — an engine may read any object in its inputs' lineage.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | M |
| **Deliverable** | Decision record N-14 |
| **Blocks** | `T00.7.1`, `T07.1.5`, `T07.2.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Access rule stated
- Authority matrix updated
- Principle 4 erosion argued as contained

### Feature F00.6 — Control & Propagation Decisions

#### `T00.6.1`

Decide source diversity propagation: lightweight independent-source-count carried on every object; deep traversal for artefact assessment.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | M |
| **Deliverable** | Decision record (M-23) |
| **Blocks** | `T00.5.2`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Summary attribute added to universal set
- Traversal path defined for detail
- Feeds evidential_support

#### `T00.6.2` ⚠

Decide Orchestration control model: scheduled batch for P1–P5, revisit at P6.

| | |
|---|---|
| **Depends on** | `T00.4.6`, `T00.4.5` |
| **Complexity** | L |
| **Deliverable** | Decision record (M-35/M-37) |
| **Blocks** | `T00.6.3`, `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Control model named
- Iteration bounding defined
- Reactive vs directive settled

#### `T00.6.3` ⚠

Assign Orchestration a roadmap phase: baseline Orchestration scoped into P1. Resolves C-08.

| | |
|---|---|
| **Depends on** | `T00.6.2` |
| **Complexity** | M |
| **Deliverable** | Decision record (C-08) + revised P1 scope |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- P1 scope revised and published
- Baseline vs advanced capability split defined

#### `T00.6.4`

Reserve Experiment Registry placement in P1; capability build in P7.

| | |
|---|---|
| **Depends on** | `T00.4.1` |
| **Complexity** | S |
| **Deliverable** | Decision record (M-53) |
| **Blocks** | `T00.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Registry position reserved
- Split rationale recorded

### Feature F00.7 — Phase 0 Exit

#### `T00.7.1` ⚠

Verify all 22 minimum decisions are ratified and recorded. Produce the P1 entry gate report.

| | |
|---|---|
| **Depends on** | `T00.2.1`, `T00.2.2`, `T00.2.3`, `T00.2.4`, `T00.2.5`, `T00.2.6`, `T00.2.7`, `T00.2.8`, `T00.3.1`, `T00.3.2`, `T00.3.3`, `T00.3.4`, `T00.3.5`, `T00.4.1`, `T00.4.2`, `T00.4.3`, `T00.4.4`, `T00.4.5`, `T00.4.6`, `T00.4.7`, `T00.4.8`, `T00.5.1`, `T00.5.2`, `T00.5.3`, `T00.5.4`, `T00.5.5`, `T00.5.6`, `T00.5.7`, `T00.6.1`, `T00.6.2`, `T00.6.3`, `T00.6.4` |
| **Complexity** | M |
| **Deliverable** | P1 entry gate report |
| **Blocks** | `T01.1.1`, `T09.3.2` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- All 22 decisions have records
- No decision in DRAFT state
- Escalations (R-7, R-8, N-1, N-7) explicitly signed off

---

# Phase 1 — Foundation

## Epic E01 — Knowledge Foundation

**Goal.** Build the Knowledge Store, Knowledge Graph, configuration/failure stores, and the object acceptance path. The platform's least changeable layer.

**Entry dependencies.** `T00.7.1`

### Feature F01.1 — Object Identity & Persistence

#### `T01.1.1` ⚠

Implement object identity: object_id (unique, never reused), lineage_id (stable across versions), version (monotonic from 1).

| | |
|---|---|
| **Depends on** | `T00.7.1` |
| **Complexity** | M |
| **Deliverable** | Identity allocation component |
| **Blocks** | `T01.1.2` |
| **Independent** | Yes |

**Acceptance criteria**

- object_id uniqueness enforced
- lineage_id constant across a supersession chain
- version increments by exactly 1
- Reuse of a retired object_id is rejected

#### `T01.1.2` ⚠

Implement the universal required attribute set (17 attributes from IOM §1.1) as the base object contract.

| | |
|---|---|
| **Depends on** | `T01.1.1` |
| **Complexity** | L |
| **Deliverable** | Universal object contract |
| **Blocks** | `T01.1.3`, `T01.1.4`, `T01.3.1`, `T01.4.1`, `T01.5.1`, `T01.5.4`, `T09.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- All 17 attributes present on every persisted object
- Missing attribute blocks acceptance
- tenancy discriminator reserved per N-5

#### `T01.1.3`

Implement the universal optional attribute set (valid_until, duplicates, contradicts, supersedes, superseded_by, tags).

| | |
|---|---|
| **Depends on** | `T01.1.2` |
| **Complexity** | S |
| **Deliverable** | Optional attribute support |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Optional attributes accepted when present
- tags carry no engine-dependent semantics

#### `T01.1.4`

Implement immutable object persistence with atomic write per N-6.

| | |
|---|---|
| **Depends on** | `T01.1.2`, `T01.4.1` |
| **Complexity** | L |
| **Deliverable** | Knowledge Store write path |
| **Blocks** | `T01.1.5`, `T01.1.6`, `T01.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Content immutable after acceptance
- Write is atomic
- Partial writes impossible
- Hard delete unsupported

#### `T01.1.5`

Implement supersession chains: linear, non-branching, exactly one ACTIVE version per lineage_id (I5).

| | |
|---|---|
| **Depends on** | `T01.1.4` |
| **Complexity** | M |
| **Deliverable** | Versioning mechanism |
| **Blocks** | `T01.4.4`, `T05.1.7`, `T06.3.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Supersession creates a new version
- Predecessor transitions to SUPERSEDED
- Two ACTIVE versions of one lineage_id rejected
- Branching rejected

#### `T01.1.6`

Implement configuration store per N-7: immutable, versioned config records referenced by engine_configuration_ref.

| | |
|---|---|
| **Depends on** | `T01.1.4` |
| **Complexity** | M |
| **Deliverable** | Configuration store |
| **Blocks** | `T01.1.7`, `T08.2.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Config records immutable and versioned
- engine_configuration_ref resolves
- Config history queryable for a given point in time

#### `T01.1.7`

Implement failure record store per N-10, outside the object model.

| | |
|---|---|
| **Depends on** | `T01.1.6` |
| **Complexity** | M |
| **Deliverable** | Failure record store |
| **Blocks** | `T01.6.1`, `T01.6.3`, `T02.2.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Failure records excluded from lineage graph
- Empty result distinguishable from failed processing
- Failures attributable to engine and invocation

### Feature F01.2 — Lifecycle & State Management

#### `T01.2.1`

Implement the seven-state lifecycle with per-type reachability constraints.

| | |
|---|---|
| **Depends on** | `T01.1.4` |
| **Complexity** | L |
| **Deliverable** | Lifecycle state machine |
| **Blocks** | `T01.2.2`, `T06.3.4`, `T07.3.3` |
| **Independent** | Yes |

**Acceptance criteria**

- All seven states implemented
- Evidence cannot reach INVALIDATED
- Terminal states cannot transition
- status_reason required when status != ACTIVE

#### `T01.2.2`

Implement status transition as the sole permitted non-versioning mutation.

| | |
|---|---|
| **Depends on** | `T01.2.1` |
| **Complexity** | M |
| **Deliverable** | Status transition path |
| **Blocks** | `T01.2.3`, `T01.2.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Status changes without new version
- Content unchanged by transition
- All other mutation rejected

#### `T01.2.3`

Implement cascade invalidation per N-9: forward traversal, bulk transition to INVALIDATED, no interpretation.

| | |
|---|---|
| **Depends on** | `T01.2.2`, `T01.3.3` |
| **Complexity** | L |
| **Deliverable** | Cascade invalidation operation |
| **Blocks** | `T01.2.4`, `T01.4.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Retracting Evidence invalidates all dependents
- Traversal terminates
- Operation is idempotent
- No content altered, only status

#### `T01.2.4`

Implement partial-retraction semantics at the object layer: an object retaining at least one valid upstream reference is re-versioned with reduced support rather than invalidated. Applies to the Fact attachment case once F03 lands.

| | |
|---|---|
| **Depends on** | `T01.2.3` |
| **Complexity** | M |
| **Deliverable** | Partial retraction rule |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Object with some upstream references retracted remains ACTIVE at a new version
- Object with all upstream references retracted becomes INVALIDATED
- Rule is type-agnostic; Fact attachment behaviour follows from it

#### `T01.2.5`

Implement ARCHIVED tiering per N-12: lineage skeleton permanent, content tiered by reachability.

| | |
|---|---|
| **Depends on** | `T01.2.2`, `T01.3.4` |
| **Complexity** | L |
| **Deliverable** | Retention/archival mechanism |
| **Blocks** | `T01.8.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Objects reachable from any ACTIVE object are never archived
- Lineage traversal never breaks after archival
- content_fingerprint and provenance retained permanently

### Feature F01.3 — Lineage & Knowledge Graph

#### `T01.3.1` ⚠

Implement the closed ten-type relationship taxonomy (D-06) with asserting-engine attribution.

| | |
|---|---|
| **Depends on** | `T01.1.2` |
| **Complexity** | L |
| **Deliverable** | Relationship model |
| **Blocks** | `T01.3.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Exactly ten types accepted
- Undefined relationship types rejected
- Every relationship records asserting engine and timestamp
- DERIVES_FROM and SUPPORTS are distinct

#### `T01.3.2` ⚠

Implement objects-authoritative lineage per N-6: lineage carried on the object, version-specific binding (D-01a).

| | |
|---|---|
| **Depends on** | `T01.3.1` |
| **Complexity** | L |
| **Deliverable** | Lineage attribute model |
| **Blocks** | `T01.3.3`, `T01.3.6` |
| **Independent** | Yes |

**Acceptance criteria**

- derives_from binds to specific versions
- References never repoint (I3)
- Object is self-describing without the graph

#### `T01.3.3` ⚠

Implement the Knowledge Graph as a derived, rebuildable traversal index.

| | |
|---|---|
| **Depends on** | `T01.3.2` |
| **Complexity** | XL |
| **Deliverable** | Knowledge Graph index |
| **Blocks** | `T01.2.3`, `T01.3.4`, `T01.3.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Graph rebuildable from objects alone
- Divergence recoverable by rebuild
- Graph is never the authority on a relationship

#### `T01.3.4` ⚠

Implement backward traversal (object to Evidence) with guaranteed termination.

| | |
|---|---|
| **Depends on** | `T01.3.3` |
| **Complexity** | M |
| **Deliverable** | Backward traversal |
| **Blocks** | `T01.2.5`, `T01.4.2`, `T01.5.2`, `T05.2.1`, `T06.3.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Every non-Evidence object reaches at least one Evidence object
- Traversal terminates on all inputs
- Depth 8 supported

#### `T01.3.5`

Implement forward traversal (Evidence to dependents) for impact analysis and cascade.

| | |
|---|---|
| **Depends on** | `T01.3.3` |
| **Complexity** | M |
| **Deliverable** | Forward traversal |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- All dependents of an Evidence object identifiable
- Supports cascade invalidation

#### `T01.3.6`

Implement cycle prevention (V10): reject any write introducing a lineage cycle.

| | |
|---|---|
| **Depends on** | `T01.3.2` |
| **Complexity** | M |
| **Deliverable** | Cycle guard |
| **Blocks** | `T01.4.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Cycle-introducing write rejected at acceptance
- Feedback Record cannot create a path back to Evidence (FR-I2)

### Feature F01.4 — Acceptance & Validation Path

#### `T01.4.1`

Implement the acceptance path per N-8: Store enforces, rules specified in the object model.

| | |
|---|---|
| **Depends on** | `T01.1.2` |
| **Complexity** | L |
| **Deliverable** | Acceptance enforcement point |
| **Blocks** | `T01.1.4`, `T01.4.2`, `T01.4.6` |
| **Independent** | Yes |

**Acceptance criteria**

- PROPOSED to ACTIVE gated by rule evaluation
- Rules externally specified, not embedded in the Store
- Failed acceptance produces a failure record

#### `T01.4.2` ⚠

Implement universal validation rules V1-V4 (attributes present, derives_from non-empty, references resolve, Evidence reachable).

| | |
|---|---|
| **Depends on** | `T01.4.1`, `T01.3.4` |
| **Complexity** | L |
| **Deliverable** | Validation rules V1-V4 |
| **Blocks** | `T01.4.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Each rule independently testable
- V2 exempts Evidence only
- V4 verified by actual traversal, not assertion

#### `T01.4.3` ⚠

Implement universal validation rules V5-V8 (confidence ceiling, explanation non-empty, create authority, timestamp ordering).

| | |
|---|---|
| **Depends on** | `T01.4.2`, `T01.5.2` |
| **Complexity** | M |
| **Deliverable** | Validation rules V5-V8 |
| **Blocks** | `T01.4.4` |
| **Independent** | Yes |

**Acceptance criteria**

- V5 rejects any object exceeding min(upstream effective_confidence)
- V7 rejects writes from engines lacking create authority
- V8 enforces observed_at <= asserted_at <= produced_at

#### `T01.4.4` ⚠

Implement universal validation rules V9-V12 (status_reason, cycles, version increment, closed taxonomy).

| | |
|---|---|
| **Depends on** | `T01.4.3`, `T01.3.6`, `T01.1.5` |
| **Complexity** | M |
| **Deliverable** | Validation rules V9-V12 |
| **Blocks** | `T01.4.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Each rule independently testable
- V11 enforces version and lineage_id integrity

#### `T01.4.5` ⚠

Implement universal integrity constraints I1-I8 as continuous invariants, not acceptance-time checks.

| | |
|---|---|
| **Depends on** | `T01.4.4`, `T01.2.3` |
| **Complexity** | L |
| **Deliverable** | Integrity constraint enforcement |
| **Blocks** | `T01.7.1`, `T01.8.1` |
| **Independent** | Yes |

**Acceptance criteria**

- I5 (one ACTIVE per lineage_id) continuously held
- I6 (cascade) enforced via T01.2.3
- I8 prevents REJECTED objects being consumed as input

#### `T01.4.6`

Implement the semantic-check hook in the acceptance path for rules structure cannot enforce (F-V6).

| | |
|---|---|
| **Depends on** | `T01.4.1` |
| **Complexity** | M |
| **Deliverable** | Semantic verification hook |
| **Blocks** | `T01.7.2`, `T03.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Hook invocable at acceptance
- Anchor verification pluggable
- Documented as not covering paraphrase drift

### Feature F01.5 — Confidence & Support

#### `T01.5.1`

Implement the two-component confidence model: evidential_support, assertion_confidence, effective_confidence with band labels.

| | |
|---|---|
| **Depends on** | `T01.1.2` |
| **Complexity** | M |
| **Deliverable** | Confidence attribute model |
| **Blocks** | `T01.5.2`, `T01.5.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Both components stored independently
- Five bands implemented
- Well-evidenced/low-confidence case representable

#### `T01.5.2`

Implement the monotonic ceiling rule: effective_confidence <= min(upstream effective_confidence).

| | |
|---|---|
| **Depends on** | `T01.5.1`, `T01.3.4` |
| **Complexity** | L |
| **Deliverable** | Ceiling enforcement |
| **Blocks** | `T01.4.3`, `T01.5.3`, `T06.3.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Ceiling computed from actual lineage
- Violation rejected at acceptance
- Worked chain 0.62 to 0.58 reproduces IOM example

#### `T01.5.3`

Implement the evidential_support function per S-2, over independent source count and diversity.

| | |
|---|---|
| **Depends on** | `T01.5.2`, `T01.5.4` |
| **Complexity** | L |
| **Deliverable** | Support computation |
| **Blocks** | `T01.7.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Deterministic given lineage
- Comparable across object types
- Recomputed on upstream change

#### `T01.5.4`

Implement the independent-source-count summary attribute per M-23, carried on every object.

| | |
|---|---|
| **Depends on** | `T01.1.2` |
| **Complexity** | M |
| **Deliverable** | Diversity summary attribute |
| **Blocks** | `T01.5.3`, `T01.7.4`, `T05.1.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Populated at creation
- Propagates without deep traversal
- Available to Pattern Intelligence at depth 3

#### `T01.5.5`

Implement calibration rubric conformance: engines assert confidence against the S-1 rubric.

| | |
|---|---|
| **Depends on** | `T01.5.1` |
| **Complexity** | M |
| **Deliverable** | Calibration conformance check |
| **Blocks** | `T08.3.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Rubric bands referenced at assertion
- Deviations recorded
- Cross-engine comparison documented as rubric-dependent

### Feature F01.6 — Baseline Orchestration

#### `T01.6.1`

Implement scheduled batch invocation per N-11 and the M-35 control model.

| | |
|---|---|
| **Depends on** | `T01.1.7` |
| **Complexity** | L |
| **Deliverable** | Orchestration invocation |
| **Blocks** | `T01.6.2`, `T01.6.5`, `T02.2.4`, `T08.2.7`, `T09.1.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Engines invoked on schedule
- Batch boundaries defined
- Iteration bounded

#### `T01.6.2`

Implement processing-state tracking: what has been processed, by which engine, when.

| | |
|---|---|
| **Depends on** | `T01.6.1` |
| **Complexity** | L |
| **Deliverable** | Processing state store |
| **Blocks** | `T01.6.3`, `T01.6.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Idempotence supported: reprocessing detectable
- State held outside the object model
- Orchestration reads metadata only, never content

#### `T01.6.3`

Implement failure surfacing: engine failures recorded and visible, never masked as completion.

| | |
|---|---|
| **Depends on** | `T01.6.2`, `T01.1.7` |
| **Complexity** | M |
| **Deliverable** | Failure surfacing |
| **Blocks** | `T09.1.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Failed invocation distinguishable from empty result
- Failures do not silently halt the pipeline

#### `T01.6.4`

Implement concurrency boundary per N-11: parallel acquisition/extraction, serialised interpretation.

| | |
|---|---|
| **Depends on** | `T01.6.2` |
| **Complexity** | L |
| **Deliverable** | Concurrency control |
| **Blocks** | `T05.1.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Problem-stage-onward writes serialised
- Pattern Intelligence sees a stable population per batch
- Version branching impossible

#### `T01.6.5`

Implement sequencing enforcement: an engine cannot run before its inputs exist.

| | |
|---|---|
| **Depends on** | `T01.6.1` |
| **Complexity** | M |
| **Deliverable** | Sequencing guard |
| **Blocks** | `T01.8.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Pipeline order never violated
- Out-of-order invocation rejected

### Feature F01.7 — Object Type Realisation

#### `T01.7.1` ⚠

Realise the Evidence object type: attributes, E-V1..E-V6, E-I1..E-I4.

| | |
|---|---|
| **Depends on** | `T01.4.5`, `T01.5.3` |
| **Complexity** | L |
| **Deliverable** | Evidence type |
| **Blocks** | `T01.7.2`, `T02.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- derives_from empty enforced (E-V1)
- E-I2 rejects platform-internal derivation
- Duplicate fingerprint+source rejected (E-V6)

#### `T01.7.2` ⚠

Realise the Fact object type including the evidence_attachment structure and F-V1..F-V6.

| | |
|---|---|
| **Depends on** | `T01.7.1`, `T01.4.6` |
| **Complexity** | XL |
| **Deliverable** | Fact type |
| **Blocks** | `T01.7.3`, `T03.1.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Multiple attachments per Fact supported
- Positional anchor required per attachment
- independent_source_count <= attachment count
- F-V6 hook wired

#### `T01.7.3` ⚠

Realise the Problem object type: attributes, P-V1..P-V6, P-I1..P-I4.

| | |
|---|---|
| **Depends on** | `T01.7.2` |
| **Complexity** | L |
| **Deliverable** | Problem type |
| **Blocks** | `T01.7.4`, `T04.1.1` |
| **Independent** | Yes |

**Acceptance criteria**

- inference_basis distinct from explanation
- P-V2 solution-independence check present
- affected_population required

#### `T01.7.4` ⚠

Realise the Pattern object type: attributes, PT-V1..PT-V6, PT-I1..PT-I4.

| | |
|---|---|
| **Depends on** | `T01.7.3`, `T01.5.4` |
| **Complexity** | L |
| **Deliverable** | Pattern type |
| **Blocks** | `T01.7.5`, `T05.1.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Minimum two distinct constituents enforced
- PT-V2 rejects patterns over versions of one problem
- source_diversity and artefact_assessment required

#### `T01.7.5` ⚠

Realise the Opportunity object type: attributes, O-V1..O-V7, O-I1..O-I4.

| | |
|---|---|
| **Depends on** | `T01.7.4` |
| **Complexity** | L |
| **Deliverable** | Opportunity type |
| **Blocks** | `T01.7.6`, `T06.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- score_model_version required with score
- O-V5 confidence ceiling enforced
- Object cannot reach ACTIVE while scoring undefined (documented)

#### `T01.7.6` ⚠

Realise the Solution object type including structured assumptions and S-V1..S-V6.

| | |
|---|---|
| **Depends on** | `T01.7.5` |
| **Complexity** | L |
| **Deliverable** | Solution type |
| **Blocks** | `T01.7.7`, `T07.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- assumptions non-empty enforced (S-V2)
- Each assumption has criticality and testability
- candidate_group supports sibling candidates

#### `T01.7.7` ⚠

Realise the Validation object type: attributes, V-V1..V-V6, V-I1..V-I4.

| | |
|---|---|
| **Depends on** | `T01.7.6` |
| **Complexity** | L |
| **Deliverable** | Validation type |
| **Blocks** | `T01.7.8`, `T07.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Negative result is ACTIVE, never REJECTED
- tests_claim targets a specific claim, not a whole object
- scope_limitations required

#### `T01.7.8` ⚠

Realise the Execution Record object type: attributes, X-V1..X-V6. Create authority remains unassigned pending C-02.

| | |
|---|---|
| **Depends on** | `T01.7.7` |
| **Complexity** | L |
| **Deliverable** | Execution Record type |
| **Blocks** | `T01.7.9`, `T08.1.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Type realised and persistable
- No engine holds create authority yet
- X-V4 requires resolvable stored prediction

#### `T01.7.9` ⚠

Realise the Feedback Record object type: attributes, FR-V1..FR-V6, FR-I1..FR-I4.

| | |
|---|---|
| **Depends on** | `T01.7.8` |
| **Complexity** | L |
| **Deliverable** | Feedback Record type |
| **Blocks** | `T01.8.1`, `T08.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- FR-V6 restricts derivation to Execution Records only
- FR-I2 prevents becoming Evidence
- reversal_procedure required

### Feature F01.8 — Phase 1 Exit

#### `T01.8.1` ⚠

Verify the P1 exit criteria: objects persistable with enforced references, bidirectional lineage traversal, attribution on every write, structural validity enforced.

| | |
|---|---|
| **Depends on** | `T01.7.9`, `T01.6.5`, `T01.2.5`, `T01.4.5` |
| **Complexity** | L |
| **Deliverable** | P1 exit report |
| **Blocks** | `T02.1.1`, `T07.1.3` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- All nine object types persistable
- Lineage traversable both directions
- No object acceptable without attribution
- Graph rebuild demonstrated

---

# Phase 2 — Research Engine

## Epic E02 — Research Engine

**Goal.** Acquire external source material as Evidence with complete provenance. The platform's only external-world acquisition boundary.

**Entry dependencies.** `T01.1.7`, `T01.6.1`, `T01.7.1`, `T01.8.1`

### Feature F02.1 — Source Model

#### `T02.1.1` ⚠

Define and implement the source taxonomy with per-type eligibility and learnable trust ratings (M-16).

| | |
|---|---|
| **Depends on** | `T01.8.1` |
| **Complexity** | L |
| **Deliverable** | Source taxonomy + trust model |
| **Blocks** | `T02.1.2`, `T02.1.3` |
| **Independent** | Yes |

**Acceptance criteria**

- source_type drawn from a closed taxonomy
- Per-source trust rating stored
- Trust rating is a learnable target for P8

#### `T02.1.2` ⚠

Implement licensing and access policy enforcement at acquisition (M-18).

| | |
|---|---|
| **Depends on** | `T02.1.1` |
| **Complexity** | L |
| **Deliverable** | Access policy enforcement |
| **Blocks** | `T02.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Ineligible sources rejected before acquisition
- access_conditions populated on every Evidence object
- Retention rights recorded and honoured

#### `T02.1.3`

Implement source independence grouping to identify non-independent sources (syndication, common ownership).

| | |
|---|---|
| **Depends on** | `T02.1.1` |
| **Complexity** | M |
| **Deliverable** | Independence grouping |
| **Blocks** | `T02.1.4` |
| **Independent** | Yes |

**Acceptance criteria**

- source_independence_group populated
- Syndicated sources not counted as independent

#### `T02.1.4`

Implement the coverage model with explicit gap declaration (M-17).

| | |
|---|---|
| **Depends on** | `T02.1.3` |
| **Complexity** | L |
| **Deliverable** | Coverage model |
| **Blocks** | `T02.3.1`, `T05.1.4`, `T08.3.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Source-type coverage measurable
- Known gaps declared explicitly
- Gap declaration inheritable by Pattern artefact assessment

### Feature F02.2 — Acquisition

#### `T02.2.1` ⚠

Implement source acquisition producing Evidence objects with complete provenance.

| | |
|---|---|
| **Depends on** | `T02.1.2`, `T01.7.1` |
| **Complexity** | L |
| **Deliverable** | Acquisition capability |
| **Blocks** | `T02.2.2`, `T02.2.4`, `T02.2.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Provenance complete on every Evidence object
- Acquisition failures recorded, not silent
- capture_fidelity documented per acquisition

#### `T02.2.2` ⚠

Implement content fingerprinting and duplicate detection (E-V6).

| | |
|---|---|
| **Depends on** | `T02.2.1` |
| **Complexity** | M |
| **Deliverable** | Duplicate detection |
| **Blocks** | `T02.2.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Same fingerprint plus source rejected
- Re-acquisition detectable
- Duplicate rate measurable

#### `T02.2.3` ⚠

Implement source drift detection by fingerprint comparison on re-acquisition.

| | |
|---|---|
| **Depends on** | `T02.2.2` |
| **Complexity** | M |
| **Deliverable** | Drift detection |
| **Blocks** | `T02.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Changed source content detected
- Drift recorded against original Evidence
- Superseding version created where fidelity improves

#### `T02.2.4`

Implement research directive intake: scheduled batch, directive-driven targets (M-01).

| | |
|---|---|
| **Depends on** | `T02.2.1`, `T01.6.1` |
| **Complexity** | M |
| **Deliverable** | Directive intake |
| **Blocks** | `T07.3.8`, `T08.3.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Directives scope acquisition
- Targets proposed for approval per human-gate decision
- Out-of-scope acquisition rejected

#### `T02.2.5`

Implement acquisition failure recording distinguishing not-found from not-attempted.

| | |
|---|---|
| **Depends on** | `T02.2.1`, `T01.1.7` |
| **Complexity** | S |
| **Deliverable** | Acquisition failure records |
| **Blocks** | `T02.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Failed attempts recorded
- Absence of evidence distinguishable from absence of attempt

### Feature F02.3 — Phase 2 Exit

#### `T02.3.1` ⚠

Verify P2 exit: Evidence acquirable with complete provenance, duplicates detectable, failures distinguishable.

| | |
|---|---|
| **Depends on** | `T02.2.5`, `T02.2.3`, `T02.1.4` |
| **Complexity** | M |
| **Deliverable** | P2 exit report |
| **Blocks** | `T03.1.1` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Evidence acquired from every defined source type
- Duplicate detection demonstrated
- Coverage gaps declared

---

# Phase 3 — Fact Extraction

## Epic E03 — Fact Extraction Engine

**Goal.** Convert Evidence into canonical, individually verifiable claims. The platform's integrity floor.

**Entry dependencies.** `T00.3.3`, `T01.4.6`, `T01.7.2`, `T02.3.1`

### Feature F03.1 — Extraction

#### `T03.1.1` ⚠

Implement claim extraction producing self-contained claims with qualifying context.

| | |
|---|---|
| **Depends on** | `T02.3.1`, `T01.7.2` |
| **Complexity** | L |
| **Deliverable** | Extraction capability |
| **Blocks** | `T03.1.2`, `T03.1.3`, `T03.1.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Claims interpretable without reading the Evidence (F-V3)
- qualifying_context preserved
- Extraction density consistent across comparable evidence

#### `T03.1.2`

Implement structured claim decomposition per S-3 (subject, predicate, qualifier, value).

| | |
|---|---|
| **Depends on** | `T03.1.1` |
| **Complexity** | L |
| **Deliverable** | Claim structure |
| **Blocks** | `T03.1.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Every claim decomposed to the defined structure
- Structure supports equivalence comparison

#### `T03.1.3` ⚠

Implement positional anchoring into source Evidence (F-V2).

| | |
|---|---|
| **Depends on** | `T03.1.1` |
| **Complexity** | M |
| **Deliverable** | Positional anchoring |
| **Blocks** | `T03.1.4`, `T03.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Every attachment has a resolvable anchor
- Anchor precise enough to locate the claim without full re-reading

#### `T03.1.4`

Implement canonical-claim merging per D-05: equivalent extractions attach to an existing Fact.

| | |
|---|---|
| **Depends on** | `T03.1.2`, `T03.1.3` |
| **Complexity** | XL |
| **Deliverable** | Merge mechanism |
| **Blocks** | `T03.1.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Equivalent claim adds an attachment, not a new Fact
- Merge produces a new Fact version
- Uncertain equivalence produces DUPLICATES, not a merge

#### `T03.1.5`

Implement assertion versus attributed-opinion classification (F-V4).

| | |
|---|---|
| **Depends on** | `T03.1.1` |
| **Complexity** | M |
| **Deliverable** | Claim type classification |
| **Blocks** | `T03.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- claim_type populated
- attributed_to required for ATTRIBUTED_OPINION

#### `T03.1.6`

Implement contradiction detection between Facts, producing CONTRADICTS relationships.

| | |
|---|---|
| **Depends on** | `T03.1.4` |
| **Complexity** | L |
| **Deliverable** | Contradiction detection |
| **Blocks** | `T03.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Incompatible claims linked, not silently resolved
- Both Facts remain ACTIVE

### Feature F03.2 — Fidelity Verification

#### `T03.2.1` ⚠

Implement anchor verification on every Fact at acceptance per S-5.

| | |
|---|---|
| **Depends on** | `T03.1.3`, `T01.4.6` |
| **Complexity** | L |
| **Deliverable** | Anchor verification |
| **Blocks** | `T03.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Claim locatable at stated anchor
- Fabricated anchors rejected
- Runs on 100 percent of Facts

#### `T03.2.2` ⚠

Implement sampled deep audit for semantic drift beyond anchor verification.

| | |
|---|---|
| **Depends on** | `T03.2.1` |
| **Complexity** | L |
| **Deliverable** | Sampled audit protocol |
| **Blocks** | `T03.2.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Sample rate configurable
- Audit detects paraphrase drift anchor checks miss

#### `T03.2.3` ⚠

Implement hallucination rate as a published quality metric feeding the success measures.

| | |
|---|---|
| **Depends on** | `T03.2.2`, `T00.3.3` |
| **Complexity** | M |
| **Deliverable** | Hallucination rate metric |
| **Blocks** | `T03.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Rate computed from audit results
- Published as a platform quality metric
- Trend trackable over time

### Feature F03.3 — Phase 3 Exit

#### `T03.3.1` ⚠

Verify P3 exit: Facts extractable with anchoring, hallucination rate measured, duplicates recognised.

| | |
|---|---|
| **Depends on** | `T03.2.3`, `T03.1.6`, `T03.1.5` |
| **Complexity** | M |
| **Deliverable** | P3 exit report |
| **Blocks** | `T04.1.1` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Facts anchored to specific evidence locations
- Hallucination rate published
- Corroboration countable via independent_source_count

---

# Phase 4 — Problem Intelligence

## Epic E04 — Problem Intelligence Engine

**Goal.** Identify unmet needs from Facts. The platform's first interpretive engine.

**Entry dependencies.** `T01.7.3`, `T03.3.1`

### Feature F04.1 — Problem Inference

#### `T04.1.1` ⚠

Implement problem inference from Facts with multi-fact support per S-4 thresholds.

| | |
|---|---|
| **Depends on** | `T03.3.1`, `T01.7.3` |
| **Complexity** | L |
| **Deliverable** | Problem inference |
| **Blocks** | `T04.1.2`, `T04.1.3`, `T04.1.4`, `T04.1.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Sufficiency threshold enforced
- Single-fact restatement rejected (P-V6)
- inference_basis references specific Facts

#### `T04.1.2`

Implement solution-independence enforcement (P-V2, P-I1).

| | |
|---|---|
| **Depends on** | `T04.1.1` |
| **Complexity** | L |
| **Deliverable** | Solution-independence check |
| **Blocks** | `T04.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Problems framed as absence of a specific solution rejected
- Check applies across all versions

#### `T04.1.3`

Implement affected-population identification (P-V3).

| | |
|---|---|
| **Depends on** | `T04.1.1` |
| **Complexity** | M |
| **Deliverable** | Population identification |
| **Blocks** | `T04.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- affected_population specific and non-empty
- Population never widened without supporting Facts (P-I3)

#### `T04.1.4` ⚠

Implement severity and frequency ordinal bands with evidence-linked justification (M-12).

| | |
|---|---|
| **Depends on** | `T04.1.1` |
| **Complexity** | L |
| **Deliverable** | Problem weight model |
| **Blocks** | `T04.1.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Ordinal bands defined
- Each rating traceable to Facts
- Weight never exceeds what Facts support (P-I4)

#### `T04.1.5` ⚠

Implement problem identity and conservative deduplication per M-22, mirroring D-05.

| | |
|---|---|
| **Depends on** | `T04.1.4` |
| **Complexity** | L |
| **Deliverable** | Problem deduplication |
| **Blocks** | `T04.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Equivalent problems merged conservatively
- Uncertain cases produce DUPLICATES links
- Under-merge preferred over over-merge

#### `T04.1.6`

Implement the problem taxonomy (M-21) constraining problem_domain.

| | |
|---|---|
| **Depends on** | `T04.1.1` |
| **Complexity** | M |
| **Deliverable** | Problem taxonomy |
| **Blocks** | `T04.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- problem_domain drawn from taxonomy
- Taxonomy extensible by decision record

### Feature F04.2 — Phase 4 Exit

#### `T04.2.1` ⚠

Verify P4 exit: Problems inferable with multi-fact support, solution-independent, population identified.

| | |
|---|---|
| **Depends on** | `T04.1.5`, `T04.1.6`, `T04.1.2`, `T04.1.3` |
| **Complexity** | M |
| **Deliverable** | P4 exit report |
| **Blocks** | `T05.1.1` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Solution-independence verified by inspection
- Sufficiency thresholds enforced
- Deduplication demonstrated

---

# Phase 5 — Pattern Intelligence

## Epic E05 — Pattern Intelligence Engine

**Goal.** Detect structure across Problems. The pipeline's narrow waist.

**Entry dependencies.** `T01.1.5`, `T01.3.4`, `T01.5.4`, `T01.6.4`, `T01.7.4`, `T02.1.4`, `T04.2.1`

### Feature F05.1 — Pattern Recognition

#### `T05.1.1` ⚠

Implement cross-problem comparison over the accumulated Problem population.

| | |
|---|---|
| **Depends on** | `T04.2.1`, `T01.7.4`, `T01.6.4` |
| **Complexity** | XL |
| **Deliverable** | Pattern recognition |
| **Blocks** | `T05.1.2`, `T05.1.3`, `T05.1.4`, `T05.1.7`, `T05.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Operates on a stable population per batch
- Minimum two distinct constituents (PT-V1)
- PT-V2 rejects versions of one problem as multiple constituents

#### `T05.1.2`

Implement the pattern type taxonomy (M-25) with per-type minimum constituent counts (M-24).

| | |
|---|---|
| **Depends on** | `T05.1.1` |
| **Complexity** | L |
| **Deliverable** | Pattern type model |
| **Blocks** | `T05.1.6` |
| **Independent** | Yes |

**Acceptance criteria**

- pattern_type from closed taxonomy
- Per-type thresholds enforced
- Cross-domain claims require higher support

#### `T05.1.3`

Implement grouping rationale generation explaining non-coincidence (PT-V3).

| | |
|---|---|
| **Depends on** | `T05.1.1` |
| **Complexity** | L |
| **Deliverable** | Grouping rationale |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Rationale references specific constituents
- Distinguishes structure from coincidence

#### `T05.1.4` ⚠

Implement source diversity computation and artefact assessment (PT-V4, PT-V5).

| | |
|---|---|
| **Depends on** | `T05.1.1`, `T01.5.4`, `T02.1.4` |
| **Complexity** | XL |
| **Deliverable** | Artefact assessment |
| **Blocks** | `T05.1.5` |
| **Independent** | Yes |

**Acceptance criteria**

- source_diversity computed from lineage
- Artefact assessment reasoned, not boilerplate
- Patterns from a single over-sampled source flagged

#### `T05.1.5` ⚠

Implement diversity-weighted pattern strength (M-24).

| | |
|---|---|
| **Depends on** | `T05.1.4` |
| **Complexity** | L |
| **Deliverable** | Pattern strength measure |
| **Blocks** | `T05.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Strength weighted by source diversity, not raw count
- Frequency inflation countered

#### `T05.1.6`

Implement pattern temporal validity with explicit valid_until and review-on-breach (M-13).

| | |
|---|---|
| **Depends on** | `T05.1.2` |
| **Complexity** | L |
| **Deliverable** | Pattern temporal validity |
| **Blocks** | `T05.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- valid_until set per pattern
- Breach triggers review, not automatic invalidation
- Stale patterns identifiable

#### `T05.1.7`

Implement batched constituent addition per OQ-21 to bound version churn.

| | |
|---|---|
| **Depends on** | `T05.1.1`, `T01.1.5` |
| **Complexity** | M |
| **Deliverable** | Batched versioning |
| **Blocks** | `T05.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Constituent additions batched per orchestration cycle
- Decomposability preserved (PT-V6)

### Feature F05.2 — Lineage Usability

#### `T05.2.1`

Implement tiered lineage summarisation (M-66): summary by default, full traversal on demand.

| | |
|---|---|
| **Depends on** | `T05.1.1`, `T01.3.4` |
| **Complexity** | L |
| **Deliverable** | Lineage summarisation |
| **Blocks** | `T05.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Summary available for depth 3+ objects
- Full traversal remains available
- Summaries do not misrepresent support

#### `T05.2.2`

Implement re-derivation flagging on upstream supersession (M-65).

| | |
|---|---|
| **Depends on** | `T05.2.1` |
| **Complexity** | L |
| **Deliverable** | Re-derivation flagging |
| **Blocks** | `T05.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Dependents of superseded objects flagged
- Recompute triggered on threshold breach
- Stale-derivation objects distinguishable from current

### Feature F05.3 — Phase 5 Exit

#### `T05.3.1` ⚠

Verify P5 exit: Patterns identifiable, decomposable, artefacts distinguishable from genuine structure.

| | |
|---|---|
| **Depends on** | `T05.1.7`, `T05.1.5`, `T05.1.6`, `T05.2.2` |
| **Complexity** | M |
| **Deliverable** | P5 exit report |
| **Blocks** | `T06.1.1` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Every Pattern decomposable to constituents
- Sampling artefacts detectable
- Diversity-weighted strength operational

---

# Phase 6 — Opportunity Intelligence

## Epic E06 — Opportunity Intelligence Engine

**Goal.** Convert Patterns into scored, comparable opportunities. The platform's primary output.

**Entry dependencies.** `T00.3.2`, `T01.1.5`, `T01.2.1`, `T01.3.4`, `T01.5.2`, `T01.7.5`, `T05.3.1`

### Feature F06.1 — Prerequisite Recovery

#### `T06.1.1` ⚠

Recover the findings of the four completed research efforts (M-48), prioritising Opportunity Evaluation.

| | |
|---|---|
| **Depends on** | `T05.3.1` |
| **Complexity** | M |
| **Deliverable** | Recovered research findings |
| **Blocks** | `T06.1.2`, `T09.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Findings documented for all four efforts
- Opportunity Evaluation output identified or confirmed lost
- Method and provenance recorded where recoverable

#### `T06.1.2` ⚠

Determine disposition of prior research (M-49): reference only, not ingested as Evidence.

| | |
|---|---|
| **Depends on** | `T06.1.1` |
| **Complexity** | S |
| **Deliverable** | Disposition decision record |
| **Blocks** | `T06.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Non-ingestion confirmed
- Re-acquisition path defined if evidence is wanted
- E-I2 integrity preserved

### Feature F06.2 — Scoring Model

#### `T06.2.1` ⚠

Define scoring dimensions, scale, weighting and aggregation (M-14), informed by T06.1.1.

| | |
|---|---|
| **Depends on** | `T06.1.2` |
| **Complexity** | XL |
| **Deliverable** | Scoring model specification |
| **Blocks** | `T06.2.2`, `T06.2.3`, `T06.2.5`, `T06.3.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Multi-dimensional, not a single opaque number
- Weights explicit and auditable
- Aggregation method defined

#### `T06.2.2`

Implement score_model_version stamping on every Opportunity (O-I3).

| | |
|---|---|
| **Depends on** | `T06.2.1`, `T01.7.5` |
| **Complexity** | M |
| **Deliverable** | Score versioning |
| **Blocks** | `T06.2.4`, `T06.3.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Every score carries its model version
- Cross-version comparison rejected
- Score drift detectable

#### `T06.2.3` ⚠

Implement per-dimension score_basis and scoring_explanation (O-V4).

| | |
|---|---|
| **Depends on** | `T06.2.1` |
| **Complexity** | L |
| **Deliverable** | Score explanation |
| **Blocks** | `T06.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Explanation references specific dimensions
- Score is never opaque
- Rejected candidates carry rejection_rationale

#### `T06.2.4`

Implement learnable scoring weights as a defined Feedback Engine target.

| | |
|---|---|
| **Depends on** | `T06.2.2` |
| **Complexity** | L |
| **Deliverable** | Learnable weight mechanism |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Weights adjustable via configuration
- Changes produce a new score_model_version
- Reversible per B-67

#### `T06.2.5`

Confirm scoring ownership as internal to Opportunity Intelligence (C-01); no new engine.

| | |
|---|---|
| **Depends on** | `T06.2.1` |
| **Complexity** | S |
| **Deliverable** | Decision record (C-01) |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Ownership recorded
- No tenth engine introduced

### Feature F06.3 — Opportunity Formulation

#### `T06.3.1` ⚠

Implement opportunity formulation from Patterns with solution-free enforcement (O-V2, O-I2).

| | |
|---|---|
| **Depends on** | `T06.2.3` |
| **Complexity** | L |
| **Deliverable** | Opportunity formulation |
| **Blocks** | `T06.3.2`, `T06.3.3`, `T06.3.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Statements contain no solution design
- value_hypothesis and beneficiary_population required

#### `T06.3.2` ⚠

Implement confidence honesty: assertion_confidence bounded by evidential support (O-V5, O-I1).

| | |
|---|---|
| **Depends on** | `T06.3.1`, `T01.5.2` |
| **Complexity** | L |
| **Deliverable** | Confidence enforcement |
| **Blocks** | `T06.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Ceiling enforced against originating Pattern
- Confidence inflation rejected at acceptance

#### `T06.3.3`

Implement sizing traceability (O-V6): quantitative claims trace to Facts via lineage.

| | |
|---|---|
| **Depends on** | `T06.3.1`, `T01.3.4` |
| **Complexity** | M |
| **Deliverable** | Sizing traceability |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Untraceable quantitative claims rejected
- market_sizing optional but evidence-linked when present

#### `T06.3.4`

Implement rejected-candidate retention with rationale (O-V7).

| | |
|---|---|
| **Depends on** | `T06.3.1`, `T01.2.1` |
| **Complexity** | M |
| **Deliverable** | Rejection retention |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- REJECTED opportunities persisted
- rejection_rationale required
- Available as learning signal

#### `T06.3.5`

Define the platform meaning of opportunity (M-26) aligned to scoring dimensions.

| | |
|---|---|
| **Depends on** | `T06.2.1` |
| **Complexity** | M |
| **Deliverable** | Opportunity definition |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Definition recorded
- Typed and aligned to scoring
- Novel forms not silently excluded

#### `T06.3.6`

Implement point-in-time score storage plus rescoring as a new version (OQ-19, O-I4).

| | |
|---|---|
| **Depends on** | `T06.2.2`, `T01.1.5` |
| **Complexity** | M |
| **Deliverable** | Score persistence model |
| **Blocks** | `T06.5.1`, `T08.1.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Historical predictions preserved unaltered
- Rescoring creates a version, never overwrites

### Feature F06.4 — Gating & Prioritisation

#### `T06.4.1` ⚠

Implement threshold-based gating with human override for opportunity selection (M-28, M-31).

| | |
|---|---|
| **Depends on** | `T06.3.2`, `T00.3.2` |
| **Complexity** | L |
| **Deliverable** | Gate mechanism |
| **Blocks** | `T06.4.2`, `T06.4.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Threshold applied mechanically by Orchestration
- Human override available at the defined gate
- Gate decisions recorded with rationale

#### `T06.4.2`

Implement prioritisation and ranking policy (M-27): score-ordered with capacity threshold.

| | |
|---|---|
| **Depends on** | `T06.4.1` |
| **Complexity** | M |
| **Deliverable** | Prioritisation policy |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Ranking reproducible within a score_model_version
- Capacity threshold bounds downstream cost

#### `T06.4.3` ⚠

Implement stage-skip prohibition (OQ-10): injected objects must carry their own evidence.

| | |
|---|---|
| **Depends on** | `T06.4.1` |
| **Complexity** | S |
| **Deliverable** | Stage-skip guard |
| **Blocks** | `T06.5.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Direct opportunity injection rejected without evidence lineage
- Principle 1 preserved

### Feature F06.5 — Phase 6 Exit

#### `T06.5.1` ⚠

Verify P6 exit: opportunities formulable, scored comparably, confidence proportionate, gates operational.

| | |
|---|---|
| **Depends on** | `T06.4.3`, `T06.4.2`, `T06.3.6`, `T06.3.4`, `T06.3.3`, `T06.3.5`, `T06.2.4`, `T06.2.5` |
| **Complexity** | L |
| **Deliverable** | P6 exit report |
| **Blocks** | `T07.1.1`, `T07.2.1` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Scores comparable within a model version
- Confidence ceiling demonstrably enforced
- Opportunity reaches ACTIVE (O-V3 satisfiable)

---

# Phase 7 — Solution & Validation

## Epic E07 — Solution & Validation Engines

**Goal.** Formulate solutions with explicit assumptions and test them. The platform's most heavily blocked phase.

**Entry dependencies.** `T00.3.2`, `T00.5.7`, `T01.2.1`, `T01.7.6`, `T01.7.7`, `T01.8.1`, `T02.2.4`, `T06.5.1`

### Feature F07.1 — Validation Foundations

#### `T07.1.1` ⚠

Resolve the Validation object / Experiment Registry boundary (C-05): Registry holds in-flight operational state, object holds concluded immutable record.

| | |
|---|---|
| **Depends on** | `T06.5.1` |
| **Complexity** | L |
| **Deliverable** | Decision record (C-05) |
| **Blocks** | `T07.1.2`, `T07.1.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Boundary stated
- Duplication eliminated
- Handoff at conclusion defined

#### `T07.1.2` ⚠

Define the validation method taxonomy (M-32) with evidence-based validation as the P7 baseline.

| | |
|---|---|
| **Depends on** | `T07.1.1` |
| **Complexity** | XL |
| **Deliverable** | Validation methodology spec |
| **Blocks** | `T07.1.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Method vocabulary defined
- Evidence-based baseline specified
- Limitation stated: novel propositions with no evidence cannot be tested this way

#### `T07.1.3`

Build the Experiment Registry capability per the reserved P1 placement.

| | |
|---|---|
| **Depends on** | `T07.1.1`, `T01.8.1` |
| **Complexity** | L |
| **Deliverable** | Experiment Registry |
| **Blocks** | `T07.1.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Holds mutable in-flight experiment state
- Distinct from immutable Validation objects
- Negative results never discarded

#### `T07.1.4`

Implement the experiment lifecycle (M-42) reusing D-02 vocabulary where applicable.

| | |
|---|---|
| **Depends on** | `T07.1.3` |
| **Complexity** | M |
| **Deliverable** | Experiment lifecycle |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- States defined for in-flight experiments
- Abandoned experiments recorded, not deleted

#### `T07.1.5` ⚠

Define what Validation validates (OQ-09): assumptions and claims on any object via lineage-restricted access.

| | |
|---|---|
| **Depends on** | `T07.1.2`, `T00.5.7` |
| **Complexity** | M |
| **Deliverable** | Validation scope decision |
| **Blocks** | `T07.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Scope recorded
- Consistent with the authority matrix

### Feature F07.2 — Solution Formulation

#### `T07.2.1`

Define solution granularity (M-29): concrete offering description without implementation design.

| | |
|---|---|
| **Depends on** | `T06.5.1` |
| **Complexity** | M |
| **Deliverable** | Granularity decision record |
| **Blocks** | `T07.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Depth fixed
- Assumptions testable at that depth
- No design work assigned to an engine that lacks it

#### `T07.2.2`

Implement solution formulation with structured assumptions (S-V2, S-V3).

| | |
|---|---|
| **Depends on** | `T07.2.1`, `T01.7.6` |
| **Complexity** | XL |
| **Deliverable** | Solution formulation |
| **Blocks** | `T07.2.3`, `T07.2.4`, `T07.2.5`, `T07.3.1` |
| **Independent** | Yes |

**Acceptance criteria**

- assumptions non-empty enforced
- Each has assumption_id, criticality, testability
- Solution with no assumptions rejected as invalid

#### `T07.2.3`

Implement the typed constraint model with evidence linkage (M-69).

| | |
|---|---|
| **Depends on** | `T07.2.2` |
| **Complexity** | L |
| **Deliverable** | Constraint model |
| **Blocks** | `T07.2.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Constraints typed and comparable
- Evidenced constraints linked to Facts
- Unevidenced judgements recorded as assumptions instead

#### `T07.2.4`

Implement problem-fit rationale via lineage-restricted read of underlying Problems (S-V4).

| | |
|---|---|
| **Depends on** | `T07.2.2`, `T00.5.7` |
| **Complexity** | L |
| **Deliverable** | Problem-fit demonstration |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Rationale references specific Problems
- Lineage-restricted access enforced
- Generic solutioning detectable

#### `T07.2.5`

Implement sibling candidate management preventing premature convergence (S-I3).

| | |
|---|---|
| **Depends on** | `T07.2.2` |
| **Complexity** | M |
| **Deliverable** | Candidate grouping |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Multiple candidates per opportunity coexist
- candidate_group populated
- Silent collapse rejected

#### `T07.2.6`

Implement feasibility assessment (S-V6) against the constraint model.

| | |
|---|---|
| **Depends on** | `T07.2.3` |
| **Complexity** | M |
| **Deliverable** | Feasibility assessment |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Assessment present on every Solution
- Infeasible candidates identifiable before validation spend

### Feature F07.3 — Validation Execution

#### `T07.3.1` ⚠

Implement claim-level validation targeting individual assumptions (V-V1).

| | |
|---|---|
| **Depends on** | `T07.1.5`, `T07.2.2`, `T01.7.7` |
| **Complexity** | XL |
| **Deliverable** | Validation execution |
| **Blocks** | `T07.3.2`, `T07.3.3`, `T07.3.4`, `T07.3.5`, `T07.3.8` |
| **Independent** | Yes |

**Acceptance criteria**

- tests_claim targets a specific assumption
- Whole-object validation rejected
- Multiple validations per Solution supported

#### `T07.3.2`

Implement falsifiability enforcement: every validation must be capable of returning a negative result.

| | |
|---|---|
| **Depends on** | `T07.3.1` |
| **Complexity** | L |
| **Deliverable** | Falsifiability check |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Tests incapable of failing rejected
- Confirmation bias countered structurally

#### `T07.3.3` ⚠

Implement negative-result preservation with equal status (V-I1).

| | |
|---|---|
| **Depends on** | `T07.3.1`, `T01.2.1` |
| **Complexity** | M |
| **Deliverable** | Negative result handling |
| **Blocks** | `T07.3.6`, `T07.3.7` |
| **Independent** | Yes |

**Acceptance criteria**

- Negative results stored ACTIVE, never REJECTED
- Suppression impossible
- Learning signal preserved

#### `T07.3.4`

Implement method recording to a reproducible standard (V-V2, V-V6).

| | |
|---|---|
| **Depends on** | `T07.3.1` |
| **Complexity** | M |
| **Deliverable** | Method recording |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- method_detail sufficient to repeat
- Opaque methods rejected

#### `T07.3.5`

Implement mandatory scope_limitations (V-V5).

| | |
|---|---|
| **Depends on** | `T07.3.1` |
| **Complexity** | M |
| **Deliverable** | Scope limitation recording |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- What was NOT established is stated
- Scope mismatch detectable

#### `T07.3.6`

Implement conflicting-result representation via CONTRADICTS between Validation objects.

| | |
|---|---|
| **Depends on** | `T07.3.3` |
| **Complexity** | M |
| **Deliverable** | Conflicting results |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Disagreeing tests both retained
- No silent selection of a winner

#### `T07.3.7` ⚠

Implement post-validation gate with human override (M-31).

| | |
|---|---|
| **Depends on** | `T07.3.3`, `T00.3.2` |
| **Complexity** | L |
| **Deliverable** | Post-validation gate |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Validation results have consequence
- Gate decision recorded
- Validation itself does not gate (V-I2 preserved)

#### `T07.3.8`

Implement backflow as a new research directive rather than reverse pipeline flow (OQ-11).

| | |
|---|---|
| **Depends on** | `T07.3.1`, `T02.2.4` |
| **Complexity** | M |
| **Deliverable** | Validation-driven research |
| **Blocks** | `T07.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Validation can raise a research directive
- No reverse flow in the pipeline
- Lineage remains acyclic

### Feature F07.4 — Phase 7 Exit

#### `T07.4.1` ⚠

Verify P7 exit: solutions carry testable assumptions, validations can fail, negative results preserved.

| | |
|---|---|
| **Depends on** | `T07.3.8`, `T07.3.7`, `T07.3.6`, `T07.3.5`, `T07.3.4`, `T07.2.6`, `T07.2.5`, `T07.2.4`, `T07.1.4` |
| **Complexity** | L |
| **Deliverable** | P7 exit report |
| **Blocks** | `T08.1.1` |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Every Solution has explicit assumptions
- Falsifiability enforced
- Negative results preserved with equal status
- Experiment Registry operational

---

# Phase 8 — Feedback

## Epic E08 — Execution Intake & Feedback Engine

**Goal.** Close the learning loop. Depends on resolving the platform's one structural break.

**Entry dependencies.** `T00.3.1`, `T00.3.2`, `T01.1.6`, `T01.5.5`, `T01.6.1`, `T01.7.8`, `T01.7.9`, `T02.1.4`, `T02.2.4`, `T06.3.6`, `T07.4.1`

### Feature F08.1 — Execution Boundary Resolution

#### `T08.1.1` ⚠ 🔺 **ESCALATION**

Resolve C-02: assign outcome intake to the Research Engine as an extension of its external-world boundary. ESCALATION: extends Research remit.

| | |
|---|---|
| **Depends on** | `T07.4.1`, `T00.3.1` |
| **Complexity** | L |
| **Deliverable** | Decision record (C-02) |
| **Blocks** | `T08.1.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Create authority for Execution Record assigned
- No tenth engine introduced
- Deviation recorded

#### `T08.1.2` ⚠

Implement outcome intake with mandatory evidence attachment (M-47).

| | |
|---|---|
| **Depends on** | `T08.1.1`, `T01.7.8` |
| **Complexity** | XL |
| **Deliverable** | Outcome intake mechanism |
| **Blocks** | `T08.1.3`, `T08.1.4`, `T08.1.5`, `T08.1.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Execution Records creatable
- Outcome reports themselves evidenced
- Intake path defined end to end

#### `T08.1.3`

Implement tiered outcome verification: mandatory evidence for all, sampled independent verification.

| | |
|---|---|
| **Depends on** | `T08.1.2` |
| **Complexity** | L |
| **Deliverable** | Outcome verification |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- outcome_verification populated
- Sample rate defined
- Reliability rate measured and published

#### `T08.1.4`

Implement attribution assessment distinguishing solution effect from external factors (X-V3).

| | |
|---|---|
| **Depends on** | `T08.1.2` |
| **Complexity** | L |
| **Deliverable** | Attribution assessment |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- attribution_assessment reasoned, not boilerplate
- external_factors recorded
- Overstated attribution rejected (X-I3)

#### `T08.1.5` ⚠

Implement prediction comparison against stored point-in-time predictions (X-V4).

| | |
|---|---|
| **Depends on** | `T08.1.2`, `T06.3.6` |
| **Complexity** | L |
| **Deliverable** | Prediction comparison |
| **Blocks** | `T08.2.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Original prediction retrievable unaltered
- Comparison recorded on the Execution Record

#### `T08.1.6`

Implement execution deviation recording.

| | |
|---|---|
| **Depends on** | `T08.1.2` |
| **Complexity** | M |
| **Deliverable** | Deviation recording |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- execution_deviations captured
- Outcomes from deviated execution flagged
- Misattribution to unexecuted solutions prevented

### Feature F08.2 — Learning

#### `T08.2.1` ⚠

Define learning targets (M-02, M-43): staged, beginning with confidence calibration and source trust.

| | |
|---|---|
| **Depends on** | `T08.1.5` |
| **Complexity** | XL |
| **Deliverable** | Learning target vocabulary |
| **Blocks** | `T08.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- change_target vocabulary defined
- Initial scope limited to calibration and source trust
- Widening criteria stated

#### `T08.2.2` ⚠

Implement Feedback Record creation from Execution Records only (FR-V6).

| | |
|---|---|
| **Depends on** | `T08.2.1`, `T01.7.9` |
| **Complexity** | L |
| **Deliverable** | Feedback Record creation |
| **Blocks** | `T08.2.3`, `T08.2.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Derivation restricted to Execution Records
- Learning from platform inferences impossible
- evidence_of_pattern required

#### `T08.2.3`

Implement overfitting guard: evidence_of_pattern must justify beyond a single outcome (FR-V4).

| | |
|---|---|
| **Depends on** | `T08.2.2` |
| **Complexity** | M |
| **Deliverable** | Overfitting guard |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Single-outcome lessons rejected
- Pattern across outcomes required

#### `T08.2.4` ⚠

Implement learning application to engine configuration per the T08.2.1 targets.

| | |
|---|---|
| **Depends on** | `T08.2.2`, `T01.1.6` |
| **Complexity** | L |
| **Deliverable** | Learning application |
| **Blocks** | `T08.2.5`, `T08.2.7`, `T08.2.8`, `T08.3.1`, `T08.3.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Configuration updated via the config store
- informs identifies affected engines
- No direct engine-to-engine coupling

#### `T08.2.5`

Implement reversal via versioned configuration rollback (M-34, FR-V3, FR-I1).

| | |
|---|---|
| **Depends on** | `T08.2.4` |
| **Complexity** | L |
| **Deliverable** | Reversal mechanism |
| **Blocks** | `T08.2.6` |
| **Independent** | Yes |

**Acceptance criteria**

- Every applied change reversible
- reversal_procedure actionable
- Rollback restores prior configuration version

#### `T08.2.6`

Implement cumulative drift determination (FR-I4).

| | |
|---|---|
| **Depends on** | `T08.2.5` |
| **Complexity** | L |
| **Deliverable** | Drift monitoring |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Total deviation from baseline determinable at any time
- Accumulated changes traceable to Feedback Records

#### `T08.2.7`

Implement batched learning cadence per orchestration cycle (M-10).

| | |
|---|---|
| **Depends on** | `T08.2.4`, `T01.6.1` |
| **Complexity** | M |
| **Deliverable** | Learning cadence |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Cadence defined and bounded
- Learning does not run per-outcome

#### `T08.2.8`

Implement the learning approval gate (OQ-05) as the third human gate.

| | |
|---|---|
| **Depends on** | `T08.2.4`, `T00.3.2` |
| **Complexity** | M |
| **Deliverable** | Learning approval gate |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Learning updates require approval before taking effect
- approval_record populated

### Feature F08.3 — Loop Stability

#### `T08.3.1` ⚠

Implement bounded change magnitude per learning cycle (M-70).

| | |
|---|---|
| **Depends on** | `T08.2.4` |
| **Complexity** | L |
| **Deliverable** | Magnitude bounds |
| **Blocks** | `T08.3.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Per-cycle change bounded
- Swing on noise prevented

#### `T08.3.2` ⚠

Implement source diversity floors that learning cannot reduce (M-70).

| | |
|---|---|
| **Depends on** | `T08.3.1`, `T02.1.4` |
| **Complexity** | L |
| **Deliverable** | Diversity floor |
| **Blocks** | `T08.3.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Learning cannot narrow the evidence base below the floor
- Self-reinforcement path closed

#### `T08.3.3` ⚠

Implement held-out evaluation not subject to learning (M-70).

| | |
|---|---|
| **Depends on** | `T08.3.2` |
| **Complexity** | XL |
| **Deliverable** | Held-out evaluation |
| **Blocks** | `T08.3.5` |
| **Independent** | Yes |

**Acceptance criteria**

- Evaluation set excluded from learning
- Drift detectable independently of platform self-assessment

#### `T08.3.4`

Implement behavioural loop closure: feedback triggers research directives, never becomes Evidence (FR-I2, E-I2).

| | |
|---|---|
| **Depends on** | `T08.2.4`, `T02.2.4` |
| **Complexity** | L |
| **Deliverable** | Loop closure |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Feedback raises research directives
- No Feedback Record enters the lineage graph as Evidence
- Lineage remains acyclic

#### `T08.3.5` ⚠

Implement empirical confidence recalibration against outcomes, refining S-1.

| | |
|---|---|
| **Depends on** | `T08.3.3`, `T01.5.5` |
| **Complexity** | L |
| **Deliverable** | Empirical recalibration |
| **Blocks** | `T08.4.1` |
| **Independent** | Yes |

**Acceptance criteria**

- Calibration refined from realised outcomes
- Prior calibration retained for comparison

### Feature F08.4 — Phase 8 Exit

#### `T08.4.1` ⚠

Verify P8 exit: loop closed, learning traceable and reversible, instability guarded.

| | |
|---|---|
| **Depends on** | `T08.3.5`, `T08.3.4`, `T08.2.8`, `T08.2.7`, `T08.2.6`, `T08.2.3`, `T08.1.6`, `T08.1.4`, `T08.1.3` |
| **Complexity** | L |
| **Deliverable** | P8 exit report |
| **Blocks** | — (nothing) |
| **Independent** | No — phase gate |

**Acceptance criteria**

- Outcomes comparable against predictions
- Every learning update traceable and reversible
- Loop instability guards operational
- Principle 5 demonstrably realised

---

# Cross-Cutting

## Epic E09 — Cross-Cutting Operations

**Goal.** Operational capabilities spanning all phases. Not blocking construction; blocking operation.

**Entry dependencies.** `T00.3.3`, `T00.3.5`, `T00.5.6`, `T00.7.1`, `T01.1.2`, `T01.6.1`, `T01.6.3`, `T06.1.1`

### Feature F09.1 — Observability & Cost

#### `T09.1.1`

Implement the cost model with per-engine costing feeding Orchestration budgets (M-56).

| | |
|---|---|
| **Depends on** | `T01.6.1` |
| **Complexity** | L |
| **Deliverable** | Cost model |
| **Blocks** | `T09.1.3` |
| **Independent** | Yes |

**Acceptance criteria**

- Per-engine cost attributable
- Budgets enforceable by Orchestration

#### `T09.1.2`

Implement observability: metrics plus explanation-derived quality signals (M-57).

| | |
|---|---|
| **Depends on** | `T00.5.6`, `T01.6.3` |
| **Complexity** | L |
| **Deliverable** | Observability capability |
| **Blocks** | `T09.1.4` |
| **Independent** | Yes |

**Acceptance criteria**

- Stage throughput and failure rates visible
- Explanation completeness measurable

#### `T09.1.3`

Implement resource limits and loop iteration bounding (M-37).

| | |
|---|---|
| **Depends on** | `T09.1.1` |
| **Complexity** | M |
| **Deliverable** | Resource governance |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Unbounded processing impossible
- Iteration bounded by resource budget

#### `T09.1.4`

Implement stage-level proxy quality measures per N-3.

| | |
|---|---|
| **Depends on** | `T00.3.3`, `T09.1.2` |
| **Complexity** | L |
| **Deliverable** | Quality measures |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Proxy measure operational per stage
- Feeds phase exit criteria

### Feature F09.2 — Security & Access

#### `T09.2.1`

Implement the tenancy discriminator on every object per N-5.

| | |
|---|---|
| **Depends on** | `T01.1.2` |
| **Complexity** | S |
| **Deliverable** | Tenancy reservation |
| **Blocks** | `T09.2.2` |
| **Independent** | Yes |

**Acceptance criteria**

- Discriminator present on all objects
- Unused but reserved

#### `T09.2.2`

Implement access control once the scope decision resolves (M-55).

| | |
|---|---|
| **Depends on** | `T09.2.1`, `T00.3.5` |
| **Complexity** | L |
| **Deliverable** | Access control |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Role-based access if single-tenant
- Partitioning if multi-tenant
- Licensing-derived restrictions honoured

### Feature F09.3 — Documentation Remediation

#### `T09.3.1`

Remediate C-07: document completed research to the platform's own evidence standards.

| | |
|---|---|
| **Depends on** | `T06.1.1` |
| **Complexity** | M |
| **Deliverable** | Remediated research documentation |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Findings, method and provenance recorded
- Project documentation consistent with Principles 1 and 3

#### `T09.3.2`

Confirm IOM closures (B-73 to B-81) against ratified decisions.

| | |
|---|---|
| **Depends on** | `T00.7.1` |
| **Complexity** | M |
| **Deliverable** | Closure confirmation report |
| **Blocks** | — (nothing) |
| **Independent** | Yes |

**Acceptance criteria**

- Each closure verified against its decision record
- No marker closed by implementation choice

---
