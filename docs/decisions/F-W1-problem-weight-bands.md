# F-W1 — Problem Weight Model: Severity and Frequency Ordinal Bands

> **RATIFIED 2026-09-14.** The annotation-layer entry recording this
> ratification and its binding interpretation is
> `RATIFICATION-ANNOTATIONS.md` §15, mapping this record to M-12 (partial),
> backlog `T04.1.4`, the T04.1.4 governance specification (WD-1–WD-6) and
> the engine-gate pattern of `T04.1.2`/`T04.1.3`. Ratified by the Project
> Owner as the six approved decisions WD-1–WD-6 (2026-09-14), drafted in
> `platform/validation/T04.1.4-specification.md` (Rev. 2 — in which the
> Rev. 1 WD-4 corroboration ladder was rejected by the Project Owner and
> replaced by the declared-criterion evidence ceiling). Frozen documents
> are not rewritten; the annotation layer records the binding
> interpretation. **Implementation has NOT started; M-12 remains open for
> population scales.**

| Field | Value |
|---|---|
| **ID** | F-W1 |
| **Title** | Problem Weight Model: Severity and Frequency Ordinal Bands |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-09-14 |
| **Date decided** | 2026-09-14 |
| **Source** | Backlog `T04.1.4` ("Implement severity and frequency ordinal bands with evidence-linked justification (M-12)", ⚠ critical-path); `platform/validation/T04.1.4-specification.md` Rev. 2 (WD-1–WD-6 with options and evaluation); Project Owner ratification of WD-1–WD-6 (2026-09-14); PreP1 blocker B-37 (Option 4 recommendation — analysis, not ratified therein); IOM §3.3 (Problem responsibility 3; `severity`/`frequency`; P-V4; P-I4; weight-revision versioning trigger); S-1 (band definition style — observable criteria, single criterion type, worked anchors); S-2 (evidential support → confidence); S-4 (independence-based sufficiency, Problem floor 2); R-3 (two-component confidence — the axis that carries corroboration); R-1/V11; N-4; N-10; N-16; M-12 |
| **Closes** | **M-12 (partially)** — severity and frequency scales. **Population scales remain open** and are not addressed by this ratification |
| **Backlog task** | `T04.1.4` |
| **Depends on** | `T04.1.1` (Problem inference engine, `1a5ce22`); the engine-gate pattern of `T04.1.2` (`5cb0b64`) and `T04.1.3` (`a7b28b35`); S-4; S-2; R-3; N-16; N-10; N-4; R-1/V11 |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Six decisions, ratified by the Project Owner on 2026-09-14 as WD-1–WD-6 of
the T04.1.4 governance specification. The full options analysis lives in
`platform/validation/T04.1.4-specification.md` (Rev. 2, §6).

### WD-1 (R1) — Severity bands

Severity uses **three ordinal bands**: `MINOR` / `MODERATE` / `SEVERE`. The
bands are defined by **observable, evidence-grounded criteria** — a single
criterion type, *the most severe harm category explicitly evidenced in the
linked Facts*, with a criterion↔band bijection:

| Criterion | Band | Observable meaning |
|---|---|---|
| `RECOVERABLE_FRICTION` | `MINOR` | At-most-recoverable cost: lost time, effort, workaround overhead; no stated lasting damage |
| `COMPOUNDING_COST` | `MODERATE` | Stated recurring or compounding cost: money, data quality, customer or productivity loss with stated scope |
| `IRREVERSIBLE_HARM` | `SEVERE` | Stated irreversible or category-defining harm: safety, health, legal exposure, permanent data loss |

**No quantitative severity formula.** The criteria are **content-based,
never count-based**: which band a Problem can claim is a function of what
the evidence states, never of how much evidence there is.

### WD-2 (R2) — Frequency bands

Frequency uses **three ordinal bands**: `EPISODIC` / `RECURRING` /
`PERSISTENT`, defined by **observable, evidence-grounded recurrence
characteristics** — a single criterion type, *the recurrence character
evidenced*:

