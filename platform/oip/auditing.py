"""Layers 2 and 3 of S-5: the sampled fidelity audit of accepted
Facts and its published hallucination/drift quality metrics.
[T03.2.2, T03.2.3]

Tasks: T03.2.2, T03.2.3

Architecture References:
- S-5     Extraction fidelity verification, three layers. Layer 1 (anchor
          verification, ``oip.semantic`` + ``oip.anchoring``) runs on 100
          percent of Facts at acceptance and catches fabricated LOCATION.
          Layers 2 and 3 -- THIS MODULE -- sample accepted Facts for
          fidelity (Layer 2): a human-equivalent auditor judges whether
          the claim is a faithful rendering of the anchored source span.
          It catches paraphrase drift, which structural checks cannot.
          Layer 3 publishes the measured hallucination/drift rates
          (F-A2, below). [M-67]
- M-67    Hallucination detection remains OPEN: measured, not eliminated.
          Layer 2 measures on a sample; it never assumes zero. The
          published residual-rate metrics (Layer 3, T03.2.3, F-A2) are
          computed in this module -- measured, never assumed away.
- N-2     Exactly three human gates (G1/G2/G3). Layer 2 is NOT a
          fourth gate: it decides no transition, holds no object in
          any state, and never blocks Fact acceptance. [F-A1 R1, R8]
- N-4     Outputs are non-deterministic; verification is statistical.
          Selection is a deterministic hash threshold over a stable
          identity string, so the sample is reproducible without
          randomness at runtime.
- N-7/CI-1 Configuration isolation: the sampling policy is
          infrastructure state under the CI-1 discipline -- immutable,
          versioned, held with the audit surface, never in reasoning,
          scoring, support or lineage, and not an engine
          ConfigurationRecord. [F-A1 R10, R6]
- N-8     Mechanism and policy are separated. This module is Layer-2
          mechanism plus the ratified default policy; the Store exposes
          only a hook slot (``audit_sampler``) and stays free of audit
          policy. ``install_sampled_audit`` is composition, mirroring
          ``install_anchor_verification``.
- N-10    Failures are recorded, never silent. Selection failures land
          on the audit register's failure list and an optional
          caller-supplied ``on_error`` callback; they NEVER block a
          committed acceptance and NEVER propagate into the Store's
          write path.
- F-A1    The sampled fidelity audit decision record (docs/decisions/
          F-A1-sampled-fidelity-audit.md): global 5 percent sample,
          stratified by SourceType and ConfidenceBand, every attachment
          considered (never first-attachment), one audit per Fact per
          policy version, closed judgement set, append-only register,
          no lifecycle effect, no fourth acceptance gate.
- F-A2    The Layer-3 quality-metrics decision record (docs/decisions/
          F-A2-layer3-quality-metrics.md): hallucination rate =
          unsupported / judged and drift rate = drifted / judged over
          JUDGED records only (pending selections and N-10
          SelectionFailures are context counts, never rate components);
          None when nothing is judged; global and per-policy-version
          scopes; a queryable frozen snapshot surface; judged_at-based
          sparse UTC-day trends. No estimator, no thresholds, and the
          configured sampling rate never enters a metric.
- N-3     Success criteria: the published hallucination rate is the
          stage-2 (Facts) proxy measure, reported alongside platform
          output so consumers can weigh it. The general stage-proxy
          machinery and phase-exit wiring are T09.1.4, not this module.

Boundaries ratified by F-A1 and T03.2.2 (violating any of these is a
regression, not an extension):

* No LLM, NLP, network, or external semantic engine is invoked. The
  judgement comes from a ``JudgementProvider`` supplied by composition
  (a human auditor in production; a fixture in tests).
* No new Intelligence Object, RelationshipType, or lifecycle state is
  introduced. The audit register is NOT part of the Intelligence Object
  Model and audit records are not Intelligence Objects.
* Facts are never mutated for audit purposes. Judgements live in
  ``AuditRecord`` objects inside the register, never on the Fact.
* No automatic rejection, retraction, supersession, or invalidation
  follows from a DRIFTED or UNSUPPORTED judgement. Publication of
  consequences is a human decision outside this module.
* Audit never blocks acceptance: Layer 2 runs only AFTER a Fact is
  committed, and the Store's hook guard treats the sampler as
  best-effort. There is no fourth N-2 gate.
* No automatic rate adjustment, no invented thresholds or formulas:
  the sampling rate is a policy constant. The Layer-3 metrics below
  are DESCRIPTIVE proportions over judged records [F-A2] -- no
  estimator, threshold, significance rule or sampling correction
  exists, and the configured rate never enters them.
* Layer 1 (T03.2.1) is untouched: ``oip.semantic`` and
  ``oip.anchoring`` are imported by NOBODY here -- span resolution is
  an injected callable so this module's import surface stays at the
  ratified four (enums, evidence, fact, source).

Import budget [F-A1, T03.2.2; unchanged by T03.2.3, F-A2]:
``oip.enums``, ``oip.evidence``, ``oip.fact``, ``oip.source`` only. Nothing in the platform imports
``oip.auditing`` (composition roots wire it), so no cycle is possible.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from enum import Enum
from typing import Callable, Protocol

from oip.enums import ConfidenceBand
from oip.evidence import Evidence
from oip.fact import Fact
from oip.source import SourceType, classify

__all__ = [
    "AuditContext",
    "AuditError",
    "AuditJudgement",
    "AuditRecord",
    "AuditRecordError",
    "AuditRegister",
    "AlreadyJudgedError",
    "DuplicateSelectionError",
    "JudgementProvider",
    "MetricTrendPoint",
    "NoPendingSelectionError",
    "POLICY_V1",
    "QualityMetricSnapshot",
    "SamplingPolicy",
    "SamplingPolicyError",
    "SelectionFailure",
    "SpanResolver",
    "install_sampled_audit",
    "judge_pending",
    "metric_trend",
    "quality_metrics",
    "selects",
]

# The F-A1 global sample rate: 5 percent of accepted Facts, measured
# over the whole population and within each stratum. This is the
# ratified constant, not a tunable the platform adjusts on its own.
F_A1_SAMPLE_RATE: float = 0.05

# Ratification date of F-A1 / T03.2.2 -- a FIXED, import-stable
# timestamp. datetime.now() at import time would make every process
# carry a different policy provenance; a policy version is a decision,
# and decisions are stamped when they are made.
POLICY_RECORDED_AT = datetime(2026, 9, 12, tzinfo=timezone.utc)


def _utc_now() -> datetime:
    """Timezone-aware now, mirroring ``oip.contract.utc_now``.

    Re-declared locally (rather than importing ``oip.contract``) to keep
    this module's import surface at the four ratified modules.
    """
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Judgements
# ---------------------------------------------------------------------------


class AuditJudgement(str, Enum):
    """The closed set of Layer-2 audit outcomes. [F-A1, M-67]

    FAITHFUL -- the claim is a faithful rendering of the anchored span
    in its Evidence context.

    DRIFTED -- the claim derives from the span but its meaning has
    shifted (paraphrase drift: precisely what Layer 1 cannot catch).

    UNSUPPORTED -- the span does not support the claim as stated.

    The set is closed: a provider returning anything else is a contract
    breach and is refused, never coerced and never defaulted. There is
    no ``UNKNOWN`` and no implicit FAITHFUL.
    """

    FAITHFUL = "FAITHFUL"
    DRIFTED = "DRIFTED"
    UNSUPPORTED = "UNSUPPORTED"


class AuditError(Exception):
    """Base class for Layer-2 audit errors. Never raised from the
    acceptance path: audit is non-gating [F-A1, N-10]."""


class SamplingPolicyError(AuditError):
    """A sampling policy violates its ratified invariants."""


class AuditRecordError(AuditError):
    """An audit record violates its invariants (immutability, closed
    judgement set, pending/judged consistency)."""


class DuplicateSelectionError(AuditError):
    """A Fact was already selected under the same policy version.

    One audit per Fact per policy version [F-A1]: re-selection requires
    a superseding policy version.
    """


class NoPendingSelectionError(AuditError):
    """No pending selection exists for the given Fact and policy."""


class AlreadyJudgedError(AuditError):
    """The selection was already judged: judgements complete exactly
    once and are then immutable [F-A1]."""


# ---------------------------------------------------------------------------
# Sampling policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SamplingPolicy:
    """An immutable, versioned audit sampling policy. [F-A1]

    A policy is a DECISION, so it is frozen and versioned like one:
    changing the rate or the salt means a new version, never in-place
    mutation. The version participates in selection, so selections made
    under different versions are independent samples, and the register's
    dedup key is (fact, policy_version).

    rate is the per-stratum draw probability: the stratum participates
    in the canonical hash input (execution spec section 7), so each of
    a Fact's distinct eligible strata is evaluated independently at
    this rate. A single-stratum Fact is selected with probability
    equal to the rate; a Fact spanning k distinct eligible strata has
    union selection probability 1-(1-rate)**k (9.75 percent at 5
    percent for k=2), capped at one audit unit by the single-audit
    dedup. The rate is ONE global constant -- no per-stratum quotas,
    no separate 5 percent populations, never adjusted automatically.
    [F-A1 R3; RATIFICATION-ANNOTATIONS section 14, multi-stratum union
    annotation]
    salt separates selection domains so that versions cannot be forced
    to correlate; it is part of the hashed identity string.
    """

    version: int
    rate: float
    salt: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.version, int) or isinstance(self.version, bool):
            raise SamplingPolicyError("policy version must be an integer >= 1")
        if self.version < 1:
            raise SamplingPolicyError("policy version must be >= 1")
        if not isinstance(self.rate, (int, float)) or isinstance(self.rate, bool):
            raise SamplingPolicyError("policy rate must be a number in [0.0, 1.0]")
        if not 0.0 <= float(self.rate) <= 1.0:
            raise SamplingPolicyError(
                f"policy rate must be in [0.0, 1.0], got {self.rate!r}"
            )
        if not isinstance(self.salt, str) or not self.salt.strip():
            raise SamplingPolicyError("policy salt is required (non-empty string)")
        if self.recorded_at is None:
            raise SamplingPolicyError("policy recorded_at is required")


#: The ratified default policy: version 1, global 5 percent, stable
#: salt, stamped with the F-A1 ratification date. [F-A1]
POLICY_V1 = SamplingPolicy(
    version=1,
    rate=F_A1_SAMPLE_RATE,
    salt="f-a1-v1",
    recorded_at=POLICY_RECORDED_AT,
)


def selects(
    fact_object_id: str,
    source_type: SourceType,
    confidence_band: ConfidenceBand,
    policy: SamplingPolicy,
) -> bool:
    """Deterministically decide whether one stratum of one Fact is in
    the sample. [F-A1, N-4]

    Pure function of its arguments: no randomness, no clock, no state.
    The canonical identity string is
    ``{version}:{salt}:{fact}:{source_type}:{band}``; its SHA-256
    digest's first 8 bytes, read big-endian and normalised to [0, 1),
    must fall below the policy rate. Uniformity of SHA-256 makes each
    (fact, stratum) draw's probability equal to the rate; the
    Fact-level union over its k distinct eligible strata is
    1-(1-rate)**k (see SamplingPolicy and RATIFICATION-ANNOTATIONS
    section 14) -- one global rate constant, never per-stratum quotas.

    Boundary semantics: rate 0.0 selects nothing; rate 1.0 selects
    everything (the normalised threshold is always < 1.0).
    """
    if not isinstance(fact_object_id, str) or not fact_object_id.strip():
        raise AuditError("selects() requires a non-empty fact_object_id")
    if not isinstance(source_type, SourceType):
        raise AuditError(
            f"source_type must be a SourceType member, got {source_type!r}"
        )
    if not isinstance(confidence_band, ConfidenceBand):
        raise AuditError(
            "confidence_band must be a ConfidenceBand member, "
            f"got {confidence_band!r}"
        )
    if not isinstance(policy, SamplingPolicy):
        raise AuditError(f"policy must be a SamplingPolicy, got {policy!r}")

    canonical = (
        f"{policy.version}:{policy.salt}:{fact_object_id}:"
        f"{source_type.value}:{confidence_band.value}"
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    threshold = int.from_bytes(digest[:8], "big") / float(2**64)
    return threshold < float(policy.rate)


# ---------------------------------------------------------------------------
# The audit register
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditRecord:
    """One sampled audit unit: immutable, versioned by policy. [F-A1]

    Created PENDING (judgement None) at selection time, carrying the
    selecting EvidenceAttachment's reference and anchor, the stratum
    that selected it, and the policy version responsible. Completed
    exactly once by ``AuditRegister.record_judgement``, which produces
    a NEW frozen record -- records are never mutated in place. The
    register is append-only: selections are only ever added, and a
    completion replaces its own pending slot, never another record's.

    This is NOT an Intelligence Object: it lives in the audit register
    (outside the IOM), participates in no lifecycle, and can never
    gate, reject, or supersede anything. [F-A1, N-8]
    """

    fact_object_id: str
    evidence_ref: str
    positional_anchor: str
    source_type: SourceType
    confidence_band: ConfidenceBand
    policy_version: int
    selected_at: datetime
    judgement: AuditJudgement | None = None
    judged_at: datetime | None = None
    auditor: str | None = None

    def __post_init__(self) -> None:
        for name in ("fact_object_id", "evidence_ref", "positional_anchor"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise AuditRecordError(f"AuditRecord requires a non-empty {name}")
        if not isinstance(self.source_type, SourceType):
            raise AuditRecordError("source_type must be a SourceType member")
        if not isinstance(self.confidence_band, ConfidenceBand):
            raise AuditRecordError(
                "confidence_band must be a ConfidenceBand member"
            )
        if (
            not isinstance(self.policy_version, int)
            or isinstance(self.policy_version, bool)
            or self.policy_version < 1
        ):
            raise AuditRecordError("policy_version must be an integer >= 1")
        if self.selected_at is None:
            raise AuditRecordError("selected_at is required")
        if self.judgement is None:
            # Pending: no judgement has been made, so no judgement
            # metadata may exist. FAITHFUL is never implicit.
            if self.judged_at is not None or self.auditor is not None:
                raise AuditRecordError(
                    "a pending selection carries no judged_at/auditor; "
                    "there is no implicit judgement [F-A1]"
                )
        else:
            if not isinstance(self.judgement, AuditJudgement):
                raise AuditRecordError(
                    "judgement must be an AuditJudgement member; the "
                    "set is closed [F-A1]"
                )
            if self.judged_at is None:
                raise AuditRecordError("a judged record requires judged_at")
            if not isinstance(self.auditor, str) or not self.auditor.strip():
                raise AuditRecordError("a judged record requires an auditor")

    @property
    def is_pending(self) -> bool:
        return self.judgement is None


@dataclass(frozen=True)
class SelectionFailure:
    """An operational failure to sample a Fact. [N-10]

    Recorded, never silent, and never a gate: the Fact's committed
    acceptance stands. Sampling failures are observable so the sample's
    coverage can be audited itself.
    """

    fact_object_id: str
    policy_version: int
    detail: str
    occurred_at: datetime


class AuditRegister:
    """Append-only register of sampled audit units. [F-A1]

    Lives OUTSIDE the Intelligence Object Model. Selections are added
    only; a selection is completed exactly once (pending -> judged),
    which replaces its own slot with a new immutable record. Records
    are never removed and completed judgements are never overwritten.

    Dedup: one selection per (fact, policy_version). A superseding
    policy version may select the same Fact again -- that is a new
    audit, not a duplicate.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: list[AuditRecord] = []
        self._failures: list[SelectionFailure] = []

    # -- selection --------------------------------------------------------

    def select(self, record: AuditRecord) -> AuditRecord:
        """Append a pending selection. [F-A1]

        Raises DuplicateSelectionError if this Fact already has a
        selection under the same policy version (one audit per Fact per
        policy version). Only pending records may be selected; the
        register never receives a pre-judged record.
        """
        if not isinstance(record, AuditRecord):
            raise AuditRecordError(f"expected AuditRecord, got {record!r}")
        if not record.is_pending:
            raise AuditRecordError(
                "only pending (unjudged) records may be selected; "
                "judgements complete via record_judgement [F-A1]"
            )
        with self._lock:
            if self.has_selection(record.fact_object_id, record.policy_version):
                raise DuplicateSelectionError(
                    f"fact {record.fact_object_id} is already selected "
                    f"under policy version {record.policy_version}; one "
                    "audit per Fact per policy version [F-A1]"
                )
            self._records.append(record)
            return record

    def has_selection(self, fact_object_id: str, policy_version: int) -> bool:
        with self._lock:
            return any(
                r.fact_object_id == fact_object_id
                and r.policy_version == policy_version
                for r in self._records
            )

    # -- judgement --------------------------------------------------------

    def record_judgement(
        self,
        fact_object_id: str,
        policy_version: int,
        judgement: AuditJudgement,
        *,
        auditor: str,
        judged_at: datetime | None = None,
    ) -> AuditRecord:
        """Complete a pending selection exactly once. [F-A1]

        The judgement must be an explicit AuditJudgement member -- the
        set is closed and nothing is ever coerced or defaulted
        (FAITHFUL is never implicit). The auditor is a required,
        non-empty identity. Returns the NEW immutable completed record;
        the pending record is never mutated in place.
        """
        if not isinstance(judgement, AuditJudgement):
            raise AuditRecordError(
                f"judgement must be an AuditJudgement member, got {judgement!r}; "
                "the set is closed and FAITHFUL is never implicit [F-A1]"
            )
        if not isinstance(auditor, str) or not auditor.strip():
            raise AuditRecordError("an audit judgement requires an auditor")
        with self._lock:
            matches = [
                i
                for i, r in enumerate(self._records)
                if r.fact_object_id == fact_object_id
                and r.policy_version == policy_version
            ]
            if not matches:
                raise NoPendingSelectionError(
                    f"no selection exists for fact {fact_object_id} under "
                    f"policy version {policy_version}"
                )
            pending = [i for i in matches if self._records[i].is_pending]
            if not pending:
                raise AlreadyJudgedError(
                    f"the audit of fact {fact_object_id} under policy version "
                    f"{policy_version} was already judged; judgements are "
                    "immutable [F-A1]"
                )
            record = self._records[pending[0]]
            completed = replace(
                record,
                judgement=judgement,
                judged_at=judged_at if judged_at is not None else _utc_now(),
                auditor=auditor,
            )
            # The single sanctioned mutation of register state: a
            # pending slot completes in place with a NEW frozen record.
            # No other record is touched; nothing is ever removed.
            self._records[pending[0]] = completed
            return completed

    # -- failure recording [N-10] ------------------------------------------

    def record_failure(self, failure: SelectionFailure) -> None:
        """Record an operational sampling failure. Never a gate."""
        if not isinstance(failure, SelectionFailure):
            raise AuditError(f"expected SelectionFailure, got {failure!r}")
        with self._lock:
            self._failures.append(failure)

    # -- read surface -------------------------------------------------------

    def __iter__(self):
        return iter(self.snapshot())

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def snapshot(self) -> tuple[AuditRecord, ...]:
        """Point-in-time tuple of all records (selections, judged or
        pending). Iteration and introspection never alias register
        state."""
        with self._lock:
            return tuple(self._records)

    def for_fact(self, fact_object_id: str) -> tuple[AuditRecord, ...]:
        """Every selection of one Fact, across policy versions."""
        with self._lock:
            return tuple(
                r for r in self._records if r.fact_object_id == fact_object_id
            )

    def pending(self) -> tuple[AuditRecord, ...]:
        """The awaiting-judgement selections, in selection order."""
        with self._lock:
            return tuple(r for r in self._records if r.is_pending)

    def selection_failures(self) -> tuple[SelectionFailure, ...]:
        """Operational sampling failures. [N-10]"""
        with self._lock:
            return tuple(self._failures)


