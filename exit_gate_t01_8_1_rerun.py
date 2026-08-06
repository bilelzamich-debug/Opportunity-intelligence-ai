"""Phase 1 Exit Gate -- T01.8.1 RE-RUN. Fresh verification from first principles.

Evaluates the 18 ratified Definition-of-Done criteria (P1-EXECUTION-PLAN §6)
and the 4 backlog acceptance criteria for T01.8.1, plus the architectural
validations the gate requires. Nothing is assumed from the previous run.

Fails closed: any check that cannot be performed counts as a failure.
"""
from __future__ import annotations

import ast
import dataclasses
import inspect
import re
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.acceptance import FailureRecord  # noqa: E402
from oip.calibration import (  # noqa: E402
    CALIBRATION_RUBRIC, assess_assertion, compare_across_engines,
)
from oip.cascade import CASCADE_TRIGGERS, CascadeInvalidation  # noqa: E402
from oip.configuration import ConfigurationStore, FailureStore  # noqa: E402
from oip.contract import Confidence, UniversalAttributes  # noqa: E402
from oip.enums import (  # noqa: E402
    CREATE_AUTHORITY, ENGINE_INPUT_TYPE, ENGINE_STAGE, ConfidenceBand, Engine,
    ObjectStatus, ObjectType, RelationshipType,
)
from oip.identity import IdentityAllocator  # noqa: E402
from oip.integrity import IntegrityVerifier  # noqa: E402
from oip.lifecycle import can_transition, permitted_transitions  # noqa: E402
from oip.orchestration import (  # noqa: E402
    ConcurrencyBoundary, CycleBounds, FailureSurface, InvocationOutcome,
    InvocationResult, Orchestrator, ProcessingStateStore, SequencingGuard,
    WorkItem, WorkSet,
)
from oip.retention import RetentionPolicy  # noqa: E402
from oip.store import KnowledgeStore, ReachabilityError  # noqa: E402
from conftest import (  # noqa: E402
    build_attrs, build_lineage, write_chain, write_derived, write_evidence,
)

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, condition: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(condition), detail))


def fresh():
    return KnowledgeStore(), IdentityAllocator()


ALL_TYPES = list(ObjectType)

# ===========================================================================
# A. Definition of Done -- Functional (criteria 1-9)
# ===========================================================================

# DoD 1 -- all nine object types persist with the 17 universal attributes
store, alloc = fresh()
persisted = {}
chain = write_chain(store, alloc)
for otype, stored in chain.items():
    persisted[otype] = stored
# ExecutionRecord and FeedbackRecord are not in write_chain (C-02 blocks XR)
try:
    from test_execution import force_persist as _xr_force
    _has_xr_helper = True
except Exception:
    _has_xr_helper = False

check("A", "DoD1: write_chain persists 7 types through Validation",
      len(persisted) == 7, str(sorted(t.value for t in persisted)))

# All nine types must be *persistable*. Types 8 and 9 are exercised by their
# own suites; verify the store exposes a write path for each of the nine.
write_paths = {
    ObjectType.EVIDENCE: "write_evidence",
    ObjectType.FACT: "write_fact",
    ObjectType.PROBLEM: "write_problem",
    ObjectType.PATTERN: "write_pattern",
    ObjectType.OPPORTUNITY: "write_opportunity",
    ObjectType.SOLUTION: "write_solution",
    ObjectType.VALIDATION: "write_validation",
    ObjectType.EXECUTION_RECORD: "write_execution_record",
    ObjectType.FEEDBACK_RECORD: "write_feedback_record",
}
check("A", "DoD1: a write path exists for all nine object types",
      all(hasattr(KnowledgeStore, m) for m in write_paths.values()),
      str([m for m in write_paths.values() if not hasattr(KnowledgeStore, m)]))
check("A", "DoD1: nine object types exist", len(ALL_TYPES) == 9)

# IOM 1.1's 17 required attributes, resolved through the composed contract:
# identity supplies object_id/version/lineage_id; confidence supplies the
# three confidence components.
sample = persisted[ObjectType.PROBLEM].attributes


