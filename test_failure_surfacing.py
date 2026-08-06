"""Contract tests for failure surfacing.

Task: T01.6.3

Architecture References:
- N-10   Failure records outside the object model; "every failure record
         identifies: the engine, the invocation, the inputs attempted, the
         configuration in force, the time, and the nature of the failure";
         a stage that produced nothing because it FAILED is distinguishable
         from one that produced nothing because it FOUND NOTHING
- N-17   Engine failure recorded, cycle continues, failure surfaced --
         never masked as completion
- N-18   Failure surfacing is P1 baseline capability
- N-8    Failed acceptance produces a failure record, never a silent
         rejection
- AD-04  Orchestration sequences but never judges
- v2 4.12 Named failure modes: partial-failure mishandling, starvation,
         duplicate invocation
- B-12   Failure records and orchestration state are separate surfaces
- Art.IV / Art.V  Failures never become Evidence, never enter lineage
- M-36   Failure-handling POLICY half OPEN -- no retry/skip/halt/compensate
- M-57   Observability OPEN (T09.1.2) -- no metrics, rates or thresholds
- N-4    Properties, never output equality

Acceptance criteria under test:
  AC1  Failed invocation distinguishable from empty result
  AC2  Failures do not silently halt the pipeline
"""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.configuration import ConfigurationError, FailureStore
from oip.enums import Engine, ObjectType
from oip.orchestration import (
    CycleBounds,
    CycleOutcome,
    CycleRecord,
    FailureMaskedError,
    FailureSurface,
    InvocationOutcome,
    InvocationRecord,
    InvocationResult,
    Orchestrator,
    OrchestrationError,
    ProcessingStateStore,
    WorkItem,
    WorkSet,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def item(n: int | str = 1, engine: Engine = Engine.RESEARCH) -> WorkItem:
    return WorkItem(engine, (f"src-{n}",), "cfg-v1")


def invocation(
    n: int | str = 1,
    engine: Engine = Engine.RESEARCH,
    outcome: InvocationOutcome = InvocationOutcome.EMPTY,
    produced: tuple[str, ...] = (),
) -> InvocationRecord:
    return InvocationRecord(
        engine, (f"src-{n}",), "cfg-v1", outcome, produced, "", T0, T0
    )


def cycle_record(
    cycle_id: int,
    invocations,
    outcome: CycleOutcome = CycleOutcome.COMPLETED,
    failures: tuple[FailureRecord, ...] = (),
) -> CycleRecord:
    invocations = tuple(invocations)
    return CycleRecord(
        cycle_id=cycle_id,
        outcome=outcome,
        bounds=CycleBounds(),
        invocations=invocations,
        failures=failures,
        planned_items=len(invocations),
        started_at=T0,
        ended_at=T0,
    )


def rule_failure(object_id: str = "EV-1") -> FailureRecord:
    return FailureRecord(
        object_id,
        ObjectType.EVIDENCE,
        (RuleResult("V1", RuleOutcome.FAIL, "attribute missing"),),
        T0,
        "cfg-v1",
    )


def empty_invoker(_item: WorkItem) -> InvocationResult:
    return InvocationResult.empty()


def raising_invoker(_item: WorkItem) -> InvocationResult:
    raise RuntimeError("engine down")


class HostileStore(FailureStore):
    """A failure store that cannot persist. [T01.6.3 regression]"""

    def record(self, failure):
        raise RuntimeError("store unavailable")


# ---------------------------------------------------------------------------
# AC1 -- failed invocation distinguishable from empty result
# ---------------------------------------------------------------------------

class TestFailedDistinguishableFromEmpty:
    """N-10: "This distinction is mandatory at every stage." """

    def test_failed_and_empty_never_overlap(self):
        surface = FailureSurface(cycles=(cycle_record(1, [
            invocation(1, outcome=InvocationOutcome.FAILED),
            invocation(2, outcome=InvocationOutcome.EMPTY),
        ], outcome=CycleOutcome.FAILED),))
        failed = {r.input_ids[0] for _, r in surface.failed_invocations()}
        empty = {r.input_ids[0] for _, r in surface.empty_invocations()}
        assert failed == {"src-1"}
        assert empty == {"src-2"}
        assert not failed & empty

    def test_counts_are_separate(self):
        surface = FailureSurface(cycles=(cycle_record(1, [
            invocation(1, outcome=InvocationOutcome.FAILED),
            invocation(2, outcome=InvocationOutcome.EMPTY),
            invocation(3, outcome=InvocationOutcome.EMPTY),
        ], outcome=CycleOutcome.FAILED),))
        assert surface.failed_count == 1
        assert surface.empty_count == 2

    def test_produced_nothing_is_the_union_without_collapsing_cause(self):
        surface = FailureSurface(cycles=(cycle_record(1, [
            invocation(1, outcome=InvocationOutcome.FAILED),
            invocation(2, outcome=InvocationOutcome.EMPTY),
        ], outcome=CycleOutcome.FAILED),))
        both = surface.produced_nothing()
        assert len(both) == 2
        assert {r.outcome for _, r in both} == {
            InvocationOutcome.FAILED,
            InvocationOutcome.EMPTY,
        }

    def test_an_empty_engine_never_registers_a_failure(self):
        orch = Orchestrator(invoker=empty_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        surface = FailureSurface.over(orch)
        assert surface.failed_count == 0
        assert surface.empty_count == 1
        assert surface.failure_free() is True

    def test_a_failing_engine_never_registers_as_empty(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        surface = FailureSurface.over(orch)
        assert surface.failed_count == 1
        assert surface.empty_count == 0

    def test_not_attempted_is_neither_failed_nor_empty(self):
        surface = FailureSurface(cycles=(cycle_record(1, [
            invocation(1, outcome=InvocationOutcome.NOT_ATTEMPTED),
        ]),))
        assert surface.failed_count == 0
        assert surface.empty_count == 0

    def test_produced_is_neither(self):
        surface = FailureSurface(cycles=(cycle_record(1, [
            invocation(1, outcome=InvocationOutcome.PRODUCED, produced=("o1",)),
        ]),))
        assert surface.failed_count == 0
        assert surface.empty_count == 0


# ---------------------------------------------------------------------------
# AC2 -- failures do not silently halt the pipeline
# ---------------------------------------------------------------------------

class TestFailuresDoNotHaltThePipeline:
    def test_cycle_continues_past_a_failure(self):
        seen: list[str] = []

        def flaky(work_item: WorkItem) -> InvocationResult:
            seen.append(work_item.input_ids[0])
            if work_item.input_ids[0] == "src-1":
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orch = Orchestrator(invoker=flaky)
        result = orch.run_cycle(WorkSet(items=(item(1), item(2), item(3))))
        assert seen == ["src-1", "src-2", "src-3"]
        assert result.attempted_count == 3

    def test_every_item_attempted_when_all_fail(self):
        orch = Orchestrator(invoker=raising_invoker)
        result = orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(10))))
        assert result.attempted_count == 10
        assert result.not_attempted_count == 0
        assert FailureSurface.over(orch).failed_count == 10

    def test_continued_past_failure_is_reported(self):
        def first_fails(work_item: WorkItem) -> InvocationResult:
            if work_item.input_ids[0] == "src-1":
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orch = Orchestrator(invoker=first_fails)
        orch.run_cycle(WorkSet(items=(item(1), item(2))))
        surface = FailureSurface.over(orch)
        assert len(surface.continued_past_failure()) == 1
        assert surface.halted_at_failure() == ()

    def test_failure_on_the_final_item_is_not_reported_as_a_halt(self):
        def last_fails(work_item: WorkItem) -> InvocationResult:
            if work_item.input_ids[0] == "src-2":
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orch = Orchestrator(invoker=last_fails)
        orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert FailureSurface.over(orch).halted_at_failure() == ()

    def test_an_engine_exception_never_escapes_to_the_caller(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))  # must not raise

    def test_failures_across_many_cycles_do_not_stop_operation(self):
        orch = Orchestrator(invoker=raising_invoker)
        for _ in range(20):
            orch.run_cycle(WorkSet(items=(item(1),)))
        assert orch.cycle_count == 20
        assert FailureSurface.over(orch).failed_count == 20


