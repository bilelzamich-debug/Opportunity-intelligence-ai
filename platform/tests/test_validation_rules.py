"""Contract tests for validation rules wired to real traversal.

Tasks: T01.4.2 (V1-V4), T01.5.2 (ceiling), T01.4.6 (semantic hook)

Architecture References:
- V1-V4 Attributes present, lineage non-empty, references resolve,
        Evidence reachable BY TRAVERSAL not assertion
- V5    Confidence ceiling from actual lineage
- R-3   Two-component confidence; monotonic ceiling
- S-5   Semantic hook; M-67 residual risk measured
- N-6   Store authoritative; graph derived

Acceptance criteria under test:
  T01.4.2  Each rule independently testable
           V2 exempts Evidence only
           V4 verified by actual traversal, not assertion
  T01.5.2  Ceiling computed from actual lineage
           Violation rejected at acceptance
           Worked chain 0.62 -> 0.58 reproduces the IOM example
  T01.4.6  Hook invocable at acceptance
           Anchor verification pluggable
           Documented as not covering paraphrase drift
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import (
    AcceptanceContext,
    AcceptancePath,
    RuleOutcome,
    v1_required_attributes_present,
    v2_derives_from_non_empty,
    v3_references_resolve,
    v4_evidence_reachable,
    v5_confidence_ceiling,
)
from oip.contract import Confidence
from oip.enums import ConfidenceBand, Engine, ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import (
    build_attrs,
    build_lineage,
    write_chain,
    write_derived,
    write_evidence,
)


# ---------------------------------------------------------------------------
# T01.4.2 -- V1-V4 independently testable
# ---------------------------------------------------------------------------

class TestRulesIndependentlyTestable:
    def _ctx(self, store, attrs):
        return AcceptanceContext(
            attributes=attrs,
            resolve_type=store.resolve_type,
            reaches_evidence=store.graph.reaches_evidence,
            would_cycle=store.graph.would_introduce_cycle,
            upstream_confidence=store._upstream_confidence,
        )

    def test_v1_runs_standalone(self, store, allocator):
        attrs = build_attrs(allocator.new_object(), ObjectType.EVIDENCE)
        assert v1_required_attributes_present(self._ctx(store, attrs)).outcome \
            is RuleOutcome.PASS

    def test_v2_runs_standalone(self, store, allocator):
        attrs = build_attrs(allocator.new_object(), ObjectType.EVIDENCE)
        assert not v2_derives_from_non_empty(self._ctx(store, attrs)).failed

    def test_v3_runs_standalone(self, store, allocator):
        evidence = write_evidence(store, allocator)
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            ((evidence.object_id, ObjectType.EVIDENCE),),
        )
        assert not v3_references_resolve(self._ctx(store, attrs)).failed

    def test_v4_runs_standalone(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert not v4_evidence_reachable(
            self._ctx(store, fact.attributes)
        ).failed

    def test_each_rule_has_a_distinct_id(self):
        ids = {
            r.rule_id for r in (
                v1_required_attributes_present, v2_derives_from_non_empty,
                v3_references_resolve, v4_evidence_reachable, v5_confidence_ceiling,
            )
        }
        assert ids == {"V1", "V2", "V3", "V4", "V5"}


class TestV2ExemptsEvidenceOnly:
    def _ctx(self, attrs):
        return AcceptanceContext(attributes=attrs)

    def test_evidence_exempt(self, allocator):
        attrs = build_attrs(allocator.new_object(), ObjectType.EVIDENCE)
        result = v2_derives_from_non_empty(self._ctx(attrs))
        assert not result.failed
        assert "root" in result.detail

    @pytest.mark.parametrize(
        "object_type", [t for t in ObjectType if not t.is_root]
    )
    def test_every_other_type_requires_lineage(self, allocator, object_type):
        attrs = build_attrs(allocator.new_object(), object_type)
        assert v2_derives_from_non_empty(self._ctx(attrs)).failed

    def test_evidence_with_lineage_rejected(self, allocator):
        """AD-05: exemption is one-directional."""
        attrs = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            (("obj-fr-1", ObjectType.FEEDBACK_RECORD),),
        )
        assert v2_derives_from_non_empty(self._ctx(attrs)).failed


class TestV4UsesRealTraversal:
    def test_v4_passes_only_with_a_real_path(self, store, allocator):
        """AC: verified by actual traversal, not assertion. [V4]"""
        chain = write_chain(store, allocator)
        validation = chain[ObjectType.VALIDATION]
        ctx = AcceptanceContext(
            attributes=validation.attributes,
            reaches_evidence=store.graph.reaches_evidence,
        )
        assert not v4_evidence_reachable(ctx).failed
        assert store.graph.depth_to_evidence(validation.object_id) == 6

    def test_v4_rejects_asserted_but_unreachable(self, store, allocator):
        """evidence_reachable=True must not substitute for a real path."""
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-phantom", ObjectType.EVIDENCE),),
            evidence_reachable=True,
        )
        ctx = AcceptanceContext(
            attributes=attrs, reaches_evidence=lambda oid: False
        )
        assert v4_evidence_reachable(ctx).failed

    def test_v4_rejects_false_flag_with_real_path(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        attrs = fact.attributes
        object.__setattr__(attrs, "evidence_reachable", False)
        ctx = AcceptanceContext(
            attributes=attrs, reaches_evidence=store.graph.reaches_evidence
        )
        assert v4_evidence_reachable(ctx).failed

    def test_orphan_write_rejected_end_to_end(self, store, allocator):
        """A Fact referencing nothing stored cannot be written. [V3, V4]"""
        identity = allocator.new_object()
        upstream = (("obj-never-written", ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        lineage = build_lineage(identity.object_id, ObjectType.FACT, upstream)
        with pytest.raises(WriteRejectedError) as exc:
            store.write(attrs, lineage)
        assert "V3" in exc.value.failure.rule_ids


# ---------------------------------------------------------------------------
# T01.5.2 -- ceiling from actual lineage
# ---------------------------------------------------------------------------

class TestCeilingFromLineage:
    def test_ceiling_read_from_stored_upstream(self, store, allocator):
        evidence = write_evidence(store, allocator, support=0.55, assertion=0.90)
        assert store._upstream_confidence(evidence.object_id) == pytest.approx(0.55)

    def test_violation_rejected_at_acceptance(self, store, allocator):
        evidence = write_evidence(store, allocator, support=0.40, assertion=0.90)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            support=0.95, assertion=0.95,   # no upstream_ceiling applied
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        lineage = build_lineage(identity.object_id, ObjectType.FACT, upstream)
        with pytest.raises(WriteRejectedError) as exc:
            store.write(attrs, lineage)
        assert "V5" in exc.value.failure.rule_ids

    def test_ceiling_takes_minimum_across_multiple_parents(self, store, allocator):
        weak = write_evidence(store, allocator, support=0.30, assertion=0.90)
        strong = write_evidence(store, allocator, support=0.90, assertion=0.90)
        fact = write_derived(store, allocator, ObjectType.FACT, [weak, strong])
        assert fact.attributes.confidence.effective_confidence <= 0.30

    def test_iom_worked_chain_reproduced_through_the_store(self, store, allocator):
        """IOM section 4.4: Evidence 0.62 -> Opportunity 0.58 MODERATE. [R-3]

        Four confident inferential steps over moderate evidence must yield a
        moderate conclusion, not a confident one.
        """
        evidence = write_evidence(store, allocator, support=0.62, assertion=0.90)
        assert evidence.attributes.confidence.effective_confidence == pytest.approx(0.62)

        fact = write_derived(
            store, allocator, ObjectType.FACT, [evidence],
            support=0.71, assertion=0.84,
        )
        problem = write_derived(
            store, allocator, ObjectType.PROBLEM, [fact],
            support=0.66, assertion=0.74,
        )
        pattern = write_derived(
            store, allocator, ObjectType.PATTERN, [problem],
            support=0.64, assertion=0.71,
        )
        opportunity = write_derived(
            store, allocator, ObjectType.OPPORTUNITY, [pattern],
            support=0.64, assertion=0.58,
        )

        for stage in (fact, problem, pattern):
            assert stage.attributes.confidence.effective_confidence == pytest.approx(0.62)
        assert opportunity.attributes.confidence.effective_confidence == pytest.approx(0.58)
        assert opportunity.attributes.confidence.band is ConfidenceBand.MODERATE

    def test_confidence_never_rises_along_a_stored_chain(self, store, allocator):
        chain = write_chain(store, allocator)
        ordered = [
            chain[t] for t in (
                ObjectType.EVIDENCE, ObjectType.FACT, ObjectType.PROBLEM,
                ObjectType.PATTERN, ObjectType.OPPORTUNITY, ObjectType.SOLUTION,
                ObjectType.VALIDATION,
            )
        ]
        values = [s.attributes.confidence.effective_confidence for s in ordered]
        for earlier, later in zip(values, values[1:]):
            assert later <= earlier + 1e-9


# ---------------------------------------------------------------------------
# T01.4.6 -- semantic hook
# ---------------------------------------------------------------------------

class TestSemanticHook:
    def _ctx(self, attrs):
        return AcceptanceContext(attributes=attrs)

    def test_hook_invocable_at_acceptance(self, allocator):
        path = AcceptancePath(semantic_verifiers=(AnchorVerifier(),))
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        results = path.evaluate(self._ctx(attrs))
        assert "F-V6" in {r.rule_id for r in results}

    def test_unconfigured_hook_skips_and_says_so(self, allocator):
        verifier = AnchorVerifier()
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        result = verifier(self._ctx(attrs))
        assert result.outcome is RuleOutcome.SKIP
        assert "M-67" in result.detail

    def test_hook_skips_non_facts(self, allocator):
        verifier = AnchorVerifier(
            span_provider=lambda a: "text", claims_of=lambda c: ()
        )
        attrs = build_attrs(allocator.new_object(), ObjectType.EVIDENCE)
        assert verifier(self._ctx(attrs)).outcome is RuleOutcome.SKIP

    def test_anchor_verification_is_pluggable(self, allocator):
        span = "Sellers report bulk updates fail silently above 50 items."
        verifier = AnchorVerifier(
            span_provider=lambda a: span,
            claims_of=lambda c: (
                AnchorClaim(
                    claim="bulk updates fail silently",
                    anchor=Anchor("obj-ev-1", "line-3"),
                    subject="bulk updates",
                    predicate="fail silently",
                ),
            ),
        )
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        assert verifier(self._ctx(attrs)).outcome is RuleOutcome.PASS

    def test_fabricated_anchor_rejected(self, allocator):
        verifier = AnchorVerifier(
            span_provider=lambda a: None,
            claims_of=lambda c: (
                AnchorClaim("any claim", Anchor("obj-ev-1", "line-999")),
            ),
        )
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        result = verifier(self._ctx(attrs))
        assert result.failed
        assert "fabricated location" in result.detail

    def test_fabricated_value_rejected(self, allocator):
        verifier = AnchorVerifier(
            span_provider=lambda a: "Sellers report failures above 50 items.",
            claims_of=lambda c: (
                AnchorClaim(
                    claim="failures above 500 items",
                    anchor=Anchor("obj-ev-1", "line-3"),
                    subject="sellers",
                    value="500",
                ),
            ),
        )
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        result = verifier(self._ctx(attrs))
        assert result.failed
        assert "value" in result.detail

    def test_paraphrase_drift_is_documented_as_uncovered(self, allocator):
        """M-67 stays OPEN: Layer 1 cannot catch meaning shift. [S-5]"""
        verifier = AnchorVerifier(
            span_provider=lambda a: "Some sellers occasionally report issues.",
            claims_of=lambda c: (
                AnchorClaim(
                    claim="All sellers consistently report failures",
                    anchor=Anchor("obj-ev-1", "line-3"),
                    subject="sellers",
                    predicate="report",
                ),
            ),
        )
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        result = verifier(self._ctx(attrs))
        # Drift passes Layer 1 -- deliberately, and the detail says so.
        assert result.outcome is RuleOutcome.PASS
        assert "paraphrase drift not covered" in result.detail
        assert verifier.covers_paraphrase_drift is False

    def test_failure_rate_is_measured(self, allocator):
        spans = {"good": "claim text here", "bad": None}
        state = {"key": "good"}
        verifier = AnchorVerifier(
            span_provider=lambda a: spans[state["key"]],
            claims_of=lambda c: (
                AnchorClaim("claim text", Anchor("obj-ev-1", "l1"),
                            subject="claim"),
            ),
        )
        attrs = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
        )
        verifier(self._ctx(attrs))
        state["key"] = "bad"
        verifier(self._ctx(attrs))

        assert verifier.checked == 2
        assert verifier.failed == 1
        assert verifier.anchor_failure_rate == pytest.approx(0.5)

    def test_rate_is_zero_before_any_check(self):
        assert AnchorVerifier().anchor_failure_rate == 0.0

    def test_hook_rejects_write_end_to_end(self, allocator):
        store = KnowledgeStore(
            acceptance=AcceptancePath(
                semantic_verifiers=(
                    AnchorVerifier(
                        span_provider=lambda a: None,
                        claims_of=lambda c: (
                            AnchorClaim("x", Anchor("obj-ev-1", "l1")),
                        ),
                    ),
                )
            )
        )
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        attrs = build_attrs(
            identity, ObjectType.FACT, upstream,
            status=ObjectStatus.ACTIVE, status_reason=None,
            upstream_ceiling=evidence.attributes.confidence.effective_confidence,
        )
        lineage = build_lineage(identity.object_id, ObjectType.FACT, upstream)
        with pytest.raises(WriteRejectedError) as exc:
            store.write(attrs, lineage)
        assert "F-V6" in exc.value.failure.rule_ids

    def test_anchor_requires_both_fields(self):
        for kwargs in ({"evidence_id": "", "locator": "l"},
                       {"evidence_id": "e", "locator": ""}):
            with pytest.raises(ValueError):
                Anchor(**kwargs)


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=40, deadline=None)
@given(
    support=st.floats(0.05, 1.0, allow_nan=False),
    steps=st.integers(min_value=1, max_value=5),
)
def test_stored_chain_never_exceeds_root_confidence(support, steps):
    """The ceiling holds through the store for any root value. [R-3, V5]"""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    ladder = [
        ObjectType.FACT, ObjectType.PROBLEM, ObjectType.PATTERN,
        ObjectType.OPPORTUNITY, ObjectType.SOLUTION,
    ]
    current = write_evidence(store, allocator, support=support, assertion=1.0)
    root_value = current.attributes.confidence.effective_confidence

    for i in range(steps):
        current = write_derived(
            store, allocator, ladder[i], [current], support=1.0, assertion=1.0
        )
        assert current.attributes.confidence.effective_confidence <= root_value + 1e-9


@settings(max_examples=60, deadline=None)
@given(object_type=st.sampled_from(list(ObjectType)))
def test_v2_exemption_is_exactly_evidence(object_type):
    allocator = IdentityAllocator()
    attrs = build_attrs(allocator.new_object(), object_type)
    ctx = AcceptanceContext(attributes=attrs)
    assert v2_derives_from_non_empty(ctx).failed is (not object_type.is_root)
