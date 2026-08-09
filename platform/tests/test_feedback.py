"""Contract tests for the Feedback Record object type.

Task: T01.7.9

Architecture References:
- FR-V1..FR-V6  Feedback Record validation rules
- FR-I1..FR-I4  Feedback Record integrity constraints
- R-7           Ninth Intelligence Object, closes C-03 [escalation]
- R-8           Behavioural loop closure; lineage graph stays acyclic
- AD-05         Learning Signal form; never becomes Evidence
- R-6           INFORMS targets engines, never objects; outside lineage
- S-4           2 Execution Records minimum (FR-V4)
- C-02          Execution Records uncreatable -- inherited blocker
- M-02          Learning target vocabulary OPEN and BLOCKING
- M-04          No success measure; observed_effect unassessable
- M-70/OQ-05/OQ-24  Instability guard, approval, application all OPEN

Acceptance criteria under test:
  AC1  FR-V6 restricts derivation to Execution Records only
  AC2  FR-I2 prevents becoming Evidence
  AC3  reversal_procedure required
"""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.enums import CREATE_AUTHORITY, Engine, ObjectStatus, ObjectType, RelationshipType
from oip.feedback import (
    FEEDBACK_RULES,
    MINIMUM_MOTIVATING_RECORDS,
    ChangeTargetError,
    DriftSummary,
    FeedbackIntegrity,
    FeedbackRecord,
    FeedbackRecordError,
    InformsError,
    MotivatingRecordError,
    PatternEvidence,
    PatternEvidenceError,
    ReversalProcedure,
    ReversalProcedureError,
    frv1_motivating_records_resolve,
    frv2_change_target_present,
    frv3_reversal_actionable,
    frv4_pattern_beyond_one_outcome,
    frv5_informs_specific_engines,
    frv6_derives_only_from_execution_records,
)
from oip.identity import IdentityAllocator
from oip.lineage import Lineage
from oip.relationships import EngineInforms, LINEAGE_RELATIONSHIPS
from oip.store import KnowledgeStore, WriteRejectedError
from oip.support import sufficiency_threshold
from tests.conftest import T0, build_attrs
from tests.test_execution import (
    force_persist,
    record_for,
    solution_and_opportunity,
)

APPLIED_AT = T0 + timedelta(days=200)
LESSON = (
    "Opportunities whose value depends on a behavioural response from an "
    "already-overloaded population have been systematically over-assessed."
)
CHANGE_TARGET = "Opportunity Intelligence assertion_confidence calibration"


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def reversal(**overrides) -> ReversalProcedure:
    kwargs = {
        "steps": (
            "Restore prior calibration.",
            "Rescore affected opportunities under the prior model version.",
        ),
        "restores_to": "score_model_version prior to this lesson",
    }
    kwargs.update(overrides)
    return ReversalProcedure(**kwargs)


def pattern(*refs: str, **overrides) -> PatternEvidence:
    kwargs = {
        "observed_across": refs or ("obj-xr-1", "obj-xr-2"),
        "distinguishing_reasoning": (
            "The same divergence appears across two distinct opportunity "
            "domains, which distinguishes it from a domain-specific effect."
        ),
    }
    kwargs.update(overrides)
    return PatternEvidence(**kwargs)


def informs_for(object_id: str, *engines: Engine) -> tuple[EngineInforms, ...]:
    targets = engines or (Engine.OPPORTUNITY_INTELLIGENCE,)
    return tuple(
        EngineInforms(
            from_object_id=object_id,
            informs_engine=engine,
            asserted_by_engine=Engine.FEEDBACK,
            asserted_at=T0,
        )
        for engine in targets
    )


def make_feedback(
    allocator: IdentityAllocator,
    execution_refs: tuple[str, ...] = ("obj-xr-1", "obj-xr-2"),
    *,
    motivating: tuple[str, ...] | None = None,
    engines: tuple[Engine, ...] = (Engine.OPPORTUNITY_INTELLIGENCE,),
    source_count: int = 2,
    upstream_ceiling: float | None = None,
    support: float = 0.51,
    assertion: float = 0.44,
    status: ObjectStatus = ObjectStatus.ACTIVE,
    status_reason: str | None = None,
    upstream_types: tuple[ObjectType, ...] | None = None,
    **overrides,
) -> FeedbackRecord:
    identity = overrides.pop("identity", None) or allocator.new_object()
    records = motivating if motivating is not None else execution_refs
    types = upstream_types or tuple(
        ObjectType.EXECUTION_RECORD for _ in execution_refs
    )
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.FEEDBACK_RECORD,
        tuple(zip(execution_refs, types)),
        status=status,
        status_reason=status_reason,
        source_count=source_count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
    )
    kwargs = {
        "attributes": attributes,
        "motivating_records": records,
        "lesson_statement": overrides.pop("lesson_statement", LESSON),
        "change_target": overrides.pop("change_target", CHANGE_TARGET),
        "change_description": overrides.pop(
            "change_description",
            "Reduce assertion_confidence for behaviour-dependent value.",
        ),
        "reversal_procedure": overrides.pop("reversal_procedure", reversal()),
        "informs": overrides.pop(
            "informs", informs_for(attributes.object_id, *engines)
        ),
        "applied_at": overrides.pop("applied_at", APPLIED_AT),
        # Lazily defaulted: pattern(*records) would otherwise be evaluated
        # even when overridden, and raises on deliberately duplicated input.
        "evidence_of_pattern": (
            overrides.pop("evidence_of_pattern")
            if "evidence_of_pattern" in overrides
            else pattern(*records)
        ),
    }
    kwargs.update(overrides)
    return FeedbackRecord(**kwargs)


