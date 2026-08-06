"""Decisive reachability probe: build the uneven-depth diamond using ONLY
legal, type-rule-conformant objects, and see whether the I6 breach reproduces.

Chain of reasoning:
  * Problem/Pattern/Opportunity/Solution/ExecutionRecord/FeedbackRecord each
    enforce a SINGLE permitted upstream type, so those edges always go from
    stage k to stage k-1.
  * Validation does NOT: validation.py only requires that `tests_claim`'s
    object appears in derives_from. IOM 3.7 says a Validation "DERIVES_FROM
    the object containing the tested claim" -- and a claim can live on any
    object, not only a Solution.
  * A Validation therefore introduces an edge that can span several stages,
    which breaks the "BFS depth == stage distance" property.

If a Validation can derive from BOTH a shallow object and a deep object, it is
discovered at shallow-depth+1 -- possibly before its deep upstream is decided
-- and the `doomed` set is incomplete when it is evaluated.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from conftest import build_attrs, build_lineage  # noqa: E402
from oip.cascade import CascadeInvalidation  # noqa: E402
from oip.enums import ObjectStatus, ObjectType  # noqa: E402
from oip.identity import IdentityAllocator  # noqa: E402
from oip.integrity import IntegrityVerifier  # noqa: E402
from oip.store import KnowledgeStore  # noqa: E402

store, alloc = KnowledgeStore(), IdentityAllocator()


def put(otype, parents):
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
print("Building a strictly stage-respecting pipeline")
print("=" * 78)

E = put(ObjectType.EVIDENCE, [])            # stage 0
F = put(ObjectType.FACT, [E])               # stage 1
PR = put(ObjectType.PROBLEM, [F])           # stage 2
PT = put(ObjectType.PATTERN, [PR])          # stage 3
OP = put(ObjectType.OPPORTUNITY, [PT])      # stage 4
SO = put(ObjectType.SOLUTION, [OP])         # stage 5

# A second, SHALLOW Fact off the same Evidence.
F2 = put(ObjectType.FACT, [E])              # stage 1

names = {E.object_id: "E", F.object_id: "F", PR.object_id: "PR",
         PT.object_id: "PT", OP.object_id: "OP", SO.object_id: "SO",
         F2.object_id: "F2"}

# The Validation derives from BOTH the deep Solution (stage 5) and the shallow
# Fact F2 (stage 1). Legal: validation.py imposes no upstream-type rule, and
# IOM 3.7 permits deriving from the object containing the tested claim.
VA = put(ObjectType.VALIDATION, [F2, SO])
names[VA.object_id] = "VA"
print(f"  Validation VA derives from F2 (stage 1) and SO (stage 5)")

casc = CascadeInvalidation(store=store)
order = casc.plan(E.object_id)
print(f"  BFS plan order: {[names.get(o, o) for o in order]}")
pos = {o: i for i, o in enumerate(order)}
print(f"  VA at index {pos[VA.object_id]}, its upstream SO at index {pos[SO.object_id]}")
if pos[SO.object_id] > pos[VA.object_id]:
    print("  => VA is evaluated BEFORE its own upstream SO. `doomed` is incomplete.")

print()
print("=" * 78)
print("Retracting the single root Evidence (everything descends from it)")
print("=" * 78)
result = casc.retract(E.object_id, "source withdrew the document")

for oid, n in names.items():
    print(f"  {n:3s} {store.find(oid).status.value}")

va_state = store.find(VA.object_id).status
upstreams = [store.find(F2.object_id).status, store.find(SO.object_id).status]
withdrawn = (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED)
orphaned_active = all(u in withdrawn for u in upstreams) and va_state is ObjectStatus.ACTIVE

print()
print(f"  partially_retracted = {[names.get(o, o) for o in result.partially_retracted]}")
print(f"  VA status = {va_state.value}; upstream states = {[u.value for u in upstreams]}")

report = IntegrityVerifier(store=store).verify()
i6 = [v for v in report.violations if v.constraint_id == "I6"]

print()
print("=" * 78)
print("VERDICT")
print("=" * 78)
if orphaned_active:
    print("  DEFECT REPRODUCED THROUGH LEGAL OBJECTS.")
    print("  VA is ACTIVE while every one of its upstream references is")
    print("  withdrawn. This is precisely the I6 breach cascade exists to")
    print("  prevent, and it is reachable without any type-rule violation.")
else:
    print("  Not reproduced: VA was handled correctly.")
print(f"  I6 violations reported by the integrity verifier: {len(i6)}")
for v in i6:
    print(f"    - {names.get(v.object_id, v.object_id)}: {v.detail}")
sys.exit(1 if (orphaned_active or i6) else 0)
