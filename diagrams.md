# Diagrams

All diagrams in Markdown/ASCII so they diff cleanly in review.

---

## 1. The Pipeline — ten stages

```
                    ┌──────────────────────────────────────────┐
                    │            ORCHESTRATION (stage 10)      │
                    │  scheduled batch · directive · bounded   │
                    └──────────────────────────────────────────┘
                                       │ invokes
   ┌───────────────────────────────────┼───────────────────────────────────┐
   ▼                                   ▼                                   ▼
┌──────────┐   ┌──────┐   ┌─────────┐   ┌─────────┐   ┌─────────────┐
│1 EVIDENCE│──▶│2 FACT│──▶│3 PROBLEM│──▶│4 PATTERN│──▶│5 OPPORTUNITY│
└──────────┘   └──────┘   └─────────┘   └─────────┘   └─────────────┘
   ▲ external                                              │  ▲
   │ world                                                 ▼  │ G1 human gate
   │                                                 ┌──────────┐
   │                                                 │6 SOLUTION│
   │                                                 └──────────┘
   │                                                       │
   │                                                       ▼  ◀── G2 human gate
   │                                                ┌────────────┐
   │                                                │7 VALIDATION│──▶ HANDOFF
   │                                                └────────────┘    (N-1)
   │                                                       │
   │                                                       ▼
   │                                              ┌──────────────────┐
   │                                              │8 EXECUTION RECORD│  ← C-02:
   │                                              └──────────────────┘    no engine
   │                                                       │
   │                                                       ▼  ◀── G3 human gate
   │                                              ┌─────────────────┐
   └──── research directive (NEVER lineage) ──────│9 FEEDBACK RECORD│
              R-8 · AD-05                         └─────────────────┘
```

---

## 2. Object Lifecycle — seven states (R-2)

```
   PROPOSED ──accept──▶ ACTIVE ──supersede──▶ SUPERSEDED  (terminal)
      │                   │
      │ reject            ├── retract ──────▶ RETRACTED   (terminal)
      ▼                   ├── upstream ─────▶ INVALIDATED (terminal)
   REJECTED               └── retention ────▶ ARCHIVED    (terminal)
   (terminal)

   I5: exactly one ACTIVE per lineage_id
   E-V1: Evidence can NEVER reach INVALIDATED
   Cascade triggers: RETRACTED, INVALIDATED only (SUPERSEDED does not — M-65)
```

---

## 3. Directive Lifecycle (N-23) — disjoint from R-2

```
   RAISED ──▶ IN_EFFECT ──▶ FULFILLED
      │           │
      │           ├──▶ CANCELLED
      └───────────┴──▶ EXPIRED

   Token disjointness is deliberate: no directive state name collides with
   any of R-2's seven object states.
```

---

## 4. Module Dependency Graph — a DAG

```
enums ─┬─▶ contract ─┬─▶ acceptance ─┬─▶ store ◀── SOLE broad integrator (≥15)
       │             │               │
       ├─▶ identity  ├─▶ lineage     ├─▶ integrity
       ├─▶ lifecycle ├─▶ graph       ├─▶ cascade
       │                             └─▶ evidence · fact · problem · pattern
       │                                 opportunity · solution · validation
       │                                 execution · feedback
       │
       ├─▶ calibration      (enums only)          ─┐
       ├─▶ retention        (enums + graph)        ├─ CI-1 boundary modules
       └─▶ orchestration    (acceptance+contract+enums)
                                                   │
contract ──▶ source  (Phase 2 — imports oip.contract only) ─┘

All modules ≤6 imports except store. Verified acyclic by closure_t01_8_1.py.
```

---

## 5. Decision Dependency Graph — Phase 2

```
        N-20 (taxonomy) ──frame──────────────▶ N-22 (coverage)
             │                                      ▲
             └─gate 2──▶ N-21 (rights) ─gate 3──────┘ REFUSED_BY_RIGHTS
                                                      ▲
        N-23 (directive) ─gate 1──────────────────────┘ OUT_OF_SCOPE

  Acyclic. Only N-22 has outbound edges.
  Ratification order: N-21 → N-20 → (resolve D-1) → N-23 → N-22
```

---

## 6. The Acquisition Gate Sequence (N-20 §5.2.1)

```
   source
     │
     ▼
  ┌──────────────┐  no   ┌──────────────────┐
  │ 1. SCOPE     │──────▶│ OUT_OF_SCOPE     │  ◀── N-23
  │ in directive?│       └──────────────────┘
  └──────┬───────┘
     yes │
         ▼
  ┌──────────────┐  no   ┌──────────────────┐
  │ 2. TYPABILITY│──────▶│ UNTYPABLE_CHANNEL│  ◀── N-20  → out_of_frame register
  │ maps to type?│       └──────────────────┘
  └──────┬───────┘
     yes │
         ▼
  ┌──────────────┐  no   ┌──────────────────┐
  │ 3. RIGHTS    │──────▶│ REFUSED_BY_RIGHTS│  ◀── N-21
  │ PERMITTED?   │       └──────────────────┘
  └──────┬───────┘
     yes │
         ▼
      ACQUIRE

  HALTS AT FIRST REFUSAL → exactly one reason, always.
  (AS-1: order selected · AS-2: halt-first inverts the N-08/N-10 precedent)
```

---

## 7. Store / Graph Boundary (N-6)

```
   ┌─────────────────────┐         ┌──────────────────────┐
   │   KNOWLEDGE STORE   │         │   KNOWLEDGE GRAPH    │
   │   AUTHORITATIVE     │────────▶│   DERIVED INDEX      │
   │                     │ rebuild │                      │
   │ objects carry their │  from   │ indexes what objects │
   │ own lineage         │ objects │ already assert       │
   └─────────────────────┘         └──────────────────────┘

   "The graph can be the reason the platform is slow,
    never the reason it is wrong."
```

---

## 8. Critical Path — what blocks what

```
  D-1 resolution ──▶ T02.2.4 ──▶ T07.3.8, T08.3.4     (22 downstream tasks)

  Rights authority ──▶ T02.1.2 ──▶ T02.2.1 ─┬─▶ T02.2.2 ──▶ T02.2.3 ──┐
                                            └─▶ T02.2.5 ──────────────┤
                       T02.1.3 ──▶ T02.1.4 ──────────────────────────┤
                                                                      ▼
                                                                 T02.3.1
                                                                      │
                                                                      ▼
                                                          T03.1.1 ──▶ P3…P9
```

---

## 9. Confidence Flow

```
  Evidence            effective = 0.55  ← sets the ceiling, unconstrained above
     │
     ▼  ceiling = min(upstream) = 0.55
  Fact                asserted 0.80 → CAPPED to 0.55       (V5)
     │
     ▼  ceiling = 0.55
  Problem             asserted 0.70 → CAPPED to 0.55
     │
     ▼
  ... certainty never increases with distance from observation (Article X)
```
