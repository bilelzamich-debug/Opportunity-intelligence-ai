# Decision Dependency Map

**Status:** Authoritative. Machine-validated.  
**Established by:** F00.3  
**Scope:** Every Architecture Decision (`AD-nn`), Ratified Decision (`R-n`), and pending decision (`N-nn`, `S-n`).

---

## 1. Purpose

Decisions constrain one another. Without an explicit map, a future contributor cannot tell which decisions a proposed change would invalidate, and supersession becomes guesswork.

This map records five relationships for every decision:

| Relationship | Meaning |
|---|---|
| **Depends on** | This decision is only coherent if the listed decisions hold. Reversing one requires revisiting this. |
| **Enables** | Decisions that became possible or necessary because of this one. |
| **Blocks** | Pending (`DRAFT`) decisions that cannot be taken until this one is ratified. Transitively derived. |
| **Supersedes** | Decisions replaced by this one. |
| **Related** | Decisions that interact without a dependency. Symmetric. |

**Validation:** the graph is machine-checked for reciprocity (every *enables* has a matching *depends on*), symmetry of *related*, and absence of cycles. All checks pass — 0 issues, 0 cycles, 32 nodes.

---

## 2. Foundation Layer

Four decisions have **no dependencies**. They are the architecture's roots — everything else rests on them.

| Decision | Title | Status |
|---|---|---|
| [AD-01](AD-01-evidence-first.md) | Evidence-First | `RECONSTRUCTED` |
| [AD-03](AD-03-feedback-loop.md) | Feedback Loop | `RECONSTRUCTED` |
| [N-1](N-01-platform-boundary.md) | Platform Boundary (advisory) | `RATIFIED` |
| `N-13` | Explanation Skeleton | `DRAFT` |
| [R-1](R-01-immutable-versioned-objects.md) | Immutable Versioned Objects | `RATIFIED` |
| [R-4](R-04-temporal-validity.md) | Temporal Validity | `RATIFIED` |

> Reversing any root decision invalidates a large part of the architecture. AD-01 alone enables five decisions directly and far more transitively.

---

## 3. Critical Path

Ranked by how many pending decisions each ratified decision unblocks.

| Decision | Blocks (pending) | Count |
|---|---|---:|
| [AD-01](AD-01-evidence-first.md) | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-1`, `S-2`, `S-3`, `S-4`, `S-5` | 13 |
| [R-1](R-01-immutable-versioned-objects.md) | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-2`, `S-3`, `S-4`, `S-5` | 12 |
| [AD-02](AD-02-intelligence-contracts.md) | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` | 9 |
| [AD-03](AD-03-feedback-loop.md) | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` | 9 |
| [R-6](R-06-relationship-taxonomy.md) | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` | 9 |
| [R-8](R-08-behavioural-loop-closure.md) | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` | 9 |
| [R-5](R-05-canonical-claims.md) | `S-2`, `S-3`, `S-4`, `S-5` | 4 |
| [R-3](R-03-confidence-model.md) | `S-1`, `S-2`, `S-4` | 3 |
| [N-1](N-01-platform-boundary.md) | `S-1`, `S-2`, `S-4` | 3 |
| [N-3](N-03-success-criteria.md) | `S-1`, `S-2`, `S-4` | 3 |
| [R-2](R-02-object-lifecycle.md) | `N-12`, `N-9` | 2 |
| [N-4](N-04-determinism.md) | `N-10`, `N-7` | 2 |
| [AD-04](AD-04-separation-of-concerns.md) | `N-9` | 1 |

**Highest-leverage pending decision:**

- **`N-6` Store/Graph Boundary** — blocks 8 further decisions: `N-10`, `N-11`, `N-12`, `N-14`, `N-7`, `N-8`, `N-9`, `S-5`
- **`N-8` Acceptance Authority** — blocks 2 further decisions: `N-9`, `S-5`
- **`S-1` Confidence Calibration Rubric** — blocks 2 further decisions: `S-2`, `S-4`

---

## 4. Full Map

### [AD-01](AD-01-evidence-first.md) — Evidence-First  `RECONSTRUCTED`

| | |
|---|---|
| **Depends on** | — |
| **Enables** | [AD-02](AD-02-intelligence-contracts.md), [AD-05](AD-05-ground-truth-protection.md), [R-3](R-03-confidence-model.md), [R-5](R-05-canonical-claims.md), [R-8](R-08-behavioural-loop-closure.md) |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-1`, `S-2`, `S-3`, `S-4`, `S-5` |
| **Supersedes** | — |
| **Related** | [AD-03](AD-03-feedback-loop.md), [AD-05](AD-05-ground-truth-protection.md) |

### [AD-02](AD-02-intelligence-contracts.md) — Intelligence Contracts  `RECONSTRUCTED`

| | |
|---|---|
| **Depends on** | [AD-01](AD-01-evidence-first.md) |
| **Enables** | [AD-04](AD-04-separation-of-concerns.md), [R-6](R-06-relationship-taxonomy.md), [R-7](R-07-feedback-record.md) |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` |
| **Supersedes** | — |
| **Related** | [AD-04](AD-04-separation-of-concerns.md) |

