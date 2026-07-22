from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.data.models import MarketBar
from core.fair_value_gap_detector.enums import FairValueGapType
from core.market_structure.enums import (
    BreakType,
    MarketTrend,
    OrderBlockType,
    TrendDirection,
)
from core.multi_timeframe.analyzer import TimeframeAnalyzer
from core.multi_timeframe.enums import MarketBias, Timeframe, TimeframeAlignment


class FakeMarketStructureEngine:
    def __init__(self, result: SimpleNamespace) -> None:
        self.result = result
        self.processed: list[MarketBar] = []
        self.reset_calls = 0

    def process(self, bar: MarketBar) -> SimpleNamespace:
        self.processed.append(bar)
        return self.result

    def reset(self) -> None:
        self.reset_calls += 1
        self.processed.clear()


class FakePriceActionEngine:
    def __init__(self, result: SimpleNamespace) -> None:
        self.result = result
        self.break_events: list[object | None] = []
        self.reset_calls = 0

    def process(self, *, bars, break_event, liquidity_event):
        self.break_events.append(break_event)
        return self.result

    def reset(self) -> None:
        self.reset_calls += 1
        self.break_events.clear()


def _bars(count: int = 3) -> list[MarketBar]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return [
        MarketBar(
            timestamp=start + timedelta(minutes=15 * index),
            open=100.0 + index,
            high=101.0 + index,
            low=99.0 + index,
            close=100.5 + index,
            tick_volume=100,
        )
        for index in range(count)
    ]


def _break(
    *,
    direction: TrendDirection,
    confirmation_index: int,
    break_type: BreakType = BreakType.BOS,
):
    return SimpleNamespace(
        direction=direction,
        confirmation_index=confirmation_index,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC)
        + timedelta(minutes=15 * confirmation_index),
        break_type=break_type,
    )


def _structure(
    *,
    trend: MarketTrend = MarketTrend.BULLISH,
    bos=None,
    choch=None,
    confidence: float = 0.8,
):
    return SimpleNamespace(
        current_trend=trend,
        last_bos=bos,
        last_choch=choch,
        last_liquidity=None,
        structure_confidence=confidence,
    )


def _price_action(
    *,
    order_block=None,
    fair_value_gap=None,
    confidence: float = 0.0,
):
    return SimpleNamespace(
        last_order_block=order_block,
        last_fair_value_gap=fair_value_gap,
        price_action_confidence=confidence,
    )


def _analyzer(structure, price_action, **kwargs) -> TimeframeAnalyzer:
    return TimeframeAnalyzer(
        market_structure_engine=FakeMarketStructureEngine(structure),
        price_action_engine=FakePriceActionEngine(price_action),
        **kwargs,
    )


def test_consistent_directional_sources_are_aligned() -> None:
    bos = _break(direction=TrendDirection.BULLISH, confirmation_index=2)
    analyzer = _analyzer(
        _structure(bos=bos),
        _price_action(
            order_block=SimpleNamespace(block_type=OrderBlockType.BULLISH),
            fair_value_gap=SimpleNamespace(gap_type=FairValueGapType.BULLISH),
            confidence=1.0,
        ),
    )

    result = analyzer.analyze(timeframe=Timeframe.H4, bars=_bars())

    assert result.bias is MarketBias.BULLISH
    assert result.alignment is TimeframeAlignment.ALIGNED
    assert result.confidence == pytest.approx(0.86)
    assert result.metadata["agreement_ratio"] == pytest.approx(1.0)
    assert result.metadata["directional_source_count"] == 4


def test_strong_opposition_is_conflict() -> None:
    bearish_break = _break(direction=TrendDirection.BEARISH, confirmation_index=2)
    analyzer = _analyzer(
        _structure(trend=MarketTrend.BULLISH, bos=bearish_break),
        _price_action(
            order_block=SimpleNamespace(block_type=OrderBlockType.BEARISH),
            fair_value_gap=SimpleNamespace(gap_type=FairValueGapType.BEARISH),
            confidence=1.0,
        ),
    )

    result = analyzer.analyze(timeframe=Timeframe.H1, bars=_bars())

    assert result.bias is MarketBias.BULLISH
    assert result.alignment is TimeframeAlignment.CONFLICT
    assert result.metadata["bullish_weight"] == pytest.approx(3.0)
    assert result.metadata["bearish_weight"] == pytest.approx(4.5)
    assert result.confidence == pytest.approx(0.43)


