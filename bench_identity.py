"""Benchmark suite for object identity allocation.

Task: T01.1.1

Architecture References:
- R-1   Objects immutable; change produces a new version
- I2    object_id never reused (retention is unbounded by design)
- N-11  Concurrent acquisition permitted; interpretation serialised
- N-12  Retention: growth is monotonic

Purpose: establish a PERFORMANCE BASELINE, not to optimise. These numbers
exist so that a future regression is visible and so P1 sizing decisions rest
on measurement rather than guesswork.

Run:  python3 benchmarks/bench_identity.py
"""

from __future__ import annotations

import gc
import json
import statistics
import sys
import threading
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from oip.identity import IdentityAllocator, ObjectIdentity  # noqa: E402


@dataclass
class Result:
    name: str
    ops: int
    seconds: float
    detail: str = ""
    extras: dict[str, float] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.extras is None:
            self.extras = {}

    @property
    def per_second(self) -> float:
        return self.ops / self.seconds if self.seconds else float("inf")

    @property
    def us_per_op(self) -> float:
        return (self.seconds / self.ops) * 1_000_000 if self.ops else 0.0


def _time(fn, *args, **kwargs) -> tuple[float, object]:
    gc.collect()
    start = time.perf_counter()
    out = fn(*args, **kwargs)
    return time.perf_counter() - start, out


# ---------------------------------------------------------------------------
# Benchmarks
# ---------------------------------------------------------------------------

def bench_new_object(n: int = 200_000) -> Result:
    """Fresh logical object allocation -- the common path at Evidence intake."""
    allocator = IdentityAllocator()

    def run() -> None:
        for _ in range(n):
            allocator.new_object()

    seconds, _ = _time(run)
    return Result("new_object", n, seconds)


def bench_succeed(n: int = 200_000) -> Result:
    """Linear supersession -- the common path for Fact corroboration. [R-1, D-05]"""
    allocator = IdentityAllocator()
    current = allocator.new_object()

    def run() -> ObjectIdentity:
        nonlocal current
        for _ in range(n):
            current = allocator.succeed(current)
        return current

    seconds, _ = _time(run)
    return Result("succeed (linear chain)", n, seconds)


def bench_validate_succession(n: int = 200_000) -> Result:
    """Pure validation with no allocation -- used on the acceptance path."""
    allocator = IdentityAllocator()
    first = allocator.new_object()
    second = allocator.succeed(first)

    def run() -> None:
        for _ in range(n):
            allocator.validate_succession(first, second)

    seconds, _ = _time(run)
    return Result("validate_succession", n, seconds)


def bench_assert_not_reused(n: int = 200_000) -> Result:
    """Reuse check on an unknown id -- the non-raising path. [I2]"""
    allocator = IdentityAllocator()
    for _ in range(1000):
        allocator.new_object()

    def run() -> None:
        for i in range(n):
            allocator.assert_not_reused(f"obj-absent-{i}")

    seconds, _ = _time(run)
    return Result("assert_not_reused", n, seconds)


