"""Validation object type: what was tested, how, and what happened.

Task: T01.7.7

Architecture References:
- V-V1   tests_claim resolves to a specific claim, not a whole object
- V-V2   validation_method and method_detail present
- V-V3   result present and drawn from the defined set
- V-V4   result_interpretation present, including for negative results
- V-V5   scope_limitations present
- V-V6   Method detail sufficient to repeat the test
- V-I1   Negative results never suppressed, downgraded, or REJECTED
- V-I2   Never modifies the object it tests
- V-I3   Never proposes alternative solutions
- V-I4   Result never reinterpreted after recording
- R-2    A negative result is ACTIVE; REJECTED denotes an unusable record
- R-3    evidential_support reflects method rigour; a high-confidence
         negative result is coherent and valuable
- R-6    DERIVES_FROM Solution; TESTS a claim; CONTRADICTS Validation
- M-32   Validation methodology OPEN and BLOCKING -- no method vocabulary
- M-31   Gate ownership OPEN: Validation reports, it does not gate
- M-42   Experiment lifecycle OPEN
- C-05   Validation / Experiment Registry boundary OPEN; experiment_ref
         optional solely for that reason
- N-19   Registry holds mutable state; Validation holds immutable results
- IOM    section 3.7

Validation is what distinguishes the platform's output from plausible
speculation. The object exists to make testing AUDITABLE: what was tested,
how, and what happened -- recorded so that a negative result is as durable
and as visible as a positive one.

It attaches to INDIVIDUAL CLAIMS, never to an object as a whole. A Solution
carries multiple assumptions of differing criticality; validating "the
solution" would obscure which were actually tested and which were not.

THE SINGLE MOST IMPORTANT STATUS RULE IN THE SPECIFICATION: a negative result
is ACTIVE, not REJECTED. REJECTED describes an unusable RECORD, not an
unfavourable FINDING. Conflating them would let negative results be quietly
filed as failures of the test rather than findings about the world -- the
negative-result-suppression failure mode, which destroys the learning signal
Principle 5 depends on. V-I1 enforces this continuously.

BLOCKING CONDITION, stated deliberately. M-32 leaves the nature of validation
undefined -- whether evidence-based, analytical, experimental or market-based
-- so `validation_method` has NO DEFINED VOCABULARY. PKP v2 names this the
largest single specification gap. This module therefore requires the method to
be PRESENT and non-empty (V-V2) but does not constrain its value, and it
introduces no method taxonomy. Note the difference from M-14 at the
Opportunity stage: M-14 made `score` unpopulatable and so blocked ACTIVE
outright, whereas the IOM's own Validation example is recorded ACTIVE with the
method shown as "<VOCABULARY UNDEFINED>". Presence is enforceable today;
legitimacy of the value is not, and is not pretended to be.

Scope: the Validation type and its rules. Falsifiability enforcement
(T07.3.2), the post-validation gate (T07.3.7, M-31) and the Experiment
Registry boundary (T07.1.1, C-05) are deliberately absent.
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


class ValidationError(Exception):
    """Base class for Validation violations."""


class ClaimReferenceError(ValidationError):
    """tests_claim absent, malformed, or naming a whole object. [V-V1]"""


class MethodError(ValidationError):
    """validation_method or method_detail absent. [V-V2, V-V6]"""


class ResultError(ValidationError):
    """result absent or outside the defined set. [V-V3]"""


class InterpretationError(ValidationError):
    """result_interpretation absent. [V-V4]"""


class ScopeLimitationError(ValidationError):
    """scope_limitations absent. [V-V5]"""


class NegativeResultSuppressionError(ValidationError):
    """A negative result was REJECTED for being negative. [V-I1, R-2]"""


class ValidationResult(str, Enum):
    """The four defined results. [V-V3, IOM section 3.7]

    A CLOSED set, unlike validation_method: the IOM enumerates these four
    explicitly, so they are enforceable today even though M-32 leaves the
    method vocabulary undefined.
    """

    SUPPORTED = "SUPPORTED"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"

    @property
    def is_negative(self) -> bool:
        """Whether the finding is unfavourable to the claim. [V-I1]

        NOT_SUPPORTED and PARTIALLY_SUPPORTED are both unfavourable in part.
        Both are protected from suppression: partial support is where
        over-claiming is easiest, because an unfavourable half can be quietly
        reported as a favourable whole.
        """
        return self in (
            ValidationResult.NOT_SUPPORTED,
            ValidationResult.PARTIALLY_SUPPORTED,
        )

    @property
    def is_favourable(self) -> bool:
        return self is ValidationResult.SUPPORTED


# Results that must never be REJECTED for being what they are. [V-I1]
PROTECTED_RESULTS: frozenset[ValidationResult] = frozenset(
    {
        ValidationResult.NOT_SUPPORTED,
        ValidationResult.PARTIALLY_SUPPORTED,
        ValidationResult.INCONCLUSIVE,
    }
)


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


# ---------------------------------------------------------------------------
# Claim reference  [V-V1]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaimReference:
    """A reference to ONE claim inside an object. [V-V1, R-6]

    Whole-object validation is not meaningful, so the claim identifier is
    mandatory and separate from the object reference. A Validation naming
    only an object cannot say which assumption it tested, which is exactly
    the ambiguity V-V1 exists to prevent.

    claim_id is opaque here. At the Solution stage it is an assumption_id;
    the IOM permits TESTS against Fact, Problem, Pattern and Opportunity
    claims too, and no single vocabulary spans them.
    """

    object_id: str
    claim_id: str

    def __post_init__(self) -> None:
        if not (self.object_id or "").strip():
            raise ClaimReferenceError(
                "tests_claim requires the object containing the claim [V-V1]"
            )
        if not (self.claim_id or "").strip():
            raise ClaimReferenceError(
                f"tests_claim on {self.object_id!r} names no specific claim; "
                f"whole-object validation obscures which assumptions were "
                f"actually tested [V-V1]"
            )

    def __str__(self) -> str:  # pragma: no cover - diagnostic convenience
        return f"{self.object_id} / {self.claim_id}"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Validation:
    """A record that a specific claim was tested. [IOM section 3.7]

    Composes the universal contract with the Validation-specific payload.
    Frozen and, unusually, rarely versioned: a concluded test is a historical
    fact. Re-testing produces a NEW Validation object, not a new version, so
    both results survive. Versions exist only to correct recording errors,
    which V-I4 requires to carry a rationale.
    """

    attributes: UniversalAttributes
    tests_claim: ClaimReference
    validation_method: str
    method_detail: str
    result: ValidationResult
    result_detail: str
    result_interpretation: str
    validated_at: datetime
    scope_limitations: str

    # Optional attributes [IOM section 3.7]
    experiment_ref: str | None = None       # optional solely due to C-05
    confidence_impact: str | None = None
    contradicting_evidence: tuple[str, ...] = ()
    follow_up_required: str | None = None
    correction_rationale: str | None = None  # required on a version [V-I4]

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.VALIDATION:
            raise ValidationError(
                f"expected Validation, got {self.attributes.object_type.value}"
            )
        if self.attributes.produced_by_engine is not Engine.VALIDATION:
            raise ValidationError(
                f"only the Validation engine may create Validations; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )

        if not isinstance(self.tests_claim, ClaimReference):
            raise ClaimReferenceError("tests_claim is required [V-V1]")
        if not isinstance(self.result, ValidationResult):
            raise ResultError(
                f"result must be one of "
                f"{sorted(r.value for r in ValidationResult)}, got "
                f"{self.result!r} [V-V3]"
            )
        if not isinstance(self.validated_at, datetime):
            raise ValidationError("validated_at must be a datetime")

        # V-V2 / V-V6: the method must be recorded to a repeatable standard.
        # The VALUE of validation_method is unconstrained -- M-32 defines no
        # vocabulary, and inventing one here would close that gap silently.
        if not (self.validation_method or "").strip():
            raise MethodError(
                "validation_method is required; an unrecorded method is "
                "unrepeatable and breaches Principle 3 "
                "[V-V2, M-32 vocabulary open]"
            )
        if not (self.method_detail or "").strip():
            raise MethodError(
                "method_detail is required to a standard sufficient for "
                "repetition [V-V2, V-V6]"
            )
        if not (self.result_detail or "").strip():
            raise ValidationError(
                "result_detail is required; what was observed must be "
                "recorded separately from what it is taken to mean"
            )
        # V-V4: interpretation is required for EVERY result, negative ones
        # included. An uninterpreted negative is the easiest to bury.
        if not (self.result_interpretation or "").strip():
            raise InterpretationError(
                "result_interpretation is required, including for negative "
                "results [V-V4]"
            )
        # V-V5: what the test does NOT establish.
        if not (self.scope_limitations or "").strip():
            raise ScopeLimitationError(
                "scope_limitations is required; stating what was not "
                "established is what makes over-claiming visible [V-V5]"
            )

        # A Validation derives from the object containing the tested claim.
        upstream = {ref.object_id for ref in self.attributes.derives_from}
        if self.tests_claim.object_id not in upstream:
            raise ClaimReferenceError(
                f"tests_claim names {self.tests_claim.object_id!r}, which is "
                f"not in derives_from; a Validation derives from the object "
                f"containing the claim it tests [R-6]"
            )

        # V-I1 at construction: a negative finding may not be filed as an
        # unusable record. This is the suppression path, closed at the
        # earliest possible point.
        if self.attributes.status is ObjectStatus.REJECTED:
            if self.result in PROTECTED_RESULTS:
                raise NegativeResultSuppressionError(
                    f"a {self.result.value} result may not be REJECTED; "
                    f"REJECTED denotes an unusable record, not an unfavourable "
                    f"finding. Suppressing it would destroy the learning "
                    f"signal Principle 5 depends on [V-I1, R-2]"
                )

        # V-I4: a correction is a new version and must say why.
        if self.attributes.version > 1:
            if not (self.correction_rationale or "").strip():
                raise ValidationError(
                    "a new version of a Validation is permitted only to "
                    "correct a recording error, and requires a "
                    "correction_rationale [V-I4]"
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
    def tested_object_id(self) -> str:
        return self.tests_claim.object_id

    @property
    def claim_id(self) -> str:
        return self.tests_claim.claim_id

    @property
    def is_negative(self) -> bool:
        """Whether the finding is unfavourable. [V-I1]"""
        return self.result.is_negative

    @property
    def is_protected(self) -> bool:
        """Whether V-I1 forbids REJECTING this result. [V-I1]"""
        return self.result in PROTECTED_RESULTS

    def result_fingerprint(self) -> tuple:
        """Immutable signature of the finding as recorded. [V-I4]

        A result is never reinterpreted after recording. The platform needs a
        way to ask whether a stored finding still says what it said, which is
        what the Feedback Engine relies on when measuring prediction error.
        """
        return (
            self.result.value,
            _normalised(self.result_detail),
            _normalised(self.result_interpretation),
            _normalised(self.scope_limitations),
        )

    def tests_same_claim_as(self, other: "Validation") -> bool:
        """Whether both tested the same claim. [CONTRADICTS, R-6]"""
        return self.tests_claim == other.tests_claim

    def disagrees_with(self, other: "Validation") -> bool:
        """Whether two tests of one claim reached different findings.

        Disagreement is INFORMATION about the claim's robustness, represented
        via CONTRADICTS and never resolved by selecting a winner.
        """
        return self.tests_same_claim_as(other) and self.result is not other.result


# ---------------------------------------------------------------------------
# Validation-specific acceptance rules  [V-V1 .. V-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _validation_of(ctx: AcceptanceContext) -> "Validation | None":
    return getattr(ctx, "validation", None)


def vv1_tests_a_specific_claim(ctx: AcceptanceContext) -> RuleResult:
    """tests_claim resolves to a specific claim, not a whole object. [V-V1]

    Two halves. The reference must name a claim, and where the tested object
    exposes a claim set, the named claim must exist within it. A Validation
    against a claim the object does not have is untraceable: nothing can say
    what was tested.
    """
    if ctx.attributes.object_type is not ObjectType.VALIDATION:
        return _skip("V-V1", "not a Validation")
    validation = _validation_of(ctx)
    if validation is None:
        return _skip("V-V1", "no Validation payload supplied")

    reference = validation.tests_claim
    if not (reference.claim_id or "").strip():
        return _fail(
            "V-V1",
            "tests_claim names no specific claim; whole-object validation is "
            "not meaningful",
        )

    if ctx.resolve_type is not None:
        actual = ctx.resolve_type(reference.object_id)
        if actual is None:
            return _fail(
                "V-V1",
                f"tested object {reference.object_id!r} does not resolve",
            )

    claims_of = getattr(ctx, "claims_of_object", None)
    if claims_of is None:
        return _skip(
            "V-V1",
            f"claim {reference.claim_id!r} named; no claim provider to verify "
            f"it exists",
        )
    available = claims_of(reference.object_id)
    if available is None:
        return _skip(
            "V-V1",
            f"tested object {reference.object_id!r} exposes no claim set to "
            f"check against",
        )
    if reference.claim_id not in available:
        return _fail(
            "V-V1",
            f"claim {reference.claim_id!r} does not exist on "
            f"{reference.object_id!r}; available: {sorted(available)}",
        )
    return _ok("V-V1", f"tests {reference.claim_id!r} specifically")


def vv2_method_recorded(ctx: AcceptanceContext) -> RuleResult:
    """validation_method and method_detail present. [V-V2, M-32]

    PRESENCE ONLY. M-32 leaves the nature of validation undefined, so no
    vocabulary constrains the method's value and none is invented here.
    Whether the stated method is a legitimate one is unanswerable today; that
    it was stated at all is enforceable, and is enforced.
    """
    if ctx.attributes.object_type is not ObjectType.VALIDATION:
        return _skip("V-V2", "not a Validation")
    validation = _validation_of(ctx)
    if validation is None:
        return _skip("V-V2", "no Validation payload supplied")

    missing = [
        name
        for name in ("validation_method", "method_detail")
        if not (getattr(validation, name) or "").strip()
    ]
    if missing:
        return _fail(
            "V-V2",
            f"method not recorded: {sorted(missing)}; an unrepeatable test "
            f"breaches Principle 3",
        )
    return _ok(
        "V-V2",
        f"method {validation.validation_method!r} recorded; vocabulary "
        f"unconstrained [M-32 open, blocking]",
    )


def vv3_result_in_defined_set(ctx: AcceptanceContext) -> RuleResult:
    """result present and drawn from the defined set. [V-V3]"""
    if ctx.attributes.object_type is not ObjectType.VALIDATION:
        return _skip("V-V3", "not a Validation")
    validation = _validation_of(ctx)
    if validation is None:
        return _skip("V-V3", "no Validation payload supplied")

    if not isinstance(validation.result, ValidationResult):
        return _fail(
            "V-V3",
            f"result {validation.result!r} is outside the defined set "
            f"{sorted(r.value for r in ValidationResult)}",
        )
    if not (validation.result_detail or "").strip():
        return _fail(
            "V-V3",
            "result recorded with no result_detail; what was observed must be "
            "separable from what it is taken to mean",
        )
    return _ok("V-V3", validation.result.value)


def vv4_interpretation_present(ctx: AcceptanceContext) -> RuleResult:
    """result_interpretation present, including for negative results. [V-V4]

    The "including for negative results" clause is the substance of the rule.
    An uninterpreted negative is the easiest finding to bury, so the check
    reports negativity explicitly rather than treating all results alike.
    """
    if ctx.attributes.object_type is not ObjectType.VALIDATION:
        return _skip("V-V4", "not a Validation")
    validation = _validation_of(ctx)
    if validation is None:
        return _skip("V-V4", "no Validation payload supplied")

    if not (validation.result_interpretation or "").strip():
        return _fail(
            "V-V4",
            f"a {validation.result.value} result carries no interpretation; "
            f"an uninterpreted result states nothing about the claim",
        )
    if validation.is_negative:
        return _ok(
            "V-V4",
            f"{validation.result.value} interpreted; negative findings are "
            f"durable knowledge [V-I1]",
        )
    return _ok("V-V4", f"{validation.result.value} interpreted")


def vv5_scope_limitations_present(ctx: AcceptanceContext) -> RuleResult:
    """scope_limitations present. [V-V5]

    Counters scope mismatch: validating a narrow proxy and treating it as
    whole-solution validation. Requiring an explicit statement of what was
    NOT established is what makes over-claiming visible.
    """
    if ctx.attributes.object_type is not ObjectType.VALIDATION:
        return _skip("V-V5", "not a Validation")
    validation = _validation_of(ctx)
    if validation is None:
        return _skip("V-V5", "no Validation payload supplied")

    if not (validation.scope_limitations or "").strip():
        return _fail(
            "V-V5",
            "scope_limitations absent; without stating what was not "
            "established, a narrow test reads as whole-object assurance",
        )
    return _ok("V-V5", "scope limitations stated")


def vv6_method_detail_repeatable(ctx: AcceptanceContext) -> RuleResult:
    """Method detail sufficient to repeat the test. [V-V6]

    STRUCTURAL PROXY ONLY, and said plainly. Whether prose genuinely permits
    repetition is a judgement no structural rule can make; M-32 defines no
    reproducibility standard to check against. What is checked is that the
    detail is materially more than a restatement of the method label -- the
    method-opacity failure in its most detectable form.
    """
    if ctx.attributes.object_type is not ObjectType.VALIDATION:
        return _skip("V-V6", "not a Validation")
    validation = _validation_of(ctx)
    if validation is None:
        return _skip("V-V6", "no Validation payload supplied")

    detail = (validation.method_detail or "").strip()
    if not detail:
        return _fail("V-V6", "method_detail is absent; the test is unrepeatable")
    if _normalised(detail) == _normalised(validation.validation_method):
        return _fail(
            "V-V6",
            "method_detail merely restates validation_method; it adds nothing "
            "a second tester could follow",
        )
    return _ok(
        "V-V6",
        "method detail recorded; genuine reproducibility unverifiable "
        "[M-32 open]",
    )


vv1_tests_a_specific_claim.rule_id = "V-V1"        # type: ignore[attr-defined]
vv2_method_recorded.rule_id = "V-V2"               # type: ignore[attr-defined]
vv3_result_in_defined_set.rule_id = "V-V3"         # type: ignore[attr-defined]
vv4_interpretation_present.rule_id = "V-V4"        # type: ignore[attr-defined]
vv5_scope_limitations_present.rule_id = "V-V5"     # type: ignore[attr-defined]
vv6_method_detail_repeatable.rule_id = "V-V6"      # type: ignore[attr-defined]

VALIDATION_RULES = (
    vv1_tests_a_specific_claim,
    vv2_method_recorded,
    vv3_result_in_defined_set,
    vv4_interpretation_present,
    vv5_scope_limitations_present,
    vv6_method_detail_repeatable,
)


# ---------------------------------------------------------------------------
# Validation integrity constraints  [V-I1 .. V-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationViolation:
    """A breached Validation integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class ValidationIntegrity:
    """Continuous verification of V-I1..V-I4. [IOM section 3.7]

    Detective, mirroring the earlier type verifiers. V-I1 is the one that
    matters most: suppression happens after recording, by transitioning a
    negative finding out of ACTIVE, and no write-time check can see that.
    """

    validation_of: Callable[[str], "Validation | None"]
    store: "object"
    _recorded_results: dict[str, tuple] = field(default_factory=dict, init=False)
    _recorded_targets: dict[str, tuple] = field(default_factory=dict, init=False)

    def verify(self) -> tuple[ValidationViolation, ...]:
        violations: list[ValidationViolation] = []
        violations.extend(self._check_vi1())
        violations.extend(self._check_vi2())
        violations.extend(self._check_vi3())
        violations.extend(self._check_vi4())
        return tuple(violations)

    def _all_validations(self) -> Iterable[tuple[str, "Validation"]]:
        for stored in self.store.objects_of_type(ObjectType.VALIDATION):
            validation = self.validation_of(stored.object_id)
            if validation is not None:
                yield stored.object_id, validation

    # -- recording, for V-I2 and V-I4 -------------------------------------

    def record(self, validation: "Validation") -> None:
        """Snapshot the finding and its target at acceptance. [V-I2, V-I4]"""
        self._recorded_results.setdefault(
            validation.object_id, validation.result_fingerprint()
        )
        target = self._target_state_of(validation.tested_object_id)
        if target is not None:
            self._recorded_targets.setdefault(
                validation.tested_object_id, target
            )

    def _target_state_of(self, object_id: str) -> tuple | None:
        """The tested object's own assessment, which V-I2 forbids changing."""
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
    def recorded_result_count(self) -> int:
        return len(self._recorded_results)

    def _check_vi1(self) -> list[ValidationViolation]:
        """Negative results never suppressed, downgraded, or REJECTED. [V-I1]

        The platform's guarantee that a finding about the world survives being
        unwelcome. Three suppression routes are checked:

        - REJECTED: filing an unfavourable finding as an unusable record.
        - ARCHIVED or RETRACTED while its tested object is still live:
          retiring the inconvenient half of the record while the claim it
          bears on continues to circulate. RETRACTED is included because the
          IOM's Validation transition table does not offer it at all --
          "withdrawn at source" describes Evidence whose basis the external
          world revoked, not a concluded test, which is a historical fact.
        - A negative result whose interpretation was emptied, leaving the
          finding technically present but saying nothing.

        SUPERSEDED and INVALIDATED are NOT treated as suppression: the first
        is the sanctioned correction route under V-I4, and the second is a
        cascade the Validation does not control.
        """
        violations: list[ValidationViolation] = []
        # Statuses that retire a record without the cascade or correction
        # routes that legitimately produce them. [IOM section 3.7]
        withdrawn = (ObjectStatus.ARCHIVED, ObjectStatus.RETRACTED)
        for object_id, validation in self._all_validations():
            if not validation.is_protected:
                continue
            stored = self.store.find(object_id)
            if stored is None:
                continue

            if stored.status is ObjectStatus.REJECTED:
                violations.append(
                    ValidationViolation(
                        "V-I1", object_id,
                        f"{validation.result.value} result is REJECTED; "
                        f"REJECTED denotes an unusable record, never an "
                        f"unfavourable finding",
                    )
                )
            elif stored.status in withdrawn:
                target = self.store.find(validation.tested_object_id)
                if target is not None and target.status is ObjectStatus.ACTIVE:
                    violations.append(
                        ValidationViolation(
                            "V-I1", object_id,
                            f"{validation.result.value} result is "
                            f"{stored.status.value} while the object it tests "
                            f"({validation.tested_object_id!r}) remains "
                            f"ACTIVE; the finding was retired, the claim was "
                            f"not",
                        )
                    )

            if not (validation.result_interpretation or "").strip():
                violations.append(
                    ValidationViolation(
                        "V-I1", object_id,
                        f"{validation.result.value} result carries no "
                        f"interpretation; a finding stripped of meaning is "
                        f"suppressed in substance",
                    )
                )
        return violations

    def _check_vi2(self) -> list[ValidationViolation]:
        """Never modifies the object it tests. [V-I2]

        Compares the tested object's assessment against the snapshot taken
        when the Validation was accepted. A test that changes what it tests
        is not a test; it is an edit, and the independence Validation exists
        to provide would be gone.
        """
        violations: list[ValidationViolation] = []
        seen: set[str] = set()
        for object_id, validation in self._all_validations():
            target_id = validation.tested_object_id
            recorded = self._recorded_targets.get(target_id)
            if recorded is None or target_id in seen:
                continue
            seen.add(target_id)
            current = self._target_state_of(target_id)
            if current is None:
                violations.append(
                    ValidationViolation(
                        "V-I2", object_id,
                        f"tested object {target_id!r} is no longer "
                        f"retrievable; its state cannot be shown unmodified",
                    )
                )
            elif current != recorded:
                violations.append(
                    ValidationViolation(
                        "V-I2", object_id,
                        f"tested object {target_id!r} changed after this "
                        f"Validation attached: recorded {recorded}, now "
                        f"{current}. A Validation never modifies what it "
                        f"tests",
                    )
                )
        return violations

    def _check_vi3(self) -> list[ValidationViolation]:
        """Never proposes alternative solutions. [V-I3]

        Structural, not semantic. A Validation may not carry an ADDRESSES
        relationship, which is how a Solution asserts that it tackles
        something -- and it may not derive from anything other than the
        object whose claim it tests. A validation that improves the solution
        has crossed into Solution Intelligence and can no longer be an
        impartial test of it.

        Whether the prose SUGGESTS an alternative is a semantic judgement and
        is NOT claimed to be caught.
        """
        violations: list[ValidationViolation] = []
        graph = getattr(self.store, "graph", None)
        for object_id, validation in self._all_validations():
            stored = self.store.find(object_id)
            if stored is None:
                continue
            extra = sorted(
                ref.object_id
                for ref in stored.attributes.derives_from
                if ref.object_id != validation.tested_object_id
            )
            if extra:
                violations.append(
                    ValidationViolation(
                        "V-I3", object_id,
                        f"derives from {extra} beyond the object it tests; a "
                        f"Validation that reaches further is proposing, not "
                        f"testing",
                    )
                )
            if graph is None or not graph.contains(object_id):
                continue
            from oip.enums import RelationshipType

            proposed = sorted(
                graph.parents(object_id, RelationshipType.ADDRESSES)
            )
            if proposed:
                violations.append(
                    ValidationViolation(
                        "V-I3", object_id,
                        f"asserts ADDRESSES against {proposed}; proposing a "
                        f"solution forfeits the independence that makes the "
                        f"test impartial",
                    )
                )
        return violations

    def _check_vi4(self) -> list[ValidationViolation]:
        """Result never reinterpreted after recording. [V-I4]

        Corrections are new versions with rationale, never edits. What the
        platform found at the time must remain retrievable, because the
        Feedback Engine measures against it.
        """
        violations: list[ValidationViolation] = []
        for object_id, validation in self._all_validations():
            recorded = self._recorded_results.get(object_id)
            if recorded is None:
                continue
            current = validation.result_fingerprint()
            if current != recorded:
                violations.append(
                    ValidationViolation(
                        "V-I4", object_id,
                        f"result reinterpreted after recording: was "
                        f"{recorded[0]}, now {current[0]}. Corrections are new "
                        f"versions with rationale, not edits",
                    )
                )

        # A later version must state why it corrects the earlier record.
        by_lineage: dict[str, list[tuple[int, str, "Validation"]]] = {}
        for object_id, validation in self._all_validations():
            by_lineage.setdefault(validation.lineage_id, []).append(
                (validation.attributes.version, object_id, validation)
            )
        for versions in by_lineage.values():
            versions.sort(key=lambda item: item[0])
            for _, later_id, later in versions[1:]:
                if not (later.correction_rationale or "").strip():
                    violations.append(
                        ValidationViolation(
                            "V-I4", later_id,
                            "supersedes an earlier Validation without a "
                            "correction_rationale; re-tests are new objects, "
                            "versions are corrections only",
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class ValidationRegistry:
    """Holds Validation payloads and resolves findings per claim. [V-V1]

    Mirrors the earlier registries. Conflicting results are SURFACED, never
    resolved: two tests disagreeing is information about the claim's
    robustness, and selecting a winner would discard it.

    No gate is offered. Validation reports; it does not gate, and gate
    ownership is unassigned under M-31.
    """

    store: "object"
    _payloads: dict[str, Validation] = field(default_factory=dict, init=False)
    _integrity: "ValidationIntegrity | None" = field(default=None, init=False)

    def register(self, validation: Validation) -> Validation:
        self._payloads[validation.object_id] = validation
        self.integrity().record(validation)
        return validation

    def get(self, object_id: str) -> Validation | None:
        return self._payloads.get(object_id)

    def active_validations(self) -> tuple[Validation, ...]:
        found = []
        for object_id, validation in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                found.append(validation)
        return tuple(found)

    def for_claim(self, object_id: str, claim_id: str) -> tuple[Validation, ...]:
        """Every test of one specific claim. [V-V1]"""
        reference = ClaimReference(object_id=object_id, claim_id=claim_id)
        return tuple(
            v for v in self._payloads.values() if v.tests_claim == reference
        )

    def for_object(self, object_id: str) -> tuple[Validation, ...]:
        return tuple(
            v for v in self._payloads.values() if v.tested_object_id == object_id
        )

    def negative_results(self) -> tuple[Validation, ...]:
        """Unfavourable findings. Retained with equal status. [V-I1]"""
        return tuple(v for v in self._payloads.values() if v.is_negative)

    def untested_claims(
        self, object_id: str, claim_ids: Iterable[str]
    ) -> tuple[str, ...]:
        """Claims with no Validation against them.

        The untested-critical-assumption failure is invisible unless someone
        asks; this is how they ask. It reports, it does not gate [M-31].
        """
        tested = {v.claim_id for v in self.for_object(object_id)}
        return tuple(sorted(set(claim_ids) - tested))

    def conflicts_for(
        self, object_id: str, claim_id: str
    ) -> tuple[tuple[Validation, Validation], ...]:
        """Pairs of tests on one claim that disagree. [CONTRADICTS]

        Surfaced for the caller to record as CONTRADICTS. No winner is
        selected: disagreement is information about robustness.
        """
        tests = self.for_claim(object_id, claim_id)
        pairs: list[tuple[Validation, Validation]] = []
        for i, left in enumerate(tests):
            for right in tests[i + 1:]:
                if left.disagrees_with(right):
                    pairs.append((left, right))
        return tuple(pairs)

    def integrity(self) -> ValidationIntegrity:
        if self._integrity is None:
            self._integrity = ValidationIntegrity(
                validation_of=self.get, store=self.store
            )
        return self._integrity

    def __len__(self) -> int:
        return len(self._payloads)
