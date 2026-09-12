# F-A1 — Sampled Fidelity Audit: S-5 Layer 2 Protocol Semantics

> **RATIFIED 2026-09-12.** The annotation-layer entry recording this
> ratification and its binding interpretation is
> `RATIFICATION-ANNOTATIONS.md` §14, mapping this record to S-5 (Layer 2
> and the Layer 3 boundary), N-2, N-4, N-7/CI-1, N-10, N-15, N-20, R-3,
> R-06, R-02, AD-02 and backlog `T03.2.2`. Ratified by the Project
> Owner as fourteen approved decisions ("OWNER DECISIONS FOR T03.2.2",
> 2026-09-12), resolving the eight specification blockers D1–D8 of the
> T03.2.2 continuation audit. Frozen documents are not rewritten; the
> annotation layer records the binding interpretation.

| Field | Value |
|---|---|
| **ID** | F-A1 |
| **Title** | Sampled Fidelity Audit: S-5 Layer 2 Protocol Semantics |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-09-12 |
| **Date decided** | 2026-09-12 |
| **Source** | Backlog `T03.2.2`; S-5 (Layer 2 table, Consequences, Layer 3 boundary); the T03.2.2 continuation audit (blockers D1–D8, A/B/C); Project Owner decisions 1–14 of 2026-09-12; N-1, N-2, N-4, N-7, N-8, N-10, N-15, N-20, R-02, R-03, R-06, AD-02; T03.2.1 (Layer 1 baseline, `9ea50a5` content) |
| **Closes** | — (resolves the T03.2.2 specification blockers D1–D8. **M-67 remains open** — "unsampled hallucinations still reach production"; **M-20 remains open** pending `T03.2.3`) |
| **Backlog task** | `T03.2.2` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

### R1 — Sampling position: prospective, at acceptance, non-gating (Owner decision 1)

Layer 2 sampling is **prospective (the R-b reading)**. The population is
**accepted Facts entering the acceptance boundary**. The sampling
decision is made **mechanically when a Fact is accepted**. The audit
itself is **asynchronous and non-blocking** and **MUST NOT become an
acceptance gate**: acceptance succeeds or fails exactly as it would
without Layer 2 installed (N-8 structural semantics unchanged; N-2's
engines-never-block preserved).

The rejected alternative (R-a — periodic census of the accumulated
ACTIVE-Fact stock) is recorded here as declined, not forbidden forever;
adopting it later requires superseding this record.

### R2 — Selection mechanism: deterministic hash-threshold (Owner decision 2)

Selection is a **pure, reproducible, property-testable function** of
**stable Fact identity plus the applicable sampling-policy
version/salt**, compared against the configured rate
(hash-threshold). Prohibited:

- **unseeded randomness** (any RNG in selection);
- **insertion-order dependence** (enumeration order, store state,
  time-of-day, process identity may not affect the decision);
- **pinning a random seed as a substitute for deterministic
  identity-based selection** (N-4's own rejection of seed-pinning
  applies; the guarantee is reproducibility from recorded inputs, not a
  pinned accident of configuration).

N-4 conformance: the decision is derivable from captured state (Fact
identity + policy version), so any selection is investigable and
re-derivable after the fact. Regression tests assert **properties**
(determinism, purity, rate-boundary behaviour, monotonicity in rate),
never equality with a pinned selection list.

### R3 — Initial rate: 5% as ONE global population fraction (Owner decision 3)

The initial global sampling rate is **5%**. "5% of accepted Facts" is
interpreted as a **global population fraction**. **Source type and
confidence band are stratification dimensions for measurement and
allocation, not separate independent 5% populations.**

No statistical optimality claims and no coverage guarantees are made or
implied. S-5's own statement stands: the 5% initial value has **no
empirical basis** and must be tuned once drift distribution is
observed. Nothing in this record converts the sampled rate into an
estimator with claimed properties beyond the recorded selection rule.

### R4 — Strata: ratified vocabularies only (Owner decision 4)

The stratification dimensions use the **existing ratified closed
vocabularies** exactly:

