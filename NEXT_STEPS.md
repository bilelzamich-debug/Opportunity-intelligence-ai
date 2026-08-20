# Next Steps

**What happens next, what blocks it, and who must act.**
Current as of **2026-08-19** — D-1 resolved, `T02.1.3` closed, N-24 ratified.
Prior state: 2026-08-04 (ratification of N-20…N-23).

---

## 1. The Short Version

Both decisions required from the **Project Owner** are now taken:

| # | Decision | Status |
|---|---|---|
| **1** | Resolve **D-1** — amend `T02.2.4` AC2, or create a fourth human gate superseding N-2 | ✅ **RESOLVED 2026-08-19** — Option A / N-23 §5.5(i). AC2 now reads *"Targets recorded with their commissioning authority"*; N-2 unchanged; no fourth gate |
| **2** | **Name the acquisition-rights authority** required by N-21 §5.1 | ✅ **RESOLVED 2026-08-19** — `N-24` **RATIFIED**: the role *Designated Source Rights/Compliance Authority*, scope narrowed to the N-21 §5.5 vocabulary, as audited. Acquisition still refuses everything until the role supplies assessments (`UNASSESSED`, fail-closed) |

**What is executable now:** `T02.1.2` (**implementable** — N-24
ratified; operational only when the role supplies assessments). It awaits
authorisation per project workflow. ~~`T02.1.1` AC1/AC2~~ — ✅ done
2026-08-19. ~~`T02.1.4`~~ — ✅ **CLOSED 2026-08-19**: `oip/coverage.py`
implements N-22 §5 exactly (coverage over types; closed five-reason gap
vocabulary; out-of-frame register per AS-4; declared-completeness; no
stopping rule; undefined-never-defaulted; inheritable declarations). Suite
3,242; verifier 33/33; mutation 14/14.

---

## 2. Decision 1 — D-1: The Missing Human Gate — ✅ RESOLVED

> **Resolution (2026-08-19).** The Project Owner selected **Option A** —
> amend `T02.2.4` AC2 using the exact wording pre-specified by N-23 §5.5(i):
> *"Targets recorded with their commissioning authority."* No fourth gate;
> N-2 stands unamended; commissioning remains a pre-platform act the platform
> records but never adjudicates. Recorded in
> `docs/governance/RATIFICATION-ANNOTATIONS.md` §11. `T02.2.4` and its 22
> downstream P7–P8 tasks are unblocked.

The original conflict analysis is retained below for the record.

### The conflict

`T02.2.4` acceptance criterion 2 states:

> "Targets proposed for approval **per human-gate decision**."

**N-2 (RATIFIED)** states:

> "Human judgement enters the platform at **exactly three gates**. Everywhere
> else the platform runs autonomously."
>
> G1 Opportunity selection · G2 Post-validation promotion · G3 Learning application

**Research target approval is none of the three.** Under Constitution Article
XI (decision records outrank the Implementation Backlog), N-2 governs and the
acceptance criterion is **unsatisfiable as written**.

N-23 §5.5 takes the only position consistent with N-2: commissioning is a
**pre-platform act**, so no fourth gate is created. That resolves the
architecture but leaves the backlog AC unmet.

### The two options

**Option A — Amend `T02.2.4` AC2.** ✅ **SELECTED 2026-08-19.**
Reword to something like *"targets recorded with their commissioning
authority"*. No gate is created; N-2 stands unamended; the backlog aligns with
the ratified architecture.
*Cost:* an acceptance criterion changes. *Risk:* low.

**Option B — Create a fourth gate, superseding N-2.**
N-2's own Revisit Conditions permit this, but set a high bar:

> Reconsider only if… "A fourth transition is shown to carry **consequence
> comparable to G1–G3**."

*Cost:* supersedes a ratified decision; adds a human dependency to every
research cycle. *Risk:* significant — N-2 warns that "Removing a gate transfers
its accountability to the platform, which requires superseding N-1", and the
inverse (adding one) expands human load on the highest-frequency operation in
the pipeline.

