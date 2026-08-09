"""Opportunity object type: the platform's primary output.

Task: T01.7.5

Architecture References:
- O-V1   originating_patterns non-empty and resolvable
- O-V2   opportunity_statement contains no solution design
- O-V3   score present with score_model_version
- O-V4   scoring_explanation references specific score dimensions
- O-V5   effective_confidence <= originating Pattern confidence
- O-V6   Any quantitative claim traces to Facts via lineage
- O-V7   rejection_rationale present when REJECTED
- O-I1   Confidence never exceeds what evidential support permits
- O-I2   Solution-free across all versions
- O-I3   Scores comparable only within the same score_model_version
- O-I4   Historical scores never retrospectively altered
- R-3    Two-component confidence; ceiling strictly enforced
- D-02   REJECTED objects are retained -- they are learning signal
- S-4    Opportunity inherits its Pattern's sufficiency; adds no evidence
- N-6    Objects authoritative; the graph is a derived index
- M-14   Scoring dimensions/scale/methodology OPEN and BLOCKING (T06.2.1)
- M-26   Platform meaning of "opportunity" OPEN (T06.3.5)
- M-27   Prioritisation policy OPEN
- C-01   Scoring has no owning engine; OPEN (T06.2.5)
- OQ-19  Score point-in-time vs recomputed OPEN; O-I4 requires point-in-time
- IOM    section 3.5

A Pattern is a structural observation; an Opportunity is a VALUE JUDGEMENT
about that structure. The separation exists for accountability: Pattern
Intelligence answers for whether the structure is real, Opportunity
Intelligence for whether it is worth pursuing. One engine answerable for both
would be unaccountable for either.

O-V5 is the platform's principal defence against its most consequential
failure. Confidence inflation here drives misallocated commitment, and PKP v2
rates it hard to detect precisely because an inflated number looks exactly
like a justified one.

BLOCKING CONDITION, stated deliberately. M-14 defines no scoring dimensions,
scale or methodology, so `score` and `score_basis` cannot be populated
meaningfully. Under O-V3 an unscored Opportunity CANNOT REACH ACTIVE. That is
not a defect in this module: the IOM's own worked example is shown as
PROPOSED with unpopulated scoring, demonstrating its own blocking condition.
This module reproduces that behaviour rather than inventing a placeholder
scale, which would silently close M-14.

Scope: the Opportunity type and its rules. The scoring model (T06.2.1),
score-model-version stamping (T06.2.2), per-dimension basis generation
(T06.2.3) and prioritisation (M-27) are deliberately absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Mapping

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType


class OpportunityError(Exception):
    """Base class for Opportunity violations."""


class OriginatingPatternError(OpportunityError):
    """originating_patterns absent, duplicated, or outside lineage. [O-V1]"""


class SolutionDesignError(OpportunityError):
    """opportunity_statement contains solution design. [O-V2, O-I2]"""


class ScoreError(OpportunityError):
    """score absent, malformed, or missing its model version. [O-V3]"""


class ScoringExplanationError(OpportunityError):
    """scoring_explanation absent or citing unscored dimensions. [O-V4]"""


class QuantitativeClaimError(OpportunityError):
    """A quantitative claim lacks a traceable basis. [O-V6]"""


class RejectionRationaleError(OpportunityError):
    """rejection_rationale absent on a REJECTED Opportunity. [O-V7, D-02]"""


class ScoreComparabilityError(OpportunityError):
    """Scores from different model versions were compared. [O-I3]"""


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


# ---------------------------------------------------------------------------
# Solution-design detection  [O-V2]
# ---------------------------------------------------------------------------

# Lexical markers of solution DESIGN -- mechanism, not outcome.
#
# TUNING PARAMETERS, not architecture, exactly as the P-V2 marker sets are.
# The boundary O-V2 polices is narrower than P-V2's: an Opportunity may
# legitimately state the outcome sought ("provide sellers with reliable
# feedback"), and the IOM's own worked example does. What it may not do is
# specify the MECHANISM, which would foreclose Solution Intelligence.
#
# Matching is word-bounded. A substring test previously read "blacklacks" as
# the marker "lacks" at the Problem stage; the same failure would make this
# rule fire on innocent prose, and a rule that does that gets switched off.
DESIGN_MARKERS: tuple[str, ...] = (
    "by building",
    "by implementing",
    "implemented as",
    "implemented using",
    "built on",
    "built using",
    "architecture",
    "microservice",
    "api endpoint",
    "database schema",
    "user interface",
    "dashboard",
    "browser extension",
    "mobile app",
    "plugin",
    "sdk",
    "the system will",
    "the tool will",
    "we will build",
    "we will develop",
    "technical design",
    "implementation plan",
)


def _marker_pattern(marker: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])")


_DESIGN_PATTERNS: dict[str, re.Pattern[str]] = {
    marker: _marker_pattern(marker) for marker in DESIGN_MARKERS
}


def detect_solution_design(
    statement: str, markers: tuple[str, ...] = DESIGN_MARKERS
) -> tuple[str, ...]:
    """Markers of solution design found in a statement. [O-V2]

    LEXICAL ONLY, and narrower than the Problem stage's check: it targets
    mechanism, not the statement of value. Implicit design smuggled through
    otherwise neutral prose is not covered, and is not claimed to be --
    the IOM rates solution contamination only "Medium" detectable.
    """
    text = _normalised(statement)
    return tuple(
        marker
        for marker in markers
        if _DESIGN_PATTERNS.get(marker, _marker_pattern(marker)).search(text)
    )


# Bare quantities in prose, for the O-V6 sizing check. Matches figures a
# reader would take as a sizing claim: "40,000", "12%", "$3.2m".
#
# Comma-grouped figures are matched explicitly. An earlier pattern required
# four consecutive digits and so read "40,000 sellers" as no claim at all --
# precisely the shape a market-size assertion takes in prose. Small bare
# ordinals ("four domains", "3 tools") are deliberately NOT matched: they are
# not sizing claims, and firing on them would make O-V6 unusable.
_QUANTITY = re.compile(
    r"(?<![a-z0-9])(?:"
    r"[$€£]\s?\d[\d,\.]*\s?(?:k|m|bn|b|billion|million|thousand)?"
    r"|\d[\d,\.]*\s?(?:%|percent|k|m|bn|b|billion|million|thousand)"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|\d{4,}(?:\.\d+)?"
    r")",
    re.IGNORECASE,
)


def find_quantities(text: str) -> tuple[str, ...]:
    """Quantitative expressions appearing in prose. [O-V6]"""
    return tuple(m.group(0).strip() for m in _QUANTITY.finditer(text or ""))


# ---------------------------------------------------------------------------
# Score  [O-V3, O-V4, O-I3, O-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreDimension:
    """One named component of a score. [O-V4]

    The DIMENSIONS THEMSELVES ARE UNDEFINED -- M-14 supplies no vocabulary,
    scale or weighting. This type carries whatever a scoring model emits
    without asserting what is legitimate, so that when M-14 closes at T06.2.1
    no structure here has to be unpicked.
    """

    name: str
    value: float
    rationale: str = ""

    def __post_init__(self) -> None:
        if not (self.name or "").strip():
            raise ScoreError("a score dimension requires a name [O-V4]")
        if isinstance(self.value, bool) or not isinstance(
            self.value, (int, float)
        ):
            raise ScoreError(
                f"score dimension {self.name!r} must be numeric, got "
                f"{self.value!r}"
            )


@dataclass(frozen=True)
class Score:
    """A comparative assessment stamped with the model that produced it.

    model_version is mandatory and inseparable from the value. Under
    Principle 5 the scoring model changes through learning, and scores from
    different models are silently incomparable -- the score-drift failure,
    invisible because the numbers stay superficially comparable. Binding the
    version to the score is what makes O-I3 enforceable at all.

    No scale is asserted: M-14 defines none, so `value` is carried, not
    interpreted, and no ordering across models is offered. [M-14, C-01]
    """

    value: float
    model_version: str
    dimensions: tuple[ScoreDimension, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(
            self.value, (int, float)
        ):
            raise ScoreError(f"score value must be numeric, got {self.value!r}")
        if not (self.model_version or "").strip():
            raise ScoreError(
                "score requires a score_model_version; scores from different "
                "models are silently incomparable [O-V3, O-I3]"
            )
        seen: set[str] = set()
        for dimension in self.dimensions:
            key = _normalised(dimension.name)
            if key in seen:
                raise ScoreError(
                    f"score dimension {dimension.name!r} appears twice"
                )
            seen.add(key)

    @property
    def dimension_names(self) -> frozenset[str]:
        return frozenset(_normalised(d.name) for d in self.dimensions)

    def dimension(self, name: str) -> ScoreDimension | None:
        for d in self.dimensions:
            if _normalised(d.name) == _normalised(name):
                return d
        return None

    def comparable_with(self, other: "Score") -> bool:
        """Whether two scores may be ranked against each other. [O-I3]"""
        return self.model_version == other.model_version

    def fingerprint(self) -> tuple:
        """Immutable signature of the score as recorded. [O-I4]

        O-I4 forbids retrospective alteration, so the platform needs a way to
        ask whether a stored prediction still says what it said. Rescoring
        creates a new version; it never overwrites.
        """
        return (
            self.model_version,
            float(self.value),
            tuple(
                sorted(
                    (_normalised(d.name), float(d.value)) for d in self.dimensions
                )
            ),
        )


def rank(scores: Iterable["Opportunity"]) -> tuple["Opportunity", ...]:
    """Rank Opportunities by score. Single model version only. [O-I3]

    Refuses to rank across model versions rather than returning a plausible
    but meaningless ordering. Ranking is the operation O-I3 exists to
    constrain, so the constraint lives where the operation is.
    """
    scored = [o for o in scores if o.score is not None]
    versions = {o.score.model_version for o in scored}
    if len(versions) > 1:
        raise ScoreComparabilityError(
            f"cannot rank across score model versions {sorted(versions)}; "
            f"scores are comparable only within one model [O-I3]"
        )
    return tuple(sorted(scored, key=lambda o: o.score.value, reverse=True))


# ---------------------------------------------------------------------------
# Quantitative claims  [O-V6]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class QuantitativeClaim:
    """A figure asserted by the Opportunity, with the Facts behind it.

    O-V6 exists because the temptation to state market size from model
    knowledge rather than evidence is strongest at this stage, and doing so
    breaches Principle 1 at the platform's most visible point. Every figure
    must name the Facts it rests on so the claim can be traced.
    """

    claim: str
    fact_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not (self.claim or "").strip():
            raise QuantitativeClaimError("a quantitative claim requires text")
        if not self.fact_refs:
            raise QuantitativeClaimError(
                f"quantitative claim {self.claim!r} names no supporting Fact; "
                f"sizing without basis breaches Principle 1 [O-V6]"
            )


# ---------------------------------------------------------------------------
# Opportunity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Opportunity:
    """A value judgement about a recognised Pattern. [IOM section 3.5]

    Composes the universal contract with the Opportunity-specific payload.
    Frozen: rescoring and restatement are content changes producing a new
    version under R-1, which is also what O-I4 requires -- a stored
    prediction is never overwritten.
    """

    attributes: UniversalAttributes
    opportunity_statement: str
    originating_patterns: tuple[str, ...]
    value_hypothesis: str
    beneficiary_population: str

    # Scoring. Optional in TYPE because M-14 defines no scale; required by
    # O-V3 for ACTIVE. An unscored Opportunity is a legitimate PROPOSED
    # object and an illegitimate ACTIVE one. [M-14, O-V3]
    score: Score | None = None
    score_basis: tuple[ScoreDimension, ...] = ()
    scoring_explanation: str | None = None

    # Optional attributes [IOM section 3.5]
    market_sizing: str | None = None
    timing_assessment: str | None = None
    competitive_context: str | None = None
    capture_hypothesis: str | None = None
    rejection_rationale: str | None = None
    quantitative_claims: tuple[QuantitativeClaim, ...] = ()

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.OPPORTUNITY:
            raise OpportunityError(
                f"expected Opportunity, got {self.attributes.object_type.value}"
            )
        if (
            self.attributes.produced_by_engine
            is not Engine.OPPORTUNITY_INTELLIGENCE
        ):
            raise OpportunityError(
                f"only Opportunity Intelligence may create Opportunities; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )

        for name in (
            "opportunity_statement",
            "value_hypothesis",
            "beneficiary_population",
        ):
            if not (getattr(self, name) or "").strip():
                raise OpportunityError(f"{name} is required [IOM section 3.5]")

        # O-V1: at least one originating Pattern, no duplicates.
        if not self.originating_patterns:
            raise OriginatingPatternError(
                "an Opportunity requires at least one originating Pattern "
                "[O-V1]"
            )
        if len(set(self.originating_patterns)) != len(self.originating_patterns):
            raise OriginatingPatternError(
                "the same Pattern originates this Opportunity twice [O-V1]"
            )

        upstream = {ref.object_id for ref in self.attributes.derives_from}
        stray = sorted(set(self.originating_patterns) - upstream)
        if stray:
            raise OriginatingPatternError(
                f"originating_patterns {stray} are not in derives_from; an "
                f"Opportunity rests on the Patterns it read [R-6]"
            )
        wrong_type = sorted(
            ref.object_id
            for ref in self.attributes.derives_from
            if ref.object_type is not ObjectType.PATTERN
        )
        if wrong_type:
            raise OpportunityError(
                f"an Opportunity derives from Patterns only; {wrong_type} are "
                f"not Patterns [R-6]"
            )

        if self.score is not None and not isinstance(self.score, Score):
            raise ScoreError("score must be a Score [O-V3]")

        # O-V7 / D-02: a rejection without a rationale destroys the learning
        # signal the retention policy exists to preserve.
        if self.attributes.status is ObjectStatus.REJECTED:
            if not (self.rejection_rationale or "").strip():
                raise RejectionRationaleError(
                    "a REJECTED Opportunity requires a rejection_rationale; "
                    "declined opportunities are among the platform's most "
                    "valuable learning signals [O-V7, D-02]"
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
    def is_scored(self) -> bool:
        """Whether a score is present. False while M-14 is open. [O-V3]"""
        return self.score is not None

    @property
    def score_model_version(self) -> str | None:
        return self.score.model_version if self.score else None

    @property
    def design_markers(self) -> tuple[str, ...]:
        """Solution-design language detected in the statement. [O-V2]"""
        return detect_solution_design(self.opportunity_statement)

    @property
    def is_solution_free(self) -> bool:
        """Whether no solution design is detectable. [O-V2, O-I2]"""
        return not self.design_markers

    @property
    def claimed_facts(self) -> frozenset[str]:
        refs: set[str] = set()
        for claim in self.quantitative_claims:
            refs |= set(claim.fact_refs)
        return frozenset(refs)

    def sized_text(self) -> str:
        """Prose in which an unsupported figure would be a sizing claim."""
        return " ".join(
            part
            for part in (
                self.opportunity_statement,
                self.market_sizing,
                self.value_hypothesis,
            )
            if part
        )

    def comparable_with(self, other: "Opportunity") -> bool:
        """Whether two Opportunities may be ranked together. [O-I3]"""
        if self.score is None or other.score is None:
            return False
        return self.score.comparable_with(other.score)

    def score_fingerprint(self) -> tuple | None:
        return self.score.fingerprint() if self.score else None


# ---------------------------------------------------------------------------
# Opportunity-specific acceptance rules  [O-V1 .. O-V7]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _opportunity_of(ctx: AcceptanceContext) -> "Opportunity | None":
    return getattr(ctx, "opportunity", None)


def ov1_originating_patterns_resolve(ctx: AcceptanceContext) -> RuleResult:
    """originating_patterns non-empty and resolvable. [O-V1]"""
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V1", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V1", "no Opportunity payload supplied")

    if not opportunity.originating_patterns:
        return _fail("O-V1", "no originating Pattern; the value judgement rests on nothing")

    if ctx.resolve_type is None:
        return _skip("O-V1", "patterns declared; no resolver supplied")

    unresolved: list[str] = []
    mistyped: list[str] = []
    for ref in opportunity.originating_patterns:
        actual = ctx.resolve_type(ref)
        if actual is None:
            unresolved.append(ref)
        elif actual is not ObjectType.PATTERN:
            mistyped.append(f"{ref} is a {actual.value}")

    if unresolved:
        return _fail(
            "O-V1", f"originating Patterns do not resolve: {sorted(unresolved)}"
        )
    if mistyped:
        return _fail("O-V1", f"originating references are not Patterns: {sorted(mistyped)}")
    return _ok(
        "O-V1", f"{len(opportunity.originating_patterns)} originating Pattern(s) resolve"
    )


def ov2_no_solution_design(ctx: AcceptanceContext) -> RuleResult:
    """opportunity_statement contains no solution design. [O-V2]

    Narrower than P-V2: an Opportunity may state the outcome sought, but not
    the mechanism. Solution contamination forecloses Solution Intelligence,
    collapsing two engines into one.
    """
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V2", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V2", "no Opportunity payload supplied")

    if not (opportunity.opportunity_statement or "").strip():
        return _fail(
            "O-V2",
            "opportunity_statement is absent; an unstated opportunity cannot "
            "be shown to be free of solution design",
        )

    markers = opportunity.design_markers
    if markers:
        return _fail(
            "O-V2",
            f"opportunity_statement specifies solution design: {list(markers)}. "
            f"Design here forecloses Solution Intelligence",
        )
    return _ok(
        "O-V2",
        "no solution design detected; implicit contamination not covered",
    )


def ov3_score_with_model_version(ctx: AcceptanceContext) -> RuleResult:
    """score present with score_model_version. [O-V3, M-14]

    DOCUMENTED BLOCKING CONDITION. M-14 defines no scoring dimensions, scale
    or methodology, so no Opportunity can satisfy this rule today and none can
    reach ACTIVE. The IOM's own worked example is shown as PROPOSED with
    unpopulated scoring for exactly this reason.

    Failing closed is the correct behaviour: passing an unscored Opportunity
    would make the platform's primary output ACTIVE without the comparative
    assessment that is its purpose.
    """
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V3", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V3", "no Opportunity payload supplied")

    # O-V3 gates the transition to ACTIVE, which is what the IOM's state
    # table specifies ("PROPOSED -> ACTIVE: validation passes; scored"). A
    # REJECTED candidate is retained BECAUSE it was declined, and requiring
    # a score of it would make D-02's retention unreachable for exactly the
    # objects O-V7 exists to preserve. [O-V3, O-V7, D-02]
    if ctx.attributes.status is ObjectStatus.REJECTED:
        return _skip(
            "O-V3", "REJECTED candidate retained unscored [D-02, O-V7]"
        )

    if opportunity.score is None:
        return _fail(
            "O-V3",
            "no score; an Opportunity cannot reach ACTIVE unscored. No "
            "scoring dimensions, scale or methodology are defined "
            "[M-14 open, blocking; C-01 scoring unowned]",
        )
    if not (opportunity.score.model_version or "").strip():
        return _fail(
            "O-V3",
            "score carries no score_model_version; scores from different "
            "models are silently incomparable",
        )
    return _ok(
        "O-V3",
        f"scored under model {opportunity.score.model_version!r}",
    )


def ov4_scoring_explanation_references_dimensions(
    ctx: AcceptanceContext,
) -> RuleResult:
    """scoring_explanation references specific score dimensions. [O-V4]

    A single opaque number cannot be explained, which is why the IOM requires
    a per-dimension basis. Where dimensions exist, the explanation must name
    at least one -- otherwise the score is asserted rather than explained.
    """
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V4", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V4", "no Opportunity payload supplied")

    if opportunity.score is None:
        return _skip("O-V4", "unscored; O-V3 reports the absent score [M-14]")

    explanation = opportunity.scoring_explanation
    if not (explanation or "").strip():
        return _fail(
            "O-V4",
            "scored but carries no scoring_explanation; an unexplained score "
            "breaches Principle 2 at the platform's primary output",
        )

    dimensions = opportunity.score.dimensions or opportunity.score_basis
    if not dimensions:
        return _fail(
            "O-V4",
            "score has no per-dimension basis; a single opaque number cannot "
            "be explained",
        )

    text = _normalised(explanation)
    named = [d.name for d in dimensions if _normalised(d.name) in text]
    if not named:
        return _fail(
            "O-V4",
            f"scoring_explanation names none of the score dimensions "
            f"{sorted(d.name for d in dimensions)}",
        )
    return _ok("O-V4", f"explanation names {sorted(named)}")


def ov5_confidence_within_pattern_ceiling(ctx: AcceptanceContext) -> RuleResult:
    """effective_confidence <= originating Pattern confidence. [O-V5, R-3]

    The platform's principal defence against its most consequential failure.
    V5 applies the same ceiling universally; O-V5 states it against the
    originating Patterns specifically and reports under its own identifier,
    because this is the stage where inflation drives resource commitment.

    Fails closed on an unresolvable Pattern: a ceiling cannot be established
    from a partial upstream set, and passing on the resolved subset is exactly
    how inflation would slip through.
    """
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V5", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V5", "no Opportunity payload supplied")
    if ctx.upstream_confidence is None:
        return _skip("O-V5", "no upstream confidence provider")

    resolved: list[float] = []
    unresolved: list[str] = []
    for ref in opportunity.originating_patterns:
        value = ctx.upstream_confidence(ref)
        if value is None:
            unresolved.append(ref)
        else:
            resolved.append(value)

    if unresolved:
        return _fail(
            "O-V5",
            f"originating Pattern confidence unresolvable for "
            f"{sorted(unresolved)}; a ceiling cannot be established from a "
            f"partial upstream set",
        )

    ceiling = min(resolved)
    effective = ctx.attributes.confidence.effective_confidence
    if effective > ceiling + 1e-9:
        return _fail(
            "O-V5",
            f"effective_confidence {effective} exceeds originating Pattern "
            f"ceiling {ceiling}; confidence inflation is the most "
            f"consequential failure in the platform",
        )
    return _ok("O-V5", f"within originating Pattern ceiling {ceiling}")


def ov6_quantitative_claims_trace(ctx: AcceptanceContext) -> RuleResult:
    """Any quantitative claim traces to Facts via lineage. [O-V6]

    Two halves. Every declared claim must name Facts that are genuinely
    beneath this Opportunity in lineage -- naming an unrelated Fact is not a
    trace. And a figure appearing in prose with no declared claim behind it is
    unfounded sizing, which is Principle 1 breached at the most visible point.
    """
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V6", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V6", "no Opportunity payload supplied")

    quantities = find_quantities(opportunity.sized_text())
    if not quantities and not opportunity.quantitative_claims:
        return _ok("O-V6", "no quantitative claim asserted")

    if quantities and not opportunity.quantitative_claims:
        return _fail(
            "O-V6",
            f"states quantities {sorted(set(quantities))} with no traceable "
            f"basis; sizing without evidence breaches Principle 1",
        )

    if ctx.lineage_facts is None:
        return _skip(
            "O-V6",
            f"{len(opportunity.quantitative_claims)} claim(s) declared; no "
            f"lineage provider to verify the trace",
        )

    reachable = ctx.lineage_facts(ctx.attributes.object_id)
    if reachable is None:
        return _skip("O-V6", "lineage not traversable for this object")

    untraceable: list[str] = []
    for claim in opportunity.quantitative_claims:
        stray = sorted(set(claim.fact_refs) - set(reachable))
        if stray:
            untraceable.append(f"{claim.claim!r} cites {stray}")
    if untraceable:
        return _fail(
            "O-V6",
            f"quantitative claims cite Facts outside this Opportunity's "
            f"lineage: {untraceable}",
        )
    return _ok(
        "O-V6",
        f"{len(opportunity.quantitative_claims)} claim(s) trace to Facts in "
        f"lineage",
    )


def ov7_rejection_rationale_present(ctx: AcceptanceContext) -> RuleResult:
    """rejection_rationale present when REJECTED. [O-V7, D-02]

    REJECTED Opportunities are retained deliberately: a declined opportunity
    that later proves valuable is direct evidence of scoring error, and it is
    the Feedback Engine's most informative input. A silent rejection destroys
    that signal.
    """
    if ctx.attributes.object_type is not ObjectType.OPPORTUNITY:
        return _skip("O-V7", "not an Opportunity")
    opportunity = _opportunity_of(ctx)
    if opportunity is None:
        return _skip("O-V7", "no Opportunity payload supplied")

    if ctx.attributes.status is not ObjectStatus.REJECTED:
        return _ok("O-V7", "not REJECTED; rationale not required")
    if not (opportunity.rejection_rationale or "").strip():
        return _fail(
            "O-V7",
            "REJECTED without a rejection_rationale; silent rejection "
            "breaches Principle 2 and destroys the learning signal [D-02]",
        )
    return _ok("O-V7", "rejection rationale recorded")


ov1_originating_patterns_resolve.rule_id = "O-V1"                  # type: ignore[attr-defined]
ov2_no_solution_design.rule_id = "O-V2"                            # type: ignore[attr-defined]
ov3_score_with_model_version.rule_id = "O-V3"                      # type: ignore[attr-defined]
ov4_scoring_explanation_references_dimensions.rule_id = "O-V4"     # type: ignore[attr-defined]
ov5_confidence_within_pattern_ceiling.rule_id = "O-V5"             # type: ignore[attr-defined]
ov6_quantitative_claims_trace.rule_id = "O-V6"                     # type: ignore[attr-defined]
ov7_rejection_rationale_present.rule_id = "O-V7"                   # type: ignore[attr-defined]

OPPORTUNITY_RULES = (
    ov1_originating_patterns_resolve,
    ov2_no_solution_design,
    ov3_score_with_model_version,
    ov4_scoring_explanation_references_dimensions,
    ov5_confidence_within_pattern_ceiling,
    ov6_quantitative_claims_trace,
    ov7_rejection_rationale_present,
)


# ---------------------------------------------------------------------------
# Opportunity integrity constraints  [O-I1 .. O-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpportunityViolation:
    """A breached Opportunity integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class OpportunityIntegrity:
    """Continuous verification of O-I1..O-I4. [IOM section 3.5]

    Detective, mirroring the earlier type verifiers. O-I4 in particular
    cannot be a write-time check: retrospective alteration is by definition
    something that happens after the write, and preserving what the platform
    predicted at the time is what the Feedback Engine depends on.
    """

    opportunity_of: Callable[[str], "Opportunity | None"]
    store: "object"
    _recorded_scores: dict[str, tuple] = field(default_factory=dict, init=False)

    def verify(self) -> tuple[OpportunityViolation, ...]:
        violations: list[OpportunityViolation] = []
        violations.extend(self._check_oi1())
        violations.extend(self._check_oi2())
        violations.extend(self._check_oi3())
        violations.extend(self._check_oi4())
        return tuple(violations)

    def _all_opportunities(self) -> Iterable[tuple[str, "Opportunity"]]:
        for stored in self.store.objects_of_type(ObjectType.OPPORTUNITY):
            opportunity = self.opportunity_of(stored.object_id)
            if opportunity is not None:
                yield stored.object_id, opportunity

    # -- O-I4 support -----------------------------------------------------

    def record_score(self, opportunity: "Opportunity") -> None:
        """Record a score as written, so alteration becomes detectable. [O-I4]"""
        fingerprint = opportunity.score_fingerprint()
        if fingerprint is not None:
            self._recorded_scores.setdefault(opportunity.object_id, fingerprint)

    @property
    def recorded_score_count(self) -> int:
        return len(self._recorded_scores)

    def _check_oi1(self) -> list[OpportunityViolation]:
        """Confidence never exceeds what evidential support permits. [O-I1]

        Re-verified against CURRENT upstream values, not those in force at
        acceptance. An originating Pattern superseded to a lower confidence
        lowers this ceiling long after the Opportunity was written, and
        nothing else would notice.
        """
        violations: list[OpportunityViolation] = []
        for object_id, opportunity in self._all_opportunities():
            confidence = opportunity.attributes.confidence
            effective = confidence.effective_confidence
            if effective > confidence.evidential_support + 1e-9:
                violations.append(
                    OpportunityViolation(
                        "O-I1", object_id,
                        f"effective_confidence {effective} exceeds its own "
                        f"evidential_support {confidence.evidential_support}",
                    )
                )
            for ref in opportunity.originating_patterns:
                upstream = self.store.find(ref)
                if upstream is None:
                    continue  # O-V1 / I4 report the broken reference
                ceiling = upstream.attributes.confidence.effective_confidence
                if effective > ceiling + 1e-9:
                    violations.append(
                        OpportunityViolation(
                            "O-I1", object_id,
                            f"effective_confidence {effective} exceeds "
                            f"originating Pattern {ref!r} ceiling {ceiling}; "
                            f"confidence inflation drives misallocated "
                            f"commitment",
                        )
                    )
        return violations

    def _check_oi2(self) -> list[OpportunityViolation]:
        """Solution-free across all versions. [O-I2]

        Every version is re-checked, not only the current one. A restatement
        that introduces design in version 3 breaches O-I2 even if version 1
        was clean, and O-V2 alone would never revisit it.
        """
        violations: list[OpportunityViolation] = []
        for object_id, opportunity in self._all_opportunities():
            markers = opportunity.design_markers
            if markers:
                violations.append(
                    OpportunityViolation(
                        "O-I2", object_id,
                        f"version {opportunity.attributes.version} specifies "
                        f"solution design: {list(markers)}; solution-freedom "
                        f"must hold across all versions",
                    )
                )
        return violations

    def _check_oi3(self) -> list[OpportunityViolation]:
        """Scores comparable only within the same score_model_version. [O-I3]

        Mechanically: a model version must denote ONE dimension set. If two
        Opportunities stamped with the same version expose different
        dimensions, the stamp no longer identifies a comparable basis and
        within-version ranking is as meaningless as cross-version ranking --
        while looking authoritative, which is the failure O-I3 names.

        Cross-version ranking itself is refused at the point of comparison by
        rank(); it is an operation, not a stored state.
        """
        violations: list[OpportunityViolation] = []
        dimensions_by_version: dict[str, tuple[frozenset[str], str]] = {}
        for object_id, opportunity in sorted(self._all_opportunities()):
            score = opportunity.score
            if score is None:
                continue
            names = score.dimension_names
            if not names:
                continue
            known = dimensions_by_version.get(score.model_version)
            if known is None:
                dimensions_by_version[score.model_version] = (names, object_id)
            elif known[0] != names:
                violations.append(
                    OpportunityViolation(
                        "O-I3", object_id,
                        f"score model {score.model_version!r} exposes "
                        f"dimensions {sorted(names)} here but "
                        f"{sorted(known[0])} on {known[1]!r}; one model "
                        f"version must denote one comparable basis",
                    )
                )
        return violations

    def _check_oi4(self) -> list[OpportunityViolation]:
        """Historical scores never retrospectively altered. [O-I4]

        Compares each stored score against the fingerprint recorded when it
        was written. Rescoring must create a new version; overwriting destroys
        what the platform predicted at the time, which is precisely what the
        Feedback Engine needs to measure scoring error.
        """
        violations: list[OpportunityViolation] = []
        for object_id, opportunity in self._all_opportunities():
            recorded = self._recorded_scores.get(object_id)
            if recorded is None:
                continue
            current = opportunity.score_fingerprint()
            if current is None:
                violations.append(
                    OpportunityViolation(
                        "O-I4", object_id,
                        "score was recorded at write but is now absent; a "
                        "historical prediction cannot be withdrawn",
                    )
                )
            elif current != recorded:
                violations.append(
                    OpportunityViolation(
                        "O-I4", object_id,
                        f"score altered after acceptance: recorded {recorded}, "
                        f"now {current}. Rescoring creates a new version; it "
                        f"does not overwrite",
                    )
                )
        return violations


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class OpportunityRegistry:
    """Holds Opportunity payloads. [IOM section 3.5]

    Mirrors the earlier registries. Prioritisation and selection are absent:
    M-27 and M-28 are open, and gate ownership is unresolved.
    """

    store: "object"
    _payloads: dict[str, Opportunity] = field(default_factory=dict, init=False)
    _integrity: "OpportunityIntegrity | None" = field(default=None, init=False)

    def register(self, opportunity: Opportunity) -> Opportunity:
        self._payloads[opportunity.object_id] = opportunity
        self.integrity().record_score(opportunity)
        return opportunity

    def get(self, object_id: str) -> Opportunity | None:
        return self._payloads.get(object_id)

    def active_opportunities(self) -> tuple[Opportunity, ...]:
        found = []
        for object_id, opportunity in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                found.append(opportunity)
        return tuple(found)

    def rejected_opportunities(self) -> tuple[Opportunity, ...]:
        """REJECTED Opportunities, retained as learning signal. [D-02, O-V7]"""
        found = []
        for object_id, opportunity in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.REJECTED:
                found.append(opportunity)
        return tuple(found)

    def from_pattern(self, pattern_ref: str) -> tuple[Opportunity, ...]:
        """Opportunities originating from a given Pattern. [O-V1]"""
        return tuple(
            o for o in self._payloads.values()
            if pattern_ref in o.originating_patterns
        )

    def scored_under(self, model_version: str) -> tuple[Opportunity, ...]:
        """The comparability cohort for one scoring model. [O-I3]"""
        return tuple(
            o for o in self._payloads.values()
            if o.score is not None and o.score.model_version == model_version
        )

    def rank_within(self, model_version: str) -> tuple[Opportunity, ...]:
        """Rank one model version's cohort. Never across versions. [O-I3]"""
        return rank(self.scored_under(model_version))

    def integrity(self) -> OpportunityIntegrity:
        if self._integrity is None:
            self._integrity = OpportunityIntegrity(
                opportunity_of=self.get, store=self.store
            )
        return self._integrity

    def __len__(self) -> int:
        return len(self._payloads)
