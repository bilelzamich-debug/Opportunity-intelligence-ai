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
