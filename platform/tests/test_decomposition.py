"""Contract tests for structured claim decomposition. [S-3]

Task: T03.1.2

Architecture References:
- S-3    Claim structure: subject, predicate, qualifier, value;
         equivalence test: four conditions, all must hold;
         merge policy: conservative, under-merge preferred;
         "claims not fitting the structure must be forced or rejected"
- R-5/D-05 Facts are canonical claims; T03.1.4 executes the merge test
- F-V3   claim self-contained; F-I1 never asserts absent Evidence
- F-I4   merge justification = the four conditions (reported, not executed)
- N-4    outputs non-deterministic; property-based assertions
- N-10   refusals recorded, never silent; failed != found-nothing
- M-19   extraction granularity stays OPEN: one request = one claim; no
         compound splitting, no synonym resolution is invented here

T03.1.2 acceptance criteria under test:
  AC1  Every claim decomposed to the defined structure -> IMPLEMENTED
  AC2  Structure supports equivalence comparison       -> IMPLEMENTED
"""

from __future__ import annotations

import math
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.claim import (
    MERGE_POLICY,
    Claim,
    MergeAction,
    Quantity,
    UNQUALIFIED,
    Verdict,
    assess_equivalence,
)
from oip.extraction import (
    DecompositionError,
    ExtractionRefusedError,
    ExtractionStage,
    _ATTEMPTED_STAGES,
    decompose,
    extract,
)
from oip.fact import ClaimType
from tests.test_extraction import TICK, VENDOR, Rig, vendor_rig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_request(**overrides):
    base = dict(
        evidence_ref="unset",
        subject="bulk edits",
        predicate="silently fail above",
        qualifying_context="per vendor changelog, for bulk edits above 50 SKUs",
        anchor="bulk edits silently fail above 50 SKUs",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.8,
    )
    base.update(overrides)
    from oip.extraction import ExtractionRequest

    return ExtractionRequest(**base)


# ---------------------------------------------------------------------------
# AC1 -- decomposition to the defined structure
# ---------------------------------------------------------------------------


class TestDecompositionStructure:
    def test_four_components_byte_identical(self):
        request = make_request(
            qualifier="for bulk edits above 50 SKUs",
        )
        claim = decompose(request)
        assert isinstance(claim, Claim)
        assert claim.subject == "bulk edits"
        assert claim.predicate == "silently fail above"
        assert claim.qualifier == "for bulk edits above 50 SKUs"
        assert claim.value is None

    def test_unqualified_is_the_explicit_none_sentinel(self):
        claim = decompose(make_request())
        assert claim.qualifier == UNQUALIFIED
        assert claim.is_unqualified

    def test_quantity_travels_with_precision_and_unit(self):
        request = make_request(
            anchor="bulk edits silently fail above 50 SKUs",
            value=Quantity(50, 0.5, "SKUs"),
            value_text="50 SKUs",
        )
        claim = decompose(request)
        assert claim.value == Quantity(50, 0.5, "SKUs")
        assert claim.value.precision == 0.5
        assert claim.value.unit == "SKUs"

    def test_value_text_is_not_a_claim_component(self):
        # the Quantity is the S-3 value; value_text is the verbatim span
        # rendering checked by S-5 layer 1, not part of the structure
        request = make_request(
            value=Quantity(50, 0.5, "SKUs"), value_text="50 SKUs"
        )
        claim = decompose(request)
        assert not hasattr(claim, "value_text")

    def test_decomposition_is_idempotent(self):
        request = make_request(value=Quantity(1.5, 0.1), value_text="1.5")
        assert decompose(request) == decompose(request)

    def test_claim_is_frozen(self):
        claim = decompose(make_request())
        with pytest.raises(Exception):
            claim.subject = "mutated"  # type: ignore[misc]

    def test_non_request_refused(self):
        with pytest.raises(DecompositionError):
            decompose("not a request")  # type: ignore[arg-type]

    def test_self_equivalence_witness_holds_for_every_decomposition(self):
        for request in (
            make_request(),
            make_request(qualifier="during March 2026"),
            make_request(
                value=Quantity(50, 0.5, "SKUs"), value_text="50 SKUs"
            ),
            make_request(value=Quantity(0, 0), value_text="0"),
        ):
            witness = assess_equivalence(decompose(request), decompose(request))
            assert witness.verdict is Verdict.EQUIVALENT


