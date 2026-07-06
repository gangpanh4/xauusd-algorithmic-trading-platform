"""
Configuration models for the Signal Generation module.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalGeneratorConfig:
    """
    Configuration for the Signal Generator.
    """

    minimum_signal_confidence: float = 0.70

    minimum_total_score: float = 6.0

    signal_cooldown_bars: int = 3

    allow_duplicate_signals: bool = False

    allow_countertrend_signals: bool = False

    minimum_trend_strength: float = 0.60

    debug_logging: bool = False