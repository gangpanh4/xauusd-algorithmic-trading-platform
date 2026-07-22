"""
Liquidity probability evaluator.
"""

from __future__ import annotations

from core.feature_engineering.models import FeatureVector

from .config import ProbabilityEngineConfig
from .evaluator import ProbabilityEvaluator
from .models import EvidenceScore


class LiquidityProbabilityEvaluator(
    ProbabilityEvaluator,
):
    """
    Evaluates liquidity-related engineered features.
    """

    def __init__(
        self,
        config: ProbabilityEngineConfig,
    ) -> None:

        self.config = config

    def evaluate(
        self,
        features: FeatureVector,
    ) -> EvidenceScore:
        """
        Baseline liquidity evaluation.
        """

        values = {
            feature.name: feature.value
            for feature in features.features
        }

        has_liquidity = values.get(
            "has_liquidity",
            0.0,
        )

        liquidity_strength = values.get(
            "liquidity_sweep_strength",
        )

        if liquidity_strength is None:
            liquidity_strength = values.get(
                "liquidity_sweep_distance",
                0.0,
            )

        liquidity_strength = min(
            max(liquidity_strength, 0.0),
            1.0,
        )

        # Presence provides the baseline evidence while sweep strength
        # differentiates weak and strong confirmations. Dividing by the
        # maximum possible weighted total keeps the result inside [0, 1]
        # without saturating every confirmed liquidity event at 1.0.
        score = (
            has_liquidity
            * (1.0 + liquidity_strength * 0.25)
            / 1.25
        )

        return EvidenceScore(
            family="liquidity",
            score=score,
            confidence=score,
        )