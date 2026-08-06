# Architecture Decision Proposal — M-16: Source Taxonomy, Eligibility and Trust

| Field | Value |
|---|---|
| **Proposed ID** | `N-20` (next free in the N- series) |
| **Title** | Source Model: Taxonomy, Eligibility and Trust |
| **Status** | **`PROPOSED` — NOT RATIFIED. Not implementable until signed off.** |
| **Author** | Lead Engineer (investigation for `T02.1.1`) |
| **Date recorded** | 2026-08-04 |
| **Source** | PKP v2 §9/§13; IOM §3.1, §5.2; Blocker Resolution B-33; crosswalk |
| **Would close** | **M-16** (incl. subsumed OQ-28) |
| **Would partially touch** | **M-02** / **M-43** (learning target membership) — see §7 |
| **Backlog task** | `T02.1.1` |
| **Depends on** | AD-01, R-3, S-02, N-16, N-15, N-05 |
| **Supersedes** | — |

> **This document proposes. It does not decide.** Under `AGENT-PLAYBOOK` §2 F2/F3
> and `decisions/README` §"a marker is closed only by a record in this
> register", nothing here may be implemented until ratified by a human.

---

## 1. FACTS — extracted from ratified documents

Every statement below is quoted or directly cited. Nothing is inferred.

### 1.1 The gap is canonical, open, and highest-severity

**PKP v2 §9 (line 620)** — the defining statement:

> **MISSING-16:** No source taxonomy, no eligibility criteria, no source trust
> or credibility model. Since all platform trust derives from evidence quality,
> and no engine assesses source quality, weak and strong sources are
> structurally indistinguishable throughout the platform. **This is the
> highest-severity omission in the engine set.**

**PKP v2 §13** (line 1785), under *"Must resolve in P2 (Research) — 4 items"*:

> | M-16 | Source taxonomy, eligibility, trust model |

**PKP v2 §14** (line 1647) — phase readiness:

> | P2 Research | — | 16-01-18-17 | **Blocked** on MISSING-16 |

**PKP v2 §10** (line 1243) — the object model itself:

> | Source / source trust | implied by Evidence | **MISSING-16** |

### 1.2 The identifier is correct — collision checked

`decisions/marker-crosswalk.md` §3, collision #4:

> | 4 | `MISSING-18` | Source taxonomy / trust | **M-16** | *(v2 M-18: Legal,
> licensing, terms-of-use)* | Would close the wrong gap |

§5 records an intentional merge:

> | **M-16** | IOM MISSING-18 (taxonomy) + OPEN QUESTION-28 (source trust) |
> Source trust is an attribute of the source model, not a separable gap |

**Therefore M-16 covers taxonomy *and* trust.** v2's own M-18 (legal/licensing)
is a distinct gap owned by `T02.1.2`. The backlog's "(M-16)" is already
canonical.

### 1.3 No ratified decision closes M-16

Exhaustive extraction of the `Closes` field from all 37 records in
`decisions/`:

```
AD-01..05, N-01..N-19, R-01..R-08, S-01..S-05
```

M-16 appears in **no** `Closes` field. Within `decisions/`, the string `M-16`
occurs **only** in `marker-crosswalk.md`, which maps identifiers and decides
nothing. Verified mechanically: `validation/verify_t02_1_1_blocker.py`, 32/32.

M-02 is likewise unclosed.

### 1.4 The Evidence contract as frozen (IOM §3.1)

| Attribute | Status | IOM annotation |
|---|---|---|
| `source_identifier` | **Required** | "Stable identifier of the origin, sufficient to assess independence" |
| `source_type` | **Required** | "Category of source **(MISSING-18: no taxonomy exists)**" |
| `source_reliability` | **Optional** | "Trust assessment of the source **(OPEN QUESTION-28)**" |
| `source_independence_group` | **Optional** | grouping of non-independent sources |

Validation rules E-V1…E-V6 and integrity constraints E-I1…E-I4 **impose no
constraint on `source_type`'s value** and never mention `source_reliability`.

The IOM's only concrete value anywhere is a worked example:
`source_type: customer_review_corpus` (§3.1). **No enumeration exists.**

### 1.5 The consequence of the gap, stated in the IOM

IOM §3.1, Confidence:

> `evidential_support` reflects source reliability (OPEN QUESTION-28
> unresolved — **absent a trust model, all sources weigh equally, a strong
> unstated assumption**).

### 1.6 S-02 constrains what trust may affect — decisively

`S-02` (RATIFIED) defines `evidential_support` with **five exhaustive inputs**:

