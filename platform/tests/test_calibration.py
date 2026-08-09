"""Contract tests for calibration rubric conformance.

Task: T01.5.5

Architecture References:
- S-1    Confidence Calibration Rubric (closes M-60). Five bands with exact
         ranges, an observable criterion and a test each, plus ten worked
         anchors. "The operative test is alternative-counting, not
         introspection." "Until O2 data exists, comparability is argued, not
         demonstrated."
- S-1 Known Tensions: "only `assertion_confidence` is governed by this
         rubric"; evidential_support uses a separate computation (M-59)
- R-3    Two-component confidence; five mandatory band labels; the engine
         asserts assertion_confidence
- N-3    Measure O2 (calibration) is the empirical correction, from P8
- B-05   Shared rubric + anchors for P1; post-hoc empirical calibration later
- N-4    Calibration is statistical rather than exact
- R-1    Historical values are reinterpreted through a recorded offset, never
         rewritten
- IOM 2.3 Per-stage assertion bases are "indicative only, not thresholds"
- T01.5.1 ConfidenceBand / Confidence already realise R-3's bands
- T08.3.5 Empirical recalibration (P8) must retain prior calibration for
         comparison, so every assessment names its rubric

Acceptance criteria under test:
  AC1  Rubric bands referenced at assertion
  AC2  Deviations recorded
  AC3  Cross-engine comparison documented as rubric-dependent
"""

from __future__ import annotations

import ast
import dataclasses
import math
import threading
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.calibration import (
    CALIBRATION_RUBRIC,
    COMPARABILITY_PROPERTIES,
    COMPARABILITY_QUALIFICATION,
    GOVERNED_COMPONENT,
    RUBRIC_ID,
    RUBRIC_RATIFIED,
    UNASSESSED_NO_COUNT,
    UNASSESSED_QUALITATIVE_BAND,
    UNGOVERNED_COMPONENTS,
    BandCriterion,
    CalibrationAssessment,
    CalibrationDeviation,
    CalibrationError,
    CalibrationRegister,
    ConformanceOutcome,
    CrossEngineComparison,
    UngovernedComponentError,
    assess_assertion,
    compare_across_engines,
    criterion_for_band,
    criterion_for_value,
    rubric_matches_band_boundaries,
)
from oip.contract import Confidence
from oip.enums import ConfidenceBand, Engine

COUNTABLE = (ConfidenceBand.WEAK, ConfidenceBand.MODERATE,
             ConfidenceBand.VERY_STRONG)
QUALITATIVE = (ConfidenceBand.NEGLIGIBLE, ConfidenceBand.STRONG)


# ---------------------------------------------------------------------------
# The rubric reproduces S-1 exactly
# ---------------------------------------------------------------------------

