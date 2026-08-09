# N-23 — Research Trigger: Directive-Scoped Acquisition Within Scheduled Cycles

| Field | Value |
|---|---|
| **ID** | N-23 |
| **Title** | Research Trigger: Directive-Scoped Acquisition Within Scheduled Cycles |
| **Status** | **`DRAFT`** — awaiting human ratification. Not binding. |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-04 |
| **Date decided** | — (not decided) |
| **Source** | PKP v2 §2 (MISSING-01), §4.4, §10, §13; IOM §3.1; Blocker Resolution B-58/B-59; N-17; AD-05 |
| **Closes** | **M-01 (partially)** — see §10, §11 |
| **Backlog task** | `T02.2.4` |
| **Depends on** | N-17, N-02, N-01, AD-05, R-8, N-10, N-11, N-07 |
| **Supersedes** | — |
| **Superseded by** | — |

> **Ratification notice.** `AGENT-PLAYBOOK` **F6** — human sign-off required.
> This record is prepared, not adopted.
>
> ### ⚠ BLOCKING CONTRADICTION IDENTIFIED (§2.1, D-1)
>
> `T02.2.4` AC2 requires *"Targets proposed for approval per human-gate
> decision."* **N-02 (RATIFIED) establishes "exactly three gates" — G1
> Opportunity selection, G2 Post-validation promotion, G3 Learning
> application. None covers research targets.**
>
> There is therefore **no ratified gate** for AC2 to invoke. This record
> **cannot resolve that** without either creating a fourth gate (superseding
> N-02) or amending AC2 — both reserved to the ratifier. §5.5 states the
> options and decides neither. **A ratifier must resolve D-1 before `T02.2.4`
> can be completed as written.**

---

## 1. Problem Restated

PKP v2 §2 (L75): *"**MISSING-01:** v1 does not define what initiates
discovery. There is no statement of whether the pipeline runs continuously, on
a schedule, on external trigger, or in response to a scoped request… This
determines the entire control model of the Orchestration Engine."*

Six concerns are conflated in that framing. Ownership divides as follows.

| Concern | Question | Owner |
|---|---|---|
| **Research initiation** | What causes acquisition to begin, and with what scope? | **M-01 — this record** |
| **Human requests** | May a person commission research, and how is it expressed? | **M-01 — this record** |
| **Automatic triggers** | May the platform raise its own research need? | **M-01 — this record** |
| **Research termination** | When does a research *cycle* stop? | **N-17 (RATIFIED)** — see below |
| **Scheduled execution** | Is the control model batch, event-driven or continuous? | **N-17 (RATIFIED)** — closed |
| **Research continuation** | Does the platform decide its own next targets? | **OQ-07 (OPEN)** — not this record |

**Two of the six are already closed and must not be re-opened.** N-17 ratifies
*"Scheduled batch orchestration for P1–P5. Directive, not reactive"*, and
bounds every cycle by *"work-set size and wall-clock budget… it never runs
unbounded"*, explicitly closing loop termination (M-37). So *scheduled
execution* and *cycle termination* are decided; what remains undecided is
**what populates the work set**. N-17 says so itself: *"Something must decide
each cycle's work set; absent a research trigger model (M-01), this is
initially manual."*

**M-01 is therefore narrower than its wording suggests.** It must answer:
what expresses a research need, who may raise it, and how it scopes
acquisition — nothing about scheduling or bounding.

---

## 2. Binding Constraints Extracted

