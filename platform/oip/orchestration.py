"""Orchestration foundation: scheduled batch invocation and processing state.

Task: T01.6.1
Task: T01.6.2
Task: T01.6.3
Task: T01.6.4
Task: T01.6.5

Architecture References:
- N-17   Scheduled batch control model; directive, not reactive (closes M-35,
         M-37, OQ-15). Every cycle bounded by work-set size AND wall-clock
         budget
- N-18   Baseline Orchestration scoped into P1 (closes C-08)
- N-11   Acquisition/extraction concurrent; interpretation serialised
- N-10   Engine failure recorded, cycle continues, failure surfaced --
         never masked as completion
- AD-04  Orchestration sequences but never judges
- N-14   Direct-input table: the object type each engine consumes
- v2 4.12 Orchestration enforces stage ordering; its input is "the existence
         and status of objects awaiting processing", read from the Store
- v2 5.5 Orchestration: "Read state only" against Store and Graph
- N-6    The graph may lag the store: existence is read from the STORE
- OQ-10  Stage skipping OPEN (scheduled P6) -- partial pipelines NOT rejected
- OQ-11  Backflow OPEN (scheduled T07.3.8) -- item order NOT policed
- P4     Engines do not call each other; Orchestration is the only engine
         permitted to invoke others
- N-4    Reproducible inputs: engine_configuration_ref on every invocation
- N-8    Failed acceptance produces a failure record, never a silent
         rejection
- M-36   Failure-handling policy (retry/skip/halt/compensate) OPEN. N-10's
         header claims to close M-36, but the crosswalk records M-36 as
         compound -- "policy + representation". N-10 closes representation
         only; its Decision section states no retry/skip/halt/compensate
         rule. The POLICY half is therefore treated as OPEN and failed
         closed. See validation/T01.6.3-specification.md section 7
- M-57   Observability (metrics, rates, thresholds, alerting) OPEN and
         scheduled at T09.1.2, which this task blocks. Not built here
- M-01   Research trigger OPEN: work sets are externally specified
- M-56   Cost model OPEN: wall-clock budget is a proxy for a cost bound
- M-10   Learning cadence inherits cycle cadence
- v2 4.12 Orchestration Engine: "It moves work, not knowledge"; duplicate
         invocation is a named failure mode
- CI-1   Infrastructure state is logically isolated from Intelligence Objects
- Art.V  Configuration/infrastructure state never participates in reasoning
- IOM 2.5 Orchestration "reads status metadata only, never content"
- IOM 4.6 Orchestration creates no object and reads no content
- v2 5.5 Orchestration: "Read state only" against Store and Graph

THE DEFINING CONSTRAINT, quoted from PKP v2 4.12: Orchestration "does NOT
create or modify Intelligence Objects. It moves work, not knowledge." This
module therefore produces no Intelligence Object, owns no storage, performs no
transformation and makes no domain judgement. It plans a cycle, invokes
engines over a defined work set, and records what completed.

DIRECTIVE, NOT REACTIVE (N-17). Orchestration executes a plan. It does not
watch for objects appearing and trigger downstream work. That distinction
follows from AD-04: deciding *when work is ready* is a judgement about
knowledge state, which Orchestration may not make. A caller supplies the work
set; this module sequences it.

BOUNDEDNESS IS THE POINT. With M-56 unresolved and no resource limits defined,
an unbounded control model could consume without limit before anyone notices.
Every cycle is bounded twice -- by work-set size and by wall-clock budget --
and a cycle exhausting either terminates and reports. M-37 is closed by the
rule that the PLATFORM has no terminal state but every CYCLE does.

FAILURE HANDLING IS DELIBERATELY MINIMAL. N-10 specifies record, continue,
surface. It does NOT specify retry, skip, halt or compensate -- that is M-36,
open. This module implements exactly N-10 and no policy beyond it: a failing
engine's failure is recorded, the cycle continues to the next invocation, and
the cycle reports as FAILED rather than COMPLETED. Adding retry would invent
the missing policy.

PROCESSING STATE IS A RECORD, NOT A DECISION (T01.6.2). The processing store
answers what has been processed, by which engine, and when. It makes reprocessing
DETECTABLE, which is all the acceptance criterion requires. It never suppresses,
skips or retries a repeat: that would be the failure-handling policy M-36 leaves
open and the scheduling policy M-01 leaves open. Detection without action is the
fail-closed reading.

Processing state is held OUTSIDE the object model. This module imports no
Intelligence Object type and holds none. Processing records carry identifiers,
an engine, timestamps, a configuration reference and an outcome -- metadata,
never content, exactly as IOM 2.5 requires of Orchestration. They never enter
the lineage graph.

ORCHESTRATION OWNS NO STORAGE (v2 4.12). The processing store is SUPPLIED to
the Orchestrator, never constructed by it, on the same rule already applied to
the failure store. The class is defined here rather than beside the
configuration store because B-12 rejected the option of holding failure records
"in the same store as orchestration state" -- the architecture keeps those two
surfaces apart, and merging them here would undo that.

FAILURE SURFACING IS DETECTION, NOT POLICY (T01.6.3). FailureSurface is a
read-only view: it makes every recorded failure visible, proves mechanically
that none is masked as completion, and reports what continued past a failure.
It stores nothing, decides nothing and recovers nothing. Detection is
deliberately kept separate from policy because no ratified source specifies a
policy -- see M-36 above.

THE N-11 BOUNDARY IS A BARRIER (T01.6.4). Stages 1-2 (Evidence, Facts) may run
concurrently; stages 3-9 (Problem onward) run one at a time. A work set is
partitioned into ordered phases and phases never overlap, so interpretation
always begins after every preceding acquisition has finished. That is what
gives Pattern Intelligence a stable population. Concurrency is OFF by default
(max_workers=1): N-11 says acquisition MAY run concurrently, and with M-56
open there is no cost bound from which to derive a worker count, so the caller
must state one. Concurrency changes no semantics -- acceptance, lineage,
integrity, confidence and object contracts are untouched; this layer moves
work only.

SEQUENCING IS ABOUT INPUT EXISTENCE, NOTHING MORE (T01.6.5). The ratified
task sentence is "an engine cannot run before its inputs exist". The guard
checks that each declared input exists in the Store and is of the type N-14
says that engine consumes. It does NOT reject a work set for skipping stages
(OQ-10, open, scheduled P6) or for running them out of pipeline order (OQ-11,
open, scheduled T07.3.8) -- enforcing either would close an open question by
implementation. It never reorders work, never infers a missing stage and never
inserts an implicit item.

Scope: invocation and cycle bounding (T01.6.1), processing-state tracking
(T01.6.2), failure surfacing (T01.6.3), the N-11 concurrency boundary
(T01.6.4) and sequencing enforcement (T01.6.5). Feature F01.6 is complete.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable, Iterator, Protocol, Sequence

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.contract import utc_now
from oip.enums import (
    CONCURRENT_STAGES,
    ENGINE_INPUT_TYPE,
    ENGINE_STAGE,
    ROOT_ENGINES,
    Engine,
    ObjectStatus,
    ObjectType,
)

# A cycle must be bounded on both axes. [N-17]
DEFAULT_MAX_WORK_ITEMS = 1_000
DEFAULT_WALL_CLOCK_BUDGET_SECONDS = 300.0


class OrchestrationError(Exception):
    """Base class for orchestration violations."""


class CycleBoundError(OrchestrationError):
    """A cycle bound is absent or non-positive. [N-17]"""


class WorkSetError(OrchestrationError):
    """The work set is malformed. [N-17, M-01]"""


class InvocationError(OrchestrationError):
    """An invocation is malformed. [AD-04, N-4]"""


class CycleStateError(OrchestrationError):
    """A cycle was used outside its permitted lifecycle."""


class KnowledgeMutationError(OrchestrationError):
    """Orchestration attempted to produce knowledge. [AD-04, v2 4.12]

    The defining constraint: Orchestration moves work, not knowledge. An
    engine result carrying an Intelligence Object back through the control
    layer would make Orchestration a producer, which it may never be.
    """


class ProcessingStateError(OrchestrationError):
    """A processing-state record is malformed or inadmissible. [T01.6.2]"""


def _id_tuple(value: object, label: str, error: type[OrchestrationError]) -> tuple[str, ...]:
    """Coerce an id collection to a tuple, refusing a bare string.

    DEFECT FIX (found at T01.6.2). These fields are declared tuple[str, ...]
    but nothing coerced or checked the container, so any iterable was stored
    verbatim. Two consequences, both silent:

    * A bare `str` is iterable, so "abc" became the three ids "a","b","c".
      An input id is a single opaque identifier; splitting it into characters
      corrupts every key derived from it. At T01.6.2 that defeats the
      acceptance criterion outright -- a genuine repeat went undetected
      because the recorded key and the queried key disagreed.
    * A `list` survived into a frozen dataclass, so a "immutable" record was
      mutable through its own field, and mutating it after recording could
      inject a key the store's index had never seen.

    Fail closed on the bare string rather than guessing whether the caller
    meant one id or several.
    """
    if isinstance(value, (str, bytes)):
        raise error(
            f"{label} must be a collection of ids, not a bare string "
            f"{value!r}; an id is opaque and is never split [T01.6.2]"
        )
    try:
        return tuple(value)  # type: ignore[arg-type]
    except TypeError:
        raise error(
            f"{label} must be an iterable of ids, got "
            f"{type(value).__name__} [T01.6.2]"
        ) from None


def _describe_exception(exc: BaseException) -> str:
    """Render an engine fault as text that can never itself raise. [N-10]

    DEFECT FIX (found at T01.6.3). The detail string was built with an
    f-string, which calls str(exc). An engine whose exception has a failing
    __str__ or __repr__ made that call raise from inside the handler, and
    the new exception propagated out of run_cycle: the cycle record was
    discarded entirely, remaining work was never attempted, and the failure
    was never recorded. That is precisely the "one engine fails mid-batch,
    leaving inconsistent state" mode PKP v2 4.12 names, and it breached both
    N-10 (failure recorded and surfaced) and the T01.6.3 criterion that
    failures must not silently halt the pipeline.

    The type name is read from the class, never from the instance, so a
    hostile __str__ cannot suppress the fact that a failure occurred. If
    rendering the message fails, the failure is still recorded with the
    rendering fault stated -- degraded detail, never a lost failure.
    """
    try:
        name = type(exc).__name__
    except BaseException:            # pragma: no cover - pathological
        name = "UnrenderableException"
    try:
        message = str(exc)
    except BaseException as inner:
        try:
            reason = type(inner).__name__
        except BaseException:        # pragma: no cover - pathological
            reason = "unknown"
        message = f"<exception message unrenderable: {reason}>"
    return f"{name}: {message}"


def _require_coherent_timestamps(
    started_at: object, ended_at: object, error: type[OrchestrationError]
) -> None:
    """Guard 'when' against mixed timezone awareness. [T01.6.2, N-10]

    Comparing a naive datetime to an aware one raises TypeError, which would
    escape as an uncaught crash rather than a stated refusal. That is the
    same defect class already fixed at V8, E-V5 and X-V5, and it is guarded
    here the same way: mixed awareness is refused explicitly.

    An uncaught TypeError inside the store would break N-10 -- the crash
    would propagate out of the commit and could leave a cycle's processing
    unrecorded while the cycle itself reported completion.
    """
    for label, value in (("started_at", started_at), ("ended_at", ended_at)):
        if not isinstance(value, datetime):
            raise error(
                f"{label} must be a datetime, got {type(value).__name__}; "
                f"'when' is one of the three facts T01.6.2 records"
            )
    if (started_at.tzinfo is None) != (ended_at.tzinfo is None):  # type: ignore[union-attr]
        raise error(
            "started_at and ended_at mix timezone-aware and naive values; "
            "comparing them is undefined [T01.6.2, cf. V8, E-V5, X-V5]"
        )


class ProcessingIsolationError(OrchestrationError):
    """Processing state was used as intelligence. [CI-1, Art.V, N-10]

    Processing state is infrastructure state. It is logically isolated from
    Intelligence Objects and never participates in reasoning, scoring,
    pattern detection or lineage.
    """


class CycleOutcome(str, Enum):
    """How a cycle ended. [N-17, M-37]

    Every cycle terminates in exactly one of these. The platform has no
    terminal state; every cycle does.
    """

    COMPLETED = "COMPLETED"                    # work set exhausted, no failures
    FAILED = "FAILED"                          # completed, but an engine failed
    WORK_LIMIT_REACHED = "WORK_LIMIT_REACHED"  # bounded by work-set size
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"      # bounded by wall clock

    @property
    def is_bounded_stop(self) -> bool:
        """Whether the cycle stopped on a bound rather than finishing."""
        return self in (
            CycleOutcome.WORK_LIMIT_REACHED,
            CycleOutcome.BUDGET_EXHAUSTED,
        )

    @property
    def had_failure(self) -> bool:
        """Whether the STOP REASON was failure. Not "did anything fail".

        A cycle that fails AND then hits a bound reports the bound, so this
        returns False while failures exist. Callers asking whether anything
        failed must use CycleRecord.had_failure, which reads the invocation
        records. Selecting on this property alone masked failures at cycle
        level, which N-10 forbids. [N-10]
        """
        return self is CycleOutcome.FAILED


class InvocationOutcome(str, Enum):
    """How a single engine invocation ended. [N-10]

    EMPTY is distinct from FAILED by design: N-10 requires that an empty
    result and a failed result stay distinguishable. An engine that ran
    correctly and found nothing has not failed.
    """

    PRODUCED = "PRODUCED"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"   # cycle bound reached before this item
    # The engine was never invoked because its inputs do not exist. [T01.6.5]
    #
    # Distinct from all three above, and deliberately so:
    #   FAILED         -- an engine ran and failed [N-10]
    #   EMPTY          -- an engine ran and found nothing [N-10]
    #   NOT_ATTEMPTED  -- a cycle bound was reached first [N-17]
    #   REJECTED_OUT_OF_ORDER -- the plan was invalid; no engine ran
    #
    # Collapsing it into FAILED would attribute a planning error to an engine
    # that never executed, blurring exactly the distinction N-10 makes
    # mandatory at every stage.
    REJECTED_OUT_OF_ORDER = "REJECTED_OUT_OF_ORDER"


class ConcurrencyClass(str, Enum):
    """The two classes N-11 defines. Exactly two; no others exist. [N-11]

    Quoted from the decision's own table:

        | 1 Evidence, 2 Facts       | Concurrent -- operations are
                                      independent per source |
        | 3 Problems ... 9 Feedback | Serialised -- one batch at a time |

    The boundary falls between stage 2 and stage 3 and nowhere else.
    """

    CONCURRENT = "CONCURRENT"    # stages 1-2: acquisition and extraction
    SERIALISED = "SERIALISED"    # stages 3-9: interpretation onward

    @classmethod
    def for_stage(cls, stage: int) -> "ConcurrencyClass":
        if stage in CONCURRENT_STAGES:
            return cls.CONCURRENT
        return cls.SERIALISED


class ConcurrencyError(OrchestrationError):
    """A work item cannot be placed on either side of the N-11 boundary.

    Fails closed. An item whose stage cannot be determined cannot be known
    to be safe to run in parallel, and guessing would risk exactly the
    version branching N-11 makes impossible. [N-11, R-1]
    """


class SequencingError(OrchestrationError):
    """A sequencing check is malformed or unanswerable. [T01.6.5]"""


class SequencingViolation(OrchestrationError):
    """An engine would run before its inputs exist. [v2 4.12, T01.6.5]

    Stage-order violation is a named Orchestration failure mode: "an engine
    runs on inputs that are not ready; pipeline integrity lost". This is
    raised only by assert_sequenced(), which fails closed.

    Deliberately NOT a failure in the N-10 sense. No engine ran, so there is
    nothing to record as an engine failure, and conflating the two would
    blur the empty/failed distinction N-10 makes mandatory.
    """


# ---------------------------------------------------------------------------
# Cycle bounds  [N-17, M-37]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CycleBounds:
    """The two bounds every cycle carries. [N-17]

    Both are mandatory and both are enforced. A cycle exhausting either
    terminates and reports; it never runs unbounded. The wall-clock budget is
    explicitly a PROXY for a cost bound that does not yet exist [M-56].
    """

    max_work_items: int = DEFAULT_MAX_WORK_ITEMS
    wall_clock_budget_seconds: float = DEFAULT_WALL_CLOCK_BUDGET_SECONDS

    def __post_init__(self) -> None:
        if not isinstance(self.max_work_items, int) or isinstance(
            self.max_work_items, bool
        ):
            raise CycleBoundError(
                f"max_work_items must be an integer, got "
                f"{self.max_work_items!r} [N-17]"
            )
        if self.max_work_items <= 0:
            raise CycleBoundError(
                f"max_work_items must be positive, got {self.max_work_items}; "
                f"an unbounded cycle is what N-17 exists to prevent"
            )
        if isinstance(self.wall_clock_budget_seconds, bool) or not isinstance(
            self.wall_clock_budget_seconds, (int, float)
        ):
            raise CycleBoundError(
                f"wall_clock_budget_seconds must be numeric, got "
                f"{self.wall_clock_budget_seconds!r} [N-17]"
            )
        if self.wall_clock_budget_seconds <= 0:
            raise CycleBoundError(
                f"wall_clock_budget_seconds must be positive, got "
                f"{self.wall_clock_budget_seconds}; with no cost model "
                f"(M-56) the wall clock is the only bound available"
            )


# ---------------------------------------------------------------------------
# Work set  [N-17, M-01]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkItem:
    """One unit of work: an engine and the input it is to process. [N-17]

    Carries an engine_configuration_ref because N-4 requires every produced
    object to be reproducible, and the configuration in force at invocation
    is part of that record.

    `input_ids` are opaque here. Orchestration moves work; it does not read
    object content, so it neither knows nor cares what the ids denote.
    """

    engine: Engine
    input_ids: tuple[str, ...]
    engine_configuration_ref: str
    produces: ObjectType | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.engine, Engine):
            raise WorkSetError(
                f"work item requires a known Engine, got {self.engine!r}"
            )
        if not (self.engine_configuration_ref or "").strip():
            raise WorkSetError(
                "work item requires an engine_configuration_ref; without it "
                "the resulting objects are not reproducible [N-4]"
            )
        if self.produces is not None and not isinstance(
            self.produces, ObjectType
        ):
            raise WorkSetError(
                f"produces must be a known ObjectType or None, got "
                f"{self.produces!r}"
            )
        # Same defect fix as ProcessingRecord: a bare string is iterable and
        # was being split into one id per character, and a list survived into
        # a frozen record. Discovered at T01.6.2, where a string-valued
        # input_ids silently defeated repeat detection -- the recorded key and
        # the queried key disagreed, so a genuine repeat read as new work.
        object.__setattr__(
            self, "input_ids",
            _id_tuple(self.input_ids, "input_ids", WorkSetError),
        )
        for oid in self.input_ids:
            if not (oid or "").strip():
                raise WorkSetError("work item input id may not be empty")
        if len(set(self.input_ids)) != len(self.input_ids):
            raise WorkSetError(
                "the same input appears twice in one work item; duplicate "
                "invocation is a named failure mode [v2 4.12]"
            )

    # -- N-11 boundary placement  [T01.6.4] -------------------------------

    @property
    def stage(self) -> int:
        """The pipeline stage this item belongs to, 1-9. [IOM 2.6]

        Resolved from `produces` first, because the object type IS the stage
        (IOM 2.6) and stage 8 has no owning engine at all -- C-02 is open and
        no producer may be invented, so an Execution Record item is
        expressible only by the type it produces.

        Falls back to the engine. Fails closed for Orchestration, which owns
        no stage and produces no object: it is cross-cutting, not
        pipeline-aligned (IOM 4.6).
        """
        if self.produces is not None:
            return self.produces.stage
        stage = ENGINE_STAGE.get(self.engine)
        if stage is None:
            raise ConcurrencyError(
                f"{self.engine.value} owns no pipeline stage, so this item "
                f"cannot be placed on either side of the N-11 boundary. "
                f"Orchestration is cross-cutting and produces no object "
                f"[IOM 4.6]; stage 8 has no owning engine [C-02 open]. "
                f"Supply `produces` to state the stage explicitly."
            )
        return stage

    @property
    def concurrency_class(self) -> "ConcurrencyClass":
        """Which side of the N-11 boundary this item falls on. [N-11]"""
        return ConcurrencyClass.for_stage(self.stage)

    @property
    def is_concurrent(self) -> bool:
        """Stages 1-2: acquisition and extraction. [N-11]"""
        return self.concurrency_class is ConcurrencyClass.CONCURRENT

    @property
    def is_serialised(self) -> bool:
        """Stages 3-9: interpretation onward. [N-11]"""
        return self.concurrency_class is ConcurrencyClass.SERIALISED


@dataclass(frozen=True)
class WorkSet:
    """The bounded set of work a cycle will attempt. [N-17]

    Externally specified: with M-01 (research trigger) open, nothing in the
    platform decides what to work on. That gap is exposed rather than filled
    -- inventing a trigger model here would close M-01 by implementation.

    Order is significant and preserved. A directive Orchestration executes a
    plan, and the plan's order is the caller's, not this module's.
    """

    items: tuple[WorkItem, ...]
    description: str = ""

    def __post_init__(self) -> None:
        for item in self.items:
            if not isinstance(item, WorkItem):
                raise WorkSetError(
                    f"work set entries must be WorkItem, got {item!r}"
                )

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    @property
    def is_empty(self) -> bool:
        return not self.items

    @property
    def engines(self) -> tuple[Engine, ...]:
        """Engines this work set will invoke, in first-appearance order."""
        seen: list[Engine] = []
        for item in self.items:
            if item.engine not in seen:
                seen.append(item.engine)
        return tuple(seen)

    # -- N-11 phase plan  [T01.6.4] ---------------------------------------

    def concurrency_plan(self) -> tuple["ExecutionPhase", ...]:
        """Partition the work set into ordered phases per N-11. [T01.6.4]

        Adjacent CONCURRENT items (stages 1-2) collapse into one phase whose
        members may run in parallel. Every SERIALISED item (stages 3-9) is a
        phase of its own -- "one batch at a time" [N-11].

        Phases run in order and never overlap, so a serialised item can only
        begin once every preceding concurrent item has finished. That barrier
        is what gives interpretation a STABLE POPULATION: Pattern
        Intelligence cannot reason across a population that acquisition is
        still writing into.

        CALLER ORDER IS PRESERVED EXACTLY. Phases are maximal runs in the
        order given; nothing is reordered, coalesced or sorted. A directive
        Orchestration executes the caller's plan [N-17], and reordering work
        would be a scheduling judgement AD-04 forbids.
        """
        phases: list[ExecutionPhase] = []
        run: list[int] = []
        for index, item in enumerate(self.items):
            if item.is_concurrent:
                run.append(index)
                continue
            if run:
                phases.append(
                    ExecutionPhase(ConcurrencyClass.CONCURRENT, tuple(run))
                )
                run = []
            phases.append(
                ExecutionPhase(ConcurrencyClass.SERIALISED, (index,))
            )
        if run:
            phases.append(
                ExecutionPhase(ConcurrencyClass.CONCURRENT, tuple(run))
            )
        return tuple(phases)


@dataclass(frozen=True)
class ExecutionPhase:
    """One ordered step of a cycle's N-11 plan. [T01.6.4]

    A CONCURRENT phase may hold many items, which may run in parallel. A
    SERIALISED phase holds exactly one, because interpretation runs one batch
    at a time. Indices refer to positions in the work set, so caller order is
    never lost.
    """

    concurrency_class: ConcurrencyClass
    item_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.concurrency_class, ConcurrencyClass):
            raise ConcurrencyError(
                f"phase requires a ConcurrencyClass, got "
                f"{self.concurrency_class!r}"
            )
        if not self.item_indices:
            raise ConcurrencyError("an execution phase may not be empty")
        if (
            self.concurrency_class is ConcurrencyClass.SERIALISED
            and len(self.item_indices) != 1
        ):
            raise ConcurrencyError(
                f"a serialised phase holds exactly one item, got "
                f"{len(self.item_indices)}; interpretation runs one batch at "
                f"a time [N-11]"
            )

    @property
    def is_parallel(self) -> bool:
        """Whether this phase MAY run in parallel. [N-11]

        Permission, not obligation: with max_workers=1 a concurrent phase
        still runs sequentially, and N-11 says "may run concurrently".
        """
        return self.concurrency_class is ConcurrencyClass.CONCURRENT

    def __len__(self) -> int:
        return len(self.item_indices)


# ---------------------------------------------------------------------------
# Engine invocation contract  [P4, AD-04]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvocationResult:
    """What an engine reports back to Orchestration. [N-10, AD-04]

    Deliberately carries NO Intelligence Object. Engines write to the Store
    themselves through the acceptance path; Orchestration is told only how
    many objects were produced and their ids, so it can record what completed
    without ever holding knowledge.

    That is the enforcement of "moves work, not knowledge": there is no field
    on this type through which an object could travel.
    """

    outcome: InvocationOutcome
    produced_ids: tuple[str, ...] = ()
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, InvocationOutcome):
            raise InvocationError(
                f"invocation outcome must be an InvocationOutcome, got "
                f"{self.outcome!r}"
            )
        # See WorkItem: a bare string was split into one id per character.
        object.__setattr__(
            self, "produced_ids",
            _id_tuple(self.produced_ids, "produced_ids", InvocationError),
        )
        if self.outcome is InvocationOutcome.PRODUCED and not self.produced_ids:
            raise InvocationError(
                "PRODUCED requires at least one produced id; an engine that "
                "produced nothing reports EMPTY, which N-10 keeps distinct "
                "from FAILED"
            )
        if self.outcome is InvocationOutcome.EMPTY and self.produced_ids:
            raise InvocationError(
                "EMPTY may not carry produced ids"
            )
        for oid in self.produced_ids:
            if not isinstance(oid, str):
                raise KnowledgeMutationError(
                    f"produced_ids must be object ids, got {type(oid).__name__}; "
                    f"Orchestration moves work, not knowledge [AD-04, v2 4.12]"
                )
            if not oid.strip():
                raise InvocationError("produced id may not be empty")

    @classmethod
    def produced(cls, *object_ids: str, detail: str = "") -> "InvocationResult":
        return cls(InvocationOutcome.PRODUCED, tuple(object_ids), detail)

    @classmethod
    def empty(cls, detail: str = "") -> "InvocationResult":
        return cls(InvocationOutcome.EMPTY, (), detail)


class EngineInvoker(Protocol):
    """What Orchestration calls. [P4]

    Engines do not call each other; Orchestration is the only engine
    permitted to invoke others. The invoker is supplied by the caller because
    no engine exists yet -- P2 onward builds them.
    """

    def __call__(self, item: WorkItem) -> InvocationResult:
        ...


# ---------------------------------------------------------------------------
# Cycle record  [N-17, M-37]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class InvocationRecord:
    """What happened for one work item. [N-10]

    Infrastructure state, not an Intelligence Object: no lineage, no
    confidence, no explanation, no status. It never enters the lineage graph,
    exactly as failure records never do.
    """

    engine: Engine
    input_ids: tuple[str, ...]
    engine_configuration_ref: str
    outcome: InvocationOutcome
    produced_ids: tuple[str, ...]
    detail: str
    started_at: datetime
    ended_at: datetime

    @property
    def failed(self) -> bool:
        return self.outcome is InvocationOutcome.FAILED

    @property
    def attempted(self) -> bool:
        """Whether an engine was actually invoked for this item.

        Both NOT_ATTEMPTED and REJECTED_OUT_OF_ORDER mean no engine ran: the
        first because a cycle bound was reached, the second because the
        item's inputs did not exist [T01.6.5]. Reporting a rejected item as
        attempted would record work as processed that never happened, which
        T01.6.2's store refuses and N-10 forbids.
        """
        return self.outcome not in (
            InvocationOutcome.NOT_ATTEMPTED,
            InvocationOutcome.REJECTED_OUT_OF_ORDER,
        )

    @property
    def rejected(self) -> bool:
        """Rejected for sequencing: inputs did not exist. [T01.6.5]"""
        return self.outcome is InvocationOutcome.REJECTED_OUT_OF_ORDER

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Control records are not knowledge. [AD-04, N-10]"""
        return False