class TestRubricMatchesS1:
    def test_exactly_five_bands(self):
        assert len(CALIBRATION_RUBRIC) == 5
        assert [c.band for c in CALIBRATION_RUBRIC] == list(ConfidenceBand)

    @pytest.mark.parametrize(
        "band,low,high",
        [
            (ConfidenceBand.NEGLIGIBLE, 0.00, 0.19),
            (ConfidenceBand.WEAK, 0.20, 0.39),
            (ConfidenceBand.MODERATE, 0.40, 0.59),
            (ConfidenceBand.STRONG, 0.60, 0.79),
            (ConfidenceBand.VERY_STRONG, 0.80, 1.00),
        ],
    )
    def test_ranges_are_s1s(self, band, low, high):
        criterion = criterion_for_band(band)
        assert (criterion.low, criterion.high) == (low, high)

    def test_ranges_agree_with_the_implemented_boundaries(self):
        """A divergence would govern an assertion by the wrong criterion."""
        assert rubric_matches_band_boundaries() is True

    def test_every_band_has_criterion_test_and_two_anchors(self):
        for criterion in CALIBRATION_RUBRIC:
            assert criterion.criterion.strip()
            assert criterion.test.strip()
            assert criterion.anchor_a.strip()
            assert criterion.anchor_b.strip()
            assert criterion.anchor_a != criterion.anchor_b

    def test_ten_distinct_anchors(self):
        anchors = [
            a for c in CALIBRATION_RUBRIC for a in (c.anchor_a, c.anchor_b)
        ]
        assert len(anchors) == 10
        assert len(set(anchors)) == 10

    def test_criteria_are_quoted_verbatim_from_s1(self):
        source = " ".join(
            (Path(__file__).resolve().parents[2] / "decisions"
             / "S-01-calibration-rubric.md").read_text().split()
        )
        for criterion in CALIBRATION_RUBRIC:
            assert " ".join(criterion.criterion.split()) in source
            assert " ".join(criterion.anchor_a.split()) in source
            assert " ".join(criterion.anchor_b.split()) in source

    def test_counts_only_where_s1_states_a_countable_test(self):
        """NEGLIGIBLE and STRONG are qualitative; a count would be invented."""
        counts = {c.band: c.alternative_count for c in CALIBRATION_RUBRIC}
        assert counts[ConfidenceBand.VERY_STRONG] == 0
        assert counts[ConfidenceBand.MODERATE] == 1
        assert counts[ConfidenceBand.WEAK] == 2
        assert counts[ConfidenceBand.NEGLIGIBLE] is None
        assert counts[ConfidenceBand.STRONG] is None

    def test_only_weak_is_a_minimum(self):
        for criterion in CALIBRATION_RUBRIC:
            assert criterion.count_is_minimum is (
                criterion.band is ConfidenceBand.WEAK
            )

    def test_countable_bands_are_exactly_three(self):
        assert {c.band for c in CALIBRATION_RUBRIC if c.is_countable} == set(
            COUNTABLE
        )

    def test_the_rubric_is_immutable(self):
        assert isinstance(CALIBRATION_RUBRIC, tuple)
        with pytest.raises(dataclasses.FrozenInstanceError):
            CALIBRATION_RUBRIC[0].criterion = "tampered"  # type: ignore[misc]

    def test_rubric_identity_is_recorded(self):
        assert RUBRIC_ID == "S-1"
        assert RUBRIC_RATIFIED == "2026-08-02"

    def test_bands_do_not_overlap_and_leave_no_printed_gap(self):
        ordered = sorted(CALIBRATION_RUBRIC, key=lambda c: c.low)
        assert ordered[0].low == 0.00
        assert ordered[-1].high == 1.00
        for lower, upper in zip(ordered, ordered[1:]):
            assert lower.high < upper.low
            assert round(upper.low - lower.high, 2) == 0.01


# ---------------------------------------------------------------------------
# AC1 -- rubric bands referenced at assertion
# ---------------------------------------------------------------------------

class TestBandsReferencedAtAssertion:
    def test_an_assertion_resolves_to_its_band(self):
        assert assess_assertion(0.85).band is ConfidenceBand.VERY_STRONG
        assert assess_assertion(0.05).band is ConfidenceBand.NEGLIGIBLE

    def test_an_assertion_carries_the_observable_criterion(self):
        assessment = assess_assertion(0.85)
        assert assessment.criterion.band is ConfidenceBand.VERY_STRONG
        assert "only reading the inputs support" in assessment.criterion.criterion
        assert assessment.criterion.test

    def test_an_assertion_carries_the_worked_anchors(self):
        assessment = assess_assertion(0.30)
        assert assessment.criterion.anchor_a
        assert assessment.criterion.anchor_b

    def test_an_assertion_names_the_rubric_that_governed_it(self):
        """T08.3.5 must retain prior calibration for comparison."""
        assessment = assess_assertion(0.5)
        assert assessment.rubric_id == "S-1"
        assert assessment.rubric_ratified == "2026-08-02"

    def test_an_assertion_names_the_component_governed(self):
        assert assess_assertion(0.5).component == "assertion_confidence"

    @pytest.mark.parametrize("band", list(ConfidenceBand))
    def test_every_band_is_reachable_by_reference(self, band):
        criterion = criterion_for_band(band)
        assert criterion_for_value(criterion.low).band is band

    def test_criterion_lookup_refuses_a_non_band(self):
        for bad in ("STRONG", None, 5):
            with pytest.raises(CalibrationError):
                criterion_for_band(bad)

    def test_contains_agrees_with_the_authoritative_band(self):
        """S-1's printed 2dp ranges leave gaps; contains() must not."""
        for value in (0.195, 0.199, 0.395, 0.599, 0.799):
            criterion = criterion_for_value(value)
            assert criterion.contains(value) is True

    def test_contains_is_exclusive_across_bands(self):
        for step in range(0, 1001):
            value = step / 1000
            holding = [c for c in CALIBRATION_RUBRIC if c.contains(value)]
            assert len(holding) == 1, value

    def test_contains_rejects_out_of_range(self):
        criterion = criterion_for_value(0.5)
        assert criterion.contains(1.5) is False
        assert criterion.contains(-0.1) is False


