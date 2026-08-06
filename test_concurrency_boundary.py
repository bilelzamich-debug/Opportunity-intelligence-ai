"""Contract tests for the N-11 concurrency boundary.

Task: T01.6.4

Architecture References:
- N-11   "Acquisition and extraction may run concurrently. Interpretation
         from Problem onward is serialised." Stages 1-2 CONCURRENT,
         stages 3-9 SERIALISED. Pattern Intelligence sees a stable Problem
         population within a batch; version branching is impossible
- IOM 2.6 Stage ownership: the 9-stage -> engine mapping. Stage 8 has no
         owning engine (C-02 open)
- IOM 2.2 "Two engines cannot concurrently version the same object"
- R-1    Non-branching supersession guaranteed only because one engine holds
         create authority per type AND interpretation is serialised (N-11)
- N-17   Batch control model; bounds; cycles serialised
- N-10   Failure recorded, cycle continues, surfaced -- never masked
- N-6    Must not assume immediate graph index consistency
- N-4    Inputs reproducible; outputs NOT deterministic. Properties, never
         output equality
- AD-04  Orchestration sequences but never judges
- v2 4.12 Named failure modes: deadlock, starvation, duplicate invocation,
         partial-failure mishandling
- M-56   Cost model OPEN -- no concurrency limit may be derived
- OQ-14  Graph scope OPEN -- no partitioning

Acceptance criteria under test:
  AC1  Problem-stage-onward writes serialised
  AC2  Pattern Intelligence sees a stable population per batch
  AC3  Version branching impossible
"""

from __future__ import annotations

import dataclasses
import random
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.configuration import FailureStore
from oip.enums import (
    CONCURRENT_STAGES,
    CREATE_AUTHORITY,
    ENGINE_STAGE,
    SERIALISED_STAGES,
    Engine,
    ObjectType,
)
from oip.orchestration import (
    ConcurrencyBoundary,
    ConcurrencyClass,
    ConcurrencyError,
    ConcurrencyViolation,
    CycleBounds,
    CycleOutcome,
    CycleRecord,
    CycleStateError,
    ExecutionPhase,
    FailureSurface,
    InvocationOutcome,
    InvocationRecord,
    InvocationResult,
    Orchestrator,
    ProcessingStateStore,
    WorkItem,
    WorkSet,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)

ACQUISITION = (Engine.RESEARCH, Engine.FACT_EXTRACTION)
INTERPRETATION = (
    Engine.PROBLEM_INTELLIGENCE,
    Engine.PATTERN_INTELLIGENCE,
    Engine.OPPORTUNITY_INTELLIGENCE,
    Engine.SOLUTION_INTELLIGENCE,
    Engine.VALIDATION,
    Engine.FEEDBACK,
)
ALL_PIPELINE = ACQUISITION + INTERPRETATION


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def item(n: int | str = 1, engine: Engine = Engine.RESEARCH, **kw) -> WorkItem:
    return WorkItem(engine, (f"s-{n}",), "cfg-v1", **kw)


def empty_invoker(_item: WorkItem) -> InvocationResult:
    return InvocationResult.empty()


def raising_invoker(_item: WorkItem) -> InvocationResult:
    raise RuntimeError("engine down")


def invocation(
    n: int | str = 1,
    engine: Engine = Engine.RESEARCH,
    outcome: InvocationOutcome = InvocationOutcome.EMPTY,
    start: float = 0.0,
    end: float = 1.0,
) -> InvocationRecord:
    return InvocationRecord(
        engine, (f"s-{n}",), "cfg-v1", outcome, (), "",
        T0 + timedelta(seconds=start), T0 + timedelta(seconds=end),
    )


def cycle_of(invocations, cycle_id: int = 1) -> CycleRecord:
    invocations = tuple(invocations)
    return CycleRecord(
        cycle_id=cycle_id,
        outcome=CycleOutcome.COMPLETED,
        bounds=CycleBounds(),
        invocations=invocations,
        failures=(),
        planned_items=len(invocations),
        started_at=T0,
        ended_at=T0 + timedelta(seconds=60),
    )


class OverlapTracker:
    """Records genuine in-flight overlap, independent of recorded timestamps."""

    def __init__(self, hold: float = 0.004) -> None:
        self.hold = hold
        self._lock = threading.Lock()
        self._acquisition = 0
        self._interpretation = 0
        self.max_concurrent_acquisition = 0
        self.max_concurrent_interpretation = 0
        self.acquisition_during_interpretation = 0
        self._per_engine: dict[Engine, int] = {}
        self.same_engine_overlap = 0

    def __call__(self, work_item: WorkItem) -> InvocationResult:
        with self._lock:
            count = self._per_engine.get(work_item.engine, 0) + 1
            self._per_engine[work_item.engine] = count
            if count > 1 and work_item.engine in INTERPRETATION:
                self.same_engine_overlap += 1
            if work_item.engine in ACQUISITION:
                self._acquisition += 1
            else:
                self._interpretation += 1
            self.max_concurrent_acquisition = max(
                self.max_concurrent_acquisition, self._acquisition
            )
            self.max_concurrent_interpretation = max(
                self.max_concurrent_interpretation, self._interpretation
            )
            if self._acquisition and self._interpretation:
                self.acquisition_during_interpretation += 1
        time.sleep(self.hold)
        with self._lock:
            self._per_engine[work_item.engine] -= 1
            if work_item.engine in ACQUISITION:
                self._acquisition -= 1
            else:
                self._interpretation -= 1
        return InvocationResult.empty()


# ---------------------------------------------------------------------------
# Stage classification -- exactly N-11's table
# ---------------------------------------------------------------------------

