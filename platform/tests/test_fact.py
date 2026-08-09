"""Contract tests for the Fact object type.

Task: T01.7.2b / T01.7.2c

Architecture References:
- F-V1..F-V6  Fact validation rules
- F-I1..F-I4  Fact integrity constraints
- R-5 / D-05  Canonical claims, not extraction events
- S-3         Equivalence and merge policy
- S-5 / M-67  Anchor verification hook only; drift remains unmeasured
- R-3         Confidence bounded by attached Evidence
- N-16        independent_source_count

Acceptance criteria under test:
  AC1  Multiple attachments per Fact supported
  AC2  Positional anchor required per attachment
  AC3  independent_source_count <= attachment count
  AC4  F-V6 hook wired
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.claim import Claim, Quantity, Verdict
from oip.contract import LineageRef
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.fact import (
    FACT_RULES,
    AttachmentError,
    ClaimType,
    ClaimTypeError,
    EvidenceAttachment,
    Fact,
    FactError,
    Independence,
    MergeJustification,
    MergeJustificationError,
    SourceCountError,
    fv1_attachment_present,
    fv2_attachments_resolvable,
    fv3_claim_self_contained,
    fv4_claim_type_declared,
    fv5_source_count_bounded,
    fv6_anchor_verification,
)
from oip.identity import IdentityAllocator
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs
from tests.test_evidence import evidence as make_evidence

EXTRACTED = T0 + timedelta(hours=3)


def attachment(evidence_ref: str, **overrides) -> EvidenceAttachment:
    kwargs = {
        "evidence_ref": evidence_ref,
        "positional_anchor": "corpus/entry-4471/lines-3-6",
        "extracted_at": EXTRACTED,
        "extraction_confidence": 0.88,
        "independence_assessment": Independence.INDEPENDENT,
    }
    kwargs.update(overrides)
    return EvidenceAttachment(**kwargs)


def claim() -> Claim:
    return Claim(
        subject="bulk listing updates",
        predicate="fail silently",
        qualifier="operations above 50 items",
    )


def make_fact(
    allocator: IdentityAllocator,
    refs: tuple[str, ...] = ("obj-ev-1",),
    *,
    source_count: int | None = None,
    upstream_ceiling: float | None = None,
    **overrides,
) -> Fact:
    identity = overrides.pop("identity", None) or allocator.new_object()
    count = source_count if source_count is not None else len(refs)
    attributes = build_attrs(
        identity,
        ObjectType.FACT,
        tuple((r, ObjectType.EVIDENCE) for r in refs),
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        source_count=count,
        upstream_ceiling=upstream_ceiling,
    )
    kwargs = {
        "attributes": attributes,
        "claim": overrides.pop("claim", claim()),
        "claim_type": overrides.pop("claim_type", ClaimType.ASSERTION),
        "attachments": overrides.pop(
            "attachments", tuple(attachment(r) for r in refs)
        ),
        "qualifying_context": overrides.pop(
            "qualifying_context", "reported for operations exceeding 50 items"
        ),
    }
    kwargs.update(overrides)
    return Fact(**kwargs)


def ctx(fact: Fact, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": fact.attributes, "fact": fact}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


@pytest.fixture()
def evidence_pair(store, allocator):
    a = store.write_evidence(
        make_evidence(allocator, content="alpha", source_identifier="src-A")
    )
    b = store.write_evidence(
        make_evidence(allocator, content="beta", source_identifier="src-B")
    )
    return a, b


def write_fact_from(store, allocator, stored_evidence, **overrides):
    refs = tuple(e.object_id for e in stored_evidence)
    ceiling = min(
        e.attributes.confidence.effective_confidence for e in stored_evidence
    )
    return store.write_fact(
        make_fact(allocator, refs, upstream_ceiling=ceiling, **overrides)
    )


# ===========================================================================
# AC1 -- multiple attachments  [R-5, D-05]
# ===========================================================================

class TestMultipleAttachments:
    def test_single_attachment_accepted(self, allocator):
        assert make_fact(allocator).attachment_count == 1

    def test_many_attachments_accepted(self, allocator):
        refs = tuple(f"obj-ev-{i}" for i in range(12))
        assert make_fact(allocator, refs).attachment_count == 12

    def test_attachments_written_to_store(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        assert store.get_fact(stored.object_id).attachment_count == 2

    def test_ten_sources_one_fact(self, store, allocator):
        """R-5: corroboration produces attachments, not duplicate Facts."""
        sources = [
            store.write_evidence(
                make_evidence(
                    allocator, content=f"text-{i}", source_identifier=f"src-{i}"
                )
            )
            for i in range(10)
        ]
        stored = write_fact_from(store, allocator, sources)
        assert store.get_fact(stored.object_id).attachment_count == 10
        assert len(store.objects_of_type(ObjectType.FACT)) == 1

    def test_no_attachments_rejected(self, allocator):
        with pytest.raises(AttachmentError):
            make_fact(allocator, attachments=())

    def test_same_evidence_attached_twice_rejected(self, allocator):
        with pytest.raises(AttachmentError):
            make_fact(
                allocator, ("obj-ev-1",),
                attachments=(attachment("obj-ev-1"), attachment("obj-ev-1")),
            )

    def test_evidence_refs_exposed(self, allocator):
        fact = make_fact(allocator, ("obj-ev-1", "obj-ev-2"))
        assert fact.evidence_refs == ("obj-ev-1", "obj-ev-2")

    def test_attachment_lookup(self, allocator):
        fact = make_fact(allocator, ("obj-ev-1", "obj-ev-2"))
        assert fact.attachment_for("obj-ev-2") is not None
        assert fact.attachment_for("obj-absent") is None


# ===========================================================================
# AC2 -- positional anchor required  [F-V2]
# ===========================================================================

class TestPositionalAnchor:
    def test_anchor_required(self):
        with pytest.raises(AttachmentError):
            attachment("obj-ev-1", positional_anchor="")

    @pytest.mark.parametrize("blank", ["", "   ", "\t", "\n"])
    def test_whitespace_is_not_an_anchor(self, blank):
        with pytest.raises(AttachmentError):
            attachment("obj-ev-1", positional_anchor=blank)

    def test_evidence_ref_required(self):
        with pytest.raises(AttachmentError):
            attachment("")

    def test_extracted_at_required(self):
        with pytest.raises(AttachmentError):
            attachment("obj-ev-1", extracted_at="2026-03-01")

    @pytest.mark.parametrize("bad", [-0.1, 1.1])
    def test_extraction_confidence_range(self, bad):
        with pytest.raises(AttachmentError):
            attachment("obj-ev-1", extraction_confidence=bad)

    def test_fv2_detects_stripped_anchor(self, allocator):
        fact = make_fact(allocator)
        object.__setattr__(fact.attachments[0], "positional_anchor", "")
        result = fv2_attachments_resolvable(ctx(fact))
        assert result.failed
        assert "no anchor" in result.detail

    def test_fv2_requires_refs_to_resolve_to_evidence(self, allocator):
        fact = make_fact(allocator)
        result = fv2_attachments_resolvable(
            ctx(fact, resolve_type=lambda oid: ObjectType.PROBLEM)
        )
        assert result.failed
        assert "do not resolve to Evidence" in result.detail

    def test_fv2_skips_resolution_without_a_resolver(self, allocator):
        result = fv2_attachments_resolvable(ctx(make_fact(allocator)))
        assert result.outcome is RuleOutcome.SKIP

    def test_attachment_projects_to_anchor(self, allocator):
        anchor = make_fact(allocator).attachments[0].as_anchor()
        assert isinstance(anchor, Anchor)
        assert anchor.evidence_id == "obj-ev-1"

    def test_store_rejects_unresolvable_attachment(self, store, allocator):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_fact(make_fact(allocator, ("obj-never-written",)))
        assert {"V3", "F-V2"} & set(exc.value.failure.rule_ids)


# ===========================================================================
# AC3 -- independent_source_count <= attachment count  [F-V5, N-16]
# ===========================================================================

class TestSourceCountBound:
    def test_equal_count_accepted(self, allocator):
        fact = make_fact(allocator, ("obj-ev-1", "obj-ev-2"), source_count=2)
        assert fact.independent_source_count == 2

    def test_lower_count_accepted(self, allocator):
        """Non-independent attachments count once. [N-16]"""
        fact = make_fact(allocator, ("obj-ev-1", "obj-ev-2"), source_count=1)
        assert fact.independent_source_count == 1

    def test_excess_count_rejected_at_construction(self, allocator):
        with pytest.raises(SourceCountError):
            make_fact(allocator, ("obj-ev-1",), source_count=5)

    def test_fv5_detects_smuggled_excess(self, allocator):
        fact = make_fact(allocator)
        object.__setattr__(fact.attributes, "independent_source_count", 9)
        result = fv5_source_count_bounded(ctx(fact))
        assert result.failed
        assert "cannot exceed its sources" in result.detail

    def test_zero_count_accepted(self, allocator):
        assert make_fact(allocator, source_count=0).independent_source_count == 0

    def test_counted_independent_reflects_assessments(self, allocator):
        fact = make_fact(
            allocator, ("obj-ev-1", "obj-ev-2"),
            attachments=(
                attachment("obj-ev-1", independence_assessment=Independence.INDEPENDENT),
                attachment("obj-ev-2",
                           independence_assessment=Independence.NOT_INDEPENDENT),
            ),
            source_count=1,
        )
        assert fact.counted_independent() == 1

    def test_corroboration_flag(self, allocator):
        assert not make_fact(allocator, source_count=1).is_corroborated
        assert make_fact(
            allocator, ("obj-ev-1", "obj-ev-2"), source_count=2
        ).is_corroborated


# ===========================================================================
# AC4 -- F-V6 hook wired  [S-5, M-67]
# ===========================================================================

class TestAnchorVerificationHook:
    def test_rule_registered(self, store):
        assert "F-V6" in store.acceptance.rule_ids

    def test_skips_and_says_risk_unmeasured_when_absent(self, allocator):
        """M-67 stays open; the platform must say so rather than imply safety."""
        result = fv6_anchor_verification(ctx(make_fact(allocator)))
        assert result.outcome is RuleOutcome.SKIP
        assert "M-67 open" in result.detail

    def test_delegates_to_the_existing_verifier(self, allocator):
        """S-5: hook only. No new detection system is introduced."""
        verifier = AnchorVerifier(
            span_provider=lambda a: "bulk listing updates fail silently",
            claims_of=lambda c: (
                AnchorClaim(
                    claim="bulk listing updates fail silently",
                    anchor=Anchor("obj-ev-1", "line-3"),
                    subject="bulk listing updates",
                    predicate="fail silently",
                ),
            ),
        )
        result = fv6_anchor_verification(
            ctx(make_fact(allocator), anchor_verifier=verifier)
        )
        assert result.outcome is RuleOutcome.PASS

    def test_fabricated_anchor_rejected_through_the_hook(self, allocator):
        verifier = AnchorVerifier(
            span_provider=lambda a: None,
            claims_of=lambda c: (
                AnchorClaim("any", Anchor("obj-ev-1", "line-999")),
            ),
        )
        result = fv6_anchor_verification(
            ctx(make_fact(allocator), anchor_verifier=verifier)
        )
        assert result.failed
        assert "fabricated location" in result.detail

    def test_store_can_install_a_verifier(self, store, allocator, evidence_pair):
        store.anchor_verifier = AnchorVerifier(
            span_provider=lambda a: None,
            claims_of=lambda c: (AnchorClaim("x", Anchor("obj-ev-1", "l1")),),
        )
        with pytest.raises(WriteRejectedError) as exc:
            write_fact_from(store, allocator, evidence_pair)
        assert "F-V6" in exc.value.failure.rule_ids

    def test_paraphrase_drift_still_uncovered(self, allocator):
        """M-67: Layer 1 cannot catch meaning shift. Recorded, not hidden."""
        verifier = AnchorVerifier(
            span_provider=lambda a: "some sellers occasionally report issues",
            claims_of=lambda c: (
                AnchorClaim(
                    claim="all sellers consistently report failures",
                    anchor=Anchor("obj-ev-1", "l1"),
                    subject="sellers",
                    predicate="report",
                ),
            ),
        )
        result = fv6_anchor_verification(
            ctx(make_fact(allocator), anchor_verifier=verifier)
        )
        assert result.outcome is RuleOutcome.PASS
        assert verifier.covers_paraphrase_drift is False


# ===========================================================================
# F-V1, F-V3, F-V4
# ===========================================================================

class TestRemainingValidationRules:
    def test_fv1_passes_with_attachments(self, allocator):
        assert not fv1_attachment_present(ctx(make_fact(allocator))).failed

    def test_fv1_skips_non_facts(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = fv1_attachment_present(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP

    def test_fv3_requires_qualifying_context(self, allocator):
        with pytest.raises(FactError):
            make_fact(allocator, qualifying_context="")

    def test_fv3_detects_stripped_context(self, allocator):
        fact = make_fact(allocator)
        object.__setattr__(fact, "qualifying_context", "")
        result = fv3_claim_self_contained(ctx(fact))
        assert result.failed
        assert "loses meaning" in result.detail

    def test_fv3_requires_claim_components(self, allocator):
        fact = make_fact(allocator)
        object.__setattr__(fact.claim, "subject", "")
        assert fv3_claim_self_contained(ctx(fact)).failed

    def test_fv4_assertion_needs_no_attribution(self, allocator):
        assert not fv4_claim_type_declared(ctx(make_fact(allocator))).failed

    def test_fv4_opinion_requires_attribution(self, allocator):
        with pytest.raises(ClaimTypeError):
            make_fact(allocator, claim_type=ClaimType.ATTRIBUTED_OPINION)

    def test_fv4_opinion_with_attribution_accepted(self, allocator):
        fact = make_fact(
            allocator,
            claim_type=ClaimType.ATTRIBUTED_OPINION,
            attributed_to="seller-forum-user-88",
        )
        assert not fv4_claim_type_declared(ctx(fact)).failed

    def test_fv4_detects_stripped_attribution(self, allocator):
        fact = make_fact(
            allocator,
            claim_type=ClaimType.ATTRIBUTED_OPINION,
            attributed_to="someone",
        )
        object.__setattr__(fact, "attributed_to", "")
        result = fv4_claim_type_declared(ctx(fact))
        assert result.failed
        assert "misleads every downstream stage" in result.detail

    def test_all_six_rules_registered(self, store):
        assert {f"F-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)

    def test_rules_skip_non_facts(self, store, allocator):
        """One acceptance path serves all nine types."""
        stored = store.write_evidence(make_evidence(allocator))
        assert stored.status is ObjectStatus.ACTIVE


# ===========================================================================
# Corroboration and merge  [R-5, S-3, F-I4]
# ===========================================================================

class TestCorroboration:
    def _justification(self, ref: str) -> MergeJustification:
        return MergeJustification(
            verdict=Verdict.EQUIVALENT,
            reason="subject, predicate, qualifier and value all agree",
            merged_evidence_ref=ref,
            merged_at=EXTRACTED,
        )

    def test_attachment_returns_a_new_fact(self, allocator):
        original = make_fact(allocator)
        extended = original.with_attachment(
            attachment("obj-ev-2"), self._justification("obj-ev-2")
        )
        assert extended is not original
        assert original.attachment_count == 1
        assert extended.attachment_count == 2

    def test_attachment_extends_lineage(self, allocator):
        extended = make_fact(allocator).with_attachment(
            attachment("obj-ev-2"), self._justification("obj-ev-2")
        )
        assert "obj-ev-2" in [r.object_id for r in extended.attributes.derives_from]

    def test_independent_attachment_raises_the_count(self, allocator):
        extended = make_fact(allocator, source_count=1).with_attachment(
            attachment("obj-ev-2"), self._justification("obj-ev-2")
        )
        assert extended.independent_source_count == 2

    def test_non_independent_attachment_does_not(self, allocator):
        """Syndicated corroboration must not inflate. [N-16]"""
        extended = make_fact(allocator, source_count=1).with_attachment(
            attachment(
                "obj-ev-2",
                independence_assessment=Independence.NOT_INDEPENDENT,
            ),
            self._justification("obj-ev-2"),
        )
        assert extended.independent_source_count == 1

    def test_duplicate_attachment_rejected(self, allocator):
        with pytest.raises(AttachmentError):
            make_fact(allocator).with_attachment(
                attachment("obj-ev-1"), self._justification("obj-ev-1")
            )

    def test_justification_must_match_the_attachment(self, allocator):
        with pytest.raises(MergeJustificationError):
            make_fact(allocator).with_attachment(
                attachment("obj-ev-2"), self._justification("obj-ev-9")
            )

    def test_only_equivalent_verdicts_may_justify(self):
        for verdict in (Verdict.CONTAINMENT, Verdict.UNCERTAIN,
                        Verdict.NOT_EQUIVALENT):
            with pytest.raises(MergeJustificationError):
                MergeJustification(verdict, "r", "obj-ev-2", EXTRACTED)

    def test_justification_requires_a_reason(self):
        with pytest.raises(MergeJustificationError):
            MergeJustification(Verdict.EQUIVALENT, "  ", "obj-ev-2", EXTRACTED)

    def test_merge_history_accumulates(self, allocator):
        fact = make_fact(allocator)
        for i in range(2, 5):
            fact = fact.with_attachment(
                attachment(f"obj-ev-{i}"), self._justification(f"obj-ev-{i}")
            )
        assert len(fact.merge_history) == 3

    def test_attachments_are_retained_across_versions(self, allocator):
        original = make_fact(allocator)
        extended = original.with_attachment(
            attachment("obj-ev-2"), self._justification("obj-ev-2")
        )
        assert extended.retains_attachments_of(original)

    def test_assess_against_uses_s3(self, allocator):
        fact = make_fact(allocator)
        result = fact.assess_against(fact.claim)
        assert result.verdict is Verdict.EQUIVALENT


# ===========================================================================
# Registry: canonical-claim resolution  [R-5, S-3]
# ===========================================================================

class TestFactRegistry:
    def test_payload_retrievable(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        assert store.get_fact(stored.object_id) is not None

    def test_unknown_payload_is_none(self, store):
        assert store.get_fact("obj-absent") is None

    def test_equivalent_claim_found(self, store, allocator, evidence_pair):
        write_fact_from(store, allocator, evidence_pair)
        match = store.facts.find_equivalent(claim())
        assert match is not None
        assert match[1].verdict is Verdict.EQUIVALENT

    def test_different_claim_not_found(self, store, allocator, evidence_pair):
        write_fact_from(store, allocator, evidence_pair)
        assert store.facts.find_equivalent(
            Claim("something", "entirely different")
        ) is None

    def test_uncertain_claim_is_not_a_merge_candidate(
        self, store, allocator, evidence_pair
    ):
        """S-3: undecidable equivalence must not merge."""
        write_fact_from(store, allocator, evidence_pair)
        other = Claim("bulk listing updates", "fail silently", "a different scope")
        assert store.facts.find_equivalent(other) is None

    def test_assess_all_surfaces_non_merging_verdicts(
        self, store, allocator, evidence_pair
    ):
        write_fact_from(store, allocator, evidence_pair)
        other = Claim("bulk listing updates", "fail silently", "a different scope")
        verdicts = [r.verdict for _, r in store.facts.assess_all(other)]
        assert Verdict.UNCERTAIN in verdicts

    def test_retracted_facts_excluded(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.facts.find_equivalent(claim()) is None

    def test_registry_counts(self, store, allocator, evidence_pair):
        write_fact_from(store, allocator, evidence_pair)
        assert len(store.facts) == 1


# ===========================================================================
# F-I1..F-I4  integrity
# ===========================================================================

class TestFactIntegrity:
    def test_clean_single_attachment_store_holds(self, store, allocator,
                                                 evidence_pair):
        """A Fact with one attachment involves no merge, so F-I4 is satisfied."""
        write_fact_from(store, allocator, evidence_pair[:1])
        assert store.facts.integrity().verify() == ()

    def test_multi_attachment_requires_justifications(self, store, allocator,
                                                      evidence_pair):
        """F-I4: attachments beyond the first arrived by a merge.

        Constructing a multi-attachment Fact directly, without recording why
        the claims were judged equivalent, is exactly what F-I4 forbids.
        """
        write_fact_from(store, allocator, evidence_pair)
        violations = store.facts.integrity().verify()
        assert [v.constraint_id for v in violations] == ["F-I4"]

    def test_multi_attachment_with_justifications_holds(self, store, allocator,
                                                        evidence_pair):
        first, second = evidence_pair
        ceiling = min(
            e.attributes.confidence.effective_confidence for e in evidence_pair
        )
        base = make_fact(
            allocator, (first.object_id,), upstream_ceiling=ceiling
        )
        merged = base.with_attachment(
            attachment(second.object_id),
            MergeJustification(
                Verdict.EQUIVALENT, "claims agree on all four components",
                second.object_id, EXTRACTED,
            ),
        )
        store.write_fact(merged)
        assert store.facts.integrity().verify() == ()

    def test_fi1_detects_missing_evidence(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        del store._objects[evidence_pair[0].object_id]
        violations = store.facts.integrity().verify()
        assert any(v.constraint_id == "F-I1" for v in violations)
        assert "no verifiable source" in violations[0].detail

    def test_fi1_detects_non_evidence_attachment(
        self, store, allocator, evidence_pair
    ):
        stored = write_fact_from(store, allocator, evidence_pair)
        fact = store.get_fact(stored.object_id)
        object.__setattr__(
            fact.attachments[0], "evidence_ref", stored.object_id
        )
        violations = store.facts.integrity().verify()
        assert any("not Evidence" in v.detail for v in violations)

    def test_fi2_detects_removed_attachments(self, store, allocator, evidence_pair):
        """Attachments are add-only across a supersession chain. [F-I2]"""
        first = write_fact_from(store, allocator, evidence_pair)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "re-extracted")

        successor = allocator.succeed(first.attributes.identity)
        reduced = make_fact(
            allocator, (evidence_pair[0].object_id,),
            identity=successor,
            upstream_ceiling=evidence_pair[0].attributes.confidence.effective_confidence,
        )
        store.write_fact(reduced, predecessor_id=first.object_id)

        violations = store.facts.integrity().verify()
        assert any(v.constraint_id == "F-I2" for v in violations)
        assert "add-only" in "".join(v.detail for v in violations)

    def test_fi2_accepts_growth(self, store, allocator, evidence_pair):
        first = write_fact_from(store, allocator, evidence_pair[:1])
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "corroborated")

        successor = allocator.succeed(first.attributes.identity)
        grown = make_fact(
            allocator,
            tuple(e.object_id for e in evidence_pair),
            identity=successor,
            upstream_ceiling=min(
                e.attributes.confidence.effective_confidence for e in evidence_pair
            ),
        )
        store.write_fact(grown, predecessor_id=first.object_id)
        assert not [
            v for v in store.facts.integrity().verify() if v.constraint_id == "F-I2"
        ]

    def test_fi3_detects_unresolvable_anchor(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        fact = store.get_fact(stored.object_id)
        object.__setattr__(fact.attachments[0], "positional_anchor", "")
        violations = store.facts.integrity().verify()
        assert any(v.constraint_id == "F-I3" for v in violations)

    def test_fi4_names_the_shortfall(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        violations = store.facts.integrity().verify()
        assert any(v.constraint_id == "F-I4" for v in violations)
        assert "1 merge(s) but only 0 justification(s)" in "".join(
            v.detail for v in violations
        )

    def test_fi4_satisfied_by_recorded_justification(self, allocator):
        fact = make_fact(allocator).with_attachment(
            attachment("obj-ev-2"),
            MergeJustification(
                Verdict.EQUIVALENT, "agreed", "obj-ev-2", EXTRACTED
            ),
        )
        assert len(fact.merge_history) == fact.attachment_count - 1


# ===========================================================================
# Store integration and compatibility
# ===========================================================================

class TestStoreIntegration:
    def test_fact_reaches_evidence(self, store, allocator, evidence_pair):
        stored = write_fact_from(store, allocator, evidence_pair)
        assert store.graph.reaches_evidence(stored.object_id)
        assert store.graph.evidence_set(stored.object_id) == {
            e.object_id for e in evidence_pair
        }

    def test_confidence_bounded_by_evidence(self, store, allocator):
        """R-3: a Fact cannot exceed its weakest attached Evidence."""
        weak = store.write_evidence(
            make_evidence(
                allocator, content="weak",
                attrs={"support": 0.25, "assertion": 0.99},
            )
        )
        stored = write_fact_from(store, allocator, [weak])
        assert stored.attributes.confidence.effective_confidence <= 0.25

    def test_retracting_all_evidence_invalidates_the_fact(
        self, store, allocator, evidence_pair
    ):
        """IOM 3.2: a Fact invalidates when ALL attesting Evidence is retracted."""
        stored = write_fact_from(store, allocator, evidence_pair)
        cascade = CascadeInvalidation(store=store)
        cascade.retract(evidence_pair[0].object_id, "withdrawn")
        cascade.retract(evidence_pair[1].object_id, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.INVALIDATED

    def test_retracting_some_evidence_leaves_the_fact_attested(
        self, store, allocator, evidence_pair
    ):
        """Partial retraction: the Fact remains attested. [T01.2.4, IOM 3.2]"""
        stored = write_fact_from(store, allocator, evidence_pair)
        result = CascadeInvalidation(store=store).retract(
            evidence_pair[0].object_id, "withdrawn"
        )
        assert store.get(stored.object_id).status is ObjectStatus.ACTIVE
        assert result.partially_retracted == (stored.object_id,)
        assert result.changed == 0

    def test_universal_integrity_still_holds(self, store, allocator, evidence_pair):
        write_fact_from(store, allocator, evidence_pair)
        assert store.verify_integrity().holds

    def test_rejected_write_leaves_no_payload(self, store, allocator):
        before = len(store.facts)
        with pytest.raises(WriteRejectedError):
            store.write_fact(make_fact(allocator, ("obj-never-written",)))
        assert len(store.facts) == before

    def test_fact_cannot_be_created_by_another_engine(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
            engine=Engine.RESEARCH,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(FactError):
            Fact(
                attributes=attributes,
                claim=claim(),
                claim_type=ClaimType.ASSERTION,
                attachments=(attachment("obj-ev-1"),),
                qualifying_context="ctx",
            )

    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(FactError):
            Fact(
                attributes=attributes,
                claim=claim(),
                claim_type=ClaimType.ASSERTION,
                attachments=(attachment("obj-ev-1"),),
                qualifying_context="ctx",
            )


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(count=st.integers(min_value=1, max_value=25))
def test_any_attachment_count_supported(count):
    """AC1 over arbitrary corroboration breadth."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-ev-{i}" for i in range(count))
    fact = make_fact(allocator, refs)
    assert fact.attachment_count == count
    assert fact.independent_source_count <= count


