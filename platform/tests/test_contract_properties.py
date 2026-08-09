"""Property-based tests for the universal object contract.

Task: T01.1.2

Architecture References:
- R-3   Two-component confidence; effective <= min(components, upstream)
- R-2   status_reason required when status != ACTIVE
- V8    observed_at <= asserted_at <= produced_at
- N-4   Assert properties, never equality against generated values
- N-5   Tenancy discriminator present on every object

Invariants are checked over generated inputs rather than fixed examples.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from oip.contract import (
    Confidence,
    ConfidenceCeilingError,
    ConfidenceRangeError,
    Explanation,
    ExplanationError,
    LineageRef,
    StatusReasonError,
    TemporalOrderError,
    UniversalAttributes,
)
from oip.enums import ConfidenceBand, Engine, ObjectStatus, ObjectType
from oip.identity import IdentityAllocator

CONF = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
TEXT = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())
DATES = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 1, 1),
).map(lambda d: d.replace(tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# Confidence invariants [R-3]
# ---------------------------------------------------------------------------

@settings(max_examples=400, deadline=None)
@given(support=CONF, assertion=CONF)
def test_effective_never_exceeds_either_component(support, assertion):
    """The ceiling rule holds for every valid pair. [R-3]"""
    c = Confidence.create(support, assertion)
    assert c.effective_confidence <= support + 1e-9
    assert c.effective_confidence <= assertion + 1e-9


@settings(max_examples=400, deadline=None)
@given(support=CONF, assertion=CONF, upstream=CONF)
def test_upstream_ceiling_always_binds(support, assertion, upstream):
    """Confidence is monotonically non-increasing along lineage. [R-3, V5]"""
    c = Confidence.create(support, assertion, upstream_ceiling=upstream)
    assert c.effective_confidence <= upstream + 1e-9
    assert c.effective_confidence <= min(support, assertion) + 1e-9


@settings(max_examples=300, deadline=None)
@given(values=st.lists(CONF, min_size=2, max_size=12))
def test_confidence_never_increases_along_a_chain(values):
    """No sequence of inferential steps can manufacture certainty. [R-3]"""
    ceiling = None
    effectives = []
    for support in values:
        c = Confidence.create(support, 1.0, upstream_ceiling=ceiling)
        ceiling = c.effective_confidence
        effectives.append(ceiling)

    for earlier, later in zip(effectives, effectives[1:]):
        assert later <= earlier + 1e-9, "confidence increased along the chain"


@settings(max_examples=300, deadline=None)
@given(support=CONF, assertion=CONF)
def test_band_is_consistent_with_effective_value(support, assertion):
    c = Confidence.create(support, assertion)
    assert c.band is ConfidenceBand.for_value(c.effective_confidence)


@settings(max_examples=300, deadline=None)
@given(value=CONF)
def test_every_valid_value_maps_to_exactly_one_band(value):
    band = ConfidenceBand.for_value(value)
    assert isinstance(band, ConfidenceBand)


@settings(max_examples=200, deadline=None)
@given(bad=st.floats(allow_nan=False, allow_infinity=False).filter(
    lambda v: v < 0.0 or v > 1.0))
def test_out_of_range_always_rejected(bad):
    with pytest.raises(ConfidenceRangeError):
        Confidence.create(bad, 0.5)


@settings(max_examples=300, deadline=None)
@given(support=CONF, assertion=CONF, excess=st.floats(
    min_value=0.001, max_value=1.0, allow_nan=False))
def test_declared_effective_above_ceiling_always_rejected(support, assertion, excess):
    ceiling = min(support, assertion)
    claimed = ceiling + excess
    assume(claimed <= 1.0)
    with pytest.raises(ConfidenceCeilingError):
        Confidence(
            evidential_support=support,
            assertion_confidence=assertion,
            effective_confidence=claimed,
        )


# ---------------------------------------------------------------------------
# Temporal invariants [V8, R-4]
# ---------------------------------------------------------------------------

@settings(max_examples=300, deadline=None)
@given(base=DATES, gap_a=st.integers(0, 100_000), gap_b=st.integers(0, 100_000))
def test_valid_temporal_order_always_accepted(base, gap_a, gap_b):
    allocator = IdentityAllocator()
    observed = base
    asserted = observed + timedelta(seconds=gap_a)
    produced = asserted + timedelta(seconds=gap_b)

    attrs = _make(allocator, observed_at=observed, asserted_at=asserted,
                  produced_at=produced)
    assert attrs.observed_at <= attrs.asserted_at <= attrs.produced_at


@settings(max_examples=300, deadline=None)
@given(base=DATES, violation=st.integers(1, 100_000))
def test_observed_after_asserted_always_rejected(base, violation):
    allocator = IdentityAllocator()
    with pytest.raises(TemporalOrderError):
        _make(
            allocator,
            observed_at=base + timedelta(seconds=violation),
            asserted_at=base,
            produced_at=base + timedelta(seconds=violation + 1),
        )


@settings(max_examples=300, deadline=None)
@given(base=DATES, violation=st.integers(1, 100_000))
def test_asserted_after_produced_always_rejected(base, violation):
    allocator = IdentityAllocator()
    with pytest.raises(TemporalOrderError):
        _make(
            allocator,
            observed_at=base,
            asserted_at=base + timedelta(seconds=violation),
            produced_at=base,
        )


# ---------------------------------------------------------------------------
# Status invariants [R-2, V9]
# ---------------------------------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(status=st.sampled_from(
    [s for s in ObjectStatus if s is not ObjectStatus.ACTIVE]))
def test_non_active_status_always_requires_reason(status):
    allocator = IdentityAllocator()
    with pytest.raises(StatusReasonError):
        _make(allocator, status=status, status_reason=None)


@settings(max_examples=200, deadline=None)
@given(
    status=st.sampled_from([s for s in ObjectStatus if s.is_terminal]),
    target=st.sampled_from(list(ObjectStatus)),
)
def test_terminal_status_never_transitions(status, target):
    allocator = IdentityAllocator()
    attrs = _make(allocator, status=status, status_reason="terminal")
    with pytest.raises(Exception):
        attrs.with_status(target, "attempt")


@settings(max_examples=200, deadline=None)
@given(reason=TEXT)
def test_status_transition_preserves_all_content(reason):
    allocator = IdentityAllocator()
    attrs = _make(allocator, status=ObjectStatus.PROPOSED, status_reason=reason)
    moved = attrs.with_status(ObjectStatus.ACTIVE, None)

    assert moved.identity == attrs.identity
    assert moved.object_type == attrs.object_type
    assert moved.confidence == attrs.confidence
    assert moved.derives_from == attrs.derives_from
    assert moved.explanation == attrs.explanation
    assert moved.produced_at == attrs.produced_at
    assert attrs.status is ObjectStatus.PROPOSED  # original untouched [I1]


# ---------------------------------------------------------------------------
# Structural invariants
# ---------------------------------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(object_type=st.sampled_from(list(ObjectType)), tenancy=TEXT)
def test_every_object_type_carries_tenancy(object_type, tenancy):
    """N-5: the discriminator is reserved on every object, whatever the type."""
    allocator = IdentityAllocator()
    attrs = _make(allocator, object_type=object_type, tenancy=tenancy)
    assert attrs.tenancy == tenancy


@settings(max_examples=200, deadline=None)
@given(count=st.integers(min_value=0, max_value=10_000))
def test_non_negative_source_count_accepted(count):
    allocator = IdentityAllocator()
    attrs = _make(allocator, independent_source_count=count)
    assert attrs.independent_source_count == count


@settings(max_examples=200, deadline=None)
@given(count=st.integers(max_value=-1))
def test_negative_source_count_always_rejected(count):
    allocator = IdentityAllocator()
    with pytest.raises(Exception):
        _make(allocator, independent_source_count=count)


@settings(max_examples=200, deadline=None)
@given(
    refs=st.lists(TEXT, min_size=1, max_size=10, unique=True),
    criteria=st.lists(TEXT, min_size=1, max_size=5),
    reasoning=TEXT,
)
def test_valid_explanation_always_accepted(refs, criteria, reasoning):
    e = Explanation(
        objects_referenced=tuple(refs),
        criteria_applied=tuple(criteria),
        reasoning=reasoning,
    )
    assert len(e.objects_referenced) == len(refs)


@settings(max_examples=200, deadline=None)
@given(criteria=st.lists(TEXT, min_size=1, max_size=5), reasoning=TEXT)
def test_explanation_without_references_always_rejected(criteria, reasoning):
    """V6: an explanation referencing nothing is not an explanation."""
    with pytest.raises(ExplanationError):
        Explanation(
            objects_referenced=(),
            criteria_applied=tuple(criteria),
            reasoning=reasoning,
        )


@settings(max_examples=200, deadline=None)
@given(object_type=st.sampled_from(list(ObjectType)))
def test_only_evidence_reports_as_root(object_type):
    assert (object_type.is_root) is (object_type is ObjectType.EVIDENCE)


@settings(max_examples=100, deadline=None)
@given(object_type=st.sampled_from(list(ObjectType)))
def test_stage_is_within_pipeline_range(object_type):
    assert 1 <= object_type.stage <= 9


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------

def _make(allocator: IdentityAllocator, **overrides) -> UniversalAttributes:
    base_time = datetime(2026, 3, 1, tzinfo=timezone.utc)
    kwargs = {
        "identity": allocator.new_object(),
        "object_type": ObjectType.FACT,
        "produced_by_engine": Engine.FACT_EXTRACTION,
        "produced_at": base_time + timedelta(hours=2),
        "engine_configuration_ref": "cfg-v1",
        "derives_from": (LineageRef("obj-ev-1", ObjectType.EVIDENCE),),
        "explanation": Explanation(
            objects_referenced=("obj-ev-1",),
            criteria_applied=("threshold",),
            reasoning="generated for property test",
        ),
        "evidence_reachable": True,
        "confidence": Confidence.create(0.6, 0.7),
        "asserted_at": base_time + timedelta(hours=1),
        "observed_at": base_time,
        "status": ObjectStatus.ACTIVE,
        "status_reason": None,
    }
    kwargs.update(overrides)
    return UniversalAttributes(**kwargs)
