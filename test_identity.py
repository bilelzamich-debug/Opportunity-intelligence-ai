"""Contract tests for object identity allocation.

Task: T01.1.1

Test style, per N-4 (determinism posture):
  Outputs are NOT asserted for equality against fixed expected values.
  Every test asserts a PROPERTY the contract guarantees -- uniqueness,
  monotonicity, constancy, rejection. Identifiers are opaque; nothing here
  depends on their form.

Acceptance criteria under test:
  AC1  object_id uniqueness enforced
  AC2  lineage_id constant across a supersession chain
  AC3  version increments by exactly 1
  AC4  reuse of a retired object_id is rejected
"""

from __future__ import annotations

import threading

import pytest

from oip.identity import (
    BranchingError,
    IdentityAllocator,
    IdentityError,
    LineageMismatchError,
    ObjectIdentity,
    ObjectIdReuseError,
    UnknownObjectIdError,
    VersionSequenceError,
)


@pytest.fixture()
def allocator() -> IdentityAllocator:
    return IdentityAllocator()


# ---------------------------------------------------------------------------
# AC1 -- object_id uniqueness
# ---------------------------------------------------------------------------

class TestObjectIdUniqueness:
    def test_new_objects_receive_distinct_object_ids(self, allocator):
        ids = {allocator.new_object().object_id for _ in range(1000)}
        assert len(ids) == 1000

    def test_new_objects_receive_distinct_lineage_ids(self, allocator):
        lineages = {allocator.new_object().lineage_id for _ in range(1000)}
        assert len(lineages) == 1000

    def test_successor_object_id_differs_from_predecessor(self, allocator):
        first = allocator.new_object()
        second = allocator.succeed(first)
        assert second.object_id != first.object_id

    def test_every_version_in_a_chain_has_a_distinct_object_id(self, allocator):
        current = allocator.new_object()
        seen = {current.object_id}
        for _ in range(50):
            current = allocator.succeed(current)
            assert current.object_id not in seen
            seen.add(current.object_id)
        assert len(seen) == 51

    def test_uniqueness_holds_under_concurrent_allocation(self, allocator):
        """N-11 permits concurrent acquisition; allocation must be safe."""
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            local = [allocator.new_object().object_id for _ in range(100)]
            with lock:
                results.extend(local)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 800
        assert len(set(results)) == 800, "concurrent allocation produced a collision"


# ---------------------------------------------------------------------------
# AC2 -- lineage_id constant across a supersession chain
# ---------------------------------------------------------------------------

class TestLineageConstancy:
    def test_lineage_id_is_constant_across_the_chain(self, allocator):
        first = allocator.new_object()
        current = first
        for _ in range(25):
            current = allocator.succeed(current)
            assert current.lineage_id == first.lineage_id

    def test_distinct_chains_never_share_a_lineage_id(self, allocator):
        chain_a = allocator.new_object()
        chain_b = allocator.new_object()
        for _ in range(10):
            chain_a = allocator.succeed(chain_a)
            chain_b = allocator.succeed(chain_b)
        assert chain_a.lineage_id != chain_b.lineage_id

    def test_succession_rejects_mismatched_lineage(self, allocator):
        first = allocator.new_object()
        forged = ObjectIdentity(
            object_id=first.object_id,
            lineage_id="lin-forged",
            version=first.version,
        )
        with pytest.raises(LineageMismatchError):
            allocator.succeed(forged)

    def test_validate_succession_rejects_lineage_change(self, allocator):
        first = allocator.new_object()
        bad = ObjectIdentity(
            object_id="obj-other", lineage_id="lin-different", version=2
        )
        with pytest.raises(LineageMismatchError):
            allocator.validate_succession(first, bad)


# ---------------------------------------------------------------------------
# AC3 -- version increments by exactly 1
# ---------------------------------------------------------------------------

class TestVersionMonotonicity:
    def test_new_object_starts_at_version_one(self, allocator):
        assert allocator.new_object().version == 1

    def test_version_increments_by_exactly_one(self, allocator):
        current = allocator.new_object()
        for expected in range(2, 40):
            current = allocator.succeed(current)
            assert current.version == expected

    def test_version_sequence_has_no_gaps(self, allocator):
        current = allocator.new_object()
        versions = [current.version]
        for _ in range(30):
            current = allocator.succeed(current)
            versions.append(current.version)
        deltas = {b - a for a, b in zip(versions, versions[1:])}
        assert deltas == {1}, f"version deltas must all be 1, saw {deltas}"

    def test_version_below_one_is_rejected(self):
        for bad in (0, -1, -100):
            with pytest.raises(VersionSequenceError):
                ObjectIdentity(object_id="obj-x", lineage_id="lin-x", version=bad)

    def test_validate_succession_rejects_skipped_version(self, allocator):
        first = allocator.new_object()
        skipped = ObjectIdentity(
            object_id="obj-new", lineage_id=first.lineage_id, version=3
        )
        with pytest.raises(VersionSequenceError):
            allocator.validate_succession(first, skipped)

    def test_validate_succession_rejects_repeated_version(self, allocator):
        first = allocator.new_object()
        repeat = ObjectIdentity(
            object_id="obj-new", lineage_id=first.lineage_id, version=1
        )
        with pytest.raises(VersionSequenceError):
            allocator.validate_succession(first, repeat)

    def test_succeeding_a_stale_version_is_rejected(self, allocator):
        """Succeeding v1 twice would branch the chain -- forbidden by R-1."""
        first = allocator.new_object()
        allocator.succeed(first)
        with pytest.raises(BranchingError):
            allocator.succeed(first)

    def test_chain_cannot_branch_at_any_depth(self, allocator):
        current = allocator.new_object()
        for _ in range(5):
            current = allocator.succeed(current)
        allocator.succeed(current)
        with pytest.raises(BranchingError):
            allocator.succeed(current)

    def test_superseded_versions_are_reported(self, allocator):
        first = allocator.new_object()
        assert not allocator.is_superseded(first.object_id)
        second = allocator.succeed(first)
        assert allocator.is_superseded(first.object_id)
        assert not allocator.is_superseded(second.object_id)

    def test_only_chain_head_may_be_succeeded_under_concurrency(self, allocator):
        """Concurrent succession of one version must produce exactly one winner."""
        first = allocator.new_object()
        outcomes: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            try:
                allocator.succeed(first)
                result = "ok"
            except BranchingError:
                result = "rejected"
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert outcomes.count("ok") == 1, "exactly one succession may win"
        assert outcomes.count("rejected") == 15


