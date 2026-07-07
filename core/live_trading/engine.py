"""
Live Trading Engine.
"""

from __future__ import annotations

import logging

from core.execution_adapter.adapter import ExecutionAdapter
from core.execution_adapter.config import ExecutionAdapterConfig
from core.mt5_execution.executor import (
    MT5Executor,
)
from core.risk_manager.models import RiskDecision
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

logger = logging.getLogger(__name__)


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

        self.adapter = ExecutionAdapter(
            ExecutionAdapterConfig(),
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
        warmup: bool = False,
    ) -> LiveTradingResult:
        """
        Process one completed market bar.
        """

        self.state.processed_bars += 1

        logger.info(
            "Processing new bar: %s",
            bar.timestamp,
        )

        pipeline_result = self.pipeline.process_bar(
            bar,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
        )

        if warmup:
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        logger.info(
            "Signal=%s Decision=%s",
            pipeline_result.signal.direction,
            pipeline_result.trade_plan.decision,
        )

        trade_plan = pipeline_result.trade_plan

        logger.info(
            "Entry=%s SL=%s TP=%s Volume=%s",
            trade_plan.entry_price,
            trade_plan.stop_loss,
            trade_plan.take_profit,
            trade_plan.position_size,
        )

        if trade_plan.decision != RiskDecision.APPROVE:
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        execution_request = self.adapter.adapt(
            pipeline_result,
        )

        logger.info("Sending order to MT5...")

        execution_result = self.executor.execute_order(
            execution_request.order_request,
        )

        logger.info(
            "Execution result: %s",
            execution_result,
        )

        self.state.executed_trades += 1

        return LiveTradingResult(
            pipeline_result=pipeline_result,
            execution_result=execution_result,
            trade_executed=True,
        )