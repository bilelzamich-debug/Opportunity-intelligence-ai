# N-13 — Explanation Skeleton

| Field | Value |
|---|---|
| **ID** | N-13 |
| **Title** | Explanation Skeleton |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | M-07 |
| **Backlog task** | `T00.5.6` |
| **Depends on** | — |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Every `explanation` follows a **mandatory four-part skeleton**, with reasoning as free text.

| # | Field | Content | Checkable |
|---|---|---|---|
| 1 | **Objects referenced** | Identifiers of the specific input objects used | **Yes** — structurally |
| 2 | **Criteria applied** | Which rules, thresholds or tests governed the judgement | **Yes** — non-empty |
| 3 | **Reasoning** | Free text: why these inputs, under these criteria, produce this output | Non-empty only |
| 4 | **Alternatives rejected** | Other conclusions considered and why declined — required where the engine chose among candidates | **Yes** — conditionally |

**V6 becomes structurally checkable:** field 1 must be non-empty and every identifier must resolve to an object in the producing engine's actual inputs. An explanation that references nothing, or references objects the engine never read, is rejected at acceptance.

**Uniform across all nine engines.** The skeleton does not vary by stage. Reasoning content varies; structure does not.

Field 4 is required whenever the engine selected among alternatives — which candidate Solutions to produce, which Problems constitute a Pattern, whether to merge a Fact. It is omitted only where no alternative existed.

## Context

`explanation` is a universal required attribute mandated by Principle 2, but its form, granularity and minimum content were undefined (M-07).

Every object write populates it. Without a standard, nine engines produce nine incompatible styles, explanations are not comparable or auditable, and V6 ("explanation references at least one input object") cannot be checked.

Under R-1 immutability, explanations written under no standard cannot be normalised later.

## Alternatives Considered

**Option A — Free text with a minimum-content rule.**
*Rejected:* maximally flexible, weakly enforceable. "Must reference inputs" is unverifiable in prose.

**Option B — Fully structured: inputs, criteria, reasoning steps, conclusion.**
*Rejected:* comparable and checkable, but forces model-driven reasoning into a step form it does not naturally produce, yielding stilted or fabricated "steps".

**Option C — Structured skeleton with free-text reasoning (selected).**

**Option D — Per-engine formats.**
*Rejected:* best fit per stage, not comparable across stages, and would make cross-object audit impossible.

## Rationale

The skeleton makes the **checkable parts checkable** and leaves the **unformalisable part free**.

Fields 1, 2 and 4 are structural: they can be validated at acceptance without interpreting content. Field 3 is where actual reasoning lives and is deliberately unconstrained, because forcing model-driven inference into formal steps produces post-hoc rationalisation rather than explanation.

**Field 4 is the addition that matters most.** Principle 2 requires that rejections be explainable, and PKP v2 names silent filtering as a forbidden anti-pattern. Recording rejected alternatives at the point of decision is the only way that requirement becomes real — and it is also the record that makes later learning possible.

## What It Binds

- **Universal attribute** `explanation` on all nine object types.
- **Validation rule V6** structurally checkable.
- **`T01.4.3`** V6 enforcement at acceptance.
- All nine engines.
- **`T09.1.2`** explanation-derived quality signals become measurable.

## Consequences Accepted

- **Authoring overhead on every object.** Justified: an unenforceable explanation requirement is not a requirement.
- **Field 4 is verifiable only for existence**, not for honesty — an engine could record trivial alternatives.
- **Free-text reasoning remains unverifiable.** The skeleton guarantees structure, never quality.
- Explanations grow storage on every object under immutability.

## Known Tensions

**With N-4 non-determinism.** Reasoning text varies between runs for identical inputs; only structure is stable.

**With M-38 retention.** Explanations are content and subject to tiering when unreachable — including for `REJECTED` objects, whose explanations carry learning value.

## Revisit Conditions

Reconsider if measured explanation quality (`T09.1.2`) shows the skeleton is being satisfied formally while reasoning remains uninformative — indicating a need for stronger constraints on field 3.
