"""Mechanical architecture verification for T01.6.2.

Checks properties against the ratified documents by extraction, not
recollection.
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
from oip.enums import Engine  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))


src = (ROOT / "oip" / "orchestration.py").read_text()
tree = ast.parse(src)

# --- 1. Backlog acceptance criteria are quoted from the ratified source ----
backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
t01_6_2 = backlog.split("#### `T01.6.2`")[1].split("#### `T01.6.3`")[0]
criteria = re.findall(r"^- (.+)$", t01_6_2, re.M)
check("backlog states exactly 3 acceptance criteria", len(criteria) == 3, str(criteria))
check("AC1 is idempotence/reprocessing",
      any("Idempotence" in c and "reprocessing detectable" in c for c in criteria))
check("AC2 is state outside the object model",
      any("outside the object model" in c for c in criteria))
check("AC3 is metadata only, never content",
      any("metadata only, never content" in c for c in criteria))
check("backlog says T01.6.2 depends on T01.6.1", "`T01.6.1`" in t01_6_2)
check("backlog says T01.6.2 blocks T01.6.3 and T01.6.4",
      "`T01.6.3`" in t01_6_2 and "`T01.6.4`" in t01_6_2)

# --- 2. Outside the object model ------------------------------------------
OBJECT_MODULES = [
    "evidence", "fact", "problem", "pattern", "opportunity", "solution",
    "validation", "execution", "feedback", "store", "graph", "lineage",
    "claim", "semantic", "relationships", "identity", "integrity",
    "lifecycle", "cascade", "support",
]
imports = {
    n.module for n in ast.walk(tree)
    if isinstance(n, ast.ImportFrom) and n.module
}
check("module imports no Intelligence Object module",
      not [m for m in OBJECT_MODULES if f"oip.{m}" in imports],
      str(sorted(imports)))
check("module imports only acceptance, contract, enums",
      {i for i in imports if i.startswith("oip.")} ==
      {"oip.acceptance", "oip.contract", "oip.enums"},
      str(sorted(i for i in imports if i.startswith("oip."))))

# --- 3. Metadata only, never content --------------------------------------
fields = {f.name: f.type for f in dataclasses.fields(orch.ProcessingRecord)}
ALLOWED = {"int", "Engine", "tuple[str, ...]", "str", "InvocationOutcome", "datetime"}
check("every ProcessingRecord field is a metadata type",
      set(fields.values()) <= ALLOWED, str(fields))
check("ProcessingRecord records what / by which engine / when",
      {"input_ids", "engine", "started_at", "ended_at"} <= set(fields))
check("ProcessingRecord records the cycle [N-17]", "cycle_id" in fields)
check("ProcessingRecord records the configuration [N-4]",
      "engine_configuration_ref" in fields)
check("ProcessingRecord carries no Intelligence Object attribute",
      not ({"lineage_id", "derives_from", "explanation", "status",
            "effective_confidence", "evidence_reachable"} & set(fields)))

# --- 4. Isolation ----------------------------------------------------------
rec = orch.ProcessingRecord(
    1, Engine.RESEARCH, ("a",), "cfg", orch.InvocationOutcome.EMPTY, (),
    __import__("datetime").datetime(2026, 3, 1, tzinfo=__import__("datetime").timezone.utc),
    __import__("datetime").datetime(2026, 3, 1, tzinfo=__import__("datetime").timezone.utc),
)
check("record.is_intelligence is False", rec.is_intelligence is False)
check("record.participates_in_lineage is False", rec.participates_in_lineage is False)
store = orch.ProcessingStateStore()
check("store.is_intelligence is False", store.is_intelligence is False)
check("store.participates_in_lineage is False", store.participates_in_lineage is False)
for accessor in ("as_lineage_reference", "as_evidence", "confidence_contribution"):
    try:
        getattr(rec, accessor)()
        check(f"record.{accessor}() refused", False)
    except orch.ProcessingIsolationError:
        check(f"record.{accessor}() refused", True)

# --- 5. No invented policy (M-36, M-01 remain open) -----------------------
BANNED = ("retry", "skip", "halt", "compensate", "suppress", "defer",
          "should_run", "next_work", "backoff", "priority")
public = [n for n in dir(orch.ProcessingStateStore) if not n.startswith("_")]
check("store exposes no retry/skip/scheduling vocabulary [M-36, M-01 open]",
      not [n for n in public if any(b in n.lower() for b in BANNED)], str(public))
check("M-36 surfaced as OPEN in the module", "M-36" in src)
check("M-01 surfaced as OPEN in the module", "M-01" in src)
# T01.6.2 introduced no enum. Later ratified tasks legitimately did:
# ConcurrencyClass (T01.6.4, N-11's two classes). The invariant this check
# defends is that T01.6.2's OWN concepts added none.
check("T01.6.2 introduced no enum",
      "ProcessingClass" not in src and "ProcessingOutcome" not in src)

# --- 6. Ownership: Orchestration owns no storage --------------------------
sig = inspect.signature(orch.Orchestrator)
check("processing_store is supplied, defaulting to None [v2 4.12]",
      sig.parameters["processing_store"].default is None)
check("Orchestrator constructs no store",
      "ProcessingStateStore()" not in src.split("class Orchestrator")[1])
check("produces_intelligence_objects stays False",
      orch.Orchestrator(invoker=lambda i: None).produces_intelligence_objects is False)

# --- 7. Backward compatibility: T01.6.1 API unchanged ---------------------
T01_6_1_API = [
    "CycleBounds", "WorkItem", "WorkSet", "InvocationResult", "EngineInvoker",
    "InvocationRecord", "CycleRecord", "Orchestrator", "CycleOutcome",
    "InvocationOutcome", "OrchestrationError", "CycleBoundError",
    "WorkSetError", "InvocationError", "CycleStateError",
    "KnowledgeMutationError", "DEFAULT_MAX_WORK_ITEMS",
    "DEFAULT_WALL_CLOCK_BUDGET_SECONDS",
]
check("every T01.6.1 public name still exists",
      all(hasattr(orch, n) for n in T01_6_1_API),
      str([n for n in T01_6_1_API if not hasattr(orch, n)]))
params = list(inspect.signature(orch.Orchestrator).parameters)
check("pre-existing Orchestrator fields keep their order",
      params[:3] == ["invoker", "bounds", "failure_store"], str(params))

# --- 8. N-10: empty vs failed stay distinguishable ------------------------
# 4 as of T01.6.2; T01.6.5 added REJECTED_OUT_OF_ORDER by ratified need.
# T01.6.2's invariant is that EMPTY and FAILED stay distinct outcomes.
check("EMPTY and FAILED remain distinct outcomes [N-10]",
      orch.InvocationOutcome.EMPTY is not orch.InvocationOutcome.FAILED)
check("record exposes failed and produced_nothing separately",
      hasattr(rec, "failed") and hasattr(rec, "produced_nothing"))
check("NOT_ATTEMPTED refused by ProcessingRecord",
      "NOT_ATTEMPTED" in src.split("class ProcessingRecord")[1].split("class ProcessingStateStore")[0])

# --- 9. Module header conventions ------------------------------------------
header = src.split('"""')[1]
check("header names Task: T01.6.2", "Task: T01.6.2" in header)
check("header has an Architecture References list",
      "Architecture References:" in header)
for marker in ("N-17", "N-10", "AD-04", "CI-1", "N-4", "N-11", "IOM 2.5"):
    check(f"header cites {marker}", marker in header)

# --- 10. Open markers not resolved -----------------------------------------
check("N-12 retention gap surfaced rather than filled",
      "retention" in src.lower() and "N-12" in src)
check("no eviction implemented",
      not re.search(r"def (evict|prune|expire|trim)", src))

failed = [(n, d) for n, ok, d in CHECKS if not ok]
for name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
