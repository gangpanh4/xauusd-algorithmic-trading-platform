from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from core.data.models import MarketBar
from core.fair_value_gap_detector.enums import FairValueGapStatus, FairValueGapType
from core.market_structure.enums import BreakType, OrderBlockType, SwingType, TrendDirection
from core.market_structure.models import BOSEvent, SwingPoint
from core.price_action.engine import PriceActionEngine


class FakeOrderBlockDetector:
    def __init__(self, *, blocks=(), events=()) -> None:
        self.blocks = list(blocks)
        self.state = SimpleNamespace(confirmed_events=list(events))
        self.calls: list[dict[str, object]] = []
        self.reset_calls = 0

    def process(self, **kwargs):
        self.calls.append(kwargs)
        return None

    def get_active_order_blocks(self):
        return list(self.blocks)

    def get_order_blocks(self):
        return list(self.blocks)

    def get_last_event(self):
        return self.state.confirmed_events[-1] if self.state.confirmed_events else None

    def reset(self):
        self.reset_calls += 1
        self.calls.clear()


class FakeFVGDetector:
    def __init__(self, *, candidates=()) -> None:
        self.state = SimpleNamespace(
            active_gaps=[],
            confirmed_gaps=[],
            pending_candidates=list(candidates),
            last_gap=(list(candidates)[-1] if candidates else None),
        )
        self.calls: list[list[MarketBar]] = []
        self.reset_calls = 0

    def process(self, bars):
        self.calls.append(list(bars))
        return None

    def reset(self):
        self.reset_calls += 1
        self.calls.clear()


def _bars(count: int = 12) -> list[MarketBar]:
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


def _break(bars: list[MarketBar], index: int = 5) -> BOSEvent:
    swing = SwingPoint(
        timestamp=bars[index - 1].timestamp,
        index=index - 1,
        price=bars[index - 1].high,
        swing_type=SwingType.HIGH,
        confirmation_index=index - 1,
    )
    return BOSEvent(
        timestamp=bars[index].timestamp,
        break_type=BreakType.BOS,
        direction=TrendDirection.BULLISH,
        swing_point=swing,
        break_price=bars[index].high,
        confirmation_index=index,
        quality=0.6,
    )


def _block(bars: list[MarketBar], index: int, *, direction=OrderBlockType.BULLISH):
    break_event = _break(bars, index)
    return SimpleNamespace(
        timestamp=bars[index].timestamp,
        confirmation_index=index,
        block_type=direction,
        trigger_break=break_event,
        trigger_liquidity=None,
    )


def _fvg(
    bars: list[MarketBar],
    index: int,
    *,
    direction=FairValueGapType.BULLISH,
    quality: float = 50.0,
    status=FairValueGapStatus.NEW,
):
    return SimpleNamespace(
        timestamp=bars[index].timestamp,
        gap_type=direction,
        quality_score=quality,
        status=status,
        third_bar=bars[index],
    )


def test_process_passes_full_bar_window_and_deduplicates_break_and_fvg() -> None:
    bars = _bars()
    order_blocks = FakeOrderBlockDetector()
    gaps = FakeFVGDetector()
    engine = PriceActionEngine(
        order_block_detector=order_blocks,
        fair_value_gap_detector=gaps,
    )
    break_event = _break(bars)

    engine.process(bars=bars, break_event=break_event, liquidity_event=None)
    engine.process(bars=bars, break_event=break_event, liquidity_event=None)

    assert len(order_blocks.calls) == 1
    assert order_blocks.calls[0]["bars"] == bars
    assert order_blocks.calls[0]["break_event"] is break_event
    assert len(gaps.calls) == 1
    assert gaps.calls[0] == bars


def test_newest_order_block_and_fvg_are_selected_not_last_appended() -> None:
    bars = _bars()
    newest_block = _block(bars, 9)
    older_block = _block(bars, 4)
    newest_gap = _fvg(bars, 10)
    older_gap = _fvg(bars, 3)
    engine = PriceActionEngine(
        order_block_detector=FakeOrderBlockDetector(
            blocks=(newest_block, older_block)
        ),
        fair_value_gap_detector=FakeFVGDetector(
            candidates=(newest_gap, older_gap)
        ),
    )

    result = engine.process(bars=bars, break_event=None, liquidity_event=None)

    assert result.last_order_block is newest_block
    assert result.last_fair_value_gap is newest_gap


