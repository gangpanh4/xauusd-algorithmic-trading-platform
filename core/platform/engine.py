"""Platform Engine."""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from datetime import datetime, timedelta

import MetaTrader5 as mt5

from core.backtesting.config import BacktestConfig, BacktestExecutionModel
from core.backtesting.runner import BacktestRunner
from core.data.market_data import MarketDataService
from core.data.models import MarketBar
from core.execution_economics.profiles import (
    pinned_xauusd_research_profile,
)
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.execution_reconciliation_report import (
    ExecutionReconciliationReporter,
)
from core.live_trading.multi_timeframe_buffer import LiveMultiTimeframeBuffer
from core.live_trading.parity_report import LiveParityReporter
from core.live_trading.shadow_observation_report import (
    ShadowObservationReporter,
)
from core.mt5_execution.account import get_account_info
from core.mt5_execution.symbol_specification import (
    get_live_symbol_specification,
)
from core.multi_timeframe.enums import Timeframe
from core.multi_timeframe.history_alignment import (
    clip_history,
    required_bar_count,
    utc_week_start,
    visible_bars,
)

logger = logging.getLogger(__name__)


class TradingPlatform:
    """Top-level platform lifecycle controller."""

    def __init__(self) -> None:
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("Platform already initialized.")
            return
        logger.info("Initializing XAUUSD Trading Platform...")
        self._initialized = True
        logger.info("Platform initialized successfully.")

    def run_backtest(self) -> None:
        if not self._initialized:
            raise RuntimeError("Platform has not been initialized.")

        logger.info("Starting Backtesting Platform...")
        if not mt5.initialize():
            raise RuntimeError(
                f"MT5 initialization failed: {mt5.last_error()}"
            )

        try:
            execution_profile = pinned_xauusd_research_profile()
            symbol = execution_profile.instrument.symbol
            config = BacktestConfig(
                execution_profile=execution_profile,
                execution_model=BacktestExecutionModel.M5_COMPLETED_OHLC_V2,
            )
            runner = BacktestRunner(config)
            result = runner.run(
                symbol=symbol,
                timeframe=mt5.TIMEFRAME_M5,
                bars=50000,
            )
            runner.generate_reports(result)
            logger.info("Backtesting completed successfully.")
        finally:
            mt5.shutdown()

    def run_live(self) -> None:
        """Run synchronized M5/M15/H1/H4 live analysis and optional execution."""

        if not self._initialized:
            raise RuntimeError("Platform has not been initialized.")

        logger.info("Starting Live Trading Platform...")
        config = LiveTradingConfig(
            live_execution_enabled=False,
            shadow_recording_enabled=True,
            parity_recording_enabled=True,
        )
        engine = LiveTradingEngine(config)
        mt5_started = False

        services = {
            Timeframe.M5: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_M5,
                server_utc_offset_hours=(
                    config.mt5_server_utc_offset_hours
                ),
                max_clock_skew_seconds=(
                    config.mt5_clock_max_skew_seconds
                ),
            ),
            Timeframe.M15: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_M15,
                server_utc_offset_hours=(
                    config.mt5_server_utc_offset_hours
                ),
                max_clock_skew_seconds=(
                    config.mt5_clock_max_skew_seconds
                ),
            ),
            Timeframe.H1: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_H1,
                server_utc_offset_hours=(
                    config.mt5_server_utc_offset_hours
                ),
                max_clock_skew_seconds=(
                    config.mt5_clock_max_skew_seconds
                ),
            ),
            Timeframe.H4: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_H4,
                server_utc_offset_hours=(
                    config.mt5_server_utc_offset_hours
                ),
                max_clock_skew_seconds=(
                    config.mt5_clock_max_skew_seconds
                ),
            ),
        }
        try:
            # Market data requires an MT5 terminal connection even when order
            # execution is disabled.
            if not mt5.initialize():
                raise RuntimeError(
                    f"MT5 initialization failed: {mt5.last_error()}"
                )
            mt5_started = True

            normalized_tick_time = services[
                Timeframe.M5
            ].validate_clock_alignment()
            logger.info(
                "Validated MT5 clock normalization: "
                "server_utc_offset_hours=%s normalized_tick_utc=%s "
                "maximum_skew_seconds=%s",
                config.mt5_server_utc_offset_hours,
                normalized_tick_time,
                config.mt5_clock_max_skew_seconds,
            )

            engine.start()
            engine.record_clock_normalization_validated()
            engine.synchronize_open_positions()
            engine.synchronize_active_orders()

            logger.info("Loading synchronized historical bars...")
            bootstrap_m5 = services[Timeframe.M5].get_latest_closed_bar()
            if bootstrap_m5 is None:
                raise RuntimeError("No completed M5 bootstrap boundary available.")
            histories, capacities, source_start, bootstrap_boundary = (
                self._load_aligned_live_histories(
                    services=services,
                    latest_m5=bootstrap_m5,
                    analysis_window_bars=config.history_window_bars,
                )
            )
            buffer = LiveMultiTimeframeBuffer(
                window_bars=config.history_window_bars,
                source_capacity_bars=capacities,
            )
            for timeframe, history in histories.items():
                buffer.load(timeframe, history)
            logger.info(
                "Loaded aligned live source history: start=%s end=%s",
                source_start,
                bootstrap_boundary,
            )

            account = get_account_info()

            engine.reconcile_realized_deals(
                account_balance=account.balance,
                initialize_only=True,
            )
            engine.pipeline.synchronize_account_balance(account.balance)

            symbol_spec = get_live_symbol_specification(config.symbol)
            logger.info(
                "Loaded %s risk specification: tick_size=%s "
                "tick_value_per_lot=%s lot_step=%s minimum_lot=%s "
                "maximum_lot=%s minimum_stop=%s",
                symbol_spec.symbol,
                symbol_spec.tick_size,
                symbol_spec.tick_value_per_lot,
                symbol_spec.lot_step,
                symbol_spec.minimum_lot,
                symbol_spec.maximum_lot,
                symbol_spec.minimum_stop_distance,
            )

            logger.info("Warming up synchronized analytical state...")
            warmup_snapshots = []
            for m5_bar in buffer.histories[Timeframe.M5]:
                boundary = m5_bar.timestamp + timedelta(minutes=5)
                snapshot = buffer.snapshot(boundary)
                if snapshot is None:
                    continue
                warmup_snapshots.append(snapshot)
            if len(warmup_snapshots) < config.warmup_bars:
                raise RuntimeError(
                    "Insufficient complete synchronized M5 warm-up snapshots: "
                    f"required={config.warmup_bars} "
                    f"available={len(warmup_snapshots)}."
                )
            for snapshot in warmup_snapshots:
                engine.process_multi_timeframe(
                    snapshot,
                    account_balance=account.balance,
                    stop_loss_distance=symbol_spec.minimum_stop_distance,
                    pip_value=symbol_spec.tick_value_per_lot,
                    tick_size=symbol_spec.tick_size,
                    lot_step=symbol_spec.lot_step,
                    minimum_lot=symbol_spec.minimum_lot,
                    maximum_lot=symbol_spec.maximum_lot,
                    warmup=True,
                )

            logger.info(
                "Warm-up completed with %s synchronized M5 snapshots. "
                "Waiting for completed M5 bars. "
                "Shadow observations will be appended to %s.",
                len(warmup_snapshots),
                config.shadow_observation_path,
            )

            try:
                while True:
                    m5_bar = services[Timeframe.M5].get_latest_closed_bar()
                    if m5_bar is None:
                        time.sleep(config.poll_interval_seconds)
                        continue

                    for timeframe in (
                        Timeframe.M15,
                        Timeframe.H1,
                        Timeframe.H4,
                    ):
                        completed = services[timeframe].get_latest_closed_bar()
                        if completed is not None:
                            buffer.append(timeframe, completed)

                    if not buffer.append(Timeframe.M5, m5_bar):
                        time.sleep(config.poll_interval_seconds)
                        continue

                    boundary = m5_bar.timestamp + timedelta(minutes=5)
                    snapshot = buffer.snapshot(boundary)
                    if snapshot is None:
                        logger.warning(
                            "Skipping %s because synchronized MTF warm-up is "
                            "incomplete.",
                            m5_bar.timestamp,
                        )
                        time.sleep(config.poll_interval_seconds)
                        continue

                    account = get_account_info()

                    # Reconcile realized P&L and exposure before every new
                    # M5 decision so daily-loss controls use broker state.
                    engine.reconcile_realized_deals(
                        account_balance=account.balance,
                        as_of=boundary,
                    )
                    engine.synchronize_open_positions()
                    engine.synchronize_active_orders()

                    engine.process_multi_timeframe(
                        snapshot,
                        account_balance=account.balance,
                        stop_loss_distance=(
                            symbol_spec.minimum_stop_distance
                        ),
                        pip_value=symbol_spec.tick_value_per_lot,
                        tick_size=symbol_spec.tick_size,
                        lot_step=symbol_spec.lot_step,
                        minimum_lot=symbol_spec.minimum_lot,
                        maximum_lot=symbol_spec.maximum_lot,
                    )
                    time.sleep(config.poll_interval_seconds)

            except KeyboardInterrupt:
                logger.info("Stopping live trading...")

        finally:
            engine.stop()
            if mt5_started:
                mt5.shutdown()
            logger.info("Live Trading Engine stopped.")

    @staticmethod
    def _load_aligned_live_histories(
        *,
        services: Mapping[Timeframe, MarketDataService],
        latest_m5: MarketBar,
        analysis_window_bars: int,
    ) -> tuple[
        dict[Timeframe, list[MarketBar]],
        dict[Timeframe, int],
        datetime,
        datetime,
    ]:
        """Load one completed live bootstrap window from a captured M5 close."""

        if isinstance(analysis_window_bars, bool) or not isinstance(
            analysis_window_bars,
            int,
        ):
            raise TypeError("analysis_window_bars must be an integer")
        if analysis_window_bars < 2:
            raise ValueError("analysis_window_bars must be at least 2")
        required = (
            Timeframe.M5,
            Timeframe.M15,
            Timeframe.H1,
            Timeframe.H4,
        )
        if set(services) != set(required):
            raise ValueError("services must contain exactly M5, M15, H1, and H4")

        boundary = latest_m5.timestamp + timedelta(minutes=5)
        pilot_h4 = visible_bars(
            services[Timeframe.H4].get_historical_bars(
                analysis_window_bars + 2
            ),
            timeframe=Timeframe.H4,
            boundary=boundary,
        )
        if len(pilot_h4) < analysis_window_bars:
            raise RuntimeError(
                "Insufficient completed H4 history at the live bootstrap boundary."
            )
        source_start = (
            utc_week_start(pilot_h4[-analysis_window_bars].timestamp)
            - timedelta(days=7)
        )
        capacities = {
            timeframe: required_bar_count(
                start=source_start,
                end=boundary,
                timeframe=timeframe,
            )
            for timeframe in required
        }
        histories: dict[Timeframe, list[MarketBar]] = {}
        for timeframe in (
            Timeframe.M5,
            Timeframe.M15,
            Timeframe.H1,
            Timeframe.H4,
        ):
            loaded = services[timeframe].get_historical_bars(
                capacities[timeframe]
            )
            clipped = list(
                clip_history(
                    loaded,
                    timeframe=timeframe,
                    start=source_start,
                    end=boundary,
                )
            )
            if not clipped:
                raise RuntimeError(
                    f"No completed {timeframe.value} history overlaps the "
                    "live bootstrap window."
                )
            histories[timeframe] = clipped

        if histories[Timeframe.M5][-1] != latest_m5:
            raise RuntimeError(
                "The captured M5 bootstrap boundary changed during history loading."
            )
        return histories, capacities, source_start, boundary

    def run_research(self) -> None:
        """Validate and summarize persisted live-shadow observations."""

        if not self._initialized:
            raise RuntimeError("Platform has not been initialized.")

        logger.info("Running Research Mode...")
        config = LiveTradingConfig()
        reporter = ShadowObservationReporter(
            input_path=config.shadow_observation_path,
            output_directory=config.shadow_summary_directory,
        )
        csv_path, json_path = reporter.export()
        logger.info("Shadow summary CSV exported to %s", csv_path)
        logger.info("Shadow summary JSON exported to %s", json_path)

        if config.parity_evidence_path.exists():
            parity_reporter = LiveParityReporter(
                input_path=config.parity_evidence_path,
                output_directory=config.parity_report_directory,
            )
            parity_csv, parity_json = parity_reporter.export()
            logger.info("Live parity CSV exported to %s", parity_csv)
            logger.info("Live parity JSON exported to %s", parity_json)
        else:
            logger.info(
                "No live parity evidence found at %s.",
                config.parity_evidence_path,
            )

        if config.execution_reconciliation_audit_path.exists():
            reconciliation_reporter = ExecutionReconciliationReporter(
                input_path=config.execution_reconciliation_audit_path,
                output_directory=(
                    config.execution_reconciliation_report_directory
                ),
            )
            reconciliation_csv, reconciliation_json = (
                reconciliation_reporter.export()
            )
            logger.info(
                "Execution reconciliation CSV exported to %s",
                reconciliation_csv,
            )
            logger.info(
                "Execution reconciliation JSON exported to %s",
                reconciliation_json,
            )
        else:
            logger.info(
                "No execution reconciliation audit found at %s.",
                config.execution_reconciliation_audit_path,
            )

    def shutdown(self) -> None:
        if not self._initialized:
            return
        logger.info("Shutting down platform...")
        self._initialized = False
        logger.info("Platform shutdown complete.")
