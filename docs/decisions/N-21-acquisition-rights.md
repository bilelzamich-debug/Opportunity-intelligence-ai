# N-21 — Acquisition Rights: Per-Source Assessment Recorded on Evidence, Enforced Before Acquisition

| Field | Value |
|---|---|
| **ID** | N-21 |
| **Title** | Acquisition Rights: Per-Source Assessment Recorded on Evidence, Enforced Before Acquisition |
| **Status** | `RATIFIED` |
| **Owner** | Platform Architecture |
| **Date recorded** | 2026-08-04 |
| **Date decided** | 2026-08-04 |
| **Source** | PKP v2 §9 (MISSING-18), §13, §14 (X14); IOM §3.1; Blocker Resolution B-34; N-15; N-05 |
| **Closes** | **M-18 (partially — rights half only)** |
| **Backlog task** | `T02.1.2` |
| **Depends on** | AD-01, AD-05, N-01, N-05, N-08, N-10, N-12, N-15, R-1, R-2, CI-1 |
| **Supersedes** | — |
| **Superseded by** | — |

> 🔺 **ESCALATION — RATIFIED 2026-08-04.** Approved by the Project Owner.
> Ratified with recorded reservations; see *Honest Limitations*.
> Owning task `T02.1.2` ⚠ carries an escalation flag, satisfying `AGENT-PLAYBOOK` F6.
>
> **Competence warning.** This decision concerns **legal admissibility**.
> Architecture can specify *where* the question is asked, *who* answers it,
> *how* the answer is recorded and *what* happens on each answer. It cannot
> determine what is lawful in any jurisdiction. §5.3 is deliberately built so
> that the legal judgement is supplied by a competent human, not inferred by
> the platform. A ratifier should confirm this division is acceptable.

---

## 1. Architectural Problem Restated

PKP v2 §9 (L624): *"No legal, licensing, robots, rate-limit, or terms-of-use
policy for acquisition, despite acquisition being the platform's only external
interface."*

v2 §14 (X14): *"Legal and compliance in acquisition"* — coverage: **No**.

M-18 names six concerns. Prior investigation established that they divide on
two distinct decision variables:

| Concern | Variable | In this decision? |
|---|---|---|
| **Acquisition legality** | Rights — *may this material be taken?* | **YES** |
| **Licensing** | Rights | **YES** |
| **Terms of use** | Rights | **YES** |
| **Retention rights** | Rights — *may it be kept?* | **YES** |
| **Robots** | Conduct — *how may the system be accessed?* | **NO** |
| **Rate limits** | Conduct | **NO** |

**Rationale for the boundary, from the corpus.** N-15 pairs licensing with
retention — *"some sources permit acquisition but not retention"* — and no
ratified text ever pairs robots or rate limits with retention. The rights half
is what `T02.1.2` and N-15 consume; the conduct half has **zero** dependent
acceptance criteria anywhere in the backlog.

This record resolves the **rights half only**. The conduct half remains open
as **M-18b** (§9).

---

## 2. Binding Constraints Extracted

Quoted or directly cited. No new requirement is introduced.

| # | Constraint | Source |
|---|---|---|
| K1 | `access_conditions` — "Terms under which acquired" — is a **required** Evidence attribute | IOM §3.1 |
| K2 | Evidence is stored "in full **where licensing permits**, by reference otherwise"; mode recorded per object | N-15 (Decision) |
| K3 | "This decision **depends on licensing assessment being correct at acquisition**; a misassessment is discovered only later" | N-15 (Known Tensions) |
| K4 | "`T02.1.2` licensing enforcement **determines mode at acquisition**" | N-15 (What It Binds) |
| K5 | "some sources **permit acquisition but not retention**" | N-15 (Context) |
| K6 | The Store enforces acceptance at `PROPOSED → ACTIVE`; "the Store enforces **structural** rules only"; "Mechanism and policy are separated: the Store evaluates rules; it does not define them" | N-08 |
| K7 | Research "is the **ONLY** engine permitted to introduce information from outside the platform" | v2 §4.4 |
| K8 | Research holds sole create authority for Evidence | IOM §2.5 |
| K9 | "Evidence licensing requires restricting which derived conclusions may be seen by whom (M-18, `T02.1.2`)" — a **named deferral trigger** for the access-control model | N-05 |
| K10 | Failed acceptance produces a **failure record**, never a silent rejection; failure is distinguishable from empty | N-08, N-10 |
| K11 | Content immutable after acceptance; hard deletion unsupported (I4) | R-1, IOM §1.4 |
| K12 | Lineage skeleton retained permanently; content tiered by **reachability**; tiering sets `ARCHIVED` | N-12 (closes M-38) |
| K13 | "Configuration … must never participate in reasoning, scoring, pattern detection, or lineage" | CI-1 / N-07 |
| K14 | The platform is **advisory**; it "holds no budget, no operational authority, and no accountability for consequences" | N-01, Constitution Art. VI |
| K15 | "Negative results, contradictions, and **known gaps are recorded** with the same standing as favourable findings" | Constitution Art. X |
| K16 | Precedence: Constitution → decision records → IOM → PKP → Backlog | Constitution Art. XI |
| K17 | A marker "is closed only by a record in this register" | README L145, Playbook F3 |
| K18 | Nine engines, nine objects, ten stages — "Fixed" | Playbook F8 |
| K19 | v2 M-18 is *"Legal, licensing, terms-of-use"* — **distinct** from M-16 (source taxonomy/trust); conflating them "would close the wrong gap" | crosswalk §3 #4 |

