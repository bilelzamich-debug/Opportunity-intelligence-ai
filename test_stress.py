"""Long-running stress tests.

Architecture References:
- R-1   Objects immutable; chains grow without bound
- R-5   Fact corroboration supersedes on every attachment (long chains)
- I2    object_id never reused; retention is unbounded by design
- N-11  Concurrent acquisition permitted
- N-12  Retention: growth is monotonic

These do NOT run by default. They probe behaviour at volumes and durations
ordinary tests never reach -- the conditions under which the platform will
actually operate.

Run:  pytest -m stress
      pytest -m stress -k chains
"""

from __future__ import annotations

import gc
import random
import threading
import time
import tracemalloc
from datetime import datetime, timedelta, timezone

import pytest

from oip.contract import Confidence, Explanation, LineageRef, UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.identity import BranchingError, IdentityAllocator, ObjectIdentity

pytestmark = pytest.mark.stress

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Large identity chains [R-1, R-5]
# ---------------------------------------------------------------------------

class TestLargeChains:
    def test_chain_of_one_million_versions(self):
        """A heavily corroborated Fact may supersede indefinitely. [R-5]"""
        allocator = IdentityAllocator()
        current = allocator.new_object()
        origin_lineage = current.lineage_id

        for _ in range(1_000_000):
            current = allocator.succeed(current)

        assert current.version == 1_000_001
        assert current.lineage_id == origin_lineage
        assert allocator.chain_length(origin_lineage) == 1_000_001
        assert allocator.issued_count() == 1_000_001

    def test_succession_cost_does_not_degrade_with_depth(self):
        """Cost must stay flat: chains are unbounded under R-1."""
        allocator = IdentityAllocator()
        current = allocator.new_object()
        bucket, samples = 50_000, 8
        timings = []

        for _ in range(samples):
            start = time.perf_counter()
            for _ in range(bucket):
                current = allocator.succeed(current)
            timings.append((time.perf_counter() - start) / bucket)

        first, last = timings[0], timings[-1]
        drift = (last - first) / first * 100
        assert drift < 50.0, (
            f"succession degraded {drift:+.1f}% over {bucket * samples:,} versions"
        )

    def test_many_parallel_chains(self):
        """10k independent chains, each 100 deep, never cross-contaminate."""
        allocator = IdentityAllocator()
        heads = [allocator.new_object() for _ in range(10_000)]
        origins = {h.lineage_id for h in heads}

        for _ in range(100):
            heads = [allocator.succeed(h) for h in heads]

        assert {h.lineage_id for h in heads} == origins
        assert all(h.version == 101 for h in heads)
        assert allocator.issued_count() == 10_000 * 101


# ---------------------------------------------------------------------------
# Prolonged concurrency [N-11]
# ---------------------------------------------------------------------------

class TestProlongedConcurrency:
    def test_sustained_concurrent_allocation(self):
        """16 threads allocating for a sustained period: no collisions."""
        allocator = IdentityAllocator()
        per_thread, threads = 50_000, 16
        collected: list[list[str]] = []
        lock = threading.Lock()
        barrier = threading.Barrier(threads)

        def worker() -> None:
            barrier.wait()
            local = [allocator.new_object().object_id for _ in range(per_thread)]
            with lock:
                collected.append(local)

        pool = [threading.Thread(target=worker) for _ in range(threads)]
        for t in pool:
            t.start()
        for t in pool:
            t.join()

        flat = [oid for batch in collected for oid in batch]
        assert len(flat) == threads * per_thread
        assert len(set(flat)) == len(flat), "collision under sustained concurrency"
        assert allocator.issued_count() == len(flat)

    def test_concurrent_succession_never_branches(self):
        """Many threads racing on many chains: exactly one winner per version."""
        allocator = IdentityAllocator()
        chains = [allocator.new_object() for _ in range(200)]
        wins: list[int] = []
        lock = threading.Lock()

        def worker(head: ObjectIdentity) -> None:
            won = 0
            for _ in range(20):
                try:
                    allocator.succeed(head)
                    won += 1
                except BranchingError:
                    pass
            with lock:
                wins.append(won)

        pool = [
            threading.Thread(target=worker, args=(chain,))
            for chain in chains
            for _ in range(6)
        ]
        for t in pool:
            t.start()
        for t in pool:
            t.join()

        # Each of the 200 heads may be succeeded exactly once, total.
        assert sum(wins) == len(chains), (
            f"expected exactly {len(chains)} successions, got {sum(wins)}"
        )

    def test_mixed_concurrent_workload(self):
        """Allocation, succession, and lookups interleaved under contention."""
        allocator = IdentityAllocator()
        seed = [allocator.new_object() for _ in range(500)]
        errors: list[str] = []
        lock = threading.Lock()
        stop = time.perf_counter() + 5.0

        def allocate() -> None:
            while time.perf_counter() < stop:
                allocator.new_object()

        def look_up() -> None:
            rng = random.Random(7)
            while time.perf_counter() < stop:
                identity = rng.choice(seed)
                if allocator.lineage_of(identity.object_id) != identity.lineage_id:
                    with lock:
                        errors.append("lineage_of returned wrong lineage")

        def check_reuse() -> None:
            rng = random.Random(11)
            while time.perf_counter() < stop:
                identity = rng.choice(seed)
                try:
                    allocator.assert_not_reused(identity.object_id)
                except Exception:
                    continue
                with lock:
                    errors.append("issued id not reported as reused")

        pool = [threading.Thread(target=fn) for fn in (allocate, look_up, check_reuse)
                for _ in range(4)]
        for t in pool:
            t.start()
        for t in pool:
            t.join()

        assert not errors, errors[:5]


# ---------------------------------------------------------------------------
# High-volume allocation [I2, N-12]
# ---------------------------------------------------------------------------

class TestHighVolume:
    def test_two_million_allocations_stay_unique(self):
        allocator = IdentityAllocator()
        seen: set[str] = set()
        for _ in range(2_000_000):
            seen.add(allocator.new_object().object_id)
        assert len(seen) == 2_000_000

    def test_memory_growth_is_linear_not_quadratic(self):
        """I2 retains every id forever; growth must stay proportional. [N-12]"""
        allocator = IdentityAllocator()
        gc.collect()
        tracemalloc.start()

        def grow_to(target: int) -> float:
            while allocator.issued_count() < target:
                allocator.new_object()
            return tracemalloc.get_traced_memory()[0]

        at_250k = grow_to(250_000)
        at_500k = grow_to(500_000)
        at_1m = grow_to(1_000_000)
        tracemalloc.stop()

        # Doubling the population should roughly double memory, not quadruple.
        ratio_1 = at_500k / at_250k
        ratio_2 = at_1m / at_500k
        assert 1.5 < ratio_1 < 3.0, f"non-linear growth: {ratio_1:.2f}x"
        assert 1.5 < ratio_2 < 3.0, f"non-linear growth: {ratio_2:.2f}x"

    def test_lookup_stays_flat_at_two_million(self):
        allocator = IdentityAllocator()
        ids = [allocator.new_object().object_id for _ in range(2_000_000)]

        sample = random.Random(3).sample(ids, 50_000)
        start = time.perf_counter()
        for oid in sample:
            allocator.lineage_of(oid)
        per_op = (time.perf_counter() - start) / len(sample) * 1_000_000

        assert per_op < 10.0, f"lookup degraded to {per_op:.2f}us at 2M entries"


# ---------------------------------------------------------------------------
# Contract construction at volume
# ---------------------------------------------------------------------------

class TestContractVolume:
    def test_high_volume_object_construction(self):
        """100k full contract objects: validation holds throughout."""
        allocator = IdentityAllocator()
        explanation = Explanation(
            objects_referenced=("obj-ev-1",),
            criteria_applied=("threshold",),
            reasoning="volume test",
        )
        confidence = Confidence.create(0.6, 0.7)
        refs = (LineageRef("obj-ev-1", ObjectType.EVIDENCE),)

        for _ in range(100_000):
            attrs = UniversalAttributes(
                identity=allocator.new_object(),
                object_type=ObjectType.FACT,
                produced_by_engine=Engine.FACT_EXTRACTION,
                produced_at=T0 + timedelta(hours=2),
                engine_configuration_ref="cfg-v1",
                derives_from=refs,
                explanation=explanation,
                evidence_reachable=True,
                confidence=confidence,
                asserted_at=T0 + timedelta(hours=1),
                observed_at=T0,
                status=ObjectStatus.ACTIVE,
            )
            assert attrs.confidence.effective_confidence <= 0.6

    def test_deep_confidence_chain_never_inflates(self):
        """1000 inferential steps cannot manufacture certainty. [R-3]"""
        ceiling = 0.62
        for _ in range(1000):
            confidence = Confidence.create(0.99, 0.99, upstream_ceiling=ceiling)
            assert confidence.effective_confidence <= ceiling + 1e-9
            ceiling = confidence.effective_confidence

        assert ceiling == pytest.approx(0.62)


# ---------------------------------------------------------------------------
# Cascade invalidation at volume  [T01.2.3, I6, N-9]
# ---------------------------------------------------------------------------

