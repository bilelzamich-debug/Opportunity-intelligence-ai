"""Mechanical architecture verification for T01.6.3.

Checks properties against the ratified documents by extraction.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip import orchestration as orch  # noqa: E402
from oip.acceptance import FailureRecord, RuleOutcome, RuleResult  # noqa: E402
from oip.configuration import FailureStore  # noqa: E402
from oip.enums import Engine, ObjectType  # noqa: E402

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))


src = (ROOT / "oip" / "orchestration.py").read_text()
tree = ast.parse(src)

# --- 1. Acceptance criteria quoted from the ratified backlog --------------
backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
task = backlog.split("#### `T01.6.3`")[1].split("#### `T01.6.4`")[0]
criteria = re.findall(r"^- (.+)$", task, re.M)
check("backlog states exactly 2 acceptance criteria", len(criteria) == 2, str(criteria))
check("AC1 is failed-vs-empty",
      any("Failed invocation distinguishable from empty result" in c for c in criteria))
check("AC2 is no silent halt",
      any("Failures do not silently halt the pipeline" in c for c in criteria))
check("backlog: depends on T01.6.2 and T01.1.7",
      "`T01.6.2`" in task and "`T01.1.7`" in task)
check("backlog: blocks T09.1.2", "`T09.1.2`" in task)
check("task statement says never masked as completion",
      "never masked as completion" in task)

# --- 2. N-10's six identifications ----------------------------------------
n10 = (DOCS / "decisions" / "N-10-failure-representation.md").read_text()
sentence = [l for l in n10.splitlines() if "Every failure record identifies" in l]
check("N-10 states the six identifications", len(sentence) == 1)
required = ("the engine", "the invocation", "the inputs attempted",
            "the configuration in force", "the time", "the nature")
check("all six identifications quoted from N-10",
      all(r in sentence[0] for r in required), sentence[0] if sentence else "")

fields = {f.name for f in dataclasses.fields(FailureRecord)}
check("FailureRecord carries engine", "engine" in fields)
check("FailureRecord carries the invocation (cycle + index)",
      {"cycle_id", "invocation_index"} <= fields)
check("FailureRecord carries inputs attempted", "input_ids" in fields)
check("FailureRecord carries configuration", "engine_configuration_ref" in fields)
check("FailureRecord carries the time", "recorded_at" in fields)
check("FailureRecord carries the nature", "failed_rules" in fields)

# an orchestrated failure satisfies all six, empirically
store = FailureStore()
o = orch.Orchestrator(
    invoker=lambda i: (_ for _ in ()).throw(RuntimeError("boom")),
    failure_store=store,
)
o.run_cycle(orch.WorkSet(items=(orch.WorkItem(Engine.VALIDATION, ("a",), "cfg"),)))
rec = store.all()[0]
check("orchestrated failure satisfies N-10 attribution",
      rec.satisfies_n10_attribution is True)
check("attempted inputs recoverable from the record", rec.input_ids == ("a",))
check("engine recoverable as an Engine", rec.engine is Engine.VALIDATION)

# --- 3. AC1 mechanically ---------------------------------------------------
surface = orch.FailureSurface.over(o)
check("failed and empty are separate accessors",
      hasattr(surface, "failed_invocations") and hasattr(surface, "empty_invocations"))
check("a failure is not counted as empty",
      surface.failed_count == 1 and surface.empty_count == 0)
clean = orch.Orchestrator(invoker=lambda i: orch.InvocationResult.empty())
clean.run_cycle(orch.WorkSet(items=(orch.WorkItem(Engine.RESEARCH, ("a",), "c"),)))
cs = orch.FailureSurface.over(clean)
check("an empty result is not counted as a failure",
      cs.failed_count == 0 and cs.empty_count == 1)

# --- 4. AC2 mechanically ---------------------------------------------------
seen: list[str] = []


def flaky(item):
    seen.append(item.input_ids[0])
    raise RuntimeError("boom")


cont = orch.Orchestrator(invoker=flaky)
r = cont.run_cycle(orch.WorkSet(items=tuple(
    orch.WorkItem(Engine.RESEARCH, (f"s{n}",), "c") for n in range(5)
)))
check("every item attempted despite total failure", r.attempted_count == 5)
check("no work left unattempted after failures", r.not_attempted_count == 0)
check("failures never masked in real operation",
      orch.FailureSurface.over(cont).masked_cycles() == ())

# --- 5. No invented policy [M-36 policy half OPEN] ------------------------
BANNED_POLICY = ("retry", "skip", "compensate", "recover", "suppress",
                 "resume", "rollback")
public = [n for n in dir(orch.FailureSurface) if not n.startswith("_")]
check("no retry/skip/compensate/recover vocabulary on the surface",
      not [n for n in public if any(b in n.lower() for b in BANNED_POLICY)],
      str(public))
check("M-36 policy half surfaced as OPEN in the module", "M-36" in src)
check("module records the M-36 compound-marker conflict",
      "policy + representation" in src)

# --- 6. No observability [M-57 OPEN, T09.1.2] ------------------------------
BANNED_OBS = ("rate", "threshold", "alert", "metric", "sla", "healthy",
              "degraded", "dashboard")
check("no observability vocabulary on the surface",
      not [n for n in public if any(b in n.lower() for b in BANNED_OBS)],
      str(public))
check("M-57 surfaced as OPEN in the module", "M-57" in src)
summary = surface.summary()
check("summary reports integer counts only",
      all(isinstance(v, int) for v in summary.values()), str(summary))
check("summary contains no rate or percentage",
      not [k for k in summary if "rate" in k or "pct" in k])

# --- 7. No severity vocabulary ---------------------------------------------
BANNED_SEV = ("severity", "critical", "warning", "priority", "grade")
check("no severity grading",
      not [n for n in public if any(b in n.lower() for b in BANNED_SEV)])

# --- 8. Detection separate from policy: the surface is read-only ----------
check("FailureSurface is frozen",
      any(isinstance(n, ast.ClassDef) and n.name == "FailureSurface"
          and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
          for n in ast.walk(tree)))
check("FailureSurface holds only cycles",
      {f.name for f in dataclasses.fields(orch.FailureSurface)} == {"cycles"})
check("FailureSurface owns no store",
      "failure_store" not in src.split("class FailureSurface")[1]
      .split("class Orchestrator")[0])

# --- 9. Outside the object model ------------------------------------------
OBJECT_MODULES = [
    "evidence", "fact", "problem", "pattern", "opportunity", "solution",
    "validation", "execution", "feedback", "store", "graph", "lineage",
    "claim", "semantic", "relationships", "identity", "integrity",
    "lifecycle", "cascade", "support",
]
imports = {n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.module}
check("orchestration imports no Intelligence Object module",
      not [m for m in OBJECT_MODULES if f"oip.{m}" in imports],
      str(sorted(i for i in imports if i.startswith("oip."))))
check("surface never participates in lineage",
      orch.FailureSurface().participates_in_lineage is False)
check("surface is not intelligence",
      orch.FailureSurface().is_intelligence is False)
check("failure record never participates in lineage",
      FailureRecord("X", ObjectType.EVIDENCE,
                    (RuleResult("V1", RuleOutcome.FAIL, "d"),), T0,
                    "cfg").participates_in_lineage is False)

# --- 10. Backward compatibility --------------------------------------------
legacy = FailureRecord("EV-1", ObjectType.EVIDENCE,
                       (RuleResult("V1", RuleOutcome.FAIL, "d"),), T0, "cfg")
check("legacy 5-argument FailureRecord still constructs", legacy.engine is None)
check("legacy record honestly reports incomplete attribution",
      legacy.satisfies_n10_attribution is False)
PRIOR_API = [
    "CycleBounds", "WorkItem", "WorkSet", "InvocationResult", "EngineInvoker",
    "InvocationRecord", "CycleRecord", "Orchestrator", "CycleOutcome",
    "InvocationOutcome", "OrchestrationError", "CycleBoundError",
    "WorkSetError", "InvocationError", "CycleStateError",
    "KnowledgeMutationError", "ProcessingRecord", "ProcessingStateStore",
    "ProcessingStateError", "ProcessingIsolationError",
    "DEFAULT_MAX_WORK_ITEMS", "DEFAULT_WALL_CLOCK_BUDGET_SECONDS",
]
check("every prior public name still exists",
      all(hasattr(orch, n) for n in PRIOR_API),
      str([n for n in PRIOR_API if not hasattr(orch, n)]))
params = list(inspect.signature(orch.Orchestrator).parameters)
check("Orchestrator field order unchanged",
      params[:4] == ["invoker", "bounds", "failure_store", "processing_store"],
      str(params))

# --- 11. Surface separation [B-12] -----------------------------------------
check("failure store and processing store remain distinct types",
      orch.ProcessingStateStore is not FailureStore)
check("FailureSurface reads cycles, not a processing store",
      "ProcessingStateStore" not in
      src.split("class FailureSurface")[1].split("class Orchestrator")[0])

# --- 12. Module header conventions -----------------------------------------
header = src.split('"""')[1]
check("header names Task: T01.6.3", "Task: T01.6.3" in header)
for marker in ("N-10", "N-17", "N-8", "AD-04", "M-36", "M-57"):
    check(f"header cites {marker}", marker in header)

# --- 13. Control signals are not engine failures ---------------------------
check("KeyboardInterrupt/SystemExit excluded from failure capture",
      "except (KeyboardInterrupt, SystemExit):" in src)

failed = [(n, d) for n, ok, d in CHECKS if not ok]
for name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
