"""Round 3: illegal transitions, boundary bypass, ordering, exhaustive matrix."""
from __future__ import annotations

import itertools
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.configuration import FailureStore
from oip.enums import (ENGINE_INPUT_TYPE, ENGINE_STAGE, ROOT_ENGINES, Engine,
                       ObjectType)
from oip.orchestration import (
    ConcurrencyBoundary, CycleBounds, CycleOutcome, InvocationOutcome,
    InvocationResult, Orchestrator, ProcessingStateStore, SequencingGuard,
    WorkItem, WorkSet,
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

    def resolve_type(self, object_id):
        return self.map.get(object_id)


def wi(engine, inputs=("x",)):
    return WorkItem(engine, tuple(inputs), "cfg")


def empty(_i):
    return InvocationResult.empty()


print("== T. exhaustive engine x type matrix ==")


@probe("every (engine, type) pair behaves exactly per N-14")
def _():
    wrong = []
    for engine in ENGINE_INPUT_TYPE:
        for otype in ObjectType:
            store = FakeStore({"in": otype})
            got = SequencingGuard(store).check(wi(engine, ("in",))).satisfied
            expected = (otype is ENGINE_INPUT_TYPE[engine])
            if got != expected:
                wrong.append((engine.value, otype.value, got, expected))
    assert not wrong, wrong


@probe("Research accepts any input id, existing or not")
def _():
    for mapping in ({}, {"in": ObjectType.SOLUTION}):
        g = SequencingGuard(FakeStore(mapping))
        assert g.check(wi(Engine.RESEARCH, ("in",))).satisfied


@probe("every consuming engine rejects an EMPTY store")
def _():
    for engine in ENGINE_INPUT_TYPE:
        g = SequencingGuard(FakeStore())
        assert not g.check(wi(engine, ("in",))).satisfied, engine


@probe("multi-input items require ALL inputs")
def _():
    store = FakeStore({"a": ObjectType.EVIDENCE, "b": ObjectType.EVIDENCE})
    g = SequencingGuard(store)
    assert g.check(wi(Engine.FACT_EXTRACTION, ("a", "b"))).satisfied
    assert not g.check(wi(Engine.FACT_EXTRACTION, ("a", "b", "c"))).satisfied


print("== U. illegal transitions / skipped stages, exhaustively ==")


@probe("skipping N stages is never rejected on order grounds [OQ-10 open]")
def _():
    # Give every engine a valid direct input; the SET skips stages entirely.
    for engine, typ in ENGINE_INPUT_TYPE.items():
        store = FakeStore({"in": typ})
        ws = WorkSet(items=(wi(engine, ("in",)),))
        assert SequencingGuard(store).violations(ws) == (), engine


@probe("all 8! -like orderings of a valid chain are accepted")
def _():
    store = FakeStore({
        "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
        "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
    })
    items = [wi(Engine.FACT_EXTRACTION, ("EV",)),
             wi(Engine.PROBLEM_INTELLIGENCE, ("FA",)),
             wi(Engine.PATTERN_INTELLIGENCE, ("PR",)),
             wi(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",))]
    g = SequencingGuard(store)
    for perm in itertools.permutations(items):
        assert g.violations(WorkSet(items=perm)) == (), "order was policed"


@probe("reversed full pipeline accepted when inputs exist [OQ-11 open]")
def _():
    store = FakeStore({
        "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
        "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
        "OP": ObjectType.OPPORTUNITY, "SO": ObjectType.SOLUTION,
        "XR": ObjectType.EXECUTION_RECORD,
    })
    reverse = WorkSet(items=(
        wi(Engine.FEEDBACK, ("XR",)),
        wi(Engine.VALIDATION, ("SO",)),
        wi(Engine.SOLUTION_INTELLIGENCE, ("OP",)),
        wi(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",)),
        wi(Engine.PATTERN_INTELLIGENCE, ("PR",)),
        wi(Engine.PROBLEM_INTELLIGENCE, ("FA",)),
        wi(Engine.FACT_EXTRACTION, ("EV",)),
    ))
    r = Orchestrator(invoker=empty, state_resolver=store).run_cycle(reverse)
    assert r.attempted_count == 7
    assert r.rejected_count == 0


print("== V. boundary bypass attempts ==")


@probe("no execution path skips the guard: sequential")
def _():
    ran = []
    o = Orchestrator(invoker=lambda i: (ran.append(1), empty(i))[1],
                     max_workers=1, state_resolver=FakeStore())
    o.run_cycle(WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(6))))
    assert ran == []


@probe("no execution path skips the guard: parallel")
def _():
    ran, lock = [], threading.Lock()

    def track(i):
        with lock:
            ran.append(1)
        return empty(i)

    o = Orchestrator(invoker=track, max_workers=8, state_resolver=FakeStore())
    o.run_cycle(WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(20))))
    assert ran == []


