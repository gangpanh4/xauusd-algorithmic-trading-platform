"""Build independent evidence for trade-quality scoring.

This module translates existing analytical outputs into the normalized inputs
consumed by :class:`core.trade_quality.manager.TradeQualityManager`.  It does
not reuse probability confidence as a substitute for missing market evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import fmean

from core.feature_engineering.models import Feature, FeatureVector
from core.market_structure.models import MarketStructureResult
from core.probability_engine.models import ProbabilityResult


@dataclass(slots=True, frozen=True)
class TradeQualityEvidence:
    """Normalized, independent evidence consumed by trade-quality scoring."""

    trend_score: float = 0.0
    momentum_score: float = 5.0
    volatility_score: float = 5.0
    risk_reward_ratio: float = 2.0


class TradeQualityEvidenceBuilder:
    """Translate analytical outputs into trade-quality evidence.

    Missing momentum or volatility is represented by a configurable neutral
    score rather than by duplicating probability confidence.  Reward/risk can
    be supplied directly or calculated from planned entry, stop, and target
    prices.  The configured planned ratio remains a compatibility fallback
    until the pipeline supplies final price geometry.
    """

    _MOMENTUM_NAMES = (
        "momentum",
        "momentum_score",
        "directional_momentum",
        "trend_momentum",
    )
    _VOLATILITY_NAMES = (
        "volatility",
        "volatility_score",
        "normalized_volatility",
        "atr_percentile",
    )

    def __init__(
        self,
        *,
        neutral_missing_score: float = 5.0,
        planned_risk_reward_ratio: float = 2.0,
    ) -> None:
        self._neutral_missing_score = self._validate_score(
            neutral_missing_score,
            "neutral_missing_score",
        )
        self._planned_risk_reward_ratio = self._validate_positive(
            planned_risk_reward_ratio,
            "planned_risk_reward_ratio",
        )

    @staticmethod
    def _validate_score(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or not 0.0 <= normalized <= 10.0:
            raise ValueError(f"{name} must be finite and within [0, 10]")
        return normalized

    @staticmethod
    def _validate_positive(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized) or normalized <= 0.0:
            raise ValueError(f"{name} must be finite and greater than zero")
        return normalized

    @staticmethod
    def _normalize_unit_interval(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be a real number")
        normalized = float(value)
        if not isfinite(normalized):
            raise ValueError(f"{name} must be finite")
        return max(0.0, min(1.0, normalized))

    @classmethod
    def _feature_score(cls, feature: Feature) -> float:
        """Convert one normalized feature into the 0–10 scoring range."""
        if not isinstance(feature, Feature):
            raise TypeError("feature_vector must contain Feature instances")
        value = cls._normalize_unit_interval(
            feature.value,
            f"feature {feature.name!r} value",
        )
        confidence = cls._normalize_unit_interval(
            feature.confidence,
            f"feature {feature.name!r} confidence",
        )
        # Confidence attenuates evidence but never creates evidence by itself.
        return value * confidence * 10.0

    @classmethod
    def _collect_feature_score(
        cls,
        feature_vector: FeatureVector,
        *,
        names: tuple[str, ...],
        family: str,
    ) -> float | None:
        selected: list[Feature] = []
        seen_ids: set[int] = set()

        for name in names:
            feature = feature_vector.get(name)
            if feature is not None and id(feature) not in seen_ids:
                selected.append(feature)
                seen_ids.add(id(feature))

        for feature in feature_vector.by_family(family):
            if id(feature) not in seen_ids:
                selected.append(feature)
                seen_ids.add(id(feature))

        if not selected:
            return None

        return fmean(cls._feature_score(feature) for feature in selected)

    @classmethod
    def _risk_reward_from_geometry(
        cls,
        *,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
    ) -> float:
        entry = cls._validate_positive(entry_price, "entry_price")
        stop = cls._validate_positive(stop_loss_price, "stop_loss_price")
        target = cls._validate_positive(take_profit_price, "take_profit_price")

        risk = abs(entry - stop)
        reward = abs(target - entry)
        if risk == 0.0:
            raise ValueError("entry_price and stop_loss_price must differ")
        if reward == 0.0:
            raise ValueError("entry_price and take_profit_price must differ")

        stop_side = stop - entry
        target_side = target - entry
        if stop_side * target_side >= 0.0:
            raise ValueError(
                "stop_loss_price and take_profit_price must be on opposite "
                "sides of entry_price"
            )

        return reward / risk

    def build(
        self,
        *,
        market_structure: MarketStructureResult,
        feature_vector: FeatureVector,
        probability: ProbabilityResult,
        risk_reward_ratio: float | None = None,
        entry_price: float | None = None,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
    ) -> TradeQualityEvidence:
        """Build normalized trade-quality evidence.

        ``probability`` remains in the public signature for compatibility and
        type validation, but its confidence is deliberately not reused as
        momentum or volatility evidence.
        """
        if not isinstance(market_structure, MarketStructureResult):
            raise TypeError("market_structure must be MarketStructureResult")
        if not isinstance(feature_vector, FeatureVector):
            raise TypeError("feature_vector must be FeatureVector")
        if not isinstance(probability, ProbabilityResult):
            raise TypeError("probability must be ProbabilityResult")

        trend_score = (
            self._normalize_unit_interval(
                market_structure.structure_confidence,
                "market_structure.structure_confidence",
            )
            * 10.0
        )

        momentum_score = self._collect_feature_score(
            feature_vector,
            names=self._MOMENTUM_NAMES,
            family="momentum",
        )
        volatility_score = self._collect_feature_score(
            feature_vector,
            names=self._VOLATILITY_NAMES,
            family="volatility",
        )

        geometry_values = (entry_price, stop_loss_price, take_profit_price)
        geometry_supplied = any(value is not None for value in geometry_values)
        if geometry_supplied and not all(value is not None for value in geometry_values):
            raise ValueError(
                "entry_price, stop_loss_price, and take_profit_price must be "
                "provided together"
            )
        if risk_reward_ratio is not None and geometry_supplied:
            raise ValueError(
                "provide risk_reward_ratio or price geometry, not both"
            )

        if geometry_supplied:
            resolved_risk_reward = self._risk_reward_from_geometry(
                entry_price=entry_price,  # type: ignore[arg-type]
                stop_loss_price=stop_loss_price,  # type: ignore[arg-type]
                take_profit_price=take_profit_price,  # type: ignore[arg-type]
            )
        elif risk_reward_ratio is not None:
            resolved_risk_reward = self._validate_positive(
                risk_reward_ratio,
                "risk_reward_ratio",
            )
        else:
            resolved_risk_reward = self._planned_risk_reward_ratio

        return TradeQualityEvidence(
            trend_score=trend_score,
            momentum_score=(
                self._neutral_missing_score
                if momentum_score is None
                else momentum_score
            ),
            volatility_score=(
                self._neutral_missing_score
                if volatility_score is None
                else volatility_score
            ),
            risk_reward_ratio=resolved_risk_reward,
        )
