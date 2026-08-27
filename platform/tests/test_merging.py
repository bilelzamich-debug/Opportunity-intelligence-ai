"""Contract tests for canonical-claim merging. [D-05, R-5, S-3]

Task: T03.1.4

Architecture References:
- D-05/R-5  Facts are canonical claims; equivalent extractions ATTACH
- S-3       merge policy: EQUIVALENT merges; CONTAINMENT/UNCERTAIN
            separate with DUPLICATES; NOT_EQUIVALENT separates
- F-I2      attachments add-only across the supersession chain
- F-I4      merge justification = the explicit S-3 verdict + reason
- R-1/V11   merge produces a NEW Fact version (new object_id, version+1)
- I5        one ACTIVE version per lineage (transition-then-write)
- R-3/V5    support re-derived as min over the WIDENED upstream set
- N-16      independence never inferred; UNASSESSED never counted
- N-10      merge refusals recorded, never silent
- T03.1.3   anchors registered for accepted merged attachments

T03.1.4 acceptance criteria under test:
  AC1  Equivalent claim adds an attachment, not a new Fact -> IMPLEMENTED
  AC2  Merge produces a new Fact version                   -> IMPLEMENTED
  AC3  Uncertain equivalence produces DUPLICATES, not a
       merge                                               -> IMPLEMENTED
"""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest

from oip.claim import Quantity, UNQUALIFIED, Verdict
from oip.configuration import FailureStore
from oip.enums import ObjectStatus, ObjectType
from oip.extraction import (
    ExtractionRefusedError,
    ExtractionStage,
    PositionalAnchorRegister,
    _ATTEMPTED_STAGES,
    build_density_report,
    extract,
    resolve_locator,
)
from oip.fact import Independence
from tests.test_extraction import TICK, VENDOR, vendor_rig

SPAN = "bulk edits silently fail above 50 SKUs"


def _fact_type():
    return ObjectType.FACT


def _active_facts(rig):
    return [
        rig.store.get_fact(stored.object_id)
        for stored in rig.store.objects_of_type(ObjectType.FACT)
        if rig.store.find(stored.object_id).status is ObjectStatus.ACTIVE
    ]


def _fact_count(rig):
    return sum(1 for _ in rig.store.objects_of_type(ObjectType.FACT))


# ---------------------------------------------------------------------------
# AC1 + AC2: equivalent -> attachment + new version
# ---------------------------------------------------------------------------


