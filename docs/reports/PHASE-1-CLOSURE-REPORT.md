# Phase 1 — Final Closure Report

**Task:** `T01.8.1` — Phase 1 Exit Gate (final closure run)
**Date:** 2026-08-04
**Verdict:** **PHASE 1 CLOSED**

---

## 1. Completed Task

`T01.8.1` executed as an independent re-verification of the whole of Phase 1
from first principles. Every completed task was treated as untrusted; no
conclusion, metric or verifier result from any previous run was reused.

**No production code was modified during this gate.** Final state:

| File | md5 |
|---|---|
| `oip/cascade.py` | `b603ce9ed81d7026f87b7466bdeac080` |
| `oip/integrity.py` | `42f1a9507b9679a25cfef9321a07fa6a` |

Mutation-artefact residue scan (`if False:` / `for _once in`): **CLEAN**.

---

## 2. Phase Completion Status

All **44** Phase-1 tasks implemented across **8** features (F01.1–F01.8), all
**14** deliverables present, all **134** acceptance criteria accounted for.

Dependency closure verified: no Phase-1 task depends on a later phase or on an
unknown task. Every one of the 44 task ids is cited in production code or
tests (traceability).

---

## 3. Acceptance Criteria

A purpose-built closure verifier (`validation/closure_t01_8_1.py`, **60
checks**) re-establishes each property by execution, not by inspection of
prior reports.

| Section | Result |
|---|---|
| A — Backlog completion (44 tasks / 134 criteria / 14 deliverables) | 9/9 |
| B — Functional verification | 32/32 |
| C — Previously discovered defects, re-tested | 4/4 |
| D — Architectural integrity | 7/7 |
| E — Open markers remain open | 8/8 |
| **Total** | **60/60** |

**The verifier was itself validated.** Run against a deliberately re-broken
`cascade.py`, it reports **59/60 and exits 1**, failing precisely on the
uneven-depth cascade check. It discriminates rather than merely passing.

### Ratified Definition of Done (P1-EXECUTION-PLAN §6)

| # | Criterion | Result |
|---|---|---|
| 1 | Nine types persist with 17 universal attributes | PASS (see §9) |
| 2 | No object accepted without resolvable lineage (V2/V3/V4) | PASS |
| 3 | Lineage traversable both directions; termination guaranteed | PASS |
| 4 | Graph rebuild demonstrated | PASS |
| 5 | Seven-state lifecycle, per-type reachability | PASS |
| 6 | Cascade terminates and is idempotent | PASS |
| 7 | Confidence ceiling enforced; IOM example reproduced | PASS |
| 8 | Engines invocable in order; violations rejected | PASS |
| 9 | Failures distinguishable from empty results | PASS |
| 10 | V1–V12 enforced at acceptance | PASS |
| 11 | I1–I8 hold continuously | PASS |
| 12 | Exactly one engine holds create authority per type | PASS |
| 13 | CI-1 verified | PASS |
| 14 | Article IV / AD-05 verified | PASS |
| 15 | Every acceptance criterion demonstrably met | PASS |
| 16 | Tests property-based, never equality-based (N-4) | PASS |
| 17 | All tests pass | PASS |
| 18 | No architectural decision made in code | PASS |

---

## 4. Tests

| Suite | Result |
|---|---|
| Full suite | **3142 passed**, 116 deselected, 0 failed (29.9s) |
| Stress suite | **116 passed**, 0 failed (1062.8s / 17m43s) |
| Closure gate | **60/60** |
| Exit gate (`exit_gate_t01_8_1_rerun`) | **94/94** |
| Task gate (`exit_gate_t01_8_1_tasks`) | **26/26** |
| Architecture verifiers (6) | **405/405** (43+52+64+76+77+93) |
| Adversarial probes | 9/9; production-API probe: 0 I6 violations |

**Total: 3,258 tests green** (3,142 + 116 stress).

---

## 5. Coverage

Total **99.02%** — `fail_under = 95` satisfied.

**No module falls below 95%** (checked mechanically). Lowest: `integrity.py`
96.0%. `cascade.py` (the repaired module) **99.6%**. Nine modules at 100%.

---

## 6. Performance

Best-of-3 on a verified-idle host (load 0.54, no competing processes):

| Run | Median throughput |
|---|---|
| 1 | 174,779 ops/sec |
| 2 | 170,215 ops/sec |
| 3 | 171,522 ops/sec |

**Zero regressions** against the 2026-08-02 baseline (174,989 ops/sec) in all
three runs. No metric exceeded its 25/20/25% threshold.

---

## 7. Mutation Testing

**19/20 killed.** Sources restored **byte-identical** (verified by `diff -q`
and md5).

The mutations covering the repaired logic — **M17** (fixpoint collapsed to a
single pass, i.e. the exact defect) and **M18** (progress never signalled) —
are both **killed**.

