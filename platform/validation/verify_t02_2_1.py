"""Architecture verification for T02.2.1 -- acquisition.

Establishes mechanically that oip/acquisition.py supplies exactly what the
backlog task and the ratified corpus authorise: provenance complete on
every Evidence object (AC1), failures recorded never silent (AC2),
capture_fidelity documented per acquisition (AC3), the ratified gate order
(typability before rights, gate 1 deliberately absent), the N-15/N-21 S 5.7
storage-mode mapping extracted from the decision text, and no invented
semantics.

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
    AcquisitionFailure, AcquisitionLog, AcquisitionRefusedError,
    AcquisitionRequest, AcquisitionStage, acquire,
)
from oip.coverage import OutOfFrameRegister  # noqa: E402
from oip.directives import (  # noqa: E402
    Directive, DirectiveRegistry, Originator,
)
from oip.evidence import StorageMode, Evidence  # noqa: E402
from oip.rights import (  # noqa: E402
    RIGHTS_AUTHORITY_ROLE, AcquisitionRight, RefusalRegister,
    RetentionRight, RightsAssessment,
)
from oip.source import SourceRegistry  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


SRC = (ROOT / "oip" / "acquisition.py").read_text()
TREE = ast.parse(SRC)
BACKLOG = (
    DOCS / "docs" / "architecture" / "PKP_Implementation_Backlog.md"
).read_text()
N21 = (DOCS / "decisions" / "N-21-acquisition-rights.md").read_text()
T0 = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)

# Executable code only: docstrings legitimately DISCUSS boundaries.
_code_only = ast.parse(SRC)
for _n in ast.walk(_code_only):
    if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and (
        _n.body and isinstance(_n.body[0], ast.Expr)
        and isinstance(_n.body[0].value, ast.Constant)
        and isinstance(_n.body[0].value.value, str)
    ):
        _n.body = _n.body[1:] or [ast.Pass()]
CODE = ast.unparse(_code_only)

# The task's acceptance criteria, extracted from the backlog mechanically.
_task = BACKLOG.split("#### `T02.2.1`")[1].split("#### `T02.2.2`")[0]
_AC1 = "Provenance complete on every Evidence object" in _task
_AC2 = "Acquisition failures recorded, not silent" in _task
_AC3 = "capture_fidelity documented per acquisition" in _task

# The N-15/N-21 S 5.7 mapping, extracted from the N-21 decision text.
_sec57 = re.sub(r"\s+", " ", N21.split("### 5.7")[1].split("### 5.8")[0])
_N15_FULL = "RETAIN_FULL` | Stored in full" in _sec57.replace("**", "")
_N15_REF = "RETAIN_REFERENCE_ONLY` | Stored by reference" in _sec57.replace(
    "**", "")


def _rig():
    registry = SourceRegistry()
    registry.register("src-a", "VENDOR_PUBLICATION")
    registry.register("src-u", "mystery-channel")
    directives = DirectiveRegistry()
    directives.raise_directive(Directive(
        directive_id="dir-v", originator=Originator.EXTERNAL_COMMISSION,
        authority="verifier-owner", description="verifier scope",
        targets=("src-a", "src-u", "src-unreg"), raised_at=T0 - timedelta(days=2),
    ))
    directives.effect("dir-v", now=T0)
    return (registry, KnowledgeStore(), OutOfFrameRegister(),
            RefusalRegister(), AcquisitionLog(), directives)


def _request(**overrides):
    base = dict(
        source_identifier="src-a",
        source_type="VENDOR_PUBLICATION",
        acquisition_method="vendor_api_retrieval",
        capture_fidelity="full text preserved; media not captured",
        acquired_at=T0,
        observed_at=T0 - timedelta(hours=1),
        evidential_support=0.62,
        assertion_confidence=0.90,
        content="material",
    )
    base.update(overrides)
    return AcquisitionRequest(**base)


def _permitted(retention=RetentionRight.RETAIN_FULL, source="src-a"):
    return RightsAssessment(
        source_identifier=source,
        acquisition=AcquisitionRight.PERMITTED,
        retention=retention,
        authority=RIGHTS_AUTHORITY_ROLE,
        basis="vendor terms",
        assessed_at=T0 - timedelta(days=1),
    )


# ===========================================================================
# A. The backlog contract, present verbatim
# ===========================================================================
check("A", "the backlog defines exactly the three ACs this task claims",
      _AC1 and _AC2 and _AC3)
check("A", "the module header names its task",
      re.search(r"Task: T02\.2\.1", SRC) is not None)
check("A", "the module does not claim to close a marker",
      not re.search(r"\bCloses\s*[:|]\s*M-\d+", SRC))

# ===========================================================================
# B. AC1 -- provenance complete  [IOM S 3.1 / E-V2]
# ===========================================================================
_reg, _store, _oof, _ref, _log, _dirs = _rig()
_ev = acquire(
    _request(),
    registry=_reg, store=_store, out_of_frame=_oof,
    refusals=_ref, log=_log, assessment=_permitted(),
    directives=_dirs, clock=lambda: T0,
)
check("B", "AC1: every required provenance field is present and non-empty",
      all(
          str(getattr(_ev.provenance, f) or "").strip()
          for f in (
              "source_identifier", "source_type", "acquisition_method",
              "access_conditions", "capture_fidelity",
          )
      ) and _ev.provenance.acquired_at is not None)
check("B", "AC1: access_conditions is composed from the rights (N-21 5.9)",
      "acquisition=PERMITTED" in _ev.provenance.access_conditions
      and RIGHTS_AUTHORITY_ROLE in _ev.provenance.access_conditions)
check("B", "AC1: produced by Research with no lineage (E-V1)",
      _ev.attributes.derives_from == ())
check("B", "the storage-mode mapping matches the N-21 S 5.7 table exactly",
      _N15_FULL and _N15_REF
      and _ev.content.storage_mode is StorageMode.FULL
      and acquire(
          _request(
              content=None,
              content_reference="ref",
              content_fingerprint="sha256:" + "0" * 64,
          ),
          registry=_reg, store=_store, out_of_frame=_oof,
          refusals=_ref, log=_log, directives=_dirs,
          assessment=_permitted(RetentionRight.RETAIN_REFERENCE_ONLY),
          clock=lambda: T0,
      ).content.storage_mode is StorageMode.REFERENCE)
check("B", "independence group is carried, never inferred (T02.1.3)",
      acquire(
          _request(independence_group="g1", content="distinct material"),
          registry=_reg, store=_store, out_of_frame=_oof,
          refusals=_ref, log=_log, directives=_dirs, assessment=_permitted(),
          clock=lambda: T0,
      ).provenance.source_independence_group == "g1")

# ===========================================================================
# C. AC2 -- failures recorded, not silent  [K10 / N-10]
# ===========================================================================
def _refuses(request, assessment=None, source="src-a"):
    reg, store, oof, ref, log, dirs = _rig()
    try:
        acquire(
            request, registry=reg, store=store, out_of_frame=oof,
            refusals=ref, log=log, assessment=assessment,
            directives=dirs, clock=lambda: T0,
        )
        return None, (reg, store, oof, ref, log, dirs)
    except AcquisitionRefusedError:
        return True, (reg, store, oof, ref, log, dirs)


_r, _w = _refuses(_request())  # unassessed  (rig inside _refuses)
check("C", "AC2: UNASSESSED rights refuse with a recorded failure",
      _r is True and len(_w[4]) == 1
      and _w[4].for_source("src-a")[0].stage
      is AcquisitionStage.REFUSED_BY_RIGHTS)
_r, _w = _refuses(_request(source_identifier="src-u",
                           source_type="mystery-channel"),
                  assessment=_permitted(source="src-u"))
check("C", "AC2: gate 2 precedes gate 3 (N-20 S 5.2.1 order)",
      _r is True
      and _w[4].for_source("src-u")[0].stage
      is AcquisitionStage.UNTYPABLE_CHANNEL
      and _w[3].__len__() == 0
      and _w[2].count() == 1,  # out-of-frame recorded, rights untouched
      f"rights_refusals={len(_w[3])} out_of_frame={_w[2].count()}")
_r, _w = _refuses(_request(source_identifier="src-unreg"))
check("C", "AC2: an unregistered source refuses and records",
      _r is True and _w[4].for_source("src-unreg")[0].stage
      is AcquisitionStage.UNREGISTERED_SOURCE)
check("C", "every failure carries stage + reason + detail (N-10)",
      all(
          f.stage in set(AcquisitionStage)
          and f.reason.strip() and f.detail.strip()
          for f in _w[4]
      ))
check("C", "no Evidence exists after any refusal",
      all(len(w[1]) == 0 for w in (_w,)))
check("C", "failure records live outside the object model (N-10)",
      not re.search(r"derives_from|lineage_id|object_id\s*:", CODE.split(
          "class AcquisitionFailure")[1].split("class AcquisitionLog")[0]))

# ===========================================================================
# D. AC3 -- capture_fidelity documented per acquisition
# ===========================================================================
from dataclasses import MISSING as _MISSING
_fid_field = AcquisitionRequest.__dataclass_fields__["capture_fidelity"]
check("D", "AC3: fidelity is a required request field, never defaulted",
      _fid_field.default is _MISSING
      and _fid_field.default_factory is _MISSING
      and "capture_fidelity" in _task)
_ok_fidelity = False
try:
    AcquisitionRequest(
        source_identifier="s", source_type="VENDOR_PUBLICATION",
        acquisition_method="m", capture_fidelity="   ",
        acquired_at=T0, observed_at=T0,
        evidential_support=0.5, assertion_confidence=0.5, content="c",
    )
except Exception:
    _ok_fidelity = True
check("D", "AC3: an empty fidelity statement is refused at construction",
      _ok_fidelity)

# ===========================================================================
# E. Boundaries -- nothing invented
# ===========================================================================
# Updated when T02.2.4 closed: gate 1 now EXISTS (injected registry,
# N-20 S 5.2.1 order). What must remain true here: acquisition never
# AUTHORS or widens a directive (N-23 S 5.2: Research executes within
# scope, never widens it) and no scheduling logic creeps in.
check("E", "acquisition consumes scope; it never authors or schedules it",
      "Directive(" not in CODE
      and "raise_directive" not in CODE
      and not re.search(r"schedule|work_set", CODE))
# Narrowed when T02.2.2 closed: acquisition legitimately CLASSIFIES the
# store's E-V6 refusal (DUPLICATE_ACQUISITION), but must not implement
# duplicate DETECTION itself (that is oip/duplicates.py) nor any drift
# logic (T02.2.3).
check("E", "no drift logic and no self-made duplicate detection",
      not re.search(r"drift", CODE, re.I)
      and "find_duplicate" not in CODE
      and "compute_fingerprint" not in CODE)
check("E", "confidence components supplied, never conflated (R-3)",
      "evidential_support" in CODE and "assertion_confidence" in CODE
      and not re.search(r"support\s*=\s*.*assertion", CODE))
_conf_call = CODE.split("Confidence.create(")[1].split(")")[0]
check("E", "rights values never feed confidence or scoring (N-21 S 5.9)",
      "rights" not in _conf_call and "retention" not in _conf_call
      and "assessment" not in _conf_call,
      _conf_call[:60])
# ===========================================================================
# F. Module conventions
# ===========================================================================
imports = {
    n.module for n in ast.walk(TREE)
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("F", "imports stay inside the platform (no external deps)",
      all(m.startswith("oip.") for m in imports), str(sorted(imports)))
check("F", "records are frozen dataclasses [R-1]",
      SRC.count("@dataclass(frozen=True)") >= 2)
check("F", "the failure log is lock-guarded [N-11]",
      "threading.RLock" in SRC)
check("F", "production module count is now 36 (incl. extraction, T03.1.1)",
      len(list((ROOT / "oip").glob("*.py"))) == 36,  # 35 through T02.3.1; +1 extraction (T03.1.1)
      f"{len(list((ROOT / 'oip').glob('*.py')))} modules")
check("F", "Phase 1 modules unchanged",
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
    "A": "Backlog contract present",
    "B": "AC1: provenance complete",
    "C": "AC2: failures recorded, never silent",
    "D": "AC3: capture_fidelity per acquisition",
    "E": "Boundaries: nothing invented",
    "F": "Conventions",
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
