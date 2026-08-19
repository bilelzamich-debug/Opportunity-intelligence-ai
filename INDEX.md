# Master Index

Every document in this repository. **329 files · 187 Markdown documents.**

Generated from the actual file tree.


---


## Root Documents

| File | Purpose |
|---|---|
| [`README.md`](README.md) | Entry point — vision, goals, architecture overview, status, roadmap |
| [`INDEX.md`](INDEX.md) | This file — links every document |
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | **Authoritative current state** — every figure verified by execution |
| [`NEXT_STEPS.md`](NEXT_STEPS.md) | Exactly what the next agent must do |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Full architecture reference |
| [`ROADMAP.md`](ROADMAP.md) | Ten-phase plan with blocking markers |
| [`CHANGELOG.md`](CHANGELOG.md) | Chronological record of every milestone, revision and ratification |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to work here — read before writing code |
| [`GLOSSARY.md`](GLOSSARY.md) | Every term, marker and identifier |
| [`LICENSE`](LICENSE) | MIT |

---


## `docs/architecture/` — Frozen Source Documents

> **These are frozen (Playbook F5).** Changes go in the annotation layer.

| File | Lines | Contents |
|---|---|---|
| [`PKP_v1_Foundation.txt`](docs/architecture/PKP_v1_Foundation.txt) | 64 | The original inheritance — vision, principles, pipeline, engines |
| [`PKP_v2_Master_Reference.md`](docs/architecture/PKP_v2_Master_Reference.md) | 1,882 | Diagnostic pass. **§11–§13 canonical marker registers** |
| [`PKP_Intelligence_Object_Model.md`](docs/architecture/PKP_Intelligence_Object_Model.md) | 2,283 | All nine object types, 18 dimensions each. D-01…D-08 |
| [`PKP_Implementation_Backlog.md`](docs/architecture/PKP_Implementation_Backlog.md) | 3,541 | Every task, all phases, with acceptance criteria |
| [`PKP_PreP1_Blocker_Resolution.md`](docs/architecture/PKP_PreP1_Blocker_Resolution.md) | 1,483 | B-01…B-6x. **"No decision herein is ratified"** |
| [`README.md`](docs/architecture/README.md) | — | Reading order and crosswalk warnings |

---


## `docs/decisions/` — 41 Ratified Decision Records

One file each. Never merged.

