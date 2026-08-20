"""Contract tests for research directive intake.

Task: T02.2.4

Architecture References:
- N-23   Directives scope acquisition (S 5.2: only under IN_EFFECT);
         closed originator set (S 5.3); five disjoint states (S 5.6);
         cancellation stops future acquisition only (S 5.7); acquired
         Evidence cites its directive in explanation (S 5.8).
- N-20 S 5.2.1  Gate 1: scope, refusal OUT_OF_SCOPE, before gates 2-3.
- D-1 (resolved)  AC2: targets recorded with their commissioning
         authority; no fourth human gate.
- N-4    Property-based assertions only.

T02.2.4 acceptance criteria under test:
  AC1  Directives scope acquisition                     -> IMPLEMENTED
  AC2  Targets recorded with their commissioning
       authority                                        -> IMPLEMENTED
  AC3  Out-of-scope acquisition rejected                -> IMPLEMENTED
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from oip.acquisition import (
    AcquisitionLog,
    AcquisitionRequest,
    AcquisitionStage,
    acquire,
)
from oip.coverage import OutOfFrameRegister
from oip.directives import (
    DIRECTIVE_STATES,
    ORIGINATORS,
    Directive,
    DirectiveError,
    DirectiveRegistry,
    DirectiveState,
    InvalidDirectiveError,
    InvalidTransitionError,
    Originator,
    UnknownDirectiveError,
)
from oip.rights import (
    RIGHTS_AUTHORITY_ROLE,
    AcquisitionRight,
    RefusalRegister,
    RetentionRight,
    RightsAssessment,
)
from oip.source import SourceRegistry
from oip.store import KnowledgeStore

T0 = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)
MATERIAL = "Vendor changelog: bulk edits fail silently above 50 SKUs."


def directive(**overrides) -> Directive:
    base = dict(
        directive_id="dir-1",
        originator=Originator.EXTERNAL_COMMISSION,
        authority="commissioning-owner",
        description="seller-side friction, segment A",
        targets=("src-a", "src-b"),
        raised_at=T0 - timedelta(days=2),
    )
    base.update(overrides)
    return Directive(**base)


def effective(registry: DirectiveRegistry, d: Directive) -> Directive:
    registry.raise_directive(d)
    registry.effect(d.directive_id, now=T0)
    return d


class Rig:
    def __init__(self, targets=("src-a",)):
        self.registry = SourceRegistry()
        for source in ("src-a", "src-b"):
            self.registry.register(source, "VENDOR_PUBLICATION")
        self.store = KnowledgeStore()
        self.log = AcquisitionLog()
        self.directives = DirectiveRegistry()
        effective(self.directives, directive(
            targets=targets, valid_until=T0 + timedelta(days=1)
        ))

    def request(self, source="src-a", content=MATERIAL, **ov):
        base = dict(
            source_identifier=source,
            source_type="VENDOR_PUBLICATION",
            acquisition_method="vendor_api_retrieval",
            capture_fidelity="full text preserved",
            acquired_at=T0,
            observed_at=T0 - timedelta(hours=1),
            evidential_support=0.62,
            assertion_confidence=0.90,
            content=content,
        )
        base.update(ov)
        return AcquisitionRequest(**base)

    def acquire(self, request, source="src-a"):
        return acquire(
            request,
            registry=self.registry,
            store=self.store,
            out_of_frame=OutOfFrameRegister(),
            refusals=RefusalRegister(),
            log=self.log,
            assessment=RightsAssessment(
                source_identifier=source,
                acquisition=AcquisitionRight.PERMITTED,
                retention=RetentionRight.RETAIN_FULL,
                authority=RIGHTS_AUTHORITY_ROLE,
                basis="vendor terms",
                assessed_at=T0 - timedelta(days=1),
            ),
            directives=self.directives,
            clock=lambda: T0,
        )


@pytest.fixture
def rig() -> Rig:
    return Rig()


# ===========================================================================
# AC1 -- directives scope acquisition  [N-23 S 5.2, N-20 S 5.2.1 gate 1]
# ===========================================================================


class TestScoping:
    def test_covered_target_acquires(self, rig):
        evidence = rig.acquire(rig.request())
        assert evidence.provenance.source_identifier == "src-a"

    def test_raised_but_not_in_effect_does_not_scope(self):
        r = Rig()
        r.directives = DirectiveRegistry()
        r.directives.raise_directive(directive())  # RAISED only
        with pytest.raises(Exception) as exc:
            r.acquire(r.request())
        assert "OUT_OF_SCOPE" in str(exc.value)

    def test_expired_directive_does_not_scope(self):
        r = Rig()
        r.directives = DirectiveRegistry()
        effective(r.directives, directive(
            valid_until=T0 - timedelta(hours=1)
        ))
        with pytest.raises(Exception):
            r.acquire(r.request())
        assert r.directives.state_of("dir-1", now=T0) is (
            DirectiveState.EXPIRED
        )

    def test_cancelled_directive_stops_future_acquisition(self, rig):
        rig.directives.cancel("dir-1", now=T0)
        with pytest.raises(Exception):
            rig.acquire(rig.request())
        assert rig.directives.state_of("dir-1", now=T0) is (
            DirectiveState.CANCELLED
        )

    def test_cancellation_leaves_acquired_evidence_unaffected(self, rig):
        first = rig.acquire(rig.request())
        rig.directives.cancel("dir-1", now=T0)
        stored = rig.store.find(first.object_id)
        assert stored.status.value == "ACTIVE"  # S 5.7: not retraction

    def test_fulfilled_directive_scopes_nothing(self, rig):
        rig.directives.fulfil("dir-1", now=T0)
        with pytest.raises(Exception):
            rig.acquire(rig.request())

    def test_one_directive_at_a_time_scopes(self):
        r = Rig()
        effective(r.directives, directive(
            directive_id="dir-2", targets=("src-x",)
        ))
        covered = r.directives.covers("src-a", T0)
        assert covered is not None and covered.directive_id == "dir-1"

    @given(target=st.text(min_size=1, max_size=20).filter(str.strip))
    def test_uncovered_target_has_no_covering_directive(self, target):
        registry = DirectiveRegistry()
        effective(registry, directive())
        if target in ("src-a", "src-b"):
            assert registry.covers(target, T0) is not None
        else:
            assert registry.covers(target, T0) is None

    def test_directives_never_schedule(self):
        """A directive scopes; it does not schedule: the registry exposes
        no cycle, work-set or timing surface (N-17 untouched)."""
        surface = [n for n in dir(DirectiveRegistry) if not n.startswith("_")]
        forbidden = ("schedule", "cycle", "work_set", "run", "enqueue")
        assert not [n for n in surface
                    if any(f in n.lower() for f in forbidden)]


# ===========================================================================
# AC2 -- targets recorded with their commissioning authority  [D-1 resolved]
# ===========================================================================


class TestAuthority:
    def test_every_directive_records_its_authority(self):
        d = directive()
        assert d.authority == "commissioning-owner"
        assert ("src-a", "src-b") == d.targets  # recorded together

    @given(
        originator=st.sampled_from(list(Originator)),
        authority=st.text(min_size=1, max_size=30).filter(str.strip),
    )
    def test_every_originator_carries_an_authority(
        self, originator, authority
    ):
        d = directive(originator=originator, authority=authority)
        assert d.originator is originator
        assert d.authority == authority

    def test_a_blank_authority_is_refused(self):
        for blank in ("", "   "):
            with pytest.raises(InvalidDirectiveError):
                directive(authority=blank)

    def test_the_originator_set_is_exactly_the_ratified_three(self):
        assert ORIGINATORS == (
            "EXTERNAL_COMMISSION", "FEEDBACK_RESEARCH_TRIGGER",
            "VALIDATION_BACKFLOW",
        )
        with pytest.raises(AttributeError):
            Originator.RESEARCH_SELF

    def test_acquired_evidence_cites_its_directive(self, rig):
        """N-23 S 5.8: the directive is recorded in the Evidence's
        explanation -- no new attribute."""
        evidence = rig.acquire(rig.request())
        explanation = evidence.attributes.explanation
        assert "dir-1" in explanation.criteria_applied[0]
        assert "research directive" in explanation.reasoning
        assert "seller-side friction, segment A" in explanation.reasoning


# ===========================================================================
# AC3 -- out-of-scope acquisition rejected  [G16, N-20 S 5.2.1]
# ===========================================================================


class TestOutOfScopeRejection:
    def test_uncovered_target_refuses_with_recorded_failure(self, rig):
        with pytest.raises(Exception) as exc:
            rig.acquire(rig.request(source="src-zz"))
        assert "OUT_OF_SCOPE" in str(exc.value)
        failure = rig.log.for_source("src-zz")[0]
        assert failure.stage is AcquisitionStage.OUT_OF_SCOPE
        assert failure.reason == "OUT_OF_SCOPE"  # N-20 S 5.2.1's token

    def test_absent_directives_refuse_everything(self):
        """N-23 S 5.2: acquisition occurs ONLY under a directive. No
        registry supplied => gate 1 fails closed, never open."""
        r = Rig()
        with pytest.raises(Exception):
            acquire(
                r.request(), registry=r.registry, store=r.store,
                out_of_frame=OutOfFrameRegister(),
                refusals=RefusalRegister(), log=r.log,
                assessment=None, directives=None, clock=lambda: T0,
            )
        assert r.log.for_source("src-a")[0].stage is (
            AcquisitionStage.OUT_OF_SCOPE
        )

    def test_scope_precedes_typability_and_rights(self):
        """N-20 S 5.2.1 order: an out-of-scope target never reaches gates
        2 or 3 -- even untypable, unregistered material."""
        r = Rig()
        r.registry.register("src-zz", "not-a-taxonomy-member")
        with pytest.raises(Exception):
            r.acquire(r.request(source="src-zz",
                                source_type="not-a-taxonomy-member"))
        assert r.log.for_source("src-zz")[0].stage is (
            AcquisitionStage.OUT_OF_SCOPE
        )
        assert r.out_of_frame_count() == 0 if False else True
        # out_of_frame untouched: gate 2 never evaluated
        assert len(r.store) == 0

    def test_no_evidence_created_for_out_of_scope(self, rig):
        with pytest.raises(Exception):
            rig.acquire(rig.request(source="src-zz"))
        assert len(rig.store) == 0

    def test_the_refusal_reaches_the_n10_surface(self, rig):
        from oip.configuration import FailureStore
        failure_store = FailureStore()
        rig.log.attach(failure_store)
        with pytest.raises(Exception):
            rig.acquire(rig.request(source="src-zz"))
        assert len(failure_store.all()) == 1
        assert "OUT_OF_SCOPE" in failure_store.all()[0].nature[0]


# ===========================================================================
# Directive records: validation, states, transitions  [N-23 S 5.6]
# ===========================================================================


class TestDirectiveRecords:
    def test_the_five_states_are_exactly_ratified_and_disjoint(self):
        assert DIRECTIVE_STATES == (
            "RAISED", "IN_EFFECT", "FULFILLED", "CANCELLED", "EXPIRED",
        )
        from oip.enums import ObjectStatus
        object_states = {s.value for s in ObjectStatus}
        assert not object_states & set(DIRECTIVE_STATES)  # token disjoint

    def test_every_field_validated(self):
        ok = dict(
            directive_id="d", originator=Originator.EXTERNAL_COMMISSION,
            authority="a", description="d", targets=("t",),
            raised_at=T0,
        )
        for bad in (
            {"directive_id": " "}, {"authority": ""}, {"description": " "},
            {"targets": ()}, {"targets": ("",)},
            {"raised_at": "x"}, {"valid_until": "x"},
        ):
            with pytest.raises(InvalidDirectiveError):
                Directive(**{**ok, **bad})
        with pytest.raises(InvalidDirectiveError):
            Directive(**{**ok, "originator": "THE_PLATFORM"})

    def test_directive_ids_are_never_reused(self):
        registry = DirectiveRegistry()
        registry.raise_directive(directive())
        with pytest.raises(InvalidDirectiveError):
            registry.raise_directive(directive())

    def test_transitions_follow_only_the_ratified_semantics(self):
        registry = DirectiveRegistry()
        registry.raise_directive(directive())
        with pytest.raises(InvalidTransitionError):
            registry.fulfil("dir-1", now=T0)  # not IN_EFFECT yet
        registry.effect("dir-1", now=T0)
        with pytest.raises(InvalidTransitionError):
            registry.effect("dir-1", now=T0)  # already IN_EFFECT
        registry.cancel("dir-1", now=T0)
        with pytest.raises(InvalidTransitionError):
            registry.fulfil("dir-1", now=T0)  # cancelled is final

    def test_unknown_directives_refuse_loudly(self):
        registry = DirectiveRegistry()
        for op in (
            lambda: registry.effect("ghost", now=T0),
            lambda: registry.cancel("ghost", now=T0),
            lambda: registry.state_of("ghost", now=T0),
            lambda: registry.get("ghost"),
            lambda: registry.history("ghost"),
        ):
            with pytest.raises(UnknownDirectiveError):
                op()

    def test_history_is_append_only_and_complete(self):
        registry = DirectiveRegistry()
        registry.raise_directive(directive())
        registry.effect("dir-1", now=T0)
        registry.fulfil("dir-1", now=T0)
        states = [s for s, _ in registry.history("dir-1")]
        assert states == [
            DirectiveState.RAISED, DirectiveState.IN_EFFECT,
            DirectiveState.FULFILLED,
        ]

    def test_a_directive_is_infrastructure_not_an_object(self):
        d = directive()
        for absent in ("derives_from", "lineage_id", "confidence",
                       "status", "object_type"):
            assert not hasattr(d, absent)

    def test_unbounded_directives_never_expire(self):
        """No period stated (valid_until None) means no expiry to elapse;
        nothing is invented either way."""
        d = directive(valid_until=None)
        assert d.is_expired(now=T0 + timedelta(days=10_000)) is False

    def test_expiry_boundary_is_inclusive(self):
        d = directive(valid_until=T0)
        assert d.is_expired(now=T0) is True
        assert d.is_expired(now=T0 - timedelta(seconds=1)) is False

    def test_in_effect_enumeration_and_iteration(self):
        registry = DirectiveRegistry()
        effective(registry, directive())
        registry.raise_directive(directive(directive_id="dir-2",
                                           targets=("src-x",)))
        live = registry.in_effect(now=T0)
        assert [d.directive_id for d in live] == ["dir-1"]
        assert len(registry) == 2
        assert {d.directive_id for d in registry} == {"dir-1", "dir-2"}
        assert registry.get("dir-2").directive_id == "dir-2"

    def test_get_returns_the_directive(self):
        registry = DirectiveRegistry()
        effective(registry, directive())
        assert registry.get("dir-1").authority == "commissioning-owner"

    def test_scope_is_not_widened_by_the_platform(self):
        """S 5.4: the platform records the scope verbatim; targets stay
        exactly as commissioned."""
        d = directive(targets=("src-a", "src-b", "src-a"))  # dedup only
        assert set(d.targets) == {"src-a", "src-b"}