| # | Input |
|---|---|
| 1 | Independent source count |
| 2 | **Source diversity** — "Number of distinct source *types* represented" |
| 3 | Corroboration depth |
| 4 | Contradiction presence |
| 5 | Upstream support |

> **No other input.**

**Source trust is not among them.** Two consequences follow directly:

- **(a)** Input 2 already *depends on* a source-type vocabulary. S-02 and N-16
  (Tier 2, `source_diversity`) are **already resting on M-16**. Pattern
  `PT-V4` mandates `source_diversity`; IOM §3.4 says computing it "requires
  evidence-level information four stages upstream — see MISSING-22,
  unresolved."
- **(b)** Making trust an input to `evidential_support` would **amend S-02**,
  which is a ratified decision. That is out of scope for closing M-16 and
  would require a superseding record.

### 1.7 The Blocker Resolution analysed this — but ratified nothing

`PKP_PreP1_Blocker_Resolution.md`, header:

> **Status:** Analysis and recommendation. **No decision herein is ratified.**

**B-33 — Source Taxonomy, Eligibility and Trust** (line 951):

> **Canonical:** M-16, with OQ-06 | **Blocks:** P2
>
> **Options.** (1) Open — any accessible source. (2) Whitelist. (3) Typed
> taxonomy with per-type eligibility. (4) Typed taxonomy with per-source trust
> ratings, learnable.
>
> **Recommendation. Option 4.** Trust ratings are needed for contradictory
> evidence and are the safest, most valuable learning target. Absent this, all
> sources weigh equally — a strong, unstated, and almost certainly false
> assumption.
>
> **Trade-offs.** Trust ratings risk entrenching bias if learned unchecked.
> Mitigated by B-25's diversity floors.
>
> **Dependencies.** M-18 (legal/licensing); B-27; B-24.
> **Timing.** Before **P2**.

**This is the origin of the backlog's wording** ("per-type eligibility and
learnable trust ratings" = B-33 Option 4). It is a *recommendation in an
unratified analysis document* — which is precisely why `T02.1.1` reads as
though the decision exists when it does not.

### 1.8 Learning ownership (M-02 / M-43)

**B-24 — Learning Target and Write Mechanism** (unratified):

> **Canonical:** M-02 and M-43 | **Blocks:** P8
>
> **Recommendation. Option 4, beginning with confidence calibration and source
> trust.** These two targets address the platform's two most damaging failures
> (confidence inflation, sampling bias) and are the most reversible.

**B-25 — Feedback Loop Instability Guard** (unratified, canonical **M-70**):

> **Recommendation. Option 4.** … **diversity floors prevent the platform
> narrowing its own evidence base** …

v2 §13 lists both **M-02** ("What the platform learns — the target of change")
and **M-43** ("Feedback Engine write target") as open. `R-07` (Feedback Record)
closed C-03 only; the `change_target` vocabulary remains undefined.

### 1.9 Related ratified decisions that constrain any source model

| Decision | Constraint imposed |
|---|---|
| **AD-01 / Art. IV / AD-05** | Evidence must originate from external reality; no platform artifact may become Evidence. A trust rating is *metadata about* a source, never Evidence. |
| **R-3** | Two-component confidence; Evidence sets the ceiling and is unconstrained from above. |
| **S-02** | Five exhaustive inputs; trust is not one (§1.6). |
| **N-16** | `independent_source_count` universal (Tier 1); source *types* via Tier 2 traversal, needed by Pattern only. |
| **N-15** | Hybrid storage constrained by licensing (M-18). |
| **N-05** | Tenancy reserved; M-18 licensing "may activate trigger 2". |
| **N-07 / CI-1** | Configuration is infrastructure state and **must never participate in reasoning, scoring, pattern detection, or lineage**. Critical: if trust ratings live in configuration, CI-1 forbids them influencing scoring. |
| **N-04** | Reproducibility: `engine_configuration_ref` must resolve at any historical point. A mutable trust rating must be versioned to preserve this. |

### 1.10 Downstream dependants

`T02.1.2` (licensing, M-18), `T02.1.3` (independence grouping),
`T02.1.4` (coverage, M-17), `T02.2.1` (acquisition), and — via S-02 input 2 and
PT-V4 — `T05.1.x` Pattern source diversity.

---

## 2. ASSUMPTIONS

**None are adopted.** The following are *candidate* assumptions that a
ratifier must accept or reject explicitly. Each is listed because implementing
`T02.1.1` silently would have smuggled it in.

