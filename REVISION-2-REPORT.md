# P2 Decision Set — Revision 2 Report

**Scope:** amendments to DRAFT N-20…N-23 resolving ARB findings C-1…C-5.
**Date:** 2026-08-04
**Status:** all four drafts remain `DRAFT`. Nothing ratified (Playbook **F6**).

---

## Section 1 — Amendments Made

Seven edits across four drafts. Every edit is additive or a token rename; no
clause was deleted, and no decision's substance was redesigned.

### A1 · N-20 §5.2 — refusal made reportable *(C-5)*
**Changed:** final paragraph of §5.2.
Replaced *"Both gates must pass"* with a reference to the new sequence, and
added a paragraph creating the **duty** to record an untypable refusal as an
*out-of-frame refusal*, citing Article X.
**Minimality:** creates the obligation only; the mechanism lives in N-22, so
the duty is stated once and implemented once.

### A2 · N-20 §5.2.1 — deterministic gate sequence *(C-4)* — **NEW SUBSECTION**
**Added:** a totally ordered three-gate table (1 Scope → 2 Typability →
3 Rights), each with its refusal reason; a corpus-grounded ordering rationale;
and a determinism proof.
**Minimality:** the sequence is recorded in **exactly one** record. N-20 was
chosen because it owns gate 2, sits topologically first among the gate-owning
drafts, and is a dependency of N-22 — so every consumer already reads it.

### A3 · N-21 §5.4 — ordering adopted, not duplicated *(C-4)*
**Changed:** the *"Both gates must pass"* paragraph.
Now states that gates are *substantively* independent but *procedurally*
ordered, that rights is **gate 3 of 3**, and that the sequence is *"adopted,
not originated, here… so no second copy exists to drift."*
**Minimality:** a cross-reference, not a restatement — prevents divergence.

### A4 · N-22 header + Implementability Warning — dependency re-pointed *(C-3)*
**Changed:** `Depends on` now reads **N-20** (plus N-21, N-23 for the reason
vocabulary) instead of *"M-16 (OPEN)"*; the warning now says N-22
*"must never be ratified before N-20."*
**Minimality:** two lines; the inertness caveat is preserved, now expressed
against a decision rather than a gap.

### A5 · N-22 §5.1 — two definitions added *(C-5)*
**Changed:** definitions table.
Added **out-of-frame refusal**; extended **declared-complete** to require that
every out-of-frame refusal is recorded. Frame now cites N-20 §5.1.
**Minimality:** `coverage`, `gaps` and `represented member` are unchanged.

### A6 · N-22 §5.2.1 — out-of-frame register *(C-5)* — **NEW SUBSECTION**
**Added:** `out_of_frame` count, held **separately** from coverage; a
well-formedness rule that a report showing `coverage = 1.0` with
`out_of_frame > 0` is *not* a claim of complete coverage; and a note that
persistent non-zero `out_of_frame` is grounds to revisit N-20's taxonomy.
**Minimality:** the coverage formula is untouched. This adds an *accompanying
count*, not a new measure — explicitly honouring the "do not redesign the
coverage model" constraint.

### A7 · N-22 §5.4 — vocabulary ownership *(C-1)*
**Added:** an ownership paragraph — all five reason values are *"defined by
this record and owned by it"*; other records produce the conditions but do not
define the vocabulary. States that `UNTYPABLE_CHANNEL` is **deliberately not**
a gap reason (it belongs to the register, §5.2.1). Two reason descriptions
re-pointed from marker IDs to gate numbers.
**Minimality:** no value added or removed from the gap vocabulary.

### A8 · N-23 §5.6 — directive states renamed *(C-2)*
**Changed:** `PROPOSED` → **`RAISED`**, `ACTIVE` → **`IN_EFFECT`**; added a
*token disjointness* paragraph noting that *"disclaiming an overlap in prose is
weaker than not creating one."*
**Propagated** to the four other occurrences (§5.1 definition, §5.2 ×3).
**Minimality:** a rename. R-2's semantics, membership and text are untouched;
the other three directive states were already disjoint and were left alone.

---