@dataclass(frozen=True)
class CycleRecord:
    """The complete, immutable record of one cycle. [N-17, M-37]

    Frozen: a concluded cycle is a historical fact, mirroring how a concluded
    Validation is. It records what was planned, what was attempted, what
    completed and why the cycle ended.
    """

    cycle_id: int
    outcome: CycleOutcome
    bounds: CycleBounds
    invocations: tuple[InvocationRecord, ...]
    failures: tuple[FailureRecord, ...]
    planned_items: int
    started_at: datetime
    ended_at: datetime
    description: str = ""

    @property
    def attempted_count(self) -> int:
        return sum(1 for r in self.invocations if r.attempted)

    @property
    def not_attempted_count(self) -> int:
        """Items no engine ran for: bound reached OR rejected. [N-17, T01.6.5]"""
        return sum(1 for r in self.invocations if not r.attempted)

    @property
    def rejected_count(self) -> int:
        """Items rejected because their inputs did not exist. [T01.6.5]"""
        return sum(1 for r in self.invocations if r.rejected)

    @property
    def had_sequencing_violation(self) -> bool:
        """Whether any item was rejected for sequencing. [T01.6.5, v2 4.12]

        Read from the invocation records, never from the cycle outcome, for
        the same reason had_failure is: a rejection must stay visible
        whatever else the cycle reports.
        """
        return any(r.rejected for r in self.invocations)

    def rejected_invocations(self) -> tuple[InvocationRecord, ...]:
        """Every sequencing rejection, with its reason. [T01.6.5]"""
        return tuple(r for r in self.invocations if r.rejected)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.invocations if r.failed)

    @property
    def produced_count(self) -> int:
        return sum(len(r.produced_ids) for r in self.invocations)

    @property
    def empty_count(self) -> int:
        """Invocations that ran correctly and produced nothing. [N-10]"""
        return sum(
            1 for r in self.invocations
            if r.outcome is InvocationOutcome.EMPTY
        )

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()

    @property
    def had_failure(self) -> bool:
        """Whether any engine failed, whatever the stop reason. [N-10]

        Read from the invocation records, NOT from the outcome. The outcome
        answers "why did the cycle stop"; this answers "did anything fail".
        They are orthogonal: a cycle can hit a bound AND contain failures,
        and an earlier version reported only the bound -- masking the failure
        at cycle level, which N-10 forbids.
        """
        return any(r.failed for r in self.invocations)

    @property
    def terminated(self) -> bool:
        """Always True. Every cycle terminates. [N-17, M-37]"""
        return True

    @property
    def engines_invoked(self) -> tuple[Engine, ...]:
        seen: list[Engine] = []
        for record in self.invocations:
            if record.attempted and record.engine not in seen:
                seen.append(record.engine)
        return tuple(seen)

    def for_engine(self, engine: Engine) -> tuple[InvocationRecord, ...]:
        return tuple(r for r in self.invocations if r.engine is engine)