# ---------------------------------------------------------------------------
# The judgement provider contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditContext:
    """Everything an auditor needs to judge one sampled unit. [F-A1]

    Built by composition at judgement time (never at acceptance): the
    retained Fact with its claim and qualifying context, the selecting
    EvidenceAttachment's reference and positional anchor, the Evidence
    object (with its full content and provenance) if still present, the
    exact anchored source span when a span resolver was wired, and the
    stratum plus policy version responsible for the selection.

    ``span`` is None when no resolver was injected: honest absence, not
    a fabricated excerpt. The Evidence content remains available, so
    the auditor can always read the source in full.
    """

    fact: Fact
    evidence: Evidence | None
    evidence_ref: str
    positional_anchor: str
    span: str | None
    source_type: SourceType
    confidence_band: ConfidenceBand
    policy_version: int


class JudgementProvider(Protocol):
    """The external auditor contract. [F-A1, M-67]

    Composition supplies the implementation -- a human auditor flow in
    production, a fixture in tests. This module deliberately supplies
    NO implementation: no LLM, no NLP, no heuristic, no network. The
    platform calls it only in the audit flow, never at acceptance, and
    never lets its answer gate or mutate anything.
    """

    # Same-line ellipsis: the stub body is the interface declaration,
    # not logic. A Protocol cannot be instantiated (typing enforces
    # it), so the stub body is structurally unreachable and excluded
    # from coverage like any interface declaration.
    def judge(self, context: AuditContext) -> AuditJudgement: ...  # pragma: no cover


