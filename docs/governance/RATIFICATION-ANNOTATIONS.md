# Ratification Annotations to Authoritative Documents

**Status:** Authoritative. Records how ratified decisions modify the interpretation of frozen documents.
**Established by:** F00.2
**Governing rule:** Frozen documents are **not rewritten**. This annotation layer records what each ratification changes, and is authoritative over the text it annotates.

---

## 1. Why an Annotation Layer

PKP v2 and the Intelligence Object Model are frozen. Rewriting them in place would break the freeze and destroy the ability to see what the architecture originally said versus what was later decided.

The same discipline already applied to marker identifiers (`marker-crosswalk.md`) applies here: **the frozen document keeps its text; this layer records the binding interpretation.**

Precedence, highest first:
1. Decision records (`R-1`…`R-8`, `AD-05`)
2. This annotation layer
3. Intelligence Object Model
4. PKP v2 — Master Reference

---

## 2. New Standing Principle — AD-05

**Ground Truth Protection Principle** is ratified as a platform-wide standing rule.

> No platform-generated artifact may become Evidence directly. Evidence must always originate from external reality.

Feedback may only become one of four permitted forms: **Learning Signal**, **Knowledge Update**, **Research Trigger**, **Model Calibration**.

### 2.1 Status relative to v1's principles

AD-05 does **not** add a sixth principle to v1's five (Evidence before conclusions, Explainable decisions, Traceable lineage, Modular engines, Continuous learning).

It is an **architecture decision that elevates and generalises AD-01 (Evidence-First)**, recorded in the `AD-nn` series alongside v1's four original decisions. v1's principle set is unchanged at five.

### 2.2 Where AD-05 binds

| Document | Section | Annotation |
|---|---|---|
| PKP v2 | §2.1 Principle 1 | AD-05 generalises this principle: the prohibition extends to *any* platform-generated artifact becoming Evidence, not only to conclusions lacking evidence. |
| PKP v2 | §3.3 Stage 1 (Evidence) | Evidence originates from external reality without exception. The C-04 alternative reading (a) — internally-generated Evidence as a legitimate subtype — is **prohibited**. |
| PKP v2 | §3.9 Stage 9 (Feedback) | Feedback output is restricted to the four permitted forms. |
| PKP v2 | §8.3 Decision 1 | AD-01's grounding guarantee is now unconditional. |
| IOM | §3.1 Evidence, E-I2 | Enforcement point. Binding. |
| IOM | §3.9 Feedback Record, FR-I2 | Enforcement point. Binding. |
| IOM | §4.2 Loop Closure | Normative, not proposed. |

### 2.3 The four permitted forms and their homes

| Form | Artefact | Enters lineage graph? |
|---|---|---|
| Learning Signal | Feedback Record (`lesson_statement`, `evidence_of_pattern`) | As a **leaf** — nothing derives from it |
| Knowledge Update | Object status transition / supersession | No — status is the sole non-versioning mutation (R-2) |
| Research Trigger | Research directive (`T02.2.4`, `T08.3.4`) | No — causes acquisition of *external* Evidence |
| Model Calibration | Configuration store record (N-7) | No — outside the object model |

**None of the four enters the lineage graph as grounding.** The prohibition is complete across all permitted forms.

---

## 3. Contradictions Closed

| Marker | Status | Closed by | Effect on PKP v2 §11 |
|---|---|---|---|
| **C-03** | **CLOSED** | R-7 | Feedback stage now has an owning object. §6.4.1 stage-object alignment: Feedback row changes from "none" to "Feedback Record". |
| **C-04** | **CLOSED** | R-8 + AD-05 | The AD-01 vs AD-03 conflict — v2 §8.7's single decision-level conflict — is resolved in favour of AD-01. |
| C-06 | Partially constrained | R-8 Part 2 | Objects authoritative for lineage; Graph is a derived index. Full boundary resolution at `T00.4.1` (N-6). |

**Contradiction register after F00.2:** C-01, C-02, C-06 remain open. Reduced from 8 to 3.

---

## 4. Missing Definitions Closed

