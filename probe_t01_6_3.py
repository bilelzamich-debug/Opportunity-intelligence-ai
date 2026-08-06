"""Adversarial probe for T01.6.3 failure surfacing. Attack before testing."""
from __future__ import annotations

import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.configuration import ConfigurationError, FailureStore
from oip.enums import Engine, ObjectType
from oip.orchestration import (
    CycleBounds, CycleOutcome, CycleRecord, FailureMaskedError, FailureSurface,
    InvocationOutcome, InvocationRecord, InvocationResult, Orchestrator,
    OrchestrationError, ProcessingStateStore, WorkItem, WorkSet,
)

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
FAILS: list[str] = []


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


def iv(n=1, engine=Engine.RESEARCH, outcome=InvocationOutcome.EMPTY, produced=()):
    return InvocationRecord(engine, (f"src-{n}",), "cfg", outcome, produced,
                            "", T0, T0)


def wi(n=1, engine=Engine.RESEARCH):
    return WorkItem(engine, (f"src-{n}",), "cfg")


def cyc(cid, invocations, outcome=CycleOutcome.COMPLETED, failures=()):
    return CycleRecord(cycle_id=cid, outcome=outcome, bounds=CycleBounds(),
                       invocations=tuple(invocations), failures=tuple(failures),
                       planned_items=len(tuple(invocations)),
                       started_at=T0, ended_at=T0)


def boom(_i):
    raise RuntimeError("engine down")


print("== A. AC1: failed distinguishable from empty ==")


@probe("failed and empty never overlap")
def _():
    s = FailureSurface(cycles=(cyc(1, [
        iv(1, outcome=InvocationOutcome.FAILED),
        iv(2, outcome=InvocationOutcome.EMPTY),
        iv(3, outcome=InvocationOutcome.PRODUCED, produced=("o",)),
    ]),))
    f = {r.input_ids[0] for _, r in s.failed_invocations()}
    e = {r.input_ids[0] for _, r in s.empty_invocations()}
    assert f == {"src-1"}, f
    assert e == {"src-2"}, e
    assert not (f & e)
    assert s.failed_count == 1 and s.empty_count == 1


@probe("produced_nothing is the union but never collapses the causes")
def _():
    s = FailureSurface(cycles=(cyc(1, [
        iv(1, outcome=InvocationOutcome.FAILED),
        iv(2, outcome=InvocationOutcome.EMPTY),
    ]),))
    both = s.produced_nothing()
    assert len(both) == 2
    outcomes = {r.outcome for _, r in both}
    assert outcomes == {InvocationOutcome.FAILED, InvocationOutcome.EMPTY}


@probe("an empty result never appears as a failure end to end")
def _():
    o = Orchestrator(invoker=lambda i: InvocationResult.empty())
    o.run_cycle(WorkSet(items=(wi(1),)))
    s = FailureSurface.over(o)
    assert s.failed_count == 0
    assert s.empty_count == 1
    assert s.failure_free()


@probe("NOT_ATTEMPTED is neither failed nor empty")
def _():
    s = FailureSurface(cycles=(cyc(1, [
        iv(1, outcome=InvocationOutcome.NOT_ATTEMPTED)]),))
    assert s.failed_count == 0
    assert s.empty_count == 0


print("== B. AC2: failures do not silently halt ==")


@probe("cycle continues past a failure")
def _():
    seen = []

    def flaky(i):
        seen.append(i.input_ids[0])
        if i.input_ids[0] == "src-1":
            raise RuntimeError("x")
        return InvocationResult.empty()

    o = Orchestrator(invoker=flaky)
    r = o.run_cycle(WorkSet(items=(wi(1), wi(2), wi(3))))
    assert seen == ["src-1", "src-2", "src-3"], seen
    assert r.attempted_count == 3
    s = FailureSurface.over(o)
    assert len(s.continued_past_failure()) == 1
    assert s.halted_at_failure() == ()


@probe("total engine failure still attempts everything")
def _():
    o = Orchestrator(invoker=boom)
    r = o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(10))))
    assert r.attempted_count == 10
    assert r.not_attempted_count == 0
    assert FailureSurface.over(o).failed_count == 10


