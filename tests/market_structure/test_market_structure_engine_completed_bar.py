from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from core.data.models import MarketBar
from core.market_structure.config import MarketStructureConfig
from core.market_structure.engine import MarketStructureEngine


def _bar(index: int, *, close: float = 100.0) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        tick_volume=100,
    )


def test_engine_calls_completed_bar_detectors_on_every_bar() -> None:
    engine = MarketStructureEngine(
        MarketStructureConfig(atr_period=2)
    )
    engine.bos_detector.process_bar = Mock(return_value=None)  # type: ignore[method-assign]
    engine.choch_detector.process_bar = Mock(return_value=None)  # type: ignore[method-assign]
    engine.liquidity_detector.process_bar = Mock(return_value=None)  # type: ignore[method-assign]

    bar = _bar(0)
    engine.process(bar)

    engine.bos_detector.process_bar.assert_called_once_with(
        bar,
        bar_index=0,
        swing=None,
        atr=None,
    )
    engine.choch_detector.process_bar.assert_called_once_with(
        bar,
        bar_index=0,
        swing=None,
        atr=None,
    )
    engine.liquidity_detector.process_bar.assert_called_once_with(
        bar,
        bar_index=0,
        swing=None,
        atr=None,
    )


def test_engine_does_not_use_legacy_swing_only_detector_methods() -> None:
    engine = MarketStructureEngine()
    engine.bos_detector.process = Mock(
        side_effect=AssertionError("legacy BOS path called")
    )  # type: ignore[method-assign]
    engine.choch_detector.process = Mock(
        side_effect=AssertionError("legacy CHOCH path called")
    )  # type: ignore[method-assign]
    engine.liquidity_detector.process = Mock(
        side_effect=AssertionError("legacy liquidity path called")
    )  # type: ignore[method-assign]

    engine.process(_bar(0))

    engine.bos_detector.process.assert_not_called()
    engine.choch_detector.process.assert_not_called()
    engine.liquidity_detector.process.assert_not_called()


def test_streaming_atr_requires_full_period_and_previous_close() -> None:
    engine = MarketStructureEngine(MarketStructureConfig(atr_period=2))

    engine.process(_bar(0, close=100.0))
    assert engine._calculate_atr() is None

    engine.process(_bar(1, close=101.0))
    assert engine._calculate_atr() is None

    engine.process(_bar(2, close=103.0))
    assert engine._calculate_atr() == 2.5
