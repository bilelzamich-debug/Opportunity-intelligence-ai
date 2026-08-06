# Opportunity Intelligence Platform
## Project Knowledge Pack (PKP) v2 — Master Reference

**Document status:** Master reference for implementation
**Supersedes:** PKP v1 – Foundation
**Relationship to v1:** Expansion only. No section removed, no engine added, no engine renamed, no pipeline stage reordered, no principle altered.

---

## 0. How To Use This Document

### 0.1 Purpose

This document is the single authoritative reference for the Opportunity Intelligence Platform. It expands every section of PKP v1 – Foundation into implementation-grade detail while preserving the original philosophy and architecture without modification.

Every downstream artefact — phase plans, engine specifications, data contracts, test strategies, review checklists — is expected to trace back to a section of this document.

### 0.2 Expansion Rules Applied

The following rules governed the production of this document and must govern its future revision:

1. **Preservation over improvement.** Where v1 made a choice, that choice is documented and elaborated, never replaced. Where a v1 choice appears suboptimal, the concern is recorded as an OPEN QUESTION rather than silently corrected.
2. **No invented structure.** No engine, object, pipeline stage, shared component, principle, or phase exists in this document that did not exist in v1.
3. **No assumption filling.** Where v1 is silent on something implementation cannot proceed without, the gap is marked, not guessed.
4. **No code, no interface design, no user interface.** This document describes responsibilities, boundaries, semantics and sequencing. It deliberately stops short of technical realisation.

### 0.3 Annotation Conventions

Three annotation types appear throughout. They are normative — each one is a blocking item that must be resolved before the affected component can be implemented.

| Marker | Meaning | Resolution owner |
|---|---|---|
| **MISSING** | A required definition, rule, threshold, or artefact that v1 does not provide and that cannot be derived from what v1 does provide. Implementation of the affected component cannot begin. | Platform architecture |
| **OPEN QUESTION** | A genuine decision point where more than one defensible answer exists and v1 does not indicate which was intended. Implementation may begin only after a decision is recorded. | Platform architecture |
| **CONTRADICTION** | Two or more statements in v1 that cannot both be satisfied as written, or a structural inconsistency between v1 sections. Must be reconciled explicitly; the reconciliation is a change to the architecture and requires a decision record. | Platform architecture |

All markers are consolidated in registers in Sections 11, 12 and 13. The inline occurrence is the definitive statement; the register is an index.

### 0.4 Terminology Precision

Three words are used with strict meaning throughout:

- **Engine** — a processing unit from v1 §4. Engines transform objects. Engines are the only things that create or modify Intelligence Objects.
- **Object** — an Intelligence Object from v1 §6. Objects are the only things that persist as platform knowledge.
- **Stage** — a step in the pipeline from v1 §3. Stages are positions in a sequence, not processing units.

The distinction matters because v1 uses overlapping names across all three categories. See CONTRADICTION-01 through CONTRADICTION-04.

---

## 1. Vision — Expanded

### 1.1 v1 Statement (Preserved Verbatim)

> Build an AI-native Opportunity Intelligence Platform that discovers, validates, scores, and learns from market opportunities using evidence-first reasoning.

### 1.2 Decomposition of the Vision Statement

The vision statement contains five load-bearing commitments. Each is binding on the architecture.

**1.2.1 "AI-native"**

The platform is not a conventional data system with AI features attached. Reasoning, extraction, synthesis and judgement are performed by model-driven engines as the primary mechanism, not as an enrichment layer over deterministic processing. Consequences:

- Non-determinism is a first-class property of the system, not a defect. Outputs vary between runs on identical inputs.
- Every engine output must therefore carry the context necessary to interpret it: what produced it, from what inputs, under what configuration.
- Correctness cannot be asserted by equality checking. It is asserted by evidence linkage, explanation quality, and downstream validation.

> **OPEN QUESTION-01:** v1 does not state whether identical inputs are expected to produce identical outputs (determinism/reproducibility requirement). This determines whether engine runs must be replayable, whether model versions and configuration must be pinned and stored, and whether re-running the pipeline over historical evidence is a supported operation. This affects every engine and both knowledge components.

**1.2.2 "discovers"**

The platform actively surfaces opportunities that were not specified in advance. It is generative with respect to its output set, not merely a filter over a candidate list supplied by a user.

> **MISSING-01:** v1 does not define what initiates discovery. There is no statement of whether the pipeline runs continuously, on a schedule, on external trigger, or in response to a scoped request (e.g. "investigate this market"). This determines the entire control model of the Orchestration Engine.

**1.2.3 "validates"**

Claims produced by the platform are subjected to a defined verification step before being treated as reliable. Validation is both a pipeline stage (v1 §3), an engine (v1 §4), and an object (v1 §6) — the most heavily represented concept in v1, indicating its centrality.

**1.2.4 "scores"**

Opportunities carry comparative quantitative assessment enabling ranking and prioritisation.

> **CONTRADICTION-01:** Scoring is named in the vision as one of four core platform capabilities, but v1 defines no Scoring Engine (§4), no scoring stage (§3), and no score object (§6). Three reconciliations are possible and v1 does not indicate which was intended: (a) scoring is a responsibility internal to the Opportunity Intelligence Engine; (b) scoring is a cross-cutting capability performed at multiple stages, with each engine scoring its own outputs; (c) scoring is an omitted engine. Option (c) would add an engine and is therefore out of scope for this document. This must be resolved before P6.

**1.2.5 "learns from"**

The platform's behaviour changes over time as a function of outcomes. This is reinforced by Principle 5 (Continuous Learning), the Feedback Engine, and the closing arc of the pipeline.

> **MISSING-02:** v1 does not define what changes when the platform learns. Candidate targets include: scoring weights, pattern definitions, extraction prompts/criteria, source trust ratings, validation thresholds, opportunity taxonomies. Without this, the Feedback Engine has no defined output target and the learning loop cannot be implemented.

**1.2.6 "evidence-first reasoning"**

No conclusion exists without traceable supporting evidence. This is the platform's defining constraint and is restated as Principle 1 and Architecture Decision 1.

### 1.3 Scope Boundaries

Derived strictly from what v1 includes and excludes.

**In scope (explicit in v1):**
- Acquisition of evidence about markets
- Extraction of discrete factual claims from evidence
- Identification of problems from facts
- Recognition of patterns across problems
- Formulation of opportunities from patterns
- Formulation of solutions addressing opportunities
- Validation of solutions and/or opportunities
- Recording of execution outcomes
- Feedback processing into platform improvement
- Persistent knowledge storage, graph relationships, and experiment tracking

**Out of scope (absent from v1 — recorded as absence, not as exclusion):**
- Anything not enumerated above. v1 does not contain an explicit non-goals statement.

> **MISSING-03:** v1 contains no non-goals / explicit exclusions section. Enterprise reference documentation requires stated boundaries to prevent scope drift, particularly around: whether the platform executes on opportunities or only recommends them (see CONTRADICTION-02), whether it serves a single organisation or multiple tenants, and whether it operates in a single market domain or arbitrary domains.

### 1.4 Success Criteria

> **MISSING-04:** v1 defines no success criteria, acceptance thresholds, or measures of platform effectiveness. Because Principle 5 requires continuous learning and the Feedback Engine requires an improvement signal, the absence of a defined measure of "better" blocks the design of the learning loop. At minimum the following are undefined: opportunity quality measure, validation pass rate expectations, evidence coverage targets, false-positive tolerance.

### 1.5 Intended Consumers of Platform Output

> **MISSING-05:** v1 does not identify who or what consumes the platform's output, nor at which stage output leaves the platform. This affects the boundary between the Validation stage, the Execution stage, and the outside world, and determines where human judgement enters the system (see OPEN QUESTION-02).

> **OPEN QUESTION-02:** v1 makes no reference to human involvement at any point. Whether the platform is fully autonomous, human-supervised at defined gates, or human-in-the-loop throughout is undetermined. This is architecturally significant: it determines whether objects require approval states, whether engines can block awaiting input, and whether the Orchestration Engine manages waits of unbounded duration.

---

## 2. Principles — Expanded

The five principles from v1 §2 are preserved exactly. Each is expanded below into a normative statement, its rationale, its binding implications on the architecture, the anti-patterns it forbids, and how conformance is verified.

### 2.1 Principle 1 — Evidence Before Conclusions

**Statement.** No conclusion may be created, stored, or propagated unless it references the evidence from which it derives.

**Rationale.** In a model-driven system, plausible-sounding output is cheap. Evidence linkage is the mechanism that distinguishes a supported claim from a fluent one. This principle is what makes the platform's output trustworthy enough to act on.

**Binding implications.**
- Every Intelligence Object except Evidence itself must reference at least one upstream object, terminating in Evidence.
- An object with no evidence path to Evidence is invalid and must be rejected at creation, not filtered at read time.
- Engines may not introduce claims from model parametric knowledge. Where a model contributes reasoning, the inputs to that reasoning must be evidence-derived objects.
- Confidence and evidence are different things. An object may be well-evidenced and low-confidence, or poorly-evidenced and high-confidence — the latter must be detectable.

**Forbidden anti-patterns.**
- Creating a Problem, Pattern, Opportunity or Solution during exploratory reasoning and attaching evidence afterwards to justify it.
- Aggregating away evidence links during summarisation.
- Treating an engine's own prior output as evidence without preserving the path to the original Evidence objects.

**Verification.** Evidence linkage is structurally checkable: every object must resolve to a non-empty set of Evidence objects by following lineage. This is the single most important platform invariant.

> **MISSING-06:** v1 does not define minimum evidence sufficiency. It is undefined whether one Evidence object is sufficient to support a Fact, how many Facts constitute a Problem, or how many Problems constitute a Pattern. Without thresholds, "evidence before conclusions" is satisfiable by a single weak source and the principle loses force. Required per object type.

> **OPEN QUESTION-03:** v1 does not state whether contradictory evidence must be represented. If two Evidence objects support opposing Facts, it is undefined whether the platform holds both, selects one, or flags a conflict. This determines whether Facts require a contradiction relationship and whether the Knowledge Graph must represent disagreement.

### 2.2 Principle 2 — Explainable Decisions

**Statement.** Every decision the platform makes must be accompanied by a human-readable account of why it was made.

**Rationale.** The platform's output drives resource allocation decisions. An unexplained ranking is not actionable, cannot be challenged, and cannot be improved.

**Binding implications.**
- Every engine that selects, ranks, scores, filters, promotes or rejects must emit the reasoning alongside the result.
- Explanation is an output, not a log. It is part of the object, persisted with it, and travels with it downstream.
- Rejections are decisions. Discarded candidates require explanations as much as accepted ones.
- Explanation must reference the specific evidence and criteria used, not restate the conclusion.

**Forbidden anti-patterns.**
- Opaque numeric scores with no accompanying rationale.
- Explanations generated after the fact by a separate process that did not perform the decision.
- Silent filtering — dropping candidates without record.

**Verification.** Every decision-bearing object field has a corresponding explanation field that is non-empty and references at least one input object.

> **MISSING-07:** v1 does not define the required form, granularity, or minimum content of an explanation. It is undefined whether an explanation is free text, structured reasoning steps, a criteria-by-criteria breakdown, or a combination. This blocks consistent implementation across all nine engines and makes explanations non-comparable.

> **OPEN QUESTION-04:** It is undefined whether rejected candidates are persisted. Principle 2 implies rejections are explainable; Principle 5 implies negative outcomes are learning signal; but v1 §6 defines no object for a rejected candidate. Discarding them makes the platform unable to learn from what it declined.

### 2.3 Principle 3 — Traceable Lineage

**Statement.** For any object in the platform, the complete derivation path from source Evidence to that object must be reconstructable.

**Rationale.** Lineage is what makes evidence-first reasoning auditable rather than merely claimed. It also enables impact analysis: when evidence is retracted or corrected, everything derived from it must be identifiable.

**Binding implications.**
- Lineage is a first-class stored relationship, not a derived or inferred one.
- Lineage must record which engine performed each transformation, and under what conditions.
- Lineage must survive aggregation. When many objects collapse into one, all contributing links are retained.
- Retraction propagation must be possible: invalidating an Evidence object must identify every downstream object affected.

**Forbidden anti-patterns.**
- Lineage stored only in logs rather than as queryable structure.
- Lossy merges that record "derived from multiple sources" without enumerating them.
- Overwriting objects in place, destroying the historical derivation.

