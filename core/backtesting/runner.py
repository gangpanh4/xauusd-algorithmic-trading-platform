"""
Historical Backtest Runner.
"""

from __future__ import annotations

from core.trading_pipeline.pipeline import (
    TradingPipeline,
)

from .config import (
    BacktestRunnerConfig,
)

from .state import (
    BacktestRunnerState,
)


class BacktestRunner:
    """
    Runs the trading pipeline over historical bars.
    """

    def __init__(
        self,
        config: BacktestRunnerConfig,
    ) -> None:

        self.config = config

        self.state = BacktestRunnerState()

        self.pipeline = TradingPipeline(
            config.pipeline,
        )