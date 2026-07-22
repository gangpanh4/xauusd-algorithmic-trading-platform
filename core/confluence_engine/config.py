"""
Configuration for the Confluence Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(
    slots=True,
    frozen=True,
)
class ConfluenceEngineConfig:
    """
    Configuration controlling confluence scoring.

    The engine produces a continuous weighted score on a 0-100 scale.
    Confluence is a corroboration gate inside a larger pipeline that already
    includes probability, trade-quality, decision, signal, and risk gates.

    The default approval score is therefore calibrated for the continuous
    evidence model rather than the original binary-presence model.
    """

    liquidity_weight: float = 20.0
    bos_weight: float = 15.0
    choch_weight: float = 10.0
    order_block_weight: float = 25.0
    fair_value_gap_weight: float = 20.0
    trend_weight: float = 10.0

    # The original 70-point threshold assumed mostly binary factor inputs.
    # Continuous quality, direction, coverage, and freshness reduce each
    # factor proportionally. A 40-point corroboration threshold requires
    # meaningful multi-factor support without duplicating the downstream
    # trade-quality gate.
    minimum_approval_score: float = 40.0

    debug_logging: bool = False

    def __post_init__(self) -> None:
        """Validate the immutable configuration at construction time."""

        for name in (
            "liquidity_weight",
            "bos_weight",
            "choch_weight",
            "order_block_weight",
            "fair_value_gap_weight",
            "trend_weight",
        ):
            self._require_non_negative_finite(
                getattr(self, name),
                name=name,
            )

        maximum_score = self.maximum_score
        if maximum_score <= 0.0:
            raise ValueError("maximum_score must be positive")

        self._require_non_negative_finite(
            self.minimum_approval_score,
            name="minimum_approval_score",
        )
        if self.minimum_approval_score > maximum_score:
            raise ValueError(
                "minimum_approval_score must not exceed maximum_score"
            )

        if type(self.debug_logging) is not bool:
            raise TypeError("debug_logging must be bool")

    @property
    def maximum_score(self) -> float:
        """Return the total achievable score."""

        return (
            self.liquidity_weight
            + self.bos_weight
            + self.choch_weight
            + self.order_block_weight
            + self.fair_value_gap_weight
            + self.trend_weight
        )

    @property
    def approval_ratio(self) -> float:
        """Return the normalized approval threshold."""

        return self.minimum_approval_score / self.maximum_score

    @staticmethod
    def _require_non_negative_finite(
        value: float,
        *,
        name: str,
    ) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric")
        if not isfinite(float(value)) or float(value) < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
