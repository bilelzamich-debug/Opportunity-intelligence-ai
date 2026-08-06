"""Round 3: sustained thread pressure, GIL-release, barrier stress."""
from __future__ import annotations

import random
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.enums import Engine, ObjectType
from oip.orchestration import (
    ConcurrencyBoundary, ConcurrencyError, CycleBounds, CycleOutcome,
    InvocationOutcome, InvocationResult, Orchestrator, ProcessingStateStore,
    WorkItem, WorkSet,
)

FAILS = []
INTERP = (Engine.PROBLEM_INTELLIGENCE, Engine.PATTERN_INTELLIGENCE,
          Engine.OPPORTUNITY_INTELLIGENCE, Engine.SOLUTION_INTELLIGENCE,
          Engine.VALIDATION, Engine.FEEDBACK)
ACQ = (Engine.RESEARCH, Engine.FACT_EXTRACTION)


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


print("== R. barrier under sustained pressure ==")


@probe("1000 mixed cycles: barrier never breached")
def _():
    rng = random.Random(4242)
    engines = list(ACQ) + list(INTERP)
    breaches = 0
    for _ in range(1000):
        items = tuple(wi(n, rng.choice(engines)) for n in range(rng.randint(2, 8)))
        r = Orchestrator(invoker=empty, max_workers=4).run_cycle(
            WorkSet(items=items))
        if not ConcurrencyBoundary(r).holds:
            breaches += 1
    assert breaches == 0, breaches


@probe("live overlap detector across 200 aggressive cycles")
def _():
    state = {"acq": 0, "ser": 0, "bad": 0, "maxser": 0}
    lock = threading.Lock()

    def invoker(item):
        with lock:
            if item.engine in ACQ:
                state["acq"] += 1
            else:
                state["ser"] += 1
                state["maxser"] = max(state["maxser"], state["ser"])
            if state["ser"] and state["acq"]:
                state["bad"] += 1
        time.sleep(0.0002)
        with lock:
            if item.engine in ACQ:
                state["acq"] -= 1
            else:
                state["ser"] -= 1
        return InvocationResult.empty()

    rng = random.Random(11)
    for _ in range(200):
        items = []
        for n in range(rng.randint(4, 10)):
            eng = rng.choice(list(ACQ)) if rng.random() < 0.6 else rng.choice(INTERP)
            items.append(wi(n, eng))
        Orchestrator(invoker=invoker, max_workers=6).run_cycle(
            WorkSet(items=tuple(items)))
    assert state["bad"] == 0, f"{state['bad']} acquisition/interpretation overlaps"
    assert state["maxser"] <= 1, state["maxser"]


@probe("GIL-releasing engines still respect the barrier")
def _():
    seen_parallel = {"acq": False}
    active = {"acq": 0, "ser": 0}
    bad = []
    lock = threading.Lock()

    def io_bound(item):
        with lock:
            key = "acq" if item.engine in ACQ else "ser"
            active[key] += 1
            if key == "acq" and active["acq"] > 1:
                seen_parallel["acq"] = True
            if active["ser"] and active["acq"]:
                bad.append(1)
        time.sleep(0.01)          # releases the GIL
        with lock:
            active["acq" if item.engine in ACQ else "ser"] -= 1
        return InvocationResult.empty()

    ws = WorkSet(items=(
        wi(0), wi(1), wi(2), wi(3),
        wi(4, Engine.PATTERN_INTELLIGENCE),
        wi(5), wi(6), wi(7),
        wi(8, Engine.PROBLEM_INTELLIGENCE),
    ))
    Orchestrator(invoker=io_bound, max_workers=4).run_cycle(ws)
    assert not bad, f"{len(bad)} overlaps under real IO waits"
    assert seen_parallel["acq"], "acquisition never actually parallelised"


@probe("high worker count over small phases is safe")
def _():
    for mw in (2, 8, 32, 64):
        r = Orchestrator(invoker=empty, max_workers=mw).run_cycle(
            WorkSet(items=(wi(0), wi(1, Engine.PROBLEM_INTELLIGENCE), wi(2))))
        assert r.attempted_count == 3
        ConcurrencyBoundary(r).assert_holds()


@probe("single-item concurrent phase takes the sequential path")
def _():
    r = Orchestrator(invoker=empty, max_workers=8).run_cycle(
        WorkSet(items=(wi(0),)))
    assert r.attempted_count == 1
    assert ConcurrencyBoundary(r).holds


print("== S. adversarial engines inside a parallel phase ==")


@probe("engine sleeping past the budget does not corrupt the record")
def _():
    def slow(i):
        time.sleep(0.05)
        return InvocationResult.empty()

    r = Orchestrator(invoker=slow, max_workers=4,
                     bounds=CycleBounds(wall_clock_budget_seconds=0.01)
                     ).run_cycle(WorkSet(items=tuple(wi(n) for n in range(8))))
    assert len(r.invocations) == 8
    assert r.attempted_count + r.not_attempted_count == 8


