"""Mutation testing for T01.5.5 calibration conformance.

Every rule introduced by this task is broken in turn; the suite must fail.
Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "oip" / "calibration.py"
ENUMS = ROOT / "oip" / "enums.py"
TARGETS = [CAL, ENUMS]

MUTATIONS = [
    # -- band ranges quoted from S-1 ---------------------------------------
    ("M1 WEAK range widened",
     CAL, "        low=0.20,\n        high=0.39,", "        low=0.20,\n        high=0.45,"),
    ("M2 VERY_STRONG range lowered",
     CAL, "        low=0.80,\n        high=1.00,", "        low=0.70,\n        high=1.00,"),
    ("M3 MODERATE range shifted",
     CAL, "        low=0.40,\n        high=0.59,", "        low=0.41,\n        high=0.59,"),
    # -- countable-test attribution ----------------------------------------
    ("M4 VERY_STRONG count changed from 0 to 1",
     CAL,
     '            "affected population is named in the evidence"\n        ),\n        alternative_count=0,',
     '            "affected population is named in the evidence"\n        ),\n        alternative_count=1,'),
    ("M5 MODERATE count changed from 1 to 2",
     CAL,
     '            "behavioural response"\n        ),\n        alternative_count=1,',
     '            "behavioural response"\n        ),\n        alternative_count=2,'),
    ("M6 WEAK count changed from 2 to 3",
     CAL,
     "        alternative_count=2,\n        count_is_minimum=True,",
     "        alternative_count=3,\n        count_is_minimum=True,"),
    ("M7 WEAK stops being a minimum",
     CAL,
     "        alternative_count=2,\n        count_is_minimum=True,",
     "        alternative_count=2,\n        count_is_minimum=False,"),
    ("M8 NEGLIGIBLE given an invented count",
     CAL,
     '            "span unrelated populations"\n        ),\n        alternative_count=None,',
     '            "span unrelated populations"\n        ),\n        alternative_count=3,'),
    ("M9 STRONG given an invented count",
     CAL,
     '        anchor_b="A Fact directly quoted with full qualifying context intact",\n        alternative_count=None,',
     '        anchor_b="A Fact directly quoted with full qualifying context intact",\n        alternative_count=1,'),
    # -- false conformity ---------------------------------------------------
    ("M10 a missing count reports CONFORMANT",
     CAL,
     "            outcome=ConformanceOutcome.UNASSESSED,\n            detail=UNASSESSED_NO_COUNT,",
     "            outcome=ConformanceOutcome.CONFORMANT,\n            detail=UNASSESSED_NO_COUNT,"),
    ("M11 a qualitative band reports CONFORMANT",
     CAL,
     "            outcome=ConformanceOutcome.UNASSESSED,\n            alternative_count=alternative_count,\n            detail=UNASSESSED_QUALITATIVE_BAND,",
     "            outcome=ConformanceOutcome.CONFORMANT,\n            alternative_count=alternative_count,\n            detail=UNASSESSED_QUALITATIVE_BAND,"),
    ("M12 a qualitative band is judged by count anyway",
     CAL,
     "    if not criterion.is_countable:", "    if False:"),
    ("M13 mismatched count reports CONFORMANT",
     CAL,
     "    if criterion.matches_count(alternative_count):",
     "    if True:"),
    ("M14 deviations never detected (matches_count always true)",
     CAL,
     "        if self.count_is_minimum:\n            return count >= self.alternative_count\n        return count == self.alternative_count",
     "        return True"),
    ("M15 assessed treats UNASSESSED as assessed",
     CAL,
     "        return self.outcome is not ConformanceOutcome.UNASSESSED",
     "        return True"),
    ("M16 conformant true for any non-deviation",
     CAL,
     "        return self.outcome is ConformanceOutcome.CONFORMANT",
     "        return self.outcome is not ConformanceOutcome.DEVIATION"),
    # -- register discipline -------------------------------------------------
    ("M17 register counts UNASSESSED as conformant (drops the counter)",
     CAL,
     "            if not assessment.assessed:\n                self._unassessed += 1\n                return None",
     "            if not assessment.assessed:\n                return None"),
    ("M18 register silently discards deviations",
     CAL,
     "            self._deviations.append(deviation)",
     "            pass"),
    ("M19 register is no longer append-only",
     CAL,
     '    def delete(self, *_args, **_kwargs) -> None:\n        """Never permitted. The register is append-only. [R-1, S-1]"""\n        raise CalibrationError(',
     '    def delete(self, *_args, **_kwargs) -> None:\n        """Never permitted. The register is append-only. [R-1, S-1]"""\n        return None\n        raise CalibrationError('),
    ("M20 register accepts a blank object id",
     CAL,
     '        if not (object_id or "").strip():\n            raise CalibrationError(',
     '        if False:\n            raise CalibrationError('),
    # -- scope: governed component ------------------------------------------
    ("M21 evidential_support becomes governable",
     CAL,
     "    if component != GOVERNED_COMPONENT:\n        raise UngovernedComponentError(",
     "    if False:\n        raise UngovernedComponentError("),
    ("M22 governed component silently switched",
     CAL,
     'GOVERNED_COMPONENT = "assertion_confidence"',
     'GOVERNED_COMPONENT = "effective_confidence"'),
    # -- cross-engine comparability ------------------------------------------
    ("M23 comparability claimed as demonstrated",
     CAL,
     '    def comparability_demonstrated(self) -> bool:\n        """Always False until O2 exists. [S-1, N-3, T08.3.5]',
     '    def comparability_demonstrated(self) -> bool:\n        return True\n        """Always False until O2 exists. [S-1, N-3, T08.3.5]'),
    ("M24 comparison stops being rubric-dependent",
     CAL,
     '    def rubric_dependent(self) -> bool:\n        """Always True. The comparison holds only under S-1. [AC3]"""\n        return True',
     '    def rubric_dependent(self) -> bool:\n        """Always True. The comparison holds only under S-1. [AC3]"""\n        return False'),
    ("M25 comparison drops the qualification",
     CAL,
     "    qualification: str = COMPARABILITY_QUALIFICATION",
     '    qualification: str = ""'),
    ("M26 comparison accepts a non-Engine",
     CAL,
     "        if not isinstance(engine, Engine):\n            raise CalibrationError(f\"expected a known Engine, got {engine!r}\")\n        bands.append",
     "        if False:\n            raise CalibrationError(f\"expected a known Engine, got {engine!r}\")\n        bands.append"),
    # -- input validation -----------------------------------------------------
    ("M27 negative counts accepted",
     CAL,
     "    if alternative_count < 0:\n        raise CalibrationError(",
     "    if False:\n        raise CalibrationError("),
    ("M28 boolean accepted as a count",
     CAL,
     "    if not isinstance(alternative_count, int) or isinstance(\n        alternative_count, bool\n    ):",
     "    if not isinstance(alternative_count, int):"),
    ("M29 contains() ignores the authoritative band",
     CAL,
     "        return ConfidenceBand.for_value(value) is self.band",
     "        return self.low <= value <= self.high"),
    ("M30 contains() accepts out-of-range values",
     CAL,
     "        if not 0.0 <= value <= 1.0:\n            return False",
     "        if False:\n            return False"),
    ("M31 the import-time boundary guard is disabled",
     CAL,
     "        for probe in (criterion.low, criterion.high):\n            if ConfidenceBand.for_value(probe) is not criterion.band:\n                return False",
     "        for probe in (criterion.low, criterion.high):\n            if False:\n                return False"),
    # -- band semantics must not drift ---------------------------------------
    ("M32 ConfidenceBand boundary moved",
     ENUMS, "        if value < 0.80:\n            return cls.STRONG", "        if value < 0.75:\n            return cls.STRONG"),
    ("M33 a sixth band introduced",
     ENUMS, '    VERY_STRONG = "VERY_STRONG"', '    VERY_STRONG = "VERY_STRONG"\n    ABSOLUTE = "ABSOLUTE"'),
]


