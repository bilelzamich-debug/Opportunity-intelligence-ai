"""Problem inference: Facts judged to indicate a deficiency. [T04.1.1, T04.1.2]

Task: T04.1.1 (standalone inference), T04.1.2 (solution-independence
enforcement across versions)

Architecture References:
- S-4    Problem sufficiency floor: 2 independent sources across the
         supporting Facts; below the floor the inference is REFUSED, not
         accepted with low confidence. Independent means after
         independence grouping (T02.1.3): syndicated or commonly-owned
         sources count once.
- N-4    Reproducible inputs: the request carries everything -- statement,
         population, weight, domain, supporting Facts, basis, certainty.
         The engine invents no value. Regression tests assert properties,
         never output equality.
- N-10   Every refusal is a recorded, staged failure. Not-attempted
         (unresolved input, ineligible input) stays distinguishable from
         attempted-and-failed (below the S-4 floor, acceptance refusal).
- N-14   Lineage-restricted read: Problem Intelligence reads Facts and the
         Evidence beneath those Facts -- the grant that makes independent
         source identity reachable without violating stage separation.
- N-16   Tier 1 independent_source_count, derived at creation from the
         inputs' independence relationships: distinct independence keys
         across the supporting Facts' Evidence. Never a blind sum of
         per-Fact counts; never a re-traversal past Evidence.
- R-1/V11
         Content change produces a NEW version: the versioned path
         (predecessor_id) allocates the successor via allocator.succeed
         (version = predecessor + 1, lineage_id constant) and persists
         through write_problem(..., predecessor_id=...). [T04.1.2]
- R-2    SUPERSEDED is terminal: no outgoing transitions. The versioned
         write therefore follows the extraction merge precedent --
         transition predecessor, then write successor, with the failure
         surface structurally closed BEFORE the transition (the
         authoritative PROBLEM_RULES dry-run) and any residual write
         refusal naming the exact surviving state. [T04.1.2]
- R-3    Two-component confidence: evidential_support from S-2 over the
         supporting Facts (P6 bounds it by their support), assertion_
         confidence is the inferer's supplied certainty, effective bounded
         by the upstream ceiling (V5 re-checks at acceptance).
- R-6    DERIVES_FROM Problem -> Fact; SUPPORTS is the supporting subset.
         The type enforces the subset at construction; the engine draws
         both from the same request field so they cannot diverge.
- V7     Create authority: only Problem Intelligence creates Problems.
         The composed object carries produced_by_engine=PROBLEM_
         INTELLIGENCE and the store's V7 rule re-checks it.
- P-V1..P-V6
         Authoritative at acceptance (store.write_problem). The engine's
         gates are preconditions, never a bypass: P-V1 re-checks the
         declared count, P-V6 rejects single-Fact restatements and
         verbatim claim restatements, P-V5 re-checks the basis.
- P-I1   Solution-independence across ALL versions. [T04.1.2] Enforced at
         the versioned-write boundary: every version in the predecessor's
         lineage is evaluated with the authoritative
         detect_solution_language (the P-V2 machinery -- no second
         lexical definition), and a chain never becomes acceptable
         merely because its newest version is clean. P-V2 at acceptance
         and ProblemIntegrity's P-I1 re-check remain authoritative.
- IOM    section 3.3 (Problem object); Master Reference section 4.6
         (engine responsibility and boundaries).

Facts describe what is; a Problem asserts that something is *wrong*. A
Fact needs only an anchor; a Problem needs an argument -- so this engine
is a judgement gate, not a generator: the hypothesis arrives fully stated
in the request, and the engine's work is to hold it against the evidence.
"Created when Facts are judged to indicate a deficiency" (IOM 3.3
lifecycle) is realised exactly as the Fact path realises it: acceptance
IS the PROPOSED -> ACTIVE transition, and an inference that cannot clear
acceptance is refused with a recorded failure rather than persisted in a
weaker state.

The versioned path (T04.1.2) adds reformulation: a new version of an
existing Problem -- the IOM's "reformulation" versioning trigger --
entering through the same acceptance, with the predecessor transitioned
ACTIVE -> SUPERSEDED and solution-independence verified over the whole
version chain before any state changes.

Scope: the inference engine only. Severity/frequency bands (T04.1.4,
M-12), population identification (T04.1.3), deduplication (T04.1.5,
M-22) and taxonomy (T04.1.6, M-21) are deliberately absent. The engine
never merges, never links DUPLICATES, never ranks weight, never
constrains problem_domain, and never acquires evidence when support is
insufficient -- it refuses (Master Reference 4.6 boundaries; OPEN
QUESTION-11 stays open).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterator

from oip.acceptance import (
    AcceptanceContext,
    FailureRecord,
    RuleOutcome,
    RuleResult,
)
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
from oip.fact import Fact
from oip.problem import (
    PROBLEM_RULES,
    FactContribution,
    InferenceBasis,
    Problem,
    detect_solution_language,
)
from oip.store import KnowledgeStore, StoreError, WriteRejectedError
from oip.support import SupportInputs, compute_support, sufficiency_threshold


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class InferenceError(Exception):
    """Base class for inference violations."""


class InferenceRefusedError(InferenceError):
    """Inference was refused; the failure is recorded, never silent.

    [T04.1.1, N-10] The attached failure names its stage and reason, so a
    refusal is always distinguishable from an inference that was never
    attempted because its inputs did not exist or were ineligible.
    """


# ---------------------------------------------------------------------------
# Failure records  [N-10]
# ---------------------------------------------------------------------------


class InferenceStage(str, Enum):
    """Why an inference refused. Closed set; one per attempt.

    Order mirrors evaluation: request validity, Fact resolution and
    lifecycle eligibility, Evidence resolution beneath the Facts, the
    S-4 sufficiency judgement, temporal consistency, persistence."""

    INVALID_REQUEST = "INVALID_REQUEST"
    FACT_NOT_FOUND = "FACT_NOT_FOUND"
    FACT_NOT_ACTIVE = "FACT_NOT_ACTIVE"
    EVIDENCE_UNRESOLVED = "EVIDENCE_UNRESOLVED"
    INSUFFICIENT_SOURCES = "INSUFFICIENT_SOURCES"
    TEMPORAL_CONFLICT = "TEMPORAL_CONFLICT"
    STORE_REJECTED = "STORE_REJECTED"
    # T04.1.2: the versioned path (reformulation). [P-V2, P-I1, R-1/V11]
    PREDECESSOR_NOT_FOUND = "PREDECESSOR_NOT_FOUND"
    PREDECESSOR_NOT_A_PROBLEM = "PREDECESSOR_NOT_A_PROBLEM"
    PREDECESSOR_NOT_ACTIVE = "PREDECESSOR_NOT_ACTIVE"
    CHAIN_NOT_SOLUTION_INDEPENDENT = "CHAIN_NOT_SOLUTION_INDEPENDENT"


# Stages at which the sufficiency judgement was actually evaluated against
# the evidence in hand. Earlier stages are NOT-ATTEMPTED: no judgement was
# possible, so the record must never be read as "the engine tried and
# failed". There is deliberately no EMPTY stage: one request is one
# hypothesis, so "ran and found nothing" has no meaning here, and the
# found-nothing distinction extraction needs does not collapse into
# anything -- it simply does not arise. [N-10]
#
# CHAIN_NOT_SOLUTION_INDEPENDENT is attempted [T04.1.2]: the chain was in
# hand and the solution-independence judgement ran over every version.
# The predecessor-resolution stages are not-attempted, like every other
# input-resolution failure.
_ATTEMPTED_STAGES = frozenset(
    {
        InferenceStage.INSUFFICIENT_SOURCES,
        InferenceStage.STORE_REJECTED,
        InferenceStage.CHAIN_NOT_SOLUTION_INDEPENDENT,
    }
)


@dataclass(frozen=True)
class InferenceFailure:
    """One recorded inference failure. Never silent. [N-10]

    The engine is Problem Intelligence by create authority (K8: `engine`
    property). `attempted` is derived from the stage so the N-10
    distinction can never drift from the record.
    """

    fact_refs: tuple[str, ...]
    stage: InferenceStage
    reason: str
    detail: str
    failed_at: datetime
    engine_configuration_ref: str

    def __post_init__(self) -> None:
        if not self.fact_refs:
            raise InferenceError(
                "fact_refs is required: a failure names the inputs it "
                "was about to rest on [N-10]"
            )
        if not isinstance(self.stage, InferenceStage):
            raise InferenceError(
                f"failure stage {self.stage!r} is outside the closed set"
            )
        if not (self.reason or "").strip():
            raise InferenceError("a failure requires a reason token")
        if not (self.detail or "").strip():
            raise InferenceError(
                "a failure requires a detail: a silent failure is exactly "
                "the N-10 condition this record exists to prevent"
            )
        if not isinstance(self.failed_at, datetime):
            raise InferenceError("failed_at must be a datetime")
        if not (self.engine_configuration_ref or "").strip():
            raise InferenceError(
                "a failure record identifies the configuration in force "
                "[N-10]; engine_configuration_ref is required, never blank"
            )

    @property
    def engine(self) -> Engine:
        """The failing engine: Problem Intelligence, by authority. [K8]"""
        return Engine.PROBLEM_INTELLIGENCE

    @property
    def attempted(self) -> bool:
        """Whether the sufficiency judgement was evaluated. [N-10]

        False through TEMPORAL_CONFLICT: nothing was judged, the inputs
        were not usable. True for INSUFFICIENT_SOURCES (the evidence was
        in hand and fell short) and STORE_REJECTED (the authoritative
        acceptance path refused the composed Problem).
        """
        return self.stage in _ATTEMPTED_STAGES

    def as_failure_record(
        self,
        cycle_id: int | None = None,
        invocation_index: int | None = None,
    ) -> FailureRecord:
        """Project into the platform's N-10 failure-record shape.

        Mirrors the extraction convention (T03.1.1): object_id names the
        engine because no object was produced; the single rule result
        carries the stage and reason -- a projection label, not a
        ratified acceptance rule.
        """
        return FailureRecord(
            object_id=f"engine:{self.engine.value}",
            object_type=ObjectType.PROBLEM,
            failed_rules=(
                RuleResult(
                    "INFERENCE-FAILURE",
                    RuleOutcome.FAIL,
                    f"{self.stage.value}/{self.reason}: {self.detail}",
                ),
            ),
            recorded_at=self.failed_at,
            engine_configuration_ref=self.engine_configuration_ref,
            engine=self.engine,
            cycle_id=cycle_id,
            invocation_index=invocation_index,
            input_ids=self.fact_refs,
        )


@dataclass
class InferenceLog:
    """Append-only register of inference failures. [N-10]

    Failure records live outside the object model; nothing here ever
    enters the lineage graph. An attached FailureStore (the N-10 home,
    T01.1.7) receives every failure by projection, so Orchestration can
    see inference refusals instead of them dying in a side register.
    """

    _failures: list[InferenceFailure] = field(default_factory=list)
    _lock: threading.RLock = field(default_factory=threading.RLock)
    _failure_store: object | None = field(default=None, init=False)

    def attach(self, failure_store: object) -> None:
        """Project every failure into the platform's N-10 store.

        Duck-typed at the ratified surface (record), like every
        cross-cutting dependency in the engine modules.
        """
        with self._lock:
            self._failure_store = failure_store

    def append(self, failure: InferenceFailure) -> InferenceFailure:
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

    def __iter__(self) -> Iterator[InferenceFailure]:
        with self._lock:
            return iter(tuple(self._failures))

    def for_facts(self, *fact_refs: str) -> tuple[InferenceFailure, ...]:
        wanted = frozenset(fact_refs)
        with self._lock:
            return tuple(
                f for f in self._failures if wanted & set(f.fact_refs)
            )

    def by_stage(self) -> dict[InferenceStage, int]:
        with self._lock:
            counts: dict[InferenceStage, int] = {}
            for f in self._failures:
                counts[f.stage] = counts.get(f.stage, 0) + 1
            return counts


# ---------------------------------------------------------------------------
# The request  [N-4]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferenceRequest:
    """One problem hypothesis, fully specified by the inferer.

    One request is ONE hypothesis over a named set of supporting Facts.
    Every field the Problem requires is REQUIRED here and never defaulted:
    the statement, the population, both weight components, the domain,
    the per-Fact basis with its synthesis, and the inferer's own
    certainty. The engine contributes no content of its own -- its work
    is to hold this hypothesis against the store's evidence. [N-4]

    Severity and frequency are free text: no scales exist (M-12 open,
    bands land at T04.1.4). problem_domain is free text: no taxonomy
    exists (M-21 open, lands at T04.1.6). The basis must cover exactly
    the supporting set: every supporting Fact represented, nothing else
    (P-V5; the engine enforces coverage, the type and the acceptance
    path re-check the rest).
    """

    fact_refs: tuple[str, ...]
    problem_statement: str
    affected_population: str
    severity: str
    frequency: str
    problem_domain: str
    contributions: tuple[FactContribution, ...]
    synthesis: str
    inference_confidence: float
    population_size_estimate: int | None = None
    existing_workarounds: str | None = None
    problem_persistence: str | None = None
    cost_indication: str | None = None
    engine_configuration_ref: str = "problem-inference-v1"

    def __post_init__(self) -> None:
        # The supporting Facts: plural expected, but a single Fact is a
        # legal REQUEST -- P-V6 at acceptance is what rejects it, and the
        # engine does not pre-empt the authoritative rule.
        if not self.fact_refs:
            raise InferenceError(
                "a Problem hypothesis requires the Facts it rests on "
                "[P-V1]"
            )
        if len(set(self.fact_refs)) != len(self.fact_refs):
            raise InferenceError(
                "the same Fact supports the hypothesis twice; "
                "corroboration cannot be manufactured by repetition "
                "[P-V1]"
            )
        for name in (
            "problem_statement",
            "affected_population",
            "severity",
            "frequency",
            "problem_domain",
            "synthesis",
        ):
            if not (getattr(self, name) or "").strip():
                raise InferenceError(f"{name} is required [N-4, IOM 3.3]")
        if not self.contributions:
            raise InferenceError(
                "inference_basis contributions are required; a Problem "
                "needs an argument, not just a statement [P-V5]"
            )
        # Exact coverage: every supporting Fact represented, no Fact
        # outside the supporting set represented. The InferenceBasis type
        # enforces the phantom and duplicate rules at composition; the
        # request enforces coverage here so a mismatched request can
        # never reach the store.
        covered = frozenset(c.fact_ref for c in self.contributions)
        supporting = frozenset(self.fact_refs)
        if len(covered) != len(self.contributions):
            # The InferenceBasis type would catch this at composition;
            # catching it here keeps the failure at the request boundary,
            # where the caller can fix it. [P-V5]
            raise InferenceError(
                "the same Fact contributes twice to the inference basis "
                "[P-V5]"
            )
        if covered != supporting:
            missing = sorted(supporting - covered)
            extra = sorted(covered - supporting)
            raise InferenceError(
                f"inference_basis must cover exactly the supporting Facts; "
                f"unrepresented {missing}, non-supporting {extra} [P-V5]"
            )
        if isinstance(self.inference_confidence, bool) or not isinstance(
            self.inference_confidence, (int, float)
        ):
            raise InferenceError(
                "inference_confidence must be numeric [R-3]"
            )
        if not 0.0 <= float(self.inference_confidence) <= 1.0:
            raise InferenceError(
                f"inference_confidence must be in [0.0, 1.0], got "
                f"{self.inference_confidence} [R-3]"
            )
        if self.population_size_estimate is not None:
            if self.population_size_estimate < 0:
                raise InferenceError(
                    "population_size_estimate must be non-negative"
                )
        for name in (
            "existing_workarounds",
            "problem_persistence",
            "cost_indication",
        ):
            supplied = getattr(self, name)
            if supplied is not None and not supplied.strip():
                raise InferenceError(
                    f"{name} must be non-empty when supplied; absence "
                    "stays absence [N-4]"
                )
        if not (self.engine_configuration_ref or "").strip():
            raise InferenceError(
                "engine_configuration_ref is required [N-4, N-7]"
            )

    def as_basis(self) -> InferenceBasis:
        """Project onto the ratified P-V5 basis structure."""
        return InferenceBasis(
            contributions=self.contributions,
            synthesis=self.synthesis,
        )


# ---------------------------------------------------------------------------
# The outcome
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InferenceOutcome:
    """One accepted inference. Traceable end to end.

    `independence_keys` are the distinct T02.1.3 keys beneath the
    supporting Facts' ACTIVE Evidence -- the identity behind the N-16
    Tier 1 count, published on the outcome so the derivation is
    auditable rather than a bare number. `evidence_refs` names every
    Evidence consulted, in supporting-Fact order then attachment order.
    """

    problem: Problem
    supporting_fact_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    independence_keys: frozenset[str]
    independent_source_count: int
    source_type_count: int
    evidential_support: float
    assertion_confidence: float
    predecessor_id: str | None = None
    """The superseded predecessor when this was a versioned inference
    (T04.1.2 reformulation); None on the standalone path."""

    @property
    def object_id(self) -> str:
        return self.problem.object_id


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------


def _refuse(failure: InferenceFailure) -> InferenceRefusedError:
    return InferenceRefusedError(f"{failure.stage.value}: {failure.detail}")


def _failure(
    request: InferenceRequest | object,
    stage: InferenceStage,
    reason: str,
    detail: str,
    log: InferenceLog,
    now: datetime,
) -> InferenceFailure:
    """Record a refusal in the log, then hand it back to be raised.

    Recorded BEFORE the exception is raised, so no refusal is ever
    silent and no partial trace remains. [N-10]
    """
    refs = (
        request.fact_refs
        if isinstance(request, InferenceRequest)
        else ("unknown: malformed request",)
    )
    config = (
        request.engine_configuration_ref
        if isinstance(request, InferenceRequest)
        else "unknown: malformed request"
    )
    return log.append(
        InferenceFailure(
            fact_refs=tuple(refs),
            stage=stage,
            reason=reason,
            detail=detail,
            failed_at=now,
            engine_configuration_ref=config,
        )
    )


# ---------------------------------------------------------------------------
# Versioned path  [T04.1.2]
# ---------------------------------------------------------------------------


def _claim_text_of(store: KnowledgeStore) -> Callable[[str], str | None]:
    """Claim text of a stored Fact, through public reads. [P-V6]"""

    def claim_text(object_id: str) -> str | None:
        fact = store.get_fact(object_id)
        return fact.claim.as_text() if fact is not None else None

    return claim_text


def _resolve_predecessor(
    request: InferenceRequest,
    predecessor_id: str,
    store: KnowledgeStore,
    log: InferenceLog,
    now: datetime,
) -> UniversalAttributes:
    """Resolve, type-check and eligibility-check the predecessor. [T04.1.2]

    V7: Problem Intelligence modifies Problems, so the predecessor must be
    one. R-2/IOM 3.3: the reformulation transition is ACTIVE -> SUPERSEDED,
    so a non-ACTIVE predecessor has no legal path. No state changes here.
    """
    stored = store.find(predecessor_id)
    if stored is None:
        failure = _failure(
            request, InferenceStage.PREDECESSOR_NOT_FOUND, "NOT_STORED",
            f"predecessor {predecessor_id!r} does not exist in the store; "
            f"a reformulation must name the version it supersedes [T04.1.2]",
            log, now,
        )
        raise _refuse(failure)
    if stored.attributes.object_type is not ObjectType.PROBLEM:
        failure = _failure(
            request, InferenceStage.PREDECESSOR_NOT_A_PROBLEM, "NOT_A_PROBLEM",
            f"predecessor {predecessor_id!r} is "
            f"{stored.attributes.object_type.value}, but Problem "
            f"Intelligence modifies Problems only [V7, T04.1.2]",
            log, now,
        )
        raise _refuse(failure)
    if stored.status is not ObjectStatus.ACTIVE:
        failure = _failure(
            request, InferenceStage.PREDECESSOR_NOT_ACTIVE,
            stored.status.value,
            f"predecessor {predecessor_id!r} is {stored.status.value}; the "
            f"reformulation transition is ACTIVE -> SUPERSEDED, and only "
            f"an ACTIVE version may be superseded [R-2, IOM 3.3, T04.1.2]",
            log, now,
        )
        raise _refuse(failure)
    return stored.attributes


def _check_chain_solution_independence(
    request: InferenceRequest,
    predecessor_id: str,
    store: KnowledgeStore,
    log: InferenceLog,
    now: datetime,
) -> None:
    """Solution-independence over EVERY version of the predecessor's
    lineage. [P-I1, T04.1.2]

    Uses the authoritative P-V2 machinery (detect_solution_language with
    its default marker set) -- no second lexical definition. A chain never
    becomes acceptable merely because its newest version is clean: if ANY
    existing version trips the detector, the versioned inference refuses,
    however clean the proposed successor. The proposed statement itself is
    held to the same standard by the authoritative dry-run below and by
    P-V2 at acceptance. Enumeration order cannot change the verdict: every
    version is evaluated and every violation is named.
    """
    lineage_id = store.resolve_lineage(predecessor_id)
    if lineage_id is None:  # defensive: find() resolved it above
        failure = _failure(
            request, InferenceStage.PREDECESSOR_NOT_FOUND, "NO_LINEAGE",
            f"predecessor {predecessor_id!r} resolves to no lineage",
            log, now,
        )
        raise _refuse(failure)

    violations: list[tuple[str, int, tuple[str, ...]]] = []
    for version in store.versions_of(lineage_id):
        payload = store.get_problem(version.object_id)
        if payload is None:
            # Fail-closed, the engine's guard philosophy: a version whose
            # payload cannot be read cannot be certified solution-
            # independent, so the chain cannot be verified -- refuse and
            # name the gap rather than certify what was never read.
            # Unreachable through the real store (payload registers in
            # the same critical section as the object); guarded anyway.
            # [N-10, P-I1, T04.1.2]
            failure = _failure(
                request, InferenceStage.STORE_REJECTED, "REGISTRY_GAP",
                f"version {version.object_id!r} of lineage {lineage_id!r} "
                f"has no Problem payload; the chain cannot be verified "
                f"solution-independent, so the versioned inference is "
                f"refused [P-I1, T04.1.2]",
                log, now,
            )
            raise _refuse(failure)
        markers = detect_solution_language(payload.problem_statement)
        if markers:
            violations.append(
                (version.object_id, version.attributes.version, markers)
            )

    if violations:
        described = "; ".join(
            f"v{version} {oid!r}: {list(markers)}"
            for oid, version, markers in violations
        )
        failure = _failure(
            request, InferenceStage.CHAIN_NOT_SOLUTION_INDEPENDENT,
            "VERSION_STATES_A_SOLUTION",
            f"solution-independence must hold across ALL versions [P-I1]; "
            f"violating version(s) of lineage {lineage_id!r}: {described}. "
            f"A clean successor cannot make the chain acceptable, so the "
            f"versioned inference is refused [T04.1.2]",
            log, now,
        )
        raise _refuse(failure)


def _dry_run_problem_rules(
    request: InferenceRequest,
    problem: Problem,
    store: KnowledgeStore,
    log: InferenceLog,
    now: datetime,
) -> None:
    """Run the AUTHORITATIVE P-V1..P-V6 over the composed successor, before
    any state changes. [T04.1.2]

    The versioned-write failure surface is structurally closed, extraction
    merge precedent: SUPERSEDED is terminal under R-2, so a successor-write
    rejection after the predecessor transition cannot be undone. Every
    acceptance rule that could reject the successor is therefore satisfied
    BEFORE the predecessor is touched -- by invoking the authoritative
    PROBLEM_RULES themselves (public rule functions over a public
    AcceptanceContext, exactly as the store does), never a re-implementation.
    The universal rules V1-V12 are closed by construction, mirroring the
    merge argument: V1/V9 by construction, V2/V3/V12 by resolved Facts,
    V4 by Fact lineage, V5 by the derived ceiling, V6 by the explanation,
    V7 by the engine, V8 by the pre-check, V10 by upstream-only references,
    V11 by allocator.succeed(). Should the write still fail, the refusal
    names the exact surviving state. [R-2, N-10]
    """
    ctx = AcceptanceContext(
        attributes=problem.attributes,
        problem=problem,
        fact_claim_text=_claim_text_of(store),
    )
    failed = [rule(ctx) for rule in PROBLEM_RULES]
    failures = [result for result in failed if result.failed]
    if failures:
        rule_ids = ", ".join(result.rule_id for result in failures)
        details = "; ".join(result.detail for result in failures)
        failure = _failure(
            request, InferenceStage.STORE_REJECTED, "DRY_RUN_REFUSED",
            f"the authoritative acceptance rules would refuse this "
            f"successor: {rule_ids} -- {details}; refused BEFORE the "
            f"predecessor was superseded, so no state has changed "
            f"[P-V1..P-V6, T04.1.2]",
            log, now,
        )
        raise _refuse(failure)


def infer(
    request: InferenceRequest,
    *,
    store: KnowledgeStore,
    log: InferenceLog,
    clock: Callable[[], datetime] = utc_now,
    predecessor_id: str | None = None,
) -> InferenceOutcome:
    """Infer one Problem from named supporting Facts. [AC1, AC2, AC3]

    Standalone mode (predecessor_id=None, T04.1.1): fail-closed throughout;
    a Problem exists only after every gate passed -- request validity, Fact
    resolution and ACTIVE eligibility (P-I2 as an input precondition),
    Evidence resolution beneath the Facts (N-14 grant), the S-4
    independence derivation (N-16), temporal consistency (V8), and the
    store's own acceptance path (P-V1..P-V6 over the universal rules).

    Versioned mode (predecessor_id, T04.1.2 reformulation): the predecessor
    is resolved, type-checked and ACTIVE-checked, the whole version chain
    is verified solution-independent (P-I1), the same standalone gates run,
    the successor is composed under allocator.succeed (R-1/V11), the
    authoritative PROBLEM_RULES dry-run closes the write-failure surface,
    and only then is the predecessor transitioned ACTIVE -> SUPERSEDED and
    the successor persisted through write_problem(..., predecessor_id=...).

    Any refusal is recorded in the log -- and projected into an attached
    FailureStore -- before the exception is raised, so no refusal is ever
    silent and no partial trace remains.
    """
    now = clock()

    # -- a non-request argument is a programming error, refused before
    # any gate touches it.
    if not isinstance(request, InferenceRequest):
        failure = _failure(
            request, InferenceStage.INVALID_REQUEST, "NOT_A_REQUEST",
            f"expected an InferenceRequest, got {request!r}", log, now,
        )
        raise _refuse(failure)

    # -- T04.1.2 versioned mode preamble. No state changes on any refusal
    # here: the predecessor is resolved, type-checked, eligibility-checked,
    # and its whole version chain verified solution-independent [P-I1]
    # before the shared gates run.
    predecessor_attributes: UniversalAttributes | None = None
    if predecessor_id is not None:
        predecessor_attributes = _resolve_predecessor(
            request, predecessor_id, store, log, now
        )
        _check_chain_solution_independence(
            request, predecessor_id, store, log, now
        )

    # -- Fact resolution: only what the store holds can support an
    # inference, and only Facts -- the N-14 direct input type. [N-14]
    resolved: list[Fact] = []
    for ref in request.fact_refs:
        stored = store.find(ref)
        if stored is None:
            failure = _failure(
                request, InferenceStage.FACT_NOT_FOUND, "NOT_STORED",
                f"supporting Fact {ref!r} does not exist in the store; "
                f"an inference cannot rest on an unresolved input [P-I2]",
                log, now,
            )
            raise _refuse(failure)
        if stored.attributes.object_type is not ObjectType.FACT:
            failure = _failure(
                request, InferenceStage.FACT_NOT_FOUND, "NOT_A_FACT",
                f"input {ref!r} is {stored.attributes.object_type.value}, "
                f"but Problem Intelligence consumes Facts only [N-14]",
                log, now,
            )
            raise _refuse(failure)
        # -- Lifecycle eligibility, checked at resolution: P-I2 as an
        # input precondition. A Problem accepted over an ineligible Fact
        # would pass the engine and fail continuous integrity later;
        # refusing here keeps the failure at the boundary where it can
        # be acted on. SUPERSEDED does not cascade (D-01a), so this
        # check is what surfaces it at inference time.
        if stored.status is not ObjectStatus.ACTIVE:
            failure = _failure(
                request, InferenceStage.FACT_NOT_ACTIVE,
                stored.status.value,
                f"supporting Fact {ref!r} is {stored.status.value}; a "
                f"Problem may rest only on ACTIVE support [P-I2]",
                log, now,
            )
            raise _refuse(failure)
        payload = store.get_fact(ref)
        if payload is None:
            failure = _failure(
                request, InferenceStage.FACT_NOT_FOUND, "NO_PAYLOAD",
                f"supporting Fact {ref!r} has no registered payload",
                log, now,
            )
            raise _refuse(failure)
        resolved.append(payload)

    # -- Evidence resolution beneath the Facts. [N-14] The read grant is
    # lineage-restricted: exactly the Evidence these Facts attach to.
    # Unresolved Evidence is a refusal, never a silent zero -- the
    # independence identity could not be established. Non-ACTIVE
    # Evidence contributes no key, mirroring the ACTIVE-only
    # independence counting of the Evidence registry: the count may
    # fall, never be inflated. [N-16]
    independence_keys: set[str] = set()
    source_types: set[str] = set()
    evidence_refs: list[str] = []
    for fact in resolved:
        for attachment in fact.attachments:
            evidence_refs.append(attachment.evidence_ref)
            evidence = store.evidence.get(attachment.evidence_ref)
            if evidence is None:
                failure = _failure(
                    request, InferenceStage.EVIDENCE_UNRESOLVED,
                    "EVIDENCE_NOT_STORED",
                    f"attachment {attachment.evidence_ref!r} of Fact "
                    f"{fact.object_id!r} resolves to no stored Evidence; "
                    f"independent-source identity cannot be established "
                    f"[N-14, N-16]",
                    log, now,
                )
                raise _refuse(failure)
            ev_stored = store.find(attachment.evidence_ref)
            if ev_stored is None or ev_stored.status is not ObjectStatus.ACTIVE:
                continue
            independence_keys.add(evidence.independence_key)
            source_types.add(evidence.provenance.source_type)

    # -- The S-4 sufficiency judgement. Distinct independence keys across
    # the supporting Facts' Evidence; a floor, not a gradient. Exactly 2
    # qualifies; 1 and 0 do not. [S-4, N-16, AC1]
    independent_source_count = len(independence_keys)
    threshold = sufficiency_threshold(ObjectType.PROBLEM)
    if independent_source_count < threshold:
        failure = _failure(
            request, InferenceStage.INSUFFICIENT_SOURCES,
            "BELOW_S4_FLOOR",
            f"{independent_source_count} independent source(s) "
            f"({sorted(independence_keys)}) across "
            f"{len(request.fact_refs)} supporting Fact(s); S-4 requires "
            f"{threshold}. An inference of deficiency from a single "
            f"source is that source's opinion -- the hypothesis is "
            f"refused, not accepted with low confidence",
            log, now,
        )
        raise _refuse(failure)

    # -- Temporal consistency: the Problem observes what its Facts
    # observed, no later. V8 (observed_at <= asserted_at <= produced_at)
    # is pre-checked here and re-checked at acceptance. [R-4]
    observed_at = max(
        fact.attributes.observed_at for fact in resolved
    )
    if observed_at > now:
        failure = _failure(
            request, InferenceStage.TEMPORAL_CONFLICT, "OBSERVED_AFTER_NOW",
            f"the supporting Facts were observed at {observed_at}, after "
            f"the inference time {now}; V8 temporal order cannot hold",
            log, now,
        )
        raise _refuse(failure)

    # -- Confidence. [R-3, S-2, IOM 3.3] evidential_support derives from
    # the supporting Facts' support and their source diversity; P6
    # bounds it by the contributing Facts. assertion_confidence is the
    # supplied interpretive certainty. The upstream ceiling is the min
    # of the supporting Facts' effective confidence, so V5 holds by
    # construction -- and is re-checked at acceptance regardless.
    upstream_support = tuple(
        fact.attributes.confidence.effective_confidence for fact in resolved
    )
    ceiling = min(upstream_support)
    evidential_support = compute_support(
        SupportInputs(
            independent_source_count=independent_source_count,
            source_type_count=len(source_types),
            corroboration_depth=len(resolved),
            upstream_support=upstream_support,
        )
    )

    # -- Compose the Problem. [V7, R-6, N-13, N-16] Standalone mode
    # allocates a fresh identity; versioned mode succeeds the predecessor
    # (version = predecessor + 1, lineage_id constant, R-1/V11) so the
    # successor is a new immutable version of the same logical object.
    if predecessor_attributes is None:
        identity = store.allocator.new_object()
    else:
        identity = store.allocator.succeed(predecessor_attributes.identity)
    criteria = (
        "S-4: 2 independent sources across supporting Facts",
        "N-16: Tier 1 count derived from distinct independence "
        "keys of the supporting Facts' Evidence",
        "P-V5: inference_basis covers exactly the supporting set",
        "P-V6: not a restatement of a single Fact (acceptance)",
        "R-3: support from contributing Facts, bounded by their "
        "confidence",
    )
    if predecessor_attributes is not None:
        # Versioned mode: the chain verdict is part of the argument. [T04.1.2]
        criteria = criteria + (
            "P-I1: solution-independence verified across all versions of "
            "the predecessor's lineage [T04.1.2]",
            "R-1/V11: successor of the named predecessor",
        )
    reformulation_note = (
        f"; supersedes {predecessor_id!r} (v{predecessor_attributes.version}) "
        f"under R-1/V11, with solution-independence verified over every "
        f"version of the lineage [P-I1, T04.1.2]"
        if predecessor_attributes is not None
        else ""
    )
    attributes = UniversalAttributes(
        identity=identity,
        object_type=ObjectType.PROBLEM,
        produced_by_engine=Engine.PROBLEM_INTELLIGENCE,
        produced_at=now,
        engine_configuration_ref=request.engine_configuration_ref,
        derives_from=tuple(
            LineageRef(ref, ObjectType.FACT) for ref in request.fact_refs
        ),
        explanation=Explanation(
            objects_referenced=request.fact_refs,
            criteria_applied=criteria,
            reasoning=(
                f"{'Reformulated' if predecessor_attributes is not None else 'Inferred'} "
                f"the deficiency from "
                f"{len(request.fact_refs)} supporting Fact(s) "
                f"{list(request.fact_refs)} attested by "
                f"{independent_source_count} independent source(s) "
                f"({sorted(independence_keys)}) across "
                f"{len(evidence_refs)} attachment(s); evidential support "
                f"{evidential_support:.2f} from the contributing Facts' "
                f"support and source diversity, bounded by their "
                f"confidence; assertion confidence "
                f"{float(request.inference_confidence):.2f} as supplied "
                f"by the inferer{reformulation_note}. Severity and "
                f"frequency are free text: no scales exist yet (M-12 "
                f"open, bands at T04.1.4); problem_domain is "
                f"unconstrained (M-21 open, taxonomy at T04.1.6)"
            ),
        ),
        evidence_reachable=True,
        confidence=Confidence.create(
            evidential_support,
            float(request.inference_confidence),
            upstream_ceiling=ceiling,
        ),
        asserted_at=now,
        observed_at=observed_at,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        independent_source_count=independent_source_count,
    )
    problem = Problem(
        attributes=attributes,
        problem_statement=request.problem_statement,
        affected_population=request.affected_population,
        supporting_facts=request.fact_refs,
        severity=request.severity,
        frequency=request.frequency,
        problem_domain=request.problem_domain,
        inference_basis=request.as_basis(),
        population_size_estimate=request.population_size_estimate,
        existing_workarounds=request.existing_workarounds,
        problem_persistence=request.problem_persistence,
        cost_indication=request.cost_indication,
    )

    # -- Persistence: the acceptance path only, never the registry, the
    # graph, or store internals. [N-8, T01.7.3] write_problem is atomic:
    # a rejected inference leaves no trace in the object map, the
    # lineage index, the graph, or the Problem registry. P-V1..P-V6 and
    # the universal rules are authoritative here -- including P-V6's
    # two restatement prongs and P-V1's re-check of the declared count.
    #
    # Versioned mode (T04.1.2) follows the extraction merge recipe
    # exactly: the authoritative PROBLEM_RULES dry-run has already closed
    # the type-rule failure surface BEFORE any state change; the
    # predecessor is transitioned ACTIVE -> SUPERSEDED (I5 permits only
    # one ACTIVE version, and R-2 makes SUPERSEDED terminal, so the
    # transition must precede the write); the successor is then persisted
    # with its predecessor. A transition failure leaves the predecessor
    # unchanged (nothing was mutated). Should the write still fail -- the
    # universal-rule residual argued closed by construction -- the
    # refusal names the exact surviving state: predecessor SUPERSEDED
    # with every attribute and payload intact, no successor, the store's
    # acceptance failure retained. Data intact, auditable, nothing
    # silent. [R-2, N-10, extraction merge precedent]
    if predecessor_id is None:
        try:
            stored = store.write_problem(problem)
        except WriteRejectedError as rejection:
            failure = _failure(
                request, InferenceStage.STORE_REJECTED,
                "ACCEPTANCE_REFUSED",
                f"the acceptance path refused the inference: "
                f"{', '.join(rejection.failure.rule_ids)} -- "
                f"{rejection.failure.object_id} [P-V1..P-V6 authoritative]",
                log, now,
            )
            raise _refuse(failure) from rejection
    else:
        _dry_run_problem_rules(request, problem, store, log, now)
        try:
            store.transition(
                predecessor_id, ObjectStatus.SUPERSEDED,
                "reformulated: successor inferred [T04.1.2, R-1/V11]",
            )
        except Exception as exc:
            # The store mutated nothing on a failed transition; the
            # predecessor is unchanged. [N-10]
            failure = _failure(
                request, InferenceStage.STORE_REJECTED,
                "PREDECESSOR_TRANSITION_FAILED",
                f"the predecessor {predecessor_id!r} could not be "
                f"superseded; no state has changed (the predecessor is "
                f"unchanged): {type(exc).__name__}: {exc} [T04.1.2, N-10]",
                log, now,
            )
            raise _refuse(failure) from exc
        try:
            stored = store.write_problem(
                problem, predecessor_id=predecessor_id
            )
        except StoreError as rejection:  # WriteRejectedError included
            # SUPERSEDED is terminal under R-2: restoration is
            # structurally impossible, exactly as the extraction merge
            # precedent argues. The refusal names the surviving state.
            rule_ids = (
                ", ".join(rejection.failure.rule_ids)
                if isinstance(rejection, WriteRejectedError)
                else type(rejection).__name__
            )
            failure = _failure(
                request, InferenceStage.STORE_REJECTED,
                "WRITE_FAILED_AFTER_TRANSITION",
                f"the successor write failed after the predecessor was "
                f"superseded: {rule_ids}. The predecessor "
                f"{predecessor_id!r} is SUPERSEDED (terminal under R-2) "
                f"and holds every attribute and payload it had; no "
                f"successor exists; the store retains its failure record "
                f"-- data intact, fully auditable, nothing silent "
                f"[R-2, N-10, T04.1.2]",
                log, now,
            )
            raise _refuse(failure) from rejection

    persisted = store.get_problem(stored.object_id)
    if persisted is None:
        # Unreachable by the store's atomicity: the payload registers in
        # the same critical section as the commit. Guarded anyway so the
        # engine can never return an outcome it cannot stand behind.
        failure = _failure(
            request, InferenceStage.STORE_REJECTED, "PAYLOAD_MISSING",
            f"the store accepted {stored.object_id!r} but no Problem "
            f"payload is registered; refusing rather than asserting an "
            f"unverifiable outcome",
            log, now,
        )
        raise _refuse(failure)

    return InferenceOutcome(
        problem=persisted,
        supporting_fact_refs=request.fact_refs,
        evidence_refs=tuple(evidence_refs),
        independence_keys=frozenset(independence_keys),
        independent_source_count=independent_source_count,
        source_type_count=len(source_types),
        evidential_support=evidential_support,
        assertion_confidence=float(request.inference_confidence),
        predecessor_id=predecessor_id,
    )
