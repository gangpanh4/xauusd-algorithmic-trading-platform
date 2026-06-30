"""
Backtesting Engine.
"""

from __future__ import annotations

from datetime import datetime, UTC

from .config import BacktestConfig
from .models import (
    BacktestResult,
)
from .state import BacktestState


class BacktestingEngine:
    """
    Executes historical backtests.
    """

    def __init__(
        self,
        config: BacktestConfig,
    ) -> None:

        self.config = config

        self.state = BacktestState()

    def reset(self) -> None:
        self.state.reset()

    def run(self) -> BacktestResult:
        """
        Execute the backtest.
        """

        self._initialize()

        #
        # Historical replay will be added here.
        #

        return self._finalize()

    def _initialize(self) -> None:
        """
        Prepare the engine.
        """

        self.state.reset()

        self.state.initialized = True

        self.state.running = True

        self.state.start_time = datetime.now(UTC)

        self.state.current_equity = (
            self.config.initial_balance
        )

        self.state.peak_equity = (
            self.config.initial_balance
        )

    def _finalize(self) -> BacktestResult:
        """
        Finish the simulation.
        """

        self.state.running = False

        self.state.completed = True

        self.state.end_time = datetime.now(UTC)

        return BacktestResult(
            total_trades=len(self.state.trades),
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            net_profit=0.0,
            win_rate=0.0,
            max_drawdown=self.state.max_drawdown,
            trades=self.state.trades.copy(),
        )