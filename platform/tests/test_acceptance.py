"""Contract tests for the acceptance path.

Tasks: T01.4.1 (path), T01.5.1 (confidence verify), T01.5.4 (diversity verify),
       T01.1.3 (optional attributes verify)

Architecture References:
- N-8   Store enforces; rules externally specified
- N-10  Failed acceptance produces a failure record
- V1-V12 Universal validation rules
- S-5   Semantic hook; M-67 residual risk measured not eliminated

Acceptance criteria under test:
  T01.4.1  PROPOSED -> ACTIVE gated by rule evaluation
           Rules externally specified, not embedded in the Store
           Failed acceptance produces a failure record
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import (
    UNIVERSAL_RULES,
    AcceptanceContext,
    AcceptancePath,
    NullSemanticVerifier,
    RuleOutcome,
    RuleResult,
)
from oip.contract import (
    Confidence,
    Explanation,
    LineageRef,
    UniversalAttributes,
)
from oip.enums import ConfidenceBand, Engine, ObjectStatus, ObjectType
from oip.identity import IdentityAllocator

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


@pytest.fixture()
def allocator() -> IdentityAllocator:
    return IdentityAllocator()


@pytest.fixture()
def path() -> AcceptancePath:
    return AcceptancePath()


def fact_attrs(allocator: IdentityAllocator, **overrides) -> UniversalAttributes:
    kwargs = {
        "identity": allocator.new_object(),
        "object_type": ObjectType.FACT,
        "produced_by_engine": Engine.FACT_EXTRACTION,
        "produced_at": T0 + timedelta(hours=2),
        "engine_configuration_ref": "cfg-v1",
        "derives_from": (LineageRef("obj-ev-1", ObjectType.EVIDENCE),),
        "explanation": Explanation(
            objects_referenced=("obj-ev-1",),
            criteria_applied=("anchor-verification",),
            reasoning="Claim located at the stated anchor.",
        ),
        "evidence_reachable": True,
        "confidence": Confidence.create(0.62, 0.84),
        "asserted_at": T0 + timedelta(hours=1),
        "observed_at": T0,
        "status": ObjectStatus.PROPOSED,
        "status_reason": "awaiting acceptance",
        "independent_source_count": 1,
    }
    kwargs.update(overrides)
    return UniversalAttributes(**kwargs)


def evidence_attrs(allocator: IdentityAllocator, **overrides) -> UniversalAttributes:
    kwargs = {
        "identity": allocator.new_object(),
        "object_type": ObjectType.EVIDENCE,
        "produced_by_engine": Engine.RESEARCH,
        "produced_at": T0 + timedelta(hours=2),
        "engine_configuration_ref": "cfg-v1",
        "derives_from": (),
        "explanation": Explanation(
            objects_referenced=("source-corpus-A",),
            criteria_applied=("licensing-eligibility",),
            reasoning="Acquired under directive covering segment A.",
        ),
        "evidence_reachable": True,
        "confidence": Confidence.create(0.62, 0.90),
        "asserted_at": T0 + timedelta(hours=1),
        "observed_at": T0,
        "status": ObjectStatus.PROPOSED,
        "status_reason": "awaiting acceptance",
        "independent_source_count": 1,
    }
    kwargs.update(overrides)
    return UniversalAttributes(**kwargs)


def ctx_for(attrs: UniversalAttributes, **overrides) -> AcceptanceContext:
    kwargs = {
        "attributes": attrs,
        "resolve_type": lambda oid: ObjectType.EVIDENCE if "ev" in oid else None,
        "reaches_evidence": lambda oid: True,
        "would_cycle": lambda a, b: False,
        "upstream_confidence": lambda oid: 0.62,
    }
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


# ---------------------------------------------------------------------------
# AC1 -- PROPOSED to ACTIVE gated by rule evaluation
# ---------------------------------------------------------------------------

class TestGatedTransition:
    def test_valid_object_is_accepted_and_becomes_active(self, allocator, path):
        result = path.accept(ctx_for(fact_attrs(allocator)))
        assert result.accepted
        assert result.attributes.status is ObjectStatus.ACTIVE
        assert result.attributes.status_reason is None

    def test_evidence_accepted_with_empty_lineage(self, allocator, path):
        result = path.accept(ctx_for(evidence_attrs(allocator)))
        assert result.accepted

    def test_rejected_object_does_not_become_active(self, allocator, path):
        bad = fact_attrs(allocator, evidence_reachable=False)
        result = path.accept(ctx_for(bad, reaches_evidence=lambda oid: False))
        assert not result.accepted
        assert result.attributes is None

    def test_all_rules_run_no_short_circuit(self, allocator, path):
        """Every failure is reported, not just the first."""
        broken = fact_attrs(
            allocator,
            produced_by_engine=Engine.RESEARCH,       # V7
            evidence_reachable=False,                  # V4
        )
        result = path.accept(
            ctx_for(broken, reaches_evidence=lambda oid: False)
        )
        failed = {r.rule_id for r in result.failures}
        assert {"V4", "V7"} <= failed

    def test_every_rule_reports_an_outcome(self, allocator, path):
        results = path.evaluate(ctx_for(fact_attrs(allocator)))
        assert len(results) == len(UNIVERSAL_RULES)
        assert all(isinstance(r, RuleResult) for r in results)

    def test_already_active_object_passes_through(self, allocator, path):
        attrs = fact_attrs(allocator, status=ObjectStatus.ACTIVE, status_reason=None)
        result = path.accept(ctx_for(attrs))
        assert result.accepted
        assert result.attributes.status is ObjectStatus.ACTIVE


# ---------------------------------------------------------------------------
# AC2 -- rules externally specified, not embedded
# ---------------------------------------------------------------------------

class TestRulesExternallySpecified:
    def test_rule_set_is_injectable(self, allocator):
        """The Store runs rules it is handed; it does not own them. [N-8]"""
        def always_fail(ctx):
            return RuleResult("CUSTOM", RuleOutcome.FAIL, "injected")
        always_fail.rule_id = "CUSTOM"

        path = AcceptancePath(rules=(always_fail,))
        result = path.accept(ctx_for(fact_attrs(allocator)))
        assert not result.accepted
        assert result.failures[0].rule_id == "CUSTOM"

    def test_empty_rule_set_accepts_everything(self, allocator):
        """Proves the mechanism holds no built-in policy. [N-8]"""
        path = AcceptancePath(rules=())
        result = path.accept(ctx_for(fact_attrs(allocator)))
        assert result.accepted
        assert result.results == ()

    def test_rule_ids_are_enumerable(self, path):
        assert set(path.rule_ids) == {f"V{i}" for i in range(1, 13)}

    def test_semantic_verifier_is_pluggable(self, allocator):
        """S-5 Layer 1 attaches here; coverage is partial by design. [M-67]"""
        path = AcceptancePath(semantic_verifiers=(NullSemanticVerifier(),))
        results = path.evaluate(ctx_for(fact_attrs(allocator)))
        semantic = [r for r in results if r.rule_id == "F-V6"]
        assert len(semantic) == 1
        assert semantic[0].outcome is RuleOutcome.SKIP

    def test_semantic_verifier_can_reject(self, allocator):
        def reject(ctx):
            return RuleResult("F-V6", RuleOutcome.FAIL, "claim absent from anchor")
        reject.rule_id = "F-V6"

        path = AcceptancePath(semantic_verifiers=(reject,))
        result = path.accept(ctx_for(fact_attrs(allocator)))
        assert not result.accepted
        assert "F-V6" in {r.rule_id for r in result.failures}


# ---------------------------------------------------------------------------
# AC3 -- failed acceptance produces a failure record [N-10]
# ---------------------------------------------------------------------------

class TestFailureRecords:
    def test_failure_produces_a_record(self, allocator, path):
        bad = fact_attrs(allocator, produced_by_engine=Engine.RESEARCH)
        result = path.accept(ctx_for(bad))
        assert result.failure is not None
        assert result.failure.object_id == bad.object_id
        assert "V7" in result.failure.rule_ids

    def test_success_produces_no_record(self, allocator, path):
        result = path.accept(ctx_for(fact_attrs(allocator)))
        assert result.failure is None
        assert path.failure_records == ()

    def test_records_accumulate(self, allocator, path):
        for _ in range(3):
            path.accept(ctx_for(fact_attrs(allocator, produced_by_engine=Engine.RESEARCH)))
        assert len(path.failure_records) == 3

    def test_record_captures_configuration(self, allocator, path):
        bad = fact_attrs(
            allocator, produced_by_engine=Engine.RESEARCH,
            engine_configuration_ref="cfg-v7",
        )
        result = path.accept(ctx_for(bad))
        assert result.failure.engine_configuration_ref == "cfg-v7"

    def test_empty_result_distinguishable_from_failure(self, allocator, path):
        """N-10's core requirement."""
        ok = path.accept(ctx_for(fact_attrs(allocator)))
        bad = path.accept(
            ctx_for(fact_attrs(allocator, produced_by_engine=Engine.RESEARCH))
        )
        assert ok.accepted and ok.failure is None
        assert not bad.accepted and bad.failure is not None


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

