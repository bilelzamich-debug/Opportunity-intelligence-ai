# Specifications

Written specifications produced **before** implementation, per the working
method's step 1: *extract, never recall*.

| File | Task |
|---|---|
| `T01.2.5-specification.md` | Retention / ARCHIVED tiering |
| `T01.5.5-specification.md` | Calibration rubric |
| `T01.6.2-specification.md` | Sequencing |
| `T01.6.3-specification.md` | Failure surfacing |
| `T01.6.4-specification.md` | Concurrency boundary |
| `T01.6.5-specification.md` | Processing state |
| `T02.1.1-specification.md` | Source model — **blocking escalation** |

---

## Structure

Each specification lists, before any code is written:

- governing sources, with line references
- constraints
- open markers
- ambiguities
- assumptions — and any assumption not directly supported by a ratified source
  **must fail closed**

## Why These Exist

`T02.1.1-specification.md` is the clearest case. Rather than implementing a
source taxonomy, it proved M-16 genuinely open and escalated — with the
exhaustive extraction that made the escalation binding rather than an opinion.

Had the task been implemented instead, an invented eight-member taxonomy would
have entered the codebase with no record of where it came from. That is exactly
the M-50 failure the project exists to avoid repeating.