@probe("failure on the final item is not reported as a halt")
def _():
    def last_fails(i):
        if i.input_ids[0] == "src-2":
            raise RuntimeError("x")
        return InvocationResult.empty()
    o = Orchestrator(invoker=last_fails)
    o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    s = FailureSurface.over(o)
    assert s.halted_at_failure() == (), "legitimate final failure flagged as halt"
    assert len(s.cycles_with_failures()) == 1


@probe("an engine raising never escapes to the caller")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1),)))   # must not raise


@probe("BaseException-style engine faults are still contained or surfaced")
def _():
    class Nasty(Exception):
        def __str__(self):
            raise RuntimeError("even __str__ explodes")

    o = Orchestrator(invoker=lambda i: (_ for _ in ()).throw(Nasty()))
    try:
        o.run_cycle(WorkSet(items=(wi(1),)))
    except Exception as e:
        raise AssertionError(f"engine fault escaped orchestration: {type(e).__name__}")


print("== C. never masked as completion ==")


@probe("a failure inside a COMPLETED cycle is detected as masked")
def _():
    s = FailureSurface(cycles=(cyc(1, [iv(1, outcome=InvocationOutcome.FAILED)],
                                   outcome=CycleOutcome.COMPLETED),))
    assert s.is_masked_as_completion() is True
    try:
        s.assert_not_masked(); raise AssertionError("did not fail closed")
    except FailureMaskedError:
        pass


@probe("real orchestration never produces a masked cycle")
def _():
    o = Orchestrator(invoker=boom)
    for _ in range(5):
        o.run_cycle(WorkSet(items=(wi(1), wi(2))))
    s = FailureSurface.over(o)
    assert s.masked_cycles() == ()
    s.assert_not_masked()
    assert s.every_failure_is_visible()


@probe("bounded stop with failures is NOT masking, but stays visible")
def _():
    o = Orchestrator(invoker=boom, bounds=CycleBounds(max_work_items=2))
    o.run_cycle(WorkSet(items=tuple(wi(n) for n in range(5))))
    s = FailureSurface.over(o)
    c = o.cycle(1)
    assert c.outcome is CycleOutcome.WORK_LIMIT_REACHED
    assert c.had_failure is True
    assert s.masked_cycles() == (), "bounded stop wrongly called masking"
    assert len(s.cycles_with_failures()) == 1, "failure invisible behind a bound"
    assert s.failed_count == 2


@probe("clean run is not flagged")
def _():
    o = Orchestrator(invoker=lambda i: InvocationResult.empty())
    o.run_cycle(WorkSet(items=(wi(1),)))
    s = FailureSurface.over(o)
    assert s.is_masked_as_completion() is False
    s.assert_not_masked()
    assert s.cycles_with_failures() == ()


print("== D. N-10 attribution ==")


@probe("orchestrated failure satisfies all six identifications")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    o.run_cycle(WorkSet(items=(WorkItem(Engine.VALIDATION, ("a", "b"), "cfg-9"),)))
    r = fs.all()[0]
    assert r.engine is Engine.VALIDATION
    assert r.cycle_id == 1 and r.invocation_index == 0
    assert r.input_ids == ("a", "b")
    assert r.engine_configuration_ref == "cfg-9"
    assert r.recorded_at is not None
    assert r.nature and "RuntimeError" in r.nature[0]
    assert r.satisfies_n10_attribution is True
    assert fs.unattributed() == ()


@probe("invocation index identifies which invocation failed")
def _():
    fs = FailureStore()

    def second_fails(i):
        if i.input_ids[0] == "src-1":
            raise RuntimeError("x")
        return InvocationResult.empty()

    o = Orchestrator(invoker=second_fails, failure_store=fs)
    o.run_cycle(WorkSet(items=(wi(0), wi(1), wi(2))))
    assert fs.all()[0].invocation_index == 1


