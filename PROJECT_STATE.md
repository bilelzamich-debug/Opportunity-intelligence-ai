# Project State

**Authoritative statement of where the Opportunity Intelligence Platform stands.**
Last updated: **2026-08-27** — `T03.1.2` closed (claim decomposition, S-3).
Prior updates: 2026-08-27 (`T03.1.3` closed), 2026-08-26 (`T03.1.1` closed;
P2 closed), 2026-08-19 (D-1 resolved, `T02.1.3` closed, N-24 ratified),
2026-08-04 (ratification of N-20…N-23).

Every figure in this document was verified by execution or extraction, not
recalled. Where a number could not be verified, that is stated.

---

## 1. Phase Status

| Phase | Name | Status | Evidence |
|---|---|---|---|
| **P0** | Specification | ✅ **CLOSED** | 37 decisions ratified; `T00.7.1` exit gate passed |
| **P1** | Foundation | ✅ **CLOSED** 2026-08-04 | 44/44 tasks, 134/134 acceptance criteria, 60/60 closure checks |
| **P2** | Research Engine | ✅ **CLOSED 2026-08-26** | All 10 tasks CLOSED (F02.1+F02.2+exit); 8/8 source types acquired; coverage=1.0; 6 decisions ratified |
| **P3** | Fact Extraction | 🟡 **In progress** — `T03.1.1`/`T03.1.2`/`T03.1.3` CLOSED (08-26/08-27/08-27); `T03.1.5` unblocked; `T03.1.4` unblocked (needs `.2`+`.3`, both done) | — |
| **P4** | Problem Intelligence | ⬜ Not started | — |
| **P5** | Pattern Intelligence | ⬜ Not started | — |
| **P6** | Opportunity Intelligence | ⬜ Not started | — |
| **P7** | Solution & Validation | ⬜ Not started | — |
| **P8** | Feedback | ⬜ Not started | — |
| **P9** | Hardening | ⬜ Not started | — |

## 2. Decision Register — 42 Records

| Series | Count | Status |
|---|---|---|
| `AD-01` … `AD-04` | 4 | `RECONSTRUCTED` (inherited from v1, documented retrospectively) |
| `AD-05` | 1 | `RATIFIED` — Ground Truth Protection |
| `R-1` … `R-8` | 8 | `RATIFIED` — IOM decisions D-01…D-08 |
| `N-1` … `N-19` | 19 | `RATIFIED` — scope, boundary, control |
| `N-20` … `N-23` | 4 | `RATIFIED` **2026-08-04** — the P2 decision set |
| `N-24` | 1 | `RATIFIED` **2026-08-19** — acquisition-rights authority (role) |
| `S-1` … `S-5` | 5 | `RATIFIED` — semantics |
| **Total** | **42** | 38 ratified + 4 reconstructed |

### 2.1 The P2 Decision Set (ratified 2026-08-04)

| ID | Title | Closes | Owning task |
|---|---|---|---|
| **N-20** | Source Model: Closed Taxonomy by Acquisition Channel, with Non-Scoring Trust | M-16 (partially), OQ-28 (fully) | `T02.1.1` |
| **N-21** | Acquisition Rights: Per-Source Assessment Recorded on Evidence, Enforced Before Acquisition | M-18 (partially — rights half) | `T02.1.2` |
| **N-22** | Coverage Model: Source-Type Coverage with Explicit Gap Declaration | M-17 (partially) | `T02.1.4` |
| **N-23** | Research Trigger: Directive-Scoped Acquisition Within Scheduled Cycles | M-01 (partially) | `T02.2.4` |

All four ratified by the Project Owner with recorded reservations. **Zero
supersessions.** No frozen document was rewritten.

## 3. Implementation State

### 3.1 Metrics — all verified by execution

