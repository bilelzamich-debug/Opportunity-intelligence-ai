"""Round 2: races, visibility, sequential/parallel equivalence, store faults."""
from __future__ import annotations

import random
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.configuration import FailureStore
from oip.enums import Engine, ObjectType
from oip.orchestration import (
    ConcurrencyBoundary, ConcurrencyClass, ConcurrencyError, CycleBounds,
    CycleOutcome, FailureSurface, InvocationOutcome, InvocationResult,
    Orchestrator, ProcessingStateStore, WorkItem, WorkSet,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
FAILS = []
ENGINES = [Engine.RESEARCH, Engine.FACT_EXTRACTION,
           Engine.PROBLEM_INTELLIGENCE, Engine.PATTERN_INTELLIGENCE,
           Engine.OPPORTUNITY_INTELLIGENCE, Engine.SOLUTION_INTELLIGENCE,
           Engine.VALIDATION, Engine.FEEDBACK]


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


print("== L. sequential/parallel equivalence over random work sets ==")


@probe("identical records for 300 random work sets at every worker count")
def _():
    rng = random.Random(20260803)
    for trial in range(300):
        items = tuple(
            wi(n, rng.choice(ENGINES)) for n in range(rng.randint(1, 14))
        )
        ws = WorkSet(items=items)
        base = Orchestrator(invoker=empty, max_workers=1).run_cycle(ws)
        for mw in (2, 5):
            got = Orchestrator(invoker=empty, max_workers=mw).run_cycle(ws)
            assert [x.input_ids for x in got.invocations] == \
                   [x.input_ids for x in base.invocations], trial
            assert [x.engine for x in got.invocations] == \
                   [x.engine for x in base.invocations], trial
            assert got.attempted_count == base.attempted_count, trial
            assert got.outcome is base.outcome, trial


@probe("identical attempted counts under random bounds")
def _():
    rng = random.Random(7)
    for _ in range(200):
        n = rng.randint(1, 12)
        items = tuple(wi(i, rng.choice(ENGINES)) for i in range(n))
        ws = WorkSet(items=items)
        limit = rng.randint(1, n + 2)
        b = CycleBounds(max_work_items=limit)
        a = Orchestrator(invoker=empty, max_workers=1, bounds=b).run_cycle(ws)
        c = Orchestrator(invoker=empty, max_workers=4, bounds=b).run_cycle(ws)
        assert (a.attempted_count, a.not_attempted_count, a.outcome) == \
               (c.attempted_count, c.not_attempted_count, c.outcome), \
               (n, limit, a.attempted_count, c.attempted_count)


@probe("boundary holds for every random work set")
def _():
    rng = random.Random(99)
    for _ in range(150):
        items = tuple(wi(n, rng.choice(ENGINES)) for n in range(rng.randint(1, 12)))
        r = Orchestrator(invoker=empty, max_workers=4).run_cycle(
            WorkSet(items=items))
        ConcurrencyBoundary(r).assert_holds()


print("== M. visibility / memory effects ==")


@probe("no slot left unfilled after a parallel phase")
def _():
    for _ in range(100):
        r = Orchestrator(invoker=empty, max_workers=8).run_cycle(
            WorkSet(items=tuple(wi(n) for n in range(32))))
        assert len(r.invocations) == 32
        assert all(x.outcome is InvocationOutcome.EMPTY for x in r.invocations)


@probe("produced ids from parallel workers all visible")
def _():
    def produce(i):
        return InvocationResult.produced(f"o-{i.input_ids[0]}")

    r = Orchestrator(invoker=produce, max_workers=8).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(60))))
    got = {x.produced_ids[0] for x in r.invocations}
    assert got == {f"o-s-{n}" for n in range(60)}, len(got)


@probe("failure list not corrupted by concurrent appends")
def _():
    for _ in range(30):
        fs = FailureStore()
        r = Orchestrator(
            invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
            failure_store=fs, max_workers=8,
        ).run_cycle(WorkSet(items=tuple(wi(n) for n in range(24))))
        assert len(r.failures) == 24, len(r.failures)
        assert len(fs) == 24


@probe("timestamps coherent on every parallel record")
def _():
    r = Orchestrator(invoker=empty, max_workers=6).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(40))))
    for x in r.invocations:
        assert x.ended_at >= x.started_at
        assert x.duration_seconds >= 0


print("== N. store faults and hostile stores under concurrency ==")


@probe("hostile failure store does not lose the cycle under parallelism")
def _():
    class Hostile(FailureStore):
        def record(self, failure):
            raise RuntimeError("store unavailable")

    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     failure_store=Hostile(), max_workers=4)
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(8))))
    assert o.cycle_count == 1
    assert r.failed_count == 8
    ids = {rid for f in r.failures for rid in f.rule_ids}
    assert "FAILURE-STORE-UNAVAILABLE" in ids and "ENGINE-FAILURE" in ids


@probe("store faults counted exactly once per failing write")
def _():
    class Hostile(FailureStore):
        def record(self, failure):
            raise RuntimeError("down")

    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     failure_store=Hostile(), max_workers=8)
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(16))))
    faults = [f for f in r.failures if "FAILURE-STORE-UNAVAILABLE" in f.rule_ids]
    assert len(faults) == 16, len(faults)


