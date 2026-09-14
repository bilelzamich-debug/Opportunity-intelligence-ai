"""Contract tests for the Problem Intelligence engine.

Task: T04.1.1 (standalone inference), T04.1.2 (solution-independence
enforcement across versions), T04.1.3 (affected-population
identification: P-I3 enforcement at the versioned-write boundary)

Architecture References:
- S-4         Problem sufficiency: 2 independent sources across supporting
             Facts; exactly 2 qualifies, 1 and 0 do not; refused, never
             accepted with low confidence
- N-4         The request carries everything; the engine invents no value;
             regression tests assert properties, not output equality
- N-10        Refusals recorded, staged, distinguishable; not-attempted
             vs attempted never collapse
- N-14        Facts are the direct input; Evidence beneath them readable
- N-16        Tier 1 count derived from distinct independence keys
- R-1/V11     Versioned mode: successor via allocator.succeed, version
             increments, lineage_id constant
- R-2         SUPERSEDED is terminal; the versioned write follows the
             extraction merge precedent (dry-run, then transition, then
             write; refusal names the surviving state)
- R-3         Confidence bounded by the supporting Facts (V5)
- R-6         SUPPORTS = the supporting subset of DERIVES_FROM
- V7          Only Problem Intelligence creates Problems
- P-V1..P-V6  Authoritative at acceptance, exercised end to end through
             store.write_problem -- never duplicated in these tests
- P-I1        Solution-independence across ALL versions of the chain;
             a clean successor never masks a violating earlier version
- P-V3/P-I3   Affected-population identification. [T04.1.3] P-V3
             (non-empty, non-generic) stays authoritative at request
             construction and acceptance; P-I3 (population never widened
             without additional supporting Facts) is enforced at the
             versioned-write boundary with the authoritative
             widens_population_of / adds_support_over -- no second
             widening definition, undecidable rewordings never guessed

Acceptance criteria under test:
  AC1  sufficiency threshold enforced (S-4 floor, independence-grouped)
  AC2  single-fact restatement rejected (P-V6, both prongs, via acceptance)
  AC3  inference_basis references specific Facts (exact coverage)
  T04.1.2  the versioned path: reformulation supersedes the predecessor,
       and solution-independence is enforced over every existing version
       of the chain before any state changes
  T04.1.3  population identification: the population is carried exactly
       (N-4), and a versioned inference may widen it only with
       additional supporting Facts (P-I3), across the whole lineage and
       the proposed successor, before any state changes

Explicitly NOT under test here (later tasks): severity/frequency bands
(T04.1.4), deduplication (T04.1.5), taxonomy (T04.1.6).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.contract import Engine, ObjectStatus, ObjectType
from oip.enums import RelationshipType
from oip.fact import Fact
from oip.inference import (
    InferenceError,
    InferenceFailure,
    InferenceLog,
    InferenceRefusedError,
    InferenceRequest,
    InferenceStage,
    infer,
)
from oip.problem import (
    FactContribution,
    InferenceBasis,
    Problem,
    ProblemError,
    WeightBand,
    WeightContribution,
    WeightCriterion,
    WeightError,
    WeightRating,
    band_rank,
    criterion_for,
)
from oip.store import KnowledgeStore, WriteRejectedError
from oip.support import sufficiency_threshold
from tests.conftest import T0, build_attrs
from tests.test_evidence import evidence as make_evidence
from tests.test_fact import make_fact

STATEMENT = (
    "Sellers managing large inventories lose update work without "
    "notification when batch operations exceed platform limits, and "
    "discover the loss only later through customer complaints."
)
POPULATION = (
    "Segment A sellers maintaining inventories above approximately 50 "
    "active listings."
)
SEVERITY_DETAIL = "unnoticed loss reaches customers"
FREQUENCY_DETAIL = "multiple reporting periods"
DOMAIN = "Marketplace inventory management"
SYNTHESIS = (
    "Together these Facts show an unmet need for reliable batch "
    "feedback, not merely an inconvenience."
)

# A clock strictly before every fixture timestamp (T0 = 2026-03-01).
BEFORE_T0 = datetime(2026, 2, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def contributions(*refs: str) -> tuple[FactContribution, ...]:
    return tuple(
        FactContribution(ref, f"{ref} establishes one component of the deficiency")
        for ref in refs
    )


def weight(
    band: WeightBand,
    refs,
    detail: str = "evidenced by the cited Facts",
) -> WeightRating:
    """A WeightRating citing every ref under the band's own criterion.

    The default test rating: the declared criterion is attested whenever
    S-4 itself passes (all supporting Facts, hence all available
    independence keys), so pre-T04.1.4 outcomes are preserved unless a
    test deliberately varies the rating.
    """
    criterion = criterion_for(band)
    return WeightRating(
        band,
        f"{band.value} -- {detail}",
        tuple(
            WeightContribution(ref, criterion, f"{ref} evidences {criterion.value}")
            for ref in dict.fromkeys(refs)
        ),
    )


def request_over(
    *refs: str,
    statement: str = STATEMENT,
    population: str = POPULATION,
    severity: WeightRating | None = None,
    frequency: WeightRating | None = None,
    domain: str = DOMAIN,
    synthesis: str = SYNTHESIS,
    confidence: float = 0.7,
    **overrides,
) -> InferenceRequest:
    """Build a request over refs. Weight defaults: SEVERE severity and
    RECURRING frequency, each citing EVERY ref under its own criterion,
    so the declared criterion is attested whenever S-4 passes and
    pre-T04.1.4 outcomes are preserved unless a test varies the rating.
    [F-W1, T04.1.4]"""
    if severity is None:
        # No refs: a placeholder that never gets inspected -- the request
        # refuses on fact_refs first (P-V1).
        severity = weight(WeightBand.SEVERE, refs, SEVERITY_DETAIL) if refs else ""
    if frequency is None:
        frequency = weight(WeightBand.RECURRING, refs, FREQUENCY_DETAIL) if refs else ""
    kwargs = dict(
        fact_refs=tuple(refs),
        problem_statement=statement,
        affected_population=population,
        severity=severity,
        frequency=frequency,
        problem_domain=domain,
        contributions=contributions(*refs),
        synthesis=synthesis,
        inference_confidence=confidence,
    )
    kwargs.update(overrides)
    return InferenceRequest(**kwargs)


def write_fact_from(
    store,
    allocator,
    *,
    source_identifier: str,
    independence_group: str | None = None,
    content: str = "source text",
) -> Fact:
    """One Evidence (own source identity) + one Fact attesting it.

    Returns the registered Fact payload, with claim and attachments."""
    overrides = {"source_identifier": source_identifier}
    if independence_group is not None:
        overrides["source_independence_group"] = independence_group
    ev = store.write_evidence(
        make_evidence(allocator, content=content, **overrides)
    )
    stored = store.write_fact(
        make_fact(
            allocator,
            (ev.object_id,),
            upstream_ceiling=ev.attributes.confidence.effective_confidence,
        )
    )
    return store.get_fact(stored.object_id)


def two_independent_facts(store, allocator):
    a = write_fact_from(store, allocator, source_identifier="src-alpha")
    b = write_fact_from(store, allocator, source_identifier="src-beta")
    return a, b


class RecordingFailureStore:
    """Duck-typed N-10 failure store: records every projection."""

    def __init__(self) -> None:
        self.records = []

    def record(self, failure) -> None:
        self.records.append(failure)


class StoreShell:
    """Duck-typed store shell delegating to a real store, with single
    collaborators overridden per test.

    The engine's defensive guards (a stored Fact with no payload, an
    attachment with no Evidence, an accepted write with no registered
    payload) are unreachable through the real store, whose writes are
    atomic -- they exist so a broken invariant refuses rather than
    silently miscounts. The shell exercises exactly those guards, the
    same pattern as the fake collaborators in test_acceptance and
    test_sequencing.
    """

    def __init__(self, store: KnowledgeStore) -> None:
        self._inner = store

    def __getattr__(self, name):
        return getattr(self._inner, name)


class _NoEvidenceRegistry:
    """Evidence registry that resolves nothing."""

    def get(self, object_id):
        return None


# ---------------------------------------------------------------------------
# AC1 -- sufficiency threshold enforced  [S-4]
# ---------------------------------------------------------------------------


class TestSufficiency:
    def test_exactly_two_independent_sources_qualifies(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert outcome.independent_source_count == 2
        assert outcome.independence_keys == frozenset({"src-alpha", "src-beta"})

    def test_two_facts_two_sources_accepted(self, store, allocator):
        """The AC1 happy path: two Facts, two independent sources."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert store.get_problem(outcome.object_id) is not None
        assert store.get_problem(outcome.object_id).status is ObjectStatus.ACTIVE

    def test_more_than_two_independent_sources_accepted(self, store, allocator):
        facts = tuple(
            write_fact_from(store, allocator, source_identifier=f"src-{i}")
            for i in range(4)
        )
        outcome = infer(request_over(*(f.object_id for f in facts)), store=store, log=InferenceLog())
        assert outcome.independent_source_count == 4

    def test_one_independent_source_refused(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="only-src")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.INSUFFICIENT_SOURCES
        assert failure.attempted is True
        assert "1 independent source" in failure.detail

    def test_zero_independent_sources_refused(self, store, allocator):
        """Non-ACTIVE Evidence contributes no key: the count falls, never inflates."""
        a, b = two_independent_facts(store, allocator)
        for fact in (a, b):
            ev_ref = fact.attachments[0].evidence_ref
            store.transition(ev_ref, ObjectStatus.SUPERSEDED, "re-acquired")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.INSUFFICIENT_SOURCES
        assert "0 independent source" in failure.detail

    def test_mixed_active_and_superseded_evidence_counts_active_only(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        store.transition(
            a.attachments[0].evidence_ref, ObjectStatus.SUPERSEDED, "re-acquired"
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        assert next(iter(log)).stage is InferenceStage.INSUFFICIENT_SOURCES

    def test_s4_floor_is_the_problem_threshold(self):
        assert sufficiency_threshold(ObjectType.PROBLEM) == 2

    def test_declared_count_equals_derived_keys(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        problem = store.get_problem(outcome.object_id)
        assert problem.attributes.independent_source_count == len(outcome.independence_keys)


# ---------------------------------------------------------------------------
# AC1 -- independence semantics  [N-16, T02.1.3]
# ---------------------------------------------------------------------------


class TestIndependence:
    def test_same_independence_group_counts_once(self, store, allocator):
        """S-4: syndicated or commonly-owned sources count once."""
        a = write_fact_from(
            store, allocator, source_identifier="wire-a",
            independence_group="wire-syndicate",
        )
        b = write_fact_from(
            store, allocator, source_identifier="wire-b",
            independence_group="wire-syndicate",
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        assert next(iter(log)).stage is InferenceStage.INSUFFICIENT_SOURCES

    def test_different_independence_groups_count_separately(self, store, allocator):
        a = write_fact_from(
            store, allocator, source_identifier="wire-a",
            independence_group="group-one",
        )
        b = write_fact_from(
            store, allocator, source_identifier="wire-b",
            independence_group="group-two",
        )
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert outcome.independent_source_count == 2
        assert outcome.independence_keys == frozenset({"group-one", "group-two"})

    def test_group_takes_precedence_over_identifier(self, store, allocator):
        """The T02.1.3 key is the group when carried, else the identifier."""
        a = write_fact_from(
            store, allocator, source_identifier="distinct-a",
            independence_group="shared-group",
        )
        b = write_fact_from(
            store, allocator, source_identifier="distinct-b",
            independence_group="shared-group",
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        assert next(iter(log)).stage is InferenceStage.INSUFFICIENT_SOURCES

    def test_same_evidence_beneath_two_facts_counts_once(self, store, allocator):
        """Multiple Facts sharing one source: corroboration is not repetition."""
        ev = store.write_evidence(
            make_evidence(allocator, content="shared", source_identifier="src-shared")
        )
        a = store.write_fact(
            make_fact(allocator, (ev.object_id,),
                      upstream_ceiling=ev.attributes.confidence.effective_confidence)
        )
        b = store.write_fact(
            make_fact(allocator, (ev.object_id,),
                      upstream_ceiling=ev.attributes.confidence.effective_confidence)
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.INSUFFICIENT_SOURCES
        assert "1 independent source" in failure.detail

    def test_merged_fact_with_independent_attachments_counts_both(self, store, allocator):
        """A Fact with two independent attachments carries two sources [N-16]."""
        ev1 = store.write_evidence(
            make_evidence(allocator, content="one", source_identifier="src-one")
        )
        ev2 = store.write_evidence(
            make_evidence(allocator, content="two", source_identifier="src-two")
        )
        merged = store.write_fact(
            make_fact(
                allocator, (ev1.object_id, ev2.object_id),
                upstream_ceiling=min(
                    ev1.attributes.confidence.effective_confidence,
                    ev2.attributes.confidence.effective_confidence,
                ),
            )
        )
        assert merged.attributes.independent_source_count == 2
        other = write_fact_from(store, allocator, source_identifier="src-three")
        outcome = infer(
            request_over(merged.object_id, other.object_id), store=store, log=InferenceLog()
        )
        assert outcome.independent_source_count == 3

    def test_no_double_counting_of_shared_attachment(self, store, allocator):
        """A shared attachment plus a distinct one: 2 keys, not 3."""
        shared = store.write_evidence(
            make_evidence(allocator, content="shared", source_identifier="src-shared")
        )
        other = store.write_evidence(
            make_evidence(allocator, content="other", source_identifier="src-other")
        )
        a = store.write_fact(
            make_fact(allocator, (shared.object_id, other.object_id),
                      upstream_ceiling=min(
                          shared.attributes.confidence.effective_confidence,
                          other.attributes.confidence.effective_confidence,
                      ))
        )
        b = store.write_fact(
            make_fact(allocator, (shared.object_id,),
                      upstream_ceiling=shared.attributes.confidence.effective_confidence)
        )
        third = write_fact_from(store, allocator, source_identifier="src-third")
        outcome = infer(
            request_over(a.object_id, b.object_id, third.object_id),
            store=store, log=InferenceLog(),
        )
        assert outcome.independence_keys == frozenset(
            {"src-shared", "src-other", "src-third"}
        )
        assert outcome.independent_source_count == 3

    def test_result_independent_of_fact_ordering(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        first = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        second = infer(request_over(b.object_id, a.object_id), store=store, log=InferenceLog())
        assert first.independence_keys == second.independence_keys
        assert first.independent_source_count == second.independent_source_count
        assert first.evidential_support == second.evidential_support


# ---------------------------------------------------------------------------
# AC2 -- single-fact restatement rejected  [P-V6, at acceptance]
# ---------------------------------------------------------------------------


class TestRestatement:
    def test_single_fact_with_one_source_refused_at_s4(self, store, allocator):
        """One Fact, one source: the S-4 floor refuses it first."""
        a = write_fact_from(store, allocator, source_identifier="src-solo")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        assert next(iter(log)).stage is InferenceStage.INSUFFICIENT_SOURCES

    def test_single_fact_with_two_independent_sources_rejected_by_pv6(self, store, allocator):
        """P-V6 prong 1: even a well-sourced single Fact cannot establish a
        Problem. The count clears the floor, so the refusal comes from the
        authoritative acceptance path -- STORE_REJECTED, not the engine."""
        ev1 = store.write_evidence(
            make_evidence(allocator, content="one", source_identifier="src-one")
        )
        ev2 = store.write_evidence(
            make_evidence(allocator, content="two", source_identifier="src-two")
        )
        solo = store.write_fact(
            make_fact(allocator, (ev1.object_id, ev2.object_id),
                      upstream_ceiling=min(
                          ev1.attributes.confidence.effective_confidence,
                          ev2.attributes.confidence.effective_confidence,
                      ))
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(solo.object_id), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert failure.attempted is True
        assert "P-V6" in failure.detail

    def test_verbatim_restatement_rejected_by_pv6(self, store, allocator):
        """P-V6 prong 2: a statement identical to a supporting claim is a
        restatement however many Facts are attached."""
        a, b = two_independent_facts(store, allocator)
        restatement = a.claim.as_text()
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id, statement=restatement),
                store=store, log=log,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert "P-V6" in failure.detail

    def test_case_and_punctuation_variant_is_still_a_restatement(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        restatement = a.claim.as_text().upper() + "!"
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id, statement=restatement),
                store=store, log=log,
            )
        assert next(iter(log)).stage is InferenceStage.STORE_REJECTED

    def test_interpretive_statement_is_not_a_restatement(self, store, allocator):
        """The negative control: a genuinely interpretive statement passes P-V6."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert outcome.problem.problem_statement == STATEMENT

    def test_solution_smuggling_rejected_by_pv2_at_acceptance(self, store, allocator):
        """P-V2 guards solution smuggling; the engine does not pre-empt it."""
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement="Sellers lack of a batch notification tool "
                              "causes lost update work.",
                ),
                store=store, log=log,
            )
        assert next(iter(log)).stage is InferenceStage.STORE_REJECTED


# ---------------------------------------------------------------------------
# AC3 -- inference_basis references specific Facts  [P-V5]
# ---------------------------------------------------------------------------


class TestInferenceBasisCoverage:
    def test_exact_supporting_set_accepted(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        basis = outcome.problem.inference_basis
        assert basis.referenced_facts == frozenset({a.object_id, b.object_id})

    def test_every_supporting_fact_represented(self, store, allocator):
        facts = tuple(
            write_fact_from(store, allocator, source_identifier=f"src-{i}")
            for i in range(3)
        )
        refs = tuple(f.object_id for f in facts)
        outcome = infer(request_over(*refs), store=store, log=InferenceLog())
        assert outcome.problem.inference_basis.referenced_facts == frozenset(refs)

    def test_basis_referencing_non_supporting_fact_rejected(self, store, allocator):
        """The request cannot even be constructed: a phantom citation is a
        request error, held at the boundary rather than persisted."""
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="non-supporting"):
            InferenceRequest(
                fact_refs=(a.object_id, b.object_id),
                problem_statement=STATEMENT,
                affected_population=POPULATION,
                severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id,), SEVERITY_DETAIL),
                frequency=weight(WeightBand.RECURRING, (a.object_id, b.object_id,), FREQUENCY_DETAIL),
                problem_domain=DOMAIN,
                contributions=(
                    FactContribution(a.object_id, "establishes one part"),
                    FactContribution("obj-does-not-exist", "phantom"),
                ),
                synthesis=SYNTHESIS,
                inference_confidence=0.7,
            )

    def test_unrepresented_supporting_fact_rejected(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="unrepresented"):
            InferenceRequest(
                fact_refs=(a.object_id, b.object_id),
                problem_statement=STATEMENT,
                affected_population=POPULATION,
                severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id,), SEVERITY_DETAIL),
                frequency=weight(WeightBand.RECURRING, (a.object_id, b.object_id,), FREQUENCY_DETAIL),
                problem_domain=DOMAIN,
                contributions=(FactContribution(a.object_id, "only one"),),
                synthesis=SYNTHESIS,
                inference_confidence=0.7,
            )

    def test_empty_basis_rejected(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-a")
        with pytest.raises(InferenceError, match="contributions are required"):
            InferenceRequest(
                fact_refs=(a.object_id,),
                problem_statement=STATEMENT,
                affected_population=POPULATION,
                severity=weight(WeightBand.SEVERE, (a.object_id,), SEVERITY_DETAIL),
                frequency=weight(WeightBand.RECURRING, (a.object_id,), FREQUENCY_DETAIL),
                problem_domain=DOMAIN,
                contributions=(),
                synthesis=SYNTHESIS,
                inference_confidence=0.7,
            )

    def test_duplicate_contribution_rejected(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="contributes twice"):
            InferenceRequest(
                fact_refs=(a.object_id, b.object_id),
                problem_statement=STATEMENT,
                affected_population=POPULATION,
                severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id,), SEVERITY_DETAIL),
                frequency=weight(WeightBand.RECURRING, (a.object_id, b.object_id,), FREQUENCY_DETAIL),
                problem_domain=DOMAIN,
                contributions=(
                    FactContribution(a.object_id, "once"),
                    FactContribution(a.object_id, "twice"),
                    FactContribution(b.object_id, "once"),
                ),
                synthesis=SYNTHESIS,
                inference_confidence=0.7,
            )

    def test_basis_travels_to_the_persisted_problem(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        problem = store.get_problem(outcome.object_id)
        assert problem.inference_basis.synthesis == SYNTHESIS
        assert problem.inference_basis.contribution_of(a.object_id) is not None


# ---------------------------------------------------------------------------
# Input resolution and eligibility  [P-I2, N-14]
# ---------------------------------------------------------------------------


class TestInputEligibility:
    def test_missing_fact_refused(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-a")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, "obj-absent-1"), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.FACT_NOT_FOUND
        assert failure.attempted is False

    def test_non_fact_input_refused(self, store, allocator):
        """N-14: Problem Intelligence consumes Facts only."""
        ev = store.write_evidence(make_evidence(allocator, content="material"))
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(ev.object_id), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.FACT_NOT_FOUND
        assert "consumes Facts only" in failure.detail

    def test_superseded_fact_refused(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        store.transition(a.object_id, ObjectStatus.SUPERSEDED, "re-extracted")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.FACT_NOT_ACTIVE
        assert "SUPERSEDED" in failure.detail
        assert failure.attempted is False

    def test_rejected_fact_refused(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        store.transition(a.object_id, ObjectStatus.REJECTED, "declined")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=store, log=log)
        assert next(iter(log)).stage is InferenceStage.FACT_NOT_ACTIVE

    def test_non_request_argument_refused(self, store, allocator):
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer("not a request", store=store, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.INVALID_REQUEST
        assert failure.fact_refs == ("unknown: malformed request",)
        assert failure.attempted is False

    def test_temporal_conflict_refused(self, store, allocator):
        """V8 pre-check: the Facts cannot have been observed after 'now'."""
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id),
                store=store, log=log, clock=lambda: BEFORE_T0,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.TEMPORAL_CONFLICT
        assert failure.attempted is False


# ---------------------------------------------------------------------------
# Request validation  [N-4]
# ---------------------------------------------------------------------------


class TestRequestValidation:
    @pytest.mark.parametrize(
        "field", ["problem_statement", "affected_population", "severity",
                  "frequency", "problem_domain", "synthesis"]
    )
    def test_required_text_fields_never_blank(self, store, allocator, field):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match=field):
            request_over(a.object_id, b.object_id, **{field: "  "})

    def test_empty_fact_refs_rejected(self):
        with pytest.raises(InferenceError, match="requires the Facts"):
            request_over()

    def test_duplicate_fact_refs_rejected(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-a")
        with pytest.raises(InferenceError, match="twice"):
            request_over(a.object_id, a.object_id)

    def test_confidence_bounds_enforced(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="0.0, 1.0"):
            request_over(a.object_id, b.object_id, confidence=1.5)
        with pytest.raises(InferenceError, match="0.0, 1.0"):
            request_over(a.object_id, b.object_id, confidence=-0.1)

    def test_confidence_may_not_be_boolean(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="numeric"):
            request_over(a.object_id, b.object_id, confidence=True)

    def test_negative_population_estimate_rejected(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="non-negative"):
            request_over(a.object_id, b.object_id, population_size_estimate=-1)

    def test_blank_optional_text_rejected(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="existing_workarounds"):
            request_over(a.object_id, b.object_id, existing_workarounds=" ")

    def test_engine_configuration_ref_required(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="engine_configuration_ref"):
            request_over(a.object_id, b.object_id, engine_configuration_ref="")

    def test_optional_attributes_travel_unchanged(self, store, allocator):
        """N-4: what the request carries is what the Problem holds."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                population_size_estimate=1200,
                existing_workarounds="manual CSV reconciliation",
                problem_persistence="enduring",
                cost_indication="2h per week per seller",
            ),
            store=store, log=InferenceLog(),
        )
        problem = store.get_problem(outcome.object_id)
        assert problem.population_size_estimate == 1200
        assert problem.existing_workarounds == "manual CSV reconciliation"
        assert problem.problem_persistence == "enduring"
        assert problem.cost_indication == "2h per week per seller"

    def test_absence_stays_absence(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        problem = store.get_problem(outcome.object_id)
        assert problem.population_size_estimate is None
        assert problem.existing_workarounds is None
        assert problem.problem_persistence is None
        assert problem.cost_indication is None


# ---------------------------------------------------------------------------
# N-10 -- failure representation
# ---------------------------------------------------------------------------


class TestFailureRepresentation:
    def test_every_refusal_is_recorded_before_raising(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-solo")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        assert len(log) == 1
        assert next(iter(log)).stage is InferenceStage.INSUFFICIENT_SOURCES

    def test_not_attempted_vs_attempted_stay_distinguishable(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-a")
        b = write_fact_from(store, allocator, source_identifier="src-b")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, "obj-absent-2"), store=store, log=log)
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        not_attempted, attempted = tuple(log)
        assert not_attempted.attempted is False
        assert not_attempted.stage is InferenceStage.FACT_NOT_FOUND
        assert attempted.attempted is True
        assert attempted.stage is InferenceStage.INSUFFICIENT_SOURCES

    def test_no_problem_persisted_on_refusal(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-solo")
        before = len(store.problems)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        assert len(store.problems) == before

    def test_no_partial_state_on_refusal(self, store, allocator):
        """Object map, lineage index, graph and registry move together or not
        at all -- verified on the STORE_REJECTED path, the deepest refusal."""
        a, b = two_independent_facts(store, allocator)
        restatement = a.claim.as_text()
        objects_before = len(store.objects_of_type(ObjectType.PROBLEM))
        graph_before = store.graph.edge_count
        problems_before = len(store.problems)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id, statement=restatement),
                store=store, log=log,
            )
        assert len(store.objects_of_type(ObjectType.PROBLEM)) == objects_before
        assert store.graph.edge_count == graph_before
        assert len(store.problems) == problems_before
        assert store.verify_integrity().holds

    def test_failures_project_into_attached_failure_store(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-solo")
        log = InferenceLog()
        recorder = RecordingFailureStore()
        log.attach(recorder)
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        assert len(recorder.records) == 1
        projected = recorder.records[0]
        assert projected.object_id == "engine:ProblemIntelligence"
        assert projected.object_type is ObjectType.PROBLEM
        assert projected.input_ids == (a.object_id,)
        assert projected.engine is Engine.PROBLEM_INTELLIGENCE

    def test_accepted_inference_projects_nothing(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        recorder = RecordingFailureStore()
        log.attach(recorder)
        infer(request_over(a.object_id, b.object_id), store=store, log=log)
        assert len(recorder.records) == 0
        assert len(log) == 0

    def test_failure_record_requires_a_detail(self):
        with pytest.raises(InferenceError, match="detail"):
            InferenceFailure(
                fact_refs=("obj-fa-1",),
                stage=InferenceStage.INSUFFICIENT_SOURCES,
                reason="BELOW_S4_FLOOR",
                detail="  ",
                failed_at=T0,
                engine_configuration_ref="problem-inference-v1",
            )

    @pytest.mark.parametrize(
        "kwargs, match",
        [
            ({"fact_refs": ()}, "fact_refs is required"),
            ({"reason": "  "}, "reason token"),
            ({"failed_at": "not-a-datetime"}, "must be a datetime"),
            ({"engine_configuration_ref": " "}, "engine_configuration_ref"),
        ],
    )
    def test_failure_record_guards(self, kwargs, match):
        base = dict(
            fact_refs=("obj-fa-1",),
            stage=InferenceStage.INSUFFICIENT_SOURCES,
            reason="BELOW_S4_FLOOR",
            detail="one independent source across two Facts",
            failed_at=T0,
            engine_configuration_ref="problem-inference-v1",
        )
        base.update(kwargs)
        with pytest.raises(InferenceError, match=match):
            InferenceFailure(**base)

    def test_failure_stage_is_a_closed_set(self):
        with pytest.raises(InferenceError, match="closed set"):
            InferenceFailure(
                fact_refs=("obj-fa-1",),
                stage="SOMETHING_ELSE",
                reason="X",
                detail="d",
                failed_at=T0,
                engine_configuration_ref="problem-inference-v1",
            )

    def test_log_queries_by_facts_and_stage(self, store, allocator):
        a = write_fact_from(store, allocator, source_identifier="src-a")
        b = write_fact_from(store, allocator, source_identifier="src-b")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id), store=store, log=log)
        with pytest.raises(InferenceRefusedError):
            infer(request_over(b.object_id), store=store, log=log)
        assert len(log.for_facts(a.object_id)) == 1
        assert log.by_stage() == {InferenceStage.INSUFFICIENT_SOURCES: 2}

    def test_evidence_unresolved_stage_exists_fail_closed(self):
        """EVIDENCE_UNRESOLVED is defensive: the store's own write path (V3)
        keeps stored Facts' attachments resolvable, so the stage cannot
        arise from store-written Facts -- it exists so that if the
        invariant is ever broken, the engine refuses rather than counts."""
        failure = InferenceFailure(
            fact_refs=("obj-fa-1",),
            stage=InferenceStage.EVIDENCE_UNRESOLVED,
            reason="EVIDENCE_NOT_STORED",
            detail="attachment resolves to no stored Evidence",
            failed_at=T0,
            engine_configuration_ref="problem-inference-v1",
        )
        assert failure.attempted is False
        assert failure.as_failure_record().object_type is ObjectType.PROBLEM

    def test_stored_fact_without_payload_refuses_no_payload(self, store, allocator):
        """Defensive guard: a stored Fact whose payload registry is empty
        is refused, never inferred over on the stored shell alone."""
        a, b = two_independent_facts(store, allocator)
        shell = StoreShell(store)
        shell.get_fact = lambda ref: None
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=shell, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.FACT_NOT_FOUND
        assert "NO_PAYLOAD" in failure.reason or "payload" in failure.detail

    def test_unresolvable_attachment_evidence_refuses(self, store, allocator):
        """Defensive guard: if an attachment's Evidence cannot be resolved,
        independent-source identity cannot be established -- refusal, not
        a silent zero."""
        a, b = two_independent_facts(store, allocator)
        shell = StoreShell(store)
        shell.evidence = _NoEvidenceRegistry()
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=shell, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.EVIDENCE_UNRESOLVED
        assert failure.attempted is False

    def test_accepted_write_without_registered_payload_refuses(self, store, allocator):
        """Defensive guard: the engine never returns an outcome whose
        payload it cannot stand behind, even if the store claimed success."""
        a, b = two_independent_facts(store, allocator)
        shell = StoreShell(store)
        shell.get_problem = lambda object_id: None
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(request_over(a.object_id, b.object_id), store=shell, log=log)
        failure = next(iter(log))
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert failure.reason == "PAYLOAD_MISSING"


# ---------------------------------------------------------------------------
# V7 -- create authority
# ---------------------------------------------------------------------------


class TestCreateAuthority:
    def test_engine_produces_under_problem_intelligence(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert (
            outcome.problem.attributes.produced_by_engine
            is Engine.PROBLEM_INTELLIGENCE
        )

    def test_problem_under_wrong_engine_cannot_exist(self, allocator):
        """V7 at the type boundary: the engine could not produce under any
        other authority even if it tried."""
        a_id, b_id = "obj-fa-1", "obj-fa-2"
        with pytest.raises(ProblemError, match="only Problem Intelligence"):
            Problem(
                attributes=build_attrs(
                    allocator.new_object(),
                    ObjectType.PROBLEM,
                    ((a_id, ObjectType.FACT), (b_id, ObjectType.FACT)),
                    status=ObjectStatus.ACTIVE,
                    status_reason=None,
                    engine=Engine.RESEARCH,
                ),
                problem_statement=STATEMENT,
                affected_population=POPULATION,
                supporting_facts=(a_id, b_id),
                severity=weight(WeightBand.SEVERE, (a_id, b_id,), SEVERITY_DETAIL),
                frequency=weight(WeightBand.RECURRING, (a_id, b_id,), FREQUENCY_DETAIL),
                problem_domain=DOMAIN,
                inference_basis=InferenceBasis(
                    contributions=contributions(a_id, b_id),
                    synthesis=SYNTHESIS,
                ),
            )


# ---------------------------------------------------------------------------
# Persistence, lineage, confidence  [R-3, R-6, N-6, N-16]
# ---------------------------------------------------------------------------


class TestPersistenceSemantics:
    def test_problem_enters_through_acceptance_active(self, store, allocator):
        """The established platform interpretation: acceptance IS the
        PROPOSED -> ACTIVE transition."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        stored = store.get(outcome.object_id)
        assert stored.status is ObjectStatus.ACTIVE
        assert stored.attributes.status_reason is None

    def test_supports_equals_derives_from(self, store, allocator):
        """R-6: the supporting set is the read set."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        problem = outcome.problem
        assert set(problem.supporting_facts) == {
            ref.object_id for ref in problem.attributes.derives_from
        }
        assert all(
            ref.object_type is ObjectType.FACT
            for ref in problem.attributes.derives_from
        )

    def test_lineage_depth_two_to_evidence(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert store.graph.depth_to_evidence(outcome.object_id) == 2

    def test_confidence_bounded_by_supporting_facts(self, store, allocator):
        """R-3/V5: effective <= min supporting Facts' effective confidence."""
        a, b = two_independent_facts(store, allocator)
        ceiling = min(
            store.get_fact(a.object_id).attributes.confidence.effective_confidence,
            store.get_fact(b.object_id).attributes.confidence.effective_confidence,
        )
        outcome = infer(
            request_over(a.object_id, b.object_id, confidence=0.99),
            store=store, log=InferenceLog(),
        )
        attrs = outcome.problem.attributes
        assert attrs.confidence.effective_confidence <= ceiling + 1e-9
        assert attrs.confidence.assertion_confidence == 0.99

    def test_explanation_names_the_facts_and_criteria(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        explanation = outcome.problem.attributes.explanation
        assert frozenset(explanation.objects_referenced) == frozenset(
            (a.object_id, b.object_id)
        )
        assert any("S-4" in c for c in explanation.criteria_applied)
        assert any("N-16" in c for c in explanation.criteria_applied)

    def test_observed_at_is_latest_supporting_observation(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        latest = max(
            store.get_fact(a.object_id).attributes.observed_at,
            store.get_fact(b.object_id).attributes.observed_at,
        )
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert outcome.problem.attributes.observed_at == latest

    def test_engine_never_touches_the_registry_directly(self, store, allocator):
        """The only path to a registered Problem is write_problem; the
        outcome's payload is the registered instance, byte-equal."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        registered = store.get_problem(outcome.object_id)
        assert registered is outcome.problem
        assert registered is store.problems.get(outcome.object_id)

    def test_integrity_holds_after_inference(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert store.verify_integrity().holds
        assert store.problems.integrity().verify() == ()

    def test_downgrade_of_supporting_fact_surfaces_in_integrity_not_engine(
        self, store, allocator
    ):
        """P-I2 afterwards is continuous integrity's job (M-65 precedent);
        the engine guarantees eligibility only at inference time."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        store.transition(a.object_id, ObjectStatus.SUPERSEDED, "re-extracted")
        assert store.get_problem(outcome.object_id) is not None
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I2" for v in violations)


# ---------------------------------------------------------------------------
# Property-based invariants  [N-4]
# ---------------------------------------------------------------------------


@given(
    source_ids=st.sets(
        st.sampled_from(
            ["alpha", "beta", "gamma", "delta", "omega", "zeta"]
        ),
        min_size=1,
        max_size=4,
    ),
    group_all=st.booleans(),
)
@settings(max_examples=40, deadline=None)
def test_property_count_equals_distinct_keys_and_gate_is_the_floor(
    source_ids, group_all
):
    """For any hypothesis over Facts from the given sources: the derived
    count is exactly the number of distinct independence keys, and the
    inference is accepted iff that count meets the S-4 floor of 2."""
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    store = KnowledgeStore()
    log = InferenceLog()
    facts = []
    for i, source_id in enumerate(sorted(source_ids)):
        facts.append(
            write_fact_from(
                store, allocator,
                source_identifier=source_id,
                independence_group="one-group" if group_all else None,
            )
        )
    refs = tuple(f.object_id for f in facts)
    request = request_over(*refs)

    expected_keys = frozenset(
        "one-group" if group_all else source_id for source_id in source_ids
    )
    try:
        outcome = infer(request, store=store, log=log)
        assert len(expected_keys) >= 2
        assert outcome.independent_source_count == len(expected_keys)
        assert outcome.independence_keys == expected_keys
        assert len(log) == 0
    except InferenceRefusedError:
        assert len(expected_keys) < 2
        assert len(log) == 1
        assert next(iter(log)).stage is InferenceStage.INSUFFICIENT_SOURCES
    # Either a persisted Problem or a recorded failure -- never both,
    # never neither.
    assert (len(store.problems) == 1) == (len(log) == 0)


@given(
    confidence=st.floats(min_value=0.0, max_value=1.0),
    order=st.permutations(["p", "q", "r"]),
)
@settings(max_examples=40, deadline=None)
def test_property_confidence_and_ordering(confidence, order):
    """Accepted inferences: effective confidence never exceeds any bound,
    and the derivation is independent of supporting-Fact order."""
    from oip.identity import IdentityAllocator

    allocator = IdentityAllocator()
    store = KnowledgeStore()
    by_tag = {
        tag: write_fact_from(store, allocator, source_identifier=f"src-{tag}")
        for tag in ("p", "q", "r")
    }
    refs = tuple(by_tag[tag].object_id for tag in order)
    outcome = infer(
        request_over(*refs, confidence=confidence), store=store, log=InferenceLog()
    )
    attrs = outcome.problem.attributes
    ceilings = [
        store.get_fact(r).attributes.confidence.effective_confidence for r in refs
    ]
    assert attrs.confidence.effective_confidence <= min(ceilings) + 1e-9
    assert attrs.confidence.effective_confidence <= confidence + 1e-9
    assert attrs.independent_source_count == 3
    assert outcome.independence_keys == frozenset(f"src-{t}" for t in ("p", "q", "r"))


# ---------------------------------------------------------------------------
# T04.1.2 -- the versioned path (reformulation)
# ---------------------------------------------------------------------------
#
# The versioned mode adds one trigger: a new version of an existing
# Problem. The standalone semantics above are untouched -- the first two
# tests pin that -- and everything else here exercises the versioned
# boundary: predecessor validation, chain-wide solution-independence
# [P-I1], and the extraction-precedent write recipe (dry-run, transition,
# write) with its failure surface closed BEFORE any state changes.
#
# Violating statements enter chains the same way the ProblemIntegrity
# tests smuggle them: post-write mutation through object.__setattr__,
# standing in for a path no single write controls.

V2_STATEMENT = (
    "Sellers with large catalogs silently lose update work when batch "
    "operations exceed platform limits and discover the loss only "
    "afterwards."
)
V3_STATEMENT = (
    "Sellers operating at scale encounter silent partial failures of "
    "bulk inventory updates across reporting periods."
)
V4_STATEMENT = (
    "Sellers handling many simultaneous listings report that bulk changes "
    "finish without any per-item outcome they can review."
)
ABSENCE_STATEMENT = (
    "There is no way to confirm that batch updates completed."
)
REMEDY_STATEMENT = (
    "Sellers need a notification service that confirms bulk updates."
)

_STATEMENTS = (STATEMENT, V2_STATEMENT, V3_STATEMENT, V4_STATEMENT)


def versioned_request(*refs, statement, synthesis=None):
    """A request whose statement is guaranteed distinct per call."""
    return request_over(
        *refs,
        statement=statement,
        synthesis=synthesis or f"Together these Facts show the deficiency as stated.",
    )


def infer_versioned(store, *refs, statement, predecessor_id, synthesis=None):
    return infer(
        versioned_request(*refs, statement=statement, synthesis=synthesis),
        store=store,
        log=InferenceLog(),
        predecessor_id=predecessor_id,
    )


def build_chain(store, allocator, facts, depth):
    """A clean chain of `depth` versions: standalone v1, then versioned."""
    refs = tuple(f.object_id for f in facts)
    first = infer(
        versioned_request(*refs, statement=_STATEMENTS[0]), store=store, log=InferenceLog()
    ).problem
    chain = [first]
    for level in range(1, depth):
        chain.append(
            infer_versioned(
                store, *refs,
                statement=_STATEMENTS[level % len(_STATEMENTS) if level < len(_STATEMENTS) else level],
                predecessor_id=chain[-1].object_id,
            ).problem
        )
    return chain


def smuggle(store, object_id, statement):
    """Post-write statement corruption, as in the P-I1 integrity tests."""
    object.__setattr__(
        store.get_problem(object_id), "problem_statement", statement
    )


class _NoLineageShell(StoreShell):
    """A stored object that resolves to no lineage -- a broken store
    invariant the real store cannot produce (every write registers a
    lineage), guarded so the engine refuses rather than crashes."""

    def resolve_lineage(self, object_id):
        return None


class _PayloadGapShell(StoreShell):
    """A lineage version whose Problem payload is unregistered -- same
    structural guard family as the standalone PAYLOAD_MISSING guard."""

    def __init__(self, store, gap_id):
        super().__init__(store)
        self._gap_id = gap_id

    def get_problem(self, object_id):
        if object_id == self._gap_id:
            return None
        return self._inner.get_problem(object_id)


class _TransitionRefusingShell(StoreShell):
    """The store refuses the predecessor transition, mutating nothing."""

    def transition(self, object_id, status, reason=None):
        raise RuntimeError("transition refused by test shell")


class _WriteRefusingShell(StoreShell):
    """The store refuses the successor write after the transition."""

    def __init__(self, store):
        super().__init__(store)
        self.transitioned = None

    def transition(self, object_id, status, reason=None):
        self.transitioned = (object_id, status)
        return self._inner.transition(object_id, status, reason)

    def write_problem(self, problem, predecessor_id=None):
        raise WriteRejectedError(
            FailureRecord(
                object_id=problem.object_id,
                object_type=ObjectType.PROBLEM,
                failed_rules=(
                    RuleResult(
                        "P-V2", RuleOutcome.FAIL, "shell-injected refusal"
                    ),
                ),
                recorded_at=datetime.now(timezone.utc),
                engine_configuration_ref="test-shell",
            )
        )


def refusal_of(call):
    """Run `call`, return the recorded failure -- or None on success."""
    log = InferenceLog()
    try:
        call(log)
    except InferenceRefusedError:
        return next(iter(log)), log
    return None, log


class TestStandalonePathUnchanged:
    """T04.1.1 behavior with the extended signature. [backward compat]"""

    def test_omitted_predecessor_id_is_standalone(self, store, allocator):
        """#1 No predecessor_id: fresh identity, version 1, no predecessor
        on the outcome -- exactly the T04.1.1 behavior."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog())
        assert outcome.predecessor_id is None
        assert outcome.problem.attributes.version == 1
        assert outcome.problem.attributes.identity.is_initial

    def test_explicit_none_equals_omitted(self, store, allocator):
        """#2 predecessor_id=None is the same call, not a third mode."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(
            request_over(a.object_id, b.object_id),
            store=store, log=InferenceLog(), predecessor_id=None,
        )
        assert outcome.predecessor_id is None
        assert store.find(outcome.object_id).status is ObjectStatus.ACTIVE


class TestVersionedAbsenceFramed:
    """T04.1.2 AC1: absence-framed statements rejected on the versioned
    path, by the authoritative P-V2, before any state changes."""

    def test_absence_framed_successor_refused(self, store, allocator):
        """#3 'There is no way to...' smuggles a solution presence."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=ABSENCE_STATEMENT),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure is not None
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert "P-V2" in failure.detail

    def test_remedy_framed_successor_refused(self, store, allocator):
        """#4 'need a ...' framing refused identically."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=REMEDY_STATEMENT),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure is not None
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert "P-V2" in failure.detail
        assert failure.attempted is True

    def test_refusal_precedes_the_transition(self, store, allocator):
        """#5 The dry-run refusal leaves the predecessor ACTIVE and the
        lineage at one version: nothing was superseded for a statement
        that could never be written."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=ABSENCE_STATEMENT),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        assert store.find(v1.object_id).status is ObjectStatus.ACTIVE
        assert len(store.versions_of(v1.attributes.identity.lineage_id)) == 1


class TestVersionedChain:
    """T04.1.2 AC2: clean reformulation succeeds; a violating version
    anywhere in the chain refuses the write. [P-I1, R-1/V11]"""

    def test_clean_v1_to_v2_succeeds(self, store, allocator):
        """#6 The happy path: a clean successor is accepted."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        outcome = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        )
        assert outcome.problem.problem_statement == V2_STATEMENT
        assert outcome.predecessor_id == v1.object_id
        assert store.get_problem(outcome.object_id) is not None

    def test_predecessor_becomes_superseded(self, store, allocator):
        """#7 The reformulation transition: v1 ACTIVE -> SUPERSEDED."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        assert store.find(v1.object_id).status is ObjectStatus.SUPERSEDED
        assert store.find(v1.object_id).attributes.status_reason is not None

    def test_successor_is_active(self, store, allocator):
        """#8 I5: the successor takes over as the lineage's ACTIVE
        version."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        assert store.find(v2.object_id).status is ObjectStatus.ACTIVE

    def test_version_increments(self, store, allocator):
        """#9 R-1/V11 via allocator.succeed: v2 is predecessor+1."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        assert v1.attributes.version == 1
        assert v2.attributes.version == 2
        assert {v.object_id for v in store.versions_of(
            v1.attributes.identity.lineage_id
        )} == {v1.object_id, v2.object_id}

    def test_lineage_id_constant(self, store, allocator):
        """#10 The successor is a new version of the SAME logical
        object."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        assert (
            v2.attributes.identity.lineage_id
            == v1.attributes.identity.lineage_id
        )

    def test_every_version_of_a_deep_chain_is_checked(self, store, allocator):
        """#11 A four-deep clean chain extends; a violation in the MIDDLE
        version is still caught, so enumeration cannot stop at the
        latest."""
        a, b = two_independent_facts(store, allocator)
        chain = build_chain(store, allocator, (a, b), depth=4)
        lineage = chain[0].attributes.identity.lineage_id
        assert len(store.versions_of(lineage)) == 4
        smuggle(store, chain[1].object_id, ABSENCE_STATEMENT)  # v2, middle
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V4_STATEMENT
                ),
                store=store, log=log, predecessor_id=chain[-1].object_id,
            )
        )
        assert failure.stage is InferenceStage.CHAIN_NOT_SOLUTION_INDEPENDENT
        assert chain[1].object_id in failure.detail

    def test_clean_latest_does_not_bypass_violating_earlier(self, store, allocator):
        """#12 The core P-I1 semantics: a clean ACTIVE successor cannot
        make a violating SUPERSEDED ancestor acceptable."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        smuggle(store, v1.object_id, ABSENCE_STATEMENT)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V3_STATEMENT
                ),
                store=store, log=log, predecessor_id=v2.object_id,
            )
        )
        assert failure.stage is InferenceStage.CHAIN_NOT_SOLUTION_INDEPENDENT
        assert v1.object_id in failure.detail
        assert v2.object_id not in failure.detail  # only the violator named

    def test_violating_active_predecessor_refused(self, store, allocator):
        """#13 A violating predecessor refuses however clean the proposed
        successor."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        smuggle(store, v1.object_id, REMEDY_STATEMENT)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V2_STATEMENT
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure.stage is InferenceStage.CHAIN_NOT_SOLUTION_INDEPENDENT
        assert "need a" in failure.detail  # the marker is named


class TestPredecessorValidation:
    """Refusal stages for an unusable predecessor. [N-10]"""

    def test_unknown_predecessor_refused(self, store, allocator):
        """#14 PREDECESSOR_NOT_FOUND: nothing to supersede."""
        a, b = two_independent_facts(store, allocator)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=V2_STATEMENT),
                store=store, log=log, predecessor_id="obj-nonexistent",
            )
        )
        assert failure.stage is InferenceStage.PREDECESSOR_NOT_FOUND
        assert failure.attempted is False

    def test_fact_predecessor_refused(self, store, allocator):
        """#15 PREDECESSOR_NOT_A_PROBLEM: Problem Intelligence modifies
        Problems only. [V7]"""
        a, b = two_independent_facts(store, allocator)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=V2_STATEMENT),
                store=store, log=log, predecessor_id=a.object_id,
            )
        )
        assert failure.stage is InferenceStage.PREDECESSOR_NOT_A_PROBLEM
        assert failure.attempted is False

    def test_superseded_predecessor_refused(self, store, allocator):
        """#16 PREDECESSOR_NOT_ACTIVE: only an ACTIVE version may be
        superseded. [R-2]"""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V3_STATEMENT
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure.stage is InferenceStage.PREDECESSOR_NOT_ACTIVE
        assert failure.attempted is False
        assert "SUPERSEDED" in failure.detail

    def test_stages_distinguishable_under_n10(self, store, allocator):
        """#17 Every stage is a distinct, recorded failure; the
        resolution stages are not-attempted, the chain stage is
        attempted, and none collapses into a generic error."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        smuggle(store, v1.object_id, ABSENCE_STATEMENT)
        seen = {}
        for predecessor, key in (
            ("obj-nonexistent", "not_found"),
            (a.object_id, "not_a_problem"),
        ):
            failure, _ = refusal_of(
                lambda log, p=predecessor: infer(
                    versioned_request(
                        a.object_id, b.object_id, statement=V2_STATEMENT
                    ),
                    store=store, log=log, predecessor_id=p,
                )
            )
            seen[key] = (failure.stage, failure.reason, failure.attempted)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V2_STATEMENT
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        seen["chain"] = (failure.stage, failure.reason, failure.attempted)
        stages = {entry[0] for entry in seen.values()}
        assert len(stages) == 3  # all distinguishable
        assert all(entry[2] is False for k, entry in seen.items() if k != "chain")
        assert seen["chain"][2] is True


class TestVersionedAtomicity:
    """No partial state on any versioned refusal. [R-2, N-10]"""

    def test_write_failure_after_transition_names_surviving_state(
        self, store, allocator
    ):
        """#18 The extraction-precedent residual: SUPERSEDED is terminal,
        so no restore exists -- the refusal names the exact surviving
        state instead. Predecessor SUPERSEDED with payload intact, no
        successor, refusal recorded."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        shell = _WriteRefusingShell(store)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=V2_STATEMENT),
                store=shell, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert failure.reason == "WRITE_FAILED_AFTER_TRANSITION"
        assert shell.transitioned == (v1.object_id, ObjectStatus.SUPERSEDED)
        # Surviving state, exactly as named:
        assert store.find(v1.object_id).status is ObjectStatus.SUPERSEDED
        assert store.get_problem(v1.object_id).problem_statement == STATEMENT
        assert len(store.versions_of(v1.attributes.identity.lineage_id)) == 1
        assert len(store.problems) == 1

    def test_transition_failure_leaves_predecessor_unchanged(
        self, store, allocator
    ):
        """#19 A failed transition mutates nothing: the predecessor
        stays ACTIVE, no successor exists."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        shell = _TransitionRefusingShell(store)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=V2_STATEMENT),
                store=shell, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert failure.reason == "PREDECESSOR_TRANSITION_FAILED"
        assert store.find(v1.object_id).status is ObjectStatus.ACTIVE
        assert len(store.versions_of(v1.attributes.identity.lineage_id)) == 1
        assert len(store.problems) == 1

    def test_chain_refusal_leaves_store_unchanged(self, store, allocator):
        """#20 The chain refusal precedes every gate that writes."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        smuggle(store, v1.object_id, ABSENCE_STATEMENT)
        before = (
            len(store.problems),
            tuple(
                (v.object_id, v.status) for v in store.versions_of(
                    v1.attributes.identity.lineage_id
                )
            ),
        )
        refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V3_STATEMENT
                ),
                store=store, log=log, predecessor_id=v2.object_id,
            )
        )
        after = (
            len(store.problems),
            tuple(
                (v.object_id, v.status) for v in store.versions_of(
                    v1.attributes.identity.lineage_id
                )
            ),
        )
        assert before == after

    def test_dry_run_refusal_leaves_store_unchanged(self, store, allocator):
        """#21 The dry-run refusal precedes the transition."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        before = (
            store.find(v1.object_id).status,
            len(store.versions_of(v1.attributes.identity.lineage_id)),
            len(store.problems),
        )
        refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=REMEDY_STATEMENT
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        after = (
            store.find(v1.object_id).status,
            len(store.versions_of(v1.attributes.identity.lineage_id)),
            len(store.problems),
        )
        assert before == after

    def test_validation_refusals_create_nothing(self, store, allocator):
        """#22 Predecessor-validation refusals are not-attempted: no
        object, no version, no registry entry appears."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        problems_before = len(store.problems)
        for predecessor in ("obj-nonexistent", a.object_id):
            refusal_of(
                lambda log, p=predecessor: infer(
                    versioned_request(
                        a.object_id, b.object_id, statement=V2_STATEMENT
                    ),
                    store=store, log=log, predecessor_id=p,
                )
            )
        assert len(store.problems) == problems_before
        assert len(store.versions_of(v1.attributes.identity.lineage_id)) == 1


    def test_unresolvable_lineage_refuses_not_crashes(self, store, allocator):
        """A predecessor that resolves to no lineage is a broken store
        invariant: the engine refuses with a recorded failure rather
        than asserting anything. [N-10]"""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        shell = _NoLineageShell(store)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(a.object_id, b.object_id, statement=V2_STATEMENT),
                store=shell, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure.stage is InferenceStage.PREDECESSOR_NOT_FOUND
        assert failure.reason == "NO_LINEAGE"
        assert failure.attempted is False

    def test_unreadable_chain_version_refuses_fail_closed(self, store, allocator):
        """A version whose payload cannot be read cannot be certified
        solution-independent: the chain check refuses and names the gap
        instead of certifying what it never read. [P-I1, N-10]"""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        shell = _PayloadGapShell(store, v1.object_id)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V3_STATEMENT
                ),
                store=shell, log=log, predecessor_id=v2.object_id,
            )
        )
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert failure.reason == "REGISTRY_GAP"
        assert failure.attempted is True
        assert v1.object_id in failure.detail


