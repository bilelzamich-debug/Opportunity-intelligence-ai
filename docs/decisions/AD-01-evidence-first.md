# AD-01 — Evidence-First

| Field | Value |
|---|---|
| **ID** | AD-01 |
| **Title** | Evidence-First |
| **Status** | `RECONSTRUCTED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | Unknown — predates PKP v1 |
| **Source** | PKP v1 §8 (title only); PKP v2 §8.3 (substance) |
| **Supersedes** | — |
| **Superseded by** | — |

> **Provenance warning.** v1 recorded this decision as the bare title "Evidence-first". The **Decision**, **What It Binds**, and **Consequences** sections below are *established* — traceable to PKP v2 §8.3, which is frozen and authoritative. The **Context** and **Alternatives Considered** sections are *reconstructed* from the architecture's internal logic. They are not a record of what was historically debated and must not be cited as such.

---

## Decision (established)

All conclusions must derive from and reference traceable evidence.

No object may exist in the platform without a resolvable path to at least one Evidence object. Evidence is the only object type with no upstream lineage; every other object terminates its lineage there.

## Context (reconstructed)

The platform is AI-native: reasoning, extraction and judgement are performed by model-driven engines as the primary mechanism, not as an enrichment layer. This creates a specific hazard — **fluent output is cheap**. A model-driven system will readily produce well-formed, plausible, confident market analysis that is entirely unsupported.

The platform's output drives resource allocation decisions. An unsupported recommendation that *looks* identical to a supported one is worse than no recommendation, because it consumes the credibility that makes the supported ones actionable.

Evidence linkage is the mechanism that distinguishes a supported claim from a merely fluent one. The decision establishes that this distinction is structural — enforced by the object model and the write path — rather than a matter of engine discipline.

## Alternatives Considered (reconstructed)

**Option A — Evidence-first (selected).** Every conclusion references traceable evidence; enforced structurally at write time.

**Option B — Model knowledge permitted, evidence optional.** Engines may draw on parametric model knowledge, attaching evidence where convenient.
*Rejected:* makes supported and unsupported conclusions structurally indistinguishable. The platform could not answer "why do you believe this?" for its own output, and Principle 2 (Explainable decisions) would be unenforceable. Every downstream quality mechanism — validation, scoring, feedback — assumes a grounded claim to operate on.

**Option C — Evidence attached after the fact.** Engines reason freely, then retrieve supporting evidence for conclusions reached.
*Rejected:* this is rationalisation, not evidence-based reasoning. Post-hoc retrieval finds support for whatever was already concluded, so the evidence layer would confirm rather than constrain. The failure is invisible: the resulting objects satisfy every structural lineage check.

**Option D — Evidence required for some object types only** (for example, Facts and Problems but not Opportunities).
*Rejected:* the pipeline is a derivation chain. An unevidenced Opportunity breaks the chain at exactly the point where output leaves the platform and drives commitment. Partial application yields the weakest guarantee at the highest-stakes stage.

## Rationale (reconstructed)

Option A is the only alternative under which the platform's central claim — that its conclusions are traceable to observed reality — is *structurally* true rather than aspirational. The others make it a matter of engine behaviour, which cannot be verified and will degrade silently.

The cost is accepted deliberately: the platform is slower, more expensive, and blind outside its evidence base. These are visible, bounded costs. The cost of the alternatives is invisible and unbounded.

## What It Binds (established)

- Every engine — no engine may introduce parametric model knowledge as a conclusion.
- Every object type — non-Evidence objects must carry non-empty upstream lineage.
- The Knowledge Store's write-time validation (rules V2, V3, V4).
- The Knowledge Graph's lineage structure.

Formalises Principle 1. Realised structurally by Principle 3. Enforced by universal requirement U6 (evidence reachability).

## Consequences Accepted (established)

- **Higher cost per conclusion.** Evidence must be acquired before reasoning can proceed.
- **Reduced speed.** The platform cannot answer from model knowledge.
- **Coverage limited by research reach.** The platform is blind to what it has not collected — making sampling bias its most dangerous systemic failure.
- **Storage growth.** Evidence must be retained to preserve traceability.

## Known Tensions (established)

**CONTRADICTION-04.** The pipeline's closing arc `Feedback -> Evidence` permits platform-internal content to enter as Evidence, weakening the grounding guarantee this decision exists to provide. PKP v2 §8.7 identifies this as the single decision-level conflict in the architecture: the loop implementing AD-03 undermines AD-01.

**Resolution in progress.** The Intelligence Object Model proposes behavioural loop closure — feedback informs engine behaviour and may trigger new research, but never becomes Evidence (constraints E-I2, FR-I2). This preserves AD-01 intact. Pending ratification as **R-8** (`T00.2.8`).

## Revisit Conditions

This decision should be reconsidered only if:

- Enforcement proves impossible for a class of legitimate conclusion, **or**
- Acquisition cost renders the platform unviable at required coverage, **or**
- R-8 is rejected, in which case AD-01 and AD-03 must be reconciled explicitly rather than left in conflict.

Cost or latency pressure alone is **not** grounds for revisiting. Those consequences were accepted knowingly.
