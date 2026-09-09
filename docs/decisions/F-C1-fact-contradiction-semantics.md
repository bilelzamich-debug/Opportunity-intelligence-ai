# F-C1 — Fact Contradiction: Detection and Representation Semantics

> **RATIFIED 2026-09-09.** The annotation-layer entry recording this
> ratification and its binding interpretation is
> `RATIFICATION-ANNOTATIONS.md` §13, mapping this record to IOM §1.2
> (the `contradicts` attribute), IOM §3.2 (Fact: the CONTRADICTS row,
> Engine Authority, both-Facts-ACTIVE), S-3 (disjoint interaction, not
> superseded) and backlog `T03.1.6`. Ratified with the Project Owner's
> required Q7 amendment (narrower binding scope; see R7). Frozen
> documents are not rewritten; the annotation layer records the binding
> interpretation.

| Field | Value |
|---|---|
| **ID** | F-C1 |
| **Title** | Fact Contradiction: Detection and Representation Semantics |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-09-09 |
| **Date decided** | 2026-09-09 |
| **Source** | Backlog `T03.1.6`; IOM §1.2 (`contradicts`), §3.2 (Fact: CONTRADICTS row, Engine Authority, Failure Cases), §2.4/D-06; R-06; S-3; F-V4; N-4; N-6; N-10; R-1; R-2; V12; T03.1.4 specification; T03.1.6 read-only inspection |
| **Closes** | — (the T03.1.6 specification gap: no ratified source defines when two claims are *incompatible*. OQ-03 is already closed for the *representation* question by R-06; this record addresses the *detection* rule OQ-03 never covered) |
| **Backlog task** | `T03.1.6` |
| **Supersedes** | — |
| **Superseded by** | — |

---

## Decision

### R1 — Normative contradiction definition (answers Q1)

For two claims `a` and `b` — the claims of two ACTIVE Facts — an
**established contradiction** exists **iff all six** conditions hold,
decided with the existing S-3 primitives, unmodified:

| # | Condition | Primitive (claim.py, unchanged) |
|---|---|---|
| C1 | Same subject | `a.same_subject(b)` |
| C2 | Same predicate | `a.same_predicate(b)` |
| C3 | Identical qualifier (R2) | `a.same_qualifier(b)` |
| C4 | Both quantified | `a.value is not None and b.value is not None` |
| C5 | Same unit | `a.value.unit == b.value.unit` |
| C6 | Values disagree outside stated precision | `not a.value.agrees_with(b.value)` — i.e. `abs(a.value.value − b.value.value) > max(a.value.precision, b.value.precision)` |

**Fail-closed rule.** Only an *established contradiction* produces a
`CONTRADICTS` link. **"Cannot establish contradiction" never links.** The
two states are distinct and must never be collapsed (R9): an undecidable
comparison is not a negative result.

The rule is a pure function of the two frozen `Claim` objects — no model,
no wording interpretation, no network, no state — and is therefore
deterministic in the sense the platform requires of structural checks
(N-4; the same posture as `assess_equivalence`).

### R2 — Qualifier scope: identical only (answers Q2)

Contradiction requires **identical qualifiers** (`same_qualifier`:
normalised equality, including both `NONE`/unqualified). Containment and
any other qualifier difference → *cannot establish contradiction* → no
link.

Two grounds:

1. **Value comparability across scopes is undecidable from structure.**
   An unqualified claim and a narrower qualified claim aggregate
   differently; a narrow disagreement is not evidence against a broad
   aggregate, exactly as S-3 holds that "a broad claim is not evidence
   for a narrow one". Counterexample: *"average deal size = $50k"
   (unqualified)* vs *"average deal size (Enterprise segment) = $80k"* —
   both can be simultaneously true; the overall average may differ from
   every segment's.
