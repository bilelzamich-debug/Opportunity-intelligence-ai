"""Mechanical architecture verification for T01.2.5.

Checks properties against the ratified documents by extraction.
"""
from __future__ import annotations

import ast
import dataclasses
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.cascade import CASCADE_TRIGGERS  # noqa: E402
from oip.enums import ObjectStatus, ObjectType  # noqa: E402
from oip.identity import IdentityAllocator  # noqa: E402
from oip.lifecycle import can_transition, permitted_transitions  # noqa: E402
from oip.retention import RetentionPolicy  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402
from oip.store import ReachabilityError as StoreReachabilityError  # noqa: E402
from conftest import write_chain, write_derived, write_evidence  # noqa: E402
from test_evidence import evidence as build_evidence  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    CHECKS.append((name, bool(condition), detail))


src = (ROOT / "oip" / "retention.py").read_text()
tree = ast.parse(src)


def fresh():
    return KnowledgeStore(), IdentityAllocator()


def real_ev(store, alloc, content="material"):
    return store.write_evidence(build_evidence(alloc, content))


# --- 1. Acceptance criteria quoted from the ratified backlog --------------
backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
task = backlog.split("#### `T01.2.5`")[1].split("### Feature F01.3")[0]
criteria = re.findall(r"^- (.+)$", task, re.M)
check("backlog states exactly 3 acceptance criteria", len(criteria) == 3, str(criteria))
check("AC1 is reachable-never-archived",
      any("reachable from any ACTIVE object are never archived" in c for c in criteria))
check("AC2 is traversal never breaks",
      any("Lineage traversal never breaks after archival" in c for c in criteria))
check("AC3 is fingerprint and provenance permanent",
      any("content_fingerprint and provenance retained permanently" in c
          for c in criteria))
check("backlog: depends on T01.2.2 and T01.3.4",
      "`T01.2.2`" in task and "`T01.3.4`" in task)
check("backlog: blocks T01.8.1", "`T01.8.1`" in task)

# --- 2. N-12's rule reproduced verbatim -----------------------------------
n12 = (DOCS / "decisions" / "N-12-retention.md").read_text()
check("N-12 is RATIFIED", "| **Status** | `RATIFIED` |" in n12)
check("N-12 closes M-38", "| **Closes** | M-38 |" in n12)
check("N-12 states the reachability rule verbatim",
      "An object is tiered only when it is **not reachable from any `ACTIVE` "
      "object** by lineage traversal." in n12)
check("N-12 says anything supporting current knowledge stays",
      "Anything supporting current knowledge stays." in n12)
check("N-12 says tiering sets ARCHIVED",
      "**Tiering sets `ARCHIVED`**" in n12)
check("N-12 says it is a maintenance operation",
      "invoked as a maintenance operation" in n12)
check("N-12 says traversal never breaks",
      "**Lineage traversal never breaks**" in n12)
check("N-12 binds T01.2.5", "**`T01.2.5`** ARCHIVED tiering by reachability" in n12)
check("N-12 rejected archiving by age (Option B)",
      "**Option B — Archive by age.**\n*Rejected:*" in n12)
check("N-12 rejected deleting unreachable objects (Option E)",
      "**Option E — Delete unreachable objects entirely.**\n*Rejected:*" in n12)

# --- 3. Marker crosswalk: IOM MISSING-31 -> M-38 (closed) -----------------
crosswalk = (DOCS / "decisions" / "marker-crosswalk.md").read_text()
check("crosswalk maps IOM MISSING-31 (retention) to canonical M-38",
      "| 7 | `MISSING-31` | Retention policy | **M-38** |" in crosswalk)
check("crosswalk warns canonical M-31 is a different gap",
      "*(v2 M-31: Post-validation promote/reject owner)* | Would close the "
      "wrong gap |" in crosswalk)
check("module records the crosswalk resolution",
      "MISSING-31" in src and "M-38" in src)

# --- 4. IOM: ACTIVE is the only ARCHIVED source ---------------------------
iom = (DOCS / "PKP_Intelligence_Object_Model.md").read_text()
check("IOM 2.1 defines ACTIVE -> ARCHIVED",
      "| `ACTIVE` → `ARCHIVED` | Retention policy |" in iom)
check("IOM 2.1 states no terminal state may transition",
      "**No terminal state may transition.**" in iom)
