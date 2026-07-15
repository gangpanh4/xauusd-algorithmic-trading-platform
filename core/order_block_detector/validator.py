"""
Order Block validation.

This module validates Order Block candidates before they become
confirmed Order Blocks.
"""

from __future__ import annotations

from core.order_block_detector.models import (
    OrderBlockCandidate,
)


class OrderBlockValidator:
    """
    Validates Order Block candidates.

    Version 2 adds basic quality filters while remaining
    lightweight and deterministic.
    """

    def validate(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Validate an Order Block candidate.
        """

        if not self._validate_price_range(candidate):
            return False

        if not self._validate_origin(candidate):
            return False

        if not self._validate_break(candidate):
            return False

        if not self._validate_block_height(candidate):
            return False

        if not self._validate_displacement(candidate):
            return False

        return True

    def _validate_price_range(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Top must not be below bottom.
        """

        return candidate.top_price >= candidate.bottom_price

    def _validate_origin(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Candidate must have a valid origin swing.
        """

        return candidate.origin_swing is not None

    def _validate_break(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Candidate must be created from a confirmed
        structural break.
        """

        return candidate.trigger_break is not None

    def _validate_block_height(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Reject Order Blocks with an invalid height.

        Version 2:
        - Height must be positive.
        - Height must not be excessively small.
        """

        height = (
            candidate.top_price
            - candidate.bottom_price
        )

        return height >= 0.10

    def _validate_displacement(
        self,
        candidate: OrderBlockCandidate,
    ) -> bool:
        """
        Validate that the structural break created a meaningful
        displacement away from the Order Block.

        Version 1 uses the distance between the Order Block
        boundary and the break price.

        Future versions will replace this with ATR-based
        displacement.
        """

        displacement = abs(
            candidate.trigger_break.break_price
            - candidate.origin_swing.price
        )

        return displacement >= 0.20