---

## 3. Legal Design Space

Four architectures remain compatible with K1–K19. (B-34's Option 1,
"permissive — acquire what is accessible", is excluded: it makes K2's
conditional inoperative and leaves K3's "assessment" undefined.)

### Option A — Conservative allow-list: acquire only from explicitly licensed sources

- **Ownership.** Whoever curates the allow-list (unassigned).
- **Enforcement point.** Before acquisition.
- **Compatibility.** Satisfies K2/K4. Compatible with K13 if the list is not
  scoring input.
- **Consequences.** Maximum legal safety; severe coverage loss. B-34 records
  the cost: *"Restricts the evidence base, worsening coverage (M-17) and
  sampling bias risk."*
- **Affected tasks.** `T02.1.2`, `T02.1.4` (coverage worsens), `T02.3.1`.
- **Affected markers.** Aggravates M-17.
- **Migration cost.** Low to build, high to operate — every source needs
  prior clearance.
- **Extensibility.** Poor: the list is the bottleneck.

### Option B — Per-source assessment recorded on Evidence, **not** enforced

- **Ownership.** Acquirer records; nobody blocks.
- **Enforcement point.** None.
- **Compatibility.** **Fails K4** — N-15 states enforcement *determines mode
  at acquisition*. Recording without enforcing leaves ineligible material in
  an immutable store (K11), unremovable (I4) and only tierable by
  reachability (K12), not by rights.
- **Migration cost.** Lowest.
- **Extensibility.** Irrelevant — architecturally non-compliant.

### Option C — Per-source assessment **with enforcement before acquisition** *(B-34 Option 4)*

- **Ownership.** Policy set by a human authority; applied mechanically.
- **Enforcement point.** Before acquisition, inside the Research Engine (K7,
  K8) — strictly earlier than the Store's acceptance gate (K6).
- **Compatibility.** Satisfies K1–K5 directly; respects K6's mechanism/policy
  split; produces failure records under K10; keeps the Store structural.
- **Consequences.** Ineligible material never enters the immutable store —
  the outcome K11/I4 make irreversible if missed.
- **Affected tasks.** Unblocks `T02.1.2` AC1 and AC3; feeds `T02.2.1`;
  supplies what N-15 consumes.
- **Affected markers.** Closes M-18 rights half; leaves M-18b open;
  interacts with N-05's trigger 2 (K9).
- **Migration cost.** Low — `access_conditions` already exists and is already
  required and enforced-present in P1.
- **Extensibility.** Good: the rights vocabulary is closed and extensible by
  superseding record; the conduct half can be added later without disturbance.

### Option D — Enforcement at the Store's acceptance gate

- **Ownership.** Store.
- **Enforcement point.** `PROPOSED → ACTIVE`.
- **Compatibility.** **Fails K6 twice**: licence admissibility is not a
  *structural* rule, and embedding it would make the Store "a policy owner",
  which N-08 explicitly rejects. Also too late — acquisition (the external
  act) has already occurred.
- **Migration cost.** Moderate.
- **Extensibility.** Poor; corrupts the Store's non-interpretive boundary.

---

## 4. Selection

**Option C.** Justified exclusively from the corpus:

- **Minimises legal ambiguity.** K3 requires an *assessment*; K5 requires
  acquisition and retention rights to be separable. Option C records both
  explicitly per source. Options A and B leave one or both implicit.
- **Minimises coupling.** Enforcement sits in the only engine permitted to
  touch the outside world (K7/K8). Option D would couple licensing policy to
  the Store, violating K6.
- **Minimises future superseding decisions.** Option C supplies exactly what
  N-15 already declares it consumes (K4). Nothing is superseded. Option B
  would eventually force superseding N-15; Option D would force superseding
  N-08.
- **Minimises policy duplication.** One assessment, recorded once on the
  Evidence object (K1), consumed by N-15 for storage mode and by N-05's
  trigger 2 for visibility. No second copy of the policy anywhere.

---

## 5. DECISION

### 5.1 Policy ownership

**Acquisition-rights policy is owned by a named human authority outside the
platform**, consistent with N-01/Article VI: the platform "holds no budget, no
operational authority, and no accountability for consequences" (K14). The
platform **applies** the policy mechanically; it does not **decide** legality.

This mirrors N-08's ratified separation (K6): mechanism is platform-side,
policy is not.

**The platform never infers rights.** Absence of a recorded assessment is not
permission (§5.4).

### 5.2 Enforcement point

**Before acquisition, within the Research Engine** (K7, K8).

This is strictly earlier than the Store's acceptance gate. K11 and I4 make the
store immutable and non-deleting, so material admitted in error cannot be
withdrawn — only status-transitioned. Enforcement must therefore precede the
external act, not follow it.

**The Store's role is unchanged.** It continues to enforce structural rules
only (K6). This record adds no rule to V1–V12 or I1–I8.

**Gate behaviour is inherited, not defined here.** The number of
pre-acquisition gates, their evaluation order, and the halt-on-first-refusal
convention are recorded once in the source model (**N-20 §5.2.1**) and are
adopted by this record unchanged. This record defines **only** the rights gate
itself — its question, its vocabulary and its outcomes (§5.4, §5.5). It
originates no ordering and holds no copy of the sequence, so the two records
cannot drift apart. The assumptions underlying that sequence (AS-1 gate order,
AS-2 halt-on-first) are recorded in N-20 §13 and are **not** re-litigated here.

### 5.3 Definitions

| Term | Definition |
|---|---|
| **Acquisition right** | A recorded determination that identified material may be taken from an identified source at a point in time |
| **Retention right** | A recorded determination that acquired material may be *stored* by the platform, and in what form |
| **Rights assessment** | The pairing of the two above for one source, attributed to the authority that made it, with the date made |
| **Rights basis** | The externally verifiable ground cited for the assessment (e.g. the licence, terms document or grant relied upon) |

An assessment is **an input to the platform, not an output of it.**

### 5.4 Acquisition admissibility model

Acquisition proceeds **only** on an explicit, unexpired `PERMITTED`
assessment. Three outcomes, closed set:

| Outcome | Meaning | Effect |
|---|---|---|
| `PERMITTED` | Assessed and allowed | Acquisition may proceed |
| `PROHIBITED` | Assessed and disallowed | Acquisition refused |
| `UNASSESSED` | No determination exists | **Acquisition refused** |

**`UNASSESSED` fails closed.** Silence is not permission. This follows K15
(Article X: known gaps are recorded, not glossed) and from K11/I4 — an error
here is irreversible.

**Refusals are recorded, never silent** (K10): a refusal produces a failure
record distinguishing *refused on rights* from *attempted and not found*.

**Every gate must pass, and the order is fixed.** A source may be typable and
still `PROHIBITED` here; the converse also holds. The gates remain
*substantively* independent (K19) — this record decides rights and nothing
else — but they are *procedurally* ordered so that a source failing several
gates yields exactly one outcome.

**The rights gate is gate 3 of 3**, evaluated only after scope (gate 1) and
typability (gate 2), per the deterministic sequence recorded in the source
model (N-20 §5.2.1). Consequently a `REFUSED_BY_RIGHTS` outcome implies the
target was in scope and typable; rights are never assessed for material that
was already excluded. This ordering is adopted, not originated, here: it is
recorded once and referenced, so no second copy of the sequence exists to
drift.

### 5.5 Rights vocabulary — closed

Recorded in `access_conditions` (K1). Extension requires a superseding record.

**Acquisition rights**

| Value | Meaning |
|---|---|
| `PERMITTED` | Acquisition allowed under the cited basis |
| `PROHIBITED` | Acquisition not allowed |
| `UNASSESSED` | No determination made |

**Retention rights**

| Value | Meaning |
|---|---|
| `RETAIN_FULL` | Content may be stored in full |
| `RETAIN_REFERENCE_ONLY` | Only a reference may be stored |
| `RETAIN_NONE` | Nothing may be retained ⇒ acquisition refused |
| `UNASSESSED` | No determination ⇒ treated as `RETAIN_REFERENCE_ONLY` is **not** permitted; refused |

`RETAIN_NONE` and `UNASSESSED` both refuse, because K11/I4 mean any write is
effectively permanent.

Every assessment additionally records: **the authority**, **the date
assessed**, and **the rights basis** (§5.3). An assessment lacking any of
these is `UNASSESSED`.

### 5.6 Retention-rights model, and its relation to N-12

Retention **rights** (what the licence permits) are distinct from retention
**policy** (what the platform chooses to keep). K12/N-12 governs the latter by
reachability and closes M-38. **This record does not touch N-12.**

Where they interact, the **more restrictive governs**: N-12 may keep content
that rights permit; it may never keep content that rights forbid. Since
`RETAIN_NONE` refuses acquisition outright (§5.5), no object subject to it can
exist for N-12 to retain — so the two never actually conflict in a
well-formed store.

### 5.7 Interaction with N-15

N-15 declares (K4) that `T02.1.2` "determines mode at acquisition". This
record **supplies** that determination and supersedes nothing:

| Retention right | N-15 storage mode |
|---|---|
| `RETAIN_FULL` | Stored in full |
| `RETAIN_REFERENCE_ONLY` | Stored by reference |
| `RETAIN_NONE` / `UNASSESSED` | No object created |

N-15's hybrid model, its permanent retention of `content_fingerprint` and
provenance, and its recorded drift exposure are all unchanged.

### 5.8 Interaction with M-16

Independent and non-overlapping (K19). M-16 answers *what kind of source is
this, and may that kind ground the platform*. This record answers *may this
specific material be taken and kept*. A source must pass **both**.

**This record does not define, refine or depend on the source taxonomy or the
trust model.** Neither is referenced by any clause above.

### 5.9 Interaction with CI-1

Rights assessments are recorded on the **Evidence object** in
`access_conditions` — an Intelligence Object attribute (K1), not
configuration. CI-1 (K13) is therefore not engaged by the recording path.

**Constraint imposed to keep it that way:** rights values **must not**
participate in reasoning, scoring, pattern detection or lineage. They gate
acquisition and select storage mode; they contribute nothing to
`evidential_support`, confidence or pattern formation.

If a future record sites rights in a configuration store, CI-1 applies and
this clause must be revisited.

---

## 6. Consequences Accepted

1. **Coverage narrows.** B-34 states the cost plainly: *"Restricts the
   evidence base, worsening coverage (M-17) and sampling bias risk. This is a
   real quality cost that must be acknowledged, not a formality."* Accepted.
2. **`UNASSESSED` blocks acquisition**, so the platform can acquire nothing
   until a human authority supplies assessments. This is the intended
   fail-closed posture, and it means ratifying this record does **not** by
   itself make acquisition operational.
3. **Assessment correctness is outside the platform** (K3). A misassessment
   is discovered only later, and the resulting Evidence is immutable (K11).
4. **N-05 trigger 2 may fire** (K9): if licensing restricts which derived
   conclusions may be seen by whom, the deferred access-control work
   (`T09.2.2`) activates.
5. **Two independent gates** (M-16 typability, M-18 rights) must both pass.
6. **The conduct half stays open**, so nothing here constrains crawl rate or
   robots directives.

---

## 7. Compatibility Analysis

| Ratified item | Effect |
|---|---|
| **N-15** | **Supplied, not superseded** — this record provides the determination K4 requires |
| **N-08** | Unaffected — Store still structural-only; policy stays outside it |
| **N-12 / M-38** | Unaffected — retention *policy* untouched; rights are a separate, stricter bound |
| **N-10** | Used — refusals produce failure records |
| **N-05** | Trigger 2 recognised, not activated by this record alone |
| **N-01 / Art. VI** | Respected — platform applies policy, never owns legal accountability |
| **CI-1 / N-07** | Not engaged; §5.9 constrains rights from entering reasoning |
| **R-1 / I4** | Respected — fail-closed *before* the immutable write |
| **AD-01 / AD-05** | Unaffected — Evidence still originates externally |
| **M-16** | Untouched (K19) |
| **Frozen documents** | None rewritten (F5) |

**Superseded decisions: NONE.**

---

## 8. Markers Closed

| Marker | Status |
|---|---|
| **M-18 (rights half)** | **CLOSED (partially)** — legality, licensing, terms of use, retention rights: §5.1–§5.7 |

Partial closure follows ratified practice: S-05 "Closes | M-67 (partially)";
R-08 "Closes | C-04 (jointly with AD-05)".

## 9. Markers Intentionally Left Open

| Marker | Why |
|---|---|
| **M-18b (conduct half)** — robots, rate limits | Architecturally independent; zero backlog acceptance criteria depend on it. Naming it here reserves the identifier without deciding it |
| **M-16** | Source taxonomy and trust — `T02.1.1` |
| **M-17** | Coverage concept — `T02.1.4`; aggravated by §6 item 1 |
| **M-55** | Security/access-control scope — `T09.2.2`, reachable via N-05 trigger 2 |
| **M-01** | What initiates research — `T02.2.4` |

## 10. Follow-up Work

1. Record the M-18 / M-18b split in `marker-crosswalk.md` (governance
   artefact, not frozen — F5 respected), preserving its §5 uniqueness
   invariant.
2. Name the human authority required by §5.1 — **this record does not name
   it**, and acquisition cannot begin until it exists.
3. `T02.1.2` AC2 note: `access_conditions` is already required and enforced
   present by ratified P1 work; this record supplies its *vocabulary*.
4. Decide whether M-18b is scheduled or deferred.

## 11. Revisit Conditions

- Coverage loss from §6 item 1 proves severe enough to threaten M-17.
- N-05 trigger 2 fires and access control changes where rights must be held.
- A jurisdiction requires a rights value the closed vocabulary cannot express.
- **Not** grounds for revisit: the inconvenience of `UNASSESSED` refusing.

---

## 12. Consistency Challenge

I attacked this draft against every constraint K1–K19.

| Attack | Result |
|---|---|
| Violates K6 (Store structural-only)? | **No** — enforcement is in Research, pre-acquisition; no rule added to V1–V12/I1–I8 |
| Violates K4 (N-15 needs the determination)? | **No** — §5.7 supplies exactly it |
| Contradicts K12/N-12 (retention policy)? | **No** — §5.6 separates rights from policy; more-restrictive-governs, and `RETAIN_NONE` prevents the object existing |
| Violates K13/CI-1? | **No** — recorded on an Intelligence Object; §5.9 forbids entry into reasoning |
| Violates K14/Art. VI (no operational authority)? | **No** — §5.1 places legal accountability outside the platform |
| Violates K18/F8 (fixed counts)? | **No** — no engine, object or stage added |
| Violates K19 (M-16 separation)? | **No** — §5.8; no clause references taxonomy or trust |
| Violates K11/I4 (immutability)? | **No** — it *relies* on them: fail-closed precedes the write |
| Violates K10 (no silent rejection)? | **No** — §5.4 mandates failure records |
| Violates K15/Art. X? | **No** — `UNASSESSED` is recorded as a known gap, not hidden |
| Violates K16/Art. XI precedence? | **No** — nothing here outranks the Constitution |
| Violates K17? | **No** — closure is by this register record, not by code |

**One residual tension, reported not resolved.** v2 §14 X14 names the gap
*"Legal **and compliance** in acquisition"*, while §13 names *"Legal,
licensing, rate-limit, terms-of-use"*. Whether **compliance** (broader
regulatory obligations) is inside M-18 is not stated anywhere. This record
addresses the §13 enumeration. If a ratifier reads *compliance* as in scope,
M-18 is **not** fully closed even for the rights half. **Flagged, not
decided.**