@settings(max_examples=200, deadline=None)
@given(
    attachments=st.integers(min_value=1, max_value=15),
    declared=st.integers(min_value=0, max_value=30),
)
def test_source_count_bound_always_enforced(attachments, declared):
    """AC3 over arbitrary declared counts."""
    allocator = IdentityAllocator()
    refs = tuple(f"obj-ev-{i}" for i in range(attachments))
    if declared <= attachments:
        fact = make_fact(allocator, refs, source_count=declared)
        assert fact.independent_source_count == declared
    else:
        with pytest.raises(SourceCountError):
            make_fact(allocator, refs, source_count=declared)


@settings(max_examples=150, deadline=None)
@given(anchor=st.text(max_size=20))
def test_anchor_required_for_every_attachment(anchor):
    """AC2 over arbitrary anchor text."""
    if anchor.strip():
        assert attachment("obj-ev-1", positional_anchor=anchor)
    else:
        with pytest.raises(AttachmentError):
            attachment("obj-ev-1", positional_anchor=anchor)


@settings(max_examples=150, deadline=None)
@given(merges=st.integers(min_value=1, max_value=10))
def test_attachments_are_monotonic_across_merges(merges):
    """F-I2: attachments are add-only. [R-5]"""
    allocator = IdentityAllocator()
    fact = make_fact(allocator)
    previous = fact
    for i in range(2, merges + 2):
        fact = fact.with_attachment(
            attachment(f"obj-ev-{i}"),
            MergeJustification(
                Verdict.EQUIVALENT, "agreed", f"obj-ev-{i}", EXTRACTED
            ),
        )
        assert fact.retains_attachments_of(previous)
        previous = fact
    assert fact.attachment_count == merges + 1
