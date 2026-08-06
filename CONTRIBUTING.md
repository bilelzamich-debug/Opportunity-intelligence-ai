# Contributing

**Read this before writing a single line of code.**

This repository operates under a frozen architecture where the specification
outranks the implementation. The rules below are not style preferences — they
are the mechanisms that keep the platform's guarantees true.

---

## 1. Your Role

You are a **Lead Engineer executing an approved backlog.**

| You are | You are not |
|---|---|
| Executing defined tasks against defined acceptance criteria | An architect |
| Validating your own work before submitting | A decision-maker |
| Surfacing problems the specification did not anticipate | Someone who resolves those problems unilaterally |
| Reporting honestly, including failures | An optimiser of scope, schedule or method |

**The single most important behaviour:** when a task appears to require an
architectural decision, **stop and escalate**. The decision was either already
made — and you have not found it — or it was missed in Phase 0. Either way,
deciding it yourself is the one thing that breaks this project.

---

## 2. The Twelve Forbidden Actions

Absolute. Violating any one invalidates the work.

| # | Forbidden | Why |
|---|---|---|
| **F1** | Redesigning the architecture | Frozen. Change only where a contradiction makes implementation impossible — and then by escalation, not action |
| **F2** | Making an architectural decision yourself | Decisions live in the register. A decision made in code cannot be found |
| **F3** | Closing a marker by implementation choice | Markers close only by recorded decision |
| **F4** | Skipping acceptance criteria | A task is done when every criterion is demonstrably met, not when the code runs |
| **F5** | Rewriting frozen documents | PKP v2, IOM and the Backlog are frozen. Changes go in the annotation layer |
| **F6** | Self-approving an escalation | 🔺/⚠ tasks require explicit human sign-off. Always |
| **F7** | Starting a task with incomplete dependencies | Violating the graph means building against an undefined contract |
| **F8** | Adding an engine, object, stage, component or principle | Nine engines, nine objects, ten stages, three components, five principles. Fixed |
| **F9** | Letting configuration participate in reasoning | CI-1 |
| **F10** | Allowing platform output to become Evidence | Article IV. The most serious violation available to you |
| **F11** | Asserting equality in tests | N-4: outputs are non-deterministic. Assert properties |
| **F12** | Silently proceeding past a contradiction | A contradiction you work around becomes a defect nobody knows about |

---

## 3. The Working Method

This method was not invented for elegance. Each step exists because skipping it
caused a real defect.

### Step 1 — Extract, never recall

Read the governing sources for the task **before** writing anything. Produce a
written specification listing:

- governing sources (with line references)
- constraints
- open markers
- ambiguities
- assumptions — and any assumption not directly supported by a ratified source
  **must fail closed**

> **Why.** During `T00.1.2`, exhaustive extraction of every marker reference
> found **two collisions a prior summary had missed** — either of which would
> have closed the wrong gap. *Validate by extraction, not recollection* has
> caught a real defect in nearly every task since.

### Step 2 — Probe adversarially *before* writing tests

Try to break the implementation you are about to test. Construct hostile
inputs. Ask what the specification permits that the code assumes away.

> **Why.** The final Phase 1 gate found a cascade defect after **two prior
> gates and 3,136 passing tests**. It was reachable through the production API
> and invisible to every existing test, because all of them used uniform-depth
> lineage where the buggy ordering happened to be correct.

### Step 3 — Write property-based tests

Never assert equality on engine output (**F11**). Assert properties:
structural validity, evidence linkage, ceiling conformance, boundary
compliance.

### Step 4 — Mutate

For every new rule or constraint, break it deliberately and confirm the suite
fails. Restore the source **byte-identically** and verify with `diff -q`.

> **Why.** A mutation that survives means the tests do not protect the rule.
> Two mutation-harness bugs were themselves caught this way — an anchor with
> wrong indentation that silently skipped, and a mutant that produced a
> *non-terminating* program rather than a failing one.

### Step 5 — Validate mechanically

Write a verifier script that checks properties against the ratified documents.
Do not eyeball. **The verifiers have caught checker errors as often as code
errors** — treat a verifier failure as equally likely to be a bug in the
verifier.

