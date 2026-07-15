"""
Order Block repository.

Provides an in-memory repository for confirmed
Order Blocks.
"""

from __future__ import annotations

from core.order_block_detector.models import (
    OrderBlock,
)


class OrderBlockRepository:
    """
    Stores confirmed Order Blocks.
    """

    def __init__(self) -> None:
        self._order_blocks: list[OrderBlock] = []

    def add(
        self,
        order_block: OrderBlock,
    ) -> None:
        """
        Store a confirmed Order Block.
        """

        self._order_blocks.append(order_block)

    def get_all(
        self,
    ) -> list[OrderBlock]:
        """
        Return all stored Order Blocks.
        """

        return list(self._order_blocks)

    def clear(
        self,
    ) -> None:
        """
        Remove every stored Order Block.
        """

        self._order_blocks.clear()

    def count(
        self,
    ) -> int:
        """
        Return the number of stored Order Blocks.
        """

        return len(self._order_blocks)