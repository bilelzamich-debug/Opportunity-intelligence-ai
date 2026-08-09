"""Universal integrity constraints I1-I8 as continuous invariants.

Task: T01.4.5

Architecture References:
- I1     Content immutable; only status may transition
- I2     object_id never reused
- I3     Lineage references never repoint
- I4     Referenced objects never hard-deleted
- I5     Exactly one version per lineage_id is ACTIVE
- I6     Upstream RETRACTED/INVALIDATED => dependents INVALIDATED
- I7     Confidence ceiling holds after any upstream change
- I8     REJECTED objects are never consumed as input
- N-8    Store enforces; rules specified in the object model
- N-10   Violations produce records, never unexpected exceptions
- R-2    Lifecycle; is_consumable() defines what may be read
- IOM    section 1.4

Validation rules (V1-V12) are ACCEPTANCE-TIME checks: they run once, when an
object is written. Integrity constraints are CONTINUOUS invariants: they must
hold at every moment thereafter, including after cascades, supersessions and
status transitions that no single write can foresee.

Two enforcement modes, deliberately distinct:

  PREVENTIVE  -- refuse an operation that would breach a constraint.
                 I8 in particular must be preventive: once a conclusion is
                 drawn from rejected knowledge, the damage is already done.

  DETECTIVE   -- audit the store and report existing breaches. Necessary
                 because I1-I7 can be breached by paths no write controls:
                 direct corruption, partial failure, or an upstream change
                 that invalidates a downstream ceiling long after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from oip.acceptance import (
    AcceptanceContext,
    FailureRecord,
    RuleOutcome,
    RuleResult,
)
from oip.contract import utc_now
from oip.enums import ObjectStatus, ObjectType
from oip.lifecycle import is_consumable


class ConstraintMode(str, Enum):
    """How a constraint is enforced."""

    PREVENTIVE = "PREVENTIVE"
    DETECTIVE = "DETECTIVE"


@dataclass(frozen=True)
class Violation:
    """A breached integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str
    object_type: ObjectType | None = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic convenience
        return f"[{self.constraint_id}] {self.object_id}: {self.detail}"


@dataclass(frozen=True)
class IntegrityReport:
    """Result of a continuous integrity audit."""

    violations: tuple[Violation, ...] = ()
    checked_objects: int = 0
    constraints_run: tuple[str, ...] = ()

    @property
    def holds(self) -> bool:
        return not self.violations

    def __bool__(self) -> bool:
        return self.holds

    def for_constraint(self, constraint_id: str) -> tuple[Violation, ...]:
        return tuple(
            v for v in self.violations if v.constraint_id == constraint_id
        )

    def breached_constraints(self) -> tuple[str, ...]:
        seen: list[str] = []
        for violation in self.violations:
            if violation.constraint_id not in seen:
                seen.append(violation.constraint_id)
        return tuple(seen)


class IntegrityError(Exception):
    """Base class for integrity violations raised preventively."""


class RejectedInputError(IntegrityError):
    """An object was derived from a non-consumable upstream. [I8]"""

    def __init__(self, violations: tuple[Violation, ...]) -> None:
        super().__init__(
            "; ".join(f"{v.object_id}: {v.detail}" for v in violations)
        )
        self.violations = violations


# ---------------------------------------------------------------------------
# I8 -- preventive: rejected knowledge must never re-enter
# ---------------------------------------------------------------------------

def i8_inputs_are_consumable(ctx: AcceptanceContext) -> RuleResult:
    """Reject a write whose upstream is not consumable. [I8, R-2]

    Only ACTIVE objects are current knowledge. A REJECTED object was declined
    deliberately; an INVALIDATED or RETRACTED one has lost its support. None
    may be built upon, and unlike the detective constraints this must be
    refused up front -- a conclusion drawn from rejected knowledge cannot be
    un-drawn by a later audit.
    """
    attributes = ctx.attributes
    if not attributes.derives_from:
        return RuleResult("I8", RuleOutcome.SKIP, "no upstream to check")
    if ctx.upstream_status is None:
        return RuleResult("I8", RuleOutcome.SKIP, "no upstream status provider")

    offending: list[str] = []
    unresolved: list[str] = []
    for ref in attributes.derives_from:
        status = ctx.upstream_status(ref.object_id)
        if status is None:
            unresolved.append(ref.object_id)
        elif not is_consumable(status):
            offending.append(f"{ref.object_id} is {status.value}")

    if offending:
        return RuleResult(
            "I8",
            RuleOutcome.FAIL,
            f"upstream not consumable: {'; '.join(sorted(offending))} [I8]",
        )
    if unresolved:
        # V3 reports unresolvable references; I8 does not duplicate that.
        return RuleResult(
            "I8", RuleOutcome.SKIP, "upstream status unresolved; see V3"
        )
    return RuleResult("I8", RuleOutcome.PASS, "all upstream objects consumable")