#: Resolves (evidence_ref, locator) to the exact source span text, or
#: None when unresolvable. Composition wires the real chain (the
#: ``oip.anchoring.evidence_span_provider`` resolution over the store's
#: Evidence content); this module must not import it, so the Layer-2
#: import surface stays at the four ratified modules.
SpanResolver = Callable[[str, str], "str | None"]


# ---------------------------------------------------------------------------
# Composition: installation and the judgement flow
# ---------------------------------------------------------------------------


def install_sampled_audit(
    store,
    policy: SamplingPolicy = POLICY_V1,
    *,
    on_error: Callable[[Fact, BaseException], None] | None = None,
) -> AuditRegister:
    """Install Layer-2 sampled fidelity audit on a Store. [F-A1, N-8]

    Mirrors ``oip.anchoring.install_anchor_verification``: composition,
    not policy. The default store stays unwired [I-1]; calling this
    installs a sampler on ``store.audit_sampler`` that runs AFTER a
    Fact is committed (never before, never as a gate) and returns the
    AuditRegister the sampler appends to.

    Sampler contract, exactly as ratified:

    * EVERY attachment of the Fact is considered -- never
      first-attachment [F-A1]. Each attachment whose Evidence is still
      present contributes one stratum key (SourceType of its Evidence,
      ConfidenceBand of its extraction confidence). An attachment
      whose Evidence is missing contributes no stratum (not eligible
      for this sample). A source type that fails classification is NOT
      skipped: sampling fails closed for the whole Fact and is
      recorded as an N-10 operational failure (SelectionFailure),
      with no selection made.
    * The Fact is selected if ANY of its strata selects under
      ``selects``. Strata are evaluated in sorted-key order and the
      first selecting stratum wins, so the outcome is deterministic
      and independent of attachment order.
    * The pending AuditRecord carries the first attachment (in Fact
      attachment order) of the selecting stratum, with that
      attachment's evidence_ref and positional_anchor -- the exact
      source context for the auditor.
    * One audit per Fact per policy version: a DuplicateSelectionError
      is swallowed deliberately -- the Fact is already under audit for
      this policy version, which satisfies dedup; it is not a failure.
    * The sampler NEVER raises into the Store's write path: audit is
      non-gating [F-A1]. Operational failures are recorded on the
      register (``selection_failures``, [N-10]) and passed to the
      optional ``on_error`` callback for routing into whatever failure
      surface the composition site keeps. ``on_error`` itself is
      guarded: its failure is recorded, never propagated.
    """
    if not isinstance(policy, SamplingPolicy):
        raise SamplingPolicyError(f"policy must be a SamplingPolicy, got {policy!r}")

    register = AuditRegister()

    def sampler(fact: Fact) -> None:
        try:
            _select_for_fact(store, register, policy, fact)
        except DuplicateSelectionError:
            # Dedup satisfied, not a failure. [F-A1]
            return
        except Exception as exc:  # noqa: BLE001 -- N-10: contained, recorded
            _record_sampling_failure(register, policy, fact, exc)
            if on_error is not None:
                try:
                    on_error(fact, exc)
                except Exception as cb_exc:  # noqa: BLE001
                    _record_sampling_failure(register, policy, fact, cb_exc)

    store.audit_sampler = sampler
    return register


