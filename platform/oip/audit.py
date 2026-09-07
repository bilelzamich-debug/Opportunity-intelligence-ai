"""Sampled deep audit for semantic / paraphrase drift. [S-5 Layer 2]

Task: T03.2.2

Architecture References:
- S-5    Layer 2: configurable sample of accepted Facts audited for
         semantic fidelity including the qualifier. Judgements
         FAITHFUL · DRIFTED · UNSUPPORTED. Layer 1 (location) is T03.2.1 /
         T01.4.6; Layer 3 (published rate) is T03.2.3.
- S-3    Claim structure; where comparison cannot decide, do not guess.
- S-5 vs N-4  Compare the claim against the SOURCE SPAN, never a re-run.
- N-15   Unverifiable (REFERENCE-mode, dangling, empty) is not verified.
- N-10   Records are operational, outside the object model.
- N-4    Sampling is a pure function of (seed, rate, identities).
- CI-1   Sample rate selects who is audited; it does not judge.
- M-67   Remains OPEN. Sampling is measurement, not elimination.

This module composes the ratified AnchorVerifier (Layer 1 component
presence) and S-3 Claim structure. It does not modify
AnchorVerifier.covers_paraphrase_drift (False) and introduces no engine,
object, stage or principle.

WHAT IS IMPLEMENTED (the two T03.2.2 acceptance criteria)
----------------------------------------------------------
- AC1  Sample rate configurable: AuditConfig validates [0.0, 1.0];
  0.0 disables; 1.0 audits every unique candidate; default 0.05 [S-5].
  Stratified by source type and extraction-confidence band; deterministic
  given seed; never larger than the unique candidate set.
- AC2  Detects paraphrase drift Layer 1 misses: qualifier, quantity,
  polarity, certainty, attribution, temporal markers and a closed
  conflict lexicon are examined against the resolved span. A Fact is
  verified only when every attachment is FAITHFUL.

WHAT IS DELIBERATELY NOT IMPLEMENTED
------------------------------------
T03.2.3 published rates. T03.1.6 contradictions. Auto-tuned sample
rates. Closing M-67. Re-extraction. Flipping the Layer 1 coverage flag.
"""

from __future__ import annotations

import hashlib
import math
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Iterable, Iterator

from oip.claim import UNQUALIFIED, Claim, Quantity
from oip.contract import utc_now
from oip.enums import ConfidenceBand
from oip.fact import ClaimType, EvidenceAttachment, Fact
from oip.semantic import Anchor, AnchorClaim, AnchorVerifier

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class AuditError(Exception):
    """Base class for Layer-2 audit violations."""


class AuditConfigError(AuditError):
    """Sample rate or seed is outside the validated boundary. [AC1]"""


# ---------------------------------------------------------------------------
# Closed vocabularies  [S-5 judgements; fail-closed disposition]
# ---------------------------------------------------------------------------


class AuditJudgement(str, Enum):
    """S-5 Layer-2 judgements. Closed. Completed audits only."""

    FAITHFUL = "FAITHFUL"
    DRIFTED = "DRIFTED"
    UNSUPPORTED = "UNSUPPORTED"


class AuditDisposition(str, Enum):
    """Whether an S-5 judgement could be produced.

    UNAUDITABLE is NOT a fourth S-5 judgement: it is the N-15/N-10
    failure to complete the audit. Those Facts are not verified.
    """

    COMPLETED = "COMPLETED"
    UNAUDITABLE = "UNAUDITABLE"


# S-5's initial sample rate. Configurable; this is the default only.
INITIAL_SAMPLE_RATE = 0.05

_DEFAULT_SEED = "s-5-layer-2"
_DEFAULT_CONFIG_REF = "cfg-s5-layer-2"

# Qualifier tokens that carry no independent meaning for support checks.
_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "for",
        "in",
        "on",
        "at",
        "by",
        "as",
        "from",
        "with",
        "per",
        "vs",
        "none",
    }
)