def test_dominant_direction_with_minor_opposition_is_partial() -> None:
    bullish_break = _break(direction=TrendDirection.BULLISH, confirmation_index=2)
    analyzer = _analyzer(
        _structure(trend=MarketTrend.BULLISH, bos=bullish_break),
        _price_action(
            fair_value_gap=SimpleNamespace(gap_type=FairValueGapType.BEARISH),
            confidence=0.5,
        ),
    )

    result = analyzer.analyze(timeframe=Timeframe.M15, bars=_bars())

    assert result.bias is MarketBias.BULLISH
    assert result.alignment is TimeframeAlignment.PARTIAL
    assert result.metadata["agreement_ratio"] == pytest.approx(5.0 / 6.0)


def test_single_structural_source_is_partial_and_not_halved_as_missing_evidence() -> None:
    analyzer = _analyzer(
        _structure(trend=MarketTrend.BEARISH, confidence=0.8),
        _price_action(confidence=0.0),
    )

    result = analyzer.analyze(timeframe=Timeframe.DAILY, bars=_bars())

    assert result.bias is MarketBias.BEARISH
    assert result.alignment is TimeframeAlignment.PARTIAL
    assert result.confidence == pytest.approx(0.68)


def test_latest_break_and_price_action_can_establish_bias_when_trend_unknown() -> None:
    bullish_break = _break(direction=TrendDirection.BULLISH, confirmation_index=2)
    analyzer = _analyzer(
        _structure(trend=MarketTrend.UNKNOWN, bos=bullish_break),
        _price_action(
            fair_value_gap=SimpleNamespace(gap_type=FairValueGapType.BULLISH),
            confidence=0.7,
        ),
    )

    result = analyzer.analyze(timeframe=Timeframe.M5, bars=_bars())

    assert result.bias is MarketBias.BULLISH
    assert result.alignment is TimeframeAlignment.ALIGNED


def test_newest_confirmed_break_is_forwarded_to_price_action() -> None:
    bos = _break(
        direction=TrendDirection.BULLISH,
        confirmation_index=1,
        break_type=BreakType.BOS,
    )
    choch = _break(
        direction=TrendDirection.BEARISH,
        confirmation_index=2,
        break_type=BreakType.CHOCH,
    )
    market_structure = FakeMarketStructureEngine(
        _structure(trend=MarketTrend.UNKNOWN, bos=bos, choch=choch)
    )
    price_action = FakePriceActionEngine(_price_action())
    analyzer = TimeframeAnalyzer(
        market_structure_engine=market_structure,
        price_action_engine=price_action,
    )

    result = analyzer.analyze(timeframe=Timeframe.H1, bars=_bars())

    assert price_action.break_events == [choch]
    assert result.bias is MarketBias.BEARISH
    assert result.metadata["latest_break_type"] == "CHOCH"


def test_invalid_configuration_and_bars_fail_closed() -> None:
    with pytest.raises(ValueError, match="alignment_threshold"):
        TimeframeAnalyzer(alignment_threshold=0.5)
    with pytest.raises(ValueError, match="minimum_aligned_sources"):
        TimeframeAnalyzer(minimum_aligned_sources=0)

    analyzer = _analyzer(_structure(), _price_action())
    duplicate = _bars(2)
    duplicate[1] = MarketBar(
        timestamp=duplicate[0].timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        tick_volume=100,
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        analyzer.analyze(timeframe=Timeframe.H4, bars=duplicate)


def test_reset_resets_both_owned_engines() -> None:
    market_structure = FakeMarketStructureEngine(_structure())
    price_action = FakePriceActionEngine(_price_action())
    analyzer = TimeframeAnalyzer(
        market_structure_engine=market_structure,
        price_action_engine=price_action,
    )

    analyzer.reset()

    assert market_structure.reset_calls == 1
    assert price_action.reset_calls == 1
