"""Strictest reachability test: reproduce the defect through the TYPED
production write path `store.write_validation(...)`, not the generic
`store.write(...)`.

If the defect reproduces here, it is reachable through the production API by
an object that passed every acceptance rule and every per-type payload rule.
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
from test_validation import make_validation  # noqa: E402

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


E = put(ObjectType.EVIDENCE, [])
F = put(ObjectType.FACT, [E])
PR = put(ObjectType.PROBLEM, [F])
PT = put(ObjectType.PATTERN, [PR])
OP = put(ObjectType.OPPORTUNITY, [PT])
SO = put(ObjectType.SOLUTION, [OP])
F2 = put(ObjectType.FACT, [E])

# Build a Validation payload deriving from BOTH F2 (stage 1) and SO (stage 5),
# testing a claim that lives on the Solution.
identity = alloc.new_object()
ceiling = min(F2.attributes.confidence.effective_confidence,
              SO.attributes.confidence.effective_confidence)
attrs = build_attrs(
    identity, ObjectType.VALIDATION,
    ((F2.object_id, ObjectType.FACT), (SO.object_id, ObjectType.SOLUTION)),
    status=ObjectStatus.ACTIVE, status_reason=None, upstream_ceiling=ceiling,
)
validation = make_validation(alloc, solution_ref=SO.object_id, attributes=attrs)

stored_va = store.write_validation(validation)
print("write_validation ACCEPTED a Validation with upstreams at stages 1 and 5")
print(f"  VA = {stored_va.object_id}")

names = {E.object_id: "E", F.object_id: "F", PR.object_id: "PR",
         PT.object_id: "PT", OP.object_id: "OP", SO.object_id: "SO",
         F2.object_id: "F2", stored_va.object_id: "VA"}

casc = CascadeInvalidation(store=store)
print(f"  BFS plan: {[names.get(o, o) for o in casc.plan(E.object_id)]}")

casc.retract(E.object_id, "the source withdrew the underlying document")

print()
for oid, n in names.items():
    print(f"  {n:3s} {store.find(oid).status.value}")

va = store.find(stored_va.object_id)
ups = [store.find(F2.object_id).status, store.find(SO.object_id).status]
withdrawn = (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED)
breach = all(u in withdrawn for u in ups) and va.status is ObjectStatus.ACTIVE

i6 = [v for v in IntegrityVerifier(store=store).verify().violations
      if v.constraint_id == "I6"]

print()
print("=" * 78)
print("VERDICT (production API)")
print("=" * 78)
print(f"  VA ACTIVE with all upstreams withdrawn : {breach}")
print(f"  I6 violations after cascade            : {len(i6)}")
if breach:
    print("  => The defect is reachable through store.write_validation().")
sys.exit(1 if (breach or i6) else 0)
