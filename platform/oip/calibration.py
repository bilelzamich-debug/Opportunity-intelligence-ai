"""Calibration rubric conformance: engines assert against the S-1 rubric.

Task: T01.5.5

Architecture References:
- S-1    Confidence Calibration Rubric (closes M-60). Five bands, each with a
         range, an observable criterion and a test. "The operative test is
         alternative-counting, not introspection." Ten worked anchors, two
         per band. "Until O2 data exists, comparability is argued, not
         demonstrated."
- S-1 Known Tensions: "With M-59 (S-2). `evidential_support` uses a separate
         computation; ONLY `assertion_confidence` is governed by this rubric."
- R-3    Two-component confidence; assertion_confidence is "asserted by the
         engine"; five mandatory band labels
- N-3    Measure O2 (calibration): "Do opportunities at confidence c succeed
         at rate approximately c?" -- the empirical correction, from P8
- B-05   Shared rubric + worked anchors for P1; post-hoc empirical
         calibration LATER. "An unstated calibration is also a calibration --
         just an invisible and inconsistent one."
- N-4    "The same engine may assert different confidence for identical
         inputs across runs, so calibration is statistical rather than exact"
- R-1    Historical values "cannot be corrected -- only reinterpreted through
         a recorded offset"
- IOM 2.3 Per-stage assertion bases are "indicative only, not thresholds"
- T01.5.1 ConfidenceBand and Confidence already realise R-3's bands
- T08.3.5 Empirical recalibration (P8) will refine S-1 and must retain "prior
         calibration for comparison", so every assessment names its rubric

WHAT THIS MODULE DOES. It makes the rubric an object the platform can point
at: each band's range, observable criterion, test question and two worked
anchors, quoted from S-1. It resolves an asserted value to its band, checks a
declared alternative count against that band where S-1 states a countable
test, and records deviations. It reports what governed an assertion; it never
changes one.

WHAT IT DOES NOT DO, AND WHY.

  It does not COUNT ALTERNATIVES. S-1 makes alternative-counting *observable*,
  not *computable*: counting requires reading the inputs and judging which
  readings are credible, which is engine judgement (AD-04) over object content
  the platform's control layers may not interpret. The count is supplied by
  the engine or it is absent, and absent means UNASSESSED -- never
  "conformant". Inventing a counting algorithm would fabricate the rubric.

  It does not CALIBRATE STATISTICALLY. That is N-3's O2, which needs realised
  outcomes that do not exist before P8, and is scheduled at T08.3.5. B-05 is
  explicit that the rubric governs first and empiricism corrects later.

  It does not TOUCH evidential_support or effective_confidence. S-1's own
  Known Tensions restrict it to assertion_confidence.

  It does not GATE ACCEPTANCE. No ratified source makes calibration a
  validation rule; V1-V12 do not include it. AC2 says deviations are
  RECORDED, and recording is what happens.

  It does not INVENT THRESHOLDS. The five ranges are quoted from S-1 and are
  verified against ConfidenceBand.for_value() at import.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable

from oip.enums import ConfidenceBand, Engine

# S-1's identity. T08.3.5 must be able to say which rubric governed a stored
# assertion in order to "retain prior calibration for comparison", and R-1
# means historical values are reinterpreted through a recorded offset rather
# than rewritten. No version scheme is invented: S-1 identifies itself by its
# decision id and ratification date, and those are what is recorded.
RUBRIC_ID = "S-1"
RUBRIC_TITLE = "Confidence Calibration Rubric"
RUBRIC_RATIFIED = "2026-08-02"

# The component S-1 governs. Quoted from its Known Tensions.
GOVERNED_COMPONENT = "assertion_confidence"
UNGOVERNED_COMPONENTS = ("evidential_support", "effective_confidence")


class CalibrationError(Exception):
    """Base class for calibration-conformance violations."""


class UngovernedComponentError(CalibrationError):
    """The rubric was applied to a component it does not govern. [S-1]

    S-1: "evidential_support uses a separate computation; only
    assertion_confidence is governed by this rubric."
    """


@dataclass(frozen=True)
class BandCriterion:
    """One band of the S-1 rubric. Every field is quoted from S-1.

    Frozen, and the rubric is a module constant: a band whose criterion could
    be edited at runtime would be no calibration at all.
    """

    band: ConfidenceBand
    low: float
    high: float
    criterion: str
    test: str
    anchor_a: str
    anchor_b: str
    # The alternative count S-1 states for this band, where it states one.
    # None means S-1 defines the band qualitatively, not by a count.
    alternative_count: int | None
    count_is_minimum: bool = False

    def contains(self, value: float) -> bool:
        """Whether a value falls in this band per the AUTHORITATIVE boundary.

        S-1 prints its ranges at two decimal places (0.00-0.19, 0.20-0.39,
        ...), which leaves unprinted gaps: 0.195 is in no printed range, yet
        it is plainly NEGLIGIBLE. Testing against the printed literals would
        answer False for a value that genuinely belongs to this band -- a
        trap for any caller that used contains() to route an assertion.

        The band boundary implemented at T01.5.1 is therefore authoritative,
        and `low`/`high` are retained as the S-1 text for display. The two
        agree at every printed gridpoint, which is verified at import by
        rubric_matches_band_boundaries().
        """
        if not 0.0 <= value <= 1.0:
            return False
        return ConfidenceBand.for_value(value) is self.band

    @property
    def is_countable(self) -> bool:
        """Whether S-1 gives this band a countable test. [S-1]"""
        return self.alternative_count is not None

    def matches_count(self, count: int) -> bool:
        """Whether a declared alternative count matches this band. [S-1]"""
        if self.alternative_count is None:
            return False
        if self.count_is_minimum:
            return count >= self.alternative_count
        return count == self.alternative_count


# The rubric, quoted from S-1's band-definition and worked-anchor tables.
#
# alternative_count is populated ONLY where S-1 states a countable test:
#   WEAK        "Are there >=2 equally good alternative conclusions? Yes."
#   MODERATE    "Is there exactly one credible alternative? Yes."
#   VERY_STRONG "Can I construct any non-contradictory alternative? No."  -> 0
#
# NEGLIGIBLE and STRONG are defined qualitatively by S-1 -- reviewer
# disagreement, and whether alternatives need extra assumptions -- so no count
# is attributed to them. Attributing one would invent a threshold S-1 does not
# state, and would manufacture deviations from a number nobody ratified.
CALIBRATION_RUBRIC: tuple[BandCriterion, ...] = (
    BandCriterion(
        band=ConfidenceBand.NEGLIGIBLE,
        low=0.00,
        high=0.19,
        criterion=(
            "The inference is speculative; a competent reviewer would likely "
            "reach a different conclusion from the same inputs"
        ),
        test="Would I defend this if challenged? No.",
        anchor_a=(
            "A Problem inferred from a single ambiguous complaint that could "
            "describe three unrelated issues"
        ),
        anchor_b=(
            "An Opportunity asserted where the Pattern's constituent Problems "
            "span unrelated populations"
        ),
        alternative_count=None,
    ),
    BandCriterion(
        band=ConfidenceBand.WEAK,
        low=0.20,
        high=0.39,
        criterion=(
            "The inference is one of several equally plausible readings of "
            "the inputs"
        ),
        test="Are there >=2 equally good alternative conclusions? Yes.",
        anchor_a=(
            "A Pattern grouping four Problems that share vocabulary but no "
            "established structural relationship"
        ),
        anchor_b=(
            "A Fact extracted from a paraphrase where the original claim's "
            "scope is unclear"
        ),
        alternative_count=2,
        count_is_minimum=True,
    ),
    BandCriterion(
        band=ConfidenceBand.MODERATE,
        low=0.40,
        high=0.59,
        criterion=(
            "The inference is the most plausible reading, but a credible "
            "alternative exists"
        ),
        test="Is there exactly one credible alternative? Yes.",
        anchor_a=(
            "A Problem where facts show recurring friction, but whether it "
            "constitutes unmet need or accepted cost is genuinely open"
        ),
        anchor_b=(
            "An Opportunity whose value depends on an unevidenced "
            "behavioural response"
        ),
        alternative_count=1,
    ),
    BandCriterion(
        band=ConfidenceBand.STRONG,
        low=0.60,
        high=0.79,
        criterion=(
            "The inference follows from the inputs; alternatives require "
            "additional assumptions"
        ),
        test="Do alternatives need extra assumptions? Yes.",
        anchor_a=(
            "A Pattern where constituent Problems share a mechanism, and the "
            "alternative explanation requires assuming coordinated unrelated "
            "causes"
        ),
        anchor_b="A Fact directly quoted with full qualifying context intact",
        alternative_count=None,
    ),
    BandCriterion(
        band=ConfidenceBand.VERY_STRONG,
        low=0.80,
        high=1.00,
        criterion=(
            "The inference is the only reading the inputs support without "
            "contradiction"
        ),
        test="Can I construct any non-contradictory alternative? No.",
        anchor_a=(
            "A Fact stated verbatim in the source with explicit scope and no "
            "ambiguity"
        ),
        anchor_b=(
            "A Problem where facts state the deficiency explicitly and the "
            "affected population is named in the evidence"
        ),
        alternative_count=0,
    ),
)

_BY_BAND: dict[ConfidenceBand, BandCriterion] = {
    criterion.band: criterion for criterion in CALIBRATION_RUBRIC
}

# The three properties S-1 says cross-engine comparability rests on.
COMPARABILITY_PROPERTIES: tuple[str, ...] = (
    "A single criterion type: every band is defined by alternative-counting, "
    "not by engine-specific notions of certainty",
    "Engine-independent anchors: anchors span multiple object types, so an "
    "engine calibrates against examples from outside its own stage",
    "Empirical correction: N-3's measure O2 tests whether opportunities "
    "asserted at confidence c succeed at rate approximately c; from P8, "
    "rubric application is corrected against outcomes",
)

# S-1, verbatim. Reported with every cross-engine comparison.
COMPARABILITY_QUALIFICATION = (
    "Until O2 data exists, comparability is argued, not demonstrated. The "
    "rubric makes engines aim at the same target; only O2 shows whether they "
    "hit it. Empirical correction is scheduled at T08.3.5 (P8). [S-1, N-3]"
)


def criterion_for_band(band: ConfidenceBand) -> BandCriterion:
    """The S-1 criterion governing a band. [S-1]"""
    if not isinstance(band, ConfidenceBand):
        raise CalibrationError(
            f"expected a ConfidenceBand, got {band!r}; the rubric defines "
            f"exactly five bands [S-1, R-3]"
        )
    return _BY_BAND[band]


def criterion_for_value(value: float) -> BandCriterion:
    """The S-1 criterion an asserted value falls under. [S-1]

    Bands are resolved through ConfidenceBand.for_value (T01.5.1), so this
    layer cannot drift from the implemented band boundaries.
    """
    return criterion_for_band(ConfidenceBand.for_value(value))


class ConformanceOutcome(str, Enum):
    """Whether an assertion conforms to the S-1 rubric. [T01.5.5]

    UNASSESSED is a first-class outcome, not a failure and not a pass. S-1's
    criterion is alternative-counting, which only the asserting engine can
    perform; where no count is declared, or where S-1 defines the band
    qualitatively, conformance is genuinely unknown. Reporting unknown as
    CONFORMANT would be the false conformity this layer exists to prevent.
    """

    CONFORMANT = "CONFORMANT"
    DEVIATION = "DEVIATION"
    UNASSESSED = "UNASSESSED"


# Why an assessment could not be made. Reported, never guessed past.
UNASSESSED_NO_COUNT = (
    "no alternative count declared; S-1's criterion is alternative-counting, "
    "which only the asserting engine can perform"
)
UNASSESSED_QUALITATIVE_BAND = (
    "S-1 defines this band qualitatively, not by an alternative count, so a "
    "count cannot confirm or contradict it"
)


@dataclass(frozen=True)
class CalibrationAssessment:
    """What governed one assertion, and whether it conformed. [T01.5.5]

    Frozen and self-describing: it names the rubric that governed the
    assertion, so T08.3.5 can retain prior calibration for comparison when it
    refines S-1 empirically.

    It carries the asserted value but never alters it. Calibration observes.
    """

    value: float
    band: ConfidenceBand
    criterion: BandCriterion
    outcome: ConformanceOutcome
    alternative_count: int | None = None
    detail: str = ""
    engine: Engine | None = None
    rubric_id: str = RUBRIC_ID
    rubric_ratified: str = RUBRIC_RATIFIED
    component: str = GOVERNED_COMPONENT

    @property
    def conformant(self) -> bool:
        return self.outcome is ConformanceOutcome.CONFORMANT

    @property
    def deviated(self) -> bool:
        return self.outcome is ConformanceOutcome.DEVIATION

    @property
    def assessed(self) -> bool:
        """Whether conformance could be determined at all."""
        return self.outcome is not ConformanceOutcome.UNASSESSED

    @property
    def expected_band(self) -> ConfidenceBand | None:
        """The band the declared count implies, where S-1 states one."""
        if self.alternative_count is None:
            return None
        for criterion in CALIBRATION_RUBRIC:
            if criterion.matches_count(self.alternative_count):
                return criterion.band
        return None


def assess_assertion(
    value: float,
    alternative_count: int | None = None,
    engine: Engine | None = None,
    component: str = GOVERNED_COMPONENT,
) -> CalibrationAssessment:
    """Reference the S-1 rubric for one asserted value. [AC1, AC2]

    Resolves the value to its band and names the observable criterion the
    engine was to apply -- that is AC1, "rubric bands referenced at
    assertion".

    Where the engine declares how many credible alternatives it found, and
    where S-1 states a countable test for the relevant band, the declared
    count is checked against the band. A mismatch is a DEVIATION, recorded
    and never corrected: R-1 makes the stored value immutable, and no
    ratified source makes calibration an acceptance rule.

    Refuses to govern any component but assertion_confidence [S-1].
    """
    if component != GOVERNED_COMPONENT:
        raise UngovernedComponentError(
            f"S-1 governs {GOVERNED_COMPONENT} only, not {component!r}; "
            f"evidential_support uses a separate computation [S-1, M-59]"
        )
    criterion = criterion_for_value(value)

    if alternative_count is None:
        return CalibrationAssessment(
            value=float(value),
            band=criterion.band,
            criterion=criterion,
            outcome=ConformanceOutcome.UNASSESSED,
            detail=UNASSESSED_NO_COUNT,
            engine=engine,
        )

    if not isinstance(alternative_count, int) or isinstance(
        alternative_count, bool
    ):
        raise CalibrationError(
            f"alternative_count must be an integer, got "
            f"{alternative_count!r}"
        )
    if alternative_count < 0:
        raise CalibrationError(
            f"alternative_count may not be negative, got {alternative_count}"
        )

    if not criterion.is_countable:
        # NEGLIGIBLE and STRONG are qualitative in S-1. A count can neither
        # confirm nor contradict them, and inventing a threshold to make it
        # do so would fabricate the rubric.
        return CalibrationAssessment(
            value=float(value),
            band=criterion.band,
            criterion=criterion,
            outcome=ConformanceOutcome.UNASSESSED,
            alternative_count=alternative_count,
            detail=UNASSESSED_QUALITATIVE_BAND,
            engine=engine,
        )

    if criterion.matches_count(alternative_count):
        return CalibrationAssessment(
            value=float(value),
            band=criterion.band,
            criterion=criterion,
            outcome=ConformanceOutcome.CONFORMANT,
            alternative_count=alternative_count,
            detail=f"declared count matches {criterion.band.value}: "
                   f"{criterion.test}",
            engine=engine,
        )

    implied = next(
        (c.band.value for c in CALIBRATION_RUBRIC
         if c.matches_count(alternative_count)),
        "no band S-1 states a count for",
    )
    return CalibrationAssessment(
        value=float(value),
        band=criterion.band,
        criterion=criterion,
        outcome=ConformanceOutcome.DEVIATION,
        alternative_count=alternative_count,
        detail=(
            f"asserted {value} falls in {criterion.band.value} "
            f"({criterion.test}) but a declared count of {alternative_count} "
            f"indicates {implied} [S-1]"
        ),
        engine=engine,
    )


@dataclass(frozen=True)
class CalibrationDeviation:
    """A recorded departure from the S-1 rubric. [AC2]

    Outside the Intelligence Object model: a deviation is an observation
    about how an engine applied a rubric, not knowledge about the world. It
    never enters lineage and never alters the object it concerns -- R-1 makes
    the stored value immutable, and S-1 states that miscalibration is
    reinterpreted through a recorded offset, never rewritten.
    """

    object_id: str
    engine: Engine | None
    value: float
    asserted_band: ConfidenceBand
    expected_band: ConfidenceBand | None
    alternative_count: int
    detail: str
    rubric_id: str = RUBRIC_ID
    rubric_ratified: str = RUBRIC_RATIFIED

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Calibration state is not knowledge. [AD-04, Art.V]"""
        return False

    @property
    def is_intelligence(self) -> bool:
        """Always False."""
        return False


