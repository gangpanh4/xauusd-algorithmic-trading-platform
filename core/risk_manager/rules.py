"""
Risk evaluation rules for the Risk Management module.
"""

from __future__ import annotations

from .config import RiskManagerConfig


def approve_trade(
    *,
    position_size: float,
    risk_reward_ratio: float,
    config: RiskManagerConfig,
) -> tuple[bool, str]:
    """
    Evaluate whether a trade should be approved.
    """

    if position_size < config.minimum_position_size:
        return (
            False,
            "Position size below minimum.",
        )

    if position_size > config.maximum_position_size:
        return (
            False,
            "Position size above maximum.",
        )

    if (
        risk_reward_ratio
        < config.minimum_risk_reward_ratio
    ):
        return (
            False,
            "Risk/Reward ratio too low.",
        )

    return (
        True,
        "Trade approved.",
    )