| # | Candidate assumption | Why it is not a fact |
|---|---|---|
| A1 | The taxonomy should be a closed enum in code | Backlog AC1 says "closed taxonomy"; no ratified source enumerates members |
| A2 | B-33 Option 4 is the intended resolution | B-33 is explicitly unratified analysis |
| A3 | Trust is numeric (e.g. 0.0–1.0) | No ratified source states a scale, range or type |
| A4 | An unrated source gets a neutral default | No ratified default exists; "all sources weigh equally" is described as a *flaw*, not a policy |
| A5 | Trust may influence `evidential_support` | **Contradicted** by S-02's "No other input" (§1.6) |
| A6 | Source trust is a P8 learning target | B-24 recommends it; M-02/M-43 remain open |
| A7 | `source_reliability` becomes required | IOM §3.1 marks it optional; changing it edits a frozen contract |

---

## 3. UNRESOLVED QUESTIONS — must be answered by the ratifier

| # | Question | Blocking for |
|---|---|---|
| Q1 | What are the **exhaustive members** of the source-type taxonomy? | AC1 |
| Q2 | Is the taxonomy closed-by-decision (extension requires a superseding record), or open with a registry? | AC1 |
| Q3 | What is the **eligibility** predicate per type — and how does it differ from M-18 licensing (`T02.1.2`)? | AC1, T02.1.2 boundary |
| Q4 | What is trust's **scale, range and semantics**? | AC2 |
| Q5 | What is the **default** for an unrated source, and does an unrated source block acquisition? | AC2 |
| Q6 | Where is trust **stored** — on Evidence (`source_reliability`), or in a source registry keyed by `source_identifier`? | AC2, CI-1 |
| Q7 | If in a registry: is that registry configuration? If so, **CI-1 forbids it influencing scoring** — how is that reconciled with its purpose? | CI-1, N-07 |
| Q8 | Does trust affect `evidential_support`? If yes, **S-02 must be superseded** — a separate decision. | S-02 |
| Q9 | If trust affects nothing scored, what *does* it affect — and is it then worth the bias risk? | Coherence |
| Q10 | Is source trust a legitimate **P8 learning target**? That is M-02/M-43 territory. | AC3 |
| Q11 | Who may **write** trust, under what authority, and how is N-04 reproducibility preserved across updates? | AC3, N-04 |
| Q12 | What guards learned trust against **bias entrenchment** (B-33 trade-off, B-25/M-70 diversity floors — both open)? | AC3, M-70 |
| Q13 | Does closing M-16 require amending the frozen Evidence contract (F5, annotation layer)? | IOM |

**Q8 is the crux.** M-16 exists because "weak and strong sources are
structurally indistinguishable". The only ratified mechanism that could
distinguish them — `evidential_support` — is closed to new inputs by S-02.
**Closing M-16 meaningfully appears to require superseding S-02.** This
tension is not resolvable by implementation and is the single most important
finding of this investigation.

---

## 4. PROPOSED DECISION (for ratification — not implemented)

**Recommended shape: a staged, three-part decision**, mirroring how N-10
separated representation from policy.

### Part 1 — Taxonomy (unblocks AC1)

Adopt a **closed source-type taxonomy** whose members are enumerated *in the
decision record*, not chosen in code. Extension requires a superseding record
(same rule as R-6's ten relationship types and R-2's seven states).

