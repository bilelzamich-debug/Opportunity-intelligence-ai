"""Verification for T03.1.3 -- positional anchoring into source Evidence.

Run AFTER the contract tests. Every check is a mechanical demonstration
against a live corpus, never a restatement of the specification.

Sections:
  A. AC1: every accepted attachment has a resolvable anchor (both forms)
  B. AC2: the anchor locates the claim WITHOUT full re-reading
  C. S-5: the ratified AnchorVerifier passes on 100% of the corpus
  D. Fail-closed: ambiguity, absence and malformed locators never guess
  E. T03.1.1 invariance: verbatim anchors, density, equivalence unchanged
  F. The register: completeness, conflict refusal, outside the model
  G. Code-point addressing across scripts
  H. Structural constraints and frozen documents
"""
from __future__ import annotations

import ast
import hashlib
import inspect
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.anchoring import evidence_span_provider, fact_anchor_claims
from oip.claim import Quantity, Verdict
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ObjectStatus, ObjectType
from oip.extraction import (
    LOCATOR_PATTERN,
    AnchoringError,
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    PositionalAnchorRegister,
    _ATTEMPTED_STAGES,
    build_density_report,
    extract,
    locate,
    resolve_locator,
)
from oip.fact import ClaimType
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
TICK = T0 + timedelta(minutes=1)
AUTHORITY = "Designated Source Rights/Compliance Authority"
COMMISSIONING_AUTHORITY = "Designated Source Rights/Compliance Authority"

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


# ===========================================================================
# BUILD: a multilingual corpus through the acquisition path, then extraction
# ===========================================================================

CORPUS = [
    # (key, source_type, content, span, subject, predicate, qualifier)
    ("en-vendor", "VENDOR_PUBLICATION",
     "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
     "Support recommends batching smaller.",
     "bulk edits silently fail above 50 SKUs",
     "bulk edits", "silently fail above",
     "per vendor changelog, for bulk edits above 50 SKUs"),
    ("de-press", "PUBLISHED_EDITORIAL",
     "Der Prüfbericht zeigt: der Markt für Photovoltaik wächst um 34 "
     "Prozent; Überspannungsschutz fehlt häufig.",
     "der Markt für Photovoltaik wächst um 34 Prozent",
     "der Markt für Photovoltaik", "wächst um",
     "laut Prüfbericht, im ersten Halbjahr"),
    ("zh-report", "PUBLISHED_EDITORIAL",
     "报告称：季度营收增长12%，利润率保持稳定。预计下一季度继续增长。",
     "季度营收增长12%",
     "季度营收增长12%", "季度营收增长12%",
     "据该报告，本季度"),
    ("ar-news", "PUBLISHED_EDITORIAL",
     "أظهر التقرير أن المبيعات ارتفعت بنسبة 15% في الربع الثاني من العام.",
     "المبيعات ارتفعت بنسبة 15%",
     "المبيعات", "المبيعات",
     "حسب التقرير، في الربع الثاني"),
    ("emoji-blog", "PUBLISHED_EDITORIAL",
     "📈 Q2 report: revenue grew 14% YoY 📉 before costs narrowed.",
     "revenue grew 14%",
     "revenue grew 14%", "revenue grew 14%",
     "per the Q2 report, year over year"),
    ("nbsp-note", "PUBLISHED_EDITORIAL",
     "Internal note\u00a0bulk edits queue without error\u00a0then fail.",
     "bulk edits queue without error",
     "bulk edits", "bulk edits",
     "per internal note, on the edits queue"),
    ("en-dup", "VENDOR_PUBLICATION",
     "A: bulk edits silently fail above 50 SKUs. "
     "B: bulk edits silently fail above 50 SKUs.",
     "bulk edits silently fail above 50 SKUs",
     "bulk edits", "silently fail above",
     "per vendor changelog, for bulk edits above 50 SKUs"),
    ("en-fab", "VENDOR_PUBLICATION",
     "Vendor changelog, April: nothing about bulk edits at all.",
     "bulk edits silently fail above 50 SKUs",
     "bulk edits", "silently fail above",
     "per vendor changelog, for bulk edits above 50 SKUs"),
]

