"""Universal object contract: the 17 required attributes.

Task: T01.1.2

Architecture References:
- AD-02 Intelligence Objects are the sole inter-engine contract
- R-1    Objects immutable; change produces a new version
- R-2    Seven-state lifecycle; status_reason required when not ACTIVE
- R-3    Two-component confidence; effective <= min(upstream)
- R-4    asserted_at / observed_at explicit; no automatic decay
- N-4    Reproducible inputs: engine_configuration_ref mandatory
- N-5    Tenancy discriminator reserved on every object
- N-7    Configuration referent; CI-1 isolation
- N-13   Explanation skeleton: four parts
- N-16   independent_source_count carried on every object (Tier 1)
- CI-1   Configuration is infrastructure state, never intelligence
- V1     All universal required attributes present and non-empty
- V8     observed_at <= asserted_at <= produced_at
- V9     status_reason present when status != ACTIVE
- IOM    sections 1.1, 1.2

Scope: structural contract only. Cross-object rules (V2-V5, V10-V12) require
the Store and Graph and are enforced on the acceptance path (T01.4.x).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from oip.enums import (
    ConfidenceBand,
    Engine,
    ObjectStatus,
    ObjectType,
)
from oip.identity import ObjectIdentity

# Reserved tenancy value while the platform is single-tenant. [N-5]
DEFAULT_TENANCY = "default"


class ContractError(Exception):
    """Base class for universal contract violations."""


class MissingAttributeError(ContractError):
    """A required attribute is absent or empty. [V1]"""


class TemporalOrderError(ContractError):
    """observed_at <= asserted_at <= produced_at violated. [V8]"""


class StatusReasonError(ContractError):
    """status_reason absent for a non-ACTIVE status. [V9]"""


class ConfidenceRangeError(ContractError):
    """A confidence component outside [0.0, 1.0]. [R-3]"""


class ConfidenceCeilingError(ContractError):
    """effective_confidence exceeds a component it may not. [R-3]"""


class ExplanationError(ContractError):
    """Explanation missing a required skeleton part. [N-13]"""


# ---------------------------------------------------------------------------
# Confidence [R-3]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Confidence:
    """Two orthogonal components plus the ceiling-constrained effective value.

    evidential_support  -- strength/breadth/independence of evidence
    assertion_confidence -- the engine's certainty in its own inference

    Kept separate so that "well-evidenced but low-confidence" and
    "poorly-evidenced but high-confidence" are both representable. [R-3]
    """

    evidential_support: float
    assertion_confidence: float
    effective_confidence: float

    def __post_init__(self) -> None:
        for name in (
            "evidential_support",
            "assertion_confidence",
            "effective_confidence",
        ):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise ConfidenceRangeError(f"{name} must be numeric, got {value!r}")
            if not 0.0 <= float(value) <= 1.0:
                raise ConfidenceRangeError(
                    f"{name} must be in [0.0, 1.0], got {value}"
                )
        # Effective may never exceed the engine's own asserted certainty, nor
        # the evidence beneath it. The upstream ceiling is applied separately
        # on the acceptance path, where lineage is resolvable. [R-3, V5]
        own_ceiling = min(self.evidential_support, self.assertion_confidence)
        if self.effective_confidence > own_ceiling + 1e-9:
            raise ConfidenceCeilingError(
                f"effective_confidence {self.effective_confidence} exceeds "
                f"min(evidential_support, assertion_confidence) = {own_ceiling}"
            )

    @property
    def band(self) -> ConfidenceBand:
        return ConfidenceBand.for_value(self.effective_confidence)

    @property
    def support_band(self) -> ConfidenceBand:
        return ConfidenceBand.for_value(self.evidential_support)

    @property
    def assertion_band(self) -> ConfidenceBand:
        return ConfidenceBand.for_value(self.assertion_confidence)

    @classmethod
    def create(
        cls,
        evidential_support: float,
        assertion_confidence: float,
        upstream_ceiling: float | None = None,
    ) -> "Confidence":
        """Build with effective_confidence derived by the ceiling rule. [R-3]"""
        effective = min(evidential_support, assertion_confidence)
        if upstream_ceiling is not None:
            effective = min(effective, upstream_ceiling)
        return cls(
            evidential_support=evidential_support,
            assertion_confidence=assertion_confidence,
            effective_confidence=effective,
        )


# ---------------------------------------------------------------------------
# Explanation [N-13]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Explanation:
    """Four-part explanation skeleton. [N-13, Article VIII]

    objects_referenced   structurally checkable -- must be non-empty and
                         resolve to the engine's actual inputs (V6)
    criteria_applied     structurally checkable -- non-empty
    reasoning            free text, non-empty
    alternatives_rejected required where the engine chose among candidates
    """

    objects_referenced: tuple[str, ...]
    criteria_applied: tuple[str, ...]
    reasoning: str
    alternatives_rejected: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.objects_referenced:
            raise ExplanationError(
                "explanation must reference at least one input object [V6]"
            )
        if not self.criteria_applied:
            raise ExplanationError("explanation must state criteria applied [N-13]")
        if not self.reasoning or not self.reasoning.strip():
            raise ExplanationError("explanation reasoning must be non-empty [N-13]")


# ---------------------------------------------------------------------------
# Lineage reference [R-1a]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LineageRef:
    """A version-specific reference to an upstream object. [R-1a, I3]

    Binds to object_id, which identifies one version. References never
    repoint to a newer version.
    """

    object_id: str
    object_type: ObjectType

    def __post_init__(self) -> None:
        if not self.object_id:
            raise MissingAttributeError("lineage reference requires an object_id")


# ---------------------------------------------------------------------------
# The universal contract
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class UniversalAttributes:
    """The 17 required attributes carried by every Intelligence Object.

    Frozen: content is immutable; change produces a new version. [R-1, I1]
    Status transition is the sole permitted mutation and is performed via
    with_status(), which returns a new instance. [R-2]
    """

    # Identity -- supplies object_id, lineage_id, version (3 of 17)
    identity: ObjectIdentity
    object_type: ObjectType

    # Provenance
    produced_by_engine: Engine
    produced_at: datetime
    engine_configuration_ref: str

    # Lineage and explanation
    derives_from: tuple[LineageRef, ...]
    explanation: Explanation
    evidence_reachable: bool

    # Confidence
    confidence: Confidence

    # Temporal
    asserted_at: datetime
    observed_at: datetime

    # Lifecycle
    status: ObjectStatus
    status_reason: str | None = None

    # Source diversity summary, Tier 1 [N-16]
    independent_source_count: int = 0

    # Reserved tenancy discriminator [N-5]
    tenancy: str = DEFAULT_TENANCY

    # Optional attributes [IOM section 1.2]
    valid_until: datetime | None = None
    duplicates: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    supersedes: str | None = None
    superseded_by: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    # -- validation -------------------------------------------------------

    def __post_init__(self) -> None:
        self._check_presence()
        self._check_temporal_order()
        self._check_status_reason()
        self._check_source_count()

    def _check_presence(self) -> None:
        """V1: all required attributes present and non-empty."""
        if not isinstance(self.identity, ObjectIdentity):
            raise MissingAttributeError("identity is required")
        if not isinstance(self.object_type, ObjectType):
            raise MissingAttributeError("object_type must be a known ObjectType")
        if not isinstance(self.produced_by_engine, Engine):
            raise MissingAttributeError("produced_by_engine must be a known Engine")
        if not self.engine_configuration_ref:
            raise MissingAttributeError(
                "engine_configuration_ref is required [N-4, N-7]"
            )
        if not isinstance(self.explanation, Explanation):
            raise MissingAttributeError("explanation is required [V6]")
        if not isinstance(self.confidence, Confidence):
            raise MissingAttributeError("confidence is required [R-3]")
        if not isinstance(self.evidence_reachable, bool):
            raise MissingAttributeError("evidence_reachable must be a boolean [U6]")
        if not self.tenancy:
            raise MissingAttributeError("tenancy discriminator is required [N-5]")
        for name in ("produced_at", "asserted_at", "observed_at"):
            if not isinstance(getattr(self, name), datetime):
                raise MissingAttributeError(f"{name} must be a datetime")

    def _check_temporal_order(self) -> None:
        """V8: observed_at <= asserted_at <= produced_at."""
        if self.observed_at > self.asserted_at:
            raise TemporalOrderError(
                f"observed_at ({self.observed_at}) must be <= "
                f"asserted_at ({self.asserted_at}) [V8]"
            )
        if self.asserted_at > self.produced_at:
            raise TemporalOrderError(
                f"asserted_at ({self.asserted_at}) must be <= "
                f"produced_at ({self.produced_at}) [V8]"
            )

    def _check_status_reason(self) -> None:
        """V9: status_reason required for every non-ACTIVE status."""
        if self.status.requires_reason:
            if not self.status_reason or not self.status_reason.strip():
                raise StatusReasonError(
                    f"status_reason is required when status is "
                    f"{self.status.value} [V9]"
                )

    def _check_source_count(self) -> None:
        if self.independent_source_count < 0:
            raise ContractError(
                "independent_source_count must be non-negative [N-16]"
            )

    # -- derived ----------------------------------------------------------

    @property
    def object_id(self) -> str:
        return self.identity.object_id

    @property
    def lineage_id(self) -> str:
        return self.identity.lineage_id

    @property
    def version(self) -> int:
        return self.identity.version

    @property
    def is_root(self) -> bool:
        """Evidence is the only type with no upstream lineage. [E-V1]"""
        return self.object_type.is_root

    # -- controlled transition -------------------------------------------

    def with_status(
        self, status: ObjectStatus, reason: str | None = None
    ) -> "UniversalAttributes":
        """Return a copy with a new status. [R-2]

        The sole permitted non-versioning mutation. Content is unchanged;
        a new instance is returned rather than mutating in place. [I1]
        """
        if self.status.is_terminal:
            raise ContractError(
                f"status {self.status.value} is terminal and cannot transition [R-2]"
            )
        return replace(self, status=status, status_reason=reason)

    # -- serialisation ----------------------------------------------------

    def to_mapping(self) -> Mapping[str, Any]:
        """Flat view of the 17 required attributes, for inspection and tests."""
        return {
            "object_id": self.object_id,
            "object_type": self.object_type.value,
            "version": self.version,
            "lineage_id": self.lineage_id,
            "produced_by_engine": self.produced_by_engine.value,
            "produced_at": self.produced_at,
            "engine_configuration_ref": self.engine_configuration_ref,
            "derives_from": tuple(r.object_id for r in self.derives_from),
            "explanation": self.explanation,
            "evidence_reachable": self.evidence_reachable,
            "evidential_support": self.confidence.evidential_support,
            "assertion_confidence": self.confidence.assertion_confidence,
            "effective_confidence": self.confidence.effective_confidence,
            "asserted_at": self.asserted_at,
            "observed_at": self.observed_at,
            "status": self.status.value,
            "status_reason": self.status_reason,
        }


REQUIRED_ATTRIBUTE_NAMES: tuple[str, ...] = (
    "object_id",
    "object_type",
    "version",
    "lineage_id",
    "produced_by_engine",
    "produced_at",
    "engine_configuration_ref",
    "derives_from",
    "explanation",
    "evidence_reachable",
    "evidential_support",
    "assertion_confidence",
    "effective_confidence",
    "asserted_at",
    "observed_at",
    "status",
    "status_reason",
)
assert len(REQUIRED_ATTRIBUTE_NAMES) == 17, "IOM section 1.1 defines 17 attributes"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