# ---------------------------------------------------------------------------
# AC2 -- deviations recorded
# ---------------------------------------------------------------------------

class TestConformanceAssessment:
    @pytest.mark.parametrize(
        "value,count",
        [(0.85, 0), (1.00, 0), (0.50, 1), (0.40, 1), (0.30, 2), (0.20, 5)],
    )
    def test_a_matching_count_is_conformant(self, value, count):
        assessment = assess_assertion(value, alternative_count=count)
        assert assessment.outcome is ConformanceOutcome.CONFORMANT
        assert assessment.conformant is True
        assert assessment.deviated is False

    @pytest.mark.parametrize(
        "value,count",
        [(0.85, 1), (0.85, 2), (0.50, 0), (0.50, 3), (0.30, 0), (0.30, 1)],
    )
    def test_a_mismatched_count_is_a_deviation(self, value, count):
        assessment = assess_assertion(value, alternative_count=count)
        assert assessment.outcome is ConformanceOutcome.DEVIATION
        assert assessment.deviated is True
        assert "S-1" in assessment.detail

    def test_a_deviation_names_the_band_the_count_implies(self):
        assessment = assess_assertion(0.85, alternative_count=1)
        assert assessment.expected_band is ConfidenceBand.MODERATE
        assert assessment.band is ConfidenceBand.VERY_STRONG

    def test_expected_band_is_unique_for_every_count(self):
        for count in range(0, 25):
            matching = [
                c.band for c in CALIBRATION_RUBRIC if c.matches_count(count)
            ]
            assert len(matching) == 1, count

    def test_any_count_above_two_still_implies_weak(self):
        for count in (2, 10, 1000, 10 ** 9):
            assessment = assess_assertion(0.30, alternative_count=count)
            assert assessment.expected_band is ConfidenceBand.WEAK
            assert assessment.conformant is True


class TestNoFalseConformity:
    """UNASSESSED must never be reported or counted as conformance."""

    @pytest.mark.parametrize("value", [0.0, 0.25, 0.5, 0.75, 1.0])
    def test_a_missing_count_is_unassessed(self, value):
        assessment = assess_assertion(value)
        assert assessment.outcome is ConformanceOutcome.UNASSESSED
        assert assessment.conformant is False
        assert assessment.assessed is False
        assert assessment.detail == UNASSESSED_NO_COUNT

    @pytest.mark.parametrize("value", [0.00, 0.10, 0.19, 0.60, 0.70, 0.79])
    @pytest.mark.parametrize("count", [0, 1, 2, 5])
    def test_a_qualitative_band_is_unassessed_whatever_the_count(
        self, value, count
    ):
        """S-1 defines NEGLIGIBLE and STRONG without a countable test."""
        assessment = assess_assertion(value, alternative_count=count)
        assert assessment.outcome is ConformanceOutcome.UNASSESSED
        assert assessment.detail == UNASSESSED_QUALITATIVE_BAND

    def test_a_qualitative_band_never_yields_a_deviation(self):
        for value in (0.0, 0.19, 0.60, 0.79):
            for count in range(0, 6):
                assert assess_assertion(
                    value, alternative_count=count
                ).deviated is False

    def test_expected_band_is_none_without_a_count(self):
        assert assess_assertion(0.5).expected_band is None