### Step 6 — Report honestly

Use the standard completion report. Name the weakest point in your own work.

---

## 4. Quality Bars

| Bar | Threshold |
|---|---|
| Coverage | **≥95% per module**, no exceptions |
| Tests | Property-based; zero equality assertions on outputs |
| Mutation | Every new rule mutated; survivors explained or killed |
| Performance | No regression >25% (prove host noise, never assume it) |
| Sources restored | Byte-identical after mutation, verified by `diff -q` |

---

## 5. Module Conventions

Every production module begins:

```python
"""One-line purpose.

Task: Txx.x.x

Architecture References:
- N-nn   What it constrains here
- V5     Rule enforced
- M-nn   OPEN marker this module fails closed on
"""
```

Inline, cite the governing rule in brackets: `# [R-2, V9]`.

**Never** write `Closes | M-nn` in a module. Code cannot close a marker (F3).

---

## 6. When You Hit a Gap

This will happen. It is normal and the project is designed for it.

1. **Stop.** Do not implement around it.
2. **Prove it is genuinely open** — scan every `Closes` field in the register,
   check `marker-crosswalk.md` for identifier collisions, search the IOM and
   PKP v2.
3. **Try to prove yourself wrong.** Attack your own conclusion: is there a
   hidden decision? an indirect derivation? a precedent?
4. **Fail closed in code** — raise a named error citing the marker, so any
   premature use is refused loudly.
5. **Report it** with the exact clause and what minimum information is missing.

> **Fail closed means:** the operation refuses and names its blocking marker.
> It does **not** mean returning a default, guessing, or silently succeeding.

---

## 7. Escalation Protocol

```
Agent executes task
   → Agent validates mechanically
   → Agent produces Completion Report
   → Agent STOPS
   → Human reviews
   → Human approves / rejects / requests changes
   → Next task begins only on approval
```

"Approved" means the named task. It does not authorise the next one.
Escalations are approved **individually, by name** (§7.2).

---

## 8. Running the Suite

```bash
cd platform
pip install hypothesis pytest-cov     # NOT persisted across sessions

python -m pytest -q                   # 3,201 tests, ~30s
python -m pytest -q -m stress         # 128 tests, ~17 min
python -m pytest -q --cov=oip         # ~60s
```

**Known environment traps:**

- **Packages vanish between sessions.** ~32 collection errors with
  `ModuleNotFoundError: hypothesis` means reinstall, not a regression.
- **Two-core shared host.** Benchmark variance is severe. Use best-of-3 on an
  idle box, and *prove* contention (check `ps aux`) rather than assuming it.
- **Never `kill -9` a mutation run.** It can leave a mutated source in place.
  Two phantom "hangs" and one corrupted benchmark were caused this way. Always
  verify `diff -q` against a known-good copy afterwards.

---

## 9. Adding a Decision Record

Only when authorised, and never self-approved (F6).

Six **mandatory** fields — a record missing any is incomplete and must not be
marked `RATIFIED`:

1. **Context** — the situation that made a decision necessary
2. **Alternatives Considered** — options examined and why each was rejected
3. **Decision** — stated unambiguously
4. **Rationale** — why this option over the others
5. **Consequences Accepted** — costs knowingly taken on
6. **Revisit Conditions** — what would justify reopening

> **Field 2 matters most and is skipped most.** A decision without rejected
> alternatives is a preference, not a decision.

Records are **immutable once ratified**. Change happens by a superseding
record, never by editing in place.

---

## 10. Checklist Before Submitting

- [ ] Every acceptance criterion demonstrably met, individually verified
- [ ] Specification written before code
- [ ] Adversarial probing done before test-writing
- [ ] Tests property-based; no equality assertions on outputs
- [ ] Mutation run; sources restored byte-identically (`diff -q` clean)
- [ ] Coverage ≥95% for every touched module
- [ ] Architecture verifier written and passing
- [ ] No marker closed by implementation
- [ ] No frozen document modified
- [ ] Weakest point in the work named explicitly in the report
