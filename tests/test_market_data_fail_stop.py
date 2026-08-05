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


def test_historical_bars_preserve_ascending_mt5_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    timestamps = [
        datetime(2026, 8, 5, 3, 40, tzinfo=UTC),
        datetime(2026, 8, 5, 3, 45, tzinfo=UTC),
        datetime(2026, 8, 5, 3, 50, tzinfo=UTC),
    ]
    rates = tuple(
        {
            "time": int(timestamp.timestamp()),
            "open": 3300.0 + index,
            "high": 3301.0 + index,
            "low": 3299.0 + index,
            "close": 3300.5 + index,
            "tick_volume": 100 + index,
        }
        for index, timestamp in enumerate(timestamps)
    )
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: rates,
    )

    bars = service.get_historical_bars(3)

    assert [bar.timestamp for bar in bars] == timestamps


def test_historical_duplicate_timestamp_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = _service()
    timestamp = datetime(2026, 8, 5, 3, 40, tzinfo=UTC)
    rates = (
        {
            "time": int(timestamp.timestamp()),
            "open": 3300.0,
            "high": 3301.0,
            "low": 3299.0,
            "close": 3300.5,
            "tick_volume": 100,
        },
        {
            "time": int(timestamp.timestamp()),
            "open": 3300.5,
            "high": 3301.5,
            "low": 3299.5,
            "close": 3301.0,
            "tick_volume": 101,
        },
    )
    monkeypatch.setattr(
        market_data.mt5,
        "copy_rates_from_pos",
        lambda *args: rates,
    )

    with pytest.raises(
        RuntimeError,
        match="strictly increasing",
    ):
        service.get_historical_bars(2)


def test_broker_server_offset_normalizes_latest_bar_to_actual_utc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MarketDataService(
        symbol="XAUUSD",
        timeframe=5,
        server_utc_offset_hours=3.0,
    )
    actual_utc = datetime(2026, 8, 5, 10, 10, tzinfo=UTC)
    broker_encoded = actual_utc.replace(hour=13)
    rates = (
        {
            "time": int(broker_encoded.timestamp()),
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

    bar = service.get_latest_closed_bar()

    assert bar is not None
    assert bar.timestamp == actual_utc


def test_clock_alignment_accepts_correct_configured_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MarketDataService(
        symbol="XAUUSD",
        timeframe=5,
        server_utc_offset_hours=3.0,
        max_clock_skew_seconds=2.0,
    )
    reference = datetime(2026, 8, 5, 10, 16, 26, tzinfo=UTC)
    broker_encoded = reference.replace(hour=13)
    monkeypatch.setattr(
        market_data.mt5,
        "symbol_info_tick",
        lambda symbol: type(
            "Tick",
            (),
            {"time": int(broker_encoded.timestamp())},
        )(),
    )

    normalized = service.validate_clock_alignment(
        reference_utc=reference,
    )

    assert normalized == reference


def test_clock_alignment_fails_closed_for_wrong_offset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MarketDataService(
        symbol="XAUUSD",
        timeframe=5,
        server_utc_offset_hours=0.0,
        max_clock_skew_seconds=120.0,
    )
    reference = datetime(2026, 8, 5, 10, 16, 26, tzinfo=UTC)
    broker_encoded = reference.replace(hour=13)
    monkeypatch.setattr(
        market_data.mt5,
        "symbol_info_tick",
        lambda symbol: type(
            "Tick",
            (),
            {"time": int(broker_encoded.timestamp())},
        )(),
    )

    with pytest.raises(
        RuntimeError,
        match="outside the allowed UTC skew",
    ):
        service.validate_clock_alignment(
            reference_utc=reference,
        )


def test_clock_alignment_fails_when_tick_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MarketDataService(
        symbol="XAUUSD",
        timeframe=5,
        server_utc_offset_hours=3.0,
    )
    monkeypatch.setattr(
        market_data.mt5,
        "symbol_info_tick",
        lambda symbol: None,
    )
    monkeypatch.setattr(
        market_data.mt5,
        "last_error",
        lambda: (-10004, "No IPC connection"),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to retrieve latest tick",
    ):
        service.validate_clock_alignment()
