# Architecture Review Board — M-16 (Source Taxonomy, Eligibility, Trust)

**Convened for:** disposition of M-16 and the status of `T02.1.1`
**Method:** all prior reports treated as untrusted; every claim re-verified
against primary ratified sources.
**Date:** 2026-08-04
**Authority limit:** this board may **prepare** a draft. Under
`AGENT-PLAYBOOK` **F6** ("Self-approving an escalation — 🔺 tasks require
explicit human sign-off. Always.") it **may not ratify**. Nothing here is
ratified.

---

## FINAL RECOMMENDATION

> ### C — SPLIT M-16, combined with E for the residual.
>
> Split M-16 into **M-16a** (taxonomy + eligibility) and **M-16b** (trust
> model). Neither is ratified by this board. **M-16b is ratifiable now** on
> the evidence available; **M-16a is not** — it remains underdetermined and
> requires human input that no amount of analysis can supply.
> `T02.1.1` therefore **remains blocked on M-16a** (recommendation E for that
> portion).

Rationale for the combined form: a single verdict would be dishonest. The
board found the two halves have **different evidentiary status** — one is
underdetermined, the other is not.

---

## 1. Verification of every prior claim

Eight architectural claims re-tested against primary sources. Method and
output: `/tmp/arb.py`.

| # | Claim | Status | Reference |
|---|---|---|---|
| 1 | M-16 is open; no decision closes it | **VERIFIED** | v2 §13 L1785 present; `Closes` scan of 37 records → none |
| 2 | No source-type member appears in normative (unfenced) text | **VERIFIED** | fence-stripped scan of IOM + v2 → zero members |
| 3 | S-02 declares inputs exhaustive and omits source trust | **VERIFIED** | S-02 "**No other input.**"; trust absent from the five |
| 4 | S-02 input 2 concerns type *count*, not source *quality* | **VERIFIED** | "Number of distinct source *types* represented"; P3 is cardinality |
| 5 | IOM §3.1 states `evidential_support` **reflects source reliability** | **VERIFIED** | IOM L552 |
| 6 | Decision records take precedence over the IOM | **VERIFIED** | RATIFICATION-ANNOTATIONS §1: "1. Decision records 2. annotation layer 3. IOM 4. PKP v2" |
| 7 | Partial/joint marker closure is an established pattern | **VERIFIED** | S-05 "Closes \| M-67 (partially)"; R-08 "Closes \| C-04 (jointly with AD-05)" |
| 8 | M-16 is an intentional **merge** of two markers | **VERIFIED** | crosswalk §5: "M-16 \| IOM MISSING-18 (taxonomy) **+** OQ-28 (source trust)" |

**No prior claim was CONTRADICTED.** Two were incomplete — see §3.

---

## 2. Is the underdetermination proof valid?

**VERIFIED — the proof holds**, and the board reproduced it independently.

- **Is the taxonomy mathematically underdetermined?** **Yes.** Every ratified
  constraint (N-03 coverage, S-02 input 2, S-05 stratification, N-16 Tier 2)
  uses source types only to *count* or *partition*. Each is evaluable for any
  `(M, c)` with `|M| ≥ 1`. Witnesses `{EXTERNAL}`, `{HUMAN, MACHINE}`,
  `{A,B,C,D}` all satisfy every constraint and are pairwise non-isomorphic.
- **Does any ratified document uniquely determine it?** **No.** Zero
  enumerating statements; the sole literal `customer_review_corpus` is at IOM
  L592 inside a `#### Example` code fence.
- **Can it be derived indirectly?** **No.** `tags` excluded (IOM L281:
  "must never carry meaning any engine depends on"); `acquisition_method` /
  `access_conditions` / `capture_fidelity` are free text with one example
  each; independence grouping is type-free (N-16, S-04).
- **Hidden authority?** **None.** No ratified statement assigns who classifies
  a source.
- **Does any wording already close M-16?** **No.** B-33 recommends Option 4,
  but `PKP_PreP1_Blocker_Resolution.md` header states: "**No decision herein
  is ratified.**"

**One correction to the proof's framing.** The investigation reported the
`{EXTERNAL}` witness as making S-02's P3 "vacuous", implying a defect in the
constraint set. The board's reading is narrower: P3 remains *well-formed*
under `|M| = 1` (it is vacuously true, not violated). This strengthens rather
than weakens the proof — the constraint set does not even *exclude* the
degenerate model.

---

## 3. Does S-02 truly prevent trust from affecting `evidential_support`?

**YES — VERIFIED, but the prior reports missed a latent conflict.**

S-02's input list is closed by the words "**No other input.**" Source trust is
not among the five. Adding it requires **superseding S-02**.

**Newly identified conflict (not in any prior report):**

> **IOM §3.1 L552:** "`evidential_support` **reflects source reliability**
> (OPEN QUESTION-28 unresolved — absent a trust model, all sources weigh
> equally, a strong unstated assumption)."

On a plain reading this is inconsistent with S-02, which excludes reliability.
Resolution, by the ratified precedence order:

1. **Decision records** ← S-02
2. Annotation layer
3. **IOM** ← the conflicting sentence
4. PKP v2

**S-02 governs.** Further, the IOM sentence is self-hedging — it flags OQ-28
as *unresolved* and labels equal weighting an *assumption*. It expresses
**intent**, not contract. So this is a **tension, not a contradiction**: the
IOM's aspiration is unrealisable until M-16 closes, and S-02 states what holds
meanwhile.

**Consequence:** closing M-16 does **not**, by itself, license trust-weighted
scoring. That is a separate S-02 supersession. The board records this because
a ratifier could easily assume otherwise.

---

## 4. Is M-16 one marker or several?

**It should be split. VERIFIED as a merge, and the merge is now load-bearing
in a harmful way.**

The crosswalk (§5) records M-16 as `MISSING-18 (taxonomy) + OQ-28 (source
trust)`, justified as "source trust is an attribute of the source model, not a
separable gap". That justification was reasonable for *cataloguing*. It is
harmful for *execution*, because the two halves now have **different
evidentiary status**:

| Half | Status | Evidence |
|---|---|---|
| Taxonomy + eligibility | **Underdetermined** — ≥3 valid models | §2 |
| Trust model | **Determinable** — representation constrained by existing ratified material | §5 |

Bundling forces the determinable half to wait on the underdetermined half.

### Proposed split (draft only)

| ID | Substance | Owner | Depends on | Blocks |
|---|---|---|---|---|
| **M-16a** | Source-type taxonomy + per-type eligibility | Platform Architecture | — (needs human input) | `T02.1.1`AC1, `T02.1.4`, `T02.3.1`, `T05.1.4` |
| **M-16b** | Source trust model (representation, scale, default) | Platform Architecture | M-16a for *per-type* trust only | `T02.1.1`AC2 |

**Migration strategy:** amend `marker-crosswalk.md` §5 to record the split,
retaining M-16 as the historical parent (the crosswalk already handles
one-to-many mappings). No frozen document is rewritten — **F5** respected.

**Honest caveat on value.** The board tested the split's benefit
counterfactually: if the independence half (`T02.1.3`) were unblocked,
**only 2 of 94 blocked tasks are freed** (`T02.1.3`, `T02.1.4`). The taxonomy
is the true bottleneck. **The split is a correctness improvement, not a
throughput one**, and should not be sold as unblocking Phase 2.

---

## 5. Minimum decision required to unblock Phase 2

The board can specify the *form* completely. It cannot supply one input.

**M-16b (draft-ready).** Every element is constrained by existing ratified
material:
- Trust recorded per source, keyed on `source_identifier` (IOM §3.1: "sufficient
  to assess independence").
- Immutable + versioned (**R-01**, **N-04**), matching `ConfigurationStore`.
- Recorded on the existing optional `source_reliability` (IOM §3.1) — no
  frozen-contract change.
- **Does not feed `evidential_support`** (S-02 untouched).
- Unrated ⇒ absent, never defaulted (IOM §3.1 calls equal weighting an
  *assumption*, not a policy).

**M-16a (NOT draft-ready).** Requires exactly four inputs, none derivable:

| # | Required | Why no analysis can supply it |
|---|---|---|
| 1 | Member set `M` | §2: ≥3 models satisfy all constraints |
| 2 | Cardinality `\|M\|` | never stated |
| 3 | Classifier `c` | no membership predicate exists |
| 4 | Authority applying `c` | no engine assigned |

Any choice is an architectural decision (**F2**) closing a marker by
implementation (**F3**).

**Therefore the board produces no Decision Draft for M-16a.** Producing one
would require inventing `M` — the precise act the mandate forbids.

---

## 6. Impact analysis

**Phases.** All of P2–P9. `T03.1.1` (P3 entry) blocked at depth 4.

**Tasks.** 94 transitively blocked; 15 reference source taxonomy/trust/
diversity directly. Immediate: `T02.1.1`, `T02.1.2`, `T02.1.3`, `T02.1.4`,
`T02.3.1`; later `T05.1.4`, `T05.1.5`, `T08.2.1`, `T08.3.2`.

**Modules.** `oip/source.py` only (the sole P2 artefact). Phase 1's 28 modules
untouched — `cascade.py` `b603ce9e…`, `integrity.py` `42f1a950…`. **No Phase 1
reopening is entailed by either sub-marker.**

**Acceptance criteria.** `T02.1.1` AC1 (blocked by M-16a), AC2 (satisfiable
under M-16b), AC3 (blocked by M-02/M-43, out of M-16's scope entirely).
`T02.3.1` AC1 ("every defined source type") unsatisfiable while `M` is empty.

**Architectural decisions affected.** Directly dependent: **N-03, S-02, S-05,
N-16**. Transitively: **S-01, S-04**. Seven of thirty-seven ratified records
rest on M-16 — a figure the board considers the single most important number
in this review.

**Superseded decisions.** **NONE** under the split as scoped. M-16b supersedes
nothing because it does not touch scoring. Had trust been made an S-02 input,
S-02 would require supersession — which is why the board scopes it out.

---

## 7. Contradictions introduced

The board searched for contradictions the split would create:

| Check | Result |
|---|---|
| Does M-16b contradict S-02? | **No** — recording ≠ scoring; inputs untouched |
| Does it contradict IOM §3.1? | **No** — uses the existing optional attribute at its existing range |
| Does it breach CI-1 (N-07)? | **No**, *conditional* — only if the registry is held outside configuration **and** non-scoring. Both hold. Flagged as Q3 below. |
| Does it add a tenth object (F8)? | **No** — a source record is infrastructure state, carrying no lineage |
| Does it reopen Phase 1? | **No** |
| Does splitting breach F5 (frozen docs)? | **No** — crosswalk is a governance artefact, not frozen |

---

## 8. Unresolved questions — the board STOPS here

Per the mandate, remaining ambiguity is listed, not resolved.

| # | Question | Blocks |
|---|---|---|
| **Q1** | What are the members of `M`? | M-16a, AC1 |
| **Q2** | Which engine holds classification authority — Research, or acquisition-time assignment? | M-16a |
| **Q3** | Is the source registry configuration under N-07? If yes, CI-1 forbids it "participating in reasoning, scoring, pattern detection, or lineage" — is non-scoring trust compatible with residing there? | M-16b siting |
| **Q4** | Is per-type eligibility distinct from M-18 licensing, or do they collapse? | M-16a / `T02.1.2` boundary |
| **Q5** | Should the IOM §3.1 "reflects source reliability" sentence be annotated as superseded by S-02? | corpus coherence |
| **Q6** | Does closing M-16 require a *future* S-02 supersession to realise IOM's intent, and should that be recorded as a known tension now? | S-02 |
| **Q7** | Is source trust a P8 learning target? (**M-02/M-43** — outside M-16) | AC3 |

**Q5 is new and independent of T02.1.1.** The board recommends it be triaged
regardless of the M-16 outcome, because the corpus currently contains an
unannotated tension between a ratified decision and a frozen document.

---

## 9. Risk assessment

| Risk | Severity | Basis |
|---|---|---|
| Ratifying an arbitrary `M` to unblock delivery | **High** | v2 §9 calls M-16 "the highest-severity omission in the engine set"; a wrong taxonomy silently distorts S-02 P3 diversity weighting and N-03 coverage forever |
| Splitting is mistaken for unblocking | **Medium** | Only 2 of 94 tasks freed (§4) |
| Assuming M-16 closure permits trust-weighted scoring | **Medium** | Requires superseding S-02 (§3) — easy to overlook |
| Leaving Q5 unannotated | **Low–Medium** | A ratified decision and a frozen document disagree in the corpus |
| Indefinite P2 blockage | **High** | 94 tasks, all remaining phases |

**Board's judgement on the central trade-off:** the cost of a wrong taxonomy is
permanent and silent; the cost of delay is visible and recoverable. That
asymmetry argues against expedient ratification — but the board notes the
decision is **not** a technical one and belongs to the human owner.

---

## 10. Deliverables index

| Deliverable | Location |
|---|---|
| Architecture Review Report | this document |
| Decision Draft | **§5 — M-16b form specified; M-16a not draftable** (inventing `M` is forbidden) |
| Risk Assessment | §9 |
| Dependency Analysis | §6 |
| Required Specification Changes | §4 (crosswalk split), §8 Q5 (IOM annotation) |
| Final Recommendation | **C + E** (see head of document) |

**No production code written. No tests modified. No documentation modified
except this proposal-layer document. Nothing ratified.**
