"""Contract tests for the Problem Intelligence engine.

Task: T04.1.1 (standalone inference), T04.1.2 (solution-independence
enforcement across versions)

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

Acceptance criteria under test:
  AC1  sufficiency threshold enforced (S-4 floor, independence-grouped)
  AC2  single-fact restatement rejected (P-V6, both prongs, via acceptance)
  AC3  inference_basis references specific Facts (exact coverage)
  T04.1.2  the versioned path: reformulation supersedes the predecessor,
       and solution-independence is enforced over every existing version
       of the chain before any state changes

Explicitly NOT under test here (later tasks): severity/frequency bands
(T04.1.4), population identification (T04.1.3), deduplication (T04.1.5),
taxonomy (T04.1.6).
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
SEVERITY = "HIGH -- unnoticed loss reaches customers"
FREQUENCY = "RECURRENT -- multiple reporting periods"
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


def request_over(
    *refs: str,
    statement: str = STATEMENT,
    population: str = POPULATION,
    severity: str = SEVERITY,
    frequency: str = FREQUENCY,
    domain: str = DOMAIN,
    synthesis: str = SYNTHESIS,
    confidence: float = 0.7,
    **overrides,
) -> InferenceRequest:
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
                severity=SEVERITY,
                frequency=FREQUENCY,
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
                severity=SEVERITY,
                frequency=FREQUENCY,
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
                severity=SEVERITY,
                frequency=FREQUENCY,
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
                severity=SEVERITY,
                frequency=FREQUENCY,
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
                severity=SEVERITY,
                frequency=FREQUENCY,
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

    def test_no_severity_ranking(self, store, allocator):
        """#32 Severity stays free text, carried unchanged, never
        ordered or ranked (T04.1.4, M-12)."""
        a, b = two_independent_facts(store, allocator)
        v1 = infer(
            request_over(a.object_id, b.object_id, severity="LOW -- minor friction"),
            store=store, log=InferenceLog(),
        ).problem
        v2 = infer(
            request_over(
                a.object_id, b.object_id,
                statement=V2_STATEMENT, severity="CRITICAL -- revenue halting",
            ),
            store=store, log=InferenceLog(), predecessor_id=v1.object_id,
        ).problem
        assert v2.severity == "CRITICAL -- revenue halting"
        assert v1.severity == "LOW -- minor friction"
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
