from __future__ import annotations

from datetime import UTC, datetime

from core.market_structure.enums import BreakType, SwingType, TrendDirection
from core.market_structure.measurements import MarketStructureMeasurements
from core.market_structure.models import (
    BOSEvent,
    CHOCHEvent,
    MarketStructureResult,
    SwingPoint,
)


def _swing() -> SwingPoint:
    return SwingPoint(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        index=0,
        price=100.0,
        swing_type=SwingType.HIGH,
        confirmation_index=0,
    )


def test_break_atr_multiple_is_backward_compatible() -> None:
    swing = _swing()
    bos = BOSEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=101.0,
        confirmation_index=1,
    )
    choch = CHOCHEvent(
        timestamp=swing.timestamp,
        break_type=BreakType.CHOCH,
        direction=TrendDirection.BEARISH,
        swing_point=swing,
        break_price=99.0,
        confirmation_index=1,
    )

    assert bos.break_atr_multiple == 0.0
    assert choch.break_atr_multiple == 0.0


def test_market_structure_result_exposes_explicit_freshness_defaults() -> None:
    result = MarketStructureResult(
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        last_swing=None,
        last_bos=None,
        last_choch=None,
        last_liquidity=None,
        current_trend=None,
        structure_confidence=0.0,
        measurements=MarketStructureMeasurements(),
    )

    assert result.bos_freshness == 0.0
    assert result.choch_freshness == 0.0
    assert result.liquidity_freshness == 0.0
    assert result.freshness_decay_bars == 1