class TestCascadeStress:
    def _store(self):
        from oip.store import KnowledgeStore
        from oip.identity import IdentityAllocator
        return KnowledgeStore(), IdentityAllocator()

    def test_deep_chain_to_the_traversal_bound(self):
        """Termination over a chain at the graph's traversal bound.

        MAX_LINEAGE_DEPTH (32) is a deliberate safety net -- real pipeline
        depth is 8 -- and V4 correctly refuses writes beyond it, since
        Evidence would no longer be reachable within the bound. This probes
        cascade right up to that limit.
        """
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from oip.graph import MAX_LINEAGE_DEPTH
        from tests.conftest import write_derived, write_evidence

        store, allocator = self._store()
        evidence = write_evidence(store, allocator)
        current = evidence
        depth = MAX_LINEAGE_DEPTH - 2
        for _ in range(depth):
            current = write_derived(store, allocator, ObjectType.FACT, [current])

        operation = CascadeInvalidation(store=store, max_depth=MAX_LINEAGE_DEPTH * 2)
        result = operation.retract(evidence.object_id, "withdrawn")

        assert result.completed
        assert result.changed == depth
        assert store.get(current.object_id).status is ObjectStatus.INVALIDATED

    def test_many_independent_deep_chains(self):
        """Volume via breadth of deep chains rather than one illegal chain."""
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectType
        from tests.conftest import write_derived, write_evidence

        store, allocator = self._store()
        evidence = write_evidence(store, allocator)
        for _ in range(200):
            current = evidence
            for _ in range(8):
                current = write_derived(
                    store, allocator, ObjectType.FACT, [current]
                )

        result = CascadeInvalidation(store=store).retract(
            evidence.object_id, "withdrawn"
        )
        assert result.completed
        assert result.changed == 1_600

    def test_wide_fan_out_of_ten_thousand(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.conftest import write_derived, write_evidence

        store, allocator = self._store()
        evidence = write_evidence(store, allocator)
        for _ in range(10_000):
            write_derived(store, allocator, ObjectType.FACT, [evidence])

        result = CascadeInvalidation(store=store).retract(
            evidence.object_id, "withdrawn"
        )
        assert result.changed == 10_000
        assert not [
            oid
            for oid in store.graph.descendants(evidence.object_id)
            if store.get(oid).status is ObjectStatus.ACTIVE
        ]

    def test_dense_diamond_lattice_visits_each_node_once(self):
        """Exponential path count, linear visit count -- the visited set holds."""
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectType
        from tests.conftest import write_derived, write_evidence

        store, allocator = self._store()
        evidence = write_evidence(store, allocator)
        layer = [
            write_derived(store, allocator, ObjectType.FACT, [evidence])
            for _ in range(6)
        ]
        for _ in range(4):
            layer = [
                write_derived(store, allocator, ObjectType.FACT, layer)
                for _ in range(6)
            ]

        operation = CascadeInvalidation(store=store)
        plan = operation.plan(evidence.object_id)
        assert len(plan) == len(set(plan)) == 30
        assert operation.retract(evidence.object_id, "withdrawn").changed == 30

    def test_repeated_cascade_stays_constant(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.conftest import write_derived, write_evidence

        store, allocator = self._store()
        evidence = write_evidence(store, allocator)
        for _ in range(500):
            write_derived(store, allocator, ObjectType.FACT, [evidence])

        operation = CascadeInvalidation(store=store)
        first = operation.retract(evidence.object_id, "withdrawn")
        for _ in range(20):
            repeat = operation.cascade(
                evidence.object_id, ObjectStatus.RETRACTED, "withdrawn"
            )
            assert repeat.changed == 0
            assert len(repeat.already_terminal) == first.changed


# ---------------------------------------------------------------------------
# Evidence at volume  [T01.7.1, E-V6, N-16]
# ---------------------------------------------------------------------------

class TestEvidenceStress:
    def _mk(self, allocator, content, source="src-A", **kw):
        from datetime import timedelta
        from oip.evidence import Evidence, EvidenceContent, Provenance
        from oip.enums import ObjectStatus, ObjectType
        from tests.conftest import T0, build_attrs

        return Evidence(
            attributes=build_attrs(
                allocator.new_object(), ObjectType.EVIDENCE,
                status=ObjectStatus.ACTIVE, status_reason=None,
            ),
            provenance=Provenance(
                source_identifier=source,
                source_type="corpus",
                acquisition_method="bulk",
                acquired_at=T0 + timedelta(hours=2),
                access_conditions="licensed",
                capture_fidelity="full",
                **kw,
            ),
            content=EvidenceContent.full(content),
        )

    def test_fifty_thousand_acquisitions_stay_unique(self):
        """E-V6 duplicate detection must stay correct and flat at volume."""
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore

        store, allocator = KnowledgeStore(), IdentityAllocator()
        for i in range(50_000):
            store.write_evidence(self._mk(allocator, f"unique-{i}"))

        assert len(store) == 50_000
        assert len(store.evidence) == 50_000

    def test_duplicate_detection_flat_at_scale(self):
        import time
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore, WriteRejectedError

        store, allocator = KnowledgeStore(), IdentityAllocator()
        for i in range(20_000):
            store.write_evidence(self._mk(allocator, f"text-{i}"))

        start = time.perf_counter()
        for i in range(0, 20_000, 2_000):
            try:
                store.write_evidence(self._mk(allocator, f"text-{i}"))
                raise AssertionError("duplicate accepted")
            except WriteRejectedError:
                pass
        per_check = (time.perf_counter() - start) / 10 * 1_000
        assert per_check < 50.0, f"duplicate check degraded to {per_check:.1f}ms"

    def test_independence_grouping_at_volume(self):
        """N-16: syndicated sources collapse to one independent source."""
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore

        store, allocator = KnowledgeStore(), IdentityAllocator()
        for i in range(5_000):
            store.write_evidence(
                self._mk(
                    allocator, f"syndicated-{i}", source=f"src-{i}",
                    source_independence_group="syndicate-1",
                )
            )
        for i in range(50):
            store.write_evidence(
                self._mk(allocator, f"independent-{i}", source=f"indep-{i}")
            )
        assert len(store.evidence.independent_sources()) == 51

    def test_evidence_integrity_audit_at_volume(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore

        store, allocator = KnowledgeStore(), IdentityAllocator()
        for i in range(10_000):
            store.write_evidence(self._mk(allocator, f"text-{i}"))
        assert store.evidence.integrity().verify() == ()
        assert store.verify_integrity().holds


# ---------------------------------------------------------------------------
# Facts at volume  [T01.7.2, R-5, S-3]
# ---------------------------------------------------------------------------

class TestFactStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _evidence(self, store, allocator, n):
        from tests.test_evidence import evidence as mk
        return [
            store.write_evidence(
                mk(allocator, content=f"text-{i}", source_identifier=f"src-{i}")
            )
            for i in range(n)
        ]

    def test_fact_with_one_thousand_attachments(self):
        """R-5: corroboration breadth must not degrade the canonical claim."""
        from oip.enums import ObjectType
        from tests.test_fact import make_fact

        store, allocator = self._setup()
        sources = self._evidence(store, allocator, 1_000)
        ceiling = min(
            e.attributes.confidence.effective_confidence for e in sources
        )
        fact = make_fact(
            allocator,
            tuple(e.object_id for e in sources),
            upstream_ceiling=ceiling,
        )
        assert fact.attachment_count == 1_000
        assert fact.independent_source_count == 1_000

    def test_long_corroboration_chain(self):
        """Each merge produces a version; chains may be long. [R-5, R-1]"""
        from oip.claim import Verdict
        from oip.fact import MergeJustification
        from tests.conftest import T0
        from tests.test_fact import attachment, make_fact

        allocator = self._setup()[1]
        fact = make_fact(allocator)
        for i in range(2, 2_002):
            fact = fact.with_attachment(
                attachment(f"obj-ev-{i}"),
                MergeJustification(
                    Verdict.EQUIVALENT, "agreed", f"obj-ev-{i}", T0
                ),
            )
        assert fact.attachment_count == 2_001
        assert len(fact.merge_history) == 2_000

    def test_equivalence_search_at_scale(self):
        """S-3 resolution must stay usable as the Fact population grows."""
        import time
        from oip.claim import Claim
        from tests.test_fact import make_fact, write_fact_from

        store, allocator = self._setup()
        sources = self._evidence(store, allocator, 400)
        for i, source in enumerate(sources):
            write_fact_from(
                store, allocator, [source],
                claim=Claim(f"subject-{i}", "predicate", "qualifier"),
            )

        start = time.perf_counter()
        for i in range(0, 400, 40):
            assert store.facts.find_equivalent(
                Claim(f"subject-{i}", "predicate", "qualifier")
            ) is not None
        per_query = (time.perf_counter() - start) / 10 * 1_000
        assert per_query < 500.0, f"equivalence search degraded: {per_query:.1f}ms"

    def test_fact_integrity_audit_at_volume(self):
        from tests.test_fact import write_fact_from

        store, allocator = self._setup()
        sources = self._evidence(store, allocator, 500)
        for source in sources:
            write_fact_from(store, allocator, [source])
        assert store.facts.integrity().verify() == ()
        assert store.verify_integrity().holds


# ---------------------------------------------------------------------------
# Problems at volume  [T01.7.3, P-V1..P-V6, P-I1..P-I4, S-4]
# ---------------------------------------------------------------------------

class TestProblemStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _facts(self, store, allocator, n):
        from tests.test_problem import write_facts
        return write_facts(store, allocator, n)

    def test_problem_resting_on_one_thousand_facts(self):
        """Fan-in is unbounded; P-V1/P-V5 must not degrade with breadth."""
        from tests.test_problem import basis, make_problem

        store, allocator = self._setup()
        facts = self._facts(store, allocator, 1_000)
        refs = tuple(f.object_id for f in facts)
        problem = make_problem(
            allocator, refs,
            upstream_ceiling=min(
                f.attributes.confidence.effective_confidence for f in facts
            ),
            inference_basis=basis(*refs),
        )
        stored = store.write_problem(problem)
        assert store.get_problem(stored.object_id).supporting_fact_count == 1_000
        assert len(store.graph.evidence_set(stored.object_id)) == 1_000

    def test_ten_thousand_problems_stay_consistent(self):
        from oip.enums import ObjectType
        from tests.test_problem import write_problem_from

        store, allocator = self._setup()
        facts = self._facts(store, allocator, 2)
        for _ in range(10_000):
            write_problem_from(store, allocator, facts)

        assert len(store.problems) == 10_000
        assert len(store.objects_of_type(ObjectType.PROBLEM)) == 10_000

    def test_problem_integrity_audit_at_volume(self):
        from tests.test_problem import write_problem_from

        store, allocator = self._setup()
        for _ in range(500):
            facts = self._facts(store, allocator, 2)
            write_problem_from(store, allocator, facts)
        assert store.problems.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_solution_detection_stays_flat_on_long_statements(self):
        """P-V2 scans the whole statement; cost must stay usable."""
        import time
        from oip.problem import detect_solution_language

        long_statement = ("sellers lose work without notification. " * 5_000)
        start = time.perf_counter()
        for _ in range(20):
            assert detect_solution_language(long_statement) == ()
        per_scan = (time.perf_counter() - start) / 20 * 1_000
        assert per_scan < 250.0, f"P-V2 scan degraded to {per_scan:.1f}ms"

    def test_long_supersession_chain_of_problems(self):
        """P-I1/P-I3 are checked pairwise across a whole lineage."""
        from oip.enums import ObjectStatus
        from tests.test_problem import write_problem_from

        store, allocator = self._setup()
        facts = self._facts(store, allocator, 2)
        current = write_problem_from(store, allocator, facts)
        for _ in range(300):
            store.transition(
                current.object_id, ObjectStatus.SUPERSEDED, "reformulated"
            )
            identity = allocator.succeed(current.attributes.identity)
            current = write_problem_from(
                store, allocator, facts,
                identity=identity, predecessor_id=current.object_id,
            )
        assert current.attributes.version == 301
        assert store.problems.integrity().verify() == ()

    def test_cascade_reaches_problems_at_depth(self):
        """I6: retracting Evidence must invalidate every dependent Problem."""
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_problem import write_problem_from

        store, allocator = self._setup()
        facts = self._facts(store, allocator, 2)
        for _ in range(300):
            write_problem_from(store, allocator, facts)

        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.PROBLEM)
        )


# ---------------------------------------------------------------------------
# Patterns at volume  [T01.7.4, PT-V1..PT-V6, PT-I1..PT-I4, S-4, M-66]
# ---------------------------------------------------------------------------

class TestPatternStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _problems(self, store, allocator, n):
        from tests.test_pattern import write_problems
        return write_problems(store, allocator, n)

    def test_pattern_over_two_hundred_constituents(self):
        """Fan-in is large by design; PT-V1/PT-V3/PT-V6 must not degrade."""
        from tests.test_pattern import rationale, make_pattern

        store, allocator = self._setup()
        problems = self._problems(store, allocator, 200)
        refs = tuple(p.object_id for p in problems)
        pattern = make_pattern(
            allocator, refs,
            upstream_ceiling=min(
                p.attributes.confidence.effective_confidence for p in problems
            ),
            grouping_rationale=rationale(*refs),
            source_diversity=len(store.graph.evidence_set(refs[0])) * 0,
        )
        stored = store.write_pattern(pattern)
        assert store.get_pattern(stored.object_id).constituent_count == 200
        # Transitive evidence set is large by design. [M-66]
        assert len(store.graph.evidence_set(stored.object_id)) == 400

    def test_pattern_integrity_audit_at_volume(self):
        from tests.test_pattern import write_pattern_from

        store, allocator = self._setup()
        for _ in range(100):
            problems = self._problems(store, allocator, 2)
            write_pattern_from(store, allocator, problems)
        assert store.patterns.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_ptv2_lineage_check_flat_at_scale(self):
        """PT-V2 groups by lineage; cost must stay usable at wide membership."""
        import time
        from oip.acceptance import AcceptanceContext
        from oip.pattern import ptv2_constituents_are_distinct_objects
        from tests.test_pattern import make_pattern, rationale

        allocator = self._setup()[1]
        refs = tuple(f"obj-pr-{i}" for i in range(2_000))
        pattern = make_pattern(
            allocator, refs, grouping_rationale=rationale(*refs[:5])
        )
        lineages = {r: f"lin-{i}" for i, r in enumerate(refs)}
        ctx = AcceptanceContext(
            attributes=pattern.attributes, pattern=pattern,
            resolve_lineage=lineages.get,
        )
        start = time.perf_counter()
        for _ in range(20):
            assert not ptv2_constituents_are_distinct_objects(ctx).failed
        per_check = (time.perf_counter() - start) / 20 * 1_000
        assert per_check < 250.0, f"PT-V2 degraded to {per_check:.1f}ms"

    def test_open_ended_membership_churn(self):
        """Membership is open-ended, producing long version chains. [OQ-21]"""
        from oip.enums import ObjectStatus
        from tests.test_pattern import write_pattern_from

        store, allocator = self._setup()
        problems = self._problems(store, allocator, 2)
        current = write_pattern_from(store, allocator, problems)
        for _ in range(200):
            store.transition(
                current.object_id, ObjectStatus.SUPERSEDED, "constituent added"
            )
            identity = allocator.succeed(current.attributes.identity)
            current = write_pattern_from(
                store, allocator, problems,
                identity=identity, predecessor_id=current.object_id,
            )
        assert current.attributes.version == 201
        assert store.patterns.integrity().verify() == ()

    def test_cascade_reaches_patterns_at_depth_three(self):
        """I6: retracting Evidence must invalidate Patterns three stages up."""
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_pattern import write_pattern_from

        store, allocator = self._setup()
        problems = self._problems(store, allocator, 2)
        for _ in range(100):
            write_pattern_from(store, allocator, problems)

        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.PATTERN)
        )

    def test_deep_evidence_set_remains_computable(self):
        """M-66: sets may reach thousands; only cardinality is used here."""
        from tests.test_pattern import write_pattern_from

        store, allocator = self._setup()
        problems = self._problems(store, allocator, 60)
        stored = write_pattern_from(store, allocator, problems)
        assert len(store.graph.evidence_set(stored.object_id)) == 120
        assert store.patterns.integrity().verify() == ()