| Metric | Value | How verified |
|---|---|---|
| Production modules | **37** | `ls oip/*.py \| wc -l` |
| Production lines | **22,148** | `wc -l oip/*.py` |
| Test files | **46** | `ls tests/*.py \| wc -l` |
| Unit tests | **3,585 passing** | `pytest -q` |
| Stress tests | **128 passing** | `pytest -q -m stress` |
| **Total tests** | **3,713 passing, 0 failing** | both suites |
| Total coverage | **99.2%** | `pytest --cov=oip` |
| Modules below 95% | **0** | mechanical per-module check |
| Architecture verifiers | **443 checks passing** | 8 verifier scripts |
| Mutation score (cascade) | 19/20 killed, 1 proven equivalent | `mutate_t01_2_4_r1.py` |
| Mutation score (source) | **21/21 killed** | `mutate_t02_1_1.py` |
| Mutation score (coverage) | **14/14 killed** | `mutate_t02_1_4.py` |
| Mutation score (rights) | **14/14 killed** | `mutate_t02_1_2.py` |
| Mutation score (acquisition) | **15/15 killed** | `mutate_t02_2_1.py` |
| Mutation score (duplicates) | **12/12 killed** | `mutate_t02_2_2.py` |
| Mutation score (drift) | **13/13 killed** | `mutate_t02_2_3.py` |
| Mutation score (failure recording) | **12/12 killed** | `mutate_t02_2_5.py` |
| Mutation score (directives) | **14/14 killed** | `mutate_t02_2_4.py` |
| Mutation score (extraction) | **16/16 killed** | `mutate_t03_1_1.py` |
| Mutation score (anchoring) | **16/16 killed** | `mutate_t03_1_3.py` |
| Mutation score (decomposition) | **11/11 killed** | `mutate_t03_1_2.py` |
| Performance regressions | **0** | best-of-3, idle host |

### 3.2 Largest Modules

| Module | Lines | Purpose |
|---|---|---|
| `orchestration.py` | 2,617 | Batch cycles, sequencing, failure surfacing |
| `store.py` | 1,162 | Knowledge Store — the sole broad integration point |
| `opportunity.py` | 1,073 | Opportunity type, O-V1…O-V7 |
| `pattern.py` | 1,069 | Pattern type, PT-V1…PT-V6 |
| `feedback.py` | 1,019 | Feedback Record, FR-V1…FR-V6 |
| `execution.py` | 1,016 | Execution Record, X-V1…X-V6 |
| `problem.py` | 993 | Problem type, P-V1…P-V6 |

### 3.3 The 29 Modules

`__init__` · `acceptance` · `calibration` · `cascade` · `claim` ·
`configuration` · `contract` · `enums` · `evidence` · `execution` · `fact` ·
`feedback` · `graph` · `identity` · `integrity` · `lifecycle` · `lineage` ·
`opportunity` · `orchestration` · `pattern` · `problem` · `relationships` ·
`retention` · `semantic` · `solution` · **`source`** · `store` · `support` ·
`validation`

`source.py` is the only Phase-2 module. The other 28 are Phase-1 and frozen.

## 4. Marker Status

### 4.1 Closed in Phase 2

| Marker | State | Closed portion | Remaining open |
|---|---|---|---|
| **OQ-28** | ✅ **FULLY CLOSED** | Source trust attribute (N-20 §5.3) | — |
| **M-16** | 🟡 Partially closed | Taxonomy, eligibility, trust representation | Trust **scoring** (needs S-2 superseded); learnability (M-02/M-43) |
| **M-17** | 🟡 Partially closed | Coverage + completeness concepts | **Stopping** — "researched enough" → M-01 |
| **M-18** | 🟡 Partially closed | Rights half: legality, licensing, ToU, retention rights | **M-18b** conduct half; v2 §14 "compliance" scope |
| **M-01** | 🟡 Partially closed | Initiation, originators, lifecycle, scoping, cancellation; target approval (**D-1 resolved 2026-08-19**, N-23 §5.5(i)) | Self-direction (D-2, no canonical ID) |

### 4.2 Reserved Identifier

**M-18b** — acquisition *conduct* (robots, rate limits). Split from M-18 on
ratification of N-21. Zero backlog acceptance criteria depend on it.

### 4.3 Open Markers Surfaced in Production Code

