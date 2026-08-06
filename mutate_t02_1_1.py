"""Mutation testing for T02.1.1 -- source model.

Each mutation breaks one rule of the ratified boundary; the suite must fail.
The most important mutants are those that CLOSE AN OPEN MARKER -- inventing a
taxonomy member, defaulting trust, letting trust score, or faking
learnability. If any of those survives, the tests are not protecting the gap.

Sources restored byte-identically and verified with `diff -q`.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "oip" / "source.py"

MUTATIONS = [
    # -- closing M-16 by inventing vocabulary -------------------------------
    ("M1 taxonomy populated with an invented member",
     SRC,
     "    # INTENTIONALLY EMPTY. Members are supplied by the decision closing M-16.",
     "    CUSTOMER_REVIEW_CORPUS = \"customer_review_corpus\""),
    ("M2 classify() guesses instead of refusing",
     SRC,
     "    raise TaxonomyNotRatifiedError(\n        f\"cannot classify source_type {source_type!r}",
     "    return source_type  # type: ignore[return-value]\n    raise TaxonomyNotRatifiedError(\n        f\"cannot classify source_type {source_type!r}"),
    ("M3 membership predicate admits raw strings",
     SRC,
     "    return isinstance(candidate, SourceType) and candidate in set(SourceType)",
     "    return bool(candidate)"),
    # -- eligibility failing OPEN instead of closed -------------------------
    ("M4 eligibility defaults to ELIGIBLE",
     SRC,
     "        outcome=SourceEligibility.UNDETERMINED,",
     "        outcome=SourceEligibility.ELIGIBLE,"),
    ("M5 undetermined wrongly admits acquisition",
     SRC,
     "        return self.outcome is SourceEligibility.ELIGIBLE",
     "        return self.outcome is not SourceEligibility.INELIGIBLE"),
    ("M6 require_eligible admits everything",
     SRC,
     "    if not assessment.admits_acquisition:",
     "    if False:"),
    # -- trust: defaulting, range, provenance -------------------------------
    ("M7 unrated trust defaults to a neutral value",
     SRC,
     "        return self.trust.value if self.trust is not None else None",
     "        return self.trust.value if self.trust is not None else 0.5"),
    ("M8 trust range check removed",
     SRC,
     "        if not TRUST_MINIMUM <= float(self.value) <= TRUST_MAXIMUM:",
     "        if False:"),
    ("M9 rationale no longer required",
     SRC,
     "        if not (self.rationale or \"\").strip():",
     "        if False:"),
    ("M10 booleans accepted as trust values",
     SRC,
     "        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):",
     "        if not isinstance(self.value, (int, float)):"),
    ("M11 trust banding invented from R-3 bands",
     SRC,
     "        raise TrustNotRatifiedError(\n            \"trust banding is undefined:",
     "        return \"MODERATE\"\n        raise TrustNotRatifiedError(\n            \"trust banding is undefined:"),
    # -- S-02: trust must not score -----------------------------------------
    ("M12 trust declared to affect evidential_support",
     SRC,
     "def affects_evidential_support() -> bool:",
     "def affects_evidential_support() -> bool:\n    return True"),
    ("M13 source-type diversity counts raw strings",
     SRC,
     "        raise TaxonomyNotRatifiedError(\n            \"source-type diversity (S-02 input 2)",
     "        return len({r.source_type for r in self._records.values()})\n        raise TaxonomyNotRatifiedError(\n            \"source-type diversity (S-02 input 2)"),
    # -- learnability: M-02 / M-43 ------------------------------------------
    ("M14 trust declared a ratified learning target",
     SRC,
     "def is_learning_target() -> bool:",
     "def is_learning_target() -> bool:\n    return True"),
    ("M15 learning update silently succeeds",
     SRC,
     "    raise LearningTargetNotRatifiedError(LEARNING_TARGET_STATUS)",
     "    return None"),
    # -- N-16 independence ---------------------------------------------------
    ("M16 independence ignores the grouping key",
     SRC,
     "        return self.independence_group or self.source_identifier",
     "        return self.source_identifier"),
    ("M17 independent count counts every record",
     SRC,
     "            return len({r.independence_key for r in self._records.values()})",
     "            return len(self._records)"),
    # -- N-04 / R-01 immutability -------------------------------------------
    ("M18 conflicting re-registration silently overwrites",
     SRC,
     "                    raise SourceImmutableError(",
     "                    return existing  # type: ignore[unreachable]\n                    raise SourceImmutableError("),
    ("M19 trust history truncated to the latest rating",
     SRC,
     "            history.append(rating)",
     "            history.clear()\n            history.append(rating)"),
    ("M20 resolve() returns None instead of raising",
     SRC,
     "                raise SourceNotFoundError(\n                    f\"source {source_identifier!r} does not resolve [N-4]\"\n                )",
     "                return None  # type: ignore[return-value]"),
    # -- gap reporting -------------------------------------------------------
    ("M21 specification gaps hidden",
     SRC,
     "        return {\n            \"source_taxonomy\": TAXONOMY_MARKER,",
     "        return {}\n        return {\n            \"source_taxonomy\": TAXONOMY_MARKER,"),
]


def _run() -> int:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-x", "-q", "tests/test_source.py"],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
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
    backup = ROOT / "validation" / ".source.py.orig"
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