def test_stale_and_non_tradable_evidence_is_excluded() -> None:
    bars = _bars(40)
    stale_block = _block(bars, 1)
    mitigated_gap = _fvg(bars, 39, status=FairValueGapStatus.MITIGATED)
    engine = PriceActionEngine(
        order_block_detector=FakeOrderBlockDetector(blocks=(stale_block,)),
        fair_value_gap_detector=FakeFVGDetector(candidates=(mitigated_gap,)),
        maximum_evidence_age_bars=16,
        freshness_half_life_bars=8,
    )

    result = engine.process(bars=bars, break_event=None, liquidity_event=None)

    assert result.last_order_block is None
    assert result.last_fair_value_gap is None
    assert result.price_action_confidence == 0.0


def test_confidence_uses_quality_freshness_and_directional_conflict() -> None:
    bars = _bars(12)
    block = _block(bars, 3)
    event = SimpleNamespace(
        order_block=block,
        confirmation_index=3,
        timestamp=bars[3].timestamp,
        analysis=SimpleNamespace(total_score=0.6),
    )
    agreeing_gap = _fvg(bars, 11, quality=50.0)
    conflicting_gap = _fvg(
        bars,
        11,
        direction=FairValueGapType.BEARISH,
        quality=50.0,
    )

    agreeing = PriceActionEngine(
        order_block_detector=FakeOrderBlockDetector(
            blocks=(block,), events=(event,)
        ),
        fair_value_gap_detector=FakeFVGDetector(candidates=(agreeing_gap,)),
        freshness_half_life_bars=8,
    ).process(bars=bars, break_event=None, liquidity_event=None)

    conflicting = PriceActionEngine(
        order_block_detector=FakeOrderBlockDetector(
            blocks=(block,), events=(event,)
        ),
        fair_value_gap_detector=FakeFVGDetector(candidates=(conflicting_gap,)),
        freshness_half_life_bars=8,
    ).process(bars=bars, break_event=None, liquidity_event=None)

    # OB base quality is mean(analysis=0.6, break=0.6), then one half-life old.
    # Combined aligned confidence = (0.3 * 0.6) + (0.5 * 0.4) = 0.38.
    assert agreeing.price_action_confidence == pytest.approx(0.38)
    assert conflicting.price_action_confidence == pytest.approx(0.19)


def test_real_fvg_detector_candidate_is_exposed_without_fabricated_confirmation() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    bars = [
        MarketBar(start, 100.0, 101.0, 99.0, 100.0, 100),
        MarketBar(start + timedelta(minutes=15), 101.0, 104.0, 101.0, 104.0, 100),
        MarketBar(start + timedelta(minutes=30), 105.0, 106.0, 103.0, 105.0, 100),
    ]
    engine = PriceActionEngine(order_block_detector=FakeOrderBlockDetector())

    result = engine.process(bars=bars, break_event=None, liquidity_event=None)

    assert result.last_fair_value_gap is not None
    assert result.last_fair_value_gap.gap_type is FairValueGapType.BULLISH
    assert engine.fair_value_gap_detector.state.confirmed_gaps == []


def test_reset_clears_detectors_and_deduplication_state() -> None:
    bars = _bars()
    order_blocks = FakeOrderBlockDetector()
    gaps = FakeFVGDetector()
    engine = PriceActionEngine(
        order_block_detector=order_blocks,
        fair_value_gap_detector=gaps,
    )
    break_event = _break(bars)

    engine.process(bars=bars, break_event=break_event, liquidity_event=None)
    engine.reset()
    engine.process(bars=bars, break_event=break_event, liquidity_event=None)

    assert order_blocks.reset_calls == 1
    assert gaps.reset_calls == 1
    assert len(order_blocks.calls) == 1
    assert len(gaps.calls) == 1


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"freshness_half_life_bars": 0}, ValueError),
        ({"freshness_half_life_bars": True}, TypeError),
        ({"maximum_evidence_age_bars": 0}, ValueError),
        (
            {"freshness_half_life_bars": 16, "maximum_evidence_age_bars": 8},
            ValueError,
        ),
    ],
)
def test_configuration_fails_closed(kwargs, error) -> None:
    with pytest.raises(error):
        PriceActionEngine(**kwargs)


def test_invalid_bar_window_fails_closed() -> None:
    engine = PriceActionEngine(
        order_block_detector=FakeOrderBlockDetector(),
        fair_value_gap_detector=FakeFVGDetector(),
    )
    bars = _bars()

    with pytest.raises(ValueError, match="strictly increasing"):
        engine.process(
            bars=[bars[1], bars[0]],
            break_event=None,
            liquidity_event=None,
        )
