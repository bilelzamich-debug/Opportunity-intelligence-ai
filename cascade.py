"""Cascade invalidation: a mechanical integrity operation.

Task: T01.2.3

Architecture References:
- N-9    Mechanical operation invoked by Orchestration; performs NO interpretation
- I6     Upstream RETRACTED/INVALIDATED => dependents INVALIDATED
- M-09   Retraction semantics: status only, never content
- R-2    Seven-state lifecycle; terminal states never transition
- R-8    Behavioural loop closure keeps the lineage graph acyclic
- D-01a  Lineage references bind to a specific version
- AD-04  Orchestration triggers; it does not judge
- N-10   Failures produce records, never unexpected exceptions
- M-65   Re-derivation on SUPERSEDED is OPEN; deliberately NOT cascaded here

The operation propagates a status already determined at the source. It makes
no judgement about whether a dependent is still valid -- that determination
was made when the upstream object was withdrawn. This is what keeps
Orchestration's non-interpretive boundary intact: it triggers, it does not
decide.

SUPERSEDED deliberately does NOT cascade. Under D-01a a dependent references
a specific version, so it remains a valid derivation of what it actually
derived from. Whether it should be revised is an engine judgement governed by
M-65, which is unresolved until T05.2.2. Cascading supersession here would
silently invent that policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from oip.acceptance import FailureRecord, RuleOutcome, RuleResult
from oip.contract import utc_now
from oip.enums import ObjectStatus, ObjectType
from oip.lifecycle import can_transition

# Statuses that propagate to dependents. [I6, N-9]
CASCADE_TRIGGERS: frozenset[ObjectStatus] = frozenset(
    {ObjectStatus.RETRACTED, ObjectStatus.INVALIDATED}
)

# Bound mirrors the graph's traversal guard. The lineage graph is acyclic
# under R-8, so this is a safety net for malformed input, not a limit.
MAX_CASCADE_DEPTH = 32


class CascadeError(Exception):
    """Base class for cascade violations."""


class CascadeDepthExceededError(CascadeError):
    """Propagation exceeded the depth bound, indicating a malformed graph."""


@dataclass(frozen=True)
class CascadeResult:
    """Outcome of one cascade operation.

    Reports what changed and what was deliberately left alone, so a caller
    can distinguish "nothing to do" from "could not complete".
    """

    origin_id: str
    origin_status: ObjectStatus
    invalidated: tuple[str, ...] = ()
    already_terminal: tuple[str, ...] = ()
    # Dependents left ACTIVE because they retain a valid upstream reference.
    # [T01.2.4, N-9, IOM 3.2]
    partially_retracted: tuple[str, ...] = ()
    visited: int = 0
    max_depth_reached: int = 0
    failures: tuple[FailureRecord, ...] = ()
    completed: bool = True

    @property
    def changed(self) -> int:
        return len(self.invalidated)

    @property
    def is_noop(self) -> bool:
        return not self.invalidated and self.completed

    @property
    def partial_count(self) -> int:
        """Dependents spared by the partial-retraction rule. [T01.2.4]"""
        return len(self.partially_retracted)

    def __bool__(self) -> bool:
        return self.completed


def is_cascade_trigger(status: ObjectStatus) -> bool:
    """Whether transitioning to this status propagates to dependents. [I6]"""
    return status in CASCADE_TRIGGERS


@dataclass
class CascadeInvalidation:
    """Forward-propagates invalidation over the lineage graph. [N-9]

    Not an engine: a mechanical maintenance operation with no engine owner,
    invoked by Orchestration. It reads status and lineage structure only,
    never object content, so it performs no interpretation. [AD-04]
    """

    store: "object"  # KnowledgeStore; untyped to avoid a circular import
    max_depth: int = MAX_CASCADE_DEPTH

    _operations: list[CascadeResult] = field(default_factory=list, init=False)

    # -- planning ---------------------------------------------------------

    def plan(self, origin_id: str) -> tuple[str, ...]:
        """Dependents that would be invalidated, in deterministic order.

        Ordering is breadth-first by depth, then lexicographic by object_id.
        Deterministic ordering matters because the same withdrawal must
        produce the same audit trail on every run. [N-4]
        """
        ordered, _, _ = self._collect(origin_id)
        return ordered

    def _retains_valid_upstream(self, stored, doomed: set[str]) -> bool:
        """Whether this object still holds at least one valid upstream. [T01.2.4]

        IOM 3.2 triggers INVALIDATED on "All attesting Evidence retracted";
        N-9 binds T01.2.4 to the same boundary -- "an object retaining at
        least one valid upstream reference is re-versioned, not invalidated".

        Valid means not withdrawn: an upstream that is RETRACTED or
        INVALIDATED no longer attests. Any other status still does, including
        SUPERSEDED, because D-01a binds references to a specific version and
        supersession is not withdrawal (M-65 leaves re-derivation open).

        An object with no upstream at all -- Evidence, the pipeline root --
        retains nothing and is never reached by this path, since cascade
        traverses forward from the origin.
        """
        lineage = getattr(stored, "lineage", None)
        if lineage is None:
            return False
        references = getattr(lineage, "reference_ids", ())
        if not references:
            return False
        for reference in references:
            upstream = self.store.find(reference)
            if upstream is None:
                # An unresolvable reference cannot be counted as attesting.
                continue
            if reference in doomed:
                # Already withdrawn, or about to be by this cascade.
                continue
            if upstream.status not in CASCADE_TRIGGERS:
                return True
        return False

    def _collect(self, origin_id: str) -> tuple[tuple[str, ...], int, int]:
        """Breadth-first forward traversal with a visited set.

        Termination is doubly guaranteed: the visited set prevents revisiting
        under any graph shape, and the depth bound stops runaway propagation
        even if the graph is malformed. [V10, R-8]
        """
        graph = self.store.graph
        if not graph.contains(origin_id):
            return (), 0, 0

        seen: set[str] = {origin_id}
        ordered: list[str] = []
        frontier = [origin_id]
        depth = 0

        while frontier and depth < self.max_depth:
            depth += 1
            next_frontier: list[str] = []
            for object_id in frontier:
                for child in sorted(graph.children(object_id)):
                    if child in seen:
                        continue
                    seen.add(child)
                    ordered.append(child)
                    next_frontier.append(child)
            frontier = next_frontier

        if frontier:
            raise CascadeDepthExceededError(
                f"cascade from {origin_id!r} exceeded depth {self.max_depth}; "
                f"the lineage graph is expected to be acyclic [R-8, V10]"
            )
        return tuple(ordered), len(seen) - 1, depth

    # -- execution --------------------------------------------------------

    def cascade(
        self,
        origin_id: str,
        origin_status: ObjectStatus | None = None,
        reason: str | None = None,
    ) -> CascadeResult:
        """Invalidate every dependent of a withdrawn object. [I6, N-9]

        Atomic: either every eligible dependent transitions, or none does and
        the store is left exactly as found. Failures are returned as records
        rather than raised, so a partial cascade never escapes. [N-10]
        """
        store = self.store
        origin = store.find(origin_id)

        if origin is None:
            return self._record(
                CascadeResult(
                    origin_id=origin_id,
                    origin_status=origin_status or ObjectStatus.INVALIDATED,
                    completed=False,
                    failures=(
                        self._failure(
                            origin_id,
                            ObjectType.EVIDENCE,
                            "I6",
                            f"cascade origin {origin_id!r} is not stored",
                        ),
                    ),
                )
            )

        status = origin_status or origin.status
        if not is_cascade_trigger(status):
            # SUPERSEDED and ARCHIVED do not propagate. [D-01a, M-65]
            return self._record(
                CascadeResult(
                    origin_id=origin_id, origin_status=status, completed=True
                )
            )

        try:
            ordered, visited, depth = self._collect(origin_id)
        except CascadeDepthExceededError as exc:
            return self._record(
                CascadeResult(
                    origin_id=origin_id,
                    origin_status=status,
                    completed=False,
                    failures=(
                        self._failure(
                            origin_id, origin.object_type, "I6", str(exc)
                        ),
                    ),
                )
            )

        eligible: list[str] = []
        terminal: list[str] = []
        partial: list[str] = []
        failures: list[FailureRecord] = []
        # Upstreams that WILL be withdrawn by this same cascade. Eligibility
        # is computed before any mutation (for rollback safety), so an
        # upstream still reading ACTIVE here may already be doomed. Counting
        # it as attesting would spare a dependent whose entire support is
        # about to vanish. [T01.2.4]
        doomed: set[str] = {origin_id}

        # Classification that does not depend on `doomed`: unresolvable
        # dependents, already-terminal ones, and illegal transitions. These
        # are decided once, in traversal order.
        undecided: list[str] = []
        for object_id in ordered:
            stored = store.find(object_id)
            if stored is None:
                failures.append(
                    self._failure(
                        object_id,
                        ObjectType.EVIDENCE,
                        "I6",
                        f"dependent {object_id!r} indexed but not stored",
                    )
                )
                continue
            if stored.status is ObjectStatus.INVALIDATED:
                terminal.append(object_id)  # idempotence: already done
                continue
            if stored.status.is_terminal:
                terminal.append(object_id)  # RETRACTED/REJECTED/ARCHIVED stay
                continue
            if not can_transition(
                stored.object_type, stored.status, ObjectStatus.INVALIDATED
            ):
                failures.append(
                    self._failure(
                        object_id,
                        stored.object_type,
                        "I6",
                        f"{stored.object_type.value} cannot transition "
                        f"{stored.status.value} -> INVALIDATED [R-2]",
                    )
                )
                continue
            undecided.append(object_id)

        # Eligibility is resolved to a FIXPOINT rather than in a single pass.
        #
        # `ordered` is breadth-first, i.e. ordered by SHORTEST path from the
        # origin. In a directed acyclic graph that is not a topological
        # order: a dependent whose upstreams sit at different distances is
        # reached before the deeper of them is decided. A single pass would
        # then read that upstream as still attesting and spare the dependent,
        # leaving it ACTIVE after its entire support had in fact been
        # withdrawn -- the silent corruption I6 exists to prevent.
        #
        # Iterating until no further object becomes eligible makes the result
        # INDEPENDENT of traversal order, so correctness no longer rests on
        # any ordering property of `_collect`. Termination is guaranteed:
        # every pass but the last adds at least one object to `doomed`, and
        # `doomed` is bounded by the finite dependent set. [T01.2.4, N-9, I6]
        doomed_dependents: set[str] = set()
        progressing = True
        while progressing:
            progressing = False
            for object_id in undecided:
                if object_id in doomed_dependents:
                    continue
                stored = store.find(object_id)
                if self._retains_valid_upstream(stored, doomed):
                    continue
                doomed_dependents.add(object_id)
                doomed.add(object_id)
                progressing = True

        # Emit in traversal order, preserving the deterministic sequence that
        # `plan()` reports. [N-4]
        for object_id in undecided:
            if object_id in doomed_dependents:
                eligible.append(object_id)
            else:
                # PARTIAL RETRACTION [T01.2.4, N-9, IOM 3.2]. An object that
                # still holds at least one valid upstream reference is NOT
                # invalidated: IOM 3.2 triggers INVALIDATED on "ALL attesting
                # Evidence retracted", and N-9 binds T01.2.4 -- "an object
                # retaining at least one valid upstream reference is
                # re-versioned, not invalidated".
                #
                # Cascade performs no interpretation (N-9), so it does not
                # re-version here: producing a new version with reduced
                # support is the owning engine's act, and cascade "alters
                # status only, never content". It leaves the object ACTIVE
                # and reports it, which is the boundary N-9 says must be
                # maintained carefully.
                partial.append(object_id)

        if failures:
            # Rollback safety: nothing has been mutated yet. [N-10]
            return self._record(
                CascadeResult(
                    origin_id=origin_id,
                    origin_status=status,
                    already_terminal=tuple(terminal),
                    partially_retracted=tuple(partial),
                    visited=visited,
                    max_depth_reached=depth,
                    failures=tuple(failures),
                    completed=False,
                )
            )

        detail = reason or f"upstream {origin_id} became {status.value}"
        applied: list[str] = []
        try:
            for object_id in eligible:
                store.transition(object_id, ObjectStatus.INVALIDATED, detail)
                applied.append(object_id)
        except Exception as exc:  # pragma: no cover - defensive
            self._rollback(applied)
            return self._record(
                CascadeResult(
                    origin_id=origin_id,
                    origin_status=status,
                    already_terminal=tuple(terminal),
                    partially_retracted=tuple(partial),
                    visited=visited,
                    max_depth_reached=depth,
                    failures=(
                        self._failure(
                            origin_id,
                            origin.object_type,
                            "I6",
                            f"propagation failed and was rolled back: {exc}",
                        ),
                    ),
                    completed=False,
                )
            )

        return self._record(
            CascadeResult(
                origin_id=origin_id,
                origin_status=status,
                invalidated=tuple(applied),
                already_terminal=tuple(terminal),
                partially_retracted=tuple(partial),
                visited=visited,
                max_depth_reached=depth,
                completed=True,
            )
        )

    def retract(self, origin_id: str, reason: str) -> CascadeResult:
        """Retract an object and cascade to its dependents. [M-09, I6]

        The origin transition and the cascade are one operation: an origin
        left RETRACTED with live dependents would be exactly the silent
        corruption I6 exists to prevent.
        """
        store = self.store
        stored = store.find(origin_id)
        if stored is None:
            return self.cascade(origin_id, ObjectStatus.RETRACTED, reason)

        previous = stored.status
        store.transition(origin_id, ObjectStatus.RETRACTED, reason)
        result = self.cascade(origin_id, ObjectStatus.RETRACTED, reason)

        if not result.completed:
            # Restore the origin so the store is exactly as found. [N-10]
            self._restore(origin_id, previous)
        return result

    # -- introspection ----------------------------------------------------

    @property
    def operations(self) -> tuple[CascadeResult, ...]:
        return tuple(self._operations)

    def impact_report(self, origin_id: str) -> dict[ObjectType, tuple[str, ...]]:
        """Dependents grouped by type, without mutating anything."""
        grouped: dict[ObjectType, list[str]] = {}
        for object_id in self.plan(origin_id):
            stored = self.store.find(object_id)
            if stored is not None:
                grouped.setdefault(stored.object_type, []).append(object_id)
        return {k: tuple(v) for k, v in grouped.items()}

    # -- internals --------------------------------------------------------

    def _record(self, result: CascadeResult) -> CascadeResult:
        self._operations.append(result)
        return result

    def _rollback(self, applied: list[str]) -> None:
        """Best-effort restoration after a failed propagation."""
        for object_id in reversed(applied):
            self._restore(object_id, ObjectStatus.ACTIVE)

    def _restore(self, object_id: str, status: ObjectStatus) -> None:
        stored = self.store.find(object_id)
        if stored is None:
            return
        replacement = type(stored)(
            attributes=stored.attributes.__class__(
                **{
                    **{
                        f: getattr(stored.attributes, f)
                        for f in stored.attributes.__dataclass_fields__
                    },
                    "status": status,
                    "status_reason": None
                    if status is ObjectStatus.ACTIVE
                    else stored.attributes.status_reason,
                }
            ),
            lineage=stored.lineage,
        )
        self.store._objects[object_id] = replacement  # noqa: SLF001
        if status is ObjectStatus.ACTIVE:
            self.store._active[stored.lineage_id] = object_id  # noqa: SLF001

    @staticmethod
    def _failure(
        object_id: str, object_type: ObjectType, rule_id: str, detail: str
    ) -> FailureRecord:
        return FailureRecord(
            object_id=object_id,
            object_type=object_type,
            failed_rules=(RuleResult(rule_id, RuleOutcome.FAIL, detail),),
            recorded_at=utc_now(),
            engine_configuration_ref="cascade-operation",
        )
