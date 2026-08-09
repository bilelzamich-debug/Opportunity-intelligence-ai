"""Adversarial probe for T01.2.5 ARCHIVED tiering. Attack before testing."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.cascade import CASCADE_TRIGGERS, CascadeInvalidation
from oip.enums import ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.contract import ContractError
from oip.lifecycle import IllegalTransitionError, TerminalStateError
from oip.retention import (
    ArchivalStateError, ReachabilityError, ReachabilityIndex, RetentionError,
    RetentionPolicy,
)
from oip.store import KnowledgeStore, ReachabilityError as StoreReachabilityError
from conftest import PARENT_OF, write_chain, write_derived, write_evidence

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


def write_real_evidence(store, allocator, content="acquired material"):
    """Evidence WITH a registered payload, so fingerprint/provenance exist."""
    sys.path.insert(0, str(ROOT / "tests"))
    from test_evidence import evidence as build_evidence
    return store.write_evidence(build_evidence(allocator, content))


print("== A. reachable objects are never archived [AC1] ==")


@probe("evidence under an ACTIVE fact cannot be archived")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    try:
        store.transition(ev.object_id, ObjectStatus.ARCHIVED, "retention")
        assert False, "archived an object supporting ACTIVE knowledge"
    except StoreReachabilityError:
        pass
    assert store.get(ev.object_id).status is ObjectStatus.ACTIVE


@probe("deep ancestor protected through a full chain")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    ev = chain[ObjectType.EVIDENCE]
    try:
        store.transition(ev.object_id, ObjectStatus.ARCHIVED, "retention")
        assert False, "archived the root of a live chain"
    except StoreReachabilityError:
        pass


@probe("every intermediate in a depth-8 chain is protected")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    terminal = chain[ObjectType.VALIDATION].object_id
    blocked = 0
    for otype, stored in chain.items():
        if stored.object_id == terminal:
            continue
        try:
            store.transition(stored.object_id, ObjectStatus.ARCHIVED, "r")
            assert False, f"archived reachable {otype.value}"
        except StoreReachabilityError:
            blocked += 1
    assert blocked == len(chain) - 1, blocked


@probe("policy refuses the same archival with a reason")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    policy = RetentionPolicy(store=store)
    a = policy.assess(ev.object_id)
    assert not a.archivable
    assert "reachable" in a.detail.lower(), a.detail
    try:
        policy.archive(ev.object_id)
        assert False
    except ReachabilityError:
        pass


@probe("unreachable object IS archivable once its dependent is withdrawn")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
    policy = RetentionPolicy(store=store)
    assert policy.is_archivable(ev.object_id), policy.assess(ev.object_id).detail
    policy.archive(ev.object_id)
    assert store.get(ev.object_id).status is ObjectStatus.ARCHIVED


@probe("a lone ACTIVE evidence with no dependents is archivable")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    RetentionPolicy(store=store).archive(ev.object_id)
    assert store.get(ev.object_id).status is ObjectStatus.ARCHIVED


@probe("protection is re-evaluated: archiving frees its ancestors")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    policy = RetentionPolicy(store=store)
    assert not policy.is_archivable(ev.object_id)
    policy.archive(fact.object_id)          # fact has no dependents
    assert policy.is_archivable(ev.object_id), "stale reachability snapshot"


@probe("archive_all re-evaluates per object, not once up front")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    done = RetentionPolicy(store=store).archive_all(
        [fact.object_id, ev.object_id])
    assert set(done) == {fact.object_id, ev.object_id}, done


@probe("archive_all skips protected objects without aborting")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    lone = write_evidence(store, alloc)
    done = RetentionPolicy(store=store).archive_all([ev.object_id, lone.object_id])
    assert done == (lone.object_id,), done


print("== B. illegal ARCHIVED transitions [IOM 2.1] ==")


@probe("no terminal state may transition to ARCHIVED")
def _():
    for terminal in (ObjectStatus.SUPERSEDED, ObjectStatus.REJECTED,
                     ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED,
                     ObjectStatus.ARCHIVED):
        store, alloc = fresh()
        ev = write_evidence(store, alloc)
        if terminal is ObjectStatus.INVALIDATED:
            continue          # unreachable for Evidence [E-V1]
        store.transition(ev.object_id, terminal, "reason")
        try:
            store.transition(ev.object_id, ObjectStatus.ARCHIVED, "retention")
            assert False, f"{terminal.value} -> ARCHIVED permitted"
        except (TerminalStateError, IllegalTransitionError, ContractError):
            pass


@probe("PROPOSED cannot go straight to ARCHIVED [IOM 2.1]")
def _():
    from oip.lifecycle import can_transition
    for src in (ObjectStatus.PROPOSED, ObjectStatus.SUPERSEDED,
                ObjectStatus.REJECTED, ObjectStatus.RETRACTED,
                ObjectStatus.INVALIDATED, ObjectStatus.ARCHIVED):
        assert not can_transition(
            ObjectType.EVIDENCE, src, ObjectStatus.ARCHIVED), src
    assert can_transition(
        ObjectType.EVIDENCE, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED)


@probe("policy refuses a non-ACTIVE source with the right error")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    store.transition(ev.object_id, ObjectStatus.RETRACTED, "withdrawn")
    policy = RetentionPolicy(store=store)
    a = policy.assess(ev.object_id)
    assert not a.archivable and "not ACTIVE" in a.detail
    try:
        policy.archive(ev.object_id); assert False
    except ArchivalStateError:
        pass


@probe("ARCHIVED is terminal: cannot leave it")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    store.transition(ev.object_id, ObjectStatus.ARCHIVED, "retention")
    for target in ObjectStatus:
        if target is ObjectStatus.ARCHIVED:
            continue
        try:
            store.transition(ev.object_id, target, "x")
            assert False, f"ARCHIVED -> {target.value} permitted"
        except (TerminalStateError, IllegalTransitionError, ContractError):
            pass


print("== C. cascade semantics unchanged [N-9, M-65] ==")


@probe("CASCADE_TRIGGERS unchanged")
def _():
    assert CASCADE_TRIGGERS == frozenset(
        {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED})


@probe("archiving never cascades")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
    RetentionPolicy(store=store).archive(ev.object_id)
    result = CascadeInvalidation(store=store).cascade(ev.object_id)
    assert result.changed == 0
    assert store.get(fact.object_id).status is ObjectStatus.RETRACTED


@probe("retraction still cascades normally")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    CascadeInvalidation(store=store).retract(ev.object_id, "withdrawn")
    assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED


@probe("cascade-invalidated dependents free their ancestor for archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    prob = write_derived(store, alloc, ObjectType.PROBLEM, [fact])
    CascadeInvalidation(store=store).retract(fact.object_id, "withdrawn")
    assert store.get(prob.object_id).status is ObjectStatus.INVALIDATED
    assert RetentionPolicy(store=store).is_archivable(ev.object_id)


print("== D. skeleton, provenance, fingerprint, traversal [AC2, AC3] ==")


@probe("traversal still works after archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
    policy = RetentionPolicy(store=store)
    policy.archive(ev.object_id)
    assert policy.traversal_intact(ev.object_id)
    assert store.graph.contains(ev.object_id)
    assert ev.object_id in store.graph.ancestors(fact.object_id)
    assert store.graph.reaches_evidence(fact.object_id)


@probe("path to evidence survives archival of the evidence")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "w")
    RetentionPolicy(store=store).archive(ev.object_id)
    path = store.graph.path_to_evidence(fact.object_id)
    assert path is not None and ev.object_id in list(path)


@probe("skeleton intact after archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    policy = RetentionPolicy(store=store)
    policy.archive(ev.object_id)
    assert policy.verify_skeleton_intact(ev.object_id) == ()


@probe("fingerprint and provenance retained permanently [N-15]")
def _():
    store, alloc = fresh()
    stored = write_real_evidence(store, alloc)
    before = store.evidence.get(stored.object_id)
    assert before is not None, "payload not registered by the probe builder"
    fp, src = before.content.fingerprint, before.provenance.source_identifier
    policy = RetentionPolicy(store=store)
    policy.archive(stored.object_id)
    after = store.evidence.get(stored.object_id)
    assert after is not None, "evidence payload lost on archival"
    assert after.content.fingerprint == fp
    assert after.provenance.source_identifier == src
    assert policy.verify_skeleton_intact(stored.object_id) == ()


@probe("no content evicted")
def _():
    store, alloc = fresh()
    stored = write_real_evidence(store, alloc)
    before = store.evidence.get(stored.object_id).content.content
    policy = RetentionPolicy(store=store)
    policy.archive(stored.object_id)
    assert store.evidence.get(stored.object_id).content.content == before
    assert policy.content_eviction_performed is False
    assert policy.performs_hard_deletion is False


@probe("archival does not hard-delete [I4]")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    n = len(store)
    RetentionPolicy(store=store).archive(ev.object_id)
    assert len(store) == n
    assert store.find(ev.object_id) is not None


@probe("lineage references survive archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    refs_before = store.get(fact.object_id).lineage.reference_ids
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "w")
    RetentionPolicy(store=store).archive(ev.object_id)
    assert store.get(fact.object_id).lineage.reference_ids == refs_before


@probe("identity/type/version/lineage_id unchanged by archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    b = store.get(ev.object_id).attributes
    snapshot = (b.object_id, b.object_type, b.version, b.lineage_id,
                b.produced_by_engine, b.engine_configuration_ref)
    RetentionPolicy(store=store).archive(ev.object_id)
    a = store.get(ev.object_id).attributes
    assert (a.object_id, a.object_type, a.version, a.lineage_id,
            a.produced_by_engine, a.engine_configuration_ref) == snapshot


@probe("status_reason recorded on archival [V9]")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    RetentionPolicy(store=store).archive(ev.object_id)
    assert (store.get(ev.object_id).attributes.status_reason or "").strip()


@probe("graph rebuild still reproduces the archived object")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "w")
    RetentionPolicy(store=store).archive(ev.object_id)
    rebuilt = store.rebuild_graph()
    assert rebuilt.contains(ev.object_id)
    assert ev.object_id in rebuilt.ancestors(fact.object_id)
    assert store.graph_diverges() == ()


@probe("integrity clean after archival")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    store.transition(fact.object_id, ObjectStatus.RETRACTED, "w")
    RetentionPolicy(store=store).archive(ev.object_id)
    store.assert_integrity()


print("== E. I5 / active-set integrity ==")


@probe("archiving clears the ACTIVE slot for its lineage")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    lid = store.get(ev.object_id).lineage_id
    assert store.active_version_of(lid) == ev.object_id
    RetentionPolicy(store=store).archive(ev.object_id)
    assert store.active_version_of(lid) is None


@probe("archived object no longer counted ACTIVE")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    RetentionPolicy(store=store).archive(ev.object_id)
    assert ev.object_id not in {s.object_id for s in store.active_objects()}


@probe("an already-ARCHIVED object is not archivable again")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    policy = RetentionPolicy(store=store)
    assert policy.assess(ev.object_id).archivable
    policy.archive(ev.object_id)
    assert policy.assess(ev.object_id).archivable is False


print("== F. reachability index ==")


@probe("index contains ACTIVE roots and their ancestors")
def _():
    store, alloc = fresh()
    chain = write_chain(store, alloc)
    idx = RetentionPolicy(store=store).reachability()
    for stored in chain.values():
        assert idx.is_reachable(stored.object_id), stored.object_type


@probe("index is a frozen snapshot")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    idx = RetentionPolicy(store=store).reachability()
    n = len(idx)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    assert len(idx) == n, "snapshot mutated"
    try:
        idx.protected = frozenset()
        assert False, "mutable"
    except Exception:
        pass


@probe("empty store yields an empty index and no candidates")
def _():
    store = KnowledgeStore()
    policy = RetentionPolicy(store=store)
    assert len(policy.reachability()) == 0
    assert policy.candidates() == ()


@probe("candidates excludes supported objects, includes leaves")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    fact = write_derived(store, alloc, ObjectType.FACT, [ev])
    lone = write_evidence(store, alloc)
    ids = {c.object_id for c in RetentionPolicy(store=store).candidates()}
    # ev supports an ACTIVE Fact -> protected. The Fact is a leaf and `lone`
    # has no dependents, so N-12 protects neither.
    assert ev.object_id not in ids, "a supporting object was listed"
    assert ids == {fact.object_id, lone.object_id}, ids


print("== G. fail closed ==")


@probe("no graph available -> refuses rather than guessing")
def _():
    class NoGraph:
        graph = None
        def active_objects(self): return ()
    try:
        RetentionPolicy(store=NoGraph()).reachability()
        assert False, "proceeded without traversal"
    except RetentionError:
        pass


@probe("policy invents no scheduling or GC vocabulary")
def _():
    # Prefix match: a name STARTING with a verb would be a capability.
    # content_eviction_performed is a report that eviction did not happen.
    banned = ("schedule", "collect", "gc_", "expire", "evict", "purge",
              "delete", "prune", "sweep")
    names = [n for n in dir(RetentionPolicy) if not n.startswith("_")]
    hits = [n for n in names if n.lower().startswith(banned)]
    assert hits == [], hits
    assert RetentionPolicy(store=KnowledgeStore()).content_eviction_performed is False


@probe("module mentions no age-based heuristic")
def _():
    src = (ROOT / "oip" / "retention.py").read_text().lower()
    for banned in ("days", "ttl", "expire", "older than", "timedelta"):
        assert banned not in src, banned


@probe("unspecified content tiering is reported, not guessed")
def _():
    policy = RetentionPolicy(store=KnowledgeStore())
    assert policy.content_tiering_specified is False
    assert policy.content_eviction_performed is False


print("== H. concurrency ==")


@probe("concurrent archival attempts on a protected object all refused")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    write_derived(store, alloc, ObjectType.FACT, [ev])
    refused, wrong = [], []

    def run():
        try:
            store.transition(ev.object_id, ObjectStatus.ARCHIVED, "r")
            wrong.append(1)
        except StoreReachabilityError:
            refused.append(1)

    ts = [threading.Thread(target=run) for _ in range(12)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not wrong, "a protected object was archived under contention"
    assert len(refused) == 12


@probe("concurrent archival of a lone object: exactly one succeeds")
def _():
    store, alloc = fresh()
    ev = write_evidence(store, alloc)
    ok, refused = [], []

    def run():
        try:
            store.transition(ev.object_id, ObjectStatus.ARCHIVED, "r")
            ok.append(1)
        except Exception:
            refused.append(1)

    ts = [threading.Thread(target=run) for _ in range(8)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(ok) == 1, f"{len(ok)} archivals succeeded"
    assert store.get(ev.object_id).status is ObjectStatus.ARCHIVED


print("== I. scale ==")


@probe("500 evidence, 250 protected, exact")
def _():
    store, alloc = fresh()
    protected, lone = [], []
    for n in range(250):
        ev = write_evidence(store, alloc)
        write_derived(store, alloc, ObjectType.FACT, [ev])
        protected.append(ev.object_id)
    for n in range(250):
        lone.append(write_evidence(store, alloc).object_id)
    policy = RetentionPolicy(store=store)
    ids = {c.object_id for c in policy.candidates()}
    assert not (set(protected) & ids), "a supporting Evidence was listed"
    assert set(lone) <= ids
    done = policy.archive_all(protected)
    assert done == (), "archived Evidence supporting ACTIVE Facts"
    for pid in protected:
        assert store.get(pid).status is ObjectStatus.ACTIVE


print()
if FAILS:
    print(f"{len(FAILS)} PROBE FAILURES")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("all probes passed")
