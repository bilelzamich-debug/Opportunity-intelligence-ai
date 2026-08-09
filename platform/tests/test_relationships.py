"""Contract tests for the closed relationship taxonomy.

Task: T01.3.1

Architecture References:
- R-6    Closed ten-type taxonomy; engines may not invent types
- V12    All relationships drawn from the closed taxonomy
- AD-05  No platform artifact may become Evidence
- FR-I2  Feedback Record never becomes Evidence
- N-4    Assert properties, never equality on generated values

Acceptance criteria under test:
  AC1  Exactly ten types accepted
  AC2  Undefined relationship types rejected
  AC3  Every relationship records asserting engine and timestamp
  AC4  DERIVES_FROM and SUPPORTS are distinct
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.enums import Engine, ObjectType, RelationshipType
from oip.relationships import (
    LINEAGE_RELATIONSHIPS,
    SUPPORT_RELATIONSHIPS,
    SYMMETRIC_RELATIONSHIPS,
    AttributionError,
    EngineInforms,
    IllegalRelationshipError,
    Relationship,
    RelationshipError,
    SelfReferenceError,
    UnknownRelationshipTypeError,
    assert_no_evidence_derivation,
    is_legal,
    legal_targets,
    lineage_edges,
)

NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)


def rel(
    rtype: RelationshipType,
    from_type: ObjectType,
    to_type: ObjectType,
    **overrides,
) -> Relationship:
    kwargs = {
        "relationship_type": rtype,
        "from_object_id": "obj-from",
        "from_type": from_type,
        "to_object_id": "obj-to",
        "to_type": to_type,
        "asserted_by_engine": Engine.FACT_EXTRACTION,
        "asserted_at": NOW,
    }
    kwargs.update(overrides)
    return Relationship(**kwargs)


# ---------------------------------------------------------------------------
# AC1 -- exactly ten types
# ---------------------------------------------------------------------------

class TestClosedTaxonomy:
    def test_exactly_ten_relationship_types(self):
        assert len(RelationshipType) == 10

    def test_all_ten_are_named_in_r6(self):
        expected = {
            "DERIVES_FROM", "SUPPORTS", "CONSTITUENT_OF", "ADDRESSES", "TESTS",
            "OUTCOME_OF", "SUPERSEDES", "DUPLICATES", "CONTRADICTS", "INFORMS",
        }
        assert {r.value for r in RelationshipType} == expected

    def test_every_type_has_a_legality_rule(self):
        for rtype in RelationshipType:
            legal_targets(rtype, ObjectType.FACT)  # must not raise


# ---------------------------------------------------------------------------
# AC2 -- undefined types rejected
# ---------------------------------------------------------------------------

class TestUndefinedTypesRejected:
    @pytest.mark.parametrize(
        "bogus", ["RELATES_TO", "CAUSES", "SIMILAR_TO", "", None, 42]
    )
    def test_non_taxonomy_type_rejected(self, bogus):
        with pytest.raises(UnknownRelationshipTypeError):
            Relationship(
                relationship_type=bogus,
                from_object_id="obj-a",
                from_type=ObjectType.FACT,
                to_object_id="obj-b",
                to_type=ObjectType.EVIDENCE,
                asserted_by_engine=Engine.FACT_EXTRACTION,
                asserted_at=NOW,
            )

    def test_known_type_illegal_pairing_rejected(self):
        """Type is in the taxonomy but not legal between these object types."""
        with pytest.raises(IllegalRelationshipError):
            rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.PATTERN)

    def test_pipeline_order_cannot_be_inverted(self):
        with pytest.raises(IllegalRelationshipError):
            rel(RelationshipType.DERIVES_FROM, ObjectType.EVIDENCE, ObjectType.FACT)


# ---------------------------------------------------------------------------
# AC3 -- attribution required
# ---------------------------------------------------------------------------

class TestAttribution:
    def test_asserting_engine_recorded(self):
        r = rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE)
        assert r.asserted_by_engine is Engine.FACT_EXTRACTION

    def test_timestamp_recorded(self):
        r = rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE)
        assert r.asserted_at == NOW

    @pytest.mark.parametrize("bad", [None, "FactExtraction", 1])
    def test_missing_engine_rejected(self, bad):
        with pytest.raises(AttributionError):
            rel(
                RelationshipType.DERIVES_FROM,
                ObjectType.FACT,
                ObjectType.EVIDENCE,
                asserted_by_engine=bad,
            )

    @pytest.mark.parametrize("bad", [None, "2026-03-01", 0])
    def test_missing_timestamp_rejected(self, bad):
        with pytest.raises(AttributionError):
            rel(
                RelationshipType.DERIVES_FROM,
                ObjectType.FACT,
                ObjectType.EVIDENCE,
                asserted_at=bad,
            )


# ---------------------------------------------------------------------------
# AC4 -- DERIVES_FROM and SUPPORTS are distinct
# ---------------------------------------------------------------------------

class TestDerivesFromVsSupports:
    def test_they_are_different_types(self):
        assert RelationshipType.DERIVES_FROM is not RelationshipType.SUPPORTS

    def test_they_have_different_legal_pairings(self):
        derives = legal_targets(RelationshipType.DERIVES_FROM, ObjectType.PROBLEM)
        supports = legal_targets(RelationshipType.SUPPORTS, ObjectType.PROBLEM)
        assert derives != supports

    def test_only_derives_from_is_lineage(self):
        assert RelationshipType.DERIVES_FROM in LINEAGE_RELATIONSHIPS
        assert RelationshipType.SUPPORTS not in LINEAGE_RELATIONSHIPS

    def test_supports_counts_toward_evidential_backing(self):
        assert RelationshipType.SUPPORTS in SUPPORT_RELATIONSHIPS
        assert RelationshipType.CONSTITUENT_OF in SUPPORT_RELATIONSHIPS

    def test_fact_derives_from_evidence_but_supports_problem(self):
        """The direction differs: derivation looks back, support looks forward."""
        derivation = rel(
            RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE
        )
        support = rel(RelationshipType.SUPPORTS, ObjectType.FACT, ObjectType.PROBLEM)
        assert derivation.is_lineage
        assert not support.is_lineage


# ---------------------------------------------------------------------------
# Pipeline legality
# ---------------------------------------------------------------------------

class TestPipelineLineage:
    @pytest.mark.parametrize(
        "child,parent",
        [
            (ObjectType.FACT, ObjectType.EVIDENCE),
            (ObjectType.PROBLEM, ObjectType.FACT),
            (ObjectType.PATTERN, ObjectType.PROBLEM),
            (ObjectType.OPPORTUNITY, ObjectType.PATTERN),
            (ObjectType.SOLUTION, ObjectType.OPPORTUNITY),
            (ObjectType.VALIDATION, ObjectType.SOLUTION),
            (ObjectType.EXECUTION_RECORD, ObjectType.SOLUTION),
            (ObjectType.FEEDBACK_RECORD, ObjectType.EXECUTION_RECORD),
        ],
    )
    def test_each_pipeline_step_is_legal(self, child, parent):
        assert is_legal(RelationshipType.DERIVES_FROM, child, parent)

    def test_evidence_never_derives_from_anything(self):
        """Evidence is the only root. [E-V1, AD-05]"""
        for target in ObjectType:
            assert not is_legal(
                RelationshipType.DERIVES_FROM, ObjectType.EVIDENCE, target
            )

    def test_feedback_derives_only_from_execution_records(self):
        """FR-V6: the Feedback Record's sole permitted upstream."""
        targets = legal_targets(
            RelationshipType.DERIVES_FROM, ObjectType.FEEDBACK_RECORD
        )
        assert targets == {ObjectType.EXECUTION_RECORD}


