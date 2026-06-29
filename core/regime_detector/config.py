"""
Configuration models for the Market Regime Detection module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from .exceptions import ConfigurationError


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
    Volatility scoring thresholds.
    """

    high_threshold: float = 2.0
    medium_threshold: float = 1.0


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

    def __post_init__(self) -> None:
        """
        Validate configuration after initialization.
        """

        if self.trend_exit_percentile >= self.trend_entry_percentile:
            raise ConfigurationError(
                "trend_exit_percentile must be less than trend_entry_percentile."
            )

        if not 0.0 <= self.crisis_percentile <= 1.0:
            raise ConfigurationError(
                "crisis_percentile must be between 0.0 and 1.0."
            )

        if self.minimum_regime_duration < 1:
            raise ConfigurationError(
                "minimum_regime_duration must be at least 1."
            )