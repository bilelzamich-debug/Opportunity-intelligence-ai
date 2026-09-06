"""oip.anchoring -- the S-5 anchor bridge over real Evidence content.

T03.1.3 delivers positional anchoring: every accepted extraction carries a
resolvable positional anchor (``chars <start>-<end>``, computed, round-trip
verified and registered by :mod:`oip.extraction`). The machinery itself is
string-level and lives in extraction.py -- but feeding the RATIFIED
AnchorVerifier (T01.4.6, S-5 layer 1) needs oip.semantic's Anchor and
AnchorClaim types, and extraction.py's oip-import budget is already at the
exit gate's maximum of six. Hence this bridge: small helpers that wire the
existing S-5 machinery to real Evidence, and nothing else -- every
public function here is composition, never a new mechanism.

T03.2.1 installs the verifier at the acceptance path for 100% of Facts:
``store_span_provider(store)`` resolves an anchor's ``evidence_id`` against
the store's Evidence payloads (FULL mode only; a dangling reference or a
REFERENCE-mode payload resolves to nothing and fails closed -- N-15), and
``install_anchor_verification(store)`` binds a ratified ``AnchorVerifier``
carrying those two helpers onto the store's existing live slot. Installation
is opt-in: an unconfigured store keeps the P1-pinned F-V6 SKIP semantics
("anchor verification not installed; hallucination risk unmeasured"), and
the swap never clobbers an existing verifier silently. This module adds no
component, stage, object or principle -- it is composition of ratified
machinery (Anchor, AnchorClaim, AnchorVerifier, SpanProvider, Fact,
locator format, the store's acceptance slot). The module graph stays a DAG:
anchoring -> {extraction, fact, semantic}; nothing imports anchoring.

Architecture References:
- S-5    layer 1: the RATIFIED AnchorVerifier over real Evidence
         content; the anchor must locate uniquely in the Evidence.
- D-04   locator discipline: closed-form computed positional locators,
         half-open, code points; never sub-string search at verify time.
- AC2    (T03.1.3) anchors are computed, round-trip verified, and
         registered only for ACCEPTED extractions.

Tasks: T03.1.3 (positional anchoring bridge);
       T03.2.1 (anchor verification at acceptance, 100% of Facts).

Limitations (unchanged by design): AnchorVerifier layer 1 checks that the
anchor resolves to a real span and that subject and predicate are present
at that span; it cannot detect paraphrase drift -- a subject present
elsewhere in the same span passes. That is MISSING-67 (M-67), open.
Installing this verification is NOT drift detection and does not close M-67;
``anchor_failure_rate`` measures fabricated location only. [S-5, T03.2.3]
"""

from typing import Callable

from oip.extraction import (
    LOCATOR_PATTERN,
    AnchoringError,
    _locate,
    resolve_locator,
)
from oip.fact import Fact
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier, SpanProvider

__all__ = [
    "evidence_span_provider",
    "fact_anchor_claims",
    "store_span_provider",
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


# ---------------------------------------------------------------------------
# T03.2.1 -- installing Layer 1 at the acceptance path for 100% of Facts
# ---------------------------------------------------------------------------


def store_span_provider(store: object) -> SpanProvider:
    """A SpanProvider resolving anchors against the store's Evidence payloads.

    Resolution is fail-closed at every step [N-08, N-15, S-5 layer 1]:

    - a dangling ``evidence_ref`` (no payload in the store) resolves to
      nothing -- the anchor cites material the platform cannot see;
    - REFERENCE-mode Evidence is not verifiable in place [N-15] -- the
      ratified ``EvidenceContent.is_verifiable_in_place`` predicate is the
      single authority on this; the provider re-implements no policy:
      None, not a pass;
    - FULL content delegates to :func:`evidence_span_provider`, which
      resolves ``chars <start>-<end>`` locators by DIRECT SLICE and the
      verbatim-span convention by unique occurrence -- no scanning, no
      guessing, deterministic in the stored bytes.

    The provider reads store state at call time under the store's own
    locking discipline; it mutates nothing.
    """

    def provider(anchor: Anchor) -> str | None:
        evidence = store.get_evidence(anchor.evidence_id)  # type: ignore[attr-defined]
        if evidence is None:
            return None
        content = evidence.content
        if not content.is_verifiable_in_place:
            return None  # REFERENCE mode [N-15]; FULL content is non-None [E-V3]
        return evidence_span_provider(content.content)(anchor)

    return provider


def install_anchor_verification(
    store: object,
    *,
    span_provider: SpanProvider | None = None,
    claims_of: Callable[[object], tuple[AnchorClaim, ...]] | None = None,
    replace: bool = False,
) -> AnchorVerifier:
    """Bind the ratified Layer-1 verifier onto ``store.anchor_verifier``.

    With a verifier installed, the existing ``F-V6`` acceptance rule
    (:func:`oip.fact.fv6_anchor_verification`) runs the ratified
    ``AnchorVerifier`` on EVERY Fact write -- all attachments of every
    new version, on every merge re-version -- because the rule delegates
    unconditionally and the store reads the slot live at each write. No
    frozen module changes; no sampling (sampling is T03.2.2's layer).

    - ``span_provider`` / ``claims_of`` default to the store-wide wiring
      built from :func:`store_span_provider` and :func:`fact_anchor_claims`;
      supply them only to verify against other material (tests, audits).
    - Installation refuses to clobber an existing verifier unless
      ``replace=True`` -- silent swap-outs of an integrity control are the
      poisoning pattern this platform refuses everywhere else.
    - The verifier is returned so the assembly point can read
      ``checked`` / ``failed`` / ``anchor_failure_rate`` later [T03.2.3].
      Its counters measure fabricated LOCATION only;
      ``covers_paraphrase_drift`` stays False [M-67].

    Thread-safety note [N-11]: the bind is an atomic attribute reference
    swap; ``_evaluate`` reads the slot once per write under the store's
    lock, so a concurrent installation cannot tear a verdict -- a write
    sees either the old verifier for its whole evaluation or the new one.
    """
    existing = getattr(store, "anchor_verifier", None)
    if existing is not None and not replace:
        raise AnchoringError(
            "anchor verification is already installed on this store; pass "
            "replace=True to swap the verifier -- an integrity control is "
            "never clobbered silently"
        )
    if span_provider is None:
        span_provider = store_span_provider(store)
    if claims_of is None:
        def claims_of(ctx: object) -> tuple[AnchorClaim, ...]:
            fact = getattr(ctx, "fact", None)
            return () if fact is None else fact_anchor_claims(fact)
    verifier = AnchorVerifier(
        span_provider=span_provider, claims_of=claims_of
    )
    store.anchor_verifier = verifier  # type: ignore[attr-defined]
    return verifier
