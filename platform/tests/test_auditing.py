"""S-5 Layer 2: sampled fidelity audit of accepted Facts. [T03.2.2]

Architecture References:
- S-5     Three-layer extraction fidelity verification. Layer 1 (100
          percent, F-V6) catches fabricated LOCATION; Layer 2 -- the
          sampled audit -- catches paraphrase drift and unsupported
          rendering that structural checks cannot. Layer 3 is the
          published residual metric (T03.2.3, out of scope).
- M-67    Hallucination/drift is measured, not eliminated: the audit
          measures on a sample; nothing assumes zero.
- F-A1    The sampled fidelity audit decision record: global 5 percent
          sample; stratification by SourceType and ConfidenceBand;
          every attachment considered, never first-attachment; one
          audit per Fact per policy version; closed judgement set
          FAITHFUL/DRIFTED/UNSUPPORTED; append-only register outside
          the IOM; auditor identity and timestamps on every judgement;
          no lifecycle effect; no fourth acceptance gate; no LLM/NLP
          (the platform records, the external provider judges).
- N-4     Non-deterministic outputs, statistical verification: the
          sample is a deterministic hash threshold, reproducible
          without runtime randomness.
- N-8     Mechanism/policy separation: install_sampled_audit is
          composition, mirroring install_anchor_verification.
- N-10    Failures recorded, never silent -- and never a gate.
- N-20    Source typing is the closed ratified taxonomy; strata come
          from classify(), never from raw strings.

T03.2.2 acceptance criteria under test (spec platform/validation/
T03.2.2-specification.md section 14, rows 1-28):
  AC1  "Sample rate configurable" -- policy-driven rate, versioned
  AC2  "Audit detects paraphrase drift anchor checks miss" -- rows
       24-25: Layer-1-PASSING Facts judged DRIFTED / UNSUPPORTED
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import threading
from dataclasses import FrozenInstanceError, fields
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

import oip.auditing as auditing_module
from oip.anchoring import evidence_span_provider
from oip.auditing import (
    POLICY_V1,
    AuditContext,
    AuditError,
    AuditJudgement,
    AuditRecord,
    AuditRecordError,
    AuditRegister,
    AlreadyJudgedError,
    DuplicateSelectionError,
    JudgementProvider,
    MetricTrendPoint,
    NoPendingSelectionError,
    QualityMetricSnapshot,
    SamplingPolicy,
    SamplingPolicyError,
    SelectionFailure,
    install_sampled_audit,
    judge_pending,
    metric_trend,
    quality_metrics,
    selects,
)
from oip.claim import Claim, Quantity, UNQUALIFIED
from oip.enums import ConfidenceBand, ObjectType, ObjectStatus, RelationshipType
from oip.fact import ClaimType, EvidenceAttachment, Fact, Independence
from oip.identity import ObjectIdentity
from oip.semantic import Anchor
from oip.source import SourceType
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs
from tests.test_extraction import TICK, VENDOR, Rig, vendor_rig

SUBJECT = "churn rate"
PREDICATE = "stands at"
CONTENT = "Q3 report: churn rate stands at 3.5 percent. Footnote follows."
SPAN = "churn rate stands at 3.5 percent"
MARKET_CONTENT = "Forum post: churn rate stands at 3.5 percent per sellers."
QUALIFYING = "as stated in the vendor report"
VALUE = Quantity(3.5, 0.5, "%")

# AC2 fixtures: both spans contain the claim's subject and predicate,
# so Layer 1 (F-V6) PASSES -- yet the first drops a scope qualifier
# the source states (paraphrase drift) and the second reports an
# unverified rumour (no support). Layer 1 is blind to both; the audit
# is not. [M-67, F-A1 R11]
DRIFT_CONTENT = (
    "Q3 analyst note: churn rate, for the Enterprise segment only, "
    "stands at 3.5 percent. Footnote follows."
)
DRIFT_SPAN = "churn rate, for the Enterprise segment only, stands at 3.5 percent"
UNSUPPORTED_CONTENT = (
    "Market chatter: rumours that churn rate stands at 3.5 percent "
    "remain unverified by the vendor."
)
UNSUPPORTED_SPAN = "rumours that churn rate stands at 3.5 percent"

JUDGED_AT = T0 + timedelta(hours=3)
AUDITOR = "fixture-auditor"
POLICY_RECORDED = POLICY_V1.recorded_at

RATE_ONE = SamplingPolicy(
    version=9, rate=1.0, salt="test-rate-one", recorded_at=POLICY_RECORDED
)
RATE_ZERO = SamplingPolicy(
    version=9, rate=0.0, salt="test-rate-zero", recorded_at=POLICY_RECORDED
)

STRONG_CONF = 0.75  # ConfidenceBand.STRONG under the for_value edges
VENDOR_STRONG = (SourceType.VENDOR_PUBLICATION, ConfidenceBand.STRONG)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FixtureAuditor:
    """Stands in for the external human auditor. [F-A1 R8, R11]

    The platform never interprets content: the judgement comes from
    outside, by contract. The fixture demonstrates the RECORDING
    architecture; the detection claim rests on the external protocol.
    """

    def __init__(self, judgement: AuditJudgement):
        self.judgement = judgement
        self.seen: list[AuditContext] = []

    def judge(self, context: AuditContext) -> AuditJudgement:
        self.seen.append(context)
        return self.judgement


class MappingAuditor(FixtureAuditor):
    """Per-fact judgements, for provider-contract tests."""

    def __init__(self, by_fact: dict[str, AuditJudgement]):
        super().__init__(AuditJudgement.FAITHFUL)
        self.by_fact = dict(by_fact)

    def judge(self, context: AuditContext) -> AuditJudgement:
        self.seen.append(context)
        return self.by_fact[context.fact.object_id]


class _GhostStore:
    """Minimal store double: a selected Fact that vanished."""

    def get_fact(self, object_id: str):
        return None

    def get_evidence(self, evidence_ref: str):
        return None


def _evidence(rig: Rig, source: str, source_type: str, content: str) -> str:
    return rig.acquire(source, source_type, content)


def _fact(
    rig: Rig,
    attachments: tuple[tuple[str, str, float], ...],
    *,
    identity: ObjectIdentity | None = None,
    subject: str = SUBJECT,
    predicate: str = PREDICATE,
    qualifier: str = UNQUALIFIED,
    value: Quantity | None = None,
    qualifying_context: str = QUALIFYING,
) -> Fact:
    """A directly-constructed Fact: acceptance, not extraction, decides.

    attachments: (evidence_ref, positional_anchor, extraction_confidence)
    per attachment -- every attachment carries its own confidence, the
    F-A1 stratification input. [F-A1 R5]
    """
    ceilings = []
    for ref, _, _ in attachments:
        evidence = rig.store.get_evidence(ref)
        assert evidence is not None, f"fixture evidence {ref} missing"
        ceilings.append(evidence.attributes.confidence.effective_confidence)
    attributes = build_attrs(
        identity or rig.store.allocator.new_object(),
        ObjectType.FACT,
        tuple((ref, ObjectType.EVIDENCE) for ref, _, _ in attachments),
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        upstream_ceiling=min(ceilings),
    )
    return Fact(
        attributes=attributes,
        claim=Claim(subject, predicate, qualifier, value),
        claim_type=ClaimType.ASSERTION,
        attachments=tuple(
            EvidenceAttachment(
                evidence_ref=ref,
                positional_anchor=anchor,
                extracted_at=TICK,
                extraction_confidence=confidence,
                independence_assessment=Independence.INDEPENDENT,
            )
            for ref, anchor, confidence in attachments
        ),
        qualifying_context=qualifying_context,
    )


def _write(rig: Rig, fact: Fact) -> Fact:
    stored = rig.store.write_fact(fact)
    return rig.store.get_fact(stored.object_id)


def _install(rig: Rig, policy: SamplingPolicy = RATE_ONE) -> AuditRegister:
    return install_sampled_audit(rig.store, policy)


def _resolver(store: KnowledgeStore):
    """The real span-resolution chain, wired by composition: this is
    exactly what a production composition root injects (the module
    itself must not import oip.anchoring)."""

    def resolve(evidence_ref: str, locator: str) -> str | None:
        evidence = store.get_evidence(evidence_ref)
        if evidence is None or evidence.content.content is None:
            return None
        return evidence_span_provider(evidence.content.content)(
            Anchor(evidence_id=evidence_ref, locator=locator)
        )

    return resolve


def _fixed_identity(n: int) -> ObjectIdentity:
    return ObjectIdentity(f"obj-fixed-{n}", f"lineage-fixed-{n}", 1)


def _separating_salt(
    fact_object_id: str,
    out_stratum: tuple[SourceType, ConfidenceBand],
    in_stratum: tuple[SourceType, ConfidenceBand],
    *,
    rate: float = 0.05,
) -> str:
    """A salt selecting the ``in`` stratum but not the ``out`` stratum
    for this Fact. Found, not invented: the hash is a pure function,
    so a separating salt provably exists and is found deterministically
    in a bounded search. (No seed-pinning [F-A1 R2].)"""
    for i in range(10_000):
        salt = f"sep-{i}"
        policy = SamplingPolicy(
            version=7, rate=rate, salt=salt, recorded_at=POLICY_RECORDED
        )
        if selects(fact_object_id, *in_stratum, policy) and not selects(
            fact_object_id, *out_stratum, policy
        ):
            return salt
    raise AssertionError("no separating salt found in 10,000 tries")


def _ghost_fact() -> Fact:
    """A minimal well-formed Fact attached to nonexistent Evidence --
    for sampler dispatch and context construction only, never written."""
    attributes = build_attrs(
        _fixed_identity(999), ObjectType.FACT, (),
        status=ObjectStatus.ACTIVE, status_reason=None,
    )
    return Fact(
        attributes=attributes,
        claim=Claim(SUBJECT, PREDICATE, UNQUALIFIED, None),
        claim_type=ClaimType.ASSERTION,
        attachments=(
            EvidenceAttachment(
                evidence_ref="no-such-evidence",
                positional_anchor=SPAN,
                extracted_at=TICK,
                extraction_confidence=STRONG_CONF,
                independence_assessment=Independence.INDEPENDENT,
            ),
        ),
        qualifying_context=QUALIFYING,
    )


def _record_kwargs(**overrides) -> dict:
    kwargs = dict(
        fact_object_id="f",
        evidence_ref="e",
        positional_anchor="a",
        source_type=SourceType.VENDOR_PUBLICATION,
        confidence_band=ConfidenceBand.STRONG,
        policy_version=1,
        selected_at=JUDGED_AT,
    )
    kwargs.update(overrides)
    return kwargs


# ---------------------------------------------------------------------------
# Rows 1, 27 -- the default composition
# ---------------------------------------------------------------------------


class TestPolicyDefaults:
    def test_row_1_policy_v1_is_the_five_percent_default(self):
        """[AC1, F-A1 R3/R10] POLICY_V1: version 1, rate 0.05, frozen."""
        assert POLICY_V1.version == 1
        assert POLICY_V1.rate == 0.05
        assert POLICY_V1.salt
        assert POLICY_V1.recorded_at is not None

    def test_row_1_installer_consumes_the_default_policy(self):
        """install_sampled_audit() with no policy uses POLICY_V1: a Fact
        whose stratum selects under POLICY_V1 is registered with
        policy_version 1."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        identity = None
        for i in range(10_000):
            candidate = _fixed_identity(i)
            if selects(candidate.object_id, *VENDOR_STRONG, POLICY_V1):
                identity = candidate
                break
        assert identity is not None
        register = _install(rig, POLICY_V1)
        _write(rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=identity))
        assert len(register) == 1
        assert register.snapshot()[0].policy_version == 1

    def test_row_27_default_store_remains_unwired(self):
        """[spec section 11] The store default is untouched: no sampler,
        zero behaviour, mirroring anchor_verifier [I-1]."""
        assert KnowledgeStore().audit_sampler is None
        rig = vendor_rig("src")
        assert rig.store.audit_sampler is None  # the T03.2.1 rig adds none

    def test_installer_rejects_a_non_policy(self):
        with pytest.raises(SamplingPolicyError):
            install_sampled_audit(KnowledgeStore(), policy="0.05")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Rows 2-7 -- selection semantics
