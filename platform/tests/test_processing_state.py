"""Contract tests for processing-state tracking.

Task: T01.6.2

Architecture References:
- N-17   Scheduled batch; processing state tracked PER CYCLE; Orchestration
         "records what completed" (closes M-35, M-37, OQ-15)
- N-18   Baseline Orchestration scoped into P1; P1 must "track what completed"
- N-10   Orchestration reads state "for scheduling and idempotence"; EMPTY
         and FAILED stay distinguishable; failure never masked as completion
- N-11   Stages 1-2 concurrent, so the store must be thread-safe
- N-4    engine_configuration_ref recorded for reproducibility
- AD-04  Orchestration sequences but never judges
- AD-05  No platform-generated artifact may become Evidence
- CI-1   Infrastructure state logically isolated from Intelligence Objects
- Art.IV Ground Truth Protection
- Art.V  Infrastructure state never participates in reasoning or lineage
- IOM 2.5 / 4.6  Orchestration reads "status metadata only, never content"
- v2 4.12 "It moves work, not knowledge"; duplicate invocation is a named
         failure mode; Orchestration "does NOT own storage"
- B-12   Failure records deliberately NOT co-located with orchestration state
- M-36   Failure-handling policy OPEN -- detection only, never retry/skip
- M-01   Research trigger OPEN -- work sets externally specified
- N-12   Retention covers objects only; processing-state retention unspecified

Acceptance criteria under test:
  AC1  Idempotence supported: reprocessing detectable
  AC2  State held outside the object model
  AC3  Orchestration reads metadata only, never content

Tests assert PROPERTIES, never output equality of engine results [N-4].
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.configuration import FailureStore
from oip.enums import Engine, ObjectType
from oip.orchestration import (
    CycleBounds,
    CycleOutcome,
    CycleRecord,
    InvocationError,
    InvocationOutcome,
    InvocationRecord,
    InvocationResult,
    KnowledgeMutationError,
    Orchestrator,
    ProcessingIsolationError,
    ProcessingRecord,
    ProcessingStateError,
    ProcessingStateStore,
    WorkItem,
    WorkSet,
    WorkSetError,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
NAIVE = datetime(2026, 3, 1)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def invocation(
    n: int | str = 1,
    engine: Engine = Engine.RESEARCH,
    outcome: InvocationOutcome = InvocationOutcome.EMPTY,
    produced: tuple[str, ...] = (),
    inputs: tuple[str, ...] | None = None,
    cfg: str = "cfg-v1",
    started: datetime = T0,
    ended: datetime | None = None,
) -> InvocationRecord:
    return InvocationRecord(
        engine=engine,
        input_ids=inputs if inputs is not None else (f"src-{n}",),
        engine_configuration_ref=cfg,
        outcome=outcome,
        produced_ids=produced,
        detail="",
        started_at=started,
        ended_at=started if ended is None else ended,
    )


def item(
    n: int | str = 1,
    engine: Engine = Engine.RESEARCH,
    inputs: tuple[str, ...] | None = None,
    **kw,
) -> WorkItem:
    kwargs = {
        "engine": engine,
        "input_ids": inputs if inputs is not None else (f"src-{n}",),
        "engine_configuration_ref": "cfg-v1",
    }
    kwargs.update(kw)
    return WorkItem(**kwargs)


def cycle_record(cycle_id: int, invocations, **kw) -> CycleRecord:
    kwargs = {
        "cycle_id": cycle_id,
        "outcome": CycleOutcome.COMPLETED,
        "bounds": CycleBounds(),
        "invocations": tuple(invocations),
        "failures": (),
        "planned_items": len(tuple(invocations)),
        "started_at": T0,
        "ended_at": T0,
    }
    kwargs.update(kw)
    return CycleRecord(**kwargs)


def empty_invoker(_item: WorkItem) -> InvocationResult:
    return InvocationResult.empty()


def raising_invoker(_item: WorkItem) -> InvocationResult:
    raise RuntimeError("engine failed")


# ---------------------------------------------------------------------------
# AC1 -- idempotence supported: reprocessing detectable
# ---------------------------------------------------------------------------

class TestReprocessingDetectable:
    def test_unprocessed_input_reads_as_unprocessed(self):
        store = ProcessingStateStore()
        assert store.has_processed(Engine.RESEARCH, "src-1") is False

    def test_processed_input_is_detected(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        assert store.has_processed(Engine.RESEARCH, "src-1") is True

    def test_repeat_appends_rather_than_overwriting(self):
        """History is what makes reprocessing detectable. [AC1]"""
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        store.record(2, invocation(1))
        assert store.attempt_count(Engine.RESEARCH, "src-1") == 2
        assert len(store.attempts(Engine.RESEARCH, "src-1")) == 2
        assert len(store) == 2

    def test_would_reprocess_detects_a_repeat_work_item(self):
        store = ProcessingStateStore()
        assert store.would_reprocess(item(1)) is False
        store.record(1, invocation(1))
        assert store.would_reprocess(item(1)) is True

    def test_repeat_inputs_names_the_overlapping_inputs(self):
        """Returns which inputs overlap, not merely that some do. [AC1]"""
        store = ProcessingStateStore()
        store.record(1, invocation(inputs=("a", "b")))
        assert store.repeat_inputs(item(inputs=("b", "c"))) == ("b",)

    def test_partial_overlap_is_still_a_repeat(self):
        store = ProcessingStateStore()
        store.record(1, invocation(inputs=("a",)))
        assert store.would_reprocess(item(inputs=("a", "z"))) is True

    def test_no_overlap_is_not_a_repeat(self):
        store = ProcessingStateStore()
        store.record(1, invocation(inputs=("a", "b")))
        assert store.repeat_inputs(item(inputs=("y", "z"))) == ()

    def test_a_different_engine_on_the_same_input_is_not_a_repeat(self):
        """'By which engine' is part of the key. [T01.6.2]"""
        store = ProcessingStateStore()
        store.record(1, invocation(1, engine=Engine.RESEARCH))
        assert store.has_processed(Engine.FACT_EXTRACTION, "src-1") is False
        assert store.would_reprocess(item(1, engine=Engine.FACT_EXTRACTION)) is False

    def test_reprocessed_keys_surfaces_duplicate_invocation(self):
        """Duplicate invocation is a named failure mode. [v2 4.12]"""
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        store.record(2, invocation(1))
        store.record(1, invocation(2))
        assert store.reprocessed_keys() == ((Engine.RESEARCH, "src-1"),)

    def test_reprocessed_keys_empty_when_nothing_repeated(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        store.record(1, invocation(2))
        assert store.reprocessed_keys() == ()

    def test_a_failed_attempt_counts_as_an_attempt(self):
        """has_processed means 'an attempt is recorded'. Retry is M-36, OPEN."""
        store = ProcessingStateStore()
        store.record(1, invocation(1, outcome=InvocationOutcome.FAILED))
        assert store.has_processed(Engine.RESEARCH, "src-1") is True
        assert store.attempts(Engine.RESEARCH, "src-1")[0].failed is True

    def test_detection_across_orchestrated_cycles(self):
        store = ProcessingStateStore()
        orch = Orchestrator(invoker=empty_invoker, processing_store=store)
        work = WorkSet(items=(item(1),))
        orch.run_cycle(work)
        assert store.would_reprocess(item(1)) is True
        assert store.attempt_count(Engine.RESEARCH, "src-1") == 1
        orch.run_cycle(work)
        assert store.attempt_count(Engine.RESEARCH, "src-1") == 2


class TestDetectionTakesNoAction:
    """AD-04: Orchestration sequences but never judges. M-36 is OPEN."""

    def test_orchestrator_does_not_skip_a_detected_repeat(self):
        store = ProcessingStateStore()
        seen: list[str] = []

        def invoker(work_item: WorkItem) -> InvocationResult:
            seen.append(work_item.input_ids[0])
            return InvocationResult.empty()

        orch = Orchestrator(invoker=invoker, processing_store=store)
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert seen == ["src-1", "src-1"], "a repeat was suppressed; M-36 is open"

    def test_store_exposes_no_scheduling_or_retry_vocabulary(self):
        """Inventing retry/skip policy would close M-36 by implementation."""
        banned = ("retry", "skip", "halt", "compensate", "suppress",
                  "defer", "schedule", "should_run", "next_work")
        names = [n for n in dir(ProcessingStateStore) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)]

    def test_recording_a_repeat_is_never_refused(self):
        """The store records what happened; it does not police the plan."""
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        store.record(2, invocation(1))
        assert len(store) == 2


# ---------------------------------------------------------------------------
# AC2 -- state held outside the object model
# ---------------------------------------------------------------------------

class TestOutsideTheObjectModel:
    def test_module_imports_no_intelligence_object_type(self):
        """Structural, not conventional. [Art.V, CI-1]"""
        import oip.orchestration as module

        source = Path(module.__file__).read_text()
        for banned in (
            "evidence", "fact", "problem", "pattern", "opportunity",
            "solution", "validation", "execution", "feedback",
            "store", "graph", "lineage", "claim", "semantic", "relationships",
        ):
            assert f"from oip.{banned}" not in source
            assert f"import oip.{banned}" not in source

    def test_record_is_not_an_intelligence_object(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        for attribute in (
            "lineage_id", "derives_from", "explanation", "effective_confidence",
            "evidential_support", "assertion_confidence", "status",
            "status_reason", "evidence_reachable", "object_type", "version",
        ):
            assert not hasattr(record, attribute), attribute

    def test_record_declares_itself_not_intelligence(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        assert record.is_intelligence is False
        assert record.participates_in_lineage is False

    def test_store_declares_itself_not_intelligence(self):
        store = ProcessingStateStore()
        assert store.is_intelligence is False
        assert store.participates_in_lineage is False

    def test_record_refuses_to_act_as_lineage(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        with pytest.raises(ProcessingIsolationError):
            record.as_lineage_reference()

    def test_record_refuses_to_become_evidence(self):
        """AD-05 / Article IV: no platform artifact becomes Evidence."""
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        with pytest.raises(ProcessingIsolationError):
            record.as_evidence()

    def test_record_refuses_to_contribute_confidence(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        with pytest.raises(ProcessingIsolationError):
            record.confidence_contribution()

    def test_processing_state_is_a_surface_apart_from_failure_records(self):
        """B-12 rejected merging orchestration state with failure records."""
        processing, failures = ProcessingStateStore(), FailureStore()
        orch = Orchestrator(
            invoker=raising_invoker,
            failure_store=failures,
            processing_store=processing,
        )
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert len(failures) == 1
        assert len(processing) == 1
        assert not any(isinstance(r, ProcessingRecord) for r in failures.all())


class TestImmutableAppendOnly:
    def test_record_is_frozen(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.cycle_id = 2  # type: ignore[misc]

    def test_record_is_hashable(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
        )
        assert hash(record) == hash(record)

    def test_delete_is_refused(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        with pytest.raises(ProcessingStateError):
            store.delete("src-1")
        assert len(store) == 1

    def test_update_is_refused(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        with pytest.raises(ProcessingStateError):
            store.update("src-1", outcome=InvocationOutcome.PRODUCED)
        assert len(store) == 1

    def test_caller_mutation_after_recording_does_not_alter_the_record(self):
        store = ProcessingStateStore()
        ids = ["a", "b"]
        store.record(1, invocation(inputs=ids))
        ids.append("ghost")
        assert store.all()[0].input_ids == ("a", "b")
        assert store.has_processed(Engine.RESEARCH, "ghost") is False

    def test_returned_collections_are_copies(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        assert isinstance(store.all(), tuple)
        assert store.all() is not store._records


# ---------------------------------------------------------------------------
# AC3 -- metadata only, never content
# ---------------------------------------------------------------------------

class TestMetadataOnly:
    def test_every_field_is_metadata(self):
        """IOM 2.5: Orchestration reads status metadata only, never content."""
        field_types = {f.name: f.type for f in dataclasses.fields(ProcessingRecord)}
        assert field_types == {
            "cycle_id": "int",
            "engine": "Engine",
            "input_ids": "tuple[str, ...]",
            "engine_configuration_ref": "str",
            "outcome": "InvocationOutcome",
            "produced_ids": "tuple[str, ...]",
            "started_at": "datetime",
            "ended_at": "datetime",
        }

    def test_non_string_input_id_is_refused_as_a_knowledge_mutation(self):
        with pytest.raises(KnowledgeMutationError):
            ProcessingRecord(
                1, Engine.RESEARCH, (object(),), "cfg",
                InvocationOutcome.EMPTY, (), T0, T0,
            )

    def test_non_string_produced_id_is_refused(self):
        with pytest.raises(KnowledgeMutationError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.PRODUCED, (object(),), T0, T0,
            )

    def test_lookup_with_a_non_string_id_is_refused(self):
        store = ProcessingStateStore()
        with pytest.raises(KnowledgeMutationError):
            store.has_processed(Engine.RESEARCH, object())  # type: ignore[arg-type]

    def test_lookup_with_an_unknown_engine_is_refused(self):
        store = ProcessingStateStore()
        with pytest.raises(ProcessingStateError):
            store.has_processed("Research", "src-1")  # type: ignore[arg-type]

    def test_records_what_by_which_engine_and_when(self):
        """The three facts the backlog names. [T01.6.2]"""
        store = ProcessingStateStore()
        end = T0 + timedelta(seconds=3)
        store.record(1, invocation(1, engine=Engine.FACT_EXTRACTION, ended=end))
        record = store.all()[0]
        assert record.input_ids == ("src-1",)          # what
        assert record.engine is Engine.FACT_EXTRACTION  # by which engine
        assert record.ended_at == end                   # when

    def test_configuration_reference_is_retained(self):
        """N-4: processing must be reproducible."""
        store = ProcessingStateStore()
        store.record(1, invocation(1, cfg="cfg-research-v7"))
        assert store.all()[0].engine_configuration_ref == "cfg-research-v7"

    def test_cycle_id_is_retained(self):
        """N-17: processing state is tracked per cycle."""
        store = ProcessingStateStore()
        store.record(9, invocation(1))
        assert store.all()[0].cycle_id == 9


# ---------------------------------------------------------------------------
# N-10 -- empty, failed and produced stay distinguishable
# ---------------------------------------------------------------------------

class TestOutcomesStayDistinguishable:
    def test_empty_is_not_failed(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1, outcome=InvocationOutcome.EMPTY))
        record = store.all()[0]
        assert record.produced_nothing is True
        assert record.failed is False

    def test_failed_is_not_empty(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1, outcome=InvocationOutcome.FAILED))
        record = store.all()[0]
        assert record.failed is True
        assert record.produced_nothing is False

    def test_produced_is_neither(self):
        store = ProcessingStateStore()
        store.record(
            1, invocation(1, outcome=InvocationOutcome.PRODUCED, produced=("o1",))
        )
        record = store.all()[0]
        assert record.failed is False and record.produced_nothing is False
        assert record.produced_ids == ("o1",)

    def test_a_failing_engine_still_produces_processing_state(self):
        store = ProcessingStateStore()
        orch = Orchestrator(invoker=raising_invoker, processing_store=store)
        result = orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert result.had_failure is True
        assert len(store) == 2
        assert all(r.failed for r in store.all())

    def test_mixed_cycle_preserves_each_outcome(self):
        store = ProcessingStateStore()

        def invoker(work_item: WorkItem) -> InvocationResult:
            which = work_item.input_ids[0]
            if which == "src-1":
                return InvocationResult.produced("o1")
            if which == "src-2":
                return InvocationResult.empty()
            raise RuntimeError("boom")

        Orchestrator(invoker=invoker, processing_store=store).run_cycle(
            WorkSet(items=(item(1), item(2), item(3)))
        )
        assert {r.input_ids[0]: r.outcome for r in store.all()} == {
            "src-1": InvocationOutcome.PRODUCED,
            "src-2": InvocationOutcome.EMPTY,
            "src-3": InvocationOutcome.FAILED,
        }


class TestNotAttemptedIsNotProcessing:
    """An item the cycle never reached was not processed. [N-17, v2 4.12]"""

    def test_direct_construction_refuses_not_attempted(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.NOT_ATTEMPTED, (), T0, T0,
            )

    def test_record_refuses_not_attempted(self):
        store = ProcessingStateStore()
        with pytest.raises(ProcessingStateError):
            store.record(1, invocation(1, outcome=InvocationOutcome.NOT_ATTEMPTED))

    def test_record_cycle_excludes_not_attempted(self):
        store = ProcessingStateStore()
        store.record_cycle(cycle_record(1, [
            invocation(1),
            invocation(2, outcome=InvocationOutcome.NOT_ATTEMPTED),
        ]))
        assert len(store) == 1
        assert store.has_processed(Engine.RESEARCH, "src-2") is False

    def test_work_limit_stop_leaves_unreached_items_unprocessed(self):
        store = ProcessingStateStore()
        orch = Orchestrator(
            invoker=empty_invoker,
            bounds=CycleBounds(max_work_items=1),
            processing_store=store,
        )
        orch.run_cycle(WorkSet(items=(item(1), item(2), item(3))))
        assert len(store) == 1
        assert store.has_processed(Engine.RESEARCH, "src-2") is False

    def test_budget_stop_leaves_unreached_items_unprocessed(self):
        store = ProcessingStateStore()
        ticks = iter([T0 + timedelta(seconds=i * 100) for i in range(60)])
        orch = Orchestrator(
            invoker=empty_invoker,
            bounds=CycleBounds(wall_clock_budget_seconds=1.0),
            processing_store=store,
            clock=lambda: next(ticks),
        )
        orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(6))))
        assert all(
            r.outcome is not InvocationOutcome.NOT_ATTEMPTED for r in store.all()
        )
        assert len(store) < 6

    def test_a_cycle_of_only_unattempted_items_records_the_cycle_not_the_work(self):
        store = ProcessingStateStore()
        store.record_cycle(cycle_record(
            1, [invocation(1, outcome=InvocationOutcome.NOT_ATTEMPTED)]
        ))
        assert len(store) == 0
        assert store.has_cycle(1) is True


# ---------------------------------------------------------------------------
# Malformed input -- fail closed
# ---------------------------------------------------------------------------

class TestFailsClosed:
    @pytest.mark.parametrize("bad", [0, -1, True, "1", 1.0, None])
    def test_bad_cycle_id_refused(self, bad):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                bad, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.EMPTY, (), T0, T0,
            )

    @pytest.mark.parametrize("bad", ["Research", None, 1])
    def test_bad_engine_refused(self, bad):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, bad, ("a",), "cfg", InvocationOutcome.EMPTY, (), T0, T0
            )

    @pytest.mark.parametrize("bad", ["EMPTY", None, 1])
    def test_bad_outcome_refused(self, bad):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg", bad, (), T0, T0
            )

    def test_empty_input_ids_refused(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, (), "cfg", InvocationOutcome.EMPTY, (), T0, T0
            )

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_blank_configuration_ref_refused(self, bad):
        """N-4: without it the processing is not reproducible."""
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), bad,
                InvocationOutcome.EMPTY, (), T0, T0,
            )

    def test_blank_input_id_refused(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("  ",), "cfg",
                InvocationOutcome.EMPTY, (), T0, T0,
            )

    def test_duplicate_input_within_one_record_refused(self):
        """Duplicate invocation is a named failure mode. [v2 4.12]"""
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a", "a"), "cfg",
                InvocationOutcome.EMPTY, (), T0, T0,
            )

    def test_ended_before_started_refused(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY,
                (), T0, T0 - timedelta(seconds=1),
            )

    @pytest.mark.parametrize("bad", ["x", None, 5, object()])
    def test_record_rejects_a_non_invocation(self, bad):
        store = ProcessingStateStore()
        with pytest.raises(ProcessingStateError):
            store.record(1, bad)

    @pytest.mark.parametrize("bad", ["x", None, 5, object()])
    def test_record_cycle_rejects_a_non_cycle(self, bad):
        store = ProcessingStateStore()
        with pytest.raises(ProcessingStateError):
            store.record_cycle(bad)

    @pytest.mark.parametrize("bad", ["x", None, 5])
    def test_repeat_inputs_rejects_a_non_work_item(self, bad):
        store = ProcessingStateStore()
        with pytest.raises(ProcessingStateError):
            store.repeat_inputs(bad)


class TestTimestampCoherence:
    """Regression: mixed awareness must not escape as a raw TypeError."""

    def test_naive_start_with_aware_end_refused_not_crashed(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.EMPTY, (), NAIVE, T0,
            )

    def test_aware_start_with_naive_end_refused_not_crashed(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.EMPTY, (), T0, NAIVE,
            )

    def test_both_naive_is_accepted(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg",
            InvocationOutcome.EMPTY, (), NAIVE, NAIVE,
        )
        assert record.duration_seconds == 0.0

    @pytest.mark.parametrize("bad", ["2026-03-01", 0, None])
    def test_non_datetime_timestamp_refused(self, bad):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.EMPTY, (), bad, bad,
            )

    def test_mixed_awareness_from_an_invocation_is_refused(self):
        store = ProcessingStateStore()
        with pytest.raises(ProcessingStateError):
            store.record(1, invocation(1, started=NAIVE, ended=T0))

    def test_duration_reported_for_a_real_interval(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a",), "cfg", InvocationOutcome.EMPTY,
            (), T0, T0 + timedelta(seconds=2.5),
        )
        assert record.duration_seconds == pytest.approx(2.5)


class TestBareStringIsNotSplit:
    """Regression: a bare string was split into one id per character.

    That silently defeated reprocessing detection -- the recorded key and the
    queried key disagreed, so a genuine repeat read as new work.
    """

    def test_processing_record_refuses_a_bare_string_input(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, "abc", "cfg",
                InvocationOutcome.EMPTY, (), T0, T0,
            )

    def test_processing_record_refuses_a_bare_string_produced(self):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, ("a",), "cfg",
                InvocationOutcome.PRODUCED, "abc", T0, T0,
            )

    def test_work_item_refuses_a_bare_string_input(self):
        with pytest.raises(WorkSetError):
            WorkItem(Engine.RESEARCH, "abc", "cfg")

    def test_invocation_result_refuses_a_bare_string_produced(self):
        with pytest.raises(InvocationError):
            InvocationResult(InvocationOutcome.PRODUCED, "abc")

    def test_detection_survives_the_defect_scenario(self):
        """The end-to-end consequence: a repeat is detected, not missed."""
        store = ProcessingStateStore()
        store.record(1, invocation(inputs=("abc",)))
        assert store.repeat_inputs(WorkItem(Engine.RESEARCH, ("abc",), "cfg")) == (
            "abc",
        )

    def test_list_input_ids_coerced_to_tuple(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ["a", "b"], "cfg",
            InvocationOutcome.EMPTY, (), T0, T0,
        )
        assert isinstance(record.input_ids, tuple)
        assert record.input_ids == ("a", "b")

    def test_work_item_list_coerced_to_tuple(self):
        assert isinstance(WorkItem(Engine.RESEARCH, ["a"], "cfg").input_ids, tuple)

    def test_generator_input_ids_not_exhausted(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, (x for x in ("a", "b")), "cfg",
            InvocationOutcome.EMPTY, (), T0, T0,
        )
        assert record.input_ids == ("a", "b")

    @pytest.mark.parametrize("bad", [5, None, object()])
    def test_non_iterable_input_ids_refused(self, bad):
        with pytest.raises(ProcessingStateError):
            ProcessingRecord(
                1, Engine.RESEARCH, bad, "cfg",
                InvocationOutcome.EMPTY, (), T0, T0,
            )


# ---------------------------------------------------------------------------
# Cycle commit integrity
# ---------------------------------------------------------------------------

class TestCycleCommit:
    def test_records_every_attempted_invocation(self):
        store = ProcessingStateStore()
        store.record_cycle(cycle_record(1, [invocation(n) for n in range(4)]))
        assert len(store) == 4
        assert store.for_cycle(1) == store.all()

    def test_committing_the_same_cycle_twice_is_refused(self):
        store = ProcessingStateStore()
        cycle = cycle_record(1, [invocation(1)])
        store.record_cycle(cycle)
        with pytest.raises(ProcessingStateError):
            store.record_cycle(cycle)
        assert len(store) == 1

    def test_a_rejected_commit_does_not_half_commit(self):
        """Atomicity: a malformed member aborts the whole cycle."""
        store = ProcessingStateStore()
        incoherent = InvocationRecord(
            Engine.RESEARCH, ("b",), "cfg", InvocationOutcome.EMPTY,
            (), "", T0, T0 - timedelta(seconds=5),
        )
        with pytest.raises(ProcessingStateError):
            store.record_cycle(cycle_record(1, [invocation(1), incoherent]))
        assert len(store) == 0
        assert store.has_processed(Engine.RESEARCH, "src-1") is False

    def test_colliding_cycle_ids_from_two_orchestrators_are_refused(self):
        store = ProcessingStateStore()
        first = Orchestrator(invoker=empty_invoker, processing_store=store)
        second = Orchestrator(invoker=empty_invoker, processing_store=store)
        first.run_cycle(WorkSet(items=(item(1),)))
        with pytest.raises(ProcessingStateError):
            second.run_cycle(WorkSet(items=(item(2),)))
        assert len(store) == 1

    def test_the_cycle_remains_in_history_when_the_commit_is_refused(self):
        """A store failure must not erase the record of a cycle that ran."""

        class Hostile(ProcessingStateStore):
            def record_cycle(self, cycle):
                raise ProcessingStateError("store unavailable")

        orch = Orchestrator(invoker=empty_invoker, processing_store=Hostile())
        with pytest.raises(ProcessingStateError):
            orch.run_cycle(WorkSet(items=(item(1),)))
        assert orch.cycle_count == 1
        assert orch.cycle(1) is not None

    def test_commit_occurs_after_the_cycle_enters_history(self):
        observed: list[int] = []

        class Watcher(ProcessingStateStore):
            def record_cycle(self, cycle):
                observed.append(orch.cycle_count)
                return super().record_cycle(cycle)

        orch = Orchestrator(invoker=empty_invoker, processing_store=Watcher())
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert observed == [1]

    def test_an_empty_cycle_registers_itself_but_no_work(self):
        store = ProcessingStateStore()
        Orchestrator(invoker=empty_invoker, processing_store=store).run_cycle(
            WorkSet(items=())
        )
        assert len(store) == 0
        assert store.has_cycle(1) is True

    def test_sequential_cycles_commit_in_order(self):
        store = ProcessingStateStore()
        orch = Orchestrator(invoker=empty_invoker, processing_store=store)
        for n in range(5):
            orch.run_cycle(WorkSet(items=(item(n),)))
        assert [r.cycle_id for r in store.all()] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

class TestQueries:
    def test_attempts_are_returned_in_recording_order(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1, started=T0 + timedelta(hours=5)))
        store.record(2, invocation(1, started=T0))
        assert [r.cycle_id for r in store.attempts(Engine.RESEARCH, "src-1")] == [1, 2]

    def test_last_processed_at_reports_the_latest_recorded(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1, started=T0, ended=T0))
        later = T0 + timedelta(hours=1)
        store.record(2, invocation(1, started=later, ended=later))
        assert store.last_processed_at(Engine.RESEARCH, "src-1") == later

    def test_engines_that_processed_lists_each_engine_once(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1, engine=Engine.RESEARCH))
        store.record(2, invocation(1, engine=Engine.RESEARCH))
        store.record(1, invocation(1, engine=Engine.FACT_EXTRACTION))
        store.record(1, invocation(2, engine=Engine.VALIDATION))
        assert set(store.engines_that_processed("src-1")) == {
            Engine.RESEARCH,
            Engine.FACT_EXTRACTION,
        }

    def test_for_engine_filters(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1, engine=Engine.RESEARCH))
        store.record(1, invocation(2, engine=Engine.FEEDBACK))
        assert len(store.for_engine(Engine.FEEDBACK)) == 1

    def test_for_cycle_groups_and_preserves_order(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        store.record(2, invocation(2))
        store.record(1, invocation(3))
        assert [r.input_ids[0] for r in store.for_cycle(1)] == ["src-1", "src-3"]

    def test_cycles_recorded_is_sorted(self):
        store = ProcessingStateStore()
        for cid in (5, 2, 9):
            store.record(cid, invocation(cid))
        assert store.cycles_recorded() == (2, 5, 9)

    def test_keys_enumerates_engine_input_pairs(self):
        record = ProcessingRecord(
            1, Engine.RESEARCH, ("a", "b"), "cfg",
            InvocationOutcome.EMPTY, (), T0, T0,
        )
        assert record.keys() == (
            (Engine.RESEARCH, "a"),
            (Engine.RESEARCH, "b"),
        )

    def test_iteration_yields_records(self):
        store = ProcessingStateStore()
        store.record(1, invocation(1))
        assert [r.input_ids for r in store] == [("src-1",)]

    def test_unknown_lookups_answer_emptily_without_raising(self):
        store = ProcessingStateStore()
        assert store.has_processed(Engine.RESEARCH, "nope") is False
        assert store.attempt_count(Engine.RESEARCH, "nope") == 0
        assert store.attempts(Engine.RESEARCH, "nope") == ()
        assert store.last_processed_at(Engine.RESEARCH, "nope") is None
        assert store.engines_that_processed("nope") == ()
        assert store.for_cycle(99) == ()
        assert store.for_engine(Engine.FEEDBACK) == ()
        assert store.has_cycle(99) is False
        assert store.reprocessed_keys() == ()
        assert len(store) == 0


# ---------------------------------------------------------------------------
# Backward compatibility  [T01.6.1 public API unchanged]
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_orchestrator_without_a_processing_store_is_unchanged(self):
        orch = Orchestrator(invoker=empty_invoker)
        assert orch.processing_store is None
        assert orch.run_cycle(WorkSet(items=(item(1),))).attempted_count == 1

    def test_clock_remains_reachable_by_keyword(self):
        orch = Orchestrator(invoker=empty_invoker, clock=lambda: T0)
        assert orch.run_cycle(WorkSet(items=(item(1),))).started_at == T0

    def test_failure_store_still_works_alone(self):
        failures = FailureStore()
        Orchestrator(invoker=raising_invoker, failure_store=failures).run_cycle(
            WorkSet(items=(item(1),))
        )
        assert len(failures) == 1

    def test_orchestration_still_produces_no_intelligence_objects(self):
        orch = Orchestrator(invoker=empty_invoker,
                            processing_store=ProcessingStateStore())
        assert orch.produces_intelligence_objects is False

    def test_work_item_tuple_inputs_behave_as_before(self):
        assert WorkItem(Engine.RESEARCH, ("a", "b"), "cfg").input_ids == ("a", "b")

    def test_invocation_result_helpers_behave_as_before(self):
        assert InvocationResult.produced("o1").produced_ids == ("o1",)
        assert InvocationResult.empty().produced_ids == ()


# ---------------------------------------------------------------------------
# Concurrency  [N-11 permits concurrent stages 1-2]
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_record_loses_nothing(self):
        store = ProcessingStateStore()

        def writer(worker: int) -> None:
            for n in range(100):
                store.record(1, invocation(f"{worker}-{n}"))

        threads = [threading.Thread(target=writer, args=(w,)) for w in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(store) == 800
        assert all(
            store.attempt_count(Engine.RESEARCH, f"src-{w}-{n}") == 1
            for w in range(8)
            for n in range(100)
        )

    def test_index_stays_consistent_with_records(self):
        store = ProcessingStateStore()

        def writer(worker: int) -> None:
            for n in range(80):
                store.record(1, invocation(inputs=(f"x{worker}-{n}", f"y{worker}-{n}")))

        threads = [threading.Thread(target=writer, args=(w,)) for w in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert sum(len(v) for v in store._by_key.values()) == 2 * len(store)
        assert sum(len(v) for v in store._by_cycle.values()) == len(store)

    def test_concurrent_commit_of_the_same_cycle_admits_exactly_one(self):
        store = ProcessingStateStore()
        cycle = cycle_record(1, [invocation(1)])
        accepted, refused = [], []
        barrier = threading.Barrier(8)

        def worker() -> None:
            barrier.wait()
            try:
                store.record_cycle(cycle)
                accepted.append(1)
            except ProcessingStateError:
                refused.append(1)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(accepted) == 1
        assert len(refused) == 7
        assert len(store) == 1

    def test_concurrent_commits_of_distinct_cycles_all_land(self):
        store = ProcessingStateStore()
        errors: list[Exception] = []

        def worker(cid: int) -> None:
            try:
                store.record_cycle(cycle_record(
                    cid, [invocation(f"{cid}-{k}") for k in range(10)]
                ))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(c,)) for c in range(1, 11)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert len(store) == 100
        assert len(store.cycles_recorded()) == 10

    def test_reading_the_store_from_inside_an_invoker_does_not_deadlock(self):
        store = ProcessingStateStore()
        observed: list[bool] = []

        def invoker(work_item: WorkItem) -> InvocationResult:
            observed.append(store.would_reprocess(work_item))
            return InvocationResult.empty()

        orch = Orchestrator(invoker=invoker, processing_store=store)
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert observed == [False, True]

    def test_reads_remain_coherent_during_concurrent_writes(self):
        store = ProcessingStateStore()
        stop = threading.Event()
        errors: list[Exception] = []

        def reader() -> None:
            while not stop.is_set():
                try:
                    assert len(store.all()) >= 0
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(exc)
                    return

        thread = threading.Thread(target=reader)
        thread.start()
        for n in range(300):
            store.record(1, invocation(n))
        stop.set()
        thread.join()
        assert not errors
        assert len(store) == 300


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality]
# ---------------------------------------------------------------------------

ids = st.text(
    alphabet=st.characters(min_codepoint=33, max_codepoint=126), min_size=1, max_size=12
)
engines = st.sampled_from(list(Engine))
outcomes = st.sampled_from([
    InvocationOutcome.PRODUCED,
    InvocationOutcome.EMPTY,
    InvocationOutcome.FAILED,
])


@settings(max_examples=200, deadline=None)
@given(engine=engines, input_id=ids)
def test_property_recording_then_querying_always_detects(engine, input_id):
    store = ProcessingStateStore()
    assert store.has_processed(engine, input_id) is False
    store.record(1, invocation(inputs=(input_id,), engine=engine))
    assert store.has_processed(engine, input_id) is True


@settings(max_examples=200, deadline=None)
@given(engine=engines, input_id=ids, repeats=st.integers(min_value=1, max_value=8))
def test_property_attempt_count_equals_recordings(engine, input_id, repeats):
    store = ProcessingStateStore()
    for n in range(repeats):
        store.record(n + 1, invocation(inputs=(input_id,), engine=engine))
    assert store.attempt_count(engine, input_id) == repeats
    assert (store.attempt_count(engine, input_id) > 1) == (
        (engine, input_id) in store.reprocessed_keys()
    )


@settings(max_examples=200, deadline=None)
@given(
    input_ids=st.lists(ids, min_size=1, max_size=6, unique=True),
    engine=engines,
)
def test_property_every_input_becomes_individually_detectable(input_ids, engine):
    store = ProcessingStateStore()
    store.record(1, invocation(inputs=tuple(input_ids), engine=engine))
    assert all(store.has_processed(engine, i) for i in input_ids)
    work = WorkItem(engine, tuple(input_ids), "cfg")
    assert set(store.repeat_inputs(work)) == set(input_ids)


@settings(max_examples=200, deadline=None)
@given(
    recorded=st.lists(ids, min_size=1, max_size=5, unique=True),
    queried=st.lists(ids, min_size=1, max_size=5, unique=True),
)
def test_property_repeat_inputs_is_exactly_the_intersection(recorded, queried):
    store = ProcessingStateStore()
    store.record(1, invocation(inputs=tuple(recorded)))
    work = WorkItem(Engine.RESEARCH, tuple(queried), "cfg")
    assert set(store.repeat_inputs(work)) == set(recorded) & set(queried)
    assert store.would_reprocess(work) == bool(set(recorded) & set(queried))


@settings(max_examples=200, deadline=None)
@given(outcome=outcomes)
def test_property_outcome_is_never_collapsed(outcome):
    """N-10: empty, failed and produced remain distinguishable."""
    store = ProcessingStateStore()
    produced = ("o1",) if outcome is InvocationOutcome.PRODUCED else ()
    store.record(1, invocation(outcome=outcome, produced=produced))
    record = store.all()[0]
    assert record.outcome is outcome
    assert record.failed == (outcome is InvocationOutcome.FAILED)
    assert record.produced_nothing == (outcome is InvocationOutcome.EMPTY)


@settings(max_examples=100, deadline=None)
@given(
    engine_a=engines,
    engine_b=engines,
    input_id=ids,
)
def test_property_detection_is_keyed_on_engine_and_input(engine_a, engine_b, input_id):
    store = ProcessingStateStore()
    store.record(1, invocation(inputs=(input_id,), engine=engine_a))
    assert store.has_processed(engine_b, input_id) is (engine_b is engine_a)


@settings(max_examples=100, deadline=None)
@given(count=st.integers(min_value=0, max_value=25))
def test_property_store_length_equals_attempted_invocations(count):
    """The store never invents or loses a record. [N-10]"""
    store = ProcessingStateStore()
    invocations = [invocation(n) for n in range(count)]
    invocations.append(invocation("x", outcome=InvocationOutcome.NOT_ATTEMPTED))
    store.record_cycle(cycle_record(1, invocations))
    assert len(store) == count


@settings(max_examples=100, deadline=None)
@given(count=st.integers(min_value=1, max_value=20))
def test_property_a_bounded_cycle_never_records_unreached_work(count):
    """Whatever the bound, only attempted work becomes processing state."""
    store = ProcessingStateStore()
    orch = Orchestrator(
        invoker=empty_invoker,
        bounds=CycleBounds(max_work_items=1),
        processing_store=store,
    )
    orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(count))))
    assert len(store) == 1
    assert all(
        r.outcome is not InvocationOutcome.NOT_ATTEMPTED
        for r in store.for_cycle(1)
    )
    assert store.has_processed(Engine.RESEARCH, "src-0") is True
    for n in range(1, count):
        assert store.has_processed(Engine.RESEARCH, f"src-{n}") is False


@settings(max_examples=100, deadline=None)
@given(
    input_id=ids,
    engine=engines,
)
def test_property_isolation_never_weakens(input_id, engine):
    """No recorded state ever becomes intelligence. [CI-1, Art.V, AD-05]"""
    store = ProcessingStateStore()
    store.record(1, invocation(inputs=(input_id,), engine=engine))
    record = store.all()[0]
    assert record.is_intelligence is False
    assert record.participates_in_lineage is False
    assert store.is_intelligence is False
    assert store.participates_in_lineage is False
    for accessor in (
        record.as_lineage_reference,
        record.as_evidence,
        record.confidence_contribution,
    ):
        with pytest.raises(ProcessingIsolationError):
            accessor()
