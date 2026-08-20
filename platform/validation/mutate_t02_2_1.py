"""Mutation testing for T02.2.1 -- acquisition.

Each mutation breaks one rule of the ratified boundary; the suite must
fail. The most important mutants are those that ADMIT WHAT MUST BE
REFUSED -- bypassing a gate, creating Evidence without rights, defaulting
the fidelity statement, or leaking an object after a refusal.

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
SRC = ROOT / "oip" / "acquisition.py"

MUTATIONS = [
    # -- gate bypasses ---------------------------------------------------------
    ("M1 gate 2 (typability) skipped entirely",
     SRC,
     "    try:\n        member = classify(request.source_type)",
     "    try:\n        member = classify(request.source_type) if False else __import__('oip.source').SourceType.PUBLISHED_EDITORIAL"),
    ("M2 gate 3 (rights) skipped: unassessed admits",
     SRC,
     "    rights = assessment if assessment is not None else unassessed(\n        request.source_identifier\n    )",
     "    rights = assessment if assessment is not None else __import__('oip.rights').RightsAssessment(\n        source_identifier=request.source_identifier,\n        acquisition=__import__('oip.rights').AcquisitionRight.PERMITTED,\n        retention=__import__('oip.rights').RetentionRight.RETAIN_FULL,\n        authority=__import__('oip.rights').RIGHTS_AUTHORITY_ROLE,\n        basis='forged',\n        assessed_at=now,\n    )"),
    ("M3 refusal decision ignored, acquisition proceeds",
     SRC,
     "    if not decision.admitted:",
     "    if False:"),
    # -- AC3 --------------------------------------------------------------------
    ("M4 capture_fidelity silently defaulted",
     SRC,
     '            "capture_fidelity",\n        ):',
     '            "capture_fidelity",\n        ) if False else ():'),
    # -- N-15 / N-21 S 5.7 ---------------------------------------------------------
    ("M5 storage mode flipped to FULL regardless of rights",
     SRC,
     "    mode = _MODE_MAP[decision.storage_mode]",
     "    mode = StorageMode.FULL"),
    ("M6 access_conditions composed without the rights",
     SRC,
     "        access_conditions=access_conditions_value(rights),",
     '        access_conditions="open",'),
    # -- AC2: silence --------------------------------------------------------------
    ("M7 failures stop being recorded in the log",
     SRC,
     "    return log.append(",
     "    return ("),
    ("M8 the out-of-frame register is skipped on gate-2 refusal",
     SRC,
     "        out_of_frame.record(",
     "        None if True else out_of_frame.record("),
    ("M9 the rights refusal register is not consulted",
     SRC,
     "    decision = evaluate_gate(rights, refusals=refusals, now=now)",
     "    decision = evaluate_gate(rights, now=now)"),
    # -- no object on refusal / partial state ------------------------------------------
    ("M10 Evidence is still returned after a store rejection",
     SRC,
     "        raise _refuse(failure) from exc\n\n    accepted = store.get_evidence(stored.object_id)",
     "        pass\n\n    accepted = store.get_evidence(stored.object_id)"),
    # -- provenance integrity ------------------------------------------------------------
    ("M11 independence group dropped from provenance",
     SRC,
     "        source_independence_group=request.independence_group,",
     "        source_independence_group=None,"),
    ("M12 provenance carries no acquisition method",
     SRC,
     "        acquisition_method=request.acquisition_method,",
     '        acquisition_method="",'),
    # -- request validation -----------------------------------------------------------------
    ("M13 E-V5 (observed <= acquired) check removed",
     SRC,
     '        if self.observed_at > self.acquired_at:\n            raise AcquisitionError(\n                f"observed_at must be <= acquired_at [E-V5]"\n            )',
     "        if False:\n            pass"),
    ("M14 both content forms accepted simultaneously",
     SRC,
     "        if has_full and has_reference:",
     "        if False:"),
    # -- gate 2 register routing ------------------------------------------------------------
    ("M15 gate-2 refusal recorded as a rights refusal instead",
     SRC,
     "            AcquisitionStage.UNTYPABLE_CHANNEL, \"UNTYPABLE_CHANNEL\",",
     "            AcquisitionStage.REFUSED_BY_RIGHTS, \"UNTYPABLE_CHANNEL\","),]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_acquisition.py"],
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
    backup = ROOT / "validation" / ".acquisition.py.orig"
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
