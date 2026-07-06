"""
Platform Engine

Coordinates the lifecycle of the XAUUSD Algorithmic Trading Platform.

Responsibilities
----------------
- Platform initialization
- Configuration validation
- Execution mode orchestration
- Clean shutdown

This module intentionally contains no trading strategy logic.
"""

from __future__ import annotations

import logging

import MetaTrader5 as mt5

from core.backtesting.config import BacktestConfig
from core.backtesting.runner import BacktestRunner
from core.live_trading.config import LiveTradingConfig
from core.live_trading.engine import LiveTradingEngine

logger = logging.getLogger(__name__)


class TradingPlatform:
    """
    Top-level platform controller.

    This class coordinates platform execution while delegating
    all trading responsibilities to specialized modules.
    """

    def __init__(self) -> None:
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self) -> None:
        """
        Initialize the trading platform.
        """
        if self._initialized:
            logger.debug("Platform already initialized.")
            return

        logger.info("Initializing XAUUSD Trading Platform...")

        # Future:
        # - Load configuration
        # - Validate environment
        # - Initialize services

        self._initialized = True

        logger.info("Platform initialized successfully.")

    def run_backtest(self) -> None:
        """
        Execute the platform backtesting workflow.
        """

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
        """
        Execute the live trading workflow.
        """

        if not self._initialized:
            raise RuntimeError(
                "Platform has not been initialized."
            )

        logger.info("Starting Live Trading Platform...")

        config = LiveTradingConfig()

        engine = LiveTradingEngine(config)

        try:
            engine.start()

            logger.info(
                "Live Trading Engine started successfully."
            )

            logger.info(
                "Platform is ready to process market bars."
            )

            #
            # Future:
            #
            # while running:
            #     engine.process_bar(...)
            #

        finally:

            engine.stop()

            logger.info(
                "Live Trading Engine stopped."
            )

    def run_research(self) -> None:
        """
        Execute the research workflow.
        """
        logger.info("Running Research Mode...")

    def shutdown(self) -> None:
        """
        Shutdown the trading platform.
        """
        if not self._initialized:
            return

        logger.info("Shutting down platform...")

        self._initialized = False

        logger.info("Platform shutdown complete.")