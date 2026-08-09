"""Contract tests for objects-authoritative lineage.

Task: T01.3.2

Architecture References:
- N-6    Objects authoritative; graph derived
- R-1a   Version-specific binding
- I3     References never repoint
- V2/V3/V4  Lineage non-empty, resolvable, Evidence-reachable
- AD-05  Evidence never derives from anything

Acceptance criteria under test:
  AC1  derives_from binds to specific versions
  AC2  References never repoint (I3)
  AC3  Object is self-describing without the graph
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.contract import LineageRef
from oip.enums import Engine, ObjectType, RelationshipType
from oip.lineage import (
    DictResolver,
    DuplicateReferenceError,
    EmptyLineageError,
    Lineage,
    LineageError,
    RepointError,
    RootLineageError,
    TypeMismatchError,
    UnresolvedReferenceError,
    assert_no_repoint,
    derive,
    evidence_reachable,
    root_lineage,
)

NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)

# Pipeline adjacency used throughout.
PARENT_OF = {
    ObjectType.FACT: ObjectType.EVIDENCE,
    ObjectType.PROBLEM: ObjectType.FACT,
    ObjectType.PATTERN: ObjectType.PROBLEM,
    ObjectType.OPPORTUNITY: ObjectType.PATTERN,
    ObjectType.SOLUTION: ObjectType.OPPORTUNITY,
    ObjectType.VALIDATION: ObjectType.SOLUTION,
    ObjectType.EXECUTION_RECORD: ObjectType.SOLUTION,
    ObjectType.FEEDBACK_RECORD: ObjectType.EXECUTION_RECORD,
}


# ---------------------------------------------------------------------------
# AC1 -- version-specific binding
# ---------------------------------------------------------------------------

class TestVersionSpecificBinding:
    def test_reference_binds_to_an_object_id(self):
        """object_id identifies ONE version, so binding is version-specific."""
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1-v3", ObjectType.EVIDENCE)])
        assert lin.reference_ids == ("obj-ev-1-v3",)

    def test_different_versions_are_different_references(self):
        v1 = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-v1", ObjectType.EVIDENCE)])
        v2 = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-v2", ObjectType.EVIDENCE)])
        assert v1.reference_ids != v2.reference_ids

    def test_reference_carries_declared_type(self):
        lin = derive(
            "obj-pr-1", ObjectType.PROBLEM, [("obj-fa-1", ObjectType.FACT)]
        )
        assert lin.reference_types == (ObjectType.FACT,)

    def test_duplicate_reference_rejected(self):
        with pytest.raises(DuplicateReferenceError):
            derive(
                "obj-pr-1",
                ObjectType.PROBLEM,
                [("obj-fa-1", ObjectType.FACT), ("obj-fa-1", ObjectType.FACT)],
            )

    def test_self_reference_rejected(self):
        with pytest.raises(LineageError):
            derive("obj-x", ObjectType.FACT, [("obj-x", ObjectType.EVIDENCE)])


# ---------------------------------------------------------------------------
# AC2 -- references never repoint [I3]
# ---------------------------------------------------------------------------

class TestNoRepointing:
    def test_lineage_is_frozen(self):
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        with pytest.raises(Exception):
            lin.references = ()

    def test_extension_returns_new_instance(self):
        original = derive(
            "obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)]
        )
        extended = original.extended_with(LineageRef("obj-ev-2", ObjectType.EVIDENCE))
        assert extended is not original
        assert original.reference_ids == ("obj-ev-1",)
        assert extended.reference_ids == ("obj-ev-1", "obj-ev-2")

    def test_extension_preserves_order(self):
        """Prior references keep their positions -- justification is stable."""
        original = derive(
            "obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)]
        )
        extended = original.extended_with(
            LineageRef("obj-ev-2", ObjectType.EVIDENCE),
            LineageRef("obj-ev-3", ObjectType.EVIDENCE),
        )
        assert extended.reference_ids[:1] == original.reference_ids

    def test_extension_rejects_duplicate(self):
        original = derive(
            "obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)]
        )
        with pytest.raises(DuplicateReferenceError):
            original.extended_with(LineageRef("obj-ev-1", ObjectType.EVIDENCE))

    def test_removal_detected_as_repoint(self):
        before = derive(
            "obj-fa-1",
            ObjectType.FACT,
            [("obj-ev-1", ObjectType.EVIDENCE), ("obj-ev-2", ObjectType.EVIDENCE)],
        )
        after = derive("obj-fa-2", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        with pytest.raises(RepointError):
            assert_no_repoint(before, after)

    def test_reorder_detected_as_repoint(self):
        before = derive(
            "obj-fa-1",
            ObjectType.FACT,
            [("obj-ev-1", ObjectType.EVIDENCE), ("obj-ev-2", ObjectType.EVIDENCE)],
        )
        after = derive(
            "obj-fa-2",
            ObjectType.FACT,
            [("obj-ev-2", ObjectType.EVIDENCE), ("obj-ev-1", ObjectType.EVIDENCE)],
        )
        with pytest.raises(RepointError):
            assert_no_repoint(before, after)

    def test_pure_addition_is_permitted(self):
        before = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        after = before.with_object_id("obj-fa-2").extended_with(
            LineageRef("obj-ev-2", ObjectType.EVIDENCE)
        )
        assert_no_repoint(before, after)  # must not raise

    def test_with_object_id_preserves_references(self):
        before = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        rebound = before.with_object_id("obj-fa-2")
        assert rebound.references == before.references
        assert rebound.object_id == "obj-fa-2"


# ---------------------------------------------------------------------------
# AC3 -- self-describing without the graph [N-6, Article V]
# ---------------------------------------------------------------------------

class TestSelfDescribing:
    def test_lineage_is_self_describing(self):
        lin = derive("obj-pr-1", ObjectType.PROBLEM, [("obj-fa-1", ObjectType.FACT)])
        assert lin.is_self_describing()

    def test_root_is_self_describing(self):
        assert root_lineage("obj-ev-1").is_self_describing()

    def test_type_known_without_lookup(self):
        """Every reference carries its type -- no graph consultation needed."""
        lin = derive(
            "obj-pt-1",
            ObjectType.PATTERN,
            [("obj-pr-1", ObjectType.PROBLEM), ("obj-pr-2", ObjectType.PROBLEM)],
        )
        assert lin.references_of_type(ObjectType.PROBLEM) == lin.references
        assert lin.references_of_type(ObjectType.FACT) == ()

    def test_object_interpretable_with_no_resolver(self):
        lin = derive("obj-so-1", ObjectType.SOLUTION, [("obj-op-1", ObjectType.OPPORTUNITY)])
        assert lin.reference_ids and lin.reference_types
        assert not lin.is_root


# ---------------------------------------------------------------------------
# V2 / E-V1 / AD-05 -- root rules
# ---------------------------------------------------------------------------

class TestRootRules:
    def test_evidence_lineage_is_empty(self):
        assert root_lineage("obj-ev-1").references == ()

    def test_evidence_with_references_rejected(self):
        for source in ObjectType:
            with pytest.raises(RootLineageError):
                derive("obj-ev-1", ObjectType.EVIDENCE, [("obj-x", source)])

    @pytest.mark.parametrize(
        "object_type", [t for t in ObjectType if not t.is_root]
    )
    def test_non_evidence_requires_references(self, object_type):
        with pytest.raises(EmptyLineageError):
            derive("obj-1", object_type, [])

    def test_only_evidence_is_root(self):
        assert root_lineage("obj-ev-1").is_root
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        assert not lin.is_root


# ---------------------------------------------------------------------------
# V3 -- resolution
# ---------------------------------------------------------------------------

class TestResolution:
    def test_resolvable_references_accepted(self):
        resolver = DictResolver({"obj-ev-1": ObjectType.EVIDENCE})
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        lin.resolve(resolver)  # must not raise

    def test_unresolvable_reference_rejected(self):
        resolver = DictResolver({})
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        with pytest.raises(UnresolvedReferenceError):
            lin.resolve(resolver)

    def test_type_mismatch_rejected(self):
        resolver = DictResolver({"obj-ev-1": ObjectType.PROBLEM})
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        with pytest.raises(TypeMismatchError):
            lin.resolve(resolver)

    def test_root_resolves_trivially(self):
        root_lineage("obj-ev-1").resolve(DictResolver({}))


# ---------------------------------------------------------------------------
# V4 -- evidence reachability
# ---------------------------------------------------------------------------

class TestEvidenceReachability:
    def _chain(self) -> dict[str, Lineage]:
        """Full depth-8 chain: Evidence -> ... -> FeedbackRecord."""
        chain: dict[str, Lineage] = {"obj-ev": root_lineage("obj-ev")}
        order = [
            (ObjectType.FACT, "obj-fa", "obj-ev", ObjectType.EVIDENCE),
            (ObjectType.PROBLEM, "obj-pr", "obj-fa", ObjectType.FACT),
            (ObjectType.PATTERN, "obj-pt", "obj-pr", ObjectType.PROBLEM),
            (ObjectType.OPPORTUNITY, "obj-op", "obj-pt", ObjectType.PATTERN),
            (ObjectType.SOLUTION, "obj-so", "obj-op", ObjectType.OPPORTUNITY),
            (ObjectType.VALIDATION, "obj-va", "obj-so", ObjectType.SOLUTION),
            (ObjectType.EXECUTION_RECORD, "obj-xr", "obj-so", ObjectType.SOLUTION),
            (ObjectType.FEEDBACK_RECORD, "obj-fr", "obj-xr",
             ObjectType.EXECUTION_RECORD),
        ]
        for otype, oid, parent, ptype in order:
            chain[oid] = derive(oid, otype, [(parent, ptype)])
        return chain

    def test_evidence_reaches_itself(self):
        assert evidence_reachable(root_lineage("obj-ev"), lambda _: None)

    def test_depth_eight_chain_reaches_evidence(self):
        """The pipeline's maximum lineage depth. [IOM section 2.4]"""
        chain = self._chain()
        assert evidence_reachable(chain["obj-fr"], chain.get)

    @pytest.mark.parametrize(
        "oid", ["obj-fa", "obj-pr", "obj-pt", "obj-op", "obj-so", "obj-va", "obj-xr"]
    )
    def test_every_object_in_chain_reaches_evidence(self, oid):
        chain = self._chain()
        assert evidence_reachable(chain[oid], chain.get)

    def test_orphaned_lineage_does_not_reach_evidence(self):
        orphan = derive("obj-pr-1", ObjectType.PROBLEM, [("obj-missing", ObjectType.FACT)])
        assert not evidence_reachable(orphan, lambda _: None)

    def test_traversal_terminates_on_depth_bound(self):
        """Bounded depth guarantees termination even on pathological input."""
        deep: dict[str, Lineage] = {}
        for i in range(100):
            parent = f"obj-p{i + 1}"
            deep[f"obj-p{i}"] = derive(
                f"obj-p{i}", ObjectType.PROBLEM, [(parent, ObjectType.FACT)]
            )
        assert not evidence_reachable(deep["obj-p0"], deep.get, max_depth=10)

    def test_fan_in_reaches_evidence(self):
        chain = {
            "obj-ev-1": root_lineage("obj-ev-1"),
            "obj-ev-2": root_lineage("obj-ev-2"),
        }
        chain["obj-fa"] = derive(
            "obj-fa",
            ObjectType.FACT,
            [("obj-ev-1", ObjectType.EVIDENCE), ("obj-ev-2", ObjectType.EVIDENCE)],
        )
        assert evidence_reachable(chain["obj-fa"], chain.get)