# ---------------------------------------------------------------------------
# Opportunities at volume  [T01.7.5, O-V1..O-V7, O-I1..O-I4]
# ---------------------------------------------------------------------------

class TestOpportunityStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _patterns(self, store, allocator, n):
        from tests.test_opportunity import write_patterns
        return write_patterns(store, allocator, n)

    def test_five_hundred_opportunities_stay_consistent(self):
        from oip.enums import ObjectType
        from tests.test_opportunity import write_opportunity_from

        store, allocator = self._setup()
        patterns = self._patterns(store, allocator, 1)
        for _ in range(500):
            write_opportunity_from(store, allocator, patterns)
        assert len(store.opportunities) == 500
        assert len(store.objects_of_type(ObjectType.OPPORTUNITY)) == 500

    def test_opportunity_integrity_audit_at_volume(self):
        from tests.test_opportunity import write_opportunity_from

        store, allocator = self._setup()
        for _ in range(60):
            patterns = self._patterns(store, allocator, 1)
            write_opportunity_from(store, allocator, patterns)
        assert store.opportunities.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_ranking_flat_at_scale(self):
        """O-I3: ranking one cohort must stay usable as the population grows."""
        import time
        from tests.test_opportunity import score, write_opportunity_from

        store, allocator = self._setup()
        patterns = self._patterns(store, allocator, 1)
        for i in range(400):
            write_opportunity_from(
                store, allocator, patterns,
                score=score(value=(i % 100) / 100.0),
                scoring_explanation="reach dominates the assessment",
            )
        start = time.perf_counter()
        for _ in range(10):
            ranked = store.opportunities.rank_within("score-model-v1")
        per_rank = (time.perf_counter() - start) / 10 * 1_000
        assert len(ranked) == 400
        assert per_rank < 250.0, f"ranking degraded to {per_rank:.1f}ms"

    def test_rescoring_chain_preserves_every_prediction(self):
        """O-I4: history must remain intact across a long rescoring chain."""
        from oip.enums import ObjectStatus
        from tests.test_opportunity import score, write_opportunity_from

        store, allocator = self._setup()
        patterns = self._patterns(store, allocator, 1)
        current = write_opportunity_from(store, allocator, patterns)
        fingerprints = [store.get_opportunity(current.object_id).score_fingerprint()]

        for i in range(150):
            store.transition(current.object_id, ObjectStatus.SUPERSEDED, "rescored")
            identity = allocator.succeed(current.attributes.identity)
            current = write_opportunity_from(
                store, allocator, patterns,
                identity=identity, predecessor_id=current.object_id,
                score=score(value=(i % 90) / 100.0),
                scoring_explanation="reach dominates the assessment",
            )
            fingerprints.append(
                store.get_opportunity(current.object_id).score_fingerprint()
            )

        assert current.attributes.version == 151
        assert store.opportunities.integrity().verify() == ()
        assert len(fingerprints) == 151

    def test_rejected_population_retained_at_volume(self):
        """D-02: declined candidates are the Feedback Engine's signal."""
        from oip.enums import ObjectStatus
        from tests.test_opportunity import write_opportunity_from

        store, allocator = self._setup()
        patterns = self._patterns(store, allocator, 1)
        for i in range(300):
            write_opportunity_from(
                store, allocator, patterns,
                scored=False,
                status=ObjectStatus.REJECTED,
                status_reason="below viability",
                rejection_rationale=f"declined on iteration {i}",
            )
        assert len(store.opportunities.rejected_opportunities()) == 300
        assert store.verify_integrity().holds

    def test_cascade_reaches_opportunities_at_depth_four(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_opportunity import write_opportunity_from

        store, allocator = self._setup()
        patterns = self._patterns(store, allocator, 1)
        for _ in range(100):
            write_opportunity_from(store, allocator, patterns)

        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.OPPORTUNITY)
        )


# ---------------------------------------------------------------------------
# Solutions at volume  [T01.7.6, S-V1..S-V6, S-I1..S-I4]
# ---------------------------------------------------------------------------

class TestSolutionStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _opportunity(self, store, allocator):
        from tests.test_solution import write_opportunities
        return write_opportunities(store, allocator, 1)[0]

    def test_solution_with_five_hundred_assumptions(self):
        """The testable surface may be wide; S-V3 must not degrade."""
        from tests.test_solution import assumption, write_solution_from

        store, allocator = self._setup()
        opportunity = self._opportunity(store, allocator)
        many = tuple(assumption(f"A{i}") for i in range(500))
        stored = write_solution_from(
            store, allocator, opportunity, assumptions=many
        )
        assert len(store.solutions.testable_surface(stored.object_id)) == 500

    def test_three_hundred_sibling_candidates_coexist(self):
        """S-I3: premature convergence is the failure, not breadth."""
        from tests.test_solution import write_solution_from

        store, allocator = self._setup()
        opportunity = self._opportunity(store, allocator)
        for _ in range(300):
            write_solution_from(store, allocator, opportunity)
        assert len(store.solutions.candidates_for(opportunity.object_id)) == 300
        assert store.solutions.integrity().verify() == ()

    def test_solution_integrity_audit_at_volume(self):
        from tests.test_solution import write_solution_from

        store, allocator = self._setup()
        for _ in range(40):
            opportunity = self._opportunity(store, allocator)
            write_solution_from(store, allocator, opportunity)
        assert store.solutions.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_long_refinement_chain(self):
        """Assumption refinement drives Solution versioning. [R-1, S-I1]"""
        from oip.enums import ObjectStatus
        from tests.test_solution import assumption, write_solution_from

        store, allocator = self._setup()
        opportunity = self._opportunity(store, allocator)
        current = write_solution_from(store, allocator, opportunity)
        for i in range(150):
            store.transition(
                current.object_id, ObjectStatus.SUPERSEDED, "assumptions refined"
            )
            identity = allocator.succeed(current.attributes.identity)
            current = write_solution_from(
                store, allocator, opportunity,
                identity=identity, predecessor_id=current.object_id,
                assumptions=tuple(assumption(f"A{j}") for j in range(i + 2)),
            )
        assert current.attributes.version == 151
        assert store.solutions.integrity().verify() == ()

    def test_sibling_lookup_flat_at_scale(self):
        import time
        from tests.test_solution import write_solution_from

        store, allocator = self._setup()
        opportunity = self._opportunity(store, allocator)
        stored = [
            write_solution_from(store, allocator, opportunity) for _ in range(400)
        ]
        start = time.perf_counter()
        for _ in range(10):
            siblings = store.solutions.siblings_of(stored[0].object_id)
        per_lookup = (time.perf_counter() - start) / 10 * 1_000
        assert len(siblings) == 399
        assert per_lookup < 250.0, f"sibling lookup degraded to {per_lookup:.1f}ms"

    def test_cascade_reaches_solutions_at_depth_five(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_solution import write_solution_from

        store, allocator = self._setup()
        opportunity = self._opportunity(store, allocator)
        for _ in range(100):
            write_solution_from(store, allocator, opportunity)

        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.SOLUTION)
        )


