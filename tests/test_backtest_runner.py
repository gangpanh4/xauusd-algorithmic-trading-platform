"""
Test the Backtest Runner.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.backtesting.config import (
    BacktestConfig,
)

from core.backtesting.runner import (
    BacktestRunner,
)


def main() -> None:
    """
    Test the Backtest Runner.
    """

    if not mt5.initialize():
        raise RuntimeError(
            f"MT5 initialization failed: {mt5.last_error()}"
        )

    runner = BacktestRunner(
        BacktestConfig(),
    )

    runner.run(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M5,
        bars=100,
    )

    print()
    print("=" * 60)
    print("BACKTEST RUNNER")
    print("=" * 60)
    print(
        f"Processed Bars : "
        f"{runner.state.processed_bar_count}"
    )
    print("=" * 60)
    print()

    mt5.shutdown()


if __name__ == "__main__":
    main()