# Closed material-conflict lexicon. Pairs are symmetric at lookup.
# This is implementation of S-5's "faithfully represent", not a new
# semantic theory: each pair is a meaning-bearing opposition Layer 1
# cannot see because both sides' subject/predicate substrings can match.
_CONFLICT_PAIRS: tuple[tuple[str, str], ...] = (
    ("all", "some"),
    ("all", "none"),
    ("every", "some"),
    ("always", "never"),
    ("always", "occasionally"),
    ("always", "sometimes"),
    ("consistently", "occasionally"),
    ("consistently", "sometimes"),
    ("increase", "decrease"),
    ("increased", "decreased"),
    ("increases", "decreases"),
    ("rise", "fall"),
    ("rose", "fell"),
    ("rising", "falling"),
    ("fail", "succeed"),
    ("failed", "succeeded"),
    ("present", "absent"),
    ("will", "may"),
    ("will", "might"),
    ("must", "may"),
    ("must", "might"),
    ("definitely", "possibly"),
    ("certain", "unclear"),
    ("issues", "failures"),
    ("issue", "failure"),
)

_CONFLICT_INDEX: dict[str, frozenset[str]] = {}
for _a, _b in _CONFLICT_PAIRS:
    _CONFLICT_INDEX.setdefault(_a, set()).add(_b)  # type: ignore[arg-type]
    _CONFLICT_INDEX.setdefault(_b, set()).add(_a)  # type: ignore[arg-type]
_CONFLICT_INDEX = {k: frozenset(v) for k, v in _CONFLICT_INDEX.items()}

_NEGATION = re.compile(
    r"\b(?:not|never|no|cannot|without|neither|nor)\b|n't",
    re.IGNORECASE,
)
_RESTRICTORS = frozenset({"only", "except", "unless", "solely", "exclusively"})
_NUMBER = re.compile(r"(?<![0-9])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_YEAR = re.compile(r"\b(?:fy|fiscal\s+year\s+)?((?:19|20)\d{2})\b", re.IGNORECASE)
_TOKEN = re.compile(r"[A-Za-z0-9]+(?:'[A-Za-z]+)?")

_WORD_NUMBERS: dict[str, float] = {
    "zero": 0.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "hundred": 100.0,
}


# ---------------------------------------------------------------------------
# Configuration  [AC1, CI-1]
# ---------------------------------------------------------------------------


def _validate_rate(sample_rate: object) -> float:
    """Reject anything that is not a finite rate in [0.0, 1.0]. [AC1]"""
    if isinstance(sample_rate, bool) or not isinstance(sample_rate, (int, float)):
        raise AuditConfigError(
            f"sample_rate must be a real number in [0.0, 1.0], got {sample_rate!r}"
        )
    rate = float(sample_rate)
    if not math.isfinite(rate) or rate < 0.0 or rate > 1.0:
        raise AuditConfigError(
            f"sample_rate must be finite and in [0.0, 1.0], got {rate!r}"
        )
    return rate


@dataclass(frozen=True)
class AuditConfig:
    """Layer-2 sampling configuration. Infrastructure, not intelligence. [CI-1]

    ``sample_rate`` is a proportion in ``[0.0, 1.0]``. ``0.0`` disables
    sampling. ``1.0`` audits every unique candidate. The S-5 initial
    value is ``0.05``. Invalid values refuse at construction — the
    boundary, not the judgement function.
    """

    sample_rate: float = INITIAL_SAMPLE_RATE
    seed: str = _DEFAULT_SEED
    config_ref: str = _DEFAULT_CONFIG_REF

    def __post_init__(self) -> None:
        object.__setattr__(self, "sample_rate", _validate_rate(self.sample_rate))
        if not isinstance(self.seed, str) or not self.seed:
            raise AuditConfigError("seed is required so sampling is reproducible [N-4]")
        if not isinstance(self.config_ref, str) or not self.config_ref.strip():
            raise AuditConfigError("config_ref is required [N-4]")

    @property
    def disabled(self) -> bool:
        return self.sample_rate == 0.0


@dataclass(frozen=True)
class AuditCandidate:
    """A Fact eligible for Layer-2 sampling, with its stratification keys."""

    fact: Fact
    source_type: str
    extraction_confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.fact, Fact):
            raise AuditError("candidate requires a Fact")
        if not (self.source_type or "").strip():
            object.__setattr__(self, "source_type", "UNKNOWN")
        if not isinstance(self.extraction_confidence, (int, float)) or isinstance(
            self.extraction_confidence, bool
        ):
            raise AuditConfigError(
                f"extraction_confidence must be numeric, got "
                f"{self.extraction_confidence!r}"
            )
        conf = float(self.extraction_confidence)
        if not 0.0 <= conf <= 1.0:
            raise AuditConfigError(
                f"extraction_confidence must be in [0.0, 1.0], got {conf}"
            )
        object.__setattr__(self, "extraction_confidence", conf)

    @property
    def stratum(self) -> tuple[str, str]:
        """(source_type, confidence band) — S-5 stratification keys."""
        band = ConfidenceBand.for_value(self.extraction_confidence)
        return (self.source_type, band.value)