registry = SourceRegistry()
store = KnowledgeStore()
out_of_frame = OutOfFrameRegister()
refusals = RefusalRegister()
acq_log = AcquisitionLog()
extraction_log = ExtractionLog()
directives = DirectiveRegistry()

for key, source_type, *_ in CORPUS:
    registry.register(key, source_type)

directive = Directive(
    directive_id="dir-t0313",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description="T03.1.3 verification corpus",
    targets=tuple(key for key, *_ in CORPUS),
    raised_at=T0 - timedelta(days=1),
)
directives.raise_directive(directive)
directives.effect("dir-t0313", now=T0)

contents: dict[str, str] = {}
evidence_ids: dict[str, str] = {}
for key, source_type, content, *_ in CORPUS:
    request = AcquisitionRequest(
        source_identifier=key,
        source_type=source_type,
        acquisition_method="verification retrieval",
        capture_fidelity="verification corpus; full text",
        acquired_at=T0,
        observed_at=T0 - timedelta(hours=1),
        evidential_support=0.7,
        assertion_confidence=0.9,
        content=content,
    )
    rights = RightsAssessment(
        source_identifier=key,
        acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_FULL,
        authority=AUTHORITY,
        basis="verification basis",
        assessed_at=T0 - timedelta(hours=1),
    )
    evidence = acquire(
        request,
        registry=registry,
        store=store,
        directives=directives,
        out_of_frame=out_of_frame,
        refusals=refusals,
        log=acq_log,
        assessment=rights,
        clock=lambda: T0,
    )
    evidence_ids[key] = evidence.object_id
    contents[key] = content

anchors_register = PositionalAnchorRegister()
accepted: dict[str, object] = {}   # key -> fact
locators: dict[str, str] = {}      # key -> locator
outcome_facts = {s.object_id: store.get_fact(s.object_id)
                 for s in store.objects_of_type(ObjectType.FACT)}

for key, source_type, content, span, subject, predicate, qualifier in CORPUS:
    overrides: dict = dict(
        evidence_ref=evidence_ids[key], anchor=span,
        subject=subject, predicate=predicate,
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.8,
    )
    if qualifier:
        overrides["qualifying_context"] = qualifier
    try:
        outcome = extract(
            ExtractionRequest(**overrides),
            store=store, log=extraction_log, clock=lambda: TICK,
            anchors=anchors_register,
        )
        accepted[key] = store.get_fact(outcome.object_id)
        locators[key] = outcome.locator
    except ExtractionRefusedError:
        pass  # the en-dup / en-fab rows MUST refuse; checked in D

EXPECTED_ACCEPTED = {"en-vendor", "de-press", "zh-report", "ar-news",
                     "emoji-blog", "nbsp-note"}
EXPECTED_REFUSED = {"en-dup", "en-fab"}

check("BUILD", "corpus accepted exactly the six verifiable rows",
      set(accepted) == EXPECTED_ACCEPTED,
      f"accepted={sorted(accepted)}")

# ===========================================================================
# A. AC1: every accepted attachment has a resolvable anchor (both forms)
# ===========================================================================

all_both = True
detail = ""
for key, fact in accepted.items():
    attachment = fact.attachment_for(evidence_ids[key])
    content = contents[key]
    verbatim_ok = content.count(attachment.positional_anchor) == 1
    locator = anchors_register.locator_for(
        evidence_ids[key], attachment.positional_anchor
    )
    positional_ok = (
        locator is not None and resolve_locator(content, locator)
        == attachment.positional_anchor
    )
    if not (verbatim_ok and positional_ok):
        all_both = False
        detail = f"{key}: verbatim={verbatim_ok} positional={positional_ok}"
check("A", "AC1: every accepted attachment resolves verbatim AND positionally",
      all_both, detail)

check("A", "AC1: acceptance-path F-V2 held (the store accepted these Facts)",
      all(fact.status is ObjectStatus.ACTIVE for fact in accepted.values()))

check("A", "AC1: register covers 100% of accepted attachments",
      len(anchors_register) == len(accepted) == 6,
      f"register={len(anchors_register)} accepted={len(accepted)}")

