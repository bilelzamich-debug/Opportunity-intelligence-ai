"""Contract tests for the Validation object type.

Task: T01.7.7

Architecture References:
- V-V1..V-V6  Validation validation rules
- V-I1..V-I4  Validation integrity constraints
- R-2         A negative result is ACTIVE; REJECTED is an unusable record
- R-3         High-confidence negative results are coherent and valuable
- R-6         DERIVES_FROM Solution; TESTS a claim; CONTRADICTS Validation
- M-32        Validation methodology OPEN and BLOCKING -- no vocabulary
- M-31        Gate ownership OPEN: Validation reports, it does not gate
- C-05        Validation / Experiment Registry boundary OPEN

Acceptance criteria under test:
  AC1  Negative result is ACTIVE, never REJECTED
  AC2  tests_claim targets a specific claim, not a whole object
  AC3  scope_limitations required
"""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.enums import Engine, ObjectStatus, ObjectType, RelationshipType
from oip.identity import IdentityAllocator
from oip.store import KnowledgeStore, WriteRejectedError
from oip.validation import (
    PROTECTED_RESULTS,
    VALIDATION_RULES,
    ClaimReference,
    ClaimReferenceError,
    InterpretationError,
    MethodError,
    NegativeResultSuppressionError,
    ResultError,
    ScopeLimitationError,
    Validation,
    ValidationError,
    ValidationIntegrity,
    ValidationResult,
    vv1_tests_a_specific_claim,
    vv2_method_recorded,
    vv3_result_in_defined_set,
    vv4_interpretation_present,
    vv5_scope_limitations_present,
    vv6_method_detail_repeatable,
)
from tests.conftest import T0, build_attrs
from tests.test_solution import assumption, write_opportunities, write_solution_from

VALIDATED_AT = T0 + timedelta(days=60)
METHOD_DETAIL = (
    "Examined response behaviour to existing partial-failure notifications "
    "across three comparable seller tools, using observed remediation rates "
    "within 48 hours as the behavioural indicator."
)
INTERPRETATION = (
    "A1 holds at low failure volumes but not at high ones. This does not "
    "invalidate the solution but materially narrows its claimed value."
)
SCOPE = (
    "Establishes nothing about response to a redesigned reporting mechanism; "
    "does not test A2 or A3."
)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def claim_ref(object_id: str = "obj-so-1", claim_id: str = "A1") -> ClaimReference:
    return ClaimReference(object_id=object_id, claim_id=claim_id)


def make_validation(
    allocator: IdentityAllocator,
    solution_ref: str = "obj-so-1",
    *,
    claim_id: str = "A1",
    result: ValidationResult = ValidationResult.PARTIALLY_SUPPORTED,
    source_count: int = 1,
    upstream_ceiling: float | None = None,
    support: float = 0.58,
    assertion: float = 0.72,
    status: ObjectStatus = ObjectStatus.ACTIVE,
    status_reason: str | None = None,
    **overrides,
) -> Validation:
    identity = overrides.pop("identity", None) or allocator.new_object()
    attributes = overrides.pop("attributes", None) or build_attrs(
        identity,
        ObjectType.VALIDATION,
        ((solution_ref, ObjectType.SOLUTION),),
        status=status,
        status_reason=status_reason,
        source_count=source_count,
        support=support,
        assertion=assertion,
        upstream_ceiling=upstream_ceiling,
    )
    kwargs = {
        "attributes": attributes,
        "tests_claim": overrides.pop(
            "tests_claim", claim_ref(solution_ref, claim_id)
        ),
        "validation_method": overrides.pop(
            "validation_method", "evidence-based behavioural proxy"
        ),
        "method_detail": overrides.pop("method_detail", METHOD_DETAIL),
        "result": result,
        "result_detail": overrides.pop(
            "result_detail", "Remediation declined sharply above 20 items."
        ),
        "result_interpretation": overrides.pop(
            "result_interpretation", INTERPRETATION
        ),
        "validated_at": overrides.pop("validated_at", VALIDATED_AT),
        "scope_limitations": overrides.pop("scope_limitations", SCOPE),
    }
    kwargs.update(overrides)
    return Validation(**kwargs)


