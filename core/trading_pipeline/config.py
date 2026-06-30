"""
Configuration for the Trading Pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core.regime_detector.config import (
    RegimeDetectorConfig,
)

from core.signal_generator.config import (
    SignalGeneratorConfig,
)

from core.risk_manager.config import (
    RiskManagerConfig,
)



@dataclass(frozen=True)
class TradingPipelineConfig:
    """
    Top-level configuration for the Trading Pipeline.
    """

    regime_detector: RegimeDetectorConfig = field(
        default_factory=RegimeDetectorConfig
    )

    signal_generator: SignalGeneratorConfig = field(
        default_factory=SignalGeneratorConfig
    )

    risk_manager: RiskManagerConfig = field(
        default_factory=RiskManagerConfig
    )

    debug_logging: bool = False