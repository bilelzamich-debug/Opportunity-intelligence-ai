# Prompts

Every governing prompt used in this project, preserved so the working method
can be reproduced exactly.

These are not documentation *about* the method — they **are** the method. An
agent continuing this project should use them verbatim.

---

## Files

| File | Purpose |
|---|---|
| [`00-STANDING-INSTRUCTIONS.md`](00-STANDING-INSTRUCTIONS.md) | The permanent operating rules that applied to every task |
| [`01-TASK-EXECUTION.md`](01-TASK-EXECUTION.md) | Prompt for executing a single backlog task |
| [`02-PHASE-EXIT-GATE.md`](02-PHASE-EXIT-GATE.md) | Prompt for a phase closure gate |
| [`03-ARCHITECTURE-INVESTIGATION.md`](03-ARCHITECTURE-INVESTIGATION.md) | Prompt for investigating a suspected blocker |
| [`04-DECISION-DRAFTING.md`](04-DECISION-DRAFTING.md) | Prompt for producing a ratification-ready decision record |
| [`05-ARB-REVIEW.md`](05-ARB-REVIEW.md) | Prompt for Architecture Review Board system-level review |
| [`06-RATIFICATION.md`](06-RATIFICATION.md) | Prompt for governance review and ratification execution |

---

## The Method These Encode

Six steps, each existing because skipping it caused a real defect:

1. **Extract, never recall.** Write the specification from ratified sources
   before writing code.
2. **Probe adversarially** before writing tests.
3. **Write property-based tests.** Never equality on outputs (F11).
4. **Mutate** every new rule; restore byte-identically.
5. **Verify mechanically** — and treat verifier failures as equally likely to
   be verifier bugs.
6. **Report honestly**, naming the weakest point in your own work.

---

## Why Prompts Are Version-Controlled

The prompts changed as the project learned. Three changes were consequential:

| Change | Cause |
|---|---|
| "Validate by extraction, not recollection" added | `T00.1.2` found **two marker collisions** a prior summary had missed |
| "Probe adversarially *before* writing tests" added | Multiple defects found by probes that tests would not have caught |
| "If host noise appears in benchmarks, **prove** it" added | Repeated false regression reports on a shared 2-core host |

An agent using an earlier prompt would reproduce the earlier failure modes.