# ---------------------------------------------------------------------------
# AC1 -- fail closed: claims the structure cannot carry as comparable
# ---------------------------------------------------------------------------


class TestNonDecomposableFailClosed:
    def test_nan_value_refused(self):
        request = make_request(
            value=Quantity(float("nan"), 0.1), value_text="not a number"
        )
        with pytest.raises(DecompositionError) as exc:
            decompose(request)
        assert "finite" in str(exc.value)

    def test_infinite_value_refused(self):
        request = make_request(
            value=Quantity(float("inf"), 0.1), value_text="infinite"
        )
        with pytest.raises(DecompositionError):
            decompose(request)

    def test_negative_infinite_value_refused(self):
        request = make_request(
            value=Quantity(float("-inf"), 0.1), value_text="-infinite"
        )
        with pytest.raises(DecompositionError):
            decompose(request)

    def test_nan_precision_refused(self):
        request = make_request(
            value=Quantity(50, float("nan")), value_text="50"
        )
        with pytest.raises(DecompositionError) as exc:
            decompose(request)
        assert "precision" in str(exc.value)

    def test_infinite_precision_refused(self):
        request = make_request(
            value=Quantity(50, float("inf")), value_text="50"
        )
        with pytest.raises(DecompositionError):
            decompose(request)

    def test_boolean_value_refused(self):
        # bool is an int subtype in Python; the structure refuses it so a
        # True/False cannot masquerade as the quantity 1/0
        request = make_request(
            value=Quantity(True, 0.1), value_text="true"
        )
        with pytest.raises(DecompositionError) as exc:
            decompose(request)
        assert "real number" in str(exc.value)

    def test_boolean_precision_refused(self):
        request = make_request(value=Quantity(50, True), value_text="50")
        with pytest.raises(DecompositionError):
            decompose(request)

    def test_string_value_refused(self):
        request = make_request(
            value=Quantity("50", 0.1),  # type: ignore[arg-type]
            value_text="50",
        )
        with pytest.raises(DecompositionError):
            decompose(request)

    def test_integer_value_is_a_real_number_and_decomposes(self):
        claim = decompose(make_request(value=Quantity(50, 0), value_text="50"))
        assert claim.value == Quantity(50, 0)

    def test_witness_gate_is_wired_not_decorative(self, monkeypatch):
        # the self-equivalence witness is unreachable through public
        # inputs (finite real values guarantee it) -- so the wiring is
        # proven directly: a broken equivalence judgement must fail the
        # decomposition, closed, rather than write an incomparable Fact
        from oip.claim import EquivalenceResult
        import oip.extraction as extraction_module

        def broken(left, right):
            return EquivalenceResult(
                Verdict.NOT_EQUIVALENT, "mutated witness for wiring test"
            )

        monkeypatch.setattr(extraction_module, "assess_equivalence", broken)
        with pytest.raises(DecompositionError) as exc:
            decompose(make_request())
        assert "not equivalent to itself" in str(exc.value)

    def test_nan_cannot_masquerade_through_a_later_mutation(self):
        # the decomposition is the claim: mutating a decomposed Quantity
        # after the fact is impossible (frozen), so the only path a NaN
        # could take is through decompose -- which refuses it
        with pytest.raises(DecompositionError):
            decompose(
                make_request(
                    value=Quantity(float("nan"), 0.0), value_text="nan"
                )
            )


# ---------------------------------------------------------------------------
# AC1 -- extraction integration: recorded refusal, nothing written
# ---------------------------------------------------------------------------


