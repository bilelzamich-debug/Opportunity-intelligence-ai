"""Adversarial probes for T03.2.2 -- sampled deep audit [S-5 Layer 2].

Run BEFORE relying on the contract tests. Each probe states the attack;
PASS means the implementation held.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.audit import (
    AuditCandidate,
    AuditConfig,
    AuditConfigError,
    AuditDisposition,
    AuditJudgement,
    audit_attachment,
    select_sample,
)
from oip.claim import Claim, Quantity
from oip.fact import ClaimType
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from tests.conftest import T0
from tests.test_fact import attachment, make_fact
from oip.identity import IdentityAllocator

CLOCK = lambda: datetime(2026, 9, 7, tzinfo=timezone.utc)  # noqa: E731
RESULTS: list[tuple[str, bool, str]] = []


def probe(label: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((label, bool(cond), detail))


def _l1_pass(span: str, subject: str, predicate: str) -> bool:
    verifier = AnchorVerifier(
        span_provider=lambda a: span,
        claims_of=lambda c: (
            AnchorClaim("x", Anchor("e", "l"), subject=subject, predicate=predicate),
        ),
    )
    from oip.enums import ObjectType
    from tests.conftest import build_attrs

    attrs = build_attrs(
        IdentityAllocator().new_object(),
        ObjectType.FACT,
        (("e", ObjectType.EVIDENCE),),
    )
    return verifier(AcceptanceContext(attributes=attrs)).outcome is RuleOutcome.PASS


def main() -> int:
    alloc = IdentityAllocator()

    # P1 -- Layer 1 PASS is not treated as Layer 2 FAITHFUL
    span = "some sellers occasionally report issues"
    fact = make_fact(
        alloc,
        claim=Claim("sellers", "report", "all consistently failures"),
        qualifying_context="all sellers consistently report failures",
    )
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P1 wording-preserving-anchors still drifts (all/some)",
        _l1_pass(span, "sellers", "report")
        and rec.layer1_pass
        and rec.judgement is AuditJudgement.DRIFTED
        and not rec.verified,
        rec.reason[:80],
    )

    # P2 -- quantity rewrite
    span = "revenue was 10 million in 2020"
    fact = make_fact(alloc, claim=Claim("revenue", "was", "in 2020", Quantity(50, 0.1)))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P2 quantity 10→50 is DRIFTED while Layer 1 locates subject/predicate",
        _l1_pass(span, "revenue", "was")
        and rec.judgement is AuditJudgement.DRIFTED,
        rec.reason[:80],
    )

    # P3 -- date rewrite
    span = "contract signed in 2019"
    fact = make_fact(alloc, claim=Claim("contract", "signed", "in 2024"))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P3 year 2019→2024 is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED and rec.layer1_pass,
        rec.reason[:80],
    )

    # P4 -- entity in qualifier
    span = "Acme acquired Beta"
    fact = make_fact(alloc, claim=Claim("Acme", "acquired", "Gamma"))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P4 entity Beta→Gamma in qualifier is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED and rec.layer1_pass,
        rec.reason[:80],
    )

    # P5 -- negation
    span = "the device never failed in testing"
    fact = make_fact(alloc, claim=Claim("the device", "failed", "in testing"))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P5 dropped negation is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED and "negation" in rec.reason,
        rec.reason[:80],
    )

    # P6 -- attribution
    span = "analyst Jane said bulk edits fail"
    fact = make_fact(
        alloc,
        claim=Claim("bulk edits", "fail", "NONE"),
        claim_type=ClaimType.ATTRIBUTED_OPINION,
        attributed_to="analyst John",
    )
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P6 attribution Jane→John is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED,
        rec.reason[:80],
    )

    # P7 -- certainty
    span = "prices may rise next quarter"
    fact = make_fact(alloc, claim=Claim("prices", "rise", "will next quarter"))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P7 may→will is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED,
        rec.reason[:80],
    )

    # P8 -- relationship
    span = "demand increased last year"
    fact = make_fact(alloc, claim=Claim("demand", "increased", "decreased last year"))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P8 increased vs decreased qualifier is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED,
        rec.reason[:80],
    )

    # P9 -- dropped qualifier restrictor
    span = "returns accepted only with receipt"
    fact = make_fact(alloc, claim=Claim("returns", "accepted", "NONE"))
    rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P9 dropped 'only' restrictor is DRIFTED",
        rec.judgement is AuditJudgement.DRIFTED,
        rec.reason[:80],
    )

    # P10 -- None span is not FAITHFUL
    fact = make_fact(alloc, claim=Claim("sellers", "report", "NONE"))
    rec = audit_attachment(fact, fact.attachments[0], None, AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P10 unavailable evidence is UNAUDITABLE, not verified",
        rec.disposition is AuditDisposition.UNAUDITABLE
        and rec.judgement is None
        and not rec.verified,
        rec.reason[:80],
    )

    # P11 -- REFERENCE-shaped empty content
    rec = audit_attachment(fact, fact.attachments[0], "", AuditConfig(seed="p"), clock=CLOCK)
    probe(
        "P11 empty content is UNAUDITABLE",
        rec.disposition is AuditDisposition.UNAUDITABLE and not rec.verified,
    )

    # P12 -- Layer 1 flag not flipped
    probe(
        "P12 AnchorVerifier.covers_paraphrase_drift remains False",
        AnchorVerifier().covers_paraphrase_drift is False,
    )

    # P13 -- rate 5 is not silently treated as 5%
    refused = False
    try:
        AuditConfig(sample_rate=5)
    except AuditConfigError:
        refused = True
    probe("P13 rate=5 (percent-shaped) is refused, not coerced to 0.05", refused)

    # P14 -- NaN refused
    refused = False
    try:
        AuditConfig(sample_rate=math.nan)
    except AuditConfigError:
        refused = True
    probe("P14 NaN sample_rate refused", refused)

    # P15 -- bool True is not rate 1.0
    refused = False
    try:
        AuditConfig(sample_rate=True)
    except AuditConfigError:
        refused = True
    probe("P15 bool True is not a valid rate", refused)

    # P16 -- duplicates do not inflate the sample
    fact = make_fact(alloc, claim=Claim("sellers", "report", "NONE"))
    c = AuditCandidate(fact, "VENDOR_PUBLICATION", 0.8)
    sample = select_sample((c, c, c), AuditConfig(sample_rate=1.0, seed="p"))
    probe("P16 duplicate candidates sampled once", len(sample) == 1)

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    for label, ok, detail in RESULTS:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {label}"
        if detail and not ok:
            line += f"  ({detail})"
        print(line)
    print(f"\nT03.2.2 probes: {passed}/{len(RESULTS)}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
