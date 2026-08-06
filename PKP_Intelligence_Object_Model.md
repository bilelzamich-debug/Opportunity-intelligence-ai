# Opportunity Intelligence Platform
## Intelligence Object Model (IOM) — Complete Specification

**Document type:** Contract specification
**Status:** Authoritative for object semantics; subject to ratification of the decisions in §0.4
**Parent document:** PKP v2 — Master Reference
**Resolves:** CONTRADICTION-08 / MISSING-35 (object model has no defined contents)
**Scope note:** No engine, pipeline stage, shared component, principle or roadmap phase is added, removed or renamed by this document.

---

## 0. Foundations

### 0.1 Purpose of This Document

Architecture Decision 2 ("Intelligence contracts") establishes that engines interact **only** through Intelligence Objects. Principle 4 forbids any other channel. The object model is therefore not a data dictionary — it is the totality of the platform's internal interface surface.

PKP v2 identified this as the platform's largest gap: eight object names with no defined contents (MISSING-35), making the stated contract surface empty (CONTRADICTION-08). This document supplies those contents.

Once ratified, the following hold:

1. Any engine may be reimplemented or replaced without consulting any other engine, provided it honours the object contracts defined here.
2. Any object encountered anywhere in the platform is interpretable without reference to the engine that produced it.
3. Every conformance question — is this object valid, may this engine write it, what does its confidence mean — is answerable from this document alone.

### 0.2 What This Document Specifies

For each of nine object types: purpose, responsibilities, existence rationale, lifecycle, state transitions, required and optional attributes, validation rules, integrity constraints, versioning, confidence, lineage, inter-object relationships, engine create/modify/read authority, owning pipeline stage, failure cases, and worked examples.

Plus four cross-cutting frameworks that no single object can define alone (§2), an object transformation diagram (§4), and the residual gap register (§5).

### 0.3 What This Document Does Not Specify

- **Storage representation.** Attributes are semantic requirements, not schemas, field types, or serialisation formats.
- **Interfaces.** No access methods, no query semantics, no protocols.
- **Engine internals.** How an engine decides what to produce is out of scope; only what it may produce is in scope.
- **Code, APIs, or user interfaces.** Excluded by standing instruction.

Attribute names appear in `snake_case` purely as stable identifiers for cross-referencing within this specification. They carry no implementation commitment.

### 0.4 Decisions Required to Specify the Object Model

Seven markers from PKP v2 cannot be deferred: the object model is undefinable while they remain open. Each is resolved below as an explicit decision, stating alternatives rejected and consequences accepted, per the standing marker-resolution rule (PKP v2 §15).

**These are architecture decisions and require ratification.** They are recorded here because specification forced them, not because authority to make them was assumed. Each preserves existing v1 architecture; none adds a component.

---

#### D-01 — Objects are immutable; change produces a new version
*Resolves MISSING-08 (object mutability undefined)*

**Decision.** Intelligence Objects are immutable once created. Any change produces a new version with a new identity, linked to its predecessor by a `SUPERSEDES` relationship. Only lifecycle `status` may transition without creating a version (see D-02).

**Alternatives rejected.**
- *Mutable in place.* Rejected: destroys the historical record Principle 3 requires, and makes prediction-versus-outcome comparison impossible, which Principle 5 depends on. The Feedback Engine must be able to retrieve what the platform believed at the time it believed it.
- *Mutable with change log.* Rejected: reconstructing prior state from a log is derivation, not record. Lineage would reference objects whose content at reference time is no longer recoverable.

**Consequences accepted.** Storage grows monotonically (compounds MISSING-31, retention). Every reference must be version-specific or explicitly version-floating (see D-01a). Supersession chains require traversal.

**D-01a — Reference binding.** Lineage references bind to a **specific version**. Rationale: an object's justification must remain stable. If a Fact is superseded, the Problem derived from the earlier Fact remains derived from what it was actually derived from; whether the Problem should be revised is a separate judgement, recorded via `status`, not by silently repointing its lineage.

---

#### D-02 — Canonical seven-state lifecycle
*Resolves MISSING-45 (no lifecycle or status model)*

**Decision.** All object types share one lifecycle vocabulary. Not every state is reachable for every type; per-type reachability is specified in each object's State Transitions subsection.

| State | Meaning | Terminal |
|---|---|---|
| `PROPOSED` | Created by an engine; not yet structurally accepted into the knowledge base | No |
| `ACTIVE` | Structurally valid; part of the platform's current knowledge | No |
| `SUPERSEDED` | Replaced by a newer version of the same object | Yes |
| `REJECTED` | Declined by the producing engine or a gate; retained for explanation and learning | Yes |
| `RETRACTED` | Withdrawn at source; applies where the external world revokes the basis | Yes |
| `INVALIDATED` | An upstream dependency was retracted or invalidated; this object is no longer supported | Yes |
| `ARCHIVED` | Removed from active working set under retention policy; lineage preserved | Yes |

**Alternatives rejected.**
- *Binary valid/invalid.* Rejected: cannot distinguish rejection (a decision, and learning signal per Principle 5) from invalidation (a consequence) from retraction (an external event). These have different meanings for the Feedback Engine.
- *Per-object-type state models.* Rejected: nine vocabularies would make cross-object status reasoning impossible and violate the uniformity a contract surface requires.

**Consequences accepted.** `REJECTED` objects persist, resolving OPEN QUESTION-04 toward retention and accepting the storage growth. Status transitions are the sole permitted non-versioning mutation, which is a deliberate, narrow exception to D-01.

> **MISSING-58:** No engine owns cascade invalidation. When Evidence is retracted, some component must walk the lineage graph and transition dependents to `INVALIDATED`. No engine in v1 §4 has this responsibility, and assigning it would add an engine — out of scope here. Blocking for P1.

---

#### D-03 — Two-component confidence with a monotonic ceiling
*Resolves MISSING-15 (no confidence model)*

**Decision.** Confidence has two orthogonal components, both required on every object except where stated:

| Component | Meaning | Determined by |
|---|---|---|
| `evidential_support` | Strength, breadth and independence of the evidence beneath this object | Computed from lineage |
| `assertion_confidence` | The producing engine's certainty in its own inferential step | Asserted by the producing engine |

These are separable and must not be conflated. PKP v2 §2.1 requires that an object may be *well-evidenced and low-confidence* (abundant evidence, weak inference) or *poorly-evidenced and high-confidence* (obvious inference, thin evidence). A single number cannot express this, and the second case is precisely the one that must be detectable.

**Propagation rule (the ceiling rule).** For any derived object:

```
effective_confidence ≤ min(effective_confidence of all upstream objects)
```

Confidence is monotonically non-increasing along the pipeline. This enforces PKP v2 §3.4.2 (certainty degrades with inferential distance) and directly counters the confidence-inflation failure mode identified as the platform's most consequential (PKP v2 §4.5 / §10.1). An Opportunity can never be more certain than the weakest Fact beneath it.

**Scale.** Both components are expressed on `0.00`–`1.00`, with mandatory band labels to prevent false precision:

| Band | Range | Interpretation |
|---|---|---|
| `NEGLIGIBLE` | 0.00–0.19 | Present but not usable as support |
| `WEAK` | 0.20–0.39 | Indicative only |
| `MODERATE` | 0.40–0.59 | Actionable with corroboration |
| `STRONG` | 0.60–0.79 | Actionable |
| `VERY_STRONG` | 0.80–1.00 | Actionable without qualification |

**Alternatives rejected.**
- *Single scalar.* Rejected: cannot distinguish evidential weakness from inferential weakness, collapsing the distinction Principle 1 depends on.
- *Categorical only.* Rejected: prevents the ceiling rule from being computable.
- *No confidence.* Rejected: the vision requires scoring and comparison.

**Consequences accepted.** Two numbers must be justified rather than one. Bands invite treating the midpoint as meaningful.

> **MISSING-59:** The function computing `evidential_support` from lineage is undefined. Inputs are identifiable from v2 (independent source count, source diversity, corroboration, contradiction) but weighting is not. Blocking for P4 onward.

> **MISSING-60:** No calibration mechanism. Nothing establishes that one engine's `assertion_confidence` of 0.7 means what another's does, making the ceiling rule arithmetically valid but semantically unsound across engines. This is the deepest unresolved issue in the confidence model.

---

#### D-04 — Explicit temporal validity, no automatic decay
*Resolves MISSING-46 (no temporal model)*

**Decision.** Every object carries `asserted_at` (when the platform formed the claim) and `observed_at` (when the underlying reality was observed, which may substantially precede assertion). Objects may optionally carry `valid_until`. Confidence does **not** decay automatically with time.

**Alternatives rejected.**
- *Automatic time decay.* Rejected: decay rates are domain-specific and unknowable in general; an automatic rate would be an invented business rule, and would silently alter stored confidence, breaching immutability.
- *No temporal model.* Rejected: PKP v2 §10.3 establishes staleness as unmanaged in a continuously looping platform.

**Consequences accepted.** Staleness is detectable (timestamps exist) but not automatically actioned. Some component must eventually assess currency — unassigned, see below.

> **MISSING-61:** No component owns staleness assessment. Timestamps make ageing visible but no engine is responsible for acting on it. Related to MISSING-13 (pattern temporal validity).

---

#### D-05 — Facts are canonical claims with multiple evidence attachments
*Resolves MISSING-11 (fact identity and deduplication)*

**Decision.** A Fact represents a **canonical claim**, not an extraction event. When extraction yields a claim semantically equivalent to an existing Fact, a new `evidence_attachment` is added to that Fact rather than a new Fact being created. Each attachment records its own Evidence reference, positional anchor, and source independence assessment.

**Alternatives rejected.**
- *One Fact per extraction.* Rejected: makes corroboration uncountable. Ten sources stating the same thing would appear as ten independent facts, structurally guaranteeing the frequency-inflation failure mode (PKP v2 §4.2, §4.4).
- *Deduplication as a downstream concern.* Rejected: pushes the problem to Pattern Intelligence, which lacks the evidence-level detail to resolve it.

**Consequences accepted.** Fact Extraction must perform semantic equivalence judgement, which is fallible in both directions (over-merging hides source disagreement; under-merging inflates frequency). Adding an attachment modifies a Fact, requiring a new version under D-01 — so corroboration produces version churn on frequently-attested Facts.

> **MISSING-62:** No semantic equivalence criterion. What makes two extracted claims "the same claim" is undefined, and both error directions are damaging. Blocking for P3.

---

#### D-06 — Closed relationship taxonomy
*Resolves MISSING-32 (no relationship taxonomy)*

**Decision.** Exactly ten relationship types exist. The set is closed; engines may not invent relationships. Every relationship records the asserting engine and timestamp.

| Relationship | From → To | Cardinality | Mandatory | Meaning |
|---|---|---|---|---|
| `DERIVES_FROM` | any → any | many:many | Yes (except Evidence) | Lineage. The transformation path. |
| `SUPPORTS` | Fact → Problem, Problem → Pattern | many:many | Yes | Evidential backing, distinct from derivation |
| `CONSTITUENT_OF` | Problem → Pattern | many:1 | Yes for Pattern | Aggregate membership |
| `ADDRESSES` | Solution → Opportunity/Problem | many:many | Yes for Solution | Intent to resolve |
| `TESTS` | Validation → assumption/claim | many:1 | Yes for Validation | Subject of a test |
| `OUTCOME_OF` | Execution Record → Solution | many:1 | Yes for Execution Record | Real-world result |
| `SUPERSEDES` | version → prior version | 1:1 | On versioning | Version chain |
| `DUPLICATES` | any → same type | many:many | No | Recognised equivalence not merged |
| `CONTRADICTS` | any → same type | many:many | No | Mutual incompatibility |
| `INFORMS` | Feedback Record → target | 1:many | Yes for Feedback Record | Learning influence |

`DERIVES_FROM` and `SUPPORTS` are deliberately distinct: a Problem *derives from* the Facts the engine read, and is *supported by* the subset that evidences it. These sets are not always identical, and conflating them would overstate evidential support.

**Alternatives rejected.**
- *Open/extensible taxonomy.* Rejected: engines would assert relationships of private conception, making the graph semantically incoherent — the failure PKP v2 §5.3 identifies.
- *Lineage only.* Rejected: cannot express contradiction (OPEN QUESTION-03), duplication, or aggregation.

**Consequences accepted.** Relationships not expressible in these ten cannot be represented without amending this document. This rigidity is intentional.

---

#### D-07 — The Feedback Record is required
*Resolves CONTRADICTION-03 (Feedback is a stage and engine but not an object)*

**Decision.** A ninth object type, the **Feedback Record**, is specified (§3.9).

**Rationale.** This is not an addition to the architecture; it is the completion of one. v1 §3 defines a Feedback stage and v1 §4 defines a Feedback Engine. Every other stage-engine pair produces a persisted object. Without one, learning updates change platform behaviour with no persistent record — which breaches Principle 3 (traceable lineage), makes learning irreversible in contradiction of Principle 5's requirements as expanded in PKP v2 §2.5, and leaves the untraceable-drift failure mode (PKP v2 §4.8) unmitigated.

The object is therefore **required by v1's own principles**, and specifying it resolves a contradiction rather than introducing a feature.

**Alternatives rejected.**
- *No feedback object.* Rejected: leaves Principle 3 violated by design.
- *Feedback as Evidence.* Rejected: this is CONTRADICTION-04, and would grant internally-generated content the grounding status Evidence exists to guarantee.

**Consequences accepted.** The object model has nine types where v1 named eight. This is flagged prominently as a resolution of a v1 contradiction requiring ratification, not a silent expansion.

---

