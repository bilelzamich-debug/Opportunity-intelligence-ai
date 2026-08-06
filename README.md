# Governance

The rules that make the architecture hold. **These outrank the code.**

---

## Files

| File | What it is |
|---|---|
| [`CONSTITUTION.md`](CONSTITUTION.md) | Eleven articles. Highest authority in the project. Amended only by a recorded decision naming the article changed |
| [`AGENT-PLAYBOOK.md`](AGENT-PLAYBOOK.md) | How work is executed: role, twelve forbidden actions, working method, gates, approval protocol |
| [`DECISION-TEMPLATE.md`](DECISION-TEMPLATE.md) | The mandatory six-field structure every decision record must satisfy |

---

## The Precedence Order (Constitution Article XI)

Where documents conflict, this order governs:

1. **The Constitution**
2. **Decision records** (the architecture decision register)
3. **Ratification annotations**
4. **Intelligence Object Model**
5. **PKP v2 Master Reference**
6. **Implementation Backlog**

> *"A subordinate document that contradicts this Constitution is in error, and
> the contradiction is resolved in the Constitution's favour without amendment
> to it."*

This order is not decorative. It has already resolved two live conflicts:

- **S-2 vs IOM §3.1** — the IOM says `evidential_support` "reflects source
  reliability"; S-2 says trust is not an input. **S-2 governs.**
- **N-2 vs backlog `T02.2.4` AC2** — the backlog requires a human gate N-2
  forecloses. **N-2 governs**, so the acceptance criterion is unsatisfiable as
  written (this is D-1).

---

## The Eleven Articles

| # | Article | Core statement |
|---|---|---|
| I–II | Purpose & Explainability | Every decision carries its *why* |
| III | Evidence First | Conclusions require evidence |
| **IV** | **Ground Truth** | **No platform-generated artifact may become Evidence** |
| V | Modularity | Engines exchange only Intelligence Objects |
| VI | Advisory Scope | The platform holds no budget, no operational authority, no accountability for consequences |
| VII | Human-in-the-Loop | Three reserved decisions (N-2's G1/G2/G3) |
| VIII–IX | Traceability | Complete path from external observation to any object |
| **X** | **Honest Uncertainty** | **Known gaps are recorded with the same standing as favourable findings** |
| XI | Precedence | The order above |

Article X is why this repository states its limitations prominently rather than
burying them — and why N-22's out-of-frame register exists at all.

---

## The Twelve Forbidden Actions

| # | Forbidden | # | Forbidden |
|---|---|---|---|
| **F1** | Redesigning the architecture | **F7** | Starting a task with incomplete dependencies |
| **F2** | Making an architectural decision yourself | **F8** | Adding an engine, object, stage, component or principle |
| **F3** | Closing a marker by implementation choice | **F9** | Letting configuration participate in reasoning |
| **F4** | Skipping acceptance criteria | **F10** | Allowing platform output to become Evidence |
| **F5** | Rewriting frozen documents | **F11** | Asserting equality in tests |
| **F6** | Self-approving an escalation | **F12** | Silently proceeding past a contradiction |

---

## Decision Record Requirements

Six mandatory fields. A record missing any is incomplete and **must not be
marked `RATIFIED`**:

1. Context
2. **Alternatives Considered** ← most often skipped, matters most
3. Decision
4. Rationale
5. Consequences Accepted
6. Revisit Conditions

> *"A decision without rejected alternatives is a preference."*
> *"Field 6 protects the architecture freeze. With explicit revisit conditions,
> 'this is inconvenient' is visibly not grounds for reopening."*

**Lifecycle:** `DRAFT → RATIFIED → SUPERSEDED` (or `DRAFT → REJECTED`).
Records are **immutable once ratified** — change happens by a superseding
record, never by editing in place.

---

## The Marker Rule

> **A marker is closed only by a record in the decision register. Closing a
> marker by implementation choice is prohibited — an architecture decision made
> in code is an architecture decision that cannot be found.**

This single rule is why nine Phase-2 tasks are legitimately blocked rather than
quietly implemented around.

---

## Escalation

Tasks flagged **⚠** or **🔺** require explicit human sign-off (**F6**). Always.

The recorded form, from precedent (N-7, R-7, R-8, and now N-20/N-21):

> 🔺 **ESCALATION — RATIFIED 2026-08-04.** Approved by the Project Owner.

Escalations are approved **individually, by name**. A feature approval does not
approve an escalation inside it.
