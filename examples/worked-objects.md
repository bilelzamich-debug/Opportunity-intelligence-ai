# Worked Objects — from the Intelligence Object Model
Extracted verbatim from the IOM's `#### Example` blocks.
**Illustrative, not normative.**

---

## Evidence

```
object_id:            EV-8841
object_type:          Evidence
version:              1
lineage_id:           EVL-8841
produced_by_engine:   Research
derives_from:         [] 
source_identifier:    marketplace-listing-corpus / seller-reviews / segment-A
source_type:          customer_review_corpus
acquisition_method:   bulk_corpus_retrieval
acquired_at:          2026-03-14T09:20:00Z
observed_at:          2026-03-01T00:00:00Z
content_reference:    <resolvable reference to preserved corpus snapshot>
content_fingerprint:  <fingerprint of preserved content>
access_conditions:    corpus licence terms, attribution required
capture_fidelity:     full text preserved; embedded media not captured
evidential_support:   0.62  (STRONG)
assertion_confidence: 0.90  (VERY_STRONG)
effective_confidence: 0.62  (STRONG)
status:               ACTIVE
explanation:          Acquired under research directive covering seller-side
                      friction in segment A. Corpus selected for date coverage
                      and volume; media omitted as out of extraction scope.
```

---

## Fact

```
object_id:                 FA-2207
object_type:               Fact
version:                   3
lineage_id:                FAL-2207
produced_by_engine:        Fact Extraction
derives_from:              [EV-8841 v1, EV-8902 v1, EV-9013 v1]
claim:                     Sellers in segment A report that bulk listing
                           updates fail silently when more than 50 items are
                           modified in one operation.
claim_type:                ASSERTION
qualifying_context:        Reported for operations exceeding 50 items;
                           smaller batches not described as affected.
evidence_attachments:
  - evidence_ref:          EV-8841 v1
    positional_anchor:     review corpus / entry 4471 / lines 3-6
    extraction_confidence: 0.88
    independence_assessment: independent
  - evidence_ref:          EV-8902 v1
    positional_anchor:     forum thread 220 / post 12
    extraction_confidence: 0.79
    independence_assessment: independent
  - evidence_ref:          EV-9013 v1
    positional_anchor:     support transcript 88 / turn 9
    extraction_confidence: 0.84
    independence_assessment: independent
independent_source_count:  3
evidential_support:        0.71  (STRONG)
assertion_confidence:      0.84  (VERY_STRONG)
effective_confidence:      0.62  (STRONG)   ← ceiling from EV-8841 (0.62)
status:                    ACTIVE
explanation:               Three mutually independent sources across distinct
                           channels attest the same failure condition with
                           consistent threshold. Version 3 adds EV-9013.
```

---

## Problem

```
object_id:            PR-0912
object_type:          Problem
version:              2
lineage_id:           PRL-0912
produced_by_engine:   Problem Intelligence
derives_from:         [FA-2207 v3, FA-2311 v1, FA-2402 v2]
supporting_facts:     [FA-2207 v3, FA-2311 v1, FA-2402 v2]
problem_statement:    Sellers managing large inventories lose update work
                      without notification when batch operations exceed
                      platform limits, and discover the loss only later
                      through customer complaints.
affected_population:  Segment A sellers maintaining inventories above
                      approximately 50 active listings.
problem_domain:       Marketplace inventory management
severity:             HIGH — unnoticed loss reaches end customers
frequency:            RECURRENT — reported across multiple periods
inference_basis:      FA-2207 establishes silent failure above a threshold.
                      FA-2311 establishes sellers are unaware until customers
                      report. FA-2402 establishes rework cost. Together these
                      show an unmet need for reliable batch feedback, not
                      merely an inconvenience.
evidential_support:   0.66  (STRONG)
assertion_confidence: 0.74  (STRONG)
effective_confidence: 0.62  (STRONG)   ← ceiling from FA-2207
status:               ACTIVE
explanation:          Version 2 adds FA-2402, establishing cost. Statement
                      deliberately excludes any remedy: it describes the
                      deficiency and its consequence only.
```

---

## Pattern

