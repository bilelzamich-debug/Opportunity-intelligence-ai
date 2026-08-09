"""Mutation testing for T01.6.3 failure surfacing.

Every rule introduced by this task is broken in turn; the suite must fail.
Sources are restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = ROOT / "oip" / "orchestration.py"
ACC = ROOT / "oip" / "acceptance.py"
CFG = ROOT / "oip" / "configuration.py"
TARGETS = [ORCH, ACC, CFG]

# (label, file, find, replace)
MUTATIONS = [
    # -- AC1: failed vs empty ------------------------------------------
    (
        "M1 failed_invocations also reports empty",
        ORCH,
        "if r.outcome is InvocationOutcome.FAILED\n        )",
        "if r.outcome in (InvocationOutcome.FAILED, InvocationOutcome.EMPTY)\n        )",
    ),
    (
        "M2 empty_invocations also reports failed",
        ORCH,
        "if r.outcome is InvocationOutcome.EMPTY\n        )",
        "if r.outcome in (InvocationOutcome.EMPTY, InvocationOutcome.FAILED)\n        )",
    ),
    # -- never masked ---------------------------------------------------
    (
        "M3 masked_cycles reports nothing",
        ORCH,
        "if c.had_failure and c.outcome is CycleOutcome.COMPLETED",
        "if False",
    ),
    (
        "M4 assert_not_masked never raises",
        ORCH,
        "masked = self.masked_cycles()\n        if masked:",
        "masked = self.masked_cycles()\n        if False:",
    ),
    (
        "M5 masked check reads the outcome instead of the invocations",
        ORCH,
        "return tuple(c for c in self.cycles if c.had_failure)",
        "return tuple(c for c in self.cycles if c.outcome is CycleOutcome.FAILED)",
    ),
    # -- AC2: does not halt ---------------------------------------------
    (
        "M6 halted_at_failure ignores unreached work",
        ORCH,
        "and cycle.not_attempted_count > 0",
        "and cycle.not_attempted_count >= 0",
    ),
    (
        "M7 engine failure aborts the cycle (breaks continue-past-failure)",
        ORCH,
        "except BaseException as exc:  # engine failure is data, not an escape",
        "except BaseException as exc:  # MUTANT\n            raise",
    ),
    # -- defect 1: hostile exception rendering ---------------------------
    (
        "M8 detail built with a naive f-string again",
        ORCH,
        "detail = _describe_exception(exc)",
        'detail = f"{type(exc).__name__}: {exc}"',
    ),
    (
        "M9 _describe_exception no longer guards str()",
        ORCH,
        "    try:\n        message = str(exc)\n    except BaseException as inner:",
        "    message = str(exc)\n    if False:\n      try:\n        pass\n      except BaseException as inner:",
    ),
    (
        "M10 control signals swallowed as engine failures",
        ORCH,
        "except (KeyboardInterrupt, SystemExit):\n            # NOT an engine failure.",
        "except (KeyboardInterrupt, SystemExit) if False else ():\n            # NOT an engine failure.",
    ),
    # -- defect 2: hostile failure store ---------------------------------
    (
        "M11 store fault propagates and destroys the cycle again",
        ORCH,
        "            try:\n                self.failure_store.record(record)\n            except (KeyboardInterrupt, SystemExit):",
        "            self.failure_store.record(record)\n            if False:\n              try:\n                pass\n              except (KeyboardInterrupt, SystemExit):",
    ),
    (
        "M12 store fault silently swallowed, never recorded",
        ORCH,
        "                self._store_faults.append(",
        "                [].append(",
    ),
    (
        "M13 store faults never reach the cycle record",
        ORCH,
        "        failures.extend(self._store_faults)",
        "        pass",
    ),
    (
        "M14 store faults leak between cycles",
        ORCH,
        "        attempted = 0\n        self._store_faults = []",
        "        attempted = 0",
    ),
    # -- N-10 attribution ------------------------------------------------
    (
        "M15 engine attribution dropped",
        ORCH,
        "            engine=item.engine,\n            cycle_id=cycle_id,",
        "            engine=None,\n            cycle_id=cycle_id,",
    ),
    (
        "M16 attempted inputs dropped again",
        ORCH,
        "            invocation_index=invocation_index,\n            input_ids=item.input_ids,\n        )",
        "            invocation_index=invocation_index,\n            input_ids=(),\n        )",
    ),
    (
        "M17 invocation index always zero",
        ORCH,
        "self._invoke(item, failures, cycle_id, len(invocations))",
        "self._invoke(item, failures, cycle_id, 0)",
    ),
    (
        "M18 satisfies_n10_attribution always true",
        ACC,
        "        return (\n            self.engine is not None\n            and self.is_attributable_to_invocation",
        "        return True or (\n            self.engine is not None\n            and self.is_attributable_to_invocation",
    ),
    (
        "M19 attribution ignores inputs attempted",
        ACC,
        "            and bool(self.input_ids)\n            and bool(self.engine_configuration_ref)",
        "            and bool(self.engine_configuration_ref)",
    ),
    (
        "M20 bare-string input_ids accepted on a failure record",
        ACC,
        "        if isinstance(self.input_ids, (str, bytes)):\n            raise ValueError(",
        "        if False:\n            raise ValueError(",
    ),
    (
        "M21 non-Engine accepted on a failure record",
        ACC,
        "        if self.engine is not None and not isinstance(self.engine, Engine):\n            raise ValueError(",
        "        if False:\n            raise ValueError(",
    ),
    (
        "M22 unattributed() reports nothing",
        CFG,
        "                r for r in self._records if not r.satisfies_n10_attribution",
        "                r for r in self._records if False",
    ),
    (
        "M23 for_engine ignores the engine",
        CFG,
        "            return tuple(r for r in self._records if r.engine is engine)",
        "            return tuple(self._records)",
    ),
    (
        "M24 unattributed_failures on the surface reports nothing",
        ORCH,
        "            f for f in self.failure_records()\n            if not f.satisfies_n10_attribution",
        "            f for f in self.failure_records()\n            if False",
    ),
    # -- fail-closed guards ---------------------------------------------
    (
        "M25 surface accepts non-CycleRecord input",
        ORCH,
        "            if not isinstance(cycle, CycleRecord):\n                raise OrchestrationError(",
        "            if False:\n                raise OrchestrationError(",
    ),
    (
        "M26 consecutive_failures never resets",
        ORCH,
        "            if cycle.had_failure:\n                streak += 1\n            else:\n                break",
        "            if cycle.had_failure:\n                streak += 1",
    ),
    (
        "M27 every_failure_is_visible always true",
        ORCH,
        "        return counted == self.failed_count",
        "        return True",
    ),
]


def run_suite() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_failure_surfacing.py", "tests/test_orchestration.py",
         "tests/test_processing_state.py", "tests/test_acceptance.py",
         "tests/test_lifecycle_config_support.py"],
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
