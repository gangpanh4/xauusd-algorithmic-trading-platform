"""
State management for the Risk Management module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import TradePlan


@dataclass
class RiskManagerState:
    """
    Maintains the runtime state of the Risk Manager.
    """

    # Initialization
    initialized: bool = False

    # Last processed trade
    last_trade_plan: TradePlan | None = None
    last_decision_time: datetime | None = None

    # Statistics
    processed_signal_count: int = 0
    approved_trade_count: int = 0
    rejected_trade_count: int = 0
    skipped_trade_count: int = 0

    # Virtual account
    virtual_balance: float = 0.0
    peak_balance: float = 0.0
    starting_balance: float = 0.0

    # Daily statistics
    daily_profit: float = 0.0
    daily_loss: float = 0.0

    # Trade statistics
    total_profit: float = 0.0
    total_loss: float = 0.0

    consecutive_wins: int = 0
    consecutive_losses: int = 0

    largest_win: float = 0.0
    largest_loss: float = 0.0

    # Drawdown
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0

    # Safety
    emergency_stop: bool = False
    daily_loss_limit_hit: bool = False

    # Metadata
    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    def reset(self) -> None:
        """
        Reset runtime state while preserving configuration.
        """

        self.initialized = False

        self.last_trade_plan = None
        self.last_decision_time = None

        self.processed_signal_count = 0
        self.approved_trade_count = 0
        self.rejected_trade_count = 0
        self.skipped_trade_count = 0

        self.virtual_balance = self.starting_balance
        self.peak_balance = self.starting_balance

        self.daily_profit = 0.0
        self.daily_loss = 0.0

        self.total_profit = 0.0
        self.total_loss = 0.0

        self.consecutive_wins = 0
        self.consecutive_losses = 0

        self.largest_win = 0.0
        self.largest_loss = 0.0

        self.current_drawdown = 0.0
        self.max_drawdown = 0.0

        self.emergency_stop = False
        self.daily_loss_limit_hit = False

    def register_trade(self, pnl: float) -> None:
        """
        Update state after a completed trade.
        """

        self.virtual_balance += pnl

        if self.virtual_balance > self.peak_balance:
            self.peak_balance = self.virtual_balance

        self.current_drawdown = (
            self.peak_balance - self.virtual_balance
        )

        self.max_drawdown = max(
            self.max_drawdown,
            self.current_drawdown,
        )

        if pnl > 0:

            self.total_profit += pnl
            self.daily_profit += pnl

            self.consecutive_wins += 1
            self.consecutive_losses = 0

            self.largest_win = max(
                self.largest_win,
                pnl,
            )

        elif pnl < 0:

            loss = abs(pnl)

            self.total_loss += loss
            self.daily_loss += loss

            self.consecutive_losses += 1
            self.consecutive_wins = 0

            self.largest_loss = max(
                self.largest_loss,
                loss,
            )