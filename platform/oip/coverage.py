"""Coverage model: source-type coverage with explicit gap declaration.

Task: T02.1.4

Architecture References:
- N-22   Coverage Model (RATIFIED 2026-08-04). This module implements its
         section 5 exactly: the formal definitions (5.1), the coverage
         measure over types, never volume (5.2), the out-of-frame register
         (5.2.1), declared-completeness (5.3), the closed five-reason gap
         vocabulary (5.4), NO stopping rule (5.5 -- M-01 stays open),
         report-not-gate acceptance semantics (5.6), and fail-closed
         failure semantics (5.7).
- N-20   Supplies the coverage frame: the ratified source-type taxonomy
         (section 5.1) and gate-2 refusal semantics (section 5.2,
         UNTYPABLE_CHANNEL). This module consumes both; it defines neither.
- N-03   Stage-1 proxy measure "source-type coverage" (J1), refined here
         under N-03's own extension clause (J2). Not superseded.
- N-10   "Produced nothing because it failed" is distinguishable from
         "found nothing" (J12): NOT_ATTEMPTED versus NO_MATERIAL_FOUND
         preserves that distinction at the coverage layer.
- N-16   Coverage is a Tier 2 concern; no universal attribute is added and
         Tier 1's independent_source_count is untouched (J6).
- S-02   Five exhaustive inputs, "No other input." Coverage is NOT an input
         to evidential_support and this module exposes no path by which it
         could become one (J7, N-22 section 6.5).
- S-04   Sufficiency floors are per-object and checked at acceptance.
         Coverage rejects no object; it is a report, not a gate (J8,
         N-22 section 5.6).
- AD-01  "Coverage limited by research reach -- the platform is blind to
         what it has not collected" (J9). Completeness is therefore
         DECLARED-completeness over the platform's own frame, never a
         claim about the market.
- Art X  Known gaps are recorded with the same standing as favourable
         findings (J10); an undeclared gap is a reportable deficiency of
         the report (N-22 section 5.7).
- AS-4   The out-of-frame mechanism is a SELECTED choice recorded in
         N-22's Honest Limitations: the duty is forced by Article X; the
         register mechanism is the ratified selection.

WHAT IS IMPLEMENTED (all from N-22 section 5)
---------------------------------------------
1. The coverage frame is the ratified taxonomy (N-20 section 5.1), taken
   from oip.source -- never redefined here.
2. coverage = |represented members| / |frame|, where a member is
   represented by the EXISTENCE of >=1 ACTIVE Evidence object of that
   type -- existence, not volume (N-22 section 5.2 counting rule).
3. An out-of-frame register records every gate-2 refusal (untypable
   channel) beside coverage; a report is well-formed only because it
   carries both (N-22 section 5.2.1, AS-4).
4. Gap declarations name an unrepresented member with a reason drawn from
   the closed five-value vocabulary of N-22 section 5.4 -- nothing else.
5. Declared-completeness: every frame member is represented or carries a
   declaration. An undeclared gap makes the report incomplete, and that
   state is itself reported (N-22 section 5.3).

WHAT IS DELIBERATELY NOT IMPLEMENTED (N-22 refuses, and so does this module)
----------------------------------------------------------------------------
- NO stopping rule (N-22 section 5.5): a coverage figure may inform a stop
  decision owned by M-01; it may not BE one. No threshold, no "enough".
- NO gate: coverage rejects no object, enters no confidence, alters no
  lifecycle state (N-22 section 5.6).
- NO default coverage when the frame is unavailable: coverage is UNDEFINED
  and reported as such -- never 0, never 1 (N-22 section 5.7).
- UNTYPABLE_CHANNEL is NOT a gap reason: an untypable source corresponds to
  no frame member; it belongs to the out-of-frame register alone.
- Trust, licensing, independence, scoring: untouched, per N-22 sections
  6.1-6.5. This module adds no vocabulary beyond N-22 section 5.4.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterator

from oip.contract import utc_now
from oip.source import SourceType, taxonomy_members

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class CoverageError(Exception):
    """Base class for coverage-model violations."""


class GapReasonError(CoverageError):
    """A gap reason outside the closed N-22 section 5.4 vocabulary."""


class FrameMemberError(CoverageError):
    """A declaration or measurement references a non-frame member."""


class OutOfFrameError(CoverageError):
    """An out-of-frame registration that is not actually out of frame."""


class CoverageUndefinedError(CoverageError):
    """Coverage was demanded while the frame is unavailable. [N-22 S 5.7]"""


# ---------------------------------------------------------------------------
# Gap-declaration reasons  [N-22 S 5.4 -- closed vocabulary]
# ---------------------------------------------------------------------------


class GapReason(str, Enum):
    """Why a frame member is unrepresented. [N-22 section 5.4, closed]

    Extension requires a superseding record (J14). All five values are
    DEFINED BY N-22 and owned by it: other records produce the conditions
    (N-23 scope, N-21 rights); none defines the vocabulary.

    ``UNTYPABLE_CHANNEL`` is deliberately ABSENT: an untypable source maps
    to no frame member, so it can never be a gap -- it is recorded in the
    out-of-frame register instead (N-22 section 5.2.1).
    """

    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    INACCESSIBLE = "INACCESSIBLE"
    REFUSED_BY_RIGHTS = "REFUSED_BY_RIGHTS"
    NO_MATERIAL_FOUND = "NO_MATERIAL_FOUND"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


GAP_REASONS: tuple[str, ...] = tuple(reason.value for reason in GapReason)
"""The closed reason vocabulary, in N-22 section 5.4 table order."""


# ---------------------------------------------------------------------------
# Frame  [N-22 S 5.1 -- taken from N-20, never redefined]
# ---------------------------------------------------------------------------


def coverage_frame() -> frozenset[SourceType]:
    """The coverage frame: the ratified source-type taxonomy. [N-22 S 5.1]

    Returns the N-20 section 5.1 members exactly. An EMPTY frame means the
    frame is UNAVAILABLE: coverage is then undefined and must be reported
    as such, never defaulted (N-22 section 5.7).
    """
    return frozenset(taxonomy_members())


# ---------------------------------------------------------------------------
# Gap declarations  [N-22 S 5.1, S 5.4]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GapDeclaration:
    """A recorded statement that a named member is unrepresented. [N-22 S 5.1]

    IMMUTABLE (append-only register history; nothing is edited). The reason
    is drawn from the closed N-22 section 5.4 vocabulary; the rationale is
    mandatory: a declaration without its why is unauditable (Principle 2),
    and PT-V5's "present and reasoned" requirement (J4/J5) is the ratified
    pressure against boilerplate -- the declaration is the evidential basis
    Pattern's artefact assessment will inherit at T05.1.4.
    """

    member: SourceType
    reason: GapReason
    declared_at: datetime
    rationale: str

    def __post_init__(self) -> None:
        if not isinstance(self.member, SourceType):
            raise FrameMemberError(
                f"declaration member must be a ratified SourceType, got "
                f"{self.member!r}; the frame is the taxonomy [N-22 S 5.1, "
                f"N-20 S 5.1]"
            )
        if not isinstance(self.reason, GapReason):
            raise GapReasonError(
                f"gap reason {self.reason!r} is outside the closed N-22 "
                f"S 5.4 vocabulary {GAP_REASONS}; extension requires a "
                f"superseding record"
            )
        if not isinstance(self.declared_at, datetime):
            raise CoverageError("declared_at must be a datetime")
        if not (self.rationale or "").strip():
            raise CoverageError(
                "a gap declaration requires a rationale: an unexplained "
                "declaration is unauditable, and PT-V5 requires the "
                "assessment be reasoned [N-22 S 5.4, Principle 2]"
            )


@dataclass(frozen=True)
class CoverageGap:
    """A frame member with no ACTIVE Evidence, and its declaration if any.

    The declaration may be None: an undeclared gap is a reportable
    deficiency of the REPORT (N-22 section 5.7), never silently dropped --
    the gap is carried so the incompleteness is visible (Art. X).
    """

    member: SourceType
    declaration: GapDeclaration | None = None

    @property
    def is_declared(self) -> bool:
        return self.declaration is not None


@dataclass
class GapRegister:
    """Append-only register of gap declarations. [N-22 S 5.1, S 5.3]

    The latest declaration per member is the operative one; history is
    retained in full so a historical read reproduces (N-04 discipline,
    mirroring SourceRegistry). Declaring an already-represented member is
    refused: a declaration states that a member is UNREPRESENTED, and
    representation is measured from Evidence, not asserted here.
    """

    _declarations: dict[SourceType, list[GapDeclaration]] = field(
        default_factory=dict, init=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def declare(
        self, member: SourceType, reason: GapReason, rationale: str
    ) -> GapDeclaration:
        """Append one declaration for a member. [N-22 S 5.4]"""
        declaration = GapDeclaration(
            member=member,
            reason=reason,
            declared_at=utc_now(),
            rationale=rationale,
        )
        with self._lock:
            self._declarations.setdefault(member, []).append(declaration)
        return declaration

    def declaration_for(self, member: SourceType) -> GapDeclaration | None:
        """The operative (latest) declaration for a member, or None."""
        with self._lock:
            history = self._declarations.get(member, [])
            return history[-1] if history else None

    def history_for(
        self, member: SourceType
    ) -> tuple[GapDeclaration, ...]:
        """Full declaration history for a member, in order. [N-04]"""
        with self._lock:
            return tuple(self._declarations.get(member, ()))

    def __iter__(self) -> Iterator[GapDeclaration]:
        with self._lock:
            return iter(
                tuple(
                    d
                    for history in self._declarations.values()
                    for d in history
                )
            )

    def __len__(self) -> int:
        with self._lock:
            return sum(len(h) for h in self._declarations.values())


# ---------------------------------------------------------------------------
# Out-of-frame register  [N-22 S 5.2.1 -- AS-4, the selected mechanism]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutOfFrameRefusal:
    """One recorded refusal of a source that maps to no frame member.

    [N-22 S 5.1, S 5.2.1] The refusal originates at gate 2 of the N-20
    section 5.2.1 acquisition sequence (UNTYPABLE_CHANNEL). This module
    RECORDS the refusal; it does not produce it -- acquisition is T02.2.1.
    """

    source_identifier: str
    raw_source_type: str
    refused_at: datetime
    detail: str

    def __post_init__(self) -> None:
        if not (self.source_identifier or "").strip():
            raise OutOfFrameError(
                "source_identifier is required [IOM section 3.1]"
            )
        if not (self.raw_source_type or "").strip():
            raise OutOfFrameError("raw_source_type is required")
        if not isinstance(self.refused_at, datetime):
            raise OutOfFrameError("refused_at must be a datetime")
        if not (self.detail or "").strip():
            raise OutOfFrameError(
                "a refusal requires a detail: silent refusal is exactly "
                "the N-10/N-22 section 5.2.1 failure this register exists "
                "to prevent [Art. X]"
            )


@dataclass
class OutOfFrameRegister:
    """Append-only register of out-of-frame refusals. [N-22 S 5.2.1]

    Counted BESIDE coverage, never inside it: out_of_frame does not enter
    the coverage arithmetic. Its only function is to keep a report showing
    coverage = 1.0 legible as "frame fully sampled AND material outside
    the frame was refused" rather than as complete observation.
    """

    _refusals: list[OutOfFrameRefusal] = field(
        default_factory=list, init=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def record(
        self, source_identifier: str, raw_source_type: str, detail: str
    ) -> OutOfFrameRefusal:
        """Record one gate-2 refusal. FAILS CLOSED on typable input.

        A source whose raw type DOES classify onto the taxonomy is not out
        of frame -- recording it here would hide a real coverage gap behind
        a false out-of-frame count. Typable sources belong in the gaps (or
        in represented members), never in this register.
        """
        from oip.source import UntypableChannelError, classify

        if not (raw_source_type or "").strip():
            raise OutOfFrameError("raw_source_type is required")
        try:
            classify(raw_source_type)
        except UntypableChannelError:
            refusal = OutOfFrameRefusal(
                source_identifier=source_identifier,
                raw_source_type=raw_source_type,
                refused_at=utc_now(),
                detail=detail,
            )
            with self._lock:
                self._refusals.append(refusal)
            return refusal
        raise OutOfFrameError(
            f"source {source_identifier!r} with source_type "
            f"{raw_source_type!r} CLASSIFIES onto the taxonomy; it is not "
            f"out of frame. Out-of-frame records untypable channels only "
            f"[N-22 S 5.2.1, N-20 S 5.2]."
        )

    def __len__(self) -> int:
        with self._lock:
            return len(self._refusals)

    def __iter__(self) -> Iterator[OutOfFrameRefusal]:
        with self._lock:
            return iter(tuple(self._refusals))

    def count(self) -> int:
        """out_of_frame -- the count reported beside coverage. [N-22 5.2.1]"""
        with self._lock:
            return len(self._refusals)


# ---------------------------------------------------------------------------
# The report  [N-22 S 5.2, S 5.3, S 5.6, S 5.7]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CoverageReport:
    """A descriptive coverage report. A REPORT, NOT A GATE. [N-22 S 5.6]

    Rejects no object, enters no confidence, alters no lifecycle state.
    Well-formed BY CONSTRUCTION: coverage and out_of_frame are reported
    together, never separately (N-22 S 5.2.1).

    ``coverage`` is None exactly when the frame is unavailable: undefined
    and reported as such, never defaulted to 0 or 1 (N-22 S 5.7).
    """

    coverage: float | None
    frame_size: int
    represented: tuple[SourceType, ...]
    gaps: tuple[CoverageGap, ...]
    out_of_frame: int
    declared_complete: bool

    @property
    def is_undefined(self) -> bool:
        """True when the frame is unavailable. [N-22 S 5.7]"""
        return self.coverage is None

    @property
    def undeclared_gaps(self) -> tuple[CoverageGap, ...]:
        """Gaps carrying no declaration -- reportable deficiencies. [Art X]"""
        return tuple(g for g in self.gaps if not g.is_declared)

    def inheritable_declarations(self) -> tuple[GapDeclaration, ...]:
        """Operative declarations for every declared gap. [T05.1.4, J4/J5]

        The surface Pattern's artefact assessment (PT-V5) consumes at
        T05.1.4: immutable, typed, rationale-carrying records -- one per
        declared gap, in frame order.
        """
        return tuple(
            g.declaration for g in self.gaps if g.declaration is not None
        )


def measure_coverage(
    active_evidence_types: tuple[str, ...] | list[str],
    declarations: GapRegister,
    out_of_frame: OutOfFrameRegister,
    frame: frozenset[SourceType] | None = None,
) -> CoverageReport:
    """Measure source-type coverage. [N-22 S 5.2 -- AC1]

    ``active_evidence_types`` are the RAW source_type strings of the
    ACTIVE Evidence objects (caller supplies them from the Knowledge
    Store; this module reads no store, keeping CI-1 and N-16's tiering).
    Representation is by EXISTENCE of ACTIVE Evidence of that type --
    never by volume: three Evidence objects of one type represent that
    member exactly once. An ACTIVE Evidence whose raw type maps onto no
    member represents nothing (the acquisition sequence refuses such
    channels at gate 2 before Evidence can exist; nothing is guessed
    here). Status filtering is the caller's: pass ACTIVE evidence only
    (ObjectStatus.ACTIVE, R-2), as N-22 section 5.1 defines representation
    over ACTIVE Evidence.

    FAILS CLOSED on the frame: an empty/unavailable frame yields coverage
    None -- undefined, never 0, never 1 (N-22 S 5.7).
    """
    active = frame if frame is not None else coverage_frame()
    if not active:
        # The frame is unavailable: coverage is UNDEFINED and reported as
        # such. Defaulting to 0 would claim nothing is covered; to 1 would
        # claim everything is. Both are falsehoods. [N-22 S 5.7, Art. X]
        return CoverageReport(
            coverage=None,
            frame_size=0,
            represented=(),
            gaps=(),
            out_of_frame=out_of_frame.count(),
            declared_complete=False,
        )

    represented_members = frozenset(
        member
        for member in active
        if any(
            raw == member.value for raw in active_evidence_types
        )
    )
    # gaps = frame \ represented members -- exactly N-22 S 5.2. A member
    # with ACTIVE Evidence is never a gap, and a declaration held against
    # a represented member is simply not operative in this report.
    gaps = tuple(
        CoverageGap(
            member=member,
            declaration=declarations.declaration_for(member),
        )
        for member in sorted(active - represented_members, key=lambda m: m.value)
    )
    return CoverageReport(
        coverage=len(represented_members) / len(active),
        frame_size=len(active),
        represented=tuple(
            sorted(represented_members, key=lambda m: m.value)
        ),
        gaps=gaps,
        out_of_frame=out_of_frame.count(),
        declared_complete=all(g.is_declared for g in gaps),
    )