class TestUniversalRules:
    def _outcome(self, path, ctx, rule_id):
        return next(r for r in path.evaluate(ctx) if r.rule_id == rule_id)

    def test_v2_rejects_empty_lineage_on_non_evidence(self, allocator, path):
        """UniversalAttributes does not enforce V2 (Lineage does), so the
        acceptance rule is the enforcement point for attribute-only objects."""
        attrs = fact_attrs(
            allocator,
            derives_from=(),
            explanation=Explanation(
                objects_referenced=("obj-ev-1",),
                criteria_applied=("x",),
                reasoning="no upstream declared",
            ),
        )
        result = self._outcome(path, ctx_for(attrs), "V2")
        assert result.failed
        assert not path.accept(ctx_for(attrs)).accepted

    def test_v2_rejects_evidence_carrying_lineage(self, allocator, path):
        """AD-05 at the acceptance layer."""
        attrs = evidence_attrs(
            allocator, derives_from=(LineageRef("obj-fr-1",
                                                ObjectType.FEEDBACK_RECORD),)
        )
        assert self._outcome(path, ctx_for(attrs), "V2").failed

    def test_v3_rejects_unresolvable_reference(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), resolve_type=lambda oid: None)
        assert self._outcome(path, ctx, "V3").failed

    def test_v3_rejects_type_mismatch(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), resolve_type=lambda oid: ObjectType.PROBLEM)
        assert self._outcome(path, ctx, "V3").failed

    def test_v3_skips_without_resolver(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), resolve_type=None)
        assert self._outcome(path, ctx, "V3").outcome is RuleOutcome.SKIP

    def test_v4_requires_real_path_not_assertion(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), reaches_evidence=lambda oid: False)
        assert self._outcome(path, ctx, "V4").failed

    def test_v4_rejects_false_assertion_with_real_path(self, allocator, path):
        attrs = fact_attrs(allocator, evidence_reachable=False)
        assert self._outcome(path, ctx_for(attrs), "V4").failed

    def test_v5_rejects_confidence_above_upstream(self, allocator, path):
        attrs = fact_attrs(allocator, confidence=Confidence.create(0.9, 0.9))
        ctx = ctx_for(attrs, upstream_confidence=lambda oid: 0.5)
        assert self._outcome(path, ctx, "V5").failed

    def test_v5_accepts_confidence_at_ceiling(self, allocator, path):
        attrs = fact_attrs(allocator, confidence=Confidence.create(0.5, 0.9))
        ctx = ctx_for(attrs, upstream_confidence=lambda oid: 0.5)
        assert not self._outcome(path, ctx, "V5").failed

    def test_v6_rejects_explanation_referencing_nothing_consumed(self, allocator, path):
        attrs = fact_attrs(
            allocator,
            explanation=Explanation(
                objects_referenced=("obj-unrelated",),
                criteria_applied=("x",),
                reasoning="references an object never read",
            ),
        )
        assert self._outcome(path, ctx_for(attrs), "V6").failed

    def test_v7_rejects_wrong_engine(self, allocator, path):
        attrs = fact_attrs(allocator, produced_by_engine=Engine.PATTERN_INTELLIGENCE)
        assert self._outcome(path, ctx_for(attrs), "V7").failed

    def test_v7_rejects_execution_record_c02_open(self, allocator, path):
        """No engine holds create authority for ExecutionRecord. [C-02]"""
        attrs = fact_attrs(
            allocator,
            object_type=ObjectType.EXECUTION_RECORD,
            produced_by_engine=Engine.RESEARCH,
            derives_from=(LineageRef("obj-so-1", ObjectType.SOLUTION),),
            explanation=Explanation(
                objects_referenced=("obj-so-1",),
                criteria_applied=("outcome-intake",),
                reasoning="outcome reported externally",
            ),
        )
        result = self._outcome(path, ctx_for(attrs), "V7")
        assert result.failed
        assert "C-02" in result.detail

    def test_v10_rejects_cycle(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), would_cycle=lambda a, b: True)
        assert self._outcome(path, ctx, "V10").failed

    def test_v11_requires_first_version_to_be_one(self, allocator, path):
        first = allocator.new_object()
        second = allocator.succeed(first)
        attrs = fact_attrs(allocator, identity=second)
        assert self._outcome(path, ctx_for(attrs), "V11").failed

    def test_v11_accepts_valid_succession(self, allocator, path):
        first_id = allocator.new_object()
        predecessor = fact_attrs(allocator, identity=first_id)
        successor = fact_attrs(allocator, identity=allocator.succeed(first_id))
        ctx = ctx_for(successor, predecessor=predecessor)
        assert not self._outcome(path, ctx, "V11").failed

    def test_v11_rejects_lineage_change_across_versions(self, allocator, path):
        predecessor = fact_attrs(allocator)
        successor = fact_attrs(allocator)  # different lineage_id
        ctx = ctx_for(successor, predecessor=predecessor)
        assert self._outcome(path, ctx, "V11").failed


