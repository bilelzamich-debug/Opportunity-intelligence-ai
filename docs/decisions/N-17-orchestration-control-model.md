# N-17 — Orchestration Control Model: Scheduled Batch

| Field | Value |
|---|---|
| **ID** | N-17 |
| **Title** | Orchestration Control Model: Scheduled Batch |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-35, M-37, OQ-15 |
| **Backlog task** | `T00.6.2` |
| **Depends on** | [N-11](N-11-concurrency.md), [N-10](N-10-failure-representation.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Scheduled batch orchestration for P1–P5. Directive, not reactive. Revisit at P6.**

| Property | Decision |
|---|---|
| **Control model** | Scheduled batch — engines invoked on a defined cycle over a bounded work set |
| **Reactive vs directive** | **Directive.** Orchestration executes a plan; it does not react to object availability |
| **Iteration bounding** | Every cycle is bounded by **work-set size** and **wall-clock budget**. A cycle that exhausts either terminates and reports; it never runs unbounded |
| **Loop termination (M-37)** | The platform has no terminal state, but **every cycle does**. Continuous operation is a sequence of bounded cycles |
| **Concurrency** | Per N-11: acquisition and extraction parallel within a cycle; interpretation serialised |
| **Failure handling** | Per N-10: engine failure recorded, cycle continues, failure surfaced — never masked as completion |
| **Revisit** | At P6, when opportunity throughput and cost data exist |

**Directive means Orchestration decides what runs.** It does not watch for objects appearing and trigger downstream work; it plans a cycle, invokes engines over a defined work set, and records what completed.

## Context

v1 does not state whether Orchestration is event-driven, batch, scheduled or continuous (M-35), how loop iteration is bounded (M-37), or whether it is reactive or directive (OQ-15).

Orchestration must exist from P2 onward — no engine can be invoked without it. The control model also determines what processing state must be tracked per object, which is P1 structure.

The platform loops continuously with no terminal state (AD-03) and currently has no cost model (M-56) and no resource limits.

## Alternatives Considered

**Option A — Event-driven.**
*Rejected:* responsive and low-latency, but hard to bound. With no cost model and no terminal state, event-driven operation risks runaway cascades where each object triggers downstream work indefinitely.

**Option B — Scheduled batch (selected).**

**Option C — Continuous streaming.**
*Rejected:* lowest latency, hardest to bound, and incompatible with N-11's serialised interpretation — Pattern Intelligence needs a stable population, which streaming does not provide.

**Option D — Hybrid: scheduled acquisition, event-driven downstream.**
*Rejected for now:* attractive, but combines two control models before either is proven, and the event-driven half inherits Option A's bounding problem at exactly the stages where N-11 requires serialisation.

## Rationale

**Boundedness is the property most needed right now.** With M-56 (cost model) unresolved and no resource limits defined, an unbounded control model could consume without limit before anyone notices. Batch gives every cycle a defined end.

Batch also **matches N-11 exactly**: serialised interpretation needs a stable population, and a batch boundary is precisely that. Pattern Intelligence operating over a population that changes mid-analysis would produce unstable results.

**Directive over reactive** follows from AD-04. A reactive Orchestration decides *when work is ready*, which is a judgement about knowledge state. A directive Orchestration executes a plan over a work set — mechanical, and consistent with the constraint that Orchestration sequences but never judges.

Latency is the accepted cost, and it is acceptable: this is a discovery platform where evidence ages in weeks, not seconds.

## What It Binds

- **`T01.6.1`** scheduled batch invocation.
- **`T01.6.2`** processing-state tracking per cycle.
- **`T01.6.4`** concurrency boundary per N-11.
- **`T01.6.5`** sequencing enforcement.
- **`T09.1.3`** resource limits bound each cycle.
- **M-37** loop termination: cycles terminate, the platform does not.

## Consequences Accepted

- **Higher latency.** Results arrive per cycle, not continuously.
- **Cycle sizing is a tuning problem** with no empirical basis yet — too small wastes overhead, too large delays results and risks budget exhaustion.
- **Upstream backlog risk.** Parallel acquisition can outpace serialised interpretation across cycles, requiring queue bounds.
- **Directive control needs a plan.** Something must decide each cycle's work set; absent a research trigger model (M-01), this is initially manual.

## Known Tensions

**With M-01 (research trigger, open).** Directive control requires knowing what to research. Until `T02.2.4`, work sets are externally specified.

**With M-56 (cost model, open).** Wall-clock budget is a proxy for a cost bound that does not yet exist.

**With Principle 5.** Batch cadence sets learning cadence (M-10), so feedback latency inherits cycle latency.

## Revisit Conditions

**Scheduled revisit at P6**, per the backlog. Revisit earlier if cycle latency demonstrably prevents the platform from surfacing time-sensitive opportunities.