## Section 2 — Finding → Amendment Mapping

| Finding | Severity | Amendments | Resolution |
|---|---|---|---|
| **C-4** gate order | HIGH | A1, A2, A3 | Total order + halt-on-first-refusal + proof; recorded once, referenced once |
| **C-5** coverage paradox | HIGH | A1, A5, A6 | Out-of-frame register; report ill-formed unless `out_of_frame` accompanies `coverage` |
| **C-3** dangling dependency | LOW | A4 | Depends on N-20, not on open M-16 |
| **C-2** token overload | LOW | A8 | `RAISED` / `IN_EFFECT` — disjoint from all seven R-2 states |
| **C-1** `OUT_OF_SCOPE` owner | LOW | A7 | N-22 owns the gap vocabulary; producers named but non-defining |

### C-4 determinism proof (as recorded in N-20 §5.2.1)

The gates form a finite, totally ordered list evaluated in index order,
returning on the first refusal. For any source, the outcome is the
**lowest-indexed failing gate** — regardless of how many gates would fail if
evaluated independently. If none refuses, acquisition proceeds. The outcome is
a total function of (source, gate states), so two conforming implementations
cannot disagree. Consistent with N-04 reproducibility.

**Worked counterexample from the ARB review, now resolved.** A source that is
out-of-scope **and** untypable **and** prohibited previously produced an
indeterminate reason. It now yields exactly `OUT_OF_SCOPE` (gate 1), and
gates 2–3 are never evaluated.

### C-5 truthfulness proof

Let *S* be any refused source. Either *S* maps to a frame member — then its
refusal is a gap with a reason from §5.4 — or it maps to none, in which case
A1 obliges recording it and A6 counts it in `out_of_frame`. **The two cases are
exhaustive and disjoint**, so no refusal is unrecorded. `coverage = 1.0` can
therefore no longer be reported without an accompanying `out_of_frame` figure.
Article X is satisfied at the N-20↔N-22 seam.

---

## Section 3 — Compatibility With Ratified Decisions

Re-verified after amendment. **No verdict regressed.**

| Decision | Verdict | Evidence after revision |
|---|---|---|
| **S-02** | Compatible | No sixth input. Trust still non-scoring (N-20 §5.3); coverage still not an input (N-22 §6.5); `out_of_frame` feeds nothing |
| **S-04** | Compatible | *"Coverage is a report, not a gate"* retained verbatim; sufficiency untouched |
| **S-05** | Compatible | Stratification by type unaffected by the rename or the register |
| **N-02** | Requires annotation *(pre-existing D-1)* | Unchanged by this revision; no fourth gate created |
| **N-03** | Compatible | Refinement still via N-03's own extension clause (5 citations retained) |
| **N-08** | Compatible | Gate sequence is pre-acquisition in Research; Store still structural-only |
| **N-10** | Compatible | All refusals still route to failure records; `NOT_ATTEMPTED` vs `NO_MATERIAL_FOUND` intact |
| **N-12** | Compatible | Retention rights/policy separation untouched |
| **N-15** | Compatible | *"Supplied, not superseded"* retained |
| **N-17** | Compatible | Gate 1 (scope) matches directive-driven work sets; scheduling untouched |
| **R-2** | **Compatible — annotation no longer required** | A8 removes the token collision. R-2 text, membership and semantics unchanged |
| **R-6** | Compatible | Closed-vocabulary discipline strengthened; no relationship type touched |
| **CI-1** | Compatible | Register and directives remain non-scoring infrastructure state; rights stay on the Evidence object |
| **Art. X** | **Strengthened** | A1/A6 close the seam where coverage could overstate |
| **Art. XI** | Compatible | Precedence unchanged; D-1 still resolved in N-02's favour |

**Supersessions required: NONE.** **Contradictions: NONE.**
**Annotations reduced from 2 to 1** — only the pre-existing N-02/D-1 backlog
annotation remains.

### Mechanical re-verification (16 checks, all PASS)