**Verification.** For any randomly selected non-Evidence object, a complete path to Evidence can be produced, with every intermediate transformation attributed to a named engine.

> **MISSING-08:** v1 does not define object mutability. It is undefined whether objects are immutable with new versions created on change, or mutable in place. Traceable lineage strongly implies versioning, but v1 does not state it. This affects the Knowledge Store, the Knowledge Graph, and every engine's write behaviour, and must be settled in P1.

> **MISSING-09:** v1 defines no retraction or correction semantics. When evidence is found to be false, superseded, or removed at source, the required behaviour for downstream objects is undefined (cascade invalidation, flag-and-review, recompute, or no action).

### 2.4 Principle 4 — Modular Engines

**Statement.** Each engine is independently definable, independently replaceable, and communicates only through Intelligence Objects.

**Rationale.** The platform's engines will evolve at different rates. Model-driven components in particular will be replaced frequently. Modularity confines the blast radius of change.

**Binding implications.**
- Engines do not call each other. Engines consume objects and produce objects; sequencing is the Orchestration Engine's responsibility.
- No engine may depend on another engine's internal reasoning, prompt design, model choice, or intermediate state.
- The contract between engines is the object definition (v1 §6) and nothing else — this is Architecture Decision 2, "Intelligence contracts".
- An engine must be replaceable by a differently-implemented engine producing conformant objects, with no change to any other engine.

**Forbidden anti-patterns.**
- One engine reaching into another's working state.
- Objects carrying engine-specific fields that only a particular downstream engine understands.
- Implicit ordering dependencies not expressed through object availability.

**Verification.** Each engine's specification can be written, and its outputs validated, without reference to any other engine's internals.

> **CONTRADICTION-02 (partial):** Principle 4 states engines are modular and communicate only via objects, and the Orchestration Engine exists to sequence them. However the pipeline (v1 §3) contains an Execution stage with no corresponding engine, meaning at least one stage transition has no defined owner. See Section 3 and CONTRADICTION-02 in full.

### 2.5 Principle 5 — Continuous Learning

**Statement.** The platform improves over time by incorporating the outcomes of its own prior conclusions.

**Rationale.** A static analysis system degrades as markets change. The closed pipeline loop (Feedback → Evidence) is the structural expression of this principle.

**Binding implications.**
- Outcomes must be captured, not just predictions. The Execution Record object exists for this purpose.
- Learning requires the original prediction to be retrievable and comparable against outcome — this requires immutable prediction records (see MISSING-08).
- Learning changes future behaviour, which means platform behaviour is time-dependent. Two identical inputs at different times may legitimately produce different outputs.
- Because learning changes behaviour, changes must themselves be traceable and reversible.

**Forbidden anti-patterns.**
- Feedback that only produces reports rather than changing platform behaviour.
- Learning that overwrites prior configuration without record, making regression undiagnosable.
- Treating feedback as a separate offline analytics activity outside the pipeline.

**Verification.** For a given learning update, it is possible to state what changed, on the basis of which Execution Records, and to revert it.

> **MISSING-02 (restated, blocking):** the target of learning is undefined. See §1.2.5.

> **MISSING-10:** v1 does not define the learning cadence or trigger — whether learning is continuous per outcome, batched, periodic, or manually initiated. This is required by both the Feedback Engine and the Orchestration Engine.

> **OPEN QUESTION-05:** v1 does not state whether learning updates require approval before taking effect. Given that learning modifies platform behaviour globally, unsupervised self-modification is a significant risk posture decision that v1 does not address.

### 2.6 Principle Interaction and Precedence

Principles conflict in practice. v1 provides no precedence ordering.

Known tensions:
- **P1 (Evidence before conclusions) vs P5 (Continuous learning).** Learned adjustments — e.g. a tuned scoring weight — are conclusions not directly traceable to a single Evidence object. Whether learned parameters must themselves be evidence-linked is undefined.
- **P3 (Traceable lineage) vs P4 (Modular engines).** Complete lineage requires recording engine-internal decisions; strict modularity discourages exposing internals. The boundary of "sufficient" lineage detail is undefined.
- **P2 (Explainable decisions) vs storage cost at scale.** Retaining explanations for rejected candidates across a continuously running discovery process has unbounded growth characteristics.

> **OPEN QUESTION-06:** v1 provides no precedence rule for resolving principle conflicts. Enterprise architecture requires one, since these tensions will be encountered in every engine specification.

---

## 3. Pipeline — Expanded

### 3.1 v1 Statement (Preserved Verbatim)

> Evidence -> Facts -> Problems -> Patterns -> Opportunities -> Solutions -> Validation -> Execution -> Feedback -> Evidence

### 3.2 Structural Reading

The pipeline is a **closed loop of ten stage positions across nine distinct stages** (Evidence appears at both ends and is the same stage). It is the platform's spine: it defines the order in which knowledge is refined and the direction of dependency.

Key structural properties, derived from the notation as written:

1. **It is a cycle, not a chain.** The final arrow returns to Evidence. The platform has no terminal state.
2. **It is monotonic in abstraction.** Each stage produces a more synthesised, more decision-relevant artefact than the previous.
3. **It is narrowing then widening.** Evidence and Facts are high-volume; Problems, Patterns and Opportunities progressively consolidate; Solutions and Validation expand again per opportunity.
4. **Every stage maps to an Intelligence Object except Feedback.** See CONTRADICTION-03.
5. **Every stage maps to an Engine except Execution.** See CONTRADICTION-02.

### 3.3 Stage Definitions

Each stage is defined below by: its purpose, the transformation it performs, its owning engine, its entry and exit conditions, its invariants, and its characteristic failure modes.

---

#### Stage 1 — Evidence

**Purpose.** Establish the platform's contact with reality. Evidence is the only stage where information enters from outside the platform.

**Transformation.** External source material → Evidence objects.

**Owning engine.** Research Engine.

**Entry condition.** A research need exists.
> **MISSING-01 (applies here):** what constitutes a research need, and what raises it, is undefined.

**Exit condition.** Source material is captured, attributed, and persisted as Evidence objects in the Knowledge Store.

**Invariants.**
- Evidence is never derived from platform conclusions. It is the loop's grounding point.
- Evidence must retain enough of the original to permit re-extraction later.
- Evidence carries provenance: where it came from, when it was captured.

**Characteristic failure modes.**
- *Source unavailability* — target sources unreachable or access-restricted.
- *Source drift* — content changes or disappears after capture, breaking reproducibility.
- *Capture fidelity loss* — content captured in a form that loses meaning (structure stripped, context removed).
- *Volume overwhelm* — acquisition rate exceeds downstream processing capacity.
- *Duplication* — the same source captured repeatedly, inflating apparent evidential weight. This is the most dangerous failure mode at this stage, because it silently corrupts every downstream frequency-based judgement.

> **CONTRADICTION-04:** The pipeline terminates with `Feedback -> Evidence`, meaning feedback re-enters the loop as Evidence. But Evidence is defined by its property of originating outside the platform (grounding), while Feedback originates inside it. Either (a) internally-generated Evidence is a legitimate subtype, in which case Principle 1's grounding guarantee weakens and circular self-reinforcement becomes structurally possible, or (b) feedback enters the loop by causing new external research rather than by becoming Evidence directly. v1's notation states (a); the evidence-first philosophy implies (b). Must be reconciled before P8, and it constrains the Feedback Engine's output definition.

---

#### Stage 2 — Facts

**Purpose.** Convert unstructured evidence into discrete, individually addressable, individually verifiable claims.

**Transformation.** Evidence objects → Fact objects. Typically one-to-many.

**Owning engine.** Fact Extraction Engine.

**Entry condition.** Evidence objects exist that have not been processed for extraction.

**Exit condition.** Discrete Facts are persisted, each linked to the Evidence span it derives from.

**Invariants.**
- A Fact must be traceable to a specific location within its Evidence, not merely to the Evidence as a whole — otherwise verification requires re-reading the entire source.
- A Fact asserts something checkable. Opinions, if extracted, must be marked as attributed statements rather than as assertions of truth.
- Extraction does not interpret. Meaning-making belongs to the Problem stage.

**Characteristic failure modes.**
- *Hallucinated facts* — claims not present in the evidence. The single most severe integrity failure in the platform, as it corrupts the grounding layer while passing all structural lineage checks.
- *Over-extraction* — trivial or non-informative claims flooding the store.
- *Under-extraction* — significant claims missed, silently reducing coverage with no error signal.
- *Context stripping* — a claim extracted without qualifying conditions, changing its meaning.
- *Duplicate facts* from distinct evidence not recognised as the same claim, inflating frequency signals.

> **MISSING-11:** v1 does not define fact deduplication or fact identity. Whether two extractions expressing the same claim are one Fact with two Evidence links or two Facts is undefined. This determines whether frequency across sources is measurable, which every downstream pattern judgement depends on.

---

#### Stage 3 — Problems

**Purpose.** Identify where facts indicate unmet needs, friction, pain, cost, or failure. This is the first interpretive stage.

**Transformation.** Fact objects → Problem objects. Many-to-one and many-to-many.

**Owning engine.** Problem Intelligence Engine.

**Entry condition.** A body of Facts sufficient to support problem inference exists.
> **MISSING-06 (applies here):** sufficiency threshold undefined.

**Exit condition.** Problems are persisted, each linked to its supporting Facts, each with an explanation of why the facts indicate a problem.

**Invariants.**
- A Problem is a statement about a deficiency in the world, not about a product or a fix.
- A Problem must be supported by Facts, not by a single Fact restated.
- Problem statements must be independent of any solution — solution-shaped problems bias the entire downstream pipeline toward pre-conceived answers.

**Characteristic failure modes.**
- *Solution smuggling* — framing the problem as the absence of a specific solution, which pre-determines the Opportunity and Solution stages.
- *Severity misjudgement* — treating a minor annoyance as a significant problem, or vice versa.
- *Over-generalisation* — abstracting a specific, real problem into a vague category that is no longer actionable.
- *Population ambiguity* — failing to identify whose problem it is, making later opportunity sizing impossible.

> **MISSING-12:** v1 does not define whether Problems carry severity, frequency, or affected-population attributes. Pattern recognition and opportunity scoring both require some measure of problem weight; without defined attributes, downstream engines have nothing to aggregate.

---

#### Stage 4 — Patterns

**Purpose.** Detect structure across problems — recurrence, correlation, clustering, and cross-domain similarity — that is not visible in any single problem.

**Transformation.** Problem objects → Pattern objects. Many-to-one, aggregative.

**Owning engine.** Pattern Intelligence Engine.

**Entry condition.** A population of Problems large enough to support cross-comparison.

**Exit condition.** Patterns are persisted, each linked to all constituent Problems, each with an account of what makes the grouping meaningful rather than coincidental.

**Invariants.**
- A Pattern must be supported by multiple Problems, by definition. A single-problem pattern is a category error.
- Patterns must distinguish genuine recurrence from artefacts of the evidence collection process — a pattern arising because one source was over-sampled is a sampling artefact, not market structure.
- Patterns must retain their constituents. A pattern that cannot be decomposed back into its problems is not explainable.

**Characteristic failure modes.**
- *Sampling artefact* — pattern reflects the platform's research bias rather than the market. The defining risk of this stage, and it is invisible without evidence-source diversity accounting.
- *Spurious correlation* — grouping by superficial similarity with no causal or structural relationship.
- *Over-clustering* — collapsing distinct problems into an unusable generality.
- *Under-clustering* — failing to recognise the same underlying problem across different vocabularies or domains.
- *Temporal blindness* — treating a historical pattern as current when the underlying conditions have changed.

> **MISSING-13:** v1 does not define whether Patterns have temporal validity — whether a Pattern can expire, weaken, or require re-confirmation as new Problems arrive. Given Principle 5 and a continuously running loop, pattern staleness is inevitable and unaddressed.

> **OPEN QUESTION-07:** It is undefined whether the Pattern Intelligence Engine may operate over Facts directly in addition to Problems. The pipeline as written forbids it (Facts → Problems → Patterns), but some patterns are properties of facts rather than of problems. The strict reading is assumed throughout this document; confirmation required.

---

#### Stage 5 — Opportunities

**Purpose.** Convert recognised structure into candidate areas where value can be created and captured.

**Transformation.** Pattern objects → Opportunity objects.

**Owning engine.** Opportunity Intelligence Engine.

**Entry condition.** Patterns exist that have not been assessed for opportunity.

**Exit condition.** Opportunities are persisted, linked to originating Patterns, with assessment and — per the vision — scores.

