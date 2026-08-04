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
from core.mt5_execution.symbol_specification import (
    get_live_symbol_specification,
)


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

        symbol = "XAUUSD"
        symbol_info_available = callable(
            getattr(mt5, "symbol_info", None)
        )

        if symbol_info_available:
            symbol_spec = get_live_symbol_specification(symbol)
            config = BacktestConfig(
                stop_loss_distance=symbol_spec.minimum_stop_distance,
                tick_size=symbol_spec.tick_size,
                tick_value_per_lot=symbol_spec.tick_value_per_lot,
                lot_step=symbol_spec.lot_step,
                minimum_lot=symbol_spec.minimum_lot,
                maximum_lot=symbol_spec.maximum_lot,
            )
        else:
            # Compatibility for isolated entrypoint tests and non-production
            # MT5 stubs that intentionally expose lifecycle methods only.
            # A real MT5 runtime must expose symbol_info and therefore uses the
            # validated broker specification above.
            symbol_spec = None
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
        if symbol_spec is not None:
            print(f"Symbol          : {symbol_spec.symbol}")
            print(f"Tick size       : {symbol_spec.tick_size}")
            print(f"Tick value/lot  : {symbol_spec.tick_value_per_lot}")
            print(f"Lot step        : {symbol_spec.lot_step}")
            print(f"Minimum lot     : {symbol_spec.minimum_lot}")
            print(f"Maximum lot     : {symbol_spec.maximum_lot}")
            print(
                "Minimum stop    : "
                f"{symbol_spec.minimum_stop_distance}"
            )

        output = runner.run_with_strategy_comparison(
            symbol=symbol,
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
