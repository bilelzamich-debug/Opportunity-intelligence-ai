"""Contract tests for the Solution object type.

Task: T01.7.6

Architecture References:
- S-V1..S-V6  Solution validation rules
- S-I1..S-I4  Solution integrity constraints
- R-1         Assumption refinement produces a new version
- R-3         evidential_support inherited from the Opportunity
- N-6         Graph is a derived index, never authoritative alone
- N-14        Lineage-restricted read of underlying Problems
- M-29        Solution depth OPEN
- M-69        Constraint model OPEN; constraints carried, not typed
- M-31        Gate ownership OPEN: Validation reports, it does not gate

Acceptance criteria under test:
  AC1  assumptions non-empty enforced (S-V2)
  AC2  Each assumption has criticality and testability
  AC3  candidate_group supports sibling candidates
"""

from __future__ import annotations

import threading

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.enums import Engine, ObjectStatus, ObjectType, RelationshipType
from oip.identity import IdentityAllocator
from oip.solution import (
    SOLUTION_RULES,
    Assumption,
    AssumptionError,
    AssumptionRemovalError,
    AssumptionSupersession,
    CandidateGroupError,
    FeasibilityError,
    OpportunityReferenceError,
    ProblemFit,
    ProblemFitError,
    ProblemFitRationale,
    Solution,
    SolutionError,
    SolutionIntegrity,
    sv1_opportunity_resolves_and_is_active,
    sv2_assumptions_present,
    sv3_assumptions_are_testable,
    sv4_problem_fit_references_lineage,
    sv5_not_an_opportunity_restatement,
    sv6_feasibility_present,
)
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs
from tests.test_opportunity import write_opportunity_from, write_patterns

STATEMENT = (
    "A pre-commit validation and post-operation reconciliation layer for bulk "
    "seller operations, reporting per-item outcome immediately on completion "
    "and surfacing partial failures explicitly."
)
SHARED_APPROACH = (
    "Per-item outcome reporting addresses the shared missing-feedback "
    "structure rather than any single operation type."
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def assumption(aid: str = "A1", **overrides) -> Assumption:
    kwargs = {
        "assumption_id": aid,
        "assumption_statement": (
            f"Assumption {aid}: sellers act on per-item failure reports."
        ),
        "criticality": "CRITICAL -- solution fails if reports are ignored",
        "testability": "Observable via response rates in comparable tooling",
    }
    kwargs.update(overrides)
    return Assumption(**kwargs)


def fit_rationale(*problem_refs: str, approach: str | None = None) -> ProblemFitRationale:
    return ProblemFitRationale(
        shared_approach=approach or SHARED_APPROACH,
        fits=tuple(
            ProblemFit(
                problem_ref=ref,
                how_addressed=f"{ref} is addressed by per-item reporting",
            )
            for ref in problem_refs
        ),
    )


def make_solution(
    allocator: IdentityAllocator,
    opportunity_ref: str = "obj-op-1",
    *,
    problem_refs: tuple[str, ...] = ("obj-pr-1",),
    assumptions: tuple[Assumption, ...] | None = None,
    source_count: int = 3,
    upstream_ceiling: float | None = None,
    support: float = 0.62,
    assertion: float = 0.58,
    status: ObjectStatus = ObjectStatus.ACTIVE,
    status_reason: str | None = None,
    **overrides,
) -> Solution:
    identity = overrides.pop("identity", None) or allocator.new_object()
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.SOLUTION,
        ((opportunity_ref, ObjectType.OPPORTUNITY),),
        status=status,
        status_reason=status_reason,
        source_count=source_count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
    )
    kwargs = {
        "attributes": attributes,
        "solution_statement": overrides.pop("solution_statement", STATEMENT),
        "addresses_opportunity": overrides.pop(
            "addresses_opportunity", opportunity_ref
        ),
        "assumptions": (
            assumptions if assumptions is not None else (assumption("A1"),)
        ),
        "problem_fit_rationale": overrides.pop(
            "problem_fit_rationale", fit_rationale(*problem_refs)
        ),
        "feasibility_assessment": overrides.pop(
            "feasibility_assessment", "Feasible in principle; A1 is binding."
        ),
        "candidate_group": overrides.pop("candidate_group", "obj-op-1-candidates"),
    }
    kwargs.update(overrides)
    return Solution(**kwargs)


