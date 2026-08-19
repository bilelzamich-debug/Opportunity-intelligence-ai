"""Stress tests for the source model at volume and under contention.

Task: T02.1.1

Architecture References:
- N-04   Historical reads must reproduce at any scale
- N-16   Independence grouping must hold at volume
- R-01   Append-only history is never truncated
- N-20   The closed eight-member taxonomy (S 5.1) must hold under every
         access pattern: volume never extends it, and raw strings outside
         the set never classify

Run with `-m stress`; deselected from the default suite.
"""

from __future__ import annotations

import threading
import time

import pytest

from oip.source import (
    TAXONOMY_RATIFIED,
    SourceEligibility,
    SourceRegistry,
    UntypableChannelError,
    assess_eligibility,
    classify,
    is_ratified_source_type,
    taxonomy_members,
)

pytestmark = pytest.mark.stress


class TestVolume:
    def test_ten_thousand_sources_register_and_resolve(self):
        reg = SourceRegistry()
        for i in range(10_000):
            reg.register(f"src-{i}", f"raw-type-{i % 20}")
        assert len(reg) == 10_000
        assert reg.resolve("src-9999").source_identifier == "src-9999"
        assert reg.independent_source_count() == 10_000

    def test_large_independence_group_collapses_to_one(self):
        """N-16: syndication cannot inflate the independent count."""
        reg = SourceRegistry()
        for i in range(5_000):
            reg.register(f"src-{i}", "raw", "one-syndicate")
        assert len(reg) == 5_000
        assert reg.independent_source_count() == 1

    def test_mixed_grouping_at_volume_partitions_exactly(self):
        reg = SourceRegistry()
        for i in range(6_000):
            group = f"g-{i % 300}" if i % 2 == 0 else None
            reg.register(f"src-{i}", "raw", group)
        groups = reg.independence_groups()
        assert sum(len(v) for v in groups.values()) == len(reg)
        # Only even i are grouped, so i % 300 yields 150 distinct groups
        # (the even residues), plus 3000 ungrouped odd singletons.
        expected_groups = len({i % 300 for i in range(6_000) if i % 2 == 0})
        assert reg.independent_source_count() == expected_groups + 3_000

    def test_deep_trust_history_is_never_truncated(self):
        """R-01 / N-04: every version stays resolvable."""
        reg = SourceRegistry()
        reg.register("src-0", "raw")
        for i in range(2_000):
            reg.record_trust("src-0", (i % 101) / 100.0, f"revision {i}")
        history = reg.trust_history("src-0")
        assert len(history) == 2_000
        assert [r.version for r in history] == list(range(1, 2_001))
        assert reg.trust_at_version("src-0", 1).version == 1
        assert reg.trust_at_version("src-0", 2_000).version == 2_000

    def test_unrated_enumeration_scales(self):
        reg = SourceRegistry()
        for i in range(5_000):
            reg.register(f"src-{i}", "raw")
        for i in range(0, 5_000, 2):
            reg.record_trust(f"src-{i}", 0.5, "rated")
        assert len(reg.unrated()) == 2_500


class TestClosedSetHoldsUnderLoad:
    def test_taxonomy_never_extends_however_many_sources_register(self):
        """N-20 S 5.1: the closed set stays exactly eight members regardless
        of access volume; raw strings never classify onto it."""
        reg = SourceRegistry()
        for i in range(3_000):
            reg.register(f"src-{i}", f"raw-type-{i}")
            if i % 500 == 0:
                assert is_ratified_source_type(f"raw-type-{i}") is False
                with pytest.raises(UntypableChannelError):
                    classify(f"raw-type-{i}")
        assert len(taxonomy_members()) == 8
        assert TAXONOMY_RATIFIED is True
        assert reg.source_type_diversity() == 0

    def test_eligibility_stays_undetermined_across_many_assessments(self):
        outcomes = {assess_eligibility(f"src-{i}").outcome for i in range(5_000)}
        assert outcomes == {SourceEligibility.UNDETERMINED}


class TestConcurrency:
    def test_high_contention_registration_loses_nothing(self):
        reg = SourceRegistry()
        errors: list[Exception] = []

        def worker(w: int) -> None:
            try:
                for j in range(250):
                    reg.register(f"src-{w}-{j}", "raw")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(reg) == 2_000

    def test_concurrent_trust_writes_produce_a_dense_version_sequence(self):
        """No lost update, no duplicate version, under contention."""
        reg = SourceRegistry()
        reg.register("src-0", "raw")
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(100):
                    reg.record_trust("src-0", 0.5, "concurrent")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        versions = [r.version for r in reg.trust_history("src-0")]
        assert versions == list(range(1, 801))
        assert len(set(versions)) == len(versions)

    def test_readers_never_observe_a_partial_write(self):
        reg = SourceRegistry()
        for i in range(200):
            reg.register(f"src-{i}", "raw")
        errors: list[Exception] = []
        stop = threading.Event()

        def writer() -> None:
            try:
                for i in range(200):
                    reg.record_trust(f"src-{i}", 0.5, "w")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)
            finally:
                stop.set()

        def reader() -> None:
            try:
                while not stop.is_set():
                    for record in reg:
                        assert record.source_identifier
                        assert record.independence_key
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=writer)] + [
            threading.Thread(target=reader) for _ in range(3)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not errors


class TestPerformance:
    def test_registration_throughput_is_linear_enough(self):
        """Guards against an accidental O(n^2) in registration."""
        reg = SourceRegistry()
        start = time.perf_counter()
        for i in range(20_000):
            reg.register(f"src-{i}", "raw")
        elapsed = time.perf_counter() - start
        # Generous: catches a quadratic blow-up, not micro-regressions.
        assert elapsed < 20.0, f"20k registrations took {elapsed:.2f}s"

    def test_resolution_does_not_degrade_with_registry_size(self):
        reg = SourceRegistry()
        for i in range(20_000):
            reg.register(f"src-{i}", "raw")
        start = time.perf_counter()
        for i in range(0, 20_000, 20):
            reg.resolve(f"src-{i}")
        elapsed = time.perf_counter() - start
        assert elapsed < 5.0, f"1k resolutions took {elapsed:.2f}s"