The single survivor **M19** is a proven **equivalent mutant**, not a test gap:
it swaps `doomed_dependents` for `doomed`, which differ only by `origin_id`,
and the loop iterates only over `undecided`, which `_collect()` can never seed
with the origin (it seeds `seen = {origin_id}` and appends only unseen
children). Verified structurally and empirically.

---

## 8. Architecture Impact

**None.** No architecture, contract, object model, API, ownership,
responsibility, acceptance rule or specification was changed by this gate.

Verified: module import graph is a **DAG**; `store` is the **sole** broad
integration point (≥15 imports); boundary modules (`calibration`, `retention`,
`orchestration`) import exactly their permitted dependencies; all public API
surfaces intact; every module cites `Task:` and `Architecture References:`; no
module claims to close a marker.

### Open markers — all verified still OPEN

`C-02`, `M-65`, `M-36` (policy half), `M-57`, `OQ-10`, `OQ-11`, `OQ-34`.

Two marker checks in the first draft of the verifier were **wrong in a
dangerous direction**: they regex-matched the words "retry" and "backflow" in
*prose that documents the markers as open*, and so asserted the opposite of
their intent. Corrected to scan executable code only, excluding comments and
doc lines.

---

## 9. Specification Blockers

**C-02 (Execution is a pipeline stage with an object but no engine)** remains
open and is *observable in behaviour*: `ObjectType.EXECUTION_RECORD` has no
entry in `CREATE_AUTHORITY`, so `V7` **fails closed** with
`"no engine holds create authority for ExecutionRecord [C-02 open]"`.

Consequently **eight of nine** object types persist through the generic write
path; ExecutionRecord cannot. This is the ratified behaviour — inventing an
authority would close C-02 in code, which is forbidden. A typed write path
exists for all nine types. DoD criterion 1 is judged met on that basis, and
the limitation is stated rather than papered over.

---

## 10. Technical Debt Review

1. **T01.2.4 re-versioning half.** Cascade spares a partially-retracted object
   but does not create the "new version with reduced support" (IOM §3.2). N-9
   forbids cascade from altering content, so this belongs to the owning
   engine, which does not exist before P2. Status semantics complete; the
   reduced-support version is produced by nothing today.
2. **Fixpoint is O(n²) worst-case** versus O(n) for a single pass.
   Unmeasurable at current scale; no benchmark covers cascade.
3. **No benchmark covers cascade, store or graph.** `bench_identity.py`
   exercises only `oip.identity`. Cascade performance is unmeasured.
4. **M-36 policy half** treated as open and failed closed (documented in
   `T01.6.3-specification.md` §7 and the `orchestration.py` header).

---

## 11. Defects Found and Fixed During the Gate

**Zero production defects** found in this run.

Ten checks failed on the first execution of the new closure verifier. **All
ten were checker defects**, diagnosed by extracting the real APIs rather than
assuming the code was wrong:

| Failure | Cause |
|---|---|
| `evidence_reachable_from` ×2 | Invented method; real API is `evidence_set` / `reaches_evidence` |
| `band_for` | Invented; real API is `criterion_for_value` |
| `RetentionPolicy(graph=…)`, `may_archive` | Wrong signature and method; real API is `(store=, graph=)` and `is_archivable` |
| `except Exception` in orchestration | Code uses the stricter `except BaseException` |
| "28 modules" → 27 | `MODULES` excludes `__init__.py` by design |
| `configuration:no-task` | Header reads `Tasks:` (plural) — it implements two |
| M-36 / OQ-11 "closed" | Regex matched prose documenting the markers as OPEN |
| ExecutionRecord V7 rejection | Correct fail-closed behaviour under open C-02 |

A separate **pre-existing fragility in the exit gate** was found and fixed
during the preceding repair task: `failed = [...]` was computed *before* the
final checks ran, so appended checks were silently excluded from the tally
(the gate reported 94/94 and exit 0 on a knowingly defective build). Now
correctly reports 92/94 / exit 1 on that build.

---

## 12. Phase 1 Closure Decision

> ### PHASE 1 IS **CLOSED**.

Every gate in the official closure procedure passes on a clean, verified tree:

- 44/44 tasks · 134/134 acceptance criteria · 14/14 deliverables
- 18/18 ratified Definition-of-Done criteria
- 3,258 tests green (3,142 full + 116 stress); 0 failures
- 60/60 closure · 94/94 exit gate · 26/26 task gate · 405/405 architecture
- Coverage 99.02%, no module below 95%
- Mutation 19/20, sole survivor proven equivalent, sources byte-identical
- 0 performance regressions, best-of-3 on a verified-idle host
- All 7 protected markers verified still open; no forbidden closure invented

`T02.1.1` (Phase 2 — Research Engine) and `T07.1.3` are unblocked.

**No Phase 2 work has been started.**
