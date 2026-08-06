"""Acceptance path: rule evaluation at PROPOSED -> ACTIVE.

Task: T01.4.1

Architecture References:
- N-8    Store enforces; the rule set is specified in the object model
- N-10   Failed acceptance produces a failure record, never a silent rejection
- R-2    PROPOSED -> ACTIVE is the accepted transition
- V1-V12 Universal validation rules
- S-5    Semantic verification hook (extraction fidelity), Layer 1
- M-67   Hallucination detection remains open; structure cannot catch it

Mechanism and policy are separated. This module supplies the MECHANISM: it
evaluates a rule set and records the outcome. The rules themselves are
declared here as object-model policy, not embedded in storage logic, so the
Store never interprets content -- it only runs checks it is handed. [N-8]

Structural rules only. Rules requiring semantic judgement -- notably F-V6,
that a Fact's claim is actually present in its Evidence -- cannot be enforced
structurally and are delegated to a pluggable hook whose residual error rate
is measured, not eliminated. [N-8, S-5, M-67]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Protocol, Sequence

from oip.contract import UniversalAttributes, utc_now
from oip.enums import CREATE_AUTHORITY, Engine, ObjectStatus, ObjectType
from oip.lineage import Lineage


class RuleOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    outcome: RuleOutcome
    detail: str = ""

    @property
    def failed(self) -> bool:
        return self.outcome is RuleOutcome.FAIL


@dataclass(frozen=True)
class AcceptanceContext:
    """Everything a rule may consult. Supplied by the Store. [N-8]"""

    attributes: UniversalAttributes
    lineage: Lineage | None = None
    resolve_type: Callable[[str], ObjectType | None] | None = None
    reaches_evidence: Callable[[str], bool] | None = None
    would_cycle: Callable[[str, str], bool] | None = None
    active_version_of_lineage: Callable[[str], str | None] | None = None
    predecessor: UniversalAttributes | None = None
    upstream_confidence: Callable[[str], float | None] | None = None
    # Upstream lifecycle status, required by the preventive I8 check. [I8]
    upstream_status: Callable[[str], "ObjectStatus | None"] | None = None
    # Type-specific payload and providers. Evidence supplies these for
    # E-V1..E-V6; other object types leave them unset. [T01.7.x]
    evidence: object | None = None
    find_duplicate_evidence: Callable[[tuple[str, str]], str | None] | None = None
    # Fact payload and the S-5 Layer 1 anchor verifier. [F-V6, M-67]
    fact: object | None = None
    anchor_verifier: object | None = None
    # Problem payload and the claim text of a supporting Fact, which P-V6
    # needs to tell an inference from a restatement. [P-V1..P-V6]
    problem: object | None = None
    fact_claim_text: Callable[[str], str | None] | None = None
    # Pattern payload. PT-V2 needs lineage_id to tell distinct Problems from
    # versions of one; PT-V1 needs upstream counts for S-4 spanning.
    pattern: object | None = None
    resolve_lineage: Callable[[str], str | None] | None = None
    upstream_source_count: Callable[[str], int | None] | None = None
    # Opportunity payload. O-V6 needs the Facts reachable in lineage to tell
    # a traced quantitative claim from unfounded sizing.
    opportunity: object | None = None
    lineage_facts: Callable[[str], frozenset[str] | None] | None = None
    # Solution payload. S-V4 needs the Problems reachable in lineage; S-V5
    # needs the Opportunity's own statement to detect a restatement.
    solution: object | None = None
    lineage_problems: Callable[[str], frozenset[str] | None] | None = None
    opportunity_statement_text: Callable[[str], str | None] | None = None
    # Validation payload. V-V1 needs the claim set an object exposes, to tell
    # a specific claim from a whole-object assertion.
    validation: object | None = None
    claims_of_object: Callable[[str], frozenset[str] | None] | None = None
    # Execution Record payload. X-V4 needs the Opportunity's stored prediction
    # to be retrievable, and the Opportunities reachable in lineage.
    execution_record: object | None = None
    stored_prediction: Callable[[str], object | None] | None = None
    lineage_opportunities: Callable[[str], frozenset[str] | None] | None = None
    # Feedback Record payload. FR-V1 and FR-V6 resolve motivating records
    # through the existing resolve_type provider; no new provider is needed.
    feedback_record: object | None = None


@dataclass(frozen=True)
class FailureRecord:
    """Recorded when processing fails. Outside the object model. [N-10]

    Failures are operational facts, not knowledge: they never enter the
    lineage graph. An empty result and a failed result must always be
    distinguishable.

    ATTRIBUTION [N-10, T01.6.3]. N-10 requires that "every failure record
    identifies: the engine, the invocation, the inputs attempted, the
    configuration in force, the time, and the nature of the failure."

    The first three had no field and were unrecoverable -- an orchestrated
    engine failure lost which inputs were attempted, and named the engine
    only by convention inside object_id. They are added here as OPTIONAL
    fields so that every existing producer and construction is unaffected.

    They are optional because only an orchestrated engine invocation HAS an
    invocation identity. Acceptance, cascade and integrity failures are not
    invocations; leaving their attribution absent is honest, whereas
    fabricating an invocation identity for them would not be. Whether a
    given record meets N-10 in full is reported by
    `satisfies_n10_attribution` rather than assumed.
    """

    object_id: str
    object_type: ObjectType
    failed_rules: tuple[RuleResult, ...]
    recorded_at: datetime
    engine_configuration_ref: str
    # -- N-10 attribution. Optional: see the class docstring. [T01.6.3]
    engine: Engine | None = None
    cycle_id: int | None = None
    invocation_index: int | None = None
    input_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.engine is not None and not isinstance(self.engine, Engine):
            raise ValueError(
                f"engine must be a known Engine or None, got {self.engine!r} "
                f"[N-10]"
            )
        if isinstance(self.input_ids, (str, bytes)):
            raise ValueError(
                f"input_ids must be a collection of ids, not a bare string "
                f"{self.input_ids!r}; an id is opaque and is never split [N-10]"
            )
        object.__setattr__(self, "input_ids", tuple(self.input_ids))

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(r.rule_id for r in self.failed_rules)

    @property
    def nature(self) -> tuple[str, ...]:
        """The nature of the failure: why it failed. [N-10]"""
        return tuple(r.detail for r in self.failed_rules)

    @property
    def is_attributable_to_invocation(self) -> bool:
        """Whether this failure names the invocation it arose from. [N-10]"""
        return self.cycle_id is not None and self.invocation_index is not None

    @property
    def satisfies_n10_attribution(self) -> bool:
        """Whether all six N-10 identifications are present. [N-10]

        Reported, never assumed. A record that does not satisfy this is not
        hidden -- it is surfaced by FailureSurface.unattributed_failures()
        and FailureStore.unattributed(), so an attribution gap is visible
        rather than silently tolerated.
        """
        return (
            self.engine is not None
            and self.is_attributable_to_invocation
            and bool(self.input_ids)
            and bool(self.engine_configuration_ref)
            and self.recorded_at is not None
            and bool(self.failed_rules)
        )

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Failures never enter lineage. [N-10, Art.V]"""
        return False


