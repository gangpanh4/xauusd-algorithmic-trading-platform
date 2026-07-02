"""
Backtesting report generation.
"""

from __future__ import annotations

from pathlib import Path

from .metrics import (
    calculate_average_loss,
    calculate_average_profit,
    calculate_average_win,
    calculate_expectancy,
    calculate_largest_loss,
    calculate_largest_win,
    calculate_profit_factor,
)
from .models import BacktestResult


def generate_report(
    result: BacktestResult,
) -> str:
    """
    Generate a formatted backtest report.
    """

    lines = [
        "",
        "=" * 70,
        "BACKTEST REPORT",
        "=" * 70,
        "",
        f"Total Trades     : {result.total_trades}",
        f"Wins             : {result.winning_trades}",
        f"Losses           : {result.losing_trades}",
        f"Breakeven        : {result.breakeven_trades}",
        "",
        f"Win Rate         : {result.win_rate:.2f}%",
        f"Net Profit       : {result.net_profit:.2f}",
        f"Gross Profit     : {result.gross_profit:.2f}",
        f"Gross Loss       : {result.gross_loss:.2f}",
        f"Profit Factor    : {calculate_profit_factor(result):.2f}",
        f"Max Drawdown     : {result.max_drawdown:.2f}",
        "",
        f"Average Trade    : {calculate_average_profit(result):.2f}",
        f"Average Win      : {calculate_average_win(result):.2f}",
        f"Average Loss     : {calculate_average_loss(result):.2f}",
        f"Expectancy       : {calculate_expectancy(result):.2f}",
        "",
        f"Largest Win      : {calculate_largest_win(result):.2f}",
        f"Largest Loss     : {calculate_largest_loss(result):.2f}",
        "",
        "=" * 70,
    ]

    return "\n".join(lines)


def print_report(
    result: BacktestResult,
) -> None:
    """
    Print report to the console.
    """

    print(generate_report(result))


def save_report(
    result: BacktestResult,
    output_file: str | Path,
) -> Path:
    """
    Save report to a text file.
    """

    output_file = Path(output_file)

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file.write_text(
        generate_report(result),
        encoding="utf-8",
    )

    return output_file