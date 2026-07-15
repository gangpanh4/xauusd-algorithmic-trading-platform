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

        liquidity_sweep_distance = max(
            values.get(
                "liquidity_sweep_distance",
                0.0,
            ),
            0.0,
        )

        #
        # Research 004:
        # Reward stronger liquidity sweeps,
        # but cap their influence.
        #
        liquidity_strength = min(
            liquidity_sweep_distance,
            1.0,
        )

        score = has_liquidity

        if has_liquidity > 0.0:
            score += (
                liquidity_strength
                * 0.25
            )

        score = min(
            score,
            1.0,
        )

        return EvidenceScore(
            family="liquidity",
            score=score,
            confidence=score,
        )