@dataclass(frozen=True)
class AcceptanceResult:
    accepted: bool
    results: tuple[RuleResult, ...]
    attributes: UniversalAttributes | None = None
    failure: FailureRecord | None = None

    @property
    def failures(self) -> tuple[RuleResult, ...]:
        return tuple(r for r in self.results if r.failed)


class Rule(Protocol):
    rule_id: str

    def __call__(self, ctx: AcceptanceContext) -> RuleResult:
        ...


def _rule(rule_id: str):
    def decorate(fn: Callable[[AcceptanceContext], RuleResult]):
        fn.rule_id = rule_id  # type: ignore[attr-defined]
        return fn
    return decorate


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


# ---------------------------------------------------------------------------
# Universal rules V1-V12 [IOM section 1.3]
# ---------------------------------------------------------------------------

@_rule("V1")
def v1_required_attributes_present(ctx: AcceptanceContext) -> RuleResult:
    """Construction of UniversalAttributes enforces presence. [V1]"""
    if not isinstance(ctx.attributes, UniversalAttributes):
        return _fail("V1", "attributes are not a UniversalAttributes instance")
    return _ok("V1")


@_rule("V2")
def v2_derives_from_non_empty(ctx: AcceptanceContext) -> RuleResult:
    """Non-empty lineage for every type except Evidence. [V2, E-V1, AD-05]"""
    attrs = ctx.attributes
    if attrs.object_type.is_root:
        if attrs.derives_from:
            return _fail("V2", "Evidence may not derive from anything [AD-05]")
        return _ok("V2", "Evidence is the lineage root")
    if not attrs.derives_from:
        return _fail("V2", f"{attrs.object_type.value} requires upstream references")
    return _ok("V2")


