"""Duplicate detection: re-acquisition detectable, duplicate rate measurable.

Task: T02.2.2

Architecture References:
- E-V6    "No ACTIVE Evidence shares content_fingerprint +
          source_identifier" (oip/evidence.py; enforced at acceptance since
          P1). This task makes the duplicate outcome CLASSIFIED at the
          acquisition boundary, exposes detection as a first-class surface,
          and makes the rate measurable from recorded outcomes.
- N-03    Stage-1 proxy measures: "Provenance completeness; duplicate
          rate; source-type coverage". N-03 names the measure; it does not
          ratify a formula for it. This module therefore exposes the
          INGREDIENTS (counts, exact-key lookup) and pure arithmetic --
          the composition the caller reports is theirs, and NO default
          rate is ever invented (an attempt-less history reports None).
- IOM     The optional `duplicates` attribute ("recognised equivalents not
          merged", populated "on detection") is an annotation about an
          object, not a change to it. This module detects; it never merges
          and never annotates -- cross-source same-fingerprint material is
          CORROBORATION, not duplication, because the E-V6 key includes
          the source.
- N-10    Duplicate refusals are recorded in the AcquisitionLog under
          their own stage (DUPLICATE_ACQUISITION), so "refused as a
          duplicate" is always distinguishable from other failures.
- N-15    Reference-mode material is fingerprinted by the acquirer; the
          fingerprint is always retained, so detection works identically
          in FULL and REFERENCE modes.

WHAT IS IMPLEMENTED (the three T02.2.2 acceptance criteria)
------------------------------------------------------------
- AC1  Same fingerprint plus source rejected: E-V6 refuses it at
  acceptance (P1), and the acquisition boundary now classifies such
  refusals as DUPLICATE_ACQUISITION with the E-V6 reason, instead of a
  generic store rejection.
- AC2  Re-acquisition detectable: `held_duplicate` resolves, for a source
  and material (full content or explicit fingerprint), the ACTIVE
  Evidence object already holding it -- or None for genuinely new
  material. Only ACTIVE Evidence blocks re-acquisition; retracted
  material may legitimately be acquired again (E-V6's own semantics).
- AC3  Duplicate rate measurable: `duplicate_refusals` counts the
  classified refusals, and `duplicate_rate` is pure, fail-closed
  arithmetic over caller-supplied counts. Zero attempts report None --
  never 0.0, never 1.0 (the same honesty rule coverage applies).

WHAT IS DELIBERATELY NOT IMPLEMENTED
-------------------------------------
- No ratified formula for "duplicate rate" exists in the corpus; none is
  invented here. No merging (the `duplicates` annotation is an
  object-owner's act, not acquisition's). No cross-source matching: the
  E-V6 key is (fingerprint, source) and stays exactly that. No drift
  analysis -- changed content at the same source is T02.2.3.
"""

from __future__ import annotations

from oip.acquisition import AcquisitionLog, AcquisitionStage
from oip.evidence import compute_fingerprint
from oip.store import KnowledgeStore

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class DuplicateError(Exception):
    """Base class for duplicate-detection violations."""


class MaterialSpecError(DuplicateError):
    """Material was specified neither as content nor as a fingerprint."""


# ---------------------------------------------------------------------------
# AC2 -- detection  [E-V6 key: (fingerprint, source_identifier)]
# ---------------------------------------------------------------------------


def held_duplicate(
    store: KnowledgeStore,
    source_identifier: str,
    *,
    content: str | None = None,
    fingerprint: str | None = None,
) -> str | None:
    """The ACTIVE Evidence already holding this material from this source.

    [E-V6, AC2] The lookup key is exactly the E-V6 key: content
    fingerprint plus source identifier. Full content is fingerprinted
    here (deterministic, E-V4); reference-mode material supplies the
    fingerprint the acquirer recorded (N-15 retains it in every mode).

    Returns the holding object's id, or None when the material is new.
    Cross-source same-fingerprint material is NOT a duplicate: it is
    independent corroboration, and the source is part of the key. Only
    ACTIVE Evidence blocks re-acquisition (E-V6): retracted material may
    be legitimately acquired again.
    """
    if content is None and fingerprint is None:
        raise MaterialSpecError(
            "specify the material: full content (fingerprinted here) or "
            "the recorded fingerprint [E-V4, N-15]"
        )
    if content is not None and fingerprint is not None:
        raise MaterialSpecError(
            "specify content OR fingerprint, not both"
        )
    key_fingerprint = (
        fingerprint if fingerprint is not None else compute_fingerprint(content)
    )
    return store.evidence.find_duplicate(
        (key_fingerprint, source_identifier)
    )


# ---------------------------------------------------------------------------
# AC3 -- measurement  [N-03 names the measure; no formula is invented]
# ---------------------------------------------------------------------------


def duplicate_refusals(log: AcquisitionLog) -> int:
    """How many acquisition attempts were refused as duplicates. [N-10]

    Counts the DUPLICATE_ACQUISITION stage in the log -- the classified
    E-V6 outcome -- so the numerator of any duplicate-rate report is a
    recorded fact, never a recollection.
    """
    return sum(
        1 for failure in log if failure.stage is AcquisitionStage.DUPLICATE_ACQUISITION
    )


def duplicate_rate(duplicates: int, attempts: int) -> float | None:
    """The duplicate share of acquisition attempts. Pure arithmetic.

    N-03 names "duplicate rate" as a stage-1 proxy measure but ratifies
    no formula; this function performs the division the caller's report
    needs and refuses to invent a value for an empty history: zero
    attempts report None -- undefined, never defaulted to 0 or 1 (the
    same fail-closed rule N-22 S 5.7 applies to coverage).
    """
    if attempts < 0 or duplicates < 0:
        raise DuplicateError("counts must be non-negative")
    if duplicates > attempts:
        raise DuplicateError(
            f"{duplicates} duplicate refusals cannot exceed {attempts} "
            f"attempts"
        )
    if attempts == 0:
        return None
    return duplicates / attempts