Gate sequence in exactly one record · halt-on-first-refusal · determinism proof ·
N-21 references without duplicating · out-of-frame register defined ·
well-formedness rule · N-20 creates the duty · coverage formula unchanged ·
dependency re-pointed · directive states disjoint from R-2 (`collisions=none`) ·
ownership assigned · no double definition · **acyclic** (only N-22 has outbound
edges: →20, →21, →23) · no supersessions · all three gate refusals
representable · all four still `DRAFT`.

---

## Section 4 — Remaining Unresolved Questions

Not introduced by this revision; carried forward and **out of scope** for it.

| # | Question | Owner |
|---|---|---|
| 1 | **D-1** — `T02.2.4` AC2 requires a human gate N-02 forecloses. Amend AC2, or create a fourth gate superseding N-02? | Ratifier |
| 2 | Rights authority identity — N-21 §5.1 names none, so N-21 is inert until one exists | Organisational |
| 3 | N-20 §5.1's eight members are chosen, not derived | Ratifier |
| 4 | Trust scoring — would require superseding S-02 | Future record |
| 5 | Learnability (`T02.1.1` AC3) — M-02 / M-43 | P8 |
| 6 | Conduct half of M-18 (robots, rate limits) — "M-18b" | Unscheduled |
| 7 | Whether "compliance" (v2 §14) falls inside M-18 | Ratifier |
| 8 | **D-2** — self-direction has no canonical marker ID | Governance |
| 9 | `source_diversity`: sources or types? (IOM §3.4 vs S-02) — blocks clean PT-V4 | Ratifier |

**Still no marker is fully closed.** Four partial closures remain partial —
this revision fixed interaction defects, not coverage of the markers.

---

## Section 5 — Honest Limitations

- **A2 and A6 add architecture.** A gate *sequence* and an *out-of-frame
  register* did not previously exist. I judged both unavoidable: C-4 is
  unresolvable without an order, and C-5 without a place to record untypable
  refusals. Both are minimal — the sequence only orders gates the drafts
  already had, and the register adds a count beside coverage rather than
  changing it — but they are additions, and a ratifier should see them as
  such rather than as pure clarifications.
- **The gate ordering is justified, not derived.** No ratified text states
  that scope precedes typability precedes rights. My rationale (narrowing from
  cycle → class → instance; scope precedes any attempt) is defensible and
  consistent with N-17, but a ratifier could order gates 1 and 2 differently
  without contradicting the corpus. **What the corpus does now demand is that
  *some* total order be fixed** — that part is not discretionary.
- **`UNTYPABLE_CHANNEL` is a new token.** It was unavoidable: C-4 requires
  every gate to have a distinct refusal reason, and no ratified vocabulary
  contained one. It is deliberately kept out of N-22's gap vocabulary so the
  two vocabularies stay disjoint.
- **A8 is a rename of tokens I myself introduced** in Revision 1, so it costs
  nothing externally — but it is worth noting the original collision existed
  only because I reused familiar names. Disjointness should have been the
  default.
- **I did not re-audit each draft's internal constraint extraction.** This
  revision addressed interactions; the per-draft citations are assumed sound
  as in the ARB review.
- **`out_of_frame` has no consumer.** Like trust in N-20, it is a produced
  figure nothing reads. That is correct under S-02 (coverage is not an input),
  but it means truthfulness depends on a human reading the report.

---

## Success Criteria Assessment

| Criterion | Status |
|---|---|
| No HIGH findings | **Met** — C-4 and C-5 resolved with proofs |
| No architectural ambiguity | **Met** for C-1…C-5; D-1 remains (external, pre-existing) |
| No circular dependency | **Met** — verified acyclic |
| No reporting paradox | **Met** — §5.2.1 truthfulness proof |
| No hidden authority conflict | **Met** — authority matrix unchanged; no cell contested |
| Ratification-ready as a coherent set | **Met, conditional on D-1** — the set is internally coherent; `T02.2.4` AC2 still needs a ratifier decision |

**Revised ratification order:** N-21 → N-20 → *(resolve D-1)* → N-23 → N-22.
N-22 must never precede N-20.

---

**Status: all four drafts remain `DRAFT`. Nothing ratified. No production code,
tests, or ratified documents modified.**
