"""Mutation testing for T01.6.2.

Every rule introduced by this task is broken in turn; the suite must fail.
A mutation that survives means the rule is not actually enforced by tests.
Source is restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "orchestration.py"
BACKUP = ROOT / "validation" / ".orchestration.py.orig"

# (label, find, replace)
MUTATIONS = [
    (
        "M1 NOT_ATTEMPTED admitted as processing",
        "if self.outcome is InvocationOutcome.NOT_ATTEMPTED:\n            raise ProcessingStateError(",
        "if False:\n            raise ProcessingStateError(",
    ),
    (
        "M2 record_cycle records unattempted items too",
        "for r in cycle.invocations\n                if r.attempted",
        "for r in cycle.invocations\n                if True",
    ),
    (
        "M3 duplicate cycle commit permitted",
        "if cycle.cycle_id in self._by_cycle:\n                raise ProcessingStateError(",
        "if False:\n                raise ProcessingStateError(",
    ),
    (
        "M4 has_processed always reports unprocessed",
        "return bool(self._by_key.get(self._key(engine, input_id)))",
        "return False",
    ),
    (
        "M5 repeat detection ignores the engine",
        "if self._by_key.get((item.engine, oid))",
        "if False",
    ),
    (
        "M6 reprocessed_keys reports nothing",
        "if len(indices) > 1",
        "if len(indices) > 99",
    ),
    (
        "M7 bare string no longer refused (the real defect)",
        'if isinstance(value, (str, bytes)):\n        raise error(',
        'if False:\n        raise error(',
    ),
    (
        "M8 mixed timezone awareness unguarded",
        "if (started_at.tzinfo is None) != (ended_at.tzinfo is None):  # type: ignore[union-attr]\n        raise error(",
        "if False:\n        raise error(",
    ),
    (
        "M9 non-datetime timestamp accepted",
        "if not isinstance(value, datetime):\n            raise error(",
        "if False:\n            raise error(",
    ),
    (
        "M10 ended-before-started accepted",
        "if self.ended_at < self.started_at:",
        "if False:",
    ),
    (
        "M11 empty input_ids accepted",
        'if not self.input_ids:\n            raise ProcessingStateError(\n                "processing record requires at least one input id',
        'if False:\n            raise ProcessingStateError(\n                "processing record requires at least one input id',
    ),
    (
        "M12 blank configuration ref accepted",
        'if not (self.engine_configuration_ref or "").strip():\n            raise ProcessingStateError(',
        'if False:\n            raise ProcessingStateError(',
    ),
    (
        "M13 duplicate input within a record accepted",
        "if len(set(self.input_ids)) != len(self.input_ids):\n            raise ProcessingStateError(",
        "if False:\n            raise ProcessingStateError(",
    ),
    (
        "M14 non-string id no longer a knowledge mutation",
        "if not isinstance(oid, str):\n                raise KnowledgeMutationError(",
        "if False:\n                raise KnowledgeMutationError(",
    ),
    (
        "M15 isolation: record may act as lineage",
        'def as_lineage_reference(self):\n        """Never permitted. [CI-1, N-10]"""\n        raise ProcessingIsolationError(',
        'def as_lineage_reference(self):\n        """Never permitted. [CI-1, N-10]"""\n        return None\n        raise ProcessingIsolationError(',
    ),
    (
        "M16 isolation: record may become Evidence",
        'def as_evidence(self):\n        """Never permitted. [AD-05, Article IV]"""\n        raise ProcessingIsolationError(',
        'def as_evidence(self):\n        """Never permitted. [AD-05, Article IV]"""\n        return None\n        raise ProcessingIsolationError(',
    ),
    (
        "M17 record claims to be intelligence",
        '@property\n    def is_intelligence(self) -> bool:\n        """Always False. Processing state is infrastructure. [CI-1, Art.V]"""\n        return False',
        '@property\n    def is_intelligence(self) -> bool:\n        """Always False. Processing state is infrastructure. [CI-1, Art.V]"""\n        return True',
    ),
    (
        "M18 record claims to participate in lineage",
        '@property\n    def participates_in_lineage(self) -> bool:\n        """Always False. Processing state never enters lineage. [N-10]"""\n        return False\n\n    def as_lineage_reference(self):',
        '@property\n    def participates_in_lineage(self) -> bool:\n        """Always False. Processing state never enters lineage. [N-10]"""\n        return True\n\n    def as_lineage_reference(self):',
    ),
    (
        "M19 append-only: delete permitted",
        'def delete(self, *_args, **_kwargs) -> None:\n        """Never permitted. Processing state is append-only. [T01.6.2]"""\n        raise ProcessingStateError(',
        'def delete(self, *_args, **_kwargs) -> None:\n        """Never permitted. Processing state is append-only. [T01.6.2]"""\n        return None\n        raise ProcessingStateError(',
    ),
    (
        "M20 append-only: update permitted",
        'def update(self, *_args, **_kwargs) -> None:\n        """Never permitted. Records are immutable. [T01.6.2]"""\n        raise ProcessingStateError(',
        'def update(self, *_args, **_kwargs) -> None:\n        """Never permitted. Records are immutable. [T01.6.2]"""\n        return None\n        raise ProcessingStateError(',
    ),
    (
        "M21 orchestrator stops committing processing state",
        "if self.processing_store is not None:\n            self.processing_store.record_cycle(record)",
        "if False:\n            self.processing_store.record_cycle(record)",
    ),
    (
        "M22 attempt_count always reports a single attempt",
        "return len(self._by_key.get(self._key(engine, input_id), ()))",
        "return 1",
    ),
    (
        "M23 atomic cycle commit becomes incremental",
        "entries = [\n                ProcessingRecord(",
        "entries = [\n                self._append(ProcessingRecord)(",
    ),
    (
        "M24 bad cycle_id accepted",
        "if self.cycle_id < 1:\n            raise ProcessingStateError(",
        "if False:\n            raise ProcessingStateError(",
    ),
    (
        "M25 unknown engine accepted in a lookup key",
        "if not isinstance(engine, Engine):\n            raise ProcessingStateError(\n                f\"expected a known Engine, got {engine!r}\"\n            )",
        "if False:\n            raise ProcessingStateError(\n                f\"expected a known Engine, got {engine!r}\"\n            )",
    ),
]


def run_suite() -> bool:
    """True if the suite passes."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_processing_state.py", "tests/test_orchestration.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode == 0


def main() -> int:
    shutil.copy2(SRC, BACKUP)
    original = SRC.read_text()

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline is not green; aborting")
        shutil.copy2(BACKUP, SRC)
        return 1
    print("pass")

    survivors, killed, inapplicable = [], [], []
    for label, find, replace in MUTATIONS:
        if find not in original:
            inapplicable.append(label)
            print(f"  ??  {label}: pattern not found")
            continue
        SRC.write_text(original.replace(find, replace, 1))
        if run_suite():
            survivors.append(label)
            print(f"  SURVIVED  {label}")
        else:
            killed.append(label)
            print(f"  killed    {label}")
        SRC.write_text(original)

    # restore and verify byte-identical
    SRC.write_text(original)
    diff = subprocess.run(["diff", "-q", str(SRC), str(BACKUP)],
                          capture_output=True, text=True)
    identical = diff.returncode == 0
    print(f"\nkilled {len(killed)}/{len(MUTATIONS)}; "
          f"survivors {len(survivors)}; inapplicable {len(inapplicable)}")
    print(f"source restored byte-identical: {identical}")
    BACKUP.unlink()

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
