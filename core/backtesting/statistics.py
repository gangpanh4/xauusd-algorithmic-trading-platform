"""
Advanced performance statistics for the backtesting engine.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .models import BacktestResult


@dataclass(slots=True)
class PerformanceStatistics:
    """
    Advanced performance statistics.
    """

    sharpe_ratio: float
    sortino_ratio: float
    recovery_factor: float
    expectancy: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    average_trade: float
    profit_factor: float
    max_drawdown: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float


class StatisticsCalculator:
    """
    Calculate advanced statistics from a BacktestResult.
    """

    def calculate(
        self,
        result: BacktestResult,
    ) -> PerformanceStatistics:

        profits = [
            trade.net_profit
            for trade in result.trades
        ]

        wins = [
            p
            for p in profits
            if p > 0
        ]

        losses = [
            p
            for p in profits
            if p < 0
        ]

        average_trade = (
            sum(profits) / len(profits)
            if profits
            else 0.0
        )

        average_win = (
            sum(wins) / len(wins)
            if wins
            else 0.0
        )

        average_loss = (
            abs(sum(losses) / len(losses))
            if losses
            else 0.0
        )

        expectancy = (
            average_trade
            if profits
            else 0.0
        )

        largest_win = (
            max(wins)
            if wins
            else 0.0
        )

        largest_loss = (
            abs(min(losses))
            if losses
            else 0.0
        )

        recovery_factor = (
            result.net_profit / result.max_drawdown
            if result.max_drawdown > 0
            else 0.0
        )

        sharpe_ratio = self._sharpe(profits)

        sortino_ratio = self._sortino(profits)

        return PerformanceStatistics(
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            recovery_factor=recovery_factor,
            expectancy=expectancy,
            average_win=average_win,
            average_loss=average_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            average_trade=average_trade,
            profit_factor=result.profit_factor,
            max_drawdown=result.max_drawdown,
            total_trades=result.total_trades,
            winning_trades=result.winning_trades,
            losing_trades=result.losing_trades,
            breakeven_trades=result.breakeven_trades,
            win_rate=result.win_rate,
        )

    @staticmethod
    def _sharpe(
        returns: list[float],
    ) -> float:

        if len(returns) < 2:
            return 0.0

        mean = sum(returns) / len(returns)

        variance = sum(
            (r - mean) ** 2
            for r in returns
        ) / (len(returns) - 1)

        std = math.sqrt(variance)

        if std == 0:
            return 0.0

        return mean / std

    @staticmethod
    def _sortino(
        returns: list[float],
    ) -> float:

        if len(returns) < 2:
            return 0.0

        mean = sum(returns) / len(returns)

        downside = [
            r
            for r in returns
            if r < 0
        ]

        if not downside:
            return 0.0

        variance = sum(
            r**2
            for r in downside
        ) / len(downside)

        downside_std = math.sqrt(variance)

        if downside_std == 0:
            return 0.0

        return mean / downside_std