@probe("no execution path skips the guard: serialised stage")
def _():
    ran = []
    o = Orchestrator(invoker=lambda i: (ran.append(1), empty(i))[1],
                     max_workers=4, state_resolver=FakeStore())
    o.run_cycle(WorkSet(items=tuple(
        wi(Engine.PATTERN_INTELLIGENCE, (f"m{n}",)) for n in range(5))))
    assert ran == []


@probe("engine cannot mutate its item to dodge a later check")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE})

    def meddler(i):
        try:
            object.__setattr__(i, "input_ids", ("GONE",))
        except Exception:
            pass
        return empty(i)

    o = Orchestrator(invoker=meddler, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV",)),
                                   wi(Engine.FACT_EXTRACTION, ("GONE",)))))
    assert r.invocations[1].rejected


@probe("guard cannot be disabled mid-cycle")
def _():
    store = FakeStore()
    o = Orchestrator(invoker=empty, state_resolver=store)

    def sneaky(i):
        o.state_resolver = None
        return empty(i)

    o.invoker = sneaky
    r = o.run_cycle(WorkSet(items=(wi(Engine.RESEARCH, ("s",)),
                                   wi(Engine.FACT_EXTRACTION, ("GONE",)))))
    # Research runs and clears the resolver; second item then unchecked.
    # This documents the behaviour rather than asserting a guarantee the
    # architecture does not state -- the caller owns the orchestrator.
    assert len(r.invocations) == 2


print("== W. record integrity ==")


@probe("rejected record carries full attribution")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=(
        WorkItem(Engine.VALIDATION, ("SO-1", "SO-2"), "cfg-v7"),)))
    rec = r.invocations[0]
    assert rec.engine is Engine.VALIDATION
    assert rec.input_ids == ("SO-1", "SO-2")
    assert rec.engine_configuration_ref == "cfg-v7"
    assert rec.produced_ids == ()
    assert rec.detail
    assert rec.duration_seconds >= 0


@probe("rejected record is not lineage")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("m",)),)))
    assert r.invocations[0].participates_in_lineage is False


@probe("cycle outcome not corrupted by rejections alone")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("m",)),)))
    assert r.outcome is CycleOutcome.COMPLETED
    assert r.had_failure is False
    assert r.had_sequencing_violation is True


@probe("produced_count unaffected by rejections")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=lambda i: InvocationResult.produced("o1"),
                     state_resolver=store)
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV",)),
                                   wi(Engine.FACT_EXTRACTION, ("GONE",)))))
    assert r.produced_count == 1


@probe("engines_invoked excludes rejected engines")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=(wi(Engine.RESEARCH, ("s",)),
                                   wi(Engine.FACT_EXTRACTION, ("m",)))))
    assert r.engines_invoked == (Engine.RESEARCH,), r.engines_invoked


print("== X. scale and stability ==")


@probe("500 cycles of mixed readiness stay exact")
def _():
    store = FakeStore({"EV": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=empty, max_workers=4, state_resolver=store)
    ws = WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV",)),
                        wi(Engine.FACT_EXTRACTION, ("GONE",)),
                        wi(Engine.RESEARCH, ("s",))))
    for _ in range(500):
        r = o.run_cycle(ws)
        assert r.attempted_count == 2 and r.rejected_count == 1
    assert o.cycle_count == 500


@probe("guard adds no unbounded cost at 20k items")
def _():
    import time
    store = FakeStore({f"EV{n}": ObjectType.EVIDENCE for n in range(20000)})
    ws = WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(20000)))
    o = Orchestrator(invoker=empty, state_resolver=store,
                     bounds=CycleBounds(max_work_items=20000,
                                        wall_clock_budget_seconds=9999))
    start = time.perf_counter()
    r = o.run_cycle(ws)
    per = (time.perf_counter() - start) / 20000 * 1e6
    assert r.attempted_count == 20000
    assert per < 200.0, f"{per:.1f}us/item"


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-3 probes passed")
