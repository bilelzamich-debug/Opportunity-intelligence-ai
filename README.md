# Opportunity Intelligence Platform (OIP)

**An AI-native platform that discovers, validates, scores and learns from market
opportunities using evidence-first reasoning.**

---

## Status at a Glance

| | |
|---|---|
| **Phase 0 — Specification** | ✅ **CLOSED** — 37 decisions ratified |
| **Phase 1 — Foundation** | ✅ **CLOSED** 2026-08-04 — 44/44 tasks, 134/134 acceptance criteria |
| **Phase 2 — Research Engine** | 🟡 **BLOCKED** — 4 decisions ratified (N-20…N-23); 9 of 10 tasks blocked |
| **Phases 3–9** | ⬜ Not started |
| **Decisions ratified** | **41** |
| **Production modules** | 29 (18,418 lines) |
| **Tests** | **3,329 passing** (3,201 unit + 128 stress), 0 failing |
| **Coverage** | **99.04%**, no module below 95% |
| **Architecture verifiers** | 443 checks passing |

**Two human decisions block all further progress.** See
[`NEXT_STEPS.md`](NEXT_STEPS.md).

---

## 1. Vision

Build a platform that finds real market opportunities, proves they are real,
scores them honestly, and improves from what happens when someone acts on them.

The platform is **advisory**. It produces scored, validated opportunities and
hands them to people who decide. It holds no budget, no operational authority,
and no accountability for consequences (Constitution Article VI).

## 2. Goals

| # | Goal | Mechanism |
|---|---|---|
| 1 | Every conclusion traces to external observation | Lineage to Evidence, enforced at acceptance (V2, V3, V4) |
| 2 | No conclusion is more certain than its evidence | Confidence ceiling (R-3, V5) |
| 3 | Nothing the platform generates becomes its own evidence | Ground Truth Protection (AD-05, Article IV) |
| 4 | Every decision carries its reasoning | Explanation skeleton (N-13) |
| 5 | The platform states what it does not know | Honest Uncertainty (Article X) |
| 6 | Learning cannot silently corrupt the evidence base | Behavioural loop closure (R-8) |

## 3. The Five Principles

From PKP v1 §2, unchanged:

1. **Evidence before conclusions**
2. **Explainable decisions**
3. **Traceable lineage**
4. **Modular engines**
5. **Continuous learning**

## 4. Architecture Overview

### The Pipeline — ten stages, nine engines, nine object types

```
 1 Evidence  ──▶ 2 Facts ──▶ 3 Problems ──▶ 4 Patterns ──▶ 5 Opportunities
      ▲                                                          │
      │                                                          ▼
 9 Feedback ◀── 8 Execution ◀── 7 Validation ◀── 6 Solutions ────┘
      │
      └── raises a research directive (never becomes Evidence — AD-05)
```

Stage 10 is **Orchestration**, which runs the cycle but never judges knowledge.

### Three shared components

**Knowledge Store** (authoritative) · **Knowledge Graph** (derived, rebuildable)
· **Experiment Registry** (P7).

### The constraint everything protects

> **No platform-generated artifact may become Evidence directly. Evidence must
> always originate from external reality.** — AD-05

Feedback may become exactly four things: a Learning Signal, a Knowledge Update,
a Research Trigger, or a Model Calibration. Nothing else.

