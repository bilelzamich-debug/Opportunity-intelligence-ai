# N-20 — Source Model: Closed Taxonomy by Acquisition Channel, with Non-Scoring Trust

| Field | Value |
|---|---|
| **ID** | N-20 |
| **Title** | Source Model: Closed Taxonomy by Acquisition Channel, with Non-Scoring Trust |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-04 |
| **Date decided** | 2026-08-04 |
| **Source** | PKP v2 §9, §13; IOM §3.1, §5.2; Blocker Resolution B-33; marker-crosswalk §3 #4, §5 |
| **Closes** | **M-16 (partially)** — see *Markers Closed* and *Markers Left Open* |
| **Backlog task** | `T02.1.1` |
| **Depends on** | AD-01, AD-05, R-1, R-3, N-04, N-07, N-15, N-16, S-02, S-04 |
| **Supersedes** | — |
| **Superseded by** | — |

> 🔺 **ESCALATION — RATIFIED 2026-08-04.** Approved by the Project Owner.
> Ratified with recorded reservations; see *Honest Limitations*.
> Owning task `T02.1.1` carries an escalation flag, satisfying `AGENT-PLAYBOOK` F6.

---

## 1. Problem Restated

M-16 must resolve three things, and nothing else:

1. **A closed source-type taxonomy** — the exhaustive member set for the
   required Evidence attribute `source_type`, which IOM §3.1 annotates
   "(MISSING-18: no taxonomy exists)".
2. **Per-type eligibility** — whether a source of a given type may be
   acquired from at all.
3. **A trust model** — how source reliability is represented, since
   crosswalk §5 subsumes OQ-28 ("Source trust attribute") into M-16.

PKP v2 §9 states the stakes: *"Since all platform trust derives from evidence
quality, and no engine assesses source quality, weak and strong sources are
structurally indistinguishable throughout the platform. This is the
highest-severity omission in the engine set."*

**Out of scope by construction.** M-18 (legal/licensing) is a distinct marker
owned by `T02.1.2` — crosswalk collision #4 warns that conflating them "would
close the wrong gap". M-02/M-43 (learning targets) are P8 markers.

---

## 2. Ratified Constraints Extracted

Every constraint below is quoted or directly cited. No constraint is
introduced.

| # | Constraint | Source | Binding effect on this decision |
|---|---|---|---|
| C1 | "`source_type` \| Category of source" — **required** attribute | IOM §3.1 | The taxonomy must populate an attribute that already exists and is mandatory |
| C2 | "`source_reliability` \| Trust assessment of the source (OPEN QUESTION-28)" — **optional** | IOM §3.1 | Trust has a home already; making it required would amend a frozen contract |
| C3 | "`source_identifier` \| Stable identifier of the origin, **sufficient to assess independence**" | IOM §3.1 | Trust and independence key on `source_identifier`, not on type |
| C4 | Inputs to `evidential_support` are five, and **"No other input."** | S-02 | Trust **may not** feed scoring without superseding S-02 |
| C5 | Input 2 = "Number of **distinct source *types*** represented"; P3 "*n* sources of one type yield less than *n* across types" | S-02 | The taxonomy must be a **partition** whose members are countable and meaningfully distinct |
| C6 | "Independent means after independence grouping (`T02.1.3`): syndicated or commonly-owned sources count once" | S-04 | Type ≠ independence. They are orthogonal axes |
| C7 | Tier 2 traversal yields "which source *types*"; revisit may promote "a small **type-vector** into Tier 1" | N-16 | Types must be a small, enumerable set |
| C8 | "1 Evidence \| Provenance completeness; duplicate rate; **source-type coverage**" | N-03 | Coverage is measured per type ⇒ the set must be finite and known in advance |
| C9 | "5% of accepted Facts, stratified by **source type**" | S-05 | Types must partition Facts, i.e. every source has exactly one type |
| C10 | Evidence "stored in full **where licensing permits**, by reference otherwise" | N-15 | Storage mode is licence-driven, **not** type-driven. The taxonomy must not encode licensing |
| C11 | "Configuration … must never participate in reasoning, scoring, pattern detection, or lineage" | CI-1 / N-07 | A trust registry must not become a scoring input |
| C12 | Reproducible inputs; `engine_configuration_ref` must resolve at any historical point | N-04 | Trust ratings must be immutable and versioned |
| C13 | Objects immutable; change produces a new version | R-1 | Trust records are append-only |
| C14 | "No platform-generated artifact may become Evidence directly" | AD-05 / Art. IV | A trust rating is metadata *about* a source, never Evidence |
| C15 | Evidence "sets the ceiling for everything downstream"; no upstream constrains it | R-3 / IOM §3.1 | Trust cannot be inserted into the ceiling arithmetic |
| C16 | "Nine engines, nine objects, ten stages, three components, five principles. Fixed." | Playbook F8 | The source model must not become a tenth object |
| C17 | Closed vocabularies are enumerated by decision; "Extension requires a superseding decision record, never an inline addition" | R-2, R-6 precedent | The member list must live **in this record** |
| C18 | "A marker … is closed only by a record in this register" | README §L145, Playbook F3 | Only this record — not code — can close M-16 |

