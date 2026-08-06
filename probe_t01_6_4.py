"""Adversarial probe for T01.6.4 concurrency boundary. Attack before testing."""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.configuration import FailureStore
from oip.enums import CONCURRENT_STAGES, ENGINE_STAGE, Engine, ObjectType
from oip.orchestration import (
    ConcurrencyBoundary, ConcurrencyClass, ConcurrencyError,
    ConcurrencyViolation, CycleBounds, CycleOutcome, ExecutionPhase,
    FailureSurface, InvocationOutcome, InvocationResult, Orchestrator,
    ProcessingStateStore, WorkItem, WorkSet,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
FAILS: list[str] = []

ACQ = (Engine.RESEARCH, Engine.FACT_EXTRACTION)
INTERP = (Engine.PROBLEM_INTELLIGENCE, Engine.PATTERN_INTELLIGENCE,
          Engine.OPPORTUNITY_INTELLIGENCE, Engine.SOLUTION_INTELLIGENCE,
          Engine.VALIDATION, Engine.FEEDBACK)


def probe(name):
    def deco(fn):
        try:
            fn(); print(f"  ok   {name}")
        except AssertionError as e:
            FAILS.append(f"{name}: {e}"); print(f"  FAIL {name}: {e}")
        except Exception as e:
            FAILS.append(f"{name}: {type(e).__name__}: {e}")
            print(f"  ERR  {name}: {type(e).__name__}: {e}")
        return fn
    return deco


def wi(n=1, engine=Engine.RESEARCH, **kw):
    return WorkItem(engine, (f"s-{n}",), "cfg", **kw)


def empty(_i):
    return InvocationResult.empty()


class Tracker:
    """Records true in-flight overlap, independent of the recorded timestamps."""

    def __init__(self, hold=0.01):
        self.hold = hold
        self.lock = threading.Lock()
        self.active: dict[Engine, int] = {}
        self.max_active = 0
        self.overlap_acq_interp = False
        self.max_serialised = 0
        self.same_engine_overlap = False

    def __call__(self, item):
        with self.lock:
            self.active[item.engine] = self.active.get(item.engine, 0) + 1
            total = sum(self.active.values())
            self.max_active = max(self.max_active, total)
            ser = sum(v for e, v in self.active.items() if e in INTERP)
            acq = sum(v for e, v in self.active.items() if e in ACQ)
            self.max_serialised = max(self.max_serialised, ser)
            if ser and acq:
                self.overlap_acq_interp = True
            if any(v > 1 for e, v in self.active.items() if e in INTERP):
                self.same_engine_overlap = True
        time.sleep(self.hold)
        with self.lock:
            self.active[item.engine] -= 1
        return InvocationResult.empty()


print("== A. stage classification is exactly N-11's table ==")


@probe("stages 1-2 concurrent, 3-9 serialised")
def _():
    assert wi(1, Engine.RESEARCH).concurrency_class is ConcurrencyClass.CONCURRENT
    assert wi(1, Engine.FACT_EXTRACTION).concurrency_class is ConcurrencyClass.CONCURRENT
    for e in INTERP:
        assert wi(1, e).is_serialised, e


@probe("every engine's stage matches IOM 2.6")
def _():
    expected = {Engine.RESEARCH: 1, Engine.FACT_EXTRACTION: 2,
                Engine.PROBLEM_INTELLIGENCE: 3, Engine.PATTERN_INTELLIGENCE: 4,
                Engine.OPPORTUNITY_INTELLIGENCE: 5,
                Engine.SOLUTION_INTELLIGENCE: 6, Engine.VALIDATION: 7,
                Engine.FEEDBACK: 9}
    assert ENGINE_STAGE == expected, ENGINE_STAGE
    assert CONCURRENT_STAGES == frozenset({1, 2})


@probe("Orchestration fails closed -- owns no stage")
def _():
    try:
        wi(1, Engine.ORCHESTRATION).concurrency_class
        assert False, "classified an engine that owns no stage"
    except ConcurrencyError:
        pass


@probe("stage 8 reachable only by object type, and serialised [C-02]")
def _():
    it = wi(1, Engine.FEEDBACK, produces=ObjectType.EXECUTION_RECORD)
    assert it.stage == 8
    assert it.is_serialised
    assert Engine.ORCHESTRATION not in ENGINE_STAGE


@probe("produces overrides engine for stage resolution")
def _():
    it = wi(1, Engine.RESEARCH, produces=ObjectType.PROBLEM)
    assert it.stage == 3 and it.is_serialised, "object type must win"


@probe("orchestration item with produces is classifiable")
def _():
    it = wi(1, Engine.ORCHESTRATION, produces=ObjectType.EVIDENCE)
    assert it.is_concurrent


print("== B. phase planning preserves caller order ==")


@probe("adjacent concurrent items collapse; serialised stand alone")
def _():
    ws = WorkSet(items=(wi(0), wi(1, Engine.FACT_EXTRACTION),
                        wi(2, Engine.PROBLEM_INTELLIGENCE),
                        wi(3, Engine.PATTERN_INTELLIGENCE), wi(4)))
    plan = ws.concurrency_plan()
    assert [(p.concurrency_class.value, p.item_indices) for p in plan] == [
        ("CONCURRENT", (0, 1)), ("SERIALISED", (2,)),
        ("SERIALISED", (3,)), ("CONCURRENT", (4,))]


@probe("every index appears exactly once, in order")
def _():
    import random
    engines = list(ENGINE_STAGE)
    for _ in range(200):
        items = tuple(wi(n, random.choice(engines)) for n in range(12))
        plan = WorkSet(items=items).concurrency_plan()
        flat = [i for p in plan for i in p.item_indices]
        assert flat == list(range(12)), flat


@probe("serialised phase may never hold more than one item")
def _():
    try:
        ExecutionPhase(ConcurrencyClass.SERIALISED, (0, 1))
        assert False, "accepted a multi-item serialised phase"
    except ConcurrencyError:
        pass


@probe("empty phase refused")
def _():
    try:
        ExecutionPhase(ConcurrencyClass.CONCURRENT, ())
        assert False
    except ConcurrencyError:
        pass


@probe("empty work set plans nothing")
def _():
    assert WorkSet(items=()).concurrency_plan() == ()


@probe("all-serialised work set gives one phase each")
def _():
    ws = WorkSet(items=tuple(wi(n, Engine.PROBLEM_INTELLIGENCE) for n in range(5)))
    plan = ws.concurrency_plan()
    assert len(plan) == 5 and all(len(p) == 1 for p in plan)


print("== C. the barrier actually holds under real threads ==")


@probe("interpretation never overlaps acquisition")
def _():
    t = Tracker()
    ws = WorkSet(items=(
        wi(0), wi(1), wi(2, Engine.FACT_EXTRACTION), wi(3),
        wi(4, Engine.PROBLEM_INTELLIGENCE),
        wi(5), wi(6),
        wi(7, Engine.PATTERN_INTELLIGENCE),
    ))
    Orchestrator(invoker=t, max_workers=4).run_cycle(ws)
    assert not t.overlap_acq_interp, "acquisition ran during interpretation"


@probe("never two serialised invocations in flight")
def _():
    t = Tracker()
    ws = WorkSet(items=tuple(
        wi(n, INTERP[n % len(INTERP)]) for n in range(10)))
    Orchestrator(invoker=t, max_workers=8).run_cycle(ws)
    assert t.max_serialised <= 1, f"{t.max_serialised} serialised in flight"


@probe("no two invocations of the SAME serialised engine overlap [AC3]")
def _():
    t = Tracker()
    ws = WorkSet(items=tuple(
        wi(n, Engine.PROBLEM_INTELLIGENCE) for n in range(8)))
    Orchestrator(invoker=t, max_workers=8).run_cycle(ws)
    assert not t.same_engine_overlap, "version branching was possible"
    assert t.max_active <= 1


@probe("acquisition really does run in parallel")
def _():
    t = Tracker(hold=0.02)
    ws = WorkSet(items=tuple(wi(n) for n in range(8)))
    Orchestrator(invoker=t, max_workers=4).run_cycle(ws)
    assert t.max_active > 1, "concurrent stages never actually overlapped"


@probe("max_workers=1 keeps everything sequential")
def _():
    t = Tracker(hold=0.001)
    ws = WorkSet(items=tuple(wi(n) for n in range(6)))
    Orchestrator(invoker=t, max_workers=1).run_cycle(ws)
    assert t.max_active == 1


@probe("boundary verifier confirms all three criteria")
def _():
    ws = WorkSet(items=(
        wi(0), wi(1), wi(2, Engine.PROBLEM_INTELLIGENCE),
        wi(3, Engine.PATTERN_INTELLIGENCE), wi(4)))
    o = Orchestrator(invoker=Tracker(hold=0.005), max_workers=4)
    r = o.run_cycle(ws)
    b = ConcurrencyBoundary(r)
    assert b.interpretation_serialised, b.serialisation_violations()
    assert b.population_stable, b.barrier_violations()
    assert b.branching_impossible, b.concurrent_same_type_writers()
    assert b.holds
    b.assert_holds()


print("== D. determinism of the record [N-4, A1] ==")


@probe("recorded order is work-set order regardless of completion order")
def _():
    import random

    def jittery(i):
        time.sleep(random.uniform(0, 0.01))
        return InvocationResult.empty()

    ws = WorkSet(items=tuple(wi(n) for n in range(12)))
    for _ in range(5):
        r = Orchestrator(invoker=jittery, max_workers=6).run_cycle(ws)
        assert [x.input_ids[0] for x in r.invocations] == \
            [f"s-{n}" for n in range(12)]


@probe("sequential and parallel produce the same record shape")
def _():
    ws = WorkSet(items=(wi(0), wi(1), wi(2, Engine.PROBLEM_INTELLIGENCE), wi(3)))
    a = Orchestrator(invoker=empty, max_workers=1).run_cycle(ws)
    b = Orchestrator(invoker=empty, max_workers=4).run_cycle(ws)
    assert [x.input_ids for x in a.invocations] == [x.input_ids for x in b.invocations]
    assert [x.engine for x in a.invocations] == [x.engine for x in b.invocations]
    assert [x.outcome for x in a.invocations] == [x.outcome for x in b.invocations]
    assert a.attempted_count == b.attempted_count


@probe("invocation index matches position under parallelism")
def _():
    fs = FailureStore()
    ws = WorkSet(items=tuple(wi(n) for n in range(6)))
    Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                 failure_store=fs, max_workers=4).run_cycle(ws)
    for rec in fs.all():
        assert rec.input_ids == (f"s-{rec.invocation_index}",), rec


