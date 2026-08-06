"""Architecture verification for T02.1.1 -- source model.

Establishes mechanically that the implementation supplies exactly what the
ratified corpus authorises and nothing more: that the open markers stay open,
that no vocabulary was invented, that CI-1 isolation holds, and that S-02's
exhaustive input list is not disturbed.

Fails closed: a check that cannot be performed counts as a failure.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT.parent
sys.path.insert(0, str(ROOT))

from oip import source as src_mod  # noqa: E402
from oip.source import (  # noqa: E402
    LEARNING_TARGET_MARKERS, LEARNING_TARGET_STATUS, TAXONOMY_MARKER,
    TAXONOMY_RATIFIED, TRUST_MAXIMUM, TRUST_MINIMUM, SourceEligibility,
    SourceRegistry, SourceType, TrustRating, affects_evidential_support,
    assess_eligibility, is_learning_target, is_ratified_source_type,
    taxonomy_members,
)

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


SRC = (ROOT / "oip" / "source.py").read_text()
TREE = ast.parse(SRC)
V2 = (DOCS / "PKP_v2_Master_Reference.md").read_text()
IOM = (DOCS / "PKP_Intelligence_Object_Model.md").read_text()
S02 = (DOCS / "decisions" / "S-02-evidential-support-function.md").read_text()

# ===========================================================================
# A. Open markers remain open
# ===========================================================================
check("A", "M-16 still open: taxonomy is unpopulated",
      len(list(SourceType)) == 0 and TAXONOMY_RATIFIED is False,
      f"{len(list(SourceType))} members")
check("A", "M-16 still open in the canonical register",
      re.search(r"\|\s*M-16\s*\|\s*Source taxonomy, eligibility, trust model",
                V2) is not None)
# M-16 was OPEN when this verifier was written. N-20 (ratified 2026-08-04)
# closes it PARTIALLY. The invariant that still matters is that the closure is
# partial -- the taxonomy half only -- and that the scoring half stays open.
_m16 = [p for p in (DOCS / "decisions").glob("[ANRS]-*.md")
        if re.search(r"^\|\s*\*\*Closes\*\*.*\bM-16\b", p.read_text(), re.M)]
check("A", "M-16 closed only partially, only by N-20",
      len(_m16) == 1 and _m16[0].stem.startswith("N-20")
      and "partially" in re.search(r"^\|\s*\*\*Closes\*\*\s*\|(.+?)\|",
                                   _m16[0].read_text(), re.M).group(1),
      f"closers={[p.stem for p in _m16]}")
check("A", "eligibility never resolves while M-16 is open",
      assess_eligibility("s").outcome is SourceEligibility.UNDETERMINED)
check("A", "M-02/M-43/M-70 still open: trust is not a learning target",
      is_learning_target() is False
      and set(LEARNING_TARGET_MARKERS) == {"M-02", "M-43", "M-70"})
check("A", "the learning gap names all three markers",
      all(m in LEARNING_TARGET_STATUS for m in ("M-02", "M-43", "M-70")))
check("A", "M-18 is left to T02.1.2, not implemented here",
      not re.search(r"def .*(licen|robots|rate_limit|terms_of_use)",
                    SRC, re.I),
      "no licensing mechanism may exist in this module")
gaps = SourceRegistry().specification_gaps()
check("A", "every unimplementable capability names its marker",
      set(gaps.values()) >= {"M-16", "M-02", "M-43", "M-70", "M-18", "S-02"},
      str(sorted(set(gaps.values()))))

# ===========================================================================
# B. No invented vocabulary, scale or policy
# ===========================================================================
enum_members: dict[str, list[str]] = {}
for node in ast.walk(TREE):
    if isinstance(node, ast.ClassDef) and any(
        isinstance(b, ast.Name) and b.id == "Enum"
        or isinstance(b, ast.Attribute) and b.attr == "Enum"
        or isinstance(b, ast.Name) and b.id == "str"
        for b in node.bases
    ):
        enum_members[node.name] = [
            t.id for stmt in node.body
            if isinstance(stmt, ast.Assign)
            for t in stmt.targets if isinstance(t, ast.Name)
        ]
check("B", "SourceType declares zero members in source",
      enum_members.get("SourceType", []) == [],
      str(enum_members.get("SourceType")))
# Scan EXECUTABLE code only. The module docstring legitimately cites the
# IOM's example value to explain why the taxonomy is empty; prose that
# documents a gap must not be mistaken for closing it. (Same failure mode as
# the M-36/OQ-11 regexes caught during the Phase 1 closure gate.)
_code_only = ast.parse(SRC)
for _n in ast.walk(_code_only):
    if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and (
        _n.body and isinstance(_n.body[0], ast.Expr)
        and isinstance(_n.body[0].value, ast.Constant)
        and isinstance(_n.body[0].value.value, str)
    ):
        _n.body = _n.body[1:] or [ast.Pass()]
CODE = ast.unparse(_code_only)
_example_values = re.findall(
    r"customer_review_corpus|marketplace_listing|complaint_record|"
    r"public_dataset|editorial_content|vendor_documentation|"
    r"community_forum|regulatory_filing", CODE)
check("B", "no source-type literal appears in executable code",
      not _example_values,
      f"example values leaked into code: {sorted(set(_example_values))}")
check("B", "SourceType has no member assignments in its class body",
      not [st for cd in ast.walk(ast.parse(SRC))
           if isinstance(cd, ast.ClassDef) and cd.name == "SourceType"
           for st in cd.body if isinstance(st, (ast.Assign, ast.AnnAssign))])
check("B", "trust range is inherited, not invented",
      TRUST_MINIMUM == 0.0 and TRUST_MAXIMUM == 1.0
      and "source_reliability" in SRC,
      "must reuse the ratified Evidence source_reliability range")
check("B", "the ratified Evidence contract uses the same range",
      "source_reliability must be in [0.0, 1.0]" in
      (ROOT / "oip" / "evidence.py").read_text())
check("B", "no trust default is materialised",
      not re.search(r"trust.*=\s*0\.5|DEFAULT_TRUST|NEUTRAL_TRUST", SRC, re.I))
check("B", "no threshold or cutoff is invented",
      not re.search(r"THRESHOLD|CUTOFF|MIN_TRUST_FOR|trust\s*[<>]=?\s*0\.[0-9]",
                    SRC),
      "eligibility by trust threshold would invent policy")
check("B", "no scoring formula is present",
      not re.search(r"def .*(score|weight|rank)", SRC, re.I))

# ===========================================================================
# C. S-02 is not disturbed
# ===========================================================================
check("C", "S-02 declares its inputs exhaustive",
      "**No other input.**" in S02)
check("C", "S-02 does not list source trust as an input",
      not re.search(r"\|\s*\d\s*\|\s*\*\*Source trust", S02))
check("C", "trust is declared non-scoring",
      affects_evidential_support() is False)
check("C", "the registry exposes no scoring surface",
      not [n for n in dir(SourceRegistry)
           if not n.startswith("_")
           and any(f in n.lower()
                   for f in ("evidential", "confidence", "score", "weight"))])
check("C", "source-type diversity (S-02 input 2) fails closed",
      "TaxonomyNotRatifiedError" in
      SRC.split("def source_type_diversity")[1][:800],
      "counting raw strings would substitute an uncontrolled vocabulary")

# ===========================================================================
# D. CI-1 isolation and module boundaries
# ===========================================================================
imports = {
    n.module for n in ast.walk(TREE)
    if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
}
check("D", "module imports only oip.contract", imports <= {"oip.contract"},
      str(sorted(imports)))
check("D", "no Intelligence Object type is imported",
      not (imports & {"oip.evidence", "oip.store", "oip.graph",
                      "oip.lineage", "oip.acceptance"}))
check("D", "no lineage attribute on the source record",
      not re.search(r"derives_from|lineage_id|object_id\s*:", SRC))
check("D", "no tenth Intelligence Object is introduced [F8]",
      "ObjectType" not in SRC)
check("D", "records are frozen dataclasses [R-1]",
      SRC.count("@dataclass(frozen=True)") >= 3)
check("D", "registry is lock-guarded [N-11]", "threading.RLock" in SRC)

# ===========================================================================
# E. Module conventions
# ===========================================================================
check("E", "module header names its task", re.search(r"Task: T02\.1\.1", SRC)
      is not None)
check("E", "module header lists Architecture References",
      "Architecture References:" in SRC)
check("E", "module does not claim to close a marker",
      not re.search(r"\bCloses\s*[:|]\s*M-\d+", SRC))
check("E", "the open marker is cited inline", "[M-16]" in SRC)
check("E", "no Phase 1 module was modified",
      __import__("hashlib").md5(
          (ROOT / "oip" / "cascade.py").read_bytes()).hexdigest()
      == "b603ce9ed81d7026f87b7466bdeac080")
check("E", "integrity.py unchanged",
      __import__("hashlib").md5(
          (ROOT / "oip" / "integrity.py").read_bytes()).hexdigest()
      == "42f1a9507b9679a25cfef9321a07fa6a")
check("E", "exactly one production module was added",
      len(list((ROOT / "oip").glob("*.py"))) == 29,
      f"{len(list((ROOT / 'oip').glob('*.py')))} modules")

# ===========================================================================
# F. Acceptance criteria status
# ===========================================================================
check("F", "AC1 taxonomy: structure present, content fails closed",
      hasattr(src_mod, "SourceType") and taxonomy_members() == ()
      and is_ratified_source_type("anything") is False)
check("F", "AC2 trust: recordable, versioned, never defaulted",
      hasattr(SourceRegistry, "record_trust")
      and hasattr(SourceRegistry, "trust_history")
      and hasattr(SourceRegistry, "trust_at_version"))
check("F", "AC2 trust: unrated reports None",
      SourceRegistry().find("absent") is None)
check("F", "AC3 learnability: refused, not faked",
      is_learning_target() is False
      and hasattr(src_mod, "register_learning_update"))

# ===========================================================================
# Report
# ===========================================================================
failed = [(s, n, d) for s, n, ok, d in RESULTS if not ok]
by: dict[str, list] = {}
for s, n, ok, d in RESULTS:
    by.setdefault(s, []).append((n, ok, d))
TITLES = {
    "A": "Open markers remain open",
    "B": "No invented vocabulary, scale or policy",
    "C": "S-02 undisturbed",
    "D": "CI-1 isolation and module boundaries",
    "E": "Module conventions and Phase 1 integrity",
    "F": "Acceptance criteria status",
}
for s in sorted(by):
    entries = by[s]
    ok_n = sum(1 for _, ok, _ in entries if ok)
    print(f"\n=== {s}. {TITLES[s]} ({ok_n}/{len(entries)}) ===")
    for n, ok, d in entries:
        line = f"  {'ok  ' if ok else 'FAIL'} {n}"
        if d and not ok:
            line += f"  -> {d}"
        print(line)
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
if failed:
    print("\nFAILURES:")
    for s, n, d in failed:
        print(f"  [{s}] {n}" + (f"  -> {d}" if d else ""))
sys.exit(1 if failed else 0)