**Invariants.**
- An Opportunity states what value could be created and for whom, not how.
- Opportunity assessment must be comparable across opportunities, otherwise prioritisation is impossible.
- An Opportunity inherits the evidential strength of its Pattern; it cannot be more certain than its support.

**Characteristic failure modes.**
- *Score incomparability* — scores produced under differing implicit criteria, making the ranking meaningless.
- *Solution contamination* — the opportunity is defined in terms of a specific solution, foreclosing the Solution stage.
- *Confidence inflation* — the opportunity presented with greater certainty than its evidence supports, the most consequential failure in the platform because this is the stage whose output drives resource commitment.
- *Sizing without basis* — quantified market claims not traceable to Facts.

> **CONTRADICTION-01 (applies here):** scoring is required by the vision but unassigned. Most plausibly resolved as an internal responsibility of this engine, but v1 does not say so.

> **MISSING-14:** No scoring dimensions, scale, or methodology are defined anywhere in v1. Even under the reading that scoring belongs to this engine, the engine cannot be specified without them.

---

#### Stage 6 — Solutions

**Purpose.** Formulate concrete approaches that address an opportunity.

**Transformation.** Opportunity objects → Solution objects. One-to-many; multiple candidate solutions per opportunity are expected.

**Owning engine.** Solution Intelligence Engine.

**Entry condition.** An Opportunity has been accepted for solution development.
> **OPEN QUESTION-08:** what causes an Opportunity to be accepted for solution development — a score threshold, human selection, or unconditional processing of all opportunities — is undefined. This is a major cost driver and a control-flow gap for the Orchestration Engine.

**Exit condition.** Solutions are persisted, linked to the Opportunity, each with its rationale and its assumptions.

**Invariants.**
- A Solution must address the problems underlying its opportunity, and this must be demonstrable through lineage.
- Solutions must surface their assumptions explicitly, because assumptions are what the Validation stage tests.
- Multiple competing solutions per opportunity are legitimate and should not be prematurely collapsed.

**Characteristic failure modes.**
- *Assumption concealment* — unstated assumptions that validation therefore cannot test.
- *Generic solutioning* — proposals that would apply to any opportunity, indicating the engine is not using its inputs.
- *Feasibility blindness* — solutions with no consideration of constraint.
- *Premature convergence* — a single solution generated, eliminating comparative validation.

---

#### Stage 7 — Validation

**Purpose.** Test whether the claims and assumptions carried by the preceding stages hold.

**Transformation.** Solution objects (and their lineage) → Validation objects.

**Owning engine.** Validation Engine.

**Entry condition.** A Solution exists with testable assumptions.

**Exit condition.** Validation objects are persisted, recording what was tested, how, and with what result — including negative results.

**Invariants.**
- Validation must be capable of returning a negative result, and negative results must be preserved with the same status as positive ones. A validation stage that only confirms is not validation.
- What was tested must be stated precisely enough that the test could be repeated.
- Validation attaches to specific claims, not to an object as a whole.

**Characteristic failure modes.**
- *Confirmation bias* — designing tests that cannot fail.
- *Negative result suppression* — discarding failed validations, which destroys the learning signal Principle 5 depends on.
- *Scope mismatch* — validating a narrow proxy and treating it as validation of the whole solution.
- *Validation without consequence* — results recorded but not affecting the object's status downstream.

> **CONTRADICTION-05:** Validation is the object of the Experiment Registry (v1 §5) and also an Intelligence Object (v1 §6). The relationship between a Validation object and an experiment record in the Experiment Registry is undefined: they may be the same thing stored twice, or the registry may hold experiment design while the object holds the result. This ambiguity blocks specification of both the Validation Engine and the Experiment Registry.

> **OPEN QUESTION-09:** v1 does not state what Validation validates. The pipeline positions it after Solutions, implying solution validation. But opportunities, patterns, problems and facts are all claims that could be validated, and the vision says the platform "validates" without specifying the target. Whether Validation operates only on Solutions or on any object is a fundamental scoping decision.

---

#### Stage 8 — Execution

**Purpose.** Capture what happened when a validated solution was acted upon in the real world.

**Transformation.** Validation objects → Execution Record objects.

**Owning engine.** **NONE — see CONTRADICTION-02.**

> **CONTRADICTION-02 (full statement):** The pipeline (v1 §3) contains an Execution stage, and the object model (v1 §6) contains an Execution Record object, but v1 §4 defines no Execution Engine. Every other stage has an owning engine. Two reconciliations are possible: (a) Execution occurs outside the platform — the platform records outcomes of actions taken by others, in which case some engine must own the intake of external outcomes and v1 does not say which (the Feedback Engine is the most plausible candidate, but this is not stated); or (b) an Execution Engine was omitted, which would mean adding an engine and is out of scope for this document. This is the single most significant structural gap in v1. It blocks the definition of the Execution Record object's producer, blocks the Orchestration Engine's control model for this stage, and blocks the roadmap — note that the roadmap (v1 §9) also has no execution phase, which is consistent with reading (a).

**Entry condition.** A validated solution is acted upon.

**Exit condition.** An Execution Record exists linking real-world outcome to the platform's prediction.

**Invariants.**
- The Execution Record must be linkable to the specific Opportunity and Solution it tests, otherwise the learning loop has no comparison basis.
- Outcomes must be recorded regardless of whether they confirm the platform's assessment.

**Characteristic failure modes.**
- *Outcome attribution error* — crediting or blaming the platform's recommendation for results driven by external factors.
- *Reporting gap* — executions occurring without records, biasing learning toward whichever outcomes happen to get reported. Under reading (a) of CONTRADICTION-02, this is the dominant risk, since the platform does not control the execution.
- *Latency* — outcomes materialising long after prediction, so the learning signal arrives against a platform state that has already changed.
- *Survivorship bias* — only successful executions reported.

---

#### Stage 9 — Feedback

**Purpose.** Convert execution outcomes into changes in platform behaviour, closing the loop.

**Transformation.** Execution Record objects → (learning updates) → re-entry to Evidence.

**Owning engine.** Feedback Engine.

**Entry condition.** Execution Records exist that have not been processed.

**Exit condition.** Platform behaviour has been updated and/or new Evidence has entered the loop.

**Invariants.**
- Feedback must change something. Feedback that only reports violates Principle 5.
- Changes must be attributable to the Execution Records that motivated them.
- Changes must be reversible.

**Characteristic failure modes.**
- *Overfitting to recent outcomes* — a small number of results causing disproportionate behavioural change.
- *Feedback loop instability* — learning amplifying its own bias over successive cycles. Structurally enabled by CONTRADICTION-04, since platform-generated content re-entering as Evidence can be re-learned from as if it were external observation.
- *Untraceable drift* — accumulated small changes with no record of aggregate effect.
- *Signal starvation* — too few execution records to learn from, leaving the loop nominally closed but functionally open.

> **CONTRADICTION-03:** Feedback is a pipeline stage (§3) and an engine (§4) but is not an Intelligence Object (§6). Every other stage produces a persisted object. Either feedback produces no persisted artefact — which contradicts Principle 3, since learning changes would then be untraceable — or an object is missing from the model. Adding one is out of scope for this document; the gap is recorded.

---

### 3.4 Cross-Stage Properties

**3.4.1 Volume profile.** Evidence and Facts are the high-volume stages; Patterns and Opportunities the most consolidated. Any resource planning must account for the fact that cost is concentrated upstream while value is concentrated downstream.

**3.4.2 Confidence propagation.** Certainty degrades along the pipeline: each interpretive step adds inferential risk. An Opportunity is necessarily less certain than the Facts beneath it.

> **MISSING-15:** v1 defines no confidence or certainty model, and no rule for how confidence propagates across stages. Since the vision requires scoring and comparison, and Principle 1 distinguishes supported from unsupported claims, the absence of a confidence representation is a foundational gap affecting all nine engines.

**3.4.3 Stage skipping.** The pipeline as written is strictly sequential.

> **OPEN QUESTION-10:** Whether stages may be skipped — for example, a known opportunity introduced directly without traversing Evidence → Facts → Problems → Patterns — is undefined. The strict reading forbids it and is assumed here. Permitting it would breach Principle 1 unless the injected object carried its own evidence.

**3.4.4 Backflow.** The pipeline shows only forward arrows plus the closing loop.

> **OPEN QUESTION-11:** Whether a downstream stage can trigger upstream work — e.g. Validation determining that more evidence is required — is undefined. The pipeline notation does not show it; practical operation almost certainly requires it. This is a control-model question for the Orchestration Engine.

**3.4.5 Loop iteration.** v1 does not indicate whether the loop runs continuously, whether multiple iterations run concurrently over different subject matter, or how one traversal is bounded. See MISSING-01.

---

## 4. Engines — Expanded

### 4.1 v1 Statement (Preserved Verbatim)

> Research / Fact Extraction / Problem Intelligence / Pattern Intelligence / Opportunity Intelligence / Solution Intelligence / Validation / Feedback / Orchestration

Nine engines. Eight are pipeline-aligned; Orchestration is cross-cutting.

### 4.2 Engine Specification Format

Each engine below is specified under a fixed schema. Every field is mandatory; where v1 provides no basis for a field, the gap is marked rather than filled.

- **Responsibility** — the single thing the engine exists to do
- **Boundaries** — what the engine explicitly does not do, and who does it instead
- **Inputs** — objects consumed
- **Outputs** — objects produced
- **Dependencies** — what must exist for the engine to function
- **Failure modes** — how the engine fails, and the consequence of each failure
- **Gaps** — MISSING / OPEN QUESTION / CONTRADICTION items blocking specification

### 4.3 Engine Boundary Doctrine

Derived from Principle 4 and Architecture Decision 4 (Separation of concerns), the following boundary rules are binding on all nine engines:

1. An engine owns exactly one transformation in the pipeline.
2. An engine reads objects of its input type and writes objects of its output type. It writes no other type.
3. An engine never invokes another engine. Sequencing belongs solely to Orchestration.
4. An engine holds no persistent state of its own. All state lives in the shared components.
5. An engine's replacement must be invisible to all other engines.
6. An engine is responsible for the explanation of its own decisions (Principle 2) and for recording its own lineage contribution (Principle 3).

---

### 4.4 Research Engine

**Responsibility.** Acquire source material from outside the platform and convert it into Evidence objects with complete provenance.

**Boundaries.**
- Does NOT interpret, summarise, or extract claims — that is Fact Extraction.
- Does NOT judge whether content is useful for a given problem — that is downstream.
- Does NOT decide what to research. → **MISSING-01**: no engine is assigned research direction. Orchestration is the plausible owner but v1 does not say so.
- Is the ONLY engine permitted to introduce information from outside the platform. This is the grounding boundary that makes Principle 1 enforceable.

**Inputs.** External sources. No Intelligence Object inputs, except under CONTRADICTION-04's reading (a), where Feedback output re-enters here.

**Outputs.** Evidence objects.

**Dependencies.** Knowledge Store (persistence); access to external sources; a research directive of undefined origin (MISSING-01).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Source inaccessible | Coverage gap, silent unless tracked |
| Source misattributed | Lineage corrupted at the root; all downstream trust invalid |
| Capture truncation | Facts extracted from partial content, meaning altered |
| Over-collection from one source | Sampling artefact propagates to Pattern stage undetected |
| Duplicate capture | Frequency signals inflated throughout the pipeline |
| Stale capture | Evidence describes conditions no longer current |
| Access/permission violation | Legal and compliance exposure |

**Gaps.**
> **MISSING-16:** No source taxonomy, no eligibility criteria, no source trust or credibility model. Since all platform trust derives from evidence quality, and no engine assesses source quality, weak and strong sources are structurally indistinguishable throughout the platform. This is the highest-severity omission in the engine set.

> **MISSING-17:** No coverage or completeness concept. The platform cannot determine when it has researched enough, nor detect what it has not seen.

> **MISSING-18:** No legal, licensing, robots, rate-limit, or terms-of-use policy for acquisition, despite acquisition being the platform's only external interface.

> **OPEN QUESTION-12:** Whether Evidence is stored in full, as reference, or both. This determines whether the platform is resilient to source disappearance and whether re-extraction (OPEN QUESTION-01) is possible.

---

### 4.5 Fact Extraction Engine

**Responsibility.** Decompose Evidence into discrete, individually addressable, checkable Fact objects, each anchored to its location in the source.

