from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from core.backtesting.candidate_outcome_models import CandidateOutcome
from core.backtesting.post_expiry_trigger_tracker import (
    PostExpiryTriggerTracker,
)
from core.data.models import MarketBar
from core.strategies.enums import EntryTriggerType, SetupDirection


def _bar(minute: int) -> MarketBar:
    return MarketBar(
        timestamp=datetime(2026, 1, 1, 12, minute, tzinfo=UTC),
        open=100.0,
        high=111.0,
        low=99.0,
        close=108.0,
        tick_volume=1,
    )


def test_late_trigger_records_geometry_and_outcome() -> None:
    setup = SimpleNamespace(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.BUY,
    )
    trigger = SimpleNamespace(
        trigger_type=EntryTriggerType.BOS_CONFIRMATION,
    )
    candidate = SimpleNamespace(
        entry_price=100.0,
        stop_loss_price=95.0,
        take_profit_prices=(110.0,),
        initial_risk_distance=5.0,
    )
    evaluation = SimpleNamespace(
        outcome=CandidateOutcome.TARGET_REACHED,
        outcome_timestamp=datetime(2026, 1, 1, 12, 10, tzinfo=UTC),
        bars_evaluated=1,
        maximum_favorable_r_multiple=2.2,
        maximum_adverse_r_multiple=0.2,
    )
    evaluator = SimpleNamespace(
        evaluate=lambda candidate_value, bars, maximum_bars: evaluation
    )

    class StrategyStub:
        def _entry_trigger_diagnostic(self, setup_value, context):
            return trigger, "TRIGGER_CONFIRMED", "confirmed"

        def _candidate_trade(self, *, setup, trigger):
            return candidate

    tracker = PostExpiryTriggerTracker(
        maximum_bars=8,
        outcome_maximum_bars=24,
        outcome_evaluator=evaluator,
    )
    tracker.register(
        setup,
        expired_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )

    tracker.observe(
        strategy=StrategyStub(),
        context=SimpleNamespace(current_bar=_bar(5)),
    )
    tracker.observe(
        strategy=StrategyStub(),
        context=SimpleNamespace(current_bar=_bar(10)),
    )

    record = tracker.records[0]
    assert record.trigger_found is True
    assert record.geometry_valid is True
    assert record.reward_risk == 2.0
    assert record.outcome == "TARGET_REACHED"
    assert record.outcome_bars_evaluated == 1
    assert record.maximum_favorable_r_multiple == 2.2
    assert record.outcome_window_complete is True