| # | Constraint | Source |
|---|---|---|
| G1 | *"Scheduled batch orchestration for P1–P5. **Directive, not reactive.**"* | N-17 (RATIFIED) |
| G2 | *"**Directive means Orchestration decides what runs.** It does not watch for objects appearing and trigger downstream work; it plans a cycle, invokes engines over a defined work set"* | N-17 |
| G3 | *"Every cycle is bounded by **work-set size** and **wall-clock budget**… it never runs unbounded"* | N-17 |
| G4 | *"Something must decide each cycle's work set; absent a research trigger model (M-01), this is **initially manual**"* | N-17 (Consequences) |
| G5 | *"Until `T02.2.4`, work sets are **externally specified**"* | N-17 (Known Tensions) |
| G6 | Research *"Does **NOT** decide what to research"*; *"Is the **ONLY** engine permitted to introduce information from outside the platform"* | v2 §4.4 |
| G7 | Research depends on *"a research directive **of undefined origin** (MISSING-01)"* | v2 §4.4 |
| G8 | *"Research directive \| implied by Research Engine \| **MISSING-01**"* — a named but unmodelled artefact | v2 §10 |
| G9 | **Research Trigger** is one of four exhaustive permitted feedback forms: *"A directive causing acquisition of new external Evidence"*, living in *"Research directive (`T02.2.4`, `T08.3.4`)"* | **AD-05 (RATIFIED)** |
| G10 | *"These four are exhaustive. Any feedback output that cannot be expressed as one of them has no permitted destination and must not be produced."* | AD-05 |
| G11 | Human judgement enters at **exactly three gates** (G1 Opportunity selection, G2 Post-validation promotion, G3 Learning application); *"Everywhere else the platform runs autonomously"* | **N-02 (RATIFIED)** |
| G12 | Reconsider N-02 only if *"A fourth transition is shown to carry consequence comparable to G1–G3"* | N-02 (Revisit) |
| G13 | The platform is **advisory**; *"holds no budget, no operational authority, and no accountability for consequences"* | N-01, Art. VI |
| G14 | Feedback *"may only trigger the Research Engine to acquire new external evidence"*; loop closes **behaviourally**, never by lineage | R-8, IOM §3.1 |
| G15 | Acquisition and extraction may run concurrently; interpretation serialised | N-11 |
| G16 | Failure is recorded, never masked; empty ≠ failed | N-10 |
| G17 | An Evidence `explanation` may cite its directive: *"Acquired under research directive covering seller-side friction in segment A"* | IOM §3.1 (worked example) |
| G18 | Configuration is infrastructure state; must never participate in reasoning, scoring or lineage | CI-1 / N-07 |
| G19 | Nine engines / nine objects / ten stages — fixed | Playbook F8 |
| G20 | Markers close only by register record | README L145, F3 |
| G21 | Precedence: Constitution → decisions → IOM → PKP → Backlog | Art. XI |

### 2.1 Disagreement between ratified sources — reported, not resolved

**D-1 (BLOCKING). `T02.2.4` AC2 requires a human gate that N-02 forecloses.**

- Backlog `T02.2.4` AC2: *"Targets proposed for approval **per human-gate
  decision**."*
- N-02 (G11): *"Human judgement enters the platform at **exactly three
  gates**"* — G1 Opportunity selection, G2 Post-validation promotion, G3
  Learning application. **Research target approval is none of them.**
- B-59 (unratified analysis) recommends *"Directed, with proposed targets
  surfaced for approval"* — which is where AC2's wording originates.

**Classification:** ratified decision (N-02) vs Implementation Backlog. Under
Art. XI (G21) the decision record outranks the backlog, so **N-02 governs and
AC2 as written is unsatisfiable**.

**Does it block ratification of N-23?** **No** — §5.5 keeps target approval
outside the platform, which is consistent with N-02. **Does it block
completion of `T02.2.4`?** **Yes**, as written. Resolution requires either
amending AC2 or creating a fourth gate under N-02's own revisit clause (G12).
**Not decided here.**

**D-2 (non-blocking). OQ-07 identifier.** B-59 attributes *"Does Research
determine its own targets"* to OQ-07, but canonical OQ-07 is *"May Pattern
Intelligence read Facts directly?"* (v2 §12), and the crosswalk records no
collision for it. The self-direction question appears to have **no canonical
identifier**. Reported; this record simply does not decide self-direction
(§5.4).

---

## 3. Design Space

Four architectures compatible with G1–G21.

### Option A — Continuous autonomous discovery
- **Initiation authority:** the platform itself.
- **Ownership:** Research.
- **Trigger semantics:** run perpetually; no discrete trigger.
- **Interaction with Research:** violates G6 — Research would decide what to research.
- **Human approval:** none.
- **Phase 2:** `T02.2.4` AC1/AC3 unsatisfiable (nothing scopes acquisition).
- **Compatibility:** **Fails G1/G3** — N-17 ratifies bounded scheduled cycles.
- **Migration cost:** high. **Extensibility:** poor.

