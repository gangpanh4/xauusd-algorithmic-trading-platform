from __future__ import annotations

from datetime import UTC, datetime

import pytest

from core.data.models import MarketBar
from core.multi_timeframe.enums import MarketBias, Timeframe
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState
from core.strategies.context import StrategyContext
from core.strategies.smc_ict_context import PriceLocation
from core.strategies.smc_ict_context_builder import SMCICTContextBuilder


def _state(timeframe: Timeframe, bias: MarketBias) -> TimeframeState:
    return TimeframeState(timeframe=timeframe, bias=bias)


def _context(h4: MarketBias, h1: MarketBias) -> StrategyContext:
    timestamp = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    result = MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, MarketBias.NEUTRAL),
        daily=_state(Timeframe.DAILY, MarketBias.NEUTRAL),
        h4=_state(Timeframe.H4, h4),
        h1=_state(Timeframe.H1, h1),
        m15=_state(Timeframe.M15, MarketBias.NEUTRAL),
        m5=_state(Timeframe.M5, MarketBias.NEUTRAL),
        timestamp=timestamp,
    )
    return StrategyContext(
        multi_timeframe=result,
        current_bar=MarketBar(
            timestamp=timestamp,
            open=2400.0,
            high=2402.0,
            low=2398.0,
            close=2401.0,
            tick_volume=1,
        ),
        current_bar_index=10,
    )


def test_builder_preserves_aligned_htf_bias() -> None:
    result = SMCICTContextBuilder().build(
        _context(MarketBias.BULLISH, MarketBias.BULLISH)
    )
    assert result.higher_timeframe_bias is MarketBias.BULLISH
    assert result.current_price == 2401.0
    assert result.price_location is PriceLocation.UNKNOWN
    assert result.missing_capabilities == (
        "dealing_range_price_location",
        "displacement_detection",
        "session_context",
        "market_regime",
    )


def test_builder_returns_neutral_for_conflicting_bias() -> None:
    result = SMCICTContextBuilder().build(
        _context(MarketBias.BULLISH, MarketBias.BEARISH)
    )
    assert result.higher_timeframe_bias is MarketBias.NEUTRAL


def test_builder_rejects_wrong_type() -> None:
    with pytest.raises(TypeError, match="context must be StrategyContext"):
        SMCICTContextBuilder().build(object())
