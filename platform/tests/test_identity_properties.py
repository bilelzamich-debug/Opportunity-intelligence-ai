"""Property-based tests for object identity allocation.

Task: T01.1.1

Architecture References:
- R-1   Objects immutable; change produces a new version
- I2    object_id never reused
- I5    Exactly one ACTIVE version per lineage_id
- V11   version = predecessor + 1; lineage_id unchanged
- N-4   Outputs non-deterministic; assert properties, never equality
- N-11  Allocation must be thread-safe

These tests verify invariants over generated operation sequences rather than
fixed examples. The stateful machine explores allocation/succession orderings
no hand-written test would enumerate.
"""

from __future__ import annotations

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    Bundle,
    RuleBasedStateMachine,
    invariant,
    precondition,
    rule,
)

from oip.identity import (
    BranchingError,
    IdentityAllocator,
    IdentityError,
    ObjectIdentity,
    ObjectIdReuseError,
    VersionSequenceError,
)


# ---------------------------------------------------------------------------
# Stateful model: invariants must hold after ANY sequence of operations
# ---------------------------------------------------------------------------

class IdentityAllocatorMachine(RuleBasedStateMachine):
    """Explores arbitrary allocate/succeed sequences and checks invariants.

    Model state mirrors what the allocator should guarantee, so divergence
    between model and implementation surfaces as an invariant failure.
    """

    identities = Bundle("identities")

    def __init__(self) -> None:
        super().__init__()
        self.allocator = IdentityAllocator()
        # Every identity ever produced, in issue order.
        self.all_issued: list[ObjectIdentity] = []
        # lineage_id -> ordered versions observed
        self.chains: dict[str, list[int]] = {}
        # object_ids that have been succeeded
        self.superseded: set[str] = set()

    # -- operations -------------------------------------------------------

    @rule(target=identities)
    def allocate_new(self) -> ObjectIdentity:
        identity = self.allocator.new_object()
        self.all_issued.append(identity)
        self.chains.setdefault(identity.lineage_id, []).append(identity.version)
        return identity

    @rule(target=identities, parent=identities)
    def succeed_existing(self, parent: ObjectIdentity) -> ObjectIdentity:
        if parent.object_id in self.superseded:
            # Branching must be rejected, whatever the depth or ordering.
            with pytest.raises(BranchingError):
                self.allocator.succeed(parent)
            return parent

        child = self.allocator.succeed(parent)
        self.superseded.add(parent.object_id)
        self.all_issued.append(child)
        self.chains.setdefault(child.lineage_id, []).append(child.version)
        return child

    @rule(identity=identities)
    def reuse_is_always_rejected(self, identity: ObjectIdentity) -> None:
        with pytest.raises(ObjectIdReuseError):
            self.allocator.assert_not_reused(identity.object_id)

    # -- invariants -------------------------------------------------------

    @invariant()
    def object_ids_are_globally_unique(self) -> None:
        ids = [i.object_id for i in self.all_issued]
        assert len(ids) == len(set(ids)), "duplicate object_id issued"

    @invariant()
    def versions_within_a_chain_are_contiguous_from_one(self) -> None:
        for lineage_id, versions in self.chains.items():
            ordered = sorted(versions)
            assert ordered[0] == 1, f"{lineage_id} does not start at version 1"
            assert ordered == list(range(1, len(ordered) + 1)), (
                f"{lineage_id} has gaps or duplicates: {ordered}"
            )

    @invariant()
    def each_version_appears_once_per_chain(self) -> None:
        for lineage_id, versions in self.chains.items():
            assert len(versions) == len(set(versions)), (
                f"{lineage_id} produced a duplicate version -- chain branched"
            )

    @invariant()
    def allocator_agrees_with_model_on_issue_count(self) -> None:
        assert self.allocator.issued_count() == len(self.all_issued)

    @invariant()
    def allocator_agrees_with_model_on_chain_heads(self) -> None:
        for lineage_id, versions in self.chains.items():
            assert self.allocator.chain_length(lineage_id) == max(versions)

    @invariant()
    def every_issued_id_resolves_to_its_lineage(self) -> None:
        for identity in self.all_issued:
            assert self.allocator.lineage_of(identity.object_id) == identity.lineage_id

    @invariant()
    def supersession_state_matches_model(self) -> None:
        for identity in self.all_issued:
            expected = identity.object_id in self.superseded
            assert self.allocator.is_superseded(identity.object_id) is expected


TestIdentityAllocatorStateful = IdentityAllocatorMachine.TestCase
TestIdentityAllocatorStateful.settings = settings(
    max_examples=150,
    stateful_step_count=40,
    suppress_health_check=[HealthCheck.too_slow],
    deadline=None,
)