### [AD-03](AD-03-feedback-loop.md) — Feedback Loop  `RECONSTRUCTED`

| | |
|---|---|
| **Depends on** | — |
| **Enables** | [R-7](R-07-feedback-record.md), [R-8](R-08-behavioural-loop-closure.md) |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` |
| **Supersedes** | — |
| **Related** | [AD-01](AD-01-evidence-first.md), [AD-05](AD-05-ground-truth-protection.md) |

### [AD-04](AD-04-separation-of-concerns.md) — Separation of Concerns  `RECONSTRUCTED`

| | |
|---|---|
| **Depends on** | [AD-02](AD-02-intelligence-contracts.md) |
| **Enables** | [N-2](N-02-human-gates.md), `N-9` |
| **Blocks** | `N-9` |
| **Supersedes** | — |
| **Related** | [AD-02](AD-02-intelligence-contracts.md), `N-14` |

### [AD-05](AD-05-ground-truth-protection.md) — Ground Truth Protection  `RATIFIED`

| | |
|---|---|
| **Depends on** | [AD-01](AD-01-evidence-first.md), [R-8](R-08-behavioural-loop-closure.md), [R-7](R-07-feedback-record.md) |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [AD-01](AD-01-evidence-first.md), [AD-03](AD-03-feedback-loop.md), [R-7](R-07-feedback-record.md), [R-8](R-08-behavioural-loop-closure.md) |

### [R-1](R-01-immutable-versioned-objects.md) — Immutable Versioned Objects  `RATIFIED`

| | |
|---|---|
| **Depends on** | — |
| **Enables** | [R-2](R-02-object-lifecycle.md), [R-5](R-05-canonical-claims.md), [N-4](N-04-determinism.md), `N-6`, `N-12` |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-2`, `S-3`, `S-4`, `S-5` |
| **Supersedes** | — |
| **Related** | `N-12`, [N-4](N-04-determinism.md), [R-2](R-02-object-lifecycle.md), [R-4](R-04-temporal-validity.md) |

### [R-2](R-02-object-lifecycle.md) — Seven-State Lifecycle  `RATIFIED`

| | |
|---|---|
| **Depends on** | [R-1](R-01-immutable-versioned-objects.md) |
| **Enables** | [N-2](N-02-human-gates.md), `N-9`, `N-12` |
| **Blocks** | `N-12`, `N-9` |
| **Supersedes** | — |
| **Related** | `N-12`, `N-9`, [R-1](R-01-immutable-versioned-objects.md) |

### [R-3](R-03-confidence-model.md) — Two-Component Confidence  `RATIFIED`

| | |
|---|---|
| **Depends on** | [AD-01](AD-01-evidence-first.md) |
| **Enables** | `S-1`, `S-2`, `S-4` |
| **Blocks** | `S-1`, `S-2`, `S-4` |
| **Supersedes** | — |
| **Related** | [R-5](R-05-canonical-claims.md), `S-1`, `S-2` |

### [R-4](R-04-temporal-validity.md) — Temporal Validity  `RATIFIED`

| | |
|---|---|
| **Depends on** | — |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [R-1](R-01-immutable-versioned-objects.md) |

### [R-5](R-05-canonical-claims.md) — Canonical Claims  `RATIFIED`

| | |
|---|---|
| **Depends on** | [R-1](R-01-immutable-versioned-objects.md), [AD-01](AD-01-evidence-first.md) |
| **Enables** | `S-3`, `S-2` |
| **Blocks** | `S-2`, `S-3`, `S-4`, `S-5` |
| **Supersedes** | — |
| **Related** | [R-3](R-03-confidence-model.md), `S-3` |

### [R-6](R-06-relationship-taxonomy.md) — Relationship Taxonomy  `RATIFIED`

