# Underdetermination Proofs

Formal proofs that the ratified corpus does **not** determine certain
artefacts. Each proof is why a marker could not be closed by analysis and
required a human decision.

**Definition.** A specification *determines* X iff **exactly one** X satisfies
it.

---

## Proof 1 — M-16 Source Taxonomy

**Formalisation.** A taxonomy is a pair `T = (M, c)`: a finite member set `M`
and a total classifier `c : Source → M`.

**Every ratified constraint mentioning source types:**

| Constraint | Requires | Needs member identity? |
|---|---|---|
| N-3 coverage | `\|{c(s) : s acquired}\| / \|M\|` | No |
| S-2 input 2 | `\|{c(s) : s ∈ lineage}\|` | No |
| S-5 stratification | a partition of Facts by `c(source)` | No |
| N-16 Tier 2 | the multiset `{c(s)}` | No |

Every constraint uses source types in exactly one way: to **count** or
**partition**. Therefore every constraint is satisfied by **any** `(M, c)` with
`|M| ≥ 1` and `c` total.

**Witnesses** — all constraint-satisfying, pairwise non-isomorphic:

| | `M` | Interpretation |
|---|---|---|
| `T₁` | `{EXTERNAL}` | all sources one type |
| `T₂` | `{HUMAN_AUTHORED, MACHINE_GENERATED}` | partition by authorship |
| `T₃` | `{A, B, C, D}` | any 4-way partition |

**Discrimination test.** Searched for any ratified predicate separating them —
`at least n source types`, `minimum of n`, `exactly n`, `source types must
include`, `source types shall`. Result: **NONE**.

**∴ ≥3 distinct models satisfy the ratified theory. The architecture does not
determine the taxonomy. ∎**

**Corollary.** `T₁ = {EXTERNAL}` is constraint-satisfying yet renders S-2
property P3 vacuous — diversity constant at 1. A ratified property goes inert
under a constraint-satisfying model, independently confirming the constraints
do not pin the intended one.

### Supporting mechanical evidence

| Test | Result |
|---|---|
| Does the corpus enumerate source types as it does its 5 other closed vocabularies? | **False** — the only one it does not |
| Every literal ever appearing as a `source_type` value | `['customer_review_corpus']` — **exactly one** |
| Its context | IOM line 592, heading `#### Example`, **inside a fenced code block** |
| Ratified decisions constraining `source_type`'s value | **NONE** |
| Statements giving trust a scale, range or default | **NONE** |
| Ratified classification authority | **NONE** |

---

## Proof 2 — M-18 Acquisition Rights

**Formalisation.** Required: `admissible : Source × Terms → {ACQUIRE, REFUSE}`
and `retain : Source × Terms → RightsVocabulary`.

**Facts.** v2 §9: *"No legal, licensing, robots, rate-limit, or terms-of-use
policy for acquisition."* · v2 §14 X14 coverage: **No** · No `Closes` field
names M-18 · Regex for all eight required elements: **NONE** ·
`access_conditions` is free text, sole value inside a fenced example.

**Deductions.**

- D1 — `RightsVocabulary` undefined ⇒ `retain` has no codomain
- D2 — no criteria define ACQUIRE vs REFUSE ⇒ `admissible` has no decision rule
- D3 — a function with an undefined codomain or no decision rule is not
  computable from the specification

**Witnesses** (from B-34's own option list, all corpus-consistent):

| | Model |
|---|---|
| W1 | Permissive — `admissible = ACQUIRE` for all |
| W2 | Conservative — ACQUIRE iff explicitly licensed |
| W3 | Per-source assessment, recorded, unenforced |
| W4 | Per-source assessment with enforcement |

W1 never refuses; W4 can — observably non-isomorphic. B-34 lists them as OPEN
options and its header states *"No decision herein is ratified."*

**∴ ≥4 mutually inconsistent models satisfy the ratified theory. M-18 is
underdetermined. ∎**

---

## Proof 3 — T02.1.1 AC1 Non-Derivability

**Claim.** For AC1 a conforming implementation must answer: *given a source,
which member of the closed taxonomy is its `source_type`?*

1. The answer's range is the taxonomy's member set (AC1: "closed taxonomy")
2. That set is defined nowhere (Proof 1)
3. One candidate literal exists, and it is illustrative
4. It cannot be derived from `acquisition_method`, `access_conditions` or
   `capture_fidelity` — each free text with a single example value
5. It cannot be borrowed from `tags` (IOM L281 forbids load-bearing tags), nor
   from independence grouping (type-free by N-16/S-4)
6. No engine is authorised to assign it

**A function whose range is undefined and whose authority is unassigned is not
determinable.** Any implementation must **choose** the member set — an
architectural decision (F2) closing a marker by implementation (F3). **∎**

---

## Proof 4 — Cascade Determinism (positive proof)

Unlike the others, this proves an artefact **is** determined — but only after
the repair.

**Before.** `_collect()` ordered dependents breadth-first, i.e. by *shortest
path*. In a DAG that is **not** a topological order. A node with upstreams at
distance 1 and 5 was evaluated at distance 2, before its deep upstream was
condemned.

**After (fixpoint).** Eligibility is resolved by iterating until no further
object becomes eligible.

**Termination.** Every pass but the last adds ≥1 object to `doomed`; `doomed`
is bounded by the finite dependent set. **∎**

**Order-independence.** The fixpoint is the least set closed under "has no
valid upstream outside the set", which is unique regardless of iteration
order. **∎**

> **Note on authority (AS-3).** An earlier draft justified the gate sequence's
> determinism by citing *N-04 reproducibility*. That citation was **invalid** —
> N-04 states *"Outputs are not guaranteed deterministic."* The determinism
> claim stands on its own construction, not on N-04.

---

## Method

All four proofs follow the same shape:

1. **Formalise** the required artefact as a function or structure
2. **Enumerate** every ratified constraint mentioning it
3. **Show** what each constraint actually requires
4. **Exhibit** ≥2 non-isomorphic witnesses satisfying all constraints
5. **Search** for any discriminating predicate
6. If none exists, the specification does not determine the artefact

Step 5 is the one most often skipped, and the one that makes the proof binding.
