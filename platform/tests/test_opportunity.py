"""Contract tests for the Opportunity object type.

Task: T01.7.5

Architecture References:
- O-V1..O-V7  Opportunity validation rules (SEVEN, per IOM section 3.5)
- O-I1..O-I4  Opportunity integrity constraints
- R-3         Confidence ceiling strictly enforced
- D-02        REJECTED objects retained as learning signal
- S-4         Opportunity inherits its Pattern's sufficiency
- N-6         Graph is a derived index, never authoritative alone
- M-14        Scoring OPEN and BLOCKING: no Opportunity reaches ACTIVE unscored
- M-26/M-27   Opportunity definition and prioritisation OPEN
- C-01        Scoring ownership OPEN
- OQ-19       Point-in-time vs recomputed scoring OPEN

Acceptance criteria under test:
  AC1  score_model_version required with score
  AC2  O-V5 confidence ceiling enforced
  AC3  Object cannot reach ACTIVE while scoring undefined (documented)
"""

from __future__ import annotations

import threading

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.contract import Confidence
from oip.enums import Engine, ObjectStatus, ObjectType, RelationshipType
from oip.identity import IdentityAllocator
from oip.opportunity import (
    DESIGN_MARKERS,
    OPPORTUNITY_RULES,
    Opportunity,
    OpportunityError,
    OpportunityIntegrity,
    OriginatingPatternError,
    QuantitativeClaim,
    QuantitativeClaimError,
    RejectionRationaleError,
    Score,
    ScoreComparabilityError,
    ScoreDimension,
    ScoreError,
    detect_solution_design,
    find_quantities,
    ov1_originating_patterns_resolve,
    ov2_no_solution_design,
    ov3_score_with_model_version,
    ov4_scoring_explanation_references_dimensions,
    ov5_confidence_within_pattern_ceiling,
    ov6_quantitative_claims_trace,
    ov7_rejection_rationale_present,
    rank,
)
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs
from tests.test_pattern import write_pattern_from, write_problems

STATEMENT = (
    "Provide marketplace sellers with reliable, immediate feedback on the "
    "outcome of bulk operations, so that partial or total failure is known at "
    "the time it occurs rather than discovered through customer impact."
)
VALUE_HYPOTHESIS = (
    "The pattern shows a consistent absence of feedback across four "
    "operational domains, with cost borne as rework and customer-facing "
    "error. Value arises from eliminating delayed discovery."
)
BENEFICIARIES = (
    "Segment A sellers and adjacent segments operating at inventory scale."
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def dimension(name: str, value: float = 0.6, **kw) -> ScoreDimension:
    return ScoreDimension(name=name, value=value, **kw)


def score(
    value: float = 0.62,
    model_version: str = "score-model-v1",
    dimension_names: tuple[str, ...] = ("reach", "severity"),
) -> Score:
    return Score(
        value=value,
        model_version=model_version,
        dimensions=tuple(dimension(n) for n in dimension_names),
    )


def make_opportunity(
    allocator: IdentityAllocator,
    pattern_refs: tuple[str, ...] = ("obj-pt-1",),
    *,
    originating: tuple[str, ...] | None = None,
    source_count: int = 3,
    upstream_ceiling: float | None = None,
    support: float = 0.62,
    assertion: float = 0.58,
    status: ObjectStatus = ObjectStatus.ACTIVE,
    status_reason: str | None = None,
    scored: bool = True,
    **overrides,
) -> Opportunity:
    identity = overrides.pop("identity", None) or allocator.new_object()
    origins = originating if originating is not None else pattern_refs
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.OPPORTUNITY,
        tuple((r, ObjectType.PATTERN) for r in pattern_refs),
        status=status,
        status_reason=status_reason,
        source_count=source_count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
    )
    kwargs = {
        "attributes": attributes,
        "opportunity_statement": overrides.pop("opportunity_statement", STATEMENT),
        "originating_patterns": overrides.pop("originating_patterns", origins),
        "value_hypothesis": overrides.pop("value_hypothesis", VALUE_HYPOTHESIS),
        "beneficiary_population": overrides.pop(
            "beneficiary_population", BENEFICIARIES
        ),
    }
    if scored and "score" not in overrides:
        kwargs["score"] = score()
        kwargs["scoring_explanation"] = (
            "Reach dominates: the pattern spans four domains. Severity is "
            "moderate because cost is rework rather than loss."
        )
    kwargs.update(overrides)
    return Opportunity(**kwargs)


