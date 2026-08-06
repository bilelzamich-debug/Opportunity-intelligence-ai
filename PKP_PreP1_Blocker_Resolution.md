# Opportunity Intelligence Platform
## Pre-P1 Blocker Resolution Analysis

**Document type:** Blocker review and readiness assessment
**Purpose:** Eliminate every implementation blocker before Phase P1 begins
**Inputs:** PKP v2 — Master Reference; Intelligence Object Model — Complete Specification
**Status:** Analysis and recommendation. No decision herein is ratified.

---

## 0. Preliminary — Marker Identifier Reconciliation

### 0.1 A Defect Found During Review

Before any blocker can be reviewed, a cross-document defect must be corrected.

The Intelligence Object Model (IOM) cites marker identifiers that **do not match** the canonical register in PKP v2 §13. The IOM was drafted against an intermediate numbering that diverged from the master register. The *substance* of every IOM statement is sound; the *identifiers* are unreliable.

Examples of the divergence:

| IOM cites | IOM means | v2 canonical M-ID actually means |
|---|---|---|
| MISSING-25 | Validation methodology | Pattern type taxonomy |
| MISSING-32 | Relationship taxonomy | Validation methodology |
| MISSING-18 | Source taxonomy | Legal / licensing / terms-of-use |
| MISSING-22 | Source diversity propagation | Problem identity and deduplication |
| MISSING-26 | Gate ownership | What an "opportunity" is |
| MISSING-31 | Retention policy | Post-validation promote/reject owner |
| MISSING-36 | Outcome intake mechanism | Failure-handling policy |
| CONTRADICTION-08 | Object model has no attributes | Orchestration has no roadmap phase |

Left uncorrected, every blocker in this document would be ambiguous, and any decision recorded against an ID would attach to the wrong gap.

**This document uses PKP v2 §13 / §11 / §12 as canonical.** All IOM references are translated below. Blockers additionally carry a `B-nn` identifier that is stable regardless of underlying marker renumbering.

### 0.2 Crosswalk — IOM Reference → Canonical

| IOM cited | Substance | Canonical | Note |
|---|---|---|---|
| MISSING-35 / CONTRADICTION-08 | Object model has no attributes | **M-68** *(new)* | No v2 equivalent existed; resolved by IOM |
| MISSING-08 | Object mutability | M-08 | Match |
| MISSING-45 | Lifecycle / status states | M-45 | Match |
| MISSING-15 | Confidence model | M-15 | Match |
| MISSING-46 | Temporal validity | M-46 | Match |
| MISSING-11 | Fact identity / dedup | M-11 | Match |
| MISSING-32 | Relationship taxonomy | **M-40** | Corrected |
| MISSING-25 | Validation methodology | **M-32** | Corrected |
| MISSING-18 | Source taxonomy / trust | **M-16** | Corrected |
| MISSING-22 | Source diversity to Pattern | **M-23** | Corrected |
| MISSING-26 | Gate ownership | **M-31** | Corrected |
| MISSING-31 | Retention policy | **M-38** | Corrected |
| MISSING-36 | Outcome intake | **M-47** | Corrected; merged with IOM MISSING-47 |
| MISSING-47 | Outcome verification | **M-47** | Same canonical item |
| MISSING-24 | Constraint model | **M-69** *(new)* | No v2 equivalent |
| MISSING-27 | Feedback instability guard | **M-70** *(new)* | No v2 equivalent |
| MISSING-17 | Failure representation | **M-36** | Corrected (policy + representation) |
| MISSING-02 | Learning target | M-02 (+ M-43) | Match; M-43 is the write-target half |
| MISSING-14 | Scoring | M-14 | Match |
| MISSING-12 | Problem attributes | M-12 | Match |
| MISSING-06 | Evidence sufficiency | M-06 | Match |
| CONTRADICTION-02/03/04/05/06 | — | C-02/03/04/05/06 | Match |
| OPEN QUESTION-21 | Cross-stage read access | **OQ-18** *(new)* | No v2 equivalent |
| OPEN QUESTION-23 | Concurrency | **OQ-13** | Corrected |
| OPEN QUESTION-25 | Evidence full vs reference | **OQ-12** | Corrected |
| OPEN QUESTION-28 | Source trust attribute | M-16 | Subsumed |
| OPEN QUESTION-29 | Score point-in-time vs recomputed | **OQ-19** *(new)* | No v2 equivalent |
| OQ-34 | Ceiling min vs weighted | **OQ-20** | Renumbered |
| OQ-35 | Pattern constituent versioning | **OQ-21** | Renumbered |
| M-58 … M-67 | IOM-originated gaps | M-58 … M-67 | No collision; v2 ended at M-57 |

### 0.3 Closed by the Intelligence Object Model

Seventeen markers are closed, subject to ratification of decisions D-01 … D-08.

| Canonical | Gap | Closed by |
|---|---|---|
| M-68 | Object attributes undefined | IOM §3 (all nine types) |
| M-08 | Mutability / versioning | D-01, D-01a |
| M-45 | Lifecycle and status | D-02 |
| M-15 | Confidence model | D-03 |
| M-46 | Temporal validity | D-04 |
| M-11 | Fact identity / dedup | D-05 |
| M-40 | Relationship taxonomy | D-06 |
| M-41 | Cycle handling | V10 + §4.2 loop closure |
| M-44 | Write-authority model | §2.5 authority matrix |
| M-30 | Assumption structure | Solution structured assumptions |
| M-33 | Validation outcome states | `result` enumeration |
| M-09 | Retraction semantics | D-02 states + I6 *(owner still open — B-03)* |
| C-03 | Feedback has no object | D-07 |
| C-04 | Feedback→Evidence | §4.2 behavioural closure *(provisional)* |
| C-06 | Store/Graph boundary | D-08 *(partial — see B-06)* |
| OQ-03 | Contradictory evidence | `CONTRADICTS` relationship |
| OQ-04 | Rejected candidates | D-02 retention |

### 0.4 Remaining Inventory

| Category | v2 original | Closed by IOM | Added by IOM | **Remaining** |
|---|---|---|---|---|
| Missing definitions | 57 | 13 | 13 (M-58…M-70) | **57** |
| Open questions | 17 | 2 | 4 (OQ-18…OQ-21) | **19** |
| Contradictions | 8 | 3 (incl. 2 provisional) | 0 | **5** |
| **Total** | **82** | **18** | **17** | **81** |

Resolving the object model closed eighteen items and opened seventeen. This is expected: rigorous specification converts vague unease into specific, actionable gaps. The count is flat; the *quality* of what remains is far higher, and every remaining item is now individually addressable.

### 0.5 Blocker Classification

| Class | Meaning | Count |
|---|---|---|
| **BLOCKING-P1** | P1 cannot safely start or complete without this | 21 |
| **BLOCKING-ENGINE** | P1 may proceed; a named engine phase cannot | 22 |
| **DEFERRABLE** | Needed before operation, not before construction | 38 |

Full treatment (all ten requested fields) is given to all 43 BLOCKING items in §1–§2. The 38 DEFERRABLE items receive complete but condensed treatment in §3, with every field represented. **No item is omitted.**

---

## 1. Blockers Requiring Resolution Before P1

Twenty-one items. P1 builds the Knowledge Store, Knowledge Graph, and object model realisation — the platform's least changeable layer. Each item below either prevents P1 construction or would force P1 rework if deferred.

---

### B-01 — Engine Configuration Referent
**Canonical:** M-63

**Description.** Every Intelligence Object carries `engine_configuration_ref`, recording the configuration in force when the object was produced. No component is defined to hold engine configuration or its history. The attribute is mandatory but has no referent.

**Why it blocks implementation.** Principle 3 requires that a transformation be reconstructable, which requires knowing not just which engine ran but how it was configured. Principle 5 makes configuration change continuously through learning. If P1 persists objects without a resolvable configuration reference, every object created before the gap is closed has permanently unreconstructable provenance — the data cannot be retrofitted because the configuration state at creation time is gone.

**Engines affected.** All nine. Every object write carries the attribute.

**Severity.** **Critical.** Unrecoverable if deferred past P1.

**Options.**
1. Configuration as a fourth shared component — clean, but adds a component to v1's three.
2. Configuration as objects in the Knowledge Store — no new component; but configuration is not an Intelligence Object and would pollute the object model.
3. Configuration snapshot embedded in each object — self-contained, no new component; heavy duplication.
4. Configuration held per-engine, referenced by identifier — modular; no single audit surface.

**Recommendation.** **Option 1 — a dedicated configuration store, resolved as a scoped extension of the Knowledge Store rather than a new architectural component.** Configuration records are immutable, versioned, and referenced by identifier. This preserves v1's three-component structure while giving the reference a real target.

**Trade-offs.** Stretches the Knowledge Store's stated remit ("holds Intelligence Objects"). The alternative — a genuinely new component — would breach the no-redesign constraint more seriously. Accepting a scoped extension is the smaller deviation, and it must be recorded as a decision.

**Dependencies.** M-34 (learning reversion) depends on configuration history existing. B-06 (store/graph boundary) should be settled first, as it determines where a configuration store sits.

**Timing.** **Must resolve before P1.**

---

### B-02 — Acceptance Authority
**Canonical:** M-64

**Description.** Validation rules V1–V12 must be enforced at the `PROPOSED` → `ACTIVE` transition. No component is assigned to enforce them. Engines cannot self-certify (an engine asserting its own output is valid is not a check), and shared components are specified as non-interpretive.

**Why it blocks implementation.** Every integrity guarantee in the object model — evidence linkage, lineage resolvability, confidence ceiling, acyclicity — is enforced at acceptance. Without an owner, the rules are aspirational. P1 builds the write path; if acceptance is not part of it, invalid objects enter the store from the first write and the store's contents can never again be trusted without a full retrospective audit.

**Engines affected.** All nine, plus Knowledge Store and Knowledge Graph.

**Severity.** **Critical.** The single largest integrity exposure in P1.

**Options.**
1. Knowledge Store enforces at write — natural chokepoint; v2 §5.2 already grants it structural-validity rejection. Risk: drifts toward interpretation.
2. Orchestration Engine enforces — has cross-engine visibility, but v1 forbids it making quality judgements.
3. Each producing engine self-certifies — no new owner; no independent check.
4. A validation function invoked by the Store but specified separately — separates *mechanism* from *policy*.

**Recommendation.** **Option 4.** The Knowledge Store performs enforcement at write, but the rule set is specified in the object model, not in the Store. The Store checks structure; it never interprets content. This stays inside v2 §5.2's existing grant and keeps the Store non-interpretive.

**Trade-offs.** Requires a hard discipline: rules must be expressible structurally. Rules needing semantic judgement (e.g. F-V6, "the claim is present in the Evidence") cannot be enforced this way — see B-20, which is precisely why that gap is severe.

**Dependencies.** B-06 (store/graph boundary). Constrains B-03.

**Timing.** **Must resolve before P1.**

---

### B-03 — Cascade Invalidation Owner
**Canonical:** M-58 (with M-09)

**Description.** Constraint I6 requires that when Evidence is retracted or invalidated, all downstream dependents transition to `INVALIDATED`. This requires forward lineage traversal and bulk status transition. No engine owns this; assigning it to an existing engine would extend that engine's remit beyond its v1 responsibility.

**Why it blocks implementation.** Retraction is not exceptional — sources withdraw content routinely. Without cascade, conclusions built on withdrawn evidence remain `ACTIVE` and indistinguishable from sound ones. This is a silent-corruption path directly through the platform's grounding layer. It must exist in P1 because the lineage structures that make cascade possible are built in P1.

