"""
Trade Simulator.
"""

from __future__ import annotations

from core.regime_detector.models import MarketBar
from core.risk_manager.models import TradePlan

from .models import BacktestTrade


class TradeSimulator:
    """
    Simulates historical trade execution.
    """

    def simulate(
        self,
        trade_plan: TradePlan,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> BacktestTrade:
        """
        Execute a historical trade candle-by-candle.

        Current implementation:

        - Opens on entry_bar.close
        - Checks every future candle
        - Stops at Stop Loss
        - Stops at Take Profit
        - Closes on final candle if neither is hit
        """

        entry_price = entry_bar.close

        exit_price = future_bars[-1].close if future_bars else entry_price
        exit_bar = future_bars[-1] if future_bars else entry_bar
        exit_reason = "END_OF_DATA"

        is_buy = trade_plan.direction.upper() == "BUY"

        for bar in future_bars:

            if is_buy:

                if bar.low <= trade_plan.stop_loss:
                    exit_price = trade_plan.stop_loss
                    exit_bar = bar
                    exit_reason = "STOP_LOSS"
                    break

                if bar.high >= trade_plan.take_profit:
                    exit_price = trade_plan.take_profit
                    exit_bar = bar
                    exit_reason = "TAKE_PROFIT"
                    break

            else:

                if bar.high >= trade_plan.stop_loss:
                    exit_price = trade_plan.stop_loss
                    exit_bar = bar
                    exit_reason = "STOP_LOSS"
                    break

                if bar.low <= trade_plan.take_profit:
                    exit_price = trade_plan.take_profit
                    exit_bar = bar
                    exit_reason = "TAKE_PROFIT"
                    break

        pnl = (
            exit_price - entry_price
            if is_buy
            else entry_price - exit_price
        )

        return BacktestTrade(
            trade_plan=trade_plan,
            entry_bar=entry_bar,
            exit_bar=exit_bar,
            entry_price=entry_price,
            exit_price=exit_price,
            profit=pnl,
            exit_reason=exit_reason,
        )