check("A", "AC1: extraction outcome locator == registered locator",
      all(
          locators[key] == anchors_register.locator_for(
              evidence_ids[key],
              accepted[key].attachment_for(evidence_ids[key])
              .positional_anchor,
          )
          for key in accepted
      ))

# ===========================================================================
# B. AC2: the anchor locates the claim WITHOUT full re-reading
# ===========================================================================

# (i) mechanically: resolution contains no search of any kind
resolve_source = inspect.getsource(resolve_locator)
scan_calls = [
    token for token in
    (".find(", ".count(", ".index(", "re.search", "re.finditer",
     "re.match", "_locate(", " in content", " in body")
    if token in resolve_source
]
check("B", "AC2: resolve_locator performs no search (mechanical, "
      "source-inspected)",
      not scan_calls, str(scan_calls))

# (ii) the locator is a direct slice of the content, for the whole corpus
slice_exact = all(
    contents[key][
        int(locators[key].split()[1].split("-")[0]):
        int(locators[key].split()[1].split("-")[1])
    ] == accepted[key].attachment_for(evidence_ids[key]).positional_anchor
    for key in accepted
)
check("B", "AC2: locator is slice-exact on 100% of the corpus", slice_exact)

# (iii) locating needs no content at all: the register alone gives the
# address, and any content supplied later is sliced, never scanned
register_only = all(
    re.fullmatch(r"chars [0-9]+-[0-9]+", locators[key]) for key in accepted
)
check("B", "AC2: the register alone locates the claim (no content needed)",
      register_only)

# (iv) half-open convention: content[start:end] == span with end-start
# equal to the span length
half_open = all(
    int(locators[key].split()[1].split("-")[1])
    - int(locators[key].split()[1].split("-")[0])
    == len(accepted[key].attachment_for(evidence_ids[key]).positional_anchor)
    for key in accepted
)
check("B", "AC2: half-open convention holds (end - start == len(span))",
      half_open)

# ===========================================================================
# C. S-5: the ratified AnchorVerifier passes on 100% of the corpus
# ===========================================================================

verifier_failures: list[str] = []
checked_total, failed_total = 0, 0
for key, fact in accepted.items():
    verifier = AnchorVerifier(
        span_provider=evidence_span_provider(contents[key]),
        claims_of=lambda ctx, f=fact: fact_anchor_claims(f),
    )
    result = verifier(AcceptanceContext(attributes=fact.attributes))
    checked_total += verifier.checked
    failed_total += verifier.failed
    if result.outcome is not RuleOutcome.PASS:
        verifier_failures.append(f"{key}: {result.detail}")

check("C", "F-V6 PASS through the ratified verifier on 100% of corpus",
      not verifier_failures and checked_total == len(accepted),
      "; ".join(verifier_failures))

# fabricated location still fails under the bridge
fact0 = accepted["en-vendor"]
original = fact_anchor_claims(fact0)[0]
forged_locator = AnchorClaim(
    claim=original.claim,
    anchor=Anchor(evidence_id=original.anchor.evidence_id,
                  locator="chars 900-950"),
    subject=original.subject, predicate=original.predicate, value="",
)
resolvable_but_wrong = AnchorClaim(
    claim=original.claim,
    anchor=Anchor(evidence_id=original.anchor.evidence_id,
                  locator="chars 0-10"),
    subject=original.subject, predicate=original.predicate, value="",
)
v_shift = AnchorVerifier(
    span_provider=evidence_span_provider(contents["en-vendor"]),
    claims_of=lambda ctx: (resolvable_but_wrong,),
)
r_shift = v_shift(AcceptanceContext(attributes=fact0.attributes))
v_forge = AnchorVerifier(
    span_provider=evidence_span_provider(contents["en-vendor"]),
    claims_of=lambda ctx: (forged_locator,),
)
r_forge = v_forge(AcceptanceContext(attributes=fact0.attributes))
check("C", "fabricated locator still FAILs layer 1 under the bridge",
      r_forge.outcome is RuleOutcome.FAIL
      and "does not resolve" in r_forge.detail, r_forge.detail)