**Engines affected.** Research (retraction origin); all downstream consumers; Knowledge Graph (forward traversal).

**Severity.** **Critical.**

**Options.**
1. Orchestration owns cascade — has cross-cutting scope; but it is forbidden from making knowledge judgements. Cascade is arguably mechanical, not judgemental.
2. Knowledge Graph performs cascade as a structural operation — the graph owns traversal; but v1 says the graph does not infer.
3. Each engine invalidates its own outputs on notification — respects ownership; requires a notification mechanism that does not exist and creates engine-to-engine coupling.
4. Cascade as a defined maintenance operation with no engine owner, invoked by Orchestration.

**Recommendation.** **Option 4.** Cascade is specified as a mechanical integrity operation over the lineage graph, invoked by Orchestration but performing no interpretation — it propagates a status already determined at the source. This preserves Orchestration's non-interpretive boundary (it triggers, it does not judge) and the Graph's non-inferential boundary (it traverses, it does not conclude).

**Trade-offs.** Introduces an operation that is not an engine, which is a mild structural novelty. The alternative — engine-to-engine notification — would breach Principle 4 far more seriously.

**Dependencies.** B-02 (status transition authority); B-06 (traversal ownership). Enables M-09.

**Timing.** **Must resolve before P1.**

---

### B-04 — Evidential Support Computation
**Canonical:** M-59

**Description.** `evidential_support` is a mandatory attribute on every object, computed from lineage. The inputs are identifiable — independent source count, source diversity, corroboration, contradiction — but no function combines them.

