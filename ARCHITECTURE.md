# Architecture Reference

Complete architectural reference for the Opportunity Intelligence Platform.

Every statement here traces to a frozen source document or a ratified decision.
Where the architecture is undefined, that is stated explicitly rather than
filled in.

---

## 1. The Fixed Counts

**Playbook F8:** *"Nine engines, nine objects, ten stages, three components,
five principles. Fixed."*

Adding to any of these sets requires a ratified decision. R-7 did exactly that
once — adding the Feedback Record as a ninth object type — and it required
escalation and human sign-off.

| Set | Count | Members |
|---|---|---|
| Principles | 5 | Evidence before conclusions · Explainable decisions · Traceable lineage · Modular engines · Continuous learning |
| Pipeline stages | 10 | Evidence · Facts · Problems · Patterns · Opportunities · Solutions · Validation · Execution · Feedback · Orchestration |
| Engines | 9 | Research · Fact Extraction · Problem Intelligence · Pattern Intelligence · Opportunity Intelligence · Solution Intelligence · Validation · Feedback · Orchestration |
| Object types | 9 | Evidence · Fact · Problem · Pattern · Opportunity · Solution · Validation · Execution Record · Feedback Record |
| Shared components | 3 | Knowledge Store · Knowledge Graph · Experiment Registry |

---

## 2. The Pipeline

```
                    ┌──────────────────────────────────────────┐
                    │            ORCHESTRATION (stage 10)      │
                    │  scheduled batch · directive · bounded   │
                    └──────────────────────────────────────────┘
                                       │ invokes
   ┌───────────────────────────────────┼───────────────────────────────────┐
   ▼                                   ▼                                   ▼
┌─────────┐   ┌──────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐
│1 EVIDENCE│──▶│2 FACT│──▶│3 PROBLEM│──▶│4 PATTERN│──▶│5 OPPORTUNITY│
└─────────┘   └──────┘   └─────────┘   └─────────┘   └─────────────┘
   ▲ external                                              │
   │ world                                                 ▼
   │                                                 ┌──────────┐
   │                                                 │6 SOLUTION│
   │                                                 └──────────┘
   │                                                       │
   │                                                       ▼
   │                                                ┌────────────┐
   │                                                │7 VALIDATION│──▶ HANDOFF
   │                                                └────────────┘    (N-1)
   │                                                       │
   │                                                       ▼
   │                                              ┌──────────────────┐
   │                                              │8 EXECUTION RECORD│
   │                                              └──────────────────┘
   │                                                       │
   │                                                       ▼
   │                                              ┌─────────────────┐
   └──────── research directive ──────────────────│9 FEEDBACK RECORD│
             (NEVER lineage — R-8, AD-05)         └─────────────────┘
```

**The dashed return path is behavioural, not lineage.** Feedback never becomes
Evidence; it raises a *directive* that causes acquisition of new **external**
Evidence. This is R-8's resolution of contradiction C-04, generalised by AD-05.

### Stage / engine / object mapping

| Stage | Engine | Produces | Create authority |
|---|---|---|---|
| 1 | Research | Evidence | `Engine.RESEARCH` |
| 2 | Fact Extraction | Fact | `Engine.FACT_EXTRACTION` |
| 3 | Problem Intelligence | Problem | `Engine.PROBLEM_INTELLIGENCE` |
| 4 | Pattern Intelligence | Pattern | `Engine.PATTERN_INTELLIGENCE` |
| 5 | Opportunity Intelligence | Opportunity | `Engine.OPPORTUNITY_INTELLIGENCE` |
| 6 | Solution Intelligence | Solution | `Engine.SOLUTION_INTELLIGENCE` |
| 7 | Validation | Validation | `Engine.VALIDATION` |
| 8 | *(none)* | Execution Record | **NONE — C-02 open** |
| 9 | Feedback | Feedback Record | `Engine.FEEDBACK` |
| 10 | Orchestration | *(no object)* | — |

> **`CREATE_AUTHORITY` has 8 entries, not 9.** Execution Record is deliberately
> absent because **C-02** (Execution is a pipeline stage with an object but no
> engine) is unresolved. V7 fails closed for it: *"no engine holds create
> authority for ExecutionRecord [C-02 open]"*.