# ---------------------------------------------------------------------------
# T01.5.1 -- confidence model verification
# ---------------------------------------------------------------------------

class TestConfidenceModelDelivered:
    def test_both_components_stored_independently(self):
        c = Confidence.create(0.9, 0.2)
        assert c.evidential_support == 0.9 and c.assertion_confidence == 0.2

    def test_five_bands_implemented(self):
        assert len(ConfidenceBand) == 5

    def test_well_evidenced_low_confidence_representable(self):
        c = Confidence.create(0.95, 0.15)
        assert c.support_band is ConfidenceBand.VERY_STRONG
        assert c.assertion_band is ConfidenceBand.NEGLIGIBLE


# ---------------------------------------------------------------------------
# T01.5.4 -- diversity summary attribute
# ---------------------------------------------------------------------------

class TestDiversitySummary:
    def test_populated_at_creation(self, allocator):
        assert fact_attrs(allocator, independent_source_count=7).independent_source_count == 7

    def test_carried_on_every_object_type(self, allocator):
        for object_type in ObjectType:
            attrs = fact_attrs(
                allocator,
                object_type=object_type,
                derives_from=() if object_type.is_root
                else (LineageRef("obj-ev-1", ObjectType.EVIDENCE),),
                independent_source_count=3,
            )
            assert attrs.independent_source_count == 3

    def test_available_without_deep_traversal(self, allocator):
        """M-23 Tier 1: constant-time read, no lineage walk."""
        attrs = fact_attrs(allocator, independent_source_count=11)
        assert attrs.independent_source_count == 11

    def test_available_at_pattern_depth(self, allocator):
        """Pattern sits at depth 3; the summary is present regardless. [M-23]"""
        pattern = fact_attrs(
            allocator,
            object_type=ObjectType.PATTERN,
            produced_by_engine=Engine.PATTERN_INTELLIGENCE,
            derives_from=(LineageRef("obj-pr-1", ObjectType.PROBLEM),),
            explanation=Explanation(
                objects_referenced=("obj-pr-1",),
                criteria_applied=("grouping-rationale",),
                reasoning="Shared structural mechanism across constituents.",
            ),
            independent_source_count=11,
        )
        assert pattern.independent_source_count == 11


