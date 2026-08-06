# Reasoning Records

How key conclusions were reached — **including conclusions later found wrong.**

Preserved because the errors are more instructive than the successes, and
because Constitution Article X requires the project to apply its own honesty
standard to its own reasoning.

---

## 1. The Cascade Defect — a three-stage reachability argument

**Stage 1 — Reproduce.** An adversarial probe built an uneven-depth diamond and
showed a dependent left `ACTIVE` with all upstreams withdrawn. 4 of 9 probes
failed.

**Stage 2 — Prove it uses legal objects.** The first probe wrote directly to
the store, bypassing typed paths. Six of eight derived types enforce a single
upstream type — so if *all* did, BFS depth would equal pipeline stage and the
ordering would be topological, making the defect unreachable.

**`Validation` does not.** IOM §3.7: *"DERIVES_FROM the object containing the
tested claim"*, and IOM types `DERIVES_FROM` as `any → any`.

**Stage 3 — Prove it survives the production API.** Reproduced through
`store.write_validation()` — the object passed V1–V12, I1–I8 and V-V1…V-V6.

> **The lesson.** A defect that fails any stage is a test artefact, not a
> defect. Reporting stage 1 alone would have been premature.

---

## 2. Errors I Made and Caught

### 2.1 Under-counting the M-16 blast radius — twice

| Report | Claim | Truth |
|---|---|---|
| Proposal | "S-02 and N-16 depend on M-16" | **Four** decisions (add N-3, S-5) |
| Challenge | "four ratified decisions" | **Seven** including transitive (S-1, S-4) |
| Investigation | "seven affected tasks" | **94** transitively blocked |

Each correction came from re-deriving rather than trusting the previous
report. **Every error under-stated severity.**

### 2.2 Overstating an authority

I wrote that the trust range `[0.0, 1.0]` was *"inherited from the ratified
Evidence contract."* Precisely: that range lives in `oip/evidence.py`, a **P1
implementation artefact**. The IOM annotates the attribute "(OQ-28)" and states
no range. A defensible storage convention — but not a ratified fact.

### 2.3 Ten verifier failures that were all my errors

On first execution of the Phase-2 closure verifier, 10 checks failed. **All ten
were checker defects**, not code defects:

| Failure | Cause |
|---|---|
| `evidence_reachable_from` ×2 | Invented method; real API is `evidence_set` / `reaches_evidence` |
| `band_for` | Invented; real API is `criterion_for_value` |
| `RetentionPolicy(graph=…)`, `may_archive` | Wrong signature and method |
| `except Exception` | Code uses the stricter `except BaseException` |
| "28 modules" → 27 | `MODULES` excludes `__init__.py` by design |
| `configuration:no-task` | Header reads `Tasks:` (plural) — it implements two |
| **M-36 / OQ-11 "closed"** | **Regex matched prose documenting the markers as OPEN** |
| ExecutionRecord V7 rejection | Correct fail-closed behaviour under open C-02 |

> Had I assumed the code was wrong, I would have "fixed" working production
> code. The M-36/OQ-11 regexes are the sharpest case: they asserted the exact
> opposite of their intent.

### 2.4 Two self-inflicted tooling incidents

**Killing a mutation run left mutated source in place** — twice. This produced
a phantom infinite-loop "hang" I initially mistook for a production defect, and
an orphaned process that corrupted a benchmark run (7 false regressions).

Root cause: `kill -9` on a mutation harness mid-run. The harness restores
sources in a `finally` block that never executed.

### 2.5 Six broken cross-references I introduced

Four in N-21 (`§6.1`, `§6.2`, `§14`) and two in N-22 (`§11.3`, `§12.3`) —
pointing at sections that do not exist. **They survived an ARB coherence review
and a Revision-2 validation** before a mechanical reference check caught them.

> The lesson is about *method*, not carelessness: no earlier pass validated
> cross-reference resolution mechanically. Structural checks belong in every
> pass, not only the last.

---

## 3. Conclusions That Survived Attack

### 3.1 M-16 is genuinely open

Attacked seven ways: hidden ratified decision · indirect derivation ·
implementation artefact · precedent · crosswalk · frozen IOM wording · backlog
wording. **All seven failed.** The challenge also found three ratified
statements that make the blocker *stronger*.

### 3.2 S-2 blocks trust from scoring

Attacked by asking whether input 2 ("source diversity") subsumes trust. It does
not — input 2 counts *types*; P3 is cardinality. Neither concerns source
*quality*.

**Then a genuine conflict surfaced:** IOM §3.1 says `evidential_support`
*"reflects source reliability"* — the opposite of S-2. Resolved by Article XI
precedence (decision records outrank the IOM), and by noting the IOM sentence
self-hedges ("OQ-28 unresolved", "a strong unstated assumption"). It states
**intent**; S-2 states the **contract**.

### 3.3 D-1 is a real contradiction

`T02.2.4` AC2 requires "approval per human-gate decision". N-2 fixes **exactly
three gates**, none covering research targets. Under Article XI, N-2 governs
and the AC is unsatisfiable as written.

Attacked by checking whether B-59 (which recommends "targets surfaced for
approval") carries authority. It does not — *"No decision herein is ratified."*

---

## 4. Where Prior Reports Were Treated as Untrusted — and Should Have Been

| Occasion | Outcome |
|---|---|
| T01.8.1 gate re-run | Found the T01.2.4 partial-retraction defect in a task marked complete |
| T01.8.1 final gate | Found the cascade BFS defect after two prior gates passed |
| Phase 2 dependency reconstruction | Found **M-01** — a fourth blocker three prior analyses had missed |
| Revision 2 validation | Found A2/A6 were **new architecture**, not derivations |
| Cross-reference audit | Found 6 broken references two reviews had missed |

**In every case, re-deriving from scratch found something trusting would have
missed.**
