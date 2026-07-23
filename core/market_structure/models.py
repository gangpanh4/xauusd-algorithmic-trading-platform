"""
Shared data models for the Market Structure Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    SwingClassification,
    SwingType,
    TrendDirection,
)
from core.market_structure.measurements import MarketStructureMeasurements


@dataclass(slots=True, frozen=True)
class SwingPoint:
    """
    Immutable representation of a confirmed market swing.

    SwingPoint objects are produced exclusively by the SwingDetector
    and consumed by downstream market structure detectors.
    """

    timestamp: datetime
    index: int
    price: float
    swing_type: SwingType

    # Index of the candle where this swing became confirmed.
    confirmation_index: int

    # -----------------------------
    # Quantitative evidence (V3)
    # -----------------------------
    # Distance from the previous confirmed swing.
    distance_from_previous: float = 0.0
    # Swing size expressed as an ATR multiple.
    atr_multiple: float = 0.0
    # How dominant this pivot is compared with surrounding candles.
    pivot_dominance: float = 0.0
    # Confidence of the swing confirmation.
    confirmation_strength: float = 0.0

    # Relationship to the previous confirmed swing of the same type.
    classification: SwingClassification = SwingClassification.UNCLASSIFIED


@dataclass(slots=True, frozen=True)
class BOSEvent:
    """
    Immutable representation of a confirmed Break of Structure (BOS).

    Version 3 extends the event with quality metrics so downstream
    engines can evaluate how strong a BOS is instead of only knowing
    that one occurred.
    """

    timestamp: datetime

    # Event classification.
    break_type: BreakType

    # Structural direction.
    direction: TrendDirection

    # Swing that was broken.
    swing_point: SwingPoint

    # Price that confirmed the break.
    break_price: float

    # Candle where the BOS became confirmed.
    confirmation_index: int

    # ----------------------------
    # Evidence Metrics
    # ----------------------------

    # Absolute distance beyond the broken swing.
    break_distance: float = 0.0

    # Break distance normalized by ATR at confirmation time.
    break_atr_multiple: float = 0.0

    # Overall BOS quality (0.0 - 1.0).
    quality: float = 0.0

    # Structural strength (0.0 - 1.0).
    strength: float = 0.0

    # Combined momentum of the break.
    power_score: float = 0.0

    # Structural quality of the break.
    structure_score: float = 0.0

    # Number of swings since the BOS occurred.
    age: int = 0


@dataclass(slots=True, frozen=True)
class CHOCHEvent:
    """
    Immutable representation of a confirmed Change of Character.

    Version 3 extends the event with quality metrics.
    """

    timestamp: datetime

    # Event classification.
    break_type: BreakType

    # Structural direction.
    direction: TrendDirection

    # Swing that was broken.
    swing_point: SwingPoint

    # Price that confirmed the break.
    break_price: float

    # Candle where the CHOCH became confirmed.
    confirmation_index: int

    # ----------------------------
    # Evidence Metrics
    # ----------------------------

    # Absolute distance beyond the protected swing.
    break_distance: float = 0.0

    # Break distance normalized by ATR at confirmation time.
    break_atr_multiple: float = 0.0

    # Overall CHOCH quality (0.0 - 1.0).
    quality: float = 0.0

    # Structural strength (0.0 - 1.0).
    strength: float = 0.0

    # Combined momentum of the break.
    power_score: float = 0.0

    # Structural quality of the break.
    structure_score: float = 0.0

    # Number of swings since the CHOCH occurred.
    age: int = 0


@dataclass(slots=True, frozen=True)
class LiquidityLevel:
    """
    Represents a price level where liquidity is expected.

    Examples:
    - Previous swing high (buy-side liquidity)
    - Previous swing low (sell-side liquidity)
    """

    timestamp: datetime
    price: float
    swing_point: SwingPoint
    is_buy_side: bool


@dataclass(slots=True, frozen=True)
class LiquiditySweepEvent:
    """
    Represents a confirmed liquidity sweep.

    A sweep occurs when price takes a liquidity level
    and confirms the grab.

    Version 4 extends the event with quantitative
    evidence used by downstream measurement and
    research engines.
    """

    timestamp: datetime

    # Liquidity level that was swept.
    liquidity_level: LiquidityLevel

    # Price where the sweep occurred.
    sweep_price: float

    # Candle where the sweep became confirmed.
    confirmation_index: int

    # -------------------------------------------------
    # Quantitative Evidence
    # -------------------------------------------------

    # Absolute distance beyond the liquidity level.
    sweep_distance: float = 0.0

    # Sweep size expressed as an ATR multiple.
    atr_multiple: float = 0.0

    # Relative strength of the sweep.
    sweep_strength: float = 0.0

    # Strength of the rejection after the sweep.
    reaction_strength: float = 0.0

    # Efficiency of reclaiming the liquidity level.
    reclaim_strength: float = 0.0

    # Relative liquidity density.
    density: float = 0.0

    # Overall sweep quality.
    quality: float = 0.0

    # Number of swings since the sweep occurred.
    age: int = 0


@dataclass(slots=True, frozen=True)
class StructureState:
    """Immutable structural snapshot for strategy consumption.

    The snapshot contains confirmed market facts only. It does not contain
    probability, trade-quality, decision, signal, risk, or execution state.
    """

    timestamp: datetime
    current_bar_index: int
    trend: MarketTrend
    confirmed_swings: tuple[SwingPoint, ...] = ()
    last_swing: SwingPoint | None = None
    last_high: SwingPoint | None = None
    last_low: SwingPoint | None = None
    protected_high: SwingPoint | None = None
    protected_low: SwingPoint | None = None
    last_bos: BOSEvent | None = None
    last_choch: CHOCHEvent | None = None
    last_liquidity: LiquiditySweepEvent | None = None
    tracked_liquidity_levels: tuple[LiquidityLevel, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.current_bar_index, bool) or not isinstance(
            self.current_bar_index,
            int,
        ):
            raise TypeError("current_bar_index must be an integer")
        if self.current_bar_index < 0:
            raise ValueError("current_bar_index cannot be negative")
        if not isinstance(self.trend, MarketTrend):
            raise TypeError("trend must be a MarketTrend")

        for swing in self.confirmed_swings:
            if not isinstance(swing, SwingPoint):
                raise TypeError(
                    "confirmed_swings must contain SwingPoint instances"
                )

        for name in (
            "last_swing",
            "last_high",
            "last_low",
            "protected_high",
            "protected_low",
        ):
            value = getattr(self, name)
            if value is not None and not isinstance(value, SwingPoint):
                raise TypeError(f"{name} must be a SwingPoint or None")

        if (
            self.last_high is not None
            and self.last_high.swing_type is not SwingType.HIGH
        ):
            raise ValueError("last_high must reference a HIGH swing")
        if (
            self.last_low is not None
            and self.last_low.swing_type is not SwingType.LOW
        ):
            raise ValueError("last_low must reference a LOW swing")
        if (
            self.protected_high is not None
            and self.protected_high.swing_type is not SwingType.HIGH
        ):
            raise ValueError("protected_high must reference a HIGH swing")
        if (
            self.protected_low is not None
            and self.protected_low.swing_type is not SwingType.LOW
        ):
            raise ValueError("protected_low must reference a LOW swing")

    @property
    def last_confirmation_index(self) -> int | None:
        """Return when the latest confirmed swing became knowable."""

        if self.last_swing is None:
            return None
        return self.last_swing.confirmation_index



@dataclass(slots=True, frozen=True)
class MarketStructureResult:
    """
    Aggregated output produced by the MarketStructureEngine.

    This is the single object consumed by downstream
    engines (Price Action, Confluence, etc.).
    """

    timestamp: datetime

    last_swing: SwingPoint | None

    last_bos: BOSEvent | None

    last_choch: CHOCHEvent | None

    last_liquidity: LiquiditySweepEvent | None

    current_trend: MarketTrend | None

    structure_confidence: float

    measurements: MarketStructureMeasurements

    swing_score: float = 0.0

    bos_score: float = 0.0

    choch_score: float = 0.0

    liquidity_score: float = 0.0

    # Explicit event freshness used by feature engineering and research.
    bos_freshness: float = 0.0
    choch_freshness: float = 0.0
    liquidity_freshness: float = 0.0

    # Configuration value used to derive freshness on this result.
    freshness_decay_bars: int = 1

    # Explicit immutable structure snapshot for strategy consumption.
    structure_state: StructureState | None = None
