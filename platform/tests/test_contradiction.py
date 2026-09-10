"""Contract tests for Fact contradiction detection. [F-C1, R-06, OQ-03]

Task: T03.1.6

Architecture References:
- F-C1     RATIFIED fact contradiction semantics (2026-09-09):
           ESTABLISHED CONTRADICTION = six-condition conjunction (same
           subject, same predicate, IDENTICAL qualifier, both values
           quantified, same unit, values outside the coarser stated
           precision). Fail-closed: "cannot establish contradiction"
           never links. Type-blind: claim_type/attributed_to are never
           consulted or altered (F-V4 preserved). Recorded once, on the
           NEW Fact's contradicts attribute; peers never mutated; both
           Facts remain ACTIVE; linked, never resolved.
- R-06     CONTRADICTS is in the closed ten-type taxonomy and resolves
           OQ-03 toward representing disagreement rather than selecting
           a winner.
- S-3      The comparison frame (subject/predicate/qualifier/value).
           NOT_EQUIVALENT is NOT automatically contradiction: incomparable
           and merely-different pairs also assess NOT_EQUIVALENT and
           MUST NOT link (F-C1 R4/R9).
- F-V4     claim_type/attributed_to untouched by detection; all four
           type pairings detect identically on content.
- T03.1.4  The DUPLICATES recording pattern CONTRADICTS mirrors; the
           two peer sets are structurally disjoint.

T03.1.6 acceptance criteria under test:
  AC1  Incompatible claims linked, not silently resolved
  AC2  Both Facts remain ACTIVE

The 24-row matrix of the approved execution specification
(platform/validation/T03.1.6-specification.md §14) is covered one row
per test, annotated [matrix N]. The four categories are proven
explicitly and never collapsed: EQUIVALENT (merge), CONTRADICTORY
(link), INCOMPARABLE (no link), MERELY DIFFERENT (no link).
"""

from __future__ import annotations

from datetime import timedelta

from oip.claim import Claim, Quantity, UNQUALIFIED, Verdict
from oip.enums import ObjectStatus
from oip.extraction import established_contradiction, extract
from oip.fact import ClaimType
from tests.test_extraction import TICK, VENDOR, Rig, vendor_rig

SUBJECT = "churn rate"
PREDICATE = "stands at"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _acquire(rig: Rig, source: str, text: str) -> str:
    """Acquire one Evidence whose content contains `text` verbatim."""
    return rig.acquire(source, VENDOR, f"Q3 report: {text}.")


def _extract(
    rig: Rig,
    ref: str,
    *,
    anchor: str,
    value: Quantity | None = None,
    value_text: str | None = None,
    subject: str = SUBJECT,
    predicate: str = PREDICATE,
    qualifier: str = UNQUALIFIED,
    claim_type: ClaimType = ClaimType.ASSERTION,
    attributed_to: str | None = None,
    clock=None,
):
    """Extract one claim, defaulting to the churn-rate frame."""
    return extract(
        rig.extraction(
            evidence_ref=ref,
            subject=subject,
            predicate=predicate,
            qualifier=qualifier,
            anchor=anchor,
            value=value,
            value_text=value_text,
            claim_type=claim_type,
            attributed_to=attributed_to,
        ),
        store=rig.store,
        log=rig.log,
        clock=clock or (lambda: TICK),
    )


def _clock(offset_seconds: int):
    return lambda: TICK + timedelta(seconds=offset_seconds)


def _stored(rig: Rig, outcome):
    fact = rig.store.get_fact(outcome.object_id)
    assert fact is not None
    return fact


def _two_source_rig():
    rig = vendor_rig("src-a", "src-b")
    ra = _acquire(rig, "src-a", "churn rate stands at 3.5 percent")
    rb = _acquire(rig, "src-b", "churn rate stands at 9.9 percent")
    return rig, ra, rb


