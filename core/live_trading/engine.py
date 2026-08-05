"""Live Trading Engine."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from math import isclose, isfinite
import json
import logging

from core.data.models import MarketBar
from core.execution_adapter.adapter import ExecutionAdapter
from core.execution_adapter.config import ExecutionAdapterConfig
from core.mt5_execution.deal_history import get_realized_deals
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.active_orders import get_active_order_count
from core.mt5_execution.models import OrderStatus
from core.mt5_execution.positions import get_open_positions
from core.multi_timeframe.enums import Timeframe
from core.risk_manager.models import RiskDecision
from core.trading_pipeline.models import PipelineResult
from core.trading_pipeline.pipeline import TradingPipeline

from .config import LiveTradingConfig
from .models import LiveTradingResult
from .partial_fill_store import (
    PartialFillStateError,
    PartialFillStateStore,
    PersistedPartialFill,
)
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
        self.partial_fill_store = PartialFillStateStore(
            config.partial_fill_state_path
        )

    def start(self) -> None:
        """Start in analysis-only or live-execution mode."""

        self.state.reset()

        if self.config.live_execution_enabled:
            self._restore_partial_fill_state()

        if not self.config.live_execution_enabled:
            self.state.running = True
            logger.warning(
                "Live execution is disabled; the execution adapter will not "
                "initialize MT5."
            )
            return

        if not self.executor.attach():
            self.state.last_error = "Failed to attach MT5 execution."
            logger.error(self.state.last_error)
            raise RuntimeError(self.state.last_error)

        self.state.running = True

    def stop(self) -> None:
        """Stop without touching MT5 in analysis-only mode."""

        self.state.running = False

        if not self.config.live_execution_enabled:
            return

        # The platform owns the shared MT5 session used by market data and
        # execution. Stop only detaches executor state; the platform performs
        # the single terminal shutdown in its finally block.
        self.executor.detach()

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

    def synchronize_active_orders(self) -> int:
        """Synchronize unresolved broker orders for the configured symbol.

        When a partial fill is unresolved, active-order state and authoritative
        broker position volume are reconciled together. Any inconsistent volume
        transition fails closed and preserves the execution guard.
        """

        count = get_active_order_count(self.config.symbol)
        if self.state.unresolved_partial_ticket is not None:
            positions = get_open_positions(self.config.symbol)
            observed_volume = sum(float(position.volume) for position in positions)
            self._reconcile_partial_fill(
                active_order_count=count,
                observed_position_volume=observed_volume,
            )
        else:
            self.state.active_order_count = count
        return self.state.active_order_count

    def reconcile_realized_deals(
        self,
        *,
        account_balance: float,
        as_of: datetime | None = None,
        initialize_only: bool = False,
    ) -> int:
        """Apply new broker closing deals exactly once.

        Startup reconciliation reconstructs the current UTC trading day before
        any ticket is committed as processed. The current balance is treated as
        authoritative, while the day-opening balance is inferred by removing
        the net P&L of this symbol's same-day realized deals.
        """

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

        if initialize_only:
            risk_state = self.pipeline.risk_manager.state
            risk_state_snapshot = deepcopy(risk_state)
            trading_date = end.date()
            same_day_deals = [
                deal
                for deal in new_deals
                if deal.timestamp.astimezone(UTC).date() == trading_date
            ]
            opening_balance = account_balance - sum(
                deal.net_pnl for deal in same_day_deals
            )
            day_start = datetime(
                trading_date.year,
                trading_date.month,
                trading_date.day,
                tzinfo=UTC,
            )

            try:
                self.pipeline.synchronize_account_balance(
                    opening_balance,
                    timestamp=day_start,
                )
                for deal in same_day_deals:
                    self.pipeline.register_realized_pnl(
                        deal.net_pnl,
                        timestamp=deal.timestamp,
                    )
                self.pipeline.synchronize_account_balance(
                    account_balance,
                    timestamp=end,
                )
            except Exception:
                self.pipeline.risk_manager.state = risk_state_snapshot
                raise
            # Startup tickets are committed only after the complete daily-state
            # reconstruction succeeds.
            self.state.processed_deal_tickets.update(
                deal.ticket for deal in new_deals
            )
        else:
            for deal in new_deals:
                self.pipeline.register_realized_pnl(
                    deal.net_pnl,
                    timestamp=deal.timestamp,
                )
                # Preserve the existing per-deal retry contract: once one deal
                # has been applied successfully, it must not be applied again if
                # a later deal or final balance synchronization fails.
                self.state.processed_deal_tickets.add(deal.ticket)

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

        self._require_new_observation_timestamp(bar.timestamp)

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
        minimum_lot: float | None = None,
        maximum_lot: float | None = None,
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
        self._require_new_observation_timestamp(
            observation_bar.timestamp
        )

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
            minimum_lot=minimum_lot,
            maximum_lot=maximum_lot,
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
        self.state.last_processed_timestamp = timestamp
        self.state.processed_bars += 1

        logger.info("Processing completed bar: %s", timestamp)

        if warmup:
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        self._record_shadow_observation(
            timestamp=timestamp,
            pipeline_result=pipeline_result,
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

        if (
            self.state.active_order_count > 0
            or self.state.unresolved_partial_ticket is not None
        ):
            self.state.skipped_trades += 1
            self.state.last_error = (
                "Execution blocked while an MT5 order remainder is unresolved."
            )
            logger.warning(self.state.last_error)
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

        if execution_result.status is OrderStatus.PENDING:
            # A placed order may execute later. Block subsequent submissions
            # until broker reconciliation confirms that no active order remains.
            self.state.active_order_count = max(
                1,
                self.state.active_order_count,
            )
            self.state.skipped_trades += 1
            self.state.last_ticket = execution_result.ticket
            self.state.last_error = execution_result.message
            logger.warning(
                "MT5 accepted an unresolved order: %s",
                execution_result.message,
            )
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=execution_result,
                trade_executed=False,
            )

        if execution_result.status is OrderStatus.PARTIALLY_FILLED:
            requested_volume = float(execution_request.order_request.volume)
            executed_volume = float(execution_result.executed_volume)
            remaining_volume = requested_volume - executed_volume

            if (
                execution_result.ticket is None
                or not isfinite(requested_volume)
                or not isfinite(executed_volume)
                or not isfinite(remaining_volume)
                or requested_volume <= 0.0
                or executed_volume <= 0.0
                or remaining_volume <= 0.0
            ):
                self.state.skipped_trades += 1
                self.state.last_error = (
                    "Partial-fill acknowledgement is internally inconsistent."
                )
                logger.error(self.state.last_error)
                return LiveTradingResult(
                    pipeline_result=pipeline_result,
                    execution_result=execution_result,
                    trade_executed=False,
                )

            created_at = execution_result.timestamp
            self.state.unresolved_partial_ticket = execution_result.ticket
            self.state.unresolved_requested_volume = requested_volume
            self.state.unresolved_executed_volume = executed_volume
            self.state.unresolved_remaining_volume = remaining_volume
            self.state.unresolved_partial_created_at = created_at
            self.state.active_order_count = max(
                1,
                self.state.active_order_count,
            )
            self.state.last_ticket = execution_result.ticket
            self.state.last_partial_fill_resolution = ""
            self.state.last_error = execution_result.message

            try:
                self._persist_partial_fill_state()
            except PartialFillStateError as exc:
                self._fail_closed_partial_fill(str(exc))
                raise

            self.pipeline.register_position_opened()
            logger.warning(
                "MT5 partially filled order %s: executed=%s remaining=%s",
                execution_result.ticket,
                executed_volume,
                remaining_volume,
            )
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=execution_result,
                trade_executed=True,
            )

        if execution_result.status is not OrderStatus.FILLED:
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

    def _require_new_observation_timestamp(
        self,
        timestamp: datetime,
    ) -> None:
        """Reject duplicate or out-of-order evidence before pipeline mutation."""

        if not isinstance(timestamp, datetime):
            raise TypeError("observation timestamp must be a datetime")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError(
                "observation timestamp must be timezone-aware"
            )

        normalized = timestamp.astimezone(UTC)
        previous = self.state.last_processed_timestamp
        if previous is not None and normalized <= previous:
            raise ValueError(
                "Live observation timestamps must increase strictly."
            )

    def _record_shadow_observation(
        self,
        *,
        timestamp: datetime,
        pipeline_result: PipelineResult,
    ) -> None:
        """Append one non-authoritative live observation as JSONL."""

        if not self.config.shadow_recording_enabled:
            return

        signal = pipeline_result.signal
        trade_plan = pipeline_result.trade_plan
        direction = getattr(signal, "direction", None)
        direction_name = getattr(direction, "name", None)
        if direction_name is None and direction is not None:
            direction_name = str(direction)

        decision = getattr(trade_plan, "decision", None)
        decision_name = getattr(decision, "name", None)
        if decision_name is None and decision is not None:
            decision_name = str(decision)

        payload = {
            "timestamp": timestamp.astimezone(UTC).isoformat(),
            "symbol": self.config.symbol,
            "live_execution_enabled": (
                self.config.live_execution_enabled
            ),
            "shadow_only": not self.config.live_execution_enabled,
            "signal_present": signal is not None,
            "trade_plan_present": trade_plan is not None,
            "direction": direction_name,
            "decision": decision_name,
            "entry_price": getattr(trade_plan, "entry_price", None),
            "stop_loss": getattr(trade_plan, "stop_loss", None),
            "take_profit": getattr(trade_plan, "take_profit", None),
            "position_size": getattr(trade_plan, "position_size", None),
            "risk_reward_ratio": getattr(
                trade_plan,
                "risk_reward_ratio",
                None,
            ),
            "reason": getattr(trade_plan, "reason", None),
            "trade_executed": False,
        }

        path = self.config.shadow_observation_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, sort_keys=True) + "\n")

        self.state.shadow_observations_recorded += 1

    def _reconcile_partial_fill(
        self,
        *,
        active_order_count: int,
        observed_position_volume: float,
    ) -> None:
        """Reconcile one unresolved partial fill against broker state."""

        requested = self.state.unresolved_requested_volume
        previously_executed = self.state.unresolved_executed_volume

        if (
            isinstance(active_order_count, bool)
            or not isinstance(active_order_count, int)
            or active_order_count < 0
            or not isfinite(observed_position_volume)
            or observed_position_volume < 0.0
            or not isfinite(requested)
            or not isfinite(previously_executed)
            or requested <= 0.0
            or previously_executed <= 0.0
            or previously_executed >= requested
        ):
            self._fail_closed_partial_fill(
                "Partial-fill reconciliation state is invalid."
            )
            return

        tolerance = 1e-12
        if observed_position_volume + tolerance < previously_executed:
            self._fail_closed_partial_fill(
                "Broker position volume fell below the acknowledged partial "
                "fill while its remainder was unresolved."
            )
            return
        if observed_position_volume > requested + tolerance:
            self._fail_closed_partial_fill(
                "Broker position volume exceeds the originally requested "
                "partial-fill volume."
            )
            return

        executed = min(observed_position_volume, requested)
        remaining = max(0.0, requested - executed)
        self.state.unresolved_executed_volume = executed
        self.state.unresolved_remaining_volume = remaining

        if active_order_count > 0:
            if isclose(
                executed,
                requested,
                rel_tol=0.0,
                abs_tol=tolerance,
            ):
                self._fail_closed_partial_fill(
                    "Broker reports full requested position volume while the "
                    "order remainder is still active."
                )
                return
            self.state.active_order_count = active_order_count
            self.state.last_error = (
                "Execution blocked while an MT5 order remainder is unresolved."
            )
            try:
                self._persist_partial_fill_state()
            except PartialFillStateError as exc:
                self._fail_closed_partial_fill(str(exc))
                raise
            return

        self.state.active_order_count = 0
        if isclose(
            executed,
            requested,
            rel_tol=0.0,
            abs_tol=tolerance,
        ):
            resolution = "FILLED"
        else:
            resolution = "REMAINDER_CANCELLED_OR_REJECTED"

        try:
            self.partial_fill_store.clear()
        except PartialFillStateError as exc:
            self._fail_closed_partial_fill(str(exc))
            raise

        if resolution == "FILLED":
            self.state.executed_trades += 1

        self.state.last_partial_fill_resolution = resolution
        self.state.unresolved_partial_ticket = None
        self.state.unresolved_requested_volume = 0.0
        self.state.unresolved_executed_volume = 0.0
        self.state.unresolved_remaining_volume = 0.0
        self.state.unresolved_partial_created_at = None
        self.state.last_error = ""

    def _restore_partial_fill_state(self) -> None:
        """Restore durable unresolved state before broker reconciliation."""

        try:
            record = self.partial_fill_store.load()
        except PartialFillStateError as exc:
            self._fail_closed_partial_fill(str(exc))
            raise

        if record is None:
            return
        if record.symbol != self.config.symbol:
            message = (
                "Persisted partial-fill symbol does not match configured "
                f"symbol: {record.symbol!r} != {self.config.symbol!r}."
            )
            self._fail_closed_partial_fill(message)
            raise PartialFillStateError(message)

        self.state.unresolved_partial_ticket = record.ticket
        self.state.unresolved_requested_volume = record.requested_volume
        self.state.unresolved_executed_volume = record.executed_volume
        self.state.unresolved_remaining_volume = record.remaining_volume
        self.state.unresolved_partial_created_at = record.created_at
        self.state.active_order_count = max(
            1,
            self.state.active_order_count,
        )
        self.state.last_ticket = record.ticket
        self.state.last_error = (
            "Execution blocked while a restored MT5 order remainder is "
            "unresolved."
        )

    def _persist_partial_fill_state(self) -> None:
        """Atomically persist the current unresolved partial-fill state."""

        ticket = self.state.unresolved_partial_ticket
        created_at = self.state.unresolved_partial_created_at
        if ticket is None or created_at is None:
            raise PartialFillStateError(
                "Unresolved partial-fill state is incomplete."
            )

        self.partial_fill_store.save(
            PersistedPartialFill(
                symbol=self.config.symbol,
                ticket=ticket,
                requested_volume=self.state.unresolved_requested_volume,
                executed_volume=self.state.unresolved_executed_volume,
                remaining_volume=self.state.unresolved_remaining_volume,
                created_at=created_at,
            )
        )

    def _fail_closed_partial_fill(self, message: str) -> None:
        """Preserve the unresolved guard when broker state is inconsistent."""

        self.state.active_order_count = max(
            1,
            self.state.active_order_count,
        )
        self.state.last_error = message
        logger.error(message)
