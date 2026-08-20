"""Contract tests for duplicate detection.

Task: T02.2.2

Architecture References:
- E-V6    The refusal key is (content_fingerprint, source_identifier)
          over ACTIVE Evidence; cross-source same fingerprint is
          corroboration, never duplication.
- N-03    "Duplicate rate" is a named stage-1 measure; no formula is
          ratified, so none is invented -- counts and fail-closed
          arithmetic only.
- N-10    Duplicate refusals carry their own stage (DUPLICATE_ACQUISITION),
          distinguishable from every other failure.
- N-4     Property-based assertions only.

T02.2.2 acceptance criteria under test:
  AC1  Same fingerprint plus source rejected    -> IMPLEMENTED (classified)
  AC2  Re-acquisition detectable                -> IMPLEMENTED
  AC3  Duplicate rate measurable                -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from oip.acquisition import (
    AcquisitionLog,
    AcquisitionRequest,
    AcquisitionStage,
    acquire,
)
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.coverage import OutOfFrameRegister
from oip.duplicates import (
    DuplicateError,
    MaterialSpecError,
    duplicate_rate,
    duplicate_refusals,
    held_duplicate,
)
from oip.evidence import compute_fingerprint
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
MATERIAL = "Vendor changelog: bulk edits silently fail above 50 SKUs."


COVERED_TARGETS = ('src-a', 'src-b', 'src-c', 'src-u', 'src-u2', 'src-untypable')


class Rig:
    def __init__(self):
        self.registry = SourceRegistry()
        self.registry.register("src-a", "VENDOR_PUBLICATION")
        self.registry.register("src-b", "VENDOR_PUBLICATION")
        self.store = KnowledgeStore()
        self.log = AcquisitionLog()
        self.directives = DirectiveRegistry()
        self.directives.raise_directive(Directive(
            directive_id="dir-1",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="commissioning-owner",
            description="seller-side friction, segment A",
            targets=COVERED_TARGETS,
            raised_at=T0 - timedelta(days=2),
        ))
        self.directives.effect("dir-1", now=T0)

    def request(self, source="src-a", content=MATERIAL, **ov):
        base = dict(
            source_identifier=source,
            source_type="VENDOR_PUBLICATION",
            acquisition_method="vendor_api_retrieval",
            capture_fidelity="full text preserved",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.62,
            assertion_confidence=0.90,
            content=content,
        )
        base.update(ov)
        return AcquisitionRequest(**base)

    def acquire(self, request, source="src-a"):
        retention = (
            RetentionRight.RETAIN_REFERENCE_ONLY
            if request.content is None
            else RetentionRight.RETAIN_FULL
        )
        assessment = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=retention,
            authority=RIGHTS_AUTHORITY_ROLE,
            basis="vendor terms",
            assessed_at=T0 - timedelta(days=1),
        )
        return acquire(
            request,
            registry=self.registry,
            store=self.store,
            out_of_frame=OutOfFrameRegister(),
            refusals=RefusalRegister(),
            log=self.log,
            directives=self.directives,
            assessment=assessment,
            clock=lambda: T0,
        )


@pytest.fixture
def rig() -> Rig:
    return Rig()


# ===========================================================================
# AC1 -- same fingerprint plus source rejected, as a CLASSIFIED outcome
# ===========================================================================


class TestDuplicateRejection:
    def test_reacquiring_the_same_material_is_refused(self, rig):
        rig.acquire(rig.request())
        with pytest.raises(Exception) as exc:
            rig.acquire(rig.request())
        assert "E-V6" in str(exc.value)

    def test_the_refusal_is_classified_not_generic(self, rig):
        rig.acquire(rig.request())
        with pytest.raises(Exception):
            rig.acquire(rig.request())
        failure = rig.log.for_source("src-a")[-1]
        assert failure.stage is AcquisitionStage.DUPLICATE_ACQUISITION
        assert failure.reason == "E-V6"

    def test_only_the_duplicate_is_refused_other_failures_stay_generic(
        self, rig,
    ):
        """A non-E-V6 store rejection must NOT be mislabelled duplicate."""
        from oip.acceptance import FailureRecord
        from oip.store import WriteRejectedError
        from oip.enums import ObjectType

        def reject(evidence, predecessor_id=None):
            raise WriteRejectedError(
                FailureRecord(
                    object_id=evidence.object_id,
                    object_type=ObjectType.EVIDENCE,
                    failed_rules=(),
                    recorded_at=T0,
                    engine_configuration_ref="test",
                )
            )

        rig.store.write_evidence = reject  # type: ignore[method-assign]
        with pytest.raises(Exception):
            rig.acquire(rig.request(content="other material"))
        failure = rig.log.for_source("src-a")[-1]
        assert failure.stage is AcquisitionStage.STORE_REJECTED
        assert failure.stage is not AcquisitionStage.DUPLICATE_ACQUISITION

    def test_no_evidence_created_for_the_duplicate(self, rig):
        rig.acquire(rig.request())
        size = len(rig.store)
        with pytest.raises(Exception):
            rig.acquire(rig.request())
        assert len(rig.store) == size

    def test_same_source_different_material_is_not_a_duplicate(self, rig):
        rig.acquire(rig.request(content="first material"))
        second = rig.acquire(rig.request(content="second material"))
        assert second.provenance.source_identifier == "src-a"

    def test_same_material_different_source_is_corroboration(self, rig):
        """E-V6's key includes the source: cross-source acquisition is
        legitimate independent corroboration, never duplication."""
        a = rig.acquire(rig.request(source="src-a"))
        b = rig.acquire(rig.request(source="src-b"))
        assert a.object_id != b.object_id
        assert len(rig.store) == 2
        assert duplicate_refusals(rig.log) == 0


# ===========================================================================
# AC2 -- re-acquisition detectable
# ===========================================================================


class TestDetection:
    def test_held_duplicate_resolves_the_active_holder(self, rig):
        first = rig.acquire(rig.request())
        assert held_duplicate(
            rig.store, "src-a", content=MATERIAL
        ) == first.object_id

    def test_new_material_reports_none(self, rig):
        rig.acquire(rig.request())
        assert held_duplicate(
            rig.store, "src-a", content="unseen material"
        ) is None

    def test_reference_mode_uses_the_recorded_fingerprint(self, rig):
        fingerprint = "sha256:" + "ab" * 32
        request = rig.request(
            content=None,
            content_reference="https://vendor.example/log",
            content_fingerprint=fingerprint,
        )
        first = rig.acquire(request)
        assert held_duplicate(
            rig.store, "src-a", fingerprint=fingerprint
        ) == first.object_id

    def test_detection_is_keyed_exactly_fingerprint_plus_source(self, rig):
        first = rig.acquire(rig.request())
        # Same material, OTHER source: not held for that source.
        assert held_duplicate(
            rig.store, "src-b", content=MATERIAL
        ) is None
        # The fingerprint computed here equals the stored one (E-V4).
        assert compute_fingerprint(MATERIAL) == first.content.fingerprint

    def test_material_held_by_another_source_is_not_a_duplicate(self, rig):
        """The source is part of the E-V6 key: material held only by
        src-a is NOT held for src-b, however identical the content."""
        rig.acquire(rig.request(source="src-a", content=MATERIAL))
        assert held_duplicate(rig.store, "src-a", content=MATERIAL) is not None
        assert held_duplicate(rig.store, "src-b", content=MATERIAL) is None

    def test_material_must_be_specified_exactly_once(self, rig):
        with pytest.raises(MaterialSpecError):
            held_duplicate(rig.store, "src-a")
        with pytest.raises(MaterialSpecError):
            held_duplicate(
                rig.store, "src-a", content="c", fingerprint="f"
            )

    @given(
        material=st.text(min_size=1, max_size=80),
        other=st.text(min_size=1, max_size=80),
    )
    def test_detection_is_exact_over_arbitrary_material(
        self, material, other
    ):
        """Property: detection follows the fingerprint, not heuristics."""
        assume(other != material)
        r = Rig()
        held = r.acquire(r.request(content=material))
        assert held_duplicate(r.store, "src-a", content=material) == (
            held.object_id
        )
        assert held_duplicate(r.store, "src-a", content=other) is None


# ===========================================================================
# AC3 -- duplicate rate measurable  [N-03 names it; no formula invented]
# ===========================================================================


class TestRate:
    def test_counts_come_from_recorded_facts(self, rig):
        rig.acquire(rig.request(content="m1"))
        with pytest.raises(Exception):
            rig.acquire(rig.request(content="m1"))  # duplicate
        rig.acquire(rig.request(content="m2"))
        with pytest.raises(Exception):
            rig.acquire(rig.request(content="m2"))  # duplicate
        assert duplicate_refusals(rig.log) == 2

    def test_only_duplicates_are_counted(self, rig):
        """A log mixing failure stages counts DUPLICATE refusals only --
        the count must stay distinguishable from every other failure
        (N-10)."""
        rig.acquire(rig.request(content="m1"))
        with pytest.raises(Exception):
            rig.acquire(rig.request(content="m1"))  # duplicate -> log
        # a rights refusal enters the same log, but is NOT a duplicate
        from oip.acquisition import acquire as _acquire
        request = rig.request(content="m2")
        with pytest.raises(Exception):
            _acquire(
                request,
                registry=rig.registry,
                store=rig.store,
                out_of_frame=OutOfFrameRegister(),
                refusals=RefusalRegister(),
                log=rig.log,
                assessment=None,  # UNASSESSED refuses
                clock=lambda: T0,
            )
        assert len(rig.log) == 2
        assert duplicate_refusals(rig.log) == 1

    def test_rate_is_pure_arithmetic(self):
        assert duplicate_rate(0, 10) == 0.0
        assert duplicate_rate(1, 4) == 0.25
        assert duplicate_rate(3, 3) == 1.0

    def test_an_empty_history_is_undefined_never_defaulted(self):
        """Zero attempts report None -- never 0.0, never 1.0 (the same
        honesty rule N-22 S 5.7 applies to coverage)."""
        assert duplicate_rate(0, 0) is None
        assert duplicate_rate(0, 0) != 0.0
        assert duplicate_rate(0, 0) != 1.0

    def test_impossible_counts_are_refused(self):
        for bad in ((-1, 5), (1, -5), (5, 3), (-2, -2)):
            with pytest.raises(DuplicateError):
                duplicate_rate(*bad)

    @given(
        duplicates=st.integers(min_value=0, max_value=50),
        attempts=st.integers(min_value=0, max_value=50),
    )
    def test_rate_is_a_share_or_undefined(self, duplicates, attempts):
        if duplicates > attempts:
            with pytest.raises(DuplicateError):
                duplicate_rate(duplicates, attempts)
        elif attempts == 0:
            assert duplicate_rate(duplicates, attempts) is None
        else:
            rate = duplicate_rate(duplicates, attempts)
            assert 0.0 <= rate <= 1.0

    def test_end_to_end_rate_over_an_attempt_history(self, rig):
        attempts = 0
        for material in ("m1", "m2", "m3"):
            rig.acquire(rig.request(content=material))
            attempts += 1
        for material in ("m1", "m2"):  # duplicates refused
            with pytest.raises(Exception):
                rig.acquire(rig.request(content=material))
            attempts += 1
        rate = duplicate_rate(duplicate_refusals(rig.log), attempts)
        assert rate == pytest.approx(2 / 5)