def _resolve(attr: str):
    if hasattr(sample, attr):
        return getattr(sample, attr)
    if hasattr(sample.confidence, attr):
        return getattr(sample.confidence, attr)
    raise AttributeError(attr)


required_17 = [
    "object_id", "object_type", "version", "lineage_id", "produced_by_engine",
    "produced_at", "engine_configuration_ref", "derives_from", "explanation",
    "evidence_reachable", "evidential_support", "assertion_confidence",
    "effective_confidence", "asserted_at", "observed_at", "status",
    "status_reason",
]
missing_attrs = []
for _a in required_17:
    try:
        _resolve(_a)
    except AttributeError:
        missing_attrs.append(_a)
check("A", "DoD1: all 17 universal required attributes present",
      not missing_attrs, str(missing_attrs))

# DoD 2 -- no object accepted without resolvable lineage to Evidence
store2, alloc2 = fresh()
ident = alloc2.new_object()
orphan = build_attrs(ident, ObjectType.FACT, ())   # no upstream
try:
    store2.write(orphan, build_lineage(ident.object_id, ObjectType.FACT))
    check("A", "DoD2: lineage-less non-Evidence write rejected", False,
          "orphan Fact was accepted")
except Exception:
    check("A", "DoD2: lineage-less non-Evidence write rejected", True)

ev_only = write_evidence(store2, alloc2)
check("A", "DoD2: Evidence is the only permitted root",
      ev_only.object_type.is_root)
check("A", "DoD2: every persisted non-Evidence reaches Evidence",
      all(store.graph.reaches_evidence(s.object_id)
          for t, s in persisted.items() if t is not ObjectType.EVIDENCE))

# DoD 3 -- lineage traversable both directions, termination guaranteed
top = persisted[ObjectType.VALIDATION].object_id
root = persisted[ObjectType.EVIDENCE].object_id
check("A", "DoD3: backward traversal reaches the root",
      root in store.graph.ancestors(top))
check("A", "DoD3: forward traversal reaches the leaf",
      top in store.graph.descendants(root))
check("A", "DoD3: traversal terminates (depth bounded)",
      store.graph.depth_to_evidence(top) is not None)
check("A", "DoD3: path to Evidence resolves",
      store.graph.path_to_evidence(top) is not None)

# DoD 4 -- graph rebuild demonstrated
rebuilt = store.rebuild_graph()
check("A", "DoD4: rebuild reproduces node count",
      rebuilt.node_count == store.graph.node_count)
check("A", "DoD4: rebuild reproduces edge count",
      rebuilt.edge_count == store.graph.edge_count)
check("A", "DoD4: rebuild reproduces ancestry",
      rebuilt.ancestors(top) == store.graph.ancestors(top))
check("A", "DoD4: store and graph do not diverge",
      store.graph_diverges() == ())

# DoD 5 -- seven-state lifecycle with per-type reachability
check("A", "DoD5: exactly seven lifecycle states",
      len(list(ObjectStatus)) == 7)
check("A", "DoD5: Evidence cannot reach INVALIDATED [E-V1]",
      ObjectStatus.INVALIDATED not in
      permitted_transitions(ObjectType.EVIDENCE, ObjectStatus.ACTIVE))
check("A", "DoD5: Fact can reach INVALIDATED",
      ObjectStatus.INVALIDATED in
      permitted_transitions(ObjectType.FACT, ObjectStatus.ACTIVE))
check("A", "DoD5: every terminal state permits nothing",
      all(permitted_transitions(ObjectType.FACT, s) == frozenset()
          for s in ObjectStatus if s.is_terminal))

# DoD 6 -- cascade invalidation terminates and is idempotent
store6, alloc6 = fresh()
ev6 = write_evidence(store6, alloc6)
fa6 = write_derived(store6, alloc6, ObjectType.FACT, [ev6])
pr6 = write_derived(store6, alloc6, ObjectType.PROBLEM, [fa6])
casc = CascadeInvalidation(store=store6)
r1 = casc.retract(ev6.object_id, "withdrawn")
after_first = (store6.get(fa6.object_id).status,
               store6.get(pr6.object_id).status)