- **`SourceType`** — the closed 8-member taxonomy of N-20 §5.1
  (`source.py`, ratified 2026-08-04), reached from the attachment's
  Evidence via `Provenance.source_type` and `classify()`;
- **`ConfidenceBand`** — the ratified 5-band taxonomy of R-3
  (`enums.py`), reached via `ConfidenceBand.for_value()` applied to the
  attachment's `extraction_confidence`.

**No new source types and no new confidence bands may be created** (the
"closed vocabularies are enumerated by a ratified decision, never
inline" rule; extension requires superseding N-20 / R-3 respectively).

### R5 — Multi-attachment Facts: per-stratum eligibility, single-audit dedup (Owner decision 5)

A Fact may qualify for **multiple strata** because it can contain
multiple `EvidenceAttachment`s (merged Facts; R-5/D-05). Therefore:

- **Eligibility is per stratum**: each distinct stratum contributed by
  an attachment makes the Fact a selection candidate in that stratum.
- **Single-audit deduplication**: a selected Fact is audited **only
  once for a given audit configuration/policy version**. The audit-unit
  key is `(fact identity, sampling-policy version)`.
- **The audit unit must retain the selected Fact and the specific
  `EvidenceAttachment`/source context that caused eligibility** — the
  recorded audit names the selecting attachment (its `evidence_ref`,
  `positional_anchor`), the source type and the confidence band, not
  just the Fact.

Prohibited: **arbitrarily choosing only the first attachment** (the
stratum set must be derived from all attachments; where several strata
select, a defined deterministic tie-break — not list order — picks the
retained context); **collapsing attachment-level
`extraction_confidence` into `UniversalAttributes.confidence`** (the
universal contract and `UniversalAttributes` are untouched).

### R6 — Recording surface: an append-only operational register outside the object model (Owner decision 6)

Audit judgements are recorded in an **append-only operational audit
register outside the Intelligence Object Model**, following the
established architectural precedent of `FailureStore`
(`configuration.py`, N-10) and `DriftRegister` (`drift.py`, "[N-10 —
outside the model]").

**Not created** (each prohibition is a closed ratified surface):

- **no tenth Intelligence Object** (AD-02/IOM §2.6: the nine-type
  surface is closed);
- **no `AUDITS` relationship** (R-06: the ten-type taxonomy is closed);
- **no new lifecycle state** (R-02: the seven-state vocabulary is
  closed);
- **no audit fields on `Fact`** (fact.py is byte-pinned and its
  contract is frozen);
- **no `FeedbackRecord`** (FR-V6: derives only from Execution Records);
- **no `Validation` object** (R-6: Validation DERIVES_FROM Solution and
  TESTS claims; M-31: Validation reports, it does not gate).

Audit judgements are **operational records, not intelligence objects**:
they never enter the lineage graph, never contribute to confidence,
scoring, support or pattern detection, and are never returned by
Intelligence Object queries (the CI-1 access-boundary discipline applied
to the audit surface).

### R7 — Judgement vocabulary: closed three, no defaults (Owner decision 7)

The audit judgement vocabulary is **exactly** the three S-5 values:

`FAITHFUL` · `DRIFTED` · `UNSUPPORTED`

The set is closed and is enumerated by S-5 itself (the ratified source
for this vocabulary). **`FAITHFUL` MUST NEVER be assumed by default.**
**Unaudited means no judgement exists** — the absence of a judgement is
recorded as absence (a pending selection), never as `FAITHFUL`, never
as silence-that-reads-as-approval.

### R8 — The human auditor: external, recorded, not a gate (Owner decision 8)

The semantic-fidelity judgement is performed **externally by a human
auditor**. The platform **does not perform semantic interpretation,
NLP, LLM-based judgement, or network-based semantic verification** (the
F-V4 R5 posture — "pure, deterministic, checkable … no interpretation
of wording, no LLM, no network" — applied to Layer 2). The platform
**records the externally supplied judgement**.

**This audit is NOT a fourth N-2 gate.** N-2 remains **exactly three
gates** (G1/G2/G3). The audit decides no transition, holds no object in
any state, and **MUST NOT block Fact acceptance** (R1). The judgement
enters the platform as **recorded operational input** — the N-1 §5
pattern: the platform records outcomes; it does not adjudicate them.

### R9 — Consequences: measurement signals only (Owner decision 9)

For T03.2.2, **`DRIFTED` and `UNSUPPORTED` are audit
measurements/signals only**. They **MUST NOT automatically**:

- reject a Fact,
- retract a Fact,
- supersede a Fact,
- invalidate a Fact,
- mutate Fact lifecycle in any way.

**An UNSUPPORTED Fact remains ACTIVE unless an independent,
already-ratified mechanism changes it** (e.g. ordinary supersession by
a later extraction version, or upstream cascade under N-9 — neither is
triggered by the audit). The purpose of Layer 2 is **measurement and
feeding Layer 3**, not per-Fact enforcement. This mirrors S-5's own
position: "a rising hallucination rate is a platform-level defect, not
a per-Fact issue."

### R10 — Rate adjustment: manual, versioned, identified (Owner decision 10)

**No automatic sampling-rate adjustment is implemented.** The initial
rate is 5% (R3). Future adjustment is a **manual owner/operator
configuration action using an immutable, versioned
policy/configuration record**. **Every audit record MUST identify the
sampling-policy/configuration version under which it was selected.**

Not invented and not ratified (all remain outside T03.2.2):
elevated-drift thresholds; adjustment formulas; statistical
significance rules; automatic adjustment algorithms. S-5's "rate rises
for source types or confidence bands showing elevated drift" is
realised only as: an owner reads measured drift, and manually records a
new policy version.

### R11 — AC2: external protocol + provider contract + fixture demonstration (Owner decision 11)

The backlog acceptance criterion **"Audit detects paraphrase drift
anchor checks miss"** is satisfied **architecturally through an
external human semantic-fidelity audit protocol**:

1. The platform must provide enough information for the auditor to
   compare: **the Fact/claim**, **its qualifying context**, **the
   relevant Evidence**, and **the exact anchored source span**.
2. The external auditor returns `FAITHFUL` / `DRIFTED` / `UNSUPPORTED`.
3. The platform records that judgement (R6/R7/R8).

The implementation **MUST include a judgement-provider/interface
contract and fixture-driven tests demonstrating that a Layer-1-passing
Fact can subsequently receive `DRIFTED` or `UNSUPPORTED` through
Layer-2 audit** (a Fact whose anchor resolves and whose structured
components are present at the span — Layer 1 PASSES — yet whose span
meaning the claim subtly misrepresents). **The platform itself must not
perform the semantic judgement.** The fixture provider stands in for
the human auditor; the demonstration proves the recording architecture
and the reachability of Layer-2 outcomes, not machine semantic
capability.

### R12 — Module and mechanical pins (Owner decision 12)

A **dedicated production module for the Layer-2 audit infrastructure**
is authorized (`oip/auditing.py`). The current module count is pinned at
**37**; the relevant mechanical governance pins are updated to reflect
**37 → 38**. **All other architectural pins and constraints are
preserved** — the change is additive, not a weakening or removal. The
exact pinned sites and the new import-set pin are enumerated in the
T03.2.2 execution specification (its §5) and in
`RATIFICATION-ANNOTATIONS.md` §14.

---

## Protected Constraints (Owner decision 13 — unchanged by this record)

| Constraint | Status |
|---|---|
| N-2: exactly three human gates | Unchanged (R8: audit is not a gate) |
| N-4: reproducibility / property-testing | Unchanged (R2: conformant selection) |
| CI-1 / N-7: configuration isolation | Unchanged (R10/R6: policy is isolated infrastructure state) |
| N-10: operational records outside the object model | Unchanged (R6 follows it) |
| N-15: Evidence storage semantics | Unchanged |
| N-20: SourceType taxonomy | Unchanged (R4 reuses it) |
| R-3: ConfidenceBand taxonomy | Unchanged (R4 reuses it) |
| R-06: relationship taxonomy (ten) | Unchanged (no AUDITS) |
| R-02: lifecycle states (seven) | Unchanged (no new state) |
| AD-02: nine Intelligence Object types | Unchanged — **no new object type is authorized** |
| T03.1.1–T03.2.1 semantics | Unchanged |
| No LLM · no NLP · no external API · no network | Unchanged (R8) |
| No changes to `main` | Unchanged |
| Existing byte pins and architectural boundaries | Unchanged **except** the module-count pins explicitly updated by R12 |

## Scope (Owner decision 14)

T03.2.2 remains a **measurement/audit layer**. **Not implemented, not
ratified here:** T03.2.3 metrics; hallucination-rate or drift-rate
formulas; rate publication; automatic policy adaptation. **M-67 and
M-20 are NOT closed** by this task or its implementation; a later task
must explicitly satisfy their closure criteria.

## Relationship with S-5 and T03.2.1

S-5 is the governing record; F-A1 **specifies what S-5 Layer 2 left
unspecified** (mechanism, trigger, surface, consequence, adjustment,
multi-attachment resolution, AC2 standard) and does not supersede any
S-5 text. Layer 1 is untouched: anchor verification runs on 100% of
Facts at acceptance, blocks acceptance on failure, and catches
fabricated location only; `AnchorVerifier.anchor_failure_rate` remains
Layer-1 measurement and is explicitly **not** the hallucination rate
(`semantic.py`). Layer 3 (T03.2.3) will consume audit records produced
under this protocol; no Layer-3 semantics (rate definitions,
publication, trending) are ratified by F-A1.

## Relationship with N-10, N-7 and the register precedents

The audit register is the third instance of the established
operational-register pattern (`FailureStore`, `DriftRegister`): outside
the object model, never in lineage, co-existing with the store rather
than inside it. The sampling policy follows N-7's immutability and
versioning discipline as infrastructure state under CI-1 — it is **not**
an engine `ConfigurationRecord` (those are per-`Engine`; the audit
protocol is not an engine), a placement choice recorded here so it is
not silently re-derived later.

## Relationship with DriftRegister (N-15) — different drift concepts

`DriftRegister` records **source drift**: a content-fingerprint
mismatch on re-acquisition (N-15, T02.2.3). F-A1's register records
**semantic-fidelity audit judgements** about extraction quality (S-5
Layer 2). The shared word "drift" names two different concepts in two
different modules; neither subsumes the other, and no conflation is
permitted.

## What It Binds

- **T03.2.2** (both ACs' meaning: AC1 = versioned `SamplingPolicy` +
  installation composition; AC2 = R11).
- **`oip/auditing.py`** (authorized; sole new production module) and
  the additive store observation hook.
- **The nine module-count pins** (37 → 38) and the **new import-set
  pin** for `auditing.py` (`verify_t03_1_2.py` §D; exact sites in the
  execution specification).
- **T03.2.3** (downstream consumer; informational — no metric
  semantics ratified here).
- The T03.2.2 execution specification, which must conform to this
  record.

## Implementation Constraints

*(For the T03.2.2 execution specification. Ratified 2026-09-12; the
ratification act itself changes no code and creates no tests — see
§Ratification.)*

1. Sole new production module: `platform/oip/auditing.py`, header
   citing `Task: T03.2.2` and the architecture references (S-5, F-A1,
   N-2, N-4, N-7/CI-1, N-10, M-67 open).
2. `platform/oip/store.py`: additive, non-interpretive observation hook
   only (`audit_sampler: object | None = None` + post-commit
   invocation at the Fact acceptance chokepoint — the `anchor_verifier`
   precedent). No acceptance-rule semantics change; F-V6 untouched;
   sampler errors must never fail an acceptance (N-10 failure record
   instead).
3. `claim.py`, `fact.py`, `semantic.py` untouched (byte-pinned);
   `extraction.py` and `anchoring.py` untouched (import-set pins;
   Layer 2 attaches by store composition, never inside the extraction
   engine).
4. `auditing.py` oip-import set ≤ 6, DAG-safe, pinned in
   `verify_t03_1_2.py` §D at implementation (proposed:
   `{enums, evidence, fact, source}`).
5. The nine module-count pins change 37 → 38 in the same change that
   adds the module; every other check in every verifier is unchanged.
6. New tests in `platform/tests/test_auditing.py`, including the R11
   AC2 fixture demonstration.
7. `scripts/verify_all.sh` untouched (its historically stale unit-count
   pin remains stale by standing rule).
8. No T03.2.3 work; no marker-register changes; M-67/M-20 stay open.

## Non-Goals

- T03.2.3: rate computation, publication, trending, success-measure
  wiring.
- Automatic rate adjustment of any kind (R10).
- Per-Fact enforcement: rejection/retraction/supersession/invalidation
  triggered by audit judgements (R9).
- In-platform semantic judgement, NLP, LLM use, or network calls (R8).
- New object types, relationships, lifecycle states, or Fact fields
  (R6).
- Auditor tooling/UI beyond the judgement-provider interface contract.
- Statistical guarantees of any kind (R3).

## Consequences Accepted

- **Sampling measures; it does not eliminate.** Most accepted Facts are
  never audited; the hallucination rate is observed only over the
  audited subset, with no statistical claim beyond the recorded
  selection rule. M-67's open portion stands.
- **Human audit capacity is an ongoing operational cost** (S-5's
  stated consequence), bounded by the configured rate.
- **Judgement quality is entirely external.** The platform cannot
  validate auditor correctness; it records, it does not adjudicate
  (N-1 §5 pattern).
- **Register growth** is unbounded until a retention decision exists
  (N-12 tension, same as `FailureStore`/`DriftRegister`).
- **Non-gating means latency is real:** a selected Fact may be consumed
  downstream before its judgement exists. Accepted — measurement, not
  enforcement.
- **The module-count deviation (37 → 38) is recorded here** as an
  authorized, pinned change — not a silent drift.

## Known Tensions

1. **With M-67 (open).** Unsampled hallucinations still reach
   production; even sampled ones remain ACTIVE when judged
   `UNSUPPORTED` (R9). Both are stated plainly, per S-5.
2. **With T03.2.3 (future).** Pending (selected-but-unjudged) records
   must be handled by that task's metric semantics; F-A1 takes no
   position.
3. **With N-12 (retention, open).** No retention treatment for audit
   records.
4. **With `DriftRegister` (naming).** Two "drift" concepts now exist
   (N-15 source drift; S-5 semantic drift). Recorded to prevent
   conflation.
5. **With the register precedents' in-memory nature.** Like
   `FailureStore`/`DriftRegister`, the register is process-local until
   the platform gains a persistence layer.

## Revisit Conditions

- S-5's own revisit: measured hallucination rates exceeding the level
  at which the grounding layer can be trusted reopen the mechanism
  (Option B, independent re-extraction).
- Any proposal to **automate** rate adjustment or add per-Fact
  enforcement consequences requires a **superseding record** — never a
  code-side redefinition.
- T03.2.3 requires its own specification for metric semantics over
  this register.
- A ratified need to persist the register, or to expose auditor
  tooling, reopens the surface question.
- Convenience is not grounds for reopening.

## Ratification

**RATIFIED 2026-09-12.** The Project Owner reviewed the T03.2.2
continuation audit (blockers D1–D8, A/B/C) and approved the
architecture as fourteen explicit decisions. Mapping: D1+D2 → R1–R3
(R-b prospective sampling; deterministic hash-threshold; 5% as one
global fraction); D3 → R6; D4 → R8; D5 → R9; D6 → R10; D7 → R5; D8 →
R11; blocker C (module count) → R12; protected constraints → Protected
Constraints; scope → Scope. All fourteen were approved as stated; no
amendment was required.

The ratification act follows the F-C1 mechanism (`2dcd03e`/`6ba086f`)
exactly: Status set to `RATIFIED`, Date decided set, and the
annotation-layer entry added at `RATIFICATION-ANNOTATIONS.md` §14. No
frozen document was rewritten. Ratification changes no code and creates
no tests. T03.2.2 now proceeds to its execution specification and
implementation under the normal task process; M-67 and M-20 remain
open.
