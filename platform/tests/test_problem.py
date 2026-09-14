"""Contract tests for the Problem object type.

Task: T01.7.3

Architecture References:
- P-V1..P-V6  Problem validation rules
- P-I1..P-I4  Problem integrity constraints
- S-4         Problem sufficiency: 2 independent sources
- S-2         Support bounded by contributing objects (P6)
- S-3         Undecidable text comparison is not guessed
- R-3         Confidence bounded by upstream
- R-6         SUPPORTS is a subset of DERIVES_FROM
- N-16        independent_source_count
- M-12/M-21/M-22  Scales, qualification criteria and identity remain OPEN

Acceptance criteria under test:
  AC1  inference_basis distinct from explanation
  AC2  P-V2 solution-independence check present
  AC3  affected_population required
"""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.contract import Confidence, Explanation, LineageRef
from oip.enums import Engine, ObjectStatus, ObjectType, RelationshipType
from oip.identity import IdentityAllocator
from oip.problem import (
    ABSENCE_MARKERS,
    GENERIC_POPULATIONS,
    PROBLEM_RULES,
    REMEDY_MARKERS,
    SOLUTION_MARKERS,
    FactContribution,
    InferenceBasis,
    InferenceBasisError,
    PopulationError,
    Problem,
    ProblemError,
    ProblemIntegrity,
    SEVERITY_BANDS,
    FREQUENCY_BANDS,
    WEIGHT_ATTESTATION_FLOOR,
    SolutionSmugglingError,
    SupportingFactError,
    WeightBand,
    WeightContribution,
    WeightCriterion,
    WeightError,
    WeightRating,
    band_of,
    band_rank,
    criterion_for,
    detect_solution_language,
    is_generic_population,
    pv1_supporting_facts_sufficient,
    pv2_solution_independent,
    pv3_population_specific,
    pv4_weight_present,
    pv5_inference_basis_references_facts,
    pv6_not_a_single_fact_restatement,
)
from oip.store import KnowledgeStore, WriteRejectedError
from oip.support import sufficiency_threshold
from tests.conftest import T0, build_attrs
from tests.test_evidence import evidence as make_evidence
from tests.test_fact import make_fact

STATEMENT = (
    "Sellers managing large inventories lose update work without notification "
    "when batch operations exceed platform limits, and discover the loss only "
    "later through customer complaints."
)
POPULATION = (
    "Segment A sellers maintaining inventories above approximately 50 active "
    "listings."
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def basis(*fact_refs: str, synthesis: str | None = None) -> InferenceBasis:
    return InferenceBasis(
        contributions=tuple(
            FactContribution(
                fact_ref=ref,
                contribution=f"{ref} establishes one component of the deficiency",
            )
            for ref in fact_refs
        ),
        synthesis=(
            synthesis
            or "Together these show an unmet need for reliable batch feedback, "
               "not merely an inconvenience."
        ),
    )


def weight(
    band: WeightBand,
    refs,
    detail: str = "evidenced by the cited Facts",
) -> WeightRating:
    """A WeightRating citing every ref under the band's own criterion.

    The default test rating: the declared criterion is attested whenever
    the cited Facts carry two independence keys, so default problems sit
    within the F-W1 evidence ceiling.
    """
    criterion = criterion_for(band)
    return WeightRating(
        band,
        f"{band.value} -- {detail}",
        tuple(
            WeightContribution(ref, criterion, f"{ref} evidences {criterion.value}")
            for ref in dict.fromkeys(refs)
        ),
    )


def make_problem(
    allocator: IdentityAllocator,
    fact_refs: tuple[str, ...] = ("obj-fa-1", "obj-fa-2"),
    *,
    supporting: tuple[str, ...] | None = None,
    source_count: int | None = None,
    upstream_ceiling: float | None = None,
    support: float = 0.62,
    assertion: float = 0.84,
    **overrides,
) -> Problem:
    identity = overrides.pop("identity", None) or allocator.new_object()
    supports = supporting if supporting is not None else fact_refs
    count = source_count if source_count is not None else len(supports)
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.PROBLEM,
        tuple((r, ObjectType.FACT) for r in fact_refs),
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        source_count=count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
    )
    # F-W1 defaults: each axis cites every supporting Fact under the
    # band's own criterion, so the default Problem sits within the
    # evidence ceiling whenever its Facts carry two independence keys.
    severity = overrides.pop(
        "severity", weight(WeightBand.SEVERE, supports, "unnoticed loss reaches customers")
    )
    frequency = overrides.pop(
        "frequency", weight(WeightBand.RECURRING, supports, "multiple periods")
    )
    kwargs = {
        "attributes": attributes,
        "problem_statement": overrides.pop("problem_statement", STATEMENT),
        "affected_population": overrides.pop("affected_population", POPULATION),
        "supporting_facts": overrides.pop("supporting_facts", supports),
        "severity": severity,
        "frequency": frequency,
        "problem_domain": overrides.pop(
            "problem_domain", "Marketplace inventory management"
        ),
        "inference_basis": overrides.pop("inference_basis", basis(*supports)),
    }
    kwargs.update(overrides)
    return Problem(**kwargs)