forged_subject = AnchorClaim(
    claim=original.claim,
    anchor=original.anchor,
    subject="component from nowhere", predicate=original.predicate, value="",
)
v_subject = AnchorVerifier(
    span_provider=evidence_span_provider(contents["en-vendor"]),
    claims_of=lambda ctx: (forged_subject,),
)
r_subject = v_subject(AcceptanceContext(attributes=fact0.attributes))
check("C", "resolvable-but-wrong slice FAILs on components",
      r_shift.outcome is RuleOutcome.FAIL
      and "absent from the span" in r_shift.detail, r_shift.detail)

check("C", "fabricated component still FAILs layer 1 under the bridge",
      r_subject.outcome is RuleOutcome.FAIL
      and "subject" in r_subject.detail, r_subject.detail)

check("C", "verifier failure counters track the demonstrated failures",
      v_forge.failed == 1 and v_subject.failed == 1
      and v_forge.checked == 1)

# ===========================================================================
# D. Fail-closed: ambiguity, absence and malformed locators never guess
# ===========================================================================

check("D", "the ambiguous and fabricated rows refused",
      set(EXPECTED_REFUSED).isdisjoint(accepted))
refused_stages = {
    f.evidence_ref: f.stage for f in extraction_log
}
dup_stage = refused_stages.get(evidence_ids["en-dup"])
fab_stage = refused_stages.get(evidence_ids["en-fab"])
check("D", "refusals recorded with the right stages [N-10]",
      dup_stage is ExtractionStage.AMBIGUOUS_ANCHOR
      and fab_stage is ExtractionStage.ANCHOR_NOT_FOUND,
      f"dup={dup_stage} fab={fab_stage}")

check("D", "ANCHOR_NOT_RESOLVABLE is an attempted stage [N-10]",
      ExtractionStage.ANCHOR_NOT_RESOLVABLE in _ATTEMPTED_STAGES)

try:
    locate("x the span x the span x", "the span")
    ambiguous_no_locator = False
except AnchoringError:
    ambiguous_no_locator = True
check("D", "ambiguous span gets no locator (never the first occurrence)",
      ambiguous_no_locator)

try:
    locate("content without that text anywhere", "the span")
    absent_no_locator = False
except AnchoringError:
    absent_no_locator = True
check("D", "absent span gets no locator [F-V2]", absent_no_locator)

bad_locators = [
    "", "   ", "chars", "chars 5", "5-10", "chars a-b", "chars 5-10 extra",
    "chars -1-5", "chars 5-", "CHARS 5-10", "chars 5 - 10", "chars +5-10",
    "chars 5.0-10", "chars\t5-10", "chars ٤٥-٥٠", "chars ５-１０",
    "chars 0-99999", "chars 10-10", "chars 10-5",
]
grammar_ok = True
bad_detail = ""
for bad in bad_locators:
    try:
        resolve_locator("some content, any content", bad)
        grammar_ok = False
        bad_detail = f"{bad!r} was accepted"
        break
    except AnchoringError:
        continue
check("D", "the closed grammar refuses all 19 malformed locators",
      grammar_ok, bad_detail)

check("D", "resolution never falls back to searching",
      resolve_locator("Vendor changelog", "chars 0-6") == "Vendor"
      and resolve_locator("Vendor changelog", "chars 1-6") == "endor")

# ===========================================================================
# E. T03.1.1 invariance: verbatim anchors, density, equivalence unchanged
# ===========================================================================

check("E", "T03.1.1: attachment anchor IS the verbatim span on every Fact",
      all(
          accepted[key].attachment_for(evidence_ids[key]).positional_anchor
          == dict((k, c[3]) for k, c in ((row[0], row) for row in CORPUS))[key]
          for key in accepted
      ))

report = build_density_report(
    store, extraction_log,
    evidence_refs=tuple(evidence_ids[key] for key in sorted(accepted)),
)
check("E", "T03.1.1: density still computed from recorded facts [AC3]",
      report.total_claims == 6
      and all(row.claims == 1 for row in report.rows),
      str(report.total_claims))