r2 = casc.cascade(ev6.object_id)
after_second = (store6.get(fa6.object_id).status,
                store6.get(pr6.object_id).status)
check("A", "DoD6: cascade completes (terminates)", r1.completed)
check("A", "DoD6: cascade invalidated the dependents",
      after_first == (ObjectStatus.INVALIDATED, ObjectStatus.INVALIDATED))
check("A", "DoD6: cascade is idempotent",
      after_second == after_first and r2.changed == 0)

# DoD 7 -- confidence ceiling enforced; IOM 4.4 example reproduced
try:
    Confidence(0.5, 0.5, 0.9)
    check("A", "DoD7: own-ceiling enforced", False, "0.9 > min(0.5,0.5)")
except Exception:
    check("A", "DoD7: own-ceiling enforced", True)

# IOM 2.3 worked ceiling illustration: Fact 0.55 -> Problem capped to 0.55
store7, alloc7 = fresh()
ev7 = write_evidence(store7, alloc7)
fa7 = write_derived(store7, alloc7, ObjectType.FACT, [ev7],
                    support=0.55, assertion=0.55)
fact_eff = store7.get(fa7.object_id).attributes.confidence.effective_confidence
check("A", "DoD7: IOM 2.3 worked example -- Fact effective is 0.55",
      abs(fact_eff - 0.55) < 1e-9, str(fact_eff))

# IOM 2.3: "Fact effective_confidence 0.55 -> Problem asserted at 0.80 is
# capped to 0.55 ... The opportunity presents at MODERATE, not VERY_STRONG."
capped = write_derived(store7, alloc7, ObjectType.PROBLEM, [fa7],
                       support=0.80, assertion=0.80)
capped_conf = store7.get(capped.object_id).attributes.confidence
check("A", "DoD7: a child asserted at 0.80 is capped to the upstream 0.55",
      abs(capped_conf.effective_confidence - fact_eff) < 1e-9,
      str(capped_conf.effective_confidence))
check("A", "DoD7: the capped child presents at MODERATE, not VERY_STRONG",
      capped_conf.band is ConfidenceBand.MODERATE, capped_conf.band.value)

# And an object claiming MORE than its upstream must be refused outright.
try:
    i7 = alloc7.new_object()
    inflated = build_attrs(
        i7, ObjectType.PATTERN,
        ((capped.object_id, ObjectType.PROBLEM),),
        status=ObjectStatus.ACTIVE, status_reason=None,
        support=0.95, assertion=0.95, upstream_ceiling=0.95)
    store7.write(inflated, build_lineage(
        i7.object_id, ObjectType.PATTERN,
        ((capped.object_id, ObjectType.PROBLEM),)))
    check("A", "DoD7: an inflating child is rejected at acceptance [V5]", False,
          "0.95 accepted above upstream 0.55")
except Exception:
    check("A", "DoD7: an inflating child is rejected at acceptance [V5]", True)

# DoD 8 -- engines invocable in pipeline order; sequencing violations rejected
store8, alloc8 = fresh()
ev8 = write_evidence(store8, alloc8)
guard = SequencingGuard(store8)
ok_item = WorkItem(Engine.FACT_EXTRACTION, (ev8.object_id,), "cfg")
bad_item = WorkItem(Engine.FACT_EXTRACTION, ("EV-missing",), "cfg")
check("A", "DoD8: an engine with existing inputs may run",
      guard.check(ok_item).satisfied is True)
check("A", "DoD8: an engine without its inputs is rejected",
      guard.check(bad_item).satisfied is False)
ran: list[int] = []
orch8 = Orchestrator(
    invoker=lambda i: (ran.append(1), InvocationResult.empty())[1],
    state_resolver=store8)
rec8 = orch8.run_cycle(WorkSet(items=(bad_item,)))
check("A", "DoD8: an out-of-order invocation never executes", ran == [])
check("A", "DoD8: the rejection is recorded",
      rec8.rejected_count == 1
      and rec8.invocations[0].outcome
      is InvocationOutcome.REJECTED_OUT_OF_ORDER)

# DoD 9 -- failures distinguishable from empty results
def _boom(_i):
    raise RuntimeError("engine down")