- [`AD-01-evidence-first.md`](docs/decisions/AD-01-evidence-first.md) — AD-01 — Evidence-First
- [`AD-02-intelligence-contracts.md`](docs/decisions/AD-02-intelligence-contracts.md) — AD-02 — Intelligence Contracts
- [`AD-03-feedback-loop.md`](docs/decisions/AD-03-feedback-loop.md) — AD-03 — Feedback Loop
- [`AD-04-separation-of-concerns.md`](docs/decisions/AD-04-separation-of-concerns.md) — AD-04 — Separation of Concerns
- [`AD-05-ground-truth-protection.md`](docs/decisions/AD-05-ground-truth-protection.md) — AD-05 — Ground Truth Protection Principle
- [`N-01-platform-boundary.md`](docs/decisions/N-01-platform-boundary.md) — N-1 — Platform Boundary: Advisory with Structured Handoff
- [`N-02-human-gates.md`](docs/decisions/N-02-human-gates.md) — N-2 — Human Gates at Three Transitions
- [`N-03-success-criteria.md`](docs/decisions/N-03-success-criteria.md) — N-3 — Success Criteria: Stage Proxies Now, Outcome Measures Frozen Now
- [`N-04-determinism.md`](docs/decisions/N-04-determinism.md) — N-4 — Determinism: Reproducible Inputs, Non-Deterministic Outputs
- [`N-05-tenancy.md`](docs/decisions/N-05-tenancy.md) — N-5 — Tenancy Discriminator Reserved
- [`N-06-store-graph-boundary.md`](docs/decisions/N-06-store-graph-boundary.md) — N-06 — Store/Graph Boundary: Objects Authoritative, Graph Derived
- [`N-07-configuration-referent.md`](docs/decisions/N-07-configuration-referent.md) — N-07 — Configuration Referent: Scoped Knowledge Store Extension
- [`N-08-acceptance-authority.md`](docs/decisions/N-08-acceptance-authority.md) — N-08 — Acceptance Authority: Store Enforces, Object Model Specifies
- [`N-09-cascade-invalidation.md`](docs/decisions/N-09-cascade-invalidation.md) — N-09 — Cascade Invalidation: Mechanical Operation Invoked by Orchestration
- [`N-10-failure-representation.md`](docs/decisions/N-10-failure-representation.md) — N-10 — Failure Representation Outside the Object Model
- [`N-11-concurrency.md`](docs/decisions/N-11-concurrency.md) — N-11 — Concurrency: Parallel Acquisition, Serialised Interpretation
- [`N-12-retention.md`](docs/decisions/N-12-retention.md) — N-12 — Retention: Lineage Skeleton Permanent, Content Tiered by Reachability
- [`N-13-explanation-skeleton.md`](docs/decisions/N-13-explanation-skeleton.md) — N-13 — Explanation Skeleton
- [`N-14-cross-stage-read-access.md`](docs/decisions/N-14-cross-stage-read-access.md) — N-14 — Cross-Stage Read Access: Lineage-Restricted
- [`N-15-evidence-storage.md`](docs/decisions/N-15-evidence-storage.md) — N-15 — Evidence Storage: Hybrid, Constrained by Licensing
- [`N-16-source-diversity-propagation.md`](docs/decisions/N-16-source-diversity-propagation.md) — N-16 — Source Diversity Propagation
- [`N-17-orchestration-control-model.md`](docs/decisions/N-17-orchestration-control-model.md) — N-17 — Orchestration Control Model: Scheduled Batch
- [`N-18-orchestration-phasing.md`](docs/decisions/N-18-orchestration-phasing.md) — N-18 — Orchestration Phased into P1
- [`N-19-experiment-registry-placement.md`](docs/decisions/N-19-experiment-registry-placement.md) — N-19 — Experiment Registry: Reserved in P1, Built in P7
- [`N-20-source-model.md`](docs/decisions/N-20-source-model.md) — N-20 — Source Model: Closed Taxonomy by Acquisition Channel, with Non-Scoring Trust
- [`N-21-acquisition-rights.md`](docs/decisions/N-21-acquisition-rights.md) — N-21 — Acquisition Rights: Per-Source Assessment Recorded on Evidence, Enforced Before Acquisition
- [`N-22-coverage-model.md`](docs/decisions/N-22-coverage-model.md) — N-22 — Coverage Model: Source-Type Coverage with Explicit Gap Declaration
- [`N-23-research-trigger.md`](docs/decisions/N-23-research-trigger.md) — N-23 — Research Trigger: Directive-Scoped Acquisition Within Scheduled Cycles
- [`N-24-source-rights-authority.md`](docs/decisions/N-24-source-rights-authority.md) — N-24 — Acquisition-Rights Authority: Designated Role, Scope Limited to N-21 §5.5
- [`R-01-immutable-versioned-objects.md`](docs/decisions/R-01-immutable-versioned-objects.md) — R-01 — Immutable Versioned Objects
- [`R-02-object-lifecycle.md`](docs/decisions/R-02-object-lifecycle.md) — R-02 — Seven-State Object Lifecycle
- [`R-03-confidence-model.md`](docs/decisions/R-03-confidence-model.md) — R-03 — Two-Component Confidence with Monotonic Ceiling
- [`R-04-temporal-validity.md`](docs/decisions/R-04-temporal-validity.md) — R-04 — Explicit Temporal Validity, No Automatic Decay
- [`R-05-canonical-claims.md`](docs/decisions/R-05-canonical-claims.md) — R-05 — Facts as Canonical Claims with Multiple Evidence Attachments
- [`R-06-relationship-taxonomy.md`](docs/decisions/R-06-relationship-taxonomy.md) — R-06 — Closed Ten-Type Relationship Taxonomy
- [`R-07-feedback-record.md`](docs/decisions/R-07-feedback-record.md) — R-7 — Feedback Record as the Ninth Intelligence Object
- [`R-08-behavioural-loop-closure.md`](docs/decisions/R-08-behavioural-loop-closure.md) — R-8 — Behavioural Loop Closure
- [`S-01-calibration-rubric.md`](docs/decisions/S-01-calibration-rubric.md) — S-1 — Confidence Calibration Rubric
- [`S-02-evidential-support-function.md`](docs/decisions/S-02-evidential-support-function.md) — S-2 — Evidential Support Function
- [`S-03-claim-equivalence.md`](docs/decisions/S-03-claim-equivalence.md) — S-3 — Structured Claim Decomposition and Fact Equivalence
- [`S-04-sufficiency-thresholds.md`](docs/decisions/S-04-sufficiency-thresholds.md) — S-4 — Evidence Sufficiency Thresholds
- [`S-05-extraction-fidelity.md`](docs/decisions/S-05-extraction-fidelity.md) — S-5 — Extraction Fidelity Verification

[`README.md`](docs/decisions/README.md) — grouped index with markers closed

---