# ---------------------------------------------------------------------------
# AC4 -- reuse of a retired object_id is rejected (I2)
# ---------------------------------------------------------------------------

class TestObjectIdReuseRejected:
    def test_issued_id_cannot_be_reused(self, allocator):
        identity = allocator.new_object()
        with pytest.raises(ObjectIdReuseError):
            allocator.assert_not_reused(identity.object_id)

    def test_superseded_id_remains_retired(self, allocator):
        """A superseded version is retired but its id stays permanently taken."""
        first = allocator.new_object()
        allocator.succeed(first)
        with pytest.raises(ObjectIdReuseError):
            allocator.assert_not_reused(first.object_id)

    def test_unknown_id_is_not_treated_as_reused(self, allocator):
        allocator.assert_not_reused("obj-never-issued")  # must not raise

    def test_successor_may_not_carry_predecessor_id(self, allocator):
        first = allocator.new_object()
        same_id = ObjectIdentity(
            object_id=first.object_id,
            lineage_id=first.lineage_id,
            version=first.version + 1,
        )
        with pytest.raises(ObjectIdReuseError):
            allocator.validate_succession(first, same_id)

    def test_adopt_rejects_conflicting_reuse(self, allocator):
        identity = allocator.new_object()
        conflicting = ObjectIdentity(
            object_id=identity.object_id,
            lineage_id="lin-different",
            version=1,
        )
        with pytest.raises(ObjectIdReuseError):
            allocator.adopt([conflicting])

    def test_adopt_is_idempotent_for_identical_identity(self, allocator):
        identity = allocator.new_object()
        allocator.adopt([identity])
        allocator.adopt([identity])
        assert allocator.is_issued(identity.object_id)


# ---------------------------------------------------------------------------
# Immutability (I1, I3) and structural guards
# ---------------------------------------------------------------------------

class TestIdentityImmutability:
    def test_identity_cannot_be_mutated(self, allocator):
        identity = allocator.new_object()
        for field, value in (
            ("object_id", "obj-other"),
            ("lineage_id", "lin-other"),
            ("version", 99),
        ):
            with pytest.raises(Exception):
                setattr(identity, field, value)

    def test_empty_identifiers_are_rejected(self):
        with pytest.raises(IdentityError):
            ObjectIdentity(object_id="", lineage_id="lin-x", version=1)
        with pytest.raises(IdentityError):
            ObjectIdentity(object_id="obj-x", lineage_id="", version=1)

    def test_is_initial_flags_only_first_version(self, allocator):
        first = allocator.new_object()
        assert first.is_initial
        assert not allocator.succeed(first).is_initial


class TestSuccessionGuards:
    def test_cannot_succeed_an_unknown_identity(self, allocator):
        foreign = ObjectIdentity(
            object_id="obj-foreign", lineage_id="lin-foreign", version=1
        )
        with pytest.raises(UnknownObjectIdError):
            allocator.succeed(foreign)

    def test_adopted_identity_can_then_be_succeeded(self, allocator):
        """Rehydration path: adopt, then continue the chain."""
        rehydrated = ObjectIdentity(
            object_id="obj-from-storage", lineage_id="lin-from-storage", version=7
        )
        allocator.adopt([rehydrated])
        successor = allocator.succeed(rehydrated)
        assert successor.version == 8
        assert successor.lineage_id == rehydrated.lineage_id
        assert successor.object_id != rehydrated.object_id


class TestAllocatorIntrospection:
    def test_chain_length_tracks_highest_version(self, allocator):
        current = allocator.new_object()
        assert allocator.chain_length(current.lineage_id) == 1
        for expected in range(2, 12):
            current = allocator.succeed(current)
            assert allocator.chain_length(current.lineage_id) == expected

    def test_chain_length_unknown_lineage_is_zero(self, allocator):
        assert allocator.chain_length("lin-unknown") == 0

    def test_issued_count_includes_every_version(self, allocator):
        current = allocator.new_object()
        for _ in range(9):
            current = allocator.succeed(current)
        assert allocator.issued_count() == 10

    def test_lineage_of_resolves_issued_ids(self, allocator):
        identity = allocator.new_object()
        assert allocator.lineage_of(identity.object_id) == identity.lineage_id
        assert allocator.lineage_of("obj-unknown") is None


class TestStaleVersionRejection:
    def test_succeeding_with_wrong_version_number_is_rejected(self, allocator):
        """Presenting a mismatched version for a known object_id. [V11]"""
        first = allocator.new_object()
        stale = ObjectIdentity(
            object_id=first.object_id,
            lineage_id=first.lineage_id,
            version=first.version + 5,
        )
        with pytest.raises(VersionSequenceError):
            allocator.succeed(stale)