# ---------------------------------------------------------------------------


class TestSelectionSemantics:
    def _three_facts(self, rig: Rig) -> None:
        for i, source in enumerate(("a", "b", "c")):
            ref = _evidence(rig, source, VENDOR, f"{CONTENT} [{i}]")
            _write(
                rig,
                _fact(
                    rig,
                    ((ref, SPAN, STRONG_CONF),),
                    identity=_fixed_identity(100 + i),
                ),
            )

    def test_row_2_rate_zero_selects_nothing(self):
        """[F-A1 R2] rate 0.0: the sample is empty, no failures."""
        rig = vendor_rig("a", "b", "c")
        register = _install(rig, RATE_ZERO)
        self._three_facts(rig)
        assert len(register) == 0
        assert register.pending() == ()
        assert register.selection_failures() == ()

    def test_row_3_rate_one_selects_every_eligible_fact(self):
        """[F-A1 R2] rate 1.0: every Fact with a resolvable attachment
        is selected -- and eligibility requires resolvable Evidence."""
        rig = vendor_rig("a", "b", "c")
        register = _install(rig, RATE_ONE)
        self._three_facts(rig)
        assert len(register) == 3
        assert {r.fact_object_id for r in register} == {
            _fixed_identity(100 + i).object_id for i in range(3)
        }
        # ineligibility: no resolvable Evidence -> no stratum -> no unit
        ghost = _ghost_fact()
        rig.store.audit_sampler(ghost)  # direct dispatch, acceptance-free
        assert len(register) == 3  # unchanged
        assert register.selection_failures() == ()  # skipping is not failure

    def test_row_4_selection_is_deterministic_and_reproducible(self):
        """[F-A1 R2, N-4] Same inputs -> same decision, every call;
        equal policies (frozen value semantics) decide identically."""
        twin = SamplingPolicy(
            version=1, rate=0.05, salt="f-a1-v1", recorded_at=POLICY_RECORDED
        )
        assert twin == POLICY_V1
        for i in range(50):
            fact_id = _fixed_identity(i).object_id
            expected = selects(fact_id, *VENDOR_STRONG, POLICY_V1)
            assert selects(fact_id, *VENDOR_STRONG, twin) == expected
            assert selects(fact_id, *VENDOR_STRONG, POLICY_V1) == expected

    @given(
        fact_id=st.text(min_size=1, max_size=40).filter(lambda s: s.strip()),
        source_type=st.sampled_from(list(SourceType)),
        band=st.sampled_from(list(ConfidenceBand)),
        rate_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        rate_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_row_5_property_invariants(
        self,
        fact_id: str,
        source_type: SourceType,
        band: ConfidenceBand,
        rate_a: float,
        rate_b: float,
    ):
        """[F-A1 R2, N-4] Determinism, rate boundaries, monotonicity in
        the rate -- the hash threshold must respect all three."""
        low, high = (rate_a, rate_b) if rate_a <= rate_b else (rate_b, rate_a)
        policy_low = SamplingPolicy(
            version=1, rate=low, salt="prop", recorded_at=POLICY_RECORDED
        )
        policy_high = SamplingPolicy(
            version=1, rate=high, salt="prop", recorded_at=POLICY_RECORDED
        )
        at_low = selects(fact_id, source_type, band, policy_low)
        # determinism: repeated calls agree
        assert at_low == selects(fact_id, source_type, band, policy_low)
        # monotonicity: selected at the lower rate -> selected at the higher
        if at_low:
            assert selects(fact_id, source_type, band, policy_high)
            assert low > 0.0  # nothing is selected at rate 0
        # boundaries: rate 0.0 never selects; rate 1.0 always selects
        zero = SamplingPolicy(
            version=1, rate=0.0, salt="prop", recorded_at=POLICY_RECORDED
        )
        one = SamplingPolicy(
            version=1, rate=1.0, salt="prop", recorded_at=POLICY_RECORDED
        )
        assert not selects(fact_id, source_type, band, zero)
        assert selects(fact_id, source_type, band, one)

    def test_row_6_policy_version_and_salt_isolate_samples(self):
        """[F-A1 R2/R10] A new version/salt re-derives the sample: old
        selections are not consulted, and a Fact audited under one
        version may be audited again under the next."""
        # (a) the salt participates in the hash: decisions flip with it
        fact_id = _fixed_identity(0).object_id
        yes_salts: list[str] = []
        no_salts: list[str] = []
        for i in range(10_000):
            salt = f"iso-{i}"
            policy = SamplingPolicy(
                version=1, rate=0.05, salt=salt, recorded_at=POLICY_RECORDED
            )
            (yes_salts if selects(fact_id, *VENDOR_STRONG, policy) else no_salts).append(salt)
            if yes_salts and no_salts:
                break
        assert yes_salts and no_salts  # the salt re-derives the decision

        # (b) version-keyed dedup: v1 selects; v2 re-selects the SAME Fact
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        identity = _fixed_identity(1)
        v1 = SamplingPolicy(
            version=1, rate=1.0, salt="iso-a", recorded_at=POLICY_RECORDED
        )
        v2 = SamplingPolicy(
            version=2, rate=1.0, salt="iso-b", recorded_at=POLICY_RECORDED
        )
        register_v1 = _install(rig, v1)
        stored = _write(rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=identity))
        assert register_v1.has_selection(stored.object_id, 1)
        # a second dispatch under v1 dedups quietly (one audit per version)
        rig.store.audit_sampler(rig.store.get_fact(stored.object_id))
        assert len(register_v1) == 1
        assert register_v1.selection_failures() == ()
        # a superseding version is a NEW sample domain: re-derive freely
        register_v2 = _install(rig, v2)
        rig.store.audit_sampler(rig.store.get_fact(stored.object_id))
        assert register_v1.has_selection(stored.object_id, 1)
        assert register_v2.has_selection(stored.object_id, 2)
        assert len(register_v2) == 1
        assert register_v2.snapshot()[0].policy_version == 2

    def test_row_7_selection_is_insertion_order_independent(self):
        """[F-A1 R2] The selection set over a fixed population does not
        depend on the order Facts are written or registered. Fixed
        identities make the two rigs decide over the same population."""
        selected: list[ObjectIdentity] = []
        unselected: list[ObjectIdentity] = []
        for i in range(10_000):
            candidate = _fixed_identity(i)
            if selects(candidate.object_id, *VENDOR_STRONG, POLICY_V1):
                if len(selected) < 2:
                    selected.append(candidate)
            elif len(unselected) < 2:
                unselected.append(candidate)
            if len(selected) == 2 and len(unselected) == 2:
                break
        assert len(selected) == 2 and len(unselected) == 2
        population = selected + unselected

        def scenario(order: list[ObjectIdentity]) -> set[str]:
            rig = vendor_rig("a", "b", "c", "d")
            register = _install(rig, POLICY_V1)
            sources = ("a", "b", "c", "d")
            refs = {
                identity.object_id: _evidence(rig, source, VENDOR, CONTENT)
                for identity, source in zip(population, sources)
            }
            for identity in order:
                _write(
                    rig,
                    _fact(
                        rig,
                        ((refs[identity.object_id], SPAN, STRONG_CONF),),
                        identity=identity,
                    ),
                )
            return {r.fact_object_id for r in register}

        forward = scenario(population)
        backward = scenario(list(reversed(population)))
        assert forward == backward == {i.object_id for i in selected}


# ---------------------------------------------------------------------------
# Rows 8, 9, 11, 12, 13 -- stratification and attachment semantics
# ---------------------------------------------------------------------------


