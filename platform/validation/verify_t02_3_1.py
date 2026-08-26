"""T02.3.1 — Phase-2 Exit Gate verification.

Proves the three acceptance criteria mechanically against the backlog
and the ratified corpus, using the eight Quratex-approved sources:

  AC1  Evidence acquired from every defined source type
  AC2  Duplicate detection demonstrated
  AC3  Coverage gaps declared

This is the P2 exit report: a single executable that registers the
sources, issues rights assessments, activates the directive, acquires
Evidence for all 8 types, demonstrates duplicate rejection (E-V6),
and produces the coverage report.

Fails closed: a check that cannot be performed counts as a failure.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

# -- production modules -----------------------------------------------------
from oip.source import SourceRegistry, taxonomy_members
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.rights import (
    RIGHTS_AUTHORITY_ROLE, AcquisitionRight, RefusalRegister,
    RetentionRight, RightsAssessment,
)
from oip.acquisition import (
    AcquisitionFailure, AcquisitionLog, AcquisitionRequest, AcquisitionStage,
    acquire,
)
from oip.coverage import (
    CoverageReport, GapRegister, OutOfFrameRegister, measure_coverage,
)
from oip.configuration import FailureStore
from oip.duplicates import duplicate_refusals
from oip.store import KnowledgeStore
from oip.enums import ObjectStatus

# -- evidence data (Quratex-approved) ----------------------------------------
from t0231_evidence import (
    AUTHORITY, COMMISSIONING_AUTHORITY, EVIDENCE, RESEARCH_SUBJECT,
    REQUIRED_TYPES, T0,
)

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


# ===========================================================================
# BUILD: register → directive → rights → acquire ×8
# ===========================================================================

registry = SourceRegistry()
store = KnowledgeStore()
out_of_frame = OutOfFrameRegister()
refusals = RefusalRegister()
acq_log = AcquisitionLog()
failure_store = FailureStore()
acq_log.attach(failure_store)
directives = DirectiveRegistry()

# -- 1. Register all sources -------------------------------------------------
for rec in EVIDENCE:
    registry.register(rec["source_identifier"], rec["source_type"])

# -- 2. Raise + effect the directive -----------------------------------------
directive = Directive(
    directive_id="dir-p2-exit",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description=RESEARCH_SUBJECT,
    targets=tuple(rec["source_identifier"] for rec in EVIDENCE),
    raised_at=T0 - timedelta(days=3),
)
directives.raise_directive(directive)
directives.effect("dir-p2-exit", now=T0)

# -- 3. Issue rights assessments (Quratex, via the N-24 role) ------------------
rights_map: dict[str, RightsAssessment] = {}
for rec in EVIDENCE:
    rights_map[rec["source_identifier"]] = RightsAssessment(
        source_identifier=rec["source_identifier"],
        acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_FULL,
        authority=AUTHORITY,
        basis=rec["rights_basis"],
        assessed_at=T0,
    )

# -- 4. Acquire all 8 ----------------------------------------------------------
evidence_objects: dict[str, object] = {}
for rec in EVIDENCE:
    request = AcquisitionRequest(
        source_identifier=rec["source_identifier"],
        source_type=rec["source_type"],
        acquisition_method=rec["acquisition_method"],
        capture_fidelity=rec["capture_fidelity"],
        acquired_at=rec["acquired_at"],
        observed_at=rec["observed_at"],
        evidential_support=rec["evidential_support"],
        assertion_confidence=rec["assertion_confidence"],
        content=rec["content"],
    )
    ev = acquire(
        request,
        registry=registry,
        store=store,
        out_of_frame=out_of_frame,
        refusals=refusals,
        log=acq_log,
        assessment=rights_map[rec["source_identifier"]],
        directives=directives,
        clock=lambda t=rec["acquired_at"]: t,
    )
    evidence_objects[rec["source_type"]] = ev

# ===========================================================================
# AC2: duplicate acquisition (same material, same source) → E-V6 refusal
# ===========================================================================
_dup_refused = False
try:
    dup_request = AcquisitionRequest(
        source_identifier=EVIDENCE[0]["source_identifier"],
        source_type=EVIDENCE[0]["source_type"],
        acquisition_method=EVIDENCE[0]["acquisition_method"],
        capture_fidelity=EVIDENCE[0]["capture_fidelity"],
        acquired_at=T0,
        observed_at=EVIDENCE[0]["observed_at"],
        evidential_support=EVIDENCE[0]["evidential_support"],
        assertion_confidence=EVIDENCE[0]["assertion_confidence"],
        content=EVIDENCE[0]["content"],  # same material
    )
    acquire(
        dup_request,
        registry=registry,
        store=store,
        out_of_frame=out_of_frame,
        refusals=refusals,
        log=acq_log,
        assessment=rights_map[EVIDENCE[0]["source_identifier"]],
        directives=directives,
        clock=lambda: T0,
    )
except Exception as exc:
    _dup_refused = "E-V6" in str(exc)

# ===========================================================================
# AC3: coverage report
# ===========================================================================
active_types = tuple(
    ev.provenance.source_type for ev in evidence_objects.values()
)
gap_register = GapRegister()
coverage_report = measure_coverage(
    active_types, gap_register, out_of_frame
)

# ===========================================================================
# VERIFY — AC1
# ===========================================================================
check("A", "AC1: Evidence acquired from every defined source type",
      len(evidence_objects) == 8
      and set(evidence_objects.keys()) == REQUIRED_TYPES
      and REQUIRED_TYPES == frozenset(
          m.value for m in taxonomy_members()
      ),
      f"acquired={sorted(evidence_objects.keys())} "
      f"required={sorted(REQUIRED_TYPES)}")

check("A", "AC1: every acquisition went through all three gates",
      all(
          ev.attributes.explanation is not None
          and any("gate-1" in c for c in
                  ev.attributes.explanation.criteria_applied)
          and any("gate-2" in c for c in
                  ev.attributes.explanation.criteria_applied)
          and any("gate-3" in c for c in
                  ev.attributes.explanation.criteria_applied)
          for ev in evidence_objects.values()
      ))

check("A", "AC1: provenance complete on every Evidence object",
      all(
          all(
              str(getattr(ev.provenance, f) or "").strip()
              for f in (
                  "source_identifier", "source_type",
                  "acquisition_method", "access_conditions",
                  "capture_fidelity",
              )
          )
          and ev.provenance.acquired_at is not None
          for ev in evidence_objects.values()
      ))

check("A", "AC1: all 8 persisted and retrievable in the store",
      all(
          store.get_evidence(ev.object_id) is not None
          for ev in evidence_objects.values()
      ) and len(store) == 8)

# ===========================================================================
# VERIFY — AC2
# ===========================================================================
check("B", "AC2: duplicate acquisition refused with E-V6",
      _dup_refused)

check("B", "AC2: the refusal is classified DUPLICATE_ACQUISITION",
      any(
          f.stage is AcquisitionStage.DUPLICATE_ACQUISITION
          for f in acq_log
      ))

check("B", "AC2: the refusal is recorded in the N-10 FailureStore",
      any(
          "E-V6" in r.nature[0] for r in failure_store.all()
      ))

check("B", "AC2: duplicate_rate is computable from recorded facts",
      duplicate_refusals(acq_log) == 1)

# ===========================================================================
# VERIFY — AC3
# ===========================================================================
check("C", "AC3: coverage = 8/8 = 1.0 (all types represented)",
      coverage_report.coverage == 1.0
      and coverage_report.frame_size == 8
      and len(coverage_report.represented) == 8)

check("C", "AC3: zero coverage gaps (declared-complete)",
      coverage_report.gaps == ()
      and coverage_report.declared_complete is True)

check("C", "AC3: coverage report carries out_of_frame beside coverage",
      coverage_report.out_of_frame == out_of_frame.count())

check("C", "AC3: report is descriptive, never a gate",
      not hasattr(coverage_report, "reject")
      and not hasattr(coverage_report, "accept"))

# ===========================================================================
# VERIFY — structural invariants
# ===========================================================================
check("D", "the directive was IN_EFFECT and covered all targets",
      directives.state_of("dir-p2-exit", now=T0).value == "IN_EFFECT"
      and all(
          directives.covers(rec["source_identifier"], T0) is not None
          for rec in EVIDENCE
      ))

check("D", "all rights assessments attributed to the N-24 role",
      all(
          ra.authority == AUTHORITY
          for ra in rights_map.values()
      ) and AUTHORITY == "Designated Source Rights/Compliance Authority")

check("D", "all 8 rights = PERMITTED + RETAIN_FULL",
      all(
          ra.acquisition is AcquisitionRight.PERMITTED
          and ra.retention is RetentionRight.RETAIN_FULL
          for ra in rights_map.values()
      ))

check("D", "no source outside the 8 was registered",
      len(registry) == 8)

check("D", "no rejection from gates 1-3 for the 8 primary acquisitions",
      not any(
          f.stage in (
              AcquisitionStage.OUT_OF_SCOPE,
              AcquisitionStage.UNTYPABLE_CHANNEL,
              AcquisitionStage.REFUSED_BY_RIGHTS,
          )
          for f in acq_log
          if f.source_identifier != EVIDENCE[0]["source_identifier"]
      ))

# ===========================================================================
# Report
# ===========================================================================
failed = [(s, n, d) for s, n, ok, d in RESULTS if not ok]
by: dict[str, list] = {}
for s, n, ok, d in RESULTS:
    by.setdefault(s, []).append((n, ok, d))

TITLES = {
    "A": "AC1: Evidence from every source type",
    "B": "AC2: Duplicate detection demonstrated",
    "C": "AC3: Coverage gaps declared",
    "D": "Structural invariants",
}

print("=" * 72)
print("T02.3.1 — PHASE-2 EXIT GATE REPORT")
print("=" * 72)
print(f"\nAcquisition timestamp: {T0.isoformat()}")
print(f"Sources registered:   {len(registry)}")
print(f"Evidence persisted:   {len(store)}")
print(f"Coverage:             {coverage_report.coverage} "
      f"({len(coverage_report.represented)}/{coverage_report.frame_size})")
print(f"Gaps:                 {len(coverage_report.gaps)}")
print(f"Out-of-frame:         {coverage_report.out_of_frame}")
print(f"Duplicate refusals:   {duplicate_refusals(acq_log)}")
print(f"FailureStore records: {len(failure_store)}")

for s in sorted(by):
    entries = by[s]
    ok_n = sum(1 for _, ok, _ in entries if ok)
    print(f"\n=== {s}. {TITLES[s]} ({ok_n}/{len(entries)}) ===")
    for n, ok, d in entries:
        line = f"  {'ok  ' if ok else 'FAIL'} {n}"
        if d and not ok:
            line += f"  -> {d}"
        print(line)

total = len(RESULTS)
passed = total - len(failed)
print(f"\n{'=' * 72}")
print(f"RESULT: {passed}/{total} checks passed")
if failed:
    print("\nFAILURES:")
    for s, n, d in failed:
        print(f"  [{s}] {n}" + (f"  -> {d}" if d else ""))
    sys.exit(1)
else:
    print("\nALL CHECKS PASSED — PHASE 2 EXIT GATE SATISFIED")
    print("  AC1 ✓  AC2 ✓  AC3 ✓")
    sys.exit(0)
