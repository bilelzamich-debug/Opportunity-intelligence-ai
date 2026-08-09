# N-16 — Source Diversity Propagation

| Field | Value |
|---|---|
| **ID** | N-16 |
| **Title** | Source Diversity Propagation |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2 |
| **Closes** | M-23 |
| **Backlog task** | `T00.6.1` |
| **Depends on** | [S-2](S-02-evidential-support-function.md), [N-6](N-06-store-graph-boundary.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**Two-tier propagation.**

### Tier 1 — Summary attribute, carried on every object

`independent_source_count` is added to the **universal attribute set**: the number of mutually independent Evidence sources beneath the object, after independence grouping.

| Property | Value |
|---|---|
| Scope | All nine object types |
| Computed | At creation, from the object's direct inputs |
| Cost | Constant — no traversal required at read time |
| Feeds | S-2 input 1; S-4 sufficiency thresholds |

**Propagation rule.** An object's count is derived from its inputs' counts and their independence relationships — never by re-traversing to Evidence. For Evidence itself the count is 1.

### Tier 2 — Deep traversal, on demand

Detailed source composition — which source *types*, which specific sources, how they distribute across constituents — is obtained by **lineage traversal** (N-6, `T01.3.4`) when an engine needs it.

**Only Pattern Intelligence requires Tier 2**, for `source_diversity` and `artefact_assessment` (PT-V4, PT-V5). Under N-14, that traversal is within its own inputs' lineage and therefore permitted.

### Why not a side channel

AD-02 forbids engines exchanging anything the object model does not represent. Tier 1 **extends the object model** rather than opening a channel around it. This was the resolution AD-02's Option D rejection anticipated.

## Context

Pattern objects require `source_diversity` and `artefact_assessment` (PT-V4, PT-V5), but that information originates at Evidence — four stages upstream. M-23 recorded that under strict Principle 4 modularity it may not be reachable.

The stakes are high: sampling artefact is Pattern Intelligence's defining risk and PKP v2 names it the platform's most dangerous systemic failure — it produces confident, well-evidenced, entirely false views of the market, invisible to every downstream engine.

S-2 also requires independent source count as its primary input, on every object, at every acceptance check.

## Alternatives Considered

**Option A — Carry full diversity metadata forward on every object.**
*Rejected:* always available, but duplicates a growing payload on every object. Under R-1 immutability the duplication is permanent, and most objects never need the detail.

**Option B — Compute on demand by lineage traversal only.**
*Rejected:* no duplication, but S-2 needs the count at **every acceptance check**. Deep traversal on every write, at depths up to 8 with large fan-in, would make acceptance the platform's bottleneck.

**Option C — Maintain a diversity summary in the Knowledge Graph.**
*Rejected:* under N-6 the graph is a **derived index**, not authoritative. Making engines depend on it for a value that feeds confidence would make a derived structure load-bearing for correctness.

**Option D — Hybrid: summary attribute carried, traversal for detail (selected).**

## Rationale

The two needs have genuinely different shapes, and one mechanism cannot serve both well.

**S-2 needs a cheap scalar on every write** — constant-time, no traversal. **Pattern Intelligence needs rich composition occasionally** — which sources, which types, how distributed. Option A over-serves the first; Option B under-serves it.

Tier 1's propagation rule is the subtle part: the count is computed **from inputs' counts**, not by re-traversal. This keeps it constant-time and consistent with N-6's principle that objects are self-describing.

Choosing an object attribute over a graph query also respects N-6: the graph may lag, and a value feeding confidence must not depend on an index that is eventually consistent.

## What It Binds

- **Universal attribute set** (`T01.1.2`): `independent_source_count` on all nine types.
- **`T01.5.4`** diversity summary attribute implementation.
- **`T02.1.3`** source independence grouping supplies the base count.
- **`T05.1.4`** Pattern artefact assessment uses Tier 2 traversal.
- **S-2 input 1**, **S-4 thresholds** — both read Tier 1.

## Consequences Accepted

- **Derivable information is duplicated** on every object. Accepted: the alternative is deep traversal on every acceptance check.
- **Count accuracy depends on independence grouping** (`T02.1.3`); a false independence judgement inflates every downstream count.
- **Tier 1 is a scalar** — it cannot express *which* sources, so an object with count 5 gives no indication of concentration.
- Tier 2 traversal remains expensive at depth for Pattern Intelligence.

## Known Tensions

**With M-66 (lineage summarisation, open).** Tier 2 traversal at depth 3+ may return sets too large to use; addressed at `T05.2.1`.

**With AD-02.** Extending the object model is the sanctioned route, but each extension enlarges the contract surface.

## Revisit Conditions

Reconsider if Tier 1's scalar proves insufficient — for example, if Pattern Intelligence needs type-level diversity at acceptance rather than on demand, which would justify promoting a small type-vector into Tier 1.
