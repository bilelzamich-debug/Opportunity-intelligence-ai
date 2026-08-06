# Glossary

Every term, identifier and marker used in this repository.

---

## 1. Identifier Systems

| Prefix | Meaning | Example |
|---|---|---|
| `AD-nn` | Architecture Decision (foundational) | `AD-05` Ground Truth Protection |
| `R-n` | Ratification of an IOM decision D-01…D-08 | `R-2` seven-state lifecycle |
| `N-nn` | Scope / boundary / control decision | `N-20` source model |
| `S-n` | Semantics decision | `S-2` evidential support function |
| `M-nn` | **Missing definition** — a specification gap | `M-16` source taxonomy |
| `OQ-nn` | **Open question** | `OQ-28` source trust attribute |
| `C-nn` | **Contradiction** in the source corpus | `C-02` Execution has no engine |
| `B-nn` | Blocker (Pre-P1 analysis; **never ratified**) | `B-33` source taxonomy |
| `Tpp.f.s` | Backlog task — phase.feature.sequence | `T02.1.1` |
| `AS-n` | Recorded reservation attached to a ratified decision | `AS-1` gate order selected |
| `D-n` | Discovered discrepancy between ratified sources | `D-1` missing human gate |
| `V1…V12` | Universal validation rules (acceptance-time) | `V5` confidence ceiling |
| `I1…I8` | Universal integrity constraints (continuous) | `I6` cascade invalidation |
| `E-Vn`, `F-Vn`, `P-Vn`, `PT-Vn`, `O-Vn`, `S-Vn`, `V-Vn`, `X-Vn`, `FR-Vn` | Per-type validation rules | `E-V6` duplicate detection |
| `GX-n` | Governance exception found in review | `GX-2` invalid citation |

**Critical:** a marker is closed **only** by a ratified decision record.
Implementing around a gap does not close it (Playbook F3).

---

## 2. Core Concepts

**Intelligence Object** — One of exactly nine persisted types. The sole
inter-engine contract surface (AD-02). Fixed at nine (Playbook F8).

**Evidence** — The grounding layer. The only object type with no upstream
lineage; that property is definitional and makes every lineage trace terminate.

**Lineage** — The `DERIVES_FROM` chain from any object back to Evidence.
Objects are authoritative for their own lineage (N-6); the graph is a derived,
rebuildable index.

**Marker** — A recorded gap, question or contradiction in the specification.
The register's central device for making unknowns visible.

**Fail closed** — When the specification is silent, refuse the operation and
name the blocking marker rather than inventing behaviour.

**Partial closure** — A decision closing part of a marker, with the remainder
explicitly enumerated. Precedent: S-5 `Closes | M-67 (partially)`.

**Ratified** — Agreed and binding. Records are **immutable once ratified**;
change happens by a superseding record, never by editing in place.

---

## 3. The Nine Object Types

| # | Type | Stage | Create authority |
|---|---|---|---|
| 1 | Evidence | 1 | Research |
| 2 | Fact | 2 | Fact Extraction |
| 3 | Problem | 3 | Problem Intelligence |
| 4 | Pattern | 4 | Pattern Intelligence |
| 5 | Opportunity | 5 | Opportunity Intelligence |
| 6 | Solution | 6 | Solution Intelligence |
| 7 | Validation | 7 | Validation |
| 8 | Execution Record | 8 | **None — C-02 open** |
| 9 | Feedback Record | 9 | Feedback |

`CREATE_AUTHORITY` has **8 entries**; Execution Record is deliberately absent
because C-02 is unresolved. V7 fails closed for it.

---

## 4. The Seven Lifecycle States (R-2)

`PROPOSED` · `ACTIVE` · `SUPERSEDED` · `REJECTED` · `RETRACTED` ·
`INVALIDATED` · `ARCHIVED`

- Terminal states never transition.
- Evidence **cannot** reach `INVALIDATED` (nothing upstream can invalidate it).
- Exactly one `ACTIVE` version per `lineage_id` (I5).
- **Cascade triggers are `RETRACTED` and `INVALIDATED` only.** `SUPERSEDED`
  does not cascade (M-65 open).

---

## 5. The Ten Relationship Types (R-6)

`DERIVES_FROM` · `SUPPORTS` · `CONSTITUENT_OF` · `ADDRESSES` · `TESTS` ·
`OUTCOME_OF` · `SUPERSEDES` · `DUPLICATES` · `CONTRADICTS` · `INFORMS`

Closed set. `DERIVES_FROM` and `SUPPORTS` are deliberately distinct: an object
*derives from* what its engine read, and is *supported by* the subset that
evidences it.

---

## 6. Confidence (R-3, S-1, S-2)

**Two components, never conflated:**
- `evidential_support` — how much independent external observation stands behind this
- `assertion_confidence` — how certain the engine is in its own inference

**`effective_confidence` ≤ min(upstream effective_confidence)** — the ceiling
rule (V5). Evidence sets the ceiling; nothing constrains it from above.

**Five bands (S-1):** NEGLIGIBLE 0.00–0.19 · WEAK 0.20–0.39 · MODERATE
0.40–0.59 · STRONG 0.60–0.79 · VERY_STRONG 0.80–1.00

