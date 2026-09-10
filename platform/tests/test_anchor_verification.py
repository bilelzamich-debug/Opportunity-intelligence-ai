"""S-5 Layer 1 at acceptance: anchor verification on every Fact. [T03.2.1]

Architecture References:
- S-5     Layer 1: every Fact's claim must be locatable at its stated
          positional anchor -- the anchor resolves to a real span in the
          referenced Evidence and the claim's subject and predicate are
          present at that span. Runs on 100% of Facts at acceptance via
          the hook; failure blocks acceptance. Catches fabricated
          LOCATION, never paraphrase drift (M-67 open; Layer 2 is
          T03.2.2, out of scope here).
- F-V6   the acceptance rule (fact.py, in the store's default rule set)
          delegates to the store's anchor_verifier: SKIP when
          unconfigured, PASS/FAIL once install_anchor_verification
          composes the ratified AnchorVerifier over the store's own
          Evidence payloads.
- N-8    the Store enforces at PROPOSED -> ACTIVE; mechanism and policy
          are separated -- the installer is composition, not policy.
- N-10   failures are recorded, never silent.
- N-15   REFERENCE-mode material is unverifiable in place; extraction
          refuses it upstream, so unresolvable content at acceptance
          fails closed (None -> "fabricated location").
- D-04   locator discipline: ``chars <start>-<end>`` by direct slice, or
          the verbatim-span convention by exact unique occurrence.
- T03.1.3 the ratified value split: acceptance checks anchor + subject +
          predicate only; the VALUE is checked at extraction against the
          verbatim value_text the Fact does not retain.
- T03.1.4 the ACCEPTANCE_REFUSED merge refusal and its named surviving
          state; the C-1 consequence (approved): a composed Fact can
          fail F-V6 after the canonical was superseded -- loud,
          recorded, no successor, data intact.

T03.2.1 acceptance criteria under test:
  AC1  Claim locatable at stated anchor
  AC2  Fabricated anchors rejected
  AC3  Runs on 100 percent of Facts
"""

from __future__ import annotations

import pytest

from oip.anchoring import (
    evidence_span_provider,
    fact_anchor_claims,
    install_anchor_verification,
)
from oip.acceptance import AcceptanceContext
from oip.claim import Claim, Quantity, UNQUALIFIED
from oip.enums import ObjectType, ObjectStatus
from oip.evidence import EvidenceContent, compute_fingerprint
from oip.extraction import ExtractionRefusedError, ExtractionStage, extract
from oip.fact import ClaimType, EvidenceAttachment, Fact, Independence
from oip.semantic import Anchor, AnchorVerifier
from oip.store import KnowledgeStore, WriteRejectedError
from tests.conftest import T0, build_attrs
from tests.test_evidence import evidence as make_evidence
from tests.test_extraction import TICK, VENDOR, Rig, vendor_rig

CONTENT = "Q3 report: churn rate stands at 3.5 percent. Footnote follows."
SPAN = "churn rate stands at 3.5 percent"
OTHER_CONTENT = "Q3 memo: an entirely different wording sits here."
SUBJECT = "churn rate"
PREDICATE = "stands at"

GOOD_SPAN = "bulk edits silently fail above 50 SKUs"      # single space
SLOPPY_SPAN = "bulk  edits silently fail above 50 SKUs"   # double space


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _evidence(rig: Rig, source: str, content: str) -> str:
    return rig.acquire(source, VENDOR, content)


def _extract(
    rig: Rig,
    ref: str,
    *,
    anchor: str,
    subject: str = SUBJECT,
    predicate: str = PREDICATE,
    value: Quantity | None = None,
    value_text: str | None = None,
):
    return extract(
        rig.extraction(
            evidence_ref=ref,
            subject=subject,
            predicate=predicate,
            anchor=anchor,
            value=value,
            value_text=value_text,
        ),
        store=rig.store,
        log=rig.log,
        clock=lambda: TICK,
    )


