"""Contract tests for partial-retraction semantics.

Task: T01.2.4 (completed at T01.2.4-R1)

Architecture References:
- N-9    Cascade is a mechanical integrity operation performing NO
         interpretation; idempotent; terminating; "altering status only,
         never content".
         What It Binds: "T01.2.4 partial retraction: an object retaining at
         least one valid upstream reference is re-versioned, not invalidated."
         Consequences Accepted: "A dependent supported by ten Facts, one of
         which is invalidated, is handled by the partial-retraction rule
         rather than by cascade -- the boundary between the two must be
         maintained carefully."
- IOM 3.2 Fact transitions: ACTIVE -> INVALIDATED on "All attesting Evidence
         retracted". Partial retraction "produces a new version with reduced
         support, not invalidation. The Fact remains attested."
- I6     Upstream RETRACTED/INVALIDATED => dependents INVALIDATED
- R-8    The lineage graph is acyclic, guaranteeing termination
- D-01a  References bind to a specific version
- M-65   Re-derivation on supersession OPEN; SUPERSEDED is not withdrawal

T01.2.4 acceptance criteria under test:
  AC1  Object with some upstream references retracted remains ACTIVE
  AC2  Object with all upstream references retracted becomes INVALIDATED
  AC3  Rule is type-agnostic; Fact attachment behaviour follows from it

SCOPE BOUNDARY. N-9 states cascade performs no interpretation and alters
status only, never content. Cascade therefore does NOT create the reduced
support version itself: producing a new version is the owning engine's act.
Cascade applies the ratified boundary structurally -- it spares the object and
reports it -- which is what "handled by the partial-retraction rule rather
than by cascade" requires.
"""

from __future__ import annotations

import threading


import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.cascade import CASCADE_TRIGGERS, CascadeInvalidation
from oip.enums import ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.store import KnowledgeStore

from conftest import write_derived, write_evidence

DERIVED_TYPES = (
    ObjectType.FACT,
    ObjectType.PROBLEM,
    ObjectType.PATTERN,
    ObjectType.OPPORTUNITY,
    ObjectType.SOLUTION,
    ObjectType.VALIDATION,
)


def roots(store, allocator, count):
    return [write_evidence(store, allocator) for _ in range(count)]


def retains_valid_upstream(store, object_id) -> bool:
    """The ratified predicate, computed independently of the implementation."""
    stored = store.get(object_id)
    references = stored.lineage.reference_ids if stored.lineage else ()
    return any(
        store.find(r) is not None
        and store.find(r).status not in CASCADE_TRIGGERS
        for r in references
    )


# ---------------------------------------------------------------------------
# AC1 -- some upstream withdrawn: the object remains ACTIVE
# ---------------------------------------------------------------------------

class TestSomeUpstreamWithdrawn:
    def test_one_of_two_withdrawn_leaves_the_object_active(self, store, allocator):
        first, second = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [first, second])

        result = CascadeInvalidation(store=store).retract(
            first.object_id, "withdrawn"
        )

        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE
        assert result.changed == 0
        assert result.partially_retracted == (fact.object_id,)

    def test_one_of_ten_withdrawn_leaves_the_object_active(self, store, allocator):
        """N-9's own example: ten Facts, one invalidated."""
        parents = roots(store, allocator, 10)
        fact = write_derived(store, allocator, ObjectType.FACT, parents)

        CascadeInvalidation(store=store).retract(parents[0].object_id, "withdrawn")

        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

    def test_nine_of_ten_withdrawn_still_leaves_it_active(self, store, allocator):
        """One surviving reference is enough. [N-9]"""
        parents = roots(store, allocator, 10)
        fact = write_derived(store, allocator, ObjectType.FACT, parents)
        cascade = CascadeInvalidation(store=store)

        for parent in parents[:-1]:
            cascade.retract(parent.object_id, "withdrawn")

        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE
        assert retains_valid_upstream(store, fact.object_id)

    def test_the_spared_object_is_reported_not_silently_skipped(
        self, store, allocator
    ):
        """N-9: the boundary "must be maintained carefully" -- so it is visible."""
        first, second = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [first, second])

        result = CascadeInvalidation(store=store).retract(
            first.object_id, "withdrawn"
        )

        assert result.partial_count == 1
        assert fact.object_id in result.partially_retracted
        assert result.completed is True

    def test_the_surviving_upstream_is_untouched(self, store, allocator):
        first, second = roots(store, allocator, 2)
        write_derived(store, allocator, ObjectType.FACT, [first, second])

        CascadeInvalidation(store=store).retract(first.object_id, "withdrawn")

        assert store.get(second.object_id).status is ObjectStatus.ACTIVE

    def test_cascade_alters_no_content(self, store, allocator):
        """N-9: "altering status only, never content"."""
        first, second = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [first, second])
        before = store.get(fact.object_id).attributes

        CascadeInvalidation(store=store).retract(first.object_id, "withdrawn")
        after = store.get(fact.object_id).attributes

        assert after.confidence == before.confidence
        assert after.explanation == before.explanation
        assert after.derives_from == before.derives_from

    def test_no_new_version_is_created_by_cascade(self, store, allocator):
        """Re-versioning with reduced support is the owning engine's act."""
        first, second = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [first, second])
        lineage_id = store.get(fact.object_id).lineage_id
        before = len(store.versions_of(lineage_id))

        CascadeInvalidation(store=store).retract(first.object_id, "withdrawn")

        assert len(store.versions_of(lineage_id)) == before


