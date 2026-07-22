"""
Performance metric calculations for the Backtesting Engine.
"""

from __future__ import annotations

from .models import BacktestResult, TradeOutcome


def calculate_win_rate(
    winning_trades: int,
    total_trades: int,
) -> float:

    if total_trades == 0:
        return 0.0

    return winning_trades / total_trades * 100.0


def calculate_net_profit(
    result: BacktestResult,
) -> float:

    return sum(
        trade.net_profit
        for trade in result.trades
    )


def calculate_gross_profit(
    result: BacktestResult,
) -> float:

    return sum(
        max(trade.net_profit, 0.0)
        for trade in result.trades
    )


def calculate_gross_loss(
    result: BacktestResult,
) -> float:

    return abs(
        sum(
            min(trade.net_profit, 0.0)
            for trade in result.trades
        )
    )


def calculate_profit_factor(
    result: BacktestResult,
) -> float:

    gross_loss = calculate_gross_loss(result)

    if gross_loss == 0:
        return 0.0

    return (
        calculate_gross_profit(result)
        / gross_loss
    )


def count_trade_outcomes(
    result: BacktestResult,
) -> tuple[int, int, int]:

    wins = 0
    losses = 0
    breakeven = 0

    for trade in result.trades:

        if trade.outcome is TradeOutcome.WIN:
            wins += 1

        elif trade.outcome is TradeOutcome.LOSS:
            losses += 1

        else:
            breakeven += 1

    return wins, losses, breakeven


def calculate_average_profit(
    result: BacktestResult,
) -> float:

    if not result.trades:
        return 0.0

    return (
        calculate_net_profit(result)
        / len(result.trades)
    )


def calculate_average_win(
    result: BacktestResult,
) -> float:

    wins = [
        trade.net_profit
        for trade in result.trades
        if trade.net_profit > 0
    ]

    if not wins:
        return 0.0

    return sum(wins) / len(wins)


def calculate_average_loss(
    result: BacktestResult,
) -> float:

    losses = [
        abs(trade.net_profit)
        for trade in result.trades
        if trade.net_profit < 0
    ]

    if not losses:
        return 0.0

    return sum(losses) / len(losses)


def calculate_largest_win(
    result: BacktestResult,
) -> float:

    wins = [
        trade.net_profit
        for trade in result.trades
        if trade.net_profit > 0
    ]

    return max(wins, default=0.0)


def calculate_largest_loss(
    result: BacktestResult,
) -> float:

    losses = [
        trade.net_profit
        for trade in result.trades
        if trade.net_profit < 0
    ]

    return min(losses, default=0.0)


def calculate_expectancy(
    result: BacktestResult,
) -> float:

    if not result.trades:
        return 0.0

    return (
        calculate_net_profit(result)
        / len(result.trades)
    )


def calculate_consecutive_streaks(
    result: BacktestResult,
) -> tuple[int, int]:

    max_win = 0
    max_loss = 0

    current_win = 0
    current_loss = 0

    for trade in result.trades:

        if trade.outcome is TradeOutcome.WIN:

            current_win += 1
            current_loss = 0

        elif trade.outcome is TradeOutcome.LOSS:

            current_loss += 1
            current_win = 0

        else:

            current_win = 0
            current_loss = 0

        max_win = max(max_win, current_win)
        max_loss = max(max_loss, current_loss)

    return max_win, max_loss


def calculate_equity_curve(
    result: BacktestResult,
    initial_balance: float,
) -> list[float]:

    equity = initial_balance

    curve = [equity]

    for trade in result.trades:
        equity += trade.net_profit
        curve.append(equity)

    return curve