### Board observation

Option A is the smaller change and matches what N-23 already ratified. Option B
requires demonstrating that choosing *what to research* carries consequence
comparable to *releasing a validated solution to a decision-maker* — a claim no
one has yet made. **This is your call, not the board's.**

---

## 3. Decision 2 — Name the Rights Authority — ✅ RATIFIED AS N-24 (2026-08-19)

> **Status (2026-08-19).** N-24 is **RATIFIED**. The authority is the
> **role** *Designated Source Rights/Compliance Authority* — a role, not an
> individual. Scope is deliberately narrow, exactly as audited: limited to
> issuing acquisition-rights and retention-rights assessments in the closed
> vocabulary of N-21 §5.5, with no broader compliance powers. **Sources
> remain `UNASSESSED` and acquisition remains fail-closed until the role is
> staffed and supplies assessments** (N-21 §6 item 2); `T02.1.2` is
> implementable, not operational.

N-21 §5.1 states:

> "Acquisition-rights policy is owned by a **named human authority outside the
> platform**, consistent with N-1/Article VI: the platform 'holds no budget, no
> operational authority, and no accountability for consequences'."

**The record deliberately names no one.** That was correct — naming an
organisational role is not an architectural decision — but it has a hard
consequence:

- N-21 §5.4 makes `UNASSESSED` **fail closed**: silence is not permission.
- Every source begins `UNASSESSED`.
- Therefore **acquisition refuses everything** until an authority exists and
  supplies assessments.

### What is needed

1. A named role or person accountable for acquisition-rights determinations.
2. A process by which assessments (`PERMITTED` / `PROHIBITED`, plus retention
   rights) reach the platform.
3. Confirmation that this division — platform *applies*, human *decides* — is
   acceptable to whoever carries the legal risk.

**Note on competence.** N-21 carries an explicit warning: architecture can
specify *where* the legal question is asked and *how* the answer is recorded.
It cannot determine what is lawful. If legal counsel is required, that is a
precondition to Phase 2 completion, not a detail.

---

## 4. Once Unblocked — Phase 2 Execution Order

Both decisions are taken (D-1 resolved; N-24 ratified).
Work proceeds in this order. Dependencies are the *real* ones, verified
against the ratified corpus, not merely the backlog's declared edges.

| # | Task | Status now | Notes |
|---|---|---|---|
| 1 | `T02.1.3` Independence grouping | ✅ **CLOSED 2026-08-19** | Explicit-input model ratified; existing code + tests are the evidence. Its dependent `T02.1.4` is unblocked |
| 2 | `T02.1.1` complete AC1/AC2 | ✅ **DONE 2026-08-19** | `SourceType` populated exactly from N-20 §5.1; the verifier matches the enum to the decision table mechanically (38/38; mutation 21/21). **AC3 stays blocked** on M-02/M-43 |
| 3 | `T02.1.4` Coverage model | ✅ **CLOSED 2026-08-19** | `oip/coverage.py`: AC1 coverage measurable · AC2 explicit declarations · AC3 inheritable by PT-V5. Verifier 33/33; mutation 14/14 |
| 4 | `T02.1.2` Licensing enforcement | 🟢 **Implementable** | N-24 ratified; operational only when the role supplies assessments |
| 5 | `T02.2.1` Acquisition | 🟡 Sequenced | Depends on `T02.1.2` |
| 6 | `T02.2.2` Duplicate detection | 🟡 Sequenced | E-V6 already implemented in P1; needs acquired Evidence |
| 7 | `T02.2.3` Drift detection | 🟡 Sequenced | Specification complete (N-15 binds it) |
| 8 | `T02.2.5` Failure recording | 🟡 Sequenced | Specification complete (N-10) |
| 9 | `T02.2.4` Directive intake | 🟡 **Unblocked 2026-08-19** | D-1 resolved (N-23 §5.5(i)); sequenced behind `T02.2.1`, `T01.6.1` |
| 10 | `T02.3.1` P2 exit gate | 🔴 Blocked | Requires all of the above + operational acquisition |