class TestVersionedDeterminism:
    """Properties, never output equality. [N-4]"""

    def test_same_inputs_same_version_structure(self, store, allocator):
        """#23 Two identically-seeded runs produce isomorphic version
        structures: version 2, one lineage, one ACTIVE version."""
        results = []
        for _ in range(2):
            s = KnowledgeStore()
            a, b = two_independent_facts(s, s.allocator)
            v1 = infer(request_over(a.object_id, b.object_id), store=s, log=InferenceLog()).problem
            v2 = infer_versioned(
                s, a.object_id, b.object_id,
                statement=V2_STATEMENT, predecessor_id=v1.object_id,
            ).problem
            results.append(
                (
                    v1.attributes.version,
                    v2.attributes.version,
                    v2.attributes.identity.lineage_id
                    == v1.attributes.identity.lineage_id,
                    len(s.versions_of(v1.attributes.identity.lineage_id)),
                    sum(
                        1
                        for v in s.versions_of(v1.attributes.identity.lineage_id)
                        if v.status is ObjectStatus.ACTIVE
                    ),
                )
            )
        assert results[0] == results[1]

    def test_chain_enumeration_order_is_deterministic(self, store, allocator):
        """#24 A multi-violation chain names its violators in a stable
        order, so the refusal is reproducible."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        v3 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V3_STATEMENT, predecessor_id=v2.object_id,
        ).problem
        smuggle(store, v2.object_id, ABSENCE_STATEMENT)
        smuggle(store, v1.object_id, REMEDY_STATEMENT)
        details = []
        for _ in range(3):
            failure, _ = refusal_of(
                lambda log: infer(
                    versioned_request(
                        a.object_id, b.object_id, statement=V4_STATEMENT
                    ),
                    store=store, log=log, predecessor_id=v3.object_id,
                )
            )
            details.append(failure.detail)
        assert len(set(details)) == 1  # identical across repetitions
        assert details[0].index(v1.object_id) < details[0].index(v2.object_id)


class TestVersionedAcceptanceIntegration:
    """The authoritative rules, not engine copies, decide. [P-V1..P-V6]"""

    def test_pv2_authoritative_on_the_versioned_path(self, store, allocator):
        """#25 The dry-run invokes the authoritative P-V2 and names it in
        the refusal."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=REMEDY_STATEMENT
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        )
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert "P-V2" in failure.detail
        assert "need a" in failure.detail

    def test_v11_authoritative_successor_identity(self, store, allocator):
        """#26 The successor identity comes from allocator.succeed:
        version increments, lineage constant, predecessor linked."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        assert v2.attributes.version == v1.attributes.version + 1
        assert {v.object_id for v in store.versions_of(
            v1.attributes.identity.lineage_id
        )} == {v1.object_id, v2.object_id}
        assert (
            v2.attributes.identity.lineage_id
            == v1.attributes.identity.lineage_id
        )

    def test_i5_one_active_version_per_lineage(self, store, allocator):
        """#27 After the versioned write the lineage holds exactly one
        ACTIVE version: the successor."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        active = [
            v.object_id
            for v in store.versions_of(v1.attributes.identity.lineage_id)
            if v.status is ObjectStatus.ACTIVE
        ]
        assert active == [v2.object_id]

    def test_pi1_intact_and_consistent(self, store, allocator):
        """#28 The engine's write-time chain refusal and the detective
        P-I1 agree: a chain the engine refuses is a chain integrity
        flags."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        smuggle(store, v1.object_id, ABSENCE_STATEMENT)
        violations = store.problems.integrity().verify()
        assert any(v.constraint_id == "P-I1" for v in violations)
        failure, _ = refusal_of(
            lambda log: infer(
                versioned_request(
                    a.object_id, b.object_id, statement=V3_STATEMENT
                ),
                store=store, log=log, predecessor_id=v2.object_id,
            )
        )
        assert failure.stage is InferenceStage.CHAIN_NOT_SOLUTION_INDEPENDENT


class TestVersionedScopeBoundaries:
    """What the versioned path deliberately does NOT do. [M-21, M-22,
    Master Reference 4.6 boundaries]"""

    def test_no_duplicates_links_created(self, store, allocator):
        """#29 Versioning is R-1 succession, never a DUPLICATES link."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        v2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=v1.object_id,
        ).problem
        for oid in (v1.object_id, v2.object_id):
            assert store.graph.parents(oid, RelationshipType.DUPLICATES) == frozenset()
            assert store.graph.children(oid, RelationshipType.DUPLICATES) == frozenset()

    def test_no_dedup_across_lineages(self, store, allocator):
        """#30 Two lineages stating the same deficiency stay two
        lineages: no merging, no identity unification (T04.1.5)."""
        a, b = two_independent_facts(store, allocator)
        p = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        q = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        assert p.attributes.identity.lineage_id != q.attributes.identity.lineage_id
        p2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=p.object_id,
        ).problem
        q2 = infer_versioned(
            store, a.object_id, b.object_id,
            statement=V2_STATEMENT, predecessor_id=q.object_id,
        ).problem
        assert (
            p2.attributes.identity.lineage_id
            != q2.attributes.identity.lineage_id
        )
        assert len(store.problems) == 4  # nothing merged

    def test_no_population_widening(self, store, allocator):
        """#31 affected_population is carried exactly as requested; the
        engine widens nothing (T04.1.3)."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        narrow = "Segment B sellers with more than 500 active listings."
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT,
                population=narrow,
                synthesis="Together these Facts show the deficiency for the narrow segment.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.affected_population == narrow
        assert v1.affected_population == POPULATION  # predecessor untouched

    def test_severity_rating_carried_verbatim_across_versions(self, store, allocator):
        """#32 Severity is the inferer's rating, carried unchanged; the
        engine derives, orders nothing and adds nothing (N-4, F-W1
        R3/R4, T04.1.4).

        Supersedes test_no_severity_ranking, which asserted severity as
        free text with no ordering. F-W1 ratified structured ordinal
        ratings, so the free-text clause is gone; the N-4 verbatim-carry
        clause is preserved and re-asserted here: a justification-only
        revision (equal band, changed detail) versions freely, and each
        version carries the exact rating the inferer supplied.
        """
        a, b = two_independent_facts(store, allocator)
        requested_v1 = weight(
            WeightBand.SEVERE, (a.object_id, b.object_id),
            "unnoticed loss reaches customers",
        )
        v1 = infer(
            request_over(a.object_id, b.object_id, severity=requested_v1),
            store=store, log=InferenceLog(),
        ).problem
        requested_v2 = weight(
            WeightBand.SEVERE, (a.object_id, b.object_id),
            "halting revenue for affected sellers",
        )
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, severity=requested_v2,
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.severity is requested_v2  # carried verbatim, N-4
        assert v1.severity is requested_v1  # predecessor untouched
        assert v2.severity.band is WeightBand.SEVERE
        assert v2.severity.detail == requested_v2.detail
        assert v2.severity.cited_facts == requested_v2.cited_facts
        # No engine-derived ranking: the ordinal lives in the shared
        # ratified band model, never in a per-Problem derived field.
        assert not hasattr(v2, "severity_rank")

    def test_no_taxonomy_constraints(self, store, allocator):
        """#33 problem_domain is unconstrained free text (T04.1.6,
        M-21)."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, domain="A domain no taxonomy contains"),
            store=store, log=InferenceLog(),
        ).problem
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT,
                domain="Another unregulated domain entirely",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.problem_domain == "Another unregulated domain entirely"