---

## 3. Design Space

Four architectures remain legally compatible with C1–C18. (B-33's Option 1
"open — any accessible source" is excluded: it leaves `source_type` unscoped,
failing C5, C8 and C9, which all require a countable partition.)

### Option A — Taxonomy by **subject domain**
*(e.g. `retail`, `finance`, `healthcare`)*

- **Advantages.** Intuitive; aligns with market-research vocabulary.
- **Disadvantages.** Fails C5/P3 decisively: two sources in the same domain
  may be wholly independent channels, so domain-counting does not measure
  sampling artefact. Domains are open-ended, breaching C17's closure
  requirement.
- **Affected decisions.** Would weaken S-02 P3's stated purpose.
- **Affected tasks.** `T02.1.4`, `T05.1.4` would measure the wrong thing.
- **Migration cost.** High — domain lists expand continuously.
- **Extensibility.** Poor: every new market needs a superseding record.

### Option B — Taxonomy by **acquisition channel**
*(the medium through which material reached the platform)*

- **Advantages.** Directly serves C5/P3: sampling artefact is a *channel*
  phenomenon — ten reviews from one review-site are one channel. Satisfies C9
  (every source has exactly one channel). Small and stable (C7). Orthogonal
  to independence (C6) and to licensing (C10).
- **Disadvantages.** Channel boundaries need judgement at the margin; a
  source reachable two ways must be assigned one.
- **Affected decisions.** None superseded; supplies what S-02, N-03, N-16,
  S-05 already assume.
- **Affected tasks.** Unblocks `T02.1.1` AC1; feeds `T02.1.4`, `T02.3.1`.
- **Migration cost.** Low — the attribute already exists (C1).
- **Extensibility.** Good: new channels are rare and additive via superseding
  record (C17).

### Option C — Taxonomy by **legal/licensing regime**
*(e.g. `public_domain`, `licensed`, `restricted`)*

- **Advantages.** Would serve `T02.1.2` directly.
- **Disadvantages.** **Violates C10.** N-15 makes storage mode licence-driven
  and *separate* from type; encoding licensing into `source_type` collapses
  M-16 and M-18, which crosswalk #4 explicitly forbids. Also fails C5: licence
  regime says nothing about sampling diversity.
- **Affected decisions.** Would force superseding N-15.
- **Migration cost.** High. **Legally non-compliant with the corpus.**

### Option D — Free-text with a registry of observed values

- **Advantages.** Zero upfront specification.
- **Disadvantages.** Not a *closed* taxonomy (backlog AC1); fails C17. A typo
  registers as new diversity, defeating C5/P3 — the precise failure S-02 P3
  exists to prevent.
- **Migration cost.** Low now, unbounded later.
- **Extensibility.** Illusory: it defers the decision permanently.

---

## 4. Selection

**Option B — taxonomy by acquisition channel.**

Justified only from the existing architecture:

- **Minimises future superseding decisions.** It supplies exactly what C5,
  C7, C8 and C9 already presuppose, so no ratified record needs amendment.
  Options A and D would require revisiting S-02's purpose; Option C would
  require superseding N-15.
- **Minimises coupling.** Channel is orthogonal to independence (C6) and to
  licensing (C10), keeping M-16, M-18 and `T02.1.3` on separate axes.
- **Minimises ambiguity.** C9 demands a partition; channel gives every source
  exactly one type. Domain (A) and free text (D) do not.
