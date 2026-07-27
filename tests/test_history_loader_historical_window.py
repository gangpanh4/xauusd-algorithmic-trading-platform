from __future__ import annotations

from datetime import UTC, datetime

import MetaTrader5 as mt5
import pytest

from core.backtesting.history_loader import HistoryLoader


def _rates() -> list[dict[str, object]]:
    return [
        {
            "time": int(datetime(2026, 4, 9, 10, 0, tzinfo=UTC).timestamp()),
            "open": 3000.0,
            "high": 3002.0,
            "low": 2999.0,
            "close": 3001.0,
            "tick_volume": 100,
            "spread": 10,
            "real_volume": 0,
        },
        {
            "time": int(datetime(2026, 4, 9, 10, 15, tzinfo=UTC).timestamp()),
            "open": 3001.0,
            "high": 3003.0,
            "low": 3000.0,
            "close": 3002.0,
            "tick_volume": 110,
            "spread": 10,
            "real_volume": 0,
        },
    ]


def test_latest_history_preserves_copy_rates_from_pos(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        mt5,
        "copy_rates_from_pos",
        lambda *args: calls.append(args) or _rates(),
    )
    monkeypatch.setattr(
        mt5,
        "copy_rates_from",
        lambda *args: pytest.fail("copy_rates_from must not be called"),
    )

    history = HistoryLoader().load_history(
        "XAUUSD",
        mt5.TIMEFRAME_M15,
        200,
    )

    assert len(history) == 2
    assert calls == [("XAUUSD", mt5.TIMEFRAME_M15, 0, 200)]


def test_explicit_end_time_uses_copy_rates_from(monkeypatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        mt5,
        "copy_rates_from",
        lambda *args: calls.append(args) or _rates(),
    )
    monkeypatch.setattr(
        mt5,
        "copy_rates_from_pos",
        lambda *args: pytest.fail("copy_rates_from_pos must not be called"),
    )
    end_time = datetime(2026, 4, 9, 12, 0, tzinfo=UTC)

    history = HistoryLoader().load_history(
        "XAUUSD",
        mt5.TIMEFRAME_M15,
        200,
        end_time=end_time,
    )

    assert len(history) == 2
    assert calls == [
        ("XAUUSD", mt5.TIMEFRAME_M15, end_time, 200)
    ]


def test_naive_end_time_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(
        mt5,
        "copy_rates_from",
        lambda *args: pytest.fail("MT5 must not be called"),
    )

    with pytest.raises(ValueError, match="end_time must be timezone-aware"):
        HistoryLoader().load_history(
            "XAUUSD",
            mt5.TIMEFRAME_M15,
            200,
            end_time=datetime(2026, 4, 9, 12, 0),
        )
