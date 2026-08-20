"""Mutation testing for T02.2.3 -- drift detection.

Each mutation breaks one rule of the ratified boundary; the suite must
fail. The critical mutants make drift INVISIBLE or INVENTED: inverting
N-15's mismatch test, recording drift for unchanged material (blurring
T02.2.2's boundary), superseding without the explicit declaration, or
bypassing the store's transition path.

Hardened harness: bytecode never cached; cache purged around every
write/restore; sources restored byte-identically.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "drift.py"

PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


MUTATIONS = [
    # -- AC1: the N-15 test itself ------------------------------------------------
    ("M1 drifted inverted: agreement counts as drift",
     SRC,
     "        return self.original_fingerprint != self.reacquired_fingerprint",
     "        return self.original_fingerprint == self.reacquired_fingerprint"),
    ("M2 drift suppressed: mismatch counts as unchanged",
     SRC,
     "        return self.original_fingerprint != self.reacquired_fingerprint",
     "        return False"),
    ("M3 the baseline replaced by the new fingerprint (drift undetectable)",
     SRC,
     "        original_fingerprint=evidence.content.fingerprint,",
     "        original_fingerprint=(\n            fingerprint\n            if fingerprint is not None\n            else compute_fingerprint(content)\n        ),"),
    # -- AC2: the record ----------------------------------------------------------------
    ("M4 unchanged material becomes recordable drift",
     SRC,
     "        if self.original_fingerprint == self.reacquired_fingerprint:\n            raise NotDriftError(",
     "        if False:\n            raise NotDriftError("),
    ("M5 drift records are not appended",
     SRC,
     "    register.append(record)",
     "    register if False else None"),
    ("M6 the record names the wrong object (the source, not the original)",
     SRC,
     "        original_object_id=verdict.holder_object_id,",
     "        original_object_id=verdict.source_identifier,"),
    # -- AC3: supersession discipline ---------------------------------------------------
    ("M7 supersession without the explicit declaration",
     SRC,
     "    disposition = (\n        Disposition.SUPERSEDED if fidelity_improved else Disposition.NOTED\n    )",
     "    disposition = Disposition.SUPERSEDED"),
    ("M8 declared improvement no longer supersedes",
     SRC,
     "    if fidelity_improved:\n        if store is None:",
     "    if False:\n        if store is None:"),
    ("M9 the transition's V9 reason is dropped",
     SRC,
     '            reason=(\n                f"source drift detected; superseded by improved-fidelity "',
     '            reason=None if True else (\n                f"source drift detected; superseded by improved-fidelity "'),
    ("M10 supersession never happens (transition not called)",
     SRC,
     "        store.transition(",
     "        print("),
    # -- input discipline --------------------------------------------------------------------
    ("M11 an unresolvable original silently drifts",
     SRC,
     '    if evidence is None:\n        raise DriftError(',
     "    if False:\n        raise DriftError("),
    ("M12 material specification checks removed",
     SRC,
     '    if content is None and fingerprint is None:\n        raise MaterialSpecError(',
     "    if False:\n        raise MaterialSpecError("),
    ("M13 the clock is ignored (recorded_at falsified)",
     SRC,
     "    now = (clock or utc_now)()",
     "    now = utc_now()"),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "tests/test_drift.py"],
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
    original = SRC.read_text()
    backup = ROOT / "validation" / ".t02_2_3.orig"
    shutil.copy2(SRC, backup)

    print("baseline (unmutated) ...", end=" ", flush=True)
    _purge_pycache()
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        SRC.write_text(original)
        _purge_pycache()
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
            _purge_pycache()

    SRC.write_text(original)
    _purge_pycache()
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
