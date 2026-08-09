# Changelog

Chronological record of architectural and implementation change.

Format: newest first. Every entry states what changed, why, and what it cost.
Dates are the project's own recorded dates.

---

## 2026-08-04 — Phase 2 Decision Set Ratified

### Added — 4 ratified decision records

| ID | Title | Closes |
|---|---|---|
| **N-20** | Source Model: Closed Taxonomy by Acquisition Channel, with Non-Scoring Trust | M-16 (partially), **OQ-28 (fully)** |
| **N-21** | Acquisition Rights: Per-Source Assessment Recorded on Evidence, Enforced Before Acquisition | M-18 (partially — rights half) |
| **N-22** | Coverage Model: Source-Type Coverage with Explicit Gap Declaration | M-17 (partially) |
| **N-23** | Research Trigger: Directive-Scoped Acquisition Within Scheduled Cycles | M-01 (partially) |

Ratified by the Project Owner with recorded reservations **AS-0…AS-5**.
**Zero supersessions.** No frozen document rewritten.

### Register mutations

- `decisions/README.md` — 4 rows added; counts **33→37 ratified, 37→41 total**
- `marker-crosswalk.md` — new §5.1 recording four partial closures; **M-18b**
  identifier reserved for the acquisition-conduct half
- `RATIFICATION-ANNOTATIONS.md` — new §10 with eight binding annotations,
  including the IOM §3.1 / S-2 precedence resolution and the N-2 / D-1 note
- Pre-ratification drafts retired to `decisions/superseded-drafts/`

### Defects caught during ratification execution

- **N-20 sign-off silently failed to apply** — its ratification notice used
  different wording than the other three, so the pattern-based edit missed it.
  Applied explicitly rather than left absent.
- **N-23 contained a stale `(DRAFT N-22 §5.4)` cross-reference** — corrected to
  `(N-22 §5.4)` now that N-22 is ratified.

### Ratification path — six review passes

1. **Architectural investigation** — M-16, M-18, M-17, M-01 each proven genuinely open
2. **Decision drafting** — four records produced
3. **ARB system-level review** — found 5 interaction defects (2 HIGH)
4. **Revision 2** — resolved C-1…C-5 with proofs
5. **Revision 2 validation** — found A2/A6 were new architecture, not derivations
6. **Governance review → Editorial Integrity Pass → Cross-Reference Integrity Pass → Final Ratification Board**

### Interaction defects found and fixed (Revision 2)

| ID | Severity | Defect |
|---|---|---|
| **C-4** | HIGH | Three pre-acquisition gates existed with **no deterministic evaluation order** — a source failing several produced an indeterminate refusal reason |
| **C-5** | HIGH | **Untypable sources vanished from coverage** — the platform could refuse a whole class of material and report 100% coverage |
| C-3 | LOW | N-22 depended on open marker M-16 rather than on N-20 which closes it |
| C-2 | LOW | `PROPOSED`/`ACTIVE` overloaded between R-2 object states and N-23 directive states |
| C-1 | LOW | `OUT_OF_SCOPE` ownership unassigned — each draft deferred to the other |

Resolutions: a fixed gate order with halt-on-first-refusal and a determinism
proof; an out-of-frame register making coverage truthful; dependency
re-pointing; directive states renamed to `RAISED`/`IN_EFFECT`; vocabulary
ownership assigned to N-22.

### Governance defects found and fixed (Editorial + Cross-Reference passes)

| ID | Defect |
|---|---|
| **GX-1** | AS-1…AS-5 existed only in an external review, not in the records they qualified |
| **GX-2** | N-20 §5.2.1 cited **N-04** for determinism — N-04 states the *opposite* ("Outputs are not guaranteed deterministic") |
| **GX-3** | N-20 §13 and N-22 §15 were factually stale after Revision 2 |
| **D-A** | Four references in N-21 to non-existent sections (§6.1, §6.2, §14) |
| **D-B** | Two references in N-22 to non-existent subsections (§11.3, §12.3) |

---

## 2026-08-04 — Phase 1 CLOSED

**44/44 tasks · 134/134 acceptance criteria · 18/18 Definition-of-Done criteria.**

| Gate | Result |
|---|---|
| Full suite | 3,142 passed, 0 failed |
| Stress suite | 116 passed |
| Closure verifier | 60/60 |
| Exit gate | 94/94 |
| Task gate | 26/26 |
| Architecture verifiers | 405/405 |
| Coverage | 99.02%, no module below 95% |
| Mutation | 19/20 killed, survivor proven equivalent |
| Performance | 0 regressions, best-of-3 on idle host |

### Defect #21 — cascade BFS ordering (found by the final gate)

**Root cause.** `_collect()` ordered dependents breadth-first — by *shortest
path*. In a DAG that is **not** a topological order. A node with upstreams at
distance 1 and 5 was evaluated at distance 2, before its deep upstream was
condemned, so that upstream still read as "attesting" and the node was spared.