### Option B — Event-driven: acquisition reacts to platform state
- **Initiation authority:** whichever engine emits the event.
- **Trigger semantics:** reactive.
- **Compatibility:** **Fails G1/G2 explicitly** — N-17: *"Directive, not
  reactive… does not watch for objects appearing and trigger downstream
  work."*
- **Migration cost:** high. **Extensibility:** poor (couples engines).

### Option C — Externally specified work sets only, no directive artefact
- **Initiation authority:** external operator.
- **Trigger semantics:** each cycle's work set handed in; nothing recorded.
- **Interaction with Research:** satisfies G6.
- **Compatibility:** consistent with G4/G5 as an *interim*, but **fails G8/G9**
  — v2 §10 names "Research directive" as a required artefact and AD-05 gives
  it a home (`T02.2.4`). Leaves feedback's Research Trigger form (G9) with no
  destination, breaching G10.
- **Phase 2:** `T02.2.4` has no deliverable to build.
- **Migration cost:** zero. **Extensibility:** none — permanently interim.

### Option D — **Research directive as a first-class recorded artefact, raised by permitted originators, scoping acquisition within N-17 cycles**
- **Initiation authority:** originators enumerated in §5.3; the platform never
  self-initiates.
- **Ownership:** Orchestration populates the work set from directives (G2);
  Research executes within a directive's scope (G6).
- **Trigger semantics:** a directive is a *scoping instruction*, not a schedule.
- **Interaction with Research:** Research consumes scope, never authors it (G6).
- **Human approval:** commissioning happens **outside** the platform, so no
  fourth gate is created (G11).
- **Phase 2:** satisfies `T02.2.4` AC1 and AC3; **AC2 blocked by D-1**.
- **Compatibility:** satisfies G1–G10, G13–G21.
- **Migration cost:** low — the artefact is already named (G8) and already has
  a home (G9); `explanation` already cites it (G17).
- **Extensibility:** good — new originator classes extend the enumeration by
  superseding record.

---

## 4. Selection

**Option D.** Justified exclusively from ratified material:

- **Minimises ambiguity.** G8 already names "Research directive" as an
  artefact whose origin is undefined; G9 already assigns it a home at
  `T02.2.4`. Option D supplies the missing origin and nothing else.
- **Minimises hidden assumptions.** Options A and B assume an autonomy G6
  denies and a reactivity G1/G2 reject.
- **Minimises coupling.** The directive is the single scoping channel;
  Research stays a pure consumer, preserving G6's boundary and N-17's
  directive model.
- **Minimises future superseding decisions.** Option C would need replacing
  the moment feedback raises a Research Trigger (G9/G10). Option D closes that
  path now without touching N-17, N-02 or N-01.

---

## 5. DECISION

### 5.1 Formal definitions

| Term | Definition |
|---|---|
| **Research directive** | A recorded instruction that scopes acquisition: what subject matter, over what period, within what bounds |
| **Originator** | The party or mechanism that raised the directive (§5.3) |
| **Directive scope** | The bounds within which acquisition is permitted for that directive |
| **Trigger** | The recorded event that caused a directive to come into effect |
| **In-scope acquisition** | Acquisition whose target falls within an `IN_EFFECT` directive's scope |

A directive is **infrastructure state**, not an Intelligence Object. It adds no
tenth object type (G19). It is not Evidence, carries no lineage, and
contributes nothing to confidence or scoring.

### 5.2 Research trigger model

**Acquisition occurs only under an `IN_EFFECT` research directive.**

- A directive **scopes**; it does not **schedule**. Scheduling and cycle
  bounding remain N-17's (G1, G3), untouched.
- Orchestration populates each cycle's work set from `IN_EFFECT` directives —
  the "something" G4 says must exist.
- Research executes within the scope and **never authors or widens it** (G6).
- Acquisition outside every `IN_EFFECT` directive's scope is **refused**, and the
  refusal is recorded as a failure record, never silent (G16). This is
  `T02.2.4` AC3.

### 5.3 Initiation authority — closed set of originators

Extension requires a superseding record.

| Originator | Basis | Human-commissioned? |
|---|---|---|
| `EXTERNAL_COMMISSION` | A person or organisation commissions research | Yes — outside the platform |
| `FEEDBACK_RESEARCH_TRIGGER` | Feedback raises a Research Trigger under AD-05 form 3 (G9) | No |
| `VALIDATION_BACKFLOW` | Validation raises a research need as a **new directive**, not reverse flow | No |