## `docs/governance/`

| File | Contents |
|---|---|
| [`AGENT-PLAYBOOK.md`](docs/governance/AGENT-PLAYBOOK.md) | AI Agent Playbook |
| [`CONSTITUTION.md`](docs/governance/CONSTITUTION.md) | Opportunity Intelligence Platform |
| [`DECISION-REGISTER.md`](docs/governance/DECISION-REGISTER.md) | Architecture Decision Register |
| [`DECISION-TEMPLATE.md`](docs/governance/DECISION-TEMPLATE.md) | Decision Record Template |
| [`DEPENDENCY-MAP.md`](docs/governance/DEPENDENCY-MAP.md) | Decision Dependency Map |
| [`NON-GOALS.md`](docs/governance/NON-GOALS.md) | Platform Non-Goals |
| [`RATIFICATION-ANNOTATIONS.md`](docs/governance/RATIFICATION-ANNOTATIONS.md) | Ratification Annotations to Authoritative Documents |
| [`TIMELINE.md`](docs/governance/TIMELINE.md) | Architecture Decision Timeline |

---


## `docs/markers/`

| File | Contents |
|---|---|
| [`MARKER-REGISTER.md`](docs/markers/MARKER-REGISTER.md) | Marker Register |
| [`marker-crosswalk.md`](docs/markers/marker-crosswalk.md) | Canonical Marker Identifier Crosswalk |

---


## `docs/reviews/` — Reviews

| File | Contents |
|---|---|
| [`ARB-REVIEW-M-16.md`](docs/reviews/ARB-REVIEW-M-16.md) | Architecture Review Board — M-16 (Source Taxonomy, Eligibility, Trust) |
| [`ARB-REVIEW-P2-DECISION-SET.md`](docs/reviews/ARB-REVIEW-P2-DECISION-SET.md) | ARB Review — P2 Decision Set N-20 … N-23 |
| [`REVIEW-T00.2.7-feedback-record.md`](docs/reviews/REVIEW-T00.2.7-feedback-record.md) | Architecture Decision Review 1 |
| [`REVIEW-T00.2.8-loop-closure.md`](docs/reviews/REVIEW-T00.2.8-loop-closure.md) | Architecture Decision Review 2 |
| [`REVISION-2-REPORT.md`](docs/reviews/REVISION-2-REPORT.md) | P2 Decision Set — Revision 2 Report |
| [`README.md`](docs/reviews/README.md) | Directory guide |

---


## `docs/reports/` — Reports

| File | Contents |
|---|---|
| [`PHASE-1-CLOSURE-REPORT.md`](docs/reports/PHASE-1-CLOSURE-REPORT.md) | Phase 1 — Final Closure Report |
| [`T01.8.1-DEFECT-cascade-bfs-ordering.md`](docs/reports/T01.8.1-DEFECT-cascade-bfs-ordering.md) | DEFECT — Cascade partial-retraction spares an object whose entire support is withdrawn |
| [`T02.1.1-ARCHITECTURE-CHALLENGE.md`](docs/reports/T02.1.1-ARCHITECTURE-CHALLENGE.md) | T02.1.1 — Final Architecture Challenge (M-16) |
| [`T02.1.1-DERIVABILITY-INVESTIGATION.md`](docs/reports/T02.1.1-DERIVABILITY-INVESTIGATION.md) | T02.1.1 — Source Taxonomy Derivability Investigation |
| [`README.md`](docs/reports/README.md) | Directory guide |

---


## `docs/specifications/` — Specifications

| File | Contents |
|---|---|
| [`T01.2.5-specification.md`](docs/specifications/T01.2.5-specification.md) | T01.2.5 — ARCHIVED Tiering / Reachability Guard: Extracted Specification & Plan |
| [`T01.5.5-specification.md`](docs/specifications/T01.5.5-specification.md) | T01.5.5 — Calibration Rubric Conformance: Extracted Specification & Plan |
| [`T01.6.2-specification.md`](docs/specifications/T01.6.2-specification.md) | T01.6.2 — Processing-State Tracking: Extracted Specification |
| [`T01.6.3-specification.md`](docs/specifications/T01.6.3-specification.md) | T01.6.3 — Failure Surfacing: Extracted Specification & Implementation Plan |
| [`T01.6.4-specification.md`](docs/specifications/T01.6.4-specification.md) | T01.6.4 — Concurrency Boundary: Extracted Specification & Implementation Plan |
| [`T01.6.5-specification.md`](docs/specifications/T01.6.5-specification.md) | T01.6.5 — Sequencing Enforcement: Extracted Specification & Implementation Plan |
| [`T02.1.1-specification.md`](docs/specifications/T02.1.1-specification.md) | T02.1.1 — Source Model — Specification and Blocking Escalation |
| [`README.md`](docs/specifications/README.md) | Directory guide |