# ---------------------------------------------------------------------------
# Direct property tests
# ---------------------------------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(chain_length=st.integers(min_value=1, max_value=60))
def test_chain_of_any_length_preserves_lineage_and_increments(chain_length):
    """For any chain length: lineage constant, versions 1..n, ids distinct."""
    allocator = IdentityAllocator()
    current = allocator.new_object()
    origin = current
    seen_ids = {current.object_id}
    versions = [current.version]

    for _ in range(chain_length - 1):
        current = allocator.succeed(current)
        assert current.lineage_id == origin.lineage_id
        assert current.object_id not in seen_ids
        seen_ids.add(current.object_id)
        versions.append(current.version)

    assert versions == list(range(1, chain_length + 1))
    assert allocator.chain_length(origin.lineage_id) == chain_length


@settings(max_examples=200, deadline=None)
@given(count=st.integers(min_value=1, max_value=300))
def test_independent_objects_never_collide(count):
    """Any number of independent allocations yields distinct ids and lineages."""
    allocator = IdentityAllocator()
    identities = [allocator.new_object() for _ in range(count)]

    assert len({i.object_id for i in identities}) == count
    assert len({i.lineage_id for i in identities}) == count
    assert all(i.version == 1 for i in identities)


@settings(max_examples=200, deadline=None)
@given(
    object_id=st.text(min_size=1, max_size=40),
    lineage_id=st.text(min_size=1, max_size=40),
    version=st.integers(min_value=1, max_value=10_000),
)
def test_identity_construction_accepts_any_nonempty_identifiers(
    object_id, lineage_id, version
):
    """Identity is opaque: no format is imposed on identifiers. [N-4]"""
    identity = ObjectIdentity(
        object_id=object_id, lineage_id=lineage_id, version=version
    )
    assert identity.object_id == object_id
    assert identity.lineage_id == lineage_id
    assert identity.version == version
    assert identity.is_initial is (version == 1)


@settings(max_examples=100, deadline=None)
@given(version=st.integers(max_value=0))
def test_non_positive_versions_always_rejected(version):
    with pytest.raises(VersionSequenceError):
        ObjectIdentity(object_id="obj-x", lineage_id="lin-x", version=version)


@settings(max_examples=100, deadline=None)
@given(
    blank=st.sampled_from(["", None]),
    which=st.sampled_from(["object_id", "lineage_id"]),
)
def test_empty_identifiers_always_rejected(blank, which):
    kwargs = {"object_id": "obj-x", "lineage_id": "lin-x", "version": 1}
    kwargs[which] = blank
    with pytest.raises(IdentityError):
        ObjectIdentity(**kwargs)


@settings(max_examples=150, deadline=None)
@given(
    gap=st.integers(min_value=2, max_value=100).filter(lambda n: n != 1),
)
def test_any_version_gap_is_rejected(gap):
    """validate_succession accepts +1 only, for any other delta. [V11]"""
    allocator = IdentityAllocator()
    first = allocator.new_object()
    bad = ObjectIdentity(
        object_id="obj-successor",
        lineage_id=first.lineage_id,
        version=first.version + gap,
    )
    with pytest.raises(VersionSequenceError):
        allocator.validate_succession(first, bad)


@settings(max_examples=150, deadline=None)
@given(depth=st.integers(min_value=1, max_value=30))
def test_branching_rejected_at_any_depth(depth):
    """Succeeding an already-superseded version fails wherever it sits."""
    allocator = IdentityAllocator()
    current = allocator.new_object()
    for _ in range(depth - 1):
        current = allocator.succeed(current)

    allocator.succeed(current)
    with pytest.raises(BranchingError):
        allocator.succeed(current)


@settings(max_examples=100, deadline=None)
@given(
    versions=st.lists(
        st.integers(min_value=1, max_value=500), min_size=1, max_size=25, unique=True
    )
)
def test_adopt_then_succeed_preserves_invariants(versions):
    """Rehydrated identities continue their chains correctly. [I2]"""
    allocator = IdentityAllocator()
    adopted = [
        ObjectIdentity(
            object_id=f"obj-stored-{n}", lineage_id=f"lin-stored-{n}", version=n
        )
        for n in versions
    ]
    allocator.adopt(adopted)

    for identity in adopted:
        assert allocator.is_issued(identity.object_id)
        successor = allocator.succeed(identity)
        assert successor.version == identity.version + 1
        assert successor.lineage_id == identity.lineage_id
        assert successor.object_id != identity.object_id
