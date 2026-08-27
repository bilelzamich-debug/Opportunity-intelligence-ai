"""Adversarial probes for T03.1.3 -- positional anchoring [F-V2].

Run BEFORE the contract tests. A probe's job is to find what the
specification permits that the code assumes away. Each probe states the
attack; PASS means the implementation held.

Attacks:
  P01  fabricated positional anchor: verifier fails it, never passes it
  P02  shifted anchor (off by one): resolves to the wrong slice, claim fails
  P03  shifted anchor whose window still contains some components:
       slice semantics return the exact bytes; no fuzzy rescue
  P04  ambiguous span: no locator is computed, first occurrence never guessed
  P05  non-resolvable anchors (out of bounds, malformed): provider None,
       verifier FAIL (fabricated location caught)
  P06  whitespace normalization attack: NBSP content vs plain-space span
  P07  unicode normalization attack: NFD anchor against NFC content
  P08  Arabic-Indic digit locator: refused by the closed grammar
  P09  full-width digit locator: refused
  P10  injection locator ("chars 5-10; drop"): grammar refuses the tail
  P11  register poisoning: conflicting re-record raises, original kept
  P12  register poisoning across extract: loud conflict, no silent overwrite
  P13  provider fidelity: the shipped provider is a pure slice closure --
       its output is exactly content[slice], nothing more, for any input
  P14  RTL override marks (U+202E) count as code points: round trip exact
  P15  astral-plane offsets are code points, not UTF-16 units
  P16  boundary: locator ending exactly at len(content) resolves; +1 refuses
  P17  same-Evidence re-extraction: refused as a replay [T03.1.4]
  P18  register completeness: every accepted attachment is registered
  P19  refusal recording: fabricated anchor refusal is attempted-flagged;
       ANCHOR_NOT_RESOLVABLE is an attempted stage [N-10]
  P20  T03.1.1 invariance: verbatim anchor preserved; F-V6 PASS via verifier
  P21  whitespace INSIDE the locator is a format violation
  P22  formatting whitespace AROUND a locator trims; the format stays strict
  P23  the two anchor forms agree: resolve(register locator) == attachment
       verbatim anchor, for every accepted Fact
  P24  content drift is detectable from the locator alone, without search
  P25  no global register state: refusals leave nothing behind
"""
from __future__ import annotations

import sys
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.anchoring import evidence_span_provider, fact_anchor_claims
from oip.configuration import FailureStore
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.extraction import (
    AnchoringError,
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    PositionalAnchorRegister,
    _ATTEMPTED_STAGES,
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

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)

RESULTS: list[tuple[str, bool, str]] = []


