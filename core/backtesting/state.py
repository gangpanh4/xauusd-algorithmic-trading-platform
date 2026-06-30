"""
State management for the Backtesting Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    BacktestTrade,
)


@dataclass
class BacktestState:
    """
    Maintains the runtime state of a backtest.
    """

    initialized: bool = False

    running: bool = False

    completed: bool = False

    start_time: datetime | None = None

    end_time: datetime | None = None

    current_equity: float = 0.0

    peak_equity: float = 0.0

    max_drawdown: float = 0.0

    processed_bar_count: int = 0

    executed_trade_count: int = 0

    trades: list[BacktestTrade] = field(default_factory=list)

    def reset(self) -> None:
        """
        Reset the engine state.
        """

        self.initialized = False

        self.running = False

        self.completed = False

        self.start_time = None

        self.end_time = None

        self.current_equity = 0.0

        self.peak_equity = 0.0

        self.max_drawdown = 0.0

        self.processed_bar_count = 0

        self.executed_trade_count = 0

        self.trades.clear()
        