@probe("engine mutating its own WorkItem cannot corrupt the plan")
def _():
    def meddler(i):
        try:
            object.__setattr__(i, "engine", Engine.PROBLEM_INTELLIGENCE)
        except Exception:
            pass
        return InvocationResult.empty()

    ws = WorkSet(items=tuple(wi(n) for n in range(6)))
    r = Orchestrator(invoker=meddler, max_workers=4).run_cycle(ws)
    assert r.attempted_count == 6


@probe("engine spawning threads does not break accounting")
def _():
    def spawner(i):
        t = threading.Thread(target=lambda: time.sleep(0.001))
        t.start(); t.join()
        return InvocationResult.empty()

    ps = ProcessingStateStore()
    r = Orchestrator(invoker=spawner, processing_store=ps,
                     max_workers=4).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(16))))
    assert r.attempted_count == 16 and len(ps) == 16


@probe("engine returning a bad result in parallel is a failure, not a crash")
def _():
    r = Orchestrator(invoker=lambda i: None, max_workers=4).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(8))))
    assert r.failed_count == 8


@probe("mixed fast/slow items all recorded in caller order")
def _():
    def uneven(i):
        n = int(i.input_ids[0].split("-")[1])
        time.sleep(0.02 if n % 2 == 0 else 0.001)
        return InvocationResult.empty()

    r = Orchestrator(invoker=uneven, max_workers=4).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(12))))
    assert [x.input_ids[0] for x in r.invocations] == [f"s-{n}" for n in range(12)]


print("== T. stage-8 and exotic classification ==")


@probe("stage-8 items serialise against each other")
def _():
    active = {"n": 0}
    bad = []
    lock = threading.Lock()

    def track(i):
        with lock:
            active["n"] += 1
            if active["n"] > 1:
                bad.append(1)
        time.sleep(0.002)
        with lock:
            active["n"] -= 1
        return InvocationResult.empty()

    items = tuple(
        WorkItem(Engine.FEEDBACK, (f"x-{n}",), "cfg",
                 produces=ObjectType.EXECUTION_RECORD)
        for n in range(6)
    )
    Orchestrator(invoker=track, max_workers=8).run_cycle(WorkSet(items=items))
    assert not bad, "stage-8 items ran concurrently"


@probe("a Research item producing a Problem is serialised by type")
def _():
    active = {"n": 0}
    bad = []
    lock = threading.Lock()

    def track(i):
        with lock:
            active["n"] += 1
            if active["n"] > 1:
                bad.append(1)
        time.sleep(0.002)
        with lock:
            active["n"] -= 1
        return InvocationResult.empty()

    items = tuple(
        WorkItem(Engine.RESEARCH, (f"x-{n}",), "cfg", produces=ObjectType.PROBLEM)
        for n in range(5)
    )
    Orchestrator(invoker=track, max_workers=8).run_cycle(WorkSet(items=items))
    assert not bad, "object type did not govern the boundary"


@probe("unclassifiable item aborts before any work runs")
def _():
    calls = []
    o = Orchestrator(invoker=lambda i: (calls.append(1),
                                        InvocationResult.empty())[1],
                     max_workers=4)
    try:
        o.run_cycle(WorkSet(items=(wi(0), wi(1, Engine.ORCHESTRATION))))
        assert False, "ran an unclassifiable work set"
    except ConcurrencyError:
        pass
    assert o.is_running is False


print("== U. no regression in prior task behaviour ==")


@probe("T01.6.3 failure surfacing intact under concurrency")
def _():
    from oip.orchestration import FailureSurface
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     max_workers=4)
    for _ in range(5):
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(6))))
    s = FailureSurface.over(o)
    assert s.failed_count == 30
    assert s.masked_cycles() == ()
    s.assert_not_masked()
    assert s.consecutive_failures() == 5


@probe("T01.6.2 idempotence detection intact under concurrency")
def _():
    ps = ProcessingStateStore()
    o = Orchestrator(invoker=empty, processing_store=ps, max_workers=4)
    ws = WorkSet(items=tuple(wi(n) for n in range(10)))
    o.run_cycle(ws)
    o.run_cycle(ws)
    assert len(ps.reprocessed_keys()) == 10
    assert all(ps.attempt_count(Engine.RESEARCH, f"s-{n}") == 2 for n in range(10))


@probe("T01.6.1 bounds and monotonic cycle ids intact")
def _():
    o = Orchestrator(invoker=empty, max_workers=4,
                     bounds=CycleBounds(max_work_items=3))
    for _ in range(6):
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(10))))
    assert [c.cycle_id for c in o.cycles] == list(range(1, 7))
    assert all(c.attempted_count == 3 for c in o.cycles)
    assert all(c.outcome is CycleOutcome.WORK_LIMIT_REACHED for c in o.cycles)


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-3 probes passed")
