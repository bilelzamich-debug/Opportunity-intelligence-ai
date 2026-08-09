# Architecture Documents (FROZEN)

**These documents are frozen. They must never be edited in place.**

Where a ratified decision changes how one of these should be read, the change
is recorded in [`../governance/RATIFICATION-ANNOTATIONS.md`](../governance/RATIFICATION-ANNOTATIONS.md),
which is authoritative over the text it annotates.

Rewriting a frozen document is **Playbook F5** — forbidden.

---

## Files

| File | Lines | What it is |
|---|---|---|
| [`PKP_v1_Foundation.txt`](PKP_v1_Foundation.txt) | 64 | The original inheritance. Vision, five principles, ten-stage pipeline, nine engines, three shared components, eight object types, nine-phase roadmap. Four architecture decisions recorded as **bare titles** with no rationale — the omission later marked M-50 |
| [`PKP_v2_Master_Reference.md`](PKP_v2_Master_Reference.md) | 1,882 | The diagnostic pass over v1. Contains the canonical marker registers: **§11 contradictions, §12 open questions, §13 missing definitions**. This is the authority for marker numbering |
| [`PKP_Intelligence_Object_Model.md`](PKP_Intelligence_Object_Model.md) | 2,283 | Complete specification of all nine object types across 18 dimensions each. Contains decisions D-01…D-08, ratified as R-1…R-8 |
| [`PKP_Implementation_Backlog.md`](PKP_Implementation_Backlog.md) | 3,541 | Every task across all phases, with acceptance criteria, dependencies and complexity |
| [`PKP_PreP1_Blocker_Resolution.md`](PKP_PreP1_Blocker_Resolution.md) | 1,483 | Blocker analysis B-01…B-6x. **Header states: "No decision herein is ratified."** Recommendations only |

---

## Reading Order

If you are new, read in this order:

1. **`PKP_v1_Foundation.txt`** — 64 lines. What was inherited.
2. **`PKP_v2_Master_Reference.md` §1–§10** — what the architecture is.
3. **`PKP_v2_Master_Reference.md` §11–§13** — what is missing from it. This is
   the most important part of the corpus.
4. **`PKP_Intelligence_Object_Model.md` §1–§3** — the object contract.
5. **`../decisions/`** — what has since been decided.

---

## Critical Warnings

### The IOM uses a different marker numbering

The IOM was drafted against an intermediate numbering that **diverged** from
PKP v2 §13. The *substance* of every IOM statement is sound; the *identifiers*
are unreliable.

**Ten collisions exist.** Always resolve through
[`../markers/marker-crosswalk.md`](../markers/marker-crosswalk.md)
before citing any marker seen in the IOM. Four of the most dangerous:

| IOM cites | IOM means | Canonical | v2's own meaning for that number |
|---|---|---|---|
| `MISSING-18` | Source taxonomy / trust | **M-16** | Legal / licensing / terms-of-use |
| `MISSING-25` | Validation methodology | **M-32** | Pattern type taxonomy |
| `MISSING-31` | Retention policy | **M-38** | Post-validation promote/reject owner |
| `MISSING-36` | Outcome intake | **M-47** | Failure-handling policy |

### The Blocker Resolution is not authoritative

`PKP_PreP1_Blocker_Resolution.md` contains detailed options and
recommendations — including B-33 (source taxonomy) and B-34 (licensing), whose
wording was **lifted verbatim into backlog task descriptions**. This makes
tasks read as though a decision exists when it does not.

Its own header: **"Status: Analysis and recommendation. No decision herein is
ratified."**

### Known unannotated discrepancies

| # | Discrepancy |
|---|---|
| **D-3** | IOM §3.1 annotates `access_conditions` with "OPEN QUESTION-13", but canonical OQ-13 is *concurrency* (closed by N-11). A licensing-terms marker appears mis-merged |
| **D-4** | IOM §3.4 defines `source_diversity` as a count of *sources*; S-2 input 2 defines it as *types*. Under Article XI, S-2 governs its own input — but the Pattern attribute is unstated |
| — | v2 §14 (X14) names the M-18 gap "Legal **and compliance**"; §13 omits compliance. Whether compliance is in scope is unstated |

These are recorded, not resolved.