2. **Disjointness from the DUPLICATES link set (T03.1.4).** Under S-3,
   non-identical qualifiers yield CONTAINMENT or UNCERTAIN, both of which
   T03.1.4 links `DUPLICATES`. If such peers could *also* be linked
   `CONTRADICTS`, one pair would carry two relationships with opposed
   meanings ("equivalence recognised but not merged" and "mutual
   incompatibility"). Under R2 the two link sets are provably disjoint:
   `CONTRADICTS` peers ⊆ NOT_EQUIVALENT peers; `DUPLICATES` peers =
   CONTAINMENT ∪ UNCERTAIN peers.

### R3 — Claim-type blindness (answers Q3; preserves F-V4)

Detection compares **claim content only** (subject, predicate, qualifier,
value). It consults neither `claim_type` nor `attributed_to` — exactly as
S-3 equivalence does not (F-V4 R6 records S-3 as type-blind). Therefore:

| Pairing | Established contradiction under R1? |
|---|---|
| ASSERTION × ASSERTION | Yes — the classic case. |
| ATTRIBUTED_OPINION × ATTRIBUTED_OPINION, **same** speaker | Yes — a speaker self-contradiction is information. |
| ATTRIBUTED_OPINION × ATTRIBUTED_OPINION, **different** speakers | Yes — this *is* the "genuine market disagreement" the IOM names as the thing suppression would hide. |
| ASSERTION × ATTRIBUTED_OPINION (either direction) | Yes — the attributed *content* conflicts with the asserted *content*. |

The link asserts **only** content-level incompatibility. It does not
assert that the opinion is false, that the assertion is wrong, or that
either speaker erred; no winner is selected and no classification
changes. F-V4's biconditional and INV-1..INV-4 are untouched: detection
neither reads nor writes `claim_type`/`attributed_to`, and no Fact's
classification is altered by being linked.

**T03.1.4-F1 (claim-type-aware merging) is NOT required by this record,
is NOT ratified by it, and is explicitly out of scope.** T03.1.6
operates correctly over the current type-blind merge behaviour
unchanged (see Relationship with T03.1.4).

### R4 — Relationship to S-3 verdicts and merge policy (answers Q4)

`MERGE_POLICY`, `Verdict`, and `assess_equivalence` are **unchanged and
not superseded**. The contradiction rule is a separate predicate over
the same claim pairs, with this exact mapping:

| S-3 verdict (pair) | Merge action (unchanged) | T03.1.4 link | T03.1.6 link (this record) |
|---|---|---|---|
| EQUIVALENT | MERGE | — | — (values agree; contradiction impossible by construction) |
| CONTAINMENT | SEPARATE_WITH_DUPLICATES | DUPLICATES | — (R2: qualifiers differ) |
| UNCERTAIN | SEPARATE_WITH_DUPLICATES | DUPLICATES | — (R2: qualifiers differ) |
| NOT_EQUIVALENT (values disagree: C1–C6 all hold) | SEPARATE | — | **CONTRADICTS** |
| NOT_EQUIVALENT (subject/predicate differ, one-sided quantification, or unit mismatch) | SEPARATE | — | — (cannot establish) |

Note the S-3 evaluation order (values are checked before qualifiers): the
contradiction subset always lands in NOT_EQUIVALENT, never in
CONTAINMENT/UNCERTAIN — the disjointness of R2 is structural, not
incidental.

The T03.1.4 specification's sentence "NOT_EQUIVALENT links nothing"
stated that task's DUPLICATES link policy (its AC3 scope, alongside
"CONTRADICTS machinery untouched" in its §4 non-goals, which anticipated
this task). This record extends the separate path with CONTRADICTS for
the established-contradiction subset. No ratified S-3 or T03.1.4
behavior is altered: every verdict, merge action and DUPLICATES link is
byte-identical before and after T03.1.6.

### R5 — Recording surface and symmetry (answers Q5)

The contradiction is recorded **once, on the newly created Fact**, as
`UniversalAttributes.contradicts = (peer object_ids, …)` at Fact
construction. The peer Facts are left untouched.

Grounds:

- **V12 is authoritative on the object surface**: "An object asserts
  relationships through four attributes, each mapping to one taxonomy
  member: derives_from (DERIVES_FROM), duplicates (DUPLICATES),
  **contradicts (CONTRADICTS)** and supersedes/superseded_by
  (SUPERSEDES)." The IOM §1.2 defines the attribute, populated "On
  detection".
- **R-06's engine-and-timestamp requirement** is satisfied by the
  recording object's own provenance: the Fact asserting the relationship
  carries `produced_by_engine = FACT_EXTRACTION` and `produced_at` — the
  same ratified reading T03.1.4 applied to `duplicates`.
- **Symmetry in meaning, one-sided in storage** (T03.1.4 precedent,
  verbatim rationale): "the relationship is symmetric in the relationship
  model, and retroactive re-versioning would be churn without correctness
  gain" (R-1: content changes require new versions; the back-link would
  re-version every peer and supersede its predecessor, gaining nothing).
- **Version binding (R-1a)**: a recorded reference names the specific
  peer version the contradiction was established against. Because a
  canonical merge never changes the claim (`with_attachment` uses
  `replace`, which inherits `contradicts` and `duplicates` tuples
  untouched), links survive versioning and remain semantically valid
  against any version of the peer lineage.

Both Facts remain ACTIVE (backlog AC2): recording a link is not a
lifecycle event; no status transition occurs (R-2: status transition is
the sole non-versioning mutation, and none is triggered here).

A single new Fact may carry both link kinds against *different* peers
(e.g. DUPLICATES to an UNCERTAIN peer and CONTRADICTS to a conflicting
one); only the *same* peer can never receive both (R2 disjointness).

### R6 — Detection timing and coverage (answers Q6)