def _conflicting_pair(claim_type_a=ClaimType.ASSERTION, attributed_a=None,
                      claim_type_b=ClaimType.ASSERTION, attributed_b=None):
    """Two extractions with identical frames and conflicting values
    (3.5% vs 9.9%, tolerance 0.5): a genuine established contradiction
    under F-C1 R1, whatever the claim types."""
    rig, ra, rb = _two_source_rig()
    first = _extract(
        rig, ra, anchor="churn rate stands at 3.5 percent",
        value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
        claim_type=claim_type_a, attributed_to=attributed_a,
        clock=_clock(0),
    )
    second = _extract(
        rig, rb, anchor="churn rate stands at 9.9 percent",
        value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
        claim_type=claim_type_b, attributed_to=attributed_b,
        clock=_clock(1),
    )
    return rig, first, second


def _mixed_corpus():
    """P1 scoped (Q3, 7.0) · P2 other subject (9.0) · P3 same frame
    (NONE, 9.0) · new (NONE, 7.0): P1 is CONTAINMENT-DUPLICATES,
    P2 is merely different, P3 is the contradiction."""
    rig = vendor_rig("src-a", "src-b", "src-c", "src-d")
    r1 = _acquire(rig, "src-a",
                  "churn rate in Q3 2026 stands at 7.0 percent")
    r2 = _acquire(rig, "src-b", "logo churn stands at 9.0 percent")
    r3 = _acquire(rig, "src-c", "churn rate stands at 9.0 percent")
    r4 = _acquire(rig, "src-d", "churn rate stands at 7.0 percent")
    p1 = _extract(
        rig, r1, anchor="churn rate in Q3 2026 stands at 7.0 percent",
        value=Quantity(7.0, 0.5, "%"), value_text="7.0 percent",
        qualifier="Q3 2026", clock=_clock(0),
    )
    p2 = _extract(
        rig, r2, anchor="logo churn stands at 9.0 percent",
        subject="logo churn",
        value=Quantity(9.0, 0.5, "%"), value_text="9.0 percent",
        clock=_clock(1),
    )
    p3 = _extract(
        rig, r3, anchor="churn rate stands at 9.0 percent",
        value=Quantity(9.0, 0.5, "%"), value_text="9.0 percent",
        clock=_clock(2),
    )
    new = _extract(
        rig, r4, anchor="churn rate stands at 7.0 percent",
        value=Quantity(7.0, 0.5, "%"), value_text="7.0 percent",
        clock=_clock(3),
    )
    return rig, p1, p2, p3, new


# ---------------------------------------------------------------------------
# The primitive itself  [matrix 24 -- fail-closed, per-condition]
# ---------------------------------------------------------------------------


