# Architecture Decision Register

**Status:** Authoritative. This register is the **single source of decision truth** for the Opportunity Intelligence Platform.
**Established by:** `T00.1.1`
**Governing rule:** No architectural commitment is binding unless it appears in this register with a linked decision record.

---

## 1. Purpose

The platform's architecture is frozen. Change is permitted only where a contradiction makes implementation impossible. This register exists so that any future contributor can determine, for any architectural commitment:

- what was decided,
- what was rejected and why,
- what consequences were knowingly accepted,
- and under what conditions the decision should be revisited.

PKP v2 §8.2 records **MISSING-50**: v1 captured four architecture decisions as bare titles with no context, alternatives, rationale, or consequences. That gap is what this register closes. Without recorded alternatives, a future contributor cannot distinguish a considered constraint from an unexamined default — and will eventually violate one believing it to be the other.

## 2. Scope and Precedence

This register governs **architectural** decisions: anything affecting the pipeline, the nine engines, the three shared components, the object model, or the principles.

Precedence, highest first:

0. **[Platform Constitution](../CONSTITUTION.md)** — supreme
1. This register (decision records)
2. Intelligence Object Model — Complete Specification
3. PKP v2 — Master Reference
4. Pre-P1 Blocker Resolution Analysis
5. Implementation Backlog

Where a decision record conflicts with an earlier document, **the decision record wins** and the document is to be annotated, not silently overridden.

## 3. Status Vocabulary

| Status | Meaning | May be built against |
|---|---|---|
| `DRAFT` | Proposed, not agreed | No |
| `RATIFIED` | Agreed and binding | Yes |
| `RECONSTRUCTED` | Historical decision documented after the fact; substance binding, provenance inferred | Yes, with caution |
| `SUPERSEDED` | Replaced by a later decision; retained permanently | No |
| `REJECTED` | Considered and declined; retained permanently | No |

Records are **never deleted**. A superseded record remains in the register with a pointer to its successor — the same immutability discipline the platform applies to its own Intelligence Objects (D-01).

## 3a. Register Artefacts

| Artefact | Purpose | Established by |
|---|---|---|
| [`TEMPLATE.md`](TEMPLATE.md) | Mandatory structure for every decision record — six required fields | `T00.1.3` |
| [`marker-crosswalk.md`](marker-crosswalk.md) | Canonical marker identifier mapping; authoritative over IOM identifiers | `T00.1.2` |
| [`RATIFICATION-ANNOTATIONS.md`](RATIFICATION-ANNOTATIONS.md) | How ratified decisions modify interpretation of frozen documents | F00.2 |
| [`DEPENDENCY-MAP.md`](DEPENDENCY-MAP.md) | Decision dependency graph — depends on / enables / blocks / supersedes / related | F00.3 |
| [`NON-GOALS.md`](NON-GOALS.md) | Platform exclusion register (X1–X9) with anticipated scope-creep pressure | F00.3 |
| [`TIMELINE.md`](TIMELINE.md) | Chronological narrative: what triggered each decision and what changed after | F00.4 |
| [`../AGENT-PLAYBOOK.md`](../AGENT-PLAYBOOK.md) | Execution manual for any implementation agent | F00.6 |
| [`reviews/`](reviews) | Architecture Decision Reviews for escalations | Directed |

**All records must conform to `TEMPLATE.md`. All marker references must use canonical identifiers per `marker-crosswalk.md`.**

## 4. Record Identifier Scheme

| Prefix | Meaning | Source |
|---|---|---|
| `AD-nn` | Architecture principle — v1 original or platform-wide standing rule | PKP v1 §8; AD-05 directed 2026-08-02 |
| `R-n` | Ratification of an Intelligence Object Model decision (D-01…D-08) | Backlog `T00.2.x` |
| `N-nn` | New decision required before P1 | Backlog `T00.3.x`–`T00.6.x` |
| `S-n` | Semantic decision required before first object write | Backlog `T00.5.x` |

Identifiers are permanent and never reused.

## 5. Register