# ---------------------------------------------------------------------------
# Relationship projection [N-6]
# ---------------------------------------------------------------------------

class TestRelationshipProjection:
    def test_lineage_projects_to_derives_from_edges(self):
        lin = derive(
            "obj-pt-1",
            ObjectType.PATTERN,
            [("obj-pr-1", ObjectType.PROBLEM), ("obj-pr-2", ObjectType.PROBLEM)],
        )
        edges = lin.to_relationships(Engine.PATTERN_INTELLIGENCE, NOW)
        assert len(edges) == 2
        assert all(e.relationship_type is RelationshipType.DERIVES_FROM for e in edges)
        assert all(e.is_lineage for e in edges)

    def test_projection_preserves_direction(self):
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        edge = lin.to_relationships(Engine.FACT_EXTRACTION, NOW)[0]
        assert edge.from_object_id == "obj-fa-1"
        assert edge.to_object_id == "obj-ev-1"

    def test_root_projects_no_edges(self):
        assert root_lineage("obj-ev-1").to_relationships(Engine.RESEARCH, NOW) == ()

    def test_projection_carries_attribution(self):
        lin = derive("obj-fa-1", ObjectType.FACT, [("obj-ev-1", ObjectType.EVIDENCE)])
        edge = lin.to_relationships(Engine.FACT_EXTRACTION, NOW)[0]
        assert edge.asserted_by_engine is Engine.FACT_EXTRACTION
        assert edge.asserted_at == NOW


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=300, deadline=None)
@given(
    child=st.sampled_from([t for t in ObjectType if not t.is_root]),
    count=st.integers(min_value=1, max_value=12),
)
def test_any_non_root_with_references_is_valid(child, count):
    parent = PARENT_OF[child]
    lin = derive(
        "obj-child", child, [(f"obj-p{i}", parent) for i in range(count)]
    )
    assert len(lin.references) == count
    assert lin.is_self_describing()
    assert not lin.is_root