# ---------------------------------------------------------------------------
# AD-05 / Article IV -- Ground Truth Protection
# ---------------------------------------------------------------------------

class TestGroundTruthProtection:
    def test_evidence_derivation_is_structurally_impossible(self):
        for source in ObjectType:
            with pytest.raises(IllegalRelationshipError):
                rel(RelationshipType.DERIVES_FROM, ObjectType.EVIDENCE, source)

    def test_feedback_cannot_derive_into_evidence(self):
        """FR-I2: a Feedback Record may never become Evidence."""
        with pytest.raises(IllegalRelationshipError):
            rel(
                RelationshipType.DERIVES_FROM,
                ObjectType.EVIDENCE,
                ObjectType.FEEDBACK_RECORD,
            )

    def test_informs_is_never_lineage(self):
        informs = EngineInforms(
            from_object_id="obj-fr-1",
            informs_engine=Engine.OPPORTUNITY_INTELLIGENCE,
            asserted_by_engine=Engine.FEEDBACK,
            asserted_at=NOW,
        )
        assert not informs.is_lineage
        assert informs.relationship_type is RelationshipType.INFORMS

    def test_informs_has_no_legal_object_target(self):
        """INFORMS targets engine behaviour, never an object."""
        for source in ObjectType:
            for target in ObjectType:
                assert not is_legal(RelationshipType.INFORMS, source, target)

    def test_only_feedback_records_may_inform(self):
        with pytest.raises(IllegalRelationshipError):
            EngineInforms(
                from_object_id="obj-op-1",
                informs_engine=Engine.RESEARCH,
                asserted_by_engine=Engine.FEEDBACK,
                asserted_at=NOW,
                from_type=ObjectType.OPPORTUNITY,
            )

    def test_guard_rejects_evidence_with_lineage(self):
        """assert_no_evidence_derivation is the AD-05 enforcement point."""
        legit = rel(RelationshipType.DERIVES_FROM, ObjectType.FACT,
                    ObjectType.EVIDENCE)
        assert_no_evidence_derivation([legit])  # must not raise

    def test_guard_passes_on_clean_lineage(self):
        edges = [
            rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE),
            rel(RelationshipType.DERIVES_FROM, ObjectType.PROBLEM, ObjectType.FACT),
        ]
        assert_no_evidence_derivation(edges)


