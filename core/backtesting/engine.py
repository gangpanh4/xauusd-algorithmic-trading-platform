"""
Backtesting Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.regime_detector.models import (
    MarketBar,
)
from core.risk_manager.models import (
    RiskDecision,
)
from core.trading_pipeline.config import (
    TradingPipelineConfig,
)
from core.trading_pipeline.models import (
    PipelineResult,
)
from core.trading_pipeline.pipeline import (
    TradingPipeline,
)

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

        self.pipeline = TradingPipeline(
            TradingPipelineConfig(),
        )

    def reset(self) -> None:
        self.state.reset()

    def run(
        self,
        historical_bars: list[MarketBar],
    ) -> BacktestResult:
        """
        Execute the backtest.
        """

        self._initialize()

        for bar in historical_bars:

            self.state.processed_bar_count += 1

            result = self.pipeline.process_bar(
                bar,
                account_balance=self.state.current_equity,
                stop_loss_distance=2.5,
                pip_value=1.0,
            )

            self._record_trade(result)

        return self._finalize()

    def _record_trade(
        self,
        result: PipelineResult,
    ) -> None:
        """
        Record an approved trade.
        """

        trade_plan = result.trade_plan

        if trade_plan.decision != RiskDecision.APPROVE:
            return

        self.state.trades.append(trade_plan)

        self.state.executed_trade_count += 1

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