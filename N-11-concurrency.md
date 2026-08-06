# N-11 — Concurrency: Parallel Acquisition, Serialised Interpretation

| Field | Value |
|---|---|
| **ID** | N-11 |
| **Title** | Concurrency: Parallel Acquisition, Serialised Interpretation |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | OQ-13 |
| **Backlog task** | `T00.4.6` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Acquisition and extraction may run concurrently. Interpretation from Problem onward is serialised.**

| Stages | Concurrency |
|---|---|
| 1 Evidence, 2 Facts | **Concurrent** — operations are independent per source |
| 3 Problems … 9 Feedback | **Serialised** — one batch at a time |

**Consequences.** Pattern Intelligence sees a **stable Problem population** within a batch. Version branching is impossible, since a single engine holds create authority per type and runs one batch at a time.

**Graph scope (OQ-14) remains open** and is not constrained by this decision.

## Context

v1 does not state whether multiple pipeline traversals may run concurrently (OQ-13).

The question determines whether the Store needs write serialisation, whether Pattern Intelligence's "full problem population" is well-defined at any instant, and whether version chains can branch — all P1 structural properties.

R-1's linear non-branching supersession assumes serialised versioning per object type; that assumption holds only if the owning engine runs single-threaded.

## Alternatives Considered

**Option A — Strictly sequential, single traversal.**
*Rejected:* simplest and gives Pattern Intelligence a stable population, but unusable at volume. Evidence acquisition is I/O-bound across many independent sources; serialising it wastes the platform's most parallelisable work.

**Option B — Concurrent traversals, partitioned knowledge.**
*Rejected:* scalable, but partitioning forecloses cross-domain pattern recognition — the platform's most distinctive capability. Patterns that span domains are precisely the ones no individual observer would find.

**Option C — Concurrent traversals, shared global knowledge.**
*Rejected:* preserves cross-domain patterns but requires full concurrency control over the interpretation stages, where cross-object consistency matters most and where Pattern Intelligence needs a stable population.

**Option D — Concurrent acquisition and extraction; serialised interpretation (selected).**

## Rationale

Option D matches the platform's actual volume and consistency profile.

**Volume is upstream.** Evidence and Facts are the high-volume stages (the expand phase of the cardinality profile), and their operations are genuinely independent — acquiring from two sources, or extracting from two Evidence objects, requires no coordination. This is where parallelism pays.

**Consistency matters downstream.** From Problem onward, engines reason across the accumulated population. Pattern Intelligence in particular cannot produce stable results over a population that is changing beneath it.

Making interpretation the throughput bottleneck is acceptable — and arguably correct. It is where quality matters most and where rushing is most damaging.

## What It Binds

- **`T01.6.4`** concurrency control: Problem-stage-onward writes serialised.
- **`T05.1.1`** Pattern Intelligence operates on a stable population per batch.
- **R-1** non-branching supersession guaranteed.
- **N-6** asynchronous graph index update must tolerate concurrent upstream writes.
- **`T01.6.1`** batch model consistent with serialised interpretation.

## Consequences Accepted

- **Interpretation is the throughput ceiling.** Downstream stages cannot be scaled by parallelism without revisiting this.
- **Batch latency.** Serialised interpretation means results arrive per batch, not continuously.
- **Upstream backlog risk.** Concurrent acquisition can outpace serialised interpretation, producing queue growth that must be bounded.

## Known Tensions

**With OQ-14 (open).** Graph scope is unconstrained here, but if partitioning is later chosen it will interact with serialised interpretation.

**With M-56 (cost model, open).** Concurrency limits on acquisition need a cost bound that does not yet exist.

## Revisit Conditions

Reconsider if interpretation throughput becomes the binding constraint on platform value **and** a concurrency model preserving population stability for Pattern Intelligence is identified.