| Marker | Closed by | Substance |
|---|---|---|
| **M-08** | R-1 | Objects immutable, versioned; version-specific lineage binding |
| **M-45** | R-2 | Seven-state canonical lifecycle |
| **M-15** | R-3 | Two-component confidence with monotonic ceiling |
| **M-46** | R-4 | Explicit temporal validity, no automatic decay |
| **M-11** | R-5 | Facts as canonical claims with multiple attachments |
| **M-40** | R-6 | Closed ten-type relationship taxonomy |
| **M-50** | F00.1 | Architecture decision records established |

**Also resolved:** OQ-03 (contradictory evidence — via `CONTRADICTS`), OQ-04 (rejected candidates retained — via R-2).

---

## 5. Object Model — Now Nine Types

Ratified by R-7. The Intelligence Object Model is:

| # | Object | Stage | Producing engine |
|---|---|---|---|
| 1 | Evidence | 1 | Research |
| 2 | Fact | 2 | Fact Extraction |
| 3 | Problem | 3 | Problem Intelligence |
| 4 | Pattern | 4 | Pattern Intelligence |
| 5 | Opportunity | 5 | Opportunity Intelligence |
| 6 | Solution | 6 | Solution Intelligence |
| 7 | Validation | 7 | Validation |
| 8 | Execution Record | 8 | **UNDEFINED — C-02 open** |
| 9 | **Feedback Record** | 9 | **Feedback** |

**Annotation to PKP v2 §6:** the object model is nine types, not eight. **Annotation to PKP v2 §6.4.1:** eight of nine stage-object pairs now align; the sole remaining break is Stage 8 (C-02).

**Unchanged:** nine engines, ten pipeline stages, three shared components, five principles, four v1 architecture decisions.

---

## 6. Pipeline Notation — Binding Interpretation

v1 §3 reads:

```
… Execution -> Feedback -> Evidence
```

**Binding interpretation (R-8):** the final arrow means *"feedback causes new external Evidence to be acquired"*, **not** *"feedback becomes Evidence"*.

```
FEEDBACK RECORD ──INFORMS──▶ engine behaviour
                                   │
                                   ▼
                          research directive
                                   │
                                   ▼
                          EXTERNAL REALITY
                                   │  acquisition
                                   ▼
                            NEW EVIDENCE
                     (external origin, no upstream lineage)
```

The arrow in v1's notation **remains**; its meaning is fixed. The lineage graph is acyclic.

---

## 7. Enforcement Points Now Binding

| Rule | Object | Enforces |
|---|---|---|
| E-V1 | Evidence | `derives_from` must be empty |
| E-I2 | Evidence | Never derives from any platform-internal object |
| FR-I2 | Feedback Record | Never becomes Evidence |
| FR-V6 | Feedback Record | Derives from Execution Records only |
| V10 | All | No lineage cycle may be introduced |
| V5 / I7 | All | Confidence ceiling |
| V11 | All | Version increment and `lineage_id` integrity |
| V12 | All | Relationships drawn from the closed taxonomy |
| V9 | All | `status_reason` required when status ≠ `ACTIVE` |
| I5 | All | Exactly one `ACTIVE` version per `lineage_id` |

These are acceptance-time or continuous checks built in P1 (`T01.4.1`–`T01.4.5`).

---

## 8. Backlog Impact

**No task added, removed or resequenced.**

| Task | Effect |
|---|---|
| `T00.2.1`–`T00.2.8` | Complete |
| `T00.4.1` | Unblocked — was gated on `T00.2.1` and `T00.2.8` |
| `T01.7.9` | Unblocked — Feedback Record type confirmed |
| `T01.3.6` | Cycle guard confirmed implementable; cycles are illegal |
| `T02.2.4`, `T08.3.4` | Research directive path confirmed as the loop closure mechanism |
| `T00.7.1` | 8 of 22 minimum decisions ratified, plus AD-05 |

---

## 9. Open Items Unaffected

Ratification does not resolve these. Recorded to prevent false confidence:

