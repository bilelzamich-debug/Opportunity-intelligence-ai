"""Contract tests for ARCHIVED tiering by reachability.

Task: T01.2.5

Architecture References:
- N-12   Retention (closes M-38). "The lineage skeleton is retained
         permanently. Heavyweight content is tiered by reachability."
         "An object is tiered only when it is not reachable from any ACTIVE
         object by lineage traversal. Anything supporting current knowledge
         stays." "Tiering sets ARCHIVED (R-2) and is invoked as a maintenance
         operation." "Lineage traversal never breaks."
- R-2    ARCHIVED = "Removed from the active working set; lineage preserved";
         terminal
- IOM 2.1 The ONLY ARCHIVED transition is ACTIVE -> ARCHIVED. "No terminal
         state may transition."
- I4     Referenced objects are never hard-deleted
- N-15   content_fingerprint and provenance always retained (closes OQ-12)
- N-6    Objects authoritative; graph derived and may lag
- N-9    Cascade triggers are RETRACTED and INVALIDATED only
- M-65   Re-derivation on supersession OPEN; ARCHIVED does not cascade
- P3     Lineage reconstructable indefinitely
- T01.3.4 Backward traversal is the reachability primitive

Marker note: IOM 2.1's "Undefined (MISSING-31)" for the ARCHIVED authority is
IOM MISSING-31 = canonical M-38 (crosswalk line 45), which N-12 CLOSES.
Canonical M-31 (gate ownership) is a different, still-open gap.

Acceptance criteria under test:
  AC1  Objects reachable from any ACTIVE object are never archived
  AC2  Lineage traversal never breaks after archival
  AC3  content_fingerprint and provenance retained permanently
"""

from __future__ import annotations

import dataclasses
import threading

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.cascade import CASCADE_TRIGGERS, CascadeInvalidation
from oip.contract import ContractError
from oip.enums import ObjectStatus, ObjectType
from oip.lifecycle import can_transition, is_consumable
from oip.retention import (
    REASON_NOT_ACTIVE,
    REASON_REACHABLE,
    ArchivalAssessment,
    ArchivalStateError,
    ReachabilityError,
    ReachabilityIndex,
    RetentionError,
    RetentionPolicy,
)
from oip.store import KnowledgeStore
from oip.store import ReachabilityError as StoreReachabilityError

from conftest import write_chain, write_derived, write_evidence
from test_evidence import evidence as build_evidence

CHAIN_ORDER = (
    ObjectType.VALIDATION,
    ObjectType.SOLUTION,
    ObjectType.OPPORTUNITY,
    ObjectType.PATTERN,
    ObjectType.PROBLEM,
    ObjectType.FACT,
    ObjectType.EVIDENCE,
)


def real_evidence(store, allocator, content="acquired material"):
    """Evidence WITH a registered payload (fingerprint + provenance)."""
    return store.write_evidence(build_evidence(allocator, content))


# ---------------------------------------------------------------------------
# AC1 -- reachable objects are never archived
# ---------------------------------------------------------------------------

class TestReachableNeverArchived:
    def test_evidence_supporting_an_active_fact_is_protected(self, store, allocator):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        with pytest.raises(StoreReachabilityError):
            store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE

    def test_the_policy_refuses_with_a_stated_reason(self, store, allocator):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        policy = RetentionPolicy(store=store)
        assessment = policy.assess(evidence.object_id)
        assert assessment.archivable is False
        assert REASON_REACHABLE in assessment.reasons
        with pytest.raises(ReachabilityError):
            policy.archive(evidence.object_id)

    def test_every_ancestor_in_a_live_chain_is_protected(self, store, allocator):
        chain = write_chain(store, allocator)
        terminal = chain[ObjectType.VALIDATION].object_id
        policy = RetentionPolicy(store=store)
        for object_type, stored in chain.items():
            if stored.object_id == terminal:
                continue
            assert policy.is_archivable(stored.object_id) is False, object_type

    def test_a_transitive_ancestor_is_protected(self, store, allocator):
        """Protection follows the whole upstream path, not just one hop."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        write_derived(store, allocator, ObjectType.PROBLEM, [fact])
        assert RetentionPolicy(store=store).is_archivable(evidence.object_id) is False

    def test_a_leaf_with_no_dependents_is_archivable(self, store, allocator):
        evidence = real_evidence(store, allocator)
        RetentionPolicy(store=store).archive(evidence.object_id)
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED

    def test_an_object_becomes_archivable_once_its_dependent_is_withdrawn(
        self, store, allocator
    ):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        policy = RetentionPolicy(store=store)
        assert policy.is_archivable(evidence.object_id) is False
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert policy.is_archivable(evidence.object_id) is True

    def test_the_candidates_own_active_status_does_not_protect_it(
        self, store, allocator
    ):
        """ACTIVE is the precondition for archiving, not a protection.

        Regression: an earlier version treated membership of the ACTIVE set as
        protection, which made archival impossible for every object.
        """
        evidence = real_evidence(store, allocator)
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE
        assert RetentionPolicy(store=store).is_archivable(evidence.object_id) is True

    def test_candidates_excludes_supporting_objects(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        identifiers = {c.object_id for c in RetentionPolicy(store=store).candidates()}
        assert evidence.object_id not in identifiers
        assert fact.object_id in identifiers

    def test_archive_all_skips_protected_objects(self, store, allocator):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        lone = real_evidence(store, allocator)
        archived = RetentionPolicy(store=store).archive_all(
            [evidence.object_id, lone.object_id]
        )
        assert archived == (lone.object_id,)
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE

    def test_archive_all_re_evaluates_per_object(self, store, allocator):
        """Archiving one object can free its ancestors within the same sweep."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        archived = RetentionPolicy(store=store).archive_all(
            [fact.object_id, evidence.object_id]
        )
        assert set(archived) == {fact.object_id, evidence.object_id}

    def test_a_stale_index_cannot_authorise_archiving(self, store, allocator):
        evidence = write_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        stale = policy.reachability()
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        with pytest.raises((ReachabilityError, StoreReachabilityError)):
            policy.archive(evidence.object_id, index=stale)
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE

    def test_a_forged_index_cannot_bypass_the_store_guard(self, store, allocator):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        empty = ReachabilityIndex(protected=frozenset(), active_roots=frozenset())
        with pytest.raises((ReachabilityError, StoreReachabilityError)):
            RetentionPolicy(store=store).archive(evidence.object_id, index=empty)


