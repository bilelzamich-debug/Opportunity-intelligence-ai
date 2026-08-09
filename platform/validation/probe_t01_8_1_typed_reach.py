"""Definitive reachability test for the BFS-ordering inconsistency.

The generic `store.write()` admitted a Problem deriving from (Fact, Problem).
But the production API for each type is `store.write_<type>(payload)`, which
runs the per-type payload rules. Those rules DO check upstream types
(problem.py:367 "a Problem derives from Facts only").

If every typed write path enforces a single permitted parent type, then every
edge in the lineage graph goes from stage k to stage k-1, BFS depth equals the
stage distance, BFS order IS topological, and the `doomed` set is always
complete when a dependent is evaluated -- making the inconsistency
UNREACHABLE through the production API.

This script determines which of the two situations holds.
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

print("=" * 78)
print("Q. Do the PAYLOAD constructors reject a skip-level / mixed-type lineage?")
print("=" * 78)

import oip.problem as problem_mod  # noqa: E402

# Inspect the Problem payload constructor's upstream-type rule directly.
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
A = put(ObjectType.FACT, [E])
P = put(ObjectType.FACT, [E])
Q = put(ObjectType.PROBLEM, [P])

# Now try to build a Problem PAYLOAD whose derives_from = (Fact A, Problem Q).
identity = alloc.new_object()
upstream = ((A.object_id, ObjectType.FACT), (Q.object_id, ObjectType.PROBLEM))
attrs = build_attrs(
    identity, ObjectType.PROBLEM, upstream,
    status=ObjectStatus.ACTIVE, status_reason=None,
    upstream_ceiling=min(A.attributes.confidence.effective_confidence,
                         Q.attributes.confidence.effective_confidence),
)

Problem = problem_mod.Problem
sig = [f for f in Problem.__dataclass_fields__]
print(f"  Problem payload fields: {sig}")

try:
    payload = Problem(
        attributes=attrs,
        statement="A skewed problem for reachability testing purposes here.",
        affected_scope="probe-scope",
        supporting_facts=(A.object_id,),
        inference_basis=problem_mod.InferenceBasis(
            referenced_facts=frozenset({A.object_id}),
            reasoning="Probe of the upstream-type rule at the payload layer.",
        ),
    )
    print("  Problem payload CONSTRUCTED with a Problem in derives_from")
    payload_allows = True
except Exception as exc:
    print(f"  Problem payload REJECTED: {type(exc).__name__}: {exc}")
    payload_allows = False

print()
print("=" * 78)
print("VERDICT")
print("=" * 78)
if payload_allows:
    print("  Typed payload layer ALSO admits the skewed shape.")
    print("  => The uneven-depth diamond is reachable through the production")
    print("     API. The BFS ordering inconsistency is a REAL DEFECT.")
else:
    print("  The typed payload layer REJECTS the skewed shape.")
    print("  Every DERIVES_FROM edge then goes stage k -> stage k-1, so BFS")
    print("  depth == stage distance and BFS order IS topological.")
    print("  => Unreachable through the production API. The generic")
    print("     store.write() bypass is a TEST-HARNESS affordance, not a")
    print("     production path. Record as a LATENT ROBUSTNESS GAP, not a")
    print("     live defect -- and verify the constraint is genuinely")
    print("     enforced on EVERY typed path before concluding.")
