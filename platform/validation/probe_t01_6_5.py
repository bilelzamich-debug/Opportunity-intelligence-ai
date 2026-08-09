"""Adversarial probe for T01.6.5 sequencing enforcement. Attack before testing."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.configuration import FailureStore
from oip.enums import (ENGINE_INPUT_TYPE, ROOT_ENGINES, Engine, ObjectStatus,
                       ObjectType)
from oip.orchestration import (
    ConcurrencyBoundary, CycleBounds, CycleOutcome, FailureSurface,
    InvocationOutcome, InvocationResult, Orchestrator, ProcessingStateStore,
    SequencingCheck, SequencingError, SequencingGuard, SequencingViolation,
    WorkItem, WorkSet,
)

FAILS: list[str] = []
T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


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
    """Minimal state resolver: id -> type, plus optional status."""

    def __init__(self, mapping=None, statuses=None):
        self.map = dict(mapping or {})
        self.statuses = dict(statuses or {})
        self.reads: list[str] = []

    def resolve_type(self, object_id):
        self.reads.append(object_id)
        return self.map.get(object_id)

    def find(self, object_id):
        if object_id not in self.map:
            return None
        class S:
            status = self.statuses.get(object_id, ObjectStatus.ACTIVE)
        return S()


def wi(engine, inputs=("x",), **kw):
    return WorkItem(engine, tuple(inputs), "cfg", **kw)


def empty(_i):
    return InvocationResult.empty()


print("== A. N-14 mapping is exactly the ratified table ==")


@probe("seven consuming engines, Research and Orchestration absent")
def _():
    assert ENGINE_INPUT_TYPE == {
        Engine.FACT_EXTRACTION: ObjectType.EVIDENCE,
        Engine.PROBLEM_INTELLIGENCE: ObjectType.FACT,
        Engine.PATTERN_INTELLIGENCE: ObjectType.PROBLEM,
        Engine.OPPORTUNITY_INTELLIGENCE: ObjectType.PATTERN,
        Engine.SOLUTION_INTELLIGENCE: ObjectType.OPPORTUNITY,
        Engine.VALIDATION: ObjectType.SOLUTION,
        Engine.FEEDBACK: ObjectType.EXECUTION_RECORD,
    }
    assert Engine.RESEARCH not in ENGINE_INPUT_TYPE
    assert Engine.ORCHESTRATION not in ENGINE_INPUT_TYPE
    assert ROOT_ENGINES == frozenset({Engine.RESEARCH})


@probe("Research requires no inputs [E-V1]")
def _():
    g = SequencingGuard(FakeStore())
    c = g.check(wi(Engine.RESEARCH, ("anything",)))
    assert c.satisfied and not c.requires_inputs and c.inputs == ()


@probe("Orchestration fails closed -- consumes nothing")
def _():
    g = SequencingGuard(FakeStore())
    try:
        g.check(wi(Engine.ORCHESTRATION))
        assert False, "classified an engine that consumes nothing"
    except SequencingError:
        pass


print("== B. missing inputs rejected ==")


@probe("absent input rejected with a reason")
def _():
    g = SequencingGuard(FakeStore())
    c = g.check(wi(Engine.FACT_EXTRACTION, ("EV-1",)))
    assert not c.satisfied
    assert "does not exist" in c.detail
    assert len(c.unsatisfied) == 1


@probe("existing input of the right type accepted")
def _():
    g = SequencingGuard(FakeStore({"EV-1": ObjectType.EVIDENCE}))
    assert g.check(wi(Engine.FACT_EXTRACTION, ("EV-1",))).satisfied


@probe("wrong-type input rejected [N-14]")
def _():
    g = SequencingGuard(FakeStore({"PR-1": ObjectType.PROBLEM}))
    c = g.check(wi(Engine.FACT_EXTRACTION, ("PR-1",)))
    assert not c.satisfied
    assert "consumes Evidence" in c.detail, c.detail


@probe("partial availability rejected, naming only the missing input")
def _():
    g = SequencingGuard(FakeStore({"EV-1": ObjectType.EVIDENCE}))
    c = g.check(wi(Engine.FACT_EXTRACTION, ("EV-1", "EV-2")))
    assert not c.satisfied
    assert len(c.unsatisfied) == 1
    assert c.unsatisfied[0].input_id == "EV-2"


@probe("every engine's correct input type is accepted")
def _():
    for eng, typ in ENGINE_INPUT_TYPE.items():
        g = SequencingGuard(FakeStore({"in": typ}))
        assert g.check(wi(eng, ("in",))).satisfied, eng


@probe("every engine rejects a one-stage-early input")
def _():
    order = [ObjectType.EVIDENCE, ObjectType.FACT, ObjectType.PROBLEM,
             ObjectType.PATTERN, ObjectType.OPPORTUNITY, ObjectType.SOLUTION]
    for eng, typ in ENGINE_INPUT_TYPE.items():
        if typ not in order or order.index(typ) == 0:
            continue
        earlier = order[order.index(typ) - 1]
        g = SequencingGuard(FakeStore({"in": earlier}))
        assert not g.check(wi(eng, ("in",))).satisfied, (eng, earlier)


@probe("Feedback consumes ExecutionRecord despite C-02")
def _():
    g = SequencingGuard(FakeStore({"XR-1": ObjectType.EXECUTION_RECORD}))
    assert g.check(wi(Engine.FEEDBACK, ("XR-1",))).satisfied
    g2 = SequencingGuard(FakeStore({"SO-1": ObjectType.SOLUTION}))
    assert not g2.check(wi(Engine.FEEDBACK, ("SO-1",))).satisfied


print("== C. skipped / reversed / partial pipelines NOT policed [OQ-10, OQ-11] ==")


@probe("stage-skipping work set is NOT rejected [OQ-10 open]")
def _():
    store = FakeStore({"PT-1": ObjectType.PATTERN})
    g = SequencingGuard(store)
    # Opportunity straight from Pattern with no Problem/Fact items in the set
    assert g.check(wi(Engine.OPPORTUNITY_INTELLIGENCE, ("PT-1",))).satisfied


@probe("reverse-ordered work set is NOT rejected [OQ-11 open]")
def _():
    store = FakeStore({"SO-1": ObjectType.SOLUTION,
                       "EV-1": ObjectType.EVIDENCE})
    ws = WorkSet(items=(wi(Engine.VALIDATION, ("SO-1",)),
                        wi(Engine.FACT_EXTRACTION, ("EV-1",))))
    assert SequencingGuard(store).violations(ws) == ()


@probe("partial pipeline (only stage 7) is NOT rejected")
def _():
    store = FakeStore({"SO-1": ObjectType.SOLUTION})
    ws = WorkSet(items=(wi(Engine.VALIDATION, ("SO-1",)),))
    assert SequencingGuard(store).violations(ws) == ()


@probe("duplicated stage is NOT rejected")
def _():
    store = FakeStore({"EV-1": ObjectType.EVIDENCE, "EV-2": ObjectType.EVIDENCE})
    ws = WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),
                        wi(Engine.FACT_EXTRACTION, ("EV-2",))))
    assert SequencingGuard(store).violations(ws) == ()


@probe("guard exposes no stage-skip or backflow vocabulary")
def _():
    banned = ("skip", "backflow", "reverse", "reorder", "sort", "infer",
              "insert", "synthes")
    names = [n for n in dir(SequencingGuard) if not n.startswith("_")]
    assert not [n for n in names if any(b in n.lower() for b in banned)], names


print("== D. status is reported, never required [A1] ==")


@probe("a non-ACTIVE input still satisfies existence")
def _():
    for st in (ObjectStatus.PROPOSED, ObjectStatus.SUPERSEDED,
               ObjectStatus.RETRACTED, ObjectStatus.ARCHIVED,
               ObjectStatus.REJECTED, ObjectStatus.INVALIDATED):
        g = SequencingGuard(FakeStore({"EV-1": ObjectType.EVIDENCE},
                                      {"EV-1": st}))
        assert g.check(wi(Engine.FACT_EXTRACTION, ("EV-1",))).satisfied, st


@probe("status is reported for the caller's own rule")
def _():
    g = SequencingGuard(FakeStore({"EV-1": ObjectType.EVIDENCE},
                                  {"EV-1": ObjectStatus.RETRACTED}))
    c = g.check(wi(Engine.FACT_EXTRACTION, ("EV-1",)))
    assert c.input_statuses == (("EV-1", ObjectStatus.RETRACTED),)


@probe("a resolver without find() still works")
class _:
    pass


@probe("resolver lacking find() degrades gracefully")
def _():
    class Bare:
        def resolve_type(self, oid):
            return ObjectType.EVIDENCE
    g = SequencingGuard(Bare())
    c = g.check(wi(Engine.FACT_EXTRACTION, ("EV-1",)))
    assert c.satisfied
    assert c.input_statuses == (("EV-1", None),)


print("== E. never reorders, never infers, never inserts ==")


@probe("rejected item does not change the position of others")
def _():
    store = FakeStore({"EV-1": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=empty, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(
        wi(Engine.FACT_EXTRACTION, ("MISSING",)),
        wi(Engine.FACT_EXTRACTION, ("EV-1",)),
        wi(Engine.RESEARCH, ("s",)),
    )))
    assert [x.input_ids[0] for x in r.invocations] == ["MISSING", "EV-1", "s"]
    assert r.invocations[0].rejected
    assert r.invocations[1].attempted and r.invocations[2].attempted


@probe("no implicit work item is inserted")
def _():
    store = FakeStore()
    o = Orchestrator(invoker=empty, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(wi(Engine.PATTERN_INTELLIGENCE, ("PR-1",)),)))
    assert len(r.invocations) == 1
    assert r.planned_items == 1


@probe("no missing stage inferred: the set runs as given")
def _():
    seen = []
    store = FakeStore({"EV-1": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=lambda i: (seen.append(i.engine), empty(i))[1],
                     state_resolver=store)
    o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),)))
    assert seen == [Engine.FACT_EXTRACTION]


print("== F. rejection is not an engine failure [N-10] ==")


@probe("rejection does not create a failure record")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=empty, failure_store=fs,
                     state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),)))
    assert r.rejected_count == 1
    assert r.failed_count == 0
    assert len(fs) == 0, "a planning error was recorded as an engine failure"


@probe("rejection is not EMPTY either")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore())
    o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),)))
    s = FailureSurface.over(o)
    assert s.failed_count == 0
    assert s.empty_count == 0, "rejection counted as an empty result"


@probe("rejection never masked: cycle reports it")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),)))
    assert r.had_sequencing_violation
    assert len(r.rejected_invocations()) == 1
    assert r.rejected_invocations()[0].detail


@probe("real engine failures still recorded alongside rejections")
def _():
    fs = FailureStore()
    store = FakeStore({"EV-1": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
                     failure_store=fs, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(
        wi(Engine.FACT_EXTRACTION, ("EV-1",)),
        wi(Engine.FACT_EXTRACTION, ("MISSING",)),
    )))
    assert r.failed_count == 1 and r.rejected_count == 1
    assert len(fs) == 1


print("== G. cycle continues; bounds and N-11 preserved ==")


@probe("cycle continues past a rejection")
def _():
    store = FakeStore({"EV-1": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=empty, state_resolver=store)
    r = o.run_cycle(WorkSet(items=(
        wi(Engine.FACT_EXTRACTION, ("MISSING",)),
        wi(Engine.FACT_EXTRACTION, ("EV-1",)),
    )))
    assert r.rejected_count == 1
    assert r.attempted_count == 1
    assert len(r.invocations) == 2


@probe("rejected items count against the work bound")
def _():
    store = FakeStore()
    o = Orchestrator(invoker=empty, state_resolver=store,
                     bounds=CycleBounds(max_work_items=3))
    r = o.run_cycle(WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(10))))
    assert r.rejected_count == 3, r.rejected_count
    assert r.outcome is CycleOutcome.WORK_LIMIT_REACHED


@probe("N-11 barrier preserved with a resolver present")
def _():
    store = FakeStore({f"EV-{n}": ObjectType.EVIDENCE for n in range(8)})
    store.map["PR-1"] = ObjectType.PROBLEM
    o = Orchestrator(invoker=empty, max_workers=4, state_resolver=store)
    r = o.run_cycle(WorkSet(items=tuple(
        [wi(Engine.FACT_EXTRACTION, (f"EV-{n}",)) for n in range(4)] +
        [wi(Engine.PATTERN_INTELLIGENCE, ("PR-1",))] +
        [wi(Engine.FACT_EXTRACTION, (f"EV-{n}",)) for n in range(4, 8)]
    )))
    ConcurrencyBoundary(r).assert_holds()
    assert r.attempted_count == 9


@probe("parallel path also rejects -- no bypass")
def _():
    o = Orchestrator(invoker=empty, max_workers=6, state_resolver=FakeStore())
    r = o.run_cycle(WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(12))))
    assert r.rejected_count == 12, r.rejected_count
    assert r.attempted_count == 0


@probe("cycles remain serialised and monotonic")
def _():
    o = Orchestrator(invoker=empty, state_resolver=FakeStore(), max_workers=4)
    for _ in range(5):
        o.run_cycle(WorkSet(items=(wi(Engine.RESEARCH, ("s",)),)))
    assert [c.cycle_id for c in o.cycles] == [1, 2, 3, 4, 5]


print("== H. processing state: a rejection is not processing [T01.6.2] ==")


@probe("rejected item never recorded as processed")
def _():
    ps = ProcessingStateStore()
    o = Orchestrator(invoker=empty, processing_store=ps,
                     state_resolver=FakeStore())
    o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),)))
    assert len(ps) == 0, "a rejected item was recorded as processed"
    assert not ps.has_processed(Engine.FACT_EXTRACTION, "EV-1")


@probe("mixed cycle records only what actually ran")
def _():
    ps = ProcessingStateStore()
    store = FakeStore({"EV-1": ObjectType.EVIDENCE})
    o = Orchestrator(invoker=empty, processing_store=ps, state_resolver=store)
    o.run_cycle(WorkSet(items=(
        wi(Engine.FACT_EXTRACTION, ("EV-1",)),
        wi(Engine.FACT_EXTRACTION, ("MISSING",)),
    )))
    assert len(ps) == 1
    assert ps.has_processed(Engine.FACT_EXTRACTION, "EV-1")
    assert not ps.has_processed(Engine.FACT_EXTRACTION, "MISSING")


print("== I. reads state only; no content, no writes ==")


@probe("guard reads only the declared input ids")
def _():
    store = FakeStore({"EV-1": ObjectType.EVIDENCE})
    SequencingGuard(store).check(wi(Engine.FACT_EXTRACTION, ("EV-1",)))
    assert store.reads == ["EV-1"], store.reads


@probe("guard never calls a content accessor")
def _():
    class Trap:
        def resolve_type(self, oid):
            return ObjectType.EVIDENCE
        def get(self, oid):
            raise AssertionError("content read")
        def get_evidence(self, oid):
            raise AssertionError("content read")
    SequencingGuard(Trap()).check(wi(Engine.FACT_EXTRACTION, ("EV-1",)))


@probe("guard against a real KnowledgeStore reads no content")
def _():
    from oip.store import KnowledgeStore
    ks = KnowledgeStore()
    g = SequencingGuard(ks)
    c = g.check(wi(Engine.FACT_EXTRACTION, ("EV-1",)))
    assert not c.satisfied
    assert len(ks) == 0, "guard mutated the store"


@probe("guard is frozen and not lineage")
def _():
    g = SequencingGuard(FakeStore())
    assert g.participates_in_lineage is False
    try:
        g.resolver = None
        assert False, "mutable"
    except Exception:
        pass


print("== J. fail closed ==")


@probe("resolver lacking resolve_type refused")
def _():
    for bad in (object(), None, "store", 5):
        try:
            SequencingGuard(bad)
            assert False, f"accepted {bad!r}"
        except SequencingError:
            pass


@probe("check rejects a non-WorkItem")
def _():
    g = SequencingGuard(FakeStore())
    for bad in ("x", None, 5):
        try:
            g.check(bad); assert False
        except SequencingError:
            pass


@probe("report rejects a non-WorkSet")
def _():
    g = SequencingGuard(FakeStore())
    try:
        g.report("x"); assert False
    except SequencingError:
        pass


@probe("assert_sequenced fails closed")
def _():
    g = SequencingGuard(FakeStore())
    try:
        g.assert_sequenced(wi(Engine.FACT_EXTRACTION, ("EV-1",)))
        assert False, "did not fail closed"
    except SequencingViolation as e:
        assert "does not exist" in str(e)


@probe("a raising resolver does not corrupt the cycle")
def _():
    class Hostile:
        def resolve_type(self, oid):
            raise RuntimeError("store down")
    o = Orchestrator(invoker=empty, state_resolver=Hostile())
    try:
        r = o.run_cycle(WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("EV-1",)),)))
    except Exception:
        assert o.cycle_count == 0 or o.cycle(1) is not None
        assert o.is_running is False, "orchestrator wedged"
        return
    assert r.failed_count == 1 or r.rejected_count == 1


print("== K. backward compatibility ==")


@probe("no resolver = unchanged behaviour")
def _():
    o = Orchestrator(invoker=empty)
    assert o.state_resolver is None
    r = o.run_cycle(WorkSet(items=(wi(Engine.PATTERN_INTELLIGENCE, ("PR-9",)),)))
    assert r.attempted_count == 1 and r.rejected_count == 0


@probe("prior public API intact")
def _():
    import oip.orchestration as m
    for n in ("CycleBounds", "WorkItem", "WorkSet", "InvocationResult",
              "Orchestrator", "CycleRecord", "FailureSurface",
              "ProcessingStateStore", "ConcurrencyBoundary", "ExecutionPhase",
              "ConcurrencyClass", "FailureMaskedError", "ConcurrencyViolation"):
        assert hasattr(m, n), n


@probe("field order preserved, state_resolver appended")
def _():
    import inspect
    p = list(inspect.signature(Orchestrator).parameters)
    assert p[:5] == ["invoker", "bounds", "failure_store", "processing_store",
                     "clock"], p
    assert p[-1] == "state_resolver", p


@probe("InvocationOutcome gained exactly one member")
def _():
    assert len(list(InvocationOutcome)) == 5
    assert InvocationOutcome.REJECTED_OUT_OF_ORDER.value == "REJECTED_OUT_OF_ORDER"


print("== L. concurrency and scale ==")


@probe("concurrent cycles with a shared resolver stay exact")
def _():
    store = FakeStore({f"EV-{n}": ObjectType.EVIDENCE for n in range(50)})
    errs, counts = [], []

    def run(k):
        try:
            o = Orchestrator(invoker=empty, max_workers=4, state_resolver=store)
            r = o.run_cycle(WorkSet(items=tuple(
                [wi(Engine.FACT_EXTRACTION, (f"EV-{n}",)) for n in range(25)] +
                [wi(Engine.FACT_EXTRACTION, (f"NOPE-{n}",)) for n in range(5)]
            )))
            counts.append((r.attempted_count, r.rejected_count))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=run, args=(k,)) for k in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert set(counts) == {(25, 5)}, set(counts)


@probe("10k mixed items at volume")
def _():
    store = FakeStore({f"EV-{n}": ObjectType.EVIDENCE for n in range(5000)})
    o = Orchestrator(invoker=empty, max_workers=8, state_resolver=store,
                     bounds=CycleBounds(max_work_items=20000,
                                        wall_clock_budget_seconds=9999))
    items = []
    for n in range(5000):
        items.append(wi(Engine.FACT_EXTRACTION, (f"EV-{n}",)))
        items.append(wi(Engine.FACT_EXTRACTION, (f"GONE-{n}",)))
    r = o.run_cycle(WorkSet(items=tuple(items)))
    assert r.attempted_count == 5000
    assert r.rejected_count == 5000
    assert r.failed_count == 0


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all probes passed")
