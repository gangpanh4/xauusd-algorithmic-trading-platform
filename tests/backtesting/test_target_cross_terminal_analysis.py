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


def test_target_cross_becomes_hypothetical_terminal_observation() -> None:
    setup = SimpleNamespace(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.BUY,
        detected_at=datetime(2026, 1, 1, 11, 15, tzinfo=UTC),
        invalidation=_reference(90.0),
        stop_reference=_reference(90.0),
        target_references=(_reference(105.0),),
    )
    calls = {"count": 0}

    class StrategyStub:
        config = SimpleNamespace(minimum_target_reward_risk=1.0)

        def _entry_trigger_diagnostic(self, setup_value, context):
            calls["count"] += 1
            if calls["count"] == 3:
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
            current_bar=_bar(10, high=106.0, low=103.0, close=105.0),
        ),
    )
    tracker.observe(
        strategy=StrategyStub(),
        context=SimpleNamespace(
            current_bar=_bar(15, high=107.0, low=104.0, close=106.0),
        ),
    )

    record = tracker.records[0]
    assert record.hypothetical_terminal_reason == (
        "TARGET_REACHED_BEFORE_TRIGGER"
    )
    assert record.hypothetical_terminal_at == datetime(
        2026, 1, 1, 12, 5, tzinfo=UTC
    )
    assert record.bars_after_expiry_at_hypothetical_terminal == 1
    assert record.setup_age_minutes_at_hypothetical_terminal == 50.0
    assert record.trigger_appeared_after_hypothetical_terminal is True
    assert record.candidate_created_after_hypothetical_terminal is False
    assert record.bars_from_hypothetical_terminal_to_trigger == 2


def test_uncrossed_target_has_no_hypothetical_terminal() -> None:
    setup = SimpleNamespace(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.SELL,
        detected_at=datetime(2026, 1, 1, 11, 15, tzinfo=UTC),
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
    assert record.hypothetical_terminal_reason is None
    assert record.hypothetical_terminal_at is None
    assert record.trigger_appeared_after_hypothetical_terminal is False
    assert record.candidate_created_after_hypothetical_terminal is False
    assert record.bars_from_hypothetical_terminal_to_trigger is None
