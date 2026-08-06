"""Contract tests for the universal object attribute set.

Task: T01.1.2

Architecture References:
- V1   All 17 required attributes present and non-empty
- V8   observed_at <= asserted_at <= produced_at
- V9   status_reason required when status != ACTIVE
- R-2  Seven-state lifecycle; terminal states cannot transition
- R-3  Two-component confidence with ceiling
- N-5  Tenancy discriminator reserved
- N-13 Explanation skeleton
- N-16 independent_source_count carried on every object

Acceptance criteria under test:
  AC1  All 17 attributes present on every persisted object
  AC2  Missing attribute blocks acceptance
  AC3  Tenancy discriminator reserved per N-5
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oip.contract import (
    DEFAULT_TENANCY,
    REQUIRED_ATTRIBUTE_NAMES,
    Confidence,
    ConfidenceCeilingError,
    ConfidenceRangeError,
    ContractError,
    Explanation,
    ExplanationError,
    LineageRef,
    MissingAttributeError,
    StatusReasonError,
    TemporalOrderError,
    UniversalAttributes,
    utc_now,
)
from oip.enums import (
    CREATE_AUTHORITY,
    ConfidenceBand,
    Engine,
    ObjectStatus,
    ObjectType,
    RelationshipType,
)
from oip.identity import IdentityAllocator

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


@pytest.fixture()
def allocator() -> IdentityAllocator:
    return IdentityAllocator()


def make_explanation(**overrides) -> Explanation:
    kwargs = {
        "objects_referenced": ("obj-upstream-1",),
        "criteria_applied": ("sufficiency-threshold",),
        "reasoning": "Derived from a single corroborated upstream claim.",
    }
    kwargs.update(overrides)
    return Explanation(**kwargs)


def make_attributes(allocator: IdentityAllocator, **overrides) -> UniversalAttributes:
    identity = overrides.pop("identity", None) or allocator.new_object()
    kwargs = {
        "identity": identity,
        "object_type": ObjectType.FACT,
        "produced_by_engine": Engine.FACT_EXTRACTION,
        "produced_at": T0 + timedelta(hours=2),
        "engine_configuration_ref": "cfg-v1",
        "derives_from": (LineageRef("obj-ev-1", ObjectType.EVIDENCE),),
        "explanation": make_explanation(),
        "evidence_reachable": True,
        "confidence": Confidence.create(0.62, 0.84),
        "asserted_at": T0 + timedelta(hours=1),
        "observed_at": T0,
        "status": ObjectStatus.PROPOSED,
        "status_reason": "awaiting acceptance",
        "independent_source_count": 3,
    }
    kwargs.update(overrides)
    return UniversalAttributes(**kwargs)


# ---------------------------------------------------------------------------
# AC1 -- all 17 attributes present
# ---------------------------------------------------------------------------

class TestSeventeenAttributes:
    def test_contract_defines_exactly_seventeen(self):
        assert len(REQUIRED_ATTRIBUTE_NAMES) == 17
        assert len(set(REQUIRED_ATTRIBUTE_NAMES)) == 17

    def test_every_required_attribute_is_present(self, allocator):
        mapping = make_attributes(allocator).to_mapping()
        for name in REQUIRED_ATTRIBUTE_NAMES:
            assert name in mapping, f"{name} absent from the contract"

    def test_no_required_attribute_is_empty(self, allocator):
        mapping = make_attributes(allocator).to_mapping()
        for name in REQUIRED_ATTRIBUTE_NAMES:
            if name == "status_reason":
                continue  # legitimately None when ACTIVE
            assert mapping[name] not in (None, "", ()), f"{name} is empty"

    def test_identity_supplies_three_of_the_seventeen(self, allocator):
        attrs = make_attributes(allocator)
        assert attrs.object_id == attrs.identity.object_id
        assert attrs.lineage_id == attrs.identity.lineage_id
        assert attrs.version == attrs.identity.version


# ---------------------------------------------------------------------------
# AC2 -- missing attribute blocks acceptance
# ---------------------------------------------------------------------------

class TestMissingAttributesRejected:
    @pytest.mark.parametrize(
        "field,value",
        [
            ("engine_configuration_ref", ""),
            ("engine_configuration_ref", None),
            ("tenancy", ""),
            ("object_type", "Fact"),
            ("produced_by_engine", "FactExtraction"),
            ("evidence_reachable", "yes"),
            ("produced_at", "2026-03-01"),
            ("asserted_at", None),
        ],
    )
    def test_invalid_required_attribute_is_rejected(self, allocator, field, value):
        with pytest.raises(MissingAttributeError):
            make_attributes(allocator, **{field: value})

    def test_explanation_must_be_an_explanation(self, allocator):
        with pytest.raises(MissingAttributeError):
            make_attributes(allocator, explanation="because")

    def test_confidence_must_be_a_confidence(self, allocator):
        with pytest.raises(MissingAttributeError):
            make_attributes(allocator, confidence=0.5)

    def test_negative_source_count_rejected(self, allocator):
        with pytest.raises(ContractError):
            make_attributes(allocator, independent_source_count=-1)


# ---------------------------------------------------------------------------
# AC3 -- tenancy discriminator reserved [N-5]
# ---------------------------------------------------------------------------

class TestTenancyReserved:
    def test_tenancy_defaults_to_reserved_value(self, allocator):
        assert make_attributes(allocator).tenancy == DEFAULT_TENANCY

    def test_tenancy_is_present_on_every_object(self, allocator):
        for object_type in ObjectType:
            attrs = make_attributes(allocator, object_type=object_type)
            assert attrs.tenancy

    def test_tenancy_may_be_set_but_never_empty(self, allocator):
        attrs = make_attributes(allocator, tenancy="tenant-a")
        assert attrs.tenancy == "tenant-a"
        with pytest.raises(MissingAttributeError):
            make_attributes(allocator, tenancy="")


# ---------------------------------------------------------------------------
# V8 -- temporal ordering
# ---------------------------------------------------------------------------

class TestTemporalOrdering:
    def test_valid_ordering_accepted(self, allocator):
        attrs = make_attributes(allocator)
        assert attrs.observed_at <= attrs.asserted_at <= attrs.produced_at

    def test_observed_after_asserted_rejected(self, allocator):
        with pytest.raises(TemporalOrderError):
            make_attributes(allocator, observed_at=T0 + timedelta(hours=5))

    def test_asserted_after_produced_rejected(self, allocator):
        with pytest.raises(TemporalOrderError):
            make_attributes(allocator, asserted_at=T0 + timedelta(hours=9))

    def test_equal_timestamps_accepted(self, allocator):
        attrs = make_attributes(
            allocator, observed_at=T0, asserted_at=T0, produced_at=T0
        )
        assert attrs.observed_at == attrs.produced_at

    def test_observation_long_before_assertion_accepted(self, allocator):
        """R-4: observed_at may substantially precede assertion."""
        attrs = make_attributes(allocator, observed_at=T0 - timedelta(days=365))
        assert attrs.observed_at < attrs.asserted_at


# ---------------------------------------------------------------------------
# V9 / R-2 -- status and status_reason
# ---------------------------------------------------------------------------

class TestStatusAndReason:
    def test_active_needs_no_reason(self, allocator):
        attrs = make_attributes(
            allocator, status=ObjectStatus.ACTIVE, status_reason=None
        )
        assert attrs.status_reason is None

    @pytest.mark.parametrize(
        "status",
        [s for s in ObjectStatus if s is not ObjectStatus.ACTIVE],
    )
    def test_non_active_requires_reason(self, allocator, status):
        with pytest.raises(StatusReasonError):
            make_attributes(allocator, status=status, status_reason=None)

    @pytest.mark.parametrize(
        "status",
        [s for s in ObjectStatus if s is not ObjectStatus.ACTIVE],
    )
    def test_blank_reason_is_not_a_reason(self, allocator, status):
        with pytest.raises(StatusReasonError):
            make_attributes(allocator, status=status, status_reason="   ")

    def test_terminal_states_cannot_transition(self, allocator):
        for status in ObjectStatus:
            if not status.is_terminal:
                continue
            attrs = make_attributes(allocator, status=status, status_reason="done")
            with pytest.raises(ContractError):
                attrs.with_status(ObjectStatus.ACTIVE)

    def test_status_transition_returns_new_instance(self, allocator):
        attrs = make_attributes(allocator, status=ObjectStatus.PROPOSED,
                                status_reason="awaiting")
        moved = attrs.with_status(ObjectStatus.ACTIVE, None)
        assert moved is not attrs
        assert attrs.status is ObjectStatus.PROPOSED  # original unchanged [I1]
        assert moved.status is ObjectStatus.ACTIVE

    def test_status_transition_preserves_content(self, allocator):
        attrs = make_attributes(allocator, status=ObjectStatus.PROPOSED,
                                status_reason="awaiting")
        moved = attrs.with_status(ObjectStatus.ACTIVE, None)
        assert moved.identity == attrs.identity
        assert moved.confidence == attrs.confidence
        assert moved.derives_from == attrs.derives_from
        assert moved.explanation == attrs.explanation


# ---------------------------------------------------------------------------
# R-3 -- confidence
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_two_components_are_independent(self):
        c = Confidence.create(evidential_support=0.9, assertion_confidence=0.2)
        assert c.evidential_support == 0.9
        assert c.assertion_confidence == 0.2

    def test_well_evidenced_low_confidence_is_representable(self):
        """R-3 requires this case to be distinguishable."""
        c = Confidence.create(0.95, 0.15)
        assert c.support_band is ConfidenceBand.VERY_STRONG
        assert c.assertion_band is ConfidenceBand.NEGLIGIBLE

    def test_poorly_evidenced_high_confidence_is_representable(self):
        c = Confidence.create(0.15, 0.95)
        assert c.support_band is ConfidenceBand.NEGLIGIBLE
        assert c.assertion_band is ConfidenceBand.VERY_STRONG

    def test_effective_never_exceeds_own_components(self):
        c = Confidence.create(0.4, 0.9)
        assert c.effective_confidence <= min(0.4, 0.9)

    def test_explicit_ceiling_violation_rejected(self):
        with pytest.raises(ConfidenceCeilingError):
            Confidence(
                evidential_support=0.4,
                assertion_confidence=0.9,
                effective_confidence=0.8,
            )

    def test_upstream_ceiling_applied(self):
        c = Confidence.create(0.9, 0.9, upstream_ceiling=0.55)
        assert c.effective_confidence == 0.55

    @pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -5.0])
    def test_out_of_range_rejected(self, bad):
        with pytest.raises(ConfidenceRangeError):
            Confidence.create(bad, 0.5)
        with pytest.raises(ConfidenceRangeError):
            Confidence.create(0.5, bad)

    def test_booleans_are_not_confidence_values(self):
        with pytest.raises(ConfidenceRangeError):
            Confidence.create(True, 0.5)

    @pytest.mark.parametrize(
        "value,band",
        [
            (0.00, ConfidenceBand.NEGLIGIBLE),
            (0.19, ConfidenceBand.NEGLIGIBLE),
            (0.20, ConfidenceBand.WEAK),
            (0.39, ConfidenceBand.WEAK),
            (0.40, ConfidenceBand.MODERATE),
            (0.59, ConfidenceBand.MODERATE),
            (0.60, ConfidenceBand.STRONG),
            (0.79, ConfidenceBand.STRONG),
            (0.80, ConfidenceBand.VERY_STRONG),
            (1.00, ConfidenceBand.VERY_STRONG),
        ],
    )
    def test_band_boundaries(self, value, band):
        assert ConfidenceBand.for_value(value) is band

    def test_iom_worked_example_reproduced(self):
        """IOM section 4.4: Evidence 0.62 -> Opportunity 0.58, not 0.85.

        Four confident inferential steps over moderate evidence must yield a
        MODERATE conclusion. This is the platform's defence against
        confidence inflation. [R-3]
        """
        evidence = Confidence.create(0.62, 0.90)
        assert evidence.effective_confidence == pytest.approx(0.62)

        fact = Confidence.create(0.71, 0.84, upstream_ceiling=evidence.effective_confidence)
        assert fact.effective_confidence == pytest.approx(0.62)

        problem = Confidence.create(0.66, 0.74, upstream_ceiling=fact.effective_confidence)
        assert problem.effective_confidence == pytest.approx(0.62)

        pattern = Confidence.create(0.64, 0.71, upstream_ceiling=problem.effective_confidence)
        assert pattern.effective_confidence == pytest.approx(0.62)

        opportunity = Confidence.create(
            0.64, 0.58, upstream_ceiling=pattern.effective_confidence
        )
        assert opportunity.effective_confidence == pytest.approx(0.58)
        assert opportunity.band is ConfidenceBand.MODERATE


# ---------------------------------------------------------------------------
# N-13 -- explanation skeleton
# ---------------------------------------------------------------------------

class TestExplanationSkeleton:
    def test_valid_explanation_accepted(self):
        e = make_explanation()
        assert e.objects_referenced and e.criteria_applied and e.reasoning

    def test_must_reference_at_least_one_object(self):
        with pytest.raises(ExplanationError):
            make_explanation(objects_referenced=())

    def test_must_state_criteria(self):
        with pytest.raises(ExplanationError):
            make_explanation(criteria_applied=())

    def test_reasoning_must_be_non_empty(self):
        for blank in ("", "   ", "\n"):
            with pytest.raises(ExplanationError):
                make_explanation(reasoning=blank)

    def test_alternatives_rejected_is_optional(self):
        assert make_explanation().alternatives_rejected == ()
        e = make_explanation(alternatives_rejected=("merged into FA-1",))
        assert len(e.alternatives_rejected) == 1


# ---------------------------------------------------------------------------
# Immutability [R-1, I1]
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_attributes_cannot_be_mutated(self, allocator):
        attrs = make_attributes(allocator)
        for field_name, value in (
            ("object_type", ObjectType.PROBLEM),
            ("status", ObjectStatus.ACTIVE),
            ("engine_configuration_ref", "cfg-v2"),
        ):
            with pytest.raises(Exception):
                setattr(attrs, field_name, value)

    def test_confidence_cannot_be_mutated(self):
        c = Confidence.create(0.5, 0.5)
        with pytest.raises(Exception):
            c.evidential_support = 0.9

    def test_explanation_cannot_be_mutated(self):
        e = make_explanation()
        with pytest.raises(Exception):
            e.reasoning = "different"

    def test_lineage_ref_cannot_be_mutated(self):
        ref = LineageRef("obj-1", ObjectType.EVIDENCE)
        with pytest.raises(Exception):
            ref.object_id = "obj-2"


# ---------------------------------------------------------------------------
# Closed vocabularies [R-2, R-6, R-7]
# ---------------------------------------------------------------------------

class TestClosedVocabularies:
    def test_nine_object_types(self):
        assert len(ObjectType) == 9

    def test_nine_engines(self):
        assert len(Engine) == 9

    def test_seven_statuses(self):
        assert len(ObjectStatus) == 7

    def test_ten_relationship_types(self):
        assert len(RelationshipType) == 10

    def test_five_confidence_bands(self):
        assert len(ConfidenceBand) == 5

    def test_only_evidence_is_root(self):
        roots = [t for t in ObjectType if t.is_root]
        assert roots == [ObjectType.EVIDENCE]

    def test_stages_cover_one_to_nine(self):
        assert sorted(t.stage for t in ObjectType) == list(range(1, 10))

    def test_create_authority_is_unique_per_type(self):
        engines = list(CREATE_AUTHORITY.values())
        assert len(engines) == len(set(engines))

    def test_execution_record_has_no_create_authority(self):
        """C-02 remains open -- no engine may create Execution Records."""
        assert ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY

    def test_orchestration_creates_nothing(self):
        assert Engine.ORCHESTRATION not in CREATE_AUTHORITY.values()

    def test_terminal_states(self):
        terminal = {s for s in ObjectStatus if s.is_terminal}
        assert terminal == {
            ObjectStatus.SUPERSEDED,
            ObjectStatus.REJECTED,
            ObjectStatus.RETRACTED,
            ObjectStatus.INVALIDATED,
            ObjectStatus.ARCHIVED,
        }


class TestUtilities:
    def test_utc_now_is_timezone_aware(self):
        assert utc_now().tzinfo is not None


# ---------------------------------------------------------------------------
# Error-path coverage
# ---------------------------------------------------------------------------

class TestErrorPaths:
    def test_lineage_ref_requires_object_id(self):
        with pytest.raises(MissingAttributeError):
            LineageRef("", ObjectType.EVIDENCE)

    def test_identity_must_be_an_object_identity(self, allocator):
        with pytest.raises(MissingAttributeError):
            make_attributes(allocator, identity="obj-not-an-identity")

    def test_is_root_true_only_for_evidence(self, allocator):
        evidence = make_attributes(
            allocator,
            object_type=ObjectType.EVIDENCE,
            produced_by_engine=Engine.RESEARCH,
            derives_from=(),
        )
        assert evidence.is_root
        assert not make_attributes(allocator, object_type=ObjectType.FACT).is_root

    @pytest.mark.parametrize("bad", [-0.5, 1.5, 100.0])
    def test_band_for_value_rejects_out_of_range(self, bad):
        with pytest.raises(ValueError):
            ConfidenceBand.for_value(bad)
