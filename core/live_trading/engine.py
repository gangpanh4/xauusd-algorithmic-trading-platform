"""Live Trading Engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
import logging

from core.data.models import MarketBar
from core.execution_adapter.adapter import ExecutionAdapter
from core.execution_adapter.config import ExecutionAdapterConfig
from core.mt5_execution.deal_history import get_realized_deals
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.models import OrderStatus
from core.mt5_execution.positions import get_open_positions
from core.multi_timeframe.enums import Timeframe
from core.risk_manager.models import RiskDecision
from core.trading_pipeline.models import PipelineResult
from core.trading_pipeline.pipeline import TradingPipeline

from .config import LiveTradingConfig
from .models import LiveTradingResult
from .state import LiveTradingState

logger = logging.getLogger(__name__)


class LiveTradingEngine:
    """Coordinate live analysis and optional MT5 order execution."""

    def __init__(self, config: LiveTradingConfig) -> None:
        self.config = config
        self.state = LiveTradingState()
        self.pipeline = TradingPipeline(config.pipeline)
        self.executor = MT5Executor(config.execution)
        self.adapter = ExecutionAdapter(
            ExecutionAdapterConfig(symbol=config.symbol)
        )

    def start(self) -> None:
        """Start in analysis-only or live-execution mode."""

        self.state.reset()

        if not self.config.live_execution_enabled:
            self.state.running = True
            logger.warning(
                "Live execution is disabled; the execution adapter will not "
                "initialize MT5."
            )
            return

        if not self.executor.initialize():
            self.state.last_error = "Failed to initialize MT5 execution."
            logger.error(self.state.last_error)
            raise RuntimeError(self.state.last_error)

        self.state.running = True

    def stop(self) -> None:
        """Stop without touching MT5 in analysis-only mode."""

        self.state.running = False

        if not self.config.live_execution_enabled:
            return

        if self.executor.is_connected():
            self.executor.shutdown()

    def synchronize_open_positions(self) -> int:
        """Synchronize risk exposure from authoritative broker positions.

        A partially closed position remains present and therefore keeps the
        open-position count unchanged. A fully closed position disappears from
        MT5 and reduces the count during the next reconciliation.
        """

        positions = get_open_positions(self.config.symbol)
        count = len(positions)
        self.pipeline.set_open_position_count(count)
        return count

    def reconcile_realized_deals(
        self,
        *,
        account_balance: float,
        as_of: datetime | None = None,
        initialize_only: bool = False,
    ) -> int:
        """Apply new broker closing deals exactly once."""

        end = datetime.now(UTC) if as_of is None else as_of.astimezone(UTC)
        start = self.state.last_deal_reconciliation_time
        if start is None:
            start = end - timedelta(days=7)
        else:
            start = start - timedelta(minutes=5)

        deals = get_realized_deals(
            date_from=start,
            date_to=end,
            symbol=self.config.symbol,
        )
        new_deals = [
            deal
            for deal in deals
            if deal.ticket not in self.state.processed_deal_tickets
        ]

        for deal in new_deals:
            if not initialize_only:
                self.pipeline.register_realized_pnl(
                    deal.net_pnl,
                    timestamp=deal.timestamp,
                )

            # Mark the deal processed only after every required state update
            # succeeds. A failure therefore remains retryable.
            self.state.processed_deal_tickets.add(deal.ticket)

        if not initialize_only:
            self.pipeline.synchronize_account_balance(
                account_balance,
                timestamp=end,
            )

        self.state.last_deal_reconciliation_time = end
        return len(new_deals)

    def process_bar(
        self,
        bar: MarketBar,
        *,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
        warmup: bool = False,
    ) -> LiveTradingResult:
        """Process one completed bar through the legacy single-timeframe path."""

        pipeline_result = self.pipeline.process_bar(
            bar,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
        )
        return self._finalize_observation(
            observation_bar=bar,
            pipeline_result=pipeline_result,
            warmup=warmup,
        )

    def process_multi_timeframe(
        self,
        bars_by_timeframe: Mapping[Timeframe, Sequence[MarketBar]],
        *,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
        tick_size: float = TradingPipeline.DEFAULT_TICK_SIZE,
        lot_step: float = TradingPipeline.DEFAULT_LOT_STEP,
        warmup: bool = False,
    ) -> LiveTradingResult:
        """Process the same synchronized MTF evidence used by backtesting."""

        if not isinstance(bars_by_timeframe, Mapping):
            raise TypeError("bars_by_timeframe must be a mapping")

        m5_bars = bars_by_timeframe.get(Timeframe.M5)
        if not m5_bars:
            raise ValueError("Missing completed M5 bars for live processing.")

        mtf_result = self.pipeline.multi_timeframe.process(
            bars_by_timeframe,
        )
        confluence = self.pipeline.confluence_engine.evaluate_multi_timeframe(
            mtf_result,
        )
        observation_bar = m5_bars[-1]

        pipeline_result = self.pipeline.process_bar(
            observation_bar,
            confluence=confluence,
            multi_timeframe_result=mtf_result,
            market_structure_result=mtf_result.m5.market_structure,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
            tick_size=tick_size,
            lot_step=lot_step,
        )
        return self._finalize_observation(
            observation_bar=observation_bar,
            pipeline_result=pipeline_result,
            warmup=warmup,
        )

    def _finalize_observation(
        self,
        *,
        observation_bar: MarketBar,
        pipeline_result: PipelineResult,
        warmup: bool,
    ) -> LiveTradingResult:
        """Apply chronology, diagnostics, and optional execution."""

        timestamp = observation_bar.timestamp.astimezone(UTC)
        previous = self.state.last_processed_timestamp
        if previous is not None and timestamp <= previous:
            raise ValueError(
                "Live observation timestamps must increase strictly."
            )

        self.state.last_processed_timestamp = timestamp
        self.state.processed_bars += 1

        logger.info("Processing completed bar: %s", timestamp)

        if warmup:
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        signal = pipeline_result.signal
        trade_plan = pipeline_result.trade_plan

        if signal is None or trade_plan is None:
            self.state.skipped_trades += 1
            logger.warning(
                "Pipeline returned no executable signal or trade plan."
            )
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        logger.info(
            "Signal=%s Decision=%s",
            signal.direction,
            trade_plan.decision,
        )
        logger.info(
            "Entry=%s SL=%s TP=%s Volume=%s",
            trade_plan.entry_price,
            trade_plan.stop_loss,
            trade_plan.take_profit,
            trade_plan.position_size,
        )

        if trade_plan.decision is not RiskDecision.APPROVE:
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
        execution_result = self.executor.execute_order(
            execution_request.order_request,
        )

        executed_statuses = {
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
        }
        if execution_result.status not in executed_statuses:
            self.state.skipped_trades += 1
            self.state.last_error = execution_result.message
            logger.error(
                "MT5 did not execute the order: %s",
                execution_result.message,
            )
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=execution_result,
                trade_executed=False,
            )

        self.pipeline.register_position_opened()
        self.state.executed_trades += 1
        self.state.last_ticket = execution_result.ticket
        self.state.last_error = ""

        return LiveTradingResult(
            pipeline_result=pipeline_result,
            execution_result=execution_result,
            trade_executed=True,
        )
