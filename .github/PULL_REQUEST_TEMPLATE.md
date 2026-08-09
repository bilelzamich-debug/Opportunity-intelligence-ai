# Pull Request

## Task

**Task ID:** `Txx.x.x`
**Escalation flag:** ⚠ / 🔺 / none
**Authorised by:** <!-- required; work must be explicitly authorised -->

## What Changed

<!-- One paragraph. What now behaves differently, and why. -->

---

## Acceptance Criteria

Every criterion must be **individually** demonstrated. Do not tick the group.

| # | Criterion (verbatim from the backlog) | Met | Evidence |
|---|---|---|---|
| AC1 | | ☐ | |
| AC2 | | ☐ | |
| AC3 | | ☐ | |

Criteria **not** met, and the marker blocking each:

| # | Blocker |
|---|---|
| | |

---

## Governance Checklist

Every box must be ticked or explicitly explained. These are the twelve
forbidden actions.

- [ ] **F1** No architecture redesigned
- [ ] **F2** No architectural decision made in code
- [ ] **F3** **No marker closed by implementation** — markers close only by ratified record
- [ ] **F4** No acceptance criterion skipped
- [ ] **F5** No frozen document edited (`docs/architecture/`)
- [ ] **F6** No escalation self-approved
- [ ] **F7** All dependencies complete before starting
- [ ] **F8** No engine, object, stage, component or principle added
- [ ] **F9** Configuration does not participate in reasoning (CI-1)
- [ ] **F10** No platform output can become Evidence (Article IV)
- [ ] **F11** No equality assertions on engine output (N-4)
- [ ] **F12** No contradiction silently worked around

Ratified decisions this change touches: <!-- e.g. N-20, S-2 -->
Supersessions required: **none** / <!-- justify -->

---

## Method

- [ ] Specification written **before** code, citing governing sources with line references
- [ ] Adversarial probing done **before** tests were written
- [ ] Tests are property-based
- [ ] Mutation run; sources restored byte-identically (`diff -q` clean)
- [ ] Architecture verifier written or extended

---

## Validation

```
# paste actual output — not a summary
```

| Check | Expected | Actual |
|---|---|---|
| Unit suite | 3,201 passed | |
| Stress (if touched) | 128 passed | |
| Coverage, changed modules | ≥95% | |
| Mutation | survivors killed or **proven** equivalent | |
| `./scripts/verify_all.sh` | 13 passed, 0 failed | |
| Performance | no regression >25% | |

---

## Defects Found

<!-- If a production defect was found: root cause, the fix, the regression
     test, and why the existing suite missed it. If none, say "None." -->

---

## Honest Limitations

<!-- REQUIRED. Name the weakest point in this work. Constitution Article X
     applies to our own reporting, not only to platform output.

     "None" is almost never true. What is untested? What did you assume?
     What would you attack if reviewing this? -->

---

## Blocked / Deferred

| Item | Marker | Why it cannot proceed |
|---|---|---|
| | | |