print("== E. bounds under concurrency [N-17] ==")


@probe("work limit still enforced")
def _():
    ws = WorkSet(items=tuple(wi(n) for n in range(20)))
    r = Orchestrator(invoker=empty, max_workers=4,
                     bounds=CycleBounds(max_work_items=6)).run_cycle(ws)
    assert r.attempted_count <= 6, r.attempted_count
    assert r.outcome is CycleOutcome.WORK_LIMIT_REACHED
    assert r.attempted_count + r.not_attempted_count == 20


@probe("bound is phase-atomic, never partial")
def _():
    ws = WorkSet(items=tuple(wi(n) for n in range(10)))
    for limit in range(1, 11):
        r = Orchestrator(invoker=empty, max_workers=4,
                         bounds=CycleBounds(max_work_items=limit)).run_cycle(ws)
        assert r.attempted_count <= limit, (limit, r.attempted_count)


@probe("unattempted work still recorded")
def _():
    ws = WorkSet(items=tuple(wi(n) for n in range(12)))
    r = Orchestrator(invoker=empty, max_workers=4,
                     bounds=CycleBounds(max_work_items=4)).run_cycle(ws)
    assert r.not_attempted_count == 8
    assert all(x.outcome is InvocationOutcome.NOT_ATTEMPTED
               for x in r.invocations if not x.attempted)


