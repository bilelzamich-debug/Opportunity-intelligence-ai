"""Mutation testing for T01.6.4 concurrency boundary.

Every rule introduced by this task is broken in turn; the suite must fail.
Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "oip" / "orchestration.py"
ENUMS = ROOT / "oip" / "enums.py"
TARGETS = [ORCH, ENUMS]

MUTATIONS = [
    # -- the N-11 boundary itself ---------------------------------------
    (
        "M1 boundary moved: stage 3 becomes concurrent",
        ENUMS,
        "CONCURRENT_STAGES: frozenset[int] = frozenset({1, 2})",
        "CONCURRENT_STAGES: frozenset[int] = frozenset({1, 2, 3})",
    ),
    (
        "M2 boundary moved: stage 2 becomes serialised",
        ENUMS,
        "CONCURRENT_STAGES: frozenset[int] = frozenset({1, 2})",
        "CONCURRENT_STAGES: frozenset[int] = frozenset({1})",
    ),
    (
        "M3 everything concurrent",
        ENUMS,
        "CONCURRENT_STAGES: frozenset[int] = frozenset({1, 2})",
        "CONCURRENT_STAGES: frozenset[int] = frozenset(range(1, 10))",
    ),
    (
        "M4 engine stage map corrupted (Pattern -> stage 1)",
        ENUMS,
        "Engine.PATTERN_INTELLIGENCE: 4,",
        "Engine.PATTERN_INTELLIGENCE: 1,",
    ),
    (
        "M5 Orchestration given a stage",
        ENUMS,
        "    Engine.FEEDBACK: 9,\n}",
        "    Engine.FEEDBACK: 9,\n    Engine.ORCHESTRATION: 1,\n}",
    ),
    (
        "M6 for_stage always concurrent",
        ORCH,
        "        if stage in CONCURRENT_STAGES:\n            return cls.CONCURRENT\n        return cls.SERIALISED",
        "        return cls.CONCURRENT",
    ),
    (
        "M7 for_stage always serialised",
        ORCH,
        "        if stage in CONCURRENT_STAGES:\n            return cls.CONCURRENT\n        return cls.SERIALISED",
        "        return cls.SERIALISED",
    ),
    # -- stage resolution -------------------------------------------------
    (
        "M8 produces no longer governs the stage",
        ORCH,
        "        if self.produces is not None:\n            return self.produces.stage",
        "        if False:\n            return self.produces.stage",
    ),
    (
        "M9 unclassifiable engine silently defaults instead of failing closed",
        ORCH,
        "        stage = ENGINE_STAGE.get(self.engine)\n        if stage is None:\n            raise ConcurrencyError(",
        "        stage = ENGINE_STAGE.get(self.engine, 1)\n        if False:\n            raise ConcurrencyError(",
    ),
    # -- phase planning ---------------------------------------------------
    (
        "M10 serialised items batched together",
        ORCH,
        "            phases.append(\n                ExecutionPhase(ConcurrencyClass.SERIALISED, (index,))\n            )",
        "            run.append(index)",
    ),
    (
        "M11 trailing concurrent run dropped",
        ORCH,
        "        if run:\n            phases.append(\n                ExecutionPhase(ConcurrencyClass.CONCURRENT, tuple(run))\n            )\n        return tuple(phases)",
        "        return tuple(phases)",
    ),
    (
        "M12 barrier removed: concurrent run not flushed before a serialised item",
        ORCH,
        "            if run:\n                phases.append(\n                    ExecutionPhase(ConcurrencyClass.CONCURRENT, tuple(run))\n                )\n                run = []",
        "            pass",
    ),
    (
        "M13 serialised phase may hold many items",
        ORCH,
        "        if (\n            self.concurrency_class is ConcurrencyClass.SERIALISED\n            and len(self.item_indices) != 1\n        ):\n            raise ConcurrencyError(",
        "        if False:\n            raise ConcurrencyError(",
    ),
    (
        "M14 empty phase permitted",
        ORCH,
        '        if not self.item_indices:\n            raise ConcurrencyError("an execution phase may not be empty")',
        '        if False:\n            raise ConcurrencyError("an execution phase may not be empty")',
    ),
    # -- the executor -----------------------------------------------------
    (
        "M15 serialised phases dispatched in parallel too",
        ORCH,
        "            if phase.is_parallel and len(admitted) > 1:",
        "            if len(admitted) > 1:",
    ),
    (
        "M16 results written back out of order (nondeterministic record)",
        ORCH,
        "        for index in phase.item_indices:\n            slots[index] = collected[index]",
        "        for slot, index in zip(sorted(phase.item_indices, reverse=True),\n                               phase.item_indices):\n            slots[slot] = collected[index]",
    ),
    (
        "M17 parallel failures dropped",
        ORCH,
        "        failures.extend(local_failures)",
        "        pass",
    ),
    (
        "M18 worker results not guarded by the lock",
        ORCH,
        "            with guard:\n                collected[index] = record\n                local_failures.extend(own)",
        "            collected[index] = record\n            local_failures.extend(own)\n            del own",
    ),
    (
        "M19 concurrent phase refused whole when over budget (the fixed defect)",
        ORCH,
        "            admitted = phase.item_indices[:remaining]",
        "            admitted = phase.item_indices if len(phase) <= remaining else ()",
    ),
    (
        "M20 work limit ignored on the parallel path",
        ORCH,
        "            remaining = bounds.max_work_items - attempted\n            if remaining <= 0:",
        "            remaining = 10 ** 9\n            if False:",
    ),
    (
        "M21 budget ignored on the parallel path",
        ORCH,
        "            if elapsed >= bounds.wall_clock_budget_seconds:\n                outcome = CycleOutcome.BUDGET_EXHAUSTED\n                stopped = True\n                break",
        "            if False:\n                outcome = CycleOutcome.BUDGET_EXHAUSTED\n                stopped = True\n                break",
    ),
    (
        "M22 unattempted work not recorded on the parallel path",
        ORCH,
        "            invocations.extend(self._not_attempted(unreached, started_at))",
        "            pass",
    ),
    (
        "M23 max_workers validation removed",
        ORCH,
        "        if self.max_workers < 1:\n            raise ConcurrencyError(",
        "        if False:\n            raise ConcurrencyError(",
    ),
    (
        "M24 max_workers type check removed",
        ORCH,
        "        if isinstance(self.max_workers, bool) or not isinstance(\n            self.max_workers, int\n        ):\n            raise ConcurrencyError(",
        "        if False:\n            raise ConcurrencyError(",
    ),
    (
        "M25 default max_workers silently raised (M-56 invented bound)",
        ORCH,
        "    max_workers: int = 1",
        "    max_workers: int = 8",
    ),
    # -- the verifier -----------------------------------------------------
    (
        "M26 overlap test never fires",
        ORCH,
        "        return a.started_at < b.ended_at and b.started_at < a.ended_at",
        "        return False",
    ),
    (
        "M27 serialisation violations never reported",
        ORCH,
        "            for i, a in enumerate(records)\n            for b in records[i + 1:]\n            if self._overlaps(a, b)\n        )",
        "            for i, a in enumerate(records)\n            for b in records[i + 1:]\n            if False\n        )",
    ),
    (
        "M28 barrier violations never reported",
        ORCH,
        "            for s in self.serialised_records()\n            for c in self.concurrent_records()\n            if self._overlaps(c, s)",
        "            for s in self.serialised_records()\n            for c in self.concurrent_records()\n            if False",
    ),
    (
        "M29 same-engine writers never reported",
        ORCH,
        "            if a.engine is b.engine and self._overlaps(a, b)",
        "            if False",
    ),
    (
        "M30 assert_holds never raises",
        ORCH,
        "        if problems:\n            raise ConcurrencyViolation(",
        "        if False:\n            raise ConcurrencyViolation(",
    ),
    (
        "M31 verifier counts unattempted invocations",
        ORCH,
        "        return tuple(r for r in self.cycle.invocations if r.attempted)",
        "        return tuple(self.cycle.invocations)",
    ),
    (
        "M32 verifier accepts a non-CycleRecord",
        ORCH,
        "        if not isinstance(self.cycle, CycleRecord):\n            raise ConcurrencyError(",
        "        if False:\n            raise ConcurrencyError(",
    ),
]


def run_suite() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_concurrency_boundary.py", "tests/test_orchestration.py",
         "tests/test_processing_state.py", "tests/test_failure_surfacing.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode == 0


def main() -> int:
    originals = {p: p.read_text() for p in TARGETS}
    backups = {p: ROOT / "validation" / f".{p.name}.orig" for p in TARGETS}
    for p in TARGETS:
        shutil.copy2(p, backups[p])

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        for p in TARGETS:
            p.write_text(originals[p])
        return 1
    print("pass")

    survivors, killed, inapplicable = [], [], []
    for label, path, find, replace in MUTATIONS:
        original = originals[path]
        if find not in original:
            inapplicable.append(label)
            print(f"  ??  {label}: pattern not found")
            continue
        path.write_text(original.replace(find, replace, 1))
        if run_suite():
            survivors.append(label)
            print(f"  SURVIVED  {label}")
        else:
            killed.append(label)
            print(f"  killed    {label}")
        path.write_text(original)

    for p in TARGETS:
        p.write_text(originals[p])

    identical = True
    for p in TARGETS:
        diff = subprocess.run(["diff", "-q", str(p), str(backups[p])],
                              capture_output=True, text=True)
        if diff.returncode != 0:
            identical = False
            print(f"  RESTORE MISMATCH: {p.name}")
        backups[p].unlink()

    print(f"\nkilled {len(killed)}/{len(MUTATIONS)}; survivors {len(survivors)}; "
          f"inapplicable {len(inapplicable)}")
    print(f"sources restored byte-identical: {identical}")
    if survivors or inapplicable or not identical:
        for s in survivors:
            print("  SURVIVOR:", s)
        for s in inapplicable:
            print("  INAPPLICABLE:", s)
        return 1
    print("all mutations killed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