def run_suite() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_calibration.py", "tests/test_contract.py",
         "tests/test_contract_properties.py", "tests/test_acceptance.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode == 0


def main() -> int:
    targets = list({m[1] for m in MUTATIONS})
    originals = {p: p.read_text() for p in targets}
    backups = {p: ROOT / "validation" / f".{p.name}.orig" for p in targets}
    for p in targets:
        shutil.copy2(p, backups[p])

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        for p in targets:
            p.write_text(originals[p])
        return 1
    print("pass")

    survivors, killed, inapplicable = [], [], []
    for label, path, find, replace in MUTATIONS:
        original = originals[path]
        if find not in original:
            inapplicable.append(label)
            print(f"  ??  {label}: pattern not found")
            continue
        path.write_text(original.replace(find, replace, 1))
        if run_suite():
            survivors.append(label)
            print(f"  SURVIVED  {label}")
        else:
            killed.append(label)
            print(f"  killed    {label}")
        path.write_text(original)

    for p in targets:
        p.write_text(originals[p])

    identical = True
    for p in targets:
        diff = subprocess.run(["diff", "-q", str(p), str(backups[p])],
                              capture_output=True, text=True)
        if diff.returncode != 0:
            identical = False
            print(f"  RESTORE MISMATCH: {p.name}")
        backups[p].unlink()

    print(f"\nkilled {len(killed)}/{len(MUTATIONS)}; survivors {len(survivors)}; "
          f"inapplicable {len(inapplicable)}")
    print(f"sources restored byte-identical: {identical}")
    if survivors or inapplicable or not identical:
        for s in survivors:
            print("  SURVIVOR:", s)
        for s in inapplicable:
            print("  INAPPLICABLE:", s)
        return 1
    print("all mutations killed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
