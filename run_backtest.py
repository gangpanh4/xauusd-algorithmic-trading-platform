"""
Standalone Backtesting Runner.

Usage:

python run_backtest.py
"""

from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5

from core.backtesting.config import BacktestConfig
from core.backtesting.runner import BacktestRunner


HISTORICAL_BARS = 20_000
HISTORICAL_END_TIME = datetime(
    2026,
    4,
    9,
    23,
    59,
    tzinfo=UTC,
)


def main() -> None:

    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    try:

        config = BacktestConfig()

        runner = BacktestRunner(config)

        print("=" * 70)
        print("XAUUSD HISTORICAL BACKTEST")
        print("=" * 70)
        print(f"Bars requested  : {HISTORICAL_BARS:,}")
        print(
            "Window end UTC  : "
            f"{HISTORICAL_END_TIME.isoformat()}"
        )

        output = runner.run_with_strategy_comparison(
            symbol="XAUUSD",
            timeframe=mt5.TIMEFRAME_M15,
            bars=HISTORICAL_BARS,
            end_time=HISTORICAL_END_TIME,
        )

        runner.generate_composite_reports(output)

        result = output.result

        print()
        print("=" * 70)
        print("BACKTEST COMPLETE")
        print("=" * 70)
        print(f"Trades          : {result.total_trades}")
        print(f"Win Rate        : {result.win_rate:.2f}%")
        print(f"Net Profit      : {result.net_profit:.2f}")
        print(f"Profit Factor   : {result.profit_factor:.2f}")
        print(f"Max Drawdown    : {result.max_drawdown:.2f}")
        print()
        print("Reports exported to:")
        print("output/backtests/")

    finally:

        mt5.shutdown()


if __name__ == "__main__":
    main()
