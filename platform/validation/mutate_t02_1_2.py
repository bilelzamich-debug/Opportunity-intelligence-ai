"""Mutation testing for T02.1.2 -- acquisition rights.

Each mutation breaks one rule of the ratified N-21/N-24 boundary; the
suite must fail. The most important mutants are those that OPEN the
fail-closed gate -- admitting UNASSESSED, honouring an expired PERMITTED,
creating an object under RETAIN_NONE, or accepting an assessment from an
authority that was never designated. If any of those survives, the tests
are not protecting the gate.

Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ROOT-CAUSE HARDENING (discovered during T02.2.1 validation): a restored
# source within the same mtime second can be served with STALE MUTATED
# bytecode from __pycache__. Never write bytecode during mutation runs,
# and purge the cache around every write so each suite sees the real file.
PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "rights.py"

MUTATIONS = [
    # -- opening the fail-closed gate ----------------------------------------
    ("M1 UNASSESSED admits acquisition",
     SRC,
     "        return (\n            self.acquisition is AcquisitionRight.PERMITTED",
     "        return (\n            self.acquisition is not AcquisitionRight.PROHIBITED"),
    ("M2 an expired PERMITTED still admits",
     SRC,
     "            and not self.is_expired()\n",
     "            and True\n"),
    ("M3 RETAIN_NONE admits",
     SRC,
     "            and self.retention\n            in (RetentionRight.RETAIN_FULL, RetentionRight.RETAIN_REFERENCE_ONLY)\n        )",
     "            and self.retention\n            in (RetentionRight.RETAIN_FULL, RetentionRight.RETAIN_REFERENCE_ONLY, RetentionRight.RETAIN_NONE)\n        )"),
    ("M4 retention UNASSESSED downgraded to REFERENCE_ONLY",
     SRC,
     "    elif assessment.retention is RetentionRight.UNASSESSED:",
     "    elif False:"),
    # -- the authority  [N-24] -------------------------------------------------
    ("M5 any authority is accepted",
     SRC,
     '        if (self.authority or "").strip() != RIGHTS_AUTHORITY_ROLE:',
     "        if False:"),
    ("M6 the authority role is silently renamed",
     SRC,
     'RIGHTS_AUTHORITY_ROLE: str = "Designated Source Rights/Compliance Authority"',
     'RIGHTS_AUTHORITY_ROLE: str = "Compliance Czar"'),
    # -- the closed vocabularies ------------------------------------------------
    ("M7 an invented acquisition right joins the vocabulary",
     SRC,
     '    UNASSESSED = "UNASSESSED"\n\n\nclass RetentionRight',
     '    UNASSESSED = "UNASSESSED"\n    CONDITIONAL = "CONDITIONAL"\n\n\nclass RetentionRight'),
    ("M8 an invented retention right joins the vocabulary",
     SRC,
     '    UNASSESSED = "UNASSESSED"\n\n\nACQUISITION_RIGHTS',
     '    UNASSESSED = "UNASSESSED"\n    RETAIN_SUMMARY = "RETAIN_SUMMARY"\n\n\nACQUISITION_RIGHTS'),
    ("M9 acquisition vocabulary validation removed",
     SRC,
     "        if not isinstance(self.acquisition, AcquisitionRight):",
     "        if False:"),
    # -- storage mode (S 5.7) ---------------------------------------------------
    ("M10 RETAIN_FULL maps to REFERENCE_ONLY",
     SRC,
     "            StorageMode.FULL\n            if assessment.retention is RetentionRight.RETAIN_FULL",
     "            StorageMode.REFERENCE_ONLY\n            if assessment.retention is RetentionRight.RETAIN_FULL"),
    # -- K10: never silent --------------------------------------------------------
    ("M11 refusals stop being recorded",
     SRC,
     "        if refusals is not None:\n            refusals.append(refusal)",
     "        if False:\n            refusals.append(refusal)"),
    ("M12 a refusal carries no detail",
     SRC,
     '        if not (self.detail or "").strip():\n            raise RightsError(',
     '        if False:\n            raise RightsError('),
    # -- access_conditions (S 5.7 / S 5.9) ---------------------------------------
    ("M13 access_conditions composed for inadmissible assessments",
     SRC,
     "    decision = evaluate_gate(assessment)\n    if not decision.admitted:",
     "    decision = evaluate_gate(assessment)\n    if False:"),
    # -- gate 3 only ---------------------------------------------------------------
    ("M14 the gate invents a scope refusal of its own",
     SRC,
     "    reference = now if now is not None else utc_now()",
     "    reference = now if now is not None else utc_now()\n    if assessment.source_identifier.startswith('x'):\n        return GateDecision(source_identifier=assessment.source_identifier, admitted=False, storage_mode=None, refusal=RightsRefusal(source_identifier=assessment.source_identifier, reason=RefusalReason.PROHIBITED, refused_at=reference, detail='invented'))"),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "tests/test_rights.py"],
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
    backup = ROOT / "validation" / ".rights.py.orig"
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
