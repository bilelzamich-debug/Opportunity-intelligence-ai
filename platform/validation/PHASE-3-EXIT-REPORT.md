# Phase 3 — Exit Gate Report

**Task:** `T03.3.1` — P3 Exit Gate ("Verify P3 exit: Facts extractable
with anchoring, hallucination rate measured, duplicates recognised.")
**Date:** 2026-09-12
**Verdict:** **P3 EXIT — PASS**

---

## 1. Scope and method

`T03.3.1` executed as a read-only audit of the whole of Phase 3 against
the authoritative backlog entry (dependencies `T03.2.3`, `T03.1.6`,
`T03.1.5`; deliverable: this report; blocks `T04.1.1`). No production
code, tests, governance records, markers or pins were modified to
obtain this verdict; the only file created by the gate is this report
itself. All numbers below were re-measured in this run, not reused.

## 2. Acceptance criteria — criterion-by-criterion

| AC | Criterion | Evidence (re-verified 2026-09-12) |
|---|---|---|
| 1 | **Facts anchored to specific evidence locations** | T03.1.3 positional anchoring: every `EvidenceAttachment` carries `evidence_ref` + `positional_anchor`, mechanically resolvable (`test_extraction.py`, `verify_t03_1_2` AC rows green). T03.2.1 anchor verification runs on **100% of Facts** at acceptance, rejects fabricated anchors, blocks acceptance on failure (`test_anchor_verification.py` 24/24; `AnchorVerifier` + `install_anchor_verification`); Layer-1 `anchor_failure_rate` measured, explicitly not the hallucination rate |
| 2 | **Hallucination rate published** | T03.2.3 Layer-3 metrics per RATIFIED F-A2: `quality_metrics()` / `metric_trend()` — deterministic, queryable, frozen `QualityMetricSnapshot` (hallucination rate = unsupported/judged, drift rate = drifted/judged, judged-only denominator, None-on-zero, dual scopes, judged_at sparse UTC-day trend); 31 focused tests; `auditing.py` 100% coverage |
| 3 | **Corroboration countable via `independent_source_count`** | N-16 Tier-1 attribute on every object (`contract.py`, non-negative-validated; F-V5 `<= attachment count` enforced on Fact); extraction initialises it (never inflated — independence never inferred); merged attachments accumulate corroboration (`test_fact.py`: `independent_source_count == 2` on multi-source Facts; `test_merging.py`: canonical never inflated); consumed downstream via the store's N-16 read and `compute_support` |

## 3. P3 task matrix (authoritative: backlog F03.1/F03.2/F03.3 — exactly ten tasks, no others)

| Task | Title (abridged) | Status | Evidence |
|---|---|---|---|
| T03.1.1 | Claim extraction with qualifying context | ✅ | `verify_t03_1_1` 42/42; `test_extraction.py`; S-5/F-V3 semantics |
| T03.1.2 | Structured claim decomposition per S-3 | ✅ | `verify_t03_1_2` 38/40 (only the 2 protected stale S-03/R-05 pins fail); `test_extraction.py`; S-3 RATIFIED |
| T03.1.3 | Positional anchoring (F-V2) | ✅ | `verify_t03_1_3` 47/47; anchor resolution tests |
| T03.1.4 | Canonical-claim merging (D-05) | ✅ | `verify_t03_1_4` 29/29; `test_merging.py`; R-5 + S-3 RATIFIED |
| T03.1.5 | Assertion vs attributed-opinion (F-V4) | ✅ | `test_claim_type_classification.py`; F-V4 RATIFIED; blocks this gate — dependency met |
| T03.1.6 | Contradiction detection | ✅ | `test_contradiction.py`; F-C1 RATIFIED (linked, not resolved; both Facts ACTIVE); blocks this gate — dependency met |
| T03.2.1 | Anchor verification | ✅ | `test_anchor_verification.py` 24/24; acceptance-path hook; 100% coverage of Facts |
| T03.2.2 | Sampled deep audit | ✅ | `test_auditing.py` 60/60 (unmodified); F-A1 RATIFIED + independently reviewed + corrected |
| T03.2.3 | Hallucination rate metric | ✅ | `test_auditing.py` 91/91 total; F-A2 RATIFIED before implementation; this gate's AC2 |
| T03.3.1 | P3 exit gate | ✅ | This report |

## 4. Marker matrix (live register, `docs/markers/MARKER-REGISTER.md`)

| Marker | State | P3 exit effect |
|---|---|---|
| M-20 | **CLOSED** (Phase 3, 2026-09-12, by F-A2; seven OD-6 conditions satisfied; governance closure verified) | AC2 basis |
| M-67 | **PARTIAL / OPEN with severity reduced** (S-5; F-A1/F-A2/closure annotation) | **Explicitly carried forward by ratified design** — sampling measures, it does not eliminate; the residual is published, not hidden. Not an exit blocker |
| M-19 | OPEN (extraction granularity; compound inputs carried verbatim, never split — recorded interpretation) | Carried forward; no P3 task or AC requires closure |
| M-11, M-62, M-23 | CLOSED (R-5, S-3, N-16) | P3 foundations |
| M-66 | OPEN (lineage summarisation; cross-cutting) | No P3 dependency |
| M-12/M-21/M-22, M-13/M-24/M-25 | OPEN (Problem/Pattern stage markers in the register's P3–P5 grouping) | P4/P5 concerns — not P3-exit-relevant |

**No open marker blocks P3 exit.** M-67 is the designed, published
residual risk of the ratified layered-fidelity architecture.

## 5. Verification results (this run)

- Full suite: **3791 passed / 0 failed / 128 deselected**; coverage
  **99.2%** total; `oip/auditing.py` **100%**.
- Verifiers: 19/19 in expected state — 17 fully green;
  `verify_t03_1_2` **38/40** (only the 2 protected stale S-03/R-05
  pins); `verify_t01_5_5` **92/93** (only the pre-existing
  worktree-state check).
- Phase-1 gates still green: `closure_t01_8_1` 60/60;
  `exit_gate_t01_8_1_rerun` 94/94; `exit_gate_t01_8_1_tasks` 26/26.
- `scripts/verify_all.sh`: 19 passed / 2 failed — the protected stale
  "3410" unit-count pin and the same T01.5.5 wrapper, unchanged in
  kind (standing rule: not "fixed").
- Module count **38**; byte pins (claim/fact/semantic) green;
  import-set pins green; marker-register consistency green.
- Worktree: 15 modified / 16 untracked — the authorized session work
  (T03.1.x–T03.2.3 + ratified governance artifacts); no unauthorized
  architecture changes; HEAD `01906a5`.

## 6. Boundary audit

T03.2.3 remains the minimum Layer-3 surface (no general observability,
no proxy framework, no phase-exit wiring — T09.1.4/T09.1.2 own those
and remain unstarted). No sampling-rate correction exists (F-A1 R10;
the 5% per-draw constant never enters a metric). T03.2.2 semantics
intact (F-A1 R1–R12; 60 T03.2.2 tests green and unmodified). M-20
CLOSED; M-67 OPEN. N-2/N-7/N-10/N-14 disciplines unchanged.

## 7. Decision

All three authoritative exit criteria are satisfied with concrete
test and verification evidence; all ten P3 tasks are complete; no
open marker blocks exit; the protected pre-existing verifier
exceptions are unchanged in kind and are not exit criteria.

**P3 EXIT — PASS.** The next authorized task is **`T04.1.1`**
(Phase 4 — Problem Intelligence; entry dependencies `T01.7.3` ✅
(Phase 1 CLOSED) and `T03.3.1` ✅ (this gate)).
