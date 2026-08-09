"""Objects-authoritative lineage.

Task: T01.3.2

Architecture References:
- N-6    Objects authoritative for lineage; graph is a derived index
- R-1a   Lineage references bind to a specific version
- I3     Lineage references never repoint
- V2     derives_from non-empty except Evidence
- V4     A path to at least one Evidence object is traversable
- AD-05  No platform artifact may become Evidence
- E-V1   Evidence derives_from is empty
- Art.V  Objects must be self-describing

The object carries its own lineage. The Knowledge Graph indexes what objects
already assert and is never the authority. An object removed from the graph
remains fully interpretable; an object with corrupt lineage is invalid
regardless of what the graph says.

Scope: the lineage borne by a single object, plus resolution against a
supplied provider. Graph-wide traversal is T01.3.3-T01.3.5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Protocol

from oip.contract import LineageRef
from oip.enums import Engine, ObjectType, RelationshipType
from oip.relationships import Relationship


class LineageError(Exception):
    """Base class for lineage violations."""


class EmptyLineageError(LineageError):
    """A non-Evidence object carries no upstream references. [V2]"""


class RootLineageError(LineageError):
    """An Evidence object carries upstream references. [E-V1, AD-05]"""


class UnresolvedReferenceError(LineageError):
    """A lineage reference does not resolve to a known object. [V3]"""


class DuplicateReferenceError(LineageError):
    """The same upstream version is referenced more than once."""


class RepointError(LineageError):
    """An attempt to change an existing lineage reference. [I3]"""


class TypeMismatchError(LineageError):
    """A reference's declared type disagrees with the resolved object."""


# ---------------------------------------------------------------------------
# Resolution protocol
# ---------------------------------------------------------------------------

class ObjectResolver(Protocol):
    """Resolves an object_id to its type. Supplied by the Store."""

    def resolve_type(self, object_id: str) -> ObjectType | None:
        ...


@dataclass(frozen=True)
class DictResolver:
    """Resolver backed by a mapping. Used in tests and rebuild paths."""

    types: dict[str, ObjectType]

    def resolve_type(self, object_id: str) -> ObjectType | None:
        return self.types.get(object_id)


