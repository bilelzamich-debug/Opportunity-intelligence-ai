# N-3 — Success Criteria: Stage Proxies Now, Outcome Measures Frozen Now

| Field | Value |
|---|---|
| **ID** | N-3 |
| **Title** | Success Criteria: Stage Proxies Now, Outcome Measures Frozen Now |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-04 |
| **Backlog task** | `T00.3.3` |
| **Depends on** | `T00.3.1` (N-1) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Two measure families, both defined now.

**Family 1 — Stage-level proxy measures.** Available from each engine phase; serve as phase exit criteria.

| Stage | Proxy measure | Traces to |
|---|---|---|
| 1 Evidence | Provenance completeness; duplicate rate; source-type coverage | P1, AD-01 |
| 2 Facts | **Hallucination rate** (measured, published); anchor resolvability; corroboration rate | P1, AD-01 |
| 3 Problems | Solution-independence conformance; multi-fact support rate | P1, P2 |
| 4 Patterns | Constituent decomposability; source diversity per pattern; artefact-assessment completeness | P1 |
| 5 Opportunities | Score comparability within `score_model_version`; confidence-ceiling conformance | Vision (scores) |
| 6 Solutions | Assumptions per solution; assumption testability rate | P2 |
| 7 Validation | Falsifiability rate; **negative-result proportion**; method reproducibility | P2 |
| 8 Execution | Outcome reporting rate; attribution completeness | P5 |
| 9 Feedback | Learning traceability; reversal coverage; cumulative drift magnitude | P3, P5 |

**Family 2 — Outcome measures. Defined now and frozen.** Evaluable only from P8.

| # | Measure | Question |
|---|---|---|
| O1 | **Prediction accuracy** | Did realised outcomes match predicted value? |
| O2 | **Calibration** | Do opportunities at confidence *c* succeed at rate ≈ *c*? |
| O3 | **Discrimination** | Do higher-scored opportunities outperform lower-scored ones? |
| O4 | **Coverage** | Of opportunities that proved real, how many did the platform surface? |
| O5 | **Precision** | Of opportunities the platform surfaced, how many proved real? |

**Family 2 is frozen on ratification.** Definitions may not be altered once P8 outcome data exists.

## Context

v1 defines no success criteria (M-04). Principle 5 requires improvement; improvement is undefined without a measure. The Feedback Engine has no target function, and no phase has an exit criterion.

Two distinct needs: something measurable **now** to gate phases, and something meaningful **later** to evaluate whether the platform works. Conflating them produces measures that are either unavailable or uninformative.

## Alternatives Considered

**Option A — Outcome-based only.**
*Rejected:* the true measure, but unavailable until P8. Phases P1–P7 would have no exit criteria — six phases built with no definition of done.

**Option B — Stage proxies only.**
*Rejected:* available early but measures process conformance, not value. A platform could score perfectly on every proxy and produce worthless opportunities.

**Option C — Prediction accuracy only.**
*Rejected:* directly usable by the Feedback Engine but requires outcomes, and alone it cannot distinguish a well-calibrated cautious platform from a lucky reckless one.

**Option D — Layered: stage proxies now, outcome measures defined now and frozen (selected).**

**Option E — Defer outcome measures until P8.**
*Rejected, and this is the important rejection.* Defining outcome measures after results exist allows the definition to be shaped — consciously or not — to match what the platform happens to produce. Freezing them now is the only protection against grading on a curve drawn afterwards.

## Rationale

Option D satisfies both needs without letting either corrupt the other.

**Freezing Family 2 now is the load-bearing choice.** The risk is not that outcome measures are hard to define — it is that they are easy to define *favourably* once results are visible. A platform that defines success after seeing its output cannot fail. Fixing O1–O5 before any outcome exists is the only structural defence, and it costs nothing now.

O2 (calibration) deserves specific note: it is the only measure that directly tests R-3's confidence model and is the empirical basis for resolving M-60. It is also the measure a confidently-wrong platform fails first.

The proxies were chosen to be **conformance-measurable without outcomes** and to map to identified failure modes — hallucination rate to the integrity floor, source diversity to sampling artefact, negative-result proportion to confirmation bias.

## Why Is This Capability Intentionally Outside the Platform?

### Business value measurement — deciding whether an opportunity was worth pursuing

**Why outside the platform.** O1–O5 measure whether the *platform* was accurate, not whether the *opportunity* was worthwhile. Whether a realised outcome represents good value depends on the pursuing organisation's cost base, alternatives and objectives — none of which the platform holds. Under N-1 the platform does not adjudicate outcomes (exclusion 5); measuring its own predictive accuracy is a different and legitimate activity.

**Scope-creep pressure to expect.** "Show ROI per opportunity." The platform can report predicted-versus-realised outcome as reported to it. Computing return requires cost and revenue data from outside the evidence base, and asserting it would breach Principle 1.

## What It Binds

- **Phase exit criteria** (M-52): each phase's exit gate uses its stage proxies.
- **`T03.2.3`**: hallucination rate published as a platform quality metric.
- **`T09.1.4`**: stage-level proxy measures implemented.
- **Feedback Engine**: O1–O5 are the improvement targets Principle 5 requires.
- **M-60**: O2 (calibration) is the empirical basis for resolving cross-engine calibration.

## Consequences Accepted

- **Proxies can be optimised without improving outcomes.** Mitigated by freezing Family 2, so proxy gaming is eventually visible against real results.
- **Family 2 is unevaluable until P8** — five of nine phases complete before the platform can be assessed on value.
- **Freezing risks measuring the wrong thing.** Accepted: a fixed imperfect measure is more honest than a perfect one defined retrospectively.
- O4 (coverage) requires knowing about opportunities the platform *missed*, which is only partially observable.

## Known Tensions

**With M-59 and M-60 (open).** Several proxies depend on confidence values whose computation and calibration are unresolved.

**With N-1.** O1–O5 all depend on outcome reports the platform cannot compel.

**With C-02 (open).** No outcomes arrive until outcome intake is assigned.

## Revisit Conditions

**Family 1 (proxies)** may be extended or refined as engines are built; additions require a decision record.

**Family 2 (outcome measures) is frozen.** It may be reconsidered only before P8 outcome data exists. Once any outcome has been observed, changing O1–O5 requires superseding this record with explicit acknowledgement that the measure is being changed after results are visible.
