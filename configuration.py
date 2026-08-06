"""Configuration and failure stores: infrastructure state, not intelligence.

Tasks: T01.1.6 (configuration), T01.1.7 (failure records)

Architecture References:
- N-7    Configuration store as a scoped Knowledge Store extension
- CI-1   Configuration is infrastructure state, NOT intelligence
- N-10   Failure records outside the object model
- N-4    Reproducible inputs: configuration must resolve at any historical point
- R-1    Immutable, versioned
- Art.V  Configuration never participates in reasoning or lineage

CI-1 is the binding invariant on which N-7 was approved:

    Configuration data is infrastructure state, not intelligence. It may be
    stored inside the Knowledge Store for operational reasons, but it must
    remain logically isolated from Intelligence Objects and must never
    participate in reasoning, scoring, pattern detection, or lineage.

Isolation is enforced at the access boundary, not by convention: this module
shares no type with the object model, returns no Intelligence Object, and
exposes no path by which a configuration record could enter a lineage graph.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Mapping

from oip.acceptance import FailureRecord
from oip.contract import utc_now
from oip.enums import Engine


class ConfigurationError(Exception):
    """Base class for configuration store violations."""


class ConfigurationNotFoundError(ConfigurationError):
    """No configuration resolves for that reference."""


class ConfigurationImmutableError(ConfigurationError):
    """An attempt to alter a recorded configuration. [R-1]"""


class IsolationViolationError(ConfigurationError):
    """An attempt to use configuration as intelligence. [CI-1]"""


@dataclass(frozen=True)
class ConfigurationRecord:
    """An immutable, versioned engine configuration. [N-7, R-1]

    Deliberately NOT an Intelligence Object: no lineage, no confidence, no
    explanation, no status. It is infrastructure state. [CI-1]
    """

    config_ref: str
    engine: Engine
    version: int
    settings: Mapping[str, Any]
    recorded_at: datetime
    supersedes: str | None = None

    def __post_init__(self) -> None:
        if not self.config_ref:
            raise ConfigurationError("config_ref is required")
        if not isinstance(self.engine, Engine):
            raise ConfigurationError("engine must be a known Engine")
        if self.version < 1:
            raise ConfigurationError("version starts at 1")
        object.__setattr__(self, "settings", dict(self.settings))

    # -- CI-1 isolation boundary -----------------------------------------

    @property
    def is_intelligence(self) -> bool:
        """Always False. Configuration is never intelligence. [CI-1]"""
        return False

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Configuration never enters the lineage graph. [CI-1]"""
        return False

    def as_lineage_reference(self):
        """Never permitted. [CI-1]"""
        raise IsolationViolationError(
            "configuration may not participate in lineage; it is "
            "infrastructure state, not intelligence [CI-1]"
        )

    def as_evidence(self):
        """Never permitted. [CI-1, AD-05, Article IV]"""
        raise IsolationViolationError(
            "configuration may not become Evidence [CI-1, AD-05]"
        )

    def confidence_contribution(self):
        """Never permitted. [CI-1]"""
        raise IsolationViolationError(
            "configuration may not contribute to confidence or scoring [CI-1]"
        )


