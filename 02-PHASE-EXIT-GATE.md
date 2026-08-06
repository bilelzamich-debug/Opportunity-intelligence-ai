# Prompt — Phase Exit Gate

Use this to close a phase. This is **not** an implementation task.

---

```
You are executing <GATE-TASK-ID> — Phase <N> Exit Gate.

This is an independent verification of the entire phase.
The purpose is to determine whether Phase <N> may be formally closed.

Working Method (mandatory)

1. Extract every governing requirement from the ratified architecture.
2. Produce a complete written specification.
3. List governing sources, constraints, open markers, ambiguities, assumptions.
4. Any assumption not directly supported by a ratified source must fail closed.

Never reuse previous conclusions.
Treat every completed task as untrusted until independently re-verified.

Required Verification

A. Backlog Completion — all tasks, features, deliverables, acceptance criteria.

B. Functional Verification — object model, lifecycle, lineage, graph,
   confidence, calibration, orchestration, acceptance, semantic validation,
   integrity, configuration separation, cascade, retention, partial retraction,
   sequencing, reachability, architecture constraints.

C. Previous Technical Debt — verify that previously discovered defects are
   actually resolved. Do not trust previous reports. Re-test them.

D. Tests — full suite, stress suite, mutation suite, architecture verifiers,
   property tests, concurrency tests. If production code changed since the
   previous gate: re-run coverage, mutation and benchmarks. Do not reuse
   previous metrics.

E. Architectural Integrity — no forbidden dependency, DAG layering, public API
   compatibility, object model consistency, lifecycle correctness, confidence
   correctness, calibration correctness, orchestration boundaries, cascade
   boundaries, retention boundaries, configuration isolation.

F. Open Markers — verify that all intentionally open markers remain open.
   Do not close <list> unless explicitly ratified.

G. Phase Closure Decision — if every verification passes, approve. Otherwise,
   refuse closure.

Produce only the exit-gate report (11 sections).
Stop immediately after issuing the closure decision.
```

---

## Notes

**The T01.8.1 gate ran three times.** The first two halted on defects that all
prior validation had missed. A gate that has passed twice can still be wrong.

**"Do not reuse previous metrics"** matters. Coverage and mutation figures from
before a code change are not evidence about the code after it.
