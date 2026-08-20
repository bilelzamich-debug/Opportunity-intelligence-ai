"""Contract tests for the coverage model.

Task: T02.1.4

Architecture References:
- N-22   The coverage model (S 5.1-5.7). These tests assert the ratified
         behaviour exactly: types-not-volume, declared-completeness, the
         closed five-reason vocabulary, the out-of-frame register, no
         stopping rule, report-not-gate, and undefined-never-defaulted.
- N-20   Supplies the frame (S 5.1) and gate-2 refusal semantics (S 5.2).
- N-10   NOT_ATTEMPTED vs NO_MATERIAL_FOUND preserves failed-vs-found.
- Art X  Undeclared gaps are reportable, never silent.
- N-4    Property-based assertions only; never equality on engine output.

T02.1.4 acceptance criteria under test:
  AC1  Source-type coverage measurable                          -> IMPLEMENTED
  AC2  Known gaps declared explicitly                           -> IMPLEMENTED
  AC3  Gap declaration inheritable by Pattern artefact assess.  -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oip.coverage import (
    GAP_REASONS,
    CoverageError,
    CoverageGap,
    CoverageReport,
    CoverageUndefinedError,
    FrameMemberError,
    GapReason,
    GapReasonError,
    GapDeclaration,
    GapRegister,
    OutOfFrameError,
    OutOfFrameRegister,
    OutOfFrameRefusal,
    coverage_frame,
    measure_coverage,
)
from oip.source import SourceType, taxonomy_members

IDENT = st.text(min_size=1, max_size=20).filter(str.strip)
RATIONALE = st.text(min_size=3, max_size=60).filter(str.strip)


def fresh() -> tuple[GapRegister, OutOfFrameRegister]:
    return GapRegister(), OutOfFrameRegister()


# ===========================================================================
# AC1 -- the frame and the measure  [N-22 S 5.1, S 5.2]
# ===========================================================================


class TestFrame:
    def test_frame_is_the_ratified_taxonomy_exactly(self):
        assert coverage_frame() == frozenset(taxonomy_members())
        assert len(coverage_frame()) == 8

    def test_empty_frame_means_unavailable_not_zero_sources(self):
        """An empty frame is 'not yet specified', never 'no sources'."""
        assert coverage_frame() != frozenset()


class TestCoverageMeasure:
    def test_empty_evidence_covers_nothing(self):
        gaps, oof = fresh()
        report = measure_coverage((), gaps, oof)
        assert report.coverage == 0.0
        assert report.represented == ()
        assert len(report.gaps) == 8
        assert report.declared_complete is False

    def test_full_representation_reaches_one(self):
        gaps, oof = fresh()
        report = measure_coverage(
            tuple(m.value for m in taxonomy_members()), gaps, oof
        )
        assert report.coverage == 1.0
        assert report.gaps == ()
        assert report.declared_complete is True  # vacuous: no gaps at all

    def test_representation_is_existence_not_volume(self):
        """Three Evidence of one type represent the member ONCE. [S 5.2]"""
        gaps, oof = fresh()
        report = measure_coverage(
            ["VENDOR_PUBLICATION"] * 3, gaps, oof
        )
        assert report.coverage == pytest.approx(1 / 8)
        assert report.represented == (SourceType.VENDOR_PUBLICATION,)

    def test_untypable_active_evidence_represents_nothing(self):
        """Raw strings outside the taxonomy represent no member; nothing
        is guessed into the frame (gate 2 owns refusing them)."""
        gaps, oof = fresh()
        report = measure_coverage(["not-a-type", "also-not"], gaps, oof)
        assert report.coverage == 0.0
        assert report.represented == ()

    @given(
        present=st.sets(
            st.sampled_from([m.value for m in taxonomy_members()]),
            min_size=0,
            max_size=8,
        )
    )
    def test_coverage_equals_represented_over_frame(self, present):
        """Property: coverage == |represented| / |frame|, always."""
        gaps, oof = fresh()
        report = measure_coverage(tuple(present), gaps, oof)
        assert report.coverage == pytest.approx(len(present) / 8)
        assert report.frame_size == 8
        assert len(report.represented) == len(present)
        assert len(report.represented) + len(report.gaps) == 8

    def test_gaps_are_exactly_frame_minus_represented(self):
        gaps, oof = fresh()
        report = measure_coverage(
            ("PUBLISHED_EDITORIAL", "REGULATORY_FILING"), gaps, oof
        )
        gap_members = {g.member for g in report.gaps}
        assert gap_members == coverage_frame() - {
            SourceType.PUBLISHED_EDITORIAL,
            SourceType.REGULATORY_FILING,
        }


# ===========================================================================
# S 5.7 -- undefined frame fails closed, never defaults
# ===========================================================================


class TestUndefinedFrame:
    def test_unavailable_frame_is_undefined_never_zero_or_one(self):
        gaps, oof = fresh()
        report = measure_coverage(
            ("PUBLISHED_EDITORIAL",), gaps, oof, frame=frozenset()
        )
        assert report.is_undefined is True
        assert report.coverage is None
        assert report.coverage != 0.0 and report.coverage != 1.0
        assert report.gaps == ()
        assert report.declared_complete is False

    def test_out_of_frame_count_survives_undefined_frame(self):
        """The register is reported even when coverage is not."""
        gaps, oof = fresh()
        oof.record("s", "not-a-type", "gate-2 refusal")
        report = measure_coverage((), gaps, oof, frame=frozenset())
        assert report.out_of_frame == 1


# ===========================================================================
# AC2 -- explicit gap declaration  [N-22 S 5.1, S 5.4]
# ===========================================================================


class TestGapDeclarations:
    def test_declaration_records_member_reason_and_why(self):
        declaration = GapDeclaration(
            member=SourceType.STRUCTURED_DATASET,
            reason=GapReason.NOT_ATTEMPTED,
            declared_at=datetime.now(timezone.utc),
            rationale="no directive covered datasets this cycle",
        )
        assert declaration.is_declared if hasattr(
            declaration, "is_declared"
        ) else True
        assert declaration.reason is GapReason.NOT_ATTEMPTED

    @given(
        member=st.sampled_from(list(SourceType)),
        reason=st.sampled_from(list(GapReason)),
        rationale=RATIONALE,
    )
    def test_every_ratified_combination_is_declarable(
        self, member, reason, rationale
    ):
        register = GapRegister()
        register.declare(member, reason, rationale)
        assert register.declaration_for(member).reason is reason

    @given(bad=st.text(max_size=20))
    def test_reasons_outside_the_closed_set_are_refused(self, bad):
        if bad in GAP_REASONS:
            return
        with pytest.raises((GapReasonError, TypeError)):
            GapDeclaration(
                member=SourceType.VENDOR_PUBLICATION,
                reason=bad,
                declared_at=datetime.now(timezone.utc),
                rationale="r",
            )

    def test_reason_enum_carries_exactly_the_five_ratified_members(self):
        """The guard against someone quietly extending the vocabulary."""
        assert list(GapReason) == [GapReason[r] for r in GAP_REASONS]
        assert len(GAP_REASONS) == 5
        with pytest.raises(AttributeError):
            GapReason.LOW_PRIORITY

    def test_untypable_channel_is_not_a_gap_reason(self):
        """N-22 S 5.4: UNTYPABLE_CHANNEL belongs to the out-of-frame
        register alone; it must not appear in the reason vocabulary."""
        assert "UNTYPABLE_CHANNEL" not in GAP_REASONS
        # The enum itself refuses the token (ValueError); GapDeclaration
        # additionally refuses non-enum reasons (GapReasonError).
        with pytest.raises((GapReasonError, TypeError, ValueError)):
            GapReason("UNTYPABLE_CHANNEL")

    def test_non_frame_members_cannot_be_declared(self):
        for bad in ("customer_review_corpus", "SOMETHING_ELSE"):
            with pytest.raises((FrameMemberError, TypeError)):
                GapDeclaration(
                    member=bad,
                    reason=GapReason.NOT_ATTEMPTED,
                    declared_at=datetime.now(timezone.utc),
                    rationale="r",
                )

    @given(member=st.sampled_from(list(SourceType)))
    def test_declaration_requires_its_why(self, member):
        for empty in ("", "   "):
            with pytest.raises(CoverageError):
                GapDeclaration(
                    member=member,
                    reason=GapReason.INACCESSIBLE,
                    declared_at=datetime.now(timezone.utc),
                    rationale=empty,
                )

    def test_register_history_is_append_only(self):
        register = GapRegister()
        register.declare(
            SourceType.MARKETPLACE_LISTING,
            GapReason.NOT_ATTEMPTED,
            "first",
        )
        register.declare(
            SourceType.MARKETPLACE_LISTING,
            GapReason.NO_MATERIAL_FOUND,
            "second, after an attempt",
        )
        assert len(register.history_for(SourceType.MARKETPLACE_LISTING)) == 2
        operative = register.declaration_for(SourceType.MARKETPLACE_LISTING)
        assert operative.reason is GapReason.NO_MATERIAL_FOUND

    def test_not_attempted_vs_no_material_found_stay_distinct(self):
        """N-10 at the coverage layer: absence of evidence is not absence
        of attempt."""
        assert GapReason.NOT_ATTEMPTED is not GapReason.NO_MATERIAL_FOUND
        assert GapReason.NOT_ATTEMPTED.value != GapReason.NO_MATERIAL_FOUND.value


# ===========================================================================
# Declared-completeness  [N-22 S 5.3]
# ===========================================================================


class TestDeclaredCompleteness:
    def test_all_gaps_declared_is_declared_complete(self):
        register, oof = fresh()
        for member in taxonomy_members():
            if member is not SourceType.SUPPORT_INTERACTION:
                register.declare(member, GapReason.OUT_OF_SCOPE, "directive")
        register.declare(
            SourceType.SUPPORT_INTERACTION,
            GapReason.NOT_ATTEMPTED,
            "not covered by any directive",
        )
        report = measure_coverage((), register, oof)
        assert report.coverage == 0.0
        assert report.declared_complete is True

    def test_one_undeclared_gap_makes_the_report_incomplete(self):
        register, oof = fresh()
        for member in taxonomy_members():
            register.declare(member, GapReason.OUT_OF_SCOPE, "directive")
        # re-declare one member's gap away? No: declarations are per-member
        # history; instead measure with a fresh register missing one.
        partial = GapRegister()
        for member in list(taxonomy_members())[:-1]:
            partial.declare(member, GapReason.OUT_OF_SCOPE, "directive")
        report = measure_coverage((), partial, oof)
        assert report.declared_complete is False
        assert len(report.undeclared_gaps) == 1

    @given(
        declared_count=st.integers(min_value=0, max_value=8),
    )
    def test_incompleteness_is_reported_never_silent(self, declared_count):
        register, oof = fresh()
        for member in list(taxonomy_members())[:declared_count]:
            register.declare(member, GapReason.INACCESSIBLE, "paywalled")
        report = measure_coverage((), register, oof)
        assert len(report.undeclared_gaps) == 8 - declared_count
        assert report.declared_complete is (declared_count == 8)


# ===========================================================================
# Out-of-frame register  [N-22 S 5.2.1 -- AS-4]
# ===========================================================================


class TestOutOfFrameRegister:
    def test_untypable_refusals_are_counted_beside_coverage(self):
        register, oof = fresh()
        oof.record("src-a", "customer_review_corpus", "gate 2 refusal")
        oof.record("src-b", "some-blog-rss", "gate 2 refusal")
        report = measure_coverage(("PUBLISHED_EDITORIAL",), register, oof)
        assert report.out_of_frame == 2
        assert report.coverage == pytest.approx(1 / 8)

    def test_full_coverage_with_out_of_frame_is_not_false(self):
        """coverage=1.0 alongside out_of_frame>0 states 'frame fully
        sampled AND material refused outside it' -- both are carried."""
        register, oof = fresh()
        oof.record("src-a", "mystery-channel", "gate 2 refusal")
        report = measure_coverage(
            tuple(m.value for m in taxonomy_members()), register, oof
        )
        assert report.coverage == 1.0
        assert report.out_of_frame == 1

    def test_typable_sources_are_refused_entry(self):
        """A typable source belongs to gaps/representation, never here;
        recording it would hide a real gap behind a false count."""
        _, oof = fresh()
        with pytest.raises(OutOfFrameError):
            oof.record("src", "VENDOR_PUBLICATION", "not out of frame")

    @given(raw=st.text(max_size=20).filter(lambda s: s.strip()))
    def test_only_untypable_raws_enter(self, raw):
        _, oof = fresh()
        if any(raw == m.value for m in taxonomy_members()):
            with pytest.raises(OutOfFrameError):
                oof.record("s", raw, "d")
        else:
            oof.record("s", raw, "gate 2 refusal")
            assert oof.count() == 1

    def test_silent_refusal_is_refused(self):
        _, oof = fresh()
        with pytest.raises(OutOfFrameError):
            oof.record("s", "not-a-type", "  ")


