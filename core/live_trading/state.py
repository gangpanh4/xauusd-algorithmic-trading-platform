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
    shadow_session_id: str = ""
    shadow_session_started_at: datetime | None = None
    last_ticket: int | None = None
    open_position_count: int = 0
    active_order_count: int = 0
    positions_synchronized: bool = False
    active_orders_synchronized: bool = False
    realized_deals_synchronized: bool = False
    symbol_specification_loaded: bool = False
    clock_normalization_validated: bool = False
    parity_validation_passed: bool = False
    order_submissions_this_session: int = 0
    consecutive_execution_failures: int = 0
    last_error: str = ""
    execution_intent_reconciliation_status: str = ""
    execution_intent_reconciliation_reason: str = ""
    execution_intent_reconciliation_ticket: int | None = None
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
        self.shadow_session_id = ""
        self.shadow_session_started_at = None
        self.last_ticket = None
        self.open_position_count = 0
        self.active_order_count = 0
        self.positions_synchronized = False
        self.active_orders_synchronized = False
        self.realized_deals_synchronized = False
        self.symbol_specification_loaded = False
        self.clock_normalization_validated = False
        self.parity_validation_passed = False
        self.order_submissions_this_session = 0
        self.consecutive_execution_failures = 0
        self.last_error = ""
        self.execution_intent_reconciliation_status = ""
        self.execution_intent_reconciliation_reason = ""
        self.execution_intent_reconciliation_ticket = None
        self.last_processed_timestamp = None
        self.last_deal_reconciliation_time = None
        self.processed_deal_tickets.clear()
        self.unresolved_partial_ticket = None
        self.unresolved_requested_volume = 0.0
        self.unresolved_executed_volume = 0.0
        self.unresolved_remaining_volume = 0.0
        self.unresolved_partial_created_at = None
        self.last_partial_fill_resolution = ""
