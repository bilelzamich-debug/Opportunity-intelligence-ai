"""Object identity allocation.

Task: T01.1.1

Architecture References:
- R-1   Objects immutable; change produces a new version
- R-1a  Lineage references bind to a specific version
- I1    Content immutable; only status may transition
- I2    object_id never reused
- I3    Lineage references never repoint
- I5    Exactly one ACTIVE version per lineage_id  (enforced in Store, not here)
- V11   version = predecessor + 1; lineage_id unchanged
- N-11  Concurrent acquisition permitted; allocation must be thread-safe
- IOM   section 1.1 (universal required attributes)

Scope: allocates and validates identity only. Does not persist, does not know
about status, does not enforce I5 -- that belongs to the Knowledge Store.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Iterable


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class IdentityError(Exception):
    """Base class for identity violations."""


class ObjectIdReuseError(IdentityError):
    """Raised when a retired or live object_id is presented for reuse (I2)."""


class VersionSequenceError(IdentityError):
    """Raised when a version does not increment by exactly 1 (V11)."""


class LineageMismatchError(IdentityError):
    """Raised when a successor's lineage_id differs from its predecessor (V11)."""


class UnknownObjectIdError(IdentityError):
    """Raised when succeeding an object_id this allocator never issued."""


class BranchingError(IdentityError):
    """Raised when a version is superseded twice. [R-1, I5]

    A fork would leave two competing "next" versions, making the single
    ACTIVE version per lineage undecidable.
    """


# --------------------------------------------------------------------------
# Identity value object
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ObjectIdentity:
    """The identity triple carried by every Intelligence Object. [I1, I3]"""

    object_id: str
    lineage_id: str
    version: int

    def __post_init__(self) -> None:
        if not self.object_id:
            raise IdentityError("object_id must be non-empty")
        if not self.lineage_id:
            raise IdentityError("lineage_id must be non-empty")
        if self.version < 1:
            raise VersionSequenceError(
                f"version must start at 1, got {self.version}"
            )

    @property
    def is_initial(self) -> bool:
        """True if this is the first version in its supersession chain."""
        return self.version == 1

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.object_id} (lineage={self.lineage_id} v{self.version})"


# --------------------------------------------------------------------------
# Allocator
# --------------------------------------------------------------------------

