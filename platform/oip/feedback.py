"""Feedback Record object type: the ninth Intelligence Object.

Task: T01.7.9

Architecture References:
- FR-V1  motivating_records non-empty and resolvable
- FR-V2  change_target present
- FR-V3  reversal_procedure present and actionable
- FR-V4  evidence_of_pattern justifies the lesson beyond a single outcome
- FR-V5  informs identifies specific affected engines
- FR-V6  Does not derive from any object other than Execution Records
- FR-I1  Every applied change is reversible
- FR-I2  Never becomes Evidence (guards C-04)
- FR-I3  Never modifies historical objects
- FR-I4  Cumulative effect of active records remains determinable
- R-7    Feedback Record ratified as the ninth object type (closes C-03) [escalation]
- R-8    Behavioural loop closure; the lineage graph stays acyclic
- AD-05  Ground Truth Protection; Feedback Record is the Learning Signal form
- R-6    INFORMS targets engine behaviour, never an object
- S-4    Feedback Record sufficiency: 2 Execution Records minimum (FR-V4)
- C-02   Execution Records uncreatable, so motivating records are unobtainable
- M-02   Learning target vocabulary OPEN and BLOCKING
- M-04   No success measure, so observed_effect is unassessable
- M-70   Feedback instability guard OPEN
- OQ-05  Learning update approval OPEN
- OQ-24  Feedback application mechanism OPEN
- IOM    section 3.9

Every other pipeline stage produces a persisted object. The Feedback stage did
not, so learning updates altered platform behaviour with NO PERSISTENT RECORD
-- breaching Principle 3, making learning irreversible, and leaving
untraceable drift unmitigated. R-7 ratified this type to close C-03.

FR-I2 IS THE LOOP-CLOSURE ENFORCEMENT POINT. Feedback influences future
behaviour and may trigger new research, but never enters the lineage graph as
grounding. Under AD-05 this object is the Learning Signal form -- one of four
permitted feedback destinations, none of which becomes Evidence. A Feedback
Record is a lineage LEAF: nothing derives from it, which is also what keeps
the graph acyclic under R-8.

INFORMS is the only relationship in the closed taxonomy pointing at something
other than an object. It targets ENGINES, and is deliberately excluded from
LINEAGE_RELATIONSHIPS. The existing EngineInforms type models it; this module
reuses that rather than introducing a parallel notion.

BLOCKING CONDITIONS, stated deliberately and enforced by failing closed:

  M-02 -- the learning target has no defined vocabulary. change_target is
  required to be PRESENT (FR-V2) but its value is unconstrained. Candidates
  named in the IOM (scoring weights, extraction criteria, source trust,
  validation thresholds, pattern definitions) are illustrative, not a
  taxonomy, and none is encoded here.

  C-02 -- no engine may create an Execution Record, so the motivating records
  FR-V1 requires cannot exist through any sanctioned path. A Feedback Record
  is therefore unwritable end-to-end today for a reason inherited from the
  stage below it, not for any defect of its own.

  M-04 -- no success measure exists, so observed_effect cannot be evaluated.
  It is carried, never assessed.

Scope: the Feedback Record type and its rules. Learning application
(T08.2.x), approval (OQ-05), the instability guard (M-70) and cumulative
drift remediation are absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Iterable

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.contract import UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.relationships import EngineInforms
from oip.support import sufficiency_threshold

# S-4: a lesson requires a pattern across outcomes, not a single result.
MINIMUM_MOTIVATING_RECORDS = 2


class FeedbackRecordError(Exception):
    """Base class for Feedback Record violations."""


class MotivatingRecordError(FeedbackRecordError):
    """motivating_records absent, duplicated, or not Execution Records."""


class ChangeTargetError(FeedbackRecordError):
    """change_target absent. [FR-V2, M-02]"""


class ReversalProcedureError(FeedbackRecordError):
    """reversal_procedure absent; irreversible learning. [FR-V3, FR-I1]"""


class PatternEvidenceError(FeedbackRecordError):
    """evidence_of_pattern absent or resting on one outcome. [FR-V4]"""


class InformsError(FeedbackRecordError):
    """informs names no specific engine. [FR-V5, R-6]"""


class GroundTruthViolationError(FeedbackRecordError):
    """A Feedback Record was treated as Evidence. [FR-I2, AD-05, C-04]"""


def _normalised(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


# ---------------------------------------------------------------------------
# Reversal  [FR-V3, FR-I1]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReversalProcedure:
    """How to undo an applied change. [FR-V3, FR-I1]

    Mandatory because irreversible learning is unrecoverable learning. A
    lesson that cannot be undone converts a wrong inference into a permanent
    change of platform behaviour, with no route back.

    `steps` is structured rather than prose so that "actionable" is
    mechanically checkable: a procedure with no steps is a statement of
    intent, not a means of recovery.
    """

    steps: tuple[str, ...]
    restores_to: str

    def __post_init__(self) -> None:
        if not self.steps:
            raise ReversalProcedureError(
                "reversal_procedure requires at least one step; irreversible "
                "learning is unrecoverable learning [FR-V3, FR-I1]"
            )
        for step in self.steps:
            if not (step or "").strip():
                raise ReversalProcedureError(
                    "a reversal step may not be empty [FR-V3]"
                )
        if not (self.restores_to or "").strip():
            raise ReversalProcedureError(
                "reversal_procedure must state the state it restores; "
                "'undo it' is not a recovery path [FR-V3, FR-I1]"
            )

    @property
    def is_actionable(self) -> bool:
        return bool(self.steps) and bool((self.restores_to or "").strip())


# ---------------------------------------------------------------------------
# Pattern evidence  [FR-V4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PatternEvidence:
    """Why this is a genuine lesson rather than noise. [FR-V4, S-4]

    Mandatory to counter overfitting. A single unfavourable outcome is not a
    lesson; requiring explicit justification that a pattern exists across
    outcomes forces the distinction between signal and noise to be STATED
    rather than assumed.

    `distinguishing_reasoning` carries the argument that the consistency is
    not a domain-specific artefact -- the IOM's own worked example turns on
    exactly that point.
    """

    observed_across: tuple[str, ...]
    distinguishing_reasoning: str

    def __post_init__(self) -> None:
        if not self.observed_across:
            raise PatternEvidenceError(
                "evidence_of_pattern must name the outcomes the pattern spans "
                "[FR-V4]"
            )
        if not (self.distinguishing_reasoning or "").strip():
            raise PatternEvidenceError(
                "evidence_of_pattern must argue why this is signal and not "
                "noise; behaviour swinging on noise is the overfitting "
                "failure [FR-V4]"
            )
        seen: set[str] = set()
        for record in self.observed_across:
            if record in seen:
                raise PatternEvidenceError(
                    f"outcome {record!r} counted twice toward the pattern; a "
                    f"pattern cannot be manufactured by repetition [FR-V4]"
                )
            seen.add(record)

    @property
    def span(self) -> int:
        return len(self.observed_across)


# ---------------------------------------------------------------------------
# Feedback Record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeedbackRecord:
    """A lesson derived from execution outcomes. [R-7, IOM section 3.9]

    Composes the universal contract with the Feedback payload. Frozen and
    rarely versioned: lessons are SUPERSEDED rather than revised, and
    reversal is a status transition to RETRACTED that preserves the record
    that the lesson was once applied.

    A lineage LEAF by construction. Nothing derives from a Feedback Record,
    which is what keeps the loop behavioural rather than evidential (R-8) and
    the lineage graph acyclic.
    """

    attributes: UniversalAttributes
    motivating_records: tuple[str, ...]
    lesson_statement: str
    change_target: str
    change_description: str
    reversal_procedure: ReversalProcedure
    informs: tuple[EngineInforms, ...]
    applied_at: datetime
    evidence_of_pattern: PatternEvidence

    # Optional attributes [IOM section 3.9]
    magnitude: str | None = None
    expected_effect: str | None = None
    observed_effect: str | None = None   # unassessable while M-04 is open
    superseded_lesson: str | None = None
    approval_record: str | None = None   # OQ-05 undefined

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
            raise FeedbackRecordError(
                f"expected FeedbackRecord, got "
                f"{self.attributes.object_type.value}"
            )
        if self.attributes.produced_by_engine is not Engine.FEEDBACK:
            raise FeedbackRecordError(
                f"only the Feedback Engine may create Feedback Records; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )

        for name in ("lesson_statement", "change_description"):
            if not (getattr(self, name) or "").strip():
                raise FeedbackRecordError(f"{name} is required [IOM section 3.9]")

        # FR-V2: presence only. M-02 defines no vocabulary for the target.
        if not (self.change_target or "").strip():
            raise ChangeTargetError(
                "change_target is required; a lesson that changes nothing is "
                "no-op feedback and makes the loop decorative "
                "[FR-V2, M-02 vocabulary open]"
            )
        if not isinstance(self.reversal_procedure, ReversalProcedure):
            raise ReversalProcedureError("reversal_procedure is required [FR-V3]")
        if not isinstance(self.evidence_of_pattern, PatternEvidence):
            raise PatternEvidenceError("evidence_of_pattern is required [FR-V4]")
        if not isinstance(self.applied_at, datetime):
            raise FeedbackRecordError("applied_at must be a datetime")

        # FR-V1: motivating records present and distinct.
        if not self.motivating_records:
            raise MotivatingRecordError(
                "motivating_records is required; a lesson with no outcome "
                "behind it is learning from the platform's own inferences "
                "[FR-V1, FR-V6]"
            )
        if len(set(self.motivating_records)) != len(self.motivating_records):
            raise MotivatingRecordError(
                "the same Execution Record motivates this lesson twice; "
                "corroboration cannot be manufactured by repetition [FR-V1]"
            )

        # FR-V6: learning comes from OUTCOMES, never from the platform's own
        # inferences. Without this the platform could learn from its own
        # conclusions -- the self-reinforcement failure M-70 warns of.
        upstream = {ref.object_id for ref in self.attributes.derives_from}
        stray = sorted(set(self.motivating_records) - upstream)
        if stray:
            raise MotivatingRecordError(
                f"motivating_records {stray} are not in derives_from [FR-V1]"
            )
        wrong_type = sorted(
            f"{ref.object_id} is a {ref.object_type.value}"
            for ref in self.attributes.derives_from
            if ref.object_type is not ObjectType.EXECUTION_RECORD
        )
        if wrong_type:
            raise MotivatingRecordError(
                f"a Feedback Record derives from Execution Records only; "
                f"{wrong_type}. Learning from anything else is the platform "
                f"learning from its own conclusions [FR-V6, M-70]"
            )

        # FR-V5: INFORMS must name specific engines. R-6 makes the target an
        # engine, never an object, and EngineInforms enforces that shape.
        if not self.informs:
            raise InformsError(
                "informs must identify at least one affected engine; a lesson "
                "informing nothing changes no behaviour [FR-V5]"
            )
        for entry in self.informs:
            if not isinstance(entry, EngineInforms):
                raise InformsError(
                    f"informs entries must be EngineInforms, got {entry!r}; "
                    f"INFORMS targets engine behaviour, never an object [R-6]"
                )
            if entry.from_object_id != self.attributes.object_id:
                raise InformsError(
                    f"informs entry originates from "
                    f"{entry.from_object_id!r}, not from this record "
                    f"{self.attributes.object_id!r}"
                )
        informed = [entry.informs_engine for entry in self.informs]
        if len(set(informed)) != len(informed):
            raise InformsError(
                "the same engine is informed twice by this record [FR-V5]"
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
    def informed_engines(self) -> frozenset[Engine]:
        """Engines whose behaviour this lesson changes. [FR-V5]"""
        return frozenset(entry.informs_engine for entry in self.informs)

    @property
    def motivating_count(self) -> int:
        return len(self.motivating_records)

    @property
    def is_reversible(self) -> bool:
        """Whether the applied change can be undone. [FR-I1]"""
        return self.reversal_procedure.is_actionable

    @property
    def is_applied(self) -> bool:
        """Whether the change is currently in force. [FR-I4]

        ACTIVE means applied. RETRACTED means reversed, and the record is
        retained precisely so the platform remembers the lesson was once in
        force.
        """
        return self.attributes.status is ObjectStatus.ACTIVE

    @property
    def is_reversed(self) -> bool:
        return self.attributes.status is ObjectStatus.RETRACTED

    @property
    def observed_effect_assessable(self) -> bool:
        """Always False. No success measure exists. [M-04]"""
        return False

    def informs_engine(self, engine: Engine) -> bool:
        return engine in self.informed_engines

    def drift_contribution(self) -> tuple[str, str, str]:
        """This record's contribution to cumulative drift. [FR-I4]

        (change_target, change_description, magnitude). FR-I4 requires the
        total current deviation from baseline to remain determinable; that is
        only possible if each applied record can state its own contribution.
        """
        return (
            self.change_target,
            self.change_description,
            self.magnitude or "unstated",
        )


# ---------------------------------------------------------------------------
# Feedback Record acceptance rules  [FR-V1 .. FR-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _feedback_of(ctx: AcceptanceContext) -> "FeedbackRecord | None":
    return getattr(ctx, "feedback_record", None)


def frv1_motivating_records_resolve(ctx: AcceptanceContext) -> RuleResult:
    """motivating_records non-empty and resolvable. [FR-V1]

    Note the standing blocker: C-02 leaves Execution Records uncreatable, so
    in practice no motivating record can exist through a sanctioned path.
    This rule does not soften for that -- it reports what it finds.
    """
    if ctx.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
        return _skip("FR-V1", "not a Feedback Record")
    record = _feedback_of(ctx)
    if record is None:
        return _skip("FR-V1", "no Feedback Record payload supplied")

    if not record.motivating_records:
        return _fail("FR-V1", "no motivating Execution Record")

    if ctx.resolve_type is None:
        return _skip("FR-V1", "records declared; no resolver supplied")

    unresolved: list[str] = []
    mistyped: list[str] = []
    for ref in record.motivating_records:
        actual = ctx.resolve_type(ref)
        if actual is None:
            unresolved.append(ref)
        elif actual is not ObjectType.EXECUTION_RECORD:
            mistyped.append(f"{ref} is a {actual.value}")

    if unresolved:
        return _fail(
            "FR-V1",
            f"motivating records do not resolve: {sorted(unresolved)} "
            f"[C-02 leaves Execution Records uncreatable]",
        )
    if mistyped:
        return _fail(
            "FR-V1", f"motivating records are not outcomes: {sorted(mistyped)}"
        )
    return _ok(
        "FR-V1", f"{record.motivating_count} motivating Execution Record(s)"
    )


def frv2_change_target_present(ctx: AcceptanceContext) -> RuleResult:
    """change_target present. [FR-V2, M-02]

    PRESENCE ONLY. M-02 leaves the learning target undefined -- the IOM lists
    scoring weights, extraction criteria, source trust, validation thresholds
    and pattern definitions as CANDIDATES, not as a taxonomy. Encoding any of
    them would close M-02 by implementation.
    """
    if ctx.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
        return _skip("FR-V2", "not a Feedback Record")
    record = _feedback_of(ctx)
    if record is None:
        return _skip("FR-V2", "no Feedback Record payload supplied")

    if not (record.change_target or "").strip():
        return _fail(
            "FR-V2",
            "change_target absent; a lesson that changes nothing is no-op "
            "feedback and makes the loop decorative",
        )
    if not (record.change_description or "").strip():
        return _fail(
            "FR-V2",
            "change_description absent; the target is named but the change "
            "itself is unrecorded",
        )
    return _ok(
        "FR-V2",
        f"targets {record.change_target!r}; vocabulary unconstrained "
        f"[M-02 open, blocking]",
    )


def frv3_reversal_actionable(ctx: AcceptanceContext) -> RuleResult:
    """reversal_procedure present and actionable. [FR-V3, FR-I1]

    Irreversible learning is unrecoverable learning. "Actionable" is checked
    structurally: at least one step and a stated restore point. Whether the
    steps genuinely work is not verifiable here and is not claimed.
    """
    if ctx.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
        return _skip("FR-V3", "not a Feedback Record")
    record = _feedback_of(ctx)
    if record is None:
        return _skip("FR-V3", "no Feedback Record payload supplied")

    procedure = record.reversal_procedure
    if not isinstance(procedure, ReversalProcedure):
        return _fail("FR-V3", "reversal_procedure is absent")
    if not procedure.steps:
        return _fail(
            "FR-V3",
            "reversal_procedure has no steps; there would be no recovery from "
            "a bad lesson",
        )
    if not (procedure.restores_to or "").strip():
        return _fail(
            "FR-V3", "reversal_procedure states no state to restore"
        )
    return _ok(
        "FR-V3",
        f"{len(procedure.steps)} reversal step(s); efficacy unverified",
    )


def frv4_pattern_beyond_one_outcome(ctx: AcceptanceContext) -> RuleResult:
    """evidence_of_pattern justifies beyond a single outcome. [FR-V4, S-4]

    S-4 binds FR-V4 explicitly: a Feedback Record requires 2 Execution
    Records minimum, because FR-V4 demands a pattern across outcomes rather
    than a single result. A lesson drawn from one outcome is behaviour
    swinging on noise.
    """
    if ctx.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
        return _skip("FR-V4", "not a Feedback Record")
    record = _feedback_of(ctx)
    if record is None:
        return _skip("FR-V4", "no Feedback Record payload supplied")

    evidence = record.evidence_of_pattern
    if not isinstance(evidence, PatternEvidence):
        return _fail("FR-V4", "evidence_of_pattern is absent")
    if not (evidence.distinguishing_reasoning or "").strip():
        return _fail(
            "FR-V4",
            "evidence_of_pattern argues nothing; signal and noise are not "
            "distinguished",
        )

    threshold = sufficiency_threshold(ObjectType.FEEDBACK_RECORD)
    if record.motivating_count < threshold:
        return _fail(
            "FR-V4",
            f"{record.motivating_count} motivating outcome(s); S-4 requires "
            f"{threshold}. A single unfavourable outcome is not a lesson",
        )
    if evidence.span < MINIMUM_MOTIVATING_RECORDS:
        return _fail(
            "FR-V4",
            f"the pattern spans {evidence.span} outcome(s); a pattern across "
            f"outcomes requires at least {MINIMUM_MOTIVATING_RECORDS}",
        )

    stray = sorted(set(evidence.observed_across) - set(record.motivating_records))
    if stray:
        return _fail(
            "FR-V4",
            f"evidence_of_pattern cites {stray}, which do not motivate this "
            f"lesson",
        )
    return _ok(
        "FR-V4",
        f"pattern spans {evidence.span} outcome(s) [S-4 floor {threshold}]",
    )


def frv5_informs_specific_engines(ctx: AcceptanceContext) -> RuleResult:
    """informs identifies specific affected engines. [FR-V5, R-6]

    INFORMS is the only relationship in the closed taxonomy targeting
    something other than an object. It names ENGINES, and is deliberately not
    part of the lineage graph -- feedback changes behaviour, it does not
    become grounding.
    """
    if ctx.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
        return _skip("FR-V5", "not a Feedback Record")
    record = _feedback_of(ctx)
    if record is None:
        return _skip("FR-V5", "no Feedback Record payload supplied")

    if not record.informs:
        return _fail(
            "FR-V5",
            "informs names no engine; a lesson informing nothing changes no "
            "behaviour",
        )
    for entry in record.informs:
        if not isinstance(entry, EngineInforms):
            return _fail(
                "FR-V5",
                f"informs entry {entry!r} is not an EngineInforms; INFORMS "
                f"targets engine behaviour, never an object",
            )
        if not isinstance(entry.informs_engine, Engine):
            return _fail(
                "FR-V5", f"informs entry names no known engine: {entry!r}"
            )
    return _ok(
        "FR-V5",
        f"informs {sorted(e.value for e in record.informed_engines)}",
    )


def frv6_derives_only_from_execution_records(
    ctx: AcceptanceContext,
) -> RuleResult:
    """Does not derive from any object other than Execution Records. [FR-V6]

    Enforces that learning comes from OUTCOMES, not from the platform's own
    inferences. Without it the platform could learn from its own conclusions
    -- the self-reinforcement failure, which is indistinguishable from
    improvement while it happens.
    """
    if ctx.attributes.object_type is not ObjectType.FEEDBACK_RECORD:
        return _skip("FR-V6", "not a Feedback Record")
    record = _feedback_of(ctx)
    if record is None:
        return _skip("FR-V6", "no Feedback Record payload supplied")

    declared = [
        f"{ref.object_id} declared {ref.object_type.value}"
        for ref in ctx.attributes.derives_from
        if ref.object_type is not ObjectType.EXECUTION_RECORD
    ]
    if declared:
        return _fail(
            "FR-V6",
            f"derives from non-outcomes: {sorted(declared)}; the platform "
            f"would be learning from its own conclusions",
        )

    if ctx.resolve_type is None:
        return _skip("FR-V6", "declared types are outcomes; no resolver")

    resolved = [
        f"{ref.object_id} resolves to {ctx.resolve_type(ref.object_id).value}"
        for ref in ctx.attributes.derives_from
        if ctx.resolve_type(ref.object_id) is not None
        and ctx.resolve_type(ref.object_id) is not ObjectType.EXECUTION_RECORD
    ]
    if resolved:
        return _fail(
            "FR-V6",
            f"derivation resolves to non-outcomes: {sorted(resolved)}",
        )
    return _ok("FR-V6", "derives from Execution Records only")


frv1_motivating_records_resolve.rule_id = "FR-V1"           # type: ignore[attr-defined]
frv2_change_target_present.rule_id = "FR-V2"                # type: ignore[attr-defined]
frv3_reversal_actionable.rule_id = "FR-V3"                  # type: ignore[attr-defined]
frv4_pattern_beyond_one_outcome.rule_id = "FR-V4"           # type: ignore[attr-defined]
frv5_informs_specific_engines.rule_id = "FR-V5"             # type: ignore[attr-defined]
frv6_derives_only_from_execution_records.rule_id = "FR-V6"  # type: ignore[attr-defined]

FEEDBACK_RULES = (
    frv1_motivating_records_resolve,
    frv2_change_target_present,
    frv3_reversal_actionable,
    frv4_pattern_beyond_one_outcome,
    frv5_informs_specific_engines,
    frv6_derives_only_from_execution_records,
)


# ---------------------------------------------------------------------------
# Feedback Record integrity constraints  [FR-I1 .. FR-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FeedbackViolation:
    """A breached Feedback Record integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass(frozen=True)
