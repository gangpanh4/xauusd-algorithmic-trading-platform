"""
Backtesting report generation.
"""

from __future__ import annotations

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

    print("=" * 60)