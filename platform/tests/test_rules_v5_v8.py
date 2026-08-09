"""Contract tests for universal validation rules V5-V8.

Task: T01.4.3

Architecture References:
- V5    effective_confidence <= min(upstream effective_confidence)
- V6    Explanation references at least one consumed input
- V7    Producing engine holds create authority
- V8    observed_at <= asserted_at <= produced_at
- R-3   Two-component confidence; monotonic ceiling
- N-13  Explanation skeleton
- N-10  Failure produces a record, never a crash
- C-02  ExecutionRecord has no create authority (open)
- AD-04 Orchestration creates no objects

Acceptance criteria under test:
  AC1  V5 rejects any object exceeding min(upstream effective_confidence)
  AC2  V7 rejects writes from engines lacking create authority
  AC3  V8 enforces observed_at <= asserted_at <= produced_at

Layers: unit (rule in isolation), integration (through the store write path),
and edge cases (boundaries, malformed input, partial resolution).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from oip.acceptance import (
    AcceptanceContext,
    AcceptancePath,
    RuleOutcome,
    v5_confidence_ceiling,
    v6_explanation_references_inputs,
    v7_create_authority,
    v8_temporal_order,
)
from oip.contract import Confidence, Explanation, LineageRef, UniversalAttributes
from oip.enums import CREATE_AUTHORITY, Engine, ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import (
    T0,
    build_attrs,
    build_lineage,
    write_derived,
    write_evidence,
)

CONF = st.floats(min_value=0.0, max_value=1.0, allow_nan=False,
                 allow_infinity=False)


def attrs_with(allocator: IdentityAllocator, **overrides) -> UniversalAttributes:
    """A Fact deriving from two Evidence references, unless overridden."""
    upstream = overrides.pop(
        "upstream",
        (("obj-ev-1", ObjectType.EVIDENCE), ("obj-ev-2", ObjectType.EVIDENCE)),
    )
    return build_attrs(
        allocator.new_object(),
        overrides.pop("object_type", ObjectType.FACT),
        upstream,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        **overrides,
    )


def ctx(attributes, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": attributes, "upstream_confidence": lambda oid: 0.9}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


# ===========================================================================
# V5 -- confidence ceiling  (AC1)
# ===========================================================================

class TestV5Unit:
    def test_within_ceiling_passes(self, allocator):
        a = attrs_with(allocator, support=0.5, assertion=0.5)
        result = v5_confidence_ceiling(ctx(a, upstream_confidence=lambda o: 0.9))
        assert result.outcome is RuleOutcome.PASS
        assert "0.9" in result.detail

    def test_exceeding_ceiling_fails(self, allocator):
        a = attrs_with(allocator, support=0.95, assertion=0.95)
        result = v5_confidence_ceiling(ctx(a, upstream_confidence=lambda o: 0.4))
        assert result.failed
        assert "exceeds upstream ceiling" in result.detail

    def test_exactly_at_ceiling_passes(self, allocator):
        """Boundary: <= is inclusive."""
        a = attrs_with(allocator, support=0.6, assertion=0.6)
        assert not v5_confidence_ceiling(
            ctx(a, upstream_confidence=lambda o: 0.6)
        ).failed

    def test_minimum_across_parents_binds(self, allocator):
        """AC1: min(), not max() or mean(). [R-3]"""
        a = attrs_with(allocator, support=0.5, assertion=0.5)
        ceilings = {"obj-ev-1": 0.9, "obj-ev-2": 0.3}
        assert v5_confidence_ceiling(
            ctx(a, upstream_confidence=ceilings.get)
        ).failed

    def test_detail_names_the_binding_set(self, allocator):
        a = attrs_with(allocator, support=0.8, assertion=0.8)
        ceilings = {"obj-ev-1": 0.7, "obj-ev-2": 0.2}
        detail = v5_confidence_ceiling(
            ctx(a, upstream_confidence=ceilings.get)
        ).detail
        assert "0.2" in detail

    def test_no_upstream_skips(self, allocator):
        a = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = v5_confidence_ceiling(ctx(a))
        assert result.outcome is RuleOutcome.SKIP
        assert "does not apply" in result.detail

    def test_no_provider_skips(self, allocator):
        result = v5_confidence_ceiling(
            ctx(attrs_with(allocator), upstream_confidence=None)
        )
        assert result.outcome is RuleOutcome.SKIP


class TestV5EdgeCases:
    def test_unresolvable_upstream_fails_closed(self, allocator):
        """A ceiling cannot be established from a partial upstream set."""
        a = attrs_with(allocator, support=0.9, assertion=0.9)
        result = v5_confidence_ceiling(ctx(a, upstream_confidence=lambda o: None))
        assert result.failed
        assert "unresolvable" in result.detail

    def test_partially_resolved_upstream_fails_closed(self, allocator):
        """The regression that motivated the fix: one parent unreadable.

        Passing on the resolved subset would let an object exceed the
        confidence of a parent nobody could read. [R-3]
        """
        a = attrs_with(allocator, support=0.9, assertion=0.9)
        partial = {"obj-ev-1": 0.9}
        result = v5_confidence_ceiling(ctx(a, upstream_confidence=partial.get))
        assert result.failed
        assert "obj-ev-2" in result.detail

    def test_zero_ceiling_rejects_any_positive_confidence(self, allocator):
        a = attrs_with(allocator, support=0.01, assertion=0.01)
        assert v5_confidence_ceiling(
            ctx(a, upstream_confidence=lambda o: 0.0)
        ).failed

    def test_zero_confidence_under_zero_ceiling_passes(self, allocator):
        a = attrs_with(allocator, support=0.0, assertion=0.0)
        assert not v5_confidence_ceiling(
            ctx(a, upstream_confidence=lambda o: 0.0)
        ).failed

    def test_floating_point_tolerance(self, allocator):
        """0.1+0.2 style drift must not fail a legitimate object."""
        a = attrs_with(allocator, support=0.1 + 0.2, assertion=1.0)
        assert not v5_confidence_ceiling(
            ctx(a, upstream_confidence=lambda o: 0.3)
        ).failed

    def test_many_parents_all_resolved(self, allocator):
        upstream = tuple((f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(30))
        a = attrs_with(allocator, upstream=upstream, support=0.4, assertion=0.4)
        ceilings = {f"obj-ev-{i}": 0.5 + i / 100 for i in range(30)}
        assert not v5_confidence_ceiling(
            ctx(a, upstream_confidence=ceilings.get)
        ).failed

    def test_one_weak_parent_among_many_binds(self, allocator):
        upstream = tuple((f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(30))
        a = attrs_with(allocator, upstream=upstream, support=0.6, assertion=0.6)
        ceilings = {f"obj-ev-{i}": 0.9 for i in range(30)}
        ceilings["obj-ev-17"] = 0.1
        assert v5_confidence_ceiling(
            ctx(a, upstream_confidence=ceilings.get)
        ).failed


class TestV5Integration:
    def test_store_rejects_ceiling_violation(self, store, allocator):
        evidence = write_evidence(store, allocator, support=0.30, assertion=0.90)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            support=0.95, assertion=0.95,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
            )
        assert "V5" in exc.value.failure.rule_ids
        assert not store.contains(identity.object_id)

    def test_store_accepts_within_ceiling(self, store, allocator):
        evidence = write_evidence(store, allocator, support=0.62, assertion=0.90)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert fact.attributes.confidence.effective_confidence <= 0.62

    def test_weakest_parent_binds_through_store(self, store, allocator):
        weak = write_evidence(store, allocator, support=0.25, assertion=0.99)
        strong = write_evidence(store, allocator, support=0.99, assertion=0.99)
        fact = write_derived(store, allocator, ObjectType.FACT, [weak, strong])
        assert fact.attributes.confidence.effective_confidence <= 0.25


# ===========================================================================
# V6 -- explanation references consumed inputs
# ===========================================================================

class TestV6Unit:
    def test_referencing_a_consumed_input_passes(self, allocator):
        a = attrs_with(allocator)
        assert not v6_explanation_references_inputs(ctx(a)).failed

    def test_referencing_nothing_consumed_fails(self, allocator):
        a = attrs_with(
            allocator,
            explanation=Explanation(("obj-unrelated",), ("c",), "r"),
        )
        result = v6_explanation_references_inputs(ctx(a))
        assert result.failed
        assert "actually consumed" in result.detail

    def test_partial_overlap_passes(self, allocator):
        """Referencing a subset of inputs is legitimate. [N-13]"""
        a = attrs_with(
            allocator,
            explanation=Explanation(("obj-ev-2", "obj-elsewhere"), ("c",), "r"),
        )
        assert not v6_explanation_references_inputs(ctx(a)).failed

    def test_evidence_exempt_from_upstream_overlap(self, allocator):
        """Evidence has no upstream; it references acquisition sources."""
        a = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = v6_explanation_references_inputs(ctx(a))
        assert not result.failed
        assert "acquisition" in result.detail

    def test_empty_reference_set_fails(self, allocator):
        a = attrs_with(allocator)
        broken = Explanation.__new__(Explanation)
        object.__setattr__(broken, "objects_referenced", ())
        object.__setattr__(broken, "criteria_applied", ("c",))
        object.__setattr__(broken, "reasoning", "r")
        object.__setattr__(broken, "alternatives_rejected", ())
        object.__setattr__(a, "explanation", broken)
        assert v6_explanation_references_inputs(ctx(a)).failed


class TestV6Integration:
    def test_store_rejects_disconnected_explanation(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
            explanation=Explanation(("obj-never-read",), ("c",), "r"),
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
            )
        assert "V6" in exc.value.failure.rule_ids


# ===========================================================================
# V7 -- create authority  (AC2)
# ===========================================================================

class TestV7Unit:
    @pytest.mark.parametrize("object_type,engine", sorted(
        CREATE_AUTHORITY.items(), key=lambda kv: kv[0].value
    ))
    def test_authorised_engine_passes(self, allocator, object_type, engine):
        a = build_attrs(
            allocator.new_object(), object_type,
            () if object_type.is_root
            else (("obj-up", ObjectType.EVIDENCE),),
            engine=engine, status=ObjectStatus.ACTIVE, status_reason=None,
        )
        assert not v7_create_authority(ctx(a)).failed

    def test_wrong_engine_fails(self, allocator):
        a = attrs_with(allocator, engine=Engine.PATTERN_INTELLIGENCE)
        result = v7_create_authority(ctx(a))
        assert result.failed
        assert "authority is FactExtraction" in result.detail

    @pytest.mark.parametrize(
        "engine", [e for e in Engine if e is not Engine.FACT_EXTRACTION]
    )
    def test_every_unauthorised_engine_rejected(self, allocator, engine):
        """AC2: exactly one engine may create each type."""
        a = attrs_with(allocator, engine=engine)
        assert v7_create_authority(ctx(a)).failed

    def test_orchestration_creates_nothing(self, allocator):
        """AD-04: Orchestration sequences but never authors."""
        for object_type in ObjectType:
            a = build_attrs(
                allocator.new_object(), object_type,
                () if object_type.is_root
                else (("obj-up", ObjectType.EVIDENCE),),
                engine=Engine.ORCHESTRATION,
                status=ObjectStatus.ACTIVE, status_reason=None,
            )
            assert v7_create_authority(ctx(a)).failed

    def test_execution_record_has_no_authority(self, allocator):
        """C-02 remains open: no engine may author an ExecutionRecord."""
        for engine in Engine:
            a = build_attrs(
                allocator.new_object(), ObjectType.EXECUTION_RECORD,
                (("obj-so-1", ObjectType.SOLUTION),),
                engine=engine, status=ObjectStatus.ACTIVE, status_reason=None,
            )
            result = v7_create_authority(ctx(a))
            assert result.failed
            assert "C-02" in result.detail

    def test_authority_map_is_injective(self):
        engines = list(CREATE_AUTHORITY.values())
        assert len(engines) == len(set(engines))

    def test_eight_of_nine_types_have_authority(self):
        assert len(CREATE_AUTHORITY) == 8
        assert ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY


class TestV7Integration:
    def test_store_rejects_unauthorised_engine(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            engine=Engine.SOLUTION_INTELLIGENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
            )
        assert "V7" in exc.value.failure.rule_ids

    def test_store_refuses_execution_records_entirely(self, store, allocator):
        """The platform will not author an object no engine may create. [C-02]"""
        solution = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((solution.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.EXECUTION_RECORD, upstream,
            engine=Engine.RESEARCH,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=solution.attributes.confidence.effective_confidence,
        )
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs,
                build_lineage(
                    identity.object_id, ObjectType.EXECUTION_RECORD, upstream
                ),
            )
        assert "V7" in exc.value.failure.rule_ids


# ===========================================================================
# V8 -- temporal ordering  (AC3)
# ===========================================================================

class TestV8Unit:
    def test_strict_ordering_passes(self, allocator):
        assert not v8_temporal_order(ctx(attrs_with(allocator))).failed

    def test_all_equal_passes(self, allocator):
        a = attrs_with(
            allocator, observed_at=T0, asserted_at=T0, produced_at=T0
        )
        assert not v8_temporal_order(ctx(a)).failed

    def test_observed_after_asserted_fails(self, allocator):
        a = attrs_with(allocator)
        object.__setattr__(a, "observed_at", T0 + timedelta(hours=9))
        result = v8_temporal_order(ctx(a))
        assert result.failed
        assert "observed_at" in result.detail and "asserted_at" in result.detail

    def test_asserted_after_produced_fails(self, allocator):
        a = attrs_with(allocator)
        object.__setattr__(a, "asserted_at", T0 + timedelta(hours=9))
        result = v8_temporal_order(ctx(a))
        assert result.failed
        assert "asserted_at" in result.detail and "produced_at" in result.detail

    def test_the_two_violations_are_distinguishable(self, allocator):
        """A shared message would hide which boundary was breached."""
        first = attrs_with(allocator)
        object.__setattr__(first, "observed_at", T0 + timedelta(hours=9))
        second = attrs_with(allocator)
        object.__setattr__(second, "asserted_at", T0 + timedelta(hours=9))
        assert v8_temporal_order(ctx(first)).detail != \
            v8_temporal_order(ctx(second)).detail

    def test_observation_long_before_assertion_passes(self, allocator):
        """R-4: observed_at may substantially precede assertion."""
        a = attrs_with(allocator, observed_at=T0 - timedelta(days=3650))
        assert not v8_temporal_order(ctx(a)).failed


class TestV8EdgeCases:
    def test_naive_timestamp_fails_rather_than_crashing(self, allocator):
        """A rehydrated naive timestamp must not take down acceptance. [N-10]"""
        a = attrs_with(allocator)
        object.__setattr__(a, "observed_at", datetime(2026, 3, 1))
        result = v8_temporal_order(ctx(a))
        assert result.failed
        assert "naive" in result.detail

    def test_acceptance_path_survives_naive_timestamp(self, allocator):
        """The whole path must produce a failure record, not raise. [N-10]"""
        a = attrs_with(allocator)
        object.__setattr__(a, "produced_at", datetime(2026, 3, 2))
        result = AcceptancePath().accept(ctx(a))
        assert not result.accepted
        assert result.failure is not None
        assert "V8" in result.failure.rule_ids

    def test_all_naive_but_ordered_passes(self, allocator):
        """Consistent awareness is acceptable; only mixing is not."""
        a = attrs_with(allocator)
        for name, value in (
            ("observed_at", datetime(2026, 3, 1)),
            ("asserted_at", datetime(2026, 3, 2)),
            ("produced_at", datetime(2026, 3, 3)),
        ):
            object.__setattr__(a, name, value)
        assert not v8_temporal_order(ctx(a)).failed

    def test_naive_field_is_named(self, allocator):
        a = attrs_with(allocator)
        object.__setattr__(a, "asserted_at", datetime(2026, 3, 1, 1))
        assert "asserted_at" in v8_temporal_order(ctx(a)).detail

    def test_microsecond_ordering_respected(self, allocator):
        base = T0
        a = attrs_with(
            allocator,
            observed_at=base,
            asserted_at=base + timedelta(microseconds=1),
            produced_at=base + timedelta(microseconds=2),
        )
        assert not v8_temporal_order(ctx(a)).failed

    def test_microsecond_violation_detected(self, allocator):
        a = attrs_with(allocator)
        object.__setattr__(a, "observed_at", a.asserted_at + timedelta(microseconds=1))
        assert v8_temporal_order(ctx(a)).failed

    def test_differing_timezones_compare_correctly(self, allocator):
        """Aware timestamps in different zones are comparable."""
        eastern = timezone(timedelta(hours=-5))
        a = attrs_with(allocator)
        object.__setattr__(a, "observed_at", T0.astimezone(eastern))
        assert not v8_temporal_order(ctx(a)).failed


class TestV8Integration:
    def test_contract_blocks_disordered_construction(self, allocator):
        """V8 is enforced twice: at construction and at acceptance."""
        from oip.contract import TemporalOrderError
        with pytest.raises(TemporalOrderError):
            attrs_with(allocator, observed_at=T0 + timedelta(hours=9))

    def test_store_rejects_rehydrated_disorder(self, store, allocator):
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        object.__setattr__(attrs, "observed_at", T0 + timedelta(days=9))
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                attrs, build_lineage(identity.object_id, ObjectType.FACT, upstream)
            )
        assert "V8" in exc.value.failure.rule_ids


# ===========================================================================
# Cross-rule behaviour
# ===========================================================================

class TestRulesTogether:
    def test_all_four_reported_independently(self, allocator):
        """No short-circuit: every violation is visible at once."""
        a = attrs_with(
            allocator, support=0.99, assertion=0.99,
            engine=Engine.VALIDATION,
            explanation=Explanation(("obj-unrelated",), ("c",), "r"),
        )
        object.__setattr__(a, "observed_at", T0 + timedelta(days=9))
        results = {
            r.rule_id: r
            for r in AcceptancePath().evaluate(
                ctx(a, upstream_confidence=lambda o: 0.1)
            )
        }
        for rule_id in ("V5", "V6", "V7", "V8"):
            assert results[rule_id].failed, f"{rule_id} did not fail"

    def test_valid_object_passes_all_four(self, allocator):
        a = attrs_with(allocator, support=0.5, assertion=0.5)
        results = {r.rule_id: r for r in AcceptancePath().evaluate(ctx(a))}
        for rule_id in ("V5", "V6", "V7", "V8"):
            assert not results[rule_id].failed

    def test_failure_record_lists_every_broken_rule(self, allocator):
        a = attrs_with(allocator, support=0.99, assertion=0.99,
                       engine=Engine.RESEARCH)
        result = AcceptancePath().accept(ctx(a, upstream_confidence=lambda o: 0.1))
        assert {"V5", "V7"} <= set(result.failure.rule_ids)

    def test_rule_ids_are_stable(self):
        assert v5_confidence_ceiling.rule_id == "V5"
        assert v6_explanation_references_inputs.rule_id == "V6"
        assert v7_create_authority.rule_id == "V7"
        assert v8_temporal_order.rule_id == "V8"


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=300, deadline=None)
@given(effective=CONF, ceiling=CONF)
def test_v5_decision_matches_the_arithmetic(effective, ceiling):
    """V5 fails exactly when the ceiling is exceeded. [AC1]"""
    allocator = IdentityAllocator()
    a = attrs_with(allocator, support=effective, assertion=1.0)
    result = v5_confidence_ceiling(ctx(a, upstream_confidence=lambda o: ceiling))
    actual = a.confidence.effective_confidence
    assert result.failed is (actual > ceiling + 1e-9)


@settings(max_examples=200, deadline=None)
@given(ceilings=st.lists(CONF, min_size=1, max_size=12))
def test_v5_always_binds_to_the_minimum(ceilings):
    allocator = IdentityAllocator()
    upstream = tuple(
        (f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(len(ceilings))
    )
    mapping = {f"obj-ev-{i}": c for i, c in enumerate(ceilings)}
    a = attrs_with(allocator, upstream=upstream, support=1.0, assertion=1.0)
    result = v5_confidence_ceiling(ctx(a, upstream_confidence=mapping.get))
    assert result.failed is (a.confidence.effective_confidence > min(ceilings) + 1e-9)


@settings(max_examples=200, deadline=None)
@given(
    object_type=st.sampled_from(list(ObjectType)),
    engine=st.sampled_from(list(Engine)),
)
def test_v7_passes_only_for_the_authorised_pairing(object_type, engine):
    """AC2, exhaustively over all 81 type/engine combinations."""
    allocator = IdentityAllocator()
    a = build_attrs(
        allocator.new_object(), object_type,
        () if object_type.is_root else (("obj-up", ObjectType.EVIDENCE),),
        engine=engine, status=ObjectStatus.ACTIVE, status_reason=None,
    )
    expected_pass = CREATE_AUTHORITY.get(object_type) is engine
    assert (not v7_create_authority(ctx(a)).failed) is expected_pass


@settings(max_examples=300, deadline=None)
@given(
    gap_a=st.integers(min_value=-100_000, max_value=100_000),
    gap_b=st.integers(min_value=-100_000, max_value=100_000),
)
def test_v8_decision_matches_the_ordering(gap_a, gap_b):
    """AC3, over arbitrary orderings including violations."""
    allocator = IdentityAllocator()
    a = attrs_with(allocator)
    observed = T0
    asserted = observed + timedelta(seconds=gap_a)
    produced = asserted + timedelta(seconds=gap_b)
    object.__setattr__(a, "observed_at", observed)
    object.__setattr__(a, "asserted_at", asserted)
    object.__setattr__(a, "produced_at", produced)

    result = v8_temporal_order(ctx(a))
    ordered = observed <= asserted <= produced
    assert result.failed is (not ordered)


@settings(max_examples=200, deadline=None)
@given(count=st.integers(min_value=1, max_value=10))
def test_v6_passes_whenever_any_input_is_referenced(count):
    allocator = IdentityAllocator()
    upstream = tuple((f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(count))
    for index in range(count):
        a = attrs_with(
            allocator, upstream=upstream,
            explanation=Explanation((f"obj-ev-{index}",), ("c",), "r"),
        )
        assert not v6_explanation_references_inputs(ctx(a)).failed


@settings(max_examples=150, deadline=None)
@given(resolved=st.integers(min_value=0, max_value=5))
def test_v5_fails_unless_every_parent_resolves(resolved):
    """Partial resolution can never establish a ceiling."""
    total = 6
    allocator = IdentityAllocator()
    upstream = tuple((f"obj-ev-{i}", ObjectType.EVIDENCE) for i in range(total))
    mapping = {f"obj-ev-{i}": 0.99 for i in range(resolved)}
    a = attrs_with(allocator, upstream=upstream, support=0.1, assertion=0.1)
    result = v5_confidence_ceiling(ctx(a, upstream_confidence=mapping.get))
    assert result.failed is (resolved < total)
