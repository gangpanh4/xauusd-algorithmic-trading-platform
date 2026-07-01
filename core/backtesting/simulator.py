"""
Trade Simulator.
"""

from __future__ import annotations

from datetime import timedelta

from .models import (
    BacktestTrade,
    ExitReason,
    TradeOutcome,
)
from core.regime_detector.models import MarketBar
from core.risk_manager.models import TradePlan


class TradeSimulator:
    """
    Historical trade simulator.
    """

    def simulate(
        self,
        trade_plan: TradePlan,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> BacktestTrade:

        entry_price = entry_bar.close

        direction = getattr(
            trade_plan.signal,
            "direction",
            getattr(trade_plan.signal, "signal", None),
        )

        direction = direction.name if direction else "BUY"

        is_buy = direction == "BUY"

        exit_price = entry_price
        exit_bar = entry_bar
        exit_reason = ExitReason.END_OF_DATA

        holding_bars = 0

        for holding_bars, bar in enumerate(future_bars, start=1):

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

            exit_price = bar.close
            exit_bar = bar

        gross_profit = (
            exit_price - entry_price
            if is_buy
            else entry_price - exit_price
        ) * trade_plan.position_size

        commission = 0.0
        spread_cost = 0.0

        net_profit = gross_profit - commission - spread_cost

        if net_profit > 0:
            outcome = TradeOutcome.WIN
        elif net_profit < 0:
            outcome = TradeOutcome.LOSS
        else:
            outcome = TradeOutcome.BREAKEVEN

        risk = abs(entry_price - trade_plan.stop_loss)

        reward = abs(exit_price - entry_price)

        rr = reward / risk if risk else 0.0

        return BacktestTrade(
            entry_time=entry_bar.timestamp,
            exit_time=exit_bar.timestamp,
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
            holding_time=timedelta(minutes=holding_bars),
            risk_reward=rr,
        )