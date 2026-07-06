"""
Historical Backtest Runner.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .config import BacktestConfig
from .engine import BacktestingEngine
from .exporter import BacktestExporter
from .models import BacktestResult
from .multi_timeframe_loader import MultiTimeframeLoader
from .reporter import (
    print_report,
    save_report,
)
from .state import BacktestState
from .statistics import StatisticsCalculator


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

        self.loader = MultiTimeframeLoader()

        self.engine = BacktestingEngine(
            config,
        )

        self.exporter = BacktestExporter(
            config.output_directory,
        )

        self.statistics = StatisticsCalculator()

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

        context = self.loader.load(
            symbol=symbol,
            bars=bars,
        )

        if not context.m15_bars:
            raise RuntimeError(
                "No historical data returned."
            )

        result = self.engine.run(context)

        self.state.processed_bar_count = len(
            context.m15_bars
        )
        self.state.executed_trade_count = (
            result.total_trades
        )
        self.state.completed = True

        return result

    def generate_reports(
        self,
        result: BacktestResult,
    ) -> None:
        """
        Generate all Sprint 1 reports.
        """

        output_dir = Path(
            self.config.output_directory,
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print_report(result)

        save_report(
            result,
            output_dir / "backtest_report.txt",
        )

        self.exporter.export_summary(result)

        self.exporter.export_trade_log(result)

        self.exporter.export_equity_curve(
            result,
            self.config.initial_balance,
        )

        stats = self.statistics.calculate(result)

        self.exporter.export_statistics(
            asdict(stats),
        )

    def print_trade_log(
        self,
        result: BacktestResult,
    ) -> None:

        print()
        print("=" * 70)
        print("TRADE LOG")
        print("=" * 70)

        for index, trade in enumerate(
            result.trades,
            start=1,
        ):

            print(
                f"{index:03d} | "
                f"{trade.direction:<4} | "
                f"{trade.entry_price:.2f} -> "
                f"{trade.exit_price:.2f} | "
                f"{trade.net_profit:.2f} | "
                f"{trade.outcome.name}"
            )