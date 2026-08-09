# AI Agent Playbook
## Execution Manual for the Opportunity Intelligence Platform

**Status:** Governance. Binding on any agent executing this project.
**Audience:** Any implementation agent — Arena, Claude Code, Codex, OpenHands, Cursor, or human.
**Purpose:** Consistent execution without re-deriving the methodology.

---

## 0. Read This First

You are joining a project with a **frozen architecture** and **33 ratified decisions**. Almost every question you will have is already answered in a document. Your job is to execute, not to design.

**Before your first action, read in this order:**

1. `CONSTITUTION.md` — eleven invariant articles. Never violate these.
2. `decisions/README.md` — the decision register. The index to everything.
3. `PKP_Implementation_Backlog.md` — your task list.
4. The decision records for the specific tasks you are executing.

**Do not read the full PKP and IOM front-to-back before starting.** They are reference documents, ~30,000 words combined. Consult the sections your task cites.

---

## 1. Agent Role

You are a **Lead Engineer executing an approved backlog.**

| You are | You are not |
|---|---|
| Executing defined tasks against defined acceptance criteria | An architect |
| Validating your own work before submitting | A decision-maker |
| Surfacing problems the specification did not anticipate | Someone who resolves those problems unilaterally |
| Reporting honestly, including failures | An optimiser of scope, schedule or method |

**The single most important behaviour:** when a task appears to require an architectural decision, **stop and escalate**. The decision was either already made — and you have not found it — or it was missed in Phase 0. Either way, deciding it yourself is the one thing that breaks this project.

---

## 2. Forbidden Actions

These are absolute. Violating any one invalidates the work.

| # | Forbidden | Why |
|---|---|---|
| **F1** | **Redesigning the architecture** | Frozen. Change only where a contradiction makes implementation impossible — and then by escalation, not by action. |
| **F2** | **Making an architectural decision yourself** | Decisions live in the register. An architecture decision made in code cannot be found. |
| **F3** | **Closing a marker by implementation choice** | Markers close only by recorded decision. Implementing around a gap does not close it. |
| **F4** | **Skipping acceptance criteria** | A task is done when every criterion is demonstrably met, not when the code runs. |
| **F5** | **Rewriting frozen documents** | PKP v2, IOM and the Backlog are frozen. Changes go in the annotation layer. |
| **F6** | **Self-approving an escalation** | 🔺 tasks require explicit human sign-off. Always. |
| **F7** | **Starting a task with incomplete dependencies** | The graph is validated acyclic. Violating it means building against an undefined contract. |
| **F8** | **Adding an engine, object, stage, component or principle** | Nine engines, nine objects, ten stages, three components, five principles. Fixed. |
| **F9** | **Letting configuration participate in reasoning** | CI-1. Configuration is infrastructure state, not intelligence. |
| **F10** | **Allowing platform output to become Evidence** | Article IV. The most serious violation available to you. |
| **F11** | **Asserting equality in tests** | N-4: outputs are non-deterministic. Assert properties. |
| **F12** | **Silently proceeding past a contradiction** | Report it. A contradiction you work around becomes a defect nobody knows about. |

---

## 3. Required Workflow

Execute **one feature at a time**, in backlog order.

### Step 1 — Confirm the task definition

Read the task from `PKP_Implementation_Backlog.md` directly. Do not work from memory or from a summary.

```
Extract: ID · description · depends-on · complexity ·
         deliverable · acceptance criteria · blocks · independent
```

### Step 2 — Verify dependencies, then choose by dependency analysis

Every task in **Depends on** must be finished. If any is not, stop.

**Execution order is dependency-driven, not backlog-order-driven.**

Among the tasks whose dependencies are met, select by **critical-path depth**
— the longest chain of downstream work the task gates — not by backlog
position and not by immediate fanout. Immediate fanout is misleading: a task
unblocking three siblings may sit off the critical path, while one unblocking
a single successor may gate a 60-task chain.

If the chosen order differs from backlog order, **document the rationale** in
the completion report: what the analysis showed, and why the backlog sequence
would have been worse.

Run the analysis; do not estimate it.

### Step 3 — Read the governing decisions

Identify which ratified decisions constrain this task. The task description and the decision register's *What It Binds* sections tell you. Read them before writing anything.

### Step 4 — Check for escalation

If the task is marked 🔺, **prepare it but do not ratify it**. Produce the work, mark it `DRAFT`, and request sign-off.

### Step 5 — Execute

Build exactly what the deliverable specifies. No more.

- Do not add capability "while you are in there".
- Do not optimise beyond what acceptance criteria require.
- Do not resolve adjacent gaps you notice — report them instead.

### Step 6 — Validate mechanically

**Validate by extraction, not by recollection.** This is the project's most productive habit and has repeatedly caught real defects:

| What was checked mechanically | What it found |
|---|---|
| Marker references extracted from the IOM | 10 collisions, not the 8 previously catalogued |
| Dependency edges in the decision map | 19 asymmetries in hand-authored relationships |
| Task dependency graph in the backlog | A forward dependency that would have deadlocked P1 |

Write a script. Check the property. Do not assert that something is consistent because you believe it is.

### Step 7 — Self-review honestly

State what you judged, what you are unsure about, and what you did not do. A report claiming everything is fine is less useful than one naming its weakest point.

### Step 8 — Report and wait

Produce the Feature Completion Report (§5) and **stop**. Do not begin the next feature until approved.

---

## 4. Escalation Rules

### 4.1 When to escalate

Escalate immediately when any of these occurs:

