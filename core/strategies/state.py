"""Mutable lifecycle state for the observational strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from .context import StrategyObservation
from .models import TradingSetup


@dataclass(slots=True)
class XAUUSDBOSCHOCHState:
    """State owned exclusively by the strategy engine."""

    active_setup: TradingSetup | None = None
    consumed_setup_ids: set[UUID] = field(default_factory=set)
    latest_observation: StrategyObservation | None = None
    observations: list[StrategyObservation] = field(default_factory=list)
    processed_observations: int = 0

    def reset(self) -> None:
        self.active_setup = None
        self.consumed_setup_ids.clear()
        self.latest_observation = None
        self.observations.clear()
        self.processed_observations = 0


    def observation_summary(self) -> dict[str, int]:
        """Return deterministic counts grouped by observation reason code."""

        summary: dict[str, int] = {}
        for observation in self.observations:
            summary[observation.reason_code] = (
                summary.get(observation.reason_code, 0) + 1
            )
        return dict(sorted(summary.items()))