# ---------------------------------------------------------------------------
# Sampling  [AC1, N-4, S-5 stratification]
# ---------------------------------------------------------------------------


def _rank(seed: str, object_id: str) -> str:
    return hashlib.sha256(f"{seed}\0{object_id}".encode("utf-8")).hexdigest()


def _sample_size(n: int, rate: float) -> int:
    """How many of n to take. Never exceeds n. 0 rate → 0. [AC1]

    Zero is handled by ``floor(rate * n)``; returning 0 explicitly for
    ``rate <= 0`` is equivalent and is therefore not a second policy.
    A mutant that returns ``n`` on a non-positive rate is a real defect.
    """
    if n <= 0:
        return 0
    if rate <= 0.0:
        return 0
    if rate >= 1.0:
        return n
    return min(n, math.floor(rate * n + 1e-12))


def select_sample(
    candidates: Iterable[AuditCandidate],
    config: AuditConfig,
) -> tuple[AuditCandidate, ...]:
    """Deterministic stratified sample. [AC1, S-5, N-4]

    - Duplicate ``object_id``s collapse to the first occurrence.
    - Empty input yields an empty sample (not a failure).
    - A requested count larger than the unique set yields the whole set.
    - Rank is ``sha256(seed || object_id)`` so replay under the same
      configuration is byte-identical regardless of input order after
      dedupe (dedupe is first-wins, then rank).
    """
    if not isinstance(config, AuditConfig):
        raise AuditConfigError("select_sample requires an AuditConfig")

    unique: list[AuditCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        oid = candidate.fact.object_id
        if oid in seen:
            continue
        seen.add(oid)
        unique.append(candidate)

    if not unique:
        return ()

    by_stratum: dict[tuple[str, str], list[AuditCandidate]] = {}
    for candidate in unique:
        by_stratum.setdefault(candidate.stratum, []).append(candidate)

    chosen: list[AuditCandidate] = []
    for stratum in sorted(by_stratum):
        group = by_stratum[stratum]
        group.sort(key=lambda c: (_rank(config.seed, c.fact.object_id), c.fact.object_id))
        k = _sample_size(len(group), config.sample_rate)
        chosen.extend(group[:k])

    chosen.sort(key=lambda c: (_rank(config.seed, c.fact.object_id), c.fact.object_id))
    return tuple(chosen)


# ---------------------------------------------------------------------------
# Comparison against the source span  [AC2, S-5, S-3]
# ---------------------------------------------------------------------------


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().casefold())


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t.casefold() for t in _TOKEN.findall(text or ""))


def _content_tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _tokens(text) if t not in _STOP)


def _numbers_in(text: str) -> tuple[float, ...]:
    found: list[float] = []
    for raw in _NUMBER.findall(text or ""):
        found.append(float(raw.replace(",", "")))
    for token in _tokens(text):
        if token in _WORD_NUMBERS:
            found.append(_WORD_NUMBERS[token])
    return tuple(found)


def _years_in(text: str) -> frozenset[str]:
    return frozenset(m.group(1) for m in _YEAR.finditer(text or ""))


def _has_negation(text: str) -> bool:
    return _NEGATION.search(text or "") is not None


def _supported_in_span(token: str, span_folded: str) -> bool:
    """Substring support: 'europe' is supported by 'european markets'."""
    return token.casefold() in span_folded


def _lexicon_conflicts(claim_tokens: frozenset[str], span_tokens: frozenset[str]) -> tuple[str, ...]:
    conflicts: list[str] = []
    for token in sorted(claim_tokens):
        opposed = _CONFLICT_INDEX.get(token)
        if not opposed:
            continue
        hit = opposed & span_tokens
        if hit and token not in span_tokens:
            conflicts.append(f"{token} vs {sorted(hit)[0]}")
    return tuple(conflicts)


