"""Round 3: attack the store-fault path added in round 2, plus leak checks."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.acceptance import FailureRecord
from oip.configuration import FailureStore
from oip.enums import Engine
from oip.orchestration import (
    CycleBounds, CycleOutcome, FailureSurface, InvocationResult, Orchestrator,
    ProcessingStateStore, WorkItem, WorkSet,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
FAILS = []


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


def wi(n=1, engine=Engine.RESEARCH):
    return WorkItem(engine, (f"src-{n}",), "cfg")


def boom(_i):
    raise RuntimeError("engine down")


class Hostile(FailureStore):
    def record(self, failure):
        raise RuntimeError("store unavailable")


print("== Q. store-fault path ==")


@probe("store faults do not leak between cycles")
def _():
    o = Orchestrator(invoker=boom, failure_store=Hostile())
    o.run_cycle(WorkSet(items=(wi(1),)))
    o.run_cycle(WorkSet(items=(wi(2),)))
    c1, c2 = o.cycle(1), o.cycle(2)
    assert len(c1.failures) == 2, len(c1.failures)
    assert len(c2.failures) == 2, f"faults accumulated across cycles: {len(c2.failures)}"


@probe("a healthy store leaves no store-fault records")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    ids = {rid for f in r.failures for rid in f.rule_ids}
    assert ids == {"ENGINE-FAILURE"}, ids


@probe("store fault on a SUCCESSFUL cycle cannot occur (nothing to record)")
def _():
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     failure_store=Hostile())
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failures == ()
    assert FailureSurface.over(o).failure_free()


@probe("intermittent store fault: only failing writes produce fault records")
def _():
    class Flaky(FailureStore):
        def __init__(self):
            super().__init__()
            self.n = 0

        def record(self, failure):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("transient")
            return super().record(failure)

    fs = Flaky()
    o = Orchestrator(invoker=boom, failure_store=fs)
    r = o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    ids = [rid for f in r.failures for rid in f.rule_ids]
    assert ids.count("FAILURE-STORE-UNAVAILABLE") == 1, ids
    assert ids.count("ENGINE-FAILURE") == 2, ids
    assert len(fs) == 1, "second write did not land"


@probe("store fault records carry full N-10 attribution")
def _():
    o = Orchestrator(invoker=boom, failure_store=Hostile())
    r = o.run_cycle(WorkSet(items=(WorkItem(Engine.VALIDATION, ("x",), "cfg-2"),)))
    fault = [f for f in r.failures if "FAILURE-STORE-UNAVAILABLE" in f.rule_ids][0]
    assert fault.engine is Engine.VALIDATION
    assert fault.cycle_id == 1 and fault.invocation_index == 0
    assert fault.input_ids == ("x",)
    assert fault.satisfies_n10_attribution is True


@probe("store fault never converts a failure into a success")
def _():
    o = Orchestrator(invoker=boom, failure_store=Hostile())
    o.run_cycle(WorkSet(items=(wi(1),)))
    s = FailureSurface.over(o)
    assert o.cycle(1).outcome is CycleOutcome.FAILED
    assert s.failed_count == 1
    assert s.masked_cycles() == ()
    s.assert_not_masked()


@probe("store fault does not stop the cycle continuing")
def _():
    seen = []

    def track(i):
        seen.append(i.input_ids[0])
        raise RuntimeError("x")

    o = Orchestrator(invoker=track, failure_store=Hostile())
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(5))))
    assert seen == [f"src-{n}" for n in range(5)], seen
    assert r.attempted_count == 5


@probe("store fault with a hostile exception message still recorded")
def _():
    class Vile(FailureStore):
        def record(self, failure):
            class E(Exception):
                def __str__(self): raise ValueError("no")
            raise E()

    o = Orchestrator(invoker=boom, failure_store=Vile())
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert any("FAILURE-STORE-UNAVAILABLE" in f.rule_ids for f in r.failures)


@probe("control signals from the STORE still propagate")
def _():
    for sig in (KeyboardInterrupt, SystemExit):
        class Sig(FailureStore):
            def record(self, failure):
                raise sig()
        o = Orchestrator(invoker=boom, failure_store=Sig())
        try:
            o.run_cycle(WorkSet(items=(wi(1),)))
            raise AssertionError(f"{sig.__name__} swallowed by the store path")
        except sig:
            pass


@probe("concurrent orchestrators with a hostile store do not cross-contaminate")
def _():
    errs, counts = [], []

    def run(k):
        try:
            o = Orchestrator(invoker=boom, failure_store=Hostile())
            o.run_cycle(WorkSet(items=(wi(k),)))
            counts.append(len(o.cycle(1).failures))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=run, args=(k,)) for k in range(12)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert set(counts) == {2}, set(counts)


print("== R. no behavioural regression in the clean path ==")


@probe("clean cycles behave exactly as before")
def _():
    o = Orchestrator(invoker=lambda i: InvocationResult.produced("o1"))
    r = o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    assert r.outcome is CycleOutcome.COMPLETED
    assert r.produced_count == 2 and r.failed_count == 0
    assert r.failures == ()


@probe("orchestrator without any store still surfaces failures")
def _():
    o = Orchestrator(invoker=boom)
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failed_count == 1
    assert len(r.failures) == 1
    assert FailureSurface.over(o).failed_count == 1


@probe("processing state unaffected by a hostile failure store")
def _():
    ps = ProcessingStateStore()
    o = Orchestrator(invoker=boom, failure_store=Hostile(), processing_store=ps)
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert len(ps) == 1 and ps.all()[0].failed


@probe("bounded stop still records unattempted work")
def _():
    o = Orchestrator(invoker=boom, bounds=CycleBounds(max_work_items=2))
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(6))))
    assert r.attempted_count == 2 and r.not_attempted_count == 4


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-3 probes passed")
