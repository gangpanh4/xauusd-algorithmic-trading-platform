"""Structure feature extraction from confirmed market-structure evidence."""

from __future__ import annotations

from .encoders import encode_trend
from .evidence import FeatureEvidence
from .extractor import FeatureExtractor
from .models import Feature, FeatureVector


class StructureFeatureExtractor(FeatureExtractor):
    """Extract unit-aware structure features for downstream scoring."""

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
                    family="structure",
                    source="market_structure",
                )
            )

        # The feature's own confidence must reflect the structure engine rather
        # than claiming perfect certainty on every bar.
        add(
            "structure_confidence",
            market_structure.structure_confidence,
            normalized=True,
        )
        add("swing_score", market_structure.swing_score, normalized=True)
        add("bos_score", market_structure.bos_score, normalized=True)
        add("choch_score", market_structure.choch_score, normalized=True)

        if market_structure.current_trend is not None:
            add(
                "current_trend",
                encode_trend(market_structure.current_trend),
                normalized=False,
            )

        bos = market_structure.last_bos
        add("has_bos", 1.0 if bos is not None else 0.0, normalized=False)
        if bos is not None:
            add("bos_break_distance", bos.break_distance, normalized=False)
            add(
                "bos_break_atr_multiple",
                bos.break_atr_multiple,
                normalized=False,
            )
            add("bos_quality", bos.quality, normalized=True)
            add("bos_strength", bos.strength, normalized=True)
            add("bos_power_score", bos.power_score, normalized=True)
            add("bos_structure_score", bos.structure_score, normalized=True)
            add("bos_age", float(bos.age), normalized=False)
            add(
                "bos_composite_score",
                (
                    bos.quality
                    + bos.strength
                    + bos.power_score
                    + bos.structure_score
                )
                / 4.0,
                normalized=True,
            )
            add(
                "bos_freshness",
                market_structure.bos_freshness,
                normalized=True,
            )
            # Efficiency is now dimensionless and comparable across volatility
            # regimes. Raw price distance remains available separately.
            add(
                "bos_break_efficiency",
                bos.break_atr_multiple
                * bos.quality
                * market_structure.bos_freshness,
                normalized=False,
            )

        choch = market_structure.last_choch
        add(
            "has_choch",
            1.0 if choch is not None else 0.0,
            normalized=False,
        )
        if choch is not None:
            add("choch_break_distance", choch.break_distance, normalized=False)
            add(
                "choch_break_atr_multiple",
                choch.break_atr_multiple,
                normalized=False,
            )
            add("choch_quality", choch.quality, normalized=True)
            add("choch_strength", choch.strength, normalized=True)
            add("choch_power_score", choch.power_score, normalized=True)
            add("choch_structure_score", choch.structure_score, normalized=True)
            add("choch_age", float(choch.age), normalized=False)
            add(
                "choch_freshness",
                market_structure.choch_freshness,
                normalized=True,
            )
            add(
                "choch_break_efficiency",
                choch.break_atr_multiple
                * choch.quality
                * market_structure.choch_freshness,
                normalized=False,
            )
