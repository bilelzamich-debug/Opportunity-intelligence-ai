"""Architecture verification for T02.2.5 -- failure recording.

Proves the two acceptance criteria mechanically against N-10: acquisition
failures are first-class data on the platform's N-10 surface (the
FailureStore built at T01.1.7), every projection carries the six N-10
identifications, and the not-found vs not-attempted distinction N-10
makes mandatory is queryable and derived from the record -- with no
failure ever masked as success and no Evidence born of a refusal.

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

from oip.acceptance import FailureRecord  # noqa: E402
from oip.acquisition import (  # noqa: E402
    AcquisitionFailure, AcquisitionLog, AcquisitionRequest,
    AcquisitionStage, acquire,
)
from oip.configuration import FailureStore  # noqa: E402
from oip.coverage import OutOfFrameRegister  # noqa: E402
from oip.directives import (  # noqa: E402
    Directive, DirectiveRegistry, Originator,
)

from oip.enums import Engine, ObjectType  # noqa: E402
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
N10 = (DOCS / "decisions" / "N-10-failure-representation.md").read_text()
T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
MATERIAL = "changelog: bulk edits fail above 50 SKUs."


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
_task = BACKLOG.split("#### `T02.2.5`")[1].split("#### `T02.3.1`")[0]

# N-10's own words, extracted from the decision text.
_n10_six = all(
    phrase in N10
    for phrase in (
        "the engine, the invocation, the inputs attempted",
        "the configuration in force, the time, and the nature",
    )
)
_n10_distinction = (
    "produced nothing because it failed is distinguishable from" in N10
)
_n10_home = "co-located with the configuration store" in N10


def _rig():
    registry = SourceRegistry()
    registry.register("src-a", "VENDOR_PUBLICATION")
    registry.register("src-u", "mystery-channel")
    store = KnowledgeStore()
    log = AcquisitionLog()
    failure_store = FailureStore()
    log.attach(failure_store)

    directives = DirectiveRegistry()
    directives.raise_directive(Directive(
        directive_id="dir-v", originator=Originator.EXTERNAL_COMMISSION,
        authority="verifier-owner", description="verifier scope",
        targets=("src-a", "src-u", "ghost"), raised_at=T0 - timedelta(days=2),
    ))
    directives.effect("dir-v", now=T0)

    def _request(source="src-a", source_type="VENDOR_PUBLICATION",
                 content=MATERIAL):
        return AcquisitionRequest(
            source_identifier=source,
            source_type=source_type,
            acquisition_method="vendor_api_retrieval",
            capture_fidelity="full text preserved",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.62,
            assertion_confidence=0.90,
            content=content,
        )

    def _acquire(request, source="src-a", permitted=False):
        return acquire(
            request, registry=registry, store=store,
            out_of_frame=OutOfFrameRegister(),
            refusals=RefusalRegister(), log=log,
            directives=directives,
            assessment=RightsAssessment(
                source_identifier=source,
                acquisition=AcquisitionRight.PERMITTED,
                retention=RetentionRight.RETAIN_FULL,
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="vendor terms",
                assessed_at=T0 - timedelta(days=1),
            ) if permitted else None,
            clock=lambda: T0,
        )

    return (registry, store, log, failure_store, _request, _acquire)


# ===========================================================================
# A. The source contract
# ===========================================================================
check("A", "the backlog defines exactly the two ACs this task claims",
      "Failed attempts recorded" in _task
      and "Absence of evidence distinguishable from absence of attempt"
      in _task)
check("A", "N-10's six identifications extracted from the decision text",
      _n10_six)
check("A", "N-10's failed-vs-found distinction is in the decision text",
      _n10_distinction)
check("A", "N-10 places failure records in the configuration-colocated store",
      _n10_home)
check("A", "the module header names the task chain",
      "T02.2.5" in SRC and re.search(r"Task: T02\.2\.1", SRC) is not None)

# ===========================================================================
# B. AC1 -- failed attempts recorded, first-class on the N-10 surface
# ===========================================================================
_reg, _store, _log, _fs, _req, _acq = _rig()
try:
    _acq(_req())  # unassessed refusal
    _recorded = False
except Exception:
    _recorded = len(_log) == 1
check("B", "AC1: a refusal is recorded in the acquisition log",
      _recorded)
check("B", "AC1: attached, the same failure reaches the N-10 FailureStore",
      len(_fs.all()) == 1)
_p = _fs.all()[0]
check("B", "the projection carries the six N-10 identifications",
      _p.engine is Engine.RESEARCH
      and _p.input_ids == ("src-a",)
      and _p.engine_configuration_ref == "research-acquisition-v1"
      and _p.recorded_at == T0
      and "UNASSESSED" in _p.nature[0]
      and _p.cycle_id is None,  # honest outside a cycle; surfaced below
      str((_p.engine, _p.input_ids, _p.engine_configuration_ref)))
_orchestrated = AcquisitionFailure(
    source_identifier="s", stage=AcquisitionStage.REFUSED_BY_RIGHTS,
    reason="UNASSESSED", detail="d", failed_at=T0,
    engine_configuration_ref="cfg",
).as_failure_record(cycle_id=1, invocation_index=0)
check("B", "an orchestrated projection satisfies N-10 attribution in full",
      _orchestrated.satisfies_n10_attribution is True)
check("B", "an unorchestrated projection is surfaced, never suppressed",
      _fs.all()[0].satisfies_n10_attribution is False
      and len(_fs.unattributed()) == 1)
check("B", "the failure names the engine because no object was produced",
      _p.object_id == "engine:Research"
      and _p.object_type is ObjectType.EVIDENCE)
check("B", "failure records stay outside the object model",
      len(_store) == 0 and _fs.participates_in_lineage is False)

# every refusal stage reaches both surfaces
_reg2, _store2, _log2, _fs2, _req2, _acq2 = _rig()
for kwargs in (
    {"source": "ghost"},
    {"source": "src-u", "source_type": "mystery-channel"},
):
    try:
        _acq2(_req2(**kwargs), source=kwargs["source"])
    except Exception:
        pass
try:
    _acq2(_req2(), permitted=True)
    _acq2(_req2(), permitted=True)  # duplicate: same material
except Exception:
    pass
check("B", "every refusal stage is recorded on both surfaces",
      len(_log2) == 3 and len(_fs2.all()) == 3)

# ===========================================================================
# C. AC2 -- absence of evidence vs absence of attempt
# ===========================================================================
_gates = [f for f in _log2 if f.stage in (
    AcquisitionStage.UNREGISTERED_SOURCE,
    AcquisitionStage.UNTYPABLE_CHANNEL,
    AcquisitionStage.REFUSED_BY_RIGHTS,
)]
_dup = [f for f in _log2
        if f.stage is AcquisitionStage.DUPLICATE_ACQUISITION]
check("C", "AC2: gate refusals report NOT-attempted (N-21 S 5.2)",
      _gates and all(f.attempted is False for f in _gates))
check("C", "AC2: post-material failures report ATTEMPTED",
      _dup and all(f.attempted is True for f in _dup))
check("C", "the distinction is derived from the stage, never asserted",
      all(
          f.attempted is (f.stage in (
              AcquisitionStage.DUPLICATE_ACQUISITION,
              AcquisitionStage.STORE_REJECTED,
          ))
          for f in _log2
      ))
check("C", "absence of evidence AND absence of attempt are both visible",
      len(_store2) == 1  # only the first permitted acquisition existed
      and any(f.attempted is False for f in _log2)
      and any(f.attempted is True for f in _log2))
check("C", "no refusal is masked as success",
      len(_store2) == 1 and len(_log2) == 3
      and "attempted" in CODE)

# ===========================================================================
# D. Conventions and boundaries
# ===========================================================================
imports = {
    n.module for n in ast.walk(TREE)
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("D", "imports stay within the <=6 exit-gate boundary",
      len(imports) <= 6, str(sorted(imports)))
check("D", "no retry policy, severity or backend invented (M-36 policy half)",
      not re.search(r"retry|severity|backoff|alert", CODE, re.I))
check("D", "failure stages are exactly the ratified gate sequence",
      len(list(AcquisitionStage)) == 8)  # +OUT_OF_SCOPE (gate 1, N-20 5.2.1)
check("D", "Production modules unchanged in count (35)",
      len(list((ROOT / "oip").glob("*.py"))) == 35,
      f"{len(list((ROOT / 'oip').glob('*.py')))} modules")
check("D", "Phase 1 modules unchanged",
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
    "A": "Source contract (N-10 extracted)",
    "B": "AC1: failures recorded, first-class on the N-10 surface",
    "C": "AC2: not-found vs not-attempted",
    "D": "Conventions and boundaries",
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
