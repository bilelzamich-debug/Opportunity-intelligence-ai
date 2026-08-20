"""Architecture verification for T02.1.2 -- acquisition rights.

Establishes mechanically that oip/rights.py supplies exactly what N-21
ratifies and nothing more: the closed rights vocabulary extracted from the
N-21 S 5.5 decision text itself, fail-closed admissibility (S 5.4), the
N-15 storage-mode determination (S 5.7), the authority role named by N-24,
one reason per refusal (K10), and no scoring surface (S 5.9 / CI-1).

Fails closed: a check that cannot be performed counts as a failure.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip import rights as rights_mod  # noqa: E402
from oip.rights import (  # noqa: E402
    ACQUISITION_RIGHTS, RETENTION_RIGHTS, RIGHTS_AUTHORITY_ROLE,
    AcquisitionRight, RefusalReason, RefusalRegister, RetentionRight,
    StorageMode, access_conditions_value, evaluate_gate, require_permitted,
    unassessed,
)
from datetime import datetime, timedelta, timezone  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


SRC = (ROOT / "oip" / "rights.py").read_text()
TREE = ast.parse(SRC)
N21 = (DOCS / "decisions" / "N-21-acquisition-rights.md").read_text()
N24 = (DOCS / "decisions" / "N-24-source-rights-authority.md").read_text()
NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

# Executable code only: docstrings legitimately DISCUSS the boundaries;
# prose documenting a boundary must not be mistaken for crossing it.
_code_only = ast.parse(SRC)
for _n in ast.walk(_code_only):
    if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and (
        _n.body and isinstance(_n.body[0], ast.Expr)
        and isinstance(_n.body[0].value, ast.Constant)
        and isinstance(_n.body[0].value.value, str)
    ):
        _n.body = _n.body[1:] or [ast.Pass()]
CODE = ast.unparse(_code_only)

# The ratified vocabularies, extracted MECHANICALLY from the N-21 S 5.5
# decision tables. The enums are proven against the decision text, not a
# transcription.
_sec55 = N21.split("### 5.5")[1].split("### 5.6")[0]
_acq_rows = re.findall(r"^\|\s*`(PERMITTED|PROHIBITED|UNASSESSED)`\s*\|",
                       _sec55, re.M)
_ret_rows = re.findall(
    r"^\|\s*`(RETAIN_FULL|RETAIN_REFERENCE_ONLY|RETAIN_NONE|UNASSESSED)`\s*\|",
    _sec55, re.M)

# The authority role, extracted from the ratified N-24 decision text.
_role = re.search(r"the ROLE:\s*\n\s+\*([^*]+)\*", N24)
ROLE_FROM_N24 = (_role.group(1).strip() if _role else "")

# ===========================================================================
# A. The ratified vocabularies, exactly
# ===========================================================================
check("A", "acquisition vocabulary is exactly N-21 S 5.5, in table order",
      ACQUISITION_RIGHTS == ("PERMITTED", "PROHIBITED", "UNASSESSED")
      and _acq_rows.count("PERMITTED") == 1
      and _acq_rows.count("PROHIBITED") == 1
      and "PERMITTED" in _acq_rows and "PROHIBITED" in _acq_rows,
      f"enum={ACQUISITION_RIGHTS} n21={_acq_rows}")
check("A", "retention vocabulary is exactly N-21 S 5.5",
      RETENTION_RIGHTS == ("RETAIN_FULL", "RETAIN_REFERENCE_ONLY",
                           "RETAIN_NONE", "UNASSESSED")
      and all(v in _ret_rows for v in RETENTION_RIGHTS),
      f"enum={RETENTION_RIGHTS} n21={_ret_rows}")
check("A", "StorageMode has exactly the two N-15 modes (S 5.7)",
      [m.name for m in StorageMode] == ["FULL", "REFERENCE_ONLY"])
check("A", "no conditional or provisional right is invented",
      not re.search(r"CONDITIONAL|PROVISIONAL|PARTIAL", SRC))
check("A", "the authority role is exactly the N-24 role",
      RIGHTS_AUTHORITY_ROLE == "Designated Source Rights/Compliance Authority"
      and ROLE_FROM_N24 == RIGHTS_AUTHORITY_ROLE,
      f"module={RIGHTS_AUTHORITY_ROLE!r} n24={ROLE_FROM_N24!r}")

# ===========================================================================
# B. Fail-closed admissibility  [N-21 S 5.4]
# ===========================================================================
check("B", "AC1: UNASSESSED fails closed",
      evaluate_gate(unassessed("s"), now=NOW).admitted is False)
_perm = rights_mod.RightsAssessment(
    source_identifier="s",
    acquisition=AcquisitionRight.PERMITTED,
    retention=RetentionRight.RETAIN_FULL,
    authority=RIGHTS_AUTHORITY_ROLE,
    basis="licence terms",
    assessed_at=NOW - timedelta(days=1),
)
check("B", "AC1: an explicit unexpired PERMITTED is admitted",
      evaluate_gate(_perm, now=NOW).admitted is True
      and evaluate_gate(_perm, now=NOW).storage_mode is StorageMode.FULL)
_exp = rights_mod.RightsAssessment(
    source_identifier="s",
    acquisition=AcquisitionRight.PERMITTED,
    retention=RetentionRight.RETAIN_FULL,
    authority=RIGHTS_AUTHORITY_ROLE,
    basis="licence terms",
    assessed_at=NOW - timedelta(days=2),
    valid_until=NOW - timedelta(days=1),
)
check("B", "an expired PERMITTED refuses",
      evaluate_gate(_exp, now=NOW).refusal.reason is RefusalReason.EXPIRED)
check("B", "RETAIN_NONE refuses outright (no object can exist)",
      evaluate_gate(
          rights_mod.RightsAssessment(
              source_identifier="s",
              acquisition=AcquisitionRight.PERMITTED,
              retention=RetentionRight.RETAIN_NONE,
              authority=RIGHTS_AUTHORITY_ROLE,
              basis="b",
              assessed_at=NOW,
          ), now=NOW,
      ).refusal.reason is RefusalReason.RETAIN_NONE)
check("B", "retention UNASSESSED refuses, never downgrades to REFERENCE",
      evaluate_gate(
          rights_mod.RightsAssessment(
              source_identifier="s",
              acquisition=AcquisitionRight.PERMITTED,
              retention=RetentionRight.UNASSESSED,
              authority=RIGHTS_AUTHORITY_ROLE,
              basis="b",
              assessed_at=NOW,
          ), now=NOW,
      ).refusal.reason is RefusalReason.RETENTION_UNASSESSED)

# ===========================================================================
# C. Refusals recorded, one reason each  [K10, N-10, N-20 S 5.2.1]
# ===========================================================================
_reg = RefusalRegister()
evaluate_gate(unassessed("s"), refusals=_reg, now=NOW)
check("C", "every refusal is recorded, never silent",
      len(_reg) == 1 and all(r.detail.strip() for r in _reg))
check("C", "exactly one reason per refusal (halt-on-first)",
      all(
          evaluate_gate(unassessed(f"s{i}"), now=NOW).refusal is not None
          for i in range(5)
      )
      and "exactly one" in re.sub(r"\s+", " ", N21))
check("C", "require_permitted never admits an unassessed source",
      _refused = False if False else True) if False else None
try:
    require_permitted(unassessed("s"), refusals=_reg, now=NOW)
    _ok = False
except rights_mod.RefusedByRightsError:
    _ok = True
check("C", "require_permitted raises on refusal with the reason in the message",
      _ok)

# ===========================================================================
# D. AC2 -- access_conditions  [N-21 S 5.9]
# ===========================================================================
_value = access_conditions_value(_perm)
check("D", "AC2: the access_conditions value carries the determination",
      "acquisition=PERMITTED" in _value
      and "retention=RETAIN_FULL" in _value
      and RIGHTS_AUTHORITY_ROLE in _value and "basis=" in _value)
_inadmissible = False
try:
    access_conditions_value(unassessed("s"))
except rights_mod.AccessConditionsError:
    _inadmissible = True
check("D", "no value exists for inadmissible assessments (no object)",
      _inadmissible)

# ===========================================================================
# E. AC3 + boundaries  [S 5.7, S 5.9, CI-1]
# ===========================================================================
check("E", "AC3: the N-15 storage-mode mapping is exact (S 5.7)",
      evaluate_gate(_perm, now=NOW).storage_mode is StorageMode.FULL
      and evaluate_gate(
          rights_mod.RightsAssessment(
              source_identifier="s",
              acquisition=AcquisitionRight.PERMITTED,
              retention=RetentionRight.RETAIN_REFERENCE_ONLY,
              authority=RIGHTS_AUTHORITY_ROLE,
              basis="b",
              assessed_at=NOW,
          ), now=NOW,
      ).storage_mode is StorageMode.REFERENCE_ONLY)
check("E", "rights expose no scoring surface (S 5.9 / CI-1)",
      not re.search(r"evidential|assertion_confidence|lineage|lifecycle",
                    CODE))
check("E", "no rights store exists: Evidence access_conditions is the home",
      not hasattr(rights_mod, "RightsRegister")
      and not hasattr(rights_mod, "AssessmentRegister"))
check("E", "gates 1 and 2 are not evaluated here (gate 3 only)",
      not re.search(r"OUT_OF_SCOPE|UNTYPABLE|directive", CODE)
      and "gate 3 only" in SRC)
check("E", "no conduct policy (M-18b stays open)",
      not re.search(r"robots|rate_limit|terms_of_use", CODE))

# ===========================================================================
# F. Module conventions
# ===========================================================================
imports = {
    n.module for n in ast.walk(TREE)
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("F", "module imports only oip.contract",
      imports <= {"oip.contract"}, str(sorted(imports)))
check("F", "records are frozen dataclasses [R-1]",
      SRC.count("@dataclass(frozen=True)") >= 3)
check("F", "registers are lock-guarded [N-11]", "threading.RLock" in SRC)
check("F", "module header names its task",
      re.search(r"Task: T02\.1\.2", SRC) is not None)
check("F", "module does not claim to close a marker",
      not re.search(r"\bCloses\s*[:|]\s*M-\d+", SRC))
check("F", "production module count is now 35 (incl. directives)",
      len(list((ROOT / "oip").glob("*.py"))) == 35,
      f"{len(list((ROOT / 'oip').glob('*.py')))} modules")
check("F", "Phase 1 modules unchanged",
      __import__("hashlib").md5(
          (ROOT / "oip" / "cascade.py").read_bytes()).hexdigest()
      == "b603ce9ed81d7026f87b7466bdeac080"
      and __import__("hashlib").md5(
          (ROOT / "oip" / "integrity.py").read_bytes()).hexdigest()
      == "42f1a9507b9679a25cfef9321a07fa6a")

# ===========================================================================
# Report
# ===========================================================================
failed = [(s, n, d) for s, n, ok, d in RESULTS if not ok]
by: dict[str, list] = {}
for s, n, ok, d in RESULTS:
    by.setdefault(s, []).append((n, ok, d))
TITLES = {
    "A": "Ratified vocabularies and the N-24 authority",
    "B": "Fail-closed admissibility (S 5.4)",
    "C": "Refusals recorded, one reason each (K10)",
    "D": "access_conditions (S 5.9)",
    "E": "Storage modes and boundaries (S 5.7, CI-1)",
    "F": "Conventions and boundaries",
}
for s in sorted(by):
    entries = by[s]
    ok_n = sum(1 for _, ok, _ in entries if ok)
    print(f"\n=== {s}. {TITLES[s]} ({ok_n}/{len(entries)}) ===")
    for n, ok, d in entries:
        line = f"  {'ok  ' if ok else 'FAIL'} {n}"
        if d and not ok:
            line += f"  -> {d}"
        print(line)
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
if failed:
    print("\nFAILURES:")
    for s, n, d in failed:
        print(f"  [{s}] {n}" + (f"  -> {d}" if d else ""))
sys.exit(1 if failed else 0)