class TestStageClassification:
    def test_engine_stage_matches_iom_2_6(self):
        assert ENGINE_STAGE == {
            Engine.RESEARCH: 1,
            Engine.FACT_EXTRACTION: 2,
            Engine.PROBLEM_INTELLIGENCE: 3,
            Engine.PATTERN_INTELLIGENCE: 4,
            Engine.OPPORTUNITY_INTELLIGENCE: 5,
            Engine.SOLUTION_INTELLIGENCE: 6,
            Engine.VALIDATION: 7,
            Engine.FEEDBACK: 9,
        }

    def test_orchestration_owns_no_stage(self):
        """Cross-cutting, not pipeline-aligned. [IOM 4.6]"""
        assert Engine.ORCHESTRATION not in ENGINE_STAGE

    def test_stage_8_has_no_engine(self):
        """C-02 remains open; no producer may be invented."""
        assert 8 not in ENGINE_STAGE.values()

    def test_engine_stages_agree_with_create_authority(self):
        assert all(
            ENGINE_STAGE[engine] == object_type.stage
            for object_type, engine in CREATE_AUTHORITY.items()
        )

    def test_the_boundary_falls_between_stage_2_and_3(self):
        assert CONCURRENT_STAGES == frozenset({1, 2})
        assert SERIALISED_STAGES == frozenset({3, 4, 5, 6, 7, 8, 9})

    def test_stage_classes_partition_all_nine_stages(self):
        assert CONCURRENT_STAGES | SERIALISED_STAGES == set(range(1, 10))
        assert not CONCURRENT_STAGES & SERIALISED_STAGES

    @pytest.mark.parametrize("engine", ACQUISITION)
    def test_acquisition_engines_are_concurrent(self, engine):
        assert item(1, engine).concurrency_class is ConcurrencyClass.CONCURRENT
        assert item(1, engine).is_concurrent is True

    @pytest.mark.parametrize("engine", INTERPRETATION)
    def test_interpretation_engines_are_serialised(self, engine):
        assert item(1, engine).concurrency_class is ConcurrencyClass.SERIALISED
        assert item(1, engine).is_serialised is True

    def test_orchestration_item_fails_closed(self):
        with pytest.raises(ConcurrencyError):
            item(1, Engine.ORCHESTRATION).concurrency_class

    def test_produces_resolves_the_stage_when_given(self):
        assert item(1, Engine.RESEARCH, produces=ObjectType.PROBLEM).stage == 3

    def test_object_type_governs_over_engine(self):
        """The object type IS the stage. [IOM 2.6]"""
        assert item(
            1, Engine.RESEARCH, produces=ObjectType.PROBLEM
        ).is_serialised is True

    def test_stage_8_reachable_only_by_object_type(self):
        work = item(1, Engine.FEEDBACK, produces=ObjectType.EXECUTION_RECORD)
        assert work.stage == 8
        assert work.is_serialised is True

    def test_orchestration_with_produces_is_classifiable(self):
        assert item(
            1, Engine.ORCHESTRATION, produces=ObjectType.EVIDENCE
        ).is_concurrent is True

    def test_concurrency_class_has_exactly_two_members(self):
        assert len(list(ConcurrencyClass)) == 2


# ---------------------------------------------------------------------------
# Phase planning
# ---------------------------------------------------------------------------

class TestPhasePlanning:
    def test_adjacent_concurrent_items_form_one_phase(self):
        plan = WorkSet(items=(item(0), item(1, Engine.FACT_EXTRACTION))).concurrency_plan()
        assert len(plan) == 1
        assert plan[0].concurrency_class is ConcurrencyClass.CONCURRENT
        assert plan[0].item_indices == (0, 1)

    def test_each_serialised_item_is_its_own_phase(self):
        plan = WorkSet(items=tuple(
            item(n, Engine.PROBLEM_INTELLIGENCE) for n in range(4)
        )).concurrency_plan()
        assert len(plan) == 4
        assert all(len(p) == 1 for p in plan)

    def test_mixed_plan_preserves_caller_order(self):
        plan = WorkSet(items=(
            item(0), item(1, Engine.FACT_EXTRACTION),
            item(2, Engine.PROBLEM_INTELLIGENCE),
            item(3, Engine.PATTERN_INTELLIGENCE), item(4),
        )).concurrency_plan()
        assert [(p.concurrency_class, p.item_indices) for p in plan] == [
            (ConcurrencyClass.CONCURRENT, (0, 1)),
            (ConcurrencyClass.SERIALISED, (2,)),
            (ConcurrencyClass.SERIALISED, (3,)),
            (ConcurrencyClass.CONCURRENT, (4,)),
        ]

    def test_empty_work_set_plans_nothing(self):
        assert WorkSet(items=()).concurrency_plan() == ()

    def test_a_serialised_phase_may_not_hold_two_items(self):
        """Interpretation runs one batch at a time. [N-11]"""
        with pytest.raises(ConcurrencyError):
            ExecutionPhase(ConcurrencyClass.SERIALISED, (0, 1))

    def test_an_empty_phase_is_refused(self):
        with pytest.raises(ConcurrencyError):
            ExecutionPhase(ConcurrencyClass.CONCURRENT, ())

    def test_phase_requires_a_concurrency_class(self):
        with pytest.raises(ConcurrencyError):
            ExecutionPhase("CONCURRENT", (0,))  # type: ignore[arg-type]

    def test_is_parallel_is_permission_not_obligation(self):
        """N-11 says acquisition MAY run concurrently."""
        phase = ExecutionPhase(ConcurrencyClass.CONCURRENT, (0,))
        assert phase.is_parallel is True
        assert len(phase) == 1


# ---------------------------------------------------------------------------
# AC1 -- Problem-stage-onward writes serialised
# ---------------------------------------------------------------------------