**The platform never self-initiates research on its own judgement.** Every
directive traces to either an external commission or a ratified mechanism that
already exists (AD-05 form 3; backflow-as-new-directive).

`VALIDATION_BACKFLOW` is included because AD-05's exhaustiveness (G10) and
R-8's behavioural closure (G14) already require a destination for it; omitting
it would leave a ratified path homeless. **This record does not decide OQ-11
(whether backflow is permitted)** — it only reserves the form so that, if
permitted, it has a lawful home.

### 5.4 Manual and automatic triggers

- **Manual** — `EXTERNAL_COMMISSION`. The scope is supplied from outside; the
  platform records it verbatim and does not interpret it. Consistent with G13
  (advisory, no operational authority) and G5 (work sets externally
  specified).
- **Automatic** — `FEEDBACK_RESEARCH_TRIGGER` and `VALIDATION_BACKFLOW`. Both
  are *mechanically derived from ratified platform events*, not from the
  platform's judgement about what is worth researching.

**Self-directed target selection is NOT decided here.** Whether Research may
propose its own targets is a distinct question (D-2, §2.1) with no canonical
identifier, and G6 currently forbids it. Left open (§11).

### 5.5 Human approval of targets — **the D-1 problem**

`T02.2.4` AC2 requires *"Targets proposed for approval per human-gate
decision."* N-02 (G11) provides no such gate.

**This record takes the only position consistent with N-02:** commissioning is
a **pre-platform act**. An `EXTERNAL_COMMISSION` directive arrives already
authorised; the platform records the authorisation, it does not adjudicate it.
No fourth gate is created, and N-02 stands unamended.

**This does not satisfy AC2 as written.** Two paths exist, both reserved to
the ratifier:

- **(i)** Amend `T02.2.4` AC2 to "targets recorded with their commissioning
  authority" — no gate, N-02 intact; or
- **(ii)** Create a fourth gate under N-02's own revisit clause (G12), which
  requires demonstrating research-target selection *"carries consequence
  comparable to G1–G3"* and **supersedes N-02**.

**This record chooses neither.**

### 5.6 Trigger lifecycle

A directive occupies exactly one state at a time:

| State | Meaning |
|---|---|
| `RAISED` | Raised, not yet in effect |
| `IN_EFFECT` | Scopes acquisition |
| `FULFILLED` | Scope satisfied; no further acquisition under it |
| `CANCELLED` | Withdrawn before fulfilment |
| `EXPIRED` | Validity period elapsed |

These are **directive states, not object lifecycle states.** R-2's seven-state
lifecycle governs Intelligence Objects; a directive is not one (§5.1), so no
contract change is implied and R-2 is untouched.

**Token disjointness is deliberate.** `RAISED` and `IN_EFFECT` were chosen
specifically so that **no directive state name collides with any R-2 state
name** (`PROPOSED`, `ACTIVE`, `SUPERSEDED`, `REJECTED`, `RETRACTED`,
`INVALIDATED`, `ARCHIVED`). Disclaiming an overlap in prose is weaker than not
creating one: with disjoint tokens, a reader encountering `ACTIVE` anywhere in
the corpus knows it refers to an Intelligence Object under R-2, and only that.
R-6's closed-vocabulary discipline is thereby preserved without amending R-2.

### 5.7 Cancellation semantics

- Cancelling a directive **stops future acquisition** under it immediately.
- **Evidence already acquired is unaffected.** It remains valid: it was
  lawfully in scope when acquired, and R-1/I4 make it immutable and
  non-deletable. Cancellation is not retraction.
- A cancelled directive is **retained**, not deleted — Evidence `explanation`
  may cite it (G17), and provenance must stay resolvable.
- Cancellation **never** cascades to Evidence. Cascade triggers are RETRACTED
  and INVALIDATED only (N-9); a directive is not upstream lineage.

### 5.8 Acquisition attribution

Every Evidence object acquired under a directive records that directive in its
`explanation`, matching the ratified worked example (G17): *"Acquired under
research directive covering seller-side friction in segment A."* No new
Evidence attribute is introduced.

---

## 6. Interactions

