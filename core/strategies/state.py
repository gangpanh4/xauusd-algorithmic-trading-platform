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
    processed_observations: int = 0

    def reset(self) -> None:
        self.active_setup = None
        self.consumed_setup_ids.clear()
        self.latest_observation = None
        self.processed_observations = 0