#### D-08 — Objects carry their own lineage; the graph is a derived index
*Partially resolves CONTRADICTION-06 (Store/Graph boundary), provisionally*

**Decision, provisional.** For object model purposes: objects carry their own lineage and relationship references as attributes. The Knowledge Graph is a **derived traversal index** over relationships the objects already assert, and is not an independent source of truth.

**Rationale.** A contract surface must be self-contained. If an object's lineage lived only in the graph, the object would be uninterpretable in isolation, violating the self-describing requirement (PKP v2 §6.1). Single-authority also eliminates the divergence failure mode (PKP v2 §5.3).

**Alternatives rejected.**
- *Graph as sole authority.* Rejected: objects become non-self-describing.
- *Both authoritative.* Rejected: dual sources of truth; guarantees divergence.

**Status.** Provisional. CONTRADICTION-06 is a knowledge-architecture decision whose full resolution exceeds this document's scope. This decision constrains it but does not settle it — the reverse-traversal and query characteristics of the Knowledge Graph remain open.

---

### 0.5 Decision Summary

| ID | Resolves | Decision | Ratification |
|---|---|---|---|
| D-01 | MISSING-08 | Immutable objects, versioned | Required |
| D-01a | — | Version-specific lineage binding | Required |
| D-02 | MISSING-45 | Seven-state canonical lifecycle | Required |
| D-03 | MISSING-15 | Two-component confidence, ceiling rule | Required |
| D-04 | MISSING-46 | Explicit temporal validity, no decay | Required |
| D-05 | MISSING-11 | Canonical claims, multiple attachments | Required |
| D-06 | MISSING-32 | Closed ten-type relationship taxonomy | Required |
| D-07 | CONTRADICTION-03 | Feedback Record specified | **Required — adds ninth object type** |
| D-08 | CONTRADICTION-06 (partial) | Objects authoritative, graph derived | Required, provisional |

Five new markers arose from these decisions: MISSING-58 (cascade invalidation owner), MISSING-59 (support function), MISSING-60 (confidence calibration), MISSING-61 (staleness owner), MISSING-62 (semantic equivalence).

---

## 1. Universal Object Model

Binding on all nine types. Per-type sections specify only additions and restrictions.

### 1.1 Universal Required Attributes

Realising U1–U9 from PKP v2 §6.2.

| Attribute | Requirement | Satisfies | Constraint |
|---|---|---|---|
| `object_id` | Unique, stable, permanent identifier | U1 | Never reused, never reassigned |
| `object_type` | One of the nine defined types | U2 | Closed set |
| `version` | Monotonic integer within a supersession chain | U1, D-01 | Starts at 1 |
| `lineage_id` | Stable identifier shared across all versions of the same logical object | U1, D-01 | Constant across versions |
| `produced_by_engine` | The engine that created this object | U3 | One of the nine engines; must hold create authority (§2.5) |
| `produced_at` | Creation timestamp | U3 | — |
| `engine_configuration_ref` | Reference to the engine configuration in force at production | U3 | See MISSING-63 |
| `derives_from` | Lineage references to upstream objects | U4 | Non-empty except Evidence; version-specific per D-01a |
| `explanation` | Why this object exists in this form | U5 | Non-empty; must reference specific inputs |
| `evidence_reachable` | Assertion that a resolvable path to Evidence exists | U6 | Must verify true at acceptance |
| `evidential_support` | Evidence-strength component | U7, D-03 | 0.00–1.00 plus band |
| `assertion_confidence` | Engine's inferential certainty | U7, D-03 | 0.00–1.00 plus band |
| `effective_confidence` | Ceiling-constrained confidence | U7, D-03 | ≤ min(upstream effective_confidence) |
| `asserted_at` | When the platform formed the claim | U8, D-04 | — |
| `observed_at` | When the underlying reality was observed | U8, D-04 | ≤ `asserted_at` |
| `status` | Lifecycle state | U9, D-02 | One of seven states |
| `status_reason` | Why the object holds its current status | U9, P2 | Required for all non-`ACTIVE` states |

> **MISSING-63:** No component owns engine configuration (PKP v2 MISSING-34). `engine_configuration_ref` is required by Principle 3 but has no defined referent. Blocking for P1.

### 1.2 Universal Optional Attributes

| Attribute | Meaning | When applicable |
|---|---|---|
| `valid_until` | Expected expiry of the claim's currency | When determinable |
| `duplicates` | Recognised equivalents not merged | On detection |
| `contradicts` | Objects mutually incompatible with this one | On detection |
| `supersedes` | Prior version | Version > 1 |
| `superseded_by` | Successor version | On supersession |
| `tags` | Non-semantic classification | Never load-bearing |

`tags` must never carry meaning any engine depends on — that would constitute a private channel and breach Principle 4.

### 1.3 Universal Validation Rules

Checked at acceptance (`PROPOSED` → `ACTIVE`). Failure blocks acceptance.

| # | Rule | Source |
|---|---|---|
| V1 | All universal required attributes present and non-empty | §1.1 |
| V2 | `derives_from` non-empty (all types except Evidence) | P1 |
| V3 | Every `derives_from` reference resolves to an existing object version | P3 |
| V4 | A path to at least one Evidence object is traversable | P1, U6 |
| V5 | `effective_confidence` ≤ min(upstream `effective_confidence`) | D-03 |
| V6 | `explanation` non-empty and references at least one input object | P2 |
| V7 | `produced_by_engine` holds create authority for this type | §2.5, P4 |
| V8 | `observed_at` ≤ `asserted_at` ≤ `produced_at` | D-04 |
| V9 | `status_reason` present when `status` ≠ `ACTIVE` | P2 |
| V10 | No lineage cycle is introduced | P3 |
| V11 | `version` = predecessor `version` + 1; `lineage_id` unchanged | D-01 |
| V12 | All relationships drawn from the closed taxonomy | D-06 |

V10 is critical: CONTRADICTION-04 (feedback re-entering as Evidence) makes lineage cycles structurally possible, and a cycle renders lineage traversal non-terminating, breaking Principle 3 for every object in the cycle.

### 1.4 Universal Integrity Constraints

Hold continuously, not only at acceptance.

| # | Constraint | Violation consequence |
|---|---|---|
| I1 | Content is immutable; only `status` may transition | Silent history rewrite |
| I2 | `object_id` is never reused | Lineage ambiguity |
| I3 | Lineage references never repoint | Retrospective justification change |
| I4 | Referenced objects are never hard-deleted | Broken lineage |
| I5 | Exactly one version per `lineage_id` is `ACTIVE` | Ambiguous current knowledge |
| I6 | Upstream `RETRACTED`/`INVALIDATED` ⇒ dependents `INVALIDATED` | Conclusions on withdrawn evidence |
| I7 | Confidence ceiling holds after any upstream change | Confidence inflation |
| I8 | `REJECTED` objects are never consumed as input | Rejected knowledge re-entering |

I6 is currently unenforceable — see MISSING-58.

---

## 2. Cross-Object Frameworks

### 2.1 Lifecycle and State Transition Model

Canonical transitions. Per-type restrictions appear in each object's section.

```
                    ┌──────────────┐
                    │   PROPOSED   │  engine creates
                    └──────┬───────┘
                 accept    │    reject
              ┌────────────┴────────────┐
              ▼                         ▼
        ┌──────────┐              ┌──────────┐
        │  ACTIVE  │              │ REJECTED │ (terminal)
        └────┬─────┘              └──────────┘
             │
   ┌─────────┼─────────┬──────────────┐
   ▼         ▼         ▼              ▼
┌────────┐ ┌─────────┐ ┌───────────┐ ┌──────────┐
│SUPER-  │ │RETRACTED│ │INVALIDATED│ │ ARCHIVED │
│SEDED   │ │         │ │           │ │          │
└────────┘ └─────────┘ └───────────┘ └──────────┘
 (all terminal)
```

**Transition rules.**

| Transition | Trigger | Authority | Versioning |
|---|---|---|---|
| → `PROPOSED` | Engine creates | Producing engine | New object |
| `PROPOSED` → `ACTIVE` | All V1–V12 pass | Acceptance check | None |
| `PROPOSED` → `REJECTED` | Engine or gate declines | Producing engine; gate owner undefined (MISSING-26) | None |
| `ACTIVE` → `SUPERSEDED` | Newer version accepted | Producing engine | Successor created |
| `ACTIVE` → `RETRACTED` | External basis withdrawn | Evidence only; owner undefined | None |
| `ACTIVE` → `INVALIDATED` | Upstream retracted/invalidated | Cascade; owner undefined (MISSING-58) | None |
| `ACTIVE` → `ARCHIVED` | Retention policy | Undefined (MISSING-31) | None |

**No terminal state may transition.** Reinstating a retracted object requires a new version, preserving the record that it was once retracted.

> **MISSING-64:** Acceptance authority is unassigned. Rules V1–V12 must be enforced by something. The Knowledge Store is the natural point (it can reject structurally invalid writes per PKP v2 §5.2) but v1 does not assign it, and shared components are specified as non-interpretive. Blocking for P1.

### 2.2 Versioning Strategy

**Model.** Linear supersession chains. Each logical object has a stable `lineage_id`; each version has a unique `object_id` and monotonic `version`. No branching.

**When a new version is required:** any content change; adding an evidence attachment to a Fact (D-05); adding a constituent to a Pattern; correcting an error; recomputing confidence after upstream change.

**When no new version is required:** status transitions; addition of `duplicates`/`contradicts` annotations, which are observations *about* the object rather than changes *to* it.

**Downstream propagation.** Superseding an object does **not** automatically version its dependents (D-01a: references bind to specific versions). Dependents remain valid derivations of what they actually derived from. Whether a dependent should be revised is an engine judgement.

> **MISSING-65:** No re-derivation policy. When an upstream object is superseded, nothing determines whether dependents are recomputed, flagged, or left. Without one, the knowledge base accumulates conclusions derived from superseded inputs with no signal distinguishing them from current ones. Blocking for P4 onward.

**Branching prohibited.** Two engines cannot concurrently version the same object; only the producing engine holds version authority (§2.5), which serialises versioning per object type. This interacts with OPEN QUESTION-23 (concurrency) — unresolved.

### 2.3 Confidence Model (Operational)

Per D-03. Both components are mandatory; `effective_confidence` is derived and ceiling-constrained.

**Per-stage expectations** — indicative only, not thresholds:

| Object | `evidential_support` basis | `assertion_confidence` basis |
|---|---|---|
| Evidence | Source reliability (OPEN QUESTION-28) | Capture fidelity |
| Fact | Count and independence of attachments | Extraction certainty |
| Problem | Support of constituent Facts | Certainty that facts indicate a deficiency |
| Pattern | Diversity of constituent Problems and their sources | Certainty the grouping is not coincidence |
| Opportunity | Inherited from Pattern | Certainty value is capturable |
| Solution | Inherited from Opportunity | Certainty the approach addresses the problems |
| Validation | Method rigour | Certainty in result interpretation |
| Execution Record | Outcome observation quality | Certainty of attribution to the solution |
| Feedback Record | Volume and consistency of Execution Records | Certainty the inferred lesson is correct |

**Worked ceiling illustration.** Fact `effective_confidence` 0.55 → Problem asserted at 0.80 is capped to **0.55** → Pattern asserted at 0.90 is capped to **0.55** → Opportunity asserted at 0.85 is capped to **0.55**.

The opportunity presents at `MODERATE`, not `VERY_STRONG`. Without the ceiling, four confident inferential steps would have manufactured near-certainty from moderate evidence. This is the confidence-inflation failure mode, and the ceiling rule is the platform's structural defence against it.

> **OPEN QUESTION-34:** Whether the ceiling should use `min` across all upstream objects or a weighted function is undefined. `min` is conservative and may understate confidence where many independent moderate sources converge — arguably the case corroboration exists to strengthen. `min` is specified here because it cannot inflate; the alternative can.

### 2.4 Lineage Model

**Structure.** A directed acyclic graph over object versions. Nodes are versions; edges are `DERIVES_FROM`. Evidence objects are the only roots.

**Guarantees.** Every non-Evidence object reaches at least one Evidence object (V4). Every edge is attributed to a producing engine (U3). No cycles (V10). References are version-specific (D-01a) and never repoint (I3).

**Maximum depth is 8** (PKP v2 §6.4.2):

```
Evidence → Fact → Problem → Pattern → Opportunity → Solution → Validation → Execution Record
```

The Feedback Record sits at depth 9, deriving from Execution Records.

**Traversal directions.** *Backward* (to Evidence) supports explanation and verification; guaranteed terminating. *Forward* (from Evidence) supports impact analysis and cascade invalidation; required by I6 and MISSING-58.

**Breadth.** Fan-in is unbounded: a single Pattern may transitively rest on thousands of Evidence objects. Complete backward traversal from a late-stage object is therefore expensive — the traversal-explosion failure mode (PKP v2 §5.3). Principle 3 requires it be possible; nothing requires it be cheap.

> **MISSING-66:** No lineage summarisation model. Objects deep in the pipeline have evidence sets too large for practical human inspection, so Principle 3 is satisfiable formally but not usefully. Whether a summarised or sampled lineage view is acceptable is undefined.

### 2.5 Engine Authority Matrix

Realising Principle 4. **Create** = may bring into existence. **Modify** = may create a superseding version, or transition status. **Read** = may consume as input.