class TestEstablishedContradictionPrimitive:
    def test_all_six_conditions_hold(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(9.9, 0.5, "%"))
        assert established_contradiction(a, b) is True

    def test_c1_subject_differs(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim("revenue churn", PREDICATE, UNQUALIFIED,
                  Quantity(9.9, 0.5, "%"))
        assert established_contradiction(a, b) is False

    def test_c2_predicate_differs(self):
        # antonymic predicates are wording, not structure [F-C1: the
        # accepted false-negative class; "checkable, not opinion"]
        a = Claim("churn", "decreased", UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim("churn", "increased", UNQUALIFIED, Quantity(9.9, 0.5, "%"))
        assert established_contradiction(a, b) is False

    def test_c3_qualifier_differs(self):
        a = Claim(SUBJECT, PREDICATE, "Q3", Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(9.9, 0.5, "%"))
        assert established_contradiction(a, b) is False

    def test_c4_one_side_unquantified(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, None)
        assert established_contradiction(a, b) is False
        assert established_contradiction(b, a) is False

    def test_c4_both_unquantified(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, None)
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, None)
        assert established_contradiction(a, b) is False

    def test_c5_unit_mismatch(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(9.9, 0.5, "pp"))
        assert established_contradiction(a, b) is False

    def test_c6_within_tolerance_is_agreement(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.9, 0.5, "%"))
        assert established_contradiction(a, b) is False

    def test_c6_boundary_equality_is_agreement_not_contradiction(self):
        # |3.5 - 4.0| == 0.5 == max tolerance: agreement, merge territory
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(4.0, 0.5, "%"))
        assert established_contradiction(a, b) is False

    def test_symmetric_in_arguments(self):
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(9.9, 0.5, "%"))
        assert established_contradiction(a, b) \
            == established_contradiction(b, a)

    def test_qualifier_normalisation(self):
        # NONE / none / None are one unqualified state [S-3]
        a = Claim(SUBJECT, PREDICATE, "NONE", Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, "none", Quantity(9.9, 0.5, "%"))
        assert established_contradiction(a, b) is True
        # qualified: normalised-equal strings are the same qualifier
        c = Claim(SUBJECT, PREDICATE, "Q3 2026", Quantity(3.5, 0.5, "%"))
        d = Claim(SUBJECT, PREDICATE, "q3  2026", Quantity(9.9, 0.5, "%"))
        assert established_contradiction(c, d) is True

    def test_not_the_forbidden_values_agree_shortcut(self):
        # values_agree is False here (one side unquantified) -- but that
        # is INCOMPARABILITY, not disagreement. The forbidden shortcut
        # `not values_agree(...)` would link this pair; F-C1 R1 must not.
        a = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(3.5, 0.5, "%"))
        b = Claim(SUBJECT, PREDICATE, UNQUALIFIED, None)
        assert a.values_agree(b) is False
        assert established_contradiction(a, b) is False
        # and the unit-mismatch variant of the same trap
        c = Claim(SUBJECT, PREDICATE, UNQUALIFIED, Quantity(9.9, 0.5, "pp"))
        assert a.values_agree(c) is False
        assert established_contradiction(a, c) is False

    def test_total_pure_never_raises(self):
        # every constructible pair yields a bool; no state, no exception
        values = [None, Quantity(3.5, 0.5, "%"), Quantity(9.9, 0.5, "pp"),
                  Quantity(3.5, 0.0, "%")]
        qualifiers = [UNQUALIFIED, "Q3", "FY26"]
        subjects = [SUBJECT, "other subject"]
        predicates = [PREDICATE, "other predicate"]
        for s1 in subjects:
            for p1 in predicates:
                for q1 in qualifiers:
                    for v1 in values:
                        a = Claim(s1, p1, q1, v1)
                        for s2 in subjects:
                            for p2 in predicates:
                                for q2 in qualifiers:
                                    for v2 in values:
                                        assert isinstance(
                                            established_contradiction(
                                                a, Claim(s2, p2, q2, v2)
                                            ),
                                            bool,
                                        )


# ---------------------------------------------------------------------------
# Category A: EQUIVALENT  [matrix 2, 5 -- existing merge path, unchanged]
# ---------------------------------------------------------------------------


class TestEquivalentMergesWithoutContradiction:
    def test_equivalent_values_merge_no_link(self):
        rig, ra, rb = _two_source_rig()  # 3.5 vs 9.9 content; use 3.5/3.6
        rb = _acquire(rig, "src-b", "churn rate stands at 3.6 percent")
        first = _extract(
            rig, ra, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="churn rate stands at 3.6 percent",
            value=Quantity(3.6, 0.5, "%"), value_text="3.6 percent",
            clock=_clock(1),
        )
        # category A: EQUIVALENT -> merge, no new Fact, no link of any kind
        assert second.merged_into is not None
        assert second.contradicts == ()
        assert second.duplicates == ()
        assert len(rig.store.facts.active_facts()) == 1

    def test_precision_boundary_is_agreement(self):
        rig, ra, rb = _two_source_rig()
        rb = _acquire(rig, "src-b", "churn rate stands at 4.0 percent")
        first = _extract(
            rig, ra, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="churn rate stands at 4.0 percent",
            value=Quantity(4.0, 0.5, "%"), value_text="4.0 percent",
            clock=_clock(1),
        )
        # |3.5 - 4.0| == 0.5 == tolerance: agreement -> merge, no link
        assert second.merged_into is not None
        assert second.contradicts == ()


# ---------------------------------------------------------------------------
# Category B: CONTRADICTORY  [matrix 1, 7 -- AC1 + AC2]
# ---------------------------------------------------------------------------


