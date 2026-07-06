"""
Trading Pipeline orchestrator.
"""

from __future__ import annotations

from core.regime_detector.detector import (
    MarketRegimeDetector,
)

from core.regime_detector.models import (
    MarketBar,
)

from core.signal_generator.detector import (
    SignalGenerator,
)

from core.intelligence.edge.opportunity_ranker import (
    OpportunityRanker,
)

from core.risk_manager.manager import (
    RiskManager,
)

from .config import TradingPipelineConfig
from .models import PipelineResult


class TradingPipeline:
    """
    Coordinates the complete trading workflow.

    Responsibilities:
        1. Determine market regime.
        2. Generate a trading signal.
        3. Build a TradePlan through the Risk Manager.
        4. Return the complete PipelineResult.

    The TradingPipeline owns the market entry price because it
    processes the current completed MarketBar.
    """

    def __init__(
        self,
        config: TradingPipelineConfig,
    ) -> None:

        self.config = config

        self.regime_detector = MarketRegimeDetector(
            config.regime_detector,
        )

        self.opportunity_ranker = OpportunityRanker()

        self.signal_generator = SignalGenerator(
            config.signal_generator,
            self.opportunity_ranker,
        )

        self.risk_manager = RiskManager(
            config.risk_manager,
        )

    def process_bar(
        self,
        bar: MarketBar,
        *,
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> PipelineResult:
        """
        Process one completed market bar through the trading pipeline.
        """

        regime = self.regime_detector.process_bar(
            bar,
        )

        # Temporary debug instrumentation
        count = self.regime_detector.state.processed_bar_count

        if count % 5000 == 0:
            print("\n========== REGIME DEBUG ==========")
            print(f"Processed Bars : {count}")
            print(f"Primary Regime : {regime.primary_regime}")
            print(f"Confidence     : {regime.confidence}")
            print("==================================")

        signal = self.signal_generator.generate_signal(
            regime,
        )

        if regime.confidence >= 0.90:
            print("\n========== SIGNAL DEBUG ==========")
            print(f"Regime      : {regime.primary_regime}")
            print(f"Confidence  : {regime.confidence}")
            print(f"Signal      : {signal.signal}")
            print("==================================")

        trade_plan = self.risk_manager.evaluate_signal(
            signal=signal,
            entry_price=bar.close,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
        )

        if regime.confidence >= 0.90:
            print(f"Risk Decision : {trade_plan.decision}")
            print(f"Reason        : {trade_plan.reason}")
            print("==================================")

        return PipelineResult(
            regime=regime,
            signal=signal,
            trade_plan=trade_plan,
        )