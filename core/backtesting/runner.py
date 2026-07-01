"""
Historical Backtest Runner.
"""

from __future__ import annotations

import MetaTrader5 as mt5

from core.trading_pipeline.pipeline import TradingPipeline

from .config import BacktestConfig
from .engine import BacktestingEngine
from .history_loader import HistoryLoader
from .models import BacktestResult
from .state import BacktestState


class BacktestRunner:
    """
    Runs complete historical backtests.
    """

    def __init__(
        self,
        config: BacktestConfig,
    ) -> None:

        self.config = config

        self.state = BacktestState()

        self.loader = HistoryLoader()

        self.pipeline = TradingPipeline(
            self.config.pipeline,
        )

        self.engine = BacktestingEngine(
            self.config,
        )

    def run(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
    ) -> BacktestResult:
        """
        Execute a complete historical backtest.
        """

        self.state.reset()

        history = self.loader.load_history(
            symbol=symbol,
            timeframe=timeframe,
            bars=bars,
        )

        if not history:
            raise RuntimeError(
                "No historical data returned."
            )

        result = self.engine.run(history)

        self.state.processed_bar_count = len(history)
        self.state.executed_trade_count = result.total_trades
        self.state.completed = True

        return result

    def print_summary(
        self,
        result: BacktestResult,
    ) -> None:

        print()
        print("=" * 70)
        print("BACKTEST SUMMARY")
        print("=" * 70)

        print(f"Trades           : {result.total_trades}")
        print(f"Wins             : {result.winning_trades}")
        print(f"Losses           : {result.losing_trades}")
        print(f"Breakeven        : {result.breakeven_trades}")

        print()

        print(f"Win Rate         : {result.win_rate:.2f}%")
        print(f"Net Profit       : {result.net_profit:.2f}")
        print(f"Gross Profit     : {result.gross_profit:.2f}")
        print(f"Gross Loss       : {result.gross_loss:.2f}")
        print(f"Profit Factor    : {result.profit_factor:.2f}")
        print(f"Max Drawdown     : {result.max_drawdown:.2f}")

        print("=" * 70)

    def print_trade_log(
        self,
        result: BacktestResult,
    ) -> None:

        print()
        print("=" * 70)
        print("TRADE LOG")
        print("=" * 70)

        for i, trade in enumerate(result.trades, start=1):

            print(
                f"{i:03d} | "
                f"{trade.direction:<4} | "
                f"{trade.entry_price:.2f} -> "
                f"{trade.exit_price:.2f} | "
                f"{trade.net_profit:.2f} | "
                f"{trade.outcome.name}"
            )