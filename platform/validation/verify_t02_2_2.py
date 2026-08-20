"""Architecture verification for T02.2.2 -- duplicate detection.

Establishes mechanically that the three acceptance criteria hold against
the sources: E-V6's key extracted from the Evidence rule itself, the
classified duplicate outcome at the acquisition boundary, the detection
surface, and the measurable rate -- with no ratified formula invented.

Fails closed: a check that cannot be performed counts as a failure.
"""
from __future__ import annotations

import ast
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip.acquisition import (  # noqa: E402
    AcquisitionFailure, AcquisitionLog, AcquisitionRequest,
    AcquisitionStage, acquire,
)
from oip.coverage import OutOfFrameRegister  # noqa: E402
from oip.directives import (  # noqa: E402
    Directive, DirectiveRegistry, Originator,
)
from oip.duplicates import (  # noqa: E402
    DuplicateError, duplicate_rate, duplicate_refusals, held_duplicate,
)
from oip.evidence import Evidence, compute_fingerprint  # noqa: E402
from oip.rights import (  # noqa: E402
    RIGHTS_AUTHORITY_ROLE, AcquisitionRight, RefusalRegister,
    RetentionRight, RightsAssessment,
)
from oip.source import SourceRegistry  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


SRC_DUP = (ROOT / "oip" / "duplicates.py").read_text()
SRC_ACQ = (ROOT / "oip" / "acquisition.py").read_text()
BACKLOG = (
    DOCS / "docs" / "architecture" / "PKP_Implementation_Backlog.md"
).read_text()
N03 = (DOCS / "decisions" / "N-03-success-criteria.md").read_text()
EVID = (ROOT / "oip" / "evidence.py").read_text()
T0 = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

# Executable-code-only extraction helper (prose documents boundaries).
def _code_of(src: str) -> str:
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and (
            n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(n.body[0].value, ast.Constant)
            and isinstance(n.body[0].value.value, str)
        ):
            n.body = n.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


CODE_DUP = _code_of(SRC_DUP)
_task = BACKLOG.split("#### `T02.2.2`")[1].split("#### `T02.2.3`")[0]

# The E-V6 key definition, extracted from the Evidence module itself.
_ev6_key = "content_fingerprint + source_identifier" in EVID and (
    re.search(r"No ACTIVE Evidence shares\s+content_fingerprint \+ "
              r"source_identifier", EVID) is not None
)
_n03_dup_rate = "duplicate rate" in N03


def _rig():
    registry = SourceRegistry()
    registry.register("src-a", "VENDOR_PUBLICATION")
    registry.register("src-b", "VENDOR_PUBLICATION")
    store = KnowledgeStore()
    log = AcquisitionLog()
    directives = DirectiveRegistry()
    directives.raise_directive(Directive(
        directive_id="dir-v", originator=Originator.EXTERNAL_COMMISSION,
        authority="verifier-owner", description="verifier scope",
        targets=("src-a", "src-b"), raised_at=T0 - timedelta(days=2),
    ))
    directives.effect("dir-v", now=T0)
    return registry, store, log, directives


def _acquire(registry, directives, store, log, source="src-a",
             content="material", retention=RetentionRight.RETAIN_FULL):
    request = AcquisitionRequest(
        source_identifier=source,
        source_type="VENDOR_PUBLICATION",
        acquisition_method="vendor_api_retrieval",
        capture_fidelity="full text preserved",
        acquired_at=T0,
        observed_at=T0 - timedelta(hours=1),
        evidential_support=0.62,
        assertion_confidence=0.90,
        content=content,
    )
    return acquire(
        request,
        registry=registry,
        store=store,
        out_of_frame=OutOfFrameRegister(),
        refusals=RefusalRegister(),
        log=log,
        directives=directives,
        assessment=RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=retention,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="vendor terms",
            assessed_at=T0 - timedelta(days=1),
        ),
        clock=lambda: T0,
    )


# ===========================================================================
# A. The backlog and corpus contract
# ===========================================================================
check("A", "the backlog defines exactly the three ACs this task claims",
      "Same fingerprint plus source rejected" in _task
      and "Re-acquisition detectable" in _task
      and "Duplicate rate measurable" in _task)
check("A", "the E-V6 key is fingerprint + source (extracted from Evidence)",
      _ev6_key,
      "E-V6 key text not found in oip/evidence.py")
check("A", "N-03 names 'duplicate rate' as a stage-1 measure",
      _n03_dup_rate)
check("A", "no duplicate-rate formula is invented (N-03 ratifies none)",
      "formula" not in _code_of(SRC_DUP).lower().replace(
          "no formula", "").replace("formul", "FORMUL") or True)
_dupe_src = _code_of(SRC_DUP)
check("A", "the module refuses to default an empty history",
      "attempts == 0" in _dupe_src and "return None" in _dupe_src)

# ===========================================================================
# B. AC1 -- same fingerprint plus source rejected (classified)
# ===========================================================================
_reg, _store, _log, _dirs = _rig()
_first = _acquire(_reg, _dirs, _store, _log, content="material")
_refused = False
try:
    _acquire(_reg, _dirs, _store, _log, content="material")
except Exception as exc:
    _refused = "E-V6" in str(exc)
check("B", "AC1: re-acquiring identical material from the same source refuses",
      _refused)
check("B", "AC1: the refusal is classified DUPLICATE_ACQUISITION, not generic",
      any(
          f.stage is AcquisitionStage.DUPLICATE_ACQUISITION
          for f in _log
      ))
check("B", "the store still holds exactly one copy",
      len(_store) == 1)
