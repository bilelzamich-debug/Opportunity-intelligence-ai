"""Claim extraction producing self-contained Facts with qualifying context.

Task: T03.1.1

Architecture References:
- F-V3   A Fact's claim is self-contained: interpretable without reading
         the Evidence. This module is the capability that produces such
         claims; the store's acceptance path re-checks it structurally.
- AC2    qualifying_context is required, non-empty, and carried verbatim;
         uncertainty is preserved, never silently resolved.
- AC3    Extraction density is measured and published per Evidence,
         stratified by source type (N-20); it is never a gate.
- S-3    Claim structure: subject, predicate, qualifier (explicit NONE
         when unqualified), value. Extraction granularity aligns with the
         structure -- every claim it accepts already decomposes into the
         four components, which is the alignment S-3's Known Tensions
         demand of T03.1.1. M-19 (what qualifies as a fact) remains OPEN;
         nothing here closes it by implementation choice.
- S-5    Layer 1 at extraction: the anchor must resolve to a real span in
         the referenced Evidence, and the claim's subject, predicate and
         -- where present -- value must appear at that span. This rejects
         fabricated locations and fabricated quantities. It does NOT
         catch paraphrase drift: that is Layer 2 sampling (T03.2.2) and
         the published rate (T03.2.3). M-20 / M-67 remain OPEN.
- R-5 / D-05
         Facts are canonical claims. This module never merges: merging is
         T03.1.4. Equivalence against existing ACTIVE Facts is assessed
         with the S-3 four-condition test and REPORTED, so under-merging
         -- the safe direction -- is the only possible outcome here.
- R-3    Two confidence components, never conflated: assertion_confidence
         is the extractor's stated certainty for this claim;
         evidential_support is the source Evidence's own effective
         confidence (IOM S 3.2: a Fact from a single weak source cannot
         exceed that source's confidence). V5 re-checks the ceiling on
         the acceptance path.
- N-4    Inputs reproducible: the request carries everything; the engine
         invents no value. Property-based tests only.
- N-10   Every refusal is a recorded failure carrying its stage; failed
         extraction is distinguishable from found-nothing (EMPTY_CONTENT)
         and from not-attempted (unresolved or unusable Evidence).
- N-15   REFERENCE-mode Evidence is not verifiable in place (drift
         exposure recorded at acquisition); extraction refuses it rather
         than produce a Fact whose anchor it can never re-check.
- N-16 / T02.1.3
         One Evidence contributes exactly one source;
         independence_assessment starts UNASSESSED and is never inferred.
- N-20   The eight-member closed taxonomy stratifies the density report.
- N-21 / N-24
         Rights were enforced before acquisition. Extraction performs no
         rights judgement and invents none.
- N-22   Coverage and density reports are descriptive, never gates.
- V7 / IOM S 2.5
         Only the Fact Extraction engine creates Facts; that is the
         create authority this module exercises and nothing else.
- M-11   Closed by R-5: identity and deduplication live in the Fact
         registry and the S-3 equivalence test, not here.

WHAT IS IMPLEMENTED (the three T03.1.1 acceptance criteria)
------------------------------------------------------------
- AC1  Claims interpretable without reading the Evidence: one request per
  claim, carrying the complete S-3 decomposition plus qualifying context;
  the produced Fact is structurally self-contained (F-V3) and grounded at
  a verbatim span of its Evidence.
- AC2  qualifying_context preserved verbatim; qualifier state explicit;
  low confidence preserved (never clamped); ambiguous anchors refused,
  never guessed.
- AC3  Density measured per Evidence (claims per 1,000 characters --
  language-agnostic -- with a whitespace word count secondary), stratified
  by source type, published in ExtractionReport; consistency demonstrated
  by the verifier on the P2 exit corpus.

WHAT IS DELIBERATELY NOT IMPLEMENTED
-------------------------------------
- T03.1.2 (decomposition as a capability), T03.1.3 (positional anchoring
  machinery -- the anchor here is the verbatim source span, the only
  locator mechanically resolvable today), T03.1.4 (merging / DUPLICATES
  recording), T03.1.5 (claim-type classification: the caller states it,
  F-V4 requires it at construction), T03.2.1-3 (Layer 1 at acceptance for
  all Facts, sampled audit, published rates).
- No new semantics: no rights judgement, no independence inference, no
  density gate, no coverage effect.

The anchor convention: the T03.1.1 locator IS the verbatim span -- the
exact contiguous excerpt of the Evidence content the claim was extracted
from, occurring exactly once. Exact-match resolution is what makes the
Layer-1 check mechanical and language-agnostic (no language model, no
tokeniser, no Unicode normalisation beyond casefold, matching the
AnchorVerifier's ratified semantics). T03.1.3 generalises locators.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterator

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.claim import Claim, EquivalenceResult, Quantity, UNQUALIFIED
from oip.contract import (
    Confidence,
    Engine,
    Explanation,
    LineageRef,
    ObjectStatus,
    ObjectType,
    UniversalAttributes,
    utc_now,
)
from oip.evidence import StorageMode
from oip.fact import ClaimType, EvidenceAttachment, Fact, Independence
from oip.store import KnowledgeStore, WriteRejectedError

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ExtractionError(Exception):
    """Base class for extraction violations."""


class ExtractionRefusedError(ExtractionError):
    """Extraction was refused; the failure is recorded, never silent.

    [T03.1.1, N-10] The attached failure names its stage and reason, so a
    refusal is always distinguishable from found-nothing and from a Fact
    that does not exist because it was never attempted."""


# ---------------------------------------------------------------------------
# Failure records  [N-10]
# ---------------------------------------------------------------------------


class ExtractionStage(str, Enum):
    """Why an extraction refused. Closed set; one per attempt.

    Order mirrors evaluation: request validity, Evidence resolution and
    usability, temporal consistency, content, anchor resolution, Layer-1
    component presence, persistence."""

    INVALID_REQUEST = "INVALID_REQUEST"
    EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
    EVIDENCE_NOT_EXTRACTABLE = "EVIDENCE_NOT_EXTRACTABLE"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    EMPTY_CONTENT = "EMPTY_CONTENT"
    ANCHOR_NOT_FOUND = "ANCHOR_NOT_FOUND"
    AMBIGUOUS_ANCHOR = "AMBIGUOUS_ANCHOR"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    STORE_REJECTED = "STORE_REJECTED"


# Stages at which the extraction judgement was actually evaluated against
# content in hand. Earlier stages are NOT-ATTEMPTED: no judgement was
# possible, so the record must never be read as "the extractor tried and
# failed". EMPTY_CONTENT is the found-nothing case: the judgement ran and
# there was nothing in the material to assert. [N-10]
_ATTEMPTED_STAGES = frozenset(
    {
        ExtractionStage.EMPTY_CONTENT,
        ExtractionStage.ANCHOR_NOT_FOUND,
        ExtractionStage.AMBIGUOUS_ANCHOR,
        ExtractionStage.UNSUPPORTED_CLAIM,
        ExtractionStage.STORE_REJECTED,
    }
)


@dataclass(frozen=True)
class ExtractionFailure:
    """One recorded extraction failure. Never silent. [N-10]

    The engine is Fact Extraction by create authority (K8: `engine`
    property). `attempted` is derived from the stage so the N-10
    distinction can never drift from the record.
    """

    evidence_ref: str
    stage: ExtractionStage
    reason: str
    detail: str
    failed_at: datetime
    engine_configuration_ref: str

    def __post_init__(self) -> None:
        if not (self.evidence_ref or "").strip():
            raise ExtractionError("evidence_ref is required")
        if not isinstance(self.stage, ExtractionStage):
            raise ExtractionError(
                f"failure stage {self.stage!r} is outside the closed set"
            )
        if not (self.reason or "").strip():
            raise ExtractionError("a failure requires a reason token")
        if not (self.detail or "").strip():
            raise ExtractionError(
                "a failure requires a detail: a silent failure is exactly "
                "the N-10 condition this record exists to prevent"
            )
        if not isinstance(self.failed_at, datetime):
            raise ExtractionError("failed_at must be a datetime")
        if not (self.engine_configuration_ref or "").strip():
            raise ExtractionError(
                "a failure record identifies the configuration in force "
                "[N-10]; engine_configuration_ref is required, never blank"
            )

    @property
    def engine(self) -> Engine:
        """The failing engine: Fact Extraction, by create authority. [K8]"""
        return Engine.FACT_EXTRACTION

    @property
    def attempted(self) -> bool:
        """Whether the extraction judgement was evaluated. [N-10]

        False for INVALID_REQUEST / EVIDENCE_NOT_FOUND /
        EVIDENCE_NOT_EXTRACTABLE: nothing was judged. True from
        EMPTY_CONTENT onward: content was in hand and the claim was
        evaluated -- EMPTY_CONTENT itself being the found-nothing case.
        """
        return self.stage in _ATTEMPTED_STAGES

    def as_failure_record(
        self,
        cycle_id: int | None = None,
        invocation_index: int | None = None,
    ) -> FailureRecord:
        """Project into the platform's N-10 failure-record shape.

        Mirrors the acquisition convention (T02.2.5): object_id names the
        engine because no object was produced; the single rule result
        carries the stage and reason -- a projection label, not a
        ratified acceptance rule.
        """
        return FailureRecord(
            object_id=f"engine:{self.engine.value}",
            object_type=ObjectType.FACT,
            failed_rules=(
                RuleResult(
                    "EXTRACTION-FAILURE",
                    RuleOutcome.FAIL,
                    f"{self.stage.value}/{self.reason}: {self.detail}",
                ),
            ),
            recorded_at=self.failed_at,
            engine_configuration_ref=self.engine_configuration_ref,
            engine=self.engine,
            cycle_id=cycle_id,
            invocation_index=invocation_index,
            input_ids=(self.evidence_ref,),
        )


@dataclass
class ExtractionLog:
    """Append-only register of extraction failures. [N-10]

    Failure records live outside the object model; nothing here ever
    enters the lineage graph. An attached FailureStore (the N-10 home,
    T01.1.7) receives every failure by projection, so Orchestration can
    see extraction refusals instead of them dying in a side register.
    """

    _failures: list[ExtractionFailure] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _failure_store: object | None = field(default=None, init=False)

    def attach(self, failure_store: object) -> None:
        """Project every failure into the platform's N-10 store.

        Duck-typed at the ratified surface (record), like every
        cross-cutting dependency in the engine modules; the store's
        contract is pinned by tests and the verifier.
        """
        with self._lock:
            self._failure_store = failure_store

    def append(self, failure: ExtractionFailure) -> ExtractionFailure:
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

    def __iter__(self) -> Iterator[ExtractionFailure]:
        with self._lock:
            return iter(tuple(self._failures))

    def for_evidence(self, evidence_ref: str) -> tuple[ExtractionFailure, ...]:
        with self._lock:
            return tuple(
                f for f in self._failures if f.evidence_ref == evidence_ref
            )

    def by_stage(self) -> dict[ExtractionStage, int]:
        with self._lock:
            counts: dict[ExtractionStage, int] = {}
            for f in self._failures:
                counts[f.stage] = counts.get(f.stage, 0) + 1
            return counts


# ---------------------------------------------------------------------------
# The request  [AC1, AC2 -- everything required, nothing defaulted]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExtractionRequest:
    """One claim to be extracted, fully specified by the extractor.

    One request is ONE claim. Multiple claims from one Evidence are
    multiple requests, each independently anchored -- this is what makes
    accidental collapse impossible and S-3 granularity structural (the
    M-19 alignment). Every field the Fact requires is REQUIRED here and
    never defaulted: the S-3 components, the qualifying context (AC2),
    the verbatim source span (the anchor), the claim type (F-V4), and
    the extractor's own certainty (R-3).
    """

    evidence_ref: str
    subject: str
    predicate: str
    qualifying_context: str
    anchor: str
    claim_type: ClaimType
    extraction_confidence: float
    qualifier: str = UNQUALIFIED
    value: Quantity | None = None
    value_text: str | None = None
    attributed_to: str | None = None
    temporal_scope: str | None = None
    population_scope: str | None = None
    engine_configuration_ref: str = "fact-extraction-v1"

    def __post_init__(self) -> None:
        if not (self.evidence_ref or "").strip():
            raise ExtractionError("evidence_ref is required")
        # S-3 structure; F-V3 self-containment starts here.
        if not (self.subject or "").strip():
            raise ExtractionError("claim subject is required [S-3]")
        if not (self.predicate or "").strip():
            raise ExtractionError("claim predicate is required [S-3]")
        if not (self.qualifier or "").strip():
            raise ExtractionError(
                f"claim qualifier is required; state {UNQUALIFIED!r} if "
                f"unqualified [S-3]"
            )
        # AC2 / F-V3: the conditions under which the claim holds travel
        # with the claim. A claim stripped of its context changes meaning.
        if not (self.qualifying_context or "").strip():
            raise ExtractionError(
                "qualifying_context is required and never defaulted; a "
                "claim stripped of its conditions changes meaning "
                "[AC2, F-V3]"
            )
        # F-V2: a non-empty anchor; here it is the verbatim span itself.
        if not (self.anchor or "").strip():
            raise ExtractionError(
                "anchor is required: the verbatim source span the claim "
                "was extracted from [F-V2, S-5 layer 1]"
            )
        if not isinstance(self.claim_type, ClaimType):
            raise ExtractionError(
                f"claim_type {self.claim_type!r} is not a ClaimType [F-V4]"
            )
        if self.claim_type is ClaimType.ATTRIBUTED_OPINION:
            if not (self.attributed_to or "").strip():
                raise ExtractionError(
                    "ATTRIBUTED_OPINION requires attributed_to [F-V4]"
                )
        if isinstance(self.extraction_confidence, bool) or not isinstance(
            self.extraction_confidence, (int, float)
        ):
            raise ExtractionError(
                "extraction_confidence must be numeric [R-3]"
            )
        if not 0.0 <= float(self.extraction_confidence) <= 1.0:
            raise ExtractionError(
                f"extraction_confidence must be in [0.0, 1.0], got "
                f"{self.extraction_confidence} [R-3]"
            )
        # S-3 value discipline: a quantity is stated with its verbatim
        # source rendering, so Layer 1 can check the number exists at the
        # span and fidelity keeps the source's own wording. [S-5]
        if self.value is not None and not (
            self.value_text or ""
        ).strip():
            raise ExtractionError(
                "a quantitative claim requires value_text: the verbatim "
                "source rendering of the value [S-3, S-5 layer 1]"
            )
        if self.value is None and (self.value_text or "").strip():
            raise ExtractionError(
                "value_text supplied without a Quantity value; state the "
                "value or drop the text [S-3]"
            )
        for name in ("temporal_scope", "population_scope"):
            supplied = getattr(self, name)
            if supplied is not None and not supplied.strip():
                raise ExtractionError(f"{name} must be non-empty when supplied")

    def as_claim(self) -> Claim:
        """Project onto the ratified S-3 Claim structure."""
        return Claim(
            subject=self.subject,
            predicate=self.predicate,
            qualifier=self.qualifier,
            value=self.value,
        )


# ---------------------------------------------------------------------------
# S-5 Layer 1 -- the mechanical span gates
# ---------------------------------------------------------------------------


def _locate(content: str, span: str) -> int:
    """Number of exact occurrences of the verbatim span in the content.

    Exact match is the verbatim discipline: the anchor must be quoted
    from the content as captured. Case-insensitive *location* would let a
    re-cased excerpt stand in for the captured wording, which the
    fidelity rules do not license. [S-5 layer 1]
    """
    return content.count(span)


def _missing_components(
    subject: str, predicate: str, value_text: str | None, span: str
) -> tuple[str, ...]:
    """Which structured components do not appear in the span.

    Casefold substring semantics, exactly those of the ratified
    AnchorVerifier._missing_components (T01.4.6, S-5 layer 1). Reimplemented
    locally to hold extraction.py within the exit gate's <=6-import budget;
    verify_t03_1_1.py proves the two agree on randomised samples.
    """
    haystack = span.casefold()
    missing = [
        name
        for name, component in (
            ("subject", subject),
            ("predicate", predicate),
            ("value", value_text),
        )
        if component and component.casefold() not in haystack
    ]
    return tuple(missing)


# ---------------------------------------------------------------------------
# Extraction  [T03.1.1]
# ---------------------------------------------------------------------------


def _failure(
    request: ExtractionRequest | None,
    evidence_ref: str,
    stage: ExtractionStage,
    reason: str,
    detail: str,
    log: ExtractionLog,
    now: datetime,
) -> ExtractionFailure:
    return log.append(
        ExtractionFailure(
            evidence_ref=evidence_ref,
            stage=stage,
            reason=reason,
            detail=detail,
            failed_at=now,
            engine_configuration_ref=(
                request.engine_configuration_ref
                if isinstance(request, ExtractionRequest)
                else "unknown: malformed request"
            ),
        )
    )


def _refuse(failure: ExtractionFailure) -> ExtractionRefusedError:
    return ExtractionRefusedError(
        f"extraction refused for {failure.evidence_ref!r} at "
        f"{failure.stage.value} ({failure.reason}): {failure.detail}"
    )


@dataclass(frozen=True)
class ExtractionOutcome:
    """One accepted extraction. Traceable end to end.

    `equivalence` reports the S-3 assessment of this claim against every
    other ACTIVE Fact in the store (never against itself). It is a
    REPORT, not an action: merging and DUPLICATES recording are
    T03.1.4's deliverables, and extraction never merges.
    """

    fact: Fact
    evidence_ref: str
    claim: Claim
    span: str
    equivalence: tuple[tuple[Fact, EquivalenceResult], ...] = ()

    @property
    def object_id(self) -> str:
        return self.fact.object_id


def extract(
    request: ExtractionRequest,
    *,
    store: KnowledgeStore,
    log: ExtractionLog,
    clock: Callable[[], datetime] = utc_now,
) -> ExtractionOutcome:
    """Extract one self-contained claim from one Evidence object. [AC1]

    Fail-closed throughout: a Fact exists only after every gate passed --
    request validity, Evidence resolution and ACTIVE status, in-place
    verifiability (N-15), temporal consistency (V8), non-empty content,
    unique verbatim anchor, S-5 layer-1 component presence, and the
    store's own acceptance path (F-V1..F-V6 with the universal rules).
    Any refusal is recorded in the log -- and projected into an attached
    FailureStore -- before the exception is raised, so no refusal is ever
    silent and no partial trace remains.
    """
    now = clock()

    # -- a non-request argument is a programming error, refused before
    # any gate touches it.
    if not isinstance(request, ExtractionRequest):
        failure = _failure(
            request, "unknown: malformed request",
            ExtractionStage.INVALID_REQUEST, "NOT_A_REQUEST",
            f"expected an ExtractionRequest, got {request!r}", log, now,
        )
        raise _refuse(failure)

    # -- Evidence resolution: only what the store holds can be extracted
    # from, and only ACTIVE material. [Grounding; R-2]
    stored = store.find(request.evidence_ref)
    if stored is None:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.EVIDENCE_NOT_FOUND, "NOT_STORED",
            "the reference resolves to no stored object; extraction "
            "grounds claims in stored Evidence only", log, now,
        )
        raise _refuse(failure)
    if stored.object_type is not ObjectType.EVIDENCE:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.EVIDENCE_NOT_EXTRACTABLE, "NOT_EVIDENCE",
            f"the reference resolves to a "
            f"{stored.object_type.value}, not Evidence; Evidence is the "
            f"only factual input [AD-05, N-14]", log, now,
        )
        raise _refuse(failure)
    if stored.status is not ObjectStatus.ACTIVE:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.EVIDENCE_NOT_EXTRACTABLE, "NOT_ACTIVE",
            f"Evidence status is {stored.status.value}; extraction reads "
            f"ACTIVE Evidence only -- retracted or superseded material "
            f"must not ground new claims [R-2]", log, now,
        )
        raise _refuse(failure)

    evidence = store.get_evidence(request.evidence_ref)
    if evidence is None:  # structural invariant: registry agrees with store
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.EVIDENCE_NOT_FOUND, "REGISTRY_GAP",
            "the store holds the object but its Evidence registry lost "
            "the payload; refusing rather than extracting blind", log, now,
        )
        raise _refuse(failure)

    # -- V8: the Fact inherits the Evidence's observed_at, so an
    # extraction clock behind the source's observation time could not
    # produce a contract-valid Fact. Recorded, never silent.
    if now < evidence.attributes.observed_at:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.TEMPORAL_CONFLICT, "CLOCK_BEHIND_SOURCE",
            f"extraction clock {now.isoformat()} precedes the Evidence's "
            f"observed_at "
            f"({evidence.attributes.observed_at.isoformat()}); V8 could "
            f"not hold [V8, R-4]", log, now,
        )
        raise _refuse(failure)

    # -- N-15: REFERENCE-mode material is not verifiable in place, so the
    # S-5 layer-1 duty could never be re-discharged on the Fact. Refuse.
    if evidence.content.storage_mode is not StorageMode.FULL:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.EVIDENCE_NOT_EXTRACTABLE, "REFERENCE_ONLY",
            "content held by reference (N-15); the platform cannot "
            "re-read it in place, so the anchor could never be "
            "re-verified [S-5 layer 1]", log, now,
        )
        raise _refuse(failure)

    body = evidence.content.content
    if body is None or not body.strip():
        # Found-nothing, NOT failed: distinguishable by stage. [N-10]
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.EMPTY_CONTENT, "NOTHING_TO_EXTRACT",
            "the Evidence content is empty; there is nothing to assert "
            "-- this is found-nothing, not a failed judgement [N-10]",
            log, now,
        )
        raise _refuse(failure)

    # -- Anchor gate 1: the verbatim span resolves exactly once.
    # [S-5 layer 1: anchor resolves to a real span; fabricated anchors]
    occurrences = _locate(body, request.anchor)
    if occurrences == 0:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.ANCHOR_NOT_FOUND, "SPAN_NOT_IN_CONTENT",
            "the stated span does not occur verbatim in the Evidence "
            "content -- a fabricated or paraphrased location [S-5 "
            "layer 1]", log, now,
        )
        raise _refuse(failure)
    if occurrences > 1:
        # Preserve uncertainty instead of resolving it: an ambiguous
        # location is refused, never guessed. [AC2]
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.AMBIGUOUS_ANCHOR, "SPAN_NOT_UNIQUE",
            f"the stated span occurs {occurrences} times; the anchor "
            f"must identify one location -- quote a longer, distinctive "
            f"span or wait for T03.1.3 positional anchors", log, now,
        )
        raise _refuse(failure)

    # -- Anchor gate 2: the structured components appear at the span.
    # [S-5 layer 1: claims attributed to spans that do not contain them;
    # fabricated quantities]
    missing = _missing_components(
        request.subject, request.predicate, request.value_text, request.anchor
    )
    if missing:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.UNSUPPORTED_CLAIM, "COMPONENTS_ABSENT",
            f"claim components {list(missing)} absent from the anchored "
            f"span; the Evidence does not support this claim as stated "
            f"[S-5 layer 1, F-I1]", log, now,
        )
        raise _refuse(failure)

    # -- Compose the Fact. [AC1, AC2, R-3, IOM S 3.2]
    claim = request.as_claim()
    support = evidence.attributes.confidence.effective_confidence
    identity = store.allocator.new_object()
    attributes = UniversalAttributes(
        identity=identity,
        object_type=ObjectType.FACT,
        produced_by_engine=Engine.FACT_EXTRACTION,
        produced_at=now,
        engine_configuration_ref=request.engine_configuration_ref,
        derives_from=(LineageRef(request.evidence_ref, ObjectType.EVIDENCE),),
        explanation=Explanation(
            objects_referenced=(request.evidence_ref,),
            criteria_applied=(
                "S-3 claim structure: subject/predicate/qualifier/value",
                "S-5 layer 1: verbatim span unique; components present",
                "F-V3: self-contained claim with qualifying context",
                "R-3: support = source Evidence effective confidence",
            ),
            reasoning=(
                f"Extracted the claim from Evidence "
                f"{request.evidence_ref!r} at its unique verbatim span; "
                f"qualifier {request.qualifier!r}; claim_type "
                f"{request.claim_type.value}; extraction confidence "
                f"{float(request.extraction_confidence):.2f} as supplied "
                f"by the extractor; evidential support {support:.2f} "
                f"taken from the source Evidence's own effective "
                f"confidence"
            ),
        ),
        evidence_reachable=True,
        confidence=Confidence.create(
            support, float(request.extraction_confidence), upstream_ceiling=support
        ),
        asserted_at=now,
        observed_at=evidence.attributes.observed_at,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        # N-16 Tier 1: exactly one source so far; independence is never
        # inferred (T02.1.3 explicit-input model), so the attachment
        # starts UNASSESSED and corroboration stays unclaimed. [F-V5]
        independent_source_count=1,
    )
    attachment = EvidenceAttachment(
        evidence_ref=request.evidence_ref,
        positional_anchor=request.anchor,
        extracted_at=now,
        extraction_confidence=float(request.extraction_confidence),
        independence_assessment=Independence.UNASSESSED,
    )
    fact = Fact(
        attributes=attributes,
        claim=claim,
        claim_type=request.claim_type,
        attachments=(attachment,),
        qualifying_context=request.qualifying_context,
        attributed_to=(
            request.attributed_to
            if request.claim_type is ClaimType.ATTRIBUTED_OPINION
            else None
        ),
        temporal_scope=request.temporal_scope,
        population_scope=request.population_scope,
    )

    # -- Persistence through the acceptance path (F-V1..F-V6 + universal
    # rules; V5 re-checks the confidence ceiling against the source).
    try:
        stored_fact = store.write_fact(fact)
    except WriteRejectedError as exc:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.STORE_REJECTED, "ACCEPTANCE_REFUSED",
            f"the store's acceptance path refused the Fact (its own "
            f"failure record is retained by the store); no Fact was "
            f"created [N-08/N-06]: {exc}", log, now,
        )
        raise _refuse(failure) from exc

    accepted = store.get_fact(stored_fact.object_id)
    if accepted is None:  # structural invariant: just committed under lock
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.STORE_REJECTED, "REGISTRY_GAP",
            "the store accepted the Fact but its registry lost the "
            "payload; reporting refusal rather than a phantom success",
            log, now,
        )
        raise _refuse(failure)

    # -- S-3 equivalence REPORT against every other ACTIVE Fact. The
    # just-written Fact assesses EQUIVALENT against itself; that is not
    # information, so it is excluded. Nothing is merged here. [S-3, T03.1.4]
    equivalence = tuple(
        (other, result)
        for other, result in store.facts.assess_all(claim)
        if other.object_id != accepted.object_id
    )

    return ExtractionOutcome(
        fact=accepted,
        evidence_ref=request.evidence_ref,
        claim=claim,
        span=request.anchor,
        equivalence=equivalence,
    )


# ---------------------------------------------------------------------------
# Density  [AC3 -- measured and published, never a gate]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceDensity:
    """Extraction density for one Evidence object. [AC3]

    Density is claims per 1,000 characters -- character-based, so the
    metric is language-agnostic (whitespace word counts mean nothing for
    CJK text and little for RTL scripts). The word count is reported
    secondarily for comparability with prose Expectations.
    """

    evidence_ref: str
    source_type: str
    claims: int
    content_characters: int
    content_words: int
    refusals: int

    @property
    def claims_per_1000_characters(self) -> float:
        if self.content_characters == 0:
            return 0.0
        return self.claims / self.content_characters * 1000.0

    @property
    def claims_per_100_words(self) -> float:
        if self.content_words == 0:
            return 0.0
        return self.claims / self.content_words * 100.0


@dataclass(frozen=True)
class ExtractionReport:
    """Published extraction density across Evidence. [AC3, N-20, N-22]

    Descriptive by construction: nothing here gates anything (N-22).
    `evidences_without_claims` is the flagged-anomaly list -- an Evidence
    that yielded nothing must be visible, whether that was
    found-nothing, refusals, or simply no attempt yet.
    """

    rows: tuple[EvidenceDensity, ...]
    total_claims: int
    total_refusals: int
    refusals_by_stage: tuple[tuple[str, int], ...]
    evidences_without_claims: tuple[str, ...]
    density_band: tuple[float, float]
    """(min, max) claims-per-1000-chars over Evidence with >=1 claim;
    (0.0, 0.0) when no Evidence has claims."""

    @property
    def density_spread_ratio(self) -> float | None:
        """max/min density over Evidence with >=1 claim; None if undefined."""
        low, high = self.density_band
        if low <= 0.0:
            return None
        return high / low


def content_words(text: str) -> int:
    """Whitespace-delimited word count (secondary metric)."""
    return len(text.split())


def build_density_report(
    store: KnowledgeStore,
    log: ExtractionLog,
    evidence_refs: tuple[str, ...] | None = None,
) -> ExtractionReport:
    """Measure extraction density from recorded facts. [AC3]

    Everything is computed from the store and the failure log -- claims
    counted from attachments actually persisted, refusals from the log --
    so the report can never disagree with the recorded facts. [N-10]
    """
    if evidence_refs is None:
        evidence_refs = tuple(
            stored.object_id
            for stored in store.objects_of_type(ObjectType.EVIDENCE)
        )

    # Claims per Evidence, counted from persisted Fact attachments.
    claims_by_evidence: dict[str, int] = {}
    for stored in store.objects_of_type(ObjectType.FACT):
        fact = store.get_fact(stored.object_id)
        if fact is None:
            continue  # pragma: no cover - registry invariant
        for attachment in fact.attachments:
            claims_by_evidence[attachment.evidence_ref] = (
                claims_by_evidence.get(attachment.evidence_ref, 0) + 1
            )

    refusals_for: dict[str, int] = {}
    for failure in log:
        refusals_for[failure.evidence_ref] = (
            refusals_for.get(failure.evidence_ref, 0) + 1
        )

    rows: list[EvidenceDensity] = []
    for ref in evidence_refs:
        evidence = store.get_evidence(ref)
        characters, words, source_type = 0, 0, "UNKNOWN"
        if evidence is not None and evidence.content.content is not None:
            characters = len(evidence.content.content)
            words = content_words(evidence.content.content)
            source_type = evidence.provenance.source_type
        rows.append(
            EvidenceDensity(
                evidence_ref=ref,
                source_type=source_type,
                claims=claims_by_evidence.get(ref, 0),
                content_characters=characters,
                content_words=words,
                refusals=refusals_for.get(ref, 0),
            )
        )

    densities = [
        row.claims_per_1000_characters for row in rows if row.claims > 0
    ]
    band = (min(densities), max(densities)) if densities else (0.0, 0.0)
    stage_counts = log.by_stage()
    return ExtractionReport(
        rows=tuple(rows),
        total_claims=sum(row.claims for row in rows),
        total_refusals=len(log),
        refusals_by_stage=tuple(sorted(
            (stage.value, count) for stage, count in stage_counts.items()
        )),
        evidences_without_claims=tuple(
            row.evidence_ref for row in rows if row.claims == 0
        ),
        density_band=band,
    )