```
object_id:            PT-0334
object_type:          Pattern
version:              4
lineage_id:           PTL-0334
produced_by_engine:   Pattern Intelligence
derives_from:         [PR-0912 v2, PR-1044 v1, PR-1130 v3, PR-1201 v1]
constituent_problems: [PR-0912 v2, PR-1044 v1, PR-1130 v3, PR-1201 v1]
pattern_statement:    Bulk operations across marketplace seller tooling fail
                      silently at undocumented thresholds, with sellers
                      discovering failures only through downstream customer
                      impact rather than system feedback.
pattern_type:         CROSS_DOMAIN_SIMILARITY
pattern_scope:        Marketplace seller tooling; segment A and adjacent
                      segments; observed across 2025-2026 periods.
grouping_rationale:   All four problems share a structure: a silent threshold
                      failure, absence of feedback, and delayed discovery via
                      third parties. PR-0912 and PR-1044 concern listing
                      updates; PR-1130 concerns bulk pricing; PR-1201 concerns
                      inventory sync. The shared structure is the missing
                      feedback channel, not the specific operation, which is
                      why this is treated as one pattern across four domains.
source_diversity:     11 independent Evidence sources across 4 channel types
artefact_assessment:  Not attributable to research bias. Constituents derive
                      from four acquisition efforts across distinct source
                      types; no single source contributes to more than one
                      constituent problem.
evidential_support:   0.64  (STRONG)
assertion_confidence: 0.71  (STRONG)
effective_confidence: 0.62  (STRONG)   ← ceiling from PR-0912
status:               ACTIVE
explanation:          Version 4 adds PR-1201, extending the pattern to
                      inventory sync and raising source diversity from 8 to 11.
```

---

## Opportunity

```
object_id:            OP-0157
object_type:          Opportunity
version:              1
lineage_id:           OPL-0157
produced_by_engine:   Opportunity Intelligence
derives_from:         [PT-0334 v4]
originating_patterns: [PT-0334 v4]
opportunity_statement: Provide marketplace sellers with reliable, immediate
                      feedback on the outcome of bulk operations, so that
                      partial or total failure is known at the time it occurs
                      rather than discovered through customer impact.
beneficiary_population: Segment A sellers and adjacent segments operating at
                      inventory scale, across multiple marketplace tools.
value_hypothesis:     The pattern shows a consistent absence of feedback across
                      four operational domains, with cost borne as rework and
                      customer-facing error. Value arises from eliminating
                      delayed discovery, which is where the cost concentrates.
score:                <UNPOPULATED — MISSING-14>
score_basis:          <UNPOPULATED — MISSING-14>
score_model_version:  <UNPOPULATED — MISSING-14>
scoring_explanation:  <UNPOPULATED — MISSING-14>
evidential_support:   0.64  (STRONG)
assertion_confidence: 0.58  (MODERATE)
effective_confidence: 0.58  (MODERATE)  ← own assertion below Pattern ceiling
status:               PROPOSED
explanation:          Derived from PT-0334, which establishes the structure
                      across four domains. Statement describes the outcome
                      sought, not any mechanism for achieving it. Assertion
                      confidence is set below evidential support because
                      whether sellers would switch tooling for this alone
                      is not established by the underlying evidence.
```

---

## Solution

```
object_id:            SO-0402
object_type:          Solution
version:              2
lineage_id:           SOL-0402
produced_by_engine:   Solution Intelligence
derives_from:         [OP-0157 v1]
addresses_opportunity: OP-0157 v1
candidate_group:      OP-0157-candidates
solution_statement:   A pre-commit validation and post-operation reconciliation
                      layer for bulk seller operations, reporting per-item
                      outcome immediately on completion and surfacing partial
                      failures explicitly rather than reporting operation-level
                      success.
problem_fit_rationale: PR-0912 establishes silent failure with delayed
                      discovery; PR-1130 and PR-1201 establish the same across
                      pricing and sync. Per-item outcome reporting addresses
                      the shared missing-feedback structure identified in
                      PT-0334 rather than any single operation type.
assumptions:
  - assumption_id:      A1
    assumption_statement: Sellers will act on per-item failure reports rather
                        than ignoring them at volume.
    criticality:        CRITICAL — solution fails if reports are ignored
    testability:        Observable via response rates to existing partial-
                        failure notifications in comparable tooling
  - assumption_id:      A2
    assumption_statement: Per-item outcome reporting is achievable within
                        acceptable operation latency at inventory scale.
    criticality:        CRITICAL
    testability:        Measurable against known operation volumes
  - assumption_id:      A3
    assumption_statement: The failure thresholds are stable enough to validate
                        against rather than varying unpredictably.
    criticality:        MODERATE — solution degrades but survives if false
    testability:        Testable against threshold observations in FA-2207
constraints:          <PARTIAL — MISSING-24, no constraint model>
feasibility_assessment: Feasible in principle; A2 is the binding uncertainty.
evidential_support:   0.64  (STRONG)
assertion_confidence: 0.61  (STRONG)
effective_confidence: 0.58  (MODERATE)  ← ceiling from OP-0157
status:               ACTIVE
explanation:          Version 2 adds A3 following review of threshold
                      stability. One of three sibling candidates in
                      OP-0157-candidates; retained for comparative validation.
```

---

## Validation