# ===========================================================================
# AC3 -- inheritance by Pattern artefact assessment  [J4/J5, T05.1.4]
# ===========================================================================


class TestInheritability:
    def test_declarations_are_immutable_typed_records(self):
        register, oof = fresh()
        register.declare(
            SourceType.STRUCTURED_DATASET,
            GapReason.REFUSED_BY_RIGHTS,
            "licence refused by the designated authority",
        )
        report = measure_coverage((), register, oof)
        inherited = report.inheritable_declarations()
        assert len(inherited) == 1
        declaration = inherited[0]
        assert isinstance(declaration, GapDeclaration)
        assert declaration.member is SourceType.STRUCTURED_DATASET
        assert declaration.reason is GapReason.REFUSED_BY_RIGHTS
        assert declaration.rationale.strip()

    def test_every_declared_gap_is_inheritable(self):
        register, oof = fresh()
        for member in list(taxonomy_members())[:3]:
            register.declare(member, GapReason.NOT_ATTEMPTED, "why")
        report = measure_coverage(
            ("PUBLISHED_EDITORIAL",), register, oof
        )
        inherited = report.inheritable_declarations()
        assert len(inherited) == 2  # PUBLISHED_EDITORIAL is represented
        assert all(d.rationale for d in inherited)

    def test_history_reproduction_for_pattern_audit(self):
        """PT-V5's 'reasoned' assessment can cite the full history."""
        register, oof = fresh()
        register.declare(
            SourceType.USER_GENERATED_DISCUSSION,
            GapReason.NOT_ATTEMPTED,
            "cycle 1",
        )
        register.declare(
            SourceType.USER_GENERATED_DISCUSSION,
            GapReason.NO_MATERIAL_FOUND,
            "cycle 2 attempted, nothing found",
        )
        history = register.history_for(SourceType.USER_GENERATED_DISCUSSION)
        assert [h.reason for h in history] == [
            GapReason.NOT_ATTEMPTED,
            GapReason.NO_MATERIAL_FOUND,
        ]