Full detail: [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 5. Repository Map

```
.
├── README.md · LICENSE · CONTRIBUTING.md · CHANGELOG.md
├── INDEX.md              Master index — links every document
├── PROJECT_STATE.md      Authoritative current state
├── NEXT_STEPS.md         What the next agent must do
├── ARCHITECTURE.md       Full architecture reference
├── ROADMAP.md            Ten-phase plan
│
├── docs/
│   ├── architecture/     5 frozen source documents (PKP v1, v2, IOM, Backlog, Blocker Resolution)
│   ├── decisions/        41 ratified decision records — one file each
│   ├── governance/       Constitution, Playbook, register, annotations, timeline, dependency map
│   ├── markers/          Marker registers and the canonical crosswalk
│   ├── reviews/          ARB reviews, escalation reviews, revision reports
│   ├── reports/          Closure certificates, defect analyses, investigations
│   ├── specifications/   Per-task written specifications
│   ├── playbooks/        Execution plans and working method
│   ├── prompts/          Every governing prompt used in this project
│   ├── research/         Design spaces, rejected alternatives, derivability proofs
│   └── appendices/       Unratified proposals and superseded drafts
│
├── platform/             The implementation
│   ├── oip/              29 production modules
│   ├── tests/            37 test files, 3,329 tests
│   ├── benchmarks/       Performance baseline
│   └── validation/       443 verifier checks, probes, mutation suites, logs
│
├── templates/            Decision record, completion report, PR templates
├── examples/             Worked examples from the IOM
├── scripts/              verify_all.sh — the complete validation battery
└── .github/              PR template
```

## 6. Current Status

**Phase 1 is closed.** All nine Intelligence Object types persist, validate,
version, traverse and invalidate correctly. 3,329 tests prove the contracts
hold. Twenty-one production defects were found and fixed during P1.

**Phase 2 is blocked.** Four decisions (N-20…N-23) were ratified on 2026-08-04,
closing parts of M-16, M-17, M-18 and M-01. But two blockers remain that only a
human can clear:

| # | Blocker | Effect |
|---|---|---|
| **D-1** | `T02.2.4` AC2 requires a human gate that N-2 forecloses | Blocks 22 downstream P7–P8 tasks |
| **Rights authority unnamed** | N-21 §5.1 names no owner | N-21 is ratified but **operationally inert** — no source can be acquired |

**Exactly one task is executable today:** `T02.1.3` (independence grouping),
subject to a one-line clarification. See [`NEXT_STEPS.md`](NEXT_STEPS.md).

## 7. How To Continue Development

**Read these four documents, in order, before writing anything:**

1. [`PROJECT_STATE.md`](PROJECT_STATE.md) — where things actually stand
2. [`docs/governance/CONSTITUTION.md`](docs/governance/CONSTITUTION.md) — the eleven articles
3. [`docs/governance/AGENT-PLAYBOOK.md`](docs/governance/AGENT-PLAYBOOK.md) — role and the twelve forbidden actions
4. [`NEXT_STEPS.md`](NEXT_STEPS.md) — the specific next action

Then:

```bash
cd platform
pip install hypothesis pytest-cov     # NOT persisted between sessions
python -m pytest -q                   # expect 3,201 passed
cd .. && ./scripts/verify_all.sh      # expect 13 passed, 0 failed
```

### The rule that governs everything

> **A marker is closed only by a ratified decision record. Closing a marker by
> implementation choice is prohibited — an architecture decision made in code is
> an architecture decision that cannot be found.**

When a task requires an undefined decision, **stop and escalate**. Nine Phase-2
tasks are legitimately halted for exactly this reason. That is the system
working, not failing.

## 8. Roadmap

| Phase | Name | Status |
|---|---|---|
| P0 | Specification | ✅ Closed |
| P1 | Foundation | ✅ Closed |
| **P2** | **Research Engine** | 🟡 **Blocked on D-1 + rights authority** |
| P3 | Fact Extraction | ⬜ Gated behind P2 exit |
| P4 | Problem Intelligence | ⬜ |
| P5 | Pattern Intelligence | ⬜ |
| P6 | Opportunity Intelligence | ⬜ |
| P7 | Solution & Validation | ⬜ |
| P8 | Feedback | ⬜ Most constrained (C-02, M-02, M-43, M-70) |
| P9 | Hardening | ⬜ |

Full detail: [`ROADMAP.md`](ROADMAP.md).

## 9. Honest Limitations

Stated prominently because Constitution Article X requires the project to apply
its own standard to itself:

- **No Phase-2 marker is fully closed.** N-20…N-23 each close their marker
  *partially*. Trust is recorded but does not affect scoring. Coverage is
  measured but does not gate. Directives exist but nothing raises them
  automatically.
- **Five reservations (AS-0…AS-5) are now binding architecture.** Two are
  significant: a gate ordering with no corpus basis (AS-1), and a
  halt-on-first-refusal convention that **inverts** the N-08/N-10 precedent
  (AS-2).
- **The platform has never acquired real Evidence.** Everything is verified
  against constructed test objects.
- **Ratification unblocked specifications, not work.**

## 10. License

MIT — see [`LICENSE`](LICENSE).
