# S-3 — Structured Claim Decomposition and Fact Equivalence

| Field | Value |
|---|---|
| **ID** | S-3 |
| **Title** | Structured Claim Decomposition and Fact Equivalence |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | M-62 |
| **Backlog task** | `T00.5.3` |
| **Depends on** | [R-5](R-05-canonical-claims.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

### Claim structure

Every extracted claim decomposes into four components:

| Component | Meaning | Required |
|---|---|---|
| **Subject** | What the claim is about | Yes |
| **Predicate** | What is asserted about the subject | Yes |
| **Qualifier** | Conditions under which it holds (scope, population, period) | Yes — explicitly `NONE` if unqualified |
| **Value** | Quantity or magnitude, where present | No |

### Equivalence test — checkable, not opinion

Two claims are **equivalent** only if **all** hold:

1. **Subjects** refer to the same entity or class
2. **Predicates** assert the same property or relation
3. **Qualifiers** are identical, or one **strictly contains** the other
4. **Values**, where both present, agree within stated precision

Failing any condition, the claims are **not equivalent**.

### Merge policy — conservative, explicitly

| Outcome | Action |
|---|---|
| All four conditions met | **Merge** — add an evidence attachment to the canonical Fact (R-5) |
| Any condition fails | **Do not merge** — create a separate Fact |
| Equivalence **uncertain** | **Do not merge** — create a separate Fact and record `DUPLICATES` |

**Under-merging is preferred over over-merging, deliberately and explicitly.**

The asymmetry is decisive: under-merging inflates apparent corroboration but leaves both claims visible, linked, and correctable. Over-merging destroys information **irreversibly** — object identity is permanent under I2, and a merged claim cannot be separated once its attachments are combined.

Where qualifiers differ in scope (condition 3, containment case), the **narrower** claim is retained as canonical and the broader recorded separately. A broad claim is not evidence for a narrow one.

## Context

R-5 established Facts as canonical claims: equivalent extractions attach to an existing Fact rather than creating a new one. M-62 recorded that "the same claim" was undefined.

This is blocking for P3 and **R-5's correctness depends on it**. Both error directions are damaging: over-merging hides genuine source disagreement; under-merging inflates corroboration, which propagates directly into `evidential_support` (S-2 input 3) and therefore every downstream confidence value.

## Alternatives Considered

**Option A — Strict textual equivalence.**
*Rejected:* precise and safe against over-merge, but will badly under-merge. Two sources stating the same fact in different words would never be recognised, making corroboration nearly uncountable — defeating R-5's purpose.

**Option B — Semantic equivalence by model judgement.**
*Rejected:* matches intent, but is non-deterministic and unauditable. Under N-4 the same pair might merge on one run and not another, making Fact identity unstable — and identity is permanent under I2.

**Option C — Structured decomposition with equivalence on structure (selected).**

**Option D — Conservative merge with `DUPLICATES` for all uncertain cases.**
*Adopted as the fallback within Option C*, not as the primary mechanism.

## Rationale

Structured claims make equivalence a **checkable property rather than an opinion**, satisfying Principle 2: an engine can state *why* two claims were judged equivalent by pointing at the four components.

**Condition 3 (qualifiers) does most of the work.** Context stripping is a named Fact-stage failure mode, and requiring qualifier match prevents the most damaging merge error — combining a narrow claim with a broad one, which silently widens what the evidence supports.

The conservative posture follows from irreversibility. Deliberate under-merging with a `DUPLICATES` link is **recoverable**: the relationship is recorded, and a later decision can merge. Over-merging is not recoverable at all.

## What It Binds

- **`T03.1.2`** structured claim decomposition.
- **`T03.1.4`** merge mechanism implements this test.
- **R-5** canonical claims become determinable.
- **F-I4** merging requires explicit equivalence justification — the four conditions are it.
- **S-2 input 3** corroboration depth depends on merge correctness.

## Consequences Accepted

- **Structured extraction constrains what Fact Extraction can express.** Claims not fitting subject-predicate-qualifier-value must be forced or rejected.
- **Deliberate under-merging leaves residual corroboration inflation**, visible via `DUPLICATES` links but not automatically corrected.
- **Subject and predicate identity still require judgement** — "sellers" versus "merchants" is a resolution the structure does not make automatic.
- Qualifier containment (condition 3) is subtle and will be applied inconsistently at the margins.

## Known Tensions

**With M-19 (fact definition, `T03.1.1`).** Extraction granularity must align with this structure; they are the same problem from two directions and must stay consistent.

**With R-5's version churn.** Conservative merging produces more Facts and fewer attachments, reducing churn but weakening measured corroboration.

## Revisit Conditions

Reconsider if measured under-merge rates prove high enough that corroboration is materially understated — evidenced by `DUPLICATES` link density. The remedy is refining subject/predicate resolution, not relaxing the conditions.
