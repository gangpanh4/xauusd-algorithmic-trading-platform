"""
Structure probability evaluator.
"""

from __future__ import annotations

from core.feature_engineering.models import FeatureVector

from .config import ProbabilityEngineConfig
from .evaluator import ProbabilityEvaluator
from .models import EvidenceScore


class StructureProbabilityEvaluator(
    ProbabilityEvaluator,
):
    """
    Evaluates structure features.
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
        Baseline deterministic structure evaluation.
        """

        values = {
            feature.name: feature.value
            for feature in features.features
        }

        structure_confidence = values.get(
            "structure_confidence",
            0.0,
        )

        trend = abs(
            values.get("current_trend", 0.0),
        )

        has_bos = values.get("has_bos", 0.0)

        has_choch = values.get("has_choch", 0.0)

        has_liquidity = values.get(
            "has_liquidity",
            0.0,
        )

        bos_break_distance = max(
            values.get("bos_break_distance", 0.0),
            0.0,
        )

        #
        # Research 004:
        # Reward stronger structural breaks.
        #
        # We cap the contribution to avoid one
        # unusually large break dominating the score.
        #
        bos_strength = min(
            bos_break_distance,
            1.0,
        )

        choch_break_distance = max(
            values.get("choch_break_distance", 0.0),
            0.0,
        )

        choch_strength = min(
            choch_break_distance,
            1.0,
        )

        score = (
            structure_confidence
            * self.config.structure_confidence_weight
            + trend
            * self.config.trend_weight
            + has_bos
            * self.config.bos_weight
            + has_choch
            * self.config.choch_weight
            + has_liquidity
            * self.config.liquidity_weight
        )

        #
        # Add a small evidence bonus only when
        # a BOS actually exists.
        #
        if has_bos > 0.0:
            score += (
                bos_strength
                * self.config.bos_weight
                * 0.25
            )

        #
        # Research 004:
        # Stronger CHOCH events carry
        # more evidence than weak reversals.
        #
        if has_choch > 0.0:
            score += (
                choch_strength
                * self.config.choch_weight
                * 0.25
            )

        #
        # Research 005:
        # Strong continuation setup.
        #
        # A BOS confirmed by both a strong trend and
        # nearby liquidity deserves additional evidence.
        #
        if (
            has_bos > 0.0
            and trend >= self.config.strong_trend_threshold
            and has_liquidity > 0.0
        ):
            score += self.config.continuation_bonus

        score = min(score, 1.0)

        return EvidenceScore(
            family="structure",
            score=score,
            confidence=structure_confidence,
        )