"""Liquidity feature extraction from confirmed sweep-and-reclaim evidence."""

from __future__ import annotations

from .evidence import FeatureEvidence
from .extractor import FeatureExtractor
from .models import Feature, FeatureVector


class LiquidityFeatureExtractor(FeatureExtractor):
    """Extract unit-aware liquidity features."""

    def extract(
        self,
        evidence: FeatureEvidence,
        feature_vector: FeatureVector,
    ) -> None:
        market_structure = evidence.market_structure
        if market_structure is None:
            return

        confidence = market_structure.structure_confidence

        def add(name: str, value: float, *, normalized: bool) -> None:
            feature_vector.add(
                Feature(
                    name=name,
                    value=value,
                    confidence=confidence,
                    normalized=normalized,
                    family="liquidity",
                    source="market_structure",
                )
            )

        liquidity = market_structure.last_liquidity
        add(
            "has_liquidity",
            1.0 if liquidity is not None else 0.0,
            normalized=False,
        )
        add(
            "liquidity_score",
            market_structure.liquidity_score,
            normalized=True,
        )

        if liquidity is None:
            return

        add(
            "liquidity_sweep_distance",
            liquidity.sweep_distance,
            normalized=False,
        )
        add(
            "liquidity_atr_multiple",
            liquidity.atr_multiple,
            normalized=False,
        )
        add(
            "liquidity_sweep_strength",
            liquidity.sweep_strength,
            normalized=True,
        )
        add(
            "liquidity_reaction_strength",
            liquidity.reaction_strength,
            normalized=True,
        )
        add(
            "liquidity_reclaim_strength",
            liquidity.reclaim_strength,
            normalized=True,
        )
        add("liquidity_density", liquidity.density, normalized=True)
        add("liquidity_quality", liquidity.quality, normalized=True)
        add("liquidity_age", float(liquidity.age), normalized=False)
        add(
            "liquidity_freshness",
            market_structure.liquidity_freshness,
            normalized=True,
        )
        add(
            "liquidity_reclaim_efficiency",
            liquidity.atr_multiple
            * liquidity.reclaim_strength
            * market_structure.liquidity_freshness,
            normalized=False,
        )