class TestDeviationsRecorded:
    def test_a_deviation_is_recorded(self):
        register = CalibrationRegister()
        deviation = register.record("EV-1", assess_assertion(0.85, 3))
        assert deviation is not None
        assert register.deviation_count == 1
        assert deviation.object_id == "EV-1"

    def test_a_conformant_assessment_records_nothing(self):
        register = CalibrationRegister()
        assert register.record("EV-1", assess_assertion(0.85, 0)) is None
        assert register.deviation_count == 0
        assert register.assessment_count == 1

    def test_an_unassessed_assessment_records_nothing_but_is_counted(self):
        register = CalibrationRegister()
        assert register.record("EV-1", assess_assertion(0.85)) is None
        assert register.deviation_count == 0
        assert register.unassessed_count == 1
        assert register.assessment_count == 1

    def test_the_deviation_carries_the_rubric_identity(self):
        """T08.3.5: prior calibration retained for comparison."""
        register = CalibrationRegister()
        deviation = register.record("EV-1", assess_assertion(0.85, 3))
        assert deviation.rubric_id == "S-1"
        assert deviation.rubric_ratified == "2026-08-02"

    def test_the_deviation_records_both_bands(self):
        register = CalibrationRegister()
        deviation = register.record("EV-1", assess_assertion(0.85, 1))
        assert deviation.asserted_band is ConfidenceBand.VERY_STRONG
        assert deviation.expected_band is ConfidenceBand.MODERATE

    def test_the_register_is_append_only(self):
        register = CalibrationRegister()
        register.record("EV-1", assess_assertion(0.85, 3))
        with pytest.raises(CalibrationError):
            register.delete("EV-1")
        assert register.deviation_count == 1

    def test_the_register_never_alters_the_value(self):
        register = CalibrationRegister()
        deviation = register.record("EV-1", assess_assertion(0.85, 3))
        assert deviation.value == 0.85

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_a_blank_object_id_is_refused(self, bad):
        register = CalibrationRegister()
        with pytest.raises(CalibrationError):
            register.record(bad, assess_assertion(0.85, 3))

    @pytest.mark.parametrize("bad", ["x", None, 5])
    def test_a_non_assessment_is_refused(self, bad):
        register = CalibrationRegister()
        with pytest.raises(CalibrationError):
            register.record("EV-1", bad)

    def test_queries_are_exact(self):
        register = CalibrationRegister()
        register.record("o1", assess_assertion(0.85, 3, engine=Engine.RESEARCH))
        register.record("o2", assess_assertion(0.50, 4, engine=Engine.FEEDBACK))
        assert len(register.for_engine(Engine.RESEARCH)) == 1
        assert len(register.for_engine(Engine.FEEDBACK)) == 1
        assert len(register.for_object("o1")) == 1
        assert register.for_object("nope") == ()

    def test_for_engine_refuses_a_non_engine(self):
        with pytest.raises(CalibrationError):
            CalibrationRegister().for_engine("Research")

    def test_returned_collections_are_copies(self):
        register = CalibrationRegister()
        register.record("o1", assess_assertion(0.85, 3))
        assert isinstance(register.all(), tuple)
        assert register.all() is not register._deviations

    def test_len_counts_deviations_not_assessments(self):
        register = CalibrationRegister()
        register.record("a", assess_assertion(0.85, 0))
        register.record("b", assess_assertion(0.85, 2))
        assert len(register) == 1
        assert register.assessment_count == 2

    def test_the_summary_reports_counts_only(self):
        """Measuring calibration quality is O2, at T08.3.5."""
        register = CalibrationRegister()
        register.record("a", assess_assertion(0.85, 0))
        register.record("b", assess_assertion(0.85, 2))
        register.record("c", assess_assertion(0.85))
        summary = register.summary()
        assert summary == {"assessments": 3, "deviations": 1, "unassessed": 1}
        assert all(isinstance(v, int) for v in summary.values())
        assert not [k for k in summary if "rate" in k or "score" in k]

    def test_a_deviation_never_enters_lineage(self):
        register = CalibrationRegister()
        deviation = register.record("o1", assess_assertion(0.85, 3))
        assert deviation.participates_in_lineage is False
        assert deviation.is_intelligence is False
        assert register.participates_in_lineage is False


