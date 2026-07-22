"""
Confluence Engine models.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# =====================================================
# Legacy V1 Models (KEEP)
# =====================================================

@dataclass(slots=True, frozen=True)
class ConfluenceFactor:
    """
    One evaluated confluence factor.
    """

    name: str

    passed: bool

    score: float

    weight: float

    reason: str


@dataclass(slots=True, frozen=True)
class ConfluenceResult:
    """
    Legacy Confluence Result.

    Used by the existing ConfluenceEngine and
    current test suite.
    """

    score: float

    maximum_score: float

    confidence: float

    approved: bool

    factors: list[ConfluenceFactor] = field(
        default_factory=list
    )

    @property
    def percentage(
        self,
    ) -> float:
        """
        Return the approval percentage.
        """

        return self.confidence * 100.0


# =====================================================
# New Architecture V2 Models
# =====================================================

@dataclass(slots=True, frozen=True)
class EvidenceContext:
    """
    Normalized evidence supplied to the Confluence Engine.

    Every quality metric is normalized to the range 0.0–1.0,
    where:

        0.0 = no evidence
        1.0 = strongest possible evidence

    This object decouples the Confluence Engine from the
    internal implementation of Market Structure, Price Action,
    and future analysis engines.
    """

    structure_quality: float = 0.0

    liquidity_quality: float = 0.0

    order_block_quality: float = 0.0

    fair_value_gap_quality: float = 0.0

    trend_quality: float = 0.0


@dataclass(slots=True, frozen=True)
class ConfluenceAnalysisResult:
    """
    New architecture output.

    This will eventually be consumed by the
    SignalGenerator V2.
    """

    timestamp: datetime

    structure_score: float

    liquidity_score: float

    order_block_score: float

    fair_value_gap_score: float

    trend_score: float

    total_score: float

    @property
    def confidence(
        self,
    ) -> float:
        """
        Return the normalized confluence confidence.
        """

        return self.total_score

    reasons: tuple[str, ...] = field(
        default_factory=tuple,
    )