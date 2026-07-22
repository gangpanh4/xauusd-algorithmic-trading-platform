"""
Standalone Backtesting Runner.

Usage:

python run_backtest.py
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.backtesting.config import BacktestConfig
from core.backtesting.runner import BacktestRunner


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

        result = runner.run(
            symbol="XAUUSD",
            timeframe=mt5.TIMEFRAME_M15,
            bars=500,
        )

        runner.generate_reports(result)

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