| Object | Create | Modify | Read |
|---|---|---|---|
| Evidence | Research | Research | Fact Extraction, Feedback¹ |
| Fact | Fact Extraction | Fact Extraction | Problem Intelligence, Feedback¹ |
| Problem | Problem Intelligence | Problem Intelligence | Pattern Intelligence, Solution Intelligence² |
| Pattern | Pattern Intelligence | Pattern Intelligence | Opportunity Intelligence |
| Opportunity | Opportunity Intelligence | Opportunity Intelligence | Solution Intelligence, Validation², Feedback |
| Solution | Solution Intelligence | Solution Intelligence | Validation, Feedback |
| Validation | Validation | Validation | Feedback |
| Execution Record | **UNDEFINED³** | **UNDEFINED³** | Feedback |
| Feedback Record | Feedback | Feedback | All engines⁴ |

¹ Feedback reads upstream objects to compare predictions against outcomes.
² Subject to OPEN QUESTION-21 (whether engines may read beyond their immediate predecessor). Solution Intelligence cannot demonstrate problem-fit without it.
³ CONTRADICTION-02: no Execution Engine exists. See §3.8.
⁴ Feedback Records inform engine behaviour; whether engines read them directly or configuration is updated externally is OPEN QUESTION-22.

**Invariants.** Exactly one engine holds create authority per type (except the undefined Execution Record). Create authority implies modify authority; no engine holds modify authority for a type it cannot create. Orchestration holds no authority over any object type — it reads status metadata only, never content, preserving its non-interpretive boundary.

### 2.6 Stage Ownership

| Object | Owning stage | Owning engine |
|---|---|---|
| Evidence | 1 — Evidence | Research |
| Fact | 2 — Facts | Fact Extraction |
| Problem | 3 — Problems | Problem Intelligence |
| Pattern | 4 — Patterns | Pattern Intelligence |
| Opportunity | 5 — Opportunities | Opportunity Intelligence |
| Solution | 6 — Solutions | Solution Intelligence |
| Validation | 7 — Validation | Validation |
| Execution Record | 8 — Execution | **none (CONTRADICTION-02)** |
| Feedback Record | 9 — Feedback | Feedback |

With D-07, every stage now owns exactly one object type. The sole remaining break is Stage 8.
---

## 3. Object Specifications

Each specification follows an identical structure. Universal attributes (§1.1–1.2), validation rules (§1.3), and integrity constraints (§1.4) apply to every type and are not repeated; only additions and restrictions appear.

---

### 3.1 Evidence Object

#### Purpose
Record source material acquired from outside the platform, together with the provenance needed to trust and re-verify it.

#### Responsibilities
1. Preserve acquired source material, or a reliable reference to it, with sufficient fidelity for later re-extraction.
2. Record complete provenance: origin, acquisition time, access conditions.
3. Identify its source distinctly enough that independence between sources is assessable.
4. Enable duplicate acquisition detection.
5. Carry no interpretation whatsoever.

#### Why This Object Exists
Evidence is the platform's grounding layer and the sole point of contact with external reality. Principle 1 requires every conclusion to trace to evidence; Evidence is the terminus of every such trace. It is the **only object type with no upstream lineage**, and that property is definitional — it is what makes the trace terminate and what makes grounding meaningful.

Without a distinct Evidence object, extracted claims would have no verifiable origin and Principle 1 would be unenforceable.

#### Lifecycle
Created by the Research Engine on acquisition. Normally remains `ACTIVE` indefinitely. May be `RETRACTED` if the source withdraws or repudiates the material. May be `SUPERSEDED` if re-acquired with better fidelity. Cannot be `INVALIDATED` — having no upstream, nothing can invalidate it from above.

#### State Transitions

| From | To | Trigger | Notes |
|---|---|---|---|
| — | `PROPOSED` | Acquisition completes | Research Engine |
| `PROPOSED` | `ACTIVE` | Validation passes | Provenance completeness is decisive |
| `PROPOSED` | `REJECTED` | Provenance incomplete or duplicate | Retained per D-02 |
| `ACTIVE` | `RETRACTED` | Source withdraws material | Triggers cascade (MISSING-58) |
| `ACTIVE` | `SUPERSEDED` | Re-acquired with better fidelity | New version |
| `ACTIVE` | `ARCHIVED` | Retention policy | MISSING-31 |

`INVALIDATED` is unreachable for Evidence.

#### Required Attributes

Universal, except `derives_from`, which **must be empty** — the defining restriction. Plus:

| Attribute | Meaning |
|---|---|
| `source_identifier` | Stable identifier of the origin, sufficient to assess independence |
| `source_type` | Category of source (MISSING-18: no taxonomy exists) |
| `acquisition_method` | How the material was obtained |
| `acquired_at` | Acquisition timestamp |
| `content` or `content_reference` | The material itself or a resolvable reference (OPEN QUESTION-25) |
| `content_fingerprint` | Enables duplicate detection and drift detection |
| `access_conditions` | Terms under which acquired (OPEN QUESTION-13) |
| `capture_fidelity` | Assessment of what was preserved versus lost |

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `source_reliability` | Trust assessment of the source (OPEN QUESTION-28) |
| `publication_date` | When the source published, distinct from acquisition |
| `author_identifier` | Attributed author, where available |
| `source_independence_group` | Grouping of sources known to be non-independent (syndication, common ownership) |

#### Validation Rules

| # | Rule |
|---|---|
| E-V1 | `derives_from` is empty |
| E-V2 | `source_identifier` and `acquired_at` present |
| E-V3 | `content` or `content_reference` present |
| E-V4 | `content_fingerprint` present and computed from actual content |
| E-V5 | `observed_at` ≤ `acquired_at` |
| E-V6 | No `ACTIVE` Evidence shares the same `content_fingerprint` and `source_identifier` |

#### Integrity Constraints

| # | Constraint |
|---|---|
| E-I1 | Content never altered after acceptance |
| E-I2 | Never derives from any platform-internal object |
| E-I3 | Provenance never removed |
| E-I4 | Retraction cascades to all dependents |

E-I2 is the direct enforcement point for CONTRADICTION-04. Under this specification, feedback **cannot** become Evidence — it may only trigger the Research Engine to acquire new external evidence. This is reading (b) of CONTRADICTION-04, adopted because reading (a) would breach E-I2, and E-I2 is what makes Evidence a grounding layer. **This constrains the resolution of CONTRADICTION-04 and requires ratification.**

#### Versioning
Rare. Justified only by improved fidelity re-acquisition. The original version is retained; superseding does not delete it.

#### Confidence
`evidential_support` reflects source reliability (OPEN QUESTION-28 unresolved — absent a trust model, all sources weigh equally, a strong unstated assumption). `assertion_confidence` reflects capture fidelity. Evidence has no upstream, so the ceiling rule does not constrain it; Evidence sets the ceiling for everything downstream.

#### Lineage
Root node. No `DERIVES_FROM`. All lineage traversal terminates at Evidence.

#### Relationships

| Relationship | Target | Notes |
|---|---|---|
| `DUPLICATES` | Evidence | Same material from different acquisition |
| `CONTRADICTS` | Evidence | Directly conflicting source material |
| `SUPERSEDES` | Evidence | Re-acquisition |

#### Engine Authority
**Create:** Research. **Modify:** Research. **Read:** Fact Extraction; Feedback (for prediction-outcome comparison).

#### Owning Stage
Stage 1 — Evidence.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Missing provenance | Easy | Principle 3 broken at the root; unrecoverable |
| Silent duplication | Hard | Corrupts every downstream frequency signal |
| Source drift after capture | Hard | Lineage points to unverifiable material |
| Capture fidelity loss | Hard | Corrupts extraction with no error signal |
| Sampling bias | Very hard | Confident, well-evidenced, wrong patterns — the platform's most dangerous systemic failure |
| Internal content admitted as Evidence | Medium | Grounding destroyed; self-reinforcing loop (CONTRADICTION-04) |

#### Example

```
object_id:            EV-8841
object_type:          Evidence
version:              1
lineage_id:           EVL-8841
produced_by_engine:   Research
derives_from:         [] 
source_identifier:    marketplace-listing-corpus / seller-reviews / segment-A
source_type:          customer_review_corpus
acquisition_method:   bulk_corpus_retrieval
acquired_at:          2026-03-14T09:20:00Z
observed_at:          2026-03-01T00:00:00Z
content_reference:    <resolvable reference to preserved corpus snapshot>
content_fingerprint:  <fingerprint of preserved content>
access_conditions:    corpus licence terms, attribution required
capture_fidelity:     full text preserved; embedded media not captured
evidential_support:   0.62  (STRONG)
assertion_confidence: 0.90  (VERY_STRONG)
effective_confidence: 0.62  (STRONG)
status:               ACTIVE
explanation:          Acquired under research directive covering seller-side
                      friction in segment A. Corpus selected for date coverage
                      and volume; media omitted as out of extraction scope.
```

---

### 3.2 Fact Object

#### Purpose
Represent a single canonical, individually verifiable claim, attached to every piece of Evidence attesting it.

#### Responsibilities
1. State one discrete claim, self-contained and context-preserving.
2. Maintain evidence attachments, each with a positional anchor into its Evidence.
3. Distinguish assertions of fact from attributed opinions.
4. Enable corroboration counting across independent sources.
5. Carry no interpretation of significance.

#### Why This Object Exists
Evidence is unstructured and cannot be reasoned over discretely. The Fact object converts source material into addressable units that can be individually verified, counted, corroborated, and contradicted.

Under D-05, the Fact is a **canonical claim, not an extraction event**. This is what makes corroboration measurable: ten sources attesting one claim produce one Fact with ten attachments, not ten Facts. Every downstream frequency judgement depends on this.

#### Lifecycle
Created on first extraction of a claim. Versioned when attachments are added (corroboration), which is expected to be frequent. `INVALIDATED` if all attesting Evidence is retracted. `SUPERSEDED` on re-extraction (OPEN QUESTION-14).

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Claim extracted |
| `PROPOSED` | `ACTIVE` | Validation passes; anchoring verified |
| `PROPOSED` | `REJECTED` | Not supported by evidence, or duplicate resolved to existing Fact |
| `ACTIVE` | `SUPERSEDED` | Attachment added, or re-extraction |
| `ACTIVE` | `INVALIDATED` | All attesting Evidence retracted |
| `ACTIVE` | `ARCHIVED` | Retention policy |

Partial retraction — some but not all attachments retracted — produces a **new version** with reduced support, not invalidation. The Fact remains attested.

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `claim` | The claim, self-contained with qualifying context |
| `claim_type` | `ASSERTION` or `ATTRIBUTED_OPINION` |
| `evidence_attachments` | One or more attachments (structure below) |
| `independent_source_count` | Attesting sources assessed as mutually independent |
| `qualifying_context` | Conditions under which the claim holds |

**Evidence attachment** (each entry):

| Field | Meaning |
|---|---|
| `evidence_ref` | Version-specific Evidence reference |
| `positional_anchor` | Precise location within that Evidence |
| `extracted_at` | Extraction timestamp |
| `extraction_confidence` | Certainty for this specific extraction |
| `independence_assessment` | Whether independent of other attachments |

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `quantitative_value` | Where the claim is numeric |
| `attributed_to` | Speaker, for `ATTRIBUTED_OPINION` |
| `temporal_scope` | Period the claim describes |
| `population_scope` | Population the claim describes |

#### Validation Rules

| # | Rule |
|---|---|
| F-V1 | At least one evidence attachment present |
| F-V2 | Every attachment has a resolvable `evidence_ref` and non-empty `positional_anchor` |
| F-V3 | `claim` is self-contained — interpretable without reading the Evidence |
| F-V4 | `claim_type` present; `attributed_to` required when `ATTRIBUTED_OPINION` |
| F-V5 | `independent_source_count` ≤ attachment count |
| F-V6 | Claim is present in the referenced Evidence at the stated anchor |

F-V6 is the platform's integrity floor and the guard against hallucinated facts. It is stated as a rule; **no mechanism enforces it** — see MISSING-67.

> **MISSING-67:** No verification mechanism for F-V6. Hallucinated facts satisfy every structural check (they have anchors, references, explanations) while being false. PKP v2 §4.2 identifies this as catastrophic and undetectable by structure alone. Nothing in v1 or this specification detects it. **This is the highest-severity unresolved gap in the object model.**

#### Integrity Constraints

| # | Constraint |
|---|---|
| F-I1 | Never asserts anything absent from its attached Evidence |
| F-I2 | Attachments are only ever added, never removed (removal requires retraction) |
| F-I3 | Positional anchors remain resolvable |
| F-I4 | Merging Facts requires explicit equivalence justification (MISSING-62) |

#### Versioning
Frequent, driven by corroboration. Each new attachment produces a version. Supersession chains for widely-attested facts may be long.

#### Confidence
`evidential_support` rises with independent attachment count and source diversity — the primary corroboration signal in the platform. `assertion_confidence` reflects extraction certainty. Ceiling: bounded by the Evidence attached; a Fact from a single weak source cannot exceed that source's confidence.

#### Lineage
`DERIVES_FROM` every attached Evidence version. Depth 1. Fan-in equals attachment count.

#### Relationships

| Relationship | Target | Notes |
|---|---|---|
| `SUPPORTS` | Problem | Evidential backing |
| `DUPLICATES` | Fact | Equivalence recognised but not merged |
| `CONTRADICTS` | Fact | Incompatible claims (OPEN QUESTION-03) |
| `SUPERSEDES` | Fact | Version chain |

`CONTRADICTS` resolves OPEN QUESTION-03 toward representing disagreement rather than selecting a winner. Contradiction is information; suppressing it would hide genuine market disagreement.

#### Engine Authority
**Create:** Fact Extraction. **Modify:** Fact Extraction. **Read:** Problem Intelligence; Feedback.

