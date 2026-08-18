"""Mode-aware freshness contracts for Aurum snapshot evaluation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from core.multi_timeframe.enums import Timeframe

from .enums import AurumDataMode


@dataclass(frozen=True, slots=True)
class FreshnessContext:
    """Temporal facts supplied to an explicit freshness policy."""

    mode: AurumDataMode
    symbol: str
    generated_at_utc: datetime
    observation_time_utc: datetime
    decision_available_at_utc: datetime
    quote_available: bool
    quote_timestamp_utc: datetime | None
    bar_timestamps_by_timeframe: Mapping[Timeframe, Sequence[datetime]]


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    """Precomputed freshness/provenance verdict consumed by the builder."""

    policy_id: str | None
    valid: bool
    critical_failure: bool = False
    reason_code: str | None = None
    reason: str | None = None


class FreshnessPolicy(Protocol):
    """Interface for explicit freshness policy implementations."""

    def evaluate(self, context: FreshnessContext) -> FreshnessAssessment:
        """Evaluate freshness without mutating analytical state."""
        ...
