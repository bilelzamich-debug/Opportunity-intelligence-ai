"""Verification for T03.2.1 -- anchor verification at acceptance [F-V6].

Run AFTER the contract tests. Every check is a mechanical demonstration
against a live corpus, never a restatement of the specification.

Sections:
  A. AC1: every accepted Fact's anchor resolves at the stated position
  B. AC2: fabricated anchors are refused at acceptance, with attribution
  C. AC3: verification runs on 100% of Facts -- exact count arithmetic
  D. Installation contract: opt-in, non-clobbering, explicit replace
  E. The store-wide provider: FULL resolves, REFERENCE/dangling fail closed
  F. M-67 honesty: the installed state keeps stating what it does NOT cover
  G. N-4 determinism: same input, same verdicts
  H. Frozen modules: byte-identical; the change is anchoring.py alone
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.anchoring import (
    install_anchor_verification,
    store_span_provider,
)
from oip.claim import Claim
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.extraction import AnchoringError, extract, locate
from oip.fact import ClaimType, EvidenceAttachment, Fact, fv6_anchor_verification
from oip.identity import IdentityAllocator
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import build_attrs
from tests.test_extraction import TICK, VENDOR, make_rig

T0 = datetime(2026, 9, 6, 12, 0, 0, tzinfo=timezone.utc)
CHANGES = (
    "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
    "Support recommends batching smaller."
)
SPAN = "bulk edits silently fail above 50 SKUs"

RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


def wired(identifiers=("src-a", "src-z")):
    rig = make_rig({name: VENDOR for name in identifiers})
    ref = rig.acquire("src-a", VENDOR, CHANGES)
    verifier = install_anchor_verification(rig.store)
    return rig, ref, verifier


def hand_fact(store, ref, anchor):
    attributes = build_attrs(
        store.allocator.new_object(), ObjectType.FACT,
        upstream=((ref, ObjectType.EVIDENCE),),
        status=ObjectStatus.ACTIVE, status_reason="verifier probe",
        engine=Engine.FACT_EXTRACTION,
        support=0.55, assertion=0.55, upstream_ceiling=0.55,
    )
    return Fact(
        attributes=attributes,
        claim=Claim(subject="bulk edits", predicate="silently fail above"),
        claim_type=ClaimType.ASSERTION,
        attachments=(EvidenceAttachment(
            evidence_ref=ref, positional_anchor=anchor,
            extracted_at=T0, extraction_confidence=0.8),),
        qualifying_context="verifier material",
    )


# ===========================================================================
# A. AC1 -- locatable at the stated anchor
# ===========================================================================

rig, ref, verifier = wired()
outcome = extract(rig.extraction(evidence_ref=ref), store=rig.store,
                  log=rig.log, clock=lambda: TICK)
fact = rig.store.get_fact(outcome.object_id)
att = fact.attachments[0]
provider = store_span_provider(rig.store)
check("A", "AC1: attachment positional anchor resolves to the exact span",
      provider(SimpleNamespace(evidence_id=att.evidence_ref,
                               locator=att.positional_anchor)) == SPAN)
check("A", "AC1: the attachment anchor IS the verbatim span (T03.1.1 "
      "convention) and resolves in place",
      att.positional_anchor == SPAN)
check("A", "AC1: a positional locator resolves to the same bytes in the "
      "same store (dual convention, direct slice)",
      provider(SimpleNamespace(evidence_id=att.evidence_ref,
                               locator=locate(CHANGES, SPAN))) == SPAN)
res = fv6_anchor_verification(AcceptanceContext(
    attributes=fact.attributes, lineage=None, fact=fact,
    anchor_verifier=verifier))
check("A", "AC1: F-V6 PASSes through the ratified rule with the store-wide "
      "wiring", res.outcome is RuleOutcome.PASS, res.detail[:70])

# ===========================================================================
# B. AC2 -- fabricated anchors refused
# ===========================================================================

for label, forged in (
    ("out-of-bounds locator", "chars 900-999"),
    ("reversed range", "chars 30-10"),
    ("absent verbatim span", "this sentence was never written anywhere"),
    ("ambiguous verbatim span", SPAN),  # only once here -> resolves; next case
    ("non-numeric junk", "chars a-b"),
):
    r2, ref2, _ = wired()
    if label == "ambiguous verbatim span":
        r2 = make_rig({"src-amb": VENDOR})
        ref2 = r2.acquire("src-amb", VENDOR, f"A: {SPAN}. B: {SPAN}.")
        install_anchor_verification(r2.store)
    bad = hand_fact(r2.store, ref2, forged)
    refused = False
    try:
        r2.store.write_fact(bad)
    except WriteRejectedError:
        refused = True
    check("B", f"AC2: {label} refused at acceptance", refused
          and r2.store.get_fact(bad.attributes.object_id) is None)

recs = r2.store.failure_records
check("B", "AC2: the refusal is a recorded N-10 failure naming F-V6",
      any("F-V6" in rec.rule_ids for rec in recs))
check("B", "AC2: a refused fabrication leaves no payload behind",
      r2.store.get_fact(bad.attributes.object_id) is None)

# ===========================================================================
# C. AC3 -- 100 percent of Facts, exact arithmetic
# ===========================================================================

rig, ref, verifier = wired()
r2ref = rig.acquire("src-z", VENDOR, f"Restatement: {SPAN}.")
o1 = extract(rig.extraction(evidence_ref=ref), store=rig.store, log=rig.log,
             clock=lambda: TICK)
n1 = len(rig.store.get_fact(o1.object_id).attachments)
o2 = extract(rig.extraction(evidence_ref=r2ref), store=rig.store,
             log=rig.log, clock=lambda: TICK + timedelta(minutes=1))
n2 = len(rig.store.get_fact(o2.object_id).attachments)
check("C", "AC3: checked == attachments of EVERY accepted Fact write "
      f"(fresh={n1} + merge={n2})", verifier.checked == n1 + n2 == 3,
      f"checked={verifier.checked}")
check("C", "AC3: the rule is unconditional in FACT_RULES (no sampling knob)",
      any(r.__name__ == "fv6_anchor_verification"
          for r in __import__("oip.fact", fromlist=["FACT_RULES"]).FACT_RULES))
check("C", "AC3: with no verifier installed the rule SKIPs with the M-67 "
      "text -- it never fabricates a pass",
      fv6_anchor_verification(AcceptanceContext(
          attributes=fact.attributes, lineage=None, fact=fact,
          anchor_verifier=None)).outcome is RuleOutcome.SKIP)
check("C", "AC3: the merged re-version re-ran verification over BOTH "
      "attachments against live content", verifier.failed == 0
      and n2 == 2)

# ===========================================================================
# D. Installation contract
# ===========================================================================

store = KnowledgeStore()
check("D", "default store: unconfigured (P1-pinned; install is opt-in)",
      store.anchor_verifier is None)
v = install_anchor_verification(store)
check("D", "install binds the store's live slot", store.anchor_verifier is v)
try:
    install_anchor_verification(store)
    clobbered = False
except AnchoringError:
    clobbered = True
check("D", "double install REFUSES to clobber silently", clobbered
      and store.anchor_verifier is v)
v2 = install_anchor_verification(store, replace=True)
check("D", "replace=True is the only, explicit swap path",
      store.anchor_verifier is v2 and v2 is not v)

# ===========================================================================
# E. Provider semantics
# ===========================================================================

from oip.evidence import Evidence, EvidenceContent, Provenance, StorageMode

store = KnowledgeStore()
install_anchor_verification(store)
ev_attrs = build_attrs(store.allocator.new_object(), ObjectType.EVIDENCE,
                       engine=Engine.RESEARCH)
store.write_evidence(Evidence(
    attributes=ev_attrs,
    provenance=Provenance(source_identifier="s-e", source_type=VENDOR,
                          acquisition_method="m", acquired_at=T0,
                          access_conditions="reference",
                          capture_fidelity="f"),
    content=EvidenceContent(fingerprint="sha256:x",
                            storage_mode=StorageMode.REFERENCE,
                            content=None, content_reference="archive://r"),
))
p = store_span_provider(store)
check("E", "REFERENCE-mode payload: provider answers None [N-15]",
      p(SimpleNamespace(evidence_id=ev_attrs.object_id,
                        locator="chars 0-4")) is None)
check("E", "dangling evidence_ref: provider answers None",
      p(SimpleNamespace(evidence_id="obj-none", locator="chars 0-4")) is None)

# ===========================================================================
# F. M-67 honesty under installation
# ===========================================================================

check("F", "installed verifier declares covers_paraphrase_drift=False",
      v2.covers_paraphrase_drift is False)
rig_f, ref_f, ver_f = wired()
out_f = extract(rig_f.extraction(evidence_ref=ref_f), store=rig_f.store,
                log=rig_f.log, clock=lambda: TICK)
fact_f = rig_f.store.get_fact(out_f.object_id)
res = fv6_anchor_verification(AcceptanceContext(
    attributes=fact_f.attributes, lineage=None, fact=fact_f,
    anchor_verifier=ver_f))
check("F", "the PASS text keeps stating what Layer 1 does not cover",
      res.outcome is RuleOutcome.PASS and "drift" in res.detail,
      res.detail[:70])
check("F", "anchor_failure_rate is exposed and honest (0.0 on a clean "
      "corpus: 1 attachment via the engine write + 1 via this direct call)",
      ver_f.checked == 2 and ver_f.failed == 0
      and ver_f.anchor_failure_rate == 0.0)

# ===========================================================================
# G. Determinism (N-4)
# ===========================================================================

seqs = []
for _ in range(2):
    r3, ref3, ver3 = wired()
    extract(r3.extraction(evidence_ref=ref3), store=r3.store, log=r3.log,
            clock=lambda: TICK)
    try:
        r3.store.write_fact(hand_fact(r3.store, ref3, "chars 900-999"))
    except WriteRejectedError:
        pass
    seqs.append((ver3.checked, ver3.failed))
check("G", "replay of the same corpus+attack yields identical verification "
      "arithmetic", seqs[0] == seqs[1] == (2, 1), str(seqs))

# ===========================================================================
# H. Frozen surface (mechanical, from git)
# ===========================================================================

status = subprocess.run(
    ["git", "status", "--porcelain", "--", "platform/oip", "oip"],
    capture_output=True, text=True, cwd=ROOT.parent,
).stdout.strip().splitlines()
changed = [line for line in status if line.strip()]
only_anchoring = all("anchoring.py" in line for line in changed)
check("H", "git status: within oip/, ONLY anchoring.py differs from HEAD "
      "(frozen P1/P2 modules byte-identical)", only_anchoring,
      "; ".join(changed)[:120])
import hashlib
h = hashlib.sha256((ROOT / "oip" / "extraction.py").read_bytes()).hexdigest()
base = subprocess.run(
    ["git", "show", "HEAD:platform/oip/extraction.py"],
    capture_output=True, text=True, cwd=ROOT.parent,
).stdout
check("H", "extraction.py unchanged at the hash level (engine path untouched "
      "by the wiring)", hashlib.sha256(base.encode()).hexdigest() == h)

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
print(f"\nT03.2.1 verifier: {passed}/{total} checks")
sys.exit(0 if passed == total else 1)
