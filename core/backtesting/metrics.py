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


def calculate_average_profit(
    result: BacktestResult,
) -> float:
    """
    Calculate average profit per trade.
    """

    if not result.trades:
        return 0.0

    return (
        calculate_net_profit(result)
        / len(result.trades)
    )


def calculate_largest_win(
    result: BacktestResult,
) -> float:
    """
    Return the largest winning trade.
    """

    wins = [
        trade.profit_loss
        for trade in result.trades
        if trade.profit_loss > 0.0
    ]

    if not wins:
        return 0.0

    return max(wins)


def calculate_largest_loss(
    result: BacktestResult,
) -> float:
    """
    Return the largest losing trade.
    """

    losses = [
        trade.profit_loss
        for trade in result.trades
        if trade.profit_loss < 0.0
    ]

    if not losses:
        return 0.0

    return min(losses)