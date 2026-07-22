"""
Core data models for the Risk Management module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from core.signal_generator.models import TradingSignal


class RiskDecision(Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SKIP = "SKIP"


@dataclass
class TradePlan:
    # Optional for backward compatibility
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    signal: TradingSignal | None = None

    decision: RiskDecision = RiskDecision.SKIP

    # Position
    position_size: float = 0.0

    # Prices
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0

    # Risk
    risk_percent: float = 0.0
    reward_percent: float = 0.0
    risk_reward_ratio: float = 0.0

    reason: str = ""

    metadata: dict[str, Any] = field(default_factory=dict)

    # ==========================
    # Research 004
    # Trade quality snapshot
    # ==========================

    probability: float | None = None

    confidence: float | None = None

    # ==========================
    # Research 005
    # Trade observability
    # ==========================

    feature_count: int | None = None

    evidence_count: int | None = None

    regime: str | None = None

    @property
    def stop_loss_price(self) -> float:
        return self.stop_loss

    @property
    def take_profit_price(self) -> float:
        return self.take_profit