---

## 3. The Object Contract

### 17 universal required attributes

Every Intelligence Object carries these (composed: `identity` yields
`object_id`/`version`/`lineage_id`; `confidence` yields the three components).

| # | Attribute | Source |
|---|---|---|
| 1–3 | `object_id`, `version`, `lineage_id` | R-1, identity |
| 4 | `object_type` | IOM §1.1 |
| 5 | `produced_by_engine` | IOM §2.5 |
| 6 | `produced_at` | IOM §1.1 |
| 7 | `engine_configuration_ref` | N-4, N-7 |
| 8 | `derives_from` | R-6, D-01a |
| 9 | `explanation` | N-13 (four parts) |
| 10 | `evidence_reachable` | V4 |
| 11–13 | `evidential_support`, `assertion_confidence`, `effective_confidence` | R-3 |
| 14 | `status` | R-2 |
| 15 | `asserted_at` | R-4 |
| 16 | `independent_source_count` | N-16 Tier 1 |
| 17 | `tenancy` | N-5 |

### 6 optional attributes

`observed_at` · `valid_until` · `tags` (non-semantic, **never load-bearing**) ·
`duplicates` · `contradicts` · `supersedes` / `superseded_by`

---

## 4. Lifecycle — Seven States (R-2)

```
   PROPOSED ──accept──▶ ACTIVE ──supersede──▶ SUPERSEDED  (terminal)
      │                   │
      │ reject            ├── retract ──▶ RETRACTED       (terminal)
      ▼                   ├── upstream ─▶ INVALIDATED     (terminal)
   REJECTED               └── retention ▶ ARCHIVED        (terminal)
   (terminal)
```

| Rule | Statement |
|---|---|
| **I5** | Exactly one `ACTIVE` version per `lineage_id` |
| **E-V1** | Evidence **cannot** reach `INVALIDATED` — nothing upstream can invalidate it |
| **V9** | `status_reason` required whenever status ≠ `ACTIVE` |
| — | Terminal states never transition |
| **N-9** | Cascade triggers are `RETRACTED` and `INVALIDATED` **only** |
| **M-65** | `SUPERSEDED` does **not** cascade — re-derivation is OPEN |

### Partial retraction (T01.2.4, N-9, IOM §3.2)

> *"An object retaining at least one valid upstream reference is re-versioned,
> not invalidated."*

Cascade **spares** such an object and reports it as `partially_retracted`.
It does **not** re-version it — N-9 says cascade alters "status only, never
content", so producing the reduced-support version is the owning engine's act.
**That engine does not exist before P2**, so the reduced-support version is
currently produced by nothing. This is a recorded honest limitation.

---

## 5. Relationships — Ten Types (R-6)

`DERIVES_FROM` · `SUPPORTS` · `CONSTITUENT_OF` · `ADDRESSES` · `TESTS` ·
`OUTCOME_OF` · `SUPERSEDES` · `DUPLICATES` · `CONTRADICTS` · `INFORMS`

Closed set. Engines may not invent relationships.

> `DERIVES_FROM` and `SUPPORTS` are **deliberately distinct**: an object
> *derives from* the inputs its engine read, and is *supported by* the subset
> that evidences it. Conflating them would overstate evidential support.

`DERIVES_FROM` is typed `any → any` in the IOM relationship table. This matters:
it is why a Validation may legitimately derive from objects at different
pipeline depths, which is precisely how the cascade BFS ordering defect became
reachable.

---

## 6. Confidence (R-3, S-1, S-2)

### Two components, never conflated

| Component | Measures |
|---|---|
| `evidential_support` | How much independent external observation stands behind this |
| `assertion_confidence` | How certain the engine is in its own inference |

### The ceiling rule (V5)

```
effective_confidence ≤ min(upstream effective_confidence)
```

Evidence sets the ceiling; nothing constrains it from above. Certainty degrades
as reasoning moves further from observation (Article X).

### Five bands (S-1)

