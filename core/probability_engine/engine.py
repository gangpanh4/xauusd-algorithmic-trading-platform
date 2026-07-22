"""
Probability Engine.
"""

from __future__ import annotations

from core.feature_engineering.models import FeatureVector
from .feature_weight import (
    FeatureWeight,
)
from .weight_repository import (
    WeightRepository,
)
from .weighted_probability_calculator import (
    WeightedProbabilityCalculator,
)

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
from .validator import FeatureValidator


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
        self.validator = FeatureValidator()
        self.weight_repository = WeightRepository()

        self._load_default_weights()

        self.weighted_calculator = (
            WeightedProbabilityCalculator(
                self.weight_repository,
            )
        )

        self.evaluators: list[ProbabilityEvaluator] = [
            StructureProbabilityEvaluator(
                self.config,
            ),
            LiquidityProbabilityEvaluator(
                self.config,
            ),
        ]

        self.conditioner = RegimeConditioner()

    def _load_default_weights(self) -> None:
        """
        Load the default feature weights used by the
        probability engine.

        These serve as fallback weights until research-
        generated weights become available.
        """
        self.weight_repository.set(
            FeatureWeight(
                feature_name="structure_confidence",
                weight=0.15,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="has_bos",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_break_distance",
                weight=0.35,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_break_efficiency",
                weight=0.30,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_composite_score",
                weight=0.15,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_quality",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_strength",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_power_score",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_structure_score",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="bos_age",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="has_choch",
                weight=0.10,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="choch_quality",
                weight=0.10,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="choch_strength",
                weight=0.10,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="choch_power_score",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="choch_structure_score",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="choch_age",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="current_trend",
                weight=0.25,
            )
        )
        
        # New Liquidity Weights
        self.weight_repository.set(
            FeatureWeight(
                feature_name="liquidity_atr_multiple",
                weight=0.35,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="liquidity_density",
                weight=0.05,
            )
        )
        self.weight_repository.set(
            FeatureWeight(
                feature_name="liquidity_sweep_distance",
                weight=0.25,
            )
        )

    def load_weights(
        self,
        weights: dict[str, float],
    ) -> None:
        """
        Replace the current feature weights with the
        supplied mapping.
        """

        self.weight_repository.load_weights(weights)

    def process(
        self,
        features: FeatureVector,
    ) -> ProbabilityResult:
        """
        Calculate probability and confidence from engineered features.
        """

        self.validator.validate(features)

        evidence = [
            evaluator.evaluate(features)
            for evaluator in self.evaluators
        ]

        evidence = self.conditioner.condition(
            evidence=evidence,
            regime=None,
        )
        evidence_count = len(evidence)

        if evidence_count == 0:
            raise RuntimeError(
                "Probability Engine requires at least one evidence evaluator."
            )

        weighted_probability = (
            self.weighted_calculator.calculate(
                features,
            )
        )
        evaluator_probability = (
            sum(
                item.score
                for item in evidence
            )
            / evidence_count
        )
        
        probability = (
            (
                weighted_probability
                * self.config.weighted_probability_weight
                +
                evaluator_probability
                * self.config.evaluator_probability_weight
            )
            / self.config.total_probability_weight
        )

        probability = min(
            max(probability, 0.0),
            1.0,
        )

        if not self._has_confirmation(features):
            probability = min(
                probability,
                self.config.max_no_confirmation_score,
            )

        confidence = (
            sum(
                item.confidence
                for item in evidence
            )
            / evidence_count
        )

        confidence = min(
            max(confidence, 0.0),
            1.0,
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

    @staticmethod
    def _has_confirmation(
        features: FeatureVector,
    ) -> bool:
        """
        Return whether the vector contains active trade confirmation.
        """

        for feature_name in (
            "has_bos",
            "has_choch",
            "has_liquidity",
        ):
            feature = features.get(feature_name)

            if feature is not None and feature.value > 0.0:
                return True

        return False