def ctx(solution: Solution, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": solution.attributes, "solution": solution}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def write_opportunities(store, allocator, n: int = 1):
    stored = []
    for _ in range(n):
        patterns = write_patterns(store, allocator, 1)
        stored.append(write_opportunity_from(store, allocator, patterns))
    return stored


def write_solution_from(
    store, allocator, stored_opportunity, predecessor_id: str | None = None, **overrides
):
    ref = stored_opportunity.object_id
    problems = sorted(
        store._lineage_of_type(ref, ObjectType.PROBLEM) or frozenset()
    )
    kwargs = {
        "problem_refs": tuple(problems[:1]),
        "candidate_group": f"{ref}-candidates",
        "upstream_ceiling": stored_opportunity.attributes.confidence.effective_confidence,
    }
    kwargs.update(overrides)
    return store.write_solution(
        make_solution(allocator, ref, **kwargs), predecessor_id=predecessor_id
    )


@pytest.fixture()
def opportunity(store, allocator):
    return write_opportunities(store, allocator, 1)[0]


# ===========================================================================
# AC1 -- assumptions non-empty  [S-V2]
# ===========================================================================

class TestAssumptionsRequired:
    def test_one_assumption_accepted(self, allocator):
        assert make_solution(allocator).assumption_count == 1

    def test_many_assumptions_accepted(self, allocator):
        many = tuple(assumption(f"A{i}") for i in range(12))
        assert make_solution(allocator, assumptions=many).assumption_count == 12

    def test_no_assumptions_refused_at_construction(self, allocator):
        """S-V2 requires the PRESENCE of uncertainty. [IOM section 3.6]"""
        with pytest.raises(AssumptionError) as exc:
            make_solution(allocator, assumptions=())
        assert "concealing them" in str(exc.value)

    def test_sv2_detects_a_stripped_assumption_set(self, allocator):
        s = make_solution(allocator)
        object.__setattr__(s, "assumptions", ())
        result = sv2_assumptions_present(ctx(s))
        assert result.failed
        assert "nothing to test" in result.detail

    def test_sv2_passes_with_assumptions(self, allocator):
        result = sv2_assumptions_present(ctx(make_solution(allocator)))
        assert result.outcome is RuleOutcome.PASS

    def test_duplicate_assumption_ids_refused(self, allocator):
        """Validation addresses assumptions by id; ids must be unique."""
        with pytest.raises(AssumptionError) as exc:
            make_solution(
                allocator, assumptions=(assumption("A1"), assumption("A1"))
            )
        assert "not unique" in str(exc.value)

    def test_store_rejects_an_assumptionless_solution(
        self, store, allocator, opportunity
    ):
        s = make_solution(
            allocator, opportunity.object_id,
            upstream_ceiling=opportunity.attributes.confidence.effective_confidence,
        )
        object.__setattr__(s, "assumptions", ())
        with pytest.raises(WriteRejectedError) as exc:
            store.write_solution(s)
        assert "S-V2" in exc.value.failure.rule_ids

    def test_assumption_statement_required(self):
        with pytest.raises(AssumptionError):
            assumption("A1", assumption_statement="  ")

    def test_assumption_id_required(self):
        with pytest.raises(AssumptionError):
            assumption("")


# ===========================================================================
# AC2 -- criticality and testability  [S-V3]
# ===========================================================================

class TestAssumptionStructure:
    def test_criticality_required(self):
        with pytest.raises(AssumptionError) as exc:
            assumption("A1", criticality="")
        assert "whether the solution fails" in str(exc.value)

    def test_testability_required(self):
        with pytest.raises(AssumptionError) as exc:
            assumption("A1", testability="   ")
        assert "bypasses Validation" in str(exc.value)

    def test_sv3_passes_when_complete(self, allocator):
        result = sv3_assumptions_are_testable(ctx(make_solution(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "addressable and testable" in result.detail

    @pytest.mark.parametrize("field_name", ["criticality", "testability"])
    def test_sv3_detects_a_stripped_field(self, allocator, field_name):
        s = make_solution(allocator)
        object.__setattr__(s.assumptions[0], field_name, "")
        result = sv3_assumptions_are_testable(ctx(s))
        assert result.failed
        assert field_name in result.detail
        assert "TESTS single assumptions" in result.detail

    def test_sv3_detects_one_bad_assumption_among_many(self, allocator):
        many = tuple(assumption(f"A{i}") for i in range(5))
        s = make_solution(allocator, assumptions=many)
        object.__setattr__(s.assumptions[3], "testability", "")
        result = sv3_assumptions_are_testable(ctx(s))
        assert result.failed
        assert "A3" in result.detail

    def test_no_criticality_vocabulary_asserted(self, allocator):
        """The IOM defines no closed scale; none is invented here."""
        s = make_solution(
            allocator,
            assumptions=(assumption("A1", criticality="somewhat load-bearing"),),
        )
        assert not sv3_assumptions_are_testable(ctx(s)).failed

    def test_assumptions_individually_addressable(self, allocator):
        many = tuple(assumption(f"A{i}") for i in range(4))
        s = make_solution(allocator, assumptions=many)
        assert s.assumption("A2") is not None
        assert s.assumption("A99") is None

    def test_testable_surface_exposed(self, store, allocator, opportunity):
        """Validation TESTS these individually. [S-V2, S-V3]"""
        stored = write_solution_from(
            store, allocator, opportunity,
            assumptions=(assumption("A1"), assumption("A2")),
        )
        surface = store.solutions.testable_surface(stored.object_id)
        assert len(surface) == 2
        assert store.solutions.testable_surface("obj-absent") == ()


# ===========================================================================
# AC3 -- candidate_group and sibling candidates  [S-I3]
# ===========================================================================

class TestCandidateGroup:
    def test_required_at_construction(self, allocator):
        with pytest.raises(CandidateGroupError) as exc:
            make_solution(allocator, candidate_group="  ")
        assert "comparative validation is impossible" in str(exc.value)

    def test_siblings_coexist(self, store, allocator, opportunity):
        """Multiple candidates per Opportunity is expected, not exceptional."""
        first = write_solution_from(store, allocator, opportunity)
        second = write_solution_from(store, allocator, opportunity)
        third = write_solution_from(store, allocator, opportunity)
        assert len(store.solutions.candidates_for(opportunity.object_id)) == 3
        for stored in (first, second, third):
            assert store.get(stored.object_id).status is ObjectStatus.ACTIVE

    def test_candidate_group_locates_competitors(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        write_solution_from(store, allocator, opportunity)
        group = f"{opportunity.object_id}-candidates"
        assert len(store.solutions.candidate_group(group)) == 2
        assert store.solutions.candidate_group("absent") == ()

    def test_siblings_of_excludes_self(self, store, allocator, opportunity):
        first = write_solution_from(store, allocator, opportunity)
        write_solution_from(store, allocator, opportunity)
        siblings = store.solutions.siblings_of(first.object_id)
        assert len(siblings) == 1
        assert siblings[0].object_id != first.object_id

    def test_siblings_of_unknown_is_empty(self, store):
        assert store.solutions.siblings_of("obj-absent") == ()

    def test_is_sibling_of_predicate(self, allocator):
        a = make_solution(allocator, candidate_group="g1")
        b = make_solution(allocator, candidate_group="g1")
        c = make_solution(allocator, candidate_group="g2")
        assert a.is_sibling_of(b)
        assert not a.is_sibling_of(c)
        assert not a.is_sibling_of(a)

    def test_distinct_opportunities_are_not_siblings(self, store, allocator):
        first, second = write_opportunities(store, allocator, 2)
        write_solution_from(store, allocator, first)
        write_solution_from(store, allocator, second)
        assert len(store.solutions.candidates_for(first.object_id)) == 1


# ===========================================================================
# S-V1  opportunity resolvable and ACTIVE
# ===========================================================================

class TestOpportunityReference:
    def test_required_at_construction(self, allocator):
        with pytest.raises(OpportunityReferenceError):
            make_solution(allocator, addresses_opportunity="  ")

    def test_must_be_in_derives_from(self, allocator):
        with pytest.raises(OpportunityReferenceError) as exc:
            make_solution(allocator, addresses_opportunity="obj-op-unread")
        assert "addresses the Opportunity it read" in str(exc.value)

    def test_derives_from_must_be_opportunities(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.SOLUTION,
            (("obj-pt-1", ObjectType.PATTERN),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(SolutionError) as exc:
            make_solution(allocator, "obj-pt-1", attributes=attributes)
        assert "derives from Opportunities only" in str(exc.value)

    def test_sv1_passes_for_an_active_opportunity(self, allocator):
        result = sv1_opportunity_resolves_and_is_active(
            ctx(
                make_solution(allocator),
                resolve_type=lambda r: ObjectType.OPPORTUNITY,
                upstream_status=lambda r: ObjectStatus.ACTIVE,
            )
        )
        assert result.outcome is RuleOutcome.PASS

    def test_sv1_detects_unresolvable(self, allocator):
        result = sv1_opportunity_resolves_and_is_active(
            ctx(make_solution(allocator), resolve_type=lambda r: None)
        )
        assert result.failed
        assert "does not resolve" in result.detail

    def test_sv1_detects_mistyped(self, allocator):
        result = sv1_opportunity_resolves_and_is_active(
            ctx(make_solution(allocator), resolve_type=lambda r: ObjectType.PATTERN)
        )
        assert result.failed
        assert "not an Opportunity" in result.detail

    @pytest.mark.parametrize(
        "status",
        [ObjectStatus.SUPERSEDED, ObjectStatus.REJECTED,
         ObjectStatus.INVALIDATED, ObjectStatus.ARCHIVED],
    )
    def test_sv1_rejects_a_non_active_opportunity(self, allocator, status):
        result = sv1_opportunity_resolves_and_is_active(
            ctx(
                make_solution(allocator),
                resolve_type=lambda r: ObjectType.OPPORTUNITY,
                upstream_status=lambda r: status,
            )
        )
        assert result.failed
        assert "not ACTIVE" in result.detail

    def test_sv1_detects_a_stripped_reference(self, allocator):
        s = make_solution(allocator)
        object.__setattr__(s, "addresses_opportunity", "")
        assert sv1_opportunity_resolves_and_is_active(ctx(s)).failed

    def test_sv1_skips_without_resolver(self, allocator):
        assert sv1_opportunity_resolves_and_is_active(
            ctx(make_solution(allocator))
        ).outcome is RuleOutcome.SKIP

    def test_sv1_skips_without_status_provider(self, allocator):
        result = sv1_opportunity_resolves_and_is_active(
            ctx(make_solution(allocator), resolve_type=lambda r: ObjectType.OPPORTUNITY)
        )
        assert result.outcome is RuleOutcome.SKIP
        assert "no status provider" in result.detail

    def test_store_rejects_a_superseded_opportunity(
        self, store, allocator, opportunity
    ):
        store.transition(opportunity.object_id, ObjectStatus.SUPERSEDED, "rescored")
        with pytest.raises(WriteRejectedError) as exc:
            write_solution_from(store, allocator, opportunity)
        assert {"S-V1", "I8"} & set(exc.value.failure.rule_ids)


# ===========================================================================
# S-V4  problem fit via lineage
# ===========================================================================

class TestProblemFit:
    def test_required_at_construction(self, allocator):
        with pytest.raises(ProblemFitError):
            make_solution(allocator, problem_fit_rationale=None)

    def test_shared_approach_required(self):
        with pytest.raises(ProblemFitError):
            ProblemFitRationale(
                shared_approach="  ",
                fits=(ProblemFit("obj-pr-1", "addressed"),),
            )

    def test_fits_required(self):
        with pytest.raises(ProblemFitError):
            ProblemFitRationale(shared_approach="approach", fits=())

    def test_fit_requires_a_problem_ref(self):
        with pytest.raises(ProblemFitError):
            ProblemFit(problem_ref="  ", how_addressed="x")

    def test_fit_requires_content(self):
        with pytest.raises(ProblemFitError) as exc:
            ProblemFit(problem_ref="obj-pr-1", how_addressed="")
        assert "semantically empty" in str(exc.value)

    def test_a_problem_may_not_be_addressed_twice(self):
        with pytest.raises(ProblemFitError):
            ProblemFitRationale(
                shared_approach="a",
                fits=(ProblemFit("obj-pr-1", "x"), ProblemFit("obj-pr-1", "y")),
            )

    def test_fit_lookup(self, allocator):
        s = make_solution(allocator)
        assert s.problem_fit_rationale.fit_for("obj-pr-1") is not None
        assert s.problem_fit_rationale.fit_for("absent") is None

    def test_sv4_passes_when_reachable(self, allocator):
        result = sv4_problem_fit_references_lineage(
            ctx(
                make_solution(allocator),
                lineage_problems=lambda oid: frozenset({"obj-pr-1"}),
            )
        )
        assert result.outcome is RuleOutcome.PASS

    def test_sv4_rejects_a_problem_outside_lineage(self, allocator):
        """Generic solutioning wearing a lineage citation. [N-14]"""
        result = sv4_problem_fit_references_lineage(
            ctx(
                make_solution(allocator),
                lineage_problems=lambda oid: frozenset({"obj-pr-other"}),
            )
        )
        assert result.failed
        assert "asserted, not demonstrated" in result.detail

    def test_sv4_detects_a_stripped_approach(self, allocator):
        s = make_solution(allocator)
        object.__setattr__(s.problem_fit_rationale, "shared_approach", "")
        result = sv4_problem_fit_references_lineage(ctx(s))
        assert result.failed
        assert "not a demonstration of fit" in result.detail

    def test_sv4_detects_emptied_fits(self, allocator):
        s = make_solution(allocator)
        object.__setattr__(s.problem_fit_rationale, "fits", ())
        result = sv4_problem_fit_references_lineage(ctx(s))
        assert result.failed
        assert "references no Problem" in result.detail

    def test_sv4_skips_without_a_provider(self, allocator):
        result = sv4_problem_fit_references_lineage(ctx(make_solution(allocator)))
        assert result.outcome is RuleOutcome.SKIP

    def test_sv4_skips_when_untraversable(self, allocator):
        result = sv4_problem_fit_references_lineage(
            ctx(make_solution(allocator), lineage_problems=lambda oid: None)
        )
        assert result.outcome is RuleOutcome.SKIP

    def test_sv4_is_live_at_acceptance(self, store, allocator, opportunity):
        """Regression guard: O-V6 was once dead for exactly this reason."""
        from oip.acceptance import AcceptancePath

        seen = []
        original = AcceptancePath.accept

        def spy(self, c):
            result = original(self, c)
            seen.extend(r for r in result.results if r.rule_id == "S-V4")
            return result

        AcceptancePath.accept = spy
        try:
            write_solution_from(store, allocator, opportunity)
        finally:
            AcceptancePath.accept = original
        assert seen and seen[0].outcome is not RuleOutcome.SKIP

    def test_store_rejects_a_foreign_problem(self, store, allocator):
        """Adversarial: cite a real Problem not beneath this Solution."""
        first, second = write_opportunities(store, allocator, 2)
        foreign = sorted(
            store._lineage_of_type(second.object_id, ObjectType.PROBLEM)
        )[0]
        with pytest.raises(WriteRejectedError) as exc:
            write_solution_from(
                store, allocator, first, problem_refs=(foreign,)
            )
        assert "S-V4" in exc.value.failure.rule_ids


# ===========================================================================
# S-V5  not an Opportunity restatement
# ===========================================================================

class TestNotARestatement:
    def test_distinct_statement_passes(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        assert stored.status is ObjectStatus.ACTIVE

    def test_verbatim_restatement_rejected(self, store, allocator, opportunity):
        original = store.get_opportunity(opportunity.object_id).opportunity_statement
        with pytest.raises(WriteRejectedError) as exc:
            write_solution_from(
                store, allocator, opportunity, solution_statement=original
            )
        assert "S-V5" in exc.value.failure.rule_ids

    @pytest.mark.parametrize(
        "mutate",
        [lambda t: t + ".", lambda t: f"  {t} !!", lambda t: t.upper(),
         lambda t: t.replace(" ", "   ")],
    )
    def test_punctuation_variants_are_still_restatements(
        self, store, allocator, opportunity, mutate
    ):
        """The defect found at the Problem stage must not recur here."""
        original = store.get_opportunity(opportunity.object_id).opportunity_statement
        with pytest.raises(WriteRejectedError) as exc:
            write_solution_from(
                store, allocator, opportunity, solution_statement=mutate(original)
            )
        assert "S-V5" in exc.value.failure.rule_ids

    def test_a_genuine_approach_is_not_a_restatement(
        self, store, allocator, opportunity
    ):
        original = store.get_opportunity(opportunity.object_id).opportunity_statement
        stored = write_solution_from(
            store, allocator, opportunity,
            solution_statement=f"{original} Achieved via reconciliation.",
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_sv5_detects_an_absent_statement(self, allocator):
        s = make_solution(allocator)
        object.__setattr__(s, "solution_statement", "  ")
        result = sv5_not_an_opportunity_restatement(ctx(s))
        assert result.failed
        assert "unstated approach" in result.detail

    def test_sv5_skips_without_a_provider(self, allocator):
        result = sv5_not_an_opportunity_restatement(ctx(make_solution(allocator)))
        assert result.outcome is RuleOutcome.SKIP

    def test_sv5_skips_when_statement_unavailable(self, allocator):
        result = sv5_not_an_opportunity_restatement(
            ctx(make_solution(allocator), opportunity_statement_text=lambda r: None)
        )
        assert result.outcome is RuleOutcome.SKIP


# ===========================================================================
# S-V6  feasibility
# ===========================================================================

class TestFeasibility:
    def test_required_at_construction(self, allocator):
        with pytest.raises(FeasibilityError) as exc:
            make_solution(allocator, feasibility_assessment="")
        assert "impossible approaches" in str(exc.value)

    def test_sv6_passes_and_records_the_open_marker(self, allocator):
        """M-69: no constraint model exists to assess against."""
        result = sv6_feasibility_present(ctx(make_solution(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "M-69" in result.detail

    def test_sv6_detects_a_stripped_assessment(self, allocator):
        s = make_solution(allocator)
        object.__setattr__(s, "feasibility_assessment", "   ")
        assert sv6_feasibility_present(ctx(s)).failed

    def test_constraints_are_carried_not_typed(self, allocator):
        """M-69 open: any constraint text is accepted, none is interpreted."""
        s = make_solution(allocator, constraints=("anything at all", "42"))
        assert len(s.constraints) == 2


# ===========================================================================
# Rule-set hygiene
# ===========================================================================

class TestRuleSetHygiene:
    def test_six_rules_registered(self, store):
        assert {f"S-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)
        assert len(SOLUTION_RULES) == 6

    def test_rule_ids_in_order(self):
        assert [r.rule_id for r in SOLUTION_RULES] == [
            f"S-V{i}" for i in range(1, 7)
        ]

    @pytest.mark.parametrize("rule", SOLUTION_RULES)
    def test_every_rule_skips_non_solutions(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert rule(AcceptanceContext(attributes=attributes)).outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", SOLUTION_RULES)
    def test_every_rule_skips_without_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.SOLUTION,
            (("obj-op-1", ObjectType.OPPORTUNITY),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Solution payload" in result.detail

    def test_earlier_stages_unaffected(self, store, allocator):
        stored = write_opportunities(store, allocator, 1)[0]
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# Type, authority, attributes
# ===========================================================================

class TestTypeAndAuthority:
    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.OPPORTUNITY,
            (("obj-pt-1", ObjectType.PATTERN),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(SolutionError):
            make_solution(allocator, "obj-pt-1", attributes=attributes)

    def test_only_solution_intelligence_may_create(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.SOLUTION,
            (("obj-op-1", ObjectType.OPPORTUNITY),),
            engine=Engine.OPPORTUNITY_INTELLIGENCE,
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(SolutionError) as exc:
            make_solution(allocator, attributes=attributes)
        assert "V7" in str(exc.value)

    def test_statement_required(self, allocator):
        with pytest.raises(SolutionError):
            make_solution(allocator, solution_statement="  ")

    def test_optional_attributes_default_absent(self, allocator):
        s = make_solution(allocator)
        assert s.differentiators is None
        assert s.dependencies == ()
        assert s.risk_factors == ()
        assert s.precedents == ()
        assert s.superseded_assumptions == ()

    def test_optional_attributes_carried(self, allocator):
        s = make_solution(
            allocator,
            differentiators="lighter integration burden than siblings",
            dependencies=("marketplace API access",),
            risk_factors=("seller notification fatigue",),
            precedents=("comparable reconciliation tooling",),
        )
        assert s.differentiators

    def test_identity_delegated(self, allocator):
        s = make_solution(allocator)
        assert s.object_id == s.attributes.object_id
        assert s.lineage_id == s.attributes.lineage_id
        assert s.status is s.attributes.status
        assert s.independent_source_count == 3

    def test_frozen(self, allocator):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            make_solution(allocator).solution_statement = "x"

    def test_addressed_problems_exposed(self, allocator):
        s = make_solution(allocator, problem_refs=("obj-pr-1", "obj-pr-2"))
        assert s.addressed_problems == frozenset({"obj-pr-1", "obj-pr-2"})
        assert s.addresses("obj-pr-1")
        assert not s.addresses("obj-pr-9")


# ===========================================================================
# S-I1..S-I4  integrity
# ===========================================================================

class TestSolutionIntegrity:
    def test_clean_store_holds(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        assert store.solutions.integrity().verify() == ()

    def test_si1_detects_a_removed_assumption(self, store, allocator, opportunity):
        """Assumptions are superseded with rationale, never removed. [S-I1]"""
        first = write_solution_from(
            store, allocator, opportunity,
            assumptions=(assumption("A1"), assumption("A2")),
        )
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")
        successor = allocator.succeed(first.attributes.identity)
        write_solution_from(
            store, allocator, opportunity,
            identity=successor, predecessor_id=first.object_id,
            assumptions=(assumption("A1"),),
        )
        violations = store.solutions.integrity().verify()
        assert any(v.constraint_id == "S-I1" for v in violations)
        assert "A2" in "".join(v.detail for v in violations)

    def test_si1_permits_a_recorded_supersession(
        self, store, allocator, opportunity
    ):
        first = write_solution_from(
            store, allocator, opportunity,
            assumptions=(assumption("A1"), assumption("A2")),
        )
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")
        successor = allocator.succeed(first.attributes.identity)
        write_solution_from(
            store, allocator, opportunity,
            identity=successor, predecessor_id=first.object_id,
            assumptions=(assumption("A1"),),
            superseded_assumptions=(
                AssumptionSupersession("A2", "Resolved by FA-2207; no longer assumed."),
            ),
        )
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I1"
        ]

    def test_si1_permits_growth(self, store, allocator, opportunity):
        first = write_solution_from(store, allocator, opportunity)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")
        successor = allocator.succeed(first.attributes.identity)
        write_solution_from(
            store, allocator, opportunity,
            identity=successor, predecessor_id=first.object_id,
            assumptions=(assumption("A1"), assumption("A2")),
        )
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I1"
        ]

    def test_supersession_requires_a_rationale(self):
        with pytest.raises(AssumptionRemovalError) as exc:
            AssumptionSupersession("A2", "  ")
        assert "never removed" in str(exc.value)

    def test_supersession_requires_an_id(self):
        with pytest.raises(AssumptionRemovalError):
            AssumptionSupersession("", "rationale")

    def test_si2_detects_a_problem_outside_lineage(
        self, store, allocator, opportunity
    ):
        stored = write_solution_from(store, allocator, opportunity)
        s = store.get_solution(stored.object_id)
        object.__setattr__(
            s.problem_fit_rationale, "fits",
            (ProblemFit("obj-pr-elsewhere", "claimed"),),
        )
        violations = store.solutions.integrity().verify()
        assert any(v.constraint_id == "S-I2" for v in violations)
        assert "semantically empty" in "".join(v.detail for v in violations)

    def test_si2_accepts_a_reachable_problem(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I2"
        ]

    def test_si3_detects_a_changed_candidate_group(
        self, store, allocator, opportunity
    ):
        """A migrating candidate makes its original group look converged."""
        first = write_solution_from(store, allocator, opportunity)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")
        successor = allocator.succeed(first.attributes.identity)
        write_solution_from(
            store, allocator, opportunity,
            identity=successor, predecessor_id=first.object_id,
            candidate_group="a-different-comparison",
        )
        violations = store.solutions.integrity().verify()
        assert any(v.constraint_id == "S-I3" for v in violations)
        assert "appears to have converged" in "".join(v.detail for v in violations)

    def test_si3_stable_group_across_versions_holds(
        self, store, allocator, opportunity
    ):
        first = write_solution_from(store, allocator, opportunity)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")
        successor = allocator.succeed(first.attributes.identity)
        write_solution_from(
            store, allocator, opportunity,
            identity=successor, predecessor_id=first.object_id,
        )
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I3"
        ]

    def test_si3_detects_a_migrated_opportunity(self, store, allocator):
        """A candidate cannot move between comparisons. [S-I3]"""
        first_opp, second_opp = write_opportunities(store, allocator, 2)
        first = write_solution_from(store, allocator, first_opp)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")

        successor = allocator.succeed(first.attributes.identity)
        migrated = store.get_solution(first.object_id)
        second = write_solution_from(
            store, allocator, second_opp,
            identity=successor, predecessor_id=first.object_id,
            candidate_group=migrated.candidate_group,
        )
        violations = store.solutions.integrity().verify()
        assert any(
            v.constraint_id == "S-I3" and "cannot migrate" in v.detail
            for v in violations
        )

    def test_si3_withdrawal_reason_guaranteed_by_v9(self, allocator):
        """A silent collapse by unreasoned withdrawal is already impossible.

        V9 refuses to construct any non-ACTIVE object without a
        status_reason, so S-I3 does not re-check it.
        """
        from oip.contract import StatusReasonError

        with pytest.raises(StatusReasonError):
            build_attrs(
                allocator.new_object(), ObjectType.SOLUTION,
                (("obj-op-1", ObjectType.OPPORTUNITY),),
                status=ObjectStatus.ARCHIVED, status_reason=None,
            )

    def test_si4_detects_an_altered_opportunity_assessment(
        self, store, allocator, opportunity
    ):
        """A Solution never revises the value judgement above it. [S-I4]"""
        from oip.contract import Confidence

        write_solution_from(store, allocator, opportunity)
        stored_opportunity = store._objects[opportunity.object_id]
        object.__setattr__(
            stored_opportunity.attributes, "confidence",
            Confidence(evidential_support=0.2, assertion_confidence=0.2,
                       effective_confidence=0.2),
        )
        violations = store.solutions.integrity().verify()
        assert any(v.constraint_id == "S-I4" for v in violations)
        assert "never revises" in "".join(v.detail for v in violations)

    def test_si4_detects_an_altered_score(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        payload = store.get_opportunity(opportunity.object_id)
        object.__setattr__(payload.score, "value", 0.999)
        assert any(
            v.constraint_id == "S-I4"
            for v in store.solutions.integrity().verify()
        )

    def test_si4_detects_a_vanished_opportunity(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        del store._objects[opportunity.object_id]
        violations = store.solutions.integrity().verify()
        assert any(
            v.constraint_id == "S-I4" and "no longer retrievable" in v.detail
            for v in violations
        )

    def test_si4_accepts_an_untouched_opportunity(
        self, store, allocator, opportunity
    ):
        write_solution_from(store, allocator, opportunity)
        write_solution_from(store, allocator, opportunity)
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I4"
        ]

    def test_si4_reports_one_violation_per_opportunity(
        self, store, allocator, opportunity
    ):
        """Three siblings sharing one Opportunity must not triple-report."""
        from oip.contract import Confidence

        for _ in range(3):
            write_solution_from(store, allocator, opportunity)
        object.__setattr__(
            store._objects[opportunity.object_id].attributes, "confidence",
            Confidence(evidential_support=0.2, assertion_confidence=0.2,
                       effective_confidence=0.2),
        )
        violations = [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I4"
        ]
        assert len(violations) == 1

    def test_assessment_recording_counts(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        assert store.solutions.integrity().recorded_assessment_count == 1

    def test_unregistered_solutions_skipped(self, store, allocator):
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.solutions.integrity().verify() == ()

    def test_verifier_constructible_standalone(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        verifier = SolutionIntegrity(solution_of=store.solutions.get, store=store)
        assert verifier.verify() == ()

    def test_si2_skipped_without_a_graph(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)

        class GraphlessStore:
            graph = None

            def objects_of_type(self, t):
                return ()

        verifier = SolutionIntegrity(
            solution_of=store.solutions.get, store=GraphlessStore()
        )
        assert verifier.verify() == ()


# ===========================================================================
# Store integration
# ===========================================================================

class TestStoreIntegration:
    def test_payload_retrievable(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        assert store.get_solution(stored.object_id) is not None

    def test_unknown_payload_is_none(self, store):
        assert store.get_solution("obj-absent") is None

    def test_registry_counts_and_memoises(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        assert len(store.solutions) == 1
        assert store.solutions is store.solutions

    def test_active_solutions_exclude_withdrawn(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        assert len(store.solutions.active_solutions()) == 1
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "not pursued")
        assert store.solutions.active_solutions() == ()

    def test_rejected_write_leaves_no_payload(self, store, allocator, opportunity):
        before = len(store.solutions)
        with pytest.raises(WriteRejectedError):
            write_solution_from(
                store, allocator, opportunity, problem_refs=("obj-pr-foreign",)
            )
        assert len(store.solutions) == before

    def test_rejected_write_records_a_failure(self, store, allocator, opportunity):
        with pytest.raises(WriteRejectedError):
            write_solution_from(
                store, allocator, opportunity, problem_refs=("obj-pr-foreign",)
            )
        assert store.failure_records[-1].object_type is ObjectType.SOLUTION

    def test_supersession_accepted(self, store, allocator, opportunity):
        first = write_solution_from(store, allocator, opportunity)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")
        successor = allocator.succeed(first.attributes.identity)
        second = write_solution_from(
            store, allocator, opportunity,
            identity=successor, predecessor_id=first.object_id,
        )
        assert second.attributes.version == 2
        assert second.lineage_id == first.lineage_id

    def test_lineage_of_type_is_restricted(self, store, allocator, opportunity):
        """N-14: only ancestors, never siblings."""
        stored = write_solution_from(store, allocator, opportunity)
        problems = store._lineage_of_type(stored.object_id, ObjectType.PROBLEM)
        assert len(problems) == 2
        assert store._lineage_of_type("obj-absent", ObjectType.PROBLEM) is None

    def test_opportunity_statement_provider(self, store, allocator, opportunity):
        assert store._opportunity_statement_text(opportunity.object_id)
        assert store._opportunity_statement_text("obj-absent") is None


# ===========================================================================
# Lineage, graph, cascade, confidence
# ===========================================================================

class TestPipelineIntegration:
    def test_reaches_evidence_at_depth_five(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.depth_to_evidence(stored.object_id) == 5

    def test_evidence_set_spans_the_chain(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        assert len(store.graph.evidence_set(stored.object_id)) == 4

    def test_lineage_edges_indexed(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset({opportunity.object_id})

    def test_graph_rebuildable(self, store, allocator, opportunity):
        stored = write_solution_from(store, allocator, opportunity)
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_confidence_bounded_by_opportunity(self, store, allocator, opportunity):
        """R-3: evidential_support inherited; ceiling enforced."""
        stored = write_solution_from(store, allocator, opportunity)
        ceiling = opportunity.attributes.confidence.effective_confidence
        assert stored.attributes.confidence.effective_confidence <= ceiling

    def test_confidence_inflation_rejected(self, store, allocator, opportunity):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_solution(
                make_solution(
                    allocator, opportunity.object_id,
                    problem_refs=tuple(
                        sorted(
                            store._lineage_of_type(
                                opportunity.object_id, ObjectType.PROBLEM
                            )
                        )[:1]
                    ),
                    support=0.99, assertion=0.99,
                )
            )
        assert "V5" in exc.value.failure.rule_ids

    def test_retracting_evidence_invalidates_the_solution(
        self, store, allocator, opportunity
    ):
        stored = write_solution_from(store, allocator, opportunity)
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_invalidating_the_opportunity_invalidates_the_solution(
        self, store, allocator, opportunity
    ):
        stored = write_solution_from(store, allocator, opportunity)
        store.transition(
            opportunity.object_id, ObjectStatus.INVALIDATED, "pattern withdrawn"
        )
        CascadeInvalidation(store=store).cascade(
            opportunity.object_id, ObjectStatus.INVALIDATED, "pattern withdrawn"
        )
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_cascade_invalidates_every_sibling(self, store, allocator, opportunity):
        """S-I3: siblings fall together, and not silently."""
        stored = [write_solution_from(store, allocator, opportunity) for _ in range(3)]
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert all(
            store.get(s.object_id).status is ObjectStatus.INVALIDATED
            for s in stored
        )

    def test_universal_integrity_holds(self, store, allocator, opportunity):
        write_solution_from(store, allocator, opportunity)
        assert store.verify_integrity().holds

    def test_all_six_type_verifiers_hold(self, store, allocator, opportunity):
        """Backward compatibility across every realised type."""
        write_solution_from(store, allocator, opportunity)
        assert store.evidence.integrity().verify() == ()
        assert store.facts.integrity().verify() == ()
        assert store.problems.integrity().verify() == ()
        assert store.patterns.integrity().verify() == ()
        assert store.opportunities.integrity().verify() == ()
        assert store.solutions.integrity().verify() == ()

    def test_evidence_may_never_derive_from_a_solution(
        self, store, allocator, opportunity
    ):
        """AD-05 holds at the Solution stage too."""
        from oip.evidence import Evidence, EvidenceContent, ExternalOriginError
        from tests.test_evidence import provenance

        stored = write_solution_from(store, allocator, opportunity)
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((stored.object_id, ObjectType.SOLUTION),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes, provenance=provenance(),
                content=EvidenceContent.full("text"),
            )

    def test_solution_may_address_a_problem(self):
        """R-6: ADDRESSES targets Opportunity and Problem."""
        from oip.relationships import is_legal

        assert is_legal(
            RelationshipType.ADDRESSES, ObjectType.SOLUTION, ObjectType.PROBLEM
        )
        assert is_legal(
            RelationshipType.ADDRESSES, ObjectType.SOLUTION, ObjectType.OPPORTUNITY
        )


# ===========================================================================
# Concurrency  [N-11, I5]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_sibling_writes_serialised(self, store, allocator):
        """Sibling candidates are formulated concurrently by design."""
        opportunity = write_opportunities(store, allocator, 1)[0]
        problems = tuple(
            sorted(store._lineage_of_type(opportunity.object_id, ObjectType.PROBLEM))[:1]
        )
        ceiling = opportunity.attributes.confidence.effective_confidence
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            s = make_solution(
                allocator, opportunity.object_id,
                problem_refs=problems, upstream_ceiling=ceiling,
                candidate_group=f"{opportunity.object_id}-candidates",
            )
            barrier.wait()
            try:
                written.append(store.write_solution(s).object_id)
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(written)) == 8
        assert len(store.solutions.candidate_group(
            f"{opportunity.object_id}-candidates"
        )) == 8
        assert store.verify_integrity().holds
        assert store.solutions.integrity().verify() == ()

    def test_only_one_successor_wins_a_refinement_race(
        self, store, allocator, opportunity
    ):
        from oip.identity import BranchingError

        first = write_solution_from(store, allocator, opportunity)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refined")

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
                write_solution_from(
                    store, allocator, opportunity,
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
@given(count=st.integers(min_value=1, max_value=25))
def test_any_assumption_count_at_or_above_one_accepted(count):
    """AC1 over arbitrary assumption breadth."""
    allocator = IdentityAllocator()
    assumptions = tuple(assumption(f"A{i}") for i in range(count))
    s = make_solution(allocator, assumptions=assumptions)
    assert s.assumption_count == count
    assert not sv2_assumptions_present(ctx(s)).failed


@settings(max_examples=200, deadline=None)
@given(
    criticality=st.text(max_size=20),
    testability=st.text(max_size=20),
)
def test_assumption_requires_both_fields(criticality, testability):
    """AC2 over arbitrary field text."""
    if criticality.strip() and testability.strip():
        a = assumption("A1", criticality=criticality, testability=testability)
        assert a.criticality == criticality
    else:
        with pytest.raises(AssumptionError):
            assumption("A1", criticality=criticality, testability=testability)


@settings(max_examples=200, deadline=None)
@given(group=st.text(max_size=20))
def test_candidate_group_is_always_required(group):
    """AC3 over arbitrary group identifiers."""
    allocator = IdentityAllocator()
    if group.strip():
        assert make_solution(allocator, candidate_group=group).candidate_group == group
    else:
        with pytest.raises(CandidateGroupError):
            make_solution(allocator, candidate_group=group)


@settings(max_examples=150, deadline=None)
@given(
    cited=st.integers(min_value=1, max_value=6),
    reachable=st.integers(min_value=1, max_value=6),
)
def test_sv4_fails_exactly_when_a_citation_is_unreachable(cited, reachable):
    """S-V4 over arbitrary citation/lineage combinations."""
    allocator = IdentityAllocator()
    cited_refs = tuple(f"obj-pr-{i}" for i in range(cited))
    reachable_refs = frozenset(f"obj-pr-{i}" for i in range(reachable))
    s = make_solution(allocator, problem_refs=cited_refs)
    result = sv4_problem_fit_references_lineage(
        ctx(s, lineage_problems=lambda oid: reachable_refs)
    )
    assert result.failed == (cited > reachable)


@settings(max_examples=150, deadline=None)
@given(dropped=st.integers(min_value=1, max_value=5))
def test_dropping_assumptions_always_detected_without_rationale(dropped):
    """S-I1: an unexplained drop is always visible."""
    allocator = IdentityAllocator()
    original = tuple(assumption(f"A{i}") for i in range(6))
    earlier = make_solution(allocator, assumptions=original)
    later = make_solution(allocator, assumptions=original[: 6 - dropped])
    assert len(later.retains_assumptions_of(earlier)) == dropped


@settings(max_examples=150, deadline=None)
@given(dropped=st.integers(min_value=1, max_value=5))
def test_recorded_supersessions_clear_the_drop(dropped):
    """S-I1: supersession with rationale is the sanctioned route."""
    allocator = IdentityAllocator()
    original = tuple(assumption(f"A{i}") for i in range(6))
    earlier = make_solution(allocator, assumptions=original)
    later = make_solution(
        allocator,
        assumptions=original[: 6 - dropped],
        superseded_assumptions=tuple(
            AssumptionSupersession(f"A{i}", "resolved by evidence")
            for i in range(6 - dropped, 6)
        ),
    )
    assert later.retains_assumptions_of(earlier) == ()


# ===========================================================================
# Adversarial and regression
# ===========================================================================

class TestAdversarial:
    def test_sibling_opportunity_problem_is_not_reachable(self, store, allocator):
        """N-14: an engine may not reach a sibling it did not derive from."""
        first, second = write_opportunities(store, allocator, 2)
        foreign = sorted(
            store._lineage_of_type(second.object_id, ObjectType.PROBLEM)
        )[0]
        with pytest.raises(WriteRejectedError) as exc:
            write_solution_from(store, allocator, first, problem_refs=(foreign,))
        assert "S-V4" in exc.value.failure.rule_ids

    def test_si2_survives_a_graph_rebuild(self, store, allocator, opportunity):
        """N-6: the index is disposable; verdicts must not depend on churn."""
        write_solution_from(store, allocator, opportunity)
        store.rebuild_graph()
        assert store.solutions.integrity().verify() == ()

    def test_cascade_is_not_an_assessment_change(self, store, allocator, opportunity):
        """S-I4 tracks the assessment, not the lifecycle status."""
        stored = write_solution_from(store, allocator, opportunity)
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I4"
        ]

    def test_si4_snapshot_is_not_overwritten_by_a_later_attach(
        self, store, allocator, opportunity
    ):
        """A second candidate must not launder an already-altered assessment."""
        from oip.contract import Confidence

        write_solution_from(store, allocator, opportunity)
        object.__setattr__(
            store._objects[opportunity.object_id].attributes, "confidence",
            Confidence(evidential_support=0.2, assertion_confidence=0.2,
                       effective_confidence=0.2),
        )
        write_solution_from(store, allocator, opportunity)
        assert any(
            v.constraint_id == "S-I4"
            for v in store.solutions.integrity().verify()
        )

    def test_assumptions_survive_the_store_round_trip(
        self, store, allocator, opportunity
    ):
        """The testable surface must not be lost in persistence."""
        stored = write_solution_from(
            store, allocator, opportunity,
            assumptions=(assumption("A1"), assumption("A2"), assumption("A3")),
        )
        payload = store.get_solution(stored.object_id)
        assert payload.assumption_ids == {"A1", "A2", "A3"}
        assert payload.assumption("A2").testability

    def test_superseded_assumptions_survive_the_round_trip(
        self, store, allocator, opportunity
    ):
        stored = write_solution_from(
            store, allocator, opportunity,
            superseded_assumptions=(
                AssumptionSupersession("A0", "resolved by evidence"),
            ),
        )
        assert store.get_solution(stored.object_id).withdrew("A0") is not None
        assert store.get_solution(stored.object_id).withdrew("A9") is None

    def test_constraints_survive_the_round_trip(self, store, allocator, opportunity):
        stored = write_solution_from(
            store, allocator, opportunity,
            constraints=("licensing", "operation latency"),
        )
        assert len(store.get_solution(stored.object_id).constraints) == 2


# ===========================================================================
# Residual surface
# ===========================================================================

class TestResidualSurface:
    def test_recording_skips_an_unresolvable_opportunity(self, store, allocator):
        """No stored Opportunity, no snapshot -- and no false verdict."""
        verifier = store.solutions.integrity()
        verifier.record_opportunity_assessment(make_solution(allocator))
        assert verifier.recorded_assessment_count == 0

    def test_assessment_of_a_non_opportunity_is_none(
        self, store, allocator, opportunity
    ):
        write_solution_from(store, allocator, opportunity)
        verifier = store.solutions.integrity()
        pattern_id = store.objects_of_type(ObjectType.PATTERN)[0].object_id
        assert verifier._assessment_of(pattern_id) is None
        assert verifier._assessment_of("obj-absent") is None

    def test_si2_skips_an_unindexed_solution(self, store, allocator, opportunity):
        """N-6: the index cannot answer, so no verdict is offered."""
        stored = write_solution_from(store, allocator, opportunity)
        store.graph = store.graph.__class__()
        assert not [
            v for v in store.solutions.integrity().verify()
            if v.constraint_id == "S-I2"
        ]
