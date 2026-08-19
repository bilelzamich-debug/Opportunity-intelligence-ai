"""Source model: registry, eligibility gate and trust representation.

Task: T02.1.1

Architecture References:
- M-16   Source taxonomy, eligibility, trust model. **PARTIALLY CLOSED by
         N-20 (RATIFIED 2026-08-04):** taxonomy (S 5.1), eligibility (S 5.2),
         trust representation (S 5.3). The scoring half stays OPEN -- making
         trust score requires superseding S-02. Subsumes OQ-28 per
         marker-crosswalk section 5 (closed with N-20 S 5.3).
- S-02   evidential_support has FIVE EXHAUSTIVE inputs -- "No other input."
         Source trust is NOT among them. Trust recorded here therefore does
         NOT score, and this module exposes no path by which it could.
- S-02   Input 2 is "source diversity -- number of distinct source *types*
         represented", which already depends on a taxonomy M-16 has not
         supplied. That dependency is surfaced, never guessed.
- N-16   Two-tier propagation; independence assessed on a grouping key.
         Evidence contributes exactly one source.
- N-04   Reproducible inputs: anything an engine reads must resolve at any
         historical point. The registry is therefore append-only and
         versioned, exactly as ConfigurationStore is.
- N-07   Configuration is a scoped store, colocated but logically isolated.
- CI-1   "Configuration data is infrastructure state, not intelligence...
         must never participate in reasoning, scoring, pattern detection, or
         lineage." This module holds no Intelligence Object, returns none,
         and exposes no path into a lineage graph.
- AD-01  Evidence-first: grounding derives from external reality.
- AD-05  Ground Truth Protection: no platform artifact may become Evidence.
         A trust rating is metadata ABOUT a source, never Evidence itself.
- R-01   Immutable, versioned records.
- IOM 3.1 Evidence provenance: `source_type` "(MISSING-18: no taxonomy
         exists)"; `source_reliability` optional "(OPEN QUESTION-28)".
- M-18   Legal, licensing, rate-limit, terms-of-use policy. OPEN, and owned
         by T02.1.2 -- deliberately NOT implemented here.
- M-02   What the platform learns -- the target of change. OPEN.
- M-43   Feedback Engine write target. OPEN.

WHAT IS RATIFIED, AND THEREFORE IMPLEMENTED
-------------------------------------------
1. Sources are identified by `source_identifier` -- IOM 3.1 requires it and
   describes it as "sufficient to assess independence".
2. Independence is assessed on `source_independence_group` falling back to
   `source_identifier` -- already ratified and implemented at
   `Provenance.independence_key` (N-16, T01.7.1). Reused, not redefined.
3. Trust, where recorded, is a float in [0.0, 1.0] -- this is the range the
   RATIFIED Evidence contract already enforces on `source_reliability`
   (oip/evidence.py, IOM 3.1 / OQ-28). No new scale is invented; the existing
   one is honoured.
4. Records are immutable and versioned, so a historical read reproduces
   (N-04, R-01), mirroring ConfigurationStore.
5. Trust does not participate in scoring (S-02's exhaustive input list).

WHAT IS **NOT** RATIFIED, AND THEREFORE FAILS CLOSED
----------------------------------------------------
N-20 (RATIFIED 2026-08-04) supplies the taxonomy: the closed eight-member
set of section 5.1 is enumerated verbatim below. Extension requires a
superseding decision record; inline addition is prohibited (N-20 S 5.1,
C17). Accordingly:

* `SourceType` is a POPULATED closed vocabulary -- exactly the eight N-20
  S 5.1 members, nothing else. `classify` maps a raw string onto the
  taxonomy and raises `UntypableChannelError` for anything outside it:
  under N-20 S 5.2 an untypable channel is INELIGIBLE (UNTYPABLE_CHANNEL,
  gate 2 of S 5.2.1).
* `SourceEligibility` from an identifier ALONE remains UNDETERMINED:
  eligibility under M-16 IS typability (N-20 S 5.2), and typability is
  decided on the channel type the Research Engine assigns at acquisition
  (N-20 S 5.1; the acquisition path is T02.2.1, not yet built).
  `assess_eligibility` therefore still returns UNDETERMINED and
  `require_eligible` still raises. Nothing is admitted by default; nothing
  is rejected by invented rule.
* Trust is RECORDED but never DEFAULTED. An unrated source reports `None`,
  never a neutral value: "all sources weigh equally" is described by the IOM
  as a "strong unstated assumption" and by v2 as the defect M-16 exists to
  correct. Materialising it as a default would encode the flaw as policy.
* Learnability (backlog AC3) is NOT implemented. The learning-target set is
  M-02 and the write authority is M-43, both OPEN. `LEARNING_TARGET_STATUS`
  reports the gap; no learning interface exists.

This module therefore provides the STRUCTURE M-16 will populate, and refuses
to supply the CONTENT M-16 alone can supply. Every refusal names its marker.
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


class SourceError(Exception):
    """Base class for source-model violations."""


class UntypableChannelError(SourceError):
    """The raw source_type maps onto no ratified taxonomy member.

    [N-20 S 5.2: an untypable channel is INELIGIBLE; UNTYPABLE_CHANNEL,
    gate 2 of the S 5.2.1 acquisition sequence]
    """


class EligibilityNotRatifiedError(SourceError):
    """Eligibility cannot be decided from an identifier alone; the channel
    type is assigned at acquisition. [N-20 S 5.1-S 5.2]"""


class SourceNotFoundError(SourceError):
    """A source_identifier does not resolve in the registry. [N-4]"""


class SourceImmutableError(SourceError):
    """An attempt was made to rewrite an immutable record. [R-1]"""


class TrustNotRatifiedError(SourceError):
    """Trust semantics beyond plain recording are undefined. [M-16]"""


class LearningTargetNotRatifiedError(SourceError):
    """Source trust is not a ratified learning target. [M-02, M-43]"""


# ---------------------------------------------------------------------------
# Taxonomy  [AC1 -- populated exactly from N-20 S 5.1]
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """The closed source-type taxonomy, by acquisition channel. [N-20 S 5.1]

    Closed vocabularies in this platform are enumerated by a ratified
    decision, never inline -- R-2's seven states, R-6's ten relationship
    types, R-3's five bands. **N-20 (RATIFIED 2026-08-04) is the decision
    that enumerates this one.** The eight members, their names and their
    order below are N-20 S 5.1 verbatim; extension requires a superseding
    decision record and inline addition is prohibited (N-20 S 5.1, C17).

    Exactly one member applies per source: a source reachable through more
    than one channel is typed by the channel actually used at acquisition.
    The Research Engine assigns `source_type` at acquisition (N-20 S 5.1).
    """

    # Material published by an identified editorial body.
    PUBLISHED_EDITORIAL = "PUBLISHED_EDITORIAL"
    # Listings, catalogue or transactional records from a marketplace.
    MARKETPLACE_LISTING = "MARKETPLACE_LISTING"
    # Reviews or ratings authored by end users.
    USER_GENERATED_REVIEW = "USER_GENERATED_REVIEW"
    # Forum, community or discussion-thread material.
    USER_GENERATED_DISCUSSION = "USER_GENERATED_DISCUSSION"
    # Complaint, support-ticket or service-transcript material.
    SUPPORT_INTERACTION = "SUPPORT_INTERACTION"
    # Datasets published as data, including public and licensed corpora.
    STRUCTURED_DATASET = "STRUCTURED_DATASET"
    # Filings or disclosures lodged with a regulatory body.
    REGULATORY_FILING = "REGULATORY_FILING"
    # Material published by a vendor about its own offering.
    VENDOR_PUBLICATION = "VENDOR_PUBLICATION"


_TAXONOMY_NAMES: frozenset[str] = frozenset(
    member.value for member in SourceType
)
"""The ratified member names as raw strings, for exact-value membership.

