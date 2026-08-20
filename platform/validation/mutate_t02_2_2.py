"""Mutation testing for T02.2.2 -- duplicate detection.

Each mutation breaks one rule of the ratified boundary; the suite must
fail. The critical mutants make duplicates INVISIBLE (unclassified
refusals, wrong key, cross-source false positives, defaulted rates) --
exactly the silent-duplication failure E-V6 exists to prevent.

Sources restored byte-identically; bytecode never cached (hardened
harness, root cause of the T02.2.1 stale-pyc incident).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DUP = ROOT / "oip" / "duplicates.py"
ACQ = ROOT / "oip" / "acquisition.py"

PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


MUTATIONS = [
    # -- the E-V6 key must be exact ------------------------------------------
    ("D1 detection ignores the source (cross-source false positive)",
     DUP,
     "    return store.evidence.find_duplicate(\n        (key_fingerprint, source_identifier)\n    )",
     "    hit = store.evidence.find_duplicate((key_fingerprint, source_identifier))\n    return hit if hit is not None else store.evidence.find_duplicate((key_fingerprint, 'src-a'))"),
    ("D2 detection ignores the fingerprint (same source = duplicate)",
     DUP,
     "    key_fingerprint = (\n        fingerprint if fingerprint is not None else compute_fingerprint(content)\n    )",
     "    key_fingerprint = fingerprint if fingerprint is not None else '*'"),
    ("D3 fingerprint computed differently than E-V4",
     DUP,
     "from oip.evidence import compute_fingerprint",
     "from oip.evidence import compute_fingerprint as _cf\ncompute_fingerprint = lambda c: 'fingerprint'"),
    # -- the rate must be fail-closed ----------------------------------------
    ("D4 empty history defaults the rate to 0.0",
     DUP,
     "    if attempts == 0:\n        return None",
     "    if attempts == 0:\n        return 0.0"),
    ("D5 empty history defaults the rate to 1.0",
     DUP,
     "    if attempts == 0:\n        return None",
     "    if attempts == 0:\n        return 1.0"),
    ("D6 impossible counts are accepted silently",
     DUP,
     "    if duplicates > attempts:\n        raise DuplicateError(",
     "    if False:\n        raise DuplicateError("),
    # -- counting must be stage-exact -----------------------------------------
    ("D7 the count includes non-duplicate failures",
     DUP,
     "        1 for failure in log if failure.stage is AcquisitionStage.DUPLICATE_ACQUISITION",
     "        1 for failure in log"),
    # -- classification at the acquisition boundary -----------------------------
    ("D8 duplicate refusals classified as generic store rejections",
     ACQ,
     '        if "E-V6" in exc.failure.rule_ids:',
     "        if False:"),
    ("D9 every store rejection mislabelled a duplicate",
     ACQ,
     '        if "E-V6" in exc.failure.rule_ids:',
     '        if True:'),
    ("D10 duplicate detail drops the E-V6 citation",
     ACQ,
     '                AcquisitionStage.DUPLICATE_ACQUISITION, "E-V6",',
     '                AcquisitionStage.DUPLICATE_ACQUISITION, "ACCEPTANCE_REFUSED",'),
    # -- material specification discipline ---------------------------------------
    ("D11 unspecified material silently reports None",
     DUP,
     '    if content is None and fingerprint is None:\n        raise MaterialSpecError(',
     "    if False:\n        raise MaterialSpecError("),
    ("D12 both forms accepted at once",
     DUP,
     '    if content is not None and fingerprint is not None:\n        raise MaterialSpecError(',
     "    if False:\n        raise MaterialSpecError("),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_duplicates.py"],
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
    originals = {p: p.read_text() for p in (DUP, ACQ)}
    backup = ROOT / "validation" / ".t02_2_2.orig"
    shutil.copy2(DUP, backup)

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
