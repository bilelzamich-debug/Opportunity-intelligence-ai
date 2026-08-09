"""Closed relationship taxonomy with asserting-engine attribution.

Task: T01.3.1

Architecture References:
- R-6    Closed ten-type relationship taxonomy; engines may not invent types
- R-1a   Lineage references bind to a specific version
- R-7    Feedback Record is the ninth object; INFORMS targets engine behaviour
- AD-02  Objects are the sole inter-engine contract
- AD-05  No platform artifact may become Evidence
- CI-1   Configuration never participates in lineage
- V12    All relationships drawn from the closed taxonomy
- I3     Lineage references never repoint
- IOM    section 2.4 (relationship semantics), section 4.5 (relationship map)

DERIVES_FROM and SUPPORTS are deliberately distinct: an object *derives from*
the inputs its engine read, and is *supported by* the subset that evidences
it. Conflating them would overstate evidential support.

Scope: relationship structure and per-type legality only. Cycle detection and
traversal belong to the Knowledge Graph (T01.3.3-T01.3.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from oip.enums import Engine, ObjectType, RelationshipType


class RelationshipError(Exception):
    """Base class for relationship violations."""


class UnknownRelationshipTypeError(RelationshipError):
    """A relationship type outside the closed taxonomy. [R-6, V12]"""


class IllegalRelationshipError(RelationshipError):
    """The type is known but not legal between these object types. [R-6]"""


class SelfReferenceError(RelationshipError):
    """An object may not relate to itself."""


class AttributionError(RelationshipError):
    """Relationship lacks asserting engine or timestamp. [R-6]"""


# ---------------------------------------------------------------------------
# Legality matrix [IOM section 2.4]
# ---------------------------------------------------------------------------

_ANY = frozenset(ObjectType)

# (from_type, to_type) pairs legal for each relationship type.
# None as a value means "any source to any target of the same type".
_LEGAL: dict[RelationshipType, frozenset[tuple[ObjectType, ObjectType]]] = {
    # Lineage: the transformation path. Legal along pipeline adjacency, plus
    # deeper reads permitted by lineage-restricted access. [N-14]
    RelationshipType.DERIVES_FROM: frozenset(
        {
            (ObjectType.FACT, ObjectType.EVIDENCE),
            (ObjectType.PROBLEM, ObjectType.FACT),
            (ObjectType.PATTERN, ObjectType.PROBLEM),
            (ObjectType.OPPORTUNITY, ObjectType.PATTERN),
            (ObjectType.SOLUTION, ObjectType.OPPORTUNITY),
            (ObjectType.VALIDATION, ObjectType.SOLUTION),
            (ObjectType.EXECUTION_RECORD, ObjectType.SOLUTION),
            (ObjectType.FEEDBACK_RECORD, ObjectType.EXECUTION_RECORD),
        }
    ),
    # Evidential backing, distinct from derivation.
    RelationshipType.SUPPORTS: frozenset(
        {
            (ObjectType.FACT, ObjectType.PROBLEM),
            (ObjectType.PROBLEM, ObjectType.PATTERN),
        }
    ),
    # Aggregate membership.
    RelationshipType.CONSTITUENT_OF: frozenset(
        {(ObjectType.PROBLEM, ObjectType.PATTERN)}
    ),
    # Intent to resolve.
    RelationshipType.ADDRESSES: frozenset(
        {
            (ObjectType.SOLUTION, ObjectType.OPPORTUNITY),
            (ObjectType.SOLUTION, ObjectType.PROBLEM),
        }
    ),
    # Subject of a test.
    RelationshipType.TESTS: frozenset(
        {
            (ObjectType.VALIDATION, ObjectType.SOLUTION),
            (ObjectType.VALIDATION, ObjectType.OPPORTUNITY),
            (ObjectType.VALIDATION, ObjectType.PATTERN),
            (ObjectType.VALIDATION, ObjectType.PROBLEM),
            (ObjectType.VALIDATION, ObjectType.FACT),
        }
    ),
    # Real-world result.
    RelationshipType.OUTCOME_OF: frozenset(
        {(ObjectType.EXECUTION_RECORD, ObjectType.SOLUTION)}
    ),
    # Version chain: same type, always.
    RelationshipType.SUPERSEDES: frozenset((t, t) for t in ObjectType),
    # Peer observations: same type, always.
    RelationshipType.DUPLICATES: frozenset((t, t) for t in ObjectType),
    RelationshipType.CONTRADICTS: frozenset((t, t) for t in ObjectType),
    # Learning influence. Targets engine behaviour, not an object -- modelled
    # separately by EngineInforms below. No object-to-object pair is legal.
    RelationshipType.INFORMS: frozenset(),
}

# Relationships that form the lineage graph. Only these are traversed when
# resolving evidence reachability. INFORMS is deliberately excluded: feedback
# influences behaviour, it never enters lineage. [AD-05, R-8, FR-I2]
LINEAGE_RELATIONSHIPS: frozenset[RelationshipType] = frozenset(
    {RelationshipType.DERIVES_FROM}
)

# Relationships asserting evidential backing, used by support computation.
SUPPORT_RELATIONSHIPS: frozenset[RelationshipType] = frozenset(
    {RelationshipType.SUPPORTS, RelationshipType.CONSTITUENT_OF}
)

# Symmetric relationships: if A relates to B, B relates to A.
SYMMETRIC_RELATIONSHIPS: frozenset[RelationshipType] = frozenset(
    {RelationshipType.DUPLICATES, RelationshipType.CONTRADICTS}
)


# ---------------------------------------------------------------------------
# Relationship
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Relationship:
    """A typed, attributed edge between two object versions.

    Frozen: relationships are asserted, never edited. [I3]
    Binds to object_id, which identifies one version. [R-1a]
    """

    relationship_type: RelationshipType
    from_object_id: str
    from_type: ObjectType
    to_object_id: str
    to_type: ObjectType
    asserted_by_engine: Engine
    asserted_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.relationship_type, RelationshipType):
            raise UnknownRelationshipTypeError(
                f"{self.relationship_type!r} is not in the closed taxonomy [R-6]"
            )
        if not self.from_object_id or not self.to_object_id:
            raise RelationshipError("both endpoints require an object_id")
        if not isinstance(self.asserted_by_engine, Engine):
            raise AttributionError(
                "relationship requires an asserting engine [R-6]"
            )
        if not isinstance(self.asserted_at, datetime):
            raise AttributionError("relationship requires asserted_at [R-6]")
        if self.from_object_id == self.to_object_id:
            raise SelfReferenceError(
                f"object {self.from_object_id!r} may not relate to itself"
            )
        self._check_legality()

    def _check_legality(self) -> None:
        legal = _LEGAL[self.relationship_type]
        if (self.from_type, self.to_type) not in legal:
            raise IllegalRelationshipError(
                f"{self.relationship_type.value} is not legal from "
                f"{self.from_type.value} to {self.to_type.value} [R-6]"
            )

    @property
    def is_lineage(self) -> bool:
        return self.relationship_type in LINEAGE_RELATIONSHIPS

    @property
    def is_symmetric(self) -> bool:
        return self.relationship_type in SYMMETRIC_RELATIONSHIPS

    def inverse(self) -> "Relationship":
        """Return the mirrored edge. Symmetric types only."""
        if not self.is_symmetric:
            raise RelationshipError(
                f"{self.relationship_type.value} is not symmetric and has no inverse"
            )
        return Relationship(
            relationship_type=self.relationship_type,
            from_object_id=self.to_object_id,
            from_type=self.to_type,
            to_object_id=self.from_object_id,
            to_type=self.from_type,
            asserted_by_engine=self.asserted_by_engine,
            asserted_at=self.asserted_at,
        )


# ---------------------------------------------------------------------------
# INFORMS: the only relationship targeting something other than an object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EngineInforms:
    """A Feedback Record informing engine behaviour. [R-6, R-7, R-8]

    Modelled separately from Relationship because its target is an engine,
    not an object. It is deliberately outside the lineage graph: feedback
    influences future behaviour and never becomes grounding. [AD-05, FR-I2]
    """

    from_object_id: str
    informs_engine: Engine
    asserted_by_engine: Engine
    asserted_at: datetime
    from_type: ObjectType = ObjectType.FEEDBACK_RECORD

    def __post_init__(self) -> None:
        if self.from_type is not ObjectType.FEEDBACK_RECORD:
            raise IllegalRelationshipError(
                "only a Feedback Record may INFORM engine behaviour [R-7]"
            )
        if not self.from_object_id:
            raise RelationshipError("INFORMS requires a source object_id")
        if not isinstance(self.informs_engine, Engine):
            raise IllegalRelationshipError("INFORMS requires a target engine")
        if not isinstance(self.asserted_by_engine, Engine):
            raise AttributionError("INFORMS requires an asserting engine [R-6]")
        if not isinstance(self.asserted_at, datetime):
            raise AttributionError("INFORMS requires asserted_at [R-6]")

    @property
    def relationship_type(self) -> RelationshipType:
        return RelationshipType.INFORMS

    @property
    def is_lineage(self) -> bool:
        """Always False. INFORMS never enters lineage. [AD-05, FR-I2]"""
        return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def legal_targets(
    relationship_type: RelationshipType, from_type: ObjectType
) -> frozenset[ObjectType]:
    """Object types this relationship may legally point to. [R-6]"""
    return frozenset(
        to for (frm, to) in _LEGAL[relationship_type] if frm is from_type
    )


def is_legal(
    relationship_type: RelationshipType,
    from_type: ObjectType,
    to_type: ObjectType,
) -> bool:
    return (from_type, to_type) in _LEGAL[relationship_type]


def lineage_edges(relationships: Iterable[Relationship]) -> tuple[Relationship, ...]:
    """Filter to edges forming the lineage graph. [AD-05]"""
    return tuple(r for r in relationships if r.is_lineage)


def assert_no_evidence_derivation(relationships: Iterable[Relationship]) -> None:
    """Evidence may never derive from anything. [AD-05, E-V1, E-I2, Article IV]

    The enforcement point for Ground Truth Protection at the relationship
    layer: no lineage edge may originate from an Evidence object.
    """
    for rel in relationships:
        if rel.is_lineage and rel.from_type is ObjectType.EVIDENCE:
            raise IllegalRelationshipError(
                f"Evidence {rel.from_object_id!r} may not derive from "
                f"{rel.to_type.value} -- Evidence originates from external "
                f"reality only [AD-05, Article IV]"
            )
