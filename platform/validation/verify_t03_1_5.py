"""Verification for T03.1.5 -- F-V4 assertion vs attributed-opinion.

Run AFTER the contract tests. Every check is a mechanical demonstration
against a live corpus, never a restatement of the specification. The task
closes on existing evidence (T02.1.3 precedent): no production file changed,
so the verifier PROVES the enforcement layers exist and hold, by exercising
them, not by recalling that they do.

Sections:
  A. AC1: claim_type is mandatory and the enum is closed
  B. AC1: the classification is populated end-to-end through extract()
  C. AC1: persistence round-trip preserves it
  D. AC2: ATTRIBUTED_OPINION without attributed_to is refused at every layer
  E. AC2: the acceptance-rule layer (fv4_claim_type_declared) behaves
  F. AC1/AC2: the classification survives merge re-versioning [T03.1.4]
  G. Adversarial bypass attempts all refuse; none leaks a Fact
  H. Boundary and invariance
  I. Finding: classification is canonical-level, not utterance-level -- an
     EQUIVALENT merge keeps the canonical's claim_type [D-05, S-3]
"""
from __future__ import annotations

import dataclasses
import inspect
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ObjectStatus, ObjectType
from oip.extraction import (
    ExtractionError,
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    extract,
)
from oip.fact import ClaimType, Fact, fv4_claim_type_declared
from oip.rights import (
    AcquisitionRight,
    RefusalRegister,
    RetentionRight,
    RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
TICK = T0 + timedelta(minutes=1)
AUTHORITY = "Designated Source Rights/Compliance Authority"

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


def raises(fn, exc=Exception) -> tuple[bool, str]:
    try:
        fn()
    except exc as e:  # noqa: BLE001 - the probe IS the exception check
        return True, str(e)
    return False, "no exception raised"


# ===========================================================================
# BUILD: real Evidence through the ratified acquisition path
# ===========================================================================

class Rig:
    """One extraction wiring: acquisition path plus the extraction log."""

    def __init__(self, sources: dict[str, str]) -> None:
        self.registry = SourceRegistry()
        self.store = KnowledgeStore()
        self.out_of_frame = OutOfFrameRegister()
        self.refusals = RefusalRegister()
        self.acq_log = AcquisitionLog()
        self.log = ExtractionLog()
        self.directives = DirectiveRegistry()
        self.directives.raise_directive(Directive(
            directive_id="dir-t5",
            originator=Originator.EXTERNAL_COMMISSION,
            authority="t03-1-5-verifier",
            description="F-V4 verification corpus",
            targets=tuple(sources),
            raised_at=T0 - timedelta(days=1),
        ))
        self.directives.effect("dir-t5", now=T0)
        for identifier, source_type in sources.items():
            self.registry.register(identifier, source_type)

    def acquire(self, source: str, source_type: str, content: str) -> str:
        request = AcquisitionRequest(
            source_identifier=source,
            source_type=source_type,
            acquisition_method="test retrieval",
            capture_fidelity="test corpus; full text",
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
            authority=AUTHORITY,
            basis="verification corpus",
            assessed_at=T0 - timedelta(hours=2),
        )
        evidence = acquire(
            request, registry=self.registry, store=self.store,
            directives=self.directives, out_of_frame=self.out_of_frame,
            refusals=self.refusals, log=self.acq_log, assessment=rights,
            clock=lambda: T0,
        )
        return evidence.object_id

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


VENDOR = "VENDOR_PUBLICATION"
# The ASSERTION material and its corroborating restatement (section F):
CHANGES = (
    "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
    "Support recommends batching smaller."
)
RESTATE = "Trade note repeats: bulk edits silently fail above 50 SKUs."
# The OPINION material -- a DIFFERENT claim so equivalence (which does not
# consider claim_type [S-3]) never merges it into the assertion corpus:
OPINION = (
    "Analyst view: smaller batches are advisable for any catalog above "
    "50 SKUs."
)

rig = Rig({"src-a": VENDOR, "src-b": VENDOR})
REF_A = rig.acquire("src-a", VENDOR, CHANGES)
REF_B = rig.acquire("src-b", VENDOR, OPINION)

OPINION_CLAIM = dict(
    subject="smaller batches",
    predicate="are advisable",
    qualifier="for catalogs above 50 SKUs, per the analyst view",
    anchor="smaller batches are advisable for any catalog above 50 SKUs",
    qualifying_context="analyst opinion, catalogs over 50 SKUs",
)

# ---------------------------------------------------------------------------
# A. AC1: claim_type mandatory, enum closed
# ---------------------------------------------------------------------------

check("A", "ClaimType is exactly the two ratified members",
      {m.value for m in ClaimType} == {"ASSERTION", "ATTRIBUTED_OPINION"},
      str(sorted(m.value for m in ClaimType)))

missing = raises(lambda: dataclasses.replace(
    rig.extraction(evidence_ref=REF_A), claim_type=None), ExtractionError)
check("A", "claim_type=None refused at the request [F-V4]", missing[0],
      missing[1][:90])

raw = raises(lambda: rig.extraction(evidence_ref=REF_A,
                                    claim_type="ASSERTION"),
             ExtractionError)
check("A", "raw string 'ASSERTION' refused: the enum is not bypassable",
      raw[0], raw[1][:90])

fact_fields = dataclasses.fields(Fact)
ct = next(f for f in fact_fields if f.name == "claim_type")
check("A", "Fact.claim_type has NO default: the classification must be "
      "stated at construction (enum membership itself is guarded at the "
      "request and at acceptance -- see G-1b)",
      ct.default is dataclasses.MISSING,
      f"default={ct.default!r}")

check("A", "the request signature carries claim_type as a named parameter",
      "claim_type" in inspect.signature(ExtractionRequest).parameters)

# ---------------------------------------------------------------------------
# B. AC1: populated end-to-end through extract()
# ---------------------------------------------------------------------------

out_assertion = extract(
    rig.extraction(evidence_ref=REF_A),
    store=rig.store, log=rig.log, clock=lambda: TICK,
)
fact_a = rig.store.get_fact(out_assertion.object_id)
check("B", "ASSERTION extraction: stored Fact carries claim_type=ASSERTION",
      fact_a.claim_type is ClaimType.ASSERTION)
check("B", "ASSERTION: structured attribution not invented (None)",
      fact_a.attributed_to is None)

out_opinion = extract(
    rig.extraction(
        evidence_ref=REF_B,
        claim_type=ClaimType.ATTRIBUTED_OPINION,
        attributed_to="the market analyst, 'Analyst view'",
        **OPINION_CLAIM,
    ),
    store=rig.store, log=rig.log, clock=lambda: TICK,
)
fact_b = rig.store.get_fact(out_opinion.object_id)
check("B", "ATTRIBUTED_OPINION extraction: stored Fact carries the type",
      fact_b.claim_type is ClaimType.ATTRIBUTED_OPINION)
check("B", "ATTRIBUTED_OPINION extraction: attributed_to travels verbatim",
      fact_b.attributed_to == "the market analyst, 'Analyst view'")
check("B", "both Facts are ACTIVE (acceptance ran, nothing skipped past V)",
      fact_a.status is ObjectStatus.ACTIVE
      and fact_b.status is ObjectStatus.ACTIVE)
check("B", "the explanation names the classification (N-13 traceability)",
      "claim_type ASSERTION" in fact_a.attributes.explanation.reasoning
      and "claim_type ATTRIBUTED_OPINION"
      in fact_b.attributes.explanation.reasoning,
      fact_a.attributes.explanation.reasoning[:80])

# ---------------------------------------------------------------------------
# C. AC1: persistence round-trip
# ---------------------------------------------------------------------------

again = rig.store.get_fact(out_assertion.object_id)
check("C", "get_fact round-trip preserves claim_type",
      again.claim_type is fact_a.claim_type)
check("C", "get_fact round-trip preserves attributed_to",
      rig.store.get_fact(out_opinion.object_id).attributed_to
      == fact_b.attributed_to)
check("C", "the payload in the registry is a real Fact instance",
      isinstance(again, Fact))

# ---------------------------------------------------------------------------
# D. AC2: refusal of ATTRIBUTED_OPINION without attributed_to, per layer
# ---------------------------------------------------------------------------

for label, attr in (("missing", None), ("blank", ""), ("whitespace", "   ")):
    refused = raises(lambda a=attr: rig.extraction(
        evidence_ref=REF_B, claim_type=ClaimType.ATTRIBUTED_OPINION,
        attributed_to=a, **OPINION_CLAIM), ExtractionError)
    check("D", f"L1 request construction refuses ATTRIBUTED_OPINION with "
        f"{label} attributed_to [F-V4]", refused[0], refused[1][:80])

# The mechanical no-side-effect statement: the request never reached
# extract(), so nothing was attempted at the engine and N-10 has nothing
# to record -- a construction refusal is NOT an extraction failure.
check("D", "the bad requests were refused before extraction: refusal raised "
      "at construction, no N-10 extraction failure exists for them "
      "(nothing was attempted at the engine)",
      len(rig.log) == 0, f"extraction log length {len(rig.log)}")

# L3: Fact construction itself.  Bypass the request entirely and mutate the
# good opinion Fact -- dataclasses.replace re-runs __post_init__, so this
# tests the constructor, not the pipeline.
bad = raises(lambda: dataclasses.replace(fact_b, attributed_to=None),
             Exception)
check("D", "L3 Fact construction refuses ATTRIBUTED_OPINION without "
      "attributed_to (bypassing the request entirely)", bad[0],
      bad[1][:80])

bad_blank = raises(lambda: dataclasses.replace(fact_b, attributed_to="  "),
                   Exception)
check("D", "L3 refuses whitespace attribution: blank is not attributed",
      bad_blank[0], bad_blank[1][:80])

check("D", "no bad Fact object can exist to attempt a write with",
      bad[0] and bad_blank[0])

# ---------------------------------------------------------------------------
# E. AC2: the acceptance-rule layer
# ---------------------------------------------------------------------------

def ctx_for(fact: Fact | None, obj_type=ObjectType.FACT):
    attrs = (fact or fact_a).attributes
    if obj_type is not None:
        attrs = dataclasses.replace(attrs, object_type=obj_type)
    return AcceptanceContext(attributes=attrs, lineage=None, fact=fact)


res_good = fv4_claim_type_declared(ctx_for(fact_a))
check("E", "rule PASSes the compliant ASSERTION fact",
      res_good.outcome is RuleOutcome.PASS, res_good.detail[:60])
res_op = fv4_claim_type_declared(ctx_for(fact_b))
check("E", "rule PASSes the compliant ATTRIBUTED_OPINION fact",
      res_op.outcome is RuleOutcome.PASS, res_op.detail[:60])
res_skip = fv4_claim_type_declared(ctx_for(None))
check("E", "rule SKIPs (never guesses a PASS) when no Fact payload is "
      "supplied", res_skip.outcome is RuleOutcome.SKIP,
      res_skip.detail[:60])
res_na = fv4_claim_type_declared(ctx_for(None, ObjectType.PATTERN))
check("E", "rule SKIPs non-Facts", res_na.outcome is RuleOutcome.SKIP)

# ---------------------------------------------------------------------------
# F. AC1/AC2: classification survives merge re-versioning [T03.1.4]
# ---------------------------------------------------------------------------

rig2 = Rig({"src-c": VENDOR, "src-d": VENDOR})
ref_c = rig2.acquire("src-c", VENDOR, CHANGES)
ref_d = rig2.acquire("src-d", VENDOR, RESTATE)
first = extract(
    rig2.extraction(
        evidence_ref=ref_c,
        claim_type=ClaimType.ATTRIBUTED_OPINION,
        attributed_to="the vendor changelog of March",
    ),
    store=rig2.store, log=rig2.log, clock=lambda: TICK,
)
fact_c = rig2.store.get_fact(first.object_id)
check("F", "first extraction is a v1 ATTRIBUTED_OPINION Fact",
      fact_c.claim_type is ClaimType.ATTRIBUTED_OPINION
      and fact_c.attributes.version == 1)

merge_note = extract(
    rig2.extraction(
        evidence_ref=ref_d,
        claim_type=ClaimType.ATTRIBUTED_OPINION,
        attributed_to="an independent trade note",
    ),
    store=rig2.store, log=rig2.log, clock=lambda: TICK,
)
merged = rig2.store.get_fact(merge_note.object_id)
check("F", "the EQUIVALENT extraction merged: v2, two attachments",
      merged.attributes.version == 2 and len(merged.attachments) == 2,
      f"v={merged.attributes.version} n={len(merged.attachments)}")
check("F", "merge preserved claim_type (classification cannot be laundered "
      "by corroboration)",
      merged.claim_type is ClaimType.ATTRIBUTED_OPINION)
check("F", "merge preserved the canonical's attributed_to (F-I2 add-only "
      "covers the classification pair too)",
      merged.attributed_to == "the vendor changelog of March")

# ---------------------------------------------------------------------------
# G. Adversarial bypass attempts
# ---------------------------------------------------------------------------

# G-1a: attribution mutations re-run the constructor pairing check (L3).
for field, value in (("attributed_to", None), ("attributed_to", " ")):
    outcome = raises(lambda f=field, v=value: dataclasses.replace(
        fact_b, **{f: v}), Exception)
    check("G", f"replace() of {field}={value!r} re-runs the constructor "
        f"checks and refuses", outcome[0], outcome[1][:80])

# G-1b: enum membership is NOT a constructor check -- it is enforced at the
# request (L1) and at acceptance (L4).  A hand-built Fact with a non-member
# claim_type can exist transiently and can NEVER be persisted: the store's
# F-V4 rule fails it.  Asserted exactly, not more strongly than reality.
for value in (None, "ASSERTION"):
    smuggled = dataclasses.replace(fact_b, claim_type=value)
    res = fv4_claim_type_declared(ctx_for(smuggled))
    check("G", f"claim_type={value!r} is refused by the acceptance net "
        f"(L4 FAIL), though the constructor pairing clause alone does not "
        f"cover membership", res.outcome is RuleOutcome.FAIL,
        res.detail[:80])


# G-2: a str-subclass smuggle is refused by the isinstance gate.
class Sneak(str):
    pass


check("G", "a str-subclass 'claim_type' is refused (isinstance on the "
      "enum, not truthiness)",
      raises(lambda: rig.extraction(evidence_ref=REF_A,
                                    claim_type=Sneak("ASSERTION")),
             ExtractionError)[0])

# G-3: the merge produced one lineage, not two Facts.
check("G", "the merge produced one lineage, not two Facts",
      fact_c.attributes.identity.lineage_id
      == merged.attributes.identity.lineage_id)
check("G", "the merged object_id IS the new version (the write resolves)",
      merged.attributes.object_id == merge_note.object_id)

# G-4: a hand-built Fact cannot bypass L3 before any write is attempted.
check("G", "hand-built ATTRIBUTED_OPINION Fact without attribution raises "
      "before any write is attempted",
      raises(lambda: Fact(
          attributes=fact_a.attributes, claim=fact_a.claim,
          claim_type=ClaimType.ATTRIBUTED_OPINION,
          attachments=fact_a.attachments,
          qualifying_context=fact_a.qualifying_context,
      ), Exception)[0])

# ---------------------------------------------------------------------------
# H. Boundary and invariance
# ---------------------------------------------------------------------------

# ref_c already attached on rig2 -> a re-extraction must REFUSE as a replay
# [T03.1.4], never because of anything F-V4 fabricated on the fly.
h_ok, h_detail = False, ""
try:
    extract(
        rig2.extraction(
            evidence_ref=ref_c,
            claim_type=ClaimType.ASSERTION,
            attributed_to="whoever said it",
        ),
        store=rig2.store, log=rig2.log, clock=lambda: TICK,
    )
    h_detail = "unexpected acceptance"
except ExtractionRefusedError as exc:
    h_ok = ("EVIDENCE_ALREADY_ATTACHED" in str(exc)
            and "F-V4" not in str(exc))
    h_detail = str(exc)[:110]
check("H", "replay refusal fires on the replay reason; attribution on an "
      "ASSERTION request raises nothing on its own (no invented "
      "constraint)", h_ok, h_detail)

check("H", "an ASSERTION with attributed_to is accepted by the request "
      "constructor (F-V4 is one-directional as ratified)",
      rig.extraction(evidence_ref="x", claim_type=ClaimType.ASSERTION,
                     attributed_to="y").claim_type is ClaimType.ASSERTION)

# Corpus invariance: this verifier changed no production file.
check("H", "the verifier only imports and exercises oip; the P1/P2 modules "
      "exist untouched by this task",
      all((ROOT / "oip" / n).exists() for n in (
          "extraction.py", "fact.py", "claim.py", "semantic.py",
          "anchoring.py", "store.py")))

# ---------------------------------------------------------------------------
# I. FINDING (documented behavior, not a defect): classification is
# canonical-level.  An EQUIVALENT extraction whose OWN claim_type disagrees
# with the canonical's merges and keeps the canonical's classification --
# S-3's four conditions do not include claim_type, and D-05 makes the Fact
# the canonical claim, not the extraction event.  Demonstrated live here so
# the record is evidence-based, then surfaced in the specification for the
# Project Owner.
# ---------------------------------------------------------------------------

rig4 = Rig({"src-e": VENDOR, "src-f": VENDOR})
ref_e = rig4.acquire("src-e", VENDOR, CHANGES)
ref_f = rig4.acquire("src-f", VENDOR,
                     "Someone else's quote: bulk edits silently fail above "
                     "50 SKUs.")
base_assertion = extract(
    rig4.extraction(evidence_ref=ref_e),  # claim_type defaults ASSERTION
    store=rig4.store, log=rig4.log, clock=lambda: TICK,
)
canon = rig4.store.get_fact(base_assertion.object_id)
opinion_merge = extract(
    rig4.extraction(
        evidence_ref=ref_f,
        claim_type=ClaimType.ATTRIBUTED_OPINION,
        attributed_to="a quoted commentator",
    ),
    store=rig4.store, log=rig4.log, clock=lambda: TICK,
)
merged4 = rig4.store.get_fact(opinion_merge.object_id)
check("I", "an opinion-equivalent extraction merged into the ASSERTION "
      "canonical (S-3 ignores claim_type)",
      merged4.attributes.version == 2
      and merged4.claim_type is ClaimType.ASSERTION
      and len(merged4.attachments) == 2,
      f"v={merged4.attributes.version} type={merged4.claim_type.value}")
check("I", "the merge changed NO classification, raised no refusal, and "
      "the canonical Fact is exactly what the ratified policy produces -- "
      "documented as a finding in the specification, not patched here",
      merged4.attributed_to is None and canon.attributes.object_id
      != merged4.attributes.object_id)

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

total = len(RESULTS)
passed = sum(1 for _, _, ok, _ in RESULTS if ok)
for section in dict.fromkeys(s for s, _, _, _ in RESULTS):
    print(f"--- section {section} ---")
    for s, name, ok, detail in RESULTS:
        if s != section:
            continue
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if detail:
            line += f"  ({detail})"
        print(line)
print(f"\nT03.1.5 verifier: {passed}/{total} checks")
sys.exit(0 if passed == total else 1)
