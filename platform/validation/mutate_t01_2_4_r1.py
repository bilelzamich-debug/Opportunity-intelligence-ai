"""Mutation testing for T01.2.4-R1 partial retraction.

Every rule of the ratified boundary is broken in turn; the suite must fail.
Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAS = ROOT / "oip" / "cascade.py"
INT = ROOT / "oip" / "integrity.py"

MUTATIONS = [
    # -- the partial-retraction boundary itself -----------------------------
    ("M1 partial retraction removed entirely (invalidate everything)",
     CAS, "                if self._retains_valid_upstream(stored, doomed):\n                    continue",
     "                if False:\n                    continue"),
    ("M2 partial retraction always applies (invalidate nothing)",
     CAS, "                if self._retains_valid_upstream(stored, doomed):\n                    continue",
     "                if True:\n                    continue"),
    ("M3 predicate always reports retention",
     CAS, "            if upstream.status not in CASCADE_TRIGGERS:\n                return True\n        return False",
     "            return True\n        return False"),
    ("M4 predicate never reports retention",
     CAS, "            if upstream.status not in CASCADE_TRIGGERS:\n                return True\n        return False",
     "            pass\n        return False"),
    # -- the doomed set (same-cascade condemnation) -------------------------
    ("M5 doomed set ignored: a condemned upstream still attests",
     CAS, "            if reference in doomed:\n                # Already withdrawn, or about to be by this cascade.\n                continue",
     "            if False:\n                continue"),
    ("M6 doomed set not seeded with the origin",
     CAS, "        doomed: set[str] = {origin_id}", "        doomed: set[str] = set()"),
    ("M7 doomed set never extended as dependents are condemned",
     CAS, "                doomed_dependents.add(object_id)\n                doomed.add(object_id)",
     "                doomed_dependents.add(object_id)"),
    # -- withdrawal vocabulary ----------------------------------------------
    ("M8 SUPERSEDED wrongly treated as withdrawal",
     CAS, "            if upstream.status not in CASCADE_TRIGGERS:",
     "            if upstream.status.is_terminal is False:"),
    ("M9 an unresolvable upstream wrongly counted as attesting",
     CAS, "            if upstream is None:\n                # An unresolvable reference cannot be counted as attesting.\n                continue",
     "            if upstream is None:\n                return True"),
    ("M10 a reference-less object wrongly counted as retaining",
     CAS, "        if not references:\n            return False", "        if not references:\n            return True"),
    ("M11 a lineage-less object wrongly counted as retaining",
     CAS, "        if lineage is None:\n            return False", "        if lineage is None:\n            return True"),
    # -- reporting -----------------------------------------------------------
    ("M12 spared objects not reported",
     CAS, "                partial.append(object_id)", "                pass"),
    ("M13 partial_count always zero",
     CAS, "        return len(self.partially_retracted)", "        return 0"),
    # -- fixpoint iteration [T01.8.1 repair] ---------------------------------
    ("M17 fixpoint collapsed to a single pass (the T01.8.1 defect)",
     CAS, "        while progressing:\n            progressing = False",
     "        for _once in (0,):\n            progressing = False"),
    ("M18 fixpoint never re-iterates (progress never signalled)",
     CAS, "                doomed.add(object_id)\n                progressing = True",
     "                doomed.add(object_id)"),
    ("M19 settled objects skipped by identity rather than membership",
     CAS, "                if object_id in doomed_dependents:\n                    continue",
     "                if object_id in doomed:\n                    continue"),
    ("M20 eligibility emitted for every undecided object",
     CAS, "            if object_id in doomed_dependents:\n                eligible.append(object_id)",
     "            if True:\n                eligible.append(object_id)"),
    # -- I6 detective boundary ----------------------------------------------
    ("M14 I6 flags partial retraction as a cascade miss",
     INT, "            if any(ref.object_id not in withdrawn for ref in references):\n                # Partial retraction: still attested. [T01.2.4, N-9, IOM 3.2]\n                continue",
     "            if False:\n                continue"),
    ("M15 I6 stops detecting a genuine uncascaded miss",
     INT, "            if not any(ref.object_id in withdrawn for ref in references):\n                continue",
     "            if True:\n                continue"),
    ("M16 I6 ignores reference-less objects check inverted",
     INT, "            if not references:\n                continue", "            if references:\n                continue"),
]


def run_suite() -> bool:
    """True if the suite PASSES. A hang counts as 'not killed' and is
    reported: a mutant that never terminates cannot be observed to fail."""
    try:
        return _run() == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] ", end="", flush=True)
        return True


def _run() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_partial_retraction.py", "tests/test_cascade.py",
         "tests/test_integrity.py", "tests/test_fact.py",
         "tests/test_problem.py", "tests/test_pattern.py",
         "tests/test_solution.py", "tests/test_validation.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    return proc.returncode


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
