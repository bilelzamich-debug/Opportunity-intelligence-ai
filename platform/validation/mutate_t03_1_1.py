"""Mutation testing for T03.1.1 -- claim extraction.

Each mutation breaks one rule the extraction engine enforces; the suite
must fail. The most important mutants are those that ADMIT WHAT MUST BE
REFUSED -- fabricating an anchor, accepting an unsupported claim,
defaulting the qualifying context, merging equivalent claims (T03.1.4
overreach), destroying recorded uncertainty, or leaking an object after
a refusal.

Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

# ROOT-CAUSE HARDENING (from T02.2.1): a restored source within the same
# mtime second can be served with STALE MUTATED bytecode from __pycache__.
# Never write bytecode during mutation runs, and purge the cache around
# every write so each suite sees the real file.
PYCACHE = Path(__file__).resolve().parents[1] / "oip" / "__pycache__"


def _purge_pycache() -> None:
    shutil.rmtree(PYCACHE, ignore_errors=True)


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "extraction.py"

MUTATIONS = [
    # -- S-5 layer 1: anchor gates ---------------------------------------
    ("M1 anchor-uniqueness gate skipped: ambiguous spans admit",
     SRC,
     """    if occurrences > 1:
        # Preserve uncertainty instead of resolving it: an ambiguous
        # location is refused, never guessed. [AC2]
        failure = _failure(""",
     """    if False:
        # Preserve uncertainty instead of resolving it: an ambiguous
        # location is refused, never guessed. [AC2]
        failure = _failure("""),
    ("M2 anchor-presence gate skipped: fabricated locations admit",
     SRC,
     """    occurrences = _locate(body, request.anchor)
    if occurrences == 0:
        failure = _failure(""",
     """    occurrences = _locate(body, request.anchor)
    if False:
        failure = _failure("""),
    ("M3 layer-1 component check skipped: unsupported claims admit",
     SRC,
     "    if missing:",
     "    if False and missing:"),
    ("M4 value component dropped from the layer-1 check",
     SRC,
     '''        request.subject, request.predicate, request.value_text, request.anchor
    )''',
     '''        request.subject, request.predicate, None, request.anchor
    )'''),
    # -- AC2: context and uncertainty ------------------------------------
    ("M5 qualifying_context silently defaulted when blank",
     SRC,
     '''        if not (self.qualifying_context or "").strip():
            raise ExtractionError(''',
     '''        if not (self.qualifying_context or "").strip():
            self.qualifying_context = "unqualified"
            return
        if False:
            raise ExtractionError('''),
    ("M6 extraction confidence clamped: low certainty destroyed",
     SRC,
     "        extraction_confidence=float(request.extraction_confidence),",
     "        extraction_confidence=max(0.5, float(request.extraction_confidence)),"),
    # -- N-15 / lifecycle --------------------------------------------------
    ("M7 REFERENCE-mode Evidence admitted despite unverifiable anchors",
     SRC,
     "    if evidence.content.storage_mode is not StorageMode.FULL:",
     "    if False:"),
    ("M8 non-ACTIVE Evidence admitted: retracted material grounds claims",
     SRC,
     "    if stored.status is not ObjectStatus.ACTIVE:",
     "    if False:"),
    # -- R-3: confidence ----------------------------------------------------
    ("M9 evidential support invented: ceiling decoupled from the source",
     SRC,
     "    support = evidence.attributes.confidence.effective_confidence",
     "    support = 1.0"),
    # -- S-3: extraction never merges ---------------------------------------
    ("M10 equivalent claim merged into an existing Fact (over-merge)",
     SRC,
     '''    # -- Persistence through the acceptance path (F-V1..F-V6 + universal
    # rules; V5 re-checks the confidence ceiling against the source).
    try:
        stored_fact = store.write_fact(fact)''',
     '''    # -- Persistence through the acceptance path (F-V1..F-V6 + universal
    # rules; V5 re-checks the confidence ceiling against the source).
    try:
        existing = store.facts.find_equivalent(claim)
        if existing is not None and existing[0].object_id != fact.object_id:
            canonical = existing[0]
            fact = canonical.with_attachment(
                attachment,
                __import__(
                    "oip.fact", fromlist=["MergeJustification"]
                ).MergeJustification(
                    verdict=__import__(
                        "oip.claim", fromlist=["Verdict"]
                    ).Verdict.EQUIVALENT,
                    reason="mutant: merged without T03.1.4 machinery",
                    merged_evidence_ref=attachment.evidence_ref,
                    merged_at=now,
                ),
            )
        stored_fact = store.write_fact(fact)'''),
    # -- N-10: refusal recording ---------------------------------------------
    ("M11 unsupported-claim refusal becomes silent (never recorded)",
     SRC,
     """    if missing:
        failure = _failure(
            request, request.evidence_ref,
            ExtractionStage.UNSUPPORTED_CLAIM, "COMPONENTS_ABSENT",
            f"claim components {list(missing)} absent from the anchored "
            f"span; the Evidence does not support this claim as stated "
            f"[S-5 layer 1, F-I1]", log, now,
        )
        raise _refuse(failure)""",
     """    if missing:
        raise ExtractionRefusedError(
            f"silent refusal: components {list(missing)} absent"
        )"""),
    ("M12 store rejection leaks as success: phantom outcome",
     SRC,
     '''    except WriteRejectedError as exc:
        failure = _failure(''',
     '''    except WriteRejectedError as exc:
        if False:
            failure = _failure('''),
    # -- V8 temporal discipline ------------------------------------------------
    ("M13 temporal-conflict gate skipped: clock errors escape unrecorded",
     SRC,
     "    if now < evidence.attributes.observed_at:",
     "    if False:"),
    # -- N-10: found-nothing vs failed ------------------------------------------
    ("M14 EMPTY_CONTENT misreported as not-attempted",
     SRC,
     """        ExtractionStage.EMPTY_CONTENT,
        ExtractionStage.ANCHOR_NOT_FOUND,""",
     """        ExtractionStage.ANCHOR_NOT_FOUND,
        ExtractionStage.ANCHOR_NOT_FOUND,"""),
    # -- N-16: independence -------------------------------------------------------
    ("M15 corroboration inflated beyond its attachments",
     SRC,
     "        independent_source_count=1,",
     "        independent_source_count=2,"),
    # -- AC3: density ----------------------------------------------------------
    ("M16 density counts refusals as claims",
     SRC,
     "        total_claims=sum(row.claims for row in rows),",
     "        total_claims=sum(row.claims + row.refusals for row in rows),"),
]


def _run() -> int:
    _purge_pycache()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q",
         "tests/test_extraction.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
        env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return proc.returncode


def run_suite() -> bool:
    """True if the suite PASSES (i.e. the mutant survived)."""
    try:
        return _run() == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] ", end="", flush=True)
        return True


def main() -> int:
    original = SRC.read_text()
    backup = ROOT / "validation" / ".extraction.py.orig"
    shutil.copy2(SRC, backup)

    print("baseline (unmutated) ...", end=" ", flush=True)
    if not run_suite():
        print("FAIL -- baseline not green; aborting")
        SRC.write_text(original)
        return 2
    print("pass")

    survivors: list[str] = []
    inapplicable: list[str] = []
    killed = 0

    for label, path, old, new in MUTATIONS:
        if old == new:
            inapplicable.append(label + " (no-op placeholder)")
            continue
        text = path.read_text()
        if old not in text:
            inapplicable.append(label)
            print(f"  SKIP      {label} (anchor not found)")
            continue
        path.write_text(text.replace(old, new, 1))
        try:
            if run_suite():
                survivors.append(label)
                print(f"  SURVIVED  {label}")
            else:
                killed += 1
                print(f"  killed    {label}")
        finally:
            path.write_text(original)
            _purge_pycache()

    SRC.write_text(original)
    identical = SRC.read_text() == backup.read_text()
    total = len(MUTATIONS) - len(inapplicable)
    print(f"\nkilled {killed}/{total}; survivors {len(survivors)}; "
          f"inapplicable {len(inapplicable)}")
    print(f"sources restored byte-identical: {identical}")
    for s in survivors:
        print(f"  SURVIVOR: {s}")
    backup.unlink(missing_ok=True)
    return 1 if (survivors or inapplicable or not identical) else 0


if __name__ == "__main__":
    sys.exit(main())