# ---------------------------------------------------------------------------
# Symmetry, self-reference, filtering
# ---------------------------------------------------------------------------

class TestSymmetryAndStructure:
    @pytest.mark.parametrize(
        "rtype", [RelationshipType.DUPLICATES, RelationshipType.CONTRADICTS]
    )
    def test_symmetric_types_have_an_inverse(self, rtype):
        r = rel(rtype, ObjectType.FACT, ObjectType.FACT)
        inverse = r.inverse()
        assert inverse.from_object_id == r.to_object_id
        assert inverse.to_object_id == r.from_object_id
        assert inverse.relationship_type is rtype

    def test_asymmetric_types_have_no_inverse(self):
        r = rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE)
        with pytest.raises(RelationshipError):
            r.inverse()

    def test_symmetric_set_is_exactly_two(self):
        assert SYMMETRIC_RELATIONSHIPS == {
            RelationshipType.DUPLICATES,
            RelationshipType.CONTRADICTS,
        }

    def test_peer_types_require_matching_object_types(self):
        with pytest.raises(IllegalRelationshipError):
            rel(RelationshipType.DUPLICATES, ObjectType.FACT, ObjectType.PROBLEM)

    def test_self_reference_rejected(self):
        with pytest.raises(SelfReferenceError):
            rel(
                RelationshipType.DUPLICATES,
                ObjectType.FACT,
                ObjectType.FACT,
                from_object_id="obj-same",
                to_object_id="obj-same",
            )

    def test_empty_endpoint_rejected(self):
        for field in ("from_object_id", "to_object_id"):
            with pytest.raises(RelationshipError):
                rel(
                    RelationshipType.DERIVES_FROM,
                    ObjectType.FACT,
                    ObjectType.EVIDENCE,
                    **{field: ""},
                )

    def test_supersedes_requires_same_type(self):
        for t in ObjectType:
            assert is_legal(RelationshipType.SUPERSEDES, t, t)
        assert not is_legal(
            RelationshipType.SUPERSEDES, ObjectType.FACT, ObjectType.PROBLEM
        )

    def test_lineage_edges_filters_correctly(self):
        edges = [
            rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE),
            rel(RelationshipType.SUPPORTS, ObjectType.FACT, ObjectType.PROBLEM),
            rel(RelationshipType.DUPLICATES, ObjectType.FACT, ObjectType.FACT),
        ]
        filtered = lineage_edges(edges)
        assert len(filtered) == 1
        assert filtered[0].relationship_type is RelationshipType.DERIVES_FROM


class TestImmutability:
    def test_relationship_cannot_be_mutated(self):
        r = rel(RelationshipType.DERIVES_FROM, ObjectType.FACT, ObjectType.EVIDENCE)
        with pytest.raises(Exception):
            r.to_object_id = "obj-repointed"  # I3

    def test_informs_cannot_be_mutated(self):
        i = EngineInforms(
            from_object_id="obj-fr",
            informs_engine=Engine.RESEARCH,
            asserted_by_engine=Engine.FEEDBACK,
            asserted_at=NOW,
        )
        with pytest.raises(Exception):
            i.informs_engine = Engine.VALIDATION


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=400, deadline=None)
@given(
    rtype=st.sampled_from(list(RelationshipType)),
    from_type=st.sampled_from(list(ObjectType)),
    to_type=st.sampled_from(list(ObjectType)),
)
def test_construction_succeeds_exactly_when_legal(rtype, from_type, to_type):
    """The legality matrix and the constructor never disagree. [R-6, V12]"""
    legal = is_legal(rtype, from_type, to_type)
    try:
        rel(rtype, from_type, to_type)
        constructed = True
    except IllegalRelationshipError:
        constructed = False
    assert constructed is legal