# ---------------------------------------------------------------------------
# Processing state  [T01.6.2 -- N-17, N-10, AD-04, CI-1, IOM 2.5]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProcessingRecord:
    """What was processed, by which engine, and when. [T01.6.2, N-17]

    The three facts the acceptance criterion names, plus the two the
    architecture requires alongside them: the cycle it belonged to (N-17
    tracks processing state PER CYCLE) and the configuration in force (N-4
    reproducibility).

    METADATA ONLY, NEVER CONTENT [IOM 2.5, 4.6]. Every field is an
    identifier, an engine, a timestamp, a configuration reference or an
    outcome. There is no field through which object content could travel --
    the same structural enforcement InvocationResult uses. Orchestration
    reads status metadata only, and this record is the shape of that limit.

    OUTSIDE THE OBJECT MODEL [Art.V, CI-1, N-10]. Not an Intelligence Object:
    no lineage, no confidence, no explanation, no status, no version chain.
    It never enters the lineage graph, so the platform can never reason from
    its own bookkeeping.

    IMMUTABLE. Frozen, and the store is append-only. A second attempt on the
    same input appends a second record; it never overwrites the first. That
    accumulated history is precisely what makes reprocessing detectable.
    """

    cycle_id: int
    engine: Engine
    input_ids: tuple[str, ...]
    engine_configuration_ref: str
    outcome: InvocationOutcome
    produced_ids: tuple[str, ...]
    started_at: datetime
    ended_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.cycle_id, int) or isinstance(self.cycle_id, bool):
            raise ProcessingStateError(
                f"cycle_id must be an integer, got {self.cycle_id!r}; "
                f"processing state is tracked per cycle [N-17]"
            )
        if self.cycle_id < 1:
            raise ProcessingStateError(
                f"cycle_id starts at 1, got {self.cycle_id}"
            )
        if not isinstance(self.engine, Engine):
            raise ProcessingStateError(
                f"processing record requires a known Engine, got "
                f"{self.engine!r}; 'by which engine' is not optional [T01.6.2]"
            )
        if not isinstance(self.outcome, InvocationOutcome):
            raise ProcessingStateError(
                f"outcome must be an InvocationOutcome, got {self.outcome!r}"
            )
        if self.outcome is InvocationOutcome.NOT_ATTEMPTED:
            raise ProcessingStateError(
                "an item the cycle never reached was not processed; "
                "recording it would mask starvation [v2 4.12] and would "
                "report work as done that never ran [N-10]"
            )
        if not (self.engine_configuration_ref or "").strip():
            raise ProcessingStateError(
                "processing record requires an engine_configuration_ref; "
                "without it the processing is not reproducible [N-4]"
            )
        object.__setattr__(
            self, "input_ids",
            _id_tuple(self.input_ids, "input_ids", ProcessingStateError),
        )
        object.__setattr__(
            self, "produced_ids",
            _id_tuple(self.produced_ids, "produced_ids", ProcessingStateError),
        )
        _require_coherent_timestamps(
            self.started_at, self.ended_at, ProcessingStateError
        )
        if not self.input_ids:
            raise ProcessingStateError(
                "processing record requires at least one input id; a record "
                "of processing nothing is not evidence that anything was "
                "processed [T01.6.2]"
            )
        self._guard_ids(self.input_ids, "input")
        self._guard_ids(self.produced_ids, "produced")
        if len(set(self.input_ids)) != len(self.input_ids):
            raise ProcessingStateError(
                "the same input appears twice in one processing record; "
                "duplicate invocation is a named failure mode [v2 4.12]"
            )
        if self.ended_at < self.started_at:
            raise ProcessingStateError(
                f"processing ended before it started: {self.started_at} -> "
                f"{self.ended_at}; 'when' must be coherent [T01.6.2]"
            )

    @staticmethod
    def _guard_ids(ids: tuple[str, ...], label: str) -> None:
        for oid in ids:
            if not isinstance(oid, str):
                raise KnowledgeMutationError(
                    f"{label} ids must be object ids, got "
                    f"{type(oid).__name__}; processing state holds metadata "
                    f"only, never content [IOM 2.5, AD-04]"
                )
            if not oid.strip():
                raise ProcessingStateError(f"{label} id may not be empty")

    # -- what happened ----------------------------------------------------

    @property
    def failed(self) -> bool:
        """Whether the attempt failed. Kept distinct from empty. [N-10]"""
        return self.outcome is InvocationOutcome.FAILED

    @property
    def produced_nothing(self) -> bool:
        """Ran correctly and found nothing -- NOT a failure. [N-10]"""
        return self.outcome is InvocationOutcome.EMPTY

    @property
    def duration_seconds(self) -> float:
        return (self.ended_at - self.started_at).total_seconds()

    def keys(self) -> tuple[tuple[Engine, str], ...]:
        """The (engine, input) pairs this record accounts for. [T01.6.2]"""
        return tuple((self.engine, oid) for oid in self.input_ids)

    # -- isolation boundary  [CI-1, Art.V, Art.IV, N-10, AD-04] -----------

    @property
    def is_intelligence(self) -> bool:
        """Always False. Processing state is infrastructure. [CI-1, Art.V]"""
        return False

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Processing state never enters lineage. [N-10]"""
        return False

    def as_lineage_reference(self):
        """Never permitted. [CI-1, N-10]"""
        raise ProcessingIsolationError(
            "processing state may not participate in lineage; it is "
            "infrastructure state, not intelligence [CI-1, N-10]"
        )

    def as_evidence(self):
        """Never permitted. [AD-05, Article IV]"""
        raise ProcessingIsolationError(
            "no platform-generated artifact may become Evidence directly; "
            "processing state least of all [AD-05, Article IV]"
        )

    def confidence_contribution(self):
        """Never permitted. [CI-1, Art.V]"""
        raise ProcessingIsolationError(
            "processing state may not contribute to confidence, scoring or "
            "pattern detection [CI-1, Art.V]"
        )


@dataclass
class ProcessingStateStore:
    """What has been processed, by which engine, when. [T01.6.2]

    Held OUTSIDE the object model, alongside the other infrastructure-state
    surfaces and sharing no type with any Intelligence Object. Append-only
    and immutable: a repeat appends, never overwrites.

    IT DETECTS; IT DOES NOT DECIDE [AD-04]. `has_processed`, `attempts` and
    `repeat_inputs` make reprocessing visible. Nothing here suppresses,
    skips, defers or retries a repeat -- that is failure-handling policy
    (M-36, OPEN) and scheduling policy (M-01, OPEN). Detection is the whole
    of the ratified requirement; acting on it would invent the missing
    policy.

    WHAT IT REFUSES TO ANSWER. Whether a changed engine_configuration_ref
    makes an input eligible for reprocessing is not ratified anywhere. The
    reference is recorded on every record and is queryable, and the store
    expresses no opinion. `has_processed` keys strictly on the pair the
    backlog names -- what was processed, by which engine.

    NOT OWNED BY THE ORCHESTRATOR. Supplied to it, never built by it:
    Orchestration "does NOT own storage" [v2 4.12].

    RETENTION IS UNSPECIFIED. N-12 governs Intelligence Objects; N-10
    already records that failure-record retention "must be specified
    separately". The same gap applies here. Growth is unbounded and no
    eviction is performed, because none is specified.

    Thread-safe: N-11 permits stages 1 and 2 to run concurrently.
    """

    _records: list[ProcessingRecord] = field(default_factory=list, init=False)
    _by_key: dict[tuple[Engine, str], list[int]] = field(
        default_factory=dict, init=False
    )
    _by_cycle: dict[int, list[int]] = field(default_factory=dict, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    # -- recording --------------------------------------------------------

    def record(
        self, cycle_id: int, invocation: InvocationRecord
    ) -> ProcessingRecord:
        """Record one completed invocation as processing state. [T01.6.2]

        Refuses NOT_ATTEMPTED: an item the cycle never reached was not
        processed, and recording it would report work as done that never
        ran.

        Returns the record. It never reports whether this was a repeat --
        callers ask `has_processed` or `repeat_inputs`, so that detection is
        an explicit act rather than a side effect that could be ignored.
        """
        if not isinstance(invocation, InvocationRecord):
            raise ProcessingStateError(
                f"expected an InvocationRecord, got {invocation!r}"
            )
        entry = ProcessingRecord(
            cycle_id=cycle_id,
            engine=invocation.engine,
            input_ids=invocation.input_ids,
            engine_configuration_ref=invocation.engine_configuration_ref,
            outcome=invocation.outcome,
            produced_ids=invocation.produced_ids,
            started_at=invocation.started_at,
            ended_at=invocation.ended_at,
        )
        return self._append(entry)

    def record_cycle(self, cycle: CycleRecord) -> tuple[ProcessingRecord, ...]:
        """Record every ATTEMPTED invocation of a concluded cycle. [N-17]

        N-17 tracks processing state per cycle. Unattempted items are
        excluded by definition, and their count remains visible on the cycle
        record as `not_attempted_count`, so the exclusion is never silent.

        A cycle is committed exactly once. Committing the same cycle_id twice
        is refused: the second commit's records would be indistinguishable
        from the first's, and a store that cannot tell two cycles apart
        cannot answer 'when' correctly.
        """
        if not isinstance(cycle, CycleRecord):
            raise ProcessingStateError(
                f"expected a CycleRecord, got {cycle!r}"
            )
        with self._lock:
            if cycle.cycle_id in self._by_cycle:
                raise ProcessingStateError(
                    f"cycle {cycle.cycle_id} is already recorded; processing "
                    f"state is append-only and a cycle is committed once. If "
                    f"two orchestrators share one store they must not share "
                    f"cycle ids [T01.6.2]"
                )
            # Build every record before appending any, so a malformed
            # invocation cannot leave the cycle half-committed.
            entries = [
                ProcessingRecord(
                    cycle_id=cycle.cycle_id,
                    engine=r.engine,
                    input_ids=r.input_ids,
                    engine_configuration_ref=r.engine_configuration_ref,
                    outcome=r.outcome,
                    produced_ids=r.produced_ids,
                    started_at=r.started_at,
                    ended_at=r.ended_at,
                )
                for r in cycle.invocations
                if r.attempted
            ]
            self._by_cycle.setdefault(cycle.cycle_id, [])
            for entry in entries:
                self._append(entry)
            return tuple(entries)

    def _append(self, entry: ProcessingRecord) -> ProcessingRecord:
        with self._lock:
            index = len(self._records)
            self._records.append(entry)
            for key in entry.keys():
                self._by_key.setdefault(key, []).append(index)
            self._by_cycle.setdefault(entry.cycle_id, []).append(index)
            return entry

    # -- idempotence support: reprocessing detectable  [T01.6.2, N-10] ----

    def has_processed(self, engine: Engine, input_id: str) -> bool:
        """Whether this engine has an attempt recorded on this input.

        An ATTEMPT, not a success. N-10 keeps empty, failed and produced
        distinguishable, and this deliberately does not collapse them:
        whether a failed attempt should be retried is M-36, OPEN. Callers
        needing the distinction read `attempts` and inspect the outcomes.
        """
        with self._lock:
            return bool(self._by_key.get(self._key(engine, input_id)))

    def attempt_count(self, engine: Engine, input_id: str) -> int:
        """How many times this engine has processed this input."""
        with self._lock:
            return len(self._by_key.get(self._key(engine, input_id), ()))

    def attempts(
        self, engine: Engine, input_id: str
    ) -> tuple[ProcessingRecord, ...]:
        """Every attempt, in recording order. The full 'when'."""
        with self._lock:
            return tuple(
                self._records[i]
                for i in self._by_key.get(self._key(engine, input_id), ())
            )

    def last_processed_at(
        self, engine: Engine, input_id: str
    ) -> datetime | None:
        """When this engine last processed this input. [T01.6.2 'when']"""
        with self._lock:
            indices = self._by_key.get(self._key(engine, input_id), ())
            return self._records[indices[-1]].ended_at if indices else None

    def engines_that_processed(self, input_id: str) -> tuple[Engine, ...]:
        """Which engines have processed this input. [T01.6.2 'by which']"""
        with self._lock:
            seen: list[Engine] = []
            for engine, oid in self._by_key:
                if oid == input_id and engine not in seen:
                    seen.append(engine)
            return tuple(seen)

    def repeat_inputs(self, item: WorkItem) -> tuple[str, ...]:
        """Inputs of this work item this engine has already processed.

        The detection primitive: non-empty means running this item would be
        reprocessing, wholly or in part. It returns the offending inputs
        rather than a bare flag so the caller can see exactly what overlaps.

        It takes no action. Whether to run anyway is scheduling policy
        [M-01, M-36 -- both OPEN].
        """
        if not isinstance(item, WorkItem):
            raise ProcessingStateError(f"expected a WorkItem, got {item!r}")
        with self._lock:
            return tuple(
                oid for oid in item.input_ids
                if self._by_key.get((item.engine, oid))
            )

    def would_reprocess(self, item: WorkItem) -> bool:
        """Whether running this item would repeat recorded work. [T01.6.2]"""
        return bool(self.repeat_inputs(item))

    def reprocessed_keys(self) -> tuple[tuple[Engine, str], ...]:
        """Every (engine, input) pair processed more than once.

        Surfaces duplicate invocation -- a named Orchestration failure mode
        [v2 4.12] -- across the whole recorded history.
        """
        with self._lock:
            return tuple(
                key for key, indices in self._by_key.items()
                if len(indices) > 1
            )

    # -- history ----------------------------------------------------------

    def for_cycle(self, cycle_id: int) -> tuple[ProcessingRecord, ...]:
        with self._lock:
            return tuple(
                self._records[i] for i in self._by_cycle.get(cycle_id, ())
            )

    def for_engine(self, engine: Engine) -> tuple[ProcessingRecord, ...]:
        with self._lock:
            return tuple(r for r in self._records if r.engine is engine)

    def cycles_recorded(self) -> tuple[int, ...]:
        with self._lock:
            return tuple(sorted(self._by_cycle))

    def has_cycle(self, cycle_id: int) -> bool:
        """Whether this cycle has already been committed. [T01.6.2]"""
        with self._lock:
            return cycle_id in self._by_cycle

    def all(self) -> tuple[ProcessingRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __iter__(self) -> Iterator[ProcessingRecord]:
        with self._lock:
            return iter(tuple(self._records))

    # -- append-only  [R-1 discipline for infrastructure state] -----------

    def delete(self, *_args, **_kwargs) -> None:
        """Never permitted. Processing state is append-only. [T01.6.2]"""
        raise ProcessingStateError(
            "processing state is append-only; deleting it would destroy the "
            "history that makes reprocessing detectable [T01.6.2]. No "
            "retention policy is specified for it [N-12 covers objects only]"
        )

    def update(self, *_args, **_kwargs) -> None:
        """Never permitted. Records are immutable. [T01.6.2]"""
        raise ProcessingStateError(
            "processing records are immutable; a repeat appends a new record "
            "rather than altering the previous one [T01.6.2]"
        )

    # -- isolation boundary  [CI-1, Art.V, N-10] --------------------------

    @property
    def is_intelligence(self) -> bool:
        """Always False. [CI-1, Art.V]"""
        return False

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Processing state never enters lineage. [N-10]"""
        return False

    @staticmethod
    def _key(engine: Engine, input_id: str) -> tuple[Engine, str]:
        if not isinstance(engine, Engine):
            raise ProcessingStateError(
                f"expected a known Engine, got {engine!r}"
            )
        if not isinstance(input_id, str):
            raise KnowledgeMutationError(
                f"input id must be an object id, got {type(input_id).__name__}; "
                f"processing state holds metadata only, never content "
                f"[IOM 2.5, AD-04]"
            )
        return (engine, input_id)