# ---------------------------------------------------------------------------
# Validations at volume  [T01.7.7, V-V1..V-V6, V-I1..V-I4]
# ---------------------------------------------------------------------------

class TestValidationStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _solution(self, store, allocator, claims=8):
        from tests.test_solution import assumption
        from tests.test_validation import write_solutions
        return write_solutions(
            store, allocator, 1,
            assumptions=tuple(assumption(f"A{i}") for i in range(claims)),
        )[0]

    def test_many_validations_per_solution(self):
        """Claim-level targeting multiplies Validations. [V-V1]"""
        from tests.test_validation import write_validation_from

        store, allocator = self._setup()
        solution = self._solution(store, allocator, claims=200)
        for i in range(200):
            write_validation_from(store, allocator, solution, claim_id=f"A{i}")
        assert len(store.validations.for_object(solution.object_id)) == 200
        assert store.validations.integrity().verify() == ()

    def test_negative_results_survive_at_volume(self):
        """V-I1: suppression must remain impossible however many there are."""
        from oip.validation import ValidationResult
        from tests.test_validation import write_validation_from

        store, allocator = self._setup()
        solution = self._solution(store, allocator, claims=2)
        for _ in range(300):
            write_validation_from(
                store, allocator, solution,
                result=ValidationResult.NOT_SUPPORTED,
            )
        assert len(store.validations.negative_results()) == 300
        assert store.validations.integrity().verify() == ()

    def test_conflict_detection_flat_at_scale(self):
        import time
        from oip.validation import ValidationResult
        from tests.test_validation import write_validation_from

        store, allocator = self._setup()
        solution = self._solution(store, allocator, claims=2)
        for i in range(120):
            write_validation_from(
                store, allocator, solution,
                result=(
                    ValidationResult.SUPPORTED if i % 2
                    else ValidationResult.NOT_SUPPORTED
                ),
            )
        start = time.perf_counter()
        for _ in range(5):
            conflicts = store.validations.conflicts_for(solution.object_id, "A1")
        per_query = (time.perf_counter() - start) / 5 * 1_000
        assert len(conflicts) == 60 * 60
        assert per_query < 500.0, f"conflict scan degraded to {per_query:.1f}ms"

    def test_validation_integrity_audit_at_volume(self):
        from tests.test_validation import write_validation_from

        store, allocator = self._setup()
        for _ in range(40):
            solution = self._solution(store, allocator, claims=2)
            write_validation_from(store, allocator, solution, claim_id="A1")
        assert store.validations.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_untested_claim_reporting_at_scale(self):
        from tests.test_validation import write_validation_from

        store, allocator = self._setup()
        solution = self._solution(store, allocator, claims=500)
        for i in range(0, 500, 2):
            write_validation_from(store, allocator, solution, claim_id=f"A{i}")
        untested = store.validations.untested_claims(
            solution.object_id, tuple(f"A{i}" for i in range(500))
        )
        assert len(untested) == 250

    def test_cascade_reaches_validations_at_depth_six(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_validation import write_validation_from

        store, allocator = self._setup()
        solution = self._solution(store, allocator, claims=2)
        for _ in range(100):
            write_validation_from(store, allocator, solution)

        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.VALIDATION)
        )


# ---------------------------------------------------------------------------
# Execution Records at volume  [T01.7.8, X-V1..X-V6, X-I1..X-I4, C-02]
# ---------------------------------------------------------------------------

class TestExecutionStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def test_c02_refusal_holds_at_volume(self):
        """C-02 must not degrade into an accidental acceptance under load."""
        from oip.store import WriteRejectedError
        from tests.test_execution import (record_for, solution_and_opportunity)

        store, allocator = self._setup()
        solution, opportunity = solution_and_opportunity(store, allocator)
        refusals = 0
        for _ in range(2_000):
            try:
                store.write_execution_record(
                    record_for(store, allocator, solution, opportunity)
                )
            except WriteRejectedError as exc:
                assert "V7" in exc.value.rule_ids if hasattr(exc, "value") else True
                refusals += 1
        assert refusals == 2_000
        assert len(store.executions) == 0

    def test_many_outcomes_per_solution(self):
        """Outcomes accumulate over extended periods. [IOM section 3.8]"""
        from tests.test_execution import (force_persist, record_for,
                                          solution_and_opportunity)

        store, allocator = self._setup()
        solution, opportunity = solution_and_opportunity(store, allocator)
        for _ in range(500):
            force_persist(
                store, record_for(store, allocator, solution, opportunity)
            )
        assert len(store.executions.for_solution(solution.object_id)) == 500
        assert store.executions.integrity().verify() == ()

    def test_unfavourable_outcomes_survive_at_volume(self):
        """X-I1: survivorship bias must stay impossible however many there are."""
        from oip.execution import OutcomeValence
        from tests.test_execution import (force_persist, record_for,
                                          solution_and_opportunity)

        store, allocator = self._setup()
        solution, opportunity = solution_and_opportunity(store, allocator)
        for _ in range(300):
            force_persist(
                store,
                record_for(
                    store, allocator, solution, opportunity,
                    valence=OutcomeValence.UNFAVOURABLE,
                ),
            )
        assert len(store.executions.unfavourable_outcomes()) == 300
        assert store.executions.integrity().verify() == ()

    def test_integrity_audit_at_volume(self):
        from tests.test_execution import (force_persist, record_for,
                                          solution_and_opportunity)

        store, allocator = self._setup()
        for _ in range(40):
            solution, opportunity = solution_and_opportunity(store, allocator)
            force_persist(
                store, record_for(store, allocator, solution, opportunity)
            )
        assert store.executions.integrity().verify() == ()
        assert store.verify_integrity().holds

    def test_long_outcome_accumulation_chain(self):
        """The object most subject to temporal spread. [IOM section 3.8]"""
        from oip.enums import ObjectStatus
        from tests.test_execution import (force_persist, record_for,
                                          solution_and_opportunity)

        store, allocator = self._setup()
        solution, opportunity = solution_and_opportunity(store, allocator)
        current = force_persist(
            store, record_for(store, allocator, solution, opportunity)
        )
        for _ in range(150):
            store.transition(
                current.object_id, ObjectStatus.SUPERSEDED, "further outcomes"
            )
            identity = allocator.succeed(current.attributes.identity)
            current = force_persist(
                store,
                record_for(
                    store, allocator, solution, opportunity, identity=identity
                ),
            )
        assert current.attributes.version == 151
        assert store.executions.integrity().verify() == ()

    def test_cascade_reaches_records_at_depth(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_execution import (force_persist, record_for,
                                          solution_and_opportunity)

        store, allocator = self._setup()
        solution, opportunity = solution_and_opportunity(store, allocator)
        for _ in range(100):
            force_persist(
                store, record_for(store, allocator, solution, opportunity)
            )
        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.EXECUTION_RECORD)
        )


# ---------------------------------------------------------------------------
# Feedback Records at volume  [T01.7.9, FR-V1..FR-V6, FR-I1..FR-I4]
# ---------------------------------------------------------------------------

class TestFeedbackStress:
    def _setup(self):
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return KnowledgeStore(), IdentityAllocator()

    def _outcomes(self, store, allocator, n=2):
        from tests.test_feedback import outcomes
        return outcomes(store, allocator, n)

    def test_lesson_across_many_outcomes(self):
        """A lesson may rest on a broad outcome population. [FR-V4]"""
        from tests.test_feedback import feedback_for, force_feedback

        store, allocator = self._setup()
        stored_outcomes = self._outcomes(store, allocator, 200)
        record = feedback_for(store, allocator, stored_outcomes)
        force_feedback(store, record)
        assert record.motivating_count == 200
        assert store.feedback.integrity().verify() == ()

    def test_many_lessons_stay_consistent(self):
        from tests.test_feedback import feedback_for, force_feedback

        store, allocator = self._setup()
        stored_outcomes = self._outcomes(store, allocator, 2)
        for _ in range(400):
            force_feedback(
                store, feedback_for(store, allocator, stored_outcomes)
            )
        assert len(store.feedback) == 400
        assert store.feedback.integrity().verify() == ()

    def test_drift_summary_flat_at_scale(self):
        """FR-I4: the total must stay statable as lessons accumulate."""
        import time
        from tests.test_feedback import feedback_for, force_feedback

        store, allocator = self._setup()
        stored_outcomes = self._outcomes(store, allocator, 2)
        for i in range(400):
            force_feedback(
                store,
                feedback_for(
                    store, allocator, stored_outcomes,
                    change_target=f"target-{i % 20}",
                ),
            )
        start = time.perf_counter()
        for _ in range(10):
            summary = store.feedback.drift_summary()
        per_call = (time.perf_counter() - start) / 10 * 1_000
        assert summary.applied_count == 400
        assert len(summary.targets()) == 20
        assert per_call < 500.0, f"drift summary degraded to {per_call:.1f}ms"

    def test_fri2_scan_flat_at_scale(self):
        """The loop-closure guard scans every object; must stay usable."""
        import time
        from tests.test_feedback import feedback_for, force_feedback

        store, allocator = self._setup()
        stored_outcomes = self._outcomes(store, allocator, 2)
        for _ in range(300):
            force_feedback(
                store, feedback_for(store, allocator, stored_outcomes)
            )
        start = time.perf_counter()
        for _ in range(5):
            violations = store.feedback.integrity().verify()
        per_audit = (time.perf_counter() - start) / 5 * 1_000
        assert violations == ()
        assert per_audit < 2_000.0, f"FR-I audit degraded to {per_audit:.1f}ms"

    def test_reversal_at_volume_preserves_records(self):
        """FR-I1: reversal retains the record that the lesson was applied."""
        from oip.enums import ObjectStatus
        from tests.test_feedback import feedback_for, force_feedback

        store, allocator = self._setup()
        stored_outcomes = self._outcomes(store, allocator, 2)
        stored = [
            force_feedback(store, feedback_for(store, allocator, stored_outcomes))
            for _ in range(200)
        ]
        for s in stored[:100]:
            store.transition(s.object_id, ObjectStatus.RETRACTED, "reversed")
        summary = store.feedback.drift_summary()
        assert summary.applied_count == 100
        assert summary.reversed_count == 100
        assert len(store.feedback) == 200

    def test_cascade_reaches_lessons(self):
        from oip.cascade import CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from tests.test_feedback import feedback_for, force_feedback

        store, allocator = self._setup()
        stored_outcomes = self._outcomes(store, allocator, 2)
        for _ in range(100):
            force_feedback(
                store, feedback_for(store, allocator, stored_outcomes)
            )
        # Withdraw EVERY attesting root: retracting one of several leaves a
        # valid upstream, which N-9 assigns to the partial-retraction rule
        # rather than to cascade. [T01.2.4, IOM 3.2]
        cascade = CascadeInvalidation(store=store)
        result = None
        for evidence in store.objects_of_type(ObjectType.EVIDENCE):
            result = cascade.retract(evidence.object_id, "withdrawn")
        assert result.completed
        assert all(
            s.status is ObjectStatus.INVALIDATED
            for s in store.objects_of_type(ObjectType.FEEDBACK_RECORD)
        )


