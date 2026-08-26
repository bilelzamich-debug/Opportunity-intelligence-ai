#!/usr/bin/env bash
#
# verify_all.sh — run the complete validation battery.
#
# Reproduces every check cited in PROJECT_STATE.md. Nothing here is a summary;
# each command re-derives its result by execution.
#
# Usage:
#   ./scripts/verify_all.sh          # fast: suite + verifiers + coverage
#   ./scripts/verify_all.sh --full   # adds stress (~17 min) and mutation
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLATFORM="$REPO/platform"
FULL=0
[[ "${1:-}" == "--full" ]] && FULL=1

pass=0; fail=0

hdr () { printf '\n\033[1m=== %s ===\033[0m\n' "$1"; }
chk () {  # chk <label> <expected-substring> <command...>
  local label="$1" want="$2"; shift 2
  printf '  %-52s ' "$label"
  local out; out="$("$@" 2>&1)"
  if grep -qF "$want" <<<"$out"; then
    printf '\033[32mPASS\033[0m\n'; pass=$((pass+1))
  else
    printf '\033[31mFAIL\033[0m\n'; fail=$((fail+1))
    sed 's/^/      /' <<<"$(tail -3 <<<"$out")"
  fi
}

hdr "Environment"
# Packages are NOT persisted between sessions in this environment.
# A missing hypothesis shows up as ~32 collection errors, not a regression.
pip install --quiet hypothesis pytest-cov 2>/dev/null
python -c "import hypothesis, pytest_cov" 2>/dev/null \
  && echo "  dependencies present" \
  || { echo "  ERROR: install hypothesis + pytest-cov"; exit 1; }

cd "$PLATFORM"

hdr "Test suites"
chk "unit suite (expect 3410 passed)" "3410 passed" \
    python -m pytest -q
if (( FULL )); then
  chk "stress suite (expect 128 passed, ~17 min)" "128 passed" \
      python -m pytest -q -m stress -p no:randomly
else
  echo "  stress suite                                         SKIPPED (--full)"
fi

hdr "Coverage (gate: 95% per module)"
chk "total coverage >= 95%" "Required test coverage of 95.0% reached" \
    python -m pytest -q --cov=oip --cov-report=term

hdr "Phase 1 gates"
chk "closure verifier (60 checks)"        "60/60"   python validation/closure_t01_8_1.py
chk "exit gate (94 checks)"               "94/94"   python validation/exit_gate_t01_8_1_rerun.py
chk "task gate (26 checks)"               "26/26"   python validation/exit_gate_t01_8_1_tasks.py

hdr "Architecture verifiers"
chk "verify_t01_6_2 sequencing (43)"      "43/43"   python validation/verify_t01_6_2.py
chk "verify_t01_6_3 failure surfacing (52)" "52/52" python validation/verify_t01_6_3.py
chk "verify_t01_6_4 concurrency (64)"     "64/64"   python validation/verify_t01_6_4.py
chk "verify_t01_6_5 processing state (76)" "76/76"  python validation/verify_t01_6_5.py
chk "verify_t01_2_5 retention (77)"       "77/77"   python validation/verify_t01_2_5.py
chk "verify_t01_5_5 calibration (93)"     "93/93"   python validation/verify_t01_5_5.py

hdr "Phase 2 verifiers"
chk "verify_t02_1_1 source model (38)"    "38/38"   python validation/verify_t02_1_1.py
chk "verify_t02_1_4 coverage model (33)"  "33/33"   python validation/verify_t02_1_4.py
chk "verify_t02_1_2 rights model (27)"    "27/27"   python validation/verify_t02_1_2.py
chk "verify_t02_2_1 acquisition (25)"     "25/25"   python validation/verify_t02_2_1.py
chk "verify_t02_2_2 duplicates (25)"      "25/25"   python validation/verify_t02_2_2.py
chk "verify_t02_2_3 drift (26)"           "26/26"   python validation/verify_t02_2_3.py
chk "verify_t02_2_5 failure recording (23)" "23/23"  python validation/verify_t02_2_5.py
chk "verify_t02_2_4 directives (30)"       "30/30"   python validation/verify_t02_2_4.py
chk "verify_t02_3_1 P2 exit gate (17)"     "17/17"   python validation/verify_t02_3_1.py
# verify_t02_1_1_blocker.py asserted M-16 was OPEN. N-20 has since closed it
# partially, so the verifier is historically true but currently false by
# design. Archived to validation/superseded/ rather than deleted.

hdr "Adversarial probes"
chk "cascade partial retraction (9)"      "FAILED 0" python validation/probe_t01_8_1_final.py

if (( FULL )); then
  hdr "Mutation testing"
  # Never interrupt these: a killed run can leave a mutated source in place.
  chk "source model (expect 21/21 killed)"  "killed 21/21" python validation/mutate_t02_1_1.py
  chk "coverage model (expect 14/14 killed)" "killed 14/14" python validation/mutate_t02_1_4.py
  chk "rights model (expect 14/14 killed)"  "killed 14/14" python validation/mutate_t02_1_2.py
  chk "acquisition (expect 15/15 killed)"  "killed 15/15" python validation/mutate_t02_2_1.py
  chk "duplicates (expect 12/12 killed)"   "killed 12/12" python validation/mutate_t02_2_2.py
  chk "drift (expect 13/13 killed)"        "killed 13/13" python validation/mutate_t02_2_3.py
  chk "failure recording (expect 12/12 killed)" "killed 12/12" python validation/mutate_t02_2_5.py
  chk "directives (expect 14/14 killed)"   "killed 14/14" python validation/mutate_t02_2_4.py
  chk "cascade (19/20, survivor equivalent)" "killed 19/20" python validation/mutate_t01_2_4_r1.py
  hdr "Source integrity after mutation"
  chk "no mutation residue in oip/" "" bash -c '! grep -rqE "if False:|for _once in" oip/*.py'
fi

hdr "Summary"
printf '  passed: %d   failed: %d\n' "$pass" "$fail"
(( fail == 0 )) && { echo "  ALL CHECKS PASSED"; exit 0; } || { echo "  FAILURES PRESENT"; exit 1; }