class TestStratification:
    def test_row_8_strata_map_the_ratified_vocabularies(self):
        """[F-A1 R4] source_type via classify onto the closed taxonomy;
        confidence via ConfidenceBand.for_value edges -- never collapsed,
        never invented."""
        rig = vendor_rig(
            "mkt", "reg", mkt="MARKETPLACE_LISTING", reg="REGULATORY_FILING"
        )
        market = _evidence(
            rig, "mkt", "MARKETPLACE_LISTING",
            "Listing: churn rate stands at 3.5 percent this quarter.",
        )
        regulatory = _evidence(
            rig, "reg", "REGULATORY_FILING",
            "Filing: churn rate stands at 3.5 percent per disclosure.",
        )
        register = _install(rig, RATE_ONE)
        m_fact = _write(
            rig,
            _fact(
                rig,
                ((market, "churn rate stands at 3.5 percent", 0.79),),
                identity=_fixed_identity(200),
            ),
        )
        r_fact = _write(
            rig,
            _fact(
                rig,
                ((regulatory, "churn rate stands at 3.5 percent", 0.80),),
                identity=_fixed_identity(201),
            ),
        )
        m_record = register.for_fact(m_fact.object_id)[0]
        r_record = register.for_fact(r_fact.object_id)[0]
        assert m_record.source_type is SourceType.MARKETPLACE_LISTING
        assert m_record.confidence_band is ConfidenceBand.STRONG  # 0.79 edge
        assert r_record.source_type is SourceType.REGULATORY_FILING
        assert r_record.confidence_band is ConfidenceBand.VERY_STRONG  # 0.80

    def test_row_9_every_attachment_is_eligible_never_first_only(self):
        """[F-A1 R5] A Fact whose FIRST attachment's stratum is not
        selected is still selected through a later attachment's stratum:
        multi-attachment eligibility is total."""
        rig = vendor_rig("ven", "mkt", mkt="MARKETPLACE_LISTING")
        vendor_ref = _evidence(rig, "ven", VENDOR, CONTENT)
        market_ref = _evidence(rig, "mkt", "MARKETPLACE_LISTING", MARKET_CONTENT)
        identity = _fixed_identity(300)
        market_stratum = (SourceType.MARKETPLACE_LISTING, ConfidenceBand.STRONG)
        salt = _separating_salt(identity.object_id, VENDOR_STRONG, market_stratum)
        policy = SamplingPolicy(
            version=7, rate=0.05, salt=salt, recorded_at=POLICY_RECORDED
        )
        register = _install(rig, policy)
        _write(
            rig,
            _fact(
                rig,
                (
                    (vendor_ref, SPAN, STRONG_CONF),  # first attachment: NOT selected
                    (market_ref, SPAN, STRONG_CONF),  # later attachment: selected
                ),
                identity=identity,
            ),
        )
        assert len(register) == 1
        record = register.snapshot()[0]
        assert record.evidence_ref == market_ref  # via the later attachment

    def test_row_11_the_unit_retains_the_selecting_attachment(self):
        """[F-A1 R5] evidence_ref, positional_anchor, source_type and
        confidence_band of the selecting attachment are retained."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ONE)
        _write(
            rig,
            _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(400)),
        )
        record = register.snapshot()[0]
        assert record.evidence_ref == ref
        assert record.positional_anchor == SPAN
        assert record.source_type is SourceType.VENDOR_PUBLICATION
        assert record.confidence_band is ConfidenceBand.STRONG

    def test_row_12_tie_break_is_deterministic_across_attachment_orders(self):
        """[F-A1 R5] When several strata select, the lexicographically
        first stratum wins -- whatever the attachment order."""
        rig = vendor_rig("ven", "mkt", mkt="MARKETPLACE_LISTING")
        vendor_ref = _evidence(rig, "ven", VENDOR, CONTENT)
        market_ref = _evidence(rig, "mkt", "MARKETPLACE_LISTING", MARKET_CONTENT)
        register = _install(rig, RATE_ONE)
        _write(
            rig,
            _fact(
                rig,
                ((vendor_ref, SPAN, STRONG_CONF), (market_ref, SPAN, STRONG_CONF)),
                identity=_fixed_identity(410),
            ),
        )
        _write(
            rig,
            _fact(
                rig,
                ((market_ref, SPAN, STRONG_CONF), (vendor_ref, SPAN, STRONG_CONF)),
                identity=_fixed_identity(411),
            ),
        )
        # MARKETPLACE_LISTING < VENDOR_PUBLICATION lexicographically
        for record in register:
            assert record.source_type is SourceType.MARKETPLACE_LISTING
            assert record.evidence_ref == market_ref

    def test_row_13_no_confidence_collapse_no_fact_mutation(self):
        """[F-A1 R5] The band comes from the ATTACHMENT's extraction
        confidence, never collapsed into the object's confidence; the
        Fact carries no audit fields and is never mutated."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ONE)
        fact = _fact(
            rig,
            ((ref, SPAN, 0.10),),  # NEGLIGIBLE attachment confidence
            identity=_fixed_identity(420),
        )
        stored = _write(rig, fact)
        record = register.snapshot()[0]
        assert record.confidence_band is ConfidenceBand.NEGLIGIBLE
        # the object's own confidence is high and was not consulted
        assert stored.attributes.confidence.effective_confidence > 0.5
        # Fact model carries no audit vocabulary at all
        fact_fields = {f.name for f in fields(Fact)}
        assert not any(
            name in fact_fields
            for name in ("judgement", "judged_at", "auditor", "audit", "audited")
        )
        # and the stored Fact is untouched by selection
        assert stored.claim == fact.claim
        assert stored.attachments == fact.attachments
        assert stored.qualifying_context == fact.qualifying_context


# ---------------------------------------------------------------------------
# Row 10 -- single-audit dedup per policy version
# ---------------------------------------------------------------------------


class TestDedup:
    def test_row_10_register_refuses_a_duplicate_selection(self):
        """[F-A1 R5] The register refuses a second selection of the
        same Fact under the same policy version."""
        register = AuditRegister()
        record = AuditRecord(**_record_kwargs(fact_object_id="dup-fact"))
        assert register.select(record) is record
        with pytest.raises(DuplicateSelectionError):
            register.select(AuditRecord(**_record_kwargs(fact_object_id="dup-fact")))
        assert len(register) == 1

    def test_row_10_sampler_dedups_quietly(self):
        """[F-A1 R5] A second dispatch of an already-selected Fact
        under the same policy is satisfied silently: no new unit, no
        failure, no exception into the write path."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ONE)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(450))
        )
        assert len(register) == 1
        rig.store.audit_sampler(rig.store.get_fact(stored.object_id))
        rig.store.audit_sampler(rig.store.get_fact(stored.object_id))
        assert len(register) == 1
        assert register.selection_failures() == ()
        assert register.has_selection(stored.object_id, RATE_ONE.version)


# ---------------------------------------------------------------------------
# Rows 14-18 -- register semantics
# ---------------------------------------------------------------------------


class TestRegisterSemantics:
    def _population(self, rig: Rig, count: int) -> list[Fact]:
        written = []
        for i in range(count):
            ref = _evidence(rig, f"src-{i}", VENDOR, f"{CONTENT} [{i}]")
            written.append(
                _write(
                    rig,
                    _fact(
                        rig,
                        ((ref, SPAN, STRONG_CONF),),
                        identity=_fixed_identity(500 + i),
                    ),
                )
            )
        return written

    def test_row_14_register_is_append_only_pending_visible(self):
        """[F-A1 R6/R7] Selections are only added; pending records carry
        no judgement; completion never removes anything."""
        rig = vendor_rig(*(f"src-{i}" for i in range(3)))
        register = _install(rig, RATE_ONE)
        self._population(rig, 3)
        assert len(register) == 3
        assert all(r.is_pending for r in register)
        assert all(r.judgement is None for r in register.pending())
        before = [r.fact_object_id for r in register.snapshot()]
        judged = judge_pending(
            rig.store,
            register,
            FixtureAuditor(AuditJudgement.DRIFTED),
            auditor=AUDITOR,
            clock=lambda: JUDGED_AT,
        )
        assert judged == 3
        after = [r.fact_object_id for r in register.snapshot()]
        assert after == before  # append-only: same units, same order
        assert len(register) == 3
        assert register.pending() == ()

    def test_row_15_judgement_on_unknown_selection_rejected(self):
        rig = vendor_rig("src")
        _evidence(rig, "src", VENDOR, CONTENT)
        register = AuditRegister()
        with pytest.raises(NoPendingSelectionError):
            register.record_judgement(
                "never-selected", 1, AuditJudgement.FAITHFUL, auditor=AUDITOR
            )

    def test_row_16_double_judgement_rejected_completed_immutable(self):
        """[F-A1 R7] Judgements complete exactly once and are then
        immutable; the record itself is frozen."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ONE)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(520))
        )
        completed = register.record_judgement(
            stored.object_id,
            RATE_ONE.version,
            AuditJudgement.DRIFTED,
            auditor=AUDITOR,
            judged_at=JUDGED_AT,
        )
        with pytest.raises(AlreadyJudgedError):
            register.record_judgement(
                stored.object_id,
                RATE_ONE.version,
                AuditJudgement.FAITHFUL,
                auditor="someone-else",
                judged_at=JUDGED_AT,
            )
        # the failed attempt changed nothing
        assert register.for_fact(stored.object_id) == (completed,)
        assert completed.judgement is AuditJudgement.DRIFTED
        assert completed.auditor == AUDITOR
        assert completed.judged_at == JUDGED_AT
        with pytest.raises(FrozenInstanceError):
            completed.judgement = AuditJudgement.FAITHFUL  # type: ignore[misc]

    def test_row_17_unaudited_fact_has_no_judgement_ever(self):
        """[F-A1 R7] Nothing defaults to FAITHFUL: an unselected Fact
        has no record, no judgement, and a pending record cannot carry
        judgement metadata."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ZERO)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(530))
        )
        assert register.for_fact(stored.object_id) == ()
        assert register.pending() == ()
        with pytest.raises(NoPendingSelectionError):
            register.record_judgement(
                stored.object_id, RATE_ONE.version, AuditJudgement.FAITHFUL, auditor=AUDITOR
            )
        # a pending record cannot smuggle judgement metadata
        with pytest.raises(AuditRecordError):
            AuditRecord(**_record_kwargs(auditor="x"))

    def test_row_18_judgement_set_is_closed(self):
        """[F-A1 R7] Only the three ratified values exist; raw strings,
        invented values, and provider breaches are refused, never
        coerced and never defaulted."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ONE)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(540))
        )
        with pytest.raises(AuditRecordError):
            register.record_judgement(
                stored.object_id, RATE_ONE.version, "DRIFTED", auditor=AUDITOR  # type: ignore[arg-type]
            )
        with pytest.raises(AuditRecordError):
            register.record_judgement(
                stored.object_id, RATE_ONE.version, AuditJudgement.DRIFTED, auditor="   "
            )
        with pytest.raises(ValueError):
            AuditJudgement("BOGUS")
        with pytest.raises(AuditRecordError):
            AuditRecord(
                **_record_kwargs(
                    judgement="FAITHFUL",  # type: ignore[arg-type]
                    judged_at=JUDGED_AT,
                    auditor=AUDITOR,
                )
            )
        # the record is still pending: the breach recorded nothing
        assert register.pending()[0].fact_object_id == stored.object_id

        class RogueProvider:
            def judge(self, context):  # type: ignore[no-untyped-def]
                return "looks-faithful-to-me"  # outside the closed set

        with pytest.raises(AuditRecordError):
            judge_pending(rig.store, register, RogueProvider(), auditor=AUDITOR)
        assert register.pending()[0].judgement is None  # breach left no trace


