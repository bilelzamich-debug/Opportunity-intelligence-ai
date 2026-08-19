"""Evidence object type: the platform's grounding layer.

Task: T01.7.1

Architecture References:
- E-V1   derives_from is empty -- the defining restriction
- E-V2   source_identifier and acquired_at present
- E-V3   content or content_reference present
- E-V4   content_fingerprint present and computed from actual content
- E-V5   observed_at <= acquired_at
- E-V6   No ACTIVE Evidence shares content_fingerprint + source_identifier
- E-I1   Content never altered after acceptance
- E-I2   Never derives from any platform-internal object
- E-I3   Provenance never removed
- E-I4   Retraction cascades to all dependents
- AD-05  Ground Truth Protection: no platform artifact may become Evidence
- R-2    Evidence cannot reach INVALIDATED (no upstream to invalidate it)
- R-3    Evidence sets the ceiling; nothing constrains it from above
- N-15   Hybrid storage: full content where licensing permits, else reference
- N-16   independent_source_count -- Evidence contributes exactly one source
- Art.IV Evidence must always originate from external reality

Evidence is the only object type with no upstream lineage, and that property
is definitional: it is what makes every lineage trace terminate, and what
makes grounding mean anything. E-I2 is the enforcement point for AD-05 --
under it, feedback can never become Evidence, only trigger new acquisition.

Scope: the Evidence type and its rules. Acquisition itself is the Research
Engine (T02.2.1); this module defines what an acquired object must look like.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType

# Evidence contributes exactly one independent source by definition. [N-16]
EVIDENCE_SOURCE_COUNT = 1


class EvidenceError(Exception):
    """Base class for Evidence violations."""


class ProvenanceError(EvidenceError):
    """Required provenance is absent or incomplete. [E-V2, E-I3]"""


class ContentError(EvidenceError):
    """Neither content nor a resolvable reference is present. [E-V3]"""


class FingerprintError(EvidenceError):
    """Fingerprint absent or inconsistent with the content. [E-V4]"""


class ExternalOriginError(EvidenceError):
    """Evidence derived from a platform-internal object. [E-I2, AD-05]"""


class StorageMode(str, Enum):
    """How the acquired material is held. [N-15, OQ-12]"""

    FULL = "FULL"            # content retained in the store
    REFERENCE = "REFERENCE"  # external reference only; exposed to source drift


@dataclass(frozen=True)
class Provenance:
    """Origin record for acquired material. [E-V2, E-I3]

    Frozen: provenance is never removed or edited after acceptance. Without
    it, Evidence cannot be trusted or re-verified, and Principle 3 fails at
    the root.
    """

    source_identifier: str
    source_type: str
    acquisition_method: str
    acquired_at: datetime
    access_conditions: str
    capture_fidelity: str

    # Optional provenance. [IOM section 3.1]
    source_reliability: float | None = None
    publication_date: datetime | None = None
    author_identifier: str | None = None
    source_independence_group: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "source_identifier",
            "source_type",
            "acquisition_method",
            "access_conditions",
            "capture_fidelity",
        ):
            if not (getattr(self, name) or "").strip():
                raise ProvenanceError(f"{name} is required [E-V2, E-I3]")
        if not isinstance(self.acquired_at, datetime):
            raise ProvenanceError("acquired_at must be a datetime [E-V2]")
        if self.source_reliability is not None:
            if not 0.0 <= self.source_reliability <= 1.0:
                raise ProvenanceError(
                    "source_reliability must be in [0.0, 1.0] [OQ-28]"
                )

    @property
    def independence_key(self) -> str:
        """Key on which source independence is assessed. [N-16, M-23]

        Sources sharing an independence group count once, so syndicated
        copies cannot inflate corroboration.

        Explicit-input model [T02.1.3 interpretation, 2026-08-19]:
        ``source_independence_group`` is carried and honoured when supplied.
        No syndication, ownership or independence inference is performed;
        any inference requires an explicit ratified rule, and none exists.
        """
        return self.source_independence_group or self.source_identifier


def compute_fingerprint(content: str | bytes) -> str:
    """Stable content fingerprint. [E-V4]

    Enables duplicate detection (E-V6) and source-drift detection on
    re-acquisition. Deterministic: identical content always fingerprints
    identically, which is what makes E-V6 checkable.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


