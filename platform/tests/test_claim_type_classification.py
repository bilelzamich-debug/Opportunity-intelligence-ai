"""Contract tests for assertion versus attributed-opinion classification.

Task: T03.1.5

Architecture References:
- F-V4   claim_type present; attributed_to required for ATTRIBUTED_OPINION
- AC1    claim_type populated from the closed two-member taxonomy:
         no third type, no None, no stringly-typed values, no silent
         defaulting
- AC2    whenever the resulting classification is ATTRIBUTED_OPINION the
         claim carries a non-empty attributed_to; an attributed opinion
         without attribution is rejected; attribution never silently
         disappears during extraction
- N-4    classification is deterministic and reproducible: the request
         carries everything; the engine invents no value
- N-10   the classification-conflict refusal is recorded, never silent;
         refused is distinguishable from not-attempted

T03.1.5 acceptance criteria under test:
  AC1  claim_type populated                                  -> IMPLEMENTED
  AC2  attributed_to required for ATTRIBUTED_OPINION          -> IMPLEMENTED

Classification semantics under test (the critical distinction): an
ATTRIBUTED_OPINION requires EXPLICIT ATTRIBUTION to an identifiable
originator. Uncertainty, hedging, low confidence, controversiality, the
source being a vendor or a publication, and attribution-suggesting
wording ("believes", "may", "likely") are NOT attribution and never
move the classification.
"""

from __future__ import annotations

from enum import Enum

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oip.enums import ObjectType
from oip.extraction import (
    ExtractionError,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    PositionalAnchorRegister,
    classify_claim_type,
    extract,
)
from oip.fact import ClaimType
from tests.test_extraction import TICK, VENDOR, Rig, changelog_rig, vendor_rig

NONEMPTY = st.text(min_size=1, max_size=80).filter(str.strip)
CONF = st.floats(min_value=0.0, max_value=1.0)

CLOSED_TAXONOMY = (ClaimType.ASSERTION, ClaimType.ATTRIBUTED_OPINION)


def hedged_rig() -> tuple[Rig, str]:
    """Evidence whose wording hedges attribution-suggestively: it names
    no originator, so no attribution exists to classify on."""
    rig = vendor_rig("src-hedged")
    ref = rig.acquire(
        "src-hedged", VENDOR,
        "Analysts believe the migration may silently fail above 50 SKUs, "
        "which is likely under load.",
    )
    return rig, ref


def hedged_extraction(**overrides):
    """A request over the hedged content whose anchor quotes the hedged
    wording verbatim (subject and predicate both present)."""
    base = dict(
        evidence_ref="unset",
        subject="the migration",
        predicate="silently fail above",
        qualifying_context="as worded by the analysts' coverage, March 2026",
        anchor="the migration may silently fail above 50 SKUs",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.8,
    )
    base.update(overrides)
    return ExtractionRequest(**base)


# ---------------------------------------------------------------------------
# The classification capability  [T03.1.5 deliverable: deterministic, total]
# ---------------------------------------------------------------------------


class TestClassificationCapability:
    def test_no_attribution_classifies_assertion(self):
        for absent in (None, "", "   ", " \t\n "):
            assert classify_claim_type(absent) is ClaimType.ASSERTION

    def test_present_attribution_classifies_attributed_opinion(self):
        for originator in (
            "Gartner",
            "seller-forum-user-88",
            "the vendor's changelog",
            "  the analysts' note  ",
        ):
            assert (
                classify_claim_type(originator)
                is ClaimType.ATTRIBUTED_OPINION
            )

    def test_whitespace_only_attribution_is_not_attribution(self):
        """The F-V4 non-emptiness convention: whitespace names no
        originator, so it classifies exactly like no attribution."""
        assert classify_claim_type("   ") is ClaimType.ASSERTION

    @given(st.none() | st.text(max_size=60))
    def test_classification_is_deterministic(self, attributed_to):
        """Same input, same output: reproducible by construction."""
        assert classify_claim_type(attributed_to) is classify_claim_type(
            attributed_to
        )

    @given(st.none() | st.text(max_size=60))
    def test_classification_returns_only_closed_taxonomy_members(
        self, attributed_to
    ):
        """No third type, no None, no stringly-typed value -- ever."""
        result = classify_claim_type(attributed_to)
        assert isinstance(result, ClaimType)
        assert result in CLOSED_TAXONOMY

    @given(st.text(max_size=60))
    def test_classification_follows_attribution_presence(
        self, attributed_to
    ):
        """The classification is exactly explicit-attribution presence:
        a non-blank originator names an attributable origin; a blank
        one names none."""
        expected = (
            ClaimType.ATTRIBUTED_OPINION
            if attributed_to.strip()
            else ClaimType.ASSERTION
        )
        assert classify_claim_type(attributed_to) is expected

    def test_non_string_originator_refused_loudly(self):
        """Out of the declared str | None domain the capability refuses
        with the module's own error, never a crash."""
        for bogus in (42, 0.5, ["vendor"], {"vendor"}):
            with pytest.raises(ExtractionError):
                classify_claim_type(bogus)