| ID | Title | Status | Owner | Date | Record |
|---|---|---|---|---|---|
| **AD-01** | Evidence-First | `RECONSTRUCTED` | Platform Architecture | 2026-08-02 | [AD-01](AD-01-evidence-first.md) |
| **AD-02** | Intelligence Contracts | `RECONSTRUCTED` | Platform Architecture | 2026-08-02 | [AD-02](AD-02-intelligence-contracts.md) |
| **AD-03** | Feedback Loop | `RECONSTRUCTED` | Platform Architecture | 2026-08-02 | [AD-03](AD-03-feedback-loop.md) |
| **AD-04** | Separation of Concerns | `RECONSTRUCTED` | Platform Architecture | 2026-08-02 | [AD-04](AD-04-separation-of-concerns.md) |
| **AD-05** | **Ground Truth Protection Principle** | `RATIFIED` | Platform Architecture | 2026-08-02 | [AD-05](AD-05-ground-truth-protection.md) |
| **R-1** | Ratify D-01: immutable versioned objects | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-01](R-01-immutable-versioned-objects.md) |
| **R-2** | Ratify D-02: seven-state lifecycle | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-02](R-02-object-lifecycle.md) |
| **R-3** | Ratify D-03: two-component confidence | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-03](R-03-confidence-model.md) |
| **R-4** | Ratify D-04: temporal validity | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-04](R-04-temporal-validity.md) |
| **R-5** | Ratify D-05: canonical claims | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-05](R-05-canonical-claims.md) |
| **R-6** | Ratify D-06: relationship taxonomy | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-06](R-06-relationship-taxonomy.md) |
| **R-7** | Ratify D-07: Feedback Record (🔺 escalation) | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-07](R-07-feedback-record.md) |
| **R-8** | Ratify D-08 + C-04 closure (🔺 escalation) | `RATIFIED` | Platform Architecture | 2026-08-02 | [R-08](R-08-behavioural-loop-closure.md) |
| **N-1** | Platform boundary: advisory with handoff | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-1](N-01-platform-boundary.md) |
| **N-2** | Human gates at three transitions | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-2](N-02-human-gates.md) |
| **N-3** | Success measures | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-3](N-03-success-criteria.md) |
| **N-4** | Determinism posture | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-4](N-04-determinism.md) |
| **N-5** | Tenancy discriminator | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-5](N-05-tenancy.md) |
| **N-6** | Store/Graph boundary and consistency | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-6](N-06-store-graph-boundary.md) |
| **N-7** | Configuration referent + CI-1 isolation (🔺 escalation) | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-7](N-07-configuration-referent.md) |
| **N-8** | Acceptance authority | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-8](N-08-acceptance-authority.md) |
| **N-9** | Cascade invalidation owner | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-9](N-09-cascade-invalidation.md) |
| **N-10** | Failure representation | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-10](N-10-failure-representation.md) |
| **N-11** | Concurrency model | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-11](N-11-concurrency.md) |
| **N-12** | Retention policy | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-12](N-12-retention.md) |
| **N-13** | Explanation skeleton | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-13](N-13-explanation-skeleton.md) |
| **N-14** | Cross-stage read access | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-14](N-14-cross-stage-read-access.md) |
| **N-15** | Evidence storage: hybrid | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-15](N-15-evidence-storage.md) |
| **S-1** | Confidence calibration rubric | `RATIFIED` | Platform Architecture | 2026-08-02 | [S-1](S-01-calibration-rubric.md) |
| **S-2** | Evidential support function | `RATIFIED` | Platform Architecture | 2026-08-02 | [S-2](S-02-evidential-support-function.md) |
| **S-3** | Claim decomposition and Fact equivalence | `RATIFIED` | Platform Architecture | 2026-08-02 | [S-3](S-03-claim-equivalence.md) |
| **S-4** | Evidence sufficiency thresholds | `RATIFIED` | Platform Architecture | 2026-08-02 | [S-4](S-04-sufficiency-thresholds.md) |
| **S-5** | Extraction fidelity verification | `RATIFIED` | Platform Architecture | 2026-08-02 | [S-5](S-05-extraction-fidelity.md) |
| **N-16** | Source diversity propagation | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-16](N-16-source-diversity-propagation.md) |
| **N-17** | Orchestration control model | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-17](N-17-orchestration-control-model.md) |
| **N-18** | Orchestration phased into P1 (C-08) | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-18](N-18-orchestration-phasing.md) |
| **N-19** | Experiment Registry placement | `RATIFIED` | Platform Architecture | 2026-08-02 | [N-19](N-19-experiment-registry-placement.md) |
| **N-20** | Source model: taxonomy, eligibility, non-scoring trust (🔺 escalation) | `RATIFIED` | Platform Architecture | 2026-08-04 | [N-20](N-20-source-model.md) |
| **N-21** | Acquisition rights: per-source assessment, enforced pre-acquisition (🔺 escalation) | `RATIFIED` | Platform Architecture | 2026-08-04 | [N-21](N-21-acquisition-rights.md) |
| **N-22** | Coverage model: source-type coverage with explicit gap declaration | `RATIFIED` | Platform Architecture | 2026-08-04 | [N-22](N-22-coverage-model.md) |
| **N-23** | Research trigger: directive-scoped acquisition within scheduled cycles | `RATIFIED` | Platform Architecture | 2026-08-04 | [N-23](N-23-research-trigger.md) |

