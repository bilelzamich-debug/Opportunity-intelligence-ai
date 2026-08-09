"""Mechanical architecture verification for T01.6.5.

Checks properties against the ratified documents by extraction.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip import orchestration as orch  # noqa: E402
from oip.enums import (  # noqa: E402
    ENGINE_INPUT_TYPE, ENGINE_STAGE, ROOT_ENGINES, Engine, ObjectStatus,
    ObjectType,
)

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))


src = (ROOT / "oip" / "orchestration.py").read_text()
tree = ast.parse(src)


class Resolver:
    def __init__(self, mapping=None):
        self.map = dict(mapping or {})

    def resolve_type(self, object_id):
        return self.map.get(object_id)


def wi(engine, inputs=("x",)):
    return orch.WorkItem(engine, tuple(inputs), "cfg")


def empty(_i):
    return orch.InvocationResult.empty()


# --- 1. Acceptance criteria quoted from the ratified backlog --------------
backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
task = backlog.split("#### `T01.6.5`")[1].split("### Feature F01.7")[0]
criteria = re.findall(r"^- (.+)$", task, re.M)
check("backlog states exactly 2 acceptance criteria", len(criteria) == 2, str(criteria))
check("AC1 is pipeline order never violated",
      any("Pipeline order never violated" in c for c in criteria))
check("AC2 is out-of-order invocation rejected",
      any("Out-of-order invocation rejected" in c for c in criteria))
check("task sentence is about INPUT EXISTENCE",
      "an engine cannot run before its inputs exist" in task)
check("backlog: depends on T01.6.1", "`T01.6.1`" in task)
check("backlog: blocks T01.8.1", "`T01.8.1`" in task)

# --- 2. v2 4.12 grants the responsibility and the Store read --------------
v2 = (DOCS / "PKP_v2_Master_Reference.md").read_text()
orch_section = v2.split("### 4.12 Orchestration Engine")[1].split("### 4.13")[0]
check("v2 4.12 makes Orchestration enforce stage ordering",
      "enforce stage ordering" in orch_section)
check("v2 4.12 names the stage-order violation failure mode",
      "Stage-order violation" in orch_section)
check("v2 4.12 grants existence-and-status as Orchestration's input",
      "the existence and status of objects awaiting processing" in orch_section)
check("v2 4.12 names the Knowledge Store as the state dependency",
      "Knowledge Store (to determine state)" in orch_section)
check("v2 4.12 forbids creating/modifying objects",
      "Does NOT create or modify Intelligence Objects" in orch_section)
check("v2 5.5 grants Orchestration read-state-only",
      "| Orchestration | Read state only | Read state only | — |" in v2)

# --- 3. N-14's direct-input table reproduced exactly ----------------------
n14 = (DOCS / "decisions" / "N-14-cross-stage-read-access.md").read_text()
check("N-14 is RATIFIED", "| **Status** | `RATIFIED` |" in n14)
table = n14.split("| Engine | Direct input | Additionally readable |")[1]
for engine_name, input_name in [
    ("Fact Extraction", "Evidence"), ("Problem Intelligence", "Facts"),
    ("Pattern Intelligence", "Problems"), ("Opportunity Intelligence", "Patterns"),
    ("Solution Intelligence", "Opportunities"), ("Validation", "Solutions"),
    ("Feedback", "Execution Records"),
]:
    check(f"N-14 gives {engine_name} the direct input {input_name}",
          re.search(rf"\| {re.escape(engine_name)} \| {re.escape(input_name)} \|",
                    table) is not None)
check("implementation maps exactly seven consuming engines",
      len(ENGINE_INPUT_TYPE) == 7, str(len(ENGINE_INPUT_TYPE)))
check("implementation matches N-14 exactly",
      ENGINE_INPUT_TYPE == {
          Engine.FACT_EXTRACTION: ObjectType.EVIDENCE,
          Engine.PROBLEM_INTELLIGENCE: ObjectType.FACT,
          Engine.PATTERN_INTELLIGENCE: ObjectType.PROBLEM,
          Engine.OPPORTUNITY_INTELLIGENCE: ObjectType.PATTERN,
          Engine.SOLUTION_INTELLIGENCE: ObjectType.OPPORTUNITY,
          Engine.VALIDATION: ObjectType.SOLUTION,
          Engine.FEEDBACK: ObjectType.EXECUTION_RECORD,
      })
check("Research is the only root engine [E-V1]",
      ROOT_ENGINES == frozenset({Engine.RESEARCH})
      and Engine.RESEARCH not in ENGINE_INPUT_TYPE)
check("Orchestration consumes nothing",
      Engine.ORCHESTRATION not in ENGINE_INPUT_TYPE
      and Engine.ORCHESTRATION not in ROOT_ENGINES)
check("each input type is the previous stage [IOM 2.6]",
      all(t.stage == ENGINE_STAGE[e] - 1 for e, t in ENGINE_INPUT_TYPE.items()))
check("every pipeline engine is classified",
      set(ENGINE_INPUT_TYPE) | ROOT_ENGINES == set(ENGINE_STAGE))

# --- 4. AC2 empirically ----------------------------------------------------
guard = orch.SequencingGuard(Resolver())
check("absent input is rejected",
      guard.check(wi(Engine.FACT_EXTRACTION, ("EV-1",))).satisfied is False)
check("present input of the right type is accepted",
      orch.SequencingGuard(Resolver({"EV-1": ObjectType.EVIDENCE}))
      .check(wi(Engine.FACT_EXTRACTION, ("EV-1",))).satisfied is True)
check("wrong-type input is rejected [N-14]",
      orch.SequencingGuard(Resolver({"PR": ObjectType.PROBLEM}))
      .check(wi(Engine.FACT_EXTRACTION, ("PR",))).satisfied is False)
check("Research needs no inputs",
      guard.check(wi(Engine.RESEARCH, ("anything",))).satisfied is True)
wrong = [
    (e.value, t.value)
    for e in ENGINE_INPUT_TYPE for t in ObjectType
    if orch.SequencingGuard(Resolver({"in": t})).check(wi(e, ("in",))).satisfied
    != (t is ENGINE_INPUT_TYPE[e])
]
check("full engine x type matrix matches N-14", not wrong, str(wrong))

ran: list[int] = []
o = orch.Orchestrator(
    invoker=lambda i: (ran.append(1), empty(i))[1], state_resolver=Resolver()
)
rec = o.run_cycle(orch.WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("m",)),)))
check("AC2: an unready engine is never invoked", ran == [])
check("AC2: the rejection is recorded",
      rec.invocations[0].outcome is orch.InvocationOutcome.REJECTED_OUT_OF_ORDER)
check("rejection is visible on the cycle",
      rec.rejected_count == 1 and rec.had_sequencing_violation is True)

# --- 5. AC1: no execution path bypasses the guard -------------------------
for workers in (1, 4, 8):
    ran2: list[int] = []
    orch.Orchestrator(
        invoker=lambda i: (ran2.append(1), empty(i))[1],
        max_workers=workers, state_resolver=Resolver(),
    ).run_cycle(orch.WorkSet(items=tuple(
        wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(8)
    )))
    check(f"AC1: guard not bypassed at max_workers={workers}", ran2 == [])

# --- 6. Open questions NOT closed -----------------------------------------
res = Resolver({"PT": ObjectType.PATTERN, "SO": ObjectType.SOLUTION,
                "EV": ObjectType.EVIDENCE})
g = orch.SequencingGuard(res)
check("OQ-10 not closed: a stage-skipping set is not rejected",
      g.violations(orch.WorkSet(items=(
          wi(Engine.OPPORTUNITY_INTELLIGENCE, ("PT",)),))) == ())
check("OQ-11 not closed: reverse order is not rejected",
      g.violations(orch.WorkSet(items=(
          wi(Engine.VALIDATION, ("SO",)),
          wi(Engine.FACT_EXTRACTION, ("EV",))))) == ())
check("OQ-10 surfaced as OPEN in the module", "OQ-10" in src)
check("OQ-11 surfaced as OPEN in the module", "OQ-11" in src)
BANNED = ("skip", "backflow", "reverse", "reorder", "sort", "infer",
          "insert", "synthes", "retry", "defer")
names = [n for n in dir(orch.SequencingGuard) if not n.startswith("_")]
check("guard invents no ordering or policy vocabulary",
      not [n for n in names if any(b in n.lower() for b in BANNED)], str(names))

# --- 7. Status reported, never required [A1] ------------------------------
class StatusResolver(Resolver):
    def find(self, object_id):
        return type("S", (), {"status": ObjectStatus.RETRACTED})()

sc = orch.SequencingGuard(StatusResolver({"EV": ObjectType.EVIDENCE})).check(
    wi(Engine.FACT_EXTRACTION, ("EV",)))
check("a non-ACTIVE input still satisfies existence", sc.satisfied is True)
check("status is reported for the caller",
      sc.input_statuses == (("EV", ObjectStatus.RETRACTED),))

# --- 8. Rejection is not a failure and not processing ---------------------
from oip.configuration import FailureStore  # noqa: E402

fs = FailureStore()
ps = orch.ProcessingStateStore()
r2 = orch.Orchestrator(
    invoker=empty, failure_store=fs, processing_store=ps,
    state_resolver=Resolver(),
).run_cycle(orch.WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("m",)),)))
check("a rejection creates no failure record [N-10]", len(fs) == 0)
check("a rejection is not counted as a failure", r2.failed_count == 0)
check("a rejection is not recorded as processing [T01.6.2]", len(ps) == 0)
check("a rejection is not 'attempted'", r2.invocations[0].attempted is False)
check("a rejection alone does not fail the cycle",
      r2.outcome is orch.CycleOutcome.COMPLETED and r2.had_failure is False)
check("a rejection never participates in lineage",
      r2.invocations[0].participates_in_lineage is False)

# --- 9. Control layer only ------------------------------------------------
OBJECT_MODULES = ["evidence", "fact", "problem", "pattern", "opportunity",
                  "solution", "validation", "execution", "feedback", "store",
                  "graph", "lineage", "claim", "semantic", "relationships",
                  "identity", "integrity", "lifecycle", "cascade", "support"]
imports = {n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.module}
check("orchestration imports no Intelligence Object module",
      not [m for m in OBJECT_MODULES if f"oip.{m}" in imports],
      str(sorted(i for i in imports if i.startswith("oip."))))
check("guard is frozen",
      any(isinstance(n, ast.ClassDef) and n.name == "SequencingGuard"
          and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
          for n in ast.walk(tree)))
check("guard holds only a resolver",
      {f.name for f in dataclasses.fields(orch.SequencingGuard)} == {"resolver"})
check("guard is not lineage",
      orch.SequencingGuard(Resolver()).participates_in_lineage is False)
check("StateResolver protocol exposes only resolve_type",
      [n for n in dir(orch.StateResolver)
       if not n.startswith("_")] == ["resolve_type"])
check("orchestration produces no Intelligence Objects",
      orch.Orchestrator(invoker=empty).produces_intelligence_objects is False)

# --- 10. Fail closed -------------------------------------------------------
try:
    orch.SequencingGuard(object())
    check("resolver lacking resolve_type refused", False)
except orch.SequencingError:
    check("resolver lacking resolve_type refused", True)
try:
    orch.SequencingGuard(Resolver()).check(wi(Engine.ORCHESTRATION))
    check("unmapped engine fails closed", False)
except orch.SequencingError:
    check("unmapped engine fails closed", True)


class Hostile:
    def resolve_type(self, object_id):
        raise RuntimeError("down")


ran3: list[int] = []
o3 = orch.Orchestrator(
    invoker=lambda i: (ran3.append(1), empty(i))[1], state_resolver=Hostile()
)
r3 = o3.run_cycle(orch.WorkSet(items=(wi(Engine.FACT_EXTRACTION, ("a",)),)))
check("a resolver fault fails CLOSED (engine not run)", ran3 == [])
check("a resolver fault does not lose the cycle", o3.cycle_count == 1)
check("a resolver fault is not blamed on an engine", r3.failed_count == 0)

# --- 11. N-11 / N-17 preserved --------------------------------------------
res2 = Resolver({f"EV{n}": ObjectType.EVIDENCE for n in range(4)}
                | {"PR": ObjectType.PROBLEM})
r4 = orch.Orchestrator(
    invoker=empty, max_workers=4, state_resolver=res2
).run_cycle(orch.WorkSet(items=tuple(
    [wi(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(2)]
    + [wi(Engine.PATTERN_INTELLIGENCE, ("PR",))]
    + [wi(Engine.FACT_EXTRACTION, (f"EV{n}",)) for n in range(2, 4)]
)))
orch.ConcurrencyBoundary(r4).assert_holds()
check("N-11 barrier still holds with sequencing active", True)
r5 = orch.Orchestrator(
    invoker=empty, state_resolver=Resolver(),
    bounds=orch.CycleBounds(max_work_items=3),
).run_cycle(orch.WorkSet(items=tuple(
    wi(Engine.FACT_EXTRACTION, (f"m{n}",)) for n in range(10))))
check("N-17 bounds still enforced", r5.rejected_count == 3
      and r5.outcome is orch.CycleOutcome.WORK_LIMIT_REACHED)

# --- 12. Determinism -------------------------------------------------------
res3 = Resolver({"EV": ObjectType.EVIDENCE})
ws = orch.WorkSet(items=tuple(
    [wi(Engine.FACT_EXTRACTION, ("EV",)), wi(Engine.FACT_EXTRACTION, ("X",))] * 5))
shapes = {
    tuple(x.outcome for x in orch.Orchestrator(
        invoker=empty, max_workers=w, state_resolver=res3).run_cycle(ws).invocations)
    for w in (1, 2, 4, 6)
}
check("verdicts identical across worker counts", len(shapes) == 1)

# --- 13. Backward compatibility -------------------------------------------
PRIOR = ["CycleBounds", "WorkItem", "WorkSet", "InvocationResult",
         "EngineInvoker", "InvocationRecord", "CycleRecord", "Orchestrator",
         "CycleOutcome", "InvocationOutcome", "OrchestrationError",
         "ProcessingStateStore", "FailureSurface", "FailureMaskedError",
         "ConcurrencyBoundary", "ConcurrencyClass", "ConcurrencyViolation",
         "ExecutionPhase", "DEFAULT_MAX_WORK_ITEMS"]
check("every prior public name still exists",
      all(hasattr(orch, n) for n in PRIOR),
      str([n for n in PRIOR if not hasattr(orch, n)]))
params = list(inspect.signature(orch.Orchestrator).parameters)
check("prior field order unchanged",
      params[:5] == ["invoker", "bounds", "failure_store",
                     "processing_store", "clock"], str(params))
check("state_resolver appended last and defaults to None",
      params[-1] == "state_resolver"
      and inspect.signature(orch.Orchestrator)
      .parameters["state_resolver"].default is None)
check("InvocationOutcome gained exactly one member",
      len(list(orch.InvocationOutcome)) == 5)
r6 = orch.Orchestrator(invoker=empty).run_cycle(
    orch.WorkSet(items=(wi(Engine.PATTERN_INTELLIGENCE, ("nope",)),)))
check("no resolver = unchanged behaviour",
      r6.attempted_count == 1 and r6.rejected_count == 0)

# --- 14. Module header -----------------------------------------------------
header = src.split('"""')[1]
check("header names Task: T01.6.5", "Task: T01.6.5" in header)
for marker in ("N-14", "v2 4.12", "N-6", "OQ-10", "OQ-11", "AD-04"):
    check(f"header cites {marker}", marker in header)

failed = [(n, d) for n, ok, d in CHECKS if not ok]
for name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
