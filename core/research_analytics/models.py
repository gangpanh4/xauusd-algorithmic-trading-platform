"""
Research Analytics models.

These models capture the information associated with each completed
trade so that research and statistical analysis can be performed after
backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.feature_engineering.models import FeatureVector
from core.signal_generator.models import SignalDirection


@dataclass(
    slots=True,
    frozen=True,
)
class TradeAnalytics:
    """
    Analytics record for a completed trade.

    Each completed trade is converted into this structure so the
    Research Analytics Engine can evaluate strategy performance,
    compare winning and losing trades, and compute feature statistics.
    """

    timestamp: datetime

    direction: SignalDirection

    regime: str

    result: str

    profit: float

    probability: float

    confidence: float

    features: FeatureVector