# ---------------------------------------------------------------------------
# Never masked as completion  [N-10, N-17]
# ---------------------------------------------------------------------------

class TestNeverMaskedAsCompletion:
    def test_real_orchestration_never_masks(self):
        orch = Orchestrator(invoker=raising_invoker)
        for _ in range(5):
            orch.run_cycle(WorkSet(items=(item(1), item(2))))
        surface = FailureSurface.over(orch)
        assert surface.masked_cycles() == ()
        assert surface.is_masked_as_completion() is False
        surface.assert_not_masked()

    def test_a_completed_cycle_hiding_a_failure_is_detected(self):
        surface = FailureSurface(cycles=(cycle_record(
            1,
            [invocation(1, outcome=InvocationOutcome.FAILED)],
            outcome=CycleOutcome.COMPLETED,
        ),))
        assert surface.is_masked_as_completion() is True
        assert len(surface.masked_cycles()) == 1

    def test_assert_not_masked_fails_closed(self):
        surface = FailureSurface(cycles=(cycle_record(
            1,
            [invocation(1, outcome=InvocationOutcome.FAILED)],
            outcome=CycleOutcome.COMPLETED,
        ),))
        with pytest.raises(FailureMaskedError):
            surface.assert_not_masked()

    def test_a_bounded_stop_with_failures_is_not_masking(self):
        """The T01.6.1 defect: the bound must not hide the failure."""
        orch = Orchestrator(
            invoker=raising_invoker, bounds=CycleBounds(max_work_items=2)
        )
        orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(5))))
        surface = FailureSurface.over(orch)
        cycle = orch.cycle(1)
        assert cycle.outcome is CycleOutcome.WORK_LIMIT_REACHED
        assert cycle.had_failure is True
        assert surface.masked_cycles() == ()
        assert len(surface.cycles_with_failures()) == 1
        assert surface.failed_count == 2

    def test_a_failed_outcome_is_not_masking(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert orch.cycle(1).outcome is CycleOutcome.FAILED
        assert FailureSurface.over(orch).masked_cycles() == ()

    def test_a_clean_cycle_is_not_flagged(self):
        orch = Orchestrator(invoker=empty_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        surface = FailureSurface.over(orch)
        assert surface.is_masked_as_completion() is False
        assert surface.cycles_with_failures() == ()
        surface.assert_not_masked()

    def test_every_failure_is_visible(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert FailureSurface.over(orch).every_failure_is_visible() is True


# ---------------------------------------------------------------------------
# N-10 attribution  [defect fix]
# ---------------------------------------------------------------------------

class TestN10Attribution:
    """N-10 names six identifications; three had no field at all."""

    def test_an_orchestrated_failure_identifies_all_six(self):
        failures = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=failures)
        orch.run_cycle(
            WorkSet(items=(WorkItem(Engine.VALIDATION, ("a", "b"), "cfg-9"),))
        )
        record = failures.all()[0]
        assert record.engine is Engine.VALIDATION          # the engine
        assert record.cycle_id == 1                        # the invocation
        assert record.invocation_index == 0
        assert record.input_ids == ("a", "b")              # inputs attempted
        assert record.engine_configuration_ref == "cfg-9"  # configuration
        assert record.recorded_at is not None              # the time
        assert "RuntimeError" in record.nature[0]          # the nature
        assert record.satisfies_n10_attribution is True

    def test_attempted_inputs_are_recoverable(self):
        """Previously unrecoverable: the whole point of the fix."""
        failures = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=failures)
        ids = tuple(f"ev-{n}" for n in range(20))
        orch.run_cycle(
            WorkSet(items=(WorkItem(Engine.FACT_EXTRACTION, ids, "cfg"),))
        )
        assert failures.all()[0].input_ids == ids

    def test_invocation_index_matches_position(self):
        failures = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=failures)
        orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(5))))
        assert [r.invocation_index for r in failures.for_cycle(1)] == [0, 1, 2, 3, 4]

    def test_cycle_id_separates_repeats_of_the_same_input(self):
        failures = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=failures)
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert [r.cycle_id for r in failures.all()] == [1, 2]

    def test_acceptance_failures_stay_honestly_unattributed(self):
        """Not an invocation: fabricating an identity would be dishonest."""
        record = rule_failure()
        assert record.engine is None
        assert record.is_attributable_to_invocation is False
        assert record.satisfies_n10_attribution is False

    def test_unattributed_records_are_surfaced_not_hidden(self):
        store = FailureStore()
        store.record(rule_failure())
        assert len(store.unattributed()) == 1

    def test_surface_reports_unattributed_failures(self):
        surface = FailureSurface(cycles=(
            cycle_record(1, [], failures=(rule_failure(),)),
        ))
        assert len(surface.unattributed_failures()) == 1

    def test_engines_with_failures_attributes_precisely(self):
        def research_fails(work_item: WorkItem) -> InvocationResult:
            if work_item.engine is Engine.RESEARCH:
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orch = Orchestrator(invoker=research_fails)
        orch.run_cycle(WorkSet(items=(
            item(1, Engine.RESEARCH), item(2, Engine.FEEDBACK)
        )))
        surface = FailureSurface.over(orch)
        assert surface.engines_with_failures() == (Engine.RESEARCH,)
        assert len(surface.failures_for_engine(Engine.RESEARCH)) == 1
        assert surface.failures_for_engine(Engine.FEEDBACK) == ()

    def test_backward_compatible_construction_still_works(self):
        record = FailureRecord(
            "EV-1", ObjectType.EVIDENCE,
            (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
        )
        assert record.engine is None
        assert record.input_ids == ()

    def test_bare_string_input_ids_refused(self):
        with pytest.raises(ValueError):
            FailureRecord(
                "EV-1", ObjectType.EVIDENCE,
                (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
                input_ids="abc",
            )

    def test_non_engine_refused(self):
        with pytest.raises(ValueError):
            FailureRecord(
                "EV-1", ObjectType.EVIDENCE,
                (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
                engine="Research",
            )

    def test_caller_mutation_does_not_leak_into_the_record(self):
        ids = ["a"]
        record = FailureRecord(
            "EV-1", ObjectType.EVIDENCE,
            (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
            input_ids=ids,
        )
        ids.append("ghost")
        assert record.input_ids == ("a",)


class TestFailureStoreQueries:
    def test_for_engine(self):
        store = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=store)
        orch.run_cycle(WorkSet(items=(
            item(1, Engine.RESEARCH), item(2, Engine.FEEDBACK)
        )))
        assert len(store.for_engine(Engine.RESEARCH)) == 1
        assert len(store.for_engine(Engine.FEEDBACK)) == 1

    def test_for_cycle(self):
        store = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=store)
        orch.run_cycle(WorkSet(items=(item(1), item(2))))
        orch.run_cycle(WorkSet(items=(item(3),)))
        assert len(store.for_cycle(1)) == 2
        assert len(store.for_cycle(2)) == 1
        assert store.for_cycle(99) == ()

    def test_for_engine_refuses_a_non_engine(self):
        with pytest.raises(ConfigurationError):
            FailureStore().for_engine("Research")

    def test_unattributed_empty_when_all_orchestrated(self):
        store = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=store)
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert store.unattributed() == ()


# ---------------------------------------------------------------------------
# Regression: hostile engine faults  [defect 1]
# ---------------------------------------------------------------------------

class TestHostileEngineFaults:
    """An exception whose __str__ raises must not destroy the cycle."""

    def test_exploding_str_does_not_lose_the_cycle(self):
        class Nasty(Exception):
            def __str__(self):
                raise RuntimeError("__str__ explodes")

        orch = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(Nasty()))
        result = orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert orch.cycle_count == 1
        assert result.attempted_count == 2
        assert result.failed_count == 2

    def test_exploding_str_still_names_the_exception_type(self):
        class Nasty(Exception):
            def __str__(self):
                raise RuntimeError("boom")

        orch = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(Nasty()))
        orch.run_cycle(WorkSet(items=(item(1),)))
        detail = FailureSurface.over(orch).failure_records()[0].nature[0]
        assert "Nasty" in detail
        assert "unrenderable" in detail

    def test_exploding_repr_is_survivable(self):
        class Vile(Exception):
            def __str__(self):
                raise ValueError("no str")

            def __repr__(self):
                raise ValueError("no repr")

        orch = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(Vile()))
        assert orch.run_cycle(WorkSet(items=(item(1),))).failed_count == 1

    def test_base_exception_is_recorded_as_a_failure(self):
        orch = Orchestrator(
            invoker=lambda i: (_ for _ in ()).throw(BaseException("low"))
        )
        assert orch.run_cycle(WorkSet(items=(item(1),))).failed_count == 1

    def test_memory_error_does_not_stop_the_cycle(self):
        def flaky(work_item: WorkItem) -> InvocationResult:
            if work_item.input_ids[0] == "src-1":
                raise MemoryError("out of memory")
            return InvocationResult.empty()

        orch = Orchestrator(invoker=flaky)
        assert orch.run_cycle(WorkSet(items=(item(1), item(2)))).attempted_count == 2

    @pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
    def test_control_signals_propagate_and_are_not_misattributed(self, signal):
        """Not engine failures: recording one would misattribute a shutdown."""
        orch = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(signal()))
        with pytest.raises(signal):
            orch.run_cycle(WorkSet(items=(item(1),)))

    def test_engine_returning_none_is_a_failure(self):
        orch = Orchestrator(invoker=lambda i: None)
        assert orch.run_cycle(WorkSet(items=(item(1),))).failed_count == 1

    def test_duck_typed_impostor_result_is_refused(self):
        class Fake:
            outcome = InvocationOutcome.PRODUCED
            produced_ids = ("o1",)
            detail = ""

        orch = Orchestrator(invoker=lambda i: Fake())
        assert orch.run_cycle(WorkSet(items=(item(1),))).failed_count == 1


