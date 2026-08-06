# N-15 — Evidence Storage: Hybrid, Constrained by Licensing

| Field | Value |
|---|---|
| **ID** | N-15 |
| **Title** | Evidence Storage: Hybrid, Constrained by Licensing |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | OQ-12 |
| **Backlog task** | `T00.4.8` |
| **Depends on** | [N-12](N-12-retention.md), [N-6](N-06-store-graph-boundary.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

Evidence is stored **in full where licensing permits, by reference otherwise**.

Every Evidence object records which mode applies. **`content_fingerprint` and provenance are always retained**, regardless of mode.

**Reference-only Evidence carries a recorded exposure to source drift** — the source may change or disappear, making the Evidence unverifiable.

## Context

Whether Evidence is stored in full, by reference, or both was undefined (OQ-12).

The decision has material consequences for N-12 retention cost, for re-extraction capability (OQ-22), and for the platform's exposure to source drift — a Research Engine failure mode where content changes after capture, leaving lineage pointing at something no longer verifiable.

It is constrained by licensing (M-18): some sources permit acquisition but not retention.

## Alternatives Considered

**Option A — Full content always.**
*Rejected:* maximum verifiability and re-extraction capability, but may breach source licensing terms, and drives the largest storage cost. Some sources simply do not permit retention.

**Option B — Reference only.**
*Rejected:* minimal storage and no licensing exposure, but makes the platform's grounding dependent on external systems remaining available and unchanged. The Research Engine's failure modes indicate they do not.

**Option C — Hybrid, licensing-determined (selected).**

**Option D — Full content with time-limited retention.**
*Rejected:* addresses licensing partially but creates a period after which historical Evidence silently becomes unverifiable, with no signal at the point of use.

## Rationale

Licensing is a hard external constraint, not a preference — so a single uniform policy is not available. Option A would be preferable on every technical dimension and is simply not permissible for all sources.

The hybrid records the mode **per Evidence object**, so downstream consumers can distinguish verifiable-in-place Evidence from Evidence dependent on an external source. That distinction is itself information: reference-only Evidence carries a genuine additional risk, and Article X requires the platform to state what it does not securely hold.

Always retaining `content_fingerprint` and provenance is the safeguard. Even for reference-only Evidence, the platform can detect drift (fingerprint mismatch on re-acquisition) and can always say what it saw and where.

## What It Binds

- **`T02.2.1`** acquisition records storage mode per Evidence object.
- **`T02.2.3`** drift detection by fingerprint comparison.
- **`T02.1.2`** licensing enforcement determines mode at acquisition.
- **N-12** retention cost profile depends on the mix.
- **OQ-22** re-extraction is possible only for full-content Evidence.

## Consequences Accepted

- **Two storage modes** to implement and reason about.
- **Reference-only Evidence is vulnerable to source drift** and may become unverifiable through no platform fault.
- **Re-extraction is unavailable** for reference-only Evidence, permanently limiting that Evidence to the extraction capability available at acquisition time.
- Mode is determined by licensing, so the platform's verifiability profile is partly outside its control.

## Known Tensions

**With M-18 (licensing, `T02.1.2`).** This decision depends on licensing assessment being correct at acquisition; a misassessment is discovered only later.

**With Article III.** Reference-only Evidence weakens verifiability in practice while satisfying it formally. Recorded rather than hidden.

## Revisit Conditions

Reconsider if source drift on reference-only Evidence proves frequent enough to undermine grounding, in which case licensing-restricted sources may need to be excluded rather than referenced.