#### Owning Stage
Stage 2 — Facts.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Hallucinated claim | Very hard | Catastrophic; passes all structural checks (MISSING-67) |
| Context stripping | Hard | Individually defensible, collectively misleading |
| Over-merging | Hard | Hides source disagreement |
| Under-merging | Medium | Inflates apparent corroboration |
| Anchor loss | Easy | Verification requires full source re-reading |
| Opinion recorded as assertion | Medium | Problems inferred from opinion presented as observation |
| False independence assessment | Hard | Syndicated sources counted as independent corroboration |

#### Example

```
object_id:                 FA-2207
object_type:               Fact
version:                   3
lineage_id:                FAL-2207
produced_by_engine:        Fact Extraction
derives_from:              [EV-8841 v1, EV-8902 v1, EV-9013 v1]
claim:                     Sellers in segment A report that bulk listing
                           updates fail silently when more than 50 items are
                           modified in one operation.
claim_type:                ASSERTION
qualifying_context:        Reported for operations exceeding 50 items;
                           smaller batches not described as affected.
evidence_attachments:
  - evidence_ref:          EV-8841 v1
    positional_anchor:     review corpus / entry 4471 / lines 3-6
    extraction_confidence: 0.88
    independence_assessment: independent
  - evidence_ref:          EV-8902 v1
    positional_anchor:     forum thread 220 / post 12
    extraction_confidence: 0.79
    independence_assessment: independent
  - evidence_ref:          EV-9013 v1
    positional_anchor:     support transcript 88 / turn 9
    extraction_confidence: 0.84
    independence_assessment: independent
independent_source_count:  3
evidential_support:        0.71  (STRONG)
assertion_confidence:      0.84  (VERY_STRONG)
effective_confidence:      0.62  (STRONG)   ← ceiling from EV-8841 (0.62)
status:                    ACTIVE
explanation:               Three mutually independent sources across distinct
                           channels attest the same failure condition with
                           consistent threshold. Version 3 adds EV-9013.
```

---

### 3.3 Problem Object

#### Purpose
State a specific unmet need, friction, cost or failure experienced by an identified population, supported by Facts.

#### Responsibilities
1. State one problem, solution-independently.
2. Identify the affected population.
3. Characterise the problem's weight — severity, frequency, or both.
4. Link every supporting Fact.
5. Explain why those Facts constitute evidence of a problem.

#### Why This Object Exists
Facts describe what is; Problems assert that something is *wrong*. This is the platform's first interpretive leap and the point where market signal becomes actionable.

The object exists separately from Fact because the inference requires justification. A Fact needs only an anchor; a Problem needs an argument. Principle 2's explanation requirement is materially heavier here, and separating the objects makes the leap explicit and auditable rather than buried inside extraction.

#### Lifecycle
Created when Facts are judged to indicate a deficiency. Versioned as supporting Facts accumulate or weight is revised. `INVALIDATED` if supporting Facts are invalidated below sufficiency. May be `SUPERSEDED` by a better-formulated statement.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Deficiency inferred from Facts |
| `PROPOSED` | `ACTIVE` | Validation passes; solution-independence verified |
| `PROPOSED` | `REJECTED` | Insufficient support, or not solution-independent |
| `ACTIVE` | `SUPERSEDED` | Reformulated, or support changed |
| `ACTIVE` | `INVALIDATED` | Supporting Facts invalidated below sufficiency |
| `ACTIVE` | `ARCHIVED` | Retention policy |

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `problem_statement` | The deficiency, stated solution-independently |
| `affected_population` | Who experiences it |
| `supporting_facts` | `SUPPORTS` references; plural expected |
| `severity` | How damaging when it occurs (MISSING-12 supplies no scale) |
| `frequency` | How often it occurs (MISSING-12 supplies no scale) |
| `problem_domain` | Context in which it occurs |
| `inference_basis` | Why these Facts indicate a problem — beyond `explanation` |

`inference_basis` is separate from the universal `explanation` deliberately: `explanation` says why the object exists in this form; `inference_basis` justifies the interpretive leap from description to deficiency. This is the one stage where those differ enough to warrant separate attributes.

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `population_size_estimate` | Scale of affected population, if traceable to Facts |
| `existing_workarounds` | How the population currently copes |
| `problem_persistence` | Whether transient or enduring |
| `cost_indication` | Cost borne, where facts support it |

#### Validation Rules

| # | Rule |
|---|---|
| P-V1 | `supporting_facts` non-empty (sufficiency threshold undefined — MISSING-06) |
| P-V2 | `problem_statement` contains no solution, proposed or implied |
| P-V3 | `affected_population` non-empty and specific |
| P-V4 | `severity` and `frequency` present |
| P-V5 | `inference_basis` references specific supporting Facts |
| P-V6 | Not a restatement of a single Fact |

P-V2 guards the solution-smuggling failure mode. A problem framed as "lack of X" pre-determines the Opportunity and Solution stages and collapses three engines into one.

#### Integrity Constraints

| # | Constraint |
|---|---|
| P-I1 | Remains solution-independent across all versions |
| P-I2 | Every supporting Fact resolves and is `ACTIVE` |
| P-I3 | Affected population never widened without supporting Facts |
| P-I4 | Weight never asserted beyond what Facts support |

#### Versioning
Moderate. New versions on additional support, weight revision, or reformulation.

#### Confidence
`evidential_support` derives from supporting Facts' support and their source diversity. `assertion_confidence` expresses certainty that the facts genuinely indicate a deficiency — the interpretive component, and typically the lower of the two at this stage.

#### Lineage
`DERIVES_FROM` Facts read; `SUPPORTS` from the subset evidencing the problem. Depth 2.

#### Relationships

| Relationship | Target |
|---|---|
| `CONSTITUENT_OF` | Pattern |
| `DUPLICATES` | Problem |
| `CONTRADICTS` | Problem |
| `SUPERSEDES` | Problem |
| `ADDRESSES` (inbound) | Solution |

#### Engine Authority
**Create:** Problem Intelligence. **Modify:** Problem Intelligence. **Read:** Pattern Intelligence; Solution Intelligence (subject to OPEN QUESTION-21).

#### Owning Stage
Stage 3 — Problems.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Solution smuggling | Medium | Forecloses two downstream engines |
| Fabricated problem | Hard | Well-formed opportunity built on nothing |
| Severity misjudgement | Hard | Misprioritisation propagating into scoring |
| Over-generalisation | Medium | Unactionable patterns |
| Population ambiguity | Easy | Opportunity sizing impossible |
| Single-fact inflation | Easy | Breaches evidence sufficiency intent |
| Upstream error laundering | Very hard | Interpretive step obscures the origin of bad facts |

#### Example

```
object_id:            PR-0912
object_type:          Problem
version:              2
lineage_id:           PRL-0912
produced_by_engine:   Problem Intelligence
derives_from:         [FA-2207 v3, FA-2311 v1, FA-2402 v2]
supporting_facts:     [FA-2207 v3, FA-2311 v1, FA-2402 v2]
problem_statement:    Sellers managing large inventories lose update work
                      without notification when batch operations exceed
                      platform limits, and discover the loss only later
                      through customer complaints.
affected_population:  Segment A sellers maintaining inventories above
                      approximately 50 active listings.
problem_domain:       Marketplace inventory management
severity:             HIGH — unnoticed loss reaches end customers
frequency:            RECURRENT — reported across multiple periods
inference_basis:      FA-2207 establishes silent failure above a threshold.
                      FA-2311 establishes sellers are unaware until customers
                      report. FA-2402 establishes rework cost. Together these
                      show an unmet need for reliable batch feedback, not
                      merely an inconvenience.
evidential_support:   0.66  (STRONG)
assertion_confidence: 0.74  (STRONG)
effective_confidence: 0.62  (STRONG)   ← ceiling from FA-2207
status:               ACTIVE
explanation:          Version 2 adds FA-2402, establishing cost. Statement
                      deliberately excludes any remedy: it describes the
                      deficiency and its consequence only.
```

---

### 3.4 Pattern Object

#### Purpose
Assert that multiple Problems share structure that is not visible in any one of them, and justify that the grouping is not coincidental.

#### Responsibilities
1. State the structure observed across constituent Problems.
2. Reference every constituent Problem.
3. Justify why the grouping is meaningful rather than coincidental.
4. Record the source diversity underlying the pattern.
5. Remain decomposable into its constituents.

#### Why This Object Exists
Patterns are where the platform delivers value no individual observer could: recognising that scattered problems share structure. The pipeline's narrow waist (PKP v2 §6.4.3) sits here — cost expands on both sides of this filter, so the quality of this object determines whether that expansion is warranted.

It exists separately from Problem because it asserts something categorically different: not that a deficiency exists, but that deficiencies *recur* in a describable way. A single-problem Pattern is a category error.

#### Lifecycle
Created when structure is recognised across a Problem population. Versioned as constituents accumulate. Uniquely, Patterns have **open-ended membership** — new Problems may join an existing Pattern indefinitely, making this the most version-churning object type after Fact.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Structure recognised |
| `PROPOSED` | `ACTIVE` | Validation passes; ≥2 constituents; non-coincidence justified |
| `PROPOSED` | `REJECTED` | Insufficient constituents, or judged a sampling artefact |
| `ACTIVE` | `SUPERSEDED` | Constituents added or removed; restatement |
| `ACTIVE` | `INVALIDATED` | Constituents invalidated below two |
| `ACTIVE` | `ARCHIVED` | Retention, or staleness (MISSING-13, MISSING-61) |

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `pattern_statement` | The structure observed |
| `constituent_problems` | `CONSTITUENT_OF` references; ≥2 |
| `pattern_type` | Recurrence, correlation, clustering, or cross-domain similarity |
| `grouping_rationale` | Why this grouping is meaningful, not coincidental |
| `source_diversity` | Count of independent Evidence sources beneath the constituents |
| `artefact_assessment` | Explicit judgement on whether this reflects research bias |
| `pattern_scope` | Domain, population and period over which it holds |

`source_diversity` and `artefact_assessment` are mandatory because sampling artefact is this stage's defining risk. Computing `source_diversity` requires evidence-level information four stages upstream — see MISSING-22, unresolved.

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `pattern_strength` | Degree of structure, distinct from confidence |
| `temporal_trend` | Whether strengthening, stable or weakening |
| `cross_domain_instances` | Domains in which the pattern appears |
| `expected_persistence` | Whether structural or transient |

#### Validation Rules

| # | Rule |
|---|---|
| PT-V1 | `constituent_problems` contains ≥2 distinct Problems |
| PT-V2 | Constituents are distinct logical objects, not versions of one |
| PT-V3 | `grouping_rationale` non-empty and references specific constituents |
| PT-V4 | `source_diversity` present |
| PT-V5 | `artefact_assessment` present and reasoned |
| PT-V6 | Pattern is decomposable — every constituent resolves |

PT-V2 prevents a pattern being asserted over multiple versions of the same underlying problem, which would be self-corroboration.

#### Integrity Constraints

| # | Constraint |
|---|---|
| PT-I1 | Never fewer than two active constituents |
| PT-I2 | Constituents never discarded during aggregation |
| PT-I3 | Never claims scope beyond its constituents' scope |
| PT-I4 | Source diversity never overstated |

#### Versioning
High churn from open-ended membership. Each constituent addition produces a version.

> **OPEN QUESTION-35:** Whether adding a constituent should always version the Pattern, or whether membership should be modelled as a relationship recorded on the Problem, is unresolved. Versioning is specified here for consistency with D-01, but produces substantial churn on broad patterns. This is the sharpest practical tension created by immutability.

#### Confidence
`evidential_support` derives from constituent Problems' support **weighted by source diversity** — the only object where diversity is an explicit confidence input, because a pattern resting on many problems from one source is weak regardless of problem count. `assertion_confidence` expresses certainty the grouping is genuine.

#### Lineage
`DERIVES_FROM` and `CONSTITUENT_OF` constituent Problems. Depth 3. Fan-in typically large; transitive evidence sets may reach thousands (MISSING-66).

#### Relationships

| Relationship | Target |
|---|---|
| `CONSTITUENT_OF` (inbound) | from Problems |
| `DUPLICATES` | Pattern |
| `CONTRADICTS` | Pattern |
| `SUPERSEDES` | Pattern |

Pattern-to-Pattern hierarchy is **not supported** — OPEN QUESTION-17 remains open, and v1's flat model is preserved.

#### Engine Authority
**Create:** Pattern Intelligence. **Modify:** Pattern Intelligence. **Read:** Opportunity Intelligence.

#### Owning Stage
Stage 4 — Patterns.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Sampling artefact | Very hard | Confident, well-evidenced, false view of the market |
| Spurious correlation | Hard | Opportunities founded on non-existent structure |
| Over-clustering | Medium | Unactionable generality |
| Under-clustering | Hard | Core platform value not delivered |
| Temporal blindness | Hard | Opportunities based on lapsed conditions |
| Frequency inflation | Hard | Weak patterns appear strong |
| Constituent loss | Easy | Unexplainable pattern |

#### Example

