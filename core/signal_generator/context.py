"""
Signal Generator Context.

Carries all information required to generate
a trading signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.confluence_engine.models import ConfluenceResult
from core.decision_engine.models import DecisionResult
from core.probability_engine.models import ProbabilityResult
from core.regime_detector.models import MarketRegime
from core.trade_quality.models import TradeQuality


@dataclass(slots=True)
class SignalContext:
    """
    Complete context for signal generation.

    New fields should be added here as the
    platform grows rather than expanding
    generate_signal() arguments.
    """

    regime: MarketRegime

    probability: ProbabilityResult | None = None

    trade_quality: TradeQuality | None = None

    decision: DecisionResult | None = None

    confluence: ConfluenceResult | None = None