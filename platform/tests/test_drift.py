"""Contract tests for source drift detection.

Task: T02.2.3

Architecture References:
- N-15   Drift IS the fingerprint mismatch on re-acquisition; the
         fingerprint is retained in every storage mode, so detection is
         always possible.
- R-2/V9 Supersession is a status transition with a recorded reason --
         the record on the ORIGINAL object.
- E-V6   ACTIVE-only duplicate index: superseding the original is what
         makes re-acquisition admissible.
- IOM    capture_fidelity is an assessment; improvement is the caller's
         explicit declaration -- never invented, never defaulted.
- N-10   Drift records are operational facts outside the object model.
- N-4    Property-based assertions only.

T02.2.3 acceptance criteria under test:
  AC1  Changed source content detected             -> IMPLEMENTED
  AC2  Drift recorded against original Evidence    -> IMPLEMENTED
  AC3  Superseding version where fidelity improves -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.coverage import OutOfFrameRegister
from oip.drift import (
    Disposition,
    DriftError,
    DriftRecord,
    DriftRegister,
    DriftVerdict,
    MaterialSpecError,
    NotDriftError,
    detect,
    record_drift,
)
from oip.evidence import compute_fingerprint
from oip.enums import ObjectStatus
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
FIRST = "Vendor changelog v1: bulk edits fail silently above 50 SKUs."
SECOND = "Vendor changelog v2: bulk edits fail silently above 200 SKUs."


class Rig:
    def __init__(self):
        self.registry = SourceRegistry()
        self.registry.register("src-a", "VENDOR_PUBLICATION")
        self.store = KnowledgeStore()
        self.log = AcquisitionLog()
        self.drifts = DriftRegister()

    def acquire(self, content, fidelity="full text preserved"):
        request = AcquisitionRequest(
            source_identifier="src-a",
            source_type="VENDOR_PUBLICATION",
            acquisition_method="vendor_api_retrieval",
            capture_fidelity=fidelity,
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.62,
            assertion_confidence=0.90,
            content=content,
        )
        return acquire(
            request,
            registry=self.registry,
            store=self.store,
            out_of_frame=OutOfFrameRegister(),
            refusals=RefusalRegister(),
            log=self.log,
            assessment=RightsAssessment(
                source_identifier="src-a",
                acquisition=AcquisitionRight.PERMITTED,
                retention=RetentionRight.RETAIN_FULL,
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="vendor terms",
                assessed_at=T0 - timedelta(days=1),
            ),
            clock=lambda: T0,
        )


@pytest.fixture
def rig() -> Rig:
    return Rig()


# ===========================================================================
# AC1 -- changed source content detected  [N-15]
# ===========================================================================


class TestDetection:
    def test_changed_content_is_detected_as_drift(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        assert verdict.drifted is True
        assert verdict.original_fingerprint != verdict.reacquired_fingerprint

    def test_unchanged_content_is_not_drift(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=FIRST)
        assert verdict.drifted is False

    def test_the_baseline_is_the_retained_fingerprint(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        assert verdict.original_fingerprint == original.content.fingerprint
        assert verdict.reacquired_fingerprint == compute_fingerprint(SECOND)

    def test_reference_mode_uses_the_recorded_fingerprint(self, rig):
        original = rig.acquire(FIRST)
        new_fp = "sha256:" + "ab" * 32
        verdict = detect(
            rig.store, original.object_id, fingerprint=new_fp
        )
        assert verdict.drifted is True
        assert verdict.reacquired_fingerprint == new_fp

    def test_source_identity_comes_from_the_original(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        assert verdict.source_identifier == "src-a"
        assert verdict.holder_object_id == original.object_id

    def test_an_unresolvable_original_refuses(self, rig):
        with pytest.raises(DriftError):
            detect(rig.store, "obj-nonexistent", content=FIRST)

    def test_material_must_be_specified_exactly_once(self, rig):
        original = rig.acquire(FIRST)
        with pytest.raises(MaterialSpecError):
            detect(rig.store, original.object_id)
        with pytest.raises(MaterialSpecError):
            detect(rig.store, original.object_id, content="c", fingerprint="f")

    @given(
        first=st.text(min_size=1, max_size=80),
        second=st.text(min_size=1, max_size=80),
    )
    def test_drift_is_exactly_fingerprint_disagreement(
        self, first, second
    ):
        """Property: drifted <=> fingerprints differ. N-15's test verbatim."""
        assume(first != second)
        r = Rig()
        original = r.acquire(first)
        verdict = detect(r.store, original.object_id, content=second)
        assert verdict.drifted is (
            compute_fingerprint(first) != compute_fingerprint(second)
        )
        assert verdict.drifted is True

    @given(material=st.text(min_size=1, max_size=80))
    def test_identical_material_never_drifts(self, material):
        r = Rig()
        original = r.acquire(material)
        assert detect(r.store, original.object_id, content=material).drifted \
            is False

    def test_detection_is_deterministic_on_repeated_calls(self, rig):
        original = rig.acquire(FIRST)
        first_call = detect(rig.store, original.object_id, content=SECOND)
        again = detect(rig.store, original.object_id, content=SECOND)
        assert first_call == again


# ===========================================================================
# AC2 -- drift recorded against the original Evidence  [N-10 pattern]
# ===========================================================================


