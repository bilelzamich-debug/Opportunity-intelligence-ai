# F-A2 — Layer-3 Quality Metrics: Hallucination and Drift Rates

> **RATIFIED 2026-09-12.** The annotation-layer entry recording this
> ratification and its binding interpretation is
> `RATIFICATION-ANNOTATIONS.md` §14, mapping this record to S-5
> (Layer 3), N-3 (stage-2 proxy measures), F-A1 (the audit protocol
> whose records Layer 3 consumes, and its explicit Layer-3 deferral)
> and backlog `T03.2.3`. Ratified by the Project Owner as the eight
> approved decisions OD-1–OD-8 ("OWNER RATIFICATION OF GOVERNANCE
> SPECIFICATION", 2026-09-12), drafted in
> `platform/validation/T03.2.3-specification.md`. Frozen documents are
> not rewritten; the annotation layer records the binding
> interpretation. **Implementation has NOT started; M-20 and M-67
> remain open.**

| Field | Value |
|---|---|
| **ID** | F-A2 |
| **Title** | Layer-3 Quality Metrics: Hallucination and Drift Rates |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-09-12 |
| **Date decided** | 2026-09-12 |
| **Source** | Backlog `T03.2.3`; S-5 (Layer 3 table: the two metrics and their definitions, publication and trend intent); N-3 (stage-2 proxy "Hallucination rate (measured, published)"; binds `T03.2.3` and `T09.1.4`); F-A1 §Scope/§Revisit Conditions (explicitly defers all Layer-3 semantics to a T03.2.3 specification); `platform/validation/T03.2.3-specification.md` (the governance specification, OD-1–OD-8 with options and evaluation); Project Owner ratification of OD-1–OD-8, 2026-09-12; N-2, N-4, N-6, N-7/CI-1, N-10, N-11, N-12, N-14; `RATIFICATION-ANNOTATIONS.md` §14 (multi-stratum union clarification); T03.2.2 corrected implementation (the `AuditRegister` baseline) |
| **Closes** | — (**M-20 remains OPEN during implementation** — closable only after the seven conditions of OD-6 below; **M-67 remains open** with severity reduced per S-5) |
| **Backlog task** | `T03.2.3` |
| **Depends on** | F-A1 (`T03.2.2`); S-5; N-3 (`T00.3.3`) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

S-5 Layer 3 is made operative as two published platform quality
metrics over the `AuditRegister`, under eight owner decisions. Every
decision below is quoted substance from the owner ratification of
2026-09-12; the full options analysis lives in the specification
(§6, OD-1–OD-8).

### OD-1 — Denominator: judged records only

The denominator is the set of `AuditRegister` records with a final
`AuditJudgement` (`FAITHFUL`, `DRIFTED`, `UNSUPPORTED` — the closed
F-A1 R7 set). Therefore `judged = faithful + drifted + unsupported`:

```
hallucination_rate = unsupported / judged
drift_rate         = drifted / judged
```

Pending selected-but-unjudged records: **excluded** from numerator and
denominator. `SelectionFailure` records: **excluded** from numerator
and denominator. Duplicate selection attempts: **excluded because they
do not create audit records** (F-A1 R5 dedup — `DuplicateSelectionError`
is raised, nothing is appended). The configured sampling rate is
**never** a denominator or estimator.

### OD-2 — Zero denominator: None, never 0.0

When `judged == 0`, the metric value is **None / unavailable**. It
must **not** be represented as 0.0 or 0%. The metric surface preserves
the distinction between "zero observed hallucinations" and "no judged
audit observations."

### OD-3 — Policy-version semantics: both scopes, no collapsing

Both a **global** metric scope and **per-policy-version** metric
scopes are provided. Global metrics are calculated over the disjoint
union of all applicable audit records. A Fact audited again under a
newer `SamplingPolicy` version is a new audit and is **not** collapsed
into the previous audit; **no "winning audit" rule is invented**.
Per-version metrics use only that version's records. **No audit
record is counted more than once within a given metric scope.**

### OD-4 — Publication surface: queryable platform quality metric

A deterministic, queryable platform quality-metric surface derived
directly from `AuditRegister`. The minimum surface exposes:
hallucination rate, drift rate, judged count, faithful count, drifted
count, unsupported count, pending count, selection-failure count,
metric scope, and policy version where applicable — an
immutable/frozen metric snapshot (compatible with the existing
architecture). The metric is derived from actual `AuditRegister`
judgement results. "Published" means queryable and available as a
platform quality metric for platform consumers. It does **not**
require network publication, external telemetry, external
observability services, dashboards, a web API, or a third-party
metrics system unless a later authoritative task requires those.
"Reported alongside platform output" means the metric is available
through the platform's quality-metric surface when platform output is
consumed. The future general observability machinery of `T09.1.4` is
**not** implemented here.

### OD-5 — Trend semantics: judged_at, sparse UTC-day series

Trend tracking uses **`judged_at`** as the temporal basis (the
quality judgement becomes an actual audit result at judgement time).
Provided: (a) the current/cumulative metric snapshot, and (b) a
deterministic **sparse UTC-day trend series** — day buckets are
calendar days in UTC; **no empty buckets** are created for days with
no judged audit records (a day with zero judged records has no metric
observation and must not manufacture a 0% rate). Trend output is
deterministic, ascending by date, insertion-order independent, derived
only from actual judgement records, and available globally and per
policy version. **Not introduced:** rolling windows, confidence
intervals, statistical significance claims, predictive trend models,
sampling correction formulas. The metric is descriptive measurement
only. The ratified T03.2.2 multi-stratum selection-probability
clarification (`P(selected) = 1-(1-r)^k`) remains unchanged and is
**not** used to alter the hallucination-rate formula.

### OD-6 — M-20: OPEN during implementation; closure conditions

**M-20 remains OPEN during implementation.** T03.2.3 may satisfy the
substantive conditions needed for M-20 closure, but M-20 must **not**
be marked closed merely because the specification has been ratified.
M-20 can be closed only after: (1) T03.2.3 implementation is complete;
(2) all T03.2.3 acceptance criteria are verified; (3) the
hallucination-rate metric is computed from audit results; (4) the
metric is published on the approved platform surface; (5) trend
tracking is verified; (6) required verification gates pass; (7) the
governance closure annotation is recorded through the established
governance mechanism. Until those conditions are satisfied, M-20 =
OPEN. **M-67 also remains OPEN** (S-5: "open with severity reduced,
not be closed").

### OD-7 — T03.2.3 / T09.1.4 boundary

T03.2.3 owns the minimum Layer-3 quality metric surface required by
S-5 and N-3: hallucination rate, drift rate, current metric snapshots,
deterministic trend data. `T09.1.4` remains responsible for the later
general stage-level proxy machinery and phase-exit wiring described by
the authoritative architecture. T09.1.4 functionality is **not**
duplicated inside T03.2.3; the general observability architecture is
**not** redesigned.

### OD-8 — Module placement: extend auditing.py, count stays 38

The metric extends `platform/oip/auditing.py` rather than creating a
new production module, because the metric is directly derived from
`AuditRegister`, `auditing.py` already owns the audit mechanism, this
follows the existing Layer-1 rate precedent, avoids unnecessary
architecture expansion, and preserves CI-1 / N-7 isolation. Module
count remains **38**; no module-count pin changes are required.

## Exact formulas (consolidated)

For scope `S` (global: all judged records; per-version: judged records
with `policy_version = v`):

```
judged(S)             = faithful(S) + drifted(S) + unsupported(S)
hallucination_rate(S) = unsupported(S) / judged(S)    if judged(S) > 0
                        None                         if judged(S) = 0
drift_rate(S)         = drifted(S) / judged(S)       if judged(S) > 0
                        None                         if judged(S) = 0

context counts (published, never inside the rates):
pending(S), selection_failures(S)

trend: utc_date(judged_at) buckets (naive timestamps read as UTC),
sparse (no empty days), ascending, pure function of the register
```

Properties: `hallucination_rate + drift_rate ≤ 1`; rates ∈ [0.0, 1.0]
or `None`; the configured sampling rate (5%, POLICY_V1) never enters
any formula; recomputation is idempotent; global scope = disjoint
union of per-version scopes.

## Protected Constraints (unchanged by this record)

F-A1 R1–R12 and all T03.2.2 semantics; the `AuditRegister` class
surface (Layer 3 is added beside the register as pure functions, not
into it); the multi-stratum union clarification (§14); N-2 non-gating;
N-4 determinism; N-6 store/graph boundary; N-7/CI-1 isolation; N-10
failure representation; N-11 concurrency discipline; N-12 (retention
open — no retention treatment here); N-14 read access; AD-02 (no new
object type); byte pins on `claim.py`/`fact.py`/`semantic.py`;
import-set pins; module-count pins at 38; the protected stale pins and
`scripts/verify_all.sh`; no network / LLM / NLP / new dependencies;
frozen ratified documents are not rewritten.

## Scope

T03.2.3 = the S-5 Layer-3 hallucination-rate and drift-rate quality
metrics over the `AuditRegister`: formulas, denominator, pending and
`SelectionFailure` treatment, policy-version scoping, the queryable
publication surface, the sparse UTC-day trend, and the M-20 closure
mechanism — per OD-1–OD-8. Not in scope: everything in Non-Goals.

## Relationship with S-5, N-3 and F-A1

S-5 Layer 3 names the two metrics and their publication intent; this
record supplies the mechanical semantics S-5 left unspecified. N-3
binds the published hallucination rate as the stage-2 proxy measure;
`T09.1.4` later generalizes. F-A1 produced the register this record
consumes and explicitly ratified none of the semantics decided here
("no Layer-3 semantics (rate definitions, publication, trending) are
ratified by F-A1"); F-A2 fills exactly that deferral. Layer 1's
`AnchorVerifier.anchor_failure_rate` remains Layer-1 measurement and
is not the hallucination rate.

## What It Binds

- **`T03.2.3`** implementation (executes OD-1–OD-8; the specification's
  §7–§19 are normative for it).
- **`T03.3.1`** (P3 exit): "Hallucination rate published" is verified
  against this surface.
- **`T09.1.4`**: consumes this surface for stage 2; must not silently
  replace it (superseding requires a new record).
- **N-3** stage-2 proxy family: hallucination rate (measured,
  published) — satisfied by this surface once implemented.
- **M-20**: closure conditions fixed by OD-6 (seven conditions, owner
  act).
- **M-67**: remains open with severity reduced; unaffected.

## Non-Goals

No estimator, sampling inference, confidence interval, significance
rule, or statistical guarantee; no predictive trend models or sampling
correction formulas (OD-5); no per-stratum / per-source-type rate
decomposition (not ratified by S-5; would require its own record); no
FAITHFUL-rate publication (S-5 names two metrics); no thresholds,
targets, alerts, or automatic rate adjustment (F-A1 R10 stands); no
persistence or retention treatment (N-12 open); no network
publication, external telemetry, dashboards, web API, or third-party
metrics system (OD-4); no general observability machinery,
multi-stage proxy framework, or phase-exit wiring (T09.1.2/T09.1.4);
no object-model change, IOM type, lifecycle effect, or gating; no
change to T03.2.1/T03.2.2 semantics, the register class surface, or
`anchor_failure_rate`; no T03.3.1 work; no marker changes outside the
OD-6 mechanism.

## Consequences Accepted

- The rates describe the **audited subset only** — most accepted Facts
  are never audited (F-A1 consequence, inherited); no statistical
  claim beyond the recorded selection rule is made or implied.
- Sparse trends make quiet periods invisible as buckets; absence is
  the honest representation (OD-5E) — consumers read counts, not just
  rates.
- `None`-on-empty requires consumers to handle absence explicitly
  (OD-2); the frozen snapshot type makes "0.0 with zero judgements"
  unrepresentable.
- A Fact judged under two policy versions contributes two units to the
  global scope (two audit results exist — the register's own ratified
  semantics); per-version scopes are the comparison-safe view.
- The trend series is process-local until a persistence decision
  exists (N-12 tension, same as the register).

## Known Tensions

1. **With M-67 (open).** The published rate measures; it does not
   eliminate. Unsampled hallucinations still reach production.
2. **With N-12 (open).** No retention treatment for audit records or
   trends.
3. **With T09.1.4 (future).** The stage-2 surface must generalize
   without silent replacement; superseding requires a record.
4. **With judgement latency (F-A1 tension 2, resolved here).** Pending
   records are context counts, never rate components — the rates
   measure fidelity, not auditor throughput.

## Revisit Conditions

- `T09.1.2`/`T09.1.4` may supersede the surface via a new ratified
  record (consuming or replacing — never silent rewrite).
- An N-12 retention decision reopens trend retention (derived data:
  retention applies to the register).
- A superseding judgement vocabulary (impossible without superseding
  F-A1 R7) reopens the formulas.
- A ratified need for external publication reopens OD-4.
- A new `SamplingPolicy` version does **not** reopen this record
  (OD-3 scoping already handles regime changes; adjustment remains
  manual and versioned per F-A1 R10).

## Ratification

**RATIFIED 2026-09-12.** The Project Owner reviewed
`platform/validation/T03.2.3-specification.md` (governance
specification, OD-1–OD-8 with options and evaluation) and approved
all eight owner decisions as recommended, with the ratification text
elaborating OD-5's prohibitions (no predictive trend models, no
sampling correction formulas) and OD-6's closure conditions (the
seven-condition list recorded verbatim above). No amendment to any
technical decision was required; no formula, denominator, time
window, publication API, trend model, module placement, or M-20 rule
was changed from the specification.

The ratification act follows the F-A1/F-C1 mechanism exactly: Status
set to `RATIFIED`, Date decided set, this record created in
`docs/decisions/` with the root `decisions/` symlink, and the
annotation-layer entry appended at `RATIFICATION-ANNOTATIONS.md` §14.
No frozen document was rewritten. Ratification changes no code and
creates no tests; **T03.2.3 implementation has not started** and
awaits explicit instruction under the specification's §17–§19 gates.
M-20 and M-67 remain open.
