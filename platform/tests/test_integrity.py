"""Contract tests for universal integrity constraints I1-I8.

Task: T01.4.5

Architecture References:
- I1-I8  Universal integrity constraints, IOM section 1.4
- N-8    Store enforces; rules specified in the object model
- N-10   Violations produce records, never unexpected exceptions
- R-2    is_consumable() defines what may be read
- R-3    Confidence ceiling
- T01.2.3 Cascade enforces I6

Acceptance criteria under test:
  AC1  I5 (one ACTIVE per lineage_id) continuously held
  AC2  I6 (cascade) enforced via T01.2.3
  AC3  I8 prevents REJECTED objects being consumed as input

Constraints are CONTINUOUS invariants, not acceptance-time checks: they are
verified after cascades, supersessions and direct corruption, not only at
write time.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from oip.acceptance import AcceptanceContext, AcceptancePath, RuleOutcome
from oip.cascade import CascadeInvalidation
from oip.enums import ObjectStatus, ObjectType
from oip.identity import IdentityAllocator
from oip.integrity import (
    ConstraintMode,
    IntegrityError,
    IntegrityReport,
    IntegrityVerifier,
    Violation,
    i8_inputs_are_consumable,
)
from oip.store import KnowledgeStore, StoredObject, WriteRejectedError
from tests.conftest import (
    build_attrs,
    build_lineage,
    write_chain,
    write_derived,
    write_evidence,
)


@pytest.fixture()
def verifier(store) -> IntegrityVerifier:
    return IntegrityVerifier(store=store)


def corrupt_status(store, object_id: str, status: ObjectStatus, reason=None):
    """Bypass the lifecycle to plant a violation the guards would refuse."""
    stored = store.get(object_id)
    attributes = stored.attributes
    object.__setattr__(attributes, "status", status)
    object.__setattr__(attributes, "status_reason", reason)
    store._objects[object_id] = StoredObject(
        attributes=attributes, lineage=stored.lineage
    )


# ===========================================================================
# Clean store: every constraint holds
# ===========================================================================

class TestCleanStore:
    def test_empty_store_holds(self, verifier):
        report = verifier.verify()
        assert report.holds
        assert report.checked_objects == 0

    def test_full_chain_holds(self, store, allocator, verifier):
        write_chain(store, allocator)
        report = verifier.verify()
        assert report.holds, report.violations
        assert report.checked_objects == 7

    def test_all_eight_constraints_run(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify().constraints_run == tuple(
            f"I{i}" for i in range(1, 9)
        )

    def test_holds_after_cascade(self, store, allocator, verifier):
        """Integrity must survive a cascade, not merely a clean write."""
        chain = write_chain(store, allocator)
        CascadeInvalidation(store=store).retract(
            chain[ObjectType.EVIDENCE].object_id, "withdrawn"
        )
        assert verifier.verify().holds

    def test_holds_after_supersession(self, store, allocator, verifier):
        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        successor = allocator.succeed(first.attributes.identity)
        store.write(
            build_attrs(
                successor, ObjectType.EVIDENCE,
                status=ObjectStatus.ACTIVE, status_reason=None,
            ),
            build_lineage(successor.object_id, ObjectType.EVIDENCE),
            predecessor_id=first.object_id,
        )
        assert verifier.verify().holds

    def test_store_exposes_verification(self, store, allocator):
        write_chain(store, allocator)
        assert store.verify_integrity().holds
        store.assert_integrity()  # must not raise


# ===========================================================================
# I1 -- content immutable
# ===========================================================================

class TestI1ContentImmutable:
    def test_attributes_are_frozen(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify_constraint("I1").holds

    def test_mutation_is_impossible_through_the_public_surface(
        self, store, allocator
    ):
        stored = write_evidence(store, allocator)
        with pytest.raises(Exception):
            stored.attributes.engine_configuration_ref = "cfg-v2"

    def test_i1_is_detective(self, verifier):
        assert verifier.CONSTRAINT_MODES["I1"] is ConstraintMode.DETECTIVE


# ===========================================================================
# I2 -- object_id never reused
# ===========================================================================

class TestI2NoIdReuse:
    def test_clean_store_holds(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify_constraint("I2").holds

    def test_duplicate_write_refused_at_the_store(self, store, allocator):
        from oip.store import DuplicateWriteError
        stored = write_evidence(store, allocator)
        with pytest.raises(DuplicateWriteError):
            store.write(
                build_attrs(
                    stored.attributes.identity, ObjectType.EVIDENCE,
                    status=ObjectStatus.ACTIVE, status_reason=None,
                ),
                build_lineage(stored.object_id, ObjectType.EVIDENCE),
            )

    def test_versions_share_lineage_without_reusing_ids(
        self, store, allocator, verifier
    ):
        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        successor = allocator.succeed(first.attributes.identity)
        store.write(
            build_attrs(
                successor, ObjectType.EVIDENCE,
                status=ObjectStatus.ACTIVE, status_reason=None,
            ),
            build_lineage(successor.object_id, ObjectType.EVIDENCE),
            predecessor_id=first.object_id,
        )
        assert verifier.verify_constraint("I2").holds


# ===========================================================================
# I3 -- lineage references never repoint
# ===========================================================================

class TestI3NoRepointing:
    def test_clean_store_holds(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify_constraint("I3").holds

    def test_repointed_reference_detected(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        other = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])

        from oip.contract import LineageRef
        object.__setattr__(
            fact.attributes, "derives_from",
            (LineageRef(other.object_id, ObjectType.EVIDENCE),),
        )

        report = verifier.verify_constraint("I3")
        assert not report.holds
        assert "repointed" in report.violations[0].detail

    def test_violation_names_both_sides(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        object.__setattr__(fact.attributes, "derives_from", ())
        detail = verifier.verify_constraint("I3").violations[0].detail
        assert "attributes say" in detail and "lineage says" in detail


# ===========================================================================
# I4 -- referenced objects never hard-deleted
# ===========================================================================

class TestI4NoHardDelete:
    def test_clean_store_holds(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify_constraint("I4").holds

    def test_delete_is_unsupported(self, store, allocator):
        from oip.store import HardDeleteError
        stored = write_evidence(store, allocator)
        with pytest.raises(HardDeleteError):
            store.delete(stored.object_id)

    def test_missing_reference_detected(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        del store._objects[evidence.object_id]

        report = verifier.verify_constraint("I4")
        assert not report.holds
        assert report.violations[0].object_id == fact.object_id
        assert "lineage is broken" in report.violations[0].detail

    def test_retracted_reference_survives(self, store, allocator, verifier):
        """I4 is about existence, not status."""
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")
        assert verifier.verify_constraint("I4").holds


# ===========================================================================
# I5 -- exactly one ACTIVE per lineage_id  (AC1)
# ===========================================================================

class TestI5SingleActive:
    def test_clean_store_holds(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify_constraint("I5").holds

    def test_write_path_prevents_a_second_active(self, store, allocator):
        from oip.store import ActiveVersionConflictError
        first = write_evidence(store, allocator)
        successor = allocator.succeed(first.attributes.identity)
        with pytest.raises(ActiveVersionConflictError):
            store.write(
                build_attrs(
                    successor, ObjectType.EVIDENCE,
                    status=ObjectStatus.ACTIVE, status_reason=None,
                ),
                build_lineage(successor.object_id, ObjectType.EVIDENCE),
                predecessor_id=first.object_id,
            )

    def test_corruption_detected_continuously(self, store, allocator, verifier):
        """AC1: the invariant is checked continuously, not only at write."""
        first = write_evidence(store, allocator)
        successor = allocator.succeed(first.attributes.identity)
        attributes = build_attrs(
            successor, ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        store._objects[successor.object_id] = StoredObject(
            attributes=attributes,
            lineage=build_lineage(successor.object_id, ObjectType.EVIDENCE),
        )

        report = verifier.verify_constraint("I5")
        assert not report.holds
        assert len(report.violations) == 2  # both offenders named
        assert "2 ACTIVE versions" in report.violations[0].detail

    def test_holds_when_predecessor_superseded(self, store, allocator, verifier):
        first = write_evidence(store, allocator)
        store.transition(first.object_id, ObjectStatus.SUPERSEDED, "replaced")
        successor = allocator.succeed(first.attributes.identity)
        store.write(
            build_attrs(
                successor, ObjectType.EVIDENCE,
                status=ObjectStatus.ACTIVE, status_reason=None,
            ),
            build_lineage(successor.object_id, ObjectType.EVIDENCE),
            predecessor_id=first.object_id,
        )
        assert verifier.verify_constraint("I5").holds

    def test_distinct_lineages_may_each_have_one_active(
        self, store, allocator, verifier
    ):
        for _ in range(10):
            write_evidence(store, allocator)
        assert verifier.verify_constraint("I5").holds


# ===========================================================================
# I6 -- cascade enforced  (AC2)
# ===========================================================================

class TestI6CascadeEnforced:
    def test_cascade_satisfies_i6(self, store, allocator, verifier):
        """AC2: I6 is enforced by the T01.2.3 operation."""
        chain = write_chain(store, allocator)
        CascadeInvalidation(store=store).retract(
            chain[ObjectType.EVIDENCE].object_id, "withdrawn"
        )
        assert verifier.verify_constraint("I6").holds

    def test_uncascaded_retraction_detected(self, store, allocator, verifier):
        """Retraction without cascade is exactly what I6 forbids."""
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")

        report = verifier.verify_constraint("I6")
        assert not report.holds
        assert report.violations[0].object_id == fact.object_id
        assert "cascade did not reach it" in report.violations[0].detail

    def test_partial_cascade_detected(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        facts = [
            write_derived(store, allocator, ObjectType.FACT, [evidence])
            for _ in range(3)
        ]
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        store.transition(facts[0].object_id, ObjectStatus.INVALIDATED, "manual")

        report = verifier.verify_constraint("I6")
        assert len(report.violations) == 2

    def test_invalidated_upstream_also_cascades(self, store, allocator, verifier):
        chain = write_chain(store, allocator)
        CascadeInvalidation(store=store).cascade(
            chain[ObjectType.PATTERN].object_id,
            ObjectStatus.INVALIDATED,
            "upstream",
        )
        assert verifier.verify_constraint("I6").holds

    def test_superseded_upstream_is_not_an_i6_violation(
        self, store, allocator, verifier
    ):
        """D-01a: dependents of a superseded version remain valid."""
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.SUPERSEDED, "replaced")
        assert verifier.verify_constraint("I6").holds


# ===========================================================================
# I7 -- confidence ceiling after upstream change
# ===========================================================================

class TestI7CeilingHolds:
    def test_clean_store_holds(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert verifier.verify_constraint("I7").holds

    def test_ceiling_breach_detected(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator, support=0.9, assertion=0.9)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])

        from oip.contract import Confidence
        object.__setattr__(
            evidence.attributes, "confidence", Confidence.create(0.2, 0.2)
        )

        report = verifier.verify_constraint("I7")
        assert not report.holds
        assert report.violations[0].object_id == fact.object_id
        assert "exceeds upstream" in report.violations[0].detail

    def test_re_verified_against_current_upstream(self, store, allocator, verifier):
        """I7 is continuous: an upstream change can breach a passed ceiling."""
        evidence = write_evidence(store, allocator, support=0.8, assertion=0.8)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert verifier.verify_constraint("I7").holds

        from oip.contract import Confidence
        object.__setattr__(
            evidence.attributes, "confidence", Confidence.create(0.1, 0.1)
        )
        assert not verifier.verify_constraint("I7").holds

    def test_missing_upstream_deferred_to_i4(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        del store._objects[evidence.object_id]
        assert verifier.verify_constraint("I7").holds  # I4 reports it instead


# ===========================================================================
# I8 -- REJECTED never consumed  (AC3)
# ===========================================================================

class TestI8PreventsRejectedInput:
    def test_rejected_upstream_blocks_the_write(self, store, allocator):
        """AC3: the defining requirement."""
        evidence = write_evidence(store, allocator)
        store.transition(evidence.object_id, ObjectStatus.REJECTED, "declined")
        with pytest.raises(WriteRejectedError) as exc:
            write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert "I8" in exc.value.failure.rule_ids

    @pytest.mark.parametrize(
        "status",
        [ObjectStatus.REJECTED, ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED,
         ObjectStatus.SUPERSEDED, ObjectStatus.ARCHIVED],
    )
    def test_no_non_active_upstream_is_consumable(self, store, allocator, status):
        """Only ACTIVE objects are current knowledge. [R-2]"""
        evidence = write_evidence(store, allocator)
        corrupt_status(store, evidence.object_id, status, "planted")
        with pytest.raises(WriteRejectedError) as exc:
            write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert "I8" in exc.value.failure.rule_ids

    def test_active_upstream_accepted(self, store, allocator):
        evidence = write_evidence(store, allocator)
        fact = write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert store.get(fact.object_id).status is ObjectStatus.ACTIVE

    def test_one_bad_parent_blocks_the_write(self, store, allocator):
        good = write_evidence(store, allocator)
        bad = write_evidence(store, allocator)
        store.transition(bad.object_id, ObjectStatus.REJECTED, "declined")
        with pytest.raises(WriteRejectedError) as exc:
            write_derived(store, allocator, ObjectType.FACT, [good, bad])
        assert "I8" in exc.value.failure.rule_ids

    def test_detail_names_the_offending_upstream(self, store, allocator):
        evidence = write_evidence(store, allocator)
        store.transition(evidence.object_id, ObjectStatus.REJECTED, "declined")
        with pytest.raises(WriteRejectedError):
            write_derived(store, allocator, ObjectType.FACT, [evidence])
        record = store.failure_records[-1]
        detail = record.failed_rules[0].detail
        assert evidence.object_id in detail and "REJECTED" in detail

    def test_i8_is_preventive(self, verifier):
        assert verifier.CONSTRAINT_MODES["I8"] is ConstraintMode.PREVENTIVE

    def test_detective_check_finds_planted_violations(
        self, store, allocator, verifier
    ):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        corrupt_status(store, evidence.object_id, ObjectStatus.REJECTED, "planted")

        report = verifier.verify_constraint("I8")
        assert not report.holds
        assert "re-entered the pipeline" in report.violations[0].detail

    def test_evidence_has_no_upstream_to_check(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.EVIDENCE,
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = i8_inputs_are_consumable(
            AcceptanceContext(attributes=attributes)
        )
        assert result.outcome is RuleOutcome.SKIP

    def test_skips_without_a_status_provider(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = i8_inputs_are_consumable(
            AcceptanceContext(attributes=attributes, upstream_status=None)
        )
        assert result.outcome is RuleOutcome.SKIP

    def test_unresolved_upstream_deferred_to_v3(self, allocator):
        attributes = build_attrs(
            allocator.new_object(), ObjectType.FACT,
            (("obj-ev-1", ObjectType.EVIDENCE),),
            status=ObjectStatus.ACTIVE, status_reason=None,
        )
        result = i8_inputs_are_consumable(
            AcceptanceContext(
                attributes=attributes, upstream_status=lambda oid: None
            )
        )
        assert result.outcome is RuleOutcome.SKIP
        assert "see V3" in result.detail


# ===========================================================================
# Reporting surface and N-10 compliance
# ===========================================================================

class TestReportingSurface:
    def test_report_bool_reflects_holding(self, store, allocator, verifier):
        write_chain(store, allocator)
        assert bool(verifier.verify())

    def test_violations_filterable_by_constraint(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")

        report = verifier.verify()
        assert report.for_constraint("I6")
        assert report.for_constraint("I1") == ()

    def test_breached_constraints_listed_once(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        for _ in range(3):
            write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        assert verifier.verify().breached_constraints() == ("I6",)

    def test_violations_convert_to_failure_records(self, store, allocator, verifier):
        """N-10: violations are recorded, not raised, by default."""
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")

        report = verifier.verify()
        records = verifier.failure_records(report)
        assert len(records) == len(report.violations)
        assert records[0].engine_configuration_ref == "integrity-audit"

    def test_assert_holds_raises_on_breach(self, store, allocator, verifier):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        with pytest.raises(IntegrityError):
            verifier.assert_holds()

    def test_store_assert_integrity_raises(self, store, allocator):
        evidence = write_evidence(store, allocator)
        write_derived(store, allocator, ObjectType.FACT, [evidence])
        store.transition(evidence.object_id, ObjectStatus.RETRACTED, "withdrawn")
        with pytest.raises(IntegrityError):
            store.assert_integrity()

    def test_unknown_constraint_rejected(self, verifier):
        with pytest.raises(IntegrityError):
            verifier.verify_constraint("I99")

    def test_violation_renders_readably(self):
        text = str(Violation("I5", "obj-1", "two ACTIVE versions"))
        assert "I5" in text and "obj-1" in text

    def test_empty_report_helpers(self):
        report = IntegrityReport()
        assert report.holds and report.breached_constraints() == ()


# ===========================================================================
# Compatibility with V1-V12
# ===========================================================================

class TestCompatibility:
    def test_universal_i8_and_type_rules_registered(self, store):
        """V1-V12 universal, I8 preventive, E-V/F-V/P-V/PT-V/O-V/S-V/V-V/X-V/FR-V type-specific."""
        assert set(store.acceptance.rule_ids) == (
            {f"V{i}" for i in range(1, 13)}
            | {"I8"}
            | {f"E-V{i}" for i in range(1, 7)}
            | {f"F-V{i}" for i in range(1, 7)}
            | {f"P-V{i}" for i in range(1, 7)}
            | {f"PT-V{i}" for i in range(1, 7)}
            | {f"O-V{i}" for i in range(1, 8)}
            | {f"S-V{i}" for i in range(1, 7)}
            | {f"V-V{i}" for i in range(1, 7)}
            | {f"X-V{i}" for i in range(1, 7)}
            | {f"FR-V{i}" for i in range(1, 7)}
        )

    def test_valid_writes_still_accepted(self, store, allocator):
        chain = write_chain(store, allocator)
        assert len(chain) == 7
        assert store.verify_integrity().holds

    def test_validation_failures_unaffected(self, store, allocator):
        from oip.enums import Engine
        evidence = write_evidence(store, allocator)
        identity = allocator.new_object()
        upstream = ((evidence.object_id, ObjectType.EVIDENCE),)
        with pytest.raises(WriteRejectedError) as exc:
            store.write(
                build_attrs(
                    identity, ObjectType.FACT, upstream,
                    engine=Engine.RESEARCH,
                    status=ObjectStatus.ACTIVE, status_reason=None,
                    upstream_ceiling=(
                        evidence.attributes.confidence.effective_confidence
                    ),
                ),
                build_lineage(identity.object_id, ObjectType.FACT, upstream),
            )
        assert "V7" in exc.value.failure.rule_ids

    def test_cascade_then_verify_is_clean(self, store, allocator):
        chain = write_chain(store, allocator)
        CascadeInvalidation(store=store).retract(
            chain[ObjectType.EVIDENCE].object_id, "withdrawn"
        )
        assert store.verify_integrity().holds
        assert store.graph_diverges() == ()


# ===========================================================================
# Property-based
# ===========================================================================

@settings(max_examples=40, deadline=None)
@given(count=st.integers(min_value=1, max_value=15))
def test_independent_lineages_never_breach_i5(count):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    for _ in range(count):
        write_evidence(store, allocator)
    assert IntegrityVerifier(store=store).verify_constraint("I5").holds


@settings(max_examples=40, deadline=None)
@given(depth=st.integers(min_value=1, max_value=8))
def test_cascade_always_satisfies_i6(depth):
    """AC2 over arbitrary chain depth."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    current = evidence
    for _ in range(depth):
        current = write_derived(store, allocator, ObjectType.FACT, [current])

    CascadeInvalidation(store=store).retract(evidence.object_id, "withdrawn")
    assert IntegrityVerifier(store=store).verify_constraint("I6").holds


@settings(max_examples=40, deadline=None)
@given(
    status=st.sampled_from(
        [s for s in ObjectStatus if s is not ObjectStatus.PROPOSED]
    )
)
def test_i8_blocks_every_non_active_upstream(status):
    """AC3 over every reachable upstream status."""
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    if status is not ObjectStatus.ACTIVE:
        corrupt_status(store, evidence.object_id, status, "planted")

    if status is ObjectStatus.ACTIVE:
        assert write_derived(store, allocator, ObjectType.FACT, [evidence])
    else:
        with pytest.raises(WriteRejectedError) as exc:
            write_derived(store, allocator, ObjectType.FACT, [evidence])
        assert "I8" in exc.value.failure.rule_ids


@settings(max_examples=30, deadline=None)
@given(fan=st.integers(min_value=1, max_value=10))
def test_clean_stores_always_hold_all_constraints(fan):
    store, allocator = KnowledgeStore(), IdentityAllocator()
    evidence = write_evidence(store, allocator)
    for _ in range(fan):
        write_derived(store, allocator, ObjectType.FACT, [evidence])
    report = IntegrityVerifier(store=store).verify()
    assert report.holds, report.violations