| | |
|---|---|
| **Depends on** | [AD-02](AD-02-intelligence-contracts.md) |
| **Enables** | `N-6`, [R-7](R-07-feedback-record.md) |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` |
| **Supersedes** | — |
| **Related** | `N-6` |

### [R-7](R-07-feedback-record.md) — Feedback Record (9th object)  `RATIFIED`

| | |
|---|---|
| **Depends on** | [AD-02](AD-02-intelligence-contracts.md), [AD-03](AD-03-feedback-loop.md), [R-6](R-06-relationship-taxonomy.md) |
| **Enables** | [AD-05](AD-05-ground-truth-protection.md) |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [AD-05](AD-05-ground-truth-protection.md), [R-8](R-08-behavioural-loop-closure.md) |

### [R-8](R-08-behavioural-loop-closure.md) — Behavioural Loop Closure  `RATIFIED`

| | |
|---|---|
| **Depends on** | [AD-01](AD-01-evidence-first.md), [AD-03](AD-03-feedback-loop.md) |
| **Enables** | [AD-05](AD-05-ground-truth-protection.md), `N-6` |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-6`, `N-7`, `N-8`, `N-9`, `S-5` |
| **Supersedes** | — |
| **Related** | [AD-05](AD-05-ground-truth-protection.md), `N-6`, [R-7](R-07-feedback-record.md) |

### [N-1](N-01-platform-boundary.md) — Platform Boundary (advisory)  `RATIFIED`

| | |
|---|---|
| **Depends on** | — |
| **Enables** | [N-2](N-02-human-gates.md), [N-3](N-03-success-criteria.md), [N-5](N-05-tenancy.md) |
| **Blocks** | `S-1`, `S-2`, `S-4` |
| **Supersedes** | — |
| **Related** | [N-2](N-02-human-gates.md), [N-3](N-03-success-criteria.md), [N-5](N-05-tenancy.md) |

### [N-2](N-02-human-gates.md) — Human Gates at Three Transitions  `RATIFIED`

| | |
|---|---|
| **Depends on** | [N-1](N-01-platform-boundary.md), [R-2](R-02-object-lifecycle.md), [AD-04](AD-04-separation-of-concerns.md) |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [N-1](N-01-platform-boundary.md), [N-3](N-03-success-criteria.md) |

### [N-3](N-03-success-criteria.md) — Success Criteria  `RATIFIED`

| | |
|---|---|
| **Depends on** | [N-1](N-01-platform-boundary.md) |
| **Enables** | `S-1` |
| **Blocks** | `S-1`, `S-2`, `S-4` |
| **Supersedes** | — |
| **Related** | [N-1](N-01-platform-boundary.md), `N-13`, [N-2](N-02-human-gates.md), `S-1` |

### [N-4](N-04-determinism.md) — Determinism Posture  `RATIFIED`

| | |
|---|---|
| **Depends on** | [R-1](R-01-immutable-versioned-objects.md) |
| **Enables** | `N-7` |
| **Blocks** | `N-10`, `N-7` |
| **Supersedes** | — |
| **Related** | `N-7`, [R-1](R-01-immutable-versioned-objects.md) |

### [N-5](N-05-tenancy.md) — Tenancy Discriminator Reserved  `RATIFIED`

| | |
|---|---|
| **Depends on** | [N-1](N-01-platform-boundary.md) |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [N-1](N-01-platform-boundary.md) |

### `N-6` — Store/Graph Boundary  `DRAFT`

| | |
|---|---|
| **Depends on** | [R-1](R-01-immutable-versioned-objects.md), [R-8](R-08-behavioural-loop-closure.md), [R-6](R-06-relationship-taxonomy.md) |
| **Enables** | `N-7`, `N-8`, `N-9`, `N-11`, `N-12`, `N-14` |
| **Blocks** | `N-10`, `N-11`, `N-12`, `N-14`, `N-7`, `N-8`, `N-9`, `S-5` |
| **Supersedes** | — |
| **Related** | `N-11`, [R-6](R-06-relationship-taxonomy.md), [R-8](R-08-behavioural-loop-closure.md) |

### `N-7` — Configuration Referent  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-6`, [N-4](N-04-determinism.md) |
| **Enables** | `N-10` |
| **Blocks** | `N-10` |
| **Supersedes** | — |
| **Related** | `N-10`, [N-4](N-04-determinism.md) |

### `N-8` — Acceptance Authority  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-6` |
| **Enables** | `N-9`, `S-5` |
| **Blocks** | `N-9`, `S-5` |
| **Supersedes** | — |
| **Related** | `N-9`, `S-5` |

### `N-9` — Cascade Invalidation Owner  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-6`, `N-8`, [R-2](R-02-object-lifecycle.md), [AD-04](AD-04-separation-of-concerns.md) |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | `N-8`, [R-2](R-02-object-lifecycle.md) |

### `N-10` — Failure Representation  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-7` |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | `N-7` |

### `N-11` — Concurrency Model  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-6` |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | `N-6` |

### `N-12` — Retention Policy  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-6`, [R-1](R-01-immutable-versioned-objects.md), [R-2](R-02-object-lifecycle.md) |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [R-1](R-01-immutable-versioned-objects.md), [R-2](R-02-object-lifecycle.md) |

### `N-13` — Explanation Skeleton  `DRAFT`

| | |
|---|---|
| **Depends on** | — |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [N-3](N-03-success-criteria.md) |