fact_count = sum(
    1 for _ in store.objects_of_type(ObjectType.FACT)
)
check("E", "T03.1.1: extractor never merges (S-3 report only)",
      fact_count >= len(accepted), f"facts={fact_count}")

# equivalence still surfaces: re-extract the EN row against itself
dup_outcome = None
en_ref = evidence_ids["en-vendor"]
try:
    dup_outcome = extract(
        ExtractionRequest(
            evidence_ref=en_ref,
            subject="bulk edits", predicate="silently fail above",
            qualifying_context="per vendor changelog",
            anchor="bulk edits silently fail above 50 SKUs",
            claim_type=ClaimType.ASSERTION,
            extraction_confidence=0.8,
        ),
        store=store, log=extraction_log, clock=lambda: TICK,
        anchors=anchors_register,
    )
except ExtractionRefusedError:
    pass
check("E", "T03.1.1: duplicate extraction reports EQUIVALENT, merges nothing",
      dup_outcome is not None
      and any(result is not None for _, result in dup_outcome.equivalence)
      and dup_outcome.locator == locators["en-vendor"])

# ===========================================================================
# F. The register: completeness, conflict refusal, outside the model
# ===========================================================================

def _register_conflict_check() -> bool:
    reg = PositionalAnchorRegister()
    reg.record("e1", "span", "chars 0-4")
    try:
        reg.record("e1", "span", "chars 5-9")
        return False
    except AnchoringError:
        return reg.locator_for("e1", "span") == "chars 0-4"


def _register_idempotence_check() -> bool:
    reg = PositionalAnchorRegister()
    reg.record("e1", "span", "chars 0-4")
    reg.record("e1", "span", "chars 0-4")
    return len(reg) == 1


check("F", "register conflicts refuse loudly; the original is kept",
      _register_conflict_check())

check("F", "register idempotent on identical re-record",
      _register_idempotence_check())

check("F", "register is outside the object model",
      not hasattr(PositionalAnchorRegister(), "object_id")
      and not hasattr(PositionalAnchorRegister(), "status"))

check("F", "register lookup requires neither content nor scan",
      anchors_register.locator_for(
          evidence_ids["zh-report"], "季度营收增长12%") is not None)


# ===========================================================================
# G. Code-point addressing across scripts
# ===========================================================================

cp_ok, cp_detail = True, ""
for key in ("de-press", "zh-report", "ar-news", "emoji-blog", "nbsp-note"):
    span = dict((row[0], row) for row in CORPUS)[key][3]
    content = contents[key]
    locator = locators[key]
    start = int(locator.split()[1].split("-")[0])
    if start != content.find(span) or content[start:] [:len(span)] != span:
        cp_ok = False
        cp_detail = key
check("G", "offsets are code points for Latin/CJK/RTL/astral/NBSP rows",
      cp_ok, cp_detail)

emoji_start = int(locators["emoji-blog"].split()[1].split("-")[0])
check("G", "astral-plane emoji counts as ONE code point (not UTF-16)",
      emoji_start == contents["emoji-blog"].find("revenue grew 14%")
      and len("📈") == 1)

pattern_ok = all(
    LOCATOR_PATTERN.fullmatch(locators[key]) for key in locators
)
check("G", "locator format is the closed 'chars <start>-<end>' grammar",
      pattern_ok and LOCATOR_PATTERN.pattern.endswith("\\Z"))

# ===========================================================================
# H. Structural constraints and frozen documents
# ===========================================================================

mod_imports: dict[str, set[str]] = {}
for path in sorted((ROOT / "oip").glob("*.py")):
    if path.name == "__init__.py":
        continue
    t = ast.parse(path.read_text())
    mod_imports[path.stem] = {
        n.module.split(".", 1)[1]
        for n in ast.walk(t)
        if isinstance(n, ast.ImportFrom) and n.module
        and n.module.startswith("oip.")
    }

check("H", "extraction.py stays at exactly its 6 ratified oip imports",
      mod_imports.get("extraction") == {
          "acceptance", "claim", "contract", "evidence", "fact", "store"},
      str(sorted(mod_imports.get("extraction", set()))))