# ---------------------------------------------------------------------------
# AC2 -- all upstream withdrawn: the object is INVALIDATED
# ---------------------------------------------------------------------------

class TestAllUpstreamWithdrawn:
    def test_both_of_two_withdrawn_invalidates(self, store, allocator):
        first, second = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [first, second])
        cascade = CascadeInvalidation(store=store)

        cascade.retract(first.object_id, "withdrawn")
        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE
        cascade.retract(second.object_id, "withdrawn")

        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

    def test_all_ten_withdrawn_invalidates(self, store, allocator):
        parents = roots(store, allocator, 10)
        fact = write_derived(store, allocator, ObjectType.FACT, parents)
        cascade = CascadeInvalidation(store=store)

        for parent in parents:
            cascade.retract(parent.object_id, "withdrawn")

        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

    def test_a_single_parent_chain_still_cascades_fully(self, store, allocator):
        """The common case must be unaffected by the partial-retraction rule."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        problem = write_derived(store, allocator, ObjectType.PROBLEM, [fact])
        pattern = write_derived(store, allocator, ObjectType.PATTERN, [problem])

        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

        for stored in (fact, problem, pattern):
            assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_a_doomed_upstream_does_not_count_as_attesting(self, store, allocator):
        """An upstream condemned by the SAME cascade is already withdrawn.

        Eligibility is computed before any mutation for rollback safety, so an
        upstream still reading ACTIVE may already be doomed. Counting it would
        spare a dependent whose entire support is about to vanish.
        """
        evidence = write_evidence(store, allocator)
        first = write_derived(store, allocator, ObjectType.FACT, [evidence])
        second = write_derived(store, allocator, ObjectType.FACT, [evidence])
        problem = write_derived(store, allocator, ObjectType.PROBLEM,
                                [first, second])

        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

        assert store.get(first.object_id).status is ObjectStatus.INVALIDATED
        assert store.get(second.object_id).status is ObjectStatus.INVALIDATED
        assert store.get(problem.object_id).status is ObjectStatus.INVALIDATED

    def test_an_invalidated_upstream_no_longer_attests(self, store, allocator):
        """INVALIDATED is withdrawal just as RETRACTED is. [I6]"""
        first, second = roots(store, allocator, 2)
        derived_a = write_derived(store, allocator, ObjectType.FACT, [first])
        derived_b = write_derived(store, allocator, ObjectType.FACT, [second])
        problem = write_derived(store, allocator, ObjectType.PROBLEM,
                                [derived_a, derived_b])
        cascade = CascadeInvalidation(store=store)

        cascade.retract(first.object_id, "withdrawn")
        assert store.get(derived_a.object_id).status is ObjectStatus.INVALIDATED
        assert store.get(problem.object_id).status is ObjectStatus.ACTIVE

        cascade.retract(second.object_id, "withdrawn")
        assert store.get(problem.object_id).status is ObjectStatus.INVALIDATED


# ---------------------------------------------------------------------------
# AC3 -- the rule is type-agnostic
# ---------------------------------------------------------------------------

class TestTypeAgnostic:
    @pytest.mark.parametrize("object_type", DERIVED_TYPES)
    def test_partial_retention_spares_every_derived_type(
        self, store, allocator, object_type
    ):
        parent_type = {
            ObjectType.FACT: ObjectType.EVIDENCE,
            ObjectType.PROBLEM: ObjectType.FACT,
            ObjectType.PATTERN: ObjectType.PROBLEM,
            ObjectType.OPPORTUNITY: ObjectType.PATTERN,
            ObjectType.SOLUTION: ObjectType.OPPORTUNITY,
            ObjectType.VALIDATION: ObjectType.SOLUTION,
        }[object_type]

        # Build two independent parent branches of the required type.
        branches = []
        for _ in range(2):
            current = write_evidence(store, allocator)
            for step in (ObjectType.FACT, ObjectType.PROBLEM,
                         ObjectType.PATTERN, ObjectType.OPPORTUNITY,
                         ObjectType.SOLUTION):
                if current.object_type is parent_type:
                    break
                current = write_derived(store, allocator, step, [current])
            branches.append(current)

        subject = write_derived(store, allocator, object_type, branches)
        first_root = store.objects_of_type(ObjectType.EVIDENCE)[0]

        CascadeInvalidation(store=store).retract(first_root.object_id, "w")

        assert store.get(subject.object_id).status is ObjectStatus.ACTIVE, (
            f"{object_type.value} was invalidated despite a valid upstream"
        )

    @pytest.mark.parametrize("object_type", DERIVED_TYPES)
    def test_total_withdrawal_invalidates_every_derived_type(
        self, store, allocator, object_type
    ):
        parent_type = {
            ObjectType.FACT: ObjectType.EVIDENCE,
            ObjectType.PROBLEM: ObjectType.FACT,
            ObjectType.PATTERN: ObjectType.PROBLEM,
            ObjectType.OPPORTUNITY: ObjectType.PATTERN,
            ObjectType.SOLUTION: ObjectType.OPPORTUNITY,
            ObjectType.VALIDATION: ObjectType.SOLUTION,
        }[object_type]

        branches = []
        for _ in range(2):
            current = write_evidence(store, allocator)
            for step in (ObjectType.FACT, ObjectType.PROBLEM,
                         ObjectType.PATTERN, ObjectType.OPPORTUNITY,
                         ObjectType.SOLUTION):
                if current.object_type is parent_type:
                    break
                current = write_derived(store, allocator, step, [current])
            branches.append(current)

        subject = write_derived(store, allocator, object_type, branches)
        cascade = CascadeInvalidation(store=store)

        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            cascade.retract(evidence.object_id, "withdrawn")

        assert store.get(subject.object_id).status is ObjectStatus.INVALIDATED


# ---------------------------------------------------------------------------
# Mixed parent scenarios
# ---------------------------------------------------------------------------

class TestMixedParents:
    def test_parents_of_differing_status_are_assessed_correctly(
        self, store, allocator
    ):
        """RETRACTED and INVALIDATED both withdraw; others still attest."""
        alpha, beta, gamma = roots(store, allocator, 3)
        fact = write_derived(store, allocator, ObjectType.FACT,
                             [alpha, beta, gamma])

        store.transition(alpha.object_id, ObjectStatus.RETRACTED, "withdrawn")
        CascadeInvalidation(store=store).cascade(alpha.object_id)

        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE
        assert retains_valid_upstream(store, fact.object_id)

    def test_a_superseded_parent_still_attests(self, store, allocator):
        """D-01a binds to a version; supersession is not withdrawal. [M-65]"""
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])

        store.transition(alpha.object_id, ObjectStatus.SUPERSEDED, "replaced")
        CascadeInvalidation(store=store).retract(beta.object_id, "withdrawn")

        assert ObjectStatus.SUPERSEDED not in CASCADE_TRIGGERS
        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

    def test_a_diamond_shares_one_root(self, store, allocator):
        """Two branches from one root: withdrawing it dooms the whole diamond."""
        evidence = write_evidence(store, allocator)
        left = write_derived(store, allocator, ObjectType.FACT, [evidence])
        right = write_derived(store, allocator, ObjectType.FACT, [evidence])
        problem = write_derived(store, allocator, ObjectType.PROBLEM,
                                [left, right])

        CascadeInvalidation(store=store).retract(evidence.object_id, "w")

        assert store.get(problem.object_id).status is ObjectStatus.INVALIDATED

    def test_a_diamond_with_an_independent_branch_survives(self, store, allocator):
        shared, independent = roots(store, allocator, 2)
        left = write_derived(store, allocator, ObjectType.FACT, [shared])
        right = write_derived(store, allocator, ObjectType.FACT, [independent])
        problem = write_derived(store, allocator, ObjectType.PROBLEM,
                                [left, right])

        CascadeInvalidation(store=store).retract(shared.object_id, "w")

        assert store.get(left.object_id).status is ObjectStatus.INVALIDATED
        assert store.get(right.object_id).status is ObjectStatus.ACTIVE
        assert store.get(problem.object_id).status is ObjectStatus.ACTIVE

    def test_depth_is_respected_across_a_partial_boundary(self, store, allocator):
        """A spared object does not propagate withdrawal to its own children."""
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        problem = write_derived(store, allocator, ObjectType.PROBLEM, [fact])

        CascadeInvalidation(store=store).retract(alpha.object_id, "w")

        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE
        assert store.get(problem.object_id).status is ObjectStatus.ACTIVE


# ---------------------------------------------------------------------------
# Rollback safety
# ---------------------------------------------------------------------------

class TestRollbackSafety:
    def test_eligibility_is_computed_before_any_mutation(self, store, allocator):
        """A failure must leave the store exactly as it was. [N-10]"""
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        before = {s.object_id: s.status for s in store}

        class Exploding(CascadeInvalidation):
            def _retains_valid_upstream(self, stored, doomed):
                raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            Exploding(store=store).retract(alpha.object_id, "w")

        # The origin itself transitions first; every dependent is untouched.
        assert store.get(fact.object_id).status == before[fact.object_id]

    def test_a_partial_result_reports_completed(self, store, allocator):
        alpha, beta = roots(store, allocator, 2)
        write_derived(store, allocator, ObjectType.FACT, [alpha, beta])

        result = CascadeInvalidation(store=store).retract(alpha.object_id, "w")

        assert result.completed is True
        assert not result.failures

    def test_spared_objects_are_not_counted_as_changed(self, store, allocator):
        alpha, beta = roots(store, allocator, 2)
        write_derived(store, allocator, ObjectType.FACT, [alpha, beta])

        result = CascadeInvalidation(store=store).retract(alpha.object_id, "w")

        assert result.changed == 0
        assert result.is_noop is True

    def test_integrity_holds_after_a_partial_retraction(self, store, allocator):
        alpha, beta = roots(store, allocator, 2)
        write_derived(store, allocator, ObjectType.FACT, [alpha, beta])

        CascadeInvalidation(store=store).retract(alpha.object_id, "w")

        store.assert_integrity()


# ---------------------------------------------------------------------------
# Idempotence  [N-9]
# ---------------------------------------------------------------------------

class TestIdempotence:
    def test_repeating_a_partial_cascade_changes_nothing(self, store, allocator):
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        cascade = CascadeInvalidation(store=store)

        first = cascade.retract(alpha.object_id, "w")
        second = cascade.cascade(alpha.object_id)
        third = cascade.cascade(alpha.object_id)

        assert first.changed == second.changed == third.changed == 0
        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

    def test_the_spared_set_is_stable_across_repeats(self, store, allocator):
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        cascade = CascadeInvalidation(store=store)

        cascade.retract(alpha.object_id, "w")
        repeat = cascade.cascade(alpha.object_id)

        assert repeat.partially_retracted == (fact.object_id,)

    def test_repeating_a_total_cascade_changes_nothing(self, store, allocator):
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        cascade = CascadeInvalidation(store=store)

        cascade.retract(alpha.object_id, "w")
        cascade.retract(beta.object_id, "w")
        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

        again = cascade.cascade(beta.object_id)
        assert again.changed == 0
        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

    def test_cascade_terminates_on_a_wide_fan_out(self, store, allocator):
        """R-8: acyclic lineage guarantees termination."""
        evidence = write_evidence(store, allocator)
        children = [
            write_derived(store, allocator, ObjectType.FACT, [evidence])
            for _ in range(30)
        ]

        result = CascadeInvalidation(store=store).retract(evidence.object_id, "w")

        assert result.completed is True
        assert result.changed == 30
        assert all(
            store.get(c.object_id).status is ObjectStatus.INVALIDATED
            for c in children
        )


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_cascades_preserve_the_invariant(self, store, allocator):
        subjects = []
        for _ in range(15):
            alpha, beta = roots(store, allocator, 2)
            subjects.append(
                (alpha, write_derived(store, allocator, ObjectType.FACT,
                                      [alpha, beta]))
            )
        errors: list[Exception] = []

        def worker(origin):
            try:
                CascadeInvalidation(store=store).retract(origin.object_id, "w")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(o,))
                   for o, _ in subjects]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        for _, subject in subjects:
            assert store.get(subject.object_id).status is ObjectStatus.ACTIVE
        store.assert_integrity()

    def test_the_invariant_holds_after_concurrent_total_withdrawal(
        self, store, allocator
    ):
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        errors: list[Exception] = []

        def worker(origin):
            try:
                CascadeInvalidation(store=store).retract(origin.object_id, "w")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(o,))
                   for o in (alpha, beta)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED
        store.assert_integrity()


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality]
# ---------------------------------------------------------------------------

@settings(max_examples=120, deadline=None)
@given(total=st.integers(min_value=2, max_value=8),
       withdraw=st.integers(min_value=1, max_value=8))
def test_property_active_iff_a_valid_upstream_remains(total, withdraw):
    """The ratified invariant, over every partition of parents."""
    withdraw = min(withdraw, total)
    store, allocator = KnowledgeStore(), IdentityAllocator()
    parents = [write_evidence(store, allocator) for _ in range(total)]
    fact = write_derived(store, allocator, ObjectType.FACT, parents)
    cascade = CascadeInvalidation(store=store)

    for parent in parents[:withdraw]:
        cascade.retract(parent.object_id, "withdrawn")

    survives = withdraw < total
    expected = ObjectStatus.ACTIVE if survives else ObjectStatus.INVALIDATED
    assert store.get(fact.object_id).status is expected
    assert retains_valid_upstream(store, fact.object_id) is survives


@settings(max_examples=120, deadline=None)
@given(total=st.integers(min_value=2, max_value=6))
def test_property_withdrawing_all_always_invalidates(total):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    parents = [write_evidence(store, allocator) for _ in range(total)]
    fact = write_derived(store, allocator, ObjectType.FACT, parents)
    cascade = CascadeInvalidation(store=store)

    for parent in parents:
        cascade.retract(parent.object_id, "withdrawn")

    assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED


@settings(max_examples=100, deadline=None)
@given(total=st.integers(min_value=2, max_value=6),
       repeats=st.integers(min_value=1, max_value=4))
def test_property_cascade_is_idempotent(total, repeats):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    parents = [write_evidence(store, allocator) for _ in range(total)]
    fact = write_derived(store, allocator, ObjectType.FACT, parents)
    cascade = CascadeInvalidation(store=store)

    cascade.retract(parents[0].object_id, "withdrawn")
    baseline = store.get(fact.object_id).status
    for _ in range(repeats):
        result = cascade.cascade(parents[0].object_id)
        assert result.changed == 0
    assert store.get(fact.object_id).status is baseline


@settings(max_examples=100, deadline=None)
@given(total=st.integers(min_value=1, max_value=6))
def test_property_no_object_is_active_without_valid_upstream(total):
    """The invariant cascade must maintain, over the whole store."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    parents = [write_evidence(store, allocator) for _ in range(total)]
    write_derived(store, allocator, ObjectType.FACT, parents)
    cascade = CascadeInvalidation(store=store)

    for parent in parents:
        cascade.retract(parent.object_id, "withdrawn")

    for stored in store:
        references = stored.lineage.reference_ids if stored.lineage else ()
        if not references or stored.status is not ObjectStatus.ACTIVE:
            continue
        assert retains_valid_upstream(store, stored.object_id)