Raw acquisition strings are compared by VALUE, never coerced: a typo must
fail closed as untypable, not silently register as a distinct type."""


TAXONOMY_RATIFIED: bool = len(SourceType) > 0
"""Whether the taxonomy is populated. True since N-20 (ratified 2026-08-04,
S 5.1) supplied the eight members. The scoring half of M-16 remains OPEN."""

TAXONOMY_MARKER: str = "M-16"
"""The marker whose closure populates SourceType. [v2 section 13]"""


def taxonomy_members() -> tuple[SourceType, ...]:
    """Every ratified source type, in N-20 S 5.1 declaration order.

    The eight members and their order are the ratified table verbatim.
    Callers must never treat the taxonomy as extensible from outside a
    superseding decision record.
    """
    return tuple(SourceType)


def is_ratified_source_type(candidate: object) -> bool:
    """Whether `candidate` is a member of the ratified taxonomy.

    True only for `SourceType` members. A raw STRING is never a member of
    this typed predicate -- use `classify` to test a raw string by value.
    Total: never raises, so callers can branch without exception handling.
    """
    return isinstance(candidate, SourceType) and candidate in set(SourceType)


def classify(source_type: str) -> SourceType:
    """Map a raw source_type string onto the ratified taxonomy. [AC1, N-20 S 5.1]

    Exact member names only: the closed set admits no synonyms and no case
    folding, so a typo cannot register as a distinct type. A string outside
    the set is UNTYPABLE (N-20 S 5.2) -- the channel maps to no taxonomy
    member, gate 2 of the S 5.2.1 acquisition sequence refuses it, and the
    source is INELIGIBLE. Fails closed; nothing is guessed.
    """
    if not isinstance(source_type, str):
        raise SourceError(
            f"source_type must be a string, got {type(source_type).__name__}"
        )
    if not source_type.strip():
        raise SourceError("source_type is required [IOM section 3.1]")
    try:
        return SourceType(source_type)
    except ValueError:
        raise UntypableChannelError(
            f"source_type {source_type!r} maps onto no member of the closed "
            f"taxonomy [N-20 S 5.1]: the channel is untypable "
            f"(UNTYPABLE_CHANNEL, N-20 S 5.2), hence INELIGIBLE for "
            f"acquisition. Extension requires a superseding decision record."
        ) from None


# ---------------------------------------------------------------------------
# Eligibility  [AC1 -- "per-type eligibility"]
# ---------------------------------------------------------------------------


class SourceEligibility(str, Enum):
    """Outcome of an eligibility assessment.

    UNDETERMINED is the only outcome reachable while M-16 is open. It is a
    first-class member rather than an error code because "we do not know"
    is a legitimate, reportable state that must not be silently coerced to
    either admission or refusal.
    """

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    UNDETERMINED = "UNDETERMINED"


@dataclass(frozen=True)
class EligibilityAssessment:
    """Why a source was, or could not be, judged eligible."""

    source_identifier: str
    outcome: SourceEligibility
    reason: str
    blocking_marker: str | None = None

    @property
    def is_determined(self) -> bool:
        return self.outcome is not SourceEligibility.UNDETERMINED

    @property
    def admits_acquisition(self) -> bool:
        """Only an explicit ELIGIBLE admits acquisition. Fails closed."""
        return self.outcome is SourceEligibility.ELIGIBLE


def assess_eligibility(source_identifier: str) -> EligibilityAssessment:
    """Assess whether a source may be acquired from. [AC1, N-20 S 5.2]

    FAILS CLOSED, and does so without raising, so that callers can record
    the gap rather than crash. Eligibility under M-16 IS typability
    (N-20 S 5.2): decidable by `classify` on the channel type the Research
    Engine assigns at acquisition (N-20 S 5.1). From a bare identifier no
    type is visible, so the outcome is UNDETERMINED -- no open MARKER blocks
    it; the acquisition path (T02.2.1) that supplies typed channels does.

    Note the boundary: legal admissibility -- licensing, robots, rate limits,
    terms of use -- is M-18 and belongs to T02.1.2. It is not assessed here
    and must not be inferred from this result.
    """
    if not (source_identifier or "").strip():
        raise SourceError("source_identifier is required [IOM section 3.1]")
    return EligibilityAssessment(
        source_identifier=source_identifier,
        outcome=SourceEligibility.UNDETERMINED,
        reason=(
            "typability cannot be evaluated from source_identifier alone: "
            "eligibility under M-16 IS typability (N-20 S 5.2), and the "
            "channel type is assigned by the Research Engine at acquisition "
            "(N-20 S 5.1; the acquisition path is T02.2.1, not yet built). "
            "Call classify() on the typed channel to decide. Legal "
            "admissibility is M-18 (T02.1.2) and is not assessed here."
        ),
        blocking_marker=None,
    )


def require_eligible(source_identifier: str) -> None:
    """Admit acquisition only from a demonstrably eligible source.

    FAILS CLOSED: raises while the channel is untyped. A permissive default
    would be B-33 Option 1 ("open -- any accessible source"), an option the
    ratified corpus never adopted.
    """
    assessment = assess_eligibility(source_identifier)
    if not assessment.admits_acquisition:
        raise EligibilityNotRatifiedError(
            f"source {source_identifier!r} cannot be admitted: "
            f"{assessment.reason}"
        )


# ---------------------------------------------------------------------------
# Trust  [AC2 -- representation only]
# ---------------------------------------------------------------------------

TRUST_MINIMUM: float = 0.0
TRUST_MAXIMUM: float = 1.0
"""Range of a recorded trust rating.