### `N-14` — Cross-Stage Read Access  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-6` |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | [AD-04](AD-04-separation-of-concerns.md) |

### `S-1` — Confidence Calibration Rubric  `DRAFT`

| | |
|---|---|
| **Depends on** | [R-3](R-03-confidence-model.md), [N-3](N-03-success-criteria.md) |
| **Enables** | `S-2` |
| **Blocks** | `S-2`, `S-4` |
| **Supersedes** | — |
| **Related** | [N-3](N-03-success-criteria.md), [R-3](R-03-confidence-model.md), `S-2` |

### `S-2` — Evidential Support Function  `DRAFT`

| | |
|---|---|
| **Depends on** | `S-1`, [R-3](R-03-confidence-model.md), [R-5](R-05-canonical-claims.md) |
| **Enables** | `S-4` |
| **Blocks** | `S-4` |
| **Supersedes** | — |
| **Related** | [R-3](R-03-confidence-model.md), `S-1`, `S-4` |

### `S-3` — Claim Decomposition & Fact Equivalence  `DRAFT`

| | |
|---|---|
| **Depends on** | [R-5](R-05-canonical-claims.md) |
| **Enables** | `S-5` |
| **Blocks** | `S-5` |
| **Supersedes** | — |
| **Related** | [R-5](R-05-canonical-claims.md), `S-5` |

### `S-4` — Evidence Sufficiency Thresholds  `DRAFT`

| | |
|---|---|
| **Depends on** | `S-2`, [R-3](R-03-confidence-model.md) |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | `S-2` |

### `S-5` — Extraction Fidelity Verification  `DRAFT`

| | |
|---|---|
| **Depends on** | `N-8`, `S-3` |
| **Enables** | — |
| **Blocks** | — |
| **Supersedes** | — |
| **Related** | `N-8`, `S-3` |

---

## 5. Impact Analysis — What Reversal Would Cost

For each ratified decision, the decisions that would require revisiting if it were reversed.

| If reversed | Directly invalidates | Transitively affects |
|---|---|---:|
| [AD-01](AD-01-evidence-first.md) | [AD-02](AD-02-intelligence-contracts.md), [AD-05](AD-05-ground-truth-protection.md), [R-3](R-03-confidence-model.md), [R-5](R-05-canonical-claims.md), [R-8](R-08-behavioural-loop-closure.md) | 22 |
| [AD-02](AD-02-intelligence-contracts.md) | [AD-04](AD-04-separation-of-concerns.md), [R-6](R-06-relationship-taxonomy.md), [R-7](R-07-feedback-record.md) | 14 |
| [AD-03](AD-03-feedback-loop.md) | [R-7](R-07-feedback-record.md), [R-8](R-08-behavioural-loop-closure.md) | 12 |
| [AD-04](AD-04-separation-of-concerns.md) | [N-2](N-02-human-gates.md), `N-9` | 2 |
| [R-1](R-01-immutable-versioned-objects.md) | [R-2](R-02-object-lifecycle.md), [R-5](R-05-canonical-claims.md), [N-4](N-04-determinism.md), `N-6`, `N-12` | 16 |
| [R-2](R-02-object-lifecycle.md) | [N-2](N-02-human-gates.md), `N-9`, `N-12` | 3 |
| [R-3](R-03-confidence-model.md) | `S-1`, `S-2`, `S-4` | 3 |
| [R-5](R-05-canonical-claims.md) | `S-3`, `S-2` | 4 |
| [R-6](R-06-relationship-taxonomy.md) | `N-6`, [R-7](R-07-feedback-record.md) | 11 |
| [R-7](R-07-feedback-record.md) | [AD-05](AD-05-ground-truth-protection.md) | 1 |
| [R-8](R-08-behavioural-loop-closure.md) | [AD-05](AD-05-ground-truth-protection.md), `N-6` | 10 |
| [N-1](N-01-platform-boundary.md) | [N-2](N-02-human-gates.md), [N-3](N-03-success-criteria.md), [N-5](N-05-tenancy.md) | 6 |
| [N-3](N-03-success-criteria.md) | `S-1` | 3 |
| [N-4](N-04-determinism.md) | `N-7` | 2 |

> **Reading this table:** AD-01 and R-1 have the widest blast radius. Any proposal touching them should be treated as an architecture-wide change, not a local one.

---

## 6. Maintenance Rule

When a decision is recorded or superseded, this map is updated **in the same change**. Specifically:

1. Add the decision's five relationships.
2. Add the reciprocal edge to every decision it names — every *enables* must appear as a *depends on*, and *related* is symmetric.
3. Re-run validation: reciprocity, symmetry, no cycles.
4. A decision with no relationships is suspicious — it likely means the interactions were not considered.

**A map that is not maintained is worse than none**, because it will be trusted.