- **Minimises architectural debt.** The attribute exists (C1), the range for
  trust exists (C2), and no new object is introduced (C16).

---

## 5. DECISION

### 5.1 Taxonomy — closed, by acquisition channel

`source_type` is drawn from this **closed set of eight members**. Extension
requires a superseding decision record; inline addition is prohibited (C17).

| Member | Definition |
|---|---|
| `PUBLISHED_EDITORIAL` | Material published by an identified editorial body |
| `MARKETPLACE_LISTING` | Listings, catalogue or transactional records from a marketplace |
| `USER_GENERATED_REVIEW` | Reviews or ratings authored by end users |
| `USER_GENERATED_DISCUSSION` | Forum, community or discussion-thread material |
| `SUPPORT_INTERACTION` | Complaint, support-ticket or service-transcript material |
| `STRUCTURED_DATASET` | Datasets published as data, including public and licensed corpora |
| `REGULATORY_FILING` | Filings or disclosures lodged with a regulatory body |
| `VENDOR_PUBLICATION` | Material published by a vendor about its own offering |

**Exactly one member applies per source.** A source reachable through more
than one channel is typed by the channel actually used at acquisition and
recorded in `acquisition_method`.

**Assignment authority.** The **Research Engine** assigns `source_type` at
acquisition. This introduces no new authority: IOM §2.5 already gives Research
sole create authority for Evidence.

### 5.2 Eligibility — per type, with a fail-closed default

| Member | Eligible for acquisition |
|---|---|
| All eight members above | **Yes**, subject to M-18 |

**A source whose channel does not map to a member is INELIGIBLE and must be
refused.** This is the operative rule: eligibility under M-16 is *typability*.

