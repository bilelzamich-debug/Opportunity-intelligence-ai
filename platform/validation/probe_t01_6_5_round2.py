"""Round 2: hostile resolvers, intra-cycle visibility, real store, races."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.configuration import FailureStore
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.orchestration import (
    ConcurrencyBoundary, CycleBounds, CycleOutcome, FailureSurface,
    InvocationOutcome, InvocationResult, Orchestrator, ProcessingStateStore,
    SequencingError, SequencingGuard, WorkItem, WorkSet,
)

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


class FakeStore:
    def __init__(self, mapping=None):
        self.map = dict(mapping or {})
        self.lock = threading.Lock()

    def resolve_type(self, object_id):
        with self.lock:
            return self.map.get(object_id)


def wi(engine, inputs=("x",)):
    return WorkItem(engine, tuple(inputs), "cfg")


def empty(_i):
    return InvocationResult.empty()


print("== M. hostile resolvers ==")


@probe("raising resolver does not lose the cycle")
def _():
    class Hostile:
        def resolve_type(self, oid):
            raise RuntimeError("store down")
    o = Orchestrator(invoker=empty, state_resolver=Hostile())
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("a",)),
                                   wi(Engine.FACT_EXTRACTION, ("b",)))))
    assert o.cycle_count == 1
    assert r.rejected_count == 2
    assert r.failed_count == 0, "a resolver fault was blamed on an engine"


@probe("raising resolver fails CLOSED, never admits the item")
def _():
    ran = []

    class Hostile:
        def resolve_type(self, oid):
            raise RuntimeError("down")

    o = Orchestrator(invoker=lambda i: (ran.append(1), empty(i))[1],
                     state_resolver=Hostile())
    o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("a",)),)))
    assert ran == [], "engine ran despite unanswerable readiness check"


@probe("hostile exception message still rendered")
def _():
    class Nasty(Exception):
        def __str__(self): raise RuntimeError("no str")

    class Hostile:
        def resolve_type(self, oid):
            raise Nasty()

    o = Orchestrator(invoker=empty, state_resolver=Hostile())
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("a",)),)))
    assert r.rejected_count == 1
    assert "Nasty" in r.invocations[0].detail


@probe("control signals from the resolver propagate")
def _():
    for sig in (KeyboardInterrupt, SystemExit):
        class S:
            def resolve_type(self, oid):
                raise sig()
        o = Orchestrator(invoker=empty, state_resolver=S())
        try:
            o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("a",)),)))
            raise AssertionError(f"{sig.__name__} swallowed")
        except sig:
            pass


@probe("resolver returning nonsense is treated as absent")
def _():
    class Weird:
        def resolve_type(self, oid):
            return "Evidence"     # a str, not an ObjectType
    g = SequencingGuard(Weird())
    c = g.check(wi(Engine.FACT_EXTRACTION, ("a",)))
    assert not c.satisfied, "a non-ObjectType was accepted as a type match"


@probe("resolver fault in a parallel phase does not corrupt the record")
def _():
    class Hostile:
        def resolve_type(self, oid):
            raise RuntimeError("down")
    o = Orchestrator(invoker=empty, max_workers=6, state_resolver=Hostile())
    r = o.run_cycle(WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"a{n}",)) for n in range(12))))
    assert len(r.invocations) == 12
    assert r.rejected_count == 12
    assert [x.input_ids[0] for x in r.invocations] == [f"a{n}" for n in range(12)]


print("== N. real KnowledgeStore integration ==")


@probe("guard works against a real store with real objects")
def _():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    from datetime import timedelta
    from oip.store import KnowledgeStore
    from oip.identity import IdentityAllocator
    import conftest as cf

    store = KnowledgeStore()
    alloc = IdentityAllocator()
    ev = cf.write_evidence(store, alloc).object_id
    g = SequencingGuard(store)
    assert g.check(wi(Engine.FACT_EXTRACTION, (ev,))).satisfied
    assert not g.check(wi(Engine.FACT_EXTRACTION, ("EV-nope",))).satisfied
    # An Evidence id is NOT valid input for Problem Intelligence [N-14]
    assert not g.check(wi(Engine.PROBLEM_INTELLIGENCE, (ev,))).satisfied


@probe("real store: status reported, existence still satisfied")
def _():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    from oip.store import KnowledgeStore
    from oip.identity import IdentityAllocator
    import conftest as cf

    store = KnowledgeStore()
    alloc = IdentityAllocator()
    ev = cf.write_evidence(store, alloc).object_id
    c = SequencingGuard(store).check(wi(Engine.FACT_EXTRACTION, (ev,)))
    assert c.satisfied
    assert c.input_statuses[0][1] is not None


@probe("guard does not mutate a real store")
def _():
    from oip.store import KnowledgeStore
    store = KnowledgeStore()
    before = len(store)
    SequencingGuard(store).check(wi(Engine.FACT_EXTRACTION, ("nope",)))
    assert len(store) == before


print("== O. intra-cycle visibility [A4] ==")


@probe("input written by an earlier item is visible to a later one")
def _():
    store = FakeStore()

    def producing(item):
        if item.engine is Engine.RESEARCH:
            with store.lock:
                store.map["EV-new"] = ObjectType.EVIDENCE
            return InvocationResult.produced("EV-new")
        return InvocationResult.empty()

    o = Orchestrator(invoker=producing, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(
        wi(Engine.RESEARCH, ("src",)),
        wi(Engine.FACT_EXTRACTION, ("EV-new",)),
    )))
    assert r.rejected_count == 0, "committed state was not observed"
    assert r.attempted_count == 2


@probe("an input NOT yet written is still rejected")
def _():
    store = FakeStore()
    o = Orchestrator(invoker=empty, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(
        wi(Engine.RESEARCH, ("src",)),
        wi(Engine.FACT_EXTRACTION, ("EV-never",)),
    )))
    assert r.rejected_count == 1
    assert r.attempted_count == 1


@probe("no future work is inferred: order still governs")
def _():
    store = FakeStore()

    def producing(item):
        if item.engine is Engine.RESEARCH:
            with store.lock:
                store.map["EV-late"] = ObjectType.EVIDENCE
        return InvocationResult.empty()

    o = Orchestrator(invoker=producing, state_resolver=store)
    # Fact Extraction placed BEFORE the Research that would create its input
    r = o.run_cycle(WorkSet(items=(
        wi(Engine.FACT_EXTRACTION, ("EV-late",)),
        wi(Engine.RESEARCH, ("src",)),
    )))
    assert r.invocations[0].rejected, "guard predicted a future write"
    assert r.invocations[1].attempted


print("== P. mixed-stage work sets ==")


@probe("a full nine-stage chain runs when all inputs exist")
def _():
    store = FakeStore({
        "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
        "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
        "OP": ObjectType.OPPORTUNITY, "SO": ObjectType.SOLUTION,
        "XR": ObjectType.EXECUTION_RECORD,
    })
    ws = WorkSet(items=(
        wi(Engine.RESEARCH, ("src",)),
        wi(Engine.FACT_EXTRACTION, ("EV",)),
        wi(Engine.PROBLEM_INTELLIGENCE, ("FA",)),
        wi(Engine.PATTERN_INTELLIGENCE, ("PR",)),
        wi(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",)),
        wi(Engine.SOLUTION_INTELLIGENCE, ("OP",)),
        wi(Engine.VALIDATION, ("SO",)),
        wi(Engine.FEEDBACK, ("XR",)),
    ))
    o = Orchestrator(invoker=empty, state_resolver=store)
    r = o.run_cycle(ws)
    assert r.attempted_count == 8, r.attempted_count
    assert r.rejected_count == 0


@probe("only the unready stages of a chain are rejected")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE, "PR": ObjectType.PROBLEM})
    ws = WorkSet(items=(
        wi(Engine.FACT_EXTRACTION, ("EV",)),
        wi(Engine.PROBLEM_INTELLIGENCE, ("FA-missing",)),
        wi(Engine.PATTERN_INTELLIGENCE, ("PR",)),
        wi(Engine.OPPORTUNITY_INTELLIGENCE, ("PT-missing",)),
    ))
    r = Orchestrator(invoker=empty, state_resolver=store).run_cycle(ws)
    assert [x.rejected for x in r.invocations] == [False, True, False, True]


@probe("mixed-stage set preserves the N-11 barrier")
def _():
    store = FakeStore({f"EV{n}": ObjectType.EVIDENCE for n in range(6)})
    store.map["PR"] = ObjectType.PROBLEM
    ws = WorkSet(items=tuple(
        [wi(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(3)] +
        [wi(Engine.PATTERN_INTELLIGENCE, ("PR",))] +
        [wi(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(3, 6)]))
    r = Orchestrator(invoker=empty, max_workers=4,
                     state_resolver=store).run_cycle(ws)
    ConcurrencyBoundary(r).assert_holds()
    assert r.attempted_count == 7


print("== Q. determinism ==")


@probe("rejection set is identical across repeated runs")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE})
    ws = WorkSet(items=tuple(
        [wi(Engine.FACT_EXTRACTION, ("EV",)),
         wi(Engine.FACT_EXTRACTION, ("GONE",))] * 6))
    seen = set()
    for _ in range(10):
        r = Orchestrator(invoker=empty, max_workers=6,
                         state_resolver=store).run_cycle(ws)
        seen.add(tuple(x.rejected for x in r.invocations))
    assert len(seen) == 1, seen


@probe("sequential and parallel agree exactly")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE})
    ws = WorkSet(items=tuple(
        [wi(Engine.FACT_EXTRACTION, ("EV",)),
         wi(Engine.FACT_EXTRACTION, ("GONE",))] * 5))
    a = Orchestrator(invoker=empty, max_workers=1, state_resolver=store).run_cycle(ws)
    b = Orchestrator(invoker=empty, max_workers=5, state_resolver=store).run_cycle(ws)
    assert (a.attempted_count, a.rejected_count, a.outcome) == \
           (b.attempted_count, b.rejected_count, b.outcome)
    assert [x.outcome for x in a.invocations] == [x.outcome for x in b.invocations]


@probe("bounds identical with and without rejections")
def _():
    store = FakeStore()
    ws = WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(12)))
    for lim in (1, 4, 7, 12, 20):
        a = Orchestrator(invoker=empty, max_workers=1, state_resolver=store,
                         bounds=CycleBounds(max_work_items=lim)).run_cycle(ws)
        b = Orchestrator(invoker=empty, max_workers=4, state_resolver=store,
                         bounds=CycleBounds(max_work_items=lim)).run_cycle(ws)
        assert (a.rejected_count, a.not_attempted_count, a.outcome) == \
               (b.rejected_count, b.not_attempted_count, b.outcome), lim


print("== R. no regression in prior tasks ==")


@probe("T01.6.3 failure surfacing unaffected")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     state_resolver=store, max_workers=4)
    for _ in range(4):
        o.run_cycle(WorkSet(items=tuple(
            wi(Engine.FACT_EXTRACTION, ("EV",)) for _ in range(3))))
    s = FailureSurface.over(o)
    assert s.failed_count == 12
    assert s.masked_cycles() == ()
    s.assert_not_masked()


@probe("T01.6.2 idempotence unaffected by rejections")
def _():
    ps = ProcessingStateStore()
    store = FakeStore({"EV": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=empty, processing_store=ps, state_resolver=store)
    ws = WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV",)),
                        wi(Engine.FACT_EXTRACTION, ("GONE",))))
    o.run_cycle(ws); o.run_cycle(ws)
    assert len(ps) == 2
    assert ps.attempt_count(Engine.FACT_EXTRACTION, "EV") == 2
    assert not ps.has_processed(Engine.FACT_EXTRACTION, "GONE")


@probe("T01.6.4 boundary intact across many mixed cycles")
def _():
    import random
    store = FakeStore({"EV": ObjectType.EVIDENCE, "PR": ObjectType.PROBLEM})
    engines = [(Engine.FACT_EXTRACTION, "EV"), (Engine.PATTERN_INTELLIGENCE, "PR"),
               (Engine.FACT_EXTRACTION, "GONE")]
    rng = random.Random(5)
    o = Orchestrator(invoker=empty, max_workers=4, state_resolver=store)
    for _ in range(200):
        items = tuple(wi(*rng.choice(engines)[:1], (rng.choice(engines)[1],))
                      for _ in range(rng.randint(1, 6)))
        ConcurrencyBoundary(o.run_cycle(WorkSet(items=items))).assert_holds()


print("== S. concurrency of the guard itself ==")


@probe("guard is safe under concurrent use")
def _():
    store = FakeStore({f"EV{n}": ObjectType.EVIDENCE for n in range(100)})
    g = SequencingGuard(store)
    errs, results = [], []
    lock = threading.Lock()

    def run(k):
        try:
            out = [g.check(wi(Engine.FACT_EXTRACTION, (f"EV{n}",))).satisfied
                   for n in range(100)]
            with lock:
                results.append(all(out))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=run, args=(k,)) for k in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert results == [True] * 8


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-2 probes passed")