```
object_id:              VA-0771
object_type:            Validation
version:                1
lineage_id:             VAL-0771
produced_by_engine:     Validation
derives_from:           [SO-0402 v2]
tests_claim:            SO-0402 v2 / assumption A1
validation_method:      <VOCABULARY UNDEFINED — MISSING-25>
method_detail:          Examined response behaviour to existing partial-failure
                        notifications across three comparable seller tools,
                        using observed remediation rates within 48 hours of
                        notification as the behavioural indicator.
result:                 PARTIALLY_SUPPORTED
result_detail:          Remediation occurred in the majority of cases where
                        fewer than 20 items failed, but rates declined sharply
                        above that threshold, with most high-volume failures
                        left unremediated.
result_interpretation:  A1 holds at low failure volumes but not at high ones.
                        Since the underlying problem concerns large inventories,
                        the assumption is weakest precisely where the
                        opportunity is strongest. This does not invalidate
                        SO-0402 but materially narrows its claimed value.
scope_limitations:      Establishes nothing about response to a redesigned
                        reporting mechanism; measures behaviour under existing
                        notification designs only. Does not test A2 or A3.
validated_at:           2026-05-02T00:00:00Z
evidential_support:     0.58  (MODERATE)
assertion_confidence:   0.72  (STRONG)
effective_confidence:   0.58  (MODERATE)
status:                 ACTIVE
explanation:            Test targeted A1 specifically as the assumption marked
                        CRITICAL with the clearest observable proxy. Result is
                        unfavourable in part and recorded as ACTIVE; the
                        finding is durable knowledge regardless of whether it
                        favours the solution.
```

---

## Execution

```
object_id:              XR-0088
object_type:            Execution Record
version:                1
lineage_id:             XRL-0088
produced_by_engine:     <UNDEFINED — CONTRADICTION-02>
derives_from:           [SO-0402 v2]
outcome_of_solution:    SO-0402 v2
execution_description:  Per-item outcome reporting introduced for bulk listing
                        operations in a limited seller cohort, with partial
                        failures surfaced at operation completion.
executed_at:            2026-06-01T00:00:00Z
outcome_observed_at:    2026-07-15T00:00:00Z
outcome:                Silent-failure complaints from the cohort fell
                        substantially. Remediation of reported failures
                        remained low at high failure volumes, consistent with
                        the VA-0771 finding.
outcome_valence:        MIXED
attribution_assessment: Complaint reduction is plausibly attributable, as no
                        other change affected the cohort in the period.
                        Remediation behaviour is not attributable to the
                        solution, since it reflects seller response capacity
                        rather than reporting availability.
prediction_comparison:  OP-0157 predicted value from eliminating delayed
                        discovery. Discovery delay was reduced as predicted.
                        The predicted downstream benefit was only partially
                        realised, matching the narrowing VA-0771 identified.
outcome_verification:   <PARTIAL — MISSING-47, no verification standard>
external_factors:       Seasonal volume variation in the observation period.
evidential_support:     0.55  (MODERATE)
assertion_confidence:   0.47  (MODERATE)
effective_confidence:   0.47  (MODERATE)
status:                 ACTIVE
explanation:            Records both the confirmed and unconfirmed portions of
                        the prediction. Attribution is limited deliberately:
                        the favourable portion is attributable, the
                        unfavourable portion is not clearly so, and the record
                        states both rather than resolving to a single verdict.
```

---

## Feedback

```
object_id:              FR-0021
object_type:            Feedback Record
version:                1
lineage_id:             FRL-0021
produced_by_engine:     Feedback
derives_from:           [XR-0088 v1, XR-0091 v1, XR-0103 v2]
motivating_records:     [XR-0088 v1, XR-0091 v1, XR-0103 v2]
lesson_statement:       Opportunities whose value depends on a behavioural
                        response from an already-overloaded population have
                        been systematically over-assessed. In all three
                        records, the mechanism worked as predicted but the
                        expected behavioural response did not follow at scale.
change_target:          <VOCABULARY UNDEFINED — MISSING-02>
                        Intended: Opportunity Intelligence assertion_confidence
                        calibration where the value hypothesis depends on
                        population behaviour change.
change_description:     Reduce assertion_confidence for opportunities whose
                        value_hypothesis depends on a behavioural response not
                        directly evidenced in the underlying Facts.
evidence_of_pattern:    Three independent execution records across two
                        distinct opportunity domains show the same divergence:
                        mechanism confirmed, behavioural response not realised.
                        The consistency across domains distinguishes this from
                        a domain-specific effect.
reversal_procedure:     Restore prior calibration; rescore affected
                        opportunities under the prior score_model_version,
                        retaining both versions for comparison.
informs:                [Opportunity Intelligence]
applied_at:             2026-07-28T00:00:00Z
expected_effect:        Better alignment between predicted and realised value
                        for behaviour-dependent opportunities.
observed_effect:        <NOT YET ASSESSABLE — MISSING-04, no success measure>
evidential_support:     0.51  (MODERATE)
assertion_confidence:   0.44  (MODERATE)
effective_confidence:   0.44  (MODERATE)
status:                 ACTIVE
explanation:            Three records is a thin basis, reflected in moderate
                        confidence. Recorded as a calibration adjustment rather
                        than a rule change, and fully reversible, because the
                        supporting volume does not justify a structural change.
```