class TestInterpretationSerialised:
    def test_serialised_invocations_never_overlap_in_flight(self):
        tracker = OverlapTracker()
        Orchestrator(invoker=tracker, max_workers=8).run_cycle(WorkSet(items=tuple(
            item(n, INTERPRETATION[n % len(INTERPRETATION)]) for n in range(12)
        )))
        assert tracker.max_concurrent_interpretation == 1

    def test_boundary_reports_serialisation_held(self):
        record = Orchestrator(invoker=OverlapTracker(), max_workers=8).run_cycle(
            WorkSet(items=tuple(item(n, Engine.PROBLEM_INTELLIGENCE) for n in range(6)))
        )
        boundary = ConcurrencyBoundary(record)
        assert boundary.interpretation_serialised is True
        assert boundary.serialisation_violations() == ()

    def test_stage_8_items_serialise_against_each_other(self):
        tracker = OverlapTracker()
        Orchestrator(invoker=tracker, max_workers=8).run_cycle(WorkSet(items=tuple(
            WorkItem(Engine.FEEDBACK, (f"x-{n}",), "cfg",
                     produces=ObjectType.EXECUTION_RECORD)
            for n in range(5)
        )))
        assert tracker.max_concurrent_interpretation == 1

    def test_an_overlap_is_detected_when_it_exists(self):
        record = cycle_of([
            invocation(1, Engine.PROBLEM_INTELLIGENCE, start=0, end=10),
            invocation(2, Engine.PATTERN_INTELLIGENCE, start=5, end=15),
        ])
        boundary = ConcurrencyBoundary(record)
        assert boundary.interpretation_serialised is False
        assert len(boundary.serialisation_violations()) == 1

    def test_adjacent_non_overlapping_invocations_are_fine(self):
        record = cycle_of([
            invocation(1, Engine.PROBLEM_INTELLIGENCE, start=0, end=5),
            invocation(2, Engine.PATTERN_INTELLIGENCE, start=5, end=10),
        ])
        assert ConcurrencyBoundary(record).interpretation_serialised is True


# ---------------------------------------------------------------------------
# AC2 -- stable population per batch
# ---------------------------------------------------------------------------

class TestStablePopulation:
    def test_acquisition_never_runs_during_interpretation(self):
        tracker = OverlapTracker()
        Orchestrator(invoker=tracker, max_workers=4).run_cycle(WorkSet(items=(
            item(0), item(1), item(2, Engine.FACT_EXTRACTION),
            item(3, Engine.PROBLEM_INTELLIGENCE),
            item(4), item(5),
            item(6, Engine.PATTERN_INTELLIGENCE),
        )))
        assert tracker.acquisition_during_interpretation == 0

    def test_the_barrier_holds_with_io_bound_engines(self):
        """Real GIL-releasing waits, where a broken barrier would show."""
        tracker = OverlapTracker(hold=0.01)
        Orchestrator(invoker=tracker, max_workers=4).run_cycle(WorkSet(items=(
            item(0), item(1), item(2), item(3),
            item(4, Engine.PATTERN_INTELLIGENCE),
            item(5), item(6), item(7),
        )))
        assert tracker.acquisition_during_interpretation == 0
        assert tracker.max_concurrent_acquisition > 1

    def test_boundary_reports_population_stable(self):
        record = Orchestrator(invoker=OverlapTracker(), max_workers=4).run_cycle(
            WorkSet(items=(item(0), item(1),
                           item(2, Engine.PATTERN_INTELLIGENCE), item(3)))
        )
        boundary = ConcurrencyBoundary(record)
        assert boundary.population_stable is True
        assert boundary.barrier_violations() == ()

    def test_a_barrier_breach_is_detected_when_it_exists(self):
        record = cycle_of([
            invocation(1, Engine.RESEARCH, start=0, end=10),
            invocation(2, Engine.PATTERN_INTELLIGENCE, start=5, end=15),
        ])
        boundary = ConcurrencyBoundary(record)
        assert boundary.population_stable is False
        assert len(boundary.barrier_violations()) == 1

    def test_acquisition_may_still_parallelise(self):
        """N-11's entire purpose: the concurrent half must actually work."""
        tracker = OverlapTracker(hold=0.02)
        Orchestrator(invoker=tracker, max_workers=4).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(8)))
        )
        assert tracker.max_concurrent_acquisition > 1


# ---------------------------------------------------------------------------
# AC3 -- version branching impossible
# ---------------------------------------------------------------------------

class TestBranchingImpossible:
    def test_one_engine_never_runs_twice_concurrently(self):
        """R-1: the guarantee rests on serialised interpretation."""
        tracker = OverlapTracker()
        Orchestrator(invoker=tracker, max_workers=8).run_cycle(
            WorkSet(items=tuple(
                item(n, Engine.PROBLEM_INTELLIGENCE) for n in range(10)
            ))
        )
        assert tracker.same_engine_overlap == 0

    def test_boundary_reports_branching_impossible(self):
        record = Orchestrator(invoker=OverlapTracker(), max_workers=8).run_cycle(
            WorkSet(items=tuple(
                item(n, Engine.SOLUTION_INTELLIGENCE) for n in range(6)
            ))
        )
        boundary = ConcurrencyBoundary(record)
        assert boundary.branching_impossible is True
        assert boundary.concurrent_same_type_writers() == ()

    def test_a_same_engine_overlap_is_detected(self):
        record = cycle_of([
            invocation(1, Engine.PROBLEM_INTELLIGENCE, start=0, end=10),
            invocation(2, Engine.PROBLEM_INTELLIGENCE, start=2, end=12),
        ])
        boundary = ConcurrencyBoundary(record)
        assert boundary.branching_impossible is False
        assert len(boundary.concurrent_same_type_writers()) == 1

    def test_concurrent_stages_are_exempt_by_ratified_decision(self):
        """N-11 permits stage 1-2 parallelism explicitly."""
        record = cycle_of([
            invocation(1, Engine.RESEARCH, start=0, end=10),
            invocation(2, Engine.RESEARCH, start=1, end=11),
        ])
        assert ConcurrencyBoundary(record).branching_impossible is True