# ---------------------------------------------------------------------------
# Orchestration at volume  [T01.6.1, N-17, N-10]
# ---------------------------------------------------------------------------

class TestOrchestrationStress:
    def _parts(self):
        from oip.enums import Engine
        from oip.orchestration import (CycleBounds, InvocationResult,
                                       Orchestrator, WorkItem, WorkSet)
        return Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet

    def test_large_work_set_within_bounds(self):
        """A cycle must stay bounded however large the plan. [N-17]"""
        Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet = self._parts()
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(50_000)
        ))
        o = Orchestrator(
            invoker=lambda i: InvocationResult.empty(),
            bounds=CycleBounds(max_work_items=1_000, wall_clock_budget_seconds=9999),
        )
        record = o.run_cycle(ws)
        assert record.attempted_count == 1_000
        assert record.not_attempted_count == 49_000
        assert record.attempted_count + record.not_attempted_count == 50_000

    def test_many_consecutive_cycles(self):
        """Continuous operation is a sequence of bounded cycles. [N-17, M-37]"""
        Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet = self._parts()
        o = Orchestrator(invoker=lambda i: InvocationResult.produced("o"))
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(5)
        ))
        for _ in range(2_000):
            o.run_cycle(ws)
        assert o.cycle_count == 2_000
        assert all(c.terminated for c in o.cycles)
        assert [c.cycle_id for c in o.cycles] == list(range(1, 2_001))

    def test_sustained_failure_never_masked(self):
        """N-10 must hold at volume, not merely in the small."""
        Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        o = Orchestrator(invoker=boom)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(200)
        ))
        record = o.run_cycle(ws)
        assert record.failed_count == 200
        assert record.had_failure is True
        assert len(record.failures) == 200
        assert len(o.failed_cycles()) == 1

    def test_failure_store_accumulates_across_cycles(self):
        from oip.configuration import FailureStore
        Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet = self._parts()

        store = FailureStore()
        o = Orchestrator(
            invoker=lambda i: (_ for _ in ()).throw(RuntimeError("x")),
            failure_store=store,
        )
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(10)
        ))
        for _ in range(50):
            o.run_cycle(ws)
        assert len(store) == 500
        assert store.participates_in_lineage is False

    def test_concurrent_cycles_serialise_at_volume(self):
        """N-11: two cycles never interleave, however many callers. [N-11]"""
        import threading
        Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet = self._parts()

        active, overlap = [], []

        def watcher(_i):
            active.append(1)
            if len(active) > 1:
                overlap.append(True)
            active.pop()
            return InvocationResult.empty()

        o = Orchestrator(invoker=watcher)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(20)
        ))
        threads = [threading.Thread(target=lambda: o.run_cycle(ws)) for _ in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert overlap == []
        assert o.cycle_count == 16
        assert len({c.cycle_id for c in o.cycles}) == 16

    def test_invocation_throughput_is_usable(self):
        """Control overhead must not dominate engine work."""
        import time
        Engine, CycleBounds, InvocationResult, Orchestrator, WorkItem, WorkSet = self._parts()

        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(20_000)
        ))
        o = Orchestrator(
            invoker=lambda i: InvocationResult.empty(),
            bounds=CycleBounds(max_work_items=20_000, wall_clock_budget_seconds=9999),
        )
        start = time.perf_counter()
        record = o.run_cycle(ws)
        per_invocation = (time.perf_counter() - start) / 20_000 * 1e6
        assert record.attempted_count == 20_000
        assert per_invocation < 200.0, f"orchestration overhead {per_invocation:.1f}us/invocation"


# ---------------------------------------------------------------------------
# Processing state at volume  [T01.6.2]
# ---------------------------------------------------------------------------

class TestProcessingStateStress:
    """Idempotence detection must hold at volume, not merely in the small.

    Architecture References:
    - T01.6.2  Idempotence supported; state outside the object model;
               metadata only
    - N-17     Processing state tracked per cycle
    - N-10     Empty and failed stay distinguishable; failure never masked
    - N-11     Concurrent acquisition permitted, so the store is contended
    - N-12     Retention covers objects only; processing state grows unbounded
    """

    def _parts(self):
        from oip.enums import Engine
        from oip.orchestration import (CycleBounds, InvocationOutcome,
                                       InvocationResult, Orchestrator,
                                       ProcessingStateStore, WorkItem, WorkSet)
        return (Engine, CycleBounds, InvocationOutcome, InvocationResult,
                Orchestrator, ProcessingStateStore, WorkItem, WorkSet)

    def test_half_million_records_stay_exactly_queryable(self):
        """Detection must not degrade into approximation at volume. [T01.6.2]"""
        from datetime import datetime, timezone
        from oip.orchestration import InvocationRecord
        (Engine, _CB, InvocationOutcome, _IR, _O,
         ProcessingStateStore, _WI, _WS) = self._parts()

        t0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        store = ProcessingStateStore()
        for i in range(500_000):
            store.record(1 + i % 100, InvocationRecord(
                Engine.RESEARCH, (f"s-{i}",), "cfg",
                InvocationOutcome.EMPTY, (), "", t0, t0,
            ))
        assert len(store) == 500_000
        assert store.has_processed(Engine.RESEARCH, "s-0") is True
        assert store.has_processed(Engine.RESEARCH, "s-499999") is True
        assert store.has_processed(Engine.RESEARCH, "s-500000") is False
        assert store.reprocessed_keys() == ()
        assert len(store.cycles_recorded()) == 100

    def test_detection_holds_across_thousands_of_cycles(self):
        """Every input processed twice must be reported. [T01.6.2, v2 4.12]"""
        (Engine, _CB, _IO, InvocationResult, Orchestrator,
         ProcessingStateStore, WorkItem, WorkSet) = self._parts()

        store = ProcessingStateStore()
        orch = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                            processing_store=store)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(10)
        ))
        for _ in range(1_000):
            orch.run_cycle(ws)
        assert len(store) == 10_000
        assert len(store.reprocessed_keys()) == 10
        assert all(
            store.attempt_count(Engine.RESEARCH, f"s-{i}") == 1_000
            for i in range(10)
        )

    def test_unattempted_work_never_accumulates_at_volume(self):
        """A permanently bound-limited pipeline must not report phantom work."""
        (Engine, CycleBounds, InvocationOutcome, InvocationResult, Orchestrator,
         ProcessingStateStore, WorkItem, WorkSet) = self._parts()

        store = ProcessingStateStore()
        orch = Orchestrator(
            invoker=lambda i: InvocationResult.empty(),
            bounds=CycleBounds(max_work_items=5, wall_clock_budget_seconds=9999),
            processing_store=store,
        )
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(500)
        ))
        for _ in range(100):
            orch.run_cycle(ws)
        assert len(store) == 500
        assert all(
            r.outcome is not InvocationOutcome.NOT_ATTEMPTED for r in store.all()
        )
        for i in range(5, 500):
            assert store.has_processed(Engine.RESEARCH, f"s-{i}") is False

    def test_sustained_failure_is_fully_recorded_never_masked(self):
        """N-10 at volume: every failed attempt remains visible."""
        (Engine, _CB, _IO, _IR, Orchestrator,
         ProcessingStateStore, WorkItem, WorkSet) = self._parts()

        store = ProcessingStateStore()
        orch = Orchestrator(
            invoker=lambda i: (_ for _ in ()).throw(RuntimeError("engine down")),
            processing_store=store,
        )
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(100)
        ))
        for _ in range(20):
            orch.run_cycle(ws)
        assert len(store) == 2_000
        assert all(r.failed for r in store.all())
        assert len(store.reprocessed_keys()) == 100

    def test_concurrent_writers_lose_nothing_under_contention(self):
        """N-11 permits concurrent stages 1-2; the store is contended."""
        import threading
        from datetime import datetime, timezone
        from oip.orchestration import InvocationRecord
        (Engine, _CB, InvocationOutcome, _IR, _O,
         ProcessingStateStore, _WI, _WS) = self._parts()

        t0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        store = ProcessingStateStore()

        def writer(worker):
            for i in range(2_000):
                store.record(1, InvocationRecord(
                    Engine.RESEARCH, (f"w{worker}-{i}",), "cfg",
                    InvocationOutcome.EMPTY, (), "", t0, t0,
                ))

        threads = [threading.Thread(target=writer, args=(w,)) for w in range(16)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(store) == 32_000
        assert sum(len(v) for v in store._by_key.values()) == 32_000
        assert store.reprocessed_keys() == ()
        assert all(
            store.attempt_count(Engine.RESEARCH, f"w{w}-{i}") == 1
            for w in range(16) for i in (0, 999, 1_999)
        )

    def test_detection_throughput_is_usable(self):
        """Idempotence checks must not dominate the control path."""
        import time
        from datetime import datetime, timezone
        from oip.orchestration import InvocationRecord
        (Engine, _CB, InvocationOutcome, _IR, _O,
         ProcessingStateStore, WorkItem, _WS) = self._parts()

        t0 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        store = ProcessingStateStore()
        for i in range(100_000):
            store.record(1, InvocationRecord(
                Engine.RESEARCH, (f"s-{i}",), "cfg",
                InvocationOutcome.EMPTY, (), "", t0, t0,
            ))
        probes = [WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg")
                  for i in range(0, 100_000, 10)]
        start = time.perf_counter()
        hits = sum(1 for p in probes if store.would_reprocess(p))
        per_check = (time.perf_counter() - start) / len(probes) * 1e6
        assert hits == len(probes)
        assert per_check < 50.0, f"detection {per_check:.1f}us/check"


# ---------------------------------------------------------------------------
# Failure surfacing at volume  [T01.6.3]
# ---------------------------------------------------------------------------

class TestFailureSurfacingStress:
    """N-10 must hold at volume, not merely in the small.

    Architecture References:
    - T01.6.3  Failed distinguishable from empty; failures never silently halt
    - N-10     Failure recorded, surfaced, never masked as completion
    - N-17     Cycle continues past failure
    - v2 4.12  Partial-failure mishandling is a named failure mode
    """

    def _parts(self):
        from oip.configuration import FailureStore
        from oip.enums import Engine
        from oip.orchestration import (CycleBounds, FailureSurface,
                                       InvocationResult, Orchestrator,
                                       WorkItem, WorkSet)
        return (Engine, CycleBounds, FailureSurface, InvocationResult,
                Orchestrator, WorkItem, WorkSet, FailureStore)

    def test_fifty_thousand_failures_remain_exactly_visible(self):
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, _FS) = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        o = Orchestrator(
            invoker=boom,
            bounds=CycleBounds(max_work_items=500, wall_clock_budget_seconds=9999),
        )
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(500)
        ))
        for _ in range(100):
            o.run_cycle(ws)
        s = FailureSurface.over(o)
        assert s.failed_count == 50_000
        assert len(s.cycles_with_failures()) == 100
        assert s.masked_cycles() == ()
        s.assert_not_masked()
        assert s.every_failure_is_visible()

    def test_empty_and_failed_never_conflate_at_volume(self):
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, _FS) = self._parts()

        def alternating(i):
            if int(i.input_ids[0].split("-")[1]) % 2 == 0:
                raise RuntimeError("boom")
            return InvocationResult.empty()

        o = Orchestrator(
            invoker=alternating,
            bounds=CycleBounds(max_work_items=10_000,
                               wall_clock_budget_seconds=9999),
        )
        o.run_cycle(WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(10_000)
        )))
        s = FailureSurface.over(o)
        assert s.failed_count == 5_000
        assert s.empty_count == 5_000
        assert len(s.produced_nothing()) == 10_000

    def test_attribution_holds_across_many_cycles(self):
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, FailureStore) = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        store = FailureStore()
        o = Orchestrator(invoker=boom, failure_store=store)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.FACT_EXTRACTION, (f"s-{i}",), "cfg") for i in range(20)
        ))
        for _ in range(250):
            o.run_cycle(ws)
        assert len(store) == 5_000
        assert store.unattributed() == ()
        assert len(store.for_cycle(1)) == 20
        assert len(store.for_engine(Engine.FACT_EXTRACTION)) == 5_000

    def test_sustained_total_failure_never_halts_the_pipeline(self):
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, _FS) = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        o = Orchestrator(invoker=boom)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(50)
        ))
        for _ in range(200):
            o.run_cycle(ws)
        assert o.cycle_count == 200
        assert all(c.attempted_count == 50 for c in o.cycles)
        assert all(c.not_attempted_count == 0 for c in o.cycles)
        assert FailureSurface.over(o).consecutive_failures() == 200

    def test_hostile_store_at_volume_never_masks(self):
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, FailureStore) = self._parts()

        class Hostile(FailureStore):
            def record(self, failure):
                raise RuntimeError("store unavailable")

        def boom(_i):
            raise RuntimeError("engine down")

        o = Orchestrator(invoker=boom, failure_store=Hostile())
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(20)
        ))
        for _ in range(100):
            o.run_cycle(ws)
        s = FailureSurface.over(o)
        assert s.failed_count == 2_000
        assert s.masked_cycles() == ()
        s.assert_not_masked()
        assert all(len(c.failures) == 40 for c in o.cycles)

    def test_concurrent_failure_recording_stays_exact(self):
        import threading
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, FailureStore) = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        store = FailureStore()
        errors = []

        def worker(k):
            try:
                o = Orchestrator(invoker=boom, failure_store=store)
                ws = WorkSet(items=tuple(
                    WorkItem(Engine.RESEARCH, (f"w{k}-{i}",), "cfg")
                    for i in range(50)
                ))
                for _ in range(20):
                    o.run_cycle(ws)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors, errors
        assert len(store) == 8_000
        assert store.unattributed() == ()

    def test_surfacing_query_throughput_is_usable(self):
        import time
        (Engine, CycleBounds, FailureSurface, InvocationResult,
         Orchestrator, WorkItem, WorkSet, _FS) = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        o = Orchestrator(
            invoker=boom,
            bounds=CycleBounds(max_work_items=200, wall_clock_budget_seconds=9999),
        )
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(200)
        ))
        for _ in range(50):
            o.run_cycle(ws)
        s = FailureSurface.over(o)
        start = time.perf_counter()
        s.assert_not_masked()
        n = s.failed_count
        elapsed = time.perf_counter() - start
        assert n == 10_000
        assert elapsed < 5.0, f"masking check took {elapsed:.2f}s over 10k failures"


