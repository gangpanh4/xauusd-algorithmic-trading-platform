"""
Fair Value Gap enumerations.
"""

from __future__ import annotations

from enum import Enum


class FairValueGapType(str, Enum):
    """
    Direction of a Fair Value Gap.
    """

    BULLISH = "bullish"
    BEARISH = "bearish"


class FairValueGapStatus(str, Enum):
    """
    Lifecycle state of a Fair Value Gap.
    """

    NEW = "new"

    ACTIVE = "active"

    MITIGATED = "mitigated"

    INVALIDATED = "invalidated"

    ARCHIVED = "archived"