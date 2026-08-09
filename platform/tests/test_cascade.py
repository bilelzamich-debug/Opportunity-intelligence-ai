"""Contract tests for cascade invalidation.

Task: T01.2.3

Architecture References:
- N-9    Mechanical operation; no interpretation
- I6     Upstream RETRACTED/INVALIDATED => dependents INVALIDATED
- M-09   Retraction semantics: status only, never content
- R-2    Lifecycle; terminal states never transition
- R-8    Lineage graph is acyclic
- D-01a  References bind to a specific version
- M-65   Re-derivation on SUPERSEDED is OPEN; must not be invented here
- N-10   Failures produce records, not unexpected exceptions

Acceptance criteria under test:
  AC1  Retracting Evidence invalidates all dependents
  AC2  Traversal terminates
  AC3  Operation is idempotent
  AC4  No content altered, only status
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.cascade import (
    CASCADE_TRIGGERS,
    CascadeDepthExceededError,
    CascadeInvalidation,
    CascadeResult,
    is_cascade_trigger,
)
from oip.enums import ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.store import KnowledgeStore
from tests.conftest import (
    PARENT_OF,
    write_chain,
    write_derived,
    write_evidence,
)


@pytest.fixture()
def cascade(store) -> CascadeInvalidation:
    return CascadeInvalidation(store=store)


def diamond(store, allocator):
    """ev -> {fa1, fa2} -> pr : a shared-ancestor fan-in."""
    evidence = write_evidence(store, allocator)
    fa1 = write_derived(store, allocator, ObjectType.FACT, [evidence])
    fa2 = write_derived(store, allocator, ObjectType.FACT, [evidence])
    problem = write_derived(store, allocator, ObjectType.PROBLEM, [fa1, fa2])
    return evidence, fa1, fa2, problem


# ===========================================================================
# AC1 -- retracting Evidence invalidates all dependents
# ===========================================================================

class TestRetractionInvalidatesDependents:
    def test_full_chain_invalidated(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]

        result = cascade.retract(evidence.object_id, "source withdrew")

        assert result.completed
        assert result.changed == 6
        for object_type, stored in chain.items():
            if object_type is ObjectType.EVIDENCE:
                assert store.get(stored.object_id).status is ObjectStatus.RETRACTED
            else:
                assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_no_orphaned_valid_descendants(self, store, allocator, cascade):
        """The defining guarantee: nothing downstream stays ACTIVE. [I6]"""
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        cascade.retract(evidence.object_id, "withdrawn")

        survivors = [
            s.object_id
            for s in store.graph.descendants(evidence.object_id)
            if store.get(s).status is ObjectStatus.ACTIVE
        ] if False else [
            oid
            for oid in store.graph.descendants(evidence.object_id)
            if store.get(oid).status is ObjectStatus.ACTIVE
        ]
        assert survivors == []

    def test_midchain_invalidation_propagates_forward_only(
        self, store, allocator, cascade
    ):
        chain = write_chain(store, allocator)
        pattern = chain[ObjectType.PATTERN]

        cascade.cascade(pattern.object_id, ObjectStatus.INVALIDATED, "upstream")

        # Downstream of Pattern is invalidated.
        for object_type in (
            ObjectType.OPPORTUNITY, ObjectType.SOLUTION, ObjectType.VALIDATION
        ):
            assert store.get(chain[object_type].object_id).status \
                is ObjectStatus.INVALIDATED
        # Upstream of Pattern is untouched.
        for object_type in (
            ObjectType.EVIDENCE, ObjectType.FACT, ObjectType.PROBLEM
        ):
            assert store.get(chain[object_type].object_id).status \
                is ObjectStatus.ACTIVE

    def test_diamond_shared_ancestor(self, store, allocator, cascade):
        evidence, fa1, fa2, problem = diamond(store, allocator)
        result = cascade.retract(evidence.object_id, "withdrawn")

        assert set(result.invalidated) == {
            fa1.object_id, fa2.object_id, problem.object_id
        }
        assert store.get(problem.object_id).status is ObjectStatus.INVALIDATED

    def test_partial_parent_loss_does_not_invalidate(self, store, allocator, cascade):
        """A dependent retaining a valid parent is NOT invalidated.

        Corrected at T01.8.1: this test previously asserted the opposite,
        encoding cascade's behaviour before T01.2.4 existed. N-9 is explicit
        that "a dependent supported by ten Facts, one of which is
        invalidated, is handled by the partial-retraction rule rather than by
        cascade", and binds T01.2.4 as "an object retaining at least one
        valid upstream reference is re-versioned, not invalidated". IOM 3.2
        triggers a Fact's INVALIDATED on "All attesting Evidence retracted".

        Cascade still performs no interpretation: it applies the ratified
        boundary structurally and reports the spared object, leaving
        re-versioning with reduced support to the owning engine. [T01.2.4]
        """
        weak = write_evidence(store, allocator)
        strong = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [weak, strong])

        result = cascade.retract(weak.object_id, "withdrawn")

        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE
        assert store.get(strong.object_id).status is ObjectStatus.ACTIVE
        assert result.partially_retracted == (fact.object_id,)
        assert result.changed == 0

    def test_total_parent_loss_still_invalidates(self, store, allocator, cascade):
        """When ALL upstream is withdrawn the dependent is invalidated. [I6]"""
        weak = write_evidence(store, allocator)
        strong = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [weak, strong])

        cascade.retract(weak.object_id, "withdrawn")
        cascade.retract(strong.object_id, "withdrawn")

        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

    def test_leaf_retraction_has_no_dependents(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        validation = chain[ObjectType.VALIDATION]
        result = cascade.retract(validation.object_id, "withdrawn")
        assert result.completed
        assert result.is_noop

    def test_wide_fan_out(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        facts = [
            write_derived(store, allocator, ObjectType.FACT, [evidence])
            for _ in range(50)
        ]
        result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.changed == 50
        assert all(
            store.get(f.object_id).status is ObjectStatus.INVALIDATED
            for f in facts
        )


# ===========================================================================
# AC2 -- traversal terminates
# ===========================================================================

class TestTermination:
    def test_deep_chain_terminates(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        current = evidence
        for _ in range(25):
            current = write_derived(store, allocator, ObjectType.FACT, [current])

        result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert result.changed == 25

    def test_depth_bound_reports_failure_not_hang(self, store, allocator):
        """A malformed graph must fail cleanly, not loop. [N-10]"""
        evidence = write_evidence(store, allocator)
        current = evidence
        for _ in range(12):
            current = write_derived(store, allocator, ObjectType.FACT, [current])

        shallow = CascadeInvalidation(store=store, max_depth=4)
        result = shallow.cascade(
            evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
        )
        assert not result.completed
        assert result.failures
        assert "exceeded depth" in result.failures[0].failed_rules[0].detail

    def test_plan_raises_on_depth_overflow(self, store, allocator):
        evidence = write_evidence(store, allocator)
        current = evidence
        for _ in range(8):
            current = write_derived(store, allocator, ObjectType.FACT, [current])
        shallow = CascadeInvalidation(store=store, max_depth=3)
        with pytest.raises(CascadeDepthExceededError):
            shallow.plan(evidence.object_id)

    def test_visited_set_prevents_repeat_work(self, store, allocator, cascade):
        """A shared ancestor is visited once, not once per path."""
        evidence, fa1, fa2, problem = diamond(store, allocator)
        plan = cascade.plan(evidence.object_id)
        assert len(plan) == len(set(plan)) == 3

    def test_lineage_graph_is_acyclic(self, store, allocator):
        """Termination rests on acyclicity. [R-8, V10]"""
        write_chain(store, allocator)
        assert store.graph.is_acyclic()


# ===========================================================================
# AC3 -- idempotence
# ===========================================================================

class TestIdempotence:
    def test_second_cascade_changes_nothing(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]

        first = cascade.retract(evidence.object_id, "withdrawn")
        second = cascade.cascade(
            evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
        )

        assert first.changed == 6
        assert second.changed == 0
        assert len(second.already_terminal) == 6

    def test_repeated_cascades_converge(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        cascade.retract(evidence.object_id, "withdrawn")

        statuses = {
            oid: store.get(oid).status
            for oid in store.graph.descendants(evidence.object_id)
        }
        for _ in range(5):
            cascade.cascade(
                evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
            )
        assert {
            oid: store.get(oid).status
            for oid in store.graph.descendants(evidence.object_id)
        } == statuses

    def test_already_invalidated_dependents_skipped(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.INVALIDATED, "manual")

        result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.changed == 0
        assert fact.object_id in result.already_terminal


# ===========================================================================
# AC4 -- no content altered, only status
# ===========================================================================

class TestContentPreserved:
    def test_only_status_changes(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        fact = chain[ObjectType.FACT]
        before = store.get(fact.object_id).attributes

        cascade.retract(evidence.object_id, "withdrawn")
        after = store.get(fact.object_id).attributes

        assert after.status is ObjectStatus.INVALIDATED
        assert after.identity == before.identity
        assert after.confidence == before.confidence
        assert after.derives_from == before.derives_from
        assert after.explanation == before.explanation
        assert after.produced_at == before.produced_at
        assert after.engine_configuration_ref == before.engine_configuration_ref

    def test_lineage_preserved(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        fact = chain[ObjectType.FACT]
        before = store.get(fact.object_id).lineage

        cascade.retract(evidence.object_id, "withdrawn")
        assert store.get(fact.object_id).lineage == before

    def test_graph_edges_preserved(self, store, allocator, cascade):
        """I4: referenced objects are never removed, only marked."""
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        fact = chain[ObjectType.FACT]

        cascade.retract(evidence.object_id, "withdrawn")

        assert store.contains(evidence.object_id)
        assert store.graph.parents(fact.object_id) == {evidence.object_id}
        assert store.graph_diverges() == ()

    def test_status_reason_names_the_origin(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        cascade.retract(evidence.object_id, "source withdrew")

        reason = store.get(chain[ObjectType.FACT].object_id).attributes.status_reason
        assert "source withdrew" in reason

    def test_default_reason_names_origin_and_status(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        result = cascade.cascade(
            evidence.object_id, ObjectStatus.RETRACTED
        )
        reason = store.get(result.invalidated[0]).attributes.status_reason
        assert evidence.object_id in reason and "RETRACTED" in reason


# ===========================================================================
# Trigger discipline -- SUPERSEDED must not cascade [D-01a, M-65]
# ===========================================================================

class TestTriggerDiscipline:
    def test_only_two_statuses_trigger(self):
        assert CASCADE_TRIGGERS == {
            ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED
        }

    @pytest.mark.parametrize("status", list(ObjectStatus))
    def test_trigger_predicate_matches_the_set(self, status):
        assert is_cascade_trigger(status) is (status in CASCADE_TRIGGERS)

    def test_superseded_does_not_cascade(self, store, allocator, cascade):
        """D-01a: dependents reference a specific version and stay valid.

        Re-derivation policy is M-65, unresolved until T05.2.2. Cascading
        supersession here would silently invent that policy.
        """
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])

        store.transition(evidence.object_id, ObjectStatus.SUPERSEDED, "new version")
        result = cascade.cascade(evidence.object_id)

        assert result.completed
        assert result.changed == 0
        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

    def test_archived_does_not_cascade(self, store, allocator, cascade):
        """ARCHIVED is not a cascade trigger. [N-9, M-65]

        The Evidence is archived only after its dependent Fact is withdrawn,
        because N-12 forbids archiving an object that ACTIVE knowledge still
        derives from [T01.2.5]. The subject under test is unchanged: what
        cascades, not what may be archived.
        """
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(fact.object_id, ObjectStatus.RETRACTED, "withdrawn")

        store.transition(evidence.object_id, ObjectStatus.ARCHIVED, "retention")
        result = cascade.cascade(evidence.object_id)

        assert result.changed == 0
        assert store.get(fact.object_id).status is ObjectStatus.RETRACTED

    def test_rejected_does_not_cascade(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        result = cascade.cascade(evidence.object_id, ObjectStatus.REJECTED)
        assert result.changed == 0


# ===========================================================================
# Failure handling and rollback [N-10]
# ===========================================================================

class TestFailureHandling:
    def test_unknown_origin_produces_a_record(self, store, cascade):
        result = cascade.cascade("obj-absent", ObjectStatus.RETRACTED, "x")
        assert not result.completed
        assert result.failures
        assert "not stored" in result.failures[0].failed_rules[0].detail

    def test_unknown_origin_does_not_raise(self, store, cascade):
        cascade.cascade("obj-absent", ObjectStatus.RETRACTED, "x")  # no exception

    def test_retract_unknown_origin_is_safe(self, store, cascade):
        result = cascade.retract("obj-absent", "x")
        assert not result.completed

    def test_indexed_but_unstored_dependent_reports_failure(
        self, store, allocator, cascade
    ):
        """Graph/store divergence must fail cleanly, not corrupt state."""
        evidence = write_evidence(store, allocator)
        from tests.conftest import build_lineage
        store.graph.index_lineage(
            build_lineage(
                "obj-phantom", ObjectType.FACT,
                ((evidence.object_id, ObjectType.EVIDENCE),),
            )
        )
        result = cascade.cascade(
            evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
        )
        assert not result.completed
        assert "indexed but not stored" in result.failures[0].failed_rules[0].detail

    def test_failure_leaves_store_untouched(self, store, allocator, cascade):
        """Rollback safety: a failed cascade mutates nothing. [N-10]"""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        from tests.conftest import build_lineage
        store.graph.index_lineage(
            build_lineage(
                "obj-phantom", ObjectType.FACT,
                ((evidence.object_id, ObjectType.EVIDENCE),),
            )
        )
        result = cascade.cascade(
            evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
        )
        assert not result.completed
        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

    def test_failed_retract_restores_the_origin(self, store, allocator, cascade):
        """The origin must not be left RETRACTED with live dependents."""
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        from tests.conftest import build_lineage
        store.graph.index_lineage(
            build_lineage(
                "obj-phantom", ObjectType.FACT,
                ((evidence.object_id, ObjectType.EVIDENCE),),
            )
        )
        result = cascade.retract(evidence.object_id, "withdrawn")
        assert not result.completed
        assert store.get(evidence.object_id).status is ObjectStatus.ACTIVE

    def test_operations_are_recorded(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        cascade.retract(chain[ObjectType.EVIDENCE].object_id, "withdrawn")
        cascade.cascade("obj-absent", ObjectStatus.RETRACTED, "x")
        assert len(cascade.operations) == 2
        assert cascade.operations[0].completed
        assert not cascade.operations[1].completed


# ===========================================================================
# Determinism [N-4]
# ===========================================================================

class TestDeterminism:
    def test_plan_ordering_is_stable(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        assert all(
            cascade.plan(evidence.object_id) == cascade.plan(evidence.object_id)
            for _ in range(5)
        )

    def test_plan_is_breadth_first_then_lexicographic(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        facts = [
            write_derived(store, allocator, ObjectType.FACT, [evidence])
            for _ in range(6)
        ]
        plan = cascade.plan(evidence.object_id)
        assert list(plan) == sorted(f.object_id for f in facts)

    def test_identical_graphs_produce_identical_plans(self):
        plans = []
        for _ in range(3):
            store, allocator = KnowledgeStore(), IdentityAllocator()
            evidence = write_evidence(store, allocator)
            for _ in range(4):
                write_derived(store, allocator, ObjectType.FACT, [evidence])
            operation = CascadeInvalidation(store=store)
            plan = operation.plan(evidence.object_id)
            plans.append(len(plan))
        assert len(set(plans)) == 1

    def test_result_is_reproducible(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        evidence = chain[ObjectType.EVIDENCE]
        planned = cascade.plan(evidence.object_id)
        result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.invalidated == planned


# ===========================================================================
# Reporting surface
# ===========================================================================

class TestReporting:
    def test_impact_report_groups_by_type(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        report = cascade.impact_report(chain[ObjectType.EVIDENCE].object_id)
        assert report[ObjectType.FACT] == (chain[ObjectType.FACT].object_id,)
        assert ObjectType.EVIDENCE not in report

    def test_impact_report_does_not_mutate(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        cascade.impact_report(chain[ObjectType.EVIDENCE].object_id)
        assert store.get(chain[ObjectType.FACT].object_id).status \
            is ObjectStatus.ACTIVE

    def test_plan_of_unknown_origin_is_empty(self, store, cascade):
        assert cascade.plan("obj-absent") == ()

    def test_result_bool_reflects_completion(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        assert bool(cascade.retract(chain[ObjectType.EVIDENCE].object_id, "x"))
        assert not bool(cascade.cascade("obj-absent", ObjectStatus.RETRACTED, "x"))

    def test_noop_flag(self, store, allocator, cascade):
        evidence = write_evidence(store, allocator)
        assert cascade.retract(evidence.object_id, "withdrawn").is_noop


# ===========================================================================
# Compatibility with V1-V12 and store invariants
# ===========================================================================

class TestCompatibility:
    def test_store_stays_consistent(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        cascade.retract(chain[ObjectType.EVIDENCE].object_id, "withdrawn")
        assert store.graph_diverges() == ()
        assert len(store) == 7

    def test_active_index_cleared_for_invalidated(self, store, allocator, cascade):
        """I5 bookkeeping survives cascade."""
        chain = write_chain(store, allocator)
        fact = chain[ObjectType.FACT]
        cascade.retract(chain[ObjectType.EVIDENCE].object_id, "withdrawn")
        assert store.active_version_of(fact.lineage_id) is None

    def test_new_writes_still_validate(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        cascade.retract(chain[ObjectType.EVIDENCE].object_id, "withdrawn")
        fresh = write_evidence(store, allocator)
        assert store.get(fresh.object_id).status is ObjectStatus.ACTIVE

    def test_rebuild_after_cascade_is_clean(self, store, allocator, cascade):
        chain = write_chain(store, allocator)
        cascade.retract(chain[ObjectType.EVIDENCE].object_id, "withdrawn")
        store.rebuild_graph()
        assert store.graph_diverges() == ()


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=40, deadline=None)
@given(depth=st.integers(min_value=1, max_value=12))
def test_every_descendant_invalidated_at_any_depth(depth):
    """AC1 + AC2 over arbitrary chain depth."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    current = evidence
    for _ in range(depth):
        current = write_derived(store, allocator, ObjectType.FACT, [current])

    operation = CascadeInvalidation(store=store)
    result = operation.retract(evidence.object_id, "withdrawn")

    assert result.completed
    assert result.changed == depth
    assert all(
        store.get(oid).status is ObjectStatus.INVALIDATED
        for oid in store.graph.descendants(evidence.object_id)
    )


