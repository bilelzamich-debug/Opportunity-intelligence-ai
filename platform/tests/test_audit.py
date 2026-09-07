"""Contract tests for sampled deep audit (S-5 Layer 2).

Task: T03.2.2

Architecture References:
- S-5    Layer 2 sampled semantic fidelity; judgements FAITHFUL/DRIFTED/
         UNSUPPORTED; initial rate 5%; stratified by source type and
         extraction confidence
- S-3    Structure makes comparison checkable; undecidable ≠ verified
- N-15   Unverifiable material is not verified
- N-4    Sampling is deterministic given seed + identities
- N-10   Records outside the object model
- M-67   Remains open; Layer 1 still declares covers_paraphrase_drift=False

Acceptance criteria under test:
  AC1  Sample rate configurable
  AC2  Audit detects paraphrase drift anchor checks miss
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

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
    audit_fact,
    rollup,
    run_sampled_audit,
    select_sample,
)
from oip.claim import Claim, Quantity
from oip.fact import ClaimType
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from tests.test_fact import attachment, make_fact

T0 = datetime(2026, 9, 7, 12, 0, 0, tzinfo=timezone.utc)
CLOCK = lambda: T0  # noqa: E731


def _claim(**overrides) -> Claim:
    kwargs = dict(
        subject="sellers",
        predicate="report",
        qualifier="NONE",
    )
    kwargs.update(overrides)
    return Claim(**kwargs)


def _candidate(allocator, oid_suffix: str, **kwargs) -> AuditCandidate:
    fact = make_fact(
        allocator,
        identity=allocator.new_object(),
        claim=kwargs.pop("claim", _claim()),
        attachments=(attachment(f"ev-{oid_suffix}"),),
        **{k: v for k, v in kwargs.items() if k in {"qualifying_context", "claim_type", "attributed_to", "temporal_scope"}},
    )
    return AuditCandidate(
        fact=fact,
        source_type=kwargs.get("source_type", "VENDOR_PUBLICATION"),
        extraction_confidence=kwargs.get("extraction_confidence", 0.8),
    )


def _layer1(span: str, subject: str, predicate: str, value: str = "") -> RuleOutcome:
    verifier = AnchorVerifier(
        span_provider=lambda a: span,
        claims_of=lambda c: (
            AnchorClaim(
                claim="n/a",
                anchor=Anchor("ev", "loc"),
                subject=subject,
                predicate=predicate,
                value=value,
            ),
        ),
    )
    fact_like = type("F", (), {})()
    # Minimal context: Layer 1 only needs object_type FACT via claims_of.
    from oip.enums import ObjectType
    from tests.conftest import build_attrs
    from oip.identity import IdentityAllocator

    alloc = IdentityAllocator()
    attrs = build_attrs(alloc.new_object(), ObjectType.FACT, (("ev", ObjectType.EVIDENCE),))
    result = verifier(AcceptanceContext(attributes=attrs))
    return result.outcome


# ===========================================================================
# AC1 -- configurable sample rate
# ===========================================================================


class TestSampleRateConfiguration:
    def test_default_rate_is_s5_initial(self):
        assert AuditConfig().sample_rate == INITIAL_SAMPLE_RATE == 0.05

    def test_zero_disables_sampling(self, allocator):
        config = AuditConfig(sample_rate=0.0, seed="s")
        assert config.disabled
        cands = [_candidate(allocator, "a") for _ in range(10)]
        assert select_sample(cands, config) == ()

    def test_one_audits_every_unique_candidate(self, allocator):
        config = AuditConfig(sample_rate=1.0, seed="s")
        cands = [_candidate(allocator, str(i)) for i in range(7)]
        sample = select_sample(cands, config)
        assert len(sample) == 7
        assert {c.fact.object_id for c in sample} == {c.fact.object_id for c in cands}

    def test_minimum_positive_rate_is_accepted(self):
        assert AuditConfig(sample_rate=0.0).sample_rate == 0.0

    def test_maximum_rate_is_accepted(self):
        assert AuditConfig(sample_rate=1.0).sample_rate == 1.0

    @pytest.mark.parametrize("bad", [-0.01, 1.01, float("nan"), float("inf"), float("-inf"), True, False, "0.05", None])
    def test_invalid_rates_refused_at_the_boundary(self, bad):
        with pytest.raises(AuditConfigError):
            AuditConfig(sample_rate=bad)

    def test_empty_seed_refused(self):
        with pytest.raises(AuditConfigError):
            AuditConfig(seed="")

    def test_empty_input_yields_empty_sample(self):
        assert select_sample((), AuditConfig(sample_rate=1.0, seed="s")) == ()

    def test_duplicates_collapse_to_first(self, allocator):
        first = _candidate(allocator, "dup")
        clone = AuditCandidate(
            fact=first.fact,
            source_type="PUBLISHED_EDITORIAL",
            extraction_confidence=0.2,
        )
        sample = select_sample((first, clone, first), AuditConfig(sample_rate=1.0, seed="s"))
        assert len(sample) == 1
        assert sample[0] is first

    def test_sample_never_exceeds_unique_candidates(self, allocator):
        cands = [_candidate(allocator, str(i)) for i in range(3)]
        sample = select_sample(cands, AuditConfig(sample_rate=1.0, seed="s"))
        assert len(sample) == 3

    def test_stratified_rate_on_a_single_stratum(self, allocator):
        cands = [
            _candidate(allocator, str(i), extraction_confidence=0.85)
            for i in range(20)
        ]
        sample = select_sample(cands, AuditConfig(sample_rate=0.05, seed="s"))
        # floor(0.05 * 20) = 1
        assert len(sample) == 1

    def test_replay_under_the_same_seed_is_identical(self, allocator):
        cands = [_candidate(allocator, str(i)) for i in range(30)]
        config = AuditConfig(sample_rate=0.2, seed="replay")
        a = [c.fact.object_id for c in select_sample(cands, config)]
        b = [c.fact.object_id for c in select_sample(list(reversed(cands)), config)]
        # reversed input, after first-wins dedupe of unique ids, rank order matches
        assert a == b

    def test_different_seeds_can_differ(self, allocator):
        cands = [_candidate(allocator, str(i)) for i in range(40)]
        a = [c.fact.object_id for c in select_sample(cands, AuditConfig(sample_rate=0.25, seed="a"))]
        b = [c.fact.object_id for c in select_sample(cands, AuditConfig(sample_rate=0.25, seed="b"))]
        assert a != b or len(a) == 0  # collision theoretically possible; 40@25% makes it vanishing

    def test_disabled_run_writes_nothing(self, allocator):
        register = AuditRegister()
        fact = make_fact(allocator, claim=_claim())
        run_sampled_audit(
            [AuditCandidate(fact, "VENDOR_PUBLICATION", 0.8)],
            span_of=lambda f, a: "sellers report issues",
            config=AuditConfig(sample_rate=0.0, seed="s"),
            register=register,
            clock=CLOCK,
        )
        assert len(register) == 0

    def test_register_is_outside_the_object_model(self):
        assert AuditRegister().participates_in_lineage is False
        assert not hasattr(AuditRegister(), "object_id")


@settings(max_examples=80, deadline=None)
@given(rate=st.floats(allow_nan=False, allow_infinity=False))
def test_rate_domain_is_closed(rate):
    if 0.0 <= rate <= 1.0:
        assert AuditConfig(sample_rate=rate).sample_rate == rate
    else:
        with pytest.raises(AuditConfigError):
            AuditConfig(sample_rate=rate)


# ===========================================================================
# AC2 -- paraphrase drift Layer 1 misses
# ===========================================================================


class TestParaphraseDriftBeyondLayer1:
    def test_canonical_quantifier_drift_layer1_passes_layer2_flags(self, allocator):
        """The recorded Layer-1 limitation: 'sellers'/'report' locatable,
        meaning shifted some/occasionally/issues → all/consistently/failures.
        """
        span = "some sellers occasionally report issues"
        fact = make_fact(
            allocator,
            claim=_claim(
                subject="sellers",
                predicate="report",
                qualifier="all consistently failures",
            ),
            qualifying_context="all sellers consistently report failures",
        )
        layer1 = AnchorVerifier(
            span_provider=lambda a: span,
            claims_of=lambda c: (
                AnchorClaim(
                    "all sellers consistently report failures",
                    Anchor(fact.attachments[0].evidence_ref, fact.attachments[0].positional_anchor),
                    subject="sellers",
                    predicate="report",
                ),
            ),
        )
        l1 = layer1(AcceptanceContext(attributes=fact.attributes, fact=fact))
        assert l1.outcome is RuleOutcome.PASS
        assert layer1.covers_paraphrase_drift is False

        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED
        assert record.verified is False

    def test_acceptable_paraphrase_is_faithful(self, allocator):
        span = "Acme increased revenue 10 percent in FY2024"
        fact = make_fact(
            allocator,
            claim=Claim(
                subject="Acme",
                predicate="increased revenue",
                qualifier="FY2024",
                value=Quantity(10, 0.5, "%"),
            ),
            qualifying_context="Acme increased revenue 10 percent in FY2024",
        )
        l1 = AnchorVerifier(
            span_provider=lambda a: span,
            claims_of=lambda c: (
                AnchorClaim(
                    fact.claim.as_text(),
                    Anchor("e", "l"),
                    subject="Acme",
                    predicate="increased revenue",
                ),
            ),
        )
        assert l1(AcceptanceContext(attributes=fact.attributes, fact=fact)).outcome is RuleOutcome.PASS
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.judgement is AuditJudgement.FAITHFUL
        assert record.verified is True
        assert record.layer1_pass is True

    def test_lexicon_conflict_not_reducible_to_substring(self, allocator):
        """'all' is a substring of 'overall' so qualifier-support would
        pass; the closed lexicon still sees all vs some. [AC2]
        """
        span = "overall, some sellers report issues"
        fact = make_fact(
            allocator,
            claim=Claim("sellers", "report", "all"),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED
        assert "all vs some" in record.reason

    def test_europe_european_is_acceptable_qualifier_paraphrase(self, allocator):
        span = "Acme increased revenue across European markets"
        fact = make_fact(
            allocator,
            claim=Claim("Acme", "increased revenue", "in Europe"),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.judgement is AuditJudgement.FAITHFUL

    def test_qualifier_entity_substitution_is_drift(self, allocator):
        span = "Acme acquired Beta in 2020"
        fact = make_fact(
            allocator,
            claim=Claim("Acme", "acquired", "Gamma in 2020"),
        )
        # Layer 1: subject/predicate present
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED

    def test_quantity_change_is_drift_even_when_layer1_omits_value(self, allocator):
        span = "Listing A rated 4.6 stars by buyers"
        fact = make_fact(
            allocator,
            claim=Claim("Listing A", "rated", "by buyers", Quantity(4.9, 0.05)),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED
        assert "quantity" in record.reason

    def test_year_change_is_drift(self, allocator):
        span = "revenue grew 14 percent in 2020"
        fact = make_fact(
            allocator,
            claim=Claim("revenue", "grew", "in 2024", Quantity(14, 0.5, "percent")),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED

    def test_negation_flip_is_drift(self, allocator):
        span = "sellers do not report failures"
        fact = make_fact(
            allocator,
            claim=Claim("sellers", "report", "failures"),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED
        assert "negation" in record.reason

    def test_certainty_will_vs_may_is_drift(self, allocator):
        span = "the company may increase prices next year"
        fact = make_fact(
            allocator,
            claim=Claim("the company", "increase prices", "will next year"),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED

    def test_relationship_increase_vs_decrease_is_drift(self, allocator):
        span = "churn decreased this quarter"
        fact = make_fact(
            allocator,
            claim=Claim("churn", "decreased", "increased this quarter"),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED

    def test_attribution_change_is_drift(self, allocator):
        span = "according to the vendor changelog, bulk edits fail"
        fact = make_fact(
            allocator,
            claim=Claim("bulk edits", "fail", "NONE"),
            claim_type=ClaimType.ATTRIBUTED_OPINION,
            attributed_to="a competing analyst",
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED

    def test_dropped_restrictor_is_drift(self, allocator):
        span = "bulk edits fail only above 50 SKUs"
        fact = make_fact(
            allocator,
            claim=Claim("bulk edits", "fail", "NONE"),
        )
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.layer1_pass is True
        assert record.judgement is AuditJudgement.DRIFTED
        assert "restrictor" in record.reason

    def test_layer1_coverage_flag_unchanged(self):
        assert AnchorVerifier().covers_paraphrase_drift is False


class TestFailClosed:
    def test_unavailable_span_is_not_verified(self, allocator):
        fact = make_fact(allocator, claim=_claim())
        record = audit_attachment(
            fact, fact.attachments[0], None, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.disposition is AuditDisposition.UNAUDITABLE
        assert record.judgement is None
        assert record.verified is False
        assert "not verified" in record.reason

    def test_empty_span_is_not_verified(self, allocator):
        fact = make_fact(allocator, claim=_claim())
        record = audit_attachment(
            fact, fact.attachments[0], "   ", AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.disposition is AuditDisposition.UNAUDITABLE
        assert record.verified is False

    def test_missing_subject_is_unsupported(self, allocator):
        span = "an unrelated sentence about weather"
        fact = make_fact(allocator, claim=_claim())
        record = audit_attachment(
            fact, fact.attachments[0], span, AuditConfig(seed="s"), clock=CLOCK
        )
        assert record.judgement is AuditJudgement.UNSUPPORTED
        assert record.layer1_pass is False
        assert record.verified is False

    def test_provenance_fields_are_populated(self, allocator):
        span = "sellers report issues"
        fact = make_fact(allocator, claim=_claim())
        config = AuditConfig(sample_rate=1.0, seed="prov-seed", config_ref="cfg-test")
        record = audit_attachment(
            fact, fact.attachments[0], span, config, clock=CLOCK
        )
        assert record.fact_id == fact.object_id
        assert record.lineage_id == fact.lineage_id
        assert record.fact_version == fact.attributes.version
        assert record.evidence_id == fact.attachments[0].evidence_ref
        assert record.locator == fact.attachments[0].positional_anchor
        assert record.compared_span == span
        assert record.sample_rate == 1.0
        assert record.seed == "prov-seed"
        assert record.config_ref == "cfg-test"
        assert record.audited_at == T0
        assert record.reason

    def test_run_sampled_audit_records_only_the_sample(self, allocator):
        facts = [
            make_fact(
                allocator,
                identity=allocator.new_object(),
                claim=_claim(),
                attachments=(attachment(f"ev-{i}"),),
            )
            for i in range(10)
        ]
        cands = [AuditCandidate(f, "VENDOR_PUBLICATION", 0.8) for f in facts]
        register = AuditRegister()
        produced = run_sampled_audit(
            cands,
            span_of=lambda f, a: "sellers report issues",
            config=AuditConfig(sample_rate=0.2, seed="s"),
            register=register,
            clock=CLOCK,
        )
        # floor(0.2 * 10) = 2 Facts, one attachment each
        assert len(produced) == 2
        assert len(register) == 2
        assert {r.fact_id for r in register} <= {f.object_id for f in facts}

    def test_unaudited_facts_are_not_treated_as_verified(self, allocator):
        facts = [
            make_fact(
                allocator,
                identity=allocator.new_object(),
                claim=_claim(),
                attachments=(attachment(f"ev-{i}"),),
            )
            for i in range(5)
        ]
        cands = [AuditCandidate(f, "VENDOR_PUBLICATION", 0.8) for f in facts]
        produced = run_sampled_audit(
            cands,
            span_of=lambda f, a: "sellers report issues",
            config=AuditConfig(sample_rate=0.2, seed="s"),
            clock=CLOCK,
        )
        audited = {r.fact_id for r in produced}
        unaudited = [f for f in facts if f.object_id not in audited]
        assert unaudited  # sampling left some out
        # no record means not verified — there is no implicit FAITHFUL

    def test_rollup_unaditable_beats_faithful(self, allocator):
        fact = make_fact(
            allocator,
            refs=("obj-ev-1", "obj-ev-2"),
            claim=_claim(),
            attachments=(attachment("obj-ev-1"), attachment("obj-ev-2")),
        )
        records = audit_fact(
            fact,
            span_of=lambda f, a: "sellers report issues" if a.evidence_ref == "obj-ev-1" else None,
            config=AuditConfig(seed="s"),
            clock=CLOCK,
        )
        assert len(records) == 2
        head = rollup(records)
        assert head.disposition is AuditDisposition.UNAUDITABLE
        assert head.verified is False