```
object_id:            PT-0334
object_type:          Pattern
version:              4
lineage_id:           PTL-0334
produced_by_engine:   Pattern Intelligence
derives_from:         [PR-0912 v2, PR-1044 v1, PR-1130 v3, PR-1201 v1]
constituent_problems: [PR-0912 v2, PR-1044 v1, PR-1130 v3, PR-1201 v1]
pattern_statement:    Bulk operations across marketplace seller tooling fail
                      silently at undocumented thresholds, with sellers
                      discovering failures only through downstream customer
                      impact rather than system feedback.
pattern_type:         CROSS_DOMAIN_SIMILARITY
pattern_scope:        Marketplace seller tooling; segment A and adjacent
                      segments; observed across 2025-2026 periods.
grouping_rationale:   All four problems share a structure: a silent threshold
                      failure, absence of feedback, and delayed discovery via
                      third parties. PR-0912 and PR-1044 concern listing
                      updates; PR-1130 concerns bulk pricing; PR-1201 concerns
                      inventory sync. The shared structure is the missing
                      feedback channel, not the specific operation, which is
                      why this is treated as one pattern across four domains.
source_diversity:     11 independent Evidence sources across 4 channel types
artefact_assessment:  Not attributable to research bias. Constituents derive
                      from four acquisition efforts across distinct source
                      types; no single source contributes to more than one
                      constituent problem.
evidential_support:   0.64  (STRONG)
assertion_confidence: 0.71  (STRONG)
effective_confidence: 0.62  (STRONG)   ← ceiling from PR-0912
status:               ACTIVE
explanation:          Version 4 adds PR-1201, extending the pattern to
                      inventory sync and raising source diversity from 8 to 11.
```
---

### 3.5 Opportunity Object

#### Purpose
Assert that a recognised Pattern represents a specific area where value could be created and captured, with a comparable score and honestly-bounded confidence.

#### Responsibilities
1. State what value could be created and for whom.
2. Reference the originating Pattern(s).
3. Carry a score enabling comparison against other Opportunities.
4. Explain the score.
5. Represent confidence honestly relative to evidential support.
6. Remain free of solution content.

#### Why This Object Exists
This is the platform's primary output — the object the vision exists to produce, and the one that drives resource commitment. It exists separately from Pattern because a pattern is a structural observation while an opportunity is a **value judgement about that structure**. The same pattern may yield several opportunities, or none.

The separation matters for accountability: Pattern Intelligence is answerable for whether the structure is real; Opportunity Intelligence is answerable for whether it is worth pursuing. Conflating them would make a single engine unaccountable for two different kinds of error.

#### Lifecycle
Created when a Pattern is assessed as carrying value potential. Scored. Possibly selected for solution development (mechanism undefined — MISSING-23). Versioned on rescoring, which occurs when the scoring model changes through learning.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Value potential assessed |
| `PROPOSED` | `ACTIVE` | Validation passes; scored; solution-free |
| `PROPOSED` | `REJECTED` | Below viability, or not solution-free |
| `ACTIVE` | `SUPERSEDED` | Rescored, or restated |
| `ACTIVE` | `INVALIDATED` | Originating Pattern invalidated |
| `ACTIVE` | `ARCHIVED` | Retention, or staleness |

`REJECTED` Opportunities are retained (D-02): they are among the platform's most valuable learning signals, since declined opportunities that later prove valuable are direct evidence of scoring error.

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `opportunity_statement` | What value could be created, for whom |
| `originating_patterns` | Source Pattern references |
| `value_hypothesis` | Why value exists here |
| `beneficiary_population` | Who would benefit |
| `score` | Comparative assessment (MISSING-14: no dimensions defined) |
| `score_basis` | Per-dimension breakdown |
| `score_model_version` | Which scoring model produced this score |
| `scoring_explanation` | Why the score is what it is |

`score_model_version` is mandatory because Principle 5 means the scoring model changes over time. Without it, scores produced under different models are silently incomparable — the score-drift failure mode (PKP v2 §4.5), which is invisible precisely because the numbers remain superficially comparable.

> **MISSING-14 (unresolved, blocking):** No scoring dimensions, scale, or methodology exist. `score` and `score_basis` are specified as required but cannot be populated meaningfully. **The Opportunity object cannot be fully implemented until MISSING-14 is resolved**, and PKP v2 MISSING-39 notes the completed "Opportunity Evaluation" research would likely inform it.

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `market_sizing` | Scale estimate, only if traceable to Facts |
| `timing_assessment` | Why now |
| `competitive_context` | Existing responses to this pattern |
| `capture_hypothesis` | How value could be retained, not how it is built |
| `rejection_rationale` | Required when `REJECTED` |

`capture_hypothesis` is deliberately narrow: it addresses whether value is retainable, not how a solution would work. The boundary is thin and must be policed.

#### Validation Rules

| # | Rule |
|---|---|
| O-V1 | `originating_patterns` non-empty and resolvable |
| O-V2 | `opportunity_statement` contains no solution design |
| O-V3 | `score` present with `score_model_version` |
| O-V4 | `scoring_explanation` references specific score dimensions |
| O-V5 | `effective_confidence` ≤ originating Pattern confidence |
| O-V6 | Any quantitative claim traces to Facts via lineage |
| O-V7 | `rejection_rationale` present when `REJECTED` |

O-V5 is the platform's principal defence against its most consequential failure. O-V6 prevents unfounded sizing — the temptation to state market size from model knowledge rather than evidence is strongest at this stage.

#### Integrity Constraints

| # | Constraint |
|---|---|
| O-I1 | Confidence never exceeds evidential support permits |
| O-I2 | Solution-free across all versions |
| O-I3 | Scores comparable only within the same `score_model_version` |
| O-I4 | Historical scores never retrospectively altered |

O-I4 preserves what the platform predicted at the time, which the Feedback Engine requires. Rescoring creates a new version; it does not overwrite.

#### Versioning
Moderate, but with a systemic driver: learning changes the scoring model, and rescoring an opportunity population produces a version per opportunity. This makes Opportunity versioning the most learning-coupled in the model.

> **OPEN QUESTION-29 (restated):** Whether scores are point-in-time or recomputed on read remains open. This specification requires point-in-time storage (O-I4) to preserve predictions, but does not resolve whether rescoring is automatic on model change.

#### Confidence
`evidential_support` inherited from the Pattern. `assertion_confidence` expresses certainty that value is real and capturable — typically the weakest inferential step in the pipeline, since it involves judgement about markets rather than observation of them. Ceiling strictly enforced.

#### Lineage
`DERIVES_FROM` Patterns. Depth 4. Transitively rests on the full Problem, Fact and Evidence sets beneath.

#### Relationships

| Relationship | Target |
|---|---|
| `ADDRESSES` (inbound) | from Solutions |
| `DUPLICATES` | Opportunity |
| `CONTRADICTS` | Opportunity (mutually exclusive opportunities) |
| `SUPERSEDES` | Opportunity |

#### Engine Authority
**Create:** Opportunity Intelligence. **Modify:** Opportunity Intelligence. **Read:** Solution Intelligence; Validation (subject to OPEN QUESTION-21); Feedback.

#### Owning Stage
Stage 5 — Opportunities.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Confidence inflation | Hard | **Most consequential failure in the platform** — drives misallocated commitment |
| Score incomparability | Hard | Ranking meaningless while appearing authoritative |
| Score drift across model versions | Very hard | Historical and current scores silently incomparable |
| Solution contamination | Medium | Forecloses Solution Intelligence |
| Sizing without basis | Medium | Breaches Principle 1 at the most visible point |
| Silent rejection | Easy | Breaches Principle 2; destroys learning signal |
| Pattern over-trust | Hard | Inherits and amplifies artefactual patterns |

#### Example

```
object_id:            OP-0157
object_type:          Opportunity
version:              1
lineage_id:           OPL-0157
produced_by_engine:   Opportunity Intelligence
derives_from:         [PT-0334 v4]
originating_patterns: [PT-0334 v4]
opportunity_statement: Provide marketplace sellers with reliable, immediate
                      feedback on the outcome of bulk operations, so that
                      partial or total failure is known at the time it occurs
                      rather than discovered through customer impact.
beneficiary_population: Segment A sellers and adjacent segments operating at
                      inventory scale, across multiple marketplace tools.
value_hypothesis:     The pattern shows a consistent absence of feedback across
                      four operational domains, with cost borne as rework and
                      customer-facing error. Value arises from eliminating
                      delayed discovery, which is where the cost concentrates.
score:                <UNPOPULATED — MISSING-14>
score_basis:          <UNPOPULATED — MISSING-14>
score_model_version:  <UNPOPULATED — MISSING-14>
scoring_explanation:  <UNPOPULATED — MISSING-14>
evidential_support:   0.64  (STRONG)
assertion_confidence: 0.58  (MODERATE)
effective_confidence: 0.58  (MODERATE)  ← own assertion below Pattern ceiling
status:               PROPOSED
explanation:          Derived from PT-0334, which establishes the structure
                      across four domains. Statement describes the outcome
                      sought, not any mechanism for achieving it. Assertion
                      confidence is set below evidential support because
                      whether sellers would switch tooling for this alone
                      is not established by the underlying evidence.
```

The example is deliberately shown as `PROPOSED` with unpopulated scoring: it cannot reach `ACTIVE` under O-V3 while MISSING-14 is unresolved. This is the object model demonstrating its own blocking condition.

---

### 3.6 Solution Object

#### Purpose
Propose a concrete approach to an Opportunity, with every assumption it depends on stated explicitly.

#### Responsibilities
1. Describe the approach.
2. Reference the Opportunity it addresses and, through lineage, the Problems.
3. **State every assumption explicitly and testably.**
4. Explain how the approach addresses the underlying problems.
5. Assess constraints and feasibility.
6. Coexist with competing candidates without premature collapse.

#### Why This Object Exists
The Solution object is the bridge between analysis and action, but its most important function is **generating the testable surface for Validation**. Assumptions are what Validation tests; a Solution with unstated assumptions is unvalidatable, and the platform's central safeguard is bypassed.

It exists separately from Opportunity because one opportunity admits many approaches, and comparing them requires each to be independently addressable and independently testable.

#### Lifecycle
Created as a candidate. Multiple candidates per Opportunity coexist as siblings — this is expected, not exceptional. Validated. Possibly executed. Versioned as assumptions are refined.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Approach formulated |
| `PROPOSED` | `ACTIVE` | Validation passes; assumptions explicit |
| `PROPOSED` | `REJECTED` | Infeasible, or assumptions not articulable |
| `ACTIVE` | `SUPERSEDED` | Refined; assumptions revised |
| `ACTIVE` | `INVALIDATED` | Opportunity invalidated |
| `ACTIVE` | `ARCHIVED` | Retention, or candidate not pursued |

Note: a Solution whose assumptions **fail** validation does not automatically become `REJECTED`. Validation reports; it does not gate (MISSING-26, gate ownership unassigned). The Solution remains `ACTIVE` with failed Validations attached until something decides otherwise. This is a visible consequence of an unresolved marker.

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `solution_statement` | The approach (depth undefined — OPEN QUESTION-20) |
| `addresses_opportunity` | `ADDRESSES` reference |
| `assumptions` | Explicit, individually testable assumptions |
| `problem_fit_rationale` | How this addresses the underlying Problems |
| `constraints` | Limits considered (MISSING-24: no constraint model) |
| `feasibility_assessment` | Judgement on whether it can be done |
| `candidate_group` | Identifier grouping competing candidates for one Opportunity |

**Assumption** (each entry):

| Field | Meaning |
|---|---|
| `assumption_id` | Addressable within the Solution |
| `assumption_statement` | What is assumed |
| `criticality` | Whether the solution fails if this is false |
| `testability` | How it could be tested |

Structured assumptions are mandatory because Validation's `TESTS` relationship targets individual assumptions, not the Solution as a whole. Unstructured prose assumptions would make claim-level validation impossible.

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `differentiators` | How this differs from sibling candidates |
| `dependencies` | External prerequisites |
| `risk_factors` | Identified risks |
| `precedents` | Comparable approaches, where evidenced |

#### Validation Rules

| # | Rule |
|---|---|
| S-V1 | `addresses_opportunity` resolvable and `ACTIVE` |
| S-V2 | `assumptions` non-empty — **a Solution with no assumptions is invalid** |
| S-V3 | Every assumption has `criticality` and `testability` |
| S-V4 | `problem_fit_rationale` references specific Problems via lineage |
| S-V5 | `solution_statement` is not a restatement of the Opportunity |
| S-V6 | `feasibility_assessment` present |

S-V2 is unusual in requiring the *presence* of uncertainty. A solution claiming no assumptions is either trivial or concealing them, and concealment is this stage's most damaging failure.

#### Integrity Constraints

| # | Constraint |
|---|---|
| S-I1 | Assumptions never removed, only superseded with rationale |
| S-I2 | Demonstrably addresses the Problems beneath its Opportunity |
| S-I3 | Sibling candidates never silently collapsed |
| S-I4 | Never modifies its Opportunity's assessment |

#### Versioning
Moderate. Driven by assumption refinement, often prompted by validation findings.

#### Confidence
`evidential_support` inherited from the Opportunity. `assertion_confidence` expresses certainty the approach addresses the problems — **not** certainty it will succeed, which is Validation's and Execution's domain. This distinction must be preserved or the Solution object will absorb judgements it has no basis for.

#### Lineage
`DERIVES_FROM` the Opportunity; `ADDRESSES` the Opportunity and, where read, the Problems. Depth 5.

#### Relationships

| Relationship | Target |
|---|---|
| `ADDRESSES` | Opportunity, Problem |
| `TESTS` (inbound) | from Validations |
| `OUTCOME_OF` (inbound) | from Execution Records |
| `DUPLICATES` / `CONTRADICTS` | Solution |
| `SUPERSEDES` | Solution |

#### Engine Authority
**Create:** Solution Intelligence. **Modify:** Solution Intelligence. **Read:** Validation; Feedback.

#### Owning Stage
Stage 6 — Solutions.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Assumption concealment | Hard | Validation tests the wrong things; central safeguard bypassed |
| Generic solutioning | Medium | Inputs not being used; no value added |
| Premature convergence | Easy | No comparative validation possible |
| Feasibility blindness | Medium | Validation effort spent on impossible approaches |
| Problem drift | Medium | Lineage intact but semantically empty |
| Opportunity restatement | Easy | No transformation performed |