| Criterion | Band | Observable meaning |
|---|---|---|
| `OCCURRENCE` | `EPISODIC` | Occurrence evidenced, without evidence of repetition or continuity |
| `REPETITION` | `RECURRING` | Repeated occurrence evidenced — the same deficiency arises again across instances or contexts |
| `CONTINUITY` | `PERSISTENT` | Continuous or unabating occurrence evidenced — present whenever the process runs |

**Band names must not imply unsupported numerical rates** — no rate
vocabulary, no quantitative frequency, consistent with B-37's rejection of
Option 3.

### WD-3 (R3) — Rating representation

Ratings use a structured **`WeightRating`**: `band`, `detail`
(preserved free text — the existing explanatory detail remains available
for backward-compatible explanatory content), and an **evidence-linked
justification** whose entries follow the repository's established
`FactContribution`-style mechanism, extended with the typed criterion:
`WeightContribution(fact_ref, criterion, contribution)`. Every entry
cites a specific supporting Fact; citations must be a subset of the
Problem's `supporting_facts`; the justification must be non-empty per
axis. This is the P-V5 precedent (structured rather than prose, so
traceability is mechanically checkable) applied to weight.

### WD-4 (R4) — Declared-criterion evidence ceiling (D-B)

The governing principle:

> **Facts establish an evidence ceiling; they do not automatically
> determine the asserted weight.**

- The **inferer supplies** the requested ordinal rating (N-4 — the engine
  contributes no content of its own).
- **Supporting Facts establish whether the claimed criterion/band is
  defensible**: a criterion is **defensible iff the justification entries
  declaring it cite Facts spanning ≥2 distinct independence keys** (N-16
  Tier-1, ACTIVE Evidence only). **The evidence ceiling is the highest
  defensible criterion's band.**