@settings(max_examples=300, deadline=None)
@given(target=st.sampled_from(list(ObjectType)))
def test_no_relationship_makes_evidence_derive(target):
    """Article IV holds for every relationship type and target. [AD-05]"""
    for rtype in RelationshipType:
        if rtype not in LINEAGE_RELATIONSHIPS:
            continue
        assert not is_legal(rtype, ObjectType.EVIDENCE, target)


@settings(max_examples=300, deadline=None)
@given(
    rtype=st.sampled_from(list(SYMMETRIC_RELATIONSHIPS)),
    obj_type=st.sampled_from(list(ObjectType)),
    a=st.text(min_size=1, max_size=20),
    b=st.text(min_size=1, max_size=20),
)
def test_inverse_is_involutive(rtype, obj_type, a, b):
    """inverse(inverse(r)) == r for every symmetric relationship."""
    if a == b:
        return
    r = rel(rtype, obj_type, obj_type, from_object_id=a, to_object_id=b)
    assert r.inverse().inverse() == r


@settings(max_examples=200, deadline=None)
@given(engine=st.sampled_from(list(Engine)))
def test_any_engine_may_be_recorded_as_asserter(engine):
    """Attribution accepts any of the nine engines. [R-6]"""
    r = rel(
        RelationshipType.DERIVES_FROM,
        ObjectType.FACT,
        ObjectType.EVIDENCE,
        asserted_by_engine=engine,
    )
    assert r.asserted_by_engine is engine


# ---------------------------------------------------------------------------
# EngineInforms validation + AD-05 guard raise path
# ---------------------------------------------------------------------------

class TestEngineInformsValidation:
    def _informs(self, **overrides):
        kwargs = {
            "from_object_id": "obj-fr-1",
            "informs_engine": Engine.OPPORTUNITY_INTELLIGENCE,
            "asserted_by_engine": Engine.FEEDBACK,
            "asserted_at": NOW,
        }
        kwargs.update(overrides)
        return EngineInforms(**kwargs)

    def test_valid_informs_accepted(self):
        assert self._informs().informs_engine is Engine.OPPORTUNITY_INTELLIGENCE

    def test_empty_source_rejected(self):
        with pytest.raises(RelationshipError):
            self._informs(from_object_id="")

    @pytest.mark.parametrize("bad", [None, "Research", 3])
    def test_invalid_target_engine_rejected(self, bad):
        with pytest.raises(IllegalRelationshipError):
            self._informs(informs_engine=bad)

    @pytest.mark.parametrize("bad", [None, "Feedback", 7])
    def test_invalid_asserting_engine_rejected(self, bad):
        with pytest.raises(AttributionError):
            self._informs(asserted_by_engine=bad)

    @pytest.mark.parametrize("bad", [None, "2026-03-01", 0])
    def test_invalid_timestamp_rejected(self, bad):
        with pytest.raises(AttributionError):
            self._informs(asserted_at=bad)


class TestEvidenceDerivationGuardRaises:
    def test_guard_raises_on_evidence_lineage_edge(self):
        """The AD-05 enforcement path must actually fire.

        Relationship construction blocks this, so the guard is a defence in
        depth for edges arriving from storage or an untrusted path.
        """
        smuggled = Relationship.__new__(Relationship)
        object.__setattr__(smuggled, "relationship_type",
                           RelationshipType.DERIVES_FROM)
        object.__setattr__(smuggled, "from_object_id", "obj-ev-1")
        object.__setattr__(smuggled, "from_type", ObjectType.EVIDENCE)
        object.__setattr__(smuggled, "to_object_id", "obj-fr-1")
        object.__setattr__(smuggled, "to_type", ObjectType.FEEDBACK_RECORD)
        object.__setattr__(smuggled, "asserted_by_engine", Engine.FEEDBACK)
        object.__setattr__(smuggled, "asserted_at", NOW)

        with pytest.raises(IllegalRelationshipError, match="Article IV"):
            assert_no_evidence_derivation([smuggled])
