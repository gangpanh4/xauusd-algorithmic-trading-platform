"""
State management for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    shadow_observations_recorded: int = 0
    last_ticket: int | None = None
    active_order_count: int = 0
    last_error: str = ""
    last_processed_timestamp: datetime | None = None
    last_deal_reconciliation_time: datetime | None = None
    processed_deal_tickets: set[int] = field(default_factory=set)

    unresolved_partial_ticket: int | None = None
    unresolved_requested_volume: float = 0.0
    unresolved_executed_volume: float = 0.0
    unresolved_remaining_volume: float = 0.0
    unresolved_partial_created_at: datetime | None = None
    last_partial_fill_resolution: str = ""

    def reset(self) -> None:
        """Reset runtime statistics."""

        self.running = False
        self.processed_bars = 0
        self.executed_trades = 0
        self.skipped_trades = 0
        self.shadow_observations_recorded = 0
        self.last_ticket = None
        self.active_order_count = 0
        self.last_error = ""
        self.last_processed_timestamp = None
        self.last_deal_reconciliation_time = None
        self.processed_deal_tickets.clear()
        self.unresolved_partial_ticket = None
        self.unresolved_requested_volume = 0.0
        self.unresolved_executed_volume = 0.0
        self.unresolved_remaining_volume = 0.0
        self.unresolved_partial_created_at = None
        self.last_partial_fill_resolution = ""
