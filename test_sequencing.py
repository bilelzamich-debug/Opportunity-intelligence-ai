"""Contract tests for sequencing enforcement.

Task: T01.6.5

Architecture References:
- v2 4.12 Orchestration "enforce[s] stage ordering". Named failure mode:
         "Stage-order violation -- an engine runs on inputs that are not
         ready; pipeline integrity lost". Its input is "the existence and
         status of objects awaiting processing"; it depends on the
         Knowledge Store "to determine state"
- v2 5.5 Orchestration: "Read state only" against Store and Graph
- IOM 2.5 / 4.6  "status metadata only, never content"
- N-14   Direct-input table: the object type each engine consumes
- N-6    "The graph may lag the store" -- existence read from the STORE
- N-17   Directive control model; bounds; cycles serialised
- N-18   Sequencing enforcement is P1 baseline; part of the T01.8.1 gate
- N-11   Concurrency boundary preserved exactly [T01.6.4]
- N-10   Failure recorded/continued/surfaced; empty != failed
- AD-04  Orchestration sequences but never judges
- E-V1   Evidence is the root; derives_from empty -- Research has no input
- OQ-10  Stage skipping OPEN (scheduled P6) -- partial pipelines NOT rejected
- OQ-11  Backflow OPEN (scheduled T07.3.8) -- item order NOT policed
- C-02   Execution Record has no producing engine
- M-36   Failure-handling policy half OPEN -- no retry/skip/defer

Acceptance criteria under test:
  AC1  Pipeline order never violated
  AC2  Out-of-order invocation rejected
"""

from __future__ import annotations

import dataclasses
import itertools
import threading

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.configuration import FailureStore
from oip.enums import (
    ENGINE_INPUT_TYPE,
    ENGINE_STAGE,
    ROOT_ENGINES,
    Engine,
    ObjectStatus,
    ObjectType,
)
from oip.orchestration import (
    ConcurrencyBoundary,
    CycleBounds,
    CycleOutcome,
    FailureSurface,
    InvocationOutcome,
    InvocationResult,
    Orchestrator,
    ProcessingStateStore,
    SequencingCheck,
    SequencingError,
    SequencingGuard,
    SequencingViolation,
    WorkItem,
    WorkSet,
)

CONSUMING = tuple(ENGINE_INPUT_TYPE)


class FakeResolver:
    """Minimal state resolver: id -> type, plus optional status."""

    def __init__(self, mapping=None, statuses=None):
        self.map = dict(mapping or {})
        self.statuses = dict(statuses or {})
        self.reads: list[str] = []
        self._lock = threading.Lock()

    def resolve_type(self, object_id):
        with self._lock:
            self.reads.append(object_id)
            return self.map.get(object_id)

    def find(self, object_id):
        if object_id not in self.map:
            return None
        status = self.statuses.get(object_id, ObjectStatus.ACTIVE)
        return type("Stored", (), {"status": status})()


def item(engine: Engine, inputs=("x",), **kw) -> WorkItem:
    return WorkItem(engine, tuple(inputs), "cfg-v1", **kw)


def empty_invoker(_item: WorkItem) -> InvocationResult:
    return InvocationResult.empty()


def raising_invoker(_item: WorkItem) -> InvocationResult:
    raise RuntimeError("engine down")


# ---------------------------------------------------------------------------
# The N-14 input mapping
# ---------------------------------------------------------------------------

class TestInputMapping:
    def test_mapping_is_exactly_n14s_direct_input_table(self):
        assert ENGINE_INPUT_TYPE == {
            Engine.FACT_EXTRACTION: ObjectType.EVIDENCE,
            Engine.PROBLEM_INTELLIGENCE: ObjectType.FACT,
            Engine.PATTERN_INTELLIGENCE: ObjectType.PROBLEM,
            Engine.OPPORTUNITY_INTELLIGENCE: ObjectType.PATTERN,
            Engine.SOLUTION_INTELLIGENCE: ObjectType.OPPORTUNITY,
            Engine.VALIDATION: ObjectType.SOLUTION,
            Engine.FEEDBACK: ObjectType.EXECUTION_RECORD,
        }

    def test_research_is_the_only_root_engine(self):
        """Evidence is the pipeline root; derives_from empty. [E-V1, N-14]"""
        assert ROOT_ENGINES == frozenset({Engine.RESEARCH})
        assert Engine.RESEARCH not in ENGINE_INPUT_TYPE

    def test_orchestration_consumes_nothing(self):
        assert Engine.ORCHESTRATION not in ENGINE_INPUT_TYPE
        assert Engine.ORCHESTRATION not in ROOT_ENGINES

    def test_each_input_type_is_the_previous_stage(self):
        """Internal consistency with IOM 2.6."""
        for engine, input_type in ENGINE_INPUT_TYPE.items():
            assert input_type.stage == ENGINE_STAGE[engine] - 1

    def test_feedback_consumes_execution_records_despite_c02(self):
        """The dependency is expressible by type; the producer is not."""
        assert ENGINE_INPUT_TYPE[Engine.FEEDBACK] is ObjectType.EXECUTION_RECORD

    def test_every_pipeline_engine_is_covered(self):
        covered = set(ENGINE_INPUT_TYPE) | ROOT_ENGINES
        assert covered == set(ENGINE_STAGE)