**Boundaries.**
- Does NOT interpret significance. A fact is not a problem.
- Does NOT judge truth. It records what the evidence asserts, with attribution.
- Does NOT aggregate across Evidence objects — cross-source synthesis is downstream.
- Does NOT discard Evidence, only reads it.

**Inputs.** Evidence objects.

**Outputs.** Fact objects, each linked to its source Evidence and to the specific location within it.

**Dependencies.** Research Engine output; Knowledge Store; extraction criteria (undefined — MISSING-19).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Hallucination | Ungrounded claim enters the platform while passing all structural checks — catastrophic, as it defeats Principle 1 invisibly |
| Omission | Silent coverage loss with no error signal |
| Context stripping | Claim's meaning altered by loss of qualifiers |
| Conflation | Two distinct claims merged into one |
| Fragmentation | One claim split into pieces that individually assert nothing |
| Opinion-as-assertion | Subjective statement recorded as fact |
| Anchor loss | Fact cannot be traced to a source location, breaking verifiability |

**Gaps.**
> **MISSING-19:** No definition of what qualifies as a fact, no extraction granularity rule. Without this the engine's output is arbitrary and non-comparable across runs.

> **MISSING-11 (applies):** fact identity and deduplication undefined.

> **MISSING-20:** No verification mechanism for extraction fidelity. Hallucination is the platform's most severe integrity risk and no engine is assigned to detect it. Note that the Validation Engine sits at stage 7, far downstream, and OPEN QUESTION-09 leaves unresolved whether it may validate Facts.

---

### 4.6 Problem Intelligence Engine

**Responsibility.** Infer, from bodies of Facts, statements of unmet need, friction, cost, or failure — and articulate them independently of any solution.

**Boundaries.**
- Does NOT propose solutions.
- Does NOT identify recurrence across problems — that is Pattern Intelligence.
- Does NOT assess commercial value — that is Opportunity Intelligence.
- Does NOT acquire additional evidence when facts are insufficient (subject to OPEN QUESTION-11).

**Inputs.** Fact objects.

**Outputs.** Problem objects, linked to supporting Facts, each with an explanation of the inference.

**Dependencies.** Fact Extraction output; Knowledge Store; Knowledge Graph (to relate problems to facts); sufficiency thresholds (MISSING-06).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Solution smuggling | Entire downstream pipeline biased toward a pre-conceived answer |
| Single-fact inference | Problem asserted on insufficient support, violating the spirit of Principle 1 |
| Over-generalisation | Problem too abstract to act on |
| Under-generalisation | Every fact becomes its own problem; Pattern stage overwhelmed |
| Population omission | Whose problem it is left unstated, making sizing impossible |
| Severity misassignment | Prioritisation corrupted from this point onward |
| Duplicate problems | Same problem stated repeatedly, inflating pattern strength |

**Gaps.**
> **MISSING-12 (applies):** problem attributes (severity, frequency, population) undefined.

> **MISSING-21:** No problem taxonomy or classification scheme. Pattern recognition across problems requires a comparable representation; free-form problem statements are not reliably comparable.

> **MISSING-22:** No problem identity/deduplication rule.

---

### 4.7 Pattern Intelligence Engine

**Responsibility.** Detect meaningful structure across the Problem population — recurrence, clustering, correlation, cross-domain analogy — and distinguish it from artefacts of the collection process.

**Boundaries.**
- Does NOT create new problems.
- Does NOT assess opportunity value.
- Does NOT read Facts or Evidence directly (per strict pipeline reading — OPEN QUESTION-07).
- Does NOT act on patterns.

**Inputs.** Problem objects, in populations.

**Outputs.** Pattern objects, linked to all constituent Problems.

