"""Knowledge Store: immutable object persistence with atomic write.

Task: T01.1.4

Architecture References:
- N-6    Objects authoritative; object write is atomic; graph derived
- N-8    Store enforces acceptance; rules specified in the object model
- N-10   Failed write produces a failure record
- R-1    Objects immutable; change produces a new version
- R-2    Status transition is the sole non-versioning mutation
- I1     Content immutable after acceptance
- I2     object_id never reused
- I4     Referenced objects never hard-deleted
- I5     Exactly one ACTIVE version per lineage_id
- V1-V12 Enforced via the acceptance path

The Store is the authority for objects. It performs no interpretation: it
runs the rule set it is handed and persists what passes. Content is immutable
after acceptance; the only permitted post-write mutation is a status
transition, which produces a new instance rather than editing in place.

Atomicity: an object and its lineage are committed together or not at all.
A partial write would leave an object without lineage -- a direct Principle 3
violation and the most likely source of silent integrity loss.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Iterator

from oip.acceptance import (
    UNIVERSAL_RULES,
    AcceptanceContext,
    AcceptancePath,
    AcceptanceResult,
    FailureRecord,
)
from oip.evidence import (
    EVIDENCE_RULES,
    Evidence,
    EvidenceRegistry,
)
from oip.fact import FACT_RULES, Fact, FactRegistry
from oip.opportunity import (
    OPPORTUNITY_RULES,
    Opportunity,
    OpportunityRegistry,
)
from oip.pattern import PATTERN_RULES, Pattern, PatternRegistry
from oip.solution import SOLUTION_RULES, Solution, SolutionRegistry
from oip.feedback import (
    FEEDBACK_RULES,
    FeedbackRecord,
    FeedbackRegistry,
)
from oip.execution import (
    EXECUTION_RULES,
    ExecutionRecord,
    ExecutionRegistry,
)
from oip.validation import (
    VALIDATION_RULES,
    Validation,
    ValidationRegistry,
)
from oip.problem import PROBLEM_RULES, Problem, ProblemRegistry
from oip.integrity import IntegrityReport, IntegrityVerifier, i8_inputs_are_consumable
from oip.contract import UniversalAttributes
from oip.enums import ObjectStatus, ObjectType
from oip.graph import KnowledgeGraph
from oip.identity import IdentityAllocator
from oip.lineage import Lineage


class StoreError(Exception):
    """Base class for store violations."""


class ObjectNotFoundError(StoreError):
    """Requested object is not held by the store."""


class DuplicateWriteError(StoreError):
    """An object_id already persisted. [I2]"""


class ImmutabilityError(StoreError):
    """An attempt to alter persisted content. [I1, R-1]"""


class HardDeleteError(StoreError):
    """Hard delete is unsupported. [I4]"""


class ReachabilityError(StoreError):
    """An object supporting ACTIVE knowledge may not be archived. [N-12]

    N-12: "An object is tiered only when it is not reachable from any ACTIVE
    object by lineage traversal. Anything supporting current knowledge stays."
    """


class ActiveVersionConflictError(StoreError):
    """More than one ACTIVE version per lineage_id. [I5]"""


class CycleWriteError(StoreError):
    """A write would introduce a lineage cycle. [V10]"""


class WriteRejectedError(StoreError):
    """Acceptance rejected the write. [N-8]"""

    def __init__(self, failure: FailureRecord) -> None:
        super().__init__(
            f"write rejected for {failure.object_id!r}: "
            f"{', '.join(failure.rule_ids)}"
        )
        self.failure = failure


@dataclass(frozen=True)
class StoredObject:
    """An object as held by the store: attributes plus its lineage."""

    attributes: UniversalAttributes
    lineage: Lineage

    @property
    def object_id(self) -> str:
        return self.attributes.object_id

    @property
    def lineage_id(self) -> str:
        return self.attributes.lineage_id

    @property
    def object_type(self) -> ObjectType:
        return self.attributes.object_type

    @property
    def status(self) -> ObjectStatus:
        return self.attributes.status


@dataclass
class KnowledgeStore:
    """Authoritative persistence for Intelligence Objects. [N-6]

    Thread-safe. Writes are serialised so that atomicity and the single-ACTIVE
    invariant hold under the concurrency N-11 permits upstream.
    """

    acceptance: AcceptancePath = field(
        default_factory=lambda: AcceptancePath(
            rules=UNIVERSAL_RULES
            + (i8_inputs_are_consumable,)
            + EVIDENCE_RULES
            + FACT_RULES
            + PROBLEM_RULES
            + PATTERN_RULES
            + OPPORTUNITY_RULES
            + SOLUTION_RULES
            + VALIDATION_RULES
            + EXECUTION_RULES
            + FEEDBACK_RULES
        )
    )
    graph: KnowledgeGraph = field(default_factory=KnowledgeGraph)
    allocator: IdentityAllocator = field(default_factory=IdentityAllocator)

    _objects: dict[str, StoredObject] = field(default_factory=dict, init=False)
    _by_lineage: dict[str, list[str]] = field(default_factory=dict, init=False)
    _active: dict[str, str] = field(default_factory=dict, init=False)
    _failures: list[FailureRecord] = field(default_factory=list, init=False)
    _evidence: "EvidenceRegistry | None" = field(default=None, init=False)
    _facts: "FactRegistry | None" = field(default=None, init=False)
    _problems: "ProblemRegistry | None" = field(default=None, init=False)
    _patterns: "PatternRegistry | None" = field(default=None, init=False)
    _opportunities: "OpportunityRegistry | None" = field(default=None, init=False)
    _solutions: "SolutionRegistry | None" = field(default=None, init=False)
    _validations: "ValidationRegistry | None" = field(default=None, init=False)
    _executions: "ExecutionRegistry | None" = field(default=None, init=False)
    _feedback: "FeedbackRegistry | None" = field(default=None, init=False)
    anchor_verifier: object | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    # -- write path -------------------------------------------------------

    def write(
        self,
        attributes: UniversalAttributes,
        lineage: Lineage,
        predecessor_id: str | None = None,
    ) -> StoredObject:
        """Persist an object atomically after acceptance. [N-6, N-8, I1]

        Either the object, its lineage and its graph edges all commit, or
        nothing does and a failure record is produced.
        """
        with self._lock:
            self._precheck(attributes, lineage)

            result = self._evaluate(attributes, lineage, predecessor_id)
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            accepted = result.attributes
            return self._commit(accepted, lineage)

    def try_write(
        self,
        attributes: UniversalAttributes,
        lineage: Lineage,
        predecessor_id: str | None = None,
    ) -> AcceptanceResult:
        """Attempt a write, returning the result rather than raising. [N-10]"""
        with self._lock:
            try:
                self._precheck(attributes, lineage)
            except StoreError:
                raise
            result = self._evaluate(attributes, lineage, predecessor_id)
            if not result.accepted:
                self._failures.append(result.failure)
                return result
            self._commit(result.attributes, lineage)
            return result

    def _precheck(
        self, attributes: UniversalAttributes, lineage: Lineage
    ) -> None:
        if attributes.object_id in self._objects:
            raise DuplicateWriteError(
                f"object_id {attributes.object_id!r} already persisted [I2]"
            )
        if lineage.object_id != attributes.object_id:
            raise StoreError(
                f"lineage object_id {lineage.object_id!r} does not match "
                f"attributes {attributes.object_id!r}"
            )
        if lineage.object_type is not attributes.object_type:
            raise StoreError("lineage object_type does not match attributes")
        if tuple(lineage.reference_ids) != tuple(
            r.object_id for r in attributes.derives_from
        ):
            raise StoreError(
                "lineage references disagree with attributes.derives_from"
            )

    def _evaluate(
        self,
        attributes: UniversalAttributes,
        lineage: Lineage,
        predecessor_id: str | None,
        evidence: "Evidence | None" = None,
        fact: "Fact | None" = None,
        problem: "Problem | None" = None,
        pattern: "Pattern | None" = None,
        opportunity: "Opportunity | None" = None,
        solution: "Solution | None" = None,
        validation: "Validation | None" = None,
        execution_record: "ExecutionRecord | None" = None,
        feedback_record: "FeedbackRecord | None" = None,
    ) -> AcceptanceResult:
        predecessor = None
        if predecessor_id is not None:
            stored = self._objects.get(predecessor_id)
            if stored is None:
                raise ObjectNotFoundError(
                    f"predecessor {predecessor_id!r} not found"
                )
            predecessor = stored.attributes

        probe = KnowledgeGraph.rebuild(
            [s.lineage for s in self._objects.values()] + [lineage]
        )

        ctx = AcceptanceContext(
            attributes=attributes,
            lineage=lineage,
            resolve_type=self.resolve_type,
            reaches_evidence=probe.reaches_evidence,
            would_cycle=self.graph.would_introduce_cycle,
            active_version_of_lineage=self.active_version_of,
            predecessor=predecessor,
            upstream_confidence=self._upstream_confidence,
            upstream_status=self._upstream_status,
            evidence=evidence,
            find_duplicate_evidence=self.evidence.find_duplicate,
            fact=fact,
            anchor_verifier=self.anchor_verifier,
            problem=problem,
            fact_claim_text=self._fact_claim_text,
            pattern=pattern,
            resolve_lineage=self.resolve_lineage,
            upstream_source_count=self._upstream_source_count,
            opportunity=opportunity,
            # Read from the PROBE graph, which includes the pending lineage.
            # The committed graph does not yet contain this object, so a
            # provider bound to it would skip O-V6 on every write -- the only
            # point at which the rule can act. [O-V6, N-6]
            lineage_facts=lambda object_id: self._lineage_facts(
                object_id, graph=probe
            ),
            solution=solution,
            # Probe graph again: the object being written is not yet
            # committed, so a provider bound to the committed index would
            # skip S-V4 on every write. [S-V4, N-6]
            lineage_problems=lambda object_id: self._lineage_of_type(
                object_id, ObjectType.PROBLEM, graph=probe
            ),
            opportunity_statement_text=self._opportunity_statement_text,
            validation=validation,
            claims_of_object=self._claims_of_object,
            execution_record=execution_record,
            stored_prediction=self._stored_prediction,
            # Probe graph: the object being written is not yet committed, so
            # a provider bound to the committed index would skip X-V4 on
            # every write. [X-V4, N-6]
            lineage_opportunities=lambda object_id: self._lineage_of_type(
                object_id, ObjectType.OPPORTUNITY, graph=probe
            ),
            feedback_record=feedback_record,
        )
        return self.acceptance.accept(ctx)

    def _commit(
        self, attributes: UniversalAttributes, lineage: Lineage
    ) -> StoredObject:
        """Atomic commit: object, indices and graph edges together. [N-6]

        Every condition that can fail is checked BEFORE any mutation, so a
        rejected commit leaves no partial state anywhere -- not in the object
        map, not in the lineage index, and not in the graph. An earlier
        version indexed the graph first and left an orphan edge behind on
        rollback; that was a partial write and is now structurally impossible.
        """
        stored = StoredObject(attributes=attributes, lineage=lineage)

        # -- pre-mutation checks ------------------------------------------
        if stored.status is ObjectStatus.ACTIVE:
            existing = self._active.get(stored.lineage_id)
            if existing is not None and existing != stored.object_id:
                raise ActiveVersionConflictError(
                    f"lineage {stored.lineage_id!r} already has ACTIVE version "
                    f"{existing!r} [I5]"
                )
        # Cycle detection is the other failure mode; probe without mutating.
        for ref in lineage.references:
            if self.graph.would_introduce_cycle(lineage.object_id, ref.object_id):
                raise CycleWriteError(
                    f"edge {lineage.object_id!r} -> {ref.object_id!r} would "
                    f"introduce a lineage cycle [V10]"
                )

        # -- mutation: nothing below may fail -----------------------------
        self.graph.index_lineage(lineage)
        self._objects[stored.object_id] = stored
        self._by_lineage.setdefault(stored.lineage_id, []).append(stored.object_id)
        if stored.status is ObjectStatus.ACTIVE:
            self._active[stored.lineage_id] = stored.object_id
        self.allocator.adopt([attributes.identity])
        return stored

    # -- Evidence [T01.7.1] -----------------------------------------------

    @property
    def evidence(self) -> EvidenceRegistry:
        """Registry of Evidence payloads. [E-V6]"""
        if self._evidence is None:
            self._evidence = EvidenceRegistry(store=self)
        return self._evidence

    def write_evidence(
        self, evidence: Evidence, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist an Evidence object, running E-V1..E-V6. [T01.7.1]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected acquisition leaves no trace in
        the duplicate index.
        """
        with self._lock:
            attributes = evidence.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.EVIDENCE,
                references=(),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, evidence=evidence
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            accepted = Evidence(
                attributes=result.attributes,
                provenance=evidence.provenance,
                content=evidence.content,
            )
            self.evidence.register(accepted)
            return stored

    def get_evidence(self, object_id: str) -> Evidence | None:
        with self._lock:
            return self.evidence.get(object_id)

    # -- Facts [T01.7.2] ---------------------------------------------------

    @property
    def facts(self) -> FactRegistry:
        """Registry of Fact payloads. [R-5, S-3]"""
        if self._facts is None:
            self._facts = FactRegistry(store=self)
        return self._facts

    def write_fact(
        self, fact: Fact, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist a Fact, running F-V1..F-V6. [T01.7.2]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected extraction leaves no trace.
        """
        with self._lock:
            attributes = fact.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.FACT,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, fact=fact
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.facts.register(
                Fact(
                    attributes=result.attributes,
                    claim=fact.claim,
                    claim_type=fact.claim_type,
                    attachments=fact.attachments,
                    qualifying_context=fact.qualifying_context,
                    attributed_to=fact.attributed_to,
                    temporal_scope=fact.temporal_scope,
                    population_scope=fact.population_scope,
                    merge_history=fact.merge_history,
                )
            )
            return stored

    def get_fact(self, object_id: str) -> Fact | None:
        with self._lock:
            return self.facts.get(object_id)

    def _fact_claim_text(self, object_id: str) -> str | None:
        """Canonical claim text of a stored Fact, for P-V6. [S-3]"""
        fact = self.facts.get(object_id)
        return fact.claim.as_text() if fact is not None else None

    # -- Problems [T01.7.3] ------------------------------------------------

    @property
    def problems(self) -> ProblemRegistry:
        """Registry of Problem payloads. [IOM section 3.3]"""
        if self._problems is None:
            self._problems = ProblemRegistry(store=self)
        return self._problems

    def write_problem(
        self, problem: Problem, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist a Problem, running P-V1..P-V6. [T01.7.3]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected inference leaves no trace.
        """
        with self._lock:
            attributes = problem.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.PROBLEM,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, problem=problem
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.problems.register(
                Problem(
                    attributes=result.attributes,
                    problem_statement=problem.problem_statement,
                    affected_population=problem.affected_population,
                    supporting_facts=problem.supporting_facts,
                    severity=problem.severity,
                    frequency=problem.frequency,
                    problem_domain=problem.problem_domain,
                    inference_basis=problem.inference_basis,
                    population_size_estimate=problem.population_size_estimate,
                    existing_workarounds=problem.existing_workarounds,
                    problem_persistence=problem.problem_persistence,
                    cost_indication=problem.cost_indication,
                )
            )
            return stored

    def get_problem(self, object_id: str) -> Problem | None:
        with self._lock:
            return self.problems.get(object_id)

    # -- Patterns [T01.7.4] ------------------------------------------------

    @property
    def patterns(self) -> PatternRegistry:
        """Registry of Pattern payloads. [IOM section 3.4]"""
        if self._patterns is None:
            self._patterns = PatternRegistry(store=self)
        return self._patterns

    def write_pattern(
        self, pattern: Pattern, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist a Pattern, running PT-V1..PT-V6. [T01.7.4]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected recognition leaves no trace.
        """
        with self._lock:
            attributes = pattern.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.PATTERN,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, pattern=pattern
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.patterns.register(
                Pattern(
                    attributes=result.attributes,
                    pattern_statement=pattern.pattern_statement,
                    constituent_problems=pattern.constituent_problems,
                    pattern_type=pattern.pattern_type,
                    grouping_rationale=pattern.grouping_rationale,
                    source_diversity=pattern.source_diversity,
                    artefact_assessment=pattern.artefact_assessment,
                    pattern_scope=pattern.pattern_scope,
                    pattern_strength=pattern.pattern_strength,
                    temporal_trend=pattern.temporal_trend,
                    cross_domain_instances=pattern.cross_domain_instances,
                    expected_persistence=pattern.expected_persistence,
                )
            )
            return stored

    def get_pattern(self, object_id: str) -> Pattern | None:
        with self._lock:
            return self.patterns.get(object_id)

    # -- Opportunities [T01.7.5] -------------------------------------------

    @property
    def opportunities(self) -> OpportunityRegistry:
        """Registry of Opportunity payloads. [IOM section 3.5]"""
        if self._opportunities is None:
            self._opportunities = OpportunityRegistry(store=self)
        return self._opportunities

    def write_opportunity(
        self, opportunity: Opportunity, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist an Opportunity, running O-V1..O-V7. [T01.7.5]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected assessment leaves no trace.

        Note that O-V3 fails closed while M-14 is open, so an unscored
        Opportunity cannot be written as ACTIVE. That is the specified
        behaviour, not a defect. [M-14, IOM section 3.5]
        """
        with self._lock:
            attributes = opportunity.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.OPPORTUNITY,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, opportunity=opportunity
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.opportunities.register(
                Opportunity(
                    attributes=result.attributes,
                    opportunity_statement=opportunity.opportunity_statement,
                    originating_patterns=opportunity.originating_patterns,
                    value_hypothesis=opportunity.value_hypothesis,
                    beneficiary_population=opportunity.beneficiary_population,
                    score=opportunity.score,
                    score_basis=opportunity.score_basis,
                    scoring_explanation=opportunity.scoring_explanation,
                    market_sizing=opportunity.market_sizing,
                    timing_assessment=opportunity.timing_assessment,
                    competitive_context=opportunity.competitive_context,
                    capture_hypothesis=opportunity.capture_hypothesis,
                    rejection_rationale=opportunity.rejection_rationale,
                    quantitative_claims=opportunity.quantitative_claims,
                )
            )
            return stored

    def get_opportunity(self, object_id: str) -> Opportunity | None:
        with self._lock:
            return self.opportunities.get(object_id)

    # -- Solutions [T01.7.6] -----------------------------------------------

    @property
    def solutions(self) -> SolutionRegistry:
        """Registry of Solution payloads. [IOM section 3.6]"""
        if self._solutions is None:
            self._solutions = SolutionRegistry(store=self)
        return self._solutions

    def write_solution(
        self, solution: Solution, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist a Solution, running S-V1..S-V6. [T01.7.6]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected candidate leaves no trace.
        """
        with self._lock:
            attributes = solution.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.SOLUTION,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, solution=solution
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.solutions.register(
                Solution(
                    attributes=result.attributes,
                    solution_statement=solution.solution_statement,
                    addresses_opportunity=solution.addresses_opportunity,
                    assumptions=solution.assumptions,
                    problem_fit_rationale=solution.problem_fit_rationale,
                    feasibility_assessment=solution.feasibility_assessment,
                    candidate_group=solution.candidate_group,
                    constraints=solution.constraints,
                    differentiators=solution.differentiators,
                    dependencies=solution.dependencies,
                    risk_factors=solution.risk_factors,
                    precedents=solution.precedents,
                    superseded_assumptions=solution.superseded_assumptions,
                )
            )
            return stored

    def get_solution(self, object_id: str) -> Solution | None:
        with self._lock:
            return self.solutions.get(object_id)

    # -- Validations [T01.7.7] ---------------------------------------------

    @property
    def validations(self) -> ValidationRegistry:
        """Registry of Validation payloads. [IOM section 3.7]"""
        if self._validations is None:
            self._validations = ValidationRegistry(store=self)
        return self._validations

    def write_validation(
        self, validation: Validation, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist a Validation, running V-V1..V-V6. [T01.7.7]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected record leaves no trace.

        A NEGATIVE RESULT IS ACTIVE. REJECTED denotes an unusable record, not
        an unfavourable finding, and V-I1 refuses the conflation at
        construction as well as continuously. [V-I1, R-2]
        """
        with self._lock:
            attributes = validation.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.VALIDATION,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, validation=validation
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.validations.register(
                Validation(
                    attributes=result.attributes,
                    tests_claim=validation.tests_claim,
                    validation_method=validation.validation_method,
                    method_detail=validation.method_detail,
                    result=validation.result,
                    result_detail=validation.result_detail,
                    result_interpretation=validation.result_interpretation,
                    validated_at=validation.validated_at,
                    scope_limitations=validation.scope_limitations,
                    experiment_ref=validation.experiment_ref,
                    confidence_impact=validation.confidence_impact,
                    contradicting_evidence=validation.contradicting_evidence,
                    follow_up_required=validation.follow_up_required,
                    correction_rationale=validation.correction_rationale,
                )
            )
            return stored

    def get_validation(self, object_id: str) -> Validation | None:
        with self._lock:
            return self.validations.get(object_id)

    # -- Execution Records [T01.7.8] ---------------------------------------

    @property
    def executions(self) -> ExecutionRegistry:
        """Registry of Execution Record payloads. [IOM section 3.8]"""
        if self._executions is None:
            self._executions = ExecutionRegistry(store=self)
        return self._executions

    def write_execution_record(
        self, record: ExecutionRecord, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist an Execution Record, running X-V1..X-V6. [T01.7.8]

        FAILS CLOSED WHILE C-02 IS OPEN. No engine holds create authority for
        this type, so V7 refuses every write with "[C-02 open]" and this
        method always raises WriteRejectedError. That is the specified
        behaviour, not a defect: the IOM states the Execution Record "cannot
        be created by any component defined in v1", and assigning authority
        here would resolve C-02 by implementation rather than by the
        escalation scheduled at T08.1.1.

        The path is written in full so that closing C-02 requires only adding
        the CREATE_AUTHORITY entry -- no restructuring of the write path.
        """
        with self._lock:
            attributes = record.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.EXECUTION_RECORD,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, execution_record=record
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.executions.register(
                ExecutionRecord(
                    attributes=result.attributes,
                    outcome_of_solution=record.outcome_of_solution,
                    execution_description=record.execution_description,
                    executed_at=record.executed_at,
                    outcome_observed_at=record.outcome_observed_at,
                    outcome=record.outcome,
                    outcome_valence=record.outcome_valence,
                    attribution_assessment=record.attribution_assessment,
                    prediction_comparison=record.prediction_comparison,
                    outcome_verification=record.outcome_verification,
                    execution_deviations=record.execution_deviations,
                    external_factors=record.external_factors,
                    partial_outcomes=record.partial_outcomes,
                    outcome_magnitude=record.outcome_magnitude,
                )
            )
            return stored

    def get_execution_record(self, object_id: str) -> ExecutionRecord | None:
        with self._lock:
            return self.executions.get(object_id)

    # -- Feedback Records [T01.7.9] ----------------------------------------

    @property
    def feedback(self) -> FeedbackRegistry:
        """Registry of Feedback Record payloads. [R-7, IOM section 3.9]"""
        if self._feedback is None:
            self._feedback = FeedbackRegistry(store=self)
        return self._feedback

    def write_feedback_record(
        self, record: FeedbackRecord, predecessor_id: str | None = None
    ) -> StoredObject:
        """Persist a Feedback Record, running FR-V1..FR-V6. [T01.7.9]

        Atomic with the universal write path: the payload is registered only
        after acceptance passes, so a rejected lesson leaves no trace.

        Note the inherited blocker: FR-V1 requires resolvable Execution
        Records, which C-02 leaves uncreatable through any sanctioned path.
        A Feedback Record is therefore unwritable end-to-end today for a
        reason belonging to the stage below it, not to this type.
        """
        with self._lock:
            attributes = record.attributes
            lineage = Lineage(
                object_id=attributes.object_id,
                object_type=ObjectType.FEEDBACK_RECORD,
                references=tuple(attributes.derives_from),
            )
            self._precheck(attributes, lineage)

            result = self._evaluate(
                attributes, lineage, predecessor_id, feedback_record=record
            )
            if not result.accepted:
                self._failures.append(result.failure)
                raise WriteRejectedError(result.failure)

            stored = self._commit(result.attributes, lineage)
            self.feedback.register(
                FeedbackRecord(
                    attributes=result.attributes,
                    motivating_records=record.motivating_records,
                    lesson_statement=record.lesson_statement,
                    change_target=record.change_target,
                    change_description=record.change_description,
                    reversal_procedure=record.reversal_procedure,
                    informs=record.informs,
                    applied_at=record.applied_at,
                    evidence_of_pattern=record.evidence_of_pattern,
                    magnitude=record.magnitude,
                    expected_effect=record.expected_effect,
                    observed_effect=record.observed_effect,
                    superseded_lesson=record.superseded_lesson,
                    approval_record=record.approval_record,
                )
            )
            return stored

    def get_feedback_record(self, object_id: str) -> FeedbackRecord | None:
        with self._lock:
            return self.feedback.get(object_id)

    # -- status transition [R-2] -----------------------------------------

    def transition(
        self, object_id: str, status: ObjectStatus, reason: str | None = None
    ) -> StoredObject:
        """Transition status. The sole permitted post-write mutation. [R-2, I1]

        ARCHIVED is additionally guarded by reachability [N-12, T01.2.5]: an
        object reachable from ACTIVE knowledge may not be archived, because
        "anything supporting current knowledge stays". The check lives here,
        at the sole mutation point, so no path can archive around it.
        """
        with self._lock:
            stored = self._require(object_id)
            if status is ObjectStatus.ARCHIVED:
                self._require_unreachable_for_archival(object_id)
            updated = stored.attributes.with_status(status, reason)

            if status is ObjectStatus.ACTIVE:
                existing = self._active.get(stored.lineage_id)
                if existing is not None and existing != object_id:
                    raise ActiveVersionConflictError(
                        f"lineage {stored.lineage_id!r} already has ACTIVE "
                        f"version {existing!r} [I5]"
                    )
                self._active[stored.lineage_id] = object_id
            elif self._active.get(stored.lineage_id) == object_id:
                del self._active[stored.lineage_id]

            replacement = StoredObject(attributes=updated, lineage=stored.lineage)
            self._objects[object_id] = replacement
            return replacement

    # -- reads ------------------------------------------------------------

    def get(self, object_id: str) -> StoredObject:
        with self._lock:
            return self._require(object_id)

    def find(self, object_id: str) -> StoredObject | None:
        with self._lock:
            return self._objects.get(object_id)

    def contains(self, object_id: str) -> bool:
        with self._lock:
            return object_id in self._objects

    def resolve_type(self, object_id: str) -> ObjectType | None:
        with self._lock:
            stored = self._objects.get(object_id)
            return stored.object_type if stored else None

    def resolve_lineage(self, object_id: str) -> str | None:
        """lineage_id of a stored object. Two versions share one. [PT-V2]"""
        with self._lock:
            stored = self._objects.get(object_id)
            return stored.lineage_id if stored else None

    def versions_of(self, lineage_id: str) -> tuple[StoredObject, ...]:
        with self._lock:
            return tuple(
                self._objects[oid] for oid in self._by_lineage.get(lineage_id, ())
            )

    def active_version_of(self, lineage_id: str) -> str | None:
        with self._lock:
            return self._active.get(lineage_id)

    def active_objects(self) -> tuple[StoredObject, ...]:
        with self._lock:
            return tuple(
                s for s in self._objects.values()
                if s.status is ObjectStatus.ACTIVE
            )

    def objects_of_type(self, object_type: ObjectType) -> tuple[StoredObject, ...]:
        with self._lock:
            return tuple(
                s for s in self._objects.values() if s.object_type is object_type
            )

    def all_lineages(self) -> tuple[Lineage, ...]:
        with self._lock:
            return tuple(s.lineage for s in self._objects.values())

    def __len__(self) -> int:
        with self._lock:
            return len(self._objects)

    def __iter__(self) -> Iterator[StoredObject]:
        with self._lock:
            return iter(tuple(self._objects.values()))

    # -- prohibited operations [I4] ---------------------------------------

    def delete(self, object_id: str) -> None:
        """Never supported. Objects are archived, never removed. [I4, N-12]"""
        raise HardDeleteError(
            f"hard delete is unsupported; transition {object_id!r} to ARCHIVED "
            f"instead [I4, N-12]"
        )

    def update(self, object_id: str, **changes) -> None:
        """Never supported. Content changes require a new version. [I1, R-1]"""
        raise ImmutabilityError(
            f"content of {object_id!r} is immutable; create a new version "
            f"instead [I1, R-1]"
        )

    # -- graph consistency [N-6] ------------------------------------------

    def rebuild_graph(self) -> KnowledgeGraph:
        """Reconstruct the index from objects alone. [N-6]

        The guarantee that divergence is a performance problem, never a
        correctness one.
        """
        with self._lock:
            self.graph = KnowledgeGraph.rebuild(self.all_lineages())
            return self.graph

    def graph_diverges(self) -> tuple[str, ...]:
        with self._lock:
            return self.graph.diverges_from(self.all_lineages())

    # -- failures [N-10] ---------------------------------------------------

    @property
    def failure_records(self) -> tuple[FailureRecord, ...]:
        with self._lock:
            return tuple(self._failures)

    # -- internals --------------------------------------------------------

    def _require_unreachable_for_archival(self, object_id: str) -> None:
        """Refuse to archive an object supporting current knowledge. [N-12]

        DEFECT FIX [T01.2.5]. transition() previously permitted archiving any
        object, including one an ACTIVE object derives from. That breaks
        N-12's rule directly -- "anything supporting current knowledge stays"
        -- and would leave live lineage pointing at archived content.

        Reachability is computed here from the STORE's ACTIVE set (objects are
        authoritative, and the graph may lag [N-6]) walked upstream through
        the graph index, because support flows upstream: an object an ACTIVE
        object derives from is what N-12 protects.

        The object's own ACTIVE status does not protect it -- every archival
        starts from ACTIVE, since IOM 2.1 defines no other source state.
        """
        for active_id in tuple(self._active.values()):
            if active_id == object_id:
                continue
            if not self.graph.contains(active_id):
                continue
            if object_id in self.graph.ancestors(active_id):
                raise ReachabilityError(
                    f"{object_id!r} is reachable from ACTIVE object "
                    f"{active_id!r} and may not be archived; anything "
                    f"supporting current knowledge stays [N-12]"
                )

    def _require(self, object_id: str) -> StoredObject:
        stored = self._objects.get(object_id)
        if stored is None:
            raise ObjectNotFoundError(f"object {object_id!r} not found")
        return stored

    def _upstream_confidence(self, object_id: str) -> float | None:
        stored = self._objects.get(object_id)
        if stored is None:
            return None
        return stored.attributes.confidence.effective_confidence

    def _lineage_facts(
        self, object_id: str, graph: "KnowledgeGraph | None" = None
    ) -> "frozenset[str] | None":
        """Facts reachable upstream of an object. [O-V6, N-6]

        Read from a derived graph index, which is rebuildable from objects and
        never authoritative alone. Returns None when the index cannot answer,
        so an untraversable object yields no verdict rather than a false one.

        At acceptance the caller supplies the probe graph: the object being
        written is not yet committed, and reading the committed index would
        make O-V6 skip on every write.
        """
        return self._lineage_of_type(object_id, ObjectType.FACT, graph=graph)

    def _lineage_of_type(
        self,
        object_id: str,
        object_type: ObjectType,
        graph: "KnowledgeGraph | None" = None,
    ) -> "frozenset[str] | None":
        """Upstream objects of one type. [O-V6, S-V4, N-6, N-14]

        Lineage-restricted by construction: only ancestors of this object are
        returned, so an engine can never reach a sibling it did not derive
        from. Returns None when the index cannot answer.
        """
        index = graph if graph is not None else self.graph
        if not index.contains(object_id):
            return None
        return frozenset(
            ancestor
            for ancestor in index.ancestors(object_id)
            if index.type_of(ancestor) is object_type
        )

    def _stored_prediction(self, object_id: str) -> object | None:
        """An Opportunity's stored prediction, for X-V4. [D-01, O-I4]

        Point-in-time by construction: the payload holds the score as
        recorded, and O-I4 forbids retrospective alteration. This is the
        retrievability X-V4 depends on.
        """
        opportunity = self.opportunities.get(object_id)
        if opportunity is None:
            return None
        return opportunity.score_fingerprint()

    def _claims_of_object(self, object_id: str) -> "frozenset[str] | None":
        """Addressable claims an object exposes, for V-V1. [V-V1]

        Only the Solution stage defines a claim vocabulary today: its
        assumption ids. Other types expose no claim set, so None is returned
        and V-V1 reports that it could not verify rather than guessing.
        M-32 does not supply a cross-type claim vocabulary.
        """
        solution = self.solutions.get(object_id)
        if solution is None:
            return None
        return solution.assumption_ids

    def _opportunity_statement_text(self, object_id: str) -> str | None:
        """Statement of a stored Opportunity, for S-V5."""
        payload = self.opportunities.get(object_id)
        return payload.opportunity_statement if payload is not None else None

    def _upstream_source_count(self, object_id: str) -> int | None:
        """Tier 1 independent source count of an upstream object. [N-16]"""
        stored = self._objects.get(object_id)
        if stored is None:
            return None
        return stored.attributes.independent_source_count

    def _upstream_status(self, object_id: str) -> ObjectStatus | None:
        """Lifecycle status of an upstream object, for the I8 check. [I8]"""
        stored = self._objects.get(object_id)
        return stored.status if stored else None

    # -- continuous integrity [I1-I8] -------------------------------------

    def verify_integrity(self) -> IntegrityReport:
        """Audit the store against I1-I8. [IOM section 1.4]

        Integrity constraints hold continuously, so they are re-checkable at
        any moment rather than only at acceptance.
        """
        with self._lock:
            return IntegrityVerifier(store=self).verify()

    def assert_integrity(self) -> None:
        """Raise if any integrity constraint is currently breached."""
        with self._lock:
            IntegrityVerifier(store=self).assert_holds()