Because no ratified member list exists, **the ratifier must supply it.** A
defensible starting set, derived only from source material actually named in
the corpus (v1 §7 "Completed Research": Etsy marketplace data, resume
templates, customer complaints; IOM's `customer_review_corpus`):

- `marketplace_listing`, `customer_review_corpus`, `complaint_record`,
  `public_dataset`, `editorial_content`, `vendor_documentation`,
  `community_forum`, `regulatory_filing`

**This list is illustrative of the *form* required. It is not proposed as
correct** — inventing it is exactly what F3 forbids.

### Part 2 — Eligibility (unblocks AC1's "per-type")

Per-type eligibility recorded as a **declarative predicate in the decision**,
evaluated at acquisition. Scope boundary to state explicitly: eligibility here
means *"is this kind of source admissible as grounding at all"*; **legal
admissibility is M-18 / `T02.1.2`** and must not be duplicated.

### Part 3 — Trust (AC2, AC3) — **recommend deferring the learnable half**

Split, as N-10 split representation from policy:

- **3a — Representation (close now).** Trust is recorded as a **first-class
  attribute of a source registry keyed by `source_identifier`**, versioned to
  satisfy N-04, and **mirrored onto Evidence at acquisition** into the existing
  optional `source_reliability`. Recording it changes no scoring and therefore
  does not disturb S-02.
- **3b — Effect on scoring (defer; requires superseding S-02).** Whether trust
  weights `evidential_support` is **not** decided here. Until decided, trust is
  *recorded and visible but non-scoring*, and the "all sources weigh equally"
  assumption remains in force **and remains explicitly labelled a known flaw.**
- **3c — Learnability (defer to P8; M-02/M-43/M-70).** Declaring trust a
  learning target adds a member to an undefined set (M-02) with an undefined
  writer (M-43) and no instability guard (M-70, B-25). Recommend the record
  state trust is *a candidate* target, with membership decided when M-02 is
  closed.

### Consequence for `T02.1.1`

Under this staging, `T02.1.1` becomes implementable for **AC1** and **AC2**,
while **AC3 ("learnable target for P8") cannot be satisfied** — it depends on
M-02/M-43, which are P8-scheduled. The ratifier should either:

- **(i)** amend `T02.1.1`'s AC3 to "trust is *representable* as a future
  learning target; membership deferred to M-02", or
- **(ii)** accept that `T02.1.1` stays blocked until M-02 is closed.

**Recommendation: (i).** It unblocks P2 without pre-empting P8, and matches the
precedent set by N-10 (representation closed, policy left open) and C-02
(fails closed, surfaced, not invented).

---

## 5. CONSEQUENCES IF RATIFIED AS PROPOSED

**Accepted:**

1. **Trust is recorded but does not score.** The platform's highest-severity
   omission is only *partially* closed — weak and strong sources become
   *distinguishable to a reader* but remain *equal to the scoring function*.
   This must be stated plainly, not presented as a full fix.
2. **A source registry is a new persistent structure.** It is not an
   Intelligence Object (F8 forbids a tenth object). Its relationship to
   configuration and CI-1 must be settled (Q7).
3. **`source_reliability` stays optional**, so no frozen contract is amended.
4. **S-02 is untouched**, so no ratified decision is disturbed.
5. **Bias risk is deferred, not solved** (B-33 trade-off; M-70 open).

**Rejected alternatives:**

- **Close M-16 fully now, including scoring.** Rejected: requires superseding
  S-02 and pre-empting M-02/M-43/M-70 in one step — four ratified/open
  concerns at once.
- **Whitelist only (B-33 Option 2).** Rejected: no eligibility criteria exist
  to populate a whitelist; defers the same gap.
- **Open acquisition (B-33 Option 1).** Rejected: contradicts v2's framing of
  M-16 as highest-severity and leaves `source_type` unscoped.

---

## 6. AFFECTED TASKS

| Task | Effect |
|---|---|
| **`T02.1.1`** | Unblocked for AC1/AC2 under §4; AC3 requires amendment (§4 (i)) |
| `T02.1.2` | Boundary must be explicit: M-18 legal ≠ M-16 eligibility |
| `T02.1.3` | Independence grouping consumes `source_identifier`; unaffected by trust |
| `T02.1.4` | Coverage (M-17) measured *per source type* — depends on Part 1 |
| `T02.2.1` | Acquisition must populate `source_type` from the closed taxonomy |
| `T05.1.x` | Pattern `source_diversity` (PT-V4, S-02 input 2) depends on Part 1 |
| `T08.x` | Learning-target membership deferred to M-02/M-43 |

---

## 7. MARKERS

| Marker | Effect of this proposal |
|---|---|
| **M-16** | **Would close** Parts 1–2 and 3a; **3b/3c remain open** — so M-16 would close *partially*. A ratifier preferring atomic closure should split M-16 into M-16a (taxonomy/eligibility/representation) and M-16b (scoring/learnability). |
| OQ-28 | Subsumed into M-16; closed with 3a |
| M-02 / M-43 | **Untouched** — explicitly not closed |
| M-70 | **Untouched** — instability guard remains open |
| M-18 | **Untouched** — `T02.1.2` |
| M-17 / M-23 | Unblocked downstream by Part 1 |

---

## 8. VERIFICATION

Every factual claim above is machine-checked by
`platform/validation/verify_t02_1_1_blocker.py` — **32/32 passing**, covering:
M-16 open in v2 §13; no `Closes` field naming it; crosswalk collision #4;
OQ-28 subsumption; IOM's unscoped `source_type`; the "all sources weigh
equally" statement; M-02 open; playbook F2/F3/F12.

**No production code was modified. No tests were created. `T02.1.1` was not
implemented.** `oip/` remains 28 modules; `cascade.py` `b603ce9e…`,
`integrity.py` `42f1a950…`.
