# Validation Artefacts

Everything used to prove the implementation correct. **76 files.**

This directory is the reason defects were caught. It is not documentation of
the work — it *is* the work.

---

## Categories

| Kind | Count | Naming | Purpose |
|---|---|---|---|
| Architecture verifiers | 8 | `verify_*.py`, `closure_*.py`, `exit_gate_*.py` | Check properties mechanically against ratified docs |
| Adversarial probes | 22 | `probe_*.py` | Try to break the implementation *before* tests are written |
| Mutation suites | 8 | `mutate_*.py` | Break each rule deliberately; the suite must fail |
| Specifications | 8 | `*-specification.md` | Written before code, per task |
| Reports | 4 | `*.md` | Closure, defect analyses, investigations |
| Logs | 26 | `*.log` | Recorded runs, retained as evidence |

---

## Verifiers — 443 checks total

| Script | Checks | Scope |
|---|---|---|
| `closure_t01_8_1.py` | **60** | Phase 1 closure — backlog, functional, defects, architecture, markers |
| `exit_gate_t01_8_1_rerun.py` | **94** | 18 Definition-of-Done criteria + architectural validations |
| `exit_gate_t01_8_1_tasks.py` | **26** | Per-task traceability |
| `verify_t01_5_5.py` | 93 | Calibration rubric |
| `verify_t01_2_5.py` | 77 | Retention |
| `verify_t01_6_5.py` | 76 | Processing state |
| `verify_t01_6_4.py` | 64 | Concurrency boundary |
| `verify_t01_6_3.py` | 52 | Failure surfacing |
| `verify_t01_6_2.py` | 43 | Sequencing |
| `verify_t02_1_1.py` | **38** | Source model — open markers stay open |
| `verify_t02_1_1_blocker.py` | **33** | M-16 blocker substantiation |

```bash
python validation/closure_t01_8_1.py          # 60/60
python validation/exit_gate_t01_8_1_rerun.py  # 94/94
python validation/verify_t02_1_1.py           # 38/38
```

---

## Probes — where the real defects came from

Probes run **before** tests are written. Their job is to find what the
specification permits that the code assumes away.

| Probe | Found |
|---|---|
| `probe_t01_8_1_final.py` | **The cascade BFS ordering defect** — 4 of 9 probes failed |
| `probe_t01_8_1_legal_skew.py` | Proved it reachable with **legal objects** |
| `probe_t01_8_1_production_api.py` | Proved it reachable through **`store.write_validation()`** |
| `probe_t01_8_1_reachability.py` | Tested whether type layering made it unreachable |
| `probe_t01_2_5_*.py` | Archival impossible — **31/39 probes failed** |
| `probe_t01_6_*.py` | Bounded-phase starvation, bare-string id splitting |

> The three-stage reachability argument for the cascade defect is the model to
> follow: *reproduce it* → *prove it uses only legal objects* → *prove it
> survives the typed production API.* A defect that fails any stage is a test
> artefact, not a defect.

---

## Mutation Suites

Every new rule is broken deliberately; the suite must fail. Sources are
restored **byte-identically** and verified with `diff -q`.

| Suite | Result |
|---|---|
| `mutate_t02_1_1.py` | **21/21 killed, 0 survivors** |
| `mutate_t01_2_4_r1.py` | 19/20 killed; survivor **proven equivalent** |
| `mutate_t01_6_2/3/4/5.py`, `mutate_t01_2_5.py`, `mutate_t01_5_5.py` | All rules covered |

Two harness bugs were caught by mutation testing itself:

1. **An anchor with wrong indentation** silently skipped a mutation (reported
   `inapplicable`, not `killed`).
2. **A mutant that produced a non-terminating program** — the suite hung rather
   than failing, so "killed" could never be observed. Replaced with a
   terminating mutant and a per-mutant timeout.

> A surviving mutant means the tests do not protect the rule. An *equivalent*
> mutant must be **proven** equivalent, not assumed.

---

## Key Reports

| File | Finding |
|---|---|
| `PHASE-1-CLOSURE-REPORT.md` | Phase 1 closed — full metrics |
| `T01.8.1-DEFECT-cascade-bfs-ordering.md` | The defect that survived two gates and 3,136 tests |
| `T02.1.1-ARCHITECTURE-CHALLENGE.md` | 7 attacks on the M-16 blocker; all failed |
| `T02.1.1-DERIVABILITY-INVESTIGATION.md` | Formal proof: ≥3 valid taxonomies satisfy every ratified constraint |

---

## The Method

Established across Phase 1, refined by what each step caught:

1. **Extract, never recall.** Write the specification from the ratified sources
   first, with line references.
2. **Probe adversarially** before writing a single test.
3. **Write property-based tests** — never equality on outputs (F11).
4. **Mutate** every new rule; restore byte-identically.
5. **Verify mechanically** — and treat a verifier failure as equally likely to
   be a bug in the *verifier*.

> **On step 5:** during the Phase-2 work, **10 of 10** initial verifier
> failures were checker errors, not code defects — invented API names, and two
> regexes that matched *prose documenting a marker as open* and so asserted the
> opposite of their intent. Had those been trusted, working production code
> would have been "fixed".

---

## Reading the Logs

`*.log` files are retained runs, not summaries. They record what actually
happened, including failures. Notable:

| Log | Contents |
|---|---|
| `T01.8.1-exit-gate.log`, `*-rerun.log` | The first two gate runs — **both halted on defects** |
| `T01.8.1-final-full.log`, `*-final-stress.log` | The passing run: 3,136 + 116 |
| `CLOSURE-mutation.log`, `CLOSURE-stress.log` | Final closure evidence |
| `T01.8.1-R2-mutation.log` | Mutation after the cascade repair |
