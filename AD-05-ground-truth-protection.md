# AD-05 — Ground Truth Protection Principle

| Field | Value |
|---|---|
| **ID** | AD-05 |
| **Title** | Ground Truth Protection Principle |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Directed by project owner following Architecture Decision Review 2 |
| **Closes** | C-04 (jointly with R-8) |
| **Backlog task** | Directed addition alongside `T00.2.8` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**No platform-generated artifact may become Evidence directly.**

Evidence must always originate from external reality.

Feedback may only become one of four permitted forms:

| # | Permitted form | What it is | Where it lives |
|---|---|---|---|
| 1 | **Learning Signal** | An observation that platform behaviour diverged from outcome | Feedback Record (`lesson_statement`, `evidence_of_pattern`) |
| 2 | **Knowledge Update** | A change to stored platform knowledge or its status | Object status transitions and supersession |
| 3 | **Research Trigger** | A directive causing acquisition of new external Evidence | Research directive (`T02.2.4`, `T08.3.4`) |
| 4 | **Model Calibration** | An adjustment to engine configuration or scoring | Configuration store (N-7), referenced by `engine_configuration_ref` |

These four are exhaustive. Any feedback output that cannot be expressed as one of them has no permitted destination and must not be produced.

## Context

The platform is a closed learning loop (AD-03) built on an evidence-first foundation (AD-01). PKP v2 §8.7 identifies the tension between these two as the architecture's single decision-level conflict, expressed as C-04.

R-8 resolves the *mechanism*: the loop closes behaviourally rather than through lineage. But R-8 is a statement about one arrow in one pipeline diagram. It does not, by itself, establish a general prohibition — and the risk it addresses is general.

The underlying hazard is that a learning system with any path from its own output back into its grounding layer can corroborate itself with itself. It becomes progressively more confident while becoming less grounded, and the failure is invisible from inside: every structural check passes, evidential support rises, and confidence bands improve. PKP v2 §4.8 records this as loop instability; the IOM records it as the reason for constraints E-I2 and FR-I2.

R-8 closes the one path v1 explicitly drew. AD-05 closes the class.

## Alternatives Considered

**Option A — Ground Truth Protection as a standing principle, with four permitted feedback forms (selected).** A general prohibition on any platform-generated artifact becoming Evidence, plus an exhaustive list of what feedback may become instead.

**Option B — Rely on R-8 alone.** The behavioural loop closure decision already prevents Feedback Records becoming Evidence via E-I2 and FR-I2.
*Rejected:* R-8 addresses the specific arrow `Feedback -> Evidence`. It does not prohibit, for example, a summarised Pattern being re-ingested as a source, a Validation finding being written back as an observation, or an Opportunity assessment being treated as market intelligence on re-acquisition. Each of these is a distinct path to the same failure, and none is covered by FR-I2. A rule that names one instance invites the others.

**Option C — Prohibition without enumerating permitted forms.** State only that platform artifacts may not become Evidence.
*Rejected:* a pure prohibition tells the Feedback Engine what it cannot do and leaves its legitimate output undefined. That ambiguity is what produced C-03 in the first place — a stage with work to do and no defined destination for it. Enumerating the four permitted forms makes the rule constructive rather than merely restrictive.

**Option D — Permit platform artifacts as Evidence with mandatory marking.** Allow re-entry but tag internally-originated Evidence and exclude it from independence counting.
*Rejected:* this is Alternative C from Review 2, rejected there and rejected here for the same reasons. Marking does not prevent lineage cycles; it adds a second class of Evidence with different rules; and it makes every rule referencing Evidence subtype-qualified. It preserves the appearance of grounding while removing its substance.

**Option E — Enforce by engine discipline rather than architectural rule.** Trust engines not to write platform content as Evidence.
*Rejected:* whether Evidence may have upstream lineage is a schema-level property enforced at write time (E-V1, E-I2). Discipline cannot enforce it, cannot be audited, and degrades silently. The platform's own Principle 1 exists because discipline is not a control.

## Rationale

Option A was selected because the hazard is a **class of paths**, not a single arrow.

R-8 is necessary but not sufficient. It resolves v1's explicit notation; AD-05 establishes the general rule that makes any future re-entry path — including ones not yet imagined — prohibited by default rather than permitted until someone notices.

The four permitted forms matter as much as the prohibition. They make the rule *constructive*: the Feedback Engine has four well-defined destinations, each with an existing home in the architecture (Feedback Record, object status, research directive, configuration store). Nothing is left undefined, so no implementer is forced to improvise a fifth path.

Critically, **none of the four permitted forms enters the lineage graph as grounding.** Learning Signals are Feedback Records, which are lineage leaves. Knowledge Updates are status transitions, which by D-02 are the sole non-versioning mutation and create no new lineage. Research Triggers cause acquisition of *external* Evidence. Model Calibration writes to configuration, which is outside the object model entirely. The prohibition is therefore complete across all four.

## What It Binds

- **Every engine.** No engine may write an Evidence object derived from platform-internal content. Only the Research Engine creates Evidence, and only from external acquisition.
- **The Evidence object.** E-V1 (`derives_from` empty) and E-I2 (never derives from any platform-internal object) are the enforcement points.
- **The Feedback Engine.** Its output is restricted to the four permitted forms.
- **The Feedback Record.** FR-I2 (never becomes Evidence) and FR-V6 (derives from Execution Records only).
- **The acceptance path** (`T01.4.1`, N-8). Violations are rejected at write time, not detected later.
- **Any future object type or engine.** The prohibition is general and applies without further amendment.

Elevates and generalises AD-01. Constrains AD-03. Enforced jointly with R-8.

## Consequences Accepted

- **Loop closure is not verifiable by lineage traversal.** An auditor cannot see the cycle in the object graph, because there is deliberately no cycle. Closure must be verified through `INFORMS` references and research-directive provenance.
- **Legitimate re-ingestion is prohibited.** If the platform ever needed to treat a derived artifact as an observation — for example, a published report of its own findings that subsequently influences a market — that content must be re-acquired externally through the Research Engine, with its own provenance. This is a real cost, accepted deliberately.
- **The four permitted forms are exhaustive and constrain future design.** Any new feedback destination requires amending this record.
- **Behavioural self-reinforcement remains possible.** AD-05 closes the lineage path completely. It does **not** close the behavioural path: learning narrows what is researched, which narrows what is found. That is M-70, mitigated separately by `T08.3.1`–`T08.3.3`. **AD-05 must not be read as having solved loop instability.**

## Known Tensions

**With AD-03 (Feedback Loop).** v1's pipeline notation `Feedback -> Evidence` is incompatible with AD-05 read literally. Resolved by R-8: the arrow means "feedback causes new external Evidence to be acquired", not "feedback becomes Evidence". AD-05 and R-8 are jointly the closure of C-04.

**With operational convenience.** Re-acquiring externally is slower and costlier than re-ingesting internally. This tension will recur under delivery pressure. The consequences above record that the cost was accepted knowingly.

**Residual, unresolved.** M-70 (feedback loop instability guard) remains open. AD-05 addresses the structural path; the behavioural path is unmitigated until P8.

## Revisit Conditions

Reconsider only if:

- A legitimate platform need cannot be expressed as any of the four permitted forms, **and** external re-acquisition is demonstrably impossible rather than merely inconvenient, **or**
- The prohibition is shown to prevent a form of learning the platform requires and cannot obtain otherwise.

**Cost, latency or convenience are explicitly not grounds.** Those consequences are recorded above as knowingly accepted. Adding a fifth permitted form requires superseding this record, not extending it informally.
