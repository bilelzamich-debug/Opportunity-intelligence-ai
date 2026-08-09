# Reviews

Architecture Decision Reviews, ARB system-level reviews and revision reports.

| File | Type | Outcome |
|---|---|---|
| [`REVIEW-T00.2.7-feedback-record.md`](REVIEW-T00.2.7-feedback-record.md) | Escalation review | R-7 approved — ninth object type |
| [`REVIEW-T00.2.8-loop-closure.md`](REVIEW-T00.2.8-loop-closure.md) | Escalation review | R-8 approved — behavioural closure |
| [`ARB-REVIEW-M-16.md`](ARB-REVIEW-M-16.md) | Architecture Review Board | Recommended **split M-16** |
| [`ARB-REVIEW-P2-DECISION-SET.md`](ARB-REVIEW-P2-DECISION-SET.md) | System-level review | **CONDITIONALLY COHERENT** — 5 defects |
| [`REVISION-2-REPORT.md`](REVISION-2-REPORT.md) | Amendment record | Resolved C-1…C-5 |

---

## Why System-Level Review Exists

The ARB review of N-20…N-23 found **five interaction defects, two HIGH**, none
visible when each decision was reviewed alone:

| ID | Severity | Defect |
|---|---|---|
| **C-4** | HIGH | Three pre-acquisition gates, **no deterministic order** |
| **C-5** | HIGH | **Untypable sources vanished from coverage** — 100% while blind |
| C-3 | LOW | N-22 depended on open marker M-16, not on N-20 |
| C-2 | LOW | `PROPOSED`/`ACTIVE` overloaded across R-2 and directive states |
| C-1 | LOW | `OUT_OF_SCOPE` ownership unassigned |

C-5 reintroduced, at the seam between two individually-correct decisions,
exactly the sampling-bias blind spot M-17 exists to prevent.

> **Per-decision review is insufficient. Defects live at the seams.**

## The Full Review Chain

| # | Pass | Found |
|---|---|---|
| 1 | Architectural investigation | Markers genuinely open; underdetermination proven |
| 2 | Decision drafting | Four records |
| 3 | **ARB system review** | 5 interaction defects |
| 4 | Revision 2 | Fixes with proofs |
| 5 | Revision 2 validation | **A2/A6 were new architecture, not derivations** |
| 6 | Governance → Editorial → Cross-Reference → Final Board | GX-1…GX-3, then 6 broken references |

Ratification followed only after all six passed **and** explicit Project Owner
sign-off (F6).