Detection runs **only at the extraction boundary**, in the separate path,
when Fact Extraction creates a new Fact (IOM §3.2 Engine Authority:
Fact relationships are Created/Modified by Fact Extraction). It
evaluates R1 for the new claim against every ACTIVE peer Fact (the
existing `store.facts.assess_all(claim)` enumeration) and records the
matches. The merge path performs no detection: an EQUIVALENT extraction
attaches to a canonical whose claim it agrees with, so every peer the
incoming claim would contradict is already contradicted by the canonical
(values agree ⟹ same contradiction set), and the merged version
inherits the canonical's links unchanged (R5).

**Pairwise coverage without retroactive mutation.** For any pair of
ACTIVE Facts, the later-created member ran detection against the earlier
one at its creation (or a merge of it inherited those links). Every pair
is therefore assessed exactly once, at the later member's creation — no
retroactive scan is required or performed.

**Historical gap, accepted and recorded (not silent).** Pairs where both
Facts pre-date T03.1.6's implementation were never assessed and remain
unlinked. A retroactive migration would re-version existing Facts (R-1
churn) and is rejected; if ever wanted it requires its own decision
record. Links accrue from implementation forward.

Detection is a **report, not a gate**: no extraction is refused because
of contradiction, and no new refusal stage or reason is created (N-10 is
unaffected — refusals remain request-validity failures).

### R7 — Graph projection (answers Q7)

**UniversalAttributes.contradicts is the authoritative recording surface
for T03.1.6. Graph projection of CONTRADICTS is OUT OF SCOPE for
T03.1.6. T03.1.6 MUST NOT add graph edges or modify graph/store
infrastructure. Any future graph projection decision remains a separate
architectural decision and must not be inferred from this task.**

This is a binding scope statement about T03.1.6 — not an architectural
claim about the entire system, and not a declaration that graph
projection is permanently forbidden. A future architectural decision may
separately determine whether CONTRADICTS (and DUPLICATES) peer-link
attributes should become Knowledge Graph edges. The scope was reached by
verifying against R-06 and the graph contracts, not by assuming the
DUPLICATES precedent:

- N-6: objects are authoritative for their relationships; the graph is a
  derived, rebuildable index that **may lag** and "may never contradict"
  the store. Divergence is a performance concern, never a correctness
  one.
- R-06 binds the closed taxonomy and per-edge engine/timestamp; it does
  not obligate edge emission. The store's atomic write path (`_commit`)
  indexes **lineage only** — this is the existing, ratified state for
  DUPLICATES as well.
- The Master Reference §1014 anticipates the graph holding
  "contradiction links (if OPEN QUESTION-03 is resolved affirmatively)".
  That anticipation is **preserved as a future architectural issue**
  (Known Tensions 1), not silently dropped and not decided here. It is
  out of scope for T03.1.6 because it would require modifying
  `store.py`/`graph.py` (frozen scope for this task) or a seventh oip
  import in `extraction.py` (breaking the ratified 6-import budget).

The backlog AC "Incompatible claims linked, not silently resolved" is
satisfied by the attribute link (V12's reading of the object-asserted
relationship surface; the identical pattern T03.1.4's ratified closure
accepted for DUPLICATES).

### R8 — Invariants

| # | Invariant |
|---|---|
| INV-C1 | **No winner.** Detection never selects, ranks, prefers or scores either Fact. |
| INV-C2 | **No status change.** Both Facts remain ACTIVE; no retraction, supersession, invalidation or archiving is triggered by detection (R-2 untouched). |
| INV-C3 | **No merge interference.** Contradiction never blocks, reorders or alters an S-3 verdict or merge decision (`MERGE_POLICY` unchanged). |
| INV-C4 | **Representation, not resolution.** The CONTRADICTS link is the deliverable; no arbitration, decay, or resolution policy exists or is implied. |
| INV-C5 | **Fail-closed.** CONTRADICTS is recorded only for *established* contradiction; "cannot establish contradiction" never links, and the distinction is auditable. |
| INV-C6 | **Determinism.** The rule is a pure function of the two claims (N-4 structural posture). |
| INV-C7 | **Version stability.** Links survive versioning (tuple inheritance on `replace`); recorded references bind object versions (R-1a). |
| INV-C8 | **Taxonomy closure.** Only CONTRADICTS, from R-06's closed ten-type set, is produced; engines invent no relationship types. |
| INV-C9 | **F-V4 preservation.** `claim_type`/`attributed_to` are neither consulted nor altered; F-V4 INV-1..INV-4 hold unchanged. |

### R9 — Terminology: four categories, never collapsed

Given two claims, exactly one category applies to the contradiction
question:

