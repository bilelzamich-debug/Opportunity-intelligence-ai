# F-V4 — Assertion vs Attributed Opinion Classification

> **RATIFIED 2026-09-09.** The annotation-layer entry recording this
> ratification and its binding interpretation is
> `RATIFICATION-ANNOTATIONS.md` §12, mapping this record to IOM §3.2
> (Fact: F-V4, the `attributed_to` attribute row, and the Purpose
> responsibility "Distinguish assertions of fact from attributed
> opinions") and to the PKP v2 Master Reference §3.3 Stage 2 invariant.
> Frozen documents are not rewritten; the annotation layer records the
> binding interpretation.

| Field | Value |
|---|---|
| **ID** | F-V4 |
| **Title** | Assertion vs Attributed Opinion Classification |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-09-09 |
| **Date decided** | 2026-09-09 |
| **Source** | IOM §3.2 (Fact); PKP v2 MR §3.3 Stage 2; S-3; R-5; N-10; T03.1.1 specification; T03.1.5 backlog entry; T03.1.5 final audit |
| **Closes** | — (the two specification gaps recorded by the T03.1.5 final audit) |
| **Backlog task** | `T03.1.5` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

### R1 — Classification rule (the biconditional)

For every claim entering the platform through extraction, `claim_type`
and `attributed_to` are **mutually determining**:

> **`claim_type = ATTRIBUTED_OPINION` ⟺ `attributed_to` is a non-empty
> string after whitespace stripping.**

Equivalently:

- If `attributed_to` names an originator (non-empty after stripping):
  `claim_type` MUST be `ATTRIBUTED_OPINION`.
- If `attributed_to` is absent, empty, or whitespace-only: `claim_type`
  MUST be `ASSERTION`.

The presence of a valid `attributed_to` **operationally defines** the
claim as an `ATTRIBUTED_OPINION`. No additional classification signal
exists or is required.

### R2 — Invalid combination rule

`claim_type = ASSERTION` together with a non-empty `attributed_to` is a
**contradictory request**. The behavior is **REJECT**: refuse the
extraction at the extraction boundary with a recorded failure (N-10) —
stage `INVALID_REQUEST`, reason `CLAIM_TYPE_CONFLICT` — before any
Evidence-dependent gate, decomposition, Fact construction, or write.
No Fact is created; no anchor is registered; no partial state survives.

Never reclassify silently (that would override the caller's epistemic
statement), never allow (the combination has no defined meaning in the
model), never drop the attribution (silent information loss).

### R3 — Attribution requirements

| State of `attributed_to` | Classification | Treatment |
|---|---|---|
| Absent (`None` / omitted) | ASSERTION | Valid for `ASSERTION`; an `ATTRIBUTED_OPINION` request without it is rejected at request construction (F-V4, existing) |
| Empty string (`""`) | ASSERTION | Treated as absent |
| Whitespace-only | ASSERTION | Treated as absent — whitespace names no speaker (the F-V4 non-emptiness convention) |
| Non-empty string after stripping | ATTRIBUTED_OPINION | Valid attribution; carried byte-identical into the Fact |
| Any non-string, non-`None` value | — | Rejected at request construction (outside the declared `str \| None` contract) |

**Speaker semantics.** A valid attribution identifies the speaker — the
named/identified source, person, organization, publication or other
identifiable originator to whom the proposition is attributed
(IOM: *"`attributed_to` — Speaker, for `ATTRIBUTED_OPINION`"*).
Structural validity (non-empty string) is checkable; whether the string
genuinely identifies an originator is the extractor's responsibility and
is **not** mechanically verifiable — consistent with the platform's
structural-checks philosophy (S-5 Layer 1 checks structure, not meaning;
M-67 remains open). Attribution is required for **every**
`ATTRIBUTED_OPINION` (F-V4, unchanged).

Attribution is **not** evidential provenance. Where the claim's
supporting material came from is carried by the Evidence attachment,
`derives_from` lineage and the source registry. `attributed_to` carries
*whose assertion the proposition is* when that asserter is not the
platform itself (MR, Fact contract: *"attribution (whose assertion it
is)"*).

### R4 — Canonical invariants

1. **INV-1 (existing F-V4, forward):** `claim_type =
   ATTRIBUTED_OPINION` ⇒ `attributed_to` is a non-empty string.
2. **INV-2 (ratified converse):** `attributed_to` is a non-empty string
   ⇒ `claim_type = ATTRIBUTED_OPINION`. Together with INV-1, the
   biconditional of R1.
3. **INV-3 (closed taxonomy):** `claim_type` is a member of the
   two-value closed taxonomy `ASSERTION | ATTRIBUTED_OPINION`. No third
   type, no `None`, no stringly-typed value, no silent default.
4. **INV-4 (merge stability):** a canonical merge never alters
   `claim_type` or `attributed_to`; the merged version carries the
   canonical's classification exactly and satisfies INV-1..INV-3.
   (Holds mechanically today: `with_attachment` inherits the canonical
   payload. No code change required.)

**Enforcement points.** INV-1: request construction, `Fact`
construction, and store acceptance (`fv4_claim_type_declared`) — all
layered today. INV-2: the extraction-boundary classification gate —
authoritative for all Facts because the Fact Extraction engine holds
sole create authority over Facts (V7 / IOM S 2.5), so no platform
Fact can bypass it. Optional future hardening: add INV-2 to `fact.py`'s
structural F-V4 (non-blocking; see Known Tensions).

### R5 — Extraction contract

`ExtractionRequest` and `extract()` MUST guarantee:

- **Caller-provided classification:** `claim_type` remains REQUIRED and
  must be a `ClaimType` member; `attributed_to` remains `str | None`.
  The public request contract is unchanged.
- **Derived classification:** the engine derives the classification as
  a pure, checkable function of the structured request
  (`classify_claim_type(attributed_to)` per R1) — no interpretation of
  wording (MR: *"Extraction does not interpret. Meaning-making belongs
  to the Problem stage"*), no model, no network, no heuristics.
- **Validation:** request-level F-V4 structural validation (unchanged)
  runs at construction; the classification gate runs at the extraction
  boundary, before Evidence resolution and every Evidence-dependent
  gate — the refusal is therefore a function of the request alone.
- **Contradiction handling:** stated type ≠ derived type ⇒ recorded
  refusal per R2 (N-10; not-attempted: request validity, no content
  judgement).
- **Fail-closed behavior:** no silent defaulting, no silent
  reclassification, no silent attribution drop. A Fact exists only
  after every gate passes; a refused extraction leaves no Fact, no
  anchor, no partial trace.
- **Guarantee on acceptance:** every accepted Fact carries a populated
  `claim_type` from the closed taxonomy equal to the derived
  classification; an `ATTRIBUTED_OPINION` carries its attribution
  byte-identical; an `ASSERTION` carries none.

### R6 — Merge interaction

F-V4 as ratified introduces **no new requirement on T03.1.4** and no
code change. Two statements:

1. **Invariant (binding, holds today):** INV-4 above — merges preserve
   the canonical's `claim_type`/`attributed_to`.
2. **Recorded future correction (separate issue, not fixed here):**
   S-3 equivalence is judged on the four claim-structure conditions
   (subject, predicate, qualifier, value) and is therefore
   **type-blind**: an `ATTRIBUTED_OPINION` extraction whose claim is
   structurally EQUIVALENT to an `ASSERTION` canonical merges into it,
   and the merged version presents the opinion-attesting extraction as
   support for an assertion — the "Opinion recorded as assertion" risk
   (IOM risk table) entering through the merge path. This behavior
   pre-dates T03.1.5 (verified identical at the T03.1.4 base) and is
   **out of scope for F-V4**. Recorded as follow-up
   **T03.1.4-F1 — claim-type-aware canonical merging**: claim types
   that differ must not merge; the conservative S-3 policy (under-merge
   preferred; over-merge destroys information irreversibly under I2)
   indicates the EQUIVALENT-but-different-type case should be treated
   like UNCERTAIN: a separate Fact plus a `DUPLICATES` link.
   **T03.1.4-F1 will require its own decision record before
   implementation**: it changes the currently ratified S-3 merge
   conditions (the four-condition EQUIVALENT ⇒ merge rule), and
   RATIFIED records are changed only by a superseding record, never by
   editing in place (decision-record template, rule 5).

## Context

T03.1.5 (`98741f270e178a1f9a782c3a3dae684b6443543d`) implemented the
classification capability at the extraction boundary. The final audit
verdict was **APPROVED WITH SPECIFICATION RISK** for exactly two
findings, both absence-of-explicit-statement gaps (no conflicting
evidence exists):

1. Every ratified statement runs opinion ⇒ attribution; the implemented
   inference attribution ⇒ opinion (R1's converse) was nowhere stated.
2. No document decides the `ASSERTION + attributed_to` combination.

This record closes both gaps by ratifying the semantics the
architecture already implies.

## Alternatives Considered

**Issue 1 — classification signal.**

- **Option A — caller judgement only** (pre-T03.1.5 state): *Rejected.*
  The backlog deliverable for T03.1.5 is "Claim type classification",
  and the T03.1.1 specification states "automated classification is
  that task's deliverable". Recording the caller's label without a
  platform-side classification leaves the deliverable unimplemented and
  the audit risk unresolved.
- **Option B — classify from wording** ("believes", "may", hedges):
  *Rejected.* Judgement, not check — violates the S-3 principle that
  platform decisions must be "checkable, not opinion", and MR's
  "Extraction does not interpret". Also non-reproducible and
  language-dependent.
- **Option C — a new structured signal** (e.g. an `is_opinion` flag):
  *Rejected.* Architectural invention. No repository evidence supports
  a third signal; under the model `attributed_to` already carries
  exactly the needed information, and a parallel flag could contradict
  it.
- **Option D — `attributed_to` presence (chosen):** the only
  structured, deterministic, in-contract carrier of attribution; its
  documented meaning is scoped to opinions.

**Issue 2 — `ASSERTION + attributed_to`.**

- **ALLOW:** *Rejected.* The model defines no meaning for a speaker on
  an assertion (IOM scopes `attributed_to` to `ATTRIBUTED_OPINION`), and
  evidential provenance is already fully carried by attachments,
  lineage and the source registry. Allowing it would either introduce
  an undefined state or duplicate provenance machinery outside the
  object model.
- **RECLASSIFY:** *Rejected.* Silently overrides the caller's epistemic
  statement ("the platform asserts X" becomes "someone else says X") —
  meaning alteration, the "Context stripping" failure class; masks
  caller error instead of surfacing it, against N-10's philosophy;
  silent inference is anti-principle in this architecture.
- **REJECT (chosen):** the only option consistent with closed
  semantics, meaning preservation, the fail-closed discipline used by
  every other extraction gate, and N-10 failure recording.

## Rationale

The biconditional is not a new rule; it is the closure of rules the
repository already states, read together:

- The Fact's responsibility is to "distinguish assertions of fact from
  attributed opinions" (IOM §3.2, Purpose r3).
- `attributed_to` is defined as "Speaker, **for** `ATTRIBUTED_OPINION`"
  (IOM §3.2) — the field has no documented meaning outside opinions.
- "Opinions, if extracted, must be **marked as attributed statements**
  rather than as assertions of truth" (MR §3.3 Stage 2). An attributed
  statement is marked *by* its speaker; a claim that names a speaker
  **is** an attributed statement, and `ATTRIBUTED_OPINION` is the only
  taxonomy member that can carry one.
- The risk table names the dangerous direction and only that
  direction: "Opinion recorded as assertion … Problems inferred from
  opinion presented as observation" (IOM §3.2; MR failure modes;
  `ClaimType` docstring). Binding attribution to opinion-hood (INV-2)
  is what closes that direction.
- The error taxonomy already anticipates the inconsistency:
  `ClaimTypeError` — "claim_type inconsistent with the attribution".
- MR's Fact contract: a Fact must carry "attribution (whose assertion
  it is)" — for an assertion the asserter is the platform (recorded as
  `produced_by_engine`); a *named* asserter is precisely the opinion
  case.

