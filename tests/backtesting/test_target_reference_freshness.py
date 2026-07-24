from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from core.backtesting.post_expiry_trigger_tracker import (
    PostExpiryTriggerTracker,
)
from core.data.models import MarketBar
from core.strategies.enums import EntryTriggerType, SetupDirection


def _reference(price: float):
    return SimpleNamespace(price=price)


def _bar(minute: int, *, high: float, low: float, close: float) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, 12, minute, tzinfo=UTC),
        open=close,
        high=high,
        low=low,
        close=close,
        tick_volume=1,
    )


def test_buy_target_crossed_before_late_trigger_is_recorded() -> None:
    setup = SimpleNamespace(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.BUY,
        invalidation=_reference(90.0),
        stop_reference=_reference(90.0),
        target_references=(_reference(105.0),),
    )
    calls = {"count": 0}

    class StrategyStub:
        config = SimpleNamespace(minimum_target_reward_risk=1.0)

        def _entry_trigger_diagnostic(self, setup_value, context):
            calls["count"] += 1
            if calls["count"] == 2:
                return (
                    SimpleNamespace(
                        trigger_type=EntryTriggerType.BOS_CONFIRMATION,
                        trigger_price=106.0,
                    ),
                    "TRIGGER_CONFIRMED",
                    "confirmed",
                )
            return None, "NO_M5_STRUCTURE_EVENT", "none"

        def _candidate_trade(self, *, setup, trigger):
            return None

    tracker = PostExpiryTriggerTracker(maximum_bars=8)
    tracker.register(
        setup,
        expired_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    tracker.observe(
        strategy=StrategyStub(),
        context=SimpleNamespace(
            current_bar=_bar(5, high=105.5, low=99.0, close=104.0),
        ),
    )
    tracker.observe(
        strategy=StrategyStub(),
        context=SimpleNamespace(
            current_bar=_bar(10, high=107.0, low=104.0, close=106.0),
        ),
    )

    record = tracker.records[0]
    assert record.target_crossed_before_trigger is True
    assert record.first_target_crossed_at == datetime(
        2026, 1, 1, 12, 5, tzinfo=UTC
    )
    assert record.bars_since_target_cross == 1
    assert record.nearest_target_price == 105.0
    assert record.target_directionally_valid_at_trigger is False
    assert record.target_distance_at_first_post_expiry_bar == 1.0
    assert record.target_distance_at_trigger == 1.0


def test_sell_target_not_crossed_and_still_valid_at_trigger() -> None:
    setup = SimpleNamespace(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.SELL,
        invalidation=_reference(110.0),
        stop_reference=_reference(110.0),
        target_references=(_reference(95.0),),
    )

    class StrategyStub:
        config = SimpleNamespace(minimum_target_reward_risk=1.0)

        def _entry_trigger_diagnostic(self, setup_value, context):
            return (
                SimpleNamespace(
                    trigger_type=EntryTriggerType.BOS_CONFIRMATION,
                    trigger_price=100.0,
                ),
                "TRIGGER_CONFIRMED",
                "confirmed",
            )

        def _candidate_trade(self, *, setup, trigger):
            return None

    tracker = PostExpiryTriggerTracker(maximum_bars=8)
    tracker.register(
        setup,
        expired_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    tracker.observe(
        strategy=StrategyStub(),
        context=SimpleNamespace(
            current_bar=_bar(5, high=102.0, low=99.0, close=100.0),
        ),
    )

    record = tracker.records[0]
    assert record.target_crossed_before_trigger is False
    assert record.first_target_crossed_at is None
    assert record.bars_since_target_cross is None
    assert record.nearest_target_price == 95.0
    assert record.target_directionally_valid_at_trigger is True
    assert record.target_distance_at_trigger == 5.0
