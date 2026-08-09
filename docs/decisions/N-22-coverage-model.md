# N-22 — Coverage Model: Source-Type Coverage with Explicit Gap Declaration

| Field | Value |
|---|---|
| **ID** | N-22 |
| **Title** | Coverage Model: Source-Type Coverage with Explicit Gap Declaration |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-04 |
| **Date decided** | 2026-08-04 |
| **Source** | PKP v2 §9 (MISSING-17), §13; IOM §3.4; Blocker Resolution B-35; N-03; N-16 |
| **Closes** | **M-17 (partially)** — see §9, §10 |
| **Backlog task** | `T02.1.4` |
| **Depends on** | **N-20** (supplies the coverage frame; closes M-16's taxonomy half), N-21, N-23, N-03, N-16, S-02, S-04, AD-01, N-10, Art. X |
| **Supersedes** | — |
| **Superseded by** | — |

> **RATIFIED 2026-08-04.** Approved by the Project Owner.
> Ratified with recorded reservations; see *Honest Limitations*.
>
> ### ⚠ IMPLEMENTABILITY WARNING (TEMPLATE §3)
>
> **This decision is agreed-shaped but cannot currently be executed.**
> Its central measure — *source-type coverage* — is defined over the source
> taxonomy supplied by **N-20**. Ratifying N-22 does **not** unblock
> `T02.1.4`; it becomes executable only once **N-20 is ratified**. This
> dependency is structural, not incidental: B-35 records it as
> *"Dependencies. B-33 (taxonomy)"*. **N-22 must therefore never be ratified
> before N-20.**
>
> A ratifier must decide whether to ratify a decision that is correct but
> inert, or to defer until N-20 is ratified. **This record does not make that
> choice.**

---

## 1. Problem Restated

PKP v2 §9 (L622): *"**MISSING-17:** No coverage or completeness concept. The
platform cannot determine when it has researched enough, nor detect what it
has not seen."*

That sentence bundles four distinct questions. Only two belong to M-17.

| Concern | Question | Owner |
|---|---|---|
| **Coverage** | Which parts of the reachable evidence space have been sampled? | **M-17 — this record** |
| **Completeness** | Is the evidence base adequate, and what is knowably absent? | **M-17 — this record** |
| **Sufficiency** | Does *this object* have enough support to be accepted? | **S-04 (RATIFIED, closes M-06)** — not M-17 |
| **Stopping criteria** | When does a research cycle begin and end? | **M-01 (OPEN)** — not M-17 |

**Sufficiency is already decided and must not be re-opened.** S-04 fixes
per-object floors (Fact 1, Problem 2, Pattern 3 independent sources across
≥2 constituents) and states: *"Sufficiency is checked at acceptance. An object
below threshold is **rejected**."* That is a per-object gate. Coverage is a
property of the **evidence base as a whole**. They are different objects of
measurement and this record does not touch S-04.

**Stopping is M-01.** v2 §9's phrase *"when it has researched enough"* reads as
coverage but resolves to triggering: v2 §4.4 records that Research *"Does NOT
decide what to research → **MISSING-01**"*. A coverage measure can *inform* a
stop; it cannot *own* the decision to stop without deciding M-01. **This
record deliberately does not define a stopping rule** (§5.5).

---

## 2. Binding Constraints Extracted

| # | Constraint | Source |
|---|---|---|
| J1 | Stage-1 Evidence proxy measures are *"Provenance completeness; duplicate rate; **source-type coverage**"* | N-03 (RATIFIED) |
| J2 | N-03 Family 1 *"may be extended or refined as engines are built; additions require a decision record"* | N-03 (Revisit) |
| J3 | `source_diversity` = *"Count of independent Evidence sources beneath the constituents"*; **PT-V4** requires it present | IOM §3.4 |
| J4 | `artefact_assessment` = *"Explicit judgement on whether this reflects research bias"*; **PT-V5** requires it *"present and reasoned"* | IOM §3.4 |
| J5 | *"`source_diversity` and `artefact_assessment` are **mandatory** because sampling artefact is this stage's defining risk"* | IOM §3.4 |
| J6 | Tier 2 deep traversal yields *"which source **types**, which specific sources, how they distribute"*; *"**Only Pattern Intelligence requires Tier 2**"* | N-16 (RATIFIED) |
| J7 | S-02 input 2 = *"Number of distinct source **types** represented"*; P3 *"n sources of one type yield less than n across types"* | S-02 (RATIFIED) |
| J8 | Sufficiency floors are per-object and enforced at acceptance | S-04 (RATIFIED) |
| J9 | *"Coverage limited by research reach — the platform is blind to what it has not collected"* | AD-01 (Consequences), v2 §7 |
| J10 | *"Negative results, contradictions, and **known gaps are recorded** with the same standing as favourable findings. Where the platform's knowledge is thin, it says so"* | Constitution **Article X** |
| J11 | *"Source inaccessible → Coverage gap, **silent unless tracked**"* | v2 §4.4 failure modes |
| J12 | A stage producing nothing because it failed is distinguishable from one that found nothing | N-10 (RATIFIED) |
| J13 | Markers close only by register record | README L145, Playbook F3 |
| J14 | Closed vocabularies enumerated by decision; extension by superseding record | R-2, R-6 precedent |
| J15 | Nine engines / nine objects / ten stages — fixed | Playbook F8 |
| J16 | Precedence: Constitution → decisions → IOM → PKP → Backlog | Art. XI |

### 2.1 Disagreement between ratified sources — reported, not resolved

**D-1. `source_diversity`: count of *sources* or of *types*?**

- IOM §3.4 (J3): *"Count of **independent Evidence sources** beneath the
  constituents."*
- IOM §3.4 worked example (L1069): *"11 independent Evidence sources across
  **4 channel types**"* — reports both.
- S-02 input 2 (J7): *"Number of distinct source ***types*** represented."*
- N-16 (J6) treats type composition as Tier 2 detail.

The IOM defines the *attribute* as a source count; S-02 defines its *input* as
a type count. Under Art. XI (J16) decision records outrank the IOM, so S-02
governs **for S-02's own input**. Whether the Pattern *attribute* `source_diversity`
should therefore also be a type count is **not stated anywhere**.

**Classification:** genuine ambiguity between a frozen document and a ratified
decision. **Does it block this record?** No — §5.2 measures coverage over
types without redefining the Pattern attribute. **It does block a clean
implementation of PT-V4**, and is flagged as follow-up (§12 item 3). Not resolved
here; resolving it would breach scope discipline.

---

## 3. Design Space

Four architectures compatible with J1–J16.

### Option A — No coverage measure; rely on volume *(B-35 Option 1)*

- **"Coverage" means:** nothing; more evidence is assumed better.
- **"Complete" means:** undefined.
- **Ownership:** none.
- **Compatibility:** **Fails J1** — N-03 already ratified source-type coverage
  as a stage-1 measure, so "no measure" contradicts a ratified decision.
  Fails J10: gaps would go unrecorded.
- **Research / Evidence / Pattern:** no signal to any.
- **Migration cost:** zero. **Extensibility:** none.

### Option B — Source-type coverage only *(B-35 Option 2)*

- **"Coverage" means:** every taxonomy member is represented by ≥1 ACTIVE
  Evidence object.
- **"Complete" means:** all members represented.
- **Ownership:** Research (measurement); no declarer of gaps.
- **Compatibility:** satisfies J1, J7. **Fails J10/J11** — an inaccessible
  source produces a silent hole; nothing declares it.
- **Pattern:** gives PT-V4 a number but leaves PT-V5's *reasoned* judgement
  unsupported.
- **Migration cost:** low. **Extensibility:** moderate.

### Option C — Population coverage against a market frame *(B-35 Option 3)*

- **"Coverage" means:** proportion of a defined market population sampled.
- **"Complete" means:** the frame is adequately represented.
- **Ownership:** requires an owner of the market frame — **no such role
  exists** (J15 fixes the engine set).
- **Compatibility:** **Fails J9** — AD-01 concedes the platform "is blind to
  what it has not collected"; a population frame asserts knowledge of the
  unseen universe, which the corpus states the platform lacks. Would require a
  new external artefact.
- **Migration cost:** very high. **Extensibility:** poor — the frame must be
  maintained per market.

### Option D — Source-type coverage **plus explicit gap declaration** *(B-35 Option 4)*

- **"Coverage" means:** which taxonomy members are represented, which are not.
- **"Complete" means:** *declared-complete* — all members either represented
  or covered by a recorded gap declaration. Never "true" completeness.
- **Ownership:** Research measures and declares (it is the only engine at the
  external boundary); Pattern consumes via Tier 2 (J6).
- **Compatibility:** satisfies J1, J6, J7, J10, J11, J12. Does not touch S-04
  (J8) or the engine set (J15).
- **Research:** must record why a member is unrepresented.
- **Evidence:** unchanged — no new attribute required.
- **Pattern:** supplies the evidential basis PT-V5 (J4/J5) needs for a
  *reasoned* artefact assessment.
- **Migration cost:** low — reuses the taxonomy and existing failure records.
- **Extensibility:** good — new taxonomy members extend coverage automatically.

---

## 4. Selection

**Option D.** Justified exclusively from ratified material:

- **Minimises ambiguity.** J1 already fixes the *unit* of coverage as source
  type. Options A and C measure something N-03 does not.
- **Minimises hidden assumptions.** Option C assumes a knowable market frame;
  J9 states the opposite. Option B assumes silence is absence of a gap; J11
  states gaps are *"silent unless tracked"*.
- **Minimises coupling.** Coverage is computed from the taxonomy and stored
  Evidence only. No dependency on scoring, trust, licensing or independence.
- **Minimises future superseding decisions.** It refines N-03's existing
  measure rather than replacing it, which J2 expressly permits ("additions
  require a decision record" — this is that record).

---

## 5. DECISION

### 5.1 Formal definitions

| Term | Definition |
|---|---|
| **Coverage frame** | The set of members of the ratified source-type taxonomy (N-20 §5.1) |
| **Represented member** | A frame member for which ≥1 `ACTIVE` Evidence object exists |
| **Coverage gap** | A frame member with no `ACTIVE` Evidence |
| **Gap declaration** | A recorded statement that a named member is unrepresented, with a recorded reason drawn from §5.4 |
| **Out-of-frame refusal** | A recorded refusal of a source that maps to **no** frame member (N-20 §5.2, gate 2) |
| **Declared-complete** | Every frame member is either represented or carries a gap declaration, **and** every out-of-frame refusal is recorded |

**"Complete" never means "the market is fully observed."** J9 forecloses that
reading. Completeness here is *declarative*: the platform has accounted for
every member of its own frame.

### 5.2 Coverage model

Coverage is measured **over source types, not volume**:

```
coverage  = |represented members| / |frame|
gaps      = frame \ represented members
```

Both are computed from the taxonomy and stored `ACTIVE` Evidence. Nothing else
is an input. This is the measure N-03 (J1) already names.

**Counting rule.** A member is represented by the *existence* of ACTIVE
Evidence of that type, not by quantity. Volume is not coverage — Option A's
error.

#### 5.2.1 Out-of-frame register — coverage may never overstate

A source refused at gate 2 (N-20 §5.2.1, `UNTYPABLE_CHANNEL`) belongs to no
frame member. It can therefore never appear as a coverage gap, and without
this clause a whole class of refused material would be invisible while
coverage read 100 %.

**Every out-of-frame refusal is recorded in an out-of-frame register**,
counted separately from `coverage` and `gaps`:

```
out_of_frame = count of sources refused at gate 2
```

**A coverage report is well-formed only if it reports `out_of_frame`
alongside `coverage`.** A report showing `coverage = 1.0` while
`out_of_frame > 0` is **not** a claim of complete coverage; it states that the
frame is fully sampled *and* that material outside the frame was refused.

This satisfies Article X (J10) at the seam between the taxonomy and the
coverage model: the platform states what it declined to see, not merely what
it looked for. It introduces no new measure of coverage — `coverage` and
`gaps` are unchanged — only an accompanying count that prevents the figure
being read as more than it is.

**Consequence for the frame.** A persistent non-zero `out_of_frame` is
evidence the taxonomy is too narrow, and is grounds for revisiting N-20 under
its own extension path (§13).

### 5.3 Completeness model

The platform reports **declared-completeness**, never absolute completeness.

A coverage report is *declared-complete* iff every gap carries a declaration.
An undeclared gap makes the report **incomplete**, and that state is itself
reportable — satisfying J10 (Article X: state what you do not know) and J11
(gaps are silent unless tracked).

### 5.4 Gap-declaration reasons — closed vocabulary

Extension requires a superseding record (J14).

| Reason | Meaning |
|---|---|
| `NOT_ATTEMPTED` | No acquisition was attempted for this member |
| `INACCESSIBLE` | Attempted; the source could not be reached (J11) |
| `REFUSED_BY_RIGHTS` | Attempted; refused on acquisition rights (gate 3; see §6.2) |
| `NO_MATERIAL_FOUND` | Attempted and reached; nothing relevant existed |
| `OUT_OF_SCOPE` | Excluded by the governing research directive (gate 1; see §6.6) |

**Ownership of this vocabulary.** All five reason values are **defined by this
record and owned by it.** Other records *produce the conditions* those values
describe — N-23 determines what is out of scope, N-21 determines what is
refused on rights — but neither defines the vocabulary. This record is the
single source of truth for gap-reason semantics, so no token is defined twice.

`UNTYPABLE_CHANNEL` is deliberately **not** in this table: it is not a gap
reason, because an untypable source corresponds to no frame member. It is
recorded in the out-of-frame register (§5.2.1) instead.

`NOT_ATTEMPTED` versus `NO_MATERIAL_FOUND` preserves N-10's mandatory
distinction (J12) at the coverage layer: *absence of evidence* is not
*absence of attempt*.

### 5.5 Stopping rule — deliberately NOT defined

**This record defines no stopping rule.** A coverage figure may *inform* a
decision to stop, but the decision itself is research triggering and scoping,
which is **M-01** — recorded in v2 §4.4 as *"Does NOT decide what to research
→ MISSING-01"*. Defining a stop here would close M-01 by implication,
breaching J13.

Consequently the second half of v2 §9's sentence — *"cannot determine when it
has researched enough"* — is **not** answered by this record (§10).

### 5.6 Acceptance semantics

**Coverage is a report, not a gate.**

- No object is rejected for low coverage. Object-level admission is S-04's
  sufficiency floor (J8), which this record does not modify.
- Coverage does not enter `evidential_support`; S-02's five inputs are
  untouched (J7).
- Coverage does not alter any lifecycle state or validation rule.

A coverage report is **descriptive**. Making it a gate would silently create a
second acceptance authority alongside S-04 and N-08.

### 5.7 Failure semantics

- A failed acquisition attempt produces a failure record (N-10, J12) **and**
  makes the member a gap requiring declaration.
- A gap with no declaration is a **reportable deficiency of the report**, not
  an error of any object.
- Coverage computation never fails silently: if the frame is unavailable —
  which it is until N-20 is ratified — coverage is **undefined and reported as
  such**, never defaulted to 0 or 1.

---

## 6. Interactions

### 6.1 With N-20 (source taxonomy) — **hard dependency**
The frame *is* the taxonomy N-20 §5.1 supplies. Until N-20 is ratified the
frame is empty, and
coverage over an empty frame is undefined (§5.7), not 100 %. This is the
Implementability Warning. **This record does not define, refine or assume any
taxonomy member.**

### 6.2 With M-18 (acquisition rights)
`REFUSED_BY_RIGHTS` (§5.4) records rights-based refusals as coverage gaps.
This record **defines no rights policy** and takes no position on M-18. It
consumes the outcome; it does not produce it. B-34 anticipates the linkage:
*"Restricts the evidence base, worsening coverage (M-17)."*

### 6.3 With N-03 (success criteria)
Refines the already-ratified stage-1 measure *"source-type coverage"* (J1)
under the extension path J2 expressly allows. **N-03 is not superseded.**

### 6.4 With N-16 (source diversity propagation)
Coverage is a Tier 2 concern: N-16 (J6) states deep traversal yields *"which
source types"* and that *"Only Pattern Intelligence requires Tier 2"*. Coverage
adds **no** universal attribute and does not disturb Tier 1's
`independent_source_count`.

### 6.5 With S-02 (evidential support)
**No interaction.** Coverage is not an input; S-02's *"No other input"* stands.
Both happen to be defined over source types (J7), but S-02 measures support
*for one object*; coverage measures the *evidence base*.

### 6.6 With Phase 2 tasks

| Task | Effect |
|---|---|
| `T02.1.4` | AC2/AC3 satisfied by §5.3–§5.4; **AC1 still requires N-20** |
| `T02.3.1` | AC3 "Coverage gaps declared" becomes satisfiable; AC1 still requires N-20 |
| `T02.2.5` | Acquisition failure records feed `INACCESSIBLE` / `NO_MATERIAL_FOUND` |
| `T05.1.4` | Gap declarations become inheritable input to PT-V5 artefact assessment (J4/J5) |
| `T02.2.4` | Untouched — `OUT_OF_SCOPE` references directives without defining them (M-01) |

---

## 7. Consequences Accepted

1. **Declared gaps do not fix bias.** B-35: *"Declared gaps do not fix bias;
   they only make it visible. That is nonetheless the difference between a
   known limitation and a silent falsehood."* Accepted verbatim.
2. **Coverage is relative to the platform's own frame**, not to the market.
   A frame that omits a whole channel yields 100 % coverage while the platform
   remains blind — consistent with J9, and the reason §5.3 says
   *declared*-complete.
3. **This record is inert until N-20 is ratified** (§6.1).
4. **Stopping remains unanswered** (§5.5), so v2 §9's complaint is only half
   addressed.
5. **A gap declaration is a judgement**, and a lazy `NOT_ATTEMPTED` can hide a
   real omission. PT-V5's *"reasoned"* requirement (J4) is the only ratified
   pressure against boilerplate.

---

## 8. Alternatives Considered

Options A, B and C in §3 — rejected there with the constraint each fails
(A: J1/J10; B: J10/J11; C: J9/J15).

---

## 9. Compatibility Analysis

| Ratified item | Effect |
|---|---|
| **N-03** | Refined under its own extension clause (J2). Not superseded |
| **S-04** | Untouched — sufficiency stays per-object (§5.6) |
| **S-02** | Untouched — five inputs unchanged (§6.5) |
| **N-16** | Consistent — Tier 2 only; no new universal attribute |
| **N-10** | Used — failure records feed gap reasons |
| **AD-01 / Art. X** | Satisfied — the platform states what it has not seen |
| **N-08** | Untouched — coverage is not an acceptance rule (§5.6) |
| **Playbook F8** | No engine, object or stage added |
| **Frozen documents** | None rewritten (F5) |

**Superseded decisions: NONE.**

## 10. Markers Closed

| Marker | Status |
|---|---|
| **M-17** | **CLOSED (partially)** — the *coverage* and *completeness* concepts, §5.1–§5.4, §5.6–§5.7 |

Partial closure follows ratified precedent: S-05 *"Closes | M-67
(partially)"*; R-08 *"Closes | C-04 (jointly with AD-05)"*.

**Explicitly NOT closed by this record:** v2 §9's *"cannot determine when it
has researched enough."* That is the stopping question (§5.5), which belongs
to M-01.

## 11. Markers Intentionally Left Open

| Marker | Why |
|---|---|
| **M-01** | Research triggering and stopping (§5.5) |
| **M-16** | Source taxonomy — closed in part by N-20, which supplies the frame this record depends on (§6.1) |
| **M-18** | Acquisition rights — consumed, not decided (§6.2) |
| **M-17 (stopping half)** | Follows M-01; may warrant its own identifier |
| **D-1 ambiguity (§2.1)** | `source_diversity` sources-vs-types — reported, not resolved |

## 12. Follow-up Work

1. Ratify N-20 before `T02.1.4` can execute.
2. Decide whether M-17's stopping half is tracked separately or folded into
   M-01.
3. **Resolve D-1 (§2.1)** — whether the Pattern `source_diversity` attribute
   counts sources or types. Blocks a clean PT-V4 implementation.
4. Record M-17's partial closure in `marker-crosswalk.md` (governance
   artefact, not frozen).

## 13. Revisit Conditions

- The taxonomy grows large enough that member-presence is too coarse and
  per-member volume thresholds become necessary.
- Measured evidence that declared-completeness masks material bias.
- A market frame becomes genuinely available, making Option C viable.
- **Not** grounds for revisit: coverage figures being unflattering.

---

## 14. Formal Consistency Challenge

Attacked against every constraint J1–J16.

| Attack | Result |
|---|---|
| Contradicts N-03 (J1)? | **No** — refines the measure N-03 names, via J2's extension path |
| Re-opens S-04 sufficiency (J8)? | **No** — §5.6 makes coverage descriptive; no object gate |
| Adds an input to S-02 (J7)? | **No** — §6.5; five inputs unchanged |
| Breaches N-16's tiering (J6)? | **No** — Tier 2 only; no universal attribute added |
| Asserts knowledge of the unseen (J9)? | **No** — §5.3 defines *declared*-completeness; Option C rejected for this reason |
| Leaves gaps silent (J10, J11)? | **No** — undeclared gaps make the report incomplete and reportable |
| Collapses N-10's distinction (J12)? | **No** — `NOT_ATTEMPTED` vs `NO_MATERIAL_FOUND` preserves it |
| Closes M-01 by implication (J13)? | **No** — §5.5 refuses to define a stopping rule |
| Adds an engine/object/stage (J15)? | **No** |
| Violates precedence (J16)? | **No** — §2.1 applies Art. XI rather than overriding it |
| Redefines taxonomy / trust / licensing / independence / scoring? | **No** — §6.1, §6.2, §6.4, §6.5 consume without defining |

**One unresolved ambiguity, classified.** D-1 (§2.1): IOM §3.4 and S-02
disagree on whether `source_diversity` counts sources or types.
**Classification:** frozen-document vs ratified-decision divergence, resolvable
under Art. XI for S-02's input but *unstated* for the Pattern attribute.
**Does it block ratification of N-22?** **No** — this record measures coverage
over types without redefining the Pattern attribute, so it is consistent under
either reading. **It does block a clean PT-V4 implementation** and is recorded
as follow-up (§12 item 3).

**Why the draft survives.** Every clause either (a) refines a measure a
ratified decision already names, under an extension path that decision itself
grants; (b) consumes an outcome another marker owns without deciding it; or
(c) declines to decide where the corpus is silent — §5.5 being the clearest
case. No clause creates authority, adds a rule to V1–V12 or I1–I8, or
introduces a requirement absent from J1–J16.

---

## 15. Honest Limitations

- **This record is inert on ratification.** It cannot be executed until
  **N-20** is ratified, since N-20 supplies the coverage frame. A ratifier may
  reasonably prefer to defer this record and ratify N-20 and N-22 together;
  that choice is not made here (see the warning at the head).
- **AS-4 — the out-of-frame mechanism is selected, not derived.** The *duty*
  to record untypable refusals **is** forced: Article X requires that
  *"known gaps are recorded"* and forbids *"presenting fluency as
  confidence"*, and a coverage figure of 1.0 that conceals a refused class
  does exactly that. Article X is constitutional and outranks every decision
  record (Art. XI). **The mechanism, however, is chosen.** No ratified text
  names a register, a counter, or `out_of_frame`. At least two alternatives
  satisfy Article X equally: a sixth gap reason recorded against a reserved
  pseudo-member, or relying solely on the N-10 failure records that gate-2
  refusals already produce and requiring the coverage report to cite them —
  the latter adding no new structure at all. **A ratifier is choosing this
  mechanism, not verifying it.**
- **What `out_of_frame` is.** A count, held **beside** `coverage` and `gaps`,
  of sources refused at gate 2 (N-20 §5.2.1, `UNTYPABLE_CHANNEL`) because they
  map to no frame member. It is **not** a coverage measure and does not enter
  the coverage arithmetic: `coverage = |represented members| / |frame|` is
  unchanged by this mechanism. Its only function is to make a report showing
  `coverage = 1.0` alongside `out_of_frame > 0` legible as *"the frame is
  fully sampled **and** material outside the frame was refused"*, rather than
  as a claim of complete observation.
- **`out_of_frame` has no consumer.** Nothing reads it — correct under S-02,
  whose five inputs are closed, but it means truthfulness depends on a human
  reading the report rather than on any enforced check.
- **It closes half of what v2 §9 complains about.** Coverage and completeness
  are addressed; "when has it researched enough" is not, and I judged that
  answering it would close M-01 by implication.
- **§5.4's five reasons are the one element not fully derivable.**
  `INACCESSIBLE` traces to J11 and `NOT_ATTEMPTED`/`NO_MATERIAL_FOUND` to J12,
  but `REFUSED_BY_RIGHTS` and `OUT_OF_SCOPE` are constructed to keep M-18 and
  M-01 outcomes representable without deciding them. A ratifier is choosing
  that list.
- **Gap declaration quality is unenforceable here.** Only PT-V5's "reasoned"
  requirement pushes against boilerplate, and it applies at Pattern, not at
  declaration time.
- **D-1 was discovered during this drafting**, not in prior investigations. It
  suggests other IOM-vs-decision divergences over shared vocabulary may exist;
  I have not audited for them.

---

**Status: `RATIFIED` 2026-08-04 by the Project Owner, with recorded reservations.**
