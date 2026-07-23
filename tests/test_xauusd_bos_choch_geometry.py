from __future__ import annotations

from core.market_structure.enums import TrendDirection
from core.strategies.xauusd_bos_choch import XAUUSDBOSCHOCHStrategy


def test_buy_target_must_be_above_invalidation() -> None:
    assert XAUUSDBOSCHOCHStrategy._target_is_beyond_invalidation(
        direction=TrendDirection.BULLISH,
        invalidation_price=4100.0,
        target_price=4120.0,
    )
    assert not XAUUSDBOSCHOCHStrategy._target_is_beyond_invalidation(
        direction=TrendDirection.BULLISH,
        invalidation_price=4100.0,
        target_price=4090.0,
    )
    assert not XAUUSDBOSCHOCHStrategy._target_is_beyond_invalidation(
        direction=TrendDirection.BULLISH,
        invalidation_price=4100.0,
        target_price=4100.0,
    )


def test_sell_target_must_be_below_invalidation() -> None:
    assert XAUUSDBOSCHOCHStrategy._target_is_beyond_invalidation(
        direction=TrendDirection.BEARISH,
        invalidation_price=4100.0,
        target_price=4080.0,
    )
    assert not XAUUSDBOSCHOCHStrategy._target_is_beyond_invalidation(
        direction=TrendDirection.BEARISH,
        invalidation_price=4100.0,
        target_price=4120.0,
    )
    assert not XAUUSDBOSCHOCHStrategy._target_is_beyond_invalidation(
        direction=TrendDirection.BEARISH,
        invalidation_price=4100.0,
        target_price=4100.0,
    )
