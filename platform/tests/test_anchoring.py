"""Contract tests for positional anchoring into source Evidence. [F-V2]

Task: T03.1.3

Architecture References:
- F-V2   Every accepted Claim/Fact attachment has a resolvable anchor
- F-V6   A Fact's claim must be present in its Evidence at the stated anchor
- F-I3   Anchors are preserved verbatim, never rewritten
- S-5    Layer 1 leans on anchors being mechanically checkable
- N-4    Outputs non-deterministic; property-based assertions
- N-10   Refusals recorded, never silent; failed != found-nothing
- N-22   Side registers live outside the object model

T03.1.3 acceptance criteria under test:
  AC1  Every accepted attachment has a resolvable anchor          -> IMPLEMENTED
  AC2  Anchor precise enough to locate the claim without
       full re-reading (O(1) direct-slice resolution)             -> IMPLEMENTED

The locator format is closed: `chars <start>-<end>`, 0-based, half-open
(content[start:end] == span), code-point indexed -- language-agnostic for
CJK, RTL and astral-plane text. Resolution never searches: malformed,
out-of-bounds and ambiguous anchors fail closed, never guessed.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, RuleOutcome
from oip.anchoring import evidence_span_provider, fact_anchor_claims
from oip.extraction import (
    LOCATOR_PATTERN,
    AnchoringError,
    ExtractionRefusedError,
    ExtractionStage,
    PositionalAnchorRegister,
    extract,
    locate,
    resolve_locator,
)
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier
from oip.store import KnowledgeStore
from tests.test_extraction import TICK, VENDOR, changelog_rig, vendor_rig

T0 = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The locator computation -- exact spans, all scripts
# ---------------------------------------------------------------------------


class TestLocatorComputation:
    CONTENT = (
        "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
        "Support recommends batching smaller."
    )
    SPAN = "bulk edits silently fail above 50 SKUs"

    def test_exact_span_round_trip(self):
        locator = locate(self.CONTENT, self.SPAN)
        assert locator == f"chars {self.CONTENT.find(self.SPAN)}-{self.CONTENT.find(self.SPAN) + len(self.SPAN)}"
        assert resolve_locator(self.CONTENT, locator) == self.SPAN

    def test_locator_format_is_closed(self):
        locator = locate(self.CONTENT, self.SPAN)
        assert re.fullmatch(r"chars [0-9]+-[0-9]+", locator)

    def test_half_open_slice_convention(self):
        locator = locate(self.CONTENT, self.SPAN)
        start, end = (
            int(part) for part in locator.removeprefix("chars ").split("-")
        )
        assert self.CONTENT[start:end] == self.SPAN
        assert end == start + len(self.SPAN)

    def test_span_at_start_boundary(self):
        span = self.CONTENT[:20]
        assert resolve_locator(self.CONTENT, locate(self.CONTENT, span)) == span

    def test_span_at_end_boundary(self):
        span = self.CONTENT[-17:]
        assert resolve_locator(self.CONTENT, locate(self.CONTENT, span)) == span

    def test_whole_content_span(self):
        locator = locate(self.CONTENT, self.CONTENT)
        assert locator == f"chars 0-{len(self.CONTENT)}"
        assert resolve_locator(self.CONTENT, locator) == self.CONTENT

    def test_span_with_punctuation(self):
        span = "March: bulk edits silently fail above 50 SKUs."
        assert resolve_locator(self.CONTENT, locate(self.CONTENT, span)) == span

    def test_span_with_internal_whitespace(self):
        content = "alpha  beta\tgamma\ndelta: the datum holds."
        span = "beta\tgamma\ndelta"
        assert resolve_locator(content, locate(content, span)) == span

    def test_multilingual_offsets_are_code_points(self):
        content = (
            "Der Prüfbericht zeigt: der Markt für Photovoltaik wächst "
            "um 34 Prozent; Überspannungsschutz fehlt häufig."
        )
        span = "der Markt für Photovoltaik wächst um 34 Prozent"
        locator = locate(content, span)
        assert resolve_locator(content, locator) == span
        # offset counts characters, not bytes: the ü/ä before the span
        # shift it by exactly their code-point count
        assert int(locator.split()[1].split("-")[0]) == content.find(span)

    def test_cjk_offsets_are_code_points(self):
        content = "报告称：季度营收增长12%，利润率保持稳定。预计下一季度继续增长。"
        span = "季度营收增长12%"
        locator = locate(content, span)
        assert resolve_locator(content, locator) == span
        # three CJK chars + full-width colon before the span: offset 4
        assert int(locator.split()[1].split("-")[0]) == 4

    def test_rtl_offsets_are_code_points(self):
        content = (
            "أظهر التقرير أن المبيعات ارتفعت بنسبة 15% في الربع الثاني "
            "من هذا العام."
        )
        span = "المبيعات ارتفعت بنسبة 15%"
        locator = locate(content, span)
        assert resolve_locator(content, locator) == span
        assert int(locator.split()[1].split("-")[0]) == content.find(span)

    def test_astral_plane_counts_as_one_code_point(self):
        content = "📈 Q2 report: revenue grew 14% YoY 📉 before costs."
        span = "revenue grew 14%"
        locator = locate(content, span)
        assert resolve_locator(content, locator) == span
        # the emoji (astral plane, two UTF-16 units) is ONE code point:
        # the offset agrees with Python's own index, not a UTF-16 count
        assert int(locator.split()[1].split("-")[0]) == content.find(span)
        assert len("📈") == 1


# ---------------------------------------------------------------------------
# Locator resolution -- strict, never searching, never guessing
# ---------------------------------------------------------------------------


class TestLocatorResolutionStrictness:
    CONTENT = "Vendor changelog: bulk edits silently fail above 50 SKUs."

    @pytest.mark.parametrize(
        "bad",
        [
            "",
            "   ",
            "chars",
            "chars 5",
            "5-10",
            "chars a-b",
            "chars 5-10 extra",
            "chars -1-5",
            "chars 5-",
            "CHARS 5-10",
            "Chars 5-10",
            "chars 5 - 10",
            "chars +5-10",
            "chars 5.0-10",
            "position 5-10",
            "chars\t5-10",
            "chars\n5-10",
        ],
    )
    def test_malformed_locators_refused(self, bad):
        with pytest.raises(AnchoringError):
            resolve_locator(self.CONTENT, bad)

    def test_non_ascii_digits_refused(self):
        # Python's int() accepts non-ASCII decimal digits; the closed
        # [0-9] grammar must refuse look-alike locators outright.
        with pytest.raises(AnchoringError):
            resolve_locator(self.CONTENT, "chars ٤٥-٥٠")  # Arabic-Indic
        with pytest.raises(AnchoringError):
            resolve_locator(self.CONTENT, "chars ５-１０")  # full-width

    def test_end_beyond_content_refused(self):
        with pytest.raises(AnchoringError):
            resolve_locator(self.CONTENT, "chars 0-1000")

    def test_empty_span_refused(self):
        with pytest.raises(AnchoringError):
            resolve_locator(self.CONTENT, "chars 10-10")

    def test_inverted_span_refused(self):
        with pytest.raises(AnchoringError):
            resolve_locator(self.CONTENT, "chars 10-5")

    def test_exact_end_boundary_resolves(self):
        assert (
            resolve_locator(self.CONTENT, f"chars 0-{len(self.CONTENT)}")
            == self.CONTENT
        )

    def test_surrounding_whitespace_tolerated_format_not(self):
        # formatting whitespace around a well-formed locator is trimmed;
        # whitespace INSIDE the locator is a format violation (above)
        assert resolve_locator(self.CONTENT, "  chars 0-6  ") == "Vendor"

    def test_resolution_never_searches_content(self):
        # a locator pointing at the WRONG offset returns exactly what is
        # there -- it never falls back to searching for a plausible span
        assert resolve_locator(self.CONTENT, "chars 0-6") == "Vendor"
        assert resolve_locator(self.CONTENT, "chars 1-6") == "endor"

    def test_empty_content_refuses_any_locator(self):
        with pytest.raises(AnchoringError):
            resolve_locator("", "chars 0-1")


# ---------------------------------------------------------------------------
# Ambiguity and absence are preserved, never resolved by guessing
# ---------------------------------------------------------------------------


class TestAmbiguityPreserved:
    CONTENT = "A: the datum holds. B: the datum holds."

    def test_repeated_span_gets_no_locator(self):
        with pytest.raises(AnchoringError) as exc:
            locate(self.CONTENT, "the datum holds")
        assert "occurs 2 times" in str(exc.value)

    def test_missing_span_gets_no_locator(self):
        with pytest.raises(AnchoringError) as exc:
            locate(self.CONTENT, "the datum does not hold")
        assert "F-V2" in str(exc.value)

    def test_unique_inside_repeated_is_still_ambiguous(self):
        # uniqueness is a property of the whole span in the whole content;
        # a locator cannot be guessed from a unique prefix of a repeated span
        with pytest.raises(AnchoringError):
            locate(self.CONTENT, "the datum holds.")


# ---------------------------------------------------------------------------
# N-4: property-based round trip
# ---------------------------------------------------------------------------

TEXT = st.text(min_size=1, max_size=200)


@st.composite
def content_and_span(draw):
    content = draw(TEXT)
    if not content:
        return content, ""
    start = draw(st.integers(0, len(content) - 1))
    length = draw(st.integers(1, len(content) - start))
    return content, content[start : start + length]


class TestPropertyRoundTrip:
    @settings(max_examples=100, deadline=None)
    @given(content_and_span())
    def test_locate_resolve_round_trip(self, pair):
        content, span = pair
        if content.count(span) != 1:
            with pytest.raises(AnchoringError):
                locate(content, span)
            return
        locator = locate(content, span)
        assert LOCATOR_PATTERN.fullmatch(locator)
        assert resolve_locator(content, locator) == span

    @settings(max_examples=100, deadline=None)
    @given(TEXT, st.integers(min_value=0, max_value=10_000))
    def test_out_of_bounds_locators_always_refused(self, content, end):
        end = max(end, len(content) + 1)
        with pytest.raises(AnchoringError):
            resolve_locator(content, f"chars 0-{end}")

    @settings(max_examples=50, deadline=None)
    @given(TEXT)
    def test_empty_and_inverted_always_refused(self, content):
        for bad in ("chars 0-0", "chars 5-2", "chars 3-3"):
            with pytest.raises(AnchoringError):
                resolve_locator(content, bad)


# ---------------------------------------------------------------------------
# The register [N-22 pattern: side register, outside the object model]
# ---------------------------------------------------------------------------


class TestPositionalAnchorRegister:
    def test_record_and_lookup(self):
        register = PositionalAnchorRegister()
        assert register.record("e1", "span one", "chars 0-8") == "chars 0-8"
        assert register.locator_for("e1", "span one") == "chars 0-8"
        assert len(register) == 1

    def test_lookup_of_unknown_key_is_none(self):
        register = PositionalAnchorRegister()
        assert register.locator_for("e1", "nope") is None
        assert register.for_evidence("e1") == {}

    def test_idempotent_re_record(self):
        register = PositionalAnchorRegister()
        register.record("e1", "span", "chars 0-4")
        assert register.record("e1", "span", "chars 0-4") == "chars 0-4"
        assert len(register) == 1

    def test_conflicting_re_record_refused(self):
        register = PositionalAnchorRegister()
        register.record("e1", "span", "chars 0-4")
        with pytest.raises(AnchoringError) as exc:
            register.record("e1", "span", "chars 5-9")
        assert "conflicting" in str(exc.value)

    def test_for_evidence_filters_by_reference(self):
        register = PositionalAnchorRegister()
        register.record("e1", "span a", "chars 0-6")
        register.record("e1", "span b", "chars 10-16")
        register.record("e2", "span c", "chars 0-6")
        assert register.for_evidence("e1") == {
            "span a": "chars 0-6",
            "span b": "chars 10-16",
        }
        assert len(register) == 3

    def test_concurrent_records_of_distinct_keys(self):
        register = PositionalAnchorRegister()
        errors: list[Exception] = []

        def worker(n: int) -> None:
            try:
                for i in range(50):
                    register.record(f"e{n}", f"span {i}", f"chars {i}-{i + 1}")
            except Exception as exc:  # pragma: no cover - failure signal
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert len(register) == 400

    def test_register_is_outside_the_object_model(self):
        # the register is a plain dataclass: it enters no lineage graph,
        # holds no identity, and carries no lifecycle
        register = PositionalAnchorRegister()
        register.record("e1", "span", "chars 0-4")
        assert not hasattr(register, "object_id")
        assert not hasattr(register, "status")


# ---------------------------------------------------------------------------
# Extraction integration [AC1: every accepted attachment anchored]
# ---------------------------------------------------------------------------


class TestExtractionIntegration:
    SPAN = "bulk edits silently fail above 50 SKUs"

    def _content_of(self, rig, ref):
        return rig.store.get_evidence(ref).content.content

    def test_accepted_extraction_carries_verified_locator(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.locator is not None
        content = self._content_of(rig, ref)
        start = content.find(self.SPAN)
        assert outcome.locator == f"chars {start}-{start + len(self.SPAN)}"
        # the round trip held at extraction time; it holds now too
        assert resolve_locator(content, outcome.locator) == self.SPAN

    def test_attachment_verbatim_anchor_unchanged(self):
        # T03.1.1 behavior preserved: the attachment's anchor IS the span
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        attachment = fact.attachment_for(ref)
        assert attachment.positional_anchor == self.SPAN

    def test_register_populated_on_acceptance(self):
        rig, ref = changelog_rig()
        register = PositionalAnchorRegister()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=register,
        )
        assert register.locator_for(ref, self.SPAN) == outcome.locator
        assert len(register) == 1

    def test_extraction_works_without_a_register(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert outcome.locator is not None  # computed regardless

    def test_refused_extraction_registers_nothing(self):
        rig, ref = changelog_rig()
        register = PositionalAnchorRegister()
        with pytest.raises(ExtractionRefusedError):
            extract(
                rig.extraction(
                    evidence_ref=ref, anchor="a span that never occurred"
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
                anchors=register,
            )
        assert len(register) == 0  # only accepted extractions register

    def test_reextraction_of_same_span_is_idempotent_in_register(self):
        rig, ref = changelog_rig()
        register = PositionalAnchorRegister()
        first = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=register,
        )
        second = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=register,
        )
        assert first.locator == second.locator
        assert len(register) == 1  # same key, same locator: no conflict

    def test_anchor_not_resolvable_is_an_attempted_stage(self):
        # N-10: the judgement ran against content in hand, so a refusal at
        # this stage is a FAILED attempt, never found-nothing
        from oip.extraction import _ATTEMPTED_STAGES

        assert ExtractionStage.ANCHOR_NOT_RESOLVABLE in _ATTEMPTED_STAGES

    def test_multilingual_corpus_all_anchored(self):
        corpus = {
            "src-de": (
                "Der Prüfbericht zeigt: der Markt für Photovoltaik wächst "
                "um 34 Prozent; Überspannungsschutz fehlt häufig."
            ),
            "src-zh": "报告称：季度营收增长12%，利润率保持稳定。",
            "src-ar": "أظهر التقرير أن المبيعات ارتفعت بنسبة 15% في الربع الثاني.",
        }
        spans = {
            "src-de": "der Markt für Photovoltaik wächst um 34 Prozent",
            "src-zh": "季度营收增长12%",
            "src-ar": "المبيعات ارتفعت بنسبة 15%",
        }
        rig = vendor_rig(*corpus)
        register = PositionalAnchorRegister()
        facts = []
        for source, content in corpus.items():
            ref = rig.acquire(source, VENDOR, content)
            outcome = extract(
                rig.extraction(
                    evidence_ref=ref, anchor=spans[source],
                    subject=spans[source].split()[0],
                    predicate=spans[source].split()[0],
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
                anchors=register,
            )
            facts.append((ref, rig.store.get_fact(outcome.object_id)))
        # AC1 over the whole multilingual corpus: every accepted
        # attachment resolves BOTH ways -- verbatim and positional
        for ref, fact in facts:
            attachment = fact.attachment_for(ref)
            content = self._content_of(rig, ref)
            assert content.count(attachment.positional_anchor) == 1
            locator = register.locator_for(ref, attachment.positional_anchor)
            assert locator is not None
            assert resolve_locator(content, locator) == (
                attachment.positional_anchor
            )


# ---------------------------------------------------------------------------
# The S-5 bridge [existing AnchorVerifier machinery, real content]
# ---------------------------------------------------------------------------


class TestAnchorVerifierWiring:
    SPAN = "bulk edits silently fail above 50 SKUs"
    CONTENT = (
        "Vendor changelog, March: bulk edits silently fail above 50 SKUs. "
        "Support recommends batching smaller."
    )

    def _fact_and_provider(self):
        rig, ref = changelog_rig()
        outcome = extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        fact = rig.store.get_fact(outcome.object_id)
        provider = evidence_span_provider(self.CONTENT)
        return fact, provider, ref

    def test_provider_resolves_locator_by_direct_slice(self):
        _, provider, _ = self._fact_and_provider()
        locator = f"chars {self.CONTENT.find(self.SPAN)}-{self.CONTENT.find(self.SPAN) + len(self.SPAN)}"
        assert provider(Anchor("e1", locator)) == self.SPAN

    def test_provider_malformed_locator_is_unresolvable(self):
        _, provider, _ = self._fact_and_provider()
        for bad in ("chars 999-9999", "garbage", "chars -1-5"):
            assert provider(Anchor("e1", bad)) is None

    def test_empty_locator_unrepresentable_and_unresolvable(self):
        # the ratified Anchor type refuses an empty locator outright, so
        # an unresolvable-by-emptiness anchor cannot even be constructed;
        # the provider's own None path stays defensive
        with pytest.raises(ValueError):
            Anchor("e1", "")
        _, provider, _ = self._fact_and_provider()
        assert provider(Anchor("e1", " ")) is None

    def test_provider_resolves_verbatim_span(self):
        # the T03.1.1 convention still resolves: the anchor IS the span
        _, provider, _ = self._fact_and_provider()
        assert provider(Anchor("e1", self.SPAN)) == self.SPAN

    def test_provider_refuses_missing_verbatim_span(self):
        _, provider, _ = self._fact_and_provider()
        assert provider(Anchor("e1", "never written anywhere here")) is None

    def test_provider_refuses_ambiguous_verbatim_span(self):
        provider = evidence_span_provider("A: datum. B: datum.")
        assert provider(Anchor("e1", "datum")) is None

    def test_fv6_passes_on_a_real_extracted_fact(self):
        fact, provider, _ = self._fact_and_provider()
        verifier = AnchorVerifier(
            span_provider=provider,
            claims_of=lambda ctx: fact_anchor_claims(fact),
        )
        result = verifier(AcceptanceContext(attributes=fact.attributes))
        assert result.outcome is RuleOutcome.PASS
        assert verifier.checked == 1
        assert verifier.failed == 0

    def test_fabricated_subject_still_fails_layer_1(self):
        # the bridge must not weaken S-5: a wrong subject is still caught
        fact, provider, _ = self._fact_and_provider()
        original = fact_anchor_claims(fact)[0]
        forged = AnchorClaim(
            claim=original.claim,
            anchor=original.anchor,
            subject="a subject from nowhere",
            predicate=original.predicate,
            value="",
        )
        verifier = AnchorVerifier(
            span_provider=provider,
            claims_of=lambda ctx: (forged,),
        )
        result = verifier(AcceptanceContext(attributes=fact.attributes))
        assert result.outcome is RuleOutcome.FAIL
        assert "subject" in result.detail

    def test_fabricated_locator_fails_layer_1(self):
        # an anchor that does not resolve is fabricated location: caught
        fact, _, _ = self._fact_and_provider()
        original = fact_anchor_claims(fact)[0]
        forged = AnchorClaim(
            claim=original.claim,
            anchor=Anchor(
                evidence_id=original.anchor.evidence_id, locator="chars 900-950"
            ),
            subject=original.subject,
            predicate=original.predicate,
            value="",
        )
        verifier = AnchorVerifier(
            span_provider=evidence_span_provider(self.CONTENT),
            claims_of=lambda ctx: (forged,),
        )
        result = verifier(AcceptanceContext(attributes=fact.attributes))
        assert result.outcome is RuleOutcome.FAIL
        assert "does not resolve" in result.detail

    def test_projection_emits_one_claim_per_attachment(self):
        fact, _, ref = self._fact_and_provider()
        claims = fact_anchor_claims(fact)
        assert len(claims) == 1
        assert claims[0].claim == fact.claim.as_text()
        assert claims[0].subject == fact.claim.subject
        assert claims[0].predicate == fact.claim.predicate
        # the Fact does not carry the value text; the projection emits no
        # value rather than an unfaithful one
        assert claims[0].value == ""
        assert claims[0].anchor.evidence_id == ref
        # F-I3: the anchor is the attachment's verbatim span, unchanged
        assert claims[0].anchor.locator == fact.attachment_for(ref).positional_anchor

    def test_store_default_verifier_unchanged(self):
        # installing the verifier at acceptance for 100% of Facts is
        # T03.2.1; the default store remains unconfigured
        assert KnowledgeStore().anchor_verifier is None

    def test_fv2_holds_on_every_attachment_of_the_corpus(self):
        # AC1 end to end: for each accepted Fact the store accepted, its
        # attachment anchor resolves verbatim in the originating Evidence
        corpus = {
            "src-en": self.CONTENT,
            "src-zh": "报告称：季度营收增长12%，利润率保持稳定。",
        }
        spans = {
            "src-en": self.SPAN,
            "src-zh": "季度营收增长12%",
        }
        rig = vendor_rig(*corpus)
        register = PositionalAnchorRegister()
        accepted = []
        for source, content in corpus.items():
            ref = rig.acquire(source, VENDOR, content)
            outcome = extract(
                rig.extraction(
                    evidence_ref=ref, anchor=spans[source],
                    subject=spans[source].split()[0],
                    predicate=spans[source].split()[0],
                ),
                store=rig.store, log=rig.log, clock=lambda: TICK,
                anchors=register,
            )
            accepted.append((ref, outcome.object_id))
        for ref, fact_id in accepted:
            fact = rig.store.get_fact(fact_id)
            attachment = fact.attachment_for(ref)
            content = rig.store.get_evidence(ref).content.content
            assert content.count(attachment.positional_anchor) == 1
            locator = register.locator_for(ref, attachment.positional_anchor)
            assert locator is not None
            assert resolve_locator(content, locator) == (
                attachment.positional_anchor
            )

    def test_locator_locates_without_holding_content(self):
        # AC2: the register alone locates the claim's position -- no
        # content object is consulted to produce the address
        rig, ref = changelog_rig()
        register = PositionalAnchorRegister()
        extract(
            rig.extraction(evidence_ref=ref),
            store=rig.store, log=rig.log, clock=lambda: TICK,
            anchors=register,
        )
        locator = register.locator_for(ref, self.SPAN)
        assert locator is not None
        assert re.fullmatch(r"chars [0-9]+-[0-9]+", locator)
        # and the slice is exact the moment any content is supplied
        content = self.CONTENT if self.CONTENT in (
            rig.store.get_evidence(ref).content.content,
        ) else rig.store.get_evidence(ref).content.content
        start, end = (
            int(p) for p in locator.removeprefix("chars ").split("-")
        )
        assert content[start:end] == self.SPAN
