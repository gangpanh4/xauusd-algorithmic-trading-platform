from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan
from types import SimpleNamespace

import pytest

import core.data.quote as quote_module
from core.data.quote import MarketQuote, QuoteReader

RAW_TIME = datetime(2026, 8, 16, 12, 0, tzinfo=UTC).timestamp()


def _tick(*, time: float = RAW_TIME, bid: float = 4400.0, ask: float = 4400.2) -> SimpleNamespace:
    return SimpleNamespace(time=time, bid=bid, ask=ask)


def test_valid_quote_is_read_without_mt5_lifecycle_ownership(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quote_module.mt5, "symbol_info_tick", lambda symbol: _tick())
    quote = QuoteReader(" xauusd ").read()

    assert quote.symbol == "XAUUSD"
    assert quote.timestamp_utc == datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
    assert quote.bid == pytest.approx(4400.0)
    assert quote.ask == pytest.approx(4400.2)
    assert quote.mid == pytest.approx(4400.1)
    assert quote.spread_price == pytest.approx(0.2)


def test_configured_plus_three_broker_offset_is_subtracted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quote_module.mt5, "symbol_info_tick", lambda symbol: _tick())
    quote = QuoteReader("XAUUSD", server_utc_offset_hours=3.0).read()

    assert quote.timestamp_utc == datetime(2026, 8, 16, 9, 0, tzinfo=UTC)


@pytest.mark.parametrize("bad", [nan, inf, -inf])
def test_non_finite_timestamp_is_rejected(monkeypatch: pytest.MonkeyPatch, bad: float) -> None:
    monkeypatch.setattr(quote_module.mt5, "symbol_info_tick", lambda symbol: _tick(time=bad))
    with pytest.raises(ValueError, match="finite"):
        QuoteReader("XAUUSD").read()


@pytest.mark.parametrize(
    ("bid", "ask"),
    [
        (0.0, 1.0),
        (-1.0, 1.0),
        (1.0, 0.0),
        (1.0, -1.0),
        (nan, 1.0),
        (1.0, nan),
        (inf, inf),
        (2.0, 1.0),
    ],
)
def test_invalid_prices_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    bid: float,
    ask: float,
) -> None:
    monkeypatch.setattr(
        quote_module.mt5,
        "symbol_info_tick",
        lambda symbol: _tick(bid=bid, ask=ask),
    )
    with pytest.raises(ValueError):
        QuoteReader("XAUUSD").read()


def test_missing_tick_reports_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(quote_module.mt5, "symbol_info_tick", lambda symbol: None)
    monkeypatch.setattr(quote_module.mt5, "last_error", lambda: (1, "not connected"))

    with pytest.raises(RuntimeError, match="not connected"):
        QuoteReader("XAUUSD").read()


def test_missing_required_tick_field_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        quote_module.mt5,
        "symbol_info_tick",
        lambda symbol: SimpleNamespace(time=RAW_TIME, bid=4400.0),
    )
    with pytest.raises(RuntimeError, match="missing a required field"):
        QuoteReader("XAUUSD").read()


def test_market_quote_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        MarketQuote(
            "XAUUSD",
            datetime(2026, 8, 16, 12, 0),  # noqa: DTZ001
            4400.0,
            4400.2,
        )


def test_reader_rejects_non_finite_offset() -> None:
    with pytest.raises(ValueError, match="finite"):
        QuoteReader("XAUUSD", server_utc_offset_hours=inf)


def test_quote_reader_source_contains_no_lifecycle_or_order_api_calls() -> None:
    source_path = quote_module.__file__
    assert source_path is not None

    with open(source_path, encoding="utf-8") as handle:
        text = handle.read()

    forbidden = (
        "mt5.initialize",
        "mt5.shutdown",
        "order_send",
        "order_check",
        "positions_get",
        "orders_get",
    )
    for token in forbidden:
        assert token not in text