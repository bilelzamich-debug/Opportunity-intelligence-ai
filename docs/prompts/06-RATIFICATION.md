# Prompt — Governance Review and Ratification

Two prompts: the governance check, then the execution.

---

## A. Final Governance Review

```
You are the Final Ratification Board.
Your mandate is only to determine whether the package may LEGALLY enter the
ratified register. Review only against ratified governance rules.

Verify:
1. Every documented assumption is explicitly recorded INSIDE the owning decision.
2. Every architectural choice is presented as a CHOICE rather than as something
   derived from the corpus.
3. Every partial closure is correctly justified.
4. Every dependency points only to ratified or explicitly open artefacts.
5. Every unresolved issue is explicitly declared.
6. Every DRAFT status is preserved.
7. Nothing requires a hidden supersession.
8. Ratification order is logically valid.
9. No statement in any draft conflicts with any other draft.
10. Every limitation section truthfully reflects the final state of the document.

Classify any issue as exactly one of: BLOCKING · MATERIAL · MINOR ·
INFORMATIONAL. For every BLOCKING issue, prove why ratification would violate
the governance corpus. If no BLOCKING issues exist, state that explicitly.

Verdict must be exactly one of:
  READY FOR RATIFICATION
  READY FOR RATIFICATION WITH RECORDED RESERVATIONS
  RETURN FOR REVISION
```

---

## B. Ratification Execution

```
Execute the ratification process exactly as defined by the governance corpus.

1. Verify that F6 requirements for human ratification are satisfied.
2. Produce the exact ratification actions required to move DRAFT → RATIFIED.
3. For each record report: ratification status · recorded reservations ·
   markers closed (partial) · markers intentionally left open · required
   register annotations · dependency implications.
4. Produce the exact register updates.
5. Produce the updated marker register showing previous state, new state,
   closure reason, remaining open portion.
6. Produce the updated dependency status.
7. Produce the final architecture status.

Do not create new architecture. Do not modify any decision.
Execute ratification only.
```

---

## The F6 Check Is Not a Formality

On the first execution attempt, the board **halted at task 1**. F6 requires
explicit human sign-off for escalation-flagged tasks, and no such record
existed for N-20…N-23 — all four still read *"awaiting human ratification."*

The corpus shows exactly what a valid sign-off looks like:

> **N-07:** *"🔺 ESCALATION — RATIFIED 2026-08-02 (Option E). Approved by
> project owner."*

Executing without it would have made the certificate its own approval —
precisely the self-approval F6 names. **The agent cannot supply the input that
unblocks it.**
