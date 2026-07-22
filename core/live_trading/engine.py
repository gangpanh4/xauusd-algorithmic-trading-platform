"""
Live Trading Engine.
"""

from __future__ import annotations

import logging

from core.execution_adapter.adapter import ExecutionAdapter
from core.execution_adapter.config import ExecutionAdapterConfig
from core.mt5_execution.executor import MT5Executor
from core.risk_manager.models import RiskDecision
from core.trading_pipeline.pipeline import TradingPipeline

from .config import LiveTradingConfig
from .models import LiveTradingResult
from .state import LiveTradingState

logger = logging.getLogger(__name__)


class LiveTradingEngine:
    """
    Coordinate the live trading workflow.

    Market analysis may run while live execution is disabled. In that mode the
    engine must never initialize MetaTrader 5 or submit an order.
    """

    def __init__(
        self,
        config: LiveTradingConfig,
    ) -> None:
        self.config = config
        self.state = LiveTradingState()
        self.pipeline = TradingPipeline(config.pipeline)
        self.executor = MT5Executor(config.execution)
        self.adapter = ExecutionAdapter(ExecutionAdapterConfig())

    def start(self) -> None:
        """
        Start the engine in analysis-only or live-execution mode.

        Raises:
            RuntimeError: If live execution is enabled but MT5 initialization
                fails.
        """

        self.state.reset()

        if not self.config.live_execution_enabled:
            self.state.running = True
            logger.warning(
                "Live execution is disabled; MT5 will not be initialized."
            )
            return

        if not self.executor.initialize():
            self.state.last_error = "Failed to initialize MT5 execution."
            logger.error(self.state.last_error)
            raise RuntimeError(self.state.last_error)

        self.state.running = True

    def stop(self) -> None:
        """
        Stop the engine without touching MT5 in analysis-only mode.
        """

        self.state.running = False

        if not self.config.live_execution_enabled:
            return

        if self.executor.is_connected():
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

        An approved trade plan is intentionally returned without execution when
        ``live_execution_enabled`` is false.
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
            self.state.skipped_trades += 1
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        if not self.config.live_execution_enabled:
            self.state.skipped_trades += 1
            logger.warning(
                "Approved trade was not executed because live execution is "
                "disabled."
            )
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        if not self.executor.is_connected():
            self.state.last_error = (
                "Live execution is enabled, but MT5 is not connected."
            )
            logger.error(self.state.last_error)
            raise RuntimeError(self.state.last_error)

        execution_request = self.adapter.adapt(pipeline_result)

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
