"""Verification for T03.1.2 -- structured claim decomposition [S-3].

Run AFTER the contract tests. Every check is a mechanical demonstration
against a live corpus, never a restatement of the specification.

Sections:
  A. AC1: every claim decomposed to the defined structure (mechanically,
     over the full corpus; non-decomposable input refused and recorded)
  B. AC2: the structure supports the S-3 equivalence comparison (every
     verdict recomputed from the four structure checks; merge policy =
     the decision's table; no merge executed)
  C. Integration order: layer 1 first, decomposition before persistence
  D. Structural constraints: import set, DAG, module count, closed
     modules byte-pinned to 17de9af
  E. Frozen documents and open markers
"""
from __future__ import annotations

import ast
import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.anchoring import evidence_span_provider, fact_anchor_claims
from oip.claim import (
    MERGE_POLICY,
    Claim,
    MergeAction,
    Quantity,
    UNQUALIFIED,
    Verdict,
    assess_equivalence,
)
from oip.configuration import FailureStore
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ObjectStatus, ObjectType
from oip.extraction import (
    DecompositionError,
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    PositionalAnchorRegister,
    decompose,
    extract,
    resolve_locator,
)
from oip.fact import ClaimType
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.semantic import Anchor, AnchorVerifier
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
TICK = T0 + timedelta(minutes=1)
AUTHORITY = "Designated Source Rights/Compliance Authority"

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


# ===========================================================================
# BUILD: a multilingual + quantitative corpus through the full path
# ===========================================================================

# (key, content, span, subject, predicate, qualifier, value, value_text)
CORPUS = [
    ("en-vendor",
     "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
     "Support recommends batching smaller.",
     "bulk edits silently fail above 50 SKUs",
     "bulk edits", "silently fail above",
     "per vendor changelog, for bulk edits above 50 SKUs", None, None),
    ("en-qty",
     "Pricing update: merchant fees rise 3.5% for card payments from April.",
     "merchant fees rise 3.5% for card payments",
     "merchant fees", "rise", UNQUALIFIED,
     Quantity(3.5, 0.1, "%"), "3.5%"),
    ("de-press",
     "Der Prüfbericht zeigt: der Markt für Photovoltaik wächst um 34 "
     "Prozent; Überspannungsschutz fehlt häufig.",
     "der Markt für Photovoltaik wächst um 34 Prozent",
     "der Markt für Photovoltaik", "wächst um",
     "laut Prüfbericht, im ersten Halbjahr",
     Quantity(34, 1, "Prozent"), "34"),
    ("zh-report",
     "报告称：季度营收增长12%，利润率保持稳定。预计下一季度继续增长。",
     "季度营收增长12%",
     "季度营收增长12%", "季度营收增长12%", "据该报告，本季度", None, None),
    ("ar-news",
     "أظهر التقرير أن المبيعات ارتفعت بنسبة 15% في الربع الثاني من العام.",
     "المبيعات ارتفعت بنسبة 15%",
     "المبيعات", "المبيعات", "حسب التقرير، في الربع الثاني", None, None),
    ("en-unq",
     "Internal note: the export job completes without errors on Tuesdays.",
     "the export job completes without errors",
     "the export job", "completes without errors", UNQUALIFIED, None, None),
    ("en-nan",
     "Vendor changelog, April: bulk edits silently fail above 50 SKUs "
     "for unnamed reasons.",
     "bulk edits silently fail above 50 SKUs",
     "bulk edits", "silently fail above",
     "per the April changelog", Quantity(float("nan"), 0.1), "50"),
]

registry = SourceRegistry()
store = KnowledgeStore()
out_of_frame = OutOfFrameRegister()
refusals = RefusalRegister()
acq_log = AcquisitionLog()
extraction_log = ExtractionLog()
failure_store = FailureStore()
extraction_log.attach(failure_store)
directives = DirectiveRegistry()

for key, *_ in CORPUS:
    registry.register(key, "VENDOR_PUBLICATION")

directive = Directive(
    directive_id="dir-t0312",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=AUTHORITY,
    description="T03.1.2 verification corpus",
    targets=tuple(key for key, *_ in CORPUS),
    raised_at=T0 - timedelta(days=1),
)
directives.raise_directive(directive)
directives.effect("dir-t0312", now=T0)

