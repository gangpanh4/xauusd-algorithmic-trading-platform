from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from core.backtesting.engine import BacktestingEngine
from core.backtesting.models import BacktestResult
from core.research.models import (
    Experiment,
    ExperimentResult,
)


@dataclass(slots=True)
class ExperimentRunner:
    """
    Runs a single quantitative research experiment.

    Responsibilities
    ----------------
    - Execute one backtest
    - Collect performance statistics
    - Produce an ExperimentResult

    This class intentionally contains no trading logic.
    """

    backtesting_engine: BacktestingEngine

    def run(
        self,
        experiment: Experiment,
        backtest_callable: Callable[[], BacktestResult],
    ) -> ExperimentResult:
        """
        Execute one experiment.

        Parameters
        ----------
        experiment
            Experiment definition.

        backtest_callable
            Function that executes one complete backtest.

        Returns
        -------
        ExperimentResult
        """

        started = datetime.now(UTC)

        result = backtest_callable()

        finished = datetime.now(UTC)

        metadata = {
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": (
                finished - started
            ).total_seconds(),
        }

        return ExperimentResult(
            experiment_id=experiment.experiment_id,
            trades=result.total_trades,
            wins=result.wins,
            losses=result.losses,
            breakeven=result.breakeven,
            win_rate=result.win_rate,
            net_profit=result.net_profit,
            gross_profit=result.gross_profit,
            gross_loss=result.gross_loss,
            profit_factor=result.profit_factor,
            expectancy=result.expectancy,
            sharpe_ratio=getattr(result, "sharpe_ratio", 0.0),
            sortino_ratio=getattr(result, "sortino_ratio", 0.0),
            max_drawdown=result.max_drawdown,
            average_trade=result.average_trade,
            average_win=result.average_win,
            average_loss=result.average_loss,
            largest_win=result.largest_win,
            largest_loss=result.largest_loss,
            metadata=metadata,
        )