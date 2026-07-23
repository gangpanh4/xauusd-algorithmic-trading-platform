"""Composite output for one completed historical backtest run."""

from __future__ import annotations

from dataclasses import dataclass

from .models import BacktestResult
from .strategy_comparison import BacktestStrategyComparison


@dataclass(slots=True, frozen=True)
class BacktestRunOutput:
    """Bundle the existing backtest result with its strategy comparison.

    The wrapper preserves ``BacktestResult`` unchanged while allowing callers
    to receive the execution result and observational comparison from one run.
    """

    result: BacktestResult
    strategy_comparison: BacktestStrategyComparison

    def __post_init__(self) -> None:
        if not isinstance(self.result, BacktestResult):
            raise TypeError('result must be BacktestResult')
        if not isinstance(
            self.strategy_comparison,
            BacktestStrategyComparison,
        ):
            raise TypeError(
                'strategy_comparison must be BacktestStrategyComparison'
            )