@settings(max_examples=200, deadline=None)
@given(source=st.sampled_from(list(ObjectType)), count=st.integers(1, 6))
def test_evidence_never_accepts_references(source, count):
    """AD-05 holds for any source type and any count."""
    with pytest.raises(RootLineageError):
        derive(
            "obj-ev", ObjectType.EVIDENCE,
            [(f"obj-x{i}", source) for i in range(count)],
        )


@settings(max_examples=200, deadline=None)
@given(additions=st.integers(min_value=1, max_value=10))
def test_extension_is_always_additive(additions):
    """Prior references survive every extension. [I3]"""
    lineage = derive("obj-fa", ObjectType.FACT, [("obj-ev-0", ObjectType.EVIDENCE)])
    original = lineage.reference_ids
    for i in range(1, additions + 1):
        lineage = lineage.extended_with(
            LineageRef(f"obj-ev-{i}", ObjectType.EVIDENCE)
        )
        assert lineage.reference_ids[: len(original)] == original
    assert len(lineage.references) == additions + 1


@settings(max_examples=200, deadline=None)
@given(depth=st.integers(min_value=1, max_value=8))
def test_chains_of_any_valid_depth_reach_evidence(depth):
    """Termination and reachability hold across the full pipeline depth."""
    ladder = [
        ObjectType.FACT, ObjectType.PROBLEM, ObjectType.PATTERN,
        ObjectType.OPPORTUNITY, ObjectType.SOLUTION, ObjectType.VALIDATION,
        ObjectType.EXECUTION_RECORD, ObjectType.FEEDBACK_RECORD,
    ]
    store: dict[str, Lineage] = {"obj-0": root_lineage("obj-0")}
    prev_id, prev_type = "obj-0", ObjectType.EVIDENCE
    for i in range(depth):
        otype = ladder[i]
        oid = f"obj-{i + 1}"
        store[oid] = derive(oid, otype, [(prev_id, prev_type)])
        prev_id, prev_type = oid, otype

    assert evidence_reachable(store[prev_id], store.get)