class IdentityAllocator:
    """Allocates identities and enforces the identity invariants.

    Thread-safe. [N-11]
    Retains every object_id ever issued, making reuse rejectable. [I2]
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # object_id -> (lineage_id, version). Never pruned: I2 requires that
        # a retired id stays known so reuse can be rejected.
        self._issued: dict[str, tuple[str, int]] = {}
        # lineage_id -> highest version issued so far.
        self._chain_head: dict[str, int] = {}
        # object_ids already superseded. R-1 chains are linear, so an
        # object_id may be succeeded at most once.
        self._superseded: set[str] = set()

    # -- allocation -------------------------------------------------------

    def new_object(self) -> ObjectIdentity:
        """Allocate identity for a brand-new logical object (version 1)."""
        with self._lock:
            lineage_id = self._fresh_lineage_id()
            object_id = self._fresh_object_id()
            identity = ObjectIdentity(
                object_id=object_id, lineage_id=lineage_id, version=1
            )
            self._issued[object_id] = (lineage_id, 1)
            self._chain_head[lineage_id] = 1
            return identity

    def succeed(self, predecessor: ObjectIdentity) -> ObjectIdentity:
        """Allocate identity for the next version of an existing object.

        The successor receives a new object_id; versions are distinct
        objects, not mutations. [R-1, V11]
        """
        with self._lock:
            known = self._issued.get(predecessor.object_id)
            if known is None:
                raise UnknownObjectIdError(
                    f"cannot succeed unknown object_id {predecessor.object_id!r}"
                )

            known_lineage, known_version = known
            if known_lineage != predecessor.lineage_id:
                raise LineageMismatchError(
                    f"object_id {predecessor.object_id!r} belongs to lineage "
                    f"{known_lineage!r}, not {predecessor.lineage_id!r}"
                )
            if known_version != predecessor.version:
                raise VersionSequenceError(
                    f"object_id {predecessor.object_id!r} is version "
                    f"{known_version}, not {predecessor.version}"
                )

            if predecessor.object_id in self._superseded:
                raise BranchingError(
                    f"object_id {predecessor.object_id!r} has already been "
                    f"superseded; supersession chains are linear and may not "
                    f"branch (R-1, I5)"
                )

            next_version = predecessor.version + 1
            object_id = self._fresh_object_id()
            identity = ObjectIdentity(
                object_id=object_id,
                lineage_id=predecessor.lineage_id,
                version=next_version,
            )
            self._issued[object_id] = (predecessor.lineage_id, next_version)
            self._superseded.add(predecessor.object_id)
            head = self._chain_head.get(predecessor.lineage_id, 0)
            if next_version > head:
                self._chain_head[predecessor.lineage_id] = next_version
            return identity

    # -- validation -------------------------------------------------------

    def assert_not_reused(self, object_id: str) -> None:
        """Reject an object_id that has already been issued. [I2]"""
        with self._lock:
            if object_id in self._issued:
                raise ObjectIdReuseError(
                    f"object_id {object_id!r} has already been issued and "
                    f"may never be reused (I2)"
                )

    def validate_succession(
        self, predecessor: ObjectIdentity, successor: ObjectIdentity
    ) -> None:
        """Validate a predecessor/successor pair. Pure check, no allocation. [V11]"""
        if successor.lineage_id != predecessor.lineage_id:
            raise LineageMismatchError(
                f"lineage_id must be constant across a supersession chain: "
                f"{predecessor.lineage_id!r} -> {successor.lineage_id!r}"
            )
        if successor.version != predecessor.version + 1:
            raise VersionSequenceError(
                f"version must increment by exactly 1: "
                f"{predecessor.version} -> {successor.version}"
            )
        if successor.object_id == predecessor.object_id:
            raise ObjectIdReuseError(
                "a new version must carry a new object_id (R-1, I2)"
            )

    # -- introspection ----------------------------------------------------

    def is_superseded(self, object_id: str) -> bool:
        """True if this version has already been succeeded."""
        with self._lock:
            return object_id in self._superseded

    def is_issued(self, object_id: str) -> bool:
        with self._lock:
            return object_id in self._issued

    def chain_length(self, lineage_id: str) -> int:
        """Highest version issued for a lineage; 0 if unknown."""
        with self._lock:
            return self._chain_head.get(lineage_id, 0)

    def issued_count(self) -> int:
        with self._lock:
            return len(self._issued)

    def lineage_of(self, object_id: str) -> str | None:
        with self._lock:
            known = self._issued.get(object_id)
            return known[0] if known else None

    def adopt(self, identities: Iterable[ObjectIdentity]) -> None:
        """Register externally-created identities as issued (rehydration). [I2]"""
        with self._lock:
            for identity in identities:
                existing = self._issued.get(identity.object_id)
                if existing is not None and existing != (
                    identity.lineage_id,
                    identity.version,
                ):
                    raise ObjectIdReuseError(
                        f"object_id {identity.object_id!r} already issued with "
                        f"different lineage/version"
                    )
                self._issued[identity.object_id] = (
                    identity.lineage_id,
                    identity.version,
                )
                head = self._chain_head.get(identity.lineage_id, 0)
                if identity.version > head:
                    self._chain_head[identity.lineage_id] = identity.version

    # -- internals --------------------------------------------------------

    @staticmethod
    def _fresh_object_id() -> str:
        return f"obj-{uuid.uuid4()}"

    @staticmethod
    def _fresh_lineage_id() -> str:
        return f"lin-{uuid.uuid4()}"
