"""
Performance metric calculations for the Backtesting Engine.
"""

from __future__ import annotations

from .models import (
    BacktestResult,
    TradeOutcome,
)


def calculate_win_rate(
    winning_trades: int,
    total_trades: int,
) -> float:
    """
    Calculate the win rate.
    """

    if total_trades == 0:
        return 0.0

    return winning_trades / total_trades


def calculate_net_profit(
    result: BacktestResult,
) -> float:
    """
    Calculate total net profit.
    """

    return sum(
        trade.profit_loss
        for trade in result.trades
    )


def count_trade_outcomes(
    result: BacktestResult,
) -> tuple[int, int, int]:
    """
    Count wins, losses and breakeven trades.
    """

    wins = 0
    losses = 0
    breakeven = 0

    for trade in result.trades:

        if trade.outcome == TradeOutcome.WIN:
            wins += 1

        elif trade.outcome == TradeOutcome.LOSS:
            losses += 1

        else:
            breakeven += 1

    return (
        wins,
        losses,
        breakeven,
    )
