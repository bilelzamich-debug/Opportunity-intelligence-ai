"""Acquisition rights: per-source assessment, enforced before acquisition.

Task: T02.1.2

Architecture References:
- N-21   Acquisition Rights (RATIFIED 2026-08-04). This module implements
         its section 5 vocabulary and enforcement mechanism exactly: the
         closed rights vocabulary (5.5), the admissibility model --
         acquisition proceeds only on an explicit, UNEXPIRED PERMITTED,
         and UNASSESSED fails closed (5.4) -- the retention-rights model
         and its more-restrictive-governs relation to N-12 (5.6), the N-15
         storage-mode determination this task was scheduled to supply
         (5.7), and the CI-1 boundary: rights are recorded on the Evidence
         object in access_conditions, never in a configuration store, and
         never participate in reasoning, scoring, pattern detection or
         lineage (5.9).
- N-24   The acquisition-rights authority (RATIFIED 2026-08-19): the ROLE
         *Designated Source Rights/Compliance Authority*, scope limited to
         the N-21 section 5.5 vocabulary. Every assessment is attributed
         to that role. Until the role supplies assessments, every source
         is UNASSESSED and acquisition fails closed -- ratification of the
         role does not by itself admit a single source.
- N-20   Section 5.2.1 fixes the deterministic gate order: scope (1),
         typability (2), rights (3). This module is gate 3 only. It
         neither defines nor evaluates the other two; halting order is
         inherited, not redefined here.
- N-10   Refusals are recorded, never silent (K10): every refusal this
         module produces carries a reason and a detail, distinguishing
         refused-on-rights from attempted-and-not-found.
- N-15   "T02.1.2 determines mode at acquisition" (K4): the storage-mode
         mapping of N-21 section 5.7 is that determination. N-15's hybrid
         model and permanent provenance retention are unchanged.
- N-12   Retention POLICY (what the platform chooses to keep) is N-12's;
         retention RIGHTS (what the licence permits) are N-21's. Where
         they interact, the more restrictive governs; RETAIN_NONE refuses
         acquisition outright, so no object subject to it can ever exist
         for N-12 to retain.
- S-02   Rights values must not score (N-21 5.9): this module exposes no
         path by which a rights value could enter evidential_support.
- Art VI / K14  The platform applies assessments mechanically; it never
         decides legality. Nothing here determines what is lawful.

WHAT IS IMPLEMENTED (all from N-21 section 5)
---------------------------------------------
1. The closed rights vocabulary of section 5.5, verbatim: acquisition
   PERMITTED / PROHIBITED / UNASSESSED; retention RETAIN_FULL /
   RETAIN_REFERENCE_ONLY / RETAIN_NONE / UNASSESSED.
2. RightsAssessment: the pairing of the two for one source, attributed to
   the authority that made it, with the date assessed and the rights
   basis (section 5.3). An assessment lacking any of these degrades to
   UNASSESSED -- silence is never permission.
3. Gate 3 evaluation (section 5.4): admitted only on explicit, unexpired
   PERMITTED with retainable rights; every other outcome is a recorded
   refusal with exactly one reason.
4. The N-15 storage-mode determination (section 5.7): RETAIN_FULL stores
   in full; RETAIN_REFERENCE_ONLY stores by reference; RETAIN_NONE and
   UNASSESSED create no object at all.
5. The canonical access_conditions value composed onto Evidence (5.9) --
   refused for inadmissible assessments, because no Evidence object may
   exist to carry one.

WHAT IS DELIBERATELY NOT IMPLEMENTED (N-21 refuses; so does this module)
------------------------------------------------------------------------
- NO rights store: the recording home is the Evidence object's
  access_conditions attribute (K1), never a configuration store. This
  module holds no Intelligence Object and no registry of assessments.
- NO scope or typability evaluation: gates 1 and 2 belong to the
  acquisition sequence (N-20 section 5.2.1; T02.2.1).
- NO acquisition: enforcement PRECEDES the external act (N-21 section 5.2);
  the acquisition path itself is T02.2.1 and calls this gate.
- NO conduct policy: robots, rate limits and terms-of-use conduct are
  M-18b, open (N-21 section 9).
- NO scoring, confidence, lineage or lifecycle effect (N-21 section 5.9).
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


class RightsError(Exception):
    """Base class for acquisition-rights violations."""


class AssessmentInvalidError(RightsError):
    """An assessment is malformed or unattributable to the authority."""


class RefusedByRightsError(RightsError):
    """Gate 3 refused acquisition. [N-21 S 5.4, K10 -- never silent]"""


class AccessConditionsError(RightsError):
    """access_conditions was demanded for an inadmissible assessment."""


# ---------------------------------------------------------------------------
# The authority  [N-24 -- RATIFIED 2026-08-19]
# ---------------------------------------------------------------------------


RIGHTS_AUTHORITY_ROLE: str = "Designated Source Rights/Compliance Authority"
"""The N-21 section 5.1 authority, named by N-24 as a designated ROLE.

