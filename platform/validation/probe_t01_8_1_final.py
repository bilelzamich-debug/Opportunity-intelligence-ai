"""T01.8.1 final gate -- adversarial probes against the T01.2.4-R1 partial-retraction path.

Hypothesis under test: `_collect` orders dependents breadth-first by SHORTEST
path from the origin. In a DAG, shortest-path order is NOT a topological
order. If a node X has one upstream reachable at depth 1 and another upstream
reachable only at depth 3, X is discovered at depth 2 -- BEFORE its own
depth-3 upstream is decided. The `doomed` set would then be incomplete when X
is evaluated, and X would be spared as "partially retracted" even though every
one of its upstreams ends up withdrawn by this same cascade.

That would leave X ACTIVE with all upstream references withdrawn, which is
exactly the I6 breach cascade exists to prevent.
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

FAILURES: list[str] = []
PASSES: list[str] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    (PASSES if ok else FAILURES).append(f"{name}: {detail}")
    print(("PASS  " if ok else "FAIL  ") + name + (f"  -- {detail}" if detail else ""))


def put(store, alloc, otype, parents):
    """Persist an ACTIVE object of `otype` derived from `parents`."""
    identity = alloc.new_object()
    upstream = tuple((p.object_id, p.object_type) for p in parents)
    if parents:
        ceiling = min(p.attributes.confidence.effective_confidence for p in parents)
        attrs = build_attrs(
            identity, otype, upstream, status=ObjectStatus.ACTIVE,
            status_reason=None, upstream_ceiling=ceiling,
        )
    else:
        attrs = build_attrs(
            identity, otype, upstream, status=ObjectStatus.ACTIVE, status_reason=None,
        )
    return store.write(attrs, build_lineage(identity.object_id, otype, upstream))


# --------------------------------------------------------------------------
# Probe 1: uneven-depth diamond. X's two upstreams sit at BFS depth 1 and 3.
# --------------------------------------------------------------------------
def probe_uneven_depth_diamond():
    store, alloc = KnowledgeStore(), IdentityAllocator()

    E = put(store, alloc, ObjectType.EVIDENCE, [])
    A = put(store, alloc, ObjectType.FACT, [E])          # depth 1
    P = put(store, alloc, ObjectType.FACT, [E])          # depth 1
    Q = put(store, alloc, ObjectType.PROBLEM, [P])       # depth 2
    B = put(store, alloc, ObjectType.FACT, [E])          # depth 1 (control)

    # X derives from A (depth 1) and Q (depth 2) -> X discovered at depth 2
    X = put(store, alloc, ObjectType.PROBLEM, [A, Q])

    casc = CascadeInvalidation(store=store)
    order = casc.plan(E.object_id)
    pos = {oid: i for i, oid in enumerate(order)}
    print(f"    plan order = {[('A' if o==A.object_id else 'P' if o==P.object_id else 'Q' if o==Q.object_id else 'B' if o==B.object_id else 'X' if o==X.object_id else o) for o in order]}")
    upstream_after_x = pos.get(Q.object_id, -1) > pos.get(X.object_id, 1 << 30)
    print(f"    Q evaluated after X? {upstream_after_x}")

    result = casc.retract(E.object_id, "source withdrew everything")

    x_state = store.find(X.object_id).status
    # Every upstream of X (A and Q) descends from E, so all must be withdrawn.
    a_state = store.find(A.object_id).status
    q_state = store.find(Q.object_id).status
    print(f"    A={a_state.value} Q={q_state.value} X={x_state.value}")

    all_up_withdrawn = a_state in (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED) and \
        q_state in (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED)
    ok = not (all_up_withdrawn and x_state is ObjectStatus.ACTIVE)
    record(
        "P1 uneven-depth diamond: X not left ACTIVE with all upstream withdrawn",
        ok,
        f"X={x_state.value}, upstreams A={a_state.value} Q={q_state.value}, "
        f"partially_retracted={len(result.partially_retracted)}",
    )

    audit = IntegrityVerifier(store=store).verify()
    i6 = [v for v in audit.violations if v.constraint_id == "I6"]
    record("P1 integrity audit reports no I6 breach after cascade", not i6,
           f"{len(i6)} I6 violation(s): {[v.object_id for v in i6][:3]}")
    return store, X, A, Q


# --------------------------------------------------------------------------
# Probe 2: deeper skew -- upstream at depth 4 vs depth 1.
# --------------------------------------------------------------------------
def probe_deep_skew():
    store, alloc = KnowledgeStore(), IdentityAllocator()
    E = put(store, alloc, ObjectType.EVIDENCE, [])
    A = put(store, alloc, ObjectType.FACT, [E])                 # d1
    c1 = put(store, alloc, ObjectType.FACT, [E])                # d1
    c2 = put(store, alloc, ObjectType.PROBLEM, [c1])            # d2
    c3 = put(store, alloc, ObjectType.PATTERN, [c2])            # d3
    c4 = put(store, alloc, ObjectType.OPPORTUNITY, [c3])        # d4
    X = put(store, alloc, ObjectType.OPPORTUNITY, [A, c4])      # discovered d2

    casc = CascadeInvalidation(store=store)
    casc.retract(E.object_id, "withdrawn")

    states = {n: store.find(o.object_id).status
              for n, o in (("A", A), ("c4", c4), ("X", X))}
    print(f"    {[(k, v.value) for k, v in states.items()]}")
    withdrawn = (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED)
    bad = states["A"] in withdrawn and states["c4"] in withdrawn and \
        states["X"] is ObjectStatus.ACTIVE
    record("P2 deep-skew diamond: X not orphaned-but-ACTIVE", not bad,
           f"X={states['X'].value}")

    i6 = [v for v in IntegrityVerifier(store=store).verify().violations
          if v.constraint_id == "I6"]
    record("P2 integrity audit reports no I6 breach", not i6, f"{len(i6)} violation(s)")


# --------------------------------------------------------------------------
# Probe 3: legitimate partial retraction must still be spared (no over-fix).
# --------------------------------------------------------------------------
def probe_genuine_partial_is_spared():
    store, alloc = KnowledgeStore(), IdentityAllocator()
    E1 = put(store, alloc, ObjectType.EVIDENCE, [])
    E2 = put(store, alloc, ObjectType.EVIDENCE, [])
    F1 = put(store, alloc, ObjectType.FACT, [E1])
    F2 = put(store, alloc, ObjectType.FACT, [E2])
    X = put(store, alloc, ObjectType.PROBLEM, [F1, F2])

    casc = CascadeInvalidation(store=store)
    result = casc.retract(E1.object_id, "one source withdrew")

    x_state = store.find(X.object_id).status
    f2_state = store.find(F2.object_id).status
    ok = x_state is ObjectStatus.ACTIVE and f2_state is ObjectStatus.ACTIVE
    record("P3 genuine partial retraction spares the dependent", ok,
           f"X={x_state.value} (F2 still {f2_state.value}), "
           f"reported partial={X.object_id in result.partially_retracted}")

    i6 = [v for v in IntegrityVerifier(store=store).verify().violations
          if v.constraint_id == "I6"]
    record("P3 no I6 breach for a legitimately spared dependent", not i6,
           f"{len(i6)} violation(s)")


# --------------------------------------------------------------------------
# Probe 4: total retraction of both roots must invalidate X.
# --------------------------------------------------------------------------
def probe_total_retraction_invalidates():
    store, alloc = KnowledgeStore(), IdentityAllocator()
    E1 = put(store, alloc, ObjectType.EVIDENCE, [])
    E2 = put(store, alloc, ObjectType.EVIDENCE, [])
    F1 = put(store, alloc, ObjectType.FACT, [E1])
    F2 = put(store, alloc, ObjectType.FACT, [E2])
    X = put(store, alloc, ObjectType.PROBLEM, [F1, F2])

    casc = CascadeInvalidation(store=store)
    casc.retract(E1.object_id, "first withdrew")
    casc.retract(E2.object_id, "second withdrew")

    x_state = store.find(X.object_id).status
    record("P4 total retraction invalidates the dependent",
           x_state is ObjectStatus.INVALIDATED, f"X={x_state.value}")

    i6 = [v for v in IntegrityVerifier(store=store).verify().violations
          if v.constraint_id == "I6"]
    record("P4 no I6 breach after total retraction", not i6, f"{len(i6)} violation(s)")


# --------------------------------------------------------------------------
# Probe 5: idempotence -- re-running cascade changes nothing further.
# --------------------------------------------------------------------------
def probe_idempotence():
    store, alloc = KnowledgeStore(), IdentityAllocator()
    E = put(store, alloc, ObjectType.EVIDENCE, [])
    F = put(store, alloc, ObjectType.FACT, [E])
    P = put(store, alloc, ObjectType.PROBLEM, [F])
    casc = CascadeInvalidation(store=store)
    r1 = casc.retract(E.object_id, "withdrawn")
    snap1 = {s.object_id: s.status for s in store}
    r2 = casc.cascade(E.object_id, ObjectStatus.RETRACTED, "withdrawn")
    snap2 = {s.object_id: s.status for s in store}
    record("P5 cascade is idempotent (no further change on re-run)",
           snap1 == snap2 and r2.changed == 0,
           f"second run changed={r2.changed}")


if __name__ == "__main__":
    print("=" * 78)
    print("T01.8.1 FINAL GATE -- adversarial probes on partial retraction")
    print("=" * 78)
    for fn in (probe_uneven_depth_diamond, probe_deep_skew,
               probe_genuine_partial_is_spared, probe_total_retraction_invalidates,
               probe_idempotence):
        print(f"\n-- {fn.__name__}")
        try:
            fn()
        except Exception as exc:  # fail closed
            record(fn.__name__, False, f"raised {type(exc).__name__}: {exc}")
    print("\n" + "=" * 78)
    print(f"PASSED {len(PASSES)}   FAILED {len(FAILURES)}")
    for f in FAILURES:
        print("  FAIL " + f)
    sys.exit(1 if FAILURES else 0)
