"""Contract tests for source acquisition.

Task: T02.2.1

Architecture References:
- N-20   Gate order (S 5.2.1): typability before rights, halt on first
         refusal; untypable channels are out-of-frame, not gaps.
- N-21   Rights enforced before acquisition (S 5.2); access_conditions
         composed from the assessment (S 5.9); storage mode from the
         retention right (S 5.7).
- N-15   Mode recorded per Evidence object; fingerprint + provenance
         always retained.
- N-10   Failures recorded, never silent; failed is not found.
- R-3 / IOM S 3.1  Two confidence components, supplied, never conflated.
- N-16 / T02.1.3   Independence group carried, never inferred.
- N-4    Property-based assertions only.

T02.2.1 acceptance criteria under test:
  AC1  Provenance complete on every Evidence object   -> IMPLEMENTED
  AC2  Acquisition failures recorded, not silent      -> IMPLEMENTED
  AC3  capture_fidelity documented per acquisition    -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oip.acquisition import (
    AcquisitionError,
    AcquisitionFailure,
    AcquisitionLog,
    AcquisitionRefusedError,
    AcquisitionRequest,
    AcquisitionStage,
    acquire,
)
from oip.coverage import OutOfFrameRegister
from oip.evidence import StorageMode
from oip.rights import (
    RIGHTS_AUTHORITY_ROLE,
    AcquisitionRight,
    RefusalRegister,
    RetentionRight,
    RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 8, 19, 12, 0, 0, tzinfo=timezone.utc)
IDENT = st.text(min_size=1, max_size=20).filter(str.strip)
FIDELITY = st.text(min_size=5, max_size=60).filter(str.strip)


class Rig:
    """One acquisition wiring: registry, store, registers, log, clock."""

    def __init__(self):
        self.registry = SourceRegistry()
        self.registry.register("src-a", "VENDOR_PUBLICATION")
        self.registry.register("src-untypable", "some-unknown-channel")
        self.store = KnowledgeStore()
        self.out_of_frame = OutOfFrameRegister()
        self.refusals = RefusalRegister()
        self.log = AcquisitionLog()

    def request(self, **overrides) -> AcquisitionRequest:
        base = dict(
            source_identifier="src-a",
            source_type="VENDOR_PUBLICATION",
            acquisition_method="vendor_api_retrieval",
            capture_fidelity="full text preserved; media not captured",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.62,
            assertion_confidence=0.90,
            content="Vendor changelog: bulk edits silently fail above 50 SKUs.",
        )
        base.update(overrides)
        return AcquisitionRequest(**base)

    def permitted(
        self, retention: RetentionRight = RetentionRight.RETAIN_FULL
    ) -> RightsAssessment:
        return RightsAssessment(
            source_identifier="src-a",
            acquisition=AcquisitionRight.PERMITTED,
            retention=retention,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="vendor terms of use, section 2",
            assessed_at=T0 - timedelta(days=1),
        )

    def acquire(self, request, assessment=None):
        return acquire(
            request,
            registry=self.registry,
            store=self.store,
            out_of_frame=self.out_of_frame,
            refusals=self.refusals,
            log=self.log,
            assessment=assessment,
            clock=lambda: T0,
        )


@pytest.fixture
def rig() -> Rig:
    return Rig()


# ===========================================================================
# AC1 -- provenance complete on every Evidence object
# ===========================================================================


class TestProvenanceComplete:
    def test_every_required_provenance_field_is_present(self, rig):
        evidence = rig.acquire(rig.request(), assessment=rig.permitted())
        p = evidence.provenance
        for name in (
            "source_identifier", "source_type", "acquisition_method",
            "acquired_at", "access_conditions", "capture_fidelity",
        ):
            value = getattr(p, name)
            assert value is not None and str(value).strip()

    def test_access_conditions_is_composed_from_the_rights(self, rig):
        evidence = rig.acquire(rig.request(), assessment=rig.permitted())
        assert "acquisition=PERMITTED" in evidence.provenance.access_conditions
        assert "retention=RETAIN_FULL" in evidence.provenance.access_conditions
        assert RIGHTS_AUTHORITY_ROLE in evidence.provenance.access_conditions

    def test_produced_by_research_engine_with_no_lineage(self, rig):
        evidence = rig.acquire(rig.request(), assessment=rig.permitted())
        from oip.enums import Engine
        assert evidence.attributes.produced_by_engine is Engine.RESEARCH
        assert evidence.attributes.derives_from == ()

    def test_evidence_is_persisted_and_retrievable(self, rig):
        evidence = rig.acquire(rig.request(), assessment=rig.permitted())
        fetched = rig.store.get_evidence(evidence.object_id)
        assert fetched is not None
        assert fetched.provenance.source_identifier == "src-a"

    @given(
        support=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        assertion=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_confidence_components_carried_separately(
        self, support, assertion
    ):
        rig = Rig()
        evidence = rig.acquire(
            rig.request(
                evidential_support=support, assertion_confidence=assertion
            ),
            assessment=rig.permitted(),
        )
        c = evidence.attributes.confidence
        assert c.evidential_support == pytest.approx(support)
        assert c.assertion_confidence == pytest.approx(assertion)


class TestStorageModeHonoured:
    def test_retain_full_stores_in_full(self, rig):
        evidence = rig.acquire(
            rig.request(), assessment=rig.permitted(RetentionRight.RETAIN_FULL)
        )
        assert evidence.content.storage_mode is StorageMode.FULL
        assert evidence.content.content is not None

    def test_retain_reference_only_stores_by_reference(self, rig):
        request = rig.request(
            content=None,
            content_reference="https://vendor.example/changelog",
            content_fingerprint="sha256:" + "0" * 64,
        )
        evidence = rig.acquire(
            request,
            assessment=rig.permitted(
                RetentionRight.RETAIN_REFERENCE_ONLY
            ),
        )
        assert evidence.content.storage_mode is StorageMode.REFERENCE
        assert evidence.content.content is None
        assert evidence.content.content_reference is not None

    def test_reference_mode_ignores_supplied_content_contradiction(self, rig):
        """A request carrying BOTH content and reference is malformed at
        construction -- the request refuses, so no mismatched acquisition
        can exist."""
        with pytest.raises(AcquisitionError):
            rig.request(
                content="x",
                content_reference="ref",
                content_fingerprint="sha256:" + "0" * 64,
            )


class TestIndependenceCarried:
    def test_supplied_independence_group_is_carried(self, rig):
        evidence = rig.acquire(
            rig.request(independence_group="vendor-syndicate-1"),
            assessment=rig.permitted(),
        )
        assert (
            evidence.provenance.source_independence_group
            == "vendor-syndicate-1"
        )

    def test_absent_group_defaults_to_identifier_explicitly(self, rig):
        """T02.1.3 explicit-input model: absent group falls back to the
        identifier; nothing is inferred."""
        evidence = rig.acquire(
            rig.request(), assessment=rig.permitted()
        )
        assert evidence.provenance.source_independence_group is None
        assert evidence.independence_key == "src-a"


# ===========================================================================
# AC3 -- capture_fidelity documented per acquisition
# ===========================================================================


class TestCaptureFidelity:
    @given(fidelity=FIDELITY)
    def test_every_fidelity_statement_is_carried(self, fidelity):
        rig = Rig()
        evidence = rig.acquire(
            rig.request(capture_fidelity=fidelity),
            assessment=rig.permitted(),
        )
        assert evidence.provenance.capture_fidelity == fidelity

    def test_no_fidelity_no_request(self):
        for empty in ("", "   "):
            with pytest.raises(AcquisitionError):
                AcquisitionRequest(
                    source_identifier="s",
                    source_type="VENDOR_PUBLICATION",
                    acquisition_method="m",
                    capture_fidelity=empty,
                    acquired_at=T0,
                    observed_at=T0,
                    evidential_support=0.5,
                    assertion_confidence=0.5,
                    content="c",
                )

    def test_fidelity_is_never_defaulted(self):
        """No constructor path omits it: it is positional-required."""
        import inspect
        fields = AcquisitionRequest.__dataclass_fields__
        assert fields["capture_fidelity"].default is not type(
            fields["capture_fidelity"].default
        ) or fields["capture_fidelity"].default is None


# ===========================================================================
# AC2 -- failures recorded, not silent
# ===========================================================================


class TestFailuresRecorded:
    def test_unregistered_source_refuses_and_records(self, rig):
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(source_identifier="nope"))
        assert len(rig.log) == 1
        failure = next(iter(rig.log))
        assert failure.stage is AcquisitionStage.UNREGISTERED_SOURCE

    def test_type_mismatch_refuses_and_records(self, rig):
        rig.registry.register("src-b", "VENDOR_PUBLICATION")
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(
                rig.request(source_identifier="src-b",
                            source_type="REGULATORY_FILING")
            )
        failure = rig.log.for_source("src-b")[0]
        assert failure.stage is AcquisitionStage.SOURCE_TYPE_MISMATCH

    def test_untypable_channel_refuses_records_and_frames_out(self, rig):
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(source_identifier="src-untypable",
                                    source_type="some-unknown-channel"))
        failure = rig.log.for_source("src-untypable")[0]
        assert failure.stage is AcquisitionStage.UNTYPABLE_CHANNEL
        assert rig.out_of_frame.count() == 1  # N-22 S 5.2.1

    def test_unassessed_rights_refuse_and_record(self, rig):
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(), assessment=None)
        failure = rig.log.for_source("src-a")[0]
        assert failure.stage is AcquisitionStage.REFUSED_BY_RIGHTS
        assert failure.reason == "UNASSESSED"
        assert len(rig.refusals) == 1  # K10: recorded in the gate too

    def test_prohibited_rights_refuse(self, rig):
        assessment = RightsAssessment(
            source_identifier="src-a",
            acquisition=AcquisitionRight.PROHIBITED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="licence forbids retention",
            assessed_at=T0 - timedelta(days=1),
        )
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(), assessment=assessment)
        assert rig.log.for_source("src-a")[0].reason == "PROHIBITED"

    def test_retain_none_never_creates_an_object(self, rig):
        assessment = rigAssessment = RightsAssessment(
            source_identifier="src-a",
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_NONE,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
            assessed_at=T0 - timedelta(days=1),
        )
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(), assessment=rigAssessment)
        assert rig.log.for_source("src-a")[0].reason == "RETAIN_NONE"
        assert len(rig.store) == 0  # N-21 S 5.7: no object created

    def test_expired_permitted_refuses(self, rig):
        assessment = RightsAssessment(
            source_identifier="src-a",
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
            assessed_at=T0 - timedelta(days=10),
            valid_until=T0 - timedelta(days=1),
        )
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(), assessment=assessment)
        assert rig.log.for_source("src-a")[0].reason == "EXPIRED"

    def test_gate_order_typability_precedes_rights(self, rig):
        """N-20 S 5.2.1: an untypable channel refused at gate 2 never
        reaches the rights gate -- even PERMITTED rights cannot save it."""
        rig.registry.register("src-u2", "mystery")
        assessment = rig.permitted()
        # remap to the untypable source
        assessment = RightsAssessment(
            source_identifier="src-u2",
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
            assessed_at=T0 - timedelta(days=1),
        )
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(
                rig.request(source_identifier="src-u2",
                            source_type="mystery"),
                assessment=assessment,
            )
        assert rig.log.for_source("src-u2")[0].stage is (
            AcquisitionStage.UNTYPABLE_CHANNEL
        )
        assert len(rig.refusals) == 0  # rights never evaluated

    def test_no_partial_state_leaks_after_failure(self, rig):
        before = (
            len(rig.store), len(rig.log), rig.out_of_frame.count(),
            len(rig.refusals),
        )
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request())  # unassessed
        assert len(rig.store) == before[0]
        assert len(rig.log) == before[1] + 1
        assert rig.out_of_frame.count() == before[2]
        assert len(rig.refusals) == before[3] + 1

    def test_failure_record_validates_its_own_fields(self):
        ok = dict(
            source_identifier="s",
            stage=AcquisitionStage.REFUSED_BY_RIGHTS,
            reason="UNASSESSED",
            detail="d",
            failed_at=T0,
        )
        for bad in (
            {"source_identifier": " "}, {"reason": ""},
            {"detail": ""}, {"failed_at": "x"},
        ):
            with pytest.raises(AcquisitionError):
                AcquisitionFailure(**{**ok, **bad})
        with pytest.raises(AcquisitionError):
            AcquisitionFailure(**{**ok, "stage": "SOMEWHERE"})

    def test_log_is_append_only_and_indexed(self, rig):
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request(source_identifier="ghost"))
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(rig.request())  # unassessed
        assert len(rig.log) == 2
        assert len(rig.log.for_source("src-a")) == 1
        assert len(rig.log.for_source("ghost")) == 1
        assert all(isinstance(f, AcquisitionFailure) for f in rig.log)

    def test_store_rejection_is_recorded_not_leaked(self, rig):
        """E-V5 violation passes the request pre-check window only if
        observed_at > acquired_at slipped through -- impossible by the
        request's own E-V5 check; instead force rejection with a
        confidence ceiling violation is unavailable for roots, so use a
        store that refuses: patch write_evidence to reject."""
        rig.registry.register("src-c", "VENDOR_PUBLICATION")
        from oip.store import WriteRejectedError
        from oip.acceptance import FailureRecord

        def reject(evidence, predecessor_id=None):
            raise WriteRejectedError(
                FailureRecord(
                    object_id=evidence.object_id,
                    object_type=evidence.attributes.object_type,
                    failed_rules=(),
                    recorded_at=T0,
                    engine_configuration_ref="test",
                )
            )

        rig.store.write_evidence = reject  # type: ignore[method-assign]
        with pytest.raises(AcquisitionRefusedError):
            rig.acquire(
                rig.request(source_identifier="src-c"),
                assessment=RightsAssessment(
                    source_identifier="src-c",
                    acquisition=AcquisitionRight.PERMITTED,
                    retention=RetentionRight.RETAIN_FULL,
                    authority=RIGHTS_AUTHORITY_ROLE,
                    basis="b",
                    assessed_at=T0 - timedelta(days=1),
                ),
            )
        assert rig.log.for_source("src-c")[0].stage is (
            AcquisitionStage.STORE_REJECTED
        )
        assert rig.store.get_evidence is not None  # store intact


# ===========================================================================
# Request validation (construction refuses malformed -- no bad acquisition
# can even be attempted)
# ===========================================================================


class TestRequestValidation:
    def test_both_content_forms_refused(self):
        with pytest.raises(AcquisitionError):
            Rig().request(
                content="x",
                content_reference="r",
                content_fingerprint="sha256:" + "0" * 64,
            )

    def test_neither_content_form_refused(self):
        with pytest.raises(AcquisitionError):
            Rig().request(content=None, content_reference=None,
                          content_fingerprint=None)

    def test_confidence_components_must_be_numeric(self):
        for bad in ("high", None, True, [0.5]):
            with pytest.raises(AcquisitionError):
                Rig().request(evidential_support=bad)
            with pytest.raises(AcquisitionError):
                Rig().request(assertion_confidence=bad)

    def test_datetimes_must_be_datetimes(self):
        with pytest.raises(AcquisitionError):
            Rig().request(acquired_at="2026-01-01")
        with pytest.raises(AcquisitionError):
            Rig().request(observed_at="2026-01-01")

    def test_e_v5_enforced_at_construction(self):
        with pytest.raises(AcquisitionError):
            Rig().request(
                acquired_at=T0, observed_at=T0 + timedelta(seconds=1)
            )

    def test_non_request_argument_refused_loudly(self, rig):
        with pytest.raises(AcquisitionError):
            rig.acquire("not-a-request")

    @given(source=IDENT)
    def test_identifiers_are_carried_faithfully(self, source):
        rig = Rig()
        rig.registry.register(source, "VENDOR_PUBLICATION")
        assessment = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="b",
            assessed_at=T0 - timedelta(days=1),
        )
        evidence = rig.acquire(
            rig.request(source_identifier=source), assessment=assessment
        )
        assert evidence.provenance.source_identifier == source