fs9 = FailureStore()
orch9 = Orchestrator(invoker=_boom, failure_store=fs9)
orch9.run_cycle(WorkSet(items=(WorkItem(Engine.RESEARCH, ("s",), "cfg"),)))
orch9b = Orchestrator(invoker=lambda i: InvocationResult.empty())
orch9b.run_cycle(WorkSet(items=(WorkItem(Engine.RESEARCH, ("s",), "cfg"),)))
surf_f = FailureSurface.over(orch9)
surf_e = FailureSurface.over(orch9b)
check("A", "DoD9: a failure is counted as failed, not empty",
      surf_f.failed_count == 1 and surf_f.empty_count == 0)
check("A", "DoD9: an empty result is counted as empty, not failed",
      surf_e.empty_count == 1 and surf_e.failed_count == 0)
check("A", "DoD9: failure recorded outside the object model",
      len(fs9) == 1 and fs9.participates_in_lineage is False)
check("A", "DoD9: no failure is masked as completion",
      surf_f.masked_cycles() == ())

# ===========================================================================
# B. Definition of Done -- Contract (criteria 10-14)
# ===========================================================================

acc = KnowledgeStore().acceptance
rule_ids = list(acc.rule_ids)

# DoD 10 -- V1-V12 enforced at acceptance
check("B", "DoD10: V1-V12 all present in the rule set",
      all(f"V{i}" in rule_ids for i in range(1, 13)),
      str([f"V{i}" for i in range(1, 13) if f"V{i}" not in rule_ids]))
check("B", "DoD10: V1-V12 lead the rule ordering",
      rule_ids[:12] == [f"V{i}" for i in range(1, 13)], str(rule_ids[:12]))
check("B", "DoD10: total rule count is 68", len(rule_ids) == 68,
      str(len(rule_ids)))
check("B", "DoD10: no duplicate rule ids",
      len(rule_ids) == len(set(rule_ids)))

# DoD 11 -- I1-I8 hold continuously
report = store.verify_integrity()
check("B", "DoD11: integrity report clean on a live chain",
      not report.violations, str(report.breached_constraints()))
check("B", "DoD11: I8 enforced on the acceptance path", "I8" in rule_ids)
store.assert_integrity()
check("B", "DoD11: assert_integrity passes", True)

# DoD 12 -- exactly one engine holds create authority per type
check("B", "DoD12: create authority has 8 entries (XR absent, C-02)",
      len(CREATE_AUTHORITY) == 8
      and ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY)
check("B", "DoD12: no engine creates two types",
      len(set(CREATE_AUTHORITY.values())) == len(CREATE_AUTHORITY))
check("B", "DoD12: Orchestration creates nothing",
      Engine.ORCHESTRATION not in CREATE_AUTHORITY.values())

# DoD 13 -- CI-1: configuration cannot enter lineage, scoring or reasoning
cfg = ConfigurationStore()
rec = cfg.record(Engine.RESEARCH, {"k": "v"})
check("B", "DoD13: configuration is not intelligence",
      rec.is_intelligence is False)
check("B", "DoD13: configuration never participates in lineage",
      rec.participates_in_lineage is False)
for accessor in ("as_lineage_reference", "as_evidence",
                 "confidence_contribution"):
    try:
        getattr(rec, accessor)()
        check("B", f"DoD13: {accessor} refused", False)
    except Exception:
        check("B", f"DoD13: {accessor} refused", True)

# DoD 14 -- Article IV: no platform artifact can become Evidence
art4_guards = []
try:
    rec.as_evidence()
    art4_guards.append("configuration")
except Exception:
    pass
fr_rules = [r for r in rule_ids if r.startswith("FR-")]
check("B", "DoD14: configuration cannot become Evidence", not art4_guards)
check("B", "DoD14: Feedback Record rules enforce AD-05",
      len(fr_rules) == 6, str(fr_rules))
pr = RetentionPolicy(store=KnowledgeStore())
check("B", "DoD14: retention artefacts are not intelligence",
      pr.performs_hard_deletion is False)

