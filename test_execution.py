"""Contract tests for the Execution Record object type.

Task: T01.7.8

Architecture References:
- X-V1..X-V6  Execution Record validation rules
- X-I1..X-I4  Execution Record integrity constraints
- C-02        NO CREATE AUTHORITY -- open, blocking; write fails closed
- M-47        Outcome intake and verification OPEN
- R-1a        Lineage references bind to a specific version
- R-3         assertion_confidence reflects attribution certainty
- D-01/O-I4   Immutable prediction storage, which X-V4 depends on

Acceptance criteria under test:
  AC1  Type realised and persistable (structure complete; write path whole)
  AC2  No engine holds create authority yet
  AC3  X-V4 requires resolvable stored prediction
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.enums import CREATE_AUTHORITY, Engine, ObjectStatus, ObjectType, RelationshipType
from oip.execution import (
    EXECUTION_RULES,
    NO_CREATE_AUTHORITY,
    PROTECTED_VALENCES,
    AttributionAssessment,
    AttributionError,
    ExecutionIntegrity,
    ExecutionRecord,
    ExecutionRecordError,
    OutcomeTimingError,
    OutcomeValence,
    PredictionComparison,
    PredictionComparisonError,
    SolutionReferenceError,
    UnfavourableSuppressionError,
    ValenceError,
    VerificationError,
    xv1_solution_version_resolves,
    xv2_valence_present,
    xv3_attribution_reasoned,
    xv4_prediction_retrievable,
    xv5_execution_precedes_observation,
    xv6_verification_present,
)
from oip.identity import IdentityAllocator
from oip.lineage import Lineage
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs
from tests.test_solution import assumption
from tests.test_validation import write_solutions

EXECUTED_AT = T0 + timedelta(days=90)
OBSERVED_AT = T0 + timedelta(days=135)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def attribution(**overrides) -> AttributionAssessment:
    kwargs = {
        "attributable": ("complaint reduction in the cohort",),
        "not_attributable": ("remediation behaviour at high volume",),
        "reasoning": (
            "Complaint reduction is plausibly attributable, as no other change "
            "affected the cohort. Remediation reflects seller capacity."
        ),
    }
    kwargs.update(overrides)
    return AttributionAssessment(**kwargs)


def comparison(opportunity_ref: str = "obj-op-1", **overrides) -> PredictionComparison:
    kwargs = {
        "predicted_by": opportunity_ref,
        "comparison": (
            "Predicted value from eliminating delayed discovery; discovery "
            "delay was reduced, downstream benefit only partially realised."
        ),
    }
    kwargs.update(overrides)
    return PredictionComparison(**kwargs)


def make_record(
    allocator: IdentityAllocator,
    solution_ref: str = "obj-so-1",
    *,
    opportunity_ref: str = "obj-op-1",
    valence: OutcomeValence = OutcomeValence.MIXED,
    engine: Engine = Engine.FEEDBACK,
    source_count: int = 1,
    upstream_ceiling: float | None = None,
    support: float = 0.55,
    assertion: float = 0.47,
    status: ObjectStatus = ObjectStatus.ACTIVE,
    status_reason: str | None = None,
    **overrides,
) -> ExecutionRecord:
    identity = overrides.pop("identity", None) or allocator.new_object()
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.EXECUTION_RECORD,
        ((solution_ref, ObjectType.SOLUTION),),
        status=status,
        status_reason=status_reason,
        source_count=source_count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
        engine=engine,
    )
    kwargs = {
        "attributes": attributes,
        "outcome_of_solution": overrides.pop("outcome_of_solution", solution_ref),
        "execution_description": overrides.pop(
            "execution_description",
            "Per-item outcome reporting introduced for a limited cohort.",
        ),
        "executed_at": overrides.pop("executed_at", EXECUTED_AT),
        "outcome_observed_at": overrides.pop("outcome_observed_at", OBSERVED_AT),
        "outcome": overrides.pop(
            "outcome", "Silent-failure complaints fell substantially."
        ),
        "outcome_valence": valence,
        "attribution_assessment": overrides.pop(
            "attribution_assessment", attribution()
        ),
        "prediction_comparison": overrides.pop(
            "prediction_comparison", comparison(opportunity_ref)
        ),
        "outcome_verification": overrides.pop(
            "outcome_verification", "Cohort ticket audit against source system."
        ),
    }
    kwargs.update(overrides)
    return ExecutionRecord(**kwargs)


def ctx(record: ExecutionRecord, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": record.attributes, "execution_record": record}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def solution_and_opportunity(store, allocator):
    """A persisted Solution plus the Opportunity that predicted it."""
    stored = write_solutions(
        store, allocator, 1, assumptions=(assumption("A1"),)
    )[0]
    opportunity_id = store.objects_of_type(ObjectType.OPPORTUNITY)[0].object_id
    return stored, opportunity_id


def record_for(store, allocator, stored_solution, opportunity_ref, **overrides):
    kwargs = {
        "opportunity_ref": opportunity_ref,
        "upstream_ceiling": stored_solution.attributes.confidence.effective_confidence,
    }
    kwargs.update(overrides)
    return make_record(allocator, stored_solution.object_id, **kwargs)


def evaluate(store, record, predecessor_id=None):
    """Run the acceptance path without requiring a successful write.

    Necessary because C-02 blocks every write: the X-V rules can only be
    exercised end-to-end by evaluating them directly.
    """
    lineage = Lineage(
        object_id=record.attributes.object_id,
        object_type=ObjectType.EXECUTION_RECORD,
        references=tuple(record.attributes.derives_from),
    )
    return store._evaluate(
        record.attributes, lineage, predecessor_id, execution_record=record
    )


def force_persist(store, record):
    """Persist a record bypassing V7 only, for integrity testing. [C-02]

    C-02 makes normal creation impossible, but X-I1..X-I4 are CONTINUOUS
    constraints that must be verifiable now so they are ready when C-02
    closes. This installs the record exactly as _commit would, without
    granting any engine create authority.
    """
    from oip.store import StoredObject

    lineage = Lineage(
        object_id=record.attributes.object_id,
        object_type=ObjectType.EXECUTION_RECORD,
        references=tuple(record.attributes.derives_from),
    )
    store.graph.index_lineage(lineage)
    stored = StoredObject(attributes=record.attributes, lineage=lineage)
    store._objects[stored.object_id] = stored
    store._by_lineage.setdefault(stored.lineage_id, []).append(stored.object_id)
    if stored.status is ObjectStatus.ACTIVE:
        store._active[stored.lineage_id] = stored.object_id
    store.executions.register(record)
    return stored


@pytest.fixture()
def executed(store, allocator):
    solution, opportunity_ref = solution_and_opportunity(store, allocator)
    return solution, opportunity_ref


# ===========================================================================
# AC2 -- no engine holds create authority  [C-02]
# ===========================================================================

class TestNoCreateAuthority:
    """C-02: the only object type with no producing engine."""

    def test_create_authority_has_no_entry(self):
        assert ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY
        assert NO_CREATE_AUTHORITY is True

    def test_authority_map_covers_the_other_eight_types(self):
        missing = set(ObjectType) - set(CREATE_AUTHORITY)
        assert missing == {ObjectType.EXECUTION_RECORD}
        assert len(CREATE_AUTHORITY) == 8

    @pytest.mark.parametrize("engine", list(Engine))
    def test_no_engine_may_create_one(self, store, allocator, executed, engine):
        """Every engine is refused, not merely the implausible ones."""
        solution, opportunity_ref = executed
        record = record_for(
            store, allocator, solution, opportunity_ref, engine=engine
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write_execution_record(record)
        assert "V7" in exc.value.failure.rule_ids

    def test_refusal_names_the_open_contradiction(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        with pytest.raises(WriteRejectedError):
            store.write_execution_record(record)
        failure = store.failure_records[-1]
        assert failure.object_type is ObjectType.EXECUTION_RECORD
        assert "C-02" in failure.failed_rules[0].detail

    def test_v7_is_the_only_obstacle(self, store, allocator, executed):
        """AC1/AC3: everything except authority is ready. [C-02]"""
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        result = evaluate(store, record)
        assert [r.rule_id for r in result.results if r.failed] == ["V7"]

    def test_all_six_x_rules_pass_when_evaluated(self, store, allocator, executed):
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        outcomes = {
            r.rule_id: r.outcome
            for r in evaluate(store, record).results
            if r.rule_id.startswith("X-V")
        }
        assert outcomes == {f"X-V{i}": RuleOutcome.PASS for i in range(1, 7)}

    def test_rejected_write_leaves_no_payload(self, store, allocator, executed):
        solution, opportunity_ref = executed
        with pytest.raises(WriteRejectedError):
            store.write_execution_record(
                record_for(store, allocator, solution, opportunity_ref)
            )
        assert len(store.executions) == 0

    def test_registry_exists_but_stays_empty(self, store):
        """Ready for C-02's resolution; unpopulated until then."""
        assert len(store.executions) == 0
        assert store.executions.active_records() == ()
        assert store.get_execution_record("obj-absent") is None

    def test_no_authority_asserted_by_the_type(self, allocator):
        """The payload must not smuggle in an authority of its own."""
        for engine in (Engine.FEEDBACK, Engine.RESEARCH, Engine.ORCHESTRATION):
            assert make_record(allocator, engine=engine)


