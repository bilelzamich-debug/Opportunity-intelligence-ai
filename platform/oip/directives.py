"""Research directive intake: directive-driven targets scoping acquisition.

Task: T02.2.4

Architecture References:
- N-23   The Research Trigger decision (RATIFIED 2026-08-04). A directive
         is a RECORDED INSTRUCTION that scopes acquisition -- what subject
         matter, over what period, within what bounds (S 5.1) -- and is
         infrastructure state, NOT an Intelligence Object: no tenth type
         (G19), no lineage, no confidence, no scoring.
  S 5.2  Acquisition occurs ONLY under an IN_EFFECT directive. A
         directive SCOPES; it does not schedule (N-17 untouched).
         Acquisition outside every IN_EFFECT scope is refused and the
         refusal is recorded as a failure record, never silent (G16) --
         this task's AC3.
  S 5.3  Originators are a closed set: EXTERNAL_COMMISSION,
         FEEDBACK_RESEARCH_TRIGGER, VALIDATION_BACKFLOW. The platform
         NEVER self-initiates research on its own judgement.
  S 5.4  An external commission's scope is supplied from outside; the
         platform records it verbatim and does not interpret it.
  S 5.6  Five directive states -- RAISED, IN_EFFECT, FULFILLED,
         CANCELLED, EXPIRED -- deliberately disjoint from R-2's object
         states. A directive occupies exactly one state at a time.
  S 5.7  Cancellation stops FUTURE acquisition immediately; acquired
         Evidence is unaffected; cancellation never cascades (cascade
         triggers are RETRACTED/INVALIDATED only, N-9).
  S 5.8  Every Evidence acquired under a directive records that
         directive in its explanation -- no new Evidence attribute.
- N-20 S 5.2.1  Gate 1 of the deterministic acquisition sequence:
         "Does an in-effect research directive cover this target?",
         refusal reason OUT_OF_SCOPE, evaluated BEFORE typability (2)
         and rights (3), halting at the first refusal.
- D-1 (resolved, N-23 S 5.5(i), 2026-08-19)
         AC2 as amended: "Targets recorded with their commissioning
         authority." No fourth human gate; commissioning is a
         pre-platform act the platform records, never adjudicates.
- M-01   Initiation is now partially closed by N-23; self-direction
         (D-2) remains open and is NOT implemented.
- N-4    Explicit inputs, never inferred: targets, authority and period
         are supplied from outside, exactly as the T02.1.3
         explicit-input model supplies independence groups.

WHAT IS IMPLEMENTED (the three T02.2.4 acceptance criteria)
------------------------------------------------------------
- AC1  Directives scope acquisition: a Directive carries explicit
  targets (the bounds within which acquisition is permitted, S 5.1);
  DirectiveRegistry.covers(target) resolves the IN_EFFECT, unexpired
  directive covering that target -- the mechanical gate-1 test.
- AC2  Targets recorded with their commissioning authority: every
  Directive records its authority verbatim (for EXTERNAL_COMMISSION the
  commissioning person or organisation; for the automatic originators
  the ratified mechanism itself); the platform records, never
  adjudicates.
- AC3  Out-of-scope acquisition rejected: acquisition integrates gate 1
  FIRST (N-20 S 5.2.1 order), refusing with a recorded OUT_OF_SCOPE
  failure -- never silent (G16) -- and cites the covering directive in
  the acquired Evidence's explanation (S 5.8).

WHAT IS DELIBERATELY NOT IMPLEMENTED
-------------------------------------
- No scheduling, cycle management or work-set population (N-17);
  no satisfaction criterion for FULFILLED (unspecified by the corpus --
  fulfilment is an explicit recorded act, never inferred);
  no self-directed targets (D-2 open, G6 forbids);
  no interpretation of a commission's subject matter (S 5.4: verbatim);
  no new Evidence attribute (S 5.8 uses explanation);
  no rights, typability, duplicate or drift logic -- the directive gates
  none of them and overrides nothing.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterator

from oip.contract import utc_now

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DirectiveError(Exception):
    """Base class for directive-intake violations."""


class InvalidDirectiveError(DirectiveError):
    """A directive is malformed or unattributable."""


class UnknownDirectiveError(DirectiveError):
    """A directive identifier does not resolve."""


class InvalidTransitionError(DirectiveError):
    """A lifecycle transition the ratified semantics do not grant."""


# ---------------------------------------------------------------------------
# Closed vocabularies  [N-23 S 5.3, S 5.6]
# ---------------------------------------------------------------------------


class Originator(str, Enum):
    """Who may raise a directive. [N-23 S 5.3 -- closed set]

    The platform never self-initiates research on its own judgement;
    extension requires a superseding record."""

    EXTERNAL_COMMISSION = "EXTERNAL_COMMISSION"
    FEEDBACK_RESEARCH_TRIGGER = "FEEDBACK_RESEARCH_TRIGGER"
    VALIDATION_BACKFLOW = "VALIDATION_BACKFLOW"


class DirectiveState(str, Enum):
    """The five directive states. [N-23 S 5.6]

    Deliberately disjoint from R-2's object states: a directive is
    infrastructure state, not an Intelligence Object."""

    RAISED = "RAISED"
    IN_EFFECT = "IN_EFFECT"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


ORIGINATORS: tuple[str, ...] = tuple(o.value for o in Originator)
DIRECTIVE_STATES: tuple[str, ...] = tuple(s.value for s in DirectiveState)


# ---------------------------------------------------------------------------
# The directive record  [N-23 S 5.1; AC2; N-4 explicit inputs]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Directive:
    """A recorded instruction that scopes acquisition. [N-23 S 5.1]

    Infrastructure state: no lineage, no confidence, no lifecycle under
    R-2. Every field is supplied from outside and recorded verbatim
    (N-4 explicit-input discipline; S 5.4 for external commissions) --
    targets are DECLARED, never inferred, and the commissioning
    authority is recorded alongside them exactly as AC2 (amended, D-1
    Option N-23 S 5.5(i)) requires.
    """

    directive_id: str
    originator: Originator
    authority: str
    description: str
    targets: tuple[str, ...]
    raised_at: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if not (self.directive_id or "").strip():
            raise InvalidDirectiveError("directive_id is required")
        if not isinstance(self.originator, Originator):
            raise InvalidDirectiveError(
                f"originator {self.originator!r} is outside the closed "
                f"N-23 S 5.3 set {ORIGINATORS}; extension requires a "
                f"superseding record"
            )
        if not (self.authority or "").strip():
            raise InvalidDirectiveError(
                "targets are recorded WITH their commissioning authority "
                "[AC2, D-1 resolution]; the authority is required, never "
                "blank"
            )
        if not (self.description or "").strip():
            raise InvalidDirectiveError(
                "the subject matter is recorded verbatim [N-23 S 5.4] and "
                "is required"
            )
        if not self.targets or not all(
            (t or "").strip() for t in self.targets
        ):
            raise InvalidDirectiveError(
                "a directive scopes acquisition by explicit bounds "
                "[N-23 S 5.1]; at least one non-empty target is required"
            )
        if not isinstance(self.raised_at, datetime):
            raise InvalidDirectiveError("raised_at must be a datetime")
        if self.valid_until is not None and not isinstance(
            self.valid_until, datetime
        ):
            raise InvalidDirectiveError(
                "valid_until must be a datetime or None [N-23 S 5.6: "
                "EXPIRED when the validity period elapses]"
            )
        object.__setattr__(
            self, "targets", tuple(dict.fromkeys(self.targets))
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Whether the validity period has elapsed. [N-23 S 5.6]"""
        if self.valid_until is None:
            return False
        return self.valid_until <= (now if now is not None else utc_now())

    def covers(self, target: str, now: datetime | None = None) -> bool:
        """Whether the directive's bounds cover an unexpired target:
        the SCOPE-and-period test. STATE is the registry's to apply
        (S 5.2: only IN_EFFECT scopes)."""
        return (
            target in self.targets
            and not self.is_expired(now)
        )