# ---------------------------------------------------------------------------
# Matrix A -- ASSERTION  [AC1]
# ---------------------------------------------------------------------------


class TestAssertionPath:
    def test_valid_assertion_extracted_as_assertion(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.fact.claim_type is ClaimType.ASSERTION
        fact = rig.store.get_fact(outcome.object_id)
        assert fact is not None
        assert fact.claim_type is ClaimType.ASSERTION

    def test_assertion_needs_no_attribution(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref, attributed_to=None),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ASSERTION
        assert fact.attributed_to is None

    @given(CONF)
    def test_accepted_assertion_always_carries_assertion_type(
        self, confidence
    ):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(
                evidence_ref=ref, extraction_confidence=confidence
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ASSERTION
        assert fact.claim_type in CLOSED_TAXONOMY  # populated, valid
        assert fact.attributed_to is None

    def test_assertion_extraction_structure_unchanged(self):
        """Regression: the T03.1.1 assertion Fact structure is exactly
        what it was before classification was integrated."""
        rig, ref = changelog_rig()
        anchors = PositionalAnchorRegister()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=anchors,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim.subject == "bulk edits"
        assert fact.claim.predicate == "silently fail above"
        assert fact.claim.qualifier  # explicit, never blank
        assert fact.qualifying_context == (
            "per vendor changelog, for bulk edits above 50 SKUs"
        )
        attachment = fact.attachment_for(ref)
        assert attachment is not None
        assert attachment.extraction_confidence == pytest.approx(0.8)
        assert attachment.independence_assessment.value == "UNASSESSED"
        assert outcome.locator is not None
        span = "bulk edits silently fail above 50 SKUs"
        assert anchors.locator_for(ref, span) == outcome.locator
        assert fact.attributes.independent_source_count == 1


# ---------------------------------------------------------------------------
# Matrix B -- ATTRIBUTED_OPINION  [AC2]
# ---------------------------------------------------------------------------


class TestAttributedOpinionPath:
    def test_valid_attributed_opinion_extracted(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                claim_type=ClaimType.ATTRIBUTED_OPINION,
                attributed_to="the vendor's changelog",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ATTRIBUTED_OPINION

    def test_attribution_preserved_exactly(self):
        rig, ref = changelog_rig()
        originator = "the vendor's own March changelog"
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                claim_type=ClaimType.ATTRIBUTED_OPINION,
                attributed_to=originator,
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.fact.attributed_to == originator
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.attributed_to == originator  # byte-identical, exact

    @given(NONEMPTY, CONF)
    def test_accepted_opinion_always_carries_attribution_and_type(
        self, originator, confidence
    ):
        """AC2 held for any originator text and any confidence: the
        resulting ATTRIBUTED_OPINION carries its attribution exactly."""
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(
                evidence_ref=ref,
                claim_type=ClaimType.ATTRIBUTED_OPINION,
                attributed_to=originator,
                extraction_confidence=confidence,
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ATTRIBUTED_OPINION
        assert fact.attributed_to == originator

    def test_whitespace_only_attribution_rejected(self):
        rig = vendor_rig("src-a")
        with pytest.raises(ExtractionError):
            rig.extraction(
                claim_type=ClaimType.ATTRIBUTED_OPINION,
                attributed_to="   ",
            )

    def test_missing_attribution_rejected(self):
        rig = vendor_rig("src-a")
        for absent in (None, ""):
            with pytest.raises(ExtractionError):
                rig.extraction(
                    claim_type=ClaimType.ATTRIBUTED_OPINION,
                    attributed_to=absent,
                )

    def test_attribution_never_silently_disappears(self):
        """A request that states ASSERTION while naming an originator is
        internally contradictory. It is refused and recorded -- the
        attribution is never dropped, the type never flipped."""
        rig, ref = changelog_rig()
        anchors = PositionalAnchorRegister()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ref,
                    claim_type=ClaimType.ASSERTION,
                    attributed_to="the vendor's changelog",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
                anchors=anchors,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.INVALID_REQUEST
        assert failure.reason == "CLAIM_TYPE_CONFLICT"
        assert not failure.attempted  # request validity, no content judged
        assert "never silently" in failure.detail
        assert rig.store.objects_of_type(ObjectType.FACT) == ()
        assert len(anchors) == 0  # refused extractions register no anchor

    def test_whitespace_attribution_with_assertion_is_no_attribution(self):
        """Whitespace names no originator, so it does not conflict with
        a stated ASSERTION: there is nothing to attribute."""
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref, attributed_to="   "),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ASSERTION
        assert fact.attributed_to is None


# ---------------------------------------------------------------------------
# Matrix C -- invalid claim types  [AC1: closed taxonomy, no silent default]
# ---------------------------------------------------------------------------


class TestInvalidClaimType:
    def test_non_claim_type_values_rejected(self):
        rig = vendor_rig("src-a")
        for bogus in ("ASSERTION", "assertion", 1, object()):
            with pytest.raises(ExtractionError):
                rig.extraction(claim_type=bogus)

    def test_none_claim_type_rejected(self):
        rig = vendor_rig("src-a")
        with pytest.raises(ExtractionError):
            rig.extraction(claim_type=None)

    def test_no_third_claim_type_accepted(self):
        """No arbitrary third type -- not a lookalike string, not a
        foreign enum member (even one whose value collides with a
        ratified member) -- can enter through the request."""
        rig = vendor_rig("src-a")

        class FakeClaimType(str, Enum):
            HEDGED_SPECULATION = "HEDGED_SPECULATION"
            ATTRIBUTED_OPINION = "ATTRIBUTED_OPINION"

        for bogus in (
            "HEDGED_SPECULATION",
            FakeClaimType.HEDGED_SPECULATION,
            FakeClaimType.ATTRIBUTED_OPINION,
        ):
            with pytest.raises(ExtractionError):
                rig.extraction(claim_type=bogus)


# ---------------------------------------------------------------------------
# Classification semantics  [the critical distinction: explicit attribution]
# ---------------------------------------------------------------------------


class TestClassificationSemantics:
    def test_hedged_wording_without_originator_is_assertion(self):
        """"believes"/"may"/"likely" in the wording are NOT attribution:
        without a named originator the claim is an assertion of the
        stated proposition."""
        rig, ref = hedged_rig()
        outcome = extract(
            hedged_extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ASSERTION
        assert fact.attributed_to is None

    def test_low_confidence_and_uncertainty_do_not_create_attribution(
        self,
    ):
        """Low extraction confidence and an uncertain context classify
        exactly like any other unattributed claim."""
        rig, ref = hedged_rig()
        outcome = extract(
            hedged_extraction(
                evidence_ref=ref,
                extraction_confidence=0.05,
                qualifying_context="uncertain; the analysts hedge throughout",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ASSERTION
        assert fact.attributed_to is None

    def test_vendor_publication_source_is_not_attribution(self):
        """That the Evidence comes from a vendor publication does not
        attribute the claim: attribution requires a named originator."""
        rig, ref = changelog_rig()  # source_type VENDOR_PUBLICATION
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ASSERTION
        assert fact.attributed_to is None

    def test_named_originator_classifies_attributed_opinion(self):
        """The same hedged wording, with the originator the proposition
        is attributed to actually named, classifies ATTRIBUTED_OPINION
        and carries the attribution into the Fact."""
        rig, ref = hedged_rig()
        outcome = extract(
            hedged_extraction(
                evidence_ref=ref,
                claim_type=ClaimType.ATTRIBUTED_OPINION,
                attributed_to="the analysts' March note",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        assert fact.claim_type is ClaimType.ATTRIBUTED_OPINION
        assert fact.attributed_to == "the analysts' March note"

    def test_conflict_refused_regardless_of_evidence_state(self):
        """The classification gate sits at the extraction boundary, on
        the request itself: a contradictory request is refused as such
        even when its Evidence reference resolves to nothing."""
        rig = vendor_rig("src-a")
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref="EV-NOT-STORED",
                    claim_type=ClaimType.ASSERTION,
                    attributed_to="someone",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = next(iter(rig.log))
        assert failure.stage is ExtractionStage.INVALID_REQUEST
        assert failure.reason == "CLAIM_TYPE_CONFLICT"