def bench_lookup_at_scale(populate: int = 500_000, probes: int = 100_000) -> Result:
    """Lookup cost once the allocator holds many retired ids. [I2, N-12]

    I2 means issued ids are never pruned, so lookup must not degrade as the
    platform accumulates history.
    """
    allocator = IdentityAllocator()
    ids = [allocator.new_object().object_id for _ in range(populate)]
    sample = ids[:: max(1, populate // probes)][:probes]

    def run() -> None:
        for oid in sample:
            allocator.lineage_of(oid)

    seconds, _ = _time(run)
    return Result(
        "lineage_of (500k populated)", len(sample), seconds, f"table={populate:,}"
    )


def bench_concurrent_allocation(threads: int = 8, per_thread: int = 25_000) -> Result:
    """Throughput under contention. [N-11]

    Allocation is lock-guarded, so this measures the cost of that lock and
    confirms concurrency is safe rather than fast.
    """
    allocator = IdentityAllocator()
    barrier = threading.Barrier(threads)

    def worker() -> None:
        barrier.wait()
        for _ in range(per_thread):
            allocator.new_object()

    workers = [threading.Thread(target=worker) for _ in range(threads)]

    def run() -> None:
        for t in workers:
            t.start()
        for t in workers:
            t.join()

    seconds, _ = _time(run)
    total = threads * per_thread
    assert allocator.issued_count() == total, "concurrent allocation lost writes"
    return Result(
        "new_object (concurrent)", total, seconds, f"{threads} threads"
    )


def bench_memory_per_identity(n: int = 200_000) -> Result:
    """Retained memory per issued identity. [I2, N-12]

    Ids are never pruned, so per-identity cost sets the floor on long-run
    memory. This informs N-12 retention planning.
    """
    gc.collect()
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]

    allocator = IdentityAllocator()
    start = time.perf_counter()
    for _ in range(n):
        allocator.new_object()
    seconds = time.perf_counter() - start

    peak = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    bytes_each = (peak - baseline) / n
    return Result(
        "memory per identity", n, seconds, f"{bytes_each:,.0f} bytes/identity",
        extras={"bytes_per_identity": bytes_each},
    )


def bench_chain_depth_stability(depth: int = 100_000, samples: int = 10) -> Result:
    """Succession cost must not degrade with chain depth.

    Chains grow without bound under R-1 (a heavily corroborated Fact
    supersedes on every attachment), so this must stay flat.
    """
    allocator = IdentityAllocator()
    current = allocator.new_object()
    bucket = depth // samples
    timings: list[float] = []

    total_start = time.perf_counter()
    for _ in range(samples):
        start = time.perf_counter()
        for _ in range(bucket):
            current = allocator.succeed(current)
        timings.append((time.perf_counter() - start) / bucket * 1_000_000)
    total = time.perf_counter() - total_start

    first, last = timings[0], timings[-1]
    drift = ((last - first) / first * 100) if first else 0.0
    return Result(
        "succeed (depth stability)",
        bucket * samples,
        total,
        f"first={first:.2f}us last={last:.2f}us drift={drift:+.1f}%",
        extras={"drift_pct": drift},
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

BENCHMARKS = (
    bench_new_object,
    bench_succeed,
    bench_validate_succession,
    bench_assert_not_reused,
    bench_lookup_at_scale,
    bench_concurrent_allocation,
    bench_memory_per_identity,
    bench_chain_depth_stability,
)


BASELINE_PATH = Path(__file__).with_name("baseline.json")


def _load_baseline() -> dict | None:
    if not BASELINE_PATH.exists():
        return None
    with BASELINE_PATH.open() as fh:
        return json.load(fh)


def _write_baseline(results: list[Result]) -> None:
    existing = _load_baseline() or {}
    payload = {
        "_comment": existing.get(
            "_comment",
            "Machine-readable performance baseline. Regenerate with: "
            "python3 benchmarks/bench_identity.py --write-baseline",
        ),
        "_purpose": existing.get(
            "_purpose", "Regression detection, not an optimisation target."
        ),
        "_thresholds": existing.get(
            "_thresholds",
            {
                "throughput_regression_pct": 25.0,
                "drift_regression_pct": 20.0,
                "memory_regression_pct": 25.0,
            },
        ),
        "python": sys.version.split()[0],
        "recorded": time.strftime("%Y-%m-%d"),
        "task": "T01.1.1",
        "benchmarks": {
            r.name: {
                "ops_per_sec": round(r.per_second, 1),
                "us_per_op": round(r.us_per_op, 2),
                **{k: round(v, 2) for k, v in r.extras.items()},
            }
            for r in results
        },
    }
    with BASELINE_PATH.open("w") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")
    print(f"\nbaseline written to {BASELINE_PATH}")


@dataclass
class Regression:
    name: str
    metric: str
    baseline: float
    current: float
    change_pct: float


def compare_to_baseline(results: list[Result], baseline: dict) -> list[Regression]:
    """Detect significant regressions against the recorded baseline.

    Throughput regressions are reported when current is materially SLOWER.
    Improvements are never reported as regressions.
    """
    thresholds = baseline.get("_thresholds", {})
    thr_tp = thresholds.get("throughput_regression_pct", 25.0)
    thr_drift = thresholds.get("drift_regression_pct", 20.0)
    thr_mem = thresholds.get("memory_regression_pct", 25.0)
    recorded = baseline.get("benchmarks", {})

    found: list[Regression] = []
    for result in results:
        prior = recorded.get(result.name)
        if not prior:
            continue

        base_tp = prior.get("ops_per_sec")
        if base_tp:
            change = (result.per_second - base_tp) / base_tp * 100.0
            if change < -thr_tp:
                found.append(
                    Regression(result.name, "throughput", base_tp,
                               result.per_second, change)
                )

        base_mem = prior.get("bytes_per_identity")
        cur_mem = result.extras.get("bytes_per_identity")
        if base_mem and cur_mem:
            change = (cur_mem - base_mem) / base_mem * 100.0
            if change > thr_mem:
                found.append(
                    Regression(result.name, "memory", base_mem, cur_mem, change)
                )

        base_drift = prior.get("drift_pct")
        cur_drift = result.extras.get("drift_pct")
        if base_drift is not None and cur_drift is not None:
            if cur_drift > thr_drift:
                found.append(
                    Regression(result.name, "depth drift", base_drift,
                               cur_drift, cur_drift - base_drift)
                )
    return found


def main() -> int:
    print("=" * 78)
    print("IDENTITY ALLOCATION BASELINE  --  T01.1.1")
    print(f"python {sys.version.split()[0]}")
    print("=" * 78)
    print(f"{'benchmark':<32}{'ops':>10}{'ops/sec':>14}{'us/op':>10}  detail")
    print("-" * 78)

    results: list[Result] = []
    for bench in BENCHMARKS:
        result = bench()
        results.append(result)
        print(
            f"{result.name:<32}{result.ops:>10,}{result.per_second:>14,.0f}"
            f"{result.us_per_op:>10.2f}  {result.detail}"
        )

    print("-" * 78)
    rates = [r.per_second for r in results if r.name != "memory per identity"]
    print(f"median throughput: {statistics.median(rates):,.0f} ops/sec")

    if "--write-baseline" in sys.argv:
        _write_baseline(results)
        return 0

    baseline = _load_baseline()
    if baseline is None:
        print("\nno baseline recorded; run with --write-baseline to create one")
        return 0

    print()
    print("=" * 78)
    print(f"REGRESSION CHECK vs baseline recorded {baseline.get('recorded')}")
    print("=" * 78)

    regressions = compare_to_baseline(results, baseline)
    if not regressions:
        thr = baseline.get("_thresholds", {}).get("throughput_regression_pct", 25.0)
        print(f"PASS -- no metric regressed beyond {thr:.0f}%")
        return 0

    for reg in regressions:
        print(
            f"REGRESSION  {reg.name} [{reg.metric}]  "
            f"baseline={reg.baseline:,.1f}  current={reg.current:,.1f}  "
            f"change={reg.change_pct:+.1f}%"
        )
    print(f"\n{len(regressions)} regression(s) detected")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
