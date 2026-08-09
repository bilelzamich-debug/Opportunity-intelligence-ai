# N-18 — Orchestration Phased into P1

| Field | Value |
|---|---|
| **ID** | N-18 |
| **Title** | Orchestration Phased into P1 |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | C-08 |
| **Backlog task** | `T00.6.3` |
| **Depends on** | [N-17](N-17-orchestration-control-model.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Baseline Orchestration is scoped into P1** as foundation infrastructure. Advanced capability increments in later phases.

### Baseline — P1

| Capability | Backlog task |
|---|---|
| Scheduled batch invocation | `T01.6.1` |
| Processing-state tracking | `T01.6.2` |
| Failure surfacing | `T01.6.3` |
| Concurrency boundary enforcement | `T01.6.4` |
| Sequencing enforcement | `T01.6.5` |

### Advanced — later phases

| Capability | Phase |
|---|---|
| Backlog management across cycles | P2+ |
| Resource governance and budgets | P2 (`T09.1.3`) |
| Research directive scheduling | P2 (`T02.2.4`) |
| Cascade invalidation invocation | P1 mechanism (N-9), routine use P2+ |
| Learning cadence scheduling | P8 (`T08.2.7`) |

**No new phase is created.** The roadmap's nine phases are unchanged; P1's scope is clarified to include what was always implicitly required.

## Context

C-08: the Orchestration Engine appears in no roadmap phase, yet no pipeline engine can be invoked without it.

Every other engine has a dedicated phase (P2–P8). Orchestration — which sequences all of them — was unscheduled. Either it is built in P1, which v1 does not state, or the roadmap is unexecutable as written.

The dependency is immediate: P2 (Research) cannot run without invocation.

## Alternatives Considered

**Option A — Baseline Orchestration built in P1 (selected).**

**Option B — A new phase P1.5.**
*Rejected:* explicit, but changes the roadmap's structure to solve a scoping question. The roadmap's nine phases follow the pipeline; inserting a control phase breaks that correspondence.

**Option C — Orchestration capability incremented within each engine phase.**
*Rejected:* matches need precisely, but risks no coherent control model — each phase would add what it needs, and the result would be nine partial orchestrations with no unified sequencing guarantee.

**Option D — Manual invocation until a later phase.**
*Rejected:* defers cost, but means P2–P5 are not operating as a platform. Sequencing enforcement and idempotence would be human responsibilities, and the failure modes N-10 exists to prevent would recur manually.

## Rationale

P1 already owns the platform's least changeable layer. Orchestration's baseline — invocation, state tracking, failure surfacing, sequencing — is **foundation infrastructure in the same sense as the Knowledge Store**: everything else depends on it and nothing works without it.

The baseline/advanced split keeps P1 tractable. What P1 needs is the *ability to invoke engines in the correct order, track what completed, and surface failures*. Backlog management, resource governance and directive scheduling are genuinely later concerns that depend on operational data P1 will not have.

**P1 becoming the largest phase is accepted.** It already was: coherence in the foundation layer is worth more than phase symmetry.

## What It Binds

- **P1 scope** formally includes `T01.6.1`–`T01.6.5`.
- **C-08** closed — Orchestration has a phase.
- **N-17** control model is what P1 implements.
- **P1 exit criteria** (`T01.8.1`) include sequencing enforcement.

## Consequences Accepted

- **P1 is the largest phase**, now spanning knowledge foundation, object realisation and baseline control.
- **Orchestration is built before its consumers exist**, so its baseline is validated against engines that arrive in P2+.
- **The baseline/advanced boundary is a judgement** and may prove misplaced — some advanced capability may turn out to be needed earlier.

## Known Tensions

**With the roadmap's engine-per-phase pattern.** Orchestration is the only engine without a dedicated phase, now resolved by folding it into foundation rather than by creating one.

**With M-01 (open).** Directive control needs research targets; P1's baseline can invoke but has nothing meaningful to schedule until P2.

## Revisit Conditions

Reconsider if P1 proves unmanageably large in execution, in which case Option B (a separate control phase) becomes preferable to descoping the baseline.
