from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import exp

import pytest

from core.data.models import MarketBar
from core.market_structure.config import (
    BOSDetectorConfig,
    CHOCHDetectorConfig,
    LiquidityDetectorConfig,
    MarketStructureConfig,
    SwingDetectorConfig,
)
from core.market_structure.engine import MarketStructureEngine
from core.market_structure.enums import BreakType, SwingType, TrendDirection
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    LiquidityLevel,
    LiquiditySweepEvent,
    SwingPoint,
)


def _bar(index: int) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * index),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        tick_volume=100,
    )


def _swing() -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        index=0,
        price=100.0,
        swing_type=SwingType.HIGH,
        confirmation_index=0,
    )


def _events() -> tuple[BOSEvent, CHOCHEvent, LiquiditySweepEvent]:
    swing = _swing()
    bos = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=101.0,
        confirmation_index=0,
        break_distance=1.0,
    )
    choch = CHOCHEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.CHOCH,
        direction=TrendDirection.BEARISH,
        swing_point=swing,
        break_price=99.0,
        confirmation_index=0,
        break_distance=1.0,
    )
    level = LiquidityLevel(
        timestamp=swing.timestamp,
        price=swing.price,
        swing_point=swing,
        is_buy_side=True,
    )
    liquidity = LiquiditySweepEvent(
        timestamp=swing.timestamp,
        liquidity_level=level,
        sweep_price=101.0,
        confirmation_index=0,
        sweep_distance=1.0,
    )
    return bos, choch, liquidity


def test_engine_injects_all_composed_detector_configs() -> None:
    config = MarketStructureConfig(
        swing=SwingDetectorConfig(pivot_left=2, pivot_right=2),
        bos=BOSDetectorConfig(minimum_break_distance=0.1),
        choch=CHOCHDetectorConfig(minimum_break_distance=0.2),
        liquidity=LiquidityDetectorConfig(minimum_sweep_distance=0.3),
        maximum_bar_history=25,
    )

    engine = MarketStructureEngine(config)

    assert engine.swing_detector.config is config.swing
    assert engine.bos_detector.config is config.bos
    assert engine.choch_detector.config is config.choch
    assert engine.liquidity_detector.config is config.liquidity
    assert engine.bar_history.maxlen == 25


def test_engine_preserves_legacy_swing_config_construction() -> None:
    swing_config = SwingDetectorConfig(pivot_left=1, pivot_right=1)

    engine = MarketStructureEngine(swing_config)

    assert engine.config.swing is swing_config
    assert engine.swing_detector.config is swing_config


def test_engine_ages_events_by_completed_bar_index() -> None:
    engine = MarketStructureEngine(
        MarketStructureConfig(
            pivot_left=3,
            pivot_right=3,
            maximum_bos_age_bars=5,
            maximum_choch_age_bars=5,
            maximum_liquidity_age_bars=5,
        )
    )
    bos, choch, liquidity = _events()
    engine.bos_detector.state.last_break = bos
    engine.bos_detector.state.confirmed_breaks.append(bos)
    engine.choch_detector.state.last_change = choch
    engine.choch_detector.state.confirmed_changes.append(choch)
    engine.liquidity_detector.state.last_sweep = liquidity
    engine.liquidity_detector.state.confirmed_sweeps.append(liquidity)
    engine.swing_detector.state.processed_bar_count = 2

    result = engine.process(_bar(2))

    assert result.last_bos is not None and result.last_bos.age == 2
    assert result.last_choch is not None and result.last_choch.age == 2
    assert result.last_liquidity is not None
    assert result.last_liquidity.age == 2
    assert result.measurements.bos_age == 2
    assert result.measurements.choch_age == 2
    assert result.measurements.liquidity_age == 2
    assert result.bos_freshness == pytest.approx(exp(-2 / 8))
    assert result.choch_freshness == pytest.approx(exp(-2 / 8))
    assert result.liquidity_freshness == pytest.approx(exp(-2 / 8))
    assert result.freshness_decay_bars == 8
    assert engine.bos_detector.state.confirmed_breaks[-1].age == 2


def test_engine_expires_stale_events_without_erasing_history() -> None:
    engine = MarketStructureEngine(
        MarketStructureConfig(
            maximum_bos_age_bars=1,
            maximum_choch_age_bars=1,
            maximum_liquidity_age_bars=1,
        )
    )
    bos, choch, liquidity = _events()
    engine.bos_detector.state.last_break = bos
    engine.bos_detector.state.confirmed_breaks.append(bos)
    engine.choch_detector.state.last_change = choch
    engine.choch_detector.state.confirmed_changes.append(choch)
    engine.liquidity_detector.state.last_sweep = liquidity
    engine.liquidity_detector.state.confirmed_sweeps.append(liquidity)
    engine.swing_detector.state.processed_bar_count = 2

    result = engine.process(_bar(2))

    assert result.last_bos is None
    assert result.last_choch is None
    assert result.last_liquidity is None
    assert len(engine.bos_detector.state.confirmed_breaks) == 1
    assert len(engine.choch_detector.state.confirmed_changes) == 1
    assert len(engine.liquidity_detector.state.confirmed_sweeps) == 1


def test_engine_can_disable_expiry_while_still_aging_events() -> None:
    engine = MarketStructureEngine(
        MarketStructureConfig(
            maximum_bos_age_bars=1,
            expire_stale_events=False,
        )
    )
    bos, _, _ = _events()
    engine.bos_detector.state.last_break = bos
    engine.bos_detector.state.confirmed_breaks.append(bos)
    engine.swing_detector.state.processed_bar_count = 3

    result = engine.process(_bar(3))

    assert result.last_bos is not None
    assert result.last_bos.age == 3