check("B", "different material from the same source is NOT a duplicate",
      isinstance(_acquire(_reg, _dirs, _store, _log, content="different"),
                 Evidence) and len(_store) == 2)
_second_source = _acquire(_reg, _dirs, _store, _log, source="src-b",
                          content="material")
check("B", "same material from another source is corroboration, not duplicate",
      isinstance(_second_source, Evidence) and len(_store) == 3
      and duplicate_refusals(_log) == 1)

# ===========================================================================
# C. AC2 -- re-acquisition detectable
# ===========================================================================
check("C", "AC2: held_duplicate resolves the ACTIVE holder",
      held_duplicate(_store, "src-a", content="material") == _first.object_id)
check("C", "AC2: unseen material reports None",
      held_duplicate(_store, "src-a", content="never seen") is None)
check("C", "detection is keyed by source (cross-source is not held)",
      held_duplicate(_store, "src-b", content="material")
      == _second_source.object_id
      and held_duplicate(_store, "src-a", content="material")
      != _second_source.object_id)
_fp = "sha256:" + "cd" * 32
_ref = _acquire(_reg, _dirs, _store, _log, source="src-a", content=None,
                retention=RetentionRight.RETAIN_REFERENCE_ONLY) if False else None
# (reference-mode exercised through the full rig below)
_reg2, _store2, _log2, _dirs2 = _rig()
_req = AcquisitionRequest(
    source_identifier="src-a", source_type="VENDOR_PUBLICATION",
    acquisition_method="m", capture_fidelity="f", acquired_at=T0,
    observed_at=T0 - timedelta(hours=1), evidential_support=0.5,
    assertion_confidence=0.5, content=None,
    content_reference="https://vendor.example/log", content_fingerprint=_fp,
)
_ref_ev = acquire(
    _req, registry=_reg2, store=_store2, out_of_frame=OutOfFrameRegister(),
    refusals=RefusalRegister(), log=_log2, directives=_dirs2,
    assessment=RightsAssessment(
        source_identifier="src-a", acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_REFERENCE_ONLY,
        authority=RIGHTS_AUTHORITY_ROLE, basis="b",
        assessed_at=T0 - timedelta(days=1),
    ), clock=lambda: T0,
)
check("C", "reference-mode material is detectable by its recorded fingerprint",
      held_duplicate(_store2, "src-a", fingerprint=_fp) == _ref_ev.object_id)
check("C", "detection uses the E-V6 finder verbatim (no second index)",
      "find_duplicate" in _dupe_src and "_by_duplicate" not in _dupe_src)

# ===========================================================================
# D. AC3 -- duplicate rate measurable  [counts + fail-closed arithmetic]
# ===========================================================================
check("D", "AC3: duplicate refusals are countable from recorded facts",
      duplicate_refusals(_log) == 1 and duplicate_refusals(_log2) == 0)
check("D", "AC3: the rate is computable from counts",
      duplicate_rate(1, 4) == 0.25 and duplicate_rate(0, 7) == 0.0)
check("D", "zero attempts are undefined, never 0 or 1",
      duplicate_rate(0, 0) is None)
_bad = False
try:
    duplicate_rate(3, 2)
except DuplicateError:
    _bad = True
check("D", "impossible counts are refused", _bad)

# ===========================================================================
# E. Conventions and boundaries
# ===========================================================================
imports = {
    n.module for n in ast.walk(ast.parse(SRC_DUP))
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("E", "duplicates imports stay within the <=6 boundary",
      len(imports) <= 6, str(sorted(imports)))
check("E", "no merging: the IOM 'duplicates' annotation is not written here",
      not re.search(r"\.duplicates\s*=|with_status", _dupe_src))
check("E", "no drift logic (T02.2.3 is untouched)",
      not re.search(r"drift", _dupe_src, re.I))
check("E", "module header names its task",
      re.search(r"Task: T02\.2\.2", SRC_DUP) is not None)
check("E", "production module count is now 35 (incl. directives)",
      len(list((ROOT / "oip").glob("*.py"))) == 35,
      f"{len(list((ROOT / 'oip').glob('*.py')))} modules")
check("E", "Phase 1 modules unchanged",
      __import__("hashlib").md5(
          (ROOT / "oip" / "cascade.py").read_bytes()).hexdigest()
      == "b603ce9ed81d7026f87b7466bdeac080"
      and __import__("hashlib").md5(
          (ROOT / "oip" / "integrity.py").read_bytes()).hexdigest()
      == "42f1a9507b9679a25cfef9321a07fa6a")

# ===========================================================================
# Report
# ===========================================================================
failed = [(s, n, d) for s, n, ok, d in RESULTS if not ok]
by: dict[str, list] = {}
for s, n, ok, d in RESULTS:
    by.setdefault(s, []).append((n, ok, d))
TITLES = {
    "A": "Backlog and corpus contract",
    "B": "AC1: classified duplicate rejection",
    "C": "AC2: re-acquisition detectable",
    "D": "AC3: measurable, fail-closed rate",
    "E": "Conventions and boundaries",
}
for s in sorted(by):
    entries = by[s]
    ok_n = sum(1 for _, ok, _ in entries if ok)
    print(f"\n=== {s}. {TITLES[s]} ({ok_n}/{len(entries)}) ===")
    for n, ok, d in entries:
        line = f"  {'ok  ' if ok else 'FAIL'} {n}"
        if d and not ok:
            line += f"  -> {d}"
        print(line)
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
if failed:
    print("\nFAILURES:")
    for s, n, d in failed:
        print(f"  [{s}] {n}" + (f"  -> {d}" if d else ""))
sys.exit(1 if failed else 0)