check("IOM contains no other ARCHIVED transition row",
      not re.search(
          r"\| `(PROPOSED|SUPERSEDED|REJECTED|RETRACTED|INVALIDATED)` → "
          r"`ARCHIVED`", iom))
for source in (ObjectStatus.PROPOSED, ObjectStatus.SUPERSEDED,
               ObjectStatus.REJECTED, ObjectStatus.RETRACTED,
               ObjectStatus.INVALIDATED, ObjectStatus.ARCHIVED):
    check(f"implementation forbids {source.value} -> ARCHIVED",
          can_transition(ObjectType.EVIDENCE, source, ObjectStatus.ARCHIVED)
          is False)
check("implementation permits ACTIVE -> ARCHIVED",
      can_transition(ObjectType.EVIDENCE, ObjectStatus.ACTIVE,
                     ObjectStatus.ARCHIVED) is True)
check("ARCHIVED is terminal",
      permitted_transitions(ObjectType.FACT, ObjectStatus.ARCHIVED)
      == frozenset())

# --- 5. AC1 empirically ----------------------------------------------------
store, alloc = fresh()
ev = write_evidence(store, alloc)
write_derived(store, alloc, ObjectType.FACT, [ev])
try:
    store.transition(ev.object_id, ObjectStatus.ARCHIVED, "retention")
    check("AC1: a supporting object cannot be archived", False)
except StoreReachabilityError:
    check("AC1: a supporting object cannot be archived", True)
check("AC1: the object remains ACTIVE",
      store.get(ev.object_id).status is ObjectStatus.ACTIVE)

store, alloc = fresh()
chain = write_chain(store, alloc)
policy = RetentionPolicy(store=store)
terminal = chain[ObjectType.VALIDATION].object_id
check("AC1: every ancestor in a live chain is protected",
      all(not policy.is_archivable(s.object_id)
          for s in chain.values() if s.object_id != terminal))

store, alloc = fresh()
lone = real_ev(store, alloc)
RetentionPolicy(store=store).archive(lone.object_id)
check("a leaf with no dependents IS archivable",
      store.get(lone.object_id).status is ObjectStatus.ARCHIVED)

# --- 6. AC2 empirically ----------------------------------------------------
store, alloc = fresh()
chain = write_chain(store, alloc)
top = chain[ObjectType.VALIDATION].object_id
before_edges = (store.graph.node_count, store.graph.edge_count)
before_evidence = store.graph.evidence_set(top)
store.transition(top, ObjectStatus.RETRACTED, "withdrawn")
policy = RetentionPolicy(store=store)
for otype in (ObjectType.SOLUTION, ObjectType.OPPORTUNITY, ObjectType.PATTERN,
              ObjectType.PROBLEM, ObjectType.FACT, ObjectType.EVIDENCE):
    policy.archive(chain[otype].object_id)
evidence_id = chain[ObjectType.EVIDENCE].object_id
check("AC2: archived object still in the graph", store.graph.contains(evidence_id))
check("AC2: ancestry still resolves", evidence_id in store.graph.ancestors(top))
check("AC2: evidence still reachable", store.graph.reaches_evidence(top) is True)
check("AC2: path to evidence still found",
      store.graph.path_to_evidence(top) is not None)
check("AC2: evidence_set unchanged", store.graph.evidence_set(top) == before_evidence)
check("AC2: graph shape unchanged",
      (store.graph.node_count, store.graph.edge_count) == before_edges)
check("AC2: graph rebuild reproduces the archived chain",
      store.graph_diverges() == ())
store.assert_integrity()
check("AC2: integrity holds after archival", True)

# --- 7. AC3 empirically ----------------------------------------------------
store, alloc = fresh()
stored = real_ev(store, alloc, "precious")
before = store.evidence.get(stored.object_id)
fingerprint, source = before.content.fingerprint, before.provenance.source_identifier
count = len(store)
policy = RetentionPolicy(store=store)
policy.archive(stored.object_id)
after = store.evidence.get(stored.object_id)
check("AC3: payload retained", after is not None)
check("AC3: fingerprint retained", after.content.fingerprint == fingerprint)
check("AC3: provenance retained", after.provenance.source_identifier == source)
check("AC3: content not evicted", after.content.content == "precious")
check("AC3: skeleton verification passes",
      policy.verify_skeleton_intact(stored.object_id) == ())
check("I4: nothing hard-deleted",
      len(store) == count and store.find(stored.object_id) is not None)
