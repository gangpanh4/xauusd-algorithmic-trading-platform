from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class TradeOutcome(Enum):
    WIN = "WIN"
    LOSS = "LOSS"
    BREAKEVEN = "BREAKEVEN"


@dataclass(frozen=True)
class BacktestTrade:

    entry_time: datetime

    exit_time: datetime

    direction: str

    entry_price: float

    exit_price: float

    position_size: float

    profit_loss: float

    outcome: TradeOutcome


@dataclass(frozen=True)
class BacktestResult:

    total_trades: int

    winning_trades: int

    losing_trades: int

    breakeven_trades: int

    net_profit: float

    win_rate: float

    max_drawdown: float

    trades: list[BacktestTrade] = field(default_factory=list)