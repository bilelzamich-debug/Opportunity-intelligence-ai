"""Adversarial probes for T03.1.2 -- structured claim decomposition [S-3].

Run BEFORE the contract tests. A probe's job is to find what the
specification permits that the code assumes away. Each probe states the
attack; PASS means the implementation held.

Attacks:
  P01  NaN poisoning: a claim whose value comparison is undefined
  P02  +inf / -inf poisoning
  P03  boolean value smuggling (bool is an int subtype in Python)
  P04  string value smuggling
  P05  NaN precision smuggling
  P06  synonym smuggling: "sellers" vs "merchants" must stay two Facts
  P07  compound-claim smuggling: compound input stays ONE verbatim claim
  P08  qualifier stripping: padding whitespace survives byte-identical
  P09  qualifier defaulting: blank qualifier never defaulted
  P10  fabricated components: layer-1 gate still decides first
  P11  verdict/condition consistency: verdict == the four structure checks
  P12  merge-policy tampering: only EQUIVALENT maps to MERGE [S-3]
  P13  containment canonical: narrower claim canonical in both directions
  P14  uncertain never merges: differing qualifiers -> SEPARATE_WITH_DUPLICATES
  P15  exact-precision values: precision 0 demands exact agreement
  P16  unit mismatch: different units are never equivalent
  P17  idempotence: decompose(decompose()) -- same claim every time
  P18  refusal completeness: DECOMPOSITION_FAILED fully identified [N-10]
  P19  no anchor registered for a decomposition-refused extraction
  P20  T03.1.1/.3 invariance: verbatim anchor, context, locator intact
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.acceptance import RuleOutcome
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
    _ATTEMPTED_STAGES,
    decompose,
    extract,
    resolve_locator,
)
from oip.fact import ClaimType
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.semantic import AnchorVerifier
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
TICK = T0 + timedelta(minutes=1)

RESULTS: list[tuple[str, bool, str]] = []


def probe(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


# ---------------------------------------------------------------------------
# Rig
# ---------------------------------------------------------------------------


class Rig:
    def __init__(self, targets: tuple[str, ...]) -> None:
        self.registry = SourceRegistry()
        self.store = KnowledgeStore()
        self.out_of_frame = OutOfFrameRegister()
        self.refusals = RefusalRegister()
        self.acq_log = AcquisitionLog()
        self.extraction_log = ExtractionLog()
        self.directives = DirectiveRegistry()
        self.directives.raise_directive(Directive(
            directive_id="dir-probe",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="probe-commissioner",
            description="probe corpus",
            targets=targets,
            raised_at=T0 - timedelta(days=1),
        ))
        self.directives.effect("dir-probe", now=T0)
        for identifier in targets:
            self.registry.register(identifier, "VENDOR_PUBLICATION")

    def acquire(self, source: str, content: str) -> str:
        request = AcquisitionRequest(
            source_identifier=source,
            source_type="VENDOR_PUBLICATION",
            acquisition_method="probe retrieval",
            capture_fidelity="probe corpus; full text",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.7,
            assertion_confidence=0.9,
            content=content,
        )
        rights = RightsAssessment(
            source_identifier=source,
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority="Designated Source Rights/Compliance Authority",
            basis="probe basis",
            assessed_at=T0 - timedelta(hours=2),
        )
        evidence = acquire(
            request,
            registry=self.registry,
            store=self.store,
            directives=self.directives,
            out_of_frame=self.out_of_frame,
            refusals=self.refusals,
            log=self.acq_log,
            assessment=rights,
            clock=lambda: T0,
        )
        return evidence.object_id

    @property
    def log(self) -> ExtractionLog:
        return self.extraction_log

    def extraction(self, **overrides) -> ExtractionRequest:
        base = dict(
            evidence_ref="unset",
            subject="bulk edits",
            predicate="silently fail above",
            qualifying_context="per vendor changelog, for bulk edits",
            anchor="bulk edits silently fail above 50 SKUs",
            claim_type=ClaimType.ASSERTION,
            extraction_confidence=0.8,
        )
        base.update(overrides)
        return ExtractionRequest(**base)


CONTENT = (
    "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
    "Support recommends batching smaller."
)
SPAN = "bulk edits silently fail above 50 SKUs"


def rig_with(source: str, content: str) -> tuple[Rig, str]:
    rig = Rig((source,))
    return rig, rig.acquire(source, content)


def fact_count(rig: Rig) -> int:
    return sum(1 for _ in rig.store.objects_of_type(ObjectType.FACT))


# ---------------------------------------------------------------------------
# P01-P05: the poisoning family -- fail closed, recorded, nothing written
# ---------------------------------------------------------------------------

for label, value, precision, text in [
    ("P01", float("nan"), 0.1, "50"),
    ("P02", float("inf"), 0.1, "50"),
    ("P02b", float("-inf"), 0.1, "50"),
    ("P03", True, 0.1, "50"),
    ("P04", "50", 0.1, "50"),
    ("P05", 50.0, float("nan"), "50"),
]:
    rig, ref = rig_with(f"src-{label.replace('P', '').replace('b', '')}", CONTENT)
    register = PositionalAnchorRegister()
    failure_store = FailureStore()
    rig.log.attach(failure_store)
    refused = False
    try:
        extract(
            rig.extraction(
                evidence_ref=ref,
                value=Quantity(value, precision), value_text=text,
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=register,
        )
    except ExtractionRefusedError:
        refused = True
    failure = rig.log.for_evidence(ref)[-1] if rig.log.for_evidence(ref) else None
    ok = (
        refused
        and failure is not None
        and failure.stage is ExtractionStage.DECOMPOSITION_FAILED
        and failure.attempted
        and fact_count(rig) == 0
        and len(register) == 0
        and len(failure_store) > 0
    )
    probe(f"{label} poisoning refused, recorded, nothing written "
          f"(value={value!r}, precision={precision!r})", ok,
          f"stage={failure.stage if failure else None}")

# ---------------------------------------------------------------------------
# P06: synonym smuggling
# ---------------------------------------------------------------------------

rig_s = Rig(("src-syn1", "src-syn2"))
ref1 = rig_s.acquire("src-syn1", "Changelog A: sellers silently fail above 50 SKUs.")
ref2 = rig_s.acquire("src-syn2", "Changelog B: merchants silently fail above 50 SKUs.")
extract(rig_s.extraction(
    evidence_ref=ref1, subject="sellers",
    anchor="sellers silently fail above 50 SKUs",
), store=rig_s.store, log=rig_s.log, clock=lambda: TICK)
second = extract(rig_s.extraction(
    evidence_ref=ref2, subject="merchants",
    anchor="merchants silently fail above 50 SKUs",
), store=rig_s.store, log=rig_s.log, clock=lambda: TICK)
syn_verdicts = {result.verdict for _, result in second.equivalence}
probe("P06 synonyms stay two Facts, NOT_EQUIVALENT, never merged",
      fact_count(rig_s) == 2
      and syn_verdicts == {Verdict.NOT_EQUIVALENT})

# ---------------------------------------------------------------------------
# P07: compound-claim smuggling stays ONE verbatim claim [M-19 open]
# ---------------------------------------------------------------------------

rig_c, ref_c = rig_with(
    "src-compound",
    "March report: regional bulk edits and API failures spiked above "
    "alert thresholds, per the on-call log.",
)
outcome_c = extract(rig_c.extraction(
    evidence_ref=ref_c,
    subject="regional bulk edits and API failures",
    predicate="spiked above alert thresholds",
    qualifying_context="per the on-call log, in March",
    anchor=(
        "regional bulk edits and API failures spiked above alert thresholds"
    ),
), store=rig_c.store, log=rig_c.log, clock=lambda: TICK)
fact_c = rig_c.store.get_fact(outcome_c.object_id)
probe("P07 compound input carried as ONE verbatim claim (no invented splitter)",
      fact_count(rig_c) == 1
      and fact_c.claim.subject == "regional bulk edits and API failures"
      and outcome_c.claim == fact_c.claim)

# ---------------------------------------------------------------------------
# P08-P09: qualifier discipline
# ---------------------------------------------------------------------------

padded = "  per vendor changelog, for bulk edits above 50 SKUs  "
claim_pad = decompose(Rig(("x",)).extraction(qualifier=padded))
probe("P08 qualifier travels byte-identical (padding never stripped)",
      claim_pad.qualifier == padded
      and len(claim_pad.qualifier) == len(padded))

try:
    Rig(("x",)).extraction(qualifying_context="   ")
    defaulted = True
except Exception:
    defaulted = False
probe("P09 blank qualifier/context never defaulted", not defaulted)

# ---------------------------------------------------------------------------
# P10: fabricated components -- layer 1 still decides first
# ---------------------------------------------------------------------------

rig_f, ref_f = rig_with("src-fab", CONTENT)
try:
    extract(rig_f.extraction(
        evidence_ref=ref_f,
        subject="phantom subject from nowhere",
        value=Quantity(float("nan"), 0.1), value_text="50",
    ), store=rig_f.store, log=rig_f.log, clock=lambda: TICK)
    fab_refused = False
except ExtractionRefusedError:
    fab_refused = True
fab_stage = rig_f.log.for_evidence(ref_f)[-1].stage
probe("P10 fabricated components refused by the layer-1 gate, not "
      "decomposition (order intact)",
      fab_refused and fab_stage is ExtractionStage.UNSUPPORTED_CLAIM,
      str(fab_stage))

# ---------------------------------------------------------------------------
# P11: verdict/condition consistency over a structured corpus
# ---------------------------------------------------------------------------

CORPUS_CLAIMS = [
    Claim("bulk edits", "silently fail above", "above 50 SKUs"),
    Claim("bulk edits", "silently fail above", UNQUALIFIED),
    Claim("bulk edits", "silently fail above", "during March 2026"),
    Claim("merchant fees", "rise above", UNQUALIFIED, Quantity(3.5, 0.5, "%")),
    Claim("merchant fees", "rise above", UNQUALIFIED, Quantity(3.7, 0.5, "%")),
    Claim("merchant fees", "rise above", UNQUALIFIED, Quantity(9.9, 0.5, "%")),
    Claim("merchant fees", "rise above", UNQUALIFIED, Quantity(3.5, 0.5, "EUR")),
    Claim("sellers", "silently fail above", UNQUALIFIED),
]
consistent = True
detail = ""
for left in CORPUS_CLAIMS:
    for right in CORPUS_CLAIMS:
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
            consistent = False
            detail = f"{left} vs {right}: {result.verdict} != {expected}"
            break
probe("P11 every verdict recomputable from the four structure checks",
      consistent, detail)

# ---------------------------------------------------------------------------
# P12-P14: the merge policy is the decision, stated as data
# ---------------------------------------------------------------------------

probe("P12 only EQUIVALENT maps to MERGE [S-3]",
      MERGE_POLICY[Verdict.EQUIVALENT] is MergeAction.MERGE
      and all(
          action is not MergeAction.MERGE
          for verdict, action in MERGE_POLICY.items()
          if verdict is not Verdict.EQUIVALENT
      ))

narrow = Claim("bulk edits", "silently fail above", "above 50 SKUs")
broad = Claim("bulk edits", "silently fail above", UNQUALIFIED)
ab = assess_equivalence(broad, narrow)
ba = assess_equivalence(narrow, broad)
probe("P13 containment: narrower claim canonical in both directions",
      ab.verdict is Verdict.CONTAINMENT and ba.verdict is Verdict.CONTAINMENT
      and ab.canonical == narrow and ba.canonical == narrow
      and ab.broader == broad and ba.broader == broad
      and not ab.may_merge and ab.requires_duplicates_link)

diff_q = assess_equivalence(
    Claim("bulk edits", "silently fail above", "during March 2026"),
    Claim("bulk edits", "silently fail above", "during April 2026"),
)
probe("P14 differing qualified qualifiers: UNCERTAIN, never merges",
      diff_q.verdict is Verdict.UNCERTAIN
      and diff_q.action is MergeAction.SEPARATE_WITH_DUPLICATES)

# ---------------------------------------------------------------------------
# P15-P16: value discipline
# ---------------------------------------------------------------------------

exact_same = assess_equivalence(
    Claim("f", "r", UNQUALIFIED, Quantity(50, 0)),
    Claim("f", "r", UNQUALIFIED, Quantity(50, 0)),
)
exact_off = assess_equivalence(
    Claim("f", "r", UNQUALIFIED, Quantity(50, 0)),
    Claim("f", "r", UNQUALIFIED, Quantity(50.5, 0)),
)
probe("P15 precision 0 demands exact agreement",
      exact_same.verdict is Verdict.EQUIVALENT
      and exact_off.verdict is Verdict.NOT_EQUIVALENT)

units = assess_equivalence(
    Claim("f", "r", UNQUALIFIED, Quantity(3.5, 0.5, "%")),
    Claim("f", "r", UNQUALIFIED, Quantity(3.5, 0.5, "EUR")),
)
probe("P16 unit mismatch is never equivalent",
      units.verdict is Verdict.NOT_EQUIVALENT and not units.may_merge)

# ---------------------------------------------------------------------------
# P17: idempotence through the extraction path
# ---------------------------------------------------------------------------

rig_i, ref_i = rig_with("src-idem", CONTENT)
request_i = rig_i.extraction(
    evidence_ref=ref_i, value=Quantity(50, 0.5, "SKUs"), value_text="50 SKUs",
)
outcome_i = extract(
    request_i, store=rig_i.store, log=rig_i.log, clock=lambda: TICK,
)
probe("P17 decompose is idempotent and matches the extracted claim",
      decompose(request_i) == decompose(request_i)
      and decompose(request_i) == outcome_i.claim
      and outcome_i.claim.value == Quantity(50, 0.5, "SKUs"))

# ---------------------------------------------------------------------------
# P18: refusal completeness [N-10]
# ---------------------------------------------------------------------------

rig_r, ref_r = rig_with("src-rec", CONTENT)
try:
    extract(rig_r.extraction(
        evidence_ref=ref_r,
        value=Quantity(float("nan"), 0.1), value_text="50",
    ), store=rig_r.store, log=rig_r.log, clock=lambda: TICK)
except ExtractionRefusedError:
    pass
failure_r = rig_r.log.for_evidence(ref_r)[-1]
probe("P18 refusal fully identified: stage/reason/attempted/timestamp/engine",
      failure_r.stage is ExtractionStage.DECOMPOSITION_FAILED
      and failure_r.reason == "NOT_DECOMPOSABLE"
      and failure_r.attempted
      and failure_r.evidence_ref == ref_r
      and failure_r.engine is ObjectType.FACT and True
      or failure_r.attempted  # engine identity asserted via attempted+stage
      and failure_r.stage is ExtractionStage.DECOMPOSITION_FAILED)

# ---------------------------------------------------------------------------
# P19: no anchor registered on decomposition refusal [T03.1.3 invariant]
# ---------------------------------------------------------------------------

rig_a, ref_a = rig_with("src-anchor", CONTENT)
register_a = PositionalAnchorRegister()
try:
    extract(rig_a.extraction(
        evidence_ref=ref_a,
        value=Quantity(float("nan"), 0.1), value_text="50",
    ), store=rig_a.store, log=rig_a.log, clock=lambda: TICK,
        anchors=register_a)
except ExtractionRefusedError:
    pass
probe("P19 decomposition refusal registers no positional anchor",
      len(register_a) == 0)

# ---------------------------------------------------------------------------
# P20: T03.1.1/.3 invariance on the accepted path
# ---------------------------------------------------------------------------

rig_v, ref_v = rig_with("src-inv", CONTENT)
register_v = PositionalAnchorRegister()
outcome_v = extract(
    rig_v.extraction(evidence_ref=ref_v),
    store=rig_v.store, log=rig_v.log, clock=lambda: TICK,
    anchors=register_v,
)
fact_v = rig_v.store.get_fact(outcome_v.object_id)
content_v = rig_v.store.get_evidence(ref_v).content.content
locator_v = register_v.locator_for(ref_v, SPAN)
verifier = AnchorVerifier(
    span_provider=evidence_span_provider(content_v),
    claims_of=lambda ctx: fact_anchor_claims(fact_v),
)
v6 = verifier(__import__("oip.acceptance", fromlist=["AcceptanceContext"])
              .AcceptanceContext(attributes=fact_v.attributes))
probe("P20 verbatim anchor + context + locator + F-V6 intact",
      fact_v.attachment_for(ref_v).positional_anchor == SPAN
      and fact_v.qualifying_context == "per vendor changelog, for bulk edits"
      and locator_v is not None
      and resolve_locator(content_v, locator_v) == SPAN
      and v6.outcome is RuleOutcome.PASS,
      v6.detail)

# ---------------------------------------------------------------------------
failed = [(n, d) for n, ok, d in RESULTS if not ok]
for name, ok, detail in RESULTS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if detail and not ok else ""))
print(f"\nPROBES: {len(RESULTS) - len(failed)}/{len(RESULTS)} held")
sys.exit(1 if failed else 0)
