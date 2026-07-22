"""
State management for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class LiveTradingState:
    """
    Runtime state of the Live Trading Engine.
    """

    running: bool = False

    processed_bars: int = 0

    executed_trades: int = 0

    skipped_trades: int = 0

    last_ticket: int | None = None

    last_error: str = ""

    last_processed_timestamp: datetime | None = None

    def reset(self) -> None:
        """
        Reset runtime statistics.
        """

        self.running = False

        self.processed_bars = 0

        self.executed_trades = 0

        self.skipped_trades = 0

        self.last_ticket = None

        self.last_error = ""

        self.last_processed_timestamp = None