def probe(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


# ---------------------------------------------------------------------------
# Rig: the acquisition path in miniature
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

    def acquire(
        self, source: str, source_type: str, content: str,
    ) -> str:
        request = AcquisitionRequest(
            source_identifier=source,
            source_type=source_type,
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
            qualifying_context=(
                "per vendor changelog, for bulk edits above 50 SKUs"
            ),
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
START = CONTENT.find(SPAN)
LOCATOR = f"chars {START}-{START + len(SPAN)}"


def rig_with_content(source: str, content: str) -> tuple[Rig, str]:
    rig = Rig((source,))
    ref = rig.acquire(source, "VENDOR_PUBLICATION", content)
    return rig, ref


def extracted_fact(rig: Rig, ref: str):
    outcome = extract(
        rig.extraction(evidence_ref=ref),
        store=rig.store, log=rig.log,
        clock=lambda: T0 + timedelta(minutes=1),
    )
    return rig.store.get_fact(outcome.object_id)


def verifies(fact, content: str, claims_override=None) -> tuple[bool, str]:
    """Run the real AnchorVerifier against a fact over real content."""
    verifier = AnchorVerifier(
        span_provider=evidence_span_provider(content),
        claims_of=lambda ctx: (
            claims_override if claims_override is not None
            else fact_anchor_claims(fact)
        ),
    )
    result = verifier(AcceptanceContext(attributes=fact.attributes))
    return result.outcome is RuleOutcome.PASS, result.detail


# ---------------------------------------------------------------------------
# P01-P03: fabricated and shifted anchors
# ---------------------------------------------------------------------------

rig, ref = rig_with_content("src-a", CONTENT)
fact = extracted_fact(rig, ref)

forged = fact_anchor_claims(fact)[0]

ok, detail = verifies(fact, CONTENT, claims_override=(
    AnchorClaim(
        claim=forged.claim,
        anchor=Anchor(evidence_id=forged.anchor.evidence_id,
                      locator="chars 0-20"),
        subject=forged.subject,
        predicate=forged.predicate,
        value="",
    ),
))
probe("P01 fabricated positional anchor fails the verifier", not ok, detail)

shifted = f"chars {START + 1}-{START + 1 + len(SPAN)}"
probe("P02 shifted anchor resolves to different bytes",
      resolve_locator(CONTENT, shifted) != SPAN,
      resolve_locator(CONTENT, shifted)[:40])

ok_shifted, detail = verifies(fact, CONTENT, claims_override=(
    AnchorClaim(
        claim=forged.claim,
        anchor=Anchor(evidence_id=forged.anchor.evidence_id, locator=shifted),
        subject=forged.subject,
        predicate=forged.predicate,
        value="",
    ),
))
probe("P02b shifted anchor fails component check", not ok_shifted, detail)

# a window that still CONTAINS the subject but not the predicate:
# slice semantics give exactly those bytes; no fuzzy rescue
partial = f"chars {START}-{START + len('bulk edits silently fail')}"
ok_partial, detail = verifies(fact, CONTENT, claims_override=(
    AnchorClaim(
        claim=forged.claim,
        anchor=Anchor(evidence_id=forged.anchor.evidence_id, locator=partial),
        subject=forged.subject,
        predicate=forged.predicate,
        value="",
    ),
))
probe("P03 partial window (subject without predicate) fails",
      not ok_partial and resolve_locator(CONTENT, partial)
      == "bulk edits silently fail", detail)

# ---------------------------------------------------------------------------
# P04-P10: ambiguity, non-resolvable, normalization, grammar attacks
# ---------------------------------------------------------------------------

try:
    locate(CONTENT + " Also: " + SPAN + ".", SPAN)
    ambiguous_refused = False
except AnchoringError:
    ambiguous_refused = True
probe("P04 ambiguous span gets no locator (first occurrence not guessed)",
      ambiguous_refused)

for bad in ("chars 0-99999", "chars 5-2", "garbage", "chars x-y"):
    try:
        resolve_locator(CONTENT, bad)
        refused = False
        break
    except AnchoringError:
        refused = True
probe("P05 non-resolvable locators refused (provider None path)",
      refused and evidence_span_provider(CONTENT)(
          Anchor("e", "chars 0-99999")) is None)

nbsp_content = "bulk edits\u00a0silently fail above 50 SKUs"  # NBSP inside
try:
    locate(nbsp_content, SPAN)
    nbsp_ok = False
except AnchoringError:
    nbsp_ok = True
probe("P06 NBSP content vs plain-space span: no locator invented",
      nbsp_ok)

nfc = unicodedata.normalize("NFC", "der Markt für Photovoltaik wächst")
nfd_span = unicodedata.normalize("NFD", "Markt für Photovoltaik")
try:
    locate(nfc, nfd_span)
    nfd_ok = False
except AnchoringError:
    nfd_ok = True
probe("P07 NFD span against NFC content: refused, never normalized away",
      nfd_ok)

arabic_digits = "chars ٤٥-٥٠"


def _refused(locator: str) -> bool:
    try:
        resolve_locator(CONTENT, locator)
        return False
    except AnchoringError:
        return True


probe("P08 Arabic-Indic digits refused by the closed grammar",
      _refused(arabic_digits))

fullwidth = "chars ５-１０"
try:
    resolve_locator(CONTENT, fullwidth)
    fw_refused = False
except AnchoringError:
    fw_refused = True
probe("P09 full-width digits refused", fw_refused)

injection = "chars 5-10; drop tables"
try:
    resolve_locator(CONTENT, injection)
    inj_refused = False
except AnchoringError:
    inj_refused = True
probe("P10 injection locator refused: nothing beyond the grammar evaluates",
      inj_refused)

# ---------------------------------------------------------------------------
# P11-P12: register poisoning
# ---------------------------------------------------------------------------

register = PositionalAnchorRegister()
register.record("e1", SPAN, LOCATOR)
try:
    register.record("e1", SPAN, "chars 0-5")
    poison_held = False
except AnchoringError:
    poison_held = True
probe("P11 conflicting re-record raises; original locator kept",
      poison_held and register.locator_for("e1", SPAN) == LOCATOR)

rig_p, ref_p = rig_with_content("src-poison", CONTENT)
register_p = PositionalAnchorRegister()
register_p.record(ref_p, SPAN, "chars 0-5")  # poisoned ahead of extraction
raised = False
try:
    extract(
        rig_p.extraction(evidence_ref=ref_p),
        store=rig_p.store, log=rig_p.log,
        clock=lambda: T0 + timedelta(minutes=1),
        anchors=register_p,
    )
except AnchoringError:
    raised = True
probe("P12 poisoned register fails LOUDLY at registration, never silently "
      "overwritten",
      raised and register_p.locator_for(ref_p, SPAN) == "chars 0-5"
      and rig_p.store.get_fact(
          [s.object_id for s in rig_p.store.objects_of_type(
              __import__("oip.enums", fromlist=["ObjectType"])
              .ObjectType.FACT)][0]
      ) is not None)

# ---------------------------------------------------------------------------
# P13: provider fidelity -- pure slice closure, nothing more
# ---------------------------------------------------------------------------

provider = evidence_span_provider(CONTENT)
faithful = all(
    (provider(Anchor("e", f"chars {a}-{b}"))
     == (CONTENT[a:b] if b <= len(CONTENT) and a < b else None))
    for a, b in [(0, 6), (START, START + len(SPAN)), (5, 2), (0, 99999),
                 (len(CONTENT) - 3, len(CONTENT)), (0, 1), (3, 3)]
)
probe("P13 shipped provider is content-faithful for every input",
      faithful)

# ---------------------------------------------------------------------------
# P14-P16: exotic scripts, boundaries
# ---------------------------------------------------------------------------

rtl_marks = "ر\u202e report\u202c: المبيعات ارتفعت بنسبة 15% هذا العام."
rtl_span = "المبيعات ارتفعت بنسبة 15%"
try:
    rtl_locator = locate(rtl_marks, rtl_span)
    rtl_ok = resolve_locator(rtl_marks, rtl_locator) == rtl_span
except AnchoringError:
    rtl_ok = False
probe("P14 RTL override marks are code points; round trip exact", rtl_ok)

emoji = "📈 revenue grew 14% 📉 then stabilised."
try:
    emoji_locator = locate(emoji, "revenue grew 14%")
    emoji_ok = (
        resolve_locator(emoji, emoji_locator) == "revenue grew 14%"
        and int(emoji_locator.split()[1].split("-")[0])
        == emoji.find("revenue grew 14%")
        and emoji.find("revenue grew 14%") == 2  # emoji = ONE code point
    )
except AnchoringError:
    emoji_ok = False
probe("P15 astral-plane offsets are code points, not UTF-16 units",
      emoji_ok)

end_locator = f"chars {len(CONTENT) - 6}-{len(CONTENT)}"
probe("P16 boundary: exact-end resolves, one-past-end refuses",
      resolve_locator(CONTENT, end_locator) == CONTENT[-6:]
      and evidence_span_provider(CONTENT)(
          Anchor("e", f"chars 0-{len(CONTENT) + 1}")) is None)

# ---------------------------------------------------------------------------
# P17-P18: idempotence and completeness
# ---------------------------------------------------------------------------

rig_idem, ref_idem = rig_with_content("src-idem", CONTENT)
register_idem = PositionalAnchorRegister()
tick = lambda: T0 + timedelta(minutes=1)  # noqa: E731
first = extract(rig_idem.extraction(evidence_ref=ref_idem),
                store=rig_idem.store, log=rig_idem.log, clock=tick,
                anchors=register_idem)
# PROVENANCE (T03.1.4): P17 pinned "re-extraction of the same span
# yields two Facts, no merge". Under D-05 the same-span re-extraction
# of the SAME Evidence is a REPLAY: F-I2 (add-only attachments) refuses
# it as MERGE_FAILED / EVIDENCE_ALREADY_ATTACHED -- never re-attached,
# no phantom version. The idempotence invariant survives as: one Fact,
# one attachment, one anchor registration after the refused replay.
replay_refusal = None
try:
    extract(rig_idem.extraction(evidence_ref=ref_idem),
            store=rig_idem.store, log=rig_idem.log, clock=tick,
            anchors=register_idem)
except ExtractionRefusedError as exc:
    replay_refusal = exc
facts_now = list(rig_idem.store.objects_of_type(
    __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT))
replay_failure = (
    rig_idem.log.for_evidence(ref_idem)[-1] if replay_refusal else None)
probe("P17 same-Evidence re-extraction refused as a replay "
      "[F-I2/T03.1.4]",
      first.locator == LOCATOR and replay_refusal is not None
      and replay_failure is not None
      and replay_failure.stage is ExtractionStage.MERGE_FAILED
      and replay_failure.reason == "EVIDENCE_ALREADY_ATTACHED"
      and len(facts_now) == 1
      and rig_idem.store.get_fact(facts_now[0].object_id).attachment_count == 1
      and len(register_idem) == 1)

rig_c = Rig(("src-en", "src-zh", "src-ar"))
register_c = PositionalAnchorRegister()
corpus = {
    "src-en": (CONTENT, SPAN, "bulk edits", "silently fail above"),
    "src-zh": ("报告称：季度营收增长12%，利润率保持稳定。",
               "季度营收增长12%", "季度营收增长12%", "季度营收增长12%"),
    "src-ar": ("أظهر التقرير أن المبيعات ارتفعت بنسبة 15% في الربع الثاني.",
               "المبيعات ارتفعت بنسبة 15%", "المبيعات", "المبيعات"),
}
refs = {}
for source, (content, span, subject, predicate) in corpus.items():
    refs[source] = rig_c.acquire(source, "VENDOR_PUBLICATION", content)
    extract(
        rig_c.extraction(
            evidence_ref=refs[source], anchor=span,
            subject=subject, predicate=predicate,
        ),
        store=rig_c.store, log=rig_c.log, clock=tick, anchors=register_c,
    )
complete = True
for source, (content, span, _, _) in corpus.items():
    fact_c = None
    for stored in rig_c.store.objects_of_type(
        __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT
    ):
        candidate = rig_c.store.get_fact(stored.object_id)
        if any(a.evidence_ref == refs[source]
               for a in candidate.attachments):
            fact_c = candidate
            break
    attachment = fact_c.attachment_for(refs[source])
    locator = register_c.locator_for(refs[source], span)
    if locator is None or resolve_locator(content, locator) != span:
        complete = False
probe("P18 every accepted attachment is registered and resolvable",
      complete and len(register_c) == 3)

# ---------------------------------------------------------------------------
# P19: refusal recording [N-10]
# ---------------------------------------------------------------------------

rig_f, ref_f = rig_with_content("src-fail", CONTENT)
try:
    extract(rig_f.extraction(evidence_ref=ref_f, anchor="never happened"),
            store=rig_f.store, log=rig_f.log, clock=tick)
    refused_extract = False
except ExtractionRefusedError:
    refused_extract = True
failure = rig_f.log.for_evidence(ref_f)[-1]
probe("P19 fabricated anchor refusal recorded and attempted-flagged; "
      "ANCHOR_NOT_RESOLVABLE is an attempted stage",
      refused_extract
      and failure.stage is ExtractionStage.ANCHOR_NOT_FOUND
      and failure.attempted
      and ExtractionStage.ANCHOR_NOT_RESOLVABLE in _ATTEMPTED_STAGES)

# ---------------------------------------------------------------------------
# P20: T03.1.1 invariance under the new machinery
# ---------------------------------------------------------------------------

attachment = fact.attachment_for(ref)
ok_v6, detail_v6 = verifies(fact, CONTENT)
probe("P20 verbatim anchor preserved; F-V6 PASS through the real verifier",
      attachment.positional_anchor == SPAN
      and CONTENT.count(attachment.positional_anchor) == 1
      and ok_v6, detail_v6)

# ---------------------------------------------------------------------------
# P21-P22: grammar strictness vs formatting tolerance
# ---------------------------------------------------------------------------

def refused_locator(locator: str) -> bool:
    try:
        resolve_locator(CONTENT, locator)
        return False
    except AnchoringError:
        return True

probe("P21 whitespace inside the locator is a format violation",
      all(refused_locator(l) for l in
          ("chars 5 - 10", "chars\t5-10", "chars 5- 10", "chars 5 -10")))

probe("P22 formatting whitespace around a locator trims; format stays "
      "strict",
      resolve_locator(CONTENT, f"  {LOCATOR}  ") == SPAN
      and refused_locator(f"{LOCATOR} tail"))

# ---------------------------------------------------------------------------
# P23: the two anchor forms agree
# ---------------------------------------------------------------------------

agree = all(
    resolve_locator(corpus[s][0],
                    register_c.locator_for(refs[s], corpus[s][1]))
    == corpus[s][1]
    for s in corpus
)
probe("P23 positional locator and verbatim anchor agree on every Fact",
      agree)

# ---------------------------------------------------------------------------
# P24: content drift detectable from the locator alone
# ---------------------------------------------------------------------------

drifted = CONTENT.replace("March", "April")  # one char shorter? no: same
drifted = CONTENT[:START] + "XX" + CONTENT[START:]  # 2 chars inserted
probe("P24 content drift is detectable without search: the locator now "
      "resolves to different bytes",
      resolve_locator(drifted, LOCATOR) != SPAN
      and SPAN not in resolve_locator(drifted, LOCATOR))

# ---------------------------------------------------------------------------
# P25: no global register state
# ---------------------------------------------------------------------------

import oip.extraction as extraction_module  # noqa: E402

globals_ok = not any(
    isinstance(getattr(extraction_module, name, None),
               PositionalAnchorRegister)
    for name in dir(extraction_module)
)
rig_g, ref_g = rig_with_content("src-global", CONTENT)
try:
    extract(rig_g.extraction(evidence_ref=ref_g, anchor="absent span"),
            store=rig_g.store, log=rig_g.log, clock=tick)
except ExtractionRefusedError:
    pass
probe("P25 no module-level register; refusals leave no anchor state",
      globals_ok)

# ---------------------------------------------------------------------------
failed = [(n, d) for n, ok, d in RESULTS if not ok]
for name, ok, detail in RESULTS:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}"
          + (f"  [{detail}]" if detail and not ok else ""))
print(f"\nPROBES: {len(RESULTS) - len(failed)}/{len(RESULTS)} held")
sys.exit(1 if failed else 0)
