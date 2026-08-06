"""Knowledge Graph: a derived, rebuildable traversal index.

Task: T01.3.3 (index), T01.3.4 (backward), T01.3.5 (forward), T01.3.6 (cycles)

Architecture References:
- N-6    Objects authoritative; the graph is a DERIVED index, never the authority
- R-6    Closed ten-type relationship taxonomy
- R-8    Behavioural loop closure keeps the lineage graph acyclic
- AD-05  No platform artifact may become Evidence
- V4     A path to at least one Evidence object is traversable
- V10    No lineage cycle may be introduced
- I6     Retracted/invalidated upstream cascades to dependents
- M-66   Lineage summarisation (open) -- deep sets may exceed human inspection

The graph holds no authority. It indexes what objects already assert about
themselves, and can be discarded and rebuilt from those objects at any time.
Divergence is therefore a performance problem, never a correctness one: the
graph can be the reason the platform is slow, never the reason it is wrong.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Iterable, Iterator

from oip.enums import ObjectType, RelationshipType
from oip.lineage import Lineage
from oip.relationships import Relationship

# Maximum real lineage depth is 8 (Evidence -> FeedbackRecord). The bound is
# a safety net for malformed input, not a functional limit.
MAX_LINEAGE_DEPTH = 32


class GraphError(Exception):
    """Base class for graph violations."""


class CycleError(GraphError):
    """A lineage cycle was detected or would be introduced. [V10]"""


class UnknownNodeError(GraphError):
    """Traversal requested from an object the index does not hold."""


@dataclass(frozen=True)
class Path:
    """An ordered lineage path between two objects."""

    object_ids: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.object_ids)

    @property
    def depth(self) -> int:
        """Edges traversed; a single node has depth 0."""
        return max(0, len(self.object_ids) - 1)

    def __iter__(self) -> Iterator[str]:
        return iter(self.object_ids)


@dataclass
class KnowledgeGraph:
    """Derived traversal index over object-asserted relationships. [N-6]

    Not authoritative. Built by projecting each object's own lineage into
    edges; rebuild() reconstructs the whole index from objects alone.
    """

    # object_id -> declared type
    _types: dict[str, ObjectType] = field(default_factory=dict)
    # relationship type -> from -> set of to
    _out: dict[RelationshipType, dict[str, set[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )
    # relationship type -> to -> set of from
    _in: dict[RelationshipType, dict[str, set[str]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )
    _edge_count: int = 0

    # -- construction -----------------------------------------------------

    def add_object(self, object_id: str, object_type: ObjectType) -> None:
        """Register an object node. Idempotent."""
        existing = self._types.get(object_id)
        if existing is not None and existing is not object_type:
            raise GraphError(
                f"object {object_id!r} already indexed as {existing.value}, "
                f"cannot re-index as {object_type.value}"
            )
        self._types[object_id] = object_type

    def add_relationship(self, relationship: Relationship) -> None:
        """Index one relationship. Idempotent.

        Cycle checking applies to lineage edges only: DUPLICATES and
        CONTRADICTS are symmetric by design and form legitimate loops.
        """
        self.add_object(relationship.from_object_id, relationship.from_type)
        self.add_object(relationship.to_object_id, relationship.to_type)

        rtype = relationship.relationship_type
        frm, to = relationship.from_object_id, relationship.to_object_id

        if to in self._out[rtype][frm]:
            return  # already indexed

        if relationship.is_lineage and self._would_cycle(frm, to):
            raise CycleError(
                f"lineage edge {frm!r} -> {to!r} would introduce a cycle [V10]"
            )

        self._out[rtype][frm].add(to)
        self._in[rtype][to].add(frm)
        self._edge_count += 1

    def index_lineage(self, lineage: Lineage) -> None:
        """Index an object's self-asserted lineage. [N-6]"""
        self.add_object(lineage.object_id, lineage.object_type)
        for ref in lineage.references:
            self.add_object(ref.object_id, ref.object_type)
            if self._would_cycle(lineage.object_id, ref.object_id):
                raise CycleError(
                    f"lineage edge {lineage.object_id!r} -> {ref.object_id!r} "
                    f"would introduce a cycle [V10]"
                )
            rtype = RelationshipType.DERIVES_FROM
            if ref.object_id not in self._out[rtype][lineage.object_id]:
                self._out[rtype][lineage.object_id].add(ref.object_id)
                self._in[rtype][ref.object_id].add(lineage.object_id)
                self._edge_count += 1

    @classmethod
    def rebuild(
        cls,
        lineages: Iterable[Lineage],
        relationships: Iterable[Relationship] = (),
    ) -> "KnowledgeGraph":
        """Reconstruct the entire index from objects alone. [N-6]

        This is the guarantee that makes divergence recoverable: the graph is
        disposable, because everything it holds is derivable from objects.
        """
        graph = cls()
        for lineage in lineages:
            graph.index_lineage(lineage)
        for relationship in relationships:
            graph.add_relationship(relationship)
        return graph

    # -- introspection ----------------------------------------------------

    @property
    def node_count(self) -> int:
        return len(self._types)

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def contains(self, object_id: str) -> bool:
        return object_id in self._types

    def type_of(self, object_id: str) -> ObjectType | None:
        return self._types.get(object_id)

    def resolve_type(self, object_id: str) -> ObjectType | None:
        """ObjectResolver protocol, so the graph can serve lineage.resolve()."""
        return self._types.get(object_id)

    def parents(
        self, object_id: str, rtype: RelationshipType = RelationshipType.DERIVES_FROM
    ) -> frozenset[str]:
        """Objects this one points to under the given relationship."""
        return frozenset(self._out[rtype].get(object_id, ()))

    def children(
        self, object_id: str, rtype: RelationshipType = RelationshipType.DERIVES_FROM
    ) -> frozenset[str]:
        """Objects pointing at this one under the given relationship."""
        return frozenset(self._in[rtype].get(object_id, ()))

    def roots(self) -> frozenset[str]:
        """All Evidence nodes: the only lineage terminals. [E-V1]"""
        return frozenset(
            oid for oid, otype in self._types.items() if otype.is_root
        )

    # -- T01.3.4 backward traversal --------------------------------------

    def ancestors(
        self, object_id: str, max_depth: int = MAX_LINEAGE_DEPTH
    ) -> frozenset[str]:
        """All objects reachable upstream. Terminates by visited-set. [V4]"""
        self._require(object_id)
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(object_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for parent in self._out[RelationshipType.DERIVES_FROM].get(current, ()):
                if parent not in seen:
                    seen.add(parent)
                    queue.append((parent, depth + 1))
        return frozenset(seen)

    def reaches_evidence(
        self, object_id: str, max_depth: int = MAX_LINEAGE_DEPTH
    ) -> bool:
        """Whether a path to Evidence exists. [V4, U6]"""
        self._require(object_id)
        if self._types[object_id].is_root:
            return True
        return any(
            self._types.get(a) is not None and self._types[a].is_root
            for a in self.ancestors(object_id, max_depth)
        )

    def evidence_set(
        self, object_id: str, max_depth: int = MAX_LINEAGE_DEPTH
    ) -> frozenset[str]:
        """Every Evidence object beneath this one.

        Fan-in is unbounded: a Pattern may rest on thousands of Evidence
        objects. Callers needing a human-inspectable view require lineage
        summarisation, which is unresolved. [M-66]
        """
        self._require(object_id)
        if self._types[object_id].is_root:
            return frozenset({object_id})
        return frozenset(
            a for a in self.ancestors(object_id, max_depth)
            if self._types.get(a, ObjectType.FACT).is_root
        )

    def path_to_evidence(
        self, object_id: str, max_depth: int = MAX_LINEAGE_DEPTH
    ) -> Path | None:
        """Shortest path to any Evidence object, or None. [V4]"""
        self._require(object_id)
        if self._types[object_id].is_root:
            return Path((object_id,))

        seen = {object_id}
        queue: deque[tuple[str, tuple[str, ...]]] = deque([(object_id, (object_id,))])
        while queue:
            current, trail = queue.popleft()
            if len(trail) > max_depth:
                continue
            for parent in sorted(
                self._out[RelationshipType.DERIVES_FROM].get(current, ())
            ):
                if parent in seen:
                    continue
                seen.add(parent)
                extended = trail + (parent,)
                if self._types.get(parent) is not None and self._types[parent].is_root:
                    return Path(extended)
                queue.append((parent, extended))
        return None

    def depth_to_evidence(self, object_id: str) -> int | None:
        path = self.path_to_evidence(object_id)
        return path.depth if path else None

    # -- T01.3.5 forward traversal ---------------------------------------

    def descendants(
        self, object_id: str, max_depth: int = MAX_LINEAGE_DEPTH
    ) -> frozenset[str]:
        """All objects derived from this one, transitively. [I6]

        The traversal cascade invalidation walks when Evidence is retracted.
        """
        self._require(object_id)
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(object_id, 0)])
        while queue:
            current, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for child in self._in[RelationshipType.DERIVES_FROM].get(current, ()):
                if child not in seen:
                    seen.add(child)
                    queue.append((child, depth + 1))
        return frozenset(seen)

    def impact_of(self, object_id: str) -> frozenset[str]:
        """Objects affected if this one is retracted or invalidated. [I6]"""
        return self.descendants(object_id)

    def dependents_by_type(
        self, object_id: str
    ) -> dict[ObjectType, frozenset[str]]:
        """Descendants grouped by object type, for impact reporting."""
        grouped: dict[ObjectType, set[str]] = defaultdict(set)
        for dependent in self.descendants(object_id):
            otype = self._types.get(dependent)
            if otype is not None:
                grouped[otype].add(dependent)
        return {k: frozenset(v) for k, v in grouped.items()}

    # -- T01.3.6 cycle prevention ----------------------------------------

    def _would_cycle(self, frm: str, to: str) -> bool:
        """True if a lineage edge frm -> to would close a cycle. [V10]

        A cycle forms when `to` can already reach `frm` upstream, or when the
        edge is a self-loop.
        """
        if frm == to:
            return True
        if to not in self._types:
            return False
        seen: set[str] = set()
        stack = [to]
        while stack:
            current = stack.pop()
            if current == frm:
                return True
            for parent in self._out[RelationshipType.DERIVES_FROM].get(current, ()):
                if parent not in seen:
                    seen.add(parent)
                    stack.append(parent)
        return False

    def would_introduce_cycle(self, frm: str, to: str) -> bool:
        """Public cycle check, used by the acceptance path. [V10]"""
        return self._would_cycle(frm, to)

    def is_acyclic(self) -> bool:
        """Verify the whole lineage graph is acyclic. [V10, R-8]"""
        WHITE, GREY, BLACK = 0, 1, 2
        colour: dict[str, int] = {oid: WHITE for oid in self._types}

        for start in self._types:
            if colour[start] != WHITE:
                continue
            stack: list[tuple[str, Iterator[str]]] = [
                (start, iter(sorted(
                    self._out[RelationshipType.DERIVES_FROM].get(start, ())
                )))
            ]
            colour[start] = GREY
            while stack:
                node, children = stack[-1]
                advanced = False
                for child in children:
                    if colour.get(child, WHITE) == GREY:
                        return False
                    if colour.get(child, WHITE) == WHITE:
                        colour[child] = GREY
                        stack.append((child, iter(sorted(
                            self._out[RelationshipType.DERIVES_FROM].get(child, ())
                        ))))
                        advanced = True
                        break
                if not advanced:
                    colour[node] = BLACK
                    stack.pop()
        return True

    # -- consistency ------------------------------------------------------

    def diverges_from(self, lineages: Iterable[Lineage]) -> tuple[str, ...]:
        """Object ids where the index disagrees with authoritative objects.

        Divergence is a performance/consistency concern only: objects are
        authoritative, so the remedy is always rebuild(). [N-6]
        """
        divergent: list[str] = []
        for lineage in lineages:
            indexed = self.parents(lineage.object_id)
            asserted = frozenset(lineage.reference_ids)
            if indexed != asserted:
                divergent.append(lineage.object_id)
        return tuple(divergent)

    # -- internals --------------------------------------------------------

    def _require(self, object_id: str) -> None:
        if object_id not in self._types:
            raise UnknownNodeError(f"object {object_id!r} is not indexed")
