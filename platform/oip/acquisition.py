"""Source acquisition producing Evidence objects with complete provenance.

Task: T02.2.1

Architecture References:
- N-20   The acquisition gate sequence (S 5.2.1) is evaluated in its
         ratified order -- typability (gate 2) before rights (gate 3) --
         halting at the first refusal so exactly one reason is produced.
         Gate 2 consumes `classify`: an untypable channel is INELIGIBLE
         and is recorded in the out-of-frame register (N-22 S 5.2.1), not
         as a coverage gap. `source_type` is assigned by the Research
         Engine at acquisition (S 5.1).
- N-21   Enforcement precedes the external act (S 5.2): acquisition is
         admitted only on an explicit, unexpired PERMITTED with retainable
         rights (S 5.4). Every rights refusal is recorded, never silent
         (K10). access_conditions is composed from the assessment (S 5.9).
- N-24   Assessments arrive attributed to the designated role
         (Designated Source Rights/Compliance Authority); an absent
         assessment is UNASSESSED and refuses.
- N-15   Acquisition records the storage mode per Evidence object:
         RETAIN_FULL stores in full, RETAIN_REFERENCE_ONLY stores by
         reference. The content_fingerprint and provenance are always
         retained regardless of mode.
- N-22   A failed acquisition attempt produces a failure record AND makes
         the member a gap requiring declaration (S 5.7); gate-2 refusals
         feed the out-of-frame register (S 5.2.1).
- N-10   A stage that produced nothing because it failed is
         distinguishable from one that found nothing: every refusal here
         carries its stage and reason.
- N-16 / T02.1.3
         source_independence_group is carried and honoured when supplied
         (explicit-input model); no syndication inference is performed.
- R-3 / IOM S 3.1
         The two confidence components are supplied explicitly by the
         Research Engine at acquisition and are never conflated; the IOM
         worked example records both on acquired Evidence.
- T02.2.5 / N-10
         Failure recording: every refusal is first-class data. Acquisition
         failures are projected into the platform's FailureStore (the
         N-10 home built at T01.1.7, co-located with configuration N-7)
         with all six N-10 identifications, and carry the not-found vs
         not-attempted distinction N-10 makes mandatory: gate refusals
         precede the external act (N-21 S 5.2) and are NOT attempts;
         duplicate and store refusals happen after material is in hand
         and ARE attempts.
- M-01   Gate 1 (scope) is DELIBERATELY ABSENT: directives are T02.2.4
         and the triggering question is open. This module invents no
         scope rule and no directive vocabulary.

WHAT IS IMPLEMENTED (the three T02.2.1 acceptance criteria)
------------------------------------------------------------
- AC1  Provenance complete on every Evidence object: all six required
  Provenance fields are required by the request, validated, and carried
  onto the Evidence; access_conditions is composed from the rights
  assessment (N-21 S 5.9); the storage mode is recorded per object (N-15).
- AC2  Acquisition failures recorded, not silent: every refusal --
  malformed request, unregistered source, type mismatch, untypable
  channel (gate 2, also into the out-of-frame register), rights refusal
  (gate 3, also into the rights refusal register), and store rejection --
  appends one AcquisitionFailure to the AcquisitionLog and raises with it.
- AC3  capture_fidelity documented per acquisition: the request REQUIRES a
  non-empty fidelity statement -- an assessment of what was preserved
  versus lost (IOM S 3.1) -- and it is never defaulted.

WHAT IS DELIBERATELY NOT IMPLEMENTED
-------------------------------------
- Gate 1 / directives (M-01, T02.2.4). Duplicate detection is T02.2.2
  (E-V6 continues to run at acceptance). Drift detection is T02.2.3.
  The fuller failure-recording integration is T02.2.5. Conduct is M-18b.
- No new semantics: confidence values, fidelity wording and acquisition
  method are the caller's (the Research Engine's) judgement, required
  explicitly, never invented here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterator

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.contract import (
    Confidence, Engine, Explanation, ObjectStatus, ObjectType,
    UniversalAttributes, utc_now,
)
from oip.evidence import Evidence, EvidenceContent, Provenance, StorageMode
from oip.rights import (
    RightsAssessment,
    RefusalRegister,
    StorageMode as RightsStorageMode,
    access_conditions_value,
    evaluate_gate,
    unassessed,
)
from oip.source import (
    SourceRegistry,
    UntypableChannelError,
    classify,
)
from oip.store import KnowledgeStore, WriteRejectedError

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AcquisitionError(Exception):
    """Base class for acquisition violations."""


class AcquisitionRefusedError(AcquisitionError):
    """Acquisition was refused; the failure is recorded, never silent.

    [T02.2.1 AC2, K10, N-10] The attached failure names its stage and
    reason, so a refusal is always distinguishable from found-nothing."""


# ---------------------------------------------------------------------------
# Failure records  [AC2, N-10, K10]
# ---------------------------------------------------------------------------


class AcquisitionStage(str, Enum):
    """Why an acquisition attempt refused. Closed set; one per attempt.

    Order mirrors the ratified evaluation sequence (N-20 S 5.2.1):
    gate 1 (scope), request validation, source resolution, gate 2
    (typability), gate 3 (rights), persistence."""

    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNREGISTERED_SOURCE = "UNREGISTERED_SOURCE"
    SOURCE_TYPE_MISMATCH = "SOURCE_TYPE_MISMATCH"
    UNTYPABLE_CHANNEL = "UNTYPABLE_CHANNEL"
    REFUSED_BY_RIGHTS = "REFUSED_BY_RIGHTS"
    DUPLICATE_ACQUISITION = "DUPLICATE_ACQUISITION"
    STORE_REJECTED = "STORE_REJECTED"


@dataclass(frozen=True)
class AcquisitionFailure:
    """One recorded acquisition failure. Never silent. [AC2, N-10]

    T02.2.5: the record identifies the configuration in force
    (N-10's fourth identification -- the request carries it), the engine
    is Research by create authority (K8: `engine` property), and the
    not-found vs not-attempted distinction N-10 makes mandatory is
    carried by `attempted` -- derived from the stage, never asserted, so
    the two can never disagree.
    """

    source_identifier: str
    stage: AcquisitionStage
    reason: str
    detail: str
    failed_at: datetime
    engine_configuration_ref: str = ""

    def __post_init__(self) -> None:
        if not (self.source_identifier or "").strip():
            raise AcquisitionError("source_identifier is required")
        if not isinstance(self.stage, AcquisitionStage):
            raise AcquisitionError(
                f"failure stage {self.stage!r} is outside the closed set"
            )
        if not (self.reason or "").strip():
            raise AcquisitionError("a failure requires a reason token")
        if not (self.detail or "").strip():
            raise AcquisitionError(
                "a failure requires a detail: a silent failure is exactly "
                "the K10/N-10 condition this record exists to prevent"
            )
        if not isinstance(self.failed_at, datetime):
            raise AcquisitionError("failed_at must be a datetime")
        if not (self.engine_configuration_ref or "").strip():
            raise AcquisitionError(
                "a failure record identifies the configuration in force "
                "[N-10]; the request's engine_configuration_ref is "
                "required, never blank"
            )

    @property
    def engine(self) -> "Engine":
        """The failing engine: Research, by create authority. [K8, N-10]"""
        return Engine.RESEARCH

    @property
    def attempted(self) -> bool:
        """N-10's mandatory distinction: was the external act attempted?

        Gate refusals (request validation, resolution, gate 2 typability,
        gate 3 rights) happen BEFORE the external act -- enforcement
        precedes acquisition (N-21 S 5.2) -- so nothing was attempted and
        the failure means NOT-ATTEMPTED. Duplicate (E-V6) and store
        refusals happen after material is in hand: the attempt was made
        and failed, meaning ATTEMPTED-AND-FAILED. Derived from the
        stage so the classification cannot drift from the record.
        """
        return self.stage in (
            AcquisitionStage.DUPLICATE_ACQUISITION,
            AcquisitionStage.STORE_REJECTED,
        )

    def as_failure_record(
        self,
        cycle_id: int | None = None,
        invocation_index: int | None = None,
    ) -> "FailureRecord":
        """Project into the platform's N-10 failure-record shape.

        Mirrors Orchestration's convention (T01.6.3): object_id names the
        engine because no object was produced; the single rule result
        carries the acquisition nature (stage + reason) -- a projection
        label, not a ratified acceptance rule. Invocation identity is
        optional exactly as N-10's precedent records it: only an
        orchestrated invocation HAS one.
        """
        return FailureRecord(
            object_id=f"engine:{self.engine.value}",
            object_type=ObjectType.EVIDENCE,
            failed_rules=(
                RuleResult(
                    "ACQUISITION-FAILURE",
                    RuleOutcome.FAIL,
                    f"{self.stage.value}/{self.reason}: {self.detail}",
                ),
            ),
            recorded_at=self.failed_at,
            engine_configuration_ref=self.engine_configuration_ref,
            engine=self.engine,
            cycle_id=cycle_id,
            invocation_index=invocation_index,
            input_ids=(self.source_identifier,),
        )


@dataclass
class AcquisitionLog:
    """Append-only register of acquisition failures. [AC2, N-10]

    Failure records live outside the object model, exactly as N-10
    requires; nothing here ever enters the lineage graph.

    T02.2.5: attach the platform FailureStore (T01.1.7's N-10 home,
    co-located with configuration per N-7) and every appended failure is
    projected there too, so Orchestration -- which reads failure records
    for scheduling and idempotence -- can see acquisition refusals
    instead of them dying in a side register."""

    _failures: list[AcquisitionFailure] = field(
        default_factory=list, init=False
    )
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)
    _failure_store: "FailureStore | None" = field(default=None, init=False)

    def attach(self, failure_store: "FailureStore") -> None:  # noqa: F821
        """Project every failure into the platform's N-10 store. [T02.2.5]"""
        with self._lock:
            self._failure_store = failure_store

    def append(self, failure: AcquisitionFailure) -> AcquisitionFailure:
        with self._lock:
            self._failures.append(failure)
            store = self._failure_store
        if store is not None:
            # Projected outside the log lock: the FailureStore guards
            # itself, and projection can never deadlock the register.
            store.record(failure.as_failure_record())
        return failure

    def __len__(self) -> int:
        with self._lock:
            return len(self._failures)

    def __iter__(self) -> Iterator[AcquisitionFailure]:
        with self._lock:
            return iter(tuple(self._failures))

    def for_source(self, source_identifier: str) -> tuple[AcquisitionFailure, ...]:
        with self._lock:
            return tuple(
                f
                for f in self._failures
                if f.source_identifier == source_identifier
            )


# ---------------------------------------------------------------------------
# The request  [AC1, AC3 -- everything required, nothing defaulted]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AcquisitionRequest:
    """One acquisition attempt, fully specified by the Research Engine.

    Every field that Provenance requires (IOM S 3.1 / E-V2) is REQUIRED
    here and never defaulted: the caller documents the fidelity of each
    capture (AC3), the method, the observation time, and R-3's two
    confidence components -- supplied separately, never conflated, with
    no ceiling invented (V5 is enforced at acceptance, not here).

    Content arrives either in full or by reference with its fingerprint
    (N-15); the storage mode is NOT chosen here -- it is determined by
    the rights assessment's retention right (N-21 S 5.7).
    """

    source_identifier: str
    source_type: str
    acquisition_method: str
    capture_fidelity: str
    acquired_at: datetime
    observed_at: datetime
    evidential_support: float
    assertion_confidence: float
    content: str | None = None
    content_reference: str | None = None
    content_fingerprint: str | None = None
    source_reliability: float | None = None
    publication_date: datetime | None = None
    author_identifier: str | None = None
    independence_group: str | None = None
    engine_configuration_ref: str = "research-acquisition-v1"

    def __post_init__(self) -> None:
        for name in (
            "source_identifier",
            "source_type",
            "acquisition_method",
            "capture_fidelity",
        ):
            if not (getattr(self, name) or "").strip():
                raise AcquisitionError(
                    f"{name} is required [IOM section 3.1, E-V2; "
                    f"capture_fidelity is documented per acquisition "
                    f"(T02.2.1 AC3)]"
                )
        for name in ("acquired_at", "observed_at"):
            if not isinstance(getattr(self, name), datetime):
                raise AcquisitionError(f"{name} must be a datetime [E-V5]")
        if self.observed_at > self.acquired_at:
            raise AcquisitionError(
                f"observed_at must be <= acquired_at [E-V5]"
            )
        if not isinstance(self.evidential_support, (int, float)) or isinstance(
            self.evidential_support, bool
        ):
            raise AcquisitionError("evidential_support must be numeric [R-3]")
        if not isinstance(
            self.assertion_confidence, (int, float)
        ) or isinstance(self.assertion_confidence, bool):
            raise AcquisitionError(
                "assertion_confidence must be numeric [R-3]"
            )
        has_full = self.content is not None
        has_reference = (self.content_reference or "").strip() and (
            self.content_fingerprint or ""
        ).strip()
        if has_full and has_reference:
            raise AcquisitionError(
                "provide content OR (content_reference + fingerprint), "
                "not both [N-15]"
            )
        if not has_full and not has_reference:
            raise AcquisitionError(
                "acquisition requires material: content or "
                "(content_reference + fingerprint) [N-15, E-V3]"
            )


def _failure(
    request: AcquisitionRequest | None,
    source_identifier: str,
    stage: AcquisitionStage,
    reason: str,
    detail: str,
    log: AcquisitionLog,
    now: datetime,
) -> AcquisitionFailure:
    return log.append(
        AcquisitionFailure(
            source_identifier=source_identifier,
            stage=stage,
            reason=reason,
            detail=detail,
            failed_at=now,
            engine_configuration_ref=(
                request.engine_configuration_ref
                if isinstance(request, AcquisitionRequest)
                else "unknown: malformed request"
            ),
        )
    )


def _refuse(failure: AcquisitionFailure) -> AcquisitionRefusedError:
    return AcquisitionRefusedError(
        f"acquisition refused for {failure.source_identifier!r} at "
        f"{failure.stage.value} ({failure.reason}): {failure.detail}"
    )


# ---------------------------------------------------------------------------
# Acquisition  [T02.2.1]
# ---------------------------------------------------------------------------


_MODE_MAP: dict[RightsStorageMode, StorageMode] = {
    RightsStorageMode.FULL: StorageMode.FULL,
    RightsStorageMode.REFERENCE_ONLY: StorageMode.REFERENCE,
}
"""The N-15/N-21 S 5.7 determination: retention right -> storage mode."""


def acquire(
    request: AcquisitionRequest,
    *,
    registry: SourceRegistry,
    store: KnowledgeStore,
    # Annotation-only dependency (exit-gate import budget): consumed
    # through its ratified surface (covers), contract pinned by tests
    # and the verifier. None behaves as an EMPTY registry: gate 1 then
    # refuses everything -- acquisition occurs only under an IN_EFFECT
    # directive (N-23 S 5.2), so absence is fail-closed, never open.
    directives: "DirectiveRegistry | None" = None,
    # Annotation-only dependency, deliberately NOT imported at runtime: the
    # exit gate fixes non-store modules at <=6 oip imports, and the coverage
    # register is consumed through its ratified surface (record/count) --
    # duck-typed here, contract pinned by tests and the verifier.
    out_of_frame: "OutOfFrameRegister",
    refusals: RefusalRegister,
    log: AcquisitionLog,
    assessment: RightsAssessment | None = None,
    clock: Callable[[], datetime] = utc_now,
) -> Evidence:
    """Acquire source material as Evidence with complete provenance. [AC1]

    Evaluation order is the ratified gate order minus gate 1 (M-01 /
    T02.2.4): request validation, source resolution, gate 2 typability,
    gate 3 rights -- halting at the first refusal with exactly one
    recorded failure. Admitted material is persisted through the store's
    acceptance path (E-V1..E-V6); a store rejection is itself recorded.

    Fail-closed throughout: no Evidence object is created or leaked on
    any refusal, and UNASSESSED rights refuse (silence is not
    permission).
    """
    now = clock()

    # -- a non-request argument is a programming error, refused before
    # any gate touches it. [AC2 of silence]
    if not isinstance(request, AcquisitionRequest):
        raise AcquisitionError(
            f"expected an AcquisitionRequest, got {request!r}"
        )

    # -- gate 1: scope. [N-20 S 5.2.1; N-23 S 5.2 -- AC1, AC3]
    # The FIRST gate of the ratified sequence, before resolution,
    # typability and rights: acquisition occurs only under an IN_EFFECT
    # directive, and one refusal reason is produced (halt-on-first).
    # Duck-typed at the ratified surface (covers) to keep the module
    # import budget within the exit gate; the registry's contract is
    # pinned by tests and verify_t02_2_4.
    covering = (
        directives.covers(request.source_identifier, now)
        if directives is not None
        else None
    )
    if covering is None:
        failure = _failure(
            request, request.source_identifier,
            AcquisitionStage.OUT_OF_SCOPE, "OUT_OF_SCOPE",
            "no IN_EFFECT directive covers this target; acquisition "
            "occurs only under one [N-20 S 5.2.1 gate 1, N-23 S 5.2] -- "
            "the refusal is recorded, never silent [G16]", log, now,
        )
        raise _refuse(failure)

    # -- a request is fully validated at CONSTRUCTION (its __post_init__
    # refuses malformed fields, so nothing malformed reaches this far).
    # The non-request guard now runs BEFORE gate 1 (moved when gate 1
    # became the first evaluation).

    # -- source resolution: the registry is what the platform knows. [N-04]
    try:
        record = registry.resolve(request.source_identifier)
    except Exception as exc:  # SourceNotFoundError
        failure = _failure(
            request, request.source_identifier,
            AcquisitionStage.UNREGISTERED_SOURCE, "NOT_REGISTERED",
            f"the source does not resolve in the registry; register it "
            f"before acquiring [N-04]: {exc}", log, now,
        )
        raise _refuse(failure) from exc
    if record.source_type != request.source_type:
        failure = _failure(
            request, request.source_identifier,
            AcquisitionStage.SOURCE_TYPE_MISMATCH, "TYPE_MISMATCH",
            f"registered as {record.source_type!r} but the request "
            f"declares {request.source_type!r}; source records are "
            f"immutable [R-1]", log, now,
        )
        raise _refuse(failure)

    # -- gate 2: typability. [N-20 S 5.2.1; refusal -> out-of-frame]
    try:
        member = classify(request.source_type)
    except UntypableChannelError as exc:
        out_of_frame.record(
            request.source_identifier,
            request.source_type,
            f"gate 2 refusal during acquisition: {exc}",
        )
        failure = _failure(
            request, request.source_identifier,
            AcquisitionStage.UNTYPABLE_CHANNEL, "UNTYPABLE_CHANNEL",
            f"the channel maps onto no taxonomy member and is INELIGIBLE; "
            f"recorded in the out-of-frame register [N-20 S 5.2, "
            f"N-22 S 5.2.1]: {exc}", log, now,
        )
        raise _refuse(failure) from exc

    # -- gate 3: rights, evaluated before the external act. [N-21 S 5.2]
    rights = assessment if assessment is not None else unassessed(
        request.source_identifier
    )
    decision = evaluate_gate(rights, refusals=refusals, now=now)
    if not decision.admitted:
        assert decision.refusal is not None  # structural invariant
        failure = _failure(
            request, request.source_identifier,
            AcquisitionStage.REFUSED_BY_RIGHTS,
            decision.refusal.reason.value,
            decision.refusal.detail, log, now,
        )
        raise _refuse(failure)

    # -- admitted: compose provenance and content. [AC1, N-15, N-21 S 5.9]
    assert decision.storage_mode is not None  # structural invariant
    mode = _MODE_MAP[decision.storage_mode]
    if mode is StorageMode.FULL:
        assert request.content is not None  # validated by the request
        body = EvidenceContent.full(request.content)
    else:
        assert request.content_reference is not None  # validated
        body = EvidenceContent.by_reference(
            request.content_reference, request.content_fingerprint or ""
        )

    provenance = Provenance(
        source_identifier=request.source_identifier,
        source_type=request.source_type,
        acquisition_method=request.acquisition_method,
        acquired_at=request.acquired_at,
        access_conditions=access_conditions_value(rights),
        capture_fidelity=request.capture_fidelity,
        source_reliability=request.source_reliability,
        publication_date=request.publication_date,
        author_identifier=request.author_identifier,
        source_independence_group=request.independence_group,
    )

    identity = store.allocator.new_object()
    attributes = UniversalAttributes(
        identity=identity,
        object_type=ObjectType.EVIDENCE,
        produced_by_engine=Engine.RESEARCH,
        produced_at=now,
        engine_configuration_ref=request.engine_configuration_ref,
        derives_from=(),
        explanation=Explanation(
            objects_referenced=(request.source_identifier,),
            criteria_applied=(
                "gate-1 scope: " + covering.directive_id,
                "gate-2 typability: " + member.value,
                "gate-3 rights: " + decision.storage_mode.value,
            ),
            reasoning=(
                f"Acquired from {request.source_identifier!r} by "
                f"{request.acquisition_method} under research directive "
                f"{covering.directive_id!r} ({covering.description}); "
                f"fidelity: {request.capture_fidelity}"
            ),
        ),
        evidence_reachable=True,
        confidence=Confidence.create(
            float(request.evidential_support),
            float(request.assertion_confidence),
        ),
        asserted_at=now,
        observed_at=request.observed_at,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        independent_source_count=1,
    )

    evidence = Evidence(
        attributes=attributes, provenance=provenance, content=body
    )

    # -- persistence through the acceptance path. [E-V1..E-V6, N-6]
    try:
        stored = store.write_evidence(evidence)
    except WriteRejectedError as exc:
        if "E-V6" in exc.failure.rule_ids:
            # T02.2.2 AC1: a duplicate acquisition (same fingerprint plus
            # source, E-V6) is its own classified outcome, so the duplicate
            # rate is measurable from recorded facts [N-03, N-10].
            failure = _failure(
                request, request.source_identifier,
                AcquisitionStage.DUPLICATE_ACQUISITION, "E-V6",
                f"duplicate acquisition: ACTIVE Evidence already holds "
                f"this fingerprint from this source, so re-acquiring it "
                f"is not new evidence [E-V6]: {exc}", log, now,
            )
            raise _refuse(failure) from exc
        failure = _failure(
            request, request.source_identifier,
            AcquisitionStage.STORE_REJECTED, "ACCEPTANCE_REFUSED",
            f"the store's acceptance path refused the object (its own "
            f"failure record is retained by the store); no Evidence was "
            f"created [N-08/N-06]: {exc}", log, now,
        )
        raise _refuse(failure) from exc

    accepted = store.get_evidence(stored.object_id)
    assert accepted is not None  # just committed under the store lock
    return accepted