# ---------------------------------------------------------------------------
# Rows 19, 24, 25, 26 -- the judgement flow and AC2
# ---------------------------------------------------------------------------


class TestJudgementFlow:
    def _selected_fixture(
        self, rig: Rig, content: str, span: str, *, identity: int
    ) -> tuple[AuditRegister, Fact]:
        ref = _evidence(rig, "src", VENDOR, content)
        register = _install(rig, RATE_ONE)
        stored = _write(
            rig,
            _fact(
                rig,
                ((ref, span, STRONG_CONF),),
                identity=_fixed_identity(identity),
                value=VALUE,
            ),
        )
        assert len(register) == 1
        return register, stored

    def test_row_19_provider_judgements_recorded_exactly(self):
        """[F-A1 R8/R11] The platform records exactly what the provider
        returns -- FAITHFUL included; auditor and timestamp are
        retained on every completed record."""
        rig = vendor_rig("a", "b")
        register = _install(rig, RATE_ONE)
        by_fact = {}
        for i, source in enumerate(("a", "b")):
            ref = _evidence(rig, source, VENDOR, f"{CONTENT} [{i}]")
            stored = _write(
                rig,
                _fact(
                    rig,
                    ((ref, SPAN, STRONG_CONF),),
                    identity=_fixed_identity(600 + i),
                ),
            )
            by_fact[stored.object_id] = (
                AuditJudgement.FAITHFUL if i == 0 else AuditJudgement.DRIFTED
            )
        provider = MappingAuditor(by_fact)
        judged = judge_pending(
            rig.store,
            register,
            provider,
            auditor=AUDITOR,
            clock=lambda: JUDGED_AT,
        )
        assert judged == 2
        for record in register.snapshot():
            assert record.judgement is by_fact[record.fact_object_id]
            assert record.judgement is not None  # explicit, never default
            assert record.auditor == AUDITOR
            assert record.judged_at == JUDGED_AT

    def test_row_24_ac2_fixture_a_layer1_pass_then_drifted(self):
        """[AC2, F-A1 R11, M-67] The anchor resolves and the claim's
        components are present, so Layer 1 PASSES -- yet the span
        scopes the figure to the Enterprise segment while the claim is
        unqualified: paraphrase drift Layer 1 cannot see. The fixture
        auditor judges DRIFTED; the platform records it."""
        rig = vendor_rig("src")
        register, stored = self._selected_fixture(
            rig, DRIFT_CONTENT, DRIFT_SPAN, identity=610
        )
        # Layer 1 genuinely passed this Fact
        assert rig.anchor_verifier.checked == 1
        assert rig.anchor_verifier.failed == 0
        auditor = FixtureAuditor(AuditJudgement.DRIFTED)
        judged = judge_pending(
            rig.store,
            register,
            auditor,
            span_provider=_resolver(rig.store),
            auditor=AUDITOR,
            clock=lambda: JUDGED_AT,
        )
        assert judged == 1
        record = register.snapshot()[0]
        assert record.fact_object_id == stored.object_id
        assert record.judgement is AuditJudgement.DRIFTED
        assert record.auditor == AUDITOR
        assert record.judged_at == JUDGED_AT
        # the drifted Fact is untouched: still ACTIVE, no transition
        assert (
            rig.store.get_fact(stored.object_id).attributes.status
            is ObjectStatus.ACTIVE
        )

    def test_row_25_ac2_fixture_b_layer1_pass_then_unsupported(self):
        """[AC2, F-A1 R11] The span reports an unverified rumour: the
        components are present (Layer 1 passes) but the source does not
        support the assertion. Judged UNSUPPORTED; recorded."""
        rig = vendor_rig("src")
        register, stored = self._selected_fixture(
            rig, UNSUPPORTED_CONTENT, UNSUPPORTED_SPAN, identity=611
        )
        assert rig.anchor_verifier.checked == 1
        assert rig.anchor_verifier.failed == 0
        judge_pending(
            rig.store,
            register,
            FixtureAuditor(AuditJudgement.UNSUPPORTED),
            span_provider=_resolver(rig.store),
            auditor=AUDITOR,
            clock=lambda: JUDGED_AT,
        )
        record = register.snapshot()[0]
        assert record.fact_object_id == stored.object_id
        assert record.judgement is AuditJudgement.UNSUPPORTED

    def test_row_26_audit_context_presents_the_full_source_context(self):
        """[F-A1 R11] The context exposes the claim, the qualifying
        context, the Evidence identity, and the EXACT anchored span."""
        rig = vendor_rig("src")
        register, _ = self._selected_fixture(rig, DRIFT_CONTENT, DRIFT_SPAN, identity=612)
        auditor = FixtureAuditor(AuditJudgement.DRIFTED)
        judge_pending(
            rig.store,
            register,
            auditor,
            span_provider=_resolver(rig.store),
            auditor=AUDITOR,
            clock=lambda: JUDGED_AT,
        )
        assert len(auditor.seen) == 1
        context = auditor.seen[0]
        assert context.fact.claim.subject == SUBJECT
        assert context.fact.claim.predicate == PREDICATE
        assert SUBJECT in context.fact.claim.as_text()
        assert context.fact.qualifying_context == QUALIFYING
        assert context.evidence is not None
        assert context.evidence.attributes.object_id == context.evidence_ref
        assert context.span == DRIFT_SPAN  # exact source-span presentation
        assert context.source_type is SourceType.VENDOR_PUBLICATION
        assert context.confidence_band is ConfidenceBand.STRONG
        assert context.policy_version == RATE_ONE.version


# ---------------------------------------------------------------------------
# Rows 20, 21, 22 -- non-gating, failures, no lifecycle effect
# ---------------------------------------------------------------------------


class TestNonGating:
    def test_row_20_acceptance_identical_with_and_without_sampler(self):
        """[F-A1 R1/R8] The sampler changes no acceptance outcome: the
        same Fact is accepted identically, and a Fact acceptance
        rejects is rejected identically -- the sampler only ever runs
        AFTER commitment. There is no fourth N-2 gate."""
        # accepted case
        plain_rig = vendor_rig("src")
        audited_rig = vendor_rig("src")
        register = _install(audited_rig, RATE_ONE)
        for rig in (plain_rig, audited_rig):
            ref = _evidence(rig, "src", VENDOR, CONTENT)
            stored = _write(
                rig,
                _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(700)),
            )
            assert stored.attributes.status is ObjectStatus.ACTIVE
            assert rig.anchor_verifier.checked == 1
            assert rig.anchor_verifier.failed == 0
        assert len(register) == 1  # audited side selected; plain side unaware
        assert plain_rig.store.audit_sampler is None

        # rejected case: fabricated anchor
        plain_rig = vendor_rig("src")
        audited_rig = vendor_rig("src")
        register = _install(audited_rig, RATE_ONE)
        for rig in (plain_rig, audited_rig):
            ref = _evidence(rig, "src", VENDOR, CONTENT)
            fabricated = _fact(
                rig,
                ((ref, "chars 900-950", STRONG_CONF),),
                identity=_fixed_identity(701),
            )
            with pytest.raises(WriteRejectedError) as excinfo:
                rig.store.write_fact(fabricated)
            assert excinfo.value.failure.rule_ids == ("F-V6",)
        # a rejected Fact is never sampled and never a failure
        assert len(register) == 0
        assert register.selection_failures() == ()

    def test_row_21_sampler_failure_never_blocks_and_is_recorded(
        self, monkeypatch
    ):
        """[F-A1 R1, N-10] A sampler that fails mid-selection leaves
        the committed acceptance standing, records the failure, and
        reports it through on_error; a sampler that raises outright is
        contained by the store's hook guard."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        seen: list[tuple[str, BaseException]] = []
        register = install_sampled_audit(
            rig.store,
            RATE_ONE,
            on_error=lambda fact, exc: seen.append((fact.object_id, exc)),
        )

        def _explode(source_type: str) -> SourceType:
            raise RuntimeError("taxonomy unavailable")

        monkeypatch.setattr(auditing_module, "classify", _explode)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(720))
        )
        monkeypatch.undo()
        # the acceptance stands
        assert stored.attributes.status is ObjectStatus.ACTIVE
        assert rig.anchor_verifier.failed == 0
        # the failure is recorded, never silent [N-10]
        failures = register.selection_failures()
        assert len(failures) == 1
        assert failures[0].fact_object_id == stored.object_id
        assert failures[0].policy_version == RATE_ONE.version
        assert "taxonomy unavailable" in failures[0].detail
        assert failures[0].occurred_at is not None
        # nothing was selected for the failed sampling
        assert len(register) == 0
        # on_error routed the same failure to the composition surface
        assert len(seen) == 1
        fact_id, exc = seen[0]
        assert fact_id == stored.object_id
        assert isinstance(exc, RuntimeError)

        # a sampler that raises outright: the store guard contains it
        boom_rig = vendor_rig("src")
        boom_ref = _evidence(boom_rig, "src", VENDOR, CONTENT)
        boom_rig.store.audit_sampler = lambda fact: 1 / 0
        stored = _write(
            boom_rig,
            _fact(boom_rig, ((boom_ref, SPAN, STRONG_CONF),), identity=_fixed_identity(721)),
        )
        assert stored.attributes.status is ObjectStatus.ACTIVE

    def test_row_21_on_error_raising_is_contained_and_recorded(
        self, monkeypatch
    ):
        """[N-10] A broken on_error callback cannot smuggle an
        exception into the write path either; its own failure is
        recorded."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)

        def _bad_callback(fact, exc):  # type: ignore[no-untyped-def]
            raise RuntimeError("callback itself broken")

        register = install_sampled_audit(rig.store, RATE_ONE, on_error=_bad_callback)

        def _explode(source_type: str) -> SourceType:
            raise RuntimeError("taxonomy unavailable")

        monkeypatch.setattr(auditing_module, "classify", _explode)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(722))
        )
        monkeypatch.undo()
        assert stored.attributes.status is ObjectStatus.ACTIVE
        # both the sampling failure and the callback failure are recorded
        assert len(register.selection_failures()) == 2

    def test_row_22_no_lifecycle_effect_no_object_model_additions(self):
        """[F-A1 R9] DRIFTED and UNSUPPORTED change nothing: no status
        transition, no relationship, no graph edge; downstream writes
        are unaffected; the closed vocabularies gained no members."""
        rig = vendor_rig("a", "b", "c")
        register = _install(rig, RATE_ONE)
        by_fact = {}
        for i, source in enumerate(("a", "b")):
            content = DRIFT_CONTENT if i == 0 else UNSUPPORTED_CONTENT
            span = DRIFT_SPAN if i == 0 else UNSUPPORTED_SPAN
            ref = _evidence(rig, source, VENDOR, content)
            stored = _write(
                rig,
                _fact(
                    rig,
                    ((ref, span, STRONG_CONF),),
                    identity=_fixed_identity(730 + i),
                    value=VALUE,
                ),
            )
            by_fact[stored.object_id] = (
                AuditJudgement.DRIFTED if i == 0 else AuditJudgement.UNSUPPORTED
            )
        judge_pending(
            rig.store,
            register,
            MappingAuditor(by_fact),
            auditor=AUDITOR,
            clock=lambda: JUDGED_AT,
        )
        graph_size = rig.store.graph.edge_count
        for fact_id, judgement in by_fact.items():
            fact = rig.store.get_fact(fact_id)
            assert fact.attributes.status is ObjectStatus.ACTIVE
            assert register.for_fact(fact_id)[0].judgement is judgement
        assert rig.store.graph.edge_count == graph_size  # audit added no edge
        # downstream acceptance is unblocked after adverse judgements
        ref = _evidence(rig, "c", VENDOR, CONTENT)
        fresh = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(740))
        )
        assert fresh.attributes.status is ObjectStatus.ACTIVE
        # the closed vocabularies are unchanged: no audit vocabulary
        assert not hasattr(ObjectStatus, "AUDITED")
        assert not hasattr(RelationshipType, "AUDITS")
        assert not hasattr(ObjectType, "AUDIT")
        assert all(m.name != "AUDITED" for m in ObjectStatus)
        assert all(m.name != "AUDITS" for m in RelationshipType)


