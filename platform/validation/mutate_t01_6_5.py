"""Mutation testing for T01.6.5 sequencing enforcement.

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
    # -- the N-14 mapping ------------------------------------------------
    (
        "M1 mapping corrupted: Fact Extraction consumes Facts",
        ENUMS,
        "    Engine.FACT_EXTRACTION: ObjectType.EVIDENCE,",
        "    Engine.FACT_EXTRACTION: ObjectType.FACT,",
    ),
    (
        "M2 mapping corrupted: Validation consumes Opportunities",
        ENUMS,
        "    Engine.VALIDATION: ObjectType.SOLUTION,",
        "    Engine.VALIDATION: ObjectType.OPPORTUNITY,",
    ),
    (
        "M3 Feedback loses its ExecutionRecord input",
        ENUMS,
        "    Engine.FEEDBACK: ObjectType.EXECUTION_RECORD,\n}",
        "}",
    ),
    (
        "M4 Research given an input requirement",
        ENUMS,
        "ROOT_ENGINES: frozenset[Engine] = frozenset({Engine.RESEARCH})",
        "ROOT_ENGINES: frozenset[Engine] = frozenset()",
    ),
    (
        "M5 every engine treated as a root (no checking at all)",
        ENUMS,
        "ROOT_ENGINES: frozenset[Engine] = frozenset({Engine.RESEARCH})",
        "ROOT_ENGINES: frozenset[Engine] = frozenset(Engine)",
    ),
    # -- existence checking ------------------------------------------------
    (
        "M6 existence never checked",
        ORCH,
        "            exists=actual is not None,",
        "            exists=True,",
    ),
    (
        "M7 type never checked",
        ORCH,
        "        return self.actual_type is self.expected_type",
        "        return True",
    ),
    (
        "M8 satisfied ignores existence",
        ORCH,
        "        return self.exists and self.type_matches",
        "        return self.type_matches",
    ),
    (
        "M9 satisfied ignores the type",
        ORCH,
        "        return self.exists and self.type_matches",
        "        return self.exists",
    ),
    (
        "M10 a check always passes",
        ORCH,
        "        return all(check.satisfied for check in self.inputs)",
        "        return True",
    ),
    (
        "M11 only the FIRST input is required",
        ORCH,
        "        return all(check.satisfied for check in self.inputs)",
        "        return not self.inputs or self.inputs[0].satisfied",
    ),
    (
        "M12 a status precondition is invented [A1]",
        ORCH,
        "        return self.exists and self.type_matches",
        "        return (self.exists and self.type_matches\n                and self.status is not None\n                and self.status.value == 'ACTIVE')",
    ),
    # -- fail-closed behaviour ---------------------------------------------
    (
        "M13 unmapped engine silently treated as ready",
        ORCH,
        "            raise SequencingError(\n                f\"{item.engine.value} has no direct input type in N-14 and is \"",
        "            return SequencingCheck(item.engine, (), requires_inputs=False)\n            raise SequencingError(\n                f\"{item.engine.value} has no direct input type in N-14 and is \"",
    ),
    (
        "M14 resolver fault admits the item instead of failing closed",
        ORCH,
        "            satisfied = False\n            detail = (\n                f\"sequencing could not be determined for \"",
        "            satisfied = True\n            detail = (\n                f\"sequencing could not be determined for \"",
    ),
    (
        "M15 resolver fault propagates and destroys the cycle",
        ORCH,
        "        try:\n            result = SequencingGuard(self.state_resolver).check(item)\n            satisfied, detail = result.satisfied, result.detail\n        except (KeyboardInterrupt, SystemExit):",
        "        if True:\n            result = SequencingGuard(self.state_resolver).check(item)\n            satisfied, detail = result.satisfied, result.detail\n        if False:\n          try:\n            pass\n          except (KeyboardInterrupt, SystemExit):",
    ),
    (
        "M16 control signals swallowed by the guard path",
        ORCH,
        "        except (KeyboardInterrupt, SystemExit):\n            raise\n        except BaseException as exc:\n            satisfied = False",
        "        except () :\n            raise\n        except BaseException as exc:\n            satisfied = False",
    ),
    (
        "M17 resolver protocol no longer validated",
        ORCH,
        '        if not hasattr(self.resolver, "resolve_type"):\n            raise SequencingError(',
        "        if False:\n            raise SequencingError(",
    ),
    (
        "M18 assert_sequenced never raises",
        ORCH,
        "        result = self.check(item)\n        if not result.satisfied:\n            raise SequencingViolation(result.detail)",
        "        result = self.check(item)\n        if False:\n            raise SequencingViolation(result.detail)",
    ),
    # -- orchestrator integration ------------------------------------------
    (
        "M19 the guard is never consulted",
        ORCH,
        "        rejection = self._sequencing_rejection(item, cycle_id, invocation_index)\n        if rejection is not None:\n            return rejection",
        "        rejection = None\n        if rejection is not None:\n            return rejection",
    ),
    (
        "M20 rejection recorded but the engine still runs",
        ORCH,
        "        if rejection is not None:\n            return rejection",
        "        if False:\n            return rejection",
    ),
    (
        "M21 rejection recorded as an engine FAILURE [N-10]",
        ORCH,
        "            outcome=InvocationOutcome.REJECTED_OUT_OF_ORDER,\n            produced_ids=(),\n            detail=detail,",
        "            outcome=InvocationOutcome.FAILED,\n            produced_ids=(),\n            detail=detail,",
    ),
    (
        "M22 rejected item counted as attempted (corrupts processing state)",
        ORCH,
        "        return self.outcome not in (\n            InvocationOutcome.NOT_ATTEMPTED,\n            InvocationOutcome.REJECTED_OUT_OF_ORDER,\n        )",
        "        return self.outcome is not InvocationOutcome.NOT_ATTEMPTED",
    ),
    (
        "M23 rejected flag never true",
        ORCH,
        "        return self.outcome is InvocationOutcome.REJECTED_OUT_OF_ORDER",
        "        return False",
    ),
    (
        "M24 cycle hides sequencing violations",
        ORCH,
        "        return any(r.rejected for r in self.invocations)",
        "        return False",
    ),
    (
        "M25 rejected_count always zero",
        ORCH,
        "        return sum(1 for r in self.invocations if r.rejected)",
        "        return 0",
    ),
    # -- must NOT invent policy -------------------------------------------
    (
        "M26 work-set order policed (would close OQ-11)",
        ORCH,
        "        return tuple(self.check(item) for item in work_set)",
        "        seen = -1\n        out = []\n        for it in work_set:\n            st = ENGINE_STAGE.get(it.engine, 0)\n            c = self.check(it)\n            if st < seen:\n                c = SequencingCheck(it.engine, (InputCheck('order', False, None, None),), True)\n            seen = max(seen, st)\n            out.append(c)\n        return tuple(out)",
    ),
]


def run_suite() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_sequencing.py", "tests/test_orchestration.py",
         "tests/test_concurrency_boundary.py", "tests/test_processing_state.py",
         "tests/test_failure_surfacing.py"],
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
