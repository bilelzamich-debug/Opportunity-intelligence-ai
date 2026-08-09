"""Object lifecycle: seven states with per-type reachability.

Task: T01.2.1

Architecture References:
- R-2   Seven-state canonical lifecycle
- R-1   Objects immutable; status transition is the sole non-versioning change
- I5    Exactly one ACTIVE version per lineage_id
- I6    Upstream RETRACTED/INVALIDATED cascades to dependents
- N-9   Cascade is a mechanical operation invoked by Orchestration
- V9    status_reason required when status is not ACTIVE
- E-V1  Evidence has no upstream, so it cannot be INVALIDATED

One vocabulary for all nine object types; reachability differs per type.
Evidence cannot reach INVALIDATED because nothing upstream can invalidate it.
"""

from __future__ import annotations

from dataclasses import dataclass

from oip.enums import ObjectStatus, ObjectType

# Canonical transitions. [R-2]
_TRANSITIONS: dict[ObjectStatus, frozenset[ObjectStatus]] = {
    ObjectStatus.PROPOSED: frozenset(
        {ObjectStatus.ACTIVE, ObjectStatus.REJECTED}
    ),
    ObjectStatus.ACTIVE: frozenset(
        {
            ObjectStatus.SUPERSEDED,
            ObjectStatus.RETRACTED,
            ObjectStatus.INVALIDATED,
            ObjectStatus.ARCHIVED,
        }
    ),
    ObjectStatus.SUPERSEDED: frozenset(),
    ObjectStatus.REJECTED: frozenset(),
    ObjectStatus.RETRACTED: frozenset(),
    ObjectStatus.INVALIDATED: frozenset(),
    ObjectStatus.ARCHIVED: frozenset(),
}

# Per-type unreachable states. [R-2, E-V1]
_UNREACHABLE: dict[ObjectType, frozenset[ObjectStatus]] = {
    # Evidence has no upstream, so nothing can invalidate it from above.
    ObjectType.EVIDENCE: frozenset({ObjectStatus.INVALIDATED}),
}


class LifecycleError(Exception):
    """Base class for lifecycle violations."""


class IllegalTransitionError(LifecycleError):
    """The transition is not permitted from the current state. [R-2]"""


class TerminalStateError(LifecycleError):
    """A terminal state may never transition. [R-2]"""


class UnreachableStateError(LifecycleError):
    """This object type can never hold that state. [R-2, E-V1]"""


class MissingReasonError(LifecycleError):
    """status_reason required for a non-ACTIVE state. [V9]"""


@dataclass(frozen=True)
class Transition:
    """A validated lifecycle transition."""

    object_type: ObjectType
    from_status: ObjectStatus
    to_status: ObjectStatus
    reason: str | None

    @property
    def clears_active(self) -> bool:
        """True if this transition removes the object from ACTIVE. [I5]"""
        return (
            self.from_status is ObjectStatus.ACTIVE
            and self.to_status is not ObjectStatus.ACTIVE
        )

    @property
    def is_cascade_trigger(self) -> bool:
        """True if dependents must be invalidated. [I6, N-9]"""
        return self.to_status in (
            ObjectStatus.RETRACTED,
            ObjectStatus.INVALIDATED,
        )


def reachable_states(object_type: ObjectType) -> frozenset[ObjectStatus]:
    """States this object type may ever hold. [R-2]"""
    return frozenset(ObjectStatus) - _UNREACHABLE.get(object_type, frozenset())


def permitted_transitions(
    object_type: ObjectType, current: ObjectStatus
) -> frozenset[ObjectStatus]:
    """Legal next states from the current one. [R-2]"""
    return _TRANSITIONS[current] & reachable_states(object_type)


def validate_transition(
    object_type: ObjectType,
    current: ObjectStatus,
    target: ObjectStatus,
    reason: str | None = None,
) -> Transition:
    """Validate a transition, raising the specific violation. [R-2, V9]"""
    if current.is_terminal:
        raise TerminalStateError(
            f"{current.value} is terminal and cannot transition [R-2]"
        )
    if target not in reachable_states(object_type):
        raise UnreachableStateError(
            f"{object_type.value} can never hold {target.value} [R-2]"
        )
    if target not in _TRANSITIONS[current]:
        raise IllegalTransitionError(
            f"{current.value} -> {target.value} is not a permitted transition; "
            f"legal targets are "
            f"{sorted(s.value for s in permitted_transitions(object_type, current))} "
            f"[R-2]"
        )
    if target.requires_reason and not (reason or "").strip():
        raise MissingReasonError(
            f"{target.value} requires a status_reason [V9]"
        )
    return Transition(
        object_type=object_type,
        from_status=current,
        to_status=target,
        reason=reason,
    )


def can_transition(
    object_type: ObjectType, current: ObjectStatus, target: ObjectStatus
) -> bool:
    """Non-raising legality check, ignoring the reason requirement."""
    if current.is_terminal:
        return False
    return (
        target in _TRANSITIONS[current]
        and target in reachable_states(object_type)
    )


def is_consumable(status: ObjectStatus) -> bool:
    """Whether an object in this state may be consumed as engine input. [I8]

    Only ACTIVE objects are current knowledge. REJECTED objects in
    particular must never re-enter the pipeline.
    """
    return status is ObjectStatus.ACTIVE
