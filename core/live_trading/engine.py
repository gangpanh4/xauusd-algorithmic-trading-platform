"""Live Trading Engine."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from math import isclose, isfinite
from uuid import uuid4

from core.data.models import MarketBar
from core.execution_adapter.adapter import ExecutionAdapter
from core.execution_adapter.config import ExecutionAdapterConfig
from core.mt5_execution.account import get_account_info
from core.mt5_execution.active_orders import (
    get_active_order_count,
    get_active_orders,
)
from core.mt5_execution.authority import _authorize_broker_mutation
from core.mt5_execution.deal_history import (
    get_execution_deals,
    get_realized_deals,
)
from core.mt5_execution.executor import MT5Executor
from core.mt5_execution.models import (
    OrderRequest,
    OrderResult,
    OrderStatus,
)
from core.mt5_execution.order_history import get_historical_orders
from core.mt5_execution.positions import get_open_positions
from core.mt5_execution.symbols import get_symbol_info
from core.multi_timeframe.enums import Timeframe
from core.risk_manager.models import RiskDecision
from core.trading_pipeline.models import (
    PipelineObservationAudit,
    PipelineResult,
)
from core.trading_pipeline.pipeline import TradingPipeline

from .config import LiveTradingConfig
from .demo_canary_launch_abort_control import (
    DemoCanaryLaunchAbort,
    DemoCanaryLaunchPlan,
    DemoCanaryPreflightSnapshot,
    build_demo_canary_preflight_snapshot,
    create_demo_canary_launch_plan,
    evaluate_demo_canary_final_abort_control,
)
from .demo_canary_readiness_review import (
    DemoCanaryReadinessReview,
    review_demo_canary_readiness,
)
from .demo_execution_authorization import (
    DemoExecutionAuthorization,
    DemoExecutionAuthorizationError,
    consume_demo_execution_authorization,
    load_demo_execution_authorization,
    validate_demo_execution_authorization,
    validate_demo_execution_authorization_time_window,
)
from .execution_concurrency import (
    ExecutionConcurrencyError,
    LocalExecutionLock,
    build_execution_lock_path,
)
from .execution_intent_reconciliation import (
    ExecutionIntentReconciliationDisposition,
    ExecutionIntentReconciliationError,
    ExecutionIntentReconciliationResult,
    reconcile_execution_intent,
)
from .execution_intent_store import (
    ExecutionIntentStateError,
    ExecutionIntentStore,
    PersistedExecutionIntent,
    apply_execution_result,
    build_execution_intent,
)
from .execution_readiness import (
    ExecutionReadinessInputs,
    ExecutionReadinessResult,
    assess_execution_readiness,
)
from .execution_reconciliation_audit import (
    append_execution_reconciliation_audit,
    build_execution_reconciliation_audit,
)
from .models import LiveTradingResult
from .parity_evidence import (
    LiveParityEvidence,
    append_parity_evidence,
)
from .parity_provenance import (
    PARITY_EVIDENCE_SCHEMA_VERSION,
    current_parity_provenance,
)
from .partial_fill_store import (
    PartialFillStateError,
    PartialFillStateStore,
    PersistedPartialFill,
)
from .state import LiveTradingState

logger = logging.getLogger(__name__)

_MT5_TRADE_RETCODE_PLACED = 10008


@dataclass(frozen=True, slots=True)
class _ExecutionSafetyFacts:
    """One read-only view of submission-relevant runtime and broker facts."""

    readiness_inputs: ExecutionReadinessInputs
    open_position_count: int
    unresolved_execution_intent: bool


@dataclass(frozen=True, slots=True)
class _ExecutionSafetyPlan:
    """Initial reviewed state to compare inside submission ownership."""

    review: DemoCanaryReadinessReview
    launch_plan: DemoCanaryLaunchPlan


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
        self.execution_intent_store = ExecutionIntentStore(
            config.execution_intent_state_path
        )
        self._execution_submission_lock = LocalExecutionLock(
            build_execution_lock_path(
                config.execution_intent_state_path,
                scope="broker-submission",
            ),
            purpose="broker submission",
        )

    def assess_demo_execution_readiness(
        self,
        inputs: ExecutionReadinessInputs,
    ) -> ExecutionReadinessResult:
        """Return readiness diagnostics without submitting or authorizing orders."""

        return assess_execution_readiness(self.config, inputs)

    def record_clock_normalization_validated(self) -> None:
        """Record successful clock validation for the current process session."""

        self.state.clock_normalization_validated = True

    def record_parity_validation_passed(self) -> None:
        """Record externally verified parity evidence for this process session."""

        self.state.parity_validation_passed = True

    def start(self) -> None:
        """Start in analysis-only or live-execution mode."""

        self.state.reset()
        self.state.shadow_session_id = str(uuid4())
        self.state.shadow_session_started_at = datetime.now(UTC)

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

        try:
            self.reconcile_execution_intent()
        except Exception:
            self.executor.detach()
            raise

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

    def reconcile_execution_intent(
        self,
        *,
        as_of: datetime | None = None,
    ) -> ExecutionIntentReconciliationResult | None:
        """Reconcile persisted execution identity before any new submission."""

        intent = self.execution_intent_store.load()
        if intent is None:
            self.state.execution_intent_reconciliation_status = "NO_INTENT"
            self.state.execution_intent_reconciliation_reason = (
                "No persisted execution intent exists."
            )
            self.state.execution_intent_reconciliation_ticket = None
            return None

        end = datetime.now(UTC) if as_of is None else as_of.astimezone(UTC)
        start = intent.observation_timestamp.astimezone(UTC) - timedelta(
            minutes=5
        )

        try:
            active_orders = get_active_orders(intent.symbol)
            historical_orders = get_historical_orders(
                date_from=start,
                date_to=end,
                symbol=intent.symbol,
            )
            execution_deals = get_execution_deals(
                date_from=start,
                date_to=end,
                symbol=intent.symbol,
            )
            open_positions = get_open_positions(intent.symbol)
            result = reconcile_execution_intent(
                intent=intent,
                active_orders=active_orders,
                historical_orders=historical_orders,
                execution_deals=execution_deals,
                open_positions=open_positions,
                as_of=end,
            )
        except (
            ExecutionIntentReconciliationError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            failure_audit = build_execution_reconciliation_audit(
                intent_before=intent,
                intent_after=intent,
                disposition="FAILED_CLOSED",
                matching_order_ticket=intent.ticket,
                matching_deal_tickets=(),
                active_order_match_count=len(
                    locals().get("active_orders", ())
                ),
                historical_order_match_count=len(
                    locals().get("historical_orders", ())
                ),
                execution_deal_match_count=len(
                    locals().get("execution_deals", ())
                ),
                open_position_match_count=len(
                    locals().get("open_positions", ())
                ),
                startup_allowed=False,
                live_execution_enabled=self.config.live_execution_enabled,
                failure_reason=str(exc),
            )
            append_execution_reconciliation_audit(
                self.config.execution_reconciliation_audit_path,
                failure_audit,
            )
            self.state.active_order_count = max(
                1,
                self.state.active_order_count,
            )
            self.state.execution_intent_reconciliation_status = "FAILED_CLOSED"
            self.state.execution_intent_reconciliation_reason = str(exc)
            self.state.execution_intent_reconciliation_ticket = intent.ticket
            self.state.last_error = str(exc)
            logger.error("Execution-intent reconciliation failed: %s", exc)
            raise RuntimeError(
                "Execution-intent reconciliation failed closed."
            ) from exc

        if result.intent != intent:
            self.execution_intent_store.save(result.intent)

        startup_allowed = not result.intent.unresolved
        audit = build_execution_reconciliation_audit(
            intent_before=intent,
            intent_after=result.intent,
            disposition=result.disposition.value,
            matching_order_ticket=result.matching_order_ticket,
            matching_deal_tickets=result.matching_deal_tickets,
            active_order_match_count=len(active_orders),
            historical_order_match_count=len(historical_orders),
            execution_deal_match_count=len(execution_deals),
            open_position_match_count=len(open_positions),
            startup_allowed=startup_allowed,
            live_execution_enabled=self.config.live_execution_enabled,
            failure_reason="" if startup_allowed else result.reason,
        )
        append_execution_reconciliation_audit(
            self.config.execution_reconciliation_audit_path,
            audit,
        )

        self.state.execution_intent_reconciliation_status = (
            result.disposition.value
        )
        self.state.execution_intent_reconciliation_reason = result.reason
        self.state.execution_intent_reconciliation_ticket = (
            result.matching_order_ticket
        )
        self.state.last_ticket = result.matching_order_ticket

        if result.intent.unresolved:
            self.state.active_order_count = max(
                1,
                len(active_orders),
                self.state.active_order_count,
            )
            self.state.last_error = result.reason
        else:
            self.state.active_order_count = len(active_orders)
            self.state.last_error = ""

        if result.disposition is (
            ExecutionIntentReconciliationDisposition.UNRESOLVED_NO_EVIDENCE
        ):
            logger.warning(result.reason)
        else:
            logger.info(
                "Execution-intent reconciliation: %s (%s)",
                result.disposition.value,
                result.reason,
            )
        return result

    def synchronize_open_positions(self) -> int:
        """Synchronize risk exposure from authoritative broker positions.

        A partially closed position remains present and therefore keeps the
        open-position count unchanged. A fully closed position disappears from
        MT5 and reduces the count during the next reconciliation.
        """

        self.state.positions_synchronized = False
        positions = get_open_positions(self.config.symbol)
        count = len(positions)
        self.pipeline.set_open_position_count(count)
        self.state.open_position_count = count
        self.state.positions_synchronized = True
        return count

    def synchronize_active_orders(self) -> int:
        """Synchronize unresolved broker orders for the configured symbol.

        When a partial fill is unresolved, active-order state and authoritative
        broker position volume are reconciled together. Any inconsistent volume
        transition fails closed and preserves the execution guard.
        """

        self.state.active_orders_synchronized = False
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
        self.state.active_orders_synchronized = True
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

        self.state.realized_deals_synchronized = False
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
        self.state.realized_deals_synchronized = True
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
            parity_context=None,
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
            parity_context=(
                bars_by_timeframe,
                account_balance,
                stop_loss_distance,
                pip_value,
                tick_size,
                lot_step,
                minimum_lot,
                maximum_lot,
            ),
        )

    def _finalize_observation(
        self,
        *,
        observation_bar: MarketBar,
        pipeline_result: PipelineResult,
        warmup: bool,
        parity_context: tuple[
            Mapping[Timeframe, Sequence[MarketBar]],
            float,
            float,
            float,
            float,
            float,
            float | None,
            float | None,
        ] | None,
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
        if parity_context is not None:
            self._record_parity_evidence(
                timestamp=timestamp,
                parity_context=parity_context,
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

        try:
            safety_plan = self._prepare_execution_safety(
                request=execution_request.order_request,
            )
        except (
            DemoCanaryLaunchAbort,
            DemoExecutionAuthorizationError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as exc:
            self.state.skipped_trades += 1
            self.state.last_error = (
                "Execution safety controls blocked submission: "
                f"{exc}"
            )
            logger.error(self.state.last_error)
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        try:
            submission_owner = self._execution_submission_lock.acquire()
        except ExecutionConcurrencyError as exc:
            self.state.skipped_trades += 1
            self.state.last_error = (
                "Execution safety controls blocked submission: "
                f"{exc}"
            )
            logger.error(self.state.last_error)
            return LiveTradingResult(
                pipeline_result=pipeline_result,
                execution_result=None,
                trade_executed=False,
            )

        try:
            try:
                authorization = self._require_final_execution_safety(
                    plan=safety_plan,
                    request=execution_request.order_request,
                )
                execution_intent = self._build_execution_intent(
                    observation_timestamp=timestamp,
                    request=execution_request.order_request,
                )
                consume_demo_execution_authorization(
                    self.config.demo_authorization_path,
                    authorization,
                    intent_key=execution_intent.intent_key,
                    consumed_at=datetime.now(UTC),
                )
                self.execution_intent_store.claim(execution_intent)
            except (
                DemoCanaryLaunchAbort,
                DemoExecutionAuthorizationError,
                ExecutionConcurrencyError,
                ExecutionIntentStateError,
                RuntimeError,
                TypeError,
                ValueError,
            ) as exc:
                self.state.skipped_trades += 1
                self.state.last_error = (
                    "Execution safety controls blocked submission: "
                    f"{exc}"
                )
                logger.error(self.state.last_error)
                return LiveTradingResult(
                    pipeline_result=pipeline_result,
                    execution_result=None,
                    trade_executed=False,
                )

            broker_request = OrderRequest(
                symbol=execution_request.order_request.symbol,
                side=execution_request.order_request.side,
                volume=execution_request.order_request.volume,
                entry_price=execution_request.order_request.entry_price,
                stop_loss=execution_request.order_request.stop_loss,
                take_profit=execution_request.order_request.take_profit,
                comment=execution_intent.broker_comment,
            )
            def pre_send_guard() -> None:
                validate_demo_execution_authorization_time_window(
                    authorization,
                    now=datetime.now(UTC),
                )

            self.state.order_submissions_this_session += 1
            with _authorize_broker_mutation():
                execution_result = self.executor.execute_order(
                    broker_request,
                    pre_send_guard=pre_send_guard,
                )
            self._record_execution_intent_result(
                execution_intent,
                execution_result,
            )
            self._update_execution_failure_counter(execution_result)
        finally:
            self._execution_submission_lock.release(submission_owner)

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

    def _prepare_execution_safety(
        self,
        *,
        request: OrderRequest,
    ) -> _ExecutionSafetyPlan:
        """Build the initial read-only plan before submission ownership."""

        initial_time = datetime.now(UTC)
        initial_facts = self._collect_execution_safety_facts()
        self._require_execution_readiness(initial_facts.readiness_inputs)

        authorization = load_demo_execution_authorization(
            self.config.demo_authorization_path
        )
        validate_demo_execution_authorization(
            authorization,
            config=self.config,
            account=initial_facts.readiness_inputs.account,
            request=request,
            now=initial_time,
        )

        review = review_demo_canary_readiness(
            config=self.config,
            readiness_inputs=initial_facts.readiness_inputs,
            authorization=authorization,
            request=request,
            reconciliation_status=(
                self.state.execution_intent_reconciliation_status
            ),
            now=initial_time,
        )
        if not review.review_passed:
            raise DemoCanaryLaunchAbort(
                "Demo canary readiness review failed: "
                + "; ".join(review.reasons)
            )

        initial_snapshot = self._build_demo_canary_snapshot(
            review=review,
            authorization=authorization,
            request=request,
            facts=initial_facts,
            captured_at=initial_time,
        )
        launch_plan = create_demo_canary_launch_plan(
            initial_snapshot,
            now=initial_time,
        )
        return _ExecutionSafetyPlan(
            review=review,
            launch_plan=launch_plan,
        )

    def _require_final_execution_safety(
        self,
        *,
        plan: _ExecutionSafetyPlan,
        request: OrderRequest,
    ) -> DemoExecutionAuthorization:
        """Re-read and bind final state while submission ownership is held."""

        final_time = datetime.now(UTC)
        final_facts = self._collect_execution_safety_facts()
        self._require_execution_readiness(final_facts.readiness_inputs)
        final_authorization = load_demo_execution_authorization(
            self.config.demo_authorization_path
        )
        validate_demo_execution_authorization(
            final_authorization,
            config=self.config,
            account=final_facts.readiness_inputs.account,
            request=request,
            now=final_time,
        )
        current_review = replace(
            plan.review,
            account_login=final_facts.readiness_inputs.account.login,
            account_server=final_facts.readiness_inputs.account.server,
        )
        current_snapshot = self._build_demo_canary_snapshot(
            review=current_review,
            authorization=final_authorization,
            request=request,
            facts=final_facts,
            captured_at=final_time,
        )
        decision = evaluate_demo_canary_final_abort_control(
            plan=plan.launch_plan,
            current_snapshot=current_snapshot,
            now=final_time,
        )
        if decision.abort_required:
            raise DemoCanaryLaunchAbort(
                "Final demo canary state recheck failed: "
                + "; ".join(decision.reasons)
            )

        return final_authorization

    def _collect_execution_safety_facts(self) -> _ExecutionSafetyFacts:
        """Read current broker and durable state without mutation authority."""

        account = get_account_info()

        self.state.positions_synchronized = False
        positions = get_open_positions(self.config.symbol)
        open_position_count = len(positions)
        self.state.open_position_count = open_position_count
        self.state.positions_synchronized = True

        self.state.active_orders_synchronized = False
        active_order_count = get_active_order_count(self.config.symbol)
        self.state.active_order_count = active_order_count
        self.state.active_orders_synchronized = True

        self.state.symbol_specification_loaded = False
        symbol = get_symbol_info(self.config.symbol)
        if symbol.name != self.config.symbol:
            raise RuntimeError(
                "Loaded symbol specification does not match configured symbol."
            )
        self.state.symbol_specification_loaded = True

        persisted_partial = self.partial_fill_store.load()
        runtime_partial_ticket = self.state.unresolved_partial_ticket
        persisted_partial_ticket = (
            None if persisted_partial is None else persisted_partial.ticket
        )
        if (
            runtime_partial_ticket is not None
            and persisted_partial_ticket is not None
            and runtime_partial_ticket != persisted_partial_ticket
        ):
            raise RuntimeError(
                "Runtime and persisted partial-fill tickets differ."
            )
        unresolved_partial_ticket = (
            runtime_partial_ticket
            if runtime_partial_ticket is not None
            else persisted_partial_ticket
        )

        intent = self.execution_intent_store.load()
        readiness_inputs = ExecutionReadinessInputs(
            account=account,
            positions_synchronized=self.state.positions_synchronized,
            active_orders_synchronized=(
                self.state.active_orders_synchronized
            ),
            realized_deals_synchronized=(
                self.state.realized_deals_synchronized
            ),
            symbol_specification_loaded=(
                self.state.symbol_specification_loaded
            ),
            clock_normalization_validated=(
                self.state.clock_normalization_validated
            ),
            parity_validation_passed=self.state.parity_validation_passed,
            active_order_count=active_order_count,
            unresolved_partial_ticket=unresolved_partial_ticket,
            order_submissions_this_session=(
                self.state.order_submissions_this_session
            ),
            consecutive_execution_failures=(
                self.state.consecutive_execution_failures
            ),
        )
        return _ExecutionSafetyFacts(
            readiness_inputs=readiness_inputs,
            open_position_count=open_position_count,
            unresolved_execution_intent=(
                intent is not None and intent.unresolved
            ),
        )

    def _require_execution_readiness(
        self,
        inputs: ExecutionReadinessInputs,
    ) -> None:
        result = assess_execution_readiness(self.config, inputs)
        if result.ready:
            return
        raise RuntimeError(
            "Execution readiness failed: " + "; ".join(result.reasons)
        )

    def _build_demo_canary_snapshot(
        self,
        *,
        review: DemoCanaryReadinessReview,
        authorization: DemoExecutionAuthorization,
        request: OrderRequest,
        facts: _ExecutionSafetyFacts,
        captured_at: datetime,
    ) -> DemoCanaryPreflightSnapshot:
        inputs = facts.readiness_inputs
        return build_demo_canary_preflight_snapshot(
            review=review,
            authorization=authorization,
            request=request,
            account_trade_mode=inputs.account.trade_mode,
            active_order_count=inputs.active_order_count,
            open_position_count=facts.open_position_count,
            unresolved_partial_ticket=inputs.unresolved_partial_ticket,
            unresolved_execution_intent=(
                facts.unresolved_execution_intent
            ),
            reconciliation_status=(
                self.state.execution_intent_reconciliation_status
            ),
            order_submissions_this_session=(
                inputs.order_submissions_this_session
            ),
            consecutive_execution_failures=(
                inputs.consecutive_execution_failures
            ),
            live_execution_enabled=self.config.live_execution_enabled,
            demo_execution_approved=self.config.demo_execution_approved,
            execution_kill_switch_enabled=(
                self.config.execution_kill_switch_enabled
            ),
            captured_at=captured_at,
        )

    def _update_execution_failure_counter(
        self,
        result: OrderResult,
    ) -> None:
        """Update the process-session breaker from one confirmed outcome."""

        confirmed_success = result.status in {
            OrderStatus.FILLED,
            OrderStatus.PARTIALLY_FILLED,
        } or (
            result.status is OrderStatus.PENDING
            and result.retcode == _MT5_TRADE_RETCODE_PLACED
        )
        if confirmed_success:
            self.state.consecutive_execution_failures = 0
            return

        confirmed_broker_failure = (
            result.status in {OrderStatus.REJECTED, OrderStatus.CANCELLED}
            and result.retcode is not None
        )
        if confirmed_broker_failure:
            self.state.consecutive_execution_failures += 1

    def _prepare_execution_intent(
        self,
        *,
        observation_timestamp: datetime,
        request: object,
    ) -> PersistedExecutionIntent:
        """Persist intent before broker submission and reject duplicates."""

        return self.execution_intent_store.claim(
            self._build_execution_intent(
                observation_timestamp=observation_timestamp,
                request=request,
            )
        )

    def _build_execution_intent(
        self,
        *,
        observation_timestamp: datetime,
        request: object,
    ) -> PersistedExecutionIntent:
        """Build one deterministic intent without mutating durable state."""

        return build_execution_intent(
            observation_timestamp=observation_timestamp,
            request=request,
            magic_number=self.config.execution.magic_number,
        )

    def _record_execution_intent_result(
        self,
        intent: PersistedExecutionIntent,
        result: OrderResult,
    ) -> None:
        """Persist broker acknowledgement before later state mutation."""

        self.execution_intent_store.save(
            apply_execution_result(intent, result)
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

    def _record_parity_evidence(
        self,
        *,
        timestamp: datetime,
        parity_context: tuple[
            Mapping[Timeframe, Sequence[MarketBar]],
            float,
            float,
            float,
            float,
            float,
            float | None,
            float | None,
        ],
    ) -> None:
        """Persist exact synchronized inputs for research-only replay."""

        if not self.config.parity_recording_enabled:
            return
        if self.config.live_execution_enabled:
            raise RuntimeError(
                "Parity evidence recording requires analysis-only mode."
            )

        audit = self.pipeline.last_observation_audit
        if audit is None:
            raise RuntimeError(
                "Parity evidence requires an authoritative pipeline audit."
            )

        (
            bars_by_timeframe,
            account_balance,
            stop_loss_distance,
            pip_value,
            tick_size,
            lot_step,
            minimum_lot,
            maximum_lot,
        ) = parity_context
        histories = {
            timeframe: tuple(bars_by_timeframe.get(timeframe, ()))
            for timeframe in Timeframe
        }
        provenance = current_parity_provenance(self.config.pipeline)
        evidence = LiveParityEvidence(
            schema_version=PARITY_EVIDENCE_SCHEMA_VERSION,
            analytical_contract_version=(
                provenance.analytical_contract_version
            ),
            source_commit=provenance.source_commit,
            pipeline_config_fingerprint=(
                provenance.pipeline_config_fingerprint
            ),
            captured_at=datetime.now(UTC),
            observation_timestamp=timestamp,
            symbol=self.config.symbol,
            bars_by_timeframe=histories,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
            tick_size=tick_size,
            lot_step=lot_step,
            minimum_lot=minimum_lot,
            maximum_lot=maximum_lot,
            expected_audit=audit,
            live_execution_enabled=False,
            shadow_only=True,
            trade_executed=False,
        )
        append_parity_evidence(
            self.config.parity_evidence_path,
            evidence,
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

        session_started_at = self.state.shadow_session_started_at
        if not self.state.shadow_session_id or session_started_at is None:
            # Preserve compatibility with direct analysis/test callers that
            # process observations without explicitly starting the engine.
            # The normal platform path still creates a fresh session in
            # start(), including on every restart.
            self.state.shadow_session_id = str(uuid4())
            self.state.shadow_session_started_at = datetime.now(UTC)
            session_started_at = self.state.shadow_session_started_at

        recorded_at = datetime.now(UTC)

        payload = {
            "timestamp": timestamp.astimezone(UTC).isoformat(),
            "recorded_at": recorded_at.isoformat(),
            "session_id": self.state.shadow_session_id,
            "session_started_at": (
                session_started_at.astimezone(UTC).isoformat()
            ),
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

        audit = self.pipeline.last_observation_audit
        if audit is not None:
            payload.update(
                self._pipeline_audit_payload(
                    audit=audit,
                    timestamp=timestamp,
                )
            )

        path = self.config.shadow_observation_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, sort_keys=True) + "\n")

        self.state.shadow_observations_recorded += 1

    @staticmethod
    def _pipeline_audit_payload(
        *,
        audit: PipelineObservationAudit,
        timestamp: datetime,
    ) -> dict[str, object]:
        """Serialize the authoritative pipeline audit without recomputation."""

        normalized_timestamp = timestamp.astimezone(UTC)
        if audit.timestamp != normalized_timestamp:
            raise ValueError(
                "Pipeline audit timestamp must match the live observation."
            )

        return {
            "pipeline_disposition": audit.disposition.value,
            "pipeline_stage_reached": audit.stage_reached.value,
            "pipeline_rejection_stage": (
                audit.rejection_stage.value
                if audit.rejection_stage is not None
                else None
            ),
            "pipeline_reason_code": audit.reason_code,
            "pipeline_reason": audit.reason,
            "regime_confirmed": audit.regime_confirmed,
            "bos_present": audit.bos_present,
            "choch_present": audit.choch_present,
            "liquidity_present": audit.liquidity_present,
            "feature_count": audit.feature_count,
            "probability_calculated": audit.probability_calculated,
            "probability_accepted": audit.probability_accepted,
            "probability_value": audit.probability_value,
            "trade_quality_calculated": audit.trade_quality_calculated,
            "trade_quality_approved": audit.trade_quality_approved,
            "trade_quality_score": audit.trade_quality_score,
            "confluence_available": audit.confluence_available,
            "confluence_approved": audit.confluence_approved,
            "confluence_score": audit.confluence_score,
            "signal_generated": audit.signal_generated,
            "risk_approved": audit.risk_approved,
        }

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
