#!/usr/bin/env python3
"""T03.1.4 mutation harness -- canonical-claim merging per D-05.

Each mutant surgically breaks ONE guarantee of the merge machinery in
``oip/extraction.py``; the kill suite (tests/test_merging.py +
tests/test_extraction.py + tests/test_anchoring.py +
tests/test_decomposition.py) must fail for every mutant. Zero survivors
is the exit condition. Sources are restored byte-identically afterwards
and verified against their sha256 digests.

PROVENANCE (T03.1.4): the harness discipline (mutant list shape, purge,
byte-identical restore) mirrors mutate_t03_1_1.py; the mutants target
the merge machinery this task added. The kill suite is the 4-file set
exercised throughout T03.1.4.
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "oip" / "extraction.py"
TESTS = [
    "tests/test_merging.py",
    "tests/test_extraction.py",
    "tests/test_anchoring.py",
    "tests/test_decomposition.py",
]

MUTANTS: list[tuple[str, str, str]] = [
    # -- AC1: the merge interception ------------------------------------
    ("N1 merge disabled: equivalent claim gets a duplicate Fact [AC1]",
     """    existing = store.facts.find_equivalent(claim)""",
     """    existing = None and store.facts.find_equivalent(claim)"""),

    ("N2 over-merge: UNCERTAIN/CONTAINMENT merged like EQUIVALENT [AC3]",
     """    existing = store.facts.find_equivalent(claim)""",
     """    _overmerge_pairs = store.facts.assess_all(claim)
    existing = next(
        ((_f, _a) for _f, _a in _overmerge_pairs
         if _a.verdict is not __import__(
             "oip.claim", fromlist=["Verdict"]
         ).Verdict.NOT_EQUIVALENT),
        None,
    )"""),

    ("N3 replay allowed: Evidence attached twice [F-I2]",
     """        if canonical.attachment_for(request.evidence_ref) is not None:""",
     """        if False:"""),

    # -- N-10: the replay refusal must be recorded ------------------------
    ("N4 replay refusal silent: never recorded [N-10]",
     '''            failure = _failure(
                request, request.evidence_ref,
                ExtractionStage.MERGE_FAILED, "EVIDENCE_ALREADY_ATTACHED",
                f"the canonical Fact {canonical.object_id!r} already "
                f"attaches Evidence {request.evidence_ref!r}; a replay "
                f"adds nothing and is refused, never re-attached "
                f"[F-I2, T03.1.4]", log, now,
            )
            raise _refuse(failure)''',
     '''            raise ExtractionRefusedError("silent replay refusal")'''),

    # -- AC2: the version machinery ---------------------------------------
    ("N5 no supersession: I5 blocks the merged write [R-1]",
     '''            store.transition(
                canonical.object_id, ObjectStatus.SUPERSEDED,
                "corroborated: equivalent extraction attached [D-05, F-I4]",
            )''',
     '''            if False:
                store.transition(
                    canonical.object_id, ObjectStatus.SUPERSEDED,
                    "corroborated: equivalent extraction attached "
                    "[D-05, F-I4]",
                )'''),

    ("N6 chain broken: merged write loses its predecessor [V11]",
     """                merged, predecessor_id=canonical.object_id""",
     """                merged, predecessor_id=None"""),

    ("N7 allocator bypassed: merged version reuses the old identity "
     "[R-1/V11]",
     """                identity=store.allocator.succeed(canonical.attributes.identity),""",
     """                identity=None,"""),

    ("N8 justification dropped: merge without F-I4 evidence linkage",
     """            merged_evidence_ref=request.evidence_ref,""",
     """            merged_evidence_ref=None,"""),

    # -- R-3/V5: the re-derived ceiling ------------------------------------
    ("N9 ceiling inherited: weak corroborator ignored [V5]",
     """            support = min(
                store.get_evidence(ref).attributes.confidence.effective_confidence
                for ref in upstream_refs
            )""",
     """            support = canonical.attributes.confidence.evidential_support"""),

    ("N10 assertion floor dropped: extraction confidence trusted alone "
     "[R-3]",
     """            assertion = min(
                canonical.attributes.confidence.assertion_confidence,
                float(request.extraction_confidence),
            )""",
     """            assertion = float(request.extraction_confidence)"""),

    # -- AC3: the DUPLICATES link ------------------------------------------
    ("N11 duplicates dropped: uncertain equivalence links nothing [AC3]",
     """        duplicates=duplicates_targets,""",
     """        duplicates=(),"""),

    ("N12 spurious duplicates: NOT_EQUIVALENT linked too",
     """        if result.verdict in (Verdict.CONTAINMENT, Verdict.UNCERTAIN)""",
     """        if True or result.verdict in (
            Verdict.CONTAINMENT, Verdict.UNCERTAIN)"""),

    # -- N-10: attempted semantics ------------------------------------------
    ("N13 merge failures reported as never-attempted [N-10]",
     """        ExtractionStage.DECOMPOSITION_FAILED,
        ExtractionStage.MERGE_FAILED,""",
     """        ExtractionStage.DECOMPOSITION_FAILED,"""),

    # -- density -------------------------------------------------------------
    ("N14 density double-counts superseded versions",
     """        if stored_object is not None and (
            stored_object.status is not ObjectStatus.ACTIVE
        ):
            continue""",
     """        if False:
            continue"""),

    # -- concurrency surface --------------------------------------------------
    ("N15 race reason swapped: concurrent merge mislabelled",
     """ExtractionStage.MERGE_FAILED, "MERGE_NOT_POSSIBLE",""",
     """ExtractionStage.MERGE_FAILED, "CONCURRENT_MERGE","""),
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _purge_pycache() -> None:
    for cache in (ROOT / "oip" / "__pycache__",):
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", *TESTS],
        cwd=ROOT, capture_output=True, text=True, timeout=900,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode


def run_suite() -> bool:
    """True if the suite PASSES (i.e. the mutant survived)."""
    try:
        return _run() == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] ", end="", flush=True)
        return False


def main() -> int:
    original = SRC.read_bytes()
    original_digest = _sha256(original)

    killed, survivors, inapplicable = 0, [], 0
    try:
        for name, old, new in MUTANTS:
            mutated = original.decode("utf-8")
            if old not in mutated:
                print(f"  INAPPLICABLE (anchor missing): {name}")
                inapplicable += 1
                continue
            mutated = mutated.replace(old, new, 1)
            SRC.write_text(mutated, encoding="utf-8")
            try:
                survived = run_suite()
            finally:
                SRC.write_bytes(original)
                _purge_pycache()
            if survived:
                survivors.append(name)
                print(f"  SURVIVOR: {name}")
            else:
                killed += 1
                print(f"  killed:   {name}")
    finally:
        SRC.write_bytes(original)

    restored_digest = _sha256(SRC.read_bytes())
    restored = restored_digest == original_digest
    print(f"sources restored byte-identical: {restored}")
    print(f"killed {killed}/{len(MUTANTS)}; survivors {len(survivors)}; "
          f"inapplicable {inapplicable}")
    for name in survivors:
        print(f"  SURVIVOR: {name}")
    if not restored:
        print("FATAL: sources did not restore byte-identically")
        return 2
    return 0 if (not survivors and inapplicable == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