class TestBoundaryVerifier:
    def test_holds_combines_all_three_criteria(self):
        record = Orchestrator(invoker=empty_invoker, max_workers=4).run_cycle(
            WorkSet(items=(item(0), item(1, Engine.PROBLEM_INTELLIGENCE)))
        )
        assert ConcurrencyBoundary(record).holds is True

    def test_assert_holds_passes_on_a_clean_cycle(self):
        record = Orchestrator(invoker=empty_invoker, max_workers=4).run_cycle(
            WorkSet(items=(item(0), item(1)))
        )
        ConcurrencyBoundary(record).assert_holds()

    def test_assert_holds_fails_closed(self):
        record = cycle_of([
            invocation(1, Engine.PROBLEM_INTELLIGENCE, start=0, end=10),
            invocation(2, Engine.PROBLEM_INTELLIGENCE, start=1, end=11),
        ])
        with pytest.raises(ConcurrencyViolation):
            ConcurrencyBoundary(record).assert_holds()

    def test_violation_message_names_each_breached_criterion(self):
        record = cycle_of([
            invocation(1, Engine.RESEARCH, start=0, end=10),
            invocation(2, Engine.PROBLEM_INTELLIGENCE, start=1, end=11),
            invocation(3, Engine.PROBLEM_INTELLIGENCE, start=2, end=12),
        ])
        with pytest.raises(ConcurrencyViolation) as caught:
            ConcurrencyBoundary(record).assert_holds()
        message = str(caught.value)
        assert "AC1" in message and "AC2" in message and "AC3" in message

    def test_unattempted_invocations_are_ignored(self):
        record = cycle_of([
            invocation(1, Engine.PROBLEM_INTELLIGENCE,
                       outcome=InvocationOutcome.NOT_ATTEMPTED, start=0, end=10),
            invocation(2, Engine.PROBLEM_INTELLIGENCE,
                       outcome=InvocationOutcome.NOT_ATTEMPTED, start=0, end=10),
        ])
        assert ConcurrencyBoundary(record).holds is True

    def test_unclassified_records_are_surfaced(self):
        record = cycle_of([invocation(1, Engine.ORCHESTRATION)])
        assert len(ConcurrencyBoundary(record).unclassified_records()) == 1

    def test_classified_records_partition_the_attempted_work(self):
        record = Orchestrator(invoker=empty_invoker, max_workers=2).run_cycle(
            WorkSet(items=(item(0), item(1, Engine.PROBLEM_INTELLIGENCE)))
        )
        boundary = ConcurrencyBoundary(record)
        assert len(boundary.concurrent_records()) == 1
        assert len(boundary.serialised_records()) == 1

    @pytest.mark.parametrize("bad", ["x", None, 5, object()])
    def test_verifier_refuses_a_non_cycle(self, bad):
        with pytest.raises(ConcurrencyError):
            ConcurrencyBoundary(bad)

    def test_verifier_is_frozen(self):
        record = Orchestrator(invoker=empty_invoker).run_cycle(
            WorkSet(items=(item(0),))
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            ConcurrencyBoundary(record).cycle = None  # type: ignore[misc]

    def test_verifier_never_participates_in_lineage(self):
        record = Orchestrator(invoker=empty_invoker).run_cycle(
            WorkSet(items=(item(0),))
        )
        assert ConcurrencyBoundary(record).participates_in_lineage is False

    def test_verifier_mutates_nothing(self):
        record = Orchestrator(invoker=empty_invoker, max_workers=2).run_cycle(
            WorkSet(items=(item(0), item(1)))
        )
        before = (record.attempted_count, record.outcome, len(record.invocations))
        boundary = ConcurrencyBoundary(record)
        boundary.holds
        boundary.serialisation_violations()
        boundary.barrier_violations()
        boundary.concurrent_same_type_writers()
        assert (record.attempted_count, record.outcome,
                len(record.invocations)) == before


# ---------------------------------------------------------------------------
# Determinism of the record  [N-4, A1]
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_recorded_order_is_work_set_order(self):
        def jittery(_item: WorkItem) -> InvocationResult:
            time.sleep(random.uniform(0, 0.008))
            return InvocationResult.empty()

        work = WorkSet(items=tuple(item(n) for n in range(12)))
        for _ in range(5):
            record = Orchestrator(invoker=jittery, max_workers=6).run_cycle(work)
            assert [r.input_ids[0] for r in record.invocations] == [
                f"s-{n}" for n in range(12)
            ]

    def test_parallel_matches_sequential_record_shape(self):
        work = WorkSet(items=(
            item(0), item(1), item(2, Engine.PROBLEM_INTELLIGENCE), item(3)
        ))
        sequential = Orchestrator(invoker=empty_invoker, max_workers=1).run_cycle(work)
        parallel = Orchestrator(invoker=empty_invoker, max_workers=4).run_cycle(work)
        assert [r.input_ids for r in parallel.invocations] == [
            r.input_ids for r in sequential.invocations
        ]
        assert [r.engine for r in parallel.invocations] == [
            r.engine for r in sequential.invocations
        ]
        assert parallel.attempted_count == sequential.attempted_count
        assert parallel.outcome is sequential.outcome

    def test_slow_items_do_not_reorder_the_record(self):
        def uneven(work_item: WorkItem) -> InvocationResult:
            n = int(work_item.input_ids[0].split("-")[1])
            time.sleep(0.02 if n % 2 == 0 else 0.001)
            return InvocationResult.empty()

        record = Orchestrator(invoker=uneven, max_workers=4).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(10)))
        )
        assert [r.input_ids[0] for r in record.invocations] == [
            f"s-{n}" for n in range(10)
        ]

    def test_failure_attribution_index_matches_position(self):
        store = FailureStore()
        Orchestrator(invoker=raising_invoker, failure_store=store,
                     max_workers=4).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(8)))
        )
        for record in store.all():
            assert record.input_ids == (f"s-{record.invocation_index}",)


