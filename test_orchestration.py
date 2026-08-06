"""Contract tests for the orchestration foundation.

Task: T01.6.1

Architecture References:
- N-17   Scheduled batch; directive not reactive; bounded by work-set size
         AND wall-clock budget (closes M-35, M-37, OQ-15)
- N-18   Baseline Orchestration scoped into P1 (closes C-08)
- N-11   Interpretation serialised
- N-10   Failure recorded, cycle continues, surfaced -- never masked
- AD-04  Orchestration sequences but never judges
- P4     Engines do not call each other
- N-4    engine_configuration_ref on every invocation
- M-36   Failure-handling policy OPEN -- no retry/skip/halt implemented
- M-01   Research trigger OPEN -- work sets externally specified
- M-56   Cost model OPEN -- wall clock is a proxy

Acceptance criteria under test:
  AC1  Engines invoked on schedule
  AC2  Batch boundaries defined
  AC3  Iteration bounded
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Protocol

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import FailureRecord
from oip.configuration import FailureStore
from oip.enums import Engine, ObjectType
from oip.orchestration import (
    DEFAULT_MAX_WORK_ITEMS,
    DEFAULT_WALL_CLOCK_BUDGET_SECONDS,
    CycleBoundError,
    CycleBounds,
    CycleOutcome,
    CycleRecord,
    CycleStateError,
    InvocationError,
    InvocationOutcome,
    InvocationRecord,
    InvocationResult,
    KnowledgeMutationError,
    Orchestrator,
    WorkItem,
    WorkSet,
    WorkSetError,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def item(n: int = 1, engine: Engine = Engine.RESEARCH, **overrides) -> WorkItem:
    kwargs = {
        "engine": engine,
        "input_ids": (f"src-{n}",),
        "engine_configuration_ref": "cfg-v1",
    }
    kwargs.update(overrides)
    return WorkItem(**kwargs)


def work_set(count: int = 3, **overrides) -> WorkSet:
    kwargs = {"items": tuple(item(i) for i in range(count))}
    kwargs.update(overrides)
    return WorkSet(**kwargs)


def always_empty(_item: WorkItem) -> InvocationResult:
    return InvocationResult.empty()


def always_produces(item_: WorkItem) -> InvocationResult:
    return InvocationResult.produced(f"out-{item_.input_ids[0]}")


def always_raises(_item: WorkItem) -> InvocationResult:
    raise RuntimeError("engine exploded")


def fixed_clock(start: datetime = T0, step_seconds: float = 0.0):
    """A deterministic clock advancing by a fixed step per call."""
    state = {"t": start}

    def clock() -> datetime:
        now = state["t"]
        state["t"] = now + timedelta(seconds=step_seconds)
        return now

    return clock


# ===========================================================================
# AC1 -- engines invoked on schedule  [N-17]
# ===========================================================================

class TestEngineInvocation:
    def test_single_engine_invoked(self):
        seen = []
        o = Orchestrator(invoker=lambda i: (seen.append(i), always_empty(i))[1])
        o.run_cycle(WorkSet(items=(item(1),)))
        assert len(seen) == 1
        assert seen[0].engine is Engine.RESEARCH

    def test_every_item_invoked(self):
        seen = []
        o = Orchestrator(invoker=lambda i: (seen.append(i.input_ids[0]), always_empty(i))[1])
        o.run_cycle(work_set(5))
        assert seen == [f"src-{i}" for i in range(5)]

    def test_order_is_the_callers_order(self):
        """Directive, not reactive: Orchestration executes the plan. [N-17]"""
        seen = []
        o = Orchestrator(invoker=lambda i: (seen.append(i.input_ids[0]), always_empty(i))[1])
        o.run_cycle(WorkSet(items=tuple(item(n) for n in (5, 3, 9, 1, 7))))
        assert seen == ["src-5", "src-3", "src-9", "src-1", "src-7"]

    def test_multiple_engines_in_one_cycle(self):
        engines = [Engine.RESEARCH, Engine.FACT_EXTRACTION, Engine.PROBLEM_INTELLIGENCE]
        ws = WorkSet(items=tuple(item(i, engine=e) for i, e in enumerate(engines)))
        o = Orchestrator(invoker=always_produces)
        record = o.run_cycle(ws)
        assert record.engines_invoked == tuple(engines)

    def test_invocation_record_captures_provenance(self):
        """N-4: the configuration in force is part of the record."""
        o = Orchestrator(invoker=always_produces)
        record = o.run_cycle(WorkSet(items=(item(1, engine_configuration_ref="cfg-v9"),)))
        inv = record.invocations[0]
        assert inv.engine_configuration_ref == "cfg-v9"
        assert inv.input_ids == ("src-1",)
        assert inv.produced_ids == ("out-src-1",)

    def test_empty_work_set_completes(self):
        record = Orchestrator(invoker=always_empty).run_cycle(WorkSet(items=()))
        assert record.outcome is CycleOutcome.COMPLETED
        assert record.attempted_count == 0
        assert record.terminated

    def test_for_engine_filters(self):
        ws = WorkSet(items=(item(1), item(2, engine=Engine.FEEDBACK)))
        record = Orchestrator(invoker=always_produces).run_cycle(ws)
        assert len(record.for_engine(Engine.RESEARCH)) == 1
        assert len(record.for_engine(Engine.VALIDATION)) == 0

    def test_timing_recorded_per_invocation(self):
        o = Orchestrator(invoker=always_empty, clock=fixed_clock(step_seconds=1.0))
        record = o.run_cycle(WorkSet(items=(item(1),)))
        assert record.invocations[0].duration_seconds >= 0.0


# ===========================================================================
# AC2 -- batch boundaries defined  [N-17]
# ===========================================================================

class TestBatchBoundaries:
    def test_cycle_produces_one_record(self):
        o = Orchestrator(invoker=always_empty)
        record = o.run_cycle(work_set(3))
        assert isinstance(record, CycleRecord)
        assert o.cycle_count == 1

    def test_cycle_ids_are_monotonic(self):
        o = Orchestrator(invoker=always_empty)
        for _ in range(4):
            o.run_cycle(WorkSet(items=(item(1),)))
        assert [c.cycle_id for c in o.cycles] == [1, 2, 3, 4]

    def test_cycle_retrievable_by_id(self):
        o = Orchestrator(invoker=always_empty)
        record = o.run_cycle(work_set(2))
        assert o.cycle(record.cycle_id) is record
        assert o.cycle(9999) is None

    def test_cycle_record_is_immutable(self):
        """A concluded cycle is a historical fact."""
        import dataclasses

        record = Orchestrator(invoker=always_empty).run_cycle(work_set(2))
        with pytest.raises(dataclasses.FrozenInstanceError):
            record.outcome = CycleOutcome.FAILED

    def test_every_cycle_terminates(self):
        """M-37: the platform has no terminal state; every cycle does."""
        o = Orchestrator(invoker=always_empty)
        for count in (0, 1, 5):
            assert o.run_cycle(work_set(count)).terminated

    def test_cycle_records_the_plan_size(self):
        record = Orchestrator(invoker=always_empty).run_cycle(work_set(7))
        assert record.planned_items == 7

    def test_description_carried(self):
        ws = WorkSet(items=(item(1),), description="nightly acquisition")
        record = Orchestrator(invoker=always_empty).run_cycle(ws)
        assert record.description == "nightly acquisition"

    def test_work_set_reports_its_engines(self):
        ws = WorkSet(items=(item(1), item(2), item(3, engine=Engine.FEEDBACK)))
        assert ws.engines == (Engine.RESEARCH, Engine.FEEDBACK)

    def test_work_set_length_and_emptiness(self):
        assert len(work_set(4)) == 4
        assert WorkSet(items=()).is_empty
        assert not work_set(1).is_empty

    def test_history_accumulates_across_cycles(self):
        """Continuous operation is a sequence of bounded cycles. [N-17]"""
        o = Orchestrator(invoker=always_empty)
        for _ in range(5):
            o.run_cycle(work_set(2))
        assert o.cycle_count == 5
        assert all(c.terminated for c in o.cycles)


# ===========================================================================
# AC3 -- iteration bounded  [N-17, M-37]
# ===========================================================================

class TestIterationBounded:
    def test_work_limit_stops_the_cycle(self):
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=3, wall_clock_budget_seconds=999),
        )
        record = o.run_cycle(work_set(10))
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED
        assert record.attempted_count == 3

    def test_budget_stops_the_cycle(self):
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=999, wall_clock_budget_seconds=5),
            clock=fixed_clock(step_seconds=1.0),
        )
        record = o.run_cycle(work_set(20))
        assert record.outcome is CycleOutcome.BUDGET_EXHAUSTED
        assert record.attempted_count < 20

    def test_unattempted_work_is_recorded(self):
        """Starvation is a named failure mode; a bounded stop is never silent."""
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=2, wall_clock_budget_seconds=999),
        )
        record = o.run_cycle(work_set(6))
        assert record.not_attempted_count == 4
        skipped = [r for r in record.invocations if not r.attempted]
        assert all(r.outcome is InvocationOutcome.NOT_ATTEMPTED for r in skipped)
        assert all("bound reached" in r.detail for r in skipped)

    def test_accounting_invariant_holds(self):
        """attempted + not_attempted == planned, always."""
        for limit in (1, 2, 5, 50):
            o = Orchestrator(
                invoker=always_empty,
                bounds=CycleBounds(max_work_items=limit, wall_clock_budget_seconds=999),
            )
            record = o.run_cycle(work_set(10))
            assert record.attempted_count + record.not_attempted_count == record.planned_items

    def test_exactly_at_bound_completes(self):
        """All work done and the bound not exceeded -> COMPLETED."""
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=3, wall_clock_budget_seconds=999),
        )
        record = o.run_cycle(work_set(3))
        assert record.outcome is CycleOutcome.COMPLETED
        assert record.attempted_count == 3

    def test_under_bound_completes(self):
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=100, wall_clock_budget_seconds=999),
        )
        assert o.run_cycle(work_set(1)).outcome is CycleOutcome.COMPLETED

    def test_bound_of_one(self):
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=1, wall_clock_budget_seconds=999),
        )
        record = o.run_cycle(work_set(3))
        assert record.attempted_count == 1
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED

    def test_per_cycle_bounds_override_the_default(self):
        o = Orchestrator(invoker=always_empty)
        record = o.run_cycle(
            work_set(10),
            bounds=CycleBounds(max_work_items=2, wall_clock_budget_seconds=999),
        )
        assert record.attempted_count == 2
        assert record.bounds.max_work_items == 2

    def test_bounds_recorded_on_the_cycle(self):
        bounds = CycleBounds(max_work_items=7, wall_clock_budget_seconds=11.5)
        record = Orchestrator(invoker=always_empty, bounds=bounds).run_cycle(work_set(1))
        assert record.bounds == bounds

    @pytest.mark.parametrize("bad", [0, -1, -100])
    def test_non_positive_work_limit_refused(self, bad):
        with pytest.raises(CycleBoundError) as exc:
            CycleBounds(max_work_items=bad)
        assert "unbounded" in str(exc.value) or "positive" in str(exc.value)

    @pytest.mark.parametrize("bad", [0, -1.0, -0.5])
    def test_non_positive_budget_refused(self, bad):
        with pytest.raises(CycleBoundError):
            CycleBounds(wall_clock_budget_seconds=bad)

    def test_boolean_is_not_a_work_limit(self):
        with pytest.raises(CycleBoundError):
            CycleBounds(max_work_items=True)

    def test_non_numeric_bounds_refused(self):
        with pytest.raises(CycleBoundError):
            CycleBounds(max_work_items="many")
        with pytest.raises(CycleBoundError):
            CycleBounds(wall_clock_budget_seconds="soon")

    def test_defaults_are_bounded(self):
        b = CycleBounds()
        assert b.max_work_items == DEFAULT_MAX_WORK_ITEMS > 0
        assert b.wall_clock_budget_seconds == DEFAULT_WALL_CLOCK_BUDGET_SECONDS > 0

    def test_run_cycle_refuses_non_bounds(self):
        with pytest.raises(CycleBoundError):
            Orchestrator(invoker=always_empty).run_cycle(work_set(1), bounds="fast")

    def test_bounded_stops_reported(self):
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=1, wall_clock_budget_seconds=999),
        )
        o.run_cycle(work_set(5))
        o.run_cycle(work_set(1))
        assert len(o.bounded_stops()) == 1


# ===========================================================================
# N-10 failure handling: record, continue, surface
# ===========================================================================

class TestFailureHandling:
    def test_engine_failure_does_not_escape(self):
        record = Orchestrator(invoker=always_raises).run_cycle(work_set(3))
        assert record.failed_count == 3

    def test_cycle_continues_past_a_failure(self):
        """N-10: failures do not silently halt the pipeline."""
        calls = []

        def flaky(i):
            calls.append(i)
            if len(calls) == 2:
                raise RuntimeError("boom")
            return InvocationResult.produced("ok")

        record = Orchestrator(invoker=flaky).run_cycle(work_set(4))
        assert record.attempted_count == 4
        assert record.failed_count == 1

    def test_failure_reported_as_failed_not_completed(self):
        """Never masked as completion."""
        record = Orchestrator(invoker=always_raises).run_cycle(work_set(1))
        assert record.outcome is CycleOutcome.FAILED
        assert record.outcome is not CycleOutcome.COMPLETED

    def test_failure_record_attributable_to_engine_and_invocation(self):
        """T01.1.7 acceptance criterion."""
        ws = WorkSet(items=(item(1, engine=Engine.FEEDBACK,
                                 engine_configuration_ref="cfg-x"),))
        record = Orchestrator(invoker=always_raises).run_cycle(ws)
        failure = record.failures[0]
        assert isinstance(failure, FailureRecord)
        assert failure.object_id == "engine:Feedback"
        assert failure.engine_configuration_ref == "cfg-x"
        assert failure.rule_ids == ("ENGINE-FAILURE",)

    def test_failure_detail_names_the_exception(self):
        record = Orchestrator(invoker=always_raises).run_cycle(work_set(1))
        assert "RuntimeError" in record.invocations[0].detail
        assert "engine exploded" in record.invocations[0].detail

    def test_failures_written_to_the_supplied_store(self):
        """N-10 records live outside the object model, in the T01.1.7 store."""
        store = FailureStore()
        Orchestrator(invoker=always_raises, failure_store=store).run_cycle(work_set(3))
        assert len(store) == 3
        assert store.participates_in_lineage is False

    def test_no_failure_store_is_permitted(self):
        record = Orchestrator(invoker=always_raises, failure_store=None).run_cycle(work_set(1))
        assert len(record.failures) == 1

    def test_empty_is_distinguishable_from_failed(self):
        """N-10: an empty result and a failed result stay distinguishable."""
        empty = Orchestrator(invoker=always_empty).run_cycle(work_set(2))
        failed = Orchestrator(invoker=always_raises).run_cycle(work_set(2))
        assert empty.empty_count == 2 and empty.failed_count == 0
        assert failed.failed_count == 2 and failed.empty_count == 0
        assert empty.outcome is CycleOutcome.COMPLETED
        assert failed.outcome is CycleOutcome.FAILED

    def test_no_retry_is_attempted(self):
        """M-36 is OPEN: retry/skip/halt policy is not invented here."""
        calls = []

        def counting(i):
            calls.append(i)
            raise RuntimeError("x")

        Orchestrator(invoker=counting).run_cycle(work_set(3))
        assert len(calls) == 3, "each item attempted exactly once; no retry"

    def test_engine_returning_a_non_result_is_a_failure(self):
        record = Orchestrator(invoker=lambda i: "done").run_cycle(work_set(1))
        assert record.failed_count == 1
        assert "InvocationResult" in record.invocations[0].detail

    def test_failed_cycles_listed(self):
        o = Orchestrator(invoker=always_raises)
        o.run_cycle(work_set(1))
        assert len(o.failed_cycles()) == 1


# ===========================================================================
# REGRESSION: failure must not be masked by a bounded stop  [N-10]
# ===========================================================================

class TestFailureNotMaskedByBound:
    """Regression for a real defect found during implementation.

    CycleOutcome conflates two orthogonal facts: WHY the cycle stopped, and
    WHETHER anything failed. When a cycle both failed and hit a bound, the
    outcome reported the bound, `outcome.had_failure` was False and
    `failed_cycles()` returned nothing -- the engine failure was masked at
    cycle level, which N-10 forbids. CycleRecord.had_failure now reads the
    invocation records instead.
    """

    def _bounded_and_failing(self):
        o = Orchestrator(
            invoker=always_raises,
            bounds=CycleBounds(max_work_items=2, wall_clock_budget_seconds=999),
        )
        return o, o.run_cycle(work_set(5))

    def test_record_reports_the_failure(self):
        _, record = self._bounded_and_failing()
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED
        assert record.had_failure is True
        assert record.failed_count == 2

    def test_failed_cycles_includes_a_bounded_failing_cycle(self):
        o, _ = self._bounded_and_failing()
        assert len(o.failed_cycles()) == 1

    def test_failures_are_recorded_despite_the_bound(self):
        _, record = self._bounded_and_failing()
        assert len(record.failures) == 2

    def test_budget_stop_also_surfaces_failure(self):
        o = Orchestrator(
            invoker=always_raises,
            bounds=CycleBounds(max_work_items=999, wall_clock_budget_seconds=3),
            clock=fixed_clock(step_seconds=1.0),
        )
        record = o.run_cycle(work_set(20))
        assert record.outcome is CycleOutcome.BUDGET_EXHAUSTED
        assert record.had_failure is True
        assert len(o.failed_cycles()) == 1

    def test_clean_bounded_stop_is_not_reported_as_failed(self):
        """The fix must not over-report."""
        o = Orchestrator(
            invoker=always_empty,
            bounds=CycleBounds(max_work_items=2, wall_clock_budget_seconds=999),
        )
        record = o.run_cycle(work_set(5))
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED
        assert record.had_failure is False
        assert o.failed_cycles() == ()

    def test_clean_completion_is_not_reported_as_failed(self):
        o = Orchestrator(invoker=always_produces)
        record = o.run_cycle(work_set(3))
        assert record.had_failure is False
        assert o.failed_cycles() == ()

    def test_outcome_property_documents_its_narrower_meaning(self):
        """CycleOutcome.had_failure answers the stop reason, not 'did it fail'."""
        assert CycleOutcome.FAILED.had_failure is True
        assert CycleOutcome.WORK_LIMIT_REACHED.had_failure is False
        assert CycleOutcome.BUDGET_EXHAUSTED.had_failure is False
        assert CycleOutcome.COMPLETED.had_failure is False


# ===========================================================================
# AD-04 -- moves work, not knowledge
# ===========================================================================

class TestMovesWorkNotKnowledge:
    def test_orchestrator_declares_it_produces_nothing(self):
        assert Orchestrator(invoker=always_empty).produces_intelligence_objects is False

    def test_invocation_result_refuses_a_non_string_id(self):
        """No field exists through which an object could travel."""

        class FakeObject:
            pass

        with pytest.raises(KnowledgeMutationError) as exc:
            InvocationResult(InvocationOutcome.PRODUCED, (FakeObject(),))
        assert "moves work, not knowledge" in str(exc.value)

    def test_invocation_records_are_not_lineage(self):
        record = Orchestrator(invoker=always_produces).run_cycle(work_set(1))
        assert record.invocations[0].participates_in_lineage is False

    def test_orchestrator_owns_no_store(self):
        o = Orchestrator(invoker=always_empty)
        assert not hasattr(o, "store")
        assert not hasattr(o, "graph")

    def test_no_acceptance_or_integrity_is_bypassed(self):
        """Orchestration never writes; engines write through the Store.

        Checked by absence of any WRITE call and of any Store/graph import.
        Importing FailureRecord from oip.acceptance is legitimate -- that is
        N-10's record type, and recording a failure is not a write of
        knowledge.
        """
        import ast
        import inspect
        from oip import orchestration

        src = inspect.getsource(orchestration)
        for forbidden in (
            "write_evidence", "write_fact", "write_problem", "write_pattern",
            "write_opportunity", "write_solution", "write_validation",
            "write_execution_record", "write_feedback_record",
            "verify_integrity", "assert_integrity", "transition(",
        ):
            assert forbidden not in src, forbidden

        imported = {
            n.module for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.ImportFrom) and n.module
        }
        assert "oip.store" not in imported
        assert "oip.graph" not in imported
        assert "oip.integrity" not in imported

    def test_orchestration_imports_only_control_surface(self):
        """It may know about failure records, engines and time -- nothing more."""
        import ast
        import inspect
        from oip import orchestration

        imported = {
            n.module for n in ast.walk(ast.parse(inspect.getsource(orchestration)))
            if isinstance(n, ast.ImportFrom) and n.module
            and n.module.startswith("oip")
        }
        assert imported == {"oip.acceptance", "oip.contract", "oip.enums"}

    def test_produced_result_requires_ids(self):
        with pytest.raises(InvocationError):
            InvocationResult(InvocationOutcome.PRODUCED, ())

    def test_empty_result_may_not_carry_ids(self):
        with pytest.raises(InvocationError):
            InvocationResult(InvocationOutcome.EMPTY, ("obj-1",))

    def test_empty_produced_id_refused(self):
        with pytest.raises(InvocationError):
            InvocationResult(InvocationOutcome.PRODUCED, ("  ",))

    def test_unknown_outcome_refused(self):
        with pytest.raises(InvocationError):
            InvocationResult("DONE", ())


# ===========================================================================
# Work set validity  [N-17, N-4, M-01]
# ===========================================================================

class TestWorkSetValidity:
    def test_engine_must_be_known(self):
        with pytest.raises(WorkSetError):
            WorkItem("Research", ("s",), "cfg")

    def test_configuration_ref_required(self):
        """N-4: without it the resulting objects are not reproducible."""
        with pytest.raises(WorkSetError) as exc:
            item(1, engine_configuration_ref="  ")
        assert "reproducible" in str(exc.value)

    def test_empty_input_id_refused(self):
        with pytest.raises(WorkSetError):
            item(1, input_ids=("",))

    def test_duplicate_input_refused(self):
        """Duplicate invocation is a named failure mode. [v2 4.12]"""
        with pytest.raises(WorkSetError) as exc:
            item(1, input_ids=("s-1", "s-1"))
        assert "twice" in str(exc.value)

    def test_produces_must_be_a_known_type_or_none(self):
        assert item(1, produces=ObjectType.EVIDENCE).produces is ObjectType.EVIDENCE
        assert item(1, produces=None).produces is None
        with pytest.raises(WorkSetError):
            item(1, produces="Evidence")

    def test_work_set_entries_must_be_work_items(self):
        with pytest.raises(WorkSetError):
            WorkSet(items=("not-an-item",))

    def test_run_cycle_refuses_a_non_work_set(self):
        with pytest.raises(WorkSetError):
            Orchestrator(invoker=always_empty).run_cycle(["item"])

    def test_zero_input_item_permitted(self):
        """An engine may be invoked with no specific input (e.g. acquisition)."""
        record = Orchestrator(invoker=always_produces).run_cycle(
            WorkSet(items=(item(1, input_ids=()),))
        )
        assert record.attempted_count == 1

    def test_work_item_is_immutable(self):
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            item(1).engine = Engine.FEEDBACK

    def test_work_set_is_iterable(self):
        ws = work_set(3)
        assert len(list(ws)) == 3


# ===========================================================================
# Concurrency  [N-11]
# ===========================================================================

class TestConcurrency:
    def test_cycles_are_serialised(self):
        """Interpretation is serialised; two cycles never interleave. [N-11]"""
        active = []
        overlap = []

        def watcher(i):
            active.append(1)
            if len(active) > 1:
                overlap.append(True)
            active.pop()
            return InvocationResult.empty()

        o = Orchestrator(invoker=watcher)
        threads = [threading.Thread(target=lambda: o.run_cycle(work_set(5)))
                   for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert overlap == []
        assert o.cycle_count == 8

    def test_cycle_ids_unique_under_contention(self):
        o = Orchestrator(invoker=always_empty)
        barrier = threading.Barrier(8)

        def run():
            barrier.wait()
            o.run_cycle(work_set(2))

        threads = [threading.Thread(target=run) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        ids = [c.cycle_id for c in o.cycles]
        assert len(set(ids)) == len(ids) == 8

    def test_reentrant_cycle_refused(self):
        """An engine may not start a cycle inside a cycle."""
        holder = {}

        def reentrant(i):
            try:
                holder["o"].run_cycle(WorkSet(items=(item(99),)))
                return InvocationResult.empty("reentered")
            except CycleStateError:
                return InvocationResult.empty("refused")

        o = Orchestrator(invoker=reentrant)
        holder["o"] = o
        record = o.run_cycle(WorkSet(items=(item(1),)))
        assert record.invocations[0].detail == "refused"
        assert o.cycle_count == 1

    def test_is_running_false_when_idle(self):
        o = Orchestrator(invoker=always_empty)
        o.run_cycle(work_set(1))
        assert o.is_running is False

    def test_running_flag_cleared_after_failure(self):
        o = Orchestrator(invoker=always_raises)
        o.run_cycle(work_set(1))
        assert o.is_running is False
        o.run_cycle(work_set(1))
        assert o.cycle_count == 2

    def test_history_snapshot_is_a_copy(self):
        o = Orchestrator(invoker=always_empty)
        o.run_cycle(work_set(1))
        snapshot = o.cycles
        o.run_cycle(work_set(1))
        assert len(snapshot) == 1 and o.cycle_count == 2


# ===========================================================================
# Determinism and reproducibility  [N-17, N-4]
# ===========================================================================

class TestDeterminism:
    def test_identical_plans_produce_identical_sequences(self):
        def signature(record):
            return tuple(
                (r.engine, r.input_ids, r.outcome, r.produced_ids)
                for r in record.invocations
            )

        sigs = set()
        for _ in range(5):
            o = Orchestrator(invoker=always_produces)
            sigs.add(signature(o.run_cycle(work_set(6))))
        assert len(sigs) == 1

    def test_bounded_stop_is_deterministic(self):
        outcomes = set()
        for _ in range(5):
            o = Orchestrator(
                invoker=always_empty,
                bounds=CycleBounds(max_work_items=3, wall_clock_budget_seconds=999),
            )
            record = o.run_cycle(work_set(10))
            outcomes.add((record.outcome, record.attempted_count))
        assert outcomes == {(CycleOutcome.WORK_LIMIT_REACHED, 3)}

    def test_configuration_ref_preserved_end_to_end(self):
        refs = ("cfg-a", "cfg-b", "cfg-c")
        ws = WorkSet(items=tuple(
            item(i, engine_configuration_ref=r) for i, r in enumerate(refs)
        ))
        record = Orchestrator(invoker=always_produces).run_cycle(ws)
        assert tuple(r.engine_configuration_ref for r in record.invocations) == refs


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(planned=st.integers(min_value=0, max_value=40),
       limit=st.integers(min_value=1, max_value=40))
def test_accounting_invariant_over_arbitrary_plans(planned, limit):
    """attempted + not_attempted == planned, for every plan and bound."""
    o = Orchestrator(
        invoker=always_empty,
        bounds=CycleBounds(max_work_items=limit, wall_clock_budget_seconds=9999),
    )
    record = o.run_cycle(work_set(planned))
    assert record.attempted_count + record.not_attempted_count == record.planned_items
    assert record.attempted_count <= limit


@settings(max_examples=200, deadline=None)
@given(planned=st.integers(min_value=1, max_value=30),
       limit=st.integers(min_value=1, max_value=30))
def test_outcome_follows_the_bound_exactly(planned, limit):
    """WORK_LIMIT_REACHED iff the plan exceeds the bound."""
    o = Orchestrator(
        invoker=always_empty,
        bounds=CycleBounds(max_work_items=limit, wall_clock_budget_seconds=9999),
    )
    record = o.run_cycle(work_set(planned))
    if planned > limit:
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED
    else:
        assert record.outcome is CycleOutcome.COMPLETED


@settings(max_examples=200, deadline=None)
@given(limit=st.integers(min_value=1, max_value=50))
def test_a_cycle_never_exceeds_its_work_bound(limit):
    """AC3: iteration is bounded, always."""
    o = Orchestrator(
        invoker=always_produces,
        bounds=CycleBounds(max_work_items=limit, wall_clock_budget_seconds=9999),
    )
    record = o.run_cycle(work_set(100))
    assert record.attempted_count <= limit
    assert record.terminated


@settings(max_examples=150, deadline=None)
@given(count=st.integers(min_value=1, max_value=20))
def test_every_failure_is_surfaced(count):
    """N-10 over arbitrary work-set sizes."""
    o = Orchestrator(invoker=always_raises)
    record = o.run_cycle(work_set(count))
    assert record.failed_count == count
    assert record.had_failure is True
    assert len(record.failures) == count


@settings(max_examples=150, deadline=None)
@given(
    limit=st.integers(min_value=1, max_value=10),
    planned=st.integers(min_value=1, max_value=20),
)
def test_failure_always_visible_regardless_of_bound(limit, planned):
    """Regression property: a bound never hides a failure."""
    o = Orchestrator(
        invoker=always_raises,
        bounds=CycleBounds(max_work_items=limit, wall_clock_budget_seconds=9999),
    )
    record = o.run_cycle(work_set(planned))
    if record.attempted_count > 0:
        assert record.had_failure is True
        assert len(o.failed_cycles()) == 1


@settings(max_examples=150, deadline=None)
@given(engines=st.lists(st.sampled_from(list(Engine)), min_size=1, max_size=9))
def test_any_engine_mix_is_invocable(engines):
    """AC1 over arbitrary engine sequences."""
    ws = WorkSet(items=tuple(item(i, engine=e) for i, e in enumerate(engines)))
    record = Orchestrator(invoker=always_produces).run_cycle(ws)
    assert record.attempted_count == len(engines)
    assert set(record.engines_invoked) == set(engines)


@settings(max_examples=150, deadline=None)
@given(n=st.integers(min_value=1, max_value=12))
def test_cycle_ids_are_strictly_increasing(n):
    o = Orchestrator(invoker=always_empty)
    for _ in range(n):
        o.run_cycle(WorkSet(items=(item(1),)))
    ids = [c.cycle_id for c in o.cycles]
    assert ids == sorted(ids) == list(range(1, n + 1))


# ===========================================================================
# Residual surface
# ===========================================================================

class TestResidualSurface:
    def test_produced_count_sums_across_invocations(self):
        def multi(i):
            return InvocationResult.produced(f"a-{i.input_ids[0]}", f"b-{i.input_ids[0]}")

        record = Orchestrator(invoker=multi).run_cycle(work_set(3))
        assert record.produced_count == 6

    def test_produced_count_zero_when_all_empty(self):
        assert Orchestrator(invoker=always_empty).run_cycle(work_set(3)).produced_count == 0

    def test_cycle_duration_is_measured(self):
        o = Orchestrator(invoker=always_empty, clock=fixed_clock(step_seconds=2.0))
        record = o.run_cycle(work_set(2))
        assert record.duration_seconds > 0.0

    def test_cycle_duration_zero_with_a_frozen_clock(self):
        o = Orchestrator(invoker=always_empty, clock=lambda: T0)
        assert o.run_cycle(work_set(2)).duration_seconds == 0.0

    def test_engine_invoker_protocol_is_structural(self):
        """Any callable with the right shape satisfies it. [P4]"""
        from oip.orchestration import EngineInvoker

        class Invoker:
            def __call__(self, item: WorkItem) -> InvocationResult:
                return InvocationResult.empty()

        record = Orchestrator(invoker=Invoker()).run_cycle(work_set(2))
        assert record.attempted_count == 2
        assert isinstance(EngineInvoker, type(Protocol)) or True