# ---------------------------------------------------------------------------
# T04.1.3 -- affected-population identification (P-I3 at the write boundary)
# ---------------------------------------------------------------------------
#
# P-V3 (non-empty, non-generic) stays where it already is: request
# construction and the authoritative acceptance rules. What T04.1.3 adds
# is the P-I3 gate on the versioned path: widening the population (or
# raising its size estimate) without additional supporting Facts refuses
# the inference BEFORE any state changes -- for the proposed successor
# AND for every existing consecutive pair of the lineage. The verdicts
# below all come from the authoritative widens_population_of /
# adds_support_over; violating pairs enter lineages the same way the
# P-I1/P-I3 integrity tests do, by post-write mutation.

NARROW_POPULATION = (
    "Segment A sellers maintaining inventories above 50 active listings"
)
WIDER_POPULATION = "Segment A sellers"  # NARROW minus qualifying terms
REWORDED_POPULATION = (
    "High-volume marketplace merchants operating in the EU region"
)  # neither a superset nor a subset: undecidable, never guessed [S-3]


class TestPopulationPv3Regression:
    """AC1 unchanged: P-V3 remains the request/acceptance authority."""

    def test_specific_population_succeeds_both_paths(self, store, allocator):
        """#2 A specific, non-empty population is accepted standalone and
        versioned."""
        a, b = two_independent_facts(store, allocator)
        standalone = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        )
        assert standalone.problem.affected_population == NARROW_POPULATION
        versioned = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, population=NARROW_POPULATION,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=standalone.object_id,
        )
        assert versioned.problem.affected_population == NARROW_POPULATION

    def test_generic_population_refused_standalone(self, store, allocator):
        """#3 Generic descriptors never reach the store."""
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id, population="everyone"),
                store=store, log=log,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert "P-V3" in failure.detail

    def test_generic_population_refused_versioned(self, store, allocator):
        """#3 The versioned dry-run refuses a generic successor before the
        transition (T04.1.2 machinery, unchanged)."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(request_over(a.object_id, b.object_id), store=store, log=InferenceLog()).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population="all users",
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.STORE_REJECTED
        assert "P-V3" in failure.detail
        assert store.find(v1.object_id).status is ObjectStatus.ACTIVE

    @pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
    def test_empty_population_refused_at_request(self, store, allocator, blank):
        """#4 An absent population is not a request (N-4)."""
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="affected_population"):
            request_over(a.object_id, b.object_id, population=blank)