# ---------------------------------------------------------------------------
# Concurrency boundary at volume  [T01.6.4]
# ---------------------------------------------------------------------------

class TestConcurrencyBoundaryStress:
    """N-11 must hold at volume and under sustained thread pressure.

    Architecture References:
    - N-11    Stages 1-2 concurrent; stages 3-9 serialised, one batch at a time
    - R-1     Non-branching supersession rests on serialised interpretation
    - N-17    Bounds hold whatever the concurrency
    - N-10    Failures recorded and surfaced, never masked
    - v2 4.12 Deadlock, starvation and duplicate invocation are named modes
    """

    def _parts(self):
        from oip.configuration import FailureStore
        from oip.enums import Engine
        from oip.orchestration import (ConcurrencyBoundary, CycleBounds,
                                       FailureSurface, InvocationResult,
                                       Orchestrator, ProcessingStateStore,
                                       WorkItem, WorkSet)
        return (Engine, CycleBounds, ConcurrencyBoundary, FailureSurface,
                InvocationResult, Orchestrator, ProcessingStateStore,
                WorkItem, WorkSet, FailureStore)

    def test_fifty_thousand_concurrent_items_exact(self):
        (Engine, CycleBounds, ConcurrencyBoundary, _FS, InvocationResult,
         Orchestrator, ProcessingStateStore, WorkItem, WorkSet,
         _Store) = self._parts()

        ps = ProcessingStateStore()
        o = Orchestrator(
            invoker=lambda i: InvocationResult.empty(),
            processing_store=ps, max_workers=8,
            bounds=CycleBounds(max_work_items=50_000,
                               wall_clock_budget_seconds=9999),
        )
        r = o.run_cycle(WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(50_000)
        )))
        assert r.attempted_count == 50_000
        assert len(ps) == 50_000
        assert ps.reprocessed_keys() == ()
        assert ConcurrencyBoundary(r).holds

    def test_barrier_never_breached_over_two_thousand_cycles(self):
        import random
        (Engine, CycleBounds, ConcurrencyBoundary, _FS, InvocationResult,
         Orchestrator, _PS, WorkItem, WorkSet, _Store) = self._parts()

        engines = [Engine.RESEARCH, Engine.FACT_EXTRACTION,
                   Engine.PROBLEM_INTELLIGENCE, Engine.PATTERN_INTELLIGENCE,
                   Engine.OPPORTUNITY_INTELLIGENCE,
                   Engine.SOLUTION_INTELLIGENCE, Engine.VALIDATION,
                   Engine.FEEDBACK]
        rng = random.Random(20260804)
        o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                         max_workers=6)
        for _ in range(2_000):
            items = tuple(
                WorkItem(rng.choice(engines), (f"s-{n}",), "cfg")
                for n in range(rng.randint(1, 8))
            )
            r = o.run_cycle(WorkSet(items=items))
            ConcurrencyBoundary(r).assert_holds()
        assert o.cycle_count == 2_000

    def test_live_overlap_detector_under_sustained_pressure(self):
        import threading
        import time
        (Engine, CycleBounds, _CB, _FS, InvocationResult,
         Orchestrator, _PS, WorkItem, WorkSet, _Store) = self._parts()

        acquisition = (Engine.RESEARCH, Engine.FACT_EXTRACTION)
        state = {"acq": 0, "ser": 0, "bad": 0, "max_ser": 0, "max_acq": 0}
        lock = threading.Lock()

        def invoker(item):
            with lock:
                key = "acq" if item.engine in acquisition else "ser"
                state[key] += 1
                state["max_" + key] = max(state["max_" + key], state[key])
                if state["ser"] and state["acq"]:
                    state["bad"] += 1
            time.sleep(0.0002)
            with lock:
                state["acq" if item.engine in acquisition else "ser"] -= 1
            return InvocationResult.empty()

        o = Orchestrator(invoker=invoker, max_workers=8)
        items = []
        for n in range(400):
            items.append(WorkItem(Engine.RESEARCH, (f"a-{n}",), "cfg"))
            if n % 8 == 0:
                items.append(
                    WorkItem(Engine.PATTERN_INTELLIGENCE, (f"p-{n}",), "cfg")
                )
        ws = WorkSet(items=tuple(items))
        for _ in range(10):
            o.run_cycle(ws)
        assert state["bad"] == 0, f"{state['bad']} barrier breaches"
        assert state["max_ser"] <= 1, state["max_ser"]
        assert state["max_acq"] > 1, "acquisition never parallelised"

    def test_no_duplicate_invocation_at_volume(self):
        import threading
        (Engine, CycleBounds, _CB, _FS, InvocationResult,
         Orchestrator, _PS, WorkItem, WorkSet, _Store) = self._parts()

        calls, lock = [], threading.Lock()

        def track(item):
            with lock:
                calls.append(item.input_ids[0])
            return InvocationResult.empty()

        o = Orchestrator(invoker=track, max_workers=8,
                         bounds=CycleBounds(max_work_items=20_000,
                                            wall_clock_budget_seconds=9999))
        o.run_cycle(WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(20_000)
        )))
        assert len(calls) == 20_000
        assert len(set(calls)) == 20_000

    def test_sustained_failure_under_concurrency_never_masked(self):
        (Engine, CycleBounds, ConcurrencyBoundary, FailureSurface,
         _IR, Orchestrator, _PS, WorkItem, WorkSet, FailureStore) = self._parts()

        def boom(_i):
            raise RuntimeError("engine down")

        store = FailureStore()
        o = Orchestrator(invoker=boom, failure_store=store, max_workers=8)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(100)
        ))
        for _ in range(50):
            o.run_cycle(ws)
        s = FailureSurface.over(o)
        assert s.failed_count == 5_000
        assert len(store) == 5_000
        assert store.unattributed() == ()
        assert s.masked_cycles() == ()
        s.assert_not_masked()

    def test_record_order_deterministic_at_volume(self):
        import random
        import time
        (Engine, CycleBounds, _CB, _FS, InvocationResult,
         Orchestrator, _PS, WorkItem, WorkSet, _Store) = self._parts()

        def jittery(_i):
            if random.random() < 0.01:
                time.sleep(0.0005)
            return InvocationResult.empty()

        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(5_000)
        ))
        expected = [f"s-{i}" for i in range(5_000)]
        o = Orchestrator(invoker=jittery, max_workers=8,
                         bounds=CycleBounds(max_work_items=5_000,
                                            wall_clock_budget_seconds=9999))
        for _ in range(5):
            r = o.run_cycle(ws)
            assert [x.input_ids[0] for x in r.invocations] == expected

    def test_no_thread_leak_across_many_parallel_cycles(self):
        import threading
        import time
        (Engine, CycleBounds, _CB, _FS, InvocationResult,
         Orchestrator, _PS, WorkItem, WorkSet, _Store) = self._parts()

        before = threading.active_count()
        o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                         max_workers=8)
        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(20)
        ))
        for _ in range(500):
            o.run_cycle(ws)
        time.sleep(0.3)
        assert threading.active_count() <= before + 2

    def test_parallel_throughput_beats_sequential_on_io_bound_work(self):
        import time
        (Engine, CycleBounds, _CB, _FS, InvocationResult,
         Orchestrator, _PS, WorkItem, WorkSet, _Store) = self._parts()

        def io_bound(_i):
            time.sleep(0.002)
            return InvocationResult.empty()

        ws = WorkSet(items=tuple(
            WorkItem(Engine.RESEARCH, (f"s-{i}",), "cfg") for i in range(80)
        ))
        bounds = CycleBounds(max_work_items=200, wall_clock_budget_seconds=9999)
        start = time.perf_counter()
        Orchestrator(invoker=io_bound, max_workers=1,
                     bounds=bounds).run_cycle(ws)
        sequential = time.perf_counter() - start
        start = time.perf_counter()
        Orchestrator(invoker=io_bound, max_workers=8,
                     bounds=bounds).run_cycle(ws)
        parallel = time.perf_counter() - start
        assert parallel < sequential, (
            f"parallel {parallel:.3f}s not faster than sequential "
            f"{sequential:.3f}s -- N-11's concurrent half is not working"
        )