**Dependencies.** A Problem population of sufficient size; Knowledge Graph (relationship traversal is intrinsic to this engine's work — it is the most graph-dependent engine); evidence-source diversity information, needed to distinguish real patterns from sampling artefacts — see MISSING-23.

**Failure modes.**

| Mode | Consequence |
|---|---|
| Sampling artefact | Research bias mistaken for market structure; defining risk of this engine |
| Spurious correlation | Unrelated problems grouped on surface similarity |
| Over-clustering | Distinct problems collapsed into unusable generality |
| Under-clustering | Same problem across vocabularies not recognised |
| Temporal conflation | Historical and current problems merged, pattern no longer true |
| Threshold arbitrariness | Pattern existence determined by an undefined and unjustifiable cutoff |
| Pattern staleness | Pattern remains asserted after conditions change |

**Gaps.**
> **MISSING-23:** No source-diversity or independence accounting. Without knowing whether ten problems came from ten independent sources or one source ten times, the engine cannot distinguish a pattern from an echo. This is a direct downstream consequence of MISSING-16.

> **MISSING-24:** No pattern strength or significance measure, and no minimum constituent count.

> **MISSING-13 (applies):** pattern temporal validity undefined.

> **MISSING-25:** No pattern type taxonomy — v1 does not indicate what kinds of patterns are sought (recurrence, causal, temporal, structural, cross-domain).

---

### 4.8 Opportunity Intelligence Engine

**Responsibility.** Convert Patterns into assessed, comparable Opportunity objects representing where value could be created and captured.

**Boundaries.**
- Does NOT design solutions.
- Does NOT validate.
- Does NOT decide whether to pursue — subject to OPEN QUESTION-08, the acceptance decision has no defined owner.
- Does NOT create patterns.

**Inputs.** Pattern objects.

**Outputs.** Opportunity objects, linked to originating Patterns, carrying assessment and — under the most plausible reading of CONTRADICTION-01 — scores.

**Dependencies.** Pattern Intelligence output; Knowledge Store; Knowledge Graph; scoring methodology (MISSING-14); confidence model (MISSING-15).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Confidence inflation | Weakly-supported opportunity presented as strong; drives misallocated resources — highest business-impact failure in the platform |
| Score incomparability | Ranking meaningless; the platform's primary output loses its function |
| Solution contamination | Opportunity framed as a specific product, foreclosing the Solution stage |
| Unfounded sizing | Quantitative claims not traceable to Facts, breaching Principle 1 |
| Pattern over-extrapolation | Narrow pattern projected onto a broad market |
| Feasibility blindness | Opportunity assessed without constraint |
| Staleness | Opportunity remains ranked after its pattern has decayed |

**Gaps.**
> **CONTRADICTION-01 (applies):** scoring is a vision-level capability with no assigned owner.

> **MISSING-14 (applies):** no scoring dimensions, scale, weighting, or aggregation method.

> **MISSING-26:** No definition of what an opportunity is in this platform's terms — market gap, unserved segment, product concept, business model, or all of these. The output type of the platform's central engine is undefined.

> **MISSING-27:** No prioritisation or ranking policy beyond raw score.

---

### 4.9 Solution Intelligence Engine

**Responsibility.** Generate candidate approaches that address an Opportunity, each with explicit rationale and explicit assumptions.

**Boundaries.**
- Does NOT validate its own solutions — that separation is essential to avoid confirmation bias.
- Does NOT execute.
- Does NOT redefine the opportunity.
- Does NOT select the winning solution. → **MISSING-28**: no engine owns solution selection.

**Inputs.** Opportunity objects, with traversable lineage to the underlying Problems.

**Outputs.** Solution objects, linked to the Opportunity, each stating assumptions in a form the Validation Engine can test.

**Dependencies.** Opportunity Intelligence output; Knowledge Graph (to reach the underlying problems); acceptance trigger (OPEN QUESTION-08).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Assumption concealment | Validation cannot test what was never stated; the Validation stage is silently weakened |
| Generic solutioning | Output independent of input, indicating the engine adds no value |
| Premature convergence | One candidate produced, eliminating comparison |
| Problem drift | Solution addresses something other than the linked problems |
| Feasibility blindness | Unimplementable proposals consume validation capacity |
| Untestable assumptions | Assumptions stated too vaguely to validate |

**Gaps.**
> **MISSING-29:** No definition of solution granularity — concept, specification, or business case.

> **MISSING-28:** No owner for solution selection among candidates.

> **MISSING-30:** No required structure for stating assumptions, despite assumptions being the interface to the Validation Engine. This is a contract gap between two adjacent engines and directly threatens Architecture Decision 2.

---

### 4.10 Validation Engine

**Responsibility.** Test claims and assumptions, and record results — including negative results — as Validation objects.

**Boundaries.**
- Does NOT generate what it validates (independence requirement).
- Does NOT execute in market.
- Does NOT decide what happens after a validation result. → **MISSING-31**: no engine owns the promote/reject decision following validation.
- Does NOT modify the objects it validates.

**Inputs.** Solution objects and their assumptions; per OPEN QUESTION-09, possibly other object types.

**Outputs.** Validation objects.

**Dependencies.** Solution Intelligence output; Experiment Registry (relationship undefined — CONTRADICTION-05); validation methodology (MISSING-32).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Confirmation bias | Tests constructed to succeed; validation becomes ceremonial |
| Negative result suppression | Destroys the learning signal Principle 5 requires |
| Proxy mismatch | Narrow test treated as validating the whole |
| Inconclusive handling | No defined state for "test ran, result unclear" |
| Result without consequence | Validation recorded but not affecting downstream status |
| Unrepeatable design | Test not described precisely enough to repeat |

**Gaps.**
> **CONTRADICTION-05 (applies):** Validation object vs Experiment Registry relationship undefined; blocks both.

> **OPEN QUESTION-09 (applies):** validation target scope undefined.

> **MISSING-32:** No validation methodology, evidence standards, or pass/fail criteria.

> **MISSING-33:** No definition of validation outcome states (pass / fail / inconclusive / partial).

> **MISSING-31:** No owner for the post-validation decision.

---

### 4.11 Feedback Engine

**Responsibility.** Convert Execution Records into changes in platform behaviour, and close the pipeline loop.

**Boundaries.**
- Does NOT execute.
- Does NOT create opportunities or solutions.
- Does NOT validate.
- Under CONTRADICTION-02 reading (a), it is the most plausible owner of external outcome intake — but v1 does not assign this.

**Inputs.** Execution Record objects.

**Outputs.** Learning updates to an undefined target (MISSING-02); and, per the pipeline's closing arrow, Evidence — subject to CONTRADICTION-04.

**Dependencies.** Execution Records (whose producer is undefined — CONTRADICTION-02); the original predictions, retrievable and unmodified (requires MISSING-08 resolved toward immutability); a defined learning target (MISSING-02); a success measure (MISSING-04).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Overfitting | Small sample drives disproportionate behavioural change |
| Loop instability | Learning amplifies its own bias across cycles; structurally enabled by CONTRADICTION-04 |
| Untraceable drift | Cumulative change with no aggregate record; breaches Principle 3 |
| Signal starvation | Loop nominally closed, functionally open |
| Attribution error | Outcome credited to the wrong prediction |
| Irreversible update | Regression cannot be undone |
| Latency mismatch | Outcome arrives against an already-changed platform state |

**Gaps.**
> **MISSING-02 (applies, blocking):** learning target undefined — the engine has no defined output.

> **MISSING-10 (applies):** learning cadence undefined.

> **CONTRADICTION-04 (applies):** feedback-as-Evidence contradicts the grounding property of Evidence.

> **CONTRADICTION-03 (applies):** Feedback produces no Intelligence Object, so its work is untraceable, breaching Principle 3.

> **OPEN QUESTION-05 (applies):** whether learning updates require approval.

> **MISSING-34:** No mechanism for reverting a learning update.

---

### 4.12 Orchestration Engine

**Responsibility.** Sequence the pipeline, determine when each engine runs and over what, and enforce stage ordering. It is the only engine with knowledge of the pipeline as a whole and the only one permitted to invoke others (per Principle 4, which forbids engine-to-engine calls).

**Boundaries.**
- Does NOT perform any transformation.
- Does NOT create or modify Intelligence Objects. It moves work, not knowledge — this is its defining constraint.
- Does NOT make domain judgements.
- Does NOT own storage.

**Inputs.** Platform state — the existence and status of objects awaiting processing.

**Outputs.** Engine invocations and execution control. Produces no Intelligence Object.

**Dependencies.** All eight other engines; Knowledge Store (to determine state); a control model (MISSING-35); a triggering model (MISSING-01).

**Failure modes.**

| Mode | Consequence |
|---|---|
| Stage-order violation | An engine runs on inputs that are not ready; pipeline integrity lost |
| Deadlock | Circular waiting; loop halts |
| Starvation | Some objects never progress |
| Runaway iteration | The closed loop cycles without bound, consuming resources indefinitely |
| Partial-failure mishandling | One engine fails mid-batch, leaving inconsistent state |
| Duplicate invocation | Same input processed twice, creating duplicate objects |
| Backpressure failure | Upstream volume overwhelms downstream capacity |

**Gaps.**
> **MISSING-35:** No control model — event-driven, batch, scheduled, or continuous is undefined. This is the single largest specification gap for this engine and blocks P1.

> **MISSING-01 (applies):** no pipeline trigger defined.

> **MISSING-36:** No failure-handling policy — retry, skip, halt, compensate — for any engine failure.

> **MISSING-37:** No loop termination or iteration-bounding condition. A closed loop with no stopping rule is unbounded by construction.

> **OPEN QUESTION-11 (applies):** whether backflow (downstream triggering upstream work) is permitted.

> **OPEN QUESTION-13:** Whether multiple pipeline traversals may run concurrently over different subject matter, and if so how they share the Knowledge Store and Knowledge Graph without interference.

---

### 4.13 Engine Dependency Matrix

Read as: row engine depends on column engine's output.

| Engine ↓ depends on → | Res | Fact | Prob | Patt | Opp | Sol | Val | Feed | Orch |
|---|---|---|---|---|---|---|---|---|---|
| **Research** | — | | | | | | | ●¹ | ● |
| **Fact Extraction** | ● | — | | | | | | | ● |
| **Problem Intelligence** | | ● | — | | | | | | ● |
| **Pattern Intelligence** | | | ● | — | | | | | ● |
| **Opportunity Intelligence** | | | | ● | — | | | | ● |
| **Solution Intelligence** | | | | | ● | — | | | ● |
| **Validation** | | | | | | ● | — | | ● |
| **Feedback** | | | | | | | ●² | — | ● |
| **Orchestration** | ● | ● | ● | ● | ● | ● | ● | ● | — |

¹ Only under CONTRADICTION-04 reading (a).
² Indirect: Feedback consumes Execution Records, which follow Validation but have no defined producer (CONTRADICTION-02).

**Observations.**
- The chain is strictly linear except for Orchestration (universal) and the closing loop.
- The only cycle is the intended pipeline loop.
- The Execution gap breaks the chain between Validation and Feedback — the platform's learning loop is not structurally complete as specified.

---

## 5. Knowledge Architecture (Shared Components) — Expanded

### 5.1 v1 Statement (Preserved Verbatim)

> Knowledge Store / Knowledge Graph / Experiment Registry

These are not engines. They hold state; engines hold none (Boundary Doctrine rule 4).

---

### 5.2 Knowledge Store

**Responsibility.** Authoritative persistence of all Intelligence Objects. The system of record.

**Holds.** All eight Intelligence Objects, their content, attributes, provenance, explanations, and lineage references.

**Boundaries.**
- Does NOT interpret or transform.
- Does NOT decide what is stored — engines do.
- Does NOT own relationship traversal — that is the Knowledge Graph's role (see CONTRADICTION-06).

**Required properties, derived from the principles.**
- *From Principle 1:* must be able to reject objects lacking evidence linkage, since evidence-first must be enforced at write time rather than checked at read time.
- *From Principle 2:* must persist explanations as first-class content, not as ancillary logs.
- *From Principle 3:* must retain history sufficient to reconstruct any derivation.
- *From Principle 5:* must preserve predictions unmodified so outcomes can be compared against them.

**Failure modes.** Loss of provenance; silent overwrite destroying lineage; partial write leaving orphaned objects; unbounded growth from continuous loop operation; inconsistency with the Knowledge Graph.

**Gaps.**
> **MISSING-08 (applies, blocking):** mutability and versioning undefined — the foundational storage semantic.

> **CONTRADICTION-06:** The division of responsibility between Knowledge Store and Knowledge Graph is undefined. Both plausibly hold objects and relationships. Without a stated division, either they duplicate state (creating consistency risk) or the boundary is decided ad hoc per engine (breaching Architecture Decision 4, Separation of concerns). Must be resolved in P1, as every engine writes to one or both.

> **MISSING-38:** No retention policy. A continuously looping pipeline with preserved rejected candidates and full history grows without bound.

> **MISSING-39:** No consistency model between the two knowledge components.

---

### 5.3 Knowledge Graph

**Responsibility.** Represent and make traversable the relationships between Intelligence Objects — above all, lineage.

**Holds.** Relationships: derivation links, evidence support links, aggregation membership, contradiction links (if OPEN QUESTION-03 is resolved affirmatively), and prediction-to-outcome links.

**Boundaries.**
- Does NOT hold object content (assumed; see CONTRADICTION-06).
- Does NOT infer relationships not asserted by an engine — silent inference would create unattributed lineage, breaching Principle 3.
- Does NOT make judgements.

**Why it is architecturally necessary.** Principle 3 requires lineage reconstruction; Pattern Intelligence requires cross-problem traversal; retraction propagation (MISSING-09) requires reverse traversal from Evidence to all descendants. None of these are efficiently expressible without an explicit relationship structure. This component is what makes traceable lineage practical rather than aspirational.

**Failure modes.** Orphaned nodes; broken lineage chains; divergence from Knowledge Store; relationship type proliferation without governance; traversal cost growth as the loop accumulates history; cycles introduced by the pipeline loop making ancestor queries non-terminating.

**Gaps.**
> **CONTRADICTION-06 (applies):** boundary with Knowledge Store undefined.

> **MISSING-40:** No relationship taxonomy. v1 names no relationship types, yet the graph's entire value is in relationship semantics. Blocks P1.

> **MISSING-41:** No rule for handling the cycle introduced by `Feedback -> Evidence`. If feedback-derived Evidence links back to the objects that produced it, the lineage graph contains cycles and "trace to origin" has no terminating definition. Directly consequent on CONTRADICTION-04.

---

### 5.4 Experiment Registry

**Responsibility.** Record experiments — their design, execution, and results.

**Holds.** Experiment records. Precise content undefined (CONTRADICTION-05).

**Boundaries.**
- Does NOT run experiments; the Validation Engine does.
- Does NOT judge results.

**Failure modes.** Experiments recorded after the fact with post-hoc rationalisation; results not linked to the objects they concern; failed experiments omitted (destroying the negative-result record Principle 5 depends on); duplication with Validation objects producing two divergent accounts of the same test.

**Gaps.**
> **CONTRADICTION-05 (applies, blocking):** relationship to the Validation object undefined. This component and the Validation Engine cannot both be specified until resolved.

> **MISSING-42:** No experiment lifecycle definition (proposed → designed → running → complete → analysed).

> **OPEN QUESTION-14:** Whether the registry covers only Validation-stage experiments or also platform-level experiments such as Feedback Engine learning updates. The latter reading would make it the mechanism for making learning traceable and reversible (MISSING-34), which would be architecturally significant.

---

### 5.5 Shared Component Access Matrix

| Engine | Knowledge Store | Knowledge Graph | Experiment Registry |
|---|---|---|---|
| Research | Write Evidence | Write provenance links | — |
| Fact Extraction | Read Evidence / Write Fact | Write derivation links | — |
| Problem Intelligence | Read Fact / Write Problem | Read + write links | — |
| Pattern Intelligence | Read Problem / Write Pattern | Heavy read + write | — |
| Opportunity Intelligence | Read Pattern / Write Opportunity | Read + write links | — |
| Solution Intelligence | Read Opportunity / Write Solution | Read lineage + write links | — |
| Validation | Read Solution / Write Validation | Write links | Write |
| Feedback | Read Execution Record / Write ? | Read + write links | Read (possibly write — OQ-14) |
| Orchestration | Read state only | Read state only | — |

> **MISSING-43:** Feedback's write target in the Knowledge Store is undefined, being a direct consequence of CONTRADICTION-03 (no Feedback object) and MISSING-02 (no learning target).

> **MISSING-44:** No write-authority model. Nothing in v1 prevents an engine writing an object type it does not own, which would breach Boundary Doctrine rule 2 and Architecture Decision 4.

---

## 6. Intelligence Object Model — Expanded

### 6.1 v1 Statement (Preserved Verbatim)

> Evidence / Fact / Problem / Pattern / Opportunity / Solution / Validation / Execution Record

Eight objects. Per Architecture Decision 2, these objects **are** the contracts between engines. Their definitions are therefore the most load-bearing content in the platform.

### 6.2 Universal Object Requirements

Derived from the principles, binding on all eight object types. These are semantic requirements, not schemas.

| # | Requirement | Source |
|---|---|---|
| U1 | Identity — each object is uniquely and stably identifiable | P3 |
| U2 | Type — each object declares its type | P4 |
| U3 | Provenance — which engine produced it, when, under what configuration | P3 |
| U4 | Lineage — references to the objects it derives from | P1, P3 |
| U5 | Explanation — why this object exists in this form | P2 |
| U6 | Evidence reachability — a resolvable path to at least one Evidence object | P1 |
| U7 | Confidence — the strength of the claim | vision ("scores"), P1 |
| U8 | Temporal validity — when it was true, and whether it still is | P5 |
| U9 | Status — its lifecycle position | P3 |

> **MISSING-15 (applies to U7):** no confidence model defined anywhere in v1.

> **MISSING-45 (applies to U9):** no object lifecycle or status model defined. Objects need states (candidate, accepted, superseded, retracted, invalidated) for retraction (MISSING-09), rejection (OPEN QUESTION-04), and validation outcomes (MISSING-33) to be representable. Undefined for all eight types.

> **MISSING-46 (applies to U8):** no temporal model. In a continuously looping platform, every object ages, and nothing in v1 addresses this.

### 6.3 Object Definitions

For each: role, what it asserts, source, consumers, distinguishing characteristic, and gaps.

---

**6.3.1 Evidence**

- **Role.** The platform's grounding. Raw material from outside.
- **Asserts.** "This material existed at this source at this time."
- **Produced by.** Research Engine (only).
- **Consumed by.** Fact Extraction Engine.
- **Distinguishing characteristic.** The only object not derived from another object. The termination point of every lineage chain — which is what makes Principle 1 verifiable.
- **Must carry.** Source identity, capture time, content or reference (OPEN QUESTION-12), access context.
- **Gaps.** MISSING-16 (no source trust model); OPEN QUESTION-12 (content vs reference); CONTRADICTION-04 (whether internally-generated Evidence is legitimate, which if affirmed removes this object's defining property).

---

**6.3.2 Fact**

- **Role.** An atomic checkable claim.
- **Asserts.** "This specific claim is present in this evidence at this location."
- **Produced by.** Fact Extraction Engine.
- **Consumed by.** Problem Intelligence Engine.
- **Distinguishing characteristic.** The finest granularity in the platform, and the last point at which a claim can be checked directly against a source without inference.
- **Must carry.** The claim, anchor to Evidence location, attribution (whose assertion it is).
- **Gaps.** MISSING-19 (what qualifies as a fact); MISSING-11 (identity/deduplication); OPEN QUESTION-03 (contradictory facts); MISSING-20 (no fidelity verification).

---

**6.3.3 Problem**

- **Role.** A statement of unmet need or friction.
- **Asserts.** "This population experiences this deficiency, per these facts."
- **Produced by.** Problem Intelligence Engine.
- **Consumed by.** Pattern Intelligence Engine.
- **Distinguishing characteristic.** The first interpretive object — the point where the platform moves from recording to reasoning, and therefore the first point where it can be wrong in a way no source check will catch.
- **Must carry.** Problem statement, affected population, supporting Facts, inference explanation.
- **Gaps.** MISSING-12 (severity/frequency/population attributes); MISSING-21 (taxonomy); MISSING-22 (identity).

---

**6.3.4 Pattern**

- **Role.** Structure recognised across multiple Problems.
- **Asserts.** "These problems share this structure, and it is not an artefact of collection."
- **Produced by.** Pattern Intelligence Engine.
- **Consumed by.** Opportunity Intelligence Engine.
- **Distinguishing characteristic.** The only inherently plural object — it cannot exist with a single constituent.
- **Must carry.** Pattern description, constituent Problems, strength/significance, source-diversity basis.
- **Gaps.** MISSING-24 (strength measure, minimum constituents); MISSING-23 (source diversity accounting); MISSING-25 (pattern taxonomy); MISSING-13 (temporal validity).

---

**6.3.5 Opportunity**

- **Role.** A candidate area for value creation. The platform's primary output.
- **Asserts.** "Value could be created here, of this magnitude, with this confidence."
- **Produced by.** Opportunity Intelligence Engine.
- **Consumed by.** Solution Intelligence Engine; ultimately by external decision-makers (MISSING-05).
- **Distinguishing characteristic.** The object the entire upstream pipeline exists to produce, and the one carrying the greatest consequence if wrong.
- **Must carry.** Opportunity statement, originating Patterns, score(s), confidence, assessment explanation.
- **Gaps.** CONTRADICTION-01 (scoring unassigned); MISSING-14 (no scoring dimensions or scale); MISSING-26 (opportunity type undefined); MISSING-27 (no ranking policy).

---

**6.3.6 Solution**

- **Role.** A candidate approach addressing an Opportunity.
- **Asserts.** "This approach would address this opportunity, given these assumptions."
- **Produced by.** Solution Intelligence Engine.
- **Consumed by.** Validation Engine.
- **Distinguishing characteristic.** The only object whose primary downstream value lies in its stated assumptions rather than its content — the assumptions are the interface to Validation.
- **Must carry.** Solution description, addressed Opportunity, explicit testable assumptions, rationale.
- **Gaps.** MISSING-29 (granularity); MISSING-30 (assumption structure — an engine-to-engine contract gap); MISSING-28 (no selection owner).

---

**6.3.7 Validation**

- **Role.** The record of a test and its result.
- **Asserts.** "This claim was tested this way and this was the outcome."
- **Produced by.** Validation Engine.
- **Consumed by.** Whatever owns the post-validation decision (MISSING-31); indirectly by Feedback.
- **Distinguishing characteristic.** The only object that can carry a negative result about another object — the platform's sole self-correction mechanism before execution.
- **Must carry.** What was tested, method, result, outcome state, link to the validated object.
- **Gaps.** CONTRADICTION-05 (relationship to Experiment Registry); MISSING-33 (outcome states); OPEN QUESTION-09 (what may be validated); MISSING-32 (methodology and standards).

---

**6.3.8 Execution Record**

- **Role.** The record of what happened in reality.
- **Asserts.** "This was acted upon and this was the real outcome."
- **Produced by.** **UNDEFINED — CONTRADICTION-02.** No engine is assigned.
- **Consumed by.** Feedback Engine.
- **Distinguishing characteristic.** The only object sourced from real-world outcome rather than platform reasoning. It is the platform's sole ground-truth signal, and therefore the only thing that makes Principle 5 possible.
- **Must carry.** Link to the Solution/Opportunity acted upon, actual outcome, comparison basis against prediction, timing.
- **Gaps.** CONTRADICTION-02 (no producing engine); MISSING-47: no definition of how outcomes are obtained, verified, or attributed. Given that this is the only ground-truth input to the learning loop, an unverified intake path means the platform can be taught by unreliable outcome reports.

---

### 6.4 Object Relationship Map

```
Evidence ──derived-into──> Fact ──supports──> Problem ──constitutes──> Pattern
                                                                          │
                                                                    gives-rise-to
                                                                          v
Execution Record <──acts-on── Validation <──tests── Solution <──addresses── Opportunity
        │
   informs (Feedback Engine)
        │
        └──> [learning target: MISSING-02] ──> [re-entry as Evidence: CONTRADICTION-04]
```

Every arrow is a lineage relationship that must be persisted in the Knowledge Graph and traversable in both directions — forward for derivation, backward for retraction propagation (MISSING-09).

### 6.5 Objects With No Owning Engine

| Object | Producing engine | Status |
|---|---|---|
| Execution Record | none | **CONTRADICTION-02** |

### 6.6 Engines With No Corresponding Object

| Engine | Object produced | Status |
|---|---|---|
| Feedback | none | **CONTRADICTION-03** |
| Orchestration | none | By design — Orchestration moves work, not knowledge. Not a defect. |

### 6.7 Concepts Referenced But Not Modelled

| Concept | Referenced in | Status |
|---|---|---|
| Score | Vision §1 | **CONTRADICTION-01** — no object, no attribute definition |
| Confidence | implied by P1 and "scores" | **MISSING-15** |
| Rejected candidate | implied by P2 and P5 | **OPEN QUESTION-04** |
| Source / source trust | implied by Evidence | **MISSING-16** |
| Learning update | Vision, P5, Feedback Engine | **MISSING-02**, **CONTRADICTION-03** |
| Research directive | implied by Research Engine | **MISSING-01** |

This table represents the platform's largest category of gap: six concepts that the architecture depends on but does not model.

---

## 7. Completed Research — Expanded

### 7.1 v1 Statement (Preserved Verbatim)

> - Etsy AI vs Traditional
> - Resume Templates
> - Customer Complaints
> - Opportunity Evaluation

### 7.2 Status of This Section

v1 lists four completed research efforts by title only. No findings, dates, sources, methods, or conclusions are recorded.

> **MISSING-48:** No research findings are captured for any of the four items. Titles alone cannot inform implementation, cannot be validated, and cannot be traced.

> **CONTRADICTION-07:** This section is itself a violation of Principles 1 and 3 as applied to the project's own knowledge base. Four research conclusions are asserted as "completed" with no evidence, no sources, no lineage, and no findings. The platform demands evidence-first, traceable reasoning of its own outputs while its foundational documentation records conclusions without any of it. Either these research items must be documented to the standard the platform requires, or they must be reclassified as unverified prior work.

### 7.3 Interpretation of the Four Items

Based solely on the titles, and on their position in v1 immediately before Architecture Decisions, these appear to fall into two categories. This categorisation is inference from ordering and naming, and is flagged as such.

**Category A — Domain research (probable evidence about markets):**
- *Etsy AI vs Traditional* — comparative research within a marketplace domain.
- *Resume Templates* — research within a specific product/market area.
- *Customer Complaints* — research into a source class of problem signal.

**Category B — Methodological research (probable input to the platform's own design):**
- *Opportunity Evaluation* — likely informed the Opportunity Intelligence Engine and possibly the scoring approach implied by the vision.

> **OPEN QUESTION-15:** The above categorisation is inferred, not stated. v1 does not indicate whether these were domain investigations, methodology development, or validation exercises for the platform concept itself. This matters because Category B research, if it exists, may contain the missing scoring methodology (MISSING-14) — the most consequential undocumented item in the platform.

### 7.4 Required Disposition

Each item must be resolved into one of three states before it can be relied upon:

| State | Meaning | Consequence |
|---|---|---|
| **Ingested** | Findings entered the platform as Evidence and traversed the pipeline | Becomes traceable platform knowledge, subject to all principles |
| **Reference only** | Retained as background, explicitly outside the evidence chain | Must never be cited as support for a platform conclusion |
| **Superseded** | Retained for history, no longer current | Excluded from reasoning |

> **MISSING-49:** No disposition is recorded for any of the four items. Until each is dispositioned, it is undefined whether prior research forms part of the platform's evidence base or sits outside it. This is a Principle 1 boundary question and should be resolved in P1.

> **OPEN QUESTION-16:** Whether pre-platform research can be retroactively ingested as Evidence at all. Evidence requires provenance (source, capture time, access context). Research summarised in a document without its underlying sources may be unable to satisfy the Evidence object's requirements, in which case ingestion is structurally impossible and "reference only" is the sole available disposition.

---

## 8. Architecture Decisions — Expanded

### 8.1 v1 Statement (Preserved Verbatim)

> - Evidence-first
> - Intelligence contracts
> - Feedback loop
> - Separation of concerns

### 8.2 Status of This Section

v1 records four decisions as bare titles. An architecture decision, to be usable, requires the alternatives that were rejected and the reasons — otherwise future contributors cannot tell whether a proposed change violates a considered decision or merely an unexamined default.

> **MISSING-50:** No decision records exist. For all four decisions the following are undocumented: context, alternatives considered, rationale, consequences accepted, and date. This is the difference between a decision and a preference, and it applies to every architectural commitment the platform has made.

---

### 8.3 Decision 1 — Evidence-First

**Decision.** All conclusions must derive from and reference traceable evidence.

**What it binds.** Every engine, every object, the Knowledge Store's write-time validation, and the Knowledge Graph's lineage structure. It is the strongest constraint in the platform.

**Relationship to other elements.** Formalises Principle 1; realised structurally by Principle 3; enforced by U6 in §6.2.

**Consequences accepted (derived).**
- Higher cost per conclusion — evidence must be acquired before reasoning can proceed.
- Reduced speed — the platform cannot answer from model knowledge.
- Coverage limited by research reach — the platform is blind to what it has not collected.
- Storage growth — evidence must be retained to preserve traceability.

**Known tensions.**
> **CONTRADICTION-04 (applies):** `Feedback -> Evidence` permits platform-internal content to enter as Evidence, weakening the grounding guarantee this decision exists to provide. This is the deepest architectural tension in v1: the loop that implements Decision 3 undermines Decision 1.

---

### 8.4 Decision 2 — Intelligence Contracts

**Decision.** Engines communicate exclusively through defined Intelligence Objects.

**What it binds.** All nine engines. The eight object definitions are the complete inter-engine interface surface.

**Relationship to other elements.** Enables Principle 4; enforced by Boundary Doctrine rules 2, 3 and 5.

**Consequences accepted (derived).**
- Object definitions become the highest-stakes artefacts in the platform; a weak object definition weakens every engine on both sides of it.
- Object schema changes are breaking changes affecting multiple engines.
- Engines cannot exchange anything the object model does not represent — which is why §6.7's six unmodelled concepts are severe.

**Known tensions.**
> The object definitions are not yet specified to contract standard. MISSING-30 (assumption structure between Solution and Validation) is a concrete instance of a contract that this decision requires but v1 does not provide. Decision 2 is currently aspirational rather than realised.

---

### 8.5 Decision 3 — Feedback Loop

**Decision.** The pipeline closes on itself; outcomes feed back into platform behaviour.

**What it binds.** Pipeline topology, the Feedback Engine, the Execution Record object, Orchestration's control model.

**Relationship to other elements.** Implements Principle 5.

**Consequences accepted (derived).**
- Platform behaviour is time-dependent and non-stationary.
- Regression is possible — learning can make the platform worse.
- The system has no terminal state, so resource consumption is bounded only by explicit control (MISSING-37).
- Debugging becomes historical: current behaviour is a function of the entire outcome history.

**Known tensions.**
> **CONTRADICTION-02 (applies):** the loop is structurally incomplete — no engine produces Execution Records, so the feedback path has a gap between Validation and Feedback.

> **CONTRADICTION-03 (applies):** feedback produces no persisted object, so learning changes are untraceable, breaching Principle 3.

> **MISSING-02 (applies):** the loop has no defined target of change, so it cannot be closed even once the above are resolved.

Decision 3 is the least implementable of the four as currently specified.

---

### 8.6 Decision 4 — Separation of Concerns

**Decision.** Each engine and component has one responsibility and does not encroach on others.

**What it binds.** The nine engines, the three shared components, and the Boundary Doctrine.

**Relationship to other elements.** Underpins Principle 4 and makes Decision 2 enforceable.

**Consequences accepted (derived).**
- More components, more sequencing overhead, higher orchestration complexity.
- Cross-cutting concerns (confidence, scoring, explanation quality) have no natural home and risk being implemented inconsistently in each engine.

**Known tensions.**
> **CONTRADICTION-06 (applies):** Knowledge Store vs Knowledge Graph responsibilities are not separated, directly violating this decision at the component level.

> **CONTRADICTION-01 (applies):** scoring is a cross-cutting concern with no assigned owner — the characteristic failure mode of this decision.

> **MISSING-31, MISSING-28 (apply):** decision points (post-validation promotion, solution selection) fall between engines and are owned by none. Strict separation without an explicit decision-owner creates responsibility voids.

---

### 8.7 Decision Interaction Summary

| | Ev-first | Contracts | Feedback | SoC |
|---|---|---|---|---|
| **Evidence-first** | — | Reinforces | **Conflicts (C-04)** | Neutral |
| **Intelligence contracts** | Reinforces | — | Neutral | Reinforces |
| **Feedback loop** | **Conflicts (C-04)** | Neutral | — | Neutral |
| **Separation of concerns** | Neutral | Reinforces | Neutral | — |

The single decision-level conflict in the architecture is Evidence-first vs Feedback loop, expressed as CONTRADICTION-04. It should be treated as the highest-priority architectural reconciliation.

---

## 9. Roadmap — Expanded

### 9.1 v1 Statement (Preserved Verbatim)

> P0 Specification / P1 Foundation / P2 Research Engine / P3 Fact Engine / P4 Problem Engine / P5 Pattern Engine / P6 Opportunity Engine / P7 Solution & Validation / P8 Feedback

### 9.2 Structural Reading

Nine phases. The sequence follows the pipeline exactly: each phase after P1 builds the next engine in pipeline order. This is a deliberate consequence of the architecture — an engine cannot be built before its input object exists.

Observations on the sequence as given:
- P0 and P1 are enabling phases; P2–P8 are engine phases.
- P7 combines two engines (Solution and Validation); all other phases build one.
- **There is no Orchestration phase**, despite Orchestration being one of the nine engines.
- **There is no Execution phase**, consistent with CONTRADICTION-02 reading (a) — that execution happens outside the platform.

> **CONTRADICTION-08:** The Orchestration Engine appears in v1 §4 but has no roadmap phase. Orchestration is required to sequence any multi-engine pipeline, so it is needed no later than P3 (the first point at which two engines must run in sequence). Either it is implicitly part of P1 Foundation — which v1 does not state — or it is unscheduled. Since Orchestration also carries the largest single specification gap (MISSING-35, no control model), leaving it unscheduled is a material planning risk.

> **MISSING-51:** No phase durations, sequencing dependencies, resource assumptions, or entry/exit criteria are defined for any phase.

> **MISSING-52:** No definition of done for any phase.

---

### 9.3 Phase Expansions

Each phase below is expanded into: objective, scope, what must exist before it starts, what must be true when it ends, blocking gaps, and its characteristic risk.

---

#### P0 — Specification

**Objective.** Establish the complete specification of the platform before construction.

**Scope.** Vision, principles, pipeline, engine responsibilities, object model, knowledge architecture, architecture decisions.

**Prerequisites.** None. This is the entry phase.

**Exit criteria.**
- All nine engines have defined responsibilities and boundaries.
- All eight objects have defined semantics and contracts.
- Architecture decisions are recorded with rationale.
- **All CONTRADICTION items are resolved.**
- All MISSING items blocking P1–P8 are resolved or explicitly deferred with a recorded owner.

**Blocking gaps.** This phase is the owner of every marker in this document. It cannot be considered complete while any CONTRADICTION remains open.

**Status assessment.** v1 represents a partial P0. It establishes structure but not specification: 8 contradictions, 16 open questions and 52 missing definitions remain. **P0 is not complete.** Proceeding to P1 with contradictions unresolved means building foundations against an architecture that has not settled.

**Characteristic risk.** Under-specification mistaken for completion, because the section headings are all present.

---

#### P1 — Foundation

**Objective.** Build the shared substrate all engines depend on.

**Scope.** Knowledge Store, Knowledge Graph, Intelligence Object definitions, lineage mechanism, and — per CONTRADICTION-08 — plausibly Orchestration.

**Prerequisites.** P0 complete. In particular: object mutability (MISSING-08), the Store/Graph boundary (CONTRADICTION-06), and the relationship taxonomy (MISSING-40) must be settled, as all three are foundational and expensive to change later.

**Exit criteria.**
- All eight object types are persistable with identity, provenance, lineage, and explanation.
- Lineage is traversable in both directions.
- Evidence-linkage can be enforced at write time (Principle 1).
- The Store/Graph responsibility split is implemented as decided.

**Blocking gaps.** MISSING-08; MISSING-40; MISSING-45 (lifecycle states); MISSING-15 (confidence model, since it is a universal object requirement); CONTRADICTION-06; MISSING-39 (consistency model); MISSING-44 (write authority).

**Characteristic risk.** Foundation choices are the hardest to reverse. Building the Knowledge Store before mutability semantics are decided is the highest-cost sequencing error available in this roadmap.

---

#### P2 — Research Engine

**Objective.** Establish evidence acquisition — the platform's only contact with the outside world.

**Scope.** Source acquisition, Evidence object creation, provenance capture.

**Prerequisites.** P1 complete (Evidence must be persistable).

**Exit criteria.**
- Evidence is acquired and persisted with complete provenance.
- Source diversity is recorded (required later by P5 — see MISSING-23).
- Duplicate capture is detectable.

**Blocking gaps.** MISSING-16 (source taxonomy and trust); MISSING-01 (what initiates research); MISSING-18 (acquisition legal policy); MISSING-17 (coverage); OPEN QUESTION-12 (content vs reference storage).

**Characteristic risk.** Everything downstream inherits the quality and bias of this phase. Source-diversity accounting omitted here cannot be reconstructed later, and its absence silently invalidates P5.

---

#### P3 — Fact Engine

**Objective.** Convert Evidence into discrete, anchored, checkable Facts.

**Scope.** Extraction, anchoring to source location, deduplication.

**Prerequisites.** P2 complete.

**Exit criteria.**
- Facts are extracted with anchors back to specific evidence locations.
- Fact identity and deduplication behave per a defined rule.
- Extraction fidelity is measurable.

**Blocking gaps.** MISSING-19 (what qualifies as a fact); MISSING-11 (identity); MISSING-20 (fidelity verification); OPEN QUESTION-03 (contradictory facts).

**Characteristic risk.** Hallucination. This is the phase where ungrounded content can enter while satisfying every structural check the platform performs. Without a fidelity mechanism (MISSING-20), the platform's core guarantee is unverified from this phase onward.

**Note.** This is the first phase requiring two engines to run in sequence, so Orchestration must exist by now (CONTRADICTION-08).

---

#### P4 — Problem Engine

**Objective.** Infer Problems from Facts — the platform's first interpretive capability.

**Scope.** Problem inference, attribution to affected populations, supporting-fact linkage.

**Prerequisites.** P3 complete, with sufficient Fact volume to support inference.

**Exit criteria.**
- Problems are inferred with explicit supporting Facts and explanations.
- Problem statements are solution-independent.
- Problems are classified per a defined taxonomy.

**Blocking gaps.** MISSING-12 (attributes); MISSING-21 (taxonomy); MISSING-22 (identity); MISSING-06 (sufficiency thresholds).

**Characteristic risk.** Solution smuggling. A solution-shaped problem definition here biases P5, P6 and P7 irreversibly, and the bias is invisible downstream because the lineage still validates.

---

#### P5 — Pattern Engine

**Objective.** Detect structure across the Problem population.

**Scope.** Clustering, recurrence detection, cross-domain similarity, significance assessment.

**Prerequisites.** P4 complete, with a Problem population large enough for cross-comparison, and source-diversity data from P2.

**Exit criteria.**
- Patterns identified with all constituent Problems linked.
- Pattern strength measured per a defined method.
- Sampling artefacts distinguishable from genuine patterns.

**Blocking gaps.** MISSING-23 (source diversity — depends on P2 having captured it); MISSING-24 (strength measure); MISSING-25 (pattern taxonomy); MISSING-13 (temporal validity).

**Characteristic risk.** This phase cannot succeed if P2 did not record source independence. It is the clearest cross-phase dependency in the roadmap and is not visible in v1's phase list.

---

#### P6 — Opportunity Engine

**Objective.** Convert Patterns into scored, comparable Opportunities — the platform's primary output.

**Scope.** Opportunity formulation, assessment, scoring, ranking.

**Prerequisites.** P5 complete; scoring methodology decided.

**Exit criteria.**
- Opportunities generated with linked Patterns and explanations.
- Scores produced on a defined, consistent basis.
- Opportunities are comparable and rankable.
- Confidence reflects underlying evidential strength.

**Blocking gaps.** CONTRADICTION-01 (scoring ownership — must be resolved before this phase); MISSING-14 (scoring dimensions and scale); MISSING-26 (what an opportunity is); MISSING-27 (ranking policy); MISSING-15 (confidence model).

**Characteristic risk.** This phase delivers the platform's headline capability while carrying the largest concentration of unresolved definition. Scoring cannot be built at all until CONTRADICTION-01 and MISSING-14 are closed.

---

#### P7 — Solution & Validation

**Objective.** Generate candidate solutions and test their assumptions.

**Scope.** Two engines: Solution Intelligence and Validation. Also the Experiment Registry, which v1 does not schedule anywhere else.

**Prerequisites.** P6 complete.

**Exit criteria.**
- Solutions generated with explicit, testable assumptions.
- Validations executed and recorded, including negative results.
- Experiment Registry operational and its relationship to Validation objects resolved.

**Blocking gaps.** MISSING-30 (assumption structure — the contract between the two engines in this phase); CONTRADICTION-05 (Validation object vs Experiment Registry); MISSING-32 (methodology); MISSING-33 (outcome states); OPEN QUESTION-08 (what triggers solution development); OPEN QUESTION-09 (what may be validated); MISSING-28 and MISSING-31 (unowned decisions).

> **OPEN QUESTION-17:** v1 combines two engines into a single phase without stating why. Given that Decision 4 (Separation of concerns) and the independence requirement in §4.10 both depend on Solution and Validation being genuinely separate, combining their construction risks coupling. Whether this combination is deliberate (they are jointly testable) or incidental is undefined.

> **MISSING-53:** The Experiment Registry, one of three shared components, has no explicit phase. It is presumed here to fall in P7 because that is where validation occurs, but v1 does not schedule it. Compare CONTRADICTION-08 for Orchestration — two of the platform's twelve named components are unscheduled.

**Characteristic risk.** Confirmation bias, structurally invited by building the generator and its tester in the same phase.

---

#### P8 — Feedback

**Objective.** Close the loop; make the platform learn.

**Scope.** Execution Record intake, outcome comparison, learning updates, loop closure.

**Prerequisites.** P7 complete; execution outcomes available; and critically, CONTRADICTION-02 resolved so Execution Records have a producer.

**Exit criteria.**
- Execution Records captured and linked to predictions.
- Learning updates applied to a defined target, traceably and reversibly.
- The loop closes without instability.

**Blocking gaps.** CONTRADICTION-02 (no Execution Record producer); CONTRADICTION-03 (no Feedback object); CONTRADICTION-04 (feedback-as-Evidence); MISSING-02 (learning target); MISSING-04 (success measure — nothing can improve against an undefined measure); MISSING-10 (cadence); MISSING-34 (reversion); MISSING-47 (outcome verification); OPEN QUESTION-05 (approval).

**Characteristic risk.** This phase carries three of the eight contradictions and cannot begin until all are resolved. It is also gated by MISSING-04, which sits back in P0 — the platform cannot learn to be "better" without a definition of better. **P8 is the most heavily blocked phase in the roadmap.**

---

### 9.4 Cross-Phase Dependencies Not Visible in v1's Sequence

The linear phase list conceals several dependencies that will cause rework if not planned for:

| Dependency | From | To | Consequence if missed |
|---|---|---|---|
| Source diversity capture | P2 | P5 | Pattern validity unassessable; P2 rework |
| Confidence model | P1 | P6 | Scores not interpretable; object rework |
| Object lifecycle states | P1 | P7 | Validation outcomes unrepresentable |
| Immutable predictions | P1 | P8 | Learning has no comparison basis |
| Success measure | P0 | P8 | Learning has no objective |
| Orchestration | unscheduled | P3 | No multi-engine sequencing |
| Scoring methodology | P0 | P6 | Headline capability unbuildable |
| Assumption structure | P0 | P7 | Solution/Validation contract broken |

> **MISSING-54:** v1's roadmap is presented as a linear sequence with no dependency model. Eight of these cross-phase dependencies are foundational (originating in P0 or P1), meaning late discovery causes foundation-level rework rather than local fixes.

### 9.5 Phase Readiness Summary

| Phase | Contradictions | Missing items | Readiness |
|---|---|---|---|
| P0 Specification | all 8 | all | In progress — this document defines its remaining work |
| P1 Foundation | C-06 | 8-40-45-15-39-44 | **Blocked** on C-06, MISSING-08 |
| P2 Research | — | 16-01-18-17 | **Blocked** on MISSING-16 |
| P3 Fact | — | 19-11-20 | **Blocked** on MISSING-19 |
| P4 Problem | — | 12-21-22-06 | **Blocked** on MISSING-21 |
| P5 Pattern | — | 23-24-25-13 | **Blocked** on MISSING-23 (and P2) |
| P6 Opportunity | C-01 | 14-26-27-15 | **Blocked** on C-01, MISSING-14 |
| P7 Solution & Validation | C-05 | 30-32-33-28-31-53 | **Blocked** on C-05, MISSING-30 |
| P8 Feedback | C-02, C-03, C-04 | 02-04-10-34-47 | **Blocked** — most constrained phase |
| — Orchestration | C-08 | 35-36-37 | **Unscheduled** |

No phase is currently unblocked. Every blocker is a P0 specification item, which is the correct and expected finding for a foundation-stage document — but it means P0 must be genuinely completed before construction begins.

---

## 10. Cross-Cutting Concerns

Concerns that span all engines and therefore belong to no single one. Under Decision 4 (Separation of concerns), these are precisely the items at risk of inconsistent implementation, since strict separation gives them no natural owner.

| # | Concern | Present in v1 | Status |
|---|---|---|---|
| X1 | Confidence representation and propagation | Implied only | **MISSING-15** |
| X2 | Scoring | Vision only | **CONTRADICTION-01**, **MISSING-14** |
| X3 | Explanation format and quality | Principle 2 | **MISSING-07** |
| X4 | Object lifecycle and status | No | **MISSING-45** |
| X5 | Temporal validity and decay | No | **MISSING-46**, **MISSING-13** |
| X6 | Deduplication and identity | No | **MISSING-11**, **MISSING-22** |
| X7 | Retraction and correction | No | **MISSING-09** |
| X8 | Versioning and immutability | No | **MISSING-08** |
| X9 | Failure handling and recovery | No | **MISSING-36** |
| X10 | Volume, scale and retention | No | **MISSING-38** |
| X11 | Human involvement points | No | **OPEN QUESTION-02** |
| X12 | Determinism and reproducibility | No | **OPEN QUESTION-01** |
| X13 | Security, access control, tenancy | No | **MISSING-55** |
| X14 | Legal and compliance in acquisition | No | **MISSING-18** |
| X15 | Cost model | No | **MISSING-56** |
| X16 | Observability of engine behaviour | No | **MISSING-57** |

> **MISSING-55:** v1 addresses no security, access control, confidentiality, or tenancy concerns, despite the platform aggregating market intelligence that is likely commercially sensitive.

> **MISSING-56:** v1 contains no cost model. An AI-native platform running a continuous loop over high-volume evidence has cost as a primary design constraint, and no engine has a defined cost boundary.

> **MISSING-57:** v1 defines no observability requirements. Principle 2 covers explanation of decisions to users; it does not cover operational visibility into engine behaviour, throughput, or degradation.

Sixteen cross-cutting concerns, of which zero are specified in v1. This is the systemic weakness of the current architecture: it is well-decomposed vertically (engines, stages, objects) and unspecified horizontally.

---

## 11. Contradiction Register

Eight contradictions. Each blocks the listed phase and must be resolved by explicit decision, not by implementation choice.

| ID | Summary | Location | Blocks | Severity |
|---|---|---|---|---|
| **C-01** | Vision requires scoring; no engine, stage or object owns it | §1.2.4, §3 Stage 5, §4.8 | P6 | High |
| **C-02** | Execution is a pipeline stage with an object but no engine | §3 Stage 8, §4.13, §6.5 | P8 | **Critical** |
| **C-03** | Feedback is a stage and engine but produces no object, so learning is untraceable (breaches P3) | §3 Stage 9, §4.11, §6.6 | P8 | High |
| **C-04** | `Feedback -> Evidence` lets internal content enter as Evidence, undermining the grounding property Decision 1 exists to guarantee | §3 Stage 1, §8.3 | P8 | **Critical** |
| **C-05** | Validation object vs Experiment Registry relationship undefined | §3 Stage 7, §5.4 | P7 | High |
| **C-06** | Knowledge Store vs Knowledge Graph responsibilities not separated (violates Decision 4) | §5.2, §5.3 | P1 | **Critical** |
| **C-07** | Completed Research asserts four conclusions with no evidence or lineage, violating Principles 1 and 3 within the project's own documentation | §7.2 | P0 | Medium |
| **C-08** | Orchestration Engine exists but has no roadmap phase, though needed by P3 | §9.2 | P3 | High |

**Resolution priority.** C-06 first (blocks P1, the foundation). Then C-04 and C-02, which are architectural rather than structural and will take longest to settle. Then C-01, C-05, C-08. C-03 follows from C-02. C-07 is documentation remediation.

---

## 12. Open Question Register

Seventeen decision points. Each has more than one defensible answer; v1 does not indicate which was intended.

| ID | Question | Affects |
|---|---|---|
| **OQ-01** | Is the platform expected to be deterministic/reproducible? | All engines, both knowledge components |
| **OQ-02** | Is there human involvement, and at which gates? | All engines, object lifecycle, Orchestration |
| **OQ-03** | Must contradictory evidence be represented? | Fact, Knowledge Graph |
| **OQ-04** | Are rejected candidates persisted? | All engines, storage growth |
| **OQ-05** | Do learning updates require approval? | Feedback Engine, risk posture |
| **OQ-06** | What is the precedence rule when principles conflict? | All specifications |
| **OQ-07** | May Pattern Intelligence read Facts directly? | Pattern Engine, pipeline strictness |
| **OQ-08** | What triggers solution development for an opportunity? | Solution Engine, Orchestration, cost |
| **OQ-09** | What does Validation validate — Solutions only, or any object? | Validation Engine scope |
| **OQ-10** | May pipeline stages be skipped? | Pipeline integrity, Principle 1 |
| **OQ-11** | Is backflow (downstream triggering upstream) permitted? | Orchestration control model |
| **OQ-12** | Is Evidence stored in full, by reference, or both? | Research Engine, storage, OQ-01 |
| **OQ-13** | May multiple pipeline traversals run concurrently? | Orchestration, knowledge consistency |
| **OQ-14** | Does the Experiment Registry cover platform-level learning experiments? | Experiment Registry, Feedback traceability |
| **OQ-15** | Were the four completed research items domain or methodology research? | P0 inputs, possibly MISSING-14 |
| **OQ-16** | Can pre-platform research be retroactively ingested as Evidence? | Evidence definition, P1 |
| **OQ-17** | Why are Solution and Validation combined into one phase? | P7 structure, independence requirement |

---

## 13. Missing Definition Register

Fifty-seven items. Grouped by the phase that must resolve them.

**Must resolve in P0 (Specification) — 17 items**

| ID | Missing definition |
|---|---|
| M-01 | What initiates discovery / the research trigger |
| M-02 | What the platform learns — the target of change |
| M-03 | Non-goals / explicit scope exclusions |
| M-04 | Success criteria and measures of effectiveness |
| M-05 | Who consumes platform output, and where it exits |
| M-06 | Minimum evidence sufficiency per object type |
| M-07 | Explanation format, granularity, minimum content |
| M-14 | Scoring dimensions, scale, weighting, aggregation |
| M-26 | What an "opportunity" is in platform terms |
| M-29 | Solution granularity |
| M-30 | Assumption structure (Solution→Validation contract) |
| M-32 | Validation methodology and evidence standards |
| M-48 | Findings of the four completed research items |
| M-49 | Disposition of prior research (ingested / reference / superseded) |
| M-50 | Architecture decision records (context, alternatives, rationale) |
| M-51 | Phase durations, dependencies, entry/exit criteria |
| M-52 | Definition of done per phase |

**Must resolve in P1 (Foundation) — 12 items**

| ID | Missing definition |
|---|---|
| M-08 | Object mutability and versioning |
| M-09 | Retraction and correction semantics |
| M-15 | Confidence model and propagation |
| M-38 | Retention policy |
| M-39 | Consistency model between Store and Graph |
| M-40 | Relationship taxonomy for the Knowledge Graph |
| M-41 | Cycle handling in the lineage graph |
| M-44 | Write-authority model |
| M-45 | Object lifecycle and status states |
| M-46 | Temporal validity model |
| M-54 | Cross-phase dependency model |
| M-55 | Security, access control, tenancy |

**Must resolve in P2 (Research) — 4 items**

| ID | Missing definition |
|---|---|
| M-16 | Source taxonomy, eligibility, trust model |
| M-17 | Coverage and completeness concept |
| M-18 | Legal, licensing, rate-limit, terms-of-use policy |
| M-23 | Source diversity and independence accounting |

**Must resolve in P3–P5 (Fact, Problem, Pattern) — 8 items**

| ID | Missing definition |
|---|---|
| M-11 | Fact identity and deduplication |
| M-19 | What qualifies as a fact; extraction granularity |
| M-20 | Extraction fidelity verification (hallucination detection) |
| M-12 | Problem attributes (severity, frequency, population) |
| M-21 | Problem taxonomy |
| M-22 | Problem identity and deduplication |
| M-13 | Pattern temporal validity |
| M-24 | Pattern strength measure and minimum constituents |
| M-25 | Pattern type taxonomy |

**Must resolve in P6–P8 (Opportunity, Solution/Validation, Feedback) — 10 items**

| ID | Missing definition |
|---|---|
| M-27 | Prioritisation and ranking policy |
| M-28 | Owner of solution selection |
| M-31 | Owner of post-validation promote/reject decision |
| M-33 | Validation outcome states |
| M-42 | Experiment lifecycle |
| M-53 | Experiment Registry phase assignment |
| M-10 | Learning cadence and trigger |
| M-34 | Learning update reversion mechanism |
| M-43 | Feedback Engine write target |
| M-47 | How execution outcomes are obtained, verified, attributed |

**Orchestration (unscheduled) — 3 items**

| ID | Missing definition |
|---|---|
| M-35 | Control model (event / batch / scheduled / continuous) |
| M-36 | Failure-handling policy |
| M-37 | Loop termination and iteration bounding |

**Cross-cutting, no natural owner — 3 items**

| ID | Missing definition |
|---|---|
| M-56 | Cost model |
| M-57 | Observability requirements |
| M-05 | (also listed in P0) Output consumers |

---

## 14. Traceability to PKP v1

Confirmation that this document expands v1 without altering it.

| v1 Section | v1 Content | v2 Section | Treatment |
|---|---|---|---|
| 1. Vision | 1 statement | §1 | Preserved verbatim, decomposed into 5 commitments |
| 2. Principles | 5 items | §2 | All 5 preserved; each expanded with rationale, implications, anti-patterns, verification |
| 3. Pipeline | 10 stage positions | §3 | Order preserved exactly; each stage expanded |
| 4. Engines | 9 engines | §4 | All 9 preserved; none added, renamed or merged |
| 5. Shared Components | 3 components | §5 | All 3 preserved and expanded |
| 6. Intelligence Objects | 8 objects | §6 | All 8 preserved; none added |
| 7. Completed Research | 4 items | §7 | All 4 preserved; gaps marked, no findings invented |
| 8. Architecture Decisions | 4 decisions | §8 | All 4 preserved and expanded |
| 9. Roadmap | 9 phases | §9 | All 9 preserved in original order |

**Counts.** v1: 5 principles, 9 engines, 3 components, 8 objects, 9 stages, 4 decisions, 9 phases. v2: identical in every count.

**Additions.** Sections 0, 10, 11, 12, 13, 14 are navigational, cross-cutting, or registers. They introduce no new architectural element — Section 10 catalogues concerns absent from v1 rather than adding capability.

---

## 15. Document Governance

**Status.** This document expands v1. It does not resolve v1's gaps; it identifies them. It becomes the master reference once P0 markers are dispositioned.

**Amendment rule.** Any change to an engine, object, stage, principle, component, decision or phase is an architecture change requiring a recorded decision (MISSING-50 applies — no decision record mechanism yet exists).

**Marker resolution rule.** A marker is closed only by a recorded decision stating what was decided, why, and which alternatives were rejected. Markers must never be closed by implementation choice, since that would place architecture decisions in code rather than in this document.

**Review triggers.** Completion of any phase; resolution of any contradiction; any proposed change to the object model, since objects are the platform's contracts.

**Summary of outstanding work.**

| Category | Count | Blocking |
|---|---|---|
| Contradictions | 8 | 3 critical (C-02, C-04, C-06) |
| Open questions | 17 | all phases |
| Missing definitions | 57 | all phases |
| **Total** | **82** | **P0 incomplete** |

**Principal finding.** v1 is a structurally sound and internally coherent architecture skeleton. Its decomposition — pipeline, engines, objects, components — is consistent and the four architecture decisions reinforce each other with one exception (Evidence-first vs Feedback loop, C-04). What it lacks is horizontal specification: the sixteen cross-cutting concerns in §10, of which none are addressed, and the semantics that turn named objects into enforceable contracts. The recommended next action is completion of P0 against the three registers in Sections 11–13, beginning with the three critical contradictions.

---

*End of PKP v2 — Master Reference.*
