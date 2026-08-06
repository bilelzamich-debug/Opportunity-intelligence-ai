"""Contract tests for the Evidence object type.

Task: T01.7.1

Architecture References:
- E-V1..E-V6  Evidence validation rules
- E-I1..E-I4  Evidence integrity constraints
- AD-05       Ground Truth Protection
- Article IV  Evidence originates from external reality
- R-2         Evidence cannot reach INVALIDATED
- R-3         Evidence sets the ceiling
- N-15        Hybrid storage
- N-16        Evidence contributes one independent source

Acceptance criteria under test:
  AC1  derives_from empty enforced (E-V1)
  AC2  E-I2 rejects platform-internal derivation
  AC3  Duplicate fingerprint+source rejected (E-V6)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.contract import LineageRef
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.evidence import (
    EVIDENCE_RULES,
    ContentError,
    Evidence,
    EvidenceContent,
    EvidenceError,
    EvidenceRegistry,
    ExternalOriginError,
    FingerprintError,
    Provenance,
    ProvenanceError,
    StorageMode,
    compute_fingerprint,
    ev1_no_upstream_lineage,
    ev2_provenance_present,
    ev3_content_present,
    ev4_fingerprint_matches,
    ev5_observed_before_acquired,
    ev6_no_duplicate_acquisition,
)
from oip.identity import IdentityAllocator
from oip.lifecycle import reachable_states
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs, build_lineage

ACQUIRED = T0 + timedelta(hours=2)


def provenance(**overrides) -> Provenance:
    kwargs = {
        "source_identifier": "corpus/segment-A",
        "source_type": "customer_review_corpus",
        "acquisition_method": "bulk_corpus_retrieval",
        "acquired_at": ACQUIRED,
        "access_conditions": "licensed; attribution required",
        "capture_fidelity": "full text preserved; media omitted",
    }
    kwargs.update(overrides)
    return Provenance(**kwargs)


def evidence(
    allocator: IdentityAllocator,
    content: str = "Sellers report bulk updates fail silently above 50 items.",
    **overrides
) -> Evidence:
    attrs_overrides = overrides.pop("attrs", {})
    body = overrides.pop("content_obj", None) or EvidenceContent.full(content)
    attributes = build_attrs(
        overrides.pop("identity", None) or allocator.new_object(),
        ObjectType.EVIDENCE,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        **attrs_overrides,
    )
    return Evidence(
        attributes=attributes,
        provenance=provenance(**overrides),
        content=body,
    )


def ctx(ev: Evidence, **overrides) -> AcceptanceContext:
    kwargs = {"attributes": ev.attributes, "evidence": ev}
    kwargs.update(overrides)
    return AcceptanceContext(**kwargs)


# ===========================================================================
# AC1 / AC2 -- E-V1 and E-I2: no upstream lineage, external origin only
# ===========================================================================

class TestGroundingLayer:
    def test_evidence_has_no_upstream(self, allocator):
        assert evidence(allocator).attributes.derives_from == ()

    def test_evidence_is_root(self, allocator):
        assert evidence(allocator).is_root

    def test_lineage_bearing_evidence_cannot_be_constructed(self, allocator):
        """AC1/AC2: refused at construction, so it cannot exist transiently."""
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            (("obj-fr-1", ObjectType.FEEDBACK_RECORD),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes,
                provenance=provenance(),
                content=EvidenceContent.full("text"),
            )

    @pytest.mark.parametrize("source_type", list(ObjectType))
    def test_no_object_type_may_become_evidence(self, allocator, source_type):
        """AD-05: the prohibition covers every platform artifact."""
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            (("obj-x", source_type),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(ExternalOriginError):
            Evidence(
                attributes=attributes,
                provenance=provenance(),
                content=EvidenceContent.full("text"),
            )

    def test_ev1_rule_passes_for_clean_evidence(self, allocator):
        result = ev1_no_upstream_lineage(ctx(evidence(allocator)))
        assert result.outcome is RuleOutcome.PASS
        assert "grounding preserved" in result.detail

    def test_ev1_rule_fails_on_smuggled_lineage(self, allocator):
        ev = evidence(allocator)
        object.__setattr__(
            ev.attributes, "derives_from",
            (LineageRef("obj-fr-1", ObjectType.FEEDBACK_RECORD),),
        )
        result = ev1_no_upstream_lineage(ctx(ev))
        assert result.failed
        assert "Article IV" in result.detail

    def test_ev1_skips_non_evidence(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = ev1_no_upstream_lineage(AcceptanceContext(attributes=attributes))
        assert result.outcome is RuleOutcome.SKIP

    def test_only_research_may_create_evidence(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            engine=Engine.FEEDBACK,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(EvidenceError):
            Evidence(
                attributes=attributes,
                provenance=provenance(),
                content=EvidenceContent.full("text"),
            )

    def test_wrong_object_type_rejected(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev", ObjectType.EVIDENCE),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        with pytest.raises(EvidenceError):
            Evidence(
                attributes=attributes,
                provenance=provenance(),
                content=EvidenceContent.full("text"),
            )


# ===========================================================================
# E-V2 / E-I3 -- provenance
# ===========================================================================

class TestProvenance:
    def test_complete_provenance_accepted(self, allocator):
        assert not ev2_provenance_present(ctx(evidence(allocator))).failed

    @pytest.mark.parametrize(
        "field_name",
        ["source_identifier", "source_type", "acquisition_method",
         "access_conditions", "capture_fidelity"],
    )
    def test_every_provenance_field_is_required(self, field_name):
        with pytest.raises(ProvenanceError):
            provenance(**{field_name: ""})

    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_whitespace_is_not_provenance(self, blank):
        with pytest.raises(ProvenanceError):
            provenance(source_identifier=blank)

    def test_acquired_at_must_be_a_datetime(self):
        with pytest.raises(ProvenanceError):
            provenance(acquired_at="2026-03-01")

    def test_ev2_detects_stripped_provenance(self, allocator):
        ev = evidence(allocator)
        object.__setattr__(ev.provenance, "source_identifier", "")
        result = ev2_provenance_present(ctx(ev))
        assert result.failed
        assert "source_identifier" in result.detail

    def test_optional_provenance_defaults_to_none(self, allocator):
        prov = evidence(allocator).provenance
        assert prov.source_reliability is None
        assert prov.publication_date is None
        assert prov.author_identifier is None
        assert prov.source_independence_group is None

    def test_optional_provenance_accepted(self, allocator):
        ev = evidence(
            allocator,
            source_reliability=0.8,
            publication_date=T0,
            author_identifier="author-7",
            source_independence_group="group-A",
        )
        assert ev.provenance.source_reliability == 0.8
        assert ev.provenance.author_identifier == "author-7"

    @pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0])
    def test_source_reliability_range_enforced(self, bad):
        with pytest.raises(ProvenanceError):
            provenance(source_reliability=bad)

    def test_independence_key_defaults_to_source(self, allocator):
        ev = evidence(allocator)
        assert ev.independence_key == ev.source_identifier

    def test_independence_group_overrides_source(self, allocator):
        """Syndicated sources count once. [N-16, M-23]"""
        ev = evidence(allocator, source_independence_group="syndicate-1")
        assert ev.independence_key == "syndicate-1"

    def test_provenance_is_frozen(self, allocator):
        with pytest.raises(Exception):
            evidence(allocator).provenance.source_identifier = "other"


# ===========================================================================
# E-V3 / E-V4 -- content and fingerprint
# ===========================================================================

class TestContentAndFingerprint:
    def test_full_storage_accepted(self, allocator):
        ev = evidence(allocator)
        assert ev.content.storage_mode is StorageMode.FULL
        assert not ev3_content_present(ctx(ev)).failed
        assert not ev4_fingerprint_matches(ctx(ev)).failed

    def test_reference_storage_accepted(self, allocator):
        body = EvidenceContent.by_reference("s3://corpus/a", "sha256:abc")
        ev = evidence(allocator, content_obj=body)
        assert ev.content.storage_mode is StorageMode.REFERENCE
        assert not ev3_content_present(ctx(ev)).failed

    def test_full_storage_requires_content(self):
        with pytest.raises(ContentError):
            EvidenceContent(
                fingerprint="sha256:abc",
                storage_mode=StorageMode.FULL,
                content=None,
            )

    def test_reference_storage_requires_a_reference(self):
        with pytest.raises(ContentError):
            EvidenceContent(
                fingerprint="sha256:abc",
                storage_mode=StorageMode.REFERENCE,
                content_reference="",
            )

    def test_fingerprint_required(self):
        with pytest.raises(FingerprintError):
            EvidenceContent(
                fingerprint="", storage_mode=StorageMode.REFERENCE,
                content_reference="ref",
            )

    def test_mismatched_fingerprint_rejected(self):
        with pytest.raises(FingerprintError):
            EvidenceContent(
                fingerprint="sha256:wrong",
                storage_mode=StorageMode.FULL,
                content="actual text",
            )

    def test_fingerprint_is_deterministic(self):
        assert compute_fingerprint("abc") == compute_fingerprint("abc")

    def test_fingerprint_distinguishes_content(self):
        assert compute_fingerprint("abc") != compute_fingerprint("abd")

    def test_fingerprint_accepts_bytes(self):
        assert compute_fingerprint(b"abc") == compute_fingerprint("abc")

    def test_ev4_detects_post_hoc_content_change(self, allocator):
        """E-I1 at the rule layer: altered content breaks the fingerprint."""
        ev = evidence(allocator)
        object.__setattr__(ev.content, "content", "tampered text")
        result = ev4_fingerprint_matches(ctx(ev))
        assert result.failed
        assert "does not match" in result.detail

    def test_ev4_cannot_reverify_reference_material(self, allocator):
        """N-15: reference-only material cannot be re-fingerprinted here."""
        body = EvidenceContent.by_reference("s3://corpus/a", "sha256:abc")
        result = ev4_fingerprint_matches(ctx(evidence(allocator, content_obj=body)))
        assert result.outcome is RuleOutcome.PASS
        assert "N-15" in result.detail

    def test_verifiability_flag_reflects_storage_mode(self, allocator):
        assert evidence(allocator).content.is_verifiable_in_place
        body = EvidenceContent.by_reference("s3://a", "sha256:abc")
        assert not evidence(allocator, content_obj=body).content.is_verifiable_in_place

    def test_drift_detection(self, allocator):
        ev = evidence(allocator, content="original")
        assert not ev.drifted_from(compute_fingerprint("original"))
        assert ev.drifted_from(compute_fingerprint("changed"))


# ===========================================================================
# E-V5 -- observed_at <= acquired_at
# ===========================================================================

class TestObservationOrdering:
    def test_observation_before_acquisition_accepted(self, allocator):
        assert not ev5_observed_before_acquired(ctx(evidence(allocator))).failed

    def test_equal_timestamps_accepted(self, allocator):
        ev = evidence(
            allocator,
            attrs={"observed_at": ACQUIRED, "asserted_at": ACQUIRED,
                   "produced_at": ACQUIRED},
        )
        assert not ev5_observed_before_acquired(ctx(ev)).failed

    def test_observation_after_acquisition_rejected(self, allocator):
        with pytest.raises(ProvenanceError):
            evidence(allocator, acquired_at=T0 - timedelta(hours=1))

    def test_ev5_rule_detects_smuggled_disorder(self, allocator):
        ev = evidence(allocator)
        object.__setattr__(
            ev.attributes, "observed_at", ACQUIRED + timedelta(days=1)
        )
        result = ev5_observed_before_acquired(ctx(ev))
        assert result.failed
        assert "cannot be observed after" in result.detail

    def test_naive_aware_mix_fails_cleanly(self, allocator):
        ev = evidence(allocator)
        object.__setattr__(ev.attributes, "observed_at", datetime(2026, 3, 1))
        result = ev5_observed_before_acquired(ctx(ev))
        assert result.failed
        assert "naive" in result.detail

    def test_long_prior_observation_accepted(self, allocator):
        """Evidence about the distant past is legitimate. [R-4]"""
        ev = evidence(
            allocator,
            attrs={"observed_at": T0 - timedelta(days=3650)},
        )
        assert not ev5_observed_before_acquired(ctx(ev)).failed


# ===========================================================================
# AC3 / E-V6 -- duplicate acquisition
# ===========================================================================

class TestDuplicateDetection:
    def test_duplicate_key_is_fingerprint_and_source(self, allocator):
        ev = evidence(allocator)
        assert ev.duplicate_key == (ev.fingerprint, ev.source_identifier)

    def test_duplicate_rejected_at_write(self, store, allocator):
        """AC3: the defining requirement."""
        store.write_evidence(evidence(allocator, content="same text"))
        with pytest.raises(WriteRejectedError) as exc:
            store.write_evidence(evidence(allocator, content="same text"))
        assert "E-V6" in exc.value.failure.rule_ids

    def test_same_content_different_source_accepted(self, store, allocator):
        """Independent corroboration, not duplication."""
        store.write_evidence(
            evidence(allocator, content="text", source_identifier="src-A")
        )
        stored = store.write_evidence(
            evidence(allocator, content="text", source_identifier="src-B")
        )
        assert stored.status is ObjectStatus.ACTIVE

    def test_different_content_same_source_accepted(self, store, allocator):
        store.write_evidence(evidence(allocator, content="first"))
        stored = store.write_evidence(evidence(allocator, content="second"))
        assert stored.status is ObjectStatus.ACTIVE

    def test_retracted_material_may_be_reacquired(self, store, allocator):
        """Only ACTIVE Evidence blocks re-acquisition."""
        first = store.write_evidence(evidence(allocator, content="text"))
        store.transition(first.object_id, ObjectStatus.RETRACTED, "withdrawn")
        again = store.write_evidence(evidence(allocator, content="text"))
        assert again.status is ObjectStatus.ACTIVE

    def test_rejected_material_may_be_reacquired(self, store, allocator):
        first = store.write_evidence(evidence(allocator, content="text"))
        store.transition(first.object_id, ObjectStatus.REJECTED, "declined")
        again = store.write_evidence(evidence(allocator, content="text"))
        assert again.status is ObjectStatus.ACTIVE

    def test_rejected_duplicate_leaves_no_trace(self, store, allocator):
        """Atomicity: a refused acquisition must not enter the index."""
        store.write_evidence(evidence(allocator, content="text"))
        before = len(store.evidence)
        with pytest.raises(WriteRejectedError):
            store.write_evidence(evidence(allocator, content="text"))
        assert len(store.evidence) == before
        assert len(store) == 1

    def test_ev6_skips_without_a_provider(self, allocator):
        result = ev6_no_duplicate_acquisition(
            ctx(evidence(allocator), find_duplicate_evidence=None)
        )
        assert result.outcome is RuleOutcome.SKIP

    def test_ev6_ignores_the_object_itself(self, allocator):
        ev = evidence(allocator)
        result = ev6_no_duplicate_acquisition(
            ctx(ev, find_duplicate_evidence=lambda key: ev.object_id)
        )
        assert not result.failed


# ===========================================================================
# Lifecycle  [R-2]
# ===========================================================================

class TestEvidenceLifecycle:
    def test_evidence_cannot_be_invalidated(self):
        """Nothing upstream exists to invalidate it. [R-2, E-V1]"""
        assert ObjectStatus.INVALIDATED not in reachable_states(ObjectType.EVIDENCE)

    def test_evidence_may_be_retracted(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.get(stored.object_id).status is ObjectStatus.RETRACTED

    def test_evidence_may_be_superseded(self, store, allocator):
        """Re-acquisition with better fidelity. [IOM section 3.1]"""
        first = store.write_evidence(evidence(allocator, content="low fidelity"))
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "refidelity")
        successor = allocator.succeed(first.attributes.identity)
        better = evidence(allocator, content="high fidelity", identity=successor)
        stored = store.write_evidence(better, predecessor_id=first.object_id)
        assert stored.attributes.version == 2
        assert store.contains(first.object_id)

    def test_evidence_may_be_archived(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        store.transition(stored.object_id, ObjectStatus.ARCHIVED, "retention")
        assert store.get(stored.object_id).status is ObjectStatus.ARCHIVED


# ===========================================================================
# E-I1..E-I4 -- integrity constraints
# ===========================================================================

class TestEvidenceIntegrity:
    def test_clean_store_holds(self, store, allocator):
        for _ in range(3):
            store.write_evidence(evidence(allocator, content=f"text-{_}"))
        assert store.evidence.integrity().verify() == ()

    def test_ei1_detects_content_alteration(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        payload = store.get_evidence(stored.object_id)
        object.__setattr__(payload.content, "content", "tampered")

        violations = store.evidence.integrity().verify()
        assert any(v.constraint_id == "E-I1" for v in violations)
        assert "altered after acceptance" in violations[0].detail

    def test_ei2_detects_platform_internal_derivation(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        object.__setattr__(
            stored.attributes, "derives_from",
            (LineageRef("obj-fr-1", ObjectType.FEEDBACK_RECORD),),
        )
        violations = store.evidence.integrity().verify()
        assert any(v.constraint_id == "E-I2" for v in violations)
        assert "grounding is compromised" in "".join(v.detail for v in violations)

    def test_ei3_detects_removed_provenance(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        payload = store.get_evidence(stored.object_id)
        object.__setattr__(payload.provenance, "capture_fidelity", "")

        violations = store.evidence.integrity().verify()
        assert any(v.constraint_id == "E-I3" for v in violations)

    def test_ei4_holds_after_cascade(self, store, allocator):
        from tests.conftest import write_derived
        stored = store.write_evidence(evidence(allocator))
        write_derived(store, allocator, ObjectType.FACT, [stored])
        CascadeInvalidation(store=store).retract(stored.object_id, "withdrawn")
        assert store.evidence.integrity().verify() == ()

    def test_ei4_detects_uncascaded_retraction(self, store, allocator):
        from tests.conftest import write_derived
        stored = store.write_evidence(evidence(allocator))
        write_derived(store, allocator, ObjectType.FACT, [stored])
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")

        violations = store.evidence.integrity().verify()
        assert any(v.constraint_id == "E-I4" for v in violations)
        assert "cascade did not complete" in violations[0].detail


# ===========================================================================
# Registry and store integration
# ===========================================================================

class TestRegistryAndStore:
    def test_payload_retrievable_after_write(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        payload = store.get_evidence(stored.object_id)
        assert payload is not None
        assert payload.object_id == stored.object_id

    def test_unknown_payload_is_none(self, store):
        assert store.get_evidence("obj-absent") is None

    def test_registry_counts_payloads(self, store, allocator):
        for i in range(4):
            store.write_evidence(evidence(allocator, content=f"text-{i}"))
        assert len(store.evidence) == 4

    def test_independent_sources_deduplicated(self, store, allocator):
        """N-16: syndicated sources count once."""
        for i in range(3):
            store.write_evidence(
                evidence(
                    allocator, content=f"text-{i}",
                    source_identifier=f"src-{i}",
                    source_independence_group="syndicate-1",
                )
            )
        store.write_evidence(
            evidence(allocator, content="independent", source_identifier="src-X")
        )
        assert len(store.evidence.independent_sources()) == 2

    def test_retracted_source_not_counted(self, store, allocator):
        stored = store.write_evidence(evidence(allocator))
        assert len(store.evidence.independent_sources()) == 1
        store.transition(stored.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert store.evidence.independent_sources() == frozenset()

    def test_universal_integrity_still_holds(self, store, allocator):
        for i in range(3):
            store.write_evidence(evidence(allocator, content=f"text-{i}"))
        assert store.verify_integrity().holds

    def test_evidence_participates_in_lineage_as_root(self, store, allocator):
        from tests.conftest import write_derived
        stored = store.write_evidence(evidence(allocator))
        fact = write_derived(store, allocator, ObjectType.FACT, [stored])
        assert store.graph.evidence_set(fact.object_id) == {stored.object_id}
        assert store.graph.reaches_evidence(fact.object_id)

    def test_evidence_sets_the_confidence_ceiling(self, store, allocator):
        """R-3: Evidence is unconstrained from above and bounds everything."""
        from tests.conftest import write_derived
        stored = store.write_evidence(
            evidence(allocator, attrs={"support": 0.42, "assertion": 0.99})
        )
        fact = write_derived(store, allocator, ObjectType.FACT, [stored])
        assert fact.attributes.confidence.effective_confidence <= 0.42

    def test_all_six_evidence_rules_registered(self, store):
        assert {f"E-V{i}" for i in range(1, 7)} <= set(store.acceptance.rule_ids)

    def test_evidence_rules_skip_non_evidence(self, store, allocator):
        """One acceptance path serves all nine types."""
        from tests.conftest import write_derived
        stored = store.write_evidence(evidence(allocator))
        fact = write_derived(store, allocator, ObjectType.FACT, [stored])
        assert fact.status is ObjectStatus.ACTIVE


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=200, deadline=None)
@given(content=st.text(min_size=1, max_size=200))
def test_fingerprint_round_trips_for_any_content(content):
    body = EvidenceContent.full(content)
    assert body.fingerprint == compute_fingerprint(content)
    assert body.is_verifiable_in_place


@settings(max_examples=200, deadline=None)
@given(a=st.text(min_size=1, max_size=60), b=st.text(min_size=1, max_size=60))
def test_distinct_content_fingerprints_distinctly(a, b):
    if a == b:
        return
    assert compute_fingerprint(a) != compute_fingerprint(b)


@settings(max_examples=60, deadline=None)
@given(count=st.integers(min_value=1, max_value=12))
def test_distinct_acquisitions_all_accepted(count):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    for i in range(count):
        store.write_evidence(evidence(allocator, content=f"unique-text-{i}"))
    assert len(store) == count
    assert store.verify_integrity().holds
    assert store.evidence.integrity().verify() == ()


@settings(max_examples=60, deadline=None)
@given(repeats=st.integers(min_value=1, max_value=6))
def test_repeated_acquisition_always_rejected(repeats):
    """AC3 over arbitrary repetition."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    store.write_evidence(evidence(allocator, content="same"))
    for _ in range(repeats):
        with pytest.raises(WriteRejectedError) as exc:
            store.write_evidence(evidence(allocator, content="same"))
        assert "E-V6" in exc.value.failure.rule_ids
    assert len(store) == 1


@settings(max_examples=60, deadline=None)
@given(object_type=st.sampled_from(list(ObjectType)))
def test_evidence_never_accepts_any_upstream_type(object_type):
    """AC1/AC2 exhaustively: no type may become Evidence's parent. [AD-05]"""
    allocator = IdentityAllocator()
    attributes = build_attrs(
        allocator.new_object(), ObjectType.EVIDENCE,
        (("obj-upstream", object_type),),
        status=ObjectStatus.ACTIVE, status_reason=None,
    )
    with pytest.raises(ExternalOriginError):
        Evidence(
            attributes=attributes,
            provenance=provenance(),
            content=EvidenceContent.full("text"),
        )


@settings(max_examples=60, deadline=None)
@given(sources=st.integers(min_value=1, max_value=10))
def test_independent_source_count_matches_distinct_sources(sources):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    for i in range(sources):
        store.write_evidence(
            evidence(allocator, content=f"text-{i}", source_identifier=f"src-{i}")
        )
    assert len(store.evidence.independent_sources()) == sources