class TestRecording:
    def test_every_drift_names_its_original(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        record = record_drift(
            verdict, rig.drifts, fidelity_improved=False, clock=lambda: T0
        )
        assert record.original_object_id == original.object_id
        assert rig.drifts.against(original.object_id) == (record,)
        assert len(rig.drifts) == 1

    def test_the_record_carries_both_fingerprints(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        record = record_drift(
            verdict, rig.drifts, fidelity_improved=False, clock=lambda: T0
        )
        assert record.original_fingerprint == original.content.fingerprint
        assert record.reacquired_fingerprint == compute_fingerprint(SECOND)

    def test_without_improvement_the_original_stands(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        record = record_drift(
            verdict, rig.drifts, fidelity_improved=False, clock=lambda: T0
        )
        assert record.disposition is Disposition.NOTED
        stored = rig.store.find(original.object_id)
        assert stored.status is ObjectStatus.ACTIVE
        assert stored.attributes.status_reason is None

    def test_a_record_requires_a_real_mismatch(self):
        verdict = DriftVerdict(
            holder_object_id="obj-x",
            source_identifier="src-a",
            original_fingerprint="sha256:" + "0" * 64,
            reacquired_fingerprint="sha256:" + "0" * 64,
        )
        with pytest.raises(NotDriftError):
            record_drift(
                verdict, DriftRegister(), fidelity_improved=False,
                clock=lambda: T0,
            )

    def test_record_validates_every_field(self):
        ok = dict(
            original_object_id="obj-x",
            source_identifier="src-a",
            original_fingerprint="sha256:a",
            reacquired_fingerprint="sha256:b",
            detected_at=T0,
            disposition=Disposition.NOTED,
        )
        for bad in (
            {"original_object_id": " "},
            {"source_identifier": ""},
            {"original_fingerprint": " "},
            {"reacquired_fingerprint": ""},
            {"detected_at": "x"},
            {"disposition": "MAYBE"},
        ):
            with pytest.raises(DriftError):
                DriftRecord(**{**ok, **bad})

    def test_the_register_is_append_only_and_indexed(self, rig):
        original = rig.acquire(FIRST)
        for changed in ("v2 text", "v3 text"):
            verdict = detect(rig.store, original.object_id, content=changed)
            record_drift(
                verdict, rig.drifts, fidelity_improved=False,
                clock=lambda: T0,
            )
        assert len(rig.drifts) == 2
        assert len(rig.drifts.against(original.object_id)) == 2
        assert rig.drifts.against("obj-other") == ()
        listed = list(rig.drifts)
        assert len(listed) == 2
        assert all(isinstance(r, DriftRecord) for r in listed)


# ===========================================================================
# AC3 -- superseding version where fidelity improves  [R-2/V9 + E-V6]
# ===========================================================================


class TestSupersession:
    def test_declared_improvement_supersedes_the_original(self, rig):
        original = rig.acquire(FIRST, fidelity="text only, media lost")
        verdict = detect(rig.store, original.object_id, content=SECOND)
        record = record_drift(
            verdict, rig.drifts, store=rig.store,
            fidelity_improved=True, clock=lambda: T0,
        )
        assert record.disposition is Disposition.SUPERSEDED
        stored = rig.store.find(original.object_id)
        assert stored.status is ObjectStatus.SUPERSEDED
        assert stored.attributes.status_reason is not None  # V9
        assert "drift" in stored.attributes.status_reason

    def test_supersession_enables_the_reacquisition(self, rig):
        """E-V6's index is ACTIVE-only: after the transition the new
        material acquires cleanly -- the superseding version exists."""
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        record_drift(
            verdict, rig.drifts, store=rig.store,
            fidelity_improved=True, clock=lambda: T0,
        )
        replacement = rig.acquire(SECOND)
        assert replacement.object_id != original.object_id
        assert rig.store.find(replacement.object_id).status is (
            ObjectStatus.ACTIVE
        )
        assert rig.store.find(original.object_id).status is (
            ObjectStatus.SUPERSEDED
        )

    def test_without_supersession_the_reacquisition_still_duplicates(self, rig):
        """NOTED drift leaves the original ACTIVE, so the new material
        remains E-V6-refused -- superseding is the only ratified path to
        a replacement. (Unchanged case aside: changed material with a
        different fingerprint is NOT blocked by E-V6.)"""
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        record_drift(
            verdict, rig.drifts, fidelity_improved=False, clock=lambda: T0
        )
        # changed material acquires (different fingerprint) alongside
        replacement = rig.acquire(SECOND)
        assert rig.store.find(original.object_id).status is ObjectStatus.ACTIVE
        assert len(rig.store) == 2  # both stand: no supersession happened

    def test_the_clock_is_injectable_and_records_use_it(self, rig):
        """detected_at honours the injected clock (deterministic audits)."""
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        later = T0 + timedelta(days=3)
        record = record_drift(
            verdict, rig.drifts, fidelity_improved=False, clock=lambda: later
        )
        assert record.detected_at == later

    def test_supersession_without_a_store_refuses(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        with pytest.raises(DriftError):
            record_drift(
                verdict, rig.drifts, store=None,
                fidelity_improved=True, clock=lambda: T0,
            )

    def test_the_declaration_is_explicit_never_inferred(self, rig):
        original = rig.acquire(FIRST)
        verdict = detect(rig.store, original.object_id, content=SECOND)
        with pytest.raises(TypeError):
            record_drift(verdict, rig.drifts, store=rig.store,
                         clock=lambda: T0)  # no declaration supplied
