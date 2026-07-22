"""
Order Block quality analysis.
"""

from __future__ import annotations

from core.order_block_detector.models import (
    OrderBlock,
    OrderBlockAnalysis,
)


class OrderBlockAnalyzer:
    """
    Computes quality metrics for confirmed
    Order Blocks.

    Version 1 returns deterministic baseline
    scores. Future versions will incorporate
    displacement, liquidity, reaction,
    volume and confluence metrics.
    """

    def analyze(
        self,
        order_block: OrderBlock,
    ) -> OrderBlockAnalysis:
        """
        Analyze a confirmed Order Block.
        """

        structure_score = 1.0
        displacement_score = 1.0
        liquidity_score = 1.0
        reaction_score = 1.0

        total_score = (
            structure_score
            + displacement_score
            + liquidity_score
            + reaction_score
        ) / 4.0

        return OrderBlockAnalysis(
            structure_score=structure_score,
            displacement_score=displacement_score,
            liquidity_score=liquidity_score,
            reaction_score=reaction_score,
            total_score=total_score,
        )