# ---------------------------------------------------------------------------
# AC2 -- out-of-order invocation rejected
# ---------------------------------------------------------------------------

class TestOutOfOrderRejected:
    def test_absent_input_is_rejected(self):
        guard = SequencingGuard(FakeResolver())
        result = guard.check(item(Engine.FACT_EXTRACTION, ("EV-1",)))
        assert result.satisfied is False
        assert "does not exist" in result.detail

    def test_present_input_is_accepted(self):
        guard = SequencingGuard(FakeResolver({"EV-1": ObjectType.EVIDENCE}))
        assert guard.check(item(Engine.FACT_EXTRACTION, ("EV-1",))).satisfied

    def test_wrong_type_is_rejected(self):
        guard = SequencingGuard(FakeResolver({"PR-1": ObjectType.PROBLEM}))
        result = guard.check(item(Engine.FACT_EXTRACTION, ("PR-1",)))
        assert result.satisfied is False
        assert "consumes Evidence" in result.detail

    def test_partial_availability_is_rejected(self):
        guard = SequencingGuard(FakeResolver({"EV-1": ObjectType.EVIDENCE}))
        result = guard.check(item(Engine.FACT_EXTRACTION, ("EV-1", "EV-2")))
        assert result.satisfied is False
        assert [c.input_id for c in result.unsatisfied] == ["EV-2"]

    @pytest.mark.parametrize("engine", CONSUMING)
    def test_every_engine_accepts_its_own_input_type(self, engine):
        resolver = FakeResolver({"in": ENGINE_INPUT_TYPE[engine]})
        assert SequencingGuard(resolver).check(item(engine, ("in",))).satisfied

    @pytest.mark.parametrize("engine", CONSUMING)
    def test_every_engine_rejects_an_empty_store(self, engine):
        guard = SequencingGuard(FakeResolver())
        assert guard.check(item(engine, ("in",))).satisfied is False

    def test_the_full_engine_by_type_matrix_matches_n14(self):
        wrong = []
        for engine in CONSUMING:
            for object_type in ObjectType:
                resolver = FakeResolver({"in": object_type})
                got = SequencingGuard(resolver).check(
                    item(engine, ("in",))
                ).satisfied
                if got != (object_type is ENGINE_INPUT_TYPE[engine]):
                    wrong.append((engine, object_type, got))
        assert not wrong

    def test_research_needs_no_inputs(self):
        guard = SequencingGuard(FakeResolver())
        result = guard.check(item(Engine.RESEARCH, ("anything",)))
        assert result.satisfied is True
        assert result.requires_inputs is False
        assert result.inputs == ()

    def test_multi_input_requires_every_input(self):
        resolver = FakeResolver({"a": ObjectType.EVIDENCE,
                                 "b": ObjectType.EVIDENCE})
        guard = SequencingGuard(resolver)
        assert guard.check(item(Engine.FACT_EXTRACTION, ("a", "b"))).satisfied
        assert not guard.check(
            item(Engine.FACT_EXTRACTION, ("a", "b", "c"))
        ).satisfied

    def test_reasons_name_every_unsatisfied_input(self):
        guard = SequencingGuard(FakeResolver())
        result = guard.check(item(Engine.FACT_EXTRACTION, ("a", "b")))
        assert len(result.reasons) == 2
        assert all(r for r in result.reasons)

    def test_assert_sequenced_fails_closed(self):
        guard = SequencingGuard(FakeResolver())
        with pytest.raises(SequencingViolation):
            guard.assert_sequenced(item(Engine.FACT_EXTRACTION, ("EV-1",)))

    def test_assert_sequenced_passes_when_ready(self):
        guard = SequencingGuard(FakeResolver({"EV-1": ObjectType.EVIDENCE}))
        guard.assert_sequenced(item(Engine.FACT_EXTRACTION, ("EV-1",)))

    def test_is_sequenced_is_a_boolean_shorthand(self):
        guard = SequencingGuard(FakeResolver({"EV-1": ObjectType.EVIDENCE}))
        assert guard.is_sequenced(item(Engine.FACT_EXTRACTION, ("EV-1",)))
        assert not guard.is_sequenced(item(Engine.FACT_EXTRACTION, ("no",)))


class TestOrchestratedRejection:
    def test_an_unready_engine_is_never_invoked(self):
        ran: list[int] = []
        orchestrator = Orchestrator(
            invoker=lambda i: (ran.append(1), empty_invoker(i))[1],
            state_resolver=FakeResolver(),
        )
        orchestrator.run_cycle(
            WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),))
        )
        assert ran == []

    def test_rejection_is_recorded_with_its_own_outcome(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        record = orchestrator.run_cycle(
            WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),))
        )
        invocation = record.invocations[0]
        assert invocation.outcome is InvocationOutcome.REJECTED_OUT_OF_ORDER
        assert invocation.rejected is True
        assert invocation.attempted is False

    def test_rejection_carries_full_attribution(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        record = orchestrator.run_cycle(WorkSet(items=(
            WorkItem(Engine.VALIDATION, ("SO-1", "SO-2"), "cfg-v7"),
        )))
        invocation = record.invocations[0]
        assert invocation.engine is Engine.VALIDATION
        assert invocation.input_ids == ("SO-1", "SO-2")
        assert invocation.engine_configuration_ref == "cfg-v7"
        assert invocation.produced_ids == ()
        assert invocation.detail

    def test_cycle_reports_the_violation(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        record = orchestrator.run_cycle(
            WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),))
        )
        assert record.rejected_count == 1
        assert record.had_sequencing_violation is True
        assert len(record.rejected_invocations()) == 1

    def test_ready_and_unready_items_are_separated(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=resolver
        )
        record = orchestrator.run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("EV-1",)),
            item(Engine.FACT_EXTRACTION, ("GONE",)),
        )))
        assert record.attempted_count == 1
        assert record.rejected_count == 1

    def test_engines_invoked_excludes_rejected_engines(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        record = orchestrator.run_cycle(WorkSet(items=(
            item(Engine.RESEARCH, ("s",)),
            item(Engine.FACT_EXTRACTION, ("m",)),
        )))
        assert record.engines_invoked == (Engine.RESEARCH,)

    def test_produced_count_unaffected_by_rejections(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        orchestrator = Orchestrator(
            invoker=lambda i: InvocationResult.produced("o1"),
            state_resolver=resolver,
        )
        record = orchestrator.run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("EV-1",)),
            item(Engine.FACT_EXTRACTION, ("GONE",)),
        )))
        assert record.produced_count == 1