# ---------------------------------------------------------------------------
# Bounds under concurrency  [N-17]
# ---------------------------------------------------------------------------

class TestBoundsPreserved:
    def test_work_limit_enforced_under_parallelism(self):
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4,
            bounds=CycleBounds(max_work_items=5),
        ).run_cycle(WorkSet(items=tuple(item(n) for n in range(20))))
        assert record.attempted_count == 5
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED

    @pytest.mark.parametrize("limit", [1, 2, 3, 5, 7, 11, 12, 20])
    def test_parallel_attempts_exactly_what_sequential_would(self, limit):
        """Regression: a large concurrent phase must not be refused whole."""
        work = WorkSet(items=tuple(item(n) for n in range(12)))
        bounds = CycleBounds(max_work_items=limit)
        sequential = Orchestrator(
            invoker=empty_invoker, max_workers=1, bounds=bounds
        ).run_cycle(work)
        parallel = Orchestrator(
            invoker=empty_invoker, max_workers=4, bounds=bounds
        ).run_cycle(work)
        assert parallel.attempted_count == sequential.attempted_count
        assert parallel.not_attempted_count == sequential.not_attempted_count
        assert parallel.outcome is sequential.outcome

    def test_a_bounded_concurrent_phase_still_runs_its_prefix(self):
        """Starvation is a named failure mode. [v2 4.12]"""
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4,
            bounds=CycleBounds(max_work_items=3),
        ).run_cycle(WorkSet(items=tuple(item(n) for n in range(12))))
        assert record.attempted_count == 3, "the whole phase was refused"

    def test_unattempted_work_is_recorded(self):
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4,
            bounds=CycleBounds(max_work_items=4),
        ).run_cycle(WorkSet(items=tuple(item(n) for n in range(12))))
        assert record.not_attempted_count == 8
        assert len(record.invocations) == 12

    def test_budget_exhaustion_terminates_a_parallel_cycle(self):
        ticks = iter([T0 + timedelta(seconds=i * 100) for i in range(200)])
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4,
            bounds=CycleBounds(wall_clock_budget_seconds=1.0),
            clock=lambda: next(ticks),
        ).run_cycle(WorkSet(items=tuple(
            item(n, Engine.PROBLEM_INTELLIGENCE) for n in range(8)
        )))
        assert record.outcome is CycleOutcome.BUDGET_EXHAUSTED

    def test_every_cycle_still_terminates(self):
        orchestrator = Orchestrator(invoker=empty_invoker, max_workers=4)
        for _ in range(10):
            assert orchestrator.run_cycle(
                WorkSet(items=tuple(item(n) for n in range(6)))
            ).terminated is True


# ---------------------------------------------------------------------------
# Failure semantics preserved  [N-10, T01.6.3]
# ---------------------------------------------------------------------------

class TestFailureSemanticsPreserved:
    def test_all_parallel_failures_recorded(self):
        store = FailureStore()
        orchestrator = Orchestrator(
            invoker=raising_invoker, failure_store=store, max_workers=8
        )
        record = orchestrator.run_cycle(
            WorkSet(items=tuple(item(n) for n in range(20)))
        )
        assert record.failed_count == 20
        assert len(store) == 20
        assert store.unattributed() == ()

    def test_failures_never_masked_under_concurrency(self):
        orchestrator = Orchestrator(invoker=raising_invoker, max_workers=4)
        for _ in range(5):
            orchestrator.run_cycle(WorkSet(items=tuple(item(n) for n in range(6))))
        surface = FailureSurface.over(orchestrator)
        assert surface.failed_count == 30
        assert surface.masked_cycles() == ()
        surface.assert_not_masked()

    def test_a_failure_does_not_stop_its_phase(self):
        seen: list[str] = []
        guard = threading.Lock()

        def flaky(work_item: WorkItem) -> InvocationResult:
            with guard:
                seen.append(work_item.input_ids[0])
            if work_item.input_ids[0] == "s-0":
                raise RuntimeError("boom")
            return InvocationResult.empty()

        record = Orchestrator(invoker=flaky, max_workers=4).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(8)))
        )
        assert len(seen) == 8
        assert record.attempted_count == 8

    def test_a_failed_phase_does_not_block_the_next(self):
        def acquisition_fails(work_item: WorkItem) -> InvocationResult:
            if work_item.engine is Engine.RESEARCH:
                raise RuntimeError("boom")
            return InvocationResult.empty()

        record = Orchestrator(invoker=acquisition_fails, max_workers=4).run_cycle(
            WorkSet(items=(item(0), item(1), item(2, Engine.PROBLEM_INTELLIGENCE)))
        )
        assert record.attempted_count == 3
        assert record.failed_count == 2

    def test_empty_and_failed_stay_distinguishable(self):
        def mixed(work_item: WorkItem) -> InvocationResult:
            if int(work_item.input_ids[0].split("-")[1]) % 2:
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orchestrator = Orchestrator(invoker=mixed, max_workers=4)
        orchestrator.run_cycle(WorkSet(items=tuple(item(n) for n in range(10))))
        surface = FailureSurface.over(orchestrator)
        assert surface.failed_count == 5
        assert surface.empty_count == 5

    def test_a_hostile_failure_store_does_not_lose_the_cycle(self):
        class Hostile(FailureStore):
            def record(self, failure):
                raise RuntimeError("store unavailable")

        orchestrator = Orchestrator(
            invoker=raising_invoker, failure_store=Hostile(), max_workers=4
        )
        record = orchestrator.run_cycle(
            WorkSet(items=tuple(item(n) for n in range(6)))
        )
        assert orchestrator.cycle_count == 1
        assert record.failed_count == 6

    def test_a_hostile_exception_in_a_worker_still_surfaces(self):
        class Nasty(Exception):
            def __str__(self):
                raise RuntimeError("no str")

        record = Orchestrator(
            invoker=lambda i: (_ for _ in ()).throw(Nasty()), max_workers=4
        ).run_cycle(WorkSet(items=tuple(item(n) for n in range(6))))
        assert record.failed_count == 6