# ---------------------------------------------------------------------------
# AC3 -- cross-engine comparison documented as rubric-dependent
# ---------------------------------------------------------------------------

class TestCrossEngineComparison:
    def test_a_comparison_is_rubric_dependent(self):
        comparison = compare_across_engines([(Engine.RESEARCH, 0.8)])
        assert comparison.rubric_dependent is True
        assert comparison.rubric_id == "S-1"

    def test_comparability_is_never_claimed_as_demonstrated(self):
        """S-1: argued, not demonstrated, until O2 exists."""
        comparison = compare_across_engines([(Engine.RESEARCH, 0.8)])
        assert comparison.comparability_demonstrated is False

    def test_the_qualification_travels_with_the_result(self):
        comparison = compare_across_engines([(Engine.RESEARCH, 0.8)])
        assert "argued, not demonstrated" in comparison.qualification
        assert "T08.3.5" in comparison.qualification

    def test_the_three_comparability_properties_are_carried(self):
        comparison = compare_across_engines([])
        assert len(comparison.properties) == 3
        assert comparison.properties == COMPARABILITY_PROPERTIES

    def test_a_comparison_returns_bands(self):
        comparison = compare_across_engines(
            [(Engine.RESEARCH, 0.9), (Engine.FEEDBACK, 0.2)]
        )
        assert comparison.bands == (
            (Engine.RESEARCH, ConfidenceBand.VERY_STRONG),
            (Engine.FEEDBACK, ConfidenceBand.WEAK),
        )

    def test_a_comparison_offers_no_ranking(self):
        comparison = compare_across_engines([(Engine.RESEARCH, 0.9)])
        names = [n for n in dir(comparison) if not n.startswith("_")]
        assert not [
            n for n in names
            if any(b in n.lower() for b in ("rank", "best", "winner", "top"))
        ]

    def test_all_nine_engines_can_be_compared(self):
        comparison = compare_across_engines([(e, 0.5) for e in Engine])
        assert len(comparison) == 9
        assert set(comparison.engines) == set(Engine)

    def test_duplicate_engines_are_preserved(self):
        comparison = compare_across_engines(
            [(Engine.RESEARCH, 0.9), (Engine.RESEARCH, 0.1)]
        )
        assert len(comparison) == 2

    def test_an_empty_comparison_is_still_qualified(self):
        comparison = compare_across_engines([])
        assert len(comparison) == 0
        assert comparison.comparability_demonstrated is False
        assert comparison.qualification

    def test_a_comparison_is_frozen(self):
        comparison = compare_across_engines([])
        with pytest.raises(dataclasses.FrozenInstanceError):
            comparison.bands = ()  # type: ignore[misc]

    def test_a_non_engine_is_refused(self):
        with pytest.raises(CalibrationError):
            compare_across_engines([("Research", 0.5)])

    def test_an_out_of_range_value_is_refused(self):
        with pytest.raises(ValueError):
            compare_across_engines([(Engine.RESEARCH, 1.5)])


# ---------------------------------------------------------------------------
# Scope: only assertion_confidence  [S-1 Known Tensions / M-59]
# ---------------------------------------------------------------------------

class TestGovernedComponentOnly:
    def test_the_governed_component_is_assertion_confidence(self):
        assert GOVERNED_COMPONENT == "assertion_confidence"

    @pytest.mark.parametrize("component", UNGOVERNED_COMPONENTS)
    def test_an_ungoverned_component_is_refused(self, component):
        with pytest.raises(UngovernedComponentError):
            assess_assertion(0.5, 1, component=component)

    def test_the_ungoverned_components_are_named(self):
        assert set(UNGOVERNED_COMPONENTS) == {
            "evidential_support",
            "effective_confidence",
        }


