"""
Win/Loss analysis models.

Captures the average feature values for winning and losing
trades and measures the separation between them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(
    slots=True,
    frozen=True,
)
class WinLossAnalysis:
    """
    Statistical comparison between winning and losing trades.
    """

    winning_probability: float
    losing_probability: float

    winning_structure: float
    losing_structure: float

    winning_liquidity: float
    losing_liquidity: float

    @property
    def probability_gap(
        self,
    ) -> float:
        """
        Difference between winning and losing probability.
        """

        return (
            self.winning_probability
            - self.losing_probability
        )

    @property
    def structure_gap(
        self,
    ) -> float:
        """
        Difference between winning and losing structure score.
        """

        return (
            self.winning_structure
            - self.losing_structure
        )

    @property
    def liquidity_gap(
        self,
    ) -> float:
        """
        Difference between winning and losing liquidity score.
        """

        return (
            self.winning_liquidity
            - self.losing_liquidity
        )