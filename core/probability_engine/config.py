"""
Probability Engine configuration.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(
    slots=True,
    frozen=True,
)
class ProbabilityEngineConfig:
    """
    Configuration for the Probability Engine.
    """

    minimum_probability: float = 0.60

    minimum_confidence: float = 0.50

    #
    # Baseline Structure Weights
    #

    structure_confidence_weight: float = 0.40

    trend_weight: float = 0.25

    bos_weight: float = 0.20

    choch_weight: float = 0.10

    liquidity_weight: float = 0.05

    # Structure Interaction Thresholds
    strong_trend_threshold: float = 0.70
    weak_trend_threshold: float = 0.40
    strong_structure_threshold: float = 0.70
    weak_structure_threshold: float = 0.50

    # Structure Interaction Adjustments
    continuation_bonus: float = 0.10
    strong_reversal_bonus: float = 0.12
    weak_bos_penalty: float = 0.08
    conflict_penalty: float = 0.10
    max_no_confirmation_score: float = 0.30

    # ======================================================
    # Probability Combination
    # ======================================================

    # Balance the engineered-feature model with independent structure and
    # liquidity evaluators. The weighted model is heuristic and must not
    # dominate the final estimate before outcome calibration exists.
    weighted_probability_weight: float = 0.50

    evaluator_probability_weight: float = 0.50

    def __post_init__(self) -> None:
        """
        Validate configuration invariants.

        Probability thresholds and normalized adjustments must remain inside
        ``[0.0, 1.0]``. Weights must be finite and non-negative. Probability
        combination weights are treated as relative weights, so their total
        must be greater than zero but does not need to equal ``1.0``.
        """

        unit_interval_fields = (
            "minimum_probability",
            "minimum_confidence",
            "strong_trend_threshold",
            "weak_trend_threshold",
            "strong_structure_threshold",
            "weak_structure_threshold",
            "continuation_bonus",
            "strong_reversal_bonus",
            "weak_bos_penalty",
            "conflict_penalty",
            "max_no_confirmation_score",
        )

        for field_name in unit_interval_fields:
            self._validate_unit_interval(
                field_name,
                getattr(self, field_name),
            )

        weight_fields = (
            "structure_confidence_weight",
            "trend_weight",
            "bos_weight",
            "choch_weight",
            "liquidity_weight",
            "weighted_probability_weight",
            "evaluator_probability_weight",
        )

        for field_name in weight_fields:
            self._validate_non_negative(
                field_name,
                getattr(self, field_name),
            )

        if self.weak_trend_threshold > self.strong_trend_threshold:
            raise ValueError(
                "weak_trend_threshold must be less than or equal to "
                "strong_trend_threshold."
            )

        if self.weak_structure_threshold > self.strong_structure_threshold:
            raise ValueError(
                "weak_structure_threshold must be less than or equal to "
                "strong_structure_threshold."
            )

        if self.total_probability_weight <= 0.0:
            raise ValueError(
                "Probability combination weights must have a positive total."
            )

    @staticmethod
    def _validate_unit_interval(
        field_name: str,
        value: float,
    ) -> None:
        """
        Validate a finite normalized configuration value.
        """

        if not isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(
                f"{field_name} must be a finite value between 0.0 and 1.0."
            )

    @staticmethod
    def _validate_non_negative(
        field_name: str,
        value: float,
    ) -> None:
        """
        Validate a finite non-negative configuration value.
        """

        if not isfinite(value) or value < 0.0:
            raise ValueError(
                f"{field_name} must be a finite non-negative value."
            )

    @property
    def total_probability_weight(
        self,
    ) -> float:
        """
        Return the sum of the probability combination weights.
        """

        return (
            self.weighted_probability_weight
            + self.evaluator_probability_weight
        )