# ---------------------------------------------------------------------------
# AC1 -- pipeline order never violated
# ---------------------------------------------------------------------------

class TestPipelineOrderNeverViolated:
    def test_no_execution_path_bypasses_the_guard_sequentially(self):
        ran: list[int] = []
        Orchestrator(
            invoker=lambda i: (ran.append(1), empty_invoker(i))[1],
            max_workers=1, state_resolver=FakeResolver(),
        ).run_cycle(WorkSet(items=tuple(
            item(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(6)
        )))
        assert ran == []

    def test_no_execution_path_bypasses_the_guard_in_parallel(self):
        ran: list[int] = []
        guard = threading.Lock()

        def track(work_item: WorkItem) -> InvocationResult:
            with guard:
                ran.append(1)
            return InvocationResult.empty()

        Orchestrator(
            invoker=track, max_workers=8, state_resolver=FakeResolver()
        ).run_cycle(WorkSet(items=tuple(
            item(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(20)
        )))
        assert ran == []

    def test_no_execution_path_bypasses_the_guard_on_serialised_stages(self):
        ran: list[int] = []
        Orchestrator(
            invoker=lambda i: (ran.append(1), empty_invoker(i))[1],
            max_workers=4, state_resolver=FakeResolver(),
        ).run_cycle(WorkSet(items=tuple(
            item(Engine.PATTERN_INTELLIGENCE, (f"m{n}",)) for n in range(5)
        )))
        assert ran == []

    def test_a_full_valid_chain_runs(self):
        resolver = FakeResolver({
            "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
            "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
            "OP": ObjectType.OPPORTUNITY, "SO": ObjectType.SOLUTION,
            "XR": ObjectType.EXECUTION_RECORD,
        })
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=resolver
        ).run_cycle(WorkSet(items=(
            item(Engine.RESEARCH, ("src",)),
            item(Engine.FACT_EXTRACTION, ("EV",)),
            item(Engine.PROBLEM_INTELLIGENCE, ("FA",)),
            item(Engine.PATTERN_INTELLIGENCE, ("PR",)),
            item(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",)),
            item(Engine.SOLUTION_INTELLIGENCE, ("OP",)),
            item(Engine.VALIDATION, ("SO",)),
            item(Engine.FEEDBACK, ("XR",)),
        )))
        assert record.attempted_count == 8
        assert record.rejected_count == 0

    def test_only_the_unready_stages_of_a_chain_are_rejected(self):
        resolver = FakeResolver({"EV": ObjectType.EVIDENCE,
                                 "PR": ObjectType.PROBLEM})
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=resolver
        ).run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("EV",)),
            item(Engine.PROBLEM_INTELLIGENCE, ("FA-missing",)),
            item(Engine.PATTERN_INTELLIGENCE, ("PR",)),
            item(Engine.OPPORTUNITY_INTELLIGENCE, ("PT-missing",)),
        )))
        assert [r.rejected for r in record.invocations] == [
            False, True, False, True
        ]


# ---------------------------------------------------------------------------
# Open questions NOT closed by implementation
# ---------------------------------------------------------------------------