NOT invented here. This is the range the ratified Evidence contract already
enforces on the optional `source_reliability` attribute (oip/evidence.py,
T01.7.1; IOM section 3.1 / OQ-28, which marker-crosswalk section 5 subsumes
into M-16). Recording trust on the same scale keeps one representation rather
than introducing a second.
"""


@dataclass(frozen=True)
class TrustRating:
    """A recorded trust rating for one source, at one point in time. [AC2]

    IMMUTABLE and VERSIONED (R-1, N-04): a rating is never edited, only
    superseded, so a historical read reproduces exactly what an engine saw.

    SEMANTICS ARE DELIBERATELY ABSENT. The value's *meaning* -- what 0.7
    asserts about a source, how it compares across source types, what it
    should influence -- is M-16. This type records a number, its provenance
    and its time. It interprets nothing.
    """

    source_identifier: str
    value: float
    rated_at: datetime
    rationale: str
    version: int
    supersedes: str | None = None

    def __post_init__(self) -> None:
        if not (self.source_identifier or "").strip():
            raise SourceError("source_identifier is required [IOM section 3.1]")
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise TrustNotRatifiedError(
                f"trust value must be numeric, got {type(self.value).__name__}"
            )
        if not TRUST_MINIMUM <= float(self.value) <= TRUST_MAXIMUM:
            raise TrustNotRatifiedError(
                f"trust value {self.value} outside "
                f"[{TRUST_MINIMUM}, {TRUST_MAXIMUM}]; this is the range the "
                f"ratified Evidence contract enforces on source_reliability "
                f"[IOM section 3.1, OQ-28]"
            )
        if not (self.rationale or "").strip():
            raise TrustNotRatifiedError(
                "a trust rating requires a rationale: an unexplained rating "
                "is unauditable, and Principle 2 requires every decision to "
                "carry its why"
            )
        if not isinstance(self.rated_at, datetime):
            raise TrustNotRatifiedError("rated_at must be a datetime")
        if self.version < 1:
            raise TrustNotRatifiedError("version starts at 1 [R-1]")

    @property
    def band(self) -> str:
        """Qualitative band for the rating.

        FAILS CLOSED. R-3's five confidence bands govern *confidence*, not
        source trust; reusing them would assert an equivalence no ratified
        source states. Banding trust is part of the trust model, i.e. M-16.
        """
        raise TrustNotRatifiedError(
            "trust banding is undefined: R-3's bands govern confidence, not "
            "source trust, and no ratified source defines trust bands [M-16]"
        )


def affects_evidential_support() -> bool:
    """Whether a recorded trust rating influences `evidential_support`.

    Always False, and this is RATIFIED rather than provisional. S-02 lists
    five inputs and states "No other input." Source trust is not among them.
    Making trust score would amend a ratified decision, which closing M-16
    does not authorise -- S-02 would have to be superseded.
    """
    return False


# ---------------------------------------------------------------------------
# Learnability  [AC3 -- NOT implementable]
# ---------------------------------------------------------------------------

LEARNING_TARGET_STATUS: str = (
    "UNRATIFIED: whether source trust is a learning target is M-02 ('what the "
    "platform learns -- the target of change'); the write authority is M-43 "
    "('Feedback Engine write target'). Both are OPEN in PKP v2 section 13. "
    "The Feedback Record's change_target attribute has no ratified vocabulary. "
    "M-70 (feedback instability guard) is also open, so learned trust would "
    "additionally be unguarded against bias entrenchment."
)

LEARNING_TARGET_MARKERS: tuple[str, ...] = ("M-02", "M-43", "M-70")


def is_learning_target() -> bool:
    """Whether source trust is a ratified P8 learning target. [AC3]

    Always False. Total predicate: callers branch without exception handling.
    """
    return False


def register_learning_update(*args: object, **kwargs: object) -> None:
    """Apply a learned update to a source's trust rating. [AC3]

    FAILS CLOSED. Present so the API surface a future P8 decision will need
    exists and is discoverable, and so that any premature call is refused
    loudly rather than silently succeeding.
    """
    raise LearningTargetNotRatifiedError(LEARNING_TARGET_STATUS)


# ---------------------------------------------------------------------------
# Source record and registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRecord:
    """What the platform knows about one external source. [N-04, R-01]

    NOT an Intelligence Object. It has no lineage, no confidence, no
    lifecycle, and never enters the Knowledge Graph -- F8 fixes the object
    model at nine types. It is infrastructure state about the external world,
    held so that provenance is auditable and reproducible.

    `source_type` is retained as the RAW string the acquirer supplied, exactly
    as the ratified Evidence contract does (Provenance.source_type: str). It
    is not coerced onto the taxonomy at registration: classification is an
    explicit act (`classify`), and the Research Engine assigns the type at
    acquisition (N-20 S 5.1). `taxonomy_classified` reports whether the raw
    string maps onto a member.
    """

    source_identifier: str
    source_type: str
    registered_at: datetime
    independence_group: str | None = None
    trust: TrustRating | None = None

    def __post_init__(self) -> None:
        if not (self.source_identifier or "").strip():
            raise SourceError("source_identifier is required [IOM section 3.1]")
        if not (self.source_type or "").strip():
            raise SourceError("source_type is required [IOM section 3.1]")
        if not isinstance(self.registered_at, datetime):
            raise SourceError("registered_at must be a datetime")

    @property
    def independence_key(self) -> str:
        """Key on which independence is assessed. [N-16]

        Identical rule to the ratified `Provenance.independence_key`
        (T01.7.1): the grouping wins where present, so syndicated copies
        count once. Reused deliberately rather than redefined.

        Explicit-input model [T02.1.3 interpretation, 2026-08-19]:
        ``independence_group`` is carried and honoured when supplied. This
        module performs NO syndication, ownership or independence inference;
        any inference requires an explicit ratified rule, and none exists.
        """
        return self.independence_group or self.source_identifier

    @property
    def is_trusted(self) -> bool:
        """Whether a trust rating has been recorded. NOT a judgement."""
        return self.trust is not None

    @property
    def trust_value(self) -> float | None:
        """The recorded rating, or None when unrated.

        NEVER defaults. IOM section 3.1 records that "absent a trust model,
        all sources weigh equally" is "a strong unstated assumption", and v2
        section 9 names exactly that indistinguishability as the defect M-16
        exists to correct. Returning a neutral default would encode the
        defect as policy.
        """
        return self.trust.value if self.trust is not None else None

    @property
    def taxonomy_classified(self) -> bool:
        """Whether the raw source_type string maps onto the ratified taxonomy.

        Value-based: the raw string is tested against the ratified member
        names. `is_ratified_source_type` is the TYPED predicate for enum
        members and is deliberately not used here -- a raw string is not an
        enum instance, and coercing it would blur registration with the
        explicit classification act.
        """
        return self.source_type in _TAXONOMY_NAMES


@dataclass
class SourceRegistry:
    """Append-only, versioned registry of external sources. [N-04, R-01, N-07]

    Modelled on ConfigurationStore, which solves the same problem: state that
    engines read, which must resolve identically at any historical point.

    CI-1 ISOLATION. This registry holds no Intelligence Object, returns none,
    and exposes no path into a lineage graph. Trust it records does not score
    (S-02), so it cannot participate in reasoning even indirectly. That is
    what keeps it on the correct side of CI-1.
    """

    _records: dict[str, SourceRecord] = field(default_factory=dict, init=False)
    _trust_history: dict[str, list[TrustRating]] = field(
        default_factory=dict, init=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    # -- registration ------------------------------------------------------

    def register(
        self,
        source_identifier: str,
        source_type: str,
        independence_group: str | None = None,
    ) -> SourceRecord:
        """Register a source. Idempotent only for an identical declaration."""
        with self._lock:
            existing = self._records.get(source_identifier)
            if existing is not None:
                if (
                    existing.source_type != source_type
                    or existing.independence_group != independence_group
                ):
                    raise SourceImmutableError(
                        f"source {source_identifier!r} is already registered "
                        f"as {existing.source_type!r}; source records are "
                        f"immutable [R-1]"
                    )
                return existing
            record = SourceRecord(
                source_identifier=source_identifier,
                source_type=source_type,
                registered_at=utc_now(),
                independence_group=independence_group,
            )
            self._records[source_identifier] = record
            return record

    def find(self, source_identifier: str) -> SourceRecord | None:
        with self._lock:
            return self._records.get(source_identifier)

    def resolve(self, source_identifier: str) -> SourceRecord:
        """Resolve a source, raising when absent. [N-4]"""
        with self._lock:
            record = self._records.get(source_identifier)
            if record is None:
                raise SourceNotFoundError(
                    f"source {source_identifier!r} does not resolve [N-4]"
                )
            return record

    def contains(self, source_identifier: str) -> bool:
        with self._lock:
            return source_identifier in self._records

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __iter__(self) -> Iterator[SourceRecord]:
        with self._lock:
            return iter(tuple(self._records.values()))

    # -- trust -------------------------------------------------------------

    def record_trust(
        self, source_identifier: str, value: float, rationale: str
    ) -> TrustRating:
        """Record a trust rating, superseding any previous one. [AC2, R-1, N-4]

        The previous rating is retained, never overwritten, so a historical
        read reproduces what an engine actually saw.
        """
        with self._lock:
            record = self.resolve(source_identifier)
            history = self._trust_history.setdefault(source_identifier, [])
            previous = history[-1] if history else None
            rating = TrustRating(
                source_identifier=source_identifier,
                value=float(value),
                rated_at=utc_now(),
                rationale=rationale,
                version=len(history) + 1,
                supersedes=(
                    f"{source_identifier}@v{previous.version}"
                    if previous is not None
                    else None
                ),
            )
            history.append(rating)
            self._records[source_identifier] = SourceRecord(
                source_identifier=record.source_identifier,
                source_type=record.source_type,
                registered_at=record.registered_at,
                independence_group=record.independence_group,
                trust=rating,
            )
            return rating

    def trust_for(self, source_identifier: str) -> TrustRating | None:
        """Current rating, or None when unrated. Never defaults."""
        with self._lock:
            history = self._trust_history.get(source_identifier, [])
            return history[-1] if history else None

    def trust_history(self, source_identifier: str) -> tuple[TrustRating, ...]:
        """Full ordered rating history. [N-4, R-1]"""
        with self._lock:
            return tuple(self._trust_history.get(source_identifier, ()))

    def trust_at_version(self, source_identifier: str, version: int) -> TrustRating:
        """Resolve a specific historical rating. [N-4]"""
        with self._lock:
            history = self._trust_history.get(source_identifier, [])
            for rating in history:
                if rating.version == version:
                    return rating
            raise SourceNotFoundError(
                f"source {source_identifier!r} has no trust version {version} "
                f"[N-4]"
            )

    def unrated(self) -> tuple[str, ...]:
        """Sources carrying no trust rating, in registration order.

        Surfacing them is the honest alternative to defaulting: the caller
        sees precisely which sources the platform cannot yet distinguish.
        """
        with self._lock:
            return tuple(
                identifier
                for identifier, record in self._records.items()
                if record.trust is None
            )

    # -- independence  [N-16] ---------------------------------------------

    def independence_groups(self) -> dict[str, tuple[str, ...]]:
        """Registered sources grouped by independence key. [N-16]

        Reports the grouping the ratified rule already defines. It does NOT
        infer syndication or common ownership -- detecting those is T02.1.3.
        """
        with self._lock:
            grouped: dict[str, list[str]] = {}
            for record in self._records.values():
                grouped.setdefault(record.independence_key, []).append(
                    record.source_identifier
                )
            return {key: tuple(sorted(v)) for key, v in sorted(grouped.items())}

    def independent_source_count(self) -> int:
        """Number of mutually independent registered sources. [N-16]"""
        with self._lock:
            return len({r.independence_key for r in self._records.values()})

    # -- coverage / diversity ---------------------------------------------

    def source_type_diversity(self) -> int:
        """Distinct source TYPES registered -- S-02 input 2.

        Counts distinct members of the ratified taxonomy (N-20 S 5.1) among
        registered sources, by value. Raw strings mapping onto no member are
        NOT counted: counting them would substitute an uncontrolled
        vocabulary for the closed one and let a typo register as diversity --
        precisely the sampling-artefact failure S-02 property P3 exists to
        prevent. Untypable registrations are out-of-frame for diversity;
        declaring them is the coverage model's duty (N-22, T02.1.4), not
        this method's.
        """
        with self._lock:
            return len({
                r.source_type
                for r in self._records.values()
                if r.source_type in _TAXONOMY_NAMES
            })

    # -- introspection -----------------------------------------------------

    def specification_gaps(self) -> dict[str, str]:
        """Every capability this module cannot supply, and its marker.

        Machine-readable so a gate can assert the gaps stay open rather than
        being quietly closed by a later edit. Capabilities N-20 S 8 closed --
        source_taxonomy (S 5.1), per_type_eligibility (S 5.2) and
        source_type_diversity -- are no longer gaps and are deliberately
        absent from this mapping.
        """
        return {
            "trust_semantics": TAXONOMY_MARKER,
            "trust_banding": TAXONOMY_MARKER,
            "trust_affects_scoring": "S-02",
            "learning_target": "M-02",
            "learning_write_authority": "M-43",
            "learning_instability_guard": "M-70",
            "legal_licensing_policy": "M-18",
        }
