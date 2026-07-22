"""
Configuration models for the Risk Management module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LotSizingMode(Enum):
    """
    Position sizing modes.
    """

    FIXED = "FIXED"
    DYNAMIC = "DYNAMIC"
    RISK_PERCENT = "RISK_PERCENT"


@dataclass(frozen=True)
class RiskManagerConfig:
    """
    Configuration for the Risk Management module.
    """

    # =============================
    # Risk Limits
    # =============================

    max_risk_per_trade: float = 0.01

    max_daily_loss: float = 0.03

    minimum_risk_reward_ratio: float = 2.0

    maximum_open_positions: int = 3

    allow_multiple_positions: bool = False

    # =============================
    # Position Size Limits
    # =============================

    minimum_position_size: float = 0.01

    maximum_position_size: float = 10.00

    # =============================
    # Lot Size Mode
    # =============================

    lot_sizing_mode: LotSizingMode = LotSizingMode.FIXED

    fixed_lot_size: float = 0.01

    risk_percent: float = 1.0

    # =============================
    # Virtual Trading Account
    # =============================

    use_virtual_balance: bool = False

    virtual_balance: float = 100.0

    dynamic_virtual_balance: bool = False

    # =============================
    # Trading Costs
    # =============================

    include_spread: bool = True

    spread_points: float = 0.0

    include_commission: bool = True

    commission_per_lot: float = 0.0

    slippage_points: float = 0.0

    # =============================
    # Safety
    # =============================

    emergency_stop_balance: float = 0.0

    stop_after_daily_loss: bool = True

    # =============================
    # Logging
    # =============================

    debug_logging: bool = False