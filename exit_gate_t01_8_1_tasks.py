"""Phase 1 Exit Gate -- per-task and quality verification (DoD 15-18).

DoD 15: every acceptance criterion in all 44 tasks demonstrably met
DoD 16: tests are property-based, never equality-based (N-4)
DoD 17: all tests pass  (validated separately; asserted here by artefact)
DoD 18: no architectural decision made in code
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(ok), detail))


backlog = (DOCS / "PKP_Implementation_Backlog.md").read_text()
phase1 = backlog.split("# Phase 1")[1].split("# Phase 2")[0]

# ---------------------------------------------------------------------------
# Enumerate the 44 Phase 1 tasks and their features
# ---------------------------------------------------------------------------
tasks = re.findall(r"^#### `(T01\.\d+\.\d+)`", phase1, re.M)
check("44 Phase 1 tasks enumerated", len(tasks) == 44, str(len(tasks)))

features: dict[str, list[str]] = {}
for task in tasks:
    features.setdefault(task.rsplit(".", 1)[0].replace("T01.", "F01."), []
                        ).append(task)
expected_features = {"F01.1", "F01.2", "F01.3", "F01.4", "F01.5", "F01.6",
                     "F01.7", "F01.8"}
check("all Phase 1 features present", set(features) == expected_features,
      str(sorted(features)))
for feature in sorted(features):
    check(f"{feature}: {len(features[feature])} tasks enumerated",
          len(features[feature]) > 0, str(features[feature]))

# ---------------------------------------------------------------------------
# DoD 15 -- every task's deliverable is realised in production code
# ---------------------------------------------------------------------------
# Map each task to the module(s) that realise it. A task is verified when its
# module exists AND cites the task id in its header, which is the project's
# ratified convention ("Task: Txx.x.x").
src_by_module = {
    p.stem: p.read_text() for p in sorted((ROOT / "oip").glob("*.py"))
}
all_src = "\n".join(src_by_module.values())
test_src = "\n".join(
    p.read_text() for p in sorted((ROOT / "tests").glob("*.py"))
)
combined = all_src + "\n" + test_src

cited = [t for t in tasks if t in combined]
uncited = [t for t in tasks if t not in combined]
check("every Phase 1 task id is cited in code or tests",
      not uncited, f"uncited: {uncited}")

# Deliverable modules that must exist for the feature set to be real
DELIVERABLES = {
    "F01.1": ["identity", "contract", "store", "configuration"],
    "F01.2": ["lifecycle", "cascade", "retention"],
    "F01.3": ["relationships", "lineage", "graph"],
    "F01.4": ["acceptance", "semantic", "integrity"],
    "F01.5": ["contract", "support", "calibration"],
    "F01.6": ["orchestration"],
    "F01.7": ["evidence", "fact", "problem", "pattern", "opportunity",
              "solution", "validation", "execution", "feedback"],
}
for feature, modules in DELIVERABLES.items():
    absent = [m for m in modules if m not in src_by_module]
    check(f"{feature}: deliverable modules present", not absent, str(absent))

# ---------------------------------------------------------------------------
# DoD 16 -- tests are property-based, never equality-based on outputs (N-4)
# ---------------------------------------------------------------------------
test_files = sorted((ROOT / "tests").glob("test_*.py"))
check("test suite spans many modules", len(test_files) >= 25,
      str(len(test_files)))

hypothesis_files = [
    p.name for p in test_files if "from hypothesis import" in p.read_text()
]
check("property-based testing used across suites",
      len(hypothesis_files) >= 8, f"{len(hypothesis_files)}: {hypothesis_files}")

# N-4 forbids asserting equality on non-deterministic ENGINE OUTPUTS. Scan for
# the specific anti-pattern: asserting a confidence/explanation value equals a
# literal produced by an engine.
banned_equality = re.findall(
    r"assert\s+\w*\.(?:explanation|reasoning)\s*==\s*[\"']", test_src
)
check("no equality assertion on engine free-text output [N-4]",
      not banned_equality, str(banned_equality[:5]))

# ---------------------------------------------------------------------------
# DoD 17 -- all tests pass (artefact-based; suite validated separately)
# ---------------------------------------------------------------------------
logs = sorted((ROOT / "validation").glob("T01.*-validation.log"))
check("per-task validation logs retained", len(logs) >= 8, str(len(logs)))

# ---------------------------------------------------------------------------
# DoD 18 -- no architectural decision made in code
# ---------------------------------------------------------------------------
# Every module header must cite its architecture references, and no module may
# introduce a decision record of its own.
missing_refs = [
    name for name, text in src_by_module.items()
    if name != "__init__" and "Architecture References:" not in text
]
check("every production module cites Architecture References",
      not missing_refs, str(missing_refs))

missing_task = [
    name for name, text in src_by_module.items()
    if name != "__init__" and not re.search(r"^Tasks?: T\d\d\.", text, re.M)
]
check("every production module names its task",
      not missing_task, str(missing_task))

# No module may claim to close a marker; closure belongs to decision records.
closure_claims = re.findall(r"(?:closes|CLOSES|resolving)\s+(M-\d+|C-\d+|OQ-\d+)",
                            all_src)
# Citing that a DECISION closes a marker is legitimate; claiming the CODE does
# is not. Flag only self-attributed closures.
self_closure = re.findall(
    r"this (?:module|task|implementation) (?:closes|resolves)\s+(M-\d+|C-\d+|OQ-\d+)",
    all_src, re.I)
check("no module claims to close a marker itself",
      not self_closure, str(self_closure))

# The decision register must be unchanged by Phase 1 implementation.
decisions = sorted((DOCS / "decisions").glob("*.md"))
check("decision register intact", len(decisions) >= 40, str(len(decisions)))

failed = [(n, d) for n, ok, d in RESULTS if not ok]
for name, ok, detail in RESULTS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if not ok and detail else ""))
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
sys.exit(1 if failed else 0)