class TestEquivalentMerges:
    def test_equivalent_claim_adds_attachment_not_a_new_fact(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        first = extract(
            rig.extraction(evidence_ref=ra),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            rig.extraction(evidence_ref=rb),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        # AC1: the equivalent claim ATTACHED; there is exactly ONE
        # canonical lineage -- no parallel Fact was created
        assert second.merged_into == second.object_id
        canonical = rig.store.get_fact(second.object_id)
        assert canonical.attachment_count == 2
        assert {a.evidence_ref for a in canonical.attachments} == {ra, rb}
        assert canonical.attributes.identity.lineage_id == (
            rig.store.get_fact(first.object_id).attributes.identity.lineage_id
        )
        # and no second lineage exists in the store
        active = _active_facts(rig)
        assert len(active) == 1 and active[0].object_id == second.object_id

    def test_merge_produces_a_new_fact_version(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        first = extract(
            rig.extraction(evidence_ref=ra),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            rig.extraction(evidence_ref=rb),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        # AC2: new version -- new object_id, version+1, one lineage
        assert second.object_id != first.object_id
        predecessor = rig.store.get_fact(first.object_id)
        successor = rig.store.get_fact(second.object_id)
        assert successor.attributes.version == (
            predecessor.attributes.version + 1
        )
        assert successor.attributes.identity.lineage_id == (
            predecessor.attributes.identity.lineage_id
        )
        # the predecessor is superseded WITH its recorded reason
        stored = rig.store.find(first.object_id)
        assert stored.status is ObjectStatus.SUPERSEDED
        assert stored.attributes.status_reason is not None
        assert "corroborated" in stored.attributes.status_reason

    def test_fi4_justification_recorded_on_the_canonical(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        second = extract(rig.extraction(evidence_ref=rb),
                         store=rig.store, log=rig.log, clock=lambda: TICK)
        canonical = rig.store.get_fact(second.object_id)
        assert len(canonical.merge_history) == 1
        justification = canonical.merge_history[0]
        assert justification.verdict is Verdict.EQUIVALENT
        assert justification.reason.strip()  # the S-3 four-condition why
        assert justification.merged_evidence_ref == rb

    def test_merge_chain_three_sources_one_lineage(self):
        rig = vendor_rig("src-a", "src-b", "src-c")
        refs = [
            rig.acquire(name, VENDOR, f"{name}: {SPAN}.")
            for name in ("src-a", "src-b", "src-c")
        ]
        outcomes = []
        for i, ref in enumerate(refs):
            outcomes.append(extract(
                rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log,
                clock=lambda: TICK + timedelta(seconds=i),
            ))
        head = rig.store.get_fact(outcomes[-1].object_id)
        assert head.attributes.version == 3
        assert head.attachment_count == 3
        assert len(head.merge_history) == 2
        assert all(j.verdict is Verdict.EQUIVALENT for j in head.merge_history)
        superseded = [
            o for o in outcomes[:-1]
            if rig.store.find(o.object_id).status is ObjectStatus.SUPERSEDED
        ]
        assert len(superseded) == 2
        # F-I2 across the chain: every version keeps what IT carried --
        # v1 had one attachment, v2 had two, both intact as superseded
        assert rig.store.get_fact(outcomes[0].object_id).attachment_count == 1
        assert rig.store.get_fact(outcomes[1].object_id).attachment_count == 2
        assert not rig.store.facts.integrity().verify()

    def test_merged_lineage_reaches_every_attesting_evidence(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        second = extract(rig.extraction(evidence_ref=rb),
                         store=rig.store, log=rig.log, clock=lambda: TICK)
        canonical = rig.store.get_fact(second.object_id)
        upstream = {r.object_id for r in canonical.attributes.derives_from}
        assert upstream == {ra, rb}
        assert canonical.attributes.evidence_reachable


# ---------------------------------------------------------------------------
# AC3: uncertain / containment -> DUPLICATES, never a merge
# ---------------------------------------------------------------------------


class TestDuplicatesNotMerges:
    def test_uncertain_equivalence_produces_duplicates_not_a_merge(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire(
            "src-b", VENDOR, "Forum: bulk edits silently fail above 60 SKUs."
        )
        first = extract(
            rig.extraction(evidence_ref=ra, qualifier="above 50 SKUs"),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            rig.extraction(
                evidence_ref=rb, qualifier="above 60 SKUs",
                anchor="bulk edits silently fail above 60 SKUs",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        # AC3: NOT merged; DUPLICATES recorded on the new Fact
        assert second.merged_into is None
        assert second.duplicates == (first.object_id,)
        fact = rig.store.get_fact(second.object_id)
        assert fact.attributes.duplicates == (first.object_id,)
        assert fact.attachment_count == 1
        # both Facts remain ACTIVE
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        assert rig.store.find(second.object_id).status is ObjectStatus.ACTIVE
        # and the verdict behind the link was UNCERTAIN (differing
        # qualified qualifiers: containment undecidable from structure)
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.UNCERTAIN
        }

    def test_containment_keeps_the_existing_narrower_canonical(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire(
            "src-b", VENDOR, "Forum: bulk edits silently fail above 50 SKUs, "
            "per the March advisory."
        )
        first = extract(
            rig.extraction(evidence_ref=ra),  # unqualified: the BROADER
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            rig.extraction(
                evidence_ref=rb, qualifier="above 50 SKUs, per the March advisory",
                anchor="bulk edits silently fail above 50 SKUs",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        # the narrower (qualified) new claim is NOT merged away either:
        # S-3 containment separates with DUPLICATES
        assert second.merged_into is None
        assert second.duplicates == (first.object_id,)
        # the existing Fact was never rewritten or superseded
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        assert rig.store.get_fact(first.object_id).attachment_count == 1

    def test_value_mismatch_separates_with_no_link(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Pricing: merchant fees rise 3.5% this year.")
        rb = rig.acquire("src-b", VENDOR,
                         "Pricing: merchant fees rise 9.9% this year.")
        first = extract(
            rig.extraction(
                evidence_ref=ra, subject="merchant fees", predicate="rise",
                qualifier=UNQUALIFIED,
                anchor="merchant fees rise 3.5%",
                value=Quantity(3.5, 0.5, "%"), value_text="3.5%",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            rig.extraction(
                evidence_ref=rb, subject="merchant fees", predicate="rise",
                qualifier=UNQUALIFIED,
                anchor="merchant fees rise 9.9%",
                value=Quantity(9.9, 0.5, "%"), value_text="9.9%",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert second.merged_into is None
        assert second.duplicates == ()  # NOT_EQUIVALENT: no link
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.NOT_EQUIVALENT
        }
        assert _fact_count(rig) == 2
        assert len(_active_facts(rig)) == 2

    def test_precision_governs_whether_equivalents_merge(self):
        # values within the coarser stated precision are EQUIVALENT and
        # MUST merge; outside it they MUST NOT
        rig = vendor_rig("src-a", "src-b", "src-c")
        ra = rig.acquire("src-a", VENDOR,
                         "Pricing: merchant fees rise 3.50% this year.")
        rb = rig.acquire("src-b", VENDOR,
                         "Pricing: merchant fees rise 3.60% this year.")
        rc = rig.acquire("src-c", VENDOR,
                         "Pricing: merchant fees rise 5.00% this year.")
        first = extract(
            rig.extraction(
                evidence_ref=ra, subject="merchant fees", predicate="rise",
                anchor="merchant fees rise 3.50%",
                value=Quantity(3.5, 0.5, "%"), value_text="3.50%",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        near = extract(
            rig.extraction(
                evidence_ref=rb, subject="merchant fees", predicate="rise",
                anchor="merchant fees rise 3.60%",
                value=Quantity(3.6, 0.5, "%"), value_text="3.60%",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        far = extract(
            rig.extraction(
                evidence_ref=rc, subject="merchant fees", predicate="rise",
                anchor="merchant fees rise 5.00%",
                value=Quantity(5.0, 0.5, "%"), value_text="5.00%",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert near.merged_into is not None      # |0.1| <= 0.5: merged
        assert far.merged_into is None           # 1.5 > 0.5: separate
        assert far.duplicates == ()
        canonical = rig.store.get_fact(near.object_id)
        assert canonical.attachment_count == 2

    def test_synonyms_separate_with_no_link(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR,
                         "Changelog A: sellers silently fail above 50 SKUs.")
        rb = rig.acquire("src-b", VENDOR,
                         "Changelog B: merchants silently fail above 50 SKUs.")
        first = extract(
            rig.extraction(
                evidence_ref=ra, subject="sellers",
                anchor="sellers silently fail above 50 SKUs",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        second = extract(
            rig.extraction(
                evidence_ref=rb, subject="merchants",
                anchor="merchants silently fail above 50 SKUs",
            ),
            store=rig.store, log=rig.log, clock=lambda: TICK,
        )
        assert second.merged_into is None
        assert second.duplicates == ()
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.NOT_EQUIVALENT
        }


# ---------------------------------------------------------------------------
# Replay, confidence, independence, anchors, density
# ---------------------------------------------------------------------------


class TestMergeDiscipline:
    def test_duplicate_attachment_replay_refused_and_recorded(self):
        rig = vendor_rig("src-a")
        ref = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        extract(rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        with pytest.raises(ExtractionRefusedError):
            extract(rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log, clock=lambda: TICK)
        failure = rig.log.for_evidence(ref)[-1]
        assert failure.stage is ExtractionStage.MERGE_FAILED
        assert failure.reason == "EVIDENCE_ALREADY_ATTACHED"
        assert failure.attempted
        # nothing changed: still one Fact object, one attachment
        assert _fact_count(rig) == 1
        assert rig.store.get_fact(
            _active_facts(rig)[0].object_id
        ).attachment_count == 1

    def test_v5_weak_source_lowers_the_rederived_ceiling(self):
        # R-3/V5: the merged version's support is min over the WIDENED
        # upstream set -- the weaker corroborating source governs, and
        # acceptance must PASS on the re-derived ceiling
        rig = vendor_rig("src-strong", "src-weak")
        ra = rig.acquire("src-strong", VENDOR, f"Changelog: {SPAN}.",
                         support=0.9)
        rb = rig.acquire("src-weak", VENDOR, f"Weak source: {SPAN}.",
                         support=0.3)
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        second = extract(rig.extraction(evidence_ref=rb),
                         store=rig.store, log=rig.log, clock=lambda: TICK)
        canonical = rig.store.get_fact(second.object_id)
        confidence = canonical.attributes.confidence
        assert confidence.evidential_support == pytest.approx(0.3)
        assert confidence.effective_confidence == pytest.approx(0.3)
        assert confidence.assertion_confidence == pytest.approx(0.8)
        # the merge was accepted (V5 held on the re-derived ceiling)
        assert second.merged_into == second.object_id

    def test_assertion_confidence_takes_the_more_conservative_extraction(self):
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig.extraction(evidence_ref=ra, extraction_confidence=0.9),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        second = extract(rig.extraction(evidence_ref=rb, extraction_confidence=0.6),
                         store=rig.store, log=rig.log, clock=lambda: TICK)
        canonical = rig.store.get_fact(second.object_id)
        assert canonical.attributes.confidence.assertion_confidence == (
            pytest.approx(0.6)
        )
        # and the mirror direction: the PREDECESSOR is the more
        # conservative side, and the merged version must keep its floor
        # rather than trusting the newer extraction's higher confidence
        rig2 = vendor_rig("src-a", "src-b")
        rc = rig2.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rd = rig2.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig2.extraction(evidence_ref=rc, extraction_confidence=0.6),
                store=rig2.store, log=rig2.log, clock=lambda: TICK)
        second2 = extract(
            rig2.extraction(evidence_ref=rd, extraction_confidence=0.9),
            store=rig2.store, log=rig2.log, clock=lambda: TICK)
        canonical2 = rig2.store.get_fact(second2.object_id)
        assert canonical2.attributes.confidence.assertion_confidence == (
            pytest.approx(0.6)
        )

    def test_independence_is_never_inferred_by_merging(self):
        # N-16: merged attachments start UNASSESSED and the independent
        # count must not move -- corroboration is not independence
        rig = vendor_rig("src-a", "src-b", "src-c")
        refs = [rig.acquire(n, VENDOR, f"{n}: {SPAN}.")
                for n in ("src-a", "src-b", "src-c")]
        for i, ref in enumerate(refs):
            extract(rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log,
                    clock=lambda: TICK + timedelta(seconds=i))
        head_ref = refs[-1]
        canonical = rig.store.get_fact(
            [o for o in _active_facts(rig)][0].object_id
        ) if False else _active_facts(rig)[0]
        assert canonical.attachment_count == 3
        assert canonical.independent_source_count == 1  # never inflated
        assert all(
            a.independence_assessment is Independence.UNASSESSED
            for a in canonical.attachments
        )

    def test_merged_attachment_anchor_registered_and_resolvable(self):
        # T03.1.3 invariant on the merge path: the accepted attachment's
        # anchor is registered and mechanically resolvable
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        register = PositionalAnchorRegister()
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK,
                anchors=register)
        second = extract(rig.extraction(evidence_ref=rb),
                         store=rig.store, log=rig.log, clock=lambda: TICK,
                         anchors=register)
        locator = register.locator_for(rb, SPAN)
        assert locator is not None
        content = rig.store.get_evidence(rb).content.content
        assert resolve_locator(content, locator) == SPAN
        canonical = rig.store.get_fact(second.object_id)
        attachment = canonical.attachment_for(rb)
        assert attachment.positional_anchor == SPAN
        assert content.count(attachment.positional_anchor) == 1

    def test_density_counts_active_versions_only(self):
        # T03.1.4: superseded versions are not double-counted
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        extract(rig.extraction(evidence_ref=rb),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        report = build_density_report(rig.store, rig.log)
        assert report.total_claims == 2  # not 3 (2 versions + 1 superseded)
        assert all(row.claims == 1 for row in report.rows)

    def test_merge_failure_projection_reaches_the_failure_store(self):
        from oip.configuration import FailureStore as FS

        rig = vendor_rig("src-a")
        ref = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        failure_store = FS()
        rig.log.attach(failure_store)
        extract(rig.extraction(evidence_ref=ref),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        with pytest.raises(ExtractionRefusedError):
            extract(rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log, clock=lambda: TICK)
        assert len(failure_store) > 0

    def test_merge_failed_is_an_attempted_stage(self):
        assert ExtractionStage.MERGE_FAILED in _ATTEMPTED_STAGES

    def test_merge_not_possible_recorded_and_canonical_unchanged(self):
        # wiring proof for the store-side guard: an allocator refusal
        # (e.g. a concurrent merge's branching refusal) is recorded,
        # attempted, and leaves the canonical untouched
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        canonical_id = _active_facts(rig)[0].object_id
        original = rig.store.allocator.succeed

        def refusing_succeed(predecessor):
            raise RuntimeError("simulated concurrent-merge branching")

        rig.store.allocator.succeed = refusing_succeed  # type: ignore[
        try:
            with pytest.raises(ExtractionRefusedError):
                extract(rig.extraction(evidence_ref=rb),
                        store=rig.store, log=rig.log, clock=lambda: TICK)
        finally:
            rig.store.allocator.succeed = original  # type: ignore[
        failure = rig.log.for_evidence(rb)[-1]
        assert failure.stage is ExtractionStage.MERGE_FAILED
        assert failure.reason == "MERGE_NOT_POSSIBLE"
        assert failure.attempted
        # the canonical was never superseded: still ACTIVE, 1 attachment
        assert rig.store.find(canonical_id).status is ObjectStatus.ACTIVE
        assert rig.store.get_fact(canonical_id).attachment_count == 1

    def test_acceptance_refusal_records_the_orphaned_supersession(self):
        # T03.1.4 supersedes the interim "restore to ACTIVE" contract.
        # PROVENANCE: the restore design was impossible -- SUPERSEDED is
        # a TERMINAL state under R-2 (oip/enums.py _TERMINAL_STATES), so
        # once I5 forces transition-then-write, a post-supersession
        # write failure cannot be undone. The honest contract is: the
        # refusal is recorded naming the exact surviving state (canonical
        # SUPERSEDED with its attachments intact, no successor), nothing
        # silent, data intact and auditable [N-10]. The write-failure
        # surface is structurally closed (V5 re-derived ceiling, V11
        # allocator consistency, V12 no DUPLICATES, no cycles from
        # Evidence references); this test exercises the defensive path
        # via a stub.
        from oip.store import WriteRejectedError

        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        failure_store = FailureStore()
        rig.log.attach(failure_store)
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        canonical_id = _active_facts(rig)[0].object_id
        original = rig.store.write_fact

        def refusing_write(fact, predecessor_id=None):
            if predecessor_id is not None:  # only the MERGED write

                class _StubFailure:
                    object_id = "obj-stub"
                    rule_ids = ["V5"]

                raise WriteRejectedError(_StubFailure())
            return original(fact)

        rig.store.write_fact = refusing_write  # type: ignore[method-assign]
        try:
            with pytest.raises(ExtractionRefusedError):
                extract(rig.extraction(evidence_ref=rb),
                        store=rig.store, log=rig.log, clock=lambda: TICK)
        finally:
            rig.store.write_fact = original  # type: ignore[method-assign]
        failure = rig.log.for_evidence(rb)[-1]
        assert failure.stage is ExtractionStage.MERGE_FAILED
        assert failure.reason == "ACCEPTANCE_REFUSED"
        assert failure.attempted
        assert "SUPERSEDED" in failure.detail
        assert "no successor" in failure.detail
        # the canonical is terminal with every attachment it had, and no
        # successor exists: the state the detail names is the real state
        assert rig.store.find(canonical_id).status is ObjectStatus.SUPERSEDED
        assert rig.store.get_fact(canonical_id).attachment_count == 1
        assert _active_facts(rig) == []
        assert len(failure_store) > 0

    def test_merged_version_registry_gap_reports_refusal(self):
        # wiring proof: a lost payload after an accepted merge is a
        # recorded refusal, never a phantom success [N-10]
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        extract(rig.extraction(evidence_ref=ra),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        original = rig.store.get_fact
        rig.store.get_fact = lambda _id: None  # type: ignore[method-assign]
        try:
            with pytest.raises(ExtractionRefusedError):
                extract(rig.extraction(evidence_ref=rb),
                        store=rig.store, log=rig.log, clock=lambda: TICK)
        finally:
            rig.store.get_fact = original  # type: ignore[method-assign]
        failure = rig.log.for_evidence(rb)[-1]
        assert failure.stage is ExtractionStage.MERGE_FAILED
        assert failure.reason == "REGISTRY_GAP"
        assert failure.attempted

    def test_single_extraction_never_reports_a_merge(self):
        rig = vendor_rig("src-a")
        ref = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        outcome = extract(rig.extraction(evidence_ref=ref),
                          store=rig.store, log=rig.log, clock=lambda: TICK)
        assert outcome.merged_into is None
        assert outcome.duplicates == ()


# ---------------------------------------------------------------------------
# Version-chain and concurrency invariants
# ---------------------------------------------------------------------------


class TestVersionChainInvariants:
    def test_integrity_clean_after_merges(self):
        rig = vendor_rig("src-a", "src-b", "src-c")
        refs = [rig.acquire(n, VENDOR, f"{n}: {SPAN}.")
                for n in ("src-a", "src-b", "src-c")]
        for i, ref in enumerate(refs):
            extract(rig.extraction(evidence_ref=ref),
                    store=rig.store, log=rig.log,
                    clock=lambda: TICK + timedelta(seconds=i))
        assert not rig.store.facts.integrity().verify()

    def test_predecessor_attachment_never_removed(self):
        # F-I2 spot check through the public merge path
        rig = vendor_rig("src-a", "src-b")
        ra = rig.acquire("src-a", VENDOR, f"Changelog: {SPAN}.")
        rb = rig.acquire("src-b", VENDOR, f"Forum: {SPAN}.")
        first = extract(rig.extraction(evidence_ref=ra),
                        store=rig.store, log=rig.log, clock=lambda: TICK)
        predecessor = rig.store.get_fact(first.object_id)
        extract(rig.extraction(evidence_ref=rb),
                store=rig.store, log=rig.log, clock=lambda: TICK)
        after = rig.store.get_fact(first.object_id)
        assert after.attachments == predecessor.attachments
        assert after.claim == predecessor.claim

    def test_concurrent_merges_keep_integrity_and_record(self):
        # N-11: concurrent acquisition/merging permitted. Racing merges
        # resolve conservatively: one merges, the rest either merge into
        # the moving head, land as separate Facts with DUPLICATES, or
        # refuse with a recorded MERGE_FAILED. Nothing is ever corrupt.
        rig = vendor_rig(*tuple(f"src-{i}" for i in range(6)))
        refs = [rig.acquire(f"src-{i}", VENDOR, f"src-{i}: {SPAN}.")
                for i in range(6)]
        outcomes: list = []
        failures: list = []
        lock = threading.Lock()

        def run(i: int) -> None:
            try:
                outcome = extract(
                    rig.extraction(evidence_ref=refs[i]),
                    store=rig.store, log=rig.log,
                    clock=lambda: TICK + timedelta(seconds=i),
                )
                with lock:
                    outcomes.append(outcome)
            except ExtractionRefusedError:
                with lock:
                    failures.append(rig.log.for_evidence(refs[i])[-1])

        threads = [threading.Thread(target=run, args=(i,)) for i in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # every refusal is a recorded, attempted merge failure
        assert all(
            f.stage is ExtractionStage.MERGE_FAILED and f.attempted
            for f in failures
        ), [(f.stage, f.reason) for f in failures]
        # the store is consistent: integrity clean, at least one ACTIVE
        # canonical
        violations = rig.store.facts.integrity().verify()
        assert not violations, violations
        active = _active_facts(rig)
        assert len(active) >= 1
        # every SUCCESSFUL extraction's Evidence is attached to exactly
        # one ACTIVE Fact -- never lost, never duplicated across Facts;
        # recorded refusals contributed nothing
        attached_refs = [
            a.evidence_ref for f in active for a in f.attachments
        ]
        assert sorted(attached_refs) == sorted(
            o.evidence_ref for o in outcomes
        ), f"attached={sorted(attached_refs)} vs successful="
        f"{sorted(o.evidence_ref for o in outcomes)}" 