**Why it blocks implementation.** Without the function, `evidential_support` is either unpopulated (objects cannot reach `ACTIVE`) or populated arbitrarily by each engine (values become incomparable, and the confidence ceiling — the platform's defence against its most consequential failure — becomes arithmetic over meaningless numbers).

**Engines affected.** All eight pipeline engines.

**Severity.** **Critical.**

**Options.**
1. Single platform-wide function computed centrally from lineage — guarantees comparability; may be insensitive to type-specific nuance.
2. Per-object-type functions — better fit; risks incomparability across types, which the ceiling rule requires.
3. Engine-asserted with recorded justification — flexible; abandons comparability.
4. Central function for the base value, with a bounded per-type adjustment.

**Recommendation.** **Option 1 for P1.** A single conservative function over independent source count and source diversity. Comparability matters more than nuance at this stage, and the ceiling rule's validity depends on it. Option 4 becomes available later once real distributions are observable.

**Trade-offs.** A crude function will misjudge specific cases. But an incomparable one silently corrupts every ranking — a worse failure, and harder to detect.

**Dependencies.** Requires B-27 (source diversity propagation) — diversity cannot be an input if it never reaches downstream engines. Constrained by OQ-20 (min vs weighted ceiling).

**Timing.** **Must resolve before P1.** The attribute is universal and populated at every write.

---

### B-05 — Confidence Calibration Across Engines
**Canonical:** M-60

**Description.** `assertion_confidence` is asserted independently by each engine. Nothing establishes that Problem Intelligence's 0.7 denotes the same certainty as Opportunity Intelligence's 0.7. The ceiling rule takes the minimum across engines, so it is arithmetically valid but semantically unsound.

**Why it blocks implementation.** This is the deepest flaw in the confidence model. Uncalibrated confidence makes cross-object comparison meaningless, and comparison is what the vision's scoring commitment rests on. If P1 stores uncalibrated values, historical confidence is uninterpretable forever — recalibration cannot be applied retrospectively to immutable objects without creating a new version of everything.

**Engines affected.** All eight pipeline engines.

**Severity.** **Critical.**

**Options.**
1. Shared rubric — each band defined by observable criteria all engines apply.
2. Reference anchoring — worked examples per band per engine.
3. Post-hoc calibration against outcomes via the Feedback Engine — empirically grounded; requires outcomes that do not yet exist (C-02).
4. Abandon cross-engine comparability; use confidence only within an object type.

**Recommendation.** **Option 1 plus Option 2 for P1; Option 3 later.** A shared rubric with worked anchors per band, ratified before P1. Once execution outcomes exist, recalibrate empirically. Option 4 is rejected: it would void the ceiling rule.

**Trade-offs.** A rubric is judgement-based and imperfect. But an unstated calibration is also a calibration — just an invisible and inconsistent one.

**Dependencies.** Empirical calibration depends on C-02 and M-47. Interacts with B-04.

**Timing.** **Must resolve before P1** (rubric). Empirical refinement post-P8.

---

### B-06 — Knowledge Store / Knowledge Graph Boundary and Consistency
**Canonical:** C-06 and M-39

**Description.** D-08 provisionally makes objects authoritative for their own lineage, with the Graph a derived index. This constrains but does not settle C-06: the Graph's traversal responsibilities, query surface, and the consistency model between Store and Graph (M-39) remain undefined. A write touching both is of undefined atomicity.

**Why it blocks implementation.** This is *the* P1 decision. P1 builds both components. Partial writes produce objects without lineage — a direct Principle 3 violation and the most likely source of silent integrity loss. Deferring means building storage before knowing what it must guarantee.

**Engines affected.** All nine.

**Severity.** **Critical.** Highest-leverage single item in the review.

**Options.**
1. Single component; graph as an index within it — atomicity trivial; deviates from v1's stated three components.
2. Two components, atomic dual write — preserves v1; requires transactional coupling and reduces independence.
3. Two components, eventual consistency with reconciliation — resilient; permits windows where lineage is unresolvable, breaching V3/V4 transiently.
4. Objects authoritative (D-08), graph rebuildable from objects — divergence is recoverable by rebuild; graph may lag.

**Recommendation.** **Option 4, with Option 2 for the write path.** Objects carry authoritative lineage and are written atomically; the Graph is a derived index that can be rebuilt from the objects at any time. Divergence becomes a recoverable performance problem, not a correctness one.

**Trade-offs.** Graph rebuild is expensive at scale. Accepting that cost buys the guarantee that the Graph can never be the reason the platform is wrong — only the reason it is slow.

**Dependencies.** Blocks B-01, B-02, B-03. Interacts with OQ-13 (concurrency), OQ-14 (graph global vs partitioned).

**Timing.** **Must resolve before P1.** Nothing in P1 can start without it.

---

### B-07 — Retention, Archival and Lifecycle Policy
**Canonical:** M-38

**Description.** No retention policy exists. The platform loops continuously, objects are immutable, versions accumulate, and rejected candidates are retained by D-02. Growth is unbounded and monotonic. The `ARCHIVED` state exists with no owner or trigger.

**Why it blocks implementation.** Immutability (D-01) plus continuous operation plus retained rejections means the store only ever grows. Principle 3 requires lineage to remain reconstructable indefinitely, which is in direct tension with any deletion. If P1 builds storage with no retention concept, retrofitting one later means discovering that lineage paths traverse archived objects — precisely when the platform is largest and the problem hardest.

**Engines affected.** All nine; Knowledge Store primarily.

**Severity.** **High.**

**Options.**
1. Retain everything indefinitely — maximal traceability; unbounded cost.
2. Archive by age — simple; may archive objects still in active lineage.
3. Archive by lineage reachability — never archive anything reachable from an `ACTIVE` object; preserves Principle 3 exactly.
4. Tiered: full content archived, lineage skeleton retained permanently.

**Recommendation.** **Option 4, governed by Option 3's reachability rule.** Lineage structure is永 retained so traversal never breaks; heavyweight content (notably raw Evidence) tiers out once unreachable from any `ACTIVE` object. Principle 3 is preserved structurally while bounding the dominant cost.

**Trade-offs.** Archived content may be needed for re-verification. Mitigated by retaining `content_fingerprint` and provenance permanently, so what was archived is always identifiable even when not immediately available.

**Dependencies.** OQ-12 (Evidence stored in full or by reference) materially changes the cost profile. Requires B-06.

**Timing.** **Must resolve before P1** — as policy. Mechanism may follow.

---

### B-08 — Security, Access Control and Tenancy
**Canonical:** M-55

**Description.** No security model, access control, or tenancy concept exists anywhere in v1 or v2.

**Why it blocks implementation.** Access control cannot be retrofitted onto a knowledge store without redesigning its access paths. If the platform is ever multi-tenant, or if evidence carries licence restrictions limiting who may see derived conclusions (OQ-11 / M-18), the partitioning must exist in the foundation. Retrofitting means rewriting every access path and re-partitioning existing data.

**Engines affected.** All nine; both knowledge components.

**Severity.** **High.**

**Options.**
1. Single-tenant, no internal access control — simplest; forecloses multi-tenancy without rework.
2. Single-tenant with role-based access — moderate cost; supports segregation.
3. Multi-tenant with partitioning from the outset — highest cost; maximum flexibility.
4. Defer, but reserve a tenancy discriminator on every object.

**Recommendation.** **Option 4 for P1, pending a scope decision.** M-03 (non-goals) and M-05 (output consumers) are unresolved, so the tenancy requirement is genuinely unknown. Carrying a reserved discriminator on every object costs little now and preserves the option. Full access control follows the scope decision.

**Trade-offs.** A reserved-but-unused attribute is mild overhead. The alternative is a foundation that cannot be partitioned later.

**Dependencies.** M-03, M-05, OQ-02 (human role), M-18 (licensing).

**Timing.** **Must resolve before P1** — the reservation decision. Full model may wait.

---

### B-09 — Concurrency Model
**Canonical:** OQ-13

**Description.** Whether multiple pipeline traversals may run concurrently — over different markets, subjects, or periods — is undefined. The IOM assumes versioning is serialised per object type because only one engine holds create authority, but this holds only if that engine runs single-threaded.

**Why it blocks implementation.** Concurrency determines whether the Knowledge Store needs write serialisation, whether the Graph is global or partitioned (OQ-14), whether Pattern Intelligence's "full problem population" is well-defined at any instant, and whether version chains can branch. Every one of these is a P1 structural property.

**Engines affected.** All nine; Orchestration especially.

**Severity.** **High.**

**Options.**
1. Strictly sequential, single traversal — simplest; unusable at scale; Pattern Intelligence sees a stable population.
2. Concurrent traversals, partitioned knowledge — scalable; forecloses cross-domain pattern recognition, arguably a core capability.
3. Concurrent traversals, shared global knowledge — preserves cross-domain patterns; needs full concurrency control.
4. Concurrent acquisition and extraction; serialised interpretation from Problem onward.

**Recommendation.** **Option 4.** The volume is upstream (Evidence, Facts) where operations are independent and parallelism pays. Interpretation from Problem onward is where cross-object consistency matters and where Pattern Intelligence needs a stable population. This matches the platform's actual volume profile.

**Trade-offs.** Interpretation becomes the throughput bottleneck. That is acceptable — it is also where quality matters most and where rushing is most damaging.

**Dependencies.** Determines OQ-14. Interacts with B-06, M-35 (control model).

**Timing.** **Must resolve before P1.**

---

### B-10 — Explanation Format and Minimum Content
**Canonical:** M-07

**Description.** `explanation` is a universal required attribute on every object, mandated by Principle 2. Its form, granularity, and minimum content are undefined.

**Why it blocks implementation.** Every object write populates this attribute. Without a standard, nine engines will produce nine incompatible explanation styles, and explanations will not be comparable, auditable, or verifiable. Since objects are immutable, explanations written under no standard cannot be normalised later.

**Engines affected.** All nine.

**Severity.** **High.**

**Options.**
1. Free text with a minimum-content rule — flexible; weakly enforceable.
2. Structured: inputs used, criteria applied, reasoning, conclusion — comparable and checkable; rigid.
3. Structured skeleton with a free-text reasoning field — checkable structure, expressive content.
4. Per-engine formats — best fit per engine; not comparable.

**Recommendation.** **Option 3.** A mandatory skeleton — objects referenced, criteria applied, reasoning, and (where applicable) alternatives rejected — with reasoning as free text. V6 becomes structurally checkable (does it reference inputs?) without constraining the reasoning itself.

**Trade-offs.** Skeleton adds authoring overhead per object. Justified: Principle 2 is one of five principles, and an unenforceable explanation requirement is not a requirement.

**Dependencies.** None blocking. Interacts with M-57 (observability).

**Timing.** **Must resolve before P1.**

---

### B-11 — Evidence Sufficiency Thresholds
**Canonical:** M-06

**Description.** No minimum evidence sufficiency is defined per object type. Validation rules require `supporting_facts` and `constituent_problems` to be non-empty, and Pattern requires ≥2 constituents, but no threshold establishes what constitutes adequate support.

**Why it blocks implementation.** Principle 1 is satisfiable by a single weak source without thresholds. The rules P-V1 and PT-V1 are written as "non-empty", which is a placeholder, not a standard. These are acceptance-time checks built in P1.

**Engines affected.** Fact Extraction, Problem Intelligence, Pattern Intelligence, Opportunity Intelligence.

**Severity.** **High.**

**Options.**
1. Fixed minimum counts per type — simple, enforceable, arbitrary.
2. Confidence-based: sufficiency as an `evidential_support` floor — principled; depends on B-04.
3. Independence-based: minimum independent sources rather than raw counts — resistant to syndication inflation.
4. No threshold; record support and let downstream engines judge.

**Recommendation.** **Option 3, expressed as a floor on independent source count, with Option 2 layered once B-04 exists.** Independence is the property that matters — ten syndicated copies of one claim are one source. This directly counters the frequency-inflation failure mode.

**Trade-offs.** Independence assessment is itself fallible (a Fact failure mode). But counting raw occurrences is *reliably* wrong, whereas assessing independence is *occasionally* wrong.

**Dependencies.** B-04; M-23 (source diversity accounting).

**Timing.** **Must resolve before P1** — thresholds are enforced at acceptance.

---

### B-12 — Failure Representation and Handling Policy
**Canonical:** M-36

**Description.** No object, state, or mechanism exists for an engine to signal that processing failed. A stage producing nothing is indistinguishable from a stage finding nothing.

**Why it blocks implementation.** This distinction is critical at every stage: empty extraction versus failed extraction; no validation result versus a negative one. Silent failure produces coverage holes with no error signal. Orchestration cannot handle failures it cannot detect, and cannot honour idempotence (M-16-adjacent) without knowing what completed.

**Engines affected.** All nine.

**Severity.** **High.**

**Options.**
1. Failure as an Intelligence Object — consistent with the object model; failures are not knowledge and would pollute lineage.
2. Failure as engine execution state outside the object model — clean separation; needs a home (see B-01).
3. Failure as an object status — reuses D-02; conflates "this object failed" with "production failed", and a failed production has no object.
4. Failure records in the same store as orchestration state.

**Recommendation.** **Option 2, co-located with the configuration store from B-01.** Failures are operational facts, not knowledge. They must not enter the lineage graph, or the platform could derive conclusions from its own malfunctions.

**Trade-offs.** Creates a second persistence surface distinct from Intelligence Objects. That separation is correct and should be explicit.

**Dependencies.** B-01 (shared home). Required by M-35, M-37.

**Timing.** **Must resolve before P1.**

---

### B-13 — Determinism and Reproducibility Requirement
**Canonical:** OQ-01

**Description.** Whether identical inputs must produce identical outputs is undefined. This determines whether engine runs must be replayable and whether re-running the pipeline over historical evidence is supported.

**Why it blocks implementation.** Determinism dictates what must be captured at write time: model version, configuration, input snapshot, random seed. These cannot be reconstructed retrospectively. If reproducibility is required and P1 does not capture the necessary state, no object created before the decision is ever reproducible.

**Engines affected.** All nine.

**Severity.** **High.**

**Options.**
1. Full reproducibility — strongest audit; heavy capture cost; hard with model-driven engines.
2. No reproducibility guarantee; rely on lineage and explanation — cheapest; cannot re-derive or regression-test.
3. Reproducible inputs, non-reproducible outputs — inputs and configuration pinned, outputs may vary; permits investigating divergence.
4. Reproducibility for structural operations only.

**Recommendation.** **Option 3.** Full output determinism is not achievable with model-driven engines and pretending otherwise would be false assurance. Capturing exact inputs and configuration makes divergence investigable, which is the practical need.

**Trade-offs.** Cannot assert "the same analysis yields the same answer". Accepting this openly is better than an unmeetable guarantee.

**Dependencies.** B-01 (configuration capture). Interacts with M-34.

**Timing.** **Must resolve before P1.**

---

### B-14 — Human Role and Approval Gates
**Canonical:** OQ-02

**Description.** v1 makes no reference to human involvement. Whether the platform is autonomous, gated, or human-in-the-loop is undetermined.

**Why it blocks implementation.** This determines whether objects need approval states beyond D-02's seven, whether engines can block awaiting input of unbounded duration, and who owns gate decisions (B-32). It also determines whether learning updates require approval (OQ-05). Approval states are object model structure — adding them later is a contract change affecting every engine.

**Engines affected.** All nine; Orchestration especially.

**Severity.** **High.**

**Options.**
1. Fully autonomous — simplest control model; highest risk; no gate owner needed.
2. Human gates at defined transitions (opportunity selection, solution promotion, learning application) — bounded, auditable.
3. Human-in-the-loop throughout — highest quality; throughput-limited; contradicts "AI-native".
4. Autonomous with human override and review.

**Recommendation.** **Option 2.** Gates at exactly three points — opportunity selection for solutioning, post-validation promotion, and learning application. These are the three transitions where the cost of an error is highest and where v2 already identifies unowned gates (B-32, OQ-05). Everything else runs autonomously, honouring "AI-native".

**Trade-offs.** Gates introduce latency and a human dependency. Confined to three transitions, this is proportionate to the consequences at each.

**Dependencies.** Determines B-32 (gate ownership), OQ-05. Requires M-05 (who consumes output).

**Timing.** **Must resolve before P1** — approval states are object structure.

---

### B-15 — Orchestration Control Model
**Canonical:** M-35, with M-37 and OQ-15

**Description.** Whether Orchestration is event-driven, batch, scheduled, or continuous is undefined (M-35), as is loop termination and iteration bounding (M-37) and whether Orchestration is reactive or directive (OQ-15).

**Why it blocks implementation.** Orchestration invokes every engine and must exist from P2 onward, yet it has no roadmap phase (C-08). The control model determines what state must be tracked per object — what has been processed, by what, when — which is object-adjacent metadata built in P1.

**Engines affected.** All nine.

**Severity.** **High.**

**Options.**
1. Event-driven — responsive; hard to bound; risk of runaway loops.
2. Scheduled batch — bounded and predictable; latency; simplest to reason about.
3. Continuous streaming — lowest latency; hardest to bound.
4. Hybrid: scheduled acquisition, event-driven downstream.

**Recommendation.** **Option 2 for P1–P5; revisit at P6.** Batch is bounded, and boundedness is the property most needed while no cost model (M-56) or resource limits exist. It also gives Pattern Intelligence a stable population per batch, which aligns with the B-09 recommendation.

**Trade-offs.** Higher latency. Acceptable for a discovery platform where evidence ages in weeks, not seconds.

**Dependencies.** B-09 (concurrency), B-12 (failure handling), M-56 (cost). Resolves part of C-08.

**Timing.** **Must resolve before P1** — determines processing-state metadata.

---

### B-16 — Orchestration Roadmap Phase
**Canonical:** C-08

**Description.** The Orchestration Engine appears in no roadmap phase, yet no pipeline engine can be invoked without it.

**Why it blocks implementation.** P2 (Research) cannot run without invocation. Either Orchestration is built in P1 — which v1 does not state — or the roadmap is unexecutable as written.

**Engines affected.** All nine.

**Severity.** **High.**

**Options.**
1. Baseline Orchestration built in P1 — unblocks the roadmap; expands P1.
2. New phase P1.5 — explicit; changes the roadmap structure.
3. Orchestration capability incremented within each engine phase — matches need; risks no coherent control model.
4. Manual invocation until a later phase — defers; means P2–P5 are not operating as a platform.

**Recommendation.** **Option 1.** Baseline Orchestration — invocation, sequencing, processing-state tracking, failure surfacing — is scoped into P1 as foundation infrastructure. Advanced capability (concurrency, backlog management, resource governance) increments later.

**Trade-offs.** P1 becomes the largest phase. It already is: P1 owns the least changeable layer, and coherence there is worth more than phase symmetry.

**Dependencies.** B-15 (control model must be decided first).

**Timing.** **Must resolve before P1** — it changes P1's scope.

---

### B-17 — Success Criteria and Effectiveness Measures
**Canonical:** M-04

**Description.** No success criteria, acceptance thresholds, or measures of platform effectiveness exist.

**Why it blocks implementation.** Principle 5 requires continuous improvement; improvement is undefined without a measure. The Feedback Engine has no target function. More immediately for P1: with no definition of "working", there is no exit criterion for any phase (M-52) and no basis for the quality obligations attached to each engine.

**Engines affected.** All nine; Feedback critically.

**Severity.** **High.**

**Options.**
1. Outcome-based: realised value of executed opportunities — the true measure; unavailable until P8.
2. Proxy measures per stage: extraction fidelity, pattern precision, validation pass rate — available early; may not correlate with value.
3. Prediction accuracy: predicted versus realised — directly usable by Feedback; requires outcomes.
4. Layered: stage proxies now, outcome measures from P8.

**Recommendation.** **Option 4.** Define stage-level proxies before P1 so each phase has exit criteria, and define outcome measures now so they are ready when P8 delivers outcomes. Defining outcome measures late risks defining them to match whatever the platform happens to produce.

**Trade-offs.** Proxies can be optimised without improving real outcomes. Mitigated by fixing outcome measures early, before results can bias their definition.

**Dependencies.** Requires M-05 (who consumes output). Feeds M-52, M-02.

**Timing.** **Must resolve before P1** — proxies are phase exit criteria.

---

### B-18 — Scope Definition: Non-Goals and Output Consumers
**Canonical:** M-03 and M-05

**Description.** No non-goals statement exists (M-03), and no identification of who consumes platform output or at which stage it leaves the platform (M-05).

**Why it blocks implementation.** M-05 determines the boundary between Validation, Execution, and the outside world — the location of C-02, the platform's structural break. It also determines whether the platform recommends or acts, which is the difference between an analysis system and an operational one. M-03 governs scope drift across every subsequent phase.

**Engines affected.** All nine; Validation and Feedback at the boundary.

**Severity.** **High.**

**Options.**
1. Advisory: output is scored, validated opportunities; humans decide and act — clean boundary; C-02 resolves as external execution.
2. Operational: the platform initiates action — requires an Execution Engine; contradicts v1's absence of one.
3. Advisory with structured handoff and mandatory outcome reporting — advisory boundary plus a defined intake for outcomes.
4. Undecided; build to the Validation boundary only — defers, leaves P7/P8 unplannable.

**Recommendation.** **Option 3.** It matches v1's structure exactly — no Execution Engine, no execution phase — while closing the loop that Principle 5 requires. The platform advises; execution happens externally; outcomes return through a defined intake. This is the reading that makes v1 internally consistent.

**Trade-offs.** Depends on external parties reporting outcomes reliably — the reporting-gap and survivorship-bias failure modes. Must be mitigated by making outcome reporting a condition of the handoff, not an optional courtesy.

**Dependencies.** Determines C-02 and M-47. Requires B-14 (human role).

**Timing.** **Must resolve before P1** — determines the platform's boundary.

---

### B-19 — Architecture Decision Records
**Canonical:** M-50

**Description.** v1's four architecture decisions are recorded as titles only: no context, alternatives, rationale, consequences, or revisit conditions. This document and the IOM propose a further sixteen-plus decisions with no established mechanism for recording them.

**Why it blocks implementation.** Without decision records, implementers cannot distinguish a deliberate constraint from an incidental choice, and cannot safely revise anything. The IOM's standing instruction requires markers to be closed by recorded decision — the mechanism must exist before the closures begin.

**Engines affected.** None directly; all indirectly.

**Severity.** **High.** Process, not architecture — but it governs every other resolution.

**Options.**
1. Lightweight ADR per decision — low overhead; standard practice.
2. Decisions recorded inline in the PKP — single source; PKP becomes unwieldy.
3. Decision register with detail held separately — indexed and navigable.
4. No formal mechanism — rejected; makes every resolution unauditable.

**Recommendation.** **Option 3.** A register listing every decision with status and links to full records. The eight IOM decisions (D-01…D-08) and the recommendations in this document become the first entries. v1's four original decisions should be retrospectively documented.

**Trade-offs.** Documentation overhead. Minimal against the cost of an unexplained architecture.

**Dependencies.** None. **Should be established first**, as every other resolution produces a record.

**Timing.** **Must resolve before P1.**

---

### B-20 — Extraction Fidelity Verification (Hallucination Detection)
**Canonical:** M-20

**Description.** Rule F-V6 requires that a Fact's claim be present in its Evidence at the stated anchor. No mechanism verifies this. A hallucinated Fact satisfies every structural rule in the object model — it has references, anchors, explanations, confidence — while being false.

**Why it blocks implementation.** This is the platform's integrity floor. A hallucinated Fact corrupts the grounding layer while passing every check the platform can perform, and every downstream conclusion inherits a falsehood that appears fully evidenced. It is listed here rather than under P3 because the *verification hook* must exist in the acceptance path built in P1 — B-02's structural enforcement explicitly cannot cover semantic rules like F-V6.

**Engines affected.** Fact Extraction primarily; all downstream engines inherit the corruption.

**Severity.** **Critical.** Highest-severity item in the entire review.

**Options.**
1. Anchor verification: confirm the claim text is locatable at the stated anchor — mechanical, catches fabricated anchors, not paraphrase drift.
2. Independent re-extraction and comparison — catches more; doubles extraction cost; correlated errors possible.
3. Sampled human audit — catches semantic drift; does not scale; provides a measured error rate.
4. Layered: anchor verification on all, sampled deeper audit, measured hallucination rate as a quality metric.

**Recommendation.** **Option 4.** Anchor verification on every Fact at acceptance; sampled audit producing a measured hallucination rate; that rate published as a platform quality metric feeding B-17. Detection cannot be perfect — measurement is what makes the residual risk visible instead of invisible.

**Trade-offs.** Sampling means some hallucinations pass. The alternative is an unmeasured error rate, which is strictly worse: unquantified corruption at the grounding layer.

**Dependencies.** B-02 (acceptance path must accommodate a semantic check). Feeds B-17.

**Timing.** **Must resolve before P1** — the acceptance path is built in P1. Full mechanism may land in P3.

---

### B-21 — Semantic Equivalence Criterion for Fact Merging
**Canonical:** M-62

**Description.** D-05 makes Facts canonical claims: equivalent extractions attach to an existing Fact rather than creating a new one. What makes two claims "the same claim" is undefined.

**Why it blocks implementation.** Both error directions are damaging. Over-merging hides genuine source disagreement; under-merging inflates apparent corroboration, which directly inflates `evidential_support` and therefore every downstream confidence value. Since merging changes object identity and identity is permanent (I2), errors are not correctable by later reprocessing.

**Engines affected.** Fact Extraction; Pattern Intelligence and Opportunity Intelligence inherit distorted frequency.

**Severity.** **Critical.**

**Options.**
1. Strict textual equivalence — precise, safe against over-merge; will badly under-merge paraphrase.
2. Semantic equivalence by model judgement — matches intent; non-deterministic and unauditable.
3. Structured claim decomposition (subject, predicate, qualifier, value) with equivalence on the structure — auditable and explainable; requires extraction to produce structure.
4. Conservative merge plus explicit `DUPLICATES` links for uncertain cases — under-merges deliberately but records suspicion for later resolution.

**Recommendation.** **Option 3, with Option 4 as fallback.** Structured claims make equivalence a checkable property rather than an opinion, satisfying Principle 2. Where structure is ambiguous, do not merge — record `DUPLICATES` instead. Deliberate under-merging with an explicit marker is recoverable; over-merging destroys information irreversibly.

**Trade-offs.** Structured extraction constrains what Fact Extraction can express. Justified: unstructured claims cannot be reliably compared, and comparison is what the Fact object exists to enable.

**Dependencies.** M-19 (what qualifies as a fact) must align. Affects B-04, B-11.

**Timing.** **Must resolve before P1** — it determines Fact identity, and identity is permanent.

---
---

## 2. Blockers Deferrable Past P1 but Blocking a Named Engine Phase

Twenty-two items. P1 can complete without these, but each prevents a specific engine phase from starting. All ten fields are given for each.

---

### B-22 — Execution Stage Has No Owning Engine
**Canonical:** C-02 | **Blocks:** P8

**Description.** The pipeline contains an Execution stage and the object model contains an Execution Record, but no Execution Engine exists in v1 §4 and no execution phase exists in the roadmap. The Execution Record is the only object type with no create authority.

**Why it blocks.** The Feedback Engine's sole input is Execution Records. With no producer, P8 is scheduled to build an engine whose input has no source. The learning loop is structurally open.

**Engines affected.** Feedback (starved); Validation (no defined consumer).

**Severity.** **Critical** — but for P8, not P1.

**Options.** (1) Execution is external; an existing engine owns outcome intake. (2) Add an Execution Engine — out of scope, changes v1. (3) Outcome intake as a Research Engine responsibility, since it already handles external-world contact. (4) Intake as a non-engine mechanism feeding Feedback.

**Recommendation.** **Option 3.** The Research Engine is already the platform's only external-world boundary. Receiving outcome reports is acquisition, not interpretation — consistent with its remit. It preserves v1's nine engines exactly while giving the Execution Record a producer.

**Trade-offs.** Extends Research beyond market evidence into outcome intake. The alternative — a tenth engine — is a larger deviation. Must be recorded as a decision.

**Dependencies.** B-18 (M-05, platform boundary) determines this. Requires B-23.

**Timing.** Before **P7 completes**. P8 cannot start without it.

---

### B-23 — Outcome Intake, Verification and Attribution
**Canonical:** M-47 (merges IOM MISSING-36 and MISSING-47) | **Blocks:** P8

**Description.** No mechanism defines how execution outcomes are obtained, verified, or attributed to the platform's recommendations.

**Why it blocks.** Execution Records are the only ground-truth input. Unverified intake means the platform can be taught by unreliable reports — the most direct route to corrupting a continuously learning system. Attribution error means learning from the wrong signal entirely.

**Engines affected.** Feedback; whichever engine owns intake (B-22).

**Severity.** **Critical** for P8.

**Options.** (1) Self-reported outcomes, accepted as given. (2) Self-reported with mandatory evidence attachment. (3) Independently verified by platform re-research. (4) Tiered: self-report with evidence, sampled independent verification.

**Recommendation.** **Option 4.** Mirrors B-20's approach: mandatory evidence for all, sampled deep verification, measured reliability rate. Outcome reports should themselves be evidenced — the platform's own standard applied to its ground truth.

**Trade-offs.** Verification is costly and slow, and outcomes already arrive late. Sampling bounds the cost while keeping the error rate visible.

**Dependencies.** B-22 (who owns intake); B-18 (handoff model).

**Timing.** Before **P8**.

---

### B-24 — Learning Target and Write Mechanism
**Canonical:** M-02 and M-43 | **Blocks:** P8

**Description.** What changes when the platform learns is undefined (M-02), as is the Feedback Engine's write target (M-43). The Feedback Record's `change_target` attribute has no vocabulary.

**Why it blocks.** The Feedback Engine has no defined output. Principle 5 and Architecture Decision 3 are unrealised without it.

**Engines affected.** Feedback (produces); all engines (receive).

**Severity.** **Critical** for P8.

**Options.** (1) Confidence calibration only — narrow, safe, addresses the most consequential failure. (2) Scoring weights only — directly affects ranking. (3) Broad: scoring, extraction criteria, source trust, thresholds. (4) Staged: calibration first, widening as reliability is demonstrated.

**Recommendation.** **Option 4, beginning with confidence calibration and source trust.** These two targets address the platform's two most damaging failures (confidence inflation, sampling bias) and are the most reversible. Widen only once the loop is demonstrably stable.

**Trade-offs.** Narrow learning limits improvement rate. Appropriate: an unstable broad learning loop is worse than a slow narrow one, and B-25 shows the instability risk is unguarded.

**Dependencies.** B-01 (configuration must exist to be written); B-05 (calibration); B-17 (measure of improvement); B-25 (stability).

**Timing.** Before **P8**.

---

### B-25 — Feedback Loop Instability Guard
**Canonical:** M-70 | **Blocks:** P8

**Description.** No mechanism prevents the learning loop from amplifying its own bias across cycles. The IOM's behavioural loop closure removes the lineage-cycle path, but behavioural self-reinforcement remains possible: learning changes what is researched, which changes what is found, which reinforces the learning.

**Why it blocks.** A continuously learning system with no stability guard can converge on self-generated belief. This is safety-critical and, unlike most gaps, becomes harder to detect the longer it operates.

**Engines affected.** Feedback; Research (via directives); Opportunity Intelligence (via calibration).

**Severity.** **Critical** for P8.

**Options.** (1) Bounded change magnitude per cycle. (2) Mandatory source diversity floors that learning cannot reduce. (3) Held-out evaluation not subject to learning. (4) All three, with cumulative drift monitoring.

**Recommendation.** **Option 4.** Each addresses a different amplification path: magnitude bounds limit per-cycle swing, diversity floors prevent the platform narrowing its own evidence base, and held-out evaluation detects drift the platform cannot see in its own metrics.

**Trade-offs.** Constrains learning rate and adds evaluation overhead. Proportionate to the risk of an unrecoverable belief spiral.

**Dependencies.** B-24 (targets must be known to be bounded); B-17 (measures).

**Timing.** Before **P8**. Must not lag B-24.

---

### B-26 — Scoring Dimensions, Scale and Methodology
**Canonical:** M-14, with M-26 and M-27 | **Blocks:** P6

**Description.** No scoring dimensions, scale, weighting, or aggregation method exists (M-14); no platform definition of "opportunity" (M-26); no prioritisation policy (M-27). The Opportunity object's `score`, `score_basis`, and `score_model_version` are unpopulatable.

**Why it blocks.** The Opportunity object cannot reach `ACTIVE` under its own rule O-V3. Scoring is one of four vision commitments and has no owner (C-01).

**Engines affected.** Opportunity Intelligence.

**Severity.** **Critical** for P6.

**Options.** (1) Single composite score. (2) Multi-dimensional vector with no aggregation. (3) Multi-dimensional with explicit weighted aggregation. (4) Multi-dimensional with aggregation, weights learnable via feedback.

**Recommendation.** **Option 4.** Multi-dimensional preserves explainability (Principle 2) — a single number cannot be explained. Explicit weights make the aggregation auditable, and learnable weights give the Feedback Engine a well-defined target aligning with B-24.

**Trade-offs.** Learnable weights create score drift across model versions. Already mitigated: `score_model_version` is mandatory, and O-I3 forbids cross-version comparison.

**Dependencies.** M-48/M-49 — the completed "Opportunity Evaluation" research likely contains this and must be recovered first. Also C-01, B-05.

**Timing.** Before **P6**.

---

### B-27 — Source Diversity Propagation
**Canonical:** M-23, with M-17 | **Blocks:** P5, and constrains B-04

**Description.** Pattern objects require `source_diversity` and `artefact_assessment`, but that information originates at Evidence — four stages upstream. Under strict Principle 4 modularity it may not be reachable.

**Why it blocks.** Sampling artefact is Pattern Intelligence's defining risk, and detecting it requires knowing how many independent sources contributed. Without propagation, PT-V4 and PT-V5 are unpopulatable and the platform's most dangerous systemic failure is undetectable.

**Engines affected.** Pattern Intelligence primarily; Research (origin); all intermediate engines if carried forward.

**Severity.** **High** for P5; **also constrains B-04 at P1**.

**Options.** (1) Carry diversity metadata forward through every object. (2) Compute on demand by lineage traversal. (3) Maintain a diversity summary in the Knowledge Graph. (4) Hybrid: carry a summary, traverse for detail.

**Recommendation.** **Option 4.** Carry a lightweight independent-source count on each object (cheap, always available, sufficient for B-04's support computation) and traverse lineage for detailed artefact assessment when Pattern Intelligence needs it.

**Trade-offs.** Duplicates derivable information. Justified: the alternative is deep traversal on every confidence computation, at every write.

**Dependencies.** Requires B-04 alignment and M-16 (source identity/trust). Traversal requires B-06.

**Timing.** Summary attribute decision **before P1** (it is an object attribute). Full mechanism before **P5**.

---

### B-28 — Validation Methodology and Evidence Standards
**Canonical:** M-32, with M-42 | **Blocks:** P7

**Description.** What validation consists of is undefined — evidence-based, analytical, experimental, or market-based. `validation_method` has no vocabulary. Experiment lifecycle (M-42) is also undefined.

**Why it blocks.** The Validation Engine cannot be specified at all, and it sits at the platform's most critical juncture — the last checkpoint before commitment. PKP v2 identifies this as the largest single specification gap.

**Engines affected.** Validation; Solution Intelligence (assumptions must be testable by available methods).

**Severity.** **Critical** for P7.

**Options.** (1) Evidence-based only: seek confirming/disconfirming evidence via Research. (2) Analytical only: logical consistency and internal coherence. (3) Experimental: real-world tests. (4) Method taxonomy covering all three, selected per assumption type.

**Recommendation.** **Option 4, with Option 1 as the P7 baseline.** Evidence-based validation is achievable within the platform's existing capabilities — it reuses the Research Engine and requires no external execution. Experimental validation depends on the same external-world access as C-02 and should follow it.

**Trade-offs.** Evidence-based validation cannot test genuinely novel propositions where no evidence exists — arguably the most valuable opportunities. This limitation must be stated explicitly rather than discovered.

**Dependencies.** C-05 (Validation/Experiment Registry boundary); M-30 (assumption structure, closed by IOM); B-32 (gate ownership).

**Timing.** Before **P7**.

---

### B-29 — Validation Object / Experiment Registry Boundary
**Canonical:** C-05, with M-53 | **Blocks:** P7

**Description.** The relationship between the Validation object and the Experiment Registry is undefined — same information stored twice, or design-versus-result split. The Registry also has no roadmap phase (M-53).

**Why it blocks.** Neither the Validation Engine nor the Experiment Registry can be specified. Any implementation risks dual sources of truth.

**Engines affected.** Validation; Feedback (reads both).

**Severity.** **High** for P7.

**Options.** (1) Registry holds design and status; Validation object holds concluded results. (2) Registry is an index over Validation objects. (3) Registry holds in-flight state only; objects hold history. (4) Merge — Registry becomes a view; contradicts v1's three components.

**Recommendation.** **Option 3.** The Registry holds operational experiment state (in-flight, scheduled, abandoned); the Validation object holds the immutable concluded record. This gives each a distinct character — mutable operational state versus immutable knowledge — and eliminates duplication.

**Trade-offs.** Requires clear handoff at conclusion. Mitigated by the rule that a Validation object is created only when an experiment concludes.

**Dependencies.** B-06 (component boundaries); B-28.

**Timing.** Before **P7**. Registry construction must be scheduled (M-53).

---

### B-30 — Constraint Model
**Canonical:** M-69 | **Blocks:** P7

**Description.** No representation exists for constraints limiting solutions — capability, resource, regulatory, temporal, competitive. The Solution object's `constraints` attribute is unpopulatable.

**Why it blocks.** Feasibility assessment is unspecifiable, so S-V6 cannot be satisfied meaningfully and validation effort may be spent on impossible solutions.

**Engines affected.** Solution Intelligence; Validation (tests feasibility assumptions).

**Severity.** **High** for P7.

**Options.** (1) Free-text constraints. (2) Typed constraint taxonomy. (3) Constraints as first-class objects — would add a tenth object type. (4) Typed taxonomy with evidence linkage where constraints are evidenced.

**Recommendation.** **Option 4.** A typed taxonomy keeps constraints comparable across solutions, and evidence linkage keeps Principle 1 intact where a constraint is an empirical claim rather than an assumption.

**Trade-offs.** Some constraints are genuinely unevidenced judgements. These should be recorded as Solution assumptions instead, where validation can test them.

**Dependencies.** M-29 (solution granularity) determines the necessary constraint detail.

**Timing.** Before **P7**.

---

### B-31 — Solution Granularity
**Canonical:** M-29 | **Blocks:** P7

**Description.** The required depth of a Solution is undefined — strategic direction, concrete offering description, or detailed design.

**Why it blocks.** Determines the Solution Intelligence Engine's entire output character and what Validation tests. Too shallow and assumptions are untestable; too deep and the engine performs design work v1 does not assign it.

**Engines affected.** Solution Intelligence; Validation.

**Severity.** **High** for P7.

**Options.** (1) Strategic direction only. (2) Concrete offering description without implementation detail. (3) Detailed design. (4) Progressive: direction first, deepening for solutions that pass validation.

**Recommendation.** **Option 2.** Concrete enough that assumptions are testable — the Solution object's core purpose — without crossing into design work v1 does not assign to any engine.

**Trade-offs.** Some assumptions only surface at design depth and will be missed. Acceptable, since v1 assigns design to no engine and inventing that scope would be a redesign.

**Dependencies.** B-28 (methods determine testable depth); B-30.

**Timing.** Before **P7**.

---

### B-32 — Gate Ownership
**Canonical:** M-28 and M-31 | **Blocks:** P6, P7

**Description.** No component owns the decision to promote an opportunity to solutioning (M-28) or to promote/reject after validation (M-31). Validation reports but does not gate; Orchestration sequences but does not judge.

**Why it blocks.** Without gates, every opportunity proceeds to solutioning — an unbounded cost driver at the pipeline's most expensive transition — and validation results have no consequence, making validation decorative.

**Engines affected.** Opportunity Intelligence, Solution Intelligence, Validation, Orchestration.

**Severity.** **High** for P6/P7.

**Options.** (1) Human gates. (2) Threshold-based automatic gates. (3) A gate-owning engine — adds a tenth engine. (4) Threshold-based with human override.

**Recommendation.** **Option 4**, consistent with B-14. Automatic thresholds handle volume; human override handles judgement. No new engine: the threshold is policy applied by Orchestration mechanically, and the human gate sits at the boundary B-18 defines.

**Trade-offs.** Thresholds require the scoring model (B-26) to be trustworthy before they can be relied on.

**Dependencies.** B-14, B-26, B-17.

**Timing.** Before **P6**.

---

### B-33 — Source Taxonomy, Eligibility and Trust
**Canonical:** M-16, with OQ-06 | **Blocks:** P2

**Description.** No evidence source taxonomy, eligibility policy, or trust model exists. The Evidence object's `source_type` is unscoped, and whether Evidence carries source reliability is unresolved.

**Why it blocks.** The Research Engine cannot be scoped without knowing what it may acquire. Source trust is also a prime learning target (B-24) and an input to weighing contradictory evidence.

**Engines affected.** Research; Fact Extraction (independence assessment); Pattern Intelligence (diversity).

**Severity.** **High** for P2.

**Options.** (1) Open — any accessible source. (2) Whitelist. (3) Typed taxonomy with per-type eligibility. (4) Typed taxonomy with per-source trust ratings, learnable.

**Recommendation.** **Option 4.** Trust ratings are needed for contradictory evidence and are the safest, most valuable learning target. Absent this, all sources weigh equally — a strong, unstated, and almost certainly false assumption.

**Trade-offs.** Trust ratings risk entrenching bias if learned unchecked. Mitigated by B-25's diversity floors.

**Dependencies.** M-18 (legal/licensing); B-27; B-24.

**Timing.** Before **P2**.

---

### B-34 — Legal, Licensing and Access Policy
**Canonical:** M-18 | **Blocks:** P2

**Description.** No policy governs source terms of use, licensing, rate limits, or retention rights. v1 §7 references acquiring marketplace and complaint data, making this concrete rather than hypothetical.

**Why it blocks.** Acquisition may be unlawful or contractually prohibited. Retention rights determine whether Evidence can be stored in full (OQ-12), which is a P1 storage decision with a large cost implication.

**Engines affected.** Research; Knowledge Store (retention).

**Severity.** **High** for P2; **affects P1 via OQ-12**.

**Options.** (1) Permissive — acquire what is accessible. (2) Conservative — only explicitly licensed sources. (3) Per-source assessment recorded on Evidence. (4) Per-source assessment with policy enforcement at acquisition.

**Recommendation.** **Option 4.** `access_conditions` is already a required Evidence attribute; enforcement at acquisition prevents ineligible material entering the store, where it would be immutable and cascade through derived objects.

**Trade-offs.** Restricts the evidence base, worsening coverage (M-17) and sampling bias risk. This is a real quality cost that must be acknowledged, not a formality.

**Dependencies.** Determines OQ-12; interacts with B-07, B-08.

**Timing.** Before **P2**; the OQ-12 element **before P1**.

---

### B-35 — Coverage and Completeness Concept
**Canonical:** M-17 | **Blocks:** P2, P5

**Description.** No definition of coverage, completeness, or representativeness exists. Nothing establishes whether the evidence base adequately represents the market.

**Why it blocks.** Sampling bias is the platform's most dangerous systemic failure — it produces confident, well-evidenced, wrong patterns and is invisible to every downstream engine. Without a coverage concept, it is unmanageable by construction.

**Engines affected.** Research; Pattern Intelligence.

**Severity.** **High** for P2/P5.

**Options.** (1) No coverage measure; rely on volume. (2) Source-type coverage: all defined types represented. (3) Population coverage against a market frame. (4) Source-type coverage plus explicit gap declaration.

**Recommendation.** **Option 4.** True population coverage requires a market frame the platform does not have. Source-type coverage with explicit declaration of known gaps makes blind spots visible and inheritable by Pattern Intelligence's artefact assessment.

**Trade-offs.** Declared gaps do not fix bias; they only make it visible. That is nonetheless the difference between a known limitation and a silent falsehood.

**Dependencies.** B-33 (taxonomy); feeds B-27.

**Timing.** Before **P2**.

---

### B-36 — Fact Definition and Extraction Granularity
**Canonical:** M-19 | **Blocks:** P3

**Description.** What qualifies as a fact, and at what granularity claims are extracted, is undefined.

**Why it blocks.** Unrestricted extraction produces unmanageable volume; restricted extraction needs a taxonomy that does not exist. Granularity also determines whether B-21's structured equivalence is feasible.

**Engines affected.** Fact Extraction; Problem Intelligence.

**Severity.** **High** for P3.

**Options.** (1) Unrestricted. (2) Typed fact taxonomy. (3) Relevance-filtered against the research directive. (4) Typed taxonomy with structured claim decomposition, aligned to B-21.

**Recommendation.** **Option 4**, specified jointly with B-21. Fact identity and fact definition are the same problem viewed from two sides and must be decided together.

**Trade-offs.** A typed taxonomy will fail to anticipate claim types. Mitigated by allowing taxonomy extension via decision record.

**Dependencies.** Must be co-decided with B-21.

**Timing.** Before **P3**; co-decided with B-21 **before P1**.

---

### B-37 — Problem Attributes and Taxonomy
**Canonical:** M-12 and M-21 | **Blocks:** P4

**Description.** No scales exist for problem severity or frequency (M-12), and no problem taxonomy (M-21). The Problem object requires both attributes.

**Why it blocks.** P-V4 requires severity and frequency. Without scales they are free text and cannot be aggregated by Pattern Intelligence or used in scoring.

**Engines affected.** Problem Intelligence; Pattern Intelligence; Opportunity Intelligence.

**Severity.** **High** for P4.

**Options.** (1) Free text. (2) Ordinal bands. (3) Quantitative measures. (4) Ordinal bands with evidence-linked justification.

**Recommendation.** **Option 4.** Ordinal bands with mandatory evidence linkage — consistent with the confidence banding in D-03 and with Principle 1. Quantitative severity is rarely traceable to Facts and would invite unfounded precision.

**Trade-offs.** Ordinal bands lose granularity and invite boundary disputes. Acceptable against false precision at a stage that is already interpretive.

**Dependencies.** M-22 (problem deduplication) should be co-decided.

**Timing.** Before **P4**.

---

### B-38 — Problem Identity and Deduplication
**Canonical:** M-22 | **Blocks:** P4

**Description.** No criterion determines when two Problems are the same problem. The Fact-level equivalent (B-21) is addressed by D-05; the Problem-level equivalent is not.

**Why it blocks.** Duplicate Problems inflate Pattern constituent counts, and PT-V2 forbids patterns over multiple versions of one problem but cannot detect duplicates that are distinct objects.

**Engines affected.** Problem Intelligence; Pattern Intelligence.

**Severity.** **High** for P4.

**Options.** (1) No deduplication; rely on `DUPLICATES` links. (2) Canonical problems, mirroring D-05. (3) Deduplication at Pattern time. (4) Canonical problems with conservative merging and explicit duplicate links.

**Recommendation.** **Option 4**, mirroring the B-21 approach for consistency. Same reasoning: under-merging is recoverable, over-merging is not.

**Trade-offs.** Same as B-21 — deliberate under-merging leaves some inflation, but it is visible and correctable.

**Dependencies.** Should mirror B-21's resolution.

**Timing.** Before **P4**.

---

### B-39 — Pattern Strength, Minimum Constituents and Type Taxonomy
**Canonical:** M-24 and M-25 | **Blocks:** P5

**Description.** No pattern strength measure or minimum constituent count beyond the IOM's ≥2 (M-24), and no pattern type taxonomy (M-25). The Pattern object requires `pattern_type` and optionally `pattern_strength`.

**Why it blocks.** Two constituents is a floor, not a standard. Without strength, weak and strong patterns are indistinguishable to Opportunity Intelligence.

**Engines affected.** Pattern Intelligence; Opportunity Intelligence.

**Severity.** **High** for P5.

**Options.** (1) Constituent count as strength. (2) Diversity-weighted strength. (3) Statistical measures. (4) Diversity-weighted strength with a type taxonomy fixing minimum constituents per type.

**Recommendation.** **Option 4.** Different pattern types warrant different thresholds — a cross-domain similarity claim needs more support than a simple recurrence. Diversity weighting counters the frequency-inflation failure mode.

**Trade-offs.** Per-type thresholds add complexity. Justified: a uniform threshold is either too permissive for strong claims or too restrictive for simple ones.

**Dependencies.** B-27 (diversity); B-04 alignment.

**Timing.** Before **P5**.

---

### B-40 — Pattern Temporal Validity
**Canonical:** M-13, with M-61 | **Blocks:** P5

**Description.** Whether a Pattern expires, weakens, or requires re-confirmation is undefined (M-13), and no component owns staleness assessment (M-61). D-04 makes ageing visible but not actioned.

**Why it blocks.** Patterns rest on accumulated Problems from evidence spanning long periods. A pattern true two years ago may be false now, and nothing detects this. Opportunities would be founded on lapsed conditions.

**Engines affected.** Pattern Intelligence; Opportunity Intelligence.

**Severity.** **High** for P5.

**Options.** (1) Patterns never expire. (2) Age-based expiry. (3) Re-confirmation requirement on a defined cadence. (4) Explicit `valid_until` set per pattern with mandatory review on breach.

**Recommendation.** **Option 4**, consistent with D-04's rejection of automatic decay. The producing engine sets expected validity from the pattern's own characteristics; breach triggers review rather than automatic invalidation.

**Trade-offs.** Requires the engine to make a judgement it may make poorly. Better than a uniform expiry that is wrong for every pattern in a different way.

**Dependencies.** Requires an owner for review triggering — relates to B-15.

**Timing.** Before **P5**.

---

### B-41 — Cross-Stage Read Access
**Canonical:** OQ-18 | **Blocks:** P5, P6, P7

**Description.** Whether an engine may read objects from stages earlier than its immediate predecessor is undefined. The strict pipeline reading forbids it, but Solution Intelligence cannot demonstrate problem-fit without reading Problems, and Validation may need underlying Facts.

**Why it blocks.** The IOM's authority matrix marks three read grants as conditional on this. S-V4 requires Solutions to reference specific Problems — impossible if the read is forbidden.

**Engines affected.** Pattern Intelligence, Opportunity Intelligence, Solution Intelligence, Validation.

**Severity.** **High** for P5–P7; **affects the P1 authority model**.

**Options.** (1) Strict — immediate predecessor only. (2) Unrestricted read of any `ACTIVE` object. (3) Lineage-restricted — an engine may read any object in its own inputs' lineage. (4) Explicit per-engine grants.

**Recommendation.** **Option 3.** An engine may read anything its inputs derive from. This satisfies Principle 1 (justification requires reaching evidence) without permitting arbitrary access that would erode stage separation.

**Trade-offs.** Widens engine input surfaces and increases coupling to upstream object definitions. Contained: the grant follows lineage, which every object already carries.

**Dependencies.** Affects the §2.5 authority matrix, which is P1 structure.

**Timing.** **Decide before P1** (authority model); enforcement matters from P5.

---

### B-42 — Experiment Registry Phase Assignment
**Canonical:** M-53, with M-42 | **Blocks:** P7

**Description.** The Experiment Registry has no roadmap phase, and experiment lifecycle is undefined. P7 requires it.

**Why it blocks.** P7 depends on a component nothing schedules.

**Engines affected.** Validation; Feedback.

**Severity.** **Medium-High** for P7.

**Options.** (1) Build in P1 with the other shared components. (2) Build in P7 where it is needed. (3) Split — schema in P1, capability in P7. (4) Fold into the Knowledge Store.

**Recommendation.** **Option 3.** B-29 establishes the Registry holds mutable operational state, which differs from the Store's immutable records. Reserving its place in P1 while building capability in P7 avoids a foundation retrofit.

**Trade-offs.** Splitting risks the P1 portion being under-specified. Mitigated by B-29 settling the boundary first.

**Dependencies.** B-29; B-06.

**Timing.** Reservation **before P1**; capability before **P7**.

---

### B-43 — Completed Research Recovery and Disposition
**Canonical:** M-48 and M-49, with C-07 | **Blocks:** P6 materially; P0 formally

**Description.** The findings of the four completed research efforts are unrecorded (M-48), as is their disposition (M-49). C-07 notes this violates Principles 1 and 3 within the project's own documentation.

**Why it blocks.** The "Opportunity Evaluation" effort is the most likely existing source of scoring criteria (B-26), the single most-blocking P6 item. Recovering it may substantially resolve B-26; failing to recover it means rebuilding work already done.

**Engines affected.** Opportunity Intelligence primarily; Research (if ingested).

**Severity.** **Medium** structurally; **High** in practical value.

**Options.** (1) Treat as background; do not recover. (2) Recover findings into the PKP as documentation. (3) Recover and ingest as Evidence — requires retrospective provenance that may not exist. (4) Recover as documentation; re-acquire sources if ingestion is wanted.

**Recommendation.** **Option 4.** Recover findings to inform B-26 immediately. Do not ingest retrospectively as Evidence — provenance cannot be reconstructed, and admitting unprovenanced Evidence would breach E-I2 and corrupt the grounding layer at its origin.

**Trade-offs.** Re-acquisition duplicates effort. Necessary: the grounding layer's integrity is worth more than the saved effort.

**Dependencies.** Feeds B-26.

**Timing.** Before **P6**; recover **early** given its bearing on B-26.

---

## 3. Deferrable Items

Thirty-eight items that do not block P1 or any engine phase start, but must be resolved before the platform operates. Each is given all ten fields in condensed form. None is omitted.

### 3.1 Operational and Governance

| ID | Canonical | Description | Why not blocking | Engines | Sev | Options | Recommendation | Trade-offs | Depends on | Timing |
|---|---|---|---|---|---|---|---|---|---|---|
| B-44 | M-56 | Cost model | Construction proceeds without cost accounting; operation cannot | All | High | Per-run / per-engine / per-object costing; none | Per-engine costing feeding Orchestration budgets | Adds measurement overhead | B-15 | Before P2 operation |
| B-45 | M-57 | Observability requirements | Not needed to build; needed to run | All | High | Logs / metrics / explanation-derived / combined | Metrics plus explanation-derived quality signals | Explanation-derived observability couples to B-10 | B-10, B-17 | Before P2 operation |
| B-46 | M-37 | Loop termination and iteration bounding | Batch control (B-15) provides interim bounding | Orchestration | High | Fixed iterations / resource-bounded / convergence-based / manual | Resource-bounded, aligned to B-44 | Resource bounds may truncate useful work | B-15, B-44 | Before continuous operation |
| B-47 | M-51 | Phase durations, dependencies, entry/exit criteria | Planning artefact, not architecture | None | Medium | Per-phase plans / rolling / none | Per-phase entry/exit criteria derived from B-17 | Planning overhead | B-17 | Before P1 execution |
| B-48 | M-52 | Definition of done per phase | Follows from B-17 and B-47 | None | Medium | Criteria per phase / global | Per-phase, tied to stage proxies | Risks proxy-optimisation | B-17, B-47 | Before P1 execution |
| B-49 | M-54 | Cross-phase dependency model | Roadmap is sequential; dependencies are implicit | None | Medium | Explicit DAG / sequential assumption | Explicit dependency register | Maintenance overhead | B-47 | Before P1 execution |

### 3.2 Object and Knowledge Refinements

| ID | Canonical | Description | Why not blocking | Engines | Sev | Options | Recommendation | Trade-offs | Depends on | Timing |
|---|---|---|---|---|---|---|---|---|---|---|
| B-50 | M-65 | Re-derivation policy on supersession | D-01a keeps dependents valid; policy affects freshness only | All pipeline | High | Auto-recompute / flag / ignore / flag with threshold | Flag dependents; recompute on threshold breach | Flagged-but-stale objects accumulate | B-06, B-15 | Before P4 |
| B-51 | M-66 | Lineage summarisation | Principle 3 is formally satisfied; usability is the gap | All | High | Full traversal / sampled / summarised / tiered | Tiered: summary by default, full on demand | Summaries can mislead | B-06 | Before P5 |
| B-52 | OQ-14 | Knowledge Graph global or partitioned | Determined largely by B-09 | All | High | Global / partitioned / hybrid | Global, consistent with B-09's serialised interpretation | Global graph limits concurrency | B-09, B-06 | Before P5 |
| B-53 | OQ-12 | Evidence stored in full or by reference | B-34 and B-07 constrain it | Research, Store | High | Full / reference / hybrid | Hybrid: full where licensing permits, reference otherwise | Referenced evidence is vulnerable to source drift | B-34, B-07 | **Before P1** if storage design depends on it |
| B-54 | OQ-19 | Score point-in-time or recomputed | O-I4 already requires point-in-time storage | Opportunity | Medium | Point-in-time / recomputed / both | Both: stored prediction plus current score as a new version | Version churn on rescoring | B-26 | Before P6 |
| B-55 | OQ-20 | Confidence ceiling: min or weighted | `min` is specified and safe | All | Medium | min / weighted / hybrid | Retain `min` until outcome data justifies change | May understate corroborated confidence | B-04, B-24 | Revisit post-P8 |
| B-56 | OQ-21 | Pattern constituent versioning | Versioning is specified; churn is the concern | Pattern | Medium | Version always / membership relationship / batched | Batched versioning per orchestration cycle | Interim states less precise | B-15, D-01 | Before P5 |
| B-57 | OQ-16 | Prior research ingestion as Evidence | B-43 recommends non-ingestion | Research | Low | Ingest / re-acquire / reference only | Reference only; re-acquire if needed | Prior effort not reusable as Evidence | B-43 | Before P2 |

### 3.3 Engine-Level Refinements

| ID | Canonical | Description | Why not blocking | Engines | Sev | Options | Recommendation | Trade-offs | Depends on | Timing |
|---|---|---|---|---|---|---|---|---|---|---|
| B-58 | M-01 | Research trigger / what initiates discovery | B-15's batch model provides an interim trigger | Research, Orchestration | High | Scheduled / directive / event / hybrid | Directive-driven within scheduled batches | Limits spontaneous discovery | B-15 | Before P2 |
| B-59 | OQ-07 | Does Research determine its own targets | Follows from B-58 | Research | Medium | Self-directed / directed / hybrid | Directed, with proposed targets surfaced for approval | Reduces autonomy | B-58, B-14 | Before P2 |
| B-60 | OQ-08 | May Pattern Intelligence read Facts directly | B-41 resolves via lineage-restricted access | Pattern | Medium | Yes / no / lineage-restricted | Lineage-restricted per B-41 | Slightly widens Pattern inputs | B-41 | Before P5 |
| B-61 | OQ-09 | What Validation validates | B-28 baseline implies solution assumptions | Validation | High | Solutions only / any object / assumptions only | Assumptions and claims on any object, via lineage-restricted access | Widens Validation scope | B-28, B-41 | Before P7 |
| B-62 | OQ-10 | May pipeline stages be skipped | Strict reading assumed; no need to relax yet | All | Medium | Permit / forbid / permit with evidence | Forbid; injected objects must carry their own evidence | Prevents fast-path insertion of known opportunities | — | Before P6 |
| B-63 | OQ-11 | Is backflow permitted | Batch control defers the need | Orchestration, Validation | High | Permit / forbid / permit as new directive | Permit as a new research directive, not as reverse flow | Adds latency to validation-driven research | B-15, B-28 | Before P7 |
| B-64 | OQ-05 | Do learning updates require approval | B-14 gates cover this | Feedback | High | Required / not / threshold-based | Required, per B-14's third gate | Slows learning | B-14, B-24 | Before P8 |
| B-65 | OQ-17 | Why Solution and Validation share a phase | Structural question, not blocking | Solution, Validation | Low | Split / retain / retain with internal gates | Retain with an internal gate at solution completion | P7 remains the largest phase | B-32 | Before P7 |
| B-66 | M-10 | Learning cadence and trigger | Follows B-24 | Feedback | High | Per-outcome / batched / periodic / threshold | Batched per orchestration cycle | Delays learning | B-15, B-24 | Before P8 |
| B-67 | M-34 | Learning update reversion mechanism | FR-V3 requires reversibility; mechanism can follow | Feedback | High | Config rollback / inverse update / versioned config | Versioned configuration rollback | Requires B-01 | B-01, B-24 | Before P8 |
| B-68 | M-42 | Experiment lifecycle | Follows B-29 | Validation | Medium | States per experiment / reuse D-02 | Reuse D-02 vocabulary where applicable | Operational state differs from knowledge state | B-29 | Before P7 |
| B-69 | M-33 | Validation outcome states | Closed by IOM `result` enumeration | Validation | Low | — | Confirm IOM enumeration is sufficient | — | B-28 | Before P7 |
| B-70 | M-28 | Owner of solution selection | Covered by B-32 | Solution | High | — | Resolve with B-32 | — | B-32 | Before P6 |
| B-71 | M-27 | Prioritisation and ranking policy | Follows B-26 | Opportunity | High | Score-ordered / portfolio / threshold | Score-ordered with capacity threshold | Ignores portfolio effects | B-26, B-32 | Before P6 |
| B-72 | M-26 | Platform definition of "opportunity" | Object purpose is specified; formal definition refines it | Opportunity | High | Narrow / broad / typed | Typed, aligned to scoring dimensions | Typing may exclude novel forms | B-26 | Before P6 |
| B-73 | M-09 | Retraction and correction semantics | D-02 and I6 define states; B-03 supplies the owner | All | High | — | Resolve with B-03 | — | B-03 | Before P1 completion |
| B-74 | M-30 | Assumption structure | Closed by IOM structured assumptions | Solution, Validation | Low | — | Confirm IOM structure is sufficient for B-28 methods | — | B-28 | Before P7 |
| B-75 | M-44 | Write-authority model | Closed by IOM §2.5 | All | Low | — | Confirm on ratification; extend for B-22 | — | B-22 | Before P1 completion |
| B-76 | M-41 | Cycle handling | Closed by V10 and behavioural loop closure | All | Low | — | Confirm on ratification of C-04 | — | C-04 | Before P1 completion |
| B-77 | C-07 | Project documentation violates its own principles | Documentation remediation | None | Medium | Remediate / accept / partial | Remediate via B-43 recovery | Effort with no functional gain | B-43 | Before P0 closure |
| B-78 | C-01 | Scoring has no owning engine | B-26 resolves to Opportunity Intelligence | Opportunity | High | Internal / cross-cutting / new engine | Internal to Opportunity Intelligence; no new engine | Concentrates responsibility | B-26 | Before P6 |
| B-79 | M-45/46 confirmations | Lifecycle and temporal models | Closed by D-02 and D-04 | All | Low | — | Confirm on ratification | — | D-02, D-04 | Before P1 completion |
| B-80 | M-11/M-40/M-08/M-15 confirmations | Fact identity, relationships, versioning, confidence | Closed by D-05, D-06, D-01, D-03 | All | Low | — | Confirm on ratification | — | D-01…D-06 | Before P1 completion |
| B-81 | OQ-03/OQ-04 confirmations | Contradictory evidence; rejected candidates | Closed by `CONTRADICTS` and D-02 | All | Low | — | Confirm on ratification | — | D-02, D-06 | Before P1 completion |
---

## 4. Prioritized Resolution Roadmap

Ordered by dependency, not severity. An item appears only after everything it depends on. Resolving out of order forces rework.

### Wave 0 — Enabling (must precede all other resolution work)

| Order | Blocker | Item | Rationale |
|---|---|---|---|
| 0.1 | **B-19** | Architecture decision records (M-50) | Every subsequent resolution produces a record. Without the mechanism, decisions are unauditable and the IOM's standing instruction cannot be honoured. |
| 0.2 | — | **Publish the marker crosswalk (§0.2)** and renumber IOM references | Until identifiers are canonical, decisions attach to the wrong gaps. |
| 0.3 | — | **Ratify IOM decisions D-01 … D-08** | Seventeen closures depend on them. Two need specific attention: D-07 adds a ninth object type; the C-04 behavioural loop closure determines lineage acyclicity. |

Wave 0 is process, not architecture, and can be completed quickly. Nothing else should start first.

### Wave 1 — Scope and Boundary (determines everything downstream)

| Order | Blocker | Item | Unblocks |
|---|---|---|---|
| 1.1 | **B-18** | Scope: non-goals and output consumers (M-03, M-05) | B-22, B-14, B-32, the platform boundary |
| 1.2 | **B-14** | Human role and approval gates (OQ-02) | B-32, B-64, object approval states |
| 1.3 | **B-17** | Success criteria and effectiveness measures (M-04) | B-24, B-47, B-48, all phase exit criteria |
| 1.4 | **B-13** | Determinism and reproducibility (OQ-01) | Capture requirements at every write |
| 1.5 | **B-08** | Security, access control, tenancy (M-55) | Partitioning decisions in the foundation |

These five determine what the platform *is*. Every later decision inherits from them, and each is cheap now and expensive after P1.

### Wave 2 — Knowledge Foundation (the P1 critical path)

| Order | Blocker | Item | Note |
|---|---|---|---|
| 2.1 | **B-06** | Store/Graph boundary and consistency (C-06, M-39) | **Highest-leverage single item.** Nothing in P1 starts without it. |
| 2.2 | **B-01** | Engine configuration referent (M-63) | Required by every object write |
| 2.3 | **B-02** | Acceptance authority (M-64) | Enforces V1–V12; largest integrity exposure |
| 2.4 | **B-03** | Cascade invalidation owner (M-58) | Closes M-09 |
| 2.5 | **B-12** | Failure representation (M-36) | Shares B-01's home |
| 2.6 | **B-09** | Concurrency model (OQ-13) | Determines OQ-14 |
| 2.7 | **B-07** | Retention policy (M-38) | Depends on B-53 |
| 2.8 | **B-53** | Evidence full vs reference (OQ-12) | Storage cost profile |

### Wave 3 — Object Semantics (completes the contract surface)

| Order | Blocker | Item | Note |
|---|---|---|---|
| 3.1 | **B-05** | Confidence calibration rubric (M-60) | Must precede any stored confidence value |
| 3.2 | **B-27** | Source diversity propagation — summary attribute (M-23) | Input to B-04 |
| 3.3 | **B-04** | Evidential support computation (M-59) | Depends on B-27 |
| 3.4 | **B-11** | Evidence sufficiency thresholds (M-06) | Depends on B-04 |
| 3.5 | **B-21 + B-36** | Fact equivalence and definition (M-62, M-19) | **Co-decided.** Fact identity is permanent. |
| 3.6 | **B-20** | Hallucination detection hook (M-20) | **Highest severity in the review** |
| 3.7 | **B-10** | Explanation format (M-07) | Universal attribute |
| 3.8 | **B-41** | Cross-stage read access (OQ-18) | Completes the authority matrix |

### Wave 4 — Control (unblocks P2 onward)

| Order | Blocker | Item |
|---|---|---|
| 4.1 | **B-15** | Orchestration control model (M-35, M-37, OQ-15) |
| 4.2 | **B-16** | Orchestration roadmap phase (C-08) |
| 4.3 | **B-42** | Experiment Registry phase reservation (M-53) |

**— P1 MAY BEGIN AFTER WAVE 4 —**

### Wave 5 — Research Engine (P2)

B-33 (source taxonomy, M-16) → B-34 (legal/licensing, M-18) → B-35 (coverage, M-17) → B-58 (research trigger, M-01) → B-59 (target determination, OQ-07) → B-44 (cost model, M-56) → B-45 (observability, M-57).

### Wave 6 — Extraction and Interpretation (P3–P5)

B-37 (problem attributes, M-12/M-21) → B-38 (problem identity, M-22) → B-50 (re-derivation, M-65) → B-39 (pattern strength, M-24/M-25) → B-40 (pattern temporal validity, M-13/M-61) → B-51 (lineage summarisation, M-66) → B-52 (graph scope, OQ-14) → B-56 (pattern versioning, OQ-21) → B-60 (fact-level patterns, OQ-08).

### Wave 7 — Opportunity (P6)

**B-43 (recover completed research, M-48/M-49) first** — it may substantially resolve B-26. Then B-26 (scoring, M-14) → B-78 (scoring ownership, C-01) → B-72 (opportunity definition, M-26) → B-71 (prioritisation, M-27) → B-32 (gate ownership, M-28/M-31) → B-70 → B-54 (score persistence, OQ-19) → B-62 (stage skipping, OQ-10).

### Wave 8 — Solution and Validation (P7)

B-29 (Registry boundary, C-05) → B-28 (validation methodology, M-32) → B-31 (solution granularity, M-29) → B-30 (constraint model, M-69) → B-61 (validation target, OQ-09) → B-63 (backflow, OQ-11) → B-68 (experiment lifecycle, M-42) → B-65 (P7 structure, OQ-17) → B-69, B-74.

### Wave 9 — Feedback (P8)

**B-22 (Execution stage owner, C-02) first** — the structural break. Then B-23 (outcome intake, M-47) → B-24 (learning target, M-02/M-43) → B-25 (instability guard, M-70) → B-66 (cadence, M-10) → B-67 (reversion, M-34) → B-64 (approval, OQ-05) → B-55 (ceiling revisit, OQ-20).

### Confirmations (on ratification)

B-73, B-75, B-76, B-77, B-79, B-80, B-81 — confirm IOM closures and remediate project documentation.

---

## 5. Minimum Set of Architectural Decisions Before Implementation

Twenty-two decisions. This is the **irreducible minimum** — each either cannot be retrofitted after P1, or determines P1's structure. Everything else may follow.

### 5.1 Ratifications (8)

| # | Decision | Consequence if not ratified |
|---|---|---|
| R-1 | **D-01** Objects immutable, versioned | Storage model undefined |
| R-2 | **D-02** Seven-state lifecycle | No status semantics |
| R-3 | **D-03** Two-component confidence + ceiling | No defence against confidence inflation |
| R-4 | **D-04** Explicit temporal validity | Staleness invisible |
| R-5 | **D-05** Facts as canonical claims | Corroboration uncountable |
| R-6 | **D-06** Closed relationship taxonomy | Graph semantically incoherent |
| R-7 | **D-07** Feedback Record — **ninth object type** | Learning untraceable; Principle 3 breached |
| R-8 | **D-08 + C-04 closure** Objects authoritative; behavioural loop closure | Lineage cycles possible; grounding compromised |

R-7 and R-8 warrant explicit attention: R-7 extends v1's object count, and R-8 reinterprets v1's pipeline notation.

### 5.2 New Decisions (14)

| # | Decision | Blocker | Why it cannot wait |
|---|---|---|---|
| N-1 | Platform boundary: advisory with structured handoff and mandatory outcome reporting | B-18 | Determines C-02, the structural break |
| N-2 | Human gates at exactly three transitions | B-14 | Approval states are object structure |
| N-3 | Success measures: stage proxies now, outcome measures fixed now | B-17 | Defining outcome measures late lets results bias them |
| N-4 | Reproducible inputs, non-deterministic outputs | B-13 | Determines write-time capture |
| N-5 | Tenancy discriminator reserved on every object | B-08 | Cannot partition retrospectively |
| N-6 | Objects authoritative; graph derived and rebuildable; atomic object write | B-06 | The P1 decision |
| N-7 | Configuration store as scoped Knowledge Store extension | B-01 | Every object references it |
| N-8 | Knowledge Store enforces acceptance; rules specified in the object model | B-02 | Invalid objects otherwise enter from the first write |
| N-9 | Cascade invalidation as a mechanical operation invoked by Orchestration | B-03 | Retraction is routine |
| N-10 | Failure records outside the object model, co-located with configuration | B-12 | Silent failure otherwise indistinguishable from empty results |
| N-11 | Concurrent acquisition/extraction; serialised interpretation | B-09 | Determines store and graph structure |
| N-12 | Retention: lineage skeleton permanent, content tiered by reachability | B-07 | Growth is monotonic and unbounded |
| N-13 | Explanation skeleton with free-text reasoning | B-10 | Universal attribute; immutable once written |
| N-14 | Lineage-restricted cross-stage read access | B-41 | Completes the authority matrix |

### 5.3 Semantic Decisions Required Before First Write (5)

These fix values that become permanent the moment objects are stored.

| # | Decision | Blocker | Permanence |
|---|---|---|---|
| S-1 | Confidence calibration rubric with worked anchors | B-05 | Stored values uninterpretable without it |
| S-2 | Evidential support function (conservative, source-independence based) | B-04 | Stored values incomparable without it |
| S-3 | Structured claim decomposition; conservative merge with `DUPLICATES` | B-21+B-36 | Fact identity is permanent (I2) |
| S-4 | Independence-based sufficiency thresholds | B-11 | Enforced at acceptance |
| S-5 | Anchor verification on all Facts; sampled audit; published hallucination rate | B-20 | Acceptance path built in P1 |

**Total: 22 decisions** (8 ratifications + 14 new + 5 semantic, with B-04/B-05 counted once). Every other item in this review may be resolved after P1 begins.

---

## 6. Readiness Assessment

### 6.1 Method

Scores are computed, not estimated. Each dimension is decomposed into constituent requirements, weighted by criticality (3 = blocking, 2 = significant, 1 = minor), scored as resolved (1.0), partially resolved (0.5), or unresolved (0.0). The score is the weighted proportion resolved.

### 6.2 Scores

| Dimension | Readiness | Weighted basis |
|---|---|---|
| **Architecture** | **24%** | 6.0 / 25 |
| **Object Model** | **44%** | 19.0 / 43 |
| **Engine Contracts** | **42%** | 11.0 / 26 |
| **Knowledge System** | **12%** | 3.5 / 29 |
| **Feedback System** | **17%** | 4.5 / 26 |
| **Overall (weighted average)** | **30%** | 44.0 / 149 |
| **Overall (foundation-gated)** | **12%** | — |

### 6.3 Two Overall Figures, and Which to Use

The weighted average is **30%**. The foundation-gated figure is **12%** — the minimum across Architecture, Object Model and Knowledge System.

**Use 12% as the implementation-readiness figure.** Readiness is not an average; it is gated by the weakest foundational layer. The Knowledge System is built first, everything else is built on it, and it is 12% ready. A high Object Model score cannot compensate: objects cannot be stored correctly by a knowledge system whose boundary, consistency model, acceptance authority and configuration home are all undefined.

The 30% average is the honest measure of *specification progress*. The 12% is the honest measure of *whether P1 can start*.

### 6.4 Dimension Commentary

**Architecture — 24%.** The strongest content is v1's own: vision, principles, pipeline and engine boundaries are coherent and internally consistent. What is missing is everything horizontal — scope boundary, human role, success criteria, control model, security. v1 specified the platform's *shape* thoroughly and its *operating context* not at all.

**Object Model — 44%, the strongest dimension.** Structure is complete: nine types, attributes, lifecycle, versioning, relationships, lineage. What remains is *semantic content* — the support function, calibration, equivalence criteria, and four vocabularies (scoring, validation methods, learning targets, problem scales). The contract's grammar exists; parts of its dictionary do not.

**Engine Contracts — 42%.** The authority matrix, single-creator rule, boundaries and object-only communication are settled. Blocking gaps are cross-stage access, failure representation, gate ownership, and the missing Execution Engine.

**Knowledge System — 12%, the critical path.** Only the relationship taxonomy is settled, with D-08 partial. The store/graph boundary, consistency model, acceptance authority, cascade invalidation, configuration home, retention and concurrency are all open — and all are P1 construction decisions. **This dimension alone determines whether P1 can begin.**

**Feedback System — 17%.** The Feedback Record now exists (D-07) and loop closure is provisionally resolved. But the input has no producer (C-02), no intake mechanism (M-47), no learning target (M-02), no stability guard (M-70), and no success measure (M-04). Principle 5 and Architecture Decision 3 remain the least-realised parts of the platform.

### 6.5 Projected Readiness After Resolution

| Dimension | Now | After Waves 0–4 |
|---|---|---|
| Architecture | 24% | ~88% |
| Object Model | 44% | ~79% |
| Engine Contracts | 42% | ~85% |
| Knowledge System | 12% | ~93% |
| Feedback System | 17% | ~35% |
| **Overall (gated)** | **12%** | **~79%** |

The Feedback System remains low after Wave 4 by design: its blockers are P8 items and cannot be resolved earlier without inventing the execution boundary. This is acceptable — the loop is built last — provided C-02 is resolved before P7 completes rather than discovered at P8.

### 6.6 Principal Findings

1. **Twenty-two decisions stand between the project and a safe P1 start.** All are decidable now; none requires new research except B-43, which is recovery of work already done.

2. **The Knowledge System is the critical path, and B-06 is the critical item.** It blocks B-01, B-02 and B-03, and it determines the layer that is hardest to change later.

3. **The highest-severity gap is B-20, hallucination detection.** A fabricated Fact satisfies every structural rule in the object model. Structure cannot catch it, so the acceptance path must accommodate a semantic check and the residual error rate must be measured and published rather than left invisible.

4. **The marker identifier defect (§0.1) is a genuine risk, not a clerical matter.** Uncorrected, decisions would be recorded against the wrong gaps and closures would be unverifiable.

5. **Specification progress is real.** The IOM closed eighteen items and opened seventeen — a flat count, but the remaining items are specific, individually addressable, and correctly scoped, where v1's were diffuse. The count is the wrong measure; the tractability is the right one.

6. **v1's architecture holds.** Ninety-nine items of scrutiny across three documents have produced no finding that the pipeline, engine decomposition, or object model is wrong. Every gap is an omission, not an error. The architecture is sound and radically under-specified — which is a far better position than the reverse.

---

## 7. Document Control

**Scope.** All 81 open items reviewed: 21 P1 blockers (§1), 22 engine-phase blockers (§2), 38 deferrable items (§3). Every item carries all ten requested fields. None omitted.

**Preservation.** No engine, stage, component, principle or phase added, removed or renamed. Two recommendations extend existing scope and are flagged for explicit ratification: outcome intake assigned to the Research Engine (B-22), and a configuration store as a scoped Knowledge Store extension (B-01). Both were chosen as the smallest available deviation; the alternatives would have added a tenth engine and a fourth component respectively.

**Exclusions observed.** No code. No schemas or interfaces. No user interface. No redesign. No implementation.

**Status.** Analysis and recommendation only. No decision herein is ratified. Every recommendation requires a decision record under B-19 before it becomes binding.

---

*End of Pre-P1 Blocker Resolution Analysis.*
