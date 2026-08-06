"""ARCHIVED tiering: lineage skeleton permanent, content tiered by reachability.

Task: T01.2.5

Architecture References:
- N-12   Retention (closes M-38). "The lineage skeleton is retained
         permanently. Heavyweight content is tiered by reachability."
         Reachability rule: "An object is tiered only when it is not
         reachable from any ACTIVE object by lineage traversal. Anything
         supporting current knowledge stays." "Tiering sets ARCHIVED (R-2)
         and is invoked as a maintenance operation." "Lineage traversal
         never breaks."
- R-2    ARCHIVED = "Removed from the active working set; lineage
         preserved". Terminal.
- IOM 2.1 The ONLY ARCHIVED transition is ACTIVE -> ARCHIVED, trigger
         "Retention policy". "No terminal state may transition."
- I4     Referenced objects are never hard-deleted. N-12: "satisfied".
- N-15   content_fingerprint and provenance "are always retained,
         regardless of mode" (closes OQ-12)
- N-6    Objects are authoritative; the graph is a derived, rebuildable
         index that may lag
- N-9    Cascade triggers are RETRACTED and INVALIDATED only
- M-65   Re-derivation on supersession OPEN; ARCHIVED does not cascade
- P3     Lineage reconstructable indefinitely; traversal never breaks
- T01.3.4 Backward traversal (ancestors) is the reachability primitive
- T01.2.2 store.transition() is the sole non-versioning mutation

MARKER CROSSWALK, recorded because it determines whether this task is
implementable at all. IOM 2.1 marks the ACTIVE -> ARCHIVED authority as
"Undefined (MISSING-31)". That is IOM MISSING-31, which marker-crosswalk.md
line 45 maps to canonical M-38 ("Retention policy"), warning that canonical
M-31 is a different gap (post-validation promote/reject owner) and that using
it "would close the wrong gap". M-38 IS closed, by N-12, which supplies both
the trigger (unreachability) and the owner (a maintenance operation).
Canonical M-31 remains OPEN and is untouched here.

WHAT THIS MODULE DOES NOT DO. N-12 states that content is "tiered" and
becomes "retrievable through a slower path", but no ratified source defines a
storage tier, an eviction step or a retrieval path. Inventing one could
destroy content that no ratified path could bring back, so NO CONTENT IS
EVICTED. The status transition to ARCHIVED -- which is precisely what N-12
says tiering sets -- is implemented, and the eligibility rule is enforced
exactly. The unspecified half is reported by `content_tiering_specified`,
never guessed at.

It also performs no scheduling, no garbage collection, no age heuristics
(N-12 rejected Option B, "archive by age"), and no hard deletion (I4). It is
a MAINTENANCE OPERATION: it acts only when a caller invokes it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Protocol

from oip.enums import ObjectStatus, ObjectType
from oip.graph import MAX_LINEAGE_DEPTH


class RetentionError(Exception):
    """Base class for retention violations."""


class ReachabilityError(RetentionError):
    """An object reachable from ACTIVE knowledge may not be archived. [N-12]

    N-12's rule, quoted: "An object is tiered only when it is not reachable
    from any ACTIVE object by lineage traversal. Anything supporting current
    knowledge stays."
    """


class ArchivalStateError(RetentionError):
    """The object is not in a state from which ARCHIVED is reachable. [R-2]

    IOM 2.1 defines exactly one ARCHIVED transition, ACTIVE -> ARCHIVED, and
    states that no terminal state may transition.
    """


# Why an object may not be archived. Reported, never guessed at.
REASON_NOT_ACTIVE = "object is not ACTIVE; only ACTIVE -> ARCHIVED exists [IOM 2.1]"
REASON_REACHABLE = "reachable from ACTIVE knowledge [N-12]"


class GraphView(Protocol):
    """The traversal this mechanism needs. [T01.3.4]

    Only `ancestors` and `contains`: reachability is a lineage question, and
    nothing here reads object content.
    """

    def ancestors(
        self, object_id: str, max_depth: int = MAX_LINEAGE_DEPTH
    ) -> frozenset[str]:
        ...

    def contains(self, object_id: str) -> bool:
        ...


@dataclass(frozen=True)
class ReachabilityIndex:
    """Everything supporting current knowledge. [N-12]

    The protected set is every ACTIVE object together with all of their
    ancestors: support flows upstream, so an object that an ACTIVE object
    derives from is what N-12 means by "supporting current knowledge".

    A SNAPSHOT, not a live view. Reachability is computed once and frozen, so
    a caller reasoning about a set of candidates sees one consistent picture.
    Recompute to observe later writes.
    """

    protected: frozenset[str]
    active_roots: frozenset[str]

    @classmethod
    def build(
        cls,
        active_ids: Iterable[str],
        graph: GraphView,
        max_depth: int = MAX_LINEAGE_DEPTH,
    ) -> "ReachabilityIndex":
        roots = frozenset(active_ids)
        protected: set[str] = set(roots)
        for root in roots:
            if graph.contains(root):
                protected.update(graph.ancestors(root, max_depth))
        return cls(protected=frozenset(protected), active_roots=roots)

    def is_reachable(self, object_id: str) -> bool:
        """Whether this object supports current knowledge. [N-12]"""
        return object_id in self.protected

    def is_active_root(self, object_id: str) -> bool:
        return object_id in self.active_roots

    def __len__(self) -> int:
        return len(self.protected)


@dataclass(frozen=True)
class ArchivalAssessment:
    """Whether one object may be archived, and why not. [N-12, T01.2.5]

    Frozen and itemised: a refusal names its reason rather than returning a
    bare boolean, so a caller can see exactly what protects the object.
    """

    object_id: str
    status: ObjectStatus
    object_type: ObjectType
    archivable: bool
    reasons: tuple[str, ...] = ()

    @property
    def detail(self) -> str:
        if self.archivable:
            return ""
        return f"{self.object_id} may not be archived: " + "; ".join(self.reasons)


@dataclass
class RetentionPolicy:
    """ARCHIVED tiering by reachability. A maintenance operation. [N-12]

    IT OWNS NO STORAGE. The store and graph are supplied. It never writes an
    object, never edits content and never deletes anything: the only mutation
    it can cause is the ACTIVE -> ARCHIVED status transition that R-2 defines
    and that the store already performs.

    IT ACTS ONLY WHEN INVOKED. N-12 calls tiering "a maintenance operation".
    Nothing here schedules, polls or collects garbage, and nothing archives by
    age -- N-12 considered and rejected that (Option B: "age is uncorrelated
    with relevance").

    IT EVICTS NO CONTENT. See the module docstring: the physical tiering step
    is unspecified by every ratified source, so it is left unimplemented and
    reported rather than invented.
    """

    store: object
    graph: GraphView | None = None
    max_depth: int = MAX_LINEAGE_DEPTH

    # The unspecified half of N-12, surfaced rather than guessed at.
    content_tiering_specified: bool = field(default=False, init=False)

    def _graph(self) -> GraphView:
        graph = self.graph if self.graph is not None else getattr(
            self.store, "graph", None
        )
        if graph is None:
            raise RetentionError(
                "reachability requires a lineage graph; without traversal the "
                "N-12 rule cannot be evaluated and archiving would be a guess"
            )
        return graph

    def _active_ids(self) -> frozenset[str]:
        """The ACTIVE set, read from the STORE. [N-6]

        Objects are authoritative and the graph may lag, so status comes from
        the store even though traversal uses the index.
        """
        return frozenset(
            stored.object_id for stored in self.store.active_objects()
        )

    def reachability(self) -> ReachabilityIndex:
        """Snapshot everything supporting current knowledge. [N-12]"""
        return ReachabilityIndex.build(
            self._active_ids(), self._graph(), self.max_depth
        )

    # -- eligibility -------------------------------------------------------

    def assess(
        self, object_id: str, index: ReachabilityIndex | None = None
    ) -> ArchivalAssessment:
        """Whether this object may be archived. Reads only. [N-12, IOM 2.1]"""
        stored = self.store.get(object_id)
        index = index if index is not None else self.reachability()

        reasons: list[str] = []
        if stored.status is not ObjectStatus.ACTIVE:
            # IOM 2.1: the only ARCHIVED transition is ACTIVE -> ARCHIVED, and
            # no terminal state may transition. N-12's Known Tension that
            # REJECTED objects are "subject to tiering" concerns CONTENT
            # tiering, which is unspecified; it cannot license a status
            # transition the lifecycle forbids.
            reasons.append(REASON_NOT_ACTIVE)

        # DEFECT FIX [T01.2.5]. An earlier version treated "is itself an
        # ACTIVE object" as protection, which made archival impossible: ACTIVE
        # is the ONLY state from which IOM 2.1 permits ARCHIVED, so protecting
        # every ACTIVE object protects everything. N-12 protects what SUPPORTS
        # current knowledge -- objects reachable from ANOTHER ACTIVE object --
        # not the candidate's own ACTIVE status, which is the precondition for
        # archiving at all.
        if self._supports_other_active(object_id, index):
            reasons.append(REASON_REACHABLE)

        return ArchivalAssessment(
            object_id=object_id,
            status=stored.status,
            object_type=stored.object_type,
            archivable=not reasons,
            reasons=tuple(reasons),
        )

    def _supports_other_active(
        self, object_id: str, index: ReachabilityIndex
    ) -> bool:
        """Whether some OTHER ACTIVE object derives from this one. [N-12]

        The candidate's own membership of the ACTIVE set is excluded, because
        being ACTIVE is the precondition for archiving, not a protection.
        """
        graph = self._graph()
        for active_id in index.active_roots:
            if active_id == object_id or not graph.contains(active_id):
                continue
            if object_id in graph.ancestors(active_id, self.max_depth):
                return True
        return False

    def is_archivable(
        self, object_id: str, index: ReachabilityIndex | None = None
    ) -> bool:
        return self.assess(object_id, index).archivable

    def candidates(self) -> tuple[ArchivalAssessment, ...]:
        """Every object currently eligible for archival. [N-12]

        Reports; it does not act. Given the ACTIVE-only transition rule and
        the reachability rule, an eligible object is by construction an
        ACTIVE object that no other ACTIVE object derives from -- so in
        practice this is usually empty, which is the correct conservative
        answer rather than an error.
        """
        index = self.reachability()
        found = [
            assessment
            for stored in self.store
            if (assessment := self.assess(stored.object_id, index)).archivable
        ]
        return tuple(found)

    # -- the maintenance operation ----------------------------------------

    def archive(
        self,
        object_id: str,
        reason: str = "retention: unreachable from ACTIVE knowledge [N-12]",
        index: ReachabilityIndex | None = None,
    ) -> object:
        """Archive one object, if N-12 permits it. Fails closed. [N-12, R-2]

        Sets ARCHIVED via the store's ordinary transition path, which is the
        sole permitted non-versioning mutation (T01.2.2, R-1). No content is
        touched, nothing is deleted, and the lineage skeleton is untouched by
        construction -- a status transition alters status alone.
        """
        assessment = self.assess(object_id, index)
        if not assessment.archivable:
            if REASON_NOT_ACTIVE in assessment.reasons:
                raise ArchivalStateError(assessment.detail)
            raise ReachabilityError(assessment.detail)
        return self.store.transition(object_id, ObjectStatus.ARCHIVED, reason)

    def archive_all(
        self,
        object_ids: Iterable[str],
        reason: str = "retention: unreachable from ACTIVE knowledge [N-12]",
    ) -> tuple[str, ...]:
        """Archive each eligible object. Returns those archived.

        Reachability is re-evaluated per object, because archiving one object
        removes it from the ACTIVE set and can therefore change what is
        reachable. Evaluating once up front would archive on a stale picture.

        Ineligible objects are skipped rather than raising: this is a
        maintenance sweep over a caller-supplied set, and one protected
        object must not abort the sweep. Callers wanting a hard failure use
        archive().
        """
        archived: list[str] = []
        for object_id in object_ids:
            if self.assess(object_id).archivable:
                self.store.transition(object_id, ObjectStatus.ARCHIVED, reason)
                archived.append(object_id)
        return tuple(archived)

    # -- skeleton preservation  [N-12, AC2, AC3] ---------------------------

    def verify_skeleton_intact(self, object_id: str) -> tuple[str, ...]:
        """Confirm N-12's permanently-retained skeleton still resolves.

        Returns the names of any missing element; empty means intact. N-12
        lists exactly what survives archival: object identity, type, version,
        lineage_id, lineage references and relationships, content_fingerprint
        and provenance, status, status_reason and attribution.

        Checked mechanically rather than assumed, because "lineage traversal
        never breaks" is the property Principle 3 rests on.
        """
        missing: list[str] = []
        stored = self.store.find(object_id)
        if stored is None:
            return ("object",)

        attributes = stored.attributes
        for name in (
            "object_id",
            "object_type",
            "version",
            "lineage_id",
            "produced_by_engine",
            "produced_at",
            "engine_configuration_ref",
            "status",
        ):
            if getattr(attributes, name, None) in (None, ""):
                missing.append(name)

        if attributes.status is not ObjectStatus.ACTIVE and not (
            attributes.status_reason or ""
        ).strip():
            missing.append("status_reason")

        if stored.lineage is None:
            missing.append("lineage")
        elif not attributes.object_type.is_root and not stored.lineage.references:
            missing.append("lineage_references")

        missing.extend(self._missing_evidence_skeleton(object_id, attributes))
        return tuple(missing)

    def _missing_evidence_skeleton(
        self, object_id: str, attributes: object
    ) -> list[str]:
        """content_fingerprint and provenance are always retained. [N-15]"""
        if getattr(attributes, "object_type", None) is not ObjectType.EVIDENCE:
            return []
        registry = getattr(self.store, "evidence", None)
        if registry is None:
            return []
        payload = registry.get(object_id)
        if payload is None:
            return []

        missing: list[str] = []
        fingerprint = getattr(
            getattr(payload, "content", None), "fingerprint", None
        )
        if not (fingerprint or "").strip():
            missing.append("content_fingerprint")
        provenance = getattr(payload, "provenance", None)
        if provenance is None:
            missing.append("provenance")
        elif not (getattr(provenance, "source_identifier", "") or "").strip():
            missing.append("provenance.source_identifier")
        return missing

    def traversal_intact(self, object_id: str) -> bool:
        """Whether lineage traversal through this object still works. [N-12]"""
        graph = self._graph()
        if not graph.contains(object_id):
            return False
        graph.ancestors(object_id, self.max_depth)
        return True

    @property
    def performs_hard_deletion(self) -> bool:
        """Always False. Referenced objects are never hard-deleted. [I4]"""
        return False

    @property
    def content_eviction_performed(self) -> bool:
        """Always False. The physical tiering step is unspecified. [N-12]

        Named as a report, not a capability: this module has no eviction
        behaviour to enable or disable.
        """
        return False