@dataclass
class CalibrationRegister:
    """Append-only record of rubric deviations. [AC2]

    Records; it never corrects. Under R-1 a stored confidence value is
    immutable, and S-1 is explicit that historical values are reinterpreted
    through a recorded offset rather than revised in place.

    Thread-safe, and it owns no Intelligence Object.
    """

    _deviations: list[CalibrationDeviation] = field(
        default_factory=list, init=False
    )
    _assessments: int = field(default=0, init=False)
    _unassessed: int = field(default=0, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def record(
        self, object_id: str, assessment: CalibrationAssessment
    ) -> CalibrationDeviation | None:
        """Record one assessment. Returns a deviation if there was one.

        Every assessment is counted, including UNASSESSED ones: a register
        that counted only what it could judge would overstate conformance.
        """
        if not isinstance(assessment, CalibrationAssessment):
            raise CalibrationError(
                f"expected a CalibrationAssessment, got {assessment!r}"
            )
        if not (object_id or "").strip():
            raise CalibrationError("object_id is required to record a deviation")

        with self._lock:
            self._assessments += 1
            if not assessment.assessed:
                self._unassessed += 1
                return None
            if assessment.conformant:
                return None
            deviation = CalibrationDeviation(
                object_id=object_id,
                engine=assessment.engine,
                value=assessment.value,
                asserted_band=assessment.band,
                expected_band=assessment.expected_band,
                alternative_count=assessment.alternative_count,
                detail=assessment.detail,
            )
            self._deviations.append(deviation)
            return deviation

    def all(self) -> tuple[CalibrationDeviation, ...]:
        with self._lock:
            return tuple(self._deviations)

    def for_engine(self, engine: Engine) -> tuple[CalibrationDeviation, ...]:
        if not isinstance(engine, Engine):
            raise CalibrationError(f"expected a known Engine, got {engine!r}")
        with self._lock:
            return tuple(d for d in self._deviations if d.engine is engine)

    def for_object(self, object_id: str) -> tuple[CalibrationDeviation, ...]:
        with self._lock:
            return tuple(
                d for d in self._deviations if d.object_id == object_id
            )

    @property
    def deviation_count(self) -> int:
        with self._lock:
            return len(self._deviations)

    @property
    def assessment_count(self) -> int:
        with self._lock:
            return self._assessments

    @property
    def unassessed_count(self) -> int:
        """Assessments where conformance could not be determined. [S-1]"""
        with self._lock:
            return self._unassessed

    def summary(self) -> dict[str, int]:
        """Plain counts. No rate, no threshold, no verdict.

        Deliberately not a calibration score: measuring whether assertions
        are well calibrated is N-3's O2, which needs realised outcomes and is
        scheduled at T08.3.5 (P8).
        """
        with self._lock:
            return {
                "assessments": self._assessments,
                "deviations": len(self._deviations),
                "unassessed": self._unassessed,
            }

    def __len__(self) -> int:
        with self._lock:
            return len(self._deviations)

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. [AD-04, Art.V]"""
        return False

    def delete(self, *_args, **_kwargs) -> None:
        """Never permitted. The register is append-only. [R-1, S-1]"""
        raise CalibrationError(
            "calibration deviations are append-only; historical values are "
            "reinterpreted through a recorded offset, never rewritten [S-1, R-1]"
        )


@dataclass(frozen=True)
class CrossEngineComparison:
    """A comparison of assertions across engines. [AC3]

    S-1 grounds cross-engine comparability in three properties and then
    states plainly that, until O2 data exists, "comparability is argued, not
    demonstrated". This type carries that qualification with the result so a
    consumer cannot read the comparison as more than the rubric supports.
    """

    bands: tuple[tuple[Engine, ConfidenceBand], ...]
    rubric_id: str = RUBRIC_ID
    rubric_ratified: str = RUBRIC_RATIFIED
    qualification: str = COMPARABILITY_QUALIFICATION
    properties: tuple[str, ...] = COMPARABILITY_PROPERTIES

    @property
    def rubric_dependent(self) -> bool:
        """Always True. The comparison holds only under S-1. [AC3]"""
        return True

    @property
    def comparability_demonstrated(self) -> bool:
        """Always False until O2 exists. [S-1, N-3, T08.3.5]

        S-1: "Until O2 data exists, comparability is argued, not
        demonstrated." Reporting True would claim an empirical result the
        platform cannot have before P8.
        """
        return False

    @property
    def engines(self) -> tuple[Engine, ...]:
        return tuple(engine for engine, _ in self.bands)

    def __len__(self) -> int:
        return len(self.bands)


def compare_across_engines(
    assertions: Iterable[tuple[Engine, float]]
) -> CrossEngineComparison:
    """Compare assertions across engines under the S-1 rubric. [AC3]

    Returns bands, never a ranking or a winner: S-1 supports the claim that
    engines aim at the same target, not that their numbers are
    interchangeable. The qualification travels with the result.
    """
    bands: list[tuple[Engine, ConfidenceBand]] = []
    for entry in assertions:
        engine, value = entry
        if not isinstance(engine, Engine):
            raise CalibrationError(f"expected a known Engine, got {engine!r}")
        bands.append((engine, ConfidenceBand.for_value(value)))
    return CrossEngineComparison(bands=tuple(bands))


def rubric_matches_band_boundaries() -> bool:
    """Whether the rubric's ranges equal the implemented band boundaries.

    S-1's table and ConfidenceBand.for_value (T01.5.1) must agree exactly, or
    an assertion could be governed by a criterion that does not apply to it.
    Verified at import: a silent divergence here would be invisible
    miscalibration of exactly the kind S-1 exists to prevent.
    """
    for criterion in CALIBRATION_RUBRIC:
        for probe in (criterion.low, criterion.high):
            if ConfidenceBand.for_value(probe) is not criterion.band:
                return False
    return True


if not rubric_matches_band_boundaries():  # pragma: no cover - import guard
    raise CalibrationError(
        "the S-1 rubric ranges do not match the implemented ConfidenceBand "
        "boundaries; assertions would be governed by the wrong criterion "
        "[S-1, R-3, T01.5.1]"
    )