class TestLineageGuards:
    def test_empty_object_id_rejected(self):
        with pytest.raises(LineageError):
            Lineage(object_id="", object_type=ObjectType.EVIDENCE, references=())

    def test_non_self_describing_when_type_missing(self):
        lin = derive("obj-fa", ObjectType.FACT, [("obj-ev", ObjectType.EVIDENCE)])
        broken = Lineage.__new__(Lineage)
        object.__setattr__(broken, "object_id", lin.object_id)
        object.__setattr__(broken, "object_type", lin.object_type)
        object.__setattr__(broken, "references", (LineageRef.__new__(LineageRef),))
        object.__setattr__(broken.references[0], "object_id", "obj-ev")
        object.__setattr__(broken.references[0], "object_type", "Evidence")
        assert not broken.is_self_describing()

    def test_reachability_skips_already_visited(self):
        """Diamond: the shared ancestor is visited once, not twice."""
        store = {
            "ev": root_lineage("ev"),
            "fa-1": derive("fa-1", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)]),
            "fa-2": derive("fa-2", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)]),
        }
        store["pr"] = derive(
            "pr", ObjectType.PROBLEM,
            [("fa-1", ObjectType.FACT), ("fa-2", ObjectType.FACT)],
        )
        assert evidence_reachable(store["pr"], store.get)
