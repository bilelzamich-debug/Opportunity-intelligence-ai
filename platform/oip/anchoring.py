"""oip.anchoring -- the S-5 anchor bridge over real Evidence content.

T03.1.3 delivers positional anchoring: every accepted extraction carries a
resolvable positional anchor (``chars <start>-<end>``, computed, round-trip
verified and registered by :mod:`oip.extraction`). The machinery itself is
string-level and lives in extraction.py -- but feeding the RATIFIED
AnchorVerifier (T01.4.6, S-5 layer 1) needs oip.semantic's Anchor and
AnchorClaim types, and extraction.py's oip-import budget is already at the
exit gate's maximum of six. Hence this bridge: two helpers that wire the
existing S-5 machinery to real Evidence, and nothing else.

Installing the verifier at the acceptance path for 100% of Facts is
T03.2.1's deliverable; until then these helpers are used by tests and
verifiers to demonstrate F-V6 PASSING mechanically. This module adds no
component, stage, object or principle -- it is composition of ratified
machinery (Anchor, AnchorClaim, AnchorVerifier, SpanProvider, Fact,
locator format). The module graph stays a DAG: anchoring ->
{extraction, fact, semantic}; nothing imports anchoring.

Architecture References:
- S-5    layer 1: the RATIFIED AnchorVerifier over real Evidence
         content; the anchor must locate uniquely in the Evidence.
- D-04   locator discipline: closed-form computed positional locators,
         half-open, code points; never sub-string search at verify time.
- AC2    (T03.1.3) anchors are computed, round-trip verified, and
         registered only for ACCEPTED extractions.

Tasks: T03.1.3 (positional anchoring bridge).

Limitations (unchanged by design): AnchorVerifier layer 1 checks that the
anchor resolves to a real span and that subject and predicate are present
at that span; it cannot detect paraphrase drift -- a subject present
elsewhere in the same span passes. That is MISSING-67 (M-67), open.
"""

from oip.extraction import LOCATOR_PATTERN, _locate, resolve_locator
from oip.fact import Fact
from oip.semantic import Anchor, AnchorClaim, SpanProvider

__all__ = ["evidence_span_provider", "fact_anchor_claims"]


def evidence_span_provider(content: str) -> SpanProvider:
    """A SpanProvider over one Evidence's content. [S-5 layer 1]

    Resolves both anchor formats:

    - ``chars <start>-<end>`` locators by DIRECT SLICE -- no scanning; any
      parse or bounds failure is the protocol's unresolvable ``None``.
      Locating the claim never re-reads the Evidence. [T03.1.3 AC2]
    - verbatim-span anchors (the T03.1.1 convention: the anchor IS the
      span) by exact unique-substring check.
    """

    def provider(anchor: Anchor) -> str | None:
        locator = anchor.locator
        if not locator:  # pragma: no cover - defensive: the ratified Anchor
            return None  # refuses empty locators by construction
        if LOCATOR_PATTERN.fullmatch(locator.strip()):
            try:
                return resolve_locator(content, locator)
            except Exception:  # noqa: BLE001 - unresolvable is the protocol
                return None
        # verbatim-span convention: resolve by exact unique occurrence
        return locator if _locate(content, locator) == 1 else None

    return provider


def fact_anchor_claims(fact: Fact) -> tuple[AnchorClaim, ...]:
    """Project a Fact's attachments + claim into AnchorClaims.

    Feeds ``AnchorVerifier.claims_of``. Subject and predicate are the S-3
    components the Fact carries. The VALUE component is checked at
    extraction time against the verbatim ``value_text`` in the extraction
    record, which the Fact itself does not retain -- the projection emits
    no value rather than an unfaithful one.
    """
    return tuple(
        AnchorClaim(
            claim=fact.claim.as_text(),
            anchor=Anchor(
                evidence_id=attachment.evidence_ref,
                locator=attachment.positional_anchor,
            ),
            subject=fact.claim.subject,
            predicate=fact.claim.predicate,
            value="",
        )
        for attachment in fact.attachments
    )
