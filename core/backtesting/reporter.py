"""
Backtesting report generation.
"""

from __future__ import annotations

from .metrics import (
    calculate_average_profit,
    calculate_largest_loss,
    calculate_largest_win,
)
from .models import BacktestResult


def print_report(
    result: BacktestResult,
) -> None:
    """
    Print a human-readable backtest summary.
    """

    print()
    print("=" * 60)
    print("BACKTEST REPORT")
    print("=" * 60)

    print(f"Total Trades     : {result.total_trades}")
    print(f"Wins             : {result.winning_trades}")
    print(f"Losses           : {result.losing_trades}")
    print(f"Breakeven        : {result.breakeven_trades}")

    print()

    print(f"Win Rate         : {result.win_rate:.2%}")
    print(f"Net Profit       : {result.net_profit:.2f}")
    print(f"Max Drawdown     : {result.max_drawdown:.2f}")

    print(
        f"Average Trade    : "
        f"{calculate_average_profit(result):.2f}"
    )

    print(
        f"Largest Win      : "
        f"{calculate_largest_win(result):.2f}"
    )

    print(
        f"Largest Loss     : "
        f"{calculate_largest_loss(result):.2f}"
    )

    print("=" * 60)