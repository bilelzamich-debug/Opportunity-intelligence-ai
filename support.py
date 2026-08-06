"""Evidential support computation.

Task: T01.5.3

Architecture References:
- S-2    Single platform-wide function; seven normative properties
- S-4    Sufficiency thresholds expressed in independent sources
- R-3    evidential_support is one of two confidence components
- N-16   independent_source_count carried on every object (Tier 1)
- M-23   Source diversity: summary carried, detail by traversal
- I7     Recomputed when upstream changes

S-2 specifies PROPERTIES, not a formula. A formula fixed now would encode
weights with no empirical basis. The seven properties are the contract; the
curve satisfying them is an implementation parameter.

  P1 Monotonic in independent sources
  P2 Saturating -- diminishing returns
  P3 Diversity-weighted -- n types beat n of one type
  P4 Independence-gated -- non-independent sources count once
  P5 Contradiction-penalised
  P6 Bounded by upstream support
  P7 Deterministic given lineage

Note P7: this is one of the few genuinely deterministic computations in the
platform, because it reads only stored lineage, never model output. [N-4]
"""

from __future__ import annotations

from dataclasses import dataclass, field


class SupportError(Exception):
    """Base class for support computation violations."""


@dataclass(frozen=True)
class SupportInputs:
    """The five inputs to the support function. Exhaustive. [S-2]

    assertion_confidence is deliberately NOT an input: the two confidence
    components must remain orthogonal. [R-3]
    """

    independent_source_count: int
    source_type_count: int = 1
    corroboration_depth: int = 1
    contradiction_count: int = 0
    upstream_support: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.independent_source_count < 0:
            raise SupportError("independent_source_count must be non-negative")
        if self.source_type_count < 0:
            raise SupportError("source_type_count must be non-negative")
        if self.corroboration_depth < 0:
            raise SupportError("corroboration_depth must be non-negative")
        if self.contradiction_count < 0:
            raise SupportError("contradiction_count must be non-negative")
        for value in self.upstream_support:
            if not 0.0 <= value <= 1.0:
                raise SupportError(
                    f"upstream support must be in [0.0, 1.0], got {value}"
                )


# Tuning parameters. Not architecture: they may change without a decision
# record provided the seven properties continue to hold. [S-2]
@dataclass(frozen=True)
class SupportParameters:
    saturation_scale: float = 4.0     # P2: sources at which returns flatten
    diversity_weight: float = 0.35    # P3: share attributable to type spread
    contradiction_penalty: float = 0.25  # P5: reduction per contradiction
    max_contradiction_penalty: float = 0.75

    def __post_init__(self) -> None:
        if self.saturation_scale <= 0:
            raise SupportError("saturation_scale must be positive")
        if not 0.0 <= self.diversity_weight <= 1.0:
            raise SupportError("diversity_weight must be in [0.0, 1.0]")


DEFAULT_PARAMETERS = SupportParameters()


def compute_support(
    inputs: SupportInputs, params: SupportParameters = DEFAULT_PARAMETERS
) -> float:
    """Compute evidential_support in [0.0, 1.0]. [S-2]

    Deterministic given lineage (P7): reads only stored counts, never model
    output, so identical lineage always yields an identical value.
    """
    if inputs.independent_source_count == 0:
        return 0.0

    # P1 + P2: monotonic and saturating in independent sources.
    n = inputs.independent_source_count
    breadth = n / (n + params.saturation_scale)

    # P3: diversity weighting. n sources across k types beat n of one type.
    types = min(inputs.source_type_count, n) if inputs.source_type_count else 1
    diversity_ratio = types / n if n else 0.0
    diversity = (
        (1.0 - params.diversity_weight)
        + params.diversity_weight * diversity_ratio
    )

    value = breadth * diversity

    # P5: contradiction penalty, bounded so support never collapses to zero
    # purely from disagreement -- disagreement is information, not absence.
    if inputs.contradiction_count:
        penalty = min(
            params.contradiction_penalty * inputs.contradiction_count,
            params.max_contradiction_penalty,
        )
        value *= 1.0 - penalty

    # P6: never exceeds the support of contributing objects.
    if inputs.upstream_support:
        value = min(value, min(inputs.upstream_support))

    return max(0.0, min(1.0, value))