@_rule("V3")
def v3_references_resolve(ctx: AcceptanceContext) -> RuleResult:
    """Every reference resolves to an existing object version. [V3]"""
    if ctx.resolve_type is None:
        return _skip("V3", "no resolver supplied")
    for ref in ctx.attributes.derives_from:
        actual = ctx.resolve_type(ref.object_id)
        if actual is None:
            return _fail("V3", f"reference {ref.object_id!r} does not resolve")
        if actual is not ref.object_type:
            return _fail(
                "V3",
                f"reference {ref.object_id!r} declared {ref.object_type.value} "
                f"but resolves to {actual.value}",
            )
    return _ok("V3")


@_rule("V4")
def v4_evidence_reachable(ctx: AcceptanceContext) -> RuleResult:
    """A path to Evidence must be traversable, not merely asserted. [V4, U6]"""
    attrs = ctx.attributes
    if attrs.object_type.is_root:
        return _ok("V4", "Evidence is its own root")
    if ctx.reaches_evidence is None:
        return _skip("V4", "no reachability provider supplied")
    if not ctx.reaches_evidence(attrs.object_id):
        return _fail("V4", "no traversable path to Evidence")
    if not attrs.evidence_reachable:
        return _fail("V4", "evidence_reachable asserted False but path exists")
    return _ok("V4")


@_rule("V5")
def v5_confidence_ceiling(ctx: AcceptanceContext) -> RuleResult:
    """effective_confidence <= min(upstream effective_confidence). [V5, R-3]

    Every upstream reference must resolve. A partially-resolved upstream set
    cannot establish a ceiling: an unresolved parent might carry lower
    confidence than any resolved one, so passing on the resolved subset would
    let confidence inflation through undetected -- the failure R-3 exists to
    prevent. Unresolvable upstream is therefore a FAIL, not a SKIP.
    """
    attrs = ctx.attributes
    if not attrs.derives_from:
        return _skip("V5", "no upstream references; ceiling does not apply")
    if ctx.upstream_confidence is None:
        return _skip("V5", "no upstream confidence provider")

    resolved: list[float] = []
    unresolved: list[str] = []
    for ref in attrs.derives_from:
        value = ctx.upstream_confidence(ref.object_id)
        if value is None:
            unresolved.append(ref.object_id)
        else:
            resolved.append(value)

    if unresolved:
        return _fail(
            "V5",
            f"upstream confidence unresolvable for {sorted(unresolved)}; "
            f"a ceiling cannot be established from a partial upstream set",
        )

    ceiling = min(resolved)
    effective = attrs.confidence.effective_confidence
    if effective > ceiling + 1e-9:
        return _fail(
            "V5",
            f"effective_confidence {effective} exceeds upstream ceiling "
            f"{ceiling} (min of {sorted(resolved)})",
        )
    return _ok("V5", f"within upstream ceiling {ceiling}")


