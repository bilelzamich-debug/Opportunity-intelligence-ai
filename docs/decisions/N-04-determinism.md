# N-4 — Determinism: Reproducible Inputs, Non-Deterministic Outputs

| Field | Value |
|---|---|
| **ID** | N-4 |
| **Title** | Determinism: Reproducible Inputs, Non-Deterministic Outputs |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | OQ-01 |
| **Backlog task** | `T00.3.4` |
| **Depends on** | `T00.1.3` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Inputs are reproducible. Outputs are not guaranteed deterministic.**

Every object records enough state to reconstruct exactly what its producing engine was given:

| Captured | Attribute / mechanism |
|---|---|
| Input objects, version-specific | `derives_from` (R-1 / D-01a) |
| Engine configuration in force | `engine_configuration_ref` (N-7) |
| Model version and parameters | Within the configuration record |
| Producing engine and time | `produced_by_engine`, `produced_at` |

**Replay expectation.** Re-running an engine on captured inputs may produce a **different but explainable** result. Divergence is investigable, not prevented.

**Regression testing** asserts **properties**, not equality: structural validity, evidence linkage, confidence-ceiling conformance, boundary compliance. Output equality is not a valid test assertion anywhere in the platform.

## Context

v1 does not state whether identical inputs must produce identical outputs (OQ-01).

This determines what must be captured at write time — and capture cannot be retrofitted. Objects created before the decision would be permanently non-reproducible, so it must be settled before P1 builds the write path.

The platform is AI-native: eight of nine engines are model-driven, and non-determinism is a property of that choice, not a defect.

## Alternatives Considered

**Option A — Full output reproducibility.**
*Rejected:* not achievable with model-driven engines. Asserting it would create false assurance — a guarantee the platform cannot honour, discovered only when it fails. Achieving it would require constraining engines to deterministic methods, contradicting "AI-native".

**Option B — No reproducibility guarantee; rely on lineage and explanation alone.**
*Rejected:* cheapest, but makes divergence uninvestigable. If an engine produces a different result today, nothing establishes whether the inputs, the configuration, or the model changed.

**Option C — Reproducible inputs, non-deterministic outputs (selected).**

**Option D — Reproducibility for structural operations only.**
*Rejected:* leaves the model-driven engines — where divergence actually occurs — uncovered. Structural operations are already deterministic by construction.

## Rationale

Option C captures what is achievable and is honest about what is not.

The practical need is not "the same answer twice" — it is **the ability to investigate why the answer changed**. That requires knowing exactly what the engine was given, which is capturable, rather than constraining what it produces, which is not.

Rejecting Option A matters: a reproducibility guarantee the platform cannot honour is worse than a stated limitation, because it will be relied upon.

The regression-testing consequence follows directly. Equality assertions would fail spuriously and train implementers to ignore failures. Property assertions test what the architecture actually guarantees — and every guarantee in the IOM is a property (V1–V12, I1–I8), not an output value.

## Why Is This Capability Intentionally Outside the Platform?

### Deterministic reasoning — guaranteeing identical output for identical input

**Why outside the platform.** Determinism is not a capability the platform declines to build; it is one that conflicts with the platform's defining choice. AI-native reasoning is non-deterministic by nature, and the vision selects it deliberately. Guaranteeing determinism would require replacing model-driven engines with rule-based ones — a different platform.

**Structural evidence.** PKP v2 §1.2.1 states that non-determinism is "a first-class property of the system, not a defect", and that correctness "cannot be asserted by equality checking".

**Scope-creep pressure to expect.** "Pin the seed so tests pass." Seed-pinning produces reproducibility that holds only until the model changes, creating tests that assert an accident of configuration. The correct response is property-based assertions.

## What It Binds

- **Universal attributes:** `engine_configuration_ref` mandatory on every object (R-1, N-7).
- **Configuration store** (N-7, `T01.1.6`): immutable, versioned, resolvable at any historical point.
- **`T01.1.4`**: write path captures full input state.
- **All engine test strategies:** property-based, never equality-based.
- **Feedback Engine:** can compare prediction to outcome because inputs and configuration are recoverable (R-1 immutability + this decision).

## Consequences Accepted

- **The platform cannot assert "the same analysis yields the same answer."** Stated openly rather than implied.
- **Divergence investigation is manual.** Captured inputs make it possible, not automatic.
- **Configuration capture on every object** adds storage and a mandatory dependency on N-7.
- **Regression testing is weaker** than equality testing. Property assertions catch contract violations, not subtle quality drift — which is why N-3's proxy measures exist.

## Known Tensions

**With M-60 (open).** Non-deterministic confidence assertion compounds the calibration problem: the same engine may assert different confidence for the same input on different runs.

**With N-3.** Proxy measures over non-deterministic outputs are statistical, requiring volume before a trend is meaningful.

**With M-63 (closing at N-7).** This decision makes `engine_configuration_ref` load-bearing; without a configuration store it is unresolvable.

## Revisit Conditions

Reconsider only if the platform's engines become substantially deterministic — for example, if model-driven reasoning is replaced by rule-based methods in some stage — in which case that stage may assert stronger guarantees without changing this decision for the others.

Test-suite convenience is not grounds.