Illustrative boundary the rule draws: "Revenue grew 10%, per the CFO's
report" is an ASSERTION — the CFO's report is the Evidence (attachment,
lineage), not a speaker. "The CEO believes revenue will grow" is an
ATTRIBUTED_OPINION — the proposition is the CEO's, and
`attributed_to = "the CEO"` marks it. Uncertainty, hedging, low
confidence, controversiality and vendor/publication source status are
never attribution.

## What It Binds

- **Fact Extraction engine** (`oip/extraction.py`): the classification
  gate, R1–R3, R5. (Implemented as of T03.1.5 `98741f2`; ratification
  requires **no implementation change**.)
- **`ExtractionRequest` contract:** unchanged fields; the biconditional
  is a consistency requirement evaluated at `extract()`.
- **Fact model (interpretation only):** F-V4 reads as the biconditional
  for platform-created Facts; INV-2's enforcement point is the create
  authority (V7), not `fact.py`.
- **T03.1.4 merging:** INV-4 binding today; T03.1.4-F1 recorded as a
  future correction.
- **On ratification:** an annotation row in `RATIFICATION-ANNOTATIONS.md`
  mapping this record to IOM §3.2 (F-V4; `attributed_to` attribute) and
  MR §3.3 Stage 2 invariants.

## Consequences Accepted