| Marker | Status | Note |
|---|---|---|
| **M-70** | Open | Behavioural loop instability. AD-05 and R-8 close the **lineage** path to self-reinforcement; the **behavioural** path — learning narrows research, which narrows findings — remains open until `T08.3.1`–`T08.3.3`. **Neither decision should be read as having solved loop instability.** |
| M-59 | Open | `evidential_support` computation (S-2) |
| M-60 | Open | Cross-engine confidence calibration (S-1) — R-3's ceiling is arithmetically valid but semantically unsound until resolved |
| M-62 | Open | Semantic equivalence for Fact merging (S-3) — R-5's correctness depends on it |
| M-02 | Open | Learning target vocabulary — Feedback Record's `change_target` unpopulatable until `T08.2.1` |
| C-02 | Open | Execution Record has no producing engine — Feedback Record's only permitted upstream |
| M-31, M-38, M-58, M-61 | Open | Gate ownership, retention, cascade owner, staleness owner |

## 10. P2 Decision Set — Annotations (2026-08-04)

Recorded on ratification of N-20…N-23. No frozen document is rewritten; this
layer records the binding interpretation (§1 precedence: decision records →
this layer → IOM → PKP v2).

| Target | Annotation |
|---|---|
| **IOM §3.1** `source_type` | Annotated "(MISSING-18: no taxonomy exists)". **N-20 §5.1 now supplies the closed taxonomy.** The IOM text stands; N-20 governs. |
| **IOM §3.1** `source_reliability` | Annotated "(OPEN QUESTION-28)". **OQ-28 is closed by N-20 §5.3.** The attribute remains **optional**; no contract change. |
| **IOM §3.1** Confidence | States `evidential_support` "reflects source reliability". **S-2 governs** (Art. XI): trust is **not** an input. The IOM sentence expresses intent, unrealised until a record supersedes S-2. |
| **IOM §3.1** `access_conditions` | Annotated "(OPEN QUESTION-13)" — a mis-merge: canonical OQ-13 is *concurrency*, closed by N-11. **N-21 §5.5 supplies the rights vocabulary.** Identifier defect recorded, not resolved. |
| **N-2** | `T02.2.4` AC2 requires "approval per human-gate decision". N-2 fixes **exactly three gates**, none covering research targets. Under Art. XI **N-2 governs; the backlog AC is unsatisfiable as written** (D-1). N-2 is **unchanged**; N-23 creates no fourth gate. |
| **R-2** | N-23 directive states (`RAISED`, `IN_EFFECT`, `FULFILLED`, `CANCELLED`, `EXPIRED`) are **disjoint** from R-2's seven object states. R-2 is untouched. |
| **N-15** | Its licensing precondition is **supplied** by N-21 §5.7, not superseded. |
| **N-3** | "Source-type coverage" refined by N-22 under N-3's own extension clause. Not superseded. |

**Reservations carried into force.** AS-0…AS-5 remain recorded in the
*Honest Limitations* sections of N-20 and N-22. Ratification adopted them as
**choices**, not as corpus-derived consequences.

---

## 11. Owner Decisions — D-1 Resolution, T02.1.3 Interpretation, N-24 Ratification (2026-08-19)

Three acts were taken by the Project Owner on **2026-08-19**: the D-1
resolution (reserved to the ratifier by N-23 §5.5), the `T02.1.3` AC1
reading (carried-vs-detected, `NEXT_STEPS.md` §4), and the ratification of
**N-24**, which names the authority N-21 §5.1 deliberately left unnamed. No frozen document is rewritten; this section records
the binding interpretation (§1 precedence: decision records → this layer →
IOM → PKP v2 → backlog).

