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

    history_retention_periods: int = 252

    trend_entry_percentile: float = 0.70
    trend_exit_percentile: float = 0.55

    crisis_percentile: float = 0.95

    trend_confirmation_bars: int = 3
    range_confirmation_bars: int = 2
    crisis_confirmation_bars: int = 1

    minimum_regime_duration: int = 5

    strict_data_validation: bool = True