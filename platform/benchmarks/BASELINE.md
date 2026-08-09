# Performance Baseline

Recorded from `benchmarks/bench_identity.py`. Python 3.13.14.
**Purpose: regression detection, not an optimisation target.**

## T01.1.1 — Identity allocation

| Benchmark | ops/sec | µs/op | Note |
|---|---:|---:|---|
| `new_object` | 87,406 | 11.44 | Two UUID4 generations per call |
| `succeed` (linear chain) | 174,989 | 5.71 | One UUID4; ~2× faster than `new_object` |
| `validate_succession` | 9,895,790 | 0.10 | Pure check, no allocation, no lock |
| `assert_not_reused` | 1,471,558 | 0.68 | Lock-guarded dict lookup |
| `lineage_of` @ 500k table | 1,704,565 | 0.59 | **Flat at scale** — I2 retention does not degrade lookup |
| `new_object` (8 threads) | 48,094 | 20.79 | **Net-negative under contention** |
| `succeed` depth stability | 177,625 | 5.63 | **Flat** — drift +5.4% over 100k depth |
| Memory per identity | — | — | **295 bytes/identity retained** |

## Observations

1. **`new_object` costs ~2× `succeed`** — it generates two UUID4s (object_id + lineage_id) versus one. Expected, not a defect.

2. **Concurrency is net-negative** (87k single-threaded → 48k across 8 threads). The allocator is correct under contention (verified by tests) but the global lock serialises it. Acceptable now: N-11 serialises interpretation anyway, and identity allocation is not the platform bottleneck. **Revisit only if measurement shows it binding.**

3. **Lookup is flat at 500k retired ids** — confirms I2's unbounded retention does not degrade access.

4. **Succession is flat to 100k depth** (+5.4% drift) — important because R-1 + D-05 mean heavily corroborated Facts develop long chains.

5. **295 bytes/identity retained.** At 10M objects ≈ 2.95 GB in identity tracking alone. Feeds N-12 retention planning; the lineage skeleton is permanent by design.

## Regression thresholds

Investigate if any degrades >25% from the figures above, or if depth-stability drift exceeds +20%.
