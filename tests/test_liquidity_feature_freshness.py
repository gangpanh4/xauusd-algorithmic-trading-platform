from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.feature_engineering.evidence import FeatureEvidence
from core.feature_engineering.liquidity import LiquidityFeatureExtractor
from core.feature_engineering.models import FeatureVector
from core.market_structure.enums import SwingType
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import (
    LiquidityLevel,
    LiquiditySweepEvent,
    MarketStructureResult,
    SwingPoint,
)


def test_liquidity_features_include_age_freshness_and_efficiency() -> None:
    timestamp = datetime(2025, 1, 1, tzinfo=UTC)
    swing = SwingPoint(
        timestamp=timestamp,
        index=0,
        price=100.0,
        swing_type=SwingType.HIGH,
        confirmation_index=0,
    )
    level = LiquidityLevel(
        timestamp=timestamp,
        price=100.0,
        swing_point=swing,
        is_buy_side=True,
    )
    sweep = LiquiditySweepEvent(
        timestamp=timestamp,
        liquidity_level=level,
        sweep_price=101.0,
        confirmation_index=1,
        sweep_distance=1.0,
        atr_multiple=0.5,
        reclaim_strength=0.8,
        age=3,
    )
    structure = MarketStructureResult(
        timestamp=timestamp,
        last_swing=swing,
        last_bos=None,
        last_choch=None,
        last_liquidity=sweep,
        current_trend=None,
        structure_confidence=0.4,
        measurements=MarketStructureMeasurements(),
        liquidity_freshness=0.25,
    )
    vector = FeatureVector()

    LiquidityFeatureExtractor().extract(
        FeatureEvidence(market_structure=structure),
        vector,
    )

    assert vector.get("liquidity_age").value == 3.0  # type: ignore[union-attr]
    assert vector.get("liquidity_freshness").value == 0.25  # type: ignore[union-attr]
    assert vector.get("liquidity_atr_multiple").normalized is False  # type: ignore[union-attr]
    assert vector.get("liquidity_reclaim_efficiency").value == pytest.approx(0.1)  # type: ignore[union-attr]


def test_missing_liquidity_only_exports_presence_and_score() -> None:
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

    LiquidityFeatureExtractor().extract(
        FeatureEvidence(market_structure=structure),
        vector,
    )

    assert vector.get("has_liquidity").value == 0.0  # type: ignore[union-attr]
    assert vector.get("liquidity_age") is None
