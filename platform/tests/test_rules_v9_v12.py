"""Contract tests for universal validation rules V9-V12.

Task: T01.4.4

Architecture References:
- V9    status_reason required when status is not ACTIVE
- V10   No lineage cycle may be introduced
- V11   version = predecessor + 1; lineage_id (and type) unchanged
- V12   All relationships drawn from the closed taxonomy
- R-1   Immutable versioned objects; linear supersession
- R-2   Seven-state lifecycle
- R-6   Closed ten-type relationship taxonomy; no self-reference
- R-8   Behavioural loop closure keeps lineage acyclic
- AD-05 No platform artifact may become Evidence
- I2    object_id never reused

Acceptance criteria under test:
  AC1  Each rule independently testable
  AC2  V11 enforces version and lineage_id integrity

Layers: unit (rule in isolation), edge cases, integration (through the store),
cross-rule compatibility with V1-V8, and property-based.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import (
    UNIVERSAL_RULES,
    AcceptanceContext,
    AcceptancePath,
    RuleOutcome,
    v9_status_reason,
    v10_no_cycle,
    v11_version_increment,
    v12_closed_taxonomy,
)
from oip.contract import Explanation, LineageRef, UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType, RelationshipType
from oip.identity import IdentityAllocator, ObjectIdentity
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import (
    build_attrs,
    build_lineage,
    write_evidence,
)

TERMINAL = [s for s in ObjectStatus if s.is_terminal]
NON_ACTIVE = [s for s in ObjectStatus if s is not ObjectStatus.ACTIVE]


def A(allocator: IdentityAllocator, **overrides) -> UniversalAttributes:
    """A Fact deriving from one Evidence reference, unless overridden."""
    identity = overrides.pop("identity", None) or allocator.new_object()
    upstream = overrides.pop(
        "upstream", (("obj-ev-1", ObjectType.EVIDENCE),)
    )
    return build_attrs(
        identity,
        overrides.pop("object_type", ObjectType.FACT),
        upstream,
        status=overrides.pop("status", ObjectStatus.ACTIVE),
        status_reason=overrides.pop("status_reason", None),
        **overrides,
    )


def ctx(attributes, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": attributes}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


# ===========================================================================
# V9 -- status_reason
# ===========================================================================

class TestV9Unit:
    def test_active_needs_no_reason(self, allocator):
        result = v9_status_reason(ctx(A(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "no reason" in result.detail

    @pytest.mark.parametrize("status", NON_ACTIVE)
    def test_every_non_active_requires_a_reason(self, allocator, status):
        a = A(allocator, status=status, status_reason="recorded")
        assert not v9_status_reason(ctx(a)).failed

    @pytest.mark.parametrize("status", NON_ACTIVE)
    def test_missing_reason_fails_for_every_non_active(self, allocator, status):
        a = A(allocator, status=status, status_reason="placeholder")
        object.__setattr__(a, "status_reason", None)
        result = v9_status_reason(ctx(a))
        assert result.failed
        assert status.value in result.detail

    @pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", "  \n  "])
    def test_whitespace_is_not_a_reason(self, allocator, blank):
        a = A(allocator, status=ObjectStatus.REJECTED, status_reason="temp")
        object.__setattr__(a, "status_reason", blank)
        assert v9_status_reason(ctx(a)).failed

    def test_reason_on_active_is_tolerated(self, allocator):
        """A reason is required when non-ACTIVE, not forbidden when ACTIVE."""
        a = A(allocator, status=ObjectStatus.ACTIVE, status_reason=None)
        object.__setattr__(a, "status_reason", "informational")
        assert not v9_status_reason(ctx(a)).failed

    def test_detail_names_the_status(self, allocator):
        a = A(allocator, status=ObjectStatus.RETRACTED, status_reason="withdrawn")
        assert "RETRACTED" in v9_status_reason(ctx(a)).detail


class TestV9Integration:
    def test_contract_blocks_missing_reason_at_construction(self, allocator):
        """V9 is enforced twice: at construction and at acceptance."""
        from oip.contract import StatusReasonError
        with pytest.raises(StatusReasonError):
            A(allocator, status=ObjectStatus.REJECTED, status_reason=None)

    def test_store_rejects_rehydrated_missing_reason(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        object.__setattr__(attrs, "status", ObjectStatus.REJECTED)
        object.__setattr__(attrs, "status_reason", None)
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
            )
        assert "V9" in exc.value.failure.rule_ids


# ===========================================================================
# V10 -- no lineage cycle
# ===========================================================================

class TestV10Unit:
    def test_acyclic_passes(self, allocator):
        a = A(allocator)
        assert not v10_no_cycle(ctx(a, would_cycle=lambda f, t: False)).failed

    def test_provider_reported_cycle_fails(self, allocator):
        a = A(allocator)
        result = v10_no_cycle(ctx(a, would_cycle=lambda f, t: True))
        assert result.failed
        assert "would create a cycle" in result.detail

    def test_detail_names_the_offending_edge(self, allocator):
        a = A(allocator)
        detail = v10_no_cycle(ctx(a, would_cycle=lambda f, t: True)).detail
        assert a.object_id in detail and "obj-ev-1" in detail

    def test_evidence_has_no_edges_to_check(self, allocator):
        a = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert not v10_no_cycle(ctx(a, would_cycle=lambda f, t: True)).failed

    def test_first_cyclic_edge_of_many_is_reported(self, allocator):
        upstream = tuple((f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(5))
        a = A(allocator, upstream=upstream)
        cyclic = {"obj-ev-3"}
        result = v10_no_cycle(
            ctx(a, would_cycle=lambda f, t: t in cyclic)
        )
        assert result.failed
        assert "obj-ev-3" in result.detail


class TestV10SelfReference:
    """Self-reference is a cycle by definition and must not depend on a provider."""

    def test_self_reference_fails_without_a_provider(self, allocator):
        a = A(allocator)
        object.__setattr__(
            a, "derives_from", (LineageRef(a.object_id, ObjectType.EVIDENCE),)
        )
        result = v10_no_cycle(ctx(a, would_cycle=None))
        assert result.failed
        assert "derives from itself" in result.detail

    def test_self_reference_fails_despite_a_naive_provider(self, allocator):
        """The regression that motivated the fix."""
        a = A(allocator)
        object.__setattr__(
            a, "derives_from", (LineageRef(a.object_id, ObjectType.EVIDENCE),)
        )
        assert v10_no_cycle(ctx(a, would_cycle=lambda f, t: False)).failed

    def test_self_reference_among_valid_parents_detected(self, allocator):
        a = A(allocator)
        object.__setattr__(
            a,
            "derives_from",
            (
                LineageRef("obj-ev-1", ObjectType.EVIDENCE),
                LineageRef(a.object_id, ObjectType.EVIDENCE),
                LineageRef("obj-ev-2", ObjectType.EVIDENCE),
            ),
        )
        assert v10_no_cycle(ctx(a, would_cycle=lambda f, t: False)).failed

    def test_no_provider_skips_only_after_self_check(self, allocator):
        result = v10_no_cycle(ctx(A(allocator), would_cycle=None))
        assert result.outcome is RuleOutcome.SKIP
        assert "self-reference clear" in result.detail

    def test_lineage_blocks_self_reference_at_construction(self):
        """Defence in depth: Lineage refuses it too."""
        from oip.lineage import LineageError, derive
        with pytest.raises(LineageError):
            derive("obj-x", ObjectType.FACT, [("obj-x", ObjectType.EVIDENCE)])


class TestV10Integration:
    def test_store_supplies_a_real_cycle_provider(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        result = AcceptancePath().evaluate(
            AcceptanceContext(
                attributes=attrs,
                would_cycle=store.graph.would_introduce_cycle,
            )
        )
        v10 = next(r for r in result if r.rule_id == "V10")
        assert not v10.failed

    def test_feedback_cannot_close_the_loop_to_evidence(self, store, allocator):
        """AD-05 / R-8: the lineage graph stays acyclic."""
        evidence = write_evidence(store, allocator)
        assert not store.graph.would_introduce_cycle(
            "obj-new", evidence.object_id
        )


# ===========================================================================
# V11 -- version and lineage integrity  (AC2)
# ===========================================================================

class TestV11InitialVersion:
    def test_version_one_without_predecessor_passes(self, allocator):
        result = v11_version_increment(ctx(A(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "initial version" in result.detail

    def test_version_two_without_predecessor_fails(self, allocator):
        first = allocator.new_object()
        second = allocator.succeed(first)
        a = A(allocator, identity=second)
        result = v11_version_increment(ctx(a))
        assert result.failed
        assert "first version must be 1" in result.detail

    def test_detail_suggests_declaring_a_predecessor(self, allocator):
        first = allocator.new_object()
        a = A(allocator, identity=allocator.succeed(first))
        assert "predecessor" in v11_version_increment(ctx(a)).detail


class TestV11Succession:
    def _pair(self, allocator, **successor_overrides):
        first = allocator.new_object()
        second = allocator.succeed(first)
        predecessor = A(allocator, identity=first)
        successor = A(allocator, identity=second, **successor_overrides)
        return predecessor, successor

    def test_valid_succession_passes(self, allocator):
        predecessor, successor = self._pair(allocator)
        result = v11_version_increment(
            ctx(successor, predecessor=predecessor)
        )
        assert not result.failed
        assert "1 -> 2" in result.detail

    def test_lineage_id_must_be_constant(self, allocator):
        """AC2: lineage_id integrity."""
        predecessor = A(allocator)
        successor = A(allocator)  # independently allocated: different lineage
        result = v11_version_increment(ctx(successor, predecessor=predecessor))
        assert result.failed
        assert "lineage_id must be constant" in result.detail

    def test_version_must_increment_by_exactly_one(self, allocator):
        """AC2: version integrity."""
        first = allocator.new_object()
        third = allocator.succeed(allocator.succeed(first))
        predecessor = A(allocator, identity=first)
        successor = A(allocator, identity=third)
        result = v11_version_increment(ctx(successor, predecessor=predecessor))
        assert result.failed
        assert "increment by 1" in result.detail

    def test_repeated_version_rejected(self, allocator):
        first = allocator.new_object()
        predecessor = A(allocator, identity=first)
        same = ObjectIdentity(
            object_id="obj-different", lineage_id=first.lineage_id, version=1
        )
        successor = A(allocator, identity=same)
        assert v11_version_increment(
            ctx(successor, predecessor=predecessor)
        ).failed

    def test_reused_object_id_rejected(self, allocator):
        """I2: a new version requires a new object_id."""
        first = allocator.new_object()
        predecessor = A(allocator, identity=first)
        reused = ObjectIdentity(
            object_id=first.object_id,
            lineage_id=first.lineage_id,
            version=2,
        )
        successor = A(allocator, identity=reused)
        result = v11_version_increment(ctx(successor, predecessor=predecessor))
        assert result.failed
        assert "new object_id" in result.detail

    def test_object_type_must_be_constant(self, allocator):
        """A chain holds versions of one logical object. [R-1]"""
        first = allocator.new_object()
        second = allocator.succeed(first)
        predecessor = A(allocator, identity=first, object_type=ObjectType.FACT)
        successor = A(
            allocator,
            identity=second,
            object_type=ObjectType.PROBLEM,
            upstream=(("obj-fa-1", ObjectType.FACT),),
            engine=Engine.PROBLEM_INTELLIGENCE,
            explanation=Explanation(("obj-fa-1",), ("c",), "r"),
        )
        result = v11_version_increment(ctx(successor, predecessor=predecessor))
        assert result.failed
        assert "object_type must be constant" in result.detail

    def test_long_chain_each_step_valid(self, allocator):
        current = allocator.new_object()
        predecessor = A(allocator, identity=current)
        for _ in range(20):
            nxt = allocator.succeed(current)
            successor = A(allocator, identity=nxt)
            assert not v11_version_increment(
                ctx(successor, predecessor=predecessor)
            ).failed
            current, predecessor = nxt, successor


class TestV11Integration:
    def test_store_rejects_unversioned_second_write(self, store, allocator):
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

    def test_store_accepts_declared_succession(self, store, allocator):
        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        successor = allocator.succeed(first.attributes.identity)
        attrs = build_attrs(
            successor, ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        stored = store.write(
            attrs, build_lineage(successor.object_id, ObjectType.EVIDENCE),
            predecessor_id=first.object_id,
        )
        assert stored.attributes.version == 2
        assert stored.lineage_id == first.lineage_id


# ===========================================================================
# V12 -- closed taxonomy
# ===========================================================================

class TestV12Unit:
    def test_conforming_object_passes(self, allocator):
        result = v12_closed_taxonomy(ctx(A(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "conform" in result.detail

    def test_unknown_lineage_type_fails(self, allocator):
        a = A(allocator)
        bad = LineageRef.__new__(LineageRef)
        object.__setattr__(bad, "object_id", "obj-ev-1")
        object.__setattr__(bad, "object_type", "Evidence")
        object.__setattr__(a, "derives_from", (bad,))
        result = v12_closed_taxonomy(ctx(a))
        assert result.failed
        assert "DERIVES_FROM" in result.detail

    def test_taxonomy_has_exactly_ten_members(self):
        assert len(RelationshipType) == 10

    def test_valid_peer_relationships_pass(self, allocator):
        a = A(allocator, duplicates=("obj-fa-9",), contradicts=("obj-fa-8",))
        assert not v12_closed_taxonomy(ctx(a)).failed

    def test_valid_supersession_references_pass(self, allocator):
        a = A(allocator, supersedes="obj-fa-0", superseded_by="obj-fa-2")
        assert not v12_closed_taxonomy(ctx(a)).failed


class TestV12PeerRelationships:
    """R-6 forbids self-reference on every relationship, not lineage alone."""

    def test_self_duplicate_rejected(self, allocator):
        a = A(allocator)
        object.__setattr__(a, "duplicates", (a.object_id,))
        result = v12_closed_taxonomy(ctx(a))
        assert result.failed
        assert "DUPLICATES" in result.detail

    def test_self_contradiction_rejected(self, allocator):
        a = A(allocator)
        object.__setattr__(a, "contradicts", (a.object_id,))
        result = v12_closed_taxonomy(ctx(a))
        assert result.failed
        assert "CONTRADICTS" in result.detail

    def test_self_supersedes_rejected(self, allocator):
        a = A(allocator)
        object.__setattr__(a, "supersedes", a.object_id)
        result = v12_closed_taxonomy(ctx(a))
        assert result.failed
        assert "SUPERSEDES" in result.detail

    def test_self_superseded_by_rejected(self, allocator):
        a = A(allocator)
        object.__setattr__(a, "superseded_by", a.object_id)
        result = v12_closed_taxonomy(ctx(a))
        assert result.failed
        assert "SUPERSEDED_BY" in result.detail

    def test_empty_peer_target_rejected(self, allocator):
        a = A(allocator)
        object.__setattr__(a, "duplicates", ("",))
        assert v12_closed_taxonomy(ctx(a)).failed

    def test_self_reference_among_valid_peers_detected(self, allocator):
        a = A(allocator)
        object.__setattr__(
            a, "contradicts", ("obj-other-1", a.object_id, "obj-other-2")
        )
        assert v12_closed_taxonomy(ctx(a)).failed

    def test_relationship_construction_agrees(self):
        """Defence in depth: Relationship refuses self-reference too. [R-6]"""
        from datetime import datetime, timezone
        from oip.relationships import Relationship, SelfReferenceError
        with pytest.raises(SelfReferenceError):
            Relationship(
                relationship_type=RelationshipType.DUPLICATES,
                from_object_id="obj-same",
                from_type=ObjectType.FACT,
                to_object_id="obj-same",
                to_type=ObjectType.FACT,
                asserted_by_engine=Engine.FACT_EXTRACTION,
                asserted_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            )


class TestV12Integration:
    def test_store_rejects_self_duplicate(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        object.__setattr__(attrs, "duplicates", (identity.object_id,))
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
            )
        assert "V12" in exc.value.failure.rule_ids


# ===========================================================================
# Cross-rule behaviour and V1-V8 compatibility
# ===========================================================================

class TestRulesTogether:
    def test_all_twelve_rules_registered(self):
        assert len(UNIVERSAL_RULES) == 12
        assert {r.rule_id for r in UNIVERSAL_RULES} == {
            f"V{i}" for i in range(1, 13)
        }

    def test_rule_ids_are_stable(self):
        assert v9_status_reason.rule_id == "V9"
        assert v10_no_cycle.rule_id == "V10"
        assert v11_version_increment.rule_id == "V11"
        assert v12_closed_taxonomy.rule_id == "V12"

    def test_each_rule_runs_independently(self, allocator):
        """AC1: no rule depends on another having run."""
        a = A(allocator)
        for rule in (
            v9_status_reason, v10_no_cycle,
            v11_version_increment, v12_closed_taxonomy,
        ):
            assert rule(ctx(a)).outcome in (RuleOutcome.PASS, RuleOutcome.SKIP)

    def test_all_four_reported_without_short_circuit(self, allocator):
        a = A(allocator, status=ObjectStatus.REJECTED, status_reason="declined")
        object.__setattr__(a, "status_reason", None)
        object.__setattr__(
            a, "derives_from", (LineageRef(a.object_id, ObjectType.EVIDENCE),)
        )
        object.__setattr__(a, "duplicates", (a.object_id,))
        first = allocator.new_object()
        predecessor = A(allocator, identity=first)

        results = {
            r.rule_id: r
            for r in AcceptancePath().evaluate(ctx(a, predecessor=predecessor))
        }
        for rule_id in ("V9", "V10", "V11", "V12"):
            assert results[rule_id].failed, f"{rule_id} did not fail"

    def test_v1_to_v8_unaffected_by_the_fixes(self, allocator):
        """Compatibility: earlier rules behave exactly as before."""
        a = A(allocator)
        results = {
            r.rule_id: r
            for r in AcceptancePath().evaluate(
                ctx(
                    a,
                    resolve_type=lambda oid: ObjectType.EVIDENCE,
                    reaches_evidence=lambda oid: True,
                    would_cycle=lambda f, t: False,
                    upstream_confidence=lambda oid: 0.9,
                )
            )
        }
        for rule_id in (f"V{i}" for i in range(1, 9)):
            assert not results[rule_id].failed, f"{rule_id} regressed"

    def test_valid_object_passes_all_twelve(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        stored = store.write(
            attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_failure_record_lists_every_broken_rule(self, allocator):
        a = A(allocator)
        object.__setattr__(
            a, "derives_from", (LineageRef(a.object_id, ObjectType.EVIDENCE),)
        )
        object.__setattr__(a, "supersedes", a.object_id)
        result = AcceptancePath().accept(ctx(a))
        assert {"V10", "V12"} <= set(result.failure.rule_ids)


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(status=st.sampled_from(list(ObjectStatus)), reason=st.text(max_size=30))
def test_v9_decision_matches_the_requirement(status, reason):
    """V9 fails exactly when a non-ACTIVE status lacks a usable reason."""
    allocator = IdentityAllocator()
    a = A(allocator, status=ObjectStatus.ACTIVE, status_reason=None)
    object.__setattr__(a, "status", status)
    object.__setattr__(a, "status_reason", reason)

    expected_fail = status.requires_reason and not reason.strip()
    assert v9_status_reason(ctx(a)).failed is expected_fail


@settings(max_examples=200, deadline=None)
@given(parents=st.integers(min_value=1, max_value=8),
       self_index=st.integers(min_value=0, max_value=7))
def test_v10_always_catches_self_reference(parents, self_index):
    """Position in the upstream list never hides a self-reference."""
    allocator = IdentityAllocator()
    a = A(allocator)
    index = self_index % parents
    refs = [
        LineageRef(f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(parents)
    ]
    refs[index] = LineageRef(a.object_id, ObjectType.EVIDENCE)
    object.__setattr__(a, "derives_from", tuple(refs))
    assert v10_no_cycle(ctx(a, would_cycle=lambda f, t: False)).failed


@settings(max_examples=200, deadline=None)
@given(gap=st.integers(min_value=-5, max_value=5))
def test_v11_accepts_only_an_increment_of_one(gap):
    """AC2: version integrity over arbitrary offsets."""
    allocator = IdentityAllocator()
    first = allocator.new_object()
    predecessor = A(allocator, identity=first)
    target_version = first.version + gap
    if target_version < 1:
        return
    successor = A(
        allocator,
        identity=ObjectIdentity(
            object_id="obj-successor",
            lineage_id=first.lineage_id,
            version=target_version,
        ),
    )
    result = v11_version_increment(ctx(successor, predecessor=predecessor))
    assert result.failed is (gap != 1)


@settings(max_examples=200, deadline=None)
@given(same_lineage=st.booleans(), same_type=st.booleans())
def test_v11_requires_both_lineage_and_type_stability(same_lineage, same_type):
    """AC2: lineage_id integrity, plus type invariance. [R-1]"""
    allocator = IdentityAllocator()
    first = allocator.new_object()
    second = allocator.succeed(first)
    predecessor = A(allocator, identity=first, object_type=ObjectType.FACT)

    lineage_id = first.lineage_id if same_lineage else "lin-different"
    object_type = ObjectType.FACT if same_type else ObjectType.PROBLEM
    upstream = (
        (("obj-ev-1", ObjectType.EVIDENCE),) if same_type
        else (("obj-fa-1", ObjectType.FACT),)
    )
    successor = A(
        allocator,
        identity=ObjectIdentity(
            object_id=second.object_id, lineage_id=lineage_id, version=2
        ),
        object_type=object_type,
        upstream=upstream,
        engine=(
            Engine.FACT_EXTRACTION if same_type else Engine.PROBLEM_INTELLIGENCE
        ),
        explanation=Explanation((upstream[0][0],), ("c",), "r"),
    )
    result = v11_version_increment(ctx(successor, predecessor=predecessor))
    assert result.failed is not (same_lineage and same_type)


@settings(max_examples=200, deadline=None)
@given(
    duplicates=st.lists(st.text(min_size=1, max_size=12), max_size=4),
    contradicts=st.lists(st.text(min_size=1, max_size=12), max_size=4),
)
def test_v12_passes_when_no_peer_is_self(duplicates, contradicts):
    allocator = IdentityAllocator()
    a = A(allocator)
    object.__setattr__(a, "duplicates", tuple(duplicates))
    object.__setattr__(a, "contradicts", tuple(contradicts))
    references_self = a.object_id in set(duplicates) | set(contradicts)
    assert v12_closed_taxonomy(ctx(a)).failed is references_self


@settings(max_examples=150, deadline=None)
@given(object_type=st.sampled_from(list(ObjectType)))
def test_v12_conformance_holds_for_every_object_type(object_type):
    allocator = IdentityAllocator()
    a = build_attrs(
        allocator.new_object(), object_type,
        () if object_type.is_root else (("obj-up", ObjectType.EVIDENCE),),
        status=ObjectStatus.ACTIVE, status_reason=None,
    )
    assert not v12_closed_taxonomy(ctx(a)).failed
