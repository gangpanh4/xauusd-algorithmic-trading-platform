"""
Fair Value Gap models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.data.models import (
    MarketBar,
)

from core.fair_value_gap_detector.enums import (
    FairValueGapStatus,
    FairValueGapType,
)


@dataclass(slots=True)
class FairValueGapCandidate:
    """
    Candidate Fair Value Gap.
    """

    timestamp: datetime

    gap_type: FairValueGapType

    top_price: float

    bottom_price: float

    first_bar: MarketBar

    middle_bar: MarketBar

    third_bar: MarketBar

    equilibrium_price: float = 0.0

    is_discount_zone: bool = False

    is_premium_zone: bool = False

    quality_score: float = 0.0

    age: int = 0

    status: FairValueGapStatus = (
        FairValueGapStatus.NEW
    )

    @property
    def gap_size(
        self,
    ) -> float:
        """
        Return the size of the Fair Value Gap.
        """

        return (
            self.top_price
            - self.bottom_price
        )


@dataclass(slots=True)
class FairValueGap:
    """
    Confirmed Fair Value Gap.
    """

    id: int

    timestamp: datetime

    gap_type: FairValueGapType

    top_price: float

    bottom_price: float

    first_bar: MarketBar

    middle_bar: MarketBar

    third_bar: MarketBar

    equilibrium_price: float = 0.0

    is_discount_zone: bool = False

    is_premium_zone: bool = False

    quality_score: float = 0.0

    age: int = 0

    status: FairValueGapStatus = (
        FairValueGapStatus.ACTIVE
    )

    @property
    def gap_size(
        self,
    ) -> float:
        """
        Return the size of the Fair Value Gap.
        """

        return (
            self.top_price
            - self.bottom_price
        )

    @property
    def is_active(
        self,
    ) -> bool:
        """
        True if the gap is tradable.
        """

        return (
            self.status
            is FairValueGapStatus.ACTIVE
        )

    @property
    def is_mitigated(
        self,
    ) -> bool:
        """
        True if the gap has been mitigated.
        """

        return (
            self.status
            is FairValueGapStatus.MITIGATED
        )

    @property
    def is_invalidated(
        self,
    ) -> bool:
        """
        True if the gap has been invalidated.
        """

        return (
            self.status
            is FairValueGapStatus.INVALIDATED
        )