@dataclass(frozen=True)
class EvidenceContent:
    """Acquired material, held in full or by reference. [N-15, E-V3, E-V4]"""

    fingerprint: str
    storage_mode: StorageMode
    content: str | None = None
    content_reference: str | None = None

    def __post_init__(self) -> None:
        if not (self.fingerprint or "").strip():
            raise FingerprintError("content_fingerprint is required [E-V4]")

        if self.storage_mode is StorageMode.FULL:
            if self.content is None:
                raise ContentError(
                    "FULL storage requires content to be present [E-V3, N-15]"
                )
            expected = compute_fingerprint(self.content)
            if self.fingerprint != expected:
                raise FingerprintError(
                    f"fingerprint does not match content: expected {expected}, "
                    f"got {self.fingerprint} [E-V4]"
                )
        else:
            if not (self.content_reference or "").strip():
                raise ContentError(
                    "REFERENCE storage requires a content_reference "
                    "[E-V3, N-15]"
                )

    @property
    def is_verifiable_in_place(self) -> bool:
        """Whether the material can be re-read without an external system.

        Reference-only Evidence carries a recorded exposure to source drift:
        the source may change or disappear, leaving lineage pointing at
        something no longer checkable. [N-15]
        """
        return self.storage_mode is StorageMode.FULL

    @classmethod
    def full(cls, content: str) -> "EvidenceContent":
        return cls(
            fingerprint=compute_fingerprint(content),
            storage_mode=StorageMode.FULL,
            content=content,
        )

    @classmethod
    def by_reference(cls, reference: str, fingerprint: str) -> "EvidenceContent":
        return cls(
            fingerprint=fingerprint,
            storage_mode=StorageMode.REFERENCE,
            content_reference=reference,
        )