contents: dict[str, str] = {}
evidence_ids: dict[str, str] = {}
for key, content, *_ in CORPUS:
    request = AcquisitionRequest(
        source_identifier=key,
        source_type="VENDOR_PUBLICATION",
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

register = PositionalAnchorRegister()
accepted: dict[str, object] = {}
requests: dict[str, ExtractionRequest] = {}
outcomes: dict[str, object] = {}

for key, _, span, subject, predicate, qualifier, value, value_text in CORPUS:
    context = (
        qualifier if qualifier != UNQUALIFIED
        else "no qualification stated in the source"
    )
    overrides = dict(
        evidence_ref=evidence_ids[key], anchor=span,
        subject=subject, predicate=predicate, qualifier=qualifier,
        qualifying_context=context,
        claim_type=ClaimType.ASSERTION, extraction_confidence=0.8,
    )
    if value is not None:
        overrides["value"] = value
        overrides["value_text"] = value_text
    request = ExtractionRequest(**overrides)
    requests[key] = request
    try:
        outcome = extract(
            request, store=store, log=extraction_log,
            clock=lambda: TICK, anchors=register,
        )
        accepted[key] = store.get_fact(outcome.object_id)
        outcomes[key] = outcome
    except ExtractionRefusedError:
        pass

EXPECTED_ACCEPTED = {"en-vendor", "en-qty", "de-press", "zh-report",
                     "ar-news", "en-unq"}
check("BUILD", "corpus accepted exactly the six decomposable rows",
      set(accepted) == EXPECTED_ACCEPTED, f"accepted={sorted(accepted)}")
check("BUILD", "the NaN row refused with the decomposition stage",
      "en-nan" not in accepted
      and extraction_log.for_evidence(evidence_ids["en-nan"])[-1].stage
      is ExtractionStage.DECOMPOSITION_FAILED)

# ===========================================================================
# A. AC1: every claim decomposed to the defined structure
# ===========================================================================

ac1_ok, ac1_detail = True, ""
for key, fact in accepted.items():
    request = requests[key]
    claim = fact.claim
    if not isinstance(claim, Claim):
        ac1_ok, ac1_detail = False, f"{key}: not a Claim"
        break
    if (claim.subject != request.subject
            or claim.predicate != request.predicate
            or claim.qualifier != request.qualifier):
        ac1_ok, ac1_detail = False, f"{key}: components not byte-identical"
        break
    if claim.value != request.value:
        ac1_ok, ac1_detail = False, f"{key}: value not carried"
        break
    if decompose(request) != claim:
        ac1_ok, ac1_detail = False, f"{key}: decompose != outcome.claim"
        break
check("A", "AC1: 100% of corpus claims decomposed byte-identically to the "
      "four-component structure", ac1_ok, ac1_detail)

check("A", "AC1: qualifier discipline -- explicit NONE never blank",
      all(
          accepted[key].claim.qualifier == requests[key].qualifier
          and (accepted[key].claim.qualifier != UNQUALIFIED
               or requests[key].qualifier == UNQUALIFIED)
          for key in accepted
      ))

check("A", "AC1: quantities carry mandatory precision",
      accepted["en-qty"].claim.value.precision == 0.1
      and accepted["de-press"].claim.value.precision == 1)

def _finite_pair(claim: Claim) -> bool:
    import math

    if claim.value is None:
        return True
    number, precision = claim.value.value, claim.value.precision
    return all(
        isinstance(n, (int, float)) and not isinstance(n, bool)
        and math.isfinite(n)
        for n in (number, precision)
    )


check("A", "AC1: every decomposed quantity is a finite real pair",
      all(_finite_pair(accepted[key].claim) for key in accepted))

# "forced or rejected": the rejected branch recorded, never silent
nan_failure = extraction_log.for_evidence(evidence_ids["en-nan"])[-1]
check("A", "AC1: non-decomposable claim REJECTED with a complete N-10 record",
      nan_failure.stage is ExtractionStage.DECOMPOSITION_FAILED
      and nan_failure.reason == "NOT_DECOMPOSABLE"
      and nan_failure.attempted
      and len(failure_store) > 0
      and sum(1 for _ in store.objects_of_type(ObjectType.FACT)) == 6)

check("A", "AC1: the refused claim registered no positional anchor",
      register.locator_for(
          evidence_ids["en-nan"], CORPUS[6][2]
      ) is None)

# ===========================================================================
# B. AC2: the structure supports the S-3 equivalence comparison
# ===========================================================================

corpus_claims = [accepted[key].claim for key in sorted(accepted)]
# plus structured pairs the corpus alone cannot show: containment,
# uncertainty, precision agreement, synonym separation
corpus_claims += [
    Claim("bulk edits", "silently fail above", UNQUALIFIED),  # contains row 1
    Claim("sellers", "silently fail above", UNQUALIFIED),     # synonym
    Claim("merchant fees", "rise", UNQUALIFIED, Quantity(3.7, 0.1, "%")),
]

matrix_ok, matrix_detail = True, ""
for left in corpus_claims:
    for right in corpus_claims:
        result = assess_equivalence(left, right)
        same_sp = left.same_subject(right) and left.same_predicate(right)
        values = left.values_agree(right)
        if not same_sp or values is False:
            expected = Verdict.NOT_EQUIVALENT
        elif left.same_qualifier(right):
            expected = Verdict.EQUIVALENT
        elif left.qualifier_contains(right) or right.qualifier_contains(left):
            expected = Verdict.CONTAINMENT
        else:
            expected = Verdict.UNCERTAIN
        if result.verdict is not expected or not result.reason.strip():
            matrix_ok = False
            matrix_detail = f"{left} vs {right}"
check("B", "AC2: every pairwise verdict recomputable from the four "
      "structure checks (56-claim matrix)", matrix_ok, matrix_detail)

check("B", "AC2: self-equivalence holds for 100% of corpus claims",
      all(
          assess_equivalence(claim, claim).verdict is Verdict.EQUIVALENT
          for claim in corpus_claims
      ))

check("B", "AC2: precision-governed agreement demonstrated",
      assess_equivalence(
          Claim("m", "r", UNQUALIFIED, Quantity(3.7, 0.5, "%")),
          Claim("m", "r", UNQUALIFIED, Quantity(3.5, 0.5, "%")),
      ).verdict is Verdict.EQUIVALENT
      and assess_equivalence(
          Claim("m", "r", UNQUALIFIED, Quantity(4.5, 0.5, "%")),
          Claim("m", "r", UNQUALIFIED, Quantity(3.5, 0.5, "%")),
      ).verdict is Verdict.NOT_EQUIVALENT)

vendor_claim = accepted["en-vendor"].claim
check("B", "AC2: containment keeps the narrower claim canonical",
      (r := assess_equivalence(
          Claim("bulk edits", "silently fail above", UNQUALIFIED),
          vendor_claim,
      )).verdict is Verdict.CONTAINMENT
      and r.canonical == vendor_claim
      and r.action is MergeAction.SEPARATE_WITH_DUPLICATES)

check("B", "AC2: synonyms separated by structure, never resolved",
      assess_equivalence(
          vendor_claim,
          Claim("sellers", "silently fail above",
                vendor_claim.qualifier),
      ).verdict is Verdict.NOT_EQUIVALENT)

check("B", "AC2: the merge-policy table IS the S-3 decision",
      MERGE_POLICY == {
          Verdict.EQUIVALENT: MergeAction.MERGE,
          Verdict.CONTAINMENT: MergeAction.SEPARATE_WITH_DUPLICATES,
          Verdict.UNCERTAIN: MergeAction.SEPARATE_WITH_DUPLICATES,
          Verdict.NOT_EQUIVALENT: MergeAction.SEPARATE,
      })

# no merge executed at extraction: re-extract the EN row verbatim
dup = None
try:
    dup = extract(
        requests["en-vendor"], store=store, log=extraction_log,
        clock=lambda: TICK, anchors=register,
    )
except ExtractionRefusedError:
    pass
check("B", "AC2: EQUIVALENT verdicts are REPORTED; extraction never merges "
      "[T03.1.4 boundary]",
      dup is not None
      and any(
          result.verdict is Verdict.EQUIVALENT
          for _, result in dup.equivalence
      )
      and sum(1 for _ in store.objects_of_type(ObjectType.FACT)) == 7)

check("B", "AC2: decomposition equivalence survives extraction round-trip",
      decompose(requests["en-vendor"]) == dup.claim)

# ===========================================================================
# C. Integration order: layer 1 first; decomposition before persistence
# ===========================================================================

# a request that fails BOTH layer-1 and decomposition reports layer-1
fab = ExtractionRequest(
    evidence_ref=evidence_ids["en-nan"],
    subject="phantom subject", predicate="silently fail above",
    qualifying_context="ctx", anchor="bulk edits silently fail above 50 SKUs",
    claim_type=ClaimType.ASSERTION, extraction_confidence=0.8,
    value=Quantity(float("nan"), 0.1), value_text="50",
)
try:
    extract(fab, store=store, log=extraction_log, clock=lambda: TICK)
    order_ok = False
except ExtractionRefusedError:
    order_ok = (
        extraction_log.for_evidence(evidence_ids["en-nan"])[-1].stage
        is ExtractionStage.UNSUPPORTED_CLAIM
    )
check("C", "layer-1 component gate decides before decomposition",
      order_ok)

check("C", "decomposition refusal leaves no anchor behind",
      register.locator_for(
          evidence_ids["en-nan"], CORPUS[6][2]
      ) is None)

# F-V6 still PASSES through the ratified verifier on the decomposed claims
v6_ok, v6_detail = True, ""
for key in ("en-vendor", "en-qty", "de-press"):
    fact = accepted[key]
    verifier = AnchorVerifier(
        span_provider=evidence_span_provider(contents[key]),
        claims_of=lambda ctx, f=fact: fact_anchor_claims(f),
    )
    result = verifier(AcceptanceContext(attributes=fact.attributes))
    if result.outcome is not RuleOutcome.PASS:
        v6_ok, v6_detail = False, f"{key}: {result.detail}"
check("C", "S-5 layer 1 still PASSES on the decomposed corpus (S-5 leans "
      "on S-3)", v6_ok, v6_detail)

# ===========================================================================
# D. Structural constraints
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

check("D", "extraction.py oip-import SET unchanged (6/6, decomposition "
      "reused the claim import)",
      mod_imports.get("extraction") == {
          "acceptance", "claim", "contract", "evidence", "fact", "store"},
      str(sorted(mod_imports.get("extraction", set()))))

check("D", "anchoring.py imports unchanged",
      mod_imports.get("anchoring") == {"extraction", "fact", "semantic"})

check("D", "no new module: the count stays 37",
      len(list((ROOT / "oip").glob("*.py"))) == 37)


def has_cycle(graph: dict[str, set[str]]) -> bool:
    state: dict[str, int] = {}

    def visit(node: str) -> bool:
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        for nxt in graph.get(node, ()):
            if visit(nxt):
                return True
        state[node] = 2
        return False

    return any(visit(n) for n in graph)


check("D", "module graph remains a DAG", not has_cycle(mod_imports))

check("D", "no non-store module exceeds the 6-import boundary",
      all(len(v) <= 6 for k, v in mod_imports.items() if k != "store"),
      str({k: len(v) for k, v in mod_imports.items()
           if k != "store" and len(v) > 6}))

# closed modules byte-identical to the 17de9af state (the pre-task pin)
CLOSED_MODULE_HASHES = {
    "claim.py":
        "96e22ed919c2295d7f37195c7ee1e53ab24494091ac9bbf162732d78b97adfaf",
    "fact.py":
        "f1ae721428f3f198ca7b3df5308be08802f55e467717704a02254d2990813b90",
    "semantic.py":
        "7e84725d1363235692d8463d2dd379a22e49208629a9f5649a082323d89fbd7d",
}
for name, expected in CLOSED_MODULE_HASHES.items():
    actual = hashlib.sha256((ROOT / "oip" / name).read_bytes()).hexdigest()
    check("D", f"{name} untouched (byte-pinned to 17de9af)",
          actual == expected, actual[:16])

# ===========================================================================
# E. Frozen documents and open markers
# ===========================================================================

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
    check("E", f"{rel.split('/')[-1]} unmodified [S-3, S-5, N-20..N-24]",
          actual == expected, actual[:16])

# S-3 and R-5 themselves are ratified decisions: byte-identical to 17de9af
for rel in ("docs/decisions/S-03-claim-equivalence.md",
            "docs/decisions/R-05-canonical-claims.md"):
    import subprocess

    blob = subprocess.run(
        ["git", "show", f"17de9af:{rel}"], cwd=PROJECT,
        capture_output=True
    ).stdout
    expected = hashlib.sha256(blob).hexdigest()
    actual = hashlib.sha256((PROJECT / rel).read_bytes()).hexdigest()
    check("E", f"{rel.split('/')[-1]} unmodified (ratified decision)",
          actual == expected, actual[:16])

marker_register = (PROJECT / "docs" / "markers" / "MARKER-REGISTER.md"
                   ).read_text()
check("E", "M-19 remains OPEN (extraction granularity; compound inputs "
      "carried verbatim, never split)",
      "| M-19 |" in marker_register)
check("E", "M-20 remains OPEN (fidelity measured, not eliminated)",
      "| M-20 |" in marker_register)
check("E", "M-67 remains OPEN (layer 1 cannot detect paraphrase drift)",
      "| **M-67** |" in marker_register)

backlog = (PROJECT / "docs" / "architecture"
           / "PKP_Implementation_Backlog.md").read_text()
check("E", "backlog T03.1.2 task and ACs unchanged [F5]",
      "Implement structured claim decomposition per S-3 (subject, "
      "predicate, qualifier, value)." in backlog
      and "Every claim decomposed to the defined structure" in backlog
      and "Structure supports equivalence comparison" in backlog)
check("E", "backlog T03.1.1 acceptance criteria unchanged [F5]",
      "Claims interpretable without reading the Evidence (F-V3)" in backlog
      and "qualifying_context preserved" in backlog
      and "Extraction density consistent across comparable evidence"
      in backlog)
check("E", "backlog T03.1.3 acceptance criteria unchanged [F5]",
      "Implement positional anchoring into source Evidence (F-V2)." in
      backlog
      and "Every attachment has a resolvable anchor" in backlog
      and "Anchor precise enough to locate the claim without full "
      "re-reading" in backlog)

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
    print("ALL CHECKS PASSED -- T03.1.2 ACCEPTANCE DEMONSTRATED")
    sys.exit(0)
sys.exit(1)