# ---------------------------------------------------------------------------
# Rows 23, 28 -- traceability and the T03.2.3 boundary
# ---------------------------------------------------------------------------


class TestTraceabilityAndScope:
    def test_row_23_every_record_carries_its_policy_version(self):
        """[F-A1 R10] Policy-version traceability on every audit unit,
        across installs and versions."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", VENDOR, CONTENT)
        v1 = SamplingPolicy(
            version=1, rate=1.0, salt="trace-a", recorded_at=POLICY_RECORDED
        )
        register_v1 = _install(rig, v1)
        stored = _write(
            rig, _fact(rig, ((ref, SPAN, STRONG_CONF),), identity=_fixed_identity(800))
        )
        v2 = SamplingPolicy(
            version=2, rate=1.0, salt="trace-b", recorded_at=POLICY_RECORDED
        )
        register_v2 = _install(rig, v2)
        rig.store.audit_sampler(rig.store.get_fact(stored.object_id))
        for register, version in ((register_v1, 1), (register_v2, 2)):
            assert len(register) == 1
            record = register.snapshot()[0]
            assert record.policy_version == version
            assert record.policy_version >= 1

    def test_row_28_no_rate_or_metric_computation_on_the_surface(self):
        """[F-A1 R10, T03.2.3 boundary] The register computes nothing:
        no rate, no residual metric, no hallucination estimate. Its
        public surface is recording and reading, exactly."""
        public = {name for name in dir(AuditRegister) if not name.startswith("_")}
        assert public == {
            "select",
            "has_selection",
            "record_judgement",
            "record_failure",
            "snapshot",
            "for_fact",
            "pending",
            "selection_failures",
        }
        for name in public:
            assert not any(
                token in name.lower()
                for token in ("rate", "metric", "hallucin", "drift_", "publish")
            )
        record_fields = {f.name for f in fields(AuditRecord)}
        assert record_fields == {
            "fact_object_id",
            "evidence_ref",
            "positional_anchor",
            "source_type",
            "confidence_band",
            "policy_version",
            "selected_at",
            "judgement",
            "judged_at",
            "auditor",
        }
        failure_fields = {f.name for f in fields(SelectionFailure)}
        assert failure_fields == {
            "fact_object_id",
            "policy_version",
            "detail",
            "occurred_at",
        }


# ---------------------------------------------------------------------------
# T03.2.2 correction-pass tests (independent-review findings): the
# multi-stratum union-selection semantics are acknowledged in
# RATIFICATION-ANNOTATIONS section 14 and the SamplingPolicy docstring;
# these tests pin the behaviors the review found unpinned.
# ---------------------------------------------------------------------------


class TestRegisterConcurrency:
    """Real concurrent register access (spec section 9: RLock-guarded,
    N-11). Thread contention, not lock inspection: racing selections,
    racing judgement completions, and continuous snapshot/iteration
    reads must never corrupt state, lose a record, duplicate a
    completed judgement, or raise on a valid operation. [T03.2.2
    correction pass, review finding F2a]"""

    N_FACTS = 12
    RACERS_PER_FACT = 2
    READERS = 4
    READ_ROUNDS = 300

    @staticmethod
    def _record(i: int) -> AuditRecord:
        return AuditRecord(
            fact_object_id=f"conc-{i}",
            evidence_ref=f"ev-{i}",
            positional_anchor=f"chars {i}-{i + 1}",
            source_type=SourceType.VENDOR_PUBLICATION,
            confidence_band=ConfidenceBand.STRONG,
            policy_version=1,
            selected_at=JUDGED_AT,
        )

    def _readers(self, barrier, register: AuditRegister, errors: list) -> list:
        def reader() -> None:
            try:
                barrier.wait(timeout=30)
                for _ in range(self.READ_ROUNDS):
                    snap = register.snapshot()
                    keys = [(r.fact_object_id, r.policy_version) for r in snap]
                    assert len(set(keys)) == len(keys)  # never duplicated
                    register.pending()
                    register.for_fact("conc-0")
                    for _ in register:
                        pass
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        return [threading.Thread(target=reader) for _ in range(self.READERS)]

    def test_concurrent_selection_completion_and_reads(self):
        register = AuditRegister()
        errors: list = []
        outcomes: list = []
        n, racers = self.N_FACTS, self.RACERS_PER_FACT

        def selector(i: int) -> None:
            try:
                barrier.wait(timeout=30)
                register.select(self._record(i % n))
                outcomes.append("selected")
            except DuplicateSelectionError:
                outcomes.append("select-dup")  # the racing twin won
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def completer(i: int) -> None:
            try:
                barrier.wait(timeout=30)
                register.record_judgement(
                    f"conc-{i % n}", 1, AuditJudgement.DRIFTED,
                    auditor=AUDITOR, judged_at=JUDGED_AT,
                )
                outcomes.append("judged")
            except AlreadyJudgedError:
                outcomes.append("judge-dup")  # exactly-once: twin won
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def run(threads: list) -> None:
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            assert not any(t.is_alive() for t in threads)

        # Phase 1: racing duplicate selections + continuous reads.
        barrier = threading.Barrier(n * racers + self.READERS)
        threads = self._readers(barrier, register, errors)
        threads += [
            threading.Thread(target=selector, args=(i,))
            for i in range(n * racers)
        ]
        run(threads)
        assert errors == []
        assert outcomes.count("selected") == n
        assert outcomes.count("select-dup") == n

        # Phase 2: racing completions of the same selections + reads.
        outcomes.clear()
        barrier = threading.Barrier(n * racers + self.READERS)
        threads = self._readers(barrier, register, errors)
        threads += [
            threading.Thread(target=completer, args=(i,))
            for i in range(n * racers)
        ]
        run(threads)

        # No race-induced exception on valid operations; exactly-once
        # completion; nothing lost, nothing duplicated, no corruption.
        assert errors == []
        assert outcomes.count("judged") == n
        assert outcomes.count("judge-dup") == n
        snap = register.snapshot()
        assert len(snap) == n
        keys = [(r.fact_object_id, r.policy_version) for r in snap]
        assert len(set(keys)) == n
        assert all(r.judgement is AuditJudgement.DRIFTED for r in snap)
        assert all(r.auditor == AUDITOR for r in snap)
        assert all(r.judged_at == JUDGED_AT for r in snap)
        assert register.pending() == ()
        assert len(register) == n
        assert register.selection_failures() == ()


class TestWithinStratumRetention:
    """A Fact with multiple attachments in the SAME stratum: the
    retained audit context is the first contributing attachment in the
    Fact's frozen attachment order -- the current deterministic
    retention semantics (spec section 8.3/8.6: a stratum selects "via
    its contributing attachment"; the F-A1 R5 tie-break governs
    selection AMONG strata, which the lexicographic rule settles).
    Pinned so retention cannot silently drift into arbitrary
    hash/set-iteration dependence. [T03.2.2 correction pass, review
    finding F2b]"""

    def test_same_stratum_retains_first_contributing_attachment(self):
        rig = vendor_rig("a", "b")
        ref_a = _evidence(rig, "a", VENDOR, f"{CONTENT} [a]")
        ref_b = _evidence(rig, "b", VENDOR, f"{CONTENT} [b]")
        register = _install(rig, RATE_ONE)

        # both attachments: same SourceType, same band -> ONE stratum
        first = _write(
            rig,
            _fact(
                rig,
                ((ref_a, SPAN, STRONG_CONF), (ref_b, SPAN, STRONG_CONF)),
                identity=_fixed_identity(810),
            ),
        )
        record = register.for_fact(first.object_id)[0]
        assert record.source_type is SourceType.VENDOR_PUBLICATION
        assert record.confidence_band is ConfidenceBand.STRONG
        assert record.evidence_ref == ref_a  # first in attachment order
        assert record.positional_anchor == SPAN
        assert len(register.for_fact(first.object_id)) == 1  # one unit

        # the reversed Fact retains ITS first attachment: deterministic
        # per Fact, never arbitrary set/dict iteration order
        second = _write(
            rig,
            _fact(
                rig,
                ((ref_b, SPAN, STRONG_CONF), (ref_a, SPAN, STRONG_CONF)),
                identity=_fixed_identity(811),
            ),
        )
        assert register.for_fact(second.object_id)[0].evidence_ref == ref_b

        # re-dispatch is stable: dedup holds, nothing re-derived
        rig.store.audit_sampler(rig.store.get_fact(first.object_id))
        assert register.for_fact(first.object_id) == (record,)


class TestCrossProcessDeterminism:
    """selects() must decide identically in separate OS processes: the
    primitive is SHA-256 over the canonical string only -- never
    Python hash() (per-process randomized), never seeds, never
    network. Two subprocesses under DIFFERENT PYTHONHASHSEED values
    must agree with each other and with this process, decision for
    decision. [spec section 7 property list; T03.2.2 correction pass,
    review row-5 gap]"""

    def test_selection_is_identical_across_processes(self):
        root = str(Path(__file__).resolve().parents[1])
        script = (
            "import sys\n"
            f"sys.path.insert(0, {root!r})\n"
            "from oip.auditing import POLICY_V1, selects\n"
            "from oip.enums import ConfidenceBand\n"
            "from oip.source import SourceType\n"
            "facts = [f'xproc-{i}' for i in range(40)]\n"
            "strata = [(st, band) for st in SourceType"
            " for band in ConfidenceBand]\n"
            "print(','.join('1' if selects(f, st, b, POLICY_V1) else '0'\n"
            "              for f in facts for (st, b) in strata))\n"
        )
        results = []
        for seed in ("0", "12345"):
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=60,
                env={**os.environ, "PYTHONHASHSEED": seed},
            )
            assert proc.returncode == 0, proc.stderr
            results.append(proc.stdout.strip())

        facts = [f"xproc-{i}" for i in range(40)]
        strata = [
            (st, band) for st in SourceType for band in ConfidenceBand
        ]
        expected = ",".join(
            "1" if selects(f, st, b, POLICY_V1) else "0"
            for f in facts for (st, b) in strata
        )
        # three processes (two under different hash seeds), one answer
        assert results[0] == results[1] == expected
        # a real, non-degenerate population: the 5 percent rate picks
        # some of the 1600 draws but never all or none
        assert 0 < expected.count("1") < len(expected)


# ---------------------------------------------------------------------------
# Contract guards on the pure primitives and record invariants
# ---------------------------------------------------------------------------


class TestPrimitiveGuards:
    """Fail-closed validation of the selection primitive and the
    immutable records -- every guard line is a tested line."""

    def test_selects_rejects_malformed_inputs(self):
        with pytest.raises(AuditError):
            selects("   ", *VENDOR_STRONG, POLICY_V1)  # empty fact id
        with pytest.raises(AuditError):
            selects(123, *VENDOR_STRONG, POLICY_V1)  # type: ignore[arg-type]
        with pytest.raises(AuditError):
            selects("f", "VENDOR_PUBLICATION", ConfidenceBand.STRONG, POLICY_V1)  # type: ignore[arg-type]
        with pytest.raises(AuditError):
            selects("f", SourceType.VENDOR_PUBLICATION, "STRONG", POLICY_V1)  # type: ignore[arg-type]
        with pytest.raises(AuditError):
            selects("f", *VENDOR_STRONG, None)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"version": 0, "rate": 0.05, "salt": "s", "recorded_at": POLICY_RECORDED},
            {"version": True, "rate": 0.05, "salt": "s", "recorded_at": POLICY_RECORDED},
            {"version": "1", "rate": 0.05, "salt": "s", "recorded_at": POLICY_RECORDED},
            {"version": 1, "rate": 1.5, "salt": "s", "recorded_at": POLICY_RECORDED},
            {"version": 1, "rate": -0.1, "salt": "s", "recorded_at": POLICY_RECORDED},
            {"version": 1, "rate": "0.05", "salt": "s", "recorded_at": POLICY_RECORDED},
            {"version": 1, "rate": 0.05, "salt": "  ", "recorded_at": POLICY_RECORDED},
            {"version": 1, "rate": 0.05, "salt": "s", "recorded_at": None},
        ],
    )
    def test_policy_invariants(self, kwargs):
        with pytest.raises(SamplingPolicyError):
            SamplingPolicy(**kwargs)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"fact_object_id": ""},
            {"evidence_ref": " "},
            {"positional_anchor": None},
            {"source_type": "VENDOR_PUBLICATION"},
            {"confidence_band": "STRONG"},
            {"policy_version": 0},
            {"policy_version": "1"},
            {"selected_at": None},
        ],
    )
    def test_record_invariants(self, overrides):
        with pytest.raises(AuditRecordError):
            AuditRecord(**_record_kwargs(**overrides))

    def test_record_judged_state_requires_full_metadata(self):
        with pytest.raises(AuditRecordError):
            AuditRecord(
                **_record_kwargs(
                    judgement=AuditJudgement.FAITHFUL,
                    judged_at=None,
                    auditor=AUDITOR,
                )
            )
        with pytest.raises(AuditRecordError):
            AuditRecord(
                **_record_kwargs(
                    judgement=AuditJudgement.FAITHFUL,
                    judged_at=JUDGED_AT,
                    auditor=" ",
                )
            )

    def test_record_rejects_boolean_policy_version(self):
        """[T03.2.2 correction pass, review F8] bool is an int subclass:
        True would otherwise pass as policy_version 1. AuditRecord now
        rejects boolean versions exactly as SamplingPolicy does --
        fail-closed and consistent."""
        with pytest.raises(AuditRecordError):
            AuditRecord(**_record_kwargs(policy_version=True))
        # the aligned guard still accepts legitimate integer versions
        assert AuditRecord(**_record_kwargs()).policy_version == 1

    def test_register_select_rejects_malformed_records(self):
        register = AuditRegister()
        with pytest.raises(AuditRecordError):
            register.select("not-a-record")  # type: ignore[arg-type]
        pre_judged = AuditRecord(
            **_record_kwargs(
                judgement=AuditJudgement.DRIFTED,
                judged_at=JUDGED_AT,
                auditor=AUDITOR,
            )
        )
        with pytest.raises(AuditRecordError):
            register.select(pre_judged)  # never receives pre-judged units

    def test_register_record_failure_rejects_malformed_failures(self):
        register = AuditRegister()
        with pytest.raises(AuditError):
            register.record_failure("oops")  # type: ignore[arg-type]

    def test_judge_pending_requires_auditor_identity(self):
        with pytest.raises(AuditError):
            judge_pending(
                KnowledgeStore(),
                AuditRegister(),
                FixtureAuditor(AuditJudgement.FAITHFUL),
                auditor="  ",
            )

    def test_judge_pending_refuses_a_vanished_fact(self):
        register = AuditRegister()
        register.select(AuditRecord(**_record_kwargs(fact_object_id="ghost")))
        with pytest.raises(AuditError):
            judge_pending(
                _GhostStore(),
                register,
                FixtureAuditor(AuditJudgement.FAITHFUL),
                auditor=AUDITOR,
            )
        # the breach left the unit pending
        assert register.pending()[0].fact_object_id == "ghost"

    def test_sampler_rejects_non_fact_dispatch(self):
        """The hook contract is Fact-only; anything else is recorded as
        a sampling failure, never raised into the write path."""
        rig = vendor_rig("src")
        _evidence(rig, "src", VENDOR, CONTENT)
        register = _install(rig, RATE_ONE)
        rig.store.audit_sampler("not-a-fact")
        failures = register.selection_failures()
        assert len(failures) == 1
        assert failures[0].fact_object_id == "<unknown>"
        assert len(register) == 0

    def test_judgement_provider_protocol_is_structural(self):
        """Any object with judge(context) -> AuditJudgement satisfies
        the contract: the platform imposes no inheritance. Structural
        conformance only -- the protocol is not runtime_checkable,
        matching the repo's existing protocol style."""
        provider = FixtureAuditor(AuditJudgement.FAITHFUL)
        assert callable(provider.judge)
        context = AuditContext(
            fact=_ghost_fact(),
            evidence=None,
            evidence_ref="e",
            positional_anchor="a",
            span=None,
            source_type=SourceType.VENDOR_PUBLICATION,
            confidence_band=ConfidenceBand.STRONG,
            policy_version=1,
        )
        assert provider.judge(context) is AuditJudgement.FAITHFUL