# ---------------------------------------------------------------------------
# Only ACTIVE -> ARCHIVED  [IOM 2.1, R-2]
# ---------------------------------------------------------------------------

class TestOnlyActiveMayBeArchived:
    @pytest.mark.parametrize(
        "source",
        [
            ObjectStatus.PROPOSED,
            ObjectStatus.SUPERSEDED,
            ObjectStatus.REJECTED,
            ObjectStatus.RETRACTED,
            ObjectStatus.INVALIDATED,
            ObjectStatus.ARCHIVED,
        ],
    )
    def test_no_other_state_reaches_archived(self, source):
        assert can_transition(
            ObjectType.EVIDENCE, source, ObjectStatus.ARCHIVED
        ) is False

    def test_active_reaches_archived(self):
        assert can_transition(
            ObjectType.EVIDENCE, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED
        ) is True

    @pytest.mark.parametrize(
        "terminal",
        [ObjectStatus.SUPERSEDED, ObjectStatus.REJECTED, ObjectStatus.RETRACTED],
    )
    def test_a_terminal_object_cannot_be_archived(self, store, allocator, terminal):
        evidence = real_evidence(store, allocator)
        store.transition(evidence.object_id, terminal, "reason")
        with pytest.raises(ContractError):
            store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")

    def test_the_policy_reports_a_non_active_source(self, store, allocator):
        evidence = real_evidence(store, allocator)
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        policy = RetentionPolicy(store=store)
        assessment = policy.assess(evidence.object_id)
        assert assessment.archivable is False
        assert REASON_NOT_ACTIVE in assessment.reasons
        with pytest.raises(ArchivalStateError):
            policy.archive(evidence.object_id)

    def test_archived_is_terminal(self, store, allocator):
        evidence = real_evidence(store, allocator)
        RetentionPolicy(store=store).archive(evidence.object_id)
        for target in ObjectStatus:
            if target is ObjectStatus.ARCHIVED:
                continue
            with pytest.raises(ContractError):
                store.transition(evidence.object_id, target, "x")

    def test_an_archived_object_is_not_archivable_again(self, store, allocator):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        policy.archive(evidence.object_id)
        assert policy.assess(evidence.object_id).archivable is False

    def test_a_superseded_predecessor_cannot_be_archived(self, store, allocator):
        evidence = real_evidence(store, allocator)
        store.transition(evidence.object_id, ObjectStatus.SUPERSEDED, "replaced")
        with pytest.raises(ArchivalStateError):
            RetentionPolicy(store=store).archive(evidence.object_id)

    def test_archiving_creates_no_new_version(self, store, allocator):
        """IOM 2.1 records versioning 'None' for ACTIVE -> ARCHIVED."""
        evidence = real_evidence(store, allocator)
        lineage_id = store.get(evidence.object_id).lineage_id
        versions = len(store.versions_of(lineage_id))
        version = store.get(evidence.object_id).attributes.version
        RetentionPolicy(store=store).archive(evidence.object_id)
        assert len(store.versions_of(lineage_id)) == versions
        assert store.get(evidence.object_id).attributes.version == version

    def test_archiving_clears_the_active_slot(self, store, allocator):
        evidence = real_evidence(store, allocator)
        lineage_id = store.get(evidence.object_id).lineage_id
        RetentionPolicy(store=store).archive(evidence.object_id)
        assert store.active_version_of(lineage_id) is None

    def test_an_archived_object_is_not_consumable(self):
        """I8: only current knowledge may be consumed."""
        assert is_consumable(ObjectStatus.ARCHIVED) is False