check("I4: policy reports no hard deletion",
      policy.performs_hard_deletion is False)
attributes = store.get(stored.object_id).attributes
check("skeleton: identity/type/version/lineage_id retained",
      all(getattr(attributes, n, None) not in (None, "")
          for n in ("object_id", "object_type", "version", "lineage_id")))
check("skeleton: attribution retained",
      bool(attributes.produced_by_engine) and
      bool(attributes.engine_configuration_ref))
check("skeleton: status_reason recorded [V9]",
      bool((attributes.status_reason or "").strip()))

# --- 8. Cascade unchanged [N-9, M-65] -------------------------------------
check("CASCADE_TRIGGERS unchanged",
      CASCADE_TRIGGERS == frozenset(
          {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED}))
check("ARCHIVED is not a cascade trigger",
      ObjectStatus.ARCHIVED not in CASCADE_TRIGGERS)
cascade_src = (ROOT / "oip" / "cascade.py").read_text()
check("cascade module still records M-65 as open", "M-65" in cascade_src)

# --- 9. No invented policy -------------------------------------------------
BANNED_PREFIX = ("schedule", "collect", "expire", "evict", "purge", "delete",
                 "prune", "sweep")
names = [n for n in dir(RetentionPolicy) if not n.startswith("_")]
check("no scheduling/GC/eviction capability",
      not [n for n in names if n.lower().startswith(BANNED_PREFIX)], str(names))
lowered = src.lower()
for banned in ("timedelta", "older than", "ttl", " days"):
    check(f"no age heuristic: {banned!r} absent", banned not in lowered)
check("unspecified content tiering is reported",
      RetentionPolicy(store=KnowledgeStore()).content_tiering_specified is False)
check("no content eviction performed",
      RetentionPolicy(store=KnowledgeStore()).content_eviction_performed is False)
check("OQ-12 not reopened: N-15 cited for permanent retention", "N-15" in src)

# --- 10. Control-layer discipline -----------------------------------------
imports = {n.module for n in ast.walk(tree)
           if isinstance(n, ast.ImportFrom) and n.module}
check("retention imports only enums and graph constants",
      {i for i in imports if i.startswith("oip.")} <= {"oip.enums", "oip.graph"},
      str(sorted(i for i in imports if i.startswith("oip."))))
check("policy owns no storage: store and graph are supplied",
      {f.name for f in dataclasses.fields(RetentionPolicy)}
      == {"store", "graph", "max_depth", "content_tiering_specified"})
check("ReachabilityIndex is frozen",
      any(isinstance(n, ast.ClassDef) and n.name == "ReachabilityIndex"
          and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
          for n in ast.walk(tree)))
check("ArchivalAssessment is frozen",
      any(isinstance(n, ast.ClassDef) and n.name == "ArchivalAssessment"
          and any("frozen=True" in ast.unparse(d) for d in n.decorator_list)
          for n in ast.walk(tree)))

# --- 11. Fail closed -------------------------------------------------------
class NoGraph:
    graph = None

    def active_objects(self):
        return ()


try:
    RetentionPolicy(store=NoGraph()).reachability()
    check("fails closed without a graph", False)
except Exception:
    check("fails closed without a graph", True)

# --- 12. Backward compatibility -------------------------------------------
store, alloc = fresh()
ev = write_evidence(store, alloc)
write_derived(store, alloc, ObjectType.FACT, [ev])
store.transition(ev.object_id, ObjectStatus.RETRACTED, "withdrawn")
check("non-ARCHIVED transitions are unguarded",
      store.get(ev.object_id).status is ObjectStatus.RETRACTED)
check("KnowledgeStore public API intact",
      all(hasattr(KnowledgeStore, n) for n in
          ("write", "transition", "get", "find", "contains", "active_objects",
           "rebuild_graph", "verify_integrity")))

# --- 13. Module header -----------------------------------------------------
header = src.split('"""')[1]
check("header names Task: T01.2.5", "Task: T01.2.5" in header)
for marker in ("N-12", "R-2", "IOM 2.1", "I4", "N-15", "M-65"):
    check(f"header cites {marker}", marker in header)

failed = [(n, d) for n, ok, d in CHECKS if not ok]
for name, ok, detail in CHECKS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(CHECKS) - len(failed)}/{len(CHECKS)} checks passed")
sys.exit(1 if failed else 0)
