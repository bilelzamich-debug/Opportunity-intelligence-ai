"""Contract tests for structured claims and S-3 semantic equivalence.

Task: T01.7.2a

Architecture References:
- S-3   Claim decomposition; four-condition equivalence test; merge policy
- R-5   Facts are canonical claims
- I2    Merge errors are irreversible, hence the conservative bias
- M-62  Semantic equivalence criterion (closed by S-3)
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.claim import (
    MERGE_POLICY,
    UNQUALIFIED,
    Claim,
    ClaimStructureError,
    MergeAction,
    PrecisionError,
    Quantity,
    Verdict,
    assess_equivalence,
)

TEXT = st.text(min_size=1, max_size=20).filter(lambda s: s.strip())


# ===========================================================================
# Claim structure [S-3]
# ===========================================================================

class TestClaimStructure:
    def test_four_components(self):
        claim = Claim("sellers", "report failures", "segment A",
                      Quantity(50, 1, "items"))
        assert claim.subject and claim.predicate and claim.qualifier
        assert claim.value is not None

    def test_subject_required(self):
        with pytest.raises(ClaimStructureError):
            Claim("", "predicate")

    def test_predicate_required(self):
        with pytest.raises(ClaimStructureError):
            Claim("subject", "")

    def test_qualifier_required_explicitly(self):
        """S-3: state NONE rather than leaving it empty."""
        with pytest.raises(ClaimStructureError):
            Claim("subject", "predicate", "")

    def test_qualifier_defaults_to_none_sentinel(self):
        assert Claim("s", "p").qualifier == UNQUALIFIED
        assert Claim("s", "p").is_unqualified

    def test_value_is_optional(self):
        assert Claim("s", "p").value is None
        assert not Claim("s", "p").is_quantitative

    @pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
    def test_whitespace_is_not_a_component(self, blank):
        with pytest.raises(ClaimStructureError):
            Claim(blank, "predicate")

    def test_claim_is_frozen(self):
        with pytest.raises(Exception):
            Claim("s", "p").subject = "other"

    def test_renders_readably(self):
        text = Claim("sellers", "report failures", "segment A").as_text()
        assert "sellers" in text and "segment A" in text

    def test_unqualified_omits_qualifier_from_text(self):
        assert "(" not in Claim("s", "p").as_text()


class TestQuantity:
    def test_precision_required_non_negative(self):
        with pytest.raises(PrecisionError):
            Quantity(1.0, -0.1)

    def test_agreement_within_precision(self):
        assert Quantity(50, 2).agrees_with(Quantity(51, 2))
        assert not Quantity(50, 0.1).agrees_with(Quantity(51, 0.1))

    def test_coarser_precision_governs(self):
        assert Quantity(50, 0.0).agrees_with(Quantity(55, 10))

    def test_units_must_match(self):
        assert not Quantity(50, 5, "items").agrees_with(Quantity(50, 5, "percent"))


# ===========================================================================
# Equivalence: condition 1 and 2 (subject, predicate)
# ===========================================================================

class TestSubjectAndPredicate:
    def test_identical_claims_are_equivalent(self):
        base = Claim("sellers", "report failures", "segment A")
        result = assess_equivalence(base, Claim("sellers", "report failures",
                                                "segment A"))
        assert result.verdict is Verdict.EQUIVALENT
        assert result.may_merge

    def test_different_subject_not_equivalent(self):
        result = assess_equivalence(
            Claim("sellers", "report failures"),
            Claim("merchants", "report failures"),
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT
        assert "subjects differ" in result.reason

    def test_different_predicate_not_equivalent(self):
        result = assess_equivalence(
            Claim("sellers", "report failures"),
            Claim("sellers", "report delays"),
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT
        assert "predicates differ" in result.reason

    def test_comparison_is_case_and_whitespace_insensitive(self):
        result = assess_equivalence(
            Claim("Sellers", "Report  Failures"),
            Claim("sellers", "report failures"),
        )
        assert result.verdict is Verdict.EQUIVALENT

    def test_synonyms_are_not_resolved(self):
        """S-3 records that subject identity still requires judgement."""
        result = assess_equivalence(
            Claim("sellers", "report failures"),
            Claim("vendors", "report failures"),
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT


# ===========================================================================
# Equivalence: condition 3 (qualifiers) -- containment
# ===========================================================================

class TestQualifierContainment:
    def test_identical_qualifiers_equivalent(self):
        result = assess_equivalence(
            Claim("s", "p", "segment A"), Claim("s", "p", "segment A")
        )
        assert result.verdict is Verdict.EQUIVALENT

    def test_unqualified_contains_qualified(self):
        result = assess_equivalence(
            Claim("s", "p", UNQUALIFIED), Claim("s", "p", "segment A")
        )
        assert result.verdict is Verdict.CONTAINMENT

    def test_narrower_claim_is_canonical(self):
        """S-3: a broad claim is not evidence for a narrow one."""
        broad = Claim("s", "p", UNQUALIFIED)
        narrow = Claim("s", "p", "segment A")
        result = assess_equivalence(broad, narrow)
        assert result.canonical == narrow
        assert result.broader == broad

    def test_containment_is_symmetric_in_verdict(self):
        broad = Claim("s", "p", UNQUALIFIED)
        narrow = Claim("s", "p", "segment A")
        assert assess_equivalence(broad, narrow).verdict is Verdict.CONTAINMENT
        assert assess_equivalence(narrow, broad).verdict is Verdict.CONTAINMENT

    def test_containment_picks_the_same_canonical_either_way(self):
        broad = Claim("s", "p", UNQUALIFIED)
        narrow = Claim("s", "p", "segment A")
        assert assess_equivalence(broad, narrow).canonical == narrow
        assert assess_equivalence(narrow, broad).canonical == narrow

    def test_containment_does_not_merge(self):
        result = assess_equivalence(
            Claim("s", "p", UNQUALIFIED), Claim("s", "p", "segment A")
        )
        assert not result.may_merge
        assert result.requires_duplicates_link

    def test_two_different_qualifiers_are_uncertain(self):
        """S-3 warns containment is subtle; undecidable cases do not merge."""
        result = assess_equivalence(
            Claim("s", "p", "segment A"), Claim("s", "p", "segment B")
        )
        assert result.verdict is Verdict.UNCERTAIN
        assert "undecidable" in result.reason

    def test_uncertain_does_not_merge(self):
        result = assess_equivalence(
            Claim("s", "p", "segment A"), Claim("s", "p", "segment B")
        )
        assert not result.may_merge
        assert result.requires_duplicates_link


# ===========================================================================
# Equivalence: condition 4 (values)
# ===========================================================================

class TestValueAgreement:
    def test_matching_values_equivalent(self):
        result = assess_equivalence(
            Claim("s", "p", "q", Quantity(50, 1)),
            Claim("s", "p", "q", Quantity(50, 1)),
        )
        assert result.verdict is Verdict.EQUIVALENT

    def test_values_within_precision_equivalent(self):
        result = assess_equivalence(
            Claim("s", "p", "q", Quantity(50, 5)),
            Claim("s", "p", "q", Quantity(53, 5)),
        )
        assert result.verdict is Verdict.EQUIVALENT

    def test_values_outside_precision_not_equivalent(self):
        result = assess_equivalence(
            Claim("s", "p", "q", Quantity(50, 0.5)),
            Claim("s", "p", "q", Quantity(500, 0.5)),
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT
        assert "values disagree" in result.reason

    def test_one_sided_quantification_not_equivalent(self):
        result = assess_equivalence(
            Claim("s", "p", "q", Quantity(50, 1)), Claim("s", "p", "q")
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT

    def test_neither_quantified_is_fine(self):
        result = assess_equivalence(Claim("s", "p", "q"), Claim("s", "p", "q"))
        assert result.verdict is Verdict.EQUIVALENT

    def test_unit_mismatch_not_equivalent(self):
        result = assess_equivalence(
            Claim("s", "p", "q", Quantity(50, 1, "items")),
            Claim("s", "p", "q", Quantity(50, 1, "percent")),
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT

    def test_value_check_precedes_qualifier_verdict(self):
        """A numeric disagreement must not be masked as UNCERTAIN."""
        result = assess_equivalence(
            Claim("s", "p", "segment A", Quantity(50, 1)),
            Claim("s", "p", "segment B", Quantity(900, 1)),
        )
        assert result.verdict is Verdict.NOT_EQUIVALENT


# ===========================================================================
# Merge policy [S-3]
# ===========================================================================

class TestMergePolicy:
    def test_policy_covers_every_verdict(self):
        assert set(MERGE_POLICY) == set(Verdict)

    def test_only_equivalent_merges(self):
        merging = [v for v, a in MERGE_POLICY.items() if a is MergeAction.MERGE]
        assert merging == [Verdict.EQUIVALENT]

    def test_uncertain_and_containment_link_duplicates(self):
        for verdict in (Verdict.UNCERTAIN, Verdict.CONTAINMENT):
            assert MERGE_POLICY[verdict] is MergeAction.SEPARATE_WITH_DUPLICATES

    def test_not_equivalent_separates_cleanly(self):
        assert MERGE_POLICY[Verdict.NOT_EQUIVALENT] is MergeAction.SEPARATE

    def test_under_merge_bias_is_structural(self):
        """Three of four verdicts refuse to merge. [S-3, I2]"""
        non_merging = [a for a in MERGE_POLICY.values() if a is not MergeAction.MERGE]
        assert len(non_merging) == 3

    def test_every_result_reports_a_reason(self):
        pairs = [
            (Claim("a", "p"), Claim("b", "p")),
            (Claim("s", "p"), Claim("s", "q")),
            (Claim("s", "p", "x"), Claim("s", "p", "y")),
            (Claim("s", "p", UNQUALIFIED), Claim("s", "p", "x")),
            (Claim("s", "p"), Claim("s", "p")),
        ]
        for left, right in pairs:
            assert assess_equivalence(left, right).reason.strip()


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=300, deadline=None)
@given(subject=TEXT, predicate=TEXT, qualifier=TEXT)
def test_claim_is_always_equivalent_to_itself(subject, predicate, qualifier):
    claim = Claim(subject, predicate, qualifier)
    assert assess_equivalence(claim, claim).verdict is Verdict.EQUIVALENT


@settings(max_examples=300, deadline=None)
@given(a=TEXT, b=TEXT, predicate=TEXT, qualifier=TEXT)
def test_verdict_is_symmetric(a, b, predicate, qualifier):
    """Equivalence must not depend on argument order."""
    left = Claim(a, predicate, qualifier)
    right = Claim(b, predicate, qualifier)
    assert (
        assess_equivalence(left, right).verdict
        is assess_equivalence(right, left).verdict
    )


@settings(max_examples=300, deadline=None)
@given(subject=TEXT, predicate=TEXT, qualifier=TEXT)
def test_broader_never_merges_with_narrower(subject, predicate, qualifier):
    """A broad claim is never evidence for a narrow one. [S-3]"""
    if qualifier.strip().casefold() == UNQUALIFIED.casefold():
        return
    result = assess_equivalence(
        Claim(subject, predicate, UNQUALIFIED),
        Claim(subject, predicate, qualifier),
    )
    assert not result.may_merge


@settings(max_examples=300, deadline=None)
@given(
    subject=TEXT, predicate=TEXT,
    left=st.floats(0, 1000, allow_nan=False),
    right=st.floats(0, 1000, allow_nan=False),
    precision=st.floats(0, 10, allow_nan=False),
)
def test_value_verdict_matches_the_arithmetic(
    subject, predicate, left, right, precision
):
    result = assess_equivalence(
        Claim(subject, predicate, "q", Quantity(left, precision)),
        Claim(subject, predicate, "q", Quantity(right, precision)),
    )
    agrees = abs(left - right) <= precision
    assert (result.verdict is Verdict.EQUIVALENT) is agrees


@settings(max_examples=200, deadline=None)
@given(subject=TEXT, predicate=TEXT, qualifier=TEXT)
def test_every_pair_yields_exactly_one_action(subject, predicate, qualifier):
    result = assess_equivalence(
        Claim(subject, predicate, qualifier), Claim(subject, predicate, "other")
    )
    assert result.action in set(MergeAction)