M-01 · M-02 · M-04 · M-12 · M-13 · M-14 · M-16 (scoring) · M-17 (stopping) ·
M-18b · M-21 · M-22 · M-23 · M-24 · M-25 · M-26 · M-27 · M-29 · M-31 · M-32 ·
M-36 (policy) · M-42 · M-43 · M-47 · M-55 · M-56 · M-57 · M-61 · M-65 · M-66 ·
M-67 · M-69 · M-70 · C-01 · C-02 · C-04 · C-05 · OQ-05 · OQ-10 · OQ-11 ·
OQ-19 · OQ-21 · OQ-24 · OQ-34

Every one is cited in the code that fails closed because of it.

## 5. Recorded Reservations (Binding)

These were adopted as **choices**, not derivations, and are now in force.

| ID | Record | Reservation |
|---|---|---|
| **AS-0** | N-20 §13 | The eight taxonomy members are selected, not derived from the corpus |
| **AS-1** | N-20 §13 | Gate order (Scope → Typability → Rights) is selected; 6 permutations were legal |
| **AS-2** | N-20 §13 | Halt-on-first-refusal is selected, and **inverts** the N-08/N-10 all-failures precedent |
| **AS-3** | N-20 §13 | An invalid N-04 citation was removed; the determinism proof stands on its own construction |
| **AS-4** | N-22 §15 | The out-of-frame *duty* is forced by Article X; the *register mechanism* is selected |
| **AS-5** | N-20 §13 | `UNTYPABLE_CHANNEL` is a newly introduced token with no ratified antecedent |

## 6. Phase 2 Task Status