# ---------------------------------------------------------------------------
# Regression: hostile failure store  [defect 2]
# ---------------------------------------------------------------------------

class TestHostileFailureStore:
    """A fault where failures are written must never hide the failures."""

    def test_store_fault_does_not_lose_the_cycle(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        result = orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert orch.cycle_count == 1
        assert result.attempted_count == 2
        assert result.failed_count == 2

    def test_store_fault_keeps_failures_surfaced(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        orch.run_cycle(WorkSet(items=(item(1),)))
        surface = FailureSurface.over(orch)
        assert surface.failed_count == 1
        assert surface.masked_cycles() == ()
        surface.assert_not_masked()

    def test_store_fault_is_itself_recorded(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        result = orch.run_cycle(WorkSet(items=(item(1),)))
        rule_ids = {rid for f in result.failures for rid in f.rule_ids}
        assert "FAILURE-STORE-UNAVAILABLE" in rule_ids
        assert "ENGINE-FAILURE" in rule_ids

    def test_store_fault_records_carry_attribution(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        result = orch.run_cycle(
            WorkSet(items=(WorkItem(Engine.VALIDATION, ("x",), "cfg-2"),))
        )
        fault = next(
            f for f in result.failures
            if "FAILURE-STORE-UNAVAILABLE" in f.rule_ids
        )
        assert fault.engine is Engine.VALIDATION
        assert fault.input_ids == ("x",)
        assert fault.satisfies_n10_attribution is True

    def test_store_faults_do_not_leak_between_cycles(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(2),)))
        assert len(orch.cycle(1).failures) == 2
        assert len(orch.cycle(2).failures) == 2

    def test_a_healthy_store_produces_no_fault_records(self):
        store = FailureStore()
        orch = Orchestrator(invoker=raising_invoker, failure_store=store)
        result = orch.run_cycle(WorkSet(items=(item(1),)))
        assert {rid for f in result.failures for rid in f.rule_ids} == {
            "ENGINE-FAILURE"
        }

    def test_intermittent_store_fault_records_only_the_failed_write(self):
        class Flaky(FailureStore):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def record(self, failure):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("transient")
                return super().record(failure)

        store = Flaky()
        orch = Orchestrator(invoker=raising_invoker, failure_store=store)
        result = orch.run_cycle(WorkSet(items=(item(1), item(2))))
        ids = [rid for f in result.failures for rid in f.rule_ids]
        assert ids.count("FAILURE-STORE-UNAVAILABLE") == 1
        assert ids.count("ENGINE-FAILURE") == 2
        assert len(store) == 1

    def test_store_fault_does_not_stop_the_cycle(self):
        seen: list[str] = []

        def track(work_item: WorkItem) -> InvocationResult:
            seen.append(work_item.input_ids[0])
            raise RuntimeError("boom")

        orch = Orchestrator(invoker=track, failure_store=HostileStore())
        orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(5))))
        assert seen == [f"src-{n}" for n in range(5)]

    @pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
    def test_control_signals_from_the_store_propagate(self, signal):
        class Signalling(FailureStore):
            def record(self, failure):
                raise signal()

        orch = Orchestrator(invoker=raising_invoker, failure_store=Signalling())
        with pytest.raises(signal):
            orch.run_cycle(WorkSet(items=(item(1),)))