# ---------------------------------------------------------------------------
# T01.1.3 -- optional attributes
# ---------------------------------------------------------------------------

class TestOptionalAttributes:
    def test_all_optional_attributes_accepted(self, allocator):
        expiry = T0 + timedelta(days=365)
        attrs = fact_attrs(
            allocator,
            valid_until=expiry,
            duplicates=("obj-fa-9",),
            contradicts=("obj-fa-8",),
            supersedes="obj-fa-0",
            superseded_by=None,
            tags=("segment-a",),
        )
        assert attrs.valid_until == expiry
        assert attrs.duplicates == ("obj-fa-9",)
        assert attrs.contradicts == ("obj-fa-8",)
        assert attrs.supersedes == "obj-fa-0"
        assert attrs.tags == ("segment-a",)

    def test_optional_attributes_default_empty(self, allocator):
        attrs = fact_attrs(allocator)
        assert attrs.valid_until is None
        assert attrs.duplicates == () and attrs.contradicts == ()
        assert attrs.supersedes is None and attrs.superseded_by is None
        assert attrs.tags == ()

    def test_tags_do_not_affect_acceptance(self, allocator, path):
        """Tags must never be load-bearing. [IOM section 1.2]"""
        plain = path.accept(ctx_for(fact_attrs(allocator)))
        tagged = path.accept(
            ctx_for(fact_attrs(allocator, tags=("a", "b", "c")))
        )
        assert plain.accepted == tagged.accepted
        assert {r.rule_id for r in plain.results} == {r.rule_id for r in tagged.results}


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=200, deadline=None)
@given(support=st.floats(0.0, 1.0), assertion=st.floats(0.0, 1.0),
       ceiling=st.floats(0.0, 1.0))
