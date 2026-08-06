"""Is the uneven-depth diamond REACHABLE through legal objects?

The probe that exposed the ordering inconsistency wrote straight to the store.
If the pipeline enforces strict type layering -- every upstream of an object of
type T has the same type -- then BFS depth equals the type's stage index, BFS
order IS a topological order, and the inconsistency is unreachable.

This script tests the enforcement question mechanically, per type pair, through
the acceptance path rather than by direct store writes. Fails closed: if a
skewed shape can be ACCEPTED, the defect is real.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conftest import build_attrs, build_lineage  # noqa: E402
from oip.enums import ObjectStatus, ObjectType  # noqa: E402
from oip.identity import IdentityAllocator  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402

PIPELINE = [
    ObjectType.EVIDENCE, ObjectType.FACT, ObjectType.PROBLEM,
    ObjectType.PATTERN, ObjectType.OPPORTUNITY, ObjectType.SOLUTION,
]


def put(store, alloc, otype, parents):
    identity = alloc.new_object()
    upstream = tuple((p.object_id, p.object_type) for p in parents)
    kw = {}
    if parents:
        kw["upstream_ceiling"] = min(
            p.attributes.confidence.effective_confidence for p in parents
        )
    attrs = build_attrs(identity, otype, upstream, status=ObjectStatus.ACTIVE,
                        status_reason=None, **kw)
    return store.write(attrs, build_lineage(identity.object_id, otype, upstream))


print("=" * 78)
print("Q1. Does the STORE write path reject a mixed-type / skip-level lineage?")
print("=" * 78)

# X : PROBLEM derived from [FACT, PROBLEM]  -- the shape used in probe P1
store, alloc = KnowledgeStore(), IdentityAllocator()
E = put(store, alloc, ObjectType.EVIDENCE, [])
A = put(store, alloc, ObjectType.FACT, [E])
P = put(store, alloc, ObjectType.FACT, [E])
Q = put(store, alloc, ObjectType.PROBLEM, [P])
try:
    X = put(store, alloc, ObjectType.PROBLEM, [A, Q])
    print(f"  ACCEPTED: Problem derived from (Fact, Problem)  -> {X.object_id}")
    store_allows_skew = True
except Exception as exc:
    print(f"  REJECTED by store: {type(exc).__name__}: {exc}")
    store_allows_skew = False

print()
print("=" * 78)
print("Q2. Which upstream type combinations does the store admit per type?")
print("=" * 78)
matrix = {}
for target in PIPELINE[1:] + [ObjectType.VALIDATION, ObjectType.EXECUTION_RECORD,
                              ObjectType.FEEDBACK_RECORD]:
    admitted = []
    for parent_type in ObjectType:
        s2, a2 = KnowledgeStore(), IdentityAllocator()
        # build a chain deep enough to own an object of parent_type
        try:
            ev = put(s2, a2, ObjectType.EVIDENCE, [])
            made = {ObjectType.EVIDENCE: ev}
            order = [ObjectType.FACT, ObjectType.PROBLEM, ObjectType.PATTERN,
                     ObjectType.OPPORTUNITY, ObjectType.SOLUTION,
                     ObjectType.VALIDATION, ObjectType.EXECUTION_RECORD,
                     ObjectType.FEEDBACK_RECORD]
            prev = ev
            for t in order:
                prev = put(s2, a2, t, [prev])
                made[t] = prev
            if parent_type not in made:
                continue
            put(s2, a2, target, [made[parent_type]])
            admitted.append(parent_type.value)
        except Exception:
            pass
    matrix[target] = admitted
    print(f"  {target.value:18s} <- {admitted}")

print()
print("=" * 78)
print("VERDICT")
print("=" * 78)
if store_allows_skew:
    print("  The store ADMITS a skip-level lineage (Problem <- Fact + Problem).")
    print("  BFS depth is therefore NOT pinned to the type stage, so BFS order")
    print("  is NOT guaranteed topological, and the `doomed` set can be")
    print("  incomplete when a dependent is evaluated.")
    print("  => the ordering inconsistency is REACHABLE. Treat as a DEFECT.")
else:
    print("  The store REJECTS the skewed shape; reachability NOT established")
    print("  by this route. Further routes must be tried before concluding.")