@probe("acceptance failures remain honestly unattributed, not fabricated")
def _():
    r = FailureRecord("EV-1", ObjectType.EVIDENCE,
                      (RuleResult("V1", RuleOutcome.FAIL, "missing"),), T0, "cfg")
    assert r.engine is None
    assert r.is_attributable_to_invocation is False
    assert r.satisfies_n10_attribution is False


@probe("unattributed records are surfaced, never hidden")
def _():
    fs = FailureStore()
    fs.record(FailureRecord("EV-1", ObjectType.EVIDENCE,
                            (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg"))
    assert len(fs.unattributed()) == 1
    s = FailureSurface(cycles=(cyc(1, [], failures=fs.all()),))
    assert len(s.unattributed_failures()) == 1


@probe("failure store engine/cycle queries")
def _():
    fs = FailureStore()
    o = Orchestrator(invoker=boom, failure_store=fs)
    o.run_cycle(WorkSet(items=(wi(1, Engine.RESEARCH),
                               wi(2, Engine.FEEDBACK))))
    o.run_cycle(WorkSet(items=(wi(3, Engine.RESEARCH),)))
    assert len(fs.for_engine(Engine.RESEARCH)) == 2
    assert len(fs.for_engine(Engine.FEEDBACK)) == 1
    assert len(fs.for_cycle(1)) == 2
    assert len(fs.for_cycle(2)) == 1
    try:
        fs.for_engine("Research"); raise AssertionError("accepted a bare string")
    except ConfigurationError:
        pass


@probe("bare string input_ids refused on a failure record")
def _():
    try:
        FailureRecord("X", ObjectType.EVIDENCE,
                      (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
                      input_ids="abc")
        raise AssertionError("accepted a bare string")
    except ValueError:
        pass


@probe("bad engine refused on a failure record")
def _():
    try:
        FailureRecord("X", ObjectType.EVIDENCE,
                      (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg",
                      engine="Research")
        raise AssertionError("accepted a non-Engine")
    except ValueError:
        pass


print("== E. no policy, no metrics, no severity ==")


@probe("surface exposes no retry/skip/halt/compensate vocabulary")
def _():
    banned = ("retry", "skip", "halt_pipeline", "compensate", "recover",
              "suppress", "resume", "rollback")
    names = [n for n in dir(FailureSurface) if not n.startswith("_")]
    hits = [n for n in names if any(b in n.lower() for b in banned)]
    assert hits == [], hits


@probe("surface exposes no rate/threshold/alert vocabulary [M-57 open]")
def _():
    banned = ("rate", "threshold", "alert", "metric", "sla", "budget_exceeded",
              "healthy", "degraded")
    names = [n for n in dir(FailureSurface) if not n.startswith("_")]
    hits = [n for n in names if any(b in n.lower() for b in banned)]
    assert hits == [], hits


@probe("surface exposes no severity grading")
def _():
    banned = ("severity", "critical", "warning", "priority", "grade")
    names = [n for n in dir(FailureSurface) if not n.startswith("_")]
    hits = [n for n in names if any(b in n.lower() for b in banned)]
    assert hits == [], hits


@probe("summary reports counts only, never rates")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1),)))
    summary = FailureSurface.over(o).summary()
    assert all(isinstance(v, int) for v in summary.values()), summary
    assert not any("rate" in k or "pct" in k for k in summary)


@probe("consecutive_failures reports a fact and triggers nothing")
def _():
    o = Orchestrator(invoker=boom)
    for _ in range(3):
        o.run_cycle(WorkSet(items=(wi(1),)))
    s = FailureSurface.over(o)
    assert s.consecutive_failures() == 3
    o2 = Orchestrator(invoker=lambda i: InvocationResult.empty())
    o2.run_cycle(WorkSet(items=(wi(1),)))
    assert FailureSurface.over(o2).consecutive_failures() == 0


@probe("surface mutates nothing")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1),)))
    before = (o.cycle_count, o.cycle(1).outcome, len(o.cycle(1).failures))
    s = FailureSurface.over(o)
    for fn in (s.failed_invocations, s.empty_invocations, s.masked_cycles,
               s.continued_past_failure, s.halted_at_failure, s.summary,
               s.unattributed_failures, s.failure_records,
               s.engines_with_failures, s.consecutive_failures):
        fn()
    assert (o.cycle_count, o.cycle(1).outcome, len(o.cycle(1).failures)) == before