class DriftSummary:
    """Total current deviation from baseline behaviour. [FR-I4]

    FR-I4 requires the cumulative effect of active records to remain
    determinable. This is that statement: which lessons are in force, what
    each changed, and which engines are affected.
    """

    applied: tuple[tuple[str, str, str], ...]
    engines_affected: frozenset[Engine]
    reversed_count: int

    @property
    def is_determinable(self) -> bool:
        """Always True when constructible. FR-I4 fails by absence, not value."""
        return True

    @property
    def applied_count(self) -> int:
        return len(self.applied)

    def targets(self) -> tuple[str, ...]:
        seen: list[str] = []
        for target, _, _ in self.applied:
            if target not in seen:
                seen.append(target)
        return tuple(seen)


@dataclass
class FeedbackIntegrity:
    """Continuous verification of FR-I1..FR-I4. [IOM section 3.9]

    Detective, mirroring the earlier type verifiers. FR-I2 is the one that
    guards the architecture's outermost boundary: a Feedback Record that
    became grounding would close the loop evidentially rather than
    behaviourally, which AD-05 and R-8 both forbid.
    """

    feedback_of: Callable[[str], "FeedbackRecord | None"]
    store: "object"
    _recorded_upstream: dict[str, tuple] = field(default_factory=dict, init=False)

    def verify(self) -> tuple[FeedbackViolation, ...]:
        violations: list[FeedbackViolation] = []
        violations.extend(self._check_fri1())
        violations.extend(self._check_fri2())
        violations.extend(self._check_fri3())
        violations.extend(self._check_fri4())
        return tuple(violations)

    def _all_records(self) -> Iterable[tuple[str, "FeedbackRecord"]]:
        for stored in self.store.objects_of_type(ObjectType.FEEDBACK_RECORD):
            record = self.feedback_of(stored.object_id)
            if record is not None:
                yield stored.object_id, record

    # -- recording, for FR-I3 ---------------------------------------------

    def record(self, feedback: "FeedbackRecord") -> None:
        """Snapshot the motivating outcomes at acceptance. [FR-I3]"""
        for ref in feedback.motivating_records:
            state = self._state_of(ref)
            if state is not None:
                self._recorded_upstream.setdefault(ref, state)

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
    def recorded_upstream_count(self) -> int:
        return len(self._recorded_upstream)

    def _check_fri1(self) -> list[FeedbackViolation]:
        """Every applied change is reversible. [FR-I1]

        Checked for records currently in force. A lesson that has been
        reversed already, or was never applied, is not required to remain
        reversible -- but every ACTIVE one is, because there is otherwise no
        recovery from a bad lesson.
        """
        violations: list[FeedbackViolation] = []
        for object_id, record in self._all_records():
            stored = self.store.find(object_id)
            if stored is None or stored.status is not ObjectStatus.ACTIVE:
                continue
            if not record.is_reversible:
                violations.append(
                    FeedbackViolation(
                        "FR-I1", object_id,
                        "is applied but carries no actionable reversal "
                        "procedure; irreversible learning is unrecoverable",
                    )
                )
        return violations

    def _check_fri2(self) -> list[FeedbackViolation]:
        """Never becomes Evidence. [FR-I2, AD-05, C-04, R-8]

        The enforcement point for loop closure. Three routes are closed:

        - The record itself typed as Evidence.
        - Any Evidence deriving from a Feedback Record -- the direct C-04
          path, where a platform artefact becomes grounding.
        - Any object at all deriving from a Feedback Record. A Feedback
          Record is a lineage leaf; anything descending from it would put
          feedback into the lineage graph, which is what R-8 keeps out to
          preserve acyclicity.
        """
        violations: list[FeedbackViolation] = []
        feedback_ids = {
            stored.object_id
            for stored in self.store.objects_of_type(ObjectType.FEEDBACK_RECORD)
        }
        if not feedback_ids:
            return violations

        for stored in self.store:
            for ref in stored.attributes.derives_from:
                if ref.object_id not in feedback_ids:
                    continue
                if stored.object_type is ObjectType.EVIDENCE:
                    violations.append(
                        FeedbackViolation(
                            "FR-I2", ref.object_id,
                            f"Evidence {stored.object_id!r} derives from this "
                            f"Feedback Record; a platform artefact has become "
                            f"grounding [AD-05, C-04]",
                        )
                    )
                else:
                    violations.append(
                        FeedbackViolation(
                            "FR-I2", ref.object_id,
                            f"{stored.object_type.value} "
                            f"{stored.object_id!r} derives from this Feedback "
                            f"Record; feedback influences behaviour and never "
                            f"enters the lineage graph [R-8]",
                        )
                    )
        return violations

    def _check_fri3(self) -> list[FeedbackViolation]:
        """Never modifies historical objects. [FR-I3]

        The motivating Execution Records are compared against snapshots taken
        when the lesson was accepted. A lesson that edits the outcomes it
        learned from has rewritten its own evidence.
        """
        violations: list[FeedbackViolation] = []
        seen: set[str] = set()
        for object_id, record in self._all_records():
            for ref in record.motivating_records:
                recorded = self._recorded_upstream.get(ref)
                if recorded is None or ref in seen:
                    continue
                seen.add(ref)
                current = self._state_of(ref)
                if current is None:
                    violations.append(
                        FeedbackViolation(
                            "FR-I3", object_id,
                            f"motivating record {ref!r} is no longer "
                            f"retrievable; the lesson's basis cannot be shown "
                            f"intact",
                        )
                    )
                elif current != recorded:
                    violations.append(
                        FeedbackViolation(
                            "FR-I3", object_id,
                            f"motivating record {ref!r} changed after this "
                            f"lesson attached: recorded {recorded}, now "
                            f"{current}. A lesson never modifies the history "
                            f"it learned from",
                        )
                    )
        return violations

    def _check_fri4(self) -> list[FeedbackViolation]:
        """Cumulative effect of active records remains determinable. [FR-I4]

        Counters accumulated untraceable drift: it must always be possible to
        state the total current deviation from baseline. That is only
        possible if every applied record can state its own contribution, so
        an applied record with an unstatable contribution breaks the total.
        """
        violations: list[FeedbackViolation] = []
        for object_id, record in self._all_records():
            stored = self.store.find(object_id)
            if stored is None or stored.status is not ObjectStatus.ACTIVE:
                continue
            target, description, _ = record.drift_contribution()
            if not (target or "").strip() or not (description or "").strip():
                violations.append(
                    FeedbackViolation(
                        "FR-I4", object_id,
                        "is applied but cannot state its contribution to "
                        "cumulative drift; the total deviation from baseline "
                        "becomes undeterminable",
                    )
                )
        return violations

    # -- FR-I4 reporting ---------------------------------------------------

    def drift_summary(self) -> DriftSummary:
        """Total current deviation from baseline behaviour. [FR-I4]"""
        applied: list[tuple[str, str, str]] = []
        engines: set[Engine] = set()
        reversed_count = 0
        for object_id, record in self._all_records():
            stored = self.store.find(object_id)
            if stored is None:
                continue
            if stored.status is ObjectStatus.ACTIVE:
                applied.append(record.drift_contribution())
                engines |= set(record.informed_engines)
            elif stored.status is ObjectStatus.RETRACTED:
                reversed_count += 1
        return DriftSummary(
            applied=tuple(applied),
            engines_affected=frozenset(engines),
            reversed_count=reversed_count,
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class FeedbackRegistry:
    """Holds Feedback Record payloads. [IOM section 3.9]

    Mirrors the earlier registries. Conflicting lessons are surfaced, never
    resolved: two lessons disagreeing on one target is information about the
    reliability of both.

    No application mechanism is offered. OQ-24 leaves feedback application
    undefined, OQ-05 leaves approval undefined, and M-70 leaves the
    instability guard open.
    """

    store: "object"
    _payloads: dict[str, FeedbackRecord] = field(default_factory=dict, init=False)
    _integrity: "FeedbackIntegrity | None" = field(default=None, init=False)

    def register(self, record: FeedbackRecord) -> FeedbackRecord:
        self._payloads[record.object_id] = record
        self.integrity().record(record)
        return record

    def get(self, object_id: str) -> FeedbackRecord | None:
        return self._payloads.get(object_id)

    def applied_records(self) -> tuple[FeedbackRecord, ...]:
        """Lessons currently in force. [FR-I4]"""
        found = []
        for object_id, record in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                found.append(record)
        return tuple(found)

    def reversed_records(self) -> tuple[FeedbackRecord, ...]:
        """Lessons applied and later undone, retained deliberately. [FR-I1]"""
        found = []
        for object_id, record in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.RETRACTED:
                found.append(record)
        return tuple(found)

    def informing(self, engine: Engine) -> tuple[FeedbackRecord, ...]:
        """Lessons affecting one engine's behaviour. [FR-V5]"""
        return tuple(
            r for r in self._payloads.values() if r.informs_engine(engine)
        )

    def from_outcome(self, execution_ref: str) -> tuple[FeedbackRecord, ...]:
        return tuple(
            r for r in self._payloads.values()
            if execution_ref in r.motivating_records
        )

    def targeting(self, change_target: str) -> tuple[FeedbackRecord, ...]:
        """Lessons on one target, for supersession and conflict inspection."""
        key = _normalised(change_target)
        return tuple(
            r for r in self._payloads.values()
            if _normalised(r.change_target) == key
        )

    def conflicts_for(
        self, change_target: str
    ) -> tuple[tuple[FeedbackRecord, FeedbackRecord], ...]:
        """Pairs of APPLIED lessons on one target. [CONTRADICTS]

        Two lessons simultaneously in force on the same target may conflict.
        Surfaced for the caller to record as CONTRADICTS; no winner is
        selected, and no resolution policy is invented -- OQ-24 leaves the
        application mechanism undefined.
        """
        applied = [
            r for r in self.targeting(change_target)
            if r in self.applied_records()
        ]
        pairs: list[tuple[FeedbackRecord, FeedbackRecord]] = []
        for i, left in enumerate(applied):
            for right in applied[i + 1:]:
                pairs.append((left, right))
        return tuple(pairs)

    def drift_summary(self) -> DriftSummary:
        """Total current deviation from baseline. [FR-I4]"""
        return self.integrity().drift_summary()

    def integrity(self) -> FeedbackIntegrity:
        if self._integrity is None:
            self._integrity = FeedbackIntegrity(
                feedback_of=self.get, store=self.store
            )
        return self._integrity

    def __len__(self) -> int:
        return len(self._payloads)
