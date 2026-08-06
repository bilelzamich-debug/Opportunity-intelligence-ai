"""Mutation testing for T01.2.5 ARCHIVED tiering.

Every rule introduced by this task is broken in turn; the suite must fail.
Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RET = ROOT / "oip" / "retention.py"
STORE = ROOT / "oip" / "store.py"
LIFE = ROOT / "oip" / "lifecycle.py"
TARGETS = [RET, STORE, LIFE]

MUTATIONS = [
    # -- the store guard: the load-bearing enforcement point ---------------
    (
        "M1 store guard removed entirely",
        STORE,
        "            if status is ObjectStatus.ARCHIVED:\n                self._require_unreachable_for_archival(object_id)",
        "            if False:\n                self._require_unreachable_for_archival(object_id)",
    ),
    (
        "M2 store guard never raises",
        STORE,
        "            if object_id in self.graph.ancestors(active_id):\n                raise ReachabilityError(",
        "            if False:\n                raise ReachabilityError(",
    ),
    (
        "M3 store guard skips every ACTIVE object",
        STORE,
        "        for active_id in tuple(self._active.values()):",
        "        for active_id in ():",
    ),
    (
        "M4 store guard checks only direct parents, not ancestors",
        STORE,
        "            if object_id in self.graph.ancestors(active_id):",
        "            if object_id in self.graph.parents(active_id):",
    ),
    (
        "M5 store guard protects the candidate from itself (archival impossible)",
        STORE,
        "            if active_id == object_id:\n                continue",
        "            if False:\n                continue",
    ),
    # -- the policy's eligibility rule -------------------------------------
    (
        "M6 policy ignores reachability",
        RET,
        "        if self._supports_other_active(object_id, index):\n            reasons.append(REASON_REACHABLE)",
        "        if False:\n            reasons.append(REASON_REACHABLE)",
    ),
    (
        "M7 policy ignores the ACTIVE-only rule",
        RET,
        "        if stored.status is not ObjectStatus.ACTIVE:",
        "        if False:",
    ),
    (
        "M8 support test always false",
        RET,
        "            if object_id in graph.ancestors(active_id, self.max_depth):\n                return True\n        return False",
        "            pass\n        return False",
    ),
    (
        "M9 support test excludes nothing (candidate protects itself)",
        RET,
        "            if active_id == object_id or not graph.contains(active_id):",
        "            if not graph.contains(active_id):",
    ),
    (
        "M10 assess always archivable",
        RET,
        "            archivable=not reasons,",
        "            archivable=True,",
    ),
    (
        "M11 archive skips its own eligibility check",
        RET,
        "        assessment = self.assess(object_id, index)\n        if not assessment.archivable:",
        "        assessment = self.assess(object_id, index)\n        if False:",
    ),
    (
        "M12 archive_all ignores eligibility",
        RET,
        "            if self.assess(object_id).archivable:",
        "            if True:",
    ),
    (
        "M13 archive_all evaluates once up front (stale picture)",
        RET,
        "        for object_id in object_ids:\n            if self.assess(object_id).archivable:",
        "        _stale = self.reachability()\n        for object_id in object_ids:\n            if self.assess(object_id, _stale).archivable:",
    ),
    (
        "M14 candidates reports everything",
        RET,
        "            if (assessment := self.assess(stored.object_id, index)).archivable",
        "            if (assessment := self.assess(stored.object_id, index)) is not None",
    ),
    # -- reachability index -------------------------------------------------
    (
        "M15 index omits ancestors",
        RET,
        "                protected.update(graph.ancestors(root, max_depth))",
        "                pass",
    ),
    (
        "M16 index omits the ACTIVE roots themselves",
        RET,
        "        protected: set[str] = set(roots)",
        "        protected: set[str] = set()",
    ),
    # -- lifecycle: ARCHIVED must stay terminal and ACTIVE-only ------------
    (
        "M17 ARCHIVED becomes non-terminal",
        LIFE,
        "    ObjectStatus.ARCHIVED: frozenset(),",
        "    ObjectStatus.ARCHIVED: frozenset({ObjectStatus.ACTIVE}),",
    ),
    (
        "M18 REJECTED may transition to ARCHIVED",
        LIFE,
        "    ObjectStatus.REJECTED: frozenset(),",
        "    ObjectStatus.REJECTED: frozenset({ObjectStatus.ARCHIVED}),",
    ),
    (
        "M19 PROPOSED may transition straight to ARCHIVED",
        LIFE,
        "    ObjectStatus.PROPOSED: frozenset(\n        {ObjectStatus.ACTIVE, ObjectStatus.REJECTED}\n    ),",
        "    ObjectStatus.PROPOSED: frozenset(\n        {ObjectStatus.ACTIVE, ObjectStatus.REJECTED, ObjectStatus.ARCHIVED}\n    ),",
    ),
    (
        "M20 ACTIVE loses the ARCHIVED transition entirely",
        LIFE,
        "            ObjectStatus.ARCHIVED,\n        }\n    ),",
        "        }\n    ),",
    ),
    # -- cascade / M-65 must not change ------------------------------------
    (
        "M21 ARCHIVED becomes a cascade trigger",
        ROOT / "oip" / "cascade.py",
        "CASCADE_TRIGGERS: frozenset[ObjectStatus] = frozenset(\n    {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED}\n)",
        "CASCADE_TRIGGERS: frozenset[ObjectStatus] = frozenset(\n    {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED, ObjectStatus.ARCHIVED}\n)",
    ),
    # -- skeleton verification ---------------------------------------------
    (
        "M22 skeleton check never reports a missing attribute",
        RET,
        "            if getattr(attributes, name, None) in (None, \"\"):\n                missing.append(name)",
        "            if False:\n                missing.append(name)",
    ),
    (
        "M23 skeleton check ignores a lost fingerprint",
        RET,
        "        if not (fingerprint or \"\").strip():\n            missing.append(\"content_fingerprint\")",
        "        if False:\n            missing.append(\"content_fingerprint\")",
    ),
    (
        "M24 skeleton check ignores lost provenance",
        RET,
        "        if provenance is None:\n            missing.append(\"provenance\")",
        "        if False:\n            missing.append(\"provenance\")",
    ),
    (
        "M25 skeleton check ignores missing lineage references",
        RET,
        "        elif not attributes.object_type.is_root and not stored.lineage.references:\n            missing.append(\"lineage_references\")",
        "        elif False:\n            missing.append(\"lineage_references\")",
    ),
    (
        "M26 traversal_intact always true",
        RET,
        "        if not graph.contains(object_id):\n            return False",
        "        if False:\n            return False",
    ),
    (
        "M27 policy claims it performs hard deletion",
        RET,
        "    def performs_hard_deletion(self) -> bool:\n        \"\"\"Always False. Referenced objects are never hard-deleted. [I4]\"\"\"\n        return False",
        "    def performs_hard_deletion(self) -> bool:\n        \"\"\"Always False. Referenced objects are never hard-deleted. [I4]\"\"\"\n        return True",
    ),
    (
        "M28 no-graph case proceeds instead of failing closed",
        RET,
        "        if graph is None:\n            raise RetentionError(",
        "        if False:\n            raise RetentionError(",
    ),
]


def run_suite() -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_retention.py", "tests/test_cascade.py",
         "tests/test_store.py", "tests/test_lifecycle_config_support.py",
         "tests/test_integrity.py", "tests/test_graph.py"],
        cwd=ROOT, capture_output=True, text=True,
    )
    return proc.returncode == 0


def main() -> int:
    targets = list({m[1] for m in MUTATIONS})
    originals = {p: p.read_text() for p in targets}
    backups = {p: ROOT / "validation" / f".{p.name}.orig" for p in targets}
    for p in targets:
        shutil.copy2(p, backups[p])

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        for p in targets:
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

    for p in targets:
        p.write_text(originals[p])

    identical = True
    for p in targets:
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
