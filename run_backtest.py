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
from core.execution_economics.profiles import (
    pinned_xauusd_research_profile,
)

# Number of eligible M5 analytical decision bars. The loader obtains separate
# overlapping source counts for M5, M15, H1, and H4 plus synchronized warm-up.
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

        execution_profile = pinned_xauusd_research_profile()
        symbol = execution_profile.instrument.symbol
        config = BacktestConfig(execution_profile=execution_profile)

        runner = BacktestRunner(config)

        print("=" * 70)
        print("XAUUSD HISTORICAL BACKTEST")
        print("=" * 70)
        print(f"Bars requested  : {HISTORICAL_BARS:,}")
        print(
            "Window end UTC  : "
            f"{HISTORICAL_END_TIME.isoformat()}"
        )
        instrument = execution_profile.instrument
        costs = execution_profile.costs
        print(f"Symbol          : {instrument.symbol}")
        print(f"Tick size       : {instrument.tick_size}")
        print(f"Tick value/lot  : {instrument.tick_value_per_lot}")
        print(f"Point size      : {instrument.point_size}")
        print(f"Lot step        : {instrument.volume_step}")
        print(f"Minimum lot     : {instrument.minimum_volume}")
        print(f"Maximum lot     : {instrument.maximum_volume}")
        print(f"Contract size   : {instrument.contract_size}")
        print(f"Minimum stop    : {instrument.minimum_stop_distance}")
        print(f"Spec provenance : {instrument.provenance.value}")
        print(
            "Historical spec : "
            f"{instrument.historical_specification_verified}"
        )
        print(
            "Historical price: "
            f"{execution_profile.historical_price_side.value}"
        )

        print(
            "Cost profile     : "
            f"{costs.profile_id}"
        )
        print(
            "Costs verified   : "
            f"{costs.verified}"
        )
        print(f"Spread points   : {costs.spread_points}")
        print(f"Slippage points : {costs.slippage_points}")
        print(
            "Commission/trade: "
            f"{costs.commission_per_trade}"
        )
        print(
            "Commission/lot  : "
            f"{costs.commission_per_lot}"
        )
        if not costs.verified:
            print(
                "WARNING          : Execution costs are not verified for "
                "this broker account."
            )

        output = runner.run_with_strategy_comparison(
            symbol=symbol,
            timeframe=mt5.TIMEFRAME_M5,
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