# ---------------------------------------------------------------------------
# Failure surfacing  [T01.6.3 -- N-10, N-17, N-8, AD-04]
# ---------------------------------------------------------------------------

class FailureMaskedError(OrchestrationError):
    """A failure was found reported as completion. [N-10, T01.6.3]

    The invariant N-10 exists to protect: "engine failure recorded, cycle
    continues, failure surfaced -- never masked as completion". Raised only
    by assert_not_masked(), which fails closed rather than letting a hidden
    failure pass as success.
    """


@dataclass(frozen=True)
class FailureSurface:
    """Makes recorded failures visible. Reports; never decides. [T01.6.3]

    A READ-ONLY VIEW. It owns no storage, holds no policy and mutates
    nothing: it is constructed over cycle records that already exist and
    answers questions about them. Orchestration owns no storage [v2 4.12],
    and detection must stay separate from policy, so this type deliberately
    has no power to act.

    WHAT IT DOES NOT DO. No retry, skip, halt, compensation or recovery --
    that is failure-handling policy, and no ratified source specifies one.
    N-10's header claims to close M-36, but M-36 is a compound marker
    (crosswalk: "policy + representation") and N-10's Decision section
    addresses representation only. The policy half is therefore treated as
    OPEN and failed closed. Implementing retry here would invent it.

    NO METRICS. Rates, thresholds, alerting and dashboards are observability
    (M-57), which is OPEN and scheduled at T09.1.2 -- the task this one
    blocks. This layer makes failures queryable; it does not decide what is
    worth watching. Counts are reported as facts, never compared to a limit.

    NO SEVERITY. No ratified severity or classification vocabulary exists.
    Failures are reported, not graded.
    """

    cycles: tuple[CycleRecord, ...] = ()

    def __post_init__(self) -> None:
        for cycle in self.cycles:
            if not isinstance(cycle, CycleRecord):
                raise OrchestrationError(
                    f"failure surface reads CycleRecords, got {cycle!r}"
                )

    @classmethod
    def over(cls, source: "Orchestrator | Iterable[CycleRecord]") -> "FailureSurface":
        """Build a surface over an Orchestrator's history or any cycles."""
        if isinstance(source, Orchestrator):
            return cls(cycles=source.cycles)
        return cls(cycles=tuple(source))

    # -- AC1: failed invocation distinguishable from empty result ---------

    def failed_invocations(self) -> tuple[tuple[int, InvocationRecord], ...]:
        """Every failed invocation, paired with its cycle id. [N-10]"""
        return tuple(
            (c.cycle_id, r)
            for c in self.cycles
            for r in c.invocations
            if r.outcome is InvocationOutcome.FAILED
        )

    def empty_invocations(self) -> tuple[tuple[int, InvocationRecord], ...]:
        """Invocations that ran correctly and found nothing. NOT failures.

        N-10: "A stage that produced nothing because it failed is
        distinguishable from a stage that produced nothing because it found
        nothing. This distinction is mandatory at every stage."
        """
        return tuple(
            (c.cycle_id, r)
            for c in self.cycles
            for r in c.invocations
            if r.outcome is InvocationOutcome.EMPTY
        )

    def produced_nothing(self) -> tuple[tuple[int, InvocationRecord], ...]:
        """Everything that yielded no object, failed or empty alike.

        Provided precisely so that the two reasons stay separable: this is
        the union, and it is never the same as either half. A caller that
        wants "no output" must not be forced to conflate the causes.
        """
        return tuple(
            sorted(
                self.failed_invocations() + self.empty_invocations(),
                key=lambda pair: (pair[0], pair[1].started_at),
            )
        )

    @property
    def failed_count(self) -> int:
        return len(self.failed_invocations())

    @property
    def empty_count(self) -> int:
        return len(self.empty_invocations())

    # -- AC2: failures do not silently halt the pipeline ------------------

    def cycles_with_failures(self) -> tuple[CycleRecord, ...]:
        """Cycles in which at least one engine failed, whatever the outcome.

        Reads CycleRecord.had_failure, which inspects the invocation records,
        NOT the cycle outcome. A cycle that failed and then hit a bound
        reports the bound; selecting on the outcome hid exactly that case.
        """
        return tuple(c for c in self.cycles if c.had_failure)

    def continued_past_failure(self) -> tuple[CycleRecord, ...]:
        """Cycles that kept going after a failure. [N-17, AC2]

        Evidence of the ratified behaviour: record, continue, surface.
        """
        return tuple(
            c for c in self.cycles_with_failures()
            if self._attempted_after_first_failure(c) > 0
        )

    def halted_at_failure(self) -> tuple[CycleRecord, ...]:
        """Cycles that stopped at a failure with work still unattempted.

        A cycle appears here only if it failed, attempted nothing further,
        AND left planned work unreached. That combination is what "silently
        halt" would look like. It is reported rather than prevented: a cycle
        may legitimately fail on its final item, and this layer judges
        nothing. Callers can see the distinction; the store never hides it.
        """
        halted = []
        for cycle in self.cycles_with_failures():
            if (
                self._attempted_after_first_failure(cycle) == 0
                and cycle.not_attempted_count > 0
            ):
                halted.append(cycle)
        return tuple(halted)

    @staticmethod
    def _attempted_after_first_failure(cycle: CycleRecord) -> int:
        seen_failure = False
        after = 0
        for record in cycle.invocations:
            if seen_failure and record.attempted:
                after += 1
            if record.failed:
                seen_failure = True
        return after

    # -- the never-masked invariant  [N-10, N-17] -------------------------

    def masked_cycles(self) -> tuple[CycleRecord, ...]:
        """Cycles containing a failure that their outcome does not reveal.

        This is the invariant N-10 exists to protect, checked mechanically
        rather than trusted. A cycle is masked when it contains a failed
        invocation but reports COMPLETED -- indistinguishable, to a caller
        reading the outcome alone, from a clean run.

        A bounded stop is NOT masking: WORK_LIMIT_REACHED and
        BUDGET_EXHAUSTED are not claims of success, and CycleRecord.
        had_failure still reports the failure. That distinction is why
        had_failure reads the invocation records.
        """
        return tuple(
            c for c in self.cycles
            if c.had_failure and c.outcome is CycleOutcome.COMPLETED
        )

    def is_masked_as_completion(self) -> bool:
        """Whether any failure is hidden behind a completion. [N-10]"""
        return bool(self.masked_cycles())

    def assert_not_masked(self) -> None:
        """Fail closed if any failure is reported as completion. [N-10]"""
        masked = self.masked_cycles()
        if masked:
            raise FailureMaskedError(
                f"{len(masked)} cycle(s) report COMPLETED while containing "
                f"engine failures: {[c.cycle_id for c in masked]}; a failure "
                f"masked as completion is what N-10 forbids [N-10, N-17]"
            )

    def every_failure_is_visible(self) -> bool:
        """Whether every failed invocation is reachable from the records.

        The counting form of the same invariant: the failures a caller can
        enumerate must equal the failures that actually occurred.
        """
        counted = sum(c.failed_count for c in self.cycles)
        return counted == self.failed_count

    # -- N-10 attribution  [T01.6.3] --------------------------------------

    def failure_records(self) -> tuple[FailureRecord, ...]:
        """Every failure record carried by the observed cycles. [N-10]"""
        return tuple(f for c in self.cycles for f in c.failures)

    def unattributed_failures(self) -> tuple[FailureRecord, ...]:
        """Failure records missing one of N-10's six identifications.

        Surfaced rather than suppressed: an attribution gap is itself a
        failure-surfacing defect, and hiding it would be the masking N-10
        forbids one level up.
        """
        return tuple(
            f for f in self.failure_records()
            if not f.satisfies_n10_attribution
        )

    def failures_for_engine(self, engine: Engine) -> tuple[FailureRecord, ...]:
        if not isinstance(engine, Engine):
            raise OrchestrationError(
                f"expected a known Engine, got {engine!r}"
            )
        return tuple(f for f in self.failure_records() if f.engine is engine)

    def engines_with_failures(self) -> tuple[Engine, ...]:
        """Which engines failed, in first-appearance order. [AD-04]

        Attribution, not judgement: it reports where failures arose and says
        nothing about why or what to do.
        """
        seen: list[Engine] = []
        for record in self.failure_records():
            if record.engine is not None and record.engine not in seen:
                seen.append(record.engine)
        return tuple(seen)

    # -- reported facts, never thresholds  [M-57 OPEN] --------------------

    def consecutive_failures(self) -> int:
        """Failures at the end of the observed history, unbroken.

        A FACT, not a trigger. No threshold is attached and no action is
        implied: deciding that some number of consecutive failures means
        something is failure-handling policy (M-36) and observability
        (M-57), both open.
        """
        streak = 0
        for cycle in reversed(self.cycles):
            if cycle.had_failure:
                streak += 1
            else:
                break
        return streak

    def failure_free(self) -> bool:
        return self.failed_count == 0

    def summary(self) -> dict[str, int]:
        """Plain counts. No rates, no thresholds, no judgement. [M-57 OPEN]"""
        return {
            "cycles": len(self.cycles),
            "cycles_with_failures": len(self.cycles_with_failures()),
            "failed_invocations": self.failed_count,
            "empty_invocations": self.empty_count,
            "masked_cycles": len(self.masked_cycles()),
            "unattributed_failures": len(self.unattributed_failures()),
        }

    # -- isolation  [N-10, Art.V, CI-1] -----------------------------------

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Failures never enter lineage. [N-10]"""
        return False

    @property
    def is_intelligence(self) -> bool:
        """Always False. Failures are operational facts. [N-10, Art.V]"""
        return False


# ---------------------------------------------------------------------------
# Sequencing enforcement  [T01.6.5 -- v2 4.12, N-14, N-6, AD-04]
# ---------------------------------------------------------------------------

class StateResolver(Protocol):
    """What Orchestration may ask the Knowledge Store. [v2 4.12, 5.5]

    "Read state only" (v2 5.5); "status metadata only, never content"
    (IOM 2.5). This protocol is the enforcement of that limit: there is no
    method here through which object content could travel. It answers what
    type an id denotes and what status it holds, and nothing else.

    Supplied by the caller, never constructed: Orchestration "does NOT own
    storage" (v2 4.12). A KnowledgeStore satisfies it structurally via
    resolve_type; the status accessor is optional.

    MUST READ THE STORE, NOT THE GRAPH. N-6: "the graph may lag the store"
    and "read-after-write on the index is not guaranteed". Resolving
    existence through a lagging index would reject work whose inputs
    genuinely exist.
    """

    def resolve_type(self, object_id: str) -> ObjectType | None:
        ...


@dataclass(frozen=True)
class InputCheck:
    """The verdict on one declared input. [T01.6.5]

    Metadata only: an id, a type and a status. No content.
    """

    input_id: str
    exists: bool
    actual_type: ObjectType | None
    expected_type: ObjectType | None
    status: ObjectStatus | None = None

    @property
    def type_matches(self) -> bool:
        if self.expected_type is None or self.actual_type is None:
            return False
        return self.actual_type is self.expected_type

    @property
    def satisfied(self) -> bool:
        """Existence AND the N-14 type. Status is reported, never required.

        The acceptance criterion says inputs must EXIST. No ratified source
        states a status precondition for invocation, so none is imposed --
        `status` is carried so a caller can apply its own rule. Inventing one
        here would be policy no document states. [A1]
        """
        return self.exists and self.type_matches

    @property
    def reason(self) -> str:
        if not self.exists:
            return f"input {self.input_id!r} does not exist"
        if not self.type_matches:
            actual = self.actual_type.value if self.actual_type else "unknown"
            expected = (
                self.expected_type.value if self.expected_type else "unknown"
            )
            return (
                f"input {self.input_id!r} is {actual}, but this engine "
                f"consumes {expected} [N-14]"
            )
        return ""


@dataclass(frozen=True)
class SequencingCheck:
    """Whether one work item may run. [T01.6.5]

    Frozen and itemised: a rejection names every input that failed and why,
    so a caller can see precisely what was not ready. Rejection is never a
    bare boolean.
    """

    engine: Engine
    inputs: tuple[InputCheck, ...]
    requires_inputs: bool

    @property
    def satisfied(self) -> bool:
        """Whether every declared input exists and is of the consumed type."""
        return all(check.satisfied for check in self.inputs)

    @property
    def unsatisfied(self) -> tuple[InputCheck, ...]:
        return tuple(c for c in self.inputs if not c.satisfied)

    @property
    def reasons(self) -> tuple[str, ...]:
        return tuple(c.reason for c in self.unsatisfied)

    @property
    def detail(self) -> str:
        if self.satisfied:
            return ""
        return (
            f"{self.engine.value} cannot run before its inputs exist: "
            + "; ".join(self.reasons)
        )

    @property
    def input_statuses(self) -> tuple[tuple[str, ObjectStatus | None], ...]:
        """Status of each input, reported for the caller's own rules. [A1]"""
        return tuple((c.input_id, c.status) for c in self.inputs)