| With | Effect |
|---|---|
| **N-17** | **Supplied, not superseded.** Provides the work-set input G4 says is missing. Scheduling, bounding and directive-vs-reactive are untouched |
| **N-02** | **Untouched.** §5.5 keeps commissioning outside the platform; no fourth gate created. D-1 remains for the ratifier |
| **N-01 / Art. VI** | Respected — the platform holds no authority to commission its own research |
| **AD-05 / R-8** | Form 3 (Research Trigger) gains its origin semantics; behavioural closure preserved; no feedback becomes Evidence |
| **N-10** | Out-of-scope acquisition produces a failure record (§5.2) |
| **N-11** | Untouched — concurrency unchanged |
| **N-07 / CI-1** | A directive is infrastructure state and must not enter reasoning, scoring or lineage (G18) |
| **N-9 / R-1** | Cancellation never cascades and never mutates acquired Evidence (§5.7) |
| **M-16** | **No interaction** — directives scope *subject matter*, not source type |
| **M-17** | Coverage consumes `OUT_OF_SCOPE` as a gap reason (DRAFT N-22 §5.4). This record supplies the notion of scope; it does not define coverage |
| **M-18** | **No interaction** — an in-scope target may still be refused on rights. Both gates apply |

### Phase 2 tasks

| Task | Effect |
|---|---|
| `T02.2.4` | AC1 (§5.2) and AC3 (§5.2) satisfied. **AC2 blocked by D-1** |
| `T02.2.1` | Acquisition gains its scoping input; still blocked on M-18 |
| `T02.1.4` | `OUT_OF_SCOPE` gap reason becomes meaningful |
| `T08.3.4`, `T07.3.8` | Gain a lawful destination for feedback/validation-raised directives |

---

## 7. Consequences Accepted

1. **The platform cannot start its own research.** Every directive traces to
   an external commission or a ratified mechanism. This limits spontaneous
   discovery — B-58 records the cost: *"Limits spontaneous discovery."*
2. **No acquisition without a directive**, so the platform is inert until one
   exists. Deliberate: it is the only reading consistent with G6.
3. **A fifth artefact-with-states enters the system** (the directive). It is
   not an Intelligence Object (G19) and carries no lineage, but it is
   additional machinery to operate.
4. **D-1 is not resolved**, so `T02.2.4` cannot complete as written.
5. **Self-direction stays open** (§5.4), so target proposal remains
   unavailable even where it would be useful.

---

## 8. Alternatives Considered

Options A, B, C in §3, each rejected with the ratified constraint it fails
(A: G1/G3/G6; B: G1/G2; C: G8/G9/G10).

---

## 9. Compatibility Analysis

| Ratified item | Effect |
|---|---|
| **N-17** | Supplied, not superseded |
| **N-02** | Untouched — no fourth gate |
| **N-01 / AD-05 / R-8** | Respected; AD-05 form 3 given origin semantics |
| **N-09 / R-1 / R-2** | Untouched — directive states are not object states |
| **N-10 / N-11 / CI-1** | Consistent |
| **Playbook F8** | No engine, object or stage added |
| **Frozen documents** | None rewritten (F5) |

**Superseded decisions: NONE.**

## 10. Markers Closed

| Marker | Status |
|---|---|
| **M-01** | **CLOSED (partially)** — initiation, originators, trigger lifecycle, scoping, cancellation: §5.1–§5.8 |

Not closed by this record: **research continuation / self-directed target
selection** (§5.4, D-2), and any human-approval gate for targets (§5.5, D-1).

Partial closure follows ratified precedent: S-05 *"Closes | M-67 (partially)"*;
R-08 *"Closes | C-04 (jointly with AD-05)"*.

## 11. Markers Intentionally Left Open

| Marker | Why |
|---|---|
| **Self-direction (no canonical ID — D-2)** | Whether Research may propose its own targets; G6 currently forbids it |
| **OQ-11** | Backflow permission; §5.3 reserves the form without permitting it |
| **M-16 / M-17 / M-18** | Untouched by this record |
| **M-56** | Cost model — directives imply budget questions this record does not address |

## 12. Follow-up Work

1. **Resolve D-1** (§2.1, §5.5) — amend `T02.2.4` AC2, or create a fourth gate
   superseding N-02. **`T02.2.4` cannot complete until this is decided.**
