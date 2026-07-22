"""
Core data models for the Trade Quality module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class QualityLevel(Enum):
    """
    Overall quality classification.
    """

    REJECTED = "REJECTED"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    EXCELLENT = "EXCELLENT"


class QualityReason(Enum):
    """
    Standardized quality explanations.
    """

    STRONG_TREND = "Strong Trend"
    WEAK_TREND = "Weak Trend"

    HIGH_MOMENTUM = "High Momentum"
    LOW_MOMENTUM = "Low Momentum"

    GOOD_VOLATILITY = "Good Volatility"
    LOW_VOLATILITY = "Low Volatility"

    EXCELLENT_RISK_REWARD = "Excellent Risk Reward"
    POOR_RISK_REWARD = "Poor Risk Reward"

    HIGH_CONFIDENCE = "High Confidence"
    LOW_CONFIDENCE = "Low Confidence"

    REGIME_CONFIRMED = "Regime Confirmed"
    REGIME_UNCERTAIN = "Regime Uncertain"

    PASSED = "Passed Trade Quality Filter"
    REJECTED = "Rejected by Trade Quality Filter"


@dataclass(
    slots=True,
)
class TradeQuality:
    """
    Complete evaluation of a trading opportunity.

    This object becomes the contract between
    Signal Generator -> Trade Quality -> Risk Manager.
    """

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    score: float = 0.0

    level: QualityLevel = QualityLevel.REJECTED

    approved: bool = False

    confidence: float = 0.0

    reasons: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def rejected(self) -> bool:
        return not self.approved

    def add_reason(
        self,
        reason: QualityReason | str,
    ) -> None:
        """
        Add a human-readable explanation.
        """

        text = (
            reason.value
            if isinstance(reason, QualityReason)
            else reason
        )
        if text not in self.reasons:
            self.reasons.append(text)