# ---------------------------------------------------------------------------
# Sequencing enforcement at volume  [T01.6.5]
# ---------------------------------------------------------------------------

class TestSequencingStress:
    """An engine cannot run before its inputs exist -- at volume.

    Architecture References:
    - T01.6.5 Pipeline order never violated; out-of-order invocation rejected
    - N-14    Direct-input table
    - v2 4.12 Stage-order violation is a named failure mode
    - N-11    Concurrency boundary preserved [T01.6.4]
    - N-10    A rejection is not an engine failure
    """

    def _parts(self):
        from oip.enums import Engine, ObjectType
        from oip.orchestration import (ConcurrencyBoundary, CycleBounds,
                                       InvocationResult, Orchestrator,
                                       ProcessingStateStore, SequencingGuard,
                                       WorkItem, WorkSet)
        return (Engine, ObjectType, ConcurrencyBoundary, CycleBounds,
                InvocationResult, Orchestrator, ProcessingStateStore,
                SequencingGuard, WorkItem, WorkSet)

    class _Resolver:
        def __init__(self, mapping):
            self.map = mapping

        def resolve_type(self, object_id):
            return self.map.get(object_id)

    def test_fifty_thousand_mixed_items_exact(self):
        (Engine, ObjectType, ConcurrencyBoundary, CycleBounds,
         InvocationResult, Orchestrator, ProcessingStateStore,
         _SG, WorkItem, WorkSet) = self._parts()

        resolver = self._Resolver(
            {f"EV-{n}": ObjectType.EVIDENCE for n in range(25_000)}
        )
        ps = ProcessingStateStore()
        o = Orchestrator(
            invoker=lambda i: InvocationResult.empty(),
            max_workers=8, state_resolver=resolver, processing_store=ps,
            bounds=CycleBounds(max_work_items=60_000,
                               wall_clock_budget_seconds=9999),
        )
        items = []
        for n in range(25_000):
            items.append(WorkItem(Engine.FACT_EXTRACTION, (f"EV-{n}",), "cfg"))
            items.append(WorkItem(Engine.FACT_EXTRACTION, (f"GONE-{n}",), "cfg"))
        r = o.run_cycle(WorkSet(items=tuple(items)))
        assert r.attempted_count == 25_000
        assert r.rejected_count == 25_000
        assert r.failed_count == 0
        assert len(ps) == 25_000

    def test_barrier_holds_with_sequencing_across_many_cycles(self):
        import random
        (Engine, ObjectType, ConcurrencyBoundary, _CB, InvocationResult,
         Orchestrator, _PS, _SG, WorkItem, WorkSet) = self._parts()

        resolver = self._Resolver({
            "EV": ObjectType.EVIDENCE, "FA": ObjectType.FACT,
            "PR": ObjectType.PROBLEM, "PT": ObjectType.PATTERN,
        })
        choices = [
            (Engine.FACT_EXTRACTION, "EV"), (Engine.PROBLEM_INTELLIGENCE, "FA"),
            (Engine.PATTERN_INTELLIGENCE, "PR"),
            (Engine.OPPORTUNITY_INTELLIGENCE, "PT"),
            (Engine.FACT_EXTRACTION, "MISSING"), (Engine.RESEARCH, "src"),
        ]
        rng = random.Random(20260805)
        o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                         max_workers=6, state_resolver=resolver)
        for _ in range(1_500):
            items = tuple(
                WorkItem(*rng.choice(choices)[:1],
                         (rng.choice(choices)[1],), "cfg")
                for _ in range(rng.randint(1, 7))
            )
            ConcurrencyBoundary(o.run_cycle(WorkSet(items=items))).assert_holds()
        assert o.cycle_count == 1_500

    def test_no_unready_engine_ever_runs_at_volume(self):
        import threading
        (Engine, ObjectType, _CB2, CycleBounds, InvocationResult,
         Orchestrator, _PS, _SG, WorkItem, WorkSet) = self._parts()

        ran, lock = [], threading.Lock()

        def track(item):
            with lock:
                ran.append(item.input_ids[0])
            return InvocationResult.empty()

        o = Orchestrator(invoker=track, max_workers=8,
                         state_resolver=self._Resolver({}),
                         bounds=CycleBounds(max_work_items=30_000,
                                            wall_clock_budget_seconds=9999))
        r = o.run_cycle(WorkSet(items=tuple(
            WorkItem(Engine.FACT_EXTRACTION, (f"m-{n}",), "cfg")
            for n in range(20_000)
        )))
        assert ran == []
        assert r.rejected_count == 20_000

    def test_rejections_never_become_processing_state_at_volume(self):
        (Engine, ObjectType, _CB2, CycleBounds, InvocationResult,
         Orchestrator, ProcessingStateStore, _SG, WorkItem, WorkSet) = self._parts()

        ps = ProcessingStateStore()
        o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                         max_workers=8, state_resolver=self._Resolver({}),
                         processing_store=ps,
                         bounds=CycleBounds(max_work_items=20_000,
                                            wall_clock_budget_seconds=9999))
        for _ in range(10):
            o.run_cycle(WorkSet(items=tuple(
                WorkItem(Engine.PATTERN_INTELLIGENCE, (f"m-{n}",), "cfg")
                for n in range(1_000)
            )))
        assert len(ps) == 0

    def test_determinism_of_the_rejection_set_at_volume(self):
        (Engine, ObjectType, _CB2, CycleBounds, InvocationResult,
         Orchestrator, _PS, _SG, WorkItem, WorkSet) = self._parts()

        resolver = self._Resolver(
            {f"EV-{n}": ObjectType.EVIDENCE for n in range(2_000)}
        )
        items = []
        for n in range(2_000):
            items.append(WorkItem(Engine.FACT_EXTRACTION, (f"EV-{n}",), "cfg"))
            items.append(WorkItem(Engine.FACT_EXTRACTION, (f"X-{n}",), "cfg"))
        ws = WorkSet(items=tuple(items))
        expected = None
        for _ in range(5):
            o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                             max_workers=8, state_resolver=resolver,
                             bounds=CycleBounds(max_work_items=10_000,
                                                wall_clock_budget_seconds=9999))
            got = tuple(x.rejected for x in o.run_cycle(ws).invocations)
            if expected is None:
                expected = got
            assert got == expected

    def test_sequencing_check_throughput_is_usable(self):
        import time
        (Engine, ObjectType, _CB2, CycleBounds, InvocationResult,
         Orchestrator, _PS, _SG, WorkItem, WorkSet) = self._parts()

        resolver = self._Resolver(
            {f"EV-{n}": ObjectType.EVIDENCE for n in range(20_000)}
        )
        ws = WorkSet(items=tuple(
            WorkItem(Engine.FACT_EXTRACTION, (f"EV-{n}",), "cfg")
            for n in range(20_000)
        ))
        o = Orchestrator(invoker=lambda i: InvocationResult.empty(),
                         state_resolver=resolver,
                         bounds=CycleBounds(max_work_items=20_000,
                                            wall_clock_budget_seconds=9999))
        start = time.perf_counter()
        r = o.run_cycle(ws)
        per = (time.perf_counter() - start) / 20_000 * 1e6
        assert r.attempted_count == 20_000
        assert per < 200.0, f"sequencing overhead {per:.1f}us/item"


# ---------------------------------------------------------------------------
# ARCHIVED tiering at volume  [T01.2.5]
# ---------------------------------------------------------------------------

