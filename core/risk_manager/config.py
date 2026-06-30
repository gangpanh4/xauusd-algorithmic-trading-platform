"""
Configuration models for the Risk Management module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskManagerConfig:
    """
    Configuration for the Risk Management module.
    """

    max_risk_per_trade: float = 0.01

    max_daily_loss: float = 0.03

    minimum_risk_reward_ratio: float = 2.0

    maximum_open_positions: int = 3

    allow_multiple_positions: bool = False

    minimum_position_size: float = 0.01

    maximum_position_size: float = 10.00

    debug_logging: bool = False