#### Example

```
object_id:            SO-0402
object_type:          Solution
version:              2
lineage_id:           SOL-0402
produced_by_engine:   Solution Intelligence
derives_from:         [OP-0157 v1]
addresses_opportunity: OP-0157 v1
candidate_group:      OP-0157-candidates
solution_statement:   A pre-commit validation and post-operation reconciliation
                      layer for bulk seller operations, reporting per-item
                      outcome immediately on completion and surfacing partial
                      failures explicitly rather than reporting operation-level
                      success.
problem_fit_rationale: PR-0912 establishes silent failure with delayed
                      discovery; PR-1130 and PR-1201 establish the same across
                      pricing and sync. Per-item outcome reporting addresses
                      the shared missing-feedback structure identified in
                      PT-0334 rather than any single operation type.
assumptions:
  - assumption_id:      A1
    assumption_statement: Sellers will act on per-item failure reports rather
                        than ignoring them at volume.
    criticality:        CRITICAL — solution fails if reports are ignored
    testability:        Observable via response rates to existing partial-
                        failure notifications in comparable tooling
  - assumption_id:      A2
    assumption_statement: Per-item outcome reporting is achievable within
                        acceptable operation latency at inventory scale.
    criticality:        CRITICAL
    testability:        Measurable against known operation volumes
  - assumption_id:      A3
    assumption_statement: The failure thresholds are stable enough to validate
                        against rather than varying unpredictably.
    criticality:        MODERATE — solution degrades but survives if false
    testability:        Testable against threshold observations in FA-2207
constraints:          <PARTIAL — MISSING-24, no constraint model>
feasibility_assessment: Feasible in principle; A2 is the binding uncertainty.
evidential_support:   0.64  (STRONG)
assertion_confidence: 0.61  (STRONG)
effective_confidence: 0.58  (MODERATE)  ← ceiling from OP-0157
status:               ACTIVE
explanation:          Version 2 adds A3 following review of threshold
                      stability. One of three sibling candidates in
                      OP-0157-candidates; retained for comparative validation.
```

---

### 3.7 Validation Object

#### Purpose
Record that a specific claim or assumption was tested, by what method, with what result — including negative results.

#### Responsibilities
1. Identify the specific claim tested.
2. Record the method to a reproducible standard.
3. Record the result, positive or negative, without prejudice.
4. Interpret the result.
5. Attach to the specific claim, never to an object as a whole.

#### Why This Object Exists
Validation is what distinguishes the platform's output from plausible speculation. The object exists to make testing **auditable**: what was tested, how, and what happened — recorded such that a negative result is as durable and as visible as a positive one.

It attaches to individual claims rather than whole objects because whole-object validation is not meaningful. A Solution has multiple assumptions of differing criticality; validating "the solution" would obscure which assumptions were actually tested and which were not.

#### Lifecycle
Created when a test concludes. Generally not versioned — a concluded test is a historical fact. Re-testing produces a **new** Validation object, not a new version, preserving both results.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Test concludes; result recorded |
| `PROPOSED` | `ACTIVE` | Validation passes; method reproducible |
| `PROPOSED` | `REJECTED` | Method inadequate; result unusable |
| `ACTIVE` | `SUPERSEDED` | Only on correction of a recording error |
| `ACTIVE` | `INVALIDATED` | Tested object invalidated |
| `ACTIVE` | `ARCHIVED` | Retention |

A **negative result is `ACTIVE`, not `REJECTED`.** This is the single most important status rule in the specification: `REJECTED` describes an unusable record, not an unfavourable finding. Conflating them would let negative results be quietly filed as failures of the test rather than findings about the world — the negative-result-suppression failure mode.

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `tests_claim` | `TESTS` reference to a specific assumption or claim |
| `validation_method` | Method used (MISSING-25: no methodology defined) |
| `method_detail` | Sufficient detail for repetition |
| `result` | `SUPPORTED`, `NOT_SUPPORTED`, `INCONCLUSIVE`, `PARTIALLY_SUPPORTED` |
| `result_detail` | What was actually observed |
| `result_interpretation` | What the result means for the claim |
| `validated_at` | When the test concluded |
| `scope_limitations` | What this test does **not** establish |

`scope_limitations` is mandatory to counter scope mismatch — validating a narrow proxy and treating it as whole-solution validation. Requiring explicit statement of what was *not* established makes over-claiming visible.

> **MISSING-25 (unresolved, blocking):** The nature of validation is undefined — whether evidence-based, analytical, experimental, or market-based. `validation_method` is required but has no defined vocabulary. **The Validation object cannot be fully implemented until MISSING-25 is resolved.** PKP v2 identifies this as the largest single specification gap.

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `experiment_ref` | Reference to an Experiment Registry entry (CONTRADICTION-05) |
| `confidence_impact` | How this result should affect the tested object's confidence |
| `contradicting_evidence` | Evidence encountered that opposes the claim |
| `follow_up_required` | Further testing indicated |

`experiment_ref` is optional solely because CONTRADICTION-05 is unresolved. Once the Validation/Experiment Registry boundary is settled, this becomes either mandatory or removed.

#### Validation Rules

| # | Rule |
|---|---|
| V-V1 | `tests_claim` resolves to a specific claim, not a whole object |
| V-V2 | `validation_method` and `method_detail` present |
| V-V3 | `result` present and drawn from the defined set |
| V-V4 | `result_interpretation` present, including for negative results |
| V-V5 | `scope_limitations` present |
| V-V6 | Method detail sufficient to repeat the test |

#### Integrity Constraints

| # | Constraint |
|---|---|
| V-I1 | Negative results never suppressed, downgraded, or `REJECTED` for being negative |
| V-I2 | Never modifies the object it tests |
| V-I3 | Never proposes alternative solutions |
| V-I4 | Result never reinterpreted after recording; corrections are new versions with rationale |

V-I3 preserves Validation's independence. A validation that improves the solution has crossed into Solution Intelligence and can no longer be an impartial test of it.

#### Versioning
Rare. Only for correction of recording errors. Re-tests are new objects.

#### Confidence
`evidential_support` reflects method rigour. `assertion_confidence` reflects certainty in the interpretation. Note: a **high-confidence negative result** is entirely coherent and highly valuable — the platform can be very certain that an assumption is false.

#### Lineage
`DERIVES_FROM` the object containing the tested claim; `TESTS` the specific claim. Depth 6.

#### Relationships

| Relationship | Target |
|---|---|
| `TESTS` | Assumption or claim within any object |
| `CONTRADICTS` | Validation (conflicting results on the same claim) |
| `SUPERSEDES` | Validation (correction only) |

Conflicting validation results are represented via `CONTRADICTS`, not resolved by selection. Two tests disagreeing is information about the claim's robustness.

#### Engine Authority
**Create:** Validation. **Modify:** Validation. **Read:** Feedback.

#### Owning Stage
Stage 7 — Validation.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Confirmation bias | Hard | Validation becomes ceremonial; safeguard void |
| Negative result suppression | Medium | Destroys the learning signal Principle 5 depends on |
| Scope mismatch | Hard | False assurance at the highest-stakes point |
| Untested critical assumption | Hard | Inherits Solution Intelligence's concealment failure |
| Validation without consequence | Easy | Results recorded but nothing follows (MISSING-26) |
| Method opacity | Medium | Unrepeatable; breaches Principle 3 |
| Registry divergence | Medium | Dual truth (CONTRADICTION-05) |

#### Example

```
object_id:              VA-0771
object_type:            Validation
version:                1
lineage_id:             VAL-0771
produced_by_engine:     Validation
derives_from:           [SO-0402 v2]
tests_claim:            SO-0402 v2 / assumption A1
validation_method:      <VOCABULARY UNDEFINED — MISSING-25>
method_detail:          Examined response behaviour to existing partial-failure
                        notifications across three comparable seller tools,
                        using observed remediation rates within 48 hours of
                        notification as the behavioural indicator.
result:                 PARTIALLY_SUPPORTED
result_detail:          Remediation occurred in the majority of cases where
                        fewer than 20 items failed, but rates declined sharply
                        above that threshold, with most high-volume failures
                        left unremediated.
result_interpretation:  A1 holds at low failure volumes but not at high ones.
                        Since the underlying problem concerns large inventories,
                        the assumption is weakest precisely where the
                        opportunity is strongest. This does not invalidate
                        SO-0402 but materially narrows its claimed value.
scope_limitations:      Establishes nothing about response to a redesigned
                        reporting mechanism; measures behaviour under existing
                        notification designs only. Does not test A2 or A3.
validated_at:           2026-05-02T00:00:00Z
evidential_support:     0.58  (MODERATE)
assertion_confidence:   0.72  (STRONG)
effective_confidence:   0.58  (MODERATE)
status:                 ACTIVE
explanation:            Test targeted A1 specifically as the assumption marked
                        CRITICAL with the clearest observable proxy. Result is
                        unfavourable in part and recorded as ACTIVE; the
                        finding is durable knowledge regardless of whether it
                        favours the solution.
```

This example deliberately shows an unfavourable result recorded as `ACTIVE` with full interpretation — the behaviour the specification exists to guarantee.

---

### 3.8 Execution Record Object

#### Purpose
Record what actually happened when a solution was acted upon in the real world, linked to the prediction it tests.

#### Responsibilities
1. Record what was executed.
2. Link to the Solution executed and, through it, to the Opportunity's original prediction.
3. Record the outcome, favourable or not.
4. Distinguish what is attributable to the solution from what is not.
5. Record observation timing.

#### Why This Object Exists
This is the **only object carrying ground truth**. Every other object records what the platform inferred; this one records what occurred. Principle 5 depends entirely on it: without outcomes, the platform has nothing to learn from and the loop is open.

#### Producing Engine — Undefined

> **CONTRADICTION-02 (restated, blocking):** No Execution Engine exists in v1 §4. This is the only object type with no producing engine, no create authority, and no defined intake path. The roadmap has no execution phase, consistent with execution occurring outside the platform — but no engine is assigned to receive external outcome reports either.
>
> **Consequence for this specification:** the Execution Record is specified in full below, but **cannot be created by any component defined in v1**. Its attributes, rules and constraints are stated so that they are ready when the contradiction is resolved. Assigning create authority would add or extend an engine, which is out of scope.

> **MISSING-36 (restated):** No intake mechanism for external outcome reports. The learning loop is structurally open at this point.

#### Lifecycle
Created when outcomes are observed. Versioned as further outcomes accumulate — outcomes often materialise over extended periods, making this the object most subject to temporal spread between prediction and observation.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Outcome observed and reported |
| `PROPOSED` | `ACTIVE` | Validation passes; attribution assessed |
| `PROPOSED` | `REJECTED` | Outcome unverifiable or unattributable |
| `ACTIVE` | `SUPERSEDED` | Further outcomes observed |
| `ACTIVE` | `INVALIDATED` | Executed Solution invalidated |
| `ACTIVE` | `ARCHIVED` | Retention |

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `outcome_of_solution` | `OUTCOME_OF` reference to the executed Solution |
| `execution_description` | What was actually done |
| `executed_at` | When execution occurred |
| `outcome_observed_at` | When the outcome was observed |
| `outcome` | What happened |
| `outcome_valence` | `FAVOURABLE`, `UNFAVOURABLE`, `MIXED`, `INCONCLUSIVE` |
| `attribution_assessment` | What is and is not attributable to the solution |
| `prediction_comparison` | Actual outcome against the Opportunity's prediction |
| `outcome_verification` | How the outcome was verified (MISSING-47) |

`attribution_assessment` and `outcome_verification` are mandatory because this object is the platform's only ground-truth input. If outcomes can be reported unverified and unattributed, the platform can be taught anything — the most direct route to corrupting a continuously learning system.

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `execution_deviations` | How execution differed from the specified solution |
| `external_factors` | Confounding influences identified |
| `partial_outcomes` | Interim results before final outcome |
| `outcome_magnitude` | Scale of the effect observed |

`execution_deviations` matters: if execution departed from the Solution, the outcome tests something other than what the platform proposed, and learning from it would attribute results to the wrong cause.

#### Validation Rules

| # | Rule |
|---|---|
| X-V1 | `outcome_of_solution` resolvable to a specific Solution version |
| X-V2 | `outcome_valence` present |
| X-V3 | `attribution_assessment` present and reasoned |
| X-V4 | `prediction_comparison` references the Opportunity's stored prediction |
| X-V5 | `executed_at` ≤ `outcome_observed_at` |
| X-V6 | `outcome_verification` present |

X-V4 requires the original prediction to be retrievable, which requires immutable prediction storage (D-01, O-I4). This is where immutability pays for itself.

#### Integrity Constraints

| # | Constraint |
|---|---|
| X-I1 | Unfavourable outcomes recorded with equal status to favourable |
| X-I2 | Never modifies the Solution or Opportunity it evaluates |
| X-I3 | Attribution never overstated |
| X-I4 | Links to the specific Solution version executed |

#### Versioning
Moderate, driven by outcome accumulation over time.

#### Confidence
`evidential_support` reflects observation quality. `assertion_confidence` reflects attribution certainty — typically low, since isolating a solution's effect from external factors is genuinely difficult. **This is the object where low confidence is most often appropriate and most often overstated.**

#### Lineage
`DERIVES_FROM` and `OUTCOME_OF` the Solution. Depth 7 — the deepest object in the forward pipeline.

#### Relationships

| Relationship | Target |
|---|---|
| `OUTCOME_OF` | Solution |
| `SUPERSEDES` | Execution Record |
| `CONTRADICTS` | Execution Record (conflicting outcome reports) |

