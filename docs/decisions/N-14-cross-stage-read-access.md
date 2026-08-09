# N-14 — Cross-Stage Read Access: Lineage-Restricted

| Field | Value |
|---|---|
| **ID** | N-14 |
| **Title** | Cross-Stage Read Access: Lineage-Restricted |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-02 |
| **Date decided** | 2026-08-02 |
| **Source** | Blocker Resolution; PKP v2; IOM |
| **Closes** | OQ-18 |
| **Backlog task** | `T00.5.7` |
| **Depends on** | [N-6](N-06-store-graph-boundary.md) |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

**An engine may read any object within the lineage of its own inputs.**

It may not read objects outside that lineage, regardless of stage.

| Engine | Direct input | Additionally readable |
|---|---|---|
| Fact Extraction | Evidence | — |
| Problem Intelligence | Facts | Evidence beneath those Facts |
| Pattern Intelligence | Problems | Facts and Evidence beneath those Problems |
| Opportunity Intelligence | Patterns | Problems, Facts, Evidence beneath |
| Solution Intelligence | Opportunities | Patterns, **Problems**, Facts, Evidence beneath |
| Validation | Solutions | Opportunities, Patterns, Problems, Facts, Evidence beneath |
| Feedback | Execution Records | Solutions, Opportunities and their full lineage |

**Read access does not confer write access.** The authority matrix is unchanged: exactly one engine creates each object type.

**The restriction is lineage, not stage distance.** An engine may read deep into its own inputs' derivation; it may not read a sibling object it did not derive from.

## Context

Whether an engine may read objects from stages earlier than its immediate predecessor was undefined (OQ-18).

The strict pipeline reading forbids it. But S-V4 requires Solutions to demonstrate problem-fit by referencing specific Problems, which is impossible if Solution Intelligence can read only Opportunities. Three read grants in the IOM authority matrix were marked conditional on this.

PKP v2 names this the sharpest practical tension between the pipeline's sequential notation and Principle 1's evidence requirement.

## Alternatives Considered

**Option A — Strict: immediate predecessor only.**
*Rejected:* maximum stage separation, but makes S-V4 unsatisfiable. Solution Intelligence could not demonstrate that a solution addresses the underlying problems — it would have lineage without meaning.

**Option B — Unrestricted read of any `ACTIVE` object.**
*Rejected:* solves the problem and erodes stage separation entirely. Pattern Intelligence reading arbitrary Opportunities would create implicit coupling AD-04 forbids.

**Option C — Lineage-restricted (selected).**

**Option D — Explicit per-engine grants.**
*Rejected:* precise, but a fixed grant list requires amendment whenever a legitimate need appears, and encodes no principle — each grant would be justified individually rather than by rule.

## Rationale

Lineage restriction grants exactly what Principle 1 requires and nothing more.

An engine justifying its output must be able to reach the evidence beneath it — that is what evidence-first reasoning means. Lineage is precisely the set of objects that contributed to its inputs, so **the grant follows the justification requirement exactly**.

**Why Principle 4 erosion is contained:** the grant is bounded by a relationship every object already carries. An engine cannot reach an object it did not derive from, so no new coupling is created between parallel branches of the pipeline. Coupling is to *ancestry*, which already exists as a hard dependency, rather than to *peers*, which would be new.

The rule is also self-maintaining: as the object model evolves, lineage-restricted access adjusts automatically, where Option D's fixed grants would decay.

## What It Binds

- **IOM §2.5 authority matrix** — three conditional read grants confirmed.
- **S-V4** problem-fit rationale becomes satisfiable.
- **`T07.2.4`** Solution Intelligence reads underlying Problems.
- **`T01.3.4`** backward traversal is the access mechanism.
- **OQ-08** Pattern Intelligence reading Facts: permitted where those Facts are in its Problems' lineage.

## Consequences Accepted

- **Wider engine input surfaces.** Engines may now depend on the definitions of object types several stages upstream, increasing the blast radius of object model changes.
- **Deep reads are expensive** — traversal cost grows with lineage depth and fan-in.
- **Temptation to over-read.** Nothing prevents an engine reading its entire lineage habitually rather than as needed.
- Testing surfaces expand: an engine's behaviour now depends on objects beyond its direct inputs.

## Known Tensions

**With AD-04.** Any cross-stage access is in tension with strict separation. Contained because the grant follows lineage rather than opening arbitrary access.

**With M-66 (lineage summarisation, open).** Deep reads at depth 5+ may return evidence sets too large to use, addressed at `T05.2.1`.

## Revisit Conditions

Reconsider if lineage-restricted access proves to create de facto coupling — for example, if engines routinely depend on deep upstream attributes such that upstream object changes break downstream engines regularly.
