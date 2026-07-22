"""
Trading Pipeline models.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite

from core.confluence_engine.models import (
    ConfluenceResult,
)

from core.fair_value_gap_detector.models import (
    FairValueGapCandidate,
)

from core.feature_engineering.models import (
    FeatureVector,
)

from core.probability_engine.models import (
    ProbabilityResult,
)

from core.decision_engine.models import (
    DecisionResult,
)

from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquiditySweepEvent,
)

from core.order_block_detector.models import (
    OrderBlockCandidate,
)

from core.regime_detector.models import (
    MarketRegime,
)

from core.risk_manager.models import (
    TradePlan,
)

from core.signal_generator.models import (
    TradingSignal,
)

from core.trade_quality.models import (
    TradeQuality,
)


class PipelineStage(StrEnum):
    """Ordered stages used by pipeline-observation diagnostics."""

    OBSERVATION = "OBSERVATION"
    REGIME = "REGIME"
    MARKET_STRUCTURE = "MARKET_STRUCTURE"
    FEATURES = "FEATURES"
    PROBABILITY = "PROBABILITY"
    TRADE_QUALITY = "TRADE_QUALITY"
    CONFLUENCE = "CONFLUENCE"
    SIGNAL = "SIGNAL"
    RISK = "RISK"
    APPROVED = "APPROVED"


class PipelineDisposition(StrEnum):
    """Final disposition of one completed market observation."""

    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class PipelineObservationAudit:
    """
    Immutable diagnostic record for one completed pipeline observation.

    The record deliberately stores scalar facts rather than the complete
    mutable pipeline object graph so it can be exported safely and compared
    across backtest runs.
    """

    timestamp: datetime
    disposition: PipelineDisposition
    stage_reached: PipelineStage
    rejection_stage: PipelineStage | None = None
    reason_code: str | None = None
    reason: str | None = None

    regime_confirmed: bool = False
    bos_present: bool = False
    choch_present: bool = False
    liquidity_present: bool = False
    feature_count: int = 0

    probability_calculated: bool = False
    probability_accepted: bool = False
    probability_value: float | None = None

    trade_quality_calculated: bool = False
    trade_quality_approved: bool = False
    trade_quality_score: float | None = None

    confluence_available: bool = False
    confluence_approved: bool = False
    confluence_score: float | None = None

    signal_generated: bool = False
    risk_approved: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        object.__setattr__(self, "timestamp", self.timestamp.astimezone(UTC))

        if not isinstance(self.disposition, PipelineDisposition):
            raise TypeError("disposition must be PipelineDisposition")
        if not isinstance(self.stage_reached, PipelineStage):
            raise TypeError("stage_reached must be PipelineStage")
        if self.rejection_stage is not None and not isinstance(
            self.rejection_stage, PipelineStage
        ):
            raise TypeError("rejection_stage must be PipelineStage or None")

        if self.feature_count < 0:
            raise ValueError("feature_count cannot be negative")

        for name in ("reason_code", "reason"):
            value = getattr(self, name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{name} must be a non-empty string or None")

        for name in (
            "probability_value",
            "trade_quality_score",
            "confluence_score",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric or None")
            numeric = float(value)
            if not isfinite(numeric):
                raise ValueError(f"{name} must be finite")
            if not 0.0 <= numeric <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
            object.__setattr__(self, name, numeric)

        if self.disposition is PipelineDisposition.ACCEPTED:
            if self.stage_reached is not PipelineStage.APPROVED:
                raise ValueError(
                    "accepted observations must reach PipelineStage.APPROVED"
                )
            if self.rejection_stage is not None:
                raise ValueError("accepted observations cannot have rejection_stage")
            if self.reason_code is not None or self.reason is not None:
                raise ValueError("accepted observations cannot have rejection reason")
            if not self.risk_approved:
                raise ValueError("accepted observations must be risk approved")
        elif self.disposition is PipelineDisposition.REJECTED:
            if self.rejection_stage is None:
                raise ValueError("rejected observations require rejection_stage")
            if self.reason_code is None:
                raise ValueError("rejected observations require reason_code")
        elif self.rejection_stage is not None:
            raise ValueError(
                "only rejected observations may define rejection_stage"
            )

    @property
    def accepted(self) -> bool:
        """Return whether the observation reached final approval."""

        return self.disposition is PipelineDisposition.ACCEPTED


@dataclass(slots=True)
class PipelineResult:
    """
    Final result produced by the trading pipeline.

    Every stage of the pipeline contributes to this object.
    """

    # ==========================
    # Market Regime
    # ==========================

    regime: MarketRegime

    # ==========================
    # Market Structure
    # ==========================

    bos_event: BOSEvent | None = None

    choch_event: CHOCHEvent | None = None

    liquidity_event: LiquiditySweepEvent | None = None

    # ==========================
    # Smart Money Concepts
    # ==========================

    order_block: OrderBlockCandidate | None = None

    fair_value_gap: FairValueGapCandidate | None = None

    # ==========================
    # Feature Engineering
    # ==========================

    features: FeatureVector | None = None

    # ==========================
    # Probability & Decision
    # ==========================

    probability: ProbabilityResult | None = None

    decision: DecisionResult | None = None

    # ==========================
    # Trade Quality
    # ==========================

    trade_quality: TradeQuality | None = None

    # ==========================
    # Decision Layer
    # ==========================

    confluence: ConfluenceResult | None = None

    signal: TradingSignal | None = None

    trade_plan: TradePlan | None = None

    # ==========================
    # Convenience Properties
    # ==========================

    @property
    def has_structure(
        self,
    ) -> bool:
        """
        True if any structural event exists.
        """

        return (
            self.bos_event is not None
            or self.choch_event is not None
        )

    @property
    def has_order_block(
        self,
    ) -> bool:
        """
        True if an Order Block exists.
        """

        return self.order_block is not None

    @property
    def has_fair_value_gap(
        self,
    ) -> bool:
        """
        True if a Fair Value Gap exists.
        """

        return self.fair_value_gap is not None

    @property
    def approved(
        self,
    ) -> bool:
        """
        Final pipeline approval.
        """

        if self.confluence is None:
            return False

        return self.confluence.approved