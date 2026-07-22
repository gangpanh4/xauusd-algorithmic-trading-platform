"""
Research Analytics storage.

Provides an in-memory repository for completed trade analytics
records. The storage layer is intentionally simple and independent
from statistical calculations.
"""

from __future__ import annotations

from .models import TradeAnalytics


class ResearchStorage:
    """
    Stores completed trade analytics records.

    The storage layer is responsible only for persisting
    TradeAnalytics objects during a research session.
    """

    def __init__(self) -> None:
        """Initialize empty storage."""

        self._trades: list[TradeAnalytics] = []

    def add_trade(
        self,
        trade: TradeAnalytics,
    ) -> None:
        """
        Store a completed trade.
        """

        self._trades.append(trade)

    def get_trades(
        self,
    ) -> tuple[TradeAnalytics, ...]:
        """
        Return all stored trades as an immutable tuple.
        """

        return tuple(self._trades)

    def clear(
        self,
    ) -> None:
        """
        Remove all stored trades.
        """

        self._trades.clear()

    @property
    def total_trades(
        self,
    ) -> int:
        """
        Number of stored trades.
        """

        return len(self._trades)

    @property
    def is_empty(
        self,
    ) -> bool:
        """
        Whether no trades are currently stored.
        """

        return self.total_trades == 0