def _select_for_fact(
    store,
    register: AuditRegister,
    policy: SamplingPolicy,
    fact: Fact,
) -> None:
    """Stratify every attachment and select at most one audit unit.

    Raises DuplicateSelectionError for an already-audited Fact (the
    caller treats that as dedup, not failure); any other exception is
    an operational sampling failure for the caller to record. [N-10]
    """
    if not isinstance(fact, Fact):
        raise AuditError(f"sampler expected a Fact, got {type(fact).__name__}")

    # F-A1: every attachment considered, never first-attachment.
    strata: dict[tuple[SourceType, ConfidenceBand], list] = {}
    for attachment in fact.attachments:
        evidence = store.get_evidence(attachment.evidence_ref)
        if evidence is None:
            continue  # no resolvable Evidence: not eligible [F-A1]
        source_type = classify(evidence.provenance.source_type)
        band = ConfidenceBand.for_value(attachment.extraction_confidence)
        strata.setdefault((source_type, band), []).append(attachment)

    # Sorted-key evaluation: deterministic, order-independent outcome.
    for source_type, band in sorted(strata, key=lambda key: (key[0].value, key[1].value)):
        if not selects(fact.attributes.object_id, source_type, band, policy):
            continue
        # Within the selecting stratum the retained context is the
        # first contributing attachment in the Fact's frozen
        # attachment order -- deterministic, part of the Fact's
        # recorded identity (spec section 8.3/8.6; the F-A1 R5
        # tie-break governs selection AMONG strata).
        attachment = strata[(source_type, band)][0]
        register.select(
            AuditRecord(
                fact_object_id=fact.attributes.object_id,
                evidence_ref=attachment.evidence_ref,
                positional_anchor=attachment.positional_anchor,
                source_type=source_type,
                confidence_band=band,
                policy_version=policy.version,
                selected_at=_utc_now(),
            )
        )
        return  # one audit unit per Fact per policy version