def ctx(validation: Validation, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": validation.attributes, "validation": validation}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


def write_solutions(store, allocator, n: int = 1, **overrides):
    stored = []
    for _ in range(n):
        opportunity = write_opportunities(store, allocator, 1)[0]
        stored.append(
            write_solution_from(store, allocator, opportunity, **overrides)
        )
    return stored


def write_validation_from(
    store, allocator, stored_solution, predecessor_id: str | None = None, **overrides
):
    kwargs = {
        "upstream_ceiling": stored_solution.attributes.confidence.effective_confidence,
    }
    kwargs.update(overrides)
    return store.write_validation(
        make_validation(allocator, stored_solution.object_id, **kwargs),
        predecessor_id=predecessor_id,
    )


@pytest.fixture()
def solution(store, allocator):
    return write_solutions(
        store, allocator, 1,
        assumptions=(assumption("A1"), assumption("A2"), assumption("A3")),
    )[0]


# ===========================================================================
# AC1 -- a negative result is ACTIVE, never REJECTED  [V-I1, R-2]
# ===========================================================================

class TestNegativeResultsAreActive:
    """The single most important status rule in the specification."""

    @pytest.mark.parametrize("result", sorted(PROTECTED_RESULTS, key=lambda r: r.value))
    def test_protected_result_cannot_be_rejected_at_construction(
        self, allocator, result
    ):
        with pytest.raises(NegativeResultSuppressionError) as exc:
            make_validation(
                allocator, result=result,
                status=ObjectStatus.REJECTED, status_reason="unwelcome",
            )
        assert "unusable record" in str(exc.value)

    @pytest.mark.parametrize(
        "result",
        [ValidationResult.NOT_SUPPORTED, ValidationResult.PARTIALLY_SUPPORTED],
    )
    def test_negative_result_persists_as_active(
        self, store, allocator, solution, result
    ):
        stored = write_validation_from(store, allocator, solution, result=result)
        assert stored.status is ObjectStatus.ACTIVE
        assert store.get_validation(stored.object_id).is_negative

    def test_high_confidence_negative_is_coherent(self, store, allocator, solution):
        """R-3: the platform can be very certain an assumption is false."""
        stored = write_validation_from(
            store, allocator, solution,
            result=ValidationResult.NOT_SUPPORTED,
            support=0.5, assertion=0.5,
        )
        assert stored.attributes.confidence.effective_confidence > 0.0
        assert store.get_validation(stored.object_id).is_negative

    def test_vi1_detects_a_rejected_negative(self, store, allocator, solution):
        """Suppression after the fact is what the verifier exists to catch."""
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        replacement = store._objects[stored.object_id].__class__(
            attributes=stored.attributes.with_status(
                ObjectStatus.REJECTED, "filed as unusable"
            ),
            lineage=store._objects[stored.object_id].lineage,
        )
        store._objects[stored.object_id] = replacement
        violations = store.validations.integrity().verify()
        assert any(v.constraint_id == "V-I1" for v in violations)
        assert "never an unfavourable finding" in "".join(
            v.detail for v in violations
        )

    def test_vi1_detects_archiving_a_live_claims_negative(
        self, store, allocator, solution
    ):
        """Retiring the finding while the claim still circulates."""
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "tidied away")
        violations = store.validations.integrity().verify()
        assert any(
            v.constraint_id == "V-I1" and "the claim was not" in v.detail
            for v in violations
        )

    def test_vi1_permits_archiving_alongside_its_object(
        self, store, allocator, solution
    ):
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        store.transition(solution.object_id, ObjectStatus.ARCHIVED, "retention")
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I1"
        ]

    def test_vi1_detects_a_gutted_interpretation(self, store, allocator, solution):
        """A finding stripped of meaning is suppressed in substance."""
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        payload = store.get_validation(stored.object_id)
        object.__setattr__(payload, "result_interpretation", "  ")
        assert any(
            v.constraint_id == "V-I1" and "suppressed in substance" in v.detail
            for v in store.validations.integrity().verify()
        )

    def test_vi1_ignores_a_supported_result(self, store, allocator, solution):
        """Only unfavourable findings need protection."""
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.SUPPORTED
        )
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I1"
        ]

    def test_supported_result_may_be_rejected_as_unusable(self, allocator):
        """REJECTED remains available for a genuinely unusable record."""
        v = make_validation(
            allocator, result=ValidationResult.SUPPORTED,
            status=ObjectStatus.REJECTED, status_reason="method inadequate",
        )
        assert v.status is ObjectStatus.REJECTED

    def test_cascade_invalidation_is_not_suppression(
        self, store, allocator, solution
    ):
        """INVALIDATED is a cascade the Validation does not control."""
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I1"
        ]

    def test_negative_results_retained_and_findable(self, store, allocator, solution):
        write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        write_validation_from(
            store, allocator, solution, result=ValidationResult.SUPPORTED,
            claim_id="A2",
        )
        assert len(store.validations.negative_results()) == 1

    def test_result_negativity_classification(self):
        assert ValidationResult.NOT_SUPPORTED.is_negative
        assert ValidationResult.PARTIALLY_SUPPORTED.is_negative
        assert not ValidationResult.SUPPORTED.is_negative
        assert not ValidationResult.INCONCLUSIVE.is_negative
        assert ValidationResult.SUPPORTED.is_favourable

    def test_inconclusive_is_protected_though_not_negative(self):
        """An inconclusive record is also not an unusable one."""
        assert ValidationResult.INCONCLUSIVE in PROTECTED_RESULTS
        assert not ValidationResult.INCONCLUSIVE.is_negative


# ===========================================================================
# AC2 -- tests_claim targets a specific claim  [V-V1]
# ===========================================================================