**S-2's five exhaustive inputs** — independent source count · source diversity ·
corroboration depth · contradiction presence · upstream support.
**"No other input."** Source trust is *not* among them.

---

## 7. Phase 2 Vocabulary (N-20 … N-23)

### Source types (N-20 §5.1) — closed, eight members

`PUBLISHED_EDITORIAL` · `MARKETPLACE_LISTING` · `USER_GENERATED_REVIEW` ·
`USER_GENERATED_DISCUSSION` · `SUPPORT_INTERACTION` · `STRUCTURED_DATASET` ·
`REGULATORY_FILING` · `VENDOR_PUBLICATION`

Taxonomy is by **acquisition channel** — the medium through which material
reached the platform. Exactly one member per source.

### Acquisition gate sequence (N-20 §5.2.1)

| # | Gate | Refusal reason |
|---|---|---|
| 1 | Scope | `OUT_OF_SCOPE` |
| 2 | Typability | `UNTYPABLE_CHANNEL` |
| 3 | Rights | `REFUSED_BY_RIGHTS` |

Evaluated in fixed order; **halts at the first refusal**, so exactly one reason
is ever produced.

### Rights vocabulary (N-21 §5.5) — closed

**Acquisition:** `PERMITTED` · `PROHIBITED` · `UNASSESSED`
**Retention:** `RETAIN_FULL` · `RETAIN_REFERENCE_ONLY` · `RETAIN_NONE` · `UNASSESSED`

`UNASSESSED` **fails closed** — silence is not permission.

### Coverage vocabulary (N-22)

**Gap reasons:** `NOT_ATTEMPTED` · `INACCESSIBLE` · `REFUSED_BY_RIGHTS` ·
`NO_MATERIAL_FOUND` · `OUT_OF_SCOPE`

`coverage = |represented members| / |frame|` · `out_of_frame` = count of
sources refused at gate 2, reported **beside** coverage so a figure of 1.0 can
never conceal a refused class.

### Directive states (N-23 §5.6)

`RAISED` · `IN_EFFECT` · `FULFILLED` · `CANCELLED` · `EXPIRED`

**Deliberately disjoint from R-2's seven object states** — a reader
encountering `ACTIVE` anywhere knows it means an Intelligence Object.

### Directive originators (N-23 §5.3) — closed

`EXTERNAL_COMMISSION` · `FEEDBACK_RESEARCH_TRIGGER` · `VALIDATION_BACKFLOW`

The platform **never self-initiates** research.

---

## 8. Key Invariants

| ID | Statement |
|---|---|
| **CI-1** | Configuration is infrastructure state, never intelligence. It must never participate in reasoning, scoring, pattern detection or lineage |
| **Article IV / AD-05** | No platform-generated artifact may become Evidence directly |
| **Article X** | The platform states what it does not know. Known gaps are recorded with the same standing as favourable findings |
| **Article XI** | Precedence: Constitution → decision records → annotations → IOM → PKP v2 → Backlog |
| **N-4** | Inputs are reproducible; **outputs are not guaranteed deterministic**. Tests assert properties, never equality |

---

## 9. Forbidden Actions (Playbook §2)

| # | Forbidden |
|---|---|
| F1 | Redesigning the architecture |
| F2 | Making an architectural decision yourself |
| F3 | Closing a marker by implementation choice |
| F4 | Skipping acceptance criteria |
| F5 | Rewriting frozen documents |
| F6 | Self-approving an escalation |
| F7 | Starting a task with incomplete dependencies |
| F8 | Adding an engine, object, stage, component or principle |
| F9 | Letting configuration participate in reasoning |
| F10 | Allowing platform output to become Evidence |
| F11 | Asserting equality in tests |
| F12 | Silently proceeding past a contradiction |

---

## 10. Discovered Discrepancies

| ID | Discrepancy | Status |
|---|---|---|
| **D-1** | `T02.2.4` AC2 requires a human gate; N-2 fixes exactly three, none covering research | **BLOCKING** — awaiting Project Owner |
| **D-2** | B-59 attributes self-direction to OQ-07, but canonical OQ-07 is "May Pattern Intelligence read Facts directly?" | Open — no canonical ID exists |
| **D-3** | IOM annotates `access_conditions` with "OPEN QUESTION-13", but canonical OQ-13 is *concurrency*, closed by N-11 | Recorded in annotations §10 |
| **D-4** | IOM §3.4 defines `source_diversity` as a count of *sources*; S-2 input 2 defines it as *types* | Blocks clean PT-V4 |

---

## 11. Marker Crosswalk Traps

The IOM was drafted against an intermediate numbering. **Ten collisions** exist
where an IOM identifier denotes different substance from the same identifier in
PKP v2. The most dangerous:

| IOM cites | IOM means | Canonical | v2's own meaning |
|---|---|---|---|
| `MISSING-18` | Source taxonomy / trust | **M-16** | Legal / licensing / ToU |
| `MISSING-25` | Validation methodology | **M-32** | Pattern type taxonomy |
| `MISSING-31` | Retention policy | **M-38** | Post-validation promote/reject owner |
| `MISSING-36` | Outcome intake | **M-47** | Failure-handling policy |

**Always resolve through `marker-crosswalk.md` before citing a marker.**
