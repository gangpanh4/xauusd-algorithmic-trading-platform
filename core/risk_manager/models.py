"""
Core data models for the Risk Management module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

from core.signal_generator.models import TradingSignal


class RiskDecision(Enum):
    """
    Final decision produced by the Risk Manager.
    """
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    SKIP = "SKIP"


@dataclass(frozen=True)
class TradePlan:
    timestamp: datetime

    signal: TradingSignal

    decision: RiskDecision

    # Position
    position_size: float

    # Execution prices
    entry_price: float

    stop_loss_price: float

    take_profit_price: float

    # Risk information
    risk_percent: float

    reward_percent: float

    risk_reward_ratio: float

    reason: str

    metadata: dict[str, Any] = field(default_factory=dict)