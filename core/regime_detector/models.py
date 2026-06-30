"""
Core data models for the Market Regime Detection module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum
from typing import Any

class RegimeLabel(Enum):
    UNKNOWN = "UNKNOWN"

    TRENDING_BULL = "TRENDING_BULL"
    TRENDING_BEAR = "TRENDING_BEAR"

    RANGING = "RANGING"

    LOW_VOLATILITY = "LOW_VOLATILITY"
    NORMAL_VOLATILITY = "NORMAL_VOLATILITY"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"

    CRISIS = "CRISIS"


class ConfidenceTier(Enum):
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class StatusFlag(Enum):
    INITIALIZATION_PERIOD = "INITIALIZATION_PERIOD"
    DATA_QUALITY_WARNING = "DATA_QUALITY_WARNING"
    CALIBRATION_STALE = "CALIBRATION_STALE"
    REDUCED_CONFIDENCE = "REDUCED_CONFIDENCE"
    STRUCTURAL_BREAK_DETECTED = "STRUCTURAL_BREAK_DETECTED"
    OSCILLATION_SUPPRESSION = "OSCILLATION_SUPPRESSION"
    LOG_SINK_DEGRADED = "LOG_SINK_DEGRADED"

@dataclass(frozen=True)
class MarketBar:
    """
    Represents one validated market bar (OHLCV).
    """

    timestamp: datetime

    open: float
    high: float
    low: float
    close: float

    volume: float

    spread: float | None = None

    tick_volume: int | None = None

    real_volume: int | None = None

    is_imputed: bool = False

    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class MarketRegime:
    """
    Final regime assessment returned by the detector after processing
    one MarketBar.
    """

    observation_timestamp: datetime

    computation_timestamp: datetime

    primary_regime: RegimeLabel

    confidence: float

    confidence_tier: ConfidenceTier

    status_flags: frozenset[StatusFlag] = field(default_factory=frozenset)

@dataclass(frozen=True)
class TransitionRecord:
    """
    Records a confirmed regime transition.
    """

    timestamp: datetime

    previous_regime: RegimeLabel

    new_regime: RegimeLabel

    confidence: float

    reason: str

    status_flags_at_transition: frozenset[StatusFlag] = field(default_factory=frozenset)

    prior_candidate_abort_count: int = 0

@dataclass(frozen=True)
class FeatureSet:
    """
    Computed market features used for regime evaluation.
    """

    # Trend
    adx: float
    trend_strength: float

    # Volatility
    atr: float
    normalized_volatility: float
    volatility_percentile: float
    choppiness: float

    # Moving averages
    ema20: float
    ema50: float
    ema200: float

    # EMA slopes
    ema20_slope: float
    ema50_slope: float
    ema200_slope: float

    # Momentum
    momentum: float
    efficiency_ratio: float