@dataclass(frozen=True)
class SequencingGuard:
    """An engine cannot run before its inputs exist. [T01.6.5, v2 4.12]

    THE RESPONSIBILITY IS RATIFIED. PKP v2 4.12 makes Orchestration
    responsible for enforcing stage ordering and names the failure mode it
    prevents: "an engine runs on inputs that are not ready; pipeline
    integrity lost". Its permitted input is "the existence and status of
    objects awaiting processing", read from the Knowledge Store.

    THE INPUT MAPPING IS RATIFIED. N-14's direct-input table gives each
    engine exactly one consumed object type. Research is the sole engine with
    no input: Evidence is the pipeline root and its derives_from must be
    empty (E-V1). Nothing here is inferred.

    WHAT IT REFUSES TO DECIDE. It does NOT reject a work set for skipping
    stages -- OQ-10 is OPEN and scheduled at P6. It does NOT reject a work
    set for running stages out of pipeline order -- OQ-11 (backflow) is OPEN
    and scheduled at T07.3.8. Enforcing either would close an open question
    by implementation, phases early. A directive Orchestration executes the
    caller's plan (N-17); this guard validates that plan's inputs exist, and
    nothing more.

    IT NEVER REORDERS AND NEVER INFERS. No work item is moved, synthesised or
    inserted. An item whose inputs are absent is rejected in place, and the
    cycle continues.

    IT MAKES NO KNOWLEDGE JUDGEMENT. Type identity is structural. The guard
    reads no content, no confidence, no explanation and no lineage.
    """

    resolver: StateResolver

    def __post_init__(self) -> None:
        if not hasattr(self.resolver, "resolve_type"):
            raise SequencingError(
                f"state resolver must expose resolve_type(object_id), got "
                f"{type(self.resolver).__name__}; Orchestration reads state "
                f"only [v2 5.5]"
            )

    def check(self, item: WorkItem) -> SequencingCheck:
        """Whether this item's inputs exist. Reads state only. [v2 5.5]"""
        if not isinstance(item, WorkItem):
            raise SequencingError(f"expected a WorkItem, got {item!r}")

        expected = ENGINE_INPUT_TYPE.get(item.engine)
        if expected is None:
            if item.engine in ROOT_ENGINES:
                # Research consumes nothing: Evidence is the root. [N-14, E-V1]
                return SequencingCheck(item.engine, (), requires_inputs=False)
            raise SequencingError(
                f"{item.engine.value} has no direct input type in N-14 and is "
                f"not a root engine, so whether its inputs exist cannot be "
                f"determined; failing closed rather than assuming readiness "
                f"[N-14, v2 4.12]"
            )

        checks = tuple(
            self._check_input(oid, expected) for oid in item.input_ids
        )
        return SequencingCheck(item.engine, checks, requires_inputs=True)

    def _check_input(
        self, object_id: str, expected: ObjectType
    ) -> InputCheck:
        actual = self.resolver.resolve_type(object_id)
        return InputCheck(
            input_id=object_id,
            exists=actual is not None,
            actual_type=actual,
            expected_type=expected,
            status=self._status_of(object_id) if actual is not None else None,
        )

    def _status_of(self, object_id: str) -> ObjectStatus | None:
        """Status metadata, if the resolver offers it. Reported, not enforced."""
        accessor = getattr(self.resolver, "find", None)
        if accessor is None:
            return None
        stored = accessor(object_id)
        return getattr(stored, "status", None)

    def is_sequenced(self, item: WorkItem) -> bool:
        return self.check(item).satisfied

    def assert_sequenced(self, item: WorkItem) -> None:
        """Fail closed on a stage-order violation. [v2 4.12]"""
        result = self.check(item)
        if not result.satisfied:
            raise SequencingViolation(result.detail)

    def report(self, work_set: WorkSet) -> tuple[SequencingCheck, ...]:
        """Pre-flight check of a whole work set. Mutates nothing."""
        if not isinstance(work_set, WorkSet):
            raise SequencingError(f"expected a WorkSet, got {work_set!r}")
        return tuple(self.check(item) for item in work_set)

    def violations(self, work_set: WorkSet) -> tuple[SequencingCheck, ...]:
        return tuple(c for c in self.report(work_set) if not c.satisfied)

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Control state is not knowledge. [AD-04, N-10]"""
        return False


# ---------------------------------------------------------------------------
# Concurrency boundary verification  [T01.6.4 -- N-11, R-1]
# ---------------------------------------------------------------------------

class ConcurrencyViolation(OrchestrationError):
    """The N-11 boundary was crossed. [N-11]"""


@dataclass(frozen=True)
class ConcurrencyBoundary:
    """Proves the N-11 boundary held, from the record. [T01.6.4]

    A READ-ONLY verifier, mirroring FailureSurface: it owns no storage,
    schedules nothing and mutates nothing. It reads a concluded cycle and
    checks mechanically that what actually ran obeyed N-11 -- validation by
    extraction rather than by trusting the executor.

    It checks the three ratified acceptance criteria and nothing else. It
    holds no policy: it reports violations and, on request, fails closed.
    """

    cycle: CycleRecord

    def __post_init__(self) -> None:
        if not isinstance(self.cycle, CycleRecord):
            raise ConcurrencyError(
                f"expected a CycleRecord, got {self.cycle!r}"
            )

    # -- AC1: Problem-stage-onward writes serialised ----------------------

    def _attempted(self) -> tuple[InvocationRecord, ...]:
        return tuple(r for r in self.cycle.invocations if r.attempted)

    @staticmethod
    def _stage_of(record: InvocationRecord) -> int | None:
        return ENGINE_STAGE.get(record.engine)

    def serialised_records(self) -> tuple[InvocationRecord, ...]:
        """Attempted invocations in stages 3-9. [N-11]"""
        return tuple(
            r for r in self._attempted()
            if (s := self._stage_of(r)) is not None
            and ConcurrencyClass.for_stage(s) is ConcurrencyClass.SERIALISED
        )

    def concurrent_records(self) -> tuple[InvocationRecord, ...]:
        """Attempted invocations in stages 1-2. [N-11]"""
        return tuple(
            r for r in self._attempted()
            if (s := self._stage_of(r)) is not None
            and ConcurrencyClass.for_stage(s) is ConcurrencyClass.CONCURRENT
        )

    @staticmethod
    def _overlaps(a: InvocationRecord, b: InvocationRecord) -> bool:
        """Whether two invocations were in flight at the same instant."""
        return a.started_at < b.ended_at and b.started_at < a.ended_at

    def serialisation_violations(
        self,
    ) -> tuple[tuple[InvocationRecord, InvocationRecord], ...]:
        """Serialised invocations that overlapped in time. [AC1]

        Interpretation runs "one batch at a time"; two stage-3-onward
        invocations overlapping means it did not.
        """
        records = self.serialised_records()
        return tuple(
            (a, b)
            for i, a in enumerate(records)
            for b in records[i + 1:]
            if self._overlaps(a, b)
        )

    @property
    def interpretation_serialised(self) -> bool:
        """AC1: Problem-stage-onward writes serialised."""
        return not self.serialisation_violations()

    # -- AC2: stable population per batch ---------------------------------

    def barrier_violations(
        self,
    ) -> tuple[tuple[InvocationRecord, InvocationRecord], ...]:
        """Concurrent work still in flight while interpretation ran. [AC2]

        This is the property Pattern Intelligence depends on. If acquisition
        overlaps a serialised invocation, the population that invocation
        reasons over is changing beneath it, and N-11's "stable Problem
        population" does not hold.
        """
        return tuple(
            (c, s)
            for s in self.serialised_records()
            for c in self.concurrent_records()
            if self._overlaps(c, s)
        )

    @property
    def population_stable(self) -> bool:
        """AC2: Pattern Intelligence sees a stable population per batch."""
        return not self.barrier_violations()

    # -- AC3: version branching impossible --------------------------------

    def concurrent_same_type_writers(
        self,
    ) -> tuple[tuple[InvocationRecord, InvocationRecord], ...]:
        """Two overlapping invocations of the SAME engine. [AC3]

        R-1: non-branching supersession is guaranteed "only because a single
        engine holds create authority per type and interpretation is
        serialised under N-11". Create authority is one engine per type, so
        two overlapping invocations of one engine are the only way this layer
        could produce a branch.

        Stages 1-2 are exempt by ratified decision, not by oversight: N-11
        permits them to run concurrently because "operations are independent
        per source". Evidence and Fact concurrency is the decision's entire
        point, and R-1's guarantee is stated over the serialised stages.
        """
        records = self.serialised_records()
        return tuple(
            (a, b)
            for i, a in enumerate(records)
            for b in records[i + 1:]
            if a.engine is b.engine and self._overlaps(a, b)
        )

    @property
    def branching_impossible(self) -> bool:
        """AC3: version branching impossible."""
        return not self.concurrent_same_type_writers()

    # -- combined ----------------------------------------------------------

    @property
    def holds(self) -> bool:
        """Whether all three ratified criteria held for this cycle."""
        return (
            self.interpretation_serialised
            and self.population_stable
            and self.branching_impossible
        )

    def assert_holds(self) -> None:
        """Fail closed if the N-11 boundary was crossed. [N-11]"""
        problems: list[str] = []
        if not self.interpretation_serialised:
            problems.append(
                f"{len(self.serialisation_violations())} overlapping "
                f"serialised invocation(s) [AC1]"
            )
        if not self.population_stable:
            problems.append(
                f"{len(self.barrier_violations())} acquisition/interpretation "
                f"overlap(s); population not stable [AC2]"
            )
        if not self.branching_impossible:
            problems.append(
                f"{len(self.concurrent_same_type_writers())} concurrent "
                f"same-engine writer(s); version branching possible [AC3]"
            )
        if problems:
            raise ConcurrencyViolation(
                f"cycle {self.cycle.cycle_id} crossed the N-11 boundary: "
                + "; ".join(problems)
            )

    def unclassified_records(self) -> tuple[InvocationRecord, ...]:
        """Attempted invocations owning no pipeline stage.

        Surfaced rather than silently ignored: an invocation this layer
        cannot classify is one whose boundary compliance it cannot vouch for.
        """
        return tuple(
            r for r in self._attempted() if self._stage_of(r) is None
        )

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Control state is not knowledge. [AD-04, N-10]"""
        return False


