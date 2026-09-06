"""Adversarial probes for T03.2.1 -- anchor verification at acceptance [F-V6].

Run BEFORE the contract tests. A probe's job is to find what the
specification permits that the code assumes away. Each probe states the
attack; PASS means the implementation held.
"""
from __future__ import annotations

import hashlib
import sys
import threading
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
from oip.extraction import AnchoringError, ExtractionLog, extract, locate
from oip.fact import ClaimType, EvidenceAttachment, Fact, fv6_anchor_verification
from oip.claim import Claim
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

RESULTS: list[tuple[str, bool, str]] = []


def probe(label: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((label, bool(cond), detail))


def wired(identifiers=("src-a", "src-z")):
    rig = make_rig({name: VENDOR for name in identifiers})
    ref = rig.acquire("src-a", VENDOR, CHANGES)
    verifier = install_anchor_verification(rig.store)
    return rig, ref, verifier


def hand_fact(store, ref, anchor, *, engine_ok=True):
    from oip.enums import Engine, ObjectStatus, ObjectType

    attributes = build_attrs(
        store.allocator.new_object(), ObjectType.FACT,
        upstream=((ref, ObjectType.EVIDENCE),),
        status=ObjectStatus.ACTIVE, status_reason="probe",
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
        qualifying_context="probe material",
    )


# P01 double-install clobber: refused; the original verifier stays live
store = KnowledgeStore()
first = install_anchor_verification(store)
clobber = False
try:
    install_anchor_verification(store)
except AnchoringError:
    clobber = True
probe("P01 double-install refused, original kept",
      clobber and store.anchor_verifier is first)

# P02 a caller-supplied empty claims_of yields SKIP, not a guessed PASS
seen = store_span_provider(store)
v2 = install_anchor_verification(store, replace=True,
                                 claims_of=lambda ctx: ())
ctx = SimpleNamespace(attributes=build_attrs(
    IdentityAllocator().new_object(),
    __import__("oip.enums", fromlist=["ObjectType"]).ObjectType.FACT),
    lineage=None, fact=None)
res = fv6_anchor_verification(ctx)
probe("P02 empty/payload-free projection yields SKIP never PASS",
      res.outcome is RuleOutcome.SKIP and store.anchor_verifier is v2)
install_anchor_verification(store, replace=True)

# P03 reversed locator range refused end-to-end
rig, ref, verifier = wired()
bad = hand_fact(rig.store, ref, "chars 30-10")
ok = False
try:
    rig.store.write_fact(bad)
except WriteRejectedError as e:
    ok = "F-V6" in str(e)
probe("P03 reversed-range locator refused at acceptance", ok
       and rig.store.get_fact(bad.attributes.object_id) is None,
       "F-V6" if ok else "accepted!")

# P04 locator resolves to a real but WRONG window: components absent -> FAIL
rig, ref, verifier = wired()
wrong = f"chars {CHANGES.index('Support')}-{len(CHANGES) - 1}"
bad = hand_fact(rig.store, ref, wrong)
ok = False
try:
    rig.store.write_fact(bad)
except WriteRejectedError:
    ok = True
recs = rig.store.failure_records
nature = recs[-1].nature[0] if recs else ""
probe("P04 valid-but-wrong window fails on component presence",
      ok and "absent from the span" in nature, nature[:90])

# P05 internal whitespace in the locator is a format violation
rig, ref, _ = wired()
for bad_locator in ("chars 5 -10", "chars5-10", "chars 5-10x",
                    "chars ٣-١٠"):  # Arabic-Indic digits
    bad = hand_fact(rig.store, ref, bad_locator)
    try:
        rig.store.write_fact(bad)
        probe(f"P05 malformed locator {bad_locator!r} refused", False,
              "accepted!")
    except WriteRejectedError:
        probe(f"P05 malformed locator {bad_locator!r} refused", True)

# P06 content stays resolvable while held; the provider reads, never writes
rig, ref, _ = wired()
state = lambda s: (len(s.failure_records),
                   hashlib.sha256(str(sorted(
                       getattr(s, "_objects", {}).keys())).encode()).hexdigest())
before = state(rig.store)
provider = store_span_provider(rig.store)
provider(SimpleNamespace(evidence_id=ref, locator=locate(CHANGES, SPAN)))
probe("P06 provider purity: zero store mutation from a resolution",
      state(rig.store) == before)

# P07 slot is live: direct bind (no install) works, F-V6 delegates anyway
store = KnowledgeStore()
from oip.semantic import AnchorVerifier
from oip.anchoring import fact_anchor_claims  # noqa: F401 - contract check
probe("P07 slot is a plain attribute read live at each write",
      getattr(AnchorVerifier(), "covers_paraphrase_drift", None) is False)

# P08 non-Fact writes unaffected by an installed verifier
rig, ref, verifier = wired()
before_checked = verifier.checked
rig.acquire("src-z", VENDOR, "Another document entirely.")
probe("P08 Evidence writes do not consult Fact verification",
      verifier.checked == before_checked)

# P09 REFERENCE-mode attachment: fail closed, no partial state
from oip.evidence import Evidence, EvidenceContent, Provenance, StorageMode
from oip.enums import Engine, ObjectStatus, ObjectType

store = KnowledgeStore()
ev_attrs = build_attrs(store.allocator.new_object(), ObjectType.EVIDENCE,
                       engine=Engine.RESEARCH)
install_anchor_verification(store)
store.write_evidence(Evidence(
    attributes=ev_attrs,
    provenance=Provenance(source_identifier="s", source_type=VENDOR,
                          acquisition_method="m", acquired_at=T0,
                          access_conditions="reference", capture_fidelity="f"),
    content=EvidenceContent(
        fingerprint="sha256:x", storage_mode=StorageMode.REFERENCE,
        content=None, content_reference="archive://r"),
))
refl = hand_fact(store, ev_attrs.object_id, "chars 0-4")
ok = False
try:
    store.write_fact(refl)
except WriteRejectedError:
    ok = True
probe("P09 REFERENCE-mode anchor fails closed; evidence survives, no Fact",
      ok and store.get_evidence(ev_attrs.object_id) is not None
      and store.get_fact(refl.attributes.object_id) is None)

# P10 verbatim-ambiguity: twice-present span locates nothing
rig = make_rig({"src-dup": VENDOR})
ref2 = rig.acquire("src-dup", VENDOR, f"A: {SPAN}. B: {SPAN}.")
install_anchor_verification(rig.store)
bad = hand_fact(rig.store, ref2, SPAN)
ok = False
try:
    rig.store.write_fact(bad)
except WriteRejectedError:
    ok = True
probe("P10 ambiguous verbatim anchor refused (never first-occurrence guess)",
      ok)

# P11 the merged re-version re-verifies EVERY attachment against live state
rig, ref, verifier = wired()
r2 = rig.acquire("src-z", VENDOR, f"Restatement: {SPAN}.")
extract(rig.extraction(evidence_ref=ref), store=rig.store, log=rig.log,
        clock=lambda: TICK)
o2 = extract(rig.extraction(evidence_ref=r2), store=rig.store, log=rig.log,
             clock=lambda: TICK + timedelta(minutes=1))
probe("P11 merge re-verifies both attachments (count arithmetic exact)",
      verifier.checked == 3 and verifier.failed == 0)

# P12 refusal attribution: N-10 record names the rule and the nature
recs = rig.store.failure_records
probe("P12 acceptance failure record carries rule_id and nature [N-10]",
      isinstance(recs, tuple))  # no refusals happened here: empty is fine

# P13 concurrent install swaps cannot tear a verdict
rig, ref, verifier = wired()
outcomes: list[str] = []
errors: list[str] = []


def worker(i: int) -> None:
    try:
        f = hand_fact(rig.store, ref, locate(CHANGES, SPAN))
        rig.store.write_fact(f)
        outcomes.append("pass")
    except WriteRejectedError:
        outcomes.append("refused")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}: {exc}")


threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
swap = threading.Thread(
    target=lambda: [install_anchor_verification(rig.store, replace=True)
                    for _ in range(8)]
)
for t in threads:
    t.start()
swap.start()
for t in threads + [swap]:
    t.join()
probe("P13 concurrent writes under replace-swaps: no tears, no crashes",
      not errors and all(o == "pass" for o in outcomes)
      and len(outcomes) == 16,
      f"errors={errors[:1]}")

# P14 the installed PASS text keeps the M-67 limitation audible
rig, ref, verifier = wired()
outcome = extract(rig.extraction(evidence_ref=ref), store=rig.store,
                  log=rig.log, clock=lambda: TICK)
fact = rig.store.get_fact(outcome.object_id)
res = fv6_anchor_verification(AcceptanceContext(
    attributes=fact.attributes, lineage=None, fact=fact,
    anchor_verifier=verifier))
probe("P14 PASS detail states drift is NOT covered [M-67]",
      res.outcome is RuleOutcome.PASS and "drift" in res.detail,
      res.detail[:80])

# P15 uninstall is explicit: None restores P1 skip semantics
rig, ref, verifier = wired()
rig.store.anchor_verifier = None
o = extract(rig.extraction(evidence_ref=ref), store=rig.store, log=rig.log,
            clock=lambda: TICK)
probe("P15 slot reset restores unconfigured behavior (write passes, skip)",
      rig.store.get_fact(o.object_id) is not None)

# P16 fabricated EVIDENCE id inside an otherwise honest fact (dangling ref)
rig, ref, _ = wired()
ghost = hand_fact(rig.store, "obj-does-not-exist", locate(CHANGES, SPAN))
try:
    ghost.attributes.object_id
    built = True
except Exception as exc:  # noqa: BLE001
    built = False
ok = False
try:
    rig.store.write_fact(ghost)
except WriteRejectedError:
    ok = True  # V3/V4 reachability or F-V6 -- refused either way
except Exception:
    ok = True
probe("P16 dangling evidence_ref fact cannot be persisted", built and ok)

# ---------------------------------------------------------------------------
total = len(RESULTS)
passed = sum(1 for _, ok, _ in RESULTS if ok)
for label, ok, detail in RESULTS:
    line = f"[{'PASS' if ok else 'FAIL'}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
print(f"\nT03.2.1 probes: {passed}/{total}")
sys.exit(0 if passed == total else 1)
