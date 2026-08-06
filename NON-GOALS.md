# Platform Non-Goals

**Status:** Authoritative. Closes M-03.
**Established by:** N-1 (`T00.3.1`), consolidated across F00.3
**Purpose:** Prevent scope creep by recording what the platform deliberately does not do, and why.

---

## 1. How To Use This Document

v1 contained no non-goals statement. PKP v2 recorded this as M-03 and noted that enterprise reference documentation requires stated boundaries to prevent scope drift.

Every exclusion below is **deliberate**, recorded with its reason and the pressure that will eventually be applied to reverse it. When a proposal arrives to add one of these capabilities:

1. It is a **scope change**, not a feature request.
2. It requires **superseding** the decision record that excluded it.
3. The anticipated pressure is already documented — recognising it is not a counter-argument.

**A capability absent from this list is not thereby in scope.** v1 defines the platform's scope positively; this document records only the exclusions that were actively considered.

## 2. Exclusion Register

| # | Excluded capability | Excluded by | Type |
|---|---|---|---|
| X1 | Execution — acting on a recommendation | N-1 | Permanent |
| X2 | Decision authority — choosing which opportunity to pursue | N-1, N-2 | Permanent |
| X3 | Implementation design — how a solution is built | N-1 | Permanent |
| X4 | Market operation — running the opportunity | N-1 | Permanent |
| X5 | Outcome determination — adjudicating success | N-1 | Permanent |
| X6 | Automated decision authority at gates G1–G3 | N-2 | Permanent |
| X7 | Business value measurement — ROI per opportunity | N-3 | Permanent |
| X8 | Deterministic reasoning — identical output for identical input | N-4 | Structural |
| X9 | Access control and multi-tenancy | N-5 | **Deferred, with named trigger** |

**Type definitions.**
- **Permanent** — architecturally inappropriate. Reversal changes what the platform *is*.
- **Structural** — conflicts with a defining platform property. Reversal requires changing that property.
- **Deferred** — appropriate but premature. Has a named trigger and planned work.

## 3. Exclusions in Detail

### X1 — Execution
**Why.** Requires budget authority, operational control, and accountability for consequences. The platform has none and v1 assigns none. An advisory system that executes acquires liability for outcomes it cannot control.
**Evidence.** No Execution Engine (v1 §4), no execution phase (v1 §9), but an Execution *Record* object — the platform records what happened, it does not make it happen.
**Pressure to expect.** *"The platform already knows what to do — why not let it do it?"*

### X2 — Decision authority
**Why.** Prioritisation depends on strategy, capacity, appetite and timing that exist outside the evidence base. A score computed from market evidence cannot encode organisational context; presenting it as a decision overstates what the evidence supports.
**Evidence.** Confidence inflation at the Opportunity stage is PKP v2's most consequential identified failure.
**Pressure to expect.** *"Just auto-approve above threshold."* Threshold automation is permitted under N-2; what is retained is human **override**.

### X3 — Implementation design
**Why.** Solution granularity stops at concrete offering description (M-29). Detailed design is assigned to no v1 engine; inventing that scope extends the platform into product development.
**Pressure to expect.** *"The solution is too vague to act on."* The correct response is validating assumptions, not deepening design.

### X4 — Market operation
**Why.** Follows from X1. A market participant cannot be a neutral observer of the same market — its own actions enter the evidence base, which AD-05 exists to prevent.
**Pressure to expect.** *"We could test the opportunity ourselves."* That is execution; its outcomes must enter as externally-acquired Evidence with full provenance.

### X5 — Outcome determination
**Why.** Success depends on objectives held by the executing party. A platform that both predicted and judged the outcome would be marking its own work — the most direct route to self-reinforcement.
**Evidence.** `outcome_valence` and `attribution_assessment` are *recorded*; `outcome_verification` is required (M-47) precisely because the platform is not the arbiter.
**Pressure to expect.** *"The platform should decide if it was right."* It should **measure** whether it was right against reported outcomes — a different thing.

### X6 — Automated authority at gates
**Why.** G1, G2 and G3 require context the evidence base does not contain: organisational capacity (G1), willingness to act on given confidence (G2), tolerance for behavioural change in a live system (G3).
**Evidence.** PKP v2 leaves M-28 and M-31 unowned because AD-04's strict separation creates responsibility voids at decision points between engines.
**Pressure to expect.** *"The threshold works — remove the human."* Removing override converts a gate into a rule and transfers accountability to the platform, which N-1 places outside it.

### X7 — Business value measurement
**Why.** N-3's measures assess whether the *platform* was accurate, not whether the *opportunity* was worthwhile. Computing return requires cost and revenue data outside the evidence base; asserting it would breach Principle 1.
**Pressure to expect.** *"Show ROI per opportunity."* The platform can report predicted-versus-realised outcome as reported to it.

### X8 — Deterministic reasoning
**Why.** Not declined but *conflicting*: AI-native reasoning is non-deterministic by nature, and the vision selects it deliberately. Guaranteeing determinism would require replacing model-driven engines with rule-based ones.
**Evidence.** PKP v2 §1.2.1: non-determinism is "a first-class property of the system, not a defect".
**Pressure to expect.** *"Pin the seed so tests pass."* Seed-pinning asserts an accident of configuration. Use property-based assertions.

### X9 — Access control and multi-tenancy *(deferred)*
**Why deferred, not excluded.** Architecturally appropriate but premature. Building now would encode guesses about organisational structure that N-1 does not specify, and partitioning would forfeit cross-domain pattern recognition (OQ-14) for a requirement that may never arrive.
**Named trigger — any one of:**
1. A second tenant or organisational boundary is introduced
2. Evidence licensing requires restricting visibility of derived conclusions (M-18)
3. Platform output is exposed beyond the commissioning organisation
**On trigger.** `T09.2.2` is initiated; N-5 is superseded.
**Pressure to expect, in both directions.** *"Add permissions now, just in case"* — premature. *"We'll deal with it if it happens"* — forecloses the option. The reserved discriminator is the middle path.

## 4. Scope Boundary Summary

```
        EXTERNAL REALITY
              │ acquisition
              ▼
   ┌──────────────────────────────┐
   │   PLATFORM (advisory)        │
   │                              │
   │   Evidence → Facts →         │
   │   Problems → Patterns →      │
   │   Opportunities →            │
   │   Solutions → Validation     │
   │                              │
   └──────────────┬───────────────┘
                  │ structured handoff  ← OUTPUT EXITS HERE (Stage 7)
                  ▼
        DECISION-MAKERS  ── X2 decide ── X1 execute ── X5 judge outcome
                  │
                  │ mandatory outcome reporting
                  ▼
        Execution Record (Stage 8) → Feedback (Stage 9)
                  │
                  └──▶ Learning Signal · Knowledge Update
                       Research Trigger · Model Calibration   (AD-05)
```

The platform's boundary is **Stage 7**. Stages 8 and 9 process what returns from outside it.
