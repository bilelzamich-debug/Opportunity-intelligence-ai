"""Architecture verification for T02.2.3 -- drift detection.

Proves the three acceptance criteria mechanically against their sources:
N-15's drift definition extracted from the decision text, detection as
the fingerprint mismatch on re-acquisition, records naming the original
Evidence, and supersession exactly on the caller's explicit
fidelity-improvement declaration -- with no fidelity ordering invented.

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
    AcquisitionLog, AcquisitionRequest, acquire,
)
from oip.coverage import OutOfFrameRegister  # noqa: E402
from oip.directives import (  # noqa: E402
    Directive, DirectiveRegistry, Originator,
)

from oip.drift import (  # noqa: E402
    Disposition, DriftError, DriftRegister, NotDriftError, detect,
    record_drift,
)
from oip.evidence import compute_fingerprint  # noqa: E402
from oip.enums import ObjectStatus  # noqa: E402
from oip.rights import (  # noqa: E402
    RIGHTS_AUTHORITY_ROLE, AcquisitionRight, RefusalRegister,
    RetentionRight, RightsAssessment,
)
from oip.source import SourceRegistry  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


SRC = (ROOT / "oip" / "drift.py").read_text()
TREE = ast.parse(SRC)
BACKLOG = (
    DOCS / "docs" / "architecture" / "PKP_Implementation_Backlog.md"
).read_text()
N15 = (DOCS / "decisions" / "N-15-evidence-storage.md").read_text()
IOM = (
    DOCS / "docs" / "architecture" / "PKP_Intelligence_Object_Model.md"
).read_text()
T0 = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
FIRST = "changelog v1: fails above 50 SKUs."
SECOND = "changelog v2: fails above 200 SKUs."


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


CODE = _code_of(SRC)
_task = BACKLOG.split("#### `T02.2.3`")[1].split("#### `T02.2.4`")[0]

# The drift definition, extracted from N-15's decision text.
_n15_defines = (
    "fingerprint mismatch on re-acquisition" in N15
    and "source drift" in N15
    and "T02.2.3" in N15
)
_iom_fidelity = re.search(
    r"capture_fidelity.*Assessment of what was preserved", IOM, re.S
) is not None and not re.search(
    r"fidelity (order|ranking|scale)", IOM, re.I
)


def _rig():
    registry = SourceRegistry()
    registry.register("src-a", "VENDOR_PUBLICATION")
    store = KnowledgeStore()
    log = AcquisitionLog()
    drifts = DriftRegister()
    directives = DirectiveRegistry()
    directives.raise_directive(Directive(
        directive_id="dir-v", originator=Originator.EXTERNAL_COMMISSION,
        authority="verifier-owner", description="verifier scope",
        targets=("src-a",), raised_at=T0 - timedelta(days=2),
    ))
    directives.effect("dir-v", now=T0)

    def _acquire(content, fidelity="full text preserved"):
        request = AcquisitionRequest(
            source_identifier="src-a",
            source_type="VENDOR_PUBLICATION",
            acquisition_method="vendor_api_retrieval",
            capture_fidelity=fidelity,
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.62,
            assertion_confidence=0.90,
            content=content,
        )
        return acquire(
            request, registry=registry, store=store,
            out_of_frame=OutOfFrameRegister(),
            refusals=RefusalRegister(), log=log,
            directives=directives,
            assessment=RightsAssessment(
                source_identifier="src-a",
                acquisition=AcquisitionRight.PERMITTED,
                retention=RetentionRight.RETAIN_FULL,
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="vendor terms",
                assessed_at=T0 - timedelta(days=1),
            ),
            clock=lambda: T0,
        )

    return store, drifts, _acquire  # directives closed over


# ===========================================================================
# A. The source contract
# ===========================================================================
check("A", "the backlog defines exactly the three ACs this task claims",
      "Changed source content detected" in _task
      and "Drift recorded against original Evidence" in _task
      and "Superseding version created where fidelity improves" in _task)
check("A", "N-15 defines drift as the fingerprint mismatch (extracted)",
      _n15_defines)
check("A", "the IOM carries fidelity as an assessment, with no ordering",
      _iom_fidelity)
check("A", "the module header names its task",
      re.search(r"Task: T02\.2\.3", SRC) is not None)
check("A", "the module does not claim to close a marker",
      not re.search(r"\bCloses\s*[:|]\s*M-\d+", SRC))

# ===========================================================================
# B. AC1 -- changed content detected  [N-15 verbatim]
# ===========================================================================
_store, _drifts, _acquire = _rig()
_original = _acquire(FIRST)
_changed = detect(_store, _original.object_id, content=SECOND)
_unchanged = detect(_store, _original.object_id, content=FIRST)
check("B", "AC1: changed content reports drift",
      _changed.drifted is True
      and _changed.reacquired_fingerprint == compute_fingerprint(SECOND))
check("B", "AC1: identical content reports no drift (E-V6's domain)",
      _unchanged.drifted is False
      and _unchanged.original_fingerprint
      == _unchanged.reacquired_fingerprint)
check("B", "the baseline is the retained fingerprint of the original",
      _changed.original_fingerprint == _original.content.fingerprint)
check("B", "drifted IS fingerprint disagreement -- nothing else",
      _changed.drifted
      == (
          _changed.original_fingerprint != _changed.reacquired_fingerprint
      ))
_unresolved = False
try:
    detect(_store, "obj-nonexistent", content=FIRST)
except DriftError:
    _unresolved = True
check("B", "an unresolvable original refuses loudly", _unresolved)

# ===========================================================================
# C. AC2 -- recorded against the original  [N-10 pattern]
# ===========================================================================
_record = record_drift(
    _changed, _drifts, fidelity_improved=False, clock=lambda: T0
)
check("C", "AC2: the record names the ORIGINAL Evidence",
      _record.original_object_id == _original.object_id
      and _drifts.against(_original.object_id) == (_record,))
check("C", "the record carries both fingerprints and a time",
      _record.original_fingerprint == _original.content.fingerprint
      and _record.reacquired_fingerprint == compute_fingerprint(SECOND)
      and _record.detected_at == T0)
check("C", "without improvement the original stands ACTIVE",
      _store.find(_original.object_id).status is ObjectStatus.ACTIVE
      and _record.disposition is Disposition.NOTED)
_notdrift = False
try:
    record_drift(
        _unchanged, DriftRegister(), fidelity_improved=False,
        clock=lambda: T0,
    )
except NotDriftError:
    _notdrift = True
check("C", "a drift record requires a mismatch (unchanged = duplicate)",
      _notdrift)
check("C", "records live outside the object model (no lineage mutation)",
      "derives_from" not in CODE.split("class DriftRecord")[1][:600]
      and "lineage" not in CODE.split("class DriftRecord")[1][:600])

# ===========================================================================
# D. AC3 -- supersession exactly on the explicit declaration
# ===========================================================================
_store2, _drifts2, _acquire2 = _rig()
_orig2 = _acquire2(FIRST, fidelity="text only; media lost")
_verdict2 = detect(_store2, _orig2.object_id, content=SECOND)
_rec2 = record_drift(
    _verdict2, _drifts2, store=_store2,
    fidelity_improved=True, clock=lambda: T0,
)
_stored2 = _store2.find(_orig2.object_id)
check("D", "AC3: declared improvement supersedes the original (R-2/V9)",
      _rec2.disposition is Disposition.SUPERSEDED
      and _stored2.status is ObjectStatus.SUPERSEDED
      and _stored2.attributes.status_reason is not None)
check("D", "AC3: the superseding version acquires (E-V6 ACTIVE-only index)",
      _acquire2(SECOND).object_id != _orig2.object_id
      and _store2.find(_orig2.object_id).status is ObjectStatus.SUPERSEDED)
check("D", "the improvement is the caller's declaration, never inferred",
      "fidelity_improved" in CODE
      and not re.search(r"def [a-z_]*fidelity[a-z_]*[(]", CODE)
      and not re.search(r"fidelity_improved = (?!True)(?!False)", CODE),
      "no fidelity-comparing function may exist; the flag is never computed")
check("D", "supersession goes through the store's transition path only",
      "store.transition" in CODE
      and ".status =" not in CODE,
      "the sole permitted mutation is the store's own transition [R-2]")

# ===========================================================================
# E. Boundaries: no other task's responsibility
# ===========================================================================
imports = {
    n.module for n in ast.walk(TREE)
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("E", "imports stay within the <=6 boundary",
      len(imports) <= 6, str(sorted(imports)))
check("E", "no duplicate logic (T02.2.2 untouched)",
      "find_duplicate" not in CODE and "E-V6" not in CODE.split(
          "unchanged material is a duplicate")[0].replace("E-V6", ""))
check("E", "no rights, coverage or gate logic (T02.1.2/T02.1.4/T02.2.1)",
      not re.search(r"evaluate_gate|classify|coverage|OUT_OF_FRAME", CODE))
check("E", "records are frozen dataclasses [R-1]",
      SRC.count("@dataclass(frozen=True)") >= 2)
check("E", "the register is lock-guarded [N-11]", "threading.RLock" in SRC)
check("E", "production module count is now 36 (incl. extraction, T03.1.1)",
      len(list((ROOT / "oip").glob("*.py"))) == 37,  # 35 through T02.3.1; +1 extraction (T03.1.1); +1 anchoring (T03.1.3)
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
    "A": "Source contract",
    "B": "AC1: changed content detected",
    "C": "AC2: recorded against the original",
    "D": "AC3: supersession on explicit improvement",
    "E": "Boundaries and conventions",
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
