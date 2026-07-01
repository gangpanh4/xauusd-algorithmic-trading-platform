"""
Historical Backtest Runner.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.trading_pipeline.pipeline import (
    TradingPipeline,
)

from .config import (
    BacktestConfig,
)

from .history_loader import (
    HistoryLoader,
)

from .state import (
    BacktestState,
)


class BacktestRunner:
    """
    Runs the trading pipeline over historical bars.
    """

    def __init__(
        self,
        config: BacktestConfig,
    ) -> None:

        self.config = config

        self.state = BacktestState()

        self.pipeline = TradingPipeline(
            self.config.pipeline,
        )

        self.loader = HistoryLoader()

    def run(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
    ) -> None:
        """
        Run the trading pipeline over historical data.
        """

        # Load historical data.
        history = self.loader.load_history(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
        )

        # TODO:
        # 1. Initialize/reset the runner state.
        # 2. Iterate through each historical bar.
        # 3. Feed each bar into the trading pipeline.
        # 4. Update the runner state.
        # 5. Collect statistics/results.

        for bar in history:

            result = self.pipeline.process_bar(
                bar,
                account_balance=self.config.initial_balance,
                stop_loss_distance=100.0,
                pip_value=1.0,
            )

            self.state.processed_bar_count += 1