"""Mutation testing for T03.2.2 -- sampled deep audit [S-5 Layer 2].

Each mutation breaks one rule the audit layer enforces; the suite must
fail. The mutants that matter are ADMIT-WHAT-MUST-BE-REFUSED: an invalid
rate accepted, a zero rate that still samples, None-span treated as
FAITHFUL, Layer-1-pass collapsed to FAITHFUL, lexicon conflicts ignored.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "oip" / "audit.py"

MUTATIONS = [
    ("M1 invalid rates accepted (boundary skipped)",
     AUDIT,
     "    if not math.isfinite(rate) or rate < 0.0 or rate > 1.0:",
     "    if False:"),
    ("M2 zero rate returns the whole stratum",
     AUDIT,
     "    if rate <= 0.0:\n        return 0",
     "    if rate <= 0.0:\n        return n"),
    ("M3 sample size not capped at n",
     AUDIT,
     "    return min(n, math.floor(rate * n + 1e-12))",
     "    return math.floor(rate * n + 1e-12) + n"),
    ("M4 None span treated as FAITHFUL",
     AUDIT,
     "    if span is None:",
     "    if False:"),
    ("M5 empty span treated as auditable",
     AUDIT,
     "    if not str(span).strip():",
     "    if False:"),
    ("M6 lexicon conflicts ignored",
     AUDIT,
     "    if conflicts:",
     "    if False:"),
    ("M7 negation mismatch ignored",
     AUDIT,
     "    if _has_negation(claim_text) != _has_negation(span):",
     "    if False:"),
    ("M8 quantity mismatch ignored",
     AUDIT,
     "    if value_ok is False:",
     "    if False:"),
    ("M9 qualifier tokens not required to be supported",
     AUDIT,
     "        if missing_qual:",
     "        if False:"),
    ("M10 completed FAITHFUL assigned on UNAUDITABLE path (judgement smuggled)",
     AUDIT,
     '            judgement=None,\n            reason=(\n                f"span at {locator!r} in {attachment.evidence_ref!r} is "',
     '            judgement=AuditJudgement.FAITHFUL,\n            reason=(\n                f"span at {locator!r} in {attachment.evidence_ref!r} is "'),
]


def _run() -> int:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "tests/test_audit.py"],
        cwd=ROOT, capture_output=True, env=env, timeout=180,
    ).returncode


def run_suite() -> bool:
    try:
        return _run() == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] ", end="", flush=True)
        return True


def main() -> int:
    source = AUDIT.read_text()
    backup_dir = ROOT / "validation" / ".t0322_backup"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / AUDIT.name
    shutil.copy2(AUDIT, backup)

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        AUDIT.write_text(source)
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
        _purge_pycache()
        try:
            if run_suite():
                survivors.append(label)
                print(f"  SURVIVED  {label}")
            else:
                killed += 1
                print(f"  killed    {label}")
        finally:
            path.write_text(source)
            _purge_pycache()

    AUDIT.write_text(source)
    identical = AUDIT.read_text() == backup.read_text()
    total = len(MUTATIONS) - len(inapplicable)
    print(f"\nkilled {killed}/{total}; survivors {len(survivors)}; "
          f"inapplicable {len(inapplicable)}")
    print(f"sources restored byte-identical: {identical}")
    for s in survivors:
        print(f"  SURVIVOR: {s}")
    shutil.rmtree(backup_dir, ignore_errors=True)
    return 1 if (survivors or inapplicable or not identical) else 0


if __name__ == "__main__":
    sys.exit(main())