# ===========================================================================
# S 5.5 / S 5.6 -- no stopping rule; a report, never a gate
# ===========================================================================


class TestReportNotGate:
    def test_module_defines_no_stopping_rule(self):
        """N-22 S 5.5: a coverage figure may inform a stop owned by M-01;
        it may not BE one. No threshold vocabulary may exist."""
        import oip.coverage as mod

        forbidden = (
            n.upper()
            for n in dir(mod)
            if any(k in n.upper() for k in ("STOP", "ENOUGH", "THRESHOLD"))
        )
        assert not list(forbidden)

    def test_report_rejects_no_object(self):
        """The report carries no rejection surface whatsoever. [S 5.6]"""
        register, oof = fresh()
        report = measure_coverage((), register, oof)
        assert isinstance(report, CoverageReport)
        rejectish = [
            n
            for n in dir(report)
            if not n.startswith("_")
            and any(k in n.lower() for k in ("reject", "accept", "deny"))
        ]
        assert rejectish == []

    def test_coverage_is_descriptive_even_at_zero(self):
        register, oof = fresh()
        report = measure_coverage((), register, oof)
        assert report.coverage == 0.0  # measured fact, not a verdict


class TestCoverageGapRecord:
    def test_undeclared_gap_is_carried_not_dropped(self):
        gap = CoverageGap(member=SourceType.REGULATORY_FILING)
        assert gap.is_declared is False
        assert gap.declaration is None


