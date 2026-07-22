"""
Price Action Engine models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.order_block_detector.models import (
    OrderBlock,
)

from core.fair_value_gap_detector.models import (
    FairValueGap,
    FairValueGapCandidate,
)


@dataclass(slots=True, frozen=True)
class PriceActionResult:
    """
    Aggregated output produced by the PriceActionEngine.
    """

    timestamp: datetime

    last_order_block: OrderBlock | None

    last_fair_value_gap: FairValueGap | FairValueGapCandidate | None

    price_action_confidence: float