**Scope boundary, stated explicitly.** Eligibility here means "is this kind of
channel admissible as grounding at all". **Legal admissibility — licensing,
robots, rate limits, terms of use — is M-18 and remains OPEN** (C10,
crosswalk #4). An M-16-eligible source may still be refused on rights. Every
gate in the sequence of §5.2.1 must pass.

**A refusal under this gate is reportable.** An untypable source is by
definition outside the taxonomy, so it corresponds to no frame member and
cannot appear as a coverage gap. It must therefore be recorded as an
**out-of-frame refusal**, so that refusing a whole class of material can never
present as complete coverage. The reporting obligation is discharged by the
coverage model; this clause creates the duty, not the mechanism.
[Art. X — the platform states what it does not know]

#### 5.2.1 Deterministic acquisition gate sequence

Three ratified gates precede acquisition. They are evaluated in **this fixed
total order**, and **evaluation halts at the first refusal**:

| # | Gate | Question | Refusal reason |
|---|---|---|---|
| **1** | **Scope** | Does an in-effect research directive cover this target? | `OUT_OF_SCOPE` |
| **2** | **Typability** (this record, §5.2) | Does the source map to a taxonomy member? | `UNTYPABLE_CHANNEL` |
| **3** | **Rights** | May this material be taken and kept? | `REFUSED_BY_RIGHTS` |

**Why this order, from the corpus.** It narrows from cycle to class to
instance, and it matches the pre-attempt / post-attempt split the coverage
vocabulary already draws: scope exclusion precedes any attempt, whereas a
rights refusal presupposes a specific target was identified. Orchestration
populates each cycle's work set from directives before any source is examined,
so scope is logically prior to any property of the source itself.

**Determinism proof.** The gates form a finite, totally ordered list. Evaluation
proceeds in index order and returns on the first refusal. Therefore for any
source, *exactly one* gate can produce the outcome — the lowest-indexed failing
gate — regardless of how many gates would fail if evaluated independently. If
no gate refuses, acquisition proceeds. The outcome is a total function of the
source and the gate states, so two conforming implementations cannot disagree.

*Authority note.* This proof stands on its own construction — a totally
ordered list evaluated with halt-on-first-refusal is deterministic by
definition. **It is not supported by N-04**, which states the opposite of what
an earlier draft of this clause implied: *"Inputs are reproducible. Outputs
are **not** guaranteed deterministic."* N-04 is therefore **not** cited here.
See §13 (AS-3).

### 5.3 Trust — recorded, versioned, non-scoring

- **Location.** A **source registry** keyed on `source_identifier` (C3),
  outside the Intelligence Object model (C16), mirrored onto the existing
  optional `source_reliability` at acquisition (C2).
- **Range.** `[0.0, 1.0]`, the range the Evidence contract already carries.
- **Immutability.** Append-only and versioned (C12, C13); a rating is
  superseded, never edited, so historical reads reproduce.
- **Default.** **None.** An unrated source reports absence, never a neutral
  value. IOM §3.1 calls equal weighting "a strong unstated assumption";
  materialising it as a default would encode the defect M-16 exists to expose.
- **Scoring.** Trust **does not** feed `evidential_support` (C4). S-02's five
  inputs are unchanged and this record supersedes nothing.

---

## 6. Consequences Accepted

1. **M-16 closes only partially.** Trust becomes *visible* but not
   *operative*: weak and strong sources remain equal to the scoring function.
   PKP v2 §9's core complaint is mitigated, not eliminated. Stated plainly
   rather than obscured.
2. **Eight members will prove imperfect.** Some source will sit awkwardly
   between channels. Accepted: C17's superseding-record path exists, and a
   closed-but-imperfect set is more honest than an open one that silently
   accumulates typos (Option D).
3. **A ninth structure exists** — the source registry. It is infrastructure
   state, not an Intelligence Object (C16), and holds no lineage.
4. **Two eligibility gates** (M-16 typability, M-18 legality) must both pass,
   which is more machinery than a single gate.
5. **Trust may prove to need scoring.** If so, S-02 must be superseded by a
   separate record. This decision deliberately does not pre-empt that.

---

## 7. Compatibility Analysis

| Ratified item | Effect |
|---|---|
| **S-02** | **Untouched.** Five inputs unchanged; input 2 becomes computable |
| **N-03** | Source-type coverage becomes measurable |
| **N-16** | Tier 2 "which source types" becomes answerable; type-vector option preserved |
| **S-05** | Stratification by source type becomes possible |
| **S-04** | Unaffected — independence stays keyed on grouping, not type |
| **N-15** | Unaffected — storage mode stays licence-driven, not type-driven |
| **N-07 / CI-1** | Registry holds no lineage and does not score, so it cannot participate in reasoning |
| **R-3 / AD-05 / R-1 / N-04** | Unaffected; trust is metadata, immutable, versioned |
| **Frozen documents** | **None rewritten.** IOM §3.1's annotations are interpreted through this record and the crosswalk (F5) |

**Superseded decisions: NONE.**

---

## 8. Markers Closed

| Marker | Status after this record |
|---|---|
| **M-16** | **CLOSED (partially)** — taxonomy §5.1, eligibility §5.2, trust representation §5.3 |
| **OQ-28** | Closed with §5.3 (subsumed into M-16 by crosswalk §5) |

Partial closure follows established practice: S-05 "Closes \| M-67
(partially)"; R-08 "Closes \| C-04 (jointly with AD-05)".

## 9. Markers Intentionally Left Open

| Marker | Why |
|---|---|
| **M-16 (scoring half)** | Whether trust weights `evidential_support` requires superseding S-02 (C4) |
| **M-18** | Legal/licensing/robots/rate-limit/ToU — `T02.1.2` |
| **M-02 / M-43** | Learning targets and write authority — P8 |
| **M-70** | Feedback instability guard; learned trust would otherwise be unguarded |
| **M-17** | Coverage concept — `T02.1.4` |
| **M-01** | What initiates research — `T02.2.4` |

**`T02.1.1` AC3 ("learnable target for P8") is NOT satisfied by this record.**
It depends on M-02/M-43. Ratifiers must either amend AC3 or accept that
`T02.1.1` completes only AC1 and AC2.

## 10. Required Follow-up

1. Amend `marker-crosswalk.md` to record M-16's partial closure (governance
   artefact, not frozen — F5 respected).
2. Decide `T02.1.1` AC3 disposition (amend, or leave partially complete).
3. `T02.1.2` remains blocked on M-18 — unaffected by this record.
4. If trust-weighted scoring is later wanted, open a record superseding S-02.

## 11. Revisit Conditions