# ===========================================================================
# AC1 -- type realised; structure complete
# ===========================================================================

class TestTypeRealised:
    def test_required_attributes_present(self, allocator):
        record = make_record(allocator)
        for name in (
            "outcome_of_solution", "execution_description", "executed_at",
            "outcome_observed_at", "outcome", "outcome_valence",
            "attribution_assessment", "prediction_comparison",
            "outcome_verification",
        ):
            assert getattr(record, name) is not None

    def test_optional_attributes_default_absent(self, allocator):
        record = make_record(allocator)
        assert record.execution_deviations == ()
        assert record.external_factors == ()
        assert record.partial_outcomes == ()
        assert record.outcome_magnitude is None

    def test_optional_attributes_carried(self, allocator):
        record = make_record(
            allocator,
            execution_deviations=("cohort narrower than specified",),
            external_factors=("seasonal volume variation",),
            partial_outcomes=("week 4 interim",),
            outcome_magnitude="complaints down ~40%",
            attribution_assessment=attribution(
                reasoning="Deviation in cohort width limits attribution."
            ),
        )
        assert record.deviated
        assert record.has_confounders

    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.SOLUTION,
            (("obj-op-1", ObjectType.OPPORTUNITY),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExecutionRecordError):
            make_record(allocator, "obj-op-1", attributes=attributes)

    @pytest.mark.parametrize(
        "field_name", ["outcome_of_solution", "execution_description", "outcome"]
    )
    def test_required_prose_attributes(self, allocator, field_name):
        with pytest.raises(ExecutionRecordError):
            make_record(allocator, **{field_name: "  "})

    def test_derives_from_must_be_solutions(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EXECUTION_RECORD,
            (("obj-op-1", ObjectType.OPPORTUNITY),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExecutionRecordError) as exc:
            make_record(allocator, "obj-op-1", attributes=attributes)
        assert "derives from Solutions only" in str(exc.value)

    def test_outcome_of_solution_must_be_in_lineage(self, allocator):
        with pytest.raises(SolutionReferenceError) as exc:
            make_record(allocator, outcome_of_solution="obj-so-unrelated")
        assert "outcome of the Solution it derives from" in str(exc.value)

    def test_identity_delegated(self, allocator):
        record = make_record(allocator)
        assert record.object_id == record.attributes.object_id
        assert record.lineage_id == record.attributes.lineage_id
        assert record.status is record.attributes.status
        assert record.predicted_by == "obj-op-1"

    def test_frozen(self, allocator):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            make_record(allocator).outcome = "changed"

    def test_observation_lag(self, allocator):
        assert make_record(allocator).observation_lag == timedelta(days=45)

    def test_outcome_fingerprint_stable(self, allocator):
        record = make_record(allocator)
        assert record.outcome_fingerprint() == record.outcome_fingerprint()


# ===========================================================================
# AC3 -- X-V4 requires a resolvable stored prediction
# ===========================================================================

class TestPredictionRetrievable:
    def test_passes_when_prediction_retrievable(self, store, allocator, executed):
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        result = xv4_prediction_retrievable(
            ctx(
                record,
                lineage_opportunities=lambda oid: frozenset({opportunity_ref}),
                stored_prediction=store._stored_prediction,
            )
        )
        assert result.outcome is RuleOutcome.PASS
        assert "stored prediction" in result.detail

    def test_fails_when_prediction_unretrievable(self, allocator):
        """D-01/O-I4: this is where immutability pays for itself."""
        result = xv4_prediction_retrievable(
            ctx(
                make_record(allocator),
                stored_prediction=lambda ref: None,
            )
        )
        assert result.failed
        assert "not retrievable" in result.detail
        assert "O-I4" in result.detail

    def test_fails_on_an_opportunity_outside_lineage(self, allocator):
        """An outcome measured against a different bet."""
        result = xv4_prediction_retrievable(
            ctx(
                make_record(allocator),
                lineage_opportunities=lambda oid: frozenset({"obj-op-other"}),
            )
        )
        assert result.failed
        assert "different bet" in result.detail

    def test_skips_without_a_prediction_provider(self, allocator):
        result = xv4_prediction_retrievable(ctx(make_record(allocator)))
        assert result.outcome is RuleOutcome.SKIP
        assert "no provider" in result.detail

    def test_predicted_by_required(self):
        with pytest.raises(PredictionComparisonError):
            PredictionComparison(predicted_by="  ", comparison="x")

    def test_comparison_text_required(self):
        with pytest.raises(PredictionComparisonError) as exc:
            PredictionComparison(predicted_by="obj-op-1", comparison="")
        assert "teaches nothing" in str(exc.value)

    def test_comparison_required_on_the_record(self, allocator):
        with pytest.raises(PredictionComparisonError):
            make_record(allocator, prediction_comparison=None)

    def test_xv4_detects_a_stripped_reference(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record.prediction_comparison, "predicted_by", "")
        result = xv4_prediction_retrievable(ctx(record))
        assert result.failed
        assert "names no Opportunity" in result.detail

    def test_xv4_detects_stripped_comparison_text(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record.prediction_comparison, "comparison", "  ")
        result = xv4_prediction_retrievable(ctx(record))
        assert result.failed
        assert "teaches nothing" in result.detail

    def test_store_prediction_provider(self, store, allocator, executed):
        solution, opportunity_ref = executed
        assert store._stored_prediction(opportunity_ref) is not None
        assert store._stored_prediction("obj-absent") is None

    def test_prediction_is_point_in_time(self, store, allocator, executed):
        """O-I4: the fingerprint is what the platform predicted then."""
        solution, opportunity_ref = executed
        before = store._stored_prediction(opportunity_ref)
        payload = store.get_opportunity(opportunity_ref)
        assert before == payload.score_fingerprint()


# ===========================================================================
# X-V1  executed Solution version
# ===========================================================================

class TestSolutionVersionReference:
    def test_passes_when_resolvable(self, allocator):
        result = xv1_solution_version_resolves(
            ctx(make_record(allocator), resolve_type=lambda r: ObjectType.SOLUTION)
        )
        assert result.outcome is RuleOutcome.PASS

    def test_fails_when_unresolvable(self, allocator):
        result = xv1_solution_version_resolves(
            ctx(make_record(allocator), resolve_type=lambda r: None)
        )
        assert result.failed
        assert "does not resolve" in result.detail

    def test_fails_on_wrong_type(self, allocator):
        result = xv1_solution_version_resolves(
            ctx(make_record(allocator), resolve_type=lambda r: ObjectType.OPPORTUNITY)
        )
        assert result.failed
        assert "not a Solution" in result.detail

    def test_detects_a_stripped_reference(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record, "outcome_of_solution", "")
        assert xv1_solution_version_resolves(ctx(record)).failed

    def test_skips_without_resolver(self, allocator):
        assert xv1_solution_version_resolves(
            ctx(make_record(allocator))
        ).outcome is RuleOutcome.SKIP

    def test_reference_is_version_specific(self, store, allocator, executed):
        """R-1a: object_id identifies exactly one version."""
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        assert record.outcome_of_solution == solution.object_id
        assert store.get(record.outcome_of_solution).attributes.version == 1


# ===========================================================================
# X-V2  valence
# ===========================================================================

class TestOutcomeValence:
    def test_four_defined_valences(self):
        assert {v.value for v in OutcomeValence} == {
            "FAVOURABLE", "UNFAVOURABLE", "MIXED", "INCONCLUSIVE"
        }

    @pytest.mark.parametrize("valence", list(OutcomeValence))
    def test_every_valence_accepted(self, allocator, valence):
        assert make_record(allocator, valence=valence).outcome_valence is valence

    def test_undefined_valence_rejected(self, allocator):
        with pytest.raises(ValenceError) as exc:
            make_record(allocator, valence="QUITE_GOOD")
        assert "must be one of" in str(exc.value)

    def test_unfavourable_classification(self):
        assert OutcomeValence.UNFAVOURABLE.is_unfavourable
        assert OutcomeValence.MIXED.is_unfavourable
        assert not OutcomeValence.FAVOURABLE.is_unfavourable
        assert not OutcomeValence.INCONCLUSIVE.is_unfavourable

    def test_protected_set(self):
        assert OutcomeValence.FAVOURABLE not in PROTECTED_VALENCES
        assert PROTECTED_VALENCES == {
            OutcomeValence.UNFAVOURABLE,
            OutcomeValence.MIXED,
            OutcomeValence.INCONCLUSIVE,
        }

    def test_xv2_detects_a_smuggled_valence(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record, "outcome_valence", "INVENTED")
        result = xv2_valence_present(ctx(record))
        assert result.failed
        assert "outside the defined set" in result.detail


# ===========================================================================
# X-V3  attribution
# ===========================================================================

class TestAttribution:
    def test_reasoning_required(self):
        with pytest.raises(AttributionError) as exc:
            AttributionAssessment(("a",), ("b",), "  ")
        assert "only ground-truth input" in str(exc.value)

    def test_must_distinguish_something(self):
        with pytest.raises(AttributionError) as exc:
            AttributionAssessment((), (), "reasoned but empty")
        assert "distinguishes nothing" in str(exc.value)

    def test_required_on_the_record(self, allocator):
        with pytest.raises(AttributionError):
            make_record(allocator, attribution_assessment=None)

    def test_xv3_passes_when_reasoned(self, allocator):
        result = xv3_attribution_reasoned(ctx(make_record(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "attributable" in result.detail

    def test_xv3_detects_stripped_reasoning(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record.attribution_assessment, "reasoning", "")
        result = xv3_attribution_reasoned(ctx(record))
        assert result.failed
        assert "cannot be audited" in result.detail

    def test_xv3_detects_an_emptied_assessment(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record.attribution_assessment, "attributable", ())
        object.__setattr__(record.attribution_assessment, "not_attributable", ())
        result = xv3_attribution_reasoned(ctx(record))
        assert result.failed
        assert "distinguishes nothing" in result.detail

    def test_xv3_detects_a_removed_assessment(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record, "attribution_assessment", None)
        assert xv3_attribution_reasoned(ctx(record)).failed

    def test_total_attribution_flag(self):
        assert AttributionAssessment(("a",), (), "all ours").claims_total_attribution
        assert not attribution().claims_total_attribution

    def test_partial_attribution_is_legitimate(self, allocator):
        """Recording both halves is the specified behaviour."""
        record = make_record(allocator)
        assert record.attribution_assessment.attributable
        assert record.attribution_assessment.not_attributable


# ===========================================================================
# X-V5  timing
# ===========================================================================

class TestOutcomeTiming:
    def test_execution_before_observation_accepted(self, allocator):
        assert not xv5_execution_precedes_observation(
            ctx(make_record(allocator))
        ).failed

    def test_equal_timestamps_accepted(self, allocator):
        record = make_record(
            allocator, executed_at=EXECUTED_AT, outcome_observed_at=EXECUTED_AT
        )
        assert not xv5_execution_precedes_observation(ctx(record)).failed

    def test_observation_before_execution_refused(self, allocator):
        with pytest.raises(OutcomeTimingError) as exc:
            make_record(
                allocator, executed_at=OBSERVED_AT, outcome_observed_at=EXECUTED_AT
            )
        assert "cannot be observed before it was caused" in str(exc.value)

    def test_mixed_awareness_refused_at_construction(self, allocator):
        with pytest.raises(OutcomeTimingError) as exc:
            make_record(
                allocator,
                executed_at=datetime(2026, 6, 1),
                outcome_observed_at=OBSERVED_AT,
            )
        assert "naive" in str(exc.value)

    def test_xv5_reports_mixed_awareness_rather_than_crashing(self, allocator):
        """N-10: a malformed pair produces a record, never an exception."""
        record = make_record(allocator)
        object.__setattr__(record, "executed_at", datetime(2026, 6, 1))
        result = xv5_execution_precedes_observation(ctx(record))
        assert result.failed
        assert "naive" in result.detail

    def test_xv5_detects_reordered_timestamps(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record, "executed_at", OBSERVED_AT + timedelta(days=1))
        result = xv5_execution_precedes_observation(ctx(record))
        assert result.failed
        assert "before it was caused" in result.detail

    def test_timestamps_must_be_datetimes(self, allocator):
        with pytest.raises(ExecutionRecordError):
            make_record(allocator, executed_at="2026-06-01")

    def test_long_observation_lag_permitted(self, allocator):
        """Outcomes materialise over extended periods. [IOM section 3.8]"""
        record = make_record(
            allocator, outcome_observed_at=EXECUTED_AT + timedelta(days=900)
        )
        assert record.observation_lag.days == 900
        assert not xv5_execution_precedes_observation(ctx(record)).failed


# ===========================================================================
# X-V6  verification  [M-47]
# ===========================================================================

class TestOutcomeVerification:
    def test_required_at_construction(self, allocator):
        with pytest.raises(VerificationError) as exc:
            make_record(allocator, outcome_verification="")
        assert "taught anything" in str(exc.value)

    def test_xv6_passes_and_records_the_open_marker(self, allocator):
        result = xv6_verification_present(ctx(make_record(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "M-47 open" in result.detail

    def test_no_verification_standard_invented(self, allocator):
        """M-47 must stay open: any verification text is accepted."""
        for text in ("audited", "<PARTIAL - MISSING-47>", "someone said so"):
            record = make_record(allocator, outcome_verification=text)
            assert not xv6_verification_present(ctx(record)).failed

    def test_xv6_detects_a_stripped_verification(self, allocator):
        record = make_record(allocator)
        object.__setattr__(record, "outcome_verification", "  ")
        result = xv6_verification_present(ctx(record))
        assert result.failed
        assert "taught anything" in result.detail


# ===========================================================================
# Rule-set hygiene
# ===========================================================================

class TestRuleSetHygiene:
    def test_six_rules_registered(self, store):
        assert {f"X-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)
        assert len(EXECUTION_RULES) == 6

    def test_rule_ids_in_order(self):
        assert [r.rule_id for r in EXECUTION_RULES] == [
            f"X-V{i}" for i in range(1, 7)
        ]

    @pytest.mark.parametrize("rule", EXECUTION_RULES)
    def test_every_rule_skips_non_records(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert rule(AcceptanceContext(attributes=attributes)).outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", EXECUTION_RULES)
    def test_every_rule_skips_without_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EXECUTION_RECORD,
            (("obj-so-1", ObjectType.SOLUTION),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Execution Record payload" in result.detail

    def test_earlier_stages_unaffected(self, store, allocator):
        """Backward compatibility: the blocked type blocks nothing else."""
        solution, _ = solution_and_opportunity(store, allocator)
        assert solution.status is ObjectStatus.ACTIVE


# ===========================================================================
# X-I1..X-I4  integrity
# ===========================================================================

class TestExecutionIntegrity:
    def test_clean_store_holds(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert store.executions.integrity().verify() == ()

    @pytest.mark.parametrize(
        "valence", sorted(PROTECTED_VALENCES, key=lambda v: v.value)
    )
    def test_protected_outcome_cannot_be_rejected_at_construction(
        self, allocator, valence
    ):
        """X-I1: survivorship bias closed at the earliest point."""
        with pytest.raises(UnfavourableSuppressionError) as exc:
            make_record(
                allocator, valence=valence,
                status=ObjectStatus.REJECTED, status_reason="unwelcome",
            )
        assert "never an unwelcome result" in str(exc.value)

    def test_favourable_outcome_may_be_rejected_as_unverifiable(self, allocator):
        """REJECTED stays available for a genuinely unusable record."""
        record = make_record(
            allocator, valence=OutcomeValence.FAVOURABLE,
            status=ObjectStatus.REJECTED, status_reason="unverifiable",
        )
        assert record.status is ObjectStatus.REJECTED

    def test_xi1_detects_a_rejected_unfavourable_outcome(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        record = record_for(
            store, allocator, solution, opportunity_ref,
            valence=OutcomeValence.UNFAVOURABLE,
        )
        stored = force_persist(store, record)
        store._objects[stored.object_id] = store._objects[
            stored.object_id
        ].__class__(
            attributes=stored.attributes.with_status(
                ObjectStatus.REJECTED, "filed away"
            ),
            lineage=store._objects[stored.object_id].lineage,
        )
        violations = store.executions.integrity().verify()
        assert any(v.constraint_id == "X-I1" for v in violations)
        assert "never an unwelcome result" in "".join(
            v.detail for v in violations
        )

    @pytest.mark.parametrize(
        "status", [ObjectStatus.ARCHIVED, ObjectStatus.RETRACTED]
    )
    def test_xi1_detects_retiring_while_the_solution_lives(
        self, store, allocator, executed, status
    ):
        solution, opportunity_ref = executed
        stored = force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                valence=OutcomeValence.UNFAVOURABLE,
            ),
        )
        store.transition(stored.object_id, status, "withdrawn")
        assert store.get(solution.object_id).status is ObjectStatus.ACTIVE
        assert any(
            v.constraint_id == "X-I1" and "the solution was not" in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi1_permits_retiring_alongside_the_solution(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        stored = force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                valence=OutcomeValence.UNFAVOURABLE,
            ),
        )
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        store.transition(solution.object_id, ObjectStatus.ARCHIVED, "retention")
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I1"
        ]

    def test_xi1_detects_gutted_attribution(self, store, allocator, executed):
        solution, opportunity_ref = executed
        record = record_for(
            store, allocator, solution, opportunity_ref,
            valence=OutcomeValence.UNFAVOURABLE,
        )
        force_persist(store, record)
        object.__setattr__(record.attribution_assessment, "reasoning", "  ")
        assert any(
            v.constraint_id == "X-I1" and "suppressed in substance" in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi1_ignores_a_favourable_outcome(self, store, allocator, executed):
        solution, opportunity_ref = executed
        stored = force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                valence=OutcomeValence.FAVOURABLE,
            ),
        )
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I1"
        ]

    def test_xi2_detects_a_modified_solution(self, store, allocator, executed):
        """Ground truth observes; it does not revise what it judges."""
        from oip.contract import Confidence

        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        object.__setattr__(
            store._objects[solution.object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        violations = store.executions.integrity().verify()
        assert any(v.constraint_id == "X-I2" for v in violations)
        assert "never modifies what it evaluates" in "".join(
            v.detail for v in violations
        )

    def test_xi2_detects_a_modified_opportunity(self, store, allocator, executed):
        """Both the Solution AND the Opportunity are protected."""
        from oip.contract import Confidence

        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        object.__setattr__(
            store._objects[opportunity_ref].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        assert any(
            v.constraint_id == "X-I2" and opportunity_ref in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi2_detects_a_vanished_target(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        del store._objects[solution.object_id]
        assert any(
            v.constraint_id == "X-I2" and "no longer retrievable" in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi3_detects_total_attribution_despite_confounders(
        self, store, allocator, executed
    ):
        """X-I3: self-contradiction between attribution and disclosure."""
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                external_factors=("seasonal variation",),
                attribution_assessment=AttributionAssessment(
                    ("the entire improvement",), (), "all of it was us"
                ),
            ),
        )
        violations = store.executions.integrity().verify()
        assert any(v.constraint_id == "X-I3" for v in violations)
        assert "nothing is marked unattributable" in "".join(
            v.detail for v in violations
        )

    def test_xi3_detects_an_unaccounted_deviation(
        self, store, allocator, executed
    ):
        """The outcome tests something other than what was proposed.

        The reasoning here engages only with the outcome, never with the
        disclosed departure from the specified Solution.
        """
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("rollout scope reduced",),
                attribution_assessment=attribution(
                    reasoning="Complaint reduction follows from the change."
                ),
            ),
        )
        assert any(
            v.constraint_id == "X-I3" and "other than what was proposed" in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi3_accepts_an_accounted_deviation(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("cohort narrower than specified",),
                attribution_assessment=attribution(
                    reasoning=(
                        "The cohort narrower than specified limits how far "
                        "this generalises."
                    )
                ),
            ),
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]

    def test_xi3_accepts_honest_partial_attribution(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                external_factors=("seasonal variation",),
            ),
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]

    def test_xi4_detects_a_missing_solution(self, store, allocator, executed):
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        force_persist(store, record)
        del store._objects[solution.object_id]
        assert any(
            v.constraint_id == "X-I4" and "attached to nothing" in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi4_detects_a_non_solution_reference(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        force_persist(store, record)
        object.__setattr__(record, "outcome_of_solution", opportunity_ref)
        assert any(
            v.constraint_id == "X-I4" and "not a Solution" in v.detail
            for v in store.executions.integrity().verify()
        )

    def test_xi4_detects_retargeting_across_versions(self, store, allocator):
        """Outcomes accumulate against the version actually run. [X-I4]"""
        first_solution, first_opportunity = solution_and_opportunity(
            store, allocator
        )
        other_solution, _ = solution_and_opportunity(store, allocator)

        original = record_for(
            store, allocator, first_solution, first_opportunity
        )
        stored = force_persist(store, original)
        store.transition(
            stored.object_id, ObjectStatus.SUPERSEDED, "further outcomes"
        )
        successor = allocator.succeed(stored.attributes.identity)
        retargeted = make_record(
            allocator, other_solution.object_id,
            opportunity_ref=first_opportunity, identity=successor,
            upstream_ceiling=other_solution.attributes.confidence.effective_confidence,
        )
        force_persist(store, retargeted)
        violations = store.executions.integrity().verify()
        assert any(
            v.constraint_id == "X-I4" and "version actually run" in v.detail
            for v in violations
        )

    def test_xi4_accepts_stable_targeting_across_versions(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        store.transition(
            stored.object_id, ObjectStatus.SUPERSEDED, "further outcomes"
        )
        successor = allocator.succeed(stored.attributes.identity)
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref, identity=successor
            ),
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I4"
        ]

    def test_recorded_target_count(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert store.executions.integrity().recorded_target_count == 2

    def test_unregistered_records_skipped(self, store, allocator):
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.executions.integrity().verify() == ()

    def test_verifier_constructible_standalone(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        verifier = ExecutionIntegrity(
            record_of=store.executions.get, store=store
        )
        assert verifier.verify() == ()

    def test_recording_skips_unresolvable_targets(self, store, allocator):
        verifier = store.executions.integrity()
        verifier.record(make_record(allocator))
        assert verifier.recorded_target_count == 0


# ===========================================================================
# Registry
# ===========================================================================

class TestRegistry:
    def test_for_solution_locates_outcomes(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert len(store.executions.for_solution(solution.object_id)) == 1
        assert store.executions.for_solution("obj-absent") == ()

    def test_unfavourable_outcomes_retained(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                valence=OutcomeValence.UNFAVOURABLE,
            ),
        )
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                valence=OutcomeValence.FAVOURABLE,
            ),
        )
        assert len(store.executions.unfavourable_outcomes()) == 1

    def test_active_records(self, store, allocator, executed):
        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert len(store.executions.active_records()) == 1
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.executions.active_records() == ()

    def test_conflicting_reports_surfaced(self, store, allocator, executed):
        """Disagreement is information; no winner is selected."""
        solution, opportunity_ref = executed
        for valence in (OutcomeValence.FAVOURABLE, OutcomeValence.UNFAVOURABLE):
            force_persist(
                store,
                record_for(
                    store, allocator, solution, opportunity_ref, valence=valence
                ),
            )
        conflicts = store.executions.conflicts_for(solution.object_id)
        assert len(conflicts) == 1

    def test_agreeing_reports_are_not_conflicts(self, store, allocator, executed):
        solution, opportunity_ref = executed
        for _ in range(2):
            force_persist(
                store,
                record_for(
                    store, allocator, solution, opportunity_ref,
                    valence=OutcomeValence.MIXED,
                ),
            )
        assert store.executions.conflicts_for(solution.object_id) == ()

    def test_registry_memoised(self, store):
        assert store.executions is store.executions


# ===========================================================================
# Lineage, graph, cascade
# ===========================================================================

class TestPipelineIntegration:
    def test_reaches_evidence_and_is_a_sibling_branch_of_validation(
        self, store, allocator, executed
    ):
        """IOM "Depth 7" is stage-1 arithmetic, not a lineage-edge count.

        ExecutionRecord and Validation BOTH derive from Solution under the
        ratified R-6 legality matrix, so they are sibling branches at the
        same lineage depth: 7 nodes / 6 edges from Evidence. The IOM's per-
        type "Depth N" labels equal stage-1 for every type, which assumes a
        single linear chain and does not hold where the pipeline forks.
        The legality matrix governs; this is a documentation inconsistency,
        recorded rather than worked around.
        """
        from tests.test_validation import write_validation_from

        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.depth_to_evidence(stored.object_id) == 6
        assert len(store.graph.path_to_evidence(stored.object_id).object_ids) == 7

        validation = write_validation_from(store, allocator, solution)
        assert store.graph.depth_to_evidence(validation.object_id) == 6
        assert store.graph.parents(stored.object_id) == store.graph.parents(
            validation.object_id
        )

    def test_lineage_edges_indexed(self, store, allocator, executed):
        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset({solution.object_id})

    def test_graph_rebuildable(self, store, allocator, executed):
        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_outcome_of_relationship_is_legal(self):
        from oip.relationships import is_legal

        assert is_legal(
            RelationshipType.OUTCOME_OF,
            ObjectType.EXECUTION_RECORD, ObjectType.SOLUTION,
        )

    def test_contradicts_legal_between_records(self):
        from oip.relationships import is_legal

        assert is_legal(
            RelationshipType.CONTRADICTS,
            ObjectType.EXECUTION_RECORD, ObjectType.EXECUTION_RECORD,
        )

    def test_confidence_bounded_by_solution(self, store, allocator, executed):
        solution, opportunity_ref = executed
        record = record_for(store, allocator, solution, opportunity_ref)
        ceiling = solution.attributes.confidence.effective_confidence
        assert record.attributes.confidence.effective_confidence <= ceiling

    def test_confidence_inflation_rejected(self, store, allocator, executed):
        solution, opportunity_ref = executed
        record = make_record(
            allocator, solution.object_id, opportunity_ref=opportunity_ref,
            support=0.99, assertion=0.99,
        )
        result = evaluate(store, record)
        assert "V5" in [r.rule_id for r in result.results if r.failed]

    def test_low_assertion_confidence_is_appropriate(self, allocator):
        """R-3: attribution certainty is typically low here."""
        record = make_record(allocator, support=0.55, assertion=0.20)
        assert record.attributes.confidence.effective_confidence <= 0.20

    def test_cascade_invalidates_the_record(self, store, allocator, executed):
        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_cascade_is_not_suppression(self, store, allocator, executed):
        solution, opportunity_ref = executed
        stored = force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                valence=OutcomeValence.UNFAVOURABLE,
            ),
        )
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I1"
        ]

    def test_universal_integrity_holds(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert store.verify_integrity().holds

    def test_all_eight_type_verifiers_hold(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert store.evidence.integrity().verify() == ()
        assert store.facts.integrity().verify() == ()
        assert store.problems.integrity().verify() == ()
        assert store.patterns.integrity().verify() == ()
        assert store.opportunities.integrity().verify() == ()
        assert store.solutions.integrity().verify() == ()
        assert store.validations.integrity().verify() == ()
        assert store.executions.integrity().verify() == ()

    def test_evidence_may_never_derive_from_a_record(
        self, store, allocator, executed
    ):
        """AD-05: not even ground truth may become Evidence."""
        from oip.evidence import Evidence, EvidenceContent, ExternalOriginError
        from tests.test_evidence import provenance

        solution, opportunity_ref = executed
        stored = force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((stored.object_id, ObjectType.EXECUTION_RECORD),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes, provenance=provenance(),
                content=EvidenceContent.full("outcome text"),
            )


# ===========================================================================
# Concurrency  [N-11]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_writes_all_refused_identically(
        self, store, allocator, executed
    ):
        """C-02 must hold under concurrency, not merely in sequence."""
        solution, opportunity_ref = executed
        refusals: list[tuple[str, ...]] = []
        accepted: list[str] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            record = record_for(store, allocator, solution, opportunity_ref)
            barrier.wait()
            try:
                accepted.append(store.write_execution_record(record).object_id)
            except WriteRejectedError as exc:
                refusals.append(exc.failure.rule_ids)

        threads = [threading.Thread(target=writer) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert accepted == []
        assert len(refusals) == 8
        assert all("V7" in ids for ids in refusals)
        assert len(store.executions) == 0

    def test_concurrent_forced_writes_serialise(self, store, allocator, executed):
        """When C-02 closes, the write path must already be thread-safe."""
        solution, opportunity_ref = executed
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer() -> None:
            record = record_for(store, allocator, solution, opportunity_ref)
            barrier.wait()
            try:
                with store._lock:
                    written.append(force_persist(store, record).object_id)
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


# ===========================================================================
# Adversarial
# ===========================================================================

class TestAdversarial:
    def test_authority_cannot_be_smuggled_via_the_payload(
        self, store, allocator, executed
    ):
        """No combination of engine and status gets a record accepted."""
        solution, opportunity_ref = executed
        for engine in Engine:
            for status, reason in (
                (ObjectStatus.ACTIVE, None),
                (ObjectStatus.PROPOSED, "awaiting"),
            ):
                record = record_for(
                    store, allocator, solution, opportunity_ref,
                    engine=engine, status=status, status_reason=reason,
                )
                with pytest.raises(WriteRejectedError) as exc:
                    store.write_execution_record(record)
                assert "V7" in exc.value.failure.rule_ids

    def test_a_second_record_cannot_launder_a_modified_target(
        self, store, allocator, executed
    ):
        """The X-I2 snapshot must not reset on a later attach."""
        from oip.contract import Confidence

        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        object.__setattr__(
            store._objects[solution.object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert any(
            v.constraint_id == "X-I2"
            for v in store.executions.integrity().verify()
        )

    def test_payload_survives_the_registry_round_trip(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        record = record_for(
            store, allocator, solution, opportunity_ref,
            valence=OutcomeValence.UNFAVOURABLE,
            outcome_magnitude="complaints down 40%",
            partial_outcomes=("week 4",),
        )
        stored = force_persist(store, record)
        payload = store.get_execution_record(stored.object_id)
        assert payload.outcome_valence is OutcomeValence.UNFAVOURABLE
        assert payload.outcome_magnitude == "complaints down 40%"
        assert payload.predicted_by == opportunity_ref

    def test_graph_rebuild_does_not_disturb_integrity(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        store.rebuild_graph()
        assert store.executions.integrity().verify() == ()

    def test_deviation_detection_is_case_insensitive(self, store, allocator, executed):
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("Narrower Cohort",),
                attribution_assessment=attribution(
                    reasoning="The narrower cohort constrains generalisation."
                ),
            ),
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(valence=st.sampled_from(list(OutcomeValence)))
def test_protected_valences_never_rejectable(valence):
    """X-I1 over every defined valence."""
    allocator = IdentityAllocator()
    kwargs = dict(
        valence=valence, status=ObjectStatus.REJECTED, status_reason="filed"
    )
    if valence in PROTECTED_VALENCES:
        with pytest.raises(UnfavourableSuppressionError):
            make_record(allocator, **kwargs)
    else:
        assert make_record(allocator, **kwargs).status is ObjectStatus.REJECTED


@settings(max_examples=200, deadline=None)
@given(days=st.integers(min_value=-400, max_value=400))
def test_timing_ordering_enforced_over_arbitrary_offsets(days):
    """X-V5 fails exactly when observation precedes execution."""
    allocator = IdentityAllocator()
    observed = EXECUTED_AT + timedelta(days=days)
    if days >= 0:
        record = make_record(allocator, outcome_observed_at=observed)
        assert not xv5_execution_precedes_observation(ctx(record)).failed
    else:
        with pytest.raises(OutcomeTimingError):
            make_record(allocator, outcome_observed_at=observed)


@settings(max_examples=200, deadline=None)
@given(verification=st.text(max_size=30))
def test_verification_presence_required_value_unconstrained(verification):
    """M-47: presence is enforceable, adequacy is not."""
    allocator = IdentityAllocator()
    if verification.strip():
        record = make_record(allocator, outcome_verification=verification)
        assert not xv6_verification_present(ctx(record)).failed
    else:
        with pytest.raises(VerificationError):
            make_record(allocator, outcome_verification=verification)


@settings(max_examples=200, deadline=None)
@given(
    attributable=st.integers(min_value=0, max_value=4),
    not_attributable=st.integers(min_value=0, max_value=4),
)
def test_attribution_must_distinguish_something(attributable, not_attributable):
    """X-V3 over arbitrary attribution splits."""
    a = tuple(f"effect-{i}" for i in range(attributable))
    n = tuple(f"other-{i}" for i in range(not_attributable))
    if attributable or not_attributable:
        assessment = AttributionAssessment(a, n, "reasoned")
        assert assessment.claims_total_attribution == (
            bool(a) and not n
        )
    else:
        with pytest.raises(AttributionError):
            AttributionAssessment(a, n, "reasoned")


@settings(max_examples=150, deadline=None)
@given(engine=st.sampled_from(list(Engine)))
def test_no_engine_ever_holds_authority(engine):
    """C-02 over every engine in the closed vocabulary."""
    assert CREATE_AUTHORITY.get(ObjectType.EXECUTION_RECORD) is not engine


@settings(max_examples=150, deadline=None)
@given(
    left=st.sampled_from(list(OutcomeValence)),
    right=st.sampled_from(list(OutcomeValence)),
)
def test_conflict_is_exactly_valence_inequality(left, right):
    allocator = IdentityAllocator()
    a = make_record(allocator, valence=left)
    b = make_record(allocator, valence=right)
    assert (a.outcome_valence is not b.outcome_valence) == (left is not right)


# ===========================================================================
# Regression: X-I3 must not accept a hand-wave
# ===========================================================================

class TestDeviationAccountRegression:
    """Regression for a defect found by adversarial probing.

    X-I3 originally accepted any reasoning containing the substring
    "deviat". A record disclosing "cohort narrowed" while reasoning "No
    deviations of note occurred" therefore passed -- a hand-wave that
    contradicts the record's own disclosure, satisfying the check by
    accident. The mention test now requires the deviation's own content
    words.
    """

    def test_hand_wave_no_longer_satisfies_the_check(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("cohort narrowed",),
                attribution_assessment=attribution(
                    reasoning="No deviations of note occurred."
                ),
            ),
        )
        assert any(
            v.constraint_id == "X-I3" and "other than what was proposed" in v.detail
            for v in store.executions.integrity().verify()
        )

    @pytest.mark.parametrize(
        "reasoning",
        [
            "The narrowed cohort limits how far this generalises.",
            "A NARROWED COHORT constrains the finding.",
            "Cohort narrowing means the result is partial.",
        ],
    )
    def test_a_genuine_account_passes(
        self, store, allocator, executed, reasoning
    ):
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("cohort narrowed",),
                attribution_assessment=attribution(reasoning=reasoning),
            ),
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]

    def test_no_false_positive_without_a_deviation(
        self, store, allocator, executed
    ):
        solution, opportunity_ref = executed
        force_persist(
            store, record_for(store, allocator, solution, opportunity_ref)
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]

    def test_a_deviation_with_no_content_words_is_not_faulted(
        self, store, allocator, executed
    ):
        """Nothing discriminating to look for; silence is not detectable."""
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("a b c",),
            ),
        )
        assert not [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]

    def test_both_xi3_checks_fire_independently(self, store, allocator, executed):
        """Deviation unaccounted AND total attribution: two distinct faults."""
        solution, opportunity_ref = executed
        force_persist(
            store,
            record_for(
                store, allocator, solution, opportunity_ref,
                execution_deviations=("narrower cohort",),
                attribution_assessment=AttributionAssessment(
                    ("all of it",), (), "ours entirely"
                ),
            ),
        )
        violations = [
            v for v in store.executions.integrity().verify()
            if v.constraint_id == "X-I3"
        ]
        assert len(violations) == 2


# ===========================================================================
# Forward compatibility: the write path when C-02 closes
# ===========================================================================

class TestWritePathReadyForC02:
    """The write path is unreachable today and must still be correct.

    C-02 blocks every write, so the post-acceptance branch of
    `write_execution_record` never executes. That branch is exactly what
    T08.1.2 will depend on, and a latent defect there would surface only
    after the escalation closes. These tests grant authority TEMPORARILY,
    inside the test only, to prove the path works -- then restore the map.
    No production code assigns authority.
    """

    @pytest.fixture()
    def authority_granted(self):
        """Temporarily simulate C-02's resolution. Test-local only."""
        CREATE_AUTHORITY[ObjectType.EXECUTION_RECORD] = Engine.RESEARCH
        try:
            yield Engine.RESEARCH
        finally:
            del CREATE_AUTHORITY[ObjectType.EXECUTION_RECORD]

    def test_authority_map_is_restored_afterwards(self):
        """Guard: the fixture must not leak into other tests."""
        assert ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY

    def test_write_succeeds_once_authority_exists(
        self, store, allocator, executed, authority_granted
    ):
        solution, opportunity_ref = executed
        stored = store.write_execution_record(
            record_for(
                store, allocator, solution, opportunity_ref,
                engine=authority_granted,
            )
        )
        assert stored.status is ObjectStatus.ACTIVE
        assert store.get_execution_record(stored.object_id) is not None

    def test_written_payload_is_complete(
        self, store, allocator, executed, authority_granted
    ):
        solution, opportunity_ref = executed
        stored = store.write_execution_record(
            record_for(
                store, allocator, solution, opportunity_ref,
                engine=authority_granted,
                valence=OutcomeValence.UNFAVOURABLE,
                outcome_magnitude="complaints down 40%",
                external_factors=("seasonal variation",),
                partial_outcomes=("week 4",),
            )
        )
        payload = store.get_execution_record(stored.object_id)
        assert payload.outcome_valence is OutcomeValence.UNFAVOURABLE
        assert payload.outcome_magnitude == "complaints down 40%"
        assert payload.external_factors == ("seasonal variation",)
        assert payload.partial_outcomes == ("week 4",)
        assert payload.predicted_by == opportunity_ref

    def test_written_record_passes_every_verifier(
        self, store, allocator, executed, authority_granted
    ):
        solution, opportunity_ref = executed
        store.write_execution_record(
            record_for(
                store, allocator, solution, opportunity_ref,
                engine=authority_granted,
            )
        )
        assert store.executions.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_wrong_engine_still_refused_under_authority(
        self, store, allocator, executed, authority_granted
    ):
        """Granting one engine authority must not grant it to all."""
        solution, opportunity_ref = executed
        with pytest.raises(WriteRejectedError) as exc:
            store.write_execution_record(
                record_for(
                    store, allocator, solution, opportunity_ref,
                    engine=Engine.FEEDBACK,
                )
            )
        assert "V7" in exc.value.failure.rule_ids

    def test_x_rules_still_enforced_under_authority(
        self, store, allocator, executed, authority_granted
    ):
        """Authority removes V7, not the type's own rules."""
        solution, opportunity_ref = executed
        record = record_for(
            store, allocator, solution, opportunity_ref, engine=authority_granted
        )
        object.__setattr__(record, "outcome_verification", "")
        with pytest.raises(WriteRejectedError) as exc:
            store.write_execution_record(record)
        assert "X-V6" in exc.value.failure.rule_ids