class TestClaimLevelTargeting:
    def test_claim_id_required(self):
        with pytest.raises(ClaimReferenceError) as exc:
            ClaimReference(object_id="obj-so-1", claim_id="  ")
        assert "whole-object validation" in str(exc.value)

    def test_object_id_required(self):
        with pytest.raises(ClaimReferenceError):
            ClaimReference(object_id="", claim_id="A1")

    def test_tests_claim_required(self, allocator):
        with pytest.raises(ClaimReferenceError):
            make_validation(allocator, tests_claim=None)

    def test_claim_must_be_in_derives_from(self, allocator):
        with pytest.raises(ClaimReferenceError) as exc:
            make_validation(
                allocator, "obj-so-1", tests_claim=claim_ref("obj-so-other", "A1")
            )
        assert "derives from the object containing the claim" in str(exc.value)

    def test_vv1_passes_for_an_existing_claim(self, allocator):
        result = vv1_tests_a_specific_claim(
            ctx(
                make_validation(allocator),
                claims_of_object=lambda oid: frozenset({"A1", "A2"}),
            )
        )
        assert result.outcome is RuleOutcome.PASS
        assert "specifically" in result.detail

    def test_vv1_rejects_a_nonexistent_claim(self, allocator):
        result = vv1_tests_a_specific_claim(
            ctx(
                make_validation(allocator, claim_id="A9"),
                claims_of_object=lambda oid: frozenset({"A1", "A2"}),
            )
        )
        assert result.failed
        assert "does not exist" in result.detail

    def test_vv1_detects_a_stripped_claim_id(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v.tests_claim, "claim_id", "")
        result = vv1_tests_a_specific_claim(ctx(v))
        assert result.failed
        assert "not meaningful" in result.detail

    def test_vv1_detects_an_unresolvable_object(self, allocator):
        result = vv1_tests_a_specific_claim(
            ctx(make_validation(allocator), resolve_type=lambda oid: None)
        )
        assert result.failed
        assert "does not resolve" in result.detail

    def test_vv1_skips_without_a_claim_provider(self, allocator):
        result = vv1_tests_a_specific_claim(ctx(make_validation(allocator)))
        assert result.outcome is RuleOutcome.SKIP
        assert "no claim provider" in result.detail

    def test_vv1_skips_when_object_exposes_no_claims(self, allocator):
        """M-32 supplies no cross-type claim vocabulary; no verdict is faked."""
        result = vv1_tests_a_specific_claim(
            ctx(make_validation(allocator), claims_of_object=lambda oid: None)
        )
        assert result.outcome is RuleOutcome.SKIP
        assert "no claim set" in result.detail

    def test_store_rejects_a_claim_the_solution_lacks(
        self, store, allocator, solution
    ):
        with pytest.raises(WriteRejectedError) as exc:
            write_validation_from(store, allocator, solution, claim_id="A99")
        assert "V-V1" in exc.value.failure.rule_ids

    def test_store_accepts_each_real_assumption(self, store, allocator, solution):
        for claim in ("A1", "A2", "A3"):
            stored = write_validation_from(
                store, allocator, solution, claim_id=claim
            )
            assert stored.status is ObjectStatus.ACTIVE

    def test_multiple_validations_per_solution(self, store, allocator, solution):
        """Claim-level targeting means many tests per object. [T07.3.1]"""
        for claim in ("A1", "A2", "A3"):
            write_validation_from(store, allocator, solution, claim_id=claim)
        assert len(store.validations.for_object(solution.object_id)) == 3
        assert len(store.validations.for_claim(solution.object_id, "A1")) == 1

    def test_untested_claims_are_reportable(self, store, allocator, solution):
        """The untested-critical-assumption failure is invisible unless asked."""
        write_validation_from(store, allocator, solution, claim_id="A1")
        untested = store.validations.untested_claims(
            solution.object_id, ("A1", "A2", "A3")
        )
        assert untested == ("A2", "A3")

    def test_claim_reference_equality(self):
        assert claim_ref("o", "A1") == claim_ref("o", "A1")
        assert claim_ref("o", "A1") != claim_ref("o", "A2")


# ===========================================================================
# AC3 -- scope_limitations required  [V-V5]
# ===========================================================================

class TestScopeLimitations:
    def test_required_at_construction(self, allocator):
        with pytest.raises(ScopeLimitationError) as exc:
            make_validation(allocator, scope_limitations="")
        assert "over-claiming visible" in str(exc.value)

    @pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
    def test_whitespace_is_not_a_limitation(self, allocator, blank):
        with pytest.raises(ScopeLimitationError):
            make_validation(allocator, scope_limitations=blank)

    def test_vv5_passes_when_stated(self, allocator):
        assert not vv5_scope_limitations_present(ctx(make_validation(allocator))).failed

    def test_vv5_detects_a_stripped_scope(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v, "scope_limitations", "  ")
        result = vv5_scope_limitations_present(ctx(v))
        assert result.failed
        assert "whole-object assurance" in result.detail

    def test_store_rejects_a_missing_scope(self, store, allocator, solution):
        v = make_validation(
            allocator, solution.object_id,
            upstream_ceiling=solution.attributes.confidence.effective_confidence,
        )
        object.__setattr__(v, "scope_limitations", "")
        with pytest.raises(WriteRejectedError) as exc:
            store.write_validation(v)
        assert "V-V5" in exc.value.failure.rule_ids


# ===========================================================================
# V-V2 / V-V6  method recording  [M-32 blocking]
# ===========================================================================

