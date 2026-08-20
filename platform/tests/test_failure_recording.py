"""Contract tests for governed acquisition failure recording.

Task: T02.2.5

Architecture References:
- N-10   Failure records live OUTSIDE the object model, co-located with
         configuration (T01.1.7's FailureStore); every record identifies
         the engine, the invocation, the inputs attempted, the
         configuration in force, the time, and the nature of the failure;
         and a stage that produced nothing because it FAILED is
         distinguishable from one that found nothing.
- N-21 S 5.2  Enforcement precedes the external act: gate refusals are
         NOT attempts.
- K8     Research holds sole create authority for Evidence -- the
         failing engine is Research, identified, not guessed.
- N-4    Property-based assertions only.

T02.2.5 acceptance criteria under test:
  AC1  Failed attempts recorded                             -> IMPLEMENTED
  AC2  Absence of evidence distinguishable from absence of
       attempt                                              -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oip.acceptance import FailureRecord
from oip.acquisition import (
    AcquisitionFailure,
    AcquisitionLog,
    AcquisitionRequest,
    AcquisitionStage,
    acquire,
)
from oip.configuration import FailureStore
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.coverage import OutOfFrameRegister
from oip.duplicates import duplicate_refusals
from oip.enums import Engine, ObjectType
from oip.rights import (
    RIGHTS_AUTHORITY_ROLE,
    AcquisitionRight,
    RefusalRegister,
    RetentionRight,
    RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
MATERIAL = "Vendor changelog: bulk edits fail silently above 50 SKUs."


COVERED_TARGETS = ('src-a', 'src-b', 'src-c', 'src-u', 'src-u2', 'src-untypable')


class Rig:
    def __init__(self):
        self.registry = SourceRegistry()
        self.registry.register("src-a", "VENDOR_PUBLICATION")
        self.registry.register("src-u", "mystery-channel")
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
        self.failure_store = FailureStore()
        self.log.attach(self.failure_store)

    def request(self, source="src-a", source_type="VENDOR_PUBLICATION",
                content=MATERIAL, **ov):
        base = dict(
            source_identifier=source,
            source_type=source_type,
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

    def acquire(self, request, source="src-a", permitted=False):
        assessment = None
        if permitted:
            assessment = RightsAssessment(
                source_identifier=source,
                acquisition=AcquisitionRight.PERMITTED,
                retention=RetentionRight.RETAIN_FULL,
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


def refuse(rig, permitted=False, **request_kwargs):
    with pytest.raises(Exception):
        rig.acquire(rig.request(**request_kwargs), permitted=permitted)


# ===========================================================================
# AC1 -- failed attempts recorded (first-class, on the N-10 surface)
# ===========================================================================


class TestFailuresRecorded:
    @given(
        stage=st.sampled_from([s for s in AcquisitionStage])
    )
    def test_every_failure_carries_stage_reason_detail_and_time(
        self, stage
    ):
        """Property: whatever the stage, a constructed failure is fully
        identified -- the N-10 nature never degrades."""
        failure = AcquisitionFailure(
            source_identifier="s",
            stage=stage,
            reason="R",
            detail="d",
            failed_at=T0,
            engine_configuration_ref="cfg",
        )
        assert failure.stage is stage
        assert failure.reason.strip() and failure.detail.strip()
        assert failure.failed_at == T0

    def test_unassessed_rights_refusal_recorded_on_both_surfaces(self, rig):
        refuse(rig)
        assert len(rig.log) == 1
        assert len(rig.failure_store.all()) == 1  # the N-10 home [T01.1.7]

    def test_untypable_channel_refusal_recorded(self, rig):
        refuse(rig, source="src-u", source_type="mystery-channel")
        assert rig.log.for_source("src-u")[0].stage is (
            AcquisitionStage.UNTYPABLE_CHANNEL
        )

    def test_duplicate_refusal_recorded(self, rig):
        rig.acquire(rig.request(), permitted=True)
        refuse(rig, permitted=True)  # same material, permitted: E-V6 fires
        assert duplicate_refusals(rig.log) == 1

    def test_store_rejection_recorded(self, rig):
        from oip.enums import ObjectType as OT
        from oip.store import WriteRejectedError

        def reject(evidence, predecessor_id=None):
            raise WriteRejectedError(
                FailureRecord(
                    object_id=evidence.object_id,
                    object_type=OT.EVIDENCE,
                    failed_rules=(),
                    recorded_at=T0,
                    engine_configuration_ref="test",
                )
            )

        rig.store.write_evidence = reject  # type: ignore[method-assign]
        refuse(rig, permitted=True, content="other material")
        assert rig.log.for_source("src-a")[0].stage is (
            AcquisitionStage.STORE_REJECTED
        )

    def test_unregistered_source_recorded(self, rig):
        refuse(rig, source="src-c")  # covered by the directive, unregistered
        assert rig.log.for_source("src-c")[0].stage is (
            AcquisitionStage.UNREGISTERED_SOURCE
        )

    def test_failures_accumulate_without_loss(self, rig):
        refuse(rig, source="ghost")              # 1
        refuse(rig)                               # 2 (unassessed)
        refuse(rig, source="src-u",
               source_type="mystery-channel")     # 3
        assert len(rig.log) == 3
        assert len(rig.failure_store.all()) == 3

    def test_failures_of_independent_attempts_never_mix(self, rig):
        refuse(rig, source="ghost")
        refuse(rig)
        assert [f.source_identifier for f in rig.log] == ["ghost", "src-a"]
        assert rig.log.for_source("ghost")[0] is not rig.log.for_source(
            "src-a"
        )[0]


class TestN10Projection:
    def test_the_projection_identifies_all_six(self, rig):
        refuse(rig)
        record = rig.failure_store.all()[0]
        assert record.engine is Engine.RESEARCH            # 1 engine
        assert record.cycle_id == 7 or record.cycle_id is None  # 2 invocation (optional outside a cycle)
        assert record.input_ids == ("src-a",)              # 3 inputs
        assert record.engine_configuration_ref == (        # 4 config
            "research-acquisition-v1"
        )
        assert record.recorded_at == T0                    # 5 time
        assert "UNASSESSED" in record.nature[0]            # 6 nature

    def test_the_projection_carries_the_detail_in_its_nature(self, rig):
        """N-10's 'nature of the failure' includes WHY it failed: the
        detail travels into the projection, not just the reason token."""
        refuse(rig)
        nature = rig.failure_store.all()[0].nature[0]
        assert "UNASSESSED" in nature          # the reason token
        assert "silence is not permission" in nature  # the detail body

    def test_the_projection_is_a_failing_result_never_a_skip(self, rig):
        from oip.acceptance import RuleOutcome
        refuse(rig)
        rule = rig.failure_store.all()[0].failed_rules[0]
        assert rule.outcome is RuleOutcome.FAIL
        assert rule.failed is True

    def test_the_projection_names_the_engine_not_the_source(self, rig):
        """Orchestration's convention (T01.6.3): object_id names the
        engine because no object was produced."""
        refuse(rig, source="ghost")
        record = rig.failure_store.all()[0]
        assert record.object_id == "engine:Research"
        assert record.object_id != "source:ghost"

    def test_orchestrated_attribution_satisfies_n10_in_full(self, rig):
        failure = AcquisitionFailure(
            source_identifier="s",
            stage=AcquisitionStage.REFUSED_BY_RIGHTS,
            reason="UNASSESSED",
            detail="d",
            failed_at=T0,
            engine_configuration_ref="cfg",
        )
        record = failure.as_failure_record(cycle_id=1, invocation_index=0)
        assert record.satisfies_n10_attribution is True

    def test_unorchestrated_projection_is_surfaced_not_hidden(self, rig):
        """Outside a cycle there is no invocation identity (N-10's own
        precedent); the gap is surfaced by unattributed(), never
        suppressed."""
        refuse(rig)
        assert rig.failure_store.all()[0].satisfies_n10_attribution is False
        assert len(rig.failure_store.unattributed()) == 1

    def test_projection_never_enters_the_object_model(self, rig):
        refuse(rig)
        assert len(rig.store) == 0
        assert rig.failure_store.participates_in_lineage is False

    def test_attached_store_sees_every_stage(self, rig):
        refuse(rig, source="ghost")
        refuse(rig)
        refuse(rig, source="src-u", source_type="mystery-channel")
        stages = {f.stage for f in rig.log}
        projected_natures = " | ".join(
            r.nature[0] for r in rig.failure_store.all()
        )
        for stage in stages:
            assert stage.value in projected_natures

    def test_config_ref_comes_from_the_request_in_force(self, rig):
        request = rig.request()
        refuse(rig)
        assert rig.log.for_source("src-a")[0].engine_configuration_ref == (
            request.engine_configuration_ref
        )


# ===========================================================================
# AC2 -- absence of evidence distinguishable from absence of attempt
# ===========================================================================


class TestAttemptedDistinction:
    def test_gate_refusals_are_not_attempts(self, rig):
        """N-21 S 5.2: enforcement precedes the external act -- gate
        refusals mean NOT-ATTEMPTED (absence of attempt)."""
        refuse(rig)  # unassessed rights
        refuse(rig, source="ghost")
        refuse(rig, source="src-u", source_type="mystery-channel")
        assert all(f.attempted is False for f in rig.log)

    def test_post_material_failures_are_attempts(self, rig):
        rig.acquire(rig.request(), permitted=True)
        refuse(rig, permitted=True)  # duplicate: material was in hand
        assert rig.log.for_source("src-a")[-1].attempted is True

    def test_the_distinction_is_derived_from_the_stage(self):
        """It can never drift from the record: same data, one source."""
        for stage in AcquisitionStage:
            failure = AcquisitionFailure(
                source_identifier="s", stage=stage, reason="R", detail="d",
                failed_at=T0, engine_configuration_ref="cfg",
            )
            assert failure.attempted is (
                stage in (
                    AcquisitionStage.DUPLICATE_ACQUISITION,
                    AcquisitionStage.STORE_REJECTED,
                )
            )

    def test_absence_of_evidence_vs_absence_of_attempt_queryable(self, rig):
        """The two questions N-10 separates have distinct answers here:
        NO Evidence exists (absence of evidence) while the rights refusal
        records absence of ATTEMPT -- both visible at once."""
        refuse(rig)
        assert len(rig.store) == 0                    # no evidence came to be
        assert rig.log.for_source("src-a")[0].attempted is False

    def test_a_refusal_is_never_a_success(self, rig):
        refuse(rig)
        assert len(rig.store) == 0
        rig.acquire(rig.request(), permitted=True)  # explicit acquisition
        assert len(rig.store) == 1
        assert len(rig.log) == 1     # the refusal did not become a success