Scope limited to the N-21 section 5.5 vocabulary; a role, not an
individual. Assessments are attributed to this role; the platform applies
them and never decides legality (K14, Art. VI)."""


# ---------------------------------------------------------------------------
# The closed vocabulary  [N-21 S 5.5 -- verbatim]
# ---------------------------------------------------------------------------


class AcquisitionRight(str, Enum):
    """Acquisition rights. [N-21 S 5.5 -- closed; extension requires a
    superseding record]"""

    PERMITTED = "PERMITTED"
    PROHIBITED = "PROHIBITED"
    UNASSESSED = "UNASSESSED"


class RetentionRight(str, Enum):
    """Retention rights. [N-21 S 5.5 -- closed; extension requires a
    superseding record]

    RETAIN_NONE and UNASSESSED both refuse: K11/I4 make any write
    effectively permanent, so material that may not be retained is never
    acquired."""

    RETAIN_FULL = "RETAIN_FULL"
    RETAIN_REFERENCE_ONLY = "RETAIN_REFERENCE_ONLY"
    RETAIN_NONE = "RETAIN_NONE"
    UNASSESSED = "UNASSESSED"


ACQUISITION_RIGHTS: tuple[str, ...] = tuple(
    r.value for r in AcquisitionRight
)
RETENTION_RIGHTS: tuple[str, ...] = tuple(r.value for r in RetentionRight)


class StorageMode(str, Enum):
    """The N-15 storage mode selected by retention rights. [N-21 S 5.7]

    There is deliberately NO 'NONE' member: RETAIN_NONE and UNASSESSED
    create no object at all, so no mode exists to select."""

    FULL = "FULL"
    REFERENCE_ONLY = "REFERENCE_ONLY"


# ---------------------------------------------------------------------------
# The assessment  [N-21 S 5.3, S 5.5]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RightsAssessment:
    """The rights determination for one source, at one point in time.

    [N-21 S 5.3] "Rights assessment: the pairing of the two [rights] for
    one source, attributed to the authority that made it, with the date
    made." An assessment is an INPUT to the platform, not an output of it.

    [N-21 S 5.5] Every assessment additionally records the authority, the
    date assessed, and the rights basis. An assessment lacking any of
    these is UNASSESSED -- use `unassessed()` rather than forging a
    partial record.

    [N-24] The authority is the designated role; no other attribution is
    accepted, so no assessment can arrive claiming an authority the
    platform was never given.
    """

    source_identifier: str
    acquisition: AcquisitionRight
    retention: RetentionRight
    authority: str
    basis: str
    assessed_at: datetime
    valid_until: datetime | None = None

    def __post_init__(self) -> None:
        if not (self.source_identifier or "").strip():
            raise AssessmentInvalidError(
                "source_identifier is required [IOM section 3.1]"
            )
        if not isinstance(self.acquisition, AcquisitionRight):
            raise AssessmentInvalidError(
                f"acquisition right {self.acquisition!r} is outside the "
                f"closed N-21 S 5.5 vocabulary {ACQUISITION_RIGHTS}"
            )
        if not isinstance(self.retention, RetentionRight):
            raise AssessmentInvalidError(
                f"retention right {self.retention!r} is outside the closed "
                f"N-21 S 5.5 vocabulary {RETENTION_RIGHTS}"
            )
        if (self.authority or "").strip() != RIGHTS_AUTHORITY_ROLE:
            raise AssessmentInvalidError(
                f"assessment authority must be the designated role "
                f"{RIGHTS_AUTHORITY_ROLE!r} [N-24]; got {self.authority!r}. "
                f"The platform applies assessments; it never adjudicates "
                f"them."
            )
        if not (self.basis or "").strip():
            raise AssessmentInvalidError(
                "an assessment requires its rights basis: the externally "
                "verifiable ground cited for the determination [N-21 S 5.3]. "
                "Without a basis the assessment is UNASSESSED -- use "
                "unassessed(), never a forged record."
            )
        if not isinstance(self.assessed_at, datetime):
            raise AssessmentInvalidError("assessed_at must be a datetime")
        if self.valid_until is not None and not isinstance(
            self.valid_until, datetime
        ):
            raise AssessmentInvalidError(
                "valid_until must be a datetime or None [N-21 S 5.4 -- "
                "acquisition proceeds only on an UNEXPIRED PERMITTED]"
            )

    def is_expired(self, now: datetime | None = None) -> bool:
        """Whether a time-bounded assessment has lapsed. [N-21 S 5.4]"""
        if self.valid_until is None:
            return False
        return self.valid_until <= (now if now is not None else utc_now())

    @property
    def is_admissible(self) -> bool:
        """Acquisition may proceed. [N-21 S 5.4, S 5.5]

        True only for an explicit, unexpired PERMITTED whose retention
        right permits an object to exist at all. UNASSESSED fails closed
        (silence is not permission); PROHIBITED refuses; RETAIN_NONE and
        retention-UNASSESSED refuse (no object may be created).
        """
        return (
            self.acquisition is AcquisitionRight.PERMITTED
            and not self.is_expired()
            and self.retention
            in (RetentionRight.RETAIN_FULL, RetentionRight.RETAIN_REFERENCE_ONLY)
        )


def unassessed(source_identifier: str) -> RightsAssessment:
    """The fail-closed default: no determination exists. [N-21 S 5.4, N-24]

    Every source begins UNASSESSED and acquisition refuses it. This is the
    intended posture until the designated authority supplies assessments
    -- it is not an error state, and it is never silently upgraded.
    """
    return RightsAssessment(
        source_identifier=source_identifier,
        acquisition=AcquisitionRight.UNASSESSED,
        retention=RetentionRight.UNASSESSED,
        authority=RIGHTS_AUTHORITY_ROLE,
        basis="no determination has been supplied by the designated "
        "authority [N-21 S 5.4; N-24]",
        assessed_at=utc_now(),
    )


# ---------------------------------------------------------------------------
# Refusal records  [N-21 S 5.4 -- K10: refusals are recorded, never silent]
# ---------------------------------------------------------------------------


class RefusalReason(str, Enum):
    """Why gate 3 refused. One reason per refusal, exactly. [N-21 S 5.4;
    N-20 S 5.2.1 -- halt on first refusal yields exactly one reason]"""

    UNASSESSED = "UNASSESSED"
    PROHIBITED = "PROHIBITED"
    EXPIRED = "EXPIRED"
    RETAIN_NONE = "RETAIN_NONE"
    RETENTION_UNASSESSED = "RETENTION_UNASSESSED"


@dataclass(frozen=True)
class RightsRefusal:
    """One recorded gate-3 refusal. Never silent. [K10, N-10]"""

    source_identifier: str
    reason: RefusalReason
    refused_at: datetime
    detail: str

    def __post_init__(self) -> None:
        if not (self.source_identifier or "").strip():
            raise RightsError("source_identifier is required")
        if not isinstance(self.reason, RefusalReason):
            raise RightsError(
                f"refusal reason {self.reason!r} is outside the closed set"
            )
        if not isinstance(self.refused_at, datetime):
            raise RightsError("refused_at must be a datetime")
        if not (self.detail or "").strip():
            raise RightsError(
                "a refusal requires a detail: a silent refusal is exactly "
                "the K10/N-10 failure this record exists to prevent"
            )


@dataclass
class RefusalRegister:
    """Append-only register of gate-3 refusals. [K10; N-10 -- failure
    records live outside the object model, co-located with configuration]

    Acquisition (T02.2.1) consults this surface so a rights refusal is
    always distinguishable from attempted-and-not-found."""

    _refusals: list[RightsRefusal] = field(
        default_factory=list, init=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def append(self, refusal: RightsRefusal) -> RightsRefusal:
        with self._lock:
            self._refusals.append(refusal)
        return refusal

    def __len__(self) -> int:
        with self._lock:
            return len(self._refusals)

    def __iter__(self) -> Iterator[RightsRefusal]:
        with self._lock:
            return iter(tuple(self._refusals))

    def for_source(self, source_identifier: str) -> tuple[RightsRefusal, ...]:
        with self._lock:
            return tuple(
                r for r in self._refusals
                if r.source_identifier == source_identifier
            )


# ---------------------------------------------------------------------------
# Gate 3  [N-21 S 5.2, S 5.4 -- before acquisition, within Research]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateDecision:
    """The outcome of gate 3 for one source. [N-21 S 5.4]

    Exactly one of: admitted with a storage mode, or refused with exactly
    one recorded reason. Never both; never neither."""

    source_identifier: str
    admitted: bool
    storage_mode: StorageMode | None
    refusal: RightsRefusal | None

    def __post_init__(self) -> None:
        if self.admitted and (
            self.refusal is not None or self.storage_mode is None
        ):
            raise RightsError(
                "an admitted decision carries a storage mode and no refusal"
            )
        if not self.admitted and (
            self.refusal is None or self.storage_mode is not None
        ):
            raise RightsError(
                "a refused decision carries exactly one refusal and no mode"
            )


def evaluate_gate(
    assessment: RightsAssessment,
    refusals: RefusalRegister | None = None,
    now: datetime | None = None,
) -> GateDecision:
    """Evaluate gate 3 for one source. FAILS CLOSED. [N-21 S 5.4]

    Enforcement precedes the external act (S 5.2): the acquisition path
    (T02.2.1) must call this before acquiring, and may acquire only on an
    ADMITTED decision. Every refusal is recorded (K10) when a register is
    supplied -- recording is the caller's wiring, never skippable silence.
    """
    reference = now if now is not None else utc_now()
    refusal: RightsRefusal | None = None
    if assessment.acquisition is AcquisitionRight.UNASSESSED:
        refusal = RightsRefusal(
            source_identifier=assessment.source_identifier,
            reason=RefusalReason.UNASSESSED,
            refused_at=reference,
            detail="no determination exists: UNASSESSED fails closed -- "
            "silence is not permission [N-21 S 5.4]",
        )
    elif assessment.acquisition is AcquisitionRight.PROHIBITED:
        refusal = RightsRefusal(
            source_identifier=assessment.source_identifier,
            reason=RefusalReason.PROHIBITED,
            refused_at=reference,
            detail="assessed PROHIBITED by the designated authority "
            "[N-21 S 5.5]",
        )
    elif (
        assessment.acquisition is AcquisitionRight.PERMITTED
        and assessment.is_expired(now=reference)
    ):
        refusal = RightsRefusal(
            source_identifier=assessment.source_identifier,
            reason=RefusalReason.EXPIRED,
            refused_at=reference,
            detail="the PERMITTED assessment has lapsed; acquisition "
            "proceeds only on an unexpired one [N-21 S 5.4]",
        )
    elif assessment.retention is RetentionRight.RETAIN_NONE:
        refusal = RightsRefusal(
            source_identifier=assessment.source_identifier,
            reason=RefusalReason.RETAIN_NONE,
            refused_at=reference,
            detail="retention right RETAIN_NONE: nothing may be retained, "
            "so acquisition is refused outright and no object can exist "
            "[N-21 S 5.5, S 5.6]",
        )
    elif assessment.retention is RetentionRight.UNASSESSED:
        refusal = RightsRefusal(
            source_identifier=assessment.source_identifier,
            reason=RefusalReason.RETENTION_UNASSESSED,
            refused_at=reference,
            detail="retention right UNASSESSED: treated as REFUSED, never "
            "as RETAIN_REFERENCE_ONLY [N-21 S 5.5]",
        )

    if refusal is not None:
        if refusals is not None:
            refusals.append(refusal)
        return GateDecision(
            source_identifier=assessment.source_identifier,
            admitted=False,
            storage_mode=None,
            refusal=refusal,
        )

    return GateDecision(
        source_identifier=assessment.source_identifier,
        admitted=True,
        storage_mode=(
            StorageMode.FULL
            if assessment.retention is RetentionRight.RETAIN_FULL
            else StorageMode.REFERENCE_ONLY
        ),
        refusal=None,
    )


def require_permitted(
    assessment: RightsAssessment,
    refusals: RefusalRegister | None = None,
    now: datetime | None = None,
) -> StorageMode:
    """Admit acquisition only on a demonstrably permitted source.

    FAILS CLOSED: raises RefusedByRightsError on every non-admitted
    outcome, with the refusal's reason and detail (never silent). The
    acquisition path (T02.2.1) calls this as its gate-3 choke point.
    """
    decision = evaluate_gate(assessment, refusals=refusals, now=now)
    if not decision.admitted:
        assert decision.refusal is not None  # structural invariant
        raise RefusedByRightsError(
            f"source {assessment.source_identifier!r} refused at gate 3 "
            f"({decision.refusal.reason.value}): {decision.refusal.detail}"
        )
    assert decision.storage_mode is not None  # structural invariant
    return decision.storage_mode


# ---------------------------------------------------------------------------
# access_conditions  [N-21 S 5.9 -- recorded on the Evidence object]
# ---------------------------------------------------------------------------


def access_conditions_value(assessment: RightsAssessment) -> str:
    """The canonical access_conditions value for an ADMITTED assessment.

    [N-21 S 5.9] Rights are recorded on the Evidence object in
    access_conditions -- an Intelligence Object attribute, never a
    configuration store. Composing the value is refused for every
    inadmissible assessment: RETAIN_NONE and UNASSESSED create no object
    (S 5.7), so no Evidence may exist to carry their conditions. The
    composed string carries the full determination -- rights, basis,
    authority, date -- so the record is auditable without a second home.
    """
    decision = evaluate_gate(assessment)
    if not decision.admitted:
        assert decision.refusal is not None
        raise AccessConditionsError(
            f"no access_conditions value exists for source "
            f"{assessment.source_identifier!r}: the assessment is "
            f"inadmissible ({decision.refusal.reason.value}) and no "
            f"Evidence object may be created to carry one [N-21 S 5.7]"
        )
    return (
        f"acquisition={assessment.acquisition.value};"
        f"retention={assessment.retention.value};"
        f"authority={assessment.authority};"
        f"basis={assessment.basis};"
        f"assessed_at={assessment.assessed_at.isoformat()};"
        f"valid_until="
        f"{assessment.valid_until.isoformat() if assessment.valid_until else 'unbounded'}"
    )
