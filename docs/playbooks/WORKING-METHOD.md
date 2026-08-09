# The Working Method

Six steps. Each exists because skipping it caused a real, documented defect.

This is not process for its own sake — every step below can be traced to a
specific failure it now prevents.

---

## Step 1 — Extract, never recall

Read the governing sources **before** writing anything. Produce a written
specification listing governing sources (with line references), constraints,
open markers, ambiguities, and assumptions. **Any assumption not directly
supported by a ratified source must fail closed.**

> **Why.** During `T00.1.2`, exhaustive extraction of every marker reference
> found **two collisions a prior summary had missed** — either would have
> closed the wrong gap. Two later analyses each under-counted the M-16 blast
> radius (4→7 decisions, 7→94 tasks) by trusting an earlier report.

**Anti-pattern:** "I remember the decision says X." Open it and read it.

---

## Step 2 — Probe adversarially, before writing tests

Construct hostile inputs. Ask what the specification *permits* that the code
*assumes away*.

> **Why.** The final Phase-1 gate found the cascade defect after **two prior
> gates and 3,136 passing tests**. It was reachable through the production API
> and invisible to every existing test, because all of them used uniform-depth
> lineage where the buggy ordering happened to be correct.

**The three-stage reachability test** — a probe finding is only a defect if it
survives all three:

1. **Reproduce** it
2. **Prove it uses legal objects** (not test-harness bypasses)
3. **Prove it survives the typed production API**

A finding failing any stage is a test artefact, not a defect.

---

## Step 3 — Write property-based tests

Never assert equality on engine output (**F11**, per N-4: *"Outputs are not
guaranteed deterministic"*). Assert properties: structural validity, evidence
linkage, ceiling conformance, boundary compliance.

**Vary fixture shape.** Uniform fixtures hide order-dependent bugs — that is
precisely how the cascade defect survived.

---

## Step 4 — Mutate

Break each new rule deliberately; the suite must fail. Restore the source
**byte-identically** and verify with `diff -q`.

> **Why.** A surviving mutant means the tests do not protect the rule. An
> *equivalent* mutant must be **proven** equivalent, not assumed.

Two harness bugs were caught by mutation testing itself:

| Bug | Symptom |
|---|---|
| Anchor with wrong indentation | Silently skipped — reported `inapplicable`, not `killed` |
| Mutant producing a **non-terminating** program | Suite hung rather than failing, so "killed" could never be observed |

**Never `kill -9` a mutation run.** The harness restores sources in a `finally`
block. Killing it leaves mutated source in place — this caused two phantom
"hangs" and one corrupted benchmark.

---

## Step 5 — Verify mechanically

Write a verifier that checks properties against the ratified documents. Do not
eyeball.

> **Critical.** Treat a verifier failure as **equally likely to be a bug in the
> verifier**. During Phase-2 work, **10 of 10** initial verifier failures were
> checker errors — invented API names, and two regexes that matched *prose
> documenting a marker as open*, thereby asserting the opposite of their
> intent. Had those been trusted, working production code would have been
> "fixed".

**Scan executable code, not prose.** Strip docstrings and comments before
regex-matching for forbidden constructs.

---

## Step 6 — Report honestly

Use the standard format. **Name the weakest point in your own work.**

> Constitution Article X — *"the platform states what it does not know"* —
> applies to the project's own reporting, not only to platform output.

"None" in an Honest Limitations section is almost never true.

---

## Cross-Cutting Rules

### Prove host noise; never assume it

```bash
python -c "import sys; sys.path.insert(0,'.'); from oip.identity import IdentityAllocator; \
  print(sorted(m for m in sys.modules if m.startswith('oip')))"
# → ['oip', 'oip.identity']  — proves the benchmark never loads the changed module
```

Also check `ps aux` and `/proc/loadavg`. On this two-core host, an orphaned
process produced **7 false regressions** in one run.

### Treat completed work as untrusted

| Occasion | Found by re-deriving |
|---|---|
| T01.8.1 gate re-run | T01.2.4 partial-retraction defect in a "complete" task |
| T01.8.1 final gate | The cascade BFS defect |
| P2 dependency reconstruction | **M-01** — a fourth blocker three analyses had missed |
| Revision 2 validation | A2/A6 were new architecture, not derivations |
| Cross-reference audit | 6 broken references two reviews had missed |

### Stop at the boundary

- Stop after the named task
- Stop immediately on discovering a production defect
- If a defect is fixed, stop after validating the fix
- **When a task requires an architectural decision, stop and escalate**

---

## What This Method Costs, and Why It Is Worth It

Phase 1 took 44 tasks to deliver 29 modules. The exit gate ran **three times**.
Twenty-one production defects were found and fixed.

The alternative — trusting prior reports, writing tests before probing, closing
markers by implementation — would have shipped faster and produced a platform
whose grounding guarantees were quietly false. The cascade defect alone would
have left objects `ACTIVE` after their entire evidential support was withdrawn,
undetectably, through the production API.
