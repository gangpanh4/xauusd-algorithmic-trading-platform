from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class TradeOutcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


class ExitReason(Enum):
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_LOSS = "STOP_LOSS"
    END_OF_DATA = "END_OF_DATA"
    MANUAL = "MANUAL"


@dataclass(frozen=True)
class BacktestTrade:
    # Trade information
    entry_time: datetime
    exit_time: datetime

    direction: str

    # Prices
    entry_price: float
    exit_price: float

    # Position
    position_size: float

    # Costs
    spread_cost: float = 0.0
    commission: float = 0.0

    # Profit
    gross_profit: float = 0.0
    net_profit: float = 0.0

    # Statistics
    outcome: TradeOutcome = TradeOutcome.BREAKEVEN
    exit_reason: ExitReason = ExitReason.END_OF_DATA

    holding_bars: int = 0

    holding_time: timedelta = timedelta(0)

    risk_reward: float = 0.0

    # -------------------------------------------------
    # Trade Lifecycle Analytics (Sprint 2)
    # -------------------------------------------------

    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0

    highest_price: float = 0.0
    lowest_price: float = 0.0

    breakeven_triggered: bool = False
    trailing_stop_triggered: bool = False

    partial_exit_taken: bool = False

    lifecycle_events: tuple[str, ...] = ()

    metadata: dict = field(default_factory=dict)

    @property
    def profit_loss(self) -> float:
        """
        Backward compatibility with the existing project.
        """
        return self.net_profit


@dataclass(frozen=True)
class BacktestResult:

    total_trades: int

    winning_trades: int

    losing_trades: int

    breakeven_trades: int

    net_profit: float

    win_rate: float

    max_drawdown: float

    gross_profit: float = 0.0

    gross_loss: float = 0.0

    profit_factor: float = 0.0

    expectancy: float = 0.0

    average_win: float = 0.0

    average_loss: float = 0.0

    largest_win: float = 0.0

    largest_loss: float = 0.0

    consecutive_wins: int = 0

    consecutive_losses: int = 0

    trades: list[BacktestTrade] = field(default_factory=list)