| Target | Annotation |
|---|---|
| **D-1** | **RESOLVED — Option N-23 §5.5(i).** `T02.2.4` AC2 is amended to *"Targets recorded with their commissioning authority"* — the exact wording ratified in N-23 §5.5(i). **N-2 is unchanged**; no fourth human gate is created; commissioning remains a pre-platform act that the platform records, never adjudicates (N-23 §5.5). The backlog AC text is amended (backlog is not frozen; it sits below this layer in precedence). `T02.2.4` is unblocked and sequenced behind `T02.2.1`; the 22 downstream P7–P8 tasks blocked on D-1 are unblocked. M-01's "target approval (D-1)" remainder is closed. |
| **`T02.1.3` AC1** | **Interpreted — explicit-input model.** `source_independence_group` is supplied explicitly as an input and is carried and honoured wherever supplied; the fallback rule (`independence_group or source_identifier`, N-16/T01.7.1) governs where absent. **The platform performs no syndication, ownership or independence inference.** Any future inference of independence or syndication requires an explicit ratified rule; none exists. This is the conservative, fail-closed reading of N-16, which defines assessment mechanics (the grouping key) but never assigns detection to any engine. |
| **`T02.1.3` status** | **CLOSED 2026-08-19 on existing evidence** — the explicit-input model is the implemented, tested reality: `oip/source.py` (registry `independence_group`, `independence_key`, `independence_groups()`), `oip/evidence.py` (`Provenance.source_independence_group`, `independence_key`, `independent_sources()`), with tests `test_source.py` and `test_evidence.py` (`test_independence_key_defaults_to_source`, `test_independence_group_overrides_source`, `test_independent_sources_deduplicated`). AC2 holds: sources sharing a supplied group count once. `T02.1.4` (declared dependent) is unblocked by this closure. |
| **N-24** | **RATIFIED 2026-08-19 — N-21 §5.1 authority named.** The "named human authority outside the platform" is the role **Designated Source Rights/Compliance Authority** (`decisions/N-24-source-rights-authority.md`). **N-21 is unchanged and not superseded**; N-24 supplies what §5.1 deliberately left unnamed, closing its §10 item 2. Scope is bound to the N-21 §5.5 vocabulary only — no M-18b conduct powers, no trust scoring (S-2), no taxonomy assignment (N-20 §5.1), no research scoping (N-23); the N-21 §12 compliance discrepancy remains open. **Ratification does not operationalise acquisition**: sources stay `UNASSESSED` until the role is staffed and supplies assessments (N-21 §6 item 2), and `T02.1.2` is implementable, not operational. |

## 12. F-V4 — Assertion vs Attributed Opinion Classification (2026-09-09)

Recorded on ratification of **F-V4**
(`decisions/F-V4-assertion-vs-attributed-opinion.md`), which closes the
two specification gaps identified by the T03.1.5 final audit (implementation
commit `98741f270e178a1f9a782c3a3dae684b6443543d`): the classification
direction and the `ASSERTION + attributed_to` combination. No frozen
document is rewritten; this layer records the binding interpretation
(§1 precedence: decision records → this layer → IOM → PKP v2).

| Target | Annotation |
|---|---|
| **IOM §3.2 F-V4** | "claim_type present; attributed_to required when ATTRIBUTED_OPINION" is now read as the **biconditional** (F-V4 R1/R4): `claim_type = ATTRIBUTED_OPINION ⟺ attributed_to` is a non-empty string after whitespace stripping. The forward direction is the existing rule, unchanged. The ratified converse (R2) makes `ASSERTION` + non-empty `attributed_to` a **contradictory request: REJECTED** at the extraction boundary with a recorded failure (`INVALID_REQUEST` / `CLAIM_TYPE_CONFLICT`, N-10) — never reclassified, never allowed, never silently dropped. Absent, empty and whitespace-only attribution all mean "no attribution" (⇒ ASSERTION); non-string values are outside the declared `str \| None` contract and rejected at request construction (R3). |
| **IOM §3.2 `attributed_to`** | "Speaker, for `ATTRIBUTED_OPINION`" is binding as the field's **only** meaning (R3): a valid attribution names the identifiable originator the proposition is attributed to (**WHO** holds the statement) and is **not** evidential provenance (**WHERE** the supporting material came from — that remains the Evidence attachment, `derives_from` lineage and the source registry). Structural validity is checkable; whether the string genuinely identifies an originator is the extractor's responsibility, consistent with S-5 Layer 1 / M-67. |
| **MR §3.3 Stage 2 invariant** | "Opinions, if extracted, must be marked as attributed statements rather than as assertions of truth" is given its checkable mechanism (R5): classification at the extraction boundary is a pure, deterministic, checkable function of the structured request — no interpretation of wording, no LLM, no network, no silent reclassification, no silent attribution loss. The converse is enforced at the create-authority boundary (V7: only Fact Extraction creates Facts), so every platform Fact satisfies the biconditional; the store's F-V4 rule remains the final structural safety net. |
| **T03.1.5** | The audit verdict **APPROVED WITH SPECIFICATION RISK** is resolved: audit findings 1 and 2 map to R1 and R2, and the implementation (`98741f2`) satisfies R1–R5 exactly — ratification requires **no implementation change**. |
| **T03.1.4 / S-3** | R6 introduces **no** new requirement on T03.1.4: canonical merges preserve the canonical's `claim_type` / `attributed_to` (INV-4; holds mechanically today). The type-blind cross-type merge issue is recorded as future item **T03.1.4-F1 — claim-type-aware canonical merging**, which will require its own decision record before implementation because it supersedes the ratified S-3 merge conditions. S-3 and R-5 are unchanged and not superseded. |