# ---------------------------------------------------------------------------
# Detection separate from policy  [M-36 policy half OPEN]
# ---------------------------------------------------------------------------

class TestDetectionSeparateFromPolicy:
    def test_no_retry_skip_halt_or_compensate_vocabulary(self):
        banned = ("retry", "skip", "compensate", "recover", "suppress",
                  "resume", "rollback")
        names = [n for n in dir(FailureSurface) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)]

    def test_no_observability_vocabulary(self):
        """M-57 is OPEN and scheduled at T09.1.2, which this task blocks."""
        banned = ("rate", "threshold", "alert", "metric", "sla",
                  "healthy", "degraded")
        names = [n for n in dir(FailureSurface) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)]

    def test_no_severity_grading(self):
        banned = ("severity", "critical", "warning", "priority", "grade")
        names = [n for n in dir(FailureSurface) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)]

    def test_a_failing_engine_is_never_retried(self):
        calls: list[str] = []

        def counted(work_item: WorkItem) -> InvocationResult:
            calls.append(work_item.input_ids[0])
            raise RuntimeError("boom")

        Orchestrator(invoker=counted).run_cycle(WorkSet(items=(item(1),)))
        assert calls == ["src-1"], "an invocation was retried; M-36 policy is open"

    def test_summary_reports_counts_only(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        summary = FailureSurface.over(orch).summary()
        assert all(isinstance(v, int) for v in summary.values())
        assert not [k for k in summary if "rate" in k or "pct" in k]

    def test_consecutive_failures_is_a_fact_with_no_threshold(self):
        orch = Orchestrator(invoker=raising_invoker)
        for _ in range(3):
            orch.run_cycle(WorkSet(items=(item(1),)))
        assert FailureSurface.over(orch).consecutive_failures() == 3

    def test_consecutive_failures_resets_after_a_clean_cycle(self):
        calls = {"n": 0}

        def alternate(_item: WorkItem) -> InvocationResult:
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return InvocationResult.empty()

        orch = Orchestrator(invoker=alternate)
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert FailureSurface.over(orch).consecutive_failures() == 0

    def test_the_surface_mutates_nothing(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        before = (orch.cycle_count, orch.cycle(1).outcome,
                  len(orch.cycle(1).failures))
        surface = FailureSurface.over(orch)
        for accessor in (
            surface.failed_invocations, surface.empty_invocations,
            surface.masked_cycles, surface.continued_past_failure,
            surface.halted_at_failure, surface.summary,
            surface.unattributed_failures, surface.failure_records,
            surface.engines_with_failures, surface.consecutive_failures,
        ):
            accessor()
        assert (orch.cycle_count, orch.cycle(1).outcome,
                len(orch.cycle(1).failures)) == before


# ---------------------------------------------------------------------------
# Isolation and surface separation
# ---------------------------------------------------------------------------

class TestIsolation:
    def test_surface_never_participates_in_lineage(self):
        surface = FailureSurface()
        assert surface.participates_in_lineage is False
        assert surface.is_intelligence is False

    def test_failure_record_never_participates_in_lineage(self):
        assert rule_failure().participates_in_lineage is False

    def test_surface_holds_only_cycles(self):
        assert {f.name for f in dataclasses.fields(FailureSurface)} == {"cycles"}

    def test_failure_and_processing_surfaces_stay_separate(self):
        """B-12 kept these apart deliberately."""
        failures, processing = FailureStore(), ProcessingStateStore()
        orch = Orchestrator(
            invoker=raising_invoker,
            failure_store=failures,
            processing_store=processing,
        )
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert len(failures) == 1
        assert len(processing) == 1
        assert type(failures.all()[0]) is not type(processing.all()[0])

    def test_a_failure_appears_on_both_surfaces_without_masking(self):
        failures, processing = FailureStore(), ProcessingStateStore()
        orch = Orchestrator(
            invoker=raising_invoker,
            failure_store=failures,
            processing_store=processing,
        )
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert processing.all()[0].failed is True
        assert FailureSurface.over(orch).failed_count == 1


class TestFailsClosed:
    @pytest.mark.parametrize("bad", ["x", 5, None, object()])
    def test_surface_refuses_non_cycle_records(self, bad):
        with pytest.raises(OrchestrationError):
            FailureSurface(cycles=(bad,))

    def test_failures_for_engine_refuses_a_non_engine(self):
        with pytest.raises(OrchestrationError):
            FailureSurface().failures_for_engine("Research")

    def test_surface_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            FailureSurface().cycles = ()  # type: ignore[misc]

    def test_empty_surface_answers_without_raising(self):
        surface = FailureSurface()
        assert surface.failed_invocations() == ()
        assert surface.empty_invocations() == ()
        assert surface.masked_cycles() == ()
        assert surface.is_masked_as_completion() is False
        assert surface.consecutive_failures() == 0
        assert surface.failure_free() is True
        assert surface.engines_with_failures() == ()
        assert surface.every_failure_is_visible() is True
        surface.assert_not_masked()

    def test_over_accepts_any_iterable(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert FailureSurface.over(list(orch.cycles)).failed_count == 1
        assert FailureSurface.over(iter(orch.cycles)).failed_count == 1
        assert FailureSurface.over(orch).failed_count == 1

    def test_surface_is_a_snapshot_not_a_live_view(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        surface = FailureSurface.over(orch)
        orch.run_cycle(WorkSet(items=(item(2),)))
        assert surface.failed_count == 1
        assert FailureSurface.over(orch).failed_count == 2


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_clean_cycles_behave_as_before(self):
        orch = Orchestrator(invoker=lambda i: InvocationResult.produced("o1"))
        result = orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert result.outcome is CycleOutcome.COMPLETED
        assert result.produced_count == 2
        assert result.failures == ()

    def test_orchestrator_without_stores_still_surfaces_failures(self):
        orch = Orchestrator(invoker=raising_invoker)
        result = orch.run_cycle(WorkSet(items=(item(1),)))
        assert result.failed_count == 1
        assert len(result.failures) == 1

    def test_failed_cycles_still_reports(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert len(orch.failed_cycles()) == 1

    def test_bounded_stop_still_records_unattempted_work(self):
        orch = Orchestrator(
            invoker=raising_invoker, bounds=CycleBounds(max_work_items=2)
        )
        result = orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(6))))
        assert result.attempted_count == 2
        assert result.not_attempted_count == 4

    def test_processing_state_unaffected_by_a_hostile_failure_store(self):
        processing = ProcessingStateStore()
        orch = Orchestrator(
            invoker=raising_invoker,
            failure_store=HostileStore(),
            processing_store=processing,
        )
        orch.run_cycle(WorkSet(items=(item(1),)))
        assert len(processing) == 1


# ---------------------------------------------------------------------------
# Concurrency  [N-11]
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_shared_failure_store_stays_exact_under_contention(self):
        store = FailureStore()
        errors: list[Exception] = []

        def worker(k: int) -> None:
            try:
                orch = Orchestrator(invoker=raising_invoker, failure_store=store)
                for _ in range(10):
                    orch.run_cycle(WorkSet(items=(item(k),)))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert len(store) == 100
        assert store.unattributed() == ()

    def test_concurrent_surfaces_over_one_orchestrator_agree(self):
        orch = Orchestrator(invoker=raising_invoker)
        for _ in range(20):
            orch.run_cycle(WorkSet(items=(item(1),)))
        seen: list[int] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                seen.append(FailureSurface.over(orch).failed_count)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert set(seen) == {20}

    def test_concurrent_hostile_stores_do_not_cross_contaminate(self):
        counts: list[int] = []
        errors: list[Exception] = []

        def worker(k: int) -> None:
            try:
                orch = Orchestrator(
                    invoker=raising_invoker, failure_store=HostileStore()
                )
                orch.run_cycle(WorkSet(items=(item(k),)))
                counts.append(len(orch.cycle(1).failures))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert set(counts) == {2}


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality]
# ---------------------------------------------------------------------------

outcomes = st.sampled_from([
    InvocationOutcome.PRODUCED,
    InvocationOutcome.EMPTY,
    InvocationOutcome.FAILED,
    InvocationOutcome.NOT_ATTEMPTED,
])
engines = st.sampled_from(list(Engine))


@settings(max_examples=200, deadline=None)
@given(pattern=st.lists(outcomes, min_size=1, max_size=12))
def test_property_failed_and_empty_partition_correctly(pattern):
    invocations = [
        invocation(
            n,
            outcome=o,
            produced=("o1",) if o is InvocationOutcome.PRODUCED else (),
        )
        for n, o in enumerate(pattern)
    ]
    outcome = (
        CycleOutcome.FAILED
        if any(o is InvocationOutcome.FAILED for o in pattern)
        else CycleOutcome.COMPLETED
    )
    surface = FailureSurface(cycles=(cycle_record(1, invocations, outcome=outcome),))
    assert surface.failed_count == pattern.count(InvocationOutcome.FAILED)
    assert surface.empty_count == pattern.count(InvocationOutcome.EMPTY)
    failed = {id(r) for _, r in surface.failed_invocations()}
    empty = {id(r) for _, r in surface.empty_invocations()}
    assert not failed & empty


@settings(max_examples=200, deadline=None)
@given(failing=st.lists(st.booleans(), min_size=1, max_size=10))
def test_property_orchestration_never_masks(failing):
    """Whatever the failure pattern, no failure is hidden behind COMPLETED."""
    flags = iter(failing)

    def invoker(_item: WorkItem) -> InvocationResult:
        if next(flags):
            raise RuntimeError("boom")
        return InvocationResult.empty()

    orch = Orchestrator(invoker=invoker)
    orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(len(failing)))))
    surface = FailureSurface.over(orch)
    assert surface.masked_cycles() == ()
    surface.assert_not_masked()
    assert surface.failed_count == sum(failing)


