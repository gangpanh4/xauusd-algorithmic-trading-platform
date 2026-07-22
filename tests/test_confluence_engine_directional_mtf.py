from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from core.confluence_engine.engine import ConfluenceEngine
from core.fair_value_gap_detector.enums import FairValueGapType
from core.market_structure.enums import (
    MarketTrend,
    OrderBlockType,
    TrendDirection,
)
from core.multi_timeframe.enums import (
    MarketBias,
    Timeframe,
    TimeframeAlignment,
)
from core.multi_timeframe.models import MultiTimeframeResult, TimeframeState


def _state(
    timeframe: Timeframe,
    *,
    bias: MarketBias,
    confidence: float = 0.8,
    structure=None,
    price_action=None,
) -> TimeframeState:
    return TimeframeState(
        timeframe=timeframe,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        bias=bias,
        alignment=TimeframeAlignment.ALIGNED,
        confidence=confidence,
        market_structure=structure,
        price_action=price_action,
    )


def _structure(*, direction: TrendDirection = TrendDirection.BULLISH):
    event = SimpleNamespace(
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        confirmation_index=10,
        direction=direction,
        quality=0.8,
        strength=0.8,
        structure_score=0.8,
        power_score=0.8,
        age=0,
    )
    liquidity = SimpleNamespace(
        quality=0.8,
        sweep_strength=0.8,
        reaction_strength=0.8,
        reclaim_strength=0.8,
        density=0.8,
        age=0,
    )
    return SimpleNamespace(
        last_bos=event,
        last_choch=None,
        last_liquidity=liquidity,
        current_trend=(
            MarketTrend.BULLISH
            if direction is TrendDirection.BULLISH
            else MarketTrend.BEARISH
        ),
        bos_freshness=1.0,
        choch_freshness=0.0,
        liquidity_freshness=1.0,
        freshness_decay_bars=8,
    )


def _price_action(
    *,
    block_type: OrderBlockType = OrderBlockType.BULLISH,
    gap_type: FairValueGapType = FairValueGapType.BULLISH,
):
    return SimpleNamespace(
        last_order_block=SimpleNamespace(block_type=block_type),
        last_fair_value_gap=SimpleNamespace(
            gap_type=gap_type,
            quality_score=0.8,
            age=0,
        ),
        price_action_confidence=0.8,
    )


def _result(
    *,
    htf_bias: MarketBias = MarketBias.BULLISH,
    execution_bias: MarketBias = MarketBias.BULLISH,
    alignment: TimeframeAlignment = TimeframeAlignment.ALIGNED,
    structure=None,
    price_action=None,
) -> MultiTimeframeResult:
    return MultiTimeframeResult(
        weekly=_state(Timeframe.WEEKLY, bias=htf_bias),
        daily=_state(Timeframe.DAILY, bias=htf_bias),
        h4=_state(Timeframe.H4, bias=htf_bias),
        h1=_state(Timeframe.H1, bias=htf_bias),
        m15=_state(Timeframe.M15, bias=execution_bias),
        m5=_state(
            Timeframe.M5,
            bias=execution_bias,
            structure=structure,
            price_action=price_action,
        ),
        overall_bias=htf_bias,
        overall_alignment=alignment,
        confidence=0.8,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_mtf_uses_six_distinct_factors() -> None:
    result = ConfluenceEngine().evaluate_multi_timeframe(
        _result(structure=_structure(), price_action=_price_action())
    )

    assert [factor.name for factor in result.factors] == [
        "Liquidity",
        "Break of Structure",
        "Change of Character",
        "Order Block",
        "Fair Value Gap",
        "Higher-Timeframe Agreement",
    ]
    assert result.factors[2].score == 0.0


def test_directionally_aligned_evidence_scores_strongly() -> None:
    result = ConfluenceEngine().evaluate_multi_timeframe(
        _result(structure=_structure(), price_action=_price_action())
    )

    assert result.approved
    assert result.confidence > 0.70


def test_opposing_order_block_and_gap_do_not_score() -> None:
    result = ConfluenceEngine().evaluate_multi_timeframe(
        _result(
            structure=_structure(),
            price_action=_price_action(
                block_type=OrderBlockType.BEARISH,
                gap_type=FairValueGapType.BEARISH,
            ),
        )
    )

    factors = {factor.name: factor for factor in result.factors}
    assert factors["Order Block"].score == 0.0
    assert factors["Fair Value Gap"].score == 0.0
    assert not result.approved


def test_opposing_higher_timeframes_zero_trend_factor() -> None:
    result = ConfluenceEngine().evaluate_multi_timeframe(
        _result(
            htf_bias=MarketBias.BEARISH,
            execution_bias=MarketBias.BULLISH,
            structure=_structure(),
            price_action=_price_action(),
        )
    )

    factors = {factor.name: factor for factor in result.factors}
    assert factors["Higher-Timeframe Agreement"].score == 0.0


def test_partial_alignment_reduces_htf_agreement() -> None:
    aligned = ConfluenceEngine().evaluate_multi_timeframe(
        _result(
            alignment=TimeframeAlignment.ALIGNED,
            structure=_structure(),
            price_action=_price_action(),
        )
    )
    partial = ConfluenceEngine().evaluate_multi_timeframe(
        _result(
            alignment=TimeframeAlignment.PARTIAL,
            structure=_structure(),
            price_action=_price_action(),
        )
    )

    aligned_factor = aligned.factors[-1]
    partial_factor = partial.factors[-1]
    assert partial_factor.score < aligned_factor.score


def test_event_freshness_reduces_structure_and_liquidity() -> None:
    fresh_structure = _structure()
    stale_structure = _structure()
    stale_structure.last_bos.age = 4
    stale_structure.last_liquidity.age = 4
    stale_structure.bos_freshness = 0.5
    stale_structure.liquidity_freshness = 0.5

    fresh = ConfluenceEngine().evaluate_multi_timeframe(
        _result(structure=fresh_structure, price_action=_price_action())
    )
    stale = ConfluenceEngine().evaluate_multi_timeframe(
        _result(structure=stale_structure, price_action=_price_action())
    )

    assert stale.factors[0].score < fresh.factors[0].score
    assert stale.factors[1].score < fresh.factors[1].score


def test_invalid_mtf_confidence_fails_closed() -> None:
    value = _result(structure=_structure(), price_action=_price_action())
    value.confidence = 1.1

    with pytest.raises(ValueError):
        ConfluenceEngine().evaluate_multi_timeframe(value)


def test_fvg_percentage_quality_is_normalized() -> None:
    price_action = _price_action()
    price_action.last_fair_value_gap.quality_score = 80.0

    result = ConfluenceEngine().evaluate_multi_timeframe(
        _result(structure=_structure(), price_action=price_action)
    )

    fvg = next(
        factor
        for factor in result.factors
        if factor.name == "Fair Value Gap"
    )
    assert fvg.score == pytest.approx(16.0)


def test_fvg_quality_above_percentage_scale_fails_closed() -> None:
    price_action = _price_action()
    price_action.last_fair_value_gap.quality_score = 100.1

    with pytest.raises(ValueError, match=r"\[0, 1\] or \[0, 100\]"):
        ConfluenceEngine().evaluate_multi_timeframe(
            _result(structure=_structure(), price_action=price_action)
        )
