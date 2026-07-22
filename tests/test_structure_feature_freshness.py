from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.feature_engineering.evidence import FeatureEvidence
from core.feature_engineering.models import FeatureVector
from core.feature_engineering.structure import StructureFeatureExtractor
from core.market_structure.enums import BreakType, MarketTrend, SwingType, TrendDirection
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import BOSEvent, MarketStructureResult, SwingPoint


def test_structure_features_use_explicit_freshness_and_atr_units() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    swing = SwingPoint(
        timestamp=timestamp,
        index=0,
        price=100.0,
        swing_type=SwingType.HIGH,
        confirmation_index=0,
    )
    bos = BOSEvent(
        timestamp=timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=102.0,
        confirmation_index=1,
        break_distance=2.0,
        break_atr_multiple=0.5,
        quality=0.8,
        strength=0.7,
        power_score=0.6,
        structure_score=0.5,
        age=4,
    )
    structure = MarketStructureResult(
        timestamp=timestamp,
        last_swing=swing,
        last_bos=bos,
        last_choch=None,
        last_liquidity=None,
        current_trend=MarketTrend.BULLISH,
        structure_confidence=0.4,
        measurements=MarketStructureMeasurements(),
        bos_freshness=0.25,
    )
    vector = FeatureVector()

    StructureFeatureExtractor().extract(
        FeatureEvidence(market_structure=structure),
        vector,
    )

    assert vector.get("bos_break_atr_multiple").value == 0.5  # type: ignore[union-attr]
    assert vector.get("bos_freshness").value == 0.25  # type: ignore[union-attr]
    assert vector.get("bos_break_efficiency").value == pytest.approx(0.1)  # type: ignore[union-attr]
    assert vector.get("structure_confidence").confidence == 0.4  # type: ignore[union-attr]


def test_missing_events_export_presence_without_fabricated_metrics() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    structure = MarketStructureResult(
        timestamp=timestamp,
        last_swing=None,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
        current_trend=None,
        structure_confidence=0.0,
        measurements=MarketStructureMeasurements(),
    )
    vector = FeatureVector()

    StructureFeatureExtractor().extract(
        FeatureEvidence(market_structure=structure),
        vector,
    )

    assert vector.get("has_bos").value == 0.0  # type: ignore[union-attr]
    assert vector.get("has_choch").value == 0.0  # type: ignore[union-attr]
    assert vector.get("bos_break_distance") is None
    assert vector.get("choch_break_distance") is None