@settings(max_examples=200, deadline=None)
@given(failing=st.lists(st.booleans(), min_size=1, max_size=10))
def test_property_every_item_is_always_attempted(failing):
    """AC2: failures never stop the pipeline, whatever the pattern."""
    flags = iter(failing)

    def invoker(_item: WorkItem) -> InvocationResult:
        if next(flags):
            raise RuntimeError("boom")
        return InvocationResult.empty()

    orch = Orchestrator(invoker=invoker)
    result = orch.run_cycle(
        WorkSet(items=tuple(item(n) for n in range(len(failing))))
    )
    assert result.attempted_count == len(failing)
    assert result.not_attempted_count == 0


@settings(max_examples=150, deadline=None)
@given(engine=engines, count=st.integers(min_value=1, max_value=6))
def test_property_orchestrated_failures_are_always_attributable(engine, count):
    store = FailureStore()
    orch = Orchestrator(invoker=raising_invoker, failure_store=store)
    orch.run_cycle(
        WorkSet(items=tuple(item(n, engine) for n in range(count)))
    )
    assert len(store) == count
    assert store.unattributed() == ()
    for record in store.all():
        assert record.engine is engine
        assert record.satisfies_n10_attribution is True


@settings(max_examples=150, deadline=None)
@given(cycles=st.integers(min_value=1, max_value=10))
def test_property_consecutive_failures_never_exceeds_cycle_count(cycles):
    orch = Orchestrator(invoker=raising_invoker)
    for _ in range(cycles):
        orch.run_cycle(WorkSet(items=(item(1),)))
    surface = FailureSurface.over(orch)
    assert surface.consecutive_failures() == cycles
    assert surface.consecutive_failures() <= len(surface.cycles)