## 13. F-C1 — Fact Contradiction: Detection and Representation Semantics (2026-09-09)

Recorded on ratification of **F-C1**
(`decisions/F-C1-fact-contradiction-semantics.md`), which closes the
T03.1.6 specification gap: no ratified source defined when two claims are
incompatible (OQ-03, already closed by R-06, settled only that
contradiction must be *represented*). Ratified with the Project Owner's
required Q7 amendment (narrower binding scope, applied verbatim in F-C1
R7). No frozen document is rewritten; this layer records the binding
interpretation (§1 precedence: decision records → this layer → IOM →
PKP v2 → backlog).

| Target | Annotation |
|---|---|
| **IOM §1.2 `contradicts`** | "Objects mutually incompatible with this one", populated "On detection" — F-C1 R1 now supplies the checkable detection rule: an **established contradiction** exists iff same subject, same predicate, identical qualifier, both values quantified, same unit, and the values disagree outside the coarser stated precision — decided with the S-3 primitives (`same_subject`, `same_predicate`, `same_qualifier`, `Quantity.agrees_with`) unchanged. **Fail-closed:** "cannot establish contradiction" (incomparable or merely different claims) never produces a link; its distinction from "established contradiction" is mandatory and auditable. |
| **IOM §3.2 `CONTRADICTS` (Fact)** | "Incompatible claims" is now determined by F-C1 R1. "Representing disagreement rather than selecting a winner" is made structural: no winner, no status change, no merge interference, no resolution policy — **both Facts remain ACTIVE** (F-C1 INV-C1..C4; backlog AC1/AC2). Engine Authority unchanged: Fact Extraction alone detects and records, at the extraction boundary, over ACTIVE peers, on the **new Fact's** `contradicts` attributes (R5/R6); the merge path performs no detection (equivalent content ⇒ identical contradiction set); pairs predating implementation remain unlinked — recorded, not silent. |
| **IOM §3.2 claim_type / `attributed_to` (F-V4)** | F-C1 R3 is **type-blind**: detection consults neither field, exactly as S-3 equivalence does not (F-V4 R6). Cross-type (ASSERTION × ATTRIBUTED_OPINION) and cross-speaker contradiction links express content-level conflict only; F-V4's biconditional and INV-1..INV-4 are unchanged and not superseded. **T03.1.4-F1 is not ratified and not required by F-C1.** |
| **S-3 / T03.1.4** | **Not superseded.** `MERGE_POLICY`, `Verdict` and `assess_equivalence` are unchanged: CONTRADICTS peers are a strict subset of NOT_EQUIVALENT peers, structurally disjoint from DUPLICATES peers (CONTAINMENT ∪ UNCERTAIN) and from merge (EQUIVALENT). T03.1.4's "NOT_EQUIVALENT links nothing" stated that task's DUPLICATES link policy; T03.1.4's own §4 non-goals anticipated this task ("CONTRADICTS machinery untouched"). |
| **Q7 (Project Owner's required amendment, binding)** | **UniversalAttributes.contradicts is the authoritative recording surface for T03.1.6. Graph projection of CONTRADICTS is OUT OF SCOPE for T03.1.6. T03.1.6 MUST NOT add graph edges or modify graph/store infrastructure. Any future graph projection decision remains a separate architectural decision and must not be inferred from this task.** This is a scope statement for T03.1.6, not a permanent prohibition; the MR §1014 anticipation (graph-held contradiction links) is preserved as a future architectural issue (F-C1 Known Tensions 1). |
| **T03.1.6** | Specification-unblocked: both backlog ACs are given their checkable meaning by F-C1 R1–R8 (implementation constraints in the record: sole file `oip/extraction.py`, import budget 6/6 unchanged, no new Verdict/`MERGE_POLICY`/refusal reason, T03.1.4's frozen-module pins intact). Ratification itself changes no code and creates no tests; implementation proceeds per the normal task process. |

## 14. F-A1 — Sampled Fidelity Audit: S-5 Layer 2 Protocol Semantics (2026-09-12)

Recorded on ratification of **F-A1**
(`decisions/F-A1-sampled-fidelity-audit.md`), which resolves the
T03.2.2 specification blockers D1–D8: no ratified source defined the
Layer 2 selection mechanism, trigger, recording surface, gate status,
consequence, rate adjustment, multi-attachment stratification, or AC2
demonstration standard. Ratified by the Project Owner as fourteen
approved decisions (2026-09-12). No frozen document is rewritten; this
layer records the binding interpretation (§1 precedence: decision
records → this layer → IOM → PKP v2 → backlog).

| Target | Annotation |
|---|---|
| **S-5 Layer 2 ("Sampled deep audit")** | Every Layer 2 row now has checkable meaning. "A configurable sample of accepted Facts" = **prospective selection at the acceptance boundary** (the R-b reading): the population is accepted Facts entering acceptance; the decision is mechanical at acceptance; the audit itself is asynchronous, non-blocking and MUST NOT become an acceptance gate. "5% of accepted Facts, stratified by source type and extraction confidence" = **one global population fraction (5%)**; source type and confidence band are stratification dimensions for measurement and allocation, **not** separate independent 5% populations — and no statistical optimality or coverage claim is made (S-5's "no empirical basis" stands). Selection = **deterministic hash-threshold**, a pure, reproducible, property-testable function of stable Fact identity plus the applicable sampling-policy version/salt (N-4-conformant: no unseeded randomness, no insertion-order dependence, no seed-pinning substitute). Strata use the ratified closed vocabularies only — `SourceType` (N-20 §5.1, 8 members, via `classify(Provenance.source_type)`) × `ConfidenceBand` (R-3, 5 bands, via `for_value(attachment.extraction_confidence)`); no new source types or bands. Multi-attachment Facts: **per-stratum eligibility with single-audit deduplication** (audited once per audit configuration/policy version), the audit unit retaining the selecting Fact **and** the specific EvidenceAttachment/source context that caused eligibility — never an arbitrary first-attachment rule, never a collapse of attachment-level confidence into `UniversalAttributes.confidence`. |
| **S-5 "Audit judgement"** | Exactly the closed three values `FAITHFUL` · `DRIFTED` · `UNSUPPORTED` (enumerated by S-5 itself). **`FAITHFUL` is never assumed by default; unaudited means no judgement exists.** The judgement is performed **externally by a human auditor**; the platform records the externally supplied judgement and performs **no semantic interpretation, NLP, LLM-based judgement, or network-based semantic verification** — the F-V4 R5 posture applied to Layer 2. |
| **S-5 "Adjustment" ("Sample rate rises…")** | **Not automated in T03.2.2.** Future adjustment is a manual owner/operator configuration action through an **immutable versioned policy/configuration record**, and **every audit record identifies the sampling-policy version under which it was selected**. No elevated-drift thresholds, formulas, statistical-significance rules or automatic adjustment algorithms are ratified — those remain outside T03.2.2. |
| **N-2 (Human Gates)** | **UNCHANGED — exactly three gates.** The Layer 2 audit is **not a fourth gate**: it decides no transition, never blocks Fact acceptance, and its judgements enter the platform as **recorded operational input** (the N-1 §5 records-does-not-adjudicate pattern). `DRIFTED`/`UNSUPPORTED` are measurement signals only: no automatic rejection, retraction, supersession, invalidation or lifecycle mutation — an UNSUPPORTED Fact remains ACTIVE unless an independent already-ratified mechanism changes it. |
| **N-10 / N-7 / CI-1 (operational records and configuration)** | The audit register extends the established register pattern (`FailureStore`, `DriftRegister` — "[N-10 — outside the model]"): an **append-only operational register outside the Intelligence Object Model**. Not created: a tenth Intelligence Object (AD-02/IOM §2.6 closed), an `AUDITS` relationship (R-06 closed ten), a new lifecycle state (R-02 closed seven), audit fields on Fact, a FeedbackRecord (FR-V6), a Validation object (M-31). The sampling policy is infrastructure state under CI-1 discipline — immutable, versioned, never in reasoning, scoring, support or lineage — and is not an engine `ConfigurationRecord` (those are per-Engine; the audit protocol is not an engine). |
| **Backlog T03.2.2** | Both ACs are given their checkable meaning by F-A1. AC1 "Sample rate configurable" = versioned `SamplingPolicy` records (initial version 1 = 5%) consumed by an installation-composition installer. AC2 "Audit detects paraphrase drift anchor checks miss" = satisfied **architecturally through an external human semantic-fidelity audit protocol**: the platform supplies the Fact/claim, qualifying context, relevant Evidence and exact anchored source span; the external auditor returns the judgement; the platform records it. The implementation MUST include a judgement-provider/interface contract and fixture-driven tests demonstrating that a **Layer-1-passing Fact can subsequently receive `DRIFTED` or `UNSUPPORTED` through Layer-2 audit**; the platform itself must not perform the semantic judgement. |
| **Mechanical pins (module count)** | The oip module-count pin is updated **37 → 38** (`oip/auditing.py`, authorized by F-A1 R12) at exactly the nine pinned sites — `verify_t02_1_1.py:214`, `verify_t02_1_2.py:226`, `verify_t02_1_4.py:193`, `verify_t02_2_1.py:287`, `verify_t02_2_2.py:248`, `verify_t02_2_3.py:258`, `verify_t02_2_4.py:285`, `verify_t02_2_5.py:256`, `verify_t03_1_2.py:457` — plus **one NEW import-set pin for `auditing.py`** in `verify_t03_1_2.py` §D. All other pins are preserved, not weakened: byte pins (claim/fact/semantic; the T02-era content pins), import sets (extraction 6/6, anchoring 3/3), DAG, ≤6-import boundary, closure Phase-1 containment, marker-register mechanics. `scripts/verify_all.sh` is untouched; its historically stale "3410 passed" unit-count pin remains stale by standing rule. |
| **M-67 / M-20** | **NOT closed by T03.2.2.** M-67 remains open ("unsampled hallucinations still reach production" — sampling measures, it does not eliminate); M-20 remains open pending `T03.2.3`. T03.2.3 (rate computation, publication, trending) is explicitly out of T03.2.2's scope and will require its own specification. |
| **S-5 Layer 2 — multi-stratum union selection probability (T03.2.2 correction pass, 2026-09-12)** | Binding interpretation, recorded on adoption of the independent T03.2.2 review: the execution specification (§7) places the stratum in the canonical sampling input, so each of a Fact's k distinct eligible strata is an independently evaluated draw at the configured rate. **POLICY_V1's configured sampling rate is 5%.** The 5% is the configured per-draw rate, **NOT a guarantee that every Fact has exactly 5% selection probability**: a Fact spanning k distinct eligible strata has union selection probability `1-(1-r)^k` (k=1 → 5%; k=2 → 9.75%; k=3 → 14.2625%), capped at one audit unit by the `(fact, policy_version)` single-audit dedup. This does **not** modify F-A1 R3 — the rate remains **one global population fraction**, a single constant in a single versioned policy with no per-stratum quotas and no separate independent 5% populations, and F-A1's disclaimer of coverage guarantees and estimator properties stands. **T03.2.3 MUST NOT assume a uniform 5% per-Fact sampling fraction without accounting for stratum multiplicity.** |
| **F-A2 Layer 3 — hallucination/drift quality metrics (T03.2.3, ratified 2026-09-12)** | Recorded on ratification of **F-A2** (`decisions/F-A2-layer3-quality-metrics.md`), which supplies the Layer-3 semantics S-5 defined in intent but F-A1 explicitly declined to ratify ("no Layer-3 semantics (rate definitions, publication, trending) are ratified by F-A1"). **Source-derived (previously ratified):** S-5 Layer 3 names two platform quality metrics — hallucination rate = proportion of audited Facts judged `UNSUPPORTED`, drift rate = proportion judged `DRIFTED` — both feeding N-3's stage-2 proxy measures, tracked as trends, reported alongside platform output; F-A1 R7's closed three-value judgement set and the `(fact, policy_version)` register dedup; the multi-stratum clarification above (unchanged by F-A2). **T03.2.3 owner decision (F-A2 OD-1–OD-8):** the denominator is judged records only (`judged = faithful + drifted + unsupported`; `hallucination_rate = unsupported/judged`, `drift_rate = drifted/judged`); pending selections and N-10 `SelectionFailure`s are excluded from the rates and published as context counts; duplicate selections create no records; both rates are `None` when `judged == 0` (never 0.0 — "zero observed hallucinations" ≠ "no judged audit observations"); scopes are global and per `policy_version` (global = disjoint union; a Fact re-audited under a newer policy is a new audit, no "winning audit" rule; no record counted twice within a scope); publication = a deterministic, queryable, frozen metric-snapshot surface derived directly from the `AuditRegister` (rates + judged/faithful/drifted/unsupported/pending/selection-failure counts + scope + policy version) — no network, telemetry, dashboards, or external services; trends use `judged_at`, sparse UTC calendar-day buckets (no empty days manufactured), ascending, insertion-order independent, global and per-version — no rolling windows, confidence intervals, significance claims, predictive models, or sampling correction formulas; the configured 5% never enters any formula; T09.1.4 owns the later general proxy machinery and phase-exit wiring; the metric extends `oip/auditing.py` beside an unchanged `AuditRegister` class (module count stays 38, zero pin changes). **Implementation status:** NOT STARTED — ratification changes no code and creates no tests. **M-20 remains OPEN** (closable only after F-A2 OD-6's seven conditions: implementation complete; ACs verified; rate computed from audit results; published on the approved surface; trend verified; gates pass; closure annotation recorded through this mechanism). **M-67 remains OPEN** with severity reduced. |
| **M-20 closure — extraction fidelity verification (T03.2.3 / F-A2 OD-6, 2026-09-12)** | **M-20 IS CLOSED by this act.** T03.2.3 is implemented and all three backlog acceptance criteria are verified with concrete test evidence: AC1 — the rate is computed from audit results (`hallucination_rate = unsupported/judged`, `drift_rate = drifted/judged` over judged records only; 31 focused tests, 91/91 green in `platform/tests/test_auditing.py`); AC2 — published as a platform quality metric (the deterministic, queryable, frozen `QualityMetricSnapshot` surface via `quality_metrics()`/`metric_trend()` on `oip/auditing.py`, module count unchanged at 38); AC3 — trend trackable over time (the ratified `judged_at` / sparse UTC-day series semantics, tests rows 14–18). **F-A2 was ratified 2026-09-12 BEFORE implementation** — governance preceded code; no production semantics were invented during implementation. The seven F-A2 OD-6 closure conditions are satisfied: (1) implementation complete; (2) all acceptance criteria verified; (3) the hallucination-rate metric is computed from audit results; (4) the metric is published on the approved platform surface; (5) trend tracking is verified; (6) the required verification gates passed (3791 passed / 0 failed / 128 deselected; coverage 99.2% total and 100% on `auditing.py`; verifier landscape unchanged except the protected/pre-existing stale pins and worktree-state check); (7) this closure annotation, recorded through the established governance mechanism — this annotation layer plus the marker register (`docs/markers/MARKER-REGISTER.md`: Closed in Phase 3, by **F-A2**; missing-definition counts now 23 closed / 43 open). **This closure applies to M-20 ONLY and does NOT close M-67:** M-67 remains OPEN with severity reduced (S-5: sampling measures, it does not eliminate — unsampled hallucinations still reach production; the register's partial-closure row stands). **T09.1.4 remains a separate future task and boundary** (general stage-level proxy machinery and phase-exit wiring — deliberately not implemented by T03.2.3). **No sampling-rate correction was introduced and T03.2.2 semantics remain unchanged** (F-A1 R1–R12 intact; the 60 T03.2.2 tests green and unmodified; the 5% is a per-draw constant that never enters a metric; the multi-stratum union clarification stands). Frozen documents are not rewritten; this row and the register update are the closure record. |
