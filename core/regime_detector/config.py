"""
Configuration models for the Market Regime Detection module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Dict

from .exceptions import ConfigValidationError


@dataclass(frozen=True)
class IndicatorConfig:
    """
    Configuration for a single technical indicator.
    """

    enabled: bool = True
    weight: float = 1.0
    lookback_period: int = 14
    normalization_window: int = 252
    trending_threshold: float = 25.0


@dataclass(frozen=True)
class VolatilityConfig:
    """
    ATR-to-close volatility thresholds.

    Values use the same ratio returned by ``ATRIndicator``:
    ``normalized_atr = atr / close``. For example, ``0.001``
    represents ATR equal to 0.10% of the current close.
    """

    high_threshold: float = 0.002
    medium_threshold: float = 0.001

    def __post_init__(self) -> None:
        """Validate ordered unit-ratio volatility thresholds."""

        for name, value in (
            ("high_threshold", self.high_threshold),
            ("medium_threshold", self.medium_threshold),
        ):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ConfigValidationError(
                    f"{name} must be a finite numeric ATR-to-close ratio."
                )
            if not isfinite(float(value)):
                raise ConfigValidationError(
                    f"{name} must be finite."
                )
            if not 0.0 < float(value) <= 1.0:
                raise ConfigValidationError(
                    f"{name} must be within (0.0, 1.0]."
                )

        if self.medium_threshold >= self.high_threshold:
            raise ConfigValidationError(
                "medium_threshold must be less than high_threshold."
            )


@dataclass(frozen=True)
class ChoppinessConfig:
    """
    Choppiness Index thresholds.
    """

    trending_threshold: float = 38.2
    neutral_threshold: float = 50.0
    veto_threshold: float = 61.8


@dataclass(frozen=True)
class RegimeConfig:
    """
    Regime scoring configuration.
    """

    min_score_threshold: float = 6.0


@dataclass(frozen=True)
class ThresholdConfig:
    """
    Threshold configuration for regime transitions.
    """

    trend_entry_percentile: float = 0.70
    trend_exit_percentile: float = 0.55
    crisis_percentile: float = 0.95
    minimum_confidence: float = 0.60
    max_adaptive_drift_per_cycle: float = 0.02


@dataclass(frozen=True)
class ValidationConfig:
    """
    Data validation configuration.
    """

    strict_data_validation: bool = True
    initialization_period: int = 252
    history_retention_periods: int = 252


@dataclass(frozen=True)
class MarketRegimeConfig:
    """
    Root configuration object for the regime detector.
    """

    indicators: Dict[str, IndicatorConfig] = field(default_factory=dict)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)


@dataclass(frozen=True)
class RegimeDetectorConfig:
    """
    Top-level configuration for the Market Regime Detection module.
    """

    adx: IndicatorConfig = field(default_factory=IndicatorConfig)
    volatility: VolatilityConfig = field(default_factory=VolatilityConfig)
    choppiness: ChoppinessConfig = field(default_factory=ChoppinessConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)

    history_retention_periods: int = 252

    trend_entry_percentile: float = 0.70
    trend_exit_percentile: float = 0.55

    crisis_percentile: float = 0.95

    trend_confirmation_bars: int = 3
    range_confirmation_bars: int = 2
    crisis_confirmation_bars: int = 1

    minimum_regime_duration: int = 5

    strict_data_validation: bool = True

    debug_logging: bool = False

    def __post_init__(self) -> None:
        """
        Validate configuration after initialization.
        """

        if self.trend_exit_percentile >= self.trend_entry_percentile:
            raise ConfigValidationError(
                "trend_exit_percentile must be less than trend_entry_percentile."
            )

        if not 0.0 <= self.crisis_percentile <= 1.0:
            raise ConfigValidationError(
                "crisis_percentile must be between 0.0 and 1.0."
            )

        if self.minimum_regime_duration < 1:
            raise ConfigValidationError(
                "minimum_regime_duration must be at least 1."
            )