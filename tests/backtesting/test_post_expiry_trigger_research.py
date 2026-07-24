from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from core.backtesting.exporter import BacktestExporter
from core.backtesting.post_expiry_trigger_tracker import PostExpiryTriggerTracker
from core.backtesting.strategy_comparison import BacktestStrategyComparison
from core.strategies.enums import EntryTriggerType, SetupDirection


def _setup():
    return SimpleNamespace(
        setup_id=uuid4(),
        strategy_id="XAUUSD_BOS_CHOCH_V1",
        direction=SetupDirection.BUY,
    )


def _context(minute: int):
    return SimpleNamespace(
        current_bar=SimpleNamespace(
            timestamp=datetime(2026, 1, 1, 12, minute, tzinfo=UTC),
        )
    )


def test_tracker_records_first_trigger_after_expiry() -> None:
    tracker = PostExpiryTriggerTracker(maximum_bars=8)
    setup = _setup()
    expired_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    tracker.register(setup, expired_at=expired_at)

    calls = {"count": 0}

    class StrategyStub:
        def _entry_trigger_diagnostic(self, setup_value, context):
            calls["count"] += 1
            if calls["count"] == 3:
                return (
                    SimpleNamespace(trigger_type=EntryTriggerType.BOS_CONFIRMATION),
                    "TRIGGER_CONFIRMED",
                    "confirmed",
                )
            return None, "M5_EVENT_NOT_FRESH", "stale"
        
        def _candidate_trade(self, *, setup, trigger):
            return None

    strategy = StrategyStub()
    tracker.observe(strategy=strategy, context=_context(5))
    tracker.observe(strategy=strategy, context=_context(10))
    tracker.observe(strategy=strategy, context=_context(15))

    record = tracker.records[0]
    assert record.trigger_found is True
    assert record.bars_observed == 3
    assert record.bars_after_expiry == 3
    assert record.trigger_type == EntryTriggerType.BOS_CONFIRMATION.value
    assert record.window_complete is True


def test_tracker_closes_without_trigger_after_maximum_bars() -> None:
    tracker = PostExpiryTriggerTracker(maximum_bars=2)
    tracker.register(
        _setup(),
        expired_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    strategy = SimpleNamespace(
        _entry_trigger_diagnostic=lambda setup_value, context: (
            None,
            "NO_M5_STRUCTURE_EVENT",
            "none",
        )
    )
    tracker.observe(strategy=strategy, context=_context(5))
    tracker.observe(strategy=strategy, context=_context(10))

    record = tracker.records[0]
    assert record.trigger_found is False
    assert record.bars_observed == 2
    assert record.window_complete is True


def test_exporter_writes_post_expiry_report(tmp_path: Path) -> None:
    tracker = PostExpiryTriggerTracker(maximum_bars=1)
    tracker.register(
        _setup(),
        expired_at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
    )
    strategy = SimpleNamespace(
        _entry_trigger_diagnostic=lambda setup_value, context: (
            None,
            "NO_M5_STRUCTURE_EVENT",
            "none",
        )
    )
    tracker.observe(strategy=strategy, context=_context(5))

    comparison = BacktestStrategyComparison(
        pipeline_observation_count=0,
        pipeline_approval_count=0,
        executed_trade_count=0,
        strategy_observation_count=0,
        strategy_setup_count=1,
        strategy_candidate_count=0,
        pipeline_reason_counts=(),
        strategy_reason_counts=(),
        events=(),
        post_expiry_triggers=tracker.records,
    )
    path = BacktestExporter(tmp_path).export_strategy_post_expiry_triggers(
        comparison
    )
    with path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    assert path.name == "strategy_post_expiry_triggers.csv"
    assert len(rows) == 1
    assert rows[0]["Trigger Found"] == "False"
    assert rows[0]["Bars Observed"] == "1"
