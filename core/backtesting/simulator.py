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
        Simulate a trade using future market bars.

        NOTE:
        This is the first implementation step.
        Trade execution logic will be added next.
        """

        raise NotImplementedError(
            "Trade simulation has not been implemented yet."
        )