@settings(max_examples=150, deadline=None)
@given(failing=st.lists(st.booleans(), min_size=1, max_size=8))
def test_property_summary_is_internally_consistent(failing):
    flags = iter(failing)

    def invoker(_item: WorkItem) -> InvocationResult:
        if next(flags):
            raise RuntimeError("boom")
        return InvocationResult.empty()

    orch = Orchestrator(invoker=invoker)
    orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(len(failing)))))
    surface = FailureSurface.over(orch)
    summary = surface.summary()
    assert summary["failed_invocations"] == surface.failed_count
    assert summary["empty_invocations"] == surface.empty_count
    assert summary["masked_cycles"] == 0
    assert summary["failed_invocations"] + summary["empty_invocations"] == len(failing)


class TestHaltedAtFailure:
    """A cycle that stopped at a failure with work left unreached.

    Reported, never prevented: this layer judges nothing. The point is that
    the shape is VISIBLE rather than silent. [AC2, AD-04]
    """

    def test_a_halt_with_unreached_work_is_reported(self):
        halted = CycleRecord(
            cycle_id=1,
            outcome=CycleOutcome.FAILED,
            bounds=CycleBounds(),
            invocations=(
                invocation(1, outcome=InvocationOutcome.FAILED),
                invocation(2, outcome=InvocationOutcome.NOT_ATTEMPTED),
                invocation(3, outcome=InvocationOutcome.NOT_ATTEMPTED),
            ),
            failures=(),
            planned_items=3,
            started_at=T0,
            ended_at=T0,
        )
        surface = FailureSurface(cycles=(halted,))
        assert len(surface.halted_at_failure()) == 1
        assert surface.continued_past_failure() == ()

    def test_a_failure_with_work_still_attempted_is_not_a_halt(self):
        cycle = cycle_record(
            1,
            [
                invocation(1, outcome=InvocationOutcome.FAILED),
                invocation(2, outcome=InvocationOutcome.EMPTY),
            ],
            outcome=CycleOutcome.FAILED,
        )
        surface = FailureSurface(cycles=(cycle,))
        assert surface.halted_at_failure() == ()
        assert len(surface.continued_past_failure()) == 1

    def test_real_orchestration_never_halts_at_a_failure(self):
        """N-17: the cycle continues. Nothing produces this shape."""
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=tuple(item(n) for n in range(5))))
        assert FailureSurface.over(orch).halted_at_failure() == ()

    def test_a_bounded_stop_after_a_failure_is_visible_as_a_halt_shape(self):
        """A bound reached right after a failure leaves work unreached."""
        orch = Orchestrator(
            invoker=raising_invoker, bounds=CycleBounds(max_work_items=1)
        )
        orch.run_cycle(WorkSet(items=(item(1), item(2), item(3))))
        surface = FailureSurface.over(orch)
        assert len(surface.halted_at_failure()) == 1
        assert surface.masked_cycles() == ()
        assert surface.failed_count == 1