def _layer1_missing(claim: Claim, span: str) -> tuple[str, ...]:
    """Compose the ratified Layer-1 predicate, including value. [S-5, S-3]

    Acceptance-path Layer 1 (`fact_anchor_claims`) emits no value. Layer 2
    includes it so quantity fabrication the Fact-path misses is visible.
    Subject/predicate absence is still Layer 1's UNSUPPORTED case.
    """
    value_text = ""
    if claim.value is not None:
        number = claim.value.value
        value_text = str(int(number)) if float(number).is_integer() else str(number)
    anchored = AnchorClaim(
        claim=claim.as_text(),
        anchor=Anchor(evidence_id="audit", locator="span"),
        subject=claim.subject,
        predicate=claim.predicate,
        value=value_text,
    )
    return AnchorVerifier._missing_components(anchored, span)


def _value_agrees(value: Quantity | None, span: str) -> bool | None:
    """True if the asserted quantity is supported by the span; False if a
    conflicting quantity is present; None if the claim is unquantified.
    """
    if value is None:
        return None
    span_numbers = _numbers_in(span)
    if any(abs(n - value.value) <= max(value.precision, 0.0) for n in span_numbers):
        return True
    if span_numbers:
        return False
    return False


# ---------------------------------------------------------------------------
# Records  [provenance, N-10]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditRecord:
    """One attachment's Layer-2 audit, with enough provenance to explain it."""

    fact_id: str
    lineage_id: str
    fact_version: int
    evidence_id: str
    locator: str
    compared_span: str
    sample_rate: float
    seed: str
    config_ref: str
    disposition: AuditDisposition
    judgement: AuditJudgement | None
    reason: str
    layer1_pass: bool
    audited_at: datetime

    def __post_init__(self) -> None:
        if not (self.fact_id or "").strip():
            raise AuditError("fact_id is required")
        if not (self.evidence_id or "").strip():
            raise AuditError("evidence_id is required")
        if not (self.reason or "").strip():
            raise AuditError("reason is required [Principle 2]")
        if not isinstance(self.disposition, AuditDisposition):
            raise AuditError("disposition is outside the closed set")
        if self.disposition is AuditDisposition.COMPLETED:
            if not isinstance(self.judgement, AuditJudgement):
                raise AuditError("a completed audit must carry an S-5 judgement")
        else:
            if self.judgement is not None:
                raise AuditError(
                    "an unauditable result must not carry an S-5 judgement; "
                    "unverifiable material is not verified [N-15]"
                )

    @property
    def verified(self) -> bool:
        """True only for a completed FAITHFUL audit. Fail-closed otherwise."""
        return (
            self.disposition is AuditDisposition.COMPLETED
            and self.judgement is AuditJudgement.FAITHFUL
        )