**Ratified: 37 · Reconstructed: 4 · Draft: 0 · Total: 41**

> **P2 decision set added 2026-08-04.** N-20…N-23 were ratified together by the
> Project Owner with recorded reservations (AS-0…AS-5, held in each record's
> *Honest Limitations*). All four close their markers **partially**; none
> supersedes an existing record.

Phase 0 completes when every row above reaches `RATIFIED` (or `RECONSTRUCTED` for AD-01…AD-04), verified by `T00.7.1`.

> Rows beyond AD-01…AD-04 are **placeholders**, pre-registered so that identifiers are stable and the Phase 0 exit gate has a definitive checklist. Their `DRAFT` status means no work may be built against them.

## 6. Additional Decisions Expected

The following are required by the backlog but fall outside the `T00.7.1` minimum set. They are recorded here so they are not lost; identifiers are assigned when the decision is taken.

| Backlog task | Decision | Phase |
|---|---|---|
| `T00.4.8` | Evidence storage: full content, reference, or hybrid (OQ-12) | 0 |
| `T00.6.1` | Source diversity propagation (M-23) | 0 |
| `T00.6.2` | Orchestration control model (M-35, M-37) | 0 |
| `T00.6.3` | Orchestration roadmap phase (C-08) | 0 |
| `T00.6.4` | Experiment Registry placement (M-53) | 0 |
| `T06.1.2` | Prior research disposition (M-49) | 6 |
| `T06.2.5` | Scoring ownership (C-01) | 6 |
| `T07.1.1` | Validation / Experiment Registry boundary (C-05) | 7 |
| `T07.2.1` | Solution granularity (M-29) | 7 |
| `T08.1.1` | Execution stage owner (C-02) 🔺 | 8 |

## 7. Amendment Procedure

1. A proposed change is raised as a new record in `DRAFT`, never by editing a `RATIFIED` record.
2. The proposal states which existing record it supersedes.
3. On agreement, the new record becomes `RATIFIED` and the prior becomes `SUPERSEDED`.
4. Documents affected by the change are annotated with the new record's identifier.

**A marker (MISSING / OPEN QUESTION / CONTRADICTION) is closed only by a record in this register.** Closing a marker by implementation choice is prohibited — an architecture decision made in code is an architecture decision that cannot be found.

## 8. Note on the Reconstructed Records

AD-01 through AD-04 are marked `RECONSTRUCTED`, not `RATIFIED`. v1 recorded these four decisions as titles only. Their **substance** is established by PKP v2 §8, which is authoritative and frozen.

Their **alternatives and rationale** are not recorded anywhere and cannot be recovered. Each record therefore separates:

- **Established** — traceable to a frozen document, binding without qualification.
- **Reconstructed** — inferred from the architecture's internal logic, marked as such, and **not** to be cited as evidence of what was historically considered.

This distinction is preserved deliberately. Presenting inferred rationale as historical record would be exactly the failure the platform's own Principle 1 exists to prevent: a conclusion asserted beyond its evidence.
