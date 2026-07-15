"""
Unit tests for the Liquidity Sweep Detection Engine.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.market_structure.config import (
    LiquidityDetectorConfig,
)
from core.market_structure.enums import (
    SwingType,
)
from core.market_structure.liquidity_detector import (
    LiquidityDetector,
)
from core.market_structure.models import (
    SwingPoint,
)


def make_swing(
    *,
    index: int,
    price: float,
    swing_type: SwingType,
) -> SwingPoint:
    """
    Create a confirmed SwingPoint for testing.
    """

    return SwingPoint(
        timestamp=datetime.now(UTC),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index,
    )


def test_detector_initializes_with_default_config() -> None:
    """
    Detector should initialize correctly.
    """

    detector = LiquidityDetector()

    assert isinstance(
        detector.config,
        LiquidityDetectorConfig,
    )
    assert detector.state.liquidity_levels == []
    assert detector.state.confirmed_sweeps == []
    assert detector.state.last_sweep is None

def test_reset_clears_runtime_state() -> None:
    """
    Reset should restore the detector state.
    """

    detector = LiquidityDetector()

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector.process(swing)

    detector.reset()

    assert detector.state.liquidity_levels == []
    assert detector.state.confirmed_sweeps == []
    assert detector.state.last_sweep is None
    assert detector.state.processed_swing_count == 0

def test_add_swing_creates_liquidity_level() -> None:
    """
    A confirmed swing should create a liquidity level.
    """

    detector = LiquidityDetector()

    swing = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector.process(swing)

    assert len(detector.state.liquidity_levels) == 1

    level = detector.state.liquidity_levels[0]

    assert level.price == 100.0
    assert level.swing_point == swing
    assert level.is_buy_side is True
    assert detector.state.processed_swing_count == 1

def test_detects_buy_side_liquidity_sweep() -> None:
    """
    Breaking above a previous swing high should create
    a buy-side liquidity sweep.
    """

    detector = LiquidityDetector()

    first_high = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector.process(first_high)

    second_high = make_swing(
        index=2,
        price=105.0,
        swing_type=SwingType.HIGH,
    )

    result = detector.process(second_high)

    assert result is not None
    assert result.liquidity_level.price == 100.0
    assert result.sweep_price == 105.0
    assert detector.state.last_sweep == result

def test_detects_sell_side_liquidity_sweep() -> None:
    """
    Breaking below a previous swing low should create
    a sell-side liquidity sweep.
    """

    detector = LiquidityDetector()

    first_low = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.LOW,
    )

    detector.process(first_low)

    second_low = make_swing(
        index=2,
        price=95.0,
        swing_type=SwingType.LOW,
    )

    result = detector.process(second_low)

    assert result is not None
    assert result.liquidity_level.price == 100.0
    assert result.sweep_price == 95.0
    assert detector.state.last_sweep == result

def test_duplicate_sweep_is_rejected() -> None:
    """
    Duplicate liquidity sweeps should not be created.
    """

    detector = LiquidityDetector()

    first_high = make_swing(
        index=1,
        price=100.0,
        swing_type=SwingType.HIGH,
    )

    detector.process(first_high)

    sweep_high = make_swing(
        index=2,
        price=105.0,
        swing_type=SwingType.HIGH,
    )

    first = detector.process(sweep_high)
    second = detector.process(sweep_high)

    assert first is not None
    assert second is None

def test_get_last_sweep() -> None:
    """
    get_last_sweep should return the most recent sweep.
    """

    detector = LiquidityDetector()

    detector.process(
        make_swing(
            index=1,
            price=100.0,
            swing_type=SwingType.HIGH,
        )
    )

    event = detector.process(
        make_swing(
            index=2,
            price=105.0,
            swing_type=SwingType.HIGH,
        )
    )

    assert detector.get_last_sweep() == event

def test_get_sweeps() -> None:
    """
    get_sweeps should return all confirmed sweeps.
    """

    detector = LiquidityDetector()

    detector.process(
        make_swing(
            index=1,
            price=100.0,
            swing_type=SwingType.HIGH,
        )
    )

    event = detector.process(
        make_swing(
            index=2,
            price=105.0,
            swing_type=SwingType.HIGH,
        )
    )

    assert detector.get_sweeps() == [event]

def test_get_state() -> None:
    """
    get_state should return the detector runtime state.
    """

    detector = LiquidityDetector()

    assert detector.get_state() is detector.state