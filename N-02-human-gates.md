# N-2 — Human Gates at Three Transitions

| Field | Value |
|---|---|
| **ID** | N-2 |
| **Title** | Human Gates at Three Transitions |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | OQ-02, OQ-05 |
| **Backlog task** | `T00.3.2` |
| **Depends on** | `T00.3.1` (N-1) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Human judgement enters the platform at **exactly three gates**. Everywhere else the platform runs autonomously.

| # | Gate | Transition | Decides |
|---|---|---|---|
| **G1** | Opportunity selection | Stage 5 → 6 | Which scored opportunities proceed to solutioning |
| **G2** | Post-validation promotion | Stage 7 → handoff | Whether a validated solution is released to the recipient |
| **G3** | Learning application | Stage 9 | Whether a learning update takes effect |

**No new object states.** Gates use the existing seven-state lifecycle (R-2): a gate rejection is `PROPOSED → REJECTED` with `status_reason`; a gate approval is `PROPOSED → ACTIVE`. Gate decisions are recorded via `status_reason` and, for G3, the Feedback Record's `approval_record`.

**Unbounded-wait behaviour.** Engines **never block** awaiting a gate. An object awaiting a decision remains `PROPOSED` indefinitely; Orchestration continues processing other work. A `PROPOSED` object is not consumable as input (it is not `ACTIVE`), so the pipeline stalls for that object alone, never for the platform.

## Context

v1 makes no reference to human involvement anywhere (OQ-02). Whether the platform is autonomous, gated, or human-in-the-loop is undetermined, as is whether learning updates require approval (OQ-05).

The gap is structural, not operational: it determines whether objects need approval states, whether engines can block for unbounded periods, and who owns the gate decisions that PKP v2 records as unowned (M-28 solution selection, M-31 post-validation promotion).

## Alternatives Considered

**Option A — Fully autonomous.**
*Rejected:* simplest control model but highest risk. The three transitions above are precisely where an error is most expensive: G1 commits cost, G2 releases advice that drives resource allocation, G3 changes platform behaviour globally. Full autonomy also leaves M-28 and M-31 unowned.

**Option B — Human gates at defined transitions (selected).**

**Option C — Human-in-the-loop throughout.**
*Rejected:* highest quality per decision but throughput-limited to human capacity at every stage, which contradicts the vision's "AI-native" commitment. It would also make the platform's discovery function pointless — a system that surfaces opportunities nobody has time to review surfaces nothing.

**Option D — Autonomous with post-hoc human override.**
*Rejected:* override after the fact cannot undo a released recommendation or a committed spend. For G3 in particular, post-hoc override means the platform has already changed behaviour and produced output under the new configuration.

## Rationale

Three gates, chosen by consequence asymmetry rather than by preference for oversight.

- **G1** is the pipeline's most expensive transition (Opportunity → many Solutions → many Validations). It is the platform's only cost throttle.
- **G2** is where output leaves the platform under N-1 and becomes someone's resource decision.
- **G3** changes platform behaviour globally and, under R-1's immutability, produces objects that will carry the new configuration permanently.

Everywhere else, the cost of an error is contained and recoverable: a bad Fact is superseded, a bad Problem is invalidated, a weak Pattern is not selected. Gating those stages would add latency without reducing consequential risk.

**No new object states** was deliberate. Adding `AWAITING_APPROVAL` would have meant a contract change across all nine object types (AD-02) for information the existing `PROPOSED` state already carries. A gate is not a new lifecycle position — it is a *decider* for an existing transition.

## Why Is This Capability Intentionally Outside the Platform?

### Automated decision authority at G1, G2 and G3

**Why outside the platform.** These three decisions require context the evidence base does not contain: organisational capacity and appetite (G1), willingness to act on advice of a given confidence (G2), and tolerance for behavioural change in a live system (G3). The platform can compute a score; it cannot know whether the organisation has the capacity to pursue it this quarter.

**Structural evidence.** PKP v2 leaves M-28 and M-31 unowned precisely because strict separation of concerns (AD-04) creates responsibility voids at decision points between engines. Assigning them to an engine would make that engine a decision-maker, which no v1 engine is.

**Scope-creep pressure to expect.** "The threshold works fine — remove the human." Threshold automation is already permitted; what is retained is *override*. Removing override converts a gate into a rule and transfers accountability to the platform, which N-1 places outside it.

## What It Binds

- **G1** → `T06.4.1` (threshold gating with human override); resolves **M-28**.
- **G2** → `T07.3.7` (post-validation gate); resolves **M-31**. Validation still does not gate — V-I2 preserved; it reports, the gate decides.
- **G3** → `T08.2.8` (learning approval gate); resolves **OQ-05**.
- **Object model:** unchanged. Seven states suffice.
- **Orchestration:** must not block on gates; `PROPOSED` objects are skipped, not awaited.
- **Threshold automation:** gates may be pre-satisfied by threshold policy applied mechanically by Orchestration, with human override retained. Orchestration applies policy; it does not judge (AD-04 preserved).

## Consequences Accepted

- **Three human dependencies in the pipeline.** Throughput at G1, G2 and G3 is bounded by reviewer availability.
- **Indefinite `PROPOSED` accumulation.** Objects awaiting decisions accumulate with no automatic expiry, interacting with M-38 (retention).
- **Gate rejection and engine rejection share one state.** Both are `REJECTED`; they are distinguished only by `status_reason`. Accepted to avoid a contract change.
- Learning is slowed by G3, deliberately.

## Known Tensions

**With the vision's "AI-native" commitment.** Three gates are a genuine constraint on autonomy. Confined to the three highest-consequence transitions to keep the constraint proportionate.

**With M-38 (open).** Indefinitely-`PROPOSED` objects have no retention treatment until N-12.

**With M-31/M-28 (closing).** This decision assigns the owners; the mechanisms are built at `T06.4.1` and `T07.3.7`.

## Revisit Conditions

Reconsider only if:

- Gate latency demonstrably prevents the platform from operating at required throughput **after** threshold automation is in place, **or**
- A fourth transition is shown to carry consequence comparable to G1–G3.

Reviewer inconvenience is not grounds. Removing a gate transfers its accountability to the platform, which requires superseding N-1.
