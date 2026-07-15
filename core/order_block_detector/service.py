"""
Order Block application service.
"""

from __future__ import annotations

from core.order_block_detector.analyzer import (
    OrderBlockAnalyzer,
)
from core.order_block_detector.lifecycle import (
    OrderBlockLifecycle,
)
from core.order_block_detector.models import (
    OrderBlock,
    OrderBlockAnalysis,
)
from core.order_block_detector.repository import (
    OrderBlockRepository,
)


class OrderBlockService:
    """
    High-level service for managing confirmed Order Blocks.
    """

    def __init__(
        self,
        repository: OrderBlockRepository | None = None,
        analyzer: OrderBlockAnalyzer | None = None,
        lifecycle: OrderBlockLifecycle | None = None,
    ) -> None:
        self.repository = repository or OrderBlockRepository()
        self.analyzer = analyzer or OrderBlockAnalyzer()
        self.lifecycle = lifecycle or OrderBlockLifecycle()

    def add(
        self,
        order_block: OrderBlock,
    ) -> OrderBlockAnalysis:
        """
        Analyze and store an Order Block.
        """

        analysis = self.analyzer.analyze(order_block)

        self.repository.add(order_block)

        return analysis

    def get_all(
        self,
    ) -> list[OrderBlock]:
        """
        Return all stored Order Blocks.
        """

        return self.repository.get_all()

    def count(
        self,
    ) -> int:
        """
        Return the number of stored Order Blocks.
        """

        return self.repository.count()

    def clear(
        self,
    ) -> None:
        """
        Remove all stored Order Blocks.
        """

        self.repository.clear()