| Task | Status | Blocker |
|---|---|---|
| `T02.1.1` Source model | 🟡 **PARTIAL** — AC1 ✅ **(enum populated from N-20 §5.1, 2026-08-19)** AC2 ✅ **AC3 ❌** | M-02 / M-43 (learnability) |
| `T02.1.2` Licensing & access policy | ✅ **CLOSED 2026-08-19** — AC1 ✅ AC2 ✅ AC3 ✅ (`oip/rights.py`; verifier 27/27; mutation 14/14). Mechanism delivered; operational when the role supplies assessments and acquisition (`T02.2.1`) exists | Role assessments awaited (organisational) |
| `T02.1.3` Independence grouping | ✅ **CLOSED 2026-08-19** — explicit-input model; existing code + tests are the evidence | — |
| `T02.1.4` Coverage model | ✅ **CLOSED 2026-08-19** — AC1 ✅ AC2 ✅ AC3 ✅ (`oip/coverage.py`; verifier 33/33; mutation 14/14) | — |
| `T02.2.1` Acquisition | ✅ **CLOSED 2026-08-19** — AC1 ✅ AC2 ✅ AC3 ✅ (`oip/acquisition.py`; verifier 25/25; mutation 15/15). Gate order per N-20 §5.2.1 (gate 1 deliberately absent: M-01/T02.2.4); duplicate refusals delegated to E-V6 at acceptance | — |
| `T02.2.2` Duplicate detection | ✅ **CLOSED 2026-08-19** — AC1 ✅ (E-V6 classified as DUPLICATE_ACQUISITION) AC2 ✅ (`held_duplicate`) AC3 ✅ (`duplicate_refusals`/`duplicate_rate`, fail-closed). Verifier 25/25; mutation 12/12 | — |
| `T02.2.3` Drift detection | ✅ **CLOSED 2026-08-20** — AC1 ✅ (`detect`: N-15 mismatch against a named original) AC2 ✅ (`DriftRegister`, N-10 pattern) AC3 ✅ (supersession via store.transition **only on explicit fidelity declaration**; E-V6 ACTIVE-only enables re-acquisition). Verifier 26/26; mutation 13/13 | — |
| `T02.2.4` Directive intake | ✅ **CLOSED 2026-08-20** — AC1 ✅ (gate 1: only IN_EFFECT directives scope; RAISED/CANCELLED/EXPIRED/FULFILLED scope nothing) AC2 ✅ (targets recorded with their commissioning authority verbatim) AC3 ✅ (out-of-scope refuses at gate 1 with recorded failure, G16; order per N-20 §5.2.1). Verifier 30/30; mutation 14/14 | — |
| `T02.2.5` Failure recording | ✅ **CLOSED 2026-08-20** — AC1 ✅ (every refusal first-class in AcquisitionLog **and** projected into the T01.1.7 FailureStore with N-10's six identifications) AC2 ✅ (`attempted` derived from stage: gate refusals precede the external act per N-21 §5.2). Verifier 23/23; mutation 12/12 | — |
| `T02.3.1` P2 exit gate | ✅ **CLOSED 2026-08-26** — AC1 ✅ (8/8 types acquired through scope→typability→rights with complete provenance) AC2 ✅ (E-V6 duplicate refused, classified DUPLICATE_ACQUISITION, FailureStore record) AC3 ✅ (coverage=1.0, 0 gaps, declared-complete). Verifier 17/17 | — |

### 6.1 Phase 3 Task Status

| Task | Status | Blocker |
|---|---|---|
| `T03.1.1` Claim extraction | ✅ **CLOSED 2026-08-26** — AC1 ✅ (self-contained S-3-structured claims; F-V3 enforced at construction and acceptance) AC2 ✅ (qualifying_context verbatim; ambiguity refused, never guessed; uncertainty preserved) AC3 ✅ (density measured per Evidence, N-20-stratified, never a gate; spread 4.62× ≤ published 6.0× bound on the 8-record P2 corpus). `oip/extraction.py`: one request = one claim; S-5 layer 1 fail-closed (unique verbatim anchor, components present at span — pinned to AnchorVerifier on 200/200 samples); refusals recorded (N-10) with FailureStore projection; equivalence reported per S-3, never merged (T03.1.4). Module coverage 100%; verifier 42/42; probes 25/25; mutation 16/16 | — |
| `T03.1.3` Positional anchoring | ✅ **CLOSED 2026-08-27** — AC1 ✅ (every accepted Claim/Fact attachment carries a resolvable anchor: verbatim (T03.1.1, preserved byte-for-byte) AND positional, dual-resolvability demonstrated on 100% of the multilingual verification corpus; acceptance-path F-V2 held) AC2 ✅ (locator `chars <start>-<end>`, 0-based half-open code-point indexed; `resolve_locator` is a direct slice — no search of any kind, mechanically source-inspected; the register alone locates the claim with no content in hand). `extract()` computes, round-trip-verifies and registers the locator for every accepted extraction; ANCHOR_NOT_RESOLVABLE refuses fail-closed (attempted stage, N-10). S-5 bridge `oip/anchoring.py`: F-V6 PASSES via the ratified AnchorVerifier on 100% of the corpus; M-67 stays open; acceptance-path wiring is T03.2.1's deliverable. Module coverage 100% (extraction + anchoring); verifier 46/46; probes 26/26; mutation 16/16 | — |
| `T03.1.2` Claim decomposition | ✅ **CLOSED 2026-08-27** — AC1 ✅ (every claim decomposed byte-identically to the S-3 four-component structure across the full verification corpus; a claim the structure would carry but comparison cannot — a non-real or non-finite Quantity — is REJECTED with a recorded DECOMPOSITION_FAILED failure, no Fact, no anchor [S-3 "forced or rejected", N-10]) AC2 ✅ (every pairwise verdict recomputable from the four structure checks over the full matrix; self-equivalence 100%; merge-policy table == the S-3 decision; EQUIVALENT verdicts REPORTED, merging never executed [T03.1.4 boundary]). `decompose()` in `oip/extraction.py`; import set unchanged (6/6); claim.py/fact.py/semantic.py byte-pinned. Module coverage 100% (extraction); verifier 39/39; probes 21/21; mutation 11/11 | — |

## 7. Active Blockers

| # | Blocker | Type | Impact |
|---|---|---|---|
| **1** | **Rights assessments not yet supplied** — N-24 ratified 2026-08-19 names the authority role (*Designated Source Rights/Compliance Authority*); the role must now be staffed and supply assessments | Organisational (operational, not a decision) | No source can be admitted until assessments arrive; acquisition stays fail-closed (`UNASSESSED`) |
| **2** | **M-02 / M-43** — learning target vocabulary undefined | Open marker | `T02.1.1` AC3 unsatisfiable |
| **3** | **`source_diversity` ambiguity** — IOM §3.4 says "sources", S-2 says "types" | Corpus disagreement | Blocks clean PT-V4 implementation at `T05.1.4` |
| **4** | **D-2** — self-direction question has no canonical marker ID | Register gap | Cannot be tracked |

**D-1 was resolved 2026-08-19** (Project Owner selected N-23 §5.5(i);
`T02.2.4` AC2 amended to *"Targets recorded with their commissioning
authority"*; N-2 unchanged). **Blocker 1 requires a human decision** —
N-24 was ratified 2026-08-19 — the authority exists; blocker 1 is now
**operational** (staffing the role and supplying assessments), not a
decision to be analysed or implemented.

## 8. What Phase 1 Delivered

All 18 ratified Definition-of-Done criteria met:

**Functional** — nine object types persist with 17 universal attributes · no
object without resolvable lineage to Evidence · bidirectional traversal with
guaranteed termination · graph rebuild demonstrated · seven-state lifecycle
with per-type reachability · cascade terminates and is idempotent · confidence
ceiling enforced · engines invocable in pipeline order · failures
distinguishable from empty results.

**Contract** — V1–V12 enforced at acceptance · I1–I8 hold continuously · one
engine holds create authority per type · CI-1 verified · Article IV verified.

**Quality** — every acceptance criterion demonstrably met · tests
property-based, never equality-based · all tests pass · no architectural
decision made in code.

## 9. Defects Found and Fixed (Phase 1)

Twenty production defects were found and fixed during P1, each with regression
tests. The most consequential:

| # | Task | Defect |
|---|---|---|
| 19 | T01.8.1 | **T01.2.4 partial retraction never implemented** — cascade over-invalidated any dependent retaining a valid upstream |
| 20 | T01.2.4-R1 | I6 detective check flagged correct partial retraction as an integrity breach |
| 21 | T01.8.1 final | **Cascade BFS ordering** — BFS is shortest-path, not topological; a dependent could be spared while its entire support was withdrawn. Fixed by fixpoint iteration |

The last was found by adversarial probing *after* two prior gates and 3,136
tests had passed. It is the clearest evidence that the validation method —
extraction over recollection, adversarial probing before test-writing — earns
its cost.

## 10. Verification Commands

```bash
cd platform
python -m pytest -q                              # 3,585 pass
python -m pytest -q -m stress                    # 128 pass
python -m pytest -q --cov=oip --cov-report=term  # 99.2%
python validation/closure_t01_8_1.py             # 60/60
python validation/exit_gate_t01_8_1_rerun.py     # 94/94
python validation/verify_t02_1_1.py              # 38/38
python validation/verify_t02_1_4.py              # 33/33
python validation/verify_t02_1_2.py              # 27/27
python validation/verify_t02_2_1.py              # 25/25
python validation/verify_t02_2_2.py              # 25/25
python validation/verify_t02_2_3.py              # 26/26
python validation/verify_t02_2_5.py              # 23/23
python validation/verify_t02_2_4.py              # 30/30
python validation/verify_t02_3_1.py              # 17/17
python validation/verify_t03_1_1.py              # 42/42
python validation/verify_t03_1_3.py              # 46/46
python validation/verify_t03_1_2.py              # 39/39
```

## 11. Known Environment Constraints

- **Packages do not persist.** `pip install hypothesis pytest-cov` must be
  re-run each session. Symptom: ~32 collection errors.
- **Two-core shared host.** Benchmark variance is severe; use best-of-3 on an
  idle box and prove noise rather than assuming it.
- **Stress suite takes 17–18 minutes.** Long single commands can trip harness
  timeouts; split into batches and log to `validation/*.log`.