def _record_sampling_failure(
    register: AuditRegister,
    policy: SamplingPolicy,
    fact: object,
    exc: BaseException,
) -> None:
    """Record a sampling failure. [N-10]

    Cannot itself raise for a well-formed register: a valid
    SelectionFailure is append-only bookkeeping. If the register were
    ever broken, the Store's hook guard still contains the escape.
    """
    fact_id = (
        fact.attributes.object_id
        if isinstance(fact, Fact) and fact.attributes is not None
        else "<unknown>"
    )
    register.record_failure(
        SelectionFailure(
            fact_object_id=fact_id,
            policy_version=policy.version,
            detail=f"sampling failed: {exc!r}",
            occurred_at=_utc_now(),
        )
    )


def judge_pending(
    store,
    register: AuditRegister,
    provider: JudgementProvider,
    *,
    span_provider: SpanResolver | None = None,
    auditor: str,
    clock: Callable[[], datetime] | None = None,
) -> int:
    """Drive every pending selection through the external provider.

    This is the audit flow, composition-side: it is NEVER called from
    the acceptance path. For each pending record the platform builds
    the full ``AuditContext`` -- retained Fact, Evidence, exact span
    (when a resolver is wired) -- asks the provider, and completes the
    record exactly once with the explicit judgement, the auditor
    identity, and a timestamp (injected clock for reproducibility).

    Provider contract breaches (a judgement outside the closed set)
    are raised as AuditRecordError rather than coerced: FAITHFUL is
    never implicit. Returns the number of judgements recorded.
    """
    if not isinstance(auditor, str) or not auditor.strip():
        raise AuditError("judge_pending requires an auditor identity")
    judged = 0
    for record in register.pending():
        fact = store.get_fact(record.fact_object_id)
        if fact is None:
            raise AuditError(
                f"fact {record.fact_object_id} selected for audit is no "
                "longer present in the store"
            )
        evidence = store.get_evidence(record.evidence_ref)
        span = (
            span_provider(record.evidence_ref, record.positional_anchor)
            if span_provider is not None
            else None
        )
        context = AuditContext(
            fact=fact,
            evidence=evidence,
            evidence_ref=record.evidence_ref,
            positional_anchor=record.positional_anchor,
            span=span,
            source_type=record.source_type,
            confidence_band=record.confidence_band,
            policy_version=record.policy_version,
        )
        judgement = provider.judge(context)
        if not isinstance(judgement, AuditJudgement):
            raise AuditRecordError(
                f"provider returned {judgement!r}; the judgement set is "
                "closed and FAITHFUL is never implicit [F-A1]"
            )
        register.record_judgement(
            record.fact_object_id,
            record.policy_version,
            judgement,
            auditor=auditor,
            judged_at=clock() if clock is not None else None,
        )
        judged += 1
    return judged