class TestOpenQuestionsNotClosed:
    """OQ-10 (P6) and OQ-11 (T07.3.8) must not be pre-empted here."""

    @pytest.mark.parametrize("engine", CONSUMING)
    def test_a_stage_skipping_work_set_is_not_rejected(self, engine):
        """OQ-10 is OPEN and scheduled at P6."""
        resolver = FakeResolver({"in": ENGINE_INPUT_TYPE[engine]})
        work = WorkSet(items=(item(engine, ("in",)),))
        assert SequencingGuard(resolver).violations(work) == ()

    def test_a_reverse_ordered_pipeline_is_not_rejected(self):
        """OQ-11 is OPEN and scheduled at T07.3.8."""
        resolver = FakeResolver({
            "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
            "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
            "OP": ObjectType.OPPORTUNITY, "SO": ObjectType.SOLUTION,
            "XR": ObjectType.EXECUTION_RECORD,
        })
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=resolver
        ).run_cycle(WorkSet(items=(
            item(Engine.FEEDBACK, ("XR",)),
            item(Engine.VALIDATION, ("SO",)),
            item(Engine.SOLUTION_INTELLIGENCE, ("OP",)),
            item(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",)),
            item(Engine.PATTERN_INTELLIGENCE, ("PR",)),
            item(Engine.PROBLEM_INTELLIGENCE, ("FA",)),
            item(Engine.FACT_EXTRACTION, ("EV",)),
        )))
        assert record.attempted_count == 7
        assert record.rejected_count == 0

    def test_every_ordering_of_a_valid_chain_is_accepted(self):
        resolver = FakeResolver({
            "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
            "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
        })
        items = [
            item(Engine.FACT_EXTRACTION, ("EV",)),
            item(Engine.PROBLEM_INTELLIGENCE, ("FA",)),
            item(Engine.PATTERN_INTELLIGENCE, ("PR",)),
            item(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",)),
        ]
        guard = SequencingGuard(resolver)
        for permutation in itertools.permutations(items):
            assert guard.violations(WorkSet(items=permutation)) == ()

    def test_a_duplicated_stage_is_not_rejected(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE,
                                 "EV-2": ObjectType.EVIDENCE})
        work = WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),
                              item(Engine.FACT_EXTRACTION, ("EV-2",))))
        assert SequencingGuard(resolver).violations(work) == ()

    def test_a_partial_pipeline_is_not_rejected(self):
        resolver = FakeResolver({"SO-1": ObjectType.SOLUTION})
        work = WorkSet(items=(item(Engine.VALIDATION, ("SO-1",)),))
        assert SequencingGuard(resolver).violations(work) == ()

    def test_no_stage_skip_or_backflow_vocabulary_exists(self):
        banned = ("skip", "backflow", "reverse", "reorder", "sort",
                  "infer", "insert", "synthes", "retry", "defer")
        names = [n for n in dir(SequencingGuard) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)]


class TestStatusReportedNotRequired:
    """A1: the criterion says inputs must EXIST. No status is imposed."""

    @pytest.mark.parametrize("status", list(ObjectStatus))
    def test_any_status_satisfies_existence(self, status):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE},
                                {"EV-1": status})
        assert SequencingGuard(resolver).check(
            item(Engine.FACT_EXTRACTION, ("EV-1",))
        ).satisfied

    def test_status_is_reported_for_the_caller(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE},
                                {"EV-1": ObjectStatus.RETRACTED})
        result = SequencingGuard(resolver).check(
            item(Engine.FACT_EXTRACTION, ("EV-1",))
        )
        assert result.input_statuses == (("EV-1", ObjectStatus.RETRACTED),)

    def test_a_resolver_without_find_degrades_gracefully(self):
        class Bare:
            def resolve_type(self, object_id):
                return ObjectType.EVIDENCE

        result = SequencingGuard(Bare()).check(
            item(Engine.FACT_EXTRACTION, ("EV-1",))
        )
        assert result.satisfied
        assert result.input_statuses == (("EV-1", None),)


# ---------------------------------------------------------------------------
# Never reorders, infers or inserts
# ---------------------------------------------------------------------------

class TestNeverReordersOrInfers:
    def test_a_rejection_does_not_move_other_items(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=resolver
        ).run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("MISSING",)),
            item(Engine.FACT_EXTRACTION, ("EV-1",)),
            item(Engine.RESEARCH, ("s",)),
        )))
        assert [r.input_ids[0] for r in record.invocations] == [
            "MISSING", "EV-1", "s"
        ]

    def test_no_implicit_work_item_is_inserted(self):
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        ).run_cycle(
            WorkSet(items=(item(Engine.PATTERN_INTELLIGENCE, ("PR-1",)),))
        )
        assert len(record.invocations) == 1
        assert record.planned_items == 1

    def test_no_missing_stage_is_inferred(self):
        seen: list[Engine] = []
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        Orchestrator(
            invoker=lambda i: (seen.append(i.engine), empty_invoker(i))[1],
            state_resolver=resolver,
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),)))
        assert seen == [Engine.FACT_EXTRACTION]

    def test_the_guard_does_not_predict_future_writes(self):
        """An input a later item would create is still absent now. [A4]"""
        resolver = FakeResolver()

        def producing(work_item: WorkItem) -> InvocationResult:
            if work_item.engine is Engine.RESEARCH:
                resolver.map["EV-late"] = ObjectType.EVIDENCE
            return InvocationResult.empty()

        record = Orchestrator(
            invoker=producing, state_resolver=resolver
        ).run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("EV-late",)),
            item(Engine.RESEARCH, ("src",)),
        )))
        assert record.invocations[0].rejected is True
        assert record.invocations[1].attempted is True

    def test_committed_state_from_an_earlier_item_is_observed(self):
        """Observation of what exists, never inference. [A4]"""
        resolver = FakeResolver()

        def producing(work_item: WorkItem) -> InvocationResult:
            if work_item.engine is Engine.RESEARCH:
                resolver.map["EV-new"] = ObjectType.EVIDENCE
                return InvocationResult.produced("EV-new")
            return InvocationResult.empty()

        record = Orchestrator(
            invoker=producing, state_resolver=resolver
        ).run_cycle(WorkSet(items=(
            item(Engine.RESEARCH, ("src",)),
            item(Engine.FACT_EXTRACTION, ("EV-new",)),
        )))
        assert record.rejected_count == 0
        assert record.attempted_count == 2


