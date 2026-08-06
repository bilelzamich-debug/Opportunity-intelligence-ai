# Canonical Marker Identifier Crosswalk

**Status:** Authoritative. This is the **canonical mapping** for all marker identifiers across project documents.
**Established by:** `T00.1.2`
**Source:** Pre-P1 Blocker Resolution §0.1–§0.2, extended by direct extraction from the Intelligence Object Model.

---

## 1. The Problem

The Intelligence Object Model (IOM) was drafted against an intermediate marker numbering that diverged from the canonical register in PKP v2 §11–§13. The **substance** of every IOM statement is sound; the **identifiers** are unreliable.

Left uncorrected, a decision recorded against "MISSING-25" would attach to *validation methodology* if read against the IOM, or to *pattern type taxonomy* if read against PKP v2. Marker closure would be unverifiable, and the register's guarantee that markers are closed only by recorded decision would be void.

## 2. Canonical Authority

**PKP v2 §11 (contradictions), §12 (open questions) and §13 (missing definitions) are canonical.**

All other documents defer to v2 numbering. Where the IOM cites a different identifier for the same substance, the v2 identifier governs.

Three marker families extend v2:

| Range | Origin | Status |
|---|---|---|
| `M-01` … `M-57` | PKP v2 §13 | Canonical |
| `M-58` … `M-67` | IOM §5.2 (new gaps found during object specification) | Canonical — no collision, v2 ended at M-57 |
| `M-68` … `M-70` | Blocker Resolution §0.2 (substance had no v2 identifier) | Canonical — newly assigned |
| `OQ-01` … `OQ-17` | PKP v2 §12 | Canonical |
| `OQ-18` … `OQ-21` | Blocker Resolution §0.2 | Canonical — newly assigned |
| `OQ-22` … `OQ-24` | `T00.1.2` (IOM collisions resolved) | Canonical — newly assigned |
| `C-01` … `C-08` | PKP v2 §11 | Canonical |

## 3. Collision Table

Ten collisions, where an IOM identifier denotes different substance from the same identifier in v2. **Eight were catalogued in Blocker Resolution §0.2; two further collisions (marked ⊕) were discovered during this task by exhaustive extraction of IOM references.**

| # | IOM cites | IOM substance | Canonical ID | v2's own meaning for that number | Risk if unmapped |
|---|---|---|---|---|---|
| 1 | `MISSING-35` | Object model has no attributes | **M-68** | *(v2 M-35: Orchestration control model)* | Would close the wrong gap |
| 2 | `MISSING-32` | Relationship taxonomy | **M-40** | *(v2 M-32: Validation methodology)* | Would close the wrong gap |
| 3 | `MISSING-25` | Validation methodology | **M-32** | *(v2 M-25: Pattern type taxonomy)* | Would close the wrong gap |
| 4 | `MISSING-18` | Source taxonomy / trust | **M-16** | *(v2 M-18: Legal, licensing, terms-of-use)* | Would close the wrong gap |
| 5 | `MISSING-22` | Source diversity to Pattern | **M-23** | *(v2 M-22: Problem identity and dedup)* | Would close the wrong gap |
| 6 | `MISSING-26` | Gate ownership | **M-31** | *(v2 M-26: Definition of "opportunity")* | Would close the wrong gap |
| 7 | `MISSING-31` | Retention policy | **M-38** | *(v2 M-31: Post-validation promote/reject owner)* | Would close the wrong gap |
| 8 | `MISSING-36` | Outcome intake mechanism | **M-47** | *(v2 M-36: Failure-handling policy)* | Would close the wrong gap |
| 9 ⊕ | `MISSING-23` | Opportunity selection mechanism | **M-28** | *(v2 M-23: Source diversity accounting)* | Would close the wrong gap |
| 10 ⊕ | `MISSING-34` | Home for engine configuration | **M-63** | *(v2 M-34: Learning update reversion)* | Would close the wrong gap |

⊕ **Discovered during `T00.1.2`.** Blocker Resolution §0.2 catalogued eight collisions. Exhaustive extraction of all 36 distinct `MISSING-nn` references in the IOM revealed two more. Both are recorded here and §0.2 is superseded by this table.

**Note on #9 and #10.** IOM `MISSING-23` (opportunity selection, IOM §3.5 Opportunity lifecycle) maps to canonical **M-28** "Owner of solution selection". IOM `MISSING-34` is cited *within* IOM MISSING-63 as "PKP v2 MISSING-34" for the configuration home; canonical **M-63** is the correct identifier for that gap, and v2's actual M-34 is learning update reversion — an unrelated concern.

## 4. Full Reference Map

Every distinct marker reference appearing in the IOM, with its canonical identifier. Verified complete by extraction.

### 4.1 MISSING references (36 distinct)