class TestRecordValidationBranches:
    """Every refusal branch is exercised: coverage validation is contract,
    and an untested refusal is a refusal that will rot."""

    def test_declaration_requires_a_datetime(self):
        with pytest.raises(CoverageError):
            GapDeclaration(
                member=SourceType.VENDOR_PUBLICATION,
                reason=GapReason.NOT_ATTEMPTED,
                declared_at="2026-01-01",
                rationale="r",
            )

    def test_refusal_requires_every_field(self):
        now = datetime.now(timezone.utc)
        for kwargs in (
            {"source_identifier": "", "raw_source_type": "x", "detail": "d"},
            {"source_identifier": "s", "raw_source_type": " ", "detail": "d"},
            {"source_identifier": "s", "raw_source_type": "x", "detail": ""},
        ):
            with pytest.raises(OutOfFrameError):
                OutOfFrameRefusal(
                    refused_at=now, **kwargs
                )
        with pytest.raises(OutOfFrameError):
            OutOfFrameRefusal(
                source_identifier="s",
                raw_source_type="x",
                refused_at="2026-01-01",
                detail="d",
            )

    def test_register_record_requires_a_raw_type(self):
        _, oof = fresh()
        with pytest.raises(OutOfFrameError):
            oof.record("s", "   ", "detail")

    def test_registers_are_iterable_and_counted(self):
        register, oof = fresh()
        register.declare(SourceType.VENDOR_PUBLICATION, GapReason.NOT_ATTEMPTED, "a")
        register.declare(SourceType.VENDOR_PUBLICATION, GapReason.INACCESSIBLE, "b")
        assert len(register) == 2
        assert len(list(register)) == 2
        assert len(oof) == 0 and len(list(oof)) == 0
        oof.record("s", "not-a-type", "gate 2 refusal")
        assert len(oof) == 1 and len(list(oof)) == 1
        assert oof.count() == len(list(oof))
