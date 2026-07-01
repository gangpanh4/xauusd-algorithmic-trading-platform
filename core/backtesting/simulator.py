"""
Trade Simulator.
"""

from __future__ import annotations

from .models import (
    BacktestTrade,
)


class TradeSimulator:
    """
    Simulates historical trade execution.
    """

    def simulate(
        self,
        trade: BacktestTrade,
    ) -> BacktestTrade:
        """
        Simulate a completed trade.

        Currently this is a placeholder and simply
        returns the provided trade.
        """

        return trade