- **Checkable, not omniscient.** A caller can still suppress a speaker
  and assert an opinion as an assertion; the classifier does not
  interpret text and cannot catch that. The residual exposure is the
  already-recorded "Opinion recorded as assertion" risk (Medium);
  detection belongs to fidelity sampling (T03.2.2, M-67), not to
  structure — the same boundary S-5 Layer 1 draws between fabricated
  locations and paraphrase drift.
- **`ASSERTION + named speaker` is unconstructable via extraction** and
  must be restated by the caller; extractors that used `attributed_to`
  as informal provenance must move that information to Evidence or
  lineage, where the model already carries it.
- The `Fact` dataclass continues to accept a direct-construction
  `ASSERTION` carrying `attributed_to` (INV-2 is enforced at the
  create-authority boundary, not in `fact.py`); see Known Tensions.

## Known Tensions

1. **T03.1.4-F1 (recorded, not fixed):** type-blind S-3 equivalence
   permits cross-type merges (R6). Pre-existing; correcting it changes
   T03.1.4 merge semantics and is deliberately out of scope here.
   Before implementation it requires its own decision record, because
   it supersedes the ratified S-3 merge conditions (see R6).
2. **INV-2 enforcement location:** structural hardening of `fact.py`
   F-V4 to check the converse is a possible follow-up; unnecessary
   while V7 create authority holds, but worth revisiting if Facts ever
   gain a second creation path.

## Revisit Conditions

- A third claim type, or a ratified notion of attributed *assertions*
  distinct from opinions, reopens R1.
- T03.1.4-F1 landing (claim-type-aware merging) resolves tension 1 and
  tightens R6.
- Systematic speaker-suppression ("opinion laundering") observed in
  extraction corpora reopens the *detection* question (sampling), not
  the biconditional.
- Inconvenience is not grounds for reopening.

## Relationship to T03.1.5

T03.1.5 (`98741f270e178a1f9a782c3a3dae684b6443543d`) implemented
exactly R1–R5: `classify_claim_type()`, the `CLAIM_TYPE_CONFLICT`
refusal, the request-level type validation of `attributed_to`, and the
tests proving both ACs. If this record is ratified, the T03.1.5 audit
status upgrades from APPROVED WITH SPECIFICATION RISK to fully
specified — no implementation change is required. The audit's
specification findings 1 and 2 map to R1 and R2 respectively.

## Relationship to T03.1.4

R6 states the merge stability invariant (INV-4) that T03.1.4 already
satisfies mechanically, and records T03.1.4-F1 as the future
claim-type-aware merging correction. T03.1.4 code and semantics are
untouched by this record.