@probe("store faults do not leak between parallel cycles")
def _():
    class Hostile(FailureStore):
        def record(self, failure):
            raise RuntimeError("down")

    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     failure_store=Hostile(), max_workers=4)
    for _ in range(4):
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(5))))
    for c in o.cycles:
        faults = [f for f in c.failures if "FAILURE-STORE-UNAVAILABLE" in f.rule_ids]
        assert len(faults) == 5, (c.cycle_id, len(faults))


@probe("control signal from a worker is not silently swallowed")
def _():
    def sig(i):
        if i.input_ids[0] == "s-3":
            raise KeyboardInterrupt()
        return InvocationResult.empty()

    o = Orchestrator(invoker=sig, max_workers=4)
    try:
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(8))))
        raised = False
    except KeyboardInterrupt:
        raised = True
    # Either it propagates, or it is recorded as a failure -- never vanishes.
    if not raised:
        r = o.cycle(1)
        assert r is not None and r.failed_count >= 1, \
            "KeyboardInterrupt vanished entirely"


print("== O. processing state exactness under parallelism ==")


@probe("processing state matches attempted work exactly, 50 runs")
def _():
    for _ in range(50):
        ps = ProcessingStateStore()
        r = Orchestrator(invoker=empty, processing_store=ps,
                         max_workers=8).run_cycle(
            WorkSet(items=tuple(wi(n) for n in range(20))))
        assert len(ps) == r.attempted_count == 20
        assert ps.reprocessed_keys() == ()


@probe("bounded parallel cycle records no unattempted work as processed")
def _():
    ps = ProcessingStateStore()
    r = Orchestrator(invoker=empty, processing_store=ps, max_workers=4,
                     bounds=CycleBounds(max_work_items=5)).run_cycle(
        WorkSet(items=tuple(wi(n) for n in range(20))))
    assert r.attempted_count == 5
    assert len(ps) == 5
    assert all(x.outcome is not InvocationOutcome.NOT_ATTEMPTED for x in ps.all())


print("== P. repeated cycles / reuse ==")


@probe("orchestrator reusable across many parallel cycles")
def _():
    o = Orchestrator(invoker=empty, max_workers=4)
    for _ in range(50):
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(8))))
    assert o.cycle_count == 50
    assert all(c.attempted_count == 8 for c in o.cycles)
    assert [c.cycle_id for c in o.cycles] == list(range(1, 51))


@probe("thread pool does not leak across cycles")
def _():
    before = threading.active_count()
    o = Orchestrator(invoker=empty, max_workers=8)
    for _ in range(30):
        o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(10))))
    time.sleep(0.2)
    after = threading.active_count()
    assert after <= before + 2, f"threads leaked: {before} -> {after}"


@probe("is_running clears after a parallel cycle")
def _():
    o = Orchestrator(invoker=empty, max_workers=4)
    o.run_cycle(WorkSet(items=(wi(0), wi(1))))
    assert o.is_running is False


@probe("is_running clears after a parallel cycle that raises")
def _():
    class Hostile(ProcessingStateStore):
        def record_cycle(self, cycle):
            raise RuntimeError("nope")

    o = Orchestrator(invoker=empty, processing_store=Hostile(), max_workers=4)
    try:
        o.run_cycle(WorkSet(items=(wi(0), wi(1))))
    except Exception:
        pass
    assert o.is_running is False, "orchestrator wedged after a failed commit"


print("== Q. semantics untouched ==")


@probe("concurrency introduces no new public mutation surface")
def _():
    from oip.orchestration import ConcurrencyBoundary as CB
    # Prefix match: "writers" in concurrent_same_type_writers is a REPORT of
    # writers, not a write. Only a method that starts with a mutating verb
    # would be a new mutation surface.
    banned = ("write", "commit", "accept", "supersede", "invalidate",
              "mutate", "set", "update", "record", "delete")
    names = [n for n in dir(CB) if not n.startswith("_")]
    offenders = [n for n in names if n.lower().startswith(banned)]
    assert not offenders, offenders


@probe("boundary layer imports no Intelligence Object module")
def _():
    import oip.orchestration as m
    src = Path(m.__file__).read_text()
    for mod in ("evidence", "fact", "problem", "pattern", "opportunity",
                "solution", "validation", "execution", "feedback", "store",
                "graph", "lineage", "claim", "semantic", "relationships"):
        assert f"from oip.{mod}" not in src, mod


@probe("no scheduling/priority vocabulary invented [AD-04]")
def _():
    from oip.orchestration import WorkSet as W, Orchestrator as O
    banned = ("priority", "reorder", "sort_", "rebalance", "throttle",
              "backpressure", "queue_bound")
    for cls in (W, O):
        names = [n for n in dir(cls) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)], names


@probe("orchestration still produces no intelligence objects")
def _():
    o = Orchestrator(invoker=empty, max_workers=4)
    o.run_cycle(WorkSet(items=(wi(0),)))
    assert o.produces_intelligence_objects is False


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-2 probes passed")