def ctx(record: FeedbackRecord, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": record.attributes, "feedback_record": record}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def outcomes(store, allocator, n: int = 2):
    """Force-persist n Execution Records. [C-02 blocks the sanctioned path]"""
    solution, opportunity = solution_and_opportunity(store, allocator)
    return [
        force_persist(store, record_for(store, allocator, solution, opportunity))
        for _ in range(n)
    ]


def feedback_for(store, allocator, stored_outcomes, **overrides):
    refs = tuple(o.object_id for o in stored_outcomes)
    kwargs = {
        "upstream_ceiling": min(
            o.attributes.confidence.effective_confidence for o in stored_outcomes
        ),
    }
    kwargs.update(overrides)
    return make_feedback(allocator, refs, **kwargs)


def evaluate(store, record, predecessor_id=None):
    """Run acceptance directly; C-02 blocks the outcome stage below."""
    lineage = Lineage(
        object_id=record.attributes.object_id,
        object_type=ObjectType.FEEDBACK_RECORD,
        references=tuple(record.attributes.derives_from),
    )
    return store._evaluate(
        record.attributes, lineage, predecessor_id, feedback_record=record
    )


@pytest.fixture()
def motivating(store, allocator):
    return outcomes(store, allocator, 2)


# ===========================================================================
# AC1 -- FR-V6 restricts derivation to Execution Records  [FR-V6]
# ===========================================================================

class TestDerivationRestriction:
    """Learning comes from OUTCOMES, never the platform's own inferences."""

    def test_execution_records_accepted(self, allocator):
        assert make_feedback(allocator).motivating_count == 2

    @pytest.mark.parametrize(
        "wrong_type",
        [t for t in ObjectType if t is not ObjectType.EXECUTION_RECORD],
    )
    def test_every_other_object_type_refused(self, allocator, wrong_type):
        with pytest.raises(MotivatingRecordError) as exc:
            make_feedback(
                allocator, ("obj-a", "obj-b"),
                upstream_types=(wrong_type, ObjectType.EXECUTION_RECORD),
            )
        assert "Execution Records only" in str(exc.value)

    def test_refusal_names_the_self_reinforcement_failure(self, allocator):
        with pytest.raises(MotivatingRecordError) as exc:
            make_feedback(
                allocator, ("obj-a", "obj-b"),
                upstream_types=(ObjectType.OPPORTUNITY, ObjectType.EXECUTION_RECORD),
            )
        assert "learning from its own conclusions" in str(exc.value)

    def test_frv6_detects_a_smuggled_declaration(self, allocator):
        from oip.contract import LineageRef

        record = make_feedback(allocator)
        object.__setattr__(
            record.attributes, "derives_from",
            record.attributes.derives_from
            + (LineageRef("obj-op-9", ObjectType.OPPORTUNITY),),
        )
        result = frv6_derives_only_from_execution_records(ctx(record))
        assert result.failed
        assert "learning from its own conclusions" in result.detail

    def test_frv6_detects_a_reference_resolving_to_another_type(self, allocator):
        """Declared correctly but resolves to something else."""
        record = make_feedback(allocator)
        result = frv6_derives_only_from_execution_records(
            ctx(record, resolve_type=lambda oid: ObjectType.SOLUTION)
        )
        assert result.failed
        assert "resolves to non-outcomes" in result.detail

    def test_frv6_passes_when_all_resolve_as_outcomes(self, allocator):
        result = frv6_derives_only_from_execution_records(
            ctx(
                make_feedback(allocator),
                resolve_type=lambda oid: ObjectType.EXECUTION_RECORD,
            )
        )
        assert result.outcome is RuleOutcome.PASS

    def test_frv6_skips_without_a_resolver(self, allocator):
        result = frv6_derives_only_from_execution_records(
            ctx(make_feedback(allocator))
        )
        assert result.outcome is RuleOutcome.SKIP

    def test_store_rejects_derivation_from_a_solution(self, store, allocator):
        """End-to-end: a real Solution cannot motivate a lesson.

        Declared as an Execution Record but resolving to a Solution -- the
        misdeclaration route, which FR-V6's resolver half exists to close.
        """
        solution, _ = solution_and_opportunity(store, allocator)
        stored_outcomes = outcomes(store, allocator, 1)
        record = make_feedback(
            allocator,
            (stored_outcomes[0].object_id, solution.object_id),
            upstream_types=(
                ObjectType.EXECUTION_RECORD, ObjectType.EXECUTION_RECORD,
            ),
            upstream_ceiling=0.2,
        )
        result = frv6_derives_only_from_execution_records(
            ctx(record, resolve_type=store.resolve_type)
        )
        assert result.failed
        assert "resolves to non-outcomes" in result.detail
        assert "Solution" in result.detail


# ===========================================================================
# AC2 -- FR-I2 prevents becoming Evidence  [AD-05, C-04, R-8]
# ===========================================================================

class TestNeverBecomesEvidence:
    """The enforcement point for loop closure."""

    def test_evidence_may_not_derive_from_a_feedback_record(
        self, store, allocator, motivating
    ):
        from oip.evidence import Evidence, EvidenceContent, ExternalOriginError
        from tests.test_evidence import provenance

        record = feedback_for(store, allocator, motivating)
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((record.object_id, ObjectType.FEEDBACK_RECORD),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes, provenance=provenance(),
                content=EvidenceContent.full("lesson text"),
            )

    def test_fri2_detects_evidence_derived_from_feedback(
        self, store, allocator, motivating
    ):
        """The direct C-04 path: a platform artefact becomes grounding."""
        from oip.contract import LineageRef
        from oip.store import StoredObject

        record = feedback_for(store, allocator, motivating)
        force_feedback(store, record)

        identity = allocator.new_object()
        attributes = build_attrs(
            identity, ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        object.__setattr__(
            attributes, "derives_from",
            (LineageRef(record.object_id, ObjectType.FEEDBACK_RECORD),),
        )
        lineage = Lineage(
            object_id=identity.object_id, object_type=ObjectType.EVIDENCE,
            references=(),
        )
        store._objects[identity.object_id] = StoredObject(
            attributes=attributes, lineage=lineage
        )
        violations = store.feedback.integrity().verify()
        assert any(v.constraint_id == "FR-I2" for v in violations)
        assert "become grounding" in "".join(v.detail for v in violations)

    def test_fri2_detects_any_object_deriving_from_feedback(
        self, store, allocator, motivating
    ):
        """A Feedback Record is a lineage leaf. [R-8]"""
        from oip.contract import LineageRef
        from oip.store import StoredObject

        record = feedback_for(store, allocator, motivating)
        force_feedback(store, record)

        identity = allocator.new_object()
        attributes = build_attrs(
            identity, ObjectType.FACT,
            (("obj-ev-x", ObjectType.EVIDENCE),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        object.__setattr__(
            attributes, "derives_from",
            (LineageRef(record.object_id, ObjectType.FEEDBACK_RECORD),),
        )
        store._objects[identity.object_id] = StoredObject(
            attributes=attributes,
            lineage=Lineage(
                object_id=identity.object_id, object_type=ObjectType.FACT,
                references=(
                    LineageRef(record.object_id, ObjectType.FEEDBACK_RECORD),
                ),
            ),
        )
        violations = store.feedback.integrity().verify()
        assert any(
            v.constraint_id == "FR-I2" and "never enters the lineage graph" in v.detail
            for v in violations
        )

    def test_fri2_clean_when_feedback_is_a_leaf(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert not [
            v for v in store.feedback.integrity().verify()
            if v.constraint_id == "FR-I2"
        ]

    def test_fri2_silent_with_no_feedback_records(self, store, allocator):
        assert store.feedback.integrity().verify() == ()

    def test_feedback_to_evidence_edge_is_illegal_in_the_taxonomy(self):
        """AD-05 enforced at the relationship layer too."""
        from oip.relationships import is_legal

        assert not is_legal(
            RelationshipType.DERIVES_FROM,
            ObjectType.EVIDENCE, ObjectType.FEEDBACK_RECORD,
        )

    def test_lineage_graph_stays_acyclic(self, store, allocator, motivating):
        """R-8: behavioural loop closure keeps the graph acyclic."""
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert store.graph.is_acyclic()


# ===========================================================================
# AC3 -- reversal_procedure required  [FR-V3, FR-I1]
# ===========================================================================

class TestReversalRequired:
    def test_required_at_construction(self, allocator):
        with pytest.raises(ReversalProcedureError):
            make_feedback(allocator, reversal_procedure=None)

    def test_steps_required(self):
        with pytest.raises(ReversalProcedureError) as exc:
            ReversalProcedure(steps=(), restores_to="prior state")
        assert "unrecoverable learning" in str(exc.value)

    def test_empty_step_refused(self):
        with pytest.raises(ReversalProcedureError):
            ReversalProcedure(steps=("  ",), restores_to="prior state")

    def test_restore_point_required(self):
        with pytest.raises(ReversalProcedureError) as exc:
            ReversalProcedure(steps=("undo",), restores_to="")
        assert "not a recovery path" in str(exc.value)

    def test_frv3_passes_when_actionable(self, allocator):
        result = frv3_reversal_actionable(ctx(make_feedback(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "efficacy unverified" in result.detail

    def test_frv3_detects_stripped_steps(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record.reversal_procedure, "steps", ())
        result = frv3_reversal_actionable(ctx(record))
        assert result.failed
        assert "no recovery from a bad lesson" in result.detail

    def test_frv3_detects_a_stripped_restore_point(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record.reversal_procedure, "restores_to", " ")
        assert frv3_reversal_actionable(ctx(record)).failed

    def test_frv3_detects_a_removed_procedure(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "reversal_procedure", None)
        result = frv3_reversal_actionable(ctx(record))
        assert result.failed
        assert "absent" in result.detail

    def test_is_reversible_property(self, allocator):
        assert make_feedback(allocator).is_reversible

    def test_store_rejects_an_irreversible_lesson(self, store, allocator, motivating):
        record = feedback_for(store, allocator, motivating)
        object.__setattr__(record.reversal_procedure, "steps", ())
        result = evaluate(store, record)
        assert "FR-V3" in [r.rule_id for r in result.results if r.failed]


# ===========================================================================
# FR-V1  motivating records
# ===========================================================================

class TestMotivatingRecords:
    def test_required_at_construction(self, allocator):
        with pytest.raises(MotivatingRecordError):
            make_feedback(allocator, motivating=())

    def test_duplicates_refused(self, allocator):
        """Refused at the record level, given valid pattern evidence."""
        with pytest.raises(MotivatingRecordError) as exc:
            make_feedback(
                allocator, ("obj-xr-1", "obj-xr-2"),
                motivating=("obj-xr-1", "obj-xr-1"),
                evidence_of_pattern=PatternEvidence(
                    ("obj-xr-1", "obj-xr-2"), "consistent across both"
                ),
            )
        assert "repetition" in str(exc.value)

    def test_duplicates_also_refused_by_pattern_evidence(self):
        """Defence in depth: the same repetition is caught earlier too."""
        with pytest.raises(PatternEvidenceError):
            pattern("obj-xr-1", "obj-xr-1")

    def test_must_be_in_derives_from(self, allocator):
        with pytest.raises(MotivatingRecordError):
            make_feedback(
                allocator, ("obj-xr-1", "obj-xr-2"),
                motivating=("obj-xr-1", "obj-xr-unread"),
                evidence_of_pattern=pattern("obj-xr-1"),
            )

    def test_frv1_passes_when_resolvable(self, allocator):
        result = frv1_motivating_records_resolve(
            ctx(
                make_feedback(allocator),
                resolve_type=lambda oid: ObjectType.EXECUTION_RECORD,
            )
        )
        assert result.outcome is RuleOutcome.PASS

    def test_frv1_reports_the_inherited_blocker(self, allocator):
        """C-02 leaves Execution Records uncreatable."""
        result = frv1_motivating_records_resolve(
            ctx(make_feedback(allocator), resolve_type=lambda oid: None)
        )
        assert result.failed
        assert "C-02" in result.detail

    def test_frv1_detects_a_non_outcome(self, allocator):
        result = frv1_motivating_records_resolve(
            ctx(make_feedback(allocator), resolve_type=lambda oid: ObjectType.SOLUTION)
        )
        assert result.failed
        assert "not outcomes" in result.detail

    def test_frv1_detects_stripped_records(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "motivating_records", ())
        assert frv1_motivating_records_resolve(ctx(record)).failed

    def test_frv1_skips_without_a_resolver(self, allocator):
        assert frv1_motivating_records_resolve(
            ctx(make_feedback(allocator))
        ).outcome is RuleOutcome.SKIP


# ===========================================================================
# FR-V2  change target  [M-02 blocking]
# ===========================================================================

class TestChangeTarget:
    def test_required_at_construction(self, allocator):
        with pytest.raises(ChangeTargetError) as exc:
            make_feedback(allocator, change_target="  ")
        assert "M-02" in str(exc.value)

    def test_no_op_feedback_named_in_the_refusal(self, allocator):
        with pytest.raises(ChangeTargetError) as exc:
            make_feedback(allocator, change_target="")
        assert "loop decorative" in str(exc.value)

    def test_change_description_required(self, allocator):
        with pytest.raises(FeedbackRecordError):
            make_feedback(allocator, change_description="")

    def test_frv2_passes_and_records_the_blocking_marker(self, allocator):
        result = frv2_change_target_present(ctx(make_feedback(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "M-02 open, blocking" in result.detail

    @pytest.mark.parametrize(
        "target",
        ["scoring weights", "extraction criteria", "source trust",
         "validation thresholds", "pattern definitions", "something else"],
    )
    def test_no_vocabulary_invented(self, allocator, target):
        """M-02 must stay open: the IOM's list is illustrative, not closed."""
        record = make_feedback(allocator, change_target=target)
        assert not frv2_change_target_present(ctx(record)).failed

    def test_frv2_detects_a_stripped_target(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "change_target", "")
        result = frv2_change_target_present(ctx(record))
        assert result.failed
        assert "no-op feedback" in result.detail

    def test_frv2_detects_a_stripped_description(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "change_description", "  ")
        result = frv2_change_target_present(ctx(record))
        assert result.failed
        assert "change itself is unrecorded" in result.detail


# ===========================================================================
# FR-V4  pattern beyond one outcome  [S-4]
# ===========================================================================

class TestPatternEvidence:
    def test_s4_threshold_is_two(self):
        assert sufficiency_threshold(ObjectType.FEEDBACK_RECORD) == 2
        assert MINIMUM_MOTIVATING_RECORDS == 2

    def test_single_outcome_fails(self, allocator):
        """A single unfavourable outcome is not a lesson."""
        record = make_feedback(
            allocator, ("obj-xr-1",),
            evidence_of_pattern=pattern("obj-xr-1"),
        )
        result = frv4_pattern_beyond_one_outcome(ctx(record))
        assert result.failed
        assert "not a lesson" in result.detail

    def test_two_outcomes_pass(self, allocator):
        result = frv4_pattern_beyond_one_outcome(ctx(make_feedback(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "S-4 floor 2" in result.detail

    def test_reasoning_required(self):
        with pytest.raises(PatternEvidenceError) as exc:
            PatternEvidence(("a", "b"), "  ")
        assert "overfitting failure" in str(exc.value)

    def test_observed_across_required(self):
        with pytest.raises(PatternEvidenceError):
            PatternEvidence((), "reasoned")

    def test_duplicate_outcome_in_pattern_refused(self):
        with pytest.raises(PatternEvidenceError) as exc:
            PatternEvidence(("a", "a"), "reasoned")
        assert "repetition" in str(exc.value)

    def test_required_on_the_record(self, allocator):
        with pytest.raises(PatternEvidenceError):
            make_feedback(allocator, evidence_of_pattern=None)

    def test_frv4_detects_a_phantom_outcome(self, allocator):
        record = make_feedback(
            allocator, ("obj-xr-1", "obj-xr-2"),
            evidence_of_pattern=pattern("obj-xr-1", "obj-xr-99"),
        )
        result = frv4_pattern_beyond_one_outcome(ctx(record))
        assert result.failed
        assert "do not motivate this lesson" in result.detail

    def test_frv4_detects_stripped_reasoning(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(
            record.evidence_of_pattern, "distinguishing_reasoning", ""
        )
        result = frv4_pattern_beyond_one_outcome(ctx(record))
        assert result.failed
        assert "signal and noise are not distinguished" in result.detail

    def test_frv4_detects_a_narrowed_span(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(
            record.evidence_of_pattern, "observed_across", ("obj-xr-1",)
        )
        result = frv4_pattern_beyond_one_outcome(ctx(record))
        assert result.failed
        assert "pattern across outcomes requires" in result.detail

    def test_frv4_detects_a_removed_evidence(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "evidence_of_pattern", None)
        assert frv4_pattern_beyond_one_outcome(ctx(record)).failed

    def test_pattern_span(self, allocator):
        assert make_feedback(allocator).evidence_of_pattern.span == 2


# ===========================================================================
# FR-V5  INFORMS targets engines  [R-6]
# ===========================================================================

class TestInformsEngines:
    def test_informs_required(self, allocator):
        with pytest.raises(InformsError) as exc:
            make_feedback(allocator, informs=())
        assert "changes no behaviour" in str(exc.value)

    def test_informs_targets_an_engine_not_an_object(self, allocator):
        record = make_feedback(allocator)
        assert record.informed_engines == {Engine.OPPORTUNITY_INTELLIGENCE}
        assert all(
            isinstance(e.informs_engine, Engine) for e in record.informs
        )

    def test_informs_is_outside_the_lineage_graph(self, allocator):
        """The only relationship pointing at a non-object. [R-6, AD-05]"""
        assert RelationshipType.INFORMS not in LINEAGE_RELATIONSHIPS
        record = make_feedback(allocator)
        assert all(not e.is_lineage for e in record.informs)

    def test_multiple_engines_supported(self, allocator):
        record = make_feedback(
            allocator,
            engines=(Engine.OPPORTUNITY_INTELLIGENCE, Engine.PATTERN_INTELLIGENCE),
        )
        assert len(record.informed_engines) == 2

    def test_duplicate_engine_refused(self, allocator):
        with pytest.raises(InformsError) as exc:
            make_feedback(
                allocator,
                engines=(Engine.FEEDBACK, Engine.FEEDBACK),
            )
        assert "informed twice" in str(exc.value)

    def test_informs_must_originate_from_this_record(self, allocator):
        with pytest.raises(InformsError) as exc:
            make_feedback(
                allocator,
                informs=informs_for("obj-someone-else", Engine.FEEDBACK),
            )
        assert "originates from" in str(exc.value)

    def test_non_engineinforms_entry_refused(self, allocator):
        with pytest.raises(InformsError) as exc:
            make_feedback(allocator, informs=("Opportunity Intelligence",))
        assert "never an object" in str(exc.value)

    def test_only_a_feedback_record_may_inform(self):
        """R-7: EngineInforms enforces the source type."""
        from oip.relationships import IllegalRelationshipError

        with pytest.raises(IllegalRelationshipError):
            EngineInforms(
                from_object_id="obj-op-1",
                informs_engine=Engine.RESEARCH,
                asserted_by_engine=Engine.FEEDBACK,
                asserted_at=T0,
                from_type=ObjectType.OPPORTUNITY,
            )

    def test_frv5_passes_and_lists_engines(self, allocator):
        result = frv5_informs_specific_engines(ctx(make_feedback(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "OpportunityIntelligence" in result.detail

    def test_frv5_detects_emptied_informs(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "informs", ())
        result = frv5_informs_specific_engines(ctx(record))
        assert result.failed
        assert "changes no behaviour" in result.detail

    def test_frv5_detects_a_non_engineinforms_entry(self, allocator):
        record = make_feedback(allocator)
        object.__setattr__(record, "informs", ("not-an-informs",))
        result = frv5_informs_specific_engines(ctx(record))
        assert result.failed
        assert "never an object" in result.detail

    def test_informs_engine_predicate(self, allocator):
        record = make_feedback(allocator)
        assert record.informs_engine(Engine.OPPORTUNITY_INTELLIGENCE)
        assert not record.informs_engine(Engine.RESEARCH)


# ===========================================================================
# Rule-set hygiene
# ===========================================================================

class TestRuleSetHygiene:
    def test_six_rules_registered(self, store):
        assert {f"FR-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)
        assert len(FEEDBACK_RULES) == 6

    def test_rule_ids_in_order(self):
        assert [r.rule_id for r in FEEDBACK_RULES] == [
            f"FR-V{i}" for i in range(1, 7)
        ]

    def test_prefixes_remain_disjoint(self, store):
        """FR-V, F-V and V-V must not collide in the live rule set."""
        ids = set(store.acceptance.rule_ids)
        fr = {f"FR-V{i}" for i in range(1, 7)}
        f = {f"F-V{i}" for i in range(1, 7)}
        v = {f"V-V{i}" for i in range(1, 7)}
        assert fr <= ids and f <= ids and v <= ids
        assert not (fr & f) and not (fr & v) and not (f & v)

    @pytest.mark.parametrize("rule", FEEDBACK_RULES)
    def test_every_rule_skips_non_feedback(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert rule(AcceptanceContext(attributes=attributes)).outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", FEEDBACK_RULES)
    def test_every_rule_skips_without_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FEEDBACK_RECORD,
            (("obj-xr-1", ObjectType.EXECUTION_RECORD),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Feedback Record payload" in result.detail

    def test_earlier_stages_unaffected(self, store, allocator):
        solution, _ = solution_and_opportunity(store, allocator)
        assert solution.status is ObjectStatus.ACTIVE


# ===========================================================================
# Type and authority
# ===========================================================================

class TestTypeAndAuthority:
    def test_feedback_engine_holds_authority(self):
        """Unlike ExecutionRecord, this type HAS an owner. [R-7]"""
        assert CREATE_AUTHORITY[ObjectType.FEEDBACK_RECORD] is Engine.FEEDBACK

    def test_only_feedback_engine_may_create(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FEEDBACK_RECORD,
            (("obj-xr-1", ObjectType.EXECUTION_RECORD),),
            engine=Engine.RESEARCH,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(FeedbackRecordError) as exc:
            make_feedback(allocator, ("obj-xr-1",), attributes=attributes)
        assert "V7" in str(exc.value)

    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EXECUTION_RECORD,
            (("obj-so-1", ObjectType.SOLUTION),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(FeedbackRecordError):
            make_feedback(allocator, ("obj-so-1",), attributes=attributes)

    def test_lesson_statement_required(self, allocator):
        with pytest.raises(FeedbackRecordError):
            make_feedback(allocator, lesson_statement="  ")

    def test_applied_at_must_be_a_datetime(self, allocator):
        with pytest.raises(FeedbackRecordError):
            make_feedback(allocator, applied_at="2026-07-28")

    def test_optional_attributes_default_absent(self, allocator):
        record = make_feedback(allocator)
        assert record.magnitude is None
        assert record.expected_effect is None
        assert record.observed_effect is None
        assert record.superseded_lesson is None
        assert record.approval_record is None

    def test_optional_attributes_carried(self, allocator):
        record = make_feedback(
            allocator,
            magnitude="0.05 reduction",
            expected_effect="better alignment of predicted and realised value",
            superseded_lesson="obj-fr-prior",
            approval_record="owner sign-off",
        )
        assert record.magnitude == "0.05 reduction"

    def test_observed_effect_is_unassessable(self, allocator):
        """M-04: no success measure exists."""
        record = make_feedback(allocator, observed_effect="seemed to help")
        assert record.observed_effect_assessable is False

    def test_identity_delegated(self, allocator):
        record = make_feedback(allocator)
        assert record.object_id == record.attributes.object_id
        assert record.lineage_id == record.attributes.lineage_id
        assert record.status is record.attributes.status

    def test_frozen(self, allocator):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            make_feedback(allocator).lesson_statement = "x"

    def test_applied_and_reversed_states(self, allocator):
        applied = make_feedback(allocator)
        assert applied.is_applied and not applied.is_reversed
        withdrawn = make_feedback(
            allocator, status=ObjectStatus.RETRACTED, status_reason="reversed"
        )
        assert withdrawn.is_reversed and not withdrawn.is_applied


# ===========================================================================
# FR-I1..FR-I4  integrity
# ===========================================================================

def force_feedback(store, record):
    """Persist a Feedback Record bypassing acceptance. [C-02 inherited]

    FR-I1..FR-I4 are CONTINUOUS constraints that must be verifiable now so
    they are ready when C-02 closes. This installs the record exactly as
    _commit would.
    """
    from oip.store import StoredObject

    lineage = Lineage(
        object_id=record.attributes.object_id,
        object_type=ObjectType.FEEDBACK_RECORD,
        references=tuple(record.attributes.derives_from),
    )
    store.graph.index_lineage(lineage)
    stored = StoredObject(attributes=record.attributes, lineage=lineage)
    store._objects[stored.object_id] = stored
    store._by_lineage.setdefault(stored.lineage_id, []).append(stored.object_id)
    if stored.status is ObjectStatus.ACTIVE:
        store._active[stored.lineage_id] = stored.object_id
    store.feedback.register(record)
    return stored


class TestFeedbackIntegrity:
    def test_clean_store_holds(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert store.feedback.integrity().verify() == ()

    def test_fri1_detects_an_irreversible_applied_lesson(
        self, store, allocator, motivating
    ):
        record = feedback_for(store, allocator, motivating)
        force_feedback(store, record)
        object.__setattr__(record.reversal_procedure, "steps", ())
        violations = store.feedback.integrity().verify()
        assert any(v.constraint_id == "FR-I1" for v in violations)
        assert "unrecoverable" in "".join(v.detail for v in violations)

    def test_fri1_ignores_a_reversed_lesson(self, store, allocator, motivating):
        """A lesson already undone need not remain reversible."""
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "reversed")
        object.__setattr__(record.reversal_procedure, "steps", ())
        assert not [
            v for v in store.feedback.integrity().verify()
            if v.constraint_id == "FR-I1"
        ]

    def test_fri3_detects_a_modified_motivating_record(
        self, store, allocator, motivating
    ):
        """A lesson never modifies the history it learned from."""
        from oip.contract import Confidence

        force_feedback(store, feedback_for(store, allocator, motivating))
        object.__setattr__(
            store._objects[motivating[0].object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        violations = store.feedback.integrity().verify()
        assert any(v.constraint_id == "FR-I3" for v in violations)
        assert "history it learned from" in "".join(v.detail for v in violations)

    def test_fri3_detects_a_vanished_motivating_record(
        self, store, allocator, motivating
    ):
        force_feedback(store, feedback_for(store, allocator, motivating))
        del store._objects[motivating[0].object_id]
        assert any(
            v.constraint_id == "FR-I3" and "no longer retrievable" in v.detail
            for v in store.feedback.integrity().verify()
        )

    def test_fri3_reports_once_per_outcome(self, store, allocator, motivating):
        from oip.contract import Confidence

        for _ in range(3):
            force_feedback(store, feedback_for(store, allocator, motivating))
        object.__setattr__(
            store._objects[motivating[0].object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        violations = [
            v for v in store.feedback.integrity().verify()
            if v.constraint_id == "FR-I3"
        ]
        assert len(violations) == 1

    def test_fri4_detects_an_unstatable_contribution(
        self, store, allocator, motivating
    ):
        record = feedback_for(store, allocator, motivating)
        force_feedback(store, record)
        object.__setattr__(record, "change_target", "  ")
        violations = store.feedback.integrity().verify()
        assert any(v.constraint_id == "FR-I4" for v in violations)
        assert "undeterminable" in "".join(v.detail for v in violations)

    def test_fri4_ignores_reversed_records(self, store, allocator, motivating):
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "reversed")
        object.__setattr__(record, "change_target", "")
        assert not [
            v for v in store.feedback.integrity().verify()
            if v.constraint_id == "FR-I4"
        ]

    def test_drift_summary_is_determinable(self, store, allocator, motivating):
        """FR-I4: total current deviation must always be statable."""
        force_feedback(store, feedback_for(store, allocator, motivating))
        summary = store.feedback.drift_summary()
        assert isinstance(summary, DriftSummary)
        assert summary.is_determinable
        assert summary.applied_count == 1
        assert Engine.OPPORTUNITY_INTELLIGENCE in summary.engines_affected

    def test_drift_summary_excludes_reversed(self, store, allocator, motivating):
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "reversed")
        summary = store.feedback.drift_summary()
        assert summary.applied_count == 0
        assert summary.reversed_count == 1

    def test_drift_summary_lists_distinct_targets(
        self, store, allocator, motivating
    ):
        for target in ("calibration", "calibration", "source trust"):
            force_feedback(
                store,
                feedback_for(store, allocator, motivating, change_target=target),
            )
        assert set(store.feedback.drift_summary().targets()) == {
            "calibration", "source trust"
        }

    def test_drift_summary_carries_magnitude(self, store, allocator, motivating):
        force_feedback(
            store,
            feedback_for(store, allocator, motivating, magnitude="0.05"),
        )
        assert store.feedback.drift_summary().applied[0][2] == "0.05"

    def test_drift_contribution_defaults_magnitude(self, allocator):
        assert make_feedback(allocator).drift_contribution()[2] == "unstated"

    def test_recorded_upstream_count(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert store.feedback.integrity().recorded_upstream_count == 2

    def test_recording_skips_unresolvable_outcomes(self, store, allocator):
        verifier = store.feedback.integrity()
        verifier.record(make_feedback(allocator))
        assert verifier.recorded_upstream_count == 0

    def test_unregistered_records_skipped(self, store, allocator):
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.feedback.integrity().verify() == ()

    def test_verifier_constructible_standalone(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        verifier = FeedbackIntegrity(
            feedback_of=store.feedback.get, store=store
        )
        assert verifier.verify() == ()


# ===========================================================================
# Registry
# ===========================================================================

class TestRegistry:
    def test_applied_and_reversed_partitioned(self, store, allocator, motivating):
        first = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, first)
        force_feedback(store, feedback_for(store, allocator, motivating))
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "reversed")
        assert len(store.feedback.applied_records()) == 1
        assert len(store.feedback.reversed_records()) == 1

    def test_informing_locates_by_engine(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert len(store.feedback.informing(Engine.OPPORTUNITY_INTELLIGENCE)) == 1
        assert store.feedback.informing(Engine.RESEARCH) == ()

    def test_from_outcome_locates_lessons(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert len(store.feedback.from_outcome(motivating[0].object_id)) == 1
        assert store.feedback.from_outcome("obj-absent") == ()

    def test_targeting_is_case_insensitive(self, store, allocator, motivating):
        force_feedback(
            store,
            feedback_for(store, allocator, motivating, change_target="Calibration"),
        )
        assert len(store.feedback.targeting("calibration")) == 1

    def test_conflicts_between_applied_lessons_surfaced(
        self, store, allocator, motivating
    ):
        """Two lessons in force on one target may conflict. [CONTRADICTS]"""
        for _ in range(2):
            force_feedback(
                store,
                feedback_for(store, allocator, motivating, change_target="calibration"),
            )
        assert len(store.feedback.conflicts_for("calibration")) == 1

    def test_reversed_lessons_are_not_conflicts(self, store, allocator, motivating):
        first = feedback_for(store, allocator, motivating, change_target="calibration")
        stored = force_feedback(store, first)
        force_feedback(
            store,
            feedback_for(store, allocator, motivating, change_target="calibration"),
        )
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "reversed")
        assert store.feedback.conflicts_for("calibration") == ()

    def test_no_resolution_policy_offered(self, store):
        """OQ-24 leaves application undefined; no winner is selected."""
        assert not hasattr(store.feedback, "apply")
        assert not hasattr(store.feedback, "resolve")

    def test_registry_memoised_and_counted(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert len(store.feedback) == 1
        assert store.feedback is store.feedback

    def test_unknown_payload_is_none(self, store):
        assert store.get_feedback_record("obj-absent") is None


# ===========================================================================
# Pipeline integration
# ===========================================================================

class TestPipelineIntegration:
    def test_reaches_evidence_through_outcomes(self, store, allocator, motivating):
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.depth_to_evidence(stored.object_id) == 7

    def test_deepest_object_in_the_pipeline(self, store, allocator, motivating):
        """IOM "Depth 8" is stage-1 arithmetic; real lineage is 7 edges.

        Recorded at T01.7.8: the per-type depth labels equal stage-1 for
        every type, which assumes a linear chain. ExecutionRecord and
        Validation are sibling branches off Solution, so the chain to a
        Feedback Record is ev>fa>pr>pt>op>so>xr>fr = 8 nodes / 7 edges.
        """
        stored = force_feedback(
            store, feedback_for(store, allocator, motivating)
        )
        path = store.graph.path_to_evidence(stored.object_id)
        assert len(path.object_ids) == 8
        assert path.depth == 7

    def test_lineage_edges_indexed(self, store, allocator, motivating):
        stored = force_feedback(
            store, feedback_for(store, allocator, motivating)
        )
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset(o.object_id for o in motivating)

    def test_graph_rebuildable(self, store, allocator, motivating):
        stored = force_feedback(
            store, feedback_for(store, allocator, motivating)
        )
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_is_a_lineage_leaf(self, store, allocator, motivating):
        """Nothing derives from a Feedback Record. [R-8, FR-I2]"""
        stored = force_feedback(
            store, feedback_for(store, allocator, motivating)
        )
        assert store.graph.descendants(stored.object_id) == frozenset()

    def test_confidence_bounded_by_outcomes(self, store, allocator, motivating):
        stored = force_feedback(
            store, feedback_for(store, allocator, motivating)
        )
        ceiling = min(
            o.attributes.confidence.effective_confidence for o in motivating
        )
        assert stored.attributes.confidence.effective_confidence <= ceiling

    def test_confidence_inflation_rejected(self, store, allocator, motivating):
        """The builder clamps to the ceiling, so inflate deliberately."""
        from oip.contract import Confidence

        record = feedback_for(store, allocator, motivating)
        object.__setattr__(
            record.attributes, "confidence",
            Confidence(evidential_support=0.99, assertion_confidence=0.99,
                       effective_confidence=0.99),
        )
        result = evaluate(store, record)
        assert "V5" in [r.rule_id for r in result.results if r.failed]

    def test_cascade_invalidates_the_lesson(self, store, allocator, motivating):
        """IOM: ACTIVE -> INVALIDATED when motivating records invalidated."""
        stored = force_feedback(
            store, feedback_for(store, allocator, motivating)
        )
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_universal_integrity_holds(self, store, allocator, motivating):
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert store.verify_integrity().holds

    def test_all_nine_type_verifiers_hold(self, store, allocator, motivating):
        """Every realised type, together. The full object model."""
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert store.evidence.integrity().verify() == ()
        assert store.facts.integrity().verify() == ()
        assert store.problems.integrity().verify() == ()
        assert store.patterns.integrity().verify() == ()
        assert store.opportunities.integrity().verify() == ()
        assert store.solutions.integrity().verify() == ()
        assert store.validations.integrity().verify() == ()
        assert store.executions.integrity().verify() == ()
        assert store.feedback.integrity().verify() == ()


# ===========================================================================
# Concurrency  [N-11, I5]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_lessons_serialise(self, store, allocator, motivating):
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            record = feedback_for(store, allocator, motivating)
            barrier.wait()
            try:
                with store._lock:
                    written.append(force_feedback(store, record).object_id)
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
        assert store.feedback.drift_summary().applied_count == 8

    def test_concurrent_acceptance_all_consistent(self, store, allocator, motivating):
        """Acceptance under contention must give one verdict per record."""
        verdicts: list[bool] = []
        barrier = threading.Barrier(8)

        def evaluator() -> None:
            record = feedback_for(store, allocator, motivating)
            barrier.wait()
            verdicts.append(evaluate(store, record).accepted)

        threads = [threading.Thread(target=evaluator) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(verdicts) == 8
        assert all(verdicts)


# ===========================================================================
# Adversarial
# ===========================================================================

class TestAdversarial:
    def test_loop_cannot_be_closed_evidentially(self, store, allocator, motivating):
        """R-8: the feedback loop is behavioural, never evidential."""
        record = feedback_for(store, allocator, motivating)
        force_feedback(store, record)
        assert store.graph.is_acyclic()
        assert store.graph.descendants(record.object_id) == frozenset()
        assert not [
            v for v in store.feedback.integrity().verify()
            if v.constraint_id == "FR-I2"
        ]

    def test_a_second_lesson_cannot_launder_a_modified_outcome(
        self, store, allocator, motivating
    ):
        from oip.contract import Confidence

        force_feedback(store, feedback_for(store, allocator, motivating))
        object.__setattr__(
            store._objects[motivating[0].object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        force_feedback(store, feedback_for(store, allocator, motivating))
        assert any(
            v.constraint_id == "FR-I3"
            for v in store.feedback.integrity().verify()
        )

    def test_payload_survives_the_registry_round_trip(
        self, store, allocator, motivating
    ):
        record = feedback_for(
            store, allocator, motivating,
            magnitude="0.05", expected_effect="better alignment",
            engines=(Engine.OPPORTUNITY_INTELLIGENCE, Engine.VALIDATION),
        )
        stored = force_feedback(store, record)
        payload = store.get_feedback_record(stored.object_id)
        assert payload.magnitude == "0.05"
        assert len(payload.informed_engines) == 2
        assert payload.reversal_procedure.is_actionable

    def test_graph_rebuild_does_not_disturb_integrity(
        self, store, allocator, motivating
    ):
        force_feedback(store, feedback_for(store, allocator, motivating))
        store.rebuild_graph()
        assert store.feedback.integrity().verify() == ()

    def test_reversal_preserves_the_record(self, store, allocator, motivating):
        """Reversal is a status transition; the lesson is not erased."""
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "reversed")
        assert store.get_feedback_record(stored.object_id) is not None
        assert store.get(stored.object_id).status is ObjectStatus.RETRACTED


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(count=st.integers(min_value=0, max_value=8))
def test_s4_floor_is_the_gate_on_motivating_count(count):
    """FR-V4/S-4 over arbitrary outcome counts."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-xr-{i}" for i in range(count))
    if count == 0:
        with pytest.raises(MotivatingRecordError):
            make_feedback(allocator, refs, motivating=(),
                          evidence_of_pattern=pattern("obj-xr-0"))
        return
    record = make_feedback(allocator, refs, evidence_of_pattern=pattern(*refs))
    result = frv4_pattern_beyond_one_outcome(ctx(record))
    assert result.failed == (count < MINIMUM_MOTIVATING_RECORDS)


@settings(max_examples=200, deadline=None)
@given(wrong=st.sampled_from(
    [t for t in ObjectType if t is not ObjectType.EXECUTION_RECORD]
))
def test_frv6_refuses_every_non_outcome_type(wrong):
    """AC1 over the whole closed type vocabulary."""
    allocator = IdentityAllocator()
    with pytest.raises(MotivatingRecordError):
        make_feedback(
            allocator, ("obj-a", "obj-b"),
            upstream_types=(wrong, ObjectType.EXECUTION_RECORD),
        )


@settings(max_examples=200, deadline=None)
@given(target=st.text(max_size=30))
def test_change_target_presence_required_value_unconstrained(target):
    """M-02: presence is enforceable, vocabulary is not."""
    allocator = IdentityAllocator()
    if target.strip():
        record = make_feedback(allocator, change_target=target)
        assert not frv2_change_target_present(ctx(record)).failed
    else:
        with pytest.raises(ChangeTargetError):
            make_feedback(allocator, change_target=target)


@settings(max_examples=200, deadline=None)
@given(steps=st.integers(min_value=0, max_value=6))
def test_reversal_requires_at_least_one_step(steps):
    """AC3 over arbitrary procedure lengths."""
    procedure_steps = tuple(f"step {i}" for i in range(steps))
    if steps:
        assert ReversalProcedure(procedure_steps, "baseline").is_actionable
    else:
        with pytest.raises(ReversalProcedureError):
            ReversalProcedure(procedure_steps, "baseline")


@settings(max_examples=150, deadline=None)
@given(engines=st.lists(st.sampled_from(list(Engine)), min_size=1, max_size=4))
def test_informs_rejects_duplicate_engines(engines):
    """FR-V5 over arbitrary engine sets."""
    allocator = IdentityAllocator()
    unique = len(set(engines)) == len(engines)
    if unique:
        record = make_feedback(allocator, engines=tuple(engines))
        assert len(record.informed_engines) == len(engines)
    else:
        with pytest.raises(InformsError):
            make_feedback(allocator, engines=tuple(engines))


@settings(max_examples=150, deadline=None)
@given(applied=st.integers(min_value=0, max_value=6))
def test_drift_summary_counts_exactly_the_applied(applied):
    """FR-I4: the total must always be determinable."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    stored_outcomes = outcomes(store, allocator, 2)
    for _ in range(applied):
        force_feedback(store, feedback_for(store, allocator, stored_outcomes))
    summary = store.feedback.drift_summary()
    assert summary.is_determinable
    assert summary.applied_count == applied


# ===========================================================================
# Self-reinforcement: a lesson may never learn from a lesson
# ===========================================================================

class TestSelfReinforcement:
    """The failure FR-V6 and FR-I2 exist together to prevent. [M-70]"""

    def test_lesson_from_lesson_refused_at_construction(
        self, store, allocator, motivating
    ):
        first = feedback_for(store, allocator, motivating)
        force_feedback(store, first)
        with pytest.raises(MotivatingRecordError) as exc:
            make_feedback(
                allocator,
                (first.object_id, motivating[0].object_id),
                upstream_types=(
                    ObjectType.FEEDBACK_RECORD, ObjectType.EXECUTION_RECORD,
                ),
                upstream_ceiling=0.2,
            )
        assert "learning from its own conclusions" in str(exc.value)

    def test_lesson_from_lesson_detected_continuously(
        self, store, allocator, motivating
    ):
        """Even if it reached storage, FR-I2 reports it."""
        from oip.contract import LineageRef

        first = feedback_for(store, allocator, motivating)
        force_feedback(store, first)
        second = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, second)
        object.__setattr__(
            store._objects[stored.object_id].attributes, "derives_from",
            (LineageRef(first.object_id, ObjectType.FEEDBACK_RECORD),),
        )
        violations = store.feedback.integrity().verify()
        assert any(
            v.constraint_id == "FR-I2" and "never enters the lineage graph" in v.detail
            for v in violations
        )

    def test_supersession_chain_stays_a_leaf(self, store, allocator, motivating):
        """Lessons are superseded, not derived from. [IOM versioning]"""
        first = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, first)
        store.transition(stored.object_id, ObjectStatus.SUPERSEDED, "later lesson")
        identity = allocator.succeed(stored.attributes.identity)
        force_feedback(
            store,
            feedback_for(
                store, allocator, motivating,
                identity=identity, superseded_lesson=first.object_id,
            ),
        )
        assert store.feedback.integrity().verify() == ()
        assert store.graph.is_acyclic()
        assert store.graph.descendants(first.object_id) == frozenset()

    def test_fri1_detects_a_gutted_restore_point_while_applied(
        self, store, allocator, motivating
    ):
        record = feedback_for(store, allocator, motivating)
        force_feedback(store, record)
        object.__setattr__(record.reversal_procedure, "restores_to", "")
        assert any(
            v.constraint_id == "FR-I1"
            for v in store.feedback.integrity().verify()
        )


# ===========================================================================
# Forward compatibility: the write path when C-02 closes
# ===========================================================================

class TestWritePathReadyForC02:
    """The sanctioned write path is unreachable today and must be correct.

    FR-V1 requires resolvable Execution Records, which C-02 leaves
    uncreatable through any sanctioned path. `write_feedback_record` is
    therefore never exercised end-to-end -- and it is exactly what T08.2.2
    will depend on. These tests grant Execution Record authority
    TEMPORARILY, inside the test only, so the whole chain runs. No
    production code assigns authority.
    """

    @pytest.fixture()
    def execution_authority(self):
        CREATE_AUTHORITY[ObjectType.EXECUTION_RECORD] = Engine.RESEARCH
        try:
            yield Engine.RESEARCH
        finally:
            del CREATE_AUTHORITY[ObjectType.EXECUTION_RECORD]

    def test_authority_map_is_restored_afterwards(self):
        assert ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY

    def _written_outcomes(self, store, allocator, engine, n=2):
        solution, opportunity = solution_and_opportunity(store, allocator)
        return [
            store.write_execution_record(
                record_for(
                    store, allocator, solution, opportunity, engine=engine
                )
            )
            for _ in range(n)
        ]

    def test_full_chain_writes_once_c02_closes(
        self, store, allocator, execution_authority
    ):
        """Evidence through to Feedback Record, entirely through the store."""
        written = self._written_outcomes(store, allocator, execution_authority)
        stored = store.write_feedback_record(
            feedback_for(store, allocator, written)
        )
        assert stored.status is ObjectStatus.ACTIVE
        assert store.get_feedback_record(stored.object_id) is not None

    def test_written_payload_is_complete(
        self, store, allocator, execution_authority
    ):
        written = self._written_outcomes(store, allocator, execution_authority)
        stored = store.write_feedback_record(
            feedback_for(
                store, allocator, written,
                magnitude="0.05", expected_effect="better alignment",
                engines=(Engine.OPPORTUNITY_INTELLIGENCE, Engine.VALIDATION),
            )
        )
        payload = store.get_feedback_record(stored.object_id)
        assert payload.magnitude == "0.05"
        assert len(payload.informed_engines) == 2
        assert payload.reversal_procedure.is_actionable
        assert payload.evidence_of_pattern.span == 2

    def test_written_record_passes_every_verifier(
        self, store, allocator, execution_authority
    ):
        written = self._written_outcomes(store, allocator, execution_authority)
        store.write_feedback_record(feedback_for(store, allocator, written))
        assert store.feedback.integrity().verify() == ()
        assert store.executions.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_rejected_lesson_leaves_no_payload(
        self, store, allocator, execution_authority
    ):
        written = self._written_outcomes(store, allocator, execution_authority)
        record = feedback_for(store, allocator, written)
        object.__setattr__(record, "change_target", "")
        before = len(store.feedback)
        with pytest.raises(WriteRejectedError) as exc:
            store.write_feedback_record(record)
        assert "FR-V2" in exc.value.failure.rule_ids
        assert len(store.feedback) == before

    def test_wrong_engine_still_refused(
        self, store, allocator, execution_authority
    ):
        written = self._written_outcomes(store, allocator, execution_authority)
        record = feedback_for(store, allocator, written)
        object.__setattr__(
            record.attributes, "produced_by_engine", Engine.RESEARCH
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write_feedback_record(record)
        assert "V7" in exc.value.failure.rule_ids

    def test_failure_record_typed_correctly(
        self, store, allocator, execution_authority
    ):
        written = self._written_outcomes(store, allocator, execution_authority)
        record = feedback_for(store, allocator, written)
        object.__setattr__(record, "change_target", "")
        with pytest.raises(WriteRejectedError):
            store.write_feedback_record(record)
        assert store.failure_records[-1].object_type is ObjectType.FEEDBACK_RECORD


# ===========================================================================
# Residual surface
# ===========================================================================

class TestResidualSurface:
    def test_frv5_detects_a_malformed_engine_target(self, allocator):
        """An EngineInforms whose target was corrupted after construction."""
        record = make_feedback(allocator)
        object.__setattr__(record.informs[0], "informs_engine", "Research")
        result = frv5_informs_specific_engines(ctx(record))
        assert result.failed
        assert "no known engine" in result.detail

    def test_drift_summary_skips_unstored_records(self, store, allocator, motivating):
        """A payload without a stored object contributes nothing. [N-6]"""
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        del store._objects[stored.object_id]
        summary = store.feedback.drift_summary()
        assert summary.applied_count == 0
        assert summary.reversed_count == 0

    def test_drift_summary_ignores_other_statuses(
        self, store, allocator, motivating
    ):
        """SUPERSEDED is neither applied nor reversed."""
        record = feedback_for(store, allocator, motivating)
        stored = force_feedback(store, record)
        store.transition(stored.object_id, ObjectStatus.SUPERSEDED, "later lesson")
        summary = store.feedback.drift_summary()
        assert summary.applied_count == 0
        assert summary.reversed_count == 0