i8_inputs_are_consumable.rule_id = "I8"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Continuous verifier
# ---------------------------------------------------------------------------

@dataclass
class IntegrityVerifier:
    """Audits a store against I1-I8 continuously. [IOM section 1.4]

    Detective rather than preventive for I1-I7: these can be breached by
    paths no single write controls, so the platform needs a way to ask "do
    the invariants still hold?" at any moment, not only at write time.
    """

    store: "object"  # KnowledgeStore; untyped to avoid a circular import

    CONSTRAINT_MODES: dict[str, ConstraintMode] = field(
        default_factory=lambda: {
            "I1": ConstraintMode.DETECTIVE,
            "I2": ConstraintMode.DETECTIVE,
            "I3": ConstraintMode.DETECTIVE,
            "I4": ConstraintMode.DETECTIVE,
            "I5": ConstraintMode.DETECTIVE,
            "I6": ConstraintMode.DETECTIVE,
            "I7": ConstraintMode.DETECTIVE,
            "I8": ConstraintMode.PREVENTIVE,
        },
        init=False,
    )

    # -- full audit -------------------------------------------------------

    def verify(self) -> IntegrityReport:
        """Run every constraint over the whole store."""
        violations: list[Violation] = []
        for check in (
            self._check_i1,
            self._check_i2,
            self._check_i3,
            self._check_i4,
            self._check_i5,
            self._check_i6,
            self._check_i7,
            self._check_i8,
        ):
            violations.extend(check())
        return IntegrityReport(
            violations=tuple(violations),
            checked_objects=len(self.store),
            constraints_run=tuple(f"I{i}" for i in range(1, 9)),
        )

    def verify_constraint(self, constraint_id: str) -> IntegrityReport:
        """Run one constraint, for targeted diagnosis."""
        checks = {
            "I1": self._check_i1,
            "I2": self._check_i2,
            "I3": self._check_i3,
            "I4": self._check_i4,
            "I5": self._check_i5,
            "I6": self._check_i6,
            "I7": self._check_i7,
            "I8": self._check_i8,
        }
        check = checks.get(constraint_id)
        if check is None:
            raise IntegrityError(f"unknown constraint {constraint_id!r}")
        return IntegrityReport(
            violations=tuple(check()),
            checked_objects=len(self.store),
            constraints_run=(constraint_id,),
        )

    def assert_holds(self) -> None:
        """Raise if any constraint is breached."""
        report = self.verify()
        if not report.holds:
            raise IntegrityError(
                f"{len(report.violations)} integrity violation(s): "
                f"{', '.join(report.breached_constraints())}"
            )

    def failure_records(self, report: IntegrityReport) -> tuple[FailureRecord, ...]:
        """Convert violations to failure records. [N-10]"""
        return tuple(
            FailureRecord(
                object_id=v.object_id,
                object_type=v.object_type or ObjectType.EVIDENCE,
                failed_rules=(
                    RuleResult(v.constraint_id, RuleOutcome.FAIL, v.detail),
                ),
                recorded_at=utc_now(),
                engine_configuration_ref="integrity-audit",
            )
            for v in report.violations
        )

    # -- individual constraints ------------------------------------------

    def _check_i1(self) -> list[Violation]:
        """Content immutable; only status may transition. [I1]

        Verified structurally: attributes are frozen dataclasses, so mutation
        is impossible through the public surface. This confirms the property
        rather than re-testing Python.
        """
        violations: list[Violation] = []
        for stored in self.store:
            attributes = stored.attributes
            if not getattr(type(attributes), "__dataclass_params__", None):
                violations.append(
                    Violation("I1", stored.object_id, "attributes are not a dataclass",
                              stored.object_type)
                )
            elif not type(attributes).__dataclass_params__.frozen:
                violations.append(
                    Violation("I1", stored.object_id,
                              "attributes are mutable; content could be rewritten",
                              stored.object_type)
                )
        return violations

    def _check_i2(self) -> list[Violation]:
        """object_id never reused. [I2]"""
        violations: list[Violation] = []
        seen: dict[str, str] = {}
        for stored in self.store:
            lineage_id = seen.get(stored.object_id)
            if lineage_id is not None and lineage_id != stored.lineage_id:
                violations.append(
                    Violation("I2", stored.object_id,
                              f"object_id reused across lineages {lineage_id!r} "
                              f"and {stored.lineage_id!r}", stored.object_type)
                )
            seen[stored.object_id] = stored.lineage_id
        return violations

    def _check_i3(self) -> list[Violation]:
        """Lineage references never repoint. [I3]

        Each object's stored lineage must still agree with the references its
        attributes assert. Divergence means something rewrote a reference
        after the fact.
        """
        violations: list[Violation] = []
        for stored in self.store:
            asserted = tuple(r.object_id for r in stored.attributes.derives_from)
            recorded = tuple(stored.lineage.reference_ids)
            if asserted != recorded:
                violations.append(
                    Violation("I3", stored.object_id,
                              f"lineage references repointed: attributes say "
                              f"{asserted}, lineage says {recorded}",
                              stored.object_type)
                )
        return violations

    def _check_i4(self) -> list[Violation]:
        """Referenced objects never hard-deleted. [I4]"""
        violations: list[Violation] = []
        for stored in self.store:
            for ref in stored.attributes.derives_from:
                if not self.store.contains(ref.object_id):
                    violations.append(
                        Violation("I4", stored.object_id,
                                  f"references {ref.object_id!r}, which is not "
                                  f"stored; lineage is broken",
                                  stored.object_type)
                    )
        return violations

    def _check_i5(self) -> list[Violation]:
        """Exactly one version per lineage_id is ACTIVE. [I5]"""
        violations: list[Violation] = []
        by_lineage: dict[str, list[str]] = {}
        for stored in self.store:
            if stored.status is ObjectStatus.ACTIVE:
                by_lineage.setdefault(stored.lineage_id, []).append(
                    stored.object_id
                )
        for lineage_id, object_ids in by_lineage.items():
            if len(object_ids) > 1:
                for object_id in sorted(object_ids):
                    violations.append(
                        Violation("I5", object_id,
                                  f"lineage {lineage_id!r} has "
                                  f"{len(object_ids)} ACTIVE versions: "
                                  f"{sorted(object_ids)}")
                    )
        return violations

    def _check_i6(self) -> list[Violation]:
        """Upstream RETRACTED/INVALIDATED => dependents INVALIDATED. [I6]

        Enforced by the cascade operation (T01.2.3); this detects any
        dependent the cascade did not reach.

        BOUNDED BY THE PARTIAL-RETRACTION RULE [T01.2.4, N-9, IOM 3.2]. A
        dependent that retains at least one valid upstream reference is NOT a
        cascade miss: N-9 states that such an object "is handled by the
        partial-retraction rule rather than by cascade", and IOM 3.2 triggers
        INVALIDATED only on "All attesting Evidence retracted". Flagging it
        would report the ratified behaviour as an integrity breach.

        A dependent is a genuine miss only when EVERY upstream reference is
        withdrawn and it is still ACTIVE.
        """
        violations: list[Violation] = []
        withdrawn = {
            stored.object_id
            for stored in self.store
            if stored.status in (ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED)
        }
        if not withdrawn:
            return violations

        for stored in self.store:
            if stored.status is not ObjectStatus.ACTIVE:
                continue
            references = stored.attributes.derives_from
            if not references:
                continue
            if not any(ref.object_id in withdrawn for ref in references):
                continue
            if any(ref.object_id not in withdrawn for ref in references):
                # Partial retraction: still attested. [T01.2.4, N-9, IOM 3.2]
                continue
            detail = ", ".join(sorted(r.object_id for r in references))
            violations.append(
                Violation("I6", stored.object_id,
                          f"is ACTIVE but every upstream reference ({detail}) "
                          f"is withdrawn; cascade did not reach it",
                          stored.object_type)
            )
        return violations

    def _check_i7(self) -> list[Violation]:
        """Confidence ceiling holds after any upstream change. [I7, R-3]

        Re-verified against current upstream values, not the values in force
        when the object was written. An upstream supersession can lower a
        ceiling long after acceptance passed.
        """
        violations: list[Violation] = []
        for stored in self.store:
            if not stored.attributes.derives_from:
                continue
            effective = stored.attributes.confidence.effective_confidence
            for ref in stored.attributes.derives_from:
                upstream = self.store.find(ref.object_id)
                if upstream is None:
                    continue  # I4 reports the missing reference
                ceiling = upstream.attributes.confidence.effective_confidence
                if effective > ceiling + 1e-9:
                    violations.append(
                        Violation("I7", stored.object_id,
                                  f"effective_confidence {effective} exceeds "
                                  f"upstream {ref.object_id!r} ceiling {ceiling}",
                                  stored.object_type)
                    )
        return violations

    def _check_i8(self) -> list[Violation]:
        """REJECTED objects never consumed as input. [I8, R-2]

        Preventive at write time; this detects any that slipped through.
        """
        violations: list[Violation] = []
        for stored in self.store:
            for ref in stored.attributes.derives_from:
                upstream = self.store.find(ref.object_id)
                if upstream is None:
                    continue  # I4 reports the missing reference
                if upstream.status is ObjectStatus.REJECTED:
                    violations.append(
                        Violation("I8", stored.object_id,
                                  f"derives from REJECTED {ref.object_id!r}; "
                                  f"rejected knowledge re-entered the pipeline",
                                  stored.object_type)
                    )
        return violations
