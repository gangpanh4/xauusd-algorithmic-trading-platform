from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.data.models import MarketBar
from core.market_structure.enums import SwingType
from core.market_structure.liquidity_detector import LiquidityDetector
from core.market_structure.models import SwingPoint


def _swing(index: int, price: float, swing_type: SwingType) -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        index=index,
        price=price,
        swing_type=swing_type,
        confirmation_index=index,
        pivot_dominance=0.5,
    )


def _bar(index: int, *, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        open=100.0,
        high=high,
        low=low,
        close=close,
        tick_volume=100,
    )


def _seed_buy_side_sweep(detector: LiquidityDetector) -> None:
    detector.process_bar(
        _bar(1, high=100.0, low=99.0, close=99.5),
        bar_index=1,
        swing=_swing(1, 100.0, SwingType.HIGH),
    )
    assert detector.process_bar(
        _bar(2, high=101.0, low=98.0, close=99.0),
        bar_index=2,
        atr=1.0,
    ) is not None


def test_repeated_membership_check_does_not_scan_event_history() -> None:
    detector = LiquidityDetector()
    _seed_buy_side_sweep(detector)

    class NoIterationList(list):
        def __iter__(self):  # type: ignore[override]
            raise AssertionError("confirmed sweep history was scanned")

    detector.state.confirmed_sweeps = NoIterationList(
        detector.state.confirmed_sweeps
    )

    assert detector.process_bar(
        _bar(3, high=102.0, low=98.0, close=99.0),
        bar_index=3,
        atr=1.0,
    ) is None


def test_equal_price_levels_from_different_swings_are_independent() -> None:
    detector = LiquidityDetector()
    first = _swing(1, 100.0, SwingType.HIGH)
    second = _swing(2, 100.0, SwingType.HIGH)

    detector.process_bar(
        _bar(1, high=100.0, low=99.0, close=99.5),
        bar_index=1,
        swing=first,
    )
    detector.process_bar(
        _bar(2, high=100.0, low=99.0, close=99.5),
        bar_index=2,
        swing=second,
    )

    newest = detector.process_bar(
        _bar(3, high=101.0, low=98.0, close=99.0),
        bar_index=3,
        atr=1.0,
    )
    older = detector.process_bar(
        _bar(4, high=101.0, low=98.0, close=99.0),
        bar_index=4,
        atr=1.0,
    )

    assert newest is not None
    assert older is not None
    assert newest.liquidity_level.swing_point == second
    assert older.liquidity_level.swing_point == first
    assert detector.confirmed_sweep_count == 2


def test_external_state_mutation_rebuilds_index_once() -> None:
    detector = LiquidityDetector()
    _seed_buy_side_sweep(detector)
    event = detector.state.confirmed_sweeps[0]

    detector._swept_level_keys.clear()
    detector._indexed_sweep_count = 0

    assert detector._level_already_swept(event.liquidity_level) is True
    assert detector._indexed_sweep_count == 1
    assert detector._level_key(event.liquidity_level) in detector._swept_level_keys


def test_reset_clears_private_sweep_index() -> None:
    detector = LiquidityDetector()
    _seed_buy_side_sweep(detector)

    detector.reset()

    assert detector.state.confirmed_sweeps == []
    assert detector._swept_level_keys == set()
    assert detector._indexed_sweep_count == 0