# ---------------------------------------------------------------------------
# T03.2.3 -- Layer-3 quality metrics [F-A2; T03.2.3-specification
# section 18, rows 1-24]. Row 21 (all 60 T03.2.2 tests green and
# unmodified) is verified by this suite itself; row 22 is additionally
# pinned by source inspection below.
# ---------------------------------------------------------------------------

UTC = timezone.utc

_T3_DAY_10 = datetime(2026, 9, 10, 8, 0, tzinfo=UTC)
_T3_DAY_11_EARLY = datetime(2026, 9, 11, 10, 0, tzinfo=UTC)
_T3_DAY_11_LATE = datetime(2026, 9, 11, 23, 59, 59, 999999, tzinfo=UTC)
_T3_DAY_12_MIDNIGHT = datetime(2026, 9, 12, 0, 0, 0, tzinfo=UTC)
_T3_DAY_12_NOON = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)
_T3_DAY_14 = datetime(2026, 9, 14, 8, 0, tzinfo=UTC)


def _metric_entries():
    """Eight judged entries spanning two policy versions, two UTC days
    and all three judgements (the T03.2.3 matrix population)."""
    return [
        ("mf-0", 1, AuditJudgement.UNSUPPORTED, _T3_DAY_11_EARLY),
        ("mf-1", 1, AuditJudgement.DRIFTED, _T3_DAY_11_EARLY),
        ("mf-2", 1, AuditJudgement.FAITHFUL, _T3_DAY_11_EARLY),
        ("mf-3", 1, AuditJudgement.UNSUPPORTED, _T3_DAY_12_NOON),
        ("mf-4", 2, AuditJudgement.FAITHFUL, _T3_DAY_11_EARLY),
        ("mf-5", 2, AuditJudgement.DRIFTED, _T3_DAY_12_NOON),
        ("mf-6", 2, AuditJudgement.FAITHFUL, _T3_DAY_12_NOON),
        ("mf-7", 2, AuditJudgement.UNSUPPORTED, _T3_DAY_12_NOON),
    ]


def _judged_register(entries):
    """A register holding exactly the given judged entries, built the
    way the audit protocol itself builds one: select, then complete."""
    register = AuditRegister()
    for fact_id, version, judgement, judged_at in entries:
        register.select(
            AuditRecord(
                **_record_kwargs(
                    fact_object_id=fact_id, policy_version=version
                )
            )
        )
        register.record_judgement(
            fact_id,
            version,
            judgement,
            auditor=AUDITOR,
            judged_at=judged_at,
        )
    return register


def _selection_failure(fact_id, version=1):
    return SelectionFailure(
        fact_object_id=fact_id,
        policy_version=version,
        detail="fixture selection failure",
        occurred_at=_T3_DAY_12_NOON,
    )


