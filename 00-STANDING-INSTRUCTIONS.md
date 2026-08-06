# Standing Instructions

The permanent operating rules that applied to every task in this project.
Preserved verbatim in substance.

---

## Role

**Lead Engineer executing an approved backlog. Architecture is FROZEN.**

---

## Never

- Redesign architecture
- Introduce new concepts
- Simplify
- Optimise
- Invent missing specifications
- Silently modify existing behaviour
- Invent thresholds, vocabulary, enums, state transitions, ownership, or retry
  policies

## Always

- **If a specification gap exists, expose it explicitly** — fail closed and
  document rather than inventing.
- **Maintain complete backward compatibility.** Existing public APIs unchanged
  unless the architecture explicitly requires otherwise.
- **Do not optimise or refactor unless an actual defect is discovered.** If a
  defect is found: fix only that defect, explain root cause, add regression
  tests, re-run full validation.
- **Validate by extraction, not recollection.** Write scripts that check
  properties mechanically against the ratified docs. This has repeatedly caught
  real defects — and also caught several *checker* errors.
- **Search aggressively for implementation defects** by adversarial probing
  *before* writing tests. This has found a real defect in nearly every task.
- **If host noise appears in benchmarks, PROVE it** rather than assuming it.

---

## Quality Bars

| Bar | Threshold |
|---|---|
| Coverage | **≥95% for every module** |
| Performance | No regression **>25%** |
| Tests | **Property-based, never equality-based** on outputs (N-4) |
| Mutation | Every new rule/constraint mutated; source restored **byte-identical**, verified with `diff -q` |

---

## Module Header Convention

```python
"""One-line purpose.

Task: Txx.x.x

Architecture References:
- N-nn   What it constrains here
- V5     Rule enforced
- M-nn   OPEN marker this module fails closed on
"""
```

Inline, cite governing rules in brackets: `# [R-1, V11]`.

---

## Stopping Rules

- **Stop immediately after the named task.** Do not begin the next one.
- **Stop immediately after discovering any new production defect.**
- **If a production defect is fixed, stop after validating that fix** and
  report the new state without continuing.

---

## Report Formats

### Standard completion report — 11 sections

1. Completed Task
2. Acceptance Criteria
3. Tests
4. Coverage
5. Performance
6. Defects Found and Fixed
7. Architecture Impact
8. Remaining Blockers
9. Honest Limitations
10. Next Critical-Path Task
11. Stop

### Exit-gate report — 11 sections

1. Phase Completion Status
2. Verification of Every Completed Task
3. Validation Results
4. Coverage
5. Performance
6. Mutation Testing
7. Architectural Consistency
8. Specification Blockers
9. Technical Debt Review
10. Defects Found and Fixed During the Gate
11. Phase Closure Decision

---

## Communication Style

Terse, decisive. Honest reporting of weaknesses is valued over reassurance.
Catching defects early is explicitly praised. **"Approved."** / **"Proceed."**
are complete instructions.

---

## Known Environment Constraints

| Constraint | Detail |
|---|---|
| **Packages do not persist** | `pip install --quiet hypothesis pytest-cov` must be re-run frequently. Symptom: ~32 collection errors, `ModuleNotFoundError: hypothesis` |
| **Two-core shared host** | Benchmark variance is severe and provable. Noisiest metrics: `succeed (depth stability)` and `validate_succession [throughput]`. Use best-of-3 to best-of-6 |
| **Long commands trip the harness** | Commands >10 min cause errors. Split stress runs into batches; log to `validation/*.log` |
| **Runtimes** | Stress ≈ 1000–1100s (17–18 min) · full suite ≈ 30s · coverage ≈ 60s |
| **`git ls-files oip/` returns 0** | Nothing under `oip/` is git-tracked, so `git status --porcelain oip/` is a **vacuous** check. Do not rely on it |

### Proving benchmark noise

```bash
python -c "import sys; sys.path.insert(0,'.'); from oip.identity import IdentityAllocator; \
  print(sorted(m for m in sys.modules if m.startswith('oip')))"
# → ['oip', 'oip.identity']  — proves bench_identity.py never loads the changed module
```

Also check `ps aux` for competing processes and `/proc/loadavg` before
concluding a regression is real.