def _manual_fact(
    rig: Rig,
    evidence_ref: str,
    anchor: str,
    *,
    subject: str = SUBJECT,
    predicate: str = PREDICATE,
    value: Quantity | None = None,
) -> Fact:
    """A directly-constructed Fact: acceptance, not extraction, decides."""
    evidence = rig.store.get_evidence(evidence_ref)
    ceiling = (
        evidence.attributes.confidence.effective_confidence
        if evidence is not None
        else None
    )
    identity = rig.store.allocator.new_object()
    attributes = build_attrs(
        identity,
        ObjectType.FACT,
        ((evidence_ref, ObjectType.EVIDENCE),),
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        upstream_ceiling=ceiling,
    )
    return Fact(
        attributes=attributes,
        claim=Claim(subject, predicate, UNQUALIFIED, value),
        claim_type=ClaimType.ASSERTION,
        attachments=(
            EvidenceAttachment(
                evidence_ref=evidence_ref,
                positional_anchor=anchor,
                extracted_at=TICK,
                extraction_confidence=0.8,
                independence_assessment=Independence.INDEPENDENT,
            ),
        ),
        qualifying_context="as stated in the vendor report",
    )


def _locator_of(content: str, span: str) -> str:
    """The D-04 locator extraction would compute for a verbatim span."""
    start = content.index(span)
    return f"chars {start}-{start + len(span)}"


# ---------------------------------------------------------------------------
# Installation and the I-1 composition point
# ---------------------------------------------------------------------------


class TestInstallation:
    def test_default_store_remains_unconfigured(self):
        """[I-1] The store default is untouched: no verifier, F-V6 SKIPs."""
        assert KnowledgeStore().anchor_verifier is None

    def test_installer_returns_and_installs_the_verifier(self):
        rig = vendor_rig("src")
        assert isinstance(rig.anchor_verifier, AnchorVerifier)
        assert rig.store.anchor_verifier is rig.anchor_verifier
        assert rig.anchor_verifier.span_provider is not None
        assert rig.anchor_verifier.claims_of is not None

    def test_reinstall_replaces_the_verifier(self):
        rig = vendor_rig("src")
        replacement = install_anchor_verification(rig.store)
        assert replacement is not rig.anchor_verifier
        assert rig.store.anchor_verifier is replacement