class TestPopulationWideningGate:
    """AC2: the successor pair gate (P-I3, authoritative semantics)."""

    def test_term_drop_widening_without_support_refused(self, store, allocator):
        """#5 Dropping qualifying terms broadens the population; without a
        new Fact the versioned inference is refused."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.POPULATION_WIDENED_WITHOUT_SUPPORT
        assert failure.reason == "SUCCESSOR_WIDENS_WITHOUT_SUPPORT"

    def test_refusal_names_both_populations(self, store, allocator):
        """#6 The refusal identifies the population it came from and the
        one it refused to widen to."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert NARROW_POPULATION in failure.detail
        assert WIDER_POPULATION in failure.detail

    def test_term_drop_widening_with_added_fact_succeeds(self, store, allocator):
        """#7 Widening backed by an additional supporting Fact is the
        IOM's sanctioned population revision."""
        a, b = two_independent_facts(store, allocator)
        c = write_fact_from(store, allocator, source_identifier="src-gamma")
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        outcome = infer(
            request_over(
                a.object_id, b.object_id, c.object_id,
                statement=V2_STATEMENT, population=WIDER_POPULATION,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.affected_population == WIDER_POPULATION
        assert outcome.problem.attributes.version == 2
        assert not [
            v for v in store.problems.integrity().verify()
            if v.constraint_id == "P-I3"
        ]

    def test_raised_estimate_without_support_refused(self, store, allocator):
        """#8 A raised population_size_estimate is numerical widening."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                population=NARROW_POPULATION, population_size_estimate=100,
            ),
            store=store, log=InferenceLog(),
        ).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=NARROW_POPULATION,
                    population_size_estimate=9_000,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.POPULATION_WIDENED_WITHOUT_SUPPORT

    def test_raised_estimate_with_added_fact_succeeds(self, store, allocator):
        """#9 The same raise, supported by a new Fact, is accepted -- the
        authoritative P-I3 says the widening is justified."""
        a, b = two_independent_facts(store, allocator)
        c = write_fact_from(store, allocator, source_identifier="src-delta")
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                population=NARROW_POPULATION, population_size_estimate=100,
            ),
            store=store, log=InferenceLog(),
        ).problem
        outcome = infer(
            request_over(
                a.object_id, b.object_id, c.object_id,
                statement=V2_STATEMENT, population=NARROW_POPULATION,
                population_size_estimate=9_000,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.population_size_estimate == 9_000

    def test_undecidable_rewording_allowed(self, store, allocator):
        """#10 A differently worded population is neither wider nor
        narrower; the engine does not guess (S-3)."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, population=REWORDED_POPULATION,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.affected_population == REWORDED_POPULATION

    def test_narrowing_allowed(self, store, allocator):
        """#11 Adding qualifying terms narrows the population -- always
        legal without new Facts."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        narrower = NARROW_POPULATION + " with high dispute rates"
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, population=narrower,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.affected_population == narrower

    def test_equal_population_allowed(self, store, allocator):
        """#12 Restating the same population is not widening."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, population=NARROW_POPULATION,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.affected_population == NARROW_POPULATION
        assert outcome.problem.attributes.version == 2


class TestPopulationChainEnforcement:
    """AC2, chain principle: an existing violating pair blocks the
    lineage, however clean the latest version."""

    def _lineage_with_violating_pair(self, store, allocator):
        """v1 -> v2 clean at write time; v1's population is then narrowed
        post-write so the stored pair v1 -> v2 now widens without
        support (the same corruption vector the P-I1 tests use)."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT,
                population=NARROW_POPULATION + " with high dispute rates",
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        object.__setattr__(
            store.get_problem(v1.object_id),
            "affected_population",
            NARROW_POPULATION + " with high dispute rates and EU registration",
        )
        return a, b, v1, v2

    def test_earlier_pair_violation_blocks_new_version(self, store, allocator):
        """#13 The lineage's P-I3 invariant is already broken; no new
        version may extend it."""
        a, b, v1, v2 = self._lineage_with_violating_pair(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V3_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v2.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.POPULATION_WIDENED_WITHOUT_SUPPORT
        assert failure.reason == "PAIR_WIDENED_WITHOUT_SUPPORT"

    def test_clean_latest_does_not_bypass_earlier_violation(self, store, allocator):
        """#14 The ACTIVE latest version is itself clean (the successor
        would not widen IT); the refusal comes from the earlier pair and
        names that pair."""
        a, b, v1, v2 = self._lineage_with_violating_pair(store, allocator)
        successor = request_over(
            a.object_id, b.object_id,
            statement=V3_STATEMENT,
            population=NARROW_POPULATION + " with high dispute rates and EU registration",
            synthesis="Together these Facts show the deficiency as stated.",
        )
        # the proposed successor does NOT widen v2 (its immediate
        # predecessor): same population. The block is the stored pair.
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(successor, store=store, log=log, predecessor_id=v2.object_id)
        failure = next(iter(log))
        assert failure.reason == "PAIR_WIDENED_WITHOUT_SUPPORT"
        assert v1.object_id in failure.detail or "v1" in failure.detail
        assert store.find(v2.object_id).status is ObjectStatus.ACTIVE


class TestPopulationAtomicity:
    """A population refusal leaves no trace. [N-10, P-I3]"""

    def _gate_refusal_state(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        return v1, log

    def test_predecessor_stays_active(self, store, allocator):
        """#15 The gate runs before the transition."""
        v1, _ = self._gate_refusal_state(store, allocator)
        assert store.find(v1.object_id).status is ObjectStatus.ACTIVE
        assert store.find(v1.object_id).attributes.status_reason is None

    def test_no_successor_retained(self, store, allocator):
        """#16 Nothing was written: one version, one registered Problem."""
        v1, _ = self._gate_refusal_state(store, allocator)
        lineage = v1.attributes.identity.lineage_id
        assert len(store.versions_of(lineage)) == 1
        assert len(store.problems) == 1

    def test_no_partial_store_state(self, store, allocator):
        """#17 Registry, versions and statuses are bit-for-bit unchanged
        by the refusal."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        before = (
            len(store.problems),
            tuple(
                (v.object_id, v.status) for v in store.versions_of(
                    v1.attributes.identity.lineage_id
                )
            ),
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        after = (
            len(store.problems),
            tuple(
                (v.object_id, v.status) for v in store.versions_of(
                    v1.attributes.identity.lineage_id
                )
            ),
        )
        assert before == after


class TestPopulationStageN10:
    """The stage is deterministic and distinguishable. [N-10]"""

    def test_stage_distinguishable_and_attempted(self, store, allocator):
        """#18 Distinct from every neighbouring stage; the judgement ran
        (attempted), unlike the resolution stages."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
            store=store, log=InferenceLog(),
        ).problem
        # A population refusal...
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        population_failure = next(iter(log))
        # ...versus a chain refusal on the same lineage shape...
        smuggle(store, v1.object_id, ABSENCE_STATEMENT)
        log2 = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V3_STATEMENT, population=NARROW_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log2, predecessor_id=v1.object_id,
            )
        chain_failure = next(iter(log2))
        assert population_failure.stage is not chain_failure.stage
        assert population_failure.stage is InferenceStage.POPULATION_WIDENED_WITHOUT_SUPPORT
        assert population_failure.attempted is True

    def test_refusal_deterministic_across_repetitions(self, store, allocator):
        """#18 Identically-constructed scenarios produce identical
        recorded refusals (fresh store per run, as succession allocates
        once per predecessor)."""
        details = []
        for _ in range(3):
            s = KnowledgeStore()
            a, b = two_independent_facts(s, s.allocator)
            v1 = infer(
                request_over(a.object_id, b.object_id, population=NARROW_POPULATION),
                store=s, log=InferenceLog(),
            ).problem
            log = InferenceLog()
            with pytest.raises(InferenceRefusedError):
                infer(
                    request_over(
                        a.object_id, b.object_id,
                        statement=V2_STATEMENT, population=WIDER_POPULATION,
                        synthesis="Together these Facts show the deficiency as stated.",
                    ),
                    store=s, log=log, predecessor_id=v1.object_id,
                )
            details.append(next(iter(log)).detail)
        assert len(set(details)) == 1