class TestConfidenceIsNeverChanged:
    @pytest.mark.parametrize("value", [0.0, 0.137, 0.5, 0.8001, 1.0])
    def test_the_assessed_value_is_carried_unchanged(self, value):
        assert assess_assertion(value, 0).value == float(value)

    def test_a_confidence_object_is_untouched(self):
        confidence = Confidence(0.6, 0.85, 0.6)
        before = dataclasses.astuple(confidence)
        assess_assertion(confidence.assertion_confidence, alternative_count=0)
        assert dataclasses.astuple(confidence) == before

    def test_an_assessment_is_frozen(self):
        assessment = assess_assertion(0.5, 1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            assessment.value = 0.9  # type: ignore[misc]

    def test_the_module_exposes_no_confidence_mutator(self):
        import oip.calibration as module

        banned = ("adjust", "correct", "recalibrat", "rescale", "shift",
                  "offset", "normalise", "normalize", "set_confidence")
        names = [n for n in dir(module) if not n.startswith("_")]
        assert not [n for n in names if any(b in n.lower() for b in banned)]


class TestNoStatisticalCalibration:
    def test_no_empirical_vocabulary_exists(self):
        """O2 needs realised outcomes and is scheduled at T08.3.5 (P8)."""
        import oip.calibration as module

        source = Path(module.__file__).read_text().lower()
        for banned in ("brier", "isotonic", "platt", "reliability_curve",
                       "regression", "success_rate", "posterior"):
            assert banned not in source, banned

    def test_the_future_mechanism_is_named_not_built(self):
        import oip.calibration as module

        source = Path(module.__file__).read_text()
        assert "O2" in source
        assert "T08.3.5" in source
        names = [n for n in dir(module) if not n.startswith("_")]
        assert "o2" not in [n.lower() for n in names]

    def test_no_threshold_beyond_s1s_bands_is_introduced(self):
        """Only the five S-1 ranges; no sub-band, no tolerance."""
        import oip.calibration as module

        names = [n for n in dir(module) if not n.startswith("_")]
        assert not [
            n for n in names
            if any(b in n.lower() for b in ("threshold", "tolerance",
                                            "cutoff", "epsilon"))
        ]


# ---------------------------------------------------------------------------
# Fail closed
# ---------------------------------------------------------------------------

class TestFailsClosed:
    @pytest.mark.parametrize("bad", [-0.01, 1.01, 2.0, -1.0])
    def test_an_out_of_range_value_is_refused(self, bad):
        with pytest.raises(ValueError):
            assess_assertion(bad, 0)

    @pytest.mark.parametrize("bad", [-1, -5])
    def test_a_negative_count_is_refused(self, bad):
        with pytest.raises(CalibrationError):
            assess_assertion(0.5, bad)

    @pytest.mark.parametrize("bad", [1.5, "1", True, [1]])
    def test_a_non_integer_count_is_refused(self, bad):
        with pytest.raises(CalibrationError):
            assess_assertion(0.5, bad)

    def test_zero_is_a_valid_count(self):
        assert assess_assertion(0.85, 0).conformant is True

    def test_boolean_is_not_an_integer_count(self):
        """True == 1 numerically; accepting it would silently mean MODERATE."""
        with pytest.raises(CalibrationError):
            assess_assertion(0.5, True)


# ---------------------------------------------------------------------------
# Architecture boundaries
# ---------------------------------------------------------------------------

class TestArchitectureBoundaries:
    def test_calibration_imports_only_enums(self):
        source = (
            Path(__file__).resolve().parents[1] / "oip" / "calibration.py"
        ).read_text()
        modules = {
            node.module
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert {m for m in modules if m.startswith("oip.")} == {"oip.enums"}

    def test_no_intelligence_object_module_is_imported(self):
        source = (
            Path(__file__).resolve().parents[1] / "oip" / "calibration.py"
        ).read_text()
        for banned in ("evidence", "fact", "problem", "pattern", "store",
                       "graph", "lineage", "acceptance", "lifecycle"):
            assert f"from oip.{banned}" not in source

    def test_confidence_band_semantics_are_unchanged(self):
        assert [b.value for b in ConfidenceBand] == [
            "NEGLIGIBLE", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"
        ]
        assert ConfidenceBand.for_value(0.0) is ConfidenceBand.NEGLIGIBLE
        assert ConfidenceBand.for_value(1.0) is ConfidenceBand.VERY_STRONG

    def test_the_confidence_contract_is_unchanged(self):
        confidence = Confidence(0.62, 0.84, 0.62)
        assert confidence.band is ConfidenceBand.STRONG
        with pytest.raises(Exception):
            Confidence(0.5, 0.5, 0.9)

    def test_the_acceptance_rule_set_is_unchanged(self):
        from oip.store import KnowledgeStore

        assert len(KnowledgeStore().acceptance.rule_ids) == 68

    def test_calibration_is_not_an_acceptance_rule(self):
        """No ratified source makes calibration gate acceptance."""
        from oip.store import KnowledgeStore

        rule_ids = KnowledgeStore().acceptance.rule_ids
        assert not [r for r in rule_ids if "CAL" in r.upper()]


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_recording_loses_nothing(self):
        register = CalibrationRegister()
        errors: list[Exception] = []

        def worker(k: int) -> None:
            try:
                for i in range(200):
                    register.record(f"o{k}-{i}", assess_assertion(0.85, 3))
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert register.deviation_count == 1600
        assert register.assessment_count == 1600

    def test_mixed_outcomes_are_counted_exactly(self):
        register = CalibrationRegister()

        def worker(k: int) -> None:
            for i in range(100):
                register.record(f"d{k}-{i}", assess_assertion(0.85, 3))
                register.record(f"c{k}-{i}", assess_assertion(0.85, 0))
                register.record(f"u{k}-{i}", assess_assertion(0.85))

        threads = [threading.Thread(target=worker, args=(k,)) for k in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert register.assessment_count == 1800
        assert register.deviation_count == 600
        assert register.unassessed_count == 600

    def test_assessment_is_pure_under_concurrency(self):
        results: list[tuple] = []
        errors: list[Exception] = []

        def worker() -> None:
            try:
                results.append(
                    tuple(
                        assess_assertion(v, 0).outcome
                        for v in (0.85, 0.5, 0.3)
                    )
                )
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors
        assert len(set(results)) == 1

    def test_reads_stay_coherent_during_writes(self):
        register = CalibrationRegister()
        stop = threading.Event()
        errors: list[Exception] = []

        def reader() -> None:
            while not stop.is_set():
                try:
                    assert all(d.rubric_id == "S-1" for d in register.all())
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(exc)
                    return

        thread = threading.Thread(target=reader)
        thread.start()
        for i in range(1000):
            register.record(f"o{i}", assess_assertion(0.85, 2))
        stop.set()
        thread.join()
        assert not errors
        assert register.deviation_count == 1000


# ---------------------------------------------------------------------------
# Property-based  [N-4: properties, never output equality of engine results]
# ---------------------------------------------------------------------------

values = st.floats(min_value=0.0, max_value=1.0, allow_nan=False,
                   allow_infinity=False)
counts = st.integers(min_value=0, max_value=50)
engines = st.sampled_from(list(Engine))


@settings(max_examples=300, deadline=None)
@given(value=values)
def test_property_every_value_resolves_to_exactly_one_criterion(value):
    holding = [c for c in CALIBRATION_RUBRIC if c.contains(value)]
    assert len(holding) == 1
    assert holding[0].band is ConfidenceBand.for_value(value)


@settings(max_examples=300, deadline=None)
@given(value=values)
def test_property_a_missing_count_is_always_unassessed(value):
    assessment = assess_assertion(value)
    assert assessment.outcome is ConformanceOutcome.UNASSESSED
    assert assessment.conformant is False


@settings(max_examples=300, deadline=None)
@given(value=values, count=counts)
def test_property_assessment_never_alters_the_value(value, count):
    assert assess_assertion(value, count).value == float(value)


@settings(max_examples=300, deadline=None)
@given(value=values, count=counts)
def test_property_a_qualitative_band_is_never_judged(value, count):
    assessment = assess_assertion(value, count)
    if assessment.band in QUALITATIVE:
        assert assessment.outcome is ConformanceOutcome.UNASSESSED


@settings(max_examples=300, deadline=None)
@given(value=values, count=counts)
def test_property_a_countable_band_is_always_judged(value, count):
    assessment = assess_assertion(value, count)
    if assessment.band in COUNTABLE:
        assert assessment.outcome in (
            ConformanceOutcome.CONFORMANT,
            ConformanceOutcome.DEVIATION,
        )


@settings(max_examples=300, deadline=None)
@given(value=values, count=counts)
def test_property_conformance_iff_the_count_matches_the_band(value, count):
    assessment = assess_assertion(value, count)
    criterion = criterion_for_value(value)
    if criterion.is_countable:
        assert assessment.conformant == criterion.matches_count(count)


@settings(max_examples=200, deadline=None)
@given(value=values, count=counts, engine=engines)
def test_property_assessment_is_deterministic(value, count, engine):
    first = assess_assertion(value, count, engine=engine)
    second = assess_assertion(value, count, engine=engine)
    assert dataclasses.asdict(first) == dataclasses.asdict(second)


@settings(max_examples=200, deadline=None)
@given(entries=st.lists(st.tuples(engines, values), max_size=12))
def test_property_a_comparison_is_always_qualified(entries):
    comparison = compare_across_engines(entries)
    assert comparison.rubric_dependent is True
    assert comparison.comparability_demonstrated is False
    assert len(comparison) == len(entries)


@settings(max_examples=200, deadline=None)
@given(records=st.lists(st.tuples(values, counts), min_size=1, max_size=20))
def test_property_register_totals_are_internally_consistent(records):
    register = CalibrationRegister()
    for index, (value, count) in enumerate(records):
        register.record(f"o{index}", assess_assertion(value, count))
    summary = register.summary()
    assert summary["assessments"] == len(records)
    assert summary["deviations"] == register.deviation_count
    assert summary["deviations"] + summary["unassessed"] <= summary["assessments"]


@settings(max_examples=200, deadline=None)
@given(count=counts)
def test_property_a_count_maps_to_at_most_one_band(count):
    matching = [c.band for c in CALIBRATION_RUBRIC if c.matches_count(count)]
    assert len(matching) == 1


class TestDefensiveBranches:
    """Cover the branches that only fire when something is already wrong."""

    def test_expected_band_is_none_when_no_band_claims_the_count(self):
        """Constructed directly: every real count maps to a band, so this
        branch fires only if the rubric were ever narrowed."""
        assessment = CalibrationAssessment(
            value=0.85,
            band=ConfidenceBand.VERY_STRONG,
            criterion=criterion_for_band(ConfidenceBand.VERY_STRONG),
            outcome=ConformanceOutcome.DEVIATION,
            alternative_count=-1,          # matches no band
        )
        assert assessment.expected_band is None

    def test_the_boundary_guard_detects_a_divergent_rubric(self, monkeypatch):
        """If S-1's ranges ever stopped matching ConfidenceBand.for_value,
        an assertion would be governed by the wrong criterion. The guard
        must report that rather than let it pass."""
        import oip.calibration as module

        divergent = dataclasses.replace(
            criterion_for_band(ConfidenceBand.WEAK), low=0.95, high=0.99
        )
        monkeypatch.setattr(module, "CALIBRATION_RUBRIC", (divergent,))
        assert module.rubric_matches_band_boundaries() is False

    def test_the_guard_passes_for_the_real_rubric(self):
        assert rubric_matches_band_boundaries() is True

    def test_matches_count_is_false_for_a_qualitative_band(self):
        for band in QUALITATIVE:
            criterion = criterion_for_band(band)
            assert criterion.is_countable is False
            for count in range(0, 5):
                assert criterion.matches_count(count) is False