**Why the draft survives.** Every clause either (a) supplies something a
ratified decision already declares it consumes (N-15, K4), (b) reuses an
existing ratified attribute and authority (K1, K7, K8), or (c) fails closed
where the corpus is silent. No clause creates authority, and none introduces a
requirement absent from K1–K19.

---

## 13. Honest Limitations

- **The legal content is not architectural.** §5.5's vocabulary is a
  *structure* for recording determinations; it does not encode what is lawful.
  If a ratifier expects M-18 closure to make acquisition legally safe, this
  record does not deliver that and cannot.
- **§5.1 names no authority.** Deliberate — naming one is an organisational
  decision, not an architectural one. But it means ratification alone does not
  unblock acquisition (§6 item 2).
- **The rights/conduct split is analysis, not corpus text.** It is grounded in
  N-15's pairing of licensing with retention and the absence of any ratified
  robots/retention pairing, but the corpus never states the taxonomy.
- **`UNASSESSED` is strict.** A ratifier may reasonably prefer a
  provisional-acquisition posture. I chose fail-closed because K11/I4 make
  the error irreversible, but this is the clause most likely to be contested.
- **The v2 §14 / v2 §13 "compliance" discrepancy** may mean this record closes less
  than it claims.

---

**Status: `RATIFIED` 2026-08-04 by the Project Owner, with recorded reservations.**