**Impact.** An object could remain `ACTIVE` after **every** upstream reference
was withdrawn — precisely the silent corruption I6 exists to prevent.

**Reachability proven through the production API.** Six of eight derived types
enforce a single upstream type, but `Validation` correctly does not (IOM §3.7:
"DERIVES_FROM the object containing the tested claim"; IOM types DERIVES_FROM
as `any → any`). A Validation accepted by `store.write_validation()` — passing
V1–V12, I1–I8, V-V1…V-V6 — reproduced it.

**Fix.** Fixpoint iteration rather than topological ordering, chosen because
`plan()`'s breadth-first order is a *documented, tested public contract*;
re-ordering would have forced weakening a test. Eligibility now resolves to a
fixpoint, making the result independent of traversal order.

**Why the suite missed it.** All five partial-retraction tests used
uniform-depth lineage, where BFS coincides with topological order. No test
constructed a stage-spanning edge. Both gate verifiers passed because they
asserted the rule's *shape*, never its behaviour on a non-uniform graph.

### Also fixed during the gate

- **Exit-gate tally bug** — `failed = [...]` was computed *before* the last
  checks ran, so appended checks were silently excluded. The gate reported
  94/94 and exit 0 on a knowingly defective build. Now reports 92/94, exit 1.
- **I6 detective check** — flagged correct partial retraction as an integrity
  breach (15 violations on a legitimately spared population).

---

## 2026-08-02 → 2026-08-04 — Phase 1 Execution

44 tasks across 8 features. **Twenty production defects found and fixed**, each
with regression tests. Selected:

| Task | Defect |
|---|---|
| T01.1.1 | Succeeding the same version twice forked the chain — added `BranchingError` |
| T01.1.4 | Atomicity bug — `_commit` indexed the graph *before* the I5 check, leaving an orphan edge |
| T01.4.3 | V5 silently permissive on unresolvable upstream; V8 crashed on naive/aware datetime mix |
| T01.4.5 | **I8 entirely unenforced** |
| T01.6.2 | **Bare-string id collections split character-wise** — `input_ids="abc"` stored `"a","b","c"`, defeating repeat detection |
| T01.6.4 | **Bounded concurrent phase starved the whole cycle** — 12 items under `max_work_items=4` attempted zero |
| T01.7.3 | P-V2 substring false positive — "blacklacks" matched "lacks" |
| T01.7.5 | Terminal status crashed the shared acceptance path; O-V6 structurally dead |
| T01.7.8 | X-I3 accepted a hand-wave ("No deviations of note occurred") |
| T01.2.5 | **My own first design made archival impossible** — treating "is ACTIVE" as protection protected everything (31/39 probes failed) |
| T01.5.5 | `BandCriterion.contains()` returned False for 0.195/0.395/0.599/0.799 — S-1's printed 2dp ranges leave gaps |

---

## 2026-08-02 — Phase 0 CLOSED

37 decisions ratified. `T00.7.1` exit gate passed.

### Era 2 — Governance first

Established the decision register, the six-field mandatory template, and the
canonical marker crosswalk. **The crosswalk exposed ten marker-identifier
collisions, not the eight previously catalogued** — two of which would have
caused ratifications to close entirely the wrong gaps.

> **Lesson that shaped everything after.** The two extra collisions were found
> only by exhaustively extracting every marker reference rather than trusting a
> prior summary. *Validate by extraction, not by recollection* was applied to
> every subsequent feature and repeatedly caught real defects.

### Era 3 — The AD-01 / AD-03 conflict

AD-01 (Evidence-First) and AD-03 (Feedback Loop) were found to be in **direct
conflict**: the loop implementing continuous learning undermined the
evidence-first guarantee. Resolved by **R-8** (the loop closes *behaviourally*)
and **AD-05** (Ground Truth Protection — no platform-generated artifact may
become Evidence, with four exhaustive permitted forms).

> Neither decision solved loop *instability* — the behavioural path (learning
> narrows research, which narrows findings) remains open as **M-70**, recorded
> in both records so neither is misread as having solved it.

---

## Pre-project — Inheritance

PKP v1 defined a vision, five principles, a ten-stage pipeline, nine engines,
three shared components, eight Intelligence Objects and a nine-phase roadmap.

**It recorded four architecture decisions as bare titles** — no context, no
alternatives, no rationale. That omission (later **M-50**) meant nobody could
distinguish a considered constraint from an unexamined default, and is where
the decision register begins.

Key diagnosis from Era 1: v1 was **structurally sound and radically
under-specified**. Across all analysis, no finding indicated the pipeline,
engine decomposition or object model was *wrong*. Every gap was an omission,
not an error — a far better position than the reverse.
