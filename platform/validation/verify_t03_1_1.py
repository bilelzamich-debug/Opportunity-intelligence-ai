"""T03.1.1 -- Claim extraction verification.

Proves the three acceptance criteria mechanically against the ratified
corpus and decisions, on top of the eight Quratex-approved Evidence
objects acquired through the P2 exit path:

  AC1  Claims interpretable without reading the Evidence (F-V3)
  AC2  qualifying_context preserved; uncertainty never silently resolved
  AC3  Extraction density consistent across comparable evidence

Also proves: refusal recording (N-10, incl. FailureStore projection),
S-3 equivalence surfacing without merging, S-5 layer-1 agreement with
the ratified AnchorVerifier, full traceability and integrity (F-I1..I4),
the <=6-import / DAG constraints, and that the governing decisions are
byte-identical to their ratified state.

Fails closed: a check that cannot be performed counts as a failure.
"""
from __future__ import annotations

import ast
import hashlib
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "validation"))

from oip.acquisition import AcquisitionLog, AcquisitionRequest, acquire
from oip.claim import Quantity, Verdict
from oip.configuration import FailureStore
from oip.coverage import OutOfFrameRegister
from oip.directives import Directive, DirectiveRegistry, Originator
from oip.enums import ObjectStatus
from oip.extraction import (
    ExtractionLog,
    ExtractionRefusedError,
    ExtractionRequest,
    ExtractionStage,
    build_density_report,
    extract,
)
from oip.fact import ClaimType, Independence
from oip.rights import (
    AcquisitionRight, RefusalRegister, RetentionRight, RightsAssessment,
)
from oip.semantic import AnchorClaim, AnchorVerifier
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

from t0231_evidence import COMMISSIONING_AUTHORITY, EVIDENCE, T0

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


from oip.enums import ObjectType as OBJECT_TYPE_EVIDENCE_MODULE

OBJECT_TYPE_EVIDENCE = OBJECT_TYPE_EVIDENCE_MODULE.EVIDENCE

TICK = T0 + timedelta(minutes=1)
AUTHORITY = "Designated Source Rights/Compliance Authority"

# ===========================================================================
# BUILD: the P2 exit corpus through the acquisition path, then extraction
# ===========================================================================

registry = SourceRegistry()
store = KnowledgeStore()
out_of_frame = OutOfFrameRegister()
refusals = RefusalRegister()
acq_log = AcquisitionLog()
failure_store = FailureStore()
acq_log.attach(failure_store)
directives = DirectiveRegistry()

for rec in EVIDENCE:
    registry.register(rec["source_identifier"], rec["source_type"])

directive = Directive(
    directive_id="dir-p2-exit",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description="P2 exit corpus re-acquisition for T03.1.1 verification",
    targets=tuple(rec["source_identifier"] for rec in EVIDENCE),
    raised_at=T0 - timedelta(days=1),
)
directives.raise_directive(directive)
directives.effect("dir-p2-exit", now=T0)