# ---------------------------------------------------------------------------
# The orchestrator  [N-17, N-18, AD-04]
# ---------------------------------------------------------------------------

@dataclass
class Orchestrator:
    """Scheduled batch invocation. Sequences, never judges. [N-17, AD-04]

    Owns no storage and produces no Intelligence Object. It plans a cycle,
    invokes engines over a work set in the order the caller specified, and
    records what completed. Every cycle is bounded on both axes and every
    cycle terminates.

    Thread-safe: cycles are serialised under a lock, so two cycles never
    interleave. That is the minimum consistent with N-11's serialised
    interpretation; the finer per-stage concurrency boundary is T01.6.4 and
    is deliberately not implemented here.

    The failure store is supplied rather than created: N-10's records live
    outside the object model in the store built at T01.1.7, and Orchestration
    does not own storage. The processing store [T01.6.2] is supplied on the
    same rule. Both default to None, so an Orchestrator built before either
    existed behaves exactly as it did.

    When a processing store is supplied, every concluded cycle commits its
    ATTEMPTED invocations to it. The Orchestrator reads that state for
    nothing: it neither skips repeats nor reorders work, because suppression
    is scheduling policy under M-01 and M-36, both OPEN. Recording is what
    N-17 requires ("records what completed"); acting is not.
    """

    invoker: EngineInvoker
    bounds: CycleBounds = field(default_factory=CycleBounds)
    failure_store: object | None = None
    processing_store: ProcessingStateStore | None = None
    clock: Callable[[], datetime] = utc_now
    # N-11 concurrency [T01.6.4]. Default 1 = fully sequential, byte-identical
    # to the pre-T01.6.4 path. Above 1, stage 1-2 items in the same phase may
    # run in parallel; stages 3-9 remain one at a time whatever this is set to.
    #
    # NO DEFAULT ABOVE 1 IS PERMITTED. N-11's Known Tensions record that
    # "concurrency limits on acquisition need a cost bound that does not yet
    # exist" (M-56, OPEN). Deriving a worker count from CPU count or cost
    # would invent that bound, so the caller must state it explicitly.
    max_workers: int = 1
    # Sequencing enforcement [T01.6.5]. Supplied, never constructed:
    # Orchestration "does NOT own storage" (v2 4.12) and reads "state only"
    # (v2 5.5). Default None = no checking, byte-identical to the
    # pre-T01.6.5 path, because no engine exists to have inputs until P2.
    #
    # When supplied, each item is checked immediately before invocation and
    # an item whose inputs do not exist is REJECTED_OUT_OF_ORDER rather than
    # invoked. The cycle continues, exactly as it does past a failure.
    state_resolver: StateResolver | None = None

    _cycles: list[CycleRecord] = field(default_factory=list, init=False)
    _next_cycle_id: int = field(default=1, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)
    _running: bool = field(default=False, init=False)
    # Faults raised BY the failure store itself, collected per cycle so that
    # a persistence fault is surfaced rather than masking the failures it
    # was meant to record. [T01.6.3]
    _store_faults: list[FailureRecord] = field(default_factory=list, init=False)

    # -- cycle execution --------------------------------------------------

    def run_cycle(
        self,
        work_set: WorkSet,
        bounds: CycleBounds | None = None,
    ) -> CycleRecord:
        """Execute one bounded cycle over the work set. [N-17]

        Terminates in exactly one CycleOutcome. Bounds are checked BEFORE each
        invocation, so a cycle can never exceed its work limit and can only
        exceed its wall-clock budget by the duration of a single in-flight
        invocation -- Orchestration cannot interrupt an engine without
        inventing a cancellation policy M-36 does not define.

        An engine raising is recorded and the cycle CONTINUES, per N-10.
        Retry, skip and halt policies are M-36 and are not implemented.

        If a processing store was supplied, the concluded cycle is committed
        to it [T01.6.2]. The commit happens AFTER the cycle is appended to
        history, so a store that refuses the commit cannot erase the record
        of a cycle that genuinely ran; the refusal then propagates rather
        than being swallowed, because a processing store that silently
        dropped a cycle would leave the platform believing work was never
        done. The cycle remains retrievable from `cycles`.
        """
        if not isinstance(work_set, WorkSet):
            raise WorkSetError(f"expected a WorkSet, got {work_set!r}")
        self._require_valid_workers()
        active_bounds = bounds if bounds is not None else self.bounds
        if not isinstance(active_bounds, CycleBounds):
            raise CycleBoundError(
                f"expected CycleBounds, got {active_bounds!r}; every cycle is "
                f"bounded [N-17]"
            )

        with self._lock:
            if self._running:
                raise CycleStateError(
                    "a cycle is already running; cycles are serialised so "
                    "that interpretation sees a stable population [N-11]"
                )
            self._running = True
            cycle_id = self._next_cycle_id
            self._next_cycle_id += 1

        try:
            record = self._execute(cycle_id, work_set, active_bounds)
        finally:
            with self._lock:
                self._running = False

        with self._lock:
            self._cycles.append(record)
        if self.processing_store is not None:
            self.processing_store.record_cycle(record)
        return record

    def _execute(
        self, cycle_id: int, work_set: WorkSet, bounds: CycleBounds
    ) -> CycleRecord:
        started_at = self.clock()
        failures: list[FailureRecord] = []
        self._store_faults = []

        if self.max_workers > 1:
            invocations, outcome = self._execute_phased(
                cycle_id, work_set, bounds, failures, started_at
            )
        else:
            invocations, outcome = self._execute_sequential(
                cycle_id, work_set, bounds, failures, started_at
            )

        ended_at = self.clock()
        if not outcome.is_bounded_stop and any(r.failed for r in invocations):
            outcome = CycleOutcome.FAILED

        # A fault in the failure store is itself a failure and travels with
        # the cycle, so persistence problems are surfaced rather than
        # silently losing the failures they were meant to record. [T01.6.3]
        failures.extend(self._store_faults)
        self._store_faults = []

        return CycleRecord(
            cycle_id=cycle_id,
            outcome=outcome,
            bounds=bounds,
            invocations=tuple(invocations),
            failures=tuple(failures),
            planned_items=len(work_set),
            started_at=started_at,
            ended_at=ended_at,
            description=work_set.description,
        )

    def _execute_sequential(
        self,
        cycle_id: int,
        work_set: WorkSet,
        bounds: CycleBounds,
        failures: list[FailureRecord],
        started_at: datetime,
    ) -> tuple[list[InvocationRecord], CycleOutcome]:
        """The pre-T01.6.4 path, unchanged. Used whenever max_workers == 1.

        Kept intact rather than folded into the phased path: N-11 says
        acquisition "MAY run concurrently", so sequential execution remains
        fully conformant, and the default must not change behaviour.
        """
        invocations: list[InvocationRecord] = []
        outcome = CycleOutcome.COMPLETED
        attempted = 0

        for item in work_set:
            # -- bounds checked BEFORE the invocation. [N-17]
            if attempted >= bounds.max_work_items:
                outcome = CycleOutcome.WORK_LIMIT_REACHED
                invocations.extend(
                    self._not_attempted(work_set.items[len(invocations):], started_at)
                )
                break
            elapsed = (self.clock() - started_at).total_seconds()
            if elapsed >= bounds.wall_clock_budget_seconds:
                outcome = CycleOutcome.BUDGET_EXHAUSTED
                invocations.extend(
                    self._not_attempted(work_set.items[len(invocations):], started_at)
                )
                break

            invocations.append(
                self._invoke(item, failures, cycle_id, len(invocations))
            )
            attempted += 1

        return invocations, outcome

    def _execute_phased(
        self,
        cycle_id: int,
        work_set: WorkSet,
        bounds: CycleBounds,
        failures: list[FailureRecord],
        started_at: datetime,
    ) -> tuple[list[InvocationRecord], CycleOutcome]:
        """Execute the N-11 plan: parallel stages 1-2, serialised 3-9.

        THE BOUNDARY IS A BARRIER. Phases run strictly in order and never
        overlap, so every concurrent invocation of a phase has completed
        before the next phase begins. A serialised item therefore always sees
        a population that nothing is still writing into -- the "stable
        Problem population" N-11 promises Pattern Intelligence.

        DETERMINISM IS PRESERVED WHERE THE PLATFORM CONTROLS IT [N-4, A1].
        Results are written back BY INDEX, so the recorded invocation order is
        always work-set order however the threads finish. Two runs over the
        same work set produce the same record ORDER; engine OUTPUTS remain
        non-deterministic, which N-4 ratifies and this task does not change.

        BOUNDS ARE CHECKED BEFORE DISPATCH, per phase, exactly as the
        sequential path checks before each invocation. A phase is admitted
        whole or not at all, because admitting half a concurrent phase would
        make the bound depend on thread scheduling.
        """
        slots: list[InvocationRecord | None] = [None] * len(work_set.items)
        outcome = CycleOutcome.COMPLETED
        attempted = 0
        stopped = False

        for phase in work_set.concurrency_plan():
            remaining = bounds.max_work_items - attempted
            if remaining <= 0:
                outcome = CycleOutcome.WORK_LIMIT_REACHED
                stopped = True
                break
            elapsed = (self.clock() - started_at).total_seconds()
            if elapsed >= bounds.wall_clock_budget_seconds:
                outcome = CycleOutcome.BUDGET_EXHAUSTED
                stopped = True
                break

            # DEFECT FIX [T01.6.4]. A phase larger than the remaining budget
            # used to be refused WHOLE, so a single concurrent phase of 12
            # under a limit of 4 ran nothing at all -- starvation, a named
            # failure mode [v2 4.12], and a silent divergence from the
            # sequential path, which attempts exactly max_work_items.
            #
            # The bound counts WORK, not phases, so a phase is admitted up to
            # the remaining budget. The prefix taken is the first N indices in
            # caller order, which is what the sequential path would have run.
            admitted = phase.item_indices[:remaining]
            if len(admitted) < len(phase):
                outcome = CycleOutcome.WORK_LIMIT_REACHED
                stopped = True

            if phase.is_parallel and len(admitted) > 1:
                self._run_parallel(
                    ExecutionPhase(phase.concurrency_class, admitted),
                    work_set, slots, failures, cycle_id,
                )
            else:
                for index in admitted:
                    slots[index] = self._invoke(
                        work_set.items[index], failures, cycle_id, index
                    )
            attempted += len(admitted)
            if stopped:
                break

        invocations = [r for r in slots if r is not None]
        if stopped:
            unreached = [
                work_set.items[i] for i, r in enumerate(slots) if r is None
            ]
            invocations.extend(self._not_attempted(unreached, started_at))
        return invocations, outcome

    def _run_parallel(
        self,
        phase: "ExecutionPhase",
        work_set: WorkSet,
        slots: list[InvocationRecord | None],
        failures: list[FailureRecord],
        cycle_id: int,
    ) -> None:
        """Run one concurrent phase. Stages 1-2 only. [N-11]

        `failures` is appended to from worker threads, so it is guarded: list
        mutation is not a documented atomic, and a lost failure record would
        breach N-10.

        A worker never raises: _invoke already converts any engine fault into
        a FAILED record [N-10, T01.6.3]. The pool is therefore only a
        dispatch mechanism and cannot introduce a new failure path.
        """
        collected: dict[int, InvocationRecord] = {}
        guard = threading.Lock()
        local_failures: list[FailureRecord] = []

        def run(index: int) -> None:
            own: list[FailureRecord] = []
            record = self._invoke(
                work_set.items[index], own, cycle_id, index
            )
            with guard:
                collected[index] = record
                local_failures.extend(own)

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            list(pool.map(run, phase.item_indices))

        # Written back by index and in phase order: the recorded history is
        # independent of completion order. [N-4, determinism]
        for index in phase.item_indices:
            slots[index] = collected[index]
        failures.extend(local_failures)

    def _sequencing_rejection(
        self, item: WorkItem, cycle_id: int, invocation_index: int
    ) -> InvocationRecord | None:
        """Reject an item whose inputs do not exist. [T01.6.5, v2 4.12]

        Returns a REJECTED_OUT_OF_ORDER record, or None if the item may run.

        The rejection is NOT an engine failure. No engine was invoked, so
        recording one would attribute a planning error to an engine that
        never executed and would blur N-10's empty/failed distinction. It is
        recorded on the cycle, visible and attributable, and the cycle
        continues -- the same shape N-17 prescribes for failures.

        No retry, no deferral, no reordering: M-36's policy half is OPEN and
        reordering would breach the directive control model [N-17, AD-04].
        """
        if self.state_resolver is None:
            return None

        # DEFECT FIX [T01.6.5]. A resolver that raises used to propagate out
        # of _invoke, out of _execute and out of run_cycle, discarding the
        # ENTIRE cycle record: work that had already run became invisible and
        # remaining work was never attempted. Identical in shape to the
        # failure-store defect fixed at T01.6.3, and forbidden for the same
        # reason -- a fault in the readiness check must never be the reason a
        # cycle disappears.
        #
        # FAIL CLOSED. If readiness cannot be determined, the engine does not
        # run: v2 4.12's stage-order violation is what happens when an engine
        # runs on inputs that are not ready, and an unanswerable check cannot
        # establish that they are. The item is rejected with the reason
        # stated, not silently admitted and not recorded as an engine failure.
        try:
            result = SequencingGuard(self.state_resolver).check(item)
            satisfied, detail = result.satisfied, result.detail
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException as exc:
            satisfied = False
            detail = (
                f"sequencing could not be determined for "
                f"{item.engine.value}: {_describe_exception(exc)}; failing "
                f"closed rather than running an engine whose inputs may not "
                f"exist [v2 4.12]"
            )
        if satisfied:
            return None

        stamp = self.clock()
        return InvocationRecord(
            engine=item.engine,
            input_ids=item.input_ids,
            engine_configuration_ref=item.engine_configuration_ref,
            outcome=InvocationOutcome.REJECTED_OUT_OF_ORDER,
            produced_ids=(),
            detail=detail,
            started_at=stamp,
            ended_at=stamp,
        )

    def _require_valid_workers(self) -> None:
        """max_workers must be a positive integer. [N-11, M-56 OPEN]"""
        if isinstance(self.max_workers, bool) or not isinstance(
            self.max_workers, int
        ):
            raise ConcurrencyError(
                f"max_workers must be an integer, got {self.max_workers!r}"
            )
        if self.max_workers < 1:
            raise ConcurrencyError(
                f"max_workers must be at least 1, got {self.max_workers}; "
                f"a cycle with no workers would never terminate [N-17]"
            )

    def _invoke(
        self,
        item: WorkItem,
        failures: list[FailureRecord],
        cycle_id: int,
        invocation_index: int,
    ) -> InvocationRecord:
        """Invoke one engine. Never raises. [N-10]

        An engine failure is an operational fact, not a reason to abandon the
        cycle. It is recorded, surfaced, and the cycle continues -- never
        masked as completion.

        SEQUENCING IS CHECKED FIRST [T01.6.5]. If a state resolver was
        supplied and this item's inputs do not exist, the engine is NOT
        invoked: "an engine cannot run before its inputs exist". The check
        happens here, at the single point through which both the sequential
        and the parallel path invoke, so no execution path can bypass it.

        It is checked immediately before invocation rather than at plan time
        so that an input written by an earlier phase of the same cycle is
        visible -- observation of committed state, never inference about
        what a later engine might produce.
        """
        rejection = self._sequencing_rejection(item, cycle_id, invocation_index)
        if rejection is not None:
            return rejection

        started_at = self.clock()
        try:
            result = self.invoker(item)
            if not isinstance(result, InvocationResult):
                raise InvocationError(
                    f"engine returned {type(result).__name__}, expected an "
                    f"InvocationResult; Orchestration moves work, not "
                    f"knowledge [AD-04, v2 4.12]"
                )
            outcome, produced, detail = (
                result.outcome, result.produced_ids, result.detail
            )
        except (KeyboardInterrupt, SystemExit):
            # NOT an engine failure. These are operator and process control
            # signals, and recording one as an engine failure would
            # misattribute a shutdown to the engine -- the mirror image of
            # masking. Propagated untouched; nothing already recorded is
            # lost, because prior invocations are already in the list.
            raise
        except BaseException as exc:  # engine failure is data, not an escape
            outcome, produced = InvocationOutcome.FAILED, ()
            detail = _describe_exception(exc)
            failures.append(
                self._failure_record(item, detail, cycle_id, invocation_index)
            )

        return InvocationRecord(
            engine=item.engine,
            input_ids=item.input_ids,
            engine_configuration_ref=item.engine_configuration_ref,
            outcome=outcome,
            produced_ids=produced,
            detail=detail,
            started_at=started_at,
            ended_at=self.clock(),
        )

    def _not_attempted(
        self, remaining: Sequence[WorkItem], at: datetime
    ) -> list[InvocationRecord]:
        """Record unattempted work so a bounded stop is never silent. [N-17]

        Starvation is a named failure mode. A cycle that stopped on a bound
        must say precisely what it did not reach.
        """
        stamp = self.clock()
        return [
            InvocationRecord(
                engine=item.engine,
                input_ids=item.input_ids,
                engine_configuration_ref=item.engine_configuration_ref,
                outcome=InvocationOutcome.NOT_ATTEMPTED,
                produced_ids=(),
                detail="cycle bound reached before this item",
                started_at=stamp,
                ended_at=stamp,
            )
            for item in remaining
        ]

    def _failure_record(
        self,
        item: WorkItem,
        detail: str,
        cycle_id: int,
        invocation_index: int,
    ) -> FailureRecord:
        """Build an N-10 failure record and store it if a store was supplied.

        The record is attributable to the engine and the invocation, which is
        T01.1.7's acceptance criterion. object_id names the engine because no
        object was produced -- the failure is the reason there is none.

        DEFECT FIX [T01.6.3]. N-10 requires every failure record to identify
        the engine, the invocation and the inputs attempted. All three were
        being discarded here despite being in hand: the engine survived only
        as a substring of object_id, and which inputs were attempted was
        unrecoverable. A failure whose attempted inputs cannot be named is not
        surfaced in the sense N-10 requires. The invocation is identified by
        the cycle it belonged to (N-17's per-cycle unit) and its ordinal
        within that cycle; no new identifier scheme is invented.
        """
        record = FailureRecord(
            object_id=f"engine:{item.engine.value}",
            object_type=item.produces or ObjectType.EVIDENCE,
            failed_rules=(
                RuleResult("ENGINE-FAILURE", RuleOutcome.FAIL, detail),
            ),
            recorded_at=self.clock(),
            engine_configuration_ref=item.engine_configuration_ref,
            engine=item.engine,
            cycle_id=cycle_id,
            invocation_index=invocation_index,
            input_ids=item.input_ids,
        )
        # DEFECT FIX [T01.6.3]. A raising failure store used to propagate out
        # of _invoke, out of _execute and out of run_cycle, discarding the
        # ENTIRE cycle record: every engine failure in that cycle became
        # invisible and remaining work was never attempted. A fault in the
        # place failures are written must never be the reason a failure
        # disappears -- that is total masking, the worst form of what N-10
        # forbids.
        #
        # The record is always returned and always reaches the CycleRecord,
        # so the failure stays surfaced through FailureSurface even when
        # persistence fails. The persistence fault is itself recorded as a
        # second failure on the same invocation, so it is not swallowed
        # either. No retry is attempted [M-36 policy half OPEN].
        if self.failure_store is not None:
            try:
                self.failure_store.record(record)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException as exc:
                self._store_faults.append(
                    FailureRecord(
                        object_id=f"failure-store:{item.engine.value}",
                        object_type=item.produces or ObjectType.EVIDENCE,
                        failed_rules=(
                            RuleResult(
                                "FAILURE-STORE-UNAVAILABLE",
                                RuleOutcome.FAIL,
                                _describe_exception(exc),
                            ),
                        ),
                        recorded_at=self.clock(),
                        engine_configuration_ref=item.engine_configuration_ref,
                        engine=item.engine,
                        cycle_id=cycle_id,
                        invocation_index=invocation_index,
                        input_ids=item.input_ids,
                    )
                )
        return record

    # -- history ----------------------------------------------------------

    @property
    def cycles(self) -> tuple[CycleRecord, ...]:
        with self._lock:
            return tuple(self._cycles)

    @property
    def cycle_count(self) -> int:
        with self._lock:
            return len(self._cycles)

    def cycle(self, cycle_id: int) -> CycleRecord | None:
        with self._lock:
            for record in self._cycles:
                if record.cycle_id == cycle_id:
                    return record
            return None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def produces_intelligence_objects(self) -> bool:
        """Always False. Orchestration moves work, not knowledge. [AD-04]"""
        return False

    def failed_cycles(self) -> tuple[CycleRecord, ...]:
        """Cycles in which an engine failed. Never masked. [N-10]

        Selects on CycleRecord.had_failure, which reads the invocation
        records, rather than on the outcome. A cycle that both failed and hit
        a bound reports the bound as its outcome but must still appear here:
        selecting on the outcome hid exactly that case.
        """
        with self._lock:
            return tuple(c for c in self._cycles if c.had_failure)

    def bounded_stops(self) -> tuple[CycleRecord, ...]:
        """Cycles that stopped on a bound rather than finishing. [N-17]"""
        with self._lock:
            return tuple(c for c in self._cycles if c.outcome.is_bounded_stop)
