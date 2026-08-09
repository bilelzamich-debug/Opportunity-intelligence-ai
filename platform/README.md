# Platform — Implementation

The working implementation of the Opportunity Intelligence Platform.

| Metric | Value |
|---|---|
| Production modules | **29** (`oip/`) |
| Production lines | **18,418** |
| Test files | **37** (`tests/`) |
| Unit tests | **3,201 passing** |
| Stress tests | **128 passing** |
| Coverage | **99.04%**, no module below 95% |
| Architecture verifiers | **443 checks** |

---

## Layout

```
platform/
├── oip/            29 production modules — the platform itself
├── tests/          37 test files, property-based (N-4)
├── benchmarks/     Performance baseline and harness
├── validation/     Verifiers, probes, mutation suites, per-task logs
├── Makefile        test · cov · stress · bench · all
├── pytest.ini      pythonpath=. · testpaths=tests · addopts=-m "not stress"
└── .coveragerc     source=oip · branch=True · fail_under=95
```

---

## Running

```bash
pip install hypothesis pytest-cov   # NOT persisted across sessions

python -m pytest -q                 # 3,201 tests, ~30s
python -m pytest -q -m stress       # 128 tests, ~17 min
python -m pytest -q --cov=oip       # ~60s
python benchmarks/bench_identity.py # best-of-3 on an idle host
```

Or: `make test` · `make cov` · `make stress` · `make bench` · `make all`

---

## The 29 Modules

### Foundation
| Module | Task | Purpose |
|---|---|---|
| `enums.py` | T01.1.2 | Closed vocabularies — 9 types, 7 states, 10 relationships, 5 bands |
| `identity.py` | T01.1.1 | Identity allocation, version monotonicity, branching prevention |
| `contract.py` | T01.1.2 | The 17 universal required attributes |
| `lineage.py` | T01.3.2 | Objects-authoritative lineage (N-6) |
| `relationships.py` | T01.3.1 | Closed ten-type taxonomy (R-6) |

### Store and Graph
| Module | Task | Purpose |
|---|---|---|
| `store.py` | T01.1.4 | Knowledge Store — atomic writes, typed paths. **Sole broad integration point** |
| `graph.py` | T01.3.3–3.6 | Derived, rebuildable index; bidirectional traversal |
| `configuration.py` | T01.1.6–1.7 | Configuration + failure stores, CI-1 isolated |
| `retention.py` | T01.2.5 | ARCHIVED tiering by reachability (N-12) |

### Acceptance and Integrity
| Module | Task | Purpose |
|---|---|---|
| `acceptance.py` | T01.4.1–4.4 | V1–V12 at the `PROPOSED → ACTIVE` gate |
| `integrity.py` | T01.4.5 | I1–I8 as continuous invariants |
| `semantic.py` | T01.4.6 | Semantic verification hook (S-5 Layer 1) |
| `lifecycle.py` | T01.2.1 | Seven states, per-type reachability |
| `cascade.py` | T01.2.3/2.4 | Cascade invalidation + partial retraction |

### Confidence
| Module | Task | Purpose |
|---|---|---|
| `support.py` | T01.5.2 | Evidential support (S-2's five inputs) |
| `calibration.py` | T01.5.5 | Five-band rubric (S-1) |
| `claim.py` | T01.7.2 | Canonical claims (R-5) |

### Orchestration
| Module | Task | Purpose |
|---|---|---|
| `orchestration.py` | T01.6.1–6.5 | Batch cycles, sequencing, failure surfacing, concurrency boundary |

### Object Types
`evidence.py` · `fact.py` · `problem.py` · `pattern.py` · `opportunity.py` ·
`solution.py` · `validation.py` · `execution.py` · `feedback.py` — one per
Intelligence Object type, each with its per-type rules.

### Phase 2
| Module | Task | Purpose |
|---|---|---|
| `source.py` | T02.1.1 | Source registry, versioned trust, independence grouping |

> **`source.py` is the only Phase-2 module.** It was written *before* N-20 was
> ratified, so its `SourceType` enum is **deliberately empty** and every
> taxonomy operation fails closed citing M-16. Now that N-20 §5.1 supplies the
> eight members, the enum may be populated — **only** from that record.

---

## Architectural Constraints Enforced in Code

| Constraint | Where |
|---|---|
| Module dependency graph is a **DAG** | Verified by `closure_t01_8_1.py` |
| `store` is the **sole** broad integrator (≥15 imports) | All others ≤6 |
| `calibration` imports only `enums` | CI-1 boundary |
| `retention` imports only `enums` + `graph` | CI-1 boundary |
| `source` imports only `contract` | CI-1 boundary |
| No module claims to close a marker | Playbook F3 |
| Every module cites `Task:` and `Architecture References:` | Convention |

---

## Test Discipline (N-4)

**Outputs are not guaranteed deterministic.** Tests assert *properties*, never
equality on engine output (Playbook **F11**).

- Property-based via `hypothesis`
- Mutation-tested: every new rule broken deliberately, suite must fail
- Sources restored **byte-identically** after mutation (`diff -q` verified)
- Stress-tested at volume and under thread contention

---

## Known Environment Traps

| Trap | Symptom | Action |
|---|---|---|
| Packages not persisted | ~32 `ModuleNotFoundError: hypothesis` collection errors | Reinstall — not a regression |
| Two-core shared host | Wild benchmark variance | Best-of-3 on idle box; **prove** contention via `ps aux` |
| Killing a mutation run | Phantom "hangs", corrupted benchmarks | Never `kill -9`; verify `diff -q` afterwards |
| Stress suite ~17 min | Harness timeouts on long commands | Split into batches, log to `validation/*.log` |

---

## A Note on the `decisions/` Symlinks

`tests/test_calibration.py` verifies the calibration rubric **verbatim against
`S-01-calibration-rubric.md`** — a genuine specification-to-code cross-check.

It resolves the record at `<repo>/decisions/<ID>.md`. Because this repository
groups records under `docs/decisions/`, the historical paths are preserved
by symlinks rather than by editing a frozen Phase-1 test.

This was caught by running the suite in the copied tree: **1 failure that did
not exist in the original.** Worth stating plainly — the repository
reorganisation broke a real check, and the check did its job.