| IOM | Canonical | Substance | Relation |
|---|---|---|---|
| MISSING-02 | **M-02** | Learning target (write target half: **M-43**) | Match |
| MISSING-04 | **M-04** | Success criteria | Match |
| MISSING-06 | **M-06** | Evidence sufficiency | Match |
| MISSING-08 | **M-08** | Object mutability | Match |
| MISSING-11 | **M-11** | Fact identity / dedup | Match |
| MISSING-12 | **M-12** | Problem attributes | Match |
| MISSING-13 | **M-13** | Pattern temporal validity | Match |
| MISSING-14 | **M-14** | Scoring | Match |
| MISSING-15 | **M-15** | Confidence model | Match |
| MISSING-18 | **M-16** | Source taxonomy / trust | **Collision 4** |
| MISSING-22 | **M-23** | Source diversity to Pattern | **Collision 5** |
| MISSING-23 | **M-28** | Opportunity selection mechanism | **Collision 9 ⊕** |
| MISSING-24 | **M-69** | Constraint model | New — no v2 equivalent |
| MISSING-25 | **M-32** | Validation methodology | **Collision 3** |
| MISSING-26 | **M-31** | Gate ownership | **Collision 6** |
| MISSING-27 | **M-70** | Feedback instability guard | New — no v2 equivalent |
| MISSING-31 | **M-38** | Retention policy | **Collision 7** |
| MISSING-32 | **M-40** | Relationship taxonomy | **Collision 2** |
| MISSING-34 | **M-63** | Engine configuration home | **Collision 10 ⊕** |
| MISSING-35 | **M-68** | Object model has no attributes | **Collision 1** |
| MISSING-36 | **M-47** | Outcome intake | **Collision 8** |
| MISSING-39 | **M-39** | Store/Graph consistency model | Match |
| MISSING-45 | **M-45** | Lifecycle / status states | Match |
| MISSING-46 | **M-46** | Temporal validity | Match |
| MISSING-47 | **M-47** | Outcome verification | Merged with collision 8 |
| MISSING-57 | **M-57** | Observability (cited as v2 upper bound) | Match |
| MISSING-58 | **M-58** | Cascade invalidation owner | IOM-originated |
| MISSING-59 | **M-59** | Evidential support function | IOM-originated |
| MISSING-60 | **M-60** | Confidence calibration | IOM-originated |
| MISSING-61 | **M-61** | Staleness assessment owner | IOM-originated |
| MISSING-62 | **M-62** | Semantic equivalence criterion | IOM-originated |
| MISSING-63 | **M-63** | Engine configuration home | IOM-originated (same gap as collision 10) |
| MISSING-64 | **M-64** | Acceptance authority | IOM-originated |
| MISSING-65 | **M-65** | Re-derivation policy | IOM-originated |
| MISSING-66 | **M-66** | Lineage summarisation | IOM-originated |
| MISSING-67 | **M-67** | Hallucination detection | IOM-originated |

### 4.2 OPEN QUESTION references (16 distinct)

| IOM | Canonical | Substance | Relation |
|---|---|---|---|
| OPEN QUESTION-03 | **OQ-03** | Contradictory evidence | Match |
| OPEN QUESTION-04 | **OQ-04** | Rejected candidates | Match |
| OPEN QUESTION-05 | **OQ-05** | Learning update approval | Match |
| OPEN QUESTION-13 | **OQ-13** | Concurrency | Match — IOM also cites this as OPEN QUESTION-23 |
| OPEN QUESTION-14 | **OQ-22** | Fact re-extraction | Renumbered — v2 OQ-14 is Experiment Registry scope |
| OPEN QUESTION-17 | **OQ-23** | Pattern-to-pattern relationships | Renumbered — v2 OQ-17 is P7 phase structure |
| OPEN QUESTION-20 | **M-29** | Solution depth / granularity | Subsumed — canonical M-29 "Solution granularity" |
| OPEN QUESTION-21 | **OQ-18** | Cross-stage read access | Renumbered |
| OPEN QUESTION-22 | **OQ-24** | Feedback application mechanism | Renumbered — OQ-22 reassigned to Fact re-extraction |
| OPEN QUESTION-23 | **OQ-13** | Concurrency | Renumbered |
| OPEN QUESTION-25 | **OQ-12** | Evidence full vs reference | Renumbered |
| OPEN QUESTION-28 | **M-16** | Source trust attribute | Subsumed into source model |
| OPEN QUESTION-29 | **OQ-19** | Score point-in-time vs recomputed | Renumbered |
| OPEN QUESTION-33 | **OQ-33** | *(cited as v2 upper bound)* | Match |
| OPEN QUESTION-34 / OQ-34 | **OQ-20** | Ceiling min vs weighted | Renumbered |
| OPEN QUESTION-35 / OQ-35 | **OQ-21** | Pattern constituent versioning | Renumbered |

> **Resolved during validation.** Four IOM open-question identifiers collided with canonical v2 assignments and have been corrected above: IOM `OPEN QUESTION-14` (Fact re-extraction) → **OQ-22**, since canonical `OQ-14` is Experiment Registry scope; IOM `OPEN QUESTION-17` (pattern-to-pattern) → **OQ-23**, since canonical `OQ-17` is P7 phase structure; IOM `OPEN QUESTION-20` (solution depth) → **M-29**, which already covers solution granularity; IOM `OPEN QUESTION-22` (feedback application) → **OQ-24**, freeing OQ-22. Both IOM `OPEN QUESTION-23` and `OPEN QUESTION-13` denote concurrency and map to the single canonical **OQ-13**.
>
> **New canonical identifiers assigned by this task:** `OQ-22` (Fact re-extraction), `OQ-23` (pattern-to-pattern relationships), `OQ-24` (feedback application mechanism). The canonical open-question range is now `OQ-01`…`OQ-24`.

