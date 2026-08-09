"""Shared fixtures and object builders.

Architecture References:
- R-1  Objects immutable; new version per change
- R-3  Two-component confidence
- N-13 Explanation skeleton

Builders produce contract-valid objects so tests state only what they vary.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from oip.acceptance import AcceptancePath
from oip.contract import Confidence, Explanation, LineageRef, UniversalAttributes
from oip.enums import CREATE_AUTHORITY, Engine, ObjectStatus, ObjectType
from oip.identity import IdentityAllocator, ObjectIdentity
from oip.lineage import Lineage, derive, root_lineage
from oip.store import KnowledgeStore

T0 = datetime(2026, 3, 1, tzinfo=timezone.utc)

PARENT_OF: dict[ObjectType, ObjectType] = {
    ObjectType.FACT: ObjectType.EVIDENCE,
    ObjectType.PROBLEM: ObjectType.FACT,
    ObjectType.PATTERN: ObjectType.PROBLEM,
    ObjectType.OPPORTUNITY: ObjectType.PATTERN,
    ObjectType.SOLUTION: ObjectType.OPPORTUNITY,
    ObjectType.VALIDATION: ObjectType.SOLUTION,
    ObjectType.EXECUTION_RECORD: ObjectType.SOLUTION,
    ObjectType.FEEDBACK_RECORD: ObjectType.EXECUTION_RECORD,
}


@pytest.fixture()
def allocator() -> IdentityAllocator:
    return IdentityAllocator()


@pytest.fixture()
def store() -> KnowledgeStore:
    return KnowledgeStore()


def build_attrs(
    identity: ObjectIdentity,
    object_type: ObjectType,
    upstream: tuple[tuple[str, ObjectType], ...] = (),
    *,
    status: ObjectStatus = ObjectStatus.PROPOSED,
    status_reason: str | None = "awaiting acceptance",
    support: float = 0.62,
    assertion: float = 0.84,
    upstream_ceiling: float | None = None,
    engine: Engine | None = None,
    config_ref: str = "cfg-v1",
    source_count: int = 1,
    **overrides,
) -> UniversalAttributes:
    """Build contract-valid attributes for any object type."""
    refs = tuple(LineageRef(oid, otype) for oid, otype in upstream)
    referenced = tuple(oid for oid, _ in upstream) or ("external-source",)

    kwargs = dict(
        identity=identity,
        object_type=object_type,
        produced_by_engine=engine or CREATE_AUTHORITY.get(object_type, Engine.RESEARCH),
        produced_at=T0 + timedelta(hours=2),
        engine_configuration_ref=config_ref,
        derives_from=refs,
        explanation=Explanation(
            objects_referenced=referenced,
            criteria_applied=("contract-conformance",),
            reasoning=f"Constructed {object_type.value} for test.",
        ),
        evidence_reachable=True,
        confidence=Confidence.create(support, assertion, upstream_ceiling),
        asserted_at=T0 + timedelta(hours=1),
        observed_at=T0,
        status=status,
        status_reason=status_reason,
        independent_source_count=source_count,
    )
    kwargs.update(overrides)
    return UniversalAttributes(**kwargs)


def build_lineage(
    object_id: str,
    object_type: ObjectType,
    upstream: tuple[tuple[str, ObjectType], ...] = (),
) -> Lineage:
    if object_type.is_root:
        return root_lineage(object_id)
    return derive(object_id, object_type, upstream)


def write_evidence(
    store: KnowledgeStore, allocator: IdentityAllocator, **overrides
):
    """Persist an ACTIVE Evidence object."""
    identity = allocator.new_object()
    attrs = build_attrs(
        identity,
        ObjectType.EVIDENCE,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        **overrides,
    )
    return store.write(attrs, build_lineage(identity.object_id, ObjectType.EVIDENCE))


def write_derived(
    store: KnowledgeStore,
    allocator: IdentityAllocator,
    object_type: ObjectType,
    parents,
    **overrides,
):
    """Persist an ACTIVE object derived from the given parents."""
    identity = allocator.new_object()
    upstream = tuple((p.object_id, p.object_type) for p in parents)
    ceiling = min(
        p.attributes.confidence.effective_confidence for p in parents
    )
    attrs = build_attrs(
        identity,
        object_type,
        upstream,
        status=ObjectStatus.ACTIVE,
        status_reason=None,
        upstream_ceiling=ceiling,
        **overrides,
    )
    return store.write(
        attrs, build_lineage(identity.object_id, object_type, upstream)
    )


def write_chain(store: KnowledgeStore, allocator: IdentityAllocator):
    """Persist a full pipeline chain, returning it by type."""
    evidence = write_evidence(store, allocator)
    chain = {ObjectType.EVIDENCE: evidence}
    for otype in (
        ObjectType.FACT,
        ObjectType.PROBLEM,
        ObjectType.PATTERN,
        ObjectType.OPPORTUNITY,
        ObjectType.SOLUTION,
        ObjectType.VALIDATION,
    ):
        chain[otype] = write_derived(
            store, allocator, otype, [chain[PARENT_OF[otype]]]
        )
    return chain