print("== F. isolation and separation of surfaces ==")


@probe("surface never participates in lineage")
def _():
    s = FailureSurface()
    assert s.participates_in_lineage is False
    assert s.is_intelligence is False


@probe("failure record never participates in lineage")
def _():
    r = FailureRecord("X", ObjectType.EVIDENCE,
                      (RuleResult("V1", RuleOutcome.FAIL, "x"),), T0, "cfg")
    assert r.participates_in_lineage is False


@probe("failure surface and processing surface stay separate [B-12]")
def _():
    fs, ps = FailureStore(), ProcessingStateStore()
    o = Orchestrator(invoker=boom, failure_store=fs, processing_store=ps)
    o.run_cycle(WorkSet(items=(wi(1),)))
    assert len(fs) == 1 and len(ps) == 1
    assert type(fs.all()[0]) is not type(ps.all()[0])


@probe("surface holds no store reference")
def _():
    import dataclasses
    fields = {f.name for f in dataclasses.fields(FailureSurface)}
    assert fields == {"cycles"}, fields


print("== G. malformed input / fail closed ==")


@probe("surface refuses non-CycleRecord input")
def _():
    for bad in ("x", 5, None, object()):
        try:
            FailureSurface(cycles=(bad,))
            raise AssertionError(f"accepted {bad!r}")
        except OrchestrationError:
            pass


@probe("failures_for_engine refuses a non-Engine")
def _():
    try:
        FailureSurface().failures_for_engine("Research")
        raise AssertionError("accepted a bare string")
    except OrchestrationError:
        pass


@probe("empty surface answers everything without raising")
def _():
    s = FailureSurface()
    assert s.failed_invocations() == () and s.empty_invocations() == ()
    assert s.masked_cycles() == () and s.is_masked_as_completion() is False
    assert s.consecutive_failures() == 0 and s.failure_free()
    assert s.engines_with_failures() == ()
    assert s.every_failure_is_visible()
    s.assert_not_masked()


@probe("surface is frozen")
def _():
    s = FailureSurface()
    try:
        s.cycles = ()
        raise AssertionError("mutable")
    except Exception:
        pass


print("== H. concurrency ==")


@probe("concurrent failing cycles all surface")
def _():
    fs = FailureStore()
    orchs = [Orchestrator(invoker=boom, failure_store=fs) for _ in range(8)]
    errs = []

    def run(o):
        try:
            o.run_cycle(WorkSet(items=(wi(1), wi(2))))
        except Exception as e:
            errs.append(e)

    ts = [threading.Thread(target=run, args=(o,)) for o in orchs]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    assert len(fs) == 16, len(fs)
    total = sum(FailureSurface.over(o).failed_count for o in orchs)
    assert total == 16, total


@probe("surface over a live orchestrator is a stable snapshot")
def _():
    o = Orchestrator(invoker=boom)
    o.run_cycle(WorkSet(items=(wi(1),)))
    s = FailureSurface.over(o)
    n = s.failed_count
    o.run_cycle(WorkSet(items=(wi(2),)))
    assert s.failed_count == n, "snapshot mutated under the caller"
    assert FailureSurface.over(o).failed_count == n + 1


print("== I. scale ==")


@probe("20k failures across 200 cycles remain exactly visible")
def _():
    o = Orchestrator(invoker=boom,
                     bounds=CycleBounds(max_work_items=100,
                                        wall_clock_budget_seconds=9999))
    ws = WorkSet(items=tuple(wi(n) for n in range(100)))
    for _ in range(200):
        o.run_cycle(ws)
    s = FailureSurface.over(o)
    assert s.failed_count == 20_000
    assert len(s.cycles_with_failures()) == 200
    assert s.masked_cycles() == ()
    assert s.consecutive_failures() == 200
    s.assert_not_masked()


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all probes passed")