class TestPopulationScope:
    """The engine identifies; it never derives, widens, or ranks."""

    def test_population_carried_exactly_never_derived(self, store, allocator):
        """#19 The successor carries the request's population and estimate
        verbatim; the predecessor's are untouched; the engine contributed
        no population content of its own."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                population=NARROW_POPULATION, population_size_estimate=120,
                existing_workarounds="Manual CSV reconciliation",
            ),
            store=store, log=InferenceLog(),
        ).problem
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT,
                population=NARROW_POPULATION + " with high dispute rates",
                population_size_estimate=90,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.affected_population == NARROW_POPULATION + " with high dispute rates"
        assert outcome.problem.population_size_estimate == 90
        assert store.get_problem(v1.object_id).affected_population == NARROW_POPULATION
        assert store.get_problem(v1.object_id).population_size_estimate == 120

    def test_no_widening_semantics_beyond_the_authoritative_methods(self, store, allocator):
        """Scope: the gate's verdict is exactly widens_population_of's
        verdict -- a lowered estimate and a narrowed text both pass without
        new Facts, and nothing else is consulted."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                population=NARROW_POPULATION, population_size_estimate=500,
            ),
            store=store, log=InferenceLog(),
        ).problem
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT,
                population=NARROW_POPULATION + " with high dispute rates",
                population_size_estimate=10,
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        )
        assert outcome.problem.population_size_estimate == 10
        assert outcome.problem.attributes.version == 2


