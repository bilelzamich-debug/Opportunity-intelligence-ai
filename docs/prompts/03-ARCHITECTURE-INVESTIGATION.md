# Prompt — Architecture Investigation

Use this when a task appears blocked by an undefined specification.

---

```
Perform a first-principles architectural investigation of <MARKER>.

Do NOT implement production code.
Do NOT draft architecture.
Do NOT invent policy.
Do NOT close any marker.

Required work:

1. Verify independently whether <MARKER> is actually unresolved.
   - Search every ratified source.
   - Search every decision record.
   - Search the crosswalk.
   - Search all specifications.
   - Search the backlog.
   - Search historical documents.
   - Do not trust previous reports.

2. Determine whether a ratified decision already defines <the required items>.

3. Produce a dependency graph showing:
   - every ratified decision depending on <MARKER>
   - every task blocked directly
   - every task blocked transitively
   - every architectural marker interacting with <MARKER>

4. Attempt to prove your own conclusion wrong. Specifically attack:
   - <MARKER> is already implicitly closed
   - some other decision already defines it
   - an implementation artefact accidentally became architecture
   - precedent, crosswalk, frozen wording, or backlog wording resolves it

   Try to falsify every claim.

5. If <MARKER> remains open, provide a formal proof of underdetermination.
   Show exactly which information is missing. Separate:
   - facts
   - deductions
   - assumptions
   - unresolved questions

6. If you discover inconsistencies between IOM, PKP v2, decision records,
   crosswalk or backlog: identify them precisely but DO NOT resolve them.

7. Report: acceptance criteria status, dependency analysis, architectural
   conflicts, hidden assumptions, blocker severity, honest limitations,
   final verdict.

Stop immediately after the investigation.
```

---

## The Underdetermination Proof Pattern

Formalise the required artefact as a function. Then:

1. List every ratified constraint that mentions it.
2. Show what each constraint actually requires (usually: *count* or *partition*).
3. Exhibit ≥2 non-isomorphic witnesses satisfying all constraints.
4. Search for any predicate that discriminates between the witnesses.
5. If none exists, the specification does not determine the artefact. **QED.**

This pattern proved M-16 underdetermined with three witnesses (`{EXTERNAL}`,
`{HUMAN, MACHINE}`, `{A,B,C,D}`) — none excluded by any ratified statement.
