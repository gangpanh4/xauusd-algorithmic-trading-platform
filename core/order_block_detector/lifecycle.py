"""
Order Block lifecycle management.
"""

from __future__ import annotations

from core.order_block_detector.models import (
    OrderBlock,
)


class OrderBlockLifecycle:
    """
    Handles runtime lifecycle transitions for Order Blocks.

    Version 1 only exposes the lifecycle interface.
    Full mitigation, invalidation and expiration logic
    will be implemented in later versions.
    """

    def is_active(
        self,
        order_block: OrderBlock,
    ) -> bool:
        """
        Return whether an Order Block should be
        considered active.

        Version 1 always returns True.
        """

        return True

    def is_mitigated(
        self,
        order_block: OrderBlock,
    ) -> bool:
        """
        Return whether an Order Block has been
        mitigated.

        Version 1 always returns False.
        """

        return False

    def is_invalidated(
        self,
        order_block: OrderBlock,
    ) -> bool:
        """
        Return whether an Order Block has been
        invalidated.

        Version 1 always returns False.
        """

        return False

    def is_expired(
        self,
        order_block: OrderBlock,
    ) -> bool:
        """
        Return whether an Order Block has expired.

        Version 1 always returns False.
        """

        return False