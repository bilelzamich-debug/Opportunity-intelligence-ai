"""Execution Record object type: the platform's only ground truth.

Task: T01.7.8

Architecture References:
- X-V1   outcome_of_solution resolvable to a specific Solution version
- X-V2   outcome_valence present
- X-V3   attribution_assessment present and reasoned
- X-V4   prediction_comparison references the Opportunity's stored prediction
- X-V5   executed_at <= outcome_observed_at
- X-V6   outcome_verification present
- X-I1   Unfavourable outcomes recorded with equal status to favourable
- X-I2   Never modifies the Solution or Opportunity it evaluates
- X-I3   Attribution never overstated
- X-I4   Links to the specific Solution version executed
- C-02   NO PRODUCING ENGINE, NO CREATE AUTHORITY -- open, blocking (T08.1.1)
- M-47   Outcome intake and verification mechanism OPEN (T08.1.2)
- R-1a   Lineage references bind to a specific version
- R-3    assertion_confidence reflects attribution certainty, typically low
- R-6    DERIVES_FROM / OUTCOME_OF the Solution; CONTRADICTS Execution Record
- D-01   Immutable prediction storage, which X-V4 depends on
- O-I4   Historical scores never altered -- what X-V4 compares against
- IOM    section 3.8

This is the ONLY object carrying ground truth. Every other object records what
the platform inferred; this one records what occurred. Principle 5 depends
entirely on it: without outcomes the platform has nothing to learn from and
the loop is open.

BLOCKING CONDITION, stated deliberately and enforced by failing closed.

C-02 records that no Execution Engine exists in v1 §4. This is the only object
type with no producing engine, no create authority and no defined intake path.
`CREATE_AUTHORITY` therefore has no entry for EXECUTION_RECORD, and the
universal rule V7 refuses every write with "[C-02 open]". That refusal is not
a defect in this module -- it is the specification's own consequence, quoted
from the IOM: "the Execution Record is specified in full below, but cannot be
created by any component defined in v1. Its attributes, rules and constraints
are stated so that they are ready when the contradiction is resolved."

This module therefore realises the type completely and assigns NO authority.
Doing otherwise would add or extend an engine, which is out of scope here and
is scheduled as an escalation at T08.1.1. Until then an Execution Record can
be constructed and validated but never accepted, and `write_execution_record`
fails closed for that reason.

M-47 leaves outcome intake AND its verification undefined as a single gap, so
`outcome_verification` is required to be PRESENT (X-V6) while its adequacy is
unconstrained -- there is no standard to check against.

Scope: the Execution Record type and its rules. Outcome intake (T08.1.2),
verification standards (M-47) and attribution methodology are absent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable

import re

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import CREATE_AUTHORITY, ObjectStatus, ObjectType


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def _content_words(text: str) -> frozenset[str]:
    """Discriminating words of a phrase, for the X-I3 mention test.

    Short function words are dropped: they appear in almost any sentence and
    would let unrelated prose count as an account of a deviation.
    """
    return frozenset(
        word for word in re.findall(r"[a-z0-9]+", _normalised(text))
        if len(word) > 3
    )


def _mentions(reasoning: str, deviation: str) -> bool:
    """Whether reasoning engages with a specific disclosed deviation. [X-I3]

    Requires the deviation's own content words, not the mere presence of the
    word "deviation". Detects silence about a disclosed departure; it cannot
    judge whether the account given is adequate.
    """
    words = _content_words(deviation)
    if not words:
        return True  # nothing discriminating to look for
    present = _content_words(reasoning)
    return bool(words & present)

# C-02: no engine holds create authority for this type. Asserted here so a
# future edit that quietly assigns one breaks loudly at import. [C-02]
NO_CREATE_AUTHORITY: bool = ObjectType.EXECUTION_RECORD not in CREATE_AUTHORITY


class ExecutionRecordError(Exception):
    """Base class for Execution Record violations."""


class SolutionReferenceError(ExecutionRecordError):
    """outcome_of_solution absent or not a specific version. [X-V1, X-I4]"""


class ValenceError(ExecutionRecordError):
    """outcome_valence absent or outside the defined set. [X-V2]"""


class AttributionError(ExecutionRecordError):
    """attribution_assessment absent or unreasoned. [X-V3, X-I3]"""


class PredictionComparisonError(ExecutionRecordError):
    """prediction_comparison absent or naming no prediction. [X-V4]"""


class OutcomeTimingError(ExecutionRecordError):
    """executed_at is after outcome_observed_at. [X-V5]"""


class VerificationError(ExecutionRecordError):
    """outcome_verification absent. [X-V6, M-47]"""


class UnfavourableSuppressionError(ExecutionRecordError):
    """An unfavourable outcome was REJECTED for being unfavourable. [X-I1]"""


class OutcomeValence(str, Enum):
    """The four defined valences. [X-V2, IOM section 3.8]

    A CLOSED set, unlike outcome_verification: the IOM enumerates these four
    explicitly, so they are enforceable today even while M-47 leaves the
    verification mechanism undefined.
    """

    FAVOURABLE = "FAVOURABLE"
    UNFAVOURABLE = "UNFAVOURABLE"
    MIXED = "MIXED"
    INCONCLUSIVE = "INCONCLUSIVE"

    @property
    def is_unfavourable(self) -> bool:
        """Whether the outcome is unwelcome in whole or in part. [X-I1]"""
        return self in (OutcomeValence.UNFAVOURABLE, OutcomeValence.MIXED)


# Valences that must never be REJECTED or quietly retired for being what they
# are. Survivorship bias -- only favourable outcomes reported -- is an
# explicit failure case, and it is the one that corrupts learning fastest.
PROTECTED_VALENCES: frozenset[OutcomeValence] = frozenset(
    {
        OutcomeValence.UNFAVOURABLE,
        OutcomeValence.MIXED,
        OutcomeValence.INCONCLUSIVE,
    }
)


# ---------------------------------------------------------------------------
# Attribution  [X-V3, X-I3]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AttributionAssessment:
    """What is and is not attributable to the solution. [X-V3, X-I3]

    Both halves are modelled. An assessment that records only what the
    solution achieved, with nothing marked unattributable, is the shape
    attribution overstatement takes -- and attribution error is rated "very
    hard" to detect precisely because the record looks complete.

    Isolating a solution's effect from external factors is genuinely
    difficult, so a claim of total attribution is a strong one and X-I3
    checks it against the confounders the record itself discloses.
    """

    attributable: tuple[str, ...]
    not_attributable: tuple[str, ...]
    reasoning: str

    def __post_init__(self) -> None:
        if not (self.reasoning or "").strip():
            raise AttributionError(
                "attribution_assessment must be reasoned; an unreasoned "
                "attribution cannot be audited and this object is the "
                "platform's only ground-truth input [X-V3]"
            )
        if not self.attributable and not self.not_attributable:
            raise AttributionError(
                "attribution_assessment distinguishes nothing; what is and is "
                "not attributable to the solution must both be stated [X-V3]"
            )

    @property
    def claims_total_attribution(self) -> bool:
        """Whether everything observed is claimed for the solution. [X-I3]"""
        return bool(self.attributable) and not self.not_attributable


# ---------------------------------------------------------------------------
# Prediction comparison  [X-V4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PredictionComparison:
    """The actual outcome set against what was predicted. [X-V4]

    predicted_by names the Opportunity whose stored prediction is being
    compared against. X-V4 requires that prediction to be RETRIEVABLE, which
    is what immutable point-in-time storage (D-01, O-I4) exists to guarantee.
    This is where immutability pays for itself: without it the platform could
    only compare an outcome against a prediction it had since revised.
    """

    predicted_by: str
    comparison: str

    def __post_init__(self) -> None:
        if not (self.predicted_by or "").strip():
            raise PredictionComparisonError(
                "prediction_comparison must name the Opportunity whose "
                "prediction is being tested [X-V4]"
            )
        if not (self.comparison or "").strip():
            raise PredictionComparisonError(
                f"comparison against {self.predicted_by!r} is empty; an "
                f"outcome recorded without reference to what was predicted "
                f"teaches nothing [X-V4]"
            )


# ---------------------------------------------------------------------------
# Execution Record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionRecord:
    """What actually happened when a solution was acted upon.

    Composes the universal contract with the Execution Record payload.
    Frozen: outcomes accumulate over extended periods and each accumulation
    produces a new version under R-1, making this the object most subject to
    temporal spread between prediction and observation.

    CONSTRUCTIBLE BUT NOT ACCEPTABLE. No engine holds create authority
    (C-02), so V7 refuses every write. The type is complete and ready; the
    authority is not this task's to assign.
    """

    attributes: UniversalAttributes
    outcome_of_solution: str
    execution_description: str
    executed_at: datetime
    outcome_observed_at: datetime
    outcome: str
    outcome_valence: OutcomeValence
    attribution_assessment: AttributionAssessment
    prediction_comparison: PredictionComparison
    outcome_verification: str

    # Optional attributes [IOM section 3.8]
    execution_deviations: tuple[str, ...] = ()
    external_factors: tuple[str, ...] = ()
    partial_outcomes: tuple[str, ...] = ()
    outcome_magnitude: str | None = None

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.EXECUTION_RECORD:
            raise ExecutionRecordError(
                f"expected ExecutionRecord, got "
                f"{self.attributes.object_type.value}"
            )
        # NOTE: produced_by_engine is deliberately NOT checked against a
        # create authority. None exists. V7 refuses the write instead, which
        # is the specified behaviour while C-02 is open. Asserting an
        # authority here would resolve C-02 by implementation. [C-02]

        for name in (
            "outcome_of_solution",
            "execution_description",
            "outcome",
        ):
            if not (getattr(self, name) or "").strip():
                raise ExecutionRecordError(
                    f"{name} is required [IOM section 3.8]"
                )

        if not isinstance(self.outcome_valence, OutcomeValence):
            raise ValenceError(
                f"outcome_valence must be one of "
                f"{sorted(v.value for v in OutcomeValence)}, got "
                f"{self.outcome_valence!r} [X-V2]"
            )
        if not isinstance(self.attribution_assessment, AttributionAssessment):
            raise AttributionError("attribution_assessment is required [X-V3]")
        if not isinstance(self.prediction_comparison, PredictionComparison):
            raise PredictionComparisonError(
                "prediction_comparison is required [X-V4]"
            )
        if not (self.outcome_verification or "").strip():
            raise VerificationError(
                "outcome_verification is required; an unverified outcome lets "
                "the platform be taught anything [X-V6, M-47 open]"
            )

        for name in ("executed_at", "outcome_observed_at"):
            if not isinstance(getattr(self, name), datetime):
                raise ExecutionRecordError(f"{name} must be a datetime")
        # X-V5, guarded for mixed awareness exactly as V8 and E-V5 are: an
        # unguarded comparison raises TypeError and would take down the whole
        # acceptance path rather than producing a failure record. [N-10]
        if (self.executed_at.tzinfo is None) != (
            self.outcome_observed_at.tzinfo is None
        ):
            raise OutcomeTimingError(
                "executed_at and outcome_observed_at mix timezone-aware and "
                "naive values [X-V5]"
            )
        if self.executed_at > self.outcome_observed_at:
            raise OutcomeTimingError(
                f"executed_at ({self.executed_at.isoformat()}) is after "
                f"outcome_observed_at "
                f"({self.outcome_observed_at.isoformat()}); an outcome cannot "
                f"be observed before it was caused [X-V5]"
            )

        # X-V1 / X-I4: OUTCOME_OF binds to the specific version executed.
        upstream = {ref.object_id for ref in self.attributes.derives_from}
        if self.outcome_of_solution not in upstream:
            raise SolutionReferenceError(
                f"outcome_of_solution {self.outcome_of_solution!r} is not in "
                f"derives_from; an Execution Record is the outcome of the "
                f"Solution it derives from [R-6, X-I4]"
            )
        wrong_type = sorted(
            ref.object_id
            for ref in self.attributes.derives_from
            if ref.object_type is not ObjectType.SOLUTION
        )
        if wrong_type:
            raise ExecutionRecordError(
                f"an Execution Record derives from Solutions only; "
                f"{wrong_type} are not Solutions [R-6]"
            )

        # X-I1 at construction: an unwelcome outcome may not be filed as an
        # unusable record. Survivorship bias closed at the earliest point.
        if self.attributes.status is ObjectStatus.REJECTED:
            if self.outcome_valence in PROTECTED_VALENCES:
                raise UnfavourableSuppressionError(
                    f"a {self.outcome_valence.value} outcome may not be "
                    f"REJECTED; REJECTED denotes an unverifiable or "
                    f"unattributable record, never an unwelcome result. "
                    f"Suppressing it biases learning toward whichever "
                    f"outcomes are convenient [X-I1]"
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
    def is_unfavourable(self) -> bool:
        return self.outcome_valence.is_unfavourable

    @property
    def is_protected(self) -> bool:
        """Whether X-I1 forbids REJECTING this outcome. [X-I1]"""
        return self.outcome_valence in PROTECTED_VALENCES

    @property
    def predicted_by(self) -> str:
        return self.prediction_comparison.predicted_by

    @property
    def deviated(self) -> bool:
        """Whether execution departed from the specified Solution. [X-I3]

        If it did, the outcome tests something other than what the platform
        proposed, and learning from it would attribute results to the wrong
        cause.
        """
        return bool(self.execution_deviations)

    @property
    def has_confounders(self) -> bool:
        """Whether the record itself discloses competing explanations."""
        return bool(self.external_factors) or self.deviated

    @property
    def observation_lag(self):
        """Time between execution and observation. [latency mismatch]"""
        return self.outcome_observed_at - self.executed_at

    def outcome_fingerprint(self) -> tuple:
        """Immutable signature of the recorded outcome. [D-01]"""
        return (
            self.outcome_valence.value,
            self.outcome,
            self.attribution_assessment.reasoning,
        )


# ---------------------------------------------------------------------------
# Execution Record acceptance rules  [X-V1 .. X-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _record_of(ctx: AcceptanceContext) -> "ExecutionRecord | None":
    return getattr(ctx, "execution_record", None)


def xv1_solution_version_resolves(ctx: AcceptanceContext) -> RuleResult:
    """outcome_of_solution resolvable to a specific Solution version. [X-V1]

    Version-specific by construction: object_id identifies one version under
    R-1a, so resolving the reference is what establishes which version was
    executed. X-I4 re-checks that binding continuously.
    """
    if ctx.attributes.object_type is not ObjectType.EXECUTION_RECORD:
        return _skip("X-V1", "not an Execution Record")
    record = _record_of(ctx)
    if record is None:
        return _skip("X-V1", "no Execution Record payload supplied")

    ref = record.outcome_of_solution
    if not (ref or "").strip():
        return _fail("X-V1", "outcome_of_solution is absent")

    if ctx.resolve_type is None:
        return _skip("X-V1", "solution declared; no resolver supplied")

    actual = ctx.resolve_type(ref)
    if actual is None:
        return _fail(
            "X-V1",
            f"executed Solution {ref!r} does not resolve; the outcome cannot "
            f"be attached to what was executed",
        )
    if actual is not ObjectType.SOLUTION:
        return _fail("X-V1", f"{ref!r} is a {actual.value}, not a Solution")
    return _ok("X-V1", f"outcome of Solution version {ref!r}")


def xv2_valence_present(ctx: AcceptanceContext) -> RuleResult:
    """outcome_valence present. [X-V2]"""
    if ctx.attributes.object_type is not ObjectType.EXECUTION_RECORD:
        return _skip("X-V2", "not an Execution Record")
    record = _record_of(ctx)
    if record is None:
        return _skip("X-V2", "no Execution Record payload supplied")

    if not isinstance(record.outcome_valence, OutcomeValence):
        return _fail(
            "X-V2",
            f"outcome_valence {record.outcome_valence!r} is outside the "
            f"defined set {sorted(v.value for v in OutcomeValence)}",
        )
    return _ok("X-V2", record.outcome_valence.value)


def xv3_attribution_reasoned(ctx: AcceptanceContext) -> RuleResult:
    """attribution_assessment present and reasoned. [X-V3]

    Mandatory because this object is the platform's only ground-truth input.
    If outcomes can be reported unattributed, the platform can be taught
    anything -- the most direct route to corrupting a continuously learning
    system.
    """
    if ctx.attributes.object_type is not ObjectType.EXECUTION_RECORD:
        return _skip("X-V3", "not an Execution Record")
    record = _record_of(ctx)
    if record is None:
        return _skip("X-V3", "no Execution Record payload supplied")

    assessment = record.attribution_assessment
    if not isinstance(assessment, AttributionAssessment):
        return _fail("X-V3", "attribution_assessment is absent")
    if not (assessment.reasoning or "").strip():
        return _fail(
            "X-V3",
            "attribution_assessment is unreasoned; a bare verdict cannot be "
            "audited",
        )
    if not assessment.attributable and not assessment.not_attributable:
        return _fail(
            "X-V3",
            "attribution_assessment distinguishes nothing attributable from "
            "anything unattributable",
        )
    return _ok(
        "X-V3",
        f"{len(assessment.attributable)} attributable, "
        f"{len(assessment.not_attributable)} not",
    )


def xv4_prediction_retrievable(ctx: AcceptanceContext) -> RuleResult:
    """prediction_comparison references the stored prediction. [X-V4]

    The prediction must be RETRIEVABLE, not merely named. Immutable
    point-in-time storage (D-01, O-I4) is what makes that possible, and this
    rule is where that immutability pays for itself: comparing an outcome
    against a prediction the platform has since revised would measure
    nothing.

    The named Opportunity must also be reachable in this record's own
    lineage. An outcome compared against some other Opportunity's prediction
    is measuring a different bet.
    """
    if ctx.attributes.object_type is not ObjectType.EXECUTION_RECORD:
        return _skip("X-V4", "not an Execution Record")
    record = _record_of(ctx)
    if record is None:
        return _skip("X-V4", "no Execution Record payload supplied")

    comparison = record.prediction_comparison
    if not (comparison.predicted_by or "").strip():
        return _fail("X-V4", "prediction_comparison names no Opportunity")
    if not (comparison.comparison or "").strip():
        return _fail(
            "X-V4",
            "prediction_comparison is empty; an outcome recorded without "
            "reference to what was predicted teaches nothing",
        )

    if ctx.lineage_opportunities is not None:
        reachable = ctx.lineage_opportunities(ctx.attributes.object_id)
        if reachable is not None and comparison.predicted_by not in reachable:
            return _fail(
                "X-V4",
                f"prediction_comparison cites {comparison.predicted_by!r}, "
                f"which is not in this record's lineage; the outcome would be "
                f"measured against a different bet",
            )

    prediction_of = getattr(ctx, "stored_prediction", None)
    if prediction_of is None:
        return _skip(
            "X-V4",
            f"prediction of {comparison.predicted_by!r} named; no provider to "
            f"retrieve it",
        )
    prediction = prediction_of(comparison.predicted_by)
    if prediction is None:
        return _fail(
            "X-V4",
            f"the stored prediction of {comparison.predicted_by!r} is not "
            f"retrievable; without it the outcome cannot be compared against "
            f"what was predicted [D-01, O-I4]",
        )
    return _ok(
        "X-V4",
        f"compared against the stored prediction of "
        f"{comparison.predicted_by!r}",
    )


def xv5_execution_precedes_observation(ctx: AcceptanceContext) -> RuleResult:
    """executed_at <= outcome_observed_at. [X-V5]

    Guarded against mixed timezone awareness, which would otherwise raise and
    take down the acceptance path instead of producing a failure record.
    [N-10]
    """
    if ctx.attributes.object_type is not ObjectType.EXECUTION_RECORD:
        return _skip("X-V5", "not an Execution Record")
    record = _record_of(ctx)
    if record is None:
        return _skip("X-V5", "no Execution Record payload supplied")

    executed, observed = record.executed_at, record.outcome_observed_at
    if (executed.tzinfo is None) != (observed.tzinfo is None):
        return _fail(
            "X-V5",
            "executed_at and outcome_observed_at mix timezone-aware and naive "
            "values",
        )
    if executed > observed:
        return _fail(
            "X-V5",
            f"executed_at ({executed.isoformat()}) is after "
            f"outcome_observed_at ({observed.isoformat()}); an outcome cannot "
            f"be observed before it was caused",
        )
    return _ok("X-V5", f"observed after {record.observation_lag} of execution")


def xv6_verification_present(ctx: AcceptanceContext) -> RuleResult:
    """outcome_verification present. [X-V6, M-47]

    PRESENCE ONLY. M-47 leaves outcome intake and its verification undefined
    as a single gap, so there is no standard against which adequacy could be
    judged. That the outcome was verified somehow is recordable and is
    recorded; whether the verification was sufficient is not answerable today
    and is not pretended to be.
    """
    if ctx.attributes.object_type is not ObjectType.EXECUTION_RECORD:
        return _skip("X-V6", "not an Execution Record")
    record = _record_of(ctx)
    if record is None:
        return _skip("X-V6", "no Execution Record payload supplied")

    if not (record.outcome_verification or "").strip():
        return _fail(
            "X-V6",
            "outcome_verification is absent; an unverified outcome lets the "
            "platform be taught anything",
        )
    return _ok(
        "X-V6",
        "verification recorded; adequacy unconstrained [M-47 open]",
    )


xv1_solution_version_resolves.rule_id = "X-V1"        # type: ignore[attr-defined]
xv2_valence_present.rule_id = "X-V2"                  # type: ignore[attr-defined]
xv3_attribution_reasoned.rule_id = "X-V3"             # type: ignore[attr-defined]
xv4_prediction_retrievable.rule_id = "X-V4"           # type: ignore[attr-defined]
xv5_execution_precedes_observation.rule_id = "X-V5"   # type: ignore[attr-defined]
xv6_verification_present.rule_id = "X-V6"             # type: ignore[attr-defined]

EXECUTION_RULES = (
    xv1_solution_version_resolves,
    xv2_valence_present,
    xv3_attribution_reasoned,
    xv4_prediction_retrievable,
    xv5_execution_precedes_observation,
    xv6_verification_present,
)


# ---------------------------------------------------------------------------
# Execution Record integrity constraints  [X-I1 .. X-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionViolation:
    """A breached Execution Record integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class ExecutionIntegrity:
    """Continuous verification of X-I1..X-I4. [IOM section 3.8]

    Detective, mirroring the earlier type verifiers. X-I1 matters most:
    survivorship bias operates after recording, by retiring the outcomes
    nobody wanted, and no write-time check can see that happen.
    """

    record_of: Callable[[str], "ExecutionRecord | None"]
    store: "object"
    _recorded_targets: dict[str, tuple] = field(default_factory=dict, init=False)

    def verify(self) -> tuple[ExecutionViolation, ...]:
        violations: list[ExecutionViolation] = []
        violations.extend(self._check_xi1())
        violations.extend(self._check_xi2())
        violations.extend(self._check_xi3())
        violations.extend(self._check_xi4())
        return tuple(violations)

    def _all_records(self) -> Iterable[tuple[str, "ExecutionRecord"]]:
        for stored in self.store.objects_of_type(ObjectType.EXECUTION_RECORD):
            record = self.record_of(stored.object_id)
            if record is not None:
                yield stored.object_id, record

    def _by_lineage(self) -> dict[str, list[tuple[int, str, "ExecutionRecord"]]]:
        grouped: dict[str, list[tuple[int, str, "ExecutionRecord"]]] = {}
        for object_id, record in self._all_records():
            grouped.setdefault(record.lineage_id, []).append(
                (record.attributes.version, object_id, record)
            )
        for versions in grouped.values():
            versions.sort(key=lambda item: item[0])
        return grouped

    # -- recording, for X-I2 ----------------------------------------------

    def record(self, execution_record: "ExecutionRecord") -> None:
        """Snapshot the evaluated objects at acceptance. [X-I2]"""
        for target in (
            execution_record.outcome_of_solution,
            execution_record.predicted_by,
        ):
            state = self._state_of(target)
            if state is not None:
                self._recorded_targets.setdefault(target, state)

    def _state_of(self, object_id: str) -> tuple | None:
        stored = self.store.find(object_id)
        if stored is None:
            return None
        confidence = stored.attributes.confidence
        return (
            round(confidence.effective_confidence, 12),
            round(confidence.evidential_support, 12),
            round(confidence.assertion_confidence, 12),
        )

    @property
    def recorded_target_count(self) -> int:
        return len(self._recorded_targets)

    def _check_xi1(self) -> list[ExecutionViolation]:
        """Unfavourable outcomes recorded with equal status. [X-I1]

        Survivorship bias is an explicit failure case and it is rated "very
        hard" to detect, because the surviving record looks complete. Three
        routes are closed, mirroring V-I1 at the Validation stage:

        - REJECTED: filing an unwelcome result as unverifiable.
        - ARCHIVED or RETRACTED while the executed Solution is still ACTIVE:
          retiring the outcome while the thing it judges keeps circulating.
        - An unfavourable outcome whose attribution reasoning was emptied,
          leaving the record present but saying nothing.

        SUPERSEDED and INVALIDATED are not suppression: the first is normal
        outcome accumulation, the second a cascade the record does not
        control.
        """
        violations: list[ExecutionViolation] = []
        withdrawn = (ObjectStatus.ARCHIVED, ObjectStatus.RETRACTED)
        for object_id, record in self._all_records():
            if not record.is_protected:
                continue
            stored = self.store.find(object_id)
            if stored is None:
                continue

            if stored.status is ObjectStatus.REJECTED:
                violations.append(
                    ExecutionViolation(
                        "X-I1", object_id,
                        f"{record.outcome_valence.value} outcome is REJECTED; "
                        f"REJECTED denotes an unverifiable or unattributable "
                        f"record, never an unwelcome result",
                    )
                )
            elif stored.status in withdrawn:
                executed = self.store.find(record.outcome_of_solution)
                if executed is not None and executed.status is ObjectStatus.ACTIVE:
                    violations.append(
                        ExecutionViolation(
                            "X-I1", object_id,
                            f"{record.outcome_valence.value} outcome is "
                            f"{stored.status.value} while the Solution it "
                            f"judges ({record.outcome_of_solution!r}) remains "
                            f"ACTIVE; the result was retired, the solution "
                            f"was not",
                        )
                    )

            if not (record.attribution_assessment.reasoning or "").strip():
                violations.append(
                    ExecutionViolation(
                        "X-I1", object_id,
                        f"{record.outcome_valence.value} outcome carries no "
                        f"attribution reasoning; a result stripped of meaning "
                        f"is suppressed in substance",
                    )
                )
        return violations

    def _check_xi2(self) -> list[ExecutionViolation]:
        """Never modifies the Solution or Opportunity it evaluates. [X-I2]

        Both are compared against snapshots taken when the record was
        accepted. Ground truth observes; it does not revise the inferences it
        judges, or the platform would be marking its own work.
        """
        violations: list[ExecutionViolation] = []
        seen: set[str] = set()
        for object_id, record in self._all_records():
            for target in (record.outcome_of_solution, record.predicted_by):
                recorded = self._recorded_targets.get(target)
                if recorded is None or target in seen:
                    continue
                seen.add(target)
                current = self._state_of(target)
                if current is None:
                    violations.append(
                        ExecutionViolation(
                            "X-I2", object_id,
                            f"evaluated object {target!r} is no longer "
                            f"retrievable; its state cannot be shown "
                            f"unmodified",
                        )
                    )
                elif current != recorded:
                    violations.append(
                        ExecutionViolation(
                            "X-I2", object_id,
                            f"evaluated object {target!r} changed after this "
                            f"record attached: recorded {recorded}, now "
                            f"{current}. An Execution Record never modifies "
                            f"what it evaluates",
                        )
                    )
        return violations

    def _check_xi3(self) -> list[ExecutionViolation]:
        """Attribution never overstated. [X-I3]

        Two mechanical checks against what the record itself discloses:

        - Confounders disclosed but nothing marked unattributable. If
          external factors or execution deviations are recorded, claiming the
          whole outcome for the solution contradicts the record's own
          evidence.
        - Execution deviated from the Solution, yet the deviation goes
          unmentioned in the attribution reasoning. The outcome then tests
          something other than what the platform proposed, and learning from
          it would attribute results to the wrong cause.

        Whether an attribution is materially correct is unanswerable here --
        the IOM rates attribution error "very hard" to detect and no
        methodology is defined. Only self-contradiction is caught.
        """
        violations: list[ExecutionViolation] = []
        for object_id, record in self._all_records():
            assessment = record.attribution_assessment

            if record.has_confounders and assessment.claims_total_attribution:
                disclosed = list(record.external_factors) + list(
                    record.execution_deviations
                )
                violations.append(
                    ExecutionViolation(
                        "X-I3", object_id,
                        f"claims the whole outcome for the solution while "
                        f"disclosing confounders {disclosed}; nothing is "
                        f"marked unattributable",
                    )
                )

            if record.deviated:
                # The reasoning must engage with the DISCLOSED deviation, not
                # merely contain the word. A bare "no deviations of note"
                # satisfied an earlier substring test while contradicting the
                # record's own disclosure -- a hand-wave passing as an
                # account. Matching on the deviation's own content words
                # closes that, and unmatched cases are reported rather than
                # judged: this detects silence, not inadequacy.
                reasoning = _normalised(record.attribution_assessment.reasoning)
                mentioned = any(
                    _mentions(reasoning, deviation)
                    for deviation in record.execution_deviations
                )
                if not mentioned:
                    violations.append(
                        ExecutionViolation(
                            "X-I3", object_id,
                            f"execution deviated from the Solution "
                            f"({list(record.execution_deviations)}) but the "
                            f"attribution does not account for it; the "
                            f"outcome tests something other than what was "
                            f"proposed",
                        )
                    )
        return violations

    def _check_xi4(self) -> list[ExecutionViolation]:
        """Links to the specific Solution version executed. [X-I4, R-1a]

        The reference must resolve to a Solution -- an object_id identifies
        one version, so a reference that resolves is version-specific by
        construction. Across a supersession chain the reference must also stay
        put: later outcomes accumulate against the SAME executed version, and
        retargeting would silently reassign results to a version that was
        never run.
        """
        violations: list[ExecutionViolation] = []
        for object_id, record in self._all_records():
            executed = self.store.find(record.outcome_of_solution)
            if executed is None:
                violations.append(
                    ExecutionViolation(
                        "X-I4", object_id,
                        f"executed Solution {record.outcome_of_solution!r} is "
                        f"not stored; the outcome is attached to nothing",
                    )
                )
            elif executed.object_type is not ObjectType.SOLUTION:
                violations.append(
                    ExecutionViolation(
                        "X-I4", object_id,
                        f"outcome_of_solution {record.outcome_of_solution!r} "
                        f"is a {executed.object_type.value}, not a Solution",
                    )
                )

        for versions in self._by_lineage().values():
            for (_, _, earlier), (_, later_id, later) in zip(
                versions, versions[1:]
            ):
                if later.outcome_of_solution != earlier.outcome_of_solution:
                    violations.append(
                        ExecutionViolation(
                            "X-I4", later_id,
                            f"executed Solution changed across versions: "
                            f"{earlier.outcome_of_solution!r} -> "
                            f"{later.outcome_of_solution!r}; outcomes "
                            f"accumulate against the version actually run",
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class ExecutionRegistry:
    """Holds Execution Record payloads. [IOM section 3.8]

    Mirrors the earlier registries. It will hold nothing until C-02 is
    resolved, because no engine may create an Execution Record and V7 refuses
    every write. The registry exists so the type is complete and ready, not
    because a path to populating it exists today.

    Conflicting outcome reports are surfaced, never resolved: like
    conflicting Validations, disagreement is information.
    """

    store: "object"
    _payloads: dict[str, ExecutionRecord] = field(default_factory=dict, init=False)
    _integrity: "ExecutionIntegrity | None" = field(default=None, init=False)

    def register(self, record: ExecutionRecord) -> ExecutionRecord:
        self._payloads[record.object_id] = record
        self.integrity().record(record)
        return record

    def get(self, object_id: str) -> ExecutionRecord | None:
        return self._payloads.get(object_id)

    def active_records(self) -> tuple[ExecutionRecord, ...]:
        found = []
        for object_id, record in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                found.append(record)
        return tuple(found)

    def for_solution(self, solution_ref: str) -> tuple[ExecutionRecord, ...]:
        """Outcomes recorded against one executed Solution version. [X-I4]"""
        return tuple(
            r for r in self._payloads.values()
            if r.outcome_of_solution == solution_ref
        )

    def unfavourable_outcomes(self) -> tuple[ExecutionRecord, ...]:
        """Unwelcome results, retained with equal status. [X-I1]"""
        return tuple(r for r in self._payloads.values() if r.is_unfavourable)

    def conflicts_for(
        self, solution_ref: str
    ) -> tuple[tuple[ExecutionRecord, ExecutionRecord], ...]:
        """Pairs of outcome reports on one Solution that disagree.

        Surfaced for the caller to record as CONTRADICTS. No winner is
        selected: conflicting reports are information about the outcome's
        reliability.
        """
        records = self.for_solution(solution_ref)
        pairs: list[tuple[ExecutionRecord, ExecutionRecord]] = []
        for i, left in enumerate(records):
            for right in records[i + 1:]:
                if left.outcome_valence is not right.outcome_valence:
                    pairs.append((left, right))
        return tuple(pairs)

    def integrity(self) -> ExecutionIntegrity:
        if self._integrity is None:
            self._integrity = ExecutionIntegrity(
                record_of=self.get, store=self.store
            )
        return self._integrity

    def __len__(self) -> int:
        return len(self._payloads)
