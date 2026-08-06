"""Round 3: remaining seams -- reentrancy, aliasing, cross-store, exhaustion."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.configuration import FailureStore
from oip.enums import Engine
from oip.orchestration import (
    CycleBounds, CycleOutcome, CycleRecord, InvocationOutcome, InvocationRecord,
    InvocationResult, Orchestrator, ProcessingRecord, ProcessingStateError,
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


def iv(n=1, engine=Engine.RESEARCH, outcome=InvocationOutcome.EMPTY):
    return InvocationRecord(engine, (f"src-{n}",), "cfg-v1", outcome, (), "", T0, T0)


def wi(n=1, engine=Engine.RESEARCH):
    return WorkItem(engine, (f"src-{n}",), "cfg-v1")


print("== O. two orchestrators sharing one store ==")


@probe("colliding cycle ids across orchestrators are refused, not merged")
def _():
    s = ProcessingStateStore()
    a = Orchestrator(invoker=lambda i: InvocationResult.empty(), processing_store=s)
    b = Orchestrator(invoker=lambda i: InvocationResult.empty(), processing_store=s)
    a.run_cycle(WorkSet(items=(wi(1),)))
    try:
        b.run_cycle(WorkSet(items=(wi(2),)))
        assert False, "silently merged two different cycles under id 1"
    except ProcessingStateError:
        pass
    assert len(s) == 1


@probe("distinct engines on one store stay separable")
def _():
    s = ProcessingStateStore()
    s.record(1, iv(1, Engine.RESEARCH))
    s.record(2, iv(1, Engine.FACT_EXTRACTION))
    assert len(s.for_engine(Engine.RESEARCH)) == 1
    assert len(s.for_engine(Engine.FACT_EXTRACTION)) == 1
    assert s.reprocessed_keys() == ()


@probe("processing store and failure store remain separate surfaces [B-12]")
def _():
    ps, fs = ProcessingStateStore(), FailureStore()
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("boom")),
                     failure_store=fs, processing_store=ps)
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert len(fs) == 1, "failure not recorded"
    assert len(ps) == 1, "processing not recorded"
    assert ps.all()[0].failed, "failed attempt not marked failed"
    assert not any(isinstance(r, ProcessingRecord) for r in fs.all())


print("== P. reentrancy and locking ==")


@probe("a store method called from inside the invoker does not deadlock")
def _():
    s = ProcessingStateStore()
    seen = []

    def invoker(i):
        seen.append(s.would_reprocess(i))   # read under the orchestrator's flow
        return InvocationResult.empty()

    o = Orchestrator(invoker=invoker, processing_store=s)
    o.run_cycle(WorkSet(items=(wi(1),)))
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert seen == [False, True], seen


@probe("concurrent record_cycle on distinct ids does not deadlock or lose")
def _():
    s = ProcessingStateStore()
    errs = []

    def w(cid):
        try:
            s.record_cycle(CycleRecord(
                cycle_id=cid, outcome=CycleOutcome.COMPLETED, bounds=CycleBounds(),
                invocations=tuple(iv(f"{cid}-{k}") for k in range(20)),
                failures=(), planned_items=20, started_at=T0, ended_at=T0))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=w, args=(c,)) for c in range(1, 13)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert len(s) == 240, len(s)
    assert len(s.cycles_recorded()) == 12


@probe("concurrent record_cycle on the SAME id: exactly one wins")
def _():
    s = ProcessingStateStore()
    ok, rejected = [], []
    c = CycleRecord(cycle_id=1, outcome=CycleOutcome.COMPLETED, bounds=CycleBounds(),
                    invocations=(iv(1),), failures=(), planned_items=1,
                    started_at=T0, ended_at=T0)
    barrier = threading.Barrier(8)

    def w():
        barrier.wait()
        try:
            s.record_cycle(c); ok.append(1)
        except ProcessingStateError:
            rejected.append(1)

    ts = [threading.Thread(target=w) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(ok) == 1, f"{len(ok)} commits won the race"
    assert len(rejected) == 7
    assert len(s) == 1


print("== Q. aliasing ==")


@probe("mutating the caller's list after recording does not alter the record")
def _():
    s = ProcessingStateStore()
    ids = ["a", "b"]
    s.record(1, InvocationRecord(Engine.RESEARCH, ids, "c",
                                 InvocationOutcome.EMPTY, (), "", T0, T0))
    ids.append("ghost")
    assert s.all()[0].input_ids == ("a", "b")
    assert not s.has_processed(Engine.RESEARCH, "ghost")


@probe("internal index not reachable through public API")
def _():
    s = ProcessingStateStore()
    s.record(1, iv(1))
    got = s.all()
    assert isinstance(got, tuple)
    assert got is not s._records
    assert s.attempts(Engine.RESEARCH, "src-1") is not s._records


@probe("keys() reflects the coerced tuple")
def _():
    r = ProcessingRecord(1, Engine.RESEARCH, ["a", "b"], "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
    assert r.keys() == ((Engine.RESEARCH, "a"), (Engine.RESEARCH, "b"))


print("== R. failure masking ==")


@probe("a failing engine still produces processing state [N-10]")
def _():
    s = ProcessingStateStore()
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(ValueError("x")),
                     processing_store=s)
    r = o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    assert r.had_failure
    assert len(s) == 2, "failed attempts absent from processing state"
    assert all(p.failed for p in s.all())


@probe("mixed cycle: produced / empty / failed all recorded, all distinct")
def _():
    s = ProcessingStateStore()
    def invoker(i):
        n = i.input_ids[0]
        if n == "src-1":
            return InvocationResult.produced("o1")
        if n == "src-2":
            return InvocationResult.empty()
        raise RuntimeError("boom")
    o = Orchestrator(invoker=invoker, processing_store=s)
    o.run_cycle(WorkSet(items=(wi(1), wi(2), wi(3))))
    got = {p.input_ids[0]: p.outcome for p in s.all()}
    assert got == {"src-1": InvocationOutcome.PRODUCED,
                   "src-2": InvocationOutcome.EMPTY,
                   "src-3": InvocationOutcome.FAILED}, got


@probe("a rejected commit is loud, never swallowed")
def _():
    class Hostile(ProcessingStateStore):
        def record_cycle(self, cycle):
            raise ProcessingStateError("store unavailable")
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     processing_store=Hostile())
    try:
        o.run_cycle(WorkSet(items=(wi(1),)))
        assert False, "store failure silently swallowed"
    except ProcessingStateError:
        pass
    assert o.cycle_count == 1, "cycle that ran is missing from history"


print("== S. empty and boundary ==")


@probe("empty cycle registers no processing state")
def _():
    s = ProcessingStateStore()
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(), processing_store=s)
    o.run_cycle(WorkSet(items=()))
    assert len(s) == 0
    assert s.has_cycle(1)


@probe("empty store answers everything without raising")
def _():
    s = ProcessingStateStore()
    assert len(s) == 0 and s.all() == () and s.cycles_recorded() == ()
    assert list(s) == []
    assert not s.would_reprocess(wi(1))
    assert s.repeat_inputs(wi(1)) == ()


@probe("very many inputs on one item")
def _():
    s = ProcessingStateStore()
    ids = tuple(f"i{n}" for n in range(5000))
    s.record(1, InvocationRecord(Engine.RESEARCH, ids, "c",
                                 InvocationOutcome.EMPTY, (), "", T0, T0))
    assert len(s) == 1
    assert all(s.has_processed(Engine.RESEARCH, i) for i in ids)
    assert len(s.repeat_inputs(WorkItem(Engine.RESEARCH, ids, "c"))) == 5000


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-3 probes passed")