### 4.3 CONTRADICTION references (6 distinct)

| IOM | Canonical | Substance | Relation |
|---|---|---|---|
| CONTRADICTION-02 | **C-02** | Execution stage has no engine | Match |
| CONTRADICTION-03 | **C-03** | Feedback has no object | Match |
| CONTRADICTION-04 | **C-04** | Feedback → Evidence | Match |
| CONTRADICTION-05 | **C-05** | Validation vs Experiment Registry | Match |
| CONTRADICTION-06 | **C-06** | Store / Graph boundary | Match |
| CONTRADICTION-08 | **M-68** | Object model has no attributes | **Collision 1** — v2 C-08 is *Orchestration has no roadmap phase* |

## 5. Uniqueness Verification

**No canonical identifier in this crosswalk denotes two different gaps.** Verified programmatically during `T00.1.2`: 53 canonical identifiers, of which exactly two carry more than one source reference, both intentional merges. each canonical ID appears in the "Canonical" column for exactly one substance, with two intentional many-to-one mappings:

| Canonical | Merged sources | Justification |
|---|---|---|
| **M-47** | IOM MISSING-36 (intake) + MISSING-47 (verification) | Single gap: outcome intake *and* its verification are one unresolved mechanism |
| **M-16** | IOM MISSING-18 (taxonomy) + OPEN QUESTION-28 (source trust) | Source trust is an attribute of the source model, not a separable gap |

Both merges are recorded in Blocker Resolution §0.2 and carried forward unchanged.

### 5.1 Partial Closures — P2 Decision Set (2026-08-04)

Recorded on ratification of N-20…N-23. Partial closure follows established
practice: S-5 `Closes | M-67 (partially)`; R-8 `Closes | C-04 (jointly with
AD-05)`.

| Canonical | Closed by | Closed portion | Remaining open |
|---|---|---|---|
| **M-16** | N-20 | Source-type taxonomy, per-type eligibility, trust representation | Trust **scoring** (requires superseding S-2); learnability (M-02 / M-43) |
| **M-17** | N-22 | Coverage and completeness concepts | **Stopping** — "when has it researched enough" → M-01 |
| **M-18** | N-21 | Rights half: legality, licensing, terms of use, retention rights | **M-18b** conduct half (robots, rate limits); v2 §14 "compliance" scope |
| **M-01** | N-23 | Initiation, originators, trigger lifecycle, scoping, cancellation | Self-direction (no canonical ID); target approval (blocked by N-2) |
| **OQ-28** | N-20 | Source trust attribute — **fully closed** (subsumed into M-16 per §5) | — |

**New identifier reserved:** **M-18b** — acquisition *conduct* (robots,
rate limits). Split from M-18 on ratification of N-21, which closes the rights
half only. The §5 uniqueness invariant is preserved: M-18 and M-18b denote
disjoint substance.

## 6. Standing Rule

**From this point, all project artefacts cite canonical identifiers only.**

- Decision records cite canonical IDs.
- Marker closures reference canonical IDs.
- The Implementation Backlog's marker citations are interpreted through this crosswalk.

The IOM's internal marker references are **not** rewritten in place. The IOM is a frozen authoritative document; amending its text would break the freeze for a clerical reason. This crosswalk is the interpretation layer, and it is authoritative over the IOM's identifiers.

## 7. Impact on Prior Work

`T00.1.1` recorded AD-01…AD-04, which cite `MISSING-50`, `CONTRADICTION-01/02/03/04/06`, `MISSING-02`, `MISSING-23`, `MISSING-26`, `MISSING-28`, `MISSING-31`, `MISSING-34`, `MISSING-68`.

Reviewed against this crosswalk:

| Cited in AD records | Canonical | Correct as cited? |
|---|---|---|
| MISSING-50 (no decision records) | M-50 | Yes |
| CONTRADICTION-01/02/03/04/06 | C-01/02/03/04/06 | Yes |
| MISSING-02 (learning target) | M-02 | Yes |
| MISSING-26, MISSING-28, MISSING-31 (AD-04 voids) | M-26/M-28/M-31 | Yes — cited from **v2 §8.6**, already canonical |
| MISSING-23 (AD-02 source diversity) | M-23 | Yes — cited from **v2 §8.4**, already canonical |
| MISSING-34 (AD-03 reversion) | M-34 | Yes — cited from **v2 §8.5**, already canonical |
| CONTRADICTION-08 / MISSING-68 (AD-02) | M-68 | Yes — cited as the pair, unambiguous |

**No correction required.** The AD records were written from PKP v2 §8, which uses canonical numbering throughout. The collisions are confined to the IOM.