| Band | Range | Countable test |
|---|---|---|
| NEGLIGIBLE | 0.00–0.19 | qualitative |
| WEAK | 0.20–0.39 | ≥2 credible alternatives |
| MODERATE | 0.40–0.59 | exactly 1 credible alternative |
| STRONG | 0.60–0.79 | qualitative |
| VERY_STRONG | 0.80–1.00 | 0 credible alternatives |

**The operative test is alternative-counting**, not introspection.

### S-2's five exhaustive inputs

| # | Input |
|---|---|
| 1 | Independent source count (after independence grouping) |
| 2 | Source diversity — number of distinct source **types** |
| 3 | Corroboration depth |
| 4 | Contradiction presence |
| 5 | Upstream support |

> **"No other input."**

Seven normative properties: monotonic · saturating · diversity-weighted ·
independence-gated · contradiction-penalised · bounded by upstream ·
deterministic.

**Consequence:** source trust is *not* an input. N-20 records trust but it does
**not** score. Making it score requires **superseding S-2**.

### Sufficiency floors (S-4)

| Object | Minimum independent sources |
|---|---|
| Fact | 1 |
| Problem | **2** |
| Pattern | **3**, spanning ≥2 constituents |
| Opportunity / Solution | inherits upstream |
| Validation | 1 |
| Execution Record | 1 verified outcome report |
| Feedback Record | **2 Execution Records** |

Checked at acceptance. Below threshold is **rejected**, not accepted with low
confidence.

---

## 7. Validation and Integrity

### V1–V12 — acceptance-time (run once, at write)

| # | Rule |
|---|---|
| V1 | All universal required attributes present and non-empty |
| V2 | `derives_from` non-empty (all types except Evidence) |
| V3 | Every reference resolves to an existing object version |
| V4 | A path to at least one Evidence object is traversable |
| V5 | Confidence ceiling: `effective ≤ min(upstream)` |
| V6 | Explanation references actual inputs |
| V7 | Producing engine holds create authority |
| V8 | `observed_at ≤ asserted_at ≤ produced_at` |
| V9 | `status_reason` present when status ≠ ACTIVE |
| V10 | No lineage cycle introduced |
| V11 | Version and `lineage_id` integrity |
| V12 | All relationships conform to the closed taxonomy |

### I1–I8 — continuous invariants (must hold at every moment)

| # | Constraint |
|---|---|
| I1 | Content immutable; only status may transition |
| I2 | `object_id` never reused |
| I3 | Lineage references never repoint |
| I4 | Referenced objects never hard-deleted |
| I5 | Exactly one ACTIVE version per `lineage_id` |
| I6 | Upstream RETRACTED/INVALIDATED ⇒ dependents INVALIDATED |
| I7 | Confidence ceiling holds after any upstream change |
| I8 | REJECTED objects never consumed as input |

**68 acceptance rules total**: V1–V12, I8, then per-type E-V1…6, F-V1…6,
P-V1…6, PT-V1…6, **O-V1…7 (seven)**, S-V1…6, V-V1…6, X-V1…6, FR-V1…6.

### Enforcement (N-8)

> *"The Knowledge Store enforces acceptance at the `PROPOSED → ACTIVE`
> transition. The rule set is specified in the Intelligence Object Model, not
> embedded in the Store. Mechanism and policy are separated."*

Scope limit: the Store enforces **structural** rules only. Semantic judgement
(notably F-V6) goes through the semantic hook, with a measured residual error
rate.

**The acceptance path evaluates every rule and never short-circuits** —
`FailureRecord.failed_rules` is a tuple of *all* failures. This matters: N-20's
gate sequence deliberately adopts the *opposite* convention (AS-2).

---

## 8. Store and Graph (N-6)

| | Knowledge Store | Knowledge Graph |
|---|---|---|
| Authority | **Authoritative** | **Derived index** |
| Lineage | Objects carry their own | Indexes what objects assert |
| Failure mode | Correctness | Performance only |
| Rebuild | — | From objects alone, at any time |

> *"The graph can be the reason the platform is slow, never the reason it is
> wrong."*