# ---------------------------------------------------------------------------
# Processing state preserved  [T01.6.2]
# ---------------------------------------------------------------------------

class TestProcessingStatePreserved:
    def test_every_attempted_item_recorded_exactly_once(self):
        store = ProcessingStateStore()
        Orchestrator(invoker=empty_invoker, processing_store=store,
                     max_workers=8).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(40)))
        )
        assert len(store) == 40
        assert store.reprocessed_keys() == ()

    def test_no_duplicate_invocation_under_parallelism(self):
        """Duplicate invocation is a named failure mode. [v2 4.12]"""
        calls: list[str] = []
        guard = threading.Lock()

        def track(work_item: WorkItem) -> InvocationResult:
            with guard:
                calls.append(work_item.input_ids[0])
            return InvocationResult.empty()

        Orchestrator(invoker=track, max_workers=8).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(50)))
        )
        assert len(calls) == len(set(calls)) == 50

    def test_unattempted_work_never_recorded_as_processed(self):
        store = ProcessingStateStore()
        Orchestrator(
            invoker=empty_invoker, processing_store=store, max_workers=4,
            bounds=CycleBounds(max_work_items=5),
        ).run_cycle(WorkSet(items=tuple(item(n) for n in range(20))))
        assert len(store) == 5

    def test_idempotence_detection_intact(self):
        store = ProcessingStateStore()
        orchestrator = Orchestrator(
            invoker=empty_invoker, processing_store=store, max_workers=4
        )
        work = WorkSet(items=tuple(item(n) for n in range(8)))
        orchestrator.run_cycle(work)
        orchestrator.run_cycle(work)
        assert len(store.reprocessed_keys()) == 8


# ---------------------------------------------------------------------------
# Deadlock, starvation, reentrancy
# ---------------------------------------------------------------------------

class TestNoDeadlockOrStarvation:
    def test_a_blocking_engine_does_not_deadlock(self):
        def waiter(_item: WorkItem) -> InvocationResult:
            time.sleep(0.02)
            return InvocationResult.empty()

        done = threading.Event()

        def run() -> None:
            Orchestrator(invoker=waiter, max_workers=2).run_cycle(
                WorkSet(items=tuple(item(n) for n in range(4)))
            )
            done.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=30)
        assert done.is_set()

    def test_a_reentrant_engine_is_refused_not_deadlocked(self):
        orchestrator = Orchestrator(invoker=empty_invoker, max_workers=2)
        refused: list[bool] = []

        def reentrant(_item: WorkItem) -> InvocationResult:
            try:
                orchestrator.run_cycle(WorkSet(items=(item(99),)))
                refused.append(False)
            except CycleStateError:
                refused.append(True)
            return InvocationResult.empty()

        orchestrator.invoker = reentrant
        done = threading.Event()

        def run() -> None:
            orchestrator.run_cycle(WorkSet(items=(item(0), item(1))))
            done.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        thread.join(timeout=30)
        assert done.is_set()
        assert all(refused)

    def test_no_item_starves(self):
        def jitter(_item: WorkItem) -> InvocationResult:
            time.sleep(random.uniform(0, 0.004))
            return InvocationResult.empty()

        record = Orchestrator(invoker=jitter, max_workers=4).run_cycle(
            WorkSet(items=tuple(item(n) for n in range(30)))
        )
        assert record.attempted_count == 30

    def test_worker_threads_do_not_leak(self):
        before = threading.active_count()
        orchestrator = Orchestrator(invoker=empty_invoker, max_workers=8)
        for _ in range(20):
            orchestrator.run_cycle(WorkSet(items=tuple(item(n) for n in range(8))))
        time.sleep(0.2)
        assert threading.active_count() <= before + 2

    def test_is_running_clears_after_a_parallel_cycle(self):
        orchestrator = Orchestrator(invoker=empty_invoker, max_workers=4)
        orchestrator.run_cycle(WorkSet(items=(item(0), item(1))))
        assert orchestrator.is_running is False

    def test_is_running_clears_when_a_commit_raises(self):
        class Hostile(ProcessingStateStore):
            def record_cycle(self, cycle):
                raise RuntimeError("nope")

        orchestrator = Orchestrator(
            invoker=empty_invoker, processing_store=Hostile(), max_workers=4
        )
        with pytest.raises(RuntimeError):
            orchestrator.run_cycle(WorkSet(items=(item(0), item(1))))
        assert orchestrator.is_running is False


# ---------------------------------------------------------------------------
# Fail-closed and no invented policy
# ---------------------------------------------------------------------------