@probe("budget exhaustion still terminates")
def _():
    ticks = iter([T0 + timedelta(seconds=i * 100) for i in range(200)])
    ws = WorkSet(items=tuple(wi(n, Engine.PROBLEM_INTELLIGENCE) for n in range(8)))
    r = Orchestrator(invoker=empty, max_workers=4,
                     bounds=CycleBounds(wall_clock_budget_seconds=1.0),
                     clock=lambda: next(ticks)).run_cycle(ws)
    assert r.outcome is CycleOutcome.BUDGET_EXHAUSTED


print("== F. failure semantics preserved [N-10, T01.6.3] ==")


@probe("failures in a parallel phase all recorded, none masked")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("boom")),
                     failure_store=fs, max_workers=4)
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(12))))
    assert r.failed_count == 12, r.failed_count
    assert len(fs) == 12
    s = FailureSurface.over(o)
    assert s.failed_count == 12
    assert s.masked_cycles() == ()
    s.assert_not_masked()


@probe("a failing concurrent item does not stop the phase")
def _():
    seen = []
    lock = threading.Lock()

    def flaky(i):
        with lock:
            seen.append(i.input_ids[0])
        if i.input_ids[0] == "s-0":
            raise RuntimeError("boom")
        return InvocationResult.empty()

    r = Orchestrator(invoker=flaky, max_workers=4).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(8))))
    assert len(seen) == 8, seen
    assert r.attempted_count == 8


