"""Feature Engineering Engine.

Transforms validated market evidence into a standardized ``FeatureVector`` for
probability, trade-quality, and research consumers.
"""

from __future__ import annotations

from math import isfinite

from core.market_structure.models import MarketStructureResult
from core.regime_detector.models import MarketRegime, RegimeLabel

from .config import FeatureEngineeringConfig
from .evidence import FeatureEvidence
from .extractor import FeatureExtractor
from .liquidity import LiquidityFeatureExtractor
from .models import Feature, FeatureVector
from .registry import FeatureRegistry
from .state import FeatureEngineeringState
from .structure import StructureFeatureExtractor


class FeatureEngineeringEngine:
    """Convert validated evidence into deterministic engineered features.

    Structure and liquidity facts are delegated to focused extractors. Regime
    momentum and volatility are added here because they are already computed by
    the confirmed regime detector and require only explicit normalization—not a
    second indicator implementation or a probability-derived substitute.
    """

    _REGIME_COMPONENT_MAXIMUM = 2.0

    def __init__(
        self,
        config: FeatureEngineeringConfig | None = None,
    ) -> None:
        self.config = config or FeatureEngineeringConfig()
        self._validate_config()

        self.state = FeatureEngineeringState()
        self.registry = FeatureRegistry()
        self.extractors: tuple[FeatureExtractor, ...] = (
            StructureFeatureExtractor(),
            LiquidityFeatureExtractor(),
        )

    def reset(self) -> None:
        """Reset runtime state without changing configuration."""
        self.state.reset()

    @property
    def registered_feature_count(self) -> int:
        """Return the number of statically registered feature definitions."""
        return self.registry.size

    @property
    def feature_count(self) -> int:
        """Return the number of features produced during the latest run."""
        return self.state.latest_features.size

    def process(self, evidence: FeatureEvidence) -> FeatureVector:
        """Build a standardized feature vector from one evidence snapshot.

        Momentum and volatility are emitted only when a confirmed regime exists.
        ``UNKNOWN`` regime output is treated as unavailable evidence rather than
        as a zero-strength market fact.
        """
        if not isinstance(evidence, FeatureEvidence):
            raise TypeError("evidence must be a FeatureEvidence instance")

        vector = FeatureVector()

        for extractor in self.extractors:
            extractor.extract(evidence, vector)

        self._extract_regime_quality_features(
            regime=evidence.regime,
            vector=vector,
        )
        self._validate_vector(vector)

        self.state.latest_features = vector
        self.state.processed_count += 1
        return vector

    def create_evidence(
        self,
        *,
        market_structure: MarketStructureResult | None = None,
        regime: MarketRegime | None = None,
    ) -> FeatureEvidence:
        """Create a typed evidence bundle without coupling to the pipeline."""
        if market_structure is not None and not isinstance(
            market_structure,
            MarketStructureResult,
        ):
            raise TypeError(
                "market_structure must be MarketStructureResult or None"
            )
        if regime is not None and not isinstance(regime, MarketRegime):
            raise TypeError("regime must be MarketRegime or None")

        return FeatureEvidence(
            market_structure=market_structure,
            regime=regime,
        )

    def _extract_regime_quality_features(
        self,
        *,
        regime: MarketRegime | None,
        vector: FeatureVector,
    ) -> None:
        if regime is None or regime.primary_regime is RegimeLabel.UNKNOWN:
            return

        confidence = self._validate_unit_interval(
            regime.confidence,
            name="regime.confidence",
        )
        momentum = self._normalize_regime_component(
            regime.momentum_score,
            name="regime.momentum_score",
        )
        volatility = self._normalize_regime_component(
            regime.volatility_score,
            name="regime.volatility_score",
        )

        self._add_feature(
            vector,
            name="momentum_score",
            value=momentum,
            family="momentum",
            source="confirmed_regime_detector",
            confidence=confidence,
        )
        self._add_feature(
            vector,
            name="volatility_score",
            value=volatility,
            family="volatility",
            source="confirmed_regime_detector",
            confidence=confidence,
        )

    def _normalize_regime_component(self, value: float, *, name: str) -> float:
        numeric = self._validate_finite_number(value, name=name)
        if not 0.0 <= numeric <= self._REGIME_COMPONENT_MAXIMUM:
            raise ValueError(
                f"{name} must be inside [0, {self._REGIME_COMPONENT_MAXIMUM}]"
            )
        return numeric / self._REGIME_COMPONENT_MAXIMUM

    def _add_feature(
        self,
        vector: FeatureVector,
        *,
        name: str,
        value: float,
        family: str,
        source: str,
        confidence: float = 1.0,
        normalized: bool = True,
    ) -> None:
        """Add one validated standardized feature to ``vector``."""
        numeric_value = self._validate_finite_number(value, name=name)
        numeric_confidence = self._validate_unit_interval(
            confidence,
            name=f"{name}.confidence",
        )

        if normalized and not 0.0 <= numeric_value <= 1.0:
            raise ValueError(f"normalized feature {name!r} must be inside [0, 1]")
        if numeric_confidence < self.config.minimum_confidence:
            return
        if not name or not family or not source:
            raise ValueError("feature name, family, and source must be non-empty")
        if vector.get(name) is not None:
            raise ValueError(f"duplicate feature name: {name}")

        vector.add(
            Feature(
                name=name,
                value=numeric_value,
                confidence=numeric_confidence,
                normalized=normalized,
                family=family,
                source=source,
            )
        )

    def _validate_vector(self, vector: FeatureVector) -> None:
        names: set[str] = set()
        for feature in vector.features:
            if feature.name in names:
                raise ValueError(f"duplicate feature name: {feature.name}")
            names.add(feature.name)

            self._validate_finite_number(feature.value, name=feature.name)
            self._validate_unit_interval(
                feature.confidence,
                name=f"{feature.name}.confidence",
            )
            if feature.normalized and not 0.0 <= feature.value <= 1.0:
                raise ValueError(
                    f"normalized feature {feature.name!r} must be inside [0, 1]"
                )
            if not feature.name or not feature.family or not feature.source:
                raise ValueError(
                    "all features require non-empty name, family, and source"
                )

    def _validate_config(self) -> None:
        if not isinstance(self.config, FeatureEngineeringConfig):
            raise TypeError("config must be a FeatureEngineeringConfig")
        if not isinstance(self.config.enabled, bool):
            raise TypeError("config.enabled must be bool")
        if not isinstance(self.config.normalize_features, bool):
            raise TypeError("config.normalize_features must be bool")
        self._validate_unit_interval(
            self.config.minimum_confidence,
            name="config.minimum_confidence",
        )

    @staticmethod
    def _validate_finite_number(value: float, *, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a finite number")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError(f"{name} must be finite")
        return numeric

    @classmethod
    def _validate_unit_interval(cls, value: float, *, name: str) -> float:
        numeric = cls._validate_finite_number(value, name=name)
        if not 0.0 <= numeric <= 1.0:
            raise ValueError(f"{name} must be inside [0, 1]")
        return numeric
