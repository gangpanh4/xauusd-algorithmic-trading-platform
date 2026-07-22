"""Platform Engine."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

import MetaTrader5 as mt5

from core.backtesting.config import BacktestConfig
from core.backtesting.runner import BacktestRunner
from core.data.market_data import MarketDataService
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine
from core.live_trading.multi_timeframe_buffer import LiveMultiTimeframeBuffer
from core.mt5_execution.symbol_specification import (
    get_live_symbol_specification,
)
from core.multi_timeframe.enums import Timeframe

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
            config = BacktestConfig()
            runner = BacktestRunner(config)
            result = runner.run(
                symbol="XAUUSD",
                timeframe=mt5.TIMEFRAME_M15,
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
        config = LiveTradingConfig()
        engine = LiveTradingEngine(config)
        mt5_started = False

        services = {
            Timeframe.M5: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_M5,
            ),
            Timeframe.M15: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_M15,
            ),
            Timeframe.H1: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_H1,
            ),
            Timeframe.H4: MarketDataService(
                symbol=config.symbol,
                timeframe=mt5.TIMEFRAME_H4,
            ),
        }
        buffer = LiveMultiTimeframeBuffer(
            window_bars=config.history_window_bars,
        )

        try:
            # Market data requires an MT5 terminal connection even when order
            # execution is disabled.
            if not mt5.initialize():
                raise RuntimeError(
                    f"MT5 initialization failed: {mt5.last_error()}"
                )
            mt5_started = True
            engine.start()

            logger.info("Loading synchronized historical bars...")
            for timeframe, service in services.items():
                history = service.get_historical_bars(
                    config.history_window_bars,
                )
                if not history:
                    raise RuntimeError(
                        f"No completed {timeframe.value} history available."
                    )
                buffer.load(timeframe, history)

            account = mt5.account_info()
            if account is None:
                raise RuntimeError("Unable to retrieve account information.")

            symbol_spec = get_live_symbol_specification(config.symbol)
            logger.info(
                "Loaded %s risk specification: tick_size=%s "
                "tick_value_per_lot=%s lot_step=%s minimum_stop=%s",
                symbol_spec.symbol,
                symbol_spec.tick_size,
                symbol_spec.tick_value_per_lot,
                symbol_spec.lot_step,
                symbol_spec.minimum_stop_distance,
            )

            logger.info("Warming up synchronized analytical state...")
            for m5_bar in buffer.histories[Timeframe.M5]:
                boundary = m5_bar.timestamp + timedelta(minutes=5)
                snapshot = buffer.snapshot(boundary)
                if snapshot is None:
                    engine.process_bar(
                        m5_bar,
                        account_balance=account.balance,
                        stop_loss_distance=(
                            symbol_spec.minimum_stop_distance
                        ),
                        pip_value=symbol_spec.tick_value_per_lot,
                        warmup=True,
                    )
                    continue

                engine.process_multi_timeframe(
                    snapshot,
                    account_balance=account.balance,
                    stop_loss_distance=symbol_spec.minimum_stop_distance,
                    pip_value=symbol_spec.tick_value_per_lot,
                    tick_size=symbol_spec.tick_size,
                    lot_step=symbol_spec.lot_step,
                    warmup=True,
                )

            logger.info("Warm-up completed. Waiting for completed M5 bars.")

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

                    account = mt5.account_info()
                    if account is None:
                        logger.warning(
                            "Unable to retrieve account information."
                        )
                        time.sleep(config.poll_interval_seconds)
                        continue

                    engine.process_multi_timeframe(
                        snapshot,
                        account_balance=account.balance,
                        stop_loss_distance=(
                            symbol_spec.minimum_stop_distance
                        ),
                        pip_value=symbol_spec.tick_value_per_lot,
                        tick_size=symbol_spec.tick_size,
                        lot_step=symbol_spec.lot_step,
                    )
                    time.sleep(config.poll_interval_seconds)

            except KeyboardInterrupt:
                logger.info("Stopping live trading...")

        finally:
            engine.stop()
            if mt5_started:
                mt5.shutdown()
            logger.info("Live Trading Engine stopped.")

    def run_research(self) -> None:
        logger.info("Running Research Mode...")

    def shutdown(self) -> None:
        if not self._initialized:
            return
        logger.info("Shutting down platform...")
        self._initialized = False
        logger.info("Platform shutdown complete.")
