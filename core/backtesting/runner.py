"""
Historical Backtest Runner.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from .candidate_outcome_exporter import CandidateOutcomeExporter
from .config import BacktestConfig
from .engine import BacktestingEngine
from .exporter import BacktestExporter
from .models import BacktestResult
from .multi_timeframe_loader import MultiTimeframeLoader
from .reporter import (
    print_report,
    save_report,
)
from .run_output import BacktestRunOutput
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

        self.candidate_outcome_exporter = CandidateOutcomeExporter(
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

        self._complete_state(
            processed_bar_count=len(context.m15_bars),
            executed_trade_count=result.total_trades,
        )

        return result

    def run_with_strategy_comparison(
        self,
        symbol: str,
        timeframe: int,
        bars: int,
    ) -> BacktestRunOutput:
        """Execute one backtest and return result plus strategy comparison.

        This additive entry point preserves :meth:`run` and its existing
        ``BacktestResult`` return contract.
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

        output = self.engine.run_with_strategy_comparison(context)

        self._complete_state(
            processed_bar_count=len(context.m15_bars),
            executed_trade_count=output.result.total_trades,
        )

        return output

    def _complete_state(
        self,
        *,
        processed_bar_count: int,
        executed_trade_count: int,
    ) -> None:
        """Publish one completed runner state consistently."""

        self.state.processed_bar_count = processed_bar_count
        self.state.executed_trade_count = executed_trade_count
        self.state.completed = True

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

        self.exporter.export_observation_audit(
            self.engine.observation_audits,
        )

        self.exporter.export_rejection_summary(
            self.engine.observation_audits,
        )

        self.exporter.export_equity_curve(
            result,
            self.config.initial_balance,
        )

        stats = self.statistics.calculate(result)

        self.exporter.export_statistics(
            asdict(stats),
        )

    def generate_composite_reports(
        self,
        output: BacktestRunOutput,
    ) -> None:
        """Generate execution, comparison, and candidate research artifacts."""

        if not isinstance(output, BacktestRunOutput):
            raise TypeError("output must be BacktestRunOutput")

        self.generate_reports(output.result)
        self.exporter.export_strategy_comparison_summary(
            output.strategy_comparison
        )
        self.exporter.export_strategy_comparison_events(
            output.strategy_comparison
        )
        has_candidate_outcome_research = bool(
            output.candidate_outcome_evaluations
            or output.candidate_outcome_summary
        )
        if has_candidate_outcome_research:
            self.candidate_outcome_exporter.export_summary(
                output.candidate_outcome_summary
            )
            self.candidate_outcome_exporter.export_evaluations(
                output.candidate_outcome_evaluations
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