@probe("failure in a concurrent phase does not block the next phase")
def _():
    def flaky(i):
        if i.engine is Engine.RESEARCH:
            raise RuntimeError("boom")
        return InvocationResult.empty()

    r = Orchestrator(invoker=flaky, max_workers=4).run_cycle(WorkSet(items=(
        wi(0), wi(1), wi(2, Engine.PROBLEM_INTELLIGENCE))))
    assert r.attempted_count == 3
    assert r.failed_count == 2


@probe("empty vs failed still distinguishable under parallelism")
def _():
    def mixed(i):
        n = int(i.input_ids[0].split("-")[1])
        if n % 2:
            raise RuntimeError("boom")
        return InvocationResult.empty()

    o = Orchestrator(invoker=mixed, max_workers=4)
    o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(10))))
    s = FailureSurface.over(o)
    assert s.failed_count == 5 and s.empty_count == 5


@probe("no failure record lost under contention")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     failure_store=fs, max_workers=8)
    for _ in range(10):
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(20))))
    assert len(fs) == 200, len(fs)
    assert fs.unattributed() == ()


print("== G. processing state under concurrency [T01.6.2] ==")


@probe("every attempted item recorded exactly once")
def _():
    ps = ProcessingStateStore()
    o = Orchestrator(invoker=empty, processing_store=ps, max_workers=6)
    o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(50))))
    assert len(ps) == 50
    assert all(ps.attempt_count(Engine.RESEARCH, f"s-{n}") == 1 for n in range(50))
    assert ps.reprocessed_keys() == ()


@probe("no duplicate invocation under parallelism [v2 4.12]")
def _():
    calls, lock = [], threading.Lock()

    def track(i):
        with lock:
            calls.append(i.input_ids[0])
        return InvocationResult.empty()

    Orchestrator(invoker=track, max_workers=8).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(60))))
    assert len(calls) == len(set(calls)) == 60


print("== H. deadlock / starvation / hostile engines ==")


@probe("engine that blocks briefly does not deadlock the pool")
def _():
    ev = threading.Event()

    def waiter(i):
        ev.wait(timeout=0.05)
        return InvocationResult.empty()

    done = threading.Event()

    def run():
        Orchestrator(invoker=waiter, max_workers=2).run_cycle(
            WorkSet(items=tuple(wi(n) for n in range(4))))
        done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout=10)
    assert done.is_set(), "cycle did not terminate -- possible deadlock"


@probe("engine calling back into the orchestrator is refused, not deadlocked")
def _():
    o = Orchestrator(invoker=None, max_workers=2)

    def reentrant(i):
        try:
            o.run_cycle(WorkSet(items=(wi(99),)))
        except Exception:
            pass
        return InvocationResult.empty()

    o.invoker = reentrant
    done = threading.Event()

    def run():
        o.run_cycle(WorkSet(items=(wi(0), wi(1))))
        done.set()

    t = threading.Thread(target=run, daemon=True)
    t.start(); t.join(timeout=10)
    assert done.is_set(), "reentrant engine deadlocked the orchestrator"


@probe("no item starves: all attempted work completes")
def _():
    import random

    def jitter(i):
        time.sleep(random.uniform(0, 0.005))
        return InvocationResult.empty()

    r = Orchestrator(invoker=jitter, max_workers=4).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(40))))
    assert r.attempted_count == 40
    assert all(x.attempted for x in r.invocations)


@probe("hostile exception in a worker still surfaces")
def _():
    class Nasty(Exception):
        def __str__(self): raise RuntimeError("no str")

    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(Nasty()),
                     max_workers=4)
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(6))))
    assert r.failed_count == 6


@probe("cycle-level serialisation still refuses overlapping cycles")
def _():
    from oip.orchestration import CycleStateError
    o = Orchestrator(invoker=None, max_workers=4)
    errs = []

    def invoker(i):
        try:
            o.run_cycle(WorkSet(items=(wi(50),)))
            errs.append("second cycle admitted")
        except CycleStateError:
            pass
        return InvocationResult.empty()

    o.invoker = invoker
    o.run_cycle(WorkSet(items=(wi(0),)))
    assert not errs, errs


print("== I. validation and fail-closed ==")