`MAX_LINEAGE_DEPTH = MAX_CASCADE_DEPTH = 32`. The lineage graph is acyclic under
R-8 and V10, which is what guarantees traversal termination.

---

## 9. Orchestration (N-17, N-18, N-11)

| Property | Decision |
|---|---|
| Control model | **Scheduled batch** — engines invoked on a defined cycle |
| Reactive vs directive | **Directive.** Orchestration executes a plan; it does not react to object availability |
| Iteration bounding | Every cycle bounded by **work-set size** and **wall-clock budget** |
| Loop termination | The platform has no terminal state, but **every cycle does** |
| Concurrency | Stages 1–2 concurrent; stages 3–9 serialised (N-11) |
| Failure handling | Recorded, cycle continues, never masked as completion (N-10) |

`ENGINE_STAGE` has 8 entries (Orchestration absent, stage 8 absent).
`CONCURRENT_STAGES = {1,2}`, `SERIALISED_STAGES = {3..9}`.

`InvocationOutcome` has **5** members: `PRODUCED` · `EMPTY` · `FAILED` ·
`NOT_ATTEMPTED` · `REJECTED_OUT_OF_ORDER`.

### Failure representation (N-10)

> *"A stage that produced nothing because it failed is distinguishable from a
> stage that produced nothing because it found nothing. This distinction is
> mandatory at every stage."*

Failure records live **outside** the object model, co-located with
configuration. They never enter the lineage graph.

**M-36's policy half remains OPEN** — N-10 closes *representation*; retry, skip,
halt and compensate are undefined and deliberately not implemented.

---

## 10. Human Gates (N-2) — Exactly Three

| Gate | Transition | Decides |
|---|---|---|
| **G1** | Stage 5 → 6 | Which scored opportunities proceed to solutioning |
| **G2** | Stage 7 → handoff | Whether a validated solution is released |
| **G3** | Stage 9 | Whether a learning update takes effect |

> *"Human judgement enters the platform at exactly three gates. Everywhere else
> the platform runs autonomously."*

No new object states: a gate rejection is `PROPOSED → REJECTED` with
`status_reason`. **Engines never block** awaiting a gate.

> **This is the source of D-1.** `T02.2.4` AC2 requires "approval per human-gate
> decision" for research targets — a fourth gate N-2 forecloses. Under Article
> XI, N-2 governs and the acceptance criterion is unsatisfiable as written.

---

## 11. Configuration Isolation (CI-1, N-7)

> *"Configuration data is infrastructure state, not intelligence. It may be
> stored inside the Knowledge Store for operational reasons, but it must remain
> logically isolated from Intelligence Objects and must never participate in
> reasoning, scoring, pattern detection, or lineage."*

Enforced at the access boundary, not by convention: the configuration module
shares no type with the object model, returns no Intelligence Object, and
exposes no path into a lineage graph.

---

## 12. Phase 2 Architecture (N-20 … N-23)

### Source taxonomy — closed, by acquisition channel (N-20 §5.1)

`PUBLISHED_EDITORIAL` · `MARKETPLACE_LISTING` · `USER_GENERATED_REVIEW` ·
`USER_GENERATED_DISCUSSION` · `SUPPORT_INTERACTION` · `STRUCTURED_DATASET` ·
`REGULATORY_FILING` · `VENDOR_PUBLICATION`

Exactly one member per source. Assigned by the Research Engine at acquisition.

> **AS-0:** these eight members are **selected, not derived**. The corpus
> enumerates zero source types.

### The acquisition gate sequence (N-20 §5.2.1)

| # | Gate | Question | Refusal reason |
|---|---|---|---|
| 1 | **Scope** | Does an in-effect directive cover this target? | `OUT_OF_SCOPE` |
| 2 | **Typability** | Does the source map to a taxonomy member? | `UNTYPABLE_CHANNEL` |
| 3 | **Rights** | May this material be taken and kept? | `REFUSED_BY_RIGHTS` |

**Halts at the first refusal**, so exactly one reason is ever produced.

> **AS-1/AS-2:** the order is selected (6 permutations were legal), and
> halt-first **inverts** the N-08/N-10 all-failures convention.

