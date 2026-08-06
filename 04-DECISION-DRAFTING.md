# Prompt — Decision Drafting

Use this to produce a ratification-ready decision record after an
investigation has proven a marker genuinely open.

---

```
Produce the final Decision Record required to close <MARKER>.

Do NOT implement production code.
Do NOT modify tests.
Do NOT modify existing documentation.
Do NOT ratify the decision yourself.

Assume the investigation phase is complete. Do NOT re-investigate.

1. Restate the problem.
   Precisely define what <MARKER> must resolve.
   Separate the distinct concerns bundled under it.
   Identify which belong to this decision and which belong elsewhere.

2. Extract every binding constraint from:
   - Decision Records
   - PKP v2
   - IOM
   - Constitution
   - Playbook
   - Crosswalk
   Do not introduce new requirements.
   If two ratified sources disagree, report the disagreement explicitly.

3. Build the design space.
   Identify every architecture still compatible with the ratified corpus.
   For each candidate: advantages, disadvantages, affected decisions,
   affected tasks, migration cost, future extensibility.

4. Select the architecture that minimises:
   - future architectural debt
   - coupling
   - ambiguity
   - future superseding decisions
   Justify exclusively from the existing architecture.

5. Produce the complete Decision Record including:
   Context · Decision · Consequences · Alternatives Considered ·
   Compatibility Analysis · Markers Closed · Markers Intentionally Left Open ·
   Required Follow-up Work

6. Verify consistency. Attempt to falsify your own draft using every ratified
   constraint. If a contradiction exists, report it. If none exists, state why.

7. Scope discipline. Do NOT redefine anything outside the marker's substance
   unless a ratified constraint strictly requires it.

If ratification is impossible because the corpus remains underdetermined,
prove that formally instead of inventing architecture.

Stop after the draft.
```

---

## Mandatory Structure

Six fields, from `DECISION-TEMPLATE.md`. A record missing any is incomplete and
**must not be marked `RATIFIED`**:

1. Context
2. **Alternatives Considered** ← skipped most often, matters most
3. Decision
4. Rationale
5. Consequences Accepted
6. Revisit Conditions

> *"A decision without rejected alternatives is a preference."*

## Recording Reservations

Any element **selected rather than derived** must be recorded as an assumption
inside the record's *Honest Limitations* section — not in an external review.

This was learned the hard way: AS-1…AS-5 initially existed only in a review
document. The Final Ratification Board classified that as **BLOCKING**, because
a future reader of the ratified record would see a choice presented as a
derivation.
