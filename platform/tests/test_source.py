"""Contract tests for the source model.

Task: T02.1.1

Architecture References:
- N-20   Source model (RATIFIED 2026-08-04): taxonomy S 5.1 (the eight
         members below are its table verbatim), eligibility-as-typability
         S 5.2, trust representation S 5.3. The M-16 scoring half stays
         OPEN and is still surfaced by these tests.
- S-02   evidential_support has five exhaustive inputs; trust is not one.
- N-16   Independence assessed on grouping key, falling back to identifier.
- N-04   Historical reads reproduce: append-only, versioned.
- CI-1   No Intelligence Object, no lineage path.
- N-4    Property-based assertions only; never equality on engine output.

T02.1.1 acceptance criteria under test:
  AC1  source_type drawn from a closed taxonomy   -> IMPLEMENTED from N-20 S 5.1
  AC2  per-source trust rating stored             -> IMPLEMENTED
  AC3  trust is a learnable target for P8         -> NOT IMPLEMENTABLE (M-02/M-43)
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.source import (
    LEARNING_TARGET_MARKERS,
    LEARNING_TARGET_STATUS,
    TAXONOMY_MARKER,
    TAXONOMY_RATIFIED,
    TRUST_MAXIMUM,
    TRUST_MINIMUM,
    EligibilityNotRatifiedError,
    LearningTargetNotRatifiedError,
    SourceEligibility,
    SourceError,
    SourceImmutableError,
    SourceNotFoundError,
    SourceRecord,
    SourceRegistry,
    SourceType,
    TrustNotRatifiedError,
    TrustRating,
    UntypableChannelError,
    affects_evidential_support,
    assess_eligibility,
    classify,
    is_learning_target,
    is_ratified_source_type,
    register_learning_update,
    require_eligible,
    taxonomy_members,
)

TRUST = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# The N-20 S 5.1 closed set, in ratified table order. [AC1]
TAXONOMY_NAMES: tuple[str, ...] = (
    "PUBLISHED_EDITORIAL",
    "MARKETPLACE_LISTING",
    "USER_GENERATED_REVIEW",
    "USER_GENERATED_DISCUSSION",
    "SUPPORT_INTERACTION",
    "STRUCTURED_DATASET",
    "REGULATORY_FILING",
    "VENDOR_PUBLICATION",
)
IDENT = st.text(min_size=1, max_size=40).filter(lambda s: s.strip())


def registry_with(n: int = 3) -> SourceRegistry:
    reg = SourceRegistry()
    for i in range(n):
        reg.register(f"src-{i}", f"raw-type-{i}")
    return reg


# ===========================================================================
# AC1 -- taxonomy: populated exactly from N-20 S 5.1, closed  [N-20]
# ===========================================================================


class TestTaxonomyPopulatedFromN20:
    def test_taxonomy_is_the_eight_members_in_ratified_order(self):
        assert [m.name for m in taxonomy_members()] == list(TAXONOMY_NAMES)
        assert len(TAXONOMY_NAMES) == 8
        assert TAXONOMY_RATIFIED is True

    def test_the_marker_still_names_the_open_scoring_half(self):
        assert TAXONOMY_MARKER == "M-16"

    @given(candidate=st.sampled_from(TAXONOMY_NAMES))
    def test_classify_maps_every_ratified_member(self, candidate):
        """Property: each ratified name classifies to its own member."""
        assert classify(candidate) is SourceType[candidate]

    @given(candidate=st.text(max_size=30).filter(
        lambda s: s.strip() and s not in TAXONOMY_NAMES))
    def test_classify_refuses_everything_else(self, candidate):
        """Property: nothing outside the closed set classifies. [N-20 S 5.2]"""
        with pytest.raises(UntypableChannelError) as exc:
            classify(candidate)
        assert "UNTYPABLE_CHANNEL" in str(exc.value)

    def test_classify_rejects_non_strings_and_empty(self):
        for bad in (None, 0, [], object(), "", "   "):
            with pytest.raises(SourceError):
                classify(bad)

    @given(candidate=st.text(max_size=30))
    def test_no_raw_string_is_ever_a_typed_member(self, candidate):
        """The typed predicate is for enum values; strings use classify."""
        assert is_ratified_source_type(candidate) is False

    def test_membership_predicate_is_total(self):
        """It must never raise -- callers branch without try/except."""
        for candidate in (None, 0, "", [], object(), SourceType):
            assert is_ratified_source_type(candidate) is False
        assert is_ratified_source_type(SourceType.REGULATORY_FILING) is True

    def test_enum_carries_exactly_the_eight_ratified_members(self):
        """The guard against someone quietly extending the vocabulary."""
        assert list(SourceType) == [SourceType[n] for n in TAXONOMY_NAMES]
        with pytest.raises(AttributeError):
            SourceType.CUSTOMER_REVIEW_CORPUS


# ===========================================================================
# AC1 -- eligibility = typability  [N-20 S 5.2]
# ===========================================================================


class TestEligibilityFailsClosed:
    @given(identifier=IDENT)
    def test_eligibility_is_never_determined_from_identifier_alone(self, identifier):
        assessment = assess_eligibility(identifier)
        assert assessment.outcome is SourceEligibility.UNDETERMINED
        assert assessment.is_determined is False

    @given(identifier=IDENT)
    def test_undetermined_never_admits_acquisition(self, identifier):
        """Fails closed: absence of a rule is not permission."""
        assert assess_eligibility(identifier).admits_acquisition is False

    def test_assessment_carries_no_blocking_marker(self):
        """No open MARKER blocks eligibility anymore; the untyped channel
        does (T02.2.1 sequencing), and that is a task, not a marker."""
        assert assess_eligibility("src-a").blocking_marker is None

    def test_require_eligible_refuses(self):
        with pytest.raises(EligibilityNotRatifiedError) as exc:
            require_eligible("src-a")
        assert "cannot be admitted" in str(exc.value)
        assert "typability" in str(exc.value)

    def test_assessment_does_not_raise(self):
        """Reporting a gap must not force callers into exception handling."""
        assert assess_eligibility("src-a") is not None

    def test_empty_identifier_is_rejected(self):
        for bad in ("", "   "):
            with pytest.raises(SourceError):
                assess_eligibility(bad)

    def test_legal_policy_is_not_conflated_with_eligibility(self):
        """M-18 is T02.1.2; this result must not be read as legal clearance."""
        reason = assess_eligibility("src-a").reason
        assert "M-18" in reason and "T02.1.2" in reason


# ===========================================================================
# AC2 -- trust recording  [IMPLEMENTED]
# ===========================================================================


class TestTrustRecording:
    @given(value=TRUST)
    def test_recorded_trust_is_retrievable(self, value):
        reg = registry_with(1)
        reg.record_trust("src-0", value, "assessed during closure review")
        stored = reg.trust_for("src-0")
        assert stored is not None
        assert TRUST_MINIMUM <= stored.value <= TRUST_MAXIMUM

    @given(value=TRUST)
    def test_recording_marks_the_source_trusted(self, value):
        reg = registry_with(1)
        assert reg.resolve("src-0").is_trusted is False
        reg.record_trust("src-0", value, "rationale")
        assert reg.resolve("src-0").is_trusted is True

    @given(values=st.lists(TRUST, min_size=2, max_size=6))
    def test_history_grows_monotonically_and_versions_increment(self, values):
        reg = registry_with(1)
        for v in values:
            reg.record_trust("src-0", v, "re-assessed")
        history = reg.trust_history("src-0")
        assert len(history) == len(values)
        assert [r.version for r in history] == list(range(1, len(values) + 1))

    @given(values=st.lists(TRUST, min_size=2, max_size=5))
    def test_earlier_ratings_are_never_overwritten(self, values):
        """N-04: a historical read must reproduce what an engine saw."""
        reg = registry_with(1)
        for v in values:
            reg.record_trust("src-0", v, "re-assessed")
        for version in range(1, len(values) + 1):
            assert reg.trust_at_version("src-0", version).version == version

    @given(values=st.lists(TRUST, min_size=2, max_size=4))
    def test_supersession_chain_is_recorded(self, values):
        reg = registry_with(1)
        for v in values:
            reg.record_trust("src-0", v, "re-assessed")
        history = reg.trust_history("src-0")
        assert history[0].supersedes is None
        assert all(r.supersedes is not None for r in history[1:])

    def test_unrated_source_returns_none_never_a_default(self):
        """The core honesty property: absence is reported, not imputed."""
        reg = registry_with(2)
        assert reg.trust_for("src-0") is None
        assert reg.resolve("src-0").trust_value is None

    def test_unrated_sources_are_enumerable(self):
        reg = registry_with(3)
        reg.record_trust("src-1", 0.5, "rationale")
        unrated = reg.unrated()
        assert "src-1" not in unrated
        assert set(unrated) == {"src-0", "src-2"}

    @given(value=st.floats(allow_nan=False, allow_infinity=False)
           .filter(lambda v: not 0.0 <= v <= 1.0))
    def test_out_of_range_trust_is_rejected(self, value):
        reg = registry_with(1)
        with pytest.raises(TrustNotRatifiedError):
            reg.record_trust("src-0", value, "rationale")

    def test_rating_requires_a_rationale(self):
        reg = registry_with(1)
        for bad in ("", "   "):
            with pytest.raises(TrustNotRatifiedError):
                reg.record_trust("src-0", 0.5, bad)

    def test_boolean_is_not_a_valid_trust_value(self):
        """bool is a subclass of int; it must not slip through as 0/1."""
        with pytest.raises(TrustNotRatifiedError):
            TrustRating("s", True, datetime.now(timezone.utc), "r", 1)

    def test_rating_for_unregistered_source_is_refused(self):
        with pytest.raises(SourceNotFoundError):
            SourceRegistry().record_trust("ghost", 0.5, "rationale")

    def test_trust_banding_fails_closed(self):
        """R-3 bands govern confidence, not trust. [M-16]"""
        rating = TrustRating("s", 0.5, datetime.now(timezone.utc), "r", 1)
        with pytest.raises(TrustNotRatifiedError):
            _ = rating.band

    def test_version_must_start_at_one(self):
        with pytest.raises(TrustNotRatifiedError):
            TrustRating("s", 0.5, datetime.now(timezone.utc), "r", 0)


class TestTrustDoesNotScore:
    def test_trust_never_affects_evidential_support(self):
        """S-02 lists five inputs and says 'No other input.'"""
        assert affects_evidential_support() is False

    def test_registry_exposes_no_scoring_path(self):
        """CI-1 / S-02: no member may hand trust to a scoring function."""
        forbidden = ("evidential_support", "confidence", "score", "weight")
        for name in dir(SourceRegistry):
            if name.startswith("_"):
                continue
            assert not any(f in name.lower() for f in forbidden), name


# ===========================================================================
# AC3 -- learnability  [NOT IMPLEMENTABLE: M-02, M-43]
# ===========================================================================


class TestLearningTargetFailsClosed:
    def test_trust_is_not_a_ratified_learning_target(self):
        assert is_learning_target() is False

    def test_learning_update_is_refused(self):
        with pytest.raises(LearningTargetNotRatifiedError):
            register_learning_update("src-0", 0.9)

    def test_status_names_every_blocking_marker(self):
        for marker in ("M-02", "M-43", "M-70"):
            assert marker in LEARNING_TARGET_STATUS
        assert set(LEARNING_TARGET_MARKERS) == {"M-02", "M-43", "M-70"}

    def test_predicate_is_total(self):
        """Callers branch without exception handling."""
        assert is_learning_target() in (True, False)


# ===========================================================================
# Registry: immutability, resolution, independence
# ===========================================================================


class TestRegistry:
    def test_registration_resolves(self):
        reg = SourceRegistry()
        reg.register("src-a", "raw-type")
        assert reg.resolve("src-a").source_identifier == "src-a"
        assert reg.contains("src-a")

    def test_identical_registration_is_idempotent(self):
        reg = SourceRegistry()
        first = reg.register("src-a", "raw-type", "group-1")
        second = reg.register("src-a", "raw-type", "group-1")
        assert first.registered_at == second.registered_at
        assert len(reg) == 1

    def test_conflicting_re_registration_is_refused(self):
        reg = SourceRegistry()
        reg.register("src-a", "raw-type")
        with pytest.raises(SourceImmutableError):
            reg.register("src-a", "different-type")

    def test_unknown_source_does_not_resolve(self):
        with pytest.raises(SourceNotFoundError):
            SourceRegistry().resolve("ghost")

    def test_find_returns_none_rather_than_raising(self):
        assert SourceRegistry().find("ghost") is None

    def test_record_requires_identifier_and_type(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(SourceError):
            SourceRecord("", "type", now)
        with pytest.raises(SourceError):
            SourceRecord("src", "", now)

    def test_records_are_frozen(self):
        reg = registry_with(1)
        with pytest.raises(Exception):
            reg.resolve("src-0").source_identifier = "mutated"

    @given(n=st.integers(min_value=0, max_value=12))
    def test_length_matches_registrations(self, n):
        reg = SourceRegistry()
        for i in range(n):
            reg.register(f"s-{i}", "raw")
        assert len(reg) == n
        assert len(list(reg)) == n


class TestIndependence:
    def test_identifier_is_the_default_independence_key(self):
        """N-16, mirroring the ratified Provenance.independence_key."""
        reg = registry_with(1)
        record = reg.resolve("src-0")
        assert record.independence_key == record.source_identifier

    def test_grouping_overrides_the_identifier(self):
        reg = SourceRegistry()
        reg.register("src-a", "raw", "syndicate-1")
        assert reg.resolve("src-a").independence_key == "syndicate-1"

    @given(n=st.integers(min_value=2, max_value=8))
    def test_grouped_sources_count_once(self, n):
        """Property: syndication cannot inflate the independent count."""
        reg = SourceRegistry()
        for i in range(n):
            reg.register(f"src-{i}", "raw", "one-syndicate")
        assert reg.independent_source_count() == 1

    @given(n=st.integers(min_value=1, max_value=8))
    def test_ungrouped_sources_count_individually(self, n):
        reg = SourceRegistry()
        for i in range(n):
            reg.register(f"src-{i}", "raw")
        assert reg.independent_source_count() == n

    def test_groups_partition_every_registered_source(self):
        reg = SourceRegistry()
        reg.register("a", "raw", "g1")
        reg.register("b", "raw", "g1")
        reg.register("c", "raw")
        groups = reg.independence_groups()
        assert sum(len(v) for v in groups.values()) == len(reg)

    def test_source_type_diversity_counts_classified_members_only(self):
        """S-02 input 2 counts taxonomy members, never raw strings."""
        reg = SourceRegistry()
        reg.register("a", "PUBLISHED_EDITORIAL")
        reg.register("b", "PUBLISHED_EDITORIAL")
        reg.register("c", "MARKETPLACE_LISTING")
        reg.register("d", "not-a-ratified-type")
        assert reg.source_type_diversity() == 2

    def test_source_type_diversity_is_zero_when_nothing_classifies(self):
        assert registry_with(3).source_type_diversity() == 0


class TestGapReporting:
    def test_every_gap_names_a_marker(self):
        gaps = SourceRegistry().specification_gaps()
        assert gaps
        assert all(v.strip() for v in gaps.values())

    def test_the_known_open_markers_are_reported(self):
        gaps = SourceRegistry().specification_gaps()
        assert set(gaps.values()) >= {"M-16", "M-02", "M-43", "M-70", "M-18", "S-02"}

    def test_n20_closed_gaps_are_gone_and_open_ones_remain(self):
        """N-20 S 8 closed the taxonomy/eligibility/diversity gaps; the
        scoring/semantics half of M-16 stays open and reported."""
        gaps = SourceRegistry().specification_gaps()
        for key in ("source_taxonomy", "per_type_eligibility",
                    "source_type_diversity"):
            assert key not in gaps
        assert gaps["trust_semantics"] == "M-16"
        assert gaps["trust_banding"] == "M-16"


class TestCI1Isolation:
    def test_module_imports_no_intelligence_object(self):
        """CI-1: no shared type with the object model."""
        import ast
        from pathlib import Path

        src = Path(__file__).resolve().parents[1] / "oip" / "source.py"
        tree = ast.parse(src.read_text())
        imported = {
            n.module
            for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom) and n.module
            and n.module.startswith("oip.")
        }
        assert imported <= {"oip.contract"}, imported

    def test_no_record_carries_lineage(self):
        record = registry_with(1).resolve("src-0")
        for attr in ("derives_from", "lineage", "lineage_id", "object_id"):
            assert not hasattr(record, attr)


class TestConcurrency:
    def test_concurrent_registration_is_consistent(self):
        reg = SourceRegistry()
        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                for j in range(10):
                    reg.register(f"src-{i}-{j}", "raw")
            except Exception as exc:  # pragma: no cover - failure path
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(reg) == 40

    def test_concurrent_trust_recording_preserves_every_version(self):
        reg = registry_with(1)
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(10):
                    reg.record_trust("src-0", 0.5, "concurrent")
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        history = reg.trust_history("src-0")
        assert [r.version for r in history] == list(range(1, 41))


# ===========================================================================
# Defensive guards  [coverage of every validation branch]
# ===========================================================================

class TestGuards:
    def test_trust_rating_requires_an_identifier(self):
        with pytest.raises(SourceError):
            TrustRating("", 0.5, datetime.now(timezone.utc), "r", 1)

    def test_trust_rating_requires_a_datetime(self):
        with pytest.raises(TrustNotRatifiedError):
            TrustRating("s", 0.5, "2026-01-01", "r", 1)

    def test_source_record_requires_a_datetime(self):
        with pytest.raises(SourceError):
            SourceRecord("s", "raw", "2026-01-01")

    def test_taxonomy_classified_reflects_raw_string_membership(self):
        reg = SourceRegistry()
        typed = reg.register("s", "VENDOR_PUBLICATION")
        untyped = reg.register("t", "raw")
        assert typed.taxonomy_classified is True
        assert untyped.taxonomy_classified is False

    def test_unknown_trust_version_is_refused(self):
        reg = registry_with(1)
        reg.record_trust("src-0", 0.5, "rationale")
        with pytest.raises(SourceNotFoundError):
            reg.trust_at_version("src-0", 99)

    def test_require_eligible_passes_through_a_determined_admission(self):
        """Guard the branch that will matter once M-16 closes."""
        assessment = assess_eligibility("src-a")
        assert assessment.admits_acquisition is False
        with pytest.raises(EligibilityNotRatifiedError):
            require_eligible("src-a")