class TestContradictoryLinks:
    def test_genuine_contradiction_linked_both_active(self):
        rig, first, second = _conflicting_pair()
        # category B: NOT_EQUIVALENT + six-condition result -> CONTRADICTS
        assert second.merged_into is None
        assert second.contradicts == (first.object_id,)
        stored = _stored(rig, second)
        assert stored.attributes.contradicts == (first.object_id,)
        # AC2: both Facts remain ACTIVE; nothing was resolved
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        assert rig.store.find(second.object_id).status is ObjectStatus.ACTIVE
        assert stored.attributes.status_reason is None
        # no merge, no retraction, no supersession of either Fact
        assert len(rig.store.facts.active_facts()) == 2
        # AC1 auditability: the link is named in the explanation, never silent
        assert "CONTRADICTS recorded" in stored.attributes.explanation.reasoning

    def test_same_explicit_qualifier_disagreement_links(self):
        rig = vendor_rig("src-a", "src-b")
        ra = _acquire(rig, "src-a",
                      "churn rate in Q3 2026 stands at 3.5 percent")
        rb = _acquire(rig, "src-b",
                      "churn rate in Q3 2026 stands at 9.9 percent")
        first = _extract(
            rig, ra, anchor="churn rate in Q3 2026 stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            qualifier="Q3 2026", clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="churn rate in Q3 2026 stands at 9.9 percent",
            value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
            qualifier="Q3 2026", clock=_clock(1),
        )
        # identical explicit qualifier + disagreement -> contradiction
        assert second.contradicts == (first.object_id,)
        assert second.duplicates == ()


# ---------------------------------------------------------------------------
# Category C: INCOMPARABLE  [matrix 3, 4, 6 -- no CONTRADICTS, fail-closed]
# ---------------------------------------------------------------------------


class TestIncomparableNoLink:
    def test_unquantified_side_no_link(self):
        rig, ra, rb = _two_source_rig()
        first = _extract(
            rig, ra, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="churn rate stands at 9.9 percent",
            value=None, clock=_clock(1),
        )
        # one side unquantified: cannot establish contradiction
        assert second.contradicts == ()
        assert second.duplicates == ()
        assert second.merged_into is None
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.NOT_EQUIVALENT
        }
        assert len(rig.store.facts.active_facts()) == 2

    def test_unit_mismatch_no_link(self):
        rig, ra, rb = _two_source_rig()
        first = _extract(
            rig, ra, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="churn rate stands at 9.9 percent",
            value=Quantity(9.9, 0.5, "pp"), value_text="9.9 percent",
            clock=_clock(1),
        )
        # no unit conversion exists: agreement AND disagreement are both
        # undecidable -> fail-closed, no link
        assert second.contradicts == ()
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.NOT_EQUIVALENT
        }

    def test_qualifier_scope_mismatch_no_contradiction(self):
        rig = vendor_rig("src-a", "src-b", "src-c")
        ra = _acquire(rig, "src-a",
                      "churn rate in Q3 2026 stands at 3.5 percent")
        rb = _acquire(rig, "src-b", "churn rate stands at 3.5 percent")
        rc = _acquire(rig, "src-c", "churn rate stands at 9.9 percent")
        scoped = _extract(
            rig, ra, anchor="churn rate in Q3 2026 stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            qualifier="Q3 2026", clock=_clock(0),
        )
        broad_same_value = _extract(
            rig, rb, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(1),
        )
        broad_other_value = _extract(
            rig, rc, anchor="churn rate stands at 9.9 percent",
            value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
            clock=_clock(2),
        )
        # agreeing values, unqualified-vs-scoped -> CONTAINMENT:
        # DUPLICATES, never CONTRADICTS [Q2 disjointness]
        assert broad_same_value.duplicates == (scoped.object_id,)
        assert broad_same_value.contradicts == ()
        # disagreeing values across scopes: still no CONTRADICTS with
        # the SCOPED peer -- a narrow/broad disagreement is not evidence
        # against the other scope. (The same-frame peer IS contradicted:
        # two unqualified churn claims with different values conflict.)
        assert broad_other_value.contradicts == (broad_same_value.object_id,)
        assert scoped.object_id not in broad_other_value.contradicts
        assert broad_other_value.duplicates == ()


# ---------------------------------------------------------------------------
# Category D: MERELY DIFFERENT  [matrix 18, 19 -- no link]
# ---------------------------------------------------------------------------