# ---------------------------------------------------------------------------
# Property verification [S-2]
# ---------------------------------------------------------------------------

@dataclass
class PropertyReport:
    """Which of the seven properties hold for a given parameter set."""

    results: dict[str, bool] = field(default_factory=dict)

    @property
    def all_hold(self) -> bool:
        return all(self.results.values())

    def failures(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.results.items() if not v)


def verify_properties(
    params: SupportParameters = DEFAULT_PARAMETERS,
) -> PropertyReport:
    """Verify the seven normative properties hold. [S-2]

    The contract is the properties, so any parameter change must be checked
    against this rather than against fixed expected values.
    """
    report = PropertyReport()

    # P1 monotonic in independent sources
    values = [
        compute_support(SupportInputs(independent_source_count=n), params)
        for n in range(1, 30)
    ]
    report.results["P1_monotonic"] = all(
        b >= a - 1e-12 for a, b in zip(values, values[1:])
    )

    # P2 saturating: later increments add less than earlier ones
    deltas = [b - a for a, b in zip(values, values[1:])]
    report.results["P2_saturating"] = all(
        b <= a + 1e-12 for a, b in zip(deltas, deltas[1:])
    )

    # P3 diversity-weighted
    concentrated = compute_support(
        SupportInputs(independent_source_count=8, source_type_count=1), params
    )
    diverse = compute_support(
        SupportInputs(independent_source_count=8, source_type_count=4), params
    )
    report.results["P3_diversity_weighted"] = diverse > concentrated

    # P4 independence-gated: the input is independent sources, so five
    # syndicated copies present as one source and score as one.
    one = compute_support(SupportInputs(independent_source_count=1), params)
    syndicated = compute_support(
        SupportInputs(independent_source_count=1, corroboration_depth=5), params
    )
    report.results["P4_independence_gated"] = one == syndicated

    # P5 contradiction-penalised
    clean = compute_support(SupportInputs(independent_source_count=6), params)
    contested = compute_support(
        SupportInputs(independent_source_count=6, contradiction_count=2), params
    )
    report.results["P5_contradiction_penalised"] = contested < clean

    # P6 bounded by upstream
    bounded = compute_support(
        SupportInputs(independent_source_count=50, upstream_support=(0.2,)), params
    )
    report.results["P6_bounded_by_upstream"] = bounded <= 0.2 + 1e-12

    # P7 deterministic
    probe = SupportInputs(
        independent_source_count=7,
        source_type_count=3,
        contradiction_count=1,
        upstream_support=(0.8,),
    )
    report.results["P7_deterministic"] = (
        compute_support(probe, params) == compute_support(probe, params)
    )

    return report


# ---------------------------------------------------------------------------
# Sufficiency thresholds [S-4]
# ---------------------------------------------------------------------------

from oip.enums import ObjectType  # noqa: E402  (kept local to the threshold map)

# Minimum independent sources per object type. Expressed in INDEPENDENT
# sources, never raw counts: ten syndicated copies are one source. [S-4]
SUFFICIENCY_THRESHOLDS: dict[ObjectType, int] = {
    ObjectType.EVIDENCE: 1,
    ObjectType.FACT: 1,
    ObjectType.PROBLEM: 2,
    ObjectType.PATTERN: 3,
    ObjectType.OPPORTUNITY: 3,        # inherits its Pattern's sufficiency
    ObjectType.SOLUTION: 3,           # inherits its Opportunity's sufficiency
    ObjectType.VALIDATION: 1,
    ObjectType.EXECUTION_RECORD: 1,
    ObjectType.FEEDBACK_RECORD: 2,    # FR-V4: a pattern across outcomes
}


def meets_sufficiency(object_type: ObjectType, independent_sources: int) -> bool:
    """Whether an object clears its sufficiency floor. [S-4]

    A floor, not a gradient: below it, the object is rejected rather than
    accepted with low confidence.
    """
    return independent_sources >= SUFFICIENCY_THRESHOLDS[object_type]


def sufficiency_threshold(object_type: ObjectType) -> int:
    return SUFFICIENCY_THRESHOLDS[object_type]