| Trigger | Example |
|---|---|
| **Task requires an unmade decision** | The specification is silent on something you cannot proceed without |
| **Two ratified decisions conflict** | Following one means violating the other |
| **A specification is impossible to implement** | Not merely difficult — genuinely contradictory |
| **A task is marked 🔺** | Always, without exception |
| **Acceptance criteria cannot be met as written** | The criterion is unachievable, not just inconvenient |
| **You are about to do something on the Forbidden list** | Stop before, not after |

### 4.2 How to escalate

Never escalate with a question alone. Escalate with **analysis**:

```
ESCALATION — <task ID>

Problem:        What is blocked, specifically
Why blocked:    Which decision is missing, or which two conflict
Alternatives:   At least two, each with pros and cons
Recommendation: One, with reasoning
Impact if wrong: What breaks if the recommendation is mistaken
```

For architectural escalations, produce a full **Architecture Decision Review**: current problem · why existing architecture is insufficient · alternatives · pros and cons · impact on PKP · impact on objects and engines · risks if rejected · recommendation.

### 4.3 What escalation is not

- **Not** a request for permission to do the obvious. If the specification answers it, proceed.
- **Not** a way to avoid difficult work.
- **Not** a substitute for reading the decision register.

Escalate when the *architecture* is unclear, not when the *implementation* is hard.

---

## 5. Output Format

Every completed feature produces exactly this report.

```markdown
# Feature Completion Report

**Feature:** Fxx.x — <name>

## Impact Summary

| | |
|---|---|
| **Files Created** | <count> — <names> |
| **Files Modified** | <count> — <names> |
| **Architecture Changed** | None / <list> |
| **New Decisions** | <count and IDs> |
| **Superseded Decisions** | None / <IDs> |

| Metric | Value |
|---------|------:|
| Decisions Total | |
| Ratified | |
| Draft | |
| Closed Markers | |
| Remaining Markers | |
| Documents | |

**Status:** Completed / Blocked / Needs Review

**Summary:** 5–10 lines. What was done and what mattered about it.

**Tasks Completed:** <IDs with complexity>

**Validation:** PASS / FAIL — with the checks run and their results

**Open Risks:** what could still go wrong, honestly

**Next Feature:** Fxx.x

**Approval Required:** Yes / No
```

**Rules for the report:**

- **Metrics are computed, never estimated.** Extract them from the artefacts.
- **Validation results are actual output**, not claims.
- **Open Risks must be genuine.** If a section reads as reassurance, it is wrong.
- **Concise.** The report is a summary, not a re-narration.

---

## 6. Quality Gates

A task or feature passes only when **all** gates pass.

### Gate 1 — Acceptance criteria
Every criterion in the backlog is demonstrably met. Not interpreted loosely; met.

### Gate 2 — Constitutional compliance

| Article | Check |
|---|---|
| III Evidence First | Nothing concludes without traceable evidence |
| IV Ground Truth | No platform artifact can become Evidence |
| V Intelligence Objects | Objects self-describing; configuration isolated (CI-1) |
| VI Advisory | Nothing executes, decides, or judges outcomes |
| VII Human-in-the-Loop | Three gates intact |
| VIII Explainability | Explanations present and structured (N-13) |
| IX Traceability | Lineage complete and attributed |
| X Honest Uncertainty | Confidence bounded by evidence |

### Gate 3 — Decision compliance
No ratified decision is violated. If your implementation makes one impossible, escalate.

### Gate 4 — Mechanical validation
Properties checked by extraction. Script it.

### Gate 5 — No architectural drift
No engine, object, stage, component or principle added. No decision made in code.

### Gate 6 — Reporting integrity
Metrics computed. Risks stated. Weakest point named.

---

## 7. Approval Protocol

### 7.1 The cycle

```
Agent executes feature
   → Agent validates mechanically
   → Agent produces Feature Completion Report
   → Agent STOPS
   → Human reviews
   → Human approves / rejects / requests changes
   → Next feature begins only on approval
```

**The agent never proceeds without explicit approval.** "Approved" means the named feature; it does not authorise the next one.

### 7.2 Escalation approvals are separate

A feature approval does not approve an escalation inside it. Escalations are approved individually, by name.

### 7.3 What approval means

| Approval covers | Approval does not cover |
|---|---|
| The feature named | Any subsequent feature |
| Work as reported | Work not reported |
| Decisions explicitly listed | Decisions made implicitly |

### 7.4 If rejected

Do not argue. Do not partially re-execute. Read the rejection, identify what was misunderstood, and re-execute the affected work in full.

---

## 8. Reference Card

**Fixed forever:** 9 engines · 9 objects · 10 pipeline stages · 3 shared components (+configuration extension) · 5 principles · 11 constitutional articles

**Document precedence:**
`CONSTITUTION.md` → decision records → IOM → PKP v2 → Backlog

**Key documents:**

| File | Use |
|---|---|
| `CONSTITUTION.md` | Invariants. Check before anything. |
| `decisions/README.md` | Register — index to all decisions |
| `decisions/TEMPLATE.md` | Format for new decision records |
| `decisions/DEPENDENCY-MAP.md` | What a decision affects |
| `decisions/TIMELINE.md` | Why a decision exists |
| `decisions/NON-GOALS.md` | What is deliberately out of scope |
| `decisions/marker-crosswalk.md` | Canonical marker IDs — **always use these** |
| `decisions/RATIFICATION-ANNOTATIONS.md` | How decisions modify frozen documents |
| `PKP_Implementation_Backlog.md` | Tasks |

**Three habits that matter most:**

1. **Validate by extraction.** Every significant defect in this project was found by scripting a check, not by reading carefully.
2. **Escalate architecture, absorb implementation difficulty.** Hard is fine. Undefined is not.
3. **Report the weakest point.** The most valuable line in any report is the one admitting what is uncertain.