@settings(max_examples=40, deadline=None)
@given(fan=st.integers(min_value=1, max_value=20))
def test_no_active_descendant_survives_any_fan_out(fan):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    for _ in range(fan):
        write_derived(store, allocator, ObjectType.FACT, [evidence])

    CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

    assert not [
        oid
        for oid in store.graph.descendants(evidence.object_id)
        if store.get(oid).status is ObjectStatus.ACTIVE
    ]


@settings(max_examples=30, deadline=None)
@given(runs=st.integers(min_value=2, max_value=6))
def test_repeated_cascade_is_always_idempotent(runs):
    """AC3 over arbitrary repetition."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    for _ in range(4):
        write_derived(store, allocator, ObjectType.FACT, [evidence])

    operation = CascadeInvalidation(store=store)
    first = operation.retract(evidence.object_id, "withdrawn")
    for _ in range(runs):
        repeat = operation.cascade(
            evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
        )
        assert repeat.changed == 0
        assert len(repeat.already_terminal) == first.changed


@settings(max_examples=30, deadline=None)
@given(fan=st.integers(min_value=1, max_value=10))
def test_plan_matches_what_cascade_applies(fan):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    for _ in range(fan):
        write_derived(store, allocator, ObjectType.FACT, [evidence])

    operation = CascadeInvalidation(store=store)
    planned = operation.plan(evidence.object_id)
    applied = operation.retract(evidence.object_id, "withdrawn").invalidated
    assert planned == applied


@settings(max_examples=30, deadline=None)
@given(status=st.sampled_from(list(ObjectStatus)))
def test_only_triggers_cause_change(status):
    """SUPERSEDED and ARCHIVED must never cascade. [D-01a, M-65]"""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    fact = write_derived(store, allocator, ObjectType.FACT, [evidence])

    result = CascadeInvalidation(store=store).cascade(
        evidence.object_id, status, "probe"
    )
    changed = store.get(fact.object_id).status is ObjectStatus.INVALIDATED
    assert changed is is_cascade_trigger(status)
    assert result.completed


# ===========================================================================
# Recovery paths and remaining guards
# ===========================================================================

class TestRecoveryPaths:
    def test_unreachable_target_status_reports_failure(self, store, allocator, cascade):
        """A dependent that cannot legally reach INVALIDATED is refused,
        never force-transitioned. [R-2, E-V1]

        Evidence cannot reach INVALIDATED, so an Evidence node appearing as a
        dependent -- only possible via a corrupted index -- must produce a
        failure record rather than a bad transition.
        """
        from oip.enums import RelationshipType
        from oip.lifecycle import can_transition

        assert not can_transition(
            ObjectType.EVIDENCE, ObjectStatus.ACTIVE, ObjectStatus.INVALIDATED
        )
        origin = write_evidence(store, allocator)
        dependent = write_evidence(store, allocator)

        # Corrupt the index directly: an Evidence node as a dependent.
        derives = RelationshipType.DERIVES_FROM
        store.graph._out[derives][dependent.object_id].add(origin.object_id)
        store.graph._in[derives][origin.object_id].add(dependent.object_id)

        result = cascade.cascade(
            origin.object_id, ObjectStatus.RETRACTED, "withdrawn"
        )
        assert not result.completed
        assert "cannot transition" in result.failures[0].failed_rules[0].detail
        assert store.get(dependent.object_id).status is ObjectStatus.ACTIVE

    def test_rollback_restores_applied_transitions(self, store, allocator, cascade):
        """Mid-propagation failure must leave nothing half-applied. [N-10]"""
        evidence = write_evidence(store, allocator)
        facts = [
            write_derived(store, allocator, ObjectType.FACT, [evidence])
            for _ in range(4)
        ]

        original = store.transition
        calls = {"n": 0}

        def failing_transition(object_id, status, reason=None):
            calls["n"] += 1
            if calls["n"] == 3:
                raise RuntimeError("simulated storage fault")
            return original(object_id, status, reason)

        store.transition = failing_transition
        try:
            result = cascade.cascade(
                evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
            )
        finally:
            store.transition = original

        assert not result.completed
        assert "rolled back" in result.failures[0].failed_rules[0].detail
        assert all(
            store.get(f.object_id).status is ObjectStatus.ACTIVE for f in facts
        )

    def test_restore_of_missing_object_is_safe(self, store, cascade):
        cascade._restore("obj-absent", ObjectStatus.ACTIVE)  # must not raise

    def test_impact_report_skips_unstored_dependents(self, store, allocator, cascade):
        from tests.conftest import build_lineage
        evidence = write_evidence(store, allocator)
        store.graph.index_lineage(
            build_lineage(
                "obj-phantom", ObjectType.FACT,
                ((evidence.object_id, ObjectType.EVIDENCE),),
            )
        )
        assert cascade.impact_report(evidence.object_id) == {}
