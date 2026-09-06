"""Contract tests for T03.2.1 -- anchor verification at acceptance [F-V6].

Task: T03.2.1

Architecture References:
- S-5    Layer 1 at acceptance: the ratified AnchorVerifier, installed on
         the store's existing slot; no new verification system is built.
- F-V6   Claim present in the referenced Evidence at the stated anchor.
- N-08   The acceptance path is the authority: every Fact write passes.
- N-15   REFERENCE-mode Evidence is not verifiable in place: fail closed.
- N-10   A refused write is an ordinary recorded failure, never a crash.
- N-11   Installation is an atomic reference bind read under the store
         lock; a write sees one consistent verifier for its whole evaluation.
- N-4    The provider is pure in the stored bytes: replay reproduces verdicts.
- M-67   Installation measures fabricated LOCATION, never paraphrase drift;
         the installed state must keep saying so.

T03.2.1 acceptance criteria under test:
  AC1  Claim locatable at stated anchor                        -> IMPLEMENTED
  AC2  Fabricated anchors rejected                             -> IMPLEMENTED
  AC3  Runs on 100 percent of Facts                            -> IMPLEMENTED

Regression guard (P1-pinned): an unconfigured store keeps F-V6 SKIP
semantics -- installation is opt-in composition, never a constructor change.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.anchoring import (
    evidence_span_provider,
    install_anchor_verification,
    store_span_provider,
)
from oip.claim import Claim
from oip.evidence import Evidence, EvidenceContent, StorageMode
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


def wired_rig(identifiers=("src-a", "src-z")):
    """The ratified acquisition+extraction rig, with T03.2.1 installed."""
    rig = make_rig({name: VENDOR for name in identifiers})
    ref = rig.acquire("src-a", VENDOR, CHANGES)
    verifier = install_anchor_verification(rig.store)
    return rig, ref, verifier


# ---------------------------------------------------------------------------
# Installation contract (opt-in, non-clobbering, explicit replace)
# ---------------------------------------------------------------------------


class TestInstallation:
    def test_default_store_is_unconfigured(self):
        # P1-pinned regression guard, re-asserted at the T03.2.1 boundary
        assert KnowledgeStore().anchor_verifier is None

    def test_install_binds_the_ratified_verifier(self):
        store = KnowledgeStore()
        verifier = install_anchor_verification(store)
        assert store.anchor_verifier is verifier
        assert verifier.span_provider is not None
        assert verifier.claims_of is not None
        assert verifier.covers_paraphrase_drift is False  # M-67, loud

    def test_double_install_refuses_clobbering(self):
        store = KnowledgeStore()
        first = install_anchor_verification(store)
        with pytest.raises(AnchoringError):
            install_anchor_verification(store)
        assert store.anchor_verifier is first  # refusal keeps the original

    def test_replace_true_swaps_explicitly(self):
        store = KnowledgeStore()
        install_anchor_verification(store)
        second = install_anchor_verification(store, replace=True)
        assert store.anchor_verifier is second

    def test_injected_overrides_are_honoured(self):
        store = KnowledgeStore()
        seen: list[str] = []
        provider = evidence_span_provider(CHANGES)

        def logging_provider(anchor):
            seen.append(anchor.evidence_id)
            return provider(anchor)

        verifier = install_anchor_verification(
            store, span_provider=logging_provider, claims_of=lambda ctx: ()
        )
        assert verifier.span_provider is logging_provider
        assert seen == []  # nothing consulted the injection yet


# ---------------------------------------------------------------------------
# The store-wide provider
# ---------------------------------------------------------------------------


class TestStoreSpanProvider:
    def test_resolves_locator_from_stored_full_content(self):
        rig, ref, _ = wired_rig()
        provider = store_span_provider(rig.store)
        anchor = SimpleNamespace(evidence_id=ref, locator=locate(CHANGES, SPAN))
        assert provider(anchor) == SPAN

    def test_resolves_verbatim_span_convention(self):
        rig, ref, _ = wired_rig()
        provider = store_span_provider(rig.store)
        anchor = SimpleNamespace(evidence_id=ref, locator=SPAN)
        assert provider(anchor) == SPAN

    def test_dangling_evidence_ref_resolves_to_nothing(self):
        provider = store_span_provider(KnowledgeStore())
        anchor = SimpleNamespace(evidence_id="EV-nope", locator="chars 0-4")
        assert provider(anchor) is None

    def test_reference_mode_resolves_to_nothing(self):
        # N-15: REFERENCE Evidence stores no material; presence at the
        # anchor CANNOT be demonstrated, so the provider answers None.
        from oip.enums import Engine, ObjectType

        store = KnowledgeStore()
        attrs = build_attrs(
            IdentityAllocator().new_object(), ObjectType.EVIDENCE,
            engine=Engine.RESEARCH,
        )
        content = EvidenceContent(
            fingerprint="sha256:external-reference",
            storage_mode=StorageMode.REFERENCE,
            content=None,
            content_reference="archive://doc-99",
        )
        from oip.evidence import Provenance

        evidence = Evidence(
            attributes=attrs,
            provenance=Provenance(
                source_identifier="src-ref", source_type=VENDOR,
                acquisition_method="test retrieval", acquired_at=T0,
                access_conditions="reference only",
                capture_fidelity="reference only; bytes not retained",
            ),
            content=content,
        )
        store.write_evidence(evidence)
        provider = store_span_provider(store)
        anchor = SimpleNamespace(evidence_id=attrs.object_id,
                                 locator="chars 0-4")
        assert provider(anchor) is None

    def test_reference_mode_holding_content_is_still_unverifiable(self):
        # the mode governs, not the field: a REFERENCE payload that happens
        # to carry text is STILL not verifiable in place [N-15]. The
        # ratified is_verifiable_in_place predicate is the single authority.
        from oip.enums import Engine, ObjectType

        store = KnowledgeStore()
        attrs = build_attrs(
            IdentityAllocator().new_object(), ObjectType.EVIDENCE,
            engine=Engine.RESEARCH,
        )
        content = EvidenceContent(
            fingerprint="sha256:whatever",
            storage_mode=StorageMode.REFERENCE,
            content=CHANGES,  # retained by accident of construction
            content_reference="archive://doc-77",
        )
        from oip.evidence import Provenance

        store.write_evidence(Evidence(
            attributes=attrs,
            provenance=Provenance(
                source_identifier="src-ref2", source_type=VENDOR,
                acquisition_method="test retrieval", acquired_at=T0,
                access_conditions="reference",
                capture_fidelity="reference retained text",
            ),
            content=content,
        ))
        provider = store_span_provider(store)
        anchor = SimpleNamespace(evidence_id=attrs.object_id,
                                 locator=locate(CHANGES, SPAN))
        assert provider(anchor) is None


# ---------------------------------------------------------------------------
# AC1 + AC3: every accepted Fact write is verified, end to end
# ---------------------------------------------------------------------------


class TestAC1AC3VerificationRuns:
    def test_engine_extraction_passes_installed_verification(self):
        rig, ref, verifier = wired_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        from oip.enums import ObjectStatus

        fact = rig.store.get_fact(outcome.object_id)
        assert fact is not None
        assert fact.attributes.status is ObjectStatus.ACTIVE
        assert verifier.checked == len(fact.attachments) == 1
        assert verifier.failed == 0

    def test_checked_count_equals_attachments_of_every_accepted_write(self):
        # AC3: 100% of Facts -- and of their attachments; every write path
        # (fresh Fact AND merge re-version) is counted, none sampled.
        rig, ref, verifier = wired_rig()
        r2 = rig.acquire("src-z", VENDOR,
                         f"Restatement: {SPAN}.")
        o1 = extract(rig.extraction(evidence_ref=ref),
                     store=rig.store, log=rig.log, clock=lambda: TICK)
        expect = len(rig.store.get_fact(o1.object_id).attachments)
        o2 = extract(rig.extraction(evidence_ref=r2),
                     store=rig.store, log=rig.log,
                     clock=lambda: TICK + timedelta(minutes=1))
        expect += len(rig.store.get_fact(o2.object_id).attachments)
        assert verifier.checked == expect == 3  # 1 on v1, 2 on the merge v2
        assert verifier.failed == 0

    def test_merge_reversion_reverifies_the_predecessor_attachment(self):
        # the merged version carries BOTH attachments through F-V6 against
        # live store content -- the old anchor must still resolve.
        rig, ref, verifier = wired_rig()
        r2 = rig.acquire("src-z", VENDOR, f"Restatement: {SPAN}.")
        extract(rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        o2 = extract(rig.extraction(evidence_ref=r2),
                     store=rig.store, log=rig.log,
                     clock=lambda: TICK + timedelta(minutes=1))
        merged = rig.store.get_fact(o2.object_id)
        assert len(merged.attachments) == 2
        ids = {a.evidence_ref for a in merged.attachments}
        assert ref in ids and r2 in ids
        assert verifier.failed == 0

    def test_uninstalled_store_still_accepts_with_skip(self):
        # default OFF: the F-V6 rule SKIPs (P1-pinned); no guessed PASS.
        rig, ref, _ = wired_rig()
        plain = make_rig({"src-a": VENDOR})
        plain_ref = plain.acquire("src-a", VENDOR, CHANGES)
        outcome = extract(plain.extraction(evidence_ref=plain_ref),
                          store=plain.store, log=plain.log,
                          clock=lambda: TICK)
        assert plain.store.get_fact(outcome.object_id) is not None

    def test_same_input_same_outcome(self):
        # N-4 determinism: two fresh rigs with the same material produce
        # identical verification outcomes.
        results = []
        for _ in range(2):
            rig, ref, verifier = wired_rig()
            extract(rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log, clock=lambda: TICK)
            results.append((verifier.checked, verifier.failed))
        assert results[0] == results[1] == (1, 0)


# ---------------------------------------------------------------------------
# AC2: fabricated anchors are refused at acceptance
# ---------------------------------------------------------------------------


def hand_written_fact(store: KnowledgeStore, evidence_ref: str, *,
                      anchor: str, allocator: IdentityAllocator) -> Fact:
    """A Fact built OUTSIDE the engine -- the attack surface AC2 governs.

    Legal at construction (V7 authority respected, F-V4 respected), so the
    only thing that can refuse it is the acceptance path -- which is exactly
    where F-V6 lives. Confidence stays under the upstream ceiling so V5
    cannot mask the F-V6 verdict under test.
    """
    from oip.enums import Engine, ObjectStatus, ObjectType

    identity = allocator.new_object()
    attributes = build_attrs(
        identity, ObjectType.FACT,
        upstream=((evidence_ref, ObjectType.EVIDENCE),),
        status=ObjectStatus.ACTIVE, status_reason="hand-written probe",
        engine=Engine.FACT_EXTRACTION,
        support=0.55, assertion=0.55, upstream_ceiling=0.55,
    )
    attachment = EvidenceAttachment(
        evidence_ref=evidence_ref,
        positional_anchor=anchor,
        extracted_at=T0,
        extraction_confidence=0.8,
    )
    claim = Claim(subject="bulk edits", predicate="silently fail above",
                  qualifier="NONE")
    return Fact(
        attributes=attributes, claim=claim, claim_type=ClaimType.ASSERTION,
        attachments=(attachment,),
        qualifying_context="hand-written for the AC2 probe",
    )


class TestAC2FabricationRefused:
    def test_out_of_bounds_locator_is_refused(self):
        rig, ref, verifier = wired_rig()
        bad = hand_written_fact(rig.store, ref, anchor="chars 900-999",
                                allocator=rig.store.allocator)
        with pytest.raises(WriteRejectedError):
            rig.store.write_fact(bad)
        assert verifier.failed == 1
        assert verifier.checked == 1

    def test_verbatim_span_not_in_content_is_refused(self):
        rig, ref, verifier = wired_rig()
        bad = hand_written_fact(
            rig.store, ref,
            anchor="this sentence was never written anywhere",
            allocator=rig.store.allocator,
        )
        with pytest.raises(WriteRejectedError):
            rig.store.write_fact(bad)
        assert verifier.failed == 1

    def test_ambiguous_verbatim_span_is_refused(self):
        # the provider's unique-occurrence rule: twice-present material
        # locates nothing, so verification cannot pass on a guess.
        rig = make_rig({"src-dup": VENDOR})
        dup = f"Note: {SPAN}. And again: {SPAN}. End."
        ref2 = rig.acquire("src-dup", VENDOR, dup)
        install_anchor_verification(rig.store)
        bad = hand_written_fact(rig.store, ref2, anchor=SPAN,
                                allocator=rig.store.allocator)
        with pytest.raises(WriteRejectedError):
            rig.store.write_fact(bad)

    def test_refused_write_leaves_no_trace(self):
        # N-6 atomicity: the payload registry gains nothing and the store's
        # failure log records the F-V6 refusal.
        rig, ref, verifier = wired_rig()
        bad = hand_written_fact(rig.store, ref, anchor="chars 900-999",
                                allocator=rig.store.allocator)
        with pytest.raises(WriteRejectedError):
            rig.store.write_fact(bad)
        assert rig.store.get_fact(bad.attributes.object_id) is None
        records = rig.store.failure_records
        assert records and "F-V6" in records[-1].rule_ids
        assert "fabricated location" in records[-1].nature[0] \
            or "absent from the span" in records[-1].nature[0]

    def test_legitimate_anchor_still_writes_after_a_refusal(self):
        # a refusal must not poison the slot: the next honest write passes
        rig, ref, verifier = wired_rig()
        bad = hand_written_fact(rig.store, ref, anchor="chars 900-999",
                                allocator=rig.store.allocator)
        with pytest.raises(WriteRejectedError):
            rig.store.write_fact(bad)
        good = hand_written_fact(rig.store, ref, anchor=SPAN,
                                allocator=rig.store.allocator)
        stored = rig.store.write_fact(good)
        assert stored.attributes.object_id == good.attributes.object_id
        assert verifier.failed == 1 and verifier.checked == 2


# ---------------------------------------------------------------------------
# Boundary: routing and non-Fact writes are untouched by installation
# ---------------------------------------------------------------------------


class TestBoundaryObservations:
    def test_non_fact_writes_are_unaffected_by_installation(self):
        rig, ref, verifier = wired_rig()
        before = verifier.checked
        rig.acquire("src-z", VENDOR, "Another document entirely.")
        assert verifier.checked == before

    def test_fv6_rule_delegates_only_for_facts(self):
        from oip.enums import ObjectType

        rig, ref, verifier = wired_rig()
        outcome = extract(rig.extraction(evidence_ref=ref),
                          store=rig.store, log=rig.log, clock=lambda: TICK)
        fact = rig.store.get_fact(outcome.object_id)
        other = build_attrs(IdentityAllocator().new_object(),
                            ObjectType.PROBLEM)
        assert fv6_anchor_verification(
            AcceptanceContext(attributes=other, lineage=None, fact=None)
        ).outcome is RuleOutcome.SKIP
        # a real fact payload with the installed verifier resolves PASS
        assert fv6_anchor_verification(
            AcceptanceContext(attributes=fact.attributes, lineage=None,
                              fact=fact, anchor_verifier=verifier)
        ).outcome is RuleOutcome.PASS
