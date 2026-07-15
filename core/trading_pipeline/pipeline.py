"""
Trading Pipeline orchestrator.
"""

from __future__ import annotations

from collections.abc import Mapping

from core.multi_timeframe.enums import Timeframe

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

from core.multi_timeframe.coordinator import (
    MultiTimeframeCoordinator,
)

from core.market_structure.engine import (
    MarketStructureEngine,
)

from core.confluence_engine.engine import (
    ConfluenceEngine,
)

from core.decision_engine.engine import (
    DecisionEngine,
)

from core.feature_engineering.engine import (
    FeatureEngineeringEngine,
)

from core.probability_engine.engine import (
    ProbabilityEngine,
)

from core.feature_engineering.evidence import (
    FeatureEvidence,
)

from core.confluence_engine.models import (
    ConfluenceResult,
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

        #
        # Phase 2 Architecture
        #

        self.multi_timeframe = MultiTimeframeCoordinator()

        self.market_structure = MarketStructureEngine()

        self.confluence_engine = ConfluenceEngine()

        self.feature_engineering = FeatureEngineeringEngine()

        self.probability_engine = ProbabilityEngine()

        self.decision_engine = DecisionEngine()

    def process(
        self,
        *,
        bars_by_timeframe: Mapping[
            Timeframe,
            list[MarketBar],
        ],
        account_balance: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> PipelineResult:
        """
        Version 2 processing entry point.

        Currently delegates to the existing V1 pipeline while the
        remaining subsystems are being integrated.

        Future versions will execute:

            MultiTimeframe
                ↓
            Confluence
                ↓
            Regime
                ↓
            Signal
                ↓
            Risk
        """

        #
        # Version 2 Analysis
        #

        mtf_result = self.multi_timeframe.process(
            bars_by_timeframe,
        )

        #
        # Execute Version 2 confluence analysis.
        #
        # The result is intentionally not yet used to influence
        # trading decisions. This commit verifies subsystem
        # integration while preserving Version 1 behaviour.
        #

        confluence = (
            self.confluence_engine.evaluate_multi_timeframe(
                mtf_result,
            )
        )

        #
        # Temporary compatibility bridge.
        #

        current_bars = bars_by_timeframe[
            Timeframe.M5
        ]

        #
        # Keep the variable alive until Pipeline V2 begins
        # consuming the confluence result.
        #

        _ = confluence

        return self.process_bar(
            current_bars[-1],
            confluence=confluence,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,
        )

    def process_bar(
        self,
        bar: MarketBar,
        *,
        confluence: ConfluenceResult | None = None,
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

        market_structure = self.market_structure.process(
            bar,
        )

        

        feature_evidence = self.feature_engineering.create_evidence(
            market_structure=market_structure,
            regime=regime,
        )

        

        feature_vector = self.feature_engineering.process(
            feature_evidence,
        )

        

        probability = self.probability_engine.process(
            feature_vector,
        )

        

        

        decision = self.decision_engine.evaluate(
            regime=regime,
            confluence=confluence,
            probability=probability,
        )

        signal = self.signal_generator.generate_signal(
            regime,
            confluence=confluence,
        )

        

        trade_plan = self.risk_manager.evaluate_signal(
            signal=signal,
            entry_price=bar.close,
            account_balance=account_balance,
            stop_loss_distance=stop_loss_distance,
            pip_value=pip_value,

            # ----------------------------------
            # Research 005 Observability
            # ----------------------------------

            probability=probability.probability,
            confidence=probability.confidence,
            feature_count=feature_vector.size,
            evidence_count=len(probability.evidence),
            regime=str(regime.primary_regime),
        )

        

        return PipelineResult(
            regime=regime,
            features=feature_vector,
            probability=probability,
            decision=decision,
            signal=signal,
            trade_plan=trade_plan,
        )