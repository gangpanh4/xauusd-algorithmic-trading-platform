"""
State management for the Risk Management module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC

from .models import (
    TradePlan,
)


@dataclass
class RiskManagerState:
    """
    Maintains the internal state of the Risk Manager.
    """

    initialized: bool = False

    last_trade_plan: TradePlan | None = None

    last_decision_time: datetime | None = None

    approved_trade_count: int = 0

    rejected_trade_count: int = 0

    processed_signal_count: int = 0

    def reset(self) -> None:
        """
        Reset the Risk Manager state.
        """

        self.initialized = False

        self.last_trade_plan = None

        self.last_decision_time = None

        self.approved_trade_count = 0

        self.rejected_trade_count = 0

        self.processed_signal_count = 0