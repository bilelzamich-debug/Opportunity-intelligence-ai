"""Adversarial probe for T01.6.2. Attack the implementation before testing it."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.enums import Engine, ObjectType
from oip.orchestration import (
    CycleBounds, CycleRecord, InvocationOutcome, InvocationRecord,
    InvocationResult, Orchestrator, ProcessingIsolationError,
    ProcessingRecord, ProcessingStateError, ProcessingStateStore,
    WorkItem, WorkSet, KnowledgeMutationError,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
FAILS: list[str] = []


def probe(name):
    def deco(fn):
        try:
            fn()
            print(f"  ok   {name}")
        except AssertionError as e:
            FAILS.append(f"{name}: {e}")
            print(f"  FAIL {name}: {e}")
        except Exception as e:
            FAILS.append(f"{name}: {type(e).__name__}: {e}")
            print(f"  ERR  {name}: {type(e).__name__}: {e}")
        return fn
    return deco


def inv(n=1, engine=Engine.RESEARCH, outcome=InvocationOutcome.EMPTY,
        produced=(), inputs=None, cfg="cfg-v1", t=T0):
    return InvocationRecord(
        engine=engine,
        input_ids=inputs if inputs is not None else (f"src-{n}",),
        engine_configuration_ref=cfg,
        outcome=outcome,
        produced_ids=produced,
        detail="",
        started_at=t,
        ended_at=t,
    )


def item(n=1, engine=Engine.RESEARCH, inputs=None):
    return WorkItem(engine=engine,
                    input_ids=inputs if inputs is not None else (f"src-{n}",),
                    engine_configuration_ref="cfg-v1")


def cycle(cid, invocations):
    return CycleRecord(
        cycle_id=cid, outcome=__import__("oip.orchestration", fromlist=["x"]).CycleOutcome.COMPLETED,
        bounds=CycleBounds(), invocations=tuple(invocations), failures=(),
        planned_items=len(invocations), started_at=T0, ended_at=T0,
    )


print("== A. NOT_ATTEMPTED must never count as processed ==")


@probe("direct construction refuses NOT_ATTEMPTED")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.NOT_ATTEMPTED, (), T0, T0)
        assert False, "accepted NOT_ATTEMPTED"
    except ProcessingStateError:
        pass


@probe("record() refuses NOT_ATTEMPTED")
def _():
    s = ProcessingStateStore()
    try:
        s.record(1, inv(outcome=InvocationOutcome.NOT_ATTEMPTED))
        assert False, "accepted"
    except ProcessingStateError:
        pass


@probe("record_cycle excludes NOT_ATTEMPTED; bounded stop leaves store clean")
def _():
    s = ProcessingStateStore()
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     bounds=CycleBounds(max_work_items=1),
                     processing_store=s)
    o.run_cycle(WorkSet(items=(item(1), item(2), item(3))))
    assert len(s) == 1, len(s)
    assert not s.has_processed(Engine.RESEARCH, "src-2"), "unattempted marked processed"
    assert not s.has_processed(Engine.RESEARCH, "src-3")


print("== B. idempotence detection ==")


@probe("repeat appends, never overwrites")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1))
    s.record(2, inv(1))
    assert s.attempt_count(Engine.RESEARCH, "src-1") == 2
    assert len(s.attempts(Engine.RESEARCH, "src-1")) == 2
    assert len(s) == 2


@probe("different engine on same input is NOT a repeat")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1, engine=Engine.RESEARCH))
    assert not s.has_processed(Engine.FACT_EXTRACTION, "src-1")
    assert s.would_reprocess(item(1, engine=Engine.RESEARCH))
    assert not s.would_reprocess(item(1, engine=Engine.FACT_EXTRACTION))


@probe("partial overlap detected precisely")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(inputs=("a", "b")))
    assert s.repeat_inputs(item(inputs=("b", "c"))) == ("b",)


@probe("FAILED attempt is recorded as an attempt, outcome preserved")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(outcome=InvocationOutcome.FAILED))
    assert s.has_processed(Engine.RESEARCH, "src-1")
    a = s.attempts(Engine.RESEARCH, "src-1")[0]
    assert a.failed and not a.produced_nothing


@probe("EMPTY distinguishable from FAILED [N-10]")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1, outcome=InvocationOutcome.EMPTY))
    s.record(1, inv(2, outcome=InvocationOutcome.FAILED))
    e = s.attempts(Engine.RESEARCH, "src-1")[0]
    f = s.attempts(Engine.RESEARCH, "src-2")[0]
    assert e.produced_nothing and not e.failed
    assert f.failed and not f.produced_nothing


@probe("reprocessed_keys surfaces duplicate invocation")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1)); s.record(2, inv(1)); s.record(1, inv(2))
    assert s.reprocessed_keys() == ((Engine.RESEARCH, "src-1"),)


print("== C. no action taken on detection (AD-04, M-36 open) ==")


@probe("orchestrator does NOT skip a detected repeat")
def _():
    s = ProcessingStateStore()
    seen = []
    o = Orchestrator(invoker=lambda i: (seen.append(i.input_ids[0]),
                                        InvocationResult.empty())[1],
                     processing_store=s)
    o.run_cycle(WorkSet(items=(item(1),)))
    o.run_cycle(WorkSet(items=(item(1),)))
    assert seen == ["src-1", "src-1"], seen
    assert s.attempt_count(Engine.RESEARCH, "src-1") == 2


@probe("store exposes no retry/skip/suppress vocabulary")
def _():
    banned = {"retry", "skip", "halt", "compensate", "suppress", "defer",
              "schedule", "next_work", "should_run"}
    names = {n.lower() for n in dir(ProcessingStateStore) if not n.startswith("_")}
    hits = {n for n in names if any(b in n for b in banned)}
    assert not hits, hits


print("== D. isolation: outside object model, metadata only ==")


@probe("module imports no Intelligence Object type")
def _():
    import oip.orchestration as m
    src = Path(m.__file__).read_text()
    for mod in ("evidence", "fact", "problem", "pattern", "opportunity",
                "solution", "validation", "execution", "feedback", "store",
                "graph", "lineage", "claim", "semantic", "relationships"):
        assert f"from oip.{mod}" not in src, mod


@probe("no field can carry an object")
def _():
    import dataclasses
    types = {f.type for f in dataclasses.fields(ProcessingRecord)}
    assert types == {"int", "Engine", "tuple[str, ...]", "str",
                     "InvocationOutcome", "datetime"}, types


@probe("non-string input id refused as knowledge mutation")
def _():
    for bad in [object(), 42, None]:
        try:
            ProcessingRecord(1, Engine.RESEARCH, (bad,), "c",
                             InvocationOutcome.EMPTY, (), T0, T0)
            assert False, f"accepted {bad!r}"
        except KnowledgeMutationError:
            pass


@probe("non-string produced id refused")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.PRODUCED, (object(),), T0, T0)
        assert False
    except KnowledgeMutationError:
        pass


@probe("lookup with non-string input id refused")
def _():
    s = ProcessingStateStore()
    try:
        s.has_processed(Engine.RESEARCH, object())
        assert False
    except KnowledgeMutationError:
        pass


@probe("isolation refusals")
def _():
    r = ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
    assert r.is_intelligence is False
    assert r.participates_in_lineage is False
    for fn in (r.as_lineage_reference, r.as_evidence, r.confidence_contribution):
        try:
            fn(); assert False, fn.__name__
        except ProcessingIsolationError:
            pass
    s = ProcessingStateStore()
    assert s.is_intelligence is False and s.participates_in_lineage is False


@probe("append-only: delete and update refused")
def _():
    s = ProcessingStateStore()
    s.record(1, inv())
    for fn in (s.delete, s.update):
        try:
            fn("x"); assert False
        except ProcessingStateError:
            pass
    assert len(s) == 1


@probe("record frozen")
def _():
    r = ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
    try:
        r.cycle_id = 9; assert False
    except Exception:
        pass


print("== E. malformed input, fail closed ==")


@probe("empty input_ids refused")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, (), "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
        assert False
    except ProcessingStateError:
        pass


@probe("blank config ref refused [N-4]")
def _():
    for bad in ("", "   "):
        try:
            ProcessingRecord(1, Engine.RESEARCH, ("a",), bad,
                             InvocationOutcome.EMPTY, (), T0, T0)
            assert False
        except ProcessingStateError:
            pass


@probe("bad cycle_id refused")
def _():
    for bad in (0, -1, True, "1", 1.0):
        try:
            ProcessingRecord(bad, Engine.RESEARCH, ("a",), "c",
                             InvocationOutcome.EMPTY, (), T0, T0)
            assert False, bad
        except ProcessingStateError:
            pass


@probe("bad engine refused")
def _():
    try:
        ProcessingRecord(1, "Research", ("a",), "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
        assert False
    except ProcessingStateError:
        pass


@probe("bad outcome refused")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a",), "c", "EMPTY", (), T0, T0)
        assert False
    except ProcessingStateError:
        pass


@probe("duplicate input inside one record refused")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a", "a"), "c",
                         InvocationOutcome.EMPTY, (), T0, T0)
        assert False
    except ProcessingStateError:
        pass


@probe("ended before started refused")
def _():
    try:
        ProcessingRecord(1, Engine.RESEARCH, ("a",), "c",
                         InvocationOutcome.EMPTY, (), T0, T0 - timedelta(seconds=1))
        assert False
    except ProcessingStateError:
        pass


@probe("record()/record_cycle() reject wrong types")
def _():
    s = ProcessingStateStore()
    for bad in ("x", None, 5):
        try:
            s.record(1, bad); assert False
        except ProcessingStateError:
            pass
        try:
            s.record_cycle(bad); assert False
        except ProcessingStateError:
            pass
    try:
        s.repeat_inputs("x"); assert False
    except ProcessingStateError:
        pass


print("== F. cycle commit integrity ==")


@probe("same cycle_id refused twice")
def _():
    s = ProcessingStateStore()
    c = cycle(1, [inv(1)])
    s.record_cycle(c)
    try:
        s.record_cycle(c); assert False
    except ProcessingStateError:
        pass
    assert len(s) == 1


@probe("cycle with only NOT_ATTEMPTED registers the cycle but no records")
def _():
    s = ProcessingStateStore()
    s.record_cycle(cycle(1, [inv(1, outcome=InvocationOutcome.NOT_ATTEMPTED)]))
    assert len(s) == 0
    assert s.has_cycle(1)
    assert s.cycles_recorded() == (1,)


@probe("failed cycle commit does not half-commit")
def _():
    s = ProcessingStateStore()
    good = inv(1)
    bad = InvocationRecord(Engine.RESEARCH, ("b",), "cfg", InvocationOutcome.EMPTY,
                           (), "", T0, T0 - timedelta(seconds=5))
    try:
        s.record_cycle(cycle(1, [good, bad]))
        assert False, "accepted incoherent record"
    except ProcessingStateError:
        pass
    assert len(s) == 0, f"half committed: {len(s)}"
    assert not s.has_processed(Engine.RESEARCH, "src-1")


@probe("orchestrator cycle history survives a rejected commit")
def _():
    s = ProcessingStateStore()
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     processing_store=s)
    o.run_cycle(WorkSet(items=(item(1),)))
    # force a collision by pre-registering the next cycle id
    s.record_cycle(cycle(2, [inv(9)]))
    try:
        o.run_cycle(WorkSet(items=(item(2),)))
        assert False, "collision not surfaced"
    except ProcessingStateError:
        pass
    assert o.cycle_count == 2, o.cycle_count
    assert o.cycle(2) is not None


print("== G. concurrency ==")


@probe("concurrent record() loses nothing")
def _():
    s = ProcessingStateStore()
    def w(k):
        for i in range(200):
            s.record(1, inv(f"{k}-{i}"))
    ts = [threading.Thread(target=w, args=(k,)) for k in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(s) == 1600, len(s)
    assert all(s.attempt_count(Engine.RESEARCH, f"src-{k}-{i}") == 1
               for k in range(8) for i in range(200))


@probe("concurrent read during write is consistent")
def _():
    s = ProcessingStateStore()
    stop = threading.Event()
    errs = []
    def reader():
        while not stop.is_set():
            try:
                n = len(s)
                assert len(s.all()) >= n - 50
            except Exception as e:
                errs.append(e); return
    r = threading.Thread(target=reader); r.start()
    for i in range(500):
        s.record(1, inv(i))
    stop.set(); r.join()
    assert not errs, errs


@probe("index consistent with records after concurrency")
def _():
    s = ProcessingStateStore()
    def w(k):
        for i in range(100):
            s.record(1, inv(inputs=(f"x{k}-{i}", f"y{k}-{i}")))
    ts = [threading.Thread(target=w, args=(k,)) for k in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    total = sum(len(v) for v in s._by_key.values())
    assert total == 2 * len(s), (total, len(s))
    assert sum(len(v) for v in s._by_cycle.values()) == len(s)


print("== H. determinism / query correctness ==")


@probe("attempts in recording order; last_processed_at is latest recorded")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1, t=T0 + timedelta(hours=5)))
    s.record(2, inv(1, t=T0))
    a = s.attempts(Engine.RESEARCH, "src-1")
    assert [r.cycle_id for r in a] == [1, 2]
    assert s.last_processed_at(Engine.RESEARCH, "src-1") == T0


@probe("engines_that_processed exact")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1, engine=Engine.RESEARCH))
    s.record(1, inv(1, engine=Engine.FACT_EXTRACTION))
    s.record(1, inv(2, engine=Engine.VALIDATION))
    assert set(s.engines_that_processed("src-1")) == {
        Engine.RESEARCH, Engine.FACT_EXTRACTION}
    assert s.engines_that_processed("nope") == ()


@probe("unknown lookups are empty, never raising")
def _():
    s = ProcessingStateStore()
    assert s.has_processed(Engine.RESEARCH, "no") is False
    assert s.attempt_count(Engine.RESEARCH, "no") == 0
    assert s.attempts(Engine.RESEARCH, "no") == ()
    assert s.last_processed_at(Engine.RESEARCH, "no") is None
    assert s.for_cycle(99) == ()
    assert s.for_engine(Engine.FEEDBACK) == ()
    assert s.reprocessed_keys() == ()


@probe("for_cycle groups correctly and preserves order")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1)); s.record(2, inv(2)); s.record(1, inv(3))
    assert [r.input_ids[0] for r in s.for_cycle(1)] == ["src-1", "src-3"]
    assert s.cycles_recorded() == (1, 2)


@probe("returned collections are copies")
def _():
    s = ProcessingStateStore()
    s.record(1, inv(1))
    got = s.all()
    assert isinstance(got, tuple)
    assert list(s) == list(got)


print("== I. backward compatibility ==")


@probe("Orchestrator without processing_store unchanged")
def _():
    o = Orchestrator(invoker=lambda i: InvocationResult.empty())
    r = o.run_cycle(WorkSet(items=(item(1),)))
    assert o.processing_store is None
    assert r.attempted_count == 1


@probe("processing_store is positional-safe: clock still keyword-reachable")
def _():
    o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                     clock=lambda: T0)
    assert o.run_cycle(WorkSet(items=(item(1),))).started_at == T0


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all probes passed")
