"""Mechanical architecture verification for T01.6.4.

Checks properties against the ratified documents by extraction.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip import orchestration as orch  # noqa: E402
from oip.enums import (  # noqa: E402
    CONCURRENT_STAGES, CREATE_AUTHORITY, ENGINE_STAGE, SERIALISED_STAGES,
    Engine, ObjectType,
)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))


src = (ROOT / "oip" / "orchestration.py").read_text()
tree = ast.parse(src)


def wi(n=1, engine=Engine.RESEARCH, **kw):
    return orch.WorkItem(engine, (f"s-{n}",), "cfg", **kw)


def empty(_i):
    return orch.InvocationResult.empty()


# --- 1. Acceptance criteria quoted from the ratified backlog --------------
backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
task = backlog.split("#### `T01.6.4`")[1].split("#### `T01.6.5`")[0]
criteria = re.findall(r"^- (.+)$", task, re.M)
check("backlog states exactly 3 acceptance criteria", len(criteria) == 3, str(criteria))
check("AC1 is problem-stage-onward serialised",
      any("Problem-stage-onward writes serialised" in c for c in criteria))
check("AC2 is stable population per batch",
      any("stable population per batch" in c for c in criteria))
check("AC3 is version branching impossible",
      any("Version branching impossible" in c for c in criteria))
check("backlog: depends on T01.6.2", "`T01.6.2`" in task)
check("backlog: blocks T05.1.1", "`T05.1.1`" in task)

# --- 2. N-11's table reproduced exactly ------------------------------------
n11 = (DOCS / "decisions" / "N-11-concurrency.md").read_text()
check("N-11 is RATIFIED", "| **Status** | `RATIFIED` |" in n11)
check("N-11 states the decision verbatim",
      "Acquisition and extraction may run concurrently. Interpretation from "
      "Problem onward is serialised." in n11)
check("N-11 table: stages 1-2 concurrent",
      "| 1 Evidence, 2 Facts | **Concurrent**" in n11)
check("N-11 table: stages 3-9 serialised",
      "| 3 Problems … 9 Feedback | **Serialised** — one batch at a time |" in n11)
check("implementation puts exactly stages 1-2 in the concurrent class",
      CONCURRENT_STAGES == frozenset({1, 2}), str(CONCURRENT_STAGES))
check("implementation puts exactly stages 3-9 in the serialised class",
      SERIALISED_STAGES == frozenset({3, 4, 5, 6, 7, 8, 9}), str(SERIALISED_STAGES))
check("stage classes partition 1-9 with no overlap",
      CONCURRENT_STAGES | SERIALISED_STAGES == set(range(1, 10))
      and not CONCURRENT_STAGES & SERIALISED_STAGES)
check("exactly two concurrency classes exist",
      len(list(orch.ConcurrencyClass)) == 2)

# --- 3. Stage mapping matches IOM 2.6 --------------------------------------
iom = (DOCS / "PKP_Intelligence_Object_Model.md").read_text()
stage_table = iom.split("### 2.6 Stage Ownership")[1].split("###")[0]
for engine_name, stage in [
    ("Research", 1), ("Fact Extraction", 2), ("Problem Intelligence", 3),
    ("Pattern Intelligence", 4), ("Opportunity Intelligence", 5),
    ("Solution Intelligence", 6), ("Validation", 7), ("Feedback", 9),
]:
    check(f"IOM 2.6 assigns {engine_name} to stage {stage}",
          re.search(rf"\| {stage} — .+ \| {re.escape(engine_name)} \|", stage_table)
          is not None)
check("IOM 2.6 records stage 8 as having no owning engine",
      "**none (CONTRADICTION-02)**" in stage_table)
check("ENGINE_STAGE has 8 entries (Orchestration absent)",
      len(ENGINE_STAGE) == 8 and Engine.ORCHESTRATION not in ENGINE_STAGE)
check("no engine is mapped to stage 8 [C-02 open]",
      8 not in ENGINE_STAGE.values())
check("ENGINE_STAGE agrees with CREATE_AUTHORITY",
      all(ENGINE_STAGE[e] == t.stage for t, e in CREATE_AUTHORITY.items()))

# --- 4. AC1 empirically ----------------------------------------------------
ACQ = (Engine.RESEARCH, Engine.FACT_EXTRACTION)
INTERP = (Engine.PROBLEM_INTELLIGENCE, Engine.PATTERN_INTELLIGENCE,
          Engine.OPPORTUNITY_INTELLIGENCE, Engine.SOLUTION_INTELLIGENCE,
          Engine.VALIDATION, Engine.FEEDBACK)

state = {"acq": 0, "ser": 0, "bad": 0, "max_ser": 0, "max_acq": 0,
         "same": 0, "per": {}}
lock = threading.Lock()


def tracker(item):
    with lock:
        per = state["per"]
        per[item.engine] = per.get(item.engine, 0) + 1
        if per[item.engine] > 1 and item.engine in INTERP:
            state["same"] += 1
        key = "acq" if item.engine in ACQ else "ser"
        state[key] += 1
        state["max_" + key] = max(state["max_" + key], state[key])
        if state["ser"] and state["acq"]:
            state["bad"] += 1
    time.sleep(0.004)
    with lock:
        state["per"][item.engine] -= 1
        state["acq" if item.engine in ACQ else "ser"] -= 1
    return orch.InvocationResult.empty()


mixed = orch.WorkSet(items=(
    wi(0), wi(1), wi(2, Engine.FACT_EXTRACTION), wi(3),
    wi(4, Engine.PROBLEM_INTELLIGENCE),
    wi(5), wi(6),
    wi(7, Engine.PATTERN_INTELLIGENCE),
    wi(8, Engine.PROBLEM_INTELLIGENCE),
))
record = orch.Orchestrator(invoker=tracker, max_workers=4).run_cycle(mixed)
check("AC1: never two serialised invocations in flight",
      state["max_ser"] <= 1, f"max={state['max_ser']}")
check("AC2: acquisition never overlapped interpretation",
      state["bad"] == 0, f"{state['bad']} overlaps")
check("AC3: no same-engine overlap among serialised stages",
      state["same"] == 0, f"{state['same']} overlaps")
check("concurrent half actually parallelises",
      state["max_acq"] > 1, f"max={state['max_acq']}")

boundary = orch.ConcurrencyBoundary(record)
check("verifier confirms AC1", boundary.interpretation_serialised)
check("verifier confirms AC2", boundary.population_stable)
check("verifier confirms AC3", boundary.branching_impossible)
check("verifier confirms all three", boundary.holds)

# --- 5. R-1 linkage --------------------------------------------------------
r1 = (DOCS / "decisions" / "R-01-immutable-versioned-objects.md").read_text()
check("R-1 ties non-branching to serialised interpretation under N-11",
      "interpretation is serialised under N-11" in r1)
check("IOM 2.2 prohibits concurrent versioning of one object",
      "Two engines cannot concurrently version the same object" in iom)

# --- 6. Determinism of the record [N-4] ------------------------------------
det_ws = orch.WorkSet(items=tuple(wi(n) for n in range(12)))
orders = set()
for _ in range(5):
    r = orch.Orchestrator(invoker=empty, max_workers=6).run_cycle(det_ws)
    orders.add(tuple(x.input_ids[0] for x in r.invocations))
check("recorded order deterministic across parallel runs", len(orders) == 1)
check("recorded order equals work-set order",
      orders.pop() == tuple(f"s-{n}" for n in range(12)))

seq = orch.Orchestrator(invoker=empty, max_workers=1).run_cycle(mixed)
par = orch.Orchestrator(invoker=empty, max_workers=6).run_cycle(mixed)
check("parallel record matches sequential record",
      [x.input_ids for x in par.invocations] == [x.input_ids for x in seq.invocations]
      and par.attempted_count == seq.attempted_count
      and par.outcome is seq.outcome)

# --- 7. Bounds preserved [N-17] --------------------------------------------
bounded_ws = orch.WorkSet(items=tuple(wi(n) for n in range(12)))
identical = True
for limit in range(1, 14):
    b = orch.CycleBounds(max_work_items=limit)
    a = orch.Orchestrator(invoker=empty, max_workers=1, bounds=b).run_cycle(bounded_ws)
    c = orch.Orchestrator(invoker=empty, max_workers=4, bounds=b).run_cycle(bounded_ws)
    if (a.attempted_count, a.not_attempted_count, a.outcome) != \
       (c.attempted_count, c.not_attempted_count, c.outcome):
        identical = False
check("bounds identical sequential vs parallel at every limit", identical)

# --- 8. No invented policy -------------------------------------------------
check("M-56 surfaced: no CPU-derived worker default",
      not any(t in src for t in ("cpu_count", "os.cpu", "multiprocessing")))
check("default max_workers is 1",
      inspect.signature(orch.Orchestrator).parameters["max_workers"].default == 1)
check("M-56 cited in the module", "M-56" in src)
BANNED = ("queue_bound", "backpressure", "throttle", "rebalance", "priority",
          "reorder", "retry", "skip")
for cls in (orch.WorkSet, orch.Orchestrator, orch.ConcurrencyBoundary):
    names = [n for n in dir(cls) if not n.startswith("_")]
    check(f"{cls.__name__} invents no scheduling/policy vocabulary",
          not [n for n in names if any(b in n.lower() for b in BANNED)], str(names))
check("OQ-14 respected: no graph partitioning or sharding",
      not any(t in src.lower() for t in ("graph partition", "shard",
                                         "partitioned graph")))

# --- 9. Control layer only -------------------------------------------------
OBJECT_MODULES = ["evidence", "fact", "problem", "pattern", "opportunity",
                  "solution", "validation", "execution", "feedback", "store",
                  "graph", "lineage", "claim", "semantic", "relationships",
                  "identity", "integrity", "lifecycle", "cascade", "support"]
imports = {n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.module}
check("orchestration imports no Intelligence Object module",
      not [m for m in OBJECT_MODULES if f"oip.{m}" in imports],
      str(sorted(i for i in imports if i.startswith("oip."))))
check("orchestration produces no Intelligence Objects",
      orch.Orchestrator(invoker=empty).produces_intelligence_objects is False)
check("ConcurrencyBoundary never participates in lineage",
      orch.ConcurrencyBoundary(record).participates_in_lineage is False)
check("ConcurrencyBoundary is frozen",
      any(isinstance(n, ast.ClassDef) and n.name == "ConcurrencyBoundary"
          and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
          for n in ast.walk(tree)))
check("ConcurrencyBoundary holds only a cycle",
      {f.name for f in dataclasses.fields(orch.ConcurrencyBoundary)} == {"cycle"})
check("ExecutionPhase is frozen",
      any(isinstance(n, ast.ClassDef) and n.name == "ExecutionPhase"
          and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
          for n in ast.walk(tree)))

# --- 10. Fail closed -------------------------------------------------------
try:
    wi(1, Engine.ORCHESTRATION).concurrency_class
    check("unclassifiable engine fails closed", False)
except orch.ConcurrencyError:
    check("unclassifiable engine fails closed", True)
for bad in (0, -1, True, 1.5, "4"):
    try:
        orch.Orchestrator(invoker=empty, max_workers=bad).run_cycle(
            orch.WorkSet(items=(wi(0),)))
        check(f"max_workers={bad!r} refused", False)
        break
    except orch.ConcurrencyError:
        pass
else:
    check("invalid max_workers values all refused", True)
check("stage 8 classified as serialised by object type",
      wi(1, Engine.FEEDBACK, produces=ObjectType.EXECUTION_RECORD).is_serialised)

# --- 11. Backward compatibility -------------------------------------------
PRIOR = ["CycleBounds", "WorkItem", "WorkSet", "InvocationResult",
         "EngineInvoker", "InvocationRecord", "CycleRecord", "Orchestrator",
         "CycleOutcome", "InvocationOutcome", "OrchestrationError",
         "CycleBoundError", "WorkSetError", "InvocationError",
         "CycleStateError", "KnowledgeMutationError", "ProcessingRecord",
         "ProcessingStateStore", "ProcessingStateError",
         "ProcessingIsolationError", "FailureSurface", "FailureMaskedError",
         "DEFAULT_MAX_WORK_ITEMS", "DEFAULT_WALL_CLOCK_BUDGET_SECONDS"]
check("every prior public name still exists",
      all(hasattr(orch, n) for n in PRIOR),
      str([n for n in PRIOR if not hasattr(orch, n)]))
params = list(inspect.signature(orch.Orchestrator).parameters)
check("prior Orchestrator field order unchanged",
      params[:5] == ["invoker", "bounds", "failure_store",
                     "processing_store", "clock"], str(params))
check("max_workers appended after the pre-T01.6.4 fields",
      params.index("max_workers") == 5, str(params))

# --- 12. Module header -----------------------------------------------------
header = src.split('"""')[1]
check("header names Task: T01.6.4", "Task: T01.6.4" in header)
for marker in ("N-11", "N-17", "AD-04", "M-56"):
    check(f"header cites {marker}", marker in header)

failed = [(n, d) for n, ok, d in CHECKS if not ok]
for name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