#### Engine Authority
**Create:** UNDEFINED (CONTRADICTION-02). **Modify:** UNDEFINED. **Read:** Feedback.

#### Owning Stage
Stage 8 — Execution. **No owning engine.**

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| No intake mechanism | Certain | Learning loop structurally open (MISSING-36) |
| Attribution error | Very hard | Learning from the wrong signal |
| Reporting gap | Very hard | Learning biased toward whichever outcomes get reported |
| Survivorship bias | Very hard | Only favourable outcomes reported |
| Unverified outcome | Hard | Platform taught by unreliable reports |
| Latency mismatch | Medium | Signal arrives against a changed platform state |
| Undisclosed execution deviation | Hard | Outcome attributed to a solution that was not executed |

#### Example

```
object_id:              XR-0088
object_type:            Execution Record
version:                1
lineage_id:             XRL-0088
produced_by_engine:     <UNDEFINED — CONTRADICTION-02>
derives_from:           [SO-0402 v2]
outcome_of_solution:    SO-0402 v2
execution_description:  Per-item outcome reporting introduced for bulk listing
                        operations in a limited seller cohort, with partial
                        failures surfaced at operation completion.
executed_at:            2026-06-01T00:00:00Z
outcome_observed_at:    2026-07-15T00:00:00Z
outcome:                Silent-failure complaints from the cohort fell
                        substantially. Remediation of reported failures
                        remained low at high failure volumes, consistent with
                        the VA-0771 finding.
outcome_valence:        MIXED
attribution_assessment: Complaint reduction is plausibly attributable, as no
                        other change affected the cohort in the period.
                        Remediation behaviour is not attributable to the
                        solution, since it reflects seller response capacity
                        rather than reporting availability.
prediction_comparison:  OP-0157 predicted value from eliminating delayed
                        discovery. Discovery delay was reduced as predicted.
                        The predicted downstream benefit was only partially
                        realised, matching the narrowing VA-0771 identified.
outcome_verification:   <PARTIAL — MISSING-47, no verification standard>
external_factors:       Seasonal volume variation in the observation period.
evidential_support:     0.55  (MODERATE)
assertion_confidence:   0.47  (MODERATE)
effective_confidence:   0.47  (MODERATE)
status:                 ACTIVE
explanation:            Records both the confirmed and unconfirmed portions of
                        the prediction. Attribution is limited deliberately:
                        the favourable portion is attributable, the
                        unfavourable portion is not clearly so, and the record
                        states both rather than resolving to a single verdict.
```

---

### 3.9 Feedback Record Object

**Status: specified under D-07, resolving CONTRADICTION-03. Adds a ninth object type to v1's eight — requires ratification.**

#### Purpose
Record a lesson derived from execution outcomes, what platform behaviour it changes, and how that change can be reversed.

#### Responsibilities
1. State the lesson learned from one or more Execution Records.
2. Identify the target of the change — which engine behaviour or configuration.
3. Record the change made.
4. Record how to reverse it.
5. Link to the motivating Execution Records.

#### Why This Object Exists
Every other pipeline stage produces a persisted object. The Feedback stage did not, meaning learning updates would alter platform behaviour with **no persistent record** — breaching Principle 3, making learning irreversible against PKP v2 §2.5's requirements, and leaving untraceable drift unmitigated.

The object is required by v1's own principles. Specifying it completes the architecture rather than extending it.

#### Lifecycle
Created when the Feedback Engine derives a lesson. May be reversed — reversal is a status transition to `RETRACTED` with the reversal recorded, preserving the record that the lesson was once applied.

#### State Transitions

| From | To | Trigger |
|---|---|---|
| — | `PROPOSED` | Lesson derived |
| `PROPOSED` | `ACTIVE` | Change applied (approval undefined — OPEN QUESTION-05) |
| `PROPOSED` | `REJECTED` | Lesson judged unsound or insufficiently supported |
| `ACTIVE` | `SUPERSEDED` | Superseded by a later lesson on the same target |
| `ACTIVE` | `RETRACTED` | Change reversed |
| `ACTIVE` | `INVALIDATED` | Motivating Execution Records invalidated |
| `ACTIVE` | `ARCHIVED` | Retention |

#### Required Attributes

Universal, plus:

| Attribute | Meaning |
|---|---|
| `motivating_records` | Execution Records prompting the lesson |
| `lesson_statement` | What was learned |
| `change_target` | What behaviour or configuration changes (MISSING-02) |
| `change_description` | The change made |
| `reversal_procedure` | How to undo it |
| `informs` | `INFORMS` references to affected engines |
| `applied_at` | When the change took effect |
| `evidence_of_pattern` | Why this is a genuine lesson, not noise |

`evidence_of_pattern` is mandatory to counter overfitting. A single unfavourable outcome is not a lesson; requiring explicit justification that a pattern exists across outcomes forces the distinction between signal and noise to be stated rather than assumed.

`reversal_procedure` is mandatory because irreversible learning is unrecoverable learning.

> **MISSING-02 (restated, blocking):** The learning target is undefined. `change_target` is required but has no defined vocabulary — candidates include scoring weights, extraction criteria, source trust, validation thresholds, pattern definitions. **The Feedback Record cannot be fully implemented until MISSING-02 is resolved.**

#### Optional Attributes

| Attribute | Meaning |
|---|---|
| `magnitude` | Size of the adjustment |
| `expected_effect` | What the change is expected to improve |
| `observed_effect` | What it actually improved, assessed later |
| `superseded_lesson` | Prior lesson this revises |
| `approval_record` | Who approved, if approval applies (OPEN QUESTION-05) |

`expected_effect` paired with `observed_effect` allows the platform to learn about its own learning — assessing whether feedback improved anything. Without a success measure (PKP v2 MISSING-04), `observed_effect` cannot currently be evaluated.

#### Validation Rules

| # | Rule |
|---|---|
| FR-V1 | `motivating_records` non-empty and resolvable |
| FR-V2 | `change_target` present |
| FR-V3 | `reversal_procedure` present and actionable |
| FR-V4 | `evidence_of_pattern` justifies the lesson beyond a single outcome |
| FR-V5 | `informs` identifies specific affected engines |
| FR-V6 | Does not derive from any object other than Execution Records |

FR-V6 enforces that learning comes from **outcomes**, not from the platform's own inferences. Without it, the platform could learn from its own conclusions — the self-reinforcement failure MISSING-27 warns of.

#### Integrity Constraints

| # | Constraint |
|---|---|
| FR-I1 | Every applied change is reversible |
| FR-I2 | Never becomes Evidence (guards CONTRADICTION-04) |
| FR-I3 | Never modifies historical objects |
| FR-I4 | Cumulative effect of active records remains determinable |

FR-I2 is the enforcement point for the loop-closure decision taken in E-I2: feedback influences future behaviour and may trigger new research, but never enters the lineage graph as grounding.

FR-I4 counters accumulated untraceable drift: it must always be possible to state the total current deviation from baseline behaviour.

#### Versioning
Low. Lessons are superseded rather than revised.

#### Confidence
`evidential_support` reflects the volume and consistency of motivating Execution Records. `assertion_confidence` reflects certainty the inferred lesson is correct — distinct, since many consistent outcomes may still support a wrong causal lesson.

#### Lineage
`DERIVES_FROM` Execution Records only (FR-V6). Depth 8 — the deepest object type. `INFORMS` targets engines, which is the only relationship pointing at something other than an object, and is deliberately not part of the lineage graph.

#### Relationships

| Relationship | Target |
|---|---|
| `INFORMS` | Engine behaviour or configuration |
| `SUPERSEDES` | Feedback Record |
| `CONTRADICTS` | Feedback Record (conflicting lessons) |

#### Engine Authority
**Create:** Feedback. **Modify:** Feedback. **Read:** All engines (subject to OPEN QUESTION-22).

#### Owning Stage
Stage 9 — Feedback.

#### Failure Cases

| Failure | Detection | Consequence |
|---|---|---|
| Overfitting to few outcomes | Medium | Behaviour swings on noise |
| Irreversible change | Easy | No recovery from a bad lesson |
| Untraceable cumulative drift | Hard | Regression undiagnosable |
| Learning from platform output | Medium | Self-reinforcing belief (MISSING-27) |
| No-op feedback | Easy | Breaches Principle 5; loop decorative |
| Attribution error inherited | Very hard | Correct process, wrong lesson |
| Signal starvation | Easy | Loop nominally closed, functionally open |

#### Example

```
object_id:              FR-0021
object_type:            Feedback Record
version:                1
lineage_id:             FRL-0021
produced_by_engine:     Feedback
derives_from:           [XR-0088 v1, XR-0091 v1, XR-0103 v2]
motivating_records:     [XR-0088 v1, XR-0091 v1, XR-0103 v2]
lesson_statement:       Opportunities whose value depends on a behavioural
                        response from an already-overloaded population have
                        been systematically over-assessed. In all three
                        records, the mechanism worked as predicted but the
                        expected behavioural response did not follow at scale.
change_target:          <VOCABULARY UNDEFINED — MISSING-02>
                        Intended: Opportunity Intelligence assertion_confidence
                        calibration where the value hypothesis depends on
                        population behaviour change.
change_description:     Reduce assertion_confidence for opportunities whose
                        value_hypothesis depends on a behavioural response not
                        directly evidenced in the underlying Facts.
evidence_of_pattern:    Three independent execution records across two
                        distinct opportunity domains show the same divergence:
                        mechanism confirmed, behavioural response not realised.
                        The consistency across domains distinguishes this from
                        a domain-specific effect.
reversal_procedure:     Restore prior calibration; rescore affected
                        opportunities under the prior score_model_version,
                        retaining both versions for comparison.
informs:                [Opportunity Intelligence]
applied_at:             2026-07-28T00:00:00Z
expected_effect:        Better alignment between predicted and realised value
                        for behaviour-dependent opportunities.
observed_effect:        <NOT YET ASSESSABLE — MISSING-04, no success measure>
evidential_support:     0.51  (MODERATE)
assertion_confidence:   0.44  (MODERATE)
effective_confidence:   0.44  (MODERATE)
status:                 ACTIVE
explanation:            Three records is a thin basis, reflected in moderate
                        confidence. Recorded as a calibration adjustment rather
                        than a rule change, and fully reversible, because the
                        supporting volume does not justify a structural change.
```
---

## 4. Object Transformation and Dependency Diagram

### 4.1 Primary Transformation Chain

Each transformation shows the owning engine, the cardinality of the transformation, and the lineage depth reached.

```
   EXTERNAL WORLD
        │
        │  acquisition (Research Engine)
        ▼
┌───────────────────┐
│     EVIDENCE      │  depth 0 — root, no upstream lineage
│   Stage 1         │  Create: Research
└─────────┬─────────┘
          │  DERIVES_FROM        1 Evidence → many Facts
          │  extraction (Fact Extraction Engine)
          ▼
┌───────────────────┐
│       FACT        │  depth 1 — canonical claim, many attachments
│   Stage 2         │  Create: Fact Extraction
└─────────┬─────────┘
          │  DERIVES_FROM + SUPPORTS    many Facts → 1 Problem
          │  inference (Problem Intelligence Engine)
          ▼
┌───────────────────┐
│     PROBLEM       │  depth 2 — first interpretive object
│   Stage 3         │  Create: Problem Intelligence
└─────────┬─────────┘
          │  DERIVES_FROM + CONSTITUENT_OF   many Problems → 1 Pattern
          │  aggregation (Pattern Intelligence Engine)
          ▼
┌───────────────────┐
│     PATTERN       │  depth 3 — narrow waist; ≥2 constituents required
│   Stage 4         │  Create: Pattern Intelligence
└─────────┬─────────┘
          │  DERIVES_FROM        1 Pattern → 1..n Opportunities
          │  valuation (Opportunity Intelligence Engine)
          ▼
┌───────────────────┐
│   OPPORTUNITY     │  depth 4 — platform's primary output
│   Stage 5         │  Create: Opportunity Intelligence
└─────────┬─────────┘
          │  DERIVES_FROM + ADDRESSES    1 Opportunity → many Solutions
          │  formulation (Solution Intelligence Engine)
          ▼
┌───────────────────┐
│     SOLUTION      │  depth 5 — assumptions are the testable surface
│   Stage 6         │  Create: Solution Intelligence
└─────────┬─────────┘
          │  DERIVES_FROM + TESTS    1 Solution → many Validations
          │  testing (Validation Engine)              (one per assumption)
          ▼
┌───────────────────┐
│    VALIDATION     │  depth 6 — attaches to claims, not objects
│   Stage 7         │  Create: Validation
└─────────┬─────────┘
          │
          ╎  ✗ BREAK — no engine owns this transformation
          ╎  CONTRADICTION-02 / MISSING-36
          ╎
          ▼
┌───────────────────┐
│ EXECUTION RECORD  │  depth 7 — only ground-truth object
│   Stage 8         │  Create: UNDEFINED
└─────────┬─────────┘
          │  DERIVES_FROM + OUTCOME_OF   many Records → 1 Feedback Record
          │  learning (Feedback Engine)
          ▼
┌───────────────────┐
│  FEEDBACK RECORD  │  depth 8 — specified under D-07
│   Stage 9         │  Create: Feedback
└─────────┬─────────┘
          │  INFORMS — engine behaviour, NOT lineage
          ▼
   ENGINE BEHAVIOUR ──────┐
                          │  may trigger new research directive
                          ▼
                   EXTERNAL WORLD
                   (loop closes via new acquisition,
                    NOT by feedback becoming Evidence)
```

### 4.2 Loop Closure — How the Cycle Actually Closes

