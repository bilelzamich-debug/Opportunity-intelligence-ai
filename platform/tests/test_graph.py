"""Contract tests for the Knowledge Graph index and traversal.

Tasks: T01.3.3, T01.3.4, T01.3.5, T01.3.6

Architecture References:
- N-6   Objects authoritative; graph derived and rebuildable
- V4    Evidence reachability
- V10   No lineage cycle
- I6    Cascade traversal
- AD-05 Feedback never becomes Evidence

Acceptance criteria under test:
  T01.3.3  Graph rebuildable from objects alone; divergence recoverable;
           graph is never the authority
  T01.3.4  Every non-Evidence object reaches Evidence; traversal terminates;
           depth 8 supported
  T01.3.5  All dependents identifiable; supports cascade
  T01.3.6  Cycle-introducing write rejected; Feedback cannot reach Evidence
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.enums import Engine, ObjectType, RelationshipType
from oip.graph import (
    CycleError,
    GraphError,
    KnowledgeGraph,
    Path,
    UnknownNodeError,
)
from oip.lineage import Lineage, derive, root_lineage
from oip.relationships import Relationship

NOW = datetime(2026, 3, 1, tzinfo=timezone.utc)

CHAIN_SPEC = [
    (ObjectType.FACT, "fa", "ev", ObjectType.EVIDENCE),
    (ObjectType.PROBLEM, "pr", "fa", ObjectType.FACT),
    (ObjectType.PATTERN, "pt", "pr", ObjectType.PROBLEM),
    (ObjectType.OPPORTUNITY, "op", "pt", ObjectType.PATTERN),
    (ObjectType.SOLUTION, "so", "op", ObjectType.OPPORTUNITY),
    (ObjectType.VALIDATION, "va", "so", ObjectType.SOLUTION),
    (ObjectType.EXECUTION_RECORD, "xr", "so", ObjectType.SOLUTION),
    (ObjectType.FEEDBACK_RECORD, "fr", "xr", ObjectType.EXECUTION_RECORD),
]


def full_chain() -> list[Lineage]:
    """Depth-8 pipeline chain: ev -> fa -> pr -> pt -> op -> so -> va/xr -> fr."""
    lineages = [root_lineage("ev")]
    for otype, oid, parent, ptype in CHAIN_SPEC:
        lineages.append(derive(oid, otype, [(parent, ptype)]))
    return lineages


@pytest.fixture()
def chain_graph() -> KnowledgeGraph:
    return KnowledgeGraph.rebuild(full_chain())


# ---------------------------------------------------------------------------
# T01.3.3 -- derived, rebuildable index
# ---------------------------------------------------------------------------

class TestRebuildable:
    def test_graph_builds_from_objects_alone(self, chain_graph):
        assert chain_graph.node_count == 9
        assert chain_graph.edge_count == 8

    def test_rebuild_is_deterministic(self):
        a = KnowledgeGraph.rebuild(full_chain())
        b = KnowledgeGraph.rebuild(full_chain())
        assert a.node_count == b.node_count
        assert a.edge_count == b.edge_count
        for oid in ("fa", "pr", "pt", "fr"):
            assert a.parents(oid) == b.parents(oid)
            assert a.children(oid) == b.children(oid)

    def test_discarded_graph_fully_recovers(self, chain_graph):
        """The index is disposable: everything derives from objects. [N-6]"""
        before = {
            oid: chain_graph.parents(oid) for oid in ("fa", "pr", "pt", "fr")
        }
        rebuilt = KnowledgeGraph.rebuild(full_chain())
        after = {oid: rebuilt.parents(oid) for oid in ("fa", "pr", "pt", "fr")}
        assert before == after

    def test_divergence_is_detectable(self, chain_graph):
        """A graph missing an edge is divergent, not authoritative. [N-6]"""
        objects = full_chain()
        objects.append(derive("extra", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)]))
        divergent = chain_graph.diverges_from(objects)
        assert "extra" in divergent

    def test_no_divergence_when_consistent(self, chain_graph):
        assert chain_graph.diverges_from(full_chain()) == ()

    def test_divergence_recovered_by_rebuild(self, chain_graph):
        objects = full_chain()
        objects.append(derive("extra", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)]))
        assert chain_graph.diverges_from(objects)
        rebuilt = KnowledgeGraph.rebuild(objects)
        assert rebuilt.diverges_from(objects) == ()

    def test_graph_reports_type_but_does_not_own_it(self, chain_graph):
        """Types come from objects; the graph only mirrors them."""
        assert chain_graph.type_of("ev") is ObjectType.EVIDENCE
        assert chain_graph.resolve_type("fa") is ObjectType.FACT

    def test_conflicting_type_rejected(self):
        graph = KnowledgeGraph()
        graph.add_object("obj-1", ObjectType.FACT)
        with pytest.raises(GraphError):
            graph.add_object("obj-1", ObjectType.PROBLEM)

    def test_indexing_is_idempotent(self):
        graph = KnowledgeGraph()
        lineage = derive("fa", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)])
        graph.index_lineage(lineage)
        graph.index_lineage(lineage)
        assert graph.edge_count == 1

    def test_relationships_indexed_alongside_lineage(self):
        graph = KnowledgeGraph.rebuild(
            full_chain(),
            [
                Relationship(
                    relationship_type=RelationshipType.SUPPORTS,
                    from_object_id="fa",
                    from_type=ObjectType.FACT,
                    to_object_id="pr",
                    to_type=ObjectType.PROBLEM,
                    asserted_by_engine=Engine.PROBLEM_INTELLIGENCE,
                    asserted_at=NOW,
                )
            ],
        )
        assert graph.parents("fa", RelationshipType.SUPPORTS) == {"pr"}
        # SUPPORTS is not lineage, so DERIVES_FROM is unaffected
        assert graph.parents("fa") == {"ev"}


# ---------------------------------------------------------------------------
# T01.3.4 -- backward traversal
# ---------------------------------------------------------------------------

class TestBackwardTraversal:
    def test_every_object_reaches_evidence(self, chain_graph):
        for _, oid, _, _ in CHAIN_SPEC:
            assert chain_graph.reaches_evidence(oid), f"{oid} cannot reach Evidence"

    def test_evidence_reaches_itself(self, chain_graph):
        assert chain_graph.reaches_evidence("ev")

    def test_depth_eight_supported(self, chain_graph):
        """The chain spans 8 levels: ev,fa,pr,pt,op,so,xr,fr. [IOM section 2.4]

        IOM depth counts NODES; Path.depth counts EDGES. An 8-level chain is
        7 edges. ExecutionRecord derives from Solution per R-6, so Validation
        is a branch rather than a link in this path.
        """
        path = chain_graph.path_to_evidence("fr")
        assert len(path) == 8, "8 pipeline levels must be traversable"
        assert path.depth == 7, "8 nodes means 7 edges"
        assert chain_graph.depth_to_evidence("fr") == 7

    def test_path_to_evidence_is_ordered(self, chain_graph):
        path = chain_graph.path_to_evidence("fr")
        assert isinstance(path, Path)
        assert path.object_ids[0] == "fr"
        assert path.object_ids[-1] == "ev"
        assert path.object_ids == ("fr", "xr", "so", "op", "pt", "pr", "fa", "ev")

    def test_ancestors_include_whole_chain(self, chain_graph):
        assert chain_graph.ancestors("fr") == {"xr", "so", "op", "pt", "pr", "fa", "ev"}

    def test_evidence_set_resolves(self, chain_graph):
        assert chain_graph.evidence_set("fr") == {"ev"}

    def test_evidence_set_of_evidence_is_itself(self, chain_graph):
        assert chain_graph.evidence_set("ev") == {"ev"}

    def test_traversal_terminates_on_wide_fan_in(self):
        lineages = [root_lineage(f"ev-{i}") for i in range(200)]
        lineages.append(
            derive("fa", ObjectType.FACT,
                   [(f"ev-{i}", ObjectType.EVIDENCE) for i in range(200)])
        )
        graph = KnowledgeGraph.rebuild(lineages)
        assert len(graph.evidence_set("fa")) == 200
        assert graph.depth_to_evidence("fa") == 1

    def test_orphan_does_not_reach_evidence(self):
        graph = KnowledgeGraph()
        graph.add_object("pr", ObjectType.PROBLEM)
        assert not graph.reaches_evidence("pr")
        assert graph.path_to_evidence("pr") is None

    def test_depth_bound_terminates(self, chain_graph):
        assert chain_graph.ancestors("fr", max_depth=2) < chain_graph.ancestors("fr")

    def test_unknown_node_rejected(self, chain_graph):
        with pytest.raises(UnknownNodeError):
            chain_graph.ancestors("obj-unknown")


# ---------------------------------------------------------------------------
# T01.3.5 -- forward traversal
# ---------------------------------------------------------------------------

class TestForwardTraversal:
    def test_all_dependents_identifiable(self, chain_graph):
        """Retracting Evidence must identify everything built on it. [I6]"""
        assert chain_graph.descendants("ev") == {
            "fa", "pr", "pt", "op", "so", "va", "xr", "fr"
        }

    def test_leaf_has_no_dependents(self, chain_graph):
        assert chain_graph.descendants("fr") == frozenset()

    def test_impact_of_is_the_cascade_set(self, chain_graph):
        assert chain_graph.impact_of("ev") == chain_graph.descendants("ev")

    def test_partial_impact_from_midchain(self, chain_graph):
        assert chain_graph.impact_of("op") == {"so", "va", "xr", "fr"}

    def test_dependents_grouped_by_type(self, chain_graph):
        grouped = chain_graph.dependents_by_type("ev")
        assert grouped[ObjectType.FACT] == {"fa"}
        assert grouped[ObjectType.FEEDBACK_RECORD] == {"fr"}
        assert ObjectType.EVIDENCE not in grouped

    def test_forward_traversal_terminates_on_wide_fan_out(self):
        lineages = [root_lineage("ev")]
        lineages += [
            derive(f"fa-{i}", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)])
            for i in range(300)
        ]
        graph = KnowledgeGraph.rebuild(lineages)
        assert len(graph.descendants("ev")) == 300

    def test_forward_and_backward_are_consistent(self, chain_graph):
        """If A is an ancestor of B, B is a descendant of A."""
        for ancestor in chain_graph.ancestors("fr"):
            assert "fr" in chain_graph.descendants(ancestor)


# ---------------------------------------------------------------------------
# T01.3.6 -- cycle prevention
# ---------------------------------------------------------------------------

class TestCyclePrevention:
    def test_chain_is_acyclic(self, chain_graph):
        assert chain_graph.is_acyclic()

    def test_direct_cycle_detected(self):
        graph = KnowledgeGraph.rebuild(
            [root_lineage("ev"), derive("fa", ObjectType.FACT,
                                        [("ev", ObjectType.EVIDENCE)])]
        )
        assert graph.would_introduce_cycle("ev", "fa")

    def test_r6_blocks_back_edges_before_the_graph_sees_them(self):
        """Defence in depth: the taxonomy rejects it first. [R-6, AD-05]

        Legal DERIVES_FROM pairs follow strict pipeline adjacency and
        Evidence has no legal source, so cycles cannot be expressed through
        the relationship layer at all.
        """
        from oip.relationships import IllegalRelationshipError
        with pytest.raises(IllegalRelationshipError):
            Relationship(
                relationship_type=RelationshipType.DERIVES_FROM,
                from_object_id="ev",
                from_type=ObjectType.EVIDENCE,
                to_object_id="fa",
                to_type=ObjectType.FACT,
                asserted_by_engine=Engine.RESEARCH,
                asserted_at=NOW,
            )

    def test_cycle_guard_fires_on_untrusted_lineage(self):
        """Objects rehydrated from storage bypass R-6; the guard catches them."""
        graph = KnowledgeGraph()
        graph.index_lineage(derive("a", ObjectType.FACT, [("b", ObjectType.FACT)]))
        with pytest.raises(CycleError):
            graph.index_lineage(derive("b", ObjectType.FACT, [("a", ObjectType.FACT)]))

    def test_three_node_cycle_rejected(self):
        graph = KnowledgeGraph()
        graph.index_lineage(derive("a", ObjectType.FACT, [("b", ObjectType.FACT)]))
        graph.index_lineage(derive("b", ObjectType.FACT, [("c", ObjectType.FACT)]))
        with pytest.raises(CycleError):
            graph.index_lineage(derive("c", ObjectType.FACT, [("a", ObjectType.FACT)]))

    def test_long_cycle_detected(self, chain_graph):
        """fr -> ... -> ev already exists; ev -> fr would close the loop."""
        assert chain_graph.would_introduce_cycle("ev", "fr")

    def test_self_loop_rejected(self, chain_graph):
        assert chain_graph.would_introduce_cycle("fa", "fa")

    def test_feedback_cannot_reach_evidence(self, chain_graph):
        """FR-I2 / AD-05 enforced structurally at the graph layer."""
        assert chain_graph.would_introduce_cycle("ev", "fr")
        assert "fr" not in chain_graph.ancestors("ev")

    def test_non_cycle_edge_accepted(self, chain_graph):
        assert not chain_graph.would_introduce_cycle("pr", "ev")

    def test_symmetric_relationships_are_not_cycles(self):
        """DUPLICATES loops are legitimate; only lineage must be acyclic."""
        graph = KnowledgeGraph.rebuild(
            [root_lineage("ev-1"), root_lineage("ev-2")]
        )
        for frm, to in (("ev-1", "ev-2"), ("ev-2", "ev-1")):
            graph.add_relationship(
                Relationship(
                    relationship_type=RelationshipType.DUPLICATES,
                    from_object_id=frm,
                    from_type=ObjectType.EVIDENCE,
                    to_object_id=to,
                    to_type=ObjectType.EVIDENCE,
                    asserted_by_engine=Engine.RESEARCH,
                    asserted_at=NOW,
                )
            )
        assert graph.is_acyclic()

    def test_acyclicity_holds_on_diamond(self):
        """Diamond fan-in/fan-out is legal and not a cycle."""
        graph = KnowledgeGraph.rebuild(
            [
                root_lineage("ev"),
                derive("fa-1", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)]),
                derive("fa-2", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)]),
                derive("pr", ObjectType.PROBLEM,
                       [("fa-1", ObjectType.FACT), ("fa-2", ObjectType.FACT)]),
            ]
        )
        assert graph.is_acyclic()
        assert graph.evidence_set("pr") == {"ev"}


# ---------------------------------------------------------------------------
# Property-based
# ---------------------------------------------------------------------------

@settings(max_examples=150, deadline=None)
@given(depth=st.integers(min_value=1, max_value=8))
def test_any_chain_depth_reaches_evidence(depth):
    lineages = [root_lineage("ev")]
    prev_id, prev_type = "ev", ObjectType.EVIDENCE
    for i in range(depth):
        otype, oid, _, _ = CHAIN_SPEC[i]
        lineages.append(derive(oid, otype, [(prev_id, prev_type)]))
        prev_id, prev_type = oid, otype
    graph = KnowledgeGraph.rebuild(lineages)
    assert graph.reaches_evidence(prev_id)
    assert graph.depth_to_evidence(prev_id) == depth
    assert graph.is_acyclic()


@settings(max_examples=150, deadline=None)
@given(fan=st.integers(min_value=1, max_value=60))
def test_rebuild_matches_incremental_for_any_fan_in(fan):
    lineages = [root_lineage(f"ev-{i}") for i in range(fan)]
    lineages.append(
        derive("fa", ObjectType.FACT,
               [(f"ev-{i}", ObjectType.EVIDENCE) for i in range(fan)])
    )
    incremental = KnowledgeGraph()
    for lineage in lineages:
        incremental.index_lineage(lineage)
    rebuilt = KnowledgeGraph.rebuild(lineages)

    assert incremental.node_count == rebuilt.node_count
    assert incremental.edge_count == rebuilt.edge_count
    assert incremental.evidence_set("fa") == rebuilt.evidence_set("fa")


@settings(max_examples=150, deadline=None)
@given(fan=st.integers(min_value=1, max_value=50))
def test_descendants_and_ancestors_are_inverse(fan):
    lineages = [root_lineage("ev")]
    lineages += [
        derive(f"fa-{i}", ObjectType.FACT, [("ev", ObjectType.EVIDENCE)])
        for i in range(fan)
    ]
    graph = KnowledgeGraph.rebuild(lineages)
    for i in range(fan):
        assert "ev" in graph.ancestors(f"fa-{i}")
        assert f"fa-{i}" in graph.descendants("ev")


@settings(max_examples=100, deadline=None)
@given(depth=st.integers(min_value=2, max_value=8))
def test_no_back_edge_is_ever_acceptable(depth):
    """Closing the loop is rejected at every depth. [V10, AD-05]"""
    lineages = [root_lineage("ev")]
    prev_id, prev_type = "ev", ObjectType.EVIDENCE
    for i in range(depth):
        otype, oid, _, _ = CHAIN_SPEC[i]
        lineages.append(derive(oid, otype, [(prev_id, prev_type)]))
        prev_id, prev_type = oid, otype
    graph = KnowledgeGraph.rebuild(lineages)
    assert graph.would_introduce_cycle("ev", prev_id)


# ---------------------------------------------------------------------------
# Coverage: guards, alternate paths, protocol surface
# ---------------------------------------------------------------------------

class TestGraphGuardsAndSurface:
    def test_path_iteration_and_len(self, chain_graph):
        path = chain_graph.path_to_evidence("pr")
        assert list(path) == list(path.object_ids)
        assert len(path) == 3

    def test_single_node_path_has_zero_depth(self, chain_graph):
        path = chain_graph.path_to_evidence("ev")
        assert path.depth == 0
        assert len(path) == 1

    def test_contains_and_type_of(self, chain_graph):
        assert chain_graph.contains("ev")
        assert not chain_graph.contains("nope")
        assert chain_graph.type_of("nope") is None
        assert chain_graph.resolve_type("nope") is None

    def test_roots_lists_every_evidence_node(self):
        graph = KnowledgeGraph.rebuild(
            [root_lineage("ev-1"), root_lineage("ev-2"),
             derive("fa", ObjectType.FACT, [("ev-1", ObjectType.EVIDENCE)])]
        )
        assert graph.roots() == {"ev-1", "ev-2"}

    def test_parents_and_children_of_unknown_are_empty(self, chain_graph):
        assert chain_graph.parents("nope") == frozenset()
        assert chain_graph.children("nope") == frozenset()

    def test_unknown_node_rejected_on_every_traversal(self, chain_graph):
        for call in (
            chain_graph.descendants,
            chain_graph.ancestors,
            chain_graph.reaches_evidence,
            chain_graph.evidence_set,
            chain_graph.path_to_evidence,
        ):
            with pytest.raises(UnknownNodeError):
                call("obj-absent")

    def test_would_cycle_false_for_unindexed_target(self, chain_graph):
        assert not chain_graph.would_introduce_cycle("fa", "obj-absent")

    def test_add_relationship_is_idempotent(self):
        graph = KnowledgeGraph.rebuild([root_lineage("ev-1"), root_lineage("ev-2")])
        edge = Relationship(
            relationship_type=RelationshipType.DUPLICATES,
            from_object_id="ev-1",
            from_type=ObjectType.EVIDENCE,
            to_object_id="ev-2",
            to_type=ObjectType.EVIDENCE,
            asserted_by_engine=Engine.RESEARCH,
            asserted_at=NOW,
        )
        graph.add_relationship(edge)
        before = graph.edge_count
        graph.add_relationship(edge)
        assert graph.edge_count == before

    def test_path_respects_depth_bound(self, chain_graph):
        assert chain_graph.path_to_evidence("fr", max_depth=3) is None

    def test_evidence_set_bounded_by_depth(self, chain_graph):
        assert chain_graph.evidence_set("fr", max_depth=2) == frozenset()

    def test_descendants_bounded_by_depth(self, chain_graph):
        shallow = chain_graph.descendants("ev", max_depth=2)
        assert shallow < chain_graph.descendants("ev")

    def test_reaches_evidence_bounded_by_depth(self, chain_graph):
        assert not chain_graph.reaches_evidence("fr", max_depth=2)

    def test_dependents_by_type_empty_for_leaf(self, chain_graph):
        assert chain_graph.dependents_by_type("fr") == {}

    def test_is_acyclic_on_empty_graph(self):
        assert KnowledgeGraph().is_acyclic()

    def test_is_acyclic_detects_smuggled_cycle(self):
        """Bypass the guard to prove is_acyclic() actually walks the graph."""
        graph = KnowledgeGraph()
        graph.add_object("a", ObjectType.FACT)
        graph.add_object("b", ObjectType.FACT)
        d = RelationshipType.DERIVES_FROM
        graph._out[d]["a"].add("b")
        graph._in[d]["b"].add("a")
        graph._out[d]["b"].add("a")
        graph._in[d]["a"].add("b")
        assert not graph.is_acyclic()

    def test_is_acyclic_on_deep_chain(self):
        lineages = [root_lineage("ev")]
        prev = "ev"
        prev_type = ObjectType.EVIDENCE
        for i in range(200):
            oid = f"fa-{i}"
            lineages.append(derive(oid, ObjectType.FACT, [(prev, prev_type)])
                            if prev_type is ObjectType.EVIDENCE
                            else derive(oid, ObjectType.FACT, [(prev, ObjectType.FACT)]))
            prev, prev_type = oid, ObjectType.FACT
        graph = KnowledgeGraph.rebuild(lineages)
        assert graph.is_acyclic()
