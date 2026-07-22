"""
Configuration models for the Signal Generation module.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isclose, isfinite


@dataclass(slots=True, frozen=True)
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

    def __post_init__(self) -> None:
        """Validate signal-generation thresholds."""

        if not isfinite(self.minimum_signal_confidence):
            raise ValueError(
                "minimum_signal_confidence must be finite."
            )

        if not 0.0 <= self.minimum_signal_confidence <= 1.0:
            raise ValueError(
                "minimum_signal_confidence must be between 0.0 and 1.0."
            )

        if not isfinite(self.minimum_total_score):
            raise ValueError(
                "minimum_total_score must be finite."
            )

        if self.minimum_total_score < 0.0:
            raise ValueError(
                "minimum_total_score must be non-negative."
            )

        if (
            isinstance(self.signal_cooldown_bars, bool)
            or not isinstance(self.signal_cooldown_bars, int)
        ):
            raise TypeError(
                "signal_cooldown_bars must be an integer."
            )

        if self.signal_cooldown_bars < 0:
            raise ValueError(
                "signal_cooldown_bars must be non-negative."
            )

        if not isfinite(self.minimum_trend_strength):
            raise ValueError(
                "minimum_trend_strength must be finite."
            )

        if self.minimum_trend_strength < 0.0:
            raise ValueError(
                "minimum_trend_strength must be non-negative."
            )


@dataclass(slots=True, frozen=True)
class SignalScorerConfig:
    """
    Configuration for SignalScorer.

    All weights should sum to 1.0.
    """

    probability_weight: float = 0.30

    trade_quality_weight: float = 0.25

    decision_weight: float = 0.20

    confluence_weight: float = 0.15

    regime_weight: float = 0.10

    def __post_init__(self) -> None:
        """Validate scorer weights after initialization."""

        weights = {
            "probability_weight": self.probability_weight,
            "trade_quality_weight": self.trade_quality_weight,
            "decision_weight": self.decision_weight,
            "confluence_weight": self.confluence_weight,
            "regime_weight": self.regime_weight,
        }

        for name, value in weights.items():
            if not isfinite(value):
                raise ValueError(f"{name} must be finite.")

            if value < 0.0:
                raise ValueError(f"{name} must be non-negative.")

        total_weight = fsum(weights.values())

        if not isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError(
                "SignalScorerConfig weights must sum to 1.0; "
                f"received {total_weight:.12g}."
            )