class TestFailsClosed:
    @pytest.mark.parametrize("bad", [0, -1, True, 1.5, "4", None])
    def test_bad_max_workers_refused(self, bad):
        with pytest.raises(ConcurrencyError):
            Orchestrator(invoker=empty_invoker, max_workers=bad).run_cycle(
                WorkSet(items=(item(0),))
            )

    def test_an_unclassifiable_item_aborts_before_any_work_runs(self):
        calls: list[int] = []

        def counted(_item: WorkItem) -> InvocationResult:
            calls.append(1)
            return InvocationResult.empty()

        orchestrator = Orchestrator(invoker=counted, max_workers=4)
        with pytest.raises(ConcurrencyError):
            orchestrator.run_cycle(
                WorkSet(items=(item(0), item(1, Engine.ORCHESTRATION)))
            )
        assert orchestrator.is_running is False

    def test_no_concurrency_limit_is_derived_from_the_machine(self):
        """M-56 is OPEN: no cost bound exists to derive a worker count from."""
        import inspect

        source = inspect.getsource(Orchestrator)
        for banned in ("cpu_count", "os.cpu", "multiprocessing"):
            assert banned not in source

    def test_no_queue_or_backpressure_vocabulary_invented(self):
        banned = ("queue_bound", "backpressure", "throttle", "rebalance",
                  "priority", "reorder")
        for cls in (WorkSet, Orchestrator, ConcurrencyBoundary):
            names = [n for n in dir(cls) if not n.startswith("_")]
            assert not [n for n in names if any(b in n.lower() for b in banned)]

    def test_no_graph_partitioning_invented(self):
        """OQ-14 remains open and unconstrained by N-11.

        Partitioning the WORK SET into phases is this task's mechanism and is
        unrelated; what must not appear is any partitioning of the knowledge
        graph or the store.
        """
        import inspect

        import oip.orchestration as module

        source = inspect.getsource(module).lower()
        for banned in ("graph partition", "partition the graph",
                       "partitioned graph", "shard", "namespace"):
            assert banned not in source, banned
        assert "knowledgegraph" not in source.replace(" ", "")


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_default_is_sequential(self):
        assert Orchestrator(invoker=empty_invoker).max_workers == 1

    def test_default_cycle_behaviour_unchanged(self):
        record = Orchestrator(invoker=empty_invoker).run_cycle(
            WorkSet(items=(item(0), item(1)))
        )
        assert record.attempted_count == 2
        assert record.outcome is CycleOutcome.COMPLETED

    def test_orchestrator_field_order_unchanged(self):
        import inspect

        params = list(inspect.signature(Orchestrator).parameters)
        assert params[:5] == [
            "invoker", "bounds", "failure_store", "processing_store", "clock"
        ]

    def test_orchestration_produces_no_intelligence_objects(self):
        orchestrator = Orchestrator(invoker=empty_invoker, max_workers=4)
        orchestrator.run_cycle(WorkSet(items=(item(0),)))
        assert orchestrator.produces_intelligence_objects is False

    def test_cycles_remain_serialised_against_each_other(self):
        orchestrator = Orchestrator(invoker=empty_invoker, max_workers=4)
        for _ in range(5):
            orchestrator.run_cycle(WorkSet(items=(item(0),)))
        assert [c.cycle_id for c in orchestrator.cycles] == [1, 2, 3, 4, 5]

    def test_work_item_without_produces_still_valid(self):
        assert item(1).produces is None


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality]
# ---------------------------------------------------------------------------

engines = st.sampled_from(list(ALL_PIPELINE))


@settings(max_examples=200, deadline=None)
@given(chosen=st.lists(engines, min_size=1, max_size=12))
def test_property_plan_covers_every_index_in_order(chosen):
    work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
    flat = [i for phase in work.concurrency_plan() for i in phase.item_indices]
    assert flat == list(range(len(chosen)))


@settings(max_examples=200, deadline=None)
@given(chosen=st.lists(engines, min_size=1, max_size=12))
def test_property_serialised_phases_are_singletons(chosen):
    work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
    for phase in work.concurrency_plan():
        if phase.concurrency_class is ConcurrencyClass.SERIALISED:
            assert len(phase) == 1
        else:
            assert all(
                work.items[i].is_concurrent for i in phase.item_indices
            )


@settings(max_examples=100, deadline=None)
@given(chosen=st.lists(engines, min_size=1, max_size=8),
       workers=st.integers(min_value=1, max_value=6))
def test_property_boundary_always_holds(chosen, workers):
    work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
    record = Orchestrator(invoker=empty_invoker, max_workers=workers).run_cycle(work)
    ConcurrencyBoundary(record).assert_holds()


@settings(max_examples=100, deadline=None)
@given(chosen=st.lists(engines, min_size=1, max_size=8),
       workers=st.integers(min_value=2, max_value=6))
def test_property_parallel_matches_sequential(chosen, workers):
    """Concurrency changes no recorded semantics. [N-11, N-4]"""
    work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
    sequential = Orchestrator(invoker=empty_invoker, max_workers=1).run_cycle(work)
    parallel = Orchestrator(invoker=empty_invoker, max_workers=workers).run_cycle(work)
    assert [r.input_ids for r in parallel.invocations] == [
        r.input_ids for r in sequential.invocations
    ]
    assert [r.engine for r in parallel.invocations] == [
        r.engine for r in sequential.invocations
    ]
    assert parallel.attempted_count == sequential.attempted_count
    assert parallel.outcome is sequential.outcome


@settings(max_examples=100, deadline=None)
@given(count=st.integers(min_value=1, max_value=14),
       limit=st.integers(min_value=1, max_value=16),
       workers=st.integers(min_value=2, max_value=6))
