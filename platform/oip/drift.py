"""Source drift detection by fingerprint comparison on re-acquisition.

Task: T02.2.3

Architecture References:
- N-15   Drift is DEFINED there: "content changes after capture, leaving
         lineage pointing at something no longer verifiable". The
         safeguard is that the content fingerprint is always retained
         (both storage modes), so "the platform can detect drift
         (fingerprint mismatch on re-acquisition)". This module is
         exactly that comparison, orchestrated.
- IOM    capture_fidelity is an ASSESSMENT ("what was preserved versus
         lost") in free text; no ratified ordering of fidelities exists.
         Whether re-captured material IMPROVES fidelity is therefore the
         Research Engine's explicit judgement -- a required caller input,
         never defaulted, never invented here (the same discipline
         acquisition applies to R-3's confidence components).
- R-2 / V9
         Supersession is a status transition with a recorded reason: the
         original Evidence becomes SUPERSEDED and carries status_reason.
         That transition IS the ratified record on the original object;
         Evidence has no upstream (E-V1), so a "superseding version" is a
         fresh acquisition of the same source whose admissibility E-V6
         grants once the original is no longer ACTIVE (the E-V6 index is
         ACTIVE-only).
- E-V6 / T02.2.2
         UNCHANGED material is NOT drift: it is a duplicate acquisition,
         oip/duplicates.py's domain. A drift record requires a fingerprint
         MISMATCH; this module never re-implements duplicate detection or
         the E-V6 key.
- N-10   Drift records are operational facts OUTSIDE the object model
         (no ratified Evidence attribute carries drift): an append-only
         register naming the original object, never entering lineage.

WHAT IS IMPLEMENTED (the three T02.2.3 acceptance criteria)
------------------------------------------------------------
- AC1  Changed source content detected: `detect` resolves the ACTIVE
  Evidence held for the source (the store's own E-V6 finder) and compares
  fingerprints -- N-15's mismatch test, in both storage modes (full
  content is fingerprinted here, E-V4; reference mode supplies the
  recorded fingerprint).
- AC2  Drift recorded against original Evidence: every detected drift
  appends an immutable DriftRecord naming the ORIGINAL object id, both
  fingerprints, and the disposition -- to the lock-guarded DriftRegister.
- AC3  Superseding version created where fidelity improves: when the
  caller explicitly declares improved fidelity, the original transitions
  to SUPERSEDED with a drift-citing reason (R-2/V9 -- the record on the
  original), which is exactly what makes the re-acquisition admissible
  under E-V6; the fresh acquisition (T02.2.1) then creates the superseding
  version. Without the explicit declaration nothing is superseded --
  the drift is NOTED and the original stands (fail-closed).

WHAT IS DELIBERATELY NOT IMPLEMENTED
-------------------------------------
- No fidelity ordering or scoring (none is ratified; the declaration is
  the caller's). No drift GATE: nothing ratified lets drift block
  acquisition -- detection is not adjudication. No duplicate logic
  (T02.2.2). No graph/lineage mutation: supersession is the sole
  permitted mutation, performed by the store's own transition path.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Iterator

from oip.contract import utc_now
from oip.evidence import compute_fingerprint
from oip.enums import ObjectStatus
from oip.store import KnowledgeStore

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DriftError(Exception):
    """Base class for drift-detection violations."""


class MaterialSpecError(DriftError):
    """Material was specified neither as content nor as a fingerprint."""


class NotDriftError(DriftError):
    """A drift record was demanded for unchanged material.

    Unchanged material on re-acquisition is a DUPLICATE (E-V6,
    oip/duplicates.py), not drift; conflating the two would blur the
    boundary T02.2.2 drew."""


# ---------------------------------------------------------------------------
# AC1 -- detection  [N-15: fingerprint mismatch on re-acquisition]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DriftVerdict:
    """What re-acquired material shows against the ACTIVE held Evidence."""

    holder_object_id: str
    source_identifier: str
    original_fingerprint: str
    reacquired_fingerprint: str

    @property
    def drifted(self) -> bool:
        """N-15's test verbatim: the fingerprints disagree."""
        return self.original_fingerprint != self.reacquired_fingerprint


