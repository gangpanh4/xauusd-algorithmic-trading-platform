"""
Trade Simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import (
    BacktestTrade,
    ExitReason,
    TradeOutcome,
)
from core.regime_detector.models import MarketBar
from core.risk_manager.models import TradePlan


class ExecutionPolicy(Enum):
    """
    Defines how OHLC candles are interpreted when
    both stop-loss and take-profit could occur
    within the same candle.
    """

    CONSERVATIVE = "CONSERVATIVE"
    OPTIMISTIC = "OPTIMISTIC"


@dataclass
class SimulationState:
    """
    Mutable state for a single simulated trade.
    """

    entry_price: float
    is_buy: bool

    current_stop_loss: float

    holding_bars: int = 0

    highest_price: float = 0.0
    lowest_price: float = 0.0

    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0

    breakeven_triggered: bool = False
    breakeven_pending: bool = False

    lifecycle_events: list[str] = field(default_factory=list)


class TradeSimulator:
    """
    Executes a TradePlan against historical market data.
    """

    def __init__(
        self,
        execution_policy: ExecutionPolicy = ExecutionPolicy.CONSERVATIVE,
    ):
        self.execution_policy = execution_policy

    def _should_activate_breakeven(
        self,
        is_buy: bool,
        bar: MarketBar,
        entry_price: float,
        original_stop_loss: float,
    ) -> bool:
        """
        Returns True when price has moved at least +1R.
        Does NOT modify the stop loss.
        """

        risk = abs(entry_price - original_stop_loss)

        if risk <= 0:
            return False

        if is_buy:
            return bar.high >= entry_price + risk

        return bar.low <= entry_price - risk







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

        state = SimulationState(
            entry_price=trade_plan.entry_price,
            is_buy=is_buy,
            current_stop_loss=trade_plan.stop_loss,
            highest_price=trade_plan.entry_price,
            lowest_price=trade_plan.entry_price,
        )

        exit_price = None
        exit_bar = None
        exit_reason = ExitReason.END_OF_DATA

        for i, bar in enumerate(future_bars, start=1):

            state.holding_bars = i

            # Activate breakeven at the start of the NEXT candle
            if state.breakeven_pending:
                state.current_stop_loss = entry_price
                state.breakeven_triggered = True
                state.lifecycle_events.append("BREAKEVEN")
                state.breakeven_pending = False

            if is_buy:

                state.highest_price = max(
                    state.highest_price,
                    bar.high,
                )
                state.lowest_price = min(
                    state.lowest_price,
                    bar.low,
                )

                state.max_favorable_excursion = max(
                    state.max_favorable_excursion,
                    state.highest_price - entry_price,
                )

                state.max_adverse_excursion = max(
                    state.max_adverse_excursion,
                    entry_price - state.lowest_price,
                )

            else:

                state.highest_price = max(
                    state.highest_price,
                    bar.high,
                )
                state.lowest_price = min(
                    state.lowest_price,
                    bar.low,
                )

                state.max_favorable_excursion = max(
                    state.max_favorable_excursion,
                    entry_price - state.lowest_price,
                )

                state.max_adverse_excursion = max(
                    state.max_adverse_excursion,
                    state.highest_price - entry_price,
                )

            if (
                not state.breakeven_triggered
                and not state.breakeven_pending
            ):
                if self._should_activate_breakeven(
                    is_buy=is_buy,
                    bar=bar,
                    entry_price=entry_price,
                    original_stop_loss=trade_plan.stop_loss,
                ):
                    state.breakeven_pending = True

            if is_buy:

                if bar.low <= state.current_stop_loss:
                    exit_price = state.current_stop_loss
                    exit_bar = bar
                    exit_reason = ExitReason.STOP_LOSS
                    break

                if bar.high >= trade_plan.take_profit:
                    exit_price = trade_plan.take_profit
                    exit_bar = bar
                    exit_reason = ExitReason.TAKE_PROFIT
                    break

            else:

                if bar.high >= state.current_stop_loss:
                    exit_price = state.current_stop_loss
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



        # Always calculate R using the ORIGINAL stop loss,
        # not the dynamically managed stop.
        original_risk = abs(
            trade_plan.entry_price
            - trade_plan.stop_loss
        )

        reward = abs(
            exit_price
            - trade_plan.entry_price
        )

        risk_reward = (
            reward / original_risk
            if original_risk > 0
            else 0.0
        )
        
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
            holding_bars=state.holding_bars,
            holding_time=exit_time - entry_time,
            risk_reward=risk_reward,
            max_favorable_excursion=state.max_favorable_excursion,
            max_adverse_excursion=state.max_adverse_excursion,
            highest_price=state.highest_price,
            lowest_price=state.lowest_price,
            breakeven_triggered=state.breakeven_triggered,
            trailing_stop_triggered=False,
            partial_exit_taken=False,
            lifecycle_events=tuple(state.lifecycle_events),
        )
    