- A source recurs that no member types, and mis-typing distorts diversity.
- Measured evidence that channel-based diversity fails to detect sampling
  artefact (S-02 P3's purpose).
- M-02 closes and source trust is admitted as a learning target.
- **Not** grounds for revisit: inconvenience of the two-gate model.

---

## 12. Falsification Attempt

I attacked this draft with every ratified constraint.

| Attack | Result |
|---|---|
| Violates S-02's "No other input"? | **No** — §5.3 explicitly excludes trust from scoring |
| Violates C5/P3 (diversity must be meaningful)? | **No** — channel is precisely the axis along which sampling artefact occurs |
| Violates C9 (must partition)? | **No** — exactly one member per source, stated in §5.1 |
| Violates C10 (licensing separate)? | **No** — no member encodes a licence regime; Option C rejected for this reason |
| Violates C6 (type vs independence)? | **No** — independence stays keyed on `source_identifier` / grouping |
| Violates C16 (F8, no tenth object)? | **No** — the registry carries no lineage, confidence or lifecycle |
| Violates CI-1 (C11)? | **No**, *conditionally* — holds only because trust does not score. **If a later record makes trust score while the registry is configuration, CI-1 would be breached.** Flagged. |
| Violates AD-05 (C14)? | **No** — trust is metadata about an external source |
| Violates F5 (frozen docs)? | **No** — no frozen text rewritten |
| Violates C17 (closure)? | **No** — members enumerated in the record itself |
| Violates C2 (optional attribute)? | **No** — `source_reliability` stays optional |

**One residual tension, reported not resolved.** IOM §3.1 states
"`evidential_support` **reflects source reliability**", which §5.3 does not
make true. Under `RATIFICATION-ANNOTATIONS` §1 precedence (decision records >
IOM), S-02 governs and the IOM sentence is aspirational — it self-labels
OQ-28 "unresolved". This record does **not** resolve that tension; it inherits
it. A ratifier may wish to annotate IOM §3.1 accordingly.

**No contradiction with any ratified constraint was found.**

---

## 13. Honest Limitations of This Draft

**This record contains five elements that are *selected*, not derived from the
ratified corpus. A ratifier is choosing each of them.** They are listed here
so that no clause in §5 is mistaken for a consequence of C1–C18.

- **AS-0 — §5.1's eight taxonomy members.** Constructed to satisfy C5/C7/C9
  and to cover the source kinds the corpus actually names (v1 §7 marketplace
  and complaint data; IOM's `customer_review_corpus`). **A ratifier is
  choosing this list, not verifying it.** That is precisely why F6 reserves
  the choice to a human.
- **AS-1 — §5.2.1's gate order (Scope → Typability → Rights) is selected, not
  derived.** No ratified text fixes an order. Three gates admit six
  permutations, each corpus-compatible. What the corpus *does* require, once
  halt-on-first-refusal is adopted, is that **some** total order be fixed;
  which one is discretionary.
- **AS-2 — §5.2.1's halt-on-first-refusal is selected, and differs from the
  ratified precedent.** The platform's one existing multi-check gate — the
  acceptance path under N-08/N-10 — evaluates *every* rule and records *all*
  failures together (`FailureRecord.failed_rules` is a tuple). This record
  adopts the opposite convention so that each refusal has exactly one reason.
  An alternative that evaluates all gates and records a set of reasons would
  match precedent and would need no ordering at all.
- **AS-3 — a citation was corrected.** An earlier revision justified §5.2.1's
  determinism by citing *N-04 reproducibility*. That citation was **invalid**:
  N-04 states *"Outputs are not guaranteed deterministic."* The citation has
  been removed and replaced with an authority note. **No normative text
  changed** — only the stated justification.
- **AS-5 — `UNTYPABLE_CHANNEL` is a newly introduced token** with no ratified
  antecedent. It exists only because halt-on-first-refusal (AS-2) requires one
  distinct reason per gate. Under a collect-all alternative it may be
  unnecessary. It is deliberately kept out of the coverage gap vocabulary so
  the two vocabularies remain disjoint.
- The channel/domain distinction is my reading of what C5/P3 measure. It is
  defensible from S-02's stated purpose but is not stated in the corpus.
- §5.2 makes eligibility equivalent to typability. That is the weakest clause:
  it is a real gate, but a thin one, and most eligibility force in practice
  will come from M-18.

---

**Status: `RATIFIED` 2026-08-04 by the Project Owner, with recorded reservations.**