v1's pipeline notation reads `Feedback -> Evidence`, which CONTRADICTION-04 identifies as incompatible with Evidence's grounding property. This specification resolves it as follows:

```
   ┌──────────────────────────────────────────────────────┐
   │                                                      │
   │   FEEDBACK RECORD ──INFORMS──▶ Engine behaviour      │
   │                                      │               │
   │                                      │ may raise     │
   │                                      ▼               │
   │                              Research directive      │
   │                                      │               │
   │                                      ▼               │
   │                              EXTERNAL WORLD          │
   │                                      │               │
   │                                      │ acquisition   │
   │                                      ▼               │
   └──────────────────────────────▶  NEW EVIDENCE  ───────┘
                                    (external origin,
                                     no upstream lineage)
```

**The loop closes behaviourally, not through lineage.** Feedback changes what the platform researches and how it reasons; it never becomes Evidence itself (E-I2, FR-I2).

Consequences:
- The lineage graph remains acyclic (V10 holds).
- Evidence retains its grounding property — every trace terminates at external observation.
- Self-reinforcement through the lineage graph is structurally impossible.
- The platform still learns, and learning still influences future evidence acquisition.

**This adopts reading (b) of CONTRADICTION-04 and requires ratification.** Reading (a) — feedback becoming Evidence directly — would create lineage cycles, violate E-I2, and enable the platform to treat its own output as observation.

### 4.3 Cardinality and Volume Profile

| Transformation | Cardinality | Volume effect |
|---|---|---|
| External → Evidence | 1:1 | Entry |
| Evidence → Fact | 1:many | **Expansion** |
| Fact → Problem | many:1 | Consolidation |
| Problem → Pattern | many:1 | **Strong consolidation** |
| Pattern → Opportunity | 1:many | **Expansion** |
| Opportunity → Solution | 1:many | Expansion |
| Solution → Validation | 1:many | Expansion (one per assumption) |
| Validation → Execution Record | many:few | **Strong narrowing** |
| Execution Record → Feedback Record | many:1 | Consolidation |

The profile is **expand → consolidate → expand → narrow**. Pattern is the narrow waist: cost expands on both sides of it, so its discrimination quality determines whether downstream expansion is justified. A weak Pattern stage means the platform spends heavily on both sides of a poor filter.

### 4.4 Confidence Ceiling Propagation

```
EVIDENCE      effective 0.62 ─┐
                              │ ceiling
FACT          asserted 0.84 ──┼──▶ effective 0.62
                              │
PROBLEM       asserted 0.74 ──┼──▶ effective 0.62
                              │
PATTERN       asserted 0.71 ──┼──▶ effective 0.62
                              │
OPPORTUNITY   asserted 0.58 ──┴──▶ effective 0.58  ← own assertion now lower
                                                     than inherited ceiling
SOLUTION      asserted 0.61 ─────▶ effective 0.58  ← ceiling reasserts
```

Four confident inferential steps over moderate evidence yield a moderate conclusion, not a confident one. Without the ceiling rule, the same chain would compound to apparent near-certainty. This is the platform's structural defence against confidence inflation.

### 4.5 Relationship Map

```
                    ┌──────────────┐
                    │   EVIDENCE   │◀──── DUPLICATES, CONTRADICTS (peer)
                    └──────┬───────┘
                           │ DERIVES_FROM (attachments)
                    ┌──────▼───────┐
                    │     FACT     │◀──── DUPLICATES, CONTRADICTS (peer)
                    └──────┬───────┘
                           │ DERIVES_FROM, SUPPORTS
                    ┌──────▼───────┐
                    │   PROBLEM    │◀──── ADDRESSES (from Solution)
                    └──────┬───────┘
                           │ DERIVES_FROM, CONSTITUENT_OF
                    ┌──────▼───────┐
                    │   PATTERN    │
                    └──────┬───────┘
                           │ DERIVES_FROM
                    ┌──────▼───────┐
                    │ OPPORTUNITY  │◀──── ADDRESSES (from Solution)
                    └──────┬───────┘
                           │ DERIVES_FROM, ADDRESSES
                    ┌──────▼───────┐
                    │   SOLUTION   │◀──── TESTS (from Validation)
                    └──────┬───────┘      OUTCOME_OF (from Execution Record)
                           │ DERIVES_FROM, TESTS
                    ┌──────▼───────┐
                    │  VALIDATION  │◀──── CONTRADICTS (peer: conflicting results)
                    └──────┬───────┘
                           ╎ ✗ no owning engine
                    ┌──────▼───────┐
                    │  EXECUTION   │
                    │    RECORD    │
                    └──────┬───────┘
                           │ DERIVES_FROM, OUTCOME_OF
                    ┌──────▼───────┐
                    │   FEEDBACK   │──INFORMS──▶ engine behaviour
                    │    RECORD    │             (outside lineage graph)
                    └──────────────┘

SUPERSEDES applies within every type (version chains, all types)
```

### 4.6 Engine Authority Overview

```
ENGINE                      CREATES              READS
─────────────────────────────────────────────────────────────────────
Research                    Evidence             —  (external sources)
Fact Extraction             Fact                 Evidence
Problem Intelligence        Problem              Fact
Pattern Intelligence        Pattern              Problem
Opportunity Intelligence    Opportunity          Pattern
Solution Intelligence       Solution             Opportunity, Problem†
Validation                  Validation           Solution, Opportunity†
UNDEFINED  ✗                Execution Record     Solution
Feedback                    Feedback Record      Execution Record, and
                                                 upstream for comparison
Orchestration               — (no objects)       status metadata only

† subject to OPEN QUESTION-21 (cross-stage read access)
```

Exactly one engine creates each type. Orchestration creates nothing and reads no content — preserving its non-interpretive boundary.

---

## 5. Residual Missing Definitions

Definitions still required before implementation. Numbering continues from PKP v2, which ended at MISSING-57, OPEN QUESTION-33, CONTRADICTION-08.

### 5.1 Resolved by This Document

| Marker | Resolution |
|---|---|
| MISSING-35 / CONTRADICTION-08 | Object attributes specified for all nine types |
| MISSING-08 | D-01: immutable, versioned |
| MISSING-45 | D-02: seven-state lifecycle |
| MISSING-15 | D-03: two-component confidence, ceiling rule |
| MISSING-46 | D-04: explicit temporal validity |
| MISSING-11 | D-05: canonical claims with attachments |
| MISSING-32 | D-06: closed relationship taxonomy |
| CONTRADICTION-03 | D-07: Feedback Record specified |
| OPEN QUESTION-03 | `CONTRADICTS` relationship — disagreement represented |
| OPEN QUESTION-04 | D-02: rejected candidates retained |
| CONTRADICTION-04 | §4.2: behavioural loop closure — **provisional, requires ratification** |
| CONTRADICTION-06 | D-08: objects authoritative, graph derived — **partial** |

### 5.2 New Gaps Arising From This Specification

| ID | Missing definition | Blocks | Severity |
|---|---|---|---|
| **M-58** | Cascade invalidation owner — no engine walks lineage to invalidate dependents when Evidence is retracted (I6 unenforceable) | P1 | **Critical** |
| **M-59** | `evidential_support` computation function from lineage | P4+ | **Critical** |
| **M-60** | Confidence calibration across engines — one engine's 0.7 need not mean another's | All engines | **Critical** |
| **M-61** | Staleness assessment owner — ageing visible but unactioned | P5+ | High |
| **M-62** | Semantic equivalence criterion for Fact merging (D-05) | P3 | **Critical** |
| **M-63** | Engine configuration referent — `engine_configuration_ref` required but has no home | P1 | **Critical** |
| **M-64** | Acceptance authority — who enforces V1–V12 at `PROPOSED` → `ACTIVE` | P1 | **Critical** |
| **M-65** | Re-derivation policy when upstream objects are superseded | P4+ | High |
| **M-66** | Lineage summarisation — deep objects have humanly un-inspectable evidence sets | P5+ | High |
| **M-67** | **Hallucinated fact detection — F-V6 is stated but unenforceable by structure** | P3 | **Critical** |

### 5.3 Pre-existing Gaps That Block Object Implementation

These remain unresolved from PKP v2 and directly prevent objects from being fully populated:

| Marker | Gap | Object blocked |
|---|---|---|
| **MISSING-14** | No scoring dimensions, scale, methodology | **Opportunity — cannot reach `ACTIVE`** |
| **MISSING-25** | No validation methodology vocabulary | **Validation — `validation_method` unpopulatable** |
| **MISSING-02** | No learning target vocabulary | **Feedback Record — `change_target` unpopulatable** |
| **CONTRADICTION-02** | No Execution Engine | **Execution Record — no create authority** |
| MISSING-36 | No outcome intake mechanism | Execution Record |
| MISSING-47 | No outcome verification standard | Execution Record |
| MISSING-12 | No severity/frequency scales | Problem — attributes unscaled |
| MISSING-24 | No constraint model | Solution — `constraints` unpopulatable |
| MISSING-18 | No source taxonomy | Evidence — `source_type` unscoped |
| MISSING-22 | Source diversity not propagated forward | Pattern — `source_diversity` uncomputable |
| MISSING-06 | No evidence sufficiency thresholds | Problem, Pattern — plurality unquantified |
| MISSING-26 | No gate ownership | Solution, Opportunity — status transitions unowned |
| MISSING-31 | No retention policy | All — `ARCHIVED` transition unowned |
| OPEN QUESTION-21 | Cross-stage read access | Solution, Validation — authority ambiguous |
| OPEN QUESTION-23 | Concurrency model | All — versioning serialisation assumed |

### 5.4 New Open Questions

| ID | Question | Affects |
|---|---|---|
| **OQ-34** | Should the confidence ceiling use `min` or a weighted function? `min` cannot inflate but may understate genuine corroboration | All objects |
| **OQ-35** | Should Pattern constituent addition always create a version, or should membership be a relationship on the Problem? | Pattern versioning churn |

### 5.5 Implementation Readiness by Object

| Object | Status | Blocking |
|---|---|---|
| Evidence | **Implementable** with source taxonomy caveat | MISSING-18 (scoping only) |
| Fact | **Blocked** | M-62, M-67 |
| Problem | Implementable with unscaled attributes | MISSING-12, MISSING-06 |
| Pattern | **Blocked** | MISSING-22 |
| Opportunity | **Blocked** | MISSING-14 |
| Solution | Implementable with partial constraints | MISSING-24 |
| Validation | **Blocked** | MISSING-25, CONTRADICTION-05 |
| Execution Record | **Blocked** | CONTRADICTION-02, MISSING-36 |
| Feedback Record | **Blocked** | MISSING-02 |

Plus five cross-cutting blockers affecting every object: M-58, M-59, M-60, M-63, M-64.

### 5.6 Resolution Priority

**Tier 1 — Ratify the decisions in §0.4.** Nothing in this document is authoritative until D-01 through D-08 are accepted or amended. Two require particular attention: **D-07** adds a ninth object type, and the **CONTRADICTION-04 resolution in §4.2** determines whether the lineage graph remains acyclic.

**Tier 2 — Cross-cutting blockers.** M-63 (configuration referent), M-64 (acceptance authority), M-58 (cascade invalidation), M-59 (support function), M-60 (calibration). These affect every object and must precede P1.

**Tier 3 — Integrity enforcement.** M-67 (hallucination detection) and M-62 (semantic equivalence). Both concern the Fact object, which is the platform's integrity floor. M-67 is the highest-severity gap in the model: a hallucinated fact satisfies every structural rule in this specification while being false.

**Tier 4 — Vocabularies.** MISSING-14 (scoring), MISSING-25 (validation methods), MISSING-02 (learning targets), MISSING-12 (weight scales), MISSING-24 (constraints). Each unblocks exactly one object type.

**Tier 5 — Structural.** CONTRADICTION-02 and MISSING-36. The Execution Record cannot be created by anything defined in v1, leaving the learning loop open.

---

## 6. Document Control

### 6.1 Coverage

All eighteen required dimensions are specified for all nine object types: purpose, responsibilities, existence rationale, lifecycle, state transitions, required attributes, optional attributes, validation rules, integrity constraints, versioning, confidence, lineage, relationships, create authority, modify authority, read authority, owning stage, failure cases, examples.

### 6.2 Preservation Statement

No engine, pipeline stage, shared component, principle, architecture decision or roadmap phase is added, removed, renamed or reordered. One object type — the Feedback Record — is added under D-07, which resolves a contradiction in v1 rather than introducing a feature: v1 defines a Feedback stage and a Feedback Engine, and every other stage-engine pair produces a persisted object.

Eight architecture decisions (D-01 to D-08) were required to make the object model specifiable. Each is recorded with alternatives rejected and consequences accepted. **None is assumed; all require ratification.**

### 6.3 Exclusions Observed

No code. No schemas, field types, or serialisation formats. No interfaces, access methods, or protocols. No user interface. No business features. No roadmap continuation.

### 6.4 Marker Totals

| Category | Count |
|---|---|
| Decisions requiring ratification | 8 |
| Markers resolved | 12 |
| New missing definitions | 10 (M-58 to M-67) |
| New open questions | 2 (OQ-34, OQ-35) |
| Pre-existing blockers confirmed | 15 |
| Objects fully implementable | 0 of 9 |

### 6.5 Standing Instruction

This specification is the contract surface for the platform. Any change to an object type, attribute, validation rule, integrity constraint, relationship type or engine authority is a contract change affecting every engine that touches the object, and requires a recorded decision stating what changed, why, and which alternatives were rejected.

Markers must be resolved by recorded decision, never closed by implementation choice — an architecture decision made in code is an architecture decision that cannot be found.

---

*End of Intelligence Object Model — Complete Specification.*
