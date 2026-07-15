"""
Probability Engine.
"""

from __future__ import annotations

from core.feature_engineering.models import FeatureVector

from .conditioner import RegimeConditioner
from .config import ProbabilityEngineConfig
from .evaluator import (
    ProbabilityEvaluator,
)
from .liquidity import (
    LiquidityProbabilityEvaluator,
)
from .models import ProbabilityResult
from .state import ProbabilityEngineState
from .structure import StructureProbabilityEvaluator


class ProbabilityEngine:
    """
    Converts engineered features into a probability estimate.
    """

    def __init__(
        self,
        config: ProbabilityEngineConfig | None = None,
    ) -> None:

        self.config = config or ProbabilityEngineConfig()

        self.state = ProbabilityEngineState()

        self.evaluators: list[ProbabilityEvaluator] = [
            StructureProbabilityEvaluator(
                self.config,
            ),
            LiquidityProbabilityEvaluator(
                self.config,
            ),
        ]

        self.conditioner = RegimeConditioner()

    def process(
        self,
        features: FeatureVector,
    ) -> ProbabilityResult:
        """
        Version 1 placeholder.

        Research-based scoring will be implemented
        in the next iteration.
        """

        evidence = [
            evaluator.evaluate(features)
            for evaluator in self.evaluators
        ]

        evidence = self.conditioner.condition(
            evidence=evidence,
            regime=None,
        )

        probability = (
            sum(item.score for item in evidence)
            / len(evidence)
        )

        confidence = (
            sum(item.confidence for item in evidence)
            / len(evidence)
        )

        accepted = (
            probability >= self.config.minimum_probability
            and confidence >= self.config.minimum_confidence
        )

        result = ProbabilityResult(
            probability=probability,
            confidence=confidence,
            accepted=accepted,
            evidence=evidence,
            feature_vector=features,
        )

        self.state.latest_result = result

        self.state.processed_count += 1

        return result