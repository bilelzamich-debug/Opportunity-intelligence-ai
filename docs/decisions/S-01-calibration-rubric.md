# S-1 — Confidence Calibration Rubric

| Field | Value |
|---|---|
| **ID** | S-1 |
| **Title** | Confidence Calibration Rubric |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | M-60 |
| **Backlog task** | `T00.5.1` |
| **Depends on** | [R-3](R-03-confidence-model.md), [N-3](N-03-success-criteria.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

A **shared calibration rubric** defines each confidence band by **observable criteria**, applied identically by all nine engines.

### Band definitions — `assertion_confidence`

| Band | Range | Observable criterion | Test |
|---|---|---|---|
| `NEGLIGIBLE` | 0.00–0.19 | The inference is speculative; a competent reviewer would likely reach a different conclusion from the same inputs | Would I defend this if challenged? *No.* |
| `WEAK` | 0.20–0.39 | The inference is one of several equally plausible readings of the inputs | Are there ≥2 equally good alternative conclusions? *Yes.* |
| `MODERATE` | 0.40–0.59 | The inference is the most plausible reading, but a credible alternative exists | Is there exactly one credible alternative? *Yes.* |
| `STRONG` | 0.60–0.79 | The inference follows from the inputs; alternatives require additional assumptions | Do alternatives need extra assumptions? *Yes.* |
| `VERY_STRONG` | 0.80–1.00 | The inference is the only reading the inputs support without contradiction | Can I construct any non-contradictory alternative? *No.* |

**The operative test is alternative-counting**, not introspection. "How certain do I feel" is not a criterion; "how many credible alternative conclusions do these inputs support" is observable and comparable across engines.

### Worked anchors — two per band

| Band | Anchor A | Anchor B |
|---|---|---|
| `NEGLIGIBLE` | A Problem inferred from a single ambiguous complaint that could describe three unrelated issues | An Opportunity asserted where the Pattern's constituent Problems span unrelated populations |
| `WEAK` | A Pattern grouping four Problems that share vocabulary but no established structural relationship | A Fact extracted from a paraphrase where the original claim's scope is unclear |
| `MODERATE` | A Problem where facts show recurring friction, but whether it constitutes unmet need or accepted cost is genuinely open | An Opportunity whose value depends on an unevidenced behavioural response |
| `STRONG` | A Pattern where constituent Problems share a mechanism, and the alternative explanation requires assuming coordinated unrelated causes | A Fact directly quoted with full qualifying context intact |
| `VERY_STRONG` | A Fact stated verbatim in the source with explicit scope and no ambiguity | A Problem where facts state the deficiency explicitly and the affected population is named in the evidence |

### Cross-engine comparability

Comparability rests on three properties:

1. **A single criterion type.** Every band is defined by alternative-counting, not by engine-specific notions of certainty.
2. **Engine-independent anchors.** Anchors span multiple object types, so an engine calibrates against examples from outside its own stage.
3. **Empirical correction.** N-3's measure **O2 (calibration)** tests whether opportunities asserted at confidence *c* succeed at rate ≈ *c*. From P8, rubric application is corrected against outcomes.

Until O2 data exists, comparability is **argued, not demonstrated** — see Consequences.

## Context

R-3 established two-component confidence with a `min()` ceiling. The ceiling takes the minimum across engines, which is arithmetically valid but **semantically unsound** unless one engine's 0.7 means what another's does.

M-60 recorded this as the deepest unresolved issue in the confidence model. It is blocking because R-1 makes objects immutable: confidence values stored under no rubric cannot be recalibrated retrospectively without re-versioning every object.

## Alternatives Considered

**Option A — Shared rubric with observable criteria and worked anchors (selected).**

**Option B — Numeric guidance only ("0.7 means fairly confident").**
*Rejected:* restates the number in words. Provides no test an engine can apply, so it produces the same inconsistency it purports to fix.

**Option C — Post-hoc empirical calibration only, no rubric.**
*Rejected as sole mechanism:* the most rigorous approach, but requires outcomes that do not exist until P8. Five phases would store uncalibrated values first, and under immutability those cannot be corrected.

**Option D — Per-engine rubrics.**
*Rejected:* better fit per stage, but destroys the cross-engine comparability the ceiling rule requires. It would make `min()` a comparison of incommensurable quantities.

**Option E — Abandon cross-engine comparability.**
*Rejected:* would void R-3's ceiling rule, the platform's structural defence against confidence inflation.

## Rationale

The rubric had to be **applied by engines that cannot consult each other** (Article V), so the criterion must be self-contained and objective enough that independent application converges.

**Alternative-counting was chosen as the criterion** because it is observable and stage-independent. Asking "how many credible alternative conclusions do these inputs support?" produces comparable answers whether the inputs are Evidence spans or Patterns. Asking "how confident are you?" does not.

Anchors deliberately span object types so that an engine calibrating a Pattern can check its judgement against a Fact-level anchor. This is what makes the rubric shared rather than nine parallel rubrics using the same words.

Option C remains correct in the long run and is retained as the second layer: the rubric governs now, O2 corrects it from P8. Rubric-first is not a rejection of empiricism — it is what makes the first five phases' data usable.

## What It Binds

- **`T01.5.5`** calibration conformance: engines assert confidence against this rubric.
- **R-3** the `min()` ceiling becomes semantically meaningful.
- **N-3 measure O2** is the empirical correction mechanism from P8.
- All nine engines asserting `assertion_confidence`.

## Consequences Accepted

- **Comparability is argued, not demonstrated, until P8.** The rubric makes engines *aim* at the same target; only O2 shows whether they hit it.
- **Alternative-counting is judgement.** Two competent reviewers may count differently — the rubric narrows variance rather than eliminating it.
- **Anchors may not generalise** to object types or domains not represented.
- Values stored before empirical correction may prove systematically offset, and under R-1 immutability cannot be revised in place.

## Known Tensions

**With R-1 immutability.** If O2 reveals systematic miscalibration, historical values cannot be corrected — only reinterpreted through a recorded offset.

**With N-4 non-determinism.** The same engine may assert different confidence for identical inputs across runs, so calibration is statistical rather than exact.

**With M-59 (S-2).** `evidential_support` uses a separate computation; only `assertion_confidence` is governed by this rubric.

## Revisit Conditions

**Reconsider from P8**, once O2 calibration data exists. If systematic per-engine offsets are observed, the rubric is refined and the offset recorded — historical values are reinterpreted, never rewritten.