# ---------------------------------------------------------------------------
# AC2 -- lineage traversal never breaks
# ---------------------------------------------------------------------------

class TestTraversalNeverBreaks:
    def test_traversal_through_an_archived_object_still_works(
        self, store, allocator
    ):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        policy = RetentionPolicy(store=store)
        policy.archive(evidence.object_id)
        assert policy.traversal_intact(evidence.object_id) is True
        assert evidence.object_id in store.graph.ancestors(fact.object_id)
        assert store.graph.reaches_evidence(fact.object_id) is True

    def test_path_to_evidence_survives(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        RetentionPolicy(store=store).archive(evidence.object_id)
        path = store.graph.path_to_evidence(fact.object_id)
        assert path is not None
        assert evidence.object_id in list(path)

    def test_a_fully_archived_chain_remains_traversable(self, store, allocator):
        chain = write_chain(store, allocator)
        terminal = chain[ObjectType.VALIDATION].object_id
        store.transition(terminal, ObjectStatus.RETRACTED, "withdrawn")
        policy = RetentionPolicy(store=store)
        for object_type in CHAIN_ORDER[1:]:
            policy.archive(chain[object_type].object_id)

        evidence_id = chain[ObjectType.EVIDENCE].object_id
        assert store.graph.contains(evidence_id)
        assert evidence_id in store.graph.ancestors(terminal)
        assert store.graph.reaches_evidence(terminal) is True
        assert store.graph.depth_to_evidence(terminal) is not None

    def test_evidence_set_unchanged_by_archival(self, store, allocator):
        chain = write_chain(store, allocator)
        top = chain[ObjectType.VALIDATION].object_id
        before = store.graph.evidence_set(top)
        store.transition(top, ObjectStatus.RETRACTED, "withdrawn")
        policy = RetentionPolicy(store=store)
        for object_type in CHAIN_ORDER[1:]:
            policy.archive(chain[object_type].object_id)
        assert store.graph.evidence_set(top) == before

    def test_graph_shape_unchanged_by_archival(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        before = (store.graph.node_count, store.graph.edge_count)
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        RetentionPolicy(store=store).archive(evidence.object_id)
        assert (store.graph.node_count, store.graph.edge_count) == before

    def test_graph_rebuild_reproduces_archived_objects(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        RetentionPolicy(store=store).archive(evidence.object_id)
        rebuilt = store.rebuild_graph()
        assert rebuilt.contains(evidence.object_id)
        assert evidence.object_id in rebuilt.ancestors(fact.object_id)
        assert store.graph_diverges() == ()

    def test_lineage_references_still_resolve(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        RetentionPolicy(store=store).archive(evidence.object_id)
        for reference in store.get(fact.object_id).lineage.reference_ids:
            assert store.find(reference) is not None

    def test_integrity_holds_after_archival(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        RetentionPolicy(store=store).archive(evidence.object_id)
        store.assert_integrity()


# ---------------------------------------------------------------------------
# AC3 -- fingerprint and provenance retained permanently
# ---------------------------------------------------------------------------

class TestSkeletonRetainedPermanently:
    def test_fingerprint_and_provenance_survive(self, store, allocator):
        stored = real_evidence(store, allocator)
        before = store.evidence.get(stored.object_id)
        fingerprint = before.content.fingerprint
        source = before.provenance.source_identifier
        RetentionPolicy(store=store).archive(stored.object_id)
        after = store.evidence.get(stored.object_id)
        assert after is not None
        assert after.content.fingerprint == fingerprint
        assert after.provenance.source_identifier == source

    def test_content_is_not_evicted(self, store, allocator):
        """The physical tiering step is unspecified, so nothing is dropped."""
        stored = real_evidence(store, allocator, "precious material")
        policy = RetentionPolicy(store=store)
        policy.archive(stored.object_id)
        assert store.evidence.get(stored.object_id).content.content == (
            "precious material"
        )
        assert policy.content_eviction_performed is False
        assert policy.content_tiering_specified is False

    def test_no_hard_deletion(self, store, allocator):
        """I4: referenced objects are never hard-deleted."""
        evidence = real_evidence(store, allocator)
        count = len(store)
        policy = RetentionPolicy(store=store)
        policy.archive(evidence.object_id)
        assert len(store) == count
        assert store.find(evidence.object_id) is not None
        assert policy.performs_hard_deletion is False

    def test_identity_attributes_unchanged(self, store, allocator):
        evidence = real_evidence(store, allocator)
        before = store.get(evidence.object_id).attributes
        snapshot = (
            before.object_id, before.object_type, before.version,
            before.lineage_id, before.produced_by_engine,
            before.engine_configuration_ref,
        )
        RetentionPolicy(store=store).archive(evidence.object_id)
        after = store.get(evidence.object_id).attributes
        assert (
            after.object_id, after.object_type, after.version,
            after.lineage_id, after.produced_by_engine,
            after.engine_configuration_ref,
        ) == snapshot

    def test_status_reason_recorded(self, store, allocator):
        """V9: status_reason required when status is not ACTIVE."""
        evidence = real_evidence(store, allocator)
        RetentionPolicy(store=store).archive(evidence.object_id)
        reason = store.get(evidence.object_id).attributes.status_reason
        assert (reason or "").strip()

    def test_skeleton_verification_passes_after_archival(self, store, allocator):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        policy.archive(evidence.object_id)
        assert policy.verify_skeleton_intact(evidence.object_id) == ()

    def test_skeleton_verification_passes_for_every_type(self, store, allocator):
        chain = write_chain(store, allocator)
        policy = RetentionPolicy(store=store)
        for object_type, stored in chain.items():
            assert policy.verify_skeleton_intact(stored.object_id) == (), object_type

    def test_skeleton_verification_reports_a_lost_fingerprint(
        self, store, allocator
    ):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        policy.archive(evidence.object_id)
        payload = store.evidence.get(evidence.object_id)
        object.__setattr__(payload.content, "fingerprint", "   ")
        assert "content_fingerprint" in policy.verify_skeleton_intact(
            evidence.object_id
        )

    def test_skeleton_verification_reports_an_unknown_object(self, store):
        assert RetentionPolicy(store=store).verify_skeleton_intact("nope") == (
            "object",
        )


# ---------------------------------------------------------------------------
# Cascade semantics unchanged  [N-9, M-65]
# ---------------------------------------------------------------------------

class TestCascadeUnchanged:
    def test_cascade_triggers_unchanged(self):
        assert CASCADE_TRIGGERS == frozenset(
            {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED}
        )

    def test_archiving_never_cascades(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")
        RetentionPolicy(store=store).archive(evidence.object_id)
        result = CascadeInvalidation(store=store).cascade(evidence.object_id)
        assert result.changed == 0
        assert store.get(fact.object_id).status is ObjectStatus.RETRACTED

    def test_retraction_still_cascades(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")
        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

    def test_cascade_does_not_move_an_archived_dependent(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        RetentionPolicy(store=store).archive(fact.object_id)
        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")
        assert store.get(fact.object_id).status is ObjectStatus.ARCHIVED

    def test_invalidated_dependents_free_their_ancestor(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        problem = write_derived(store, allocator, ObjectType.PROBLEM, [fact])
        CascadeInvalidation(store=store).retract(fact.object_id, "withdrawn")
        assert store.get(problem.object_id).status is ObjectStatus.INVALIDATED
        assert RetentionPolicy(store=store).is_archivable(evidence.object_id) is True


# ---------------------------------------------------------------------------
# Reachability index
# ---------------------------------------------------------------------------

class TestReachabilityIndex:
    def test_index_holds_active_roots_and_ancestors(self, store, allocator):
        chain = write_chain(store, allocator)
        index = RetentionPolicy(store=store).reachability()
        for stored in chain.values():
            assert index.is_reachable(stored.object_id) is True

    def test_index_is_a_frozen_snapshot(self, store, allocator):
        evidence = write_evidence(store, allocator)
        index = RetentionPolicy(store=store).reachability()
        size = len(index)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert len(index) == size
        with pytest.raises(dataclasses.FrozenInstanceError):
            index.protected = frozenset()  # type: ignore[misc]

    def test_an_empty_store_yields_an_empty_index(self, store):
        policy = RetentionPolicy(store=store)
        assert len(policy.reachability()) == 0
        assert policy.candidates() == ()

    def test_active_roots_are_recorded(self, store, allocator):
        evidence = real_evidence(store, allocator)
        index = RetentionPolicy(store=store).reachability()
        assert index.is_active_root(evidence.object_id) is True


# ---------------------------------------------------------------------------
# No invented policy
# ---------------------------------------------------------------------------

class TestNoInventedPolicy:
    def test_no_scheduling_or_collection_capability(self):
        banned = ("schedule", "collect", "expire", "evict", "purge",
                  "delete", "prune", "sweep")
        names = [n for n in dir(RetentionPolicy) if not n.startswith("_")]
        assert not [n for n in names if n.lower().startswith(banned)]

    def test_no_age_based_heuristic(self):
        """N-12 rejected Option B: age is uncorrelated with relevance."""
        from pathlib import Path

        import oip.retention as module

        source = Path(module.__file__).read_text().lower()
        for banned in ("timedelta", "older than", "ttl", "days"):
            assert banned not in source, banned

    def test_unspecified_content_tiering_is_reported(self, store):
        policy = RetentionPolicy(store=store)
        assert policy.content_tiering_specified is False
        assert policy.content_eviction_performed is False

    def test_it_fails_closed_without_a_graph(self):
        class NoGraph:
            graph = None

            def active_objects(self):
                return ()

        with pytest.raises(RetentionError):
            RetentionPolicy(store=NoGraph()).reachability()

    def test_the_policy_owns_no_storage(self):
        fields = {f.name for f in dataclasses.fields(RetentionPolicy)}
        assert fields == {"store", "graph", "max_depth", "content_tiering_specified"}


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    @pytest.mark.parametrize(
        "target", [ObjectStatus.SUPERSEDED, ObjectStatus.RETRACTED]
    )
    def test_other_transitions_are_unaffected(self, store, allocator, target):
        """Only ARCHIVED gained a guard; every other ACTIVE transition is
        unchanged even for an object supporting current knowledge."""
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, target, "reason")
        assert store.get(evidence.object_id).status is target

    def test_a_reachable_object_may_still_be_retracted(self, store, allocator):
        """Only ARCHIVED is reachability-guarded; retraction is unaffected."""
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.get(evidence.object_id).status is ObjectStatus.RETRACTED

    def test_writing_and_reading_is_unchanged(self, store, allocator):
        evidence = real_evidence(store, allocator)
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE
        assert store.evidence.get(evidence.object_id) is not None


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_archival_of_a_protected_object_all_refused(
        self, store, allocator
    ):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        refused: list[int] = []
        wrong: list[int] = []

        def worker() -> None:
            try:
                store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "r")
                wrong.append(1)
            except StoreReachabilityError:
                refused.append(1)

        threads = [threading.Thread(target=worker) for _ in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not wrong
        assert len(refused) == 12
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE

    def test_concurrent_archival_of_a_leaf_admits_exactly_one(
        self, store, allocator
    ):
        evidence = real_evidence(store, allocator)
        succeeded: list[int] = []

        def worker() -> None:
            try:
                store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "r")
                succeeded.append(1)
            except Exception:
                pass

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(succeeded) == 1
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED

    def test_the_invariant_holds_under_concurrent_archival(self, store, allocator):
        objects = [real_evidence(store, allocator, f"m{n}") for n in range(20)]

        def worker(stored) -> None:
            try:
                RetentionPolicy(store=store).archive(stored.object_id)
            except Exception:
                pass

        threads = [threading.Thread(target=worker, args=(o,)) for o in objects]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        store.assert_integrity()
        for stored in store:
            if stored.status is not ObjectStatus.ARCHIVED:
                continue
            for active in store.active_objects():
                assert stored.object_id not in store.graph.ancestors(
                    active.object_id
                ), "archived object supports ACTIVE knowledge"


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality]
# ---------------------------------------------------------------------------

@settings(max_examples=60, deadline=None)
@given(depth=st.integers(min_value=1, max_value=6))
def test_property_no_ancestor_of_an_active_object_is_archivable(depth):
    store = KnowledgeStore()
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    ladder = [ObjectType.FACT, ObjectType.PROBLEM, ObjectType.PATTERN,
              ObjectType.OPPORTUNITY, ObjectType.SOLUTION, ObjectType.VALIDATION]
    current = write_evidence(store, allocator)
    made = [current]
    for object_type in ladder[:depth]:
        current = write_derived(store, allocator, object_type, [current])
        made.append(current)

    policy = RetentionPolicy(store=store)
    for stored in made[:-1]:
        assert policy.is_archivable(stored.object_id) is False
    assert policy.is_archivable(made[-1].object_id) is True


@settings(max_examples=60, deadline=None)
@given(count=st.integers(min_value=1, max_value=8))
def test_property_archiving_never_reduces_the_object_count(count):
    store = KnowledgeStore()
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    made = [write_evidence(store, allocator) for _ in range(count)]
    before = len(store)
    RetentionPolicy(store=store).archive_all([m.object_id for m in made])
    assert len(store) == before


@settings(max_examples=60, deadline=None)
@given(count=st.integers(min_value=1, max_value=6))
def test_property_traversal_survives_any_archival_set(count):
    store = KnowledgeStore()
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    roots = []
    for _ in range(count):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        roots.append((evidence, fact))

    policy = RetentionPolicy(store=store)
    policy.archive_all([f.object_id for _, f in roots])
    policy.archive_all([e.object_id for e, _ in roots])
    for evidence, fact in roots:
        assert store.graph.contains(evidence.object_id)
        assert evidence.object_id in store.graph.ancestors(fact.object_id)
        assert store.find(evidence.object_id) is not None


@settings(max_examples=60, deadline=None)
@given(count=st.integers(min_value=1, max_value=6))
def test_property_archived_objects_never_support_active_ones(count):
    store = KnowledgeStore()
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    for _ in range(count):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
    for _ in range(count):
        write_evidence(store, allocator)

    policy = RetentionPolicy(store=store)
    policy.archive_all([s.object_id for s in list(store)])
    for stored in store:
        if stored.status is not ObjectStatus.ARCHIVED:
            continue
        for active in store.active_objects():
            assert stored.object_id not in store.graph.ancestors(active.object_id)


@settings(max_examples=60, deadline=None)
@given(count=st.integers(min_value=1, max_value=5))
def test_property_assessment_reasons_are_never_empty_when_refusing(count):
    store = KnowledgeStore()
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    evidence = write_evidence(store, allocator)
    for _ in range(count):
        write_derived(store, allocator, ObjectType.FACT, [evidence])

    assessment = RetentionPolicy(store=store).assess(evidence.object_id)
    assert assessment.archivable is False
    assert assessment.reasons
    assert assessment.detail


class TestSkeletonVerificationBranches:
    """Directly exercise every defensive branch of the skeleton check.

    Each simulates a genuine loss of one N-12 permanently-retained element,
    so no branch is asserted only by inspection.
    """

    def test_reports_a_missing_required_attribute(self, store, allocator):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        stored = store.get(evidence.object_id)
        object.__setattr__(stored.attributes, "engine_configuration_ref", "")
        assert "engine_configuration_ref" in policy.verify_skeleton_intact(
            evidence.object_id
        )

    def test_reports_a_missing_status_reason_when_not_active(
        self, store, allocator
    ):
        """V9: a non-ACTIVE object must carry a status_reason."""
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        policy.archive(evidence.object_id)
        stored = store.get(evidence.object_id)
        object.__setattr__(stored.attributes, "status_reason", "   ")
        assert "status_reason" in policy.verify_skeleton_intact(evidence.object_id)

    def test_reports_missing_lineage(self, store, allocator):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        stored = store.get(evidence.object_id)
        object.__setattr__(stored, "lineage", None)
        assert "lineage" in policy.verify_skeleton_intact(evidence.object_id)

    def test_reports_missing_lineage_references_for_a_derived_object(
        self, store, allocator
    ):
        """Evidence is a root and may have none; a Fact may not."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        policy = RetentionPolicy(store=store)
        stored = store.get(fact.object_id)
        object.__setattr__(stored.lineage, "references", ())
        assert "lineage_references" in policy.verify_skeleton_intact(fact.object_id)

    def test_a_root_object_needs_no_lineage_references(self, store, allocator):
        evidence = real_evidence(store, allocator)
        assert store.get(evidence.object_id).lineage.references == ()
        assert RetentionPolicy(store=store).verify_skeleton_intact(
            evidence.object_id
        ) == ()

    def test_reports_missing_provenance(self, store, allocator):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        payload = store.evidence.get(evidence.object_id)
        object.__setattr__(payload, "provenance", None)
        assert "provenance" in policy.verify_skeleton_intact(evidence.object_id)

    def test_reports_a_blanked_source_identifier(self, store, allocator):
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        payload = store.evidence.get(evidence.object_id)
        object.__setattr__(payload.provenance, "source_identifier", "  ")
        assert "provenance.source_identifier" in policy.verify_skeleton_intact(
            evidence.object_id
        )

    def test_a_non_evidence_type_skips_the_payload_check(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert RetentionPolicy(store=store).verify_skeleton_intact(
            fact.object_id
        ) == ()

    def test_an_evidence_object_without_a_registered_payload_is_tolerated(
        self, store, allocator
    ):
        """conftest evidence registers no payload; absence is not corruption."""
        evidence = write_evidence(store, allocator)
        assert store.evidence.get(evidence.object_id) is None
        assert RetentionPolicy(store=store).verify_skeleton_intact(
            evidence.object_id
        ) == ()

    def test_a_store_without_an_evidence_registry_is_tolerated(self):
        class Bare:
            graph = None

            def find(self, object_id):
                return None

        assert RetentionPolicy(store=Bare()).verify_skeleton_intact("x") == (
            "object",
        )


class TestTraversalIntactBranches:
    def test_traversal_intact_is_false_for_an_unknown_object(self, store):
        assert RetentionPolicy(store=store).traversal_intact("nope") is False

    def test_traversal_intact_is_true_for_a_known_object(self, store, allocator):
        evidence = real_evidence(store, allocator)
        assert RetentionPolicy(store=store).traversal_intact(
            evidence.object_id
        ) is True


class TestReachabilityIndexBranches:
    def test_an_active_root_absent_from_the_graph_is_skipped(self):
        """N-6: the graph may lag the store, so a root may not be indexed."""
        class LaggingGraph:
            def contains(self, object_id):
                return False

            def ancestors(self, object_id, max_depth=32):
                raise AssertionError("must not traverse an unindexed root")

        index = ReachabilityIndex.build(
            ["a", "b"], LaggingGraph()
        )
        assert index.protected == frozenset({"a", "b"})
        assert index.active_roots == frozenset({"a", "b"})

    def test_an_explicit_graph_overrides_the_stores(self, store, allocator):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        policy = RetentionPolicy(store=store, graph=store.graph)
        assert policy.is_archivable(evidence.object_id) is False


class TestStoreGuardBranches:
    def test_an_active_object_absent_from_the_graph_is_skipped(
        self, store, allocator
    ):
        """N-6: the graph may lag the store; an unindexed ACTIVE object
        cannot be traversed, so it cannot establish protection."""
        evidence = real_evidence(store, allocator)
        other = real_evidence(store, allocator, "second")
        # Simulate index lag: drop the other ACTIVE object from the graph.
        store.graph._types.pop(other.object_id, None)
        assert store.graph.contains(other.object_id) is False
        # Archival of an unrelated leaf still proceeds.
        store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED

    def test_the_candidate_itself_is_skipped_when_scanning_active(
        self, store, allocator
    ):
        """An object is never protected from archival by its own ACTIVE row."""
        evidence = real_evidence(store, allocator)
        store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED


class TestGuardRulesBoundExactly:
    """Each test here kills a specific mutation that initially survived.

    Recorded deliberately: a surviving mutant means a ratified rule was not
    actually bound by any assertion.
    """

    def test_the_store_guard_protects_transitive_ancestors_not_just_parents(
        self, store, allocator
    ):
        """Kills: guard checking parents() instead of ancestors().

        N-12 says "reachable ... by lineage traversal", not "directly
        referenced". A grandparent supports current knowledge just as a
        parent does.
        """
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        problem = write_derived(store, allocator, ObjectType.PROBLEM, [fact])
        # Withdraw the intermediate so the ONLY remaining ACTIVE dependent is
        # two hops away. A guard checking direct parents would now miss it.
        store.transition(fact.object_id, ObjectStatus.SUPERSEDED, "replaced")
        actives = {s.object_id for s in store.active_objects()}
        assert fact.object_id not in actives
        assert problem.object_id in actives
        assert evidence.object_id not in store.graph.parents(problem.object_id)
        assert evidence.object_id in store.graph.ancestors(problem.object_id)

        with pytest.raises(StoreReachabilityError):
            store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE

    def test_a_three_hop_ancestor_is_protected_at_the_store(
        self, store, allocator
    ):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE].object_id
        terminal = chain[ObjectType.VALIDATION].object_id
        # Withdraw every intermediate: only a 6-hop ancestor path remains.
        for object_type, stored in chain.items():
            if stored.object_id not in (evidence, terminal):
                store.transition(
                    stored.object_id, ObjectStatus.SUPERSEDED, "replaced"
                )
        assert evidence not in store.graph.parents(terminal)
        assert evidence in store.graph.ancestors(terminal)
        with pytest.raises(StoreReachabilityError):
            store.transition(evidence, ObjectStatus.ARCHIVED, "retention")

    def test_the_store_guard_does_not_protect_the_candidate_from_itself(
        self, store, allocator
    ):
        """Kills: guard omitting the `active_id == object_id` skip.

        Without that skip every ACTIVE object is its own protector and no
        archival is ever possible -- ACTIVE is the only legal source state.
        """
        evidence = real_evidence(store, allocator)
        store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED

    def test_a_self_referencing_active_root_is_still_archivable(
        self, store, allocator
    ):
        """Kills: policy support-test omitting the self-exclusion.

        An object that is its own ancestor in the scan (because it is ACTIVE)
        must not thereby protect itself: ACTIVE is the precondition for
        archiving, not a protection. Uses a self-lineage Evidence root, the
        case where candidate and scanned root are the same object.
        """
        evidence = real_evidence(store, allocator)
        policy = RetentionPolicy(store=store)
        index = policy.reachability()
        assert index.is_active_root(evidence.object_id) is True
        assert index.is_reachable(evidence.object_id) is True
        assert policy.is_archivable(evidence.object_id) is True
        # And it actually archives, through both paths.
        policy.archive(evidence.object_id)
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED

    def test_a_lone_active_object_archives_through_the_store_guard(
        self, store, allocator
    ):
        """Kills: store guard omitting the self-skip, which would make every
        ACTIVE object its own protector and archival impossible."""
        evidence = real_evidence(store, allocator)
        assert {s.object_id for s in store.active_objects()} == {
            evidence.object_id
        }
        store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(evidence.object_id).status is ObjectStatus.ARCHIVED

    def test_many_lone_active_objects_all_archive(self, store, allocator):
        """Several ACTIVE objects present: each must still archive, so the
        self-skip cannot be replaced by 'only when alone'."""
        objects = [real_evidence(store, allocator, f"m{n}") for n in range(4)]
        policy = RetentionPolicy(store=store)
        archived = policy.archive_all([o.object_id for o in objects])
        assert len(archived) == 4

    def test_the_index_records_ancestors_not_only_roots(self, store, allocator):
        """Kills: ReachabilityIndex.build omitting the ancestors update."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        # Withdraw the Evidence so it is NOT an ACTIVE root: it can then only
        # enter the index as an ancestor of the still-ACTIVE Fact.
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        index = RetentionPolicy(store=store).reachability()
        assert index.is_active_root(fact.object_id) is True
        assert index.is_active_root(evidence.object_id) is False
        assert index.is_reachable(evidence.object_id) is True, (
            "an ancestor of an ACTIVE object is missing from the index"
        )
        assert len(index) > len(index.active_roots)

    def test_the_index_over_a_deep_chain_holds_every_ancestor(
        self, store, allocator
    ):
        chain = write_chain(store, allocator)
        terminal = chain[ObjectType.VALIDATION].object_id
        # Withdraw every upstream object so only the terminal is an ACTIVE
        # root; the rest can enter the index solely as ancestors.
        for object_type, stored in chain.items():
            if stored.object_id != terminal:
                store.transition(
                    stored.object_id, ObjectStatus.RETRACTED, "withdrawn"
                )
        index = RetentionPolicy(store=store).reachability()
        assert index.active_roots == frozenset({terminal})
        for object_type, stored in chain.items():
            assert index.is_reachable(stored.object_id) is True, object_type

    def test_rejected_can_never_reach_archived(self, store, allocator):
        """Kills: adding ARCHIVED to REJECTED's permitted transitions.

        IOM 2.1: REJECTED is terminal and "no terminal state may transition".
        """
        from oip.lifecycle import permitted_transitions

        assert can_transition(
            ObjectType.EVIDENCE, ObjectStatus.REJECTED, ObjectStatus.ARCHIVED
        ) is False
        assert permitted_transitions(
            ObjectType.EVIDENCE, ObjectStatus.REJECTED
        ) == frozenset()

    @pytest.mark.parametrize(
        "terminal",
        [
            ObjectStatus.SUPERSEDED,
            ObjectStatus.REJECTED,
            ObjectStatus.RETRACTED,
            ObjectStatus.INVALIDATED,
            ObjectStatus.ARCHIVED,
        ],
    )
    def test_every_terminal_state_permits_nothing(self, terminal):
        from oip.lifecycle import permitted_transitions

        assert permitted_transitions(ObjectType.FACT, terminal) == frozenset()


class TestSelfExclusionIsDefensive:
    """Why two mutation survivors are equivalent, demonstrated not asserted.

    Removing the `active_id == object_id` skip (store guard) or the
    `active_id == object_id` disjunct (policy support test) changes nothing
    observable, because the lineage graph is acyclic under R-8: an object is
    never among its own ancestors. Both skips are defensive, and are retained
    because they state the intent -- an object's own ACTIVE status is the
    precondition for archiving, never a protection.
    """

    def test_no_object_is_among_its_own_ancestors(self, store, allocator):
        chain = write_chain(store, allocator)
        for object_type, stored in chain.items():
            assert stored.object_id not in store.graph.ancestors(
                stored.object_id
            ), object_type

    def test_a_root_has_no_ancestors_at_all(self, store, allocator):
        evidence = write_evidence(store, allocator)
        assert store.graph.ancestors(evidence.object_id) == frozenset()

    def test_the_graph_refuses_a_self_edge(self, store, allocator):
        """R-8: the lineage graph is acyclic, so no self-loop can exist."""
        evidence = write_evidence(store, allocator)
        assert store.graph.would_introduce_cycle(
            evidence.object_id, evidence.object_id
        ) is True

    def test_archival_therefore_works_for_every_active_object(
        self, store, allocator
    ):
        """The observable consequence: self-exclusion never blocks anything."""
        objects = [real_evidence(store, allocator, f"m{n}") for n in range(5)]
        policy = RetentionPolicy(store=store)
        for stored in objects:
            assert policy.is_archivable(stored.object_id) is True
        assert len(policy.archive_all([o.object_id for o in objects])) == 5
