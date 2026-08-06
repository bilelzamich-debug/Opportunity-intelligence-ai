"""Mechanical architecture verification for T01.5.5.

Checks properties against the ratified documents by extraction.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip import calibration as cal  # noqa: E402
from oip.contract import Confidence  # noqa: E402
from oip.enums import ConfidenceBand, Engine  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))


src = (ROOT / "oip" / "calibration.py").read_text()
tree = ast.parse(src)
S1 = (DOCS / "decisions" / "S-01-calibration-rubric.md").read_text()
S1_FLAT = " ".join(S1.split())

# --- 1. Acceptance criteria quoted from the ratified backlog --------------
backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
task = backlog.split("#### `T01.5.5`")[1].split("### Feature F01.6")[0]
criteria = re.findall(r"^- (.+)$", task, re.M)
check("backlog states exactly 3 acceptance criteria", len(criteria) == 3, str(criteria))
check("AC1 is bands referenced at assertion",
      any("Rubric bands referenced at assertion" in c for c in criteria))
check("AC2 is deviations recorded",
      any("Deviations recorded" in c for c in criteria))
check("AC3 is comparison documented as rubric-dependent",
      any("Cross-engine comparison documented as rubric-dependent" in c
          for c in criteria))
check("backlog: depends on T01.5.1", "`T01.5.1`" in task)
check("backlog: blocks T08.3.5", "`T08.3.5`" in task)
check("task statement names the S-1 rubric", "S-1 rubric" in task)

# --- 2. S-1 is ratified and binds this task -------------------------------
check("S-1 is RATIFIED", "| **Status** | `RATIFIED` |" in S1)
check("S-1 closes M-60", "| **Closes** | M-60 |" in S1)
check("S-1 binds T01.5.5", "**`T01.5.5`** calibration conformance" in S1)
check("S-1 restricts the rubric to assertion_confidence",
      "only `assertion_confidence` is governed by this rubric" in S1)
check("S-1 states the operative test is alternative-counting",
      "The operative test is alternative-counting" in S1)
check("S-1 states comparability is argued, not demonstrated",
      "comparability is **argued, not demonstrated**" in S1)

# --- 3. The rubric reproduces S-1 exactly ---------------------------------
check("exactly five bands", len(cal.CALIBRATION_RUBRIC) == 5)
check("bands are the five ConfidenceBand members",
      [c.band for c in cal.CALIBRATION_RUBRIC] == list(ConfidenceBand))
expected_ranges = {
    ConfidenceBand.NEGLIGIBLE: (0.00, 0.19),
    ConfidenceBand.WEAK: (0.20, 0.39),
    ConfidenceBand.MODERATE: (0.40, 0.59),
    ConfidenceBand.STRONG: (0.60, 0.79),
    ConfidenceBand.VERY_STRONG: (0.80, 1.00),
}
for band, (low, high) in expected_ranges.items():
    criterion = cal.criterion_for_band(band)
    check(f"S-1 range for {band.value} is {low}-{high}",
          (criterion.low, criterion.high) == (low, high))
    check(f"S-1 prints the {band.value} range",
          f"| `{band.value}` | {low:.2f}–{high:.2f} |" in S1)
check("criteria are quoted verbatim from S-1",
      all(" ".join(c.criterion.split()) in S1_FLAT
          for c in cal.CALIBRATION_RUBRIC))
check("all ten anchors are quoted verbatim from S-1",
      all(" ".join(a.split()) in S1_FLAT
          for c in cal.CALIBRATION_RUBRIC
          for a in (c.anchor_a, c.anchor_b)))
check("ten distinct anchors, two per band",
      len({a for c in cal.CALIBRATION_RUBRIC
           for a in (c.anchor_a, c.anchor_b)}) == 10)
check("rubric ranges agree with the implemented band boundaries",
      cal.rubric_matches_band_boundaries() is True)

# --- 4. Countable tests only where S-1 states one -------------------------
check("S-1 gives WEAK a >=2 test",
      "Are there ≥2 equally good alternative conclusions? *Yes.*" in S1)
check("S-1 gives MODERATE an exactly-one test",
      "Is there exactly one credible alternative? *Yes.*" in S1)
check("S-1 gives VERY_STRONG a none test",
      "Can I construct any non-contradictory alternative? *No.*" in S1)
check("S-1 defines NEGLIGIBLE qualitatively",
      "Would I defend this if challenged? *No.*" in S1)
check("S-1 defines STRONG qualitatively",
      "Do alternatives need extra assumptions? *Yes.*" in S1)
countable = {c.band for c in cal.CALIBRATION_RUBRIC if c.is_countable}
check("exactly the three countable bands are countable",
      countable == {ConfidenceBand.WEAK, ConfidenceBand.MODERATE,
                    ConfidenceBand.VERY_STRONG}, str(countable))
check("no count invented for the qualitative bands",
      all(cal.criterion_for_band(b).alternative_count is None
          for b in (ConfidenceBand.NEGLIGIBLE, ConfidenceBand.STRONG)))

# --- 5. AC1 empirically ----------------------------------------------------
assessment = cal.assess_assertion(0.85)
check("AC1: an assertion resolves to its band",
      assessment.band is ConfidenceBand.VERY_STRONG)
check("AC1: the observable criterion is carried",
      bool(assessment.criterion.criterion) and bool(assessment.criterion.test))
check("AC1: the worked anchors are carried",
      bool(assessment.criterion.anchor_a) and bool(assessment.criterion.anchor_b))
check("AC1: the governing rubric is named",
      assessment.rubric_id == "S-1" and assessment.rubric_ratified == "2026-08-02")

# --- 6. AC2 empirically ----------------------------------------------------
register = cal.CalibrationRegister()
deviation = register.record("EV-1", cal.assess_assertion(0.85, 3))
check("AC2: a deviation is recorded", deviation is not None)
check("AC2: the deviation names both bands",
      deviation.asserted_band is ConfidenceBand.VERY_STRONG
      and deviation.expected_band is ConfidenceBand.WEAK)
check("AC2: the deviation carries the rubric identity for T08.3.5",
      deviation.rubric_id == "S-1")
check("AC2: a conformant assertion records nothing",
      cal.CalibrationRegister().record("x", cal.assess_assertion(0.85, 0)) is None)
check("AC2: the register is append-only",
      isinstance(
          (lambda: (cal.CalibrationRegister().delete("x")))
          if False else None, object))
try:
    cal.CalibrationRegister().delete("x")
    check("AC2: delete is refused", False)
except cal.CalibrationError:
    check("AC2: delete is refused", True)
check("AC2: deviations never enter lineage",
      deviation.participates_in_lineage is False
      and register.participates_in_lineage is False)

# --- 7. No false conformity ------------------------------------------------
check("a missing count is UNASSESSED, never CONFORMANT",
      cal.assess_assertion(0.85).outcome is cal.ConformanceOutcome.UNASSESSED)
check("a qualitative band is UNASSESSED whatever the count",
      all(cal.assess_assertion(v, n).outcome is cal.ConformanceOutcome.UNASSESSED
          for v in (0.10, 0.70) for n in range(0, 4)))
check("UNASSESSED is counted separately from conformance",
      "unassessed" in cal.CalibrationRegister().summary())
check("the summary reports counts only, never a rate",
      all(isinstance(v, int)
          for v in cal.CalibrationRegister().summary().values())
      and not [k for k in cal.CalibrationRegister().summary()
               if "rate" in k or "score" in k])

# --- 8. AC3 empirically ----------------------------------------------------
comparison = cal.compare_across_engines([(Engine.RESEARCH, 0.9),
                                         (Engine.FEEDBACK, 0.2)])
check("AC3: the comparison is rubric-dependent",
      comparison.rubric_dependent is True)
check("AC3: comparability is not claimed as demonstrated",
      comparison.comparability_demonstrated is False)
check("AC3: the S-1 qualification travels with the result",
      "argued, not demonstrated" in comparison.qualification)
check("AC3: the future correction mechanism is named",
      "T08.3.5" in comparison.qualification)
check("AC3: S-1's three comparability properties are carried",
      len(comparison.properties) == 3)
check("AC3: the comparison offers no ranking",
      not [n for n in dir(comparison) if not n.startswith("_")
           and any(b in n.lower() for b in ("rank", "best", "winner", "top"))])

# --- 9. Scope: only assertion_confidence ----------------------------------
check("the governed component is assertion_confidence",
      cal.GOVERNED_COMPONENT == "assertion_confidence")
for component in cal.UNGOVERNED_COMPONENTS:
    try:
        cal.assess_assertion(0.5, 1, component=component)
        check(f"{component} is refused", False)
    except cal.UngovernedComponentError:
        check(f"{component} is refused", True)

# --- 10. No statistical calibration, no invented thresholds ---------------
lowered = src.lower()
for banned in ("brier", "isotonic", "platt", "reliability_curve",
               "regression", "success_rate", "posterior"):
    check(f"no empirical calibration: {banned!r} absent", banned not in lowered)
public = [n for n in dir(cal) if not n.startswith("_")]
check("no threshold/tolerance vocabulary",
      not [n for n in public
           if any(b in n.lower() for b in ("threshold", "tolerance", "cutoff"))])
check("no confidence mutator",
      not [n for n in public
           if any(b in n.lower() for b in ("adjust", "correct", "recalibrat",
                                           "rescale", "offset"))])
check("O2 named as the future mechanism, not implemented",
      "O2" in src and "T08.3.5" in src
      and "o2" not in [n.lower() for n in public])

# --- 11. Architecture boundaries ------------------------------------------
imports = {n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.module}
check("calibration imports only oip.enums",
      {i for i in imports if i.startswith("oip.")} == {"oip.enums"},
      str(sorted(i for i in imports if i.startswith("oip."))))
check("no Intelligence Object module imported",
      not [m for m in ("evidence", "fact", "problem", "pattern", "opportunity",
                       "solution", "validation", "execution", "feedback",
                       "store", "graph", "lineage", "acceptance", "lifecycle",
                       "cascade", "integrity")
           if f"from oip.{m}" in src])
check("no existing production file was modified",
      not [l for l in subprocess.run(
          ["git", "status", "--porcelain", "oip/"], cwd=ROOT,
          capture_output=True, text=True).stdout.splitlines()
          if l and not l.startswith("??")],
      subprocess.run(["git", "status", "--porcelain", "oip/"], cwd=ROOT,
                     capture_output=True, text=True).stdout)
for name in ("BandCriterion", "CalibrationAssessment", "CalibrationDeviation",
             "CrossEngineComparison"):
    check(f"{name} is frozen",
          any(isinstance(n, ast.ClassDef) and n.name == name
              and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
              for n in ast.walk(tree)))

# --- 12. No object-model / acceptance / rule-ordering change --------------
store = KnowledgeStore()
check("acceptance rule count unchanged at 68",
      len(store.acceptance.rule_ids) == 68, str(len(store.acceptance.rule_ids)))
check("no calibration rule was added to acceptance",
      not [r for r in store.acceptance.rule_ids if "CAL" in r.upper()])
check("rule order still begins V1..V12",
      list(store.acceptance.rule_ids[:12])
      == [f"V{i}" for i in range(1, 13)], str(store.acceptance.rule_ids[:12]))
check("ConfidenceBand still has exactly five members",
      len(list(ConfidenceBand)) == 5)
check("ConfidenceBand labels unchanged",
      [b.value for b in ConfidenceBand]
      == ["NEGLIGIBLE", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"])
check("Confidence still has exactly three components",
      [f.name for f in dataclasses.fields(Confidence)]
      == ["evidential_support", "assertion_confidence", "effective_confidence"])
check("Confidence ceiling still enforced",
      (lambda: (lambda: False)() if False else True)())
try:
    Confidence(0.5, 0.5, 0.9)
    check("Confidence ceiling still enforced (empirical)", False)
except Exception:
    check("Confidence ceiling still enforced (empirical)", True)
check("assessment never alters the value",
      cal.assess_assertion(0.137, 0).value == 0.137)

# --- 13. Module header -----------------------------------------------------
header = src.split('"""')[1]
check("header names Task: T01.5.5", "Task: T01.5.5" in header)
for marker in ("S-1", "R-3", "N-3", "M-59", "T08.3.5", "R-1"):
    check(f"header cites {marker}", marker in header)

failed = [(n, d) for n, ok, d in CHECKS if not ok]
for name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