# ---------------------------------------------------------------------------
# A rejection is not an engine failure  [N-10]
# ---------------------------------------------------------------------------

class TestRejectionIsNotFailure:
    def test_no_failure_record_is_created(self):
        failures = FailureStore()
        record = Orchestrator(
            invoker=empty_invoker, failure_store=failures,
            state_resolver=FakeResolver(),
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),)))
        assert record.rejected_count == 1
        assert record.failed_count == 0
        assert len(failures) == 0

    def test_a_rejection_is_not_an_empty_result(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        orchestrator.run_cycle(
            WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),))
        )
        surface = FailureSurface.over(orchestrator)
        assert surface.failed_count == 0
        assert surface.empty_count == 0

    def test_real_failures_still_recorded_alongside_rejections(self):
        failures = FailureStore()
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        record = Orchestrator(
            invoker=raising_invoker, failure_store=failures,
            state_resolver=resolver,
        ).run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("EV-1",)),
            item(Engine.FACT_EXTRACTION, ("MISSING",)),
        )))
        assert record.failed_count == 1
        assert record.rejected_count == 1
        assert len(failures) == 1

    def test_a_rejection_alone_does_not_make_a_cycle_fail(self):
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("m",)),)))
        assert record.outcome is CycleOutcome.COMPLETED
        assert record.had_failure is False
        assert record.had_sequencing_violation is True

    def test_a_rejection_never_participates_in_lineage(self):
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("m",)),)))
        assert record.invocations[0].participates_in_lineage is False

    def test_failures_still_never_masked(self):
        resolver = FakeResolver({"EV": ObjectType.EVIDENCE})
        orchestrator = Orchestrator(
            invoker=raising_invoker, state_resolver=resolver, max_workers=4
        )
        for _ in range(4):
            orchestrator.run_cycle(WorkSet(items=tuple(
                item(Engine.FACT_EXTRACTION, ("EV",)) for _ in range(3)
            )))
        surface = FailureSurface.over(orchestrator)
        assert surface.failed_count == 12
        assert surface.masked_cycles() == ()
        surface.assert_not_masked()


class TestRejectionIsNotProcessing:
    """T01.6.2: an item no engine ran for was not processed."""

    def test_a_rejected_item_is_not_recorded_as_processed(self):
        processing = ProcessingStateStore()
        Orchestrator(
            invoker=empty_invoker, processing_store=processing,
            state_resolver=FakeResolver(),
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),)))
        assert len(processing) == 0
        assert not processing.has_processed(Engine.FACT_EXTRACTION, "EV-1")

    def test_only_what_ran_is_recorded(self):
        processing = ProcessingStateStore()
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        Orchestrator(
            invoker=empty_invoker, processing_store=processing,
            state_resolver=resolver,
        ).run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("EV-1",)),
            item(Engine.FACT_EXTRACTION, ("MISSING",)),
        )))
        assert len(processing) == 1
        assert processing.has_processed(Engine.FACT_EXTRACTION, "EV-1")

    def test_idempotence_detection_still_works(self):
        processing = ProcessingStateStore()
        resolver = FakeResolver({"EV": ObjectType.EVIDENCE})
        orchestrator = Orchestrator(
            invoker=empty_invoker, processing_store=processing,
            state_resolver=resolver,
        )
        work = WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV",)),
                              item(Engine.FACT_EXTRACTION, ("GONE",))))
        orchestrator.run_cycle(work)
        orchestrator.run_cycle(work)
        assert processing.attempt_count(Engine.FACT_EXTRACTION, "EV") == 2
        assert not processing.has_processed(Engine.FACT_EXTRACTION, "GONE")


# ---------------------------------------------------------------------------
# Reads state only  [v2 5.5, IOM 2.5]
# ---------------------------------------------------------------------------