def test_v5_never_accepts_above_ceiling(support, assertion, ceiling):
    allocator = IdentityAllocator()
    path = AcceptancePath()
    attrs = fact_attrs(allocator, confidence=Confidence.create(support, assertion))
    ctx = ctx_for(attrs, upstream_confidence=lambda oid: ceiling)
    result = next(r for r in path.evaluate(ctx) if r.rule_id == "V5")
    if attrs.confidence.effective_confidence > ceiling + 1e-9:
        assert result.failed
    else:
        assert not result.failed


@settings(max_examples=150, deadline=None)
@given(engine=st.sampled_from(list(Engine)))
def test_v7_accepts_only_the_authorised_engine(engine):
    allocator = IdentityAllocator()
    path = AcceptancePath()
    attrs = fact_attrs(allocator, produced_by_engine=engine)
    result = next(r for r in path.evaluate(ctx_for(attrs)) if r.rule_id == "V7")
    assert result.failed is (engine is not Engine.FACT_EXTRACTION)


@settings(max_examples=150, deadline=None)
@given(count=st.integers(min_value=0, max_value=5000))
def test_diversity_summary_accepts_any_non_negative(count):
    allocator = IdentityAllocator()
    assert fact_attrs(
        allocator, independent_source_count=count
    ).independent_source_count == count


# ---------------------------------------------------------------------------
# Rule edge cases and result surface
# ---------------------------------------------------------------------------

