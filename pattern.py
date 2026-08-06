"""Pattern object type: structure across Problems. The pipeline's narrow waist.

Task: T01.7.4

Architecture References:
- PT-V1  constituent_problems contains >=2 distinct Problems; S-4 sufficiency
- PT-V2  Constituents are distinct logical objects, not versions of one
- PT-V3  grouping_rationale non-empty and references specific constituents
- PT-V4  source_diversity present
- PT-V5  artefact_assessment present and reasoned
- PT-V6  Pattern is decomposable -- every constituent resolves
- PT-I1  Never fewer than two active constituents
- PT-I2  Constituents never discarded during aggregation
- PT-I3  Never claims scope beyond its constituents' scope
- PT-I4  Source diversity never overstated
- S-4    Pattern sufficiency: 3 independent sources spanning >=2 constituents
- N-16   Tier 1 count carried; Tier 2 diversity by traversal -- Pattern is the
         ONLY consumer of Tier 2
- N-6    Objects authoritative; the graph is a derived index
- R-1    Objects immutable; open-ended membership means high version churn
- R-6    DERIVES_FROM Pattern -> Problem; CONSTITUENT_OF Problem -> Pattern
- M-13   Pattern temporal validity OPEN; no expiry is asserted here
- M-24   Pattern strength / per-type minimum constituents OPEN (T05.1.5)
- M-25   Pattern type taxonomy formalisation OPEN (T05.1.2)
- M-61   Staleness owner OPEN
- M-66   Lineage summarisation OPEN; transitive evidence sets may be huge
- OQ-21  Whether constituent addition must always version is OPEN
- IOM    section 3.4

A Pattern asserts something categorically different from a Problem: not that a
deficiency exists, but that deficiencies RECUR in a describable way. A
single-problem Pattern is a category error, which is why PT-V1's floor is
structural rather than advisory.

Sampling artefact is this stage's defining risk and PKP v2 names it the
platform's most dangerous systemic failure -- it produces a confident,
well-evidenced, entirely false view of the market that is invisible to every
downstream engine. source_diversity and artefact_assessment are mandatory for
that reason alone.

Scope: the Pattern type and its rules. Recognition itself is Pattern
Intelligence (T05.1.1); the type taxonomy with per-type thresholds (T05.1.2),
diversity-weighted strength (T05.1.5) and temporal validity (T05.1.6) are
deliberately absent -- M-24, M-25 and M-13 remain open.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.support import sufficiency_threshold

# A Pattern is a category error below two constituents. [PT-V1, IOM 3.4]
MINIMUM_CONSTITUENTS = 2

# S-4 requires the independent sources to span more than one constituent, so
# a pattern cannot rest on a single well-sourced Problem. [S-4]
MINIMUM_CONTRIBUTING_CONSTITUENTS = 2


class PatternError(Exception):
    """Base class for Pattern violations."""


class ConstituentError(PatternError):
    """constituent_problems absent, too few, or malformed. [PT-V1, PT-V2]"""


class ConstituentVersionError(PatternError):
    """Two constituents are versions of one logical Problem. [PT-V2]"""


class GroupingRationaleError(PatternError):
    """grouping_rationale absent or citing non-constituents. [PT-V3]"""


class SourceDiversityError(PatternError):
    """source_diversity absent or negative. [PT-V4]"""


class ArtefactAssessmentError(PatternError):
    """artefact_assessment absent or unreasoned. [PT-V5]"""


class PatternScopeError(PatternError):
    """pattern_scope absent or internally inconsistent. [PT-I3]"""


class PatternType(str, Enum):
    """The kinds of structure a Pattern may assert. [IOM section 3.4]

    These four are the IOM's own enumeration. The FORMALISED taxonomy --
    per-type minimum constituent counts and the higher support required of a
    cross-domain claim -- is M-24/M-25 and lands at T05.1.2. Nothing here
    treats one type as stronger than another.
    """

    RECURRENCE = "RECURRENCE"
    CORRELATION = "CORRELATION"
    CLUSTERING = "CLUSTERING"
    CROSS_DOMAIN_SIMILARITY = "CROSS_DOMAIN_SIMILARITY"


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


# ---------------------------------------------------------------------------
# Grouping rationale  [PT-V3]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstituentRole:
    """What one constituent Problem contributes to the structure. [PT-V3]

    Structured rather than prose so "references specific constituents" is
    mechanically checkable, mirroring InferenceBasis at the Problem stage and
    Claim decomposition under S-3.
    """

    problem_ref: str
    role: str

    def __post_init__(self) -> None:
        if not (self.problem_ref or "").strip():
            raise GroupingRationaleError(
                "a role must name the constituent it describes [PT-V3]"
            )
        if not (self.role or "").strip():
            raise GroupingRationaleError(
                f"role of {self.problem_ref!r} is empty; the grouping would "
                f"rest on an unstated step [PT-V3]"
            )


@dataclass(frozen=True)
class GroupingRationale:
    """Why this grouping is meaningful rather than coincidental. [PT-V3]

    shared_structure carries the claim that makes the grouping a pattern; the
    roles say what each constituent contributes to it. Both are required: a
    list of Problems is not an argument that they share structure.
    """

    shared_structure: str
    constituent_roles: tuple[ConstituentRole, ...]

    def __post_init__(self) -> None:
        if not (self.shared_structure or "").strip():
            raise GroupingRationaleError(
                "grouping_rationale must state the shared structure; without "
                "it the grouping is an assertion of coincidence [PT-V3]"
            )
        if not self.constituent_roles:
            raise GroupingRationaleError(
                "grouping_rationale must reference specific constituents "
                "[PT-V3]"
            )
        seen: set[str] = set()
        for role in self.constituent_roles:
            if role.problem_ref in seen:
                raise GroupingRationaleError(
                    f"constituent {role.problem_ref!r} is described twice"
                )
            seen.add(role.problem_ref)

    @property
    def referenced_constituents(self) -> frozenset[str]:
        return frozenset(r.problem_ref for r in self.constituent_roles)

    def role_of(self, problem_ref: str) -> ConstituentRole | None:
        for role in self.constituent_roles:
            if role.problem_ref == problem_ref:
                return role
        return None


# ---------------------------------------------------------------------------
# Artefact assessment  [PT-V5]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ArtefactAssessment:
    """Explicit judgement on whether the pattern reflects research bias.

    Mandatory because sampling artefact is this stage's defining risk: it is
    the one failure that is confident, well-evidenced and false at the same
    time. An unstated judgement is indistinguishable from an unconsidered one.
    [PT-V5, IOM section 3.4]
    """

    attributable_to_research_bias: bool
    reasoning: str
    acquisition_efforts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (self.reasoning or "").strip():
            raise ArtefactAssessmentError(
                "artefact_assessment must be reasoned; a bare verdict is not "
                "an assessment [PT-V5]"
            )

    @property
    def is_artefact(self) -> bool:
        return self.attributable_to_research_bias

    @property
    def independent_effort_count(self) -> int:
        """Distinct acquisition efforts behind the constituents."""
        return len({e for e in self.acquisition_efforts if (e or "").strip()})


# ---------------------------------------------------------------------------
# Pattern scope  [PT-I3]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternScope:
    """Domain, population and period over which the pattern holds. [IOM 3.4]

    Structured so PT-I3 can compare the claim against the constituents that
    support it. The period is optional: a Pattern that makes no temporal claim
    is not over-claiming, and M-13 leaves temporal validity open, so absence
    must not be read as an assertion.
    """

    domain: str
    population: str
    period_start: datetime | None = None
    period_end: datetime | None = None

    def __post_init__(self) -> None:
        if not (self.domain or "").strip():
            raise PatternScopeError("pattern_scope requires a domain")
        if not (self.population or "").strip():
            raise PatternScopeError("pattern_scope requires a population")
        if self.period_start is not None and self.period_end is not None:
            if (self.period_start.tzinfo is None) != (
                self.period_end.tzinfo is None
            ):
                raise PatternScopeError(
                    "pattern_scope period mixes timezone-aware and naive values"
                )
            if self.period_start > self.period_end:
                raise PatternScopeError(
                    f"pattern_scope period_start ({self.period_start.isoformat()}) "
                    f"is after period_end ({self.period_end.isoformat()})"
                )

    @property
    def claims_a_period(self) -> bool:
        return self.period_start is not None or self.period_end is not None


# ---------------------------------------------------------------------------
# Pattern
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Pattern:
    """Structure shared across constituent Problems. [IOM section 3.4]

    Composes the universal contract with the Pattern-specific payload. Frozen
    throughout: membership is open-ended, so adding a constituent is a content
    change producing a new version under R-1. Whether that must always be a
    version is OQ-21, open; nothing here forecloses the alternative.
    """

    attributes: UniversalAttributes
    pattern_statement: str
    constituent_problems: tuple[str, ...]
    pattern_type: PatternType
    grouping_rationale: GroupingRationale
    source_diversity: int
    artefact_assessment: ArtefactAssessment
    pattern_scope: PatternScope

    # Optional attributes [IOM section 3.4]
    pattern_strength: float | None = None
    temporal_trend: str | None = None
    cross_domain_instances: tuple[str, ...] = ()
    expected_persistence: str | None = None

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.PATTERN:
            raise PatternError(
                f"expected Pattern, got {self.attributes.object_type.value}"
            )
        if self.attributes.produced_by_engine is not Engine.PATTERN_INTELLIGENCE:
            raise PatternError(
                f"only Pattern Intelligence may create Patterns; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )

        if not (self.pattern_statement or "").strip():
            raise PatternError("pattern_statement is required [IOM section 3.4]")
        if not isinstance(self.pattern_type, PatternType):
            raise PatternError(
                f"pattern_type must be a known PatternType, got "
                f"{self.pattern_type!r} [IOM section 3.4]"
            )
        if not isinstance(self.grouping_rationale, GroupingRationale):
            raise GroupingRationaleError("grouping_rationale is required [PT-V3]")
        if not isinstance(self.artefact_assessment, ArtefactAssessment):
            raise ArtefactAssessmentError(
                "artefact_assessment is required [PT-V5]"
            )
        if not isinstance(self.pattern_scope, PatternScope):
            raise PatternScopeError("pattern_scope is required [IOM section 3.4]")

        # PT-V4: presence and coherence. A negative count is not a measurement.
        if self.source_diversity is None or isinstance(
            self.source_diversity, bool
        ):
            raise SourceDiversityError("source_diversity is required [PT-V4]")
        if not isinstance(self.source_diversity, int):
            raise SourceDiversityError(
                f"source_diversity must be an integer count, got "
                f"{self.source_diversity!r} [PT-V4]"
            )
        if self.source_diversity < 0:
            raise SourceDiversityError(
                "source_diversity must be non-negative [PT-V4, N-16]"
            )

        # PT-V1: two constituents is the floor, checked at construction so a
        # single-problem Pattern cannot exist even transiently.
        if len(self.constituent_problems) < MINIMUM_CONSTITUENTS:
            raise ConstituentError(
                f"a Pattern requires at least {MINIMUM_CONSTITUENTS} "
                f"constituent Problems, got {len(self.constituent_problems)}; "
                f"a single-problem Pattern is a category error [PT-V1]"
            )
        if len(set(self.constituent_problems)) != len(self.constituent_problems):
            raise ConstituentError(
                "the same Problem is a constituent twice; structure cannot be "
                "manufactured by repetition [PT-V1, PT-V2]"
            )

        # CONSTITUENT_OF is drawn from the Problems the engine actually read,
        # so it can never name one outside derives_from. [R-6]
        upstream = {ref.object_id for ref in self.attributes.derives_from}
        stray = sorted(set(self.constituent_problems) - upstream)
        if stray:
            raise ConstituentError(
                f"constituents {stray} are not in derives_from; a Pattern "
                f"aggregates the Problems it read [R-6, IOM section 3.4]"
            )
        wrong_type = sorted(
            ref.object_id
            for ref in self.attributes.derives_from
            if ref.object_type is not ObjectType.PROBLEM
        )
        if wrong_type:
            raise PatternError(
                f"a Pattern derives from Problems only; {wrong_type} are not "
                f"Problems [R-6]"
            )

        # PT-V3: the rationale may not describe a Problem that is not a member.
        phantom = sorted(
            self.grouping_rationale.referenced_constituents
            - set(self.constituent_problems)
        )
        if phantom:
            raise GroupingRationaleError(
                f"grouping_rationale describes {phantom}, which are not "
                f"constituents of this Pattern [PT-V3]"
            )

        if self.pattern_strength is not None:
            if not 0.0 <= self.pattern_strength <= 1.0:
                raise PatternError(
                    f"pattern_strength must be in [0.0, 1.0], got "
                    f"{self.pattern_strength} [M-24 open]"
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
    def independent_source_count(self) -> int:
        return self.attributes.independent_source_count

    @property
    def constituent_count(self) -> int:
        return len(self.constituent_problems)

    @property
    def is_declared_artefact(self) -> bool:
        """Whether the producing engine judged this a sampling artefact."""
        return self.artefact_assessment.is_artefact

    @property
    def domains_claimed(self) -> int:
        """Distinct domains the Pattern claims instances in. [PT-I3]"""
        return len({_normalised(d) for d in self.cross_domain_instances if d.strip()})

    def describes(self, problem_ref: str) -> bool:
        """Whether grouping_rationale names this constituent. [PT-V3]"""
        return problem_ref in self.grouping_rationale.referenced_constituents

    def retains_constituents_of(self, earlier: "Pattern") -> bool:
        """Whether every earlier constituent survives. [PT-I2]"""
        return set(earlier.constituent_problems) <= set(self.constituent_problems)


# ---------------------------------------------------------------------------
# Pattern-specific acceptance rules  [PT-V1 .. PT-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _pattern_of(ctx: AcceptanceContext) -> "Pattern | None":
    return getattr(ctx, "pattern", None)


def ptv1_minimum_constituents(ctx: AcceptanceContext) -> RuleResult:
    """>=2 distinct Problems, and S-4 sufficiency. [PT-V1, S-4]

    S-4 binds PT-V1 explicitly: a Pattern needs 3 independent sources across
    its constituent Problems, spanning at least 2 of them. The spanning
    requirement is the part that matters -- three sources all beneath one
    constituent is one well-sourced Problem, not structure.
    """
    if ctx.attributes.object_type is not ObjectType.PATTERN:
        return _skip("PT-V1", "not a Pattern")
    pattern = _pattern_of(ctx)
    if pattern is None:
        return _skip("PT-V1", "no Pattern payload supplied")

    count = pattern.constituent_count
    if count < MINIMUM_CONSTITUENTS:
        return _fail(
            "PT-V1",
            f"{count} constituent(s); a Pattern requires at least "
            f"{MINIMUM_CONSTITUENTS}. Structure claimed from one Problem is a "
            f"category error",
        )

    threshold = sufficiency_threshold(ObjectType.PATTERN)
    declared = pattern.independent_source_count
    if declared < threshold:
        return _fail(
            "PT-V1",
            f"{declared} independent source(s) across {count} constituent(s); "
            f"S-4 requires {threshold}. Structure claimed from fewer cannot be "
            f"distinguished from coincidence",
        )

    if ctx.upstream_source_count is None:
        return _ok(
            "PT-V1",
            f"{count} constituent(s), {declared} independent source(s); "
            f"spanning unchecked, no upstream count provider",
        )

    contributing = 0
    unresolved = 0
    for problem_ref in pattern.constituent_problems:
        upstream = ctx.upstream_source_count(problem_ref)
        if upstream is None:
            unresolved += 1
        elif upstream > 0:
            contributing += 1

    if unresolved:
        # PT-V6 and V3 report unresolvable constituents; PT-V1 does not
        # duplicate that, but it cannot certify spanning either.
        return _skip(
            "PT-V1", f"{unresolved} constituent(s) unresolved; see PT-V6"
        )
    if contributing < MINIMUM_CONTRIBUTING_CONSTITUENTS:
        return _fail(
            "PT-V1",
            f"independent sources span only {contributing} constituent(s); "
            f"S-4 requires {MINIMUM_CONTRIBUTING_CONSTITUENTS}. A pattern "
            f"resting on one well-sourced Problem is not structure",
        )
    return _ok(
        "PT-V1",
        f"{count} constituent(s), {declared} independent source(s) spanning "
        f"{contributing} [S-4 floor {threshold}]",
    )


def ptv2_constituents_are_distinct_objects(ctx: AcceptanceContext) -> RuleResult:
    """Constituents are distinct logical objects, not versions of one. [PT-V2]

    Two versions of one Problem share a lineage_id. Admitting both would let a
    Pattern corroborate itself from a single underlying deficiency -- the
    frequency-inflation failure, arriving through the front door.
    """
    if ctx.attributes.object_type is not ObjectType.PATTERN:
        return _skip("PT-V2", "not a Pattern")
    pattern = _pattern_of(ctx)
    if pattern is None:
        return _skip("PT-V2", "no Pattern payload supplied")

    if len(set(pattern.constituent_problems)) != pattern.constituent_count:
        return _fail("PT-V2", "the same Problem appears twice as a constituent")

    if ctx.resolve_lineage is None:
        return _skip(
            "PT-V2",
            "constituents distinct by object_id; no lineage provider to "
            "detect versions of one Problem",
        )

    by_lineage: dict[str, list[str]] = {}
    unresolved: list[str] = []
    for problem_ref in pattern.constituent_problems:
        lineage_id = ctx.resolve_lineage(problem_ref)
        if lineage_id is None:
            unresolved.append(problem_ref)
            continue
        by_lineage.setdefault(lineage_id, []).append(problem_ref)

    if unresolved:
        return _skip(
            "PT-V2",
            f"{len(unresolved)} constituent(s) unresolved; see PT-V6",
        )

    collisions = {
        lineage_id: sorted(refs)
        for lineage_id, refs in by_lineage.items()
        if len(refs) > 1
    }
    if collisions:
        detail = "; ".join(
            f"{lineage_id} -> {refs}" for lineage_id, refs in sorted(collisions.items())
        )
        return _fail(
            "PT-V2",
            f"constituents are versions of one logical Problem: {detail}. "
            f"A Pattern over versions of one Problem is self-corroboration",
        )
    return _ok(
        "PT-V2", f"{len(by_lineage)} distinct logical Problem(s)"
    )


def ptv3_rationale_references_constituents(ctx: AcceptanceContext) -> RuleResult:
    """grouping_rationale non-empty and references constituents. [PT-V3]

    Distinct from V6, which checks the universal explanation. The rationale
    carries the specific burden of this stage: why the grouping is meaningful
    rather than coincidental.
    """
    if ctx.attributes.object_type is not ObjectType.PATTERN:
        return _skip("PT-V3", "not a Pattern")
    pattern = _pattern_of(ctx)
    if pattern is None:
        return _skip("PT-V3", "no Pattern payload supplied")

    rationale = pattern.grouping_rationale
    if not (rationale.shared_structure or "").strip():
        return _fail(
            "PT-V3",
            "grouping_rationale states no shared structure; a list of "
            "Problems is not an argument that they form a pattern",
        )
    referenced = rationale.referenced_constituents
    if not referenced:
        return _fail("PT-V3", "grouping_rationale references no constituent")

    phantom = sorted(referenced - set(pattern.constituent_problems))
    if phantom:
        return _fail(
            "PT-V3",
            f"grouping_rationale describes {phantom}, which are not "
            f"constituents of this Pattern",
        )
    return _ok(
        "PT-V3",
        f"{len(referenced)} of {pattern.constituent_count} constituent(s) "
        f"described by name",
    )


def ptv4_source_diversity_present(ctx: AcceptanceContext) -> RuleResult:
    """source_diversity present. [PT-V4, N-16]

    Presence only. The Tier 2 traversal that COMPUTES diversity from lineage
    is T05.1.4; PT-I4 bounds the declared value against what the constituents
    can actually carry.
    """
    if ctx.attributes.object_type is not ObjectType.PATTERN:
        return _skip("PT-V4", "not a Pattern")
    pattern = _pattern_of(ctx)
    if pattern is None:
        return _skip("PT-V4", "no Pattern payload supplied")

    if not isinstance(pattern.source_diversity, int) or isinstance(
        pattern.source_diversity, bool
    ):
        return _fail("PT-V4", "source_diversity is not an integer count")
    if pattern.source_diversity < 0:
        return _fail(
            "PT-V4",
            f"source_diversity {pattern.source_diversity} is negative; a "
            f"count of sources cannot be below zero",
        )
    return _ok(
        "PT-V4",
        f"{pattern.source_diversity} independent Evidence source(s) declared "
        f"[N-16 Tier 2]",
    )


def ptv5_artefact_assessment_reasoned(ctx: AcceptanceContext) -> RuleResult:
    """artefact_assessment present and reasoned. [PT-V5]

    A Pattern the producing engine itself judges attributable to research bias
    is a declared sampling artefact, and the IOM's own transition table sends
    it PROPOSED -> REJECTED. Accepting it would let the platform record a
    structure it has already said it does not believe.
    """
    if ctx.attributes.object_type is not ObjectType.PATTERN:
        return _skip("PT-V5", "not a Pattern")
    pattern = _pattern_of(ctx)
    if pattern is None:
        return _skip("PT-V5", "no Pattern payload supplied")

    assessment = pattern.artefact_assessment
    if not isinstance(assessment, ArtefactAssessment):
        return _fail("PT-V5", "artefact_assessment is absent")
    if not (assessment.reasoning or "").strip():
        return _fail(
            "PT-V5",
            "artefact_assessment is unreasoned; a bare verdict cannot be "
            "audited and sampling artefact is this stage's defining risk",
        )
    if assessment.is_artefact:
        return _fail(
            "PT-V5",
            f"assessed as attributable to research bias: "
            f"{assessment.reasoning}. A declared sampling artefact is "
            f"rejected, not recorded [IOM section 3.4 transitions]",
        )
    return _ok(
        "PT-V5",
        f"not attributable to research bias; "
        f"{assessment.independent_effort_count} acquisition effort(s) cited",
    )


def ptv6_decomposable(ctx: AcceptanceContext) -> RuleResult:
    """Pattern is decomposable -- every constituent resolves. [PT-V6]

    An undecomposable Pattern cannot be explained, which is Principle 2's
    floor: constituent loss makes the assertion unexplainable rather than
    merely weaker.
    """
    if ctx.attributes.object_type is not ObjectType.PATTERN:
        return _skip("PT-V6", "not a Pattern")
    pattern = _pattern_of(ctx)
    if pattern is None:
        return _skip("PT-V6", "no Pattern payload supplied")

    if ctx.resolve_type is None:
        return _skip("PT-V6", "no resolver supplied")

    unresolved: list[str] = []
    mistyped: list[str] = []
    for problem_ref in pattern.constituent_problems:
        actual = ctx.resolve_type(problem_ref)
        if actual is None:
            unresolved.append(problem_ref)
        elif actual is not ObjectType.PROBLEM:
            mistyped.append(f"{problem_ref} is a {actual.value}")

    if unresolved:
        return _fail(
            "PT-V6",
            f"constituents do not resolve: {sorted(unresolved)}; the Pattern "
            f"cannot be decomposed into what it claims to aggregate",
        )
    if mistyped:
        return _fail(
            "PT-V6", f"constituents are not Problems: {sorted(mistyped)}"
        )
    return _ok(
        "PT-V6", f"all {pattern.constituent_count} constituent(s) resolve"
    )


ptv1_minimum_constituents.rule_id = "PT-V1"                   # type: ignore[attr-defined]
ptv2_constituents_are_distinct_objects.rule_id = "PT-V2"      # type: ignore[attr-defined]
ptv3_rationale_references_constituents.rule_id = "PT-V3"      # type: ignore[attr-defined]
ptv4_source_diversity_present.rule_id = "PT-V4"               # type: ignore[attr-defined]
ptv5_artefact_assessment_reasoned.rule_id = "PT-V5"           # type: ignore[attr-defined]
ptv6_decomposable.rule_id = "PT-V6"                           # type: ignore[attr-defined]

PATTERN_RULES = (
    ptv1_minimum_constituents,
    ptv2_constituents_are_distinct_objects,
    ptv3_rationale_references_constituents,
    ptv4_source_diversity_present,
    ptv5_artefact_assessment_reasoned,
    ptv6_decomposable,
)


# ---------------------------------------------------------------------------
# Pattern integrity constraints  [PT-I1 .. PT-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternViolation:
    """A breached Pattern integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class PatternIntegrity:
    """Continuous verification of PT-I1..PT-I4. [IOM section 3.4]

    Detective, mirroring the universal, Evidence, Fact and Problem verifiers.
    PT-I1 in particular cannot be a write-time check alone: constituents are
    invalidated long after the Pattern was accepted, and the IOM's own
    transition table makes "constituents invalidated below two" a live event.
    """

    pattern_of: Callable[[str], "Pattern | None"]
    store: "object"

    def verify(self) -> tuple[PatternViolation, ...]:
        violations: list[PatternViolation] = []
        violations.extend(self._check_pti1())
        violations.extend(self._check_pti2())
        violations.extend(self._check_pti3())
        violations.extend(self._check_pti4())
        return tuple(violations)

    def _all_patterns(self) -> Iterable[tuple[str, "Pattern"]]:
        for stored in self.store.objects_of_type(ObjectType.PATTERN):
            pattern = self.pattern_of(stored.object_id)
            if pattern is not None:
                yield stored.object_id, pattern

    def _by_lineage(self) -> dict[str, list[tuple[int, str, "Pattern"]]]:
        grouped: dict[str, list[tuple[int, str, "Pattern"]]] = {}
        for object_id, pattern in self._all_patterns():
            grouped.setdefault(pattern.lineage_id, []).append(
                (pattern.attributes.version, object_id, pattern)
            )
        for versions in grouped.values():
            versions.sort(key=lambda item: item[0])
        return grouped

    def _check_pti1(self) -> list[PatternViolation]:
        """Never fewer than two active constituents. [PT-I1]

        Applied to ACTIVE Patterns only. A SUPERSEDED or INVALIDATED version
        asserts nothing, and demanding live membership of it would report a
        completed cascade as a violation.
        """
        violations: list[PatternViolation] = []
        for object_id, pattern in self._all_patterns():
            stored = self.store.find(object_id)
            if stored is None or stored.status is not ObjectStatus.ACTIVE:
                continue
            active = 0
            for problem_ref in pattern.constituent_problems:
                upstream = self.store.find(problem_ref)
                if (
                    upstream is not None
                    and upstream.object_type is ObjectType.PROBLEM
                    and upstream.status is ObjectStatus.ACTIVE
                ):
                    active += 1
            if active < MINIMUM_CONSTITUENTS:
                violations.append(
                    PatternViolation(
                        "PT-I1", object_id,
                        f"is ACTIVE with {active} active constituent(s) of "
                        f"{pattern.constituent_count}; a Pattern below "
                        f"{MINIMUM_CONSTITUENTS} asserts structure it no "
                        f"longer has",
                    )
                )
        return violations

    def _check_pti2(self) -> list[PatternViolation]:
        """Constituents never discarded during aggregation. [PT-I2]

        Checked across a supersession chain: membership is open-ended and
        grows, so a later version must retain everything its predecessor
        aggregated. Constituent loss is what makes a Pattern unexplainable.
        """
        violations: list[PatternViolation] = []
        for versions in self._by_lineage().values():
            for (_, _, earlier), (_, later_id, later) in zip(
                versions, versions[1:]
            ):
                if not later.retains_constituents_of(earlier):
                    missing = sorted(
                        set(earlier.constituent_problems)
                        - set(later.constituent_problems)
                    )
                    violations.append(
                        PatternViolation(
                            "PT-I2", later_id,
                            f"constituents discarded across versions: "
                            f"{missing}; aggregation is add-only",
                        )
                    )
        return violations

    def _check_pti3(self) -> list[PatternViolation]:
        """Never claims scope beyond its constituents' scope. [PT-I3]

        Two mechanical bounds, both unambiguous:

        - The claimed period may not extend beyond the window its constituents
          actually observed. A pattern asserted over a period nothing was
          observed in is asserted over nothing.
        - cross_domain_instances may not exceed the number of distinct domains
          its constituent Problems occupy.

        Textual breadth of the scope's domain and population is NOT compared.
        Whether "marketplace seller tooling" over-claims relative to
        "marketplace inventory management" is undecidable from structure, and
        an unreliable signal here would be worse than none -- the same
        judgement S-3 records and P-I3 follows.
        """
        violations: list[PatternViolation] = []
        for object_id, pattern in self._all_patterns():
            observed: list[datetime] = []
            domains: set[str] = set()
            resolved = 0
            for problem_ref in pattern.constituent_problems:
                upstream = self.store.find(problem_ref)
                if upstream is None or upstream.object_type is not ObjectType.PROBLEM:
                    continue  # PT-V6 / PT-I1 report the broken membership
                resolved += 1
                observed.append(upstream.attributes.observed_at)
                payload = self._problem_payload(problem_ref)
                if payload is not None:
                    domains.add(_normalised(payload.problem_domain))

            if resolved == 0:
                continue

            scope = pattern.pattern_scope
            if observed and scope.claims_a_period:
                earliest, latest = min(observed), max(observed)
                for label, claimed, bound, over in (
                    ("period_start", scope.period_start, earliest, "before"),
                    ("period_end", scope.period_end, latest, "after"),
                ):
                    if claimed is None:
                        continue
                    if (claimed.tzinfo is None) != (bound.tzinfo is None):
                        violations.append(
                            PatternViolation(
                                "PT-I3", object_id,
                                f"pattern_scope {label} mixes timezone-aware "
                                f"and naive values with its constituents; the "
                                f"claim cannot be compared",
                            )
                        )
                        continue
                    exceeds = claimed < bound if over == "before" else claimed > bound
                    if exceeds:
                        violations.append(
                            PatternViolation(
                                "PT-I3", object_id,
                                f"pattern_scope {label} "
                                f"({claimed.isoformat()}) falls {over} the "
                                f"window its constituents observed "
                                f"({bound.isoformat()})",
                            )
                        )

            if pattern.cross_domain_instances and domains:
                claimed_domains = pattern.domains_claimed
                if claimed_domains > len(domains):
                    violations.append(
                        PatternViolation(
                            "PT-I3", object_id,
                            f"claims instances in {claimed_domains} domain(s) "
                            f"but its constituents occupy {len(domains)}",
                        )
                    )
        return violations

    def _problem_payload(self, problem_ref: str):
        """Problem payload, where the store holds one. [N-6]

        Returns None when unavailable, so a Pattern over Problems written
        through the universal path yields no verdict rather than a false one.
        """
        registry = getattr(self.store, "problems", None)
        if registry is None:
            return None
        return registry.get(problem_ref)

    def _check_pti4(self) -> list[PatternViolation]:
        """Source diversity never overstated. [PT-I4, N-16]

        Two upper bounds, each mechanical:

        - source_diversity may not exceed the number of DISTINCT Evidence
          objects beneath the constituents. This is N-16's Tier 2 traversal,
          read from the derived index and skipped when the index cannot
          answer [N-6].
        - independent_source_count may not exceed the sum of the constituents'
          own counts [N-16 Tier 1].

        Both are upper bounds: constituents sharing sources make them loose,
        and independence grouping (T02.1.3) tightens them [M-23]. Overstated
        diversity is the frequency-inflation failure, which makes a weak
        pattern look strong precisely where the pipeline narrows.
        """
        violations: list[PatternViolation] = []
        for object_id, pattern in self._all_patterns():
            available = 0
            resolved = 0
            for problem_ref in pattern.constituent_problems:
                upstream = self.store.find(problem_ref)
                if upstream is None or upstream.object_type is not ObjectType.PROBLEM:
                    continue  # PT-V6 / PT-I1 report the broken membership
                resolved += 1
                available += upstream.attributes.independent_source_count

            if resolved == 0:
                continue

            declared = pattern.independent_source_count
            if declared > available:
                violations.append(
                    PatternViolation(
                        "PT-I4", object_id,
                        f"asserts {declared} independent source(s) but its "
                        f"constituents carry at most {available}",
                    )
                )

            if resolved == pattern.constituent_count:
                grounding = self._distinct_evidence_beneath(pattern)
                if grounding is not None:
                    if pattern.source_diversity > grounding:
                        violations.append(
                            PatternViolation(
                                "PT-I4", object_id,
                                f"declares source_diversity "
                                f"{pattern.source_diversity} but only "
                                f"{grounding} distinct Evidence object(s) lie "
                                f"beneath its constituents; diversity is "
                                f"overstated [N-16]",
                            )
                        )
                    # The Tier 1 sum above is defeated when constituents share
                    # grounding: two Problems on the same two Facts sum to
                    # four, clearing the S-4 floor of three on two real
                    # sources. Evidence contributes exactly one independent
                    # source [N-16], so distinct grounding is the true bound.
                    # This is the narrow waist -- frequency inflation here
                    # propagates into every Opportunity downstream.
                    if declared > grounding:
                        violations.append(
                            PatternViolation(
                                "PT-I4", object_id,
                                f"asserts {declared} independent source(s) but "
                                f"rests on only {grounding} distinct Evidence "
                                f"object(s); constituents share grounding "
                                f"[N-16, S-4]",
                            )
                        )
        return violations

    def _distinct_evidence_beneath(self, pattern: "Pattern") -> int | None:
        """Distinct Evidence beneath the constituents. [N-16 Tier 2, M-66]

        Read from the derived graph index, which is rebuildable from objects
        and never authoritative alone [N-6]. Returns None when the graph
        cannot answer. Fan-in here is large by design and the set may reach
        thousands; only its cardinality is used, so no summarisation decision
        is pre-empted [M-66].
        """
        graph = getattr(self.store, "graph", None)
        if graph is None:
            return None
        grounding: set[str] = set()
        for problem_ref in pattern.constituent_problems:
            if not graph.contains(problem_ref):
                return None
            grounding |= set(graph.evidence_set(problem_ref))
        return len(grounding)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class PatternRegistry:
    """Holds Pattern payloads. [IOM section 3.4]

    Mirrors the Evidence, Fact and Problem registries. Pattern-to-Pattern
    hierarchy is deliberately absent: OQ-17 is open and v1's flat model is
    preserved.
    """

    store: "object"
    _payloads: dict[str, Pattern] = field(default_factory=dict, init=False)

    def register(self, pattern: Pattern) -> Pattern:
        self._payloads[pattern.object_id] = pattern
        return pattern

    def get(self, object_id: str) -> Pattern | None:
        return self._payloads.get(object_id)

    def active_patterns(self) -> tuple[Pattern, ...]:
        patterns = []
        for object_id, pattern in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                patterns.append(pattern)
        return tuple(patterns)

    def containing(self, problem_ref: str) -> tuple[Pattern, ...]:
        """Patterns aggregating a given Problem, for impact inspection."""
        return tuple(
            pattern
            for pattern in self._payloads.values()
            if problem_ref in pattern.constituent_problems
        )

    def integrity(self) -> PatternIntegrity:
        return PatternIntegrity(pattern_of=self.get, store=self.store)

    def __len__(self) -> int:
        return len(self._payloads)
