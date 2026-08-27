#!/usr/bin/env python3
"""T03.1.4 dedicated acceptance verifier -- canonical-claim merging per D-05.

Proves the three backlog acceptance criteria MECHANICALLY, from store
state (lineage sets, versions, statuses, attachment counts) rather than
from outcome fields alone:

  AC1  an equivalent extraction adds an attachment to an existing Fact,
       not a new Fact
  AC2  the merge produces a new Fact version
  AC3  an uncertain equivalence produces DUPLICATES, never a merge

Plus the invariant pins the merge machinery must hold at the same time:
R-3/V5 ceiling re-derivation over the widened upstream set, F-I2
add-only attachments and chain integrity, N-16 independence semantics,
T03.1.3 anchor registration, N-10 refusal recording, density
ACTIVE-only counting, and the pinned MERGE_POLICY table.

Exit code 0 iff every check passes.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.claim import MERGE_POLICY, MergeAction, Verdict
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
    resolve_locator,
)
from oip.fact import ClaimType, Independence
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(hours=1)  # first extraction clock
T2 = T0 + timedelta(hours=2)  # merging extraction clock
VENDOR = "VENDOR_PUBLICATION"
SPAN = "bulk edits silently fail above 50 SKUs"

CHECKS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    CHECKS.append((section, name, bool(cond), detail))


# ---------------------------------------------------------------------------
# Rig: the acquisition path in miniature (mirrors probe_t03_1_4)
# ---------------------------------------------------------------------------


class Rig:
    def __init__(self, targets: tuple[str, ...]) -> None:
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
            directive_id="dir-verify",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="verify-commissioner",
            description="T03.1.4 verification corpus",
            targets=targets,
            raised_at=T0 - timedelta(days=1),
        ))
        self.directives.effect("dir-verify", now=T0)

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
        support: float = 0.7,
        assertion: float = 0.9,
    ) -> str:
        request = AcquisitionRequest(
            source_identifier=source,
            source_type=source_type,
            acquisition_method="verification retrieval",
            capture_fidelity="verification corpus; full text",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=support,
            assertion_confidence=assertion,
            content=content,
        )
        rights = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority="Designated Source Rights/Compliance Authority",
            basis="verification basis",
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


def fact_objects(rig: Rig) -> list:
    return list(rig.store.objects_of_type(ObjectType.FACT))


def active_lineage_ids(rig: Rig) -> set[str]:
    return {
        stored.lineage_id
        for stored in fact_objects(rig)
        if rig.store.find(stored.object_id).status is ObjectStatus.ACTIVE
    }


def head_of(rig: Rig, lineage_id: str):
    heads = [
        rig.store.get_fact(s.object_id)
        for s in fact_objects(rig)
        if s.lineage_id == lineage_id
        and rig.store.find(s.object_id).status is ObjectStatus.ACTIVE
    ]
    return heads[0] if heads else None


# ===========================================================================
# Corpus: vendor changelog (strong), forum repost (equivalent), weak
# advisory (equivalent, weak source), qualified variant (uncertain),
# synonym variant (not equivalent)
# ===========================================================================
rig = Rig(targets=("src-vendor", "src-forum", "src-weak", "src-variant",
                   "src-synonym"))
for src in ("src-vendor", "src-forum", "src-weak", "src-variant",
            "src-synonym"):
    rig.add_source(src, VENDOR)
ref_vendor = rig.acquire("src-vendor", VENDOR, f"Changelog: {SPAN}.",
                         support=0.85)
ref_forum = rig.acquire("src-forum", VENDOR, f"Forum: {SPAN}.",
                        support=0.75)
ref_weak = rig.acquire("src-weak", VENDOR, f"Advisory: {SPAN}.",
                       support=0.3)
ref_variant = rig.acquire(
    "src-variant", VENDOR, "Forum: bulk edits silently fail above 60 SKUs.")
ref_synonym = rig.acquire(
    "src-synonym", VENDOR, "Thread: sellers silently fail above 50 SKUs.")

# ===========================================================================
# A. AC1 -- equivalent claim adds an attachment, not a new Fact
# ===========================================================================
first = extract(rig.extraction(evidence_ref=ref_vendor),
                store=rig.store, log=rig.log, clock=lambda: T1)
lineages_after_first = active_lineage_ids(rig)
facts_after_first = len(fact_objects(rig))

second = extract(rig.extraction(evidence_ref=ref_forum),
                 store=rig.store, log=rig.log, clock=lambda: T2)
lineages_after_second = active_lineage_ids(rig)

check("A", "AC1: the ACTIVE lineage set is UNCHANGED by the equivalent "
      "extraction (no new Fact lineage)",
      lineages_after_first == lineages_after_second
      and len(lineages_after_second) == 1,
      f"{lineages_after_first} -> {lineages_after_second}")

check("A", "AC1: the Fact OBJECT count grew by exactly one version",
      len(fact_objects(rig)) == facts_after_first + 1,
      f"{facts_after_first} -> {len(fact_objects(rig))}")

canonical_lineage = next(iter(lineages_after_second))
head = head_of(rig, canonical_lineage)
pred = rig.store.get_fact(first.object_id)
check("A", "AC1: the head Fact now carries BOTH attachments",
      head.attachment_count == 2
      and {a.evidence_ref for a in head.attachments}
      == {ref_vendor, ref_forum},
      f"attachments={[a.evidence_ref for a in head.attachments]}")

check("A", "AC1: the extraction outcome points INTO the existing lineage",
      second.merged_into is not None
      and rig.store.find(second.object_id).lineage_id == canonical_lineage
      and rig.store.find(first.object_id).lineage_id == canonical_lineage,
      f"merged_into={second.merged_into}")

# ===========================================================================
# B. AC2 -- the merge produces a new Fact version
# ===========================================================================
check("B", "AC2: the head is version 2; the predecessor was version 1",
      head.attributes.identity.version == 2
      and pred.attributes.identity.version == 1,
      f"v{pred.attributes.identity.version} -> "
      f"v{head.attributes.identity.version}")

check("B", "AC2: the predecessor is SUPERSEDED, same lineage",
      rig.store.find(first.object_id).status is ObjectStatus.SUPERSEDED
      and rig.store.find(second.object_id).status is ObjectStatus.ACTIVE
      and rig.store.find(first.object_id).lineage_id == canonical_lineage,
      f"pred={rig.store.find(first.object_id).status}")

check("B", "AC2: the predecessor keeps its own attachment [F-I2]",
      pred.attachment_count == 1
      and pred.attachments[0].evidence_ref == ref_vendor,
      f"pred attachments={pred.attachment_count}")

check("B", "AC2: the version chain is contiguous and allocator-issued "
      "[V11]",
      head.attributes.identity.version == pred.attributes.identity.version + 1
      and head.attributes.identity.lineage_id
      == pred.attributes.identity.lineage_id,
      f"lineage={head.attributes.identity.lineage_id}")

check("B", "AC2: the head's derives_from covers the widened upstream set "
      "[F-I2]",
      {r.object_id for r in rig.store.find(second.object_id)
       .attributes.derives_from}
      == {a.evidence_ref for a in head.attachments},
      f"derives={len(head.attachments)}")

check("B", "AC2: the merge is justified -- EQUIVALENT, correct evidence, "
      "stamped at the clock [F-I4]",
      len(head.merge_history) == 1
      and head.merge_history[0].verdict is Verdict.EQUIVALENT
      and head.merge_history[0].merged_evidence_ref == ref_forum
      and head.merge_history[0].merged_at == T2
      and head.attributes.produced_at == T2,
      f"justification={head.merge_history[0].verdict}")

check("B", "AC2: F-I2 add-only -- attachments only ever accumulate",
      head.attachment_count == pred.attachment_count + 1,
      f"{pred.attachment_count} -> {head.attachment_count}")

# ===========================================================================
# C. AC3 -- uncertain equivalence produces DUPLICATES, never a merge
# ===========================================================================
variant = extract(rig.extraction(
        evidence_ref=ref_variant, qualifier="above 60 SKUs",
        anchor="bulk edits silently fail above 60 SKUs"),
    store=rig.store, log=rig.log, clock=lambda: T2 + timedelta(minutes=30))
variant_fact = rig.store.get_fact(variant.object_id)
check("C", "AC3: the uncertain extraction created its OWN lineage "
      "(no merge)",
      variant.merged_into is None
      and rig.store.find(variant.object_id).lineage_id
      not in lineages_after_second
      and len(active_lineage_ids(rig)) == 2,
      f"lineages={len(active_lineage_ids(rig))}")

check("C", "AC3: DUPLICATES recorded on the NEW Fact, pointing at the "
      "existing canonical",
      variant.duplicates == (second.object_id,)
      and variant_fact.attributes.duplicates == (second.object_id,),
      f"duplicates={variant_fact.attributes.duplicates}")

check("C", "AC3: the canonical was never re-versioned by the uncertain "
      "extraction",
      rig.store.find(second.object_id).status is ObjectStatus.ACTIVE
      and head_of(rig, canonical_lineage).attributes.identity.version == 2
      and head_of(rig, canonical_lineage).attachment_count == 2,
      "canonical untouched")

check("C", "AC3: the uncertain Fact carries exactly one attachment and "
      "no merge history",
      variant_fact.attachment_count == 1
      and variant_fact.merge_history == ()
      and head.merge_history != (),
      "uncertain side clean")

check("C", "AC3: the verdict behind the link is in the "
      "separate-with-duplicates class (CONTAINMENT/UNCERTAIN)",
      {r.verdict for _, r in variant.equivalence}
      <= {Verdict.CONTAINMENT, Verdict.UNCERTAIN}
      and MERGE_POLICY[next(iter(
          {r.verdict for _, r in variant.equivalence}))]
      is MergeAction.SEPARATE_WITH_DUPLICATES,
      f"{[r.verdict for _, r in variant.equivalence]}")

# NOT_EQUIVALENT: no merge, no duplicates link at all
synonym = extract(rig.extraction(
        evidence_ref=ref_synonym, subject="sellers",
        anchor="sellers silently fail above 50 SKUs"),
    store=rig.store, log=rig.log, clock=lambda: T2 + timedelta(minutes=45))
check("C", "AC3: NOT_EQUIVALENT stays separate with NO duplicates link",
      synonym.merged_into is None
      and synonym.duplicates == ()
      and len(active_lineage_ids(rig)) == 3,
      f"duplicates={synonym.duplicates}")

# ===========================================================================
# D. R-3/V5: the ceiling is RE-DERIVED over the widened upstream set
# ===========================================================================
weak = extract(rig.extraction(
        evidence_ref=ref_weak, extraction_confidence=0.6),
    store=rig.store, log=rig.log, clock=lambda: T2 + timedelta(hours=1))
merged = rig.store.get_fact(weak.object_id)
src_conf = {
    a.evidence_ref: rig.store.get_evidence(a.evidence_ref)
    .attributes.confidence.effective_confidence
    for a in merged.attachments
}
expected_support = min(src_conf.values())
check("D", "V5: merged support is min over the WIDENED upstream set "
      "(weak source governs), never inherited",
      merged.attributes.confidence.effective_confidence
      == expected_support
      and expected_support == 0.3
      and merged.attachments[0].evidence_ref != ref_weak,
      f"sources={sorted(src_conf.values())} -> "
      f"{merged.attributes.confidence.effective_confidence}")

check("D", "V5: evidential support IS the re-derived min; effective is "
      "ceiling-constrained to it",
      merged.attributes.confidence.evidential_support == expected_support
      and merged.attributes.confidence.effective_confidence
      <= expected_support + 1e-9,
      f"support={merged.attributes.confidence.evidential_support} "
      f"effective={merged.attributes.confidence.effective_confidence}")

check("D", "R-3: assertion confidence is min(predecessor, extraction)",
      merged.attributes.confidence.assertion_confidence
      == min(head.attributes.confidence.assertion_confidence, 0.6),
      f"assertion={merged.attributes.confidence.assertion_confidence}")

check("D", "V5: F-V5 invariant -- independent_source_count <= attachments",
      merged.independent_source_count <= merged.attachment_count
      and merged.independent_source_count == 1
      and all(a.independence_assessment is Independence.UNASSESSED
              for a in merged.attachments),
      f"count={merged.independent_source_count} "
      f"attachments={merged.attachment_count}")

# ===========================================================================
# E. F-I2 / N-10: replay refusal and failure projection
# ===========================================================================
facts_before_replay = len(fact_objects(rig))
replay_refused = False
try:
    extract(rig.extraction(evidence_ref=ref_vendor),
            store=rig.store, log=rig.log, clock=lambda: T2 + timedelta(hours=2))
except ExtractionRefusedError:
    replay_refused = True
replay_failure = rig.log.for_evidence(ref_vendor)[-1]
check("E", "F-I2: replaying attached Evidence is refused "
      "EVIDENCE_ALREADY_ATTACHED",
      replay_refused
      and replay_failure.stage is ExtractionStage.MERGE_FAILED
      and replay_failure.reason == "EVIDENCE_ALREADY_ATTACHED"
      and replay_failure.attempted,
      f"reason={replay_failure.reason}")

check("E", "N-10: the refused replay changed NOTHING and is projected "
      "into the FailureStore",
      len(fact_objects(rig)) == facts_before_replay
      and head_of(rig, canonical_lineage).attachment_count == 3
      and len(rig.failure_store) >= 1,
      f"facts={len(fact_objects(rig))} "
      f"failure_store={len(rig.failure_store)}")

# ===========================================================================
# F. T03.1.3 anchors + density
# ===========================================================================
check("F", "T03.1.3: anchors registered once per accepted extraction "
      "(merged path included)",
      all(
          rig.store.get_evidence(a.evidence_ref).content.content.count(
              a.positional_anchor) == 1
          for s in fact_objects(rig)
          for a in rig.store.get_fact(s.object_id).attachments
      ),
      "every attachment anchor locates uniquely")

_forum_content = rig.store.get_evidence(ref_forum).content.content
_located = _forum_content.find(SPAN)
check("F", "T03.1.3: the merged-path anchor resolves to its span",
      resolve_locator(
          _forum_content,
          f"chars {_located}-{_located + len(SPAN)}",
      ) == SPAN
      and merged.attachments[1].positional_anchor == SPAN,
      "locator round-trip")

report = build_density_report(rig.store, rig.log)
active_attachments = sum(
    rig.store.get_fact(s.object_id).attachment_count
    for s in fact_objects(rig)
    if rig.store.find(s.object_id).status is ObjectStatus.ACTIVE
)
check("F", "density counts ACTIVE attachments only (no version "
      "double-count)",
      sum(row.claims for row in report.rows) == active_attachments,
      f"report={sum(row.claims for row in report.rows)} "
      f"active={active_attachments}")

# ===========================================================================
# G. pinned policy + store integrity
# ===========================================================================
check("G", "the MERGE_POLICY table is exactly the S-3 decision",
      MERGE_POLICY == {
          Verdict.EQUIVALENT: MergeAction.MERGE,
          Verdict.CONTAINMENT: MergeAction.SEPARATE_WITH_DUPLICATES,
          Verdict.UNCERTAIN: MergeAction.SEPARATE_WITH_DUPLICATES,
          Verdict.NOT_EQUIVALENT: MergeAction.SEPARATE,
      },
      "MERGE_POLICY pinned")

violations = rig.store.facts.integrity().verify()
check("G", "store integrity clean over the merged corpus",
      not violations, str(violations[:3]))

trace_ok = all(
    {r.object_id
     for r in rig.store.find(s.object_id).attributes.derives_from}
    == {a.evidence_ref
        for a in rig.store.get_fact(s.object_id).attachments}
    for s in fact_objects(rig)
)
check("G", "every Fact version traces: derives_from == attachment set",
      trace_ok, "F-I2 lineage audit")

# ---------------------------------------------------------------------------
passed = sum(1 for _, _, ok, _ in CHECKS if ok)
for section, name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} [{section}] {name}"
          + (f"  [{detail}]" if not ok else ""))
print(f"\nRESULT: {passed}/{len(CHECKS)} checks passed")
sys.exit(0 if passed == len(CHECKS) else 1)
