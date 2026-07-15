"""
Trading Pipeline models.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.confluence_engine.models import (
    ConfluenceResult,
)

from core.fair_value_gap_detector.models import (
    FairValueGapCandidate,
)

from core.feature_engineering.models import (
    FeatureVector,
)

from core.probability_engine.models import (
    ProbabilityResult,
)

from core.decision_engine.models import (
    DecisionResult,
)

from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
)

from core.order_block_detector.models import (
    OrderBlockCandidate,
)

from core.regime_detector.models import (
    MarketRegime,
)

from core.risk_manager.models import (
    TradePlan,
)

from core.signal_generator.models import (
    TradingSignal,
)


@dataclass(slots=True)
class PipelineResult:
    """
    Final result produced by the trading pipeline.

    Every stage of the pipeline contributes to this object.
    """

    # ==========================
    # Market Regime
    # ==========================

    regime: MarketRegime

    # ==========================
    # Market Structure
    # ==========================

    bos_event: BOSEvent | None = None

    choch_event: CHOCHEvent | None = None

    liquidity_event: LiquiditySweepEvent | None = None

    # ==========================
    # Smart Money Concepts
    # ==========================

    order_block: OrderBlockCandidate | None = None

    fair_value_gap: FairValueGapCandidate | None = None

    # ==========================
    # Feature Engineering
    # ==========================

    features: FeatureVector | None = None

    # ==========================
    # Probability & Decision
    # ==========================

    probability: ProbabilityResult | None = None

    decision: DecisionResult | None = None

    # ==========================
    # Decision Layer
    # ==========================

    confluence: ConfluenceResult | None = None

    signal: TradingSignal | None = None

    trade_plan: TradePlan | None = None

    # ==========================
    # Convenience Properties
    # ==========================

    @property
    def has_structure(
        self,
    ) -> bool:
        """
        True if any structural event exists.
        """

        return (
            self.bos_event is not None
            or self.choch_event is not None
        )

    @property
    def has_order_block(
        self,
    ) -> bool:
        """
        True if an Order Block exists.
        """

        return self.order_block is not None

    @property
    def has_fair_value_gap(
        self,
    ) -> bool:
        """
        True if a Fair Value Gap exists.
        """

        return self.fair_value_gap is not None

    @property
    def approved(
        self,
    ) -> bool:
        """
        Final pipeline approval.
        """

        if self.confluence is None:
            return False

        return self.confluence.approved