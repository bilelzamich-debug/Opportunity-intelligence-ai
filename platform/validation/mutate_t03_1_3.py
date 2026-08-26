"""Mutation testing for T03.1.3 -- positional anchoring [F-V2].

Each mutation breaks one rule the anchoring layer enforces; the suite
must fail. The most important mutants are those that ADMIT WHAT MUST BE
REFUSED -- a locator that guesses, a resolution that searches, an anchor
invented for an ambiguous or absent span, a register that overwrites
itself, or a bridge that silently fabricates claim components.

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
# Never write bytecode during mutation runs, and purge the cache around
# every write so each suite sees the real file.
PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


ROOT = Path(__file__).resolve().parents[1]
EXTRACTION = ROOT / "oip" / "extraction.py"
ANCHORING = ROOT / "oip" / "anchoring.py"

MUTATIONS = [
    # -- the closed locator grammar ---------------------------------------
    ("M1 grammar check skipped: any string parses as a locator",
     EXTRACTION,
     "    if match is None:",
     "    if False:"),
    ("M2 Unicode digits leak past the ASCII-only grammar",
     EXTRACTION,
     'LOCATOR_PATTERN = re.compile(r"chars ([0-9]+)-([0-9]+)\\Z")',
     'LOCATOR_PATTERN = re.compile(r"chars (\\d+)-(\\d+)\\Z")'),
    ("M3 bounds check skipped: out-of-range locators resolve",
     EXTRACTION,
     "    if end > len(content):",
     "    if False:"),
    ("M4 empty/inverted spans resolve instead of refusing",
     EXTRACTION,
     "    if start >= end:",
     "    if False:"),
    # -- the anchoring computation ----------------------------------------
    ("M5 ambiguous span: locator guessed as the first occurrence",
     EXTRACTION,
     '''    if occurrences > 1:
        # Preserve uncertainty instead of resolving it: an ambiguous span
        # gets no locator, never a guessed position. [AC2]
        raise AnchoringError(''',
     '''    if False:
        # Preserve uncertainty instead of resolving it: an ambiguous span
        # gets no locator, never a guessed position. [AC2]
        raise AnchoringError('''),
    ("M6 absent span: phantom locator at find() == -1",
     EXTRACTION,
     '''    if occurrences == 0:
        raise AnchoringError(''',
     '''    if False:
        raise AnchoringError('''),
    ("M7 locator off by one: end drifts past the span",
     EXTRACTION,
     '    return f"chars {start}-{start + len(span)}"',
     '    return f"chars {start}-{start + len(span) + 1}"'),
    # -- extraction integration -------------------------------------------
    ("M8 registration skipped: accepted Facts never anchored in register",
     EXTRACTION,
     "    if anchors is not None:\n        anchors.record",
     "    if False:\n        anchors.record"),
    ("M9 ANCHOR_NOT_RESOLVABLE misreported as not-attempted [N-10]",
     EXTRACTION,
     """        ExtractionStage.ANCHOR_NOT_FOUND,
        ExtractionStage.AMBIGUOUS_ANCHOR,
        ExtractionStage.ANCHOR_NOT_RESOLVABLE,""",
     """        ExtractionStage.ANCHOR_NOT_FOUND,
        ExtractionStage.AMBIGUOUS_ANCHOR,
        ExtractionStage.AMBIGUOUS_ANCHOR,"""),
    # -- the register --------------------------------------------------------
    ("M10 register conflict silently overwrites the original anchor",
     EXTRACTION,
     """            if existing is not None:
                if existing != locator:""",
     """            if existing is not None:
                if False:"""),
    # -- the S-5 bridge ------------------------------------------------------
    ("M11 provider stops resolving positional locators",
     ANCHORING,
     "        if LOCATOR_PATTERN.fullmatch(locator.strip()):",
     "        if False:"),
    ("M12 provider raises instead of the protocol's unresolvable None",
     ANCHORING,
     """            except Exception:  # noqa: BLE001 - unresolvable is the protocol
                return None""",
     """            except Exception:  # noqa: BLE001 - unresolvable is the protocol
                raise"""),
    ("M13 provider admits ambiguous verbatim spans",
     ANCHORING,
     "        return locator if _locate(content, locator) == 1 else None",
     "        return locator if _locate(content, locator) >= 1 else None"),
    ("M14 projection fabricates a value the Fact never carried",
     ANCHORING,
     '            value="",\n        )\n        for attachment in fact.attachments',
     '            value="0",\n        )\n        for attachment in fact.attachments'),
    ("M15 projection drops the subject (weakened layer-1 check)",
     ANCHORING,
     "            subject=fact.claim.subject,",
     '            subject="",'),
    ("M16 projection rewrites the anchor (F-I3 broken)",
     ANCHORING,
     "                locator=attachment.positional_anchor,",
     '                locator="chars 0-1",'),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_anchoring.py", "tests/test_extraction.py"],
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
    sources = {EXTRACTION: EXTRACTION.read_text(),
               ANCHORING: ANCHORING.read_text()}
    backup_dir = ROOT / "validation" / ".t0313_backup"
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
            path.write_text(sources[path])
            _purge_pycache()

    for path, text in sources.items():
        path.write_text(text)
    identical = all(
        path.read_text() == backups[path].read_text() for path in sources
    )
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
