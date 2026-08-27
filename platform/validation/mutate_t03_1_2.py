"""Mutation testing for T03.1.2 -- structured claim decomposition [S-3].

Each mutation breaks one rule the decomposition enforces; the suite must
fail. The most important mutants are those that ADMIT WHAT MUST BE
REFUSED -- a non-real or non-finite quantity slipping into a Fact, a
broken equivalence witness ignored, a refusal left unrecorded, or a
component silently altered between the request and the claim.

Sources restored byte-identically and verified byte-for-byte.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ROOT-CAUSE HARDENING (from T02.2.1): a restored source within the same
# mtime second can be served with STALE MUTATED bytecode from __pycache__.
PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "extraction.py"

MUTATIONS = [
    # -- the finiteness / type gates [AC2: comparison must be defined] ----
    ("M1 finiteness check skipped: NaN/inf quantities become Facts",
     SRC,
     "            if not math.isfinite(number):",
     "            if False:"),
    ("M2 real-number type check skipped: bool/str quantities become Facts",
     SRC,
     "            if isinstance(number, bool) or not isinstance(number, (int, float)):",
     "            if False:"),
    # -- the self-equivalence witness [AC2] --------------------------------
    ("M3 witness gate skipped: incomparable claims admitted",
     SRC,
     "    if witness.verdict is not Verdict.EQUIVALENT:",
     "    if False:"),
    # -- the extraction gate [N-10] ----------------------------------------
    ("M4 decomposition gate unwired: DecompositionError escapes unrecorded",
     SRC,
     "    except DecompositionError as exc:",
     "    except ():"),
    ("M5 decompose bypassed: unguarded as_claim restored in extract",
     SRC,
     "        claim = decompose(request)",
     "        claim = request.as_claim()"),
    ("M6 DECOMPOSITION_FAILED misreported as not-attempted [N-10]",
     SRC,
     "        ExtractionStage.ANCHOR_NOT_RESOLVABLE,\n"
     "        ExtractionStage.DECOMPOSITION_FAILED,",
     "        ExtractionStage.ANCHOR_NOT_RESOLVABLE,\n"
     "        ExtractionStage.ANCHOR_NOT_RESOLVABLE,"),
    ("M7 refusal reason token altered (record drift)",
     SRC,
     'ExtractionStage.DECOMPOSITION_FAILED, "NOT_DECOMPOSABLE",',
     'ExtractionStage.DECOMPOSITION_FAILED, "DECOMPOSED",'),
    ("M8 refusal detail stripped (silent-failure record)",
     SRC,
     '''            f"the claim does not satisfy the S-3 structure as a "
            f"comparable claim: {exc} [S-3, T03.1.2]", log, now,''',
     '''            " ", log, now,'''),
    # -- the structure projection [AC1: byte-identical components] ---------
    ("M9 qualifier stripped to the NONE sentinel during decomposition",
     SRC,
     """    claim = request.as_claim()
    quantity = claim.value""",
     """    claim = Claim(
        subject=request.subject,
        predicate=request.predicate,
        qualifier=UNQUALIFIED,
        value=request.value,
    )
    quantity = claim.value"""),
    ("M10 quantity dropped before the gates: value discipline skipped",
     SRC,
     "    quantity = claim.value",
     "    quantity = None"),
    ("M11 subject/predicate swapped in the decomposition",
     SRC,
     """    claim = request.as_claim()
    quantity = claim.value""",
     """    claim = Claim(
        subject=request.predicate,
        predicate=request.subject,
        qualifier=request.qualifier,
        value=request.value,
    )
    quantity = claim.value"""),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_decomposition.py", "tests/test_extraction.py",
         "tests/test_anchoring.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
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
    backup = ROOT / "validation" / ".t0312_backup.py"
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
        if old == new:
            inapplicable.append(label + " (no-op placeholder)")
            continue
        text = path.read_text()
        if old not in text:
            inapplicable.append(label)
            print(f"  SKIP      {label} (anchor not found)")
            continue
        path.write_text(text.replace(old, new, 1))
        _purge_pycache()
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
