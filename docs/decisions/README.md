# Decision Records

**41 ratified decisions. One file each — never merged.**

This directory is the authority for every architectural question. It outranks
the IOM, PKP v2 and the Implementation Backlog (Constitution Article XI).

Register index with status and dates:
[`../governance/DECISION-REGISTER.md`](../governance/DECISION-REGISTER.md)

---

## Architecture Decisions — 5

| ID | Title | Status | Closes |
|---|---|---|---|
| [`AD-01`](AD-01-evidence-first.md) | Evidence-First | `RECONSTRUCTED` | — |
| [`AD-02`](AD-02-intelligence-contracts.md) | Intelligence Contracts | `RECONSTRUCTED` | — |
| [`AD-03`](AD-03-feedback-loop.md) | Feedback Loop | `RECONSTRUCTED` | — |
| [`AD-04`](AD-04-separation-of-concerns.md) | Separation of Concerns | `RECONSTRUCTED` | — |
| [`AD-05`](AD-05-ground-truth-protection.md) | **Ground Truth Protection** | `RATIFIED` | C-04 (jointly) |

> AD-01…AD-04 were inherited from v1 as **bare titles**. Their alternatives are
> *reconstructed*, not recovered, and must never be cited as evidence of what
> was historically debated. That omission is M-50 — the project's founding
> defect.

## IOM Ratifications — 8

| ID | Title | Closes |
|---|---|---|
| [`R-01`](R-01-immutable-versioned-objects.md) | Immutable versioned objects | M-08 |
| [`R-02`](R-02-object-lifecycle.md) | Seven-state lifecycle | M-45, OQ-04 |
| [`R-03`](R-03-confidence-model.md) | Two-component confidence | M-15 |
| [`R-04`](R-04-temporal-validity.md) | Temporal validity | M-46 |
| [`R-05`](R-05-canonical-claims.md) | Canonical claims | M-11 |
| [`R-06`](R-06-relationship-taxonomy.md) | Ten-type relationship taxonomy | M-40 |
| [`R-07`](R-07-feedback-record.md) 🔺 | Feedback Record as ninth object | C-03 |
| [`R-08`](R-08-behavioural-loop-closure.md) 🔺 | Behavioural loop closure | C-04 |

## Scope, Boundary and Control — 23

| ID | Title | Closes |
|---|---|---|
| [`N-01`](N-01-platform-boundary.md) | Platform boundary: advisory | M-03, M-05 |
| [`N-02`](N-02-human-gates.md) | **Human gates — exactly three** | OQ-02, OQ-05 |
| [`N-03`](N-03-success-criteria.md) | Success measures | M-04 |
| [`N-04`](N-04-determinism.md) | Determinism posture | OQ-01 |
| [`N-05`](N-05-tenancy.md) | Tenancy discriminator | — |
| [`N-06`](N-06-store-graph-boundary.md) | Store / Graph boundary | C-06, M-39 |
| [`N-07`](N-07-configuration-referent.md) 🔺 | Configuration referent + CI-1 | M-63 |
| [`N-08`](N-08-acceptance-authority.md) | Acceptance authority | M-64 |
| [`N-09`](N-09-cascade-invalidation.md) | Cascade invalidation | M-58, M-09 |
| [`N-10`](N-10-failure-representation.md) | Failure representation | M-36 |
| [`N-11`](N-11-concurrency.md) | Concurrency model | OQ-13 |
| [`N-12`](N-12-retention.md) | Retention | M-38 |
| [`N-13`](N-13-explanation-skeleton.md) | Explanation skeleton | M-07 |
| [`N-14`](N-14-cross-stage-read-access.md) | Cross-stage read access | OQ-18 |
| [`N-15`](N-15-evidence-storage.md) | Evidence storage (licence-driven) | OQ-12 |
| [`N-16`](N-16-source-diversity-propagation.md) | Source diversity propagation | M-23 |
| [`N-17`](N-17-orchestration-control-model.md) | Orchestration control model | M-35, M-37, OQ-15 |
| [`N-18`](N-18-orchestration-phasing.md) | Orchestration phasing | C-08 |
| [`N-19`](N-19-experiment-registry-placement.md) | Experiment Registry placement | M-53 |
| [`N-20`](N-20-source-model.md) 🔺 | **Source model** | M-16 (partial), OQ-28 |
| [`N-21`](N-21-acquisition-rights.md) 🔺 | **Acquisition rights** | M-18 (partial) |
| [`N-22`](N-22-coverage-model.md) | **Coverage model** | M-17 (partial) |
| [`N-23`](N-23-research-trigger.md) | **Research trigger** | M-01 (partial) |

## Semantics — 5

| ID | Title | Closes |
|---|---|---|
| [`S-01`](S-01-calibration-rubric.md) | Calibration rubric — five bands | M-60 |
| [`S-02`](S-02-evidential-support-function.md) | **Evidential support — five exhaustive inputs** | M-59 |
| [`S-03`](S-03-claim-equivalence.md) | Claim equivalence | M-62 |
| [`S-04`](S-04-sufficiency-thresholds.md) | Sufficiency thresholds | M-06 |
| [`S-05`](S-05-extraction-fidelity.md) | Extraction fidelity | M-67 *(partially)* |

---

## Rules

1. **A marker is closed only by a record here** (Playbook F3).
2. **Records are immutable once `RATIFIED`** — change by superseding record.
3. **Six mandatory fields** — see [`../governance/DECISION-TEMPLATE.md`](../governance/DECISION-TEMPLATE.md).
4. **Cite canonical identifiers only** — resolve through [`../markers/marker-crosswalk.md`](../markers/marker-crosswalk.md).
5. **Escalations (🔺) need explicit human sign-off** (F6), individually by name.

## Recorded Reservations

AS-0…AS-5 are binding and live inside the records they qualify — N-20 §13 and
N-22 §15. See [`../../PROJECT_STATE.md`](../../PROJECT_STATE.md) §5.
