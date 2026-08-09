# Prompt — Task Execution

Use this to execute a single backlog task.

---

```
Execute <TASK-ID> — <title>.

Working Method (mandatory)

Before writing or modifying any code:

1. Extract every governing requirement from the ratified architecture.
2. Produce a complete written specification.
3. List:
   - governing sources
   - constraints
   - open markers
   - ambiguities
   - assumptions (if any)
4. Any assumption not directly supported by a ratified source must fail closed.

Never reuse previous conclusions.
Treat every completed task as untrusted until independently re-verified.

Required Work

1. Search aggressively for implementation defects by adversarial probing
   BEFORE writing tests.
2. Implement only <TASK-ID>. Do not begin the next task.
3. Produce:
   - production implementation
   - complete property-based tests
   - stress tests
   - mutation tests
   - validation scripts
   - acceptance verification
   - architecture verification where required
4. Verify every acceptance criterion independently.
5. Execute the complete validation battery:
   - unit tests
   - property tests
   - stress tests
   - mutation testing
   - coverage
   - performance where applicable
   - architectural verification

Rules

- No architectural invention.
- No hidden assumptions.
- No speculative fixes.
- No silent repairs.
- No weakening of tests.
- No skipping validation.
- Fail closed.
- Stop immediately after discovering any new production defect.
- If a production defect is fixed, stop after validating that fix and report
  the new state without continuing.

Produce only the standard completion report (11 sections).
Stop immediately after the named task.
```

---

## Notes

**"Treat every completed task as untrusted"** is load-bearing. The Phase 1 exit
gate found a defect in `T01.2.4` — a task marked complete — precisely because
it re-verified rather than trusted.

**"Adversarial probing BEFORE writing tests"** is the single highest-yield
step. Tests written first tend to encode the implementation's own assumptions.