@dataclass(frozen=True)
class Evidence:
    """A record of source material acquired from outside the platform.

    Composes the universal contract with Evidence-specific provenance and
    content. Frozen throughout: content is never altered after acceptance,
    and provenance is never removed. [E-I1, E-I3, I1]
    """

    attributes: UniversalAttributes
    provenance: Provenance
    content: EvidenceContent

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.EVIDENCE:
            raise EvidenceError(
                f"expected Evidence, got {self.attributes.object_type.value}"
            )
        # E-V1 / E-I2: the defining restriction, checked at construction so an
        # Evidence object with lineage cannot exist even transiently.
        if self.attributes.derives_from:
            raise ExternalOriginError(
                f"Evidence {self.attributes.object_id!r} may not derive from "
                f"anything; Evidence originates from external reality only "
                f"[E-V1, E-I2, AD-05, Article IV]"
            )
        if self.attributes.produced_by_engine is not Engine.RESEARCH:
            raise EvidenceError(
                f"only the Research Engine may create Evidence; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )
        if self.attributes.observed_at > self.provenance.acquired_at:
            raise ProvenanceError(
                f"observed_at ({self.attributes.observed_at.isoformat()}) must "
                f"be <= acquired_at "
                f"({self.provenance.acquired_at.isoformat()}) [E-V5]"
            )

    # -- delegated identity ----------------------------------------------

    @property
    def object_id(self) -> str:
        return self.attributes.object_id

    @property
    def lineage_id(self) -> str:
        return self.attributes.lineage_id

    @property
    def status(self) -> ObjectStatus:
        return self.attributes.status

    @property
    def fingerprint(self) -> str:
        return self.content.fingerprint

    @property
    def source_identifier(self) -> str:
        return self.provenance.source_identifier

    @property
    def duplicate_key(self) -> tuple[str, str]:
        """Key on which duplicate acquisition is detected. [E-V6]"""
        return (self.content.fingerprint, self.provenance.source_identifier)

    @property
    def independence_key(self) -> str:
        return self.provenance.independence_key

    @property
    def is_root(self) -> bool:
        """Always True. Evidence terminates every lineage trace. [E-V1]"""
        return True

    def drifted_from(self, reacquired_fingerprint: str) -> bool:
        """Whether the source has changed since acquisition. [N-15]"""
        return self.content.fingerprint != reacquired_fingerprint


# ---------------------------------------------------------------------------
# Evidence-specific acceptance rules  [E-V1 .. E-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _evidence_of(ctx: AcceptanceContext) -> "Evidence | None":
    return getattr(ctx, "evidence", None)


def ev1_no_upstream_lineage(ctx: AcceptanceContext) -> RuleResult:
    """derives_from is empty. [E-V1, E-I2, AD-05]"""
    attributes = ctx.attributes
    if attributes.object_type is not ObjectType.EVIDENCE:
        return _skip("E-V1", "not an Evidence object")
    if attributes.derives_from:
        return _fail(
            "E-V1",
            f"Evidence declares {len(attributes.derives_from)} upstream "
            f"reference(s); Evidence originates from external reality only "
            f"[AD-05, Article IV]",
        )
    return _ok("E-V1", "no upstream lineage; grounding preserved")


def ev2_provenance_present(ctx: AcceptanceContext) -> RuleResult:
    """source_identifier and acquired_at present. [E-V2]"""
    if ctx.attributes.object_type is not ObjectType.EVIDENCE:
        return _skip("E-V2", "not an Evidence object")
    evidence = _evidence_of(ctx)
    if evidence is None:
        return _skip("E-V2", "no Evidence payload supplied")
    provenance = evidence.provenance
    missing = [
        name
        for name in ("source_identifier", "acquisition_method", "access_conditions")
        if not (getattr(provenance, name) or "").strip()
    ]
    if missing:
        return _fail("E-V2", f"provenance incomplete: {sorted(missing)}")
    return _ok("E-V2", "provenance complete")


def ev3_content_present(ctx: AcceptanceContext) -> RuleResult:
    """content or content_reference present. [E-V3, N-15]"""
    if ctx.attributes.object_type is not ObjectType.EVIDENCE:
        return _skip("E-V3", "not an Evidence object")
    evidence = _evidence_of(ctx)
    if evidence is None:
        return _skip("E-V3", "no Evidence payload supplied")
    body = evidence.content
    if body.content is None and not (body.content_reference or "").strip():
        return _fail("E-V3", "neither content nor content_reference is present")
    return _ok("E-V3", f"content held as {body.storage_mode.value}")


def ev4_fingerprint_matches(ctx: AcceptanceContext) -> RuleResult:
    """content_fingerprint present and computed from actual content. [E-V4]"""
    if ctx.attributes.object_type is not ObjectType.EVIDENCE:
        return _skip("E-V4", "not an Evidence object")
    evidence = _evidence_of(ctx)
    if evidence is None:
        return _skip("E-V4", "no Evidence payload supplied")
    body = evidence.content
    if not (body.fingerprint or "").strip():
        return _fail("E-V4", "content_fingerprint is absent")
    if body.storage_mode is StorageMode.FULL:
        expected = compute_fingerprint(body.content or "")
        if body.fingerprint != expected:
            return _fail(
                "E-V4",
                f"fingerprint {body.fingerprint} does not match the stored "
                f"content (expected {expected})",
            )
        return _ok("E-V4", "fingerprint verified against content")
    # Reference-only material cannot be re-fingerprinted in place. [N-15]
    return _ok("E-V4", "fingerprint recorded; content held by reference [N-15]")


def ev5_observed_before_acquired(ctx: AcceptanceContext) -> RuleResult:
    """observed_at <= acquired_at. [E-V5]"""
    if ctx.attributes.object_type is not ObjectType.EVIDENCE:
        return _skip("E-V5", "not an Evidence object")
    evidence = _evidence_of(ctx)
    if evidence is None:
        return _skip("E-V5", "no Evidence payload supplied")
    observed = ctx.attributes.observed_at
    acquired = evidence.provenance.acquired_at
    if (observed.tzinfo is None) != (acquired.tzinfo is None):
        return _fail(
            "E-V5", "observed_at and acquired_at mix timezone-aware and naive"
        )
    if observed > acquired:
        return _fail(
            "E-V5",
            f"observed_at ({observed.isoformat()}) is after acquired_at "
            f"({acquired.isoformat()}); reality cannot be observed after it "
            f"was captured",
        )
    return _ok("E-V5", "observation precedes acquisition")


def ev6_no_duplicate_acquisition(ctx: AcceptanceContext) -> RuleResult:
    """No ACTIVE Evidence shares fingerprint + source_identifier. [E-V6]

    Silent duplication is the most damaging failure at the Evidence stage: it
    inflates every downstream frequency signal while passing every other
    check. Re-acquiring the same material from the same source is not new
    evidence.
    """
    if ctx.attributes.object_type is not ObjectType.EVIDENCE:
        return _skip("E-V6", "not an Evidence object")
    evidence = _evidence_of(ctx)
    if evidence is None:
        return _skip("E-V6", "no Evidence payload supplied")
    finder = getattr(ctx, "find_duplicate_evidence", None)
    if finder is None:
        return _skip("E-V6", "no duplicate provider supplied")

    existing = finder(evidence.duplicate_key)
    if existing is not None and existing != evidence.object_id:
        return _fail(
            "E-V6",
            f"duplicate acquisition: ACTIVE Evidence {existing!r} already "
            f"holds fingerprint {evidence.fingerprint} from source "
            f"{evidence.source_identifier!r}",
        )
    return _ok("E-V6", "no duplicate acquisition")


ev1_no_upstream_lineage.rule_id = "E-V1"       # type: ignore[attr-defined]
ev2_provenance_present.rule_id = "E-V2"        # type: ignore[attr-defined]
ev3_content_present.rule_id = "E-V3"           # type: ignore[attr-defined]
ev4_fingerprint_matches.rule_id = "E-V4"       # type: ignore[attr-defined]
ev5_observed_before_acquired.rule_id = "E-V5"  # type: ignore[attr-defined]
ev6_no_duplicate_acquisition.rule_id = "E-V6"  # type: ignore[attr-defined]

EVIDENCE_RULES = (
    ev1_no_upstream_lineage,
    ev2_provenance_present,
    ev3_content_present,
    ev4_fingerprint_matches,
    ev5_observed_before_acquired,
    ev6_no_duplicate_acquisition,
)


# ---------------------------------------------------------------------------
# Evidence-specific integrity constraints  [E-I1 .. E-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceViolation:
    """A breached Evidence integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class EvidenceIntegrity:
    """Continuous verification of E-I1..E-I4. [IOM section 3.1]

    Detective, mirroring the universal verifier: these can be breached by
    paths no single write controls.
    """

    evidence_of: Callable[[str], "Evidence | None"]
    store: "object"

    def verify(self) -> tuple[EvidenceViolation, ...]:
        violations: list[EvidenceViolation] = []
        violations.extend(self._check_ei1())
        violations.extend(self._check_ei2())
        violations.extend(self._check_ei3())
        violations.extend(self._check_ei4())
        return tuple(violations)

    def _all_evidence(self) -> Iterable[tuple[str, "Evidence"]]:
        for stored in self.store.objects_of_type(ObjectType.EVIDENCE):
            evidence = self.evidence_of(stored.object_id)
            if evidence is not None:
                yield stored.object_id, evidence

    def _check_ei1(self) -> list[EvidenceViolation]:
        """Content never altered after acceptance. [E-I1]"""
        violations: list[EvidenceViolation] = []
        for object_id, evidence in self._all_evidence():
            body = evidence.content
            if body.storage_mode is not StorageMode.FULL:
                continue
            actual = compute_fingerprint(body.content or "")
            if actual != body.fingerprint:
                violations.append(
                    EvidenceViolation(
                        "E-I1", object_id,
                        f"content altered after acceptance: fingerprint "
                        f"{body.fingerprint} no longer matches {actual}",
                    )
                )
        return violations

    def _check_ei2(self) -> list[EvidenceViolation]:
        """Never derives from any platform-internal object. [E-I2, AD-05]"""
        violations: list[EvidenceViolation] = []
        for stored in self.store.objects_of_type(ObjectType.EVIDENCE):
            if stored.attributes.derives_from or stored.lineage.references:
                violations.append(
                    EvidenceViolation(
                        "E-I2", stored.object_id,
                        "Evidence derives from a platform-internal object; "
                        "grounding is compromised [AD-05, Article IV]",
                    )
                )
        return violations

    def _check_ei3(self) -> list[EvidenceViolation]:
        """Provenance never removed. [E-I3]"""
        violations: list[EvidenceViolation] = []
        for object_id, evidence in self._all_evidence():
            provenance = evidence.provenance
            missing = [
                name
                for name in (
                    "source_identifier", "source_type", "acquisition_method",
                    "access_conditions", "capture_fidelity",
                )
                if not (getattr(provenance, name) or "").strip()
            ]
            if missing:
                violations.append(
                    EvidenceViolation(
                        "E-I3", object_id,
                        f"provenance removed: {sorted(missing)}",
                    )
                )
        return violations

    def _check_ei4(self) -> list[EvidenceViolation]:
        """Retraction cascades to all dependents. [E-I4, I6]"""
        violations: list[EvidenceViolation] = []
        for stored in self.store.objects_of_type(ObjectType.EVIDENCE):
            if stored.status is not ObjectStatus.RETRACTED:
                continue
            for dependent_id in self.store.graph.descendants(stored.object_id):
                dependent = self.store.find(dependent_id)
                if dependent is not None and dependent.status is ObjectStatus.ACTIVE:
                    violations.append(
                        EvidenceViolation(
                            "E-I4", stored.object_id,
                            f"retracted, but dependent {dependent_id!r} is "
                            f"still ACTIVE; cascade did not complete",
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Registry: duplicate detection and payload resolution
# ---------------------------------------------------------------------------

@dataclass
class EvidenceRegistry:
    """Holds Evidence payloads and answers duplicate queries. [E-V6]

    The universal contract carries identity, confidence and status; the
    Evidence payload carries provenance and content. This registry keeps the
    two associated without widening UniversalAttributes, which is the
    platform's contract surface for all nine types.
    """

    store: "object"
    _payloads: dict[str, Evidence] = field(default_factory=dict, init=False)
    _by_duplicate_key: dict[tuple[str, str], str] = field(
        default_factory=dict, init=False
    )

    def register(self, evidence: Evidence) -> Evidence:
        self._payloads[evidence.object_id] = evidence
        self._by_duplicate_key[evidence.duplicate_key] = evidence.object_id
        return evidence

    def get(self, object_id: str) -> Evidence | None:
        return self._payloads.get(object_id)

    def find_duplicate(self, key: tuple[str, str]) -> str | None:
        """Return the ACTIVE Evidence holding this key, if any. [E-V6]

        Only ACTIVE Evidence blocks re-acquisition: material previously
        retracted or rejected may legitimately be acquired again.
        """
        object_id = self._by_duplicate_key.get(key)
        if object_id is None:
            return None
        stored = self.store.find(object_id)
        if stored is None or stored.status is not ObjectStatus.ACTIVE:
            return None
        return object_id

    def independent_sources(self) -> frozenset[str]:
        """Distinct independence keys across ACTIVE Evidence. [N-16, M-23]"""
        keys: set[str] = set()
        for object_id, evidence in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                keys.add(evidence.independence_key)
        return frozenset(keys)

    def integrity(self) -> EvidenceIntegrity:
        return EvidenceIntegrity(evidence_of=self.get, store=self.store)

    def __len__(self) -> int:
        return len(self._payloads)
