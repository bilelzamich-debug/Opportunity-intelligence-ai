"""Mutation testing for T02.1.4 -- the coverage model.

Each mutation breaks one rule of the ratified N-22 boundary; the suite must
fail. The most important mutants are those that OVERSTATE coverage --
defaulting an unavailable frame, counting volume as coverage, dropping the
out-of-frame register, or admitting an invented gap reason. If any of those
survives, the tests are not protecting the model's honesty.

Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "coverage.py"

MUTATIONS = [
    # -- overstating coverage ------------------------------------------------
    ("M1 unavailable frame defaults coverage to 0.0",
     SRC,
     "            coverage=None,",
     "            coverage=0.0,"),
    ("M2 unavailable frame defaults coverage to 1.0",
     SRC,
     "            coverage=None,",
     "            coverage=1.0,"),
    ("M3 coverage counts volume, not member existence",
     SRC,
     "        coverage=len(represented_members) / len(active),",
     "        coverage=min(1.0, len(active_evidence_types) / len(active)),"),
    ("M4 represented members leak into the gaps",
     SRC,
     "        for member in sorted(active - represented_members, key=lambda m: m.value)",
     "        for member in sorted(active, key=lambda m: m.value)"),
    # -- the out-of-frame register (AS-4) ------------------------------------
    ("M5 out_of_frame count dropped from the report",
     SRC,
     "            out_of_frame=out_of_frame.count(),",
     "            out_of_frame=0,"),
    ("M6 out_of_frame enters the coverage arithmetic",
     SRC,
     "        coverage=len(represented_members) / len(active),",
     "        coverage=(len(represented_members) + out_of_frame.count()) / len(active),"),
    ("M7 typable sources admitted to the out-of-frame register",
     SRC,
     "        raise OutOfFrameError(\n            f\"source {source_identifier!r} with source_type \"",
     "        return None  # type: ignore[return-value]\n        raise OutOfFrameError(\n            f\"source {source_identifier!r} with source_type \""),
    # -- the closed reason vocabulary ----------------------------------------
    ("M8 an invented gap reason joins the vocabulary",
     SRC,
     "    OUT_OF_SCOPE = \"OUT_OF_SCOPE\"",
     "    OUT_OF_SCOPE = \"OUT_OF_SCOPE\"\n    LOW_PRIORITY = \"LOW_PRIORITY\""),
    ("M9 UNTYPABLE_CHANNEL smuggled in as a gap reason",
     SRC,
     "    OUT_OF_SCOPE = \"OUT_OF_SCOPE\"",
     "    OUT_OF_SCOPE = \"OUT_OF_SCOPE\"\n    UNTYPABLE_CHANNEL = \"UNTYPABLE_CHANNEL\""),
    ("M10 gap reason validation removed",
     SRC,
     "        if not isinstance(self.reason, GapReason):",
     "        if False:"),
    # -- declared completeness and its why ------------------------------------
    ("M11 declared-complete ignores undeclared gaps",
     SRC,
     "        declared_complete=all(g.is_declared for g in gaps),",
     "        declared_complete=True,"),
    ("M12 a declaration no longer requires its rationale",
     SRC,
     "        if not (self.rationale or \"\").strip():",
     "        if False:"),
    # -- AC3 inheritance ------------------------------------------------------
    ("M13 inheritance drops the rationale PT-V5 must reason over",
     SRC,
     "        return tuple(\n            g.declaration for g in self.gaps if g.declaration is not None\n        )",
     "        return tuple(\n            g.declaration for g in self.gaps if g.declaration is not None\n        )[:0]"),
    # -- the frame is taken, never redefined ----------------------------------
    ("M14 frame redefined inline instead of taken from the taxonomy",
     SRC,
     "    return frozenset(taxonomy_members())",
     "    return frozenset(list(taxonomy_members()) + [__import__('oip.source').SourceType('PUBLISHED_EDITORIAL')])"),
]


def _run() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "tests/test_coverage.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
    )
    return proc.returncode


def run_suite() -> bool:
    """True if the suite PASSES (i.e. the mutant survived)."""
    try:
        return _run() == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] ", end="", flush=True)
        return True


def main() -> int:
    original = SRC.read_text()
    backup = ROOT / "validation" / ".coverage.py.orig"
    shutil.copy2(SRC, backup)

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        SRC.write_text(original)
        return 2
    print("pass")

    survivors: list[str] = []
    inapplicable: list[str] = []
    killed = 0

    for label, path, old, new in MUTATIONS:
        text = path.read_text()
        if old not in text:
            inapplicable.append(label)
            print(f"  SKIP      {label} (anchor not found)")
            continue
        path.write_text(text.replace(old, new, 1))
        try:
            if run_suite():
                survivors.append(label)
                print(f"  SURVIVED  {label}")
            else:
                killed += 1
                print(f"  killed    {label}")
        finally:
            path.write_text(original)

    SRC.write_text(original)
    identical = SRC.read_text() == backup.read_text()
    total = len(MUTATIONS) - len(inapplicable)
    print(f"\nkilled {killed}/{total}; survivors {len(survivors)}; "
          f"inapplicable {len(inapplicable)}")
    print(f"sources restored byte-identical: {identical}")
    for s in survivors:
        print(f"  SURVIVOR: {s}")
    backup.unlink(missing_ok=True)
    return 1 if (survivors or inapplicable or not identical) else 0


if __name__ == "__main__":
    sys.exit(main())