class TestExtractionIntegration:
    def _rig(self):
        rig = vendor_rig("src-d")
        ref = rig.acquire(
            "src-d", VENDOR,
            "Vendor changelog: bulk edits silently fail above 50 SKUs.",
        )
        return rig, ref

    def test_accepted_extraction_decomposes_to_the_outcome_claim(self):
        rig, ref = self._rig()
        request = make_request(evidence_ref=ref)
        outcome = extract(
            request, store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.claim == decompose(request)

    def test_non_decomposable_refusal_is_recorded_with_stage(self):
        rig, ref = self._rig()
        # "50" occurs at the span, so the layer-1 component gate passes
        # and the refusal is genuinely the decomposition gate's
        request = make_request(
            evidence_ref=ref,
            value=Quantity(float("nan"), 0.1),
            value_text="50",
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                request, store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.DECOMPOSITION_FAILED
        assert failure.reason == "NOT_DECOMPOSABLE"
        assert failure.attempted  # the judgement ran [N-10]

    def test_non_decomposable_refusal_writes_no_fact(self):
        rig, ref = self._rig()
        with pytest.raises(ExtractionRefusedError):
            extract(
                make_request(
                    evidence_ref=ref,
                    value=Quantity(float("inf"), 0.1),
                    value_text="50",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert rig.store.objects_of_type(
            __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT
        ) == ()

    def test_non_decomposable_refusal_registers_no_anchor(self):
        # T03.1.3 invariant: only accepted extractions register
        from oip.extraction import PositionalAnchorRegister

        rig, ref = self._rig()
        register = PositionalAnchorRegister()
        with pytest.raises(ExtractionRefusedError):
            extract(
                make_request(
                    evidence_ref=ref,
                    value=Quantity(float("nan"), 0.1),
                    value_text="50",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
                anchors=register,
            )
        assert len(register) == 0

    def test_refusal_is_projected_into_the_failure_store(self):
        # N-10: the refusal is visible to Orchestration
        from oip.configuration import FailureStore

        rig, ref = self._rig()
        failure_store = FailureStore()
        rig.log.attach(failure_store)
        with pytest.raises(ExtractionRefusedError):
            extract(
                make_request(
                    evidence_ref=ref,
                    value=Quantity(float("nan"), 0.1),
                    value_text="50",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert len(failure_store) > 0

    def test_decomposition_failed_is_an_attempted_stage(self):
        assert ExtractionStage.DECOMPOSITION_FAILED in _ATTEMPTED_STAGES

    def test_t0311_invariance_context_and_anchor_preserved(self):
        rig, ref = self._rig()
        outcome = extract(
            make_request(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachment_for(ref)
        assert attachment.positional_anchor == (
            "bulk edits silently fail above 50 SKUs"
        )
        assert fact.qualifying_context == (
            "per vendor changelog, for bulk edits above 50 SKUs"
        )

    def test_t0313_invariance_locator_still_registered(self):
        from oip.extraction import PositionalAnchorRegister, resolve_locator

        rig, ref = self._rig()
        register = PositionalAnchorRegister()
        outcome = extract(
            make_request(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=register,
        )
        content = rig.store.get_evidence(ref).content.content
        locator = register.locator_for(ref, outcome.claim.subject and (
            "bulk edits silently fail above 50 SKUs"
        ))
        assert locator is not None
        assert resolve_locator(
            content, locator
        ) == "bulk edits silently fail above 50 SKUs"


# ---------------------------------------------------------------------------
# AC2 -- the structure supports the S-3 equivalence comparison
# ---------------------------------------------------------------------------

CLAIM_CORPUS = [
    Claim("bulk edits", "silently fail above", "for edits above 50 SKUs"),
    Claim("bulk edits", "silently fail above", UNQUALIFIED),
    Claim("bulk edits", "silently fail above", "during March 2026"),
    Claim("bulk edits", "silently fail above", "during April 2026"),
    Claim("merchant fees", "rise above", UNQUALIFIED,
          Quantity(3.5, 0.1, "%")),
    Claim("merchant fees", "rise above", UNQUALIFIED,
          Quantity(3.6, 0.1, "%")),
    Claim("merchant fees", "rise above", UNQUALIFIED,
          Quantity(5.0, 0.1, "%")),
    Claim("merchant fees", "rise above", UNQUALIFIED,
          Quantity(3.5, 0.1, "EUR")),
    Claim("merchant fees", "rise above", UNQUALIFIED),
    Claim("sellers", "silently fail above", UNQUALIFIED),
]


class TestEquivalenceSupport:
    def test_every_verdict_carries_a_reason(self):
        # Principle 2: checkable, not opinion -- an engine can state WHY
        for left in CLAIM_CORPUS:
            for right in CLAIM_CORPUS:
                result = assess_equivalence(left, right)
                assert result.reason.strip()
                assert isinstance(result.verdict, Verdict)

    def test_self_equivalence_holds_across_the_corpus(self):
        for claim in CLAIM_CORPUS:
            result = assess_equivalence(claim, claim)
            assert result.verdict is Verdict.EQUIVALENT, result.reason

    def test_verdicts_are_recomputable_from_structure_alone(self):
        # AC2 mechanically: the verdict must equal what the four
        # component checks yield -- no opinion enters anywhere
        for left in CLAIM_CORPUS:
            for right in CLAIM_CORPUS:
                result = assess_equivalence(left, right)
                same_sp = (
                    left.same_subject(right) and left.same_predicate(right)
                )
                values = left.values_agree(right)
                if not same_sp or values is False:
                    expected = Verdict.NOT_EQUIVALENT
                elif left.same_qualifier(right):
                    expected = Verdict.EQUIVALENT
                elif left.qualifier_contains(right) or (
                    right.qualifier_contains(left)
                ):
                    expected = Verdict.CONTAINMENT
                else:
                    expected = Verdict.UNCERTAIN
                assert result.verdict is expected, (
                    left, right, result.verdict, expected,
                )

    def test_verdict_is_symmetric_with_canonical_preserved(self):
        for left in CLAIM_CORPUS:
            for right in CLAIM_CORPUS:
                ab = assess_equivalence(left, right)
                ba = assess_equivalence(right, left)
                assert ab.verdict is ba.verdict
                if ab.verdict is Verdict.CONTAINMENT:
                    # the narrower claim is canonical either way [S-3]
                    assert ab.canonical == ba.canonical
                    assert ab.broader == ba.broader

    def test_precision_governs_value_agreement(self):
        near = assess_equivalence(
            Claim("f", "r", UNQUALIFIED, Quantity(3.7, 0.5, "%")),
            Claim("f", "r", UNQUALIFIED, Quantity(3.5, 0.5, "%")),
        )
        assert near.verdict is Verdict.EQUIVALENT  # |0.2| <= 0.5
        far = assess_equivalence(
            Claim("f", "r", UNQUALIFIED, Quantity(5.0, 0.5, "%")),
            Claim("f", "r", UNQUALIFIED, Quantity(3.5, 0.5, "%")),
        )
        assert far.verdict is Verdict.NOT_EQUIVALENT  # 1.5 > 0.5

    def test_merge_policy_matches_s3_exactly(self):
        # the policy table IS the decision's merge policy, stated as data
        assert MERGE_POLICY[Verdict.EQUIVALENT] is MergeAction.MERGE
        assert MERGE_POLICY[Verdict.CONTAINMENT] is (
            MergeAction.SEPARATE_WITH_DUPLICATES
        )
        assert MERGE_POLICY[Verdict.UNCERTAIN] is (
            MergeAction.SEPARATE_WITH_DUPLICATES
        )
        assert MERGE_POLICY[Verdict.NOT_EQUIVALENT] is MergeAction.SEPARATE

    def test_extraction_reports_equivalence_but_never_merges(self):
        # PROVENANCE (T03.1.4, supersedes the interim T03.1.2 boundary):
        # identical claims from two Evidence used to stay two Facts with
        # the EQUIVALENT verdict reported only. D-05 merging is now
        # implemented, so the verdict is RECORDED as the F-I4 merge
        # justification on the surviving canonical version -- the
        # reasoning surface (Principle 2) is preserved, and the merge is
        # asserted explicitly.
        rig = vendor_rig("src-e1", "src-e2")
        content = "Vendor changelog: bulk edits silently fail above 50 SKUs."
        ref1 = rig.acquire("src-e1", VENDOR, content)
        ref2 = rig.acquire("src-e2", VENDOR, content)
        first = extract(
            make_request(evidence_ref=ref1),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            make_request(evidence_ref=ref2),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        from oip.enums import ObjectStatus

        assert second.merged_into == second.object_id
        canonical = rig.store.get_fact(second.object_id)
        assert canonical.attachment_count == 2
        assert len(canonical.merge_history) == 1
        assert canonical.merge_history[0].verdict is Verdict.EQUIVALENT
        assert canonical.merge_history[0].reason.strip()
        assert rig.store.find(first.object_id).status is ObjectStatus.SUPERSEDED
        # the same claim from two Evidence is ONE canonical lineage
        predecessor = rig.store.get_fact(first.object_id)
        assert predecessor.attributes.identity.lineage_id == (
            canonical.attributes.identity.lineage_id
        )
        # PROVENANCE (T03.1.4): the old final assertion here checked the
        # EQUIVALENT verdict in second.equivalence. After a merge there
        # IS no other ACTIVE Fact to report against; the verdict now
        # lives on the canonical as the F-I4 justification, asserted
        # above.

    def test_synonyms_are_not_resolved(self):
        # S-3: subject identity "still requires judgement" -- the
        # structure reports NOT_EQUIVALENT and the conservative policy
        # keeps both claims; it never decides "sellers" == "merchants"
        left = Claim("sellers", "silently fail above", UNQUALIFIED)
        right = Claim("merchants", "silently fail above", UNQUALIFIED)
        result = assess_equivalence(left, right)
        assert result.verdict is Verdict.NOT_EQUIVALENT
        assert not result.may_merge


# ---------------------------------------------------------------------------
# Adversarial: the attacks the structure must survive without inventing
# ---------------------------------------------------------------------------


class TestAdversarial:
    def _rig_with(self, source: str, content: str):
        rig = vendor_rig(source)
        ref = rig.acquire(source, VENDOR, content)
        return rig, ref

    def test_fabricated_subject_refused_unchanged(self):
        # T03.1.1's layer-1 gate still decides: decomposition happens
        # AFTER the components are proven present at the span
        rig, ref = self._rig_with(
            "src-f", "Vendor changelog: bulk edits silently fail above 50 SKUs."
        )
        with pytest.raises(ExtractionRefusedError) as exc:
            extract(
                make_request(
                    evidence_ref=ref,
                    subject="phantom subject",
                    anchor="bulk edits silently fail above 50 SKUs",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        # the refusal is the components gate, not the decomposition gate:
        # the anchor is the FIRST thing found unsupported
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.UNSUPPORTED_CLAIM

    def test_compound_claim_smuggling_stays_one_verbatim_claim(self):
        # M-19 stays open: the structure does NOT split compound inputs
        # (inventing a splitter would resolve granularity by stealth).
        # A compound subject is carried verbatim as ONE claim.
        rig, ref = self._rig_with(
            "src-c",
            "March report: regional bulk edits and API failures spiked "
            "above alert thresholds, per the on-call log.",
        )
        outcome = extract(
            make_request(
                evidence_ref=ref,
                subject="regional bulk edits and API failures",
                predicate="spiked above alert thresholds",
                qualifying_context="per the on-call log, in March",
                anchor=(
                    "regional bulk edits and API failures spiked "
                    "above alert thresholds"
                ),
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        fact_count = sum(
            1 for _ in rig.store.objects_of_type(
                __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT
            )
        )
        assert fact_count == 1  # one request = one claim; never split
        assert fact.claim.subject == "regional bulk edits and API failures"

    def test_qualifier_stripping_is_impossible(self):
        # the qualifier travels byte-identical: decomposition cannot
        # drop, trim, normalise or default it -- not even padding
        # whitespace (normalisation is comparison-only, never storage)
        qualifier = "  for bulk edits above 50 SKUs, per vendor changelog  "
        request = make_request(qualifier=qualifier)
        claim = decompose(request)
        assert claim.qualifier == qualifier
        assert claim.qualifier != qualifier.strip()
        assert len(claim.qualifier) == len(qualifier)

    def test_synonym_smuggling_never_merges_at_extraction(self):
        rig = vendor_rig("src-s1", "src-s2")
        ref1 = rig.acquire(
            "src-s1", VENDOR,
            "Changelog A: sellers silently fail above 50 SKUs.",
        )
        ref2 = rig.acquire(
            "src-s2", VENDOR,
            "Changelog B: merchants silently fail above 50 SKUs.",
        )
        first = extract(
            make_request(
                evidence_ref=ref1, subject="sellers",
                anchor="sellers silently fail above 50 SKUs",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            make_request(
                evidence_ref=ref2, subject="merchants",
                anchor="merchants silently fail above 50 SKUs",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact_count = sum(
            1 for _ in rig.store.objects_of_type(
                __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT
            )
        )
        assert fact_count == 2
        assert all(
            result.verdict is Verdict.NOT_EQUIVALENT
            for _, result in second.equivalence
        )

    def test_nan_poisoning_cannot_reach_a_fact(self):
        rig, ref = self._rig_with(
            "src-n", "Vendor changelog: bulk edits silently fail above 50 SKUs."
        )
        with pytest.raises(ExtractionRefusedError):
            extract(
                make_request(
                    evidence_ref=ref,
                    value=Quantity(float("nan"), 0.0),
                    value_text="50",
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
            )
        assert rig.store.objects_of_type(
            __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT
        ) == ()


# ---------------------------------------------------------------------------
# N-4 property tests
# ---------------------------------------------------------------------------

COMPONENT_TEXT = st.text(min_size=1, max_size=40).filter(str.strip)
FINITE = st.floats(
    allow_nan=False, allow_infinity=False,
    min_value=-1e9, max_value=1e9,
)
PRECISION = st.floats(
    allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1e6,
)


@settings(max_examples=75, deadline=None)
@given(
    subject=COMPONENT_TEXT,
    predicate=COMPONENT_TEXT,
    qualifier=COMPONENT_TEXT,
    value=FINITE,
    precision=PRECISION,
)
def test_property_decomposition_round_trips_components(
    subject, predicate, qualifier, value, precision,
):
    from oip.extraction import ExtractionRequest

    request = ExtractionRequest(
        evidence_ref="e",
        subject=subject,
        predicate=predicate,
        qualifying_context="context",
        anchor=f"{subject} {predicate}",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.5,
        qualifier=qualifier,
        value=Quantity(value, precision),
        value_text=f"{value}",
    )
    claim = decompose(request)
    assert claim.subject == subject
    assert claim.predicate == predicate
    assert claim.qualifier == qualifier
    assert claim.value == Quantity(value, precision)


@settings(max_examples=75, deadline=None)
@given(value=FINITE, precision=PRECISION)
def test_property_decomposed_claims_are_self_equivalent(value, precision):
    claim = Claim("s", "p", UNQUALIFIED, Quantity(value, precision))
    result = assess_equivalence(claim, claim)
    assert result.verdict is Verdict.EQUIVALENT
    decompose(make_request(value=Quantity(value, precision), value_text="x"))


@settings(max_examples=50, deadline=None)
@given(
    bad=st.sampled_from([float("nan"), float("inf"), float("-inf")]),
    slot=st.sampled_from(["value", "precision"]),
)
def test_property_non_finite_quantities_always_refused(bad, slot):
    if slot == "value":
        request = make_request(value=Quantity(bad, 0.1), value_text="x")
        with pytest.raises(DecompositionError):
            decompose(request)
    else:
        if bad == float("-inf"):
            # negative precision is refused one layer earlier, by the
            # ratified Quantity itself -- fail-closed at every layer
            from oip.claim import PrecisionError

            with pytest.raises(PrecisionError):
                Quantity(1.0, bad)
        else:
            request = make_request(
                value=Quantity(1.0, bad), value_text="x"
            )
            with pytest.raises(DecompositionError):
                decompose(request)


def test_negative_precision_refused_by_the_ratified_type():
    from oip.claim import PrecisionError

    with pytest.raises(PrecisionError):
        Quantity(1.0, -0.1)