### Rights vocabulary (N-21 §5.5) — closed

**Acquisition:** `PERMITTED` · `PROHIBITED` · `UNASSESSED`
**Retention:** `RETAIN_FULL` · `RETAIN_REFERENCE_ONLY` · `RETAIN_NONE` · `UNASSESSED`

`UNASSESSED` **fails closed** — silence is not permission. Policy is owned by a
human authority **outside** the platform (N-1, Article VI).

### Coverage model (N-22)

```
coverage     = |represented members| / |frame|
gaps         = frame \ represented members
out_of_frame = count of sources refused at gate 2
```

**Gap reasons:** `NOT_ATTEMPTED` · `INACCESSIBLE` · `REFUSED_BY_RIGHTS` ·
`NO_MATERIAL_FOUND` · `OUT_OF_SCOPE`

A report showing `coverage = 1.0` with `out_of_frame > 0` is **not** a claim of
complete coverage. Coverage is a **report, not a gate** — it rejects no object.

### Research directives (N-23)

**States:** `RAISED` · `IN_EFFECT` · `FULFILLED` · `CANCELLED` · `EXPIRED`
— deliberately **disjoint** from R-2's seven object states.

**Originators (closed):** `EXTERNAL_COMMISSION` · `FEEDBACK_RESEARCH_TRIGGER` ·
`VALIDATION_BACKFLOW`. **The platform never self-initiates research.**

A directive **scopes**; it does not **schedule**. Scheduling remains N-17's.

---

## 13. Module Dependency Structure

```
enums ─┬─▶ contract ─┬─▶ acceptance ─┬─▶ store ◀── (sole broad integrator)
       │             │               │
       ├─▶ identity  ├─▶ lineage     ├─▶ integrity
       ├─▶ lifecycle ├─▶ graph       ├─▶ cascade
       ├─▶ calibration (enums only)  └─▶ 9 object-type modules
       ├─▶ retention (enums + graph)
       └─▶ orchestration (acceptance + contract + enums)

contract ──▶ source  (Phase 2; imports oip.contract only)
```

| Invariant | Verified by |
|---|---|
| Import graph is a **DAG** | `closure_t01_8_1.py` |
| `store` is the **sole** broad integrator (≥15 imports); all others ≤6 | `closure_t01_8_1.py` |
| `calibration` imports only `enums` | boundary check |
| `retention` imports only `enums` + `graph` | boundary check |
| `source` imports only `contract` | CI-1 boundary |

---

## 14. Precedence (Article XI)

1. **The Constitution**
2. **Decision records**
3. **Ratification annotations**
4. **Intelligence Object Model**
5. **PKP v2 Master Reference**
6. **Implementation Backlog**

This has already resolved two live conflicts:

| Conflict | Resolution |
|---|---|
| IOM §3.1 says `evidential_support` "reflects source reliability"; S-2 excludes trust | **S-2 governs.** The IOM sentence states intent, unrealised |
| Backlog `T02.2.4` AC2 requires a human gate; N-2 fixes exactly three | **N-2 governs.** The AC is unsatisfiable as written (D-1) |

---

## 15. What Is Deliberately Undefined

The architecture's most important property is that it **knows what it does not
know**. These are open, surfaced in code, and fail closed:

| Marker | Undefined |
|---|---|
| C-02 | Execution Record has no producing engine |
| M-02 / M-43 | Learning target vocabulary and Feedback write authority |
| M-16 (scoring) | Whether trust weights `evidential_support` |
| M-17 (stopping) | When the platform has researched enough |
| M-18b | Robots and rate-limit conduct |
| M-36 (policy) | Retry / skip / halt / compensate |
| M-65 | Re-derivation on supersession |
| M-70 | Feedback loop instability guard |
| OQ-10 / OQ-11 | Stage skipping; backflow permission |

**Twelve forbidden closures** were verified as *not invented* during Phase 1:
severity/frequency scales · scoring dimensions · per-type pattern thresholds ·
validation method vocabulary · verification standard · learning-target
vocabulary · constraint model · gate ownership · problem dedup · feedback
application · instability guard · success measure.
