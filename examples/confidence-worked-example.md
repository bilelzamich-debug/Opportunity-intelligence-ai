# Confidence Ceiling — Worked Example

Reproduced from **IOM §2.3** and implemented as a Phase-1 regression test.

## The rule (R-3, V5)

```
effective_confidence ≤ min(upstream effective_confidence)
```

Evidence sets the ceiling; nothing constrains it from above.

## The example

| Step | Object | Asserted | Ceiling | Effective | Band |
|---|---|---|---|---|---|
| 1 | Evidence | 0.55 | — (root) | **0.55** | MODERATE |
| 2 | Fact ← Evidence | 0.80 | 0.55 | **0.55** (capped) | MODERATE |

The Fact's engine asserted 0.80. The ceiling capped it to 0.55. **The band
follows the capped value, not the assertion.**

## Why this matters

Without the ceiling, a chain of four confident inferences over weak evidence
would present as highly certain. Article X:

> *"Certainty degrades as reasoning moves further from observation, and the
> platform's confidence must degrade with it — a conclusion drawn through four
> inferential steps is never more certain than the evidence beneath it."*

## As a test

The P1 exit gate verifies this reproduces exactly. Note the test asserts the
**property** (`effective ≤ min(upstream)`), never equality on an engine's
output — Playbook **F11**, per N-4.

## A defect this area produced

`BandCriterion.contains()` returned `False` for 0.195, 0.395, 0.599 and 0.799
— S-1's printed two-decimal ranges leave gaps between bands. Fixed by
delegating to the authoritative band lookup. Found at `T01.5.5`.
