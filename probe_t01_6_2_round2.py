"""Round 2: attack the seams round 1 did not reach."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.enums import Engine
from oip.orchestration import (
    CycleBounds, CycleOutcome, CycleRecord, InvocationOutcome, InvocationRecord,
    InvocationResult, Orchestrator, ProcessingRecord, ProcessingStateError,
    ProcessingStateStore, WorkItem, WorkSet, KnowledgeMutationError,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
NAIVE = datetime(2026, 3, 1)
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


print("== J. naive/aware datetime (the V8 defect family) ==")


@probe("naive started_at + aware ended_at does not crash the store")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.EMPTY, (), NAIVE, T0)
    except ProcessingStateError:
        return           # fail closed: acceptable
    except TypeError as e:
        assert False, f"uncaught TypeError comparing naive to aware: {e}"


@probe("aware started_at + naive ended_at does not crash")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.EMPTY, (), T0, NAIVE)
    except ProcessingStateError:
        return
    except TypeError as e:
        assert False, f"uncaught TypeError: {e}"


@probe("duration_seconds does not crash on mixed tz")
def _():
    try:
        r = ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                             InvocationOutcome.EMPTY, (), NAIVE, NAIVE)
    except ProcessingStateError:
        return
    r.duration_seconds


@probe("record() from an InvocationRecord with mixed tz does not crash")
def _():
    s = ProcessingStateStore()
    iv = InvocationRecord(Engine.RESEARCH, ("a",), "c",
                          InvocationOutcome.EMPTY, (), "", NAIVE, T0)
    try:
        s.record(1, iv)
    except ProcessingStateError:
        return
    except TypeError as e:
        assert False, f"uncaught TypeError: {e}"


@probe("non-datetime timestamps do not crash with a raw TypeError")
def _():
    for bad in ("2026-03-01", 0, None):
        try:
            ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                             InvocationOutcome.EMPTY, (), bad, bad)
        except ProcessingStateError:
            continue
        except TypeError as e:
            assert False, f"uncaught TypeError for {bad!r}: {e}"
        assert False, f"silently accepted {bad!r} as a timestamp"


print("== K. mutable sequences smuggled in as ids ==")


@probe("list input_ids coerced to tuple, so the frozen record stays immutable")
def _():
    r = ProcessingRecord(1, Engine.RESEARCH, ["a", "b"], "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
    assert isinstance(r.input_ids, tuple), type(r.input_ids)
    assert r.input_ids == ("a", "b")


@probe("list produced_ids coerced to tuple")
def _():
    r = ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.PRODUCED, ["x"], T0, T0)
    assert isinstance(r.produced_ids, tuple), type(r.produced_ids)


@probe("index cannot be desynchronised by mutating a recorded record")
def _():
    s = ProcessingStateStore()
    iv = InvocationRecord(Engine.RESEARCH, ["a"], "c",
                          InvocationOutcome.EMPTY, (), "", T0, T0)
    try:
        s.record(1, iv)
    except ProcessingStateError:
        return
    rec = s.all()[0]
    try:
        rec.input_ids.append("ghost")
    except AttributeError:
        return
    assert not s.has_processed(Engine.RESEARCH, "ghost"), \
        "mutating a stored record injected an unindexed key"


@probe("a str is not silently exploded into characters")
def _():
    try:
        r = ProcessingRecord(1, Engine.RESEARCH, "abc", "c",
                             InvocationOutcome.EMPTY, (), T0, T0)
    except ProcessingStateError:
        return
    assert tuple(r.input_ids) != ("a", "b", "c"), \
        "a bare string was treated as three ids"


@probe("generator input_ids cannot silently exhaust")
def _():
    gen = (x for x in ("a", "b"))
    try:
        r = ProcessingRecord(1, Engine.RESEARCH, gen, "c",
                             InvocationOutcome.EMPTY, (), T0, T0)
    except ProcessingStateError:
        return
    assert tuple(r.input_ids) == ("a", "b"), \
        f"generator consumed during validation: {tuple(r.input_ids)!r}"


print("== L. hashability / key integrity ==")


@probe("record is hashable (frozen dataclass contract)")
def _():
    r = ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
    hash(r)


@probe("Engine key does not collide with its str value")
def _():
    s = ProcessingStateStore()
    s.record(1, InvocationRecord(Engine.VALIDATION, ("a",), "c",
                                 InvocationOutcome.EMPTY, (), "", T0, T0))
    # Engine is a str-Enum: ("Validation", "a") must not alias the real key
    assert s.has_processed(Engine.VALIDATION, "a")
    assert (Engine.VALIDATION, "a") in dict(s._by_key)


print("== M. orchestrator commit ordering ==")


@probe("commit happens after the cycle is in history")
def _():
    seen = []

    class Watcher(ProcessingStateStore):
        def record_cycle(self, cycle):
            seen.append(o.cycle_count)
            return super().record_cycle(cycle)

    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     processing_store=Watcher())
    o.run_cycle(WorkSet(items=(WorkItem(Engine.RESEARCH, ("a",), "c"),)))
    assert seen == [1], f"cycle not yet in history at commit time: {seen}"


@probe("sequential cycles commit in cycle order")
def _():
    s = ProcessingStateStore()
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     processing_store=s)
    for n in range(5):
        o.run_cycle(WorkSet(items=(WorkItem(Engine.RESEARCH, (f"a{n}",), "c"),)))
    assert [r.cycle_id for r in s.all()] == [1, 2, 3, 4, 5]


@probe("store never sees an unattempted item even under a budget stop")
def _():
    s = ProcessingStateStore()
    clock = iter([T0 + timedelta(seconds=i * 100) for i in range(50)])
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     bounds=CycleBounds(wall_clock_budget_seconds=1.0),
                     processing_store=s, clock=lambda: next(clock))
    o.run_cycle(WorkSet(items=tuple(
        WorkItem(Engine.RESEARCH, (f"a{n}",), "c") for n in range(6))))
    assert all(r.outcome is not InvocationOutcome.NOT_ATTEMPTED for r in s.all())
    assert len(s) < 6, len(s)


print("== N. scale ==")


@probe("50k records: lookup stays exact")
def _():
    s = ProcessingStateStore()
    for i in range(50_000):
        s.record(1 + i % 7, InvocationRecord(
            Engine.RESEARCH, (f"s{i}",), "c",
            InvocationOutcome.EMPTY, (), "", T0, T0))
    assert len(s) == 50_000
    assert s.attempt_count(Engine.RESEARCH, "s49999") == 1
    assert s.reprocessed_keys() == ()
    assert len(s.cycles_recorded()) == 7


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-2 probes passed")