# ===========================================================================
# C. Backlog acceptance criteria for T01.8.1
# ===========================================================================

check("C", "AC1: all nine object types persistable",
      all(hasattr(KnowledgeStore, m) for m in write_paths.values()))
check("C", "AC2: lineage traversable both directions",
      root in store.graph.ancestors(top) and top in store.graph.descendants(root))
# AC3 -- no object acceptable without attribution
store3, alloc3 = fresh()
i3 = alloc3.new_object()
try:
    bad = build_attrs(i3, ObjectType.EVIDENCE, (), engine=None, config_ref="")
    store3.write(bad, build_lineage(i3.object_id, ObjectType.EVIDENCE))
    check("C", "AC3: write without attribution rejected", False)
except Exception:
    check("C", "AC3: write without attribution rejected", True)
check("C", "AC4: graph rebuild demonstrated",
      rebuilt.node_count == store.graph.node_count and store.graph_diverges() == ())

# ===========================================================================
# D. Architectural validations
# ===========================================================================

# Object model consistency
check("D", "object model: 9 types, 9 stages, 1:1",
      len({t.stage for t in ALL_TYPES}) == 9)
check("D", "object model: stage 8 has no owning engine [C-02]",
      8 not in ENGINE_STAGE.values())
check("D", "relationship taxonomy closed at 10",
      len(list(RelationshipType)) == 10)
check("D", "confidence: exactly five bands",
      len(list(ConfidenceBand)) == 5)
check("D", "confidence: three components",
      [f.name for f in dataclasses.fields(Confidence)]
      == ["evidential_support", "assertion_confidence", "effective_confidence"])
check("D", "calibration: five S-1 band criteria",
      len(CALIBRATION_RUBRIC) == 5)
check("D", "calibration: comparability not claimed demonstrated",
      compare_across_engines([]).comparability_demonstrated is False)

# Registry integrity -- every type with create authority has a registry
registries = ("evidence", "facts", "problems", "patterns", "opportunities",
              "solutions", "validations", "executions", "feedback")
check("D", "registry integrity: all nine registries exposed",
      all(hasattr(KnowledgeStore, r) for r in registries),
      str([r for r in registries if not hasattr(KnowledgeStore, r)]))

# Lifecycle correctness -- ARCHIVED only from ACTIVE
check("D", "lifecycle: ARCHIVED only from ACTIVE",
      can_transition(ObjectType.FACT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)
      and not any(can_transition(ObjectType.FACT, s, ObjectStatus.ARCHIVED)
                  for s in ObjectStatus if s is not ObjectStatus.ACTIVE))
# Reachability guard (T01.2.5)
storeR, allocR = fresh()
evR = write_evidence(storeR, allocR)
write_derived(storeR, allocR, ObjectType.FACT, [evR])
try:
    storeR.transition(evR.object_id, ObjectStatus.ARCHIVED, "retention")
    check("D", "lifecycle: reachable object cannot be archived [N-12]", False)
except ReachabilityError:
    check("D", "lifecycle: reachable object cannot be archived [N-12]", True)

# Cascade discipline -- M-65 preserved
check("D", "cascade: triggers are RETRACTED and INVALIDATED only [M-65]",
      CASCADE_TRIGGERS == frozenset({ObjectStatus.RETRACTED,
                                     ObjectStatus.INVALIDATED}))

# Store invariants -- I5 single ACTIVE per lineage
lineages = {}
for s in store:
    lineages.setdefault(s.lineage_id, []).append(s)
multi_active = [
    lid for lid, objs in lineages.items()
    if sum(1 for o in objs if o.status is ObjectStatus.ACTIVE) > 1
]
check("D", "store: at most one ACTIVE version per lineage [I5]",
      not multi_active, str(multi_active))
for method in ("delete", "update"):
    try:
        getattr(store, method)("x")
        check("D", f"store: hard {method} refused [I4]", False)
    except Exception:
        check("D", f"store: hard {method} refused [I4]", True)

