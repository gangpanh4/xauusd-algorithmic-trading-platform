"""
Order Block statistics.
"""

from __future__ import annotations

from core.market_structure.enums import (
    OrderBlockType,
)
from core.order_block_detector.models import (
    OrderBlock,
)


class OrderBlockStatistics:
    """
    Computes simple statistics for Order Blocks.
    """

    def total_blocks(
        self,
        order_blocks: list[OrderBlock],
    ) -> int:
        """
        Return the total number of Order Blocks.
        """

        return len(order_blocks)

    def bullish_blocks(
        self,
        order_blocks: list[OrderBlock],
    ) -> int:
        """
        Return the number of bullish Order Blocks.
        """

        return sum(
            block.block_type is OrderBlockType.BULLISH
            for block in order_blocks
        )

    def bearish_blocks(
        self,
        order_blocks: list[OrderBlock],
    ) -> int:
        """
        Return the number of bearish Order Blocks.
        """

        return sum(
            block.block_type is OrderBlockType.BEARISH
            for block in order_blocks
        )