---


## `docs/playbooks/` — Playbooks

| File | Contents |
|---|---|
| [`P1-EXECUTION-PLAN.md`](docs/playbooks/P1-EXECUTION-PLAN.md) | P1 Execution Plan — Foundation |
| [`WORKING-METHOD.md`](docs/playbooks/WORKING-METHOD.md) | The Working Method |
| [`README.md`](docs/playbooks/README.md) | Directory guide |

---


## `docs/prompts/` — Prompts

| File | Contents |
|---|---|
| [`00-STANDING-INSTRUCTIONS.md`](docs/prompts/00-STANDING-INSTRUCTIONS.md) | Standing Instructions |
| [`01-TASK-EXECUTION.md`](docs/prompts/01-TASK-EXECUTION.md) | Prompt — Task Execution |
| [`02-PHASE-EXIT-GATE.md`](docs/prompts/02-PHASE-EXIT-GATE.md) | Prompt — Phase Exit Gate |
| [`03-ARCHITECTURE-INVESTIGATION.md`](docs/prompts/03-ARCHITECTURE-INVESTIGATION.md) | Prompt — Architecture Investigation |
| [`04-DECISION-DRAFTING.md`](docs/prompts/04-DECISION-DRAFTING.md) | Prompt — Decision Drafting |
| [`05-ARB-REVIEW.md`](docs/prompts/05-ARB-REVIEW.md) | Prompt — Architecture Review Board |
| [`06-RATIFICATION.md`](docs/prompts/06-RATIFICATION.md) | Prompt — Governance Review and Ratification |
| [`README.md`](docs/prompts/README.md) | Directory guide |

---


## `docs/research/` — Research

| File | Contents |
|---|---|
| [`DESIGN-SPACES.md`](docs/research/DESIGN-SPACES.md) | Design Spaces and Rejected Alternatives |
| [`REASONING-RECORDS.md`](docs/research/REASONING-RECORDS.md) | Reasoning Records |
| [`UNDERDETERMINATION-PROOFS.md`](docs/research/UNDERDETERMINATION-PROOFS.md) | Underdetermination Proofs |
| [`README.md`](docs/research/README.md) | Directory guide |

---


## `docs/appendices/` — Appendices — Unratified

| File | Contents |
|---|---|
| [`DRAFT-N-20-source-model.md`](docs/appendices/DRAFT-N-20-source-model.md) | N-20 — Source Model: Closed Taxonomy by Acquisition Channel, with Non-Scoring Trust |
| [`DRAFT-N-21-acquisition-rights.md`](docs/appendices/DRAFT-N-21-acquisition-rights.md) | N-21 — Acquisition Rights: Per-Source Assessment Recorded on Evidence, Enforced Before Acquisition |
| [`DRAFT-N-22-coverage-model.md`](docs/appendices/DRAFT-N-22-coverage-model.md) | N-22 — Coverage Model: Source-Type Coverage with Explicit Gap Declaration |
| [`DRAFT-N-23-research-trigger.md`](docs/appendices/DRAFT-N-23-research-trigger.md) | N-23 — Research Trigger: Directive-Scoped Acquisition Within Scheduled Cycles |
| [`PROPOSAL-M-16-source-model.md`](docs/appendices/PROPOSAL-M-16-source-model.md) | Architecture Decision Proposal — M-16: Source Taxonomy, Eligibility and Trust |
| [`README.md`](docs/appendices/README.md) | Directory guide |

---


## `templates/` — Templates

| File | Contents |
|---|---|
| [`COMPLETION-REPORT-TEMPLATE.md`](templates/COMPLETION-REPORT-TEMPLATE.md) | Completion Report — `<TASK-ID>` |
| [`DECISION-RECORD-TEMPLATE.md`](templates/DECISION-RECORD-TEMPLATE.md) | Decision Record Template |
| [`EXIT-GATE-REPORT-TEMPLATE.md`](templates/EXIT-GATE-REPORT-TEMPLATE.md) | Phase `<N>` Exit Gate Report |
| [`README.md`](templates/README.md) | Directory guide |

---


## `examples/` — Examples

| File | Contents |
|---|---|
| [`confidence-worked-example.md`](examples/confidence-worked-example.md) | Confidence Ceiling — Worked Example |
| [`worked-objects.md`](examples/worked-objects.md) | Worked Objects — from the Intelligence Object Model |
| [`README.md`](examples/README.md) | Directory guide |