def detect(
    store: KnowledgeStore,
    original_object_id: str,
    *,
    content: str | None = None,
    fingerprint: str | None = None,
) -> DriftVerdict:
    """Compare re-acquired material against a named ORIGINAL Evidence.

    [AC1, N-15] Drift is N-15's fingerprint mismatch on re-acquisition,
    measured against the Evidence the platform holds. The original is
    NAMED by the caller -- the re-acquirer knows which object it is
    re-capturing -- so detection needs no scan and no second index, and
    cannot blur into duplicate detection (T02.2.2): unchanged material
    reports drifted=False and is E-V6's domain, not this one. The
    original must resolve in the store (its provenance supplies the
    source identity; its retained fingerprint supplies the baseline --
    N-15 retains the fingerprint in every storage mode). Full content is
    fingerprinted here (E-V4); reference mode supplies the recorded
    fingerprint.
    """
    if content is None and fingerprint is None:
        raise MaterialSpecError(
            "specify the material: full content (fingerprinted here) or "
            "the recorded fingerprint [E-V4, N-15]"
        )
    if content is not None and fingerprint is not None:
        raise MaterialSpecError("specify content OR fingerprint, not both")
    evidence = store.evidence.get(original_object_id)
    if evidence is None:
        raise DriftError(
            f"original Evidence {original_object_id!r} does not resolve "
            f"[N-4]; drift is measured against held material"
        )
    new_fingerprint = (
        fingerprint
        if fingerprint is not None
        else compute_fingerprint(content)
    )
    return DriftVerdict(
        holder_object_id=original_object_id,
        source_identifier=evidence.provenance.source_identifier,
        original_fingerprint=evidence.content.fingerprint,
        reacquired_fingerprint=new_fingerprint,
    )


# ---------------------------------------------------------------------------
# AC2 -- the record  [N-10 pattern: operational, outside the object model]
# ---------------------------------------------------------------------------


class Disposition(str, Enum):
    """What the platform did about a detected drift."""

    NOTED = "NOTED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True)
class DriftRecord:
    """One detected drift, recorded against the ORIGINAL Evidence.

    A drift record requires a fingerprint MISMATCH: unchanged material
    belongs to duplicate detection (E-V6 / oip/duplicates.py)."""

    original_object_id: str
    source_identifier: str
    original_fingerprint: str
    reacquired_fingerprint: str
    detected_at: datetime
    disposition: Disposition

    def __post_init__(self) -> None:
        for name in (
            "original_object_id",
            "source_identifier",
            "original_fingerprint",
            "reacquired_fingerprint",
        ):
            if not (getattr(self, name) or "").strip():
                raise DriftError(f"{name} is required")
        if not isinstance(self.detected_at, datetime):
            raise DriftError("detected_at must be a datetime")
        if not isinstance(self.disposition, Disposition):
            raise DriftError(
                f"disposition {self.disposition!r} is outside the closed set"
            )
        if self.original_fingerprint == self.reacquired_fingerprint:
            raise NotDriftError(
                "unchanged material is a duplicate acquisition (E-V6, "
                "oip/duplicates.py), not drift [N-15: drift IS the mismatch]"
            )


@dataclass
class DriftRegister:
    """Append-only register of drift records. [N-10 -- outside the model]"""

    _records: list[DriftRecord] = field(default_factory=list, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def append(self, record: DriftRecord) -> DriftRecord:
        with self._lock:
            self._records.append(record)
        return record

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __iter__(self) -> Iterator[DriftRecord]:
        with self._lock:
            return iter(tuple(self._records))

    def against(self, original_object_id: str) -> tuple[DriftRecord, ...]:
        """Every drift recorded against one original Evidence. [AC2]"""
        with self._lock:
            return tuple(
                r
                for r in self._records
                if r.original_object_id == original_object_id
            )


# ---------------------------------------------------------------------------
# AC3 -- supersession where fidelity improves  [R-2, V9, E-V6 ACTIVE-only]
# ---------------------------------------------------------------------------


def record_drift(
    verdict: DriftVerdict,
    register: DriftRegister,
    store: KnowledgeStore | None = None,
    *,
    fidelity_improved: bool,
    clock=None,
) -> DriftRecord:
    """Record a detected drift and, on declared improvement, supersede.

    [AC2 + AC3] The record is appended unconditionally (a detected drift
    is a fact about the original Evidence). When -- and only when -- the
    caller EXPLICITLY declares that the re-captured material improves
    fidelity (no ratified fidelity ordering exists; IOM S 3.1 makes
    fidelity an assessment), the original transitions to SUPERSEDED with
    a drift-citing reason (R-2/V9: the sole permitted mutation, via the
    store's own transition path), which is exactly what makes the
    re-acquisition admissible under E-V6's ACTIVE-only duplicate index.
    Without the declaration the drift is NOTED and the original stands.
    """
    now = (clock or utc_now)()
    disposition = (
        Disposition.SUPERSEDED if fidelity_improved else Disposition.NOTED
    )
    record = DriftRecord(
        original_object_id=verdict.holder_object_id,
        source_identifier=verdict.source_identifier,
        original_fingerprint=verdict.original_fingerprint,
        reacquired_fingerprint=verdict.reacquired_fingerprint,
        detected_at=now,
        disposition=disposition,
    )
    register.append(record)
    if fidelity_improved:
        if store is None:
            raise DriftError(
                "supersession requires the store (the transition is the "
                "ratified mutation path [R-2, V9])"
            )
        store.transition(
            verdict.holder_object_id,
            ObjectStatus.SUPERSEDED,
            reason=(
                f"source drift detected; superseded by improved-fidelity "
                f"re-acquisition (fingerprint "
                f"{verdict.reacquired_fingerprint}) [T02.2.3 AC3, N-15]"
            ),
        )
    return record
