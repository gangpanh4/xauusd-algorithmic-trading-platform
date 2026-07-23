from __future__ import annotations

from datetime import UTC, datetime

import pytest

import core.data.market_data as market_data
from core.data.market_data import MarketDataService
from core.mt5_execution.config import MT5ExecutionConfig


def _service() -> MarketDataService:
    return MarketDataService(
        symbol="XAUUSD",
        timeframe=5,
    )


def test_latest_bar_query_failure_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: None,
    )
    monkeypatch.setattr(
        market_data.mt5,
        "last_error",
        lambda: (-10004, "No IPC connection"),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve latest closed bar for XAUUSD",
    ):
        service.get_latest_closed_bar()


def test_latest_bar_empty_successful_query_means_no_new_bar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: (),
    )

    assert service.get_latest_closed_bar() is None


def test_historical_query_failure_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: None,
    )
    monkeypatch.setattr(
        market_data.mt5,
        "last_error",
        lambda: (-10005, "IPC timeout"),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve historical bars for XAUUSD",
    ):
        service.get_historical_bars(100)


def test_historical_empty_successful_query_returns_empty_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: (),
    )

    assert service.get_historical_bars(100) == []


def test_latest_bar_preserves_completed_bar_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    timestamp = datetime(2026, 7, 23, 8, 0, tzinfo=UTC)
    rates = (
        {
            "time": int(timestamp.timestamp()),
            "open": 3300.0,
            "high": 3305.0,
            "low": 3298.0,
            "close": 3303.0,
            "tick_volume": 1000,
        },
    )
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: rates,
    )

    first = service.get_latest_closed_bar()
    second = service.get_latest_closed_bar()

    assert first is not None
    assert first.timestamp == timestamp
    assert first.close == pytest.approx(3303.0)
    assert second is None


def test_auto_reconnect_is_disabled_until_resynchronization_exists() -> None:
    assert MT5ExecutionConfig().enable_auto_reconnect is False