class TestMetricSnapshot:
    """Rows 1-3, 6: the snapshot exists, is exact, and partitions."""

    def test_row_1_empty_register_snapshot_exists_with_none_rates(self):
        """AC2/OD-2: an empty register publishes an honest snapshot --
        judged 0 and BOTH rates None, never 0.0."""
        snap = quality_metrics(AuditRegister())
        assert snap.policy_version is None
        assert snap.judged == 0
        assert (snap.faithful, snap.drifted, snap.unsupported) == (0, 0, 0)
        assert snap.pending == 0 and snap.selection_failures == 0
        assert snap.hallucination_rate is None
        assert snap.drift_rate is None

    def test_row_2_mixed_judgements_exact_fractions(self):
        """AC1/OD-1: hallucination = unsupported/judged and drift =
        drifted/judged, exactly, over the judged set."""
        snap = quality_metrics(_judged_register(_metric_entries()))
        assert snap.judged == 8
        assert (snap.unsupported, snap.drifted, snap.faithful) == (3, 2, 3)
        assert snap.hallucination_rate == 3 / 8
        assert snap.drift_rate == 2 / 8

    def test_row_3_faithful_counts_in_denominator_only(self):
        """OD-1/R7: the closed three-value set partitions the judged
        records; FAITHFUL widens the denominator, never a numerator."""
        register = _judged_register(_metric_entries())
        snap = quality_metrics(register)
        assert snap.faithful + snap.drifted + snap.unsupported == snap.judged
        v1 = quality_metrics(register, policy_version=1)
        assert v1.judged == 4  # u2 + d1 + f1
        assert v1.hallucination_rate == 2 / 4
        assert v1.drift_rate == 1 / 4

    def test_row_6_rates_sum_to_at_most_one_faithful_recoverable(self):
        snap = quality_metrics(_judged_register(_metric_entries()))
        assert snap.hallucination_rate + snap.drift_rate <= 1.0
        assert (
            1.0 - snap.hallucination_rate - snap.drift_rate
            == pytest.approx(snap.faithful / snap.judged)
        )


class TestMetricExclusions:
    """Rows 4-5: pending and SelectionFailure are context, never rates."""

    def test_row_4_pending_excluded_and_counted(self):
        register = AuditRegister()
        for i in range(3):
            register.select(
                AuditRecord(**_record_kwargs(fact_object_id=f"mp-{i}"))
            )
        register.record_judgement(
            "mp-0", 1, AuditJudgement.UNSUPPORTED,
            auditor=AUDITOR, judged_at=_T3_DAY_11_EARLY,
        )
        register.record_judgement(
            "mp-1", 1, AuditJudgement.FAITHFUL,
            auditor=AUDITOR, judged_at=_T3_DAY_11_EARLY,
        )
        snap = quality_metrics(register)  # mp-2 stays pending
        assert snap.judged == 2 and snap.pending == 1
        assert snap.hallucination_rate == 1 / 2
        assert snap.drift_rate == 0.0

    def test_row_4b_pending_only_register_is_none_not_zero(self):
        register = AuditRegister()
        for i in range(4):
            register.select(
                AuditRecord(**_record_kwargs(fact_object_id=f"po-{i}"))
            )
        snap = quality_metrics(register)
        assert snap.judged == 0 and snap.pending == 4
        assert snap.hallucination_rate is None
        assert snap.drift_rate is None

    def test_row_5_selection_failures_excluded_and_counted(self):
        register = _judged_register(_metric_entries()[:2])  # u1 + d1
        register.record_failure(_selection_failure("x-0"))
        register.record_failure(_selection_failure("x-1", version=2))
        snap = quality_metrics(register)
        assert snap.judged == 2
        assert snap.hallucination_rate == 1 / 2
        assert snap.drift_rate == 1 / 2
        assert snap.selection_failures == 2
        v2 = quality_metrics(register, policy_version=2)
        assert v2.judged == 0 and v2.hallucination_rate is None
        assert v2.selection_failures == 1  # context is scope-filtered

    def test_row_5b_failures_only_register_is_none_not_zero(self):
        register = AuditRegister()
        register.record_failure(_selection_failure("x-0"))
        snap = quality_metrics(register)
        assert snap.judged == 0 and snap.selection_failures == 1
        assert snap.hallucination_rate is None
        assert snap.drift_rate is None


class TestMetricSnapshotValidation:
    """Row 7 (+ invalid inputs): fail-closed construction and scope."""

    def _kwargs(self, **overrides):
        kwargs = dict(
            policy_version=None, judged=4, faithful=2, drifted=1,
            unsupported=1, pending=0, selection_failures=0,
            hallucination_rate=0.25, drift_rate=0.25,
        )
        kwargs.update(overrides)
        return kwargs

    def test_row_7_rate_with_zero_judged_unrepresentable(self):
        with pytest.raises(AuditError):
            QualityMetricSnapshot(
                **self._kwargs(
                    judged=0, faithful=0, drifted=0, unsupported=0,
                    hallucination_rate=0.0,
                )
            )

    def test_row_7_inconsistent_counts_rejected(self):
        with pytest.raises(AuditError):  # 3 + 1 + 1 != 4
            QualityMetricSnapshot(**self._kwargs(faithful=3))
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(judged=5))

    def test_row_7_none_rate_with_judged_rejected(self):
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(hallucination_rate=None))
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(drift_rate=None))

    def test_row_7_out_of_range_and_bool_counts_rejected(self):
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(hallucination_rate=1.5))
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(drift_rate=True))
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(judged=True))
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(pending=-1))

    def test_row_7_scope_validation_fail_closed(self):
        for bad in (True, 0, -1, 1.5, "1"):
            with pytest.raises(AuditError):
                quality_metrics(AuditRegister(), policy_version=bad)
            with pytest.raises(AuditError):
                metric_trend(AuditRegister(), policy_version=bad)
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(policy_version=True))
        with pytest.raises(AuditError):
            QualityMetricSnapshot(**self._kwargs(policy_version=0))

    def test_row_7_valid_constructions_accepted(self):
        snap = QualityMetricSnapshot(**self._kwargs())
        assert snap.hallucination_rate == 0.25
        zero = QualityMetricSnapshot(
            policy_version=None, judged=0, faithful=0, drifted=0,
            unsupported=0, pending=2, selection_failures=1,
            hallucination_rate=None, drift_rate=None,
        )
        assert zero.hallucination_rate is None
        assert zero.pending == 2


class TestMetricScopes:
    """Rows 8-10, 19: dual scopes, disjoint union, dedup, rate-free."""

    def test_row_8_per_version_scope_and_empty_scope(self):
        register = _judged_register(_metric_entries())
        v1 = quality_metrics(register, policy_version=1)
        v2 = quality_metrics(register, policy_version=2)
        assert v1.policy_version == 1 and v1.judged == 4
        assert v1.hallucination_rate == 2 / 4 and v1.drift_rate == 1 / 4
        assert v2.policy_version == 2 and v2.judged == 4
        assert v2.hallucination_rate == 1 / 4 and v2.drift_rate == 1 / 4
        empty = quality_metrics(register, policy_version=7)
        assert empty.policy_version == 7
        assert empty.judged == 0 and empty.hallucination_rate is None

    def test_row_9_global_is_disjoint_union_no_collapsing(self):
        register = _judged_register(_metric_entries())
        g = quality_metrics(register)
        v1 = quality_metrics(register, policy_version=1)
        v2 = quality_metrics(register, policy_version=2)
        for field in (
            "judged", "faithful", "drifted", "unsupported",
            "pending", "selection_failures",
        ):
            assert getattr(g, field) == getattr(v1, field) + getattr(
                v2, field
            )
        # a Fact audited again under a newer version is a NEW audit:
        # two records, no winning-audit rule, no collapsing
        register.select(
            AuditRecord(
                **_record_kwargs(fact_object_id="mf-0", policy_version=2)
            )
        )
        register.record_judgement(
            "mf-0", 2, AuditJudgement.FAITHFUL,
            auditor=AUDITOR, judged_at=_T3_DAY_12_NOON,
        )
        assert len(register.for_fact("mf-0")) == 2
        g2 = quality_metrics(register)
        assert g2.judged == 9  # both audits counted exactly once

    def test_row_10_dedup_and_recomputation_idempotence(self):
        register = _judged_register(_metric_entries())
        with pytest.raises(DuplicateSelectionError):
            register.select(
                AuditRecord(
                    **_record_kwargs(fact_object_id="mf-0", policy_version=1)
                )
            )
        assert len(register) == 8  # duplicates create no records
        assert quality_metrics(register) == quality_metrics(register)
        assert metric_trend(register) == metric_trend(register)

    def test_row_19_no_configured_rate_contamination(self):
        """The configured sampling rate never enters a metric: two
        regimes differing ONLY in rate/salt, holding the same judgement
        outcomes, publish the same rates."""
        assert POLICY_V1.rate == 0.05
        rate_one_regime = SamplingPolicy(
            version=2, rate=1.0, salt="t3-regime", recorded_at=POLICY_RECORDED
        )
        assert rate_one_regime.rate != POLICY_V1.rate
        same_mix = [
            ("sm-0", 1, AuditJudgement.UNSUPPORTED, _T3_DAY_11_EARLY),
            ("sm-1", 1, AuditJudgement.UNSUPPORTED, _T3_DAY_11_EARLY),
            ("sm-2", 1, AuditJudgement.FAITHFUL, _T3_DAY_11_EARLY),
        ]
        under_v1 = _judged_register(same_mix)
        under_v2 = _judged_register(
            [(f, 2, j, t) for f, _, j, t in same_mix]
        )
        a = quality_metrics(under_v1, policy_version=1)
        b = quality_metrics(under_v2, policy_version=2)
        assert a.hallucination_rate == b.hallucination_rate == 2 / 3
        assert a.drift_rate == b.drift_rate == 0.0
        # the trend data is identical too (each point's snapshot still
        # honestly records ITS OWN scope -- the policy_version field)
        trend_a = metric_trend(under_v1, policy_version=1)
        trend_b = metric_trend(under_v2, policy_version=2)
        assert [p.utc_date for p in trend_a] == [p.utc_date for p in trend_b]
        for pa, pb in zip(trend_a, trend_b):
            for field in (
                "judged", "faithful", "drifted", "unsupported",
                "hallucination_rate", "drift_rate",
            ):
                assert getattr(pa.snapshot, field) == getattr(
                    pb.snapshot, field
                )
            assert pa.snapshot.policy_version == 1
            assert pb.snapshot.policy_version == 2


