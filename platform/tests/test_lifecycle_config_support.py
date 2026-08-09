"""Contract tests for lifecycle, configuration, failure store and support.

Tasks: T01.2.1 (lifecycle), T01.1.6 (config), T01.1.7 (failures),
       T01.5.3 (support function), T01.1.5 (supersession)

Architecture References:
- R-2   Seven-state lifecycle, per-type reachability
- CI-1  Configuration isolation
- N-7   Configuration store; N-10 failure store
- S-2   Support function: seven properties
- S-4   Sufficiency thresholds in independent sources
- I5    One ACTIVE version per lineage
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.configuration import (
    ConfigurationImmutableError,
    ConfigurationNotFoundError,
    ConfigurationRecord,
    ConfigurationStore,
    FailureStore,
    IsolationViolationError,
)
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.lifecycle import (
    IllegalTransitionError,
    MissingReasonError,
    TerminalStateError,
    UnreachableStateError,
    can_transition,
    is_consumable,
    permitted_transitions,
    reachable_states,
    validate_transition,
)
from oip.support import (
    DEFAULT_PARAMETERS,
    SUFFICIENCY_THRESHOLDS,
    SupportError,
    SupportInputs,
    SupportParameters,
    compute_support,
    meets_sufficiency,
    sufficiency_threshold,
    verify_properties,
)
from tests.conftest import build_attrs, build_lineage, write_evidence


# ---------------------------------------------------------------------------
# T01.2.1 -- seven-state lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_seven_states_exist(self):
        assert len(ObjectStatus) == 7

    def test_proposed_to_active(self):
        t = validate_transition(
            ObjectType.FACT, ObjectStatus.PROPOSED, ObjectStatus.ACTIVE
        )
        assert t.to_status is ObjectStatus.ACTIVE

    def test_proposed_to_rejected_requires_reason(self):
        with pytest.raises(MissingReasonError):
            validate_transition(
                ObjectType.FACT, ObjectStatus.PROPOSED, ObjectStatus.REJECTED
            )
        assert validate_transition(
            ObjectType.FACT, ObjectStatus.PROPOSED, ObjectStatus.REJECTED, "below floor"
        )

    @pytest.mark.parametrize(
        "target",
        [ObjectStatus.SUPERSEDED, ObjectStatus.RETRACTED,
         ObjectStatus.INVALIDATED, ObjectStatus.ARCHIVED],
    )
    def test_active_transitions(self, target):
        assert validate_transition(
            ObjectType.FACT, ObjectStatus.ACTIVE, target, "reason"
        )

    @pytest.mark.parametrize(
        "terminal",
        [s for s in ObjectStatus if s.is_terminal],
    )
    def test_terminal_states_never_transition(self, terminal):
        with pytest.raises(TerminalStateError):
            validate_transition(
                ObjectType.FACT, terminal, ObjectStatus.ACTIVE, "attempt"
            )

    def test_proposed_cannot_skip_to_archived(self):
        with pytest.raises(IllegalTransitionError):
            validate_transition(
                ObjectType.FACT, ObjectStatus.PROPOSED, ObjectStatus.ARCHIVED, "x"
            )

    def test_evidence_cannot_be_invalidated(self):
        """E-V1: Evidence has no upstream, so nothing invalidates it."""
        assert ObjectStatus.INVALIDATED not in reachable_states(ObjectType.EVIDENCE)
        with pytest.raises(UnreachableStateError):
            validate_transition(
                ObjectType.EVIDENCE, ObjectStatus.ACTIVE,
                ObjectStatus.INVALIDATED, "upstream gone",
            )

    def test_evidence_can_be_retracted(self):
        """Retraction is external withdrawal, which Evidence can undergo."""
        assert validate_transition(
            ObjectType.EVIDENCE, ObjectStatus.ACTIVE,
            ObjectStatus.RETRACTED, "source withdrew",
        )

    @pytest.mark.parametrize(
        "object_type", [t for t in ObjectType if not t.is_root]
    )
    def test_non_evidence_can_be_invalidated(self, object_type):
        assert validate_transition(
            object_type, ObjectStatus.ACTIVE, ObjectStatus.INVALIDATED, "upstream"
        )

    def test_cascade_trigger_flagged(self):
        for target in (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED):
            t = validate_transition(
                ObjectType.FACT, ObjectStatus.ACTIVE, target, "reason"
            )
            assert t.is_cascade_trigger
        archived = validate_transition(
            ObjectType.FACT, ObjectStatus.ACTIVE, ObjectStatus.ARCHIVED, "retention"
        )
        assert not archived.is_cascade_trigger

    def test_clears_active_flagged(self):
        t = validate_transition(
            ObjectType.FACT, ObjectStatus.ACTIVE, ObjectStatus.SUPERSEDED, "new version"
        )
        assert t.clears_active

    def test_permitted_transitions_enumerable(self):
        assert permitted_transitions(ObjectType.FACT, ObjectStatus.PROPOSED) == {
            ObjectStatus.ACTIVE, ObjectStatus.REJECTED
        }
        assert permitted_transitions(ObjectType.FACT, ObjectStatus.ARCHIVED) == frozenset()

    def test_can_transition_is_non_raising(self):
        assert can_transition(ObjectType.FACT, ObjectStatus.PROPOSED, ObjectStatus.ACTIVE)
        assert not can_transition(
            ObjectType.EVIDENCE, ObjectStatus.ACTIVE, ObjectStatus.INVALIDATED
        )
        assert not can_transition(
            ObjectType.FACT, ObjectStatus.REJECTED, ObjectStatus.ACTIVE
        )

    def test_only_active_is_consumable(self):
        """I8: REJECTED objects must never re-enter the pipeline."""
        for status in ObjectStatus:
            assert is_consumable(status) is (status is ObjectStatus.ACTIVE)


# ---------------------------------------------------------------------------
# T01.1.5 -- supersession through the store
# ---------------------------------------------------------------------------

class TestSupersession:
    def test_linear_chain_through_store(self, store, allocator):
        first = write_evidence(store, allocator)
        current = first
        for _ in range(5):
            store.transition(current.object_id, ObjectStatus.SUPERSEDED, "replaced")
            successor = allocator.succeed(current.attributes.identity)
            attrs = build_attrs(
                successor, ObjectType.EVIDENCE,
                status=ObjectStatus.ACTIVE, status_reason=None,
            )
            current = store.write(
                attrs, build_lineage(successor.object_id, ObjectType.EVIDENCE),
                predecessor_id=current.object_id,
            )
        assert len(store.versions_of(first.lineage_id)) == 6
        assert store.active_version_of(first.lineage_id) == current.object_id

    def test_exactly_one_active_at_all_times(self, store, allocator):
        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        successor = allocator.succeed(first.attributes.identity)
        attrs = build_attrs(
            successor, ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        store.write(
            attrs, build_lineage(successor.object_id, ObjectType.EVIDENCE),
            predecessor_id=first.object_id,
        )
        versions = store.versions_of(first.lineage_id)
        active = [v for v in versions if v.status is ObjectStatus.ACTIVE]
        assert len(active) == 1


# ---------------------------------------------------------------------------
# T01.1.6 / CI-1 -- configuration store
# ---------------------------------------------------------------------------

class TestConfigurationStore:
    def test_record_and_resolve(self):
        cfg = ConfigurationStore()
        entry = cfg.record(Engine.FACT_EXTRACTION, {"threshold": 0.5})
        assert cfg.resolve(entry.config_ref) == entry

    def test_versions_increment(self):
        cfg = ConfigurationStore()
        a = cfg.record(Engine.RESEARCH, {"depth": 1})
        b = cfg.record(Engine.RESEARCH, {"depth": 2})
        assert (a.version, b.version) == (1, 2)
        assert b.supersedes == a.config_ref

    def test_records_are_immutable(self):
        cfg = ConfigurationStore()
        entry = cfg.record(Engine.RESEARCH, {"depth": 1})
        with pytest.raises(Exception):
            entry.version = 2

    def test_duplicate_ref_rejected(self):
        cfg = ConfigurationStore()
        cfg.record(Engine.RESEARCH, {"a": 1}, config_ref="cfg-x")
        with pytest.raises(ConfigurationImmutableError):
            cfg.record(Engine.RESEARCH, {"a": 2}, config_ref="cfg-x")

    def test_unresolvable_ref_raises(self):
        with pytest.raises(ConfigurationNotFoundError):
            ConfigurationStore().resolve("cfg-absent")

    def test_history_supports_rollback(self):
        """M-34: learning reversal via versioned rollback."""
        cfg = ConfigurationStore()
        original = cfg.record(Engine.OPPORTUNITY_INTELLIGENCE, {"weight": 0.4})
        cfg.record(Engine.OPPORTUNITY_INTELLIGENCE, {"weight": 0.9})
        restored = cfg.rollback(Engine.OPPORTUNITY_INTELLIGENCE, original.config_ref)

        assert restored.settings == original.settings
        assert restored.version == 3, "rollback records forward, never edits history"
        assert len(cfg.history_for(Engine.OPPORTUNITY_INTELLIGENCE)) == 3

    def test_rollback_across_engines_rejected(self):
        cfg = ConfigurationStore()
        entry = cfg.record(Engine.RESEARCH, {"a": 1})
        with pytest.raises(Exception):
            cfg.rollback(Engine.VALIDATION, entry.config_ref)

    def test_current_for_engine(self):
        cfg = ConfigurationStore()
        assert cfg.current_for(Engine.RESEARCH) is None
        cfg.record(Engine.RESEARCH, {"a": 1})
        latest = cfg.record(Engine.RESEARCH, {"a": 2})
        assert cfg.current_for(Engine.RESEARCH) == latest

    def test_settings_are_copied_not_aliased(self):
        cfg = ConfigurationStore()
        mutable = {"a": 1}
        entry = cfg.record(Engine.RESEARCH, mutable)
        mutable["a"] = 999
        assert entry.settings["a"] == 1

    def test_invalid_records_rejected(self):
        from datetime import datetime, timezone
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for kwargs in (
            {"config_ref": "", "engine": Engine.RESEARCH, "version": 1},
            {"config_ref": "c", "engine": "Research", "version": 1},
            {"config_ref": "c", "engine": Engine.RESEARCH, "version": 0},
        ):
            with pytest.raises(Exception):
                ConfigurationRecord(settings={}, recorded_at=now, **kwargs)

    def test_len_and_iteration(self):
        cfg = ConfigurationStore()
        cfg.record(Engine.RESEARCH, {"a": 1})
        cfg.record(Engine.VALIDATION, {"b": 2})
        assert len(cfg) == 2
        assert len(list(cfg)) == 2
        assert cfg.contains(list(cfg)[0].config_ref)


class TestConfigurationIsolation:
    """CI-1 enforced at the access boundary, not by convention."""

    def _entry(self) -> ConfigurationRecord:
        return ConfigurationStore().record(Engine.RESEARCH, {"a": 1})

    def test_configuration_is_never_intelligence(self):
        assert self._entry().is_intelligence is False

    def test_configuration_never_participates_in_lineage(self):
        assert self._entry().participates_in_lineage is False

    def test_lineage_reference_prohibited(self):
        with pytest.raises(IsolationViolationError):
            self._entry().as_lineage_reference()

    def test_becoming_evidence_prohibited(self):
        with pytest.raises(IsolationViolationError):
            self._entry().as_evidence()

    def test_confidence_contribution_prohibited(self):
        with pytest.raises(IsolationViolationError):
            self._entry().confidence_contribution()

    def test_configuration_is_not_an_intelligence_object(self):
        from oip.contract import UniversalAttributes
        assert not isinstance(self._entry(), UniversalAttributes)


# ---------------------------------------------------------------------------
# T01.1.7 -- failure store
# ---------------------------------------------------------------------------

class TestFailureStore:
    def _failure(self, store, allocator):
        from oip.enums import Engine as E
        identity = allocator.new_object()
        evidence = write_evidence(store, allocator)
        attrs = build_attrs(
            identity, ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
            engine=E.RESEARCH,
        )
        lineage = build_lineage(
            identity.object_id, ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
        )
        result = store.try_write(attrs, lineage)
        return result.failure

    def test_records_accumulate(self, store, allocator):
        failures = FailureStore()
        failures.record(self._failure(store, allocator))
        assert len(failures) == 1

    def test_query_by_object(self, store, allocator):
        failures = FailureStore()
        failure = failures.record(self._failure(store, allocator))
        assert failures.for_object(failure.object_id) == (failure,)
        assert failures.for_object("obj-absent") == ()

    def test_query_by_rule(self, store, allocator):
        failures = FailureStore()
        failures.record(self._failure(store, allocator))
        assert len(failures.for_rule("V7")) == 1
        assert failures.for_rule("V1") == ()

    def test_failures_never_enter_lineage(self):
        assert FailureStore().participates_in_lineage is False


# ---------------------------------------------------------------------------
# T01.5.3 -- support function
# ---------------------------------------------------------------------------

class TestSupportFunction:
    def test_all_seven_properties_hold(self):
        report = verify_properties()
        assert report.all_hold, f"failing properties: {report.failures()}"

    def test_zero_sources_yields_zero(self):
        assert compute_support(SupportInputs(independent_source_count=0)) == 0.0

    def test_p1_monotonic(self):
        values = [
            compute_support(SupportInputs(independent_source_count=n))
            for n in range(1, 20)
        ]
        assert all(b >= a for a, b in zip(values, values[1:]))

    def test_p2_saturating(self):
        first = compute_support(SupportInputs(independent_source_count=2)) - \
            compute_support(SupportInputs(independent_source_count=1))
        later = compute_support(SupportInputs(independent_source_count=20)) - \
            compute_support(SupportInputs(independent_source_count=19))
        assert later < first

    def test_p3_diversity_beats_concentration(self):
        """Counters sampling artefact: n types beat n of one type. [M-23]"""
        concentrated = compute_support(
            SupportInputs(independent_source_count=10, source_type_count=1)
        )
        diverse = compute_support(
            SupportInputs(independent_source_count=10, source_type_count=5)
        )
        assert diverse > concentrated

    def test_p4_syndication_does_not_inflate(self):
        """Ten syndicated copies present as one independent source. [S-2]"""
        alone = compute_support(SupportInputs(independent_source_count=1))
        syndicated = compute_support(
            SupportInputs(independent_source_count=1, corroboration_depth=10)
        )
        assert alone == syndicated

    def test_p5_contradiction_reduces_support(self):
        clean = compute_support(SupportInputs(independent_source_count=8))
        contested = compute_support(
            SupportInputs(independent_source_count=8, contradiction_count=1)
        )
        assert contested < clean

    def test_p5_penalty_is_bounded(self):
        """Disagreement is information, not absence of evidence."""
        heavily = compute_support(
            SupportInputs(independent_source_count=8, contradiction_count=50)
        )
        assert heavily > 0.0

    def test_p6_bounded_by_upstream(self):
        bounded = compute_support(
            SupportInputs(independent_source_count=100, upstream_support=(0.15,))
        )
        assert bounded <= 0.15

    def test_p6_takes_minimum_upstream(self):
        bounded = compute_support(
            SupportInputs(
                independent_source_count=100, upstream_support=(0.8, 0.2, 0.5)
            )
        )
        assert bounded <= 0.2

    def test_p7_deterministic(self):
        probe = SupportInputs(
            independent_source_count=9, source_type_count=4,
            contradiction_count=1, upstream_support=(0.9,),
        )
        assert compute_support(probe) == compute_support(probe)

    def test_output_always_in_range(self):
        for n in (0, 1, 5, 100, 10_000):
            value = compute_support(SupportInputs(independent_source_count=n))
            assert 0.0 <= value <= 1.0

    def test_assertion_confidence_is_not_an_input(self):
        """R-3: the two components must remain orthogonal."""
        assert not hasattr(SupportInputs(independent_source_count=1),
                           "assertion_confidence")

    def test_negative_inputs_rejected(self):
        for kwargs in (
            {"independent_source_count": -1},
            {"independent_source_count": 1, "source_type_count": -1},
            {"independent_source_count": 1, "contradiction_count": -1},
        ):
            with pytest.raises(SupportError):
                SupportInputs(**kwargs)

    def test_upstream_out_of_range_rejected(self):
        with pytest.raises(SupportError):
            SupportInputs(independent_source_count=1, upstream_support=(1.5,))

    def test_invalid_parameters_rejected(self):
        with pytest.raises(SupportError):
            SupportParameters(saturation_scale=0)
        with pytest.raises(SupportError):
            SupportParameters(diversity_weight=2.0)

    def test_properties_hold_for_alternate_parameters(self):
        """The contract is the properties, not the curve. [S-2]"""
        report = verify_properties(
            SupportParameters(saturation_scale=8.0, diversity_weight=0.5)
        )
        assert report.all_hold, report.failures()

    def test_property_report_surface(self):
        report = verify_properties()
        assert len(report.results) == 7
        assert report.failures() == ()


# ---------------------------------------------------------------------------
# S-4 -- sufficiency thresholds
# ---------------------------------------------------------------------------

class TestSufficiencyThresholds:
    def test_every_type_has_a_threshold(self):
        assert set(SUFFICIENCY_THRESHOLDS) == set(ObjectType)

    def test_documented_values(self):
        assert sufficiency_threshold(ObjectType.FACT) == 1
        assert sufficiency_threshold(ObjectType.PROBLEM) == 2
        assert sufficiency_threshold(ObjectType.PATTERN) == 3
        assert sufficiency_threshold(ObjectType.FEEDBACK_RECORD) == 2

    def test_below_threshold_fails(self):
        assert not meets_sufficiency(ObjectType.PATTERN, 2)
        assert meets_sufficiency(ObjectType.PATTERN, 3)

    def test_thresholds_are_floors_not_gradients(self):
        """S-4: below the floor an object is rejected, not down-weighted."""
        for object_type in ObjectType:
            floor = sufficiency_threshold(object_type)
            assert not meets_sufficiency(object_type, floor - 1)
            assert meets_sufficiency(object_type, floor)


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=300, deadline=None)
@given(
    n=st.integers(0, 500),
    types=st.integers(0, 20),
    contradictions=st.integers(0, 20),
)
def test_support_always_in_unit_range(n, types, contradictions):
    value = compute_support(
        SupportInputs(
            independent_source_count=n,
            source_type_count=types,
            contradiction_count=contradictions,
        )
    )
    assert 0.0 <= value <= 1.0


@settings(max_examples=300, deadline=None)
@given(a=st.integers(1, 200), b=st.integers(1, 200))
def test_more_independent_sources_never_reduce_support(a, b):
    lo, hi = min(a, b), max(a, b)
    assert compute_support(SupportInputs(independent_source_count=hi)) >= \
        compute_support(SupportInputs(independent_source_count=lo)) - 1e-12


@settings(max_examples=200, deadline=None)
@given(n=st.integers(1, 100), ceiling=st.floats(0.0, 1.0, allow_nan=False))
def test_upstream_always_bounds(n, ceiling):
    value = compute_support(
        SupportInputs(independent_source_count=n, upstream_support=(ceiling,))
    )
    assert value <= ceiling + 1e-12


@settings(max_examples=200, deadline=None)
@given(
    object_type=st.sampled_from(list(ObjectType)),
    current=st.sampled_from(list(ObjectStatus)),
    target=st.sampled_from(list(ObjectStatus)),
)
def test_transition_legality_is_total(object_type, current, target):
    """can_transition never raises, for any combination. [R-2]"""
    legal = can_transition(object_type, current, target)
    if legal:
        assert validate_transition(object_type, current, target, "reason")
    else:
        with pytest.raises(Exception):
            validate_transition(object_type, current, target, "reason")
