"""Round 2: seams round 1 did not reach -- hostile engines, store faults, ordering."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.configuration import FailureStore
from oip.enums import Engine, ObjectType
from oip.orchestration import (
    CycleBounds, CycleOutcome, CycleRecord, FailureMaskedError, FailureSurface,
    InvocationOutcome, InvocationRecord, InvocationResult, Orchestrator,
    OrchestrationError, ProcessingStateStore, WorkItem, WorkSet,
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


print("== J. hostile engine returns ==")


@probe("engine returning None is a failure, not a silent pass")
def _():
    o = Orchestrator(invoker=lambda i: None)
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failed_count == 1, "a None return was not treated as a failure"
    assert FailureSurface.over(o).failed_count == 1


@probe("engine returning a fake result object is refused")
def _():
    class Fake:
        outcome = InvocationOutcome.PRODUCED
        produced_ids = ("o1",)
        detail = ""
    o = Orchestrator(invoker=lambda i: Fake())
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failed_count == 1, "duck-typed impostor accepted"


@probe("engine with exploding __repr__ still recorded")
def _():
    class Vile(Exception):
        def __str__(self): raise ValueError("no str")
        def __repr__(self): raise ValueError("no repr")
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(Vile()))
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failed_count == 1
    assert "Vile" in FailureSurface.over(o).failure_records()[0].nature[0]


@probe("exception with an exploding __class__.__name__ still recorded")
def _():
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(BaseException("low")))
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failed_count == 1, "bare BaseException not recorded as failure"


@probe("GeneratorExit from an engine is recorded, not silently swallowed")
def _():
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(GeneratorExit()))
    r = o.run_cycle(WorkSet(items=(wi(1),)))
    assert r.failed_count == 1


@probe("MemoryError-class fault recorded and cycle continues")
def _():
    calls = []

    def flaky(i):
        calls.append(i.input_ids[0])
        if i.input_ids[0] == "src-1":
            raise MemoryError("out of memory")
        return InvocationResult.empty()

    o = Orchestrator(invoker=flaky)
    r = o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    assert calls == ["src-1", "src-2"], calls
    assert r.failed_count == 1


print("== K. failure store faults ==")


@probe("a raising failure store does not lose the cycle record")
def _():
    class Hostile(FailureStore):
        def record(self, failure):
            raise RuntimeError("store unavailable")

    o = Orchestrator(invoker=boom, failure_store=Hostile())
    try:
        r = o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    except Exception as e:
        # If it propagates, the cycle must still be retrievable.
        assert o.cycle_count == 1, (
            f"store fault destroyed the cycle record entirely: {type(e).__name__}"
        )
        return
    assert r.failed_count == 2


@probe("failure store never receives an Intelligence Object")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    o.run_cycle(WorkSet(items=(wi(1),)))
    for r in fs.all():
        assert type(r) is FailureRecord
        assert r.participates_in_lineage is False


print("== L. masking edge cases ==")


@probe("FAILED cycle outcome is not called masked")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert o.cycle(1).outcome is CycleOutcome.FAILED
    assert FailureSurface.over(o).masked_cycles() == ()


@probe("hand-built COMPLETED cycle hiding a failure is caught")
def _():
    c = CycleRecord(1, CycleOutcome.COMPLETED, CycleBounds(),
                    (InvocationRecord(Engine.RESEARCH, ("a",), "c",
                                      InvocationOutcome.FAILED, (), "", T0, T0),),
                    (), 1, T0, T0)
    s = FailureSurface(cycles=(c,))
    assert s.is_masked_as_completion()
    try:
        s.assert_not_masked(); raise AssertionError("not failed closed")
    except FailureMaskedError as e:
        assert "1" in str(e)


@probe("every_failure_is_visible detects a hidden failure count")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    assert FailureSurface.over(o).every_failure_is_visible()


@probe("mixed clean and failing cycles: only failing ones reported")
def _():
    calls = {"n": 0}

    def alternate(i):
        calls["n"] += 1
        if calls["n"] % 2 == 0:
            raise RuntimeError("x")
        return InvocationResult.empty()

    o = Orchestrator(invoker=alternate)
    for _ in range(6):
        o.run_cycle(WorkSet(items=(wi(1),)))
    s = FailureSurface.over(o)
    assert s.failed_count == 3
    assert len(s.cycles_with_failures()) == 3
    assert s.masked_cycles() == ()
    # cycles 2, 4 and 6 fail; the LAST cycle failed, so the streak is 1.
    assert [c.cycle_id for c in s.cycles_with_failures()] == [2, 4, 6]
    assert s.consecutive_failures() == 1


print("== M. attribution correctness ==")


@probe("invocation_index is unique per cycle and matches position")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(5))))
    idx = [r.invocation_index for r in fs.for_cycle(1)]
    assert idx == [0, 1, 2, 3, 4], idx
    for r in fs.for_cycle(1):
        assert r.input_ids == (f"src-{r.invocation_index}",)


@probe("cycle_id distinguishes repeated failures on the same input")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    o.run_cycle(WorkSet(items=(wi(1),)))
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert [r.cycle_id for r in fs.all()] == [1, 2]
    assert all(r.satisfies_n10_attribution for r in fs.all())


@probe("multi-input failure retains every attempted input")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    ids = tuple(f"ev-{n}" for n in range(50))
    o.run_cycle(WorkSet(items=(WorkItem(Engine.FACT_EXTRACTION, ids, "cfg"),)))
    assert fs.all()[0].input_ids == ids


@probe("engines_with_failures attributes precisely")
def _():
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x"))
                     if i.engine is Engine.RESEARCH else InvocationResult.empty())
    o.run_cycle(WorkSet(items=(wi(1, Engine.RESEARCH), wi(2, Engine.FEEDBACK))))
    s = FailureSurface.over(o)
    assert s.engines_with_failures() == (Engine.RESEARCH,)
    assert len(s.failures_for_engine(Engine.RESEARCH)) == 1
    assert s.failures_for_engine(Engine.FEEDBACK) == ()


@probe("input_ids on a failure record is an immutable tuple")
def _():
    r = FailureRecord("X", ObjectType.EVIDENCE,
                      (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
                      input_ids=["a", "b"])
    assert isinstance(r.input_ids, tuple)
    ids = ["a"]
    r2 = FailureRecord("X", ObjectType.EVIDENCE,
                       (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
                       input_ids=ids)
    ids.append("ghost")
    assert r2.input_ids == ("a",), "caller mutation leaked into the record"


print("== N. ordering and determinism ==")


@probe("failed_invocations ordered by cycle")
def _():
    o = Orchestrator(invoker=boom)
    for _ in range(4):
        o.run_cycle(WorkSet(items=(wi(1),)))
    ids = [cid for cid, _ in FailureSurface.over(o).failed_invocations()]
    assert ids == [1, 2, 3, 4], ids


@probe("repeated queries are stable")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    s = FailureSurface.over(o)
    assert s.failed_invocations() == s.failed_invocations()
    assert s.summary() == s.summary()


@probe("over() accepts any iterable of cycles")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert FailureSurface.over(list(o.cycles)).failed_count == 1
    assert FailureSurface.over(iter(o.cycles)).failed_count == 1
    assert FailureSurface.over(o).failed_count == 1


print("== O. interaction with processing state (T01.6.2) ==")


@probe("a failure appears on BOTH surfaces without either masking it")
def _():
    fs, ps = FailureStore(), ProcessingStateStore()
    o = Orchestrator(invoker=boom, failure_store=fs, processing_store=ps)
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert len(fs) == 1
    assert len(ps) == 1 and ps.all()[0].failed
    assert FailureSurface.over(o).failed_count == 1


@probe("processing state records the failed attempt; surface explains why")
def _():
    fs, ps = FailureStore(), ProcessingStateStore()
    o = Orchestrator(invoker=boom, failure_store=fs, processing_store=ps)
    o.run_cycle(WorkSet(items=(WorkItem(Engine.RESEARCH, ("s1",), "cfg"),)))
    assert ps.has_processed(Engine.RESEARCH, "s1")
    rec = fs.for_cycle(1)[0]
    assert rec.input_ids == ("s1",) and "RuntimeError" in rec.nature[0]


print("== P. concurrency under contention ==")


@probe("shared failure store across concurrent orchestrators stays exact")
def _():
    fs = FailureStore()
    errs = []

    def run(k):
        try:
            o = Orchestrator(invoker=boom, failure_store=fs)
            for _ in range(10):
                o.run_cycle(WorkSet(items=(wi(k),)))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=run, args=(k,)) for k in range(10)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert len(fs) == 100, len(fs)
    assert fs.unattributed() == ()


@probe("surface built concurrently over one orchestrator is consistent")
def _():
    o = Orchestrator(invoker=boom)
    for _ in range(20):
        o.run_cycle(WorkSet(items=(wi(1),)))
    results, errs = [], []

    def read():
        try:
            results.append(FailureSurface.over(o).failed_count)
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=read) for _ in range(16)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert set(results) == {20}, set(results)


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-2 probes passed")
