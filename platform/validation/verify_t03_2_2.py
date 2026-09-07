"""Verification for T03.2.2 -- sampled deep audit [S-5 Layer 2].

Every check is a mechanical demonstration, never a restatement of the spec.

Sections:
  A. AC1: configurable sample rate (bounds, zero, one, invalid, replay)
  B. AC2: paraphrase drift Layer 1 misses
  C. Fail-closed: unavailable / empty / missing components
  D. Provenance
  E. Interaction with Layer 1 (flag unchanged; stronger judgement)
  F. Sampling edge cases (empty, duplicates, smaller-than-n)
  G. Adversarial meaning shifts
  H. Structural constraints: imports, DAG, frozen Layer-1 flag, M-67 open
"""
from __future__ import annotations

import ast
import hashlib
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.audit import (
    INITIAL_SAMPLE_RATE,
    AuditCandidate,
    AuditConfig,
    AuditConfigError,
    AuditDisposition,
    AuditJudgement,
    AuditRegister,
    audit_attachment,
    run_sampled_audit,
    select_sample,
)
from oip.claim import Claim, Quantity
from oip.fact import ClaimType
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from tests.test_fact import attachment, make_fact
from oip.identity import IdentityAllocator

CLOCK = lambda: datetime(2026, 9, 7, 12, tzinfo=timezone.utc)  # noqa: E731
RESULTS: list[tuple[str, str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((section, name, bool(cond), detail))


def _l1(span: str, subject: str, predicate: str) -> bool:
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


alloc = IdentityAllocator()

# ===========================================================================
# A. AC1
# ===========================================================================

check("A", "S-5 initial sample rate is 0.05", INITIAL_SAMPLE_RATE == 0.05)
check("A", "default config uses the S-5 initial rate", AuditConfig().sample_rate == 0.05)
check("A", "rate 0.0 is valid (disabled)", AuditConfig(sample_rate=0.0).disabled)
check("A", "rate 1.0 is valid (audit all)", AuditConfig(sample_rate=1.0).sample_rate == 1.0)

invalid_ok = True
detail = ""
for bad in (-0.01, 1.01, math.nan, math.inf, True, "0.05", 5):
    try:
        AuditConfig(sample_rate=bad)
        invalid_ok = False
        detail = repr(bad)
        break
    except AuditConfigError:
        continue
check("A", "invalid rates refused at construction", invalid_ok, detail)

cands = [
    AuditCandidate(
        make_fact(alloc, identity=alloc.new_object(), claim=Claim("sellers", "report", "NONE"),
                  attachments=(attachment(f"ev-{i}"),)),
        "VENDOR_PUBLICATION",
        0.8,
    )
    for i in range(20)
]
s1 = [c.fact.object_id for c in select_sample(cands, AuditConfig(sample_rate=0.05, seed="k"))]
s2 = [c.fact.object_id for c in select_sample(list(reversed(cands)), AuditConfig(sample_rate=0.05, seed="k"))]
check("A", "replay under the same seed is identical", s1 == s2 == [s1[0]] if s1 else s1 == s2)
check("A", "5% of 20 in one stratum is exactly 1", len(s1) == 1, str(len(s1)))
check("A", "rate 0 yields an empty sample",
      select_sample(cands, AuditConfig(sample_rate=0.0, seed="k")) == ())
check("A", "rate 1 yields every unique candidate",
      len(select_sample(cands, AuditConfig(sample_rate=1.0, seed="k"))) == 20)

# ===========================================================================
# B. AC2
# ===========================================================================

span = "some sellers occasionally report issues"
fact = make_fact(
    alloc,
    claim=Claim("sellers", "report", "all consistently failures"),
    qualifying_context="all sellers consistently report failures",
)
rec = audit_attachment(fact, fact.attachments[0], span, AuditConfig(seed="v"), clock=CLOCK)
check("B", "canonical paraphrase-drift case: Layer 1 would PASS",
      _l1(span, "sellers", "report"))
check("B", "canonical paraphrase-drift case: Layer 2 is DRIFTED",
      rec.judgement is AuditJudgement.DRIFTED and rec.layer1_pass and not rec.verified,
      rec.reason[:80])

span_ok = "Acme increased revenue 10 percent in FY2024"
fact_ok = make_fact(
    alloc,
    claim=Claim("Acme", "increased revenue", "FY2024", Quantity(10, 0.5, "%")),
)
rec_ok = audit_attachment(fact_ok, fact_ok.attachments[0], span_ok, AuditConfig(seed="v"), clock=CLOCK)
check("B", "acceptable paraphrase (10 percent / FY2024) is FAITHFUL",
      rec_ok.judgement is AuditJudgement.FAITHFUL and rec_ok.verified,
      rec_ok.reason[:80])

# ===========================================================================
# C. Fail-closed
# ===========================================================================

rec_n = audit_attachment(fact, fact.attachments[0], None, AuditConfig(seed="v"), clock=CLOCK)
check("C", "None span is UNAUDITABLE and not verified [N-15]",
      rec_n.disposition is AuditDisposition.UNAUDITABLE
      and rec_n.judgement is None
      and not rec_n.verified)
rec_e = audit_attachment(fact, fact.attachments[0], "  ", AuditConfig(seed="v"), clock=CLOCK)
check("C", "whitespace span is UNAUDITABLE",
      rec_e.disposition is AuditDisposition.UNAUDITABLE and not rec_e.verified)
rec_u = audit_attachment(
    make_fact(alloc, claim=Claim("sellers", "report", "NONE")),
    make_fact(alloc, claim=Claim("sellers", "report", "NONE")).attachments[0],
    "weather was fine",
    AuditConfig(seed="v"),
    clock=CLOCK,
)
# rebuild consistently
f_u = make_fact(alloc, claim=Claim("sellers", "report", "NONE"))
rec_u = audit_attachment(f_u, f_u.attachments[0], "weather was fine", AuditConfig(seed="v"), clock=CLOCK)
check("C", "absent subject/predicate is UNSUPPORTED (not FAITHFUL)",
      rec_u.judgement is AuditJudgement.UNSUPPORTED and not rec_u.layer1_pass)

# ===========================================================================
# D. Provenance
# ===========================================================================

check("D", "record names the Fact, evidence, locator, span, config, result, reason, time",
      rec.fact_id == fact.object_id
      and rec.evidence_id == fact.attachments[0].evidence_ref
      and rec.locator == fact.attachments[0].positional_anchor
      and rec.compared_span == span
      and rec.seed == "v"
      and rec.reason
      and rec.audited_at is not None
      and rec.lineage_id == fact.lineage_id)
check("D", "register is outside the object model [N-10]",
      AuditRegister().participates_in_lineage is False)

# ===========================================================================
# E. Layer 1 interaction
# ===========================================================================

check("E", "AnchorVerifier.covers_paraphrase_drift is still False",
      AnchorVerifier().covers_paraphrase_drift is False)
check("E", "Layer 1 PASS text still disclaims paraphrase drift",
      "paraphrase drift not covered" in AnchorVerifier(
          span_provider=lambda a: span,
          claims_of=lambda c: (
              AnchorClaim("x", Anchor("e", "l"), subject="sellers", predicate="report"),
          ),
      )(AcceptanceContext(attributes=fact.attributes, fact=fact)).detail)

# ===========================================================================
# F. Sampling edges
# ===========================================================================

check("F", "empty candidate set → empty sample",
      select_sample((), AuditConfig(sample_rate=1.0, seed="v")) == ())
dup = cands[0]
check("F", "duplicates do not inflate the sample",
      len(select_sample((dup, dup, dup), AuditConfig(sample_rate=1.0, seed="v"))) == 1)
tiny = cands[:3]
check("F", "requested 100% of 3 yields 3 (never more)",
      len(select_sample(tiny, AuditConfig(sample_rate=1.0, seed="v"))) == 3)

register = AuditRegister()
produced = run_sampled_audit(
    cands,
    span_of=lambda f, a: "sellers report issues",
    config=AuditConfig(sample_rate=0.0, seed="v"),
    register=register,
    clock=CLOCK,
)
check("F", "disabled sampling writes no records and verifies nothing",
      produced == () and len(register) == 0)

# ===========================================================================
# G. Adversarial meaning shifts
# ===========================================================================

cases = [
    ("quantity", "rated 4.6 stars", Claim("rated", "stars", "NONE", Quantity(4.9, 0.01))),
    ("year", "signed in 2019", Claim("signed", "in", "2024")),
    ("negation", "sellers do not report failures", Claim("sellers", "report", "failures")),
    ("certainty", "prices may rise", Claim("prices", "rise", "will")),
    ("relationship", "churn decreased", Claim("churn", "decreased", "increased")),
]
all_drift = True
g_detail = ""
for label, gspan, gclaim in cases:
    gf = make_fact(alloc, claim=gclaim)
    grec = audit_attachment(gf, gf.attachments[0], gspan, AuditConfig(seed="v"), clock=CLOCK)
    if grec.judgement is not AuditJudgement.DRIFTED:
        all_drift = False
        g_detail = f"{label}: {grec.judgement} {grec.reason[:60]}"
        break
check("G", "quantity/year/negation/certainty/relationship drifts detected", all_drift, g_detail)

gf = make_fact(
    alloc,
    claim=Claim("bulk edits", "fail", "NONE"),
    claim_type=ClaimType.ATTRIBUTED_OPINION,
    attributed_to="a competing analyst",
)
grec = audit_attachment(
    gf, gf.attachments[0],
    "according to the vendor, bulk edits fail",
    AuditConfig(seed="v"), clock=CLOCK,
)
check("G", "attribution rewrite is DRIFTED", grec.judgement is AuditJudgement.DRIFTED)

gf = make_fact(alloc, claim=Claim("returns", "accepted", "NONE"))
grec = audit_attachment(
    gf, gf.attachments[0], "returns accepted only with receipt",
    AuditConfig(seed="v"), clock=CLOCK,
)
check("G", "dropped restrictor is DRIFTED", grec.judgement is AuditJudgement.DRIFTED)

# ===========================================================================
# H. Structure
# ===========================================================================

mod_imports: dict[str, set[str]] = {}
for path in sorted((ROOT / "oip").glob("*.py")):
    if path.name == "__init__.py":
        continue
    tree = ast.parse(path.read_text())
    mod_imports[path.stem] = {
        n.module.split(".", 1)[1]
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("oip.")
    }

check("H", "audit.py stays within the <=6 oip-import boundary",
      len(mod_imports.get("audit", set())) <= 6,
      str(sorted(mod_imports.get("audit", set()))))
check("H", "audit.py does not import anchoring (DAG: compose via SpanOf)",
      "anchoring" not in mod_imports.get("audit", set()))
check("H", "audit.py does not import store (no new integration point)",
      "store" not in mod_imports.get("audit", set()))


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


check("H", "module graph remains a DAG with audit included", not has_cycle(mod_imports))
check("H", "no non-store module exceeds the 6-import boundary",
      all(len(v) <= 6 for k, v in mod_imports.items() if k != "store"),
      str({k: len(v) for k, v in mod_imports.items() if k != "store" and len(v) > 6}))

semantic = (ROOT / "oip" / "semantic.py").read_text()
check("H", "semantic.py still sets covers_paraphrase_drift default False",
      "covers_paraphrase_drift: bool = field(default=False, init=False)" in semantic)

PROJECT = ROOT.parent
marker_register = (PROJECT / "docs" / "markers" / "MARKER-REGISTER.md").read_text()
check("H", "M-67 remains OPEN", "| **M-67** |" in marker_register)

backlog = (PROJECT / "docs" / "architecture" / "PKP_Implementation_Backlog.md").read_text()
check("H", "backlog T03.2.2 ACs unchanged [F5]",
      "Sample rate configurable" in backlog
      and "Audit detects paraphrase drift anchor checks miss" in backlog)

s5 = (PROJECT / "docs" / "decisions" / "S-05-extraction-fidelity.md").read_text()
check("H", "S-5 Layer-2 judgement vocabulary unchanged",
      "`FAITHFUL` · `DRIFTED` · `UNSUPPORTED`" in s5
      or "FAITHFUL` · `DRIFTED` · `UNSUPPORTED" in s5)

# ===========================================================================
# RESULT
# ===========================================================================

total = len(RESULTS)
passed = sum(1 for _, _, ok, _ in RESULTS if ok)
for section in dict.fromkeys(s for s, _, _, _ in RESULTS):
    print(f"--- section {section} ---")
    for s, name, ok, detail in RESULTS:
        if s != section:
            continue
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name}"
        if detail and not ok:
            line += f"  ({detail})"
        print(line)
print(f"\nT03.2.2 verifier: {passed}/{total} checks")
sys.exit(0 if passed == total else 1)