---


## `assets/` — Assets

| File | Contents |
|---|---|
| [`diagrams.md`](assets/diagrams.md) | Diagrams |
| [`README.md`](assets/README.md) | Directory guide |
---

## `platform/` — The Implementation

| File | Contents |
|---|---|
| [`README.md`](platform/README.md) | Module map, constraints, environment traps |
| `Makefile` | `test` · `cov` · `stress` · `bench` · `all` |
| `pytest.ini` | `pythonpath=.` · `testpaths=tests` · `addopts=-m "not stress"` |
| `.coveragerc` | `source=oip` · `branch=True` · `fail_under=95` |

### `platform/oip/` — 29 production modules, 18,418 lines

| Group | Modules |
|---|---|
| Foundation | `enums` `identity` `contract` `lineage` `relationships` |
| Store & graph | `store` `graph` `configuration` `retention` |
| Acceptance | `acceptance` `integrity` `semantic` `lifecycle` `cascade` |
| Confidence | `support` `calibration` `claim` |
| Orchestration | `orchestration` |
| Object types | `evidence` `fact` `problem` `pattern` `opportunity` `solution` `validation` `execution` `feedback` |
| **Phase 2** | **`source`** |

### `platform/tests/` — 37 files, 3,329 tests

`conftest.py` plus 36 suites. Largest: `test_calibration` (157) ·
`test_processing_state` (134) · `test_sequencing` (129) ·
`test_concurrency_boundary` (120) · `test_stress` (116) ·
`test_failure_surfacing` (109) · `test_retention` (106) · `test_source` (59) ·
`test_partial_retraction` (54).

### `platform/benchmarks/` — 3

`bench_identity.py` · `baseline.json` · `BASELINE.md`

### `platform/validation/` — 77 + 3 superseded

| Kind | Count | Detail |
|---|---|---|
| Verifiers | 8 | **443 checks** — `closure_t01_8_1` (60) · `exit_gate_*` (94, 26) · `verify_t01_*` (405 total) · `verify_t02_1_1` (38) |
| Probes | 22 | `probe_*` — found the cascade defect and the archival defect |
| Mutation suites | 8 | `mutate_*` — 21/21 and 19/20 kill rates |
| Specifications | 7 | Mirrored in `docs/specifications/` |
| Reports | 4 | Mirrored in `docs/reports/` |
| Logs | 26 | Retained runs, including the two failed gates |
| Superseded | 3 | Pre-ratification M-16 verifiers, kept as audit trail |

[`README.md`](platform/validation/README.md) — full validation guide

---

## `scripts/` and `.github/`

| File | Contents |
|---|---|
| [`scripts/verify_all.sh`](scripts/verify_all.sh) | Complete validation battery — **13 checks** |
| [`scripts/README.md`](scripts/README.md) | Tooling notes and symlink rationale |
| [`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md) | AC table, F1–F12 checklist, mandatory Honest Limitations |

---

## Verification

```bash
./scripts/verify_all.sh          # 13 passed, 0 failed  (~2 min)
./scripts/verify_all.sh --full   # adds stress + mutation (~25 min)
```

| Check | Result |
|---|---|
| Unit tests | **3,201 passed** |
| Stress tests | **128 passed** |
| Coverage | **99.04%**, no module <95% |
| Phase 1 gates | 60/60 · 94/94 · 26/26 |
| Architecture verifiers | 405 checks |
| Phase 2 verifier | 38/38 |
| Probes | 9/9 |

---

## Cross-Reference Map

| To understand… | Start at | Then |
|---|---|---|
| Current state | `PROJECT_STATE.md` | `docs/phases/` *(see ROADMAP)* |
| What to do next | `NEXT_STEPS.md` | `docs/decisions/N-20…N-23` |
| The architecture | `ARCHITECTURE.md` | `docs/architecture/PKP_Intelligence_Object_Model.md` |
| The rules | `docs/governance/CONSTITUTION.md` | `docs/governance/AGENT-PLAYBOOK.md` |
| A marker | `docs/markers/MARKER-REGISTER.md` | `docs/markers/marker-crosswalk.md` |
| Why a decision was made | `docs/decisions/<ID>.md` | `docs/research/DESIGN-SPACES.md` |
| Why something is blocked | `docs/research/UNDERDETERMINATION-PROOFS.md` | `docs/reports/T02.1.1-*` |
| How to work | `CONTRIBUTING.md` | `docs/playbooks/WORKING-METHOD.md` · `docs/prompts/` |
| Mistakes already made | `docs/research/REASONING-RECORDS.md` | `docs/reports/T01.8.1-DEFECT-*` |