@_rule("V6")
def v6_explanation_references_inputs(ctx: AcceptanceContext) -> RuleResult:
    """Explanation must reference at least one actual input. [V6, N-13]"""
    attrs = ctx.attributes
    referenced = set(attrs.explanation.objects_referenced)
    if not referenced:
        return _fail("V6", "explanation references no objects")
    if attrs.object_type.is_root:
        return _ok("V6", "Evidence explanation references acquisition inputs")
    upstream = {r.object_id for r in attrs.derives_from}
    if not (referenced & upstream):
        return _fail(
            "V6",
            "explanation references no object the engine actually consumed",
        )
    return _ok("V6")


@_rule("V7")
def v7_create_authority(ctx: AcceptanceContext) -> RuleResult:
    """Producing engine must hold create authority. [V7, IOM section 2.5]"""
    attrs = ctx.attributes
    authorised = CREATE_AUTHORITY.get(attrs.object_type)
    if authorised is None:
        return _fail(
            "V7",
            f"no engine holds create authority for {attrs.object_type.value} "
            f"[C-02 open]",
        )
    if attrs.produced_by_engine is not authorised:
        return _fail(
            "V7",
            f"{attrs.produced_by_engine.value} may not create "
            f"{attrs.object_type.value}; authority is {authorised.value}",
        )
    return _ok("V7")


@_rule("V8")
def v8_temporal_order(ctx: AcceptanceContext) -> RuleResult:
    """observed_at <= asserted_at <= produced_at. [V8]

    Comparison is guarded: an object rehydrated from storage may carry a
    timezone-naive timestamp, and comparing naive to aware raises TypeError.
    An unguarded raise would take down the whole acceptance path, so a
    malformed object would crash rather than produce a failure record,
    breaching N-10. Mixed awareness is reported as a V8 failure instead.
    """
    a = ctx.attributes
    stamps = (
        ("observed_at", a.observed_at),
        ("asserted_at", a.asserted_at),
        ("produced_at", a.produced_at),
    )
    aware = {name: (value.tzinfo is not None) for name, value in stamps}
    if len(set(aware.values())) > 1:
        naive = sorted(n for n, is_aware in aware.items() if not is_aware)
        return _fail(
            "V8",
            f"timestamps mix timezone-aware and naive values; naive: {naive}",
        )

    if a.observed_at > a.asserted_at:
        return _fail(
            "V8",
            f"observed_at ({a.observed_at.isoformat()}) is after "
            f"asserted_at ({a.asserted_at.isoformat()})",
        )
    if a.asserted_at > a.produced_at:
        return _fail(
            "V8",
            f"asserted_at ({a.asserted_at.isoformat()}) is after "
            f"produced_at ({a.produced_at.isoformat()})",
        )
    return _ok("V8")


@_rule("V9")
def v9_status_reason(ctx: AcceptanceContext) -> RuleResult:
    """status_reason required when status is not ACTIVE. [V9, R-2]

    Every non-ACTIVE state records why it holds that state: a rejection, a
    retraction and an archival are different events and Principle 2 requires
    each to be explainable.
    """
    a = ctx.attributes
    if not a.status.requires_reason:
        return _ok("V9", "ACTIVE requires no reason")
    if not (a.status_reason or "").strip():
        return _fail("V9", f"{a.status.value} requires a non-empty status_reason")
    return _ok("V9", f"{a.status.value} reason recorded")


