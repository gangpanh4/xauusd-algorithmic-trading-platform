"""Mode-aware freshness contracts without hard-coded policy thresholds."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .enums import AurumDataMode


@dataclass(frozen=True, slots=True)
class FreshnessContext:
    """Facts supplied to an external freshness policy."""

    mode: AurumDataMode
    symbol: str
    generated_at_utc: datetime
    observation_time_utc: datetime
    quote_available: bool


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    """Precomputed freshness/provenance verdict consumed by the builder."""

    policy_id: str | None
    valid: bool
    critical_failure: bool = False
    reason_code: str | None = None
    reason: str | None = None


class FreshnessPolicy(Protocol):
    """Interface for future explicit freshness policy implementations."""

    def evaluate(self, context: FreshnessContext) -> FreshnessAssessment:
        """Evaluate freshness without mutating analytical state."""
        ...
