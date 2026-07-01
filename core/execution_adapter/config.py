"""
Configuration for the Execution Adapter.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionAdapterConfig:
    """
    Configuration options.
    """

    default_comment: str = (
        "XAUUSD Platform v3.2"
    )

    risk_reward_ratio: float = 2.0

    stop_loss_distance: float = 2.0