2. Assign a canonical identifier to the self-direction question (D-2), or
   record that it is deliberately unassigned.
3. Record M-01's partial closure in `marker-crosswalk.md` (governance
   artefact, not frozen).
4. Confirm whether directive states (§5.6) require any register treatment
   analogous to R-2.

## 13. Revisit Conditions

- Self-direction is decided, requiring §5.3 to admit a platform originator.
- OQ-11 resolves, confirming or removing `VALIDATION_BACKFLOW`.
- N-17's P6 revisit changes the control model from scheduled batch.
- **Not** grounds for revisit: the inconvenience of requiring a directive.

---

## 14. Formal Consistency Challenge

Attacked against every constraint G1–G21.

| Attack | Result |
|---|---|
| Contradicts N-17's scheduled-batch model (G1, G3)? | **No** — §5.2 scopes, never schedules; bounding untouched |
| Makes Orchestration reactive (G2)? | **No** — directives are planned inputs to a cycle, not events reacted to |
| Lets Research decide what to research (G6)? | **No** — §5.2/§5.3; Research consumes scope, never authors it |
| Creates a fourth human gate (G11)? | **No** — §5.5 keeps commissioning pre-platform. This is *why* D-1 remains unresolved |
| Breaches AD-05 exhaustiveness (G9, G10)? | **No** — it gives form 3 a home rather than adding a fifth form |
| Lets feedback become Evidence (G14)? | **No** — a directive causes acquisition of *external* Evidence; no lineage path |
| Adds an object/engine/stage (G19)? | **No** — the directive is infrastructure state |
| Changes R-2's lifecycle? | **No** — §5.6 states directive states are not object states |
| Cascades on cancellation (N-9)? | **No** — §5.7; triggers remain RETRACTED/INVALIDATED only |
| Violates CI-1 (G18)? | **No** — directives scope acquisition; they contribute nothing to reasoning or scoring |
| Violates precedence (G21)? | **No** — §2.1 applies Art. XI to resolve backlog-vs-decision in N-02's favour |
| Decides OQ-11 or self-direction? | **No** — both explicitly left open |

**One blocking contradiction, classified.** **D-1** (§2.1): `T02.2.4` AC2 vs
N-02's exactly-three-gates. **Classification:** Implementation Backlog vs
ratified decision record — resolved *in principle* by Art. XI in N-02's
favour, meaning the backlog AC is unsatisfiable as written. **Does it block
ratification of N-23?** **No.** **Does it block completion of `T02.2.4`?**
**Yes.** Reported, not resolved.

**Why the draft survives.** Every clause either (a) supplies an input a
ratified decision states is missing (G4/G5), (b) gives an existing ratified
artefact its undefined origin (G8/G9), or (c) declines to decide where the
corpus is silent (§5.4, §5.5, OQ-11). No clause creates authority, adds an
object type, or introduces a requirement absent from G1–G21.

---

## 15. Honest Limitations

- **D-1 is the substantive finding of this draft, and I cannot resolve it.**
  The backlog assumes a human gate the ratified architecture does not provide.
  A ratifier must choose between amending an acceptance criterion and
  superseding N-02 — the latter is significant, since N-02's revisit clause
  demands proof of *"consequence comparable to G1–G3"*.
- **§5.3's three originators are the element least derivable from the corpus.**
  `FEEDBACK_RESEARCH_TRIGGER` traces directly to AD-05 form 3 and
  `EXTERNAL_COMMISSION` to G5/G13, but `VALIDATION_BACKFLOW` is included on
  the strength of an *unratified* B-63 recommendation plus AD-05's
  exhaustiveness. A ratifier may reasonably drop it pending OQ-11.
- **§5.6's five directive states are constructed**, not quoted. They are
  deliberately kept outside R-2 so no contract change occurs, but the corpus
  does not enumerate them.
- **D-2 suggests a register gap:** B-59's "OQ-07" does not match canonical
  OQ-07, and the crosswalk records no collision. Either B-59 miscites, or a
  question exists with no identifier. I did not audit B-nn citations
  systematically for further mismatches.
- This record makes the platform *inert without a directive*. That is the
  correct reading of G6, but it means ratifying M-01 does not by itself make
  research operational.

---

**Status: `DRAFT`. Not ratified. Requires explicit human sign-off (F6).**