@dataclass
class ConfigurationStore:
    """Immutable versioned configuration, resolvable at any point. [N-7, N-4]

    Colocated with the Knowledge Store for operational reasons but logically
    isolated: it holds no Intelligence Object and exposes no path into one.
    """

    _records: dict[str, ConfigurationRecord] = field(default_factory=dict, init=False)
    _by_engine: dict[Engine, list[str]] = field(default_factory=dict, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def record(
        self,
        engine: Engine,
        settings: Mapping[str, Any],
        config_ref: str | None = None,
        supersedes: str | None = None,
    ) -> ConfigurationRecord:
        """Record a new immutable configuration version. [R-1, N-7]"""
        with self._lock:
            history = self._by_engine.setdefault(engine, [])
            version = len(history) + 1
            ref = config_ref or f"cfg-{engine.value}-v{version}"
            if ref in self._records:
                raise ConfigurationImmutableError(
                    f"config_ref {ref!r} already recorded; configurations are "
                    f"immutable [R-1]"
                )
            entry = ConfigurationRecord(
                config_ref=ref,
                engine=engine,
                version=version,
                settings=settings,
                recorded_at=utc_now(),
                supersedes=supersedes or (history[-1] if history else None),
            )
            self._records[ref] = entry
            history.append(ref)
            return entry

    def resolve(self, config_ref: str) -> ConfigurationRecord:
        """Resolve engine_configuration_ref. Required by Principle 3. [N-4]"""
        with self._lock:
            entry = self._records.get(config_ref)
            if entry is None:
                raise ConfigurationNotFoundError(
                    f"configuration {config_ref!r} does not resolve [N-4]"
                )
            return entry

    def find(self, config_ref: str) -> ConfigurationRecord | None:
        with self._lock:
            return self._records.get(config_ref)

    def current_for(self, engine: Engine) -> ConfigurationRecord | None:
        with self._lock:
            history = self._by_engine.get(engine, [])
            return self._records[history[-1]] if history else None

    def history_for(self, engine: Engine) -> tuple[ConfigurationRecord, ...]:
        """Full ordered history, enabling learning reversal. [N-7, M-34]"""
        with self._lock:
            return tuple(self._records[r] for r in self._by_engine.get(engine, ()))

    def rollback(self, engine: Engine, to_ref: str) -> ConfigurationRecord:
        """Restore a prior configuration by recording it forward. [M-34]

        Rollback never edits history: it records the prior settings as a new
        version, so the fact that a rollback occurred remains visible.
        """
        with self._lock:
            target = self.resolve(to_ref)
            if target.engine is not engine:
                raise ConfigurationError(
                    f"configuration {to_ref!r} belongs to {target.engine.value}"
                )
            return self.record(engine, target.settings)

    def contains(self, config_ref: str) -> bool:
        with self._lock:
            return config_ref in self._records

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)

    def __iter__(self) -> Iterator[ConfigurationRecord]:
        with self._lock:
            return iter(tuple(self._records.values()))


@dataclass
class FailureStore:
    """Engine and acceptance failures, outside the object model. [N-10]

    Failures are operational facts, not knowledge. They never enter the
    lineage graph, so the platform can never derive a conclusion from its own
    malfunction. An empty result and a failed result stay distinguishable.
    """

    _records: list[FailureRecord] = field(default_factory=list, init=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False)

    def record(self, failure: FailureRecord) -> FailureRecord:
        with self._lock:
            self._records.append(failure)
            return failure

    def all(self) -> tuple[FailureRecord, ...]:
        with self._lock:
            return tuple(self._records)

    def for_object(self, object_id: str) -> tuple[FailureRecord, ...]:
        with self._lock:
            return tuple(r for r in self._records if r.object_id == object_id)

    def for_rule(self, rule_id: str) -> tuple[FailureRecord, ...]:
        with self._lock:
            return tuple(r for r in self._records if rule_id in r.rule_ids)

    # -- N-10 attribution queries  [T01.6.3] ------------------------------
    # "Orchestration reads failure records for scheduling and idempotence."
    # Reads only: this store records and reports, and holds no policy.

    def for_engine(self, engine: Engine) -> tuple[FailureRecord, ...]:
        """Failures attributable to one engine. [N-10, AD-04]"""
        if not isinstance(engine, Engine):
            raise ConfigurationError(
                f"expected a known Engine, got {engine!r}"
            )
        with self._lock:
            return tuple(r for r in self._records if r.engine is engine)

    def for_cycle(self, cycle_id: int) -> tuple[FailureRecord, ...]:
        """Failures arising in one orchestration cycle. [N-10, N-17]"""
        with self._lock:
            return tuple(r for r in self._records if r.cycle_id == cycle_id)

    def unattributed(self) -> tuple[FailureRecord, ...]:
        """Records missing one of N-10's six identifications.

        Surfaced, never suppressed: an attribution gap is itself a
        failure-surfacing defect and must stay visible. [N-10, T01.6.3]
        """
        with self._lock:
            return tuple(
                r for r in self._records if not r.satisfies_n10_attribution
            )

    @property
    def participates_in_lineage(self) -> bool:
        """Always False. Failures never enter lineage. [N-10]"""
        return False

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)
