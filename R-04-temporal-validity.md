# R-04 — Explicit Temporal Validity, No Automatic Decay

| Field | Value |
|---|---|
| **ID** | R-04 |
| **Title** | Ratify D-04: Explicit Temporal Validity, No Automatic Decay |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | IOM decision D-04 |
| **Closes** | M-46 |
| **Backlog task** | `T00.2.4` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Every object carries:

- `asserted_at` — when the platform formed the claim
- `observed_at` — when the underlying reality was observed, which may substantially precede assertion
- `valid_until` — optional, expected expiry of the claim's currency

**Confidence does not decay automatically with time.**

## Context

v1 has no temporal model (M-46). In a continuously looping platform, every object ages: evidence goes stale, facts become outdated, problems get solved by others, patterns dissolve.

The distinction between `asserted_at` and `observed_at` matters because evidence about the past can be acquired today. An Execution Record in particular may observe an outcome months after the prediction it tests.

## Alternatives Considered

**Option A — Explicit timestamps, no automatic decay (selected).**

**Option B — Automatic time-based confidence decay.**
*Rejected on two independent grounds.* First, decay rates are domain-specific and unknowable in general; any rate the platform applied would be an invented business rule with no evidential basis — precisely what Principle 1 forbids. Second, decaying stored confidence would silently alter an object's content, breaching immutability under D-01.

**Option C — No temporal model.**
*Rejected:* PKP v2 §10.3 establishes staleness as entirely unmanaged in a continuously looping platform. Without timestamps, ageing is not merely unactioned but invisible.

**Option D — Mandatory `valid_until` on every object.**
*Rejected:* forces engines to assert an expiry they often cannot justify. An unjustified expiry is worse than none, because it will be trusted.

## Rationale

Timestamps make ageing **visible**; automatic decay would make it **silently wrong**. The platform can detect staleness and act on it deliberately, rather than having confidence quietly erode at a rate nobody can defend.

Keeping `valid_until` optional means an expiry is asserted only where the producing engine can justify one — consistent with Principle 1 applied to the platform's own metadata.

## What It Binds

- Universal attribute set: `asserted_at`, `observed_at` required; `valid_until` optional.
- **Validation rule V8**: `observed_at ≤ asserted_at ≤ produced_at`.
- **Pattern temporal validity** (`T05.1.6`): explicit `valid_until` with review on breach, not automatic invalidation.
- All nine object types.

## Consequences Accepted

- **Staleness is detectable but not automatically actioned.** Some component must assess currency; none is assigned. This is M-61, open.
- Objects may remain `ACTIVE` long past usefulness with no automatic signal.
- Engines must reason about two timestamps rather than one.

## Known Tensions

**With M-61 (staleness owner, open).** Timestamps make ageing visible but no engine is responsible for acting on it.

**With M-13 (pattern temporal validity, open until `T05.1.6`).** Patterns rest on problems spanning long periods and are the type most exposed to staleness.

## Revisit Conditions

Reconsider if staleness proves unmanageable through explicit review, and evidence emerges supporting domain-specific decay rates that could be applied without inventing a business rule.