class TestRuleEdgeCases:
    def _outcome(self, path, ctx, rule_id):
        return next(r for r in path.evaluate(ctx) if r.rule_id == rule_id)

    def test_v1_rejects_non_attributes(self):
        """V1 is the type guard; evaluate it alone since later rules assume it."""
        from oip.acceptance import v1_required_attributes_present

        class Fake:
            object_id = "obj-x"
            object_type = ObjectType.FACT
            engine_configuration_ref = "cfg"

        assert v1_required_attributes_present(
            AcceptanceContext(attributes=Fake())
        ).failed

    def test_v4_skips_without_provider(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), reaches_evidence=None)
        assert self._outcome(path, ctx, "V4").outcome is RuleOutcome.SKIP

    def test_v5_skips_without_provider(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), upstream_confidence=None)
        assert self._outcome(path, ctx, "V5").outcome is RuleOutcome.SKIP

    def test_v5_fails_when_upstream_cannot_be_resolved(self, allocator, path):
        """A ceiling cannot be established from an unresolved upstream. [V5]

        Previously this SKIPped, which let confidence inflation through when
        a parent could not be read. Now it fails closed.
        """
        ctx = ctx_for(fact_attrs(allocator), upstream_confidence=lambda oid: None)
        result = self._outcome(path, ctx, "V5")
        assert result.failed
        assert "unresolvable" in result.detail

    def test_v5_skips_for_evidence(self, allocator, path):
        ctx = ctx_for(evidence_attrs(allocator))
        assert self._outcome(path, ctx, "V5").outcome is RuleOutcome.SKIP

    def test_v10_skips_without_provider(self, allocator, path):
        ctx = ctx_for(fact_attrs(allocator), would_cycle=None)
        assert self._outcome(path, ctx, "V10").outcome is RuleOutcome.SKIP

    def test_v6_passes_for_evidence_referencing_sources(self, allocator, path):
        assert not self._outcome(path, ctx_for(evidence_attrs(allocator)), "V6").failed

    def test_v6_rejects_empty_reference_set(self, allocator, path):
        """Explanation construction blocks this; the rule is defence in depth."""
        attrs = fact_attrs(allocator)
        broken = Explanation.__new__(Explanation)
        object.__setattr__(broken, "objects_referenced", ())
        object.__setattr__(broken, "criteria_applied", ("x",))
        object.__setattr__(broken, "reasoning", "r")
        object.__setattr__(broken, "alternatives_rejected", ())
        object.__setattr__(attrs, "explanation", broken)
        assert self._outcome(path, ctx_for(attrs), "V6").failed

    def test_v8_rejects_out_of_order_timestamps(self, allocator, path):
        attrs = fact_attrs(allocator)
        object.__setattr__(attrs, "observed_at", T0 + timedelta(days=5))
        assert self._outcome(path, ctx_for(attrs), "V8").failed

    def test_v9_rejects_missing_reason(self, allocator, path):
        attrs = fact_attrs(allocator)
        object.__setattr__(attrs, "status", ObjectStatus.REJECTED)
        object.__setattr__(attrs, "status_reason", None)
        assert self._outcome(path, ctx_for(attrs), "V9").failed

    def test_v11_rejects_same_object_id_across_versions(self, allocator, path):
        predecessor = fact_attrs(allocator)
        successor = fact_attrs(allocator, identity=predecessor.identity)
        ctx = ctx_for(successor, predecessor=predecessor)
        assert self._outcome(path, ctx, "V11").failed

    def test_v11_rejects_non_incrementing_version(self, allocator, path):
        first = allocator.new_object()
        third = allocator.succeed(allocator.succeed(first))
        predecessor = fact_attrs(allocator, identity=first)
        successor = fact_attrs(allocator, identity=third)
        ctx = ctx_for(successor, predecessor=predecessor)
        assert self._outcome(path, ctx, "V11").failed

    def test_v12_rejects_unknown_reference_type(self, allocator):
        """Evaluate V12 alone: V3 rejects the same object earlier."""
        from oip.acceptance import v12_closed_taxonomy

        attrs = fact_attrs(allocator)
        bad = LineageRef.__new__(LineageRef)
        object.__setattr__(bad, "object_id", "obj-ev-1")
        object.__setattr__(bad, "object_type", "Evidence")
        object.__setattr__(attrs, "derives_from", (bad,))
        assert v12_closed_taxonomy(ctx_for(attrs)).failed

    def test_rule_result_failed_property(self):
        assert RuleResult("X", RuleOutcome.FAIL).failed
        assert not RuleResult("X", RuleOutcome.PASS).failed
        assert not RuleResult("X", RuleOutcome.SKIP).failed

    def test_acceptance_result_exposes_failures(self, allocator, path):
        result = path.accept(
            ctx_for(fact_attrs(allocator, produced_by_engine=Engine.RESEARCH))
        )
        assert all(r.failed for r in result.failures)

    def test_failure_record_rule_ids(self, allocator, path):
        result = path.accept(
            ctx_for(fact_attrs(allocator, produced_by_engine=Engine.RESEARCH))
        )
        assert isinstance(result.failure.rule_ids, tuple)
        assert "V7" in result.failure.rule_ids