class TestSkipToVerification:
    """F-V6 moves from SKIP (unconfigured) to real verification (wired)."""

    def test_unconfigured_store_writes_a_fabricated_anchor(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        rig.store.anchor_verifier = None  # the unconfigured composition [I-1]
        fabricated = _manual_fact(rig, ref, "chars 900-950")
        # F-V6 SKIPs: the write succeeds, no verification happened
        assert rig.store.write_fact(fabricated) is not None

    def test_configured_store_rejects_the_same_fabricated_anchor(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        fabricated = _manual_fact(rig, ref, "chars 900-950")
        with pytest.raises(WriteRejectedError) as excinfo:
            rig.store.write_fact(fabricated)
        assert excinfo.value.failure.rule_ids == ("F-V6",)
        assert "fabricated location" in excinfo.value.failure.failed_rules[0].detail
        assert rig.anchor_verifier.failed == 1


# ---------------------------------------------------------------------------
# AC1 -- valid anchors verify
# ---------------------------------------------------------------------------


class TestValidAnchors:
    def test_extraction_created_fact_passes_and_is_counted(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        outcome = _extract(
            rig, ref, anchor=SPAN,
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
        )
        assert outcome.merged_into is None
        assert rig.anchor_verifier.checked == 1
        assert rig.anchor_verifier.failed == 0

    def test_manual_fact_with_verbatim_span_passes(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        stored = rig.store.write_fact(_manual_fact(rig, ref, SPAN))
        assert stored is not None
        assert rig.anchor_verifier.checked == 1
        assert rig.anchor_verifier.failed == 0

    def test_manual_fact_with_chars_locator_passes(self):
        """Both ratified anchor formats resolve (D-04)."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        locator = _locator_of(CONTENT, SPAN)
        stored = rig.store.write_fact(_manual_fact(rig, ref, locator))
        assert stored is not None
        assert rig.anchor_verifier.failed == 0


# ---------------------------------------------------------------------------
# AC2 -- fabricated and wrong anchors are rejected
# ---------------------------------------------------------------------------


class TestFabricatedAndWrongAnchors:
    def _rejected(self, rig, fact, *, detail_fragment):
        with pytest.raises(WriteRejectedError) as excinfo:
            rig.store.write_fact(fact)
        assert excinfo.value.failure.rule_ids == ("F-V6",)
        assert detail_fragment in excinfo.value.failure.failed_rules[0].detail
        assert rig.anchor_verifier.failed == 1

    def test_out_of_bounds_locator_rejected(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        self._rejected(
            rig, _manual_fact(rig, ref, "chars 900-950"),
            detail_fragment="fabricated location",
        )

    def test_non_occurring_verbatim_span_rejected(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        self._rejected(
            rig,
            _manual_fact(rig, ref, "this wording appears nowhere in the report"),
            detail_fragment="fabricated location",
        )

    def test_malformed_anchor_rejected(self):
        """Neither a chars locator nor an occurring span: unresolvable."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        self._rejected(
            rig, _manual_fact(rig, ref, "corpus/entry-4471/lines-3-6"),
            detail_fragment="fabricated location",
        )

    def test_resolvable_but_wrong_span_rejected(self):
        """A real span that does not carry the claim's components."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        self._rejected(
            rig, _manual_fact(rig, ref, "Q3 report:"),
            detail_fragment="claim components",
        )

    def test_wrong_evidence_identity_rejected(self):
        """The anchor is real in Evidence A but attached to Evidence B:
        it does not resolve in the Evidence actually referenced."""
        rig = vendor_rig("src-a", "src-b")
        ref_a = _evidence(rig, "src-a", CONTENT)
        ref_b = _evidence(rig, "src-b", OTHER_CONTENT)
        with pytest.raises(WriteRejectedError) as excinfo:
            rig.store.write_fact(_manual_fact(rig, ref_b, SPAN))
        assert excinfo.value.failure.rule_ids == ("F-V6",)
        assert "fabricated location" in excinfo.value.failure.failed_rules[0].detail
        assert ref_b in excinfo.value.failure.failed_rules[0].detail

    def test_missing_evidence_fails_closed(self):
        """F-V2 fails the unresolvable attachment; F-V6 also fails it --
        the failure is redundant and fail-closed, never skipped."""
        rig = vendor_rig("src")
        _evidence(rig, "src", CONTENT)
        with pytest.raises(WriteRejectedError) as excinfo:
            rig.store.write_fact(
                _manual_fact(rig, "obj-nonexistent-evidence", SPAN)
            )
        assert "F-V6" in excinfo.value.failure.rule_ids

    def test_reference_mode_evidence_fails_closed(self):
        """[N-15] REFERENCE-mode material is unverifiable in place: no
        retained content means no resolvable span, so anchor verification
        fails closed. Extraction refuses such Evidence upstream; any Fact
        anchored to it is rejected at acceptance."""
        rig = vendor_rig("src")
        _evidence(rig, "src", CONTENT)
        held = make_evidence(
            rig.store.allocator,
            content_obj=EvidenceContent.by_reference(
                "https://example.com/q3-report",
                compute_fingerprint("Q3 report (held by reference)"),
            ),
        )
        stored = rig.store.write_evidence(held)
        with pytest.raises(WriteRejectedError) as excinfo:
            rig.store.write_fact(_manual_fact(rig, stored.object_id, SPAN))
        assert "F-V6" in excinfo.value.failure.rule_ids
        assert "fabricated location" in excinfo.value.failure.failed_rules[0].detail


# ---------------------------------------------------------------------------
# The ratified T03.1.3 value split
# ---------------------------------------------------------------------------


class TestValueSplit:
    def test_value_not_rechecked_at_acceptance(self):
        """Acceptance checks anchor + subject + predicate only. The value
        is extraction's gate (verbatim value_text the Fact does not
        retain); the projection emits no value rather than an unfaithful
        one. [T03.1.3]"""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        stored = rig.store.write_fact(
            _manual_fact(
                rig, ref, SPAN, value=Quantity(999.0, 0.5, "%")
            )
        )
        assert stored is not None
        assert rig.anchor_verifier.failed == 0


# ---------------------------------------------------------------------------
# AC3 -- runs on 100 percent of Facts
# ---------------------------------------------------------------------------


class TestHundredPercentCoverage:
    def test_every_fact_write_is_verified(self):
        """Three separate-path Facts plus one merged version: the counter
        arithmetic proves no Fact write skipped verification (1 + 1 + 1
        + 2 attachments = 5 checked claims)."""
        rig = vendor_rig("a", "b", "c", "d")
        r1 = _evidence(rig, "a", "Q3 report: churn rate stands at 3.5 percent.")
        r2 = _evidence(rig, "b", "Q3 report: churn rate stands at 9.9 percent.")
        r3 = _evidence(rig, "c", "Q3 memo: avg deal size is 2.7 EUR.")
        r4 = _evidence(rig, "d", "Q3 addendum: churn rate stands at 3.6 percent.")
        f1 = _extract(
            rig, r1, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
        )
        f2 = _extract(
            rig, r2, anchor="churn rate stands at 9.9 percent",
            value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
        )
        f3 = _extract(
            rig, r3, anchor="avg deal size is 2.7 EUR",
            subject="avg deal size", predicate="is",
            value=Quantity(2.7, 0.3, "EUR"), value_text="2.7 EUR",
        )
        merged = _extract(
            rig, r4, anchor="churn rate stands at 3.6 percent",
            value=Quantity(3.6, 0.5, "%"), value_text="3.6 percent",
        )
        assert f1.merged_into is None
        assert f2.merged_into is None
        assert f3.merged_into is None
        assert merged.merged_into is not None  # EQUIVALENT -> new version
        assert rig.anchor_verifier.checked == 5
        assert rig.anchor_verifier.failed == 0
        assert len(rig.store.facts.active_facts()) == 3


# ---------------------------------------------------------------------------
# Merge and versioning
# ---------------------------------------------------------------------------


class TestMergeAndVersioning:
    def test_merge_verifies_every_attachment_of_the_new_version(self):
        rig = vendor_rig("a", "b")
        r1 = _evidence(rig, "a", "Q3 report: churn rate stands at 3.5 percent.")
        r2 = _evidence(rig, "b", "Q3 report: churn rate stands at 3.6 percent.")
        first = _extract(
            rig, r1, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
        )
        second = _extract(
            rig, r2, anchor="churn rate stands at 3.6 percent",
            value=Quantity(3.6, 0.5, "%"), value_text="3.6 percent",
        )
        assert second.merged_into is not None
        head = rig.store.get_fact(second.merged_into)
        assert head is not None
        assert head.attachment_count == 2
        # canonical write (1 claim) + merged version write (2 claims)
        assert rig.anchor_verifier.checked == 3
        assert rig.anchor_verifier.failed == 0
        assert rig.store.find(first.object_id).status is ObjectStatus.SUPERSEDED
        assert rig.store.find(head.object_id).status is ObjectStatus.ACTIVE

    def test_historical_versions_not_retroactively_reverified(self):
        """Verification happens at write time only. After the merge, a new
        unrelated Fact advances the counter by exactly its own claims --
        the existing lineage is never rescanned."""
        rig = vendor_rig("a", "b", "c")
        r1 = _evidence(rig, "a", "Q3 report: churn rate stands at 3.5 percent.")
        r2 = _evidence(rig, "b", "Q3 report: churn rate stands at 3.6 percent.")
        r3 = _evidence(rig, "c", "Q3 memo: avg deal size is 2.7 EUR.")
        _extract(
            rig, r1, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
        )
        _extract(
            rig, r2, anchor="churn rate stands at 3.6 percent",
            value=Quantity(3.6, 0.5, "%"), value_text="3.6 percent",
        )
        assert rig.anchor_verifier.checked == 3  # 1 + merged 2
        _extract(
            rig, r3, anchor="avg deal size is 2.7 EUR",
            subject="avg deal size", predicate="is",
            value=Quantity(2.7, 0.3, "EUR"), value_text="2.7 EUR",
        )
        # +1 for the new Fact only -- no retroactive verification
        assert rig.anchor_verifier.checked == 4


# ---------------------------------------------------------------------------
# The approved C-1 consequence
# ---------------------------------------------------------------------------


class TestC1MergeConsequence:
    def test_whitespace_divergent_merge_refused_with_named_surviving_state(self):
        """[C-1, approved] S-3 component equality is normalised (case and
        whitespace); F-V6 presence is raw casefold substring. A merge of
        claims whose components differ only in internal whitespace composes
        under S-3, then fails F-V6 at acceptance: the T03.1.4-ratified
        ACCEPTANCE_REFUSED path names the surviving state."""
        rig = vendor_rig("src-a", "src-b")
        ra = _evidence(rig, "src-a", f"Changelog: {GOOD_SPAN}.")
        rb = _evidence(rig, "src-b", f"Memo: {SLOPPY_SPAN}.")
        first = _extract(
            rig, ra, anchor=GOOD_SPAN,
            subject="bulk edits", predicate="silently fail above",
        )
        assert first.merged_into is None
        with pytest.raises(ExtractionRefusedError) as excinfo:
            _extract(
                rig, rb, anchor=SLOPPY_SPAN,
                subject="bulk  edits", predicate="silently fail above",
            )
        assert "ACCEPTANCE_REFUSED" in str(excinfo.value)
        # the F-V6 failure is the cause: exactly one failed claim
        assert rig.anchor_verifier.failed == 1
        assert rig.anchor_verifier.checked == 3  # canonical 1 + attempted 2
        # the surviving state, as ratified [T03.1.4, N-10]:
        canonical = rig.store.get_fact(first.object_id)
        assert rig.store.find(first.object_id).status is ObjectStatus.SUPERSEDED
        assert canonical.attachment_count == 1  # every attachment it had
        assert rig.store.facts.active_facts() == ()  # no successor exists
        assert len(rig.log) == 1  # the refusal is recorded, never silent
        failure = rig.log.for_evidence(rb)[-1]
        assert failure.stage is ExtractionStage.MERGE_FAILED


# ---------------------------------------------------------------------------
# Determinism [N-4]
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_two_rigs_produce_identical_verification_outcomes(self):
        def scenario():
            rig = vendor_rig("src")
            ref = _evidence(rig, "src", CONTENT)
            _extract(
                rig, ref, anchor=SPAN,
                value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            )
            try:
                rig.store.write_fact(_manual_fact(rig, ref, "chars 900-950"))
            except WriteRejectedError:
                pass
            # checked: 1 accepted extraction + 1 evaluated (failing) claim;
            # failed: the fabricated anchor; active: the one accepted Fact
            return (
                rig.anchor_verifier.checked,
                rig.anchor_verifier.failed,
                len(rig.store.facts.active_facts()),
            )

        assert scenario() == scenario() == (2, 1, 1)

    def test_repeated_verification_of_the_same_fact_is_stable(self):
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        fact = _manual_fact(rig, ref, SPAN)
        ctx = AcceptanceContext(
            attributes=fact.attributes,
            fact=fact,
            anchor_verifier=rig.anchor_verifier,
        )
        first = rig.anchor_verifier(ctx)
        second = rig.anchor_verifier(ctx)
        assert first == second
        assert first.outcome.name == "PASS"


# ---------------------------------------------------------------------------
# Regression behavior at the boundary
# ---------------------------------------------------------------------------


class TestRegressionBehavior:
    def test_extraction_gate_precedes_acceptance(self):
        """Extraction's own S-5 layer-1 gate still refuses a claim whose
        components are absent from its anchor BEFORE any write: no Fact
        exists for acceptance to see, and the verifier never runs."""
        rig = vendor_rig("src")
        ref = _evidence(rig, "src", CONTENT)
        with pytest.raises(ExtractionRefusedError):
            _extract(
                rig, ref,
                anchor=SPAN, subject="a subject the span lacks",
            )
        assert rig.anchor_verifier.checked == 0
        assert len(rig.log) == 1
        assert len(rig.store.facts) == 0

    def test_non_fact_writes_skip_verification(self):
        """F-V6 applies to Facts only: Evidence writes through the same
        acceptance path leave the verifier untouched (SKIP)."""
        rig = vendor_rig("src-a", "src-b")
        _evidence(rig, "src-a", CONTENT)
        _evidence(rig, "src-b", OTHER_CONTENT)
        assert rig.anchor_verifier.checked == 0
        assert rig.anchor_verifier.failed == 0
