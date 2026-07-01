"""
Position sizing calculations for the Risk Management module.
"""

from __future__ import annotations

import math


class PositionSizer:
    """
    Position sizing utilities.
    """

    MIN_LOT = 0.01
    LOT_STEP = 0.01

    @staticmethod
    def calculate_position_size(
        account_balance: float,
        risk_percent: float,
        stop_loss_distance: float,
        pip_value: float,
        *,
        minimum_lot: float = MIN_LOT,
        maximum_lot: float = 100.0,
        lot_step: float = LOT_STEP,
    ) -> float:
        """
        Risk-based position sizing.
        """

        if account_balance <= 0:
            return minimum_lot

        if risk_percent <= 0:
            return minimum_lot

        if stop_loss_distance <= 0:
            return minimum_lot

        if pip_value <= 0:
            return minimum_lot

        risk_amount = account_balance * risk_percent

        raw_lot = (
            risk_amount
            / (stop_loss_distance * pip_value)
        )

        raw_lot = max(
            minimum_lot,
            min(raw_lot, maximum_lot),
        )

        steps = math.floor(raw_lot / lot_step)

        lot = steps * lot_step

        return round(
            max(minimum_lot, lot),
            2,
        )

    @staticmethod
    def calculate_fixed_lot(
        lot_size: float,
    ) -> float:
        """
        Fixed lot mode.
        """

        return max(
            PositionSizer.MIN_LOT,
            round(lot_size, 2),
        )

    @staticmethod
    def calculate_dynamic_lot(
        balance: float,
        *,
        base_balance: float = 100.0,
        base_lot: float = 0.01,
        maximum_lot: float = 100.0,
    ) -> float:
        """
        Dynamic balance scaling.

        Examples
        --------
        $100  -> 0.01
        $200  -> 0.02
        $500  -> 0.05
        $1000 -> 0.10
        """

        if balance <= 0:
            return base_lot

        multiplier = balance / base_balance

        lot = base_lot * multiplier

        lot = min(
            lot,
            maximum_lot,
        )

        steps = math.floor(
            lot / PositionSizer.LOT_STEP
        )

        return round(
            max(
                PositionSizer.MIN_LOT,
                steps * PositionSizer.LOT_STEP,
            ),
            2,
        )

    @staticmethod
    def apply_broker_limits(
        lot: float,
        *,
        minimum: float,
        maximum: float,
        step: float,
    ) -> float:
        """
        Apply broker lot constraints.
        """

        lot = max(minimum, lot)

        lot = min(maximum, lot)

        steps = math.floor(lot / step)

        return round(
            steps * step,
            2,
        )