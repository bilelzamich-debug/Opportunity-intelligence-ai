"""Contract tests for the Pattern object type.

Task: T01.7.4

Architecture References:
- PT-V1..PT-V6  Pattern validation rules
- PT-I1..PT-I4  Pattern integrity constraints
- S-4           Pattern sufficiency: 3 independent sources spanning >=2
- N-16          Tier 1 count; Tier 2 diversity by traversal
- N-6           Graph is a derived index, never authoritative alone
- R-1 / OQ-21   Open-ended membership; versioning churn
- R-6           DERIVES_FROM / CONSTITUENT_OF Problems
- M-13/24/25/61/66  Temporal validity, strength, taxonomy, staleness,
                    summarisation all remain OPEN

Acceptance criteria under test:
  AC1  Minimum two distinct constituents enforced
  AC2  PT-V2 rejects patterns over versions of one problem
  AC3  source_diversity and artefact_assessment required
"""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.contract import Confidence
from oip.enums import Engine, ObjectStatus, ObjectType, RelationshipType
from oip.identity import IdentityAllocator
from oip.pattern import (
    MINIMUM_CONSTITUENTS,
    PATTERN_RULES,
    ArtefactAssessment,
    ArtefactAssessmentError,
    ConstituentError,
    ConstituentRole,
    GroupingRationale,
    GroupingRationaleError,
    Pattern,
    PatternError,
    PatternIntegrity,
    PatternScope,
    PatternScopeError,
    PatternType,
    SourceDiversityError,
    ptv1_minimum_constituents,
    ptv2_constituents_are_distinct_objects,
    ptv3_rationale_references_constituents,
    ptv4_source_diversity_present,
    ptv5_artefact_assessment_reasoned,
    ptv6_decomposable,
)
from oip.store import KnowledgeStore, WriteRejectedError
from oip.support import sufficiency_threshold
from tests.conftest import T0, build_attrs
from tests.test_evidence import evidence as make_evidence
from tests.test_fact import make_fact
from tests.test_problem import basis, make_problem, write_facts

PATTERN_STATEMENT = (
    "Bulk operations across marketplace seller tooling fail silently at "
    "undocumented thresholds, with sellers discovering failures only through "
    "downstream customer impact rather than system feedback."
)
SHARED_STRUCTURE = (
    "All constituents share a silent threshold failure, absence of feedback, "
    "and delayed discovery via third parties. The shared structure is the "
    "missing feedback channel, not the specific operation."
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def rationale(*problem_refs: str, shared: str | None = None) -> GroupingRationale:
    return GroupingRationale(
        shared_structure=shared or SHARED_STRUCTURE,
        constituent_roles=tuple(
            ConstituentRole(
                problem_ref=ref,
                role=f"{ref} contributes one instance of the shared structure",
            )
            for ref in problem_refs
        ),
    )


def assessment(**overrides) -> ArtefactAssessment:
    kwargs = {
        "attributable_to_research_bias": False,
        "reasoning": (
            "Constituents derive from distinct acquisition efforts across "
            "distinct source types; no single source contributes to more than "
            "one constituent problem."
        ),
        "acquisition_efforts": ("effort-A", "effort-B"),
    }
    kwargs.update(overrides)
    return ArtefactAssessment(**kwargs)


def scope(**overrides) -> PatternScope:
    kwargs = {
        "domain": "Marketplace seller tooling",
        "population": "Segment A sellers and adjacent segments",
    }
    kwargs.update(overrides)
    return PatternScope(**kwargs)


def make_pattern(
    allocator: IdentityAllocator,
    problem_refs: tuple[str, ...] = ("obj-pr-1", "obj-pr-2"),
    *,
    constituents: tuple[str, ...] | None = None,
    source_count: int | None = None,
    upstream_ceiling: float | None = None,
    support: float = 0.62,
    assertion: float = 0.84,
    **overrides,
) -> Pattern:
    identity = overrides.pop("identity", None) or allocator.new_object()
    members = constituents if constituents is not None else problem_refs
    count = (
        source_count
        if source_count is not None
        else max(len(members), sufficiency_threshold(ObjectType.PATTERN))
    )
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.PATTERN,
        tuple((r, ObjectType.PROBLEM) for r in problem_refs),
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        source_count=count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
    )
    kwargs = {
        "attributes": attributes,
        "pattern_statement": overrides.pop("pattern_statement", PATTERN_STATEMENT),
        "constituent_problems": overrides.pop("constituent_problems", members),
        "pattern_type": overrides.pop(
            "pattern_type", PatternType.CROSS_DOMAIN_SIMILARITY
        ),
        "grouping_rationale": overrides.pop(
            "grouping_rationale", rationale(*members)
        ),
        "source_diversity": overrides.pop("source_diversity", len(members)),
        "artefact_assessment": overrides.pop("artefact_assessment", assessment()),
        "pattern_scope": overrides.pop("pattern_scope", scope()),
    }
    kwargs.update(overrides)
    return Pattern(**kwargs)