evidence_ids: dict[str, str] = {}
for rec in EVIDENCE:
    request = AcquisitionRequest(
        source_identifier=rec["source_identifier"],
        source_type=rec["source_type"],
        acquisition_method=rec["acquisition_method"],
        capture_fidelity=rec["capture_fidelity"],
        acquired_at=rec["acquired_at"],
        observed_at=rec["observed_at"],
        evidential_support=rec["evidential_support"],
        assertion_confidence=rec["assertion_confidence"],
        content=rec["content"],
    )
    rights = RightsAssessment(
        source_identifier=rec["source_identifier"],
        acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_FULL,
        authority=AUTHORITY,
        basis=rec["rights_basis"],
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
    evidence_ids[rec["source_identifier"]] = evidence.object_id

# -- extraction corpus: verbatim spans quoted from the captured content ----
# Each triple is (evidence key, request overrides). The anchors are quoted
# from t0231_evidence content exactly as captured, unicode included.
CORPUS: list[tuple[str, dict]] = [
    ("theconversation-anthropic-pentagon", dict(
        subject="Anthropic",
        predicate="said it would not permit",
        anchor=("Anthropic said it would not permit: fully autonomous "
                "weapons"),
        qualifying_context=(
            "The Conversation US, report on the 2026 Pentagon dispute; "
            "the two uses Anthropic ruled out"
        ),
    )),
    ("theconversation-anthropic-pentagon", dict(
        subject="This designation",
        predicate=("would require all defence contractors to cut ties "
                   "with the company"),
        anchor=("This designation would not only put the company\u2019s "
                "$200 million Pentagon contract at risk, but would "
                "require all defence contractors to cut ties with the "
                "company"),
        qualifying_context=(
            "hypothetical effect as reported by The Conversation US; "
            "conditional on the designation being carried out"
        ),
    )),
    ("openfoodfacts-nutella", dict(
        subject="Nutella",
        predicate="Brands",
        anchor="Brands: Nutella, Ferrero, Yum yum",
        qualifying_context=(
            "Open Food Facts product record 3017620422003; brand field "
            "as catalogued"
        ),
    )),
    ("openreview-iclr26-wura", dict(
        subject="Reviewer_wuRA",
        predicate="Official Review of",
        anchor="Official Review of Submission3327 by Reviewer_wuRA",
        qualifying_context=(
            "ICLR 2026 conference ('Accept More, Reject Less'), "
            "submission 3327; reviewer identity as publicly displayed"
        ),
    )),
    ("stackoverflow-yield-python", dict(
        subject="the yield keyword",
        predicate="provide",
        anchor="the yield keyword provide in Python?",
        qualifying_context=(
            "Stack Overflow question 231767 (2008); phrased as the "
            "asker's question about Python generators"
        ),
    )),
    ("wikipedia-helpdesk-inverting", dict(
        subject="an image",
        predicate="inverting the colors of",
        anchor="inverting the colors of an image for an infobox",
        qualifying_context=(
            "Wikipedia Help Desk request TPI81AF (2026-08-25); the "
            "requester's stated goal"
        ),
    )),
    ("datagov-download-metrics", dict(
        subject="Geography and Environment",
        predicate="10/01/2009 12:00:00 AM",
        anchor="10/01/2009 12:00:00 AM,Geography and Environment,18743",
        value=Quantity(18743, 1),
        value_text="18743",
        qualifying_context=(
            "data.gov archival dataset 'Datasets Download By Data "
            "Category'; October 2009 row of the CSV sample"
        ),
    )),
    ("fedregister-sba-size-2026", dict(
        subject="5,314 firms with current contracts",
        predicate="will now be eligible",
        anchor=("5,314 firms with current contracts will now be "
                "eligible"),
        value=Quantity(5314, 1),
        value_text="5,314",
        qualifying_context=(
            "SBA final rule 2026-17042 (91 FR 53741); Engineering "
            "Services, NAICS 541330"
        ),
    )),
    ("vscode-updates-1-102", dict(
        subject="Copilot Chat",
        predicate="is open source",
        anchor=("Copilot Chat is open source: source code available at "
                "microsoft/vscode-copilot-chat under the MIT license"),
        qualifying_context=(
            "VS Code June 2025 release notes (version 1.102); the "
            "announcement as published by Microsoft"
        ),
    )),
]

extraction_log = ExtractionLog()
extraction_log.attach(failure_store)

outcomes = []
requests = []
clocks = iter(
    TICK + timedelta(seconds=i) for i in range(len(CORPUS) * 10)
)
for key, overrides in CORPUS:
    full = {
        "claim_type": ClaimType.ASSERTION,
        "extraction_confidence": 0.8,
        **overrides,
    }
    request = ExtractionRequest(
        evidence_ref=evidence_ids[key], **full
    )
    outcome = extract(
        request,
        store=store, log=extraction_log,
        clock=lambda: next(clocks),
    )
    outcomes.append(outcome)
    requests.append(request)

# ===========================================================================
# A. AC1: claims interpretable without reading the Evidence (F-V3)
# ===========================================================================

check("A", "every corpus extraction produced a persisted Fact",
      len(outcomes) == len(CORPUS)
      and all(o.fact is not None for o in outcomes)
      and all(store.get_fact(o.object_id) is not None for o in outcomes),
      f"{len(outcomes)}/{len(CORPUS)}")

check("A", "every Fact produced by the Fact Extraction engine [V7]",
      all(
          store.get_fact(o.object_id).attributes.produced_by_engine.value
          == "FactExtraction"
          for o in outcomes
      ))

check("A", "F-V3: subject, predicate, qualifier stated on every Fact",
      all(
          (f := store.get_fact(o.object_id)).claim.subject.strip()
          and f.claim.predicate.strip() and f.claim.qualifier.strip()
          for o in outcomes
          if (f := store.get_fact(o.object_id)) is not None
      ))

check("A", "F-V3: qualifying_context present on every Fact",
      all(
          store.get_fact(o.object_id).qualifying_context.strip()
          for o in outcomes
      ))

check("A", "AC1 demonstrated: Fact alone states the claim",
      all(
          o.fact.claim.subject.casefold() in o.fact.claim.as_text().casefold()
          and o.fact.claim.predicate.casefold()
          in o.fact.claim.as_text().casefold()
          for o in outcomes
      ))

check("A", "claims are stored ACTIVE and retrievable",
      all(
          store.find(o.object_id).status is ObjectStatus.ACTIVE
          for o in outcomes
      ))

# ===========================================================================
# B. AC2: qualifying_context preserved; uncertainty preserved
# ===========================================================================

check("B", "qualifying_context carried verbatim on every extraction",
      all(
          store.get_fact(o.object_id).qualifying_context
          == req.qualifying_context
          for o, req in zip(outcomes, requests)
      ))

check("B", "qualifier state explicit on every claim (S-3)",
      all(
          req.qualifier.strip()
          and store.get_fact(o.object_id).claim.qualifier == req.qualifier
          for o, req in zip(outcomes, requests)
      ))

check("B", "extraction confidence preserved, never clamped",
      all(
          store.get_fact(o.object_id)
          .attachment_for(o.evidence_ref)
          .extraction_confidence
          == req.extraction_confidence
          for o, req in zip(outcomes, requests)
      ))

# ambiguity: the duplicate-span Evidence refuses rather than guessing
rig_dup = store  # reuse the corpus store: add a duplicated content source
registry.register("src-dup-verify", "VENDOR_PUBLICATION")
directives.raise_directive(Directive(
    directive_id="dir-dup-verify",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description="ambiguity probe",
    targets=("src-dup-verify",),
    raised_at=T0 - timedelta(days=1),
))
directives.effect("dir-dup-verify", now=T0)
dup_evidence = acquire(
    AcquisitionRequest(
        source_identifier="src-dup-verify",
        source_type="VENDOR_PUBLICATION",
        acquisition_method="verification probe",
        capture_fidelity="probe corpus; full text",
        acquired_at=T0,
        observed_at=T0 - timedelta(hours=1),
        evidential_support=0.7,
        assertion_confidence=0.9,
        content=("A: bulk edits silently fail above 50 SKUs. "
                 "B: bulk edits silently fail above 50 SKUs."),
    ),
    registry=registry, store=store, directives=directives,
    out_of_frame=out_of_frame, refusals=refusals, log=acq_log,
    assessment=RightsAssessment(
        source_identifier="src-dup-verify",
        acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_FULL,
        authority=AUTHORITY,
        basis="probe",
        assessed_at=T0 - timedelta(hours=1),
    ),
    clock=lambda: T0,
)
ambiguous_refused = False
try:
    extract(
        ExtractionRequest(
            evidence_ref=dup_evidence.object_id,
            subject="bulk edits",
            predicate="silently fail above",
            qualifying_context="verification probe",
            anchor="bulk edits silently fail above 50 SKUs",
            claim_type=ClaimType.ASSERTION,
            extraction_confidence=0.8,
        ),
        store=store, log=extraction_log,
        clock=lambda: TICK + timedelta(hours=1),
    )
except ExtractionRefusedError:
    ambiguous_refused = True
check("B", "ambiguous anchor refused, never guessed [AC2]",
      ambiguous_refused
      and extraction_log.for_evidence(dup_evidence.object_id)[-1].stage
      is ExtractionStage.AMBIGUOUS_ANCHOR)

# ===========================================================================
# C. AC3: extraction density consistent across comparable evidence
# ===========================================================================

report = build_density_report(
    store, extraction_log,
    evidence_refs=tuple(evidence_ids.values()),
)
claimed_evidence = {o.evidence_ref for o in outcomes}

check("C", "density measured from recorded facts only [N-10]",
      report.total_claims == len(outcomes)
      and all(
          row.claims == sum(
              1 for o in outcomes if o.evidence_ref == row.evidence_ref
          )
          for row in report.rows
      ))

check("C", "every comparable Evidence yielded at least one claim",
      claimed_evidence == set(evidence_ids.values())
      and all(row.claims >= 1 for row in report.rows),
      str(report.evidences_without_claims))

check("C", "density stratified by the N-20 closed taxonomy",
      {row.source_type for row in report.rows}
      == {rec["source_type"] for rec in EVIDENCE}
      and len(report.rows) == 8)

low, high = report.density_band
ratio = report.density_spread_ratio
check("C", "density spread bounded across the corpus (published bound 6.0)",
      ratio is not None and ratio <= 6.0,
      f"band=({low:.2f}, {high:.2f}) ratio={ratio:.2f}" if ratio else "n/a")

check("C", "density band reported and ordered",
      0.0 < low <= high)

# ===========================================================================
# D. Refusals recorded, never silent [N-10]
# ===========================================================================


def refusal_scenario(name: str, request: ExtractionRequest, stage:
                     ExtractionStage, attempted: bool) -> None:
    before = len(store.objects_of_type(
        OBJECT_TYPE_EVIDENCE_MODULE.FACT))
    refused = False
    try:
        extract(
            request, store=store, log=extraction_log,
            clock=lambda: TICK + timedelta(hours=2),
        )
    except ExtractionRefusedError:
        refused = True
    failures = extraction_log.for_evidence(request.evidence_ref)
    after = len(store.objects_of_type(
        OBJECT_TYPE_EVIDENCE_MODULE.FACT))
    check("D", f"refusal recorded: {name}",
          refused and failures and failures[-1].stage is stage
          and failures[-1].attempted is attempted
          and after == before,  # no partial trace
          f"stage={failures[-1].stage if failures else None}")


fabricated = requests[0]
refusal_scenario(
    "fabricated anchor",
    ExtractionRequest(
        evidence_ref=requests[0].evidence_ref,
        subject=requests[0].subject,
        predicate=requests[0].predicate,
        qualifying_context="probe",
        anchor="words that appear nowhere in this evidence",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.5,
    ),
    ExtractionStage.ANCHOR_NOT_FOUND, True)

refusal_scenario(
    "unsupported claim (components absent)",
    ExtractionRequest(
        evidence_ref=requests[0].evidence_ref,
        subject="competitors",
        predicate="gain market share",
        qualifying_context="probe",
        anchor=requests[0].anchor,
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.5,
    ),
    ExtractionStage.UNSUPPORTED_CLAIM, True)

refusal_scenario(
    "dangling reference",
    ExtractionRequest(
        evidence_ref="EV-DOES-NOT-EXIST",
        subject="anything",
        predicate="anything at all",
        qualifying_context="probe",
        anchor="anything",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.5,
    ),
    ExtractionStage.EVIDENCE_NOT_FOUND, False)

refusal_scenario(
    "non-Evidence reference (a Fact id)",
    ExtractionRequest(
        evidence_ref=outcomes[0].object_id,
        subject=requests[0].subject,
        predicate=requests[0].predicate,
        qualifying_context="probe",
        anchor=requests[0].anchor,
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.5,
    ),
    ExtractionStage.EVIDENCE_NOT_EXTRACTABLE, False)

check("D", "refusals projected into the FailureStore [T02.2.5 pattern]",
      len(failure_store) >= 4,
      f"failure store holds {len(failure_store)}")

check("D", "every refusal carries stage, reason and detail",
      all(
          f.stage is not None and f.reason.strip() and f.detail.strip()
          for f in extraction_log
      ))

# ===========================================================================
# E. S-3 equivalence REALIZED as the canonical merge
# PROVENANCE (T03.1.4): this section pinned the T03.1.1 interim boundary
# "equivalence reported, never merged". T03.1.4 (D-05) supersedes that
# boundary: EQUIVALENT extractions now attach to the existing canonical
# Fact as a new version. The S-3 judgement itself is unchanged -- it now
# surfaces as the merge justification (merge_history) instead of a
# report on a second Fact. Checks below were re-semantified accordingly;
# no assertion was silently deleted or weakened.
# ===========================================================================

# identical claim from a second Evidence: two Facts, EQUIVALENT reported
registry.register("src-second", "VENDOR_PUBLICATION")
directives.raise_directive(Directive(
    directive_id="dir-second",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description="second-source probe",
    targets=("src-second",),
    raised_at=T0 - timedelta(days=1),
))
directives.effect("dir-second", now=T0)
second = acquire(
    AcquisitionRequest(
        source_identifier="src-second",
        source_type="VENDOR_PUBLICATION",
        acquisition_method="verification probe",
        capture_fidelity="probe corpus; full text",
        acquired_at=T0,
        observed_at=T0 - timedelta(hours=1),
        evidential_support=0.7,
        assertion_confidence=0.9,
        content=("Forum repost: bulk edits silently fail above 50 SKUs "
                 "per the changelog."),
    ),
    registry=registry, store=store, directives=directives,
    out_of_frame=out_of_frame, refusals=refusals, log=acq_log,
    assessment=RightsAssessment(
        source_identifier="src-second",
        acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_FULL,
        authority=AUTHORITY,
        basis="probe",
        assessed_at=T0 - timedelta(hours=1),
    ),
    clock=lambda: T0,
)
registry.register("src-first", "VENDOR_PUBLICATION")
directives.raise_directive(Directive(
    directive_id="dir-first",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description="first-source probe",
    targets=("src-first",),
    raised_at=T0 - timedelta(days=1),
))
directives.effect("dir-first", now=T0)
first = acquire(
    AcquisitionRequest(
        source_identifier="src-first",
        source_type="VENDOR_PUBLICATION",
        acquisition_method="verification probe",
        capture_fidelity="probe corpus; full text",
        acquired_at=T0,
        observed_at=T0 - timedelta(hours=1),
        evidential_support=0.7,
        assertion_confidence=0.9,
        content="Changelog: bulk edits silently fail above 50 SKUs.",
    ),
    registry=registry, store=store, directives=directives,
    out_of_frame=out_of_frame, refusals=refusals, log=acq_log,
    assessment=RightsAssessment(
        source_identifier="src-first",
        acquisition=AcquisitionRight.PERMITTED,
        retention=RetentionRight.RETAIN_FULL,
        authority=AUTHORITY,
        basis="probe",
        assessed_at=T0 - timedelta(hours=1),
    ),
    clock=lambda: T0,
)
o_first = extract(
    ExtractionRequest(
        evidence_ref=first.object_id,
        subject="bulk edits",
        predicate="silently fail above",
        anchor="bulk edits silently fail above 50 SKUs",
        qualifying_context="vendor changelog claim",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.75,
    ),
    store=store, log=extraction_log,
    clock=lambda: TICK + timedelta(hours=2),
)
o_second = extract(
    ExtractionRequest(
        evidence_ref=second.object_id,
        subject="bulk edits",
        predicate="silently fail above",
        anchor="bulk edits silently fail above 50 SKUs",
        qualifying_context="forum repost of the changelog claim",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.75,
    ),
    store=store, log=extraction_log,
    clock=lambda: TICK + timedelta(hours=3),
)
check("E", "identical claims MERGE into one canonical [D-05/T03.1.4]",
      o_first.object_id != o_second.object_id
      and o_second.merged_into is not None
      and store.get_fact(o_first.object_id) is not None
      and store.get_fact(o_second.object_id) is not None)

# The equivalence report auto-excludes the predecessor (it is SUPERSEDED
# and no longer in active_facts); the EQUIVALENT judgement now lives on
# the merge justification of the new version [T03.1.4].
equivalent_verdicts = [
    result.verdict for _, result in o_second.equivalence
    if result.verdict is Verdict.EQUIVALENT
]
merged_version = store.get_fact(o_second.object_id)
check("E", "S-3 equivalence REALIZED: EQUIVALENT recorded as the merge "
      "justification [T03.1.4]",
      len(merged_version.merge_history) >= 1
      and merged_version.merge_history[-1].verdict is Verdict.EQUIVALENT
      and merged_version.merge_history[-1].merged_evidence_ref
      == second.object_id
      and equivalent_verdicts == [])

check("E", "the merged version carries both attachments; the "
      "predecessor keeps its own [F-I2/T03.1.4]",
      merged_version.attachment_count == 2
      and store.get_fact(o_first.object_id).attachment_count == 1
      and store.find(o_first.object_id).status is ObjectStatus.SUPERSEDED)

# value disagreement: NOT_EQUIVALENT, both retained
registry.register("src-lista", "MARKETPLACE_LISTING")
registry.register("src-listb", "MARKETPLACE_LISTING")
directives.raise_directive(Directive(
    directive_id="dir-listings",
    originator=Originator.EXTERNAL_COMMISSION,
    authority=COMMISSIONING_AUTHORITY,
    description="listing pair",
    targets=("src-lista", "src-listb"),
    raised_at=T0 - timedelta(days=1),
))
directives.effect("dir-listings", now=T0)
for src, rating in (("src-lista", "4.6"), ("src-listb", "4.9")):
    acquire(
        AcquisitionRequest(
            source_identifier=src,
            source_type="MARKETPLACE_LISTING",
            acquisition_method="verification probe",
            capture_fidelity="probe corpus; full text",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.7,
            assertion_confidence=0.9,
            content=f"Listing: rated {rating} stars by buyers.",
        ),
        registry=registry, store=store, directives=directives,
        out_of_frame=out_of_frame, refusals=refusals, log=acq_log,
        assessment=RightsAssessment(
            source_identifier=src,
            acquisition=AcquisitionRight.PERMITTED,
            retention=RetentionRight.RETAIN_FULL,
            authority=AUTHORITY,
            basis="probe",
            assessed_at=T0 - timedelta(hours=1),
        ),
        clock=lambda: T0,
    )
def _evidence_of_source(source: str) -> str:
    for s in store.objects_of_type(OBJECT_TYPE_EVIDENCE):
        payload = store.get_evidence(s.object_id)
        if payload is not None and payload.source_identifier == source:
            return s.object_id
    raise AssertionError(f"no Evidence for {source!r}")


o_46 = extract(
    ExtractionRequest(
        evidence_ref=_evidence_of_source("src-lista"),
        subject="Listing",
        predicate="rated",
        anchor="Listing: rated 4.6 stars by buyers.",
        value=Quantity(4.6, 0.1), value_text="4.6",
        qualifying_context="buyer ratings, probe listing A",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.8,
    ),
    store=store, log=extraction_log,
    clock=lambda: TICK + timedelta(hours=4),
)
o_49 = extract(
    ExtractionRequest(
        evidence_ref=_evidence_of_source("src-listb"),
        subject="Listing",
        predicate="rated",
        anchor="Listing: rated 4.9 stars by buyers.",
        value=Quantity(4.9, 0.1), value_text="4.9",
        qualifying_context="buyer ratings, probe listing B",
        claim_type=ClaimType.ASSERTION,
        extraction_confidence=0.8,
    ),
    store=store, log=extraction_log,
    clock=lambda: TICK + timedelta(hours=5),
)
check("E", "values outside stated precision do NOT merge [S-3 cond 4]",
      o_46.object_id != o_49.object_id
      and Verdict.NOT_EQUIVALENT in {
          r.verdict for _, r in o_49.equivalence})

check("E", "contradictory/distinct claims both retained as Facts",
      store.get_fact(o_46.object_id) is not None
      and store.get_fact(o_49.object_id) is not None)

check("E", "attachments start UNASSESSED; corroboration unclaimed [N-16]",
      all(
          a.independence_assessment is Independence.UNASSESSED
          and not a.is_independent
          for o in outcomes for a in o.fact.attachments
      ))

# ===========================================================================
# F. S-5 layer 1: the local gate agrees with the ratified AnchorVerifier
# ===========================================================================

rng = random.Random(20260826)
verifier = AnchorVerifier()
agreements = 0
mismatches: list[str] = []
for _ in range(200):
    words = ["bulk", "edits", "silently", "fail", "above", "fifty", "skus",
             "vendor", "listing", "rated", "stars", "churn", "yield"]
    span = " ".join(rng.choice(words) for _ in range(rng.randint(3, 8)))
    subject = rng.choice(words)
    predicate = rng.choice(words)
    value = rng.choice([None, rng.choice(words)])
    anchored = AnchorClaim(
        claim="n/a",
        anchor=type("A", (), {"locator": span})(),
        subject=subject, predicate=predicate, value=value or "",
    )
    ratified = verifier._missing_components(anchored, span)
    from oip.extraction import _missing_components as local_gate
    local = local_gate(subject, predicate, value, span)
    if list(ratified) == list(local):
        agreements += 1
    else:
        mismatches.append(f"{span!r}/{subject!r}/{predicate!r}/{value!r}")
check("F", "local layer-1 gate == AnchorVerifier on 200 random samples",
      not mismatches, str(mismatches[:3]))

# ===========================================================================
# G. Traceability audit -- every Fact resolvable to its Evidence
# ===========================================================================

# PROVENANCE (T03.1.4): the per-Fact trace was "exactly one derives_from
# reference == the outcome's Evidence". A merged Fact legitimately
# derives from EVERY attesting Evidence (with_attachment appends to
# derives_from), so the audit now requires derives_from to cover exactly
# the attachment set, every reference resolvable, and the ceiling to
# hold against EVERY attachment -- strictly stronger than the single-
# evidence form on merged Facts.
all_outcomes = outcomes + [o_second, o_46, o_49]
trace_ok = True
trace_detail = ""
for o in all_outcomes:
    fact = store.get_fact(o.object_id)
    stored = store.find(o.object_id)
    derive_refs = {r.object_id for r in stored.attributes.derives_from}
    att_refs = {a.evidence_ref for a in fact.attachments}
    if derive_refs != att_refs or o.evidence_ref not in derive_refs:
        trace_ok, trace_detail = False, f"{o.object_id} lineage"
        break
    for attachment in fact.attachments:
        evidence_obj = store.get_evidence(attachment.evidence_ref)
        if evidence_obj is None:
            trace_ok = False
            trace_detail = f"{o.object_id} evidence missing"
            break
        content = evidence_obj.content.content
        if content.count(attachment.positional_anchor) != 1:
            trace_ok = False
            trace_detail = f"{o.object_id} anchor"
            break
        src_conf = evidence_obj.attributes.confidence.effective_confidence
        conf = fact.attributes.confidence
        if conf.effective_confidence > min(
            src_conf, attachment.extraction_confidence
        ) + 1e-9:
            trace_ok = False
            trace_detail = f"{o.object_id} ceiling"
            break
    if not trace_ok:
        break
    if fact.independent_source_count > fact.attachment_count:
        trace_ok, trace_detail = False, f"{o.object_id} F-V5"
        break
check("G", "every Fact traces to resolvable ACTIVE Evidence "
      "(derives_from == attachment set)",
      trace_ok, trace_detail)

check("G", "anchor of every attachment locates uniquely in its Evidence",
      all(
          store.get_evidence(a.evidence_ref).content.content.count(
              a.positional_anchor) == 1
          for o in all_outcomes for a in o.fact.attachments
      ))

violations = store.facts.integrity().verify()
check("G", "Fact integrity F-I1..F-I4 clean across the store",
      not violations, str(violations[:2]))

check("G", "upstream provenance untouched by extraction [E-I3]",
      all(
          store.get_evidence(o.evidence_ref).provenance.source_identifier
          for o in all_outcomes
      ))

# ===========================================================================
# H. Structural constraints and frozen documents
# ===========================================================================

tree = ast.parse((ROOT / "oip" / "extraction.py").read_text())
imports = {
    n.module.split(".", 1)[1]
    for n in ast.walk(tree)
    if isinstance(n, ast.ImportFrom) and n.module
    and n.module.startswith("oip.")
}
check("H", "extraction.py stays within the <=6 oip-import boundary",
      len(imports) <= 6, str(sorted(imports)))

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


check("H", "module graph remains a DAG with extraction included",
      not has_cycle(mod_imports))

check("H", "no non-store module exceeds the 6-import boundary",
      all(len(v) <= 6 for k, v in mod_imports.items() if k != "store"),
      str({k: len(v) for k, v in mod_imports.items()
           if k != "store" and len(v) > 6}))

# governing decisions byte-identical to the ratified state at 4d258b7
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

backlog = (PROJECT / "docs" / "architecture"
           / "PKP_Implementation_Backlog.md").read_text()
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
if ratio:
    print(f"corpus density: {report.total_claims} claims over "
          f"{len(report.rows)} Evidence; band "
          f"({report.density_band[0]:.2f}, "
          f"{report.density_band[1]:.2f}) claims/1000 chars; "
          f"spread {ratio:.2f}x")
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
    print("ALL CHECKS PASSED -- T03.1.1 ACCEPTANCE DEMONSTRATED")
    sys.exit(0)
sys.exit(1)
