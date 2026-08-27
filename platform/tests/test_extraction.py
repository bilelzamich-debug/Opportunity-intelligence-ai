"""Contract tests for claim extraction.

Task: T03.1.1

Architecture References:
- F-V3   Claims interpretable without reading the Evidence (AC1)
- AC2    qualifying_context preserved verbatim; uncertainty preserved
- AC3    Density measured from recorded facts; never a gate
- S-3    Claim structure; equivalence surfaces, never acts (T03.1.4 merges)
- S-5    Layer 1 at extraction: unique verbatim span; components present
- R-3    Confidence derived, never invented; ceiling respected (V5)
- N-4    Property-based assertions only for outputs
- N-10   Refusals recorded, never silent; failed != found-nothing
- N-15   REFERENCE-mode Evidence refuses (not verifiable in place)
- N-16   Independence never inferred; attachment starts UNASSESSED
- N-20   Density report stratifies by the closed eight-member taxonomy

T03.1.1 acceptance criteria under test:
  AC1  Claims interpretable without reading the Evidence (F-V3) -> IMPLEMENTED
  AC2  qualifying_context preserved                             -> IMPLEMENTED
  AC3  Extraction density consistent across comparable evidence -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.claim import Quantity, Verdict
from oip.configuration import FailureStore
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ConfidenceBand, ObjectStatus
from oip.evidence import compute_fingerprint
from oip.extraction import (
    EvidenceDensity,
    ExtractionError,
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    build_density_report,
    extract,
)
from oip.fact import ClaimType, Independence
from oip.rights import (
    AcquisitionRight,
    RefusalRegister,
    RetentionRight,
    RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
TICK = T0 + timedelta(minutes=1)

NONEMPTY = st.text(min_size=1, max_size=80).filter(str.strip)
CONF = st.floats(min_value=0.0, max_value=1.0)

AUTHORITY = "Designated Source Rights/Compliance Authority"


class Rig:
    """One extraction wiring: acquisition path plus the extraction log."""

    def __init__(self, targets: dict[str, str] | None = None) -> None:
        targets = targets or {}
        self.registry = SourceRegistry()
        self.store = KnowledgeStore()
        self.out_of_frame = OutOfFrameRegister()
        self.refusals = RefusalRegister()
        self.acq_log = AcquisitionLog()
        self.log = ExtractionLog()
        self.targets = list(targets)
        self.directives = DirectiveRegistry()
        self.directives.raise_directive(Directive(
            directive_id="dir-test",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="test-commissioner",
            description="test corpus",
            targets=tuple(targets),
            raised_at=T0 - timedelta(days=1),
        ))
        self.directives.effect("dir-test", now=T0)
        for identifier, source_type in targets.items():
            self.registry.register(identifier, source_type)

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
            acquisition_method="test retrieval",
            capture_fidelity="test corpus; full text",
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
            authority=AUTHORITY,
            basis="test basis",
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


def make_rig(targets: dict[str, str]) -> Rig:
    return Rig(targets)


VENDOR = "VENDOR_PUBLICATION"


def vendor_rig(*identifiers: str, **kw) -> Rig:
    return make_rig({name: kw.get(name, VENDOR) for name in identifiers})


def changelog_rig() -> tuple[Rig, str]:
    rig = vendor_rig("src-a")
    ref = rig.acquire(
        "src-a", VENDOR,
        "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
        "Support recommends batching smaller.",
    )
    return rig, ref


# ---------------------------------------------------------------------------
# AC1 -- self-contained claims, F-V3
# ---------------------------------------------------------------------------


class TestAC1SelfContained:
    def test_extract_produces_active_fact_with_full_claim(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact is not None
        assert fact.status is ObjectStatus.ACTIVE
        # F-V3 structurally: subject, predicate, qualifier all stated.
        assert fact.claim.subject == "bulk edits"
        assert fact.claim.predicate == "silently fail above"
        assert fact.claim.qualifier  # explicit, never blank
        assert fact.qualifying_context  # AC2's structural half

    def test_claim_interpretable_without_reading_evidence(self):
        """AC1 demonstrated: the Fact alone states what is claimed."""
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        rendered = fact.claim.as_text()
        # subject and predicate travel in the rendered claim; the value,
        # where present, too; the qualifier is explicit when present.
        assert fact.claim.subject.casefold() in rendered.casefold()
        assert fact.claim.predicate.casefold() in rendered.casefold()
        if not fact.claim.is_unqualified:
            assert fact.claim.qualifier in rendered

    def test_unqualified_claim_records_NONE_explicitly(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref, qualifier="NONE"),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim.is_unqualified

    @given(st.text(min_size=1, max_size=40), st.text(min_size=1, max_size=40))
    def test_components_never_defaulted(self, subject, predicate):
        subject = subject.strip() or "x"
        predicate = predicate.strip() or "y"
        request = ExtractionRequest(
            evidence_ref="ev-1",
            subject=subject,
            predicate=predicate,
            qualifying_context="ctx",
            anchor="anchor span",
            claim_type=ClaimType.ASSERTION,
            extraction_confidence=0.5,
        )
        claim = request.as_claim()
        assert claim.subject == subject
        assert claim.predicate == predicate

    def test_only_fact_extraction_engine_creates_facts(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.attributes.produced_by_engine.value == "FactExtraction"


# ---------------------------------------------------------------------------
# AC2 -- qualifying_context preserved; uncertainty preserved
# ---------------------------------------------------------------------------


class TestAC2QualifyingContext:
    def test_context_carried_verbatim(self):
        rig, ref = changelog_rig()
        ctx = "vendor changelog, March 2026; applies ONLY to bulk edits"
        outcome = extract(
            rig.extraction(evidence_ref=ref, qualifying_context=ctx),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.qualifying_context == ctx

    @given(NONEMPTY, CONF)
    def test_context_and_confidence_preserved_for_any_input(
        self, context, confidence
    ):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                qualifying_context=context,
                extraction_confidence=confidence,
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachment_for(ref)
        assert fact.qualifying_context == context
        assert attachment is not None
        assert attachment.extraction_confidence == pytest.approx(confidence)

    def test_empty_context_is_unconstructable(self):
        with pytest.raises(ExtractionError):
            rig = vendor_rig("src-a")
            rig.extraction(qualifying_context="   ")

    def test_ambiguous_anchor_refused_not_guessed(self):
        rig = vendor_rig("src-dup")
        ref = rig.acquire(
            "src-dup", VENDOR,
            "A: bulk edits silently fail above 50 SKUs. "
            "B: bulk edits silently fail above 50 SKUs.",
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.AMBIGUOUS_ANCHOR
        assert rig.store.objects_of_type(_fact_type()) == ()

    def test_low_confidence_preserved_never_clamped(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref, extraction_confidence=0.05),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachment_for(ref)
        assert attachment.extraction_confidence == pytest.approx(0.05)
        assert fact.attributes.confidence.band is ConfidenceBand.NEGLIGIBLE


def _fact_type():
    from oip.enums import ObjectType

    return ObjectType.FACT


# ---------------------------------------------------------------------------
# S-5 layer 1 -- fidelity gates (AC1's grounding half)
# ---------------------------------------------------------------------------


class TestS5Layer1:
    def test_anchor_preserved_on_attachment(self):
        rig, ref = changelog_rig()
        anchor = "bulk edits silently fail above 50 SKUs"
        outcome = extract(
            rig.extraction(evidence_ref=ref, anchor=anchor),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachment_for(ref)
        assert attachment.positional_anchor == anchor

    def test_fabricated_anchor_refused(self):
        rig, ref = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref, anchor="never said anywhere"),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.ANCHOR_NOT_FOUND

    def test_recased_anchor_is_not_the_verbatim_span(self):
        rig, ref = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ref,
                    anchor="BULK EDITS SILENTLY FAIL ABOVE 50 SKUS",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.ANCHOR_NOT_FOUND

    def test_components_absent_from_span_refused(self):
        rig, ref = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ref,
                    subject="competitors",
                    predicate="gain market share",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.UNSUPPORTED_CLAIM

    def test_fabricated_value_refused(self):
        rig, ref = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ref,
                    value=Quantity(500, 1),
                    value_text="500",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert rig.log.for_evidence(ref)[-1].stage is (
            ExtractionStage.UNSUPPORTED_CLAIM
        )

    def test_value_present_in_content_but_outside_span_refused(self):
        rig = vendor_rig("src-c")
        ref = rig.acquire(
            "src-c", VENDOR,
            "Threshold is 5,314 firms. The quoted passage says "
            "eligibility broadened.",
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ref,
                    anchor="The quoted passage says eligibility broadened",
                    subject="threshold",
                    predicate="is firms",
                    value=Quantity(5314, 1),
                    value_text="5,314",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert rig.log.for_evidence(ref)[-1].stage is (
            ExtractionStage.UNSUPPORTED_CLAIM
        )

    def test_reference_mode_evidence_refused(self):
        rig = vendor_rig("src-ref")
        # acquire by reference: fingerprint of the hypothetical content
        fp = compute_fingerprint("external content not held")
        from oip.acquisition import AcquisitionRequest as AR

        request = AR(
            source_identifier="src-ref",
            source_type=VENDOR,
            acquisition_method="reference-only catalogue",
            capture_fidelity="metadata only; content not retained",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.6,
            assertion_confidence=0.8,
            content_reference="https://example.external/item/1",
            content_fingerprint=fp,
        )
        from oip.rights import RetentionRight

        rights = RightsAssessment(
            source_identifier="src-ref",
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_REFERENCE_ONLY,
            authority=AUTHORITY,
            basis="test basis",
            assessed_at=T0 - timedelta(hours=2),
        )
        evidence = acquire(
            request,
            registry=rig.registry,
            store=rig.store,
            directives=rig.directives,
            out_of_frame=rig.out_of_frame,
            refusals=rig.refusals,
            log=rig.acq_log,
            assessment=rights,
            clock=lambda: T0,
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=evidence.object_id),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(evidence.object_id)[-1]
        assert failure.stage is ExtractionStage.EVIDENCE_NOT_EXTRACTABLE
        assert not failure.attempted

    def test_extraction_gate_agrees_with_anchor_verifier(self):
        """The local Layer-1 predicate tracks the ratified AnchorVerifier."""
        from oip.semantic import AnchorClaim, AnchorVerifier

        verifier = AnchorVerifier()
        cases = [
            ("bulk edits", "silently fail above", None,
             "bulk edits silently fail above 50 SKUs"),
            ("bulk edits", "gain share", None,
             "bulk edits silently fail above 50 SKUs"),
            ("edits", "fail", "50", "bulk edits silently fail above 50 SKUs"),
            ("edits", "fail", "500", "bulk edits silently fail above 50 SKUs"),
        ]
        for subject, predicate, value, span in cases:
            anchored = AnchorClaim(
                claim="n/a",
                anchor=type("A", (), {"locator": span})(),
                subject=subject,
                predicate=predicate,
                value=value or "",
            )
            ratified_missing = verifier._missing_components(anchored, span)
            local_missing = __import__(
                "oip.extraction", fromlist=["_missing_components"]
            )._missing_components(subject, predicate, value, span)
            assert list(ratified_missing) == list(local_missing)


# ---------------------------------------------------------------------------
# Confidence [R-3]
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_support_taken_from_source_evidence(self):
        rig = vendor_rig("src-weak")
        ref = rig.acquire(
            "src-weak", VENDOR,
            "Changelog: bulk edits silently fail above 50 SKUs.",
            support=0.4, assertion=0.5,
        )
        outcome = extract(
            rig.extraction(evidence_ref=ref, extraction_confidence=0.99),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        conf = outcome.fact.attributes.confidence
        assert conf.evidential_support == pytest.approx(0.4)
        assert conf.assertion_confidence == pytest.approx(0.99)
        assert conf.effective_confidence <= 0.4 + 1e-9

    @given(st.floats(min_value=0.01, max_value=1.0),
           st.floats(min_value=0.0, max_value=1.0))
    def test_effective_never_exceeds_ceiling(self, support, assertion):
        rig = vendor_rig("src-p")
        ref = rig.acquire(
            "src-p", VENDOR,
            "Changelog: bulk edits silently fail above 50 SKUs.",
            support=support, assertion=min(assertion, 1.0),
        )
        outcome = extract(
            rig.extraction(evidence_ref=ref, extraction_confidence=0.9),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        conf = outcome.fact.attributes.confidence
        assert conf.effective_confidence <= min(support, 0.9) + 1e-9

    def test_confidence_out_of_range_unconstructable(self):
        with pytest.raises(ExtractionError):
            rig = vendor_rig("src-a")
            rig.extraction(extraction_confidence=1.5)


# ---------------------------------------------------------------------------
# Traceability [user requirement: exact Evidence -> Claim traceability]
# ---------------------------------------------------------------------------


class TestTraceability:
    def test_fact_derives_from_its_evidence(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        stored = rig.store.find(outcome.object_id)
        derives = stored.attributes.derives_from
        assert len(derives) == 1
        assert derives[0].object_id == ref
        assert derives[0].object_type.value == "Evidence"

    def test_attachment_resolves_and_anchor_locates(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachments[0]
        evidence = rig.store.get_evidence(attachment.evidence_ref)
        assert evidence is not None
        content = evidence.content.content
        assert content.count(attachment.positional_anchor) == 1

    def test_graph_edge_evidence_to_fact(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        stored = rig.store.find(outcome.object_id)
        assert rig.store.resolve_type(ref).value == "Evidence"
        assert stored is not None

    def test_provenance_preserved_upstream(self):
        """Source/provenance preservation: the Fact's lineage reaches the
        Evidence whose provenance is intact and unchanged."""
        rig, ref = changelog_rig()
        before = rig.store.get_evidence(ref).provenance
        extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        after = rig.store.get_evidence(ref).provenance
        assert after == before
        assert after.source_identifier == "src-a"
        assert after.source_type == VENDOR

    def test_independence_never_inferred(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachments[0]
        assert attachment.independence_assessment is Independence.UNASSESSED
        assert not attachment.is_independent
        assert fact.counted_independent() == 0
        assert not fact.is_corroborated


# ---------------------------------------------------------------------------
# One Evidence -> many claims; many Evidence -> distinct claims
# ---------------------------------------------------------------------------


class TestMultiplicity:
    def test_one_evidence_many_claims(self):
        rig, ref = changelog_rig()
        o1 = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        o2 = extract(
            rig.extraction(
                evidence_ref=ref,
                subject="Support",
                predicate="recommends batching smaller",
                anchor="Support recommends batching smaller",
                qualifying_context="vendor support guidance, March",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK + timedelta(seconds=1),
        )
        assert o1.object_id != o2.object_id
        fact1 = rig.store.get_fact(o1.object_id)
        fact2 = rig.store.get_fact(o2.object_id)
        assert fact1.claim.subject != fact2.claim.subject
        for fact in (fact1, fact2):
            assert fact.attachment_count == 1
            assert fact.attachments[0].evidence_ref == ref

    def test_multiple_evidence_distinct_claims_no_collapse(self):
        # PROVENANCE (T03.1.4, supersedes the interim T03.1.1 boundary):
        # this test originally asserted that identical claims from two
        # Evidence stay two Facts because extraction never merged. D-05
        # merging is now implemented, so the assertion is STRENGTHENED,
        # not weakened: the second extraction must attach to the
        # canonical Fact under an explicit F-I4 justification and
        # produce a NEW VERSION -- no accidental collapse (the
        # superseded predecessor keeps its own attachment, F-I2), no
        # parallel Fact.
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Changelog: bulk edits silently fail above 50 SKUs.")
        rb = rig.acquire("src-b", VENDOR,
                         "Forum: bulk edits silently fail above 50 SKUs.")
        o1 = extract(
            rig.extraction(evidence_ref=ra),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        o2 = extract(
            rig.extraction(evidence_ref=rb),
            store=rig.store, log=rig.log,
            clock=lambda: TICK + timedelta(seconds=1),
        )
        from oip.enums import ObjectStatus

        # merged, not a parallel Fact: o2 IS the new canonical version
        assert o2.merged_into == o2.object_id
        assert o1.object_id != o2.object_id  # new version, new object_id
        predecessor = rig.store.get_fact(o1.object_id)
        successor = rig.store.get_fact(o2.object_id)
        # AC2: merge produces a new Fact version
        assert successor.attributes.version == (
            predecessor.attributes.version + 1
        )
        assert rig.store.find(o1.object_id).status is ObjectStatus.SUPERSEDED
        # F-I2: the predecessor's attachment is intact, never removed
        assert predecessor.attachment_count == 1
        # AC1: the equivalent claim ADDED an attachment
        assert successor.attachment_count == 2
        # F-I4: the merge carries the explicit S-3 justification
        assert len(successor.merge_history) == 1
        assert successor.merge_history[0].verdict is Verdict.EQUIVALENT
        assert successor.merge_history[0].merged_evidence_ref == rb

    def test_equivalence_self_report_excluded(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert all(
            other.object_id != outcome.object_id
            for other, _ in outcome.equivalence
        )


# ---------------------------------------------------------------------------
# S-3 equivalence surfaces
# ---------------------------------------------------------------------------


class TestS3Equivalence:
    def test_qualifier_mismatch_never_merges(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Changelog: bulk edits silently fail above 50 SKUs.")
        rb = rig.acquire("src-b", VENDOR,
                         "Forum: bulk edits silently fail above 50 SKUs since v9.")
        o1 = extract(
            rig.extraction(evidence_ref=ra, qualifier="above 50 SKUs"),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        o2 = extract(
            rig.extraction(
                evidence_ref=rb, qualifier="above 50 SKUs since v9",
                anchor="bulk edits silently fail above 50 SKUs since v9",
            ),
            store=rig.store, log=rig.log,
            clock=lambda: TICK + timedelta(seconds=1),
        )
        assert o1.object_id != o2.object_id
        verdicts = {result.verdict for _, result in o2.equivalence}
        assert verdicts <= {Verdict.CONTAINMENT, Verdict.UNCERTAIN}

    def test_value_disagreement_not_equivalent(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Listing A: rated 4.6 stars by buyers.")
        rb = rig.acquire("src-b", VENDOR,
                         "Listing B: rated 4.9 stars by buyers.")
        o1 = extract(
            rig.extraction(
                evidence_ref=ra, subject="Listing A", predicate="rated",
                anchor="Listing A: rated 4.6 stars by buyers.",
                value=Quantity(4.6, 0.1), value_text="4.6",
                qualifier="by buyers",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        o2 = extract(
            rig.extraction(
                evidence_ref=rb, subject="Listing B", predicate="rated",
                anchor="Listing B: rated 4.9 stars by buyers.",
                value=Quantity(4.9, 0.1), value_text="4.9",
                qualifier="by buyers",
            ),
            store=rig.store, log=rig.log,
            clock=lambda: TICK + timedelta(seconds=1),
        )
        assert o1.object_id != o2.object_id
        verdicts = {result.verdict for _, result in o2.equivalence}
        assert Verdict.NOT_EQUIVALENT in verdicts

    def test_contradictory_evidence_both_retained(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Q3 report: churn decreased this quarter.")
        rb = rig.acquire("src-b", VENDOR,
                         "Analytics: churn increased this quarter.")
        o1 = extract(
            rig.extraction(
                evidence_ref=ra, subject="churn", predicate="decreased",
                anchor="churn decreased this quarter",
                qualifying_context="Q3 report",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        o2 = extract(
            rig.extraction(
                evidence_ref=rb, subject="churn", predicate="increased",
                anchor="churn increased this quarter",
                qualifying_context="analytics dashboard",
            ),
            store=rig.store, log=rig.log,
            clock=lambda: TICK + timedelta(seconds=1),
        )
        # both exist; contradiction is information, never silently resolved
        assert rig.store.get_fact(o1.object_id) is not None
        assert rig.store.get_fact(o2.object_id) is not None
        verdicts = {result.verdict for _, result in o2.equivalence}
        assert Verdict.NOT_EQUIVALENT in verdicts


# ---------------------------------------------------------------------------
# Malformed / unusable inputs  [N-10: every refusal recorded]
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_dangling_ref_refused_and_recorded(self):
        rig, _ = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref="EV-MISSING"),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence("EV-MISSING")[-1]
        assert failure.stage is ExtractionStage.EVIDENCE_NOT_FOUND
        assert not failure.attempted

    def test_non_evidence_ref_refused(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=outcome.object_id),
                store=rig.store, log=rig.log,
                clock=lambda: TICK + timedelta(seconds=1),
            )
        failure = rig.log.for_evidence(outcome.object_id)[-1]
        assert failure.stage is ExtractionStage.EVIDENCE_NOT_EXTRACTABLE
        assert failure.reason == "NOT_EVIDENCE"

    def test_retracted_evidence_refused(self):
        rig, ref = changelog_rig()
        rig.store.transition(ref, ObjectStatus.RETRACTED, "source retracted")
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.EVIDENCE_NOT_EXTRACTABLE
        assert failure.reason == "NOT_ACTIVE"

    def test_empty_content_found_nothing_not_failed(self):
        rig = vendor_rig("src-empty")
        ref = rig.acquire("src-empty", VENDOR, "")
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.EMPTY_CONTENT
        assert failure.attempted  # content was in hand; nothing to assert

    def test_non_request_refused(self):
        rig, _ = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                "not a request",
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert len(rig.log) == 1
        failure = next(iter(rig.log))
        assert failure.stage is ExtractionStage.INVALID_REQUEST

    def test_clock_behind_source_refused(self):
        rig, ref = changelog_rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log,
                clock=lambda: T0 - timedelta(hours=2),
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.TEMPORAL_CONFLICT

    def test_malformed_requests_unconstructable(self):
        rig = vendor_rig("src-a")
        for kwargs in (
            {"subject": ""},
            {"predicate": "  "},
            {"qualifier": ""},
            {"qualifying_context": ""},
            {"anchor": ""},
            {"claim_type": "ASSERTION"},
            {"claim_type": ClaimType.ATTRIBUTED_OPINION},
            {"value": Quantity(1, 1)},
            {"value_text": "orphan text"},
        ):
            with pytest.raises(ExtractionError):
                rig.extraction(**kwargs)

    def test_store_rejection_recorded_no_phantom_fact(self):
        from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
        from oip.contract import Engine as _Engine, ObjectType as _OT
        from oip.store import WriteRejectedError

        rig, ref = changelog_rig()
        record = FailureRecord(
            object_id="test:forced",
            object_type=_OT.FACT,
            failed_rules=(
                RuleResult("FORCED", RuleOutcome.FAIL, "forced by test"),
            ),
            recorded_at=TICK,
            engine_configuration_ref="test",
            engine=_Engine.FACT_EXTRACTION,
        )
        original_write = rig.store.write_fact

        def refusing_write(*args, **kwargs):
            raise WriteRejectedError(record)

        rig.store.write_fact = refusing_write  # type: ignore[method-assign]
        try:
            with pytest.raises(ExtractionRefusedError):
                extract(
                    rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log, clock=lambda: TICK,
                )
        finally:
            rig.store.write_fact = original_write  # type: ignore[method-assign]
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.STORE_REJECTED
        assert failure.attempted

    def test_refusal_projected_into_failure_store(self):
        fs = FailureStore()
        rig, ref = changelog_rig()
        rig.log.attach(fs)
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref, anchor="not in content"),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert len(fs) >= 1

    def test_no_fact_exists_after_any_refusal(self):
        rig, ref = changelog_rig()
        for kwargs in (
            {"anchor": "not in content"},
            {"subject": "absent"},
            {"value": Quantity(11, 1), "value_text": "11"},
        ):
            with pytest.raises(ExtractionRefusedError):
                extract(
                    rig.extraction(evidence_ref=ref, **kwargs),
                    store=rig.store, log=rig.log, clock=lambda: TICK,
                )
        assert rig.store.objects_of_type(_fact_type()) == ()


# ---------------------------------------------------------------------------
# Cross-source contamination prevention
# ---------------------------------------------------------------------------


class TestContamination:
    def test_foreign_span_refused(self):
        rig = vendor_rig("src-a", "src-b")
        rig.acquire("src-a", VENDOR,
                    "Changelog: bulk edits silently fail above 50 SKUs.")
        rb = rig.acquire("src-b", VENDOR,
                         "Forum: users complain the mobile app crashes.")
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=rb,
                    anchor="bulk edits silently fail above 50 SKUs",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert rig.log.for_evidence(rb)[-1].stage is (
            ExtractionStage.ANCHOR_NOT_FOUND
        )

    def test_foreign_components_against_local_span_refused(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Changelog: bulk edits silently fail above 50 SKUs.")
        rig.acquire("src-b", VENDOR,
                    "Forum: users complain the mobile app crashes.")
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ra,
                    subject="users",
                    predicate="complain the mobile app crashes",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert rig.log.for_evidence(ra)[-1].stage is (
            ExtractionStage.UNSUPPORTED_CLAIM
        )

    def test_contaminated_claim_never_persists(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Changelog: bulk edits silently fail above 50 SKUs.")
        rb = rig.acquire("src-b", VENDOR,
                         "Forum: users complain the mobile app crashes.")
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ra,
                    subject="users",
                    predicate="complain",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        facts = rig.store.objects_of_type(_fact_type())
        assert facts == ()
        # and the surviving Evidence set is untouched
        assert rig.store.get_evidence(ra) is not None
        assert rig.store.get_evidence(rb) is not None


# ---------------------------------------------------------------------------
# Non-English Evidence
# ---------------------------------------------------------------------------


class TestNonEnglish:
    def test_german_extraction(self):
        rig = make_rig({"src-de": "PUBLISHED_EDITORIAL"})
        ref = rig.acquire(
            "src-de", "PUBLISHED_EDITORIAL",
            "Redaktionell: Straßenverkehrsämter melden zusätzliche "
            "Gebühren für Kurzzeitparker in der Innenstadt.",
        )
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                subject="Straßenverkehrsämter",
                predicate="melden zusätzliche Gebühren",
                anchor=("Straßenverkehrsämter melden zusätzliche Gebühren "
                        "für Kurzzeitparker in der Innenstadt"),
                qualifying_context="redaktionelle Meldung, Innenstadt",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.fact.claim.subject == "Straßenverkehrsämter"

    def test_cjk_extraction_and_density(self):
        rig = vendor_rig("src-cjk")
        content = "リリースノート：一括編集は50SKUを超えると静かに失敗します。"
        ref = rig.acquire("src-cjk", VENDOR, content)
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                subject="一括編集",
                predicate="静かに失敗します",
                anchor="一括編集は50SKUを超えると静かに失敗します",
                qualifying_context="リリースノート、50SKU超",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.fact is not None
        report = build_density_report(rig.store, rig.log, (ref,))
        row = report.rows[0]
        # character-based density works where word counts are meaningless
        assert row.content_words == 1  # no whitespace in the corpus text
        assert row.claims_per_1000_characters > 0

    def test_rtl_extraction(self):
        rig = make_rig({"src-rtl": "SUPPORT_INTERACTION"})
        ref = rig.acquire(
            "src-rtl", "SUPPORT_INTERACTION",
            "تقرير الدعم: يفشل تصدير المكتبات الكبيرة بشكل صامت.",
        )
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                subject="يفشل تصدير المكتبات الكبيرة",
                predicate="بشكل صامت",
                anchor="يفشل تصدير المكتبات الكبيرة بشكل صامت",
                qualifying_context="تقرير الدعم",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.fact is not None


# ---------------------------------------------------------------------------
# AC3 -- density measured from recorded facts
# ---------------------------------------------------------------------------


class TestDensity:
    def test_report_counts_claims_and_refusals(self):
        rig, ref = changelog_rig()
        extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        extract(
            rig.extraction(
                evidence_ref=ref,
                subject="Support",
                predicate="recommends batching smaller",
                anchor="Support recommends batching smaller",
                qualifying_context="vendor support guidance",
            ),
            store=rig.store, log=rig.log,
            clock=lambda: TICK + timedelta(seconds=1),
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(evidence_ref=ref, anchor="absent span"),
                store=rig.store, log=rig.log,
                clock=lambda: TICK + timedelta(seconds=2),
            )
        report = build_density_report(rig.store, rig.log, (ref,))
        assert report.total_claims == 2
        assert report.total_refusals == 1
        assert report.refusals_by_stage == (("ANCHOR_NOT_FOUND", 1),)
        assert report.evidences_without_claims == ()
        row = report.rows[0]
        assert row.source_type == VENDOR  # N-20 stratification
        assert row.claims == 2
        assert row.refusals == 1
        assert row.claims_per_1000_characters > 0
        assert report.density_band[0] <= report.density_band[1]

    def test_zero_claim_evidence_is_flagged(self):
        rig = vendor_rig("src-quiet")
        ref = rig.acquire("src-quiet", VENDOR,
                          "Changelog: bulk edits silently fail above 50 SKUs.")
        report = build_density_report(rig.store, rig.log, (ref,))
        assert report.evidences_without_claims == (ref,)
        assert report.total_claims == 0
        assert report.density_band == (0.0, 0.0)
        assert report.density_spread_ratio is None

    @given(st.floats(min_value=0.1, max_value=1.0))
    def test_density_computed_from_persisted_attachments(self, support):
        rig = vendor_rig("src-p")
        ref = rig.acquire(
            "src-p", VENDOR,
            "Changelog: bulk edits silently fail above 50 SKUs.",
            support=support,
        )
        extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        report = build_density_report(rig.store, rig.log, (ref,))
        assert report.rows[0].claims == 1
        # density derives from the actual content length
        content = rig.store.get_evidence(ref).content.content
        expected = 1 / len(content) * 1000
        assert report.rows[0].claims_per_1000_characters == (
            pytest.approx(expected)
        )


# ---------------------------------------------------------------------------
# Validation branches, registry-gap invariants, density guards
# ---------------------------------------------------------------------------


class TestValidationBranches:
    def test_failure_record_validation(self):
        from oip.extraction import ExtractionFailure

        base = dict(
            evidence_ref="ev-1",
            stage=ExtractionStage.ANCHOR_NOT_FOUND,
            reason="R",
            detail="d",
            failed_at=TICK,
            engine_configuration_ref="cfg",
        )
        for override in (
            {"evidence_ref": ""},
            {"evidence_ref": "   "},
            {"stage": "ANCHOR_NOT_FOUND"},
            {"reason": ""},
            {"detail": ""},
            {"failed_at": "not-a-datetime"},
            {"engine_configuration_ref": ""},
        ):
            with pytest.raises(ExtractionError):
                ExtractionFailure(**{**base, **override})
        ok = ExtractionFailure(**base)
        assert ok.engine.value == "FactExtraction"
        assert ok.attempted

    def test_request_validation_branches(self):
        for kwargs in (
            {"evidence_ref": ""},
            {"evidence_ref": "  "},
            {"claim_type": ClaimType.ATTRIBUTED_OPINION,
             "attributed_to": None},
            {"claim_type": ClaimType.ATTRIBUTED_OPINION,
             "attributed_to": "  "},
            {"extraction_confidence": True},
            {"extraction_confidence": "0.5"},
            {"extraction_confidence": -0.1},
            {"temporal_scope": " "},
            {"population_scope": " "},
        ):
            with pytest.raises(ExtractionError):
                vendor_rig("src-a").extraction(**kwargs)

    def test_attribution_carried_for_opinions(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                claim_type=ClaimType.ATTRIBUTED_OPINION,
                attributed_to="the vendor's changelog",
                qualifying_context=("as the vendor itself frames it, "
                                    "March 2026"),
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ATTRIBUTED_OPINION
        assert fact.attributed_to == "the vendor's changelog"

    def test_scope_fields_carried(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                temporal_scope="March 2026",
                population_scope="bulk-edit operations",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.temporal_scope == "March 2026"
        assert fact.population_scope == "bulk-edit operations"

    def test_evidence_registry_gap_refuses(self):
        """Structural invariant: a store/Evidence-registry disagreement
        refuses rather than extracting blind."""
        rig, ref = changelog_rig()
        original = rig.store.get_evidence
        rig.store.get_evidence = lambda _id: None  # type: ignore[method-assign]
        try:
            with pytest.raises(ExtractionRefusedError):
                extract(
                    rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log, clock=lambda: TICK,
                )
        finally:
            rig.store.get_evidence = original  # type: ignore[method-assign]
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.EVIDENCE_NOT_FOUND
        assert failure.reason == "REGISTRY_GAP"

    def test_fact_registry_gap_reports_refusal_not_phantom(self):
        rig, ref = changelog_rig()
        original = rig.store.get_fact
        rig.store.get_fact = lambda _id: None  # type: ignore[method-assign]
        try:
            with pytest.raises(ExtractionRefusedError):
                extract(
                    rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log, clock=lambda: TICK,
                )
        finally:
            rig.store.get_fact = original  # type: ignore[method-assign]
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.STORE_REJECTED
        assert failure.reason == "REGISTRY_GAP"

    def test_density_guards(self):
        zero = EvidenceDensity(
            evidence_ref="ev-0", source_type=VENDOR,
            claims=0, content_characters=0, content_words=0, refusals=0,
        )
        assert zero.claims_per_1000_characters == 0.0
        assert zero.claims_per_100_words == 0.0
        positive = EvidenceDensity(
            evidence_ref="ev-1", source_type=VENDOR,
            claims=2, content_characters=500, content_words=100,
            refusals=0,
        )
        assert positive.claims_per_100_words == pytest.approx(2.0)
        assert positive.claims_per_1000_characters == pytest.approx(4.0)

    def test_report_row_for_unknown_reference(self):
        rig, _ = changelog_rig()
        report = build_density_report(rig.store, rig.log, ("EV-UNKNOWN",))
        assert report.rows[0].source_type == "UNKNOWN"
        assert report.rows[0].claims == 0

    def test_density_spread_ratio_and_default_scope(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Changelog: bulk edits silently fail above 50 SKUs.")
        rb = rig.acquire("src-b", VENDOR,
                         "Forum: bulk edits silently fail above 50 SKUs.")
        extract(
            rig.extraction(evidence_ref=ra),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        extract(
            rig.extraction(evidence_ref=rb),
            store=rig.store, log=rig.log,
            clock=lambda: TICK + timedelta(seconds=1),
        )
        # default scope: every Evidence in the store
        report = build_density_report(rig.store, rig.log)
        assert report.total_claims == 2
        ratio = report.density_spread_ratio
        assert ratio is not None and ratio >= 1.0