class TestAttributionRequiresEveryPart:
    """N-10 names six identifications; a partial record does not satisfy it.

    Each case below omits exactly one, so no single field can be dropped
    from the check without a test noticing.
    """

    def _record(self, **overrides) -> FailureRecord:
        kwargs = dict(
            object_id="X",
            object_type=ObjectType.EVIDENCE,
            failed_rules=(RuleResult("R", RuleOutcome.FAIL, "detail"),),
            recorded_at=T0,
            engine_configuration_ref="cfg",
            engine=Engine.RESEARCH,
            cycle_id=1,
            invocation_index=0,
            input_ids=("a",),
        )
        kwargs.update(overrides)
        return FailureRecord(**kwargs)

    def test_a_complete_record_satisfies(self):
        assert self._record().satisfies_n10_attribution is True

    def test_missing_engine_does_not_satisfy(self):
        assert self._record(engine=None).satisfies_n10_attribution is False

    def test_missing_cycle_does_not_satisfy(self):
        assert self._record(cycle_id=None).satisfies_n10_attribution is False

    def test_missing_invocation_index_does_not_satisfy(self):
        assert self._record(invocation_index=None).satisfies_n10_attribution is False

    def test_missing_inputs_attempted_does_not_satisfy(self):
        """N-10 names "the inputs attempted" explicitly."""
        assert self._record(input_ids=()).satisfies_n10_attribution is False

    def test_missing_configuration_does_not_satisfy(self):
        assert self._record(
            engine_configuration_ref=""
        ).satisfies_n10_attribution is False

    def test_missing_nature_does_not_satisfy(self):
        assert self._record(failed_rules=()).satisfies_n10_attribution is False

    def test_a_partial_record_is_reported_as_unattributed(self):
        store = FailureStore()
        store.record(self._record(input_ids=()))
        assert len(store.unattributed()) == 1


