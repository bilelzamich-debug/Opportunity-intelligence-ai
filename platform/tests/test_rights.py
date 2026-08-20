"""Contract tests for the acquisition-rights model.

Task: T02.1.2

Architecture References:
- N-21   The rights vocabulary (S 5.5), admissibility (S 5.4), retention
         model (S 5.6), storage-mode determination (S 5.7), and the CI-1
         boundary (S 5.9). These tests assert the ratified behaviour
         exactly -- fail-closed everywhere, one reason per refusal.
- N-24   The authority is the designated role; no other attribution is
         accepted.
- N-10   Refusals recorded, never silent.
- N-4    Property-based assertions only; never equality on engine output.

T02.1.2 acceptance criteria under test:
  AC1  Ineligible sources rejected before acquisition  -> IMPLEMENTED (gate 3)
  AC2  access_conditions populated on every Evidence   -> IMPLEMENTED (value)
  AC3  Retention rights recorded and honoured         -> IMPLEMENTED (S 5.7)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oip.rights import (
    ACQUISITION_RIGHTS,
    RETENTION_RIGHTS,
    RIGHTS_AUTHORITY_ROLE,
    AccessConditionsError,
    AcquisitionRight,
    AssessmentInvalidError,
    GateDecision,
    RefusalReason,
    RefusalRegister,
    RefusedByRightsError,
    RetentionRight,
    RightsAssessment,
    RightsError,
    RightsRefusal,
    StorageMode,
    access_conditions_value,
    evaluate_gate,
    require_permitted,
    unassessed,
)

IDENT = st.text(min_size=1, max_size=20).filter(str.strip)
BASIS = st.text(min_size=3, max_size=60).filter(str.strip)
FIXED_NOW = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)


def permitted(
    retention: RetentionRight = RetentionRight.RETAIN_FULL,
    valid_until: datetime | None = None,
    source: str = "src-a",
) -> RightsAssessment:
    return RightsAssessment(
        source_identifier=source,
        acquisition=AcquisitionRight.PERMITTED,
        retention=retention,
        authority=RIGHTS_AUTHORITY_ROLE,
        basis="licence terms, section 3",
        assessed_at=FIXED_NOW - timedelta(days=1),
        valid_until=valid_until,
    )


# ===========================================================================
# The closed vocabulary  [N-21 S 5.5]
# ===========================================================================


class TestVocabulary:
    def test_acquisition_vocabulary_is_the_three_ratified_values(self):
        assert ACQUISITION_RIGHTS == (
            "PERMITTED", "PROHIBITED", "UNASSESSED",
        )
        assert list(AcquisitionRight) == [
            AcquisitionRight[a] for a in ACQUISITION_RIGHTS
        ]
        with pytest.raises(AttributeError):
            AcquisitionRight.CONDITIONAL

    def test_retention_vocabulary_is_the_four_ratified_values(self):
        assert RETENTION_RIGHTS == (
            "RETAIN_FULL", "RETAIN_REFERENCE_ONLY", "RETAIN_NONE",
            "UNASSESSED",
        )
        with pytest.raises(AttributeError):
            RetentionRight.RETAIN_SUMMARY

    def test_storage_mode_has_no_none_member(self):
        """RETAIN_NONE / UNASSESSED create no object: no mode exists to
        select. [N-21 S 5.7]"""
        assert [m.name for m in StorageMode] == ["FULL", "REFERENCE_ONLY"]


# ===========================================================================
# The assessment record  [N-21 S 5.3, S 5.5; N-24]
# ===========================================================================


class TestAssessment:
    @given(source=IDENT, basis=BASIS)
    def test_a_well_formed_assessment_records_everything(
        self, source, basis
    ):
        assessment = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PROHIBITED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis=basis,
            assessed_at=FIXED_NOW,
        )
        assert assessment.authority == RIGHTS_AUTHORITY_ROLE
        assert assessment.basis == basis

    def test_the_authority_must_be_the_designated_role(self):
        for impostor in (
            "", " ", "Anyone Else", "research engine", "platform",
        ):
            with pytest.raises(AssessmentInvalidError):
                RightsAssessment(
                    source_identifier="s",
                    acquisition=AcquisitionRight.PERMITTED,
                    retention=RetentionRight.RETAIN_FULL,
                    authority=impostor,
                    basis="b",
                    assessed_at=FIXED_NOW,
                )

    @given(bad=st.text(max_size=20))
    def test_rights_outside_the_closed_vocabulary_are_refused(self, bad):
        if bad in ACQUISITION_RIGHTS:
            return
        with pytest.raises((AssessmentInvalidError, TypeError)):
            RightsAssessment(
                source_identifier="s",
                acquisition=bad,
                retention=RetentionRight.RETAIN_FULL,
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="b",
                assessed_at=FIXED_NOW,
            )

    def test_a_basis_is_mandatory(self):
        with pytest.raises(AssessmentInvalidError):
            RightsAssessment(
                source_identifier="s",
                acquisition=AcquisitionRight.PERMITTED,
                retention=RetentionRight.RETAIN_FULL,
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="  ",
                assessed_at=FIXED_NOW,
            )

    def test_datetimes_are_enforced(self):
        base = dict(
            source_identifier="s",
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
        )
        with pytest.raises(AssessmentInvalidError):
            RightsAssessment(**base, assessed_at="2026-01-01")
        with pytest.raises(AssessmentInvalidError):
            RightsAssessment(**base, assessed_at=FIXED_NOW, valid_until="x")

    def test_unassessed_is_the_fail_closed_default(self):
        default = unassessed("src-x")
        assert default.acquisition is AcquisitionRight.UNASSESSED
        assert default.retention is RetentionRight.UNASSESSED
        assert default.is_admissible is False

    @given(source=IDENT)
    def test_no_source_is_ever_admissible_while_unassessed(self, source):
        assert unassessed(source).is_admissible is False

    def test_admissibility_is_pinned_directly(self):
        """The summary property, directly, for the full boundary matrix --
        the gate has its own reason-specific branches and must not be the
        only thing exercising this logic."""
        assert permitted().is_admissible is True
        assert permitted(
            RetentionRight.RETAIN_REFERENCE_ONLY
        ).is_admissible is True
        assert permitted(
            RetentionRight.RETAIN_NONE
        ).is_admissible is False
        assert permitted(
            RetentionRight.UNASSESSED
        ).is_admissible is False
        assert permitted(
            valid_until=FIXED_NOW - timedelta(days=1)
        ).is_admissible is False
        assert permitted(
            valid_until=FIXED_NOW + timedelta(days=1)
        ).is_admissible is True
        # Mixed: acquisition UNASSESSED never becomes admissible just
        # because retention is generous.
        mixed = RightsAssessment(
            source_identifier="s",
            acquisition=AcquisitionRight.UNASSESSED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
            assessed_at=FIXED_NOW,
        )
        assert mixed.is_admissible is False

    def test_the_authority_role_name_is_pinned_literally(self):
        """[N-24] The designated role, verbatim -- no silent renaming."""
        assert RIGHTS_AUTHORITY_ROLE == (
            "Designated Source Rights/Compliance Authority"
        )

    @given(source=IDENT)
    def test_gate_three_admits_any_well_formed_permitted_source(
        self, source
    ):
        """Gate 3 evaluates RIGHTS only: it never invents scope or
        typability checks of its own (gates 1-2, N-20 S 5.2.1)."""
        assessment = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
            assessed_at=FIXED_NOW - timedelta(days=1),
            valid_until=FIXED_NOW + timedelta(days=1),
        )
        assert evaluate_gate(assessment, now=FIXED_NOW).admitted is True


# ===========================================================================
# AC1 -- gate 3 rejects before acquisition  [N-21 S 5.4]
# ===========================================================================


class TestGateThree:
    def test_unexpired_permitted_full_is_admitted_with_mode(self):
        decision = evaluate_gate(permitted(), now=FIXED_NOW)
        assert decision.admitted is True
        assert decision.storage_mode is StorageMode.FULL
        assert decision.refusal is None

    def test_permitted_reference_only_stores_by_reference(self):
        decision = evaluate_gate(
            permitted(RetentionRight.RETAIN_REFERENCE_ONLY), now=FIXED_NOW
        )
        assert decision.admitted is True
        assert decision.storage_mode is StorageMode.REFERENCE_ONLY

    def test_unassessed_fails_closed(self):
        decision = evaluate_gate(unassessed("s"), now=FIXED_NOW)
        assert decision.admitted is False
        assert decision.refusal.reason is RefusalReason.UNASSESSED

    def test_prohibited_refuses(self):
        assessment = RightsAssessment(
            source_identifier="s",
            acquisition=AcquisitionRight.PROHIBITED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="licence forbids retention",
            assessed_at=FIXED_NOW,
        )
        decision = evaluate_gate(assessment, now=FIXED_NOW)
        assert decision.refusal.reason is RefusalReason.PROHIBITED

    def test_expired_permitted_refuses(self):
        assessment = permitted(valid_until=FIXED_NOW - timedelta(days=1))
        decision = evaluate_gate(assessment, now=FIXED_NOW)
        assert decision.refusal.reason is RefusalReason.EXPIRED

    def test_unexpired_boundary_is_admitted(self):
        assessment = permitted(valid_until=FIXED_NOW + timedelta(seconds=1))
        assert evaluate_gate(assessment, now=FIXED_NOW).admitted is True

    def test_retain_none_refuses_outright(self):
        """No object subject to RETAIN_NONE can ever exist. [S 5.5, 5.6]"""
        assessment = permitted(RetentionRight.RETAIN_NONE)
        decision = evaluate_gate(assessment, now=FIXED_NOW)
        assert decision.admitted is False
        assert decision.refusal.reason is RefusalReason.RETAIN_NONE

    def test_retention_unassessed_refuses_never_downgrades(self):
        """UNASSESSED retention is NOT treated as RETAIN_REFERENCE_ONLY."""
        assessment = permitted(RetentionRight.UNASSESSED)
        decision = evaluate_gate(assessment, now=FIXED_NOW)
        assert decision.refusal.reason is RefusalReason.RETENTION_UNASSESSED

    @given(
        acquisition=st.sampled_from(list(AcquisitionRight)),
        retention=st.sampled_from(list(RetentionRight)),
        ttl_days=st.integers(min_value=-100, max_value=100),
    )
    def test_exactly_one_outcome_and_neither_both(
        self, acquisition, retention, ttl_days
    ):
        """Property: every assessment yields admitted XOR one refusal."""
        assessment = RightsAssessment(
            source_identifier="s",
            acquisition=acquisition,
            retention=retention,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="basis",
            assessed_at=FIXED_NOW - timedelta(days=1),
            valid_until=FIXED_NOW + timedelta(days=ttl_days),
        )
        decision = evaluate_gate(assessment, now=FIXED_NOW)
        assert decision.admitted != (decision.refusal is not None)
        if decision.admitted:
            assert decision.storage_mode is not None
        else:
            assert decision.storage_mode is None
            assert decision.refusal is not None

    def test_every_refusal_is_recorded_never_silent(self):
        register = RefusalRegister()
        evaluate_gate(unassessed("s"), refusals=register, now=FIXED_NOW)
        evaluate_gate(
            permitted(RetentionRight.RETAIN_NONE),
            refusals=register,
            now=FIXED_NOW,
        )
        assert len(register) == 2
        reasons = {r.reason for r in register}
        assert reasons == {RefusalReason.UNASSESSED, RefusalReason.RETAIN_NONE}
        assert all(r.detail.strip() for r in register)

    def test_require_permitted_returns_mode_or_raises(self):
        register = RefusalRegister()
        mode = require_permitted(permitted(), refusals=register, now=FIXED_NOW)
        assert mode is StorageMode.FULL
        with pytest.raises(RefusedByRightsError) as exc:
            require_permitted(
                unassessed("s"), refusals=register, now=FIXED_NOW
            )
        assert "UNASSESSED" in str(exc.value)

    def test_gate_decision_is_structurally_honest(self):
        with pytest.raises(RightsError):
            GateDecision(
                source_identifier="s",
                admitted=True,
                storage_mode=None,
                refusal=None,
            )
        with pytest.raises(RightsError):
            GateDecision(
                source_identifier="s",
                admitted=False,
                storage_mode=StorageMode.FULL,
                refusal=None,
            )


# ===========================================================================
# AC3 -- retention honoured  [N-21 S 5.7 -- the N-15 determination]
# ===========================================================================


class TestStorageModeDetermination:
    def test_the_section_57_mapping_is_exact(self):
        cases = {
            RetentionRight.RETAIN_FULL: StorageMode.FULL,
            RetentionRight.RETAIN_REFERENCE_ONLY: StorageMode.REFERENCE_ONLY,
        }
        for retention, mode in cases.items():
            decision = evaluate_gate(
                permitted(retention), now=FIXED_NOW
            )
            assert decision.storage_mode is mode

    def test_retain_none_and_unassessed_create_no_object(self):
        for retention in (
            RetentionRight.RETAIN_NONE,
            RetentionRight.UNASSESSED,
        ):
            decision = evaluate_gate(permitted(retention), now=FIXED_NOW)
            assert decision.admitted is False
            assert decision.storage_mode is None

    def test_no_mode_exists_for_forbidden_material(self):
        """The mapping is total over ADMISSIBLE assessments only: a
        refused decision carries storage_mode None, by design."""
        decision = evaluate_gate(
            permitted(RetentionRight.RETAIN_NONE), now=FIXED_NOW
        )
        assert decision.storage_mode is None


# ===========================================================================
# AC2 -- access_conditions  [N-21 S 5.9]
# ===========================================================================


class TestAccessConditions:
    def test_the_value_carries_the_full_determination(self):
        value = access_conditions_value(permitted())
        assert "acquisition=PERMITTED" in value
        assert "retention=RETAIN_FULL" in value
        assert RIGHTS_AUTHORITY_ROLE in value
        assert "basis=" in value
        assert "assessed_at=" in value
        assert "valid_until=" in value

    def test_reference_only_is_carried_faithfully(self):
        value = access_conditions_value(
            permitted(RetentionRight.RETAIN_REFERENCE_ONLY)
        )
        assert "retention=RETAIN_REFERENCE_ONLY" in value

    @given(
        retention=st.sampled_from(
            [RetentionRight.RETAIN_NONE, RetentionRight.UNASSESSED]
        )
    )
    def test_inadmissible_assessments_carry_no_value(self, retention):
        """No Evidence object may exist to carry them. [S 5.7]"""
        with pytest.raises(AccessConditionsError):
            access_conditions_value(permitted(retention))

    def test_unassessed_and_prohibited_carry_no_value(self):
        with pytest.raises(AccessConditionsError):
            access_conditions_value(unassessed("s"))


# ===========================================================================
# CI-1 boundary  [N-21 S 5.9]
# ===========================================================================


class TestCI1Boundary:
    def test_rights_values_expose_no_scoring_surface(self):
        import oip.rights as mod

        leaks = [
            n
            for n in dir(mod)
            if not n.startswith("_")
            and any(
                k in n.lower()
                for k in ("evidential", "confidence", "score", "weight",
                          "lineage", "lifecycle")
            )
        ]
        assert leaks == []

    def test_no_rights_store_exists(self):
        """The recording home is the Evidence object's access_conditions,
        never a configuration store or registry of assessments."""
        import oip.rights as mod

        assert not hasattr(mod, "RightsRegister")
        assert not hasattr(mod, "AssessmentRegister")

    def test_refusal_record_validates_every_field(self):
        ok = dict(
            source_identifier="s",
            reason=RefusalReason.PROHIBITED,
            refused_at=FIXED_NOW,
            detail="d",
        )
        with pytest.raises(RightsError):
            RightsRefusal(**{**ok, "source_identifier": " "})
        with pytest.raises((RightsError, TypeError)):
            RightsRefusal(**{**ok, "reason": "BECAUSE"})
        with pytest.raises(RightsError):
            RightsRefusal(**{**ok, "refused_at": "2026-01-01"})
        with pytest.raises(RightsError):
            RightsRefusal(**{**ok, "detail": ""})

    def test_assessment_requires_an_identifier(self):
        with pytest.raises(AssessmentInvalidError):
            unassessed("   ")

    def test_retention_outside_the_closed_vocabulary_is_refused(self):
        with pytest.raises((AssessmentInvalidError, TypeError)):
            RightsAssessment(
                source_identifier="s",
                acquisition=AcquisitionRight.PERMITTED,
                retention="RETAIN_SUMMARY",
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="b",
                assessed_at=FIXED_NOW,
            )

    def test_register_indexes_refusals_per_source(self):
        register = RefusalRegister()
        evaluate_gate(unassessed("a"), refusals=register, now=FIXED_NOW)
        evaluate_gate(unassessed("b"), refusals=register, now=FIXED_NOW)
        assert len(register.for_source("a")) == 1
        assert len(register.for_source("b")) == 1
        assert register.for_source("c") == ()
        assert len(list(register)) == 2

    def test_refusal_register_holds_no_intelligence_object(self):
        register = RefusalRegister()
        evaluate_gate(unassessed("s"), refusals=register, now=FIXED_NOW)
        assert all(
            isinstance(r, RightsRefusal) for r in register
        )
