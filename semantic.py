"""Semantic verification hook for rules structure cannot enforce.

Task: T01.4.6

Architecture References:
- N-8   Store enforces structural rules; semantic rules need a hook
- S-5   Extraction fidelity verification, three layers
- F-V6  A Fact's claim must be present in its Evidence at the stated anchor
- M-67  Hallucination detection remains OPEN; measured, not eliminated
- N-4   Outputs non-deterministic; verification is statistical

Layer 1 (anchor verification) runs on 100% of Facts and catches fabricated
LOCATION. It does NOT catch paraphrase drift -- a claim genuinely derived
from the span but subtly altered in meaning. That is Layer 2 (sampled audit),
which lands with extraction in P3, and the residual rate is published as a
platform quality metric rather than assumed to be zero.

This module supplies the hook and the anchor-verification contract. The
extraction logic that populates anchors is P3 (T03.1.3, T03.2.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from oip.acceptance import AcceptanceContext, RuleOutcome, RuleResult
from oip.enums import ObjectType


@dataclass(frozen=True)
class Anchor:
    """A positional reference into an Evidence object. [F-V2, S-5]"""

    evidence_id: str
    locator: str

    def __post_init__(self) -> None:
        if not self.evidence_id:
            raise ValueError("anchor requires an evidence_id")
        if not self.locator:
            raise ValueError("anchor requires a locator")


@dataclass(frozen=True)
class AnchorClaim:
    """A claim together with the anchor it was extracted from."""

    claim: str
    anchor: Anchor
    subject: str = ""
    predicate: str = ""
    value: str = ""


class SpanProvider(Protocol):
    """Returns the source text at an anchor, or None if unresolvable."""

    def __call__(self, anchor: Anchor) -> str | None:
        ...


@dataclass
class AnchorVerifier:
    """Layer 1 of S-5: verify a claim is locatable at its stated anchor.

    Runs on every Fact at acceptance. Checks that the anchor resolves and
    that the claim's structural components appear in the span. [S-5, F-V6]

    LIMITATION, stated deliberately: this catches fabricated anchors and
    fabricated values. It does NOT catch paraphrase drift, where the claim
    derives from the span but its meaning has shifted. Drift is sampled by
    Layer 2 and reported as a measured rate. [M-67]
    """

    rule_id: str = "F-V6"
    span_provider: SpanProvider | None = None
    claims_of: Callable[[AcceptanceContext], tuple[AnchorClaim, ...]] | None = None
    _checked: int = field(default=0, init=False)
    _failed: int = field(default=0, init=False)

    # Explicitly recorded so callers cannot mistake coverage for completeness.
    covers_paraphrase_drift: bool = field(default=False, init=False)

    def __call__(self, ctx: AcceptanceContext) -> RuleResult:
        if ctx.attributes.object_type is not ObjectType.FACT:
            return RuleResult(
                self.rule_id, RuleOutcome.SKIP, "anchor verification applies to Facts"
            )
        if self.span_provider is None or self.claims_of is None:
            return RuleResult(
                self.rule_id,
                RuleOutcome.SKIP,
                "anchor verification not configured; extraction lands in P3 [M-67]",
            )

        claims = self.claims_of(ctx)
        if not claims:
            return RuleResult(
                self.rule_id, RuleOutcome.SKIP, "no anchored claims presented"
            )

        for anchored in claims:
            self._checked += 1
            span = self.span_provider(anchored.anchor)
            if span is None:
                self._failed += 1
                return RuleResult(
                    self.rule_id,
                    RuleOutcome.FAIL,
                    f"anchor {anchored.anchor.locator!r} does not resolve in "
                    f"{anchored.anchor.evidence_id!r} -- fabricated location",
                )
            missing = self._missing_components(anchored, span)
            if missing:
                self._failed += 1
                return RuleResult(
                    self.rule_id,
                    RuleOutcome.FAIL,
                    f"claim components {missing} absent from the span at "
                    f"{anchored.anchor.locator!r}",
                )

        return RuleResult(
            self.rule_id,
            RuleOutcome.PASS,
            f"{len(claims)} claim(s) located; paraphrase drift not covered [M-67]",
        )

    @staticmethod
    def _missing_components(anchored: AnchorClaim, span: str) -> tuple[str, ...]:
        """Structured components must appear in the span. [S-3]"""
        haystack = span.casefold()
        missing = [
            name
            for name, component in (
                ("subject", anchored.subject),
                ("predicate", anchored.predicate),
                ("value", anchored.value),
            )
            if component and component.casefold() not in haystack
        ]
        return tuple(missing)

    # -- Layer 3: measured residual rate [S-5] ---------------------------

    @property
    def checked(self) -> int:
        return self._checked

    @property
    def failed(self) -> int:
        return self._failed

    @property
    def anchor_failure_rate(self) -> float:
        """Proportion of checked claims with unlocatable anchors.

        This is NOT the hallucination rate. It measures fabricated location
        only; semantic drift requires Layer 2 sampling. [S-5, M-67]
        """
        return self._failed / self._checked if self._checked else 0.0