class TestRetentionStress:
    """N-12's reachability rule must hold at volume.

    Architecture References:
    - N-12  Reachable-from-ACTIVE objects are never archived; traversal never
            breaks; skeleton retained permanently
    - I4    Nothing hard-deleted
    - N-9   ARCHIVED does not cascade
    """

    def _parts(self):
        from oip.enums import ObjectStatus, ObjectType
        from oip.identity import IdentityAllocator
        from oip.retention import RetentionPolicy
        from oip.store import KnowledgeStore
        return (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
                KnowledgeStore)

    def test_two_thousand_objects_protection_exact(self):
        from conftest import write_derived, write_evidence
        (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
         KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        protected, leaves = [], []
        for _ in range(1_000):
            ev = write_evidence(store, alloc)
            fact = write_derived(store, alloc, ObjectType.FACT, [ev])
            protected.append(ev.object_id)
            leaves.append(fact.object_id)

        policy = RetentionPolicy(store=store)
        assert policy.archive_all(protected) == ()
        for oid in protected:
            assert store.get(oid).status is ObjectStatus.ACTIVE

        archived = policy.archive_all(leaves)
        assert len(archived) == 1_000
        # every former parent is now free
        freed = policy.archive_all(protected)
        assert len(freed) == 1_000

    def test_traversal_survives_mass_archival(self):
        from conftest import write_derived, write_evidence
        (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
         KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        pairs = []
        for _ in range(500):
            ev = write_evidence(store, alloc)
            fact = write_derived(store, alloc, ObjectType.FACT, [ev])
            pairs.append((ev.object_id, fact.object_id))

        policy = RetentionPolicy(store=store)
        policy.archive_all([f for _, f in pairs])
        policy.archive_all([e for e, _ in pairs])

        for ev_id, fact_id in pairs:
            assert store.graph.contains(ev_id)
            assert ev_id in store.graph.ancestors(fact_id)
            assert store.find(ev_id) is not None
            assert policy.verify_skeleton_intact(ev_id) == ()
        assert store.graph_diverges() == ()
        store.assert_integrity()

    def test_nothing_hard_deleted_at_volume(self):
        from conftest import write_evidence
        (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
         KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        ids = [write_evidence(store, alloc).object_id for _ in range(2_000)]
        before = len(store)
        RetentionPolicy(store=store).archive_all(ids)
        assert len(store) == before
        assert all(store.find(i) is not None for i in ids)

    def test_deep_chains_protect_every_ancestor(self):
        from conftest import write_chain
        (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
         KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        chains = [write_chain(store, alloc) for _ in range(150)]
        policy = RetentionPolicy(store=store)
        for chain in chains:
            terminal = chain[ObjectType.VALIDATION].object_id
            for otype, stored in chain.items():
                if stored.object_id == terminal:
                    continue
                assert not policy.is_archivable(stored.object_id), otype

    def test_concurrent_archival_preserves_the_invariant(self):
        import threading
        from conftest import write_derived, write_evidence
        (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
         KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        for _ in range(200):
            ev = write_evidence(store, alloc)
            write_derived(store, alloc, ObjectType.FACT, [ev])
        for _ in range(200):
            write_evidence(store, alloc)

        ids = [s.object_id for s in list(store)]
        errs = []

        def worker(chunk):
            try:
                RetentionPolicy(store=store).archive_all(chunk)
            except Exception as exc:
                errs.append(exc)

        size = max(1, len(ids) // 8)
        chunks = [ids[i:i + size] for i in range(0, len(ids), size)]
        threads = [threading.Thread(target=worker, args=(c,)) for c in chunks]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errs, errs

        store.assert_integrity()
        for stored in store:
            if stored.status is not ObjectStatus.ARCHIVED:
                continue
            for active in store.active_objects():
                assert stored.object_id not in store.graph.ancestors(
                    active.object_id
                ), "archived object supports ACTIVE knowledge"

    def test_reachability_computation_is_usable(self):
        import time
        from conftest import write_derived, write_evidence
        (ObjectStatus, ObjectType, IdentityAllocator, RetentionPolicy,
         KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        for _ in range(400):
            ev = write_evidence(store, alloc)
            write_derived(store, alloc, ObjectType.FACT, [ev])

        policy = RetentionPolicy(store=store)
        start = time.perf_counter()
        index = policy.reachability()
        elapsed = time.perf_counter() - start
        assert len(index) >= 400
        assert elapsed < 10.0, f"reachability took {elapsed:.2f}s over 800 objects"


# ---------------------------------------------------------------------------
# Calibration conformance at volume  [T01.5.5]
# ---------------------------------------------------------------------------

class TestCalibrationStress:
    """The S-1 rubric must hold at volume and under contention.

    Architecture References:
    - S-1  Five bands; alternative-counting; comparability argued not
           demonstrated until O2
    - R-1  Deviations recorded, never corrected
    - N-4  Calibration is statistical rather than exact
    """

    def _parts(self):
        from oip.calibration import (CALIBRATION_RUBRIC, CalibrationRegister,
                                     ConformanceOutcome, assess_assertion,
                                     compare_across_engines,
                                     criterion_for_value)
        from oip.enums import ConfidenceBand, Engine
        return (CALIBRATION_RUBRIC, CalibrationRegister, ConformanceOutcome,
                assess_assertion, compare_across_engines, criterion_for_value,
                ConfidenceBand, Engine)

    def test_one_hundred_thousand_assessments_stay_exact(self):
        (_R, CalibrationRegister, ConformanceOutcome, assess_assertion,
         _C, _CV, _CB, _E) = self._parts()

        register = CalibrationRegister()
        deviations = 0
        for i in range(100_000):
            count = 3 if i % 2 else 0
            register.record(f"o{i}", assess_assertion(0.85, count))
            deviations += i % 2
        assert register.assessment_count == 100_000
        assert register.deviation_count == deviations == 50_000
        assert register.unassessed_count == 0

    def test_band_resolution_is_exhaustive_and_unique(self):
        (CALIBRATION_RUBRIC, _Reg, _CO, _A, _C, criterion_for_value,
         ConfidenceBand, _E) = self._parts()

        for step in range(0, 100_001):
            value = step / 100_000
            criterion = criterion_for_value(value)
            assert criterion.band is ConfidenceBand.for_value(value)
            holding = [c for c in CALIBRATION_RUBRIC if c.contains(value)]
            assert len(holding) == 1, value

    def test_no_false_conformity_across_the_whole_scale(self):
        (_R, _Reg, ConformanceOutcome, assess_assertion, _C, _CV,
         ConfidenceBand, _E) = self._parts()

        qualitative = (ConfidenceBand.NEGLIGIBLE, ConfidenceBand.STRONG)
        for step in range(0, 10_001):
            value = step / 10_000
            # no count -> never conformant
            assert assess_assertion(value).outcome is (
                ConformanceOutcome.UNASSESSED)
            # qualitative band -> never judged, whatever the count
            if ConfidenceBand.for_value(value) in qualitative:
                for count in (0, 1, 2, 9):
                    assert assess_assertion(value, count).outcome is (
                        ConformanceOutcome.UNASSESSED)

    def test_concurrent_recording_at_volume(self):
        import threading
        (_R, CalibrationRegister, _CO, assess_assertion, _C, _CV,
         _CB, _E) = self._parts()

        register = CalibrationRegister()
        errors = []

        def worker(k):
            try:
                for i in range(2_000):
                    register.record(f"d{k}-{i}", assess_assertion(0.85, 3))
                    register.record(f"c{k}-{i}", assess_assertion(0.85, 0))
                    register.record(f"u{k}-{i}", assess_assertion(0.85))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors, errors
        assert register.assessment_count == 48_000
        assert register.deviation_count == 16_000
        assert register.unassessed_count == 16_000
        assert len(register.all()) == 16_000

    def test_determinism_over_many_repeats(self):
        import dataclasses
        (_R, _Reg, _CO, assess_assertion, _C, _CV, _CB, Engine) = self._parts()

        reference = dataclasses.asdict(
            assess_assertion(0.55, 1, engine=Engine.PROBLEM_INTELLIGENCE))
        for _ in range(20_000):
            assert dataclasses.asdict(
                assess_assertion(0.55, 1, engine=Engine.PROBLEM_INTELLIGENCE)
            ) == reference

    def test_cross_engine_comparison_at_volume_stays_qualified(self):
        (_R, _Reg, _CO, _A, compare_across_engines, _CV,
         _CB, Engine) = self._parts()

        engines = list(Engine)
        for _ in range(5_000):
            comparison = compare_across_engines(
                [(engines[i % 9], (i % 101) / 100) for i in range(9)])
            assert comparison.comparability_demonstrated is False
            assert comparison.rubric_dependent is True

    def test_assessment_throughput_is_usable(self):
        import time
        (_R, _Reg, _CO, assess_assertion, _C, _CV, _CB, _E) = self._parts()

        start = time.perf_counter()
        for i in range(50_000):
            assess_assertion(0.85, i % 4)
        per = (time.perf_counter() - start) / 50_000 * 1e6
        assert per < 100.0, f"assessment {per:.1f}us each"


# ---------------------------------------------------------------------------
# Partial retraction at volume  [T01.2.4]
# ---------------------------------------------------------------------------

class TestPartialRetractionStress:
    """The N-9 / IOM 3.2 boundary must hold at volume.

    Architecture References:
    - N-9    "A dependent supported by ten Facts, one of which is
             invalidated, is handled by the partial-retraction rule rather
             than by cascade"; idempotent; terminating
    - IOM 3.2 INVALIDATED on "All attesting Evidence retracted"
    - R-8    Acyclic lineage guarantees termination
    """

    def _parts(self):
        from oip.cascade import CASCADE_TRIGGERS, CascadeInvalidation
        from oip.enums import ObjectStatus, ObjectType
        from oip.identity import IdentityAllocator
        from oip.store import KnowledgeStore
        return (CASCADE_TRIGGERS, CascadeInvalidation, ObjectStatus,
                ObjectType, IdentityAllocator, KnowledgeStore)

    def test_wide_fan_in_spared_until_the_last_parent(self):
        from conftest import write_derived, write_evidence
        (_CT, CascadeInvalidation, ObjectStatus, ObjectType,
         IdentityAllocator, KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        parents = [write_evidence(store, alloc) for _ in range(200)]
        fact = write_derived(store, alloc, ObjectType.FACT, parents)
        cascade = CascadeInvalidation(store=store)

        for parent in parents[:-1]:
            cascade.retract(parent.object_id, "withdrawn")
            assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

        cascade.retract(parents[-1].object_id, "withdrawn")
        assert store.get(fact.object_id).status is ObjectStatus.INVALIDATED

    def test_the_invariant_holds_across_a_large_population(self):
        from conftest import write_derived, write_evidence
        (CASCADE_TRIGGERS, CascadeInvalidation, ObjectStatus, ObjectType,
         IdentityAllocator, KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        subjects = []
        for _ in range(300):
            first = write_evidence(store, alloc)
            second = write_evidence(store, alloc)
            subjects.append(
                (first, write_derived(store, alloc, ObjectType.FACT,
                                      [first, second]))
            )

        cascade = CascadeInvalidation(store=store)
        for first, _ in subjects:
            cascade.retract(first.object_id, "withdrawn")

        for _, subject in subjects:
            assert store.get(subject.object_id).status is ObjectStatus.ACTIVE

        # No ACTIVE object may lack a valid upstream.
        for stored in store:
            refs = stored.lineage.reference_ids if stored.lineage else ()
            if not refs or stored.status is not ObjectStatus.ACTIVE:
                continue
            assert any(
                store.find(r) and store.find(r).status not in CASCADE_TRIGGERS
                for r in refs
            )
        store.assert_integrity()

    def test_idempotence_at_volume(self):
        from conftest import write_derived, write_evidence
        (_CT, CascadeInvalidation, ObjectStatus, ObjectType,
         IdentityAllocator, KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        first = write_evidence(store, alloc)
        second = write_evidence(store, alloc)
        for _ in range(200):
            write_derived(store, alloc, ObjectType.FACT, [first, second])

        cascade = CascadeInvalidation(store=store)
        cascade.retract(first.object_id, "withdrawn")
        for _ in range(25):
            result = cascade.cascade(first.object_id)
            assert result.changed == 0
            assert result.partial_count == 200

    def test_concurrent_partial_retraction_preserves_the_invariant(self):
        import threading
        from conftest import write_derived, write_evidence
        (CASCADE_TRIGGERS, CascadeInvalidation, ObjectStatus, ObjectType,
         IdentityAllocator, KnowledgeStore) = self._parts()

        store, alloc = KnowledgeStore(), IdentityAllocator()
        pairs = []
        for _ in range(80):
            first = write_evidence(store, alloc)
            second = write_evidence(store, alloc)
            write_derived(store, alloc, ObjectType.FACT, [first, second])
            pairs.append(first)

        errors = []

        def worker(origin):
            try:
                CascadeInvalidation(store=store).retract(origin.object_id, "w")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(p,)) for p in pairs]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        store.assert_integrity()
