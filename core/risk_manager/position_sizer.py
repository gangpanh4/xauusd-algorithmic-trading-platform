"""
Position sizing calculations for the Risk Management module.
"""

from __future__ import annotations


class PositionSizer:
    """
    Calculates the position size based on account balance and risk.
    """

    @staticmethod
    def calculate_position_size(
        account_balance: float,
        risk_percent: float,
        stop_loss_distance: float,
        pip_value: float,
    ) -> float:
        """
        Calculate the position size.

        Parameters
        ----------
        account_balance:
            Current account balance.

        risk_percent:
            Fraction of balance to risk (e.g. 0.01 for 1%).

        stop_loss_distance:
            Distance from entry to stop loss in points/pips.

        pip_value:
            Monetary value of one pip for one lot.
        """

        if account_balance <= 0.0:
            raise ValueError("Account balance must be positive.")

        if risk_percent <= 0.0:
            raise ValueError("Risk percent must be positive.")

        if stop_loss_distance <= 0.0:
            raise ValueError("Stop-loss distance must be positive.")

        if pip_value <= 0.0:
            raise ValueError("Pip value must be positive.")

        risk_amount = (
            account_balance
            * risk_percent
        )

        return risk_amount / (
            stop_loss_distance
            * pip_value
        )