class TestMethodRecording:
    def test_method_required(self, allocator):
        with pytest.raises(MethodError) as exc:
            make_validation(allocator, validation_method="")
        assert "M-32" in str(exc.value)

    def test_method_detail_required(self, allocator):
        with pytest.raises(MethodError):
            make_validation(allocator, method_detail="   ")

    def test_vv2_passes_and_records_the_blocking_marker(self, allocator):
        result = vv2_method_recorded(ctx(make_validation(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "M-32 open, blocking" in result.detail

    def test_no_method_vocabulary_is_invented(self, allocator):
        """M-32 must stay open: any method string is accepted."""
        for method in ("analytical", "experimental", "market-based", "banana"):
            v = make_validation(allocator, validation_method=method)
            assert not vv2_method_recorded(ctx(v)).failed

    def test_vv2_detects_a_stripped_method(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v, "validation_method", "")
        result = vv2_method_recorded(ctx(v))
        assert result.failed
        assert "Principle 3" in result.detail

    def test_vv6_rejects_detail_that_restates_the_method(self, allocator):
        """Method opacity in its most detectable form."""
        v = make_validation(
            allocator,
            validation_method="analytical review",
            method_detail="Analytical Review",
        )
        result = vv6_method_detail_repeatable(ctx(v))
        assert result.failed
        assert "adds nothing" in result.detail

    def test_vv6_passes_with_substantive_detail(self, allocator):
        result = vv6_method_detail_repeatable(ctx(make_validation(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "M-32 open" in result.detail

    def test_vv6_detects_an_emptied_detail(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v, "method_detail", "")
        result = vv6_method_detail_repeatable(ctx(v))
        assert result.failed
        assert "unrepeatable" in result.detail

    def test_store_rejects_opaque_method_detail(self, store, allocator, solution):
        with pytest.raises(WriteRejectedError) as exc:
            write_validation_from(
                store, allocator, solution,
                validation_method="a method", method_detail="a method",
            )
        assert "V-V6" in exc.value.failure.rule_ids


# ===========================================================================
# V-V3 / V-V4  result and interpretation
# ===========================================================================

class TestResultAndInterpretation:
    def test_four_defined_results(self):
        assert {r.value for r in ValidationResult} == {
            "SUPPORTED", "NOT_SUPPORTED", "INCONCLUSIVE", "PARTIALLY_SUPPORTED"
        }

    def test_result_must_be_from_the_set(self, allocator):
        with pytest.raises(ResultError) as exc:
            make_validation(allocator, result="MOSTLY_FINE")
        assert "must be one of" in str(exc.value)
        assert "V-V3" in str(exc.value)

    @pytest.mark.parametrize("result", list(ValidationResult))
    def test_every_defined_result_accepted(self, allocator, result):
        assert make_validation(allocator, result=result).result is result

    def test_result_detail_required(self, allocator):
        with pytest.raises(ValidationError):
            make_validation(allocator, result_detail="  ")

    def test_vv3_detects_a_smuggled_result(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v, "result", "INVENTED")
        result = vv3_result_in_defined_set(ctx(v))
        assert result.failed
        assert "outside the defined set" in result.detail

    def test_vv3_detects_a_stripped_detail(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v, "result_detail", "")
        result = vv3_result_in_defined_set(ctx(v))
        assert result.failed
        assert "separable from what it is taken to mean" in result.detail

    def test_interpretation_required(self, allocator):
        with pytest.raises(InterpretationError) as exc:
            make_validation(allocator, result_interpretation="")
        assert "including for negative results" in str(exc.value)

    def test_vv4_reports_negativity_explicitly(self, allocator):
        result = vv4_interpretation_present(
            ctx(make_validation(allocator, result=ValidationResult.NOT_SUPPORTED))
        )
        assert result.outcome is RuleOutcome.PASS
        assert "durable knowledge" in result.detail

    def test_vv4_passes_for_a_supported_result(self, allocator):
        result = vv4_interpretation_present(
            ctx(make_validation(allocator, result=ValidationResult.SUPPORTED))
        )
        assert result.outcome is RuleOutcome.PASS

    def test_vv4_detects_a_stripped_interpretation(self, allocator):
        v = make_validation(allocator)
        object.__setattr__(v, "result_interpretation", "  ")
        result = vv4_interpretation_present(ctx(v))
        assert result.failed
        assert "states nothing about the claim" in result.detail


# ===========================================================================
# Rule-set hygiene
# ===========================================================================

class TestRuleSetHygiene:
    def test_six_rules_registered(self, store):
        assert {f"V-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)
        assert len(VALIDATION_RULES) == 6

    def test_rule_ids_in_order(self):
        assert [r.rule_id for r in VALIDATION_RULES] == [
            f"V-V{i}" for i in range(1, 7)
        ]

    def test_v_v_prefix_distinct_from_universal_v(self, store):
        """V1..V12 are universal; V-V1..V-V6 are Validation-specific."""
        ids = set(store.acceptance.rule_ids)
        assert {f"V{i}" for i in range(1, 13)} <= ids
        assert {f"V-V{i}" for i in range(1, 7)} <= ids
        assert not {f"V{i}" for i in range(1, 13)} & {
            f"V-V{i}" for i in range(1, 7)
        }

    @pytest.mark.parametrize("rule", VALIDATION_RULES)
    def test_every_rule_skips_non_validations(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert rule(AcceptanceContext(attributes=attributes)).outcome is RuleOutcome.SKIP

    @pytest.mark.parametrize("rule", VALIDATION_RULES)
    def test_every_rule_skips_without_payload(self, allocator, rule):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.VALIDATION,
            (("obj-so-1", ObjectType.SOLUTION),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = rule(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP
        assert "no Validation payload" in result.detail

    def test_earlier_stages_unaffected(self, store, allocator):
        stored = write_solutions(store, allocator, 1)[0]
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# Type, authority, attributes
# ===========================================================================

class TestTypeAndAuthority:
    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.SOLUTION,
            (("obj-op-1", ObjectType.OPPORTUNITY),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ValidationError):
            make_validation(allocator, "obj-op-1", attributes=attributes)

    def test_only_validation_engine_may_create(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.VALIDATION,
            (("obj-so-1", ObjectType.SOLUTION),),
            engine=Engine.SOLUTION_INTELLIGENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ValidationError) as exc:
            make_validation(allocator, attributes=attributes)
        assert "V7" in str(exc.value)

    def test_validated_at_must_be_a_datetime(self, allocator):
        with pytest.raises(ValidationError):
            make_validation(allocator, validated_at="2026-05-02")

    def test_optional_attributes_default_absent(self, allocator):
        v = make_validation(allocator)
        assert v.experiment_ref is None
        assert v.confidence_impact is None
        assert v.contradicting_evidence == ()
        assert v.follow_up_required is None
        assert v.correction_rationale is None

    def test_experiment_ref_optional_due_to_c05(self, allocator):
        """C-05 unresolved; the field is carried, never required."""
        v = make_validation(allocator, experiment_ref="EXP-0001")
        assert v.experiment_ref == "EXP-0001"
        assert make_validation(allocator).experiment_ref is None

    def test_optional_attributes_carried(self, allocator):
        v = make_validation(
            allocator,
            confidence_impact="narrows claimed value at high volume",
            contradicting_evidence=("obj-ev-9",),
            follow_up_required="test A2 next",
        )
        assert v.contradicting_evidence == ("obj-ev-9",)

    def test_identity_delegated(self, allocator):
        v = make_validation(allocator)
        assert v.object_id == v.attributes.object_id
        assert v.lineage_id == v.attributes.lineage_id
        assert v.status is v.attributes.status
        assert v.tested_object_id == "obj-so-1"
        assert v.claim_id == "A1"

    def test_frozen(self, allocator):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            make_validation(allocator).result_detail = "x"


# ===========================================================================
# V-I1..V-I4  integrity
# ===========================================================================

class TestValidationIntegrity:
    def test_clean_store_holds(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        assert store.validations.integrity().verify() == ()

    def test_vi2_detects_a_modified_tested_object(self, store, allocator, solution):
        """A test that changes what it tests is an edit, not a test."""
        from oip.contract import Confidence

        write_validation_from(store, allocator, solution)
        object.__setattr__(
            store._objects[solution.object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        violations = store.validations.integrity().verify()
        assert any(v.constraint_id == "V-I2" for v in violations)
        assert "never modifies what it tests" in "".join(
            v.detail for v in violations
        )

    def test_vi2_detects_a_vanished_target(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        del store._objects[solution.object_id]
        assert any(
            v.constraint_id == "V-I2" and "no longer retrievable" in v.detail
            for v in store.validations.integrity().verify()
        )

    def test_vi2_reports_once_per_target(self, store, allocator, solution):
        """Three tests of one Solution must not triple-report."""
        from oip.contract import Confidence

        for claim in ("A1", "A2", "A3"):
            write_validation_from(store, allocator, solution, claim_id=claim)
        object.__setattr__(
            store._objects[solution.object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        violations = [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I2"
        ]
        assert len(violations) == 1

    def test_vi2_untouched_target_holds(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        write_validation_from(store, allocator, solution, claim_id="A2")
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I2"
        ]

    def test_vi3_detects_reaching_beyond_the_tested_object(
        self, store, allocator, solution
    ):
        """A Validation that reaches further is proposing, not testing."""
        stored = write_validation_from(store, allocator, solution)
        from oip.contract import LineageRef

        object.__setattr__(
            store._objects[stored.object_id].attributes, "derives_from",
            stored.attributes.derives_from
            + (LineageRef("obj-so-other", ObjectType.SOLUTION),),
        )
        violations = store.validations.integrity().verify()
        assert any(v.constraint_id == "V-I3" for v in violations)
        assert "proposing, not testing" in "".join(v.detail for v in violations)

    def test_vi3_clean_when_scoped_to_its_target(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I3"
        ]

    def test_vi3_detects_an_addresses_assertion(self, store, allocator, solution):
        """Proposing forfeits the independence that makes the test impartial."""
        from datetime import datetime, timezone
        from oip.relationships import Relationship

        stored = write_validation_from(store, allocator, solution)
        # A Validation may not ADDRESS anything; assert the edge directly.
        store.graph._out[RelationshipType.ADDRESSES][stored.object_id].add(
            solution.object_id
        )
        violations = store.validations.integrity().verify()
        assert any(
            v.constraint_id == "V-I3" and "forfeits the independence" in v.detail
            for v in violations
        )

    def test_vi4_detects_a_reinterpreted_result(self, store, allocator, solution):
        """Corrections are new versions with rationale, not edits."""
        stored = write_validation_from(store, allocator, solution)
        payload = store.get_validation(stored.object_id)
        object.__setattr__(payload, "result", ValidationResult.SUPPORTED)
        violations = store.validations.integrity().verify()
        assert any(v.constraint_id == "V-I4" for v in violations)
        assert "not edits" in "".join(v.detail for v in violations)

    def test_vi4_detects_a_rewritten_interpretation(
        self, store, allocator, solution
    ):
        stored = write_validation_from(store, allocator, solution)
        payload = store.get_validation(stored.object_id)
        object.__setattr__(
            payload, "result_interpretation", "Actually it went fine."
        )
        assert any(
            v.constraint_id == "V-I4"
            for v in store.validations.integrity().verify()
        )

    def test_vi4_unaltered_result_holds(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I4"
        ]

    def test_correction_requires_a_rationale_at_construction(
        self, store, allocator, solution
    ):
        first = write_validation_from(store, allocator, solution)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "recording error")
        successor = allocator.succeed(first.attributes.identity)
        with pytest.raises(ValidationError) as exc:
            make_validation(
                allocator, solution.object_id, identity=successor,
                upstream_ceiling=solution.attributes.confidence.effective_confidence,
            )
        assert "correction_rationale" in str(exc.value)

    def test_correction_with_rationale_accepted(self, store, allocator, solution):
        first = write_validation_from(store, allocator, solution)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "recording error")
        successor = allocator.succeed(first.attributes.identity)
        second = write_validation_from(
            store, allocator, solution,
            identity=successor, predecessor_id=first.object_id,
            correction_rationale="Transcription error in result_detail.",
        )
        assert second.attributes.version == 2
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I4"
        ]

    def test_retest_is_a_new_object_not_a_version(self, store, allocator, solution):
        """A concluded test is a historical fact; both results survive."""
        first = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        second = write_validation_from(
            store, allocator, solution, result=ValidationResult.SUPPORTED
        )
        assert first.lineage_id != second.lineage_id
        assert first.attributes.version == second.attributes.version == 1
        assert len(store.validations.for_claim(solution.object_id, "A1")) == 2

    def test_recorded_result_count(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        assert store.validations.integrity().recorded_result_count == 1

    def test_unregistered_validations_skipped(self, store, allocator):
        from tests.conftest import write_chain

        write_chain(store, allocator)
        assert store.validations.integrity().verify() == ()

    def test_verifier_constructible_standalone(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        verifier = ValidationIntegrity(
            validation_of=store.validations.get, store=store
        )
        assert verifier.verify() == ()


# ===========================================================================
# Conflicting results  [CONTRADICTS]
# ===========================================================================

class TestConflictingResults:
    def test_disagreeing_tests_are_surfaced(self, store, allocator, solution):
        """Two tests disagreeing is information, not a problem to resolve."""
        write_validation_from(
            store, allocator, solution, result=ValidationResult.SUPPORTED
        )
        write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        conflicts = store.validations.conflicts_for(solution.object_id, "A1")
        assert len(conflicts) == 1

    def test_agreeing_tests_are_not_conflicts(self, store, allocator, solution):
        for _ in range(2):
            write_validation_from(
                store, allocator, solution, result=ValidationResult.SUPPORTED
            )
        assert store.validations.conflicts_for(solution.object_id, "A1") == ()

    def test_no_winner_is_selected(self, store, allocator, solution):
        """Both retained; the registry offers no resolution. [T07.3.6]"""
        write_validation_from(
            store, allocator, solution, result=ValidationResult.SUPPORTED
        )
        write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        assert len(store.validations.for_claim(solution.object_id, "A1")) == 2
        assert all(
            store.get(v.object_id).status is ObjectStatus.ACTIVE
            for v in store.validations.for_claim(solution.object_id, "A1")
        )

    def test_different_claims_are_not_conflicts(self, store, allocator, solution):
        write_validation_from(
            store, allocator, solution, claim_id="A1",
            result=ValidationResult.SUPPORTED,
        )
        write_validation_from(
            store, allocator, solution, claim_id="A2",
            result=ValidationResult.NOT_SUPPORTED,
        )
        assert store.validations.conflicts_for(solution.object_id, "A1") == ()

    def test_disagreement_predicate(self, allocator):
        a = make_validation(allocator, result=ValidationResult.SUPPORTED)
        b = make_validation(allocator, result=ValidationResult.NOT_SUPPORTED)
        c = make_validation(
            allocator, claim_id="A2", result=ValidationResult.NOT_SUPPORTED
        )
        assert a.disagrees_with(b)
        assert not a.disagrees_with(c)
        assert a.tests_same_claim_as(b)

    def test_contradicts_is_legal_between_validations(self):
        from oip.relationships import is_legal

        assert is_legal(
            RelationshipType.CONTRADICTS, ObjectType.VALIDATION, ObjectType.VALIDATION
        )


# ===========================================================================
# Store integration
# ===========================================================================

class TestStoreIntegration:
    def test_payload_retrievable(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        assert store.get_validation(stored.object_id) is not None

    def test_unknown_payload_is_none(self, store):
        assert store.get_validation("obj-absent") is None

    def test_registry_counts_and_memoises(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        assert len(store.validations) == 1
        assert store.validations is store.validations

    def test_active_validations(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        assert len(store.validations.active_validations()) == 1
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.validations.active_validations() == ()

    def test_rejected_write_leaves_no_payload(self, store, allocator, solution):
        before = len(store.validations)
        with pytest.raises(WriteRejectedError):
            write_validation_from(store, allocator, solution, claim_id="A99")
        assert len(store.validations) == before

    def test_rejected_write_records_a_failure(self, store, allocator, solution):
        with pytest.raises(WriteRejectedError):
            write_validation_from(store, allocator, solution, claim_id="A99")
        assert store.failure_records[-1].object_type is ObjectType.VALIDATION

    def test_claims_provider_only_knows_solutions(self, store, allocator, solution):
        """M-32 supplies no cross-type claim vocabulary."""
        assert store._claims_of_object(solution.object_id) == {"A1", "A2", "A3"}
        opportunity_id = store.objects_of_type(ObjectType.OPPORTUNITY)[0].object_id
        assert store._claims_of_object(opportunity_id) is None
        assert store._claims_of_object("obj-absent") is None

    def test_derivation_from_a_rejected_solution_refused(
        self, store, allocator, solution
    ):
        store.transition(solution.object_id, ObjectStatus.REJECTED, "infeasible")
        with pytest.raises(WriteRejectedError) as exc:
            write_validation_from(store, allocator, solution)
        assert "I8" in exc.value.failure.rule_ids


# ===========================================================================
# Lineage, graph, cascade, confidence
# ===========================================================================

class TestPipelineIntegration:
    def test_reaches_evidence_at_depth_six(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.depth_to_evidence(stored.object_id) == 6

    def test_evidence_set_spans_the_chain(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        assert len(store.graph.evidence_set(stored.object_id)) == 4

    def test_lineage_edges_indexed(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        assert store.graph.parents(
            stored.object_id, RelationshipType.DERIVES_FROM
        ) == frozenset({solution.object_id})

    def test_graph_rebuildable(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        store.rebuild_graph()
        assert store.graph_diverges() == ()
        assert store.graph.reaches_evidence(stored.object_id)

    def test_confidence_bounded_by_solution(self, store, allocator, solution):
        stored = write_validation_from(store, allocator, solution)
        ceiling = solution.attributes.confidence.effective_confidence
        assert stored.attributes.confidence.effective_confidence <= ceiling

    def test_confidence_inflation_rejected(self, store, allocator, solution):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_validation(
                make_validation(
                    allocator, solution.object_id, support=0.99, assertion=0.99
                )
            )
        assert "V5" in exc.value.failure.rule_ids

    def test_retracting_evidence_invalidates_the_validation(
        self, store, allocator, solution
    ):
        stored = write_validation_from(store, allocator, solution)
        cascade = CascadeInvalidation(store=store)
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_invalidating_the_solution_invalidates_the_validation(
        self, store, allocator, solution
    ):
        """IOM: ACTIVE -> INVALIDATED when the tested object is invalidated."""
        stored = write_validation_from(store, allocator, solution)
        store.transition(
            solution.object_id, ObjectStatus.INVALIDATED, "opportunity withdrawn"
        )
        CascadeInvalidation(store=store).cascade(
            solution.object_id, ObjectStatus.INVALIDATED, "opportunity withdrawn"
        )
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_universal_integrity_holds(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)
        assert store.verify_integrity().holds

    def test_all_seven_type_verifiers_hold(self, store, allocator, solution):
        """Backward compatibility across every realised type."""
        write_validation_from(store, allocator, solution)
        assert store.evidence.integrity().verify() == ()
        assert store.facts.integrity().verify() == ()
        assert store.problems.integrity().verify() == ()
        assert store.patterns.integrity().verify() == ()
        assert store.opportunities.integrity().verify() == ()
        assert store.solutions.integrity().verify() == ()
        assert store.validations.integrity().verify() == ()

    def test_evidence_may_never_derive_from_a_validation(
        self, store, allocator, solution
    ):
        """AD-05 holds at the Validation stage too."""
        from oip.evidence import Evidence, EvidenceContent, ExternalOriginError
        from tests.test_evidence import provenance

        stored = write_validation_from(store, allocator, solution)
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            ((stored.object_id, ObjectType.VALIDATION),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes, provenance=provenance(),
                content=EvidenceContent.full("text"),
            )

    def test_validation_does_not_gate(self, store, allocator, solution):
        """M-31: a failed assumption does not reject the Solution."""
        write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        assert store.get(solution.object_id).status is ObjectStatus.ACTIVE
        assert not hasattr(store.validations, "gate")


# ===========================================================================
# Concurrency  [N-11, I5]
# ===========================================================================

class TestConcurrency:
    def test_concurrent_validations_serialised(self, store, allocator):
        """Independent tests of one Solution run concurrently by design."""
        solution = write_solutions(
            store, allocator, 1,
            assumptions=tuple(assumption(f"A{i}") for i in range(8)),
        )[0]
        ceiling = solution.attributes.confidence.effective_confidence
        written: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(8)

        def writer(index: int) -> None:
            v = make_validation(
                allocator, solution.object_id,
                claim_id=f"A{index}", upstream_ceiling=ceiling,
            )
            barrier.wait()
            try:
                written.append(store.write_validation(v).object_id)
            except Exception as exc:  # pragma: no cover - diagnostic
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(set(written)) == 8
        assert store.verify_integrity().holds
        assert store.validations.integrity().verify() == ()

    def test_only_one_successor_wins_a_correction_race(
        self, store, allocator, solution
    ):
        from oip.identity import BranchingError

        first = write_validation_from(store, allocator, solution)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "recording error")

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
                write_validation_from(
                    store, allocator, solution,
                    identity=identity, predecessor_id=first.object_id,
                    correction_rationale="corrected transcription",
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
# Adversarial
# ===========================================================================

class TestAdversarial:
    def test_suppression_by_rejection_is_closed_at_every_route(
        self, store, allocator, solution
    ):
        """Construction, write, and post-hoc transition all covered."""
        with pytest.raises(NegativeResultSuppressionError):
            make_validation(
                allocator, result=ValidationResult.NOT_SUPPORTED,
                status=ObjectStatus.REJECTED, status_reason="unwelcome",
            )
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        assert store.get(stored.object_id).status is ObjectStatus.ACTIVE

    def test_partial_support_is_protected_like_a_negative(
        self, store, allocator, solution
    ):
        """Over-claiming is easiest where an unfavourable half is reported."""
        with pytest.raises(NegativeResultSuppressionError):
            make_validation(
                allocator, result=ValidationResult.PARTIALLY_SUPPORTED,
                status=ObjectStatus.REJECTED, status_reason="filed away",
            )

    def test_a_second_validation_cannot_launder_a_modified_target(
        self, store, allocator, solution
    ):
        """The V-I2 snapshot must not be reset by a later attach."""
        from oip.contract import Confidence

        write_validation_from(store, allocator, solution, claim_id="A1")
        object.__setattr__(
            store._objects[solution.object_id].attributes, "confidence",
            Confidence(evidential_support=0.1, assertion_confidence=0.1,
                       effective_confidence=0.1),
        )
        write_validation_from(store, allocator, solution, claim_id="A2")
        assert any(
            v.constraint_id == "V-I2"
            for v in store.validations.integrity().verify()
        )

    def test_payload_survives_the_store_round_trip(self, store, allocator, solution):
        stored = write_validation_from(
            store, allocator, solution,
            result=ValidationResult.NOT_SUPPORTED,
            experiment_ref="EXP-1",
            contradicting_evidence=("obj-ev-1",),
            follow_up_required="retest at volume",
        )
        payload = store.get_validation(stored.object_id)
        assert payload.result is ValidationResult.NOT_SUPPORTED
        assert payload.experiment_ref == "EXP-1"
        assert payload.contradicting_evidence == ("obj-ev-1",)
        assert payload.scope_limitations == SCOPE

    def test_result_fingerprint_is_stable(self, allocator):
        v = make_validation(allocator)
        assert v.result_fingerprint() == v.result_fingerprint()

    def test_fingerprint_changes_with_interpretation(self, allocator):
        a = make_validation(allocator)
        b = make_validation(allocator, result_interpretation="Something else.")
        assert a.result_fingerprint() != b.result_fingerprint()

    def test_graph_rebuild_does_not_disturb_integrity(
        self, store, allocator, solution
    ):
        write_validation_from(store, allocator, solution)
        store.rebuild_graph()
        assert store.validations.integrity().verify() == ()


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(result=st.sampled_from(list(ValidationResult)))
def test_protected_results_never_rejectable(result):
    """AC1 over every defined result."""
    allocator = IdentityAllocator()
    kwargs = dict(
        result=result, status=ObjectStatus.REJECTED, status_reason="filed"
    )
    if result in PROTECTED_RESULTS:
        with pytest.raises(NegativeResultSuppressionError):
            make_validation(allocator, **kwargs)
    else:
        assert make_validation(allocator, **kwargs).status is ObjectStatus.REJECTED


@settings(max_examples=200, deadline=None)
@given(claim_id=st.text(max_size=20))
def test_claim_id_always_required(claim_id):
    """AC2 over arbitrary claim identifiers."""
    if claim_id.strip():
        assert ClaimReference("obj-so-1", claim_id).claim_id == claim_id
    else:
        with pytest.raises(ClaimReferenceError):
            ClaimReference("obj-so-1", claim_id)


@settings(max_examples=200, deadline=None)
@given(scope=st.text(max_size=30))
def test_scope_limitations_always_required(scope):
    """AC3 over arbitrary scope text."""
    allocator = IdentityAllocator()
    if scope.strip():
        assert make_validation(allocator, scope_limitations=scope)
    else:
        with pytest.raises(ScopeLimitationError):
            make_validation(allocator, scope_limitations=scope)


@settings(max_examples=200, deadline=None)
@given(method=st.text(max_size=30))
def test_method_presence_required_but_value_unconstrained(method):
    """M-32: presence is enforceable, legitimacy is not."""
    allocator = IdentityAllocator()
    if method.strip():
        v = make_validation(allocator, validation_method=method)
        assert not vv2_method_recorded(ctx(v)).failed
    else:
        with pytest.raises(MethodError):
            make_validation(allocator, validation_method=method)


@settings(max_examples=200, deadline=None)
@given(
    left=st.sampled_from(list(ValidationResult)),
    right=st.sampled_from(list(ValidationResult)),
)
def test_disagreement_is_exactly_result_inequality(left, right):
    """Conflicts are surfaced, never resolved."""
    allocator = IdentityAllocator()
    a = make_validation(allocator, result=left)
    b = make_validation(allocator, result=right)
    assert a.disagrees_with(b) == (left is not right)


@settings(max_examples=150, deadline=None)
@given(interpretation=st.text(max_size=30))
def test_interpretation_always_required(interpretation):
    """V-V4 over arbitrary interpretation text."""
    allocator = IdentityAllocator()
    if interpretation.strip():
        v = make_validation(allocator, result_interpretation=interpretation)
        assert not vv4_interpretation_present(ctx(v)).failed
    else:
        with pytest.raises(InterpretationError):
            make_validation(allocator, result_interpretation=interpretation)


# ===========================================================================
# Regression: every suppression route  [V-I1]
# ===========================================================================

class TestSuppressionRoutesClosed:
    """Regression for a real defect found by adversarial probing.

    V-I1 originally covered REJECTED and ARCHIVED only. A negative finding
    could be buried by RETRACTING it while the claim it bears on stayed
    ACTIVE -- the exact suppression V-I1 exists to prevent. The IOM's
    Validation transition table does not offer RETRACTED at all: "withdrawn
    at source" describes Evidence whose basis the world revoked, not a
    concluded test, which is a historical fact.
    """

    @pytest.mark.parametrize(
        "status", [ObjectStatus.ARCHIVED, ObjectStatus.RETRACTED]
    )
    @pytest.mark.parametrize(
        "result",
        [ValidationResult.NOT_SUPPORTED, ValidationResult.PARTIALLY_SUPPORTED,
         ValidationResult.INCONCLUSIVE],
    )
    def test_retiring_a_protected_finding_is_suppression(
        self, store, allocator, solution, status, result
    ):
        stored = write_validation_from(
            store, allocator, solution, result=result
        )
        store.transition(stored.object_id, status, "withdrawn")
        assert store.get(solution.object_id).status is ObjectStatus.ACTIVE
        violations = store.validations.integrity().verify()
        assert any(
            v.constraint_id == "V-I1" and "the claim was not" in v.detail
            for v in violations
        ), f"{result.value} + {status.value} not caught"

    @pytest.mark.parametrize(
        "status", [ObjectStatus.ARCHIVED, ObjectStatus.RETRACTED]
    )
    def test_retiring_alongside_the_tested_object_is_legitimate(
        self, store, allocator, solution, status
    ):
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        store.transition(stored.object_id, status, "withdrawn")
        store.transition(solution.object_id, ObjectStatus.ARCHIVED, "retention")
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I1"
        ]

    def test_supersession_is_not_suppression(self, store, allocator, solution):
        """The sanctioned correction route under V-I4."""
        first = write_validation_from(
            store, allocator, solution, result=ValidationResult.NOT_SUPPORTED
        )
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "recording error")
        successor = allocator.succeed(first.attributes.identity)
        write_validation_from(
            store, allocator, solution,
            identity=successor, predecessor_id=first.object_id,
            result=ValidationResult.NOT_SUPPORTED,
            correction_rationale="corrected a transcription error",
        )
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I1"
        ]

    def test_a_favourable_finding_may_be_retired_freely(
        self, store, allocator, solution
    ):
        """Only unfavourable and inconclusive findings need protection."""
        stored = write_validation_from(
            store, allocator, solution, result=ValidationResult.SUPPORTED
        )
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I1"
        ]


# ===========================================================================
# Residual surface
# ===========================================================================

class TestResidualSurface:
    def test_verifier_skips_an_unstored_validation(self, store, allocator, solution):
        """A payload without a stored object yields no verdict. [N-6]"""
        stored = write_validation_from(store, allocator, solution)
        del store._objects[stored.object_id]
        assert store.validations.integrity().verify() == ()

    def test_vi3_skips_when_unindexed(self, store, allocator, solution):
        """No graph entry, no ADDRESSES verdict."""
        write_validation_from(store, allocator, solution)
        store.graph = store.graph.__class__()
        assert not [
            v for v in store.validations.integrity().verify()
            if v.constraint_id == "V-I3"
        ]

    def test_vi3_skips_without_a_graph(self, store, allocator, solution):
        write_validation_from(store, allocator, solution)

        class GraphlessStore:
            graph = None

            def objects_of_type(self, t):
                return ()

            def find(self, oid):
                return None

        verifier = ValidationIntegrity(
            validation_of=store.validations.get, store=GraphlessStore()
        )
        assert verifier.verify() == ()

    def test_vi4_detects_a_version_without_rationale(
        self, store, allocator, solution
    ):
        """The chain check, distinct from the construction guard."""
        first = write_validation_from(store, allocator, solution)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "recording error")
        successor = allocator.succeed(first.attributes.identity)
        second = write_validation_from(
            store, allocator, solution,
            identity=successor, predecessor_id=first.object_id,
            correction_rationale="corrected transcription",
        )
        payload = store.get_validation(second.object_id)
        object.__setattr__(payload, "correction_rationale", "  ")
        violations = store.validations.integrity().verify()
        assert any(
            v.constraint_id == "V-I4" and "versions are corrections only" in v.detail
            for v in violations
        )

    def test_recording_skips_an_unresolvable_target(self, store, allocator):
        verifier = store.validations.integrity()
        verifier.record(make_validation(allocator))
        assert verifier.recorded_result_count == 1

    def test_claim_reference_renders_readably(self):
        assert "A1" in str(claim_ref("obj-so-1", "A1"))