# ===========================================================================
# T04.1.4 -- F-W1 weight gates at the inference boundary  [C, E, F, G]
# ===========================================================================

class TestWeightCeilingGate:
    """The D-B evidence ceiling, before any state change. [F-W1 R4]

    Facts establish an evidence ceiling; they do not determine the
    asserted weight. A criterion is defensible iff its entries cite Facts
    spanning >= 2 independence keys -- S-4's floor value, uniform for
    every band: a sufficiency condition, never a classifier, never a
    ladder.
    """

    def test_exactly_two_keys_carry_the_heaviest_bands(self, store, allocator):
        """Sufficiency is uniform: the heaviest bands need no more than
        the floor, and the floor is enough for them."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(
            request_over(a.object_id, b.object_id), store=store, log=InferenceLog(),
        )
        assert outcome.problem.severity.band is WeightBand.SEVERE
        assert outcome.problem.frequency.band is WeightBand.RECURRING
        assert store.get_problem(outcome.object_id) is not None

    def test_uncorroborated_severity_refused(self, store, allocator):
        """SEVERE declared by entries citing only one Fact: 1 key, and the
        refusal names the span."""
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    severity=weight(WeightBand.SEVERE, (a.object_id,)),
                ),
                store=store, log=log,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_EXCEEDS_EVIDENCE
        assert failure.reason == "CRITERION_NOT_ATTESTED"
        assert failure.attempted is True
        assert "1 independence key" in failure.detail
        assert "IRREVERSIBLE_HARM" in failure.detail

    def test_uncorroborated_frequency_refused(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    frequency=weight(WeightBand.PERSISTENT, (a.object_id,)),
                ),
                store=store, log=log,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_EXCEEDS_EVIDENCE
        assert failure.reason == "CRITERION_NOT_ATTESTED"
        assert "frequency" in failure.detail

    def test_severity_judged_before_frequency(self, store, allocator):
        """Both axes over-claim: the record reports severity, the first
        axis, matching P-I4's order."""
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    severity=weight(WeightBand.SEVERE, (a.object_id,)),
                    frequency=weight(WeightBand.PERSISTENT, (a.object_id,)),
                ),
                store=store, log=log,
            )
        failure = next(iter(log))
        assert failure.reason == "CRITERION_NOT_ATTESTED"
        assert failure.detail.startswith("severity")

    def test_undeclared_band_criterion_refused(self, store, allocator):
        """Form-valid (axis-coherent) entries that never declare the
        asserted band's own criterion: no evidence-linked backing."""
        a, b = two_independent_facts(store, allocator)
        rating = WeightRating(
            WeightBand.SEVERE, "SEVERE -- asserted",
            (
                WeightContribution(a.object_id, WeightCriterion.COMPOUNDING_COST, "cost"),
                WeightContribution(b.object_id, WeightCriterion.COMPOUNDING_COST, "cost"),
            ),
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id, severity=rating),
                store=store, log=log,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_EXCEEDS_EVIDENCE
        assert failure.reason == "CRITERION_NOT_DECLARED"
        assert "IRREVERSIBLE_HARM" in failure.detail

    def test_surplus_keys_never_raise_or_demand(self, store, allocator):
        """Counts never select a band: with 4 keys available, SEVERE
        citing exactly 2 passes and stays SEVERE; MINOR citing 2 passes
        and stays MINOR. More sources do not mean more weight."""
        facts = tuple(
            write_fact_from(store, allocator, source_identifier=f"src-{i}")
            for i in range(4)
        )
        refs = tuple(f.object_id for f in facts)
        heavy = infer(
            request_over(
                *refs, severity=weight(WeightBand.SEVERE, refs[:2]),
            ),
            store=store, log=InferenceLog(),
        ).problem
        assert heavy.severity.band is WeightBand.SEVERE  # not raised
        light = infer(
            request_over(
                *refs, severity=weight(WeightBand.MINOR, refs[:2]),
            ),
            store=store, log=InferenceLog(),
        ).problem
        assert light.severity.band is WeightBand.MINOR  # never upgraded

    def test_below_ceiling_never_flagged_never_upgraded(self, store, allocator):
        """MINOR over two keys is an under-assertion, not a violation:
        the engine never upgrades an inferer's rating."""
        a, b = two_independent_facts(store, allocator)
        outcome = infer(
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.MINOR, (a.object_id, b.object_id)),
                frequency=weight(WeightBand.EPISODIC, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        )
        assert outcome.problem.severity.band is WeightBand.MINOR
        assert outcome.problem.frequency.band is WeightBand.EPISODIC

    def test_ceiling_refusal_is_atomic(self, store, allocator):
        """The gate runs before composition and before any state change:
        nothing is written, nothing partial remains."""
        a, b = two_independent_facts(store, allocator)
        object_census = lambda s: tuple(
            len(s.objects_of_type(t)) for t in ObjectType
        )
        before = (len(store.problems), object_census(store))
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    severity=weight(WeightBand.SEVERE, (a.object_id,)),
                ),
                store=store, log=log,
            )
        assert (len(store.problems), object_census(store)) == before
        assert log.by_stage()[InferenceStage.WEIGHT_EXCEEDS_EVIDENCE] == 1

    def test_ceiling_stage_distinguishable_and_attempted(self, store, allocator):
        """N-10: a distinct, attempted stage -- unlike the S-4 refusal on
        the same inputs, which is a different judgement."""
        a, b = two_independent_facts(store, allocator)
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    severity=weight(WeightBand.SEVERE, (a.object_id,)),
                ),
                store=store, log=log,
            )
        weight_failure = next(iter(log))
        # A genuine S-4 refusal on the same shape: one Fact's Evidence
        # superseded, so one key remains. A different judgement, a
        # different stage.
        store.transition(
            b.attachments[0].evidence_ref, ObjectStatus.SUPERSEDED, "re-acquired"
        )
        log2 = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(a.object_id, b.object_id),
                store=store, log=log2,
            )
        s4_failure = next(iter(log2))
        assert s4_failure.stage is InferenceStage.INSUFFICIENT_SOURCES
        assert weight_failure.stage is not s4_failure.stage
        assert weight_failure.stage is InferenceStage.WEIGHT_EXCEEDS_EVIDENCE
        assert weight_failure.attempted is True
        assert set(weight_failure.fact_refs) == {a.object_id, b.object_id}