class TestMetricDeterminismAndPurity:
    """Rows 11-12, 23-24: determinism, purity, concurrency, no gating."""

    @given(st.permutations(_metric_entries()))
    def test_row_11_insertion_order_independence(self, perm):
        entries = _metric_entries()
        reference = _judged_register(entries)
        shuffled = _judged_register(list(perm))
        assert quality_metrics(shuffled) == quality_metrics(reference)
        assert metric_trend(shuffled) == metric_trend(reference)

    def test_row_12_computation_mutates_nothing(self):
        register = _judged_register(_metric_entries())
        register.record_failure(_selection_failure("x-0"))
        before_records = register.snapshot()
        before_pending = register.pending()
        before_failures = register.selection_failures()
        snap = quality_metrics(register)
        trend = metric_trend(register)
        assert snap.judged == 8 and len(trend) == 2
        assert register.snapshot() == before_records
        assert register.pending() == before_pending
        assert register.selection_failures() == before_failures
        assert len(register) == 8

    def test_row_23_metric_reads_race_free_under_concurrent_judgements(self):
        register = AuditRegister()
        n = 8
        for i in range(n):
            register.select(
                AuditRecord(**_record_kwargs(fact_object_id=f"mc-{i}"))
            )
        errors: list = []
        barrier = threading.Barrier(n + 4)

        def completer(i: int) -> None:
            try:
                barrier.wait(timeout=30)
                register.record_judgement(
                    f"mc-{i}", 1,
                    AuditJudgement.UNSUPPORTED
                    if i % 2 == 0
                    else AuditJudgement.FAITHFUL,
                    auditor=AUDITOR, judged_at=_T3_DAY_12_NOON,
                )
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        def reader() -> None:
            try:
                barrier.wait(timeout=30)
                for _ in range(200):
                    snap = quality_metrics(register)
                    trend = metric_trend(register)
                    # every observed state is internally consistent
                    assert (
                        snap.judged
                        == snap.faithful + snap.drifted + snap.unsupported
                    )
                    assert len(trend) <= 1  # single fixture day
                    for point in trend:
                        assert point.snapshot.judged >= 1
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=completer, args=(i,)) for i in range(n)
        ]
        threads += [threading.Thread(target=reader) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        assert not any(t.is_alive() for t in threads)
        assert errors == []
        snap = quality_metrics(register)
        assert snap.judged == 8
        assert snap.unsupported == 4 and snap.faithful == 4
        assert snap.hallucination_rate == 0.5
        assert len(metric_trend(register)) == 1

    def test_row_24_no_gating_no_mutation_from_metric_computation(self):
        rig = vendor_rig("a")
        register = _install(rig, RATE_ONE)
        ref = _evidence(rig, "a", VENDOR, CONTENT)
        stored = _write(
            rig,
            _fact(
                rig, ((ref, SPAN, STRONG_CONF),),
                identity=_fixed_identity(950),
            ),
        )
        fact_before = rig.store.get_fact(stored.object_id)
        assert register.has_selection(stored.object_id, RATE_ONE.version)
        register.record_judgement(
            stored.object_id, RATE_ONE.version, AuditJudgement.UNSUPPORTED,
            auditor=AUDITOR, judged_at=_T3_DAY_12_NOON,
        )
        records_before = register.snapshot()
        snap = quality_metrics(register)
        trend = metric_trend(register)
        # an UNSUPPORTED judgement gates nothing, and computing the
        # published metrics mutates neither the store nor the register
        assert snap.unsupported == 1 and snap.hallucination_rate == 1.0
        assert len(trend) == 1
        assert rig.store.get_fact(stored.object_id) == fact_before
        assert register.snapshot() == records_before


class TestMetricTrend:
    """Rows 14-18: judged_at UTC-day sparse series."""

    def test_row_14_bucketing_and_utc_midnight_boundary(self):
        entries = [
            ("tb-0", 1, AuditJudgement.UNSUPPORTED, _T3_DAY_11_LATE),
            ("tb-1", 1, AuditJudgement.DRIFTED, _T3_DAY_12_MIDNIGHT),
            ("tb-2", 1, AuditJudgement.FAITHFUL, _T3_DAY_12_NOON),
        ]
        trend = metric_trend(_judged_register(entries))
        assert [p.utc_date for p in trend] == [
            date(2026, 9, 11), date(2026, 9, 12),
        ]
        assert trend[0].snapshot.judged == 1
        assert trend[1].snapshot.judged == 2  # midnight + noon: one day

    def test_row_14b_non_utc_offsets_normalize_to_utc(self):
        entries = [
            # 01:30 at +02:00 == 23:30 UTC on the PREVIOUS calendar day
            ("tz-0", 1, AuditJudgement.UNSUPPORTED,
             datetime(2026, 9, 12, 1, 30,
                      tzinfo=timezone(timedelta(hours=2)))),
            ("tz-1", 1, AuditJudgement.FAITHFUL, _T3_DAY_12_MIDNIGHT),
        ]
        trend = metric_trend(_judged_register(entries))
        assert [p.utc_date for p in trend] == [
            date(2026, 9, 11), date(2026, 9, 12),
        ]

    def test_row_15_naive_judged_at_is_read_as_utc(self):
        entries = [
            ("nv-0", 1, AuditJudgement.UNSUPPORTED,
             datetime(2026, 9, 13, 0, 30)),  # naive
            ("nv-1", 1, AuditJudgement.FAITHFUL,
             datetime(2026, 9, 13, 0, 30, tzinfo=UTC)),
        ]
        trend = metric_trend(_judged_register(entries))
        # the naive stamp lands with its explicit-UTC twin: exactly the
        # deterministic no-local-time rule [N-4]
        assert [p.utc_date for p in trend] == [date(2026, 9, 13)]
        assert trend[0].snapshot.judged == 2

    def test_row_16_sparse_ascending_no_empty_buckets(self):
        entries = [
            ("sp-0", 1, AuditJudgement.UNSUPPORTED, _T3_DAY_14),
            ("sp-1", 1, AuditJudgement.DRIFTED, _T3_DAY_10),
            ("sp-2", 1, AuditJudgement.FAITHFUL, _T3_DAY_11_EARLY),
        ]
        trend = metric_trend(_judged_register(entries))
        assert [p.utc_date for p in trend] == [
            date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 14),
        ]  # the 09-12/09-13 gap manufactures no bucket, no 0% rate
        pending_only = AuditRegister()
        for i in range(3):
            pending_only.select(
                AuditRecord(**_record_kwargs(fact_object_id=f"pp-{i}"))
            )
        assert metric_trend(pending_only) == ()
        assert metric_trend(AuditRegister()) == ()

    def test_row_17_buckets_sum_to_cumulative_snapshot(self):
        register = _judged_register(_metric_entries())
        for scope in (None, 1, 2):
            snap = quality_metrics(register, policy_version=scope)
            trend = metric_trend(register, policy_version=scope)
            for field in ("judged", "faithful", "drifted", "unsupported"):
                assert sum(
                    getattr(p.snapshot, field) for p in trend
                ) == getattr(snap, field)
            for point in trend:
                # buckets derive ONLY from judgement records: pending
                # selections (no judged_at) and N-10 failures (not
                # judgement records) contribute no bucket context
                assert point.snapshot.pending == 0
                assert point.snapshot.selection_failures == 0

    def test_row_18_per_version_trend_and_global_spans_regimes(self):
        register = _judged_register(_metric_entries())
        v1 = metric_trend(register, policy_version=1)
        v2 = metric_trend(register, policy_version=2)
        assert [p.utc_date for p in v1] == [date(2026, 9, 11), date(2026, 9, 12)]
        assert [p.snapshot.judged for p in v1] == [3, 1]
        assert v1[0].snapshot.policy_version == 1
        assert [p.utc_date for p in v2] == [date(2026, 9, 11), date(2026, 9, 12)]
        assert [p.snapshot.judged for p in v2] == [1, 3]
        global_trend = metric_trend(register)
        # the global trend spans both policy regimes, bucketed by day
        assert [p.utc_date for p in global_trend] == [
            date(2026, 9, 11), date(2026, 9, 12),
        ]
        assert [p.snapshot.judged for p in global_trend] == [4, 4]
        assert global_trend[0].snapshot.policy_version is None


class TestMetricSurfaceAndBoundaries:
    """Rows 13, 20, 22: frozen surface, register untouched, pins."""

    def test_row_13_frozen_value_types_no_iom_leak(self):
        register = _judged_register(_metric_entries())
        snap = quality_metrics(register)
        trend = metric_trend(register)
        with pytest.raises(FrozenInstanceError):
            snap.hallucination_rate = 0.0  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            trend[0].utc_date = date(2020, 1, 1)  # type: ignore[misc]
        assert {f.name for f in fields(QualityMetricSnapshot)} == {
            "policy_version", "judged", "faithful", "drifted",
            "unsupported", "pending", "selection_failures",
            "hallucination_rate", "drift_rate",
        }
        assert {f.name for f in fields(MetricTrendPoint)} == {
            "utc_date", "snapshot",
        }
        # no Intelligence Object type leaks into the metric surface
        assert type(snap).__module__ == "oip.auditing"
        for value in (
            snap.policy_version, snap.judged, snap.faithful, snap.drifted,
            snap.unsupported, snap.pending, snap.selection_failures,
            snap.hallucination_rate, snap.drift_rate, trend[0].utc_date,
        ):
            assert value is None or isinstance(value, (int, float, date))

    def test_row_20_register_surface_unchanged_layer1_rate_distinct(self):
        # Layer 3 lives beside the register, never on it
        assert not hasattr(AuditRegister, "quality_metrics")
        assert not hasattr(AuditRegister, "metric_trend")
        # Layer 1's rate is a DIFFERENT measurement and stays untouched
        from oip.semantic import AnchorVerifier

        rate = AnchorVerifier.anchor_failure_rate
        assert isinstance(rate, property)
        assert "NOT the hallucination rate" in (rate.__doc__ or "")

    def test_row_22_import_set_and_module_count_unchanged(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "oip" / "auditing.py").read_text())
        oip_imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("oip.")
        }
        assert oip_imports == {
            "oip.enums", "oip.evidence", "oip.fact", "oip.source",
        }
        assert len(list((root / "oip").glob("*.py"))) == 39  # +1 inference (T04.1.1)