# Dependency graph -- module layering is a DAG, store is the integration point
mod_imports: dict[str, set[str]] = {}
for path in sorted((ROOT / "oip").glob("*.py")):
    if path.name == "__init__.py":
        continue
    tree = ast.parse(path.read_text())
    mod_imports[path.stem] = {
        n.module.split(".", 1)[1]
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module
        and n.module.startswith("oip.")
    }


def _has_cycle(graph: dict[str, set[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for nxt in graph.get(node, ()):
            if visit(nxt):
                return True
        state[node] = 2
        return False

    return any(visit(n) for n in graph)


check("D", "dependency graph is acyclic (a DAG)", not _has_cycle(mod_imports))
check("D", "store is the sole broad integration point",
      len(mod_imports["store"]) >= 15
      and all(len(v) <= 6 for k, v in mod_imports.items() if k != "store"),
      str({k: len(v) for k, v in mod_imports.items() if len(v) > 6}))
check("D", "orchestration imports no Intelligence Object module",
      not (mod_imports["orchestration"] & {
          "evidence", "fact", "problem", "pattern", "opportunity", "solution",
          "validation", "execution", "feedback", "store", "graph", "lineage"}),
      str(sorted(mod_imports["orchestration"])))
check("D", "calibration imports only enums",
      mod_imports["calibration"] == {"enums"},
      str(sorted(mod_imports["calibration"])))
check("D", "retention imports only enums and graph",
      mod_imports["retention"] <= {"enums", "graph"},
      str(sorted(mod_imports["retention"])))

# Public API compatibility -- names every prior task depends on
API = {
    "oip.store": ["KnowledgeStore", "StoredObject", "WriteRejectedError"],
    "oip.contract": ["UniversalAttributes", "Confidence", "Explanation",
                     "LineageRef"],
    "oip.enums": ["ObjectType", "Engine", "ObjectStatus", "ConfidenceBand",
                  "RelationshipType", "CREATE_AUTHORITY"],
    "oip.orchestration": ["Orchestrator", "WorkItem", "WorkSet", "CycleBounds",
                          "FailureSurface", "ProcessingStateStore",
                          "ConcurrencyBoundary", "SequencingGuard"],
    "oip.retention": ["RetentionPolicy", "ReachabilityIndex"],
    "oip.calibration": ["assess_assertion", "CalibrationRegister",
                        "compare_across_engines"],
    "oip.cascade": ["CascadeInvalidation", "CASCADE_TRIGGERS"],
    "oip.configuration": ["ConfigurationStore", "FailureStore"],
}
import importlib  # noqa: E402
for mod_name, names in API.items():
    module = importlib.import_module(mod_name)
    absent = [n for n in names if not hasattr(module, n)]
    check("D", f"public API intact: {mod_name}", not absent, str(absent))

# Concurrency guarantees still hold (N-11 barrier) -- structural, not a rerun
storeC, allocC = fresh()
evC = [write_evidence(storeC, allocC) for _ in range(4)]
wsC = WorkSet(items=tuple(
    [WorkItem(Engine.RESEARCH, (e.object_id,), "cfg") for e in evC]
    + [WorkItem(Engine.PATTERN_INTELLIGENCE, ("p",), "cfg")]))
recC = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                    max_workers=4).run_cycle(wsC)
ConcurrencyBoundary(recC).assert_holds()
check("D", "N-11 concurrency boundary holds", True)

# ===========================================================================
# E. Forbidden closures -- nothing invented
# ===========================================================================

OPEN_MARKERS = ["M-01", "M-02", "M-04", "M-12", "M-14", "M-22", "M-24",
                "M-29", "M-31", "M-32", "M-36", "M-47", "M-56", "M-57",
                "M-65", "M-69", "M-70", "C-01", "C-02", "OQ-10", "OQ-11",
                "OQ-24", "OQ-34"]
all_src = "\n".join(
    p.read_text() for p in sorted((ROOT / "oip").glob("*.py"))
)
surfaced = [m for m in OPEN_MARKERS if m in all_src]
check("E", "open markers surfaced in production code",
      len(surfaced) >= 18, f"{len(surfaced)}/{len(OPEN_MARKERS)}: {surfaced}")
check("E", "C-02 still open: no ExecutionRecord create authority",
      ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY)
check("E", "M-65 still open: SUPERSEDED does not cascade",
      ObjectStatus.SUPERSEDED not in CASCADE_TRIGGERS)
check("E", "OQ-10 still open: stage skipping not policed",
      SequencingGuard(KnowledgeStore()).violations(
          WorkSet(items=(WorkItem(Engine.RESEARCH, ("x",), "cfg"),))) == ())
check("E", "M-57 still open: no observability vocabulary",
      not [n for n in dir(FailureSurface)
           if not n.startswith("_")
           and any(b in n.lower() for b in ("rate", "threshold", "alert"))])
check("E", "M-36 policy half open: no retry anywhere",
      not [n for n in dir(Orchestrator)
           if not n.startswith("_") and "retry" in n.lower()])

# ---------------------------------------------------------------------------
# A. DoD6 -- cascade correctness under NON-UNIFORM lineage depth
#
# Regression guard for the defect found by this gate. `_collect` orders
# dependents by shortest path, which in a DAG is not a topological order, so
# eligibility must not depend on traversal order. Uniform-depth fixtures hide
# this; a Validation spanning stages does not. [T01.2.4, N-9, I6, IOM 3.7]
# ---------------------------------------------------------------------------
def _skew_case():
    store, alloc = KnowledgeStore(), IdentityAllocator()
    ev = write_evidence(store, alloc)
    fa = write_derived(store, alloc, ObjectType.FACT, [ev])
    pr = write_derived(store, alloc, ObjectType.PROBLEM, [fa])
    pt = write_derived(store, alloc, ObjectType.PATTERN, [pr])
    op = write_derived(store, alloc, ObjectType.OPPORTUNITY, [pt])
    so = write_derived(store, alloc, ObjectType.SOLUTION, [op])
    shallow = write_derived(store, alloc, ObjectType.FACT, [ev])
    span = write_derived(store, alloc, ObjectType.VALIDATION, [shallow, so])
    return store, ev, so, span


_st, _ev, _so, _span = _skew_case()
_plan = CascadeInvalidation(store=_st).plan(_ev.object_id)
check("A", "DoD6: BFS order is genuinely non-topological (defect precondition)",
      _plan.index(_span.object_id) < _plan.index(_so.object_id))

_st, _ev, _so, _span = _skew_case()
CascadeInvalidation(store=_st).retract(_ev.object_id, "withdrawn")
check("A", "DoD6: uneven-depth dependent is invalidated, not spared",
      _st.get(_span.object_id).status is ObjectStatus.INVALIDATED,
      f"status={_st.get(_span.object_id).status.value}")

_i6 = [v for v in IntegrityVerifier(store=_st).verify().violations
       if v.constraint_id == "I6"]
check("A", "DoD11: no I6 violation after an uneven-depth cascade",
      not _i6, f"{len(_i6)} violation(s)")

# ===========================================================================
# Report
# ===========================================================================

# Computed AFTER every check has run. Placing this earlier silently excludes
# any check appended below it from the pass/fail tally.
failed = [(s, n, d) for s, n, ok, d in RESULTS if not ok]

by_section: dict[str, list[tuple[str, bool]]] = {}
for section, name, ok, _ in RESULTS:
    by_section.setdefault(section, []).append((name, ok))

SECTION_TITLES = {
    "A": "Definition of Done -- Functional (1-9)",
    "B": "Definition of Done -- Contract (10-14)",
    "C": "T01.8.1 backlog acceptance criteria",
    "D": "Architectural validations",
    "E": "Forbidden closures / open markers",
}
for section in sorted(by_section):
    entries = by_section[section]
    passed = sum(1 for _, ok in entries if ok)
    print(f"\n=== {section}. {SECTION_TITLES[section]} "
          f"({passed}/{len(entries)}) ===")
    for name, ok in entries:
        print(f"  {'ok  ' if ok else 'FAIL'} {name}")

print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} exit-gate checks passed")
if failed:
    print("\nFAILURES:")
    for section, name, detail in failed:
        print(f"  [{section}] {name}" + (f"  -> {detail}" if detail else ""))
sys.exit(1 if failed else 0)