@_rule("V10")
def v10_no_cycle(ctx: AcceptanceContext) -> RuleResult:
    """No lineage cycle may be introduced. [V10, R-8, AD-05]

    Self-reference is checked independently of the cycle provider: an object
    deriving from itself is a cycle by definition, and must be rejected even
    where no provider is supplied or the provider is naive. Deeper cycles
    require graph reachability and remain the provider's responsibility.
    """
    a = ctx.attributes

    for ref in a.derives_from:
        if ref.object_id == a.object_id:
            return _fail(
                "V10",
                f"object {a.object_id!r} derives from itself; a self-reference "
                f"is a cycle [V10]",
            )

    if ctx.would_cycle is None:
        return _skip("V10", "self-reference clear; no cycle provider for depth")

    for ref in a.derives_from:
        if ctx.would_cycle(a.object_id, ref.object_id):
            return _fail(
                "V10",
                f"edge {a.object_id!r} -> {ref.object_id!r} would create a cycle",
            )
    return _ok("V10")


@_rule("V11")
def v11_version_increment(ctx: AcceptanceContext) -> RuleResult:
    """version = predecessor + 1; lineage_id and type unchanged. [V11, R-1]

    A supersession chain holds versions of ONE logical object, so object_type
    is invariant across it alongside lineage_id. A Fact superseded by a
    Problem would not be a new version of the same thing; it would be a
    different object wearing the same lineage_id.
    """
    a = ctx.attributes

    if ctx.predecessor is None:
        if a.version != 1:
            return _fail(
                "V11",
                f"first version must be 1, got {a.version}; declare a "
                f"predecessor to supersede an existing object",
            )
        return _ok("V11", "initial version")

    p = ctx.predecessor
    if a.lineage_id != p.lineage_id:
        return _fail(
            "V11",
            f"lineage_id must be constant across versions: "
            f"{p.lineage_id!r} -> {a.lineage_id!r}",
        )
    if a.object_type is not p.object_type:
        return _fail(
            "V11",
            f"object_type must be constant across a supersession chain: "
            f"{p.object_type.value} -> {a.object_type.value}",
        )
    if a.version != p.version + 1:
        return _fail(
            "V11", f"version must increment by 1: {p.version} -> {a.version}"
        )
    if a.object_id == p.object_id:
        return _fail("V11", "a new version requires a new object_id [I2]")
    return _ok("V11", f"version {p.version} -> {a.version}")


@_rule("V12")
def v12_closed_taxonomy(ctx: AcceptanceContext) -> RuleResult:
    """All relationships conform to the closed taxonomy. [V12, R-6]

    An object asserts relationships through four attributes, each mapping to
    one taxonomy member: derives_from (DERIVES_FROM), duplicates
    (DUPLICATES), contradicts (CONTRADICTS) and supersedes/superseded_by
    (SUPERSEDES). All four are checked, not lineage alone.

    Conformance means the declared object types are known AND the taxonomy's
    structural rules hold -- notably R-6's prohibition on self-reference,
    which Relationship enforces at construction but which objects rehydrated
    from storage bypass.
    """
    a = ctx.attributes

    for ref in a.derives_from:
        if not isinstance(ref.object_type, ObjectType):
            return _fail(
                "V12",
                f"DERIVES_FROM reference {ref.object_id!r} declares an unknown "
                f"object type {ref.object_type!r}",
            )

    peer_relationships = (
        ("DUPLICATES", a.duplicates),
        ("CONTRADICTS", a.contradicts),
    )
    for relationship, targets in peer_relationships:
        for target in targets:
            if not target:
                return _fail("V12", f"{relationship} target is empty")
            if target == a.object_id:
                return _fail(
                    "V12",
                    f"{relationship} may not reference the object itself "
                    f"{a.object_id!r} [R-6]",
                )

    for relationship, target in (
        ("SUPERSEDES", a.supersedes),
        ("SUPERSEDED_BY", a.superseded_by),
    ):
        if target is not None and target == a.object_id:
            return _fail(
                "V12",
                f"{relationship} may not reference the object itself "
                f"{a.object_id!r} [R-6]",
            )

    return _ok("V12", "all asserted relationships conform")