class TestStoreFaultsDoNotAccumulate:
    """A per-cycle fault list must be reset, or cycle N reports cycle N-1's."""

    def test_each_cycle_reports_only_its_own_store_faults(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        for _ in range(4):
            orch.run_cycle(WorkSet(items=(item(1),)))
        for cycle in orch.cycles:
            faults = [
                f for f in cycle.failures
                if "FAILURE-STORE-UNAVAILABLE" in f.rule_ids
            ]
            assert len(faults) == 1, (
                f"cycle {cycle.cycle_id} carries {len(faults)} store faults; "
                f"faults are leaking across cycles"
            )

    def test_fault_records_name_their_own_cycle(self):
        orch = Orchestrator(invoker=raising_invoker, failure_store=HostileStore())
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(2),)))
        for cycle in orch.cycles:
            for failure in cycle.failures:
                assert failure.cycle_id == cycle.cycle_id

    def test_a_later_clean_store_leaves_no_residual_faults(self):
        class Recovering(FailureStore):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def record(self, failure):
                self.calls += 1
                if self.calls <= 1:
                    raise RuntimeError("transient")
                return super().record(failure)

        orch = Orchestrator(invoker=raising_invoker, failure_store=Recovering())
        orch.run_cycle(WorkSet(items=(item(1),)))
        orch.run_cycle(WorkSet(items=(item(2),)))
        assert any(
            "FAILURE-STORE-UNAVAILABLE" in f.rule_ids
            for f in orch.cycle(1).failures
        )
        assert not any(
            "FAILURE-STORE-UNAVAILABLE" in f.rule_ids
            for f in orch.cycle(2).failures
        )


class TestEveryFailureIsVisibleDetectsUnderReporting:
    def test_returns_false_when_a_failure_is_not_enumerable(self):
        """A cycle whose failed_count exceeds what the surface can list."""

        class Understating(CycleRecord):
            @property
            def failed_count(self) -> int:
                return super().failed_count + 1

        understating = Understating(
            cycle_id=1,
            outcome=CycleOutcome.FAILED,
            bounds=CycleBounds(),
            invocations=(invocation(1, outcome=InvocationOutcome.FAILED),),
            failures=(),
            planned_items=1,
            started_at=T0,
            ended_at=T0,
        )
        surface = FailureSurface(cycles=(understating,))
        assert surface.every_failure_is_visible() is False

    def test_returns_true_for_a_consistent_history(self):
        orch = Orchestrator(invoker=raising_invoker)
        orch.run_cycle(WorkSet(items=(item(1), item(2))))
        assert FailureSurface.over(orch).every_failure_is_visible() is True

    def test_a_stale_fault_from_an_aborted_cycle_does_not_leak_forward(self):
        """The per-cycle fault list is reset at cycle START, not only at end.

        A cycle interrupted by a control signal never reaches its end-of-cycle
        drain, so without the start-reset its recorded store fault would be
        attached to the NEXT cycle -- reporting a failure against inputs that
        cycle never touched. Misattribution is the mirror of masking.
        """
        class Hostile(FailureStore):
            def record(self, failure):
                raise RuntimeError("store unavailable")

        def invoker(work_item: WorkItem) -> InvocationResult:
            if work_item.input_ids[0] == "abort":
                raise KeyboardInterrupt()
            raise RuntimeError("engine boom")

        orch = Orchestrator(invoker=invoker, failure_store=Hostile())
        with pytest.raises(KeyboardInterrupt):
            orch.run_cycle(WorkSet(items=(
                WorkItem(Engine.RESEARCH, ("a",), "cfg"),
                WorkItem(Engine.RESEARCH, ("abort",), "cfg"),
            )))

        clean = orch.run_cycle(
            WorkSet(items=(WorkItem(Engine.RESEARCH, ("b",), "cfg"),))
        )
        faults = [
            f for f in clean.failures
            if "FAILURE-STORE-UNAVAILABLE" in f.rule_ids
        ]
        assert len(faults) == 1, "a stale store fault leaked into the next cycle"
        assert faults[0].input_ids == ("b",), (
            f"fault misattributed to inputs this cycle never touched: "
            f"{faults[0].input_ids}"
        )