### The tasks available right now

**`T02.1.1` AC1/AC2 — populate `SourceType` from N-20 §5.1.** The eight
members are ratified; the enum is empty by design awaiting exactly this act.
No new decision is required — NEXT_STEPS §7 explicitly sanctions populating
from N-20 §5.1 and from nothing else.

**`T02.1.4` — coverage model.** Unblocked by `T02.1.3`'s closure; N-22 fully
specifies it.

Both await Project Owner authorisation per project workflow. **The
`T02.1.3` AC1 ambiguity is resolved**: the Project Owner selected the
explicit-input model (2026-08-19) — `source_independence_group` is carried and
honoured when supplied, and **no syndication/ownership inference is performed
without a ratified rule**. Recorded in RATIFICATION-ANNOTATIONS §11.

---

## 5. Follow-Up Work From Ratification

Recorded in the ratified records themselves; none blocks Phase 2.

| # | Item | Source |
|---|---|---|
| 1 | Decide whether M-17's stopping half is tracked separately or folded into M-01 | N-22 §12 |
| 2 | Resolve `source_diversity`: IOM §3.4 says "sources", S-2 says "types" — blocks clean PT-V4 | N-22 §12 |
| 3 | Assign a canonical identifier to the self-direction question (**D-2**), or record it as deliberately unassigned | N-23 §12 |
| 4 | Decide whether **M-18b** (robots, rate limits) is scheduled or deferred | N-21 §10 |
| 5 | Confirm whether directive states need register treatment analogous to R-2 | N-23 §12 |

---

## 6. Deferred to Later Phases

| Marker | Concern | Phase |
|---|---|---|
| **M-02 / M-43** | Learning target vocabulary and Feedback write authority | P8 |
| **M-70** | Feedback loop instability guard | P8 |
| **M-16** (scoring) | Whether trust weights `evidential_support` — requires **superseding S-2** | Undecided |
| **M-17** (stopping) | When has the platform researched enough | Follows M-01 |
| **C-02** | Execution Record has no producing engine | P8 |
| **M-55** | Security / access-control scope | P9 |

---

## 7. What NOT To Do

Recorded because each is a live temptation and each would breach governance:

- ❌ **Do not populate `SourceType` from anything except N-20 §5.1.** The enum
  is empty by design in the P1-era code; it may now be filled *only* from the
  ratified member list.
- ❌ **Do not make trust affect scoring.** S-2's five inputs are closed ("No
  other input"). Adding a sixth requires superseding S-2 — a separate decision.
- ❌ **Do not invent a rights vocabulary.** N-21 §5.5 is closed; extension
  requires a superseding record.
- ❌ **Do not create a fourth human gate in code.** That is decision 1, and it
  belongs to the Project Owner.
- ❌ **Do not treat an empty coverage frame as 100% coverage.** N-22 §5.7:
  coverage is "undefined and reported as such, never defaulted to 0 or 1".
- ❌ **Do not begin Phase 3.** `T03.1.1` is gated behind `T02.3.1`.

---

## 8. Recommended Immediate Action

Status 2026-08-19:

1. ~~**Answer decision 1** (D-1)~~ — ✅ answered: Option A, N-23 §5.5(i).
2. ~~**Ratify N-24**~~ — ✅ **ratified 2026-08-19** (scope exactly as
   audited). Next organisational step: staff the role and supply
   assessments; until then acquisition stays fail-closed.
3. ~~**Clarify `T02.1.3` AC1`**~~ — ✅ answered: explicit-input model.
4. ~~**Authorise `T02.1.3`**~~ — ✅ closed 2026-08-19 on existing evidence.
5. ~~**Authorise `T02.1.1` AC1/AC2`**~~ — ✅ done 2026-08-19: `SourceType`
   populated from N-20 §5.1 verbatim; suite 3,204; source-model verifier
   38/38; mutation 21/21.

Item 2 is minutes of decision-making that unblocks all acquisition work.
Item 5 can begin immediately on authorisation.