# ---------------------------------------------------------------------------
# Layer 3 -- published quality metrics [T03.2.3, F-A2]
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QualityMetricSnapshot:
    """A published platform quality-metric snapshot. [F-A2, S-5 Layer 3]

    S-5 Layer 3 publishes two platform quality metrics over the audit
    register: the HALLUCINATION RATE (proportion of audited Facts
    judged UNSUPPORTED) and the DRIFT RATE (proportion judged DRIFTED).
    F-A2 fixes their mechanics:

    * The denominator is JUDGED records only -- ``judged == faithful +
      drifted + unsupported`` (the closed F-A1 R7 set). Pending
      selections and N-10 SelectionFailures never enter the rates;
      their counts are published as CONTEXT so consumers can weigh the
      rates honestly. [F-A2 OD-1]
    * When ``judged == 0`` both rates are None -- "no judged audit
      observations" is NEVER reported as 0.0. [F-A2 OD-2]
    * ``policy_version`` is the scope: None = global (the disjoint
      union over all policy versions); an integer = that policy
      version's scope. A Fact audited again under a newer policy is a
      new audit; nothing is collapsed. [F-A2 OD-3]
    * The configured sampling rate never enters the metric: the 5
      percent is a per-draw selection constant (union probability
      1-(1-r)**k over k eligible strata), not an estimator,
      denominator or correction factor.

    Descriptive measurement only: no estimator, threshold, or
    statistical claim exists on this surface. [F-A2 OD-5]
    """

    policy_version: int | None
    judged: int
    faithful: int
    drifted: int
    unsupported: int
    pending: int
    selection_failures: int
    hallucination_rate: float | None
    drift_rate: float | None

    def __post_init__(self) -> None:
        for name in (
            "judged",
            "faithful",
            "drifted",
            "unsupported",
            "pending",
            "selection_failures",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise AuditError(
                    f"{name} must be a non-negative integer [F-A2]"
                )
        if self.policy_version is not None and (
            isinstance(self.policy_version, bool)
            or not isinstance(self.policy_version, int)
            or self.policy_version < 1
        ):
            raise AuditError(
                "policy_version must be None (global scope) or an "
                "integer >= 1 [F-A2 OD-3]"
            )
        if self.faithful + self.drifted + self.unsupported != self.judged:
            raise AuditError(
                "judged must equal faithful + drifted + unsupported "
                "(the closed three-value judgement set) [F-A2 OD-1]"
            )
        for name in ("hallucination_rate", "drift_rate"):
            rate = getattr(self, name)
            if self.judged == 0:
                if rate is not None:
                    raise AuditError(
                        f"{name} must be None when judged == 0: 'no "
                        "judged audit observations' is never 0.0 "
                        "[F-A2 OD-2]"
                    )
            elif (
                isinstance(rate, bool)
                or not isinstance(rate, (int, float))
                or not 0.0 <= rate <= 1.0
            ):
                raise AuditError(
                    f"{name} must be a number in [0.0, 1.0] when "
                    "judged > 0 [F-A2]"
                )


@dataclass(frozen=True)
class MetricTrendPoint:
    """One UTC calendar day's metric observation. [F-A2 OD-5]

    Trend buckets are derived ONLY from actual judgement records, on
    the ``judged_at`` time basis: a result exists exactly when its
    judgement exists. Days with no judged records produce NO bucket
    (absence is the honest representation -- no 0 percent is
    manufactured), and a bucket's context counts are therefore always
    zero: pending selections have no ``judged_at``, and N-10
    SelectionFailures are operational records, not judgement records.
    """

    utc_date: date
    snapshot: QualityMetricSnapshot


def _metric_scope_or_error(policy_version: int | None) -> None:
    """Fail-closed metric-scope validation. [F-A2 OD-3]"""
    if policy_version is None:
        return
    if (
        isinstance(policy_version, bool)
        or not isinstance(policy_version, int)
        or policy_version < 1
    ):
        raise AuditError(
            "metric scope must be None (global) or a policy version "
            "integer >= 1 [F-A2 OD-3]"
        )


def _metric_utc_date(judged_at: datetime) -> date:
    """The UTC calendar day of a judgement. [F-A2 OD-5, N-4]

    A naive ``judged_at`` is read as UTC -- a deterministic rule with
    no environment-dependent local-time conversion.
    """
    if judged_at.tzinfo is None:
        return judged_at.date()
    return judged_at.astimezone(timezone.utc).date()


def quality_metrics(
    register: AuditRegister, policy_version: int | None = None
) -> QualityMetricSnapshot:
    """The published quality-metric snapshot over an audit register.

    [F-A2 OD-1/OD-2/OD-3/OD-4; S-5 Layer 3; N-3 stage-2 proxy]

    Pure: derived only from the register's current contents, read
    under its lock; same state, same snapshot, always. Publication IS
    this queryable surface -- available to any consumer of platform
    output; no network, telemetry or dashboard exists or is implied.

    ``policy_version`` selects the scope: None = global (the disjoint
    union of all policy versions), an integer = that version's scope.
    An empty scope is a valid, honest answer: judged 0, rates None.
    """
    _metric_scope_or_error(policy_version)
    with register._lock:
        records = register.snapshot()
        failures = register.selection_failures()
    in_scope = [
        r
        for r in records
        if policy_version is None or r.policy_version == policy_version
    ]
    judged = [r for r in in_scope if r.judgement is not None]
    n_judged = len(judged)
    faithful = sum(1 for r in judged if r.judgement is AuditJudgement.FAITHFUL)
    drifted = sum(1 for r in judged if r.judgement is AuditJudgement.DRIFTED)
    unsupported = sum(
        1 for r in judged if r.judgement is AuditJudgement.UNSUPPORTED
    )
    n_pending = sum(1 for r in in_scope if r.is_pending)
    n_failures = sum(
        1
        for f in failures
        if policy_version is None or f.policy_version == policy_version
    )
    return QualityMetricSnapshot(
        policy_version=policy_version,
        judged=n_judged,
        faithful=faithful,
        drifted=drifted,
        unsupported=unsupported,
        pending=n_pending,
        selection_failures=n_failures,
        hallucination_rate=(unsupported / n_judged) if n_judged else None,
        drift_rate=(drifted / n_judged) if n_judged else None,
    )


def metric_trend(
    register: AuditRegister, policy_version: int | None = None
) -> tuple[MetricTrendPoint, ...]:
    """The sparse UTC-day trend series over judged audit records.

    [F-A2 OD-5]

    Deterministic, ascending by date, insertion-order independent, and
    derived only from actual judgement records on the ``judged_at``
    basis. No empty buckets are manufactured for days without judged
    records, and no rolling window, confidence interval, significance
    rule, predictive model or sampling correction exists here. The
    GLOBAL trend (``policy_version=None``) spans policy regimes; the
    per-version trends are the comparison-safe view across regime
    changes.
    """
    _metric_scope_or_error(policy_version)
    with register._lock:
        records = register.snapshot()
    buckets: dict[date, list[AuditRecord]] = {}
    for record in records:
        if record.judgement is None:
            continue
        if policy_version is not None and record.policy_version != policy_version:
            continue
        buckets.setdefault(_metric_utc_date(record.judged_at), []).append(
            record
        )
    points: list[MetricTrendPoint] = []
    for day in sorted(buckets):
        recs = buckets[day]
        n = len(recs)
        faithful = sum(
            1 for r in recs if r.judgement is AuditJudgement.FAITHFUL
        )
        drifted = sum(1 for r in recs if r.judgement is AuditJudgement.DRIFTED)
        unsupported = sum(
            1 for r in recs if r.judgement is AuditJudgement.UNSUPPORTED
        )
        points.append(
            MetricTrendPoint(
                utc_date=day,
                snapshot=QualityMetricSnapshot(
                    policy_version=policy_version,
                    judged=n,
                    faithful=faithful,
                    drifted=drifted,
                    unsupported=unsupported,
                    pending=0,
                    selection_failures=0,
                    hallucination_rate=unsupported / n,
                    drift_rate=drifted / n,
                ),
            )
        )
    return tuple(points)