class TestMerelyDifferentNoLink:
    def test_different_subject_no_link(self):
        rig = vendor_rig("src-a", "src-b")
        ra = _acquire(rig, "src-a", "churn rate stands at 3.5 percent")
        rb = _acquire(rig, "src-b", "logo churn stands at 9.9 percent")
        first = _extract(
            rig, ra, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="logo churn stands at 9.9 percent",
            subject="logo churn",
            value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
            clock=_clock(1),
        )
        # different subjects: logically independent claims, no link
        assert second.contradicts == ()
        assert second.duplicates == ()
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.NOT_EQUIVALENT
        }
        assert len(rig.store.facts.active_facts()) == 2

    def test_different_predicate_no_link_even_with_conflict_shaped_values(
        self,
    ):
        # the sharpest merely-different case: every condition holds
        # except the predicate -- antonymy is wording, not structure
        rig = vendor_rig("src-a", "src-b")
        ra = _acquire(rig, "src-a", "churn decreased to 3.5 percent")
        rb = _acquire(rig, "src-b", "churn increased to 9.9 percent")
        first = _extract(
            rig, ra, anchor="churn decreased to 3.5 percent",
            subject="churn", predicate="decreased to",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        second = _extract(
            rig, rb, anchor="churn increased to 9.9 percent",
            subject="churn", predicate="increased to",
            value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
            clock=_clock(1),
        )
        # both retained, never linked, never resolved [AC1's other half]
        assert second.contradicts == ()
        assert second.merged_into is None
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        assert rig.store.find(second.object_id).status is ObjectStatus.ACTIVE


# ---------------------------------------------------------------------------
# NOT_EQUIVALENT != CONTRADICTS  [matrix 10 -- subset + disjointness]
# ---------------------------------------------------------------------------


class TestNotEquivalentIsNotAutomaticallyContradiction:
    def test_contradicts_is_strict_subset_of_not_equivalent(self):
        _, p1, p2, p3, new = _mixed_corpus()
        verdicts = {other.object_id: result.verdict
                    for other, result in new.equivalence}
        for target in new.contradicts:
            assert verdicts[target] is Verdict.NOT_EQUIVALENT

    def test_disjoint_from_duplicates_and_unique(self):
        _, p1, p2, p3, new = _mixed_corpus()
        # the two link kinds partition their peers; no id repeats
        assert set(new.contradicts).isdisjoint(new.duplicates)
        assert len(set(new.contradicts)) == len(new.contradicts)
        assert new.contradicts == (p3.object_id,)
        assert new.duplicates == (p1.object_id,)
        # the different-subject peer is linked by neither
        assert p2.object_id not in new.contradicts + new.duplicates


# ---------------------------------------------------------------------------
# Recording semantics  [matrix 8, 9, 21, 22, 23]
# ---------------------------------------------------------------------------


class TestRecording:
    def test_multiple_contradictory_peers_all_recorded_in_order(self):
        rig = vendor_rig("src-a", "src-b", "src-c")
        ra = _acquire(rig, "src-a", "churn rate stands at 3.5 percent")
        rb = _acquire(rig, "src-b", "churn rate stands at 9.9 percent")
        rc = _acquire(rig, "src-c", "churn rate stands at 12.0 percent")
        a = _extract(
            rig, ra, anchor="churn rate stands at 3.5 percent",
            value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
            clock=_clock(0),
        )
        b = _extract(
            rig, rb, anchor="churn rate stands at 9.9 percent",
            value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
            clock=_clock(1),
        )
        c = _extract(
            rig, rc, anchor="churn rate stands at 12.0 percent",
            value=Quantity(12.0, 0.5, "%"), value_text="12.0 percent",
            clock=_clock(2),
        )
        # every established contradiction is recorded, in ACTIVE
        # registry (insertion) order -- deterministic [N-4]
        assert b.contradicts == (a.object_id,)
        assert c.contradicts == (a.object_id, b.object_id)

    def test_no_self_reference(self):
        rig, first, second = _conflicting_pair()
        # the new Fact is not yet registered when targets are computed;
        # V12 is the acceptance-time backstop and the write succeeded
        assert second.object_id not in second.contradicts
        stored = _stored(rig, second)
        assert stored.object_id not in stored.attributes.contradicts

    def test_duplicates_and_contradicts_coexist_on_one_fact(self):
        # [matrix 21/22] one Fact may carry both link kinds, to
        # DIFFERENT peers; the store's acceptance path (incl. V12)
        # accepted the combined attribute set
        rig, p1, p2, p3, new = _mixed_corpus()
        stored = _stored(rig, new)
        assert stored.attributes.duplicates == (p1.object_id,)
        assert stored.attributes.contradicts == (p3.object_id,)
        assert rig.store.find(new.object_id).status is ObjectStatus.ACTIVE

    def test_deterministic_ordering_and_repeatability(self):
        def scenario():
            rig = vendor_rig("src-a", "src-b", "src-c")
            ra = _acquire(rig, "src-a", "churn rate stands at 3.5 percent")
            rb = _acquire(rig, "src-b", "churn rate stands at 9.9 percent")
            rc = _acquire(rig, "src-c", "churn rate stands at 12.0 percent")
            a = _extract(
                rig, ra, anchor="churn rate stands at 3.5 percent",
                value=Quantity(3.5, 0.5, "%"), value_text="3.5 percent",
                clock=_clock(0),
            )
            b = _extract(
                rig, rb, anchor="churn rate stands at 9.9 percent",
                value=Quantity(9.9, 0.5, "%"), value_text="9.9 percent",
                clock=_clock(1),
            )
            c = _extract(
                rig, rc, anchor="churn rate stands at 12.0 percent",
                value=Quantity(12.0, 0.5, "%"), value_text="12.0 percent",
                clock=_clock(2),
            )
            return rig, a, b, c

        rig1, a1, b1, c1 = scenario()
        rig2, a2, b2, c2 = scenario()
        # same inputs -> same outputs: identical ordering, both runs
        assert c1.contradicts == (a1.object_id, b1.object_id)
        assert c2.contradicts == (a2.object_id, b2.object_id)
        assert [t for t in c1.contradicts] == [
            f.object_id for f in (a1, b1)
        ]
        assert [t for t in c2.contradicts] == [
            f.object_id for f in (a2, b2)
        ]


# ---------------------------------------------------------------------------
# Lifecycle invariants  [matrix 11, 12, 13, 20]
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_peer_never_mutated(self):
        rig, first, second = _conflicting_pair()
        peer_fact = rig.store.get_fact(first.object_id)
        peer_stored = rig.store.find(first.object_id)
        # the recording Fact holds the link; the peer holds nothing new
        assert second.contradicts == (first.object_id,)
        assert peer_fact.attributes.contradicts == ()
        # byte-for-byte the same object: no re-version, no field change
        assert rig.store.get_fact(first.object_id) == peer_fact
        assert rig.store.find(first.object_id) == peer_stored
        # no extra version was created for the peer's lineage
        assert len(rig.store.facts) == 2
        assert len(rig.store.facts.active_facts()) == 2
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE

    def test_new_fact_remains_active(self):
        rig, first, second = _conflicting_pair()
        stored = _stored(rig, second)
        assert stored.attributes.status is ObjectStatus.ACTIVE
        assert stored.attributes.status_reason is None
        assert rig.store.find(second.object_id).status is ObjectStatus.ACTIVE

    def test_versioning_preserves_contradiction_links(self):
        rig, first, second = _conflicting_pair()
        rc = _acquire(rig, "src-b", "churn rate stands at 9.95 percent")
        # a third extraction EQUIVALENT to the second merges into its
        # lineage; the merged version must inherit the CONTRADICTS links
        third = _extract(
            rig, rc, anchor="churn rate stands at 9.95 percent",
            value=Quantity(9.95, 0.5, "%"), value_text="9.95 percent",
            clock=_clock(2),
        )
        assert third.merged_into is not None
        head = rig.store.get_fact(third.merged_into)
        assert head is not None
        assert head.attributes.contradicts == (first.object_id,)
        # the peer of the contradiction is still untouched and ACTIVE
        assert rig.store.get_fact(first.object_id).attributes.contradicts == ()
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        # the outcome of a MERGE reports no links of its own [F-C1 R6]
        assert third.contradicts == ()
        assert third.duplicates == ()

    def test_historical_one_sided_detection_no_retroactive_mutation(self):
        # the later member records; the earlier member is never
        # retroactively linked -- which is also why pairs that both
        # predate the capability stay unlinked forever [F-C1 R6]
        rig, first, second = _conflicting_pair()
        assert second.contradicts == (first.object_id,)
        assert _stored(rig, first).attributes.contradicts == ()
        assert _stored(rig, second).attributes.contradicts == (
            first.object_id,
        )
        # and a still-later peer links BOTH, again one-sided only
        rd = _acquire(rig, "src-b", "churn rate stands at 12.0 percent")
        third = _extract(
            rig, rd, anchor="churn rate stands at 12.0 percent",
            value=Quantity(12.0, 0.5, "%"), value_text="12.0 percent",
            clock=_clock(3),
        )
        assert third.contradicts == (first.object_id, second.object_id)
        assert _stored(rig, first).attributes.contradicts == ()
        assert _stored(rig, second).attributes.contradicts == (
            first.object_id,
        )


# ---------------------------------------------------------------------------
# F-V4 type-blindness  [matrix 14, 15, 16, 17]
# ---------------------------------------------------------------------------


class TestClaimTypeBlindness:
    def test_assertion_vs_assertion(self):
        rig, first, second = _conflicting_pair(
            claim_type_a=ClaimType.ASSERTION,
            claim_type_b=ClaimType.ASSERTION,
        )
        assert second.contradicts == (first.object_id,)
        assert _stored(rig, first).claim_type is ClaimType.ASSERTION
        assert _stored(rig, second).claim_type is ClaimType.ASSERTION
        assert _stored(rig, first).attributed_to is None
        assert _stored(rig, second).attributed_to is None

    def test_assertion_vs_attributed_opinion(self):
        rig, first, second = _conflicting_pair(
            claim_type_a=ClaimType.ASSERTION,
            claim_type_b=ClaimType.ATTRIBUTED_OPINION,
            attributed_b="the CFO",
        )
        # identical content conflict -> identical link, no winner, and
        # the classification of either Fact is untouched [F-V4 INV-1..4]
        assert second.contradicts == (first.object_id,)
        assert _stored(rig, first).claim_type is ClaimType.ASSERTION
        assert _stored(rig, second).claim_type is ClaimType.ATTRIBUTED_OPINION
        assert _stored(rig, second).attributed_to == "the CFO"
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        assert rig.store.find(second.object_id).status is ObjectStatus.ACTIVE

    def test_attributed_opinion_vs_assertion(self):
        rig, first, second = _conflicting_pair(
            claim_type_a=ClaimType.ATTRIBUTED_OPINION,
            attributed_a="Analyst A",
            claim_type_b=ClaimType.ASSERTION,
        )
        assert second.contradicts == (first.object_id,)
        assert _stored(rig, first).claim_type is ClaimType.ATTRIBUTED_OPINION
        assert _stored(rig, first).attributed_to == "Analyst A"
        assert _stored(rig, second).claim_type is ClaimType.ASSERTION
        assert _stored(rig, second).attributed_to is None

    def test_opinion_vs_opinion_different_speakers(self):
        # the market-disagreement case OQ-03 exists to represent
        rig, first, second = _conflicting_pair(
            claim_type_a=ClaimType.ATTRIBUTED_OPINION,
            attributed_a="Analyst A",
            claim_type_b=ClaimType.ATTRIBUTED_OPINION,
            attributed_b="Analyst B",
        )
        assert second.contradicts == (first.object_id,)
        assert _stored(rig, first).attributed_to == "Analyst A"
        assert _stored(rig, second).attributed_to == "Analyst B"
        assert rig.store.find(first.object_id).status is ObjectStatus.ACTIVE
        assert rig.store.find(second.object_id).status is ObjectStatus.ACTIVE


# ---------------------------------------------------------------------------
# Report, not gate  [F-C1 R6 -- detection never refuses an extraction]
# ---------------------------------------------------------------------------


class TestReportNotGate:
    def test_contradiction_never_refuses_and_is_always_reported(self):
        rig, first, second = _conflicting_pair()
        # the extraction succeeded: a Fact exists, no failure recorded
        assert rig.store.get_fact(second.object_id) is not None
        assert len(rig.log) == 0
        # the S-3 report still carries the per-peer verdicts, so
        # "established" and "cannot establish" stay distinguishable
        assert {r.verdict for _, r in second.equivalence} == {
            Verdict.NOT_EQUIVALENT
        }
        assert any(
            result.reason
            for _, result in second.equivalence
        )
        # both Facts remain ACTIVE: contradiction is information [AC2]
        assert len(rig.store.facts.active_facts()) == 2
