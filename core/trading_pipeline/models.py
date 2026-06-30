"""
Trading Pipeline models.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.regime_detector.models import (
    MarketRegime,
)

from core.signal_generator.models import (
    TradingSignal,
)

from core.risk_manager.models import (
    TradePlan,
)


@dataclass(frozen=True)
class PipelineResult:
    """
    Result returned by the Trading Pipeline.
    """

    regime: MarketRegime

    signal: TradingSignal

    trade_plan: TradePlan