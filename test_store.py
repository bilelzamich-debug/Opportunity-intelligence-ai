"""Contract tests for the Knowledge Store write path.

Task: T01.1.4

Architecture References:
- N-6  Objects authoritative; atomic write; graph derived
- N-8  Store enforces acceptance
- N-10 Failed write produces a failure record
- I1   Content immutable after acceptance
- I2   object_id never reused
- I4   Hard delete unsupported
- I5   Exactly one ACTIVE version per lineage_id

Acceptance criteria under test:
  AC1  Content immutable after acceptance
  AC2  Write is atomic
  AC3  Partial writes impossible
  AC4  Hard delete unsupported
"""

from __future__ import annotations

import threading

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.enums import Engine, ObjectStatus, ObjectType
from oip.store import (
    ActiveVersionConflictError,
    DuplicateWriteError,
    HardDeleteError,
    ImmutabilityError,
    KnowledgeStore,
    ObjectNotFoundError,
    StoreError,
    WriteRejectedError,
)
from tests.conftest import (
    PARENT_OF,
    build_attrs,
    build_lineage,
    write_chain,
    write_derived,
    write_evidence,
)


# ---------------------------------------------------------------------------
# AC1 -- content immutable after acceptance
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_stored_content_cannot_be_mutated(self, store, allocator):
        stored = write_evidence(store, allocator)
        with pytest.raises(Exception):
            stored.attributes.engine_configuration_ref = "cfg-v2"

    def test_update_is_unsupported(self, store, allocator):
        stored = write_evidence(store, allocator)
        with pytest.raises(ImmutabilityError):
            store.update(stored.object_id, engine_configuration_ref="cfg-v2")

    def test_rewriting_same_object_id_rejected(self, store, allocator):
        stored = write_evidence(store, allocator)
        attrs = build_attrs(
            stored.attributes.identity,
            ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE,
            status_reason=None,
        )
        with pytest.raises(DuplicateWriteError):
            store.write(attrs, build_lineage(stored.object_id, ObjectType.EVIDENCE))

    def test_status_transition_preserves_content(self, store, allocator):
        stored = write_evidence(store, allocator)
        before = stored.attributes.confidence
        moved = store.transition(
            stored.object_id, ObjectStatus.ARCHIVED, "retention"
        )
        assert moved.attributes.confidence == before
        assert moved.attributes.identity == stored.attributes.identity
        assert moved.lineage == stored.lineage

    def test_read_returns_equal_content_each_time(self, store, allocator):
        stored = write_evidence(store, allocator)
        assert store.get(stored.object_id).attributes == stored.attributes


