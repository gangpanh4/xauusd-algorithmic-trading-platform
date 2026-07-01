"""
Live Trading Engine.
"""

from __future__ import annotations

from core.mt5_execution.executor import (
    MT5Executor,
)

from core.trading_pipeline.pipeline import (
    TradingPipeline,
)

from .config import (
    LiveTradingConfig,
)

from .models import (
    LiveTradingResult,
)

from .state import (
    LiveTradingState,
)


class LiveTradingEngine:
    """
    Coordinates the live trading workflow.
    """

    def __init__(
        self,
        config: LiveTradingConfig,
    ) -> None:

        self.config = config

        self.state = LiveTradingState()

        self.pipeline = TradingPipeline(
            config.pipeline,
        )

        self.executor = MT5Executor(
            config.execution,
        )

    def start(self) -> None:
        """
        Start the live trading engine.
        """

        self.state.reset()

        self.state.running = True

        self.executor.initialize()

    def stop(self) -> None:
        """
        Stop the live trading engine.
        """

        self.state.running = False

        self.executor.shutdown()

    def process_bar(
        self,
        bar,
        *,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> LiveTradingResult:
        """
        Process one completed market bar.
        """

        self.state.processed_bars += 1

        pipeline_result = self.pipeline.process_bar(
            bar,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
        )

        return LiveTradingResult(
            pipeline_result=pipeline_result,
            execution_result=None,
            trade_executed=False,
        )