| Category | Definition | Outcome |
|---|---|---|
| **Equivalent** | All four S-3 conditions hold | Merge (T03.1.4); no link |
| **Contradictory** | R1's six conditions hold — *established contradiction* | CONTRADICTS link; both ACTIVE |
| **Incomparable** | The comparable frame matches but the value relation is **undecidable from structure**: one-sided quantification, unit mismatch, or non-identical qualifiers (scope undecidable) | No CONTRADICTS (fail-closed); DUPLICATES may apply per S-3/T03.1.4 if the verdict is CONTAINMENT/UNCERTAIN |
| **Merely different** | Subjects or predicates differ — logically independent claims; no incompatibility question arises | No link of either kind |

S-3's NOT_EQUIVALENT spans three of these categories (contradictory,
incomparable, merely different); `values_agree` returning `False` covers
two of them. **This conflation is correct for merging** ("not the same
claim") **and unusable for contradiction** — which is precisely why the
detection rule needs its own predicate (R1) rather than a negated
equivalence check, and why no new `Verdict` member may be added (that
would extend S-3's ratified four-outcome set and require superseding it).

---

## Context (problem statement)

The T03.1.6 backlog entry reads: *"Implement contradiction detection
between Facts, producing CONTRADICTS relationships"*, with acceptance
criteria *"Incompatible claims linked, not silently resolved"* and *"Both
Facts remain ACTIVE"*. The representation side is fully ratified and
implemented: CONTRADICTS exists in R-06's closed taxonomy (same-type
pairs, symmetric, engine+timestamp, V12), the IOM §1.2 `contradicts`
attribute and §3.2 Fact relationship row exist, the graph tolerates
symmetric loops, and the S-2 support function already consumes a
`contradiction_count`.

**No ratified source defines the detection rule.** "Incompatible claims"
(IOM §3.2) and "mutual incompatibility" (IOM D-06) are the entire
semantic statement; the IOM's trigger text is the two words "On
detection". OQ-03 asked whether contradiction must be *represented* and
was closed affirmatively (R-06 + RATIFICATION-ANNOTATIONS §4: "OQ-03
(contradictory evidence — via CONTRADICTS)"); it never asked *when two
claims are contradictory*, and nothing else answers that question. S-3
defines agreement, not disagreement. Under the platform's own rules
(markers and semantics are closed only by recorded decision; S-3's
"checkable, not opinion"; the F-V4 precedent of ratifying semantics
before implementation), T03.1.6 cannot be implemented against an
unratified detection rule. This record proposes one.

## Scope

In scope: the normative rule deciding when two Fact claims are
contradictory (Q1); qualifier scope (Q2); claim-type interaction (Q3);
the S-3 interaction (Q4); recording surface and symmetry (Q5); detection
timing and coverage (Q6); graph projection (Q7); the invariants,
terminology and examples that make the rule auditable.

Out of scope: everything listed under Non-Goals, including T03.1.4-F1,
any implementation, any test suite, and any modification to a ratified
record, frozen document, or platform/oip file.

## Authoritative Sources Consulted

| Source | Bearing |
|---|---|
| Backlog `T03.1.6` | Task text and both ACs |
| IOM §1.2 | `contradicts` attribute: "Objects mutually incompatible with this one", "On detection" |
| IOM §2.4/D-06 + R-06 | Closed ten-type taxonomy; CONTRADICTS (any→same type, many:many, optional); symmetric; "every relationship records the asserting engine and timestamp" |
| IOM §3.2 (Fact) | CONTRADICTS → Fact "Incompatible claims (OPEN QUESTION-03)"; "representing disagreement rather than selecting a winner … suppressing it would hide genuine market disagreement"; Engine Authority (Create/Modify: Fact Extraction); Failure Cases ("Over-merging — hides source disagreement") |
| MR §2.1 (OQ-03 text) | "…it is undefined whether the platform holds both, selects one, or flags a conflict…" — resolved toward hold-both-and-flag |
| MR §1014 | Graph anticipated to hold "contradiction links" (see Q7 tension) |
| S-3 + claim.py | Four-condition equivalence; primitives the rule reuses; the NOT_EQUIVALENT conflation; judgement-gap consequences |
| F-V4 | claim_type biconditional; R6's type-blind S-3 finding; INV-1..4; T03.1.4-F1 |
| N-4 | Determinism posture for structural checks |
| N-6 | Objects authoritative; graph derived, may lag |
| N-10 | Failure vs found-nothing (detection is a report, not a gate) |
| R-1 / R-1a / R-2 | Immutability, version-specific binding, lifecycle |
| V12 (acceptance.py) | "An object asserts relationships through four attributes…"; validates contradicts targets |
| T03.1.4 specification + code | DUPLICATES-on-new-Fact precedent; separate path; 6-import budget; frozen-module pins; "CONTRADICTS machinery untouched" listed as non-goal |
| support.py (S-2) | `contradiction_count` consumer (P5) |

## Alternatives Considered

**Q1 — the trigger rule.**
- **Option A — negate S-3's value condition** (any NOT_EQUIVALENT at
  condition 4 ⇒ CONTRADICTS). *Rejected:* `values_agree` returns `False`
  for one-sided quantification and unit mismatch — both *incomparable*,
  not contradictory. Would link every quantified/unquantified pair with a
  matching frame: mass false positives, and exactly the category collapse
  R9 forbids.
- **Option B — semantic/wording contradiction** (antonyms, negation,
  "conflict" judgement). *Rejected:* violates S-3's "checkable, not
  opinion" and MR's "Extraction does not interpret"; non-reproducible
  under N-4.
- **Option C — the six-condition structural rule (selected, R1).**
  Decided with existing primitives; total over all pairs; fail-closed.

**Q2 — qualifier scope.**
- **Option A — identical qualifiers only (selected, R2).**
- **Option B — also allow containment** (broad vs narrow may contradict).
  *Rejected:* aggregation/scope ambiguity is undecidable from structure
  (the average-deal-size counterexample); and it would place CONTRADICTS
  and DUPLICATES on the same peers with opposed meanings, breaking
  T03.1.4's link semantics.

**Q3 — claim-type interaction.**
- **Option A — content-only, type-blind (selected, R3).** Consistent with
  S-3's ratified comparison fields (F-V4 R6); represents market
  disagreement (the IOM's stated purpose); creates no new claim-type
  semantics.
- **Option B — truth-bearer-aware** (require same claim_type and, for
  opinions, same speaker). *Rejected:* invents claim-type semantics in
  relationship logic that no ratified record supplies; strictly-read
  propositions ("S says 5M" vs "TAM is 7M") are compatible, so almost no
  cross-source conflict would ever link — suppressing exactly the
  "genuine market disagreement" the IOM says must not be hidden; and it
  pre-empts T03.1.4-F1's territory in the opposite direction while
  merging remains type-blind (incoherent).
- **Option C — cross-type contradiction forbidden, same-type allowed.**
  *Rejected:* same incoherence (contradiction more type-aware than
  identity), same suppression of the opinion-vs-assertion conflict, no
  textual basis in F-V4.

**Q4 — S-3 interaction.**
- **Option A — separate predicate over the same pairs (selected, R4).**
  No S-3 change; disjoint link sets; total mapping.
- **Option B — add a CONTRADICTION verdict to S-3.** *Rejected:* extends
  the ratified four-outcome set; would require superseding S-3, which a
  task-scoped record must not do.

**Q5 — recording.**
- **Option A — new Fact's attributes only (selected, R5).** V12's
  authoritative surface; T03.1.4 precedent; no R-1 churn.
- **Option B — both Facts re-versioned for symmetry.** *Rejected:*
  retroactive re-versioning is churn without correctness gain
  (T03.1.4's ratified rationale); the old versions would keep their
  missing links regardless.
- **Option C — Relationship objects as the recording surface.** See Q7.

**Q6 — timing.**
- **Option A — extraction-boundary detection on creation (selected,
  R6).** Single choke point (V7: only Fact Extraction creates Facts);
  complete pairwise coverage without retroactive mutation.
- **Option B — periodic pairwise scan of existing ACTIVE Facts.**
  *Rejected:* requires re-versioning both members of every newly found
  pair (R-1 churn), duplicates the assessment the later member already
  performed, and adds an unowned background process the orchestration
  model does not define.

**Q7 — graph projection.**
- **Option A — attribute recording only for T03.1.6; graph projection
  out of scope and reserved to a separate future architectural decision
  (selected, R7; scope narrowed at ratification by the Project Owner's
  required amendment).**
- **Option B — also emit graph Relationship objects now.** *Rejected for
  this task:* not required by any decision record (MR §1014 is
  anticipatory and the lowest-precedence document; N-6 explicitly
  permits the index to lag); not implementable within T03.1.6's file and
  import constraints (store.py/graph.py frozen; `oip.relationships`
  would be a seventh import); and projecting CONTRADICTS but not
  DUPLICATES would be arbitrary. The ratification amendment confirmed
  and narrowed this scope (R7).

## Rationale

The rule is the closure of decisions the repository already states, read
together — the same method F-V4 used:

- S-3 makes claim identity a four-component structural comparison, and
  makes agreement decidable ("values agree within stated precision").
  Its own asymmetry rationale — under-merge preferred because
  over-merge "hides source disagreement" — presupposes that disagreement
  is *representable*; R-06 supplies the type; the IOM supplies the
  surface (§1.2 attribute) and the no-winner semantics. What none of
  them supplies is the boundary between *disagreement* and
  *non-comparability* — and that boundary is the entire content of this
  record.
- The six conditions are exactly the existing S-3 comparability frame
  (C1–C3 identical, the strict EQUIVALENT-branch qualifier test) plus
  the value comparison stripped of its two undecidable degenerate cases
  (C4 removes one-sided quantification; C5 removes unit mismatch). Every
  condition is *necessary*: remove any one and a counterexample links a
  pair that can be simultaneously true (see Examples). None is
  *sufficient* alone. Together they are exactly sufficient: the frame
  establishes the claims assert the same thing in the same scope, and
  C6 establishes they assert it differently beyond stated precision.
- The fail-closed posture follows from the platform's founding
  asymmetry: a false CONTRADICTS link misrepresents the evidence base
  (and, via S-2 P5, suppresses support), while a missed link leaves both
  claims visible, ACTIVE and correctable — the same recoverable/
  irreversible asymmetry S-3 applies to merging.
- Type-blindness (R3) is not an addition but the *absence* of one: S-3's
  ratified comparison fields do not include claim_type or
  attributed_to, and a task-scoped record must not introduce semantics
  the register never ratified (F-V4 defines classification, not
  contradiction identity).

## Examples and Counterexamples

Claim notation: `(subject, predicate, qualifier, Quantity(value,
precision, unit))`; `NONE` = unqualified. Peers are ACTIVE Facts.

| # | Claim a | Claim b | Category | Outcome |
|---|---|---|---|---|
| 1 | (acme, mrr, NONE, 5.0M ±0.1M USD) | (acme, mrr, NONE, 7.2M ±0.1M USD) | **Contradictory** (C1–C6 hold; Δ=2.2M > 0.1M) | **CONTRADICTS**; both ACTIVE |
| 2 | (acme, mrr, NONE, 5.0M ±0.1M USD) | (acme, mrr, NONE, 5.05M ±0.1M USD) | Equivalent (Δ=0.05M ≤ 0.1M) | Merge (T03.1.4); no new Fact, no link |
| 3 | (acme, mrr, NONE, 5.0M ±0.1M USD) | (acme, mrr, NONE, unquantified) | Incomparable (C4 fails) | No link; NOT_EQUIVALENT; both ACTIVE |
| 4 | (acme, deal size, NONE, 5.0 ±0.1 USD k) | (acme, deal size, NONE, 4.8 ±0.1 EUR k) | Incomparable (C5 fails; no conversion knowledge — 4.8 EUR k ≈ 5.2 USD k may *agree*) | No link |
| 5 | (acme, mrr, NONE, 5.0M ±0.5M USD) | (acme, mrr, NONE, 5.3M ±0.5M USD) | Equivalent (precision-tolerated: Δ=0.3M ≤ 0.5M) | Merge; no link — and no contradiction |
| 6 | (acme, mrr, NONE, 5.0M ±0.1M USD) | (acme, mrr, Q3, 7.0M ±0.1M USD) | Incomparable (C3 fails; scope ambiguity) | CONTAINMENT → DUPLICATES (T03.1.4), **not** CONTRADICTS |
| 7 | ASSERTION (acme, churn, Q3, 3% ±0.5%) | ATTRIBUTED_OPINION attributed_to="CFO" (acme, churn, Q3, 6% ±0.5%) | Contradictory (type-blind; content frame conflicts) | CONTRADICTS; both ACTIVE; neither marked wrong; F-V4 fields untouched |
| 8 | ATTRIBUTED_OPINION "Analyst A" (tam, NONE, 5.0B ±0.1B USD) | ATTRIBUTED_OPINION "Analyst B" (tam, NONE, 7.0B ±0.1B USD) | Contradictory — the market-disagreement case OQ-03 exists to represent | CONTRADICTS; both ACTIVE |
| 9 | (acme, mrr, NONE, 5.0M) | (globex, mrr, NONE, 7.0M) | Merely different (C1 fails) | No link; NOT_EQUIVALENT |
| 10 | (churn, decreased, Q3 report) | (churn, increased, analytics) | Merely different (C2 fails — predicate antonymy is not structurally detectable) | No link; both retained — the existing `test_contradictory_evidence_both_retained` case, unchanged |

**Counterexamples that shaped the rule** (each killed or bounded an
alternative): the segment-average pair (Q2-B); the 5 kg / 11.02 lb pair
(q1-A: physically agreeing, textually mismatched — and its mirror 5 kg /
5 lb, genuinely conflicting but undecidable: unit mismatch fails closed
in *both* directions); the unquantified/quantified pair (Q1-A); the
churn decreased/increased pair (bounds the rule: a real-world
contradiction the structure cannot see — accepted false negative, since
detecting antonymy is wording interpretation, forbidden by S-3 and MR);
the hidden-scope pair (two unqualified revenue claims of different
periods, neither scope recorded — linked as contradictory *as recorded*:
unrecorded scope is invisible to structure; extraction fidelity (S-5,
M-67) governs whether scopes get recorded, not contradiction detection);
and "merchants" vs "sellers" (S-3's own recorded judgement gap —
paraphrase never links).

## Failure and Indeterminate Cases

- **Detection cannot fail operationally.** The rule is a pure function;
  there is no attempt that can fail, so N-10's failed-vs-found-nothing
  distinction does not arise, and no failure record, refusal stage or
  refusal reason is created.
- **Indeterminate outcomes are the incomparable category** (R9): they
  produce *no link* and remain fully auditable through the existing S-3
  verdict and reason already reported per peer in `ExtractionOutcome.
  equivalence` ("cannot establish contradiction" is distinguishable from
  "established contradiction" in every report and explanation).
- **No extraction is refused** because its claim contradicts existing
  Facts — contradiction is information, and both Facts are kept (AC1,
  AC2, OQ-03).

## Relationship with T03.1.4

T03.1.6 composes onto T03.1.4's separate path without modifying it:
same peer enumeration (`assess_all`), same recording pattern
(new-Fact attributes, peers untouched), disjoint link sets (R2/R4),
`MERGE_POLICY` untouched. The frozen-module guarantees T03.1.4's
verification pins (`claim.py`, `fact.py`, `semantic.py`) remain intact.
The merge path performs no detection (R6). **T03.1.4-F1 is not required,
not ratified, and not obstructed by this record**; if F1 lands later,
its interaction with contradiction (whether newly-separated cross-type
pairs should be scanned) is a revisit condition below, not a dependency.

## Relationship with T03.1.5 (F-V4)

F-V4's biconditional, INV-1..INV-4, the classification gate and the
`CLAIM_TYPE_CONFLICT` refusal are untouched: detection neither reads nor
writes `claim_type`/`attributed_to`, and no classification changes by
being linked. The type-blind reading (R3) follows F-V4 R6's own
characterisation of S-3 and creates no new claim-type semantics — the
link expresses content conflict only, selects no winner, and would not
change if F-V4 had never been ratified.

## Relationship with R-06

CONTRADICTS is used from the closed ten-type set; no type is invented or
extended. Symmetry is honoured in meaning with one-sided storage (the
T03.1.4 DUPLICATES reading). The engine-and-timestamp requirement is
carried by the recording Fact's provenance (V12's authoritative
attribute surface); a graph `Relationship` edge — which enforces
engine/timestamp structurally — is not emitted by this task (R7) but
remains available to any future projection, whose edges would cite
`FACT_EXTRACTION` and the detection timestamp.

## What It Binds

- **T03.1.6** (on ratification): the normative detection rule and both
  ACs' meaning — "incompatible" = R1's established contradiction;
  "linked" = `contradicts` attributes; "not silently resolved" +
  "both ACTIVE" = INV-C1..C4.
- **Fact Extraction engine** (`oip/extraction.py`): the only implementer
  (Engine Authority); see Implementation Constraints.
- **S-3 / T03.1.4 / F-V4 / R-06**: unchanged, not superseded; their
  guarantees are restated as invariants this rule must preserve.
- **Downstream (informational)**: S-2's `contradiction_count` input is
  populatable from recorded links when that wiring is built; nothing in
  S-2 changes here.

## Implementation Constraints

*(For the T03.1.6 execution specification. Ratified 2026-09-09; the
ratification act itself changes no code and creates no tests — see
§Ratification.)*

1. Sole modified file: `platform/oip/extraction.py`; new tests in
   `platform/tests/test_contradiction.py` (created at implementation
   time, not now). No other platform/oip file changes.
2. Import budget stays 6/6 (`acceptance, claim, contract, evidence,
   fact, store`): every primitive the rule needs is already imported or
   is a `Claim` method.
3. The contradiction predicate is evaluated from the two `Claim` objects
   directly — never by parsing `EquivalenceResult.reason` strings.
4. `contradicts` targets are constructed exactly like `duplicates`
   targets (same `assess_all` enumeration), keeping the two link
   computations structurally parallel.
5. `ExtractionOutcome` gains a `contradicts` field mirroring
   `duplicates`; the explanation text records established contradictions
   and, for indeterminate peers, carries the S-3 reason (INV-C5's
   auditability).
6. No new `Verdict` member, no `MERGE_POLICY` change, no new refusal
   stage/reason, no store/graph/acceptance change (V12 already validates
   `contradicts`).
7. Existing checks that must keep passing unchanged:
   `verify_t03_1_4` §C AC3 (asserts `duplicates == ()` for the
   NOT_EQUIVALENT synonym case — unaffected);
   `test_extraction.py::test_contradictory_evidence_both_retained`
   (the churn antonymy pair stays unlinked — Example 10);
   `test_acceptance.py` V12 default-attribute assertions.

## Non-Goals

- T03.1.4-F1 (claim-type-aware merging) — separate future decision.
- Predicate-antonymy, negation or wording-based contradiction.
- Subject/predicate/qualifier resolution (paraphrase, synonyms).
- Unit conversion or any physical-quantity knowledge.
- Retroactive scanning or migration of pre-existing Fact pairs.
- Graph edge projection (out of scope for T03.1.6; any future projection
  is a separate architectural decision that must not be inferred from
  this task — R7).
- S-2 `contradiction_count` wiring and any support-function change.
- Any resolution, arbitration, winner-selection, decay or confidence
  effect of contradiction (S-2 P5 is a *downstream consumer* of links,
  not part of detection).
- New relationship types; any change to R-06, S-3, T03.1.4, F-V4,
  `MERGE_POLICY`, `Verdict`, or any ratified record.

## Consequences Accepted

- **Narrowness.** The rule links only same-frame, same-unit,
  out-of-precision value disagreements. Antonymic predicates, paraphrase,
  unit variants and scope-qualified conflicts stay unlinked (Examples
  4, 6, 10). This is the deliberate price of checkability and
  determinism; the remedy is better decomposition and resolution (S-3's
  own revisit logic), never relaxing the conditions.
- **Hidden-scope false positives.** Two unqualified claims with
  unrecorded different scopes are linked as contradictory *as recorded*.
- **Historical gap.** Pairs predating implementation are never linked
  (R6).
- **One-sided storage.** Finding a Fact's contradictors requires
  scanning peers' `contradicts` attributes (or the future graph
  projection); no back-pointers exist. Same as DUPLICATES today.
- **Version-pinned references.** Links name peer versions; after a peer
  merges, the link points at the superseded version (semantically valid,
  R-1a-conformant; same as DUPLICATES).
- **Cross-type links exist** (opinion × assertion, opinion × opinion
  across speakers) and express content conflict only — a ratifier who
  wants truth-bearer-aware contradiction must amend R3 before
  ratification, not after.

## Known Tensions

1. **MR §1014 vs graph projection — a future architectural issue (Q7).**
   The Master Reference anticipates graph-held contradiction links; no
   projection of peer-link attributes (DUPLICATES or CONTRADICTS) exists,
   and building one is outside T03.1.6's frozen scope. Whether, how and
   when peer-link attributes should be projected into graph edges is
   deliberately left to a **separate architectural decision**: this
   record neither makes that decision nor forbids it (R7). Under N-6 the
   absence of a projection is a lagging index, not a correctness gap —
   but it is a *recorded* divergence, not a silent one.
2. **With T03.1.4-F1 (open).** If merging becomes type-aware, the
   cross-type EQUIVALENT pairs F1 would separate into DUPLICATES-linked
   Facts currently merge and never reach contradiction detection. F1's
   own record must consider that interaction; this record takes no
   position on it.
3. **With S-2 (informational).** P5 penalises `contradiction_count`;
   until that input is wired to these links, recorded contradictions
   have no support effect. No S-2 change is made or implied.

## Revisit Conditions

- A ratified notion of claim-level *semantic* comparison (paraphrase,
  antonymy, unit conversion) reopens Q1/Q2 — as it would also reopen
  S-3, which governs the shared frame.
- T03.1.4-F1 landing (type-aware merging) reopens Q3's interaction.
- A ratified requirement for graph-resident contradiction traversal
  (e.g. a consumer of MR §1014) reopens Q7.
- Observed false-link or missed-link rates that materially misrepresent
  disagreement — evidence first, per AD-01; the remedy is a superseding
  record, never a code-side redefinition.
- Convenience is not grounds for reopening.

## Ratification

**RATIFIED 2026-09-09.** The Project Owner accepted the semantic
analysis with one required amendment, applied before ratification and
affecting Q7 only:

- **Q7 amendment (owner-required, applied verbatim in R7):**
  "UniversalAttributes.contradicts is the authoritative recording
  surface for T03.1.6. Graph projection of CONTRADICTS is OUT OF SCOPE
  for T03.1.6. T03.1.6 MUST NOT add graph edges or modify graph/store
  infrastructure. Any future graph projection decision remains a
  separate architectural decision and must not be inferred from this
  task." The Master Reference §1014 tension is preserved as a future
  architectural issue (Known Tensions 1). The amendment is a scope
  statement for T03.1.6, not a permanent prohibition on graph
  projection.

Q1–Q6 were approved as proposed, unchanged. The record was re-read in
full after the amendment to confirm that no other semantics changed.

The ratification act followed the F-V4 mechanism (`2dcd03e`) exactly:
Status set to `RATIFIED`, Date decided set, and the annotation-layer
entry added at `RATIFICATION-ANNOTATIONS.md` §13, mapping this record to
IOM §1.2 (`contradicts`), IOM §3.2 (CONTRADICTS row, Engine Authority,
both-Facts-ACTIVE), S-3 (disjoint interaction, not superseded) and
backlog `T03.1.6`. No frozen document was rewritten.

Ratification changes no code and creates no tests. T03.1.6 now proceeds
to its execution specification and implementation under the normal task
process; T03.1.4-F1 remains unratified and not required.