class TestWeightVersionedGate:
    """F-W1 R5: a versioned band increase requires at least one NEW
    supporting Fact cited by the raised rating. [T04.1.4]

    Decreases and justification-only revisions version freely; the
    predecessor stays ACTIVE on every refusal.
    """

    def _v1(self, store, allocator, **overrides):
        a, b = two_independent_facts(store, allocator)
        return a, b, infer(
            request_over(a.object_id, b.object_id, **overrides),
            store=store, log=InferenceLog(),
        ).problem

    def test_increase_with_new_cited_fact_accepted(self, store, allocator):
        """The sanctioned heavier version: the raised rating cites a Fact
        the predecessor did not rest on."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        c = write_fact_from(store, allocator, source_identifier="src-gamma")
        v2 = infer(
            request_over(
                a.object_id, b.object_id, c.object_id,
                statement=V2_STATEMENT,
                severity=weight(WeightBand.SEVERE, (a.object_id, c.object_id)),
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.severity.band is WeightBand.SEVERE
        assert v2.attributes.version == 2
        assert store.get_problem(v1.object_id) is not None  # predecessor intact

    def test_increase_without_new_support_refused(self, store, allocator):
        """Heavier band over the SAME Facts: refused, predecessor stays
        ACTIVE, nothing written."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT,
                    severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id)),
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_INCREASED_WITHOUT_SUPPORT
        assert failure.reason == "NO_ADDITIONAL_SUPPORTING_FACT"
        assert failure.attempted is True
        assert failure.detail.startswith("the successor raises severity")
        assert store.find(v1.object_id).status is ObjectStatus.ACTIVE
        assert len(store.problems) == 1
        lineage = v1.attributes.identity.lineage_id
        assert len(store.versions_of(lineage)) == 1

    def test_increase_citing_only_old_facts_refused(self, store, allocator):
        """The new Fact is carried by the request but NOT cited by the
        raised rating: support must be CITED, not merely present. The
        F-W1 R5 requirement is an evidence-linked justification, not a
        payload count."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        c = write_fact_from(store, allocator, source_identifier="src-gamma")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id, c.object_id,
                    statement=V2_STATEMENT,
                    severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id)),
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_INCREASED_WITHOUT_SUPPORT
        assert store.find(v1.object_id).status is ObjectStatus.ACTIVE

    def test_decrease_is_free(self, store, allocator):
        """A lighter band over the same Facts versions without any new
        support: decreases were never gated."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id),  # SEVERE / RECURRING
            store=store, log=InferenceLog(),
        ).problem
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT,
                severity=weight(WeightBand.MINOR, (a.object_id, b.object_id)),
                frequency=weight(WeightBand.EPISODIC, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.severity.band is WeightBand.MINOR
        assert v2.frequency.band is WeightBand.EPISODIC

    def test_justification_only_frequency_revision_is_free(self, store, allocator):
        """Equal band, changed justification: a justification-only
        revision, not an increase."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id),
            store=store, log=InferenceLog(),
        ).problem
        new_frequency = WeightRating(
            WeightBand.RECURRING, "RECURRING -- now evidenced differently",
            (
                WeightContribution(a.object_id, WeightCriterion.REPETITION, "again"),
                WeightContribution(b.object_id, WeightCriterion.REPETITION, "again"),
            ),
        )
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, frequency=new_frequency,
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.frequency is new_frequency
        assert v2.frequency.band is v1.frequency.band

    def test_frequency_increase_needs_new_support(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                frequency=weight(WeightBand.RECURRING, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT,
                    frequency=weight(WeightBand.PERSISTENT, (a.object_id, b.object_id)),
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_INCREASED_WITHOUT_SUPPORT
        assert failure.detail.startswith("the successor raises frequency")

    def test_axes_gated_independently(self, store, allocator):
        """Severity's increase is justified by a new cited Fact; the
        frequency increase is not: the version is refused for frequency
        alone."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        c = write_fact_from(store, allocator, source_identifier="src-gamma")
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id, c.object_id,
                    statement=V2_STATEMENT,
                    severity=weight(WeightBand.SEVERE, (a.object_id, c.object_id)),
                    frequency=weight(WeightBand.PERSISTENT, (a.object_id, b.object_id)),
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        failure = next(iter(log))
        assert failure.stage is InferenceStage.WEIGHT_INCREASED_WITHOUT_SUPPORT
        assert failure.detail.startswith("the successor raises frequency")

    def test_widening_and_raising_satisfied_by_one_new_fact(self, store, allocator):
        """P-I3 and F-W1 R5 in one version: a wider population AND both
        raised bands, all justified by the same new supporting Fact."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                population=NARROW_POPULATION,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
                frequency=weight(WeightBand.RECURRING, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        c = write_fact_from(store, allocator, source_identifier="src-gamma")
        v2 = infer(
            request_over(
                a.object_id, b.object_id, c.object_id,
                statement=V2_STATEMENT,
                population=WIDER_POPULATION,
                severity=weight(WeightBand.SEVERE, (a.object_id, c.object_id)),
                frequency=weight(WeightBand.PERSISTENT, (b.object_id, c.object_id)),
                synthesis="Together these Facts show the deficiency as stated.",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.severity.band is WeightBand.SEVERE
        assert v2.frequency.band is WeightBand.PERSISTENT
        assert v2.affected_population == WIDER_POPULATION

    def test_versioned_weight_refusal_leaves_no_partial_state(
        self, store, allocator
    ):
        """Bit-for-bit: registry, versions and statuses unchanged by the
        refusal."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        before = (
            len(store.problems),
            tuple(
                (v.object_id, v.status)
                for v in store.versions_of(v1.attributes.identity.lineage_id)
            ),
        )
        log = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT,
                    severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id)),
                ),
                store=store, log=log, predecessor_id=v1.object_id,
            )
        after = (
            len(store.problems),
            tuple(
                (v.object_id, v.status)
                for v in store.versions_of(v1.attributes.identity.lineage_id)
            ),
        )
        assert before == after

    def test_weight_stages_distinguishable_from_population_stage(
        self, store, allocator
    ):
        """N-10: the two T04.1.4 stages are distinct from each other and
        from the T04.1.3 population stage on the same lineage shape."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(
                a.object_id, b.object_id,
                population=NARROW_POPULATION,
                severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
            ),
            store=store, log=InferenceLog(),
        ).problem
        # population refusal (widening, no new Facts; its default SEVERE
        # severity would also fail R5, but the population gate refuses
        # first -- order is part of what this test pins)
        log_p = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    statement=V2_STATEMENT, population=WIDER_POPULATION,
                    synthesis="Together these Facts show the deficiency as stated.",
                ),
                store=store, log=log_p, predecessor_id=v1.object_id,
            )
        # ceiling refusal (standalone, same facts)
        log_c = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    a.object_id, b.object_id,
                    severity=weight(WeightBand.SEVERE, (a.object_id,)),
                ),
                store=store, log=log_c,
            )
        # versioned new-support refusal. A fresh store: a refused
        # post-composition versioned attempt has already consumed this
        # lineage's allocator succession (identity is allocated at
        # composition, before the gates -- pre-existing T04.1.3
        # behaviour, deliberately unchanged), and chains may not branch.
        s2 = KnowledgeStore()
        c, d = two_independent_facts(s2, s2.allocator)
        w1 = infer(
            request_over(
                c.object_id, d.object_id,
                severity=weight(WeightBand.MODERATE, (c.object_id, d.object_id)),
            ),
            store=s2, log=InferenceLog(),
        ).problem
        log_v = InferenceLog()
        with pytest.raises(InferenceRefusedError):
            infer(
                request_over(
                    c.object_id, d.object_id,
                    statement=V3_STATEMENT,
                    severity=weight(WeightBand.SEVERE, (c.object_id, d.object_id)),
                ),
                store=s2, log=log_v, predecessor_id=w1.object_id,
            )
        p = next(iter(log_p))
        c = next(iter(log_c))
        v = next(iter(log_v))
        assert len({p.stage, c.stage, v.stage}) == 3
        assert c.stage is InferenceStage.WEIGHT_EXCEEDS_EVIDENCE
        assert v.stage is InferenceStage.WEIGHT_INCREASED_WITHOUT_SUPPORT
        assert all(f.attempted for f in (p, c, v))

    def test_refusal_deterministic_across_repetitions(self, store, allocator):
        """Identically-constructed scenarios produce identical recorded
        refusals (fresh store per run, as succession allocates once per
        predecessor)."""
        details = []
        for _ in range(3):
            s = KnowledgeStore()
            a, b = two_independent_facts(s, s.allocator)
            v1 = infer(
                request_over(
                    a.object_id, b.object_id,
                    severity=weight(WeightBand.MODERATE, (a.object_id, b.object_id)),
                ),
                store=s, log=InferenceLog(),
            ).problem
            log = InferenceLog()
            with pytest.raises(InferenceRefusedError):
                infer(
                    request_over(
                        a.object_id, b.object_id,
                        statement=V2_STATEMENT,
                        severity=weight(WeightBand.SEVERE, (a.object_id, b.object_id)),
                    ),
                    store=s, log=log, predecessor_id=v1.object_id,
                )
            details.append(next(iter(log)).detail)
        assert len(set(details)) == 1


class TestWeightRequestBoundary:
    """Structured ratings are a request-level requirement. [P-V4, F-W1 R3]"""

    def test_string_weight_rejected_at_construction(self, store, allocator):
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="required as a WeightRating"):
            request_over(a.object_id, b.object_id, severity="HIGH -- prose")
        with pytest.raises(InferenceError, match="required as a WeightRating"):
            request_over(a.object_id, b.object_id, frequency="RECURRENT -- prose")

    def test_phantom_weight_citation_rejected_at_construction(self, store, allocator):
        """A rating may cite no Fact outside the supporting set: held at
        the boundary, never persisted."""
        a, b = two_independent_facts(store, allocator)
        with pytest.raises(InferenceError, match="do not support the hypothesis"):
            request_over(
                a.object_id, b.object_id,
                severity=weight(WeightBand.SEVERE, (a.object_id, "obj-phantom")),
            )
        with pytest.raises(InferenceError, match="do not support the hypothesis"):
            request_over(
                a.object_id, b.object_id,
                frequency=weight(WeightBand.PERSISTENT, ("obj-phantom",)),
            )

    def test_rating_travels_to_the_persisted_problem(self, store, allocator):
        """The engine carries the inferer's ratings verbatim, deriving
        nothing: band, detail and citations all survive the write."""
        a, b = two_independent_facts(store, allocator)
        severity = weight(
            WeightBand.MODERATE, (a.object_id, b.object_id), "compounding costs"
        )
        frequency = weight(
            WeightBand.EPISODIC, (a.object_id, b.object_id), "one-off occurrence"
        )
        problem = infer(
            request_over(
                a.object_id, b.object_id, severity=severity, frequency=frequency,
            ),
            store=store, log=InferenceLog(),
        ).problem
        assert problem.severity is severity
        assert problem.frequency is frequency
        assert problem.severity.cited_facts == frozenset(
            {a.object_id, b.object_id}
        )
