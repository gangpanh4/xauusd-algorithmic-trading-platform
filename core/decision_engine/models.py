"""
Decision Engine models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class DecisionType(Enum):
    """
    Final trading decision produced by the Decision Engine.
    """

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(slots=True, frozen=True)
class DecisionResult:
    """
    Quantitative decision produced by the Decision Engine.

    This object represents the final decision after combining
    market regime, confluence analysis, and future decision
    policies.

    It intentionally contains no execution or risk-management
    information.
    """

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC)
    )

    decision: DecisionType = DecisionType.HOLD

    approved: bool = False

    confidence: float = 0.0

    decision_score: float = 0.0

    regime_confidence: float = 0.0

    confluence_score: float = 0.0