@dataclass
class AuditRegister:
    """Append-only register of Layer-2 audit records. [N-10 — outside the model]"""

    _records: list[AuditRecord] = field(default_factory=list, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def append(self, record: AuditRecord) -> AuditRecord:
        with self._lock:
            self._records.append(record)
        return record

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __iter__(self) -> Iterator[AuditRecord]:
        with self._lock:
            return iter(tuple(self._records))

    def for_fact(self, fact_id: str) -> tuple[AuditRecord, ...]:
        with self._lock:
            return tuple(r for r in self._records if r.fact_id == fact_id)

    @property
    def participates_in_lineage(self) -> bool:
        return False


SpanOf = Callable[[Fact, EvidenceAttachment], str | None]


def _record(
    fact: Fact,
    attachment: EvidenceAttachment,
    config: AuditConfig,
    *,
    span: str,
    disposition: AuditDisposition,
    judgement: AuditJudgement | None,
    reason: str,
    layer1_pass: bool,
    clock,
) -> AuditRecord:
    return AuditRecord(
        fact_id=fact.object_id,
        lineage_id=fact.lineage_id,
        fact_version=fact.attributes.version,
        evidence_id=attachment.evidence_ref,
        locator=attachment.positional_anchor,
        compared_span=span,
        sample_rate=config.sample_rate,
        seed=config.seed,
        config_ref=config.config_ref,
        disposition=disposition,
        judgement=judgement,
        reason=reason,
        layer1_pass=layer1_pass,
        audited_at=clock(),
    )


def audit_attachment(
    fact: Fact,
    attachment: EvidenceAttachment,
    span: str | None,
    config: AuditConfig,
    *,
    clock=None,
) -> AuditRecord:
    """Deep-audit one attachment against its resolved source span. [AC2]

    ``span is None`` means the provider could not resolve content
    (REFERENCE-mode, dangling ref, unreadable). That is UNAUDITABLE,
    never FAITHFUL. [N-15]
    """
    now = clock or utc_now
    locator = attachment.positional_anchor

    if span is None:
        return _record(
            fact,
            attachment,
            config,
            span="",
            disposition=AuditDisposition.UNAUDITABLE,
            judgement=None,
            reason=(
                f"span at {locator!r} in {attachment.evidence_ref!r} is "
                f"unavailable; unverifiable material is not verified [N-15]"
            ),
            layer1_pass=False,
            clock=now,
        )
    if not str(span).strip():
        return _record(
            fact,
            attachment,
            config,
            span=span,
            disposition=AuditDisposition.UNAUDITABLE,
            judgement=None,
            reason=(
                f"span at {locator!r} is empty; insufficient content to "
                f"determine semantic fidelity [N-15]"
            ),
            layer1_pass=False,
            clock=now,
        )

    claim = fact.claim
    missing = _layer1_missing(claim, span)
    location_missing = tuple(m for m in missing if m in ("subject", "predicate"))
    layer1_pass = not location_missing

    if location_missing:
        return _record(
            fact,
            attachment,
            config,
            span=span,
            disposition=AuditDisposition.COMPLETED,
            judgement=AuditJudgement.UNSUPPORTED,
            reason=(
                f"claim components {location_missing} absent from the span "
                f"at {locator!r} — fabricated location [S-5 Layer 1]"
            ),
            layer1_pass=False,
            clock=now,
        )

    # --- meaning checks Layer 1 does not perform --------------------------
    claim_text = claim.as_text()
    span_folded = span.casefold()
    claim_tokens = _content_tokens(claim_text)
    if not claim.is_unqualified:
        claim_tokens |= _content_tokens(claim.qualifier)
    if fact.attributed_to:
        claim_tokens |= _content_tokens(fact.attributed_to)
    span_tokens = _content_tokens(span)

    if _has_negation(claim_text) != _has_negation(span):
        return _record(
            fact,
            attachment,
            config,
            span=span,
            disposition=AuditDisposition.COMPLETED,
            judgement=AuditJudgement.DRIFTED,
            reason=(
                f"negation polarity of the claim does not match the span "
                f"at {locator!r}"
            ),
            layer1_pass=True,
            clock=now,
        )

    conflicts = _lexicon_conflicts(claim_tokens, span_tokens)
    if conflicts:
        return _record(
            fact,
            attachment,
            config,
            span=span,
            disposition=AuditDisposition.COMPLETED,
            judgement=AuditJudgement.DRIFTED,
            reason=(
                f"material semantic conflict with the span at {locator!r}: "
                f"{'; '.join(conflicts)}"
            ),
            layer1_pass=True,
            clock=now,
        )

    value_ok = _value_agrees(claim.value, span)
    if value_ok is False:
        return _record(
            fact,
            attachment,
            config,
            span=span,
            disposition=AuditDisposition.COMPLETED,
            judgement=AuditJudgement.DRIFTED,
            reason=(
                f"asserted quantity {claim.value.value} is not supported by "
                f"the span at {locator!r}"
            ),
            layer1_pass=True,
            clock=now,
        )

    claim_years = _years_in(claim.qualifier) | _years_in(claim_text)
    if fact.temporal_scope:
        claim_years |= _years_in(fact.temporal_scope)
    span_years = _years_in(span)
    if claim_years and span_years and claim_years != span_years:
        return _record(
            fact,
            attachment,
            config,
            span=span,
            disposition=AuditDisposition.COMPLETED,
            judgement=AuditJudgement.DRIFTED,
            reason=(
                f"temporal markers {sorted(claim_years)} disagree with span "
                f"years {sorted(span_years)} at {locator!r}"
            ),
            layer1_pass=True,
            clock=now,
        )
    if claim_years and not claim_years <= span_years | {
        y for y in claim_years if y in span
    }:
        unsupported_years = claim_years - span_years
        if unsupported_years and not all(y in span for y in unsupported_years):
            return _record(
                fact,
                attachment,
                config,
                span=span,
                disposition=AuditDisposition.COMPLETED,
                judgement=AuditJudgement.DRIFTED,
                reason=(
                    f"asserted year(s) {sorted(unsupported_years)} absent "
                    f"from the span at {locator!r}"
                ),
                layer1_pass=True,
                clock=now,
            )

    if fact.claim_type is ClaimType.ATTRIBUTED_OPINION:
        attributed = (fact.attributed_to or "").strip()
        if attributed and not _supported_in_span(_normalise(attributed), span_folded):
            # whole-string first; then token support
            attr_tokens = _content_tokens(attributed)
            if attr_tokens and not all(
                _supported_in_span(t, span_folded) for t in attr_tokens
            ):
                return _record(
                    fact,
                    attachment,
                    config,
                    span=span,
                    disposition=AuditDisposition.COMPLETED,
                    judgement=AuditJudgement.DRIFTED,
                    reason=(
                        f"attribution {attributed!r} is not supported by the "
                        f"span at {locator!r}"
                    ),
                    layer1_pass=True,
                    clock=now,
                )

    if claim.is_unqualified:
        dropped = _RESTRICTORS & span_tokens
        if dropped:
            return _record(
                fact,
                attachment,
                config,
                span=span,
                disposition=AuditDisposition.COMPLETED,
                judgement=AuditJudgement.DRIFTED,
                reason=(
                    f"span at {locator!r} carries restrictor(s) {sorted(dropped)} "
                    f"the unqualified claim dropped"
                ),
                layer1_pass=True,
                clock=now,
            )
    else:
        qualifier_tokens = _content_tokens(claim.qualifier)
        # Years already compared; do not double-penalise FY2024 vs 2024.
        qualifier_tokens -= {y for y in qualifier_tokens if y.isdigit() and len(y) == 4}
        qualifier_tokens -= {t for t in qualifier_tokens if t.startswith("fy") and t[2:].isdigit()}
        missing_qual = [
            t for t in sorted(qualifier_tokens) if not _supported_in_span(t, span_folded)
        ]
        if missing_qual:
            return _record(
                fact,
                attachment,
                config,
                span=span,
                disposition=AuditDisposition.COMPLETED,
                judgement=AuditJudgement.DRIFTED,
                reason=(
                    f"qualifier tokens {missing_qual} are not supported by "
                    f"the span at {locator!r} — meaning not faithful [S-5]"
                ),
                layer1_pass=True,
                clock=now,
            )

    return _record(
        fact,
        attachment,
        config,
        span=span,
        disposition=AuditDisposition.COMPLETED,
        judgement=AuditJudgement.FAITHFUL,
        reason=(
            f"claim including qualifier is supported by the span at "
            f"{locator!r}; acceptable paraphrase of locatable material"
        ),
        layer1_pass=True,
        clock=now,
    )


_ROLLUP = {
    AuditDisposition.UNAUDITABLE: 0,
    AuditJudgement.UNSUPPORTED: 1,
    AuditJudgement.DRIFTED: 2,
    AuditJudgement.FAITHFUL: 3,
}


def _severity(record: AuditRecord) -> int:
    if record.disposition is AuditDisposition.UNAUDITABLE:
        return _ROLLUP[AuditDisposition.UNAUDITABLE]
    assert record.judgement is not None
    return _ROLLUP[record.judgement]


def rollup(records: tuple[AuditRecord, ...]) -> AuditRecord:
    """Fail-closed Fact-level result: the most severe attachment governs."""
    if not records:
        raise AuditError("rollup requires at least one attachment record")
    return min(records, key=_severity)


def audit_fact(
    fact: Fact,
    span_of: SpanOf,
    config: AuditConfig,
    *,
    clock=None,
) -> tuple[AuditRecord, ...]:
    """Deep-audit every attachment of one Fact. [AC2, F-V1]"""
    return tuple(
        audit_attachment(fact, attachment, span_of(fact, attachment), config, clock=clock)
        for attachment in fact.attachments
    )


def run_sampled_audit(
    candidates: Iterable[AuditCandidate],
    span_of: SpanOf,
    config: AuditConfig,
    register: AuditRegister | None = None,
    *,
    clock=None,
) -> tuple[AuditRecord, ...]:
    """Sample, deep-audit, record. Unsampled Facts are not verified. [AC1, AC2]"""
    sample = select_sample(candidates, config)
    produced: list[AuditRecord] = []
    for candidate in sample:
        for record in audit_fact(candidate.fact, span_of, config, clock=clock):
            if register is not None:
                register.append(record)
            produced.append(record)
    return tuple(produced)
