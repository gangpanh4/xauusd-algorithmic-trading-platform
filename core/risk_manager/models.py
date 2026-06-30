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
    """
    Complete trade execution plan produced by the Risk Manager.
    """

    timestamp: datetime

    signal: TradingSignal

    decision: RiskDecision

    position_size: float

    stop_loss: float

    take_profit: float

    risk_percent: float

    reward_percent: float

    risk_reward_ratio: float

    reason: str

    metadata: dict[str, Any] = field(default_factory=dict)