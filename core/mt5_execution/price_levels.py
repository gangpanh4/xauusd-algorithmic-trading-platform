"""
Price level calculations for MT5 execution.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import OrderSide


@dataclass(frozen=True)
class PriceLevels:
    """
    Calculated stop-loss and take-profit levels.
    """

    stop_loss: float

    take_profit: float


def calculate_price_levels(
    *,
    entry_price: float,
    side: OrderSide,
    stop_loss_distance: float,
    risk_reward_ratio: float,
) -> PriceLevels:
    """
    Calculate stop-loss and take-profit levels.
    """

    take_profit_distance = (
        stop_loss_distance * risk_reward_ratio
    )

    if side is OrderSide.BUY:

        return PriceLevels(
            stop_loss=(
                entry_price - stop_loss_distance
            ),
            take_profit=(
                entry_price + take_profit_distance
            ),
        )

    return PriceLevels(
        stop_loss=(
            entry_price + stop_loss_distance
        ),
        take_profit=(
            entry_price - take_profit_distance
        ),
    )