- **Independent-source count MUST NOT automatically determine severity or
  frequency.** Independent-source evidence may establish the required
  corroboration/sufficiency condition, but **the same sufficiency rule
  applies uniformly across bands and never selects the band**: the ≥2-key
  attestation is a boolean floor identical for `MINOR`, `MODERATE`,
  `SEVERE` and every frequency band — S-4's own measure and floor value
  applied to the weight claim itself ("an inference from a single source
  is that source's opinion").
- The system **must**: accept a supplied rating when its criterion is
  evidence-defensible; **reject** a supplied rating above the evidence
  ceiling; **never automatically upgrade** a lower supplied rating;
  **never infer a higher rating merely because more independent sources
  exist**; **never derive severity/frequency solely from Fact count,
  Evidence count, independent-source count, or evidential_support**.
  Corroboration feeds **confidence** (S-2 → R-3, unchanged); it never
  feeds the band. `evidential_support` is not a ceiling input.
- **Refusal stage:** `WEIGHT_EXCEEDS_EVIDENCE` (N-10 closed-set
  extension), occurring **before irreversible state change** — on the
  standalone path before anything is written; on the versioned path
  before the predecessor leaves ACTIVE. Severity is evaluated before
  frequency; one stage per attempt; the detail names the axis.
- **Declaration-fidelity limitations remain explicitly acknowledged and
  are NOT solved through NLP/LLM/network behavior in T04.1.4.** The
  engine verifies the *form* (typed, per-Fact, subset-conforming
  declarations) and the *attestation* (key span), never the truth of a
  declaration against the Fact's content. Fidelity is the inferer's
  responsibility, sampled by the F-A1 audit; M-67 remains open.

### WD-5 (R5) — Versioned weight increases (E-1)

A versioned increase in severity or frequency requires **all three**:

1. the new rating remains **within the evidence ceiling** (R4, evaluated
   on the successor's own evidence and declarations);
2. **explicit evidence-linked justification** for the higher criterion —
   the entries declaring it cite the specific Facts that evidence it;
3. **at least one additional supporting Fact in the successor** — a Fact
   absent from the predecessor's supporting set, cited by the higher
   criterion's justification. (R-1 immutability fixes the predecessor's
   Facts and content; over an unchanged set, every declaration was
   equally available to the predecessor, so a later increase without new
   evidence is grounded in nothing new and is indistinguishable from
   assertion inflation — the P-I3 population-widening precedent applied
   to weight.)

A **decrease** is allowed without additional supporting Facts (claiming
less is always evidence-safe). A **justification-only revision** creates
a new version according to the existing versioning rules (R-1/V11) but
does not automatically increase the weight. **Refusal stage:**
`WEIGHT_INCREASED_WITHOUT_SUPPORT` (N-10 closed-set extension), before
irreversible state change, leaving the predecessor ACTIVE.

### WD-6 (R6) — M-12 partial closure

**M-12 is PARTIALLY CLOSED** for **severity scales** and **frequency
scales** by this record. **Population scales remain OPEN** and are not
addressed by this ratification (`population_size_estimate` remains an
optional unscaled integer; `affected_population` remains free text).
Partial closure follows the established precedent (S-5 closes M-67
partially; N-20/N-21/N-22/N-23 close their markers partially) and
Playbook F3 (closure only by a ratified decision record — this one). The
marker register records the partial closure in the ratification act, not
by implementation choice.

---

## Context

MISSING-12 (M-12, "Problem attributes — severity, frequency, population
scales") left the Problem's weight attributes unscaled: `severity` and
`frequency` are required non-empty free-text strings (WeightError at
construction), P-V4 checks presence only, and P-I4's detective compares
only the numeric measures (independent_source_count vs the supporting
Facts' counts and distinct Evidence; evidential_support vs contributing
Facts' support) — its own docstring defers ordering to T04.1.4: "no scale
exists (M-12), and inventing an ordering here would pre-empt T04.1.4."
B-37 analysed the options (free text / ordinal bands / quantitative /
ordinal bands with evidence-linked justification) and recommended Option
4 without ratifying it. P4 cannot aggregate problem weight for Pattern
Intelligence or opportunity scoring without scales. The engine's scope
docstring states "never ranks weight" pending this decision.

The first specification draft (Rev. 1) recommended a corroboration ladder
(source count → maximum band). The Project Owner **rejected** it on
2026-09-14 — it treats corroboration as a semantic severity classifier —
and directed the governing principle recorded in R4. Rev. 2 reworked
WD-4/WD-5 accordingly; the rejected ladder is retained in the
specification only as clearly-labelled history (Design D-A).

## Alternatives Considered

**Severity scale (WD-1):** A-1 three bands *(selected)*; A-2 four bands
(`MINOR/MODERATE/MAJOR/CRITICAL` — separates reversible from
irreversible harm, at the cost of the two most contestable boundaries);
A-3 five bands mirroring S-1's count *(rejected — S-1's count exists for
O2 calibration of a continuous measure; severity is categorical, and the
extra rungs manufacture distinctions the evidence cannot ground —
B-37's "false precision")*.

**Frequency scale (WD-2):** B-1 three bands *(selected)*; B-2 four bands
(`ISOLATED/EPISODIC/RECURRING/CHRONIC` — the ISOLATED/EPISODIC boundary
is the weakest observable distinction); B-3 five rate-named bands
(`RARE…CONTINUOUS`) *(rejected — disguised quantitative rates, i.e. B-37
Option 3 by vocabulary)*.

**Representation (WD-3):** C-1 band-only structured replacement
*(rejected — fails AC-2, "traceable to Facts" has no carrier)*; C-2
structured rating preserving detail text with criterion-typed
contributions *(selected)*; C-3 parallel free-text + structured fields,
and a string-prefix sub-variant *(rejected — illusory compatibility,
permanent dual representation; stringly-typed)*.

**Evidence ceiling (WD-4):** D-A corroboration ladder, 2→MINOR /
3→MODERATE / ≥4→SEVERE *(REJECTED by the Project Owner 2026-09-14 —
violates the governing principle: four or five sources confirming a
minor problem would "earn" a higher band; corroboration would move the
weight axis instead of the confidence axis)*; **D-B declared-criterion
ceiling with uniform claim attestation *(selected — R4)***; D-C
declared-criterion ceiling with object-level sufficiency only *(rejected
as less conservative — a single-source harm characterisation could reach
`SEVERE`; Example 1's "two strong independent sources … evidence severe
harm" is read as a requirement)*; D-D confidence-coupled ceiling
*(rejected — conflates the certainty and weight axes; fails Examples 1,
2 and 5)*; D-E detective-only ceiling *(rejected — stores unfounded
weight then flags it; contradicts the refuse-before-write pattern
ratified by T04.1.2/T04.1.3 and Principle 1)*.

**Versioned increases (WD-5):** E-1 strict additional-support *(selected
— R5)*; E-2 ceiling-only *(rejected — a successor over an unchanged
supporting set could assert a higher band than its predecessor claimed
from the same Facts, indistinguishable from assertion inflation)*; E-3
was-below-ceiling exception *(rejected — the predecessor's ceiling
depends on its own declarations, which the same inferer controls;
self-inflicted and unfalsifiable)*.

**M-12 status (WD-6):** F-1 full closure *(rejected — population scales
undecided; a false register entry)*; F-2 partial closure *(selected —
R6)*; F-3 remain fully open *(rejected as inaccurate once severity and
frequency scales are ratified)*.

## Rationale

The platform's evidence semantics already separate **what the evidence
says** from **how well it is grounded**: S-2/R-3 route support and
corroboration into confidence, and S-4 makes independence a sufficiency
floor, never a gradient. Weight is a content characterisation (how
damaging, how often), so its scale must be defined over content — the
observable harm category and recurrence character evidenced in the
linked Facts — with corroboration reused only in its ratified role: the
uniform boolean attestation floor (S-4's own measure and value, applied
to the claim). This keeps every axis honest: severity/frequency carry
content; confidence carries corroboration (Example 5's distinction, now
structural). Three bands per axis are the coarsest scales that still
give Pattern Intelligence ordinal comparability, minimising B-37's
accepted trade-off (boundary disputes) and its rejected one (false
precision). The declared-criterion mechanism makes the ceiling
computable without semantic engine behaviour: the inferer's typed,
per-Fact declarations are structurally verifiable (subset, non-empty,
key span) while their fidelity — like Fact fidelity — remains with the
inferer and the F-A1 audit, consistent with M-67's open status and
N-4's determinism posture.

## What It Binds

- **Backlog `T04.1.4`** and its three acceptance criteria: ordinal bands
  defined (R1/R2); each rating traceable to Facts (R3); weight never
  exceeds what Facts support — P-I4 (R4).
- **IOM §3.3** as annotated in `RATIFICATION-ANNOTATIONS.md` §15: P-V4,
  P-I4, the `severity`/`frequency` attributes, and the weight-revision
  versioning trigger.
- The future T04.1.4 implementation (NOT started): `Problem` and
  `InferenceRequest` rating fields, P-V4/P-I4 extensions, the engine
  ceiling gate and versioned weight-change gate, and the two N-10
  closed-set extensions `WEIGHT_EXCEEDS_EVIDENCE` and
  `WEIGHT_INCREASED_WITHOUT_SUPPORT`, each before irreversible state
  change. Implementation constraints live in the specification §9–§13
  (module count stays 39; store/acceptance-framework/lifecycle/contract
  untouched; no NLP/LLM/network/UI).
- `T04.1.5` (dedup) and `T04.1.6` (taxonomy): neither may revisit these
  scales; M-22/M-21 remain open.
- The marker register: M-12's partial closure is recorded by this
  ratification act only.

## Non-Goals

Population scales — the open remainder of M-12. Problem taxonomy (M-21,
`T04.1.6`) — `problem_domain` remains free text. Problem identity and
deduplication (M-22, `T04.1.5`). Pattern thresholds and type taxonomy
(M-24/M-25). Quantitative severity or frequency formulas (B-37 Option 3,
rejected). Engine auto-derivation, defaulting or upgrading of ratings
(N-4). Automatic upgrades of below-ceiling ratings. Semantic
verification that a declared criterion matches a Fact's actual content —
no NLP, no LLM, no network (M-67/F-A1 audit territory). New modules
(module count stays 39), new lifecycle paths, new graph relationships,
DUPLICATES linking, identity merging. Store, acceptance-rule framework,
lifecycle or contract changes. README/roadmap updates.

## Consequences Accepted

- **Declaration fidelity is unverifiable at write time.** The engine
  verifies form and attestation, not content truth. A mis-declared
  criterion is structurally indistinguishable from an honest one until
  audited. Mitigated (not solved) by typed explicit per-Fact
  declarations, full traceability for F-A1 sampling, explanation
  visibility (N-13) and the P-I4 detective.
- **A severe problem whose harm category is attested by only one source
  cannot reach `SEVERE`** (the second source may attest the problem, not
  the harm). Accepted as the conservative reading of Example 1:
  severity needs the harm itself evidenced by two strong independent
  sources.
- **Boundary disputes** between adjacent criteria are B-37's accepted
  trade-off, minimised by three bands and observable criteria.
- **Fixture migration breadth** at implementation time: every free-text
  severity/frequency fixture changes type under R3 — mechanical, but the
  largest regression surface.
- **The evidence-activation edge case** (corroboration rising without a
  new Fact, e.g. previously non-ACTIVE Evidence becoming ACTIVE beneath
  immutable Facts) is still refused under R5 condition 3; the inferer
  reformulates with an added Fact.
- **Below-ceiling ratings are never raised and never flagged**: the
  P-I4 extension must not treat under-assertion as a violation.

## Known Tensions

- M-12's population-scales remainder stays open and will need its own
  decision record before P5 sizing work.
- Declaration fidelity rests on the same unresolved foundation as M-67
  (structure cannot detect falsehood); F-A1 sampling measures, it does
  not eliminate.
- P5's frequency-inflation narrative (PT-V2) will consume these bands;
  three ordinal values are ratified as sufficient, and any future
  request for finer granularity must reopen via Revisit Conditions.
- B-37's suggestion that M-22 be "co-decided" is resolved by backlog
  sequencing (`T04.1.4` before `T04.1.5`); no dependency is taken on
  dedup semantics.

## Revisit Conditions

- P5 scoring demonstrably requires the reversible/irreversible severity
  split (a four-band scale would then be proposed as a superseding
  record — inconvenience is not grounds).
- T02.1.3 independence grouping lands and materially changes attestation
  semantics (the ≥2-key floor is expected to tighten automatically; only
  a semantic break justifies reopening).
- F-A1 audit evidence shows systematic declaration infidelity that
  structural checks could deterministically catch without NLP.
- A ratified population-scale decision (the M-12 remainder) is taken.
- Empirical O2-style evidence that three bands fail to distinguish
  problems in a way P5 scoring measurably depends on.

## Ratification

Ratified by the Project Owner on 2026-09-14 as the six approved
decisions WD-1–WD-6, drafted with options and evaluation in
`platform/validation/T04.1.4-specification.md` (Rev. 2). The ratification
act follows the F-A1/F-C1/F-A2 mechanism exactly: Status set to
`RATIFIED`, Date decided set, this record created in `docs/decisions/`
with the root `decisions/` symlink, the annotation-layer entry appended
at `RATIFICATION-ANNOTATIONS.md` §15, and the marker register updated to
record M-12's **partial** closure (§3 Partially Closed Markers; §1
counts; the §4 open row narrowed to the population-scales remainder; the
§5 forbidden-closure row annotated). No frozen document was rewritten.
Ratification changes no code and creates no tests; **T04.1.4
implementation has not started** and awaits explicit instruction under
the specification's §9–§13 constraints. M-12 remains open for population
scales; M-19, M-20, M-21, M-22, M-67 and all other markers are
unchanged.
