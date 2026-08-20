"""Architecture verification for T02.1.4 -- the coverage model.

Establishes mechanically that oip/coverage.py supplies exactly what N-22
ratifies and nothing more: the measure is over types never volume, the gap
vocabulary is the closed five-reason set extracted from the N-22 decision
text itself, the out-of-frame register exists (AS-4), no stopping rule
exists, coverage is a report never a gate, and an unavailable frame is
undefined -- never defaulted.

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

from oip import coverage as cov_mod  # noqa: E402
from oip.coverage import (  # noqa: E402
    GAP_REASONS, CoverageReport, GapReason, GapRegister, OutOfFrameRegister,
    coverage_frame, measure_coverage,
)
from oip.source import SourceType, taxonomy_members  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


SRC = (ROOT / "oip" / "coverage.py").read_text()
TREE = ast.parse(SRC)
# Executable code only: docstrings legitimately DISCUSS the boundaries
# (e.g. citing S-02 to state coverage is not its input); prose documenting
# a boundary must not be mistaken for crossing it. Same failure mode the
# Phase-1 closure gate caught and fixed in its own verifiers.
_code_only = ast.parse(SRC)
for _n in ast.walk(_code_only):
    if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and (
        _n.body and isinstance(_n.body[0], ast.Expr)
        and isinstance(_n.body[0].value, ast.Constant)
        and isinstance(_n.body[0].value.value, str)
    ):
        _n.body = _n.body[1:] or [ast.Pass()]
CODE = ast.unparse(_code_only)
N22 = (DOCS / "decisions" / "N-22-coverage-model.md").read_text()

# The ratified reason vocabulary, extracted MECHANICALLY from the N-22
# S 5.4 table (first such table of that section, in table order). The enum
# is proven against the decision text, not against a transcription.
_sec54 = N22.split("### 5.4")[1].split("### 5.5")[0]
_N22_REASONS = re.findall(r"^\|\s*`([A-Z_]+)`\s*\|", _sec54, re.M)
_sec54_flat = re.sub(r"\s+", " ", _sec54)

# ===========================================================================
# A. The ratified vocabulary, exactly
# ===========================================================================
check("A", "GapReason is exactly the N-22 S 5.4 table, in order",
      GAP_REASONS == tuple(_N22_REASONS) and len(_N22_REASONS) == 5,
      f"enum={GAP_REASONS} n22={_N22_REASONS}")
check("A", "UNTYPABLE_CHANNEL is NOT a gap reason",
      "UNTYPABLE_CHANNEL" not in GAP_REASONS
      and "not a gap reason" in _sec54_flat.lower())
check("A", "the reason vocabulary is closed in the decision text",
      "Extension requires a superseding record" in _sec54)
check("A", "NOT_ATTEMPTED and NO_MATERIAL_FOUND stay distinct (N-10)",
      GapReason.NOT_ATTEMPTED is not GapReason.NO_MATERIAL_FOUND)
check("A", "frame is the ratified taxonomy, taken not redefined",
      coverage_frame() == frozenset(taxonomy_members())
      and "taxonomy_members" in SRC
      and "PUBLISHED_EDITORIAL" not in SRC.split('class GapReason')[0])

# ===========================================================================
# B. The measure  [N-22 S 5.2]
# ===========================================================================
_gaps, _oof = GapRegister(), OutOfFrameRegister()
_full = measure_coverage(
    tuple(m.value for m in taxonomy_members()), _gaps, _oof)
_vol = measure_coverage(["VENDOR_PUBLICATION"] * 4, _gaps, _oof)
check("B", "AC1: coverage is measurable (|represented| / |frame|)",
      _full.coverage == 1.0 and _vol.coverage == 0.125
      and _vol.represented == (SourceType.VENDOR_PUBLICATION,))
check("B", "representation is existence, never volume",
      _vol.coverage == 1 / 8)
check("B", "gaps are exactly frame minus represented",
      {g.member for g in _vol.gaps} == coverage_frame() - {
          SourceType.VENDOR_PUBLICATION})
check("B", "volume never appears in the coverage arithmetic",
      "len(active_evidence_types)" not in SRC)
check("B", "coverage does not enter evidential support (S-02 undisturbed)",
      not re.search(r"evidential|assertion_confidence", CODE))

# ===========================================================================
# C. Out-of-frame register  [N-22 S 5.2.1, AS-4]
# ===========================================================================
_oof2 = OutOfFrameRegister()
_oof2.record("src", "mystery-channel", "gate 2 refusal")
_rep = measure_coverage((), GapRegister(), _oof2)
check("C", "out-of-frame refusals are recorded and counted",
      _oof2.count() == 1 and _rep.out_of_frame == 1)
check("C", "out_of_frame is reported beside coverage, never inside it",
      _rep.coverage == 0.0 and _rep.out_of_frame == 1
      and "coverage=len(represented_members) / len(active)" in CODE)
check("C", "full coverage with out_of_frame>0 carries both truths",
      measure_coverage(
          tuple(m.value for m in taxonomy_members()), GapRegister(), _oof2
      ).out_of_frame == 1)
_ok = False
try:
    _oof2.record("src", "VENDOR_PUBLICATION", "typable")
except cov_mod.OutOfFrameError:
    _ok = True
check("C", "typable sources are refused entry to the register", _ok)
check("C", "the register exists beside the report (AS-4 mechanism)",
      hasattr(cov_mod, "OutOfFrameRegister")
      and hasattr(cov_mod, "OutOfFrameRefusal"))

# ===========================================================================
# D. Declared completeness  [N-22 S 5.3, S 5.4]
# ===========================================================================
_reg = GapRegister()
for m in taxonomy_members():
    _reg.declare(m, GapReason.OUT_OF_SCOPE, "directive excludes it")
_dec = measure_coverage((), _reg, OutOfFrameRegister())
check("D", "AC2: gaps are declared explicitly with a closed reason",
      _dec.declared_complete is True
      and all(g.declaration.reason in set(GapReason) for g in _dec.gaps))
_part = GapRegister()
for m in list(taxonomy_members())[:-1]:
    _part.declare(m, GapReason.NOT_ATTEMPTED, "not attempted")
_rep2 = measure_coverage((), _part, OutOfFrameRegister())
check("D", "one undeclared gap makes the report incomplete",
      _rep2.declared_complete is False
      and len(_rep2.undeclared_gaps) == 1)
check("D", "declarations carry a mandatory rationale",
      "rationale" in SRC and "requires a rationale" in SRC)
check("D", "declaration history is retained (append-only register)",
      hasattr(GapRegister, "history_for"))

# ===========================================================================
# E. AC3 -- inheritable by Pattern artefact assessment  [J4/J5]
# ===========================================================================
check("E", "AC3: operative declarations are inheritable, typed records",
      len(_dec.inheritable_declarations()) == 8
      and all(
          d.rationale and isinstance(d.reason, GapReason)
          for d in _dec.inheritable_declarations()
      ))
check("E", "the report is the inheritance surface PT-V5 will consume",
      hasattr(CoverageReport, "inheritable_declarations"))

# ===========================================================================
# F. No stopping rule; report not gate; undefined frame  [S 5.5-S 5.7]
# ===========================================================================
check("F", "no stopping rule exists (M-01 stays open)",
      not re.search(r"def .*(stop|enough|should_stop)", SRC, re.I)
      and "NO stopping rule" in SRC)
check("F", "coverage is a report, not a gate",
      not re.search(r"def .*(reject|accept_object|deny)", SRC, re.I)
      and "rejects no object" in SRC.lower())
check("F", "an unavailable frame is undefined, never 0 or 1",
      measure_coverage((), GapRegister(), OutOfFrameRegister(),
                       frame=frozenset()).coverage is None)
check("F", "S-04 is untouched (no sufficiency logic here)",
      not re.search(r"sufficien|threshold|floor", CODE, re.I))

# ===========================================================================
# G. Module conventions and boundaries
# ===========================================================================
imports = {
    n.module for n in ast.walk(TREE)
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("G", "module imports only oip.contract and oip.source",
      imports <= {"oip.contract", "oip.source"}, str(sorted(imports)))
check("G", "no store, graph or acceptance import (Tier 2 boundary)",
      not (imports & {"oip.store", "oip.graph", "oip.acceptance",
                      "oip.evidence"}))
check("G", "records are frozen dataclasses [R-1]",
      SRC.count("@dataclass(frozen=True)") >= 3)
check("G", "registers are lock-guarded [N-11]", "threading.RLock" in SRC)
check("G", "module header names its task",
      re.search(r"Task: T02\.1\.4", SRC) is not None)
check("G", "module does not claim to close a marker",
      not re.search(r"\bCloses\s*[:|]\s*M-\d+", SRC))
check("G", "production module count is now 33 (incl. duplicates)",
      len(list((ROOT / "oip").glob("*.py"))) == 33,
      f"{len(list((ROOT / 'oip').glob('*.py')))} modules")
check("G", "Phase 1 modules unchanged",
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
    "A": "Ratified vocabulary, exactly",
    "B": "The measure (types, never volume)",
    "C": "Out-of-frame register (AS-4)",
    "D": "Declared completeness",
    "E": "Inheritability (PT-V5 surface)",
    "F": "No stopping rule; report not gate; undefined frame",
    "G": "Conventions and boundaries",
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
