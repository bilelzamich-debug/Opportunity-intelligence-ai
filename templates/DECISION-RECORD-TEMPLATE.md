# Decision Record Template

**Status:** Authoritative. Every decision record in this register must conform to this template.
**Established by:** `T00.1.3`
**Applies to:** All `AD-nn`, `R-n`, `N-nn` and `S-n` records.

---

## 1. Required Fields

Six fields are mandatory. A record missing any of them is incomplete and **must not be marked `RATIFIED`**.

| # | Field | Purpose | Omission consequence |
|---|---|---|---|
| 1 | **Context** | The situation that made a decision necessary | Future readers cannot tell whether the original conditions still hold |
| 2 | **Alternatives Considered** | Options examined and why each was rejected | A future contributor cannot distinguish a considered constraint from an unexamined default — the exact failure of MISSING-50 |
| 3 | **Decision** | What was decided, stated unambiguously | The record is not a decision |
| 4 | **Rationale** | Why this option over the others | The decision cannot be re-evaluated when conditions change |
| 5 | **Consequences Accepted** | Costs and limitations knowingly taken on | Accepted costs get re-litigated as if they were oversights |
| 6 | **Revisit Conditions** | What would justify reopening this | Either the decision is treated as immutable, or it is reopened on any pressure |

**Field 2 is the field most often skipped and the one that matters most.** MISSING-50 exists precisely because v1 recorded decisions without alternatives. A decision without rejected alternatives is a preference.

**Field 6 protects the architecture freeze.** With explicit revisit conditions, "this is inconvenient" is visibly not grounds for reopening, while a genuine trigger is recognisable.

## 2. Structure

Every record has a header block, the six required fields, and — where applicable — the optional sections in §3.

```
# <ID> — <Title>

| Field | Value |
|---|---|
| **ID** | <AD-nn | R-n | N-nn | S-n> |
| **Title** | <short name> |
| **Status** | <DRAFT | RATIFIED | RECONSTRUCTED | SUPERSEDED | REJECTED> |
| **Owner** | <accountable party> |
| **Date recorded** | <YYYY-MM-DD> |
| **Date decided** | <YYYY-MM-DD, or "Unknown — predates PKP v1"> |
| **Source** | <originating document and section> |
| **Closes** | <canonical marker IDs, or —> |
| **Backlog task** | <task ID, or —> |
| **Supersedes** | <record ID, or —> |
| **Superseded by** | <record ID, or —> |

## Decision
## Context
## Alternatives Considered
## Rationale
## What It Binds
## Consequences Accepted
## Known Tensions
## Revisit Conditions
```

Order within the file may place **Decision** first for readability — as the `AD-nn` records do — provided all six required fields are present.

## 3. Optional Sections

| Section | Include when |
|---|---|
| **What It Binds** | The decision constrains named engines, objects, components or documents |
| **Known Tensions** | Unresolved conflicts with other decisions or open markers exist |
| **Provenance warning** | Any part of the record is reconstructed rather than established |
| **Implementability warning** | The decision is agreed but cannot currently be executed |

## 4. Rules

1. **Canonical identifiers only.** All marker references use canonical IDs per `marker-crosswalk.md`.
2. **Closes is explicit.** If a decision closes a marker, name it. Markers are closed only by recorded decision, never by implementation choice.
3. **Established vs reconstructed must be distinguished.** Where rationale is inferred rather than recorded, label it `(reconstructed)` and carry a provenance warning. Never present inference as history.
4. **Alternatives must be genuine.** A rejected option that was never viable is padding. Record the options that were actually plausible, including any that were attractive and declined.
5. **Records are immutable once `RATIFIED`.** Change is made by a new record that supersedes, never by editing in place.
6. **Escalations are marked.** Decisions extending v1's frozen architecture carry 🔺 and require explicit sign-off.

## 5. Status Transitions

```
DRAFT ──ratify──▶ RATIFIED ──supersede──▶ SUPERSEDED
  │                                            ▲
  └──decline──▶ REJECTED                       │
                                               │
RECONSTRUCTED ─────────────supersede───────────┘
```

`RECONSTRUCTED` is used only for decisions taken before the register existed, where substance is established but provenance is not. It is binding for building purposes, with the caution noted in the register.

## 6. Worked Example

`AD-02 — Intelligence Contracts` demonstrates the template in full. Field-by-field:

| Field | Where it appears in AD-02 | What makes it adequate |
|---|---|---|
| **Context** | "Nine engines, eight model-driven… replaced frequently" | States the forcing condition — replacement churn — not merely a restatement of the decision |
| **Alternatives Considered** | Four options: sole contract, direct invocation, shared state, permitted side channels | Each has a stated rejection reason. Option D is recorded as "genuinely attractive" and declined — an honest record of a close call |
| **Decision** | "Engines communicate exclusively through defined Intelligence Objects" | Unambiguous and testable |
| **Rationale** | "Makes the interface surface finite, enumerable and inspectable" | Explains the selection over the alternatives, not just the merit of the choice |
| **Consequences Accepted** | Object definitions become highest-stakes; schema changes are breaking; engines cannot exchange unmodelled information | Costs stated plainly, including the one that later caused difficulty (M-23) |
| **Revisit Conditions** | Only if a need cannot be expressed as an object attribute, or throughput proves prohibitive; "inconvenience is not grounds" | Distinguishes genuine triggers from pressure |

**Why AD-02 rather than a synthetic example.** A real record demonstrates the standard, and AD-02 in particular shows the hardest part done properly: Option D was attractive, would have solved a real problem (source diversity reaching Pattern Intelligence), and was rejected anyway on the grounds that a permitted side channel becomes an undocumented second interface. That is the kind of reasoning field 2 exists to capture.

## 7. Common Failures

| Failure | Detection | Why it matters |
|---|---|---|
| Alternatives omitted or trivial | Fewer than two genuine options | Reproduces MISSING-50 |
| Rationale restates the decision | Rationale contains no comparison | Cannot be re-evaluated later |
| Consequences list only benefits | No costs recorded | Costs resurface as objections |
| Revisit conditions absent or unbounded | Field missing, or "revisit as needed" | Freeze becomes unenforceable in either direction |
| Inferred rationale presented as history | No provenance warning on a reconstructed record | Fabricates a record of deliberation that did not occur |
| Marker closed without a record | Marker cited as resolved with no decision ID | Architecture decision lives in code, not in the register |