# ---------------------------------------------------------------------------
# The registry  [infrastructure state, N-23 S 5.6/S 5.7]
# ---------------------------------------------------------------------------


@dataclass
class DirectiveRegistry:
    """Append-only registry of directives and their state. [N-23]

    A directive occupies exactly one state at a time (S 5.6). The
    transition semantics are exactly the textual ones: raising creates
    RAISED; effecting puts a RAISED directive IN_EFFECT; fulfilment and
    cancellation end an IN_EFFECT directive (FULFILLED / CANCELLED);
    expiry is TIME-derived (S 5.6), reported -- never silently applied
    -- so a lapsed directive reads EXPIRED and stops scoping (S 5.7:
    cancellation stops FUTURE acquisition immediately; acquired
    Evidence is unaffected and nothing ever cascades).
    """

    _directives: dict[str, Directive] = field(
        default_factory=dict, init=False
    )
    _states: dict[str, DirectiveState] = field(
        default_factory=dict, init=False
    )
    _history: list[tuple[str, DirectiveState, datetime]] = field(
        default_factory=list, init=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def raise_directive(self, directive: Directive) -> Directive:
        """Record a directive in RAISED. [N-23 S 5.6]"""
        with self._lock:
            if directive.directive_id in self._directives:
                raise InvalidDirectiveError(
                    f"directive {directive.directive_id!r} already exists; "
                    f"identifiers are never reused"
                )
            self._directives[directive.directive_id] = directive
            self._states[directive.directive_id] = DirectiveState.RAISED
            self._history.append(
                (directive.directive_id, DirectiveState.RAISED,
                 directive.raised_at)
            )
        return directive

    def _require(self, directive_id: str) -> Directive:
        directive = self._directives.get(directive_id)
        if directive is None:
            raise UnknownDirectiveError(
                f"directive {directive_id!r} does not resolve [N-4]"
            )
        return directive

    def _transition(
        self,
        directive_id: str,
        required: DirectiveState,
        target: DirectiveState,
        now: datetime,
    ) -> DirectiveState:
        with self._lock:
            self._require(directive_id)
            current = self._states[directive_id]
            if current is not required:
                raise InvalidTransitionError(
                    f"directive {directive_id!r} is {current.value}; the "
                    f"ratified semantics grant {target.value} only from "
                    f"{required.value} [N-23 S 5.6]"
                )
            self._states[directive_id] = target
            self._history.append((directive_id, target, now))
        return target

    def effect(self, directive_id: str, now: datetime | None = None) -> None:
        """Put a RAISED directive IN_EFFECT -- it now scopes acquisition."""
        self._transition(
            directive_id, DirectiveState.RAISED, DirectiveState.IN_EFFECT,
            now if now is not None else utc_now(),
        )

    def fulfil(self, directive_id: str, now: datetime | None = None) -> None:
        """Record that the scope is satisfied. An explicit recorded act:
        the corpus specifies no satisfaction criterion, so none is
        inferred."""
        self._transition(
            directive_id, DirectiveState.IN_EFFECT, DirectiveState.FULFILLED,
            now if now is not None else utc_now(),
        )

    def cancel(self, directive_id: str, now: datetime | None = None) -> None:
        """Withdraw an IN_EFFECT directive. [N-23 S 5.7]

        Stops future acquisition immediately. Acquired Evidence is
        unaffected; nothing cascades (N-9: cascade triggers are
        RETRACTED/INVALIDATED only, and a directive is not upstream
        lineage). The cancelled directive is RETAINED, never deleted."""
        self._transition(
            directive_id, DirectiveState.IN_EFFECT, DirectiveState.CANCELLED,
            now if now is not None else utc_now(),
        )

    def state_of(
        self, directive_id: str, now: datetime | None = None
    ) -> DirectiveState:
        """The directive's one current state, expiry included. [S 5.6]"""
        with self._lock:
            directive = self._require(directive_id)
            state = self._states[directive_id]
        if (
            state is DirectiveState.IN_EFFECT
            and directive.is_expired(now)
        ):
            return DirectiveState.EXPIRED
        return state

    def covers(
        self, target: str, now: datetime | None = None
    ) -> Directive | None:
        """The IN_EFFECT directive scoping this target, or None. [AC1]

        Gate 1's test (N-20 S 5.2.1): the covering directive must be
        IN_EFFECT and unexpired. RAISED does not scope; FULFILLED,
        CANCELLED and EXPIRED directives scope nothing (S 5.2, S 5.7).
        """
        reference = now if now is not None else utc_now()
        with self._lock:
            candidates = [
                d for d in self._directives.values()
                if self._states[d.directive_id] is DirectiveState.IN_EFFECT
                and d.covers(target, reference)
            ]
        return candidates[0] if candidates else None

    def in_effect(self, now: datetime | None = None) -> tuple[Directive, ...]:
        """All directives currently scoping acquisition. [S 5.2]"""
        reference = now if now is not None else utc_now()
        with self._lock:
            return tuple(
                d for d in self._directives.values()
                if self.state_of(d.directive_id, reference)
                is DirectiveState.IN_EFFECT
            )

    def get(self, directive_id: str) -> Directive:
        with self._lock:
            return self._require(directive_id)

    def history(
        self, directive_id: str
    ) -> tuple[tuple[DirectiveState, datetime], ...]:
        """The recorded transition history, append-only. [N-04 discipline]"""
        with self._lock:
            self._require(directive_id)
            return tuple(
                (state, at)
                for did, state, at in self._history
                if did == directive_id
            )

    def __len__(self) -> int:
        with self._lock:
            return len(self._directives)

    def __iter__(self) -> Iterator[Directive]:
        with self._lock:
            return iter(tuple(self._directives.values()))
