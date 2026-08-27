#!/usr/bin/env python3
"""T03.1.4 adversarial probes -- canonical-claim merging per D-05.

Six attack classes, each attempting to break a guarantee the merge
machinery makes:

  PA1  unjustified merges: NOT_EQUIVALENT claims must never merge and
       must never grow a DUPLICATES link
  PA2  UNCERTAIN merges: containment-undecidable claims must stay
       separate Facts with DUPLICATES recorded (AC3), the peer untouched
  PA3  independence inflation: merging must never inflate
       independent_source_count or the independence assessment [N-16]
  PA4  version tampering: stored versions are immutable; identity replay
       and version forks are refused by the store [R-1/V11]
  PA5  duplicate replay: re-extraction of attached Evidence is refused
       (F-I2 add-only); no phantom version, no double attachment
  PA6  merge-refusal recording: every merge refusal (replay, concurrent
       race, acceptance refusal) is recorded attempted=True in the log
       and projected into the FailureStore [N-10]

A probe "holds" when the platform behaves as specified under attack.
Exit code 0 iff every probe holds.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.claim import Quantity, Verdict
from oip.configuration import FailureStore
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ObjectStatus, ObjectType
from oip.extraction import (
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    build_density_report,
    extract,
)
from oip.fact import ClaimType, Independence
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore, WriteRejectedError

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
TICK = T0 + timedelta(hours=1)
VENDOR = "VENDOR_PUBLICATION"
SPAN = "bulk edits silently fail above 50 SKUs"

RESULTS: list[tuple[str, bool, str]] = []


def probe(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


class _StubFailure:
    """FailureRecord-shaped stub for WriteRejectedError construction."""

    def __init__(self, object_id: str, rule_ids: list[str]) -> None:
        self.object_id = object_id
        self.rule_ids = rule_ids


# ---------------------------------------------------------------------------
# Rig: the acquisition path in miniature (mirrors probe_t03_1_1)
# ---------------------------------------------------------------------------


class Rig:
    def __init__(self, targets: tuple[str, ...] | None = None) -> None:
        self.registry = SourceRegistry()
        self.store = KnowledgeStore()
        self.out_of_frame = OutOfFrameRegister()
        self.refusals = RefusalRegister()
        self.acq_log = AcquisitionLog()
        self.extraction_log = ExtractionLog()
        self.failure_store = FailureStore()
        self.extraction_log.attach(self.failure_store)
        self.directives = DirectiveRegistry()
        self.directives.raise_directive(Directive(
            directive_id="dir-probe",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="probe-commissioner",
            description="T03.1.4 probe corpus",
            targets=targets or (
                "src-a", "src-b", "src-c", "src-d", "src-weak",
            ),
            raised_at=T0 - timedelta(days=1),
        ))
        self.directives.effect("dir-probe", now=T0)

    def add_source(self, identifier: str, source_type: str) -> None:
        self.registry.register(identifier, source_type)

    @property
    def log(self) -> ExtractionLog:
        return self.extraction_log

    def acquire(
        self,
        source: str,
        source_type: str,
        content: str,
        *,
        observed_at: datetime | None = None,
        support: float = 0.7,
        assertion: float = 0.9,
    ) -> str:
        request = AcquisitionRequest(
            source_identifier=source,
            source_type=source_type,
            acquisition_method="probe retrieval",
            capture_fidelity="probe corpus; full text",
            acquired_at=T0,
            observed_at=observed_at or (T0 - timedelta(hours=1)),
            evidential_support=support,
            assertion_confidence=assertion,
            content=content,
        )
        rights = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority="Designated Source Rights/Compliance Authority",
            basis="probe basis",
            assessed_at=T0 - timedelta(hours=2),
        )
        evidence = acquire(
            request,
            registry=self.registry,
            store=self.store,
            directives=self.directives,
            out_of_frame=self.out_of_frame,
            refusals=self.refusals,
            log=self.acq_log,
            assessment=rights,
            clock=lambda: T0,
        )
        return evidence.object_id

    def extraction(self, **overrides) -> ExtractionRequest:
        base = dict(
            evidence_ref="unset",
            subject="bulk edits",
            predicate="silently fail above",
            qualifying_context=(
                "per vendor changelog, for bulk edits above 50 SKUs"
            ),
            anchor=SPAN,
            claim_type=ClaimType.ASSERTION,
            extraction_confidence=0.8,
        )
        base.update(overrides)
        return ExtractionRequest(**base)


def vendor_rig(*sources: str) -> Rig:
    rig = Rig(targets=tuple(sources))
    for src in sources:
        rig.add_source(src, VENDOR)
    return rig


def active_lineage_ids(rig: Rig) -> set[str]:
    return {
        stored.lineage_id
        for stored in rig.store.objects_of_type(ObjectType.FACT)
        if rig.store.find(stored.object_id).status is ObjectStatus.ACTIVE
    }


# ===========================================================================
# PA1 -- unjustified merges: NOT_EQUIVALENT must never merge, never link
# ===========================================================================
rig1 = vendor_rig("src-a", "src-b")
ra1 = rig1.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb1 = rig1.acquire(
    "src-b", VENDOR,
    "Forum: sellers silently fail above 50 SKUs.",  # synonym subject
)
o1a = extract(rig1.extraction(evidence_ref=ra1),
              store=rig1.store, log=rig1.log, clock=lambda: TICK)
o1b = extract(rig1.extraction(
        evidence_ref=rb1, subject="sellers",
        anchor="sellers silently fail above 50 SKUs"),
    store=rig1.store, log=rig1.log, clock=lambda: TICK)
probe("PA1 synonym subject: NOT_EQUIVALENT stays separate with no link",
      o1b.merged_into is None
      and o1b.duplicates == ()
      and rig1.store.find(o1a.object_id).status is ObjectStatus.ACTIVE
      and rig1.store.get_fact(o1a.object_id).attachment_count == 1
      and rig1.store.get_fact(o1b.object_id).attachment_count == 1
      and len(active_lineage_ids(rig1)) == 2,
      f"{o1a.object_id} vs {o1b.object_id}")

# value disagreement: precision-admissible neighbour merges, distant
# value does not -- the unjustified direction must NOT merge
rig1b = vendor_rig("src-a", "src-b")
rc1 = rig1b.acquire("src-a", VENDOR, "Report: merchant fees rise 3.5%.")
rd1 = rig1b.acquire("src-b", VENDOR, "Report: merchant fees rise 9.9%.")
o1c = extract(rig1b.extraction(
        evidence_ref=rc1, subject="merchant fees", predicate="rise",
        qualifying_context="for card payments", anchor="merchant fees rise 3.5%",
        value=Quantity(3.5, 0.1, "%"), value_text="3.5%",
        claim_type=ClaimType.ASSERTION),
    store=rig1b.store, log=rig1b.log, clock=lambda: TICK)
o1d = extract(rig1b.extraction(
        evidence_ref=rd1, subject="merchant fees", predicate="rise",
        qualifying_context="for card payments", anchor="merchant fees rise 9.9%",
        value=Quantity(9.9, 0.1, "%"), value_text="9.9%",
        claim_type=ClaimType.ASSERTION),
    store=rig1b.store, log=rig1b.log, clock=lambda: TICK)
probe("PA1 distant value: no merge, no DUPLICATES link",
      o1d.merged_into is None
      and o1d.duplicates == ()
      and len(active_lineage_ids(rig1b)) == 2,
      f"{o1c.object_id} vs {o1d.object_id}")

# ===========================================================================
# PA2 -- UNCERTAIN merges: containment-undecidable stays separate (AC3)
# ===========================================================================
rig2 = vendor_rig("src-a", "src-b")
ra2 = rig2.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb2 = rig2.acquire(
    "src-b", VENDOR, "Forum: bulk edits silently fail above 60 SKUs.")
o2a = extract(rig2.extraction(evidence_ref=ra2, qualifier="above 50 SKUs"),
              store=rig2.store, log=rig2.log, clock=lambda: TICK)
o2b = extract(rig2.extraction(
        evidence_ref=rb2, qualifier="above 60 SKUs",
        anchor="bulk edits silently fail above 60 SKUs"),
    store=rig2.store, log=rig2.log, clock=lambda: TICK)
f2a = rig2.store.get_fact(o2a.object_id)
f2b = rig2.store.get_fact(o2b.object_id)
probe("PA2 UNCERTAIN qualifiers: separate Facts, DUPLICATES on the new "
      "Fact, peer untouched [AC3]",
      o2b.merged_into is None
      and o2b.duplicates == (o2a.object_id,)
      and f2b.attributes.duplicates == (o2a.object_id,)
      and f2b.attachment_count == 1
      and f2b.merge_history == ()
      and f2a.merge_history == ()
      and rig2.store.find(o2a.object_id).status is ObjectStatus.ACTIVE
      and f2a.attributes.identity.version == 1
      and {r.verdict for _, r in o2b.equivalence} == {Verdict.UNCERTAIN},
      f"{o2a.object_id} vs {o2b.object_id}")

# ===========================================================================
# PA3 -- independence inflation [N-16]
# ===========================================================================
rig3 = vendor_rig("src-a", "src-b", "src-c")
ra3 = rig3.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb3 = rig3.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
rc3 = rig3.acquire("src-c", VENDOR, f"Advisory: {SPAN}.")
o3a = extract(rig3.extraction(evidence_ref=ra3),
              store=rig3.store, log=rig3.log, clock=lambda: TICK)
o3b = extract(rig3.extraction(evidence_ref=rb3),
              store=rig3.store, log=rig3.log, clock=lambda: TICK)
o3c = extract(rig3.extraction(evidence_ref=rc3),
              store=rig3.store, log=rig3.log, clock=lambda: TICK)
f3 = rig3.store.get_fact(o3c.object_id)
probe("PA3 merging never infers independence [N-16]",
      f3.independent_source_count == 1
      and all(
          a.independence_assessment is Independence.UNASSESSED
          for a in f3.attachments
      )
      and len(active_lineage_ids(rig3)) == 1
      and f3.attachment_count == 3,
      f"count={f3.independent_source_count} over "
      f"{f3.attachment_count} attachments; the count is the FIRST fact's "
      f"own (1) and no merge bumped it")

# ===========================================================================
# PA4 -- version tampering: immutability and fork refusal [R-1/V11]
# ===========================================================================
rig4 = vendor_rig("src-a", "src-b")
ra4 = rig4.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb4 = rig4.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
o4a = extract(rig4.extraction(evidence_ref=ra4),
              store=rig4.store, log=rig4.log, clock=lambda: TICK)
o4b = extract(rig4.extraction(evidence_ref=rb4),
              store=rig4.store, log=rig4.log, clock=lambda: TICK)
f4a = rig4.store.get_fact(o4a.object_id)
tamper_refused = False
try:
    f4a.attachments = ()  # type: ignore[misc]
except Exception:
    tamper_refused = True
# identity replay: writing a NEW Fact that claims the predecessor's
# identity (same lineage/version) must be refused by the allocator
identity_replay_refused = False
from oip.contract import LineageRef, ObjectType as _OT  # noqa: E402
from oip.fact import Fact as _Fact  # noqa: E402
try:
    replayed = _Fact(
        attributes=rig4.store.get_fact(o4b.object_id).attributes,
        attachments=(),
    )
    rig4.store.write_fact(replayed)
except Exception:
    identity_replay_refused = True
versions = sorted(
    rig4.store.get_fact(s.object_id).attributes.identity.version
    for s in rig4.store.objects_of_type(ObjectType.FACT)
)
probe("PA4 stored versions immutable; identity replay refused; chain "
      "contiguous [R-1/V11]",
      tamper_refused
      and identity_replay_refused
      and versions == [1, 2]
      and rig4.store.get_fact(o4b.object_id).merge_history[-1].verdict
      is Verdict.EQUIVALENT,
      f"versions={versions}")

# ===========================================================================
# PA5 -- duplicate replay [F-I2]
# ===========================================================================
rig5 = vendor_rig("src-a", "src-b")
ra5 = rig5.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb5 = rig5.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
o5a = extract(rig5.extraction(evidence_ref=ra5),
              store=rig5.store, log=rig5.log, clock=lambda: TICK)
o5b = extract(rig5.extraction(evidence_ref=rb5),
              store=rig5.store, log=rig5.log, clock=lambda: TICK)
facts_before = sum(
    1 for _ in rig5.store.objects_of_type(ObjectType.FACT))
head_before = rig5.store.get_fact(o5b.object_id)
replay_refused = False
try:
    extract(rig5.extraction(evidence_ref=ra5),
            store=rig5.store, log=rig5.log, clock=lambda: TICK)
except ExtractionRefusedError:
    replay_refused = True
facts_after = sum(1 for _ in rig5.store.objects_of_type(ObjectType.FACT))
head_after = rig5.store.get_fact(o5b.object_id)
probe("PA5 replay refused: no phantom version, no double attachment "
      "[F-I2]",
      replay_refused
      and facts_after == facts_before
      and head_after.attachment_count == head_before.attachment_count == 2
      and head_after.attributes.identity.version == 2
      and len(active_lineage_ids(rig5)) == 1,
      f"facts {facts_before} -> {facts_after}")

# ===========================================================================
# PA6 -- merge-refusal recording [N-10]: every refusal attempted+recorded
# ===========================================================================
# (a) replay refusal projected into the FailureStore
failure_a = rig5.log.for_evidence(ra5)[-1]
probe("PA6 replay refusal recorded attempted [N-10]",
      failure_a.stage is ExtractionStage.MERGE_FAILED
      and failure_a.reason == "EVIDENCE_ALREADY_ATTACHED"
      and failure_a.attempted
      and len(rig5.failure_store) >= 1,
      f"stage={failure_a.stage} reason={failure_a.reason}")

# (b) concurrent-merge race: allocator refuses; recorded, canonical
#     untouched, under-merge outcome
rig6 = vendor_rig("src-a", "src-b")
ra6 = rig6.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb6 = rig6.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
o6a = extract(rig6.extraction(evidence_ref=ra6),
              store=rig6.store, log=rig6.log, clock=lambda: TICK)
original_succeed = rig6.store.allocator.succeed


def refusing_succeed(predecessor):
    raise RuntimeError("simulated concurrent-merge branching")


rig6.store.allocator.succeed = refusing_succeed  # type: ignore[method-assign]
race_refused = False
try:
    extract(rig6.extraction(evidence_ref=rb6),
            store=rig6.store, log=rig6.log, clock=lambda: TICK)
except ExtractionRefusedError:
    race_refused = True
finally:
    rig6.store.allocator.succeed = original_succeed  # type: ignore[method-assign]
failure_b = rig6.log.for_evidence(rb6)[-1]
probe("PA6 concurrent race recorded, canonical untouched [N-10]",
      race_refused
      and failure_b.stage is ExtractionStage.MERGE_FAILED
      and failure_b.reason == "MERGE_NOT_POSSIBLE"
      and failure_b.attempted
      and rig6.store.find(o6a.object_id).status is ObjectStatus.ACTIVE
      and rig6.store.get_fact(o6a.object_id).attachment_count == 1
      and len(rig6.failure_store) >= 1,
      f"reason={failure_b.reason}")

# (c) acceptance refusal after supersession: recorded with the exact
#     surviving state named (SUPERSEDED is terminal [R-2])
rig6b = vendor_rig("src-a", "src-b")
ra6b = rig6b.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
rb6b = rig6b.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
o6c = extract(rig6b.extraction(evidence_ref=ra6b),
              store=rig6b.store, log=rig6b.log, clock=lambda: TICK)
original_write = rig6b.store.write_fact


def refusing_write(fact, predecessor_id=None):
    if predecessor_id is not None:  # only the MERGED write
        raise WriteRejectedError(_StubFailure("obj-stub", ["V5"]))
    return original_write(fact)


rig6b.store.write_fact = refusing_write  # type: ignore[method-assign]
acceptance_refused = False
try:
    extract(rig6b.extraction(evidence_ref=rb6b),
            store=rig6b.store, log=rig6b.log, clock=lambda: TICK)
except ExtractionRefusedError:
    acceptance_refused = True
finally:
    rig6b.store.write_fact = original_write  # type: ignore[method-assign]
failure_c = rig6b.log.for_evidence(rb6b)[-1]
probe("PA6 acceptance refusal recorded with the surviving state named "
      "[N-10/R-2]",
      acceptance_refused
      and failure_c.stage is ExtractionStage.MERGE_FAILED
      and failure_c.reason == "ACCEPTANCE_REFUSED"
      and failure_c.attempted
      and "SUPERSEDED" in failure_c.detail
      and "no successor" in failure_c.detail
      and rig6b.store.find(o6c.object_id).status is ObjectStatus.SUPERSEDED
      and rig6b.store.get_fact(o6c.object_id).attachment_count == 1
      and len(active_lineage_ids(rig6b)) == 0
      and len(rig6b.failure_store) >= 1,
      f"reason={failure_c.reason}")

# (d) density integrity after refusals: only ACTIVE Facts counted
report = build_density_report(rig5.store, rig5.log)
probe("PA6 density counts ACTIVE attachments only after merges",
      all(row.claims >= 0 for row in report.rows)
      and sum(row.claims for row in report.rows)
      == sum(
          rig5.store.get_fact(s.object_id).attachment_count
          for s in rig5.store.objects_of_type(ObjectType.FACT)
          if rig5.store.find(s.object_id).status is ObjectStatus.ACTIVE
      ),
      f"total={sum(row.claims for row in report.rows)}")

# ---------------------------------------------------------------------------
held = sum(1 for _, ok, _ in RESULTS if ok)
for name, ok, detail in RESULTS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}  [{detail}]"
          if not ok else f"  ok   {name}")
print(f"\nPROBES: {held}/{len(RESULTS)} held")
sys.exit(0 if held == len(RESULTS) else 1)