UNIVERSAL_RULES: tuple[Rule, ...] = (
    v1_required_attributes_present,
    v2_derives_from_non_empty,
    v3_references_resolve,
    v4_evidence_reachable,
    v5_confidence_ceiling,
    v6_explanation_references_inputs,
    v7_create_authority,
    v8_temporal_order,
    v9_status_reason,
    v10_no_cycle,
    v11_version_increment,
    v12_closed_taxonomy,
)


# ---------------------------------------------------------------------------
# Semantic hook [T01.4.6, S-5, M-67]
# ---------------------------------------------------------------------------

class SemanticVerifier(Protocol):
    """Checks rules structure cannot enforce, notably F-V6. [S-5, M-67]

    Anchor verification runs on 100% of Facts; semantic drift is sampled.
    Coverage is partial by design and the residual rate is measured.
    """

    rule_id: str

    def __call__(self, ctx: AcceptanceContext) -> RuleResult:
        ...


@dataclass
class NullSemanticVerifier:
    """Placeholder until extraction lands in P3. Records that it did not check."""

    rule_id: str = "F-V6"

    def __call__(self, ctx: AcceptanceContext) -> RuleResult:
        return _skip(self.rule_id, "semantic verification not installed [M-67]")


# ---------------------------------------------------------------------------
# The acceptance path [N-8]
# ---------------------------------------------------------------------------

@dataclass
class AcceptancePath:
    """Evaluates the rule set and gates PROPOSED -> ACTIVE. [N-8, R-2]

    The Store owns this mechanism; the rules are object-model policy passed
    in, so the Store never interprets content.
    """

    rules: Sequence[Rule] = field(default=UNIVERSAL_RULES)
    semantic_verifiers: Sequence[SemanticVerifier] = field(default_factory=tuple)
    _failures: list[FailureRecord] = field(default_factory=list, init=False)

    def evaluate(self, ctx: AcceptanceContext) -> tuple[RuleResult, ...]:
        """Run every rule. Never short-circuits: all failures are reported."""
        results = [rule(ctx) for rule in self.rules]
        results.extend(v(ctx) for v in self.semantic_verifiers)
        return tuple(results)

    def accept(self, ctx: AcceptanceContext) -> AcceptanceResult:
        """Gate the transition to ACTIVE. [R-2, N-8, N-10]"""
        results = self.evaluate(ctx)
        failures = tuple(r for r in results if r.failed)

        if failures:
            record = FailureRecord(
                object_id=ctx.attributes.object_id,
                object_type=ctx.attributes.object_type,
                failed_rules=failures,
                recorded_at=utc_now(),
                engine_configuration_ref=ctx.attributes.engine_configuration_ref,
            )
            self._failures.append(record)
            return AcceptanceResult(
                accepted=False, results=results, failure=record
            )

        # R-2 names exactly one accepted transition: PROPOSED -> ACTIVE.
        # A terminal status is preserved rather than promoted. An earlier
        # version promoted anything that was not already ACTIVE, which raised
        # an uncaught ContractError on a REJECTED write -- breaching N-10 and
        # making D-02's retention of REJECTED objects unreachable. Terminal
        # states are a legitimate write outcome, not a failure. [R-2, D-02]
        status = ctx.attributes.status
        if status is ObjectStatus.ACTIVE or status.is_terminal:
            accepted = ctx.attributes
        else:
            accepted = ctx.attributes.with_status(ObjectStatus.ACTIVE, None)
        return AcceptanceResult(accepted=True, results=results, attributes=accepted)

    @property
    def failure_records(self) -> tuple[FailureRecord, ...]:
        """Failure records accumulated. Outside the object model. [N-10]"""
        return tuple(self._failures)

    @property
    def rule_ids(self) -> tuple[str, ...]:
        return tuple(r.rule_id for r in self.rules) + tuple(
            v.rule_id for v in self.semantic_verifiers
        )
