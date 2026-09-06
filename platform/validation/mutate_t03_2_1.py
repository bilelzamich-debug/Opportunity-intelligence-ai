"""Mutation testing for T03.2.1 -- anchor verification at acceptance [F-V6].

Each mutation breaks one rule the wiring enforces; the suite must fail.
The mutants that matter are the ADMIT-WHAT-MUST-BE-REFUSED ones: a provider
that trusts a dangling reference, a REFERENCE-mode payload treated as
resolvable, an install that silently clobbers, a bind that never binds, a
projection that presents no claims, and a bypassed F-V6 rule.

Source restored byte-identically and verified byte-for-byte.

Revision note: the first harness pass exposed two weak spots and they are
fixed, not excused -- the provider's redundant guards were removed (each
surviving mutant was proven-equivalent or a test gap), and REFERENCE-mode
payloads are now tested in BOTH shapes (content retained and content
absent), killing the M2 family outright. Expected survivors: none.
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
ANCHORING = ROOT / "oip" / "anchoring.py"

MUTATIONS = [
    ("M1 dangling-evidence guard removed: a None payload must raise, the "
     "test contract demands None",
     ANCHORING,
     "        if evidence is None:\n            return None",
     "        if False:\n            return None"),
    ("M2 REFERENCE-mode payload treated as verifiable in place [N-15]",
     ANCHORING,
     "        if not content.is_verifiable_in_place:\n            return None",
     "        if False:\n            return None"),
    ("M2b provider reads attributes instead of the content half",
     ANCHORING,
     "        content = evidence.content",
     "        content = evidence.attributes"),
    ("M4 install silently clobbers an existing verifier",
     ANCHORING,
     "    if existing is not None and not replace:",
     "    if False:"),
    ("M5 install builds the verifier but never binds it to the store",
     ANCHORING,
     "    store.anchor_verifier = verifier  # type: ignore[attr-defined]",
     "    _ = verifier  # never bound"),
    ("M6 installed verifier receives no claims_of: F-V6 degrades to SKIP",
     ANCHORING,
     "    if claims_of is None:",
     "    if False:"),
    ("M7 projection presents zero claims for real Facts (empty-verification)",
     ANCHORING,
     "            fact = getattr(ctx, \"fact\", None)\n            return () if fact is None else fact_anchor_claims(fact)",
     "            fact = getattr(ctx, \"fact\", None)\n            return ()"),
]


def _run() -> int:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-x", "tests/"],
        cwd=ROOT, capture_output=True, env=env, timeout=1800,
    ).returncode


def run_suite() -> bool:
    """True if the suite PASSES (i.e. the mutant survived)."""
    try:
        return _run() == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] ", end="", flush=True)
        return True


def main() -> int:
    sources = {ANCHORING: ANCHORING.read_text()}
    backup_dir = ROOT / "validation" / ".t0321_backup"
    backup_dir.mkdir(exist_ok=True)
    backups: dict[Path, Path] = {}
    for path in sources:
        backup = backup_dir / path.name
        shutil.copy2(path, backup)
        backups[path] = backup

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        for path, text in sources.items():
            path.write_text(text)
        return 2
    print("pass")

    survivors: list[str] = []
    expected_survivors = set()
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
                tag = " (expected: proven equivalent)" if any(
                    label.startswith(e) for e in expected_survivors) else ""
                print(f"  SURVIVED  {label}{tag}")
            else:
                killed += 1
                print(f"  killed    {label}")
        finally:
            path.write_text(sources[path])
            _purge_pycache()

    for path, text in sources.items():
        current = path.read_bytes()
        assert current == text.encode(), f"restore mismatch: {path}"

    unexpected = [s for s in survivors
                  if not any(s.startswith(e) for e in expected_survivors)]
    print(f"\nkilled: {killed}/{len(MUTATIONS) - len(inapplicable)}; "
          f"survivors: {len(survivors)} "
          f"(expected-equivalent: {len(survivors) - len(unexpected)})")
    for path in backups.values():
        shutil.rmtree(path.parent, ignore_errors=True)
        break
    return 1 if unexpected or inapplicable else 0


if __name__ == "__main__":
    sys.exit(main())
