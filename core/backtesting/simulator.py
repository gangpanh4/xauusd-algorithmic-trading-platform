"""
Trade Simulator.
"""

from __future__ import annotations

from .models import (
    BacktestTrade,
    ExitReason,
    TradeOutcome,
)
from core.regime_detector.models import MarketBar
from core.risk_manager.models import TradePlan


class TradeSimulator:
    """
    Executes a TradePlan against historical market data.
    """

    def simulate(
        self,
        trade_plan: TradePlan,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> BacktestTrade:

        entry_price = trade_plan.entry_price
        entry_time = entry_bar.timestamp

        direction = getattr(
            trade_plan.signal,
            "direction",
            getattr(trade_plan.signal, "signal", None),
        )

        direction = direction.name if direction else "BUY"
        is_buy = direction == "BUY"

        exit_price = None
        exit_bar = None
        exit_reason = ExitReason.END_OF_DATA
        holding_bars = 0

        for i, bar in enumerate(future_bars, start=1):

            holding_bars = i

            if is_buy:

                if bar.low <= trade_plan.stop_loss:
                    exit_price = trade_plan.stop_loss
                    exit_bar = bar
                    exit_reason = ExitReason.STOP_LOSS
                    break

                if bar.high >= trade_plan.take_profit:
                    exit_price = trade_plan.take_profit
                    exit_bar = bar
                    exit_reason = ExitReason.TAKE_PROFIT
                    break

            else:

                if bar.high >= trade_plan.stop_loss:
                    exit_price = trade_plan.stop_loss
                    exit_bar = bar
                    exit_reason = ExitReason.STOP_LOSS
                    break

                if bar.low <= trade_plan.take_profit:
                    exit_price = trade_plan.take_profit
                    exit_bar = bar
                    exit_reason = ExitReason.TAKE_PROFIT
                    break

        # End of data fallback
        if exit_price is None:
            exit_bar = future_bars[-1] if future_bars else entry_bar
            exit_price = exit_bar.close

        exit_time = exit_bar.timestamp

        # Profit calculation
        if is_buy:
            gross_profit = (exit_price - entry_price) * trade_plan.position_size
        else:
            gross_profit = (entry_price - exit_price) * trade_plan.position_size

        commission = 0.0
        spread_cost = 0.0
        net_profit = gross_profit - commission - spread_cost

        outcome = (
            TradeOutcome.WIN
            if net_profit > 0
            else TradeOutcome.LOSS
            if net_profit < 0
            else TradeOutcome.BREAKEVEN
        )

        risk = abs(entry_price - trade_plan.stop_loss)
        reward = abs(exit_price - entry_price)

        risk_reward = reward / risk if risk else 0.0

        return BacktestTrade(
            entry_time=entry_time,
            exit_time=exit_time,
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            position_size=trade_plan.position_size,
            spread_cost=spread_cost,
            commission=commission,
            gross_profit=gross_profit,
            net_profit=net_profit,
            outcome=outcome,
            exit_reason=exit_reason,
            holding_bars=holding_bars,
            holding_time=exit_time - entry_time,
            risk_reward=risk_reward,
        )