# ---------------------------------------------------------------------------
# AC2 / AC3 -- atomic write, no partial writes
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    def test_accepted_write_commits_object_and_lineage(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert store.contains(fact.object_id)
        assert store.graph.contains(fact.object_id)
        assert store.graph.parents(fact.object_id) == {evidence.object_id}

    def test_rejected_write_commits_nothing(self, store, allocator):
        """A rejected object must leave no trace in store or graph. [N-6]"""
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        attrs = build_attrs(
            identity,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
            engine=Engine.PATTERN_INTELLIGENCE,  # violates V7
        )
        lineage = build_lineage(
            identity.object_id,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
        )
        with pytest.raises(WriteRejectedError):
            store.write(attrs, lineage)

        assert not store.contains(identity.object_id)
        assert not store.graph.contains(identity.object_id)
        assert len(store) == 1

    def test_rejected_write_produces_failure_record(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        attrs = build_attrs(
            identity,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
            engine=Engine.RESEARCH,
        )
        lineage = build_lineage(
            identity.object_id,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
        )
        with pytest.raises(WriteRejectedError):
            store.write(attrs, lineage)
        assert len(store.failure_records) == 1
        assert "V7" in store.failure_records[0].rule_ids

    def test_try_write_returns_result_without_raising(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        attrs = build_attrs(
            identity,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
            engine=Engine.RESEARCH,
        )
        lineage = build_lineage(
            identity.object_id,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
        )
        result = store.try_write(attrs, lineage)
        assert not result.accepted
        assert not store.contains(identity.object_id)

    def test_lineage_attribute_mismatch_rejected(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        attrs = build_attrs(
            identity,
            ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
        )
        wrong = build_lineage("obj-other", ObjectType.FACT,
                              ((evidence.object_id, ObjectType.EVIDENCE),))
        with pytest.raises(StoreError):
            store.write(attrs, wrong)

    def test_lineage_reference_disagreement_rejected(self, store, allocator):
        e1 = write_evidence(store, allocator)
        e2 = write_evidence(store, allocator)
        identity = allocator.new_object()
        attrs = build_attrs(
            identity, ObjectType.FACT, ((e1.object_id, ObjectType.EVIDENCE),)
        )
        mismatched = build_lineage(
            identity.object_id, ObjectType.FACT,
            ((e2.object_id, ObjectType.EVIDENCE),),
        )
        with pytest.raises(StoreError):
            store.write(attrs, mismatched)

    def test_concurrent_writes_are_serialised(self, store, allocator):
        """N-11 permits concurrent upstream work; the store must stay sound."""
        evidence = write_evidence(store, allocator)
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            for _ in range(25):
                try:
                    write_derived(store, allocator, ObjectType.FACT, [evidence])
                except Exception as exc:  # pragma: no cover - failure path
                    with lock:
                        errors.append(exc)

        pool = [threading.Thread(target=worker) for _ in range(8)]
        for t in pool:
            t.start()
        for t in pool:
            t.join()

        assert not errors, errors[:3]
        assert len(store) == 201
        assert len(store.graph.descendants(evidence.object_id)) == 200


# ---------------------------------------------------------------------------
# AC4 -- hard delete unsupported
# ---------------------------------------------------------------------------

class TestNoHardDelete:
    def test_delete_raises(self, store, allocator):
        stored = write_evidence(store, allocator)
        with pytest.raises(HardDeleteError):
            store.delete(stored.object_id)

    def test_object_survives_archival(self, store, allocator):
        stored = write_evidence(store, allocator)
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.contains(stored.object_id)
        assert store.get(stored.object_id).status is ObjectStatus.ARCHIVED

    def test_referenced_object_never_removed(self, store, allocator):
        """I4: lineage must remain traversable after upstream retraction."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.contains(evidence.object_id)
        assert store.graph.parents(fact.object_id) == {evidence.object_id}


# ---------------------------------------------------------------------------
# I5 -- one ACTIVE version per lineage
# ---------------------------------------------------------------------------

class TestSingleActiveVersion:
    def test_active_version_tracked(self, store, allocator):
        stored = write_evidence(store, allocator)
        assert store.active_version_of(stored.lineage_id) == stored.object_id

    def test_transition_away_clears_active(self, store, allocator):
        stored = write_evidence(store, allocator)
        store.transition(stored.object_id, ObjectStatus.SUPERSEDED, "replaced")
        assert store.active_version_of(stored.lineage_id) is None

    def test_second_active_in_same_lineage_rejected(self, store, allocator):
        """I5: predecessor still ACTIVE, so the successor must be refused."""
        first = write_evidence(store, allocator)
        successor = allocator.succeed(first.attributes.identity)
        attrs = build_attrs(
            successor,
            ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE,
            status_reason=None,
        )
        lineage = build_lineage(successor.object_id, ObjectType.EVIDENCE)
        with pytest.raises(ActiveVersionConflictError):
            store.write(attrs, lineage, predecessor_id=first.object_id)

    def test_unversioned_second_write_rejected_by_v11(self, store, allocator):
        """Without a declared predecessor, V11 requires version 1."""
        first = write_evidence(store, allocator)
        successor = allocator.succeed(first.attributes.identity)
        attrs = build_attrs(
            successor, ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(successor.object_id, ObjectType.EVIDENCE)
            )
        assert "V11" in exc.value.failure.rule_ids

    def test_conflict_rolls_back_completely(self, store, allocator):
        """A rejected commit must leave no partial state. [I5, atomicity]"""
        first = write_evidence(store, allocator)
        successor = allocator.succeed(first.attributes.identity)
        attrs = build_attrs(
            successor,
            ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE,
            status_reason=None,
        )
        lineage = build_lineage(successor.object_id, ObjectType.EVIDENCE)
        with pytest.raises(ActiveVersionConflictError):
            store.write(attrs, lineage, predecessor_id=first.object_id)

        assert not store.contains(successor.object_id)
        assert len(store.versions_of(first.lineage_id)) == 1
        # The graph must be untouched too: no orphan edge, no orphan node.
        assert not store.graph.contains(successor.object_id)
        assert store.graph_diverges() == ()

    def test_successor_active_after_predecessor_superseded(self, store, allocator):
        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        successor = allocator.succeed(first.attributes.identity)
        attrs = build_attrs(
            successor,
            ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE,
            status_reason=None,
        )
        stored = store.write(
            attrs, build_lineage(successor.object_id, ObjectType.EVIDENCE),
            predecessor_id=first.object_id,
        )
        assert store.active_version_of(first.lineage_id) == stored.object_id
        assert len(store.versions_of(first.lineage_id)) == 2

    def test_superseded_cannot_be_reactivated(self, store, allocator):
        """R-2: terminal states never transition, so I5 cannot be breached."""
        from oip.contract import ContractError

        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        with pytest.raises(ContractError):
            store.transition(first.object_id, ObjectStatus.ACTIVE, None)


# ---------------------------------------------------------------------------
# Reads and graph consistency
# ---------------------------------------------------------------------------

class TestReadsAndConsistency:
    def test_full_chain_persists(self, store, allocator):
        chain = write_chain(store, allocator)
        assert len(store) == 7
        for otype, stored in chain.items():
            assert store.contains(stored.object_id)
            assert store.resolve_type(stored.object_id) is otype

    def test_chain_reaches_evidence(self, store, allocator):
        chain = write_chain(store, allocator)
        validation = chain[ObjectType.VALIDATION]
        assert store.graph.reaches_evidence(validation.object_id)
        assert store.graph.evidence_set(validation.object_id) == {
            chain[ObjectType.EVIDENCE].object_id
        }

    def test_graph_rebuild_matches_incremental(self, store, allocator):
        chain = write_chain(store, allocator)
        before = {
            s.object_id: store.graph.parents(s.object_id) for s in chain.values()
        }
        store.rebuild_graph()
        after = {
            s.object_id: store.graph.parents(s.object_id) for s in chain.values()
        }
        assert before == after

    def test_graph_does_not_diverge(self, store, allocator):
        write_chain(store, allocator)
        assert store.graph_diverges() == ()

    def test_missing_object_raises(self, store):
        with pytest.raises(ObjectNotFoundError):
            store.get("obj-absent")
        assert store.find("obj-absent") is None

    def test_unknown_predecessor_raises(self, store, allocator):
        identity = allocator.new_object()
        attrs = build_attrs(identity, ObjectType.EVIDENCE)
        lineage = build_lineage(identity.object_id, ObjectType.EVIDENCE)
        with pytest.raises(ObjectNotFoundError):
            store.write(attrs, lineage, predecessor_id="obj-absent")

    def test_objects_of_type_filters(self, store, allocator):
        write_chain(store, allocator)
        assert len(store.objects_of_type(ObjectType.EVIDENCE)) == 1
        assert len(store.objects_of_type(ObjectType.FEEDBACK_RECORD)) == 0

    def test_active_objects_lists_all(self, store, allocator):
        write_chain(store, allocator)
        assert len(store.active_objects()) == 7

    def test_iteration_and_len(self, store, allocator):
        write_chain(store, allocator)
        assert len(list(store)) == len(store) == 7

    def test_transition_of_missing_object_raises(self, store):
        with pytest.raises(ObjectNotFoundError):
            store.transition("obj-absent", ObjectStatus.ARCHIVED, "x")


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=60, deadline=None)
@given(count=st.integers(min_value=1, max_value=25))
def test_every_written_object_is_retrievable(count):
    from oip.identity import IdentityAllocator

    store, allocator = KnowledgeStore(), IdentityAllocator()
    written = [write_evidence(store, allocator) for _ in range(count)]
    assert len(store) == count
    for stored in written:
        assert store.get(stored.object_id).attributes == stored.attributes


@settings(max_examples=40, deadline=None)
@given(depth=st.integers(min_value=1, max_value=6))
def test_chains_of_any_depth_reach_evidence(depth):
    from oip.identity import IdentityAllocator

    store, allocator = KnowledgeStore(), IdentityAllocator()
    ladder = [
        ObjectType.FACT, ObjectType.PROBLEM, ObjectType.PATTERN,
        ObjectType.OPPORTUNITY, ObjectType.SOLUTION, ObjectType.VALIDATION,
    ]
    current = write_evidence(store, allocator)
    evidence_id = current.object_id
    for i in range(depth):
        current = write_derived(store, allocator, ladder[i], [current])
    assert store.graph.evidence_set(current.object_id) == {evidence_id}


@settings(max_examples=40, deadline=None)
@given(fan=st.integers(min_value=1, max_value=12))
def test_rebuild_is_idempotent_for_any_shape(fan):
    from oip.identity import IdentityAllocator

    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    for _ in range(fan):
        write_derived(store, allocator, ObjectType.FACT, [evidence])

    store.rebuild_graph()
    first = store.graph.descendants(evidence.object_id)
    store.rebuild_graph()
    assert store.graph.descendants(evidence.object_id) == first
    assert store.graph_diverges() == ()


# ---------------------------------------------------------------------------
# Guards, try_write paths, and the V10 write-time cycle check
# ---------------------------------------------------------------------------

class TestStoreGuards:
    def test_try_write_precheck_still_raises(self, store, allocator):
        """Structural mismatches are programming errors, not rule failures."""
        stored = write_evidence(store, allocator)
        attrs = build_attrs(
            stored.attributes.identity, ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(DuplicateWriteError):
            store.try_write(
                attrs, build_lineage(stored.object_id, ObjectType.EVIDENCE)
            )

    def test_try_write_succeeds_and_commits(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        result = store.try_write(
            attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
        )
        assert result.accepted
        assert store.contains(identity.object_id)

    def test_lineage_type_mismatch_rejected(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(identity, ObjectType.FACT, upstream)
        wrong_type = build_lineage(identity.object_id, ObjectType.PROBLEM,
                                   ((evidence.object_id, ObjectType.EVIDENCE),))
        with pytest.raises(StoreError):
            store.write(attrs, wrong_type)

    def test_cycle_write_rejected_before_mutation(self, store, allocator):
        """V10 at the store layer: checked before any mutation. [N-6, V10]

        Objects rehydrated from storage bypass R-6 legality, so the store
        must not rely on the taxonomy alone.
        """
        from oip.store import CycleWriteError

        # Seed a graph-only edge a -> b (no stored objects yet).
        store.graph.index_lineage(
            build_lineage("obj-a", ObjectType.FACT,
                          (("obj-b", ObjectType.FACT),))
        )
        identity = allocator.new_object()
        upstream = (("obj-a", ObjectType.FACT),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        lineage = build_lineage(identity.object_id, ObjectType.FACT, upstream)
        object.__setattr__(lineage, "object_id", "obj-b")
        object.__setattr__(attrs, "identity", attrs.identity)

        # obj-b -> obj-a closes the loop with the seeded obj-a -> obj-b.
        assert store.graph.would_introduce_cycle("obj-b", "obj-a")
        with pytest.raises(CycleWriteError):
            store._commit(attrs, lineage)
        assert not store.contains("obj-b")

    def test_upstream_confidence_none_for_unknown(self, store):
        assert store._upstream_confidence("obj-absent") is None

    def test_transition_between_non_active_states(self, store, allocator):
        stored = write_evidence(store, allocator)
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.active_version_of(stored.lineage_id) is None
        assert store.get(stored.object_id).status is ObjectStatus.RETRACTED

    def test_transition_of_non_active_object_leaves_active_map_alone(
        self, store, allocator
    ):
        first = write_evidence(store, allocator)
        second = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.active_version_of(second.lineage_id) == second.object_id

    def test_versions_of_unknown_lineage_is_empty(self, store):
        assert store.versions_of("lin-absent") == ()

    def test_resolve_type_of_unknown_is_none(self, store):
        assert store.resolve_type("obj-absent") is None