class TestReadsStateOnly:
    def test_only_the_declared_inputs_are_read(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        SequencingGuard(resolver).check(
            item(Engine.FACT_EXTRACTION, ("EV-1",))
        )
        assert resolver.reads == ["EV-1"]

    def test_no_content_accessor_is_ever_called(self):
        class Trap:
            def resolve_type(self, object_id):
                return ObjectType.EVIDENCE

            def get(self, object_id):
                raise AssertionError("content was read")

            def get_evidence(self, object_id):
                raise AssertionError("content was read")

        SequencingGuard(Trap()).check(item(Engine.FACT_EXTRACTION, ("EV-1",)))

    def test_the_guard_never_mutates_a_real_store(self):
        from oip.store import KnowledgeStore

        store = KnowledgeStore()
        SequencingGuard(store).check(item(Engine.FACT_EXTRACTION, ("nope",)))
        assert len(store) == 0

    def test_it_works_against_a_real_knowledge_store(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore

        from conftest import write_evidence

        store = KnowledgeStore()
        evidence_id = write_evidence(store, IdentityAllocator()).object_id
        guard = SequencingGuard(store)
        assert guard.check(item(Engine.FACT_EXTRACTION, (evidence_id,))).satisfied
        assert not guard.check(
            item(Engine.FACT_EXTRACTION, ("EV-nope",))
        ).satisfied
        assert not guard.check(
            item(Engine.PROBLEM_INTELLIGENCE, (evidence_id,))
        ).satisfied

    def test_the_guard_is_frozen(self):
        guard = SequencingGuard(FakeResolver())
        with pytest.raises(dataclasses.FrozenInstanceError):
            guard.resolver = None  # type: ignore[misc]

    def test_the_guard_is_not_lineage(self):
        assert SequencingGuard(FakeResolver()).participates_in_lineage is False


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------

class TestFailsClosed:
    @pytest.mark.parametrize("bad", [object(), None, "store", 5])
    def test_a_resolver_without_resolve_type_is_refused(self, bad):
        with pytest.raises(SequencingError):
            SequencingGuard(bad)

    @pytest.mark.parametrize("bad", ["x", None, 5])
    def test_check_refuses_a_non_work_item(self, bad):
        with pytest.raises(SequencingError):
            SequencingGuard(FakeResolver()).check(bad)

    @pytest.mark.parametrize("bad", ["x", None, 5])
    def test_report_refuses_a_non_work_set(self, bad):
        with pytest.raises(SequencingError):
            SequencingGuard(FakeResolver()).report(bad)

    def test_an_engine_with_no_input_mapping_fails_closed(self):
        with pytest.raises(SequencingError):
            SequencingGuard(FakeResolver()).check(item(Engine.ORCHESTRATION))

    def test_a_non_object_type_return_is_treated_as_absent(self):
        class Weird:
            def resolve_type(self, object_id):
                return "Evidence"

        assert not SequencingGuard(Weird()).check(
            item(Engine.FACT_EXTRACTION, ("a",))
        ).satisfied

    def test_a_raising_resolver_does_not_lose_the_cycle(self):
        """Regression: the resolver fault used to destroy the whole cycle."""
        class Hostile:
            def resolve_type(self, object_id):
                raise RuntimeError("store down")

        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=Hostile()
        )
        record = orchestrator.run_cycle(WorkSet(items=(
            item(Engine.FACT_EXTRACTION, ("a",)),
            item(Engine.FACT_EXTRACTION, ("b",)),
        )))
        assert orchestrator.cycle_count == 1
        assert record.rejected_count == 2
        assert record.failed_count == 0

    def test_a_raising_resolver_fails_closed(self):
        ran: list[int] = []

        class Hostile:
            def resolve_type(self, object_id):
                raise RuntimeError("down")

        Orchestrator(
            invoker=lambda i: (ran.append(1), empty_invoker(i))[1],
            state_resolver=Hostile(),
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("a",)),)))
        assert ran == [], "an engine ran despite an unanswerable check"

    def test_a_hostile_exception_message_is_still_rendered(self):
        class Nasty(Exception):
            def __str__(self):
                raise RuntimeError("no str")

        class Hostile:
            def resolve_type(self, object_id):
                raise Nasty()

        record = Orchestrator(
            invoker=empty_invoker, state_resolver=Hostile()
        ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("a",)),)))
        assert record.rejected_count == 1
        assert "Nasty" in record.invocations[0].detail

    @pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
    def test_control_signals_from_the_resolver_propagate(self, signal):
        class Signalling:
            def resolve_type(self, object_id):
                raise signal()

        with pytest.raises(signal):
            Orchestrator(
                invoker=empty_invoker, state_resolver=Signalling()
            ).run_cycle(WorkSet(items=(item(Engine.FACT_EXTRACTION, ("a",)),)))


# ---------------------------------------------------------------------------
# N-11 / N-17 guarantees preserved
# ---------------------------------------------------------------------------

