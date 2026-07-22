"""
Configuration for the Trading Pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.confluence_engine.config import (
    ConfluenceEngineConfig,
)

from core.fair_value_gap_detector.config import (
    FairValueGapDetectorConfig,
)

from core.market_structure.config import (
    MarketStructureConfig,
)

from core.order_block_detector.config import (
    OrderBlockDetectorConfig,
)

from core.regime_detector.config import (
    RegimeDetectorConfig,
)

from core.risk_manager.config import (
    RiskManagerConfig,
)

from core.signal_generator.config import (
    SignalGeneratorConfig,
)


@dataclass(slots=True)
class TradingPipelineConfig:
    """
    Top-level configuration for the trading pipeline.

    Every engine receives its own configuration object.
    """

    # ======================================
    # Market Regime
    # ======================================

    regime_detector: RegimeDetectorConfig = field(
        default_factory=RegimeDetectorConfig
    )

    # ======================================
    # Market Structure
    # ======================================

    market_structure: MarketStructureConfig = field(
        default_factory=MarketStructureConfig
    )

    # ======================================
    # Signal Generation
    # ======================================

    signal_generator: SignalGeneratorConfig = field(
        default_factory=SignalGeneratorConfig
    )

    # ======================================
    # Smart Money Concepts
    # ======================================

    order_block_detector: OrderBlockDetectorConfig = field(
        default_factory=OrderBlockDetectorConfig
    )

    fair_value_gap_detector: FairValueGapDetectorConfig = field(
        default_factory=FairValueGapDetectorConfig
    )

    # ======================================
    # Confluence
    # ======================================

    confluence_engine: ConfluenceEngineConfig = field(
        default_factory=ConfluenceEngineConfig
    )

    # ======================================
    # Risk
    # ======================================

    risk_manager: RiskManagerConfig = field(
        default_factory=RiskManagerConfig
    )

    # ======================================
    # Debug
    # ======================================

    debug_logging: bool = False