# ---------------------------------------------------------------------------
# Lineage
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Lineage:
    """The upstream references an object asserts about itself. [N-6]

    Frozen: references never repoint. Adding a reference is a content change
    and therefore requires a new version. [I3, R-1]
    """

    object_id: str
    object_type: ObjectType
    references: tuple[LineageRef, ...]

    def __post_init__(self) -> None:
        if not self.object_id:
            raise LineageError("lineage requires an object_id")

        if self.object_type.is_root:
            if self.references:
                raise RootLineageError(
                    f"Evidence {self.object_id!r} may not derive from anything; "
                    f"Evidence originates from external reality only "
                    f"[E-V1, AD-05, Article IV]"
                )
        elif not self.references:
            raise EmptyLineageError(
                f"{self.object_type.value} {self.object_id!r} must reference at "
                f"least one upstream object [V2]"
            )

        seen: set[str] = set()
        for ref in self.references:
            if ref.object_id == self.object_id:
                raise LineageError(
                    f"object {self.object_id!r} may not derive from itself"
                )
            if ref.object_id in seen:
                raise DuplicateReferenceError(
                    f"upstream {ref.object_id!r} referenced more than once"
                )
            seen.add(ref.object_id)

    # -- properties -------------------------------------------------------

    @property
    def is_root(self) -> bool:
        """True for Evidence: the only type terminating a lineage path."""
        return self.object_type.is_root

    @property
    def reference_ids(self) -> tuple[str, ...]:
        return tuple(ref.object_id for ref in self.references)

    @property
    def reference_types(self) -> tuple[ObjectType, ...]:
        return tuple(ref.object_type for ref in self.references)

    def references_of_type(self, object_type: ObjectType) -> tuple[LineageRef, ...]:
        return tuple(r for r in self.references if r.object_type is object_type)

    # -- self-description [Article V] -------------------------------------

    def is_self_describing(self) -> bool:
        """True if lineage is interpretable without consulting the graph.

        Every reference carries both an id and a declared type, so an object
        can state what it derives from with no external lookup. [N-6, Art.V]
        """
        if self.is_root:
            return True
        return all(r.object_id and isinstance(r.object_type, ObjectType)
                   for r in self.references)

    # -- resolution -------------------------------------------------------

    def resolve(self, resolver: ObjectResolver) -> None:
        """Verify every reference resolves and types agree. [V3]"""
        for ref in self.references:
            actual = resolver.resolve_type(ref.object_id)
            if actual is None:
                raise UnresolvedReferenceError(
                    f"lineage reference {ref.object_id!r} does not resolve [V3]"
                )
            if actual is not ref.object_type:
                raise TypeMismatchError(
                    f"reference {ref.object_id!r} declared "
                    f"{ref.object_type.value} but resolves to {actual.value}"
                )

    # -- controlled extension ---------------------------------------------

    def extended_with(self, *refs: LineageRef) -> "Lineage":
        """Return a NEW lineage with additional references. [I3, R-1]

        Never mutates. Adding a reference is a content change requiring a new
        object version; this produces the lineage that version will carry.
        """
        existing = set(self.reference_ids)
        for ref in refs:
            if ref.object_id in existing:
                raise DuplicateReferenceError(
                    f"upstream {ref.object_id!r} already referenced"
                )
        return Lineage(
            object_id=self.object_id,
            object_type=self.object_type,
            references=self.references + tuple(refs),
        )

    def with_object_id(self, object_id: str) -> "Lineage":
        """Rebind to a new object_id, preserving references.

        Used when a successor version inherits its predecessor's upstream
        set. The references themselves are unchanged. [I3]
        """
        return Lineage(
            object_id=object_id,
            object_type=self.object_type,
            references=self.references,
        )

    # -- relationship projection ------------------------------------------

    def to_relationships(
        self, asserted_by: Engine, asserted_at
    ) -> tuple[Relationship, ...]:
        """Project lineage into DERIVES_FROM edges for graph indexing. [N-6]

        The graph is built from what objects assert. This is the projection
        that makes the index derived rather than independent.
        """
        return tuple(
            Relationship(
                relationship_type=RelationshipType.DERIVES_FROM,
                from_object_id=self.object_id,
                from_type=self.object_type,
                to_object_id=ref.object_id,
                to_type=ref.object_type,
                asserted_by_engine=asserted_by,
                asserted_at=asserted_at,
            )
            for ref in self.references
        )


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------

def root_lineage(object_id: str) -> Lineage:
    """Lineage for an Evidence object: empty by definition. [E-V1]"""
    return Lineage(
        object_id=object_id, object_type=ObjectType.EVIDENCE, references=()
    )


def derive(
    object_id: str,
    object_type: ObjectType,
    upstream: Iterable[tuple[str, ObjectType]],
) -> Lineage:
    """Build lineage from (object_id, type) pairs."""
    return Lineage(
        object_id=object_id,
        object_type=object_type,
        references=tuple(LineageRef(oid, otype) for oid, otype in upstream),
    )


def assert_no_repoint(before: Lineage, after: Lineage) -> None:
    """Verify a successor preserves its predecessor's references. [I3]

    References may be ADDED across versions; existing references may never be
    removed or changed. This is what makes an object's justification stable.
    """
    prior = before.reference_ids
    current = after.reference_ids
    if prior != current[: len(prior)]:
        raise RepointError(
            f"lineage references may not be removed or reordered: "
            f"{prior} -> {current} [I3]"
        )


def evidence_reachable(
    lineage: Lineage,
    lineage_provider: Callable[[str], "Lineage | None"],
    max_depth: int = 32,
) -> bool:
    """Whether a path to Evidence exists from this object. [V4, U6]

    Terminates by construction: bounded depth plus a visited set. The lineage
    graph is acyclic under AD-05, so the bound is a safety net rather than a
    functional limit -- maximum real depth is 8.
    """
    if lineage.is_root:
        return True

    visited: set[str] = set()
    frontier: list[tuple[Lineage, int]] = [(lineage, 0)]

    while frontier:
        current, depth = frontier.pop()
        if depth >= max_depth:
            continue
        for ref in current.references:
            if ref.object_id in visited:
                continue
            visited.add(ref.object_id)
            if ref.object_type.is_root:
                return True
            upstream = lineage_provider(ref.object_id)
            if upstream is not None:
                frontier.append((upstream, depth + 1))
    return False