@settings(max_examples=80, deadline=None)
@given(total=st.integers(min_value=2, max_value=5))
def test_property_content_never_changes(total):
    """N-9: cascade alters status only, never content."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    parents = [write_evidence(store, allocator) for _ in range(total)]
    fact = write_derived(store, allocator, ObjectType.FACT, parents)
    before = store.get(fact.object_id).attributes

    CascadeInvalidation(store=store).retract(parents[0].object_id, "withdrawn")
    after = store.get(fact.object_id).attributes

    assert after.confidence == before.confidence
    assert after.derives_from == before.derives_from
    assert after.explanation == before.explanation


class TestRetentionPredicateBranches:
    """Cover the defensive branches of the upstream-validity predicate.

    Each fires only when the store is already unusual, so each is exercised
    directly rather than left to inference.
    """

    def test_an_object_without_lineage_retains_nothing(self, store, allocator):
        cascade = CascadeInvalidation(store=store)

        class NoLineage:
            lineage = None

        assert cascade._retains_valid_upstream(NoLineage(), set()) is False

    def test_an_object_with_no_references_retains_nothing(
        self, store, allocator
    ):
        """Evidence is a root: it attests to nothing upstream."""
        evidence = write_evidence(store, allocator)
        cascade = CascadeInvalidation(store=store)
        stored = store.get(evidence.object_id)

        assert stored.lineage.reference_ids == ()
        assert cascade._retains_valid_upstream(stored, set()) is False

    def test_an_unresolvable_reference_does_not_attest(self, store, allocator):
        """A reference that resolves to nothing cannot count as support."""
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        cascade = CascadeInvalidation(store=store)
        stored = store.get(fact.object_id)

        # Both references present -> attested.
        assert cascade._retains_valid_upstream(stored, set()) is True
        # Both doomed, so nothing attests even though both resolve.
        doomed = {alpha.object_id, beta.object_id}
        assert cascade._retains_valid_upstream(stored, doomed) is False

    def test_a_missing_upstream_is_skipped_not_counted(self, store, allocator):
        """I4 forbids hard deletion, so this is a defensive path only."""
        alpha, beta = roots(store, allocator, 2)
        fact = write_derived(store, allocator, ObjectType.FACT, [alpha, beta])
        cascade = CascadeInvalidation(store=store)
        stored = store.get(fact.object_id)

        store._objects.pop(alpha.object_id)
        # beta still resolves and still attests
        assert cascade._retains_valid_upstream(stored, set()) is True
        # with beta doomed too, nothing attests
        assert cascade._retains_valid_upstream(
            stored, {beta.object_id}
        ) is False


# ===========================================================================
# Non-uniform lineage depth  [T01.8.1 gate defect, regression]
# ===========================================================================

class TestNonUniformLineageDepth:
    """Eligibility must not depend on traversal order. [T01.2.4, N-9, I6]

    Every partial-retraction test above builds lineage of UNIFORM depth,
    where breadth-first order happens to coincide with a topological order.
    That coincidence hid a defect: `_collect` orders dependents by SHORTEST
    path, which in a DAG is not a topological order, so a dependent whose
    upstreams sit at different distances was decided before the deeper of
    them, read it as still attesting, and was spared -- left ACTIVE with its
    entire support withdrawn.

    A Validation is the reachable case. IOM 3.7 says it "DERIVES_FROM the
    object containing the tested claim", and IOM's relationship table types
    DERIVES_FROM as "any -> any", so -- unlike Problem, Pattern, Opportunity,
    Solution, Execution Record and Feedback Record -- no single upstream type
    is imposed. Its references may therefore span pipeline stages.
    """

    @staticmethod
    def _skewed(store, allocator):
        """A dependent whose upstreams sit at distance 1 and distance 5."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        problem = write_derived(store, allocator, ObjectType.PROBLEM, [fact])
        pattern = write_derived(store, allocator, ObjectType.PATTERN, [problem])
        opportunity = write_derived(
            store, allocator, ObjectType.OPPORTUNITY, [pattern]
        )
        solution = write_derived(
            store, allocator, ObjectType.SOLUTION, [opportunity]
        )
        shallow = write_derived(store, allocator, ObjectType.FACT, [evidence])
        spanning = write_derived(
            store, allocator, ObjectType.VALIDATION, [shallow, solution]
        )
        return evidence, shallow, solution, spanning

    def test_dependent_is_reached_before_its_deeper_upstream(
        self, store, allocator
    ):
        """The precondition the defect needed: order is not topological."""
        evidence, _, solution, spanning = self._skewed(store, allocator)
        plan = CascadeInvalidation(store=store).plan(evidence.object_id)
        assert plan.index(spanning.object_id) < plan.index(solution.object_id)

    def test_total_withdrawal_across_uneven_depths_invalidates(
        self, store, allocator
    ):
        """All upstream withdrawn => INVALIDATED, whatever the depths."""
        evidence, shallow, solution, spanning = self._skewed(store, allocator)
        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

        assert store.get(shallow.object_id).status is not ObjectStatus.ACTIVE
        assert store.get(solution.object_id).status is not ObjectStatus.ACTIVE
        assert store.get(spanning.object_id).status is ObjectStatus.INVALIDATED

    def test_uneven_depths_are_not_reported_as_partial(self, store, allocator):
        """A fully unsupported object is not a partial retraction."""
        evidence, _, _, spanning = self._skewed(store, allocator)
        result = CascadeInvalidation(store=store).retract(
            evidence.object_id, "withdrawn"
        )
        assert spanning.object_id not in result.partially_retracted
        assert spanning.object_id in result.invalidated

    def test_no_i6_violation_after_uneven_depth_cascade(self, store, allocator):
        """The detective control agrees with the preventive one. [I6]"""
        from oip.integrity import IntegrityVerifier

        evidence, _, _, _ = self._skewed(store, allocator)
        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

        report = IntegrityVerifier(store=store).verify()
        assert not [v for v in report.violations if v.constraint_id == "I6"]

    def test_surviving_upstream_at_another_depth_still_spares(
        self, store, allocator
    ):
        """The fix must not over-invalidate: genuine support still counts."""
        evidence, shallow, solution, spanning = self._skewed(store, allocator)
        independent = write_evidence(store, allocator)
        other = write_derived(store, allocator, ObjectType.FACT, [independent])
        supported = write_derived(
            store, allocator, ObjectType.VALIDATION, [other, solution]
        )

        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

        assert store.get(other.object_id).status is ObjectStatus.ACTIVE
        assert store.get(supported.object_id).status is ObjectStatus.ACTIVE

    @settings(max_examples=25, deadline=None)
    @given(depth=st.integers(min_value=2, max_value=6))
    def test_any_skew_depth_leaves_no_unsupported_object_active(self, depth):
        """Property: after cascade, nothing ACTIVE has all upstream withdrawn."""
        store, allocator = KnowledgeStore(), IdentityAllocator()
        evidence = write_evidence(store, allocator)

        chain = [write_derived(store, allocator, ObjectType.FACT, [evidence])]
        ladder = (
            ObjectType.PROBLEM, ObjectType.PATTERN, ObjectType.OPPORTUNITY,
            ObjectType.SOLUTION, ObjectType.VALIDATION,
        )
        for otype in ladder[: depth - 1]:
            chain.append(
                write_derived(store, allocator, otype, [chain[-1]])
            )
        shallow = write_derived(store, allocator, ObjectType.FACT, [evidence])
        write_derived(
            store, allocator, ObjectType.VALIDATION, [shallow, chain[-1]]
        )

        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")

        withdrawn = {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED}
        for stored in store:
            if stored.status is not ObjectStatus.ACTIVE:
                continue
            refs = stored.attributes.derives_from
            if not refs:
                continue
            assert any(
                store.get(r.object_id).status not in withdrawn for r in refs
            )