def test_property_bounds_identical_to_sequential(count, limit, workers):
    work = WorkSet(items=tuple(item(n) for n in range(count)))
    bounds = CycleBounds(max_work_items=limit)
    sequential = Orchestrator(
        invoker=empty_invoker, max_workers=1, bounds=bounds
    ).run_cycle(work)
    parallel = Orchestrator(
        invoker=empty_invoker, max_workers=workers, bounds=bounds
    ).run_cycle(work)
    assert parallel.attempted_count == sequential.attempted_count
    assert parallel.not_attempted_count == sequential.not_attempted_count
    assert parallel.outcome is sequential.outcome


@settings(max_examples=100, deadline=None)
@given(chosen=st.lists(engines, min_size=1, max_size=10),
       workers=st.integers(min_value=1, max_value=6))
def test_property_every_item_accounted_for(chosen, workers):
    work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
    record = Orchestrator(invoker=empty_invoker, max_workers=workers).run_cycle(work)
    assert record.attempted_count + record.not_attempted_count == len(chosen)
    assert len(record.invocations) == len(chosen)


@settings(max_examples=60, deadline=None)
@given(chosen=st.lists(engines, min_size=1, max_size=8),
       workers=st.integers(min_value=2, max_value=6))
def test_property_failures_never_masked_under_concurrency(chosen, workers):
    work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
    orchestrator = Orchestrator(invoker=raising_invoker, max_workers=workers)
    orchestrator.run_cycle(work)
    surface = FailureSurface.over(orchestrator)
    assert surface.failed_count == len(chosen)
    assert surface.masked_cycles() == ()


class TestBoundExhaustionAcrossPhases:
    """The budget can run out exactly at a phase boundary."""

    def test_a_later_phase_is_refused_once_the_limit_is_reached(self):
        """remaining == 0 when the next phase begins."""
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4,
            bounds=CycleBounds(max_work_items=2),
        ).run_cycle(WorkSet(items=(
            item(0), item(1),
            item(2, Engine.PROBLEM_INTELLIGENCE),
            item(3, Engine.PATTERN_INTELLIGENCE),
        )))
        assert record.attempted_count == 2
        assert record.not_attempted_count == 2
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED

    def test_exhaustion_on_a_serialised_phase_boundary(self):
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4,
            bounds=CycleBounds(max_work_items=1),
        ).run_cycle(WorkSet(items=(
            item(0, Engine.PROBLEM_INTELLIGENCE),
            item(1, Engine.PATTERN_INTELLIGENCE),
            item(2, Engine.VALIDATION),
        )))
        assert record.attempted_count == 1
        assert record.not_attempted_count == 2

    def test_engines_with_failures_reported_under_concurrency(self):
        """T01.6.3 attribution still works on the parallel path."""
        def research_fails(work_item: WorkItem) -> InvocationResult:
            if work_item.engine is Engine.RESEARCH:
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orchestrator = Orchestrator(invoker=research_fails, max_workers=4)
        orchestrator.run_cycle(WorkSet(items=(
            item(0), item(1), item(2, Engine.PROBLEM_INTELLIGENCE)
        )))
        surface = FailureSurface.over(orchestrator)
        assert surface.engines_with_failures() == (Engine.RESEARCH,)


class TestEquivalentMutantGuards:
    """Two mutation survivors are provably equivalent; these pin the reasons.

    Recorded rather than hidden: a surviving mutant is either a test gap or an
    equivalent mutant, and the difference must be demonstrated, not asserted.
    """

    def test_a_serialised_phase_can_never_hold_more_than_one_item(self):
        """Why `phase.is_parallel and len(admitted) > 1` is equivalent to
        `len(admitted) > 1`: the serialised branch is unreachable, because
        ExecutionPhase refuses a multi-item serialised phase at construction.
        The redundant guard states the N-11 intent at the point of dispatch.
        """
        with pytest.raises(ConcurrencyError):
            ExecutionPhase(ConcurrencyClass.SERIALISED, (0, 1))
        for chosen in (
            (Engine.PROBLEM_INTELLIGENCE,) * 5,
            (Engine.RESEARCH, Engine.PROBLEM_INTELLIGENCE, Engine.VALIDATION),
        ):
            work = WorkSet(items=tuple(item(n, e) for n, e in enumerate(chosen)))
            for phase in work.concurrency_plan():
                if phase.concurrency_class is ConcurrencyClass.SERIALISED:
                    assert len(phase) == 1

    def test_worker_writeback_is_guarded(self):
        """Why removing the worker lock survives on CPython.

        dict assignment and list.extend are atomic under the GIL, so no test
        on this interpreter can observe the difference. The guard is retained
        deliberately: it is required for correctness on a free-threaded build,
        where neither operation is atomic. Its presence is asserted directly
        because its effect is unobservable here.
        """
        import inspect

        source = inspect.getsource(Orchestrator._run_parallel)
        assert "with guard:" in source
        assert "threading.Lock()" in source

    def test_no_result_is_lost_however_many_workers(self):
        """The property the guard protects, exercised as hard as possible."""
        for workers in (2, 8, 32):
            record = Orchestrator(
                invoker=empty_invoker, max_workers=workers
            ).run_cycle(WorkSet(items=tuple(item(n) for n in range(64))))
            assert len(record.invocations) == 64
            assert record.attempted_count == 64
            assert [r.input_ids[0] for r in record.invocations] == [
                f"s-{n}" for n in range(64)
            ]

    def test_no_failure_is_lost_however_many_workers(self):
        for workers in (2, 8, 32):
            store = FailureStore()
            record = Orchestrator(
                invoker=raising_invoker, failure_store=store,
                max_workers=workers,
            ).run_cycle(WorkSet(items=tuple(item(n) for n in range(48))))
            assert record.failed_count == 48
            assert len(record.failures) == 48
            assert len(store) == 48