def ctx(opportunity: Opportunity, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": opportunity.attributes, "opportunity": opportunity}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def write_patterns(store, allocator, n: int = 1):
    """Persist n Patterns, each on its own distinct Problems."""
    stored = []
    for _ in range(n):
        problems = write_problems(store, allocator, 2)
        stored.append(write_pattern_from(store, allocator, problems))
    return stored


def write_opportunity_from(
    store, allocator, stored_patterns, predecessor_id: str | None = None, **overrides
):
    refs = tuple(p.object_id for p in stored_patterns)
    ceiling = min(
        p.attributes.confidence.effective_confidence for p in stored_patterns
    )
    return store.write_opportunity(
        make_opportunity(allocator, refs, upstream_ceiling=ceiling, **overrides),
        predecessor_id=predecessor_id,
    )


@pytest.fixture()
def patterns(store, allocator):
    return write_patterns(store, allocator, 1)


# ===========================================================================
# AC1 -- score_model_version required with score  [O-V3]
# ===========================================================================

class TestScoreModelVersion:
    def test_version_required_on_score(self):
        with pytest.raises(ScoreError) as exc:
            Score(value=0.6, model_version="")
        assert "silently incomparable" in str(exc.value)

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_blank_version_rejected(self, blank):
        with pytest.raises(ScoreError):
            Score(value=0.6, model_version=blank)

    def test_version_carried_through(self, allocator):
        o = make_opportunity(allocator)
        assert o.score_model_version == "score-model-v1"

    def test_ov3_passes_when_scored(self, allocator):
        result = ov3_score_with_model_version(ctx(make_opportunity(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "score-model-v1" in result.detail

    def test_ov3_detects_a_stripped_version(self, allocator):
        o = make_opportunity(allocator)
        object.__setattr__(o.score, "model_version", "")
        result = ov3_score_with_model_version(ctx(o))
        assert result.failed
        assert "silently incomparable" in result.detail

    def test_score_value_must_be_numeric(self):
        with pytest.raises(ScoreError):
            Score(value="high", model_version="v1")

    def test_boolean_is_not_a_score(self):
        with pytest.raises(ScoreError):
            Score(value=True, model_version="v1")

    def test_dimension_requires_a_name(self):
        with pytest.raises(ScoreError):
            ScoreDimension(name="  ", value=0.5)

    def test_dimension_value_must_be_numeric(self):
        with pytest.raises(ScoreError):
            ScoreDimension(name="reach", value="lots")

    def test_duplicate_dimensions_rejected(self):
        with pytest.raises(ScoreError):
            Score(
                value=0.6, model_version="v1",
                dimensions=(dimension("reach"), dimension("Reach")),
            )

    def test_dimension_lookup_is_case_insensitive(self):
        assert score().dimension("REACH") is not None
        assert score().dimension("absent") is None

    def test_store_requires_the_version(self, store, allocator, patterns):
        o = make_opportunity(
            allocator, tuple(p.object_id for p in patterns),
            upstream_ceiling=min(
                p.attributes.confidence.effective_confidence for p in patterns
            ),
        )
        object.__setattr__(o.score, "model_version", "  ")
        with pytest.raises(WriteRejectedError) as exc:
            store.write_opportunity(o)
        assert "O-V3" in exc.value.failure.rule_ids


# ===========================================================================
# AC2 -- O-V5 confidence ceiling  [O-V5, R-3]
# ===========================================================================

class TestConfidenceCeiling:
    def test_rule_registered(self, store):
        assert "O-V5" in store.acceptance.rule_ids

    def test_within_ceiling_passes(self, allocator):
        o = make_opportunity(allocator, support=0.5, assertion=0.5)
        result = ov5_confidence_within_pattern_ceiling(
            ctx(o, upstream_confidence=lambda ref: 0.7)
        )
        assert result.outcome is RuleOutcome.PASS
        assert "within originating Pattern ceiling" in result.detail

    def test_exceeding_ceiling_rejected(self, allocator):
        o = make_opportunity(allocator, support=0.9, assertion=0.9)
        result = ov5_confidence_within_pattern_ceiling(
            ctx(o, upstream_confidence=lambda ref: 0.4)
        )
        assert result.failed
        assert "most consequential failure" in result.detail

    def test_equal_to_ceiling_accepted(self, allocator):
        o = make_opportunity(allocator, support=0.6, assertion=0.6)
        result = ov5_confidence_within_pattern_ceiling(
            ctx(o, upstream_confidence=lambda ref: 0.6)
        )
        assert result.outcome is RuleOutcome.PASS

    def test_unresolvable_pattern_fails_closed(self, allocator):
        """A ceiling cannot be established from a partial upstream set."""
        o = make_opportunity(allocator, ("obj-pt-1", "obj-pt-2"))
        known = {"obj-pt-1": 0.8}
        result = ov5_confidence_within_pattern_ceiling(
            ctx(o, upstream_confidence=known.get)
        )
        assert result.failed
        assert "partial upstream set" in result.detail

    def test_lowest_pattern_sets_the_ceiling(self, allocator):
        o = make_opportunity(allocator, ("obj-pt-1", "obj-pt-2"), support=0.5, assertion=0.5)
        ceilings = {"obj-pt-1": 0.9, "obj-pt-2": 0.3}
        result = ov5_confidence_within_pattern_ceiling(
            ctx(o, upstream_confidence=ceilings.get)
        )
        assert result.failed
        assert "0.3" in result.detail

    def test_skips_without_a_provider(self, allocator):
        result = ov5_confidence_within_pattern_ceiling(ctx(make_opportunity(allocator)))
        assert result.outcome is RuleOutcome.SKIP

    def test_store_rejects_inflation_end_to_end(self, store, allocator, patterns):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_opportunity(
                make_opportunity(
                    allocator, tuple(p.object_id for p in patterns),
                    support=0.99, assertion=0.99,
                )
            )
        assert {"V5", "O-V5"} <= set(exc.value.failure.rule_ids)

    def test_store_accepts_honest_confidence(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        ceiling = patterns[0].attributes.confidence.effective_confidence
        assert stored.attributes.confidence.effective_confidence <= ceiling

    @settings(max_examples=200, deadline=None)
    @given(
        own=st.floats(min_value=0.0, max_value=1.0),
        ceiling=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_ceiling_holds_over_arbitrary_pairs(self, own, ceiling):
        """AC2: O-V5 fails exactly when the ceiling is exceeded."""
        allocator = IdentityAllocator()
        o = make_opportunity(allocator, support=own, assertion=own)
        result = ov5_confidence_within_pattern_ceiling(
            ctx(o, upstream_confidence=lambda ref: ceiling)
        )
        assert result.failed == (own > ceiling + 1e-9)


# ===========================================================================
# AC3 -- cannot reach ACTIVE while scoring undefined  [O-V3, M-14]
# ===========================================================================

class TestBlockingConditionM14:
    def test_unscored_opportunity_is_constructible(self, allocator):
        """The TYPE permits it; O-V3 is what forbids ACTIVE. [M-14]"""
        o = make_opportunity(allocator, scored=False)
        assert not o.is_scored
        assert o.score_model_version is None

    def test_unscored_fails_ov3_naming_the_marker(self, allocator):
        result = ov3_score_with_model_version(
            ctx(make_opportunity(allocator, scored=False))
        )
        assert result.failed
        assert "M-14 open, blocking" in result.detail
        assert "C-01" in result.detail

    def test_unscored_cannot_be_written(self, store, allocator, patterns):
        """The IOM's own example is PROPOSED for exactly this reason."""
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(store, allocator, patterns, scored=False)
        assert "O-V3" in exc.value.failure.rule_ids

    def test_no_placeholder_scale_is_invented(self, allocator):
        """M-14 must stay open: no dimension vocabulary is asserted."""
        arbitrary = score(dimension_names=("anything", "at-all", "unvalidated"))
        o = make_opportunity(
            allocator, score=arbitrary,
            scoring_explanation="anything drove this",
        )
        assert not ov3_score_with_model_version(ctx(o)).failed
        assert not ov4_scoring_explanation_references_dimensions(ctx(o)).failed

    def test_ov4_skips_when_unscored(self, allocator):
        result = ov4_scoring_explanation_references_dimensions(
            ctx(make_opportunity(allocator, scored=False))
        )
        assert result.outcome is RuleOutcome.SKIP
        assert "M-14" in result.detail

    def test_rejected_unscored_opportunity_is_permitted(self, store, allocator, patterns):
        """D-02: a rejected candidate is retained even though unscored."""
        stored = write_opportunity_from(
            store, allocator, patterns,
            scored=False,
            status=ObjectStatus.REJECTED,
            status_reason="below viability",
            rejection_rationale="Value hypothesis not supported by the pattern.",
        )
        assert stored.status is ObjectStatus.REJECTED
        assert len(store.opportunities.rejected_opportunities()) == 1


# ===========================================================================
# O-V1  originating patterns
# ===========================================================================

class TestOriginatingPatterns:
    def test_required_at_construction(self, allocator):
        with pytest.raises(OriginatingPatternError):
            make_opportunity(allocator, ("obj-pt-1",), originating_patterns=())

    def test_duplicates_rejected(self, allocator):
        with pytest.raises(OriginatingPatternError):
            make_opportunity(
                allocator, ("obj-pt-1",),
                originating_patterns=("obj-pt-1", "obj-pt-1"),
            )

    def test_must_be_a_subset_of_derives_from(self, allocator):
        with pytest.raises(OriginatingPatternError) as exc:
            make_opportunity(
                allocator, ("obj-pt-1",),
                originating_patterns=("obj-pt-1", "obj-pt-unread"),
            )
        assert "rests on the Patterns it read" in str(exc.value)

    def test_derives_from_must_be_patterns(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.OPPORTUNITY,
            (("obj-pr-1", ObjectType.PROBLEM),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(OpportunityError) as exc:
            make_opportunity(allocator, ("obj-pr-1",), attributes=attributes)
        assert "derives from Patterns only" in str(exc.value)

    def test_ov1_passes_when_resolvable(self, allocator):
        result = ov1_originating_patterns_resolve(
            ctx(make_opportunity(allocator), resolve_type=lambda r: ObjectType.PATTERN)
        )
        assert result.outcome is RuleOutcome.PASS

    def test_ov1_detects_unresolvable(self, allocator):
        result = ov1_originating_patterns_resolve(
            ctx(make_opportunity(allocator), resolve_type=lambda r: None)
        )
        assert result.failed
        assert "do not resolve" in result.detail

    def test_ov1_detects_mistyped(self, allocator):
        result = ov1_originating_patterns_resolve(
            ctx(make_opportunity(allocator), resolve_type=lambda r: ObjectType.PROBLEM)
        )
        assert result.failed
        assert "not Patterns" in result.detail

    def test_ov1_detects_a_stripped_membership(self, allocator):
        o = make_opportunity(allocator)
        object.__setattr__(o, "originating_patterns", ())
        result = ov1_originating_patterns_resolve(ctx(o))
        assert result.failed
        assert "rests on nothing" in result.detail

    def test_ov1_skips_without_resolver(self, allocator):
        assert ov1_originating_patterns_resolve(
            ctx(make_opportunity(allocator))
        ).outcome is RuleOutcome.SKIP

    def test_multiple_patterns_supported(self, store, allocator):
        """The IOM permits several originating Patterns."""
        patterns = write_patterns(store, allocator, 2)
        stored = write_opportunity_from(store, allocator, patterns)
        assert len(store.get_opportunity(stored.object_id).originating_patterns) == 2


# ===========================================================================
# O-V2  solution-freedom
# ===========================================================================

class TestSolutionFreedom:
    def test_outcome_statement_passes(self, allocator):
        """The IOM's own example states the outcome sought and must pass."""
        result = ov2_no_solution_design(ctx(make_opportunity(allocator)))
        assert result.outcome is RuleOutcome.PASS

    @pytest.mark.parametrize("marker", DESIGN_MARKERS)
    def test_design_language_rejected(self, allocator, marker):
        o = make_opportunity(
            allocator,
            opportunity_statement=f"Deliver seller feedback {marker} quickly.",
        )
        result = ov2_no_solution_design(ctx(o))
        assert result.failed
        assert "forecloses Solution Intelligence" in result.detail

    @pytest.mark.parametrize(
        "innocent",
        ["the archipelago", "plugins-are-not-here", "dashboarding", "sdkx", "apiary"],
    )
    def test_matching_is_word_bounded(self, innocent):
        """A substring test would fire on innocent prose and get switched off."""
        assert detect_solution_design(innocent) == ()

    def test_absent_statement_fails_rather_than_passes(self, allocator):
        o = make_opportunity(allocator)
        object.__setattr__(o, "opportunity_statement", "   ")
        result = ov2_no_solution_design(ctx(o))
        assert result.failed
        assert "unstated opportunity" in result.detail

    def test_detection_is_case_insensitive(self):
        assert detect_solution_design("We Will Build a thing")

    def test_property_exposed(self, allocator):
        assert make_opportunity(allocator).is_solution_free
        assert not make_opportunity(
            allocator, opportunity_statement="We will build a dashboard."
        ).is_solution_free

    def test_store_rejects_design_contamination(self, store, allocator, patterns):
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(
                store, allocator, patterns,
                opportunity_statement="Solve this by implementing a plugin.",
            )
        assert "O-V2" in exc.value.failure.rule_ids


# ===========================================================================
# O-V4  scoring explanation
# ===========================================================================

class TestScoringExplanation:
    def test_passes_when_dimensions_named(self, allocator):
        result = ov4_scoring_explanation_references_dimensions(
            ctx(make_opportunity(allocator))
        )
        assert result.outcome is RuleOutcome.PASS
        assert "reach" in result.detail

    def test_missing_explanation_rejected(self, allocator):
        o = make_opportunity(allocator, scoring_explanation=None)
        result = ov4_scoring_explanation_references_dimensions(ctx(o))
        assert result.failed
        assert "breaches Principle 2" in result.detail

    def test_opaque_number_rejected(self, allocator):
        """A single number with no dimensions cannot be explained."""
        o = make_opportunity(
            allocator,
            score=Score(value=0.7, model_version="v1"),
            scoring_explanation="It scored well.",
        )
        result = ov4_scoring_explanation_references_dimensions(ctx(o))
        assert result.failed
        assert "single opaque number" in result.detail

    def test_explanation_naming_no_dimension_rejected(self, allocator):
        o = make_opportunity(
            allocator, scoring_explanation="The score reflects our judgement."
        )
        result = ov4_scoring_explanation_references_dimensions(ctx(o))
        assert result.failed
        assert "names none of the score dimensions" in result.detail

    def test_score_basis_accepted_as_dimensions(self, allocator):
        o = make_opportunity(
            allocator,
            score=Score(value=0.7, model_version="v1"),
            score_basis=(dimension("reach"),),
            scoring_explanation="reach dominates",
        )
        assert not ov4_scoring_explanation_references_dimensions(ctx(o)).failed

    def test_store_rejects_an_unexplained_score(self, store, allocator, patterns):
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(
                store, allocator, patterns, scoring_explanation=None
            )
        assert "O-V4" in exc.value.failure.rule_ids


# ===========================================================================
# O-V6  quantitative claims trace to Facts
# ===========================================================================

class TestQuantitativeClaims:
    def test_no_quantities_passes(self, allocator):
        result = ov6_quantitative_claims_trace(ctx(make_opportunity(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "no quantitative claim" in result.detail

    @pytest.mark.parametrize(
        "sizing",
        ["a $4.2m market", "40,000 sellers affected", "12% of the segment",
         "3 million users", "reaching 25000 accounts"],
    )
    def test_untraced_sizing_rejected(self, allocator, sizing):
        o = make_opportunity(allocator, market_sizing=sizing)
        result = ov6_quantitative_claims_trace(ctx(o))
        assert result.failed
        assert "breaches Principle 1" in result.detail

    def test_claim_requires_supporting_facts(self):
        with pytest.raises(QuantitativeClaimError) as exc:
            QuantitativeClaim(claim="40,000 sellers", fact_refs=())
        assert "Principle 1" in str(exc.value)

    def test_claim_requires_text(self):
        with pytest.raises(QuantitativeClaimError):
            QuantitativeClaim(claim="  ", fact_refs=("obj-fa-1",))

    def test_traced_claim_passes(self, allocator):
        o = make_opportunity(
            allocator,
            market_sizing="40,000 sellers affected",
            quantitative_claims=(
                QuantitativeClaim("40,000 sellers", ("obj-fa-1",)),
            ),
        )
        result = ov6_quantitative_claims_trace(
            ctx(o, lineage_facts=lambda oid: frozenset({"obj-fa-1"}))
        )
        assert result.outcome is RuleOutcome.PASS

    def test_claim_citing_a_fact_outside_lineage_rejected(self, allocator):
        """Naming an unrelated Fact is not a trace."""
        o = make_opportunity(
            allocator,
            market_sizing="40,000 sellers affected",
            quantitative_claims=(
                QuantitativeClaim("40,000 sellers", ("obj-fa-elsewhere",)),
            ),
        )
        result = ov6_quantitative_claims_trace(
            ctx(o, lineage_facts=lambda oid: frozenset({"obj-fa-1"}))
        )
        assert result.failed
        assert "outside this Opportunity's lineage" in result.detail

    def test_skips_without_a_lineage_provider(self, allocator):
        o = make_opportunity(
            allocator,
            market_sizing="40,000 sellers",
            quantitative_claims=(QuantitativeClaim("40,000", ("obj-fa-1",)),),
        )
        result = ov6_quantitative_claims_trace(ctx(o))
        assert result.outcome is RuleOutcome.SKIP
        assert "no lineage provider" in result.detail

    def test_skips_when_lineage_untraversable(self, allocator):
        o = make_opportunity(
            allocator,
            market_sizing="40,000 sellers",
            quantitative_claims=(QuantitativeClaim("40,000", ("obj-fa-1",)),),
        )
        result = ov6_quantitative_claims_trace(
            ctx(o, lineage_facts=lambda oid: None)
        )
        assert result.outcome is RuleOutcome.SKIP

    def test_quantity_detection(self):
        assert find_quantities("about 40,000 sellers")
        assert find_quantities("$3.2m opportunity")
        assert find_quantities("12% of segment")
        assert not find_quantities("many sellers across several domains")

    def test_small_ordinals_are_not_sizing(self):
        """'four domains' must not be read as a market-size claim."""
        assert not find_quantities("across four domains and 3 tools")

    def test_store_rejects_unfounded_sizing(self, store, allocator, patterns):
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(
                store, allocator, patterns, market_sizing="a $50m market"
            )
        assert "O-V6" in exc.value.failure.rule_ids

    def test_comma_grouped_figures_are_sizing_claims(self):
        """Regression: '40,000 sellers' read as no claim at all.

        The earlier pattern required four consecutive digits, so the most
        natural way to write a market size in prose slipped through O-V6
        entirely -- Principle 1 breached at the most visible point.
        """
        assert find_quantities("40,000 sellers affected") == ("40,000",)
        assert find_quantities("1,250,000 accounts") == ("1,250,000",)
        assert find_quantities("across four domains and 3 tools") == ()

    def test_ov6_is_live_at_acceptance(self, store, allocator, patterns):
        """Regression: O-V6 skipped on EVERY write.

        The object is not in the committed graph until after acceptance, so a
        provider bound to it returned None and the rule never acted at the
        only point it can. It now reads the probe graph. [N-6]
        """
        from oip.acceptance import AcceptancePath

        seen = []
        original = AcceptancePath.accept

        def spy(self, ctx):
            result = original(self, ctx)
            seen.extend(
                r for r in result.results if r.rule_id == "O-V6"
            )
            return result

        AcceptancePath.accept = spy
        try:
            write_opportunity_from(store, allocator, patterns)
        finally:
            AcceptancePath.accept = original

        assert seen and seen[0].outcome is not RuleOutcome.SKIP

    def test_store_accepts_a_traced_claim(self, store, allocator, patterns):
        fact_id = store.objects_of_type(ObjectType.FACT)[0].object_id
        stored = write_opportunity_from(
            store, allocator, patterns,
            market_sizing="40,000 sellers affected",
            quantitative_claims=(
                QuantitativeClaim("40,000 sellers", (fact_id,)),
            ),
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_store_rejects_a_claim_on_a_foreign_fact(self, store, allocator):
        """Adversarial: cite a real Fact that is NOT beneath this Opportunity."""
        patterns = write_patterns(store, allocator, 1)
        foreign = write_problems(store, allocator, 1)[0]
        foreign_fact = foreign.attributes.derives_from[0].object_id
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(
                store, allocator, patterns,
                market_sizing="40,000 sellers affected",
                quantitative_claims=(
                    QuantitativeClaim("40,000 sellers", (foreign_fact,)),
                ),
            )
        assert "O-V6" in exc.value.failure.rule_ids


# ===========================================================================
# O-V7  rejection rationale  [D-02]
# ===========================================================================

class TestRejectionRationale:
    def test_required_at_construction_when_rejected(self, allocator):
        with pytest.raises(RejectionRationaleError) as exc:
            make_opportunity(
                allocator,
                status=ObjectStatus.REJECTED,
                status_reason="below viability",
            )
        assert "learning signals" in str(exc.value)

    def test_accepted_with_rationale(self, allocator):
        o = make_opportunity(
            allocator,
            status=ObjectStatus.REJECTED,
            status_reason="below viability",
            rejection_rationale="Value hypothesis unsupported.",
        )
        assert not ov7_rejection_rationale_present(ctx(o)).failed

    def test_not_required_when_active(self, allocator):
        result = ov7_rejection_rationale_present(ctx(make_opportunity(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "not required" in result.detail

    def test_ov7_detects_stripped_rationale(self, allocator):
        o = make_opportunity(
            allocator,
            status=ObjectStatus.REJECTED,
            status_reason="below viability",
            rejection_rationale="unsupported",
        )
        object.__setattr__(o, "rejection_rationale", "  ")
        result = ov7_rejection_rationale_present(ctx(o))
        assert result.failed
        assert "destroys the learning signal" in result.detail

    def test_rejected_opportunities_are_retained(self, store, allocator, patterns):
        """D-02: retention is the point -- they are learning signal."""
        write_opportunity_from(
            store, allocator, patterns,
            status=ObjectStatus.REJECTED,
            status_reason="below viability",
            rejection_rationale="Scoring model judged reach insufficient.",
        )
        assert len(store.opportunities.rejected_opportunities()) == 1
        assert len(store.opportunities.active_opportunities()) == 0


# ===========================================================================
# Rule-set hygiene
# ===========================================================================

class TestRuleSetHygiene:
    def test_seven_rules_not_six(self, store):
        """The IOM defines O-V1..O-V7. O-V7 is not optional."""
        assert {f"O-V{i}" for i in range(1, 8)} <= set(store.acceptance.rule_ids)
        assert len(OPPORTUNITY_RULES) == 7

    def test_rule_ids_declared_in_order(self):
        assert [r.rule_id for r in OPPORTUNITY_RULES] == [
            f"O-V{i}" for i in range(1, 8)
        ]

    @pytest.mark.parametrize("rule", OPPORTUNITY_RULES)
    def test_every_rule_skips_non_opportunities(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert rule(AcceptanceContext(attributes=attributes)).outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", OPPORTUNITY_RULES)
    def test_every_rule_skips_without_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.OPPORTUNITY,
            (("obj-pt-1", ObjectType.PATTERN),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Opportunity payload" in result.detail

    def test_earlier_stages_unaffected(self, store, allocator):
        """Backward compatibility: one acceptance path serves all types."""
        stored = write_patterns(store, allocator, 1)[0]
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# Type, authority, attributes
# ===========================================================================

class TestTypeAndAuthority:
    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PATTERN,
            (("obj-pr-1", ObjectType.PROBLEM),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(OpportunityError):
            make_opportunity(allocator, ("obj-pr-1",), attributes=attributes)

    def test_only_opportunity_intelligence_may_create(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.OPPORTUNITY,
            (("obj-pt-1", ObjectType.PATTERN),),
            engine=Engine.PATTERN_INTELLIGENCE,
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(OpportunityError) as exc:
            make_opportunity(allocator, attributes=attributes)
        assert "V7" in str(exc.value)

    @pytest.mark.parametrize(
        "field_name", ["opportunity_statement", "value_hypothesis", "beneficiary_population"]
    )
    def test_required_prose_attributes(self, allocator, field_name):
        with pytest.raises(OpportunityError):
            make_opportunity(allocator, **{field_name: "  "})

    def test_score_must_be_a_score(self, allocator):
        with pytest.raises(ScoreError):
            make_opportunity(allocator, score=0.6)

    def test_optional_attributes_default_absent(self, allocator):
        o = make_opportunity(allocator)
        assert o.market_sizing is None
        assert o.timing_assessment is None
        assert o.competitive_context is None
        assert o.capture_hypothesis is None
        assert o.rejection_rationale is None
        assert o.quantitative_claims == ()

    def test_optional_attributes_carried(self, allocator):
        o = make_opportunity(
            allocator,
            timing_assessment="tooling consolidation underway",
            competitive_context="no incumbent addresses feedback",
            capture_hypothesis="retention through workflow lock-in",
        )
        assert o.timing_assessment

    def test_identity_delegated(self, allocator):
        o = make_opportunity(allocator)
        assert o.object_id == o.attributes.object_id
        assert o.lineage_id == o.attributes.lineage_id
        assert o.status is o.attributes.status
        assert o.independent_source_count == 3

    def test_frozen(self, allocator):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            make_opportunity(allocator).opportunity_statement = "x"


# ===========================================================================
# Score comparability and ranking  [O-I3]
# ===========================================================================

class TestScoreComparability:
    def test_same_version_comparable(self, allocator):
        a = make_opportunity(allocator)
        b = make_opportunity(allocator)
        assert a.comparable_with(b)

    def test_different_versions_not_comparable(self, allocator):
        a = make_opportunity(allocator, score=score(model_version="v1"),
                             scoring_explanation="reach")
        b = make_opportunity(allocator, score=score(model_version="v2"),
                             scoring_explanation="reach")
        assert not a.comparable_with(b)

    def test_unscored_never_comparable(self, allocator):
        a = make_opportunity(allocator, scored=False)
        assert not a.comparable_with(make_opportunity(allocator))

    def test_rank_orders_descending(self, allocator):
        low = make_opportunity(allocator, score=score(0.2), scoring_explanation="reach")
        high = make_opportunity(allocator, score=score(0.9), scoring_explanation="reach")
        assert rank([low, high])[0] is high

    def test_rank_refuses_across_versions(self, allocator):
        a = make_opportunity(allocator, score=score(0.2, "v1"), scoring_explanation="reach")
        b = make_opportunity(allocator, score=score(0.9, "v2"), scoring_explanation="reach")
        with pytest.raises(ScoreComparabilityError) as exc:
            rank([a, b])
        assert "comparable only within one model" in str(exc.value)

    def test_rank_ignores_unscored(self, allocator):
        scored = make_opportunity(allocator)
        assert len(rank([scored, make_opportunity(allocator, scored=False)])) == 1

    def test_registry_ranks_within_a_version(self, store, allocator):
        patterns = write_patterns(store, allocator, 1)
        for value in (0.2, 0.8):
            write_opportunity_from(
                store, allocator, patterns,
                score=score(value), scoring_explanation="reach dominates",
            )
        ranked = store.opportunities.rank_within("score-model-v1")
        assert [o.score.value for o in ranked] == [0.8, 0.2]

    def test_registry_cohort_by_version(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert len(store.opportunities.scored_under("score-model-v1")) == 1
        assert store.opportunities.scored_under("other") == ()


# ===========================================================================
# O-I1..O-I4  integrity
# ===========================================================================

class TestOpportunityIntegrity:
    def test_clean_store_holds(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert store.opportunities.integrity().verify() == ()

    def test_oi1_detects_inflation_against_current_pattern(
        self, store, allocator, patterns
    ):
        """Re-verified against CURRENT upstream, not values at acceptance."""
        stored = write_opportunity_from(store, allocator, patterns)
        o = store.get_opportunity(stored.object_id)
        object.__setattr__(
            o.attributes, "confidence",
            Confidence(evidential_support=0.99, assertion_confidence=0.99,
                       effective_confidence=0.99),
        )
        violations = store.opportunities.integrity().verify()
        assert any(v.constraint_id == "O-I1" for v in violations)
        assert "misallocated commitment" in "".join(v.detail for v in violations)

    def test_oi1_self_ceiling_is_unreachable_by_construction(self):
        """Confidence already forbids effective > own support at build time.

        O-I1's self-check is therefore defensive depth, not the live path;
        the upstream-ceiling half above is what does the work.
        """
        from oip.contract import ConfidenceCeilingError

        with pytest.raises(ConfidenceCeilingError):
            Confidence(evidential_support=0.1, assertion_confidence=0.9,
                       effective_confidence=0.5)

    def test_oi1_skips_a_missing_pattern(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        del store._objects[patterns[0].object_id]
        assert not [
            v for v in store.opportunities.integrity().verify()
            if v.constraint_id == "O-I1"
        ]

    def test_oi2_detects_design_introduced_later(self, store, allocator, patterns):
        """Solution-freedom must hold across all versions. [O-I2]"""
        stored = write_opportunity_from(store, allocator, patterns)
        o = store.get_opportunity(stored.object_id)
        object.__setattr__(
            o, "opportunity_statement", "We will build a dashboard for sellers."
        )
        violations = store.opportunities.integrity().verify()
        assert any(v.constraint_id == "O-I2" for v in violations)
        assert "across all versions" in "".join(v.detail for v in violations)

    def test_oi2_checks_superseded_versions(self, store, allocator, patterns):
        first = write_opportunity_from(store, allocator, patterns)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "restated")
        object.__setattr__(
            store.get_opportunity(first.object_id),
            "opportunity_statement", "Deliver this by implementing a plugin.",
        )
        successor = allocator.succeed(first.attributes.identity)
        write_opportunity_from(
            store, allocator, patterns,
            identity=successor, predecessor_id=first.object_id,
        )
        assert any(
            v.constraint_id == "O-I2"
            for v in store.opportunities.integrity().verify()
        )

    def test_oi3_detects_a_version_denoting_two_bases(
        self, store, allocator, patterns
    ):
        """One model version must denote one comparable basis. [O-I3]"""
        write_opportunity_from(
            store, allocator, patterns,
            score=score(dimension_names=("reach", "severity")),
            scoring_explanation="reach and severity",
        )
        write_opportunity_from(
            store, allocator, patterns,
            score=score(dimension_names=("reach", "novelty")),
            scoring_explanation="reach and novelty",
        )
        violations = store.opportunities.integrity().verify()
        assert any(v.constraint_id == "O-I3" for v in violations)
        assert "one comparable basis" in "".join(v.detail for v in violations)

    def test_oi3_accepts_a_consistent_basis(self, store, allocator, patterns):
        for _ in range(3):
            write_opportunity_from(store, allocator, patterns)
        assert not [
            v for v in store.opportunities.integrity().verify()
            if v.constraint_id == "O-I3"
        ]

    def test_oi3_permits_distinct_bases_across_versions(
        self, store, allocator, patterns
    ):
        """Different models legitimately score differently. [O-I3]"""
        write_opportunity_from(
            store, allocator, patterns,
            score=score(model_version="v1", dimension_names=("reach",)),
            scoring_explanation="reach",
        )
        write_opportunity_from(
            store, allocator, patterns,
            score=score(model_version="v2", dimension_names=("novelty",)),
            scoring_explanation="novelty",
        )
        assert not [
            v for v in store.opportunities.integrity().verify()
            if v.constraint_id == "O-I3"
        ]

    def test_oi4_detects_retrospective_alteration(self, store, allocator, patterns):
        """Rescoring creates a version; it never overwrites. [O-I4]"""
        stored = write_opportunity_from(store, allocator, patterns)
        o = store.get_opportunity(stored.object_id)
        object.__setattr__(o.score, "value", 0.99)
        violations = store.opportunities.integrity().verify()
        assert any(v.constraint_id == "O-I4" for v in violations)
        assert "does not overwrite" in "".join(v.detail for v in violations)

    def test_oi4_detects_an_altered_dimension(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        o = store.get_opportunity(stored.object_id)
        object.__setattr__(o.score.dimensions[0], "value", 0.01)
        assert any(
            v.constraint_id == "O-I4"
            for v in store.opportunities.integrity().verify()
        )

    def test_oi4_detects_a_withdrawn_score(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        o = store.get_opportunity(stored.object_id)
        object.__setattr__(o, "score", None)
        violations = store.opportunities.integrity().verify()
        assert any(
            v.constraint_id == "O-I4" and "cannot be withdrawn" in v.detail
            for v in violations
        )

    def test_oi4_accepts_an_unaltered_score(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert not [
            v for v in store.opportunities.integrity().verify()
            if v.constraint_id == "O-I4"
        ]

    def test_oi4_rescoring_as_a_new_version_is_clean(
        self, store, allocator, patterns
    ):
        """The sanctioned route: a new version, original preserved. [O-I4]"""
        first = write_opportunity_from(store, allocator, patterns)
        original = store.get_opportunity(first.object_id).score_fingerprint()
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "rescored")

        successor = allocator.succeed(first.attributes.identity)
        write_opportunity_from(
            store, allocator, patterns,
            identity=successor, predecessor_id=first.object_id,
            score=score(0.81), scoring_explanation="reach dominates",
        )
        assert store.get_opportunity(first.object_id).score_fingerprint() == original
        assert store.opportunities.integrity().verify() == ()

    def test_score_recording_counts(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert store.opportunities.integrity().recorded_score_count == 1

    def test_unscored_writes_record_nothing(self, store, allocator, patterns):
        write_opportunity_from(
            store, allocator, patterns,
            scored=False, status=ObjectStatus.REJECTED,
            status_reason="below viability", rejection_rationale="unsupported",
        )
        assert store.opportunities.integrity().recorded_score_count == 0

    def test_unregistered_opportunities_skipped(self, store, allocator):
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.opportunities.integrity().verify() == ()

    def test_verifier_constructible_standalone(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        verifier = OpportunityIntegrity(
            opportunity_of=store.opportunities.get, store=store
        )
        assert verifier.verify() == ()


# ===========================================================================
# Store integration
# ===========================================================================

class TestStoreIntegration:
    def test_payload_retrievable(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        assert store.get_opportunity(stored.object_id) is not None

    def test_unknown_payload_is_none(self, store):
        assert store.get_opportunity("obj-absent") is None

    def test_registry_counts_and_memoises(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert len(store.opportunities) == 1
        assert store.opportunities is store.opportunities

    def test_from_pattern_locates(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert len(store.opportunities.from_pattern(patterns[0].object_id)) == 1
        assert store.opportunities.from_pattern("obj-absent") == ()

    def test_rejected_write_leaves_no_payload(self, store, allocator, patterns):
        before = len(store.opportunities)
        with pytest.raises(WriteRejectedError):
            write_opportunity_from(store, allocator, patterns, scored=False)
        assert len(store.opportunities) == before

    def test_rejected_write_records_a_failure(self, store, allocator, patterns):
        with pytest.raises(WriteRejectedError):
            write_opportunity_from(store, allocator, patterns, scored=False)
        assert store.failure_records[-1].object_type is ObjectType.OPPORTUNITY

    def test_derivation_from_rejected_pattern_refused(self, store, allocator, patterns):
        """I8: rejected knowledge must never re-enter."""
        store.transition(patterns[0].object_id, ObjectStatus.REJECTED, "declined")
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(store, allocator, patterns)
        assert "I8" in exc.value.failure.rule_ids

    def test_supersession_accepted(self, store, allocator, patterns):
        first = write_opportunity_from(store, allocator, patterns)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "rescored")
        successor = allocator.succeed(first.attributes.identity)
        second = write_opportunity_from(
            store, allocator, patterns,
            identity=successor, predecessor_id=first.object_id,
        )
        assert second.attributes.version == 2
        assert second.lineage_id == first.lineage_id

    def test_lineage_facts_exposed(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        facts = store._lineage_facts(stored.object_id)
        assert len(facts) == 4
        assert store._lineage_facts("obj-absent") is None


# ===========================================================================
# Lineage, graph, cascade
# ===========================================================================

class TestPipelineIntegration:
    def test_reaches_evidence_at_depth_four(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.depth_to_evidence(stored.object_id) == 4

    def test_evidence_set_spans_the_pattern(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        assert len(store.graph.evidence_set(stored.object_id)) == 4

    def test_lineage_edges_indexed(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset(p.object_id for p in patterns)

    def test_graph_rebuildable(self, store, allocator, patterns):
        stored = write_opportunity_from(store, allocator, patterns)
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_retracting_evidence_invalidates_the_opportunity(
        self, store, allocator, patterns
    ):
        stored = write_opportunity_from(store, allocator, patterns)
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_invalidating_the_pattern_invalidates_the_opportunity(
        self, store, allocator, patterns
    ):
        """The IOM's own transition: ACTIVE -> INVALIDATED on Pattern loss."""
        stored = write_opportunity_from(store, allocator, patterns)
        store.transition(
            patterns[0].object_id, ObjectStatus.INVALIDATED, "artefact found"
        )
        CascadeInvalidation(store=store).cascade(
            patterns[0].object_id, ObjectStatus.INVALIDATED, "artefact found"
        )
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_universal_integrity_holds(self, store, allocator, patterns):
        write_opportunity_from(store, allocator, patterns)
        assert store.verify_integrity().holds

    def test_all_five_type_verifiers_hold(self, store, allocator, patterns):
        """Backward compatibility across every realised type."""
        write_opportunity_from(store, allocator, patterns)
        assert store.evidence.integrity().verify() == ()
        assert store.facts.integrity().verify() == ()
        assert store.problems.integrity().verify() == ()
        assert store.patterns.integrity().verify() == ()
        assert store.opportunities.integrity().verify() == ()

    def test_evidence_may_never_derive_from_an_opportunity(
        self, store, allocator, patterns
    ):
        """AD-05 holds at the platform's primary output too."""
        from oip.evidence import Evidence, EvidenceContent, ExternalOriginError
        from tests.test_evidence import provenance

        stored = write_opportunity_from(store, allocator, patterns)
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((stored.object_id, ObjectType.OPPORTUNITY),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes, provenance=provenance(),
                content=EvidenceContent.full("text"),
            )


# ===========================================================================
# Concurrency  [N-11, I5]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_writes_serialised(self, store, allocator):
        patterns = write_patterns(store, allocator, 1)
        refs = tuple(p.object_id for p in patterns)
        ceiling = patterns[0].attributes.confidence.effective_confidence
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            o = make_opportunity(allocator, refs, upstream_ceiling=ceiling)
            barrier.wait()
            try:
                written.append(store.write_opportunity(o).object_id)
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(written)) == 8
        assert store.verify_integrity().holds
        assert store.opportunities.integrity().verify() == ()

    def test_only_one_successor_wins_a_rescoring_race(
        self, store, allocator, patterns
    ):
        """Rescoring is the systemic driver of Opportunity versioning."""
        from oip.identity import BranchingError

        first = write_opportunity_from(store, allocator, patterns)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "rescored")

        winners: list[str] = []
        rejected: list[Exception] = []
        barrier = threading.Barrier(8)

        def succeed() -> None:
            barrier.wait()
            try:
                identity = allocator.succeed(first.attributes.identity)
            except BranchingError as exc:
                rejected.append(exc)
                return
            winners.append(
                write_opportunity_from(
                    store, allocator, patterns,
                    identity=identity, predecessor_id=first.object_id,
                ).object_id
            )

        threads = [threading.Thread(target=succeed) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(winners) == 1
        assert len(rejected) == 7


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(version=st.text(max_size=20))
def test_score_requires_a_non_blank_version(version):
    """AC1 over arbitrary version strings."""
    if version.strip():
        assert Score(value=0.5, model_version=version).model_version == version
    else:
        with pytest.raises(ScoreError):
            Score(value=0.5, model_version=version)


@settings(max_examples=200, deadline=None)
@given(marker=st.sampled_from(DESIGN_MARKERS), prefix=st.text(max_size=25))
def test_design_language_detected_wherever_it_appears(marker, prefix):
    """O-V2 over arbitrary surrounding text."""
    assert marker in detect_solution_design(f"{prefix} {marker} onwards")


@settings(max_examples=200, deadline=None)
@given(text=st.text(alphabet="abcdefgh ", max_size=60))
def test_neutral_alphabet_never_trips_ov2(text):
    """No false positive is possible from text containing no marker."""
    assert all(m in text.casefold() for m in detect_solution_design(text))


@settings(max_examples=200, deadline=None)
@given(
    values=st.lists(
        st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        min_size=1, max_size=8,
    )
)
def test_rank_is_monotonic_within_one_model(values):
    """O-I3: ranking within a version is a total order on score value."""
    allocator = IdentityAllocator()
    opportunities = [
        make_opportunity(allocator, score=score(v), scoring_explanation="reach")
        for v in values
    ]
    ranked = rank(opportunities)
    assert [o.score.value for o in ranked] == sorted(values, reverse=True)


@settings(max_examples=150, deadline=None)
@given(
    versions=st.lists(
        st.sampled_from(["m1", "m2"]), min_size=2, max_size=6
    )
)
def test_rank_refuses_exactly_when_versions_differ(versions):
    """O-I3 over arbitrary version mixes."""
    allocator = IdentityAllocator()
    opportunities = [
        make_opportunity(
            allocator, score=score(0.5, model_version=v),
            scoring_explanation="reach",
        )
        for v in versions
    ]
    if len(set(versions)) > 1:
        with pytest.raises(ScoreComparabilityError):
            rank(opportunities)
    else:
        assert len(rank(opportunities)) == len(versions)


@settings(max_examples=150, deadline=None)
@given(rationale=st.text(max_size=30))
def test_rejection_always_requires_a_rationale(rationale):
    """O-V7 over arbitrary rationale text. [D-02]"""
    allocator = IdentityAllocator()
    kwargs = dict(
        status=ObjectStatus.REJECTED,
        status_reason="below viability",
        rejection_rationale=rationale,
    )
    if rationale.strip():
        o = make_opportunity(allocator, **kwargs)
        assert not ov7_rejection_rationale_present(ctx(o)).failed
    else:
        with pytest.raises(RejectionRationaleError):
            make_opportunity(allocator, **kwargs)


@settings(max_examples=150, deadline=None)
@given(count=st.integers(min_value=1, max_value=10))
def test_any_originating_pattern_count_supported(count):
    """O-V1 over arbitrary fan-in."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-pt-{i}" for i in range(count))
    o = make_opportunity(allocator, refs)
    assert len(o.originating_patterns) == count
    assert not ov1_originating_patterns_resolve(
        ctx(o, resolve_type=lambda r: ObjectType.PATTERN)
    ).failed


# ===========================================================================
# Regression: the acceptance path must not promote a terminal status
# ===========================================================================

class TestTerminalStatusPreserved:
    """Regression for a defect in the SHARED acceptance path. [R-2, N-10, D-02]

    Writing a REJECTED object raised an uncaught ContractError, because the
    path promoted anything that was not already ACTIVE. Two ratified rules
    were breached at once: N-10 (failures produce records, never unexpected
    exceptions) and D-02 (REJECTED objects are retained as learning signal).
    """

    def test_rejected_opportunity_persists_as_rejected(
        self, store, allocator, patterns
    ):
        stored = write_opportunity_from(
            store, allocator, patterns,
            scored=False,
            status=ObjectStatus.REJECTED,
            status_reason="below viability",
            rejection_rationale="Value hypothesis unsupported by the pattern.",
        )
        assert stored.status is ObjectStatus.REJECTED
        assert store.get(stored.object_id).status is ObjectStatus.REJECTED

    def test_no_uncaught_exception_on_a_terminal_write(
        self, store, allocator, patterns
    ):
        """N-10: a terminal status is a legitimate outcome, not a crash."""
        from oip.contract import ContractError

        try:
            write_opportunity_from(
                store, allocator, patterns,
                scored=False,
                status=ObjectStatus.REJECTED,
                status_reason="below viability",
                rejection_rationale="declined",
            )
        except ContractError as exc:  # pragma: no cover - regression guard
            pytest.fail(f"terminal write raised {exc!r}")

    def test_proposed_still_promotes_to_active(self, store, allocator, patterns):
        """The R-2 transition must be unaffected by the fix."""
        stored = write_opportunity_from(
            store, allocator, patterns,
            status=ObjectStatus.PROPOSED, status_reason="awaiting acceptance",
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_unscored_still_cannot_reach_active(self, store, allocator, patterns):
        """The REJECTED carve-out must not leak an unscored ACTIVE. [M-14]"""
        with pytest.raises(WriteRejectedError) as exc:
            write_opportunity_from(
                store, allocator, patterns,
                scored=False,
                status=ObjectStatus.PROPOSED, status_reason="awaiting",
            )
        assert "O-V3" in exc.value.failure.rule_ids

    def test_ov3_skips_for_a_rejected_candidate(self, allocator):
        o = make_opportunity(
            allocator, scored=False,
            status=ObjectStatus.REJECTED, status_reason="declined",
            rejection_rationale="not viable",
        )
        result = ov3_score_with_model_version(ctx(o))
        assert result.outcome is RuleOutcome.SKIP
        assert "D-02" in result.detail

    def test_rejected_evidence_write_also_survives(self, store, allocator):
        """The fix is in the shared path, so every type benefits."""
        from oip.evidence import Evidence, EvidenceContent
        from tests.test_evidence import provenance

        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.REJECTED, status_reason="unusable capture",
        )
        stored = store.write_evidence(
            Evidence(
                attributes=attributes, provenance=provenance(),
                content=EvidenceContent.full("unusable"),
            )
        )
        assert stored.status is ObjectStatus.REJECTED
        assert store.verify_integrity().holds


# ===========================================================================
# Residual surface: helpers and defensive paths
# ===========================================================================

class TestResidualSurface:
    def test_claimed_facts_aggregates(self, allocator):
        o = make_opportunity(
            allocator,
            market_sizing="40,000 sellers and $2m",
            quantitative_claims=(
                QuantitativeClaim("40,000 sellers", ("obj-fa-1", "obj-fa-2")),
                QuantitativeClaim("$2m", ("obj-fa-2", "obj-fa-3")),
            ),
        )
        assert o.claimed_facts == frozenset({"obj-fa-1", "obj-fa-2", "obj-fa-3"})

    def test_claimed_facts_empty_without_claims(self, allocator):
        assert make_opportunity(allocator).claimed_facts == frozenset()

    def test_oi1_upstream_ceiling_is_the_live_check(self, store, allocator, patterns):
        """The half of O-I1 that does the work, isolated."""
        stored = write_opportunity_from(store, allocator, patterns)
        o = store.get_opportunity(stored.object_id)
        pattern_id = patterns[0].object_id
        ceiling = store.get(pattern_id).attributes.confidence.effective_confidence
        assert o.attributes.confidence.effective_confidence <= ceiling
        assert not [
            v for v in store.opportunities.integrity().verify()
            if v.constraint_id == "O-I1"
        ]

    def test_oi3_ignores_dimensionless_scores(self, store, allocator, patterns):
        """A score with no dimensions asserts no basis to disagree about."""
        write_opportunity_from(
            store, allocator, patterns,
            score=Score(value=0.5, model_version="bare-v1"),
            score_basis=(dimension("reach"),),
            scoring_explanation="reach dominates",
        )
        write_opportunity_from(
            store, allocator, patterns,
            score=Score(value=0.6, model_version="bare-v1"),
            score_basis=(dimension("reach"),),
            scoring_explanation="reach dominates",
        )
        assert not [
            v for v in store.opportunities.integrity().verify()
            if v.constraint_id == "O-I3"
        ]

    def test_score_fingerprint_absent_when_unscored(self, allocator):
        assert make_opportunity(allocator, scored=False).score_fingerprint() is None

    def test_recording_an_unscored_payload_is_a_noop(self, store, allocator):
        verifier = store.opportunities.integrity()
        verifier.record_score(make_opportunity(allocator, scored=False))
        assert verifier.recorded_score_count == 0

    def test_sized_text_covers_every_prose_field(self, allocator):
        o = make_opportunity(allocator, market_sizing="40,000 sellers")
        text = o.sized_text()
        assert "40,000" in text
        assert o.opportunity_statement in text
        assert o.value_hypothesis in text