def ctx(problem: Problem, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": problem.attributes, "problem": problem}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def write_facts(store, allocator, n: int = 2, **fact_overrides):
    """Persist n Facts, each attesting a distinct Evidence object.

    Sources are keyed off the store's existing Evidence count so repeated
    calls never re-acquire the same material, which E-V6 forbids.
    """
    stored_facts = []
    offset = len(store.objects_of_type(ObjectType.EVIDENCE))
    for i in range(offset, offset + n):
        ev = store.write_evidence(
            make_evidence(
                allocator, content=f"source text {i}", source_identifier=f"src-{i}"
            )
        )
        stored_facts.append(
            store.write_fact(
                make_fact(
                    allocator,
                    (ev.object_id,),
                    upstream_ceiling=ev.attributes.confidence.effective_confidence,
                    **fact_overrides,
                )
            )
        )
    return stored_facts


def write_problem_from(
    store, allocator, stored_facts, predecessor_id: str | None = None, **overrides
):
    refs = tuple(f.object_id for f in stored_facts)
    ceiling = min(
        f.attributes.confidence.effective_confidence for f in stored_facts
    )
    return store.write_problem(
        make_problem(allocator, refs, upstream_ceiling=ceiling, **overrides),
        predecessor_id=predecessor_id,
    )


@pytest.fixture()
def facts(store, allocator):
    return write_facts(store, allocator, 2)


# ===========================================================================
# AC1 -- inference_basis distinct from explanation
# ===========================================================================

class TestInferenceBasisDistinctFromExplanation:
    def test_both_attributes_exist_independently(self, allocator):
        problem = make_problem(allocator)
        assert problem.inference_basis is not problem.attributes.explanation
        assert not isinstance(problem.inference_basis, Explanation)

    def test_inference_basis_is_required_even_with_a_full_explanation(
        self, allocator
    ):
        with pytest.raises(InferenceBasisError):
            make_problem(allocator, inference_basis=None)

    def test_explanation_satisfied_while_basis_fails(self, store, allocator, facts):
        """V6 can pass while P-V5 fails: they answer different questions."""
        refs = tuple(f.object_id for f in facts)
        problem = make_problem(
            allocator, refs,
            upstream_ceiling=min(
                f.attributes.confidence.effective_confidence for f in facts
            ),
        )
        object.__setattr__(problem.inference_basis, "synthesis", "  ")
        from oip.acceptance import v6_explanation_references_inputs

        assert not v6_explanation_references_inputs(ctx(problem)).failed
        assert pv5_inference_basis_references_facts(ctx(problem)).failed

    def test_basis_names_each_supporting_fact(self, allocator):
        problem = make_problem(allocator, ("obj-fa-1", "obj-fa-2", "obj-fa-3"))
        assert problem.inference_basis.referenced_facts == {
            "obj-fa-1", "obj-fa-2", "obj-fa-3"
        }
        assert all(problem.cites(r) for r in problem.supporting_facts)

    def test_basis_requires_a_synthesis_not_just_a_list(self, allocator):
        with pytest.raises(InferenceBasisError):
            basis("obj-fa-1", "obj-fa-2", synthesis="   ")

    def test_basis_requires_at_least_one_contribution(self):
        with pytest.raises(InferenceBasisError):
            InferenceBasis(contributions=(), synthesis="something")

    def test_contribution_requires_a_fact_ref(self):
        with pytest.raises(InferenceBasisError):
            FactContribution(fact_ref="  ", contribution="x")

    def test_contribution_requires_content(self):
        with pytest.raises(InferenceBasisError):
            FactContribution(fact_ref="obj-fa-1", contribution="")

    def test_a_fact_may_not_contribute_twice(self):
        with pytest.raises(InferenceBasisError):
            InferenceBasis(
                contributions=(
                    FactContribution("obj-fa-1", "a"),
                    FactContribution("obj-fa-1", "b"),
                ),
                synthesis="s",
            )

    def test_contribution_lookup(self, allocator):
        problem = make_problem(allocator)
        assert problem.inference_basis.contribution_of("obj-fa-1") is not None
        assert problem.inference_basis.contribution_of("obj-absent") is None

    def test_basis_may_not_cite_a_non_supporting_fact(self, allocator):
        with pytest.raises(InferenceBasisError):
            make_problem(
                allocator, ("obj-fa-1", "obj-fa-2"),
                inference_basis=basis("obj-fa-1", "obj-fa-9"),
            )

    def test_basis_may_cite_a_subset(self, allocator):
        """Every cited Fact must support; not every supporter must be cited."""
        problem = make_problem(
            allocator, ("obj-fa-1", "obj-fa-2", "obj-fa-3"),
            inference_basis=basis("obj-fa-1", "obj-fa-2"),
        )
        assert not problem.cites("obj-fa-3")


# ===========================================================================
# AC2 -- P-V2 solution-independence  [P-V2]
# ===========================================================================

class TestSolutionIndependence:
    def test_rule_registered(self, store):
        assert "P-V2" in store.acceptance.rule_ids

    def test_neutral_statement_passes(self, allocator):
        result = pv2_solution_independent(ctx(make_problem(allocator)))
        assert result.outcome is RuleOutcome.PASS

    def test_pass_detail_records_the_residual(self, allocator):
        """M-21: the check is lexical and must not imply completeness."""
        result = pv2_solution_independent(ctx(make_problem(allocator)))
        assert "M-21" in result.detail

    @pytest.mark.parametrize("marker", ABSENCE_MARKERS)
    def test_absence_framing_rejected(self, allocator, marker):
        problem = make_problem(
            allocator,
            problem_statement=f"Sellers experience {marker} batch confirmation.",
        )
        result = pv2_solution_independent(ctx(problem))
        assert result.failed
        assert "pre-determines" in result.detail

    @pytest.mark.parametrize("marker", REMEDY_MARKERS)
    def test_remedy_language_rejected(self, allocator, marker):
        problem = make_problem(
            allocator,
            problem_statement=f"Sellers {marker} batch confirmation screen.",
        )
        assert pv2_solution_independent(ctx(problem)).failed

    def test_detection_is_case_insensitive(self):
        assert detect_solution_language("There Is No Way To confirm updates")

    def test_detection_is_whitespace_insensitive(self):
        assert detect_solution_language("a\n\n  lack   of\tfeedback")

    def test_marker_families_are_disjoint(self):
        assert not set(ABSENCE_MARKERS) & set(REMEDY_MARKERS)
        assert set(SOLUTION_MARKERS) == set(ABSENCE_MARKERS) | set(REMEDY_MARKERS)

    def test_store_rejects_a_smuggled_solution(self, store, allocator, facts):
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(
                store, allocator, facts,
                problem_statement="Sellers suffer from a lack of batch feedback.",
            )
        assert "P-V2" in exc.value.failure.rule_ids

    def test_property_exposed_on_the_object(self, allocator):
        assert make_problem(allocator).is_solution_independent
        assert not make_problem(
            allocator, problem_statement="No mechanism exists for confirmation."
        ).is_solution_independent

    @pytest.mark.parametrize(
        "innocent",
        ["The blacklacks module", "a lacksadaisical approach", "needsantics",
         "unavailablest", "xlack ofy"],
    )
    def test_marker_matching_is_word_bounded(self, innocent):
        """Regression: a plain substring test read 'blacklacks' as 'lacks'.

        A rule that fires on innocent prose gets switched off by the engines
        it is meant to constrain, so a false positive costs more than it looks.
        """
        assert detect_solution_language(innocent) == ()

    def test_absent_statement_fails_rather_than_passes(self, allocator):
        """Regression: an emptied statement passed P-V2 vacuously."""
        problem = make_problem(allocator)
        object.__setattr__(problem, "problem_statement", "   ")
        result = pv2_solution_independent(ctx(problem))
        assert result.failed
        assert "unstated deficiency" in result.detail

    def test_markers_are_reported_not_merely_counted(self, allocator):
        problem = make_problem(
            allocator,
            problem_statement="There is no way to confirm; sellers need a report.",
        )
        assert len(problem.solution_markers) >= 2


# ===========================================================================
# AC3 -- affected_population required  [P-V3]
# ===========================================================================

class TestAffectedPopulation:
    def test_required_at_construction(self, allocator):
        with pytest.raises(PopulationError):
            make_problem(allocator, affected_population="")

    @pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
    def test_whitespace_is_not_a_population(self, allocator, blank):
        with pytest.raises(PopulationError):
            make_problem(allocator, affected_population=blank)

    def test_specific_population_passes(self, allocator):
        assert not pv3_population_specific(ctx(make_problem(allocator))).failed

    @pytest.mark.parametrize("generic", sorted(GENERIC_POPULATIONS))
    def test_generic_population_rejected(self, allocator, generic):
        problem = make_problem(allocator, affected_population=generic)
        result = pv3_population_specific(ctx(problem))
        assert result.failed
        assert "sizing becomes impossible" in result.detail

    def test_generic_detection_is_case_insensitive(self):
        assert is_generic_population("  EVERYONE ")
        assert not is_generic_population("Segment A sellers")

    def test_pv3_detects_a_stripped_population(self, allocator):
        problem = make_problem(allocator)
        object.__setattr__(problem, "affected_population", "   ")
        result = pv3_population_specific(ctx(problem))
        assert result.failed
        assert "absent" in result.detail

    def test_store_rejects_a_generic_population(self, store, allocator, facts):
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(store, allocator, facts, affected_population="everyone")
        assert "P-V3" in exc.value.failure.rule_ids

    def test_pass_detail_records_the_residual(self, allocator):
        assert "M-21" in pv3_population_specific(ctx(make_problem(allocator))).detail


# ===========================================================================
# P-V1  supporting facts and S-4 sufficiency
# ===========================================================================

class TestSupportingFacts:
    def test_at_least_one_required_at_construction(self, allocator):
        with pytest.raises(SupportingFactError):
            make_problem(allocator, ("obj-fa-1", "obj-fa-2"), supporting_facts=())

    def test_duplicate_support_rejected(self, allocator):
        with pytest.raises(SupportingFactError):
            make_problem(
                allocator, ("obj-fa-1",),
                supporting_facts=("obj-fa-1", "obj-fa-1"),
                inference_basis=basis("obj-fa-1"),
            )

    def test_support_must_be_a_subset_of_derives_from(self, allocator):
        """R-6: SUPPORTS is drawn from the Facts actually read."""
        with pytest.raises(SupportingFactError) as exc:
            make_problem(
                allocator, ("obj-fa-1",),
                supporting_facts=("obj-fa-1", "obj-fa-unread"),
                inference_basis=basis("obj-fa-1", "obj-fa-unread"),
            )
        assert "subset" in str(exc.value)

    def test_support_may_be_a_strict_subset(self, allocator):
        problem = make_problem(
            allocator, ("obj-fa-1", "obj-fa-2", "obj-fa-3"),
            supporting=("obj-fa-1", "obj-fa-2"),
        )
        assert problem.supporting_fact_count == 2
        assert len(problem.attributes.derives_from) == 3

    def test_derives_from_must_be_facts(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PROBLEM,
            (("obj-ev-1", ObjectType.EVIDENCE), ("obj-fa-2", ObjectType.FACT)),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=2,
        )
        with pytest.raises(ProblemError) as exc:
            make_problem(
                allocator, ("obj-ev-1", "obj-fa-2"), attributes=attributes,
            )
        assert "derives from Facts only" in str(exc.value)

    def test_s4_floor_enforced(self, allocator):
        """S-4: 2 independent sources; one source is that source's opinion."""
        problem = make_problem(allocator, source_count=1)
        result = pv1_supporting_facts_sufficient(ctx(problem))
        assert result.failed
        assert "source's opinion" in result.detail

    def test_s4_floor_met(self, allocator):
        result = pv1_supporting_facts_sufficient(ctx(make_problem(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert f"S-4 floor {sufficiency_threshold(ObjectType.PROBLEM)}" in result.detail

    def test_pv1_detects_stripped_support(self, allocator):
        problem = make_problem(allocator)
        object.__setattr__(problem, "supporting_facts", ())
        result = pv1_supporting_facts_sufficient(ctx(problem))
        assert result.failed
        assert "at least one supporting Fact" in result.detail

    def test_store_rejects_below_the_floor(self, store, allocator, facts):
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(store, allocator, facts, source_count=1)
        assert "P-V1" in exc.value.failure.rule_ids

    def test_sufficiency_property_matches_s4(self, allocator):
        assert make_problem(allocator, source_count=2).meets_sufficiency
        assert not make_problem(allocator, source_count=1).meets_sufficiency


# ===========================================================================
# P-V4  weight
# ===========================================================================

class TestWeight:
    def test_severity_required(self, allocator):
        with pytest.raises(WeightError):
            make_problem(allocator, severity="")

    def test_frequency_required(self, allocator):
        with pytest.raises(WeightError):
            make_problem(allocator, frequency="  ")

    def test_both_present_passes(self, allocator):
        result = pv4_weight_present(ctx(make_problem(allocator)))
        assert result.outcome is RuleOutcome.PASS

    def test_scale_is_the_ratified_f_w1_model(self, allocator):
        """The scale is F-W1's ratified band model, and P-V4 names it.

        Supersedes test_no_scale_is_asserted, which asserted no scale
        existed ("bands land at T04.1.4, not here"). The bands HAVE
        landed: F-W1 (T04.1.4) ratified the severity and frequency
        ordinal bands. The M-12 reference is preserved -- the marker
        stays partially closed because population scales remain open --
        and P-V4's PASS detail still cites it.
        """
        result = pv4_weight_present(ctx(make_problem(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "F-W1" in result.detail
        assert "M-12" in result.detail  # partially closed, still cited

    @pytest.mark.parametrize("field_name", ["severity", "frequency"])
    def test_pv4_detects_a_stripped_component(self, allocator, field_name):
        problem = make_problem(allocator)
        object.__setattr__(problem, field_name, "")
        result = pv4_weight_present(ctx(problem))
        assert result.failed
        assert field_name in result.detail

    def test_arbitrary_band_wording_is_rejected(self, allocator):
        """The bands are a closed set; free wording lives in the detail.

        Supersedes test_arbitrary_severity_text_is_accepted, which
        asserted arbitrary severity wording must be accepted because no
        taxonomy existed. F-W1 (T04.1.4) ratified a CLOSED band set:
        arbitrary band wording is now rejected at rating construction,
        while arbitrary explanatory wording is preserved -- in the
        rating's detail field, exactly where the free-text model carried
        it.
        """
        with pytest.raises(WeightError, match="not a ratified WeightBand"):
            WeightRating(
                "catastrophic-ish",  # type: ignore[arg-type]
                "catastrophic-ish -- wording the ratification never defined",
                (WeightContribution(
                    "obj-fa-1",
                    WeightCriterion.IRREVERSIBLE_HARM,
                    "the Fact evidences irreversible harm",
                ),),
            )
        # the free wording survives, in the detail, under a ratified band
        problem = make_problem(
            allocator,
            severity=weight(
                WeightBand.SEVERE, ("obj-fa-1", "obj-fa-2"),
                "catastrophic-ish, in the inferer's own words",
            ),
        )
        assert "catastrophic-ish" in problem.severity.detail


# ===========================================================================
# P-V5  inference basis references specific facts
# ===========================================================================

class TestInferenceBasisRule:
    def test_passes_with_named_facts(self, allocator):
        result = pv5_inference_basis_references_facts(ctx(make_problem(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "cited by name" in result.detail

    def test_detects_an_emptied_basis(self, allocator):
        problem = make_problem(allocator)
        object.__setattr__(problem.inference_basis, "contributions", ())
        result = pv5_inference_basis_references_facts(ctx(problem))
        assert result.failed
        assert "references no Fact" in result.detail

    def test_detects_a_stripped_synthesis(self, allocator):
        problem = make_problem(allocator)
        object.__setattr__(problem.inference_basis, "synthesis", "")
        result = pv5_inference_basis_references_facts(ctx(problem))
        assert result.failed
        assert "not an argument" in result.detail

    def test_detects_a_phantom_citation(self, allocator):
        problem = make_problem(allocator)
        object.__setattr__(problem, "supporting_facts", ("obj-fa-1",))
        result = pv5_inference_basis_references_facts(ctx(problem))
        assert result.failed
        assert "obj-fa-2" in result.detail


# ===========================================================================
# P-V6  not a restatement of a single Fact
# ===========================================================================

class TestSingleFactRestatement:
    def test_single_fact_rejected(self, allocator):
        problem = make_problem(
            allocator, ("obj-fa-1",), inference_basis=basis("obj-fa-1"),
            source_count=2,
        )
        result = pv6_not_a_single_fact_restatement(ctx(problem))
        assert result.failed
        assert "inflate its weight" in result.detail

    def test_plural_support_passes(self, allocator):
        result = pv6_not_a_single_fact_restatement(ctx(make_problem(allocator)))
        assert result.outcome is RuleOutcome.PASS

    def test_unchecked_when_claim_text_unavailable(self, allocator):
        result = pv6_not_a_single_fact_restatement(ctx(make_problem(allocator)))
        assert "unchecked" in result.detail

    def test_verbatim_restatement_rejected(self, store, allocator, facts):
        claim_text = store.get_fact(facts[0].object_id).claim.as_text()
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(
                store, allocator, facts, problem_statement=claim_text
            )
        assert "P-V6" in exc.value.failure.rule_ids

    def test_restatement_detection_ignores_case_and_spacing(
        self, store, allocator, facts
    ):
        claim_text = store.get_fact(facts[0].object_id).claim.as_text()
        noisy = f"  {claim_text.upper()}  "
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(store, allocator, facts, problem_statement=noisy)
        assert "P-V6" in exc.value.failure.rule_ids

    @pytest.mark.parametrize(
        "mutate",
        [
            lambda t: t + ".",
            lambda t: f"  {t} !!",
            lambda t: t.replace(" ", "   "),
            lambda t: t.upper() + "?",
        ],
    )
    def test_punctuation_variants_are_still_restatements(
        self, store, allocator, facts, mutate
    ):
        """Regression: a trailing full stop slipped a restatement past P-V6."""
        claim_text = store.get_fact(facts[0].object_id).claim.as_text()
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(
                store, allocator, facts, problem_statement=mutate(claim_text)
            )
        assert "P-V6" in exc.value.failure.rule_ids

    def test_a_genuinely_different_statement_is_not_a_restatement(
        self, store, allocator, facts
    ):
        claim_text = store.get_fact(facts[0].object_id).claim.as_text()
        stored = write_problem_from(
            store, allocator, facts,
            problem_statement=f"{claim_text} and sellers absorb the rework cost.",
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_unresolvable_claims_are_skipped_not_guessed(self, allocator):
        """S-3: what cannot be compared is not asserted to differ or match."""
        problem = make_problem(allocator)
        result = pv6_not_a_single_fact_restatement(
            ctx(problem, fact_claim_text=lambda ref: None)
        )
        assert result.outcome is RuleOutcome.PASS
        assert "differs from every resolvable claim" in result.detail

    def test_genuine_inference_accepted(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        assert stored.status is ObjectStatus.ACTIVE

    def test_property_exposed_on_the_object(self, allocator):
        assert make_problem(
            allocator, ("obj-fa-1",), inference_basis=basis("obj-fa-1")
        ).rests_on_a_single_fact
        assert not make_problem(allocator).rests_on_a_single_fact


# ===========================================================================
# Rule-set hygiene: one acceptance path serves all nine types
# ===========================================================================

class TestRuleSetHygiene:
    def test_all_six_rules_registered(self, store):
        assert {f"P-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)

    def test_rule_ids_are_declared_on_the_functions(self):
        assert [r.rule_id for r in PROBLEM_RULES] == [
            f"P-V{i}" for i in range(1, 7)
        ]

    @pytest.mark.parametrize("rule", PROBLEM_RULES)
    def test_every_rule_skips_non_problems(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", PROBLEM_RULES)
    def test_every_rule_skips_without_a_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PROBLEM,
            (("obj-fa-1", ObjectType.FACT),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=2,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Problem payload" in result.detail

    def test_evidence_and_fact_writes_are_unaffected(self, store, allocator):
        stored = write_facts(store, allocator, 1)[0]
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# Type and authority
# ===========================================================================

class TestTypeAndAuthority:
    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ProblemError):
            make_problem(allocator, ("obj-ev-1",), attributes=attributes)

    def test_only_problem_intelligence_may_create(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PROBLEM,
            (("obj-fa-1", ObjectType.FACT), ("obj-fa-2", ObjectType.FACT)),
            engine=Engine.FACT_EXTRACTION,
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=2,
        )
        with pytest.raises(ProblemError) as exc:
            make_problem(allocator, attributes=attributes)
        assert "V7" in str(exc.value)

    def test_statement_required(self, allocator):
        with pytest.raises(ProblemError):
            make_problem(allocator, problem_statement="  ")

    def test_domain_required(self, allocator):
        with pytest.raises(ProblemError):
            make_problem(allocator, problem_domain="")

    def test_optional_attributes_default_to_absent(self, allocator):
        problem = make_problem(allocator)
        assert problem.population_size_estimate is None
        assert problem.existing_workarounds is None
        assert problem.problem_persistence is None
        assert problem.cost_indication is None

    def test_optional_attributes_carried(self, allocator):
        problem = make_problem(
            allocator,
            population_size_estimate=1200,
            existing_workarounds="manual re-checking of listings",
            problem_persistence="enduring across releases",
            cost_indication="hours of rework per incident",
        )
        assert problem.population_size_estimate == 1200

    def test_negative_population_estimate_rejected(self, allocator):
        with pytest.raises(PopulationError):
            make_problem(allocator, population_size_estimate=-1)

    def test_identity_is_delegated(self, allocator):
        problem = make_problem(allocator)
        assert problem.object_id == problem.attributes.object_id
        assert problem.lineage_id == problem.attributes.lineage_id
        assert problem.status is problem.attributes.status
        assert problem.independent_source_count == 2


# ===========================================================================
# P-I1..P-I4  integrity
# ===========================================================================

class TestProblemIntegrity:
    def test_clean_store_holds(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        assert store.problems.integrity().verify() == ()

    def test_pi1_detects_a_reformulation_that_smuggles_a_solution(
        self, store, allocator, facts
    ):
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(
            problem, "problem_statement",
            "Sellers face a lack of batch confirmation.",
        )
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I1" for v in violations)
        assert "across all versions" in "".join(v.detail for v in violations)

    def test_pi1_checks_superseded_versions_too(self, store, allocator, facts):
        """A later clean version must not mask an earlier smuggled one."""
        first = write_problem_from(store, allocator, facts)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "reformulated")
        object.__setattr__(
            store.get_problem(first.object_id), "problem_statement",
            "There is no way to confirm batch updates.",
        )
        successor = allocator.succeed(first.attributes.identity)
        write_problem_from(
            store, allocator, facts, identity=successor,
            predecessor_id=first.object_id,
        )
        assert any(
            v.constraint_id == "P-I1"
            for v in store.problems.integrity().verify()
        )

    def test_pi2_detects_a_missing_fact(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        del store._objects[facts[0].object_id]
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I2" for v in violations)
        assert "no verifiable support" in "".join(v.detail for v in violations)

    def test_pi2_detects_a_non_fact_reference(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        evidence_id = store.objects_of_type(ObjectType.EVIDENCE)[0].object_id
        object.__setattr__(problem, "supporting_facts", (evidence_id,))
        violations = store.problems.integrity().verify()
        assert any("not a Fact" in v.detail for v in violations)

    def test_pi2_detects_a_non_active_fact(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        store._objects[facts[0].object_id] = store._objects[
            facts[0].object_id
        ].__class__(
            attributes=facts[0].attributes.with_status(
                ObjectStatus.ARCHIVED, "retention"
            ),
            lineage=facts[0].lineage,
        )
        violations = store.problems.integrity().verify()
        assert any(
            v.constraint_id == "P-I2" and "ARCHIVED" in v.detail
            for v in violations
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_pi2_does_not_fault_a_withdrawn_problem(self, store, allocator, facts):
        """A cascaded Problem is not required to hold live support."""
        stored = write_problem_from(store, allocator, facts)
        cascade = CascadeInvalidation(store=store)
        for fact in facts:
            cascade.retract(fact.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I2"
        ]

    def test_pi3_detects_unsupported_widening(self, store, allocator, facts):
        first = write_problem_from(store, allocator, facts)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "broadened")
        successor = allocator.succeed(first.attributes.identity)
        write_problem_from(
            store, allocator, facts,
            identity=successor,
            predecessor_id=first.object_id,
            affected_population="Segment A sellers.",
        )
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I3" for v in violations)
        assert "without additional supporting Facts" in "".join(
            v.detail for v in violations
        )

    def test_pi3_permits_widening_backed_by_new_facts(self, store, allocator):
        facts = write_facts(store, allocator, 2)
        first = write_problem_from(store, allocator, facts)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "broadened")

        extra = write_facts(store, allocator, 1)
        widened_facts = facts + extra
        successor = allocator.succeed(first.attributes.identity)
        write_problem_from(
            store, allocator, widened_facts,
            identity=successor,
            predecessor_id=first.object_id,
            affected_population="Segment A sellers.",
            source_count=3,
        )
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I3"
        ]

    def test_pi3_detects_a_raised_size_estimate(self, store, allocator, facts):
        first = write_problem_from(
            store, allocator, facts, population_size_estimate=100
        )
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "resized")
        successor = allocator.succeed(first.attributes.identity)
        write_problem_from(
            store, allocator, facts,
            identity=successor, predecessor_id=first.object_id,
            population_size_estimate=100_000,
        )
        assert any(
            v.constraint_id == "P-I3"
            for v in store.problems.integrity().verify()
        )

    def test_pi3_ignores_an_undecidable_rewording(self, store, allocator, facts):
        """S-3: an unreliable widening signal is worse than none."""
        first = write_problem_from(store, allocator, facts)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "reworded")
        successor = allocator.succeed(first.attributes.identity)
        write_problem_from(
            store, allocator, facts,
            identity=successor,
            predecessor_id=first.object_id,
            affected_population="Segment B merchants running bulk imports nightly.",
        )
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I3"
        ]

    def test_pi4_detects_inflated_source_count(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(problem.attributes, "independent_source_count", 9)
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I4" for v in violations)
        assert "exceeds what the Facts support" in "".join(
            v.detail for v in violations
        )

    def test_pi4_detects_inflated_support(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(
            problem.attributes, "confidence",
            Confidence(
                evidential_support=0.99,
                assertion_confidence=0.99,
                effective_confidence=0.5,
            ),
        )
        violations = store.problems.integrity().verify()
        assert any("S-2 P6" in v.detail for v in violations)

    def test_pi4_detects_shared_grounding(self, store, allocator):
        """Two Facts on one Evidence cannot supply two independent sources.

        Regression: the sum-of-Fact-counts bound alone passed this, letting a
        Problem clear the S-4 floor from a single source. [N-16, S-4]
        """
        ev = store.write_evidence(
            make_evidence(allocator, content="one source", source_identifier="s-one")
        )
        ceiling = ev.attributes.confidence.effective_confidence
        twins = [
            store.write_fact(
                make_fact(allocator, (ev.object_id,), upstream_ceiling=ceiling)
            )
            for _ in range(2)
        ]
        write_problem_from(store, allocator, twins)
        violations = store.problems.integrity().verify()
        assert any(
            v.constraint_id == "P-I4" and "share grounding" in v.detail
            for v in violations
        )

    def test_pi4_accepts_distinct_grounding(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
        ]

    def test_pi4_grounding_bound_needs_a_populated_graph(self, store, allocator, facts):
        """An unindexed Fact yields no verdict rather than a false one. [N-6]"""
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(
            problem, "supporting_facts", problem.supporting_facts
        )
        verifier = store.problems.integrity()
        assert verifier._distinct_evidence_beneath(problem) == 2
        object.__setattr__(problem, "supporting_facts", ("obj-unindexed",))
        assert verifier._distinct_evidence_beneath(problem) is None

    def test_pi4_grounding_bound_skipped_without_a_graph(self, store, allocator, facts):
        """No graph, no verdict. The index is derived, never authoritative. [N-6]"""
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)

        class GraphlessStore:
            graph = None

        verifier = ProblemIntegrity(
            problem_of=store.problems.get, store=GraphlessStore()
        )
        assert verifier._distinct_evidence_beneath(problem) is None

    def test_pi4_grounding_bound_skipped_on_partial_resolution(
        self, store, allocator, facts
    ):
        """P-I2 owns unresolvable support; P-I4 must not guess around it."""
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        del store._objects[facts[0].object_id]
        object.__setattr__(problem.attributes, "independent_source_count", 1)

        violations = store.problems.integrity().verify()
        assert not [
            v for v in violations
            if v.constraint_id == "P-I4" and "share grounding" in v.detail
        ]
        assert any(v.constraint_id == "P-I2" for v in violations)

    def test_pi2_flags_a_superseded_supporting_fact(self, store, allocator, facts):
        """SUPERSEDED does not cascade (D-01a), so P-I2 is what surfaces it.

        The Problem stays ACTIVE and the universal constraints stay silent --
        exactly the case M-65 leaves open. P-I2 reports it rather than letting
        an ACTIVE Problem rest on stale support unnoticed.
        """
        stored = write_problem_from(store, allocator, facts)
        store.transition(facts[0].object_id, ObjectStatus.SUPERSEDED, "re-extracted")

        assert store.get(stored.object_id).status is ObjectStatus.ACTIVE
        assert store.verify_integrity().holds
        assert any(
            v.constraint_id == "P-I2" and "SUPERSEDED" in v.detail
            for v in store.problems.integrity().verify()
        )

    def test_pi4_enforces_the_evidence_ceiling_not_a_ranking(
        self, store, allocator, facts
    ):
        """F-W1 R4 Example 1, both halves.

        Supersedes test_pi4_does_not_rank_severity, which asserted no
        ordering could exist because no scale existed (M-12). F-W1
        (T04.1.4) ratified the ordinal bands, and P-I4 now enforces the
        ratified D-B evidence ceiling: a criterion is defensible iff its
        entries cite Facts spanning >= 2 independence keys. What P-I4
        still never does is rank or derive: the asserted band is the
        inferer's (N-4), and a rating AT or BELOW the ceiling is never
        flagged, no matter how many keys are available.
        """
        refs = tuple(f.object_id for f in facts)
        # (a) SEVERE citing both Facts: 2 independence keys, defensible,
        # no violation -- the heaviest band passes with exactly the
        # floor.
        stored = write_problem_from(
            store, allocator, facts,
            severity=weight(WeightBand.SEVERE, refs),
        )
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
        ]
        assert (
            store.get_problem(stored.object_id).severity.band
            is WeightBand.SEVERE
        )
        # (b) SEVERE citing one Fact: 1 key, uncorroborated -- P-I4
        # flags the rating the evidence ceiling does not carry.
        single = write_problem_from(
            store, allocator, facts,
            severity=weight(WeightBand.SEVERE, refs[:1]),
        )
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == single.object_id
            and "1 independence key" in v.detail
        ]

    def test_pi4_silent_when_no_fact_resolves(self, store, allocator, facts):
        """P-I2 owns broken references; P-I4 must not double-report them."""
        write_problem_from(store, allocator, facts)
        for stored_fact in facts:
            del store._objects[stored_fact.object_id]
        violations = store.problems.integrity().verify()
        assert {v.constraint_id for v in violations} == {"P-I2"}

    def test_verifier_is_constructible_standalone(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        verifier = ProblemIntegrity(problem_of=store.problems.get, store=store)
        assert verifier.verify() == ()

    def test_unregistered_problems_are_skipped(self, store, allocator):
        """Objects written through the universal path carry no payload."""
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.problems.integrity().verify() == ()


# ===========================================================================
# Store integration
# ===========================================================================

class TestStoreIntegration:
    def test_payload_retrievable(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        assert store.get_problem(stored.object_id) is not None

    def test_unknown_payload_is_none(self, store):
        assert store.get_problem("obj-absent") is None

    def test_registry_counts(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        assert len(store.problems) == 1

    def test_registry_is_memoised(self, store):
        assert store.problems is store.problems

    def test_active_problems_exclude_withdrawn(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        assert len(store.problems.active_problems()) == 1
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.problems.active_problems() == ()

    def test_supported_by_locates_dependents(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        assert len(store.problems.supported_by(facts[0].object_id)) == 1
        assert store.problems.supported_by("obj-absent") == ()

    def test_rejected_write_leaves_no_payload(self, store, allocator, facts):
        before = len(store.problems)
        with pytest.raises(WriteRejectedError):
            write_problem_from(store, allocator, facts, affected_population="users")
        assert len(store.problems) == before

    def test_rejected_write_records_a_failure(self, store, allocator, facts):
        with pytest.raises(WriteRejectedError):
            write_problem_from(store, allocator, facts, affected_population="users")
        assert store.failure_records[-1].object_type is ObjectType.PROBLEM

    def test_unresolvable_fact_rejected(self, store, allocator):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_problem(
                make_problem(allocator, ("obj-never-written", "obj-also-not"))
            )
        assert "V3" in exc.value.failure.rule_ids

    def test_derivation_from_a_rejected_fact_refused(self, store, allocator):
        """I8: rejected knowledge must never re-enter."""
        facts = write_facts(store, allocator, 2)
        store.transition(facts[0].object_id, ObjectStatus.REJECTED, "declined")
        with pytest.raises(WriteRejectedError) as exc:
            write_problem_from(store, allocator, facts)
        assert "I8" in exc.value.failure.rule_ids

    def test_supersession_accepted(self, store, allocator, facts):
        first = write_problem_from(store, allocator, facts)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "reformulated")
        successor = allocator.succeed(first.attributes.identity)
        second = write_problem_from(
            store, allocator, facts, identity=successor,
            predecessor_id=first.object_id,
        )
        assert second.attributes.version == 2
        assert second.lineage_id == first.lineage_id


# ===========================================================================
# Lineage, graph, cascade, confidence
# ===========================================================================

class TestPipelineIntegration:
    def test_problem_reaches_evidence(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        assert store.graph.reaches_evidence(stored.object_id)
        assert len(store.graph.evidence_set(stored.object_id)) == 2

    def test_depth_to_evidence_is_two_edges(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        assert store.graph.depth_to_evidence(stored.object_id) == 2

    def test_lineage_edges_indexed_as_derives_from(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset(f.object_id for f in facts)

    def test_graph_is_rebuildable_from_objects(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_confidence_bounded_by_weakest_fact(self, store, allocator):
        weak_ev = store.write_evidence(
            make_evidence(
                allocator, content="weak", source_identifier="src-weak",
                attrs={"support": 0.25, "assertion": 0.99},
            )
        )
        weak_fact = store.write_fact(
            make_fact(
                allocator, (weak_ev.object_id,),
                upstream_ceiling=weak_ev.attributes.confidence.effective_confidence,
            )
        )
        strong = write_facts(store, allocator, 1)[0]
        stored = write_problem_from(store, allocator, [weak_fact, strong])
        assert stored.attributes.confidence.effective_confidence <= 0.25

    def test_confidence_inflation_rejected(self, store, allocator, facts):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_problem(
                make_problem(
                    allocator,
                    tuple(f.object_id for f in facts),
                    support=0.99, assertion=0.99,
                )
            )
        assert "V5" in exc.value.failure.rule_ids

    def test_retracting_evidence_invalidates_the_problem(
        self, store, allocator, facts
    ):
        stored = write_problem_from(store, allocator, facts)
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_invalidating_a_fact_invalidates_the_problem(
        self, store, allocator, facts
    ):
        stored = write_problem_from(store, allocator, facts)
        cascade = CascadeInvalidation(store=store)
        for fact in facts:
            store.transition(
                fact.object_id, ObjectStatus.INVALIDATED, "support withdrawn"
            )
            cascade.cascade(
                fact.object_id, ObjectStatus.INVALIDATED, "support withdrawn"
            )
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_universal_integrity_still_holds(self, store, allocator, facts):
        write_problem_from(store, allocator, facts)
        assert store.verify_integrity().holds

    def test_problem_may_not_derive_from_itself(self, allocator):
        identity = allocator.new_object()
        attributes = build_attrs(
            identity, ObjectType.PROBLEM,
            ((identity.object_id, ObjectType.FACT), ("obj-fa-2", ObjectType.FACT)),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=2,
        )
        from oip.acceptance import v10_no_cycle

        assert v10_no_cycle(AcceptanceContext(attributes=attributes)).failed

    def test_evidence_may_never_derive_from_a_problem(self, store, allocator, facts):
        """AD-05: ground truth protection holds at the Problem stage too."""
        from oip.evidence import ExternalOriginError

        stored = write_problem_from(store, allocator, facts)
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((stored.object_id, ObjectType.PROBLEM),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        from oip.evidence import Evidence, EvidenceContent
        from tests.test_evidence import provenance

        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes,
                provenance=provenance(),
                content=EvidenceContent.full("text"),
            )


# ===========================================================================
# Concurrency  [N-11, I5]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_problem_writes_are_serialised(self, store, allocator):
        facts = write_facts(store, allocator, 2)
        refs = tuple(f.object_id for f in facts)
        ceiling = min(
            f.attributes.confidence.effective_confidence for f in facts
        )
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            problem = make_problem(allocator, refs, upstream_ceiling=ceiling)
            barrier.wait()
            try:
                written.append(store.write_problem(problem).object_id)
            except Exception as exc:  # pragma: no cover - failure diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(written)) == 8
        assert len(store.problems) == 8
        assert store.verify_integrity().holds

    def test_only_one_successor_wins_a_supersession_race(
        self, store, allocator, facts
    ):
        from oip.identity import BranchingError

        first = write_problem_from(store, allocator, facts)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "reformulated")

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
                write_problem_from(
                    store, allocator, facts, identity=identity,
                    predecessor_id=first.object_id,
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
@given(count=st.integers(min_value=2, max_value=25))
def test_any_supporting_fact_count_accepted(count):
    """P-V1/P-V6 over arbitrary support breadth."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-fa-{i}" for i in range(count))
    problem = make_problem(allocator, refs)
    assert problem.supporting_fact_count == count
    assert not pv1_supporting_facts_sufficient(ctx(problem)).failed
    assert not pv6_not_a_single_fact_restatement(ctx(problem)).failed


@settings(max_examples=200, deadline=None)
@given(declared=st.integers(min_value=0, max_value=10))
def test_s4_floor_is_the_only_gate_on_source_count(declared):
    """P-V1 fails below the S-4 floor and passes at or above it."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-fa-{i}" for i in range(3))
    problem = make_problem(allocator, refs, source_count=declared)
    result = pv1_supporting_facts_sufficient(ctx(problem))
    assert result.failed == (declared < sufficiency_threshold(ObjectType.PROBLEM))


@settings(max_examples=300, deadline=None)
@given(marker=st.sampled_from(SOLUTION_MARKERS), prefix=st.text(max_size=30))
def test_solution_language_detected_wherever_it_appears(marker, prefix):
    """P-V2 over arbitrary surrounding text."""
    assert marker in detect_solution_language(f"{prefix} {marker} something")


@settings(max_examples=200, deadline=None)
@given(text=st.text(alphabet="abcdefghij ", max_size=60))
def test_neutral_alphabet_never_trips_p_v2(text):
    """No false positive is possible from text containing no marker."""
    detected = detect_solution_language(text)
    assert all(marker in text.casefold() for marker in detected)


@settings(max_examples=200, deadline=None)
@given(population=st.text(max_size=40))
def test_population_is_required_however_written(population):
    """AC3 over arbitrary population text."""
    allocator = IdentityAllocator()
    if not population.strip():
        with pytest.raises(PopulationError):
            make_problem(allocator, affected_population=population)
        return
    problem = make_problem(allocator, affected_population=population)
    expected_fail = is_generic_population(population)
    assert pv3_population_specific(ctx(problem)).failed == expected_fail


@settings(max_examples=150, deadline=None)
@given(
    cited=st.integers(min_value=1, max_value=6),
    supporting=st.integers(min_value=1, max_value=6),
)
def test_basis_may_never_cite_beyond_its_support(cited, supporting):
    """P-V5 over arbitrary citation/support combinations."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-fa-{i}" for i in range(supporting))
    cited_refs = tuple(f"obj-fa-{i}" for i in range(cited))
    if cited <= supporting:
        problem = make_problem(
            allocator, refs, inference_basis=basis(*cited_refs)
        )
        assert not pv5_inference_basis_references_facts(ctx(problem)).failed
    else:
        with pytest.raises(InferenceBasisError):
            make_problem(allocator, refs, inference_basis=basis(*cited_refs))


@settings(
    max_examples=100, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(size=st.integers(min_value=0, max_value=10_000))
def test_widening_is_monotonic_in_the_size_estimate(size):
    """P-I3: a raised estimate always widens; a lowered one never does."""
    allocator = IdentityAllocator()
    refs = ("obj-fa-1", "obj-fa-2")
    earlier = make_problem(allocator, refs, population_size_estimate=5_000)
    later = make_problem(allocator, refs, population_size_estimate=size)
    assert later.widens_population_of(earlier) == (size > 5_000)


@settings(max_examples=100, deadline=None)
@given(dropped=st.integers(min_value=1, max_value=4))
def test_dropping_qualifying_terms_always_widens(dropped):
    """P-I3: a strict subset of terms is unambiguous widening."""
    allocator = IdentityAllocator()
    refs = ("obj-fa-1", "obj-fa-2")
    terms = ["segment", "sellers", "bulk", "nightly", "europe"]
    earlier = make_problem(allocator, refs, affected_population=" ".join(terms))
    later = make_problem(
        allocator, refs, affected_population=" ".join(terms[:-dropped])
    )
    assert later.widens_population_of(earlier)
    assert not earlier.widens_population_of(later)


# ===========================================================================
# T04.1.4 -- F-W1 weight model: bands, criteria, ratings  [A, B]
# ===========================================================================

class TestWeightModel:
    """The ratified band model: two closed axes, one bijection. [F-W1 R1/R2]"""

    def test_bands_form_two_disjoint_closed_axes(self):
        assert SEVERITY_BANDS == frozenset(
            {WeightBand.MINOR, WeightBand.MODERATE, WeightBand.SEVERE}
        )
        assert FREQUENCY_BANDS == frozenset(
            {WeightBand.EPISODIC, WeightBand.RECURRING, WeightBand.PERSISTENT}
        )
        assert not (SEVERITY_BANDS & FREQUENCY_BANDS)
        assert len(SEVERITY_BANDS | FREQUENCY_BANDS) == len(WeightBand) == 6

    def test_band_criterion_bijection(self):
        """Every band maps to exactly one criterion, and back. [F-W1 R1/R2]"""
        pairs = (
            (WeightBand.MINOR, WeightCriterion.RECOVERABLE_FRICTION),
            (WeightBand.MODERATE, WeightCriterion.COMPOUNDING_COST),
            (WeightBand.SEVERE, WeightCriterion.IRREVERSIBLE_HARM),
            (WeightBand.EPISODIC, WeightCriterion.OCCURRENCE),
            (WeightBand.RECURRING, WeightCriterion.REPETITION),
            (WeightBand.PERSISTENT, WeightCriterion.CONTINUITY),
        )
        for band, criterion in pairs:
            assert criterion_for(band) is criterion
            assert band_of(criterion) is band

    def test_rank_orders_within_an_axis_only(self):
        """The ordinal exists to recognise a versioned INCREASE, never to
        select a band; and the two axes are never compared to each other
        (ranks are axis-local: MINOR and EPISODIC both sit at 0)."""
        assert band_rank(WeightBand.MINOR) < band_rank(WeightBand.MODERATE)
        assert band_rank(WeightBand.MODERATE) < band_rank(WeightBand.SEVERE)
        assert band_rank(WeightBand.EPISODIC) < band_rank(WeightBand.RECURRING)
        assert band_rank(WeightBand.RECURRING) < band_rank(WeightBand.PERSISTENT)
        assert band_rank(WeightBand.MINOR) == band_rank(WeightBand.EPISODIC)

    def test_attestation_floor_is_the_s4_floor(self):
        """The sufficiency condition is S-4's own value, uniform for every
        band: 2 independence keys, never a gradient, never a ladder."""
        assert WEIGHT_ATTESTATION_FLOOR == 2
        assert WEIGHT_ATTESTATION_FLOOR == sufficiency_threshold(ObjectType.PROBLEM)

    def test_contribution_form_rules(self):
        with pytest.raises(WeightError, match="must name the Fact"):
            WeightContribution("  ", WeightCriterion.CONTINUITY, "text")
        with pytest.raises(WeightError, match="not a ratified WeightCriterion"):
            WeightContribution("obj-fa-1", "OFTEN", "text")  # type: ignore[arg-type]
        with pytest.raises(WeightError, match="empty"):
            WeightContribution("obj-fa-1", WeightCriterion.CONTINUITY, "  ")

    def test_rating_form_rules(self):
        refs = ("obj-fa-1", "obj-fa-2")
        with pytest.raises(WeightError, match="not a ratified WeightBand"):
            WeightRating("CATASTROPHIC", "d", tuple(  # type: ignore[arg-type]
                WeightContribution(r, WeightCriterion.IRREVERSIBLE_HARM, "x")
                for r in refs
            ))
        with pytest.raises(WeightError, match="detail is required"):
            WeightRating(  # direct construction: the helper prefixes the band
                WeightBand.SEVERE, "  ",
                (WeightContribution(r, WeightCriterion.IRREVERSIBLE_HARM, "x")
                 for r in refs),
            )
        with pytest.raises(WeightError, match="justification is required"):
            WeightRating(WeightBand.SEVERE, "d", ())
        with pytest.raises(WeightError, match="criterion mismatch"):
            WeightRating(
                WeightBand.SEVERE, "d",
                (WeightContribution(r, WeightCriterion.CONTINUITY, "x") for r in refs),
            )
        with pytest.raises(WeightError, match="twice"):
            WeightRating(
                WeightBand.SEVERE, "d",
                (
                    WeightContribution("obj-fa-1", WeightCriterion.IRREVERSIBLE_HARM, "a"),
                    WeightContribution("obj-fa-1", WeightCriterion.IRREVERSIBLE_HARM, "b"),
                ),
            )

    def test_rating_exposes_its_citations(self):
        rating = WeightRating(
            WeightBand.MODERATE, "compounding",
            (
                WeightContribution("obj-fa-1", WeightCriterion.COMPOUNDING_COST, "a"),
                WeightContribution("obj-fa-2", WeightCriterion.COMPOUNDING_COST, "b"),
                WeightContribution("obj-fa-3", WeightCriterion.RECOVERABLE_FRICTION, "c"),
            ),
        )
        assert rating.cited_facts == frozenset(
            {"obj-fa-1", "obj-fa-2", "obj-fa-3"}
        )
        assert rating.facts_for(WeightCriterion.COMPOUNDING_COST) == frozenset(
            {"obj-fa-1", "obj-fa-2"}
        )
        assert rating.facts_for(WeightCriterion.IRREVERSIBLE_HARM) == frozenset()

    def test_detail_preserves_arbitrary_wording(self):
        """The free text the old model carried survives, in the detail,
        under a ratified band. [F-W1 R3, backward-compatible detail]"""
        wording = "somewhere between annoying and existential, per the team"
        assert wording in weight(WeightBand.MODERATE, ("obj-fa-1",), wording).detail


class TestProblemWeightBoundary:
    """The Problem boundary requires structured, supporting-set-bound
    ratings. [P-V4, F-W1 R3]"""

    def test_string_weight_is_rejected(self, allocator):
        with pytest.raises(WeightError, match="required as a WeightRating"):
            make_problem(allocator, severity="HIGH -- unnoticed loss")
        with pytest.raises(WeightError, match="required as a WeightRating"):
            make_problem(allocator, frequency="")

    def test_phantom_weight_citation_is_rejected(self, allocator):
        """The P-V5 phantom rule applied to weight: a rating may cite no
        Fact outside the supporting set."""
        with pytest.raises(WeightError, match="do not support this Problem"):
            make_problem(
                allocator, ("obj-fa-1", "obj-fa-2"),
                severity=weight(WeightBand.SEVERE, ("obj-fa-1", "obj-phantom")),
            )
        with pytest.raises(WeightError, match="do not support this Problem"):
            make_problem(
                allocator, ("obj-fa-1", "obj-fa-2"),
                frequency=weight(WeightBand.PERSISTENT, ("obj-phantom",)),
            )

    def test_increases_weight_over_recognises_raises_only(self, allocator):
        refs = ("obj-fa-1", "obj-fa-2")
        severe = make_problem(allocator, refs, severity=weight(WeightBand.SEVERE, refs))
        moderate = make_problem(allocator, refs, severity=weight(WeightBand.MODERATE, refs))
        persistent = make_problem(
            allocator, refs,
            severity=weight(WeightBand.MODERATE, refs),
            frequency=weight(WeightBand.PERSISTENT, refs),
        )
        recurring = make_problem(
            allocator, refs,
            severity=weight(WeightBand.MODERATE, refs),
            frequency=weight(WeightBand.RECURRING, refs),
        )
        assert moderate.increases_weight_over(severe) == ()  # decrease
        assert severe.increases_weight_over(moderate) == ("severity",)
        assert persistent.increases_weight_over(recurring) == ("frequency",)
        assert recurring.increases_weight_over(persistent) == ()
        both_raised = make_problem(
            allocator, refs,
            severity=weight(WeightBand.SEVERE, refs),
            frequency=weight(WeightBand.PERSISTENT, refs),
        )
        assert both_raised.increases_weight_over(recurring) == (
            "severity", "frequency",
        )


# ===========================================================================
# T04.1.4 -- P-V4 at the boundary  [G]
# ===========================================================================

class TestPv4WeightForm:
    def test_pv4_flags_phantom_weight_citations(self, allocator):
        problem = make_problem(allocator)
        object.__setattr__(
            problem, "severity",
            weight(WeightBand.SEVERE, ("obj-fa-1", "obj-not-supporting")),
        )
        result = pv4_weight_present(ctx(problem))
        assert result.failed
        assert "do not support" in result.detail


# ===========================================================================
# T04.1.4 -- P-I4 detective: the declared-criterion evidence ceiling  [D]
# ===========================================================================

class TestProblemIntegrityWeightCeiling:
    """Facts establish an evidence ceiling; they do not determine the
    asserted weight. The detective re-derives the ceiling from store
    state, below the pre-write gate's verdict, never above it. [F-W1 R4]"""

    def _refs(self, facts):
        return tuple(f.object_id for f in facts)

    def test_counts_never_select_a_band(self, store, allocator):
        """4 available keys, SEVERE citing 2: clean. MINOR citing 2:
        clean -- and never upgraded. The floor is uniform; surplus keys
        assert nothing. [F-W1 R4: no ladder]"""
        facts = write_facts(store, allocator, 4)
        refs = self._refs(facts)
        heavy = write_problem_from(
            store, allocator, facts, severity=weight(WeightBand.SEVERE, refs[:2]),
        )
        light = write_problem_from(
            store, allocator, facts, severity=weight(WeightBand.MINOR, refs[:2]),
        )
        violations = store.problems.integrity().verify()
        assert not [
            v for v in violations
            if v.constraint_id == "P-I4" and v.object_id in
            {heavy.object_id, light.object_id}
        ]
        assert (
            store.get_problem(light.object_id).severity.band
            is WeightBand.MINOR
        )  # never upgraded

    def test_phantom_citation_flagged(self, store, allocator, facts):
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(
            problem, "severity",
            weight(WeightBand.SEVERE, ("obj-fa-1", "obj-not-supporting")),
        )
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "do not support" in v.detail
        ]

    def test_undeclared_band_criterion_flagged(self, store, allocator, facts):
        """Form-valid rating (axis-coherent entries), but no entry declares
        the asserted band's own criterion: the rating has no
        evidence-linked backing."""
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(
            problem, "severity",
            # SEVERE band whose entries all declare MODERATE's criterion
            WeightRating(
                WeightBand.SEVERE, "SEVERE -- asserted",
                tuple(
                    WeightContribution(
                        ref, WeightCriterion.COMPOUNDING_COST, "declares the wrong criterion"
                    )
                    for ref in self._refs(facts)
                ),
            ),
        )
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "no justification entry declares IRREVERSIBLE_HARM" in v.detail
        ]

    def test_tampered_plain_text_severity_flagged(self, store, allocator, facts):
        """A rating replaced by prose is a missing rating, not a passing
        one: the F-W1 model is structural."""
        stored = write_problem_from(store, allocator, facts)
        problem = store.get_problem(stored.object_id)
        object.__setattr__(problem, "severity", "EXTREME -- prose")
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "not a WeightRating" in v.detail
        ]

    def test_mixed_criteria_pass_when_declared_criterion_attested(
        self, store, allocator, facts
    ):
        """Extra criteria in the justification cost nothing: only the
        asserted band's own criterion must be declared and attested."""
        facts = write_facts(store, allocator, 3)  # distinct Facts, one entry each
        refs = self._refs(facts)
        rating = WeightRating(
            WeightBand.SEVERE, "SEVERE -- harm with compounding onset",
            (
                WeightContribution(refs[0], WeightCriterion.IRREVERSIBLE_HARM, "harm"),
                WeightContribution(refs[1], WeightCriterion.IRREVERSIBLE_HARM, "harm"),
                WeightContribution(refs[2], WeightCriterion.COMPOUNDING_COST, "onset"),
            ),
        )
        write_problem_from(store, allocator, facts, severity=rating)
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
        ]

    def test_non_active_evidence_drops_out_of_the_span(
        self, store, allocator, facts
    ):
        """The span is re-derived from CURRENT store state: retracting one
        Evidence halves the attestation and the ceiling no longer carries
        the rating. [F-W1 R4 re-derivation]"""
        refs = self._refs(facts)
        stored = write_problem_from(store, allocator, facts)
        # Each fixture Fact has its own Evidence; retract the first.
        first_fact = store.get_fact(refs[0])
        first_evidence_ref = first_fact.attachments[0].evidence_ref
        store.transition(
            first_evidence_ref, ObjectStatus.RETRACTED, "retracted upstream"
        )
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "1 independence key" in v.detail
        ]

    def test_frequency_axis_judged_independently(self, store, allocator, facts):
        refs = self._refs(facts)
        stored = write_problem_from(
            store, allocator, facts,
            frequency=weight(WeightBand.PERSISTENT, refs[:1]),
        )
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "frequency" in v.detail
        ]

    def test_deleted_citation_falls_below_the_floor(self, store, allocator, facts):
        """The ceiling is re-derived from CURRENT store state: a rating
        that cited a since-deleted Fact loses that Fact's keys. P-I2
        reports the broken reference; P-I4 additionally reports that the
        rating's span no longer carries it."""
        refs = self._refs(facts)
        stored = write_problem_from(store, allocator, facts)
        # one supporting Fact vanishes -- object AND payload, so neither
        # the object map nor the Fact registry can resolve it
        del store._objects[refs[1]]
        del store.facts._payloads[refs[1]]
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I2" for v in violations)
        assert [
            v for v in violations
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "1 independence key" in v.detail
        ]

    def test_payload_less_evidence_contributes_no_key(self, store, allocator, facts):
        """A stored-but-payloadless Evidence (structural break) yields no
        independence key: the span may fall, never be inflated."""
        refs = self._refs(facts)
        stored = write_problem_from(store, allocator, facts)
        second_fact = store.get_fact(refs[1])
        ev_ref = second_fact.attachments[0].evidence_ref
        del store.evidence._payloads[ev_ref]  # payload lost, object remains
        assert [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I4"
            and v.object_id == stored.object_id
            and "1 independence key" in v.detail
        ]


# ===========================================================================
# T04.1.4 -- store roundtrip  [G]
# ===========================================================================

class TestWeightStoreRoundtrip:
    def test_rating_survives_write_and_read(self, store, allocator, facts):
        refs = tuple(f.object_id for f in facts)
        severity = weight(WeightBand.SEVERE, refs, "unnoticed loss reaches customers")
        frequency = weight(WeightBand.RECURRING, refs, "multiple periods")
        stored = write_problem_from(
            store, allocator, facts, severity=severity, frequency=frequency,
        )
        payload = store.get_problem(stored.object_id)
        assert payload.severity == severity
        assert payload.frequency == frequency
        assert payload.severity is not None
        assert payload.severity.band is WeightBand.SEVERE
        assert payload.severity.cited_facts == frozenset(refs)
        assert payload.severity.facts_for(
            WeightCriterion.IRREVERSIBLE_HARM
        ) == frozenset(refs)