def ctx(pattern: Pattern, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": pattern.attributes, "pattern": pattern}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def write_problems(store, allocator, n: int = 2, facts_each: int = 2, **overrides):
    """Persist n Problems, each on its own distinct Facts."""
    stored = []
    for _ in range(n):
        facts = write_facts(store, allocator, facts_each)
        refs = tuple(f.object_id for f in facts)
        ceiling = min(
            f.attributes.confidence.effective_confidence for f in facts
        )
        stored.append(
            store.write_problem(
                make_problem(allocator, refs, upstream_ceiling=ceiling, **overrides)
            )
        )
    return stored


def write_pattern_from(
    store, allocator, stored_problems, predecessor_id: str | None = None, **overrides
):
    refs = tuple(p.object_id for p in stored_problems)
    ceiling = min(
        p.attributes.confidence.effective_confidence for p in stored_problems
    )
    diversity = len(store.graph.evidence_set(refs[0]) | set().union(
        *(store.graph.evidence_set(r) for r in refs)
    ))
    kwargs = {"source_diversity": diversity}
    kwargs.update(overrides)
    return store.write_pattern(
        make_pattern(allocator, refs, upstream_ceiling=ceiling, **kwargs),
        predecessor_id=predecessor_id,
    )


@pytest.fixture()
def problems(store, allocator):
    return write_problems(store, allocator, 2)


# ===========================================================================
# AC1 -- minimum two distinct constituents  [PT-V1]
# ===========================================================================

class TestMinimumConstituents:
    def test_two_constituents_accepted(self, allocator):
        assert make_pattern(allocator).constituent_count == 2

    def test_many_constituents_accepted(self, allocator):
        refs = tuple(f"obj-pr-{i}" for i in range(25))
        assert make_pattern(allocator, refs).constituent_count == 25

    def test_one_constituent_refused_at_construction(self, allocator):
        """A single-problem Pattern is a category error. [IOM section 3.4]"""
        with pytest.raises(ConstituentError) as exc:
            make_pattern(
                allocator, ("obj-pr-1",),
                grouping_rationale=rationale("obj-pr-1"),
            )
        assert "category error" in str(exc.value)

    def test_zero_constituents_refused(self, allocator):
        with pytest.raises(ConstituentError):
            make_pattern(
                allocator, ("obj-pr-1", "obj-pr-2"), constituent_problems=()
            )

    def test_minimum_matches_the_iom(self):
        assert MINIMUM_CONSTITUENTS == 2

    def test_duplicate_constituent_refused(self, allocator):
        with pytest.raises(ConstituentError) as exc:
            make_pattern(
                allocator, ("obj-pr-1",),
                constituent_problems=("obj-pr-1", "obj-pr-1"),
                grouping_rationale=rationale("obj-pr-1"),
            )
        assert "repetition" in str(exc.value)

    def test_ptv1_detects_a_stripped_membership(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern, "constituent_problems", ("obj-pr-1",))
        result = ptv1_minimum_constituents(ctx(pattern))
        assert result.failed
        assert "category error" in result.detail

    def test_s4_floor_enforced(self, allocator):
        """S-4: 3 independent sources; fewer cannot be told from coincidence."""
        pattern = make_pattern(allocator, source_count=2)
        result = ptv1_minimum_constituents(ctx(pattern))
        assert result.failed
        assert "coincidence" in result.detail

    def test_s4_floor_met(self, allocator):
        counts = {"obj-pr-1": 2, "obj-pr-2": 1}
        result = ptv1_minimum_constituents(
            ctx(make_pattern(allocator), upstream_source_count=counts.get)
        )
        assert result.outcome is RuleOutcome.PASS
        assert f"S-4 floor {sufficiency_threshold(ObjectType.PATTERN)}" in result.detail

    def test_s4_spanning_requires_two_contributing_constituents(self, allocator):
        """Three sources all beneath one constituent is not structure. [S-4]"""
        pattern = make_pattern(allocator, ("obj-pr-1", "obj-pr-2"))
        counts = {"obj-pr-1": 3, "obj-pr-2": 0}
        result = ptv1_minimum_constituents(
            ctx(pattern, upstream_source_count=counts.get)
        )
        assert result.failed
        assert "span only 1" in result.detail

    def test_s4_spanning_satisfied(self, allocator):
        pattern = make_pattern(allocator, ("obj-pr-1", "obj-pr-2"))
        counts = {"obj-pr-1": 2, "obj-pr-2": 1}
        result = ptv1_minimum_constituents(
            ctx(pattern, upstream_source_count=counts.get)
        )
        assert result.outcome is RuleOutcome.PASS
        assert "spanning 2" in result.detail

    def test_spanning_unchecked_without_a_provider(self, allocator):
        result = ptv1_minimum_constituents(ctx(make_pattern(allocator)))
        assert "spanning unchecked" in result.detail

    def test_spanning_skipped_when_constituents_unresolved(self, allocator):
        pattern = make_pattern(allocator)
        result = ptv1_minimum_constituents(
            ctx(pattern, upstream_source_count=lambda ref: None)
        )
        assert result.outcome is RuleOutcome.SKIP
        assert "PT-V6" in result.detail

    def test_store_rejects_below_the_s4_floor(self, store, allocator, problems):
        with pytest.raises(WriteRejectedError) as exc:
            write_pattern_from(store, allocator, problems, source_count=2)
        assert "PT-V1" in exc.value.failure.rule_ids

    def test_store_accepts_a_well_formed_pattern(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        assert stored.status is ObjectStatus.ACTIVE
        assert store.get_pattern(stored.object_id).constituent_count == 2


# ===========================================================================
# AC2 -- PT-V2 rejects versions of one Problem
# ===========================================================================

class TestConstituentsAreDistinctObjects:
    def test_rule_registered(self, store):
        assert "PT-V2" in store.acceptance.rule_ids

    def test_distinct_objects_pass(self, allocator):
        pattern = make_pattern(allocator)
        lineages = {"obj-pr-1": "lin-A", "obj-pr-2": "lin-B"}
        result = ptv2_constituents_are_distinct_objects(
            ctx(pattern, resolve_lineage=lineages.get)
        )
        assert result.outcome is RuleOutcome.PASS
        assert "2 distinct logical Problem(s)" in result.detail

    def test_versions_of_one_problem_rejected(self, allocator):
        """Self-corroboration from a single underlying deficiency. [PT-V2]"""
        pattern = make_pattern(allocator)
        lineages = {"obj-pr-1": "lin-A", "obj-pr-2": "lin-A"}
        result = ptv2_constituents_are_distinct_objects(
            ctx(pattern, resolve_lineage=lineages.get)
        )
        assert result.failed
        assert "self-corroboration" in result.detail
        assert "lin-A" in result.detail

    def test_partial_collision_detected_among_many(self, allocator):
        refs = tuple(f"obj-pr-{i}" for i in range(5))
        pattern = make_pattern(allocator, refs)
        lineages = {
            "obj-pr-0": "lin-A", "obj-pr-1": "lin-B", "obj-pr-2": "lin-C",
            "obj-pr-3": "lin-A", "obj-pr-4": "lin-D",
        }
        result = ptv2_constituents_are_distinct_objects(
            ctx(pattern, resolve_lineage=lineages.get)
        )
        assert result.failed
        assert "obj-pr-0" in result.detail and "obj-pr-3" in result.detail

    def test_skips_without_a_lineage_provider(self, allocator):
        result = ptv2_constituents_are_distinct_objects(ctx(make_pattern(allocator)))
        assert result.outcome is RuleOutcome.SKIP
        assert "no lineage provider" in result.detail

    def test_skips_when_constituents_unresolved(self, allocator):
        result = ptv2_constituents_are_distinct_objects(
            ctx(make_pattern(allocator), resolve_lineage=lambda ref: None)
        )
        assert result.outcome is RuleOutcome.SKIP
        assert "PT-V6" in result.detail

    def test_detects_a_smuggled_duplicate(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(
            pattern, "constituent_problems", ("obj-pr-1", "obj-pr-1")
        )
        result = ptv2_constituents_are_distinct_objects(ctx(pattern))
        assert result.failed
        assert "twice" in result.detail

    def test_store_rejects_a_pattern_over_two_versions(self, store, allocator):
        """End-to-end: supersede a Problem, then pattern over both versions."""
        first, other = write_problems(store, allocator, 2)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "reformulated")

        successor_identity = allocator.succeed(first.attributes.identity)
        facts = [
            store.get(r.object_id)
            for r in store.objects_of_type(ObjectType.FACT)[:2]
        ]
        second_version = store.write_problem(
            make_problem(
                allocator,
                tuple(f.object_id for f in facts),
                identity=successor_identity,
                upstream_ceiling=min(
                    f.attributes.confidence.effective_confidence for f in facts
                ),
            ),
            predecessor_id=first.object_id,
        )
        assert second_version.lineage_id == first.lineage_id

        with pytest.raises(WriteRejectedError) as exc:
            write_pattern_from(
                store, allocator, [first, second_version]
            )
        assert "PT-V2" in exc.value.failure.rule_ids

    def test_store_accepts_distinct_problems(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# AC3 -- source_diversity and artefact_assessment required
# ===========================================================================

class TestSourceDiversity:
    def test_required_at_construction(self, allocator):
        with pytest.raises(SourceDiversityError):
            make_pattern(allocator, source_diversity=None)

    def test_negative_rejected(self, allocator):
        with pytest.raises(SourceDiversityError):
            make_pattern(allocator, source_diversity=-1)

    def test_non_integer_rejected(self, allocator):
        with pytest.raises(SourceDiversityError):
            make_pattern(allocator, source_diversity="eleven")

    def test_boolean_is_not_a_count(self, allocator):
        """True == 1 in Python; a boolean is not a measurement."""
        with pytest.raises(SourceDiversityError):
            make_pattern(allocator, source_diversity=True)

    def test_zero_is_permitted_but_recorded(self, allocator):
        """PT-V4 requires presence, not a floor; S-4 is PT-V1's job."""
        result = ptv4_source_diversity_present(
            ctx(make_pattern(allocator, source_diversity=0))
        )
        assert result.outcome is RuleOutcome.PASS

    def test_ptv4_passes_and_cites_n16(self, allocator):
        result = ptv4_source_diversity_present(ctx(make_pattern(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "N-16 Tier 2" in result.detail

    def test_ptv4_detects_a_smuggled_negative(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern, "source_diversity", -3)
        result = ptv4_source_diversity_present(ctx(pattern))
        assert result.failed
        assert "cannot be below zero" in result.detail

    def test_ptv4_detects_a_smuggled_non_integer(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern, "source_diversity", 3.5)
        assert ptv4_source_diversity_present(ctx(pattern)).failed


class TestArtefactAssessment:
    def test_required_at_construction(self, allocator):
        with pytest.raises(ArtefactAssessmentError):
            make_pattern(allocator, artefact_assessment=None)

    def test_reasoning_required(self):
        with pytest.raises(ArtefactAssessmentError):
            ArtefactAssessment(
                attributable_to_research_bias=False, reasoning="   "
            )

    def test_reasoned_negative_verdict_passes(self, allocator):
        result = ptv5_artefact_assessment_reasoned(ctx(make_pattern(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "acquisition effort(s) cited" in result.detail

    def test_declared_artefact_rejected(self, allocator):
        """The IOM's own transitions send a judged artefact to REJECTED."""
        pattern = make_pattern(
            allocator,
            artefact_assessment=assessment(
                attributable_to_research_bias=True,
                reasoning="All constituents trace to one over-sampled forum.",
            ),
        )
        result = ptv5_artefact_assessment_reasoned(ctx(pattern))
        assert result.failed
        assert "rejected, not recorded" in result.detail

    def test_ptv5_detects_stripped_reasoning(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern.artefact_assessment, "reasoning", "")
        result = ptv5_artefact_assessment_reasoned(ctx(pattern))
        assert result.failed
        assert "defining risk" in result.detail

    def test_ptv5_detects_a_removed_assessment(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern, "artefact_assessment", None)
        result = ptv5_artefact_assessment_reasoned(ctx(pattern))
        assert result.failed
        assert "absent" in result.detail

    def test_effort_count_deduplicates(self):
        a = assessment(acquisition_efforts=("e1", "e1", "e2", "  ", ""))
        assert a.independent_effort_count == 2

    def test_store_rejects_a_declared_artefact(self, store, allocator, problems):
        with pytest.raises(WriteRejectedError) as exc:
            write_pattern_from(
                store, allocator, problems,
                artefact_assessment=assessment(
                    attributable_to_research_bias=True,
                    reasoning="single over-sampled channel",
                ),
            )
        assert "PT-V5" in exc.value.failure.rule_ids

    def test_is_artefact_property(self):
        assert assessment(attributable_to_research_bias=True, reasoning="r").is_artefact
        assert not assessment().is_artefact


# ===========================================================================
# PT-V3  grouping rationale
# ===========================================================================

class TestGroupingRationale:
    def test_required_at_construction(self, allocator):
        with pytest.raises(GroupingRationaleError):
            make_pattern(allocator, grouping_rationale=None)

    def test_shared_structure_required(self):
        with pytest.raises(GroupingRationaleError) as exc:
            GroupingRationale(
                shared_structure="  ",
                constituent_roles=(ConstituentRole("obj-pr-1", "r"),),
            )
        assert "coincidence" in str(exc.value)

    def test_roles_required(self):
        with pytest.raises(GroupingRationaleError):
            GroupingRationale(shared_structure="s", constituent_roles=())

    def test_role_requires_a_ref(self):
        with pytest.raises(GroupingRationaleError):
            ConstituentRole(problem_ref="  ", role="r")

    def test_role_requires_content(self):
        with pytest.raises(GroupingRationaleError):
            ConstituentRole(problem_ref="obj-pr-1", role="")

    def test_a_constituent_may_not_be_described_twice(self):
        with pytest.raises(GroupingRationaleError):
            GroupingRationale(
                shared_structure="s",
                constituent_roles=(
                    ConstituentRole("obj-pr-1", "a"),
                    ConstituentRole("obj-pr-1", "b"),
                ),
            )

    def test_rationale_may_not_describe_a_non_constituent(self, allocator):
        with pytest.raises(GroupingRationaleError):
            make_pattern(
                allocator, ("obj-pr-1", "obj-pr-2"),
                grouping_rationale=rationale("obj-pr-1", "obj-pr-9"),
            )

    def test_rationale_may_describe_a_subset(self, allocator):
        pattern = make_pattern(
            allocator, ("obj-pr-1", "obj-pr-2", "obj-pr-3"),
            grouping_rationale=rationale("obj-pr-1", "obj-pr-2"),
        )
        assert not pattern.describes("obj-pr-3")
        assert not ptv3_rationale_references_constituents(ctx(pattern)).failed

    def test_role_lookup(self, allocator):
        pattern = make_pattern(allocator)
        assert pattern.grouping_rationale.role_of("obj-pr-1") is not None
        assert pattern.grouping_rationale.role_of("obj-absent") is None

    def test_ptv3_detects_stripped_structure(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern.grouping_rationale, "shared_structure", "")
        result = ptv3_rationale_references_constituents(ctx(pattern))
        assert result.failed
        assert "not an argument" in result.detail

    def test_ptv3_detects_emptied_roles(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern.grouping_rationale, "constituent_roles", ())
        result = ptv3_rationale_references_constituents(ctx(pattern))
        assert result.failed
        assert "references no constituent" in result.detail

    def test_ptv3_detects_a_phantom_description(self, allocator):
        pattern = make_pattern(allocator)
        object.__setattr__(pattern, "constituent_problems", ("obj-pr-1",))
        result = ptv3_rationale_references_constituents(ctx(pattern))
        assert result.failed
        assert "obj-pr-2" in result.detail

    def test_ptv3_distinct_from_universal_explanation(self, store, allocator, problems):
        """V6 can pass while PT-V3 fails: they answer different questions."""
        from oip.acceptance import v6_explanation_references_inputs

        refs = tuple(p.object_id for p in problems)
        pattern = make_pattern(
            allocator, refs,
            upstream_ceiling=min(
                p.attributes.confidence.effective_confidence for p in problems
            ),
        )
        object.__setattr__(pattern.grouping_rationale, "shared_structure", "")
        assert not v6_explanation_references_inputs(ctx(pattern)).failed
        assert ptv3_rationale_references_constituents(ctx(pattern)).failed


# ===========================================================================
# PT-V6  decomposability
# ===========================================================================

class TestDecomposability:
    def test_resolving_constituents_pass(self, allocator):
        pattern = make_pattern(allocator)
        result = ptv6_decomposable(
            ctx(pattern, resolve_type=lambda ref: ObjectType.PROBLEM)
        )
        assert result.outcome is RuleOutcome.PASS

    def test_unresolvable_constituent_rejected(self, allocator):
        pattern = make_pattern(allocator)
        result = ptv6_decomposable(ctx(pattern, resolve_type=lambda ref: None))
        assert result.failed
        assert "cannot be decomposed" in result.detail

    def test_mistyped_constituent_rejected(self, allocator):
        pattern = make_pattern(allocator)
        result = ptv6_decomposable(
            ctx(pattern, resolve_type=lambda ref: ObjectType.FACT)
        )
        assert result.failed
        assert "not Problems" in result.detail

    def test_skips_without_a_resolver(self, allocator):
        result = ptv6_decomposable(ctx(make_pattern(allocator)))
        assert result.outcome is RuleOutcome.SKIP

    def test_store_rejects_unresolvable_constituents(self, store, allocator):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_pattern(
                make_pattern(allocator, ("obj-never-written", "obj-also-not"))
            )
        assert {"V3", "PT-V6"} & set(exc.value.failure.rule_ids)


# ===========================================================================
# Rule-set hygiene
# ===========================================================================

class TestRuleSetHygiene:
    def test_all_six_rules_registered(self, store):
        assert {f"PT-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)

    def test_rule_ids_declared_in_order(self):
        assert [r.rule_id for r in PATTERN_RULES] == [
            f"PT-V{i}" for i in range(1, 7)
        ]

    @pytest.mark.parametrize("rule", PATTERN_RULES)
    def test_every_rule_skips_non_patterns(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", PATTERN_RULES)
    def test_every_rule_skips_without_a_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PATTERN,
            (("obj-pr-1", ObjectType.PROBLEM),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Pattern payload" in result.detail

    def test_earlier_stages_unaffected(self, store, allocator):
        """One acceptance path serves all nine types. [Backward compatibility]"""
        stored = write_problems(store, allocator, 1)[0]
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# Type, authority and attributes
# ===========================================================================

class TestTypeAndAuthority:
    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PROBLEM,
            (("obj-fa-1", ObjectType.FACT),),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(PatternError):
            make_pattern(allocator, ("obj-fa-1",), attributes=attributes)

    def test_only_pattern_intelligence_may_create(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PATTERN,
            (("obj-pr-1", ObjectType.PROBLEM), ("obj-pr-2", ObjectType.PROBLEM)),
            engine=Engine.PROBLEM_INTELLIGENCE,
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(PatternError) as exc:
            make_pattern(allocator, attributes=attributes)
        assert "V7" in str(exc.value)

    def test_statement_required(self, allocator):
        with pytest.raises(PatternError):
            make_pattern(allocator, pattern_statement="  ")

    def test_pattern_type_must_be_known(self, allocator):
        with pytest.raises(PatternError):
            make_pattern(allocator, pattern_type="RECURRENCE")

    @pytest.mark.parametrize("ptype", list(PatternType))
    def test_every_iom_pattern_type_accepted(self, allocator, ptype):
        """M-24/M-25 open: no type is treated as stronger than another."""
        assert make_pattern(allocator, pattern_type=ptype).pattern_type is ptype

    def test_four_pattern_types(self):
        assert len(PatternType) == 4

    def test_constituents_must_be_problems(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.PATTERN,
            (("obj-fa-1", ObjectType.FACT), ("obj-pr-2", ObjectType.PROBLEM)),
            status=ObjectStatus.ACTIVE, status_reason=None, source_count=3,
        )
        with pytest.raises(PatternError) as exc:
            make_pattern(
                allocator, ("obj-fa-1", "obj-pr-2"), attributes=attributes
            )
        assert "derives from Problems only" in str(exc.value)

    def test_constituents_must_be_a_subset_of_derives_from(self, allocator):
        with pytest.raises(ConstituentError) as exc:
            make_pattern(
                allocator, ("obj-pr-1", "obj-pr-2"),
                constituent_problems=("obj-pr-1", "obj-pr-2", "obj-pr-unread"),
                grouping_rationale=rationale("obj-pr-1", "obj-pr-2"),
            )
        assert "aggregates the Problems it read" in str(exc.value)

    def test_optional_attributes_default_absent(self, allocator):
        pattern = make_pattern(allocator)
        assert pattern.pattern_strength is None
        assert pattern.temporal_trend is None
        assert pattern.cross_domain_instances == ()
        assert pattern.expected_persistence is None

    def test_optional_attributes_carried(self, allocator):
        pattern = make_pattern(
            allocator,
            pattern_strength=0.7,
            temporal_trend="strengthening",
            cross_domain_instances=("listings", "pricing"),
            expected_persistence="structural",
        )
        assert pattern.pattern_strength == 0.7
        assert pattern.domains_claimed == 2

    @pytest.mark.parametrize("bad", [-0.1, 1.1])
    def test_pattern_strength_range(self, allocator, bad):
        with pytest.raises(PatternError):
            make_pattern(allocator, pattern_strength=bad)

    def test_identity_is_delegated(self, allocator):
        pattern = make_pattern(allocator)
        assert pattern.object_id == pattern.attributes.object_id
        assert pattern.lineage_id == pattern.attributes.lineage_id
        assert pattern.status is pattern.attributes.status
        assert pattern.independent_source_count == 3

    def test_frozen(self, allocator):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            make_pattern(allocator).pattern_statement = "changed"


class TestPatternScope:
    def test_domain_required(self):
        with pytest.raises(PatternScopeError):
            PatternScope(domain="  ", population="p")

    def test_population_required(self):
        with pytest.raises(PatternScopeError):
            PatternScope(domain="d", population="")

    def test_required_on_the_pattern(self, allocator):
        with pytest.raises(PatternScopeError):
            make_pattern(allocator, pattern_scope=None)

    def test_period_is_optional(self, allocator):
        """M-13 open: absence of a period is not a temporal assertion."""
        assert not make_pattern(allocator).pattern_scope.claims_a_period

    def test_inverted_period_rejected(self):
        with pytest.raises(PatternScopeError) as exc:
            PatternScope(
                domain="d", population="p",
                period_start=T0 + timedelta(days=10), period_end=T0,
            )
        assert "after period_end" in str(exc.value)

    def test_mixed_awareness_period_rejected(self):
        from datetime import datetime

        with pytest.raises(PatternScopeError) as exc:
            PatternScope(
                domain="d", population="p",
                period_start=datetime(2026, 3, 1), period_end=T0,
            )
        assert "naive" in str(exc.value)

    def test_valid_period_accepted(self):
        s = PatternScope(
            domain="d", population="p",
            period_start=T0, period_end=T0 + timedelta(days=30),
        )
        assert s.claims_a_period


# ===========================================================================
# PT-I1..PT-I4  integrity
# ===========================================================================

class TestPatternIntegrity:
    def test_clean_store_holds(self, store, allocator, problems):
        write_pattern_from(store, allocator, problems)
        assert store.patterns.integrity().verify() == ()

    def test_pti1_detects_membership_falling_below_two(
        self, store, allocator, problems
    ):
        """Constituents withdrawn below two. [PT-I1, IOM transitions]

        RETRACTED rather than ARCHIVED: N-12 forbids archiving a Problem an
        ACTIVE Pattern still rests on [T01.2.5]. PT-I1's subject -- live
        membership falling below two -- is unchanged, and RETRACTED is a
        ratified ACTIVE transition that removes the constituent equally.
        """
        stored = write_pattern_from(store, allocator, problems)
        store.transition(
            problems[0].object_id, ObjectStatus.RETRACTED, "withdrawn"
        )
        violations = store.patterns.integrity().verify()
        assert any(v.constraint_id == "PT-I1" for v in violations)
        assert "no longer has" in "".join(v.detail for v in violations)
        assert store.get(stored.object_id).status is ObjectStatus.ACTIVE

    def test_pti1_ignores_a_withdrawn_pattern(self, store, allocator, problems):
        """A cascaded Pattern is not required to hold live membership."""
        stored = write_pattern_from(store, allocator, problems)
        cascade = CascadeInvalidation(store=store)
        for problem in problems:
            cascade.retract(problem.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I1"
        ]

    def test_pti1_counts_only_problems(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        pattern = store.get_pattern(stored.object_id)
        evidence_id = store.objects_of_type(ObjectType.EVIDENCE)[0].object_id
        object.__setattr__(
            pattern, "constituent_problems",
            (problems[0].object_id, evidence_id),
        )
        assert any(
            v.constraint_id == "PT-I1"
            for v in store.patterns.integrity().verify()
        )

    def test_pti2_detects_discarded_constituents(self, store, allocator):
        """Aggregation is add-only across a supersession chain. [PT-I2]"""
        problems = write_problems(store, allocator, 3)
        first = write_pattern_from(store, allocator, problems)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "narrowed")

        successor = allocator.succeed(first.attributes.identity)
        write_pattern_from(
            store, allocator, problems[:2],
            identity=successor, predecessor_id=first.object_id,
        )
        violations = store.patterns.integrity().verify()
        assert any(v.constraint_id == "PT-I2" for v in violations)
        assert "add-only" in "".join(v.detail for v in violations)

    def test_pti2_accepts_open_ended_growth(self, store, allocator):
        """Membership is open-ended; growth is the normal case. [IOM 3.4]"""
        problems = write_problems(store, allocator, 3)
        first = write_pattern_from(store, allocator, problems[:2])
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "extended")

        successor = allocator.succeed(first.attributes.identity)
        write_pattern_from(
            store, allocator, problems,
            identity=successor, predecessor_id=first.object_id,
        )
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I2"
        ]

    def test_pti3_detects_a_period_claim_beyond_constituents(
        self, store, allocator, problems
    ):
        stored = write_pattern_from(
            store, allocator, problems,
            pattern_scope=scope(
                period_start=T0 - timedelta(days=365),
                period_end=T0 + timedelta(days=365),
            ),
        )
        violations = store.patterns.integrity().verify()
        assert any(v.constraint_id == "PT-I3" for v in violations)
        joined = "".join(v.detail for v in violations)
        assert "falls before" in joined and "falls after" in joined
        assert stored.status is ObjectStatus.ACTIVE

    def test_pti3_accepts_a_period_matching_constituents(
        self, store, allocator, problems
    ):
        """The builders observe every constituent at T0, so [T0, T0] is the
        widest period the constituents can support."""
        write_pattern_from(
            store, allocator, problems,
            pattern_scope=scope(period_start=T0, period_end=T0),
        )
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I3"
        ]

    def test_pti3_ignores_an_absent_period(self, store, allocator, problems):
        """M-13 open: no period claimed is not an over-claim."""
        write_pattern_from(store, allocator, problems)
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I3"
        ]

    def test_pti3_detects_domain_over_claim(self, store, allocator, problems):
        write_pattern_from(
            store, allocator, problems,
            cross_domain_instances=("a", "b", "c", "d"),
        )
        violations = store.patterns.integrity().verify()
        assert any(
            v.constraint_id == "PT-I3" and "domain(s)" in v.detail
            for v in violations
        )

    def test_pti3_does_not_compare_scope_prose(self, store, allocator, problems):
        """S-3: undecidable textual breadth is not guessed at."""
        write_pattern_from(
            store, allocator, problems,
            pattern_scope=scope(domain="Everything, everywhere", population="All"),
        )
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I3"
        ]

    def test_pti4_detects_overstated_source_diversity(
        self, store, allocator, problems
    ):
        """Frequency inflation at the narrow waist. [PT-I4, N-16]"""
        stored = write_pattern_from(store, allocator, problems)
        pattern = store.get_pattern(stored.object_id)
        object.__setattr__(pattern, "source_diversity", 9_999)
        violations = store.patterns.integrity().verify()
        assert any(
            v.constraint_id == "PT-I4" and "overstated" in v.detail
            for v in violations
        )

    def test_pti4_detects_overstated_tier1_count(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        pattern = store.get_pattern(stored.object_id)
        object.__setattr__(pattern.attributes, "independent_source_count", 500)
        violations = store.patterns.integrity().verify()
        assert any(
            v.constraint_id == "PT-I4" and "constituents carry at most" in v.detail
            for v in violations
        )

    def test_pti4_detects_constituents_sharing_grounding(self, store, allocator):
        """Regression: the Tier 1 sum is defeated by shared grounding.

        Two distinct Problems built on the SAME two Facts sum to four
        independent sources, clearing the S-4 floor of three while only two
        Evidence objects exist. Evidence contributes exactly one independent
        source [N-16], so distinct grounding is the true bound. This is the
        narrow waist -- inflation here propagates into every Opportunity.
        """
        facts = write_facts(store, allocator, 2)
        refs = tuple(f.object_id for f in facts)
        ceiling = min(
            f.attributes.confidence.effective_confidence for f in facts
        )
        twins = [
            store.write_problem(
                make_problem(allocator, refs, upstream_ceiling=ceiling)
            )
            for _ in range(2)
        ]
        stored = write_pattern_from(store, allocator, twins)

        assert len(store.graph.evidence_set(stored.object_id)) == 2
        assert store.get_pattern(stored.object_id).independent_source_count == 3

        violations = store.patterns.integrity().verify()
        assert any(
            v.constraint_id == "PT-I4" and "share grounding" in v.detail
            for v in violations
        )

    def test_pti1_flags_a_superseded_constituent(self, store, allocator, problems):
        """SUPERSEDED does not cascade (D-01a), so PT-I1 is what surfaces it."""
        stored = write_pattern_from(store, allocator, problems)
        store.transition(
            problems[0].object_id, ObjectStatus.SUPERSEDED, "reformulated"
        )
        assert store.get(stored.object_id).status is ObjectStatus.ACTIVE
        assert store.verify_integrity().holds
        assert any(
            v.constraint_id == "PT-I1"
            for v in store.patterns.integrity().verify()
        )

    def test_pti3_reports_mixed_awareness_rather_than_crashing(
        self, store, allocator, problems
    ):
        """N-10: a malformed period produces a record, never an exception."""
        from datetime import datetime

        write_pattern_from(
            store, allocator, problems,
            pattern_scope=PatternScope(
                domain="d", population="p",
                period_start=datetime(2026, 3, 1),
                period_end=datetime(2026, 3, 2),
            ),
        )
        violations = store.patterns.integrity().verify()
        assert any(
            v.constraint_id == "PT-I3" and "naive" in v.detail
            for v in violations
        )

    def test_pti4_accepts_truthful_diversity(self, store, allocator, problems):
        write_pattern_from(store, allocator, problems)
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I4"
        ]

    def test_pti4_skipped_when_graph_cannot_answer(self, store, allocator, problems):
        """No index, no verdict. The graph is derived, never authoritative."""
        stored = write_pattern_from(store, allocator, problems)
        pattern = store.get_pattern(stored.object_id)

        class GraphlessStore:
            graph = None

        verifier = PatternIntegrity(
            pattern_of=store.patterns.get, store=GraphlessStore()
        )
        assert verifier._distinct_evidence_beneath(pattern) is None

    def test_pti4_skipped_on_unindexed_constituent(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        pattern = store.get_pattern(stored.object_id)
        verifier = store.patterns.integrity()
        assert verifier._distinct_evidence_beneath(pattern) == 4
        object.__setattr__(pattern, "constituent_problems", ("obj-unindexed",))
        assert verifier._distinct_evidence_beneath(pattern) is None

    def test_pti4_silent_when_no_constituent_resolves(
        self, store, allocator, problems
    ):
        """PT-I1 owns broken membership; PT-I4 must not double-report."""
        write_pattern_from(store, allocator, problems)
        for p in problems:
            del store._objects[p.object_id]
        violations = store.patterns.integrity().verify()
        assert not [v for v in violations if v.constraint_id == "PT-I4"]

    def test_unregistered_patterns_are_skipped(self, store, allocator):
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.patterns.integrity().verify() == ()

    def test_pti3_skips_an_unclaimed_period_bound(self, store, allocator, problems):
        """Only the bound actually claimed is compared. [M-13 open]"""
        write_pattern_from(
            store, allocator, problems,
            pattern_scope=scope(period_start=T0),
        )
        assert not [
            v for v in store.patterns.integrity().verify()
            if v.constraint_id == "PT-I3"
        ]

    def test_pti3_skips_problem_domains_without_a_registry(
        self, store, allocator, problems
    ):
        """No Problem payload, no domain verdict. [N-6]"""
        stored = write_pattern_from(store, allocator, problems)
        pattern = store.get_pattern(stored.object_id)

        class RegistrylessStore:
            problems = None

        verifier = PatternIntegrity(
            pattern_of=store.patterns.get, store=RegistrylessStore()
        )
        assert verifier._problem_payload(problems[0].object_id) is None

    def test_declared_artefact_property_exposed(self, allocator):
        assert not make_pattern(allocator).is_declared_artefact
        assert make_pattern(
            allocator,
            artefact_assessment=assessment(
                attributable_to_research_bias=True, reasoning="one channel"
            ),
        ).is_declared_artefact

    def test_verifier_constructible_standalone(self, store, allocator, problems):
        write_pattern_from(store, allocator, problems)
        verifier = PatternIntegrity(pattern_of=store.patterns.get, store=store)
        assert verifier.verify() == ()


# ===========================================================================
# Store integration
# ===========================================================================

class TestStoreIntegration:
    def test_payload_retrievable(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        assert store.get_pattern(stored.object_id) is not None

    def test_unknown_payload_is_none(self, store):
        assert store.get_pattern("obj-absent") is None

    def test_registry_counts_and_memoises(self, store, allocator, problems):
        write_pattern_from(store, allocator, problems)
        assert len(store.patterns) == 1
        assert store.patterns is store.patterns

    def test_active_patterns_exclude_withdrawn(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        assert len(store.patterns.active_patterns()) == 1
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.patterns.active_patterns() == ()

    def test_containing_locates_patterns(self, store, allocator, problems):
        write_pattern_from(store, allocator, problems)
        assert len(store.patterns.containing(problems[0].object_id)) == 1
        assert store.patterns.containing("obj-absent") == ()

    def test_rejected_write_leaves_no_payload(self, store, allocator, problems):
        before = len(store.patterns)
        with pytest.raises(WriteRejectedError):
            write_pattern_from(store, allocator, problems, source_count=1)
        assert len(store.patterns) == before

    def test_rejected_write_records_a_failure(self, store, allocator, problems):
        with pytest.raises(WriteRejectedError):
            write_pattern_from(store, allocator, problems, source_count=1)
        assert store.failure_records[-1].object_type is ObjectType.PATTERN

    def test_derivation_from_a_rejected_problem_refused(self, store, allocator):
        """I8: rejected knowledge must never re-enter."""
        problems = write_problems(store, allocator, 2)
        store.transition(problems[0].object_id, ObjectStatus.REJECTED, "declined")
        with pytest.raises(WriteRejectedError) as exc:
            write_pattern_from(store, allocator, problems)
        assert "I8" in exc.value.failure.rule_ids

    def test_supersession_accepted(self, store, allocator, problems):
        first = write_pattern_from(store, allocator, problems)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "restated")
        successor = allocator.succeed(first.attributes.identity)
        second = write_pattern_from(
            store, allocator, problems,
            identity=successor, predecessor_id=first.object_id,
        )
        assert second.attributes.version == 2
        assert second.lineage_id == first.lineage_id

    def test_resolve_lineage_exposed(self, store, allocator, problems):
        assert store.resolve_lineage(problems[0].object_id) == problems[0].lineage_id
        assert store.resolve_lineage("obj-absent") is None

    def test_upstream_source_count_exposed(self, store, allocator, problems):
        assert store._upstream_source_count(problems[0].object_id) == 2
        assert store._upstream_source_count("obj-absent") is None


# ===========================================================================
# Lineage, graph, cascade, confidence
# ===========================================================================

class TestPipelineIntegration:
    def test_pattern_reaches_evidence_at_depth_three(
        self, store, allocator, problems
    ):
        stored = write_pattern_from(store, allocator, problems)
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.depth_to_evidence(stored.object_id) == 3

    def test_evidence_set_spans_all_constituents(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        assert len(store.graph.evidence_set(stored.object_id)) == 4

    def test_lineage_edges_indexed(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset(p.object_id for p in problems)

    def test_graph_rebuildable(self, store, allocator, problems):
        stored = write_pattern_from(store, allocator, problems)
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_confidence_bounded_by_weakest_constituent(self, store, allocator):
        problems = write_problems(store, allocator, 2)
        weak = min(
            p.attributes.confidence.effective_confidence for p in problems
        )
        stored = write_pattern_from(store, allocator, problems)
        assert stored.attributes.confidence.effective_confidence <= weak

    def test_confidence_inflation_rejected(self, store, allocator, problems):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_pattern(
                make_pattern(
                    allocator,
                    tuple(p.object_id for p in problems),
                    support=0.99, assertion=0.99,
                )
            )
        assert "V5" in exc.value.failure.rule_ids

    def test_retracting_evidence_invalidates_the_pattern(
        self, store, allocator, problems
    ):
        stored = write_pattern_from(store, allocator, problems)
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_invalidating_a_problem_invalidates_the_pattern(
        self, store, allocator, problems
    ):
        stored = write_pattern_from(store, allocator, problems)
        cascade = CascadeInvalidation(store=store)
        for problem in problems:
            store.transition(
                problem.object_id, ObjectStatus.INVALIDATED, "support withdrawn"
            )
            cascade.cascade(
                problem.object_id, ObjectStatus.INVALIDATED, "support withdrawn"
            )
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_universal_integrity_still_holds(self, store, allocator, problems):
        write_pattern_from(store, allocator, problems)
        assert store.verify_integrity().holds

    def test_all_type_verifiers_hold_together(self, store, allocator, problems):
        """Backward compatibility: earlier stages remain clean."""
        write_pattern_from(store, allocator, problems)
        assert store.evidence.integrity().verify() == ()
        assert store.facts.integrity().verify() == ()
        assert store.problems.integrity().verify() == ()
        assert store.patterns.integrity().verify() == ()

    def test_evidence_may_never_derive_from_a_pattern(
        self, store, allocator, problems
    ):
        """AD-05: ground truth protection holds at the Pattern stage too."""
        from oip.evidence import Evidence, EvidenceContent, ExternalOriginError
        from tests.test_evidence import provenance

        stored = write_pattern_from(store, allocator, problems)
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((stored.object_id, ObjectType.PATTERN),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes,
                provenance=provenance(),
                content=EvidenceContent.full("text"),
            )

    def test_pattern_to_pattern_derivation_refused(self, store, allocator, problems):
        """OQ-17 open: v1's flat model is preserved, no hierarchy. [R-6]"""
        from oip.relationships import IllegalRelationshipError, Relationship

        stored = write_pattern_from(store, allocator, problems)
        with pytest.raises(IllegalRelationshipError):
            Relationship(
                relationship_type=RelationshipType.DERIVES_FROM,
                from_object_id="obj-pt-child",
                from_type=ObjectType.PATTERN,
                to_object_id=stored.object_id,
                to_type=ObjectType.PATTERN,
                asserted_by_engine=Engine.PATTERN_INTELLIGENCE,
                asserted_at=T0,
            )


# ===========================================================================
# Concurrency  [N-11, I5]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_pattern_writes_are_serialised(self, store, allocator):
        problems = write_problems(store, allocator, 2)
        refs = tuple(p.object_id for p in problems)
        ceiling = min(
            p.attributes.confidence.effective_confidence for p in problems
        )
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            pattern = make_pattern(allocator, refs, upstream_ceiling=ceiling)
            barrier.wait()
            try:
                written.append(store.write_pattern(pattern).object_id)
            except Exception as exc:  # pragma: no cover - failure diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(written)) == 8
        assert len(store.patterns) == 8
        assert store.verify_integrity().holds

    def test_only_one_successor_wins_a_membership_race(
        self, store, allocator, problems
    ):
        """Open-ended membership means concurrent additions are expected."""
        from oip.identity import BranchingError

        first = write_pattern_from(store, allocator, problems)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "extended")

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
                write_pattern_from(
                    store, allocator, problems,
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
@given(count=st.integers(min_value=2, max_value=30))
def test_any_membership_size_at_or_above_two_accepted(count):
    """AC1 over arbitrary membership breadth."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-pr-{i}" for i in range(count))
    pattern = make_pattern(allocator, refs)
    assert pattern.constituent_count == count
    assert not ptv1_minimum_constituents(ctx(pattern)).failed


@settings(max_examples=200, deadline=None)
@given(count=st.integers(min_value=0, max_value=1))
def test_membership_below_two_always_refused(count):
    """AC1: the floor is structural, never advisory."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-pr-{i}" for i in range(count)) or ("obj-pr-0",)
    with pytest.raises(ConstituentError):
        make_pattern(
            allocator, refs,
            constituent_problems=tuple(f"obj-pr-{i}" for i in range(count)),
            grouping_rationale=rationale(*refs),
        )


@settings(max_examples=200, deadline=None)
@given(declared=st.integers(min_value=0, max_value=12))
def test_s4_floor_is_the_gate_on_source_count(declared):
    """PT-V1 fails below the S-4 floor and passes at or above it."""
    allocator = IdentityAllocator()
    refs = ("obj-pr-1", "obj-pr-2", "obj-pr-3")
    pattern = make_pattern(allocator, refs, source_count=declared)
    result = ptv1_minimum_constituents(ctx(pattern))
    assert result.failed == (declared < sufficiency_threshold(ObjectType.PATTERN))


@settings(max_examples=200, deadline=None)
@given(
    lineage_ids=st.lists(
        st.sampled_from(["lin-A", "lin-B", "lin-C"]), min_size=2, max_size=6
    )
)
def test_ptv2_fails_exactly_when_a_lineage_repeats(lineage_ids):
    """AC2 over arbitrary lineage assignments."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-pr-{i}" for i in range(len(lineage_ids)))
    pattern = make_pattern(allocator, refs)
    mapping = dict(zip(refs, lineage_ids))
    result = ptv2_constituents_are_distinct_objects(
        ctx(pattern, resolve_lineage=mapping.get)
    )
    assert result.failed == (len(set(lineage_ids)) < len(lineage_ids))


@settings(max_examples=200, deadline=None)
@given(diversity=st.integers(min_value=-50, max_value=5_000))
def test_source_diversity_accepts_exactly_the_non_negative(diversity):
    """AC3 over arbitrary declared diversity."""
    allocator = IdentityAllocator()
    if diversity < 0:
        with pytest.raises(SourceDiversityError):
            make_pattern(allocator, source_diversity=diversity)
    else:
        pattern = make_pattern(allocator, source_diversity=diversity)
        assert not ptv4_source_diversity_present(ctx(pattern)).failed


@settings(max_examples=200, deadline=None)
@given(is_artefact=st.booleans(), reasoning=st.text(max_size=40))
def test_artefact_assessment_gate(is_artefact, reasoning):
    """AC3: unreasoned or self-declared artefacts never pass."""
    allocator = IdentityAllocator()
    if not reasoning.strip():
        with pytest.raises(ArtefactAssessmentError):
            ArtefactAssessment(
                attributable_to_research_bias=is_artefact, reasoning=reasoning
            )
        return
    pattern = make_pattern(
        allocator,
        artefact_assessment=ArtefactAssessment(
            attributable_to_research_bias=is_artefact, reasoning=reasoning
        ),
    )
    assert ptv5_artefact_assessment_reasoned(ctx(pattern)).failed == is_artefact


@settings(max_examples=150, deadline=None)
@given(
    described=st.integers(min_value=1, max_value=6),
    members=st.integers(min_value=2, max_value=6),
)
def test_rationale_may_never_describe_beyond_membership(described, members):
    """PT-V3 over arbitrary description/membership combinations."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-pr-{i}" for i in range(members))
    described_refs = tuple(f"obj-pr-{i}" for i in range(described))
    if described <= members:
        pattern = make_pattern(
            allocator, refs, grouping_rationale=rationale(*described_refs)
        )
        assert not ptv3_rationale_references_constituents(ctx(pattern)).failed
    else:
        with pytest.raises(GroupingRationaleError):
            make_pattern(
                allocator, refs, grouping_rationale=rationale(*described_refs)
            )


@settings(max_examples=150, deadline=None)
@given(additions=st.integers(min_value=1, max_value=10))
def test_membership_growth_is_monotonic(additions):
    """PT-I2: aggregation is add-only across versions. [R-1]"""
    allocator = IdentityAllocator()
    refs = ["obj-pr-0", "obj-pr-1"]
    previous = make_pattern(allocator, tuple(refs))
    for i in range(2, additions + 2):
        refs.append(f"obj-pr-{i}")
        current = make_pattern(allocator, tuple(refs))
        assert current.retains_constituents_of(previous)
        previous = current
    assert previous.constituent_count == additions + 2
