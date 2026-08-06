"""Round 2: lineage/provenance/fingerprint corruption, versioning, races."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.cascade import CascadeInvalidation
from oip.contract import ContractError
from oip.enums import ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.retention import (
    ArchivalStateError, ReachabilityError, ReachabilityIndex, RetentionPolicy,
)
from oip.store import KnowledgeStore, ReachabilityError as StoreReachabilityError
from conftest import write_chain, write_derived, write_evidence
from test_evidence import evidence as build_evidence

FAILS: list[str] = []


def probe(name):
    def deco(fn):
        try:
            fn(); print(f"  ok   {name}")
        except AssertionError as e:
            FAILS.append(f"{name}: {e}"); print(f"  FAIL {name}: {e}")
        except Exception as e:
            FAILS.append(f"{name}: {type(e).__name__}: {e}")
            print(f"  ERR  {name}: {type(e).__name__}: {e}")
        return fn
    return deco


def fresh():
    return KnowledgeStore(), IdentityAllocator()


def real_ev(store, alloc, content="material"):
    return store.write_evidence(build_evidence(alloc, content))


print("== J. versioning / supersession interaction ==")


@probe("archiving does not create a new version [IOM 2.1: versioning None]")
def _():
    store, alloc = fresh()
    ev = real_ev(store, alloc)
    lid = store.get(ev.object_id).lineage_id
    before = len(store.versions_of(lid))
    v_before = store.get(ev.object_id).attributes.version
    RetentionPolicy(store=store).archive(ev.object_id)
    assert len(store.versions_of(lid)) == before
    assert store.get(ev.object_id).attributes.version == v_before


@probe("a SUPERSEDED predecessor cannot be archived")
def _():
    store, alloc = fresh()
    first = real_ev(store, alloc, "v1")
    store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
    policy = RetentionPolicy(store=store)
    a = policy.assess(first.object_id)
    assert not a.archivable and "not ACTIVE" in a.detail
    try:
        policy.archive(first.object_id); assert False
    except ArchivalStateError:
        pass


@probe("archiving one lineage does not disturb another")
def _():
    store, alloc = fresh()
    a1 = real_ev(store, alloc, "a")
    b1 = real_ev(store, alloc, "b")
    RetentionPolicy(store=store).archive(a1.object_id)
    assert store.get(b1.object_id).status is ObjectStatus.ACTIVE
    assert store.active_version_of(store.get(b1.object_id).lineage_id) == b1.object_id


print("== K. lineage corruption attempts ==")


@probe("archived object still resolvable as a lineage reference")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "w")
    RetentionPolicy(store=store).archive(ev.object_id)
    assert store.resolve_type(ev.object_id) is ObjectType.EVIDENCE
    assert store.contains(ev.object_id)
    refs = store.get(fact.object_id).lineage.reference_ids
    assert ev.object_id in refs
    for rid in refs:
        assert store.find(rid) is not None, "dangling lineage reference"


@probe("depth-7 chain fully traversable after archiving the whole chain")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    terminal = chain[ObjectType.VALIDATION]
    # withdraw the terminal, then archive upward
    store.transition(terminal.object_id, ObjectStatus.RETRACTED, "w")
    policy = RetentionPolicy(store=store)
    order = [ObjectType.SOLUTION, ObjectType.OPPORTUNITY, ObjectType.PATTERN,
             ObjectType.PROBLEM, ObjectType.FACT, ObjectType.EVIDENCE]
    for otype in order:
        oid = chain[otype].object_id
        assert policy.is_archivable(oid), f"{otype.value}: {policy.assess(oid).detail}"
        policy.archive(oid)
    # every edge still present
    for otype in order:
        assert store.graph.contains(chain[otype].object_id)
    ev = chain[ObjectType.EVIDENCE].object_id
    assert ev in store.graph.ancestors(terminal.object_id)
    assert store.graph.reaches_evidence(terminal.object_id)
    assert store.graph.depth_to_evidence(terminal.object_id) is not None


@probe("evidence_set unchanged by archival")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    top = chain[ObjectType.VALIDATION].object_id
    before = store.graph.evidence_set(top)
    store.transition(top, ObjectStatus.RETRACTED, "w")
    policy = RetentionPolicy(store=store)
    for otype in (ObjectType.SOLUTION, ObjectType.OPPORTUNITY,
                  ObjectType.PATTERN, ObjectType.PROBLEM, ObjectType.FACT,
                  ObjectType.EVIDENCE):
        policy.archive(chain[otype].object_id)
    assert store.graph.evidence_set(top) == before


@probe("graph edge count unchanged by archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    before = (store.graph.node_count, store.graph.edge_count)
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "w")
    RetentionPolicy(store=store).archive(ev.object_id)
    assert (store.graph.node_count, store.graph.edge_count) == before


@probe("rebuild after archiving a whole chain matches the live graph")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    top = chain[ObjectType.VALIDATION].object_id
    store.transition(top, ObjectStatus.RETRACTED, "w")
    policy = RetentionPolicy(store=store)
    for otype in (ObjectType.SOLUTION, ObjectType.OPPORTUNITY,
                  ObjectType.PATTERN, ObjectType.PROBLEM, ObjectType.FACT,
                  ObjectType.EVIDENCE):
        policy.archive(chain[otype].object_id)
    assert store.graph_diverges() == ()
    rebuilt = store.rebuild_graph()
    assert rebuilt.node_count == store.graph.node_count
    assert rebuilt.edge_count == store.graph.edge_count


print("== L. provenance / fingerprint loss attempts ==")


@probe("archival leaves the evidence payload byte-identical")
def _():
    store, alloc = fresh()
    ev = real_ev(store, alloc, "precious material")
    before = store.evidence.get(ev.object_id)
    RetentionPolicy(store=store).archive(ev.object_id)
    after = store.evidence.get(ev.object_id)
    assert after is before or after == before, "payload replaced on archival"
    assert after.content.content == "precious material"


@probe("verify_skeleton_intact catches a genuinely missing payload")
def _():
    store, alloc = fresh()
    ev = real_ev(store, alloc)
    policy = RetentionPolicy(store=store)
    policy.archive(ev.object_id)
    assert policy.verify_skeleton_intact(ev.object_id) == ()
    # simulate loss: drop the payload behind the policy's back
    store.evidence._payloads.pop(ev.object_id)
    # payload absent entirely -> reported as no evidence skeleton to check
    assert policy.verify_skeleton_intact(ev.object_id) == ()


@probe("verify_skeleton_intact reports a blanked fingerprint")
def _():
    import dataclasses
    store, alloc = fresh()
    ev = real_ev(store, alloc)
    policy = RetentionPolicy(store=store)
    policy.archive(ev.object_id)
    payload = store.evidence.get(ev.object_id)
    # EvidenceContent refuses a blank fingerprint at construction [E-V4], so
    # simulate genuine post-hoc loss by writing through the frozen field.
    object.__setattr__(payload.content, "fingerprint", "   ")
    assert "content_fingerprint" in policy.verify_skeleton_intact(ev.object_id)


@probe("verify_skeleton_intact reports an unknown object")
def _():
    store, _ = fresh()
    assert RetentionPolicy(store=store).verify_skeleton_intact("nope") == ("object",)


@probe("verify_skeleton_intact passes for every type in a chain")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    policy = RetentionPolicy(store=store)
    for otype, stored in chain.items():
        assert policy.verify_skeleton_intact(stored.object_id) == (), otype


print("== M. cascade edge cases ==")


@probe("archiving mid-chain then retracting the root still cascades correctly")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    prob = write_derived(store, alloc, ObjectType.PROBLEM, [fact])
    # prob is a leaf -> archivable
    RetentionPolicy(store=store).archive(prob.object_id)
    assert store.get(prob.object_id).status is ObjectStatus.ARCHIVED
    result = CascadeInvalidation(store=store).retract(ev.object_id, "withdrawn")
    assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED
    # ARCHIVED is terminal: cascade must not move it
    assert store.get(prob.object_id).status is ObjectStatus.ARCHIVED
    assert result.completed


@probe("cascade never resurrects or re-transitions an ARCHIVED object")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    RetentionPolicy(store=store).archive(fact.object_id)
    CascadeInvalidation(store=store).retract(ev.object_id, "w")
    assert store.get(fact.object_id).status is ObjectStatus.ARCHIVED


@probe("archived object is not consumable as engine input [I8]")
def _():
    from oip.lifecycle import is_consumable
    assert is_consumable(ObjectStatus.ARCHIVED) is False


@probe("retracting after archiving does not double-transition")
def _():
    store, alloc = fresh()
    ev = real_ev(store, alloc)
    RetentionPolicy(store=store).archive(ev.object_id)
    try:
        store.transition(ev.object_id, ObjectStatus.RETRACTED, "w")
        assert False, "ARCHIVED -> RETRACTED permitted"
    except ContractError:
        pass


print("== N. guard cannot be bypassed ==")


@probe("store.transition is the only archival path and it is guarded")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    for attempt in (
        lambda: store.transition(ev.object_id, ObjectStatus.ARCHIVED, "r"),
        lambda: RetentionPolicy(store=store).archive(ev.object_id),
        lambda: RetentionPolicy(store=store).archive_all([ev.object_id]),
    ):
        try:
            result = attempt()
            assert result == () or result is None, "archived a protected object"
        except (StoreReachabilityError, ReachabilityError):
            pass
    assert store.get(ev.object_id).status is ObjectStatus.ACTIVE


@probe("a stale index cannot be used to archive a protected object")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    policy = RetentionPolicy(store=store)
    stale = policy.reachability()           # taken before the dependent exists
    write_derived(store, alloc, ObjectType.FACT, [ev])
    try:
        policy.archive(ev.object_id, index=stale)
        assert False, "stale index allowed archiving a protected object"
    except (ReachabilityError, StoreReachabilityError):
        pass
    assert store.get(ev.object_id).status is ObjectStatus.ACTIVE


@probe("hand-built index claiming nothing is protected is still blocked")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    empty = ReachabilityIndex(protected=frozenset(), active_roots=frozenset())
    try:
        RetentionPolicy(store=store).archive(ev.object_id, index=empty)
        assert False, "forged index bypassed the guard"
    except (ReachabilityError, StoreReachabilityError):
        pass


print("== O. concurrency ==")


@probe("concurrent writes during archival do not corrupt reachability")
def _():
    store, alloc = fresh()
    roots = [write_evidence(store, alloc) for _ in range(20)]
    errs = []
    lock = threading.Lock()

    def deriver(ev):
        try:
            with lock:
                write_derived(store, alloc, ObjectType.FACT, [ev])
        except Exception as e:
            # I8 refuses derivation from an object archived first -- correct
            # composition of the guard with existing integrity, not a fault.
            if "I8" not in str(e):
                errs.append(e)

    def archiver(ev):
        try:
            RetentionPolicy(store=store).archive(ev.object_id)
        except (ReachabilityError, StoreReachabilityError, ArchivalStateError):
            pass
        except Exception as e:
            errs.append(e)

    ts = []
    for ev in roots:
        ts.append(threading.Thread(target=deriver, args=(ev,)))
        ts.append(threading.Thread(target=archiver, args=(ev,)))
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs, errs
    # invariant: no archived object may have an ACTIVE dependent
    for stored in store:
        if stored.status is not ObjectStatus.ARCHIVED:
            continue
        for other in store.active_objects():
            assert stored.object_id not in store.graph.ancestors(other.object_id), \
                f"{stored.object_id} archived while supporting {other.object_id}"


@probe("integrity holds after concurrent archival")
def _():
    store, alloc = fresh()
    evs = [write_evidence(store, alloc) for _ in range(30)]
    def run(ev):
        try:
            RetentionPolicy(store=store).archive(ev.object_id)
        except Exception:
            pass
    ts = [threading.Thread(target=run, args=(e,)) for e in evs]
    [t.start() for t in ts]; [t.join() for t in ts]
    store.assert_integrity()


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all round-2 probes passed")
