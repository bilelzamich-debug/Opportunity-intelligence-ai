"""oip.anchoring -- the S-5 anchor bridge over real Evidence content.

T03.1.3 delivers positional anchoring: every accepted extraction carries a
resolvable positional anchor (``chars <start>-<end>``, computed, round-trip
verified and registered by :mod:`oip.extraction`). The machinery itself is
string-level and lives in extraction.py -- but feeding the RATIFIED
AnchorVerifier (T01.4.6, S-5 layer 1) needs oip.semantic's Anchor and
AnchorClaim types, and extraction.py's oip-import budget is already at the
exit gate's maximum of six. Hence this bridge: helpers that wire the
existing S-5 machinery to real Evidence, and nothing else.

T03.2.1 installs the verifier at the acceptance path for 100% of Facts:
``install_anchor_verification`` composes the ratified AnchorVerifier over
one store's own Evidence payloads and assigns it to
``store.anchor_verifier``, where the F-V6 acceptance rule (fact.py, in
the store's default rule set) picks it up on every ``write_fact`` --
SKIP becomes PASS/FAIL and a failure blocks acceptance [S-5, N-8].
This module adds no component, stage, object or principle -- it is
composition of ratified machinery (Anchor, AnchorClaim, AnchorVerifier,
SpanProvider, Fact, locator format). The module graph stays a DAG:
anchoring -> {extraction, fact, semantic}; no oip module imports
anchoring.

Architecture References:
- S-5    layer 1: the RATIFIED AnchorVerifier over real Evidence
         content; the anchor must locate uniquely in the Evidence.
- D-04   locator discipline: closed-form computed positional locators,
         half-open, code points; never sub-string search at verify time.
- AC2    (T03.1.3) anchors are computed, round-trip verified, and
         registered only for ACCEPTED extractions.

Tasks: T03.1.3 (positional anchoring bridge); T03.2.1 (acceptance-path
installation, S-5 layer 1 on 100% of Facts).

Limitations (unchanged by design): AnchorVerifier layer 1 checks that the
anchor resolves to a real span and that subject and predicate are present
at that span; it cannot detect paraphrase drift -- a subject present
elsewhere in the same span passes. That is MISSING-67 (M-67), open.
"""

from oip.extraction import LOCATOR_PATTERN, _locate, resolve_locator
from oip.fact import Fact
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier, SpanProvider

__all__ = [
    "evidence_span_provider",
    "fact_anchor_claims",
    "install_anchor_verification",
]


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


def install_anchor_verification(store: "KnowledgeStore") -> AnchorVerifier:
    """Configure S-5 Layer 1 verification on one store. [T03.2.1, S-5, F-V6]

    Composition, not policy: the F-V6 acceptance rule (``fv6_anchor_
    verification``, fact.py) already runs on every ``write_fact`` and
    delegates to ``ctx.anchor_verifier`` -- this helper is the sanctioned
    wiring point. It binds the RATIFIED AnchorVerifier to the supplied
    store's own Evidence payloads (an anchor resolves against the FULL
    content of the referenced Evidence; missing Evidence, absent content
    or an unresolvable locator are all the protocol's ``None`` -> FAIL
    "fabricated location", fail-closed [N-15]) and installs it on
    ``store.anchor_verifier``, so every Fact written through that store
    is verified at acceptance: SKIP becomes PASS/FAIL and a failure
    blocks acceptance [S-5, N-8, N-10]. Reuses the delivered T03.1.3
    bridge verbatim -- no duplicated verification algorithm.

    The default-constructed store stays unconfigured
    (``anchor_verifier is None`` -> F-V6 SKIP, risk recorded as
    unmeasured [M-67]); each composition root calls this once. Calling
    it again replaces the installed verifier (counters reset). Pure
    wiring: no rule, store default or semantic is changed here.
    """
    # "KnowledgeStore" is referenced by name only: importing oip.store
    # here would widen this module's pinned import set.
    def span_provider(anchor: Anchor) -> str | None:
        evidence = store.get_evidence(anchor.evidence_id)
        if evidence is None:
            return None
        content = evidence.content.content
        if content is None:  # REFERENCE-mode: unverifiable in place [N-15]
            return None
        return evidence_span_provider(content)(anchor)

    verifier = AnchorVerifier(
        span_provider=span_provider,
        claims_of=lambda ctx: (
            fact_anchor_claims(ctx.fact) if ctx.fact is not None else ()
        ),
    )
    store.anchor_verifier = verifier
    return verifier
