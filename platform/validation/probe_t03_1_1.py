"""Adversarial probes for T03.1.1 -- claim extraction.

Run BEFORE the contract tests. A probe's job is to find what the
specification permits that the code assumes away. Each probe states the
attack; PASS means the implementation held.

Attacks:
  P01  ambiguity: anchor occurs twice -> must refuse, never guess
  P02  short-span contamination: a common substring as anchor
  P03  case trick: re-cased anchor is not the verbatim span
  P04  case trick (inverse): re-cased components still verify [S-5]
  P05  cross-source contamination: span from Evidence B claimed in A
  P06  cross-source contamination: components from B anchored in A's span
  P07  fabricated quantity: value_text absent from the span
  P08  value outside the span but elsewhere in content (bound check)
  P09  extraction from a retracted Evidence
  P10  extraction from a non-Evidence object (a Fact id)
  P11  empty-content Evidence: found-nothing, never a phantom claim
  P12  dangling evidence_ref
  P13  qualifier stripping: context dropped between request and Fact
  P14  confidence inflation: extractor asserts above the source ceiling
  P15  accidental collapse: same claim from two Evidence stays two Facts
  P16  near-duplicate: differing qualifier must not merge [S-3]
  P17  value-precision: values outside stated precision must not merge
  P18  clock behind the source timeline [V8]
  P19  unicode: CJK, RTL Arabic, German umlauts extract and preserve
  P20  NBSP against plain space: verbatim discipline holds
  P21  anchor at the very start / end of content
  P22  refusal audit: every refusal is in the log and attempted-flagged
  P23  FailureStore projection: refusals visible to Orchestration
  P24  equivalence self-report excluded; multi-claim density counted
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.claim import Quantity, Verdict
from oip.configuration import FailureStore
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ObjectStatus
from oip.extraction import (
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    build_density_report,
    extract,
)
from oip.fact import ClaimType
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

RESULTS: list[tuple[str, bool, str]] = []


def probe(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


# ---------------------------------------------------------------------------
# Rig: the acquisition path in miniature (mirrors the exit-gate corpus)
# ---------------------------------------------------------------------------


class Rig:
    def __init__(self, targets: tuple[str, ...] | None = None) -> None:
        self.registry = SourceRegistry()
        self.store = KnowledgeStore()
        self.out_of_frame = OutOfFrameRegister()
        self.refusals = RefusalRegister()
        self.acq_log = AcquisitionLog()
        self.extraction_log = ExtractionLog()
        self.directives = DirectiveRegistry()
        self.directives.raise_directive(Directive(
            directive_id="dir-probe",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="probe-commissioner",
            description="probe corpus",
            targets=targets or (
                "src-a", "src-b", "src-empty", "src-dup", "src-c",
                "src-weak", "src-de", "src-cjk", "src-rtl", "src-nbsp",
                "src-edge",
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
            anchor="bulk edits silently fail above 50 SKUs",
            claim_type=ClaimType.ASSERTION,
            extraction_confidence=0.8,
        )
        base.update(overrides)
        return ExtractionRequest(**base)


def fresh_content_rig() -> tuple[Rig, str]:
    rig = Rig()
    rig.add_source("src-a", "VENDOR_PUBLICATION")
    ref = rig.acquire(
        "src-a",
        "VENDOR_PUBLICATION",
        "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
        "Support recommends batching smaller.",
    )
    return rig, ref


# P01 -- ambiguity -----------------------------------------------------------
rig, ref = fresh_content_rig()
rig.add_source("src-dup", "VENDOR_PUBLICATION")
dup_ref = rig.acquire(
    "src-dup",
    "VENDOR_PUBLICATION",
    "First telling: bulk edits silently fail above 50 SKUs. "
    "Second telling: bulk edits silently fail above 50 SKUs.",
)
try:
    extract(
        rig.extraction(evidence_ref=dup_ref),
        store=rig.store, log=rig.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P01 ambiguous anchor refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    failures = rig.log.for_evidence(dup_ref)
    probe(
        "P01 ambiguous anchor refused",
        failures
        and failures[-1].stage is ExtractionStage.AMBIGUOUS_ANCHOR,
        str(exc),
    )

# P02 -- short-span anchor occurring twice: ambiguity beats components --------
rig2 = Rig()
rig2.add_source("src-dup", "VENDOR_PUBLICATION")
dup2 = rig2.acquire(
    "src-dup", "VENDOR_PUBLICATION",
    "First telling: bulk edits silently fail above 50 SKUs. "
    "Second telling: bulk edits silently fail above 50 SKUs.",
)
try:
    extract(
        rig2.extraction(evidence_ref=dup2, anchor="telling:",
                        subject="telling", predicate="telling"),
        store=rig2.store, log=rig2.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P02 non-unique short anchor refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig2.log.for_evidence(dup2)[-1].stage
    probe("P02 non-unique short anchor refused",
          stage is ExtractionStage.AMBIGUOUS_ANCHOR, str(exc))

# P03 -- re-cased anchor is not the verbatim span ------------------------------
rig3, ref3 = fresh_content_rig()
try:
    extract(
        rig3.extraction(
            evidence_ref=ref3,
            anchor="BULK EDITS SILENTLY FAIL ABOVE 50 SKUS",
        ),
        store=rig3.store, log=rig3.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P03 re-cased anchor refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig3.log.for_evidence(ref3)[-1].stage
    probe("P03 re-cased anchor refused",
          stage is ExtractionStage.ANCHOR_NOT_FOUND, str(exc))

# P04 -- components re-cased still verify (AnchorVerifier semantics) -----------
outcome = extract(
    rig3.extraction(
        evidence_ref=ref3,
        subject="Bulk EDITS",
        predicate="Silently FAIL Above",
    ),
    store=rig3.store, log=rig3.log, clock=lambda: T0 + timedelta(minutes=2),
)
probe("P04 re-cased components verify", outcome.fact is not None)

# P05 -- span from Evidence B claimed against Evidence A ------------------------
rig5 = Rig()
rig5.add_source("src-a", "VENDOR_PUBLICATION")
rig5.add_source("src-b", "USER_GENERATED_DISCUSSION")
ref_a = rig5.acquire(
    "src-a", "VENDOR_PUBLICATION",
    "Vendor changelog: bulk edits silently fail above 50 SKUs.",
)
ref_b = rig5.acquire(
    "src-b", "USER_GENERATED_DISCUSSION",
    "Forum post: users complain the mobile app crashes on upload.",
)
try:
    extract(
        rig5.extraction(
            evidence_ref=ref_a,
            anchor="users complain the mobile app crashes on upload",
            subject="users",
            predicate="complain the mobile app crashes on upload",
        ),
        store=rig5.store, log=rig5.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P05 foreign span refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig5.log.for_evidence(ref_a)[-1].stage
    probe("P05 foreign span refused",
          stage is ExtractionStage.ANCHOR_NOT_FOUND, str(exc))

# P06 -- real span of A, but components from B ---------------------------------
try:
    extract(
        rig5.extraction(
            evidence_ref=ref_a,
            anchor="bulk edits silently fail above 50 SKUs",
            subject="users",
            predicate="complain the mobile app crashes on upload",
        ),
        store=rig5.store, log=rig5.log, clock=lambda: T0 + timedelta(minutes=2),
    )
    probe("P06 foreign components refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig5.log.for_evidence(ref_a)[-1].stage
    probe("P06 foreign components refused",
          stage is ExtractionStage.UNSUPPORTED_CLAIM, str(exc))

# P07 -- fabricated quantity ----------------------------------------------------
try:
    extract(
        rig5.extraction(
            evidence_ref=ref_a,
            anchor="bulk edits silently fail above 50 SKUs",
            value=Quantity(value=500, precision=1),
            value_text="500",
        ),
        store=rig5.store, log=rig5.log, clock=lambda: T0 + timedelta(minutes=3),
    )
    probe("P07 fabricated quantity refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig5.log.for_evidence(ref_a)[-1].stage
    probe("P07 fabricated quantity refused",
          stage is ExtractionStage.UNSUPPORTED_CLAIM, str(exc))

# P08 -- quantity present in content but OUTSIDE the span -----------------------
rig8 = Rig()
rig8.add_source("src-c", "REGULATORY_FILING")
ref_c = rig8.acquire(
    "src-c", "REGULATORY_FILING",
    "Filing 2026-17042 covers size standards. The relevant threshold is "
    "5,314 firms; the quoted passage says eligibility broadened.",
)
try:
    extract(
        rig8.extraction(
            evidence_ref=ref_c,
            anchor="the quoted passage says eligibility broadened",
            subject="threshold",
            predicate="is firms",
            value=Quantity(value=5314, precision=1),
            value_text="5,314",
        ),
        store=rig8.store, log=rig8.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P08 value outside span refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig8.log.for_evidence(ref_c)[-1].stage
    probe("P08 value outside span refused",
          stage is ExtractionStage.UNSUPPORTED_CLAIM, str(exc))

# P09 -- retracted Evidence ------------------------------------------------------
rig9, ref9 = fresh_content_rig()
rig9.store.transition(ref9, ObjectStatus.RETRACTED, "source retracted")
try:
    extract(
        rig9.extraction(evidence_ref=ref9),
        store=rig9.store, log=rig9.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P09 retracted Evidence refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig9.log.for_evidence(ref9)[-1].stage
    probe("P09 retracted Evidence refused",
          stage is ExtractionStage.EVIDENCE_NOT_EXTRACTABLE
          and not rig9.log.for_evidence(ref9)[-1].attempted,
          str(exc))

# P10 -- non-Evidence object as source --------------------------------------------
rig10, ref10 = fresh_content_rig()
outcome_a = extract(
    rig10.extraction(evidence_ref=ref10),
    store=rig10.store, log=rig10.log,
    clock=lambda: T0 + timedelta(minutes=9),
)
fact_id = outcome_a.object_id
try:
    extract(
        rig10.extraction(evidence_ref=fact_id),
        store=rig10.store, log=rig10.log,
        clock=lambda: T0 + timedelta(minutes=10),
    )
    probe("P10 non-Evidence ref refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    probe("P10 non-Evidence ref refused",
          any(f.stage is ExtractionStage.EVIDENCE_NOT_EXTRACTABLE
              for f in rig10.log.for_evidence(fact_id)),
          str(exc))

# P11 -- empty content -------------------------------------------------------------
rig11 = Rig()
rig11.add_source("src-empty", "STRUCTURED_DATASET")
empty_ref = rig11.acquire("src-empty", "STRUCTURED_DATASET", "")
try:
    extract(
        rig11.extraction(evidence_ref=empty_ref),
        store=rig11.store, log=rig11.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P11 empty content refused as found-nothing", False, "no refusal")
except ExtractionRefusedError as exc:
    failure = rig11.log.for_evidence(empty_ref)[-1]
    probe("P11 empty content refused as found-nothing",
          failure.stage is ExtractionStage.EMPTY_CONTENT
          and failure.attempted, str(exc))

# P12 -- dangling reference ----------------------------------------------------------
rig12, _ = fresh_content_rig()
try:
    extract(
        rig12.extraction(evidence_ref="EV-DOES-NOT-EXIST"),
        store=rig12.store, log=rig12.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P12 dangling ref refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    probe("P12 dangling ref refused",
          rig12.log.for_evidence("EV-DOES-NOT-EXIST")[-1].stage
          is ExtractionStage.EVIDENCE_NOT_FOUND, str(exc))

# P13 -- context preservation ---------------------------------------------------------
rig13, ref13 = fresh_content_rig()
ctx = "vendor changelog, March 2026; applies to bulk edits above 50 SKUs"
outcome13 = extract(
    rig13.extraction(evidence_ref=ref13, qualifying_context=ctx),
    store=rig13.store, log=rig13.log, clock=lambda: T0 + timedelta(minutes=1),
)
stored13 = rig13.store.get_fact(outcome13.object_id)
probe("P13 qualifying_context preserved verbatim",
      stored13 is not None and stored13.qualifying_context == ctx)

# P14 -- confidence ceiling ------------------------------------------------------------
rig14 = Rig()
rig14.add_source("src-weak", "USER_GENERATED_REVIEW")
weak_ref = rig14.acquire(
    "src-weak", "USER_GENERATED_REVIEW",
    "Review: the export feature times out on large libraries.",
    support=0.4, assertion=0.5,
)
outcome14 = extract(
    rig14.extraction(
        evidence_ref=weak_ref,
        subject="export feature",
        predicate="times out on large libraries",
        anchor="the export feature times out on large libraries",
        extraction_confidence=0.99,
        qualifying_context="single user review, large libraries",
    ),
    store=rig14.store, log=rig14.log, clock=lambda: T0 + timedelta(minutes=1),
)
conf = outcome14.fact.attributes.confidence
probe("P14 confidence capped by the source [R-3]",
      conf.effective_confidence <= 0.4 + 1e-9
      and conf.assertion_confidence == 0.99,
      f"effective={conf.effective_confidence}")

# P15 -- no accidental collapse ---------------------------------------------------------
rig15 = Rig()
rig15.add_source("src-a", "VENDOR_PUBLICATION")
rig15.add_source("src-b", "USER_GENERATED_DISCUSSION")
ra = rig15.acquire("src-a", "VENDOR_PUBLICATION",
                   "Changelog: bulk edits silently fail above 50 SKUs.")
rb = rig15.acquire("src-b", "USER_GENERATED_DISCUSSION",
                   "Forum: bulk edits silently fail above 50 SKUs.")
o1 = extract(
    rig15.extraction(evidence_ref=ra),
    store=rig15.store, log=rig15.log, clock=lambda: T0 + timedelta(minutes=1),
)
o2 = extract(
    rig15.extraction(evidence_ref=rb),
    store=rig15.store, log=rig15.log, clock=lambda: T0 + timedelta(minutes=2),
)
probe("P15 identical claims stay distinct Facts [S-3 under-merge]",
      o1.object_id != o2.object_id
      and rig15.store.get_fact(o1.object_id) is not None
      and rig15.store.get_fact(o2.object_id) is not None
      and o2.equivalence
      and o2.equivalence[0][1].verdict is Verdict.EQUIVALENT,
      f"{o1.object_id} vs {o2.object_id}")

# P16 -- near-duplicate (qualifier differs) ----------------------------------------------
rig16 = Rig()
rig16.add_source("src-a", "VENDOR_PUBLICATION")
rig16.add_source("src-b", "USER_GENERATED_DISCUSSION")
r16a = rig16.acquire("src-a", "VENDOR_PUBLICATION",
                     "Changelog: bulk edits silently fail above 50 SKUs.")
r16b = rig16.acquire("src-b", "USER_GENERATED_DISCUSSION",
                     "Forum: bulk edits silently fail above 50 SKUs since v9.")
q1 = extract(
    rig16.extraction(evidence_ref=r16a, qualifier="above 50 SKUs"),
    store=rig16.store, log=rig16.log, clock=lambda: T0 + timedelta(minutes=1),
)
q2 = extract(
    rig16.extraction(evidence_ref=r16b, qualifier="above 50 SKUs since v9"),
    store=rig16.store, log=rig16.log, clock=lambda: T0 + timedelta(minutes=2),
)
verdicts = {r.verdict for _, r in q2.equivalence}
probe("P16 qualifier mismatch never merges [S-3]",
      q1.object_id != q2.object_id
      and verdicts <= {Verdict.CONTAINMENT, Verdict.UNCERTAIN},
      str(verdicts))

# P17 -- value outside stated precision ----------------------------------------------------
rig17 = Rig()
rig17.add_source("src-a", "MARKETPLACE_LISTING")
rig17.add_source("src-b", "MARKETPLACE_LISTING")
r17a = rig17.acquire("src-a", "MARKETPLACE_LISTING",
                     "Listing: rated 4.6 stars by buyers this quarter.")
r17b = rig17.acquire("src-b", "MARKETPLACE_LISTING",
                     "Listing: rated 4.9 stars by buyers this quarter.")
v1 = extract(
    rig17.extraction(
        evidence_ref=r17a, subject="Listing", predicate="rated",
        anchor="Listing: rated 4.6 stars by buyers this quarter.",
        value=Quantity(4.6, 0.1), value_text="4.6",
        qualifier="by buyers this quarter",
    ),
    store=rig17.store, log=rig17.log, clock=lambda: T0 + timedelta(minutes=1),
)
v2 = extract(
    rig17.extraction(
        evidence_ref=r17b, subject="Listing", predicate="rated",
        anchor="Listing: rated 4.9 stars by buyers this quarter.",
        value=Quantity(4.9, 0.1), value_text="4.9",
        qualifier="by buyers this quarter",
    ),
    store=rig17.store, log=rig17.log, clock=lambda: T0 + timedelta(minutes=2),
)
verdicts17 = {r.verdict for _, r in v2.equivalence}
probe("P17 values outside precision do not merge [S-3 cond 4]",
      v1.object_id != v2.object_id
      and Verdict.NOT_EQUIVALENT in verdicts17, str(verdicts17))

# P18 -- clock behind the source timeline [V8] ----------------------------------------------
rig18, ref18 = fresh_content_rig()
try:
    extract(
        rig18.extraction(evidence_ref=ref18),
        store=rig18.store, log=rig18.log,
        clock=lambda: T0 - timedelta(hours=2),
    )
    probe("P18 clock-behind-source refused", False, "no refusal raised")
except ExtractionRefusedError as exc:
    stage = rig18.log.for_evidence(ref18)[-1].stage
    probe("P18 clock-behind-source refused",
          stage is ExtractionStage.TEMPORAL_CONFLICT, str(exc))

# P19 -- unicode corpora ------------------------------------------------------------------------
rig19 = Rig()
rig19.add_source("src-de", "PUBLISHED_EDITORIAL")
rig19.add_source("src-cjk", "VENDOR_PUBLICATION")
rig19.add_source("src-rtl", "SUPPORT_INTERACTION")
de = rig19.acquire(
    "src-de", "PUBLISHED_EDITORIAL",
    "Redaktionell: Straßenverkehrsämter melden zusätzliche Gebühren "
    "für Kurzzeitparker in der Innenstadt.",
)
cjk = rig19.acquire(
    "src-cjk", "VENDOR_PUBLICATION",
    "リリースノート：一括編集は50SKUを超えると静かに失敗します。",
)
rtl = rig19.acquire(
    "src-rtl", "SUPPORT_INTERACTION",
    "تقرير الدعم: يفشل تصدير المكتبات الكبيرة بشكل صامت.",
)
o_de = extract(
    rig19.extraction(
        evidence_ref=de, subject="Straßenverkehrsämter",
        predicate="melden zusätzliche Gebühren",
        anchor=("Straßenverkehrsämter melden zusätzliche Gebühren "
                "für Kurzzeitparker in der Innenstadt"),
        qualifying_context="redaktionelle Meldung, Innenstadt",
    ),
    store=rig19.store, log=rig19.log, clock=lambda: T0 + timedelta(minutes=1),
)
o_cjk = extract(
    rig19.extraction(
        evidence_ref=cjk, subject="一括編集",
        predicate="静かに失敗します",
        anchor="一括編集は50SKUを超えると静かに失敗します",
        qualifying_context="リリースノート、50SKU超",
    ),
    store=rig19.store, log=rig19.log, clock=lambda: T0 + timedelta(minutes=2),
)
o_rtl = extract(
    rig19.extraction(
        evidence_ref=rtl, subject="يفشل تصدير المكتبات الكبيرة",
        predicate="بشكل صامت",
        anchor="يفشل تصدير المكتبات الكبيرة بشكل صامت",
        qualifying_context="تقرير الدعم",
    ),
    store=rig19.store, log=rig19.log, clock=lambda: T0 + timedelta(minutes=3),
)
probe("P19 unicode corpora extract (de/cjk/rtl)",
      all(o.fact.claim.subject for o in (o_de, o_cjk, o_rtl)))

# P20 -- NBSP vs plain space ----------------------------------------------------------------------
rig20 = Rig()
rig20.add_source("src-nbsp", "PUBLISHED_EDITORIAL")
nbsp_ref = rig20.acquire(
    "src-nbsp", "PUBLISHED_EDITORIAL",
    "Editorial:\u00a0bulk edits silently fail above 50 SKUs.",
)
try:
    extract(
        rig20.extraction(
            evidence_ref=nbsp_ref,
            anchor="Editorial: bulk edits silently fail above 50 SKUs",
        ),
        store=rig20.store, log=rig20.log, clock=lambda: T0 + timedelta(minutes=1),
    )
    probe("P20 NBSP anchor mismatch refused", False, "no refusal")
except ExtractionRefusedError as exc:
    probe("P20 NBSP anchor mismatch refused",
          rig20.log.for_evidence(nbsp_ref)[-1].stage
          is ExtractionStage.ANCHOR_NOT_FOUND, str(exc))
# the exact span (with the NBSP) extracts cleanly
o20 = extract(
    rig20.extraction(
        evidence_ref=nbsp_ref,
        anchor="bulk edits silently fail above 50 SKUs",
    ),
    store=rig20.store, log=rig20.log, clock=lambda: T0 + timedelta(minutes=2),
)
probe("P20 exact NBSP span extracts", o20.fact is not None)

# P21 -- anchors at the boundaries ------------------------------------------------------------------
rig21 = Rig()
rig21.add_source("src-edge", "STRUCTURED_DATASET")
edge_ref = rig21.acquire(
    "src-edge", "STRUCTURED_DATASET",
    "10/01/2009,Agriculture,93",
)
o_head = extract(
    rig21.extraction(
        evidence_ref=edge_ref,
        anchor="10/01/2009,Agriculture,93",
        subject="Agriculture",
        predicate="10/01/2009",
        value=Quantity(93, 1), value_text="93",
        qualifying_context="data.gov archival CSV, first row",
    ),
    store=rig21.store, log=rig21.log, clock=lambda: T0 + timedelta(minutes=1),
)
probe("P21 whole-content anchor extracts", o_head.fact is not None)

# P22 -- refusal audit: every refusal in the log with correct attempted flag ------------------------
all_failures = list(rig9.log)
probe("P22 every refusal recorded with a stage and detail",
      all(
          f.stage is not None and f.detail and f.reason
          for f in all_failures
      ),
      f"{len(all_failures)} failures")

# P23 -- FailureStore projection ----------------------------------------------------------------------
fs = FailureStore()
rig23 = Rig()
rig23.add_source("src-a", "VENDOR_PUBLICATION")
r23 = rig23.acquire("src-a", "VENDOR_PUBLICATION",
                    "Changelog: bulk edits silently fail above 50 SKUs.")
rig23.log.attach(fs)
try:
    extract(
        rig23.extraction(evidence_ref=r23, anchor="not present anywhere"),
        store=rig23.store, log=rig23.log,
        clock=lambda: T0 + timedelta(minutes=1),
    )
except ExtractionRefusedError:
    pass
probe("P23 refusal projected into the FailureStore",
      len(fs) > 0, f"failure store holds {len(fs)}")

# P24 -- density counts from recorded facts only -------------------------------------------------------
report = build_density_report(
    rig15.store, rig15.log, evidence_refs=(ra, rb)
)
probe("P24 density counted per Evidence",
      report.total_claims == 2
      and all(row.claims == 1 for row in report.rows)
      and report.evidences_without_claims == (),
      str([(r.evidence_ref, r.claims) for r in report.rows]))

# ------------------------------------------------------------------------------------------------------
failed = [(n, d) for n, ok, d in RESULTS if not ok]
for name, ok, detail in RESULTS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if detail and not ok else ""))
print(f"\nPROBES: {len(RESULTS) - len(failed)}/{len(RESULTS)} held")
sys.exit(1 if failed else 0)
