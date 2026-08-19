# N-24 — Acquisition-Rights Authority: Designated Role, Scope Limited to N-21 §5.5

| Field | Value |
|---|---|
| **ID** | N-24 |
| **Title** | Acquisition-Rights Authority: Designated Role, Scope Limited to N-21 §5.5 |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-19 |
| **Date decided** | 2026-08-19 |
| **Source** | N-21 §5.1, §5.3, §5.4, §5.5, §10 item 2; N-01; Constitution Art. VI (K14); N-08 (K6 mechanism/policy split) |
| **Closes** | N-21 §10 follow-up item 2 — "Name the human authority required by §5.1" |
| **Backlog task** | `T02.1.2` (operational precondition) |
| **Depends on** | **N-21** (supplies the vocabulary and enforcement point this authority operates) |
| **Supersedes** | — |
| **Superseded by** | — |

> **RATIFIED 2026-08-19.** Approved by the Project Owner, scope exactly as
> audited: assessments in the N-21 §5.5 vocabulary only (`PERMITTED` /
> `PROHIBITED` / `UNASSESSED`; retention `RETAIN_FULL` /
> `RETAIN_REFERENCE_ONLY` / `RETAIN_NONE` / `UNASSESSED`) — no M-18b
> conduct powers, no trust scoring, no taxonomy assignment, no research
> scoping, and no decision on the N-21 §12 compliance discrepancy.
>
> ### Ratification does not operationalise acquisition
>
> Per the Status Vocabulary ("`RATIFIED` — Agreed and binding — **May be
> built against: Yes**") and N-21 §6 item 2, ratification creates the
> accountability structure; it admits no source by itself:
>
> - sources remain `UNASSESSED` until the role supplies assessments,
> - acquisition remains fail-closed (N-21 §5.4 — silence is not
>   permission), and
> - `T02.1.2` is **implementable, not operational** — enforcement code may
>   reference the role; no acquisition proceeds without assessments.

---

## Decision

1. **The acquisition-rights authority required by N-21 §5.1 is the ROLE:
   *Designated Source Rights/Compliance Authority*.** A designated
   organisational role, not a named individual. The role is held outside the
   platform, consistent with N-01/Article VI: the platform "holds no budget,
   no operational authority, and no accountability for consequences" (K14).
   Naming a role satisfies N-21 §5.1's "named human authority outside the
   platform": the authority is human-side and organisational; N-21 §13 itself
   records that "naming one is an organisational decision, not an
   architectural one."

2. **Scope is NARROW and closed.** The role's authority is limited to
   issuing acquisition-rights and retention-rights assessments in **exactly
   the closed vocabulary of N-21 §5.5** — Acquisition: `PERMITTED` /
   `PROHIBITED` / `UNASSESSED`; Retention: `RETAIN_FULL` /
   `RETAIN_REFERENCE_ONLY` / `RETAIN_NONE` / `UNASSESSED` — each assessment
   additionally recording the authority, the date assessed, and the rights
   basis (N-21 §5.3, §5.5). **No broader compliance powers are granted.**

3. **Explicit exclusions.** The role does **not**:
   - decide acquisition *conduct* — robots, rate limits (reserved to **M-18b**, open);
   - score or weight source trust (excluded by **S-2**'s closed input list);
   - assign source types (owned by the Research Engine per **N-20 §5.1**);
   - scope or commission research (owned by directive originators per **N-23**);
   - adjudicate coverage gaps (**N-22** reports; the authority does not gate);
   - create, amend or extend the rights vocabulary (extension requires a
     superseding record per N-21 §5.5).

4. **The word "Compliance" in the role title is a designation of
   accountability for rights determinations, NOT a scope expansion.**
   Whether "compliance" beyond the §13 enumeration ("Legal, licensing,
   rate-limit, terms-of-use") belongs to M-18 remains the flagged, undecided
   v2 §13/§14 discrepancy recorded in N-21 §12. This record does not decide
   it and must not be read as deciding it.

5. **Process.** Assessments reach the platform as explicit recorded inputs
   attributed to the role, per the recording requirements of N-21 §5.5,
   with the rights basis as defined in N-21 §5.3.
   The platform **applies** them mechanically at the enforcement point
   (N-21 §5.2, before acquisition) and **never infers rights** (N-21 §5.1).
   An assessment lacking the authority, date or basis is `UNASSESSED`, and
   `UNASSESSED` refuses.

6. **Accountability.** Legal accountability for determinations rests with
   the role holder, outside the platform (K14, Art. VI). N-21 §13's warning
   stands: architecture specifies *where* the legal question is asked and
   *how* the answer is recorded; it cannot determine what is lawful.

## Context

N-21 §5.1 placed acquisition-rights policy ownership with "a named human
authority outside the platform" and deliberately named no one. N-21 §10
item 2 records the consequence: "acquisition cannot begin until it exists."
N-21 §5.4 makes `UNASSESSED` fail closed, so every source is refused until
assessments arrive. On 2026-08-19 the Project Owner directed that the
authority be expressed as an explicit ROLE — "Designated Source
Rights/Compliance Authority" — with role definition and authority scope to be
ratified before implementation, and no person's name or identity invented.
This draft implements that direction with the narrowest scope consistent
with N-21.

## Alternatives Considered

1. **Name an individual.** Rejected by the Project Owner's direction
   (2026-08-19): no person's name or identity is to be invented; a role
   survives personnel changes and records accountability structurally.
2. **Wider compliance mandate matching the v2 §14 reading.** Rejected as
   premature: N-21 §12 flags the §13/§14 "compliance" discrepancy as
   *flagged, not decided*. Granting broad powers now would silently decide an
   open question.
3. **No record; treat N-21 as self-executing.** Impossible: N-21 §5.1
   explicitly requires the external authority, and fail-closed refusal is
   the intended behaviour until one exists.

## Rationale

The narrowest closure of N-21 §10 item 2 that (a) uses only vocabulary and
mechanisms N-21 already ratified, (b) leaves every open marker (M-18b, the
§12 compliance discrepancy, S-2 trust scoring) exactly as open as before,
and (c) keeps the mechanism/policy split (N-08 K6) intact: the platform
applies; the role decides.

## What It Binds

| Target | Effect |
|---|---|
| **N-21 §5.1** | The "named human authority" is the designated role. N-21 is otherwise unchanged and not superseded. |
| **`T02.1.2`** | Becomes implementable — enforcement code may reference the role and record its assessments. Acquisition itself remains non-operational until the role supplies assessments (N-21 §6 item 2). |
| **N-21 §10 item 2** | Closed. |
| **Store / acceptance rules** | No change — N-21 §5.2 already places enforcement before acquisition, outside the Store's structural scope. |

Nothing else. No engine, object, stage, gate or relationship is added (F8
respected). No code change is authorised by this record beyond what
`T02.1.2`'s own acceptance criteria specify.

## Consequences Accepted

- Acquisition remains impossible until the role is not only ratified but
  **staffed and supplying assessments** — ratification alone does not admit
  a single source.
- A role can be held by multiple individuals over time; assessments are
  attributed to the role (N-21 §5.5), and changes of holder do not
  invalidate past assessments — they are immutable once recorded by the
  store's own guarantees (K11/I4, the immutability N-21 §5.2 itself relies
  on), not by any new rule created here.
- If the role issues no assessments, the platform stays fail-closed
  indefinitely. This is N-21's intended behaviour, not a defect.

## Known Tensions

- **The §12 compliance discrepancy remains open.** The role title contains
  "Compliance" for continuity with the Project Owner's designation; the
  decision text binds the role to §5.5 vocabulary only. A future record may
  widen or clarify the title's scope; until then the text governs, not the
  title.
- **Single point of organisational dependency.** All acquisition waits on
  one role. Concentration is deliberate: N-21 assigns legal accountability
  outside the platform, and diluting it would obscure whose determination
  `access_conditions` records.

## Revisit Conditions

- A jurisdiction requires a rights value the N-21 §5.5 vocabulary cannot
  express (N-21 §11 trigger — extension requires a superseding record).
- The §12 compliance discrepancy is decided and scope must move.
- The role is reorganised, renamed or split.

---

## Honest Limitations

- **This record grants no power beyond N-21 §5.5.** Even ratified, it
  names an accountability structure; it changes no behaviour by itself.
- **The role is not staffed by this record.** Ratification creates the
  accountability structure; operational acquisition additionally requires
  the role to supply assessments.
- **Architectural record, not legal advice.** Nothing here determines what
  is lawful (N-21 §13).
