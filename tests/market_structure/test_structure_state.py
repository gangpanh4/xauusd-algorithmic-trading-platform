from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from core.data.models import MarketBar
from core.market_structure.config import SwingDetectorConfig
from core.market_structure.engine import MarketStructureEngine
from core.market_structure.enums import (
    MarketTrend,
    SwingClassification,
    SwingType,
)
from core.market_structure.models import (
    LiquidityLevel,
    StructureState,
    SwingPoint,
)


def _swing(
    index: int,
    price: float,
    swing_type: SwingType,
    classification: SwingClassification,
) -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=5 * index),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index + 1,
        classification=classification,
    )


def test_structure_state_exposes_confirmed_sequence_and_protected_level() -> None:
    engine = MarketStructureEngine(
        SwingDetectorConfig(
            pivot_left=1,
            pivot_right=1,
            atr_validation=False,
            minimum_swing_distance=0.0,
        )
    )
    high = _swing(
        1,
        3300.0,
        SwingType.HIGH,
        SwingClassification.UNCLASSIFIED,
    )
    low = _swing(
        2,
        3280.0,
        SwingType.LOW,
        SwingClassification.UNCLASSIFIED,
    )
    higher_high = _swing(
        3,
        3310.0,
        SwingType.HIGH,
        SwingClassification.HIGHER_HIGH,
    )

    engine.swing_detector.state.confirmed_swings[:] = [
        high,
        low,
        higher_high,
    ]
    engine.swing_detector.state.last_swing = higher_high
    engine.bos_detector.state.current_trend = MarketTrend.BULLISH
    engine.bos_detector.state.protected_swing = low
    engine.liquidity_detector.state.liquidity_levels.append(
        LiquidityLevel(
            timestamp=higher_high.timestamp,
            price=higher_high.price,
            swing_point=higher_high,
            is_buy_side=True,
        )
    )

    state = engine._build_structure_state(
        timestamp=higher_high.timestamp,
        current_bar_index=4,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
    )

    assert isinstance(state, StructureState)
    assert state.confirmed_swings == (high, low, higher_high)
    assert state.trend is MarketTrend.BULLISH
    assert state.last_swing is higher_high
    assert state.last_high is higher_high
    assert state.last_low is low
    assert state.protected_low is low
    assert state.protected_high is None
    assert state.last_confirmation_index == higher_high.confirmation_index
    assert len(state.tracked_liquidity_levels) == 1


def test_structure_state_rejects_wrong_protected_swing_type() -> None:
    high = _swing(
        1,
        3300.0,
        SwingType.HIGH,
        SwingClassification.UNCLASSIFIED,
    )

    with pytest.raises(
        ValueError,
        match="protected_low must reference a LOW swing",
    ):
        StructureState(
            timestamp=high.timestamp,
            current_bar_index=2,
            trend=MarketTrend.UNKNOWN,
            protected_low=high,
        )


def test_engine_result_contains_structure_state() -> None:
    engine = MarketStructureEngine(
        SwingDetectorConfig(
            pivot_left=1,
            pivot_right=1,
            atr_validation=False,
            minimum_swing_distance=0.0,
        )
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        MarketBar(start, 100.0, 101.0, 99.0, 100.0, 100),
        MarketBar(
            start + timedelta(minutes=5),
            101.0,
            105.0,
            100.0,
            104.0,
            100,
        ),
        MarketBar(
            start + timedelta(minutes=10),
            100.0,
            102.0,
            99.0,
            100.0,
            100,
        ),
    ]

    result = None
    for bar in bars:
        result = engine.process(bar)

    assert result is not None
    assert result.structure_state is not None
    assert result.structure_state.timestamp == bars[-1].timestamp
    assert result.structure_state.last_swing == result.last_swing
    assert result.structure_state.confirmed_swings == (
        engine.swing_detector.get_swings()
    )
