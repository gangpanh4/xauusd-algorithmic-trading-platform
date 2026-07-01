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
from .simulator import TradeSimulator


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

        self.simulator = TradeSimulator()

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

        for index, bar in enumerate(historical_bars):

            self.state.processed_bar_count += 1

            result = self.pipeline.process_bar(
                bar,
                account_balance=self.state.current_equity,
                stop_loss_distance=2.5,
                pip_value=1.0,
            )

            future_bars = historical_bars[index + 1 :]
            
            self._record_trade(
                result=result,
                entry_bar=bar,
                future_bars=future_bars,
            )

        return self._finalize()

    def _record_trade(
        self,
        result: PipelineResult,
        entry_bar: MarketBar,
        future_bars: list[MarketBar],
    ) -> None:
        """
        Record an approved trade.
        """

        trade_plan = result.trade_plan

        if trade_plan.decision != RiskDecision.APPROVE:
            return

        trade = self.simulator.simulate(
            trade_plan=trade_plan,
            entry_bar=entry_bar,
            future_bars=future_bars,
        )
        
        self.state.trades.append(trade)

        self.state.current_equity += trade.net_profit

        if self.state.current_equity > self.state.peak_equity:
            self.state.peak_equity = self.state.current_equity

        drawdown = (
            self.state.peak_equity
            - self.state.current_equity
        )

        if drawdown > self.state.max_drawdown:
            self.state.max_drawdown = drawdown

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

        wins = sum(
            trade.outcome.name == "WIN"
            for trade in self.state.trades
        )

        losses = sum(
            trade.outcome.name == "LOSS"
            for trade in self.state.trades
        )
            for trade in self.state.trades
        )

        breakeven = len(self.state.trades) - wins - losses

        net_profit = sum(
            trade.net_profit
            for trade in self.state.trades
        )

        gross_profit = sum(
            max(trade.net_profit, 0.0)
            for trade in self.state.trades
        )

        gross_loss = abs(
            sum(
                min(trade.net_profit, 0.0)
                for trade in self.state.trades
            )
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0.0
        )

        return BacktestResult(
            total_trades=len(self.state.trades),
            winning_trades=wins,
            losing_trades=losses,
            breakeven_trades=breakeven,
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            profit_factor=profit_factor,
            win_rate=(
                wins / len(self.state.trades) * 100
                if self.state.trades
                else 0.0
            ),
            max_drawdown=self.state.max_drawdown,
            trades=self.state.trades.copy(),
        )