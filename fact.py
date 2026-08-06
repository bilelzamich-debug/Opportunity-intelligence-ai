"""Fact object type: canonical claims with evidence attachments.

Task: T01.7.2b (Fact type, F-V1..F-V6, F-I1..F-I4)

Architecture References:
- F-V1   At least one evidence attachment present
- F-V2   Every attachment has a resolvable ref and non-empty anchor
- F-V3   claim is self-contained
- F-V4   claim_type present; attributed_to required for ATTRIBUTED_OPINION
- F-V5   independent_source_count <= attachment count
- F-V6   Claim present in the referenced Evidence at the stated anchor
- F-I1   Never asserts anything absent from its attached Evidence
- F-I2   Attachments only ever added, never removed
- F-I3   Positional anchors remain resolvable
- F-I4   Merging requires explicit equivalence justification
- R-5    Facts are canonical claims, not extraction events (D-05)
- S-3    Claim structure and equivalence
- S-5    Layer 1 anchor verification; M-67 residual risk measured
- R-3    Confidence bounded by attached Evidence
- N-16   independent_source_count carried on every object
- M-67   Hallucination detection OPEN; hook only, no new detection system

A Fact is a canonical claim, not an extraction event. Ten sources attesting
one claim produce one Fact with ten attachments, not ten Facts -- this is
what makes corroboration measurable, and every downstream frequency
judgement depends on it.

F-V6 is the platform's integrity floor. Per S-5 and M-67 this module wires
the measurement hook only: anchor verification (Layer 1) is delegated to the
existing AnchorVerifier from T01.4.6. No new detection system is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.claim import Claim, EquivalenceResult, Verdict, assess_equivalence
from oip.contract import LineageRef, UniversalAttributes
from oip.enums import Engine, ObjectStatus, ObjectType
from oip.semantic import Anchor


class FactError(Exception):
    """Base class for Fact violations."""


class AttachmentError(FactError):
    """An evidence attachment is malformed. [F-V1, F-V2]"""


class ClaimTypeError(FactError):
    """claim_type inconsistent with the attribution. [F-V4]"""


class SourceCountError(FactError):
    """independent_source_count exceeds attachment count. [F-V5]"""


class AttachmentRemovalError(FactError):
    """An attachment was removed. Attachments are add-only. [F-I2]"""


class MergeJustificationError(FactError):
    """A merge lacked explicit equivalence justification. [F-I4]"""


class ClaimType(str, Enum):
    """Whether the Fact records an assertion or an attributed opinion. [F-V4]

    The distinction matters because an opinion recorded as an assertion lets
    a Problem be inferred from opinion presented as observation.
    """

    ASSERTION = "ASSERTION"
    ATTRIBUTED_OPINION = "ATTRIBUTED_OPINION"


class Independence(str, Enum):
    """Whether an attachment is independent of the others. [N-16, M-23]"""

    INDEPENDENT = "INDEPENDENT"
    NOT_INDEPENDENT = "NOT_INDEPENDENT"
    UNASSESSED = "UNASSESSED"


@dataclass(frozen=True)
class EvidenceAttachment:
    """One Evidence object attesting the canonical claim. [R-5, D-05]

    Frozen: attachments are added, never edited. Each carries its own anchor
    so a claim can be located in that specific Evidence without re-reading
    the whole source.
    """

    evidence_ref: str
    positional_anchor: str
    extracted_at: datetime
    extraction_confidence: float
    independence_assessment: Independence = Independence.UNASSESSED

    def __post_init__(self) -> None:
        if not (self.evidence_ref or "").strip():
            raise AttachmentError("attachment requires an evidence_ref [F-V2]")
        if not (self.positional_anchor or "").strip():
            raise AttachmentError(
                "attachment requires a non-empty positional_anchor; without "
                "one, verification means re-reading the whole source [F-V2]"
            )
        if not isinstance(self.extracted_at, datetime):
            raise AttachmentError("attachment requires extracted_at")
        if not 0.0 <= self.extraction_confidence <= 1.0:
            raise AttachmentError(
                f"extraction_confidence must be in [0.0, 1.0], got "
                f"{self.extraction_confidence}"
            )

    @property
    def is_independent(self) -> bool:
        return self.independence_assessment is Independence.INDEPENDENT

    def as_anchor(self) -> Anchor:
        """Project to the S-5 anchor type for Layer 1 verification."""
        return Anchor(
            evidence_id=self.evidence_ref, locator=self.positional_anchor
        )


@dataclass(frozen=True)
class MergeJustification:
    """Why two claims were judged equivalent. [F-I4, S-3]

    Recorded on every merge so the decision remains auditable. Merges are
    irreversible under I2, which is why the justification is mandatory.
    """

    verdict: Verdict
    reason: str
    merged_evidence_ref: str
    merged_at: datetime

    def __post_init__(self) -> None:
        if self.verdict is not Verdict.EQUIVALENT:
            raise MergeJustificationError(
                f"only EQUIVALENT claims may merge; got {self.verdict.value} "
                f"[S-3, F-I4]"
            )
        if not (self.reason or "").strip():
            raise MergeJustificationError(
                "merge requires an explicit reason [F-I4]"
            )


@dataclass(frozen=True)
class Fact:
    """A canonical, individually verifiable claim. [R-5, D-05]

    Composes the universal contract with the claim and its attachments.
    Frozen throughout: adding an attachment produces a new Fact via
    with_attachment(), which is a content change requiring a new version
    under R-1.
    """

    attributes: UniversalAttributes
    claim: Claim
    claim_type: ClaimType
    attachments: tuple[EvidenceAttachment, ...]
    qualifying_context: str

    # Optional attributes [IOM section 3.2]
    attributed_to: str | None = None
    temporal_scope: str | None = None
    population_scope: str | None = None
    merge_history: tuple[MergeJustification, ...] = ()

    def __post_init__(self) -> None:
        if self.attributes.object_type is not ObjectType.FACT:
            raise FactError(
                f"expected Fact, got {self.attributes.object_type.value}"
            )
        if self.attributes.produced_by_engine is not Engine.FACT_EXTRACTION:
            raise FactError(
                f"only Fact Extraction may create Facts; got "
                f"{self.attributes.produced_by_engine.value} [V7]"
            )
        # F-V1: at least one attachment, checked at construction so a Fact
        # with no attesting Evidence cannot exist even transiently.
        if not self.attachments:
            raise AttachmentError(
                "a Fact requires at least one evidence attachment [F-V1]"
            )
        # F-V4: attribution must accompany an attributed opinion.
        if self.claim_type is ClaimType.ATTRIBUTED_OPINION:
            if not (self.attributed_to or "").strip():
                raise ClaimTypeError(
                    "ATTRIBUTED_OPINION requires attributed_to [F-V4]"
                )
        if not (self.qualifying_context or "").strip():
            raise FactError(
                "qualifying_context is required; a claim stripped of its "
                "conditions changes meaning [F-V3]"
            )
        # F-V5: independence can never exceed the number of attachments.
        if self.attributes.independent_source_count > len(self.attachments):
            raise SourceCountError(
                f"independent_source_count "
                f"{self.attributes.independent_source_count} exceeds "
                f"attachment count {len(self.attachments)} [F-V5]"
            )
        seen: set[str] = set()
        for attachment in self.attachments:
            if attachment.evidence_ref in seen:
                raise AttachmentError(
                    f"Evidence {attachment.evidence_ref!r} attached twice; "
                    f"one Evidence attests a claim once"
                )
            seen.add(attachment.evidence_ref)

    # -- delegated identity ----------------------------------------------

    @property
    def object_id(self) -> str:
        return self.attributes.object_id

    @property
    def lineage_id(self) -> str:
        return self.attributes.lineage_id

    @property
    def status(self) -> ObjectStatus:
        return self.attributes.status

    @property
    def attachment_count(self) -> int:
        return len(self.attachments)

    @property
    def independent_source_count(self) -> int:
        return self.attributes.independent_source_count

    @property
    def evidence_refs(self) -> tuple[str, ...]:
        return tuple(a.evidence_ref for a in self.attachments)

    @property
    def is_corroborated(self) -> bool:
        """Attested by more than one independent source. [R-5]"""
        return self.independent_source_count > 1

    def attachment_for(self, evidence_ref: str) -> EvidenceAttachment | None:
        for attachment in self.attachments:
            if attachment.evidence_ref == evidence_ref:
                return attachment
        return None

    def counted_independent(self) -> int:
        """Attachments explicitly assessed as independent. [N-16]"""
        return sum(1 for a in self.attachments if a.is_independent)

    # -- corroboration [R-5, D-05] ----------------------------------------

    def with_attachment(
        self,
        attachment: EvidenceAttachment,
        justification: MergeJustification,
        identity=None,
        independent_source_count: int | None = None,
    ) -> "Fact":
        """Return a NEW Fact carrying an additional attachment. [R-5, F-I2]

        Corroboration is a content change, so under R-1 it produces a new
        version rather than mutating in place. The justification is mandatory
        under F-I4 because merges cannot be undone.
        """
        if self.attachment_for(attachment.evidence_ref) is not None:
            raise AttachmentError(
                f"Evidence {attachment.evidence_ref!r} is already attached"
            )
        if justification.merged_evidence_ref != attachment.evidence_ref:
            raise MergeJustificationError(
                "justification does not correspond to the attachment [F-I4]"
            )

        merged = self.attachments + (attachment,)
        count = (
            independent_source_count
            if independent_source_count is not None
            else self.independent_source_count
            + (1 if attachment.is_independent else 0)
        )
        attributes = replace(
            self.attributes,
            identity=identity or self.attributes.identity,
            derives_from=self.attributes.derives_from
            + (LineageRef(attachment.evidence_ref, ObjectType.EVIDENCE),),
            independent_source_count=count,
        )
        return replace(
            self,
            attributes=attributes,
            attachments=merged,
            merge_history=self.merge_history + (justification,),
        )

    def assess_against(self, other: Claim) -> EquivalenceResult:
        """Apply the S-3 equivalence test against another claim."""
        return assess_equivalence(self.claim, other)

    def retains_attachments_of(self, earlier: "Fact") -> bool:
        """Whether every earlier attachment survives. [F-I2]"""
        return set(earlier.evidence_refs) <= set(self.evidence_refs)


# ---------------------------------------------------------------------------
# Fact-specific acceptance rules  [F-V1 .. F-V6]
# ---------------------------------------------------------------------------

def _skip(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.SKIP, detail)


def _ok(rule_id: str, detail: str = "") -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.PASS, detail)


def _fail(rule_id: str, detail: str) -> RuleResult:
    return RuleResult(rule_id, RuleOutcome.FAIL, detail)


def _fact_of(ctx: AcceptanceContext) -> "Fact | None":
    return getattr(ctx, "fact", None)


def fv1_attachment_present(ctx: AcceptanceContext) -> RuleResult:
    """At least one evidence attachment present. [F-V1]"""
    if ctx.attributes.object_type is not ObjectType.FACT:
        return _skip("F-V1", "not a Fact")
    fact = _fact_of(ctx)
    if fact is None:
        return _skip("F-V1", "no Fact payload supplied")
    if not fact.attachments:
        return _fail("F-V1", "a Fact requires at least one attachment")
    return _ok("F-V1", f"{fact.attachment_count} attachment(s)")


def fv2_attachments_resolvable(ctx: AcceptanceContext) -> RuleResult:
    """Every attachment has a resolvable ref and non-empty anchor. [F-V2]"""
    if ctx.attributes.object_type is not ObjectType.FACT:
        return _skip("F-V2", "not a Fact")
    fact = _fact_of(ctx)
    if fact is None:
        return _skip("F-V2", "no Fact payload supplied")

    for attachment in fact.attachments:
        if not (attachment.positional_anchor or "").strip():
            return _fail(
                "F-V2",
                f"attachment to {attachment.evidence_ref!r} has no anchor",
            )
    if ctx.resolve_type is None:
        return _skip("F-V2", "anchors present; no resolver for refs")

    unresolved = [
        a.evidence_ref
        for a in fact.attachments
        if ctx.resolve_type(a.evidence_ref) is not ObjectType.EVIDENCE
    ]
    if unresolved:
        return _fail(
            "F-V2",
            f"attachment refs do not resolve to Evidence: {sorted(unresolved)}",
        )
    return _ok("F-V2", "all attachments resolvable and anchored")


def fv3_claim_self_contained(ctx: AcceptanceContext) -> RuleResult:
    """claim is self-contained. [F-V3, S-3]

    Structural check only: the S-3 components and qualifying context must be
    present, so the claim is interpretable without opening the Evidence.
    Whether the wording is genuinely self-contained is semantic and is not
    claimed to be verified here.
    """
    if ctx.attributes.object_type is not ObjectType.FACT:
        return _skip("F-V3", "not a Fact")
    fact = _fact_of(ctx)
    if fact is None:
        return _skip("F-V3", "no Fact payload supplied")

    if not (fact.qualifying_context or "").strip():
        return _fail("F-V3", "qualifying_context absent; claim loses meaning")
    if not (fact.claim.subject or "").strip():
        return _fail("F-V3", "claim has no subject [S-3]")
    if not (fact.claim.predicate or "").strip():
        return _fail("F-V3", "claim has no predicate [S-3]")
    if not (fact.claim.qualifier or "").strip():
        return _fail("F-V3", "claim has no qualifier; state NONE [S-3]")
    return _ok("F-V3", "claim structurally self-contained")


def fv4_claim_type_declared(ctx: AcceptanceContext) -> RuleResult:
    """claim_type present; attributed_to required for opinion. [F-V4]"""
    if ctx.attributes.object_type is not ObjectType.FACT:
        return _skip("F-V4", "not a Fact")
    fact = _fact_of(ctx)
    if fact is None:
        return _skip("F-V4", "no Fact payload supplied")

    if not isinstance(fact.claim_type, ClaimType):
        return _fail("F-V4", "claim_type is not a known ClaimType")
    if fact.claim_type is ClaimType.ATTRIBUTED_OPINION:
        if not (fact.attributed_to or "").strip():
            return _fail(
                "F-V4",
                "ATTRIBUTED_OPINION requires attributed_to; an opinion "
                "recorded as an assertion misleads every downstream stage",
            )
    return _ok("F-V4", fact.claim_type.value)


def fv5_source_count_bounded(ctx: AcceptanceContext) -> RuleResult:
    """independent_source_count <= attachment count. [F-V5, N-16]"""
    if ctx.attributes.object_type is not ObjectType.FACT:
        return _skip("F-V5", "not a Fact")
    fact = _fact_of(ctx)
    if fact is None:
        return _skip("F-V5", "no Fact payload supplied")

    declared = fact.independent_source_count
    available = fact.attachment_count
    if declared > available:
        return _fail(
            "F-V5",
            f"independent_source_count {declared} exceeds attachment count "
            f"{available}; corroboration cannot exceed its sources",
        )
    return _ok("F-V5", f"{declared} independent of {available} attachment(s)")


def fv6_anchor_verification(ctx: AcceptanceContext) -> RuleResult:
    """Claim present in the referenced Evidence at the stated anchor. [F-V6]

    MEASUREMENT HOOK ONLY. Per S-5 and M-67 this delegates to the existing
    AnchorVerifier (T01.4.6, Layer 1) and introduces no new detection system.
    Layer 1 catches fabricated LOCATION; it does not catch paraphrase drift,
    which is Layer 2 sampling and remains OPEN under M-67.
    """
    if ctx.attributes.object_type is not ObjectType.FACT:
        return _skip("F-V6", "not a Fact")
    fact = _fact_of(ctx)
    if fact is None:
        return _skip("F-V6", "no Fact payload supplied")

    verifier = getattr(ctx, "anchor_verifier", None)
    if verifier is None:
        return _skip(
            "F-V6",
            "anchor verification not installed; hallucination risk unmeasured "
            "[M-67 open]",
        )
    return verifier(ctx)


fv1_attachment_present.rule_id = "F-V1"      # type: ignore[attr-defined]
fv2_attachments_resolvable.rule_id = "F-V2"  # type: ignore[attr-defined]
fv3_claim_self_contained.rule_id = "F-V3"    # type: ignore[attr-defined]
fv4_claim_type_declared.rule_id = "F-V4"     # type: ignore[attr-defined]
fv5_source_count_bounded.rule_id = "F-V5"    # type: ignore[attr-defined]
fv6_anchor_verification.rule_id = "F-V6"     # type: ignore[attr-defined]

FACT_RULES = (
    fv1_attachment_present,
    fv2_attachments_resolvable,
    fv3_claim_self_contained,
    fv4_claim_type_declared,
    fv5_source_count_bounded,
    fv6_anchor_verification,
)


# ---------------------------------------------------------------------------
# Fact integrity constraints  [F-I1 .. F-I4]
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FactViolation:
    """A breached Fact integrity constraint."""

    constraint_id: str
    object_id: str
    detail: str


@dataclass
class FactIntegrity:
    """Continuous verification of F-I1..F-I4. [IOM section 3.2]

    Detective, mirroring the universal and Evidence verifiers.
    """

    fact_of: Callable[[str], "Fact | None"]
    store: "object"

    def verify(self) -> tuple[FactViolation, ...]:
        violations: list[FactViolation] = []
        violations.extend(self._check_fi1())
        violations.extend(self._check_fi2())
        violations.extend(self._check_fi3())
        violations.extend(self._check_fi4())
        return tuple(violations)

    def _all_facts(self) -> Iterable[tuple[str, "Fact"]]:
        for stored in self.store.objects_of_type(ObjectType.FACT):
            fact = self.fact_of(stored.object_id)
            if fact is not None:
                yield stored.object_id, fact

    def _check_fi1(self) -> list[FactViolation]:
        """Never asserts anything absent from its attached Evidence. [F-I1]

        Structural proxy: every attachment must reference stored Evidence.
        The semantic half -- that the claim is genuinely present -- is F-V6
        and remains measured rather than proven. [M-67]
        """
        violations: list[FactViolation] = []
        for object_id, fact in self._all_facts():
            for attachment in fact.attachments:
                stored = self.store.find(attachment.evidence_ref)
                if stored is None:
                    violations.append(
                        FactViolation(
                            "F-I1", object_id,
                            f"attached Evidence {attachment.evidence_ref!r} is "
                            f"not stored; the claim has no verifiable source",
                        )
                    )
                elif stored.object_type is not ObjectType.EVIDENCE:
                    violations.append(
                        FactViolation(
                            "F-I1", object_id,
                            f"attachment {attachment.evidence_ref!r} is a "
                            f"{stored.object_type.value}, not Evidence",
                        )
                    )
        return violations

    def _check_fi2(self) -> list[FactViolation]:
        """Attachments only ever added, never removed. [F-I2]

        Checked across a supersession chain: a later version must retain
        every attachment its predecessor carried.
        """
        violations: list[FactViolation] = []
        by_lineage: dict[str, list[tuple[int, str, "Fact"]]] = {}
        for object_id, fact in self._all_facts():
            by_lineage.setdefault(fact.lineage_id, []).append(
                (fact.attributes.version, object_id, fact)
            )

        for lineage_id, versions in by_lineage.items():
            versions.sort(key=lambda item: item[0])
            for (_, _, earlier), (_, later_id, later) in zip(
                versions, versions[1:]
            ):
                if not later.retains_attachments_of(earlier):
                    missing = sorted(
                        set(earlier.evidence_refs) - set(later.evidence_refs)
                    )
                    violations.append(
                        FactViolation(
                            "F-I2", later_id,
                            f"attachments removed across versions: {missing}; "
                            f"attachments are add-only",
                        )
                    )
        return violations

    def _check_fi3(self) -> list[FactViolation]:
        """Positional anchors remain resolvable. [F-I3]"""
        violations: list[FactViolation] = []
        for object_id, fact in self._all_facts():
            for attachment in fact.attachments:
                if not (attachment.positional_anchor or "").strip():
                    violations.append(
                        FactViolation(
                            "F-I3", object_id,
                            f"anchor into {attachment.evidence_ref!r} is empty; "
                            f"verification would require re-reading the source",
                        )
                    )
        return violations

    def _check_fi4(self) -> list[FactViolation]:
        """Merging requires explicit equivalence justification. [F-I4]

        Every attachment beyond the first arrived by a merge, so each must
        carry a recorded justification.
        """
        violations: list[FactViolation] = []
        for object_id, fact in self._all_facts():
            merges = fact.attachment_count - 1
            if merges > len(fact.merge_history):
                violations.append(
                    FactViolation(
                        "F-I4", object_id,
                        f"{merges} merge(s) but only "
                        f"{len(fact.merge_history)} justification(s) recorded",
                    )
                )
            for justification in fact.merge_history:
                if justification.verdict is not Verdict.EQUIVALENT:
                    violations.append(
                        FactViolation(
                            "F-I4", object_id,
                            f"merge recorded with verdict "
                            f"{justification.verdict.value}; only EQUIVALENT "
                            f"claims may merge [S-3]",
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Registry: canonical-claim resolution
# ---------------------------------------------------------------------------

@dataclass
class FactRegistry:
    """Holds Fact payloads and resolves canonical claims. [R-5, D-05, S-3]

    Mirrors EvidenceRegistry: the universal contract carries identity and
    confidence, while the Fact payload carries the claim and its attachments.
    """

    store: "object"
    _payloads: dict[str, Fact] = field(default_factory=dict, init=False)

    def register(self, fact: Fact) -> Fact:
        self._payloads[fact.object_id] = fact
        return fact

    def get(self, object_id: str) -> Fact | None:
        return self._payloads.get(object_id)

    def active_facts(self) -> tuple[Fact, ...]:
        facts = []
        for object_id, fact in self._payloads.items():
            stored = self.store.find(object_id)
            if stored is not None and stored.status is ObjectStatus.ACTIVE:
                facts.append(fact)
        return tuple(facts)

    def find_equivalent(self, claim: Claim) -> tuple[Fact, EquivalenceResult] | None:
        """Locate an ACTIVE Fact whose claim is equivalent. [S-3, D-05]

        Returns the first EQUIVALENT match. Under S-3's conservative policy,
        CONTAINMENT and UNCERTAIN do not merge, so they are not returned as
        merge candidates.
        """
        for fact in self.active_facts():
            result = assess_equivalence(fact.claim, claim)
            if result.verdict is Verdict.EQUIVALENT:
                return fact, result
        return None

    def assess_all(self, claim: Claim) -> tuple[tuple[Fact, EquivalenceResult], ...]:
        """Assess a claim against every ACTIVE Fact. [S-3]

        Surfaces CONTAINMENT and UNCERTAIN verdicts so the caller can record
        the DUPLICATES links S-3 requires.
        """
        return tuple(
            (fact, assess_equivalence(fact.claim, claim))
            for fact in self.active_facts()
        )

    def integrity(self) -> FactIntegrity:
        return FactIntegrity(fact_of=self.get, store=self.store)

    def __len__(self) -> int:
        return len(self._payloads)
