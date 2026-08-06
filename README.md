# Scripts

Repository tooling.

| Script | Purpose |
|---|---|
| [`verify_all.sh`](verify_all.sh) | Run the complete validation battery |

---

## `verify_all.sh`

Re-derives every figure quoted in [`../PROJECT_STATE.md`](../PROJECT_STATE.md)
by execution. Nothing is summarised or cached.

```bash
./scripts/verify_all.sh          # fast  (~2 min)  suite + verifiers + coverage
./scripts/verify_all.sh --full   # full  (~25 min) adds stress + mutation
```

### What it checks

| Group | Checks |
|---|---|
| Environment | `hypothesis` + `pytest-cov` present (they do **not** persist between sessions) |
| Test suites | Unit 3,201 · stress 128 (`--full`) |
| Coverage | ≥95% per module gate |
| Phase 1 gates | closure 60 · exit 94 · task 26 |
| Architecture verifiers | 43 + 52 + 64 + 76 + 77 + 93 |
| Phase 2 verifiers | source model 38 |
| Probes | cascade partial retraction 9/9 |
| Mutation (`--full`) | source 21/21 · cascade 19/20 |
| Source integrity (`--full`) | no mutation residue left in `oip/` |

**Expected result: 13 passed, 0 failed** (fast mode).

### Exit codes

`0` all passed · `1` one or more failed

---

## Notes for Maintainers

**Never interrupt a mutation run.** A killed run can leave a mutated source in
place. This caused two phantom "hangs" and one corrupted benchmark during
Phase 1. `--full` mode ends with a residue check (`grep` for `if False:` /
`for _once in`) precisely because that failure mode is easy to miss.

**Benchmark variance is severe** on the two-core host. `verify_all.sh` does not
run benchmarks for this reason — use `make bench` on a verified-idle box, and
*prove* contention with `ps aux` rather than assuming it.

**A verifier failure is as likely to be a bug in the verifier.** During Phase-2
work, 10 of 10 initial verifier failures were checker errors — invented API
names, and two regexes that matched *prose documenting a marker as open*,
asserting the opposite of their intent. Diagnose before "fixing" production
code.

---

## The Symlinks

The repository root and `decisions/` contain symlinks that preserve historical
paths:

| Path | Target | Why |
|---|---|---|
| `/PKP_*.md`, `/CONSTITUTION.md`, `/AGENT-PLAYBOOK.md`, `/P1-EXECUTION-PLAN.md` | `docs/…` | 8 verifiers resolve frozen docs at the repo root |
| `/uploads/PKP_v1_Foundation.txt` | `docs/architecture/…` | Same |
| `/decisions/<ID>.md` (47) | `records/<ID>.md` | `test_calibration.py` reads `S-01-calibration-rubric.md` verbatim to check the rubric against its spec |

**These exist because reorganising the tree broke real checks.** Both breakages
were caught by running the battery in the copied tree — 1 test failure and 10
verifier failures that did not exist in the original.

The alternative was editing frozen Phase-1 tests and verifiers to learn new
paths. Symlinks were chosen instead: the checks stay byte-identical, and the
specification-to-code cross-check they perform keeps working.