class TestOrchestrationGuaranteesPreserved:
    def test_the_n11_barrier_still_holds(self):
        resolver = FakeResolver(
            {f"EV{n}": ObjectType.EVIDENCE for n in range(6)}
            | {"PR": ObjectType.PROBLEM}
        )
        record = Orchestrator(
            invoker=empty_invoker, max_workers=4, state_resolver=resolver
        ).run_cycle(WorkSet(items=tuple(
            [item(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(3)]
            + [item(Engine.PATTERN_INTELLIGENCE, ("PR",))]
            + [item(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(3, 6)]
        )))
        ConcurrencyBoundary(record).assert_holds()
        assert record.attempted_count == 7

    def test_rejected_items_count_against_the_work_bound(self):
        record = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver(),
            bounds=CycleBounds(max_work_items=3),
        ).run_cycle(WorkSet(items=tuple(
            item(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(10)
        )))
        assert record.rejected_count == 3
        assert record.outcome is CycleOutcome.WORK_LIMIT_REACHED

    def test_cycles_remain_serialised_and_monotonic(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver(), max_workers=4
        )
        for _ in range(5):
            orchestrator.run_cycle(
                WorkSet(items=(item(Engine.RESEARCH, ("s",)),))
            )
        assert [c.cycle_id for c in orchestrator.cycles] == [1, 2, 3, 4, 5]

    def test_every_cycle_still_terminates(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        record = orchestrator.run_cycle(
            WorkSet(items=(item(Engine.FACT_EXTRACTION, ("m",)),))
        )
        assert record.terminated is True

    def test_sequential_and_parallel_agree_exactly(self):
        resolver = FakeResolver({"EV": ObjectType.EVIDENCE})
        work = WorkSet(items=tuple(
            [item(Engine.FACT_EXTRACTION, ("EV",)),
             item(Engine.FACT_EXTRACTION, ("GONE",))] * 5
        ))
        sequential = Orchestrator(
            invoker=empty_invoker, max_workers=1, state_resolver=resolver
        ).run_cycle(work)
        parallel = Orchestrator(
            invoker=empty_invoker, max_workers=5, state_resolver=resolver
        ).run_cycle(work)
        assert [r.outcome for r in parallel.invocations] == [
            r.outcome for r in sequential.invocations
        ]
        assert parallel.rejected_count == sequential.rejected_count


class TestConcurrency:
    def test_the_guard_is_safe_under_concurrent_use(self):
        resolver = FakeResolver(
            {f"EV{n}": ObjectType.EVIDENCE for n in range(50)}
        )
        guard = SequencingGuard(resolver)
        results: list[bool] = []
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            try:
                outcome = all(
                    guard.check(
                        item(Engine.FACT_EXTRACTION, (f"EV{n}",))
                    ).satisfied
                    for n in range(50)
                )
                with lock:
                    results.append(outcome)
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert results == [True] * 8

    def test_concurrent_cycles_with_a_shared_resolver_stay_exact(self):
        resolver = FakeResolver(
            {f"EV-{n}": ObjectType.EVIDENCE for n in range(25)}
        )
        counts: list[tuple[int, int]] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                record = Orchestrator(
                    invoker=empty_invoker, max_workers=4,
                    state_resolver=resolver,
                ).run_cycle(WorkSet(items=tuple(
                    [item(Engine.FACT_EXTRACTION, (f"EV-{n}",))
                     for n in range(25)]
                    + [item(Engine.FACT_EXTRACTION, (f"NOPE-{n}",))
                       for n in range(5)]
                )))
                counts.append((record.attempted_count, record.rejected_count))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert set(counts) == {(25, 5)}

    def test_a_resolver_fault_in_a_parallel_phase_is_contained(self):
        class Hostile:
            def resolve_type(self, object_id):
                raise RuntimeError("down")

        record = Orchestrator(
            invoker=empty_invoker, max_workers=6, state_resolver=Hostile()
        ).run_cycle(WorkSet(items=tuple(
            item(Engine.FACT_EXTRACTION, (f"a{n}",)) for n in range(12)
        )))
        assert record.rejected_count == 12
        assert [r.input_ids[0] for r in record.invocations] == [
            f"a{n}" for n in range(12)
        ]


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    def test_no_resolver_means_no_checking(self):
        orchestrator = Orchestrator(invoker=empty_invoker)
        assert orchestrator.state_resolver is None
        record = orchestrator.run_cycle(
            WorkSet(items=(item(Engine.PATTERN_INTELLIGENCE, ("PR-9",)),))
        )
        assert record.attempted_count == 1
        assert record.rejected_count == 0

    def test_field_order_preserved_and_resolver_appended(self):
        import inspect

        params = list(inspect.signature(Orchestrator).parameters)
        assert params[:5] == [
            "invoker", "bounds", "failure_store", "processing_store", "clock"
        ]
        assert params[-1] == "state_resolver"

    def test_invocation_outcome_gained_exactly_one_member(self):
        assert len(list(InvocationOutcome)) == 5
        assert InvocationOutcome.REJECTED_OUT_OF_ORDER.value == (
            "REJECTED_OUT_OF_ORDER"
        )

    def test_prior_public_names_intact(self):
        import oip.orchestration as module

        for name in (
            "CycleBounds", "WorkItem", "WorkSet", "InvocationResult",
            "Orchestrator", "CycleRecord", "FailureSurface",
            "ProcessingStateStore", "ConcurrencyBoundary", "ExecutionPhase",
            "ConcurrencyClass", "FailureMaskedError", "ConcurrencyViolation",
        ):
            assert hasattr(module, name), name

    def test_orchestration_still_produces_no_intelligence_objects(self):
        orchestrator = Orchestrator(
            invoker=empty_invoker, state_resolver=FakeResolver()
        )
        orchestrator.run_cycle(WorkSet(items=(item(Engine.RESEARCH, ("s",)),)))
        assert orchestrator.produces_intelligence_objects is False


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality]
# ---------------------------------------------------------------------------

consuming = st.sampled_from(CONSUMING)
types = st.sampled_from(list(ObjectType))


@settings(max_examples=200, deadline=None)
@given(engine=consuming, object_type=types)
def test_property_acceptance_iff_type_matches_n14(engine, object_type):
    resolver = FakeResolver({"in": object_type})
    satisfied = SequencingGuard(resolver).check(
        item(engine, ("in",))
    ).satisfied
    assert satisfied == (object_type is ENGINE_INPUT_TYPE[engine])


@settings(max_examples=200, deadline=None)
@given(engine=consuming, count=st.integers(min_value=1, max_value=6))
def test_property_an_empty_store_always_rejects(engine, count):
    guard = SequencingGuard(FakeResolver())
    result = guard.check(item(engine, tuple(f"in{n}" for n in range(count))))
    assert result.satisfied is False
    assert len(result.unsatisfied) == count


@settings(max_examples=200, deadline=None)
@given(
    present=st.lists(st.integers(min_value=0, max_value=7), unique=True,
                     max_size=8),
    total=st.integers(min_value=1, max_value=8),
)
def test_property_satisfied_iff_every_input_present(present, total):
    ids = [f"in{n}" for n in range(total)]
    resolver = FakeResolver(
        {f"in{n}": ObjectType.EVIDENCE for n in present if n < total}
    )
    result = SequencingGuard(resolver).check(
        item(Engine.FACT_EXTRACTION, tuple(ids))
    )
    expected = all(n in present for n in range(total))
    assert result.satisfied == expected


@settings(max_examples=150, deadline=None)
@given(engines=st.lists(consuming, min_size=1, max_size=8))
def test_property_order_never_affects_the_verdict(engines):
    """OQ-11 open: item order must not change any decision."""
    resolver = FakeResolver({"in": ObjectType.EVIDENCE})
    items = [item(e, ("in",)) for e in engines]
    guard = SequencingGuard(resolver)
    forward = [c.satisfied for c in guard.report(WorkSet(items=tuple(items)))]
    backward = [
        c.satisfied
        for c in guard.report(WorkSet(items=tuple(reversed(items))))
    ]
    assert forward == list(reversed(backward))


@settings(max_examples=150, deadline=None)
@given(engines=st.lists(consuming, min_size=1, max_size=6),
       workers=st.integers(min_value=1, max_value=5))
def test_property_unready_work_is_never_invoked(engines, workers):
    ran: list[int] = []
    lock = threading.Lock()

    def track(work_item: WorkItem) -> InvocationResult:
        with lock:
            ran.append(1)
        return InvocationResult.empty()

    Orchestrator(
        invoker=track, max_workers=workers, state_resolver=FakeResolver()
    ).run_cycle(WorkSet(items=tuple(item(e, ("m",)) for e in engines)))
    assert ran == []


@settings(max_examples=150, deadline=None)
@given(engines=st.lists(consuming, min_size=1, max_size=6),
       workers=st.integers(min_value=1, max_value=5))
def test_property_every_item_is_accounted_for(engines, workers):
    resolver = FakeResolver({"in": ObjectType.EVIDENCE})
    record = Orchestrator(
        invoker=empty_invoker, max_workers=workers, state_resolver=resolver
    ).run_cycle(WorkSet(items=tuple(item(e, ("in",)) for e in engines)))
    assert len(record.invocations) == len(engines)
    assert (
        record.attempted_count
        + record.rejected_count
        + sum(
            1 for r in record.invocations
            if r.outcome is InvocationOutcome.NOT_ATTEMPTED
        )
    ) == len(engines)


@settings(max_examples=100, deadline=None)
@given(engines=st.lists(consuming, min_size=1, max_size=6))
def test_property_rejections_never_become_processing_state(engines):
    processing = ProcessingStateStore()
    Orchestrator(
        invoker=empty_invoker, processing_store=processing,
        state_resolver=FakeResolver(),
    ).run_cycle(WorkSet(items=tuple(item(e, ("m",)) for e in engines)))
    assert len(processing) == 0


class TestInputCheckEdges:
    """Directly exercise the defensive branches of the verdict types."""

    def test_type_matches_is_false_without_an_expected_type(self):
        from oip.orchestration import InputCheck

        check = InputCheck("a", True, ObjectType.EVIDENCE, None)
        assert check.type_matches is False
        assert check.satisfied is False

    def test_type_matches_is_false_without_an_actual_type(self):
        from oip.orchestration import InputCheck

        check = InputCheck("a", False, None, ObjectType.EVIDENCE)
        assert check.type_matches is False

    def test_a_satisfied_check_has_no_reason(self):
        from oip.orchestration import InputCheck

        check = InputCheck("a", True, ObjectType.EVIDENCE, ObjectType.EVIDENCE)
        assert check.satisfied is True
        assert check.reason == ""

    def test_reason_names_unknown_types_safely(self):
        from oip.orchestration import InputCheck

        check = InputCheck("a", True, None, None)
        assert "unknown" in check.reason

    def test_a_satisfied_result_has_empty_detail(self):
        guard = SequencingGuard(FakeResolver({"EV-1": ObjectType.EVIDENCE}))
        result = guard.check(item(Engine.FACT_EXTRACTION, ("EV-1",)))
        assert result.detail == ""
        assert result.reasons == ()

    def test_report_covers_every_item(self):
        resolver = FakeResolver({"EV-1": ObjectType.EVIDENCE})
        work = WorkSet(items=(item(Engine.FACT_EXTRACTION, ("EV-1",)),
                              item(Engine.FACT_EXTRACTION, ("GONE",))))
        report = SequencingGuard(resolver).report(work)
        assert [c.satisfied for c in report] == [True, False]

    def test_existence_is_required_independently_of_the_type(self):
        """The `exists` conjunct is load-bearing, not redundant.

        A record can report a matching type while exists is False -- an
        inconsistent resolver, or a state that changed between the two reads.
        Satisfaction must still be denied: the criterion is that the input
        EXISTS, and a type alone does not establish that.
        """
        from oip.orchestration import InputCheck

        check = InputCheck("a", False, ObjectType.EVIDENCE, ObjectType.EVIDENCE)
        assert check.type_matches is True
        assert check.satisfied is False, (
            "a non-existent input was accepted because its type matched"
        )
        assert "does not exist" in check.reason

    def test_a_check_with_a_missing_input_is_unsatisfied_overall(self):
        from oip.orchestration import InputCheck, SequencingCheck

        result = SequencingCheck(
            Engine.FACT_EXTRACTION,
            (InputCheck("a", False, ObjectType.EVIDENCE, ObjectType.EVIDENCE),),
            requires_inputs=True,
        )
        assert result.satisfied is False
        assert len(result.unsatisfied) == 1
