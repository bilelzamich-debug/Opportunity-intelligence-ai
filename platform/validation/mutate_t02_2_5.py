"""Mutation testing for T02.2.5 -- governed failure recording.

Each mutation breaks one rule of the N-10 contract; the suite must fail.
The critical mutants make failures SILENT (no projection, no log entry),
destroy an identification (engine, inputs, config, nature), or erase the
not-found vs not-attempted distinction N-10 makes mandatory.

Hardened harness: bytecode never cached; cache purged around every
write/restore; sources restored byte-identically.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "acquisition.py"

PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


MUTATIONS = [
    # -- the projection to the N-10 home ---------------------------------
    ("M1 attached failures never reach the FailureStore",
     SRC,
     "        if store is not None:",
     "        if False:"),
    ("M2 attach silently ignored",
     SRC,
     "            self._failure_store = failure_store",
     "            self._failure_store = None"),
    # -- N-10 identifications ------------------------------------------------
    ("M3 the engine identification is lost",
     SRC,
     "        return Engine.RESEARCH",
     "        return Engine.ORCHESTRATION"),
    ("M4 the inputs attempted are lost",
     SRC,
     "            input_ids=(self.source_identifier,),",
     "            input_ids=(),"),
    ("M5 the configuration in force is lost",
     SRC,
     "                request.engine_configuration_ref\n                if isinstance(request, AcquisitionRequest)",
     "                \"\"\n                if isinstance(request, AcquisitionRequest)"),
    ("M6 a blank configuration ref is accepted",
     SRC,
     '        if not (self.engine_configuration_ref or "").strip():\n            raise AcquisitionError(',
     "        if False:\n            raise AcquisitionError("),
    ("M7 the nature loses its detail",
     SRC,
     '                    f"{self.stage.value}/{self.reason}: {self.detail}",',
     '                    f"{self.stage.value}/{self.reason}",'),
    ("M8 the projection records a non-failing outcome",
     SRC,
     '                    "ACQUISITION-FAILURE",\n                    RuleOutcome.FAIL,',
     '                    "ACQUISITION-FAILURE",\n                    RuleOutcome.SKIP,'),
    ("M9 the object_id names the source, not the failing engine",
     SRC,
     '            object_id=f"engine:{self.engine.value}",',
     '            object_id=f"source:{self.source_identifier}",'),
    # -- AC2: the mandatory distinction --------------------------------------
    ("M10 attempted collapses to always-False",
     SRC,
     "        return self.stage in (\n            AcquisitionStage.DUPLICATE_ACQUISITION,\n            AcquisitionStage.STORE_REJECTED,\n        )",
     "        return False"),
    ("M11 attempted collapses to always-True",
     SRC,
     "        return self.stage in (\n            AcquisitionStage.DUPLICATE_ACQUISITION,\n            AcquisitionStage.STORE_REJECTED,\n        )",
     "        return True"),
    # -- silence ---------------------------------------------------------------
    ("M12 failures are not appended to the log",
     SRC,
     "        with self._lock:\n            self._failures.append(failure)\n            store = self._failure_store",
     "        with self._lock:\n            self._failures if False else None\n            store = self._failure_store"),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_failure_recording.py", "tests/test_acquisition.py"],
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
    backup = ROOT / "validation" / ".t02_2_5.orig"
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
