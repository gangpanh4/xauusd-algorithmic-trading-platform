from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from core.market_structure.enums import TrendDirection
from core.strategies.enums import SetupDirection
from core.strategies.xauusd_bos_choch import XAUUSDBOSCHOCHStrategy


def setup():
    return SimpleNamespace(setup_id=uuid4(), direction=SetupDirection.BUY)


def context(index=12):
    return SimpleNamespace(
        multi_timeframe=SimpleNamespace(m5=object()),
        current_bar_index=index,
        current_bar=SimpleNamespace(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC), close=4100.0
        ),
    )


def event(direction, index, age):
    return SimpleNamespace(
        direction=direction, confirmation_index=index, age=age
    )


@pytest.mark.parametrize(
    ("structure", "code"),
    [
        (None, "NO_M5_STRUCTURE_STATE"),
        (SimpleNamespace(last_bos=None, last_choch=None), "NO_M5_STRUCTURE_EVENT"),
        (SimpleNamespace(last_bos=event(TrendDirection.BEARISH, 12, 0), last_choch=None), "M5_DIRECTION_MISMATCH"),
        (SimpleNamespace(last_bos=event(TrendDirection.BULLISH, 11, 0), last_choch=None), "M5_CONFIRMATION_INDEX_MISMATCH"),
        (SimpleNamespace(last_bos=event(TrendDirection.BULLISH, 12, 1), last_choch=None), "M5_EVENT_NOT_FRESH"),
    ],
)
def test_trigger_rejection_diagnostic(monkeypatch, structure, code):
    strategy = XAUUSDBOSCHOCHStrategy()
    monkeypatch.setattr(strategy, "_structure_state", lambda _: structure)
    trigger, reason_code, reason = strategy._entry_trigger_diagnostic(
        setup(), context()
    )
    assert trigger is None
    assert reason_code == code
    assert reason


def test_entry_trigger_wrapper_keeps_none_contract(monkeypatch):
    strategy = XAUUSDBOSCHOCHStrategy()
    monkeypatch.setattr(
        strategy,
        "_entry_trigger_diagnostic",
        lambda setup, context: (None, "NO_M5_STRUCTURE_EVENT", "No event."),
    )
    assert strategy._entry_trigger(setup(), context()) is None
