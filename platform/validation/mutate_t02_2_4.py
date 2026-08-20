"""Mutation testing for T02.2.4 -- research directive intake.

Each mutation breaks one rule of the ratified boundary; the suite must
fail. The critical mutants open the scope gate (admitting uncommissioned
acquisition), erase the commissioning authority, invent scheduling or
self-initiation, or break the ratified gate order.

Hardened harness: bytecode never cached; cache purged around every
write/restore; sources restored byte-identically.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRS = ROOT / "oip" / "directives.py"
ACQ = ROOT / "oip" / "acquisition.py"

PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


MUTATIONS = [
    # -- AC1: the scope gate itself --------------------------------------
    ("M1 covers ignores targets: everything is in scope",
     DIRS,
     "        return (\n            target in self.targets\n            and not self.is_expired(now)\n        )",
     "        return not self.is_expired(now)"),
    ("M2 covers ignores expiry: lapsed directives still scope",
     DIRS,
     "        return (\n            target in self.targets\n            and not self.is_expired(now)\n        )",
     "        return target in self.targets"),
    ("M3 RAISED directives scope as if in effect",
     DIRS,
     "                if self._states[d.directive_id] is DirectiveState.IN_EFFECT\n                and d.covers(target, reference)",
     "                if d.covers(target, reference)"),
    ("M4 CANCELLED directives still scope",
     DIRS,
     "                if self._states[d.directive_id] is DirectiveState.IN_EFFECT\n                and d.covers(target, reference)",
     "                if self._states[d.directive_id] in (DirectiveState.IN_EFFECT, DirectiveState.CANCELLED)\n                and d.covers(target, reference)"),
    ("M5 EXPIRED is never reported",
     DIRS,
     "        if (\n            state is DirectiveState.IN_EFFECT\n            and directive.is_expired(now)\n        ):\n            return DirectiveState.EXPIRED",
     "        if False:\n            return DirectiveState.EXPIRED"),
    # -- AC2: authority and vocabulary ------------------------------------
    ("M6 a blank commissioning authority is accepted",
     DIRS,
     '        if not (self.authority or "").strip():\n            raise InvalidDirectiveError(',
     "        if False:\n            raise InvalidDirectiveError("),
    ("M7 an invented originator joins the closed set",
     DIRS,
     '    VALIDATION_BACKFLOW = "VALIDATION_BACKFLOW"',
     '    VALIDATION_BACKFLOW = "VALIDATION_BACKFLOW"\n    RESEARCH_SELF = "RESEARCH_SELF"'),
    ("M8 the platform may raise directives for itself",
     DIRS,
     "        if directive.directive_id in self._directives:",
     "        if False:\n            pass  # self-initiation guard removed\n        if directive.directive_id in self._directives:"),
    # -- AC3: gate-1 integration in acquire --------------------------------
    ("M9 gate 1 removed: acquisition without a directive proceeds",
     ACQ,
     "    if covering is None:",
     "    if False:"),
    ("M10 absent directives behave as all-covering",
     ACQ,
     "        if directives is not None\n        else None",
     "        if True\n        else None"),
    ("M11 the OUT_OF_SCOPE reason token is corrupted",
     ACQ,
     '            AcquisitionStage.OUT_OF_SCOPE, "OUT_OF_SCOPE",',
     '            AcquisitionStage.OUT_OF_SCOPE, "not-in-scope",'),
    # -- S 5.8: the explanation citation -------------------------------------
    ("M12 the directive citation is dropped from the explanation",
     ACQ,
     '                "gate-1 scope: " + covering.directive_id,',
     '                "gate-1 scope: present",'),
    # -- transitions -----------------------------------------------------------
    ("M13 illegal transitions are permitted",
     DIRS,
     "            if current is not required:",
     "            if False:"),
    # -- S 5.4: verbatim scope ---------------------------------------------------
    ("M14 targets are silently widened",
     DIRS,
     '        object.__setattr__(\n            self, "targets", tuple(dict.fromkeys(self.targets))\n        )',
     '        object.__setattr__(\n            self, "targets", tuple(dict.fromkeys(list(self.targets) + ["src-any"]))\n        )'),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_directives.py", "tests/test_acquisition.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
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
    originals = {p: p.read_text() for p in (DIRS, ACQ)}
    backup = ROOT / "validation" / ".t02_2_4.orig"
    shutil.copy2(DIRS, backup)

    print("baseline (unmutated) ...", end=" ", flush=True)
    _purge_pycache()
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        for p, t in originals.items():
            p.write_text(t)
        _purge_pycache()
        return 2
    print("pass")

    survivors: list[str] = []
    inapplicable: list[str] = []
    killed = 0

    for label, path, old, new in MUTATIONS:
        if old == new:
            inapplicable.append(label + " (no-op)")
            continue
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
            path.write_text(originals[path])
            _purge_pycache()

    for p, t in originals.items():
        p.write_text(t)
    _purge_pycache()
    identical = all(p.read_text() == t for p, t in originals.items())
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