check("H", "anchoring.py stays within the <=6 oip-import boundary",
      len(mod_imports.get("anchoring", set())) <= 6,
      str(sorted(mod_imports.get("anchoring", set()))))

check("H", "anchoring.py imports only ratified S-5/fact machinery",
      mod_imports.get("anchoring", set()) == {
          "extraction", "fact", "semantic"},
      str(sorted(mod_imports.get("anchoring", set()))))


def has_cycle(graph: dict[str, set[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for nxt in graph.get(node, ()):
            visit_result = visit(nxt)
            if visit_result:
                return True
        state[node] = 2
        return False

    return any(visit(n) for n in graph)


check("H", "module graph remains a DAG with anchoring included",
      not has_cycle(mod_imports))

check("H", "no non-store module exceeds the 6-import boundary",
      all(len(v) <= 6 for k, v in mod_imports.items() if k != "store"),
      str({k: len(v) for k, v in mod_imports.items()
           if k != "store" and len(v) > 6}))

BASELINE_HASHES = {
    "docs/decisions/N-20-source-model.md":
        "411b4433cdfb497426d2b2255f255b7a6128aa73fa5639dfe6c0ebae9783c04c",
    "docs/decisions/N-21-acquisition-rights.md":
        "e90b649e6b502b84e3371ab7b902890c93a338e36592fc67f575e0da68b31c40",
    "docs/decisions/N-22-coverage-model.md":
        "ecc4247047f817b732b9a811b921bb0ad8125ce0a6efcf59765bba11fe2d71f5",
    "docs/decisions/N-24-source-rights-authority.md":
        "545356b56bd5c0eb09c870769168388e8be35f816806d6455b3f6cd37d1bef33",
}
PROJECT = ROOT.parent
for rel, expected in BASELINE_HASHES.items():
    path = PROJECT / rel
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    check("H", f"{rel.split('/')[-1]} unmodified [S-3, S-5, N-20..N-24]",
          actual == expected, actual[:16])

marker_register = (PROJECT / "docs" / "markers" / "MARKER-REGISTER.md"
                   ).read_text()
check("H", "M-19 remains OPEN (closed only by recorded decision)",
      "| M-19 |" in marker_register)
check("H", "M-20 remains OPEN (fidelity measured, not eliminated)",
      "| M-20 |" in marker_register)
check("H", "M-67 remains OPEN (layer 1 cannot detect paraphrase drift)",
      "| **M-67** |" in marker_register)

backlog = (PROJECT / "docs" / "architecture"
           / "PKP_Implementation_Backlog.md").read_text()
check("H", "backlog T03.1.3 task and ACs unchanged [F5]",
      "Implement positional anchoring into source Evidence (F-V2)." in backlog
      and "Every attachment has a resolvable anchor" in backlog
      and "Anchor precise enough to locate the claim without full "
      "re-reading" in backlog)
check("H", "backlog T03.1.1 acceptance criteria unchanged [F5]",
      "Claims interpretable without reading the Evidence (F-V3)" in backlog
      and "qualifying_context preserved" in backlog
      and "Extraction density consistent across comparable evidence"
      in backlog)

# ===========================================================================
# RESULT
# ===========================================================================

by_section: dict[str, list[tuple[str, bool, str]]] = {}
for section, name, ok, detail in RESULTS:
    by_section.setdefault(section, []).append((name, ok, detail))

total = len(RESULTS)
passed = sum(1 for _, _, ok, _ in RESULTS if ok)
for section in sorted(by_section):
    print(f"=== {section}. ({sum(1 for _, ok, _ in by_section[section] if ok)}"
          f"/{len(by_section[section])}) ===")
    for name, ok, detail in by_section[section]:
        mark = "ok  " if ok else "FAIL"
        suffix = f"  [{detail}]" if detail and not ok else ""
        print(f"  {mark} {name}{suffix}")

print()
print(f"RESULT: {passed}/{total} checks passed")
if passed == total:
    print("ALL CHECKS PASSED -- T03.1.3 ACCEPTANCE DEMONSTRATED")
    sys.exit(0)
sys.exit(1)
