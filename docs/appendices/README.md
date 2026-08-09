# Proposals and Reviews — NOT AUTHORITATIVE

Nothing in this directory is binding. These are working artefacts retained
because they show *how* the ratified decisions were reached — and, in two
cases, what was rejected.

The authoritative records are in [`../decisions/`](../decisions/).

---

## Files

| File | Type | Outcome |
|---|---|---|
| [`PROPOSAL-M-16-source-model.md`](PROPOSAL-M-16-source-model.md) | Architecture Decision Proposal | **Superseded** by N-20 |
| [`ARB-REVIEW-M-16.md`](../reviews/ARB-REVIEW-M-16.md) | Architecture Review Board | Recommended **split M-16** |
| [`ARB-REVIEW-P2-DECISION-SET.md`](../reviews/ARB-REVIEW-P2-DECISION-SET.md) | System-level review of N-20…N-23 | **CONDITIONALLY COHERENT** — 5 defects found |
| [`REVISION-2-REPORT.md`](../reviews/REVISION-2-REPORT.md) | Amendment record | Resolved C-1…C-5 |

---

## Why These Are Kept

### `PROPOSAL-M-16-source-model.md`

The first attempt at closing M-16. Its structure — facts separated from
assumptions from unresolved questions — became the pattern for all four final
records.

It also recorded the finding that shaped everything after: **S-2 lists five
exhaustive inputs and states "No other input."** Source trust is not among
them, so closing M-16 does **not** license trust-weighted scoring. That
constraint survives into N-20 §5.3.

### `ARB-REVIEW-M-16.md`

Established that M-16's two halves have **different evidentiary status** —
taxonomy underdetermined, trust representation determinable — and that bundling
them forced the determinable half to wait on the underdetermined one.

It also reported honestly that splitting would free **only 2 of 94 blocked
tasks**: a correctness improvement, not a throughput one. That candour
prevented the split being oversold.

### `ARB-REVIEW-P2-DECISION-SET.md`

The most valuable document here. It reviewed the four drafts **as one system**
and found five interaction defects invisible when each was reviewed alone:

| ID | Severity | Defect |
|---|---|---|
| **C-4** | HIGH | Three pre-acquisition gates, **no deterministic evaluation order** |
| **C-5** | HIGH | **Untypable sources vanished from coverage** — 100% coverage while blind |
| C-3 | LOW | N-22 depended on open marker M-16, not on N-20 |
| C-2 | LOW | `PROPOSED`/`ACTIVE` overloaded between R-2 and directive states |
| C-1 | LOW | `OUT_OF_SCOPE` ownership unassigned |

C-5 is the instructive one: it reintroduced, at the seam between two correct
decisions, exactly the sampling-bias blind spot M-17 exists to prevent.

> **Lesson.** Per-decision review is insufficient. Decisions must also be
> reviewed as a system, because defects live at the seams.

### `REVISION-2-REPORT.md`

Records the eight amendments resolving C-1…C-5, with determinism and
truthfulness proofs. Its own honest limitation is worth reading: two of the
fixes (**A2** gate ordering, **A6** out-of-frame register) were **new
architecture, not clarifications** — a finding surfaced by the subsequent
validation pass and now recorded as AS-1, AS-2 and AS-4.

---

## The Review Chain

Six passes stood between drafting and ratification. Each found something the
previous missed:

| # | Pass | Found |
|---|---|---|
| 1 | Architectural investigation | M-16/M-17/M-18/M-01 genuinely open; underdetermination proven |
| 2 | Decision drafting | Four records produced |
| 3 | ARB system-level review | **5 interaction defects (2 HIGH)** |
| 4 | Revision 2 | Fixes with proofs |
| 5 | Revision 2 validation | **A2/A6 were new architecture, not derivations** |
| 6 | Governance → Editorial → Cross-Reference → Final Board | GX-1…GX-3, then 6 broken references |

Ratification followed only after all six passed — and after explicit Project
Owner sign-off (Playbook F6).
