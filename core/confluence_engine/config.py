"""
Configuration for the Confluence Engine.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ConfluenceEngineConfig:
    """
    Configuration controlling confluence scoring.

    Each weight contributes to the final score.
    The sum of all weights is used as the maximum score.
    """

    liquidity_weight: float = 20.0

    bos_weight: float = 15.0

    choch_weight: float = 10.0

    order_block_weight: float = 25.0

    fair_value_gap_weight: float = 20.0

    trend_weight: float = 10.0

    minimum_approval_score: float = 70.0

    debug_logging: bool = False

    @property
    def maximum_score(
        self,
    ) -> float:
        """
        Return the total achievable score.
        """

        return (
            self.liquidity_weight
            + self.bos_weight
            + self.choch_weight
            + self.order_block_weight
            + self.fair_value_gap_weight
            + self.trend_weight
        )