@probe("bad max_workers refused")
def _():
    for bad in (0, -1, True, 1.5, "4", None):
        try:
            Orchestrator(invoker=empty, max_workers=bad).run_cycle(
                WorkSet(items=(wi(0),)))
            assert False, f"accepted {bad!r}"
        except ConcurrencyError:
            pass


@probe("unclassifiable item refused at plan time, cycle not silently skipped")
def _():
    o = Orchestrator(invoker=empty, max_workers=4)
    try:
        o.run_cycle(WorkSet(items=(wi(0, Engine.ORCHESTRATION),)))
        assert False, "ran an unclassifiable item"
    except ConcurrencyError:
        pass


@probe("boundary verifier refuses non-CycleRecord")
def _():
    for bad in ("x", None, 5):
        try:
            ConcurrencyBoundary(bad)
            assert False
        except ConcurrencyError:
            pass


@probe("verifier fails closed on a hand-built violation")
def _():
    from oip.orchestration import CycleRecord, InvocationRecord
    a = InvocationRecord(Engine.PROBLEM_INTELLIGENCE, ("a",), "c",
                         InvocationOutcome.EMPTY, (), "", T0,
                         T0 + timedelta(seconds=10))
    b = InvocationRecord(Engine.PROBLEM_INTELLIGENCE, ("b",), "c",
                         InvocationOutcome.EMPTY, (), "",
                         T0 + timedelta(seconds=1), T0 + timedelta(seconds=11))
    c = CycleRecord(1, CycleOutcome.COMPLETED, CycleBounds(), (a, b), (), 2,
                    T0, T0 + timedelta(seconds=11))
    bnd = ConcurrencyBoundary(c)
    assert not bnd.interpretation_serialised
    assert not bnd.branching_impossible
    assert not bnd.holds
    try:
        bnd.assert_holds(); assert False, "did not fail closed"
    except ConcurrencyViolation:
        pass


@probe("verifier is frozen and mutates nothing")
def _():
    r = Orchestrator(invoker=empty, max_workers=2).run_cycle(
        WorkSet(items=(wi(0), wi(1))))
    b = ConcurrencyBoundary(r)
    before = (r.attempted_count, r.outcome)
    b.holds; b.serialisation_violations(); b.barrier_violations()
    assert (r.attempted_count, r.outcome) == before
    try:
        b.cycle = None
        assert False, "mutable"
    except Exception:
        pass
    assert b.participates_in_lineage is False


print("== J. backward compatibility ==")


@probe("default orchestrator is sequential and unchanged")
def _():
    o = Orchestrator(invoker=empty)
    assert o.max_workers == 1
    r = o.run_cycle(WorkSet(items=(wi(0), wi(1))))
    assert r.attempted_count == 2 and r.outcome is CycleOutcome.COMPLETED


@probe("no CPU-derived default [M-56 open]")
def _():
    import inspect
    src = inspect.getsource(Orchestrator)
    for banned in ("cpu_count", "os.cpu", "multiprocessing"):
        assert banned not in src, banned


@probe("prior public API intact")
def _():
    import oip.orchestration as m
    for n in ("CycleBounds", "WorkItem", "WorkSet", "InvocationResult",
              "Orchestrator", "CycleRecord", "FailureSurface",
              "ProcessingStateStore", "ProcessingRecord", "CycleOutcome",
              "InvocationOutcome", "FailureMaskedError"):
        assert hasattr(m, n), n


print("== K. scale ==")


@probe("5000 concurrent items, exact and unmasked")
def _():
    ps = ProcessingStateStore()
    o = Orchestrator(invoker=empty, processing_store=ps, max_workers=8,
                     bounds=CycleBounds(max_work_items=5000,
                                        wall_clock_budget_seconds=9999))
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(5000))))
    assert r.attempted_count == 5000
    assert len(ps) == 5000
    assert ps.reprocessed_keys() == ()
    assert ConcurrencyBoundary(r).holds


@probe("interleaved mixed work set at volume keeps the barrier")
def _():
    items = []
    for n in range(300):
        items.append(wi(f"a{n}"))
        if n % 10 == 0:
            items.append(wi(f"p{n}", Engine.PROBLEM_INTELLIGENCE))
    t = Tracker(hold=0)
    o = Orchestrator(invoker=t, max_workers=8,
                     bounds=CycleBounds(max_work_items=10_000,
                                        wall_clock_budget_seconds=9999))
    r = o.run_cycle(WorkSet(items=tuple(items)))
    assert not t.overlap_acq_interp
    assert t.max_serialised <= 1
    assert ConcurrencyBoundary(r).holds


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all probes passed")
