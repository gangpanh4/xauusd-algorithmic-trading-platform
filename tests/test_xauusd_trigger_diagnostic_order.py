from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from core.market_structure.enums import TrendDirection
from core.strategies.enums import SetupDirection
from core.strategies.xauusd_bos_choch import XAUUSDBOSCHOCHStrategy


def _setup():
    return SimpleNamespace(
        setup_id=uuid4(),
        direction=SetupDirection.BUY,
    )


def _context(*, current_bar_index: int):
    return SimpleNamespace(
        multi_timeframe=SimpleNamespace(m5=object()),
        current_bar_index=current_bar_index,
        current_bar=SimpleNamespace(
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            close=4100.0,
        ),
    )


def _event(*, confirmation_index: int, age: int):
    return SimpleNamespace(
        direction=TrendDirection.BULLISH,
        confirmation_index=confirmation_index,
        age=age,
    )


def test_stale_aligned_event_reports_not_fresh_before_index_mismatch(
    monkeypatch,
) -> None:
    strategy = XAUUSDBOSCHOCHStrategy()
    structure = SimpleNamespace(
        last_bos=_event(
            confirmation_index=11,
            age=1,
        ),
        last_choch=None,
    )
    monkeypatch.setattr(
        strategy,
        "_structure_state",
        lambda _: structure,
    )

    trigger, reason_code, reason = strategy._entry_trigger_diagnostic(
        _setup(),
        _context(current_bar_index=12),
    )

    assert trigger is None
    assert reason_code == "M5_EVENT_NOT_FRESH"
    assert "not fresh" in reason.lower()


def test_fresh_event_with_inconsistent_index_reports_index_mismatch(
    monkeypatch,
) -> None:
    strategy = XAUUSDBOSCHOCHStrategy()
    structure = SimpleNamespace(
        last_bos=_event(
            confirmation_index=11,
            age=0,
        ),
        last_choch=None,
    )
    monkeypatch.setattr(
        strategy,
        "_structure_state",
        lambda _: structure,
    )

    trigger, reason_code, _ = strategy._entry_trigger_diagnostic(
        _setup(),
        _context(current_bar_index=12),
    )

    assert trigger is None
